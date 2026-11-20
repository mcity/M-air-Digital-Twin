"""geofences.py - airspace a mission may not use, and the check every mission has to pass.

    py -3.10 geofences.py                         list the geofences that are loaded
    py -3.10 geofences.py --check missions/x.json would this mission be accepted, and why not
    py -3.10 geofences.py --import zones.json     convert an ED-269 file to the GeoJSON used here

WHAT IT CHECKS. Before an operation may fly, its declared volumes (airspace.py) are compared with
two things, the way an F3548 UTM service does it:

  GEOFENCES. Polygons with an altitude band and, optionally, a time window, each marked no-fly,
  restricted or advisory. A volume that overlaps a no-fly or restricted fence in plan view AND in
  height AND in time rejects the operation; an advisory one is reported and does not.

  OTHER SCHEDULED MISSIONS. Two operations whose volumes overlap in space and in time cannot both
  be accepted. Only missions given a planned start take part: an operation in F3548 is a declared
  intent with times, and a mission file with no start is a plan, not a booking. Without that rule
  the two saved missions that fly the same route as alternatives would reject each other for ever.

AS TRUE SHAPES, IN METRES. Volumes and fences are intersected as polygons in the landscape's
projected frame. Flight Blender's default engine compares bounding boxes, and the bounding box of a
diagonal route is mostly empty sky, so it rejects operations that touch nothing.

WHERE FENCES COME FROM. GeoJSON files in Tools/geofences, and wherever MAIRCORRIDOR_GEOFENCES or
--geofences points. ED-269, the EUROCAE format for UAS geographical zones that Flight Blender also
reads, converts with --import. The example shipped here is ILLUSTRATIVE and is not airspace data:
real United States airspace for drones comes from the FAA's UAS Facility Maps and LAANC.

A fence property, all optional except the geometry:

    name        what to call it
    severity    no-fly (default), restricted, or advisory
    lower_m     bottom of the band, metres (default 0)
    upper_m     top of the band, metres (default unlimited)
    reference   agl (default), msl, or w84 (the WGS84 ellipsoid, which needs geoid.py)
    start, end  ISO times it applies between; absent means always
"""
import argparse
import glob
import io
import json
import math
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from shapely.geometry import Point, Polygon, shape as shapely_shape
except ImportError:
    raise SystemExit("geofences needs shapely: py -3.10 -m pip install -r requirements.txt")

from toolpaths import HERE                                                          # noqa: E402
FENCE_DIR = os.path.join(HERE, "geofences")
MISSION_DIR = os.path.join(HERE, "missions")
SEVERITIES = ("no-fly", "restricted", "advisory")
REFERENCES = ("agl", "msl", "w84")
UNLIMITED_M = 100000.0


def parse_time(value):
    """An ISO time to epoch seconds, or None. Accepts a trailing Z."""
    if not value:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip().replace("Z", "+00:00")
    try:
        from datetime import datetime
        moment = datetime.fromisoformat(text)
        if moment.tzinfo is None:
            return time.mktime(moment.timetuple())
        return moment.timestamp()
    except ValueError:
        return None


