"""launcher.py - MCity Digital Air Command: one window to start the editor and every tool.

    py -3.10 launcher.py            or, from the plugin root:  run

WHY THIS EXISTS. There are five things to run here and they have an order: the editor has to be open
and in Play before a drone will fly, terrain has to be downloaded before it can be imported, and a
mission has to exist before it can be flown. A list of commands in a README leaves all of that to be
remembered. This window says what each thing does, whether the editor is running, and starts them.

IT LAUNCHES, IT DOES NOT WRAP. Every button starts the same program you could start yourself, in its
own process, and says so in the log. Nothing here is a reimplementation of anything, so a tool can
always be run directly instead.
"""
import io
import json
import os
import queue
import re
import subprocess
import tempfile
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from uikit import fit_to_screen

from toolpaths import HERE, PLUGIN, tool_command, tool_exists
MISSIONS = os.path.join(HERE, "missions")

# The level every flight here is flown in. Play mode and a packaged release both open it by name,
# so neither depends on what the project's default map setting says.
PLAY_LEVEL = "/MAirCorridor/Scene/CorridorTerrain"
# A window rather than the whole screen, so the planner can sit beside it.
PLAY_WINDOW = ("-windowed", "-ResX=1600", "-ResY=900")


def find_project():
    """The .uproject this plugin lives inside, by walking up from here."""
    d = PLUGIN
    for _ in range(5):
        d = os.path.dirname(d)
        if not d:
            break
        hits = [f for f in os.listdir(d) if f.lower().endswith(".uproject")] if os.path.isdir(d) else []
        if hits:
            return os.path.join(d, hits[0])
    return None


def find_editor(project):
    """UnrealEditor.exe for the engine this project is associated with. Override with UE_EDITOR."""
    override = os.environ.get("UE_EDITOR")
    if override and os.path.isfile(override):
        return override
    version = "5.7"
    if project and os.path.isfile(project):
        try:
            with io.open(project, encoding="utf-8") as f:
                assoc = str(json.load(f).get("EngineAssociation", ""))
            if re.match(r"^\d+\.\d+$", assoc):
                version = assoc
        except Exception:
            pass
    for root in (r"C:\Program Files\Epic Games\UE_%s" % version,
                 r"D:\Program Files\Epic Games\UE_%s" % version,
                 r"D:\Epic Games\UE_%s" % version):
        exe = os.path.join(root, "Engine", "Binaries", "Win64", "UnrealEditor.exe")
        if os.path.isfile(exe):
            return exe
    return None


