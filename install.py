#!/usr/bin/env python3
"""install.py - set up the M-Air corridor environment for Project AirSim.

    python3 install.py --ue-root /path/to/UnrealEngine-5.7                    (prebuilt Project AirSim)
    python3 install.py --ue-root ... --airsim /path/to/ProjectAirSim-Plugin-Linux-UE5_7-1.0.1
    python3 install.py --ue-root ... --airsim /path/to/ProjectAirSim          (a source clone)
    python3 install.py --ue-root ... --project /path/to/YourProject.uproject  (your own project)

What it does, in order. Every step is skipped when it is already done, so it is safe to run again.

  1. checks Unreal Engine, Python, git and free disk space
  2. makes a Python environment (.venv) with what the flight tools need
  3. downloads the 3D assets from Hugging Face and checks them against the dataset's manifest
  4. unpacks them into <project>/Plugins/MAirCorridor/Content
  5. puts the Project AirSim plugin (ProjectAirSim, Drone, Rover) into <project>/Plugins
  6. gets Project AirSim's Python client and sample configs
  7. builds the project's editor target
  8. writes maircorridor.env, which the scripts in scripts/ read

Needs only the Python standard library to start. docs/MANUAL_INSTALL.md does the same by hand.
"""
import argparse
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
import tarfile
import urllib.request
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))

# ---------------------------------------------------------------------------------------------
# The two things a maintainer changes when the project moves.
# ---------------------------------------------------------------------------------------------
HF_REPO = os.environ.get("MAIRCORRIDOR_HF_REPO", "M-Air/m-air_digital_twin")   # Hugging Face dataset id
AIRSIM_VERSION = "1.0.1"                                                        # Project AirSim release
AIRSIM_GIT = "https://github.com/iamaisim/ProjectAirSim.git"
AIRSIM_RELEASE = ("https://github.com/iamaisim/ProjectAirSim/releases/download/v{v}/"
                  "ProjectAirSim-Plugin-{os}-UE5_7-{v}.zip")

WINDOWS = platform.system() == "Windows"
UE_PLATFORM = "Win64" if WINDOWS else "Linux"
AIRSIM_PLUGINS = ("ProjectAirSim", "Drone", "Rover")
BUNDLED_PROJECT = os.path.join(HERE, "MAirCorridorSim", "MAirCorridorSim.uproject")
PLUGIN_SOURCE = os.path.join(HERE, "MAirCorridorSim", "Plugins", "MAirCorridor")
MARKER = ".maircorridor_assets.json"


def say(text=""):
    print(text, flush=True)


def step(n, text):
    say("\n[%d/8] %s" % (n, text))


def stop(text):
    say("\nERROR: " + text)
    sys.exit(1)


def run(cmd, **kw):
    say("  $ " + " ".join(str(c) for c in cmd))
    return subprocess.call(cmd, **kw)


def gb(n):
    return "%.1f GB" % (n / 1e9)


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(8 << 20), b""):
            h.update(block)
    return h.hexdigest()


# ---------------------------------------------------------------------------------------------
# 1. Checks
# ---------------------------------------------------------------------------------------------

def find_ue_root(given):
    root = given or os.environ.get("UE_ROOT")
    if not root:
        stop("Unreal Engine 5.7 is needed. Pass --ue-root /path/to/engine (the folder that holds "
             "Engine/), or set UE_ROOT.")
    root = os.path.abspath(os.path.expanduser(root))
    version = os.path.join(root, "Engine", "Build", "Build.version")
    if not os.path.isfile(version):
        stop("%s is not an Unreal Engine folder (no Engine/Build/Build.version)." % root)
    with open(version) as f:
        v = json.load(f)
    found = "%s.%s.%s" % (v.get("MajorVersion"), v.get("MinorVersion"), v.get("PatchVersion"))
    if (v.get("MajorVersion"), v.get("MinorVersion")) != (5, 7):
        say("  WARNING: this is Unreal Engine %s. The environment was made with 5.7; older engines "
            "cannot open its assets." % found)
    else:
        say("  Unreal Engine %s at %s" % (found, root))
    return root


def build_script(ue_root):
    name = "Build.bat" if WINDOWS else os.path.join("Linux", "Build.sh")
    return os.path.join(ue_root, "Engine", "Build", "BatchFiles", name)