class Geofence:
    """One fence: a projected polygon, a band, a severity and maybe a time window."""

    def __init__(self, name, shape, lower=0.0, upper=UNLIMITED_M, reference="agl",
                 severity="no-fly", start=None, end=None, source=None, note=None, ring=None):
        self.name = name or "unnamed fence"
        self.shape = shape                   # projected metres
        self.ring = ring or []               # longitude and latitude, for drawing
        self.lower = float(lower)
        self.upper = float(upper)
        self.reference = reference if reference in REFERENCES else "agl"
        self.severity = severity if severity in SEVERITIES else "no-fly"
        self.start = parse_time(start)
        self.end = parse_time(end)
        self.source = source
        self.note = note

    def active_between(self, t0, t1):
        """Whether the fence applies at any time in [t0, t1] (epoch seconds)."""
        if self.start is not None and t1 is not None and t1 < self.start:
            return False
        if self.end is not None and t0 is not None and t0 > self.end:
            return False
        return True

    def band_over(self, region, terrain, geoid=None):
        """The fence's band in the landscape's datum, over a region, or None if unknowable.

        AGL is measured from the ground under the region, sampled at its corners and centre, and
        widened to the lowest ground for the bottom and the highest for the top: the band the
        fence actually occupies over uneven ground is never narrower than that, so the test errs
        towards finding a conflict. W84 needs a geoid model to bring it into this datum; without
        one the band cannot be placed honestly and None says so."""
        if self.reference == "msl":
            return self.lower, self.upper
        samples = list(region.exterior.coords)[:-1] + [tuple(region.centroid.coords)[0]]
        grounds, lonlats = [], []
        for easting, northing in samples:
            lon, lat = terrain.to_lonlat(easting, northing)
            lonlats.append((lon, lat))
            g = terrain.ground_elevation(lon, lat)
            if g is not None:
                grounds.append(g)
        if self.reference == "agl":
            if not grounds:
                return None
            return min(grounds) + self.lower, max(grounds) + self.upper
        if geoid is None:
            return None
        lon, lat = lonlats[-1]
        return (geoid.to_landscape(lon, lat, self.lower),
                geoid.to_landscape(lon, lat, self.upper) if self.upper < UNLIMITED_M
                else UNLIMITED_M)

    def describe(self):
        band = "%.0f to %s m %s" % (self.lower,
                                    "unlimited" if self.upper >= UNLIMITED_M else "%.0f" % self.upper,
                                    self.reference.upper())
        return "%s (%s, %s)" % (self.name, self.severity, band)


# ---------------------------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------------------------

def fence_dirs(extra=None):
    dirs = [FENCE_DIR]
    from_env = os.environ.get("MAIRCORRIDOR_GEOFENCES")
    if from_env:
        dirs += from_env.split(os.pathsep)
    if extra:
        dirs += [extra] if isinstance(extra, str) else list(extra)
    return [d for d in dirs if d]


def load_geofences(terrain, extra=None, quiet=True):
    """Every fence in every GeoJSON file that can be found, projected onto the landscape."""
    fences = []
    for d in fence_dirs(extra):
        paths = [d] if os.path.isfile(d) else sorted(glob.glob(os.path.join(d, "*.geojson"))
                                                     + glob.glob(os.path.join(d, "*.json")))
        for path in paths:
            try:
                fences += read_geojson(path, terrain)
            except Exception as e:
                if not quiet:
                    print("could not read %s: %s" % (path, e))
    return fences


def read_geojson(path, terrain):
    with io.open(path, encoding="utf-8") as f:
        data = json.load(f)
    if data.get("type") != "FeatureCollection" and "features" in data and \
            isinstance(data["features"], list) and data["features"] and \
            "geometry" in data["features"][0] and isinstance(data["features"][0]["geometry"], list):
        data = ed269_to_geojson(data)            # an ED-269 file dropped straight in
    out = []
    for feature in data.get("features", []):
        geometry = feature.get("geometry") or {}
        props = feature.get("properties") or {}
        try:
            geo = shapely_shape(geometry)
        except Exception:
            continue
        polygons = [geo] if geo.geom_type == "Polygon" else \
            list(geo.geoms) if geo.geom_type == "MultiPolygon" else []
        for poly in polygons:
            ring = [(float(x), float(y)) for x, y in poly.exterior.coords]
            projected = Polygon([terrain.to_projected(lon, lat) for lon, lat in ring])
            if not projected.is_valid:
                projected = projected.buffer(0)
            out.append(Geofence(props.get("name"), projected, props.get("lower_m", 0.0),
                                props.get("upper_m", UNLIMITED_M), props.get("reference", "agl"),
                                props.get("severity", "no-fly"), props.get("start"),
                                props.get("end"), os.path.basename(path), props.get("note"),
                                ring))
    return out


