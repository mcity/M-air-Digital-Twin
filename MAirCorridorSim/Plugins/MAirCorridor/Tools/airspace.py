"""airspace.py - a mission as declared airspace, and an operation that has to stay inside it.

Used by fly_mission.py and the planner; not run on its own.

WHERE THIS COMES FROM. The model is the one ASTM F3548 uses for UTM, as implemented by the OpenUTM
project's Flight Blender (https://github.com/openutm/flight-blender, Apache 2.0). Nothing is copied
from it; the ideas are. The two that matter:

  A FLIGHT IS DECLARED AS 4D VOLUMES. Not a line, but a set of shapes, each with an altitude band
  and a time window: "between 10:00:20 and 10:01:40 this aircraft will be inside this polygon,
  between 290 and 330 metres". Conformance is then a yes or no, "inside the declared volume at the
  declared time", rather than a distance off a line with thresholds somebody chose. The same shapes
  are what deconfliction compares, and what a real UTM system would exchange.

  AN OPERATION HAS A LIFECYCLE. Accepted, Activated, Nonconforming, Contingent, Ended, plus the
  ways out before it starts. Leaving the volumes is an event that changes the state, and a state
  that persists is what triggers a contingency action. That is what turns a script that flies
  waypoints into a control system: it knows when it has stopped doing what it said it would.

WHAT IS DONE DIFFERENTLY ON PURPOSE. Flight Blender buffers geometry by 0.0005 DEGREES and its
default deconfliction compares bounding boxes. A degree of longitude is three quarters the length
of a degree of latitude here, so that buffer is 55 m one way and 41 m the other, and the bounding
box of a diagonal route is mostly empty sky. Everything here is built in the landscape's projected
frame, where a metre is a metre in both directions, and compared as true shapes.

ALTITUDES are metres in the landscape's own vertical datum, which for this project is NAVD88 (USGS
3DEP). That is what "msl" means in a mission file here. geoid.py converts to and from the WGS84
ellipsoid that GPS, ADS-B and the F3548 exchange format use.
"""
import io
import json
import math
import os
import threading
import time

try:
    from shapely.geometry import LineString, Point, mapping
    from shapely.geometry import Polygon
except ImportError:                      # named plainly: the one dependency this needs
    raise SystemExit("airspace needs shapely: py -3.10 -m pip install -r requirements.txt")

# ---------------------------------------------------------------------------------------------
# What a declared volume is allowed to be
# ---------------------------------------------------------------------------------------------

# Defaults for how much room a mission declares around its route. Saved per mission, these are
# only what a new one starts with. Thirty metres across covers a quadrotor cutting a corner at
# twelve metres a second; twenty metres up and down covers the altitude hold of the sim's
# controller with room to spare, measured against the flights recorded here.
DEFAULT_LATERAL_M = 30.0
DEFAULT_VERTICAL_M = 20.0

# The time windows are estimates of when each leg is flown, so they get slack, and the slack grows
# with elapsed time because every estimate before it can be wrong in the same direction.
DEFAULT_TIME_SLACK_S = 60.0
TIME_SLACK_GROWTH = 0.15

# How the operation reacts. Telemetry stale after fifteen seconds is Flight Blender's C9a.
DEFAULT_NONCONFORMING_TIMEOUT_S = 20.0
DEFAULT_RETURN_AFTER_S = 3.0
DEFAULT_TELEMETRY_STALE_S = 15.0
DEFAULT_CONTINGENCY = "hold"
CONTINGENCIES = ("hold", "land", "home", "continue")

# Estimates for the parts of a flight the mission does not describe.
TAKEOFF_S = 10.0
LANDING_RATE_MS = 1.0


