"""split_buildings.py - split the 100 merged building tiles into one actor per building, on the ground.

Headless, with the editor CLOSED (it edits the corridor level and saves as it goes):

    UnrealEditor-Cmd.exe <project>.uproject -run=pythonscript
        -script=<absolute path>/Tools/unreal/split_buildings.py
        "-EnablePlugins=PythonScriptPlugin,EditorScriptingUtilities,Interchange" -unattended -nullrhi

First, index the tiles with Blender (Tools/blender/building_index.py), which writes one JSON per tile
to <project>/Saved/MAirCorridor/building_index.

WHAT IT DOES, per tile:

  1. Imports the tile's FBX from MAirCorridor_Assets (corridor_tiles_baked) as one static mesh per
     building, into Content/BuildingsSplit/<tile>. Each building is its own object in the FBX, with
     its pivot at a footprint corner at ground level; the import keeps those pivots (no baking), so
     each mesh's pivot is its building's base. Nanite on, complex collision, and the existing
     building material instances assigned by slot name (every slot name matches one already in
     Content/Buildings). Importing without baking leaves the FBX's metres as centimetres, so the
     meshes are built at scale 100.
  2. Places each building where it already was: its position is the merged tile actor's in the
     level plus its pivot, so nothing moves sideways. (The level's tiles sit about 26 m from where
     corridor_tiles.json puts them; the level is what is kept.)
  3. Drops it onto the Landscape: from 100 m above the building's top, a ray down at each footprint
     corner and the centre, hitting the Landscape only (buildings, trees and the scan in the way are
     ignored). The building's base goes to the LOWEST of the five, so no corner floats on a slope;
     the uphill side sits slightly into the ground instead. A hit more than 10 m below the median of
     the five is a hole under one corner, not a slope, and is left out: the ground model has a pit
     45 m deep and 25 m across in flat Dearborn (-83.17128, 42.31794), and the lowest-of-five rule
     sank the building beside it 43 m into the ground. A building with no Landscape under it keeps
     its height.
  4. Spawns one static mesh actor per building, labelled with its OpenStreetMap name, in the
     outliner folder Buildings/<tile>, tagged "building" and "tile:<tile>", streamed by World
     Partition, in the building segmentation class.
  5. Records the merged tile actor's transform in Tools/building_tiles_placement.json, so the tiles
     can be put back, and removes it.
  6. Saves the tile's meshes and actors, unloads what it loaded, and moves on.

Each building can then be deleted on its own; the folder says which tile it came from.

A TILE IS ONLY REMOVED WHEN EVERY ONE OF ITS BUILDINGS STANDS IN ITS PLACE. If the import gives
fewer meshes than the tile has buildings, or any building fails to spawn, the tile is left exactly
as it was, whatever was spawned for it is removed, and the run says so and moves on. (An earlier
version removed tiles regardless, and an import that came back empty took 20 tiles' buildings out
of the level; MAIR_RESTORE=1 is how they were put back.)

A tile already split (no merged tile actor left) is skipped, so a run that stops can be run again.
MAIR_TILES=tile_a,tile_b limits it to those tiles. MAIR_DRY=1 does ONE tile and saves nothing.
MAIR_MAX_TILES=N stops after N tiles split. One long process slows as the tiles it has done pile up
in memory (0.05 s a building at the start, 0.17 s sixteen tiles later), so a full run goes faster as a
loop of shorter ones, each starting where the last stopped.

MAIR_REDROP=name,name drops buildings already standing onto the Landscape again with the rule
above, for buildings placed before it changed or after the Landscape is edited. Only their height
changes. It saves, and splits nothing.

MAIR_RESTORE=1 puts back every merged tile that is missing from the level without its buildings
standing in its place: same mesh (Content/Buildings/<tile>), the transform recorded in
Tools/building_tiles_placement.json, and the settings of a merged tile still in the level. It
restores and saves, and splits nothing.
"""
import io
import json
import os
import sys
import time

# Removed merged tiles are deleted by FILE, and a running editor holds a loaded actor's file open, so
# the files it could not delete are listed here and deleted afterwards by running this same script
# with plain Python:  py -3.10 Tools/unreal/split_buildings.py --delete-pending
PENDING = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "..", "Saved",
                       "MAirCorridor", "split_pending_deletions.txt")
