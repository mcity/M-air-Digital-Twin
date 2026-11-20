"""import_aircraft.py - bring the built aircraft into Unreal, and check they came in the right way round.

In the open editor (Output Log, Python), or on its own, with the editor closed, off screen:

    UnrealEditor.exe <project>.uproject -ExecutePythonScript="<absolute path>/Tools/unreal/import_aircraft.py"
        -RenderOffScreen -nosplash -unattended          and set MAIR_QUIT=1 so it closes when done

Not as a commandlet (UnrealEditor-Cmd -run=pythonscript): the FBX importer needs the editor's UI
framework and stops the process without it.

Imports Tools/work/aircraft/<name>/<name>.fbx (made by Tools/blender/aircraft_builder.py) for every
aircraft in Tools/aircraft/fleet.json into /MAirCorridor/Aircraft/<name>/, replacing what is there,
and saves. A drone built with its propellers marked "spin" also has <name>_body (everything but the
propellers) and <name>_rotor (one propeller, flat, about its own centre), which its Project AirSim
config (Tools/drone_configs.py) puts on the frame and on each rotor; those come in too, the body
with a collision box round it, which is how Project AirSim knows the drone has touched something.
Without one a landing drone sinks through the ground, still landing.
MAIR_ONLY=name1,name2 imports just those; MAIR_CHECK_ONLY=1 checks what is there and imports nothing.

Then it checks each mesh against the build's own record (model.json): the size in centimetres, and
which way it faces, because an importer that turns a model round leaves it the right size and wrong:
the top of the fin must be aft of the middle (-X) on anything with a fin. A mismatch is reported,
and the run ends with a non-zero count of failures for a script to see. A rotor must be its
propeller's diameter across and centred on its spin axis, or it wobbles as it turns.
"""
import io
import json
import os

import unreal

MARK = "MAIRAIRCRAFT"
PLUGINS = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_plugins_dir())
TOOLS = os.path.join(PLUGINS, "MAirCorridor", "Tools")
WORK = os.path.join(TOOLS, "work", "aircraft")
DEST = "/MAirCorridor/Aircraft"
ONLY = [n for n in os.environ.get("MAIR_ONLY", "").split(",") if n]
CHECK_ONLY = os.environ.get("MAIR_CHECK_ONLY") == "1"      # check what is there, import nothing


def say(text):
    unreal.log_warning("%s %s" % (MARK, text))


def import_fbx(path, dest):
    task = unreal.AssetImportTask()
    task.set_editor_property("filename", path)
    task.set_editor_property("destination_path", dest)
    task.set_editor_property("automated", True)
    task.set_editor_property("replace_existing", True)
    task.set_editor_property("save", True)
    ui = unreal.FbxImportUI()
    ui.set_editor_property("import_mesh", True)
    ui.set_editor_property("import_materials", True)
    ui.set_editor_property("import_textures", False)
    ui.set_editor_property("import_as_skeletal", False)
    ui.set_editor_property("mesh_type_to_import", unreal.FBXImportType.FBXIT_STATIC_MESH)
    data = ui.get_editor_property("static_mesh_import_data")
    data.set_editor_property("combine_meshes", True)
    data.set_editor_property("auto_generate_collision", False)
    data.set_editor_property("import_uniform_scale", 1.0)
    task.set_editor_property("options", ui)
    unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
    return [p for p in task.get_editor_property("imported_object_paths")]


def bounds(mesh):
    box = mesh.get_bounding_box()
    return ([box.max.x - box.min.x, box.max.y - box.min.y, box.max.z - box.min.z],
            [(box.max.x + box.min.x) / 2, (box.max.y + box.min.y) / 2, (box.max.z + box.min.z) / 2])


def import_part(name, part, fbx):
    """Import (unless only checking) and load <name><part>, or report why not."""
    if not os.path.isfile(fbx):
        say("%s: no %s (build it with Tools/blender/aircraft_builder.py)" % (name, fbx))
        return None
    paths = [] if CHECK_ONLY else import_fbx(fbx, "%s/%s" % (DEST, name))
    mesh = unreal.EditorAssetLibrary.load_asset("%s/%s/%s%s" % (DEST, name, name, part))
    if not isinstance(mesh, unreal.StaticMesh):
        say("%s: import made %s, no static mesh called %s%s" % (name, paths, name, part))
        return None
    return mesh


