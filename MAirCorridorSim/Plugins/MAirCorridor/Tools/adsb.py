"""adsb.py - real aircraft overhead, from the OpenSky Network, in this landscape's own frame.

    py -3.10 adsb.py --once                       what is up there right now
    py -3.10 adsb.py --watch                      keep looking, one line per update
    py -3.10 adsb.py --watch --snapshot traffic.json      and leave a file for Unreal to read
    py -3.10 adsb.py --watch --record traffic.jsonl       keep the history
    py -3.10 adsb.py --replay traffic.jsonl              play that history back, no network
    py -3.10 adsb.py --check-credentials          try every credential, print none of them

WHAT THIS IS FOR. A flight planned over M-City shares the sky with real traffic: Detroit Metro is
twenty miles east and Ann Arbor municipal is three miles south, so there is usually something in
the box. This fetches those aircraft, puts them in the same frame as everything else here, and
hands them to the planner to draw and to the simulator to show.

CREDITS ARE THE REAL CONSTRAINT. An authenticated account gets 4000 credits a day and a bounded
request costs one, which is a request every 21.6 seconds sustained for a whole day. More than one
client can be listed in the credentials file, and CredentialSet moves between them: when one runs
out, when one is refused, or in turns. That is also how a secret gets replaced without a gap, which
is the other thing rotation is for. So the default
interval is twenty seconds, the remaining credits are read back from every response, and the gap
between aircraft updates is filled by DEAD RECKONING rather than by asking again: a state carries
a ground speed, a track and a vertical rate, which is enough to move an aircraft believably for
the twenty seconds until the truth arrives.

ALTITUDE NEEDS A DECISION, AND THE NUMBERS ARE LARGE. OpenSky reports barometric and geometric
altitude in metres. The geometric one is height above the WGS84 ELLIPSOID, while this landscape's
elevations come from USGS 3DEP, which measures from the NAVD88 geoid. Around Ann Arbor the geoid
sits about 34 m BELOW the ellipsoid (GEOID18 says 33.94 m at M-City), so an NAVD88 elevation is
the LARGER number. Each geometric altitude is converted with the geoid model at that aircraft's own
position (geoid.py). Only when the model is not installed does a constant +34 stand in, and the
feed says so. Barometric altitude is pressure altitude, not an ellipsoidal height, so it is never
geoid corrected; it is used only when there is no geometric one, and marked as such.

WHAT IT NEVER DOES. It does not pretend an aircraft is somewhere it has not been reported. Every
aircraft carries the age of its last position report, and one that has gone quiet for longer than
--forget seconds is dropped rather than flown onwards on faith.
"""
import argparse
import hashlib
import io
import json
import math
import os
import sys
import tempfile
import threading
import time

try:
    import requests
except ImportError:
    raise SystemExit("adsb needs requests: py -3.10 -m pip install -r requirements.txt")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from flightplan import DEFAULT_PLAN, Terrain, deviation                               # noqa: E402

from toolpaths import HERE                                                          # noqa: E402

TOKEN_URL = ("https://auth.opensky-network.org/auth/realms/opensky-network/protocol/"
             "openid-connect/token")
STATES_URL = "https://opensky-network.org/api/states/all"

# The order of an OpenSky state vector, which arrives as a bare list.
# https://openskynetwork.github.io/opensky-api/rest.html
FIELDS = ("icao24", "callsign", "origin_country", "time_position", "last_contact", "longitude",
          "latitude", "baro_altitude", "on_ground", "velocity", "true_track", "vertical_rate",
          "sensors", "geo_altitude", "squawk", "spi", "position_source", "category")

# WHAT KIND OF AIRCRAFT IT IS, which only arrives when the request asks for extended data. The
# numbers are the ADS-B emitter categories; the names are what a model gets assigned against, so
# they are deliberately few and about SIZE rather than about type. A state vector never says
# "Boeing 737": it says "large", and that is enough to pick a shape that looks right in the sky.
CATEGORY_CLASS = {
    0: "unknown", 1: "unknown",
    2: "light",            # under 15500 lb: the Cessnas that actually fly over M-City
    3: "small",            # 15500 to 75000 lb
    4: "large",            # 75000 to 300000 lb: most airliners
    5: "large",            # high vortex large, a 757 and the like
    6: "heavy",            # over 300000 lb
    7: "fast",             # high performance, over 5 g and 400 kt
    8: "rotorcraft",
    9: "glider",
    10: "balloon",         # lighter than air
    11: "parachutist",
    12: "ultralight",
    14: "uav",
    15: "spacecraft",
    16: "vehicle", 17: "vehicle",        # on the surface, not in the air
    18: "obstacle", 19: "obstacle", 20: "obstacle",
}

# Roughly how wide each class is, in metres. Used to scale a stand in shape so that a sphere
# standing for an airliner is airliner sized: a marker that ignores this reads as either a speck
# or a cathedral, and both are worse than a wrong shape of the right size.
CLASS_SPAN_M = {"unknown": 20.0, "light": 11.0, "small": 20.0, "large": 36.0, "heavy": 65.0,
                "fast": 14.0, "rotorcraft": 14.0, "glider": 15.0, "balloon": 12.0,
                "parachutist": 3.0, "ultralight": 10.0, "uav": 3.0, "spacecraft": 20.0,
                "vehicle": 6.0, "obstacle": 6.0}

# 4000 credits a day, one per bounded request, is a request every 21.6 seconds. Twenty is the
# default because it leaves a little room; below the floor is refused outright.
DEFAULT_INTERVAL = 20.0
INTERVAL_FLOOR = 5.0
DAILY_CREDITS = 4000.0

# The NAVD88 geoid sits about this far below the WGS84 ellipsoid around Ann Arbor, so this much
# has to be ADDED to an ellipsoidal altitude to compare it with this landscape's elevations.
GEOID_OFFSET_M = 34.0


def grid_convergence_deg(terrain, lon, lat):
    """How far grid north is from true north at a point, in degrees, positive east of north.

    A track from ADS-B is a TRUE bearing, and this landscape is drawn on a UTM grid, so the two
    differ by the convergence of the meridians: about 1.8 degrees at M-City, which is UTM zone 17
    seen from two and a half degrees west of its central meridian. Small, and still worth doing,
    because it costs one line and a wrong heading on an aircraft marker is the sort of thing that
    quietly undermines everything else on the screen.

    Only UTM is handled, which is what the landscape builder produces. Anything else gets zero,
    which is the honest answer when the projection is unknown rather than a guess at it."""
    try:
        epsg = int(getattr(terrain, "epsg", 0))
    except (TypeError, ValueError):
        return 0.0
    # EPSG:269xx and 326xx are UTM north zones; the zone number gives the central meridian.
    zone = None
    for base in (26900, 32600, 25800):
        if base < epsg < base + 61:
            zone = epsg - base
            break
    if not zone:
        return 0.0
    central = -183.0 + 6.0 * zone
    return math.degrees(math.atan(math.tan(math.radians(lon - central))
                                  * math.sin(math.radians(lat))))


def unreal_heading_deg(terrain, lon, lat, true_track_deg):
    """An Unreal yaw for an aircraft reporting a true track.

    Unreal +X is this landscape's grid EAST and Unreal +Y its grid SOUTH, because the landscape is
    laid out from its north west corner (see flightplan.py). So a grid bearing b points along
    (sin b, -cos b) and the yaw that matches it is b - 90."""
    if true_track_deg is None:
        return None
    grid = float(true_track_deg) + grid_convergence_deg(terrain, lon, lat)
    return (grid - 90.0) % 360.0


# How old the traffic picture may get before "nothing in the way" stops meaning anything. Four
# and a half polls at the default interval: long enough to ride out a slow response or two, short
# enough that an airliner has not crossed the landscape unseen.
STALE_AFTER_S = 90.0


