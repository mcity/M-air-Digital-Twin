"""build_tools.py - build every tool here into a release of Windows executables that needs no Python.

    py -3.10 -m pip install pyinstaller          once
    py -3.10 build_tools.py                      builds dist/MAirCorridor and dist2/Anchor
    py -3.10 build_tools.py --no-landscape       leaves out the 300 MB heightmap

WHAT IT MAKES. dist/MAirCorridor, laid out like the plugin so the tools find things where they
always do:

    MAirCorridor/
        Tools/              launcher.exe, flightplan_ui.exe, fly_mission.exe, ... one per tool
            _internal/      the Python and libraries they share, once for all of them
            missions/       the missions, level.json, segmentation.json, geofences, examples
            landscape/      the landscape plan and heightmap the flights are measured against
            projectairsim/  Project AirSim's sample configs, which our scenes name robots from
        AirSim/sim_config/  our scene and robot configs

Copy that folder anywhere and run Tools/launcher.exe. The simulator (the editor in Play, or a
release from package_release.py) still has to be running for anything to fly.

THE TERRAIN AND IMAGERY TOOLS are built a second time on their own, as dist2/Anchor: the
window, the three downloaders and the landscape builder, with only the libraries they need.
They have nothing to do with the corridor or the simulator, and travel without them.

WHAT GOES IN. Every tool tracked in git with a main (a file nobody has committed is somebody's
work in progress, not part of a release), and AirSim/fly_mcity.py for the keyboard. The Project
AirSim client is built in from the clone (--clone, or PROJECTAIRSIM_ROOT), together with its
keyboard script. The OpenSky credentials are never copied: adsb.exe looks for api/credentials.json
above the plugin as the script does, or takes OPENSKY_CREDENTIALS.

THE TOOLS START EACH OTHER AS EXECUTABLES when built: toolpaths.tool_command picks python -u
script.py or the .exe beside it, and toolpaths.HERE is the executables' folder, not _internal.
"""
import argparse
import glob
import json
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PLUGIN = os.path.dirname(HERE)
DEFAULT_CLONE = os.environ.get("PROJECTAIRSIM_ROOT", r"E:\projects\ProjectAirSim")

# The tools with a window of their own get no console.
WINDOWED = {"launcher", "flightplan_ui", "geodata_ui"}

# Built in by nothing we use, but present on a development machine and large; PyInstaller would
# follow them in through optional imports.
EXCLUDES = ["open3d", "torch", "tensorflow", "IPython", "jupyter", "notebook", "pytest",
            "PyQt5", "PyQt6", "PySide2", "PySide6", "gym", "gymnasium"]

# The terrain and imagery tools, built again as a release of their own under this name.
GEODATA = ["geodata_ui", "download_3dep", "download_copernicus_dem", "download_naip",
           "build_landscape"]
GEODATA_RELEASE = "Anchor"

# The files the tools read beside themselves, copied into the release's Tools folder.
DATA = ["level.json", "segmentation.json", "README.md"]
DATA_DIRS = ["geofences", "examples"]


def tracked_tools():
    """Every tool script tracked in git that runs as a program, as (name, path)."""
    try:
        out = subprocess.run(["git", "ls-files", "*.py", "../AirSim/*.py"], cwd=HERE,
                             capture_output=True, text=True, check=True).stdout.split()
    except (OSError, subprocess.CalledProcessError):
        sys.exit("git was not found, and it says which tools belong in a release")
    tools = []
    for rel in out:
        path = os.path.normpath(os.path.join(HERE, rel))
        if os.path.dirname(path) not in (HERE, os.path.join(PLUGIN, "AirSim")):
            continue                                 # tests, and scripts run inside Unreal/Blender
        if os.path.basename(path) == os.path.basename(__file__):
            continue
        with open(path, encoding="utf-8") as f:
            if '__name__ == "__main__"' not in f.read():
                continue
        tools.append((os.path.splitext(os.path.basename(path))[0], path))
    return sorted(tools)


