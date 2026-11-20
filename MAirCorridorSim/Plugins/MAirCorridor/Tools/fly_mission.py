"""fly_mission.py - fly a saved mission with Project AirSim, and watch what it does.

    py -3.10 fly_mission.py missions/patrol.json --dry-run
    py -3.10 fly_mission.py missions/patrol.json
    py -3.10 fly_mission.py missions/patrol.json --all
    py -3.10 fly_mission.py missions/patrol.json --record FrontCamera --frames
    py -3.10 fly_mission.py missions/patrol.json --log-sensor gps --log-sensor imu
    py -3.10 fly_mission.py missions/patrol.json --list-capabilities

THE EDITOR MUST ALREADY BE IN PLAY. Project AirSim's sim server starts with the game and waits for a
client; one that connects to nothing reports a connection error rather than "press Play".

WHAT IT DOES. Reads the mission, resolves every waypoint's height against the landscape it was drawn
on, connects, takes off, flies the waypoints in order at their own speeds, holds where asked, lands.
Each leg is a separate move so a per-waypoint speed and hold mean something; one move_on_path call
would fly the lot at a single velocity.

WHAT IT WATCHES. While flying it subscribes to the drone's reported pose and measures how far that
is from the planned route, writing every sample to a track file and printing it. DEVIATION IS
MEASURED TO THE LINE, not to the next waypoint: a drone cutting a corner is where it should be, one
40 m to the side of a leg is not, even halfway between two waypoints.

WHAT IT RECORDS. With --all, everything the drone carries: every camera as video, every sensor, the
camera metadata beside each image stream, and the aircraft's own collision and rotor state, all of
it stamped with the simulator's clock and described by a manifest. Individual streams can be picked
instead with --record and --log-sensor. Sensors are not created here: they are whatever the robot
config declares, which --list-capabilities prints.

WHY THE RECORDING IS SHAPED THE WAY IT IS. It is meant to work in both directions. Going out, a
simulated flight is training and validation material for something that will fly for real, so the
pixels stay lossless on request, depth stays sixteen bit, labels are kept, and every stream carries
the sim timestamp needed to line it up with the others. Coming back, a flight flown for real has to
be comparable with the same route flown here, so the manifest writes down the projection, the
landscape origin, the NED law and the geodetic reference. recording.py holds the detail.
"""
import argparse
import asyncio
import io
import json
import math
import os
import shutil
import signal
import sys
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import airspace                                                                           # noqa: E402
import recording as rec                                                                    # noqa: E402
from flightplan import (DEFAULT_LIDAR_MOUNT, SIM_CONFIG_DIR, START_CLEARANCE_M, YAW_MODES, Mission,  # noqa: E402
                        Terrain, deviation, effective_speed, heading_to, robot_config_name)

from toolpaths import FROZEN, HERE, PROJECTAIRSIM                                   # noqa: E402
DEFAULT_CLONE = PROJECTAIRSIM
SCENE_DIR = SIM_CONFIG_DIR


def chosen_robot(mission, args):
    """The robot config this flight flies as, by file name: --robot, else the mission's own, else
    None for the one the scene names."""
    return robot_config_name(getattr(args, "robot", None)) or mission.robot_config

# The sensor name the aircraft's own topics are recorded under: collisions and rotor state belong
# to the robot, not to anything mounted on it.
ROBOT_STATE = "robot"


# ---------------------------------------------------------------------------------------------
# Resolving
# ---------------------------------------------------------------------------------------------

def resolve(mission, terrain, show=True, yaw_mode="forward"):
    legs = mission.legs(terrain)
    if show:
        start = mission.start_ned(terrain)
        if start is not None:
            s = mission.start
            print("start     %.6f, %.6f, %.1f m %s; north %.1f east %.1f down %.1f (the mission's)"
                  % (float(s["lon"]), float(s["lat"]), float(s.get("height", 0.0)),
                     "above the ground" if s.get("reference", "agl") == "agl" else "above sea level",
                     start[0], start[1], start[2]))
        else:
            spawn = airspace.spawn_from_scene(os.path.join(SCENE_DIR, mission.scene), mission.drone)
            print("start     %s (the scene's)" % ("north %.1f east %.1f down %.1f" % spawn
                                                  if spawn else "where the scene puts it"))
        print("%-14s %11s %11s %9s %9s %7s %9s %7s" %
              ("waypoint", "north", "east", "down", "ground", "height", "speed", "facing"))
        previous = None
        for w, north, east, down, elev in legs:
            ground = terrain.ground_elevation(w.lon, w.lat)
            # What the aircraft will be pointing at on the way in. Both steered modes aim along
            # the leg, so one column covers them; "free" keeps whatever heading it had.
            facing = "-"
            if yaw_mode != "free" and previous is not None:
                if math.hypot(north - previous[0], east - previous[1]) < VERTICAL_LEG_M:
                    facing = "kept"
                else:
                    facing = "%.0f deg" % (math.degrees(heading_to(previous, (north, east))) % 360.0)
            previous = (north, east)
            print("%-14s %11.1f %11.1f %9.1f %9.1f %7.1f%s %5.1f m/s %8s"
                  % (w.name, north, east, down, ground, w.height,
                     " " + w.reference, w.speed, facing))
        print("\n%d waypoint(s), %.2f km, roughly %.0f s at the speeds given"
              % (len(legs), mission.distance_m(terrain) / 1000.0, mission.duration_s(terrain)))
    return legs


def build_intent(mission, terrain, args):
    """The mission as the airspace it declares, with any margins given on the command line."""
    settings = airspace.IntentSettings.from_dict(getattr(mission, "intent", None))
    if getattr(args, "lateral", None):
        settings.lateral_m = args.lateral
    if getattr(args, "vertical", None):
        settings.vertical_m = args.vertical
    if getattr(args, "contingency", None):
        settings.contingency = args.contingency
    if getattr(args, "nonconforming_timeout", None):
        settings.nonconforming_timeout_s = args.nonconforming_timeout
    spawn = airspace.start_of(mission, terrain, SCENE_DIR)
    return airspace.OperationalIntent.from_mission(mission, terrain, settings, spawn_ned=spawn)


def strategic_check(intent, mission, terrain, args):
    """Everything this operation's airspace collides with, as reasons. Empty means accepted.

    Filled in by geofences.py when it is present; until then nothing is in the way."""
    try:
        import geofences
    except ImportError:
        return []
    return geofences.conflicts_for(intent, mission, terrain, args)