class FeedHealth:
    """How fresh the traffic picture is, and whether to believe an empty one.

    THE DIFFERENCE THIS EXISTS FOR. A request that fails and a sky with nothing in it both come
    back as "no aircraft". The feed used to treat them the same: replace its aircraft with none,
    stamp the result fresh, and carry on. The planner then said "nothing too close" and the level
    cleared the sky, about a feed that had stopped working. So a failure now keeps the last good
    picture, which goes on ageing and being dead reckoned until it is forgotten, and this says
    how old it is and why.

    Modelled on the heartbeat and health reporting a surveillance data provider gives under
    ASTM F3623, which Flight Blender's surveillance service implements, cut down to what a
    single feed needs."""

    STATES = ("starting", "healthy", "degraded", "stale", "down")

    def __init__(self, interval):
        self.interval = float(interval)
        self.started = time.time()
        self.last_success = None
        self.failures = 0
        self.total_failures = 0
        self.last_error = None

    def success(self):
        self.last_success = time.time()
        self.failures = 0
        self.last_error = None

    def failure(self, why):
        self.failures += 1
        self.total_failures += 1
        self.last_error = why or "the request failed"

    def assess(self, credits_left=None, now=None):
        now = now or time.time()
        grace = 2.0 * self.interval + 5.0
        if self.last_success is None:
            waited = now - self.started
            if waited <= grace and self.failures < 3:
                state, why = "starting", "waiting for the first report"
            else:
                state, why = "down", "no report has ever arrived: %s" % (self.last_error or
                                                                         "no answer")
            age = None
        else:
            age = now - self.last_success
            if age > STALE_AFTER_S:
                state, why = "stale", "the last good report is %.0f s old" % age
            elif self.failures or age > grace:
                state, why = "degraded", "%d request(s) failed in a row: %s" % (
                    self.failures, self.last_error) if self.failures else \
                    "the last report is %.0f s old" % age
            else:
                state, why = "healthy", "reporting every %.0f s" % self.interval
        if credits_left is not None and credits_left <= 0 and state != "starting":
            state, why = "down", "out of credits"
        return {"state": state, "reason": why,
                "age_s": None if age is None else round(age, 1),
                "failures_in_a_row": self.failures, "failures_total": self.total_failures,
                "trust_an_empty_sky": state == "healthy",
                "stale_after_s": STALE_AFTER_S}


class Datum:
    """How a reported altitude becomes a height in this landscape's datum, and how sure it is.

    GEOMETRIC altitude is WGS84 ellipsoidal height, converted with the geoid at that position.
    BAROMETRIC altitude is pressure altitude: referenced to standard pressure, roughly mean sea
    level on a standard day and off by tens of metres on any other. It is not an ellipsoidal
    height, so adding a geoid separation to it would be wrong twice; it is taken as it stands and
    labelled. An explicit constant, when given, replaces the geoid for geometric altitude."""

    def __init__(self, offset=None, geoid=None, approximate=False):
        self.offset = None if offset is None else float(offset)
        self.geoid = geoid
        self.approximate = approximate

    @classmethod
    def default(cls, offset=None, quiet=True):
        """An explicit offset if given, else the geoid, else the constant with a warning."""
        if offset is not None:
            return cls(offset=offset)
        try:
            import geoid as geoid_module
            return cls(geoid=geoid_module.Geoid.default())
        except Exception:
            if not quiet:
                print("note: the geoid model is not installed, so a constant %+.0f m stands in "
                      "for it. py -3.10 geoid.py --fetch installs it." % GEOID_OFFSET_M,
                      flush=True)
            return cls(offset=GEOID_OFFSET_M, approximate=True)

    def height(self, aircraft):
        """(metres in the landscape's datum, how it was got), or (None, why not)."""
        if aircraft.geo_m is not None:
            if self.offset is not None:
                return float(aircraft.geo_m) + self.offset, (
                    "geometric, constant %+.0f m" % self.offset)
            try:
                return self.geoid.to_landscape(aircraft.lon, aircraft.lat, aircraft.geo_m), (
                    "geometric, %s" % self.geoid.model)
            except Exception as e:
                # Outside the grid, for example. Fall to barometric rather than guess a datum.
                if aircraft.baro_m is None:
                    return None, "no geoid value here: %s" % e
        if aircraft.baro_m is not None:
            return float(aircraft.baro_m), "barometric, uncorrected for the day's pressure"
        return None, "no altitude reported"

    def describe(self):
        if self.geoid is not None:
            return {"method": "geoid", "model": self.geoid.model, "relates": self.geoid.relates}
        return {"method": "constant", "offset_m": self.offset,
                "approximate": self.approximate,
                "note": "the geoid model was not installed" if self.approximate
                else "an explicit offset was given"}

    def summary(self):
        d = self.describe()
        if d["method"] == "geoid":
            return "%s at each aircraft's position" % d["model"]
        return "a constant %+.1f m%s" % (d["offset_m"],
                                         " (approximate: no geoid model)" if d["approximate"]
                                         else "")


def find_credentials(explicit=None):
    """The OpenSky credentials file: given, named by the environment, or beside the project."""
    if explicit:
        return explicit
    from_env = os.environ.get("OPENSKY_CREDENTIALS")
    if from_env:
        return from_env
    d = os.path.dirname(HERE)                     # the plugin
    for _ in range(5):
        d = os.path.dirname(d)
        if not d:
            break
        candidate = os.path.join(d, "api", "credentials.json")
        if os.path.isfile(candidate):
            return candidate
    return os.path.join(HERE, "credentials.json")


ROTATIONS = ("exhaustion", "round-robin", "newest-first")

# Rotate off a credential once its remaining credits fall to this, so there is something left for
# a deliberate request later in the day rather than the feed consuming the very last one.
CREDIT_FLOOR = 25

# How long to leave an exhausted credential alone when the network does not say.
DEFAULT_COOLDOWN_S = 900.0


def resolve_secret(value):
    """A secret from the file, from the environment, or from a file of its own.

    "env:OPENSKY_SECRET" reads an environment variable and "file:/path/to/secret" reads a file,
    so a rotation can change the secret without the JSON ever holding one. A plain string is used
    as it stands, because that is what OpenSky's own download gives you."""
    if not isinstance(value, str):
        return value
    if value.startswith("env:"):
        return os.environ.get(value[4:]) or None
    if value.startswith("file:"):
        try:
            return io.open(value[5:], encoding="utf-8").read().strip() or None
        except OSError:
            return None
    return value or None


class Credential:
    """One OpenSky client, and how it has been behaving.

    THE SECRET IS NEVER PRINTED, LOGGED OR STORED by anything here. A credential is named in
    output by its label and by a fingerprint, which is a hash of the client id: enough to tell two
    credentials apart in a log, useless to anyone who reads the log."""

    def __init__(self, label=None, client_id=None, client_secret=None, username=None,
                 password=None, added=None, note=None):
        self.client_id = client_id or None
        self.client_secret = resolve_secret(client_secret)
        self.username = username or None
        self.password = resolve_secret(password)
        self.added = added                     # when it was created, for newest-first
        self.note = note
        self.label = label or self.client_id or self.username or "anonymous"
        self.credits_left = None
        self.cooling_until = 0.0
        self.last_error = None
        self.last_used = None
        self.token = None
        self.token_expires = 0.0

    @property
    def fingerprint(self):
        """Identifies the ACCOUNT, not the secret, and is safe to print.

        Deliberately not secret derived: this ends up in logs and in a state file. Two entries
        holding the same client id with different secrets, which is exactly what a secret being
        replaced looks like, therefore share a fingerprint. Their labels tell them apart."""
        seed = self.client_id or self.username or ""
        return hashlib.sha256(seed.encode("utf-8")).hexdigest()[:10] if seed else "anonymous"

    @property
    def token_key(self):
        """Identifies the SECRET, for the token cache, and is never printed.

        It has to include the secret. Keying the cache by account alone meant an entry with a
        dead secret could be handed a token that a different entry's live secret had earned, and
        then report itself as working: measured, and the reason this exists. The file it keys is
        in the temporary folder and already holds live bearer tokens, so a digest beside them is
        not a new exposure."""
        return hashlib.sha256(("%s:%s" % (self.client_id or "", self.client_secret or ""))
                              .encode("utf-8")).hexdigest()[:16]

    @property
    def identity(self):
        return "%s [%s]" % (self.label, self.fingerprint)

    @property
    def complete(self):
        return bool((self.client_id and self.client_secret)
                    or (self.username and self.password))

    def cooling(self, now=None):
        return (now or time.time()) < self.cooling_until

    def usable(self, now=None):
        return self.complete and not self.cooling(now)


