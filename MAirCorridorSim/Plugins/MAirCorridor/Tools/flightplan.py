"""flightplan.py - waypoint missions: the model, the ground under them, and the frames between.

A mission is a named list of waypoints in longitude and latitude, each with a height that is either
above the ground beneath it or above sea level. This module turns that into what the simulator wants
and nothing else; the window (flightplan_ui.py) and the runner (fly_mission.py) share it so a route
means the same thing in both.

THREE FRAMES, AND WHY EACH EXISTS.

  * LONGITUDE AND LATITUDE is what a waypoint is stored in. It survives a landscape being rebuilt at
    a different size or origin, which Unreal coordinates would not, and it is what a map shows.
  * UNREAL CENTIMETRES is where the landscape and everything placed on it lives:
        X = (easting - landscape west) * 100       Y = (landscape north - northing) * 100
        Z = landscape actor Z + (elevation - landscape mid elevation) * 100
  * NED METRES is what the simulator flies in, and here it is tied to Unreal's axes rather than to
    true north, exactly as the scene config says:
        north = X / 100          east = Y / 100          down = -Z / 100

HEIGHT ABOVE GROUND NEEDS THE GROUND, so a mission names the landscape plan it was drawn against and
this reads elevation straight out of the heightmap, the same file Unreal imported. That is why an
"80 m" leg is 80 m over the hill as well as over the valley.
"""
import io
import json
import math
import os

from toolpaths import ASSETS, FROZEN, HERE

try:
    import numpy as np
    from rasterio.warp import transform as reproject_points
except ImportError as e:                 # named plainly: this is the one dependency that matters
    raise SystemExit("flightplan needs numpy and rasterio: py -3.10 -m pip install -r "
                     "requirements.txt (%s)" % e)

YAW_MODES = ("forward",     # nose along the direction of travel
             "waypoint",    # aimed at the waypoint being flown to, held while it waits there
             "free")        # left alone, which is what the controller does by default

# THE FASTEST THIS AIRFRAME ACTUALLY FLIES, measured rather than assumed. A mission asked for
# 200 m/s on one leg; the controller flew it at 21.0 m/s on average over five minutes. Anything
# timed from the asked-for speed is therefore wrong by a factor of ten, so every timing here (the
# flight time, the declared volumes' time windows, how a long move is split) uses the asked-for
# speed only up to this, and so is the speed sent to the controller: asked for 200 m/s it capped
# the speed but climbed hundreds of metres off its route, on every flight of that mission.
MAX_CONTROLLER_SPEED_MS = 21.0


def effective_speed(waypoint):
    """The speed a leg will really be flown at, for anything that has to estimate time."""
    return max(0.1, min(float(waypoint.speed), MAX_CONTROLLER_SPEED_MS))


MSL = "msl"            # metres above sea level
AGL = "agl"            # metres above the ground directly below
SIM = "sim"            # metres up in the simulator, Unreal Z / 100: flown at exactly that height
REFERENCES = (AGL, MSL, SIM)

# The Ouster lidar's mount when a mission does not give one: on the nose, level, looking forward.
# A placeholder until the real airframe's mount is measured; a mission's lidar_mount overrides it.
DEFAULT_LIDAR_MOUNT = {"x_cm": 20.0, "y_cm": 0.0, "z_cm": 0.0,
                       "roll_deg": 0.0, "pitch_deg": 0.0, "yaw_deg": 0.0}

# A mission start on the ground is put this far above the landscape, so the drone settles onto it.
START_CLEARANCE_M = 0.75

# Where the scene and robot configs live. Tools/drone_configs.py writes a robot_<name>.jsonc here
# for each drone built by the aircraft builder, which a flight can fly as (see Mission.robot_config).
SIM_CONFIG_DIR = os.path.join(os.path.dirname(HERE), "AirSim", "sim_config")
BUILT_DRONE_PREFIX = "robot_drone_"


def built_drones():
    """The robot configs of the built drones, by file name, for a flight to choose from."""
    try:
        names = os.listdir(SIM_CONFIG_DIR)
    except OSError:
        return []
    return sorted(n for n in names if n.startswith(BUILT_DRONE_PREFIX) and n.endswith(".jsonc"))


