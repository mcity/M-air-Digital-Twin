"""mcity_twin_footprint.py - where the Mcity digital twin has geometry, in the twin's own frame.

In the open editor (Output Log, Python), or on its own, with the editor closed, off screen:

    UnrealEditor.exe <project>.uproject -ExecutePythonScript="<absolute path>/Tools/unreal/mcity_twin_footprint.py"
        -RenderOffScreen -nosplash -unattended          and set MAIR_QUIT=1 so it closes when done

Not as a commandlet (UnrealEditor-Cmd -run=pythonscript): there every component of the twin's levels
comes back with no mesh, so there is nothing to measure. It opens levels and saves nothing.

Opens each of the twin's levels on its own (the McityMap plugin, /McityMap) and writes the ground plan
of everything in it to Saved/MAirCorridor/mcity_twin_footprint.json: for a large piece (terrain,
roads, anything over 30 m across) every triangle of its mesh, flattened to X, Y, and for a small one
the corners of its bounding box. Triangles, not vertices: the twin's ground has triangles tens of
metres across over open grass, and its corners alone leave the middle of them out. In the twin's frame: centimetres, +X true north, +Y true east. Tools/mcity_clear.py
turns that into the twin's footprint on the corridor level and finds the corridor's own trees and
buildings under it.
"""
import io
import json
import os

import unreal

MARK = "MAIRTWINFP"
LEVELS = ["/McityMap/McityMap_Main", "/McityMap/Sublevels/McityMap_Terrain",
          "/McityMap/Sublevels/McityMap_StaticProps", "/McityMap/Sublevels/McityMap_StreetLights",
          "/McityMap/Sublevels/McityMap_UECableActors", "/McityMap/Sublevels/CarlaSigns",
          "/McityMap/Sublevels/CarlaTrafficLights", "/McityMap/Sublevels/McityMap_OpenDrive"]
LARGE_CM = 3000.0
PROJECT = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())
OUT = os.path.join(PROJECT, "Saved", "MAirCorridor", "mcity_twin_footprint.json")


def say(text):
    unreal.log_warning("%s %s" % (MARK, text))


def world_box(xf, lo, hi):
    """The X, Y box round a local box (lo, hi) put through the transform xf."""
    xs, ys = [], []
    for x in (lo.x, hi.x):
        for y in (lo.y, hi.y):
            for z in (lo.z, hi.z):
                w = xf.transform_location(unreal.Vector(x, y, z))
                xs.append(w.x)
                ys.append(w.y)
    return min(xs), min(ys), max(xs), max(ys)


actors_sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
levels_sub = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
triangles, boxes, stats = [], [], {}
seen = set()            # the main level opens with its sublevels in it, so each piece comes round twice
for level in LEVELS:
    if not levels_sub.load_level(level):
        say("could not open %s" % level)
        continue
    n_large = n_small = n_empty = 0
    for actor in actors_sub.get_all_level_actors():
        for comp in actor.get_components_by_class(unreal.StaticMeshComponent):
            mesh = comp.static_mesh
            if mesh is None:
                n_empty += 1
                continue
            if not comp.is_visible():
                continue
            lo_l, hi_l = comp.get_local_bounds()
            xf = comp.get_world_transform()
            key = (mesh.get_path_name(), round(xf.translation.x), round(xf.translation.y), round(xf.translation.z))
            if key in seen:
                continue
            seen.add(key)
            if isinstance(comp, unreal.InstancedStaticMeshComponent):
                for i in range(comp.get_instance_count()):
                    t = comp.get_instance_transform(i, True)
                    boxes.append(tuple(round(v, 1) for v in world_box(t, lo_l, hi_l)))
                n_small += comp.get_instance_count()
                continue
            x0, y0, x1, y1 = world_box(xf, lo_l, hi_l)
            if max(x1 - x0, y1 - y0) > LARGE_CM:
                for section in range(mesh.get_num_sections(0)):
                    got = unreal.ProceduralMeshLibrary.get_section_from_static_mesh(mesh, 0, section)
                    flat = [xf.transform_location(v) for v in got[0]]
                    flat = [(round(w.x, 1), round(w.y, 1)) for w in flat]
                    index = list(got[1])
                    for k in range(0, len(index) - 2, 3):
                        a, b, c = flat[index[k]], flat[index[k + 1]], flat[index[k + 2]]
                        triangles.append((a[0], a[1], b[0], b[1], c[0], c[1]))
                n_large += 1
            else:
                boxes.append((round(x0, 1), round(y0, 1), round(x1, 1), round(y1, 1)))
                n_small += 1
    stats[level] = {"large_meshes": n_large, "small_pieces": n_small, "no_mesh": n_empty}
    say("%s: %d large meshes sampled, %d small pieces boxed, %d components with no mesh"
        % (level, n_large, n_small, n_empty))

os.makedirs(os.path.dirname(OUT), exist_ok=True)
with io.open(OUT, "w", encoding="utf-8") as f:
    json.dump({"frame": "the twin's own: cm, +X true north, +Y true east, origin lat 42.3005934157 "
                        "lon -83.69928318881136",
               "levels": stats, "triangles": triangles, "boxes": boxes}, f)
say("wrote %s: %d triangles, %d boxes" % (OUT, len(triangles), len(boxes)))
if os.environ.get("MAIR_QUIT") == "1":
    unreal.SystemLibrary.quit_editor()