def load_credentials(path, quiet=False):
    """Every credential in a file, in the order it should be preferred.

    Four shapes are read, because the first is what OpenSky hands you and the rest are what a
    rotation needs:

        {"clientId": ..., "clientSecret": ...}                     one client
        {"clients": [{"label": ..., "clientId": ..., ...}, ...]}   several, in order
        [{"clientId": ...}, {"clientId": ...}]                     the same, bare
        {"username": ..., "password": ...}                         the older basic auth
    """
    try:
        with io.open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError) as e:
        if not quiet:
            print("no usable credentials at %s (%s), carrying on anonymously, which gets fewer "
                  "credits and a coarser update" % (path, e), flush=True)
        return []

    def one(item, index):
        return Credential(label=item.get("label") or item.get("name")
                          or ("client %d" % (index + 1)),
                          client_id=item.get("clientId") or item.get("client_id"),
                          client_secret=item.get("clientSecret") or item.get("client_secret"),
                          username=item.get("username"), password=item.get("password"),
                          added=item.get("added"), note=item.get("note"))

    items = []
    if isinstance(data, list):
        items = data
    elif isinstance(data, dict):
        listed = data.get("clients") or data.get("credentials")
        items = listed if isinstance(listed, list) else [data]
    out = [one(item, i) for i, item in enumerate(items) if isinstance(item, dict)]
    return [c for c in out if c.complete]


class CredentialSet:
    """Which credential to use now, and what to do when it stops working.

    WHY ROTATION IS WORTH HAVING. Two different jobs need it and they want the same machinery:

      SPREADING THE BUDGET. One account gets 4000 credits a day, which is a request every 21.6
      seconds and no more. A second account doubles that, and the feed should move to it when the
      first runs out rather than stopping, which is what "exhaustion" does.

      CHANGING A SECRET WITHOUT A GAP. A secret being replaced means two are briefly valid. Put
      the new one in the file beside the old, check it with --check-credentials, watch it serve
      traffic, then delete the old entry. Nothing has to be stopped and nothing is guessed at.
      "newest-first" prefers the new one while leaving the old as a fallback.

    WHAT IT REMEMBERS BETWEEN RUNS. Credits and cooldowns, keyed by fingerprint, in the system
    temporary folder. No secrets, and nothing that matters if it is lost: a stale cooldown costs
    one wasted request to discover."""

    def __init__(self, path=None, policy="exhaustion", only=None, quiet=False):
        self.path = path or find_credentials()
        self.policy = policy if policy in ROTATIONS else "exhaustion"
        self.quiet = quiet
        self.state_file = os.path.join(tempfile.gettempdir(), "opensky_credentials.json")
        self.credentials = load_credentials(self.path, quiet=quiet)
        if only:
            wanted = str(only).lower()
            kept = [c for c in self.credentials
                    if wanted in (c.label.lower(), c.fingerprint.lower())]
            if not kept:
                raise SystemExit("no credential called '%s' in %s. It has: %s"
                                 % (only, self.path,
                                    ", ".join(c.identity for c in self.credentials) or "none"))
            self.credentials = kept
        if self.policy == "newest-first":
            # Anything with a date sorts newest first; anything without keeps its file order
            # behind them, because an entry with no date is the one that has always been there.
            self.credentials.sort(key=lambda c: (c.added is None, str(c.added or "")),
                                  reverse=False)
            self.credentials.sort(key=lambda c: str(c.added or ""), reverse=True)
        self.index = 0
        self.rotations = 0
        self._load_state()

    def _say(self, text):
        if not self.quiet:
            print(text, flush=True)

    # ---- what the caller asks for ------------------------------------------------------------
    @property
    def anonymous(self):
        return not self.credentials

    def current(self):
        """The credential to use now, skipping any that is cooling off."""
        if not self.credentials:
            return None
        count = len(self.credentials)
        for step in range(count):
            candidate = self.credentials[(self.index + step) % count]
            if candidate.usable():
                if step:
                    self.index = (self.index + step) % count
                return candidate
        # Everything is cooling. Use the one that will recover soonest rather than nothing: the
        # request may fail, and a failed request is still better than a silent stop.
        soonest = min(self.credentials, key=lambda c: c.cooling_until)
        self.index = self.credentials.index(soonest)
        return soonest

    def rotate(self, reason=""):
        """Move to the next credential, and say so. Returns the new current one."""
        if len(self.credentials) < 2:
            if reason:
                self._say("no other credential to move to: %s" % reason)
            return self.current()
        self.index = (self.index + 1) % len(self.credentials)
        self.rotations += 1
        nxt = self.current()
        self._say("rotated to %s%s" % (nxt.identity if nxt else "nothing",
                                       (": %s" % reason) if reason else ""))
        return nxt

    def after_request(self, credential):
        """Called once a request has been made, to decide whether to move on for the next one."""
        if not credential or self.policy == "round-robin":
            if self.policy == "round-robin":
                self.rotate("round robin")
            return
        if credential.credits_left is not None and credential.credits_left <= CREDIT_FLOOR:
            self.rotate("%s is down to %d credits" % (credential.identity,
                                                      credential.credits_left))

    def note_credits(self, credential, left):
        if credential and left is not None:
            credential.credits_left = left
            credential.last_used = time.time()
            self._save_state()

    def note_exhausted(self, credential, retry_after=None):
        """Out of credits: leave it alone for a while and move on."""
        if not credential:
            return
        wait = DEFAULT_COOLDOWN_S
        try:
            if retry_after is not None:
                wait = max(60.0, float(retry_after))
        except (TypeError, ValueError):
            pass
        credential.cooling_until = time.time() + wait
        credential.credits_left = 0
        credential.last_error = "out of credits"
        self._save_state()
        self.rotate("%s is out of credits for %.0f s" % (credential.identity, wait))

    def note_rejected(self, credential, why):
        """The secret no longer works. This is the case rotation exists for."""
        if not credential:
            return
        credential.token = None
        credential.last_error = why
        credential.cooling_until = time.time() + 300.0
        self._save_state()
        self.rotate("%s was rejected (%s)" % (credential.identity, why))

    # ---- what it remembers -------------------------------------------------------------------
    def _load_state(self):
        try:
            with io.open(self.state_file, encoding="utf-8") as f:
                state = json.load(f)
        except (OSError, ValueError):
            return
        for credential in self.credentials:
            kept = state.get(credential.fingerprint) or {}
            credential.credits_left = kept.get("credits_left", credential.credits_left)
            credential.cooling_until = float(kept.get("cooling_until", 0.0) or 0.0)
            credential.last_used = kept.get("last_used")
            credential.last_error = kept.get("last_error")

    def _save_state(self):
        state = {}
        for credential in self.credentials:
            state[credential.fingerprint] = {"label": credential.label,
                                             "credits_left": credential.credits_left,
                                             "cooling_until": credential.cooling_until,
                                             "last_used": credential.last_used,
                                             "last_error": credential.last_error}
        try:
            with io.open(self.state_file, "w", encoding="utf-8") as f:
                json.dump(state, f, indent=1)
        except OSError:
            pass                        # remembering this is a convenience, never a requirement

    def summary(self):
        """One row per credential, for printing. No secrets, by construction."""
        now = time.time()
        rows = []
        for i, c in enumerate(self.credentials):
            rows.append({"label": c.label, "fingerprint": c.fingerprint,
                         "kind": "oauth2" if c.client_id else "basic",
                         "added": c.added, "note": c.note,
                         "credits_left": c.credits_left,
                         "cooling_for_s": max(0, int(c.cooling_until - now)),
                         "last_error": c.last_error,
                         "in_use": i == self.index})
        return rows