def preview(mission, args):
    """What this flight would record, worked out from the configs on disk.

    A dry run has no simulator to ask, so this reads the scene and the robot config the same way
    the client does and lists the streams they declare. --list-capabilities asks the running
    simulator instead, and that answer is the authority."""
    scene_path = os.path.join(SCENE_DIR, mission.scene)
    if not os.path.isfile(scene_path):
        print("\nno scene config at %s, so the recording cannot be previewed" % scene_path)
        return
    try:
        extra = [os.path.join(HERE, "projectairsim", "sim_config") if FROZEN else
                 os.path.join(args.clone, "client", "python", "example_user_scripts",
                              "sim_config")]
        config, _scene, where = rec.find_robot_config(scene_path, extra, chosen_robot(mission, args))
    except Exception as e:
        print("\nthe sim configs could not be read: %s" % e)
        return
    if config is None:
        print("\nthe recording cannot be previewed: %s" % where)
        return

    sensors = rec.streams_from_config(config)
    facts = rec.sensor_facts(config)
    images, data, warnings = choose(args, sensors, rec.ROBOT_STATE_STREAMS,
                                    {n: f.get("enabled", True) for n, f in facts.items()})
    print("\nrobot      %s" % where)
    for name in sorted(sensors):
        fact = facts.get(name, {})
        print("  %-14s %-14s %s" % (name, fact.get("type") or "?",
                                    "" if fact.get("enabled", True) else "switched off"))
    for w in warnings:
        print("warning:  %s" % w)
    if not images and not data:
        print("\nnothing would be recorded beyond the track. --all records everything the drone "
              "carries.")
        return
    print("\nwould record")
    for sensor, stream in images:
        sixteen = stream in rec.SIXTEEN_BIT_STREAMS
        how = ["video"] if args.video and not sixteen else []
        if args.frames or sixteen or not how:
            how.append("lossless frames%s" % (" (sixteen bit)" if sixteen else ""))
        print("  %-14s %-28s %s" % (sensor, stream, " and ".join(how)))
    for sensor, stream in data:
        print("  %-14s %-28s %s" % (sensor, stream,
                                    "data" if not args.sensor_hz
                                    else "data at up to %.1f Hz" % args.sensor_hz))
    if args.track:
        print("  %-14s %-28s %s" % ("the flight", "track.jsonl", "pose and deviation"))


def client_paths(clone):
    """Where the client package and its sample configs are. A built release carries both: the
    package inside it, the samples in projectairsim/ beside the executables."""
    if FROZEN:
        return None, os.path.join(HERE, "projectairsim")
    src = os.path.join(clone, "client", "python", "projectairsim", "src")
    scripts = os.path.join(clone, "client", "python", "example_user_scripts")
    if not os.path.isdir(src):
        sys.exit("Cannot find the Project AirSim client at %s.\nPass --clone or set "
                 "PROJECTAIRSIM_ROOT." % src)
    return src, scripts


def stage_scene(mission, scripts, terrain, lidar=False, robot=None):
    """Our configs beside their samples, which is where the client resolves names from. Returns
    that folder and the name of the scene to load.

    Every .jsonc we have, not just the scene: a scene names its robot config by filename and the
    client looks for it in the same folder, so our own robot config has to travel with it.
    Copying ours to THEM rather than theirs to us keeps one copy of each of their samples, which
    is the half that gets updated.

    What is loaded is a copy of the mission's scene, staged beside the rest as
    <scene>.flight.jsonc; the scene config itself, which other missions share, is left as it is.
    The copy starts paused, so the drone cannot fall before catch_at_start has its controller
    holding it, a mission with its own start has the drone's origin moved there, and robot (a
    robot config's file name, see chosen_robot) makes the drone that aircraft."""
    theirs = os.path.join(scripts, "sim_config")
    if not os.path.isdir(theirs) or not os.path.isdir(SCENE_DIR):
        return theirs, mission.scene
    for name in sorted(os.listdir(SCENE_DIR)):
        if name.endswith(".jsonc"):
            shutil.copy2(os.path.join(SCENE_DIR, name), os.path.join(theirs, name))
    scene = rec.load_jsonc(os.path.join(SCENE_DIR, mission.scene))
    scene.setdefault("clock", {})["pause-on-start"] = True
    if lidar:
        # ONE CLOCK FOR THE DRONE AND THE LIDAR. The lidar runs on Unreal's clock: one 25 ms sector every
        # Nth engine frame, each column at its own time. The usual steppable clock advances on its own
        # thread at wall pace, so the drone moved about three times as far per Unreal second as it
        # should, smearing every scan and giving too few of them per flight second. engine-driven
        # advances the drone exactly as Unreal ticks. And 3.125 ms is 25 / 8 exactly, where the usual
        # 3 ms is not a whole fraction of a sector (MAirLidar refuses a step that is not).
        scene["clock"]["type"] = "engine-driven"
        scene["clock"]["step-ns"] = LIDAR_STEP_NS
        scene["clock"].pop("real-time-update-rate", None)
        # Not paused on start: with this clock Project AirSim pauses the game but nothing ever
        # unpauses it, so no time would pass. Simulated time only advances as Unreal renders, so
        # the drone drops for a fraction of a second at most before catch_at_start puts it back.
        scene["clock"]["pause-on-start"] = False
    start = mission.start_ned(terrain)
    if robot and not os.path.isfile(os.path.join(theirs, robot)):
        raise SystemExit("there is no robot config %s in %s (Tools/drone_configs.py writes one for each "
                         "built drone)" % (robot, SCENE_DIR))
    if start is not None or robot:
        found = False
        for actor in scene.get("actors", []):
            if actor.get("type") == "robot" and actor.get("name") == mission.drone:
                if start is not None:
                    origin = actor.setdefault("origin", {})
                    origin["xyz"] = "%.2f %.2f %.2f" % start
                    yaw = float(mission.start.get("yaw_deg", 0.0))
                    origin["rpy-deg"] = "0 0 %.1f" % yaw
                if robot:
                    actor["robot-config"] = robot
                found = True
        if not found:
            raise SystemExit("the scene %s has no robot called %s to %s"
                             % (mission.scene, mission.drone,
                                "start at the mission's start" if start is not None else "fly as " + robot))
    name = os.path.splitext(mission.scene)[0] + ".flight.jsonc"
    with io.open(os.path.join(theirs, name), "w", encoding="utf-8", newline="\n") as f:
        f.write("// Written by fly_mission.py for the mission %s: %s, paused on start%s%s.\n"
                % (mission.name, mission.scene, "" if start is None
                   else ", with %s's origin moved to the mission's start" % mission.drone,
                   "" if not robot else ", flying as %s" % robot))
        json.dump(scene, f, indent=2)
    if start is not None:
        print("start     %s, at the mission's start (north %.1f east %.1f down %.1f)"
              % (name, start[0], start[1], start[2]), flush=True)
    if robot:
        print("aircraft  %s" % robot, flush=True)
    return theirs, name


# ---------------------------------------------------------------------------------------------
# Watching and recording
# ---------------------------------------------------------------------------------------------

def capabilities(drone, facts):
    """Everything this drone can publish, and whether the robot config has it switched on."""
    sensors = {name: sorted(streams) for name, streams in drone.sensors.items()}
    return {"drone": drone.name,
            "sensors": sensors,
            "kinds": {n: {t: rec.stream_kind(t) for t in streams}
                      for n, streams in sensors.items()},
            "types": {n: f.get("type") for n, f in facts.items()},
            "enabled": {n: bool(f.get("enabled", True)) for n, f in facts.items()},
            "robot_state": sorted(drone.robot_info.keys()),
            "note": "a stream whose sensor is not enabled publishes nothing at all"}


