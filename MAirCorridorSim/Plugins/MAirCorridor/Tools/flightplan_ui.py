"""flightplan_ui.py - draw a flight, name its waypoints, fly it.

    py -3.10 flightplan_ui.py
    py -3.10 flightplan_ui.py missions/patrol.json

Click the map to place waypoints, drag one to move it, give each a name, a height and a speed, then
press Fly. The drone takes off, flies them in order and lands.

HEIGHT IS PER WAYPOINT AND SO IS ITS MEANING. A waypoint is either a height ABOVE THE GROUND beneath
it, which this reads from the landscape's own heightmap, or an altitude ABOVE SEA LEVEL. A cruise leg
can hold one altitude while an inspection leg hugs a hillside, and the window shows both numbers for
every waypoint so there is never any doubt which is which.

IT DOES NOT FLY THE DRONE ITSELF. Pressing Fly runs fly_mission.py, the same command you would type,
and streams its output here. The mission on disk is the whole truth: anything flown from this window
can be flown again from a terminal, or on a schedule, with no window at all.
"""
import json
import os
import queue
import sys
import tempfile
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from toolpaths import HERE, tool_command

# Where the traffic snapshot goes, which is also the default an M-Air Live Traffic actor looks at.
# Under the user's temporary folder rather than in the repository: it is rewritten every twenty
# seconds and is worthless a minute later.
TRAFFIC_SNAPSHOT = os.path.join(tempfile.gettempdir(), "maircorridor_traffic.json")

# Which way the aircraft points while it flies, and so where its cameras look. The words the
# runner understands are the keys; these are what reads sensibly in a window.
YAW_LABELS = {"forward": "the way it is flying",
              "waypoint": "the waypoint it is flying to",
              "free": "wherever it already faces"}
sys.path.insert(0, HERE)

import adsb                                                                  # noqa: E402
import airspace                                                              # noqa: E402
import geofences                                                             # noqa: E402
from flightplan import (AGL, MSL, SIM, DEFAULT_PLAN, Mission, Terrain, Waypoint,  # noqa: E402
                        built_drones)
from geodata_ui import Runner                                               # noqa: E402
from uikit import ScrollColumn, fit_to_screen                              # noqa: E402
from mapview import MapView                                                 # noqa: E402

MISSIONS = os.path.join(HERE, "missions")


