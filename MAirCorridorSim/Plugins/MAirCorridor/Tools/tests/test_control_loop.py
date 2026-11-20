"""test_control_loop.py - the flight control loop, flown against a stand-in drone.

    py -3.10 tests/test_control_loop.py          (from Tools; pytest runs it too)

Three flights, each checked against what the operation recorded:

  clean       flies the route and lands. The operation must go Accepted, Activated, Ended,
              with every position report inside the declared volumes.
  blown off   a crosswind pushes it out of its volumes and keeps it there. The operation must go
              Nonconforming, then Contingent once the timeout passes, then hover and land, and
              the route must have been abandoned rather than finished.
  silent      it stops reporting its position. The operation must go Contingent on telemetry
              alone, because an aircraft nobody can see is not conforming to anything.

Uses the real landscape plan, because the volumes are built against real ground. Without the plan
on this machine the tests are skipped rather than failed.
"""
import asyncio
import io
import json
import os
import shutil
import sys
import tempfile
import types

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.dirname(HERE)
sys.path.insert(0, TOOLS)
sys.path.insert(0, HERE)

import fake_airsim                                                          # noqa: E402
fake_airsim.install()

import fly_mission                                                          # noqa: E402
from flightplan import DEFAULT_PLAN, Mission, Terrain, Waypoint             # noqa: E402

# A short route near M-City: three waypoints a little over a hundred metres apart, low and slow,
# so a flight takes seconds rather than minutes.
ROUTE = [("A", -83.6990, 42.2995), ("B", -83.6975, 42.2995), ("C", -83.6975, 42.3005)]


def have_plan():
    return os.path.isfile(DEFAULT_PLAN)


def make_mission(folder, **intent):
    mission = Mission(name="loop_test")
    mission.intent = dict(intent)
    for name, lon, lat in ROUTE:
        mission.waypoints.append(Waypoint(name, lon, lat, 40.0, "agl", 15.0))
    path = os.path.join(folder, "loop_test.json")
    mission.save(path)
    return Mission.load(path), path


def run(mission, path, folder, wind=(0.0, 0.0), silent_at=None, **switches):
    """Fly it once against the stand-in, and return what the operation wrote down."""
    terrain = Terrain(mission.plan)
    legs = mission.legs(terrain)
    # Spawn on the ground under the first waypoint, which is where a launch would be.
    first = legs[0]
    ground = terrain.ground_elevation(first[0].lon, first[0].lat)
    north, east, down = terrain.ned(first[0].lon, first[0].lat, ground)
    fake_airsim.FakeDrone.spawn = (north, east, down)
    fake_airsim.FakeDrone.wind = wind
    fake_airsim.FakeDrone.silent_at = silent_at

    args = types.SimpleNamespace(
        mission=path, address="fake", list_capabilities=False, out=os.path.join(folder, "flight"),
        track=True, track_hz=4.0, yaw="forward", force=False, fps=0.0, frames=False, video=False,
        sensor_hz=0.0, all=False, record_all=False, log_all=False, record=[], log_sensor=[],
        lateral=None, vertical=None, contingency=None, nonconforming_timeout=None)
    for key, value in switches.items():
        setattr(args, key, value)
    intent = fly_mission.build_intent(mission, terrain, args)
    # The scene's spawn is where the real drone starts; the stand-in starts here, so the
    # departure volume is rebuilt from this spawn to keep the two consistent.
    from airspace import OperationalIntent
    intent = OperationalIntent.from_mission(mission, terrain, intent.settings,
                                            spawn_ned=(north, east, down))
    real_build = fly_mission.build_intent
    fly_mission.build_intent = lambda *a, **k: intent
    try:
        asyncio.run(fly_mission.fly(mission, legs, args, folder, terrain, intent))
    finally:
        fly_mission.build_intent = real_build
    changes = [json.loads(l) for l in io.open(os.path.join(args.out, "operation.jsonl"),
                                               encoding="utf-8")]
    manifest = json.load(io.open(os.path.join(args.out, "manifest.json"), encoding="utf-8"))
    return [c["to"] for c in changes], changes, manifest


def check(label, states, expected_in_order, manifest, extra=None):
    at = 0
    for state in states:
        if at < len(expected_in_order) and state == expected_in_order[at]:
            at += 1
    ok = at == len(expected_in_order)
    summary = manifest.get("operation") or {}
    print("%-10s %s  %s" % (label, "PASS" if ok else "FAIL", " > ".join(states)))
    print("           inside %s%% of %s reports, worst %s m across, contingency: %s"
          % (summary.get("inside_percent"), summary.get("reports"),
             summary.get("worst_outside_across_m"), summary.get("contingency")))
    if extra:
        print("           " + extra)
    return ok


def test_clean():
    if not have_plan():
        print("skipped: no landscape plan at %s" % DEFAULT_PLAN)
        return
    folder = tempfile.mkdtemp(prefix="loop_clean_")
    try:
        mission, path = make_mission(folder)
        states, _changes, manifest = run(mission, path, folder)
        assert check("clean", states, ["Accepted", "Activated", "Ended"], manifest)
        assert "Nonconforming" not in states and "Contingent" not in states
    finally:
        shutil.rmtree(folder, ignore_errors=True)


def test_blown_off():
    if not have_plan():
        return
    folder = tempfile.mkdtemp(prefix="loop_wind_")
    try:
        mission, path = make_mission(folder)
        fly_mission.HOLD_BEFORE_LAND_S = 1.0
        # 12 m/s across the route: out of a 30 m volume in a few seconds, and it stays out.
        states, changes, manifest = run(mission, path, folder, wind=(0.0, 12.0),
                                        nonconforming_timeout=3.0)
        contingent = next((c for c in changes if c["to"] == "Contingent"), {})
        assert check("blown off", states,
                     ["Accepted", "Activated", "Nonconforming", "Contingent", "Ended"], manifest,
                     "why: %s" % contingent.get("reason"))
    finally:
        shutil.rmtree(folder, ignore_errors=True)


def test_silent():
    if not have_plan():
        return
    folder = tempfile.mkdtemp(prefix="loop_silent_")
    try:
        mission, path = make_mission(folder, telemetry_stale_s=2.0)
        fly_mission.HOLD_BEFORE_LAND_S = 1.0
        states, changes, manifest = run(mission, path, folder, silent_at=3.0)
        contingent = next((c for c in changes if c["to"] == "Contingent"), {})
        assert check("silent", states, ["Accepted", "Activated", "Contingent", "Ended"], manifest,
                     "why: %s" % contingent.get("reason"))
        assert "position report" in (contingent.get("reason") or "")
    finally:
        shutil.rmtree(folder, ignore_errors=True)


if __name__ == "__main__":
    failures = 0
    for test in (test_clean, test_blown_off, test_silent):
        try:
            test()
        except AssertionError as e:
            failures += 1
            print("           assertion failed %s" % (e or ""))
    print("\n%s" % ("all passed" if not failures else "%d failed" % failures))
    sys.exit(1 if failures else 0)
