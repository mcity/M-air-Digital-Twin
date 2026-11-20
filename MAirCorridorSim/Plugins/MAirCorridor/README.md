# MAirCorridor

The M-Air corridor as an Unreal Engine 5.7 plugin, together with the toolchain that builds it: very
large Landscapes from any elevation data, aerial imagery aligned to them, surveyed and generated
vegetation, OpenStreetMap buildings, and the M-City photogrammetric scan streamed at runtime.

**One of two repositories.** This one is the plugin and its tools. The data the level is rebuilt
from (the landscape plan and heightmap, the aerial imagery, the building tiles and the Blender scenes
they came from, the tree and rock libraries, and the OpenStreetMap survey) is in
[MAirCorridor_Assets](https://github.com/sriceumich/MAirCorridor_Assets), in Git LFS. **[ASSEMBLY.md](ASSEMBLY.md) puts the two together**, step
by step, and says which file feeds which step.

Every module depends on stock Unreal only, and the Python tools depend only on common open-source
packages.

## What is here

| Path | What it is |
| --- | --- |
| [`Source/MAirCorridorScan`](Source/MAirCorridorScan) | Runtime module. `AMAirScanActor` streams the M-City scan tiles around the viewer |
| [`Source/MAirCorridorEditor`](Source/MAirCorridorEditor) | Editor module. The *Tools > M-Air Corridor* menu |
| [`Tools`](Tools) | Python downloaders and builders for elevation and imagery, **for any area**. Full guide in [`Tools/README.md`](Tools/README.md) |
| [`Content`](Content) | Building meshes and textures, tree and rock meshes, and the corridor level |
| [`AirSim`](AirSim) | A launcher that flies a Project AirSim drone over the terrain on the keyboard |
| [`run.cmd`](run.cmd) | `run` opens **MCity Digital Air Command**, a window that starts the editor and every tool. `run fly`, `run plan`, `run mission FILE` and `run geodata` go straight to one |
| [`ASSEMBLY.md`](ASSEMBLY.md) | **Assembling the corridor level** from this repository and [MAirCorridor_Assets](https://github.com/sriceumich/MAirCorridor_Assets) |
| [`PROVENANCE.md`](PROVENANCE.md) | Where every item came from, file by file, and where its source data is |
| [`CITATION.cff`](CITATION.cff) | Citation metadata (GitHub shows it as *Cite this repository*) |

## Quick start

1. Clone this repository with [Git LFS](https://git-lfs.com/) installed (the M-City scan is in
   LFS; without it the scan arrives as small pointer files) into your project as
   `Plugins/MAirCorridor`, and clone
   [MAirCorridor_Assets](https://github.com/sriceumich/MAirCorridor_Assets) with Git LFS to `MAirCorridor_Assets` beside the project folder, where the tools look by
   default ([ASSEMBLY.md](ASSEMBLY.md#1-get-both-repositories) has the commands and the variables for
   anywhere else).
2. Close the editor and build the editor target:

   ```
   "<UE>/Engine/Build/BatchFiles/Build.bat" <Project>Editor Win64 Development -Project="<path>.uproject" -WaitMutex
   ```

   Close the editor first: Live Coding cannot add a new module, and UBT refuses to build while the
   editor is running (*"Unable to build while Live Coding is active"*).
3. Open the editor. The tools are under *Tools > M-Air Corridor*; `M-City Scan` is in the Place Actors
   panel. To build the corridor level from the assets, follow [ASSEMBLY.md](ASSEMBLY.md) from step 3.

## Editor tools

**Build Unreal Landscape from Plan...** builds one or more stock `ALandscape` actors from a plan
written by [`Tools/build_landscape.py`](Tools/build_landscape.py). The builder cuts an area of any
size into segments, each read and reprojected on its own, so an elevation model far larger than
Unreal's own Landscape import can take becomes terrain without ever being loaded whole. Neighbouring
segments share their edge vertices exactly and one vertical range, so there are no seams. The
importer validates every segment's size and file before spawning anything.

**Place Corridor Trees and Rocks** imports a tree and rock mesh library and places it. The three
inputs (the scene JSON, the tree folder and the rock folder) are fixed paths in
[`MAirFoliagePlacer.cpp`](Source/MAirCorridorEditor/Private/MAirFoliagePlacer.cpp), overridable with
the `MAIRCORRIDOR_SCENE`, `MAIRCORRIDOR_TREES` and `MAIRCORRIDOR_ROCKS` environment variables; a
picker opens only for one that is not on disk. It places: surveyed
trees exactly where OpenStreetMap records them, and a density-driven scatter inside wood, scrub, park,
grass and farmland polygons. Every instance is traced onto the Landscape, which is the only surface
treated as ground: nothing is planted on a building roof, and a point under a crown already placed is
skipped, which thins the scatter rather than stacking trees. Placement uses a fixed random seed and is
instanced (one HISM per mesh).

**It is too heavy as placed, and two scripts fix that.** Measured in the corridor level: the placer
puts all 677,244 trees and rocks into one actor, `CorridorFoliage`, 65.8 by 21.4 km, so World
Partition can only ever load all of it; and the 36 tree models run from 30,000 to 857,000
triangles each with Nanite off and no cull distance, so every tree in view is drawn in full, in
every camera capture. The 100 building tiles are light (1.45 million triangles in all) but carry
about 90 material slots each, and as 100 merged meshes no single building can be moved or
deleted, so the level has them split into one actor per building (73,403), each dropped onto the
Landscape and kept in an outliner folder named after its tile: `Tools/unreal/split_buildings.py`,
run headless with the editor closed, as [ASSEMBLY.md](ASSEMBLY.md#5-buildings) step 5 describes.
Each building also carries its address, OpenStreetMap id, building type and use as actor tags:
real addresses where OpenStreetMap has them, estimates from the census street ranges and the
neighbours' addresses elsewhere, each saying which ([Tools/README.md](Tools/README.md#addresses)).
For the trees and rocks, run in the open editor's Python console, in this order:

| Script | What it does | Kept by |
| --- | --- | --- |
| `Tools/unreal/nanite_scene_meshes.py` | Nanite on for the 42 tree, 30 rock and 100 building tile meshes, with Preserve Area on the trees so woods do not thin out at a distance | Saving each mesh, which it does |
| `Tools/unreal/stream_foliage.py` | Splits `CorridorFoliage` into one actor per square kilometre (339 of them), each streamed by World Partition, copying every component's settings | Saving the level, which it leaves to you |

Both scripts have a dry run (`MAIR_DRY=1`), and both were dry run headless against the level:
172 meshes to convert, and the busiest square kilometre (14,104 instances) built in full.

**How far things load, and what stands in past that.** The level's one streaming partition,
MainGrid, loads 252 m cells within 768 m of the camera, and until now no actor had an HLOD layer,
so every HLOD build made nothing and past that range there was nothing at all. That was hidden
while the buildings were 100 merged tiles in 2 to 4 km cells; split into 73,403 buildings, each
existed only within 768 m of the drone, and they blinked in and out as it flew. Three scripts
fix it, run headless with the editor closed except the second, which runs inside the editor:

| Script | What it does |
| --- | --- |
| `Tools/unreal/corridor_streaming.py` | Gives the buildings a partition of their own, `Buildings` (512 m cells within 4 km), with an HLOD layer, `HLOD_Buildings`, standing in out to 7 km (each building is its own Nanite mesh, and the GPU's Nanite root pages cap how many can be resident; the script's header has the numbers); and gives the trees an HLOD layer, `HLOD_Trees`, out to 8 km, leaving their own range as it was. World Partition's partitions are not reachable from Python in UE 5.7, so this calls `UMAirStreamingLibrary` in this plugin's editor module |
| `Tools/unreal/building_mesh_settings.py` | Builds every building mesh once inside the editor, which caches built meshes under a different key from a headless run, so play mode no longer builds them as the drone flies; and cuts their distance fields from 126 cubed to a resolution scale of 0.1 (Lumen here uses hardware ray tracing) |
| the HLOD build | `WorldPartitionBuilderCommandlet -Builder=WorldPartitionHLODsBuilder`, headless and WITHOUT the GPU (`-nullrhi`). Not *Build > Build HLODs*: the editor runs the build with the GPU, every building mesh it loads takes a Nanite root page, and it stops with the pool full partway through |

Each script's header gives its command line.

**M-City Scan** (`AMAirScanActor`, Place Actors panel) streams the photogrammetric scan's `.ancm`
tiles around the viewer with levels of detail, texture downscaling and a load radius.

**For real time, use the Nanite scan instead.** The streamed scan builds its sections on the game
thread as the viewer moves, so it draws in slowly, and its coarser levels were made by merging
vertices without regard to where the photographs' pieces meet: measured on one tile, 52 to 71
percent of their triangles stretch across unrelated parts of a photograph, which shows as a
smeared patchwork beyond 150 m. The whole scan imported as one mesh (`Content/Scan/20M16`, 20
million triangles, Nanite on) has neither problem. `Tools/unreal/place_scan_mesh.py`, run in the
open editor's Python console, puts it in the level in place of the streamed actor:

```
exec(open(r"<project folder>/Plugins/MAirCorridor/Tools/unreal/place_scan_mesh.py").read())
```

It makes one unlit photo material per photograph from `M_MCityScan`, turns on complex collision so
the drone and the range sensors meet the surface, places the mesh, and removes the streamed actor
after logging its settings. The level is left unsaved, to keep or throw away. The mesh's transform
was fitted from the data: the tiles carry the OBJ's vertex colours, so vertices whose colour is
unique in both were paired. OBJ to tiles is an affine to 1 mm; onto the level it is a rotation of
1.81391 degrees (the UTM grid convergence) and a scale of 100.02, which an actor transform holds to
within 3.5 cm of where the streamed scan puts the same points.

## Flight control

A mission is declared as airspace before it flies, checked against everything else in the sky, and
watched while it flies, with a defined response when it stops doing what it declared. The model is
ASTM F3548's, as the OpenUTM project's [Flight Blender](https://github.com/openutm/flight-blender)
implements it:

- **Declared airspace.** Each mission becomes 4D volumes: a shape, an altitude band and a time
  window per leg, plus the departure and the landing. Conformance is a yes or no, inside the
  declared volume at the declared time, rather than a distance off a line.
- **A lifecycle.** Accepted, Activated, Nonconforming, Contingent, Ended. Leaving the volumes for
  too long, or going silent for 15 s, makes the operation Contingent, and the runner holds and
  lands, lands, returns home, or carries on, as the mission says.
- **A strategic check.** Volumes are compared with geofences (GeoJSON, or ED-269 converted) and
  with other scheduled operations, as true shapes in metres. A conflict rejects the operation, in
  red in the planner as the route is drawn.
- **Real heights.** GPS, ADS-B and F3548 use the WGS84 ellipsoid and the landscape uses NAVD88.
  NOAA's GEOID18 converts between them, and refuses rather than silently returning zero when it
  cannot.
- **A traffic feed that admits when it has failed**, rather than showing an empty sky.

All of it is testable with no simulator: `Tools/tests` flies the control loop against a stand-in
drone. See [Flight control](Tools/README.md#flight-control), and
[On a new machine](Tools/README.md#on-a-new-machine) before running anything elsewhere.

## Live air traffic

**M-Air Live Traffic** (`AMAirTrafficActor`, Place Actors panel) flies the real aircraft overhead in
the level, read from a snapshot that `Tools/adsb.py` fetches from the OpenSky Network and keeps up
to date. Assign your own meshes per size class and anything unassigned falls back to a shape scaled
to the right wingspan. The flight planner draws the same traffic on its map and says which of it is
too close to the planned route, horizontally and vertically. See
[Live air traffic](Tools/README.md#live-air-traffic).

## Flight planning

**MCity Digital Air Command** (`run`) is the way in: it opens the editor and every tool, and shows whether the editor is running.
Its flight planner (`run plan`) draws automated flights, and watches them: while a mission flies it
draws the drone and the path it actually took against the planned one, and reads out how far off
the line it is. Cameras can be saved as video or frames and sensor streams written to file.
Flights draw: named waypoints placed on a map, each
with a height that is either above the ground beneath it or above sea level, a speed and a hold.
Press Fly and the drone takes off, flies them and lands. Missions are JSON holding longitude and
latitude, so they outlive a landscape rebuild, and `run mission FILE` flies one with no window.
See [`Tools/README.md`](Tools/README.md#flight-planning).

**Two drones, and why.** `scene_mcity.jsonc` flies Project AirSim's own sample drone, whose GPS,
barometer and magnetometer ship switched off, with no lidar. A sensor that is not enabled is never
updated by the simulator and publishes nothing, which is fine for flying and useless for collecting
data. `scene_mcity_sensors.jsonc` flies `robot_mcity_sensors.jsonc` instead: the same flight model,
with colour, depth, segmentation and surface normal cameras, IMU, GPS, barometer, magnetometer,
airspeed, battery, a 16 channel lidar and a distance sensor all on. A mission names its scene, so
the light drone stays available for keyboard flying.

**Recording a flight, and comparing it with a real one.** One switch records everything the drone
carries: every camera as video or as lossless frames, every sensor, the camera metadata beside each
image stream, and the aircraft's own state, each stamped with the simulator's clock and described by
a manifest that also writes down the projection, the landscape origin and the NED law. That is
enough to work in both directions: a simulated flight becomes material for something that will fly
for real, and a flight flown for real becomes a mission that can be flown here over the same ground
and then measured against it. See
[Sim to real, and real to sim](Tools/README.md#sim-to-real-and-real-to-sim).

## Geodata tools

| Tool | Purpose |
| --- | --- |
| `download_3dep.py` | USGS 3DEP elevation, 1 m lidar to 30 m, anywhere in the United States |
| `download_copernicus_dem.py` | Copernicus 30 m or 90 m elevation, anywhere on Earth |
| `build_landscape.py` | **Any** georeferenced elevation raster (ASTER GDEM, SRTM, national lidar, your own survey) into Unreal Landscape heightmaps |
| `download_naip.py` | USDA NAIP aerial imagery, tiled and aligned to a Landscape |

No accounts or API keys are needed. [`Tools/README.md`](Tools/README.md) covers the whole workflow:
defining an area, choosing and combining elevation sources, using data from anywhere, importing,
putting imagery on the terrain, making buildings with blosm, the vegetation input formats, and the
exact commands that reproduce this corridor.

## What is not in this repository

The level comes with everything placed in it: the corridor Landscape and every actor in the level
(`Content/__ExternalActors__`), the per-building meshes they place (`Content/BuildingsSplit`,
73,403 of them), the merged building tiles and their textures (`Content/Buildings`), the tree and
rock meshes (`Content/Vegetation`), the terrain materials and tiles (`Content/AnchorBaked`), and
the M-City scan (`Content/Scan` and `Content/Scans/mcity_scan_mesh`, about 2.9 GB in Git LFS).
One thing is left out; [`.gitignore`](.gitignore) names it.

| Excluded content | How to get it back |
| --- | --- |
| The four aerial photographs the terrain materials sample (`Content/AnchorBaked/mcity05_east`, `mcity05_west`, `mcity_066m_naip`, `mcity_rect_07m_naip`, 3.7 to 6.8 GB each, past what GitHub holds even in Git LFS) | The imagery sheets are in MAirCorridor_Assets (`naip_rect_066m/`); importing them is [ASSEMBLY.md](ASSEMBLY.md#4-aerial-imagery) step 4. For another area, `Tools/download_naip.py` |

**The source data the level is rebuilt from is in
[MAirCorridor_Assets](https://github.com/sriceumich/MAirCorridor_Assets)**, in Git LFS (about
9.0 GB): the landscape plan and heightmap, the aerial imagery, the 100 baked building tiles, their
placement, the Blender scenes they were baked from and their textures upscaled to 1024 px, the tree and rock libraries, and the
OpenStreetMap survey that places the vegetation. Clone it to `MAirCorridor_Assets` beside the project folder (`<workspace>/MAirCorridor_Assets`, with the project at `<workspace>/<project>`), where the tools look by default, or point them
at it as [On a new machine](Tools/README.md#on-a-new-machine) describes:

```
git lfs install
git clone git@github.com:sriceumich/MAirCorridor_Assets.git <workspace>/MAirCorridor_Assets
```

## Credits

This project is built on the work and data of others:

- **Buildings** were modelled from OpenStreetMap data with [**blosm**](https://github.com/vvoovv/blosm)
  by Vladimir Elistratov (Blosm Pro 2.7.22), a Blender add-on for OpenStreetMap, terrain and 3D cities.
- **Building and vegetation placement data**: (c) [OpenStreetMap contributors](https://www.openstreetmap.org/copyright),
  Open Database License 1.0, via the [Geofabrik](https://download.geofabrik.de) Michigan extract.
- **Building textures** come from the blosm asset pack, which includes textures from
  [ambientCG](https://ambientcg.com) (CC0) and Duion. See [PROVENANCE.md](PROVENANCE.md#building-textures).
- **Trees** were generated with [**tree-gen**](https://github.com/friggog/tree-gen) by friggog, an
  implementation of the Weber and Penn parametric tree model for Blender.
- **Terrain**: U.S. Geological Survey, [3D Elevation Program](https://www.usgs.gov/3d-elevation-program).
- **Aerial imagery**: USDA Farm Service Agency, National Agriculture Imagery Program, served by USGS.
- **Drone simulation**: [Project AirSim](https://github.com/iamaisim/ProjectAirSim) (MIT License).
- Built for [Unreal Engine](https://www.unrealengine.com) 5.7.

## How to cite

If you use MAirCorridor, its tools or its pipeline in research or a publication, please cite it. GitHub's
*Cite this repository* button (from [`CITATION.cff`](CITATION.cff)) gives APA and BibTeX; or use:

> Sean Rice - University of Michigan. (2026). *MAirCorridor: an Unreal Engine plugin and geodata toolchain for the M-Air
> corridor* (Version 1.0.0) [Computer software]. https://github.com/sriceumich/MAirCorridor

```bibtex
@software{maircorridor_2026,
  author  = {{Sean Rice - University of Michigan}},
  title   = {{MAirCorridor}: an Unreal Engine plugin and geodata toolchain for the {M-Air} corridor},
  year    = {2026},
  version = {1.0.0},
  url     = {https://github.com/sriceumich/MAirCorridor}
}
```

When you publish images, video or derived data made with this project, also credit the underlying data
as its terms require:

> Elevation: U.S. Geological Survey 3D Elevation Program. Imagery: USDA National Agriculture Imagery
> Program. Buildings: (c) OpenStreetMap contributors, modelled with blosm.

Data you download yourself with the tools carries its own attribution; see
[Data licences and attribution](Tools/README.md#12-data-licences-and-attribution).

## License

OpenStreetMap-derived content is under the ODbL, and the building textures are under the terms of
their sources. [PROVENANCE.md](PROVENANCE.md) records the source and terms of every item, including
those still to be confirmed.
