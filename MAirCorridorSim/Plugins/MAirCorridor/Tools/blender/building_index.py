"""building_index.py - list every building in the baked building tiles: its name, pivot and bounds.

Run with Blender, headless:

    blender --background --factory-startup --python Tools/blender/building_index.py -- <tiles folder> <out folder> [tile ...]

<tiles folder> is MAirCorridor_Assets' corridor_tiles_baked. One JSON per tile is written to
<out folder>, named after the tile. Naming tiles after the folders lists only those.

Each tile FBX holds every building as its own object (tile_+0004_+0000 holds 2,903), with its pivot
at a corner of its footprint at ground level and no rotation or scale. That is what lets the tiles be
split into one Unreal actor per building (Tools/unreal/split_buildings.py), each placed by its pivot.

Coordinates are the tile's own, in metres, in Blender's frame: X east, Y north, Z up, relative to the
tile's origin. Z is the height in the Blender scene, whose terrain is not the Landscape's, so the
Unreal side traces every building down onto the Landscape instead of using it.
"""
import glob
import json
import os
import sys

import bpy
from mathutils import Vector

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
if len(argv) < 2:
    raise SystemExit("usage: blender --background --python building_index.py -- <tiles> <out> [tile ...]")
tiles_dir, out_dir, only = argv[0], argv[1], set(argv[2:])
os.makedirs(out_dir, exist_ok=True)

for path in sorted(glob.glob(os.path.join(tiles_dir, "*.fbx"))):
    tile = os.path.splitext(os.path.basename(path))[0]
    if only and tile not in only:
        continue
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.fbx(filepath=path)
    rows = []
    for o in bpy.data.objects:
        if o.type != "MESH":
            continue
        corners = [o.matrix_world @ Vector(c) for c in o.bound_box]
        lo = [min(c[i] for c in corners) for i in range(3)]
        hi = [max(c[i] for c in corners) for i in range(3)]
        rows.append({
            "name": o.name,
            "pivot": [round(v, 4) for v in o.matrix_world.translation],
            "min": [round(v, 4) for v in lo],
            "max": [round(v, 4) for v in hi],
            "triangles": sum(len(p.vertices) - 2 for p in o.data.polygons),
            "materials": [s.material.name for s in o.material_slots if s.material],
        })
    out = os.path.join(out_dir, tile + ".json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump({"tile": tile, "source": os.path.basename(path),
                   "frame": "metres, Blender frame: X east, Y north, Z up, relative to the tile's "
                            "origin; pivot is the object's origin, a footprint corner at its base",
                   "buildings": rows}, f, indent=0)
    print("BUILDINGINDEX %s: %d buildings -> %s" % (tile, len(rows), out))
