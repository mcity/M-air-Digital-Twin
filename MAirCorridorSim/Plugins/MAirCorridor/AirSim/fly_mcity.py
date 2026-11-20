"""fly_mcity.py - fly a Project AirSim drone over the M-City terrain, on the keyboard.

    py -3.10 client/unreal/MAirCorridor/AirSim/fly_mcity.py
    (or, in the project: py -3.10 <Project>/Plugins/MAirCorridor/AirSim/fly_mcity.py)

WHY A LAUNCHER RATHER THAN A COMMAND IN THE README. Four things have to line up before a drone
exists, and every one of them fails in a way that looks like something else:

  * PYTHON 3.9 OR NEWER. The client's own pyproject says `requires-python = ">=3.7"` and that is
    wrong - world.py annotates `list[str]`, a PEP 585 builtin generic, which is a TypeError on 3.8.
    This box's default `python` IS 3.8, so the obvious command fails with something that reads like
    a corrupt install rather than a version problem.
  * THE CLIENT PACKAGE. `pip install -e` on it fails under older setuptools (its `project.license`
    field matches two PEP 621 definitions at once), so this runs it from `src` on PYTHONPATH
    instead of installing it. Nothing is modified in their tree.
  * THE SCENE CONFIG must sit beside the robot configs it names, because robot-config is resolved
    relative to the sim config directory. Ours references one of theirs, so it is copied next to
    them rather than vendored - a vendored copy is one that silently stops matching.
  * THE EDITOR MUST ALREADY BE IN PLAY. Project AirSim's sim server starts with the game and waits;
    a client that connects to nothing reports a connection error and not "press Play".

THE DRONE IS NOT PLACED IN THE LEVEL AND CANNOT BE. Project AirSim spawns robots from a scene
config when a CLIENT connects, so there is no actor to drag in - which is worth knowing before
spending an afternoon looking for one in the place picker.
"""
import argparse
import io
import os
import re
import shutil
import subprocess
import sys

# Built by Tools/build_tools.py, this runs as Tools/fly_mcity.exe: our configs are still in
# AirSim/sim_config beside Tools, and the client and its samples travel inside the release.
FROZEN = bool(getattr(sys, "frozen", False))
HERE = (os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(sys.executable))), "AirSim")
        if FROZEN else os.path.dirname(os.path.abspath(__file__)))

# Where the Project AirSim source clone lives: beside the Unreal project, in the folder that holds
# it (<workspace>/<project>/Plugins/MAirCorridor/AirSim). Overridable, because it is not part of
# this repo.
DEFAULT_CLONE = (os.environ.get("PROJECTAIRSIM_ROOT")
                 or os.path.join(os.path.abspath(os.path.join(HERE, "..", "..", "..", "..")),
                                 "ProjectAirSim"))

SCENE = "scene_mcity.jsonc"
# Our scene names this, and it is one of theirs - copied beside ours at run time rather than
# vendored, so it cannot drift from the version their libs expect.
ROBOT_CONFIG = "robot_quadrotor_fastphysics_weather.jsonc"


def robot_config_named(scene_path):
    """The robot config filename a scene names, without pulling in a JSON parser for comments."""
    try:
        text = io.open(scene_path, encoding="utf-8").read()
    except OSError:
        return None
    match = re.search(r'"robot-config"\s*:\s*"([^"]+)"', text)
    return match.group(1) if match else None


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--clone", default=DEFAULT_CLONE,
                    help="the ProjectAirSim source clone (or set PROJECTAIRSIM_ROOT)")
    ap.add_argument("--scene", default=SCENE, help="scene config to load")
    ap.add_argument("--address", default="127.0.0.1")
    a = ap.parse_args()

    client_src = os.path.join(a.clone, "client", "python", "projectairsim", "src")
    scripts = os.path.join(a.clone, "client", "python", "example_user_scripts")
    if FROZEN:
        client_src = scripts = os.path.join(os.path.dirname(os.path.abspath(sys.executable)),
                                            "projectairsim")
    their_cfg = os.path.join(scripts, "sim_config")
    our_cfg = os.path.join(HERE, "sim_config")

    for path, what in ((client_src, "the client package"), (scripts, "the example scripts")):
        if not os.path.isdir(path):
            sys.exit("Cannot find %s at %s.\nClone ProjectAirSim, or pass --clone / set "
                     "PROJECTAIRSIM_ROOT." % (what, path))

    # Our configs beside their samples. Copying ours to THEM rather than theirs to us keeps a
    # single copy of each of their samples, which is the half that gets updated. Every .jsonc we
    # have goes across, not only the scene: a scene names its robot config by filename and the
    # client looks for it in the same folder, so our own robot config has to travel with it.
    src_scene = os.path.join(our_cfg, a.scene)
    if not os.path.isfile(src_scene):
        sys.exit("No scene config at %s" % src_scene)
    for name in sorted(os.listdir(our_cfg)):
        if name.endswith(".jsonc"):
            shutil.copy2(os.path.join(our_cfg, name), os.path.join(their_cfg, name))
    print("scene       %s -> %s" % (a.scene, their_cfg))

    # Whichever robot config the chosen scene names has to be findable, ours or theirs.
    named = robot_config_named(src_scene) or ROBOT_CONFIG
    if not os.path.isfile(os.path.join(their_cfg, named)):
        sys.exit("The scene names %s and it is not in %s. A robot config of theirs must come from "
                 "the clone; one of ours belongs in %s." % (named, their_cfg, our_cfg))

    if sys.version_info < (3, 9):
        sys.exit("This needs Python 3.9 or newer (the client annotates list[str], which is a "
                 "TypeError on 3.8) - run it with `py -3.10`. You are on %d.%d."
                 % sys.version_info[:2])

    env = dict(os.environ)
    env["PYTHONPATH"] = client_src + os.pathsep + env.get("PYTHONPATH", "")

    cmd = [sys.executable, os.path.join(scripts, "keyboard_control.py"),
           "--sceneconfigfile", a.scene, "--address", a.address]
    print("running     %s" % " ".join(cmd[1:]))
    print()
    print("  W / S      pitch forward / back        UP / DOWN     throttle")
    print("  A / D      roll left / right           LEFT / RIGHT  yaw")
    print("  L          land")
    print()
    print("  The EDITOR MUST ALREADY BE IN PLAY - the sim server starts with the game and this")
    print("  connects to it. If it reports a connection error, that is what it means.")
    print()
    if FROZEN:
        # No Python to start their script with: it is inside this executable, so run it here,
        # from the folder its sim_config is relative to.
        import asyncio
        os.chdir(scripts)
        sys.argv = ["keyboard_control.py", "--sceneconfigfile", a.scene, "--address", a.address]
        import keyboard_control
        asyncio.run(keyboard_control.main())
        return

    sys.exit(subprocess.call(cmd, cwd=scripts, env=env))


if __name__ == "__main__":
    main()