def vertices(mesh):
    verts = []
    try:
        for section in range(mesh.get_num_sections(0)):          # every material, not just the first
            verts += list(unreal.ProceduralMeshLibrary.get_section_from_static_mesh(mesh, 0, section)[0])
    except Exception:
        return []
    return verts


def box_collision(mesh):
    """One simple box round the whole mesh, replacing any other collision, and saved. Returns how many
    simple shapes the mesh has after."""
    sub = unreal.get_editor_subsystem(unreal.StaticMeshEditorSubsystem)
    if not CHECK_ONLY:
        sub.remove_collisions(mesh)
        sub.add_simple_collisions(mesh, unreal.ScriptCollisionShapeType.BOX)
        unreal.EditorAssetLibrary.save_loaded_asset(mesh, False)
    return sub.get_simple_collision_count(mesh)


def facing_ok(mesh):
    """True when the highest vertices (the fin) are aft of the middle, None when it cannot tell."""
    verts = vertices(mesh)
    if not verts:
        return None
    top = max(v.z for v in verts)
    high = [v for v in verts if v.z > top - 0.05 * (top - min(v.z for v in verts))]
    return sum(v.x for v in high) / len(high) < 0.0


with io.open(os.path.join(TOOLS, "aircraft", "fleet.json"), encoding="utf-8") as f:
    fleet = json.load(f)["aircraft"]

failures = 0
for entry in fleet:
    name = entry["name"]
    if ONLY and name not in ONLY:
        continue
    folder = os.path.join(WORK, name)
    mesh = import_part(name, "", os.path.join(folder, name + ".fbx"))
    if mesh is None:
        failures += 1
        continue
    with io.open(os.path.join(folder, "model.json"), encoding="utf-8") as f:
        built = json.load(f)
    want = [v * 100.0 for v in built["size_m"]]
    got = bounds(mesh)[0]
    size_ok = all(abs(g - w) <= 0.02 * max(w, 1.0) + 1.0 for g, w in zip(got, want))
    # A fin to judge by: not a balloon, a truck or a multirotor, and not a helicopter, whose
    # highest point is its rotor.
    has_fin = entry.get("class") not in ("balloon", "vehicle", "rotorcraft") and entry.get("role") != "multirotor"
    fin = facing_ok(mesh) if has_fin else True
    ok = size_ok and fin is not False
    failures += 0 if ok else 1
    say("%-24s %s  %.0f x %.0f x %.0f cm (built %.0f x %.0f x %.0f)%s%s" % (
        name, "ok  " if ok else "FAIL", got[0], got[1], got[2], want[0], want[1], want[2],
        "" if size_ok else "  SIZE DIFFERS", "" if fin is not False else "  FACES BACKWARDS"))

    rotors = built.get("rotors") or []
    if not rotors:
        continue
    body = import_part(name, "_body", os.path.join(folder, name + "_body.fbx"))
    rotor = import_part(name, "_rotor", os.path.join(folder, name + "_rotor.fbx"))
    if body is None or rotor is None:
        failures += 1
        continue
    # Across the tips, whichever way the blades lie, and where the middle of the box is.
    want_across = rotors[0]["diameter_m"] * 100.0
    across = 2.0 * max([(v.x ** 2 + v.y ** 2) ** 0.5 for v in vertices(rotor)] or [0.0])
    (_, _, rz), (cx, cy, _) = bounds(rotor)
    rotor_ok = (abs(across - want_across) <= 0.03 * want_across and rz < 0.25 * want_across
                and abs(cx) < 1.0 and abs(cy) < 1.0)
    shapes = box_collision(body)
    parts_ok = rotor_ok and shapes > 0
    failures += 0 if parts_ok else 1
    say("%-24s %s  body %.0f x %.0f x %.0f cm, %s; rotor %.0f cm across, %.0f thick, about (%.1f, %.1f) "
        "(built %.0f across, centred), %d on the frame" % (
            name, "ok  " if parts_ok else "FAIL", *bounds(body)[0],
            "%d collision shape(s)" % shapes if shapes else "NO COLLISION",
            across, rz, cx, cy, want_across, len(rotors)))

say("done: %d failure(s)" % failures)
if os.environ.get("MAIR_QUIT") == "1":
    unreal.SystemLibrary.quit_editor()
