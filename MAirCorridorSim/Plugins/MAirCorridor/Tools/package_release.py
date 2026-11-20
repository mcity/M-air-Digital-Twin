"""package_release.py - bake the project into a release that runs without the editor.

    py -3.10 package_release.py                 a Development build, the default
    py -3.10 package_release.py --shipping      smaller and faster, but no console and no log
    py -3.10 package_release.py --dry-run       print the packager's command and stop
    py -3.10 package_release.py --out D:/Releases/AirCommand
    py -3.10 package_release.py --run           start the newest release, to fly

WHAT IT BUILDS. The game target of the project this plugin sits in, cooked for Windows, opening
the M-City corridor level. It lands in Releases/<project>-<config> beside the project folder, with
"Play MCity Air Command.bat" at the top of it. Run that, and the simulator is up and waiting for
the same tools that fly it in the editor: the planner, fly_mission.py, the keyboard.

WHAT A RELEASE NEEDS THAT THE EDITOR DOES NOT. The editor loads anything on demand; a release has
only what was cooked into it, and the cooker only follows references. So:

  THE LEVEL is cooked by name, and opened by name. A packaged game given no level opens the
  project's default map, and that setting has to name the level where it is now: a path that
  reaches it through a redirector, which a moved level leaves behind, fails to load in a release.
  This checks the setting and says so; the batch file names the level either way.

  ASSETS LOADED BY NAME are not references. Robot configs name their meshes (/Drone/Quadrotor1,
  and the built drones' under /MAirCorridor/Aircraft), Project AirSim loads its camera and weather
  materials by path, the scan finds its default material and its mesh the same way, the traffic
  draws aircraft from /MAirCorridor/Aircraft by size class, and the M-City view streams the
  digital twin's levels in from /McityMap by name. Those directories are cooked whole: Project
  AirSim's content, the Drone plugin's, the McityMap plugin's, and this plugin's Materials,
  Aircraft and Scan. They are the project's Directories to Always Cook (Config/DefaultGame.ini);
  this checks that every one is listed, and names any that is not, before packaging.

  FILES THAT ARE NOT ASSETS, the scan's tiles and photographs, are staged by
  MAirCorridorScan.Build.cs, which names them as runtime dependencies.

It runs Unreal's own packager (RunUAT BuildCookRun) and shows everything it says. Nothing here
changes the project's settings: the level is passed on the command line, and the directories are
the project's own setting, so packaging from the editor's own menu cooks the same content.

The first build compiles every shader for the game and cooks the level, which takes an hour or
more. Later builds reuse what they can.
"""
import argparse
import io
import os
import re
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
PLUGIN = os.path.dirname(HERE)
sys.path.insert(0, HERE)

from launcher import PLAY_LEVEL, PLAY_WINDOW, find_editor, find_project   # noqa: E402

LAUNCH_SCRIPT = "Play MCity Air Command.bat"


def release_dir(project, config):
    """Where a release of this configuration goes: Releases/<project>-<config> beside the project."""
    name = os.path.splitext(os.path.basename(project))[0]
    return os.path.join(os.path.dirname(os.path.dirname(project)), "Releases",
                        "%s-%s" % (name, config))


def release_exe(project, config):
    name = os.path.splitext(os.path.basename(project))[0]
    return os.path.join(release_dir(project, config), "Windows", name + ".exe")


def newest_release(project):
    """The most recently built release executable, or None when nothing has been packaged."""
    built = [release_exe(project, c) for c in ("Development", "Shipping")]
    built = [p for p in built if os.path.isfile(p)]
    return max(built, key=os.path.getmtime) if built else None


def find_plugin(project, name):
    """The folder of the plugin called name, anywhere under the project's Plugins folder."""
    root = os.path.join(os.path.dirname(project), "Plugins")
    for folder, dirs, files in os.walk(root):
        if folder[len(root):].count(os.sep) > 4:
            dirs[:] = []
            continue
        dirs[:] = [d for d in dirs if d not in ("Binaries", "Intermediate", "Content", "Source",
                                                "SimLibs", "Saved")]
        if name + ".uplugin" in files:
            return folder
    return None


