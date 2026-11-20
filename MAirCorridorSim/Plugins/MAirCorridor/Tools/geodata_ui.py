"""geodata_ui.py - the whole terrain pipeline in one window.

    py -3.10 geodata_ui.py

Pick an area, download elevation, build the Unreal landscape, download the imagery. The four command
line tools in this folder do the work; this only fills in their arguments and shows what they print.

WHY A WINDOW AND NOT A README. The commands are long, their arguments have to agree with each other,
and the output of one is the input of the next: the elevation folder feeds the landscape build, and
the landscape plan feeds the imagery download. Typing that three times in a row is where mistakes
come from. Here the area is entered once, the paths follow from one working folder, and each step
hands the next what it made.

IT SHELLS OUT RATHER THAN IMPORTING. The tools stay the truth: this runs exactly the command a
terminal would, streams its output into the log, and reports the exit code. Nothing is reimplemented
here, so the tools and the window cannot drift apart, and anything done here can be repeated by
copying the command out of the log.

NO UNREAL REQUIRED. This is plain Python with tkinter, which ships with Python, so it runs on a
machine that has no engine installed: download overnight, build the plan, and import it later.
"""
import json
import os
import queue
import signal
import subprocess
import sys
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import geodata_common as gc
from mapview import MapView
from uikit import ScrollColumn, fit_to_screen

from toolpaths import HERE, tool_command, tool_exists
SETTINGS = os.path.join(HERE, ".geodata_ui.json")

TOOLS = {
    "3dep": "download_3dep.py",
    "copernicus": "download_copernicus_dem.py",
    "landscape": "build_landscape.py",
    "naip": "download_naip.py",
}

# label -> (tool, product argument), in the order they are offered.
ELEVATION_SOURCES = [
    ("USGS 3DEP 1 m lidar (best detail, gaps)", "3dep", "1m"),
    ("USGS 3DEP 1/9 arc-second, about 3 m", "3dep", "19"),
    ("USGS 3DEP 1/3 arc-second, about 10 m (seamless)", "3dep", "13"),
    ("USGS 3DEP 1 arc-second, about 30 m (seamless)", "3dep", "1"),
    ("USGS 3DEP original product resolution", "3dep", "opr"),
    ("Copernicus GLO-30, worldwide", "copernicus", "30"),
    ("Copernicus GLO-90, worldwide", "copernicus", "90"),
]


# ---------------------------------------------------------------------------------------------
# Running the tools
# ---------------------------------------------------------------------------------------------