def robot_config_name(name):
    """A robot config's file name from itself or from the drone's name: drone_quad_industrial,
    robot_drone_quad_industrial and robot_drone_quad_industrial.jsonc are the same config."""
    if not name:
        return None
    stem = name[:-len(".jsonc")] if name.endswith(".jsonc") else name
    return (stem if stem.startswith("robot_") else "robot_" + stem) + ".jsonc"


def built_plan():
    """The landscape a built release (build_tools.py) carries in landscape/ beside the
    executables, or None. Only a built release looks: run as scripts, landscape/ is where
    build_landscape.py writes its own work."""
    folder = os.path.join(HERE, "landscape")
    if not FROZEN or not os.path.isdir(folder):
        return None
    plans = sorted(f for f in os.listdir(folder) if f.lower().endswith(".json"))
    return os.path.join(folder, plans[0]) if plans else None


DEFAULT_PLAN = (os.environ.get("MAIRCORRIDOR_PLAN") or built_plan()
                or os.path.join(ASSETS, "ue_rect_3m", "mcity_rect_3m.json"))

# WHERE THE LANDSCAPE ACTUALLY IS IN THE LEVEL, measured from the level rather than taken from the
# plan. The plan says where the landscape was PUT when it was imported; the level says where it IS
# now, and the two had drifted 236 m apart: the landscape and everything on it had been moved down
# to Z 0, while the plan still said Z 23599.85 cm. Every height these tools sent the simulator was
# 236 m too high, so the drone flew far above the ground it was meant to skim and the sensors that
# measure the ground found nothing in range. Unreal/measure_level.py writes this file.
LEVEL_FILE = os.environ.get("MAIRCORRIDOR_LEVEL",
                            os.path.join(HERE, "level.json"))


def level_placement(plan):
    """The measured landscape location in Unreal centimetres for this plan's landscape, or None
    when nothing has been measured for it, in which case the plan's own placement stands."""
    if not os.path.isfile(LEVEL_FILE):
        return None
    with io.open(LEVEL_FILE, encoding="utf-8") as f:
        level = json.load(f)
    wanted = level.get("plan_name")
    if wanted and plan.get("name") and wanted != plan.get("name"):
        return None
    loc = level.get("landscape_location_cm")
    return [float(v) for v in loc] if loc else None


# ---------------------------------------------------------------------------------------------
# The ground
# ---------------------------------------------------------------------------------------------

def resolve_plan(path=None):
    """A landscape plan that exists on THIS machine, starting from the one asked for.

    A mission stores the absolute path of the plan it was drawn against, which is right on the
    machine that drew it and wrong on every other. So a path that does not exist here falls back
    to MAIRCORRIDOR_PLAN, the machine's own setting, and says so once. The plan is the same
    landscape on both machines or the mission would not make sense at all, so the fallback is a
    change of where the file lives, not of what it describes."""
    if path and os.path.isfile(path):
        return path
    if DEFAULT_PLAN and os.path.isfile(DEFAULT_PLAN):
        if path and path != DEFAULT_PLAN and path not in _NOTED:
            _NOTED.add(path)
            print("note: the plan %s is not on this machine; using %s (%s)"
                  % (path, DEFAULT_PLAN, "MAIRCORRIDOR_PLAN" if os.environ.get("MAIRCORRIDOR_PLAN")
                     else "the release's own landscape" if DEFAULT_PLAN == built_plan()
                     else "the default"), flush=True)
        return DEFAULT_PLAN
    raise FileNotFoundError(
        "No landscape plan at %s. Build one with build_landscape.py, or set MAIRCORRIDOR_PLAN to "
        "the plan JSON on this machine. See 'On a new machine' in Tools/README.md."
        % (path or DEFAULT_PLAN))


_NOTED = set()


