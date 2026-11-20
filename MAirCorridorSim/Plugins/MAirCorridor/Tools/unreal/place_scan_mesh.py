"""place_scan_mesh.py - the M-City scan as one Nanite static mesh, in place of the streamed tiles.

Run it in the open editor with the corridor level loaded: the Output Log's command box, switched
from Cmd to Python, then

    exec(open(r"<project folder>/Plugins/MAirCorridor/Tools/unreal/place_scan_mesh.py").read())

WHY. The streamed scan (the M-City Scan actor) is unusable in real time. It decodes photographs
and builds mesh sections on the game thread as the viewer moves, so the scan draws in slowly, and
its coarser levels of detail were made by merging vertices without regard to where the
photographs' pieces meet: measured on one tile, 52 to 71 percent of their triangles stretch across
unrelated parts of a photograph, which is the smeared patchwork seen at a distance. The same scan
imported whole (Content/Scan/20M16, 20 million triangles, its 16 photographs mapped properly) with
Nanite has neither problem: Nanite simplifies without tearing the texture mapping, streams with no
runtime decoding, and costs every camera capture far less.

WHERE IT GOES. The import sits in the scan's own frame: the OBJ's metres read as centimetres, true
north, ellipsoidal heights. Its transform onto the level was measured, not assumed: the tiles carry
the OBJ's per-vertex colours, so vertices whose colour is unique in both were paired and fitted.
OBJ to tiles is an affine with a worst error of 1 mm over 1545 pairs; composed with the scan
component's placement onto the landscape it comes out as a rotation of 1.81391 degrees (the UTM
grid convergence here) and a scale of 100.02, which an actor transform holds to within 3.5 cm of
where the streamed scan puts the same points. The height follows the streamed scan's own Align Z
Offset Cm, read from it before it is removed, so the two agree.

WHAT IT DOES, all of it undone by not saving the level:
  - 16 photo materials, children of M_MCityScan, one per photograph, in Materials/ScanPhotos;
  - complex collision on 20M16, so the drone lands on the scan and the range sensors see it;
  - a static mesh actor, "M-City Scan (Nanite)", always loaded, with those materials;
  - the streamed scan actor removed, its settings written to the log first;
  - the placement checked against five points whose positions are known exactly.
The materials and the mesh's collision are saved; the level is NOT. Look, then save the level to
keep it, or close it without saving to put everything in the level back.

MAIRSCAN_DRY=1 runs it headless against the level without saving or changing any asset.
"""
import os

import unreal

MARK = "MAIRSCAN"
DRY = os.environ.get("MAIRSCAN_DRY") == "1"
LEVEL = "/MAirCorridor/Scene/CorridorTerrain"
MESH = "/MAirCorridor/Scan/20M16"
PHOTO_MATERIAL = "/MAirCorridor/Materials/M_MCityScan"
PHOTO_FOLDER = "/MAirCorridor/Materials/ScanPhotos"
LABEL = "M-City Scan (Nanite)"

# The fitted transform, for the streamed scan's Align Z Offset Cm of -6350 (BASE_DZ). A different
# offset moves the mesh by the difference.
ROTATION = (-0.0010566622, 1.8139125545, -0.0012466783)            # pitch, yaw, roll
SCALE = (100.0210334729, 100.0202904829, 100.0000048736)
LOCATION = (1004921.4576, 1067630.2254, -19376.9569)
BASE_DZ = -6350.0
# Mesh-local points and where the scan puts them in the level, from the fit.
CHECKS = [((-974.8, -490.7, 215.2), (909023.258, 1015488.199, 2144.379)),
          ((571.3, 1061.5, 305.6), (1058674.624, 1175557.428, 11185.372))]

mel = unreal.MaterialEditingLibrary
tools = unreal.AssetToolsHelpers.get_asset_tools()
actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)


def say(text):
    unreal.log_warning("%s %s" % (MARK, text))
    print("%s %s" % (MARK, text))


# ---- segmentation: label what is made, so a re-run keeps the level's classes (label_segmentation.py)
def _segmentation_classes():
    tools = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_plugins_dir()),
                         "MAirCorridor", "Tools")
    try:
        import io as _io, json as _json
        with _io.open(os.path.join(tools, "segmentation.json"), encoding="utf-8") as f:
            classes = _json.load(f)["classes"]
    except Exception:
        return []
    return [(p, c["id"]) for c in classes.values() for p in c.get("mesh_paths", [])]


SEGMENTATION = _segmentation_classes()


def label_segmentation(comp):
    mesh = comp.get_editor_property("static_mesh")
    path = mesh.get_path_name() if mesh else ""
    for prefix, cid in SEGMENTATION:
        if path.startswith(prefix):
            comp.set_editor_property("render_custom_depth", True)
            comp.set_editor_property("custom_depth_stencil_value", cid)
            return cid
    return None


if DRY:
    unreal.EditorLoadingAndSavingUtils.load_map(LEVEL)

# ---- the mesh -------------------------------------------------------------------------------
mesh = unreal.load_asset(MESH)
if mesh is None:
    raise RuntimeError("%s is not in the project" % MESH)
nanite = mesh.get_editor_property("nanite_settings")
if not nanite.get_editor_property("enabled"):
    raise RuntimeError("%s does not have Nanite on; turn it on in the mesh editor first" % MESH)
body = mesh.get_editor_property("body_setup")
flag = body.get_editor_property("collision_trace_flag") if body else None
say("%s: Nanite on, %d material slots, collision %s" % (
    MESH, len(mesh.get_editor_property("static_materials")), flag))
