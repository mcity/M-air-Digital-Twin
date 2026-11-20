"""flight_perf.py - how fast recorded flights actually ran, side by side.

    py -3.10 flight_perf.py                         every flight in missions/flights
    py -3.10 flight_perf.py missions/flights/20261004-125139 missions/flights/20261005-*

WHY IT EXISTS. A simulation that feels slow can be slow in two quite different ways, and they have
different cures:

  THE SIMULATION FALLS BEHIND REAL TIME. Physics and the flight controller cannot keep up. Read it
  from "speed": simulated seconds per real second, from the pose's two clocks.

  THE CAMERAS FALL BEHIND THEIR RATE. Physics is fine, but each capture is a full render of the
  scene and the frame cannot fit them all. Read it from each camera's delivered rate against the
  rate its robot config asked for.

The first flights measured this way showed the second, badly: pose at about 300 a second and the
simulation at 0.87 to 0.96 of real time, while cameras asking for 10 and 33 frames a second
delivered 1.7 to 2.8. That pointed at the number of renders per frame, which is what was cut.

Rates are in simulated time. A flight recorded before rates were requested in the manifest shows
what it got and leaves what it asked for blank.
"""
import argparse
import glob
import io
import json
import os
import sys

from toolpaths import HERE
FLIGHTS = os.path.join(HERE, "missions", "flights")


def measure(folder):
    """One flight's speed and camera rates, from its manifest and its track."""
    manifest_path = os.path.join(folder, "manifest.json")
    manifest = {}
    if os.path.isfile(manifest_path):
        with io.open(manifest_path, encoding="utf-8") as f:
            manifest = json.load(f)
    perf = manifest.get("performance") or {}
    speed = perf.get("sim_speed")
    pose_hz = None
    track = os.path.join(folder, "track.jsonl")
    if os.path.isfile(track):
        first = last = None
        count = 0
        with io.open(track, encoding="utf-8") as f:
            for line in f:
                try:
                    row = json.loads(line)
                except ValueError:
                    continue
                if row.get("sim_ns") is None:
                    continue
                first = first or row
                last = row
                count += 1
        if first and last and last["t"] > first["t"]:
            wall = last["t"] - first["t"]
            if speed is None:
                speed = ((last["sim_ns"] - first["sim_ns"]) / 1e9) / wall
            pose_hz = count / wall
    cameras = perf.get("cameras")
    if cameras is None:
        # An older flight: work the delivered rates out from the streams themselves.
        cameras = []
        for s in manifest.get("streams", []):
            if s.get("kind") != "image" or not s.get("sim_ns_first") or s.get("messages", 0) < 3:
                continue
            span = (s["sim_ns_last"] - s["sim_ns_first"]) / 1e9
            if span > 0:
                cameras.append({"sensor": s["sensor"], "stream": s["stream"], "asked_hz": None,
                                "got_hz": round((s["messages"] - 1) / span, 2), "share": None})
    images = len(cameras)
    return {"flight": os.path.basename(folder.rstrip("/\\")),
            "mission": (manifest.get("mission") or {}).get("name"),
            "scene": (manifest.get("mission") or {}).get("scene"),
            "duration_s": manifest.get("duration_s"),
            "speed": speed, "pose_hz": pose_hz, "cameras": cameras, "images": images}


def main():
    ap = argparse.ArgumentParser(description="How fast recorded flights actually ran.")
    ap.add_argument("folders", nargs="*", help="flight folders (default: every one recorded)")
    ap.add_argument("--json", action="store_true", help="print the measurements as JSON")
    args = ap.parse_args()

    folders = []
    for pattern in (args.folders or [os.path.join(FLIGHTS, "*")]):
        folders += [f for f in sorted(glob.glob(pattern)) if os.path.isdir(f)]
    rows = [measure(f) for f in folders]
    rows = [r for r in rows if r["speed"] is not None or r["cameras"]]
    if not rows:
        sys.exit("no flights with a track or cameras to measure")
    if args.json:
        print(json.dumps(rows, indent=1))
        return

    print("%-16s %-14s %-24s %6s %7s %7s  %s" % ("flight", "mission", "scene", "speed", "pose", "images",
                                                 "cameras: delivered of asked, frames a second"))
    for r in rows:
        cams = []
        for c in r["cameras"]:
            got = "-" if c["got_hz"] is None else "%.1f" % c["got_hz"]
            asked = "?" if c["asked_hz"] is None else "%.0f" % c["asked_hz"]
            cams.append("%s/%s %s of %s" % (c["sensor"][:6], c["stream"].replace("_camera", "")[:6],
                                            got, asked))
        print("%-16s %-14s %-24s %6s %7s %7d  %s" % (
            r["flight"], (r["mission"] or "?")[:14], (r["scene"] or "?")[:24],
            "-" if r["speed"] is None else "%.2fx" % r["speed"],
            "-" if r["pose_hz"] is None else "%.0f Hz" % r["pose_hz"],
            r["images"], ", ".join(cams) or "no cameras recorded"))
    print("\nspeed is simulated seconds per real second; below about 0.97 the simulation is falling")
    print("behind. images counts the camera streams recorded. Each is a full render of the scene, and")
    print("sensors that are not recorded still render: an enabled GPU lidar draws eight a frame.")


if __name__ == "__main__":
    main()