class Terrain:
    """Elevation and Unreal coordinates, read from a landscape plan and its heightmap."""

    def __init__(self, plan_path=None):
        self.path = resolve_plan(plan_path)
        with io.open(self.path, encoding="utf-8") as f:
            self.plan = json.load(f)
        self.epsg = int(str(self.plan["projection"]).split(":")[1])
        self.quad = float(self.plan["quad_metres"])
        self.segments = self.plan.get("segments") or [self.plan]
        self._maps = {}
        self.placement = level_placement(self.plan)
        self.placement_source = LEVEL_FILE if self.placement else self.path

    def location_cm(self, seg):
        """The landscape actor's location: as measured in the level when it has been, else as the
        plan placed it. Only the first segment's is overridden; a plan of several segments places
        each relative to the first, so the others move by the same amount."""
        planned = seg.get("actor_location_cm", self.plan.get("actor_location_cm", [0.0, 0.0, 0.0]))
        if not self.placement:
            return planned
        first = self.segments[0].get("actor_location_cm",
                                     self.plan.get("actor_location_cm", [0.0, 0.0, 0.0]))
        return [float(p) + (m - float(f)) for p, m, f in zip(planned, self.placement, first)]

    # ---- projection ----------------------------------------------------------------------
    def to_projected(self, lon, lat):
        xs, ys = reproject_points("EPSG:4326", "EPSG:%d" % self.epsg, [lon], [lat])
        return xs[0], ys[0]

    def to_lonlat(self, easting, northing):
        xs, ys = reproject_points("EPSG:%d" % self.epsg, "EPSG:4326", [easting], [northing])
        return xs[0], ys[0]

    # ---- heightmaps ----------------------------------------------------------------------
    def _heights(self, seg):
        """The segment's heightmap, memory mapped so a 300 MB file costs nothing until read."""
        key = seg["heightmap_r16"]
        if key not in self._maps:
            rx, ry = seg["resolution"]
            path = os.path.join(os.path.dirname(os.path.abspath(self.path)), key)
            self._maps[key] = np.memmap(path, dtype="<u2", mode="r", shape=(ry, rx))
        return self._maps[key]

    def _segment_for(self, easting, northing):
        for seg in self.segments:
            x0, y1 = seg.get("projected_origin") or self.plan.get("utm_origin")
            rx, ry = seg["resolution"]
            if x0 <= easting <= x0 + (rx - 1) * self.quad and \
               y1 - (ry - 1) * self.quad <= northing <= y1:
                return seg, x0, y1
        return None, None, None

    def ground_elevation(self, lon, lat):
        """Metres above sea level under a point, or None when it is off the landscape."""
        easting, northing = self.to_projected(lon, lat)
        seg, x0, y1 = self._segment_for(easting, northing)
        if seg is None:
            return None
        rx, ry = seg["resolution"]
        col = int(round((easting - x0) / self.quad))
        row = int(round((y1 - northing) / self.quad))
        if not (0 <= col < rx and 0 <= row < ry):
            return None
        h = float(self._heights(seg)[row, col])
        scale_z = float(seg.get("actor_scale", self.plan["actor_scale"])[2])
        mid = float(seg.get("elev_mid_m", self.plan["elev_mid_m"]))
        return (h - 32768.0) * scale_z / 12800.0 + mid

    # ---- frames --------------------------------------------------------------------------
    def unreal_cm(self, lon, lat, elevation_m):
        """Unreal centimetres for a point at a known elevation."""
        easting, northing = self.to_projected(lon, lat)
        seg, x0, y1 = self._segment_for(easting, northing)
        if seg is None:
            seg = self.segments[0]
            x0, y1 = seg.get("projected_origin") or self.plan["utm_origin"]
        loc = self.location_cm(seg)
        mid = float(seg.get("elev_mid_m", self.plan["elev_mid_m"]))
        return ((easting - x0) * 100.0,
                (y1 - northing) * 100.0,
                loc[2] + (elevation_m - mid) * 100.0)

    def ned(self, lon, lat, elevation_m):
        """NED metres, the frame the simulator flies in."""
        x, y, z = self.unreal_cm(lon, lat, elevation_m)
        return x / 100.0, y / 100.0, -z / 100.0

    def lonlat_from_unreal(self, x_cm, y_cm):
        """Back from Unreal centimetres to longitude and latitude, for drawing a reported
        position on a map."""
        seg = self.segments[0]
        x0, y1 = seg.get("projected_origin") or self.plan["utm_origin"]
        return self.to_lonlat(x0 + x_cm / 100.0, y1 - y_cm / 100.0)

    def lonlat_from_ned(self, north, east):
        """The simulator reports NED; the map wants longitude and latitude."""
        return self.lonlat_from_unreal(north * 100.0, east * 100.0)

    def projected_from_ned(self, north, east):
        """NED metres to the plan's projected easting and northing.

        The projected frame is where distances are honest metres in both directions, which is
        why airspace volumes and geofences are built and tested in it rather than in degrees."""
        seg = self.segments[0]
        x0, y1 = seg.get("projected_origin") or self.plan["utm_origin"]
        return x0 + north, y1 - east

    def ned_from_projected(self, easting, northing):
        """The reverse of projected_from_ned, for drawing a projected shape in the simulator."""
        seg = self.segments[0]
        x0, y1 = seg.get("projected_origin") or self.plan["utm_origin"]
        return easting - x0, y1 - northing

    def elevation_from_down(self, down):
        """NED down back to metres above sea level."""
        seg = self.segments[0]
        loc = self.location_cm(seg)
        mid = float(seg.get("elev_mid_m", self.plan["elev_mid_m"]))
        return (-down * 100.0 - loc[2]) / 100.0 + mid

    def extent_lonlat(self):
        """The landscape's corners, for framing a map on it."""
        seg = self.segments[0]
        x0, y1 = seg.get("projected_origin") or self.plan["utm_origin"]
        w, h = self.plan.get("world_metres", [(seg["resolution"][0] - 1) * self.quad,
                                              (seg["resolution"][1] - 1) * self.quad])
        a = self.to_lonlat(x0, y1)
        b = self.to_lonlat(x0 + w, y1 - h)
        return min(a[0], b[0]), min(a[1], b[1]), max(a[0], b[0]), max(a[1], b[1])


