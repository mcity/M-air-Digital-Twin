"""toolpaths.py - where the tools and their files are, run as scripts or as the built executables.

Run as scripts, every file a tool reads is beside the .py files, and one tool starts another with
the same Python. Built by build_tools.py, each tool is an .exe in one folder, the Python they share
is in _internal beside them, and the files they read are beside the executables. A built module's
__file__ points inside _internal, so the folder is taken from the executable instead, and a tool
is started as its own .exe rather than as a script there is no Python to run.
"""
import os
import sys

FROZEN = bool(getattr(sys, "frozen", False))
HERE = os.path.dirname(os.path.abspath(sys.executable if FROZEN else __file__))
PLUGIN = os.path.dirname(HERE)

# Everything lives in one folder: the Unreal project, and beside it the Project AirSim clone and
# the MAirCorridor_Assets clone. <workspace>/<project>/Plugins/MAirCorridor/Tools, so the
# workspace is three folders above the plugin. Either can be moved with its environment variable.
WORKSPACE = os.path.dirname(os.path.dirname(os.path.dirname(PLUGIN)))
ASSETS = os.environ.get("MAIRCORRIDOR_ASSETS") or os.path.join(WORKSPACE, "MAirCorridor_Assets")
PROJECTAIRSIM = os.environ.get("PROJECTAIRSIM_ROOT") or os.path.join(WORKSPACE, "ProjectAirSim")

if FROZEN:
    # One built tool starting another is a different frozen application, and PyInstaller says to
    # tell it so, or the child can take the parent's environment for its own. Read only at a
    # program's start, so setting it here affects the children and not this one.
    os.environ["PYINSTALLER_RESET_ENVIRONMENT"] = "1"


def tool_command(script, *args):
    """The command line that runs a tool, given its script's name or path: python -u script.py,
    or, built, the .exe of the same name beside this one."""
    if FROZEN:
        name = os.path.splitext(os.path.basename(script))[0]
        return [os.path.join(HERE, name + ".exe")] + list(args)
    path = script if os.path.isabs(script) else os.path.join(HERE, script)
    return [sys.executable, "-u", path] + list(args)


def tool_exists(script):
    """Whether tool_command(script) has something to run."""
    return os.path.isfile(tool_command(script)[0 if FROZEN else 2])