def editor_target(project):
    """The editor target of a C++ project, from its Source folder: <Name>Editor.Target.cs."""
    source = os.path.join(os.path.dirname(project), "Source")
    if os.path.isdir(source):
        for name in sorted(os.listdir(source)):
            if name.endswith("Editor.Target.cs"):
                return name[:-len(".Target.cs")]
    return None


# ---------------------------------------------------------------------------------------------
# 2. Python environment
# ---------------------------------------------------------------------------------------------

def venv_python(venv):
    return os.path.join(venv, "Scripts", "python.exe") if WINDOWS else os.path.join(venv, "bin", "python")


def make_venv(venv):
    py = venv_python(venv)
    if not os.path.isfile(py):
        if run([sys.executable, "-m", "venv", venv]) != 0:
            stop("could not create a Python environment. On Ubuntu: sudo apt install python3-venv")
    run([py, "-m", "pip", "install", "--quiet", "--upgrade", "pip"])
    if run([py, "-m", "pip", "install", "--quiet", "-r", os.path.join(HERE, "requirements.txt")]) != 0:
        stop("pip could not install requirements.txt (see the output above).")
    return py


# ---------------------------------------------------------------------------------------------
# 3 and 4. Assets
# ---------------------------------------------------------------------------------------------

def load_manifest(folder):
    with open(os.path.join(folder, "manifest.json")) as f:
        return json.load(f)


def download_assets(py, repo, folder, token_hint=True):
    """Fetch the dataset into folder with huggingface_hub (resumes a partial download)."""
    code = ("import sys\n"
            "from huggingface_hub import snapshot_download\n"
            "snapshot_download(repo_id=sys.argv[1], repo_type='dataset', local_dir=sys.argv[2],\n"
            "                  allow_patterns=['manifest.json', 'unreal_content/*', 'unreal_content/*/*',\n"
            "                                  'terrain_heightmap/*/*'])\n")
    os.makedirs(folder, exist_ok=True)
    if run([py, "-c", code, repo, folder]) != 0:
        stop("the download from Hugging Face failed.\n"
             "  - check the dataset id (%s); pass another with --hf-repo\n"
             "  - if the dataset is private or gated: %s -m huggingface_hub.commands.huggingface_cli login\n"
             "  - or download it yourself and pass the folder with --assets-dir (docs/MANUAL_INSTALL.md)"
             % (repo, py))


def safe_extract(archive, dest):
    """Unpack a tar archive into dest, refusing anything that would land outside it."""
    dest_real = os.path.realpath(dest)
    with tarfile.open(archive, "r:*") as tar:
        if hasattr(tarfile, "data_filter"):
            tar.extractall(dest, filter="data")
            return
        for member in tar:
            target = os.path.realpath(os.path.join(dest, member.name))
            if not (target == dest_real or target.startswith(dest_real + os.sep)):
                stop("%s holds a path outside the install folder: %s" % (archive, member.name))
            if member.issym() or member.islnk() or member.isdev():
                stop("%s holds a link or device entry: %s" % (archive, member.name))
            tar.extract(member, dest)


def install_assets(manifest, source, plugin_dir, assets_dir, verify=True, move=False, force=False):
    """Put every manifest item where it belongs. A marker in the plugin folder records what is
    already there, by checksum, so a second run only does what is new."""
    marker_path = os.path.join(plugin_dir, MARKER)
    done = {}
    if os.path.isfile(marker_path) and not force:
        with open(marker_path) as f:
            done = json.load(f)
    roots = {"plugin": plugin_dir, "assets": assets_dir}
    for item in manifest["items"]:
        src = os.path.join(source, item["path"])
        if done.get(item["path"]) == item["sha256"]:
            say("  already installed: %s" % item["path"])
            continue
        if not os.path.isfile(src):
            stop("%s is missing from %s" % (item["path"], source))
        if os.path.getsize(src) != item["bytes"]:
            stop("%s is %d bytes, the manifest says %d: the download is incomplete. Run again."
                 % (item["path"], os.path.getsize(src), item["bytes"]))
        if verify:
            say("  checking   %s (%s)" % (item["path"], gb(item["bytes"])))
            if sha256(src) != item["sha256"]:
                stop("%s does not match its checksum: delete it and run again." % item["path"])
        if item["kind"] == "archive":
            say("  unpacking  %s" % item["path"])
            safe_extract(src, roots[item["extract_to"]])
        else:
            root, rel = item["install_to"].split(":", 1)
            dest = os.path.join(roots[root], *rel.split("/"))
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            say("  placing    %s" % item["path"])
            if move:
                shutil.move(src, dest)
            else:
                shutil.copy2(src, dest)
        if move and os.path.isfile(src):
            os.remove(src)
        done[item["path"]] = item["sha256"]
        with open(marker_path, "w") as f:
            json.dump(done, f, indent=1)