try:
    import unreal
except ImportError:
    if "--delete-pending" not in sys.argv:
        sys.exit("Run this inside Unreal, or with --delete-pending after a run to finish its deletions.")
    done = left = 0
    if os.path.isfile(PENDING):
        with io.open(PENDING, encoding="utf-8") as f:
            paths = [l.strip() for l in f if l.strip()]
        keep = []
        for path in paths:
            try:
                if os.path.isfile(path):
                    os.remove(path)
                done += 1
            except OSError:
                keep.append(path)
        left = len(keep)
        with io.open(PENDING, "w", encoding="utf-8") as f:
            f.write("".join(k + "\n" for k in keep))
    print("deleted %d removed merged tile files; %d still locked (close Unreal and run again)" % (done, left))
    sys.exit(0)

MARK = "MAIRSPLIT"
DRY = os.environ.get("MAIR_DRY") == "1"
LEVEL = "/MAirCorridor/Scene/CorridorTerrain"
DEST = "/MAirCorridor/BuildingsSplit"
MERGED = "/MAirCorridor/Buildings"
RAISE_CM = 10000.0                    # start the rays 100 m above the building's top
PIT_CM = 1000.0                       # a hit this far below the median of the five is a hole
DROP_CM = 300000.0                    # and look 3 km down
PROJECT = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())
TOOLS = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_plugins_dir()),
                     "MAirCorridor", "Tools")
INDEX = os.environ.get("MAIR_BUILDING_INDEX",
                       os.path.join(PROJECT, "Saved", "MAirCorridor", "building_index"))
ASSETS = os.environ.get("MAIRCORRIDOR_ASSETS") or os.path.join(os.path.dirname(os.path.normpath(PROJECT)),
                                                              "MAirCorridor_Assets")
TILES_FBX = os.path.join(ASSETS, "corridor_tiles_baked")
PLACEMENT = os.path.join(TOOLS, "building_tiles_placement.json")
# The characters Unreal replaces with "_" in an asset name (INVALID_OBJECTNAME_CHARACTERS).
INVALID = "\"' ,/.:|&!~\n\r\t@#(){}[]=;^%$`"

actors_sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
reg = unreal.AssetRegistryHelpers.get_asset_registry()
wp = unreal.WorldPartitionBlueprintLibrary


def say(text):
    unreal.log_warning("%s %s" % (MARK, text))
    print("%s %s" % (MARK, text))


def asset_name(name):
    return "".join("_" if c in INVALID else c for c in name)


def building_class():
    try:
        with io.open(os.path.join(TOOLS, "segmentation.json"), encoding="utf-8") as f:
            return json.load(f)["classes"]["building"]["id"]
    except Exception:
        return None


def descriptors():
    big = unreal.Box(unreal.Vector(-1e9, -1e9, -1e9), unreal.Vector(1e9, 1e9, 1e9))
    d = wp.get_intersecting_actor_descs(big)
    return d[-1] if isinstance(d, tuple) else d


def load_box(lo, hi):
    """Load every actor whose bounds meet this box; returns the guids loaded here."""
    box = unreal.Box(unreal.Vector(lo[0], lo[1], -1e7), unreal.Vector(hi[0], hi[1], 1e7))
    d = wp.get_intersecting_actor_descs(box)
    d = d[-1] if isinstance(d, tuple) else d
    guids = [x.get_editor_property("guid") for x in d]
    wp.load_actors(guids)
    return guids