def choose(args, sensors, robot_state=(), enabled=None):
    """Which streams to record as video and which to log as data, and what to say about it.

    Separate from the flying so it can be checked without a simulator: --dry-run prints exactly
    what a flight would subscribe to. Everything is (sensor, stream), with ROBOT_STATE standing in
    as the sensor name for the aircraft's own topics, which belong to the robot rather than to any
    sensor on it."""
    enabled = enabled or {}
    images, data, warnings = [], [], []
    everything = bool(getattr(args, "all", False))

    def live(name):
        """False only when the robot config declares the sensor and switches it off."""
        if enabled.get(name, True):
            return True
        warnings.append("%s is declared in the robot config but switched off, so it publishes "
                        "nothing; it was skipped" % name)
        return False

    all_images, all_data = rec.split_streams(sensors)
    if everything or getattr(args, "record_all", False):
        images += [pair for pair in all_images if live(pair[0])]
    if everything or getattr(args, "log_all", False):
        data += [pair for pair in all_data if live(pair[0])]
        # The aircraft's own state. actual_pose is left out because it is the track, written in
        # full to track.jsonl with the deviation measured alongside it.
        data += [(ROBOT_STATE, name) for name in sorted(robot_state) if name != "actual_pose"]

    for spec in getattr(args, "record", None) or []:
        name, _, stream = spec.partition(":")
        streams = sensors.get(name)
        if streams is None:
            warnings.append("there is no camera called '%s'" % name)
            continue
        if stream:
            if stream not in streams:
                warnings.append("%s has no stream '%s'" % (name, stream))
                continue
            wanted = [stream]
        else:
            wanted = [t for t in streams if rec.stream_kind(t) == "image"] or ["scene_camera"]
            if wanted == ["scene_camera"] and "scene_camera" not in streams:
                warnings.append("%s publishes no images" % name)
                continue
        if live(name):
            images += [(name, t) for t in wanted]

    for spec in getattr(args, "log_sensor", None) or []:
        name, _, stream = spec.partition(":")
        if name == ROBOT_STATE:
            data += [(ROBOT_STATE, t) for t in ([stream] if stream else sorted(robot_state))]
            continue
        streams = sensors.get(name)
        if streams is None:
            warnings.append("there is no sensor called '%s'" % name)
            continue
        if stream:
            if stream not in streams:
                warnings.append("%s has no stream '%s'" % (name, stream))
                continue
            wanted = [stream]
        else:
            # A camera named here means its metadata, not its pixels: --record takes the pixels.
            wanted = [t for t in streams if rec.stream_kind(t) == "data"]
            if not wanted:
                warnings.append("%s publishes only images; --record saves those" % name)
                continue
        if live(name):
            data += [(name, t) for t in wanted]

    seen = set()
    images = [x for x in images if not (x in seen or seen.add(x))]
    data = [x for x in data if not (x in seen or seen.add(x))]
    return images, data, warnings


# ---------------------------------------------------------------------------------------------
# Flying
# ---------------------------------------------------------------------------------------------

# THE CLIENT GIVES UP ON ANY ONE COMMAND AFTER FIVE MINUTES (recv_timeout=300000 in the client's
# request socket), whatever the command's own timeout says. A leg of 8.5 km at the controller's
# 21 m/s takes nearly seven, and a mission flown that way died with "Timed out" 2.2 km short of its
# first waypoint. So a long leg is flown as several moves, each planned to take no more than this,
# which leaves well over twice the margin the client needs.
MAX_COMMAND_S = 120.0

# THOSE FIVE MINUTES ARE WALL TIME, and the moves are planned in simulated time. With the simulator
# at 0.3 of real time a move planned at 120 s takes nearly seven minutes, and with the corridor
# level streaming in at 0.07 it takes half an hour. A land command from 290 m at 0.285 outlasted
# the client, the runner stopped, and the aircraft was left hovering where it was. So every
# command is planned to take no more than half the client's patience at the speed the simulator
# is actually running (SimClock), and one the client gives up on anyway is sent again.
CLIENT_TIMEOUT_S = 300.0
COMMAND_RETRIES = 3


def command_budget_s(sim_speed):
    """The most simulated seconds one command may be planned to take."""
    return max(5.0, min(MAX_COMMAND_S, 0.5 * CLIENT_TIMEOUT_S * sim_speed))


def pieces_of(start, end, speed, budget_s=MAX_COMMAND_S, max_climb_m=None):
    """Points along a straight leg, so that no single move outlasts budget_s, and, given
    max_climb_m, so that none climbs or descends more than that.

    WHY THE CLIMB IS LIMITED. The declared volumes follow a leg's slope in pieces, each banded
    within the vertical margin of its own heights (airspace.py). The controller does not follow a
    slope: it goes to a move's height first and covers the distance after. A 96 m descent flown as
    two moves dropped 48 m straight down at its start, under the volume there, and the flight
    stopped. Each move changing height by no more than the margin keeps the aircraft inside the
    band of the ground it is over, however the controller orders height and distance."""
    if start is None:
        return [end]
    length = math.dist(start, end)
    count = max(1, int(math.ceil(length / (speed * budget_s))))
    if max_climb_m:
        count = max(count, int(math.ceil(abs(end[2] - start[2]) / max(1.0, max_climb_m))))
    return [tuple(s + (e - s) * (k / float(count)) for s, e in zip(start, end))
            for k in range(1, count + 1)]


class SimClock:
    """How fast the simulator is running, from the clock on the poses it sends, and where the
    aircraft last was. The speed is over the last WINDOW_S seconds, since it changes: the corridor
    level ran at 0.07 of real time while it streamed in, then 0.3."""

    WINDOW_S = 20.0
    TRAIL_S = 10.0              # simulated seconds of positions kept, for settled()

    def __init__(self):
        self.lock = threading.Lock()
        self.samples = []
        self.trail = []
        self.position = None

    def report(self, position, sim_ns):
        now = time.time()
        with self.lock:
            self.position = position
            if sim_ns is None:
                return
            self.samples.append((now, sim_ns))
            while len(self.samples) > 2 and now - self.samples[0][0] > self.WINDOW_S:
                self.samples.pop(0)
            self.trail.append((sim_ns, position))
            while len(self.trail) > 2 and (sim_ns - self.trail[0][0]) / 1e9 > self.TRAIL_S:
                self.trail.pop(0)

    def settled(self, seconds, up_down_m, across_m):
        """True when, over the last `seconds` of simulated time, the aircraft has stayed within
        up_down_m vertically and across_m sideways of where it was at the start of them."""
        with self.lock:
            if not self.trail or (self.trail[-1][0] - self.trail[0][0]) / 1e9 < seconds:
                return False
            since = self.trail[-1][0] - seconds * 1e9
            window = [p for t, p in self.trail if t >= since]
        n0, e0, d0 = window[0]
        return all(abs(d - d0) <= up_down_m and math.hypot(n - n0, e - e0) <= across_m
                   for n, e, d in window)

    def speed(self, default=0.25):
        """Simulated seconds per real second; default (cautious) until there is enough to measure."""
        with self.lock:
            if len(self.samples) < 2:
                return default
            (w0, s0), (w1, s1) = self.samples[0], self.samples[-1]
        if w1 - w0 < 3.0:
            return default
        return max(0.02, min(2.0, (s1 - s0) / 1e9 / (w1 - w0)))


async def command(make, what):
    """Send a command and wait for it. One the client gives up on is sent again, up to
    COMMAND_RETRIES times: the aircraft is still in the air and still needs it."""
    for attempt in range(1, COMMAND_RETRIES + 1):
        try:
            return await (await make())
        except asyncio.CancelledError:
            raise
        except Exception as e:
            if "timed out" not in str(e).lower() or attempt == COMMAND_RETRIES:
                raise
            print("      %s: the client gave up waiting (%s); sending it again, %d of %d"
                  % (what, e, attempt + 1, COMMAND_RETRIES), flush=True)