class OpenSky:
    """The network's REST API, with its tokens, its credits and its credentials looked after.

    A token lives for half an hour and is cached in the system temporary folder, keyed by the
    fingerprint of the credential that earned it, never by the secret. Secrets are not written
    anywhere by anything here: one that lands in a repository or a log is one that has to be
    replaced, and replacing it is exactly what CredentialSet is for."""

    def __init__(self, credentials=None, quiet=False, rotation="exhaustion", only=None,
                 credential_set=None):
        self.path = find_credentials(credentials)
        self.quiet = quiet
        self.session = requests.Session()
        self.credits_left = None
        self.cache = os.path.join(tempfile.gettempdir(), "opensky_tokens.json")
        self.set = credential_set or CredentialSet(self.path, policy=rotation, only=only,
                                                   quiet=quiet)

    def _say(self, text):
        if not self.quiet:
            print(text, flush=True)

    @property
    def anonymous(self):
        return self.set.anonymous

    # ---- tokens, one per credential ----------------------------------------------------------
    def _cached_tokens(self):
        try:
            with io.open(self.cache, encoding="utf-8") as f:
                data = json.load(f)
            return data if isinstance(data, dict) else {}
        except (OSError, ValueError):
            return {}

    def _store_token(self, credential, token, expires):
        tokens = self._cached_tokens()
        tokens[credential.token_key] = {"token": token, "expires": expires,
                                        "label": credential.label}
        # Anything long expired is dropped, so a file of retired credentials does not accumulate.
        now = time.time()
        tokens = {k: v for k, v in tokens.items() if (v or {}).get("expires", 0) > now - 3600}
        try:
            with io.open(self.cache, "w", encoding="utf-8") as f:
                json.dump(tokens, f)
        except OSError:
            pass                                  # a cache is a convenience, never a requirement

    def authorise(self, credential=None, fresh=False):
        """A bearer token for a credential, from the cache when one is still good.

        fresh skips the cache and asks the token endpoint, which is the only way to find out
        whether a secret is still good. Returns None when there is nothing to authorise with,
        which is a working state: the API answers anonymous requests too, on a smaller budget."""
        credential = credential or self.set.current()
        if not credential or not credential.client_id:
            return None
        if not fresh and credential.token and credential.token_expires - time.time() > 60:
            return credential.token
        cached = {} if fresh else (self._cached_tokens().get(credential.token_key) or {})
        if cached.get("token") and cached.get("expires", 0) - time.time() > 60:
            credential.token = cached["token"]
            credential.token_expires = cached["expires"]
            return credential.token
        try:
            r = self.session.post(TOKEN_URL, timeout=30,
                                  data={"grant_type": "client_credentials",
                                        "client_id": credential.client_id,
                                        "client_secret": credential.client_secret})
        except requests.RequestException as e:
            credential.last_error = str(e)
            return None
        if r.status_code != 200:
            # A REFUSED SECRET IS NOT FATAL ANY MORE. It used to stop the program, which is the
            # wrong answer when a second credential is sitting right there: that is the whole
            # point of being able to rotate one out.
            credential.last_error = "HTTP %d from the token endpoint" % r.status_code
            if fresh:
                return None            # a check reports it; it does not reorganise the set
            self._say("OpenSky refused %s: HTTP %d" % (credential.identity, r.status_code))
            self.set.note_rejected(credential, credential.last_error)
            return None
        body = r.json()
        credential.token = body["access_token"]
        credential.token_expires = time.time() + float(body.get("expires_in", 1800))
        self._store_token(credential, credential.token, credential.token_expires)
        return credential.token

    def check(self, probe=False, box=None):
        """Try every credential and say what happened, without printing any of them.

        Getting a token costs nothing, and it is the thing worth knowing when a secret has just
        been replaced: it proves the new one works before the old one is deleted. Reading the
        remaining credits needs a real request, so --probe asks for one, which costs a credit
        each."""
        rows = []
        for credential in self.set.credentials:
            row = {"label": credential.label, "fingerprint": credential.fingerprint,
                   "kind": "oauth2" if credential.client_id else "basic",
                   "added": credential.added, "note": credential.note,
                   "cooling_for_s": max(0, int(credential.cooling_until - time.time()))}
            if credential.client_id:
                credential.cooling_until = 0.0        # a check is a deliberate try, not a poll
                credential.last_error = None
                # fresh, because a check that accepts a cached token proves nothing about the
                # secret it is supposed to be checking.
                row["token"] = bool(self.authorise(credential, fresh=True))
                row["error"] = credential.last_error if not row["token"] else None
            else:
                row["token"] = None                   # basic auth has nothing to fetch
            if probe and box and (row.get("token") or credential.username):
                aircraft, _server = self.states(box, credential=credential, rotate_on_fail=False)
                row["credits_left"] = credential.credits_left
                row["aircraft_seen"] = len(aircraft)
            else:
                row["credits_left"] = credential.credits_left
            rows.append(row)
        return rows

    # ---- the states themselves ---------------------------------------------------------------
    def states(self, box, credential=None, rotate_on_fail=True):
        """Every aircraft in (west, south, east, north), as Aircraft, with the report's own time.

        Returns (list, server time). A request that fails returns an empty list rather than
        raising: a feed that dies because one poll timed out is worse than a gap in it. Running
        out of credits or having a secret refused moves to the next credential and tries once
        more, because both of those are precisely what another credential is for."""
        # extended=1 adds the aircraft category, which is how a model gets chosen for it. It
        # costs the same as the plain request.
        params = {"lamin": box[1], "lomin": box[0], "lamax": box[3], "lomax": box[2],
                  "extended": 1}
        credential = credential or self.set.current()
        headers = {}
        token = self.authorise(credential)
        if token is None and credential is not None and credential.client_id and rotate_on_fail:
            # The secret was refused, and authorise has already moved the set on. Use whoever is
            # current now rather than falling through to an anonymous request: an account with a
            # working secret is sitting right there, and anonymous has a far smaller budget.
            nxt = self.set.current()
            if nxt is not None and nxt is not credential:
                return self.states(box, credential=nxt, rotate_on_fail=False)
        if token:
            headers["Authorization"] = "Bearer %s" % token
        auth = None
        if not token and credential and credential.username:
            auth = (credential.username, credential.password)
        self.last_error = None
        try:
            r = self.session.get(STATES_URL, params=params, headers=headers, auth=auth,
                                 timeout=30)
        except requests.RequestException as e:
            self._say("the request failed: %s" % e)
            self.last_error = "no connection: %s" % e
            return [], None
        left = r.headers.get("x-rate-limit-remaining")
        if left is not None:
            try:
                self.credits_left = int(left)
                self.set.note_credits(credential, self.credits_left)
            except ValueError:
                pass

        if r.status_code == 429:
            # Out of credits. Another credential has its own budget, so move to it and try once;
            # with only one credential this is the same message it always was.
            wait = r.headers.get("x-rate-limit-retry-after-seconds")
            self._say("%s is out of credits%s"
                      % (credential.identity if credential else "this account",
                         "" if wait is None else "; the network says to wait %s s" % wait))
            self.set.note_exhausted(credential, wait)
            self.last_error = "out of credits"
            nxt = self.set.current()
            if rotate_on_fail and nxt and credential and nxt is not credential:
                return self.states(box, credential=nxt, rotate_on_fail=False)
            return [], None

        if r.status_code in (401, 403):
            # The token was refused. Once because it expired, twice because the secret is gone.
            if credential:
                credential.token = None
            retry = rotate_on_fail and self.authorise(credential)
            if retry:
                self._say("the token was rejected; got another")
                return self.states(box, credential=credential, rotate_on_fail=False)
            nxt = self.set.current()
            if rotate_on_fail and nxt and credential and nxt is not credential:
                return self.states(box, credential=nxt, rotate_on_fail=False)
            self.last_error = "the credentials were refused (HTTP %d)" % r.status_code
            return [], None

        if r.status_code != 200:
            self._say("HTTP %d from the states endpoint" % r.status_code)
            self.last_error = "HTTP %d from the states endpoint" % r.status_code
            return [], None
        try:
            body = r.json()
        except ValueError:
            self.last_error = "the response was not JSON"
            return [], None
        out = []
        for state in (body.get("states") or []):
            craft = Aircraft.from_state(state)
            if craft:
                out.append(craft)
        if rotate_on_fail:
            # Only on a deliberate poll, never on the retry of a failed one: rotating inside a
            # retry would move twice for one request.
            self.set.after_request(credential)
        return out, body.get("time")

    def sustainable_interval(self):
        """The fastest polling this account can keep up for the rest of the day."""
        if self.credits_left is None:
            return DEFAULT_INTERVAL
        # Credits reset daily, so what is left has to cover the time until then.
        now = time.gmtime()
        seconds_left = 86400 - (now.tm_hour * 3600 + now.tm_min * 60 + now.tm_sec)
        if self.credits_left <= 0:
            return float(seconds_left)
        return max(INTERVAL_FLOOR, seconds_left / float(self.credits_left))