def always_cook(project):
    """The content cooked whole, because code loads it by name, as (package path, plugin, why).
    The package path is None for a folder that is not on this machine."""
    wanted = []
    for plugin, sub, why in (
            ("ProjectAirSim", "", "Project AirSim's camera and weather materials"),
            ("Drone", "", "the meshes robot configs name, such as /Drone/Quadrotor1"),
            ("McityMap", "", "the digital twin's levels, which the M-City view streams in"),
            ("MAirCorridor", "Materials", "the scan's default material"),
            ("MAirCorridor", "Aircraft", "the built drones' meshes and the traffic's aircraft"),
            ("MAirCorridor", "Scan", "the M-City scan mesh")):
        folder = find_plugin(project, plugin)
        there = folder and os.path.isdir(os.path.join(folder, "Content", sub))
        wanted.append(("/" + "/".join(p for p in (plugin, sub) if p) if there else None,
                       plugin, why))
    return wanted


def check_always_cook(project):
    """Say which of always_cook() the project's Directories to Always Cook leaves out, and how to
    add them. They live in the project's Config/DefaultGame.ini rather than on this command line:
    an entry is (Path="/Drone"), and a quote does not survive the trip through RunUAT.bat to the
    cooker, while an unquoted path is rejected and the directory silently not cooked. -COOKDIR
    takes a folder on disk instead, which the cooker cannot take with a space in it."""
    ini = os.path.join(os.path.dirname(project), "Config", "DefaultGame.ini")
    try:
        with io.open(ini, encoding="utf-8-sig") as f:
            text = f.read()
    except OSError:
        text = ""
    listed = set(re.findall(r'^\+DirectoriesToAlwaysCook=\(Path="([^"]+)"\)', text, re.M))
    missing = []
    for package_path, plugin, why in always_cook(project):
        if package_path is None:
            print("warning: %s was not found, so %s will be missing from the release" % (plugin, why))
        elif package_path not in listed:
            print("warning: %s is not in the project's Directories to Always Cook, so %s will be "
                  "missing from the release" % (package_path, why))
            missing.append(package_path)
    if missing:
        print("  add to %s, under [/Script/UnrealEd.ProjectPackagingSettings]:" % ini)
        for package_path in missing:
            print('  +DirectoriesToAlwaysCook=(Path="%s")' % package_path)
        print("  or in the editor: Project Settings > Packaging > Directories to Always Cook")
    return missing


def check_default_map(project):
    """Say so when the project's default map is not the corridor level at its current path."""
    ini = os.path.join(os.path.dirname(project), "Config", "DefaultEngine.ini")
    try:
        with io.open(ini, encoding="utf-8-sig") as f:
            lines = f.read().splitlines()
    except OSError:
        return
    for line in lines:
        if line.strip().startswith("GameDefaultMap="):
            value = line.split("=", 1)[1].strip()
            if value.split(".")[0] != PLAY_LEVEL:
                print("warning: the project's default map is %s, not %s. The executable on its own "
                      "opens the default map; if that path is an old one the level was moved from, "
                      "it will not load in a release. The batch file names the level, so use it."
                      % (value, PLAY_LEVEL))
            return


def command(project, config, out):
    editor = find_editor(project)
    if not editor:
        sys.exit("UnrealEditor.exe was not found for this project; set UE_EDITOR to its full path")
    engine = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(editor))))
    runuat = os.path.join(engine, "Engine", "Build", "BatchFiles", "RunUAT.bat")
    if not os.path.isfile(runuat):
        sys.exit("RunUAT.bat is not where the engine should have it: %s" % runuat)

    return [runuat, "BuildCookRun",
            "-project=%s" % project.replace("\\", "/"),
            "-noP4", "-platform=Win64", "-clientconfig=%s" % config,
            "-build", "-cook", "-map=%s" % PLAY_LEVEL,
            "-stage", "-pak", "-iostore", "-compressed", "-prereqs",
            "-package", "-archive", "-archivedirectory=%s" % out.replace("\\", "/"),
            "-unattended", "-utf8output"]


def finish(project, config, out):
    """Put the way in next to the executable, and say what was made."""
    windows = os.path.join(out, "Windows")
    name = os.path.splitext(os.path.basename(project))[0]
    exe = os.path.join(windows, name + ".exe")
    if not os.path.isfile(exe):
        return None
    args = " ".join([PLAY_LEVEL] + list(PLAY_WINDOW))
    with io.open(os.path.join(windows, LAUNCH_SCRIPT), "w", encoding="utf-8", newline="\r\n") as f:
        f.write("@echo off\n"
                "rem Opens the M-City corridor level by name, in a window. %s.exe on its own opens\n"
                "rem the project's default map instead.\n"
                "start \"\" \"%%~dp0%s.exe\" %s %%*\n" % (name, name, args))
    with io.open(os.path.join(windows, "README.txt"), "w", encoding="utf-8", newline="\r\n") as f:
        f.write(
            "MCity Digital Air Command, %s build, packaged %s\n\n"
            "Run \"%s\". The simulator starts with the level and waits for a client on the\n"
            "usual Project AirSim ports, 8989 and 8990.\n\n"
            "Fly it with the tools in the MAirCorridor plugin's Tools folder, exactly as against\n"
            "the editor: the launcher, the flight planner, fly_mission.py, or the keyboard.\n\n"
            "%s.exe on its own opens the project's default map instead of naming the level.\n"
            "Pass a different window size after the batch file to override it, for example\n"
            "-ResX=2560 -ResY=1440, or -fullscreen.\n"
            % (config, time.strftime("%Y-%m-%d %H:%M"), LAUNCH_SCRIPT, name))
    return exe


