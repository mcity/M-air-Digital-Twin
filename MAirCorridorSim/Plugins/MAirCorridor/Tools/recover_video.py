"""recover_video.py - make a video playable again after a recording was cut short.

    py -3.10 recover_video.py missions/flights/20261004-104219
    py -3.10 recover_video.py missions/flights/20261004-104219/Chase_scene_camera/Chase.mp4
    py -3.10 recover_video.py missions/flights/20261004-104219 --replace

WHAT GOES WRONG. An MP4 keeps its frame index and its decoder configuration in a moov box, and that
box is written when the file is CLOSED. A recording that ends by power cut, by a crash, or by the
process being killed leaves every frame sitting in the file and no moov in front of them, so no
player will open it. The frames are not lost; the table of contents is.

HOW THIS GETS THEM BACK. For MPEG-4 Part 2, which is what these recordings use, the decoder
configuration is a short VOS and VOL header that depends on the encoder, the frame size and the
frame rate, and not at all on the pictures. So this writes a throwaway file with the same encoder
and size, lifts the configuration out of it, puts that in front of the orphaned picture data, and
remuxes the result. index.jsonl, which the recorder writes a line at a time and which therefore
survives, supplies the size and the rate.

WHAT YOU GET BACK. Every frame, at the rate the frames were actually captured, rounded to a whole
number because a fractional rate does not survive the remux. index.jsonl holds the exact timestamp
of every frame either way, and that remains the authority on timing.

fly_mission.py no longer needs this when it is stopped from the planner or with Ctrl-C: it closes
its files on the way out. This is for the times nothing gets a chance to run.
"""
import argparse
import io
import json
import os
import struct
import subprocess
import sys


def boxes(data, start=0, end=None):
    """Walk an ISO base media file's boxes, yielding (type, payload start, box end)."""
    end = len(data) if end is None else end
    i = start
    while i + 8 <= end:
        size = struct.unpack(">I", data[i:i + 4])[0]
        kind = data[i + 4:i + 8]
        body = i + 8
        if size == 1:                                    # 64 bit size
            size = struct.unpack(">Q", data[i + 8:i + 16])[0]
            body = i + 16
        if size == 0:                                    # runs to the end of the file
            size = end - i
        if size < 8:
            break
        yield kind, body, i + size
        i += size


def find(data, path, start=0, end=None):
    """The payload range of a nested box, by path, for example (b"moov", b"trak")."""
    for kind, body, stop in boxes(data, start, end):
        if kind == path[0]:
            if len(path) == 1:
                return body, stop
            deeper = find(data, path[1:], body, stop)
            if deeper:
                return deeper
    return None


def descriptor_length(blob, at):
    """An MPEG-4 descriptor length, which is base 128 with a continuation bit."""
    value, size = 0, 0
    while at + size < len(blob):
        byte = blob[at + size]
        value = (value << 7) | (byte & 0x7F)
        size += 1
        if not byte & 0x80 or size > 4:
            break
    return value, size


def decoder_config(mp4_bytes):
    """The esds DecoderSpecificInfo, which for MPEG-4 Part 2 is the VOS and VOL headers."""
    stsd = find(mp4_bytes, (b"moov", b"trak", b"mdia", b"minf", b"stbl", b"stsd"))
    if not stsd:
        return None
    entry = find(mp4_bytes, (b"mp4v",), stsd[0] + 8, stsd[1])
    if not entry:
        return None
    # 78 bytes of visual sample entry sit before the child boxes.
    esds = find(mp4_bytes, (b"esds",), entry[0] + 78, entry[1])
    if not esds:
        return None
    blob = mp4_bytes[esds[0] + 4:esds[1]]                # past version and flags
    i = 0
    while i < len(blob):
        tag = blob[i]
        size, used = descriptor_length(blob, i + 1)
        payload = i + 1 + used
        if tag == 0x03:                                  # ES descriptor
            i = payload + 3                              # id and flags
        elif tag == 0x04:                                # decoder config descriptor
            i = payload + 13                             # type, stream type, buffer, bitrates
        elif tag == 0x05:                                # the one we are after
            return blob[payload:payload + size]
        else:
            i = payload + size
    return None