class IntentSettings:
    """How a mission is turned into airspace, and how its operation behaves. Saved with it."""

    FIELDS = ("lateral_m", "vertical_m", "time_slack_s", "nonconforming_timeout_s",
              "return_after_s", "telemetry_stale_s", "contingency", "planned_start")

    def __init__(self, **kw):
        self.lateral_m = float(kw.get("lateral_m", DEFAULT_LATERAL_M))
        self.vertical_m = float(kw.get("vertical_m", DEFAULT_VERTICAL_M))
        self.time_slack_s = float(kw.get("time_slack_s", DEFAULT_TIME_SLACK_S))
        self.nonconforming_timeout_s = float(kw.get("nonconforming_timeout_s",
                                                    DEFAULT_NONCONFORMING_TIMEOUT_S))
        self.return_after_s = float(kw.get("return_after_s", DEFAULT_RETURN_AFTER_S))
        self.telemetry_stale_s = float(kw.get("telemetry_stale_s", DEFAULT_TELEMETRY_STALE_S))
        contingency = kw.get("contingency", DEFAULT_CONTINGENCY)
        self.contingency = contingency if contingency in CONTINGENCIES else DEFAULT_CONTINGENCY
        # When the flight is meant to start, as an ISO string or None. Without it the mission can
        # still be checked against geofences, but not against other missions in time, so it is
        # treated as overlapping all of them, which is the safe answer.
        self.planned_start = kw.get("planned_start") or None

    def as_dict(self):
        return {f: getattr(self, f) for f in self.FIELDS}

    @classmethod
    def from_dict(cls, d):
        return cls(**(d or {}))


# ---------------------------------------------------------------------------------------------
# Volumes
# ---------------------------------------------------------------------------------------------

class Volume:
    """One shape the aircraft has declared it will be inside, between two heights and two times.

    shape is a shapely polygon in the plan's projected metres. lower and upper are metres in the
    landscape's datum. t0 and t1 are seconds after the operation is activated."""

    def __init__(self, kind, name, shape, lower, upper, t0, t1):
        self.kind = kind                 # departure, leg or landing
        self.name = name
        self.shape = shape
        self.lower = float(lower)
        self.upper = float(upper)
        self.t0 = float(t0)
        self.t1 = float(t1)

    def contains(self, point, elevation):
        return (self.lower <= elevation <= self.upper) and self.shape.covers(point)

    def distance_out(self, point, elevation):
        """How far outside, as (across, up or down), both zero when inside."""
        across = 0.0 if self.shape.covers(point) else self.shape.distance(point)
        vertical = max(0.0, self.lower - elevation, elevation - self.upper)
        return across, vertical

    def as_dict(self, terrain=None):
        out = {"kind": self.kind, "name": self.name,
               "lower_m": round(self.lower, 1), "upper_m": round(self.upper, 1),
               "t0_s": round(self.t0, 1), "t1_s": round(self.t1, 1),
               "area_m2": round(self.shape.area, 0)}
        if terrain is not None:
            out["outline_lonlat"] = outline_lonlat(self.shape, terrain)
        return out