def folder_size(path):
    total = 0
    for folder, _dirs, files in os.walk(path):
        for f in files:
            try:
                total += os.path.getsize(os.path.join(folder, f))
            except OSError:
                pass
    return total


def main():
    # The packager names every asset it cooks, and some building names are not in the console's
    # code page ("Český-Národní-dům"). Printing one would raise and end this script mid-cook,
    # leaving the packager running with nothing reading it, so what cannot be shown is replaced.
    # The log file is UTF-8 and keeps every name as written.
    sys.stdout.reconfigure(errors="replace")
    ap = argparse.ArgumentParser(description="Bake the project into a release that runs without "
                                             "the editor.")
    ap.add_argument("--shipping", action="store_true",
                    help="a Shipping build: smaller and faster, with no console and no log")
    ap.add_argument("--out", help="where the release goes (default: Releases/<project>-<config> "
                                  "beside the project)")
    ap.add_argument("--dry-run", action="store_true", help="print the packager's command and stop")
    ap.add_argument("--pause", action="store_true",
                    help="wait for Enter at the end, for a window that would otherwise close")
    ap.add_argument("--run", action="store_true",
                    help="build nothing: start the newest release on the corridor level, as the "
                         "launcher's Release does, for the flight tools to fly")
    args = ap.parse_args()

    project = find_project()
    if not project:
        sys.exit("no .uproject was found above this plugin")
    if args.run:
        exe = newest_release(project)
        if not exe:
            sys.exit("no release has been built yet: py -3.10 package_release.py builds one")
        subprocess.Popen([exe, PLAY_LEVEL] + list(PLAY_WINDOW), cwd=os.path.dirname(exe))
        print("started %s on %s. Fly it as the editor: run plan, run mission <file>, run fly."
              % (exe, PLAY_LEVEL))
        return 0
    config = "Shipping" if args.shipping else "Development"
    out = os.path.abspath(args.out) if args.out else release_dir(project, config)
    argv = command(project, config, out)

    check_default_map(project)
    check_always_cook(project)
    print("project  %s" % project)
    print("level    %s" % PLAY_LEVEL)
    print("config   %s" % config)
    print("release  %s" % out)
    print()
    print(subprocess.list2cmdline(argv))
    print()
    if args.dry_run:
        return 0

    os.makedirs(out, exist_ok=True)
    log_path = out.rstrip("\\/") + ".log"
    started = time.time()
    code = 1
    with io.open(log_path, "w", encoding="utf-8") as log:
        try:
            proc = subprocess.Popen(argv, cwd=os.path.dirname(project), stdout=subprocess.PIPE,
                                    stderr=subprocess.STDOUT, text=True, encoding="utf-8",
                                    errors="replace", bufsize=1)
        except OSError as e:
            sys.exit("could not start the packager: %s" % e)
        try:
            for line in proc.stdout:
                sys.stdout.write(line)
                log.write(line)
            code = proc.wait()
        except KeyboardInterrupt:
            proc.terminate()
            print("\nstopped.")
    minutes = (time.time() - started) / 60.0

    print()
    exe = finish(project, config, out) if code == 0 else None
    if exe:
        print("RELEASE BUILT in %.0f minutes: %.1f GB" % (minutes, folder_size(out) / 1e9))
        print("  run      %s" % os.path.join(os.path.dirname(exe), LAUNCH_SCRIPT))
        print("  log      %s" % log_path)
    else:
        print("PACKAGING FAILED after %.0f minutes (exit %s). The packager's own account is in %s;"
              % (minutes, code, log_path))
        print("search it for 'Error:' to find the first thing that went wrong.")
    if args.pause:
        input("\nPress Enter to close this window.")
    return 0 if exe else 1


if __name__ == "__main__":
    sys.exit(main())
