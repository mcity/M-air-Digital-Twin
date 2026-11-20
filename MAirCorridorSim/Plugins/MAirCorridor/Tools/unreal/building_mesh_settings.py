"""building_mesh_settings.py - coarse distance fields for the 73,403 building meshes, built ahead of play.

Run INSIDE THE EDITOR, not headless, with nothing else open on the project:

    UnrealEditor.exe <project>.uproject -ExecutePythonScript="<absolute path>/Tools/unreal/building_mesh_settings.py"
        -unattended -ini:Engine:[/Script/Engine.RendererSettings]:r.GenerateMeshDistanceFields=False

It prints "MAIRMESH finished" when every tile is saved; the window can then be closed.

WITH DISTANCE FIELDS OFF FOR THE RUN, as above. A distance field is built apart from the mesh and
cached under its own key, which the editor misses as well, so every mesh loaded rebuilds its old
126 cubed field first (1 to 14 s each) before it can be changed: measured, a tile of 807 meshes
took over 10 minutes that way, and 43 s with them off. The mesh's own cache key does not depend on
whether fields are generated, so what this builds is what the editor uses with them on. The new
coarse fields are built the first time the editor needs them, in a fraction of a second each.

WHY INSIDE THE EDITOR. The editor caches a built mesh under a different key from a headless run.
Measured: 40 meshes a headless run had built, loaded in the editor, were all built again; loaded
headless, none was. So meshes only built headlessly (the split made all of them that way) are built
again by the editor the first time it draws them. In the play session where buildings blinked it
was building 759 of them as the drone flew, and a mesh draws nothing until it is built. Loading
every building mesh here, in the editor, builds them once, ahead of play.

WHY COARSER DISTANCE FIELDS. Every building mesh had a full 126 cubed distance field, the most a
mesh can have: 2 to 14 s to build and about 1.7 MB each, for buildings of 22 triangles on average.
Lumen here uses hardware ray tracing (r.Lumen.HardwareRayTracing is on by default in 5.7, and
r.RayTracing=True), so mesh distance fields only serve the software fallback and distance field
shadows; a resolution scale of 0.1 keeps a coarse one for those, at a small part of the cost.

It loads a tile's meshes together, so they build in parallel, then sets each one's LOD 0
DistanceFieldResolutionScale to 0.1 (which rebuilds it; one already at 0.1 is left alone) and saves
the tile. It records the tiles done in Saved/MAirCorridor/mesh_settings_done.txt, so a run that
stops carries on (MAIR_FORCE=1 does them all again). MAIR_TILES=tile_a,tile_b limits it to those
tiles; MAIR_MAX_TILES=N stops after N tiles.
MAIR_DRY=1 reports one tile and changes nothing.
"""
import io
import os
import time

import unreal

MARK = "MAIRMESH"
ROOT = "/MAirCorridor/BuildingsSplit"
SCALE = float(os.environ.get("MAIR_DF_SCALE", "0.1"))
DRY = os.environ.get("MAIR_DRY") == "1"
PROJECT = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())
DONE = os.path.join(PROJECT, "Saved", "MAirCorridor", "mesh_settings_done.txt")

reg = unreal.AssetRegistryHelpers.get_asset_registry()
# The subsystem lives in the StaticMeshEditor module, which loads only when asked for outside the UI.
unreal.SystemLibrary.execute_console_command(None, "Module load StaticMeshEditor")
meshes_sub = unreal.get_editor_subsystem(unreal.StaticMeshEditorSubsystem)
if meshes_sub is None:
    raise RuntimeError("the StaticMeshEditorSubsystem is not available, even with its module loaded")


def say(text):
    unreal.log_warning("%s %s" % (MARK, text))


done = set()
if os.path.isfile(DONE) and os.environ.get("MAIR_FORCE") != "1":
    with io.open(DONE, encoding="utf-8") as f:
        done = set(l.strip() for l in f if l.strip())
reg.scan_paths_synchronous([ROOT], True)
tiles = sorted(set(str(a.package_path).rsplit("/", 1)[-1] for a in reg.get_assets_by_path(ROOT, recursive=True)
                   if str(a.asset_class_path.asset_name) == "StaticMesh"))
wanted = [t for t in os.environ.get("MAIR_TILES", "").split(",") if t]
if wanted:
    tiles = [t for t in tiles if t in wanted]
limit = int(os.environ.get("MAIR_MAX_TILES", "0") or 0)
say("%d tiles of building meshes; %d already done; distance field resolution scale %.2f" % (
    len(tiles), len(done & set(tiles)), SCALE))

here = changed_total = 0
for tile in tiles:
    if tile in done:
        continue
    started = time.time()
    assets = [a for a in reg.get_assets_by_path("%s/%s" % (ROOT, tile), recursive=False)
              if str(a.asset_class_path.asset_name) == "StaticMesh"]
    # All of them first: each starts building as it loads, and they build side by side.
    meshes = [unreal.load_asset(str(a.package_name)) for a in assets]
    loaded = time.time() - started
    changed = 0
    for mesh in meshes:
        settings = meshes_sub.get_lod_build_settings(mesh, 0)        # waits for this one to be built
        if abs(settings.get_editor_property("distance_field_resolution_scale") - SCALE) < 1e-4:
            continue
        changed += 1
        if DRY:
            continue
        settings.set_editor_property("distance_field_resolution_scale", SCALE)
        meshes_sub.set_lod_build_settings(mesh, 0, settings)         # rebuilds it, alongside the others
    if DRY:
        say("%s: %d of %d meshes would change (dry run), loaded and built in %.0f s" % (
            tile, changed, len(meshes), time.time() - started))
        break
    unreal.EditorLoadingAndSavingUtils.save_dirty_packages(False, True)
    with io.open(DONE, "a", encoding="utf-8") as f:
        f.write(tile + "\n")
    del meshes
    unreal.SystemLibrary.collect_garbage()
    changed_total += changed
    here += 1
    say("%s: %d of %d meshes rebuilt (loaded in %.0f s), in %.0f s" % (
        tile, changed, len(assets), loaded, time.time() - started))
    if limit and here >= limit:
        say("stopping after %d tiles (MAIR_MAX_TILES); run again to carry on" % here)
        break
say("finished: %d meshes rebuilt in %d tiles" % (changed_total, here))
