"""label_segmentation.py - write the segmentation classes into the corridor level's components.

Run it in the open editor with the corridor level loaded: the Output Log's command box, switched
from Cmd to Python, then

    exec(open(r"<project folder>/Plugins/MAirCorridor/Tools/unreal/label_segmentation.py").read())

The classes are Tools/segmentation.json: ground, building, tree, rock, scan, and the drone, which
the flight tools label when a scene loads. A component is classed by the folder its mesh comes
from, and gets Render CustomDepth on with that class's id as its stencil value, which is what
Project AirSim's segmentation camera reads.

WHY IN THE LEVEL. Project AirSim's own pass makes an id by adding up the letters of each mesh
owner's name, overwrites whatever the level holds, and reaches only what is loaded when the scene
starts. Every square kilometre of foliage would be a different arbitrary class, and anything World
Partition streams in afterwards would have none. Written here, an id streams in with its
component. The scene configs set "initialize-ids": false so Project AirSim leaves them alone.

It works through the level in batches: actors not already loaded are loaded, labelled, saved and
unloaded again; actors you had loaded are labelled and saved and left loaded. Only the actors it
changes are saved. MAIR_DRY=1 labels in memory and saves nothing.
"""
import io
import json
import os

import unreal

MARK = "MAIRSEG"
DRY = os.environ.get("MAIR_DRY") == "1"
LEVEL = "/MAirCorridor/Scene/CorridorTerrain"
# Found through the project rather than __file__, which exec() in the editor does not set.
TOOLS = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_plugins_dir()),
                     "MAirCorridor", "Tools")
TABLE = os.environ.get("MAIR_SEGMENTATION", os.path.join(TOOLS, "segmentation.json"))
BATCH = 40


def say(text):
    unreal.log_warning("%s %s" % (MARK, text))
    print("%s %s" % (MARK, text))


with io.open(TABLE, encoding="utf-8") as f:
    classes = json.load(f)["classes"]
by_path = [(p, name, c["id"]) for name, c in classes.items() for p in c.get("mesh_paths", [])]
ground_id = next(c["id"] for c in classes.values() if c.get("landscape"))


def class_of(mesh):
    path = mesh.get_path_name() if mesh else ""
    for prefix, name, cid in by_path:
        if path.startswith(prefix):
            return name, cid
    return None, None


def label(obj, cid):
    """Render CustomDepth on with this stencil value; True when anything changed."""
    changed = False
    if not obj.get_editor_property("render_custom_depth"):
        obj.set_editor_property("render_custom_depth", True)
        changed = True
    if obj.get_editor_property("custom_depth_stencil_value") != cid:
        obj.set_editor_property("custom_depth_stencil_value", cid)
        changed = True
    return changed


if DRY:
    unreal.EditorLoadingAndSavingUtils.load_map(LEVEL)
actors_sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
big = unreal.Box(unreal.Vector(-1e9, -1e9, -1e9), unreal.Vector(1e9, 1e9, 1e9))
descs = unreal.WorldPartitionBlueprintLibrary.get_intersecting_actor_descs(big)
descs = descs[-1] if isinstance(descs, tuple) else descs
guids = [d.get_editor_property("guid") for d in descs]
say("%s: %d actors to look at, in batches of %d" % (LEVEL, len(guids), BATCH))

counts = {}
unclassed = {}
saved = 0


def guid_key(guid):
    # str() of an unreal.Guid includes its memory address, so two equal ids never compare equal.
    return unreal.GuidLibrary.conv_guid_to_string(guid)


def loaded_by_guid():
    return {guid_key(a.get_editor_property("actor_guid")): a for a in actors_sub.get_all_level_actors()}


done = set()
for start in range(0, len(guids), BATCH):
    batch = guids[start:start + BATCH]
    before = loaded_by_guid()
    ours = [g for g in batch if guid_key(g) not in before]
    if ours:
        unreal.WorldPartitionBlueprintLibrary.load_actors(ours)
    now = loaded_by_guid()
    changed_packages = []
    for g in batch:
        actor = now.get(guid_key(g))
        if actor is None or guid_key(g) in done:
            continue
        done.add(guid_key(g))
        changed = False
        if isinstance(actor, unreal.LandscapeProxy):
            changed |= label(actor, ground_id)
            counts["ground"] = counts.get("ground", 0) + 1
        for comp in actor.get_components_by_class(unreal.StaticMeshComponent):
            name, cid = class_of(comp.get_editor_property("static_mesh"))
            if name is None:
                mesh = comp.get_editor_property("static_mesh")
                key = mesh.get_path_name() if mesh else "(no mesh)"
                unclassed[key] = unclassed.get(key, 0) + 1
                continue
            changed |= label(comp, cid)
            counts[name] = counts.get(name, 0) + 1
        if changed:
            changed_packages.append(actor.get_outermost())
    if changed_packages and not DRY:
        unreal.EditorLoadingAndSavingUtils.save_packages(changed_packages, True)
        saved += len(changed_packages)
    if ours:
        unreal.WorldPartitionBlueprintLibrary.unload_actors(ours)
    say("  %d of %d actors" % (min(start + BATCH, len(guids)), len(guids)))

# The landscape actor itself is always loaded and carries the settings its proxies share.
for actor in actors_sub.get_all_level_actors():
    if isinstance(actor, unreal.Landscape) and guid_key(actor.get_editor_property("actor_guid")) not in done:
        if label(actor, ground_id) and not DRY:
            unreal.EditorLoadingAndSavingUtils.save_packages([actor.get_outermost()], True)
            saved += 1

say("labelled: %s" % ", ".join("%s %d" % kv for kv in sorted(counts.items())))
if unclassed:
    top = sorted(unclassed.items(), key=lambda kv: -kv[1])[:8]
    say("left unlabelled (no class for their folder): %s" % ", ".join("%s x%d" % kv for kv in top))
say("%s %d actor packages" % ("dry run, would have saved" if DRY else "saved", saved))