# ---------------------------------------------------------------------------------------------
# The mission
# ---------------------------------------------------------------------------------------------

class Waypoint:
    def __init__(self, name="", lon=0.0, lat=0.0, height=60.0, reference=AGL,
                 speed=10.0, hold_s=0.0):
        self.name = name
        self.lon, self.lat = float(lon), float(lat)
        self.height = float(height)
        self.reference = reference if reference in REFERENCES else AGL
        self.speed = float(speed)
        self.hold_s = float(hold_s)

    def elevation(self, terrain):
        """Metres above sea level, resolving height above ground against the terrain, and a
        simulator height through the level's own frame (so its NED down is exactly -height)."""
        if self.reference == MSL:
            return self.height
        if self.reference == SIM:
            return terrain.elevation_from_down(-self.height) if terrain else None
        ground = terrain.ground_elevation(self.lon, self.lat) if terrain else None
        if ground is None:
            return None
        return ground + self.height

    def as_dict(self):
        return {"name": self.name, "lon": self.lon, "lat": self.lat, "height": self.height,
                "reference": self.reference, "speed": self.speed, "hold_s": self.hold_s}

    @staticmethod
    def from_dict(d):
        return Waypoint(d.get("name", ""), d.get("lon", 0.0), d.get("lat", 0.0),
                        d.get("height", 60.0), d.get("reference", AGL),
                        d.get("speed", 10.0), d.get("hold_s", 0.0))