SPEC = r'''# Written by build_tools.py; rebuilt every run.
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

TOOLS = %(tools)r
GEODATA = %(geodata)r
PATHEX = %(pathex)r
EXCLUDES = %(excludes)r
# rasterio imports some of its own modules by name, and finds GDAL's and PROJ's data in
# gdal_data/ and proj_data/ inside itself; neither is seen by the analysis.
DATAS = collect_data_files("projectairsim") + collect_data_files("rasterio")
HIDDEN = %(hidden)r + collect_submodules("rasterio")

parts, geodata = [], []
for name, script, windowed in TOOLS:
    a = Analysis([script], pathex=PATHEX, datas=DATAS, excludes=EXCLUDES,
                 hiddenimports=HIDDEN)
    pyz = PYZ(a.pure)
    exe = EXE(pyz, a.scripts, [("u", None, "OPTION")], exclude_binaries=True, name=name,
              console=not windowed, upx=False)
    parts += [exe, a.binaries, a.datas]
    if name in GEODATA:
        geodata += [exe, a.binaries, a.datas]

COLLECT(*parts, name="Tools", upx=False)
# Beside Tools, because a COLLECT can only name a folder in the output; copied out afterwards.
COLLECT(*geodata, name="_geodata", upx=False)
'''


def copy_landscape(dest):
    """The landscape plan the flights use, with every heightmap it names."""
    sys.path.insert(0, HERE)
    from flightplan import DEFAULT_PLAN, resolve_plan

    try:
        plan = resolve_plan(DEFAULT_PLAN)
    except FileNotFoundError as e:
        print("warning: %s\nThe release will need MAIRCORRIDOR_PLAN set to fly." % e)
        return
    with open(plan, encoding="utf-8") as f:
        data = json.load(f)
    os.makedirs(dest, exist_ok=True)
    shutil.copy2(plan, os.path.join(dest, os.path.basename(plan)))
    for seg in data.get("segments") or [data]:
        src = os.path.join(os.path.dirname(plan), seg["heightmap_r16"])
        there = os.path.join(dest, seg["heightmap_r16"])
        same = (os.path.isfile(there) and os.path.getsize(there) == os.path.getsize(src)
                and os.path.getmtime(there) >= os.path.getmtime(src))
        if same:
            continue                                  # 300 MB, and already there
        print("landscape %s (%.0f MB)" % (src, os.path.getsize(src) / 1e6))
        shutil.copy2(src, there)


def refresh(src, dest, keep=()):
    """Make dest hold what src does, emptying it rather than deleting it: a console whose
    current folder is the release (where one goes to try a tool) locks the folder itself
    against deletion, but not what is in it. Names in keep are left alone."""
    os.makedirs(dest, exist_ok=True)
    for name in os.listdir(dest):
        if name in keep:
            continue
        path = os.path.join(dest, name)
        if os.path.isdir(path) and not os.path.islink(path):
            shutil.rmtree(path)
        else:
            os.remove(path)
    shutil.copytree(src, dest, dirs_exist_ok=True)


def smoke_test(tools_dir, names):
    """Start each console tool with --help: a library left out of the build fails on import,
    and says so, before anything is asked of it. The windowed tools cannot be asked this way."""
    broken = []
    for name in names:
        try:
            done = subprocess.run([os.path.join(tools_dir, name + ".exe"), "--help"],
                                  capture_output=True, text=True, timeout=120,
                                  encoding="utf-8", errors="replace")
            said = (done.stdout or "") + (done.stderr or "")
        except (OSError, subprocess.TimeoutExpired) as e:
            done, said = None, str(e)
        ok = done is not None and done.returncode == 0 and "usage:" in said
        print("check     %-26s %s" % (name, "ok" if ok else "FAILED"))
        if not ok:
            broken.append("%s: %s" % (name, said.strip().splitlines()[-1] if said.strip()
                                         else "exit %s" % (done and done.returncode)))
    return broken


