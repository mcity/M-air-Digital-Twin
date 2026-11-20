"""stream_foliage.py - split the corridor's single foliage actor into actors World Partition can stream.

Run it in the open editor with the corridor level loaded: the Output Log's command box, switched
from Cmd to Python, then

    exec(open(r"<project folder>/Plugins/MAirCorridor/Tools/unreal/stream_foliage.py").read())

WHY. The foliage placer put every tree and rock in the corridor into ONE actor, CorridorFoliage,
whose bounds are the whole corridor: 65.8 by 21.4 km, 677,244 instances. World Partition streams
whole actors and files each into the grid level whose cells contain it, so an actor that size is
loaded whenever anything is, and every tree in the corridor is always resident. Split into one
actor per square kilometre, each lands in a cell of its own size and loads only when the viewer
comes within the grid's loading range of it.

WHAT YOU SEE AFTERWARDS. Trees load within the loading range of the camera: this level's grid
loads 252 m cells within 768 m, and a 1 km actor sits in a 1,008 m cell, so a square kilometre of
trees loads when the camera comes within 768 m of it. Past that, World Partition draws HLOD
proxies, which need the trees to have an HLOD layer (Tools/unreal/corridor_streaming.py gives them
HLOD_Trees) and a build. Until then, distant ground has no trees on it.

The new actors copy each instanced component's settings (collision, shadows, cull distances) from
the original, and the original is removed. The level is NOT saved: look, then save it to keep it,
or close it without saving to put the single actor back.

MAIR_DRY=1 reads and counts everything and changes nothing.
"""
import os
import time

import unreal

MARK = "MAIRFOLIAGE"
DRY = os.environ.get("MAIR_DRY") == "1"
LEVEL = "/MAirCorridor/Scene/CorridorTerrain"
SOURCE_LABEL = "CorridorFoliage"
CELL_CM = 100000.0          # one square kilometre
FOLDER = "Foliage"
COPIED = ("collision_profile_name", "cast_shadow", "instance_start_cull_distance",
          "instance_end_cull_distance", "mobility")


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


actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
if DRY:
    unreal.EditorLoadingAndSavingUtils.load_map(LEVEL)
    big = unreal.Box(unreal.Vector(-1e9, -1e9, -1e9), unreal.Vector(1e9, 1e9, 1e9))
    descs = unreal.WorldPartitionBlueprintLibrary.get_intersecting_actor_descs(big)
    descs = descs[-1] if isinstance(descs, tuple) else descs
    unreal.WorldPartitionBlueprintLibrary.load_actors(
        [d.get_editor_property("guid") for d in descs
         if str(d.get_editor_property("label")) == SOURCE_LABEL])

source = [a for a in actors.get_all_level_actors() if a.get_actor_label() == SOURCE_LABEL]
if not source:
    raise RuntimeError("no actor labelled %s is loaded in this level" % SOURCE_LABEL)
source = source[0]
hlod_layer = None
try:
    hlod_layer = source.get_editor_property("hlod_layer")
except Exception:
    pass

# ---- read every instance, bucketed by square kilometre ---------------------------------------
started = time.time()
cells = {}              # (cx, cy) -> {component index: [transforms]}
templates = []
for comp in source.get_components_by_class(unreal.InstancedStaticMeshComponent):
    index = len(templates)
    templates.append(comp)
    for i in range(comp.get_instance_count()):
        xf = comp.get_instance_transform(i, True)
        loc = xf.translation
        key = (int(loc.x // CELL_CM), int(loc.y // CELL_CM))
        cells.setdefault(key, {}).setdefault(index, []).append(xf)
total = sum(len(v) for c in cells.values() for v in c.values())
say("read %d instances from %d meshes in %.0f s: %d square kilometres hold foliage" % (
    total, len(templates), time.time() - started, len(cells)))
busiest = max(cells.items(), key=lambda kv: sum(len(v) for v in kv[1].values()))
say("busiest kilometre %s holds %d instances" % (
    busiest[0], sum(len(v) for v in busiest[1].values())))
# ---- one actor per square kilometre ----------------------------------------------------------
subobjects = unreal.get_engine_subsystem(unreal.SubobjectDataSubsystem)
library = unreal.SubobjectDataBlueprintFunctionLibrary


def add_hism(actor):
    """A component the way the Details panel's Add button makes one, so it is saved with the level.
    (AddComponentByClass makes construction-script components, which the editor does not save.)"""
    handles = subobjects.k2_gather_subobject_data_for_instance(actor)
    params = unreal.AddNewSubobjectParams(parent_handle=handles[0],
                                          new_class=unreal.HierarchicalInstancedStaticMeshComponent)
    handle, failure = subobjects.add_new_subobject(params)
    if not library.is_handle_valid(handle):
        raise RuntimeError("could not add a component: %s" % failure)
    return library.get_object(library.get_data(handle))


def build(key, by_mesh):
    cx, cy = key
    centre = unreal.Vector((cx + 0.5) * CELL_CM, (cy + 0.5) * CELL_CM, 0.0)
    actor = actors.spawn_actor_from_class(unreal.Actor, centre, unreal.Rotator())
    actor.set_actor_label("Foliage_%+04d_%+04d" % (cx, cy))
    actor.set_folder_path(FOLDER)
    placed = 0
    for index, transforms in by_mesh.items():
        template = templates[index]
        comp = add_hism(actor)
        comp.set_static_mesh(template.get_editor_property("static_mesh"))
        for prop in COPIED:
            try:
                comp.set_editor_property(prop, template.get_editor_property(prop))
            except Exception:
                pass
        for slot in range(template.get_num_materials()):
            comp.set_material(slot, template.get_material(slot))
        label_segmentation(comp)
        comp.add_instances(transforms, False, True)
        placed += comp.get_instance_count()
    if hlod_layer is not None:
        actor.set_editor_property("hlod_layer", hlod_layer)
    actor.set_editor_property("is_spatially_loaded", True)
    return actor, placed


if DRY:
    # Build the busiest kilometre for real, to prove the components and instances take, and stop.
    actor, placed = build(busiest[0], busiest[1])
    want = sum(len(v) for v in busiest[1].values())
    say("dry run built %s with %d of %d instances in %d components; nothing saved" % (
        actor.get_actor_label(), placed, want,
        len(actor.get_components_by_class(unreal.HierarchicalInstancedStaticMeshComponent))))
    raise SystemExit

started = time.time()
made = placed_total = 0
for key, by_mesh in sorted(cells.items()):
    _actor, placed = build(key, by_mesh)
    made += 1
    placed_total += placed
    if made % 50 == 0:
        say("  %d of %d actors, %.0f s" % (made, len(cells), time.time() - started))
if placed_total != total:
    raise RuntimeError("placed %d instances but read %d; the original is kept" % (placed_total, total))
say("made %d foliage actors holding all %d instances in %.0f s" % (made, placed_total,
                                                                   time.time() - started))

actors.destroy_actor(source)
say("removed %s. The level is NOT saved: look, then save it to keep this, or close it without "
    "saving to undo. Then Build > Build HLODs so distant ground has trees." % SOURCE_LABEL)