class Runner:
    """Runs a queue of commands one after another, streaming their output.

    One thread per run, a queue back to the window, and the window polls it. Tkinter is not thread
    safe, so nothing here touches a widget: the thread only posts messages."""

    def __init__(self):
        self.queue = queue.Queue()
        self.process = None
        self.cancelled = False
        self.thread = None
        # ASK BEFORE KILLING. A flight holds open files: a video with no index yet, JSON lines
        # with a buffer, a manifest not written. Killing it outright leaves a folder of rubble,
        # which is exactly what happened before this existed. With this on, a stop asks the
        # process to wind up and only kills it if it will not.
        self.graceful = False
        self.grace_seconds = 12.0

    @property
    def busy(self):
        return self.thread is not None and self.thread.is_alive()

    def start(self, steps):
        """steps: a list of (title, argv). A step that fails stops the rest."""
        if self.busy:
            return False
        self.cancelled = False
        self.thread = threading.Thread(target=self._run, args=(steps,), daemon=True)
        self.thread.start()
        return True

    def cancel(self):
        self.cancelled = True
        p = self.process
        if not p or p.poll() is not None:
            return
        if self.graceful:
            # DOWN ITS STDIN, NOT BY SIGNAL. A Windows console event can only reach a process
            # that shares the sender's console, and these are started with CREATE_NO_WINDOW, so
            # each one has a console of its own and GenerateConsoleCtrlEvent never finds it.
            # Measured, not assumed: CTRL_BREAK_EVENT was ignored and the grace period ran out
            # every time. A line on stdin always arrives, on either platform.
            try:
                self.queue.put(("line", "\nAsked it to finish and close its files...\n", "warn"))
                if p.stdin:
                    try:
                        p.stdin.write("stop\n")
                        p.stdin.flush()
                    except (OSError, ValueError):
                        pass
                    try:
                        p.stdin.close()          # EOF says the same thing
                    except (OSError, ValueError):
                        pass
                elif os.name != "nt":
                    p.terminate()
                p.wait(timeout=self.grace_seconds)
                return
            except subprocess.TimeoutExpired:
                self.queue.put(("line", "it did not stop in %.0f s, killing it\n"
                                % self.grace_seconds, "error"))
            except Exception:
                pass
        if p.poll() is None:
            if os.name == "nt":
                # The tools spawn nothing, but a download can sit in a socket read; /T is the
                # reliable way to end it and anything it did start.
                subprocess.run(["taskkill", "/F", "/T", "/PID", str(p.pid)],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            else:
                p.kill()

    def _run(self, steps):
        ok = True
        for title, argv in steps:
            if self.cancelled:
                self.queue.put(("line", "\nCancelled.\n", "warn"))
                ok = False
                break
            self.queue.put(("step", title, None))
            self.queue.put(("line", "%s\n" % " ".join(_quote(a) for a in
                                                   [os.path.basename(argv[0])] + argv[1:]), "cmd"))
            code = self._one(argv)
            if self.cancelled:
                # A stop is not a failure. _one reports -1 for one, and calling something the
                # person asked for "failed" reads like a fault in the tool.
                self.queue.put(("line", "\n%s: stopped.\n" % title, "warn"))
                ok = False
                break
            if code != 0:
                self.queue.put(("line", "\n%s failed (exit %d).\n" % (title, code), "error"))
                ok = False
                break
            self.queue.put(("line", "\n%s: done.\n" % title, "good"))
        self.queue.put(("finished", ok, None))

    def _one(self, argv):
        flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
        try:
            self.process = subprocess.Popen(argv, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                            stdin=subprocess.PIPE if self.graceful else None,
                                            text=True, bufsize=1, encoding="utf-8",
                                            errors="replace", cwd=HERE, creationflags=flags)
        except OSError as e:
            self.queue.put(("line", "cannot run %s: %s\n" % (argv[0], e), "error"))
            return 1
        for line in self.process.stdout:
            # The tools redraw a progress line with a carriage return; keep only the last of those.
            self.queue.put(("line", line.split("\r")[-1], None))
        self.process.wait()
        return -1 if self.cancelled else self.process.returncode


def _quote(a):
    return '"%s"' % a if " " in a else a


# ---------------------------------------------------------------------------------------------
# The window
# ---------------------------------------------------------------------------------------------

def window_title():
    """The title, which a release of these tools on their own names in release.json beside
    the executable (build_tools.py writes it); everywhere else, the suite this window is in."""
    try:
        with open(os.path.join(HERE, "release.json"), encoding="utf-8") as f:
            return json.load(f)["title"]
    except (OSError, ValueError, KeyError):
        return "MCity Digital Air Command - Terrain and imagery"


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(window_title())
        fit_to_screen(self, 1120, 1100, 980, 600)
        try:
            ttk.Style().theme_use("vista")
        except tk.TclError:
            pass

        self.vars = {}
        self.runner = Runner()
        self._build()
        self._load()
        self.after(300, self._to_map)
        self.after(60, self._pump)
        self.protocol("WM_DELETE_WINDOW", self._close)

    # ---- layout ------------------------------------------------------------------------------

    def _build(self):
        outer = ttk.Frame(self, padding=10)
        outer.pack(fill="both", expand=True)

        # The output, with Run everything on it, goes in first and at the bottom so a short screen
        # cannot squeeze it off; the numbered steps above it scroll instead.
        self._log(outer)
        steps = ScrollColumn(outer, stretch=True)
        steps.pack(side="top", fill="both", expand=True)
        panels = steps.inner
        self._area(panels)
        self._project(panels)
        two = ttk.Frame(panels)
        two.pack(fill="x", pady=(8, 0))
        self._elevation(two)
        self._landscape(two)
        self._imagery(panels)

    def _var(self, key, value):
        v = tk.StringVar(value=value) if not isinstance(value, bool) else tk.BooleanVar(value=value)
        self.vars[key] = v
        return v

    def _row(self, parent, label, key, default, width=22, hint=""):
        row = ttk.Frame(parent)
        row.pack(fill="x", pady=2)
        ttk.Label(row, text=label, width=20, anchor="w").pack(side="left")
        ttk.Entry(row, textvariable=self._var(key, default), width=width).pack(side="left")
        if hint:
            ttk.Label(row, text=hint, foreground="#666").pack(side="left", padx=(8, 0))
        return row

    def _area(self, parent):
        box = ttk.LabelFrame(parent, text="1. Area of interest", padding=8)
        box.pack(fill="x")

        mode = self._var("area_mode", "aoi")
        line = ttk.Frame(box)
        line.pack(fill="x")
        ttk.Radiobutton(line, text="Polygon", variable=mode, value="aoi",
                        command=self._area_mode).pack(side="left")
        e = ttk.Entry(line, textvariable=self._var("aoi", ""), width=62)
        e.pack(side="left", padx=6)
        self.aoi_entry = e
        ttk.Button(line, text="Browse...", command=self._pick_aoi).pack(side="left")
        ttk.Label(line, text="KML or KMZ from Google Earth or any GIS",
                  foreground="#666").pack(side="left", padx=8)

        line2 = ttk.Frame(box)
        line2.pack(fill="x", pady=(4, 0))
        ttk.Radiobutton(line2, text="Box", variable=mode, value="bbox",
                        command=self._area_mode).pack(side="left")
        self.bbox_entries = []
        for key, label, default in (("west", "west", "-83.8199"), ("south", "south", "42.2052"),
                                    ("east", "east", "-83.0212"), ("north", "north", "42.4125")):
            ttk.Label(line2, text=label).pack(side="left", padx=(8, 2))
            ent = ttk.Entry(line2, textvariable=self._var("bbox_" + key, default), width=11)
            ent.pack(side="left")
            self.bbox_entries.append(ent)
        ttk.Label(line2, text="degrees, WGS84", foreground="#666").pack(side="left", padx=8)

        line3 = ttk.Frame(box)
        line3.pack(fill="x", pady=(4, 0))
        ttk.Label(line3, text="Grow by", width=20, anchor="w").pack(side="left")
        ttk.Entry(line3, textvariable=self._var("buffer_m", "0"), width=10).pack(side="left")
        ttk.Label(line3, text="metres on every side", foreground="#666").pack(side="left", padx=8)
        ttk.Button(line3, text="Show on map", command=self._to_map).pack(side="left", padx=(16, 0))

        self.map = MapView(box, on_box=self._from_map, height=240)
        # Fixed height, no expand: the output log is what should grow when the window does.
        self.map.pack(fill="x", pady=(6, 0))

    def _project(self, parent):
        box = ttk.LabelFrame(parent, text="2. Where the work goes", padding=8)
        box.pack(fill="x", pady=(8, 0))
        line = ttk.Frame(box)
        line.pack(fill="x")
        ttk.Label(line, text="Working folder", width=20, anchor="w").pack(side="left")
        ttk.Entry(line, textvariable=self._var("work", os.path.join(HERE, "work")),
                  width=62).pack(side="left", padx=(0, 6))
        ttk.Button(line, text="Browse...", command=self._pick_work).pack(side="left")
        ttk.Button(line, text="Open", command=self._open_work).pack(side="left", padx=4)
        self._row(box, "Name", "name", "corridor", width=24,
                  hint="names the plan, the heightmaps and the imagery tiles")

    def _elevation(self, parent):
        box = ttk.LabelFrame(parent, text="3. Elevation", padding=8)
        box.pack(side="left", fill="both", expand=True)
        for i, (label, tool, product) in enumerate(ELEVATION_SOURCES):
            default = product in ("1m", "13")
            cb = ttk.Checkbutton(box, text=label,
                                 variable=self._var("src_%s_%s" % (tool, product), default))
            cb.state(["!alternate"])
            cb.pack(anchor="w")
        ttk.Label(box, text="Pick the finest first and a seamless one to fill its gaps.",
                  foreground="#666", wraplength=380).pack(anchor="w", pady=(6, 0))
        line = ttk.Frame(box)
        line.pack(fill="x", pady=(8, 0))
        ttk.Button(line, text="Check sizes",
                   command=lambda: self._try(lambda: self._steps_elevation(True))).pack(side="left")
        ttk.Button(line, text="Download",
                   command=lambda: self._try(lambda: self._steps_elevation(False))).pack(side="left", padx=6)

    def _landscape(self, parent):
        box = ttk.LabelFrame(parent, text="4. Landscape", padding=8)
        box.pack(side="left", fill="both", expand=True, padx=(8, 0))
        self._row(box, "Metres per quad", "metres", "3", width=8,
                  hint="1 for ground level, 3 for flight")
        self._row(box, "Largest segment", "max_vertices", "8161", width=8, hint="vertices per side")
        self._row(box, "World Partition grid", "wp_grid", "4", width=8, hint="0 leaves it unsplit")

        line = ttk.Frame(box)
        line.pack(fill="x", pady=2)
        ttk.Label(line, text="Datum", width=20, anchor="w").pack(side="left")
        ttk.Combobox(line, textvariable=self._var("datum", "NAD83"), width=10, state="readonly",
                     values=("NAD83", "WGS84")).pack(side="left")
        ttk.Label(line, text="NAD83 matches USGS in North America",
                  foreground="#666").pack(side="left", padx=8)

        line2 = ttk.Frame(box)
        line2.pack(fill="x", pady=2)
        ttk.Label(line2, text="Origin", width=20, anchor="w").pack(side="left")
        ttk.Combobox(line2, textvariable=self._var("origin", "area"), width=10, state="readonly",
                     values=("area", "projected")).pack(side="left")
        ttk.Label(line2, text="'area' puts the corner at 0,0", foreground="#666").pack(side="left", padx=8)

        mask = ttk.Checkbutton(box, text="Blank terrain outside the polygon",
                               variable=self._var("mask", True))
        mask.state(["!alternate"])
        mask.pack(anchor="w", pady=(4, 0))
        line3 = ttk.Frame(box)
        line3.pack(fill="x", pady=(8, 0))
        ttk.Button(line3, text="Plan only",
                   command=lambda: self._try(lambda: [self._step_landscape(True)])).pack(side="left")
        ttk.Button(line3, text="Build",
                   command=lambda: self._try(lambda: [self._step_landscape(False)])).pack(side="left", padx=6)

    def _imagery(self, parent):
        box = ttk.LabelFrame(parent, text="5. Aerial imagery (NAIP, United States)", padding=8)
        box.pack(fill="x", pady=(8, 0))
        line = ttk.Frame(box)
        line.pack(fill="x")
        for label, key, default, width in (("Metres per pixel", "naip_metres", "0.5", 8),
                                           ("Tile pixels", "naip_tile", "8192", 8),
                                           ("Request pixels", "naip_request", "2048", 8),
                                           ("Parallel requests", "naip_workers", "4", 6)):
            ttk.Label(line, text=label).pack(side="left", padx=(0, 4))
            ttk.Entry(line, textvariable=self._var(key, default), width=width).pack(side="left", padx=(0, 12))
        ttk.Button(line, text="Estimate",
                   command=lambda: self._try(lambda: [self._step_imagery(True)])).pack(side="left")
        ttk.Button(line, text="Download",
                   command=lambda: self._try(lambda: [self._step_imagery(False)])).pack(side="left", padx=6)
        ttk.Label(box, text="Aligned to the landscape plan, so one pixel sits on the ground it was "
                            "taken of. NAIP covers the lower 48 states only.",
                  foreground="#666").pack(anchor="w", pady=(6, 0))

    def _log(self, parent):
        box = ttk.LabelFrame(parent, text="Output", padding=8)
        box.pack(side="bottom", fill="both", expand=True, pady=(8, 0))

        bar = ttk.Frame(box)
        bar.pack(fill="x", pady=(0, 6))
        self.run_all = ttk.Button(bar, text="Run everything", command=self._run_all)
        self.run_all.pack(side="left")
        self.cancel = ttk.Button(bar, text="Cancel", command=self.runner.cancel, state="disabled")
        self.cancel.pack(side="left", padx=6)
        ttk.Button(bar, text="Clear", command=lambda: self._clear()).pack(side="left")
        self.progress = ttk.Progressbar(bar, mode="indeterminate", length=180)
        self.progress.pack(side="right")
        self.status = ttk.Label(bar, text="Ready", foreground="#444")
        self.status.pack(side="right", padx=10)

        wrap = ttk.Frame(box)
        wrap.pack(fill="both", expand=True)
        self.text = tk.Text(wrap, wrap="none", height=10, font=("Consolas", 9),
                            background="#101418", foreground="#d8dee4", insertbackground="#d8dee4")
        scroll = ttk.Scrollbar(wrap, command=self.text.yview)
        self.text.configure(yscrollcommand=scroll.set)
        self.text.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        self.text.tag_configure("step", foreground="#7fd1ff", font=("Consolas", 9, "bold"))
        self.text.tag_configure("cmd", foreground="#9aa5b1")
        self.text.tag_configure("good", foreground="#8bd17c")
        self.text.tag_configure("warn", foreground="#e8c468")
        self.text.tag_configure("error", foreground="#ff8a7a")

    # ---- fields ------------------------------------------------------------------------------

    def _get(self, key):
        v = self.vars[key].get()
        return v.strip() if isinstance(v, str) else v

    def _area_mode(self):
        polygon = self._get("area_mode") == "aoi"
        self.aoi_entry.configure(state="normal" if polygon else "disabled")
        for e in self.bbox_entries:
            e.configure(state="disabled" if polygon else "normal")

    def _area_args(self):
        if self._get("area_mode") == "aoi":
            aoi = self._get("aoi")
            if not aoi or not os.path.isfile(aoi):
                raise ValueError("Choose a KML or KMZ file for the area, or switch to Box.")
            args = ["--aoi", aoi]
        else:
            try:
                box = [float(self._get("bbox_" + k)) for k in ("west", "south", "east", "north")]
            except ValueError:
                raise ValueError("The box needs four numbers in degrees.")
            if not (box[0] < box[2] and box[1] < box[3]):
                raise ValueError("The box must read west, south, east, north, with west < east "
                                 "and south < north.")
            args = ["--bbox"] + [repr(v) for v in box]
        buffer_m = self._get("buffer_m")
        if buffer_m and float(buffer_m) != 0.0:
            args += ["--buffer-m", buffer_m]
        return args

    def _work(self, *parts):
        work = self._get("work")
        if not work:
            raise ValueError("Choose a working folder.")
        return os.path.join(work, *parts)

    def _tool(self, key):
        return tool_command(TOOLS[key])

    # ---- steps -------------------------------------------------------------------------------

    def _steps_elevation(self, dry):
        steps = []
        for label, tool, product in ELEVATION_SOURCES:
            if not self._get("src_%s_%s" % (tool, product)):
                continue
            argv = self._tool(tool) + self._area_args() + ["--out", self._work("dem_cache")]
            argv += ["--product", product] if tool == "3dep" else ["--resolution", product]
            if dry:
                argv.append("--dry-run")
            steps.append(("%s%s" % (label, " (sizes only)" if dry else ""), argv))
        if not steps:
            raise ValueError("Tick at least one elevation source.")
        return steps

    def _step_landscape(self, plan_only):
        name = self._get("name") or "landscape"
        dem = self._work("dem_cache")
        if not os.path.isdir(dem):
            raise ValueError("No elevation yet: %s does not exist. Download it first, or point the "
                             "working folder at one that has a dem_cache." % dem)
        argv = self._tool("landscape") + ["--dem", dem] + self._area_args() + [
            "--out", self._work("landscape"), "--name", name,
            "--metres", self._get("metres"), "--datum", self._get("datum"),
            "--max-vertices", self._get("max_vertices"), "--wp-grid", self._get("wp_grid"),
            "--origin", self._get("origin")]
        if not self._get("mask"):
            argv.append("--no-mask")
        if plan_only:
            argv.append("--plan-only")
        return ("Landscape%s" % (" (layout only)" if plan_only else ""), argv)

    def _step_imagery(self, dry):
        name = self._get("name") or "landscape"
        plan = self._work("landscape", name + ".json")
        argv = self._tool("naip")
        if os.path.isfile(plan):
            argv += ["--plan", plan]
        else:
            # No plan yet: the area still gives the imagery somewhere to be, just not the
            # landscape's own grid.
            argv += self._area_args() + ["--datum", self._get("datum")]
        argv += ["--out", self._work("naip"), "--name", name + "_naip",
                 "--metres", self._get("naip_metres"), "--tile-px", self._get("naip_tile"),
                 "--request-px", self._get("naip_request"), "--workers", self._get("naip_workers")]
        if dry:
            argv.append("--dry-run")
        return ("Imagery%s" % (" (estimate)" if dry else ""), argv)

    def _run_all(self):
        try:
            steps = self._steps_elevation(False) + [self._step_landscape(False), self._step_imagery(False)]
        except ValueError as e:
            messagebox.showwarning("Not yet", str(e), parent=self)
            return
        if not messagebox.askokcancel(
                "Run everything",
                "This downloads elevation, builds the landscape, then downloads imagery.\n\n"
                "%d step(s), and the downloads can take hours. Cancel stops after the current one."
                % len(steps), parent=self):
            return
        self._run(steps)

    def _try(self, build):
        """Build a step list from the fields and run it. A field that does not make sense is a
        sentence in a dialog, never a traceback behind the window."""
        try:
            steps = build()
        except ValueError as e:
            messagebox.showwarning("Not yet", str(e), parent=self)
            return
        self._run(steps)

    def _run(self, steps):
        if self.runner.busy:
            messagebox.showinfo("Busy", "Something is already running.", parent=self)
            return
        os.makedirs(self._get("work"), exist_ok=True)
        self._save()
        self.runner.start(steps)
        self.cancel.configure(state="normal")
        self.run_all.configure(state="disabled")
        self.progress.start(12)
        self.status.configure(text="Running", foreground="#0a6")

    # ---- log and polling ---------------------------------------------------------------------

    def _append(self, text, tag=None):
        self.text.insert("end", text, tag or ())
        self.text.see("end")

    def _clear(self):
        self.text.delete("1.0", "end")

    def _pump(self):
        try:
            while True:
                kind, a, b = self.runner.queue.get_nowait()
                if kind == "line":
                    self._append(a, b)
                elif kind == "step":
                    self._append("\n== %s ==\n" % a, "step")
                elif kind == "finished":
                    self._finished(a)
        except queue.Empty:
            pass
        self.after(60, self._pump)

    def _finished(self, ok):
        self.progress.stop()
        self.cancel.configure(state="disabled")
        self.run_all.configure(state="normal")
        self.status.configure(text="Done" if ok else "Stopped",
                              foreground="#0a6" if ok else "#c33")

    # ---- pickers and settings ----------------------------------------------------------------

    def _pick_aoi(self):
        path = filedialog.askopenfilename(parent=self, title="Area of interest",
                                          filetypes=[("KML or KMZ", "*.kml *.kmz"), ("All", "*.*")])
        if path:
            self.vars["aoi"].set(path)
            self.vars["area_mode"].set("aoi")
            self._area_mode()
            self._show_aoi(path)

    def _show_aoi(self, path):
        """Draw a chosen polygon on the map, so what was picked is visible rather than a filename."""
        if not path or not os.path.isfile(path):
            return
        try:
            aoi = gc.load_kml_aoi(path)
        except Exception as e:
            self.map.readout.configure(text="cannot read that file: %s" % e)
            return
        self.map.set_box(None)
        self.map.set_outline(aoi.ring)

    def _from_map(self, box):
        """A box dragged on the map IS the area, so the fields follow it rather than the reverse."""
        if not box:
            return
        for key, value in zip(("west", "south", "east", "north"), box):
            self.vars["bbox_" + key].set("%.6f" % value)
        self.vars["area_mode"].set("bbox")
        self._area_mode()

    def _to_map(self):
        """Put whatever the fields say on the map, so typed numbers can be checked by eye."""
        if self._get("area_mode") == "aoi":
            self._show_aoi(self._get("aoi"))
            return
        try:
            box = tuple(float(self._get("bbox_" + k)) for k in ("west", "south", "east", "north"))
        except ValueError:
            self.map.readout.configure(text="the box needs four numbers")
            return
        self.map.set_outline(None, fit=False)
        self.map.set_box(box, fit=True)

    def _pick_work(self):
        path = filedialog.askdirectory(parent=self, title="Working folder")
        if path:
            self.vars["work"].set(path)

    def _open_work(self):
        path = self._get("work")
        if os.path.isdir(path):
            if os.name == "nt":
                os.startfile(path)
            else:
                subprocess.run(["xdg-open", path])
        else:
            messagebox.showinfo("Not there yet", "%s does not exist." % path, parent=self)

    def _save(self):
        try:
            with open(SETTINGS, "w", encoding="utf-8") as f:
                json.dump({k: v.get() for k, v in self.vars.items()}, f, indent=1)
        except OSError:
            pass            # remembering the last run is a convenience, never a reason to fail

    def _load(self):
        try:
            with open(SETTINGS, encoding="utf-8") as f:
                for k, v in json.load(f).items():
                    if k in self.vars:
                        self.vars[k].set(v)
        except (OSError, ValueError):
            pass
        self._area_mode()

    def _close(self):
        if self.runner.busy and not messagebox.askokcancel(
                "Still running", "A tool is still running. Close anyway and stop it?", parent=self):
            return
        self.runner.cancel()
        self._save()
        self.destroy()


def main():
    missing = [t for t in TOOLS.values() if not tool_exists(t)]
    if missing:
        sys.exit("These tools are missing from %s: %s" % (HERE, ", ".join(missing)))
    App().mainloop()


if __name__ == "__main__":
    main()