# How long a hold contingency hovers before landing, when nobody intervenes. Long enough to see
# what happened and take over in the sim; short enough that an unattended run does not hang.
HOLD_BEFORE_LAND_S = 30.0

# Landing: down in steps to this far above the ground, at this speed, then the land command.
LAND_FROM_M = 10.0
DESCENT_MS = 3.0

# DOWN IS DOWN. Project AirSim's land command finishes after a second of no vertical speed at all,
# which a heavy drone on rough ground may not give it: the 9.5 kg hexa sat on the M-City scan
# bouncing by centimetres, at up to a metre a second for an instant, and tipping slowly, and the
# command ran on for 90 s after it was down, past the landing's declared window. So the landing also
# counts as done when the drone has stayed this still for this long (simulated): about where a real
# autopilot's land detector calls it, once the land command has brought it down at least
# TOUCHDOWN_AFTER_M, so a drone still hovering where the land began is not taken for landed. One
# that lands within that of where it began (a roof just under LAND_FROM_M) waits for the controller
# as before. The controller's land command is left running.
TOUCHDOWN_S = 5.0
TOUCHDOWN_AFTER_M = 1.0
TOUCHDOWN_UP_DOWN_M = 0.1
TOUCHDOWN_ACROSS_M = 0.3


async def come_down(drone, terrain, sim):
    """Descend in steps the client will wait for, then land. See CLIENT_TIMEOUT_S."""
    pos = sim.position
    if pos is not None:
        n, e, d = pos
        lon, lat = terrain.lonlat_from_ned(n, e)
        ground = terrain.ground_elevation(lon, lat)
        if ground is not None:
            target = terrain.ned(lon, lat, ground + LAND_FROM_M)[2]
            if target > d + 1.0:                         # down is positive: the target is below
                steps = pieces_of((n, e, d), (n, e, target), DESCENT_MS,
                                  command_budget_s(sim.speed()))
                for k, (sn, se, sd) in enumerate(steps, 1):
                    print("      descending, step %d of %d" % (k, len(steps)), flush=True)
                    await command(lambda sn=sn, se=se, sd=sd: drone.move_to_position_async(
                        north=sn, east=se, down=sd, velocity=DESCENT_MS), "descent")
    print("landing", flush=True)
    began = sim.position
    land = asyncio.ensure_future(command(lambda: drone.land_async(), "land"))
    while not land.done():
        now = sim.position
        if (began is not None and now is not None and now[2] - began[2] >= TOUCHDOWN_AFTER_M
                and sim.settled(TOUCHDOWN_S, TOUCHDOWN_UP_DOWN_M, TOUCHDOWN_ACROSS_M)):
            print("down: still for %.0f s, though the controller has not yet called it landed"
                  % TOUCHDOWN_S, flush=True)
            land.cancel()
            return
        await asyncio.sleep(0.25)
    await land


# Sim seconds of zero velocity that catch_at_start gives the controller to reach a hover.
HOLD_SPINUP_S = 2.0

# A leg shorter than this across the ground is a climb or a descent, and is flown keeping the heading
# it has. Its heading "along the track" is the angle of the few centimetres between, say, the start
# and a WP1 straight above it, which is rounding: flown ForwardOnly, a 6.3 kg quad spun 190 degrees
# and back on the way up, and one with less thrust to spare sat on the ground under full yaw command,
# unable to lift and unable to turn.
VERTICAL_LEG_M = 2.0


def collision_reporter():
    """A line for each thing the drone hits, by name, at most every 5 s per thing. A drone that
    sits in one place while its controller is flying it is pressed against something, and it
    may be something nobody can see."""
    said = {}

    def on_collision(_topic, message):
        try:
            name = message.get("object_name") or "something unnamed"
            now = time.monotonic()
            if now - said.get(name, -1e9) < 5.0:
                return
            said[name] = now
            p = message.get("impact_point") or message.get("position") or {}
            print("COLLISION with %s at north %.1f east %.1f down %.1f"
                  % (name, float(p.get("x", math.nan)), float(p.get("y", math.nan)),
                     float(p.get("z", math.nan))), flush=True)
        except Exception:
            pass
    return on_collision


async def catch_at_start(world, drone, spawn):
    """Have the controller holding the drone in the air at its start before it can fall.

    World Partition streams the level in after Play starts, so the drone arrives before there is
    anything under it. The scene is loaded paused (see stage_scene), so the drone is still exactly
    where it spawned: API control and arming take effect without the sim running, the hold is
    sent, and only then is the sim let go. A scene that was not loaded paused has had the drone
    falling since it loaded, so it is put back at its start either way.

    The hold is a zero velocity for HOLD_SPINUP_S, not a move to the start. Arming leaves the
    controller at idle throttle, and a move to the point the drone is already at finishes at once
    ("already at end of path") without ever changing that, so the drone dropped like a stone. A
    zero velocity spins the rotors up to a hover; once airborne with no command arriving, the
    controller holds its position by itself, and goes on doing so after this script has gone, so a
    capabilities listing leaves the drone hovering where it spawned. Returns the start."""
    from projectairsim.types import Pose, Quaternion, Vector3

    try:
        drone.enable_api_control()
        drone.arm()
        pose = drone.get_ground_truth_kinematics()["pose"]
        p, q = pose["position"], pose["orientation"]
        here = (float(p["x"]), float(p["y"]), float(p["z"]))
        n, e, d = here if spawn is None else spawn
        fell = here[2] - d
        print("start     holding at north %.1f east %.1f down %.1f%s"
              % (n, e, d, " (it had fallen %.1f m first)" % fell if fell > 0.5 else ""),
              flush=True)

        # Level, facing the way it spawned facing.
        w, x, y, z = (float(q[k]) for k in ("w", "x", "y", "z"))
        yaw = math.atan2(2.0 * (w * z + x * y), 1.0 - 2.0 * (y * y + z * z))
        drone.set_pose(Pose({"translation": Vector3({"x": n, "y": e, "z": d}),
                             "rotation": Quaternion({"w": math.cos(yaw / 2), "x": 0.0, "y": 0.0,
                                                     "z": math.sin(yaw / 2)})}), True)
        hold = await drone.move_by_velocity_async(0.0, 0.0, 0.0, duration=HOLD_SPINUP_S)
    finally:
        # Never leave the editor frozen, even when catching it failed.
        try:
            if world.is_paused():
                world.resume()
        except Exception:
            pass
    await hold
    return n, e, d


# THE LIDAR. The simulated Ouster OS-1-256-RGB (the OusterSim plugin) rides on the drone through the
# MAirLidar plugin, which listens in Unreal's Saved/MAirLidar/: this writes request.json there,
# and reads status.json back. Files rather than an API, so the same flight works against the editor
# and a packaged release, whose Saved folder is its own (project_saved_dir finds whichever is
# running). The scans themselves are written by Unreal under Saved/OusterSim/<flight>, because
# OusterSim writes nowhere else inside a project; the flight's manifest says where.
LIDAR_START_WAIT_S = 120.0     # wall seconds for the bridge to find the drone and start
LIDAR_STEP_NS = 3125000        # the clock step for a lidar flight: 25 ms / 8 (see stage_scene)
LIDAR_STOP_WAIT_S = 120.0      # wall seconds for the last scans to be written


