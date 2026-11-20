"""measure_level.py - where the corridor level's landscape actually is, written to Tools/level.json.

Run it in the editor, headless, with absolute paths (relative ones resolve against the editor's
Binaries folder):

    UnrealEditor-Cmd.exe <project>.uproject -run=pythonscript
        -script=<absolute path>/Tools/unreal/measure_level.py
        "-EnablePlugins=PythonScriptPlugin,EditorScriptingUtilities" -unattended -nullrhi

WHY. The flight tools turn heights into Unreal coordinates using the landscape's placement. The
landscape plan records where the landscape was put on import, but a landscape can be moved after
that, and this one was: down to Z 0 with everything on it, 236 m below where the plan says. The
tools believed the plan and flew every mission 236 m too high. This reads the placement from the
level itself, and checks it by tracing straight down at a point to see what the ground is.

Every line meant to be read starts with MEASURELEVEL, to pull out of the editor's log.
"""
import io
import json
import os
import time

import unreal

MARK = "MEASURELEVEL"
LEVEL = os.environ.get("MAIRCORRIDOR_LEVEL_PATH", "/MAirCorridor/Scene/CorridorTerrain")
# Where to trace down as a check, in Unreal centimetres: the drone's start in the M-City scenes.
PROBE = (982700.0, 1095500.0)
OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "level.json")


def say(text):
    unreal.log_warning("%s %s" % (MARK, text))


world = unreal.EditorLoadingAndSavingUtils.load_map(LEVEL)
# World Partition loads nothing by itself here; load what is around the probe so a trace has
# landscape to hit.
box = unreal.Box(unreal.Vector(PROBE[0] - 50000, PROBE[1] - 50000, -1000000),
                 unreal.Vector(PROBE[0] + 50000, PROBE[1] + 50000, 1000000))
descs = unreal.WorldPartitionBlueprintLibrary.get_intersecting_actor_descs(box)
if isinstance(descs, tuple):
    descs = descs[-1]
unreal.WorldPartitionBlueprintLibrary.load_actors([d.guid for d in descs])

landscapes = [a for a in unreal.EditorLevelLibrary.get_all_level_actors()
              if a.get_class().get_name() == "Landscape"]
if len(landscapes) != 1:
    say("expected one Landscape actor in %s, found %d; nothing written" % (LEVEL, len(landscapes)))
else:
    landscape = landscapes[0]
    loc, scale = landscape.get_actor_location(), landscape.get_actor_scale3d()
    hit = unreal.SystemLibrary.line_trace_single(
        world, unreal.Vector(PROBE[0], PROBE[1], 1000000.0),
        unreal.Vector(PROBE[0], PROBE[1], -1000000.0), unreal.TraceTypeQuery.TRACE_TYPE_QUERY1,
        True, [], unreal.DrawDebugTrace.NONE, True)
    check = {"at_unreal_cm": list(PROBE)}
    if hit is not None:
        t = hit.to_tuple()
        if t[0]:
            check.update({"trace_hit_z_cm": round(t[4].z, 1), "hit": t[9].get_name()})
    level = {
        "WHAT": "Where the corridor level's landscape actually is, measured from the level by "
                "Tools/unreal/measure_level.py. flightplan.py uses it in place of the landscape "
                "plan's own placement. Measure again whenever the landscape is moved.",
        "level": LEVEL,
        "plan_name": landscape.get_actor_label(),
        "landscape_location_cm": [round(loc.x, 2), round(loc.y, 2), round(loc.z, 2)],
        "landscape_scale": [round(scale.x, 3), round(scale.y, 3), round(scale.z, 3)],
        "check": check,
        "measured": time.strftime("%Y-%m-%d"),
    }
    with io.open(OUT, "w", encoding="utf-8", newline="\n") as f:
        json.dump(level, f, indent=2)
        f.write("\n")
    say("wrote %s: %s" % (OUT, json.dumps(level)))