class Aircraft:
    """One aircraft's last known state, and where it will be shortly.

    Altitudes are metres as OpenSky reports them, which is above the WGS84 ellipsoid for the
    geometric one. Nothing is converted into this landscape's frame here: that needs the terrain
    and a datum decision, and both belong to the caller."""

    __slots__ = ("icao24", "callsign", "country", "lon", "lat", "baro_m", "geo_m", "on_ground",
                 "speed_ms", "track_deg", "climb_ms", "last_contact", "squawk", "seen_at",
                 "category")

    def __init__(self, **kw):
        for name in self.__slots__:
            setattr(self, name, kw.get(name))

    @classmethod
    def from_state(cls, state):
        row = dict(zip(FIELDS, state))
        if row.get("longitude") is None or row.get("latitude") is None:
            return None                           # a report with no position is no use here
        return cls(icao24=row.get("icao24"),
                   callsign=(row.get("callsign") or "").strip() or None,
                   country=row.get("origin_country"),
                   lon=float(row["longitude"]), lat=float(row["latitude"]),
                   baro_m=row.get("baro_altitude"), geo_m=row.get("geo_altitude"),
                   on_ground=bool(row.get("on_ground")),
                   speed_ms=row.get("velocity"), track_deg=row.get("true_track"),
                   climb_ms=row.get("vertical_rate"), last_contact=row.get("last_contact"),
                   squawk=row.get("squawk"), seen_at=time.time(),
                   category=row.get("category"))

    @property
    def name(self):
        return self.callsign or self.icao24 or "unknown"

    @property
    def kind(self):
        """The class a model is assigned against: about size, not about type."""
        return self.classify()[0]

    def classify(self):
        """(class, where it came from). The second half matters more than it looks.

        MOST TRANSPONDERS DO NOT BROADCAST A CATEGORY. In a sample of 43 aircraft over Ann Arbor,
        three did. So when the category says nothing, the callsign is asked instead: an airline
        callsign is an ICAO three letter prefix and a flight number, and a general aviation one is
        a registration, which in North America starts with N or with C followed by a letter. That
        is a GUESS, it is wrong for a business jet on an airline-style callsign, and anything
        acting on it is told where the answer came from so it can decide whether to trust it."""
        try:
            number = None if self.category is None else int(self.category)
        except (TypeError, ValueError):
            number = None
        if number not in (None, 0, 1):
            return CATEGORY_CLASS.get(number, "unknown"), "category"

        call = (self.callsign or "").strip().upper()
        if len(call) >= 3:
            # ORDER MATTERS HERE. N479DV is a registration and NKS123 is Spirit Airlines, and
            # both begin with N and hold three letters, so counting letters gets it wrong. What
            # separates them is WHERE the digits start: a United States registration puts one
            # straight after the N, and an airline callsign puts three letters first.
            if call[0] == "N" and call[1].isdigit():
                return "light", "callsign"            # a United States registration
            if call[0] == "C" and call[1] in "FG" and not any(c.isdigit() for c in call):
                return "light", "callsign"            # a Canadian registration
            if call[:3].isalpha() and call[3:4].isdigit():
                return "large", "callsign"            # an ICAO airline prefix and a flight number
        return "unknown", "default"

    @property
    def span_m(self):
        """Roughly how wide it is, for scaling a shape that stands in for a model."""
        return CLASS_SPAN_M.get(self.kind, CLASS_SPAN_M["unknown"])

    def altitude(self, datum=None):
        """Height in this landscape's datum, or None.

        datum is a Datum. A bare number is still accepted as a constant offset, so older callers
        keep working, and None means the raw reported value with no correction at all."""
        if datum is None:
            for value in (self.geo_m, self.baro_m):
                if value is not None:
                    return float(value)
            return None
        if isinstance(datum, (int, float)):
            datum = Datum(offset=datum)
        return datum.height(self)[0]

    def age_s(self, now=None):
        """How long ago the position was reported, which is not the same as when we asked."""
        if self.last_contact is None:
            return 0.0
        return max(0.0, (now or time.time()) - float(self.last_contact))

    def project(self, seconds):
        """Where it will be in so many seconds, by dead reckoning, as (lon, lat, altitude).

        Straight line at the last known track, speed and vertical rate. Good for the twenty
        seconds between polls and not a second longer, which is why nothing here extrapolates
        an aircraft that has stopped reporting."""
        lon, lat = self.lon, self.lat
        if self.speed_ms and self.track_deg is not None and not self.on_ground:
            metres = float(self.speed_ms) * seconds
            heading = math.radians(float(self.track_deg))
            north = metres * math.cos(heading)
            east = metres * math.sin(heading)
            lat = lat + north / 111320.0
            scale = 111320.0 * max(0.05, math.cos(math.radians(lat)))
            lon = lon + east / scale
        altitude = self.altitude()
        if altitude is not None and self.climb_ms:
            altitude += float(self.climb_ms) * seconds
        return lon, lat, altitude

    def as_dict(self, terrain=None, offset=None):
        """What the planner draws and what the simulator places.

        The landscape frame is included when a terrain is given: north, east and down in metres,
        Unreal centimetres, and the height above the ground beneath it, which is the number that
        says whether something is a problem."""
        datum = offset if isinstance(offset, Datum) else (
            Datum(offset=offset) if isinstance(offset, (int, float)) else None)
        if datum is not None:
            altitude, how = datum.height(self)
        else:
            altitude, how = self.altitude(), "as reported, uncorrected"
        out = {"icao24": self.icao24, "callsign": self.callsign, "country": self.country,
               "lon": self.lon, "lat": self.lat,
               "baro_m": self.baro_m, "geo_m": self.geo_m,
               "altitude_m": None if altitude is None else round(altitude, 1),
               "on_ground": self.on_ground,
               "speed_ms": self.speed_ms, "track_deg": self.track_deg, "climb_ms": self.climb_ms,
               "squawk": self.squawk, "age_s": round(self.age_s(), 1),
               "altitude_from": how,
               "category": self.category, "class": self.kind,
               "class_source": self.classify()[1], "span_m": self.span_m}
        if terrain is not None and altitude is not None:
            out.update(in_landscape_frame(terrain, self.lon, self.lat, altitude,
                                          self.track_deg, self.speed_ms, self.climb_ms))
        return out