def import_tile(tile):
    pipeline = unreal.InterchangeGenericAssetsPipeline()
    mesh = pipeline.get_editor_property("mesh_pipeline")
    mesh.set_editor_property("combine_static_meshes", False)
    mesh.set_editor_property("build_nanite", True)
    mesh.set_editor_property("build_scale3d", unreal.Vector(100.0, 100.0, 100.0))
    pipeline.get_editor_property("common_meshes_properties").set_editor_property("bake_meshes", False)
    mat = pipeline.get_editor_property("material_pipeline")
    mat.set_editor_property("import_materials", False)
    try:
        mat.get_editor_property("texture_pipeline").set_editor_property("import_textures", False)
    except Exception:
        pass
    params = unreal.ImportAssetParameters()
    params.set_editor_property("is_automated", True)
    params.set_editor_property("replace_existing", True)
    params.set_editor_property("override_pipelines", [unreal.SoftObjectPath(pipeline.get_path_name())])
    mgr = unreal.InterchangeManager.get_interchange_manager_scripted()
    # WaitUntilAllTasksDone takes bCancel: True CANCELS what is pending instead of waiting for it,
    # which is how every import after the first came back empty. False waits.
    mgr.wait_until_all_tasks_done(False)
    imported = mgr.import_asset("%s/%s" % (DEST, tile),
                                unreal.InterchangeManager.create_source_data(
                                    os.path.join(TILES_FBX, tile + ".fbx")),
                                params)
    mgr.wait_until_all_tasks_done(False)
    meshes = {}
    if isinstance(imported, (list, tuple)):
        for obj in imported:
            if isinstance(obj, unreal.StaticMesh):
                meshes[obj.get_name()] = obj.get_path_name().split(".")[0]
    for a in reg.get_assets_by_path("%s/%s" % (DEST, tile), recursive=True):
        if str(a.asset_class_path.asset_name) == "StaticMesh":
            meshes.setdefault(str(a.asset_name), str(a.package_name))
    return meshes


def finish_mesh(mesh, slot_materials):
    """Existing materials by slot name, and collision that is the mesh itself."""
    missing = 0
    for i, slot in enumerate(mesh.get_editor_property("static_materials")):
        mi = slot_materials.get(str(slot.get_editor_property("material_slot_name")))
        if mi is None:
            missing += 1
        else:
            mesh.set_material(i, mi)
    body = mesh.get_editor_property("body_setup")
    if body is not None:
        body.set_editor_property("collision_trace_flag",
                                 unreal.CollisionTraceFlag.CTF_USE_COMPLEX_AS_SIMPLE)
    return missing


def ground(world, x, y, z_top, ignore):
    """Height of the Landscape under (x, y), or None. Every other actor is in the ignore list."""
    hits = unreal.SystemLibrary.line_trace_multi(
        world, unreal.Vector(x, y, z_top), unreal.Vector(x, y, z_top - DROP_CM),
        unreal.TraceTypeQuery.TRACE_TYPE_QUERY1, True, ignore, unreal.DrawDebugTrace.NONE, True)
    if isinstance(hits, tuple):
        hits = hits[-1]
    for h in hits or []:
        t = h.to_tuple()
        if isinstance(t[9], unreal.LandscapeProxy):
            return t[5].z
    return None


def base_height(heights):
    """The lowest of the hits, leaving out any more than PIT_CM below their median, and how many
    were left out."""
    mid = sorted(heights)[len(heights) // 2]
    kept = [h for h in heights if h >= mid - PIT_CM]
    return min(kept), len(heights) - len(kept)


def footprint_samples(r, x, y):
    """The footprint's four corners and its centre, in Unreal centimetres, for a building whose
    pivot stands at (x, y). The index is in Blender's frame, where Y is north; Unreal's Y is south."""
    px, py = r["pivot"][0], r["pivot"][1]
    (x0, y0), (x1, y1) = r["min"][:2], r["max"][:2]
    return [(x + (sx - px) * 100.0, y - (sy - py) * 100.0)
            for sx, sy in ((x0, y0), (x0, y1), (x1, y0), (x1, y1), ((x0 + x1) / 2, (y0 + y1) / 2))]


CONTENT = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_plugins_dir()),
                       "MAirCorridor", "Content")


def actor_file(actor):
    """The file a World Partition actor is saved in (its external package)."""
    name = actor.get_outermost().get_name()            # /MAirCorridor/__ExternalActors__/...
    if not name.startswith("/MAirCorridor/"):
        return None
    return os.path.join(CONTENT, *name[len("/MAirCorridor/"):].split("/")) + ".uasset"


def remove_for_good(actor):
    """Destroy an actor AND delete its file. Destroying alone is not enough headless: saving dirty
    packages writes what changed but does not delete a removed actor's file, so the merged tiles
    came straight back. Returns the file deleted, or None."""
    path = actor_file(actor)
    actors_sub.destroy_actor(actor)
    if path and os.path.isfile(path) and not DRY:
        return delete_or_queue(path)
    return None


