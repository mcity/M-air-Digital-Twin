"""test_geoid.py - the geoid answers from its grid, the right way round, or not at all.

    py -3.10 tests/test_geoid.py          (from Tools; pytest runs it too)

Skipped when the grid is not installed (py -3.10 geoid.py --fetch).
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

import geoid as G                                                           # noqa: E402


def run():
    try:
        model = G.Geoid.default()
    except G.GeoidUnavailable as e:
        print("skipped: %s" % e)
        return 0
    results = []

    def case(label, ok, detail):
        results.append(ok)
        print("%-46s %s  %s" % (label, "PASS" if ok else "FAIL", detail))

    n = model.separation(-83.6990, 42.2995)
    # GEOID18 puts the geoid about 34 m below the ellipsoid here. The sign is the point of this
    # test: it was written down backwards once, and a sign error is worth 68 m.
    case("separation at M-City is about -34 m", -35.0 < n < -33.0, "N = %.3f m" % n)
    h = model.to_ellipsoid(-83.6990, 42.2995, 300.0)
    case("orthometric 300 m is a SMALLER ellipsoidal height", h < 300.0, "h = %.2f m" % h)
    back = model.to_landscape(-83.6990, 42.2995, h)
    case("to the ellipsoid and back is exact", abs(back - 300.0) < 1e-6, "%.9f m" % back)
    try:
        model.separation(0.0, 51.5)
        case("London is refused, not answered", False, "it answered")
    except G.GeoidUnavailable as e:
        case("London is refused, not answered", True, str(e))
    near = [model.separation(-83.6990 + d, 42.2995) for d in (0.0, 0.0001)]
    case("eight metres apart, the separation barely moves", abs(near[0] - near[1]) < 0.01,
         "%.4f m change" % abs(near[0] - near[1]))
    failed = results.count(False)
    print("\n%s" % ("all passed" if not failed else "%d failed" % failed))
    return failed


def test_geoid():
    assert run() == 0


if __name__ == "__main__":
    sys.exit(1 if run() else 0)
