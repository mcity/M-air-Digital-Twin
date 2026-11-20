"""mapview.py - a slippy map in a tkinter frame, with a box you can drag out on it.

Used by geodata_ui.py so an area can be chosen by looking at the world rather than by typing four
numbers. Pan with the left button, zoom with the wheel, hold Shift (or press "Draw box") and drag to
mark the area.

WHY NOT A BROWSER. Embedding one means another dependency and a second window; this needs only the
packages the tools already use, draws into the same window, and the map is a plain canvas of tiles,
which is a couple of hundred lines.

TILES COME FROM OPENSTREETMAP and are cached on disk, so panning the same ground again costs nothing.
They are map tiles for choosing an area, nothing else: the elevation and imagery still come from the
sources the tools download from. OpenStreetMap asks for a real User-Agent and no bulk downloading,
and both are respected here. Map data (c) OpenStreetMap contributors, ODbL.
"""
import io
import math
import os
import queue
import threading
import tkinter as tk
from concurrent.futures import ThreadPoolExecutor
from tkinter import ttk

from toolpaths import HERE

try:
    import requests
    from PIL import Image, ImageTk
except ImportError:                      # the window still runs, it just cannot draw a map
    requests = None

TILE = 256
CACHE = os.path.join(HERE, ".tilecache")
TILE_URL = "https://tile.openstreetmap.org/{z}/{x}/{y}.png"
NOMINATIM = "https://nominatim.openstreetmap.org/search"
USER_AGENT = "MAirCorridor-geodata/1.0 (+https://github.com/sriceumich/MAirCorridor)"


# ---- the web mercator the tiles are cut on ---------------------------------------------------

def lonlat_to_world(lon, lat, zoom):
    """Longitude and latitude to pixels on the whole world at this zoom."""
    n = TILE * (2 ** zoom)
    x = (lon + 180.0) / 360.0 * n
    lat = max(min(lat, 85.05112878), -85.05112878)
    s = math.sin(math.radians(lat))
    y = (0.5 - math.log((1 + s) / (1 - s)) / (4 * math.pi)) * n
    return x, y


def world_to_lonlat(x, y, zoom):
    n = TILE * (2 ** zoom)
    lon = x / n * 360.0 - 180.0
    lat = math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * y / n))))
    return lon, lat