def set_mcity_view(view):
    """Ask the level to show M-City as the scan or the twin (MAirMcityViewSubsystem reads it)."""
    saved = project_saved_dir()
    if saved is None:
        print("warning:  no Unreal project found above this plugin, so M-City stays as it is")
        return
    folder = os.path.join(saved, "MAirCorridor")
    os.makedirs(folder, exist_ok=True)
    tmp = os.path.join(folder, "mcity_view.json.tmp")
    with io.open(tmp, "w", encoding="utf-8") as f:
        json.dump({"view": view, "asked": time.time()}, f)
    os.replace(tmp, os.path.join(folder, "mcity_view.json"))
    print("mcity     shown as the %s" % ("digital twin" if view == "twin" else "scan"), flush=True)


def project_saved_dir():
    """The Saved folder of the Unreal that is flying: MAIR_PROJECT_SAVED if set, else that of a
    packaged release of this project while one is running, else the project this plugin sits in
    (the editor, and play mode, use the project's own)."""
    given = os.environ.get("MAIR_PROJECT_SAVED")
    if given:
        return given
    project = None
    d = os.path.dirname(HERE)
    for _ in range(6):
        d = os.path.dirname(d)
        if not d:
            break
        hits = [f for f in os.listdir(d) if f.lower().endswith(".uproject")] if os.path.isdir(d) else []
        if hits:
            project = os.path.join(d, hits[0])
            break
    name = os.path.splitext(os.path.basename(project))[0] if project else None
    release = running_release_saved_dir(name)
    if release:
        _say_once("unreal    a packaged release is running; its Saved folder is %s" % release)
        return release
    return os.path.join(os.path.dirname(project), "Saved") if project else None


