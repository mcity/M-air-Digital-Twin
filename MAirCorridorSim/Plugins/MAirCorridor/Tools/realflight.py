"""realflight.py - a real flight turned into a mission, and one flight measured against another.

    py -3.10 realflight.py mission real_log.csv -o missions/from_real.json
    py -3.10 realflight.py mission missions/flights/20261004-095445        (a flown sim flight)
    py -3.10 realflight.py compare missions/flights/20261004-095445 real_log.csv

WHY BOTH DIRECTIONS USE THE SAME FILES. A simulated flight recorded by fly_mission.py is a dataset
with its frame written down (see recording.py), and a real flight is a list of positions and times.
That is enough to close the loop:

  REAL TO SIM. Take the track a real aircraft flew, thin it to the waypoints that actually describe
  it, and write a mission. Flying that mission here puts the simulated aircraft along the same route
  over the same ground, so whatever the real flight saw can be compared with what the sim renders.

  SIM TO REAL. Fly a mission here with --all, fly the same mission for real, then compare the two
  tracks. The answer is a distance in metres, measured the same way the planner measures deviation
  while flying: to the nearest point on the nearest leg, not to the nearest waypoint.

WHAT IT READS. A flight folder written by fly_mission.py (track.jsonl beside its manifest.json), a
CSV with longitude, latitude and altitude columns under almost any spelling, JSON lines with the
same fields, or a GPX track. A log in a vendor's binary format has to be exported to one of those
first; ArduPilot, PX4 and DJI tools all do it.

ALTITUDE IS THE TRAP, AND IT IS NOT A SMALL ONE. This project's ground elevations come from USGS
3DEP, which is height above the NAVD88 geoid. A GPS receiver usually reports height above the WGS84
ELLIPSOID, and around Ann Arbor the geoid sits about 34 metres BELOW the ellipsoid, so an NAVD88
elevation is roughly 34 metres LARGER than the ellipsoidal height of the same point: a log of
ellipsoidal heights needs about +34 to match this landscape. Thirty four metres is the difference
between flying over the trees and flying through them.

Nothing here guesses the sign for you, and nothing should. --altitude-offset is added to every
height in the log and defaults to zero, and the import measures what the heights come out as above
the ground so the arithmetic can be checked against a flight whose real height is known.
"""
import argparse
import csv
import io
import json
import math
import os
import sys
import xml.etree.ElementTree as ET

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from toolpaths import HERE                                                          # noqa: E402
import recording as rec                                                               # noqa: E402
from flightplan import DEFAULT_PLAN, MSL, AGL, Mission, Terrain, Waypoint, deviation   # noqa: E402

# Column names seen in exported logs, lower cased, punctuation stripped. First match wins.
LON_KEYS = ("longitude", "lon", "lng", "long", "gpslongitude", "longitudedeg")
LAT_KEYS = ("latitude", "lat", "gpslatitude", "latitudedeg")
ALT_KEYS = ("altitude", "alt", "altm", "altitudem", "gpsaltitude", "absolutealtitude",
            "altitudeabove sealevel", "amsl", "msl", "ellipsoidalheight", "heightmsl")
AGL_KEYS = ("relativealtitude", "heightaboveground", "agl", "altituderelative", "heightm")
TIME_KEYS = ("time", "t", "timestamp", "timems", "times", "datetime", "utc", "gpstime",
             "timesincestart")


def key(name):
    return "".join(c for c in str(name).lower() if c.isalnum())


class Track:
    """A flight as a list of samples, however it was recorded.

    Every sample is (seconds from the start, longitude, latitude, metres above sea level). The
    elevation can be None when a log has no height in it, in which case a mission made from it has
    to be given one."""

    def __init__(self, name, samples, source, datum="as recorded", notes=None, agl=False):
        self.name = name
        self.samples = samples
        self.source = source
        self.datum = datum
        self.notes = notes or []
        self.heights_are_agl = agl

    def __len__(self):
        return len(self.samples)

    @property
    def duration_s(self):
        return (self.samples[-1][0] - self.samples[0][0]) if len(self.samples) > 1 else 0.0


