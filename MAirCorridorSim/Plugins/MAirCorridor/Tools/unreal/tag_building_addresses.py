"""tag_building_addresses.py - write each building's address and OpenStreetMap identity onto its actor.

Headless, with the editor CLOSED (it edits the corridor level and saves as it goes):

    UnrealEditor-Cmd.exe <project>.uproject -run=pythonscript
        -script=<absolute path>/Tools/unreal/tag_building_addresses.py
        "-EnablePlugins=PythonScriptPlugin,EditorScriptingUtilities" -unattended -nullrhi

Reads building_addresses.json (Tools/building_addresses.py; MAIR_ADDRESSES, or MAirCorridor_Assets
via MAIRCORRIDOR_ASSETS, default MAirCorridor_Assets beside the project) and gives every building actor, beside its
"building" and "tile:<tile>" tags:

    osm:way/538579364                      the OpenStreetMap element it was made from
    address:2444 Lancashire Drive, Ann Arbor, MI 48105
    address_source:neighbours              how far to trust the address (Tools/building_addresses.py)
    building_type:house                    OpenStreetMap's building=*
    use:amenity=parking                    its amenity, shop, office, ... when OpenStreetMap has one

Tags are on the actor's Details panel under Actor > Tags, and any tool can read them. Running it
again replaces these tags and leaves the others alone. It works tile by tile, saving each, and
records the tiles done in Saved/MAirCorridor/address_tags_done.txt, so a run that stops carries on
where it left off (MAIR_FORCE=1 does every tile again). MAIR_MAX_TILES=N stops after N tiles, since
one editor process slows as it goes. MAIR_DRY=1 does one tile and saves nothing.
"""
import io
import json
import os
import time

import unreal

MARK = "MAIRADDR"
LEVEL = "/MAirCorridor/Scene/CorridorTerrain"
DRY = os.environ.get("MAIR_DRY") == "1"
PROJECT = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())
ASSETS = os.environ.get("MAIRCORRIDOR_ASSETS") or os.path.join(os.path.dirname(os.path.normpath(PROJECT)),
                                                              "MAirCorridor_Assets")
DATA = os.environ.get("MAIR_ADDRESSES", os.path.join(ASSETS, "building_addresses.json"))
DONE = os.path.join(PROJECT, "Saved", "MAirCorridor", "address_tags_done.txt")
CONTENT = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_plugins_dir()),
                       "MAirCorridor", "Content")
OURS = ("osm:", "address:", "address_source:", "building_type:", "use:")
USES = ("amenity", "shop", "office", "tourism", "leisure", "healthcare", "religion")

actors_sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
wp = unreal.WorldPartitionBlueprintLibrary


def say(text):
    unreal.log_warning("%s %s" % (MARK, text))


def actor_file(actor):
    name = actor.get_outermost().get_name()
    if not name.startswith("/MAirCorridor/"):
        return None
    return os.path.join(CONTENT, *name[len("/MAirCorridor/"):].split("/")) + ".uasset"


def wanted_tags(existing, rec):
    keep = [t for t in existing if not t.startswith(OURS)]
    add = ["osm:" + rec["osm"]]
    if rec.get("address"):
        add.append("address:" + rec["address"])
    add.append("address_source:" + rec["source"])
    tags = rec.get("osm_tags", {})
    if tags.get("building"):
        add.append("building_type:" + tags["building"])
    for k in USES:
        if tags.get(k):
            add.append("use:%s=%s" % (k, tags[k]))
            break
    return keep + add


with io.open(DATA, encoding="utf-8") as f:
    records = json.load(f)["buildings"]
done = set()
if os.path.isfile(DONE) and os.environ.get("MAIR_FORCE") != "1":
    with io.open(DONE, encoding="utf-8") as f:
        done = set(l.strip() for l in f if l.strip())

unreal.EditorLoadingAndSavingUtils.load_map(LEVEL)
big = unreal.Box(unreal.Vector(-1e9, -1e9, -1e9), unreal.Vector(1e9, 1e9, 1e9))
descs = wp.get_intersecting_actor_descs(big)
descs = descs[-1] if isinstance(descs, tuple) else descs
guid_of = {str(d.get_editor_property("label")): d.get_editor_property("guid") for d in descs}

by_tile = {}
for name, rec in records.items():
    by_tile.setdefault(rec["tile"], []).append(name)
limit = int(os.environ.get("MAIR_MAX_TILES", "0") or 0)
say("%d buildings with addresses in %d tiles; %d tiles already done%s" % (
    len(records), len(by_tile), len(done & set(by_tile)), " (dry run: one tile, nothing saved)" if DRY else ""))

tiles_here = tagged = missing = 0
for tile in sorted(by_tile):
    if tile in done:
        continue
    started = time.time()
    names = set(by_tile[tile])
    guids = [guid_of[n] for n in names if n in guid_of]
    missing += len(names) - len(guids)
    wp.load_actors(guids)
    actors = [a for a in actors_sub.get_all_level_actors() if a.get_actor_label() in names]
    changed, sample = 0, None
    for a in actors:
        existing = [str(t) for t in a.tags]
        want = wanted_tags(existing, records[a.get_actor_label()])
        if want != existing:
            # A change from Python does not mark the actor's package dirty, and a clean package
            # is not saved.
            a.modify()
            a.set_editor_property("tags", want)
            changed += 1
            sample = sample or a
    if not DRY:
        unreal.EditorLoadingAndSavingUtils.save_dirty_packages(True, True)
        if sample is not None:
            path = actor_file(sample)
            age = time.time() - os.path.getmtime(path) if path and os.path.isfile(path) else None
            if age is None or age > 120:
                say("%s: NOT SAVED: %s was not written; stopping" % (tile, path))
                break
        with io.open(DONE, "a", encoding="utf-8") as f:
            f.write(tile + "\n")
    else:
        for a in actors[:3]:
            say("  %s: %s" % (a.get_actor_label(), [str(t) for t in a.tags]))
    wp.unload_actors(guids)
    unreal.SystemLibrary.collect_garbage()
    tagged += changed
    tiles_here += 1
    say("%s: %d of %d buildings tagged (%d not in the level), in %.0f s" % (
        tile, changed, len(names), len(names) - len(guids), time.time() - started))
    if DRY or (limit and tiles_here >= limit):
        if limit and not DRY:
            say("stopping after %d tiles (MAIR_MAX_TILES); run again to carry on" % tiles_here)
        break
say("done: %d buildings tagged in %d tiles; %d buildings in the data not in the level" % (tagged, tiles_here, missing))