class App(tk.Tk):
    def __init__(self, mission_path=None):
        super().__init__()
        self.title("MCity Digital Air Command - Flight planner")
        # Tall enough to show every panel without scrolling where the screen allows it.
        fit_to_screen(self, 1360, 1340, 1120, 640)
        try:
            ttk.Style().theme_use("vista")
        except tk.TclError:
            pass

        self.mission = Mission()
        self.path = None
        self.terrain = None
        self.runner = Runner()
        self.dirty = False

        self._build()
        self._terrain()
        if mission_path:
            self._open(mission_path)
        else:
            self._refresh()
        self.after(60, self._pump)
        self.protocol("WM_DELETE_WINDOW", self._close)

    # ---- layout ------------------------------------------------------------------------------

    def _build(self):
        outer = ttk.Frame(self, padding=8)
        outer.pack(fill="both", expand=True)

        self._mission_bar(outer)
        # The flight box goes in before the map and the panels, at the bottom, because pack hands
        # out room in the order things are packed: last in is first squeezed off a short screen,
        # and the Fly button is the one thing that must never be.
        self._log(outer)
        body = ttk.Frame(outer)
        body.pack(fill="both", expand=True, pady=(8, 0))
        self._map(body)
        self._side(body)

    def _mission_bar(self, parent):
        box = ttk.LabelFrame(parent, text="Mission", padding=8)
        box.pack(fill="x")
        line = ttk.Frame(box)
        line.pack(fill="x")
        ttk.Label(line, text="Name").pack(side="left")
        self.name = tk.StringVar(value="mission")
        ttk.Entry(line, textvariable=self.name, width=22).pack(side="left", padx=(4, 12))
        for text, cmd in (("New", self._new), ("Open...", self._open_dialog),
                          ("Save", self._save), ("Save as...", self._save_as)):
            ttk.Button(line, text=text, command=cmd, width=9).pack(side="left", padx=2)

        ttk.Label(line, text="Drone").pack(side="left", padx=(16, 2))
        self.drone = tk.StringVar(value="Drone1")
        ttk.Entry(line, textvariable=self.drone, width=12).pack(side="left")
        ttk.Label(line, text="Scene").pack(side="left", padx=(12, 2))
        self.scene = tk.StringVar(value="scene_mcity.jsonc")
        ttk.Entry(line, textvariable=self.scene, width=22).pack(side="left")

        line2 = ttk.Frame(box)
        line2.pack(fill="x", pady=(6, 0))
        ttk.Label(line2, text="Landscape plan").pack(side="left")
        self.plan = tk.StringVar(value=DEFAULT_PLAN)
        ttk.Entry(line2, textvariable=self.plan, width=74).pack(side="left", padx=4)
        ttk.Button(line2, text="Browse...", command=self._pick_plan).pack(side="left")
        ttk.Label(line2, text="gives the ground that heights above ground are measured from",
                  foreground="#666").pack(side="left", padx=8)

    def _map(self, parent):
        box = ttk.LabelFrame(parent, text="Route", padding=6)
        box.pack(side="left", fill="both", expand=True)
        self.map = MapView(box, height=360, waypoints=True)
        self.map.on_waypoint_add = self._map_add
        self.map.on_waypoint_move = self._map_move
        self.map.on_waypoint_select = self._map_select
        self.map.pack(fill="both", expand=True)

    def _side(self, parent):
        # Taller than a 1080 line screen has room for, so it scrolls rather than running off.
        column = ScrollColumn(parent)
        column.pack(side="left", fill="y", padx=(8, 0))
        box = column.inner

        table = ttk.LabelFrame(box, text="Waypoints", padding=6)
        table.pack(fill="both", expand=True)
        cols = ("n", "name", "height", "ref", "speed", "hold")
        self.tree = ttk.Treeview(table, columns=cols, show="headings", height=10,
                                 selectmode="browse")
        for c, t, w in (("n", "#", 28), ("name", "Name", 110), ("height", "Height", 60),
                        ("ref", "Ref", 44), ("speed", "m/s", 48), ("hold", "Hold", 44)):
            self.tree.heading(c, text=t)
            self.tree.column(c, width=w, anchor="w" if c == "name" else "center")
        self.tree.pack(fill="both", expand=True)
        self.tree.bind("<<TreeviewSelect>>", lambda e: self._row_selected())

        row = ttk.Frame(table)
        row.pack(fill="x", pady=(6, 0))
        for text, cmd, w in (("Add", self._add_centre, 6), ("Delete", self._delete, 7),
                             ("Up", self._up, 5), ("Down", self._down, 6),
                             ("Copy", self._duplicate, 6)):
            ttk.Button(row, text=text, command=cmd, width=w).pack(side="left", padx=1)

        edit = ttk.LabelFrame(box, text="Selected waypoint", padding=6)
        edit.pack(fill="x", pady=(8, 0))
        self.fields = {}
        for label, key, width in (("Name", "name", 18), ("Longitude", "lon", 18),
                                  ("Latitude", "lat", 18), ("Height (m)", "height", 10),
                                  ("Speed (m/s)", "speed", 10), ("Hold (s)", "hold", 10)):
            line = ttk.Frame(edit)
            line.pack(fill="x", pady=1)
            ttk.Label(line, text=label, width=12, anchor="w").pack(side="left")
            var = tk.StringVar()
            self.fields[key] = var
            e = ttk.Entry(line, textvariable=var, width=width)
            e.pack(side="left")
            e.bind("<Return>", lambda ev: self._apply())
        line = ttk.Frame(edit)
        line.pack(fill="x", pady=1)
        ttk.Label(line, text="Height is", width=12, anchor="w").pack(side="left")
        self.fields["ref"] = tk.StringVar(value=AGL)
        ttk.Combobox(line, textvariable=self.fields["ref"], width=16, state="readonly",
                     values=(AGL, MSL, SIM)).pack(side="left")
        ttk.Button(edit, text="Apply", command=self._apply).pack(anchor="e", pady=(4, 0))
        self.ground = ttk.Label(edit, text="", foreground="#444")
        self.ground.pack(anchor="w")

        # WHERE THE DRONE STARTS. Blank leaves it to the scene config, which every mission using
        # that scene shares; a start here moves the drone for this mission's flight only.
        start = ttk.LabelFrame(box, text="Start", padding=6)
        start.pack(fill="x", pady=(8, 0))
        self.start_fields = {}
        for label, key, width in (("Longitude", "lon", 18), ("Latitude", "lat", 18),
                                  ("Height (m)", "height", 10)):
            line = ttk.Frame(start)
            line.pack(fill="x", pady=1)
            ttk.Label(line, text=label, width=12, anchor="w").pack(side="left")
            var = tk.StringVar()
            self.start_fields[key] = var
            e = ttk.Entry(line, textvariable=var, width=width)
            e.pack(side="left")
            e.bind("<Return>", lambda ev: self._start_apply())
        line = ttk.Frame(start)
        line.pack(fill="x", pady=1)
        ttk.Label(line, text="Height is", width=12, anchor="w").pack(side="left")
        self.start_fields["ref"] = tk.StringVar(value=AGL)
        ttk.Combobox(line, textvariable=self.start_fields["ref"], width=16, state="readonly",
                     values=(AGL, MSL, SIM)).pack(side="left")
        row = ttk.Frame(start)
        row.pack(fill="x", pady=(4, 0))
        for text, cmd, w in (("Pick on map", self._start_pick, 11),
                             ("At first waypoint", self._start_first, 16),
                             ("Apply", self._start_apply, 6), ("Scene's", self._start_clear, 7)):
            ttk.Button(row, text=text, command=cmd, width=w).pack(side="left", padx=1)
        self.start_note = ttk.Label(start, text="", foreground="#444", wraplength=330,
                                    justify="left")
        self.start_note.pack(anchor="w", pady=(4, 0))

        setup = ttk.LabelFrame(box, text="Defaults and flight", padding=6)
        setup.pack(fill="x", pady=(8, 0))
        line = ttk.Frame(setup)
        line.pack(fill="x")
        ttk.Label(line, text="New waypoints:").pack(side="left")
        self.def_height = tk.StringVar(value="60")
        ttk.Entry(line, textvariable=self.def_height, width=6).pack(side="left", padx=2)
        ttk.Label(line, text="m").pack(side="left")
        self.def_ref = tk.StringVar(value=AGL)
        ttk.Combobox(line, textvariable=self.def_ref, width=5, state="readonly",
                     values=(AGL, MSL, SIM)).pack(side="left", padx=4)
        self.def_speed = tk.StringVar(value="12")
        ttk.Entry(line, textvariable=self.def_speed, width=5).pack(side="left", padx=2)
        ttk.Label(line, text="m/s").pack(side="left")

        line2 = ttk.Frame(setup)
        line2.pack(fill="x", pady=(4, 0))
        ttk.Label(line2, text="Land at the end").pack(side="left")
        self.land = tk.BooleanVar(value=True)
        cb = ttk.Checkbutton(line2, variable=self.land)
        cb.state(["!alternate"])
        cb.pack(side="left", padx=4)

        line3 = ttk.Frame(setup)
        line3.pack(fill="x", pady=(4, 0))
        ttk.Label(line3, text="Cameras look").pack(side="left")
        self.yaw = tk.StringVar(value=YAW_LABELS["forward"])
        yaw_box = ttk.Combobox(line3, textvariable=self.yaw, width=24, state="readonly",
                               values=tuple(YAW_LABELS.values()))
        yaw_box.pack(side="left", padx=4)
        yaw_box.bind("<<ComboboxSelected>>", lambda _e: self._yaw_chosen())

        self.summary = ttk.Label(setup, text="", foreground="#444", wraplength=330, justify="left")
        self.summary.pack(anchor="w", pady=(6, 0))

        air = ttk.LabelFrame(box, text="Real traffic overhead", padding=6)
        air.pack(fill="x", pady=(8, 0))
        self.traffic_on = tk.BooleanVar(value=False)
        tb = ttk.Checkbutton(air, text="Show aircraft from the ADS-B feed",
                             variable=self.traffic_on, command=self._traffic_toggled)
        tb.state(["!alternate"])
        tb.pack(anchor="w")

        sep = ttk.Frame(air)
        sep.pack(fill="x", pady=(4, 0))
        ttk.Label(sep, text="Too close:", width=9, anchor="w").pack(side="left")
        self.sep_h = tk.StringVar(value="1000")
        ttk.Entry(sep, textvariable=self.sep_h, width=6).pack(side="left", padx=2)
        ttk.Label(sep, text="m across,").pack(side="left")
        self.sep_v = tk.StringVar(value="300")
        ttk.Entry(sep, textvariable=self.sep_v, width=5).pack(side="left", padx=2)
        ttk.Label(sep, text="m up").pack(side="left")

        datum = ttk.Frame(air)
        datum.pack(fill="x", pady=(4, 0))
        ttk.Label(datum, text="Altitude:", width=9, anchor="w").pack(side="left")
        # Blank means the geoid model at each aircraft's position, which is what it should be.
        # A number replaces it with a constant, for checking against a known point.
        self.traffic_offset = tk.StringVar(value="")
        ttk.Entry(datum, textvariable=self.traffic_offset, width=6).pack(side="left", padx=2)
        ttk.Label(datum, text="m (blank: geoid model)").pack(side="left")
        ttk.Button(datum, text="Replay...", width=9,
                   command=self._traffic_replay).pack(side="right")

        feed_line = ttk.Frame(air)
        feed_line.pack(fill="x", pady=(4, 0))
        self.traffic_share = tk.BooleanVar(value=True)
        sb = ttk.Checkbutton(feed_line, text="Also write a snapshot for the level to fly",
                             variable=self.traffic_share)
        sb.state(["!alternate"])
        sb.pack(anchor="w")

        self.traffic_readout = ttk.Label(air, text="Not looking.", foreground="#666",
                                         wraplength=330, justify="left")
        self.traffic_readout.pack(anchor="w", pady=(6, 0))

        rec = ttk.LabelFrame(box, text="Record", padding=6)
        rec.pack(fill="x", pady=(8, 0))
        self.track = tk.BooleanVar(value=True)
        cb = ttk.Checkbutton(rec, text="Track the flight and measure deviation", variable=self.track)
        cb.state(["!alternate"])
        cb.pack(anchor="w")

        # One switch for the whole payload, because picking streams one at a time is the wrong
        # default for a flight meant to be used as data afterwards.
        self.everything = tk.BooleanVar(value=False)
        eb = ttk.Checkbutton(rec, text="Record everything the drone carries",
                             variable=self.everything, command=self._everything_toggled)
        eb.state(["!alternate"])
        eb.pack(anchor="w")

        # The simulated Ouster lidar, off unless asked for: it is 25.6 MB a scan at 5 scans a
        # second, so a long flight is hundreds of GB (fly_mission.py --lidar).
        self.lidar = tk.BooleanVar(value=False)
        lb = ttk.Checkbutton(rec, text="Lidar (Ouster OS-1-256, about 128 MB a second)",
                             variable=self.lidar)
        lb.state(["!alternate"])
        lb.pack(anchor="w")

        # M-City as the photogrammetric scan or as Mcity's digital twin (MAirMcityViewSubsystem).
        mline = ttk.Frame(rec)
        mline.pack(fill="x", pady=(4, 0))
        ttk.Label(mline, text="M-City", width=8, anchor="w").pack(side="left")
        self.mcity = tk.StringVar(value="as it is")
        ttk.Combobox(mline, textvariable=self.mcity, width=14, state="readonly",
                     values=("as it is", "scan", "digital twin")).pack(side="left")

        # Which aircraft flies: the scene's own, or a drone built by the aircraft builder, by its
        # robot config (Tools/drone_configs.py; fly_mission.py --robot).
        dline = ttk.Frame(rec)
        dline.pack(fill="x", pady=(4, 0))
        ttk.Label(dline, text="Drone", width=8, anchor="w").pack(side="left")
        self.aircraft = tk.StringVar(value="as the scene has it")
        ttk.Combobox(dline, textvariable=self.aircraft, width=24, state="readonly",
                     values=["as the scene has it"] + [n[len("robot_"):-len(".jsonc")]
                                                       for n in built_drones()]).pack(side="left")

        line = ttk.Frame(rec)
        line.pack(fill="x", pady=(4, 0))
        ttk.Label(line, text="Camera", width=8, anchor="w").pack(side="left")
        self.camera = ttk.Combobox(line, width=20, values=())
        self.camera.pack(side="left")
        self.video = tk.BooleanVar(value=True)
        vb = ttk.Checkbutton(line, text="video", variable=self.video)
        vb.state(["!alternate"])
        vb.pack(side="left", padx=4)
        self.frames = tk.BooleanVar(value=False)
        fb = ttk.Checkbutton(line, text="stills", variable=self.frames)
        fb.state(["!alternate"])
        fb.pack(side="left")

        line2 = ttk.Frame(rec)
        line2.pack(fill="x", pady=(4, 0))
        ttk.Label(line2, text="Sensors", width=8, anchor="w").pack(side="left")
        self.sensors = ttk.Entry(line2, width=24)
        self.sensors.pack(side="left")
        ttk.Button(line2, text="List...", width=7,
                   command=self._capabilities).pack(side="left", padx=4)
        self.pickers = [self.camera, self.sensors]
        ttk.Label(rec, text="Cameras and sensors are whatever the robot config gives this drone. "
                            "List asks the simulator, which must be running. Stills are lossless "
                            "and depth is always written that way. Everything lands in one folder "
                            "per flight with a manifest describing it.",
                  foreground="#666", wraplength=330, justify="left").pack(anchor="w", pady=(4, 0))

    def _log(self, parent):
        box = ttk.LabelFrame(parent, text="Flight", padding=6)
        box.pack(side="bottom", fill="x", pady=(8, 0))
        bar = ttk.Frame(box)
        bar.pack(fill="x", pady=(0, 4))
        self.fly_button = ttk.Button(bar, text="Fly", command=lambda: self._fly(False), width=10)
        self.fly_button.pack(side="left")
        ttk.Button(bar, text="Check only", command=lambda: self._fly(True), width=11).pack(side="left", padx=4)
        self.stop = ttk.Button(bar, text="Stop", command=self.runner.cancel, state="disabled", width=8)
        self.stop.pack(side="left")
        ttk.Label(bar, text="The simulation must already be playing.",
                  foreground="#666").pack(side="left", padx=10)
        self.status = ttk.Label(bar, text="Ready", foreground="#444")
        self.status.pack(side="right")
        self.live = ttk.Label(bar, text="", foreground="#0a6", font=("Segoe UI", 9, "bold"))
        # The operation's state while a flight is under way: Activated, Nonconforming and so on.
        self.state_label = ttk.Label(bar, text="", font=("Segoe UI", 9, "bold"))
        self.live.pack(side="right", padx=10)

        self.text = tk.Text(box, height=7, wrap="none", font=("Consolas", 9),
                            background="#101418", foreground="#d8dee4")
        scroll = ttk.Scrollbar(box, command=self.text.yview)
        self.text.configure(yscrollcommand=scroll.set)
        self.text.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        for tag, colour in (("step", "#7fd1ff"), ("cmd", "#9aa5b1"), ("good", "#8bd17c"),
                            ("warn", "#e8c468"), ("error", "#ff8a7a")):
            self.text.tag_configure(tag, foreground=colour)

    # ---- terrain -----------------------------------------------------------------------------

    def _terrain(self):
        try:
            self.terrain = Terrain(self.plan.get().strip())
        except Exception as e:
            self.terrain = None
            self._append("cannot read the landscape plan: %s\n" % e, "error")
            return
        if not self.mission.waypoints:
            self.map.fit(self.terrain.extent_lonlat())

    def _pick_plan(self):
        p = filedialog.askopenfilename(parent=self, title="Landscape plan",
                                       filetypes=[("Landscape plan", "*.json"), ("All", "*.*")])
        if p:
            self.plan.set(p)
            self._terrain()
            self._refresh()

    # ---- waypoints ---------------------------------------------------------------------------

    def _selected(self):
        sel = self.tree.selection()
        return int(sel[0]) if sel else -1

    def _map_add(self, lon, lat):
        try:
            height = float(self.def_height.get())
            speed = float(self.def_speed.get())
        except ValueError:
            messagebox.showwarning("Not a number", "The default height and speed must be numbers.",
                                   parent=self)
            return
        w = Waypoint(self.mission.unique_name(), lon, lat, height, self.def_ref.get(), speed)
        self.mission.waypoints.append(w)
        self.dirty = True
        self._refresh(select=len(self.mission.waypoints) - 1)

    def _map_move(self, index, lon, lat):
        if 0 <= index < len(self.mission.waypoints):
            self.mission.waypoints[index].lon = lon
            self.mission.waypoints[index].lat = lat
            self.dirty = True
            self._refresh(select=index, keep_view=True)

    def _map_select(self, index):
        self._refresh(select=index, keep_view=True)

    def _add_centre(self):
        lon, lat = self.map.centre
        self._map_add(lon, lat)

    # ---- start -------------------------------------------------------------------------------

    def _start_show(self):
        """The start box, its note and the map's start marker, from the mission. The fields are
        only rewritten when the start itself changed, so a value being typed is not lost to an
        unrelated redraw."""
        s = self.mission.start
        if s != getattr(self, "_start_shown", "unset"):
            self._start_shown = dict(s) if s else None
            for key, value in (("lon", "%.6f" % float(s["lon"]) if s else ""),
                               ("lat", "%.6f" % float(s["lat"]) if s else ""),
                               ("height", "%g" % float(s.get("height", 0.0)) if s else "")):
                self.start_fields[key].set(value)
            self.start_fields["ref"].set((s or {}).get("reference", AGL))
        self.map.set_start((float(s["lon"]), float(s["lat"])) if s else None)
        if not self.terrain:
            self.start_note.configure(text="")
            return
        try:
            if s:
                north, east, down = self.mission.start_ned(self.terrain)
                ground = self.terrain.ground_elevation(float(s["lon"]), float(s["lat"]))
                text = ("The ground here is %.1f m above sea level; the drone starts at north "
                        "%.1f, east %.1f, down %.1f. Only the landscape counts as ground: on a "
                        "building, a tree or the M-City scan, give a height that clears it."
                        % (ground, north, east, down))
            else:
                spawn = airspace.spawn_from_scene(
                    os.path.join(os.path.dirname(HERE), "AirSim", "sim_config", self.mission.scene),
                    self.mission.drone)
                text = "None set: the drone starts where %s puts it%s." % (
                    self.mission.scene,
                    " (north %.1f, east %.1f, down %.1f)" % spawn if spawn else "")
            self.start_note.configure(text=text, foreground="#444")
        except Exception as e:
            self.start_note.configure(text=str(e), foreground="#b00")

    def _set_start(self, lon, lat):
        try:
            height = float(self.start_fields["height"].get() or 0.0)
        except ValueError:
            height = 0.0
        self.mission.start = {"lon": round(float(lon), 7), "lat": round(float(lat), 7),
                              "height": height, "reference": self.start_fields["ref"].get() or AGL}
        self.dirty = True
        self._refresh(select=self._selected(), keep_view=True)

    def _start_apply(self):
        try:
            lon = float(self.start_fields["lon"].get())
            lat = float(self.start_fields["lat"].get())
        except ValueError:
            messagebox.showwarning("Not a position",
                                   "The start's longitude and latitude must be numbers.", parent=self)
            return
        self._set_start(lon, lat)

    def _start_pick(self):
        self.map.on_pick = self._set_start
        self._append("click the map where the drone should start\n", "step")

    def _start_first(self):
        if not self.mission.waypoints:
            return
        w = self.mission.waypoints[0]
        self.start_fields["height"].set("0")
        self.start_fields["ref"].set(AGL)
        self._set_start(w.lon, w.lat)

    def _start_clear(self):
        self.mission.start = None
        self.dirty = True
        self._refresh(select=self._selected(), keep_view=True)

    def _delete(self):
        i = self._selected()
        if i >= 0:
            del self.mission.waypoints[i]
            self.dirty = True
            self._refresh(select=min(i, len(self.mission.waypoints) - 1))

    def _move(self, delta):
        i = self._selected()
        j = i + delta
        if 0 <= i < len(self.mission.waypoints) and 0 <= j < len(self.mission.waypoints):
            w = self.mission.waypoints
            w[i], w[j] = w[j], w[i]
            self.dirty = True
            self._refresh(select=j)

    def _up(self):
        self._move(-1)

    def _down(self):
        self._move(1)

    def _duplicate(self):
        i = self._selected()
        if i >= 0:
            src = self.mission.waypoints[i]
            copy = Waypoint(self.mission.unique_name(), src.lon, src.lat, src.height,
                            src.reference, src.speed, src.hold_s)
            self.mission.waypoints.insert(i + 1, copy)
            self.dirty = True
            self._refresh(select=i + 1)

    def _apply(self):
        i = self._selected()
        if i < 0:
            return
        w = self.mission.waypoints[i]
        try:
            name = self.fields["name"].get().strip()
            lon = float(self.fields["lon"].get())
            lat = float(self.fields["lat"].get())
            height = float(self.fields["height"].get())
            speed = float(self.fields["speed"].get())
            hold = float(self.fields["hold"].get())
        except ValueError:
            messagebox.showwarning("Not a number",
                                   "Longitude, latitude, height, speed and hold must be numbers.",
                                   parent=self)
            return
        w.name, w.lon, w.lat = name or w.name, lon, lat
        w.height, w.speed, w.hold_s = height, speed, hold
        w.reference = self.fields["ref"].get()
        self.dirty = True
        self._refresh(select=i, keep_view=True)

    def _row_selected(self):
        i = self._selected()
        if i < 0:
            return
        w = self.mission.waypoints[i]
        self.fields["name"].set(w.name)
        self.fields["lon"].set("%.6f" % w.lon)
        self.fields["lat"].set("%.6f" % w.lat)
        self.fields["height"].set("%g" % w.height)
        self.fields["speed"].set("%g" % w.speed)
        self.fields["hold"].set("%g" % w.hold_s)
        self.fields["ref"].set(w.reference)
        self.map.selected = i
        self.map.redraw()
        ground = self.terrain.ground_elevation(w.lon, w.lat) if self.terrain else None
        elev = w.elevation(self.terrain) if self.terrain else None
        if ground is None:
            self.ground.configure(text="This point is outside the landscape.", foreground="#b00")
        else:
            self.ground.configure(
                text="ground %.1f m, flies at %.1f m above sea level (%.1f m above ground)"
                     % (ground, elev, elev - ground), foreground="#444")

    # ---- refresh -----------------------------------------------------------------------------

    def _yaw_mode(self):
        """The word the runner wants for whatever is showing in the box."""
        chosen = self.yaw.get()
        for key, label in YAW_LABELS.items():
            if label == chosen:
                return key
        return "forward"

    def _yaw_chosen(self):
        self.dirty = True
        self._refresh(keep_view=True)

    def _refresh(self, select=-1, keep_view=False):
        self.mission.name = self.name.get().strip() or "mission"
        self.mission.drone = self.drone.get().strip() or "Drone1"
        self.mission.scene = self.scene.get().strip()
        self.mission.plan = self.plan.get().strip()
        self.mission.land_at_end = bool(self.land.get())
        self.mission.yaw_mode = self._yaw_mode()

        self.tree.delete(*self.tree.get_children())
        for i, w in enumerate(self.mission.waypoints):
            self.tree.insert("", "end", iid=str(i),
                             values=(i + 1, w.name, "%g" % w.height, w.reference,
                                     "%g" % w.speed, "%g" % w.hold_s))
        if 0 <= select < len(self.mission.waypoints):
            self.tree.selection_set(str(select))
            self.tree.see(str(select))

        self._airspace()
        self.map.set_waypoints(self.mission.waypoints, selected=select,
                               fit=not keep_view and select < 0 and len(self.mission.waypoints) > 1)
        self._start_show()
        if select >= 0:
            self._row_selected()

        if self.terrain and self.mission.waypoints:
            try:
                length = self.mission.distance_m(self.terrain)
                secs = self.mission.duration_s(self.terrain)
                problems = self.mission.check(self.terrain)
                text = "%d waypoint(s), %.2f km, about %d min %02d s" % (
                    len(self.mission.waypoints), (length or 0) / 1000.0, int(secs // 60), int(secs % 60))
                if problems:
                    text += "\n" + "\n".join(problems[:4])
                verdict = getattr(self, "verdict", None)
                if verdict is not None:
                    if verdict.rejections:
                        text += "\nWould be REJECTED: " + verdict.rejections[0]
                    else:
                        text += "\nStrategic check: nothing in the way"
                    for line in (verdict.advisories + verdict.unknown)[:2]:
                        text += "\n" + line
                rejected = bool(verdict is not None and verdict.rejections)
                self.summary.configure(text=text,
                                       foreground="#b00" if (problems or rejected) else "#444")
            except Exception as e:
                self.summary.configure(text=str(e), foreground="#b00")
        else:
            self.summary.configure(text="Click the map to place a waypoint.", foreground="#444")

    # ---- files -------------------------------------------------------------------------------

    def _new(self):
        if not self._confirm_discard():
            return
        self.mission = Mission()
        self.path = None
        self.name.set("mission")
        self.dirty = False
        self._refresh()

    def _open_dialog(self):
        if not self._confirm_discard():
            return
        os.makedirs(MISSIONS, exist_ok=True)
        p = filedialog.askopenfilename(parent=self, title="Open mission", initialdir=MISSIONS,
                                       filetypes=[("Mission", "*.json"), ("All", "*.*")])
        if p:
            self._open(p)

    def _open(self, path):
        try:
            self.mission = Mission.load(path)
        except Exception as e:
            messagebox.showerror("Cannot open", str(e), parent=self)
            return
        self.path = path
        self.name.set(self.mission.name)
        self.drone.set(self.mission.drone)
        self.scene.set(self.mission.scene)
        self.plan.set(self.mission.plan)
        self.land.set(self.mission.land_at_end)
        self.yaw.set(YAW_LABELS.get(getattr(self.mission, "yaw_mode", "forward"),
                                    YAW_LABELS["forward"]))
        self.dirty = False
        self._terrain()
        self._refresh()
        self.map.set_waypoints(self.mission.waypoints, fit=True)
        self._append("opened %s\n" % path, "good")

    def _save(self):
        if not self.path:
            return self._save_as()
        self._refresh(select=self._selected(), keep_view=True)
        self.mission.save(self.path)
        self.dirty = False
        self._append("saved %s\n" % self.path, "good")

    def _save_as(self):
        os.makedirs(MISSIONS, exist_ok=True)
        p = filedialog.asksaveasfilename(parent=self, title="Save mission", initialdir=MISSIONS,
                                         defaultextension=".json",
                                         initialfile=(self.name.get().strip() or "mission") + ".json",
                                         filetypes=[("Mission", "*.json")])
        if p:
            self.path = p
            self._save()

    def _confirm_discard(self):
        return (not self.dirty) or messagebox.askokcancel(
            "Unsaved changes", "This mission has changes that are not saved. Discard them?",
            parent=self)

    # ---- flying ------------------------------------------------------------------------------

    def _fly(self, check_only):
        if self.runner.busy:
            messagebox.showinfo("Busy", "A flight is already running.", parent=self)
            return
        if not self.mission.waypoints:
            messagebox.showwarning("Nothing to fly", "Place some waypoints first.", parent=self)
            return
        self._refresh(select=self._selected(), keep_view=True)
        if not self.path or self.dirty:
            self._save()
            if not self.path:
                return
        argv = tool_command("fly_mission.py", self.path)
        self.runner.graceful = False
        if check_only:
            argv.append("--dry-run")
        else:
            # A flight is the one thing here that must be allowed to finish writing: Stop asks
            # it down its stdin and waits, rather than killing it and orphaning the video.
            self.runner.graceful = True
            argv.append("--stop-on-stdin")
            if not self.track.get():
                argv.append("--no-track")
            if self.everything.get():
                argv.append("--all")
            else:
                camera = self.camera.get().strip()
                if camera:
                    argv += ["--record", camera]
                for name in (n.strip() for n in self.sensors.get().split(",")):
                    if name:
                        argv += ["--log-sensor", name]
            if not self.video.get():
                argv.append("--no-video")
            if self.frames.get():
                argv.append("--frames")
            if self.lidar.get():
                argv.append("--lidar")
            view = {"scan": "scan", "digital twin": "twin"}.get(self.mcity.get())
            if view:
                argv += ["--mcity", view]
            if self.aircraft.get() != "as the scene has it":
                argv += ["--robot", self.aircraft.get()]
            self.map.set_drone(None)          # a new flight starts with a clean trail
            self.worst = 0.0
            self.live.configure(text="")
        self.runner.start([("Check" if check_only else "Flight", argv)])
        self.stop.configure(state="normal")
        self.fly_button.configure(state="disabled")
        self.status.configure(text="Flying" if not check_only else "Checking", foreground="#0a6")

    # ---- log and polling ---------------------------------------------------------------------

    def _append(self, text, tag=None):
        if getattr(self, "capabilities", None) is not None:
            self.capabilities += text
        self.text.insert("end", text, tag or ())
        self.text.see("end")

    def _read_capabilities(self):
        """Pull the sensor list out of what the last run printed, if it was asked for one."""
        blob = getattr(self, "capabilities", None)
        self.capabilities = None
        if not blob or "{" not in blob:
            return
        try:
            data = json.loads(blob[blob.index("{"):blob.rindex("}") + 1])
        except ValueError:
            return
        sensors = data.get("sensors") or {}
        kinds = data.get("kinds") or {}
        enabled = data.get("enabled") or {}
        off = [n for n in sensors if not enabled.get(n, True)]
        cameras = []
        for name, streams in sensors.items():
            if name in off:
                continue                    # a sensor switched off in the robot config publishes
                                            # nothing, so offering it would only disappoint
            for stream in streams:
                if (kinds.get(name, {}).get(stream) or
                        ("image" if stream.endswith("_camera") else "data")) == "image":
                    cameras.append("%s:%s" % (name, stream))
        if off:
            self._append("switched off in the robot config, so not offered: %s\n"
                         % ", ".join(sorted(off)), "warn")
        self.camera.configure(values=tuple(cameras))
        if self.everything.get():
            self._everything_toggled()
        if cameras and not self.camera.get():
            self.camera.set(cameras[0])
        others = [n for n, streams in sensors.items()
                  if n not in off and not any(s.endswith("_camera") for s in streams)]
        if others and not self.sensors.get():
            self.sensors.insert(0, ", ".join(others))
        self._append("the drone carries: %s\n"
                     % (", ".join("%s (%s)" % (n, ", ".join(s)) for n, s in sensors.items())
                        or "no sensors"), "good")

    def _pump(self):
        try:
            while True:
                kind, a, b = self.runner.queue.get_nowait()
                if kind == "line":
                    if a.startswith("STATE "):
                        self._state(a[6:])
                        continue
                    if a.startswith("TRACK "):
                        self._track(a[6:])
                        continue
                    self._append(a, b)
                elif kind == "step":
                    self._append("\n== %s ==\n" % a, "step")
                elif kind == "finished":
                    self._read_capabilities()
                    self.stop.configure(state="disabled")
                    self.fly_button.configure(state="normal")
                    self.status.configure(text="Done" if a else "Stopped",
                                          foreground="#0a6" if a else "#c33")
        except queue.Empty:
            pass
        self.after(60, self._pump)

    STATE_COLOURS = {"Accepted": "#444", "Activated": "#0a6", "Nonconforming": "#e07000",
                     "Contingent": "#c33", "Ended": "#444", "Rejected": "#c33",
                     "Cancelled": "#c33", "Withdrawn": "#444"}

    def _state(self, payload):
        """A change in the operation's lifecycle, as the runner reports it."""
        try:
            change = json.loads(payload)
        except ValueError:
            return
        to = change.get("to", "")
        if not self.state_label.winfo_ismapped():
            self.state_label.pack(side="right", padx=10)
        self.state_label.configure(text=to, foreground=self.STATE_COLOURS.get(to, "#444"))
        self._append("%s: %s\n" % (to, change.get("reason", "")),
                     "error" if to in ("Contingent", "Rejected") else
                     "warn" if to == "Nonconforming" else "good")

    def _airspace(self):
        """Draw the airspace this mission declares, so it can be seen while it is planned."""
        if not self.terrain or len(self.mission.waypoints) < 2:
            self.map.set_volumes(None)
            return None
        try:
            spawn = airspace.start_of(self.mission, self.terrain,
                                      os.path.join(os.path.dirname(HERE), "AirSim", "sim_config"))
            intent = airspace.OperationalIntent.from_mission(self.mission, self.terrain,
                                                             spawn_ned=spawn)
        except Exception:
            self.map.set_volumes(None)
            return None
        self.map.set_volumes(intent.geojson())
        # The strategic check, as the route is drawn: a mission that will be rejected should
        # say so here, not when somebody presses Fly with the editor in Play.
        try:
            fences = geofences.load_geofences(self.terrain)
            self.map.set_fences([{"ring": f.ring, "name": f.name, "severity": f.severity}
                                 for f in fences])
            others = geofences.scheduled_missions(self.terrain, exclude_path=self.path)
            self.verdict = geofences.check(intent, self.mission, self.terrain, fences=fences,
                                           other_missions=others)
        except Exception as e:
            self.verdict = None
            self._append("strategic check could not run: %s\n" % e, "warn")
        return intent

    def _track(self, payload):
        """One position report from the flight: put it on the map and say how far off it is.

        The runner owns the connection to the simulator and prints these; this window only draws
        them. That keeps the flight running whether or not anything is watching, and means a flight
        started from a terminal can be watched here by reading the same lines."""
        try:
            row = json.loads(payload)
        except ValueError:
            return
        if not self.terrain:
            return
        try:
            lon, lat = self.terrain.lonlat_from_ned(row["north"], row["east"])
        except Exception:
            return
        self.map.set_drone((lon, lat))
        verdict = row.get("conformance") or {}
        if verdict.get("volume") and verdict.get("volume") != self.map.volume_live:
            self.map.volume_live = verdict["volume"]
        dev = row.get("deviation")
        if dev is None:
            return
        self.worst = max(getattr(self, "worst", 0.0), dev)
        elevation = self.terrain.elevation_from_down(row["down"])
        leg = row.get("leg", 0)
        name = ""
        if 0 <= leg < len(self.mission.waypoints) - 1:
            name = " on %s to %s" % (self.mission.waypoints[leg].name,
                                     self.mission.waypoints[leg + 1].name)
        self.live.configure(
            text="off path %.1f m (worst %.1f m), %.0f m above sea level%s"
                 % (dev, self.worst, elevation, name),
            foreground="#c33" if dev > 25.0 else ("#e07000" if dev > 10.0 else "#0a6"))

    def _everything_toggled(self):
        """Picking individual streams is pointless while everything is being recorded."""
        state = "disabled" if self.everything.get() else "normal"
        for widget in getattr(self, "pickers", []):
            try:
                widget.configure(state="readonly" if (state == "normal" and
                                                      widget is self.camera) else state)
            except Exception:
                pass

    # ---- real traffic ------------------------------------------------------------------------

    def _traffic_toggled(self):
        """Start or stop the feed. Starting it costs credits, so it is never on by default."""
        if not self.traffic_on.get():
            if getattr(self, "feed", None):
                self.feed.stop()
                self.feed = None
            self.map.set_traffic([], ())
            self.traffic_readout.configure(text="Not looking.", foreground="#666")
            return
        if not self.terrain:
            messagebox.showinfo("No landscape", "Traffic is placed against the landscape, so a "
                                                "plan has to load first.", parent=self)
            self.traffic_on.set(False)
            return
        # One feed, two readers: the map here and the M-Air Live Traffic actor in the level,
        # which reads this file. Two feeds would spend twice the credits on the same aircraft.
        snapshot = TRAFFIC_SNAPSHOT if self.traffic_share.get() else None
        self.feed = adsb.Feed(self.terrain, offset=self._traffic_datum(),
                              replay=getattr(self, "traffic_file", None), snapshot=snapshot)
        self.feed.start()
        where = "replaying %s" % os.path.basename(self.traffic_file) \
            if getattr(self, "traffic_file", None) else "asking OpenSky every %.0f s" \
            % self.feed.interval
        if snapshot:
            self._append("the level can fly these: point an M-Air Live Traffic actor at "
                         "%s\n" % snapshot, "good")
        self.traffic_readout.configure(text="Looking: %s." % where, foreground="#444")
        self._append("traffic: %s, box %.3f %.3f to %.3f %.3f\n"
                     % (where, *self.feed.box), "step")
        self._traffic_tick()

    def _traffic_replay(self):
        """Use a recorded feed instead of the network, which is how this gets worked on offline."""
        path = filedialog.askopenfilename(parent=self, title="A recorded traffic feed",
                                          filetypes=[("Recorded feed", "*.jsonl"), ("All", "*.*")])
        if not path:
            return
        self.traffic_file = path
        if self.traffic_on.get():
            self.traffic_on.set(False)
            self._traffic_toggled()
            self.traffic_on.set(True)
        self._traffic_toggled()

    def _traffic_datum(self):
        """The geoid model, or a constant if one has been typed into the altitude box."""
        text = self.traffic_offset.get().strip()
        try:
            offset = float(text) if text else None
        except ValueError:
            offset = None
        return adsb.Datum.default(offset)

    @staticmethod
    def _traffic_number(var, fallback):
        try:
            return float(var.get())
        except (ValueError, AttributeError):
            return fallback

    def _traffic_tick(self):
        """Once a second: move the aircraft on, work out what is in the way, redraw.

        Once a second rather than once a poll because the aircraft are dead reckoned between
        reports, so they move smoothly while the network is only asked every twenty seconds."""
        if not self.traffic_on.get() or not getattr(self, "feed", None):
            return
        feed = self.feed
        feed.offset = self._traffic_datum()
        aircraft = feed.now()
        clashes = adsb.conflicts(self.mission, self.terrain, feed.live_aircraft(),
                                 self._traffic_number(self.sep_h, 1000.0),
                                 self._traffic_number(self.sep_v, 300.0), feed.offset)
        self.map.set_traffic(aircraft, [c["aircraft"].icao24 for c in clashes])

        over = sum(1 for a in aircraft if a.get("over_landscape"))
        bits = ["%d aircraft, %d over the landscape" % (len(aircraft), over)]
        if feed.credits_left is not None:
            bits.append("%d credits left today" % feed.credits_left)
        if feed.error:
            bits.append(feed.error)
        text = ", ".join(bits) + "."
        colour = "#444"
        if clashes:
            worst = clashes[0]
            text += ("  %d too close: %s is %.0f m from the route and %+.0f m on %s."
                     % (len(clashes), worst["aircraft"].name, worst["horizontal_m"],
                        worst["vertical_m"], worst["leg_name"]))
            colour = "#c33"
        elif not feed.updates:
            text += "  Waiting for the first report."
        # A FEED THAT HAS STOPPED IS NOT A CLEAR SKY. Say so before anything else, and never
        # let "nothing too close" stand on a picture that has gone stale.
        health = feed.status()
        if health["state"] in ("degraded", "stale", "down"):
            text = "TRAFFIC PICTURE %s: %s. %s" % (health["state"].upper(), health["reason"],
                                                     text)
            if not clashes:
                text += "  Nothing shown as too close does NOT mean nothing is there."
            colour = "#e07000" if health["state"] == "degraded" else "#c33"
        self.traffic_readout.configure(text=text, foreground=colour)
        self.after(1000, self._traffic_tick)

    def _capabilities(self):
        """Ask the simulator what this drone actually carries, and offer it."""
        if not self.path:
            self._save()
            if not self.path:
                return
        if self.runner.busy:
            messagebox.showinfo("Busy", "Something is already running.", parent=self)
            return
        self._append("asking the simulator what the drone carries "
                     "(it must be running and in Play)\n", "step")
        self.runner.start([("Capabilities",
                            tool_command("fly_mission.py", self.path,
                                         "--list-capabilities"))])
        self.capabilities = ""
        self.stop.configure(state="normal")
        self.fly_button.configure(state="disabled")

    def _close(self):
        if getattr(self, "feed", None):
            self.feed.stop()
        if self.runner.busy and not messagebox.askokcancel(
                "Still flying", "A flight is still running. Close anyway and stop it?", parent=self):
            return
        if not self._confirm_discard():
            return
        self.runner.cancel()
        self.destroy()


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    app = App(args[0] if args else None)
    if "--fly" in sys.argv:
        # Started to watch a flight rather than to draw one: take off as soon as the window is up.
        app.after(400, lambda: app._fly(False))
    app.mainloop()


if __name__ == "__main__":
    main()
