"""corridor_streaming.py - how far out the buildings and trees load, and what stands in for them past that.

Headless, with the editor CLOSED (it edits the corridor level and saves as it goes), after the
plugin is built (it calls UMAirStreamingLibrary, Source/MAirCorridorEditor):

    UnrealEditor-Cmd.exe <project>.uproject -run=pythonscript
        -script=<absolute path>/Tools/unreal/corridor_streaming.py
        "-EnablePlugins=PythonScriptPlugin,EditorScriptingUtilities" -unattended -nullrhi

then build the HLODs it sets up:

    UnrealEditor-Cmd.exe <project>.uproject /MAirCorridor/Scene/CorridorTerrain
        -run=WorldPartitionBuilderCommandlet -Builder=WorldPartitionHLODsBuilder
        -SetupHLODs -BuildHLODs -nullrhi -unattended
        -ini:Engine:[/Script/Engine.RendererSettings]:r.GenerateMeshDistanceFields=False

WITHOUT THE GPU (-nullrhi), unlike the editor's own Build > Build HLODs, which runs it with
-AllowCommandletRendering. Building HLODs loads every building mesh and does not let them go: with
the GPU each takes a Nanite root page, and the build stopped at 686 of its 1,192 HLOD actors with
the pool full (49,152). Instancing HLODs render nothing while they are built, so no GPU is needed.
With distance fields off for the run it does not stop to build 73,403 of them it has no use for
(Tools/unreal/building_mesh_settings.py says why).

WHY. The level had one runtime partition, MainGrid: 252 m cells loaded within 768 m of the
camera. Splitting the 100 merged building tiles into 73,403 buildings moved every building from a 2
to 4 km cell, which loads from kilometres away, into those smallest cells, so each building existed
only within 768 m of the drone. No actor in the level had an HLOD layer either (every HLOD build
so far made 0 HLOD actors), so past the loading range there was nothing at all: buildings blinked
in and out as the drone flew. Measured in the play session that showed it, streaming also swung
between Good, Slow and Critical.

WHAT IT SETS UP.

  Buildings   a runtime partition of their own: 512 m cells loaded within 4 km of the camera.
              Buildings average 22 triangles, so loading them far out costs little. Past that,
              HLOD_Buildings stands in, in 2 km cells loaded within 7 km.
  Trees       stay in the level's main partition, unchanged, so the woods cost what they did
              near the camera. Past it, HLOD_Trees stands in, in 2 km cells loaded within 8 km.

NANITE ROOT PAGES set how far the buildings can reach. Every distinct Nanite mesh in memory takes
at least one 32 KB root page, and the pool they come from cannot pass 2 GB on this NVIDIA GPU
(NaniteStreamingManager.cpp: 2048 MB, less the 512 MB streaming pool, leaves 49,152 root pages);
past that the engine stops with a fatal error. Every building is its own mesh, 73,403 of them, so
no more than about two thirds of them may ever be resident at once. Counted from every building's
position, with the camera anywhere in the corridor, the most resident at once is 18,072 for the
buildings themselves within 4 km, and for their HLOD 28,437 within 6 km, 30,373 within 7 km,
34,174 within 8 km, 44,750 within 10 km and 54,023 within 15 km, which would stop the game. 7 km
leaves a third of the pool for everything else.

Both HLOD layers are Instancing layers (copies of the level's own CorridorTerrain_HLOD0_Instancing):
the stand-in draws the same Nanite meshes, gathered per cell, with no actors, so nothing is baked
and a building far off looks exactly like the building near.

Each building actor gets Runtime Grid "Buildings" and HLOD layer HLOD_Buildings; each foliage
actor (Foliage_*, Tools/unreal/stream_foliage.py) gets HLOD_Trees. Running it again changes only
what differs. It works tile by tile, saving each and checking the save landed, and records the
tiles done in Saved/MAirCorridor/streaming_done.txt, so a run that stops carries on (MAIR_FORCE=1
does them all again). MAIR_MAX_TILES=N stops after N tiles. MAIR_DRY=1 changes nothing and
describes the streaming setup as it stands.
"""
import io
import json
import os
import time

import unreal

MARK = "MAIRSTREAM"
LEVEL = "/MAirCorridor/Scene/CorridorTerrain"
SCENE = "/MAirCorridor/Scene"
TEMPLATE_LAYER = SCENE + "/CorridorTerrain_HLOD0_Instancing"
BUILDING_LAYER = SCENE + "/HLOD_Buildings"
TREE_LAYER = SCENE + "/HLOD_Trees"
GRID = "Buildings"
BUILDINGS_CELL, BUILDINGS_RANGE = 51200, 400000                 # 512 m cells, 4 km
BUILDINGS_HLOD_CELL, BUILDINGS_HLOD_RANGE = 204800, 700000      # 2 km cells, 7 km: see NANITE ROOT PAGES
TREES_HLOD_CELL, TREES_HLOD_RANGE = 204800, 800000              # 2 km cells, 8 km
DRY = os.environ.get("MAIR_DRY") == "1"
PROJECT = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())
INDEX = os.environ.get("MAIR_BUILDING_INDEX", os.path.join(PROJECT, "Saved", "MAirCorridor", "building_index"))
DONE = os.path.join(PROJECT, "Saved", "MAirCorridor", "streaming_done.txt")
CONTENT = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_plugins_dir()),
                       "MAirCorridor", "Content")

actors_sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
wp = unreal.WorldPartitionBlueprintLibrary
lib = unreal.MAirStreamingLibrary