def main():
    ap = argparse.ArgumentParser(description="Build the tools into Windows executables.")
    ap.add_argument("--clone", default=DEFAULT_CLONE,
                    help="the ProjectAirSim source clone the client is built in from")
    ap.add_argument("--out", default=os.path.join(HERE, "dist"),
                    help="where MAirCorridor/ is written (default: Tools/dist)")
    ap.add_argument("--out2", default=os.path.join(HERE, "dist2"),
                    help="where the terrain and imagery release is written (default: Tools/dist2)")
    ap.add_argument("--no-landscape", action="store_true",
                    help="leave out the landscape; the release then needs MAIRCORRIDOR_PLAN")
    args = ap.parse_args()

    try:
        import PyInstaller.__main__ as pyinstaller
    except ImportError:
        sys.exit("PyInstaller is not installed: py -3.10 -m pip install pyinstaller")

    client_src = os.path.join(args.clone, "client", "python", "projectairsim", "src")
    samples = os.path.join(args.clone, "client", "python", "example_user_scripts")
    if not os.path.isdir(client_src):
        sys.exit("No Project AirSim client at %s. Pass --clone or set PROJECTAIRSIM_ROOT."
                 % client_src)

    tools = tracked_tools()
    print("building  %s" % ", ".join(n for n, _ in tools))

    release = os.path.join(args.out, "MAirCorridor")
    work = os.path.join(HERE, "build")
    os.makedirs(work, exist_ok=True)
    spec = os.path.join(work, "maircorridor_tools.spec")
    with open(spec, "w", encoding="utf-8", newline="\n") as f:
        f.write(SPEC % {
            "tools": [(n, p, n in WINDOWED) for n, p in tools],
            "geodata": GEODATA,
            "pathex": [HERE, os.path.join(PLUGIN, "AirSim"), client_src, samples],
            "excludes": EXCLUDES,
            # Imported by name at run time, which the analysis cannot see.
            "hidden": ["projectairsim", "keyboard_control"],
        })

    built = os.path.join(work, "out")
    pyinstaller.run([spec, "--noconfirm", "--clean", "--distpath", built,
                     "--workpath", os.path.join(work, "work")])

    tools_dir = os.path.join(release, "Tools")
    refresh(os.path.join(built, "Tools"), tools_dir, keep=("landscape",))
    for name in DATA:
        shutil.copy2(os.path.join(HERE, name), os.path.join(tools_dir, name))
    for name in DATA_DIRS:
        shutil.copytree(os.path.join(HERE, name), os.path.join(tools_dir, name),
                        dirs_exist_ok=True)
    missions = os.path.join(tools_dir, "missions")
    os.makedirs(missions, exist_ok=True)
    for path in glob.glob(os.path.join(HERE, "missions", "*.json")):
        shutil.copy2(path, missions)
    shutil.copytree(os.path.join(PLUGIN, "AirSim", "sim_config"),
                    os.path.join(release, "AirSim", "sim_config"), dirs_exist_ok=True)
    shutil.copytree(os.path.join(samples, "sim_config"),
                    os.path.join(tools_dir, "projectairsim", "sim_config"), dirs_exist_ok=True)
    if not args.no_landscape:
        copy_landscape(os.path.join(tools_dir, "landscape"))

    geo = os.path.join(args.out2, GEODATA_RELEASE)
    refresh(os.path.join(built, "_geodata"), geo)
    shutil.copytree(os.path.join(HERE, "examples"), os.path.join(geo, "examples"),
                    dirs_exist_ok=True)
    # The guide for using these tools on their own, as the release's README.
    shutil.copy2(os.path.join(HERE, "terrain_imagery_guide.md"), os.path.join(geo, "README.md"))
    # Its window is called by the tool's own name, not the suite's (geodata_ui.window_title).
    with open(os.path.join(geo, "release.json"), "w", encoding="utf-8") as f:
        json.dump({"title": "Terrain and imagery"}, f)

    exes = sorted(os.path.basename(p) for p in glob.glob(os.path.join(tools_dir, "*.exe")))
    broken = smoke_test(tools_dir, [n for n, _ in tools if n not in WINDOWED])
    broken += smoke_test(geo, [n for n in GEODATA if n not in WINDOWED])
    size = sum(os.path.getsize(os.path.join(d, f)) for d, _, fs in os.walk(release) for f in fs)
    print("\nRELEASE   %s (%.0f MB)" % (release, size / 1e6))
    print("          %s" % ", ".join(exes))
    print("start     %s" % os.path.join(tools_dir, "launcher.exe"))
    geo_size = sum(os.path.getsize(os.path.join(d, f)) for d, _, fs in os.walk(geo) for f in fs)
    print("\nRELEASE   %s (%.0f MB)" % (geo, geo_size / 1e6))
    print("start     %s" % os.path.join(geo, "geodata_ui.exe"))
    if broken:
        print("\nBROKEN    %s" % "\n          ".join(broken))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
