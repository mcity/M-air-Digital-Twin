"""mcity_clear_level.py - the corridor's own buildings and trees under M-City: list them, then clear them.

In the open editor (Output Log, Python), or on its own, with the editor closed, off screen:

    UnrealEditor.exe <project>.uproject -ExecutePythonScript="<absolute path>/Tools/unreal/mcity_clear_level.py"
        -RenderOffScreen -nosplash -unattended          and set MAIR_QUIT=1 so it closes when done

MAIR_STEP=survey (the default) opens the corridor level, loads everything around M-City, and writes
Saved/MAirCorridor/mcity_corridor_items.json: every building (an actor tagged "building") as the four
ground corners of its box, and every foliage instance (the Foliage_* actors) as its position. It
changes nothing. Tools/mcity_clear.py then decides what is under the scan, the twin or both.

MAIR_STEP=apply carries out that decision (Saved/MAirCorridor/mcity_clear_plan.json) and saves:

  under both       deleted: whichever M-City is shown covers it.
  under the scan   tagged MAirUnderScan, hidden while the scan is shown (MAirMcityViewSubsystem).
  under the twin   tagged MAirUnderTwin, hidden while the twin is shown.

A tree to hide in one view only is moved out of its square kilometre's actor into one beside it
(Foliage_<cell>_UnderScan or _UnderTwin) with the same settings, since a tag hides an actor, not an
instance. Everything changed is written to Tools/mcity_cleared.json first: each deleted building's
mesh, materials, transform and folder, and each deleted tree's mesh and transform, so it can all be
put back. MAIR_DRY=1 checks everything against the level and builds the new foliage actors, then
stops: nothing is deleted, tagged, removed, saved or recorded.

A tree is only touched if it is still where the survey found it, to the centimetre: a level changed
since the survey is skipped where it differs, and the count says so.
"""
import io
import json
import os
import shutil
import time

import unreal

MARK = "MAIRCLEAR"
LEVEL = "/MAirCorridor/Scene/CorridorTerrain"
STEP = os.environ.get("MAIR_STEP", "survey")
PROJECT = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())
TOOLS = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_plugins_dir()),
                     "MAirCorridor", "Tools")
SAVED = os.path.join(PROJECT, "Saved", "MAirCorridor")
ITEMS = os.path.join(SAVED, "mcity_corridor_items.json")
PLAN = os.path.join(SAVED, "mcity_clear_plan.json")
RECORD = os.path.join(TOOLS, "mcity_cleared.json")
# Around M-City, in level centimetres: the scan's extent (900,100 to 1,067,000 by 1,014,000 to
# 1,177,200) with the twin inside it, and 200 m to spare.
REGION = unreal.Box(unreal.Vector(880000.0, 994000.0, -1e7), unreal.Vector(1087000.0, 1197200.0, 1e7))
TAG_SCAN, TAG_TWIN = "MAirUnderScan", "MAirUnderTwin"
DRY = os.environ.get("MAIR_DRY") == "1"
COPIED = ("collision_profile_name", "cast_shadow", "instance_start_cull_distance",
          "instance_end_cull_distance", "mobility", "render_custom_depth", "custom_depth_stencil_value")


def say(text):
    unreal.log_warning("%s %s" % (MARK, text))


def ground_corners(comp):
    """The four ground corners, X and Y in level cm, of a component's box as it sits in the level."""
    lo, hi = comp.get_local_bounds()
    xf = comp.get_world_transform()
    out = []
    for x, y in ((lo.x, lo.y), (hi.x, lo.y), (hi.x, hi.y), (lo.x, hi.y)):
        w = xf.transform_location(unreal.Vector(x, y, lo.z))
        out.append([round(w.x, 1), round(w.y, 1)])
    return out


def load_region():
    unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).load_level(LEVEL)
    found = unreal.WorldPartitionBlueprintLibrary.get_intersecting_actor_descs(REGION)
    descs = found[-1] if isinstance(found, tuple) else found
    guids = [d.get_editor_property("guid") for d in descs]
    started = time.time()
    unreal.WorldPartitionBlueprintLibrary.load_actors(guids)
    say("loaded %d actors around M-City in %.0f s" % (len(guids), time.time() - started))
    return unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()