def running_release_saved_dir(name=None):
    """The Saved folder of a running packaged release, or None when none is running.

    A release keeps its own Saved folder rather than the project's: beside its content in a
    Development build (<release>/Windows/<name>/Saved), and in the user's local app data in a
    Shipping one (%LOCALAPPDATA%/<name>/Saved). It is recognised by where its executable is,
    <name>/Binaries/Win64/<exe> beside <name>/Content/Paks, so a built copy of these tools, which
    has no project above it to take a name from, still finds it. With a name, only a release of
    that project counts."""
    if os.name != "nt":
        return None
    import ctypes
    from ctypes import wintypes
    psapi, kernel32 = ctypes.WinDLL("psapi"), ctypes.WinDLL("kernel32")
    kernel32.OpenProcess.restype = wintypes.HANDLE
    kernel32.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
    kernel32.QueryFullProcessImageNameW.argtypes = (wintypes.HANDLE, wintypes.DWORD,
                                                    wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD))
    kernel32.CloseHandle.argtypes = (wintypes.HANDLE,)
    pids = (wintypes.DWORD * 8192)()
    got = wintypes.DWORD()
    if not psapi.EnumProcesses(pids, ctypes.sizeof(pids), ctypes.byref(got)):
        return None
    for pid in pids[:got.value // ctypes.sizeof(wintypes.DWORD)]:
        handle = kernel32.OpenProcess(0x1000, False, pid)   # PROCESS_QUERY_LIMITED_INFORMATION
        if not handle:
            continue
        buf = ctypes.create_unicode_buffer(1024)
        size = wintypes.DWORD(len(buf))
        ok = kernel32.QueryFullProcessImageNameW(handle, 0, buf, ctypes.byref(size))
        kernel32.CloseHandle(handle)
        if not ok:
            continue
        folder = os.path.dirname(buf.value)
        root = os.path.dirname(os.path.dirname(folder))
        if (os.path.basename(folder).lower() != "win64"
                or os.path.basename(os.path.dirname(folder)).lower() != "binaries"
                or not os.path.isdir(os.path.join(root, "Content", "Paks"))):
            continue
        game = os.path.basename(root)
        if name and game.lower() != name.lower():
            continue
        if "-shipping" in os.path.basename(buf.value).lower():
            return os.path.join(os.environ.get("LOCALAPPDATA", ""), game, "Saved")
        return os.path.join(root, "Saved")
    return None


_SAID = set()


def _say_once(text):
    if text not in _SAID:
        _SAID.add(text)
        print(text, flush=True)


class LidarLink:
    """The flight's side of the conversation with MAirLidar."""

    def __init__(self, saved):
        self.dir = os.path.join(saved, "MAirLidar")
        self.saved = saved
        self.seq = None
        self.status = {}

    def _request(self, body):
        self.seq = int(time.time() * 1000)
        body = dict(body, seq=self.seq)
        os.makedirs(self.dir, exist_ok=True)
        tmp = os.path.join(self.dir, "request.json.tmp")
        with io.open(tmp, "w", encoding="utf-8", newline="\n") as f:
            json.dump(body, f, indent=1)
        os.replace(tmp, os.path.join(self.dir, "request.json"))

    def read(self):
        try:
            with io.open(os.path.join(self.dir, "status.json"), encoding="utf-8") as f:
                self.status = json.load(f)
        except (OSError, ValueError):
            pass
        return self.status

    async def wait(self, states, timeout_s, what):
        """Until the bridge has answered this request with one of states, or the time is up."""
        began = time.monotonic()
        said = 0.0
        while True:
            s = self.read()
            if int(s.get("seq", -1)) == self.seq and s.get("state") in states:
                return s
            waited = time.monotonic() - began
            if waited > timeout_s:
                return None
            if waited - said >= 15.0:
                said = waited
                print("lidar     %s (%.0f s; the bridge says: %s)"
                      % (what, waited, s.get("state", "nothing yet")), flush=True)
            await asyncio.sleep(0.5)

    async def start(self, drone, run_id, mount):
        self._request({"action": "start", "drone": drone, "run_id": run_id, "mount": mount,
                       "out_root": os.path.join(self.saved, "OusterSim", run_id),
                       "project_lighting": True})
        s = await self.wait(("recording", "failed"), LIDAR_START_WAIT_S, "waiting to start")
        if s is None:
            print("warning:  the lidar did not start: nothing answered in %s. Is the MAirLidar "
                  "plugin in the project, and the editor in Play or a release running?"
                  % self.dir, flush=True)
        elif s["state"] == "failed":
            print("warning:  the lidar did not start: %s" % s.get("message"), flush=True)
        else:
            print("lidar     recording on %s into %s" % (drone, s.get("out_root")), flush=True)
        return s is not None and s.get("state") == "recording"

    async def stop(self):
        self._request({"action": "stop"})
        s = await self.wait(("stopped", "failed", "idle"), LIDAR_STOP_WAIT_S, "finishing")
        s = s or self.read()
        print("lidar     %s scans written (%s incomplete) in %d part(s) under %s"
              % (s.get("scans_written", 0), s.get("scans_incomplete", 0),
                 len(s.get("segments", [])), s.get("out_root")), flush=True)
        return s


async def contingency(drone, operation, settings, speed, terrain, sim):
    """Do what the mission said to do when it can no longer do what it declared.

    A new command preempts the one in flight on the controller, so the route's move is simply
    replaced. That is how the controller is documented to behave; it has not been watched
    happening against a live simulator from here."""
    action = settings.contingency
    print("CONTINGENCY %s: %s" % (action, operation.contingency_reason), flush=True)
    if action == "hold":
        await command(lambda: drone.hover_async(), "hover")
        print("holding for %.0f s, then landing" % HOLD_BEFORE_LAND_S, flush=True)
        await asyncio.sleep(HOLD_BEFORE_LAND_S)
    elif action == "home":
        # go_home's own default is 0.5 m/s, which is a walk; the route's own pace is used instead.
        await command(lambda: drone.go_home_async(timeout_sec=600, velocity=max(2.0, speed)), "home")
    await come_down(drone, terrain, sim)
    operation.end("contingency %s completed: landed" % action)


async def fly(mission, legs, args, scripts, terrain, intent):
    from projectairsim import Drone, ProjectAirSimClient, World

    if getattr(args, "mcity", None):
        set_mcity_view(args.mcity)
    sim_config, scene_name = stage_scene(mission, scripts, terrain, lidar=getattr(args, "lidar", False),
                                         robot=chosen_robot(mission, args))
    client = ProjectAirSimClient(address=args.address)
    dataset = None
    operation = None
    operation_log = None
    lidar = None
    try:
        client.connect()
        world = World(client, scene_name, delay_after_load_sec=2, sim_config_path=sim_config)
        drone = Drone(client, world, mission.drone)
        held = await catch_at_start(world, drone, intent.spawn_ned)
        drone_class = rec.label_drone(world, mission.drone)
        if drone_class is None:
            print("note: the drone could not be given its segmentation class", flush=True)

        config, scene = rec.robot_config(world, mission.drone)
        facts = rec.sensor_facts(config)
        available = {name: sorted(streams) for name, streams in drone.sensors.items()}
        if args.list_capabilities:
            print(json.dumps(capabilities(drone, facts), indent=2))
            return
        client.subscribe(drone.robot_info["collision_info"], collision_reporter())
        print("sensors   " + (", ".join("%s (%s)" % (n, ", ".join(t)) for n, t in
                                        available.items())
                              or "none declared by the robot config"))

        images, data, warnings = choose(args, available, drone.robot_info.keys(),
                                        {n: f.get("enabled", True) for n, f in facts.items()})
        for w in warnings:
            print("warning:  %s" % w)

        out_dir = args.out or os.path.join(os.path.dirname(os.path.abspath(args.mission)),
                                           "flights", time.strftime("%Y%m%d-%H%M%S"))
        dataset = rec.Dataset(out_dir, mission, args.mission, terrain)
        dataset.robot, dataset.scene_config = config, scene

        for sensor, stream in images:
            s = dataset.image(sensor, stream, video=args.video, frames=args.frames, fps=args.fps)
            if s:
                print("record    %s/%s" % (sensor, stream))
                client.subscribe(drone.sensors[sensor][stream], s.frame)

        for sensor, stream in data:
            topic = (drone.robot_info.get(stream) if sensor == ROBOT_STATE
                     else drone.sensors.get(sensor, {}).get(stream))
            if not topic:
                print("warning:  %s/%s has no topic" % (sensor, stream))
                continue
            s = dataset.data_stream(sensor, stream, hz=args.sensor_hz)
            if s:
                print("log       %s/%s%s" % (sensor, stream,
                                             "" if not args.sensor_hz
                                             else " at up to %.1f Hz" % args.sensor_hz))
                client.subscribe(topic, s.message)

        # THE OPERATION. Every change of state goes three places: a line the planner reads,
        # a line in the flight folder, and a line a person reads.
        operation_log = io.open(os.path.join(out_dir, "operation.jsonl"), "w", encoding="utf-8",
                                newline="\n", buffering=1)

        def announce(change):
            operation_log.write(json.dumps(change) + "\n")
            print("STATE " + json.dumps(change), flush=True)
            print("state     %s to %s: %s" % (change["from"], change["to"], change["reason"]),
                  flush=True)

        operation = airspace.Operation(intent, on_change=announce)
        with io.open(os.path.join(out_dir, "intent.json"), "w", encoding="utf-8",
                     newline="\n") as f:
            # F3548 heights are WGS84 ellipsoidal. With the geoid installed they are converted;
            # without it they are written in NAVD88 and labelled so, never mislabelled W84.
            to_ellipsoid = None
            try:
                import geoid as geoid_module
                to_ellipsoid = geoid_module.Geoid.default().to_ellipsoid
            except Exception:
                pass
            json.dump({"intent": intent.as_dict(), "geojson": intent.geojson(),
                       "f3548_volumes": intent.to_f3548(to_ellipsoid=to_ellipsoid)}, f, indent=1)
        clashes = strategic_check(intent, mission, terrain, args)
        if clashes and not args.force:
            operation.reject(clashes)
            sys.exit("the operation was rejected: %s. --force flies it anyway."
                     % "; ".join(clashes))
        operation.accept("forced past: " + "; ".join(clashes) if clashes else "no conflicts")

        sim = SimClock()

        def observe(north, east, down, sim_ns=None):
            sim.report((north, east, down), sim_ns)
            return operation.observe(north, east, down, sim_ns=sim_ns).as_dict()

        if args.track:
            planned = [(n, e, d) for _, n, e, d, _ in legs]
            tracker = dataset.tracker(planned, deviation, args.track_hz, observer=observe)
            client.subscribe(drone.robot_info["actual_pose"], tracker.pose)
            print("track     the flown path, its deviation, and conformance to the declared "
                  "volumes")
        else:
            # Conformance needs the pose whether or not anything is being recorded.
            def pose_only(_topic, message):
                try:
                    p = message["position"]
                    observe(float(p["x"]), float(p["y"]), float(p["z"]), message.get("time_stamp"))
                except (KeyError, TypeError, ValueError):
                    pass
            client.subscribe(drone.robot_info["actual_pose"], pose_only)

        print("recording to %s" % out_dir)

        # No takeoff: the drone has been holding at the mission's start since the scene loaded,
        # and the route leaves from there.
        if getattr(args, "lidar", False):
            saved = project_saved_dir()
            if saved is None:
                print("warning:  no Unreal project found above this plugin, so no lidar; set "
                      "MAIR_PROJECT_SAVED to its Saved folder", flush=True)
            else:
                lidar = LidarLink(saved)
                await lidar.start(mission.drone, os.path.basename(out_dir),
                                  mission.lidar_mount or DEFAULT_LIDAR_MOUNT)

        print("departing from the start", flush=True)
        operation.activate("departing from the start")

        # WHICH WAY THE AIRCRAFT POINTS, AND SO WHERE ITS CAMERAS LOOK.
        #
        # The controller's own default is MaxDegreeOfFreedom with a yaw RATE of zero, which means
        # "do not turn": take off facing north, fly east, and every camera films sideways. So:
        #
        #   forward   ForwardOnly, which turns the nose along the velocity vector, so the view is
        #             always of what is coming. This is the default here.
        #   waypoint  hold a fixed heading down the leg, aimed at the waypoint being flown to, and
        #             keep it while holding there. Steadier for inspection shots.
        #   free      the controller's default, for a mission that sets its own heading elsewhere.
        #
        # In either of the first two, a leg that is straight up or down keeps the heading it has
        # (VERTICAL_LEG_M), and the next leg turns it.
        from projectairsim.drone import YawControlMode

        def floor_down(north, east):
            """The lowest a move may go at a point: START_CLEARANCE_M above the landscape."""
            lon, lat = terrain.lonlat_from_ned(north, east)
            ground = terrain.ground_elevation(lon, lat)
            if ground is None:
                return float("inf")
            return terrain.ned(lon, lat, ground + START_CLEARANCE_M)[2]

        async def fly_route():
            previous_ned = None
            for i, (w, north, east, down, elev) in enumerate(legs, 1):
                here = (north, east)
                # Every waypoint is flown, the first one from the mission's start: the drone is
                # already holding in the air there (catch_at_start), with no takeoff in between.
                # A first waypoint at the start is a move of nothing, which the controller finishes
                # at once while it goes on holding.
                start = previous_ned or (held if i == 1 else None)
                vertical = (start is not None
                            and math.hypot(north - start[0], east - start[1]) < VERTICAL_LEG_M)
                mode, is_rate, yaw, facing = YawControlMode.MaxDegreeOfFreedom, True, 0.0, ""
                if args.yaw in ("forward", "waypoint") and vertical:
                    facing = "  straight %s, keeping its heading" % ("up" if down < start[2] else "down")
                elif args.yaw == "forward":
                    mode, is_rate, yaw = YawControlMode.ForwardOnly, False, 0.0
                    facing = "  nose along the track"
                elif args.yaw == "waypoint":
                    # Aim down the leg being flown, from wherever it starts (on the first leg, the
                    # mission's start, where the drone is holding).
                    leg = (start, here) if start else None
                    if leg:
                        yaw, is_rate = heading_to(*leg), False
                        facing = "  facing %.0f deg" % (math.degrees(yaw) % 360.0)
                print("LEG %d %s" % (i - 1, w.name), flush=True)
                print("%d/%d  %-14s north %.1f east %.1f down %.1f  at %.1f m/s%s"
                      % (i, len(legs), w.name, north, east, down, w.speed, facing), flush=True)
                # The departure is one volume from the spawn's height to the first waypoint's, so
                # only the legs after it are flown in steps of height (see pieces_of).
                speed_ms = effective_speed(w)
                budget = command_budget_s(sim.speed())
                targets = pieces_of(start, (north, east, down), speed_ms, budget,
                                    intent.settings.vertical_m if i > 1 else None)
                for k, (n, e, d) in enumerate(targets, 1):
                    if len(targets) > 1:
                        print("      part %d of %d" % (k, len(targets)), flush=True)
                    # Never into the ground: a waypoint on it (the last, where it lands) is flown
                    # to START_CLEARANCE_M above it, and the landing touches down from there.
                    d = min(d, floor_down(n, e))
                    # At most what the controller flies (flightplan.MAX_CONTROLLER_SPEED_MS): the
                    # airport mission asked for 200 m/s on every leg and climbed hundreds of metres
                    # off its route each time, at full simulator speed as well as slow.
                    await command(lambda n=n, e=e, d=d: drone.move_to_position_async(
                        north=n, east=e, down=d, velocity=speed_ms, yaw_control_mode=mode,
                        yaw_is_rate=is_rate, yaw=yaw), "%s part %d" % (w.name, k))
                previous_ned = (north, east, down)
                if w.hold_s > 0:
                    print("      holding %.1f s" % w.hold_s, flush=True)
                    await asyncio.sleep(w.hold_s)

        async def monitor():
            """Beside the route: watch for silence, and stop the route on a contingency.

            The route cannot do this itself, because it spends most of its time inside one long
            await on a move. A second task can see the state change and cancel that await."""
            while True:
                operation.watch_telemetry()
                if operation.state == "Contingent" and intent.settings.contingency != "continue":
                    return
                if operation.state in ("Ended", "Cancelled"):
                    return
                await asyncio.sleep(0.5)

        route = asyncio.create_task(fly_route())
        watch = asyncio.create_task(monitor())
        done, _pending = await asyncio.wait({route, watch}, return_when=asyncio.FIRST_COMPLETED)
        if watch in done and route not in done:
            route.cancel()
            try:
                await route
            except asyncio.CancelledError:
                pass
            await contingency(drone, operation, intent.settings,
                              max((effective_speed(w) for w, *_ in legs), default=5.0), terrain, sim)
        else:
            watch.cancel()
            route.result()               # a route that failed raises here rather than vanishing
            if mission.land_at_end:
                await come_down(drone, terrain, sim)
            operation.end("mission complete")
        drone.disarm()
        drone.disable_api_control()
        print("mission complete" if operation.contingency_reason is None
              else "mission ended by contingency: %s" % operation.contingency_reason)
    finally:
        if operation is not None and operation.state in airspace.LIVE:
            # Still live on the way out means it was stopped from outside: Stop, Ctrl-C, a crash.
            # The aircraft is wherever it was, and the record should say so rather than pretend.
            operation.cancel("stopped before it finished")
        if operation_log is not None:
            operation_log.close()
        lidar_status = None
        if lidar is not None:
            try:
                lidar_status = await lidar.stop()
            except Exception as e:
                print("warning:  the lidar could not be stopped cleanly: %s" % e, flush=True)
        if dataset is not None:
            for line in dataset.close({"flown": {"yaw_mode": args.yaw,
                                                 "legs": [{"name": w.name, "lon": w.lon,
                                                           "lat": w.lat, "height": w.height,
                                                           "reference": w.reference,
                                                           "speed": w.speed, "hold_s": w.hold_s,
                                                           "north": n, "east": e, "down": d,
                                                           "elevation_m": elev}
                                                          for w, n, e, d, elev in legs]},
                                       "operation": None if operation is None
                                       else operation.summary(),
                                       "lidar": lidar_status,
                                       "switches": {k: v for k, v in sorted(vars(args).items())
                                                    if k not in ("mission", "clone", "out")}}):
                print(line)
        try:
            client.unsubscribe_all()
        except Exception:
            pass
        try:
            client.disconnect()
        except Exception:
            pass


def wind_up_on_signal():
    """Turn a stop into something Python can catch, so the recording gets closed properly.

    A flight is stopped far more often than it is allowed to finish: the button in the planner,
    Ctrl-C in a terminal, the editor being closed. A process that is simply terminated leaves an
    MP4 with no index, which no player will open, and loses whatever was still in a buffer.
    SIGINT already raises KeyboardInterrupt; this adds the rest where they exist."""
    def stop(_signum, _frame):
        raise KeyboardInterrupt()

    for name in ("SIGTERM", "SIGBREAK", "SIGHUP"):
        number = getattr(signal, name, None)
        if number is not None:
            try:
                signal.signal(number, stop)
            except (ValueError, OSError):
                pass


def stop_when_told(task):
    """Cancel the flight when a line arrives on stdin, or when stdin closes.

    WHY NOT A SIGNAL. On Windows a console control event only reaches processes that share the
    sender's console, and a tool started with CREATE_NO_WINDOW has its own, so Ctrl-Break sent by
    the planner is silently discarded. Tested: the flight ran straight through the grace period
    and had to be killed, which is the thing this is all meant to avoid. A line on stdin arrives
    on any platform and needs no console at all.

    Cancelling the task rather than raising means the flight stops at its next await, and fly()
    closes the recording in its finally block on the way out."""
    loop = asyncio.get_running_loop()

    def wait():
        try:
            sys.stdin.readline()          # a line, or "" at end of file: either means wind up
        except Exception:
            return
        loop.call_soon_threadsafe(task.cancel)

    threading.Thread(target=wait, daemon=True).start()


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("mission", help="a mission JSON written by the flight planner")
    ap.add_argument("--clone", default=DEFAULT_CLONE, help="the Project AirSim checkout")
    ap.add_argument("--address", default="127.0.0.1")
    ap.add_argument("--dry-run", action="store_true",
                    help="resolve and print the flight without connecting to anything")
    ap.add_argument("--list-capabilities", action="store_true",
                    help="print the drone's sensors as JSON and stop")
    ap.add_argument("--out", help="where the track and recordings go (default: flights/<time>)")
    ap.add_argument("--track", dest="track", action="store_true", default=True,
                    help="record the flown path and its deviation (on by default)")
    ap.add_argument("--no-track", dest="track", action="store_false")
    ap.add_argument("--track-hz", type=float, default=4.0, help="how often to report position")
    ap.add_argument("--mcity", choices=("scan", "twin"),
                    help="show M-City as the photogrammetric scan or as Mcity's digital twin for this "
                         "flight (the level's MAirMcityView switch; default: leave it as it is)")
    ap.add_argument("--robot", metavar="CONFIG",
                    help="fly as this aircraft: a robot config in AirSim/sim_config, by file name or by the "
                         "built drone's name (drone_quad_industrial is robot_drone_quad_industrial.jsonc); "
                         "default: the mission's robot_config, else the one the scene names")
    ap.add_argument("--lidar", action="store_true",
                    help="record the simulated Ouster OS-1-256-RGB lidar for the whole flight "
                         "(needs the OusterSim and MAirLidar plugins; 25.6 MB a scan, 5 scans a second)")
    ap.add_argument("--all", action="store_true",
                    help="record everything the drone carries: every camera as video, every "
                         "sensor and the aircraft's own state as data")
    ap.add_argument("--record-all", action="store_true", help="every camera stream")
    ap.add_argument("--log-all", action="store_true",
                    help="every sensor stream, camera metadata and robot state")
    ap.add_argument("--record", action="append", default=[], metavar="CAMERA[:TYPE]",
                    help="save one camera stream, or all of one camera's streams; repeatable")
    ap.add_argument("--video", dest="video", action="store_true", default=True,
                    help="write video, which is the default for eight bit streams")
    ap.add_argument("--no-video", dest="video", action="store_false")
    ap.add_argument("--frames", action="store_true",
                    help="also write every frame losslessly, which is what training wants; "
                         "sixteen bit depth is always written this way and never as video")
    ap.add_argument("--fps", type=float, default=10.0, help="frame rate to write video at")
    ap.add_argument("--log-sensor", action="append", default=[], metavar="NAME[:STREAM]",
                    help="write a sensor's messages to a file; repeatable")
    ap.add_argument("--sensor-hz", type=float, default=0.0,
                    help="cap a data stream's rate; the default of 0 keeps every message")
    ap.add_argument("--lateral", type=float, metavar="M",
                    help="declare this much room either side of the route (default: the "
                         "mission's, else 30 m)")
    ap.add_argument("--vertical", type=float, metavar="M",
                    help="and this much above and below it (default: the mission's, else 20 m)")
    ap.add_argument("--contingency", choices=list(airspace.CONTINGENCIES),
                    help="what to do once the operation is contingent (default: the mission's, "
                         "else hold, then land)")
    ap.add_argument("--nonconforming-timeout", type=float, metavar="S",
                    help="seconds outside the declared volumes before that is a contingency")
    ap.add_argument("--geofences", help="another folder or file of GeoJSON fences to check "
                                         "against, beside Tools/geofences")
    ap.add_argument("--force", action="store_true",
                    help="fly an operation the strategic check rejected")
    ap.add_argument("--stop-on-stdin", action="store_true",
                    help="stop the flight when a line arrives on stdin, which is how a window "
                         "asks for it: the recording is closed properly on the way out")
    ap.add_argument("--yaw", choices=list(YAW_MODES),
                    help="which way the aircraft points, and so where its cameras look: along the "
                         "direction of travel, at the waypoint being flown to, or left alone "
                         "(default: what the mission says)")
    args = ap.parse_args()
    wind_up_on_signal()

    # run.cmd can be started from the project root as well as from here, so a mission named
    # without a folder that is not where it was run from is looked for in missions/, the planner's.
    if not os.path.isfile(args.mission):
        for name in (args.mission, args.mission + ".json"):
            candidate = os.path.join(HERE, "missions", name)
            if os.path.isfile(candidate):
                args.mission = candidate
                break

    mission = Mission.load(args.mission)
    terrain = Terrain(mission.plan)
    args.yaw = args.yaw or getattr(mission, "yaw_mode", YAW_MODES[0])
    if args.yaw not in YAW_MODES:
        # A mission edited by hand can say anything. check() below reports it; fly anyway.
        args.yaw = YAW_MODES[0]
    print("mission   %s (%d waypoints)" % (mission.name, len(mission.waypoints)))
    print("landscape %s" % terrain.path)
    print("scene     %s, drone %s" % (mission.scene, mission.drone))
    print("facing    %s\n" % {"forward": "the direction of travel",
                              "waypoint": "the waypoint being flown to",
                              "free": "whatever heading it already has"}[args.yaw])

    for p in mission.check(terrain):
        print("warning:  %s" % p)

    legs = resolve(mission, terrain, show=not args.list_capabilities, yaw_mode=args.yaw)
    try:
        intent = build_intent(mission, terrain, args)
    except ValueError as e:
        sys.exit(str(e))
    if not args.list_capabilities:
        st = intent.settings
        print("\ndeclared  %d volumes, %.0f m across and %.0f m up and down from the route, "
              "about %.0f s including slack" % (len(intent.volumes), st.lateral_m, st.vertical_m,
                                                intent.duration_s))
        print("contingency %s after %.0f s outside, or %.0f s with no position report"
              % (st.contingency, st.nonconforming_timeout_s, st.telemetry_stale_s))
        if args.dry_run:
            print("\n" + intent.table())
            clashes = strategic_check(intent, mission, terrain, args)
            print("\n" + ("REJECTED: " + "; ".join(clashes) if clashes
                          else "strategic check: nothing in the way"))
    if args.dry_run:
        preview(mission, args)
        return
    if not legs:
        sys.exit("nothing to fly")

    src, scripts = client_paths(args.clone)
    if src:
        sys.path.insert(0, src)
    if not args.list_capabilities:
        print("\nconnecting to %s (the editor must already be in Play)\n" % args.address)
    async def flight():
        if args.stop_on_stdin:
            stop_when_told(asyncio.current_task())
        await fly(mission, legs, args, scripts, terrain, intent)

    try:
        asyncio.run(flight())
    except (KeyboardInterrupt, asyncio.CancelledError):
        # fly() closes the recording in its finally block before this lands here.
        print("\nstopped. the recording was closed properly.")


if __name__ == "__main__":
    main()
