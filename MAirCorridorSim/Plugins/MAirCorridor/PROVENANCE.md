# Provenance

Where every item in the MAirCorridor plugin came from, what was done to it, and under what terms.
It covers everything in this repository and also the derived content that is part of the plugin
but excluded from the repository for size.

Facts here were read from the files themselves: embedded import paths inside each `.uasset`,
the JSON sidecars written by each processing step, EXIF metadata and file headers. Where something
could not be established from the evidence it says **NOT RECORDED** rather than guessing.

A per-file table of every content file in the repository is at the end, in
[Appendix: every content file](#appendix-every-content-file).

## Summary

| Item | Source | Terms | In repo |
| --- | --- | --- | --- |
| C++ plugin code, Python tools, AirSim launcher | Written for this project | No licence stated | Yes |
| Terrain (Landscape) | USGS 3D Elevation Program (3DEP) 1/9 arc-second | Public domain | No (regenerate with `Tools/`) |
| Terrain under the buildings in Blender | SRTM 1 arc-second via blosm | Public domain | No (not carried into Unreal) |
| Aerial imagery | USDA National Agriculture Imagery Program (NAIP) via USGS | Public domain | No (regenerate with `Tools/`) |
| Building meshes | OpenStreetMap, modelled with blosm | OSM data: ODbL 1.0, attribution required | Yes |
| Building textures | blosm asset pack, which includes ambientCG and Duion textures | Mixed, see [Building textures](#building-textures) | Yes |
| Tree meshes | Generated with friggog/tree-gen | Output of a GPL-3 generator, no third-party assets | Yes |
| Rock meshes | Generated procedurally, vertex colour only | No third-party assets | Yes |
| Tree and area placement data | OpenStreetMap | ODbL 1.0, attribution required | No |
| Building addresses and OpenStreetMap ids | OpenStreetMap, and US Census Bureau TIGER/Line address ranges (2024 ADDRFEAT, Washtenaw and Wayne counties) | OSM: ODbL 1.0, attribution required, the address table a derived database under the same licence; TIGER/Line: public domain | No (MAirCorridor_Assets; regenerate with `Tools/building_addresses.py`) |
| M-City photogrammetric scan | senseFly S.O.D.A. aerial survey | **NOT RECORDED**, see [Scan](#m-city-photogrammetric-scan) | Yes (Git LFS) |
| Corridor boundary polygon | Project concept boundary | **NOT RECORDED** | Yes (`Tools/examples`) |

## Code

All C++ under `Source/`, all Python under `Tools/`, `AirSim/fly_mcity.py`, the scene configs under
`AirSim/sim_config/` and `run.cmd` are the work of Sean Rice. The runtime and editor modules began as part of his own
engine, developed on his own time, and were adapted and contributed for this project's use; the
tools and launcher were written for it. No licence is stated for them.

- The plugin targets Unreal Engine 5.7 and uses only engine modules. It references one piece of
  engine content by path, `/Engine/EngineDebugMaterials/VertexColorMaterial`, which is part of
  Unreal Engine and is not redistributed here.
- The flight control model in `Tools/airspace.py` and `Tools/geofences.py` (4D volumes, the
  operation lifecycle and its state names, conformance and telemetry checks, strategic
  deconfliction, ED-269 import) follows ASTM F3548 as implemented by the OpenUTM project's
  [Flight Blender](https://github.com/openutm/flight-blender), Apache License 2.0. It was used as
  a design reference: **no code from it is included**. Where this differs on purpose (metric
  buffers, true shape intersection) the source says so.
- `Tools/geoid.py` uses NOAA's GEOID18 grid (public domain, United States Government work),
  fetched at run time from the PROJ project's CDN, `cdn.proj.org`. The grid is **not**
  redistributed here.
- `Tools/geofences/example_ann_arbor_airport.geojson` is an illustrative circle drawn for this
  project around an approximate airport position. It is **not airspace data** and is labelled so.
- `Content/Materials/M_MCityScan` (unlit) and `M_MCityScanLit` were built for this project by
  `Tools/unreal/build_scan_materials.py`, to draw the scan's own photographs: a `BaseColor`
  texture parameter the scan component binds each photograph to at run time, with the engine's
  `DefaultDiffuse` as its default so they compile on a machine without the scan.
- `Content/Materials/ScanPhotos/MI_MCityScan_*` are instances of `M_MCityScan`, one per
  photograph of the scan, made by `Tools/unreal/place_scan_mesh.py`. They add no content of their
  own: each names one of the scan's imported photographs (`Content/Scan/TEX_20M*`).
- `MAirCorridorTraffic` reads a traffic snapshot written by `Tools/adsb.py`. The aircraft states
  come from the [OpenSky Network](https://opensky-network.org/) REST API, which is free for
  non-commercial use under their terms of use; an account's own credentials are not part of this
  repository and no aircraft data is redistributed here. The stand in shapes are
  `/Engine/BasicShapes/Sphere` and `/Engine/BasicShapes/Cylinder`, which are part of Unreal Engine
  and are referenced rather than redistributed.
- The landscape import sequence follows Unreal's own
  `LandscapeEditorDetailCustomization_NewLandscape.cpp`, as noted in the source.
- `AirSim/` drives [Project AirSim](https://github.com/iamaisim/ProjectAirSim) (MIT License, IAMAI
  Simulations). Project AirSim itself is a separate download and is not included.
- `AirSim/sim_config/robot_mcity_sensors.jsonc` is **derived from two of Project AirSim's own
  sample robot configs**: the flight model, links, joints, controller and actuators are those of
  `robot_quadrotor_fastphysics_weather.jsonc`, and the sensor parameters are those of
  `robot_quadrotor_fastphysics_sensors.jsonc`, with the sensors enabled and the cameras changed.
  Both samples are MIT licensed by IAMAI Simulations. The camera and sensor selection is ours.

## Terrain

**Source.** USGS 3D Elevation Program, bare-earth lidar-derived DEMs. Public domain.
Distributed by The National Map, https://www.usgs.gov/3d-elevation-program.

**The Landscape in the corridor level** (`Scene/CorridorTerrain`, actors under
`__ExternalActors__`, excluded from the repository):

| Property | Value |
| --- | --- |
| Product | USGS 3DEP 1/9 arc-second (about 3.4 m north-south by 2.5 m east-west at this latitude) |
| Source tiles (10) | `ned19_n42x25_w083x25_mi_wayneco_2009.img`, `ned19_n42x25_w083x50_mi_wayneco_2009.img`, `ned19_n42x25_w083x75_mi_washtenawco_2009.img`, `ned19_n42x25_w083x75_mi_wayneco_2009.img`, `ned19_n42x25_w084x00_mi_washtenawco_2009.img`, `ned19_n42x50_w083x25_mi_wayneco_2009.img`, `ned19_n42x50_w083x50_mi_wayneco_2009.img`, `ned19_n42x50_w083x75_mi_washtenawco_2009.img`, `ned19_n42x50_w083x75_mi_wayneco_2009.img`, `ned19_n42x50_w084x00_mi_washtenawco_2009.img` |
| Processing | Reprojected and bilinearly resampled onto a square 3 m grid |
| Projection | EPSG:26917 (NAD83 / UTM zone 17N), north-west corner 267907 E, 4697571 N |
| Extent | 65.28 km by 21.18 km (UTM bounds 267907, 4676390, 333186, 4697571) |
| Heightmap | 21931 by 7141 vertices, 602 components (255 quads, 2 sections), World Partition grid 4 |
| Elevation | 130.44 m to 341.56 m; decode `metres = (H - 32768) * 100 / 12800 + 235.998497` |
| Coverage | 149,068,926 measured cells (97.0%); gaps filled at the minimum elevation |

The Landscape's import source is recorded inside the level's landscape actors as
`ue_rect_3m/mcity_rect_3m.r16`, the heightmap described above. No other elevation data was used
to build the Landscape.

**Source files:** [`ue_rect_3m/`](https://github.com/sriceumich/MAirCorridor_Assets/tree/main/ue_rect_3m) in MAirCorridor_Assets (the plan, the
heightmap and its record of the elevation tiles). Assembled by [ASSEMBLY.md](ASSEMBLY.md#3-terrain)
step 3.

**Terrain in the Blender building scene.** blosm fetched its own terrain for the corridor, the
SRTM 1 arc-second tile `N42W084.hgt` (NASA Shuttle Radar Topography Mission, public domain), and
stood the buildings on it while they were modelled. None of those heights reached Unreal: every
building is traced down onto the USGS Landscape when placed. blosm's satellite overlay (Mapbox)
was used only for previewing in Blender and appears in no plugin content.

**High-resolution commercial elevation, NOT used for the terrain.** A NEXTMap One 1 m DSM covering
the corridor (36 tiles, Intermap Technologies, commercially licensed) is on the source machine.
It is not used for the Landscape and nothing in this repository is derived from it. Two items of
the plugin's EXCLUDED derived content do depend on it, and neither may be redistributed under the
NEXTMap licence terms without checking them:

- Baked 1 m terrain meshes of the corridor (61501 by 25731 px, EPSG:5070), with a 32 m surround
  from USGS 3DEP 1/3 arc-second (`USGS_13_n43w084.tif`) whose cut-out follows that footprint.
  The corridor level does not reference either.
- A 4 m ground model: NEXTMap cells classified as ground by comparison with USGS 3DEP 1/3
  arc-second bare earth, averaged to 4 m. Used only to measure the scan's vertical offset. See [Scan](#m-city-photogrammetric-scan).

The only baked asset the corridor level references is the 0.66 m imagery material
(`M_mcity_066m_naip`), which is NAIP.

## Aerial imagery

**Source.** USDA National Agriculture Imagery Program (NAIP), natural colour, native 0.30 m,
served by the USGS `USGSNAIPPlus` ImageServer (`exportImage`). Public domain. Downloaded
4-5 September 2026 (re-cut on 6 September); the service returns the most recent NAIP flight for each location, and the
flight year was not recorded.

**Content** (excluded from the repository): imagery textures at 0.5 m (east and west sheets),
0.66 m and 0.7 m per pixel, each in EPSG:26917 aligned to the Landscape's north-west corner, plus
the landscape drape materials that place them by world position.

- The 0.5 m sheets were fetched as 2048 by 2048 px requests (1,566 of them) and assembled.
- The 0.66 m set was re-cut on disk from the 0.5 m sheets with an area-averaging downsample. No
  pixel was refetched or invented.

**Source files:** [`naip_rect_066m/`](https://github.com/sriceumich/MAirCorridor_Assets/tree/main/naip_rect_066m) (the 0.66 m sheets the level
drapes) and [`naip_rect_3m/`](https://github.com/sriceumich/MAirCorridor_Assets/tree/main/naip_rect_3m) in MAirCorridor_Assets. Assembled by
[ASSEMBLY.md](ASSEMBLY.md#4-aerial-imagery) step 4.

## Buildings

**Geometry source.** OpenStreetMap building footprints, heights and roof tags.
(c) OpenStreetMap contributors, Open Database License 1.0, https://www.openstreetmap.org/copyright.
The meshes are a Produced Work under the ODbL and must carry that attribution.

**Pipeline.**

1. **Extract.** The Geofabrik Michigan extract `michigan-260122.osm.pbf`, OpenStreetMap data as
   of 2026-01-22T21:21:04Z (https://download.geofabrik.de/north-america/us/michigan.html), was cut
   to the corridor with osmconvert 0.8.8 on 24-26 January 2026 (`aircorridor.osm`, bounds
   42.2287707 N to 42.3625577 N, 83.7241283 W to 83.0158431 W, the corridor boundary's box) and
   filtered to buildings in Global Mapper.
2. **Model.** Imported into Blender 4.2+ with [blosm](https://github.com/vvoovv/blosm) Pro 2.7.22
   by Vladimir Elistratov (prochitecture; add-on code GPL-3.0), with local changes to its tiled
   export options. blosm extrudes footprints to their tagged heights, builds roofs, applies the
   tileable facade materials from its asset pack (version 2021.05.07) and UV-maps them. Exported as one FBX
   (`corridor_new.fbx`, with its textures in `corridor_new.fbm`).
3. **Georeference.** blosm places the scene in its own spherical transverse Mercator frame. That
   frame's origin was solved by matching 387 named OSM buildings to their meshes: origin
   42.28600037 N, 83.38201649 W, RMS 34.6 m. An earlier 12-landmark solve gave 55.0 m RMS and was
   superseded. Heights are not carried over; every building is traced down onto the Landscape
   when placed, because blosm's terrain is a different surface.
4. **Split and bake.** 146,981 mesh objects were grouped into 73,404 buildings, then baked into
   100 tile meshes (`tile_+XXXX_+YYYY`, including 3 sub-split tiles) with their textures.
5. **Import.** The 100 tile FBX files and their textures were imported into Unreal as
   `Content/Buildings`: 100 static meshes, 140 textures and 161 material instances.

**Source files**, in MAirCorridor_Assets: [`corridor_tiles_baked/`](https://github.com/sriceumich/MAirCorridor_Assets/tree/main/corridor_tiles_baked)
(the 100 tile FBX files and `corridor_tiles.json`, each tile's position); `corridor_placement.json`
(each building's position, from the 387-building solve) and `corridor_buildings.json` (the same
buildings in Blender's frame); `blender_georef.json` (the earlier 12-landmark solve); the Blender
scenes `New Folder/corridor_new.blend`, which the tiles were baked from, and `corridor.blend`; and
`New Folder/corridor_new.fbm`, the building textures upscaled to 1024 px, which are the files
`Content/Buildings` was imported from (all 140 of its building textures record that folder as their
source). Placed by [ASSEMBLY.md](ASSEMBLY.md#5-buildings) step 5.

### Building textures

Texture names record where each came from. blosm tints a base texture by a hex colour (the
`RRGGBB_` prefix) and bakes it. The blosm asset pack (version 2021.05.07) holds 53 texture files
from these libraries: CC0 Textures (`cc0textures_*`, 3 textures), Duion (`duion_*`, 7),
`rubberduck_220` (1), `scouser_roof_tiles_*` (3), and blosm's own facades (`pro_NNNN`, 9). Its
metadata (`asset_info.json`) names the files but records no author or licence for any of them.

| Family (count in repo) | Name pattern | Origin | Terms |
| --- | --- | --- | --- |
| ambientCG (42) | `cc0textures_bricks11_col` | CC0 Textures, now [ambientCG](https://ambientcg.com), bundled in the blosm asset pack | CC0 1.0, confirmed |
| Duion (156) | `duion_bricks_classic_02_D`, `duion_plaster_sprinkled_01_D` | Textures by Duion (duion.com), bundled in the blosm asset pack | **Not confirmed.** Verify before redistributing |
| blosm defaults (91) | `concrete`, `brick`, `metal`, `plaster`, `roof_tiles`, `gravel`, plain colours | Baked from asset pack textures; the base texture is not recorded in the name, and plain-colour entries use none | **Not confirmed.** Verify with prochitecture before redistributing |
| blosm Pro facades (12) | `pro_2157_exp`, `pro_6841_exp` and similar | blosm Pro asset pack | **Not confirmed.** Verify with prochitecture before redistributing |

The blosm asset pack is delivered to purchasers of Blosm Pro. Its redistribution terms are not
published on the add-on's page or in its documentation. Nothing about this repository changes
their terms.

## Trees

**Source.** 42 meshes generated with [friggog/tree-gen](https://github.com/friggog/tree-gen), a
Blender add-on implementing the Weber and Penn parametric tree model (GPL-3.0). The GPL covers the
generator; the meshes are its output and contain no third-party mesh or texture.

- **Species (3 variants each):** acer (maple), balsam fir, black oak, black tupelo, Cambridge oak,
  Douglas fir, European larch, hill cherry, Lombardy poplar, quaking aspen, sassafras, silver
  birch, small pine, weeping willow.
- **Content:** `Content/Vegetation/Trees`, imported from `corridor_trees/*.fbx` with parts
  combined into one mesh per file, no imported materials, and colour carried in vertex colours.
- **Source files:** [`corridor_trees/`](https://github.com/sriceumich/MAirCorridor_Assets/tree/main/corridor_trees) in MAirCorridor_Assets, with
  `trees.json`, the measured heights.

## Rocks

**Source.** 30 meshes generated procedurally for this project. They use no third-party mesh or
texture; colour is in vertex colours only.

- **Types (5 variants each):** cobble, glacial erratic, fieldstone, glacial boulder, limestone
  slab and outcrop, chosen to match southern Michigan's glacial till.
- **Content:** `Content/Vegetation/Rocks`, imported from `corridor_rocks/*.fbx`.
- **Source files:** [`corridor_rocks/`](https://github.com/sriceumich/MAirCorridor_Assets/tree/main/corridor_rocks) in MAirCorridor_Assets, with
  `rocks.json`.
  `RockVertexColour` is a material instance made in Unreal to display those vertex colours.

## Vegetation placement

Tree positions and planting areas come from OpenStreetMap (`aircorridor.osm`, see Buildings step 1),
(c) OpenStreetMap contributors, ODbL 1.0.

- **Surveyed trees:** 6,893 `natural=tree` points, placed exactly where OSM records them.
- **Planting areas:** wood, scrub, park, grass and farmland polygons, scattered at per-layer
  densities (stems per hectare) with a fixed random seed.
- **Placement:** every instance is traced onto the Landscape. The placed instances live in the
  level's actors, which are excluded from the repository.
- **Source file:** [`corridor_scene.json`](https://github.com/sriceumich/MAirCorridor_Assets/blob/main/corridor_scene.json) in
  MAirCorridor_Assets. Placed by [ASSEMBLY.md](ASSEMBLY.md#6-vegetation) step 6.

## M-City photogrammetric scan

**In the repository, in Git LFS.** Part of the plugin as `Content/Scan` (34 assets) and
`Content/Scans/mcity_scan_mesh` (597 files, the streamed tile set: 581 mesh tiles, 15 photographs
and `index.json`).

| Property | Value |
| --- | --- |
| Capture | 1,915 aerial photographs `IX-02-54615_0008_0001.JPG` onward, 5472 by 3648 px |
| Camera | senseFly S.O.D.A. (fixed-wing survey drone camera), body serial SI002001AA1K00033, 10.6 mm |
| Date | 10 July 2026 (EXIF DateTimeOriginal of the first frame) |
| Reconstruction | Camera poses exported in COLMAP format (1 camera, 1,915 images); meshes exported as OBJ with per-vertex colour by software identifying itself as `VirtualSandtable`: a master named `192M` (20.6 GB) and a 20 M triangle version named `20M` |
| Orthomosaic | Produced alongside (`M-city-ORTHO-*` GeoTIFF tiles, WGS84); not used in the plugin |
| In the plugin | The `20M` mesh as Unreal assets (17 meshes, 16 textures, 1 material), and the same mesh cut into 128 m tiles with 4 levels of detail: 10,008,270 vertices, 19,999,999 triangles |
| Georeference | Fitted to the 1,915 camera positions: scale 1.0000000000000604, rotation 0.0035 degrees, median residual 0.44 m (90th percentile 0.74 m, worst 1.87 m), origin 42.30034801 N, 83.69644808 W, 356.62 m |
| Vertical fit | Shifted -2.24 m, measured against a 4 m ground model derived from the NEXTMap DSM and USGS 3DEP (27,151 comparison blocks, residual MAD 0.79 m). Only the single offset value was taken from it |
| **Operator and owner** | **NOT RECORDED.** No photographer, owner or copyright is present in the EXIF or XMP. Confirm who flew the survey and who holds rights to it before distributing any of this content. |

## Corridor boundary

`Tools/examples/mair_corridor_boundary.kml` is the "M-air Corridor Concept 2025" polygon
(32 vertices, 83.72413 W to 83.01584 W, 42.22877 N to 42.36256 N). It was saved from Global Mapper
as `mcity corridor boundary.kmz` on 5 June 2026, from the "M-air Corridor Concept 2025" KMZ package
of 3 June 2026. Its author is **NOT RECORDED** in either file. It is included so the terrain and
imagery can be regenerated for exactly the same area.

## Level and scene assets

`Content/Scene/CorridorTerrain.umap`, `CorridorTerrain_HLOD0_Instancing.uasset`,
`HLOD_Buildings.uasset`, `HLOD_Trees.uasset` and the `__ExternalObjects__` packages were created
in the Unreal Editor for this project. They hold the World Partition level (with its streaming
partitions, set up by `Tools/unreal/corridor_streaming.py`), its HLOD layers and its outliner
folders: six folders made while the level was built, then `Buildings` and one `Buildings/<tile>`
per building tile, made by `Tools/unreal/split_buildings.py`, and the `HLOD_Buildings` and
`HLOD_Trees` folders the HLOD build put its 941 and 251 HLOD actors in. The actors that populate the
level (landscape proxies, buildings, foliage and HLODs) are in `__ExternalActors__`, which is
excluded from the repository and regenerated by the editor tools.

## Appendix: every content file

One row per content file in the repository. **Imported from** is the source file recorded inside
the asset at import (the directory is the processing step's output folder on the machine that
built it); blank means the asset was created inside Unreal rather than imported.

| File | Kind | Bytes | Imported from |
| --- | --- | ---: | --- |
| `__ExternalObjects__/Scene/CorridorTerrain/0/2Q/404CLAC19VC9DX53WABV4U.uasset` | Outliner folder (World Partition external object) | 2036 |  |
| `__ExternalObjects__/Scene/CorridorTerrain/0/CX/YZSU7GPZMVS1QCOJQ7LLCP.uasset` | Outliner folder (World Partition external object) | 1855 |  |
| `__ExternalObjects__/Scene/CorridorTerrain/0/F7/76ZMX6JXXSDX1CSJUU6BTM.uasset` | Outliner folder (World Partition external object) | 1981 |  |
| `__ExternalObjects__/Scene/CorridorTerrain/0/RK/7QRIDVZHRFUW61NA6TRCB4.uasset` | Outliner folder (World Partition external object) | 1961 |  |
| `__ExternalObjects__/Scene/CorridorTerrain/1/71/HPMWB9TWUXM75J78H4V2JC.uasset` | Outliner folder (World Partition external object) | 1961 |  |
| `__ExternalObjects__/Scene/CorridorTerrain/1/T8/6XJ4W2Y7I9QF3CPMVZD95T.uasset` | Outliner folder (World Partition external object) | 1961 |  |
| `__ExternalObjects__/Scene/CorridorTerrain/2/96/1JWY1MB6Q0OJ4Q7HCJP23N.uasset` | Outliner folder (World Partition external object) | 1961 |  |
| `__ExternalObjects__/Scene/CorridorTerrain/2/98/WEUX95XFD0TU6KOM3HJFL9.uasset` | Outliner folder (World Partition external object) | 1961 |  |
| `__ExternalObjects__/Scene/CorridorTerrain/2/AK/AB2GIJ48QG6NMLM39M00P9.uasset` | Outliner folder (World Partition external object) | 1961 |  |
| `__ExternalObjects__/Scene/CorridorTerrain/2/BI/WEL3IXLHSOAJFWWIIRQOEU.uasset` | Outliner folder (World Partition external object) | 1961 |  |
| `__ExternalObjects__/Scene/CorridorTerrain/2/L9/IE2414C4Z7LJWFZNNWZDCF.uasset` | Outliner folder (World Partition external object) | 1961 |  |
| `__ExternalObjects__/Scene/CorridorTerrain/2/LX/NRL9YJFKZLGMZQXN6J5QL9.uasset` | Outliner folder (World Partition external object) | 1961 |  |
| `__ExternalObjects__/Scene/CorridorTerrain/2/TP/IBD3C57RWQTTUNTTZ5CIK4.uasset` | Outliner folder (World Partition external object) | 1961 |  |
| `__ExternalObjects__/Scene/CorridorTerrain/2/WG/UUHOTICLXGVRQFPNMV41IF.uasset` | Outliner folder (World Partition external object) | 1961 |  |
| `__ExternalObjects__/Scene/CorridorTerrain/3/3V/RMHCE3SD7U88RBDALLA1HK.uasset` | Outliner folder (World Partition external object) | 1961 |  |
| `__ExternalObjects__/Scene/CorridorTerrain/3/4I/D63FB6QXE648WMQ67PVPKV.uasset` | Outliner folder (World Partition external object) | 1961 |  |
| `__ExternalObjects__/Scene/CorridorTerrain/3/4S/WBZGDYSTX94IWAESZIJFW8.uasset` | Outliner folder (World Partition external object) | 1961 |  |
| `__ExternalObjects__/Scene/CorridorTerrain/3/6Y/WWKTNVRYTNYWURCBCOU8X7.uasset` | Outliner folder (World Partition external object) | 1961 |  |
| `__ExternalObjects__/Scene/CorridorTerrain/3/8G/22IV95KK91Y60AUFFVS9WP.uasset` | Outliner folder (World Partition external object) | 1961 |  |
| `__ExternalObjects__/Scene/CorridorTerrain/3/B2/OELLIYZ8M9TBT9VSKAXJGU.uasset` | Outliner folder (World Partition external object) | 1961 |  |
| `__ExternalObjects__/Scene/CorridorTerrain/3/KT/NMZGRV0JC2HPJ0F8E5EQJQ.uasset` | Outliner folder (World Partition external object) | 1961 |  |
| `__ExternalObjects__/Scene/CorridorTerrain/3/KZ/AUWEPIGS0IG5MY9PYNJ5QP.uasset` | Outliner folder (World Partition external object) | 1961 |  |
| `__ExternalObjects__/Scene/CorridorTerrain/3/US/1NP5DNH720V9L6QNS6EM5E.uasset` | Outliner folder (World Partition external object) | 1961 |  |
| `__ExternalObjects__/Scene/CorridorTerrain/3/UY/DAPQJUEVM0DOXQDDSDX3PJ.uasset` | Outliner folder (World Partition external object) | 1912 |  |
| `__ExternalObjects__/Scene/CorridorTerrain/4/32/BLY2GJPE1A94JO74UC85GP.uasset` | Outliner folder (World Partition external object) | 1961 |  |
| `__ExternalObjects__/Scene/CorridorTerrain/4/7E/BSW62PCTE23OE4PWUOB92E.uasset` | Outliner folder (World Partition external object) | 1961 |  |
| `__ExternalObjects__/Scene/CorridorTerrain/4/LB/6FT1M3GF8J393HO8SMICVH.uasset` | Outliner folder (World Partition external object) | 1961 |  |
| `__ExternalObjects__/Scene/CorridorTerrain/4/T5/8B3BPE0207N2945EKFINXM.uasset` | Outliner folder (World Partition external object) | 1961 |  |
| `__ExternalObjects__/Scene/CorridorTerrain/4/W5/D5CD5W4KZC7BMK1OBC3TL5.uasset` | Outliner folder (World Partition external object) | 1961 |  |
| `__ExternalObjects__/Scene/CorridorTerrain/4/YQ/VLBQ56G94CBSSZKTRJMK8P.uasset` | Outliner folder (World Partition external object) | 1961 |  |
| `__ExternalObjects__/Scene/CorridorTerrain/5/07/YP03X773BXCYSQ13HYW1LN.uasset` | Outliner folder (World Partition external object) | 1961 |  |
| `__ExternalObjects__/Scene/CorridorTerrain/5/1Y/588912U2C5EO7LR7CQHZUH.uasset` | Outliner folder (World Partition external object) | 1961 |  |
| `__ExternalObjects__/Scene/CorridorTerrain/5/28/P48L8IHD8Z1XSJSQF145FD.uasset` | Outliner folder (World Partition external object) | 1853 |  |
| `__ExternalObjects__/Scene/CorridorTerrain/5/2M/G1GL0R79VN4YZTSZSX2KPV.uasset` | Outliner folder (World Partition external object) | 1961 |  |
| `__ExternalObjects__/Scene/CorridorTerrain/5/80/E73BHJX5WHWFJFDR2EQ0EB.uasset` | Outliner folder (World Partition external object) | 1961 |  |
| `__ExternalObjects__/Scene/CorridorTerrain/5/AM/6V0932FU0VLR2MNUQ1POVC.uasset` | Outliner folder (World Partition external object) | 1961 |  |
| `__ExternalObjects__/Scene/CorridorTerrain/5/GR/CCRU4GB0IE1U8UJJMUNFGB.uasset` | Outliner folder (World Partition external object) | 1961 |  |
| `__ExternalObjects__/Scene/CorridorTerrain/5/IB/3Q8NOSNVRILV6DFJ6AL5GE.uasset` | Outliner folder (World Partition external object) | 1857 |  |
| `__ExternalObjects__/Scene/CorridorTerrain/5/QX/U1FAY5FH17RBNMQCH8HBQR.uasset` | Outliner folder (World Partition external object) | 1961 |  |
| `__ExternalObjects__/Scene/CorridorTerrain/5/SG/HODTXJ19F5SJ4OOORO7GH7.uasset` | Outliner folder (World Partition external object) | 1961 |  |
| `__ExternalObjects__/Scene/CorridorTerrain/5/VL/DZMADKZ11YR1JWRDK7U3EJ.uasset` | Outliner folder (World Partition external object) | 1961 |  |
| `__ExternalObjects__/Scene/CorridorTerrain/5/X6/T2TEHHSB1Z9BL9FV2CRIW6.uasset` | Outliner folder (World Partition external object) | 1961 |  |
| `__ExternalObjects__/Scene/CorridorTerrain/5/YD/YECPG9GYJ91YRHAFQJKH5C.uasset` | Outliner folder (World Partition external object) | 1961 |  |
| `__ExternalObjects__/Scene/CorridorTerrain/6/3I/10BNM5YKN087COVL9UC48R.uasset` | Outliner folder (World Partition external object) | 1961 |  |
| `__ExternalObjects__/Scene/CorridorTerrain/6/4G/H6T3JU6870ETTG4MTWWR1X.uasset` | Outliner folder (World Partition external object) | 1961 |  |
| `__ExternalObjects__/Scene/CorridorTerrain/6/B7/IXIW0JDX6ZYJCA0NLBHM16.uasset` | Outliner folder (World Partition external object) | 1961 |  |
| `__ExternalObjects__/Scene/CorridorTerrain/6/ER/KQ7PJ1JX0FH7OT1FDNNTJI.uasset` | Outliner folder (World Partition external object) | 1981 |  |
| `__ExternalObjects__/Scene/CorridorTerrain/6/FT/ZV77VNS79VYNATY9J9K01I.uasset` | Outliner folder (World Partition external object) | 2004 |  |
| `__ExternalObjects__/Scene/CorridorTerrain/6/FV/YTELLDS258YQ033AD79GDM.uasset` | Outliner folder (World Partition external object) | 1961 |  |
| `__ExternalObjects__/Scene/CorridorTerrain/6/GC/8BKC7V7BSSRCSA8O1EJ88O.uasset` | Outliner folder (World Partition external object) | 1961 |  |
| `__ExternalObjects__/Scene/CorridorTerrain/6/NY/UGLFS52FH8V9O5PN6UZ5OA.uasset` | Outliner folder (World Partition external object) | 1961 |  |
| `__ExternalObjects__/Scene/CorridorTerrain/6/YL/8DM3ZTZW9BCT3YZ9Z7JNEP.uasset` | Outliner folder (World Partition external object) | 1961 |  |
| `__ExternalObjects__/Scene/CorridorTerrain/6/ZU/ICU8KLSCTQ8QS68MYAZ7AJ.uasset` | Outliner folder (World Partition external object) | 1961 |  |
| `__ExternalObjects__/Scene/CorridorTerrain/7/0D/X37C7WBBZZ9K9F1B856MWJ.uasset` | Outliner folder (World Partition external object) | 1961 |  |
| `__ExternalObjects__/Scene/CorridorTerrain/7/2C/060449416YH4AAY0KO2WT8.uasset` | Outliner folder (World Partition external object) | 1961 |  |
| `__ExternalObjects__/Scene/CorridorTerrain/7/7F/CGDQDMYMEHJYDHR4089M7T.uasset` | Outliner folder (World Partition external object) | 1961 |  |
| `__ExternalObjects__/Scene/CorridorTerrain/7/UH/NXY2P2Q9XEFKRVBVS3I3CM.uasset` | Outliner folder (World Partition external object) | 1961 |  |
| `__ExternalObjects__/Scene/CorridorTerrain/8/5P/QBV7HN0D5C6IKT892WJPEV.uasset` | Outliner folder (World Partition external object) | 1961 |  |
| `__ExternalObjects__/Scene/CorridorTerrain/8/5V/HAH5C6RR76K9D1P2KJ0EAY.uasset` | Outliner folder (World Partition external object) | 1961 |  |
| `__ExternalObjects__/Scene/CorridorTerrain/8/8C/LB5AFFT6I0NUMN84NSM8P1.uasset` | Outliner folder (World Partition external object) | 1961 |  |
| `__ExternalObjects__/Scene/CorridorTerrain/8/EY/S7NGJW6T9WQX4NOEKPJMGA.uasset` | Outliner folder (World Partition external object) | 1961 |  |
| `__ExternalObjects__/Scene/CorridorTerrain/8/H6/ISSMXZUFEY80GGFVY1ZXZN.uasset` | Outliner folder (World Partition external object) | 1961 |  |
| `__ExternalObjects__/Scene/CorridorTerrain/8/KT/O23MOCHYMJTJB6P8IZG2TJ.uasset` | Outliner folder (World Partition external object) | 2040 |  |
| `__ExternalObjects__/Scene/CorridorTerrain/8/NO/VOULHGAX738U0SPV3KUJ9O.uasset` | Outliner folder (World Partition external object) | 1961 |  |
| `__ExternalObjects__/Scene/CorridorTerrain/8/SS/PPEAK8GVAWRO2GJM4A56MA.uasset` | Outliner folder (World Partition external object) | 1961 |  |
| `__ExternalObjects__/Scene/CorridorTerrain/9/2W/M7WJXHMVZ87J1U42MPGQ43.uasset` | Outliner folder (World Partition external object) | 1961 |  |
| `__ExternalObjects__/Scene/CorridorTerrain/9/9Z/UBLED0I5YJN0LMXGWXUUOF.uasset` | Outliner folder (World Partition external object) | 1961 |  |
| `__ExternalObjects__/Scene/CorridorTerrain/9/F1/5FILTGTVKB2X8MUQFLQOA9.uasset` | Outliner folder (World Partition external object) | 1961 |  |
| `__ExternalObjects__/Scene/CorridorTerrain/9/F3/8VIVWYEC80FDOE4L8DHWWR.uasset` | Outliner folder (World Partition external object) | 1961 |  |
| `__ExternalObjects__/Scene/CorridorTerrain/9/FY/5MM6EYQOIW8SIP8XJ0VLFL.uasset` | Outliner folder (World Partition external object) | 1961 |  |
| `__ExternalObjects__/Scene/CorridorTerrain/9/H0/P5YNML97ZRMKURYFJVGQUR.uasset` | Outliner folder (World Partition external object) | 1961 |  |
| `__ExternalObjects__/Scene/CorridorTerrain/9/HL/9YRDJUC7IYWGGTBRR4KA1A.uasset` | Outliner folder (World Partition external object) | 1961 |  |
| `__ExternalObjects__/Scene/CorridorTerrain/9/JU/F5G35H97J3KFLUUEGBSHXP.uasset` | Outliner folder (World Partition external object) | 1961 |  |
| `__ExternalObjects__/Scene/CorridorTerrain/9/U7/8Y46ZLINGD6YW8CIRA3OJC.uasset` | Outliner folder (World Partition external object) | 1961 |  |
| `__ExternalObjects__/Scene/CorridorTerrain/A/14/RZ7CXJ1CDM3ZW1PCJ5PMSC.uasset` | Outliner folder (World Partition external object) | 1961 |  |
| `__ExternalObjects__/Scene/CorridorTerrain/A/4Z/1L5HVLJ807XEWUO6BUIXQZ.uasset` | Outliner folder (World Partition external object) | 1926 |  |
| `__ExternalObjects__/Scene/CorridorTerrain/A/56/PKKJ580IH0BEMME6KY42XE.uasset` | Outliner folder (World Partition external object) | 1961 |  |
| `__ExternalObjects__/Scene/CorridorTerrain/A/6P/RXICAFSQG6F83DACQ8YKQ1.uasset` | Outliner folder (World Partition external object) | 1961 |  |
| `__ExternalObjects__/Scene/CorridorTerrain/A/FS/CN19EW5LNKETT2HGOC3RNA.uasset` | Outliner folder (World Partition external object) | 1961 |  |
| `__ExternalObjects__/Scene/CorridorTerrain/A/HQ/IWH0JIW9GMNP9TR1SBEYA5.uasset` | Outliner folder (World Partition external object) | 1961 |  |
| `__ExternalObjects__/Scene/CorridorTerrain/A/NA/SCVU9G7YFPD8HHT4GLKQ40.uasset` | Outliner folder (World Partition external object) | 1961 |  |
| `__ExternalObjects__/Scene/CorridorTerrain/A/ZU/VGPJ3RPZWA9RUACP51BHBZ.uasset` | Outliner folder (World Partition external object) | 1961 |  |
| `__ExternalObjects__/Scene/CorridorTerrain/B/FW/FVFUQA6TH4Z7MNIHRVYG90.uasset` | Outliner folder (World Partition external object) | 1961 |  |
| `__ExternalObjects__/Scene/CorridorTerrain/B/FW/LPC6ABSV6W8M9PB1JVS4HG.uasset` | Outliner folder (World Partition external object) | 1961 |  |
| `__ExternalObjects__/Scene/CorridorTerrain/B/JF/KFXKPG9XEXFW6FCY4N5UUP.uasset` | Outliner folder (World Partition external object) | 1961 |  |
| `__ExternalObjects__/Scene/CorridorTerrain/B/RF/25H84A4F3XYGHV9V0P7D5F.uasset` | Outliner folder (World Partition external object) | 1961 |  |
| `__ExternalObjects__/Scene/CorridorTerrain/B/VF/LO3U4UL5SFAJQ7H01CMNEQ.uasset` | Outliner folder (World Partition external object) | 1961 |  |
| `__ExternalObjects__/Scene/CorridorTerrain/B/VW/VKO195UY930I54T3WRT5YO.uasset` | Outliner folder (World Partition external object) | 1961 |  |
| `__ExternalObjects__/Scene/CorridorTerrain/B/X5/3A11OZTB1FNGBZUOX02DJ8.uasset` | Outliner folder (World Partition external object) | 1981 |  |
| `__ExternalObjects__/Scene/CorridorTerrain/B/XJ/2JYYI2WUZDN716BN9DHUKY.uasset` | Outliner folder (World Partition external object) | 1961 |  |
| `__ExternalObjects__/Scene/CorridorTerrain/B/Z7/WL6FE36KSKRI9UQCRDAOMB.uasset` | Outliner folder (World Partition external object) | 2028 |  |
| `__ExternalObjects__/Scene/CorridorTerrain/C/5F/XTGWH4E3JPDB6D7FC18YRZ.uasset` | Outliner folder (World Partition external object) | 1961 |  |
| `__ExternalObjects__/Scene/CorridorTerrain/C/GM/MSJU99GXHW8BFBPTHA6GKB.uasset` | Outliner folder (World Partition external object) | 1961 |  |
| `__ExternalObjects__/Scene/CorridorTerrain/C/PI/DXY34XU1HL468IVB5UL22N.uasset` | Outliner folder (World Partition external object) | 1961 |  |
| `__ExternalObjects__/Scene/CorridorTerrain/C/WB/OI1BQAUL4O7ZS03IT5M55V.uasset` | Outliner folder (World Partition external object) | 1961 |  |
| `__ExternalObjects__/Scene/CorridorTerrain/D/3O/DG99O733FQSYOSPGGSSMM5.uasset` | Outliner folder (World Partition external object) | 1961 |  |
| `__ExternalObjects__/Scene/CorridorTerrain/D/6J/AYJETVOHNJJ2HW3K5BOJTX.uasset` | Outliner folder (World Partition external object) | 1961 |  |
| `__ExternalObjects__/Scene/CorridorTerrain/D/6Q/UKEG7VRHAA5ID5HHUZQSMT.uasset` | Outliner folder (World Partition external object) | 1961 |  |
| `__ExternalObjects__/Scene/CorridorTerrain/D/DN/ZTEYC8AQPL58LNU0AXHYM2.uasset` | Outliner folder (World Partition external object) | 1961 |  |
| `__ExternalObjects__/Scene/CorridorTerrain/D/IZ/UWPXZE61GETRMLMPMEESLK.uasset` | Outliner folder (World Partition external object) | 1961 |  |
| `__ExternalObjects__/Scene/CorridorTerrain/D/J3/GED9UMXYOTW3FF8V0T0H1K.uasset` | Outliner folder (World Partition external object) | 1961 |  |
| `__ExternalObjects__/Scene/CorridorTerrain/D/SK/CYP1VRAVHUUWRVSI7AP3DP.uasset` | Outliner folder (World Partition external object) | 1961 |  |
| `__ExternalObjects__/Scene/CorridorTerrain/E/8S/1RVC8IL5D2FKYLJYD71LAD.uasset` | Outliner folder (World Partition external object) | 1961 |  |
| `__ExternalObjects__/Scene/CorridorTerrain/E/EU/3D22YYR0TBPETVJNT4PPWB.uasset` | Outliner folder (World Partition external object) | 1961 |  |
| `__ExternalObjects__/Scene/CorridorTerrain/E/H8/57FZJOE16GBNBK7H86PIYD.uasset` | Outliner folder (World Partition external object) | 1961 |  |
| `__ExternalObjects__/Scene/CorridorTerrain/E/I8/EF573I91864OC1KUT6ES1Y.uasset` | Outliner folder (World Partition external object) | 1961 |  |
| `__ExternalObjects__/Scene/CorridorTerrain/E/JY/PHW4KP8TDTARE8FW67VOVH.uasset` | Outliner folder (World Partition external object) | 1961 |  |
| `__ExternalObjects__/Scene/CorridorTerrain/E/MY/8SODRQB006V7R7BMHX8747.uasset` | Outliner folder (World Partition external object) | 1961 |  |
| `__ExternalObjects__/Scene/CorridorTerrain/E/TE/JAQSGKQY3KMEZ9Q9G8FI1W.uasset` | Outliner folder (World Partition external object) | 1961 |  |
| `Buildings/000000_concrete_jpg.uasset` | Building material instance | 59871 | `corridor_tiles_baked/tile_+0013_+0002.fbx` |
| `Buildings/000000_concrete_png.uasset` | Building material instance | 61694 | `corridor_tiles_baked/tile_-0009_-0003.fbx` |
| `Buildings/000000_gravel_jpg.uasset` | Building material instance | 59797 | `corridor_tiles_baked/tile_-0012_-0002.fbx` |
| `Buildings/000000_pro_6841_exp_jpg.uasset` | Building material instance | 60019 | `corridor_tiles_baked/tile_+0013_+0003.fbx` |
| `Buildings/000000_roof_tiles_png.uasset` | Building material instance | 59950 | `corridor_tiles_baked/tile_-0008_-0003.fbx` |
| `Buildings/008000_concrete_jpg.uasset` | Building material instance | 61298 | `corridor_tiles_baked/tile_-0010_-0003.fbx` |
| `Buildings/008000_plaster_png.uasset` | Building material instance | 61496 | `corridor_tiles_baked/tile_-0010_-0003.fbx` |
| `Buildings/182e45_pro_6841_exp_jpg.uasset` | Building material instance | 63584 | `corridor_tiles_baked/tile_+0007_+0001.fbx` |
| `Buildings/2b515c_pro_6841_exp_jpg.uasset` | Building material instance | 64250 | `corridor_tiles_baked/tile_+0013_+0002.fbx` |
| `Buildings/2b515c_pro_6848_exp_jpg.uasset` | Building material instance | 64721 | `corridor_tiles_baked/tile_+0013_+0002.fbx` |
| `Buildings/2d2c2a_brick_jpg.uasset` | Building material instance | 61598 | `corridor_tiles_baked/tile_+0006_+0001.fbx` |
| `Buildings/2d2c2a_brick_png.uasset` | Building material instance | 61589 | `corridor_tiles_baked/tile_+0007_+0001.fbx` |
| `Buildings/494c57_metal_png.uasset` | Building material instance | 57159 | `corridor_tiles_baked/tile_+0000_+0000_r+000+000.fbx` |
| `Buildings/4e7292_pro_6848_exp_jpg.uasset` | Building material instance | 65048 | `corridor_tiles_baked/tile_+0006_+0001.fbx` |
| `Buildings/585f4d.uasset` | Building material instance | 58698 | `corridor_tiles_baked/tile_+0014_+0002.fbx` |
| `Buildings/5e2a31_metal_png.uasset` | Building material instance | 57159 | `corridor_tiles_baked/tile_+0000_+0000_r+000+000.fbx` |
| `Buildings/5e6c76_pro_6848_exp_jpg.uasset` | Building material instance | 64907 | `corridor_tiles_baked/tile_+0013_+0002.fbx` |
| `Buildings/7b422f_brick_jpg.uasset` | Building material instance | 57159 | `corridor_tiles_baked/tile_+0000_+0000_r+000+000.fbx` |
| `Buildings/7b422f_brick_png.uasset` | Building material instance | 57159 | `corridor_tiles_baked/tile_+0000_+0000_r+000+000.fbx` |
| `Buildings/7e9a9e_metal_png.uasset` | Building material instance | 61808 | `corridor_tiles_baked/tile_+0013_+0002.fbx` |
| `Buildings/808080_concrete_jpg.uasset` | Building material instance | 61356 | `corridor_tiles_baked/tile_+0013_+0002.fbx` |
| `Buildings/808080_concrete_png.uasset` | Building material instance | 61694 | `corridor_tiles_baked/tile_-0010_-0003.fbx` |
| `Buildings/818b8f_metal_png.uasset` | Building material instance | 57159 | `corridor_tiles_baked/tile_+0000_+0000_r+000+000.fbx` |
| `Buildings/8a5c4d_roof_tiles_jpg.uasset` | Building material instance | 57344 | `corridor_tiles_baked/tile_+0000_+0000_r+000+000.fbx` |
| `Buildings/8a5c4d_roof_tiles_png.uasset` | Building material instance | 57344 | `corridor_tiles_baked/tile_+0000_+0000_r+000+000.fbx` |
| `Buildings/976c6b_brick_jpg.uasset` | Building material instance | 57159 | `corridor_tiles_baked/tile_+0000_+0000_r+000+000.fbx` |
| `Buildings/976c6b_brick_png.uasset` | Building material instance | 57159 | `corridor_tiles_baked/tile_+0000_+0000_r+000+000.fbx` |
| `Buildings/a19472.uasset` | Building material instance | 58763 | `corridor_tiles_baked/tile_+0014_+0002.fbx` |
| `Buildings/a3865f_plaster_png.uasset` | Building material instance | 57233 | `corridor_tiles_baked/tile_+0000_+0000_r+000+000.fbx` |
| `Buildings/a52a2a_brick_png.uasset` | Building material instance | 62363 | `corridor_tiles_baked/tile_+0013_+0002.fbx` |
| `Buildings/a52a2a_roof_tiles_jpg.uasset` | Building material instance | 62062 | `corridor_tiles_baked/tile_-0008_-0003.fbx` |
| `Buildings/a6653f_roof_tiles_jpg.uasset` | Building material instance | 57344 | `corridor_tiles_baked/tile_+0000_+0000_r+000+000.fbx` |
| `Buildings/a6653f_roof_tiles_png.uasset` | Building material instance | 57344 | `corridor_tiles_baked/tile_+0000_+0000_r+000+000.fbx` |
| `Buildings/a9a9a9_concrete_png.uasset` | Building material instance | 61776 | `corridor_tiles_baked/tile_+0012_+0002.fbx` |
| `Buildings/afafaf_concrete_jpg.uasset` | Building material instance | 57270 | `corridor_tiles_baked/tile_+0000_+0000_r+000+000.fbx` |
| `Buildings/afafaf_concrete_png.uasset` | Building material instance | 57270 | `corridor_tiles_baked/tile_+0000_+0000_r+000+000.fbx` |
| `Buildings/afafaf_metal_png.uasset` | Building material instance | 61813 | `corridor_tiles_baked/tile_+0013_+0002.fbx` |
| `Buildings/b2b2a6_concrete_jpg.uasset` | Building material instance | 57270 | `corridor_tiles_baked/tile_+0000_+0000_r+000+000.fbx` |
| `Buildings/b2b2a6_concrete_png.uasset` | Building material instance | 57270 | `corridor_tiles_baked/tile_+0000_+0000_r+000+000.fbx` |
| `Buildings/b8a594_concrete_png.uasset` | Building material instance | 61965 | `corridor_tiles_baked/tile_+0013_+0003.fbx` |
| `Buildings/b8a594_plaster_png.uasset` | Building material instance | 57233 | `corridor_tiles_baked/tile_+0000_+0000_r+000+000.fbx` |
| `Buildings/b9bdaf.uasset` | Building material instance | 58798 | `corridor_tiles_baked/tile_+0014_+0002.fbx` |
| `Buildings/baked_000000_concrete.uasset` | Building texture | 54305 | `corridor_new.fbm/baked_000000_concrete.jpg` |
| `Buildings/baked_000000_gravel.uasset` | Building texture | 54261 | `corridor_new.fbm/baked_000000_gravel.jpg` |
| `Buildings/baked_000000_pro_6841_exp.uasset` | Building texture | 54768 | `corridor_new.fbm/baked_000000_pro_6841_exp.jpg` |
| `Buildings/baked_000000_roof_tiles.uasset` | Building texture | 66239 | `corridor_new.fbm/baked_000000_roof_tiles.png` |
| `Buildings/baked_008000_concrete.uasset` | Building texture | 95730 | `corridor_new.fbm/baked_008000_concrete.jpg` |
| `Buildings/baked_008000_plaster.uasset` | Building texture | 131863 | `corridor_new.fbm/baked_008000_plaster.png` |
| `Buildings/baked_182e45_pro_6841_exp.uasset` | Building texture | 567276 | `corridor_new.fbm/baked_182e45_pro_6841_exp.jpg` |
| `Buildings/baked_2b515c_pro_6841_exp.uasset` | Building texture | 603696 | `corridor_new.fbm/baked_2b515c_pro_6841_exp.jpg` |
| `Buildings/baked_2b515c_pro_6848_exp.uasset` | Building texture | 458014 | `corridor_new.fbm/baked_2b515c_pro_6848_exp.jpg` |
| `Buildings/baked_2d2c2a_brick.uasset` | Building texture | 1013537 | `corridor_new.fbm/baked_2d2c2a_brick.jpg` |
| `Buildings/baked_494c57_metal.uasset` | Building texture | 1006482 | `corridor_new.fbm/baked_494c57_metal.png` |
| `Buildings/baked_4e7292_pro_6848_exp.uasset` | Building texture | 442316 | `corridor_new.fbm/baked_4e7292_pro_6848_exp.jpg` |
| `Buildings/baked_5e2a31_metal.uasset` | Building texture | 1085913 | `corridor_new.fbm/baked_5e2a31_metal.png` |
| `Buildings/baked_5e6c76_pro_6848_exp.uasset` | Building texture | 462879 | `corridor_new.fbm/baked_5e6c76_pro_6848_exp.jpg` |
| `Buildings/baked_7b422f_brick.uasset` | Building texture | 1342873 | `corridor_new.fbm/baked_7b422f_brick.jpg` |
| `Buildings/baked_7e9a9e_metal.uasset` | Building texture | 1012009 | `corridor_new.fbm/baked_7e9a9e_metal.png` |
| `Buildings/baked_808080_concrete.uasset` | Building texture | 343696 | `corridor_new.fbm/baked_808080_concrete.jpg` |
| `Buildings/baked_818b8f_metal.uasset` | Building texture | 1023806 | `corridor_new.fbm/baked_818b8f_metal.png` |
| `Buildings/baked_8a5c4d_roof_tiles.uasset` | Building texture | 1084468 | `corridor_new.fbm/baked_8a5c4d_roof_tiles.jpg` |
| `Buildings/baked_976c6b_brick.uasset` | Building texture | 1342215 | `corridor_new.fbm/baked_976c6b_brick.jpg` |
| `Buildings/baked_a3865f_plaster.uasset` | Building texture | 878120 | `corridor_new.fbm/baked_a3865f_plaster.png` |
| `Buildings/baked_a52a2a_brick.uasset` | Building texture | 1681220 | `corridor_new.fbm/baked_a52a2a_brick.png` |
| `Buildings/baked_a52a2a_roof_tiles.uasset` | Building texture | 1064645 | `corridor_new.fbm/baked_a52a2a_roof_tiles.jpg` |
| `Buildings/baked_a6653f_roof_tiles.uasset` | Building texture | 1095208 | `corridor_new.fbm/baked_a6653f_roof_tiles.jpg` |
| `Buildings/baked_a9a9a9_concrete.uasset` | Building texture | 1972180 | `corridor_new.fbm/baked_a9a9a9_concrete.png` |
| `Buildings/baked_afafaf_concrete.uasset` | Building texture | 1963373 | `corridor_new.fbm/baked_afafaf_concrete.png` |
| `Buildings/baked_afafaf_metal.uasset` | Building texture | 1025759 | `corridor_new.fbm/baked_afafaf_metal.png` |
| `Buildings/baked_b2b2a6_concrete.uasset` | Building texture | 1960555 | `corridor_new.fbm/baked_b2b2a6_concrete.png` |
| `Buildings/baked_b8a594_concrete.uasset` | Building texture | 1386106 | `corridor_new.fbm/baked_b8a594_concrete.png` |
| `Buildings/baked_b8a594_plaster.uasset` | Building texture | 954300 | `corridor_new.fbm/baked_b8a594_plaster.png` |
| `Buildings/baked_c5765d_brick.uasset` | Building texture | 1701521 | `corridor_new.fbm/baked_c5765d_brick.png` |
| `Buildings/baked_c57a63_roof_tiles.uasset` | Building texture | 1124328 | `corridor_new.fbm/baked_c57a63_roof_tiles.jpg` |
| `Buildings/baked_c8c2b6_concrete.uasset` | Building texture | 347688 | `corridor_new.fbm/baked_c8c2b6_concrete.jpg` |
| `Buildings/baked_c8c2b6_metal.uasset` | Building texture | 1011581 | `corridor_new.fbm/baked_c8c2b6_metal.png` |
| `Buildings/baked_cc0textures_bricks11_col_exp_jpg_7b422f_pro_2157_exp.uasset` | Building texture | 884968 | `corridor_new.fbm/baked_cc0textures_bricks11_col_exp.jpg_7b422f_pro_2157_exp.png` |
| `Buildings/baked_cc0textures_bricks11_col_exp_jpg_7b422f_pro_2161_exp.uasset` | Building texture | 1126003 | `corridor_new.fbm/baked_cc0textures_bricks11_col_exp.jpg_7b422f_pro_2161_exp.png` |
| `Buildings/baked_cc0textures_bricks11_col_exp_jpg_7b422f_pro_2353_exp.uasset` | Building texture | 463781 | `corridor_new.fbm/baked_cc0textures_bricks11_col_exp.jpg_7b422f_pro_2353_exp.png` |
| `Buildings/baked_cc0textures_bricks11_col_exp_jpg_7b422f_pro_2901_exp.uasset` | Building texture | 413698 | `corridor_new.fbm/baked_cc0textures_bricks11_col_exp.jpg_7b422f_pro_2901_exp.png` |
| `Buildings/baked_cc0textures_bricks11_col_exp_jpg_7b422f_pro_6908_exp.uasset` | Building texture | 886023 | `corridor_new.fbm/baked_cc0textures_bricks11_col_exp.jpg_7b422f_pro_6908_exp.png` |
| `Buildings/baked_cc0textures_bricks11_col_exp_jpg_976c6b_pro_2157_exp.uasset` | Building texture | 872720 | `corridor_new.fbm/baked_cc0textures_bricks11_col_exp.jpg_976c6b_pro_2157_exp.png` |
| `Buildings/baked_cc0textures_bricks11_col_exp_jpg_976c6b_pro_2161_exp.uasset` | Building texture | 1139489 | `corridor_new.fbm/baked_cc0textures_bricks11_col_exp.jpg_976c6b_pro_2161_exp.png` |
| `Buildings/baked_cc0textures_bricks11_col_exp_jpg_976c6b_pro_2353_exp.uasset` | Building texture | 507356 | `corridor_new.fbm/baked_cc0textures_bricks11_col_exp.jpg_976c6b_pro_2353_exp.png` |
| `Buildings/baked_cc0textures_bricks11_col_exp_jpg_976c6b_pro_2901_exp.uasset` | Building texture | 419667 | `corridor_new.fbm/baked_cc0textures_bricks11_col_exp.jpg_976c6b_pro_2901_exp.png` |
| `Buildings/baked_cc0textures_bricks11_col_exp_jpg_976c6b_pro_6908_exp.uasset` | Building texture | 872080 | `corridor_new.fbm/baked_cc0textures_bricks11_col_exp.jpg_976c6b_pro_6908_exp.png` |
| `Buildings/baked_cc0textures_bricks11_col_exp_jpg_c5765d_pro_2157_exp.uasset` | Building texture | 872664 | `corridor_new.fbm/baked_cc0textures_bricks11_col_exp.jpg_c5765d_pro_2157_exp.png` |
| `Buildings/baked_cc0textures_bricks11_col_exp_jpg_c5765d_pro_2161_exp.uasset` | Building texture | 1129557 | `corridor_new.fbm/baked_cc0textures_bricks11_col_exp.jpg_c5765d_pro_2161_exp.png` |
| `Buildings/baked_cc0textures_bricks11_col_exp_jpg_c5765d_pro_2353_exp.uasset` | Building texture | 518072 | `corridor_new.fbm/baked_cc0textures_bricks11_col_exp.jpg_c5765d_pro_2353_exp.png` |
| `Buildings/baked_cc0textures_bricks11_col_exp_jpg_c5765d_pro_2901_exp.uasset` | Building texture | 430700 | `corridor_new.fbm/baked_cc0textures_bricks11_col_exp.jpg_c5765d_pro_2901_exp.png` |
| `Buildings/baked_cc0textures_bricks11_col_exp_jpg_c5765d_pro_6908_exp.uasset` | Building texture | 884679 | `corridor_new.fbm/baked_cc0textures_bricks11_col_exp.jpg_c5765d_pro_6908_exp.png` |
| `Buildings/baked_cc0textures_bricks11_col_exp_jpg_ff0000_pro_2157_exp.uasset` | Building texture | 873097 | `corridor_new.fbm/baked_cc0textures_bricks11_col_exp.jpg_ff0000_pro_2157_exp.png` |
| `Buildings/baked_cc0textures_bricks11_col_exp_jpg_ff0000_pro_2161_exp.uasset` | Building texture | 1128073 | `corridor_new.fbm/baked_cc0textures_bricks11_col_exp.jpg_ff0000_pro_2161_exp.png` |
| `Buildings/baked_cc0textures_bricks11_col_exp_jpg_ffffff_pro_2157_exp.uasset` | Building texture | 889545 | `corridor_new.fbm/baked_cc0textures_bricks11_col_exp.jpg_ffffff_pro_2157_exp.png` |
| `Buildings/baked_cc0textures_bricks11_col_exp_jpg_ffffff_pro_2161_exp.uasset` | Building texture | 1126641 | `corridor_new.fbm/baked_cc0textures_bricks11_col_exp.jpg_ffffff_pro_2161_exp.png` |
| `Buildings/baked_cc0textures_concrete06_col_exp_jpg_808080_pro_2157_exp.uasset` | Building texture | 841713 | `corridor_new.fbm/baked_cc0textures_concrete06_col_exp.jpg_808080_pro_2157_exp.png` |
| `Buildings/baked_cc0textures_concrete06_col_exp_jpg_808080_pro_2161_exp.uasset` | Building texture | 1102846 | `corridor_new.fbm/baked_cc0textures_concrete06_col_exp.jpg_808080_pro_2161_exp.png` |
| `Buildings/baked_cfbc8e_plaster.uasset` | Building texture | 956737 | `corridor_new.fbm/baked_cfbc8e_plaster.png` |
| `Buildings/baked_duion_bricks_classic_01_D_exp_png_7b422f_pro_2157_exp.uasset` | Building texture | 885306 | `corridor_new.fbm/baked_duion_bricks_classic_01_D_exp.png_7b422f_pro_2157_exp.png` |
| `Buildings/baked_duion_bricks_classic_01_D_exp_png_7b422f_pro_2161_exp.uasset` | Building texture | 1106452 | `corridor_new.fbm/baked_duion_bricks_classic_01_D_exp.png_7b422f_pro_2161_exp.png` |
| `Buildings/baked_duion_bricks_classic_01_D_exp_png_7b422f_pro_2353_exp.uasset` | Building texture | 540087 | `corridor_new.fbm/baked_duion_bricks_classic_01_D_exp.png_7b422f_pro_2353_exp.png` |
| `Buildings/baked_duion_bricks_classic_01_D_exp_png_7b422f_pro_2901_exp.uasset` | Building texture | 396721 | `corridor_new.fbm/baked_duion_bricks_classic_01_D_exp.png_7b422f_pro_2901_exp.png` |
| `Buildings/baked_duion_bricks_classic_01_D_exp_png_7b422f_pro_6908_exp.uasset` | Building texture | 882285 | `corridor_new.fbm/baked_duion_bricks_classic_01_D_exp.png_7b422f_pro_6908_exp.png` |
| `Buildings/baked_duion_bricks_classic_01_D_exp_png_976c6b_pro_2157_exp.uasset` | Building texture | 882521 | `corridor_new.fbm/baked_duion_bricks_classic_01_D_exp.png_976c6b_pro_2157_exp.png` |
| `Buildings/baked_duion_bricks_classic_01_D_exp_png_976c6b_pro_2161_exp.uasset` | Building texture | 1126221 | `corridor_new.fbm/baked_duion_bricks_classic_01_D_exp.png_976c6b_pro_2161_exp.png` |
| `Buildings/baked_duion_bricks_classic_01_D_exp_png_976c6b_pro_2353_exp.uasset` | Building texture | 523263 | `corridor_new.fbm/baked_duion_bricks_classic_01_D_exp.png_976c6b_pro_2353_exp.png` |
| `Buildings/baked_duion_bricks_classic_01_D_exp_png_976c6b_pro_2901_exp.uasset` | Building texture | 404042 | `corridor_new.fbm/baked_duion_bricks_classic_01_D_exp.png_976c6b_pro_2901_exp.png` |
| `Buildings/baked_duion_bricks_classic_01_D_exp_png_976c6b_pro_6908_exp.uasset` | Building texture | 871980 | `corridor_new.fbm/baked_duion_bricks_classic_01_D_exp.png_976c6b_pro_6908_exp.png` |
| `Buildings/baked_duion_bricks_classic_01_D_exp_png_c5765d_pro_2157_exp.uasset` | Building texture | 887399 | `corridor_new.fbm/baked_duion_bricks_classic_01_D_exp.png_c5765d_pro_2157_exp.png` |
| `Buildings/baked_duion_bricks_classic_01_D_exp_png_c5765d_pro_2161_exp.uasset` | Building texture | 1122527 | `corridor_new.fbm/baked_duion_bricks_classic_01_D_exp.png_c5765d_pro_2161_exp.png` |
| `Buildings/baked_duion_bricks_classic_01_D_exp_png_c5765d_pro_2353_exp.uasset` | Building texture | 545634 | `corridor_new.fbm/baked_duion_bricks_classic_01_D_exp.png_c5765d_pro_2353_exp.png` |
| `Buildings/baked_duion_bricks_classic_01_D_exp_png_c5765d_pro_2901_exp.uasset` | Building texture | 399750 | `corridor_new.fbm/baked_duion_bricks_classic_01_D_exp.png_c5765d_pro_2901_exp.png` |
| `Buildings/baked_duion_bricks_classic_01_D_exp_png_c5765d_pro_6908_exp.uasset` | Building texture | 879006 | `corridor_new.fbm/baked_duion_bricks_classic_01_D_exp.png_c5765d_pro_6908_exp.png` |
| `Buildings/baked_duion_bricks_classic_02_D_exp_png_7b422f_pro_2157_exp.uasset` | Building texture | 886374 | `corridor_new.fbm/baked_duion_bricks_classic_02_D_exp.png_7b422f_pro_2157_exp.png` |
| `Buildings/baked_duion_bricks_classic_02_D_exp_png_7b422f_pro_2161_exp.uasset` | Building texture | 1142376 | `corridor_new.fbm/baked_duion_bricks_classic_02_D_exp.png_7b422f_pro_2161_exp.png` |
| `Buildings/baked_duion_bricks_classic_02_D_exp_png_7b422f_pro_2353_exp.uasset` | Building texture | 546735 | `corridor_new.fbm/baked_duion_bricks_classic_02_D_exp.png_7b422f_pro_2353_exp.png` |
| `Buildings/baked_duion_bricks_classic_02_D_exp_png_7b422f_pro_2901_exp.uasset` | Building texture | 494292 | `corridor_new.fbm/baked_duion_bricks_classic_02_D_exp.png_7b422f_pro_2901_exp.png` |
| `Buildings/baked_duion_bricks_classic_02_D_exp_png_7b422f_pro_6908_exp.uasset` | Building texture | 898522 | `corridor_new.fbm/baked_duion_bricks_classic_02_D_exp.png_7b422f_pro_6908_exp.png` |
| `Buildings/baked_duion_bricks_classic_02_D_exp_png_976c6b_pro_2157_exp.uasset` | Building texture | 894150 | `corridor_new.fbm/baked_duion_bricks_classic_02_D_exp.png_976c6b_pro_2157_exp.png` |
| `Buildings/baked_duion_bricks_classic_02_D_exp_png_976c6b_pro_2161_exp.uasset` | Building texture | 1150741 | `corridor_new.fbm/baked_duion_bricks_classic_02_D_exp.png_976c6b_pro_2161_exp.png` |
| `Buildings/baked_duion_bricks_classic_02_D_exp_png_976c6b_pro_2353_exp.uasset` | Building texture | 525315 | `corridor_new.fbm/baked_duion_bricks_classic_02_D_exp.png_976c6b_pro_2353_exp.png` |
| `Buildings/baked_duion_bricks_classic_02_D_exp_png_976c6b_pro_2901_exp.uasset` | Building texture | 501775 | `corridor_new.fbm/baked_duion_bricks_classic_02_D_exp.png_976c6b_pro_2901_exp.png` |
| `Buildings/baked_duion_bricks_classic_02_D_exp_png_976c6b_pro_6908_exp.uasset` | Building texture | 896575 | `corridor_new.fbm/baked_duion_bricks_classic_02_D_exp.png_976c6b_pro_6908_exp.png` |
| `Buildings/baked_duion_bricks_classic_02_D_exp_png_a52a2a_pro_2157_exp.uasset` | Building texture | 896591 | `corridor_new.fbm/baked_duion_bricks_classic_02_D_exp.png_a52a2a_pro_2157_exp.png` |
| `Buildings/baked_duion_bricks_classic_02_D_exp_png_a52a2a_pro_2161_exp.uasset` | Building texture | 1123162 | `corridor_new.fbm/baked_duion_bricks_classic_02_D_exp.png_a52a2a_pro_2161_exp.png` |
| `Buildings/baked_duion_bricks_classic_02_D_exp_png_c5765d_pro_2157_exp.uasset` | Building texture | 894138 | `corridor_new.fbm/baked_duion_bricks_classic_02_D_exp.png_c5765d_pro_2157_exp.png` |
| `Buildings/baked_duion_bricks_classic_02_D_exp_png_c5765d_pro_2161_exp.uasset` | Building texture | 1140449 | `corridor_new.fbm/baked_duion_bricks_classic_02_D_exp.png_c5765d_pro_2161_exp.png` |
| `Buildings/baked_duion_bricks_classic_02_D_exp_png_c5765d_pro_2353_exp.uasset` | Building texture | 547616 | `corridor_new.fbm/baked_duion_bricks_classic_02_D_exp.png_c5765d_pro_2353_exp.png` |
| `Buildings/baked_duion_bricks_classic_02_D_exp_png_c5765d_pro_2901_exp.uasset` | Building texture | 505019 | `corridor_new.fbm/baked_duion_bricks_classic_02_D_exp.png_c5765d_pro_2901_exp.png` |
| `Buildings/baked_duion_bricks_classic_02_D_exp_png_c5765d_pro_6908_exp.uasset` | Building texture | 894858 | `corridor_new.fbm/baked_duion_bricks_classic_02_D_exp.png_c5765d_pro_6908_exp.png` |
| `Buildings/baked_duion_bricks_classic_02_D_exp_png_f5f5dc_pro_2157_exp.uasset` | Building texture | 890724 | `corridor_new.fbm/baked_duion_bricks_classic_02_D_exp.png_f5f5dc_pro_2157_exp.png` |
| `Buildings/baked_duion_bricks_classic_02_D_exp_png_f5f5dc_pro_2161_exp.uasset` | Building texture | 1152397 | `corridor_new.fbm/baked_duion_bricks_classic_02_D_exp.png_f5f5dc_pro_2161_exp.png` |
| `Buildings/baked_duion_bricks_classic_02_D_exp_png_ff0000_pro_2157_exp.uasset` | Building texture | 878945 | `corridor_new.fbm/baked_duion_bricks_classic_02_D_exp.png_ff0000_pro_2157_exp.png` |
| `Buildings/baked_duion_bricks_classic_02_D_exp_png_ff0000_pro_2161_exp.uasset` | Building texture | 1135168 | `corridor_new.fbm/baked_duion_bricks_classic_02_D_exp.png_ff0000_pro_2161_exp.png` |
| `Buildings/baked_duion_concrete_rough_01_D_exp_png_b2b2a6_pro_2157_exp.uasset` | Building texture | 853052 | `corridor_new.fbm/baked_duion_concrete_rough_01_D_exp.png_b2b2a6_pro_2157_exp.png` |
| `Buildings/baked_duion_concrete_rough_01_D_exp_png_b2b2a6_pro_2161_exp.uasset` | Building texture | 1143762 | `corridor_new.fbm/baked_duion_concrete_rough_01_D_exp.png_b2b2a6_pro_2161_exp.png` |
| `Buildings/baked_duion_concrete_stripes_03_D_exp_png_b2b2a6_pro_2157_exp.uasset` | Building texture | 851027 | `corridor_new.fbm/baked_duion_concrete_stripes_03_D_exp.png_b2b2a6_pro_2157_exp.png` |
| `Buildings/baked_duion_concrete_stripes_03_D_exp_png_b2b2a6_pro_2161_exp.uasset` | Building texture | 1120096 | `corridor_new.fbm/baked_duion_concrete_stripes_03_D_exp.png_b2b2a6_pro_2161_exp.png` |
| `Buildings/baked_duion_concrete_stripes_03_D_exp_png_c8c2b6_pro_2353_exp.uasset` | Building texture | 627303 | `corridor_new.fbm/baked_duion_concrete_stripes_03_D_exp.png_c8c2b6_pro_2353_exp.png` |
| `Buildings/baked_duion_metal_panels_01_D_exp_png_afafaf_pro_2901_exp.uasset` | Building texture | 521754 | `corridor_new.fbm/baked_duion_metal_panels_01_D_exp.png_afafaf_pro_2901_exp.png` |
| `Buildings/baked_duion_metal_panels_01_D_exp_png_c8c2b6_pro_2353_exp.uasset` | Building texture | 491748 | `corridor_new.fbm/baked_duion_metal_panels_01_D_exp.png_c8c2b6_pro_2353_exp.png` |
| `Buildings/baked_duion_metal_panels_01_D_exp_png_ffffff_pro_2157_exp.uasset` | Building texture | 838141 | `corridor_new.fbm/baked_duion_metal_panels_01_D_exp.png_ffffff_pro_2157_exp.png` |
| `Buildings/baked_duion_metal_panels_01_D_exp_png_ffffff_pro_2161_exp.uasset` | Building texture | 1077450 | `corridor_new.fbm/baked_duion_metal_panels_01_D_exp.png_ffffff_pro_2161_exp.png` |
| `Buildings/baked_duion_plaster_sprinkled_01_D_exp_png_008000_pro_2353_exp.uasset` | Building texture | 510189 | `corridor_new.fbm/baked_duion_plaster_sprinkled_01_D_exp.png_008000_pro_2353_exp.png` |
| `Buildings/baked_duion_plaster_sprinkled_01_D_exp_png_a3865f_pro_2157_exp.uasset` | Building texture | 850381 | `corridor_new.fbm/baked_duion_plaster_sprinkled_01_D_exp.png_a3865f_pro_2157_exp.png` |
| `Buildings/baked_duion_plaster_sprinkled_01_D_exp_png_a3865f_pro_2161_exp.uasset` | Building texture | 1105043 | `corridor_new.fbm/baked_duion_plaster_sprinkled_01_D_exp.png_a3865f_pro_2161_exp.png` |
| `Buildings/baked_duion_plaster_sprinkled_01_D_exp_png_a3865f_pro_2353_exp.uasset` | Building texture | 513841 | `corridor_new.fbm/baked_duion_plaster_sprinkled_01_D_exp.png_a3865f_pro_2353_exp.png` |
| `Buildings/baked_duion_plaster_sprinkled_01_D_exp_png_a3865f_pro_2901_exp.uasset` | Building texture | 569857 | `corridor_new.fbm/baked_duion_plaster_sprinkled_01_D_exp.png_a3865f_pro_2901_exp.png` |
| `Buildings/baked_duion_plaster_sprinkled_01_D_exp_png_a3865f_pro_6908_exp.uasset` | Building texture | 925325 | `corridor_new.fbm/baked_duion_plaster_sprinkled_01_D_exp.png_a3865f_pro_6908_exp.png` |
| `Buildings/baked_duion_plaster_sprinkled_01_D_exp_png_b8a594_pro_2157_exp.uasset` | Building texture | 844103 | `corridor_new.fbm/baked_duion_plaster_sprinkled_01_D_exp.png_b8a594_pro_2157_exp.png` |
| `Buildings/baked_duion_plaster_sprinkled_01_D_exp_png_b8a594_pro_2161_exp.uasset` | Building texture | 1097835 | `corridor_new.fbm/baked_duion_plaster_sprinkled_01_D_exp.png_b8a594_pro_2161_exp.png` |
| `Buildings/baked_duion_plaster_sprinkled_01_D_exp_png_b8a594_pro_2353_exp.uasset` | Building texture | 577552 | `corridor_new.fbm/baked_duion_plaster_sprinkled_01_D_exp.png_b8a594_pro_2353_exp.png` |
| `Buildings/baked_duion_plaster_sprinkled_01_D_exp_png_b8a594_pro_2901_exp.uasset` | Building texture | 559543 | `corridor_new.fbm/baked_duion_plaster_sprinkled_01_D_exp.png_b8a594_pro_2901_exp.png` |
| `Buildings/baked_duion_plaster_sprinkled_01_D_exp_png_b8a594_pro_6908_exp.uasset` | Building texture | 877596 | `corridor_new.fbm/baked_duion_plaster_sprinkled_01_D_exp.png_b8a594_pro_6908_exp.png` |
| `Buildings/baked_duion_plaster_sprinkled_01_D_exp_png_cfbc8e_pro_2157_exp.uasset` | Building texture | 848541 | `corridor_new.fbm/baked_duion_plaster_sprinkled_01_D_exp.png_cfbc8e_pro_2157_exp.png` |
| `Buildings/baked_duion_plaster_sprinkled_01_D_exp_png_cfbc8e_pro_2161_exp.uasset` | Building texture | 1098877 | `corridor_new.fbm/baked_duion_plaster_sprinkled_01_D_exp.png_cfbc8e_pro_2161_exp.png` |
| `Buildings/baked_duion_plaster_sprinkled_01_D_exp_png_cfbc8e_pro_2353_exp.uasset` | Building texture | 556635 | `corridor_new.fbm/baked_duion_plaster_sprinkled_01_D_exp.png_cfbc8e_pro_2353_exp.png` |
| `Buildings/baked_duion_plaster_sprinkled_01_D_exp_png_cfbc8e_pro_2901_exp.uasset` | Building texture | 543118 | `corridor_new.fbm/baked_duion_plaster_sprinkled_01_D_exp.png_cfbc8e_pro_2901_exp.png` |
| `Buildings/baked_duion_plaster_sprinkled_01_D_exp_png_cfbc8e_pro_6908_exp.uasset` | Building texture | 880072 | `corridor_new.fbm/baked_duion_plaster_sprinkled_01_D_exp.png_cfbc8e_pro_6908_exp.png` |
| `Buildings/baked_duion_plaster_sprinkled_01_D_exp_png_ffffff_pro_2157_exp.uasset` | Building texture | 845055 | `corridor_new.fbm/baked_duion_plaster_sprinkled_01_D_exp.png_ffffff_pro_2157_exp.png` |
| `Buildings/baked_duion_plaster_sprinkled_01_D_exp_png_ffffff_pro_2161_exp.uasset` | Building texture | 1099870 | `corridor_new.fbm/baked_duion_plaster_sprinkled_01_D_exp.png_ffffff_pro_2161_exp.png` |
| `Buildings/baked_duion_plaster_stucco_01_D_exp_png_a3865f_pro_2157_exp.uasset` | Building texture | 834264 | `corridor_new.fbm/baked_duion_plaster_stucco_01_D_exp.png_a3865f_pro_2157_exp.png` |
| `Buildings/baked_duion_plaster_stucco_01_D_exp_png_a3865f_pro_2161_exp.uasset` | Building texture | 1087411 | `corridor_new.fbm/baked_duion_plaster_stucco_01_D_exp.png_a3865f_pro_2161_exp.png` |
| `Buildings/baked_duion_plaster_stucco_01_D_exp_png_a3865f_pro_2353_exp.uasset` | Building texture | 465491 | `corridor_new.fbm/baked_duion_plaster_stucco_01_D_exp.png_a3865f_pro_2353_exp.png` |
| `Buildings/baked_duion_plaster_stucco_01_D_exp_png_a3865f_pro_2901_exp.uasset` | Building texture | 397884 | `corridor_new.fbm/baked_duion_plaster_stucco_01_D_exp.png_a3865f_pro_2901_exp.png` |
| `Buildings/baked_duion_plaster_stucco_01_D_exp_png_a3865f_pro_6908_exp.uasset` | Building texture | 878743 | `corridor_new.fbm/baked_duion_plaster_stucco_01_D_exp.png_a3865f_pro_6908_exp.png` |
| `Buildings/baked_duion_plaster_stucco_01_D_exp_png_b8a594_pro_2157_exp.uasset` | Building texture | 846698 | `corridor_new.fbm/baked_duion_plaster_stucco_01_D_exp.png_b8a594_pro_2157_exp.png` |
| `Buildings/baked_duion_plaster_stucco_01_D_exp_png_b8a594_pro_2161_exp.uasset` | Building texture | 1091223 | `corridor_new.fbm/baked_duion_plaster_stucco_01_D_exp.png_b8a594_pro_2161_exp.png` |
| `Buildings/baked_duion_plaster_stucco_01_D_exp_png_b8a594_pro_2353_exp.uasset` | Building texture | 448700 | `corridor_new.fbm/baked_duion_plaster_stucco_01_D_exp.png_b8a594_pro_2353_exp.png` |
| `Buildings/baked_duion_plaster_stucco_01_D_exp_png_b8a594_pro_2901_exp.uasset` | Building texture | 423576 | `corridor_new.fbm/baked_duion_plaster_stucco_01_D_exp.png_b8a594_pro_2901_exp.png` |
| `Buildings/baked_duion_plaster_stucco_01_D_exp_png_b8a594_pro_6908_exp.uasset` | Building texture | 883502 | `corridor_new.fbm/baked_duion_plaster_stucco_01_D_exp.png_b8a594_pro_6908_exp.png` |
| `Buildings/baked_duion_plaster_stucco_01_D_exp_png_cfbc8e_pro_2157_exp.uasset` | Building texture | 843084 | `corridor_new.fbm/baked_duion_plaster_stucco_01_D_exp.png_cfbc8e_pro_2157_exp.png` |
| `Buildings/baked_duion_plaster_stucco_01_D_exp_png_cfbc8e_pro_2161_exp.uasset` | Building texture | 1094444 | `corridor_new.fbm/baked_duion_plaster_stucco_01_D_exp.png_cfbc8e_pro_2161_exp.png` |
| `Buildings/baked_duion_plaster_stucco_01_D_exp_png_cfbc8e_pro_2353_exp.uasset` | Building texture | 456821 | `corridor_new.fbm/baked_duion_plaster_stucco_01_D_exp.png_cfbc8e_pro_2353_exp.png` |
| `Buildings/baked_duion_plaster_stucco_01_D_exp_png_cfbc8e_pro_2901_exp.uasset` | Building texture | 427509 | `corridor_new.fbm/baked_duion_plaster_stucco_01_D_exp.png_cfbc8e_pro_2901_exp.png` |
| `Buildings/baked_duion_plaster_stucco_01_D_exp_png_cfbc8e_pro_6908_exp.uasset` | Building texture | 881410 | `corridor_new.fbm/baked_duion_plaster_stucco_01_D_exp.png_cfbc8e_pro_6908_exp.png` |
| `Buildings/baked_f5f5dc_brick.uasset` | Building texture | 1592924 | `corridor_new.fbm/baked_f5f5dc_brick.png` |
| `Buildings/baked_ff0000_brick.uasset` | Building texture | 129603 | `corridor_new.fbm/baked_ff0000_brick.png` |
| `Buildings/baked_ffffff_brick.uasset` | Building texture | 1171603 | `corridor_new.fbm/baked_ffffff_brick.jpg` |
| `Buildings/baked_ffffff_concrete.uasset` | Building texture | 1871521 | `corridor_new.fbm/baked_ffffff_concrete.png` |
| `Buildings/baked_ffffff_metal.uasset` | Building texture | 1027325 | `corridor_new.fbm/baked_ffffff_metal.png` |
| `Buildings/baked_ffffff_roof_tiles.uasset` | Building texture | 1369673 | `corridor_new.fbm/baked_ffffff_roof_tiles.png` |
| `Buildings/brown.uasset` | Building material instance | 58658 | `corridor_tiles_baked/tile_+0012_+0002.fbx` |
| `Buildings/c5765d_brick_jpg.uasset` | Building material instance | 57159 | `corridor_tiles_baked/tile_+0000_+0000_r+000+000.fbx` |
| `Buildings/c5765d_brick_png.uasset` | Building material instance | 57159 | `corridor_tiles_baked/tile_+0000_+0000_r+000+000.fbx` |
| `Buildings/c57a63_roof_tiles_jpg.uasset` | Building material instance | 57344 | `corridor_tiles_baked/tile_+0000_+0000_r+000+000.fbx` |
| `Buildings/c57a63_roof_tiles_png.uasset` | Building material instance | 57344 | `corridor_tiles_baked/tile_+0000_+0000_r+000+000.fbx` |
| `Buildings/c8c2b6_concrete_jpg.uasset` | Building material instance | 57270 | `corridor_tiles_baked/tile_+0000_+0000_r+000+000.fbx` |
| `Buildings/c8c2b6_concrete_png.uasset` | Building material instance | 57270 | `corridor_tiles_baked/tile_+0000_+0000_r+000+000.fbx` |
| `Buildings/c8c2b6_metal_png.uasset` | Building material instance | 61850 | `corridor_tiles_baked/tile_+0013_+0003.fbx` |
| `Buildings/cc0textures_bricks11_col_exp_jpg_7b422f_pro_2157_exp_png.uasset` | Building material instance | 58639 | `corridor_tiles_baked/tile_+0000_+0000_r+000+000.fbx` |
| `Buildings/cc0textures_bricks11_col_exp_jpg_7b422f_pro_2161_exp_png.uasset` | Building material instance | 58639 | `corridor_tiles_baked/tile_+0000_+0000_r+000+000.fbx` |
| `Buildings/cc0textures_bricks11_col_exp_jpg_7b422f_pro_2353_exp_png.uasset` | Building material instance | 66017 | `corridor_tiles_baked/tile_+0000_-0001.fbx` |
| `Buildings/cc0textures_bricks11_col_exp_jpg_7b422f_pro_2901_exp_png.uasset` | Building material instance | 66071 | `corridor_tiles_baked/tile_+0000_-0001.fbx` |
| `Buildings/cc0textures_bricks11_col_exp_jpg_7b422f_pro_6908_exp_png.uasset` | Building material instance | 58639 | `corridor_tiles_baked/tile_+0000_+0000_r+000+000.fbx` |
| `Buildings/cc0textures_bricks11_col_exp_jpg_976c6b_pro_2157_exp_png.uasset` | Building material instance | 68281 | `corridor_tiles_baked/tile_+0000_-0001.fbx` |
| `Buildings/cc0textures_bricks11_col_exp_jpg_976c6b_pro_2161_exp_png.uasset` | Building material instance | 68066 | `corridor_tiles_baked/tile_+0000_-0001.fbx` |
| `Buildings/cc0textures_bricks11_col_exp_jpg_976c6b_pro_2353_exp_png.uasset` | Building material instance | 66007 | `corridor_tiles_baked/tile_+0000_-0001.fbx` |
| `Buildings/cc0textures_bricks11_col_exp_jpg_976c6b_pro_2901_exp_png.uasset` | Building material instance | 66193 | `corridor_tiles_baked/tile_+0001_-0001.fbx` |
| `Buildings/cc0textures_bricks11_col_exp_jpg_976c6b_pro_6908_exp_png.uasset` | Building material instance | 58639 | `corridor_tiles_baked/tile_+0000_+0000_r+000+000.fbx` |
| `Buildings/cc0textures_bricks11_col_exp_jpg_c5765d_pro_2157_exp_png.uasset` | Building material instance | 68284 | `corridor_tiles_baked/tile_+0000_-0001.fbx` |
| `Buildings/cc0textures_bricks11_col_exp_jpg_c5765d_pro_2161_exp_png.uasset` | Building material instance | 68066 | `corridor_tiles_baked/tile_+0000_-0001.fbx` |
| `Buildings/cc0textures_bricks11_col_exp_jpg_c5765d_pro_2353_exp_png.uasset` | Building material instance | 66064 | `corridor_tiles_baked/tile_+0003_+0000.fbx` |
| `Buildings/cc0textures_bricks11_col_exp_jpg_c5765d_pro_2901_exp_png.uasset` | Building material instance | 66195 | `corridor_tiles_baked/tile_+0000_-0001.fbx` |
| `Buildings/cc0textures_bricks11_col_exp_jpg_c5765d_pro_6908_exp_png.uasset` | Building material instance | 58639 | `corridor_tiles_baked/tile_+0000_+0000_r+000+000.fbx` |
| `Buildings/cc0textures_bricks11_col_exp_jpg_ff0000_pro_2157_exp_png.uasset` | Building material instance | 68288 | `corridor_tiles_baked/tile_+0011_+0002.fbx` |
| `Buildings/cc0textures_bricks11_col_exp_jpg_ff0000_pro_2161_exp_png.uasset` | Building material instance | 67906 | `corridor_tiles_baked/tile_+0011_+0002.fbx` |
| `Buildings/cc0textures_bricks11_col_exp_jpg_ffffff_pro_2157_exp_png.uasset` | Building material instance | 68323 | `corridor_tiles_baked/tile_+0013_+0002.fbx` |
| `Buildings/cc0textures_bricks11_col_exp_jpg_ffffff_pro_2161_exp_png.uasset` | Building material instance | 67931 | `corridor_tiles_baked/tile_+0013_+0002.fbx` |
| `Buildings/cc0textures_concrete06_col_exp_jpg_808080_pro_2157_exp_png.uasset` | Building material instance | 68181 | `corridor_tiles_baked/tile_+0013_+0002.fbx` |
| `Buildings/cc0textures_concrete06_col_exp_jpg_808080_pro_2161_exp_png.uasset` | Building material instance | 67741 | `corridor_tiles_baked/tile_+0013_+0002.fbx` |
| `Buildings/cfbc8e_plaster_png.uasset` | Building material instance | 57233 | `corridor_tiles_baked/tile_+0000_+0000_r+000+000.fbx` |
| `Buildings/duion_bricks_classic_01_D_exp_png_7b422f_pro_2157_exp_png.uasset` | Building material instance | 58676 | `corridor_tiles_baked/tile_+0000_+0000_r+000+000.fbx` |
| `Buildings/duion_bricks_classic_01_D_exp_png_7b422f_pro_2161_exp_png.uasset` | Building material instance | 58676 | `corridor_tiles_baked/tile_+0000_+0000_r+000+000.fbx` |
| `Buildings/duion_bricks_classic_01_D_exp_png_7b422f_pro_2353_exp_png.uasset` | Building material instance | 65812 | `corridor_tiles_baked/tile_+0000_-0001.fbx` |
| `Buildings/duion_bricks_classic_01_D_exp_png_7b422f_pro_2901_exp_png.uasset` | Building material instance | 58676 | `corridor_tiles_baked/tile_+0000_+0000_r+000+000.fbx` |
| `Buildings/duion_bricks_classic_01_D_exp_png_7b422f_pro_6908_exp_png.uasset` | Building material instance | 58676 | `corridor_tiles_baked/tile_+0000_+0000_r+000+000.fbx` |
| `Buildings/duion_bricks_classic_01_D_exp_png_976c6b_pro_2157_exp_png.uasset` | Building material instance | 68235 | `corridor_tiles_baked/tile_+0000_-0001.fbx` |
| `Buildings/duion_bricks_classic_01_D_exp_png_976c6b_pro_2161_exp_png.uasset` | Building material instance | 68066 | `corridor_tiles_baked/tile_+0000_-0001.fbx` |
| `Buildings/duion_bricks_classic_01_D_exp_png_976c6b_pro_2353_exp_png.uasset` | Building material instance | 65886 | `corridor_tiles_baked/tile_+0000_-0001.fbx` |
| `Buildings/duion_bricks_classic_01_D_exp_png_976c6b_pro_2901_exp_png.uasset` | Building material instance | 65702 | `corridor_tiles_baked/tile_+0000_-0001.fbx` |
| `Buildings/duion_bricks_classic_01_D_exp_png_976c6b_pro_6908_exp_png.uasset` | Building material instance | 58676 | `corridor_tiles_baked/tile_+0000_+0000_r+000+000.fbx` |
| `Buildings/duion_bricks_classic_01_D_exp_png_c5765d_pro_2157_exp_png.uasset` | Building material instance | 68263 | `corridor_tiles_baked/tile_+0000_-0001.fbx` |
| `Buildings/duion_bricks_classic_01_D_exp_png_c5765d_pro_2161_exp_png.uasset` | Building material instance | 68107 | `corridor_tiles_baked/tile_+0000_-0001.fbx` |
| `Buildings/duion_bricks_classic_01_D_exp_png_c5765d_pro_2353_exp_png.uasset` | Building material instance | 65883 | `corridor_tiles_baked/tile_+0000_-0001.fbx` |
| `Buildings/duion_bricks_classic_01_D_exp_png_c5765d_pro_2901_exp_png.uasset` | Building material instance | 65576 | `corridor_tiles_baked/tile_+0001_+0000.fbx` |
| `Buildings/duion_bricks_classic_01_D_exp_png_c5765d_pro_6908_exp_png.uasset` | Building material instance | 58676 | `corridor_tiles_baked/tile_+0000_+0000_r+000+000.fbx` |
| `Buildings/duion_bricks_classic_02_D_exp_png_7b422f_pro_2157_exp_png.uasset` | Building material instance | 58676 | `corridor_tiles_baked/tile_+0000_+0000_r+000+000.fbx` |
| `Buildings/duion_bricks_classic_02_D_exp_png_7b422f_pro_2161_exp_png.uasset` | Building material instance | 58676 | `corridor_tiles_baked/tile_+0000_+0000_r+000+000.fbx` |
| `Buildings/duion_bricks_classic_02_D_exp_png_7b422f_pro_2353_exp_png.uasset` | Building material instance | 66017 | `corridor_tiles_baked/tile_+0000_-0001.fbx` |
| `Buildings/duion_bricks_classic_02_D_exp_png_7b422f_pro_2901_exp_png.uasset` | Building material instance | 67988 | `corridor_tiles_baked/tile_+0000_-0001.fbx` |
| `Buildings/duion_bricks_classic_02_D_exp_png_7b422f_pro_6908_exp_png.uasset` | Building material instance | 58676 | `corridor_tiles_baked/tile_+0000_+0000_r+000+000.fbx` |
| `Buildings/duion_bricks_classic_02_D_exp_png_976c6b_pro_2157_exp_png.uasset` | Building material instance | 68469 | `corridor_tiles_baked/tile_+0000_-0001.fbx` |
| `Buildings/duion_bricks_classic_02_D_exp_png_976c6b_pro_2161_exp_png.uasset` | Building material instance | 68097 | `corridor_tiles_baked/tile_+0000_-0001.fbx` |
| `Buildings/duion_bricks_classic_02_D_exp_png_976c6b_pro_2353_exp_png.uasset` | Building material instance | 66228 | `corridor_tiles_baked/tile_+0000_-0001.fbx` |
| `Buildings/duion_bricks_classic_02_D_exp_png_976c6b_pro_2901_exp_png.uasset` | Building material instance | 68148 | `corridor_tiles_baked/tile_+0000_-0001.fbx` |
| `Buildings/duion_bricks_classic_02_D_exp_png_976c6b_pro_6908_exp_png.uasset` | Building material instance | 58676 | `corridor_tiles_baked/tile_+0000_+0000_r+000+000.fbx` |
| `Buildings/duion_bricks_classic_02_D_exp_png_a52a2a_pro_2157_exp_png.uasset` | Building material instance | 68419 | `corridor_tiles_baked/tile_+0013_+0002.fbx` |
| `Buildings/duion_bricks_classic_02_D_exp_png_a52a2a_pro_2161_exp_png.uasset` | Building material instance | 68067 | `corridor_tiles_baked/tile_+0013_+0002.fbx` |
| `Buildings/duion_bricks_classic_02_D_exp_png_c5765d_pro_2157_exp_png.uasset` | Building material instance | 58676 | `corridor_tiles_baked/tile_+0000_+0000_r+000+000.fbx` |
| `Buildings/duion_bricks_classic_02_D_exp_png_c5765d_pro_2161_exp_png.uasset` | Building material instance | 58676 | `corridor_tiles_baked/tile_+0000_+0000_r+000+000.fbx` |
| `Buildings/duion_bricks_classic_02_D_exp_png_c5765d_pro_2353_exp_png.uasset` | Building material instance | 66252 | `corridor_tiles_baked/tile_+0002_+0000.fbx` |
| `Buildings/duion_bricks_classic_02_D_exp_png_c5765d_pro_2901_exp_png.uasset` | Building material instance | 68226 | `corridor_tiles_baked/tile_+0000_-0001.fbx` |
| `Buildings/duion_bricks_classic_02_D_exp_png_c5765d_pro_6908_exp_png.uasset` | Building material instance | 58676 | `corridor_tiles_baked/tile_+0000_+0000_r+000+000.fbx` |
| `Buildings/duion_bricks_classic_02_D_exp_png_f5f5dc_pro_2157_exp_png.uasset` | Building material instance | 68423 | `corridor_tiles_baked/tile_+0007_+0001.fbx` |
| `Buildings/duion_bricks_classic_02_D_exp_png_f5f5dc_pro_2161_exp_png.uasset` | Building material instance | 68091 | `corridor_tiles_baked/tile_+0007_+0001.fbx` |
| `Buildings/duion_bricks_classic_02_D_exp_png_ff0000_pro_2157_exp_png.uasset` | Building material instance | 68298 | `corridor_tiles_baked/tile_+0011_+0001.fbx` |
| `Buildings/duion_bricks_classic_02_D_exp_png_ff0000_pro_2161_exp_png.uasset` | Building material instance | 67865 | `corridor_tiles_baked/tile_+0011_+0001.fbx` |
| `Buildings/duion_concrete_rough_01_D_exp_png_b2b2a6_pro_2157_exp_png.uasset` | Building material instance | 68313 | `corridor_tiles_baked/tile_+0013_+0002.fbx` |
| `Buildings/duion_concrete_rough_01_D_exp_png_b2b2a6_pro_2161_exp_png.uasset` | Building material instance | 67983 | `corridor_tiles_baked/tile_+0013_+0002.fbx` |
| `Buildings/duion_concrete_stripes_03_D_exp_png_b2b2a6_pro_2157_exp_png.uasset` | Building material instance | 68338 | `corridor_tiles_baked/tile_+0013_+0002.fbx` |
| `Buildings/duion_concrete_stripes_03_D_exp_png_b2b2a6_pro_2161_exp_png.uasset` | Building material instance | 67867 | `corridor_tiles_baked/tile_+0013_+0002.fbx` |
| `Buildings/duion_concrete_stripes_03_D_exp_png_c8c2b6_pro_2353_exp_png.uasset` | Building material instance | 66023 | `corridor_tiles_baked/tile_-0012_-0002.fbx` |
| `Buildings/duion_metal_panels_01_D_exp_png_afafaf_pro_2901_exp_png.uasset` | Building material instance | 66207 | `corridor_tiles_baked/tile_+0013_+0002.fbx` |
| `Buildings/duion_metal_panels_01_D_exp_png_c8c2b6_pro_2353_exp_png.uasset` | Building material instance | 65357 | `corridor_tiles_baked/tile_+0013_+0003.fbx` |
| `Buildings/duion_metal_panels_01_D_exp_png_ffffff_pro_2157_exp_png.uasset` | Building material instance | 68062 | `corridor_tiles_baked/tile_+0007_+0001.fbx` |
| `Buildings/duion_metal_panels_01_D_exp_png_ffffff_pro_2161_exp_png.uasset` | Building material instance | 68020 | `corridor_tiles_baked/tile_+0007_+0001.fbx` |
| `Buildings/duion_plaster_sprinkled_01_D_exp_png_008000_pro_2353_exp_png.uasset` | Building material instance | 65888 | `corridor_tiles_baked/tile_-0010_-0003.fbx` |
| `Buildings/duion_plaster_sprinkled_01_D_exp_png_a3865f_pro_2157_exp_png.uasset` | Building material instance | 58787 | `corridor_tiles_baked/tile_+0000_+0000_r+000+000.fbx` |
| `Buildings/duion_plaster_sprinkled_01_D_exp_png_a3865f_pro_2161_exp_png.uasset` | Building material instance | 58787 | `corridor_tiles_baked/tile_+0000_+0000_r+000+000.fbx` |
| `Buildings/duion_plaster_sprinkled_01_D_exp_png_a3865f_pro_2353_exp_png.uasset` | Building material instance | 58787 | `corridor_tiles_baked/tile_+0000_+0000_r+000+000.fbx` |
| `Buildings/duion_plaster_sprinkled_01_D_exp_png_a3865f_pro_2901_exp_png.uasset` | Building material instance | 58787 | `corridor_tiles_baked/tile_+0000_+0000_r+000+000.fbx` |
| `Buildings/duion_plaster_sprinkled_01_D_exp_png_a3865f_pro_6908_exp_png.uasset` | Building material instance | 58787 | `corridor_tiles_baked/tile_+0000_+0000_r+000+000.fbx` |
| `Buildings/duion_plaster_sprinkled_01_D_exp_png_b8a594_pro_2157_exp_png.uasset` | Building material instance | 68201 | `corridor_tiles_baked/tile_+0000_-0001.fbx` |
| `Buildings/duion_plaster_sprinkled_01_D_exp_png_b8a594_pro_2161_exp_png.uasset` | Building material instance | 67779 | `corridor_tiles_baked/tile_+0000_-0001.fbx` |
| `Buildings/duion_plaster_sprinkled_01_D_exp_png_b8a594_pro_2353_exp_png.uasset` | Building material instance | 58787 | `corridor_tiles_baked/tile_+0000_+0000_r+000+000.fbx` |
| `Buildings/duion_plaster_sprinkled_01_D_exp_png_b8a594_pro_2901_exp_png.uasset` | Building material instance | 58787 | `corridor_tiles_baked/tile_+0000_+0000_r+000+000.fbx` |
| `Buildings/duion_plaster_sprinkled_01_D_exp_png_b8a594_pro_6908_exp_png.uasset` | Building material instance | 58787 | `corridor_tiles_baked/tile_+0000_+0000_r+000+000.fbx` |
| `Buildings/duion_plaster_sprinkled_01_D_exp_png_cfbc8e_pro_2157_exp_png.uasset` | Building material instance | 58787 | `corridor_tiles_baked/tile_+0000_+0000_r+000+000.fbx` |
| `Buildings/duion_plaster_sprinkled_01_D_exp_png_cfbc8e_pro_2161_exp_png.uasset` | Building material instance | 58787 | `corridor_tiles_baked/tile_+0000_+0000_r+000+000.fbx` |
| `Buildings/duion_plaster_sprinkled_01_D_exp_png_cfbc8e_pro_2353_exp_png.uasset` | Building material instance | 65747 | `corridor_tiles_baked/tile_+0000_-0001.fbx` |
| `Buildings/duion_plaster_sprinkled_01_D_exp_png_cfbc8e_pro_2901_exp_png.uasset` | Building material instance | 65581 | `corridor_tiles_baked/tile_+0000_-0001.fbx` |
| `Buildings/duion_plaster_sprinkled_01_D_exp_png_cfbc8e_pro_6908_exp_png.uasset` | Building material instance | 58787 | `corridor_tiles_baked/tile_+0000_+0000_r+000+000.fbx` |
| `Buildings/duion_plaster_sprinkled_01_D_exp_png_ffffff_pro_2157_exp_png.uasset` | Building material instance | 68226 | `corridor_tiles_baked/tile_+0013_+0002.fbx` |
| `Buildings/duion_plaster_sprinkled_01_D_exp_png_ffffff_pro_2161_exp_png.uasset` | Building material instance | 67848 | `corridor_tiles_baked/tile_+0013_+0002.fbx` |
| `Buildings/duion_plaster_stucco_01_D_exp_png_a3865f_pro_2157_exp_png.uasset` | Building material instance | 68360 | `corridor_tiles_baked/tile_+0000_-0001.fbx` |
| `Buildings/duion_plaster_stucco_01_D_exp_png_a3865f_pro_2161_exp_png.uasset` | Building material instance | 67892 | `corridor_tiles_baked/tile_+0000_-0001.fbx` |
| `Buildings/duion_plaster_stucco_01_D_exp_png_a3865f_pro_2353_exp_png.uasset` | Building material instance | 65419 | `corridor_tiles_baked/tile_+0000_-0001.fbx` |
| `Buildings/duion_plaster_stucco_01_D_exp_png_a3865f_pro_2901_exp_png.uasset` | Building material instance | 58676 | `corridor_tiles_baked/tile_+0000_+0000_r+000+000.fbx` |
| `Buildings/duion_plaster_stucco_01_D_exp_png_a3865f_pro_6908_exp_png.uasset` | Building material instance | 58676 | `corridor_tiles_baked/tile_+0000_+0000_r+000+000.fbx` |
| `Buildings/duion_plaster_stucco_01_D_exp_png_b8a594_pro_2157_exp_png.uasset` | Building material instance | 68401 | `corridor_tiles_baked/tile_+0000_-0001.fbx` |
| `Buildings/duion_plaster_stucco_01_D_exp_png_b8a594_pro_2161_exp_png.uasset` | Building material instance | 67832 | `corridor_tiles_baked/tile_+0000_-0001.fbx` |
| `Buildings/duion_plaster_stucco_01_D_exp_png_b8a594_pro_2353_exp_png.uasset` | Building material instance | 58676 | `corridor_tiles_baked/tile_+0000_+0000_r+000+000.fbx` |
| `Buildings/duion_plaster_stucco_01_D_exp_png_b8a594_pro_2901_exp_png.uasset` | Building material instance | 65327 | `corridor_tiles_baked/tile_+0000_-0001.fbx` |
| `Buildings/duion_plaster_stucco_01_D_exp_png_b8a594_pro_6908_exp_png.uasset` | Building material instance | 58676 | `corridor_tiles_baked/tile_+0000_+0000_r+000+000.fbx` |
| `Buildings/duion_plaster_stucco_01_D_exp_png_cfbc8e_pro_2157_exp_png.uasset` | Building material instance | 58676 | `corridor_tiles_baked/tile_+0000_+0000_r+000+000.fbx` |
| `Buildings/duion_plaster_stucco_01_D_exp_png_cfbc8e_pro_2161_exp_png.uasset` | Building material instance | 58676 | `corridor_tiles_baked/tile_+0000_+0000_r+000+000.fbx` |
| `Buildings/duion_plaster_stucco_01_D_exp_png_cfbc8e_pro_2353_exp_png.uasset` | Building material instance | 65362 | `corridor_tiles_baked/tile_+0000_-0001.fbx` |
| `Buildings/duion_plaster_stucco_01_D_exp_png_cfbc8e_pro_2901_exp_png.uasset` | Building material instance | 58676 | `corridor_tiles_baked/tile_+0000_+0000_r+000+000.fbx` |
| `Buildings/duion_plaster_stucco_01_D_exp_png_cfbc8e_pro_6908_exp_png.uasset` | Building material instance | 58676 | `corridor_tiles_baked/tile_+0000_+0000_r+000+000.fbx` |
| `Buildings/f5f5dc_brick_png.uasset` | Building material instance | 62500 | `corridor_tiles_baked/tile_+0007_+0001.fbx` |
| `Buildings/ff0000_brick_jpg.uasset` | Building material instance | 61589 | `corridor_tiles_baked/tile_+0011_+0002.fbx` |
| `Buildings/ff0000_brick_png.uasset` | Building material instance | 60316 | `corridor_tiles_baked/tile_+0011_+0001.fbx` |
| `Buildings/ffffff_brick_jpg.uasset` | Building material instance | 62020 | `corridor_tiles_baked/tile_+0013_+0002.fbx` |
| `Buildings/ffffff_concrete_png.uasset` | Building material instance | 61704 | `corridor_tiles_baked/tile_+0013_+0002.fbx` |
| `Buildings/ffffff_metal_png.uasset` | Building material instance | 61898 | `corridor_tiles_baked/tile_+0013_+0003.fbx` |
| `Buildings/ffffff_roof_tiles_png.uasset` | Building material instance | 63235 | `corridor_tiles_baked/tile_+0013_+0002.fbx` |
| `Buildings/grey.uasset` | Building material instance | 58733 | `corridor_tiles_baked/tile_-0008_-0003.fbx` |
| `Buildings/roof.uasset` | Building material instance | 58815 | `corridor_tiles_baked/tile_+0000_+0000_r+000+000.fbx` |
| `Buildings/tan.uasset` | Building material instance | 58720 | `corridor_tiles_baked/tile_+0013_+0002.fbx` |
| `Buildings/tile_+0000_+0000_r+000+000.uasset` | Building tile mesh | 1183469 | `corridor_tiles_baked/tile_+0000_+0000_r+000+000.fbx` |
| `Buildings/tile_+0000_+0000_r+000-001.uasset` | Building tile mesh | 111682 | `corridor_tiles_baked/tile_+0000_+0000_r+000-001.fbx` |
| `Buildings/tile_+0000_+0000_r+001+000.uasset` | Building tile mesh | 107794 | `corridor_tiles_baked/tile_+0000_+0000_r+001+000.fbx` |
| `Buildings/tile_+0000_-0001.uasset` | Building tile mesh | 1841321 | `corridor_tiles_baked/tile_+0000_-0001.fbx` |
| `Buildings/tile_+0000_-0002.uasset` | Building tile mesh | 694065 | `corridor_tiles_baked/tile_+0000_-0002.fbx` |
| `Buildings/tile_+0001_+0000.uasset` | Building tile mesh | 1412701 | `corridor_tiles_baked/tile_+0001_+0000.fbx` |
| `Buildings/tile_+0001_-0001.uasset` | Building tile mesh | 1953782 | `corridor_tiles_baked/tile_+0001_-0001.fbx` |
| `Buildings/tile_+0001_-0002.uasset` | Building tile mesh | 242242 | `corridor_tiles_baked/tile_+0001_-0002.fbx` |
| `Buildings/tile_+0002_+0000.uasset` | Building tile mesh | 1408685 | `corridor_tiles_baked/tile_+0002_+0000.fbx` |
| `Buildings/tile_+0002_+0001.uasset` | Building tile mesh | 406932 | `corridor_tiles_baked/tile_+0002_+0001.fbx` |
| `Buildings/tile_+0002_-0001.uasset` | Building tile mesh | 1501657 | `corridor_tiles_baked/tile_+0002_-0001.fbx` |
| `Buildings/tile_+0003_+0000.uasset` | Building tile mesh | 1646707 | `corridor_tiles_baked/tile_+0003_+0000.fbx` |
| `Buildings/tile_+0003_+0001.uasset` | Building tile mesh | 1005153 | `corridor_tiles_baked/tile_+0003_+0001.fbx` |
| `Buildings/tile_+0003_-0001.uasset` | Building tile mesh | 1318723 | `corridor_tiles_baked/tile_+0003_-0001.fbx` |
| `Buildings/tile_+0004_+0000.uasset` | Building tile mesh | 2275010 | `corridor_tiles_baked/tile_+0004_+0000.fbx` |
| `Buildings/tile_+0004_+0001.uasset` | Building tile mesh | 946914 | `corridor_tiles_baked/tile_+0004_+0001.fbx` |
| `Buildings/tile_+0004_-0001.uasset` | Building tile mesh | 1337403 | `corridor_tiles_baked/tile_+0004_-0001.fbx` |
| `Buildings/tile_+0005_+0000.uasset` | Building tile mesh | 2440996 | `corridor_tiles_baked/tile_+0005_+0000.fbx` |
| `Buildings/tile_+0005_+0001.uasset` | Building tile mesh | 1305268 | `corridor_tiles_baked/tile_+0005_+0001.fbx` |
| `Buildings/tile_+0005_-0001.uasset` | Building tile mesh | 309726 | `corridor_tiles_baked/tile_+0005_-0001.fbx` |
| `Buildings/tile_+0006_+0000.uasset` | Building tile mesh | 988807 | `corridor_tiles_baked/tile_+0006_+0000.fbx` |
| `Buildings/tile_+0006_+0001.uasset` | Building tile mesh | 895380 | `corridor_tiles_baked/tile_+0006_+0001.fbx` |
| `Buildings/tile_+0006_+0002.uasset` | Building tile mesh | 278916 | `corridor_tiles_baked/tile_+0006_+0002.fbx` |
| `Buildings/tile_+0007_+0000.uasset` | Building tile mesh | 740748 | `corridor_tiles_baked/tile_+0007_+0000.fbx` |
| `Buildings/tile_+0007_+0001.uasset` | Building tile mesh | 1392680 | `corridor_tiles_baked/tile_+0007_+0001.fbx` |
| `Buildings/tile_+0007_+0002.uasset` | Building tile mesh | 961885 | `corridor_tiles_baked/tile_+0007_+0002.fbx` |
| `Buildings/tile_+0008_+0000.uasset` | Building tile mesh | 568561 | `corridor_tiles_baked/tile_+0008_+0000.fbx` |
| `Buildings/tile_+0008_+0001.uasset` | Building tile mesh | 1283812 | `corridor_tiles_baked/tile_+0008_+0001.fbx` |
| `Buildings/tile_+0008_+0002.uasset` | Building tile mesh | 1589037 | `corridor_tiles_baked/tile_+0008_+0002.fbx` |
| `Buildings/tile_+0008_+0003.uasset` | Building tile mesh | 220144 | `corridor_tiles_baked/tile_+0008_+0003.fbx` |
| `Buildings/tile_+0009_+0000.uasset` | Building tile mesh | 279758 | `corridor_tiles_baked/tile_+0009_+0000.fbx` |
| `Buildings/tile_+0009_+0001.uasset` | Building tile mesh | 1215970 | `corridor_tiles_baked/tile_+0009_+0001.fbx` |
| `Buildings/tile_+0009_+0002.uasset` | Building tile mesh | 2234511 | `corridor_tiles_baked/tile_+0009_+0002.fbx` |
| `Buildings/tile_+0009_+0003.uasset` | Building tile mesh | 779766 | `corridor_tiles_baked/tile_+0009_+0003.fbx` |
| `Buildings/tile_+0010_+0001.uasset` | Building tile mesh | 2333870 | `corridor_tiles_baked/tile_+0010_+0001.fbx` |
| `Buildings/tile_+0010_+0002.uasset` | Building tile mesh | 2077509 | `corridor_tiles_baked/tile_+0010_+0002.fbx` |
| `Buildings/tile_+0010_+0003.uasset` | Building tile mesh | 546617 | `corridor_tiles_baked/tile_+0010_+0003.fbx` |
| `Buildings/tile_+0011_+0001.uasset` | Building tile mesh | 1991510 | `corridor_tiles_baked/tile_+0011_+0001.fbx` |
| `Buildings/tile_+0011_+0002.uasset` | Building tile mesh | 1576590 | `corridor_tiles_baked/tile_+0011_+0002.fbx` |
| `Buildings/tile_+0011_+0003.uasset` | Building tile mesh | 452461 | `corridor_tiles_baked/tile_+0011_+0003.fbx` |
| `Buildings/tile_+0012_+0001.uasset` | Building tile mesh | 894653 | `corridor_tiles_baked/tile_+0012_+0001.fbx` |
| `Buildings/tile_+0012_+0002.uasset` | Building tile mesh | 1582330 | `corridor_tiles_baked/tile_+0012_+0002.fbx` |
| `Buildings/tile_+0012_+0003.uasset` | Building tile mesh | 878944 | `corridor_tiles_baked/tile_+0012_+0003.fbx` |
| `Buildings/tile_+0013_+0001.uasset` | Building tile mesh | 984920 | `corridor_tiles_baked/tile_+0013_+0001.fbx` |
| `Buildings/tile_+0013_+0002.uasset` | Building tile mesh | 1509778 | `corridor_tiles_baked/tile_+0013_+0002.fbx` |
| `Buildings/tile_+0013_+0003.uasset` | Building tile mesh | 971782 | `corridor_tiles_baked/tile_+0013_+0003.fbx` |
| `Buildings/tile_+0014_+0001.uasset` | Building tile mesh | 397439 | `corridor_tiles_baked/tile_+0014_+0001.fbx` |
| `Buildings/tile_+0014_+0002.uasset` | Building tile mesh | 638522 | `corridor_tiles_baked/tile_+0014_+0002.fbx` |
| `Buildings/tile_+0014_+0003.uasset` | Building tile mesh | 229424 | `corridor_tiles_baked/tile_+0014_+0003.fbx` |
| `Buildings/tile_-0001_+0000.uasset` | Building tile mesh | 1263546 | `corridor_tiles_baked/tile_-0001_+0000.fbx` |
| `Buildings/tile_-0001_-0001.uasset` | Building tile mesh | 1444613 | `corridor_tiles_baked/tile_-0001_-0001.fbx` |
| `Buildings/tile_-0001_-0002.uasset` | Building tile mesh | 753517 | `corridor_tiles_baked/tile_-0001_-0002.fbx` |
| `Buildings/tile_-0002_+0000.uasset` | Building tile mesh | 623076 | `corridor_tiles_baked/tile_-0002_+0000.fbx` |
| `Buildings/tile_-0002_-0001.uasset` | Building tile mesh | 948613 | `corridor_tiles_baked/tile_-0002_-0001.fbx` |
| `Buildings/tile_-0002_-0002.uasset` | Building tile mesh | 666530 | `corridor_tiles_baked/tile_-0002_-0002.fbx` |
| `Buildings/tile_-0003_+0000.uasset` | Building tile mesh | 115813 | `corridor_tiles_baked/tile_-0003_+0000.fbx` |
| `Buildings/tile_-0003_-0001.uasset` | Building tile mesh | 729398 | `corridor_tiles_baked/tile_-0003_-0001.fbx` |
| `Buildings/tile_-0003_-0002.uasset` | Building tile mesh | 392521 | `corridor_tiles_baked/tile_-0003_-0002.fbx` |
| `Buildings/tile_-0003_-0003.uasset` | Building tile mesh | 163546 | `corridor_tiles_baked/tile_-0003_-0003.fbx` |
| `Buildings/tile_-0004_-0001.uasset` | Building tile mesh | 589042 | `corridor_tiles_baked/tile_-0004_-0001.fbx` |
| `Buildings/tile_-0004_-0002.uasset` | Building tile mesh | 755445 | `corridor_tiles_baked/tile_-0004_-0002.fbx` |
| `Buildings/tile_-0004_-0003.uasset` | Building tile mesh | 361397 | `corridor_tiles_baked/tile_-0004_-0003.fbx` |
| `Buildings/tile_-0005_-0001.uasset` | Building tile mesh | 1005830 | `corridor_tiles_baked/tile_-0005_-0001.fbx` |
| `Buildings/tile_-0005_-0002.uasset` | Building tile mesh | 645716 | `corridor_tiles_baked/tile_-0005_-0002.fbx` |
| `Buildings/tile_-0005_-0003.uasset` | Building tile mesh | 446894 | `corridor_tiles_baked/tile_-0005_-0003.fbx` |
| `Buildings/tile_-0006_-0001.uasset` | Building tile mesh | 407026 | `corridor_tiles_baked/tile_-0006_-0001.fbx` |
| `Buildings/tile_-0006_-0002.uasset` | Building tile mesh | 527060 | `corridor_tiles_baked/tile_-0006_-0002.fbx` |
| `Buildings/tile_-0006_-0003.uasset` | Building tile mesh | 255057 | `corridor_tiles_baked/tile_-0006_-0003.fbx` |
| `Buildings/tile_-0007_-0001.uasset` | Building tile mesh | 146544 | `corridor_tiles_baked/tile_-0007_-0001.fbx` |
| `Buildings/tile_-0007_-0002.uasset` | Building tile mesh | 377843 | `corridor_tiles_baked/tile_-0007_-0002.fbx` |
| `Buildings/tile_-0007_-0003.uasset` | Building tile mesh | 263336 | `corridor_tiles_baked/tile_-0007_-0003.fbx` |
| `Buildings/tile_-0007_-0004.uasset` | Building tile mesh | 89678 | `corridor_tiles_baked/tile_-0007_-0004.fbx` |
| `Buildings/tile_-0008_-0002.uasset` | Building tile mesh | 930250 | `corridor_tiles_baked/tile_-0008_-0002.fbx` |
| `Buildings/tile_-0008_-0003.uasset` | Building tile mesh | 1092523 | `corridor_tiles_baked/tile_-0008_-0003.fbx` |
| `Buildings/tile_-0008_-0004.uasset` | Building tile mesh | 533421 | `corridor_tiles_baked/tile_-0008_-0004.fbx` |
| `Buildings/tile_-0009_-0001.uasset` | Building tile mesh | 105967 | `corridor_tiles_baked/tile_-0009_-0001.fbx` |
| `Buildings/tile_-0009_-0002.uasset` | Building tile mesh | 2042297 | `corridor_tiles_baked/tile_-0009_-0002.fbx` |
| `Buildings/tile_-0009_-0003.uasset` | Building tile mesh | 2195267 | `corridor_tiles_baked/tile_-0009_-0003.fbx` |
| `Buildings/tile_-0009_-0004.uasset` | Building tile mesh | 784468 | `corridor_tiles_baked/tile_-0009_-0004.fbx` |
| `Buildings/tile_-0010_-0001.uasset` | Building tile mesh | 254608 | `corridor_tiles_baked/tile_-0010_-0001.fbx` |
| `Buildings/tile_-0010_-0002.uasset` | Building tile mesh | 1256253 | `corridor_tiles_baked/tile_-0010_-0002.fbx` |
| `Buildings/tile_-0010_-0003.uasset` | Building tile mesh | 2129055 | `corridor_tiles_baked/tile_-0010_-0003.fbx` |
| `Buildings/tile_-0010_-0004.uasset` | Building tile mesh | 214165 | `corridor_tiles_baked/tile_-0010_-0004.fbx` |
| `Buildings/tile_-0011_+0000.uasset` | Building tile mesh | 268687 | `corridor_tiles_baked/tile_-0011_+0000.fbx` |
| `Buildings/tile_-0011_-0001.uasset` | Building tile mesh | 504018 | `corridor_tiles_baked/tile_-0011_-0001.fbx` |
| `Buildings/tile_-0011_-0002.uasset` | Building tile mesh | 1081769 | `corridor_tiles_baked/tile_-0011_-0002.fbx` |
| `Buildings/tile_-0011_-0003.uasset` | Building tile mesh | 1270108 | `corridor_tiles_baked/tile_-0011_-0003.fbx` |
| `Buildings/tile_-0012_+0000.uasset` | Building tile mesh | 372388 | `corridor_tiles_baked/tile_-0012_+0000.fbx` |
| `Buildings/tile_-0012_-0001.uasset` | Building tile mesh | 877001 | `corridor_tiles_baked/tile_-0012_-0001.fbx` |
| `Buildings/tile_-0012_-0002.uasset` | Building tile mesh | 944775 | `corridor_tiles_baked/tile_-0012_-0002.fbx` |
| `Buildings/tile_-0013_+0000.uasset` | Building tile mesh | 1415349 | `corridor_tiles_baked/tile_-0013_+0000.fbx` |
| `Buildings/tile_-0013_+0001.uasset` | Building tile mesh | 446228 | `corridor_tiles_baked/tile_-0013_+0001.fbx` |
| `Buildings/tile_-0013_-0001.uasset` | Building tile mesh | 1128074 | `corridor_tiles_baked/tile_-0013_-0001.fbx` |
| `Buildings/tile_-0013_-0002.uasset` | Building tile mesh | 1201474 | `corridor_tiles_baked/tile_-0013_-0002.fbx` |
| `Buildings/tile_-0014_+0000.uasset` | Building tile mesh | 1121181 | `corridor_tiles_baked/tile_-0014_+0000.fbx` |
| `Buildings/tile_-0014_+0001.uasset` | Building tile mesh | 1406594 | `corridor_tiles_baked/tile_-0014_+0001.fbx` |
| `Buildings/tile_-0014_-0001.uasset` | Building tile mesh | 1320599 | `corridor_tiles_baked/tile_-0014_-0001.fbx` |
| `Buildings/tile_-0014_-0002.uasset` | Building tile mesh | 944701 | `corridor_tiles_baked/tile_-0014_-0002.fbx` |
| `Buildings/tile_-0015_+0000.uasset` | Building tile mesh | 470717 | `corridor_tiles_baked/tile_-0015_+0000.fbx` |
| `Buildings/tile_-0015_+0001.uasset` | Building tile mesh | 150879 | `corridor_tiles_baked/tile_-0015_+0001.fbx` |
| `Buildings/wall.uasset` | Building material instance | 54351 | `corridor_tiles_baked/tile_+0000_+0000_r+000+000.fbx` |
| `Scene/CorridorTerrain.umap` | Level | 15384 |  |
| `Scene/CorridorTerrain_HLOD0_Instancing.uasset` | HLOD layer | 1592 |  |
| `Scene/HLOD_Buildings.uasset` | HLOD layer (Instancing, for the buildings; Tools/unreal/corridor_streaming.py) | 1449 |  |
| `Scene/HLOD_Trees.uasset` | HLOD layer (Instancing, for the trees; Tools/unreal/corridor_streaming.py) | 1433 |  |
| `Vegetation/Rocks/cobble_01.uasset` | Rock mesh | 88990 | `corridor_rocks/cobble_01.fbx` |
| `Vegetation/Rocks/cobble_02.uasset` | Rock mesh | 88874 | `corridor_rocks/cobble_02.fbx` |
| `Vegetation/Rocks/cobble_03.uasset` | Rock mesh | 88924 | `corridor_rocks/cobble_03.fbx` |
| `Vegetation/Rocks/cobble_04.uasset` | Rock mesh | 88697 | `corridor_rocks/cobble_04.fbx` |
| `Vegetation/Rocks/cobble_05.uasset` | Rock mesh | 88923 | `corridor_rocks/cobble_05.fbx` |
| `Vegetation/Rocks/erratic_01.uasset` | Rock mesh | 89450 | `corridor_rocks/erratic_01.fbx` |
| `Vegetation/Rocks/erratic_02.uasset` | Rock mesh | 90188 | `corridor_rocks/erratic_02.fbx` |
| `Vegetation/Rocks/erratic_03.uasset` | Rock mesh | 90114 | `corridor_rocks/erratic_03.fbx` |
| `Vegetation/Rocks/erratic_04.uasset` | Rock mesh | 89979 | `corridor_rocks/erratic_04.fbx` |
| `Vegetation/Rocks/erratic_05.uasset` | Rock mesh | 88537 | `corridor_rocks/erratic_05.fbx` |
| `Vegetation/Rocks/fieldstone_01.uasset` | Rock mesh | 88959 | `corridor_rocks/fieldstone_01.fbx` |
| `Vegetation/Rocks/fieldstone_02.uasset` | Rock mesh | 89722 | `corridor_rocks/fieldstone_02.fbx` |
| `Vegetation/Rocks/fieldstone_03.uasset` | Rock mesh | 90352 | `corridor_rocks/fieldstone_03.fbx` |
| `Vegetation/Rocks/fieldstone_04.uasset` | Rock mesh | 89420 | `corridor_rocks/fieldstone_04.fbx` |
| `Vegetation/Rocks/fieldstone_05.uasset` | Rock mesh | 88349 | `corridor_rocks/fieldstone_05.fbx` |
| `Vegetation/Rocks/glacial_boulder_01.uasset` | Rock mesh | 90918 | `corridor_rocks/glacial_boulder_01.fbx` |
| `Vegetation/Rocks/glacial_boulder_02.uasset` | Rock mesh | 89871 | `corridor_rocks/glacial_boulder_02.fbx` |
| `Vegetation/Rocks/glacial_boulder_03.uasset` | Rock mesh | 88569 | `corridor_rocks/glacial_boulder_03.fbx` |
| `Vegetation/Rocks/glacial_boulder_04.uasset` | Rock mesh | 88451 | `corridor_rocks/glacial_boulder_04.fbx` |
| `Vegetation/Rocks/glacial_boulder_05.uasset` | Rock mesh | 88861 | `corridor_rocks/glacial_boulder_05.fbx` |
| `Vegetation/Rocks/limestone_slab_01.uasset` | Rock mesh | 89108 | `corridor_rocks/limestone_slab_01.fbx` |
| `Vegetation/Rocks/limestone_slab_02.uasset` | Rock mesh | 88327 | `corridor_rocks/limestone_slab_02.fbx` |
| `Vegetation/Rocks/limestone_slab_03.uasset` | Rock mesh | 89440 | `corridor_rocks/limestone_slab_03.fbx` |
| `Vegetation/Rocks/limestone_slab_04.uasset` | Rock mesh | 90139 | `corridor_rocks/limestone_slab_04.fbx` |
| `Vegetation/Rocks/limestone_slab_05.uasset` | Rock mesh | 89368 | `corridor_rocks/limestone_slab_05.fbx` |
| `Vegetation/Rocks/outcrop_01.uasset` | Rock mesh | 89094 | `corridor_rocks/outcrop_01.fbx` |
| `Vegetation/Rocks/outcrop_02.uasset` | Rock mesh | 87893 | `corridor_rocks/outcrop_02.fbx` |
| `Vegetation/Rocks/outcrop_03.uasset` | Rock mesh | 87326 | `corridor_rocks/outcrop_03.fbx` |
| `Vegetation/Rocks/outcrop_04.uasset` | Rock mesh | 89222 | `corridor_rocks/outcrop_04.fbx` |
| `Vegetation/Rocks/outcrop_05.uasset` | Rock mesh | 88622 | `corridor_rocks/outcrop_05.fbx` |
| `Vegetation/Rocks/RockVertexColour.uasset` | Rock material instance | 59415 | `corridor_rocks/cobble_01.fbx` |
| `Vegetation/Trees/acer_01.uasset` | Tree mesh | 190944 | `corridor_trees/acer_01.fbx` |
| `Vegetation/Trees/acer_02.uasset` | Tree mesh | 190659 | `corridor_trees/acer_02.fbx` |
| `Vegetation/Trees/acer_03.uasset` | Tree mesh | 176244 | `corridor_trees/acer_03.fbx` |
| `Vegetation/Trees/balsam_fir_01.uasset` | Tree mesh | 5583762 | `corridor_trees/balsam_fir_01.fbx` |
| `Vegetation/Trees/balsam_fir_02.uasset` | Tree mesh | 4960111 | `corridor_trees/balsam_fir_02.fbx` |
| `Vegetation/Trees/balsam_fir_03.uasset` | Tree mesh | 5202677 | `corridor_trees/balsam_fir_03.fbx` |
| `Vegetation/Trees/black_oak_01.uasset` | Tree mesh | 8810968 | `corridor_trees/black_oak_01.fbx` |
| `Vegetation/Trees/black_oak_02.uasset` | Tree mesh | 6783135 | `corridor_trees/black_oak_02.fbx` |
| `Vegetation/Trees/black_oak_03.uasset` | Tree mesh | 5990914 | `corridor_trees/black_oak_03.fbx` |
| `Vegetation/Trees/black_tupelo_01.uasset` | Tree mesh | 12718398 | `corridor_trees/black_tupelo_01.fbx` |
| `Vegetation/Trees/black_tupelo_02.uasset` | Tree mesh | 12773022 | `corridor_trees/black_tupelo_02.fbx` |
| `Vegetation/Trees/black_tupelo_03.uasset` | Tree mesh | 11781590 | `corridor_trees/black_tupelo_03.fbx` |
| `Vegetation/Trees/cambridge_oak_01.uasset` | Tree mesh | 13050485 | `corridor_trees/cambridge_oak_01.fbx` |
| `Vegetation/Trees/cambridge_oak_02.uasset` | Tree mesh | 16388514 | `corridor_trees/cambridge_oak_02.fbx` |
| `Vegetation/Trees/cambridge_oak_03.uasset` | Tree mesh | 10977157 | `corridor_trees/cambridge_oak_03.fbx` |
| `Vegetation/Trees/douglas_fir_01.uasset` | Tree mesh | 4249823 | `corridor_trees/douglas_fir_01.fbx` |
| `Vegetation/Trees/douglas_fir_02.uasset` | Tree mesh | 3982232 | `corridor_trees/douglas_fir_02.fbx` |
| `Vegetation/Trees/douglas_fir_03.uasset` | Tree mesh | 5201356 | `corridor_trees/douglas_fir_03.fbx` |
| `Vegetation/Trees/european_larch_01.uasset` | Tree mesh | 3092006 | `corridor_trees/european_larch_01.fbx` |
| `Vegetation/Trees/european_larch_02.uasset` | Tree mesh | 3794270 | `corridor_trees/european_larch_02.fbx` |
| `Vegetation/Trees/european_larch_03.uasset` | Tree mesh | 2040829 | `corridor_trees/european_larch_03.fbx` |
| `Vegetation/Trees/hill_cherry_01.uasset` | Tree mesh | 967031 | `corridor_trees/hill_cherry_01.fbx` |
| `Vegetation/Trees/hill_cherry_02.uasset` | Tree mesh | 1054588 | `corridor_trees/hill_cherry_02.fbx` |
| `Vegetation/Trees/hill_cherry_03.uasset` | Tree mesh | 882490 | `corridor_trees/hill_cherry_03.fbx` |
| `Vegetation/Trees/lombardy_poplar_01.uasset` | Tree mesh | 2032399 | `corridor_trees/lombardy_poplar_01.fbx` |
| `Vegetation/Trees/lombardy_poplar_02.uasset` | Tree mesh | 2013299 | `corridor_trees/lombardy_poplar_02.fbx` |
| `Vegetation/Trees/lombardy_poplar_03.uasset` | Tree mesh | 1596463 | `corridor_trees/lombardy_poplar_03.fbx` |
| `Vegetation/Trees/quaking_aspen_01.uasset` | Tree mesh | 2004105 | `corridor_trees/quaking_aspen_01.fbx` |
| `Vegetation/Trees/quaking_aspen_02.uasset` | Tree mesh | 1907457 | `corridor_trees/quaking_aspen_02.fbx` |
| `Vegetation/Trees/quaking_aspen_03.uasset` | Tree mesh | 2233854 | `corridor_trees/quaking_aspen_03.fbx` |
| `Vegetation/Trees/sassafras_01.uasset` | Tree mesh | 6550096 | `corridor_trees/sassafras_01.fbx` |
| `Vegetation/Trees/sassafras_02.uasset` | Tree mesh | 7322382 | `corridor_trees/sassafras_02.fbx` |
| `Vegetation/Trees/sassafras_03.uasset` | Tree mesh | 5028198 | `corridor_trees/sassafras_03.fbx` |
| `Vegetation/Trees/silver_birch_01.uasset` | Tree mesh | 2236790 | `corridor_trees/silver_birch_01.fbx` |
| `Vegetation/Trees/silver_birch_02.uasset` | Tree mesh | 2648403 | `corridor_trees/silver_birch_02.fbx` |
| `Vegetation/Trees/silver_birch_03.uasset` | Tree mesh | 3060680 | `corridor_trees/silver_birch_03.fbx` |
| `Vegetation/Trees/small_pine_01.uasset` | Tree mesh | 392905 | `corridor_trees/small_pine_01.fbx` |
| `Vegetation/Trees/small_pine_02.uasset` | Tree mesh | 349903 | `corridor_trees/small_pine_02.fbx` |
| `Vegetation/Trees/small_pine_03.uasset` | Tree mesh | 392213 | `corridor_trees/small_pine_03.fbx` |
| `Vegetation/Trees/weeping_willow_01.uasset` | Tree mesh | 16171240 | `corridor_trees/weeping_willow_01.fbx` |
| `Vegetation/Trees/weeping_willow_02.uasset` | Tree mesh | 17541899 | `corridor_trees/weeping_willow_02.fbx` |
| `Vegetation/Trees/weeping_willow_03.uasset` | Tree mesh | 21634521 | `corridor_trees/weeping_willow_03.fbx` |