def delete_or_queue(path):
    """Delete a removed actor's file now, or list it for --delete-pending when the editor holds it."""
    try:
        os.remove(path)
        return path
    except OSError:
        os.makedirs(os.path.dirname(PENDING), exist_ok=True)
        with io.open(PENDING, "a", encoding="utf-8") as f:
            f.write(path + "\n")
        return path + " (queued: still open in the editor)"


def record_placement(tile, actor):
    placed = {}
    if os.path.isfile(PLACEMENT):
        with io.open(PLACEMENT, encoding="utf-8") as f:
            placed = json.load(f)
    loc, rot, sc = actor.get_actor_location(), actor.get_actor_rotation(), actor.get_actor_scale3d()
    placed.setdefault("WHAT", "Where the merged building tile actors stood in the corridor level before "
                              "Tools/unreal/split_buildings.py split them into one actor per building: "
                              "location in Unreal centimetres, rotation in degrees. The mesh of each is "
                              "Content/Buildings/<tile>.")
    placed.setdefault("tiles", {})[tile] = {
        "location_cm": [round(loc.x, 2), round(loc.y, 2), round(loc.z, 2)],
        "rotation_deg": [round(rot.pitch, 4), round(rot.yaw, 4), round(rot.roll, 4)],
        "scale": [round(sc.x, 4), round(sc.y, 4), round(sc.z, 4)]}
    if not DRY:
        with io.open(PLACEMENT, "w", encoding="utf-8", newline="\n") as f:
            json.dump(placed, f, indent=1, sort_keys=True)
            f.write("\n")