def foliage_actors(actors):
    return [a for a in actors if a.get_actor_label().startswith("Foliage_")]


def survey():
    actors = load_region()
    classes = {}
    for a in actors:
        classes[a.get_class().get_name()] = classes.get(a.get_class().get_name(), 0) + 1
    say("by class: %s" % sorted(classes.items(), key=lambda kv: -kv[1])[:15])

    buildings = []
    for a in actors:
        if "building" not in [str(t) for t in a.tags]:
            continue
        comp = a.get_component_by_class(unreal.StaticMeshComponent)
        if comp is None or comp.static_mesh is None:
            continue
        buildings.append({"label": a.get_actor_label(), "path": a.get_path_name(),
                          "folder": str(a.get_folder_path()), "tags": [str(t) for t in a.tags],
                          "corners": ground_corners(comp)})

    trees = []
    for a in foliage_actors(actors):
        for comp in a.get_components_by_class(unreal.InstancedStaticMeshComponent):
            mesh = comp.static_mesh
            for i in range(comp.get_instance_count()):
                p = comp.get_instance_transform(i, True).translation
                if REGION.min.x <= p.x <= REGION.max.x and REGION.min.y <= p.y <= REGION.max.y:
                    trees.append({"actor": a.get_actor_label(), "component": comp.get_name(), "index": i,
                                  "mesh": mesh.get_path_name() if mesh else None,
                                  "x": round(p.x, 1), "y": round(p.y, 1), "z": round(p.z, 1)})
    os.makedirs(SAVED, exist_ok=True)
    with io.open(ITEMS, "w", encoding="utf-8") as f:
        json.dump({"frame": "level cm", "region": [REGION.min.x, REGION.min.y, REGION.max.x, REGION.max.y],
                   "buildings": buildings, "trees": trees}, f)
    say("wrote %s: %d buildings, %d foliage instances from %d foliage actors"
        % (ITEMS, len(buildings), len(trees), len(foliage_actors(actors))))
    for tag in (TAG_SCAN, TAG_TWIN):
        say("tagged %s: %d buildings, %d foliage actors holding %d instances" % (
            tag, sum(1 for b in buildings if tag in b["tags"]),
            sum(1 for a in foliage_actors(actors) if tag in [str(t) for t in a.tags]),
            sum(1 for t in trees if t["actor"].endswith("_UnderScan" if tag == TAG_SCAN else "_UnderTwin"))))


def transform_list(t):
    r = t.rotation.rotator()
    return [round(v, 3) for v in (t.translation.x, t.translation.y, t.translation.z,
                                  r.pitch, r.yaw, r.roll, t.scale3d.x, t.scale3d.y, t.scale3d.z)]


subobjects = unreal.get_engine_subsystem(unreal.SubobjectDataSubsystem)
library = unreal.SubobjectDataBlueprintFunctionLibrary


def add_hism(actor):
    """A component the way the Details panel's Add button makes one, so it is saved with the level
    (as Tools/unreal/stream_foliage.py does)."""
    handles = subobjects.k2_gather_subobject_data_for_instance(actor)
    params = unreal.AddNewSubobjectParams(parent_handle=handles[0],
                                          new_class=unreal.HierarchicalInstancedStaticMeshComponent)
    handle, failure = subobjects.add_new_subobject(params)
    if not library.is_handle_valid(handle):
        raise RuntimeError("could not add a component: %s" % failure)
    return library.get_object(library.get_data(handle))


def companion(source, tag, level_actors):
    """The actor beside a square kilometre's foliage actor that holds its trees under one M-City."""
    c = level_actors.spawn_actor_from_class(unreal.Actor, source.get_actor_location(), unreal.Rotator())
    c.set_actor_label("%s_%s" % (source.get_actor_label(), "UnderScan" if tag == TAG_SCAN else "UnderTwin"))
    c.set_folder_path(source.get_folder_path())
    c.tags = [tag]
    for prop in ("hlod_layer", "is_spatially_loaded"):
        try:
            c.set_editor_property(prop, source.get_editor_property(prop))
        except Exception:
            pass
    return c