class Mission:
    def __init__(self, name="mission", plan=None, scene="scene_mcity.jsonc", drone="Drone1"):
        self.name = name
        self.plan = plan or DEFAULT_PLAN
        self.scene = scene
        self.drone = drone
        self.takeoff_height = 20.0        # metres above the ground at the first waypoint
        self.land_at_end = True
        # Which way the aircraft faces, and so which way its cameras look:
        #   forward   align the nose with the direction of travel (the usual thing to want)
        #   waypoint  face the waypoint being flown to, and keep facing it while holding there
        #   free      leave the heading alone, which is what the controller does by default
        self.yaw_mode = "forward"
        # How the mission is declared as airspace and how its operation behaves when it leaves
        # that airspace: margins, timeouts, the contingency action, a planned start. Kept as a
        # plain dict here so this module does not depend on airspace.py; IntentSettings reads it.
        self.intent = {}
        # WHERE THE DRONE STARTS, or None for wherever the scene config puts it. A scene config
        # places each drone once, for every mission that uses it; a mission's own start moves the
        # drone for its flight (fly_mission.py stages a copy of the scene with the start in it), so
        # missions sharing a scene can start in different places. A dict: lon, lat, height (m),
        # reference (agl or msl, as a waypoint's) and optionally yaw_deg. See start_ned.
        self.start = None
        # WHERE THE LIDAR SITS ON THE DRONE, for a flight recorded with fly_mission.py --lidar: an
        # offset in centimetres and a rotation in degrees, in the drone's own frame (x forward, y
        # right, z up). None means DEFAULT_LIDAR_MOUNT. See MAirLidar (Plugins/MAirLidar).
        self.lidar_mount = None
        # WHICH AIRCRAFT FLIES IT: a robot config's file name in AirSim/sim_config (one of
        # built_drones(), say), or None for the one the scene names. fly_mission.py --robot
        # overrides it for one flight.
        self.robot_config = None
        self.waypoints = []

    def start_ned(self, terrain):
        """The start as NED metres, or None when the mission leaves it to the scene.

        A start at 0 m above the ground is put START_CLEARANCE_M above it, so the drone settles
        onto the ground rather than being placed in it. The ground is the landscape's: a start on
        a building, a tree or the M-City scan has to be given a height that clears it."""
        if not self.start:
            return None
        lon, lat = float(self.start["lon"]), float(self.start["lat"])
        height = float(self.start.get("height", 0.0))
        ground = terrain.ground_elevation(lon, lat)
        if ground is None:
            raise ValueError("the start (%.6f, %.6f) is off the landscape" % (lon, lat))
        reference = self.start.get("reference", AGL)
        if reference == AGL:
            elevation = ground + max(height, START_CLEARANCE_M)
        elif reference == SIM:
            elevation = max(terrain.elevation_from_down(-height), ground + START_CLEARANCE_M)
        else:
            elevation = max(height, ground + START_CLEARANCE_M)
        return terrain.ned(lon, lat, elevation)

    # ---- storage -------------------------------------------------------------------------
    def save(self, path):
        data = {"name": self.name, "plan": self.plan, "scene": self.scene, "drone": self.drone,
                "takeoff_height": self.takeoff_height, "land_at_end": self.land_at_end,
                "yaw_mode": self.yaw_mode,
                "intent": self.intent,
                "start": self.start,
                "lidar_mount": self.lidar_mount,
                "robot_config": self.robot_config,
                "FRAME": "lon/lat in WGS84 degrees; height in metres, 'agl' above the ground "
                         "beneath the point, 'msl' above sea level, or 'sim' up in the simulator "
                         "(Unreal Z / 100, flown at exactly that height); speed m/s; hold_s seconds",
                "waypoints": [w.as_dict() for w in self.waypoints]}
        with io.open(path, "w", encoding="utf-8", newline="\n") as f:
            json.dump(data, f, indent=2)
            f.write("\n")
        return path

    @staticmethod
    def load(path):
        with io.open(path, encoding="utf-8") as f:
            d = json.load(f)
        m = Mission(d.get("name", "mission"), d.get("plan"), d.get("scene", "scene_mcity.jsonc"),
                    d.get("drone", "Drone1"))
        m.takeoff_height = float(d.get("takeoff_height", 20.0))
        m.land_at_end = bool(d.get("land_at_end", True))
        m.yaw_mode = d.get("yaw_mode", "forward")
        m.intent = d.get("intent") or {}
        start = d.get("start")
        m.start = dict(start) if isinstance(start, dict) and "lon" in start and "lat" in start else None
        mount = d.get("lidar_mount")
        m.lidar_mount = dict(mount) if isinstance(mount, dict) else None
        m.robot_config = robot_config_name(d.get("robot_config"))
        m.waypoints = [Waypoint.from_dict(w) for w in d.get("waypoints", [])]
        return m

    # ---- names ---------------------------------------------------------------------------
    def unique_name(self, stem="WP"):
        taken = {w.name for w in self.waypoints}
        i = 1
        while "%s%d" % (stem, i) in taken:
            i += 1
        return "%s%d" % (stem, i)

    # ---- the flight ----------------------------------------------------------------------
    def legs(self, terrain):
        """Every waypoint as (waypoint, north, east, down, elevation). Raises on a bad one."""
        out = []
        for w in self.waypoints:
            elev = w.elevation(terrain)
            if elev is None:
                raise ValueError("%s is outside the landscape, so there is no ground under it to "
                                 "measure a height from. Move it, or give it a height above sea "
                                 "level instead." % (w.name or "a waypoint"))
            north, east, down = terrain.ned(w.lon, w.lat, elev)
            out.append((w, north, east, down, elev))
        return out

    def check(self, terrain):
        """Everything wrong with the mission, in the order a pilot would care about."""
        problems = []
        if len(self.waypoints) < 1:
            problems.append("The mission has no waypoints.")
        if self.yaw_mode not in YAW_MODES:
            problems.append("'%s' is not a way to face: it will fly facing %s instead."
                            % (self.yaw_mode, YAW_MODES[0]))
        if self.start and terrain:
            try:
                self.start_ned(terrain)
            except (KeyError, TypeError, ValueError) as e:
                problems.append("The start cannot be used: %s." % e)
        seen = set()
        for w in self.waypoints:
            if not w.name:
                problems.append("A waypoint has no name.")
            elif w.name in seen:
                problems.append("More than one waypoint is called '%s'." % w.name)
            seen.add(w.name)
            if w.speed <= 0.0:
                problems.append("%s has a speed of %.1f m/s." % (w.name, w.speed))
            elif w.speed > MAX_CONTROLLER_SPEED_MS:
                problems.append("%s asks for %.0f m/s; this airframe flies at about %.0f m/s at "
                                "most, so its leg is timed at that." % (w.name, w.speed,
                                                                        MAX_CONTROLLER_SPEED_MS))
            ground = terrain.ground_elevation(w.lon, w.lat) if terrain else None
            if ground is None:
                problems.append("%s is outside the landscape." % w.name)
                continue
            elev = w.elevation(terrain)
            # The first and last waypoints may be on the ground: where it takes off and lands.
            on_ground_ok = w is self.waypoints[0] or w is self.waypoints[-1]
            if elev is not None and elev - ground < -0.5:
                problems.append("%s is %.1f m below the ground." % (w.name, ground - elev))
            elif elev is not None and elev - ground < 2.0 and not on_ground_ok:
                problems.append("%s is %.1f m above the ground, which is below the 2 m floor."
                                % (w.name, elev - ground))
        return problems

    def distance_m(self, terrain):
        """Route length in metres, following the ground profile."""
        total = 0.0
        pts = []
        for w in self.waypoints:
            elev = w.elevation(terrain)
            if elev is None:
                return None
            pts.append(terrain.ned(w.lon, w.lat, elev))
        for a, b in zip(pts, pts[1:]):
            total += math.dist(a, b)
        return total

    def duration_s(self, terrain):
        """A rough flight time: each leg at the speed of the waypoint it flies to."""
        pts = []
        for w in self.waypoints:
            elev = w.elevation(terrain)
            if elev is None:
                return None
            pts.append((w, terrain.ned(w.lon, w.lat, elev)))
        t = 0.0
        for (_, a), (w, b) in zip(pts, pts[1:]):
            t += math.dist(a, b) / effective_speed(w) + w.hold_s
        return t

