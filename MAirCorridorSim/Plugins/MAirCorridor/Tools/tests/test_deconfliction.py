"""test_deconfliction.py - the strategic check, against fences and against other operations.

    py -3.10 tests/test_deconfliction.py          (from Tools; pytest runs it too)

Every case builds its fences and missions in memory against the real landscape plan, so nothing
in Tools/geofences or Tools/missions is touched. Skipped when the plan is not on this machine.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

import airspace                                                             # noqa: E402
import geofences as G                                                       # noqa: E402
from flightplan import DEFAULT_PLAN, Mission, Terrain, Waypoint             # noqa: E402
from shapely.geometry import Polygon                                        # noqa: E402

ROUTE = [("A", -83.6990, 42.2995), ("B", -83.6975, 42.2995), ("C", -83.6975, 42.3005)]


def mission(name="m", start=None, shift_lat=0.0):
    m = Mission(name=name)
    if start:
        m.intent = {"planned_start": start}
    for wname, lon, lat in ROUTE:
        m.waypoints.append(Waypoint(wname, lon, lat + shift_lat, 40.0, "agl", 15.0))
    return m


def fence_over_route(terrain, **kw):
    """A box around the middle of the route, in the same projected frame the check uses."""
    west, east, south, north = -83.6985, -83.6970, 42.2990, 42.3000
    ring = [(west, south), (east, south), (east, north), (west, north), (west, south)]
    shape = Polygon([terrain.to_projected(lon, lat) for lon, lat in ring])
    return G.Geofence(kw.pop("name", "test fence"), shape, ring=ring, **kw)


def run():
    if not os.path.isfile(DEFAULT_PLAN):
        print("skipped: no landscape plan at %s" % DEFAULT_PLAN)
        return 0
    terrain = Terrain()
    m = mission()
    intent = airspace.OperationalIntent.from_mission(m, terrain)
    cases = []

    def case(label, result, want_rejected, want_advisory=False, want_unknown=False):
        ok = (bool(result.rejections) == want_rejected and
              bool(result.advisories) == want_advisory and bool(result.unknown) == want_unknown)
        detail = (result.rejections or result.advisories or result.unknown or ["clear"])[0]
        cases.append(ok)
        print("%-44s %s  %s" % (label, "PASS" if ok else "FAIL", detail[:90]))

    case("no-fly fence across the route", G.check(intent, m, terrain,
         fences=[fence_over_route(terrain)]), True)
    case("same fence, advisory", G.check(intent, m, terrain,
         fences=[fence_over_route(terrain, severity="advisory")]), False, want_advisory=True)
    case("same fence, but 600 m AGL and up", G.check(intent, m, terrain,
         fences=[fence_over_route(terrain, lower=600.0)]), False)
    case("same fence, but only in 2030", G.check(intent, m, terrain, start_epoch=G.parse_time(
         "2026-10-04T12:00:00Z"), fences=[fence_over_route(
             terrain, start="2030-01-01T00:00:00Z", end="2030-01-02T00:00:00Z")]), False)
    case("same fence in W84 with no geoid model", G.check(intent, m, terrain,
         fences=[fence_over_route(terrain, reference="w84", lower=0, upper=500)]), False,
         want_unknown=True)
    try:
        import geoid as geoid_module
        model = geoid_module.Geoid.default()
    except Exception:
        model = None
    if model is not None:
        # The route flies at about 300 to 380 m NAVD88, which is about 266 to 346 m W84 here.
        case("W84 fence 0 to 500 m, with the geoid", G.check(intent, m, terrain,
             fences=[fence_over_route(terrain, reference="w84", lower=0, upper=500)],
             geoid=model), True)
        case("W84 fence 0 to 200 m, with the geoid", G.check(intent, m, terrain,
             fences=[fence_over_route(terrain, reference="w84", lower=0, upper=200)],
             geoid=model), False)
    else:
        print("%-44s skipped: geoid model not installed (py -3.10 geoid.py --fetch)"
              % "W84 fences with the geoid")
    case("the example airport fence, 8 km away", G.check(intent, m, terrain,
         fences=G.load_geofences(terrain)), False)

    # Two scheduled operations on the same route.
    noon = "2026-10-04T12:00:00Z"
    a = mission("first", start=noon)
    a_intent = airspace.OperationalIntent.from_mission(a, terrain)
    b = mission("second", start=noon)
    b_intent = airspace.OperationalIntent.from_mission(b, terrain)
    others = [("first", a_intent, G.parse_time(noon))]
    case("second operation, same route, same time", G.check(
        b_intent, b, terrain, start_epoch=G.parse_time(noon), other_missions=others), True)
    case("second operation, same route, an hour later", G.check(
        b_intent, b, terrain, start_epoch=G.parse_time("2026-10-04T13:00:00Z"),
        other_missions=others), False)
    c = mission("third", shift_lat=0.01)          # about a kilometre north
    c_intent = airspace.OperationalIntent.from_mission(c, terrain)
    case("third operation, 1 km away, same time", G.check(
        c_intent, c, terrain, start_epoch=G.parse_time(noon), other_missions=others), False)

    # An ED-269 zone in feet, as a circle, converted and read back.
    zone = {"features": [{"identifier": "TEST1", "name": "test zone", "restriction": "PROHIBITED",
                          "applicability": [{"permanent": "YES"}],
                          "geometry": [{"uomDimensions": "FT", "lowerLimit": 0,
                                        "lowerVerticalReference": "AGL", "upperLimit": 400,
                                        "upperVerticalReference": "AGL",
                                        "horizontalProjection": {"type": "Circle",
                                                                 "center": [-83.698, 42.2995],
                                                                 "radius": 500}}]}]}
    feature = G.ed269_to_geojson(zone)["features"][0]
    props = feature["properties"]
    ed_ok = (props["severity"] == "no-fly" and abs(props["upper_m"] - 121.92) < 0.01 and
             len(feature["geometry"]["coordinates"][0]) == 65)
    cases.append(ed_ok)
    print("%-44s %s  %s, upper %.2f m from 400 ft, %d vertices"
          % ("ED-269 circle in feet, converted", "PASS" if ed_ok else "FAIL",
             props["severity"], props["upper_m"], len(feature["geometry"]["coordinates"][0])))

    failed = cases.count(False)
    print("\n%s" % ("all passed" if not failed else "%d failed" % failed))
    return failed


def test_deconfliction():
    assert run() == 0


if __name__ == "__main__":
    sys.exit(1 if run() else 0)
