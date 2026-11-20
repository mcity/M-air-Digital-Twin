"""test_feed_health.py - a failed request is not an empty sky.

    py -3.10 tests/test_feed_health.py          (from Tools; pytest runs it too)

A stand-in for the OpenSky API answers twice and then fails every time. The feed must keep the
last good aircraft rather than replacing them with none, and its health must go from healthy to
degraded to stale, with the reason, so nothing downstream reads a broken feed as a clear sky.
No network is used. Skipped when the landscape plan is not on this machine.
"""
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

import adsb                                                                 # noqa: E402
from flightplan import DEFAULT_PLAN, Terrain                                # noqa: E402


class FailsAfterTwo:
    """Answers twice with one aircraft, then returns what a failed request returns."""

    def __init__(self, *args, **kwargs):
        self.calls = 0
        self.credits_left = 3990
        self.last_error = None
        self.set = None

    def states(self, box):
        self.calls += 1
        if self.calls <= 2:
            return [adsb.Aircraft(icao24="abc123", callsign="TEST1", lon=-83.70, lat=42.30,
                                  geo_m=600.0, speed_ms=60.0, track_deg=90.0, climb_ms=0.0,
                                  last_contact=time.time(), seen_at=time.time())], 1234
        self.last_error = "HTTP 503 from the states endpoint"
        return [], None


def run():
    if not os.path.isfile(DEFAULT_PLAN):
        print("skipped: no landscape plan at %s" % DEFAULT_PLAN)
        return 0
    real_client, real_stale = adsb.OpenSky, adsb.STALE_AFTER_S
    adsb.OpenSky = FailsAfterTwo
    adsb.STALE_AFTER_S = 1.2
    try:
        feed = adsb.Feed(Terrain(), interval=adsb.INTERVAL_FLOOR)
        feed.interval = 0.2                   # the floor is for the network, not for a stand-in
        feed.health.interval = 0.2
        feed.start()
        seen, kept = [], []
        for _ in range(16):
            time.sleep(0.15)
            seen.append(feed.status()["state"])
            kept.append(len(feed.now()))
        feed.stop()
    finally:
        adsb.OpenSky, adsb.STALE_AFTER_S = real_client, real_stale

    order = []
    for state in seen:
        if not order or order[-1] != state:
            order.append(state)
    results = [
        ("went healthy, then degraded, then stale", order == ["healthy", "degraded", "stale"],
         " > ".join(order)),
        ("kept the aircraft through every failure", min(kept) == 1,
         "aircraft held: %s" % sorted(set(kept))),
        ("never told anyone to trust an empty sky once failing",
         seen[-1] != "healthy", "last state %s" % seen[-1]),
    ]
    for label, ok, detail in results:
        print("%-52s %s  %s" % (label, "PASS" if ok else "FAIL", detail))
    failed = [ok for _l, ok, _d in results].count(False)
    print("\n%s" % ("all passed" if not failed else "%d failed" % failed))
    return failed


def test_feed_health():
    assert run() == 0


if __name__ == "__main__":
    sys.exit(1 if run() else 0)