def split(tile, world, seg_id):
    started = time.time()
    with io.open(os.path.join(INDEX, tile + ".json"), encoding="utf-8") as f:
        rows = json.load(f)["buildings"]
    label = "Corridor_" + tile
    tile_descs = [d for d in descriptors() if str(d.get_editor_property("label")) == label]
    if not tile_descs:
        say("%s: no merged tile actor in the level, so it is already split; skipped" % tile)
        return None
    wp.load_actors([d.get_editor_property("guid") for d in tile_descs])
    tile_actor = next(a for a in actors_sub.get_all_level_actors() if a.get_actor_label() == label)

    # Already split, with the merged tile left behind? Then only the merged tile has to go.
    labels = set(str(d.get_editor_property("label")) for d in descriptors())
    standing = sum(1 for r in rows if r["name"] in labels)
    if standing == len(rows):
        record_placement(tile, tile_actor)
        gone = remove_for_good(tile_actor)
        say("%s: its %d buildings already stand; removed the merged tile left behind (%s)" % (
            tile, standing, gone))
        return 0
    if standing:
        say("%s: %d of its %d buildings already stand; left for a person to sort out" % (
            tile, standing, len(rows)))
        return None
    origin = tile_actor.get_actor_location()
    if abs(tile_actor.get_actor_rotation().yaw) > 1e-3 or abs(tile_actor.get_actor_scale3d().x - 1) > 1e-6:
        say("%s: the merged tile actor is rotated or scaled; this tool does not handle that, skipped" % tile)
        return None

    # The tile's footprint in the level, and everything in it loaded so the rays have Landscape.
    xs = [origin.x + r[k][0] * 100.0 for r in rows for k in ("min", "max")]
    ys = [origin.y - r[k][1] * 100.0 for r in rows for k in ("min", "max")]
    loaded = load_box((min(xs) - 5000, min(ys) - 5000), (max(xs) + 5000, max(ys) + 5000))
    x0, x1, y0, y1 = min(xs) - 5000, max(xs) + 5000, min(ys) - 5000, max(ys) + 5000
    ignore = []
    for a in actors_sub.get_all_level_actors():
        if isinstance(a, unreal.LandscapeProxy):
            continue
        c, e = a.get_actor_bounds(False)
        if c.x + e.x >= x0 and c.x - e.x <= x1 and c.y + e.y >= y0 and c.y - e.y <= y1:
            ignore.append(a)

    meshes = import_tile(tile)
    say("%s: imported %d building meshes; %d actors in the way of the rays are ignored" % (
        tile, len(meshes), len(ignore)))
    # A file holding ONE mesh comes in named after the file, not the object in it
    # (tile_-0007_-0004, whose one building is element.95474), so give it its building's name.
    if len(rows) == 1 and len(meshes) == 1:
        got, path = next(iter(meshes.items()))
        want = asset_name(rows[0]["name"])
        if got != want:
            new = "%s/%s/%s" % (DEST, tile, want)
            if unreal.EditorAssetLibrary.rename_asset(path, new):
                meshes = {want: new}
                say("%s: its one mesh came in named %s, after the file; renamed %s" % (tile, got, want))
    short = [r["name"] for r in rows if asset_name(r["name"]) not in meshes]
    if short:
        say("%s: LEFT AS IT WAS. The import gave no mesh for %d of its %d buildings (e.g. %s), so "
            "the merged tile stays" % (tile, len(short), len(rows), short[:3]))
        if not DRY:
            wp.unload_actors(loaded)
        return None
    slot_materials = {str(s.get_editor_property("material_slot_name")): s.get_editor_property("material_interface")
                      for s in unreal.load_asset("%s/%s" % (MERGED, tile)).get_editor_property("static_materials")}

    # Every height first, then every actor: a ray must never meet a building placed a moment ago.
    plan = []
    no_ground = unmatched = missing_mats = over_holes = 0
    moved = []
    for r in rows:
        path = meshes.get(asset_name(r["name"]))
        if path is None:
            unmatched += 1
            continue
        px, py, pz = r["pivot"]
        old_z = origin.z + pz * 100.0
        top = origin.z + r["max"][2] * 100.0 + RAISE_CM
        samples = footprint_samples(r, origin.x + px * 100.0, origin.y - py * 100.0)
        heights = [ground(world, sx, sy, top, ignore) for sx, sy in samples]
        heights = [h for h in heights if h is not None]
        if heights:
            z, holes = base_height(heights)
            if holes:
                over_holes += 1
                say("%s: %s has %d of its footprint samples over a hole more than %.0f m deep; "
                    "left out" % (tile, r["name"], holes, PIT_CM / 100.0))
            moved.append(z - old_z)
        else:
            z = old_z
            no_ground += 1
        plan.append((r, path, unreal.Vector(origin.x + px * 100.0, origin.y - py * 100.0, z)))

    say("%s: heights found for %d buildings" % (tile, len(plan)))
    made = 0
    spawned = []
    for r, path, where in plan:
        mesh = unreal.load_asset(path)
        missing_mats += finish_mesh(mesh, slot_materials)
        # From the class, then the mesh: spawning from the asset also selects the new actor, and a
        # headless editor has no selection to update (it crashed there).
        actor = actors_sub.spawn_actor_from_class(unreal.StaticMeshActor, where, unreal.Rotator())
        actor.set_actor_label(r["name"])
        actor.set_folder_path("Buildings/%s" % tile)
        actor.set_editor_property("tags", ["building", "tile:%s" % tile])
        actor.set_editor_property("is_spatially_loaded", True)
        comp = actor.get_editor_property("static_mesh_component")
        comp.set_mobility(unreal.ComponentMobility.STATIC)
        comp.set_static_mesh(mesh)
        comp.set_collision_profile_name("BlockAll")
        if seg_id is not None:
            comp.set_editor_property("render_custom_depth", True)
            comp.set_editor_property("custom_depth_stencil_value", seg_id)
        try:
            actor.set_editor_property("hlod_layer", tile_actor.get_editor_property("hlod_layer"))
        except Exception:
            pass
        spawned.append(actor)
        made += 1

    if made != len(rows):
        for a in spawned:
            actors_sub.destroy_actor(a)
        say("%s: LEFT AS IT WAS. %d of %d buildings were placed, so they were removed again and the "
            "merged tile stays" % (tile, made, len(rows)))
        if not DRY:
            wp.unload_actors(loaded)
        return None
    record_placement(tile, tile_actor)
    merged_file = actor_file(tile_actor)
    actors_sub.destroy_actor(tile_actor)
    moved.sort()
    med = moved[len(moved) // 2] / 100.0 if moved else 0.0
    say("%s: %d buildings placed of %d (%d without Landscape under them, %d over a hole, %d with no "
        "mesh, %d material slots unmatched); base moved %.1f m at the median, %.1f to %.1f m, in %.0f s" % (
            tile, made, len(rows), no_ground, over_holes, unmatched, missing_mats, med,
            (moved[0] / 100.0) if moved else 0, (moved[-1] / 100.0) if moved else 0, time.time() - started))
    if not DRY:
        unreal.EditorLoadingAndSavingUtils.save_dirty_packages(True, True)
        # The buildings are saved; only now does the merged tile's file go.
        if merged_file and os.path.isfile(merged_file):
            delete_or_queue(merged_file)
        # Saved, so let go of this tile's actors, new and old, before the next one loads its own.
        wp.unload_actors(loaded + [a.get_editor_property("actor_guid") for a in spawned])
        unreal.SystemLibrary.collect_garbage()
    return made


def restore():
    """Put back every recorded merged tile that is gone without its buildings standing in its place."""
    if not os.path.isfile(PLACEMENT):
        say("nothing recorded in %s, so nothing to restore" % PLACEMENT)
        return
    with io.open(PLACEMENT, encoding="utf-8") as f:
        recorded = json.load(f).get("tiles", {})
    labels = set(str(d.get_editor_property("label")) for d in descriptors())
    # A surviving merged tile, to copy its settings onto the ones put back.
    template_desc = [d for d in descriptors() if str(d.get_editor_property("label")).startswith("Corridor_tile")]
    template = None
    if template_desc:
        wp.load_actors([template_desc[0].get_editor_property("guid")])
        template = next(a for a in actors_sub.get_all_level_actors()
                        if a.get_actor_label() == str(template_desc[0].get_editor_property("label")))
    put_back = 0
    for tile, t in sorted(recorded.items()):
        if "Corridor_" + tile in labels:
            continue
        with io.open(os.path.join(INDEX, tile + ".json"), encoding="utf-8") as f:
            names = [r["name"] for r in json.load(f)["buildings"]]
        standing = sum(1 for n in names if n in labels)
        if standing == len(names):
            continue                      # split properly: its buildings stand in its place
        if standing:
            say("%s: %d of its %d buildings stand in the level; restore by hand" % (tile, standing, len(names)))
            continue
        mesh = unreal.load_asset("%s/%s" % (MERGED, tile))
        loc = unreal.Vector(*t["location_cm"])
        rot = unreal.Rotator(roll=t["rotation_deg"][2], pitch=t["rotation_deg"][0], yaw=t["rotation_deg"][1])
        actor = actors_sub.spawn_actor_from_class(unreal.StaticMeshActor, loc, rot)
        actor.set_actor_scale3d(unreal.Vector(*t["scale"]))
        actor.set_actor_label("Corridor_" + tile)
        comp = actor.get_editor_property("static_mesh_component")
        comp.set_mobility(unreal.ComponentMobility.STATIC)
        comp.set_static_mesh(mesh)
        if template is not None:
            for prop in ("is_spatially_loaded", "hlod_layer", "tags"):
                try:
                    actor.set_editor_property(prop, template.get_editor_property(prop))
                except Exception:
                    pass
            try:
                actor.set_folder_path(str(template.get_folder_path()))
            except Exception:
                pass
            tc = template.get_editor_property("static_mesh_component")
            for prop in ("render_custom_depth", "custom_depth_stencil_value", "cast_shadow"):
                try:
                    comp.set_editor_property(prop, tc.get_editor_property(prop))
                except Exception:
                    pass
            try:
                comp.set_collision_profile_name(tc.get_collision_profile_name())
            except Exception:
                pass
        put_back += 1
        say("%s: merged tile put back at %s" % (tile, t["location_cm"]))
    unreal.EditorLoadingAndSavingUtils.save_dirty_packages(True, True)
    say("restored %d merged tiles%s" % (put_back, "" if template is not None else
                                        " (no merged tile left to copy settings from; defaults used)"))


def redrop(world, names):
    """Drop the named buildings onto the Landscape again with base_height; only Z changes."""
    rows = {}
    for f in sorted(os.listdir(INDEX)):
        if f.endswith(".json"):
            with io.open(os.path.join(INDEX, f), encoding="utf-8") as fh:
                for r in json.load(fh)["buildings"]:
                    if r["name"] in names:
                        rows[r["name"]] = r
    descs = {str(d.get_editor_property("label")): d for d in descriptors()
             if str(d.get_editor_property("label")) in names}
    for name in sorted(names):
        if name not in rows or name not in descs:
            say("%s: %s, skipped" % (name, "not in the building index" if name not in rows
                                     else "not standing in the level"))
            continue
        guid = descs[name].get_editor_property("guid")
        wp.load_actors([guid])
        actor = next(a for a in actors_sub.get_all_level_actors() if a.get_actor_label() == name)
        at = actor.get_actor_location()
        samples = footprint_samples(rows[name], at.x, at.y)
        xs, ys = [q[0] for q in samples], [q[1] for q in samples]
        loaded = load_box((min(xs) - 5000, min(ys) - 5000), (max(xs) + 5000, max(ys) + 5000))
        ignore = [a for a in actors_sub.get_all_level_actors() if not isinstance(a, unreal.LandscapeProxy)]
        # From 100 m above its top as it stands now, plus the most any building has sunk.
        top = at.z + (rows[name]["max"][2] - rows[name]["pivot"][2]) * 100.0 + RAISE_CM + 5000.0
        heights = [h for h in (ground(world, x, y, top, ignore) for x, y in samples) if h is not None]
        if not heights:
            say("%s: no Landscape under it; left at %.1f m" % (name, at.z / 100.0))
            wp.unload_actors(loaded + [guid])
            continue
        z, holes = base_height(heights)
        say("%s: ground %s m; base %.1f m to %.1f m (%d sample%s left out as over a hole)" % (
            name, [round(h / 100.0, 1) for h in heights], at.z / 100.0, z / 100.0, holes,
            "" if holes == 1 else "s"))
        if abs(z - at.z) > 1.0 and not DRY:
            # Moving an actor from Python does not mark its package dirty, and an actor whose
            # package is clean is not saved: the first redrop moved this one and saved nothing.
            actor.modify()
            actor.set_actor_location(unreal.Vector(at.x, at.y, z), False, False)
            unreal.EditorLoadingAndSavingUtils.save_dirty_packages(True, True)
            path = actor_file(actor)
            age = time.time() - os.path.getmtime(path) if path and os.path.isfile(path) else None
            say("%s: %s" % (name, "saved, %s written %.0f s ago" % (path, age) if age is not None and age < 60
                            else "NOT SAVED: its file %s was not written" % path))
        wp.unload_actors(loaded + [guid])


world = unreal.EditorLoadingAndSavingUtils.load_map(LEVEL)
if os.environ.get("MAIR_REDROP"):
    redrop(world, set(n for n in os.environ["MAIR_REDROP"].split(",") if n))
    say("redrop done")
    raise SystemExit
if os.environ.get("MAIR_RESTORE") == "1":
    restore()
    raise SystemExit
seg_id = building_class()
tiles = sorted(os.path.splitext(f)[0] for f in os.listdir(INDEX) if f.endswith(".json"))
wanted = [t for t in os.environ.get("MAIR_TILES", "").split(",") if t]
if wanted:
    tiles = [t for t in tiles if t in wanted]
say("%d tiles to split%s; building segmentation class %s" % (
    len(tiles), " (dry run: the first only, nothing saved)" if DRY else "", seg_id))
total = 0
limit = int(os.environ.get("MAIR_MAX_TILES", "0") or 0)
split_here = 0
for tile in tiles:
    made = split(tile, world, seg_id)
    total += made or 0
    if made:
        split_here += 1
    if DRY and made:
        break
    if limit and split_here >= limit:
        say("stopping after %d tiles (MAIR_MAX_TILES); run again to carry on" % split_here)
        break
say("done: %d buildings placed" % total)
if not DRY:
    unreal.EditorLoadingAndSavingUtils.save_dirty_packages(True, True)
    if os.path.isfile(PENDING) and os.path.getsize(PENDING):
        say("FINISH WITH: py -3.10 Tools/unreal/split_buildings.py --delete-pending  "
            "(the merged tiles' files, which this run could not delete while it held them)")