def ed269_to_geojson(data):
    """EUROCAE ED-269 UAS geographical zones as the GeoJSON this module reads.

    Covers what zone files actually use: polygon and circle projections, metres and feet, AGL,
    AMSL and WGS84 references, and the PROHIBITED, REQ_AUTHORISATION, CONDITIONAL and
    NO_RESTRICTION restrictions. AMSL is taken as this landscape's datum: both are orthometric,
    and over a few kilometres the difference between mean sea level and NAVD88 is far below any
    margin a fence is drawn with. A circle becomes a 64 sided polygon."""
    restriction = {"PROHIBITED": "no-fly", "REQ_AUTHORISATION": "restricted",
                   "CONDITIONAL": "restricted", "NO_RESTRICTION": "advisory"}
    reference = {"AGL": "agl", "AMSL": "msl", "WGS84": "w84", "SFC": "agl"}
    features = []
    for zone in data.get("features", []):
        severity = restriction.get(str(zone.get("restriction", "")).upper(), "restricted")
        when = (zone.get("applicability") or [{}])[0]
        start = None if str(when.get("permanent", "YES")).upper() == "YES" \
            else when.get("startDateTime")
        end = None if str(when.get("permanent", "YES")).upper() == "YES" \
            else when.get("endDateTime")
        for part in zone.get("geometry", []):
            scale = 0.3048 if str(part.get("uomDimensions", "M")).upper() == "FT" else 1.0
            projection = part.get("horizontalProjection") or {}
            if projection.get("type") == "Circle":
                lon0, lat0 = projection["center"]
                radius = float(projection["radius"]) * scale
                coords = []
                for k in range(65):
                    a = 2.0 * math.pi * k / 64.0
                    coords.append([lon0 + (radius * math.sin(a)) /
                                   (111320.0 * math.cos(math.radians(lat0))),
                                   lat0 + (radius * math.cos(a)) / 111320.0])
                geometry = {"type": "Polygon", "coordinates": [coords]}
            else:
                geometry = {"type": "Polygon", "coordinates": projection.get("coordinates")}
            lower = part.get("lowerLimit")
            upper = part.get("upperLimit")
            features.append({"type": "Feature", "geometry": geometry, "properties": {
                "name": zone.get("name") or zone.get("identifier"),
                "severity": severity,
                "lower_m": 0.0 if lower is None else float(lower) * scale,
                "upper_m": UNLIMITED_M if upper is None else float(upper) * scale,
                "reference": reference.get(str(part.get("lowerVerticalReference", "AGL")).upper(),
                                           "agl"),
                "start": start, "end": end,
                "note": "imported from ED-269 zone %s" % zone.get("identifier", "")}})
    return {"type": "FeatureCollection", "features": features}


# ---------------------------------------------------------------------------------------------
# The strategic check
# ---------------------------------------------------------------------------------------------

def bands_overlap(a_lower, a_upper, b_lower, b_upper):
    return a_lower <= b_upper and b_lower <= a_upper


class Deconfliction:
    """What stands in an operation's way. Rejections stop it; advisories are only reported."""

    def __init__(self):
        self.rejections = []
        self.advisories = []
        self.unknown = []

    @property
    def accepted(self):
        return not self.rejections


def check(intent, mission, terrain, start_epoch=None, fences=None, other_missions=None,
          geoid=None):
    """Compare an operation's volumes with the fences and with other scheduled operations."""
    result = Deconfliction()
    start = start_epoch
    if start is None:
        start = parse_time((intent.settings.as_dict() or {}).get("planned_start"))

    def window(volume):
        if start is None:
            return None, None
        return start + volume.t0, start + volume.t1

    # ---- geofences -------------------------------------------------------------------------
    for fence in (fences or []):
        hits = []
        for volume in intent.volumes:
            t0, t1 = window(volume)
            if not fence.active_between(t0, t1):
                continue
            if not volume.shape.intersects(fence.shape):
                continue
            region = volume.shape.intersection(fence.shape)
            if region.is_empty or region.geom_type not in ("Polygon", "MultiPolygon"):
                region = volume.shape
            if region.geom_type == "MultiPolygon":
                region = max(region.geoms, key=lambda g: g.area)
            band = fence.band_over(region, terrain, geoid)
            if band is None:
                result.unknown.append("%s overlaps %s in plan view, but its %s band cannot be "
                                      "placed without a geoid model (geoid.py)"
                                      % (volume.name, fence.describe(), fence.reference.upper()))
                continue
            if bands_overlap(volume.lower, volume.upper, band[0], band[1]):
                hits.append(volume.name)
        if hits:
            text = "%s enters %s" % (", ".join(hits[:3]) + (" and %d more" % (len(hits) - 3)
                                                            if len(hits) > 3 else ""),
                                      fence.describe())
            (result.advisories if fence.severity == "advisory" else result.rejections).append(text)

    # ---- other scheduled operations --------------------------------------------------------
    if start is not None:
        for other_name, other_intent, other_start in (other_missions or []):
            if other_start is None:
                continue
            clash = None
            for a in intent.volumes:
                for b in other_intent.volumes:
                    if (start + a.t0) > (other_start + b.t1) or \
                            (other_start + b.t0) > (start + a.t1):
                        continue
                    if not bands_overlap(a.lower, a.upper, b.lower, b.upper):
                        continue
                    if a.shape.intersects(b.shape):
                        clash = (a.name, b.name)
                        break
                if clash:
                    break
            if clash:
                result.rejections.append("%s overlaps %s of scheduled mission %s in space and time"
                                         % (clash[0], clash[1], other_name))
    return result