def hisms(actor):
    return actor.get_components_by_class(unreal.InstancedStaticMeshComponent)


def instance_key(comp, index):
    """A tree by what it is and where, to the centimetre, whichever actor holds it."""
    p = comp.get_instance_transform(index, True).translation
    return (comp.static_mesh.get_path_name() if comp.static_mesh else "", round(p.x), round(p.y), round(p.z))


def like(comp, actor):
    """A new instanced component on actor, set up as comp is."""
    h = add_hism(actor)
    h.set_static_mesh(comp.static_mesh)
    for prop in COPIED:
        try:
            h.set_editor_property(prop, comp.get_editor_property(prop))
        except Exception:
            pass
    for slot in range(comp.get_num_materials()):
        h.set_material(slot, comp.get_material(slot))
    return h


def backup(actors):
    """Copy each actor's own file (World Partition keeps one per actor) as it is now, under
    Saved/MAirCorridor/mcity_clear_backup/<time>/, at its path in the plugin. Copying them back, with
    the editor closed, undoes the change to those actors."""
    content = os.path.join(os.path.dirname(TOOLS), "Content")
    folder = os.path.join(SAVED, "mcity_clear_backup", time.strftime("%Y%m%d_%H%M%S"))
    copied = 0
    for package in sorted({a.get_package().get_name() for a in actors}):   # /MAirCorridor/__ExternalActors__/...
        if not package.startswith("/MAirCorridor/"):
            continue
        rel = package[len("/MAirCorridor/"):] + ".uasset"
        src = os.path.join(content, rel)
        if os.path.isfile(src):
            dst = os.path.join(folder, rel)
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copy2(src, dst)
            copied += 1
    return copied, folder


