"""building_osm_tags.py - each building's OpenStreetMap id and tags, from the blosm scene.

Run with Blender, headless, on the JANUARY blosm scene, corridor_new.blend of 26 January 2026
(1.27 GB; not in MAirCorridor_Assets, whose corridor_new.blend in New Folder is the September one).
Its output, corridor_osm_tags.json, is in the assets, so this is only needed to read the tags again:

    blender --background --factory-startup <January corridor_new.blend> --python Tools/blender/building_osm_tags.py -- <building index folder> <out json>

blosm writes every OpenStreetMap tag of a building, and its id, onto the Blender object it makes
(blosm/renderer/__init__.py, postRender). The January scene still has them: 146,980 building
objects, each with "id", "building" and whatever else OpenStreetMap had (addr:*, name, amenity,
shop, building:levels, ...). The September scene was rebuilt from an FBX export, which dropped
them all, but kept the object names, so a building's name in the level finds it here.

Only the buildings in <building index folder> (Tools/blender/building_index.py, one JSON per tile)
are written: the scene holds each building twice ("X" and "X.001"), and the level uses one of each
pair. Each match is checked by size, and the run says how many disagree (none did: all 73,403
matched to the millimetre, each to a different OpenStreetMap element).
"""
import glob
import json
import os
import sys

import bpy

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
if len(argv) != 2:
    raise SystemExit("usage: blender --background <January corridor_new.blend> --python building_osm_tags.py -- <index> <out>")
index_dir, out_path = argv

ours = {}
for path in sorted(glob.glob(os.path.join(index_dir, "*.json"))):
    with open(path, encoding="utf-8") as f:
        index = json.load(f)
    for b in index["buildings"]:
        ours[b["name"]] = (index["tile"], [b["max"][i] - b["min"][i] for i in range(3)])

rows, missing, untagged, size_off = {}, [], [], []
# bpy.data.objects.get(name) searches the whole list each time; with 147,000 objects, once.
objects = {o.name: o for o in bpy.data.objects}
for name, (tile, size) in sorted(ours.items()):
    o = objects.get(name)
    if o is None:
        missing.append(name)
        continue
    if "id" not in o.keys():
        untagged.append(name)
        continue
    if max(abs(a - b) for a, b in zip(size, o.dimensions)) > 0.01:
        size_off.append(name)
    tags = {k: str(o[k]) for k in o.keys() if not k.startswith("_")}
    rows[name] = {"tile": tile, "osm_id": tags.pop("id"), "tags": tags}

os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
with open(out_path, "w", encoding="utf-8") as f:
    json.dump({"WHAT": "Each building in the corridor level, by its name there, with the id and tags of the "
                       "OpenStreetMap element blosm made it from. OpenStreetMap data, (c) OpenStreetMap "
                       "contributors, under the Open Database License.",
               "source": os.path.basename(bpy.data.filepath),
               "count": len(rows), "buildings": rows}, f, ensure_ascii=False, indent=0)
print("BUILDINGOSM %d of %d buildings written to %s; %d not in the scene, %d without an OpenStreetMap id, "
      "%d whose size disagrees with the index" % (len(rows), len(ours), out_path, len(missing), len(untagged),
                                                  len(size_off)))
for label, names in (("not in the scene", missing), ("without an id", untagged), ("size disagrees", size_off)):
    if names:
        print("BUILDINGOSM %s, e.g. %s" % (label, names[:5]))