def outline_lonlat(shape, terrain, max_vertices=48):
    """A projected polygon as longitude and latitude, simplified to a sensible vertex count."""
    ring = list(shape.exterior.coords)
    if len(ring) > max_vertices:
        step = max(1, len(ring) // max_vertices)
        ring = ring[::step] + [ring[-1]]
    out = []
    for easting, northing in ring:
        lon, lat = terrain.to_lonlat(easting, northing)
        out.append([round(lon, 7), round(lat, 7)])
    return out


def start_of(mission, terrain, scene_dir):
    """Where a mission's drone starts, as NED: the mission's own start when it has one, else the
    scene config's spawn. Everything that declares or checks the departure asks this, so the
    airspace, the strategic check and the flight agree on where the climb begins."""
    start = mission.start_ned(terrain) if getattr(mission, "start", None) else None
    if start is not None:
        return start
    return spawn_from_scene(os.path.join(scene_dir, mission.scene), mission.drone)


def spawn_from_scene(scene_path, drone_name=None):
    """Where the drone starts, as NED, from the scene config. None when it cannot be found.

    The mission does not describe the climb and transit from the spawn point to its first waypoint,
    but the aircraft still flies them, so the operation has to declare them. Leaving that out is
    why the first flights recorded here showed a worst deviation of 72 m: it was the transit."""
    try:
        from recording import load_jsonc
        scene = load_jsonc(scene_path)
    except Exception:
        return None
    for actor in scene.get("actors", []):
        if actor.get("type") != "robot":
            continue
        if drone_name and actor.get("name") != drone_name:
            continue
        xyz = (actor.get("origin") or {}).get("xyz")
        if not xyz:
            return None
        try:
            north, east, down = (float(v) for v in str(xyz).split())
            return north, east, down
        except ValueError:
            return None
    return None


class OperationalIntent:
    """A mission as the airspace it declares: departure, one volume per leg, landing."""

    def __init__(self, volumes, settings, terrain, mission_name=""):
        self.volumes = volumes
        self.settings = settings
        self.terrain = terrain
        self.mission_name = mission_name
        self.spawn_ned = None

    @property
    def duration_s(self):
        return max((v.t1 for v in self.volumes), default=0.0)

    @property
    def footprint(self):
        """Every volume's shape together, for drawing and for a quick first test."""
        from shapely.ops import unary_union
        return unary_union([v.shape for v in self.volumes])

    @classmethod
    def from_mission(cls, mission, terrain, settings=None, spawn_ned=None):
        settings = settings or IntentSettings.from_dict(getattr(mission, "intent", None))
        legs = mission.legs(terrain)                 # raises on a waypoint with no ground under it
        if not legs:
            return cls([], settings, terrain, mission.name)

        from flightplan import effective_speed

        def at(north, east):
            return Point(*terrain.projected_from_ned(north, east))

        def slack(t):
            return settings.time_slack_s + TIME_SLACK_GROWTH * max(0.0, t)

        volumes = []
        clock = 0.0
        lateral, vertical = settings.lateral_m, settings.vertical_m

        # DEPARTURE: takeoff where the drone spawns, then the transit to the first waypoint.
        first_w, n1, e1, d1, elev1 = legs[0]
        if spawn_ned is not None:
            sn, se, sd = spawn_ned
            spawn_elev = terrain.elevation_from_down(sd)
            lon, lat = terrain.lonlat_from_ned(sn, se)
            ground = terrain.ground_elevation(lon, lat)
            ground = spawn_elev if ground is None else ground
            transit = math.dist((sn, se, sd), (n1, e1, d1))
            t_end = clock + TAKEOFF_S + transit / effective_speed(first_w)
            shape = LineString([tuple(at(sn, se).coords)[0], tuple(at(n1, e1).coords)[0]]) \
                .buffer(lateral) if transit > 0.5 else at(n1, e1).buffer(lateral)
            volumes.append(Volume("departure", "departure to %s" % first_w.name, shape,
                                  min(ground, spawn_elev, elev1) - vertical,
                                  max(spawn_elev, elev1) + vertical,
                                  clock - slack(clock), t_end + slack(t_end)))
            clock = t_end
        clock += first_w.hold_s

        # LEGS: capsules between waypoints, each banded between the heights it actually spans.
        #
        # A CLIMBING LEG IS SPLIT. A volume has one altitude band, so a leg climbing 50 m as one
        # volume gets a band 90 m deep, and an aircraft 40 m too high halfway along it would be
        # called conforming. Measured, not supposed: that test passed before this was here. So a
        # leg is cut into pieces, each spanning no more height than the vertical margin, and each
        # piece is banded around its own two ends.
        for (wa, na, ea, da, ela), (wb, nb, eb, db, elb) in zip(legs, legs[1:]):
            length = math.dist((na, ea, da), (nb, eb, db))
            t_leg = length / effective_speed(wb)
            pieces = max(1, int(math.ceil(abs(elb - ela) / max(1.0, vertical))))
            for k in range(pieces):
                f0, f1 = k / float(pieces), (k + 1) / float(pieces)
                pa = (na + (nb - na) * f0, ea + (eb - ea) * f0)
                pb = (na + (nb - na) * f1, ea + (eb - ea) * f1)
                h0, h1 = ela + (elb - ela) * f0, ela + (elb - ela) * f1
                t0 = clock + t_leg * f0
                t1 = clock + t_leg * f1 + (wb.hold_s if k == pieces - 1 else 0.0)
                span = math.dist(pa, pb)
                shape = (LineString([tuple(at(*pa).coords)[0], tuple(at(*pb).coords)[0]])
                         .buffer(lateral) if span > 0.5 else at(*pb).buffer(lateral))
                name = "%s to %s" % (wa.name, wb.name)
                if pieces > 1:
                    name += " (%d of %d)" % (k + 1, pieces)
                volumes.append(Volume("leg", name, shape, min(h0, h1) - vertical,
                                      max(h0, h1) + vertical, t0 - slack(t0), t1 + slack(t1)))
            clock += t_leg + wb.hold_s

        # LANDING: straight down at the last waypoint.
        last_w, nl, el, dl, ell = legs[-1]
        if getattr(mission, "land_at_end", True):
            ground = terrain.ground_elevation(last_w.lon, last_w.lat)
            ground = ell if ground is None else ground
            t_end = clock + max(0.0, ell - ground) / LANDING_RATE_MS + 10.0
            volumes.append(Volume("landing", "landing at %s" % last_w.name,
                                  at(nl, el).buffer(lateral), ground - vertical,
                                  ell + vertical, clock - slack(clock), t_end + slack(t_end)))
        intent = cls(volumes, settings, terrain, mission.name)
        intent.spawn_ned = spawn_ned       # where the departure starts, for splitting its move
        return intent

    # ---- checking a position ---------------------------------------------------------------
    def check(self, north, east, down, t):
        """Is the aircraft where it said it would be? Returns a Check."""
        easting, northing = self.terrain.projected_from_ned(north, east)
        elevation = self.terrain.elevation_from_down(down)
        point = Point(easting, northing)
        now = [v for v in self.volumes if v.t0 <= t <= v.t1]
        for v in now:
            if v.contains(point, elevation):
                return Check(True, "inside", v, 0.0, 0.0, elevation, t)
        # OVER THE ROUTE BEING FLOWN, AT THE WRONG HEIGHT, is that route's altitude failure, even
        # where some other leg passes over the same ground. A route that comes back over its start
        # put its last leg on top of its first, and an aircraft 48 m under the first leg was called
        # "in WP64 to WP65 but 8676 s early", which is true and hid what was wrong.
        over_now = [v for v in now if v.shape.covers(point)]
        if over_now:
            nearest = min(over_now, key=lambda v: v.distance_out(point, elevation)[1])
            across, up = nearest.distance_out(point, elevation)
            return Check(False, "outside_altitude", nearest, 0.0, up, elevation, t)
        # In the right place at the wrong time is its own failure: an aircraft over a leg it
        # should already have left, or not yet reached.
        for v in self.volumes:
            if v.contains(point, elevation):
                return Check(False, "early" if t < v.t0 else "late", v, 0.0, 0.0, elevation, t,
                             seconds=(v.t0 - t) if t < v.t0 else (t - v.t1))
        pool = now or self.volumes
        if not pool:
            return Check(False, "no_volumes", None, 0.0, 0.0, elevation, t)

        # OVER THE ROUTE AT THE WRONG HEIGHT IS AN ALTITUDE FAILURE, not a lateral one. Picking
        # the nearest volume by straight distance got this wrong: 40 m too high over the first
        # piece of a climbing leg was reported as 4 m outside the second piece, which is true and
        # useless. So the volumes the aircraft is horizontally over are asked first, and a
        # lateral failure is only reported when it is over none of them.
        over = [v for v in pool if v.shape.covers(point)]
        if over:
            nearest = min(over, key=lambda v: v.distance_out(point, elevation)[1])
            across, up = nearest.distance_out(point, elevation)
            return Check(False, "outside_altitude", nearest, 0.0, up, elevation, t)
        nearest = min(pool, key=lambda v: v.shape.distance(point))
        across, up = nearest.distance_out(point, elevation)
        return Check(False, "outside_lateral", nearest, across, up, elevation, t)

    # ---- describing it -------------------------------------------------------------------------
    def table(self):
        lines = ["%-28s %-9s %9s %9s %8s %8s %9s"
                 % ("volume", "kind", "lower m", "upper m", "from s", "to s", "area m2")]
        for v in self.volumes:
            lines.append("%-28s %-9s %9.1f %9.1f %8.0f %8.0f %9.0f"
                         % (v.name[:28], v.kind, v.lower, v.upper, v.t0, v.t1, v.shape.area))
        return "\n".join(lines)

    def as_dict(self):
        return {"mission": self.mission_name, "settings": self.settings.as_dict(),
                "duration_s": round(self.duration_s, 1),
                "datum": "altitudes in metres in the landscape's vertical datum (NAVD88 here)",
                "volumes": [v.as_dict(self.terrain) for v in self.volumes]}

    def to_f3548(self, start_epoch=None, to_ellipsoid=None):
        """The volumes in the shape ASTM F3548 exchanges them, as Flight Blender's Volume4D.

        F3548 altitudes are WGS84 ellipsoid heights ("W84"). to_ellipsoid converts from this
        landscape's datum when given, which needs a geoid model; without one the altitudes are
        written in the datum they are actually in and labelled so, rather than mislabelled W84."""
        start = time.time() if start_epoch is None else float(start_epoch)

        def iso(seconds):
            return time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(start + seconds)) + "Z"

        out = []
        for v in self.volumes:
            vertices = [{"lng": lon, "lat": lat}
                        for lon, lat in outline_lonlat(v.shape, self.terrain)[:-1]]
            centre = v.shape.centroid
            clon, clat = self.terrain.to_lonlat(centre.x, centre.y)
            lower, upper, ref = v.lower, v.upper, "NAVD88"
            if to_ellipsoid is not None:
                lower = to_ellipsoid(clon, clat, v.lower)
                upper = to_ellipsoid(clon, clat, v.upper)
                ref = "W84"
            out.append({"volume": {"outline_polygon": {"vertices": vertices},
                                   "altitude_lower": {"value": round(lower, 1), "reference": ref,
                                                      "units": "M"},
                                   "altitude_upper": {"value": round(upper, 1), "reference": ref,
                                                      "units": "M"}},
                        "time_start": {"value": iso(v.t0), "format": "RFC3339"},
                        "time_end": {"value": iso(v.t1), "format": "RFC3339"}})
        return out

    def geojson(self):
        """The volumes as GeoJSON in longitude and latitude, for a map."""
        features = []
        for v in self.volumes:
            features.append({"type": "Feature",
                             "geometry": {"type": "Polygon",
                                          "coordinates": [outline_lonlat(v.shape, self.terrain)]},
                             "properties": {"name": v.name, "kind": v.kind,
                                            "lower_m": v.lower, "upper_m": v.upper,
                                            "t0_s": v.t0, "t1_s": v.t1}})
        return {"type": "FeatureCollection", "features": features}