def scheduled_missions(terrain, exclude_path=None, scene_dir=None):
    """Every other mission in Tools/missions with a planned start, as (name, intent, start)."""
    import airspace
    from flightplan import Mission
    out = []
    scene_dir = scene_dir or os.path.join(os.path.dirname(HERE), "AirSim", "sim_config")
    for path in sorted(glob.glob(os.path.join(MISSION_DIR, "*.json"))):
        if exclude_path and os.path.abspath(path) == os.path.abspath(exclude_path):
            continue
        try:
            other = Mission.load(path)
        except Exception:
            continue
        start = parse_time((other.intent or {}).get("planned_start"))
        if start is None:
            continue
        try:
            spawn = airspace.start_of(other, terrain, scene_dir)
            out.append((other.name, airspace.OperationalIntent.from_mission(
                other, terrain, spawn_ned=spawn), start))
        except Exception:
            continue
    return out


def conflicts_for(intent, mission, terrain, args=None):
    """What fly_mission.py asks: the rejections, as text, with the rest printed alongside."""
    geoid = None
    try:
        import geoid as geoid_module
        geoid = geoid_module.Geoid.default()
    except Exception:
        geoid = None
    fences = load_geofences(terrain, getattr(args, "geofences", None))
    others = scheduled_missions(terrain, exclude_path=getattr(args, "mission", None))
    result = check(intent, mission, terrain, fences=fences, other_missions=others, geoid=geoid)
    for line in result.advisories:
        print("advisory  %s" % line)
    for line in result.unknown:
        print("unchecked %s" % line)
    return result.rejections


# ---------------------------------------------------------------------------------------------
# Command line
# ---------------------------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(description="Geofences, and the check a mission has to pass.")
    ap.add_argument("--check", metavar="MISSION", help="would this mission be accepted")
    ap.add_argument("--geofences", help="another folder or file of GeoJSON fences")
    ap.add_argument("--import", dest="import_path", metavar="ED269",
                    help="convert an ED-269 zone file to GeoJSON in Tools/geofences")
    ap.add_argument("--plan", help="the landscape plan (default: the usual one)")
    args = ap.parse_args()

    if args.import_path:
        with io.open(args.import_path, encoding="utf-8") as f:
            converted = ed269_to_geojson(json.load(f))
        os.makedirs(FENCE_DIR, exist_ok=True)
        out = os.path.join(FENCE_DIR, os.path.splitext(os.path.basename(args.import_path))[0]
                           + ".geojson")
        with io.open(out, "w", encoding="utf-8", newline="\n") as f:
            json.dump(converted, f, indent=1)
        print("%d zone(s) written to %s" % (len(converted["features"]), out))
        return

    from flightplan import DEFAULT_PLAN, Mission, Terrain
    terrain = Terrain(args.plan or DEFAULT_PLAN)
    fences = load_geofences(terrain, args.geofences, quiet=False)
    if not args.check:
        print("%d geofence(s)" % len(fences))
        for fence in fences:
            print("  %-48s from %s" % (fence.describe(), fence.source))
        return

    import airspace
    mission = Mission.load(args.check)
    spawn = airspace.start_of(mission, terrain, os.path.join(os.path.dirname(HERE), "AirSim", "sim_config"))
    intent = airspace.OperationalIntent.from_mission(mission, terrain, spawn_ned=spawn)
    args.mission = args.check
    rejections = conflicts_for(intent, mission, terrain, args)
    if rejections:
        print("REJECTED")
        for line in rejections:
            print("  %s" % line)
        sys.exit(1)
    print("ACCEPTED: nothing in the way of %s (%d volumes, %d fences, checked as true shapes)"
          % (mission.name, len(intent.volumes), len(fences)))


if __name__ == "__main__":
    main()
