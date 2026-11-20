#!/usr/bin/env python3
"""mair.py - start the simulator and the flight tools on any operating system.

    python scripts/mair.py sim       [Unreal arguments]     start the simulator
    python scripts/mair.py editor    [Unreal arguments]     open the project in the Unreal Editor
    python scripts/mair.py hover                            the one-minute check: prints PASS or FAIL
    python scripts/mair.py mission   <mission.json> [...]   fly a mission file
    python scripts/mair.py keyboard                         fly on the keyboard
    python scripts/mair.py planner                          draw a mission on a map
    python scripts/mair.py run       <script.py> [...]      run your own script against the simulator

The .bat files beside this one are the Windows shortcuts for these commands (run_sim.bat is
"mair.py sim", and so on). On Linux the .sh files do the same job.

It reads maircorridor.env, which install.py writes, and needs only the Python standard library:
the tools themselves are started with the Python environment named there.
"""
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
WINDOWS = os.name == "nt"
LEVEL = "/MAirCorridor/Scene/CorridorTerrain?game=/Script/ProjectAirSim.ProjectAirSimGameMode"


def load_env(path):
    """KEY="value" lines, as install.py writes them. Values are taken as they are: a Windows
    path keeps its backslashes."""
    values = {}
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            value = value.strip()
            if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
                value = value[1:-1]
            values[key.strip()] = value
    return values


def settings():
    path = os.path.join(REPO, "maircorridor.env")
    if not os.path.isfile(path):
        sys.exit("maircorridor.env not found. Run install.py first (see README.md).")
    env = dict(os.environ)
    for key, value in load_env(path).items():
        env[key] = value
    for key in ("UE_ROOT", "MAIR_PROJECT", "MAIR_PLUGIN", "MAIR_PYTHON", "PROJECTAIRSIM_ROOT"):
        if not env.get(key):
            sys.exit("%s is not set in %s." % (key, path))
    env["PYTHONUNBUFFERED"] = "1"
    # Project AirSim's client is used from its source tree.
    client = os.path.join(env["PROJECTAIRSIM_ROOT"], "client", "python", "projectairsim", "src")
    env["PYTHONPATH"] = os.pathsep.join(p for p in (client, env.get("PYTHONPATH")) if p)
    # Ports the simulator listens on. Set both variables to move the simulator and the tools together.
    env.setdefault("AIRSIM_TOPICS_PORT", "8989")
    env.setdefault("AIRSIM_SERVICES_PORT", "8990")
    return env


def editor(env):
    name = os.path.join("Win64", "UnrealEditor.exe") if WINDOWS else os.path.join("Linux", "UnrealEditor")
    path = os.path.join(env["UE_ROOT"], "Engine", "Binaries", name)
    if not os.path.isfile(path):
        sys.exit("No Unreal Editor at %s. Check UE_ROOT in maircorridor.env." % path)
    return path


def command(what, args, env):
    """The command line for one of the commands above."""
    python = [env["MAIR_PYTHON"], "-u"]
    tool = python + [os.path.join(HERE, "run_tool.py")]
    plugin = env["MAIR_PLUGIN"]
    if what == "sim":
        # Hardware ray tracing is off unless MAIR_RAYTRACING is set: see docs/TROUBLESHOOTING.md.
        ray_tracing = [] if env.get("MAIR_RAYTRACING") else ["-noraytracing"]
        return [editor(env), env["MAIR_PROJECT"], LEVEL, "-game", "-windowed", "-ResX=1280", "-ResY=720"] \
            + ray_tracing + ["-topicsport=" + env["AIRSIM_TOPICS_PORT"],
                             "-servicesport=" + env["AIRSIM_SERVICES_PORT"]] + args
    if what == "editor":
        return [editor(env), env["MAIR_PROJECT"]] + args
    if what == "hover":
        return tool + [os.path.join(HERE, "hover_test.py")] + args
    if what == "mission":
        if not args:
            sys.exit("Which mission? For example: missions/mcity_circle.json")
        return tool + [os.path.join(plugin, "Tools", "fly_mission.py")] + args
    if what == "keyboard":
        if not WINDOWS:
            # The `keyboard` package needs root on Linux; this stand-in reads keys from the X session.
            env["PYTHONPATH"] = os.path.join(HERE, "keyboard_shim") + os.pathsep + env["PYTHONPATH"]
        return python + [os.path.join(plugin, "AirSim", "fly_mcity.py")] + args
    if what == "planner":
        return python + [os.path.join(plugin, "Tools", "flightplan_ui.py")] + args
    if what == "run":
        if not args:
            sys.exit("Which script? For example: scripts/hover_test.py")
        return tool + args
    sys.exit("Unknown command '%s'.\n%s" % (what, __doc__))


def main():
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help", "help"):
        print(__doc__)
        return 0
    env = settings()
    cmd = command(sys.argv[1], sys.argv[2:], env)
    if not os.path.isfile(cmd[0]):
        sys.exit("%s does not exist. Check maircorridor.env, or run install.py again." % cmd[0])
    if env.get("MAIR_PRINT_ONLY"):                    # show what would run, and run nothing
        print(subprocess.list2cmdline(cmd))
        return 0
    try:
        return subprocess.call(cmd, env=env)
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    sys.exit(main())