def _metres(value):
    """A distance as people read one: a decimal when small, so 0.4 m is not printed as 0 m."""
    return "%.1f" % value if value < 10.0 else "%.0f" % value


class Check:
    """One answer to "is it where it said it would be"."""

    __slots__ = ("ok", "reason", "volume", "across_m", "vertical_m", "elevation", "t", "seconds")

    def __init__(self, ok, reason, volume, across_m, vertical_m, elevation, t, seconds=0.0):
        self.ok = ok
        self.reason = reason
        self.volume = volume
        self.across_m = across_m
        self.vertical_m = vertical_m
        self.elevation = elevation
        self.t = t
        self.seconds = seconds

    def describe(self):
        where = self.volume.name if self.volume else "anything declared"
        if self.ok:
            return "inside %s" % where
        if self.reason == "outside_lateral":
            return "%s m outside %s" % (_metres(self.across_m), where)
        if self.reason == "outside_altitude":
            return "%s m %s %s" % (_metres(self.vertical_m),
                                     "above" if self.elevation > (self.volume.upper
                                                                   if self.volume else 0)
                                     else "below", where)
        if self.reason in ("early", "late"):
            return "in %s but %.0f s %s" % (where, self.seconds, self.reason)
        return self.reason.replace("_", " ")

    def as_dict(self):
        return {"ok": self.ok, "reason": self.reason,
                "volume": self.volume.name if self.volume else None,
                "across_m": round(self.across_m, 1), "vertical_m": round(self.vertical_m, 1),
                "elevation_m": round(self.elevation, 1), "t": round(self.t, 2),
                "seconds": round(self.seconds, 1), "text": self.describe()}