def say(text):
    unreal.log_warning("%s %s" % (MARK, text))


def actor_file(actor):
    name = actor.get_outermost().get_name()
    if not name.startswith("/MAirCorridor/"):
        return None
    return os.path.join(CONTENT, *name[len("/MAirCorridor/"):].split("/")) + ".uasset"


def hlod_layer(path):
    """The HLOD layer at path, copied from the level's own Instancing layer if there is none yet."""
    # Headless, the asset registry has not looked in the folder yet, and duplicating needs it to have.
    unreal.AssetRegistryHelpers.get_asset_registry().scan_paths_synchronous([SCENE], True)
    if unreal.EditorAssetLibrary.does_asset_exist(path):
        layer = unreal.load_asset(path)
    elif DRY:
        return None
    else:
        layer = unreal.EditorAssetLibrary.duplicate_asset(TEMPLATE_LAYER, path)
        say("made HLOD layer %s from %s" % (path, TEMPLATE_LAYER))
    if not isinstance(layer, unreal.HLODLayer):
        raise RuntimeError("no HLOD layer at %s (got %r)" % (path, layer))
    return layer


world = unreal.EditorLoadingAndSavingUtils.load_map(LEVEL)
say("as it stands:\n" + lib.describe_streaming(world))
if DRY:
    raise SystemExit

# ---- the partitions -------------------------------------------------------------------------------
buildings_layer, trees_layer = hlod_layer(BUILDING_LAYER), hlod_layer(TREE_LAYER)
first = lib.describe_streaming(world).split("\n")[1]          # "partition <name>: ..."
main = first.split(" ", 1)[1].split(":", 1)[0] if first.startswith("partition ") else None
if not main:
    raise RuntimeError("no runtime partition found: %r" % first)
# A bool function with an out parameter comes back as the out parameter, or None when it fails.
for name, cell, rng, layer, hcell, hrng in ((main, 0, 0, trees_layer, TREES_HLOD_CELL, TREES_HLOD_RANGE),
                                            (GRID, BUILDINGS_CELL, BUILDINGS_RANGE, buildings_layer,
                                             BUILDINGS_HLOD_CELL, BUILDINGS_HLOD_RANGE)):
    if lib.set_runtime_partition(world, name, cell, rng, layer, hcell, hrng) is None:
        raise RuntimeError("could not set partition %s up" % name)
unreal.EditorLoadingAndSavingUtils.save_dirty_packages(True, True)
say("set up:\n" + lib.describe_streaming(world))

# ---- the actors ----------------------------------------------------------------------------------
done = set()
if os.path.isfile(DONE) and os.environ.get("MAIR_FORCE") != "1":
    with io.open(DONE, encoding="utf-8") as f:
        done = set(l.strip() for l in f if l.strip())
big = unreal.Box(unreal.Vector(-1e9, -1e9, -1e9), unreal.Vector(1e9, 1e9, 1e9))
descs = wp.get_intersecting_actor_descs(big)
descs = descs[-1] if isinstance(descs, tuple) else descs
guid_of = {str(d.get_editor_property("label")): d.get_editor_property("guid") for d in descs}

groups = {}
for f in sorted(os.listdir(INDEX)):
    if f.endswith(".json"):
        with io.open(os.path.join(INDEX, f), encoding="utf-8") as fh:
            index = json.load(fh)
        groups[index["tile"]] = ([b["name"] for b in index["buildings"]], GRID, buildings_layer)
groups["foliage"] = ([l for l in guid_of if l.startswith("Foliage_")], None, trees_layer)
limit = int(os.environ.get("MAIR_MAX_TILES", "0") or 0)
say("%d groups (%d building tiles and the foliage); %d already done" % (
    len(groups), len(groups) - 1, len(done & set(groups))))

here = changed_total = 0
for group in sorted(groups, key=lambda g: (g == "foliage", g)):
    if group in done:
        continue
    started = time.time()
    names, grid, layer = groups[group]
    names = set(names)
    guids = [guid_of[n] for n in names if n in guid_of]
    wp.load_actors(guids)
    actors = [a for a in actors_sub.get_all_level_actors() if a.get_actor_label() in names]
    changed, sample = 0, None
    for a in actors:
        want_grid = grid or a.get_editor_property("runtime_grid")
        if str(a.get_editor_property("runtime_grid")) == str(want_grid or "None") and \
                a.get_editor_property("hlod_layer") == layer:
            continue
        # A change from Python does not mark the actor's package dirty, and a clean package is not saved.
        a.modify()
        if grid:
            a.set_editor_property("runtime_grid", grid)
        a.set_editor_property("hlod_layer", layer)
        changed += 1
        sample = sample or a
    unreal.EditorLoadingAndSavingUtils.save_dirty_packages(True, True)
    if sample is not None:
        path = actor_file(sample)
        age = time.time() - os.path.getmtime(path) if path and os.path.isfile(path) else None
        if age is None or age > 120:
            say("%s: NOT SAVED: %s was not written; stopping" % (group, path))
            break
    with io.open(DONE, "a", encoding="utf-8") as f:
        f.write(group + "\n")
    wp.unload_actors(guids)
    unreal.SystemLibrary.collect_garbage()
    changed_total += changed
    here += 1
    say("%s: %d of %d actors set (%d not in the level), in %.0f s" % (
        group, changed, len(names), len(names) - len(guids), time.time() - started))
    if limit and here >= limit:
        say("stopping after %d groups (MAIR_MAX_TILES); run again to carry on" % here)
        break
say("done: %d actors set in %d groups" % (changed_total, here))
