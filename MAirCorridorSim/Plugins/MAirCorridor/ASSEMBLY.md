# Assembling the corridor level

The M-Air corridor is two repositories. This one holds the plugin and the tools that build and fly
the level; [MAirCorridor_Assets](https://github.com/sriceumich/MAirCorridor_Assets) holds the source
data those tools read. Neither is complete without the other.

| Repository | What it holds | Size |
| --- | --- | --- |
| [MAirCorridor](https://github.com/sriceumich/MAirCorridor) (this one) | The Unreal plugin (code, editor tools), the Python tools, the flight tools, and the finished level: the Landscape and every actor placed in it (`Content/__ExternalActors__`), the 73,403 per-building meshes (`Content/BuildingsSplit`), building tiles and textures, tree and rock meshes, the terrain materials, and the M-City scan with its materials (the scan in Git LFS) | About 8 GB |
| [MAirCorridor_Assets](https://github.com/sriceumich/MAirCorridor_Assets) | The data the level is rebuilt from, in Git LFS: the landscape plan and heightmap, the aerial imagery, the building tiles and their placement, the Blender building scenes and their upscaled textures, the tree and rock libraries, and the OpenStreetMap survey that places the vegetation | About 9.0 GB |

**You do not need to rebuild the level to use it.** A clone of this repository opens
`/MAirCorridor/Scene/CorridorTerrain` with the terrain, buildings, trees and the M-City scan in
place. One thing is missing from it, and step 4 puts it back:

- **The four aerial photographs** the terrain materials sample (3.7 to 6.8 GB each, past what
  GitHub holds). Without them the terrain renders untextured. Step 4 imports them from the assets.

The M-City photogrammetric scan is in this repository, in Git LFS, so clone it with Git LFS
installed. Who flew the survey and who holds the rights to it is not recorded; see
[PROVENANCE.md](PROVENANCE.md#m-city-photogrammetric-scan).

The rest of this guide, steps 3 to 8, rebuilds the level from the assets: for another area, after
the source data changes, or to check how it was made. **Terrain derived from the NEXTMap DSM** is
in neither repository; it is commercially licensed and the level does not use it.

## What you need

- Unreal Engine 5.7 and Visual Studio to build a C++ plugin.
- [Project AirSim](https://github.com/iamaisim/ProjectAirSim) built for 5.7, its plugin in the
  project, and its Python client (the flight tools look for it at `ProjectAirSim` beside the project folder, or
  `PROJECTAIRSIM_ROOT`).
- [Git LFS](https://git-lfs.com/), installed before cloning the assets.
- Python 3.10 with this repository's [`Tools/requirements.txt`](Tools/requirements.txt).

## 1. Get both repositories

```
cd <project folder>/Plugins
git clone git@github.com:sriceumich/MAirCorridor.git MAirCorridor

git lfs install
git clone git@github.com:sriceumich/MAirCorridor_Assets.git <workspace>/MAirCorridor_Assets
```

`<workspace>/MAirCorridor_Assets`, beside the project folder, is where every tool looks by default. Cloned anywhere else, point them at it:

| Variable | Set it to |
| --- | --- |
| `MAIRCORRIDOR_PLAN` | `<assets>/ue_rect_3m/mcity_rect_3m.json` |
| `MAIRCORRIDOR_IMAGERY` | `<assets>/naip_rect_066m/mcity_066m_naip.json` |
| `MAIRCORRIDOR_SCENE` | `<assets>/corridor_scene.json` |
| `MAIRCORRIDOR_TREES` | `<assets>/corridor_trees` |
| `MAIRCORRIDOR_ROCKS` | `<assets>/corridor_rocks` |

The editor tools also ask for a file when their default is not on disk.

## 2. Build the plugin

Close the editor, then:

```
"<UE>/Engine/Build/BatchFiles/Build.bat" <Project>Editor Win64 Development -Project="<path>.uproject" -WaitMutex
```

Open the editor and the level `/MAirCorridor/Scene/CorridorTerrain`. It opens with everything
placed in it. To use it as it is, do step 4 for the imagery and go to step 9. To rebuild it from the assets, start from an empty level and follow steps 3 to 8.

## 3. Terrain

*Tools > M-Air Corridor > Build Unreal Landscape from Plan...*, and pick
[`ue_rect_3m/mcity_rect_3m.json`](https://github.com/sriceumich/MAirCorridor_Assets/tree/main/ue_rect_3m).
It builds the 65.8 by 21.4 km Landscape from its 3 m heightmap (21931 by 7141 vertices).

**Then move the Landscape to Z 0.** The plan places it at Z 23599.85 cm, which is its elevation in
centimetres; the shipped level has it at Z 0, and everything in this repository is measured against
that: [`Tools/level.json`](Tools/level.json), which the flight tools use to turn heights into Unreal
coordinates, and the scan's placement. If you keep a different height instead, run
`Tools/unreal/measure_level.py` (step 8) so the flight tools know.

## 4. Aerial imagery

The Landscape is draped with the 0.66 m NAIP imagery in
[`naip_rect_066m/`](https://github.com/sriceumich/MAirCorridor_Assets/tree/main/naip_rect_066m):

1. Import `mcity_066m_naip.1001.png` as a UDIM virtual texture; Unreal gathers the other 13 sheets.
2. Make a Landscape material that samples it by world position,
   `UV = (WorldXY - (UVOriginX, UVOriginY)) * (UVScaleX, UVScaleY)`, with those four as scalar
   parameters, and assign it to the Landscape. [Tools/README.md, section 8](Tools/README.md#8-put-the-imagery-on-the-landscape)
   explains the frame and the north-south flip to watch for.
3. *Tools > M-Air Corridor > Fix Imagery Scale from Index* reads
   `naip_rect_066m/mcity_066m_naip.json` and sets the four parameters from it. It works out from the
   material graph whether the scale is per metre or per centimetre, which is the mistake it exists
   to prevent.

`naip_rect_3m/` holds the same imagery at 3 m, for a lighter drape.

## 5. Buildings

The level has one actor per building, 73,403 of them, each a Nanite mesh standing on the
Landscape, in outliner folders `Buildings/<tile>` that say which of the 100 building tiles it came
from. Any one of them can be deleted on its own.

They come from the tile FBX files in
[`corridor_tiles_baked/`](https://github.com/sriceumich/MAirCorridor_Assets/tree/main/corridor_tiles_baked),
which hold every building as its own object with its pivot at a corner of its footprint at ground
level, and from the 100 merged tile meshes and their materials already in this repository, in
[`Content/Buildings`](Content/Buildings). Three steps, the last two headless with the editor
closed. Set `MAIRCORRIDOR_ASSETS` to the assets folder if it is not `MAirCorridor_Assets` beside the project folder.

1. **Index the tiles** with Blender. One JSON per tile: each building's name, pivot, bounds and
   materials.

   ```
   blender --background --factory-startup --python Tools/blender/building_index.py -- <assets folder>/corridor_tiles_baked <project folder>/Saved/MAirCorridor/building_index
   ```

2. **Place the 100 merged tiles** where the shipped level had them, from
   [`Tools/building_tiles_placement.json`](Tools/building_tiles_placement.json), by running the
   split tool with `MAIR_RESTORE=1` set:

   ```
   UnrealEditor-Cmd.exe <project>.uproject -run=pythonscript -script=<project folder>/Plugins/MAirCorridor/Tools/unreal/split_buildings.py "-EnablePlugins=PythonScriptPlugin,EditorScriptingUtilities,Interchange" -unattended -nullrhi
   ```

3. **Split them**: the same command without `MAIR_RESTORE`. Each tile's FBX is imported as one mesh
   per building into `Content/BuildingsSplit/<tile>`, with the tile's own material instances. Each
   building is placed at the merged tile's position plus its pivot, so nothing moves sideways, then
   dropped onto the Landscape: rays from 100 m above its top at the four footprint corners and the
   centre, hitting only the Landscape, and its base goes to the lowest hit so no corner floats on a
   slope. A hit more than 10 m below the median of the five is a hole in the ground model under
   one corner, not a slope, and is left out (six buildings in the corridor). Then the merged tile
   is removed. A tile is only removed when every one of its buildings stands in its place;
   otherwise it is left as it was and the run says so.

   One editor process slows as the buildings pile up in memory (0.05 s a building at the start,
   0.17 s sixteen tiles later), so run it in rounds: with `MAIR_MAX_TILES=8` set it stops after
   eight tiles, and each run starts where the last stopped. Run it until it places nothing more;
   all 100 tiles took about two and a half hours here. If it ends with
   `FINISH WITH: ... --delete-pending`, run that with plain Python once Unreal has closed; it
   deletes the removed tiles' files the editor was still holding.

[`Tools/unreal/split_buildings.py`](Tools/unreal/split_buildings.py) says more, including a dry
run (`MAIR_DRY=1`), how to limit it to some tiles (`MAIR_TILES`), and how to drop buildings
already standing onto the Landscape again after it changes (`MAIR_REDROP`).
`corridor_tiles_baked/corridor_tiles.json` also places the tiles, relative to the Landscape and
without a height, but the shipped level's tiles sit about 26 m from it, so the recorded placement
is what step 2 uses.

**Addresses.** Every building's address, OpenStreetMap id, building type and use go onto its
actor as tags, from `building_addresses.json` in the assets: run
[`Tools/unreal/tag_building_addresses.py`](Tools/unreal/tag_building_addresses.py) the same way
as the split, with the editor closed. [Tools/README.md](Tools/README.md#addresses) says where
the addresses come from, how good the estimated ones are, and how to make them again.

To change the buildings themselves rather than place them, the rest of the chain is in the assets:
the 100 tile FBX files beside `corridor_tiles.json`, the Blender scene they were baked from
(`New Folder/corridor_new.blend`), its textures upscaled to 1024 px (`New Folder/corridor_new.fbm`,
the files `Content/Buildings` was imported from), and each building's position
(`corridor_placement.json`). [Tools/README.md, section 9](Tools/README.md#9-buildings-from-openstreetmap-with-blosm)
describes how they were made.

## 6. Vegetation

*Tools > M-Air Corridor > Place Corridor Trees and Rocks* reads
[`corridor_scene.json`](https://github.com/sriceumich/MAirCorridor_Assets/blob/main/corridor_scene.json)
(the surveyed trees and the areas to scatter in),
[`corridor_trees/`](https://github.com/sriceumich/MAirCorridor_Assets/tree/main/corridor_trees) and
[`corridor_rocks/`](https://github.com/sriceumich/MAirCorridor_Assets/tree/main/corridor_rocks),
and plants 677,244 trees and rocks onto the Landscape. Then, in the editor's Python console
(*Output Log*, switched from *Cmd* to *Python*), one at a time:

```
exec(open(r"<project folder>/Plugins/MAirCorridor/Tools/unreal/nanite_scene_meshes.py").read())
exec(open(r"<project folder>/Plugins/MAirCorridor/Tools/unreal/stream_foliage.py").read())
```

The first turns Nanite on for the tree, rock and building meshes (already on in this repository's
copies, so it only reports). The second splits the foliage into one actor per square kilometre so
World Partition streams it; save the level after it. [README.md](README.md#editor-tools) says why
both are needed.

## 7. The M-City scan

In this repository, in Git LFS: `Content/Scan` (the `20M` mesh as Unreal assets) and
`Content/Scans/mcity_scan_mesh` (the streamed tile set `AMAirScanActor` finds by default). If they
arrived as small pointer files, Git LFS was not installed for the clone: install it and run
`git lfs pull` in `Plugins/MAirCorridor`. To place the scan in a level again,
`Tools/unreal/place_scan_mesh.py` puts it in as one Nanite mesh at its measured position.

## 8. Labels, measurements and HLODs

```
exec(open(r"<project folder>/Plugins/MAirCorridor/Tools/unreal/label_segmentation.py").read())
```

writes the segmentation classes ([`Tools/segmentation.json`](Tools/segmentation.json)) into the
level's components. If the Landscape is not at Z 0, run `Tools/unreal/measure_level.py` headless
(its header says how) so [`Tools/level.json`](Tools/level.json) records where it is.

Then set up how far buildings and trees load and what stands in for them past that, and build
it: [`Tools/unreal/corridor_streaming.py`](Tools/unreal/corridor_streaming.py) headless,
[`Tools/unreal/building_mesh_settings.py`](Tools/unreal/building_mesh_settings.py) inside the
editor, and the HLOD build. Each header gives its command line, and
[README.md](README.md#editor-tools) says why. Without them the buildings exist only within
768 m of the camera and blink in and out as it moves.

## 9. Fly

`run` in the plugin folder opens **MCity Digital Air Command**: *Play* starts the level without the
editor, and the planner and flight tools take their ground from
[`ue_rect_3m/mcity_rect_3m.json`](https://github.com/sriceumich/MAirCorridor_Assets/tree/main/ue_rect_3m)
in the assets. [Tools/README.md](Tools/README.md) covers planning, flying, recording and releases.

## Which file feeds which step

| In MAirCorridor_Assets | Read by | Step |
| --- | --- | --- |
| `ue_rect_3m/` | *Build Unreal Landscape from Plan*; the planner and every flight tool | 3, 9 |
| `naip_rect_066m/`, `naip_rect_3m/` | The Landscape material, then *Fix Imagery Scale from Index* | 4 |
| `corridor_tiles_baked/` | `Tools/blender/building_index.py` and `Tools/unreal/split_buildings.py` | 5 |
| `corridor_placement.json`, `corridor_buildings.json`, `blender_georef.json` | Where each building stands; how the Blender scene was georeferenced | 5 |
| `New Folder/corridor_new.blend`, `New Folder/corridor_new.fbm/`, `corridor.blend` | Changing the buildings: the scenes and their upscaled textures | 5 |
| `corridor_scene.json`, `corridor_trees/`, `corridor_rocks/` | *Place Corridor Trees and Rocks* | 6 |

Where each of those came from, and under what terms, is in [PROVENANCE.md](PROVENANCE.md).