# ---------------------------------------------------------------------------------------------
# 5 and 6. Project AirSim
# ---------------------------------------------------------------------------------------------

def classify_airsim(path):
    """What --airsim points at: ('source', clone, plugins) or ('release', None, plugins)."""
    path = os.path.abspath(os.path.expanduser(path))
    if os.path.isfile(path) and path.lower().endswith(".zip"):
        return "zip", path, None
    blocks = os.path.join(path, "unreal", "Blocks", "Plugins")
    if os.path.isfile(os.path.join(blocks, "ProjectAirSim", "ProjectAirSim.uplugin")):
        return "source", path, blocks
    for plugins in (os.path.join(path, "Plugins"), path):
        if os.path.isfile(os.path.join(plugins, "ProjectAirSim", "ProjectAirSim.uplugin")):
            return "release", None, plugins
    stop("%s is not a Project AirSim plugin package (a folder with Plugins/ProjectAirSim), its "
         ".zip, or a source clone (with unreal/Blocks/Plugins)." % path)


def unzip_plugin(zip_path, downloads):
    dest = os.path.join(downloads, "ProjectAirSim-Plugin")
    if not os.path.isdir(dest):
        say("  unzipping %s" % zip_path)
        with zipfile.ZipFile(zip_path) as z:
            z.extractall(dest)
    for root, dirs, _files in os.walk(dest):
        if os.path.isfile(os.path.join(root, "ProjectAirSim", "ProjectAirSim.uplugin")):
            return root
    stop("no ProjectAirSim plugin inside %s" % zip_path)


def fetch_plugin_release(downloads):
    url = AIRSIM_RELEASE.format(v=AIRSIM_VERSION, os="Windows" if WINDOWS else "Linux")
    os.makedirs(downloads, exist_ok=True)
    dest = os.path.join(downloads, os.path.basename(url))
    if not os.path.isfile(dest):
        say("  downloading %s" % url)
        try:
            urllib.request.urlretrieve(url, dest + ".part")
        except Exception as e:                                               # noqa: BLE001
            stop("could not download the Project AirSim plugin (%s).\nDownload it from "
                 "https://github.com/iamaisim/ProjectAirSim/releases and pass it with --airsim." % e)
        os.replace(dest + ".part", dest)
    return unzip_plugin(dest, downloads)


def simlibs_built(plugins):
    libs = os.path.join(plugins, "ProjectAirSim", "SimLibs")
    return os.path.isdir(os.path.join(libs, "core_sim")) and os.path.isdir(os.path.join(libs, "simserver"))


def copy_airsim_plugins(plugins, project_plugins, refresh):
    for name in AIRSIM_PLUGINS:
        src, dest = os.path.join(plugins, name), os.path.join(project_plugins, name)
        if os.path.realpath(src) == os.path.realpath(dest):
            say("  %s is already this project's own" % name)
            continue
        if os.path.isdir(dest) and not refresh:
            say("  already there: Plugins/%s (use --refresh-airsim to replace it)" % name)
            continue
        if not os.path.isdir(src):
            stop("%s has no %s plugin" % (plugins, name))
        if os.path.isdir(dest):
            shutil.rmtree(dest)
        say("  copying %s" % name)
        shutil.copytree(src, dest, ignore=shutil.ignore_patterns("Binaries", "Intermediate"))


def fetch_client(dest):
    """Only Project AirSim's Python client and sample configs, not the whole repository."""
    if os.path.isdir(os.path.join(dest, "client", "python", "projectairsim", "src")):
        say("  already there: %s" % dest)
        return
    if not shutil.which("git"):
        stop("git is needed to fetch Project AirSim's Python client.")
    tag = "v" + AIRSIM_VERSION
    if run(["git", "clone", "--depth", "1", "--branch", tag, "--filter=blob:none", "--sparse",
            AIRSIM_GIT, dest]) != 0 or run(["git", "-C", dest, "sparse-checkout", "set", "client/python"]) != 0:
        stop("could not fetch Project AirSim %s from %s" % (tag, AIRSIM_GIT))


# ---------------------------------------------------------------------------------------------
# The plugin's code, for a project that is not the bundled one
# ---------------------------------------------------------------------------------------------