# ---------------------------------------------------------------------------------------------
# Reading
# ---------------------------------------------------------------------------------------------

def read_flight_folder(path):
    """A flight recorded here: track.jsonl, turned back into longitude and latitude.

    The conversion comes out of the manifest's own frames block rather than out of the landscape
    plan, which is the point of writing that block down: a recording stays readable on its own."""
    folder = path if os.path.isdir(path) else os.path.dirname(os.path.abspath(path))
    manifest = rec.read_manifest(folder)
    frames = manifest.get("frames") or {}
    if "projected_origin_m" not in frames:
        raise SystemExit("%s has no usable frame in its manifest, so its track cannot be placed "
                         "in the world" % folder)
    track_file = os.path.join(folder, (manifest.get("track") or {}).get("file") or "track.jsonl")
    samples = []
    with io.open(track_file, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
                lon, lat = rec.lonlat_from_frames(frames, row["north"], row["east"])
                samples.append((float(row.get("t", len(samples))), lon, lat,
                                rec.elevation_from_frames(frames, row["down"])))
            except (ValueError, KeyError):
                continue
    name = ((manifest.get("mission") or {}).get("name") or os.path.basename(folder))
    return Track(name, samples, track_file,
                 datum="the landscape's own elevations, so NAVD88 as 3DEP supplies it",
                 notes=["flown in the simulator on %s" % manifest.get("created", "an unknown date")])


def _pick(header, wanted):
    keys = {key(h): h for h in header}
    for w in wanted:
        if w in keys:
            return keys[w]
    return None


def _seconds(value, first):
    """A time column into seconds from the start, whatever it was counting in."""
    try:
        v = float(value)
    except (TypeError, ValueError):
        return None
    if first is None:
        return v
    d = v - first
    # Milliseconds and microseconds are common in exported logs; so are unix timestamps.
    if abs(d) > 1e9:
        return d / 1e9
    if abs(d) > 1e6:
        return d / 1e6
    if abs(d) > 1e4:
        return d / 1e3
    return d


def read_table(path, rows, header, source):
    """Rows of a CSV or of JSON lines, once the column names are known."""
    lon_k, lat_k = _pick(header, LON_KEYS), _pick(header, LAT_KEYS)
    if not lon_k or not lat_k:
        raise SystemExit("%s has no longitude and latitude columns I recognise. Its columns are: "
                         "%s" % (source, ", ".join(map(str, header))))
    alt_k, agl_k = _pick(header, ALT_KEYS), _pick(header, AGL_KEYS)
    time_k = _pick(header, TIME_KEYS)
    notes = ["longitude from '%s', latitude from '%s'" % (lon_k, lat_k)]
    using_agl = False
    if alt_k:
        notes.append("height from '%s', read as metres above sea level" % alt_k)
    elif agl_k:
        alt_k, using_agl = agl_k, True
        notes.append("height from '%s', read as metres above the ground" % agl_k)
    else:
        notes.append("no height column was found, so one has to be given with --height")
    if time_k:
        notes.append("time from '%s'" % time_k)

    samples, first_t = [], None
    for i, row in enumerate(rows):
        try:
            lon, lat = float(row[lon_k]), float(row[lat_k])
        except (KeyError, TypeError, ValueError):
            continue
        if not (-180.0 <= lon <= 180.0 and -90.0 <= lat <= 90.0) or (lon == 0.0 and lat == 0.0):
            continue                      # a receiver with no fix writes zeroes
        elev = None
        if alt_k:
            try:
                elev = float(row[alt_k])
            except (KeyError, TypeError, ValueError):
                elev = None
        t = float(len(samples))
        if time_k:
            raw = _seconds(row.get(time_k), None)
            if raw is not None:
                first_t = raw if first_t is None else first_t
                t = _seconds(row.get(time_k), first_t) or 0.0
        samples.append((t, lon, lat, elev))
    return Track(os.path.splitext(os.path.basename(source))[0], samples, source,
                 datum="whatever the log used, unchanged", notes=notes, agl=using_agl)


def read_csv(path):
    with io.open(path, encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        header = reader.fieldnames or []
    return read_table(path, rows, header, path)


def read_jsonl(path):
    rows = []
    with io.open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except ValueError:
                continue
            if isinstance(row, dict):
                # A nested position, as some loggers write: {"position": {"lat": ...}}
                flat = dict(row)
                for holder in ("position", "pos", "gps", "location", "msg"):
                    if isinstance(row.get(holder), dict):
                        flat.update(row[holder])
                rows.append(flat)
    if not rows:
        raise SystemExit("%s has no JSON object lines in it" % path)
    header = sorted({k for r in rows for k in r})
    if "north" in header and "east" in header and "down" in header:
        return read_flight_folder(path)
    return read_table(path, rows, header, path)


def read_gpx(path):
    tree = ET.parse(path)
    ns = {"g": "http://www.topografix.com/GPX/1/1"}
    points = tree.getroot().findall(".//g:trkpt", ns) or tree.getroot().findall(".//trkpt")
    samples = []
    for i, p in enumerate(points):
        try:
            lon, lat = float(p.get("lon")), float(p.get("lat"))
        except (TypeError, ValueError):
            continue
        ele = p.find("g:ele", ns)
        if ele is None:
            ele = p.find("ele")
        elev = None
        if ele is not None and ele.text:
            try:
                elev = float(ele.text)
            except ValueError:
                elev = None
        samples.append((float(i), lon, lat, elev))
    if not samples:
        raise SystemExit("%s has no track points in it" % path)
    return Track(os.path.splitext(os.path.basename(path))[0], samples, path,
                 datum="whatever the GPX writer used, which is usually the WGS84 ellipsoid",
                 notes=["%d track points" % len(samples),
                        "GPX has no speeds here, so --speed is used"])


def read_any(path):
    """Whichever of the four shapes this file is."""
    if os.path.isdir(path) or os.path.basename(path) == "manifest.json":
        return read_flight_folder(path)
    ext = os.path.splitext(path)[1].lower()
    if ext == ".gpx":
        return read_gpx(path)
    if ext in (".jsonl", ".ndjson"):
        return read_jsonl(path)
    if ext in (".csv", ".txt", ".tsv"):
        return read_csv(path)
    if ext == ".json":
        raise SystemExit("%s looks like a single JSON document. A flight folder, a .jsonl track, "
                         "a CSV or a GPX file is what this reads." % path)
    return read_csv(path)


# ---------------------------------------------------------------------------------------------
# Thinning a track down to a route
# ---------------------------------------------------------------------------------------------

def simplify(points, tolerance_m):
    """Douglas-Peucker: keep the points that describe the shape, drop the ones that do not.

    A log at 10 Hz is tens of thousands of positions and no mission wants them. What matters is the
    corners: anything within the tolerance of the line between its neighbours is not telling us
    anything a straight leg would not."""
    if len(points) < 3:
        return list(range(len(points)))
    keep = [False] * len(points)
    keep[0] = keep[-1] = True
    stack = [(0, len(points) - 1)]
    while stack:
        a, b = stack.pop()
        if b - a < 2:
            continue
        worst, worst_i = -1.0, -1
        for i in range(a + 1, b):
            d, _ = _distance_to_segment(points[i], points[a], points[b])
            if d > worst:
                worst, worst_i = d, i
        if worst > tolerance_m and worst_i > 0:
            keep[worst_i] = True
            stack.append((a, worst_i))
            stack.append((worst_i, b))
    return [i for i, k in enumerate(keep) if k]


def _distance_to_segment(p, a, b):
    """Metres from p to the segment ab, and how far along it the nearest point sits."""
    ax, ay, az = a
    bx, by, bz = b
    px, py, pz = p
    dx, dy, dz = bx - ax, by - ay, bz - az
    length2 = dx * dx + dy * dy + dz * dz
    if length2 <= 0.0:
        return math.dist(p, a), 0.0
    t = ((px - ax) * dx + (py - ay) * dy + (pz - az) * dz) / length2
    t = max(0.0, min(1.0, t))
    near = (ax + t * dx, ay + t * dy, az + t * dz)
    return math.dist(p, near), t


def clearance(track, terrain, offset=0.0):
    """How high above the landscape the log's heights put the aircraft, as a median and a range.

    This is the only honest check on a height datum. Nothing here knows which datum a log used, but
    a flight whose heights come out ninety metres above the ground when it was flown at sixty is
    telling us the numbers are measured from somewhere else, and by how much."""
    above = []
    for _t, lon, lat, elev in track.samples:
        if elev is None:
            continue
        ground = terrain.ground_elevation(lon, lat)
        if ground is not None:
            above.append(elev + offset - ground)
    if not above:
        return None
    above.sort()
    return {"median": above[len(above) // 2], "lowest": above[0], "highest": above[-1],
            "samples": len(above)}


def to_mission(track, terrain, args):
    """A real flight as a mission this project can fly."""
    if not len(track):
        raise SystemExit("%s has no usable positions in it" % track.source)

    offset = args.altitude_offset
    heights = []
    for _t, lon, lat, elev in track.samples:
        if elev is None:
            heights.append(None)
        else:
            heights.append(elev + offset)

    # Everything is measured in the frame the simulator flies in, so the tolerance is in the same
    # metres as the deviation the planner reports while flying.
    ned = []
    for (t, lon, lat, _e), h in zip(track.samples, heights):
        elev = h if h is not None else (terrain.ground_elevation(lon, lat) or 0.0) + args.height
        ned.append(terrain.ned(lon, lat, elev))

    tolerance = args.tolerance
    kept = simplify(ned, tolerance)
    while len(kept) > args.max_waypoints and tolerance < 10000.0:
        tolerance *= 1.6
        kept = simplify(ned, tolerance)
    if tolerance != args.tolerance:
        print("the %.1f m tolerance left %d waypoints, so it was raised to %.1f m to get %d"
              % (args.tolerance, len(simplify(ned, args.tolerance)), tolerance, len(kept)))

    mission = Mission(name=args.name or track.name, plan=terrain.path)
    mission.yaw_mode = args.yaw
    mission.land_at_end = not args.no_land
    off_landscape = 0
    for n, i in enumerate(kept, 1):
        t, lon, lat, _e = track.samples[i]
        ground = terrain.ground_elevation(lon, lat)
        if ground is None:
            off_landscape += 1
        if heights[i] is None:
            height, reference = args.height, AGL
        elif args.agl:
            if ground is None:
                height, reference = args.height, AGL
            else:
                height, reference = round(heights[i] - ground, 1), AGL
        else:
            height, reference = round(heights[i], 1), MSL

        speed = args.speed
        if n > 1 and track.duration_s > 0:
            previous = kept[n - 2]
            dt = track.samples[i][0] - track.samples[previous][0]
            if dt > 0:
                flown = math.dist(ned[i], ned[previous])
                speed = round(max(args.min_speed, min(args.max_speed, flown / dt)), 1)
        mission.waypoints.append(Waypoint("%s%03d" % (args.prefix, n), lon, lat, height,
                                          reference, speed))
    return mission, off_landscape, tolerance


# ---------------------------------------------------------------------------------------------
# Measuring one flight against another
# ---------------------------------------------------------------------------------------------

def compare(reference, flown, terrain):
    """How far the second flight was from the first, sample by sample.

    The same measure the planner shows while flying: to the nearest point on the nearest leg of the
    reference track. Horizontal distance is reported beside the full three dimensional one because
    a height datum that is out by a constant shows up in one and not the other, which is usually the
    first thing worth knowing."""
    path, flat_path = [], []
    for _t, lon, lat, elev in reference.samples:
        e = elev if elev is not None else terrain.ground_elevation(lon, lat) or 0.0
        n, ea, d = terrain.ned(lon, lat, e)
        path.append((n, ea, d))
        flat_path.append((n, ea, 0.0))
    if len(path) < 2:
        raise SystemExit("the reference flight has fewer than two positions")

    rows = []
    for t, lon, lat, elev in flown.samples:
        e = elev if elev is not None else terrain.ground_elevation(lon, lat) or 0.0
        n, ea, d = terrain.ned(lon, lat, e)
        full, leg = deviation(path, (n, ea, d))
        flat, _ = deviation(flat_path, (n, ea, 0.0))
        rows.append({"t": round(t, 3), "lon": lon, "lat": lat, "elevation_m": round(e, 2),
                     "deviation_m": None if full is None else round(full, 3),
                     "horizontal_m": None if flat is None else round(flat, 3),
                     "leg": leg})
    return rows


def stats(values):
    values = sorted(v for v in values if v is not None)
    if not values:
        return None
    def at(q):
        return values[min(len(values) - 1, int(q * (len(values) - 1)))]
    return {"samples": len(values), "mean": sum(values) / len(values), "median": at(0.5),
            "p95": at(0.95), "worst": values[-1]}


def print_stats(label, s):
    if not s:
        print("  %-12s nothing to measure" % label)
        return
    print("  %-12s mean %.2f m, median %.2f m, 95th %.2f m, worst %.2f m, over %d samples"
          % (label, s["mean"], s["median"], s["p95"], s["worst"], s["samples"]))


# ---------------------------------------------------------------------------------------------
# Running
# ---------------------------------------------------------------------------------------------

def into_landscape_datum(track):
    """A log of GPS heights, converted to this landscape's NAVD88 with the geoid at each point.

    Only for logs. A flight folder recorded here is already in the landscape's datum, and
    converting it again would move it 34 m the wrong way, so it is left alone."""
    if track.datum.startswith("the landscape's own"):
        print("          %s is already in the landscape's datum; --geoid leaves it alone"
              % track.name)
        return track
    import geoid as geoid_module
    try:
        model = geoid_module.Geoid.default()
    except geoid_module.GeoidUnavailable as e:
        raise SystemExit("--geoid needs the geoid model: %s" % e)
    converted, refused = [], 0
    for t, lon, lat, elev in track.samples:
        if elev is None:
            converted.append((t, lon, lat, None))
            continue
        try:
            converted.append((t, lon, lat, model.to_landscape(lon, lat, elev)))
        except geoid_module.GeoidUnavailable:
            refused += 1
            converted.append((t, lon, lat, None))
    track.samples = converted
    track.datum = "WGS84 ellipsoidal in the log, converted with %s" % model.model
    if refused:
        track.notes.append("%d position(s) outside the geoid grid lost their height" % refused)
    return track


def add_common(ap):
    ap.add_argument("--plan", default=DEFAULT_PLAN,
                    help="the landscape plan the heights and the frame come from")
    ap.add_argument("--geoid", action="store_true",
                    help="the log's heights are GPS heights above the WGS84 ellipsoid: convert "
                         "each with the GEOID18 model at its own position (the usual case for a "
                         "GPS or drone log; see geoid.py)")
    ap.add_argument("--altitude-offset", type=float, default=0.0, metavar="METRES",
                    help="added to every height in the log, for a datum that does not match the "
                         "landscape's; see the note at the top of this file before guessing")


def main():
    ap = argparse.ArgumentParser(description="A real flight into a mission, and one flight "
                                             "measured against another.")
    sub = ap.add_subparsers(dest="action", required=True)

    m = sub.add_parser("mission", help="turn a flown track into a mission")
    m.add_argument("log", help="a flight folder, a CSV, a .jsonl track or a GPX file")
    m.add_argument("-o", "--out", help="where to write the mission (default: beside missions/)")
    m.add_argument("--name", help="the mission's name (default: the log's)")
    m.add_argument("--prefix", default="P", help="waypoint name prefix (default: P)")
    m.add_argument("--tolerance", type=float, default=5.0, metavar="METRES",
                   help="how far the route may stray from the log when thinning it (default: 5)")
    m.add_argument("--max-waypoints", type=int, default=60,
                   help="raise the tolerance until the route fits in this many (default: 60)")
    m.add_argument("--agl", action="store_true",
                   help="store heights above the ground rather than above sea level, which keeps "
                        "the route flyable if the landscape is rebuilt")
    m.add_argument("--height", type=float, default=40.0, metavar="METRES",
                   help="height above the ground for samples the log gives no height for")
    m.add_argument("--speed", type=float, default=10.0, help="speed when the log has no times")
    m.add_argument("--min-speed", type=float, default=1.0)
    m.add_argument("--max-speed", type=float, default=25.0)
    m.add_argument("--yaw", default="forward", choices=["forward", "waypoint", "free"])
    m.add_argument("--no-land", action="store_true", help="do not land at the end")
    add_common(m)

    c = sub.add_parser("compare", help="measure one flight against another")
    c.add_argument("reference", help="the flight to measure against: a folder, CSV, jsonl or GPX")
    c.add_argument("flown", help="the flight being measured")
    c.add_argument("--csv", help="write every sample's deviation to this file")
    add_common(c)

    args = ap.parse_args()
    terrain = Terrain(args.plan)

    if args.action == "mission":
        track = read_any(args.log)
        if args.geoid:
            track = into_landscape_datum(track)
        print("read      %d positions from %s" % (len(track), track.source))
        for note in track.notes:
            print("          %s" % note)
        print("heights   %s%s" % (track.datum,
                                  "" if not args.altitude_offset
                                  else ", with %+.1f m applied" % args.altitude_offset))
        high = clearance(track, terrain, args.altitude_offset)
        if high:
            print("clearance %.1f m above the ground as a median, %.1f m to %.1f m over %d of the "
                  "%d positions" % (high["median"], high["lowest"], high["highest"],
                                    high["samples"], len(track)))
            if not (0.0 <= high["median"] <= 120.0):
                print("warning:  that is not a plausible height for a flight. A receiver usually "
                      "reports height above the WGS84 ellipsoid while this landscape measures "
                      "from the NAVD88 geoid, which sits about 34 m below it here, so an "
                      "ellipsoidal log reads about 34 m low.")
                print("          if the aircraft really flew at H metres above the ground, the "
                      "offset to pass is H %+.1f" % (args.altitude_offset - high["median"]))
                if not args.geoid:
                    print("          if the log is GPS heights, --geoid converts each one with "
                          "the real geoid model instead of a guessed offset")
        mission, off, tolerance = to_mission(track, terrain, args)
        out = args.out or os.path.join(HERE, "missions", "%s.json" % mission.name)
        os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
        mission.save(out)
        print("\n%d waypoints at a %.1f m tolerance, %.2f km, roughly %.0f s"
              % (len(mission.waypoints), tolerance, (mission.distance_m(terrain) or 0) / 1000.0,
                 mission.duration_s(terrain) or 0))
        if off:
            print("warning:  %d of them are outside this landscape, so the mission will not fly "
                  "as it stands" % off)
        for problem in mission.check(terrain):
            print("warning:  %s" % problem)
        print("written   %s" % out)
        try:
            shown = os.path.relpath(out)
        except ValueError:            # another drive on Windows has no relative path
            shown = out
        print("\nFly it with:  py -3.10 fly_mission.py %s --all" % shown)
        return

    reference = read_any(args.reference)
    flown = read_any(args.flown)
    if args.geoid:
        reference = into_landscape_datum(reference)
        flown = into_landscape_datum(flown)
    if args.altitude_offset:
        flown.samples = [(t, lon, lat, None if e is None else e + args.altitude_offset)
                         for t, lon, lat, e in flown.samples]
    print("reference %s: %d positions over %.0f s (%s)"
          % (reference.name, len(reference), reference.duration_s, reference.datum))
    print("flown     %s: %d positions over %.0f s (%s)"
          % (flown.name, len(flown), flown.duration_s, flown.datum))
    if args.altitude_offset:
        print("          with %+.1f m applied to the second flight's heights"
              % args.altitude_offset)
    rows = compare(reference, flown, terrain)
    print("\nhow far the second flight was from the first")
    print_stats("in 3D", stats([r["deviation_m"] for r in rows]))
    print_stats("horizontal", stats([r["horizontal_m"] for r in rows]))
    heights = [r["elevation_m"] for r in rows]
    if heights:
        print("  %-12s %.1f m to %.1f m above sea level" % ("flown at", min(heights),
                                                            max(heights)))
    if args.csv:
        with io.open(args.csv, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)
        print("\nevery sample written to %s" % args.csv)


if __name__ == "__main__":
    main()