def reference_config(width, height, fps):
    """Write a throwaway file with the same encoder and size, and lift its configuration out."""
    try:
        import cv2
        import numpy as np
    except ImportError:
        sys.exit("this needs opencv and numpy: py -3.10 -m pip install -r requirements.txt")
    path = os.path.join(os.environ.get("TEMP", "."), "_recover_reference.mp4")
    writer = cv2.VideoWriter(path, cv2.VideoWriter_fourcc(*"mp4v"), float(fps), (width, height))
    if not writer.isOpened():
        sys.exit("opencv would not open a writer for %dx%d" % (width, height))
    for _ in range(3):
        writer.write(np.zeros((height, width, 3), dtype="uint8"))
    writer.release()
    config = decoder_config(io.open(path, "rb").read())
    try:
        os.remove(path)
    except OSError:
        pass
    return config


def from_index(video_path):
    """Frame size and the rate the frames arrived at, from the index beside the video.

    The index is written a line at a time precisely so that it survives what the video did not."""
    index = os.path.join(os.path.dirname(os.path.abspath(video_path)), "index.jsonl")
    if not os.path.isfile(index):
        return None
    rows = []
    with io.open(index, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except ValueError:
                continue                                 # a half written last line
    if not rows:
        return None
    width = next((r["w"] for r in rows if r.get("w")), 0)
    height = next((r["h"] for r in rows if r.get("h")), 0)
    sims = [r["sim_ns"] for r in rows if r.get("sim_ns") is not None]
    rate = None
    if len(sims) > 1 and sims[-1] > sims[0]:
        rate = (len(sims) - 1) / ((sims[-1] - sims[0]) / 1e9)
    elif len(rows) > 1 and rows[-1].get("t", 0) > rows[0].get("t", 0):
        rate = (len(rows) - 1) / (rows[-1]["t"] - rows[0]["t"])
    return {"width": int(width), "height": int(height), "frames": len(rows), "rate": rate}


def needs_recovery(path):
    """True when the file has picture data but no moov box to describe it."""
    data = io.open(path, "rb").read(16 * 1024)
    if b"moov" in data:
        return False
    with io.open(path, "rb") as f:
        try:
            f.seek(-512 * 1024, os.SEEK_END)
        except OSError:
            f.seek(0)
        return b"moov" not in f.read()


def container_fps(path):
    """The rate the file says it is, which is not always the rate it was captured at."""
    try:
        import cv2
    except ImportError:
        return None
    cap = cv2.VideoCapture(path)
    rate = cap.get(cv2.CAP_PROP_FPS) if cap.isOpened() else None
    cap.release()
    return rate or None


def recover(video_path, width=0, height=0, fps=0.0, replace=False, quiet=False, retime=False):
    """Returns the path written, or None when nothing needed doing."""
    def say(text):
        if not quiet:
            print(text)

    if not needs_recovery(video_path):
        # Playable, but possibly at the wrong speed: a recording made before the rate was
        # measured carries whatever was asked for, and the frames arrived at whatever the sim
        # could manage. Same rebuild, done for the timing rather than for the index.
        if not retime:
            say("%s is already playable" % video_path)
            return None
        facts = from_index(video_path) or {}
        measured, says = facts.get("rate"), container_fps(video_path)
        if not measured or not says:
            say("%s: no measured rate to compare against, left alone" % video_path)
            return None
        if abs(says - measured) / measured <= 0.2:
            say("%s plays at %.2f fps and was captured at %.2f, which is close enough"
                % (os.path.basename(video_path), says, measured))
            return None
        say("%s plays at %.2f fps but was captured at %.2f, so it runs %.1f times too fast"
            % (os.path.basename(video_path), says, measured, says / measured))

    facts = from_index(video_path) or {}
    width = width or facts.get("width") or 0
    height = height or facts.get("height") or 0
    rate = fps or facts.get("rate") or 0.0
    if not width or not height:
        sys.exit("I need the frame size: there is no usable index.jsonl beside %s, so pass "
                 "--width and --height" % video_path)
    # A fractional rate does not survive the remux, so the header gets a whole number. The exact
    # per frame timing stays in index.jsonl.
    whole = max(1, min(120, int(round(rate or 10.0))))
    say("%s: %dx%d, %s frames in the index, captured at %s"
        % (os.path.basename(video_path), width, height, facts.get("frames", "an unknown number"),
           "%.2f fps" % rate if rate else "an unknown rate"))

    config = reference_config(width, height, whole)
    if not config:
        sys.exit("could not read a decoder configuration out of the reference file")

    data = io.open(video_path, "rb").read()
    mdat = find(data, (b"mdat",))
    payload = data[mdat[0]:mdat[1]] if mdat else data
    stream = video_path + ".m4v"
    with io.open(stream, "wb") as f:
        f.write(config)
        f.write(payload)

    out = video_path + (".retimed.mp4" if retime else ".recovered.mp4")
    done = subprocess.run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
                           "-f", "m4v", "-framerate", str(whole), "-i", stream,
                           "-c", "copy", out], capture_output=True, text=True)
    try:
        os.remove(stream)
    except OSError:
        pass
    if done.returncode != 0:
        print(done.stderr.strip())
        sys.exit("ffmpeg could not read the rebuilt stream. Is ffmpeg installed and on PATH?")

    frames = 0
    try:
        import cv2
        cap = cv2.VideoCapture(out)
        frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        cap.release()
    except ImportError:
        pass
    if frames == 0:
        say("  it rebuilt to nothing, so the file had no usable picture data in it")
        try:
            os.remove(out)
        except OSError:
            pass
        return None
    say("  %s %d frames at %d fps into %s"
        % ("retimed" if retime else "recovered", frames, whole, os.path.basename(out)))

    if replace:
        broken = video_path + (".wrongrate" if retime else ".unfinalised")
        os.replace(video_path, broken)
        os.replace(out, video_path)
        say("  put it in place; the original is %s" % os.path.basename(broken))
        return video_path
    return out


