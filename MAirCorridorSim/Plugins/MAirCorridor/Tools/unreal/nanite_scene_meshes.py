"""nanite_scene_meshes.py - Nanite on for the corridor's trees, rocks and building tiles.

Run it in the open editor: the Output Log's command box, switched from Cmd to Python, then

    exec(open(r"<project folder>/Plugins/MAirCorridor/Tools/unreal/nanite_scene_meshes.py").read())

WHY. Measured in the corridor level: the vegetation is 677,244 instances of 36 tree models and a
few rocks, the trees at 30,000 to 857,000 triangles EACH (a weeping willow is 856,860), with
Nanite off, no levels of detail and no cull distance. Every tree in view is drawn with every
triangle, in the main view and again in every camera capture a drone makes. The 100 building
tiles are light (about 1.45 million triangles in all) but carry about 90 material slots each,
which is a draw call per slot per tile per view. Nanite is made for exactly this: it draws a
mesh at the detail the pixels can show, culls instances on the GPU, and batches by material.

Trees get Shape Preservation set to Preserve Area as well, Unreal's setting for foliage: without
it Nanite thins leaves away at a distance and a wood goes bald. (Unreal 5.7 made the old Preserve
Area checkbox this setting; an earlier version of this script used the old name and stopped.)

Each mesh is saved as it is changed. Turning Nanite back off in a mesh's details undoes it.
MAIR_DRY=1 reports what would change and changes nothing.
"""
import os

import unreal

MARK = "MAIRNANITE"
DRY = os.environ.get("MAIR_DRY") == "1"
FOLDERS = {"/MAirCorridor/Vegetation/Trees": True,      # folder: is foliage
           "/MAirCorridor/Vegetation/Rocks": False,
           "/MAirCorridor/Buildings": False}


def say(text):
    unreal.log_warning("%s %s" % (MARK, text))
    print("%s %s" % (MARK, text))


PRESERVE_AREA = unreal.NaniteShapePreservation.PRESERVE_AREA

reg = unreal.AssetRegistryHelpers.get_asset_registry()
reg.scan_paths_synchronous(list(FOLDERS), True)
changed = already = 0
for folder, foliage in FOLDERS.items():
    found = reg.get_assets_by_path(folder, recursive=True)
    meshes = [a for a in found if str(a.asset_class_path.asset_name) == "StaticMesh"]
    tris_before = 0
    for data in meshes:
        mesh = unreal.load_asset(str(data.package_name))
        ns = mesh.get_editor_property("nanite_settings")
        tris_before += mesh.get_num_triangles(0)
        if ns.get_editor_property("enabled") and (
                not foliage or ns.get_editor_property("shape_preservation") == PRESERVE_AREA):
            already += 1
            continue
        # Nanite does not draw translucent materials; say so rather than discover it as a hole.
        for slot in mesh.get_editor_property("static_materials"):
            mi = slot.get_editor_property("material_interface")
            if mi and mi.get_blend_mode() in (unreal.BlendMode.BLEND_TRANSLUCENT,
                                              unreal.BlendMode.BLEND_ADDITIVE,
                                              unreal.BlendMode.BLEND_MODULATE):
                say("  %s: slot %s is translucent, which Nanite draws through the fallback mesh" % (
                    mesh.get_name(), slot.get_editor_property("material_slot_name")))
        # The settings are a copy until they are set back on the mesh, so a dry run sets every
        # field too: a renamed field fails the dry run instead of the real one.
        ns.set_editor_property("enabled", True)
        if foliage:
            ns.set_editor_property("shape_preservation", PRESERVE_AREA)
        if DRY:
            changed += 1
            continue
        mesh.set_editor_property("nanite_settings", ns)
        unreal.EditorAssetLibrary.save_loaded_asset(mesh, only_if_is_dirty=False)
        changed += 1
    say("%s: %d meshes, %d triangles at full detail" % (folder, len(meshes), tris_before))
say("%s %d meshes, %d already had it" % ("would turn Nanite on for" if DRY else "turned Nanite on for",
                                         changed, already))