def in_landscape_frame(terrain, lon, lat, altitude, track_deg, speed_ms, climb_ms):
    """One aircraft in every frame the rest of this project uses.

    The Unreal yaw and velocity are worked out here on purpose. The plugin that draws these
    aircraft should not have to know which way the landscape was laid out, what projection it is
    on, or how a true bearing relates to either: it moves a marker along a vector and points it at
    a yaw. Everything that could be got wrong is got wrong in one place, in a language that can be
    tested without an editor open."""
    north, east, down = terrain.ned(lon, lat, altitude)
    ground = terrain.ground_elevation(lon, lat)
    out = {"north": round(north, 2), "east": round(east, 2), "down": round(down, 2),
           "unreal_cm": [round(north * 100.0, 1), round(east * 100.0, 1), round(-down * 100.0, 1)],
           "ground_m": None if ground is None else round(ground, 1),
           "agl_m": None if ground is None else round(altitude - ground, 1),
           "over_landscape": ground is not None,
           "unreal_yaw_deg": unreal_heading_deg(terrain, lon, lat, track_deg)}
    # Centimetres a second along Unreal's own axes, for whatever has to keep the marker moving
    # between reports: X is grid east, Y is grid south, Z is up.
    if speed_ms is not None and track_deg is not None:
        grid = math.radians(float(track_deg) + grid_convergence_deg(terrain, lon, lat))
        out["unreal_velocity_cm_s"] = [round(float(speed_ms) * math.sin(grid) * 100.0, 1),
                                       round(-float(speed_ms) * math.cos(grid) * 100.0, 1),
                                       round(float(climb_ms or 0.0) * 100.0, 1)]
    else:
        out["unreal_velocity_cm_s"] = [0.0, 0.0, 0.0]
    return out


# ---------------------------------------------------------------------------------------------
# Where to look, and what it means for a mission
# ---------------------------------------------------------------------------------------------

def box_for(terrain, pad_km=25.0):
    """The landscape's own extent, grown by a margin, because traffic matters before it arrives.

    Twenty five kilometres at 250 knots is about three minutes of warning, which is the point."""
    west, south, east, north = terrain.extent_lonlat()
    lat = (south + north) / 2.0
    dlat = pad_km / 111.32
    dlon = pad_km / (111.32 * max(0.05, math.cos(math.radians(lat))))
    return (west - dlon, south - dlat, east + dlon, north + dlat)


def conflicts(mission, terrain, aircraft, horizontal_m=1000.0, vertical_m=300.0, offset=0.0):
    """Which aircraft come close to a planned route, and how close.

    HORIZONTAL AND VERTICAL SEPARATELY, because that is how airspace works: something directly
    overhead at ten thousand feet is not a conflict, and something at your height a kilometre away
    is worth knowing about. The horizontal distance is measured to the nearest point on the route,
    the same way the planner measures its own deviation."""
    try:
        legs = mission.legs(terrain)
    except Exception:
        return []
    if len(legs) < 2:
        return []
    flat = [(n, e, 0.0) for _w, n, e, _d, _elev in legs]
    heights = [elev for _w, _n, _e, _d, elev in legs]

    found = []
    for craft in aircraft:
        altitude = craft.altitude(offset)
        if altitude is None:
            continue
        north, east, _down = terrain.ned(craft.lon, craft.lat, altitude)
        distance, leg = deviation(flat, (north, east, 0.0))
        if distance is None:
            continue
        # The route's own height along that leg, taken as the higher of its two ends: being under
        # a climbing leg is still being under the route.
        nearby = [heights[leg]] + ([heights[leg + 1]] if leg + 1 < len(heights) else [])
        separation = altitude - max(nearby)
        if distance <= horizontal_m and abs(separation) <= vertical_m:
            found.append({"aircraft": craft, "horizontal_m": round(distance, 1),
                          "vertical_m": round(separation, 1), "leg": leg,
                          "leg_name": legs[leg][0].name,
                          "altitude_m": round(altitude, 1)})
    found.sort(key=lambda c: (c["horizontal_m"], abs(c["vertical_m"])))
    return found


# ---------------------------------------------------------------------------------------------
# Feeds
# ---------------------------------------------------------------------------------------------

def aircraft_from_payload(payload):
    """The Aircraft in a recorded update, rebuilt from what was written down.

    WHY NOT JUST REPLAY THE FILE. A recording holds whatever fields existed the day it was made,
    and the frame fields in it were worked out against whatever landscape was loaded then. Turning
    it back into Aircraft and deriving everything again means a replay behaves exactly like a live
    feed: same fields, same frame, against the landscape that is loaded now."""
    out = []
    for item in payload.get("aircraft", []):
        if item.get("lon") is None or item.get("lat") is None:
            continue
        out.append(Aircraft(
            icao24=item.get("icao24"), callsign=item.get("callsign"),
            country=item.get("country"), lon=item.get("lon"), lat=item.get("lat"),
            baro_m=item.get("baro_m"), geo_m=item.get("geo_m"),
            on_ground=item.get("on_ground"), speed_ms=item.get("speed_ms"),
            track_deg=item.get("track_deg"), climb_ms=item.get("climb_ms"),
            last_contact=time.time() - (item.get("age_s") or 0.0),
            squawk=item.get("squawk"), seen_at=time.time(),
            category=item.get("category")))
    return out


def write_snapshot(path, payload):
    """Replace a file in one step, so a reader never sees half of it.

    Unreal polls this file on a timer and must never parse a partial write, so the new version
    goes to a temporary name and is moved over the old one, which is atomic on both platforms."""
    tmp = path + ".part"
    with io.open(tmp, "w", encoding="utf-8", newline="\n") as f:
        json.dump(payload, f)
        f.write("\n")
    os.replace(tmp, path)


def payload_for(aircraft, terrain, offset, box, server_time, credits_left=None, health=None):
    return {"format": "maircorridor-traffic/1",
            "source": "OpenSky Network",
            "fetched": time.time(),
            "server_time": server_time,
            "box": list(box),
            "altitude_datum": offset.describe() if isinstance(offset, Datum)
            else {"method": "constant", "offset_m": offset},
            "vertical_datum": "NAVD88 orthometric metres, the landscape's own",
            "credits_left": credits_left,
            "health": health,
            "frame": {"ned": "north = unreal_x_cm / 100, east = unreal_y_cm / 100, "
                             "down = -unreal_z_cm / 100",
                      "plan": getattr(terrain, "path", None)},
            "aircraft": [a.as_dict(terrain, offset) for a in aircraft]}