def copy_plugin_code(dest):
    if os.path.realpath(dest) == os.path.realpath(PLUGIN_SOURCE):
        return
    say("  copying the MAirCorridor plugin code to %s" % dest)
    shutil.copytree(PLUGIN_SOURCE, dest, dirs_exist_ok=True,
                    ignore=shutil.ignore_patterns("Content", "Binaries", "Intermediate", "__pycache__", MARKER))


def write_env(path, values):
    with open(path, "w") as f:
        f.write("# Written by install.py. Read by the scripts in scripts/. Edit freely.\n")
        for key, value in values.items():
            f.write('%s="%s"\n' % (key, value))


# ---------------------------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--ue-root", help="Unreal Engine 5.7 (the folder holding Engine/). Default: $UE_ROOT")
    ap.add_argument("--airsim", metavar="PATH",
                    help="Project AirSim: the unzipped plugin release, its .zip, or a source clone. "
                         "Default: download the %s plugin release" % AIRSIM_VERSION)
    ap.add_argument("--project", metavar="UPROJECT",
                    help="install into your own C++ Unreal project instead of the bundled MAirCorridorSim")
    ap.add_argument("--hf-repo", default=HF_REPO, help="Hugging Face dataset id (default: %(default)s)")
    ap.add_argument("--assets-dir", metavar="DIR",
                    help="a copy of the dataset already on disk: nothing is downloaded")
    ap.add_argument("--refresh-airsim", action="store_true",
                    help="replace the project's ProjectAirSim/Drone/Rover plugins (after rebuilding sim libs)")
    ap.add_argument("--force-assets", action="store_true", help="unpack the assets again")
    ap.add_argument("--no-verify", action="store_true", help="skip the checksum of each download")
    ap.add_argument("--keep-downloads", action="store_true", help="keep the archives after unpacking")
    ap.add_argument("--skip-build", action="store_true", help="do not build the editor target")
    ap.add_argument("--skip-python", action="store_true", help="do not make the Python environment")
    args = ap.parse_args()

    # 1 ---------------------------------------------------------------------------------------
    step(1, "Checking this machine")
    if sys.version_info < (3, 9):
        stop("Python 3.9 or newer is needed (this is %s)." % platform.python_version())
    ue_root = find_ue_root(args.ue_root)
    if not os.path.isfile(build_script(ue_root)):
        stop("no %s: this engine cannot build C++ projects." % build_script(ue_root))
    project = os.path.abspath(os.path.expanduser(args.project)) if args.project else BUNDLED_PROJECT
    if not os.path.isfile(project) or not project.endswith(".uproject"):
        stop("%s is not a .uproject file." % project)
    target = editor_target(project)
    if not target:
        stop("%s has no Source/*Editor.Target.cs. MAirCorridor and Project AirSim are C++ plugins, so "
             "the project must be a C++ project. Use the bundled one (leave out --project), or add a "
             "C++ class to yours in the editor first." % project)
    project_dir = os.path.dirname(project)
    plugins_dir = os.path.join(project_dir, "Plugins")
    plugin_dir = os.path.join(plugins_dir, "MAirCorridor")
    assets_dir = os.path.join(HERE, "MAirCorridor_Assets")
    downloads = os.path.join(HERE, ".downloads")
    say("  project %s (target %s)" % (project, target))

    kind, clone, airsim_plugins = (None, None, None)
    if args.airsim:
        kind, clone, airsim_plugins = classify_airsim(args.airsim)
        if kind == "zip":
            kind, airsim_plugins = "release", unzip_plugin(clone, downloads)
            clone = None
        say("  Project AirSim: %s at %s" % ("source clone" if kind == "source" else "plugin release",
                                            clone or airsim_plugins))
        if kind == "source" and not simlibs_built(airsim_plugins):
            stop("the sim libs in %s are not built yet. In the clone run:\n"
                 "    export UE_ROOT=%s\n    ./build.sh simlibs_release\nthen run this again."
                 % (clone, ue_root))
    elif os.path.isfile(os.path.join(plugins_dir, "ProjectAirSim", "ProjectAirSim.uplugin")):
        say("  Project AirSim: already in the project's Plugins folder")
        guess = os.path.abspath(os.path.join(project_dir, "..", ".."))
        if os.path.isdir(os.path.join(guess, "client", "python", "projectairsim", "src")):
            kind, clone = "source", guess
    else:
        say("  Project AirSim: the %s plugin release will be downloaded" % AIRSIM_VERSION)

    source = os.path.abspath(os.path.expanduser(args.assets_dir)) if args.assets_dir else downloads
    if args.assets_dir and not os.path.isfile(os.path.join(source, "manifest.json")):
        stop("%s has no manifest.json: it is not a copy of the dataset." % source)

    # 2 ---------------------------------------------------------------------------------------
    step(2, "Python environment")
    venv = os.path.join(HERE, ".venv")
    if args.skip_python:
        py = venv_python(venv) if os.path.isfile(venv_python(venv)) else sys.executable
        say("  skipped; using %s" % py)
    else:
        py = make_venv(venv)

    # 3 ---------------------------------------------------------------------------------------
    step(3, "3D assets from Hugging Face")
    if args.assets_dir:
        say("  using the copy in %s" % source)
    else:
        marker = os.path.join(plugin_dir, MARKER)
        have_all = False
        if os.path.isfile(marker) and os.path.isfile(os.path.join(downloads, "manifest.json")) \
                and not args.force_assets:
            with open(marker) as f:
                done = json.load(f)
            have_all = all(done.get(i["path"]) == i["sha256"] for i in load_manifest(downloads)["items"])
        if have_all:
            say("  everything is already installed; nothing to download")
        else:
            free = shutil.disk_usage(HERE).free
            say("  dataset %s; free disk space here: %s (about 35 GB is needed during the install)"
                % (args.hf_repo, gb(free)))
            if free < 35e9:
                say("  WARNING: that may not be enough.")
            download_assets(py, args.hf_repo, downloads)
    manifest = load_manifest(source)
    say("  dataset version %s, %d items, %s" % (manifest.get("version"), len(manifest["items"]),
                                                 gb(sum(i["bytes"] for i in manifest["items"]))))

    # 4 ---------------------------------------------------------------------------------------
    step(4, "Unpacking into %s" % plugin_dir)
    copy_plugin_code(plugin_dir)
    os.makedirs(assets_dir, exist_ok=True)
    install_assets(manifest, source, plugin_dir, assets_dir, verify=not args.no_verify,
                   move=not args.assets_dir and not args.keep_downloads, force=args.force_assets)
    level = os.path.join(plugin_dir, "Content", "Scene", "CorridorTerrain.umap")
    if not os.path.isfile(level):
        stop("the level is not where it should be (%s)." % level)

    # 5 ---------------------------------------------------------------------------------------
    step(5, "Project AirSim plugin")
    if airsim_plugins is None and not os.path.isfile(
            os.path.join(plugins_dir, "ProjectAirSim", "ProjectAirSim.uplugin")):
        airsim_plugins = fetch_plugin_release(downloads)
    if airsim_plugins:
        copy_airsim_plugins(airsim_plugins, plugins_dir, args.refresh_airsim)
    else:
        say("  nothing to do")

    # 6 ---------------------------------------------------------------------------------------
    step(6, "Project AirSim Python client")
    if clone:
        client_root = clone
        say("  using the source clone at %s" % clone)
    else:
        client_root = os.path.join(HERE, "ProjectAirSim")
        fetch_client(client_root)

    # 7 ---------------------------------------------------------------------------------------
    step(7, "Building %s (the first build takes several minutes)" % target)
    if args.skip_build:
        say("  skipped")
    elif run([build_script(ue_root), target, UE_PLATFORM, "Development", "-Project=" + project,
              "-WaitMutex"]) != 0:
        stop("the build failed (see the output above). docs/TROUBLESHOOTING.md lists the usual causes.")

    # 8 ---------------------------------------------------------------------------------------
    step(8, "Writing maircorridor.env")
    write_env(os.path.join(HERE, "maircorridor.env"), {
        "UE_ROOT": ue_root,
        "MAIR_PROJECT": project,
        "MAIR_PLUGIN": plugin_dir,
        "MAIR_PYTHON": py,
        "PROJECTAIRSIM_ROOT": client_root,
        "MAIRCORRIDOR_ASSETS": assets_dir,
        "MAIRCORRIDOR_PLAN": os.path.join(assets_dir, "ue_rect_3m", "mcity_rect_3m.json"),
    })
    say("\nDone. Next:\n"
        "  scripts/run_sim.sh                 start the simulator (the first start builds caches: be patient)\n"
        "  scripts/hover_test.sh              in a second terminal: take off, hover, land\n"
        "  scripts/fly_mission.sh missions/mcity_circle.json\n"
        "See README.md for the rest.")


if __name__ == "__main__":
    main()