# ---------------------------------------------------------------------------------------------
# The operation and its lifecycle
# ---------------------------------------------------------------------------------------------

# The F3548 states, as Flight Blender numbers them, so a log reads the same in either.
STATES = ("NotSubmitted", "Accepted", "Activated", "Nonconforming", "Contingent", "Ended",
          "Withdrawn", "Cancelled", "Rejected")

# Which state may follow which. Anything not listed is refused rather than quietly taken.
TRANSITIONS = {
    "NotSubmitted": {"Accepted", "Rejected", "Withdrawn", "Cancelled"},
    "Accepted": {"Activated", "Ended", "Nonconforming", "Withdrawn", "Cancelled"},
    "Activated": {"Ended", "Nonconforming", "Contingent"},
    "Nonconforming": {"Activated", "Ended", "Contingent"},
    "Contingent": {"Ended"},
    "Ended": set(), "Withdrawn": set(), "Cancelled": set(), "Rejected": set(),
}

# Live states: the aircraft is, or may be, in the air under this operation.
LIVE = ("Activated", "Nonconforming", "Contingent")


class Operation:
    """One flight's lifecycle, fed by position reports, deciding when to declare a contingency.

    Called from two places at once: position reports arrive on the simulator client's threads,
    and the runner reads the state from its event loop. Everything goes through one lock, and the
    callback that reports a change is called after the lock is released, so it may do anything."""

    def __init__(self, intent, on_change=None, start_state="NotSubmitted"):
        self.intent = intent
        self.settings = intent.settings
        self.on_change = on_change
        self.lock = threading.Lock()
        self.state = start_state
        self.history = []
        self.activated_at = None
        self.nonconforming_since = None
        self.inside_since = None
        self.last_check = None
        self.last_report = None             # wall time of the last position report
        self.reports = 0
        self.inside_reports = 0
        self.worst_across = 0.0
        self.worst_vertical = 0.0
        self.reasons = {}
        self.contingency_reason = None
        # THE OPERATION RUNS ON THE SIMULATOR'S CLOCK when position reports carry it. The declared
        # volumes are timed from the speeds asked for, and the aircraft flies those speeds in
        # simulated time; timed on the wall clock instead, a simulator running at 0.3 of real time
        # put every leg minutes late, and that alone was a contingency. sim_origin_ns is the first
        # report after activation; sim_now the latest, in seconds from it.
        self.sim_origin_ns = None
        self.sim_now = None

    # ---- moving between states ---------------------------------------------------------------
    def _move(self, to, reason, t=None, detail=None):
        """Change state if the lifecycle allows it. Returns the change, or None. Lock held."""
        if to == self.state:
            return None
        if to not in TRANSITIONS.get(self.state, set()):
            return None
        change = {"t": None if t is None else round(t, 2), "wall": time.time(),
                  "from": self.state, "to": to, "reason": reason}
        if detail:
            change["detail"] = detail
        self.state = to
        self.history.append(change)
        return change

    def _emit(self, change):
        if change and self.on_change:
            try:
                self.on_change(change)
            except Exception:
                pass

    def elapsed(self):
        """Seconds since activation: simulated when reports carry the simulator's clock."""
        if self.sim_now is not None:
            return self.sim_now
        return 0.0 if self.activated_at is None else time.time() - self.activated_at

    def activate(self, reason="takeoff"):
        with self.lock:
            self.activated_at = time.time()
            self.last_report = None
            self.sim_origin_ns = None
            self.sim_now = None
            change = self._move("Activated", reason, 0.0)
        self._emit(change)

    def end(self, reason="landed"):
        with self.lock:
            change = self._move("Ended", reason, self.elapsed())
        self._emit(change)

    def cancel(self, reason="stopped by the operator"):
        with self.lock:
            if self.state in LIVE:
                change = self._move("Contingent", reason, self.elapsed())
                if change:
                    self.contingency_reason = reason
            else:
                change = self._move("Cancelled", reason, self.elapsed())
        self._emit(change)

    def accept(self, reason="no conflicts"):
        """Deconfliction found nothing in the way. Only from NotSubmitted, as in F3548."""
        with self.lock:
            change = self._move("Accepted", reason)
        self._emit(change)

    def reject(self, reasons):
        """Deconfliction found something in the way. The operation may not be flown."""
        with self.lock:
            change = self._move("Rejected", "; ".join(reasons) or "conflicts")
        self._emit(change)

    def declare_contingency(self, reason):
        with self.lock:
            change = self._move("Contingent", reason, self.elapsed())
            if change:
                self.contingency_reason = reason
        self._emit(change)

    # ---- what the aircraft is doing ----------------------------------------------------------
    def observe(self, north, east, down, t=None, sim_ns=None):
        """One position report. Returns the Check, after any state change it caused. sim_ns is
        the report's simulator timestamp; with it the operation is timed in simulated seconds."""
        if t is None and sim_ns is not None and self.activated_at is not None:
            with self.lock:
                if self.sim_origin_ns is None:
                    self.sim_origin_ns = sim_ns
                self.sim_now = max(0.0, (sim_ns - self.sim_origin_ns) / 1e9)
                t = self.sim_now
        t = self.elapsed() if t is None else t
        check = self.intent.check(north, east, down, t)
        changes = []
        with self.lock:
            self.last_report = time.time()
            self.last_check = check
            if self.state not in LIVE:
                return check
            self.reports += 1
            if check.ok:
                self.inside_reports += 1
            else:
                self.reasons[check.reason] = self.reasons.get(check.reason, 0) + 1
                self.worst_across = max(self.worst_across, check.across_m)
                self.worst_vertical = max(self.worst_vertical, check.vertical_m)

            if self.state == "Activated" and not check.ok:
                self.nonconforming_since = t
                self.inside_since = None
                changes.append(self._move("Nonconforming", check.describe(), t,
                                          check.as_dict()))
            elif self.state == "Nonconforming":
                if check.ok:
                    # Back inside, but only counted once it STAYS inside, so an aircraft skimming
                    # the boundary does not flicker between two states several times a second.
                    if self.inside_since is None:
                        self.inside_since = t
                    elif t - self.inside_since >= self.settings.return_after_s:
                        changes.append(self._move("Activated",
                                                  "back inside the declared volumes", t))
                        self.nonconforming_since = None
                else:
                    self.inside_since = None
                    if t - (self.nonconforming_since or t) >= \
                            self.settings.nonconforming_timeout_s:
                        reason = "nonconforming for %.0f s: %s" % (
                            t - self.nonconforming_since, check.describe())
                        change = self._move("Contingent", reason, t, check.as_dict())
                        if change:
                            self.contingency_reason = reason
                        changes.append(change)
        for change in changes:
            self._emit(change)
        return check

    def watch_telemetry(self):
        """Called on a timer. No reports for long enough is a contingency in its own right.

        Flight Blender's C9a and C9b: nothing in fifteen seconds, or nothing ever. An aircraft
        nobody can see is not conforming to anything, whatever it was doing last."""
        with self.lock:
            if self.state not in ("Activated", "Nonconforming"):
                return None
            elapsed = self.elapsed()
            if self.last_report is None:
                if elapsed < self.settings.telemetry_stale_s:
                    return None
                reason = "no position report since activation, %.0f s ago" % elapsed
            else:
                age = time.time() - self.last_report
                if age < self.settings.telemetry_stale_s:
                    return None
                reason = "no position report for %.1f s" % age
            change = self._move("Contingent", reason, elapsed)
            if change:
                self.contingency_reason = reason
        self._emit(change)
        return change

    # ---- reporting ---------------------------------------------------------------------------
    def summary(self):
        with self.lock:
            inside = (100.0 * self.inside_reports / self.reports) if self.reports else None
            return {"state": self.state,
                    "transitions": list(self.history),
                    "reports": self.reports,
                    "inside_percent": None if inside is None else round(inside, 1),
                    "worst_outside_across_m": round(self.worst_across, 1),
                    "worst_outside_vertical_m": round(self.worst_vertical, 1),
                    "nonconformance_reasons": dict(self.reasons),
                    "contingency": self.contingency_reason,
                    "settings": self.settings.as_dict()}