def table(aircraft, offset, terrain):
    lines = ["%-9s %-8s %10s %10s %9s %9s %7s %6s %5s"
             % ("callsign", "icao24", "lon", "lat", "alt m", "agl m", "kt", "trk", "age")]
    for craft in sorted(aircraft, key=lambda a: (a.altitude(offset) or 0.0)):
        altitude = craft.altitude(offset)
        ground = terrain.ground_elevation(craft.lon, craft.lat) if terrain else None
        lines.append("%-9s %-8s %10.4f %10.4f %9s %9s %7s %6s %5.0f"
                     % (craft.name[:9], craft.icao24 or "", craft.lon, craft.lat,
                        "-" if altitude is None else "%.0f" % altitude,
                        "-" if (ground is None or altitude is None) else "%.0f" % (altitude - ground),
                        "-" if craft.speed_ms is None else "%.0f" % (craft.speed_ms * 1.94384),
                        "-" if craft.track_deg is None else "%.0f" % craft.track_deg,
                        craft.age_s()))
    return "\n".join(lines)


class Feed:
    """Polls in the background and hands over the latest aircraft, for a window to draw.

    WHY IT LIVES HERE RATHER THAN IN THE WINDOW. Two things want this: the planner, which draws
    traffic on its map, and anything else that comes later. The window only ever asks what is up
    there now; the waiting, the token, the credits and the dead reckoning are this module's
    problem.

    NOTHING HERE TOUCHES A WIDGET. The thread stores results and the window asks for them on its
    own timer, because tkinter belongs to one thread and a feed that calls into it from another
    will work for a week and then crash during a demonstration."""

    def __init__(self, terrain, box=None, interval=DEFAULT_INTERVAL, offset=None,
                 pad_km=25.0, forget=120.0, credentials=None, replay=None, snapshot=None,
                 rotation="exhaustion", credential=None):
        self.terrain = terrain
        self.box = tuple(box) if box else box_for(terrain, pad_km)
        self.interval = max(INTERVAL_FLOOR, float(interval))
        # A Datum: the geoid unless an explicit constant was asked for.
        self.offset = offset if isinstance(offset, Datum) else Datum.default(offset)
        self.forget = float(forget)
        self.credentials = credentials
        self.rotation = rotation
        self.credential = credential
        self.replay = replay
        # A file for the level to read. One feed then serves both: asking the network twice for
        # the same aircraft would spend twice the credits for exactly the same answer.
        self.snapshot = snapshot
        self.lock = threading.Lock()
        self.thread = None
        self.stopping = threading.Event()
        self.aircraft = []            # Aircraft, as last reported
        self.fetched_at = None
        self.credits_left = None
        self.error = None
        self.updates = 0
        self.using = None             # the credential set, once the thread has built one
        self.health = FeedHealth(self.interval)

    # ---- running -----------------------------------------------------------------------------
    def start(self):
        if self.thread and self.thread.is_alive():
            return
        self.stopping.clear()
        self.thread = threading.Thread(target=self._loop, daemon=True)
        self.thread.start()

    def stop(self):
        self.stopping.set()

    @property
    def running(self):
        return bool(self.thread and self.thread.is_alive())

    def _loop(self):
        if self.replay:
            self._replay_loop()
            return
        sky = OpenSky(self.credentials, quiet=True, rotation=self.rotation,
                      only=self.credential)
        self.using = sky.set
        while not self.stopping.is_set():
            try:
                aircraft, server_time = sky.states(self.box)
                now = time.time()
                with self.lock:
                    self.credits_left = sky.credits_left
                    if server_time is None:
                        # A FAILURE IS NOT AN EMPTY SKY. The last good picture stays, ageing
                        # and dead reckoned, and the health says how old it is.
                        self.health.failure(sky.last_error)
                        self.error = sky.last_error
                        keep = [a for a in self.aircraft if a.age_s(now) <= self.forget]
                        self.aircraft = keep
                    else:
                        keep = [a for a in aircraft if a.age_s(now) <= self.forget]
                        self.health.success()
                        self.aircraft = keep
                        self.fetched_at = now
                        self.error = None
                        self.updates += 1
                    health = self.health.assess(self.credits_left)
                if self.snapshot:
                    try:
                        write_snapshot(self.snapshot,
                                       payload_for(keep, self.terrain, self.offset, self.box,
                                                   server_time, sky.credits_left, health))
                    except OSError as e:
                        with self.lock:
                            self.error = "cannot write %s: %s" % (self.snapshot, e)
            except Exception as e:                 # a feed must outlive one bad response
                with self.lock:
                    self.health.failure(str(e))
                    self.error = str(e)
            self.stopping.wait(self.interval)

    def _replay_loop(self):
        """A recorded feed, for working on any of this with no network and no credits spent."""
        rows = []
        try:
            with io.open(self.replay, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("TRAFFIC "):
                        line = line[8:]
                    if line:
                        rows.append(json.loads(line))
        except (OSError, ValueError) as e:
            with self.lock:
                self.error = "cannot replay %s: %s" % (self.replay, e)
            return
        while not self.stopping.is_set() and rows:
            for row in rows:
                if self.stopping.is_set():
                    return
                craft = aircraft_from_payload(row)
                with self.lock:
                    self.aircraft = craft
                    self.fetched_at = time.time()
                    self.error = None
                    self.updates += 1
                    self.health.success()
                if self.snapshot:
                    try:
                        write_snapshot(self.snapshot,
                                       payload_for(craft, self.terrain, self.offset, self.box,
                                                   None, None))
                    except OSError:
                        pass
                self.stopping.wait(self.interval)

    # ---- what the window asks for ------------------------------------------------------------
    def now(self):
        """Every aircraft as a dict, moved on to this instant by dead reckoning.

        The positions are from the last report, which may be twenty seconds old, so each one is
        carried forward along its own track at its own speed. An aircraft is never carried further
        than --forget allows, and the age it was reported at travels with it so nothing downstream
        has to take the position on trust."""
        with self.lock:
            craft = list(self.aircraft)
            fetched = self.fetched_at
        if not craft:
            return []
        out = []
        for one in craft:
            ahead = max(0.0, time.time() - (one.seen_at or time.time()))
            lon, lat, altitude = one.project(ahead)
            row = one.as_dict(self.terrain, self.offset)
            row["lon"], row["lat"] = lon, lat
            # The datum is applied once, where the aircraft was reported; the climb since then is
            # added on top. The separation changes by centimetres over twenty seconds of flight.
            placed = one.altitude(self.offset)
            altitude = None if placed is None else placed + float(one.climb_ms or 0.0) * ahead
            if altitude is not None:
                row["altitude_m"] = round(altitude, 1)
                row.update(in_landscape_frame(self.terrain, lon, lat, altitude, one.track_deg,
                                              one.speed_ms, one.climb_ms))
            row["projected_s"] = round(ahead, 1)
            row["reported_s_ago"] = round(one.age_s(), 1)
            out.append(row)
        return out

    def status(self):
        """The feed's health, now: how old the picture is, and whether an empty sky is real."""
        with self.lock:
            return self.health.assess(self.credits_left)

    def live_aircraft(self):
        """The raw states, for a conflict check that wants the reported position and not a guess."""
        with self.lock:
            return list(self.aircraft)


def main():
    ap = argparse.ArgumentParser(description="Real aircraft overhead, in this landscape's frame.")
    ap.add_argument("--once", action="store_true", help="one look, printed as a table")
    ap.add_argument("--watch", action="store_true", help="keep looking until stopped")
    ap.add_argument("--interval", type=float, default=DEFAULT_INTERVAL,
                    help="seconds between requests (default 20; 4000 credits a day is one every "
                         "21.6 s sustained)")
    ap.add_argument("--snapshot", help="a JSON file replaced on every update, for the simulator")
    ap.add_argument("--record", help="append every update to this file as JSON lines")
    ap.add_argument("--replay", help="read a recorded file instead of the network")
    ap.add_argument("--speed", type=float, default=1.0, help="replay faster or slower")
    ap.add_argument("--plan", default=DEFAULT_PLAN, help="the landscape plan for the frame")
    ap.add_argument("--pad-km", type=float, default=25.0,
                    help="how far beyond the landscape to look (default 25)")
    ap.add_argument("--box", nargs=4, type=float, metavar=("WEST", "SOUTH", "EAST", "NORTH"),
                    help="an explicit box instead of the landscape's")
    ap.add_argument("--altitude-offset", type=float, default=None,
                    help="added to every reported altitude to match this landscape's datum "
                         "(default +34, see the note at the top of this file)")
    ap.add_argument("--forget", type=float, default=120.0,
                    help="drop an aircraft whose last report is older than this (default 120 s)")
    ap.add_argument("--credentials", help="the OpenSky credentials JSON")
    ap.add_argument("--rotation", choices=list(ROTATIONS), default="exhaustion",
                    help="how to choose between several credentials: use one until its credits "
                         "run out (default), take turns, or prefer the newest")
    ap.add_argument("--credential", metavar="LABEL",
                    help="use only this one, by label or fingerprint")
    ap.add_argument("--check-credentials", action="store_true",
                    help="try every credential and say which work, without printing any of them")
    ap.add_argument("--probe", action="store_true",
                    help="with --check-credentials, also make one real request per credential to "
                         "read its remaining credits; costs a credit each")
    ap.add_argument("--quiet", action="store_true", help="only the machine readable output")
    args = ap.parse_args()

    terrain = Terrain(args.plan)
    box = tuple(args.box) if args.box else box_for(terrain, args.pad_km)
    # The geoid unless an explicit offset was given; the rest of main uses this, not the number.
    args.altitude_offset = Datum.default(args.altitude_offset, quiet=args.quiet)

    if args.replay:
        replay(args, terrain, box)
        return

    sky = OpenSky(args.credentials, quiet=args.quiet, rotation=args.rotation,
                  only=args.credential)
    if args.check_credentials:
        check_credentials(sky, box, args)
        return
    if not args.quiet:
        print("credentials %s%s" % (sky.path, " (anonymous)" if sky.anonymous else ""))
        if len(sky.set.credentials) > 1:
            print("rotation    %d credentials, %s: %s"
                  % (len(sky.set.credentials), sky.set.policy,
                     ", ".join(c.identity for c in sky.set.credentials)))
        elif sky.set.credentials:
            print("rotation    one credential, %s" % sky.set.credentials[0].identity)
        print("box         %.4f %.4f to %.4f %.4f" % box)
        print("altitude    %s, into the landscape's NAVD88 heights"
              % args.altitude_offset.summary())

    if args.interval < INTERVAL_FLOOR:
        sys.exit("an interval under %.0f s will burn the day's credits in an hour; raise it"
                 % INTERVAL_FLOOR)

    first = True
    health = FeedHealth(args.interval)
    last_good = []
    while True:
        aircraft, server_time = sky.states(box)
        now = time.time()
        if server_time is None:
            # Keep the last good picture rather than writing an empty sky over it.
            health.failure(sky.last_error)
            aircraft = [a for a in last_good if a.age_s(now) <= args.forget]
            if not args.quiet:
                print("feed      %s" % health.assess(sky.credits_left)["reason"], flush=True)
        else:
            health.success()
            aircraft = [a for a in aircraft if a.age_s(now) <= args.forget]
            last_good = aircraft
        payload = payload_for(aircraft, terrain, args.altitude_offset, box, server_time,
                              sky.credits_left, health.assess(sky.credits_left))
        if args.snapshot:
            write_snapshot(args.snapshot, payload)
        if args.record:
            with io.open(args.record, "a", encoding="utf-8", newline="\n") as f:
                f.write(json.dumps(payload) + "\n")
        over = [a for a in payload["aircraft"] if a.get("over_landscape")]
        if args.once or not args.watch:
            if not args.quiet:
                print("\n%d aircraft, %d of them over the landscape itself%s\n"
                      % (len(aircraft), len(over),
                         "" if sky.credits_left is None else ", %d credits left"
                         % sky.credits_left))
                print(table(aircraft, args.altitude_offset, terrain))
            else:
                print("TRAFFIC " + json.dumps(payload), flush=True)
            return
        # The planner reads these lines, the same way it reads the flight's own track.
        print("TRAFFIC " + json.dumps(payload), flush=True)
        if first and not args.quiet:
            sustainable = sky.sustainable_interval()
            if sustainable > args.interval:
                print("note: %d credits left today, which is one request every %.0f s. Asking "
                      "every %.0f s will run out before the day does."
                      % (sky.credits_left or 0, sustainable, args.interval), flush=True)
            first = False
        time.sleep(max(INTERVAL_FLOOR, args.interval))


def check_credentials(sky, box, args):
    """Print what each credential is and whether it works. Never what it is made of.

    This is the half of rotation that matters when a secret is being replaced: put the new client
    in the file beside the old one, run this, and only delete the old entry once the new one has
    answered. Nothing is stopped and nothing is assumed."""
    rows = sky.check(probe=args.probe, box=box)
    if not rows:
        print("no credentials in %s, so every request will be anonymous" % sky.path)
        return
    print("%-20s %-12s %-8s %-8s %-9s %s"
          % ("label", "account", "kind", "secret", "credits", "note"))
    for row in rows:
        note = row.get("error") or row.get("note") or ""
        if row.get("cooling_for_s"):
            note = "resting for %d s. %s" % (row["cooling_for_s"], note)
        if row.get("aircraft_seen") is not None:
            note = "%d aircraft. %s" % (row["aircraft_seen"], note)
        print("%-20s %-12s %-8s %-8s %-9s %s"
              % (row["label"][:20], row["fingerprint"], row["kind"],
                 "ok" if row["token"] else ("-" if row["token"] is None else "REFUSED"),
                 "?" if row["credits_left"] is None else row["credits_left"], note.strip()))
    working = [r for r in rows if r["token"] or r["kind"] == "basic"]
    print("\n%d of %d usable%s" % (len(working), len(rows),
                                   "" if args.probe else
                                   ". Credits are only known after a real request: add --probe "
                                   "to spend one per credential and find out"))
    seen = {}
    for row in rows:
        seen.setdefault(row["fingerprint"], []).append(row["label"])
    shared = {f: labels for f, labels in seen.items() if len(labels) > 1}
    if shared:
        for _f, labels in shared.items():
            print("note: %s are the same account, so they share one budget of credits. Rotating "
                  "between them replaces a secret; it does not buy more requests. For more "
                  "requests, add a client from a different OpenSky account."
                  % " and ".join(labels))


def replay(args, terrain, box):
    """Play a recorded feed back, for working on any of this without the network or the credits."""
    rows = []
    with io.open(args.replay, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line.startswith("TRAFFIC "):
                line = line[8:]
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except ValueError:
                continue
    if not rows:
        sys.exit("nothing to replay in %s" % args.replay)
    if not args.quiet:
        print("replaying %d updates from %s at %.1fx" % (len(rows), args.replay, args.speed))
    previous = None
    for row in rows:
        if previous is not None and args.speed > 0:
            gap = (row.get("fetched", 0) - previous) / args.speed
            if 0 < gap < 300:
                time.sleep(gap)
        previous = row.get("fetched", 0)
        fresh = payload_for(aircraft_from_payload(row), terrain, args.altitude_offset, box,
                            row.get("server_time"), None)
        fresh["replayed"] = True
        fresh["recorded_at"] = row.get("fetched")
        if args.snapshot:
            write_snapshot(args.snapshot, fresh)
        print("TRAFFIC " + json.dumps(fresh), flush=True)
        if args.once:
            return


if __name__ == "__main__":
    main()