if body and flag != unreal.CollisionTraceFlag.CTF_USE_COMPLEX_AS_SIMPLE and not DRY:
    body.set_editor_property("collision_trace_flag", unreal.CollisionTraceFlag.CTF_USE_COMPLEX_AS_SIMPLE)
    mesh.modify()
    unreal.EditorAssetLibrary.save_loaded_asset(mesh, only_if_is_dirty=False)
    say("%s: complex collision on, saved" % MESH)

# ---- one photo material per slot ------------------------------------------------------------
parent = unreal.load_asset(PHOTO_MATERIAL)
if parent is None:
    raise RuntimeError("%s is missing; run build_scan_materials.py first" % PHOTO_MATERIAL)
materials = []
for slot in mesh.get_editor_property("static_materials"):
    name = str(slot.get_editor_property("material_slot_name"))
    texture = unreal.load_asset("/MAirCorridor/Scan/TEX_%s" % name)
    if texture is None:
        raise RuntimeError("no photograph TEX_%s for slot %s" % (name, name))
    path = "%s/MI_MCityScan_%s" % (PHOTO_FOLDER, name)
    mi = None if DRY else unreal.load_asset(path)
    if mi is None:
        if DRY:
            mi = unreal.new_object(unreal.MaterialInstanceConstant, name="MI_MCityScan_%s" % name)
        else:
            mi = tools.create_asset("MI_MCityScan_%s" % name, PHOTO_FOLDER,
                                    unreal.MaterialInstanceConstant,
                                    unreal.MaterialInstanceConstantFactoryNew())
    mel.set_material_instance_parent(mi, parent)
    # Checked by reading it back: the setter's return value is False even when it worked.
    mel.set_material_instance_texture_parameter_value(mi, "BaseColor", texture)
    if mel.get_material_instance_texture_parameter_value(mi, "BaseColor") != texture:
        raise RuntimeError("could not set BaseColor on %s" % mi.get_name())
    if not DRY:
        unreal.EditorAssetLibrary.save_loaded_asset(mi, only_if_is_dirty=False)
    materials.append(mi)
say("%d photo materials ready in %s" % (len(materials), PHOTO_FOLDER))

# ---- the streamed scan: read its height, then take it out -----------------------------------
dz = BASE_DZ
for actor in actors.get_all_level_actors():
    if actor.get_class().get_name() != "MAirScanActor":
        continue
    for comp in actor.get_components_by_class(unreal.SceneComponent):
        if comp.get_class().get_name() == "MAirScanMeshComponent":
            dz = float(comp.get_editor_property("align_z_offset_cm"))
            settings = {p: comp.get_editor_property(p) for p in (
                "tiles_directory", "align_z_offset_cm", "align_row_x", "align_row_y",
                "load_radius_m", "lod_distances_m", "max_texture_size_px")}
            settings = {k: ([v.x, v.y, v.z] if isinstance(v, unreal.Vector) else
                            list(v) if isinstance(v, unreal.Array) else v)
                        for k, v in settings.items()}
            say("streamed scan %s settings, for putting it back: %s" % (actor.get_actor_label(), settings))
    label = actor.get_actor_label()
    actors.destroy_actor(actor)
    say("removed the streamed scan actor %s" % label)

# ---- the Nanite scan ------------------------------------------------------------------------
location = unreal.Vector(LOCATION[0], LOCATION[1], LOCATION[2] + (dz - BASE_DZ))
rotation = unreal.Rotator(roll=ROTATION[2], pitch=ROTATION[0], yaw=ROTATION[1])
placed = [a for a in actors.get_all_level_actors() if a.get_actor_label() == LABEL]
actor = placed[0] if placed else actors.spawn_actor_from_class(unreal.StaticMeshActor, location, rotation)
actor.set_actor_label(LABEL)
actor.set_actor_location(location, False, False)
actor.set_actor_rotation(rotation, False)
actor.set_actor_scale3d(unreal.Vector(*SCALE))
try:
    # 1.6 km across: as one World Partition cell it would load only when the viewer stood in it.
    actor.set_editor_property("is_spatially_loaded", False)
except Exception as e:
    say("could not make it always loaded (%s); set Is Spatially Loaded off by hand" % e)
comp = actor.get_editor_property("static_mesh_component")
comp.set_static_mesh(mesh)
comp.set_mobility(unreal.ComponentMobility.STATIC)
comp.set_collision_profile_name("BlockAll")
for i, mi in enumerate(materials):
    comp.set_material(i, mi)
label_segmentation(comp)
say("placed %s at %s rotation %s scale %s (Align Z Offset Cm %.2f)" % (
    LABEL, location, rotation, SCALE, dz))

# ---- the check --------------------------------------------------------------------------------
xf = actor.get_actor_transform()
worst = 0.0
for local, world in CHECKS:
    got = xf.transform_location(unreal.Vector(*local))
    want = unreal.Vector(world[0], world[1], world[2] + (dz - BASE_DZ))
    worst = max(worst, (got - want).length() / 100.0)
say("placement checked: worst %.3f m from where the scan puts the same points%s" % (
    worst, "" if worst < 0.1 else "  <-- TOO FAR, do not keep this"))
say("done. The level is NOT saved: look at the scan, then save the level to keep it, "
    "or close it without saving to undo." if not DRY else "dry run done, nothing saved")