def main():
    ap = argparse.ArgumentParser(description="Make a cut short recording playable again.")
    ap.add_argument("target", help="a flight folder, a camera folder, or one .mp4")
    ap.add_argument("--replace", action="store_true",
                    help="put the recovered file in place of the broken one, keeping the "
                         "original beside it as .unfinalised")
    ap.add_argument("--width", type=int, default=0, help="only needed without an index.jsonl")
    ap.add_argument("--height", type=int, default=0)
    ap.add_argument("--fps", type=float, default=0.0,
                    help="override the rate measured from the index")
    ap.add_argument("--retime", action="store_true",
                    help="also rebuild files that play at the wrong speed because they "
                         "were recorded before the frame rate was measured")
    args = ap.parse_args()

    targets = []
    if os.path.isfile(args.target):
        targets = [args.target]
    elif os.path.isdir(args.target):
        for root, _dirs, files in os.walk(args.target):
            targets += [os.path.join(root, f) for f in sorted(files)
                        if f.lower().endswith(".mp4")
                        and not f.endswith((".recovered.mp4", ".retimed.mp4"))]
    if not targets:
        sys.exit("no .mp4 files under %s" % args.target)

    done = 0
    for path in targets:
        if recover(path, args.width, args.height, args.fps, args.replace,
                   retime=args.retime):
            done += 1
    print("\n%d of %d file(s) needed work" % (done, len(targets)))


if __name__ == "__main__":
    main()