def apply():
    with io.open(PLAN, encoding="utf-8") as f:
        plan = json.load(f)
    actors = load_region()
    level_actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    by_path = {a.get_path_name(): a for a in actors}
    foliage = {a.get_actor_label(): a for a in foliage_actors(actors)}
    record = {"level": LEVEL, "when": time.strftime("%Y-%m-%d %H:%M:%S"), "summary": plan["summary"],
              "deleted_buildings": [], "tagged_buildings": [], "deleted_trees": [], "moved_trees": {}}

    # ---- buildings ----------------------------------------------------------------------------
    deleting, tagging, missing = [], [], 0
    for b in plan["buildings"]:
        a = by_path.get(b["path"])
        if a is None:
            missing += 1
        elif b["action"] == "both":
            deleting.append(a)
        else:
            tagging.append((a, TAG_SCAN if b["action"] == "scan" else TAG_TWIN))
    for a in deleting:
        comp = a.get_component_by_class(unreal.StaticMeshComponent)
        record["deleted_buildings"].append({
            "label": a.get_actor_label(), "folder": str(a.get_folder_path()),
            "mesh": comp.static_mesh.get_path_name(),
            "materials": [m.get_path_name() if m else None
                          for m in (comp.get_material(i) for i in range(comp.get_num_materials()))],
            "transform": transform_list(a.get_actor_transform()), "tags": [str(t) for t in a.tags]})
    for a, tag in tagging:
        record["tagged_buildings"].append({"label": a.get_actor_label(), "path": a.get_path_name(), "tag": tag})

    # ---- trees: checked against the survey, then deleted, or moved beside --------------------------
    # Safe to run again: a tree already in the actor beside is left there, and one whose copy is
    # already there is only taken out of the original.
    suffix = {TAG_SCAN: "_UnderScan", TAG_TWIN: "_UnderTwin"}
    companions, held = {}, {}
    for name, a in foliage.items():
        for tag, end in suffix.items():
            if name.endswith(end):
                companions[(name[:-len(end)], tag)] = a
                held[a.get_actor_label()] = {instance_key(c, i) for c in hisms(a) for i in range(c.get_instance_count())}
    groups = {}
    for t in plan["trees"]:
        groups.setdefault((t["actor"], t["component"]), []).append(t)
    moving, removals, stale, in_place, copied = {}, [], 0, 0, 0
    for (label, comp_name), rows in sorted(groups.items()):
        if label.endswith(tuple(suffix.values())):
            in_place += len(rows)
            continue
        source = foliage.get(label)
        comps = [c for c in hisms(source) if c.get_name() == comp_name] if source else []
        if not comps:
            stale += len(rows)
            continue
        comp, doomed = comps[0], []
        for r in rows:
            xf = comp.get_instance_transform(r["index"], True)
            if abs(xf.translation.x - r["x"]) > 1.0 or abs(xf.translation.y - r["y"]) > 1.0:
                stale += 1
                continue
            doomed.append(r["index"])
            if r["action"] == "both":
                record["deleted_trees"].append({"from": label, "mesh": r["mesh"], "transform": transform_list(xf)})
                continue
            tag = TAG_SCAN if r["action"] == "scan" else TAG_TWIN
            if (label, tag) not in companions:
                companions[(label, tag)] = companion(source, tag, level_actors)
                held[companions[(label, tag)].get_actor_label()] = set()
            beside = companions[(label, tag)]
            if instance_key(comp, r["index"]) in held[beside.get_actor_label()]:
                copied += 1
                continue
            target = (label, tag, comp_name)
            if target not in moving:
                same = [c for c in hisms(beside) if c.static_mesh == comp.static_mesh]
                moving[target] = (same[0] if same else like(comp, beside), [])
            moving[target][1].append(xf)
        removals.append((source, comp, doomed))

    for (label, tag, _comp_name), (h, transforms) in moving.items():
        name = companions[(label, tag)].get_actor_label()
        record["moved_trees"][name] = record["moved_trees"].get(name, 0) + len(transforms)

    say("buildings: %d to delete, %d to tag, %d not found; trees: %d to delete, %d to move into %d actors "
        "(%d more already there, %d already moved), %d not where the survey found them" % (
            len(deleting), len(tagging), missing, len(record["deleted_trees"]),
            sum(record["moved_trees"].values()), len(companions), copied, in_place, stale))
    if DRY:
        say("dry run: the new foliage actors were built; nothing deleted, tagged, removed, saved or recorded")
        return

    history = {"runs": []}
    if os.path.isfile(RECORD):
        with io.open(RECORD, encoding="utf-8") as f:
            history = json.load(f)
    history["runs"].append(record)
    with io.open(RECORD, "w", encoding="utf-8", newline="\n") as f:
        json.dump(history, f, indent=1)
        f.write("\n")
    say("recorded in %s" % RECORD)
    changed = ([a for a, _ in tagging] + [s for s, _, d in removals if d]
               + [companions[(label, tag)] for label, tag, _ in moving])
    say("backed up %d actor files to %s" % backup(changed + deleting))

    # Each actor is marked as changing before it does: Python's edits to tags and instances do not
    # do it themselves, and an actor not marked is not saved (the first run here lost them so).
    for (label, tag, _comp_name), (h, transforms) in moving.items():
        companions[(label, tag)].modify()
        h.modify()
        h.add_instances(transforms, False, True)
    for source, comp, doomed in removals:
        if doomed:
            source.modify()
            comp.modify()
            comp.remove_instances(sorted(doomed))
    for a, tag in tagging:
        if tag not in [str(t) for t in a.tags]:
            a.modify()
            a.set_editor_property("tags", list(a.tags) + [tag])
    for a in deleting:
        level_actors.destroy_actor(a)
    packages = list({a.get_package().get_name(): a.get_package() for a in set(changed)}.values())
    saved = unreal.EditorLoadingAndSavingUtils.save_packages(packages, False)
    saved_rest = unreal.EditorLoadingAndSavingUtils.save_dirty_packages(True, True)
    say("applied: %d actor files saved (%s), then the rest (%s)" % (len(packages), saved, saved_rest))


if STEP == "survey":
    survey()
elif STEP == "apply":
    apply()
else:
    say("unknown MAIR_STEP %s" % STEP)

if os.environ.get("MAIR_QUIT") == "1":
    unreal.SystemLibrary.quit_editor()