def unreal_running(project=None):
    """Whether Unreal is running in any form a drone can fly in: the editor (which is also what
    play mode runs), or a packaged release of this project."""
    release = os.path.splitext(os.path.basename(project))[0].lower() if project else None
    try:
        out = subprocess.run(["tasklist", "/FO", "CSV", "/NH"],
                             capture_output=True, text=True, timeout=10,
                             creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
    except Exception:
        return False
    for line in out.stdout.splitlines():
        name = line.split(",")[0].strip('"').lower()
        if name == "unrealeditor.exe" or (release and name.startswith(release)
                                          and name.endswith(".exe")):
            return True
    return False


NOT_PLAYING = "Unreal is not running: press Play above, or open the editor and press Play in it"


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("MCity Digital Air Command")
        fit_to_screen(self, 800, 980, 700, 640)
        try:
            ttk.Style().theme_use("vista")
        except tk.TclError:
            pass
        ttk.Style().configure("Big.TButton", font=("Segoe UI", 10, "bold"), padding=(10, 8))

        self.project = find_project()
        self.editor = find_editor(self.project)
        # Work that runs in a thread reports back here. Tkinter is not thread safe, so nothing
        # touches a widget except the polling below, on the thread that owns the window.
        self.jobs = queue.Queue()
        self.running = 0
        self._build()
        self._poll()

    # ---- layout ------------------------------------------------------------------------------

    def _build(self):
        outer = ttk.Frame(self, padding=12)
        outer.pack(fill="both", expand=True)

        head = ttk.Frame(outer)
        head.pack(fill="x")
        ttk.Label(head, text="MCity Digital Air Command", font=("Segoe UI", 14, "bold")).pack(side="left")
        self.state = ttk.Label(head, text="", font=("Segoe UI", 9))
        self.state.pack(side="right")

        self._entry(outer, "Play the simulation",
                    "Opens the M-City level straight into play, with no editor around it. The "
                    "simulator starts with the level, so a flight can go as soon as it is up, and "
                    "it runs lighter than Play in the editor. Release runs the packaged build "
                    "instead, once one has been made.",
                    "Play", self._play, more=(("Release", self._play_release),))

        self._entry(outer, "Open the editor",
                    "Opens this project in Unreal, to change the level. To fly from there, press "
                    "Play in it first: the simulator starts with the game.",
                    "Open", self._open_editor)

        self._entry(outer, "Plan a flight",
                    "Place named waypoints on a map, give each a height above the ground or above "
                    "sea level, and fly them. Saves missions you can fly again later.",
                    "Plan", lambda: self._run("flightplan_ui.py"))

        self._entry(outer, "Fly a saved mission",
                    "Pick a mission and fly it, watching the drone against its planned path: how "
                    "far off the line it is, and where it has actually been. The simulation "
                    "must already be playing.",
                    "Fly...", self._fly_mission)

        self._entry(outer, "Fly with the keyboard",
                    "Take manual control of the drone: W, A, S, D to move, arrows for throttle and "
                    "yaw, L to land. The simulation must already be playing.",
                    "Fly", self._keyboard)

        self._entry(outer, "Live air traffic",
                    "Fetch the real aircraft overhead and keep a snapshot up to date, for an "
                    "M-Air Live Traffic actor in the level to fly. The flight planner does this "
                    "too while it is showing traffic; this is for when it is not open.",
                    "Start", self._traffic)

        self._entry(outer, "Import a real flight",
                    "Turn a flight that was actually flown into a mission: a CSV, a GPX track or "
                    "a folder recorded here. Thins it to the waypoints that describe it and opens "
                    "it for editing, so the same route can be flown in the simulator.",
                    "Import...", self._import_real)

        self._entry(outer, "Compare two flights",
                    "Measure one flight against another and say how far apart they were, in "
                    "three dimensions and across the ground. Use it to see how closely a "
                    "simulated flight followed a real one.",
                    "Compare...", self._compare)

        self._entry(outer, "Terrain and imagery",
                    "Download elevation and aerial photography for any area and build an Unreal "
                    "landscape from it. Does not need the editor.",
                    "Open", lambda: self._run("geodata_ui.py"))

        self._entry(outer, "Build a release",
                    "Bakes the project into a build that runs without the editor: the M-City "
                    "level, the drone and the scan, cooked for Windows, with a batch file that "
                    "opens it. The first build takes an hour or more, in its own window.",
                    "Build...", self._build_release)

        paths = ttk.LabelFrame(outer, text="Where things are", padding=8)
        paths.pack(fill="x", pady=(10, 0))
        self.paths = ttk.Label(paths, text="", justify="left", foreground="#444",
                               font=("Consolas", 8))
        self.paths.pack(anchor="w")

        self.log = tk.Text(outer, height=6, wrap="word", font=("Consolas", 9),
                           background="#101418", foreground="#d8dee4")
        self.log.pack(fill="both", expand=True, pady=(10, 0))
        self.log.tag_configure("warn", foreground="#e8c468")
        self.log.tag_configure("error", foreground="#ff8a7a")

    def _entry(self, parent, title, text, button, command, more=()):
        box = ttk.Frame(parent, padding=(0, 8, 0, 0))
        box.pack(fill="x")
        left = ttk.Frame(box)
        left.pack(side="left", fill="x", expand=True)
        ttk.Label(left, text=title, font=("Segoe UI", 10, "bold")).pack(anchor="w")
        ttk.Label(left, text=text, foreground="#555", wraplength=560 - 110 * len(more),
                  justify="left").pack(anchor="w")
        # Packed from the right, so the main button ends up rightmost and the others before it.
        for label, cmd in reversed(((button, command),) + tuple(more)):
            ttk.Button(box, text=label, width=10, style="Big.TButton",
                       command=cmd).pack(side="right", padx=(10, 0))
        ttk.Separator(parent).pack(fill="x", pady=(8, 0))

    # ---- actions -----------------------------------------------------------------------------

    def _say(self, text, tag=None):
        self.log.insert("end", text + "\n", tag or ())
        self.log.see("end")

    def _spawn(self, argv, what):
        try:
            subprocess.Popen(argv, cwd=HERE,
                             creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
            self._say("started %s" % what)
        except OSError as e:
            self._say("could not start %s: %s" % (what, e), "error")

    def _run(self, script, *args):
        if not tool_exists(script):
            self._say("%s is missing" % script, "error")
            return
        self._spawn(tool_command(script, *args), script)

    def _can_launch(self):
        if not self.project:
            messagebox.showerror("No project", "No .uproject was found above this plugin.", parent=self)
            return False
        if not self.editor:
            messagebox.showerror(
                "No engine", "UnrealEditor.exe was not found for this project. Set UE_EDITOR to its "
                             "full path and reopen this window.", parent=self)
            return False
        return True

    def _second_copy_ok(self):
        """Two copies of the simulator both want the same ports, so the second cannot serve."""
        return not unreal_running(self.project) or messagebox.askokcancel(
            "Already running", "Unreal is already running. A second copy cannot take the "
                               "simulator's ports while the first holds them. Start it anyway?",
            parent=self)

    def _open_editor(self):
        if self._can_launch() and self._second_copy_ok():
            self._spawn([self.editor, self.project], os.path.basename(self.project))

    def _play(self):
        """The project in play mode: the editor's own executable with -game, so no editor."""
        if self._can_launch() and self._second_copy_ok():
            self._spawn([self.editor, self.project, PLAY_LEVEL, "-game"] + list(PLAY_WINDOW),
                        "the simulation in play mode (%s)" % PLAY_LEVEL)

    def _play_release(self):
        import package_release
        exe = package_release.newest_release(self.project) if self.project else None
        if not exe:
            self._say("no release has been built yet: Build a release first", "warn")
            return
        if self._second_copy_ok():
            self._spawn([exe, PLAY_LEVEL] + list(PLAY_WINDOW), "the release, %s" % exe)

    def _build_release(self):
        """In its own window, like the traffic feed: it runs for an hour and says a great deal."""
        if not self._can_launch():
            return
        import package_release
        out = package_release.release_dir(self.project, "Development")
        if not messagebox.askokcancel(
                "Build a release",
                "This cooks the M-City level for Windows and packages it into\n\n%s\n\n"
                "The first build compiles every shader and takes an hour or more, with the "
                "machine busy throughout. Close the editor first if it is open. Go?" % out,
                parent=self):
            return
        try:
            subprocess.Popen(tool_command("package_release.py", "--pause"), cwd=HERE,
                             creationflags=subprocess.CREATE_NEW_CONSOLE if os.name == "nt" else 0)
        except OSError as e:
            self._say("could not start the packager: %s" % e, "error")
            return
        self._say("packaging started in its own window; the release goes to %s" % out)

    def _keyboard(self):
        script = os.path.join(PLUGIN, "AirSim", "fly_mcity.py")
        if not tool_exists(script):
            self._say("AirSim/fly_mcity.py is missing", "error")
            return
        if not unreal_running(self.project):
            self._say(NOT_PLAYING, "warn")
        self._spawn(tool_command(script), "keyboard flight")

    LOG_TYPES = [("Flight logs", "*.csv *.jsonl *.gpx *.json"), ("All", "*.*")]

    def _work(self, argv, what, then=None):
        """Run a tool in a thread, print what it said, and hand the result on.

        In a thread because rasterio takes a second or two to load and a window that stops
        repainting looks broken. The result comes back through the queue, never by touching a
        widget from the thread."""
        self._say("%s..." % what)
        self.running += 1

        def run():
            try:
                done = subprocess.run(argv, cwd=HERE, capture_output=True, text=True,
                                      creationflags=subprocess.CREATE_NO_WINDOW
                                      if os.name == "nt" else 0)
                self.jobs.put((what, done.returncode,
                               (done.stdout or "") + (done.stderr or ""), then))
            except OSError as e:
                self.jobs.put((what, 1, "could not run it: %s" % e, None))

        threading.Thread(target=run, daemon=True).start()
        self.after(120, self._drain)

    def _drain(self):
        """Whatever the threads have finished, reported on the thread that owns the window."""
        try:
            while True:
                what, code, out, then = self.jobs.get_nowait()
                self.running = max(0, self.running - 1)
                for line in (out or "").splitlines():
                    if line.strip():
                        self._say("  " + line,
                                  "warn" if line.lower().startswith("warning") else None)
                if code != 0:
                    self._say("%s failed" % what, "error")
                elif then:
                    then()
        except queue.Empty:
            pass
        if self.running:
            self.after(120, self._drain)

    def _import_real(self):
        log = filedialog.askopenfilename(parent=self, title="Which flight was flown?",
                                         filetypes=self.LOG_TYPES)
        if not log:
            return
        os.makedirs(MISSIONS, exist_ok=True)
        name = os.path.splitext(os.path.basename(log))[0] or "imported"
        out = os.path.join(MISSIONS, "%s.json" % name)
        if os.path.exists(out) and not messagebox.askokcancel(
                "Already there", "%s exists. Overwrite it?" % os.path.basename(out), parent=self):
            return
        self._work(tool_command("realflight.py", "mission", log, "-o", out, "--name", name),
                   "importing %s" % os.path.basename(log),
                   then=lambda: self._run("flightplan_ui.py", out))

    def _compare(self):
        first = filedialog.askopenfilename(parent=self, title="The flight to measure AGAINST",
                                           initialdir=MISSIONS, filetypes=self.LOG_TYPES)
        if not first:
            return
        second = filedialog.askopenfilename(parent=self, title="The flight being MEASURED",
                                            initialdir=os.path.dirname(first),
                                            filetypes=self.LOG_TYPES)
        if not second:
            return
        self._work(tool_command("realflight.py", "compare", first, second),
                   "comparing the two flights")

    def _traffic(self):
        """Start the ADS-B feed in its own window so it can be watched and stopped.

        Its own window on purpose: it runs for as long as the editor is open, it prints what it
        is doing, and closing it is how it stops. Burying that in this log would hide a thing
        that spends credits."""
        snapshot = os.path.join(tempfile.gettempdir(), "maircorridor_traffic.json")
        if not tool_exists("adsb.py"):
            self._say("adsb.py is missing", "error")
            return
        try:
            subprocess.Popen(tool_command("adsb.py", "--watch", "--snapshot", snapshot),
                             cwd=HERE,
                             creationflags=subprocess.CREATE_NEW_CONSOLE if os.name == "nt" else 0)
        except OSError as e:
            self._say("could not start the traffic feed: %s" % e, "error")
            return
        self._say("traffic feed started; point an M-Air Live Traffic actor at %s" % snapshot)

    def _fly_mission(self):
        os.makedirs(MISSIONS, exist_ok=True)
        path = filedialog.askopenfilename(parent=self, title="Fly which mission?",
                                          initialdir=MISSIONS,
                                          filetypes=[("Mission", "*.json"), ("All", "*.*")])
        if not path:
            return
        if not unreal_running(self.project):
            self._say(NOT_PLAYING, "warn")
        # The planner, not the bare runner: a flight nobody can see is hard to judge, and the
        # planner draws the route, the aircraft and the deviation while it flies.
        self._run("flightplan_ui.py", path, "--fly")

    # ---- state -------------------------------------------------------------------------------

    def _poll(self):
        running = unreal_running(self.project)
        self.state.configure(text="Unreal running" if running else "Unreal not running",
                             foreground="#0a6" if running else "#999")
        self.paths.configure(text="project  %s\nengine   %s\nmissions %s" % (
            self.project or "not found",
            self.editor or "not found (set UE_EDITOR)",
            MISSIONS))
        self.after(3000, self._poll)


def main():
    App().mainloop()


if __name__ == "__main__":
    main()