class MapView(ttk.Frame):
    """A map with an optional drawn box and an optional outline (a loaded polygon)."""

    def __init__(self, parent, on_box=None, height=320, waypoints=False):
        super().__init__(parent)
        self.on_box = on_box
        # Waypoint editing, off unless asked for: a click places one, a drag on one moves it.
        self.waypoints_enabled = waypoints
        self.waypoints = []            # dicts with lon, lat and name
        self.selected = -1
        self.on_waypoint_add = None    # (lon, lat)
        self.on_waypoint_move = None   # (index, lon, lat)
        self.on_waypoint_select = None # (index)
        self.drone = None              # (lon, lat) reported by a flight in progress
        self.start = None              # (lon, lat) where the mission says the drone starts
        self.on_pick = None            # a one-off: the next click on the map goes here, (lon, lat)
        self.traffic = []              # real aircraft, as adsb.py reports them
        self.volumes = []              # declared airspace, as lists of (lon, lat), with a kind
        self.volume_live = None        # the name of the volume the aircraft is meant to be in
        self.fences = []               # geofences, as lists of (lon, lat), with a severity
        self.traffic_conflicts = set()  # icao24 of the ones worth worrying about
        self.trail = []                # where it has actually been
        self.zoom = 9
        self.centre = (-83.42, 42.30)          # the corridor, as somewhere to start
        self.box = None                        # (west, south, east, north)
        self.outline = None                    # a ring of (lon, lat), drawn as a polygon
        self.images = {}                       # (z,x,y) -> PhotoImage, kept so Tk does not free them
        self.pending = set()
        self.queue = queue.Queue()
        self.pool = ThreadPoolExecutor(max_workers=4) if requests else None
        self._drag = None
        self._draw_mode = tk.BooleanVar(value=False)

        self._build(height)
        if requests is None:
            self.canvas.create_text(10, 10, anchor="nw", fill="#a33",
                                    text="The map needs requests and Pillow:\n"
                                         "py -3.10 -m pip install -r requirements.txt")
        else:
            self.after(80, self._pump)
            self.after(120, self.redraw)

    # ---- widgets -----------------------------------------------------------------------------

    def _build(self, height):
        bar = ttk.Frame(self)
        bar.pack(fill="x")
        # A ttk check button starts in its "alternate" look, which draws as ticked even when
        # the variable is false. Clear it so the control shows what it actually is.
        draw = ttk.Checkbutton(bar, text="Draw box", variable=self._draw_mode)
        draw.state(["!alternate"])
        if not self.waypoints_enabled:
            draw.pack(side="left")
        ttk.Button(bar, text="Zoom in", width=8, command=lambda: self._zoom(1)).pack(side="left", padx=(6, 0))
        ttk.Button(bar, text="Zoom out", width=9, command=lambda: self._zoom(-1)).pack(side="left", padx=2)
        ttk.Button(bar, text="Fit", width=6, command=self.fit).pack(side="left", padx=(6, 0))
        if not self.waypoints_enabled:
            ttk.Button(bar, text="Clear box", width=9,
                       command=self.clear_box).pack(side="left", padx=2)

        self.search = tk.StringVar()
        ttk.Entry(bar, textvariable=self.search, width=22).pack(side="left", padx=(12, 2))
        ttk.Button(bar, text="Find place", command=self._find).pack(side="left")
        self.readout = ttk.Label(bar, text="", foreground="#444")
        self.readout.pack(side="right")

        self.canvas = tk.Canvas(self, height=height, background="#dfe6ec", highlightthickness=1,
                                highlightbackground="#b8c2cc", cursor="fleur")
        self.canvas.pack(fill="both", expand=True, pady=(4, 0))
        self.canvas.bind("<Configure>", lambda e: self.redraw())
        self.canvas.bind("<ButtonPress-1>", self._press)
        self.canvas.bind("<B1-Motion>", self._motion)
        self.canvas.bind("<ButtonRelease-1>", self._release)
        self.canvas.bind("<MouseWheel>", lambda e: self._zoom(1 if e.delta > 0 else -1, e.x, e.y))
        self.canvas.bind("<Double-Button-1>", lambda e: self._zoom(1, e.x, e.y))

        ttk.Label(self, text="Map data (c) OpenStreetMap contributors. " +
                  ("Left drag pans, wheel zooms, click to place a waypoint, drag one to move it."
                   if self.waypoints_enabled else
                   "Left drag pans, wheel zooms, Shift drag marks the area."),
                  foreground="#777").pack(anchor="w")

    # ---- view --------------------------------------------------------------------------------

    def _size(self):
        return max(self.canvas.winfo_width(), 1), max(self.canvas.winfo_height(), 1)

    def _origin(self):
        """World pixel at the top left of the canvas."""
        w, h = self._size()
        cx, cy = lonlat_to_world(self.centre[0], self.centre[1], self.zoom)
        return cx - w / 2.0, cy - h / 2.0

    def to_screen(self, lon, lat):
        ox, oy = self._origin()
        x, y = lonlat_to_world(lon, lat, self.zoom)
        return x - ox, y - oy

    def to_lonlat(self, sx, sy):
        ox, oy = self._origin()
        return world_to_lonlat(ox + sx, oy + sy, self.zoom)

    def _zoom(self, delta, sx=None, sy=None):
        new = max(2, min(18, self.zoom + delta))
        if new == self.zoom:
            return
        if sx is None:
            self.zoom = new
        else:
            lon, lat = self.to_lonlat(sx, sy)      # keep the point under the cursor still
            self.zoom = new
            w, h = self._size()
            x, y = lonlat_to_world(lon, lat, self.zoom)
            cx, cy = x + (w / 2.0 - sx), y + (h / 2.0 - sy)
            self.centre = world_to_lonlat(cx, cy, self.zoom)
        self.redraw()

    def waypoints_bbox(self, pad_fraction=0.15):
        """The drawn route's extent, with a margin so the end markers are not on the edge."""
        if not self.waypoints:
            return None
        lons = [w["lon"] for w in self.waypoints]
        lats = [w["lat"] for w in self.waypoints]
        pad = max(0.002, (max(lons) - min(lons)) * pad_fraction, (max(lats) - min(lats)) * pad_fraction)
        return min(lons) - pad, min(lats) - pad, max(lons) + pad, max(lats) + pad

    def fit(self, box=None):
        """Put a box, the drawn route, or a loaded outline in view."""
        box = box or self.box or self.outline_bbox() or self.waypoints_bbox()
        if not box:
            return
        west, south, east, north = box
        self.centre = ((west + east) / 2.0, (south + north) / 2.0)
        w, h = self._size()
        if w < 50 or h < 50:
            # The canvas has not been laid out yet: measuring it now would fit a one pixel
            # viewport and settle on the whole world. Ask again once Tk has placed it.
            self.after(60, lambda b=box: self.fit(b))
            return
        for z in range(18, 1, -1):
            x0, y0 = lonlat_to_world(west, north, z)
            x1, y1 = lonlat_to_world(east, south, z)
            if (x1 - x0) < w * 0.9 and (y1 - y0) < h * 0.9:
                self.zoom = z
                break
        self.redraw()

    def outline_bbox(self):
        if not self.outline:
            return None
        lons = [p[0] for p in self.outline]
        lats = [p[1] for p in self.outline]
        return min(lons), min(lats), max(lons), max(lats)

    # ---- the box -----------------------------------------------------------------------------

    def set_box(self, box, fit=False):
        self.box = tuple(box) if box else None
        if fit:
            self.fit()
        else:
            self.redraw()

    def clear_box(self):
        self.box = None
        self.redraw()
        if self.on_box:
            self.on_box(None)

    def set_outline(self, ring, fit=True):
        self.outline = list(ring) if ring else None
        if fit:
            self.fit(self.outline_bbox())
        else:
            self.redraw()

    # ---- waypoints ---------------------------------------------------------------------------

    def set_waypoints(self, points, selected=-1, fit=False):
        """points: a sequence of objects with .lon, .lat and .name, drawn in order as a route."""
        self.waypoints = [{"lon": float(p.lon), "lat": float(p.lat), "name": getattr(p, "name", "")}
                          for p in points]
        self.selected = selected
        if fit and self.waypoints:
            self.fit(self.waypoints_bbox())
        else:
            self.redraw()

    def set_start(self, lon_lat):
        """Where the drone starts, drawn as a square joined to the first waypoint. None hides it."""
        self.start = None if lon_lat is None else (float(lon_lat[0]), float(lon_lat[1]))
        self.redraw()

    def set_drone(self, lon_lat, trail_point=True, limit=4000):
        """Where the aircraft is now, and where it has been. None clears both."""
        if lon_lat is None:
            self.drone, self.trail = None, []
        else:
            self.drone = (float(lon_lat[0]), float(lon_lat[1]))
            if trail_point:
                self.trail.append(self.drone)
                if len(self.trail) > limit:        # a long flight must not grow without bound
                    del self.trail[:len(self.trail) - limit]
        self.redraw()

    def set_volumes(self, geojson, live=None):
        """The mission's declared airspace, drawn under the route so the route stays readable.

        geojson is OperationalIntent.geojson(). live names the volume the aircraft should be in
        right now, which is drawn a little stronger while a flight is under way."""
        self.volumes = []
        for feature in (geojson or {}).get("features", []):
            ring = feature.get("geometry", {}).get("coordinates", [[]])[0]
            props = feature.get("properties", {})
            self.volumes.append({"ring": [(float(x), float(y)) for x, y in ring],
                                 "name": props.get("name"), "kind": props.get("kind")})
        self.volume_live = live
        self.redraw()

    def set_fences(self, fences):
        """Geofences: dicts with a ring of (lon, lat), a name and a severity."""
        self.fences = list(fences or [])
        self.redraw()

    def set_traffic(self, aircraft, conflicts=()):
        """Real aircraft to draw, as dicts from adsb.Aircraft.as_dict, plus which ones conflict.

        The map holds no opinion about any of it: what counts as a conflict is decided where the
        route is known, and arrives here as a set of addresses to paint differently."""
        self.traffic = list(aircraft or [])
        self.traffic_conflicts = set(conflicts or ())
        self.redraw()

    def _waypoint_at(self, sx, sy, radius=10):
        """Which waypoint is under the cursor, nearest first, or -1."""
        best, best_d = -1, radius * radius
        for i, w in enumerate(self.waypoints):
            x, y = self.to_screen(w["lon"], w["lat"])
            d = (x - sx) ** 2 + (y - sy) ** 2
            if d <= best_d:
                best, best_d = i, d
        return best

    # ---- mouse -------------------------------------------------------------------------------

    def _drawing(self, event):
        return self._draw_mode.get() or (event.state & 0x0001)      # 0x0001 is Shift

    def _press(self, event):
        # While a pick is waiting, a click on a waypoint is a pick there, not a selection.
        if self.waypoints_enabled and not self.on_pick:
            hit = self._waypoint_at(event.x, event.y)
            if hit >= 0:
                self.selected = hit
                if self.on_waypoint_select:
                    self.on_waypoint_select(hit)
                self._drag = ("waypoint", event.x, event.y, hit, 0)
                self.redraw()
                return
        self._drag = ("box" if self._drawing(event) else "pan", event.x, event.y,
                      self.centre[0], self.centre[1])

    def _motion(self, event):
        if not self._drag:
            return
        kind, x0, y0, clon, clat = self._drag
        if kind == "waypoint":
            lon, lat = self.to_lonlat(event.x, event.y)
            self.waypoints[clon]["lon"], self.waypoints[clon]["lat"] = lon, lat
            # Mark it as a real drag, so the release does not read as a click.
            self._drag = (kind, x0, y0, clon, 1)
            if self.on_waypoint_move:
                self.on_waypoint_move(clon, lon, lat)
            self.redraw()
        elif kind == "pan":
            w, h = self._size()
            cx, cy = lonlat_to_world(clon, clat, self.zoom)
            self.centre = world_to_lonlat(cx - (event.x - x0), cy - (event.y - y0), self.zoom)
            self.redraw()
        else:
            a = self.to_lonlat(x0, y0)
            b = self.to_lonlat(event.x, event.y)
            self.box = (min(a[0], b[0]), min(a[1], b[1]), max(a[0], b[0]), max(a[1], b[1]))
            self.redraw()

    def _release(self, event):
        drag = self._drag
        self._drag = None
        if drag and drag[0] == "waypoint":
            return
        if self.waypoints_enabled and drag and drag[0] == "pan" \
                and abs(event.x - drag[1]) < 3 and abs(event.y - drag[2]) < 3:
            # A click on empty map, not a pan: a pick when one was asked for, else a waypoint.
            if self.on_pick:
                pick, self.on_pick = self.on_pick, None
                pick(*self.to_lonlat(event.x, event.y))
                return
            if self.on_waypoint_add:
                lon, lat = self.to_lonlat(event.x, event.y)
                self.on_waypoint_add(lon, lat)
            return
        drawing = drag and drag[0] == "box"
        if drawing and self.box and self.on_box:
            west, south, east, north = self.box
            if (east - west) > 1e-6 and (north - south) > 1e-6:
                self.on_box(self.box)

    def _find(self):
        q = self.search.get().strip()
        if not q or requests is None:
            return
        def work():
            try:
                r = requests.get(NOMINATIM, params={"q": q, "format": "json", "limit": 1},
                                 headers={"User-Agent": USER_AGENT}, timeout=20)
                hits = r.json()
                if hits:
                    h = hits[0]
                    south, north, west, east = (float(v) for v in h["boundingbox"])
                    self.queue.put(("found", (west, south, east, north)))
                else:
                    self.queue.put(("message", "no place called '%s'" % q))
            except Exception as e:
                self.queue.put(("message", "search failed: %s" % e))
        threading.Thread(target=work, daemon=True).start()

    # ---- tiles -------------------------------------------------------------------------------

    def _tile(self, z, x, y):
        """The tile image, or None while it is being fetched."""
        key = (z, x, y)
        if key in self.images:
            return self.images[key]
        if key in self.pending or self.pool is None:
            return None
        self.pending.add(key)
        self.pool.submit(self._fetch, key)
        return None

    def _fetch(self, key):
        z, x, y = key
        path = os.path.join(CACHE, str(z), str(x), "%d.png" % y)
        data = None
        try:
            if os.path.isfile(path):
                with open(path, "rb") as f:
                    data = f.read()
            else:
                r = requests.get(TILE_URL.format(z=z, x=x, y=y),
                                 headers={"User-Agent": USER_AGENT}, timeout=20)
                if r.status_code == 200:
                    data = r.content
                    os.makedirs(os.path.dirname(path), exist_ok=True)
                    with open(path, "wb") as f:
                        f.write(data)
        except Exception:
            data = None                      # a missing tile is a grey square, never an error box
        self.queue.put(("tile", (key, data)))

    def _pump(self):
        try:
            while True:
                kind, payload = self.queue.get_nowait()
                if kind == "tile":
                    key, data = payload
                    self.pending.discard(key)
                    if data:
                        try:
                            self.images[key] = ImageTk.PhotoImage(Image.open(io.BytesIO(data)))
                        except Exception:
                            pass
                    self._dirty = True
                elif kind == "found":
                    self.set_box(payload, fit=True)
                    if self.on_box:
                        self.on_box(payload)
                elif kind == "message":
                    self.readout.configure(text=payload)
        except queue.Empty:
            pass
        if getattr(self, "_dirty", False):
            self._dirty = False
            self.redraw()
        self.after(80, self._pump)

    # ---- drawing -----------------------------------------------------------------------------

    def redraw(self):
        if requests is None:
            return
        c = self.canvas
        c.delete("map")
        w, h = self._size()
        ox, oy = self._origin()
        n = 2 ** self.zoom

        first_x, first_y = int(math.floor(ox / TILE)), int(math.floor(oy / TILE))
        last_x, last_y = int(math.floor((ox + w) / TILE)), int(math.floor((oy + h) / TILE))
        for ty in range(first_y, last_y + 1):
            if ty < 0 or ty >= n:
                continue
            for tx in range(first_x, last_x + 1):
                img = self._tile(self.zoom, tx % n, ty)
                px, py = tx * TILE - ox, ty * TILE - oy
                if img:
                    c.create_image(px, py, image=img, anchor="nw", tags="map")
                else:
                    c.create_rectangle(px, py, px + TILE, py + TILE, fill="#e8edf1",
                                       outline="#dde3e8", tags="map")

        if self.outline and len(self.outline) >= 3:
            pts = []
            for lon, lat in self.outline:
                pts.extend(self.to_screen(lon, lat))
            c.create_polygon(pts, outline="#1f6feb", fill="", width=2, tags="map")

        if self.waypoints:
            # The route first, so the markers sit on top of it.
            if len(self.waypoints) > 1:
                line = []
                for w in self.waypoints:
                    line.extend(self.to_screen(w["lon"], w["lat"]))
                c.create_line(line, fill="#1f6feb", width=3, arrow="last",
                              arrowshape=(14, 16, 5), tags="map")
            for i, w in enumerate(self.waypoints):
                x, y = self.to_screen(w["lon"], w["lat"])
                r = 9 if i == self.selected else 7
                fill = "#ffcf4d" if i == self.selected else "#e8582c"
                c.create_oval(x - r, y - r, x + r, y + r, fill=fill, outline="#1b1f23",
                              width=2, tags="map")
                c.create_text(x, y, text=str(i + 1), fill="#1b1f23",
                              font=("Segoe UI", 7, "bold"), tags="map")
                if w["name"]:
                    c.create_text(x + r + 3, y - r - 2, text=w["name"], anchor="w",
                                  fill="#1b1f23", font=("Segoe UI", 8, "bold"), tags="map")
                    c.create_text(x + r + 2, y - r - 3, text=w["name"], anchor="w",
                                  fill="#ffffff", font=("Segoe UI", 8), tags="map")

        if self.start:
            # The start: a square, joined to the first waypoint by the climb out to it.
            x, y = self.to_screen(*self.start)
            if self.waypoints:
                fx, fy = self.to_screen(self.waypoints[0]["lon"], self.waypoints[0]["lat"])
                c.create_line(x, y, fx, fy, fill="#2ea043", width=2, dash=(4, 3), tags="map")
            c.create_rectangle(x - 7, y - 7, x + 7, y + 7, fill="#2ea043", outline="#0b2e13",
                               width=2, tags="map")
            c.create_text(x, y, text="S", fill="#ffffff", font=("Segoe UI", 7, "bold"), tags="map")

        if len(self.trail) > 1:
            # Where it actually went, under the planned route so the plan stays readable.
            flown = []
            for lon, lat in self.trail:
                flown.extend(self.to_screen(lon, lat))
            c.create_line(flown, fill="#8bd17c", width=2, tags="map")

        for fence in self.fences:
            ring = fence.get("ring") or []
            if len(ring) < 3:
                continue
            points = []
            for lon, lat in ring:
                points.extend(self.to_screen(lon, lat))
            colour = "#d92b2b" if fence.get("severity") == "no-fly" else "#e07000"
            c.create_polygon(points, fill=colour, stipple="gray25", outline=colour, width=2,
                             tags="map")
            if fence.get("name"):
                x, y = self.to_screen(*ring[0])
                c.create_text(x + 4, y - 6, text=fence["name"], anchor="w", fill=colour,
                              font=("Segoe UI", 8, "bold"), tags="map")

        for volume in self.volumes:
            ring = volume["ring"]
            if len(ring) < 3:
                continue
            points = []
            for lon, lat in ring:
                points.extend(self.to_screen(lon, lat))
            live = self.volume_live is not None and volume["name"] == self.volume_live
            c.create_polygon(points, fill="#1f6feb", stipple="gray50" if live else "gray12",
                             outline="#1f6feb" if live else "#6ea8fe", width=2 if live else 1,
                             tags="map")

        for craft in self.traffic:
            self._draw_aircraft(c, craft)

        if self.drone:
            x, y = self.to_screen(*self.drone)
            c.create_oval(x - 7, y - 7, x + 7, y + 7, fill="#2ea043", outline="#0b2e13",
                          width=2, tags="map")
            c.create_oval(x - 2, y - 2, x + 2, y + 2, fill="#ffffff", outline="", tags="map")

        if self.box:
            west, south, east, north = self.box
            x0, y0 = self.to_screen(west, north)
            x1, y1 = self.to_screen(east, south)
            c.create_rectangle(x0, y0, x1, y1, outline="#e8582c", width=2, tags="map")
            c.create_rectangle(x0, y0, x1, y1, outline="", fill="#e8582c", stipple="gray12",
                               tags="map")
            self.readout.configure(text="%.4f %.4f to %.4f %.4f   %.1f x %.1f km"
                                        % (west, south, east, north, *self._km(self.box)))
        elif self.waypoints_enabled:
            self.readout.configure(text="%d waypoint(s)" % len(self.waypoints))
        else:
            self.readout.configure(text="no area marked")

    def _draw_aircraft(self, c, craft):
        """One aircraft: a chevron pointing where it is going, labelled with who and how high.

        A chevron rather than a dot because a track is half of what matters about traffic. An
        aircraft on the ground is drawn small and grey: there are dozens of them at an airport and
        none of them are in anybody's way."""
        try:
            lon, lat = float(craft["lon"]), float(craft["lat"])
        except (KeyError, TypeError, ValueError):
            return
        x, y = self.to_screen(lon, lat)
        if x < -40 or y < -40 or x > self.canvas.winfo_width() + 40 or \
                y > self.canvas.winfo_height() + 40:
            return                                  # off screen, and labels are not free

        on_ground = bool(craft.get("on_ground"))
        conflict = craft.get("icao24") in self.traffic_conflicts
        if on_ground:
            c.create_oval(x - 3, y - 3, x + 3, y + 3, fill="#9aa5b1", outline="", tags="map")
            return

        track = craft.get("track_deg")
        heading = math.radians(float(track) if track is not None else 0.0)
        size = 9.0
        # A chevron: nose, then the two trailing corners, then a notch, in screen coordinates
        # where x is east and y is SOUTH, which is why the sine and cosine land where they do.
        shape = [(0.0, -size), (size * 0.62, size * 0.7), (0.0, size * 0.3),
                 (-size * 0.62, size * 0.7)]
        points = []
        for dx, dy in shape:
            points.extend((x + dx * math.cos(heading) - dy * math.sin(heading),
                           y + dx * math.sin(heading) + dy * math.cos(heading)))
        fill = "#d92b2b" if conflict else "#f2c744"
        c.create_polygon(points, fill=fill, outline="#241a00", width=1, tags="map")
        if conflict:
            c.create_oval(x - 16, y - 16, x + 16, y + 16, outline="#d92b2b", width=2, tags="map")

        label = craft.get("callsign") or craft.get("icao24") or ""
        height = craft.get("agl_m")
        if height is not None:
            label = "%s  %.0f m agl" % (label, height)
        elif craft.get("altitude_m") is not None:
            label = "%s  %.0f m" % (label, craft["altitude_m"])
        if label:
            for dx, dy, colour in ((1, 1, "#000000"), (0, 0, "#ffffff")):
                c.create_text(x + 12 + dx, y - 10 + dy, text=label, anchor="w", fill=colour,
                              font=("Segoe UI", 8, "bold" if conflict else "normal"), tags="map")

    @staticmethod
    def _km(box):
        west, south, east, north = box
        mid = math.radians((south + north) / 2.0)
        return ((east - west) * 111.32 * math.cos(mid), (north - south) * 110.57)