# ---------------------------------------------------------------------------------------------
# Watching a flight against its plan
# ---------------------------------------------------------------------------------------------

def heading_to(a, b):
    """The compass-style heading from a to b in this NED frame, in radians.

    NED's x is the frame's "north" and y its "east", so the heading of the leg is atan2(east, north).
    It is the same arithmetic whether or not that frame is aligned with true north, which here it is
    not: the simulator's north follows Unreal's X axis.
    """
    return math.atan2(b[1] - a[1], b[0] - a[0])


def _segment_distance(p, a, b):
    """Distance from p to the segment ab, and how far along ab the nearest point is (0 to 1)."""
    ax, ay, az = a
    bx, by, bz = b
    px, py, pz = p
    dx, dy, dz = bx - ax, by - ay, bz - az
    length = dx * dx + dy * dy + dz * dz
    if length <= 1e-9:
        return math.dist(p, a), 0.0
    t = ((px - ax) * dx + (py - ay) * dy + (pz - az) * dz) / length
    t = max(0.0, min(1.0, t))
    near = (ax + dx * t, ay + dy * t, az + dz * t)
    return math.dist(p, near), t


def deviation(path, point):
    """How far a point is from a planned route, in metres, and which leg it is nearest.

    THE ROUTE IS THE LINE, NOT THE WAYPOINTS. A drone that cuts a corner is where it should be; one
    that is 40 m to the side of the line between two waypoints is not, even while it sits exactly
    halfway between them. So this measures to the nearest point on the nearest LEG, which is what
    "how far off the path" means to anyone looking at it.

    path:  a list of (north, east, down) in metres.
    Returns (metres, leg index), or (None, -1) when the route has no legs.
    """
    if len(path) < 2:
        return (math.dist(point, path[0]), 0) if path else (None, -1)
    best, best_leg = None, -1
    for i in range(len(path) - 1):
        d, _ = _segment_distance(point, path[i], path[i + 1])
        if best is None or d < best:
            best, best_leg = d, i
    return best, best_leg
