# Terrain and imagery tools

Download elevation data and aerial photography for any area, and turn them into Unreal Engine
Landscapes. Everything in this folder runs on Windows with nothing else installed: no Python, no
Unreal, no GIS. Unreal is needed only at the very end, to import what these tools make.

```
an area (a box or a KML outline)
   -> download elevation           download_3dep.exe, download_copernicus_dem.exe
   -> build the landscape          build_landscape.exe
   -> download aerial imagery      download_naip.exe, lined up with the landscape
   -> import into Unreal           a Landscape actor per segment, with the photos as its material
```

The window, `geodata_ui.exe`, runs all of it from one place. The four tools behind it can also be
run on their own from a command prompt, with exactly the options the window uses.

## Contents

1. [What is in this folder](#1-what-is-in-this-folder)
2. [Before you start](#2-before-you-start)
3. [Quick start with the window](#3-quick-start-with-the-window)
4. [The window in detail](#4-the-window-in-detail)
5. [Choosing the area](#5-choosing-the-area)
6. [Elevation data](#6-elevation-data)
7. [Using elevation data from anywhere else](#7-using-elevation-data-from-anywhere-else)
8. [Building the landscape](#8-building-the-landscape)
9. [Aerial imagery](#9-aerial-imagery)
10. [Importing into Unreal](#10-importing-into-unreal)
11. [Putting the imagery on the landscape](#11-putting-the-imagery-on-the-landscape)
12. [Command line reference](#12-command-line-reference)
13. [What ends up where](#13-what-ends-up-where)
14. [Data licences and attribution](#14-data-licences-and-attribution)
15. [Troubleshooting](#15-troubleshooting)

---

## 1. What is in this folder

| File | What it is |
| --- | --- |
| `geodata_ui.exe` | **The window.** Draw the area on a map, then download, build and fetch imagery with buttons |
| `download_3dep.exe` | Downloads USGS 3DEP bare-earth elevation, 1 m lidar down to 30 m. United States only |
| `download_copernicus_dem.exe` | Downloads the Copernicus 30 m or 90 m elevation model. Anywhere on Earth |
| `build_landscape.exe` | Turns any elevation rasters into Unreal Landscape heightmaps and a plan |
| `download_naip.exe` | Downloads USDA NAIP aerial photography, tiled to line up with a landscape. Lower 48 US states |
| `examples\mair_corridor_boundary.kml` | A sample area outline (a 60 km corridor in south-east Michigan) to try things with |
| `release.json` | Gives the window its title. Leave it here |
| `_internal\` | The runtime the tools share. Leave it here; the tools do not start without it |

The folder can be moved or copied anywhere, as a whole. The tools must stay beside `_internal`.

## 2. Before you start

**Windows 10 or 11, 64-bit, and an internet connection.** The downloads come from public servers
(USGS, Amazon Web Services for Copernicus, and the USGS imagery service). No account, login or key
is needed for any of them.

**Disk space.** Elevation and imagery are large. Some rough figures:

| What | Size |
| --- | --- |
| USGS 1 m lidar | 100 to 450 MB per 10 km by 10 km tile |
| USGS 10 m seamless | 100 to 450 MB per 1 by 1 degree tile |
| Copernicus 30 m | about 25 to 50 MB per 1 by 1 degree tile |
| A built landscape at 3 m per quad, 60 by 20 km | about 270 MB of heightmap |
| NAIP imagery at 0.5 m per pixel | about 8 MB per square kilometre |

Every download tool has a dry run (**Check sizes** and **Estimate** in the window) that lists what
would be fetched and how big it is, without fetching anything. Use it first.

**The first time you run a tool, Windows may stop it.** These programs are not signed by a
publisher, so Windows SmartScreen can show "Windows protected your PC". Choose *More info*, then
*Run anyway*. Antivirus software sometimes quarantines newly built programs like these; if a tool
suddenly will not start, or its `.exe` has become 0 bytes, restore it from your antivirus
quarantine (in Windows Security: *Virus and threat protection*, *Protection history*) and allow it.

## 3. Quick start with the window

Double-click `geodata_ui.exe`.

1. **Area of interest.** Either choose *Polygon* and *Browse...* to a KML or KMZ outline (try
   `examples\mair_corridor_boundary.kml`), or choose *Box* and draw one on the map: hold **Shift**
   and drag across the ground you want. The four numbers fill themselves in.
2. **Where the work goes.** Pick a *Working folder* with plenty of free space, and a *Name* for
   this area. Every step puts its output there and the next step finds it there.
3. **Elevation.** In the United States tick *USGS 3DEP 1 m lidar* **and** *USGS 3DEP 1/3
   arc-second, about 10 m (seamless)*. Anywhere else tick *Copernicus GLO-30*. Press **Check sizes**,
   read what it would download in the *Output* panel, then press **Download**.
4. **Landscape.** Leave *Metres per quad* at 3 for flight, or set 1 for ground level. Press
   **Plan only** to see how it will be laid out, then **Build**.
5. **Aerial imagery** (United States only). Press **Estimate**, then **Download**. It lines the
   photos up with the landscape you just built.

Or press **Run everything** after step 3's choices: it downloads the elevation, builds the
landscape and downloads the imagery, one after another. Downloads can take hours; **Cancel** stops
the step that is running, and every download resumes where it left off when run again.

What you have at the end, in the working folder:

```
dem_cache\        the elevation you downloaded
landscape\        <name>.json (the plan) and the .r16 heightmaps: these go to Unreal
naip\             <name>_naip.*.png aerial photo tiles and their index: these go to Unreal
```

Then [import into Unreal](#10-importing-into-unreal).

## 4. The window in detail

**The map.** Drag with the left button to pan, turn the wheel to zoom. Hold Shift and drag (or
tick *Draw box* and drag) to mark the area. *Find place* jumps to a town, address or landmark by
name. A KML you choose is drawn on the map, so you can see it before downloading anything. *Show on
map* draws whatever the fields say, so numbers typed into the box can be checked by eye.

**1. Area of interest**

| Field | Meaning |
| --- | --- |
| Polygon | A KML or KMZ outline. Downloads skip tiles it does not touch, and terrain outside it is blanked |
| Box | West, south, east and north edges in decimal degrees (WGS84). West must be less than east, south less than north |
| Grow by | Widens the area by this many metres on every side. Useful when the area is a route and you want a margin |

**2. Where the work goes.** The *Working folder*: *Open* shows it in Explorer, and the default is a
`work` folder beside the tools. *Name* (default `corridor`) names what is made: the plan and
heightmaps are `<name>.json` and `<name>.r16`, the imagery tiles `<name>_naip.*.png`. Give each area
its own name, or its own working folder.

**3. Elevation.** Tick one or more sources. Each ticked source is downloaded into
`<working folder>\dem_cache`. **Check sizes** lists every file and the total without downloading;
**Download** fetches them. Which to tick is explained in [section 6](#6-elevation-data).

**4. Landscape**

| Field | Default | Meaning |
| --- | --- | --- |
| Metres per quad | 3 | Ground distance between two neighbouring height points. See [Choosing the detail](#choosing-the-detail) |
| Largest segment | 8161 | The most vertices on a side of one Landscape actor. Unreal's recommended maximum is 8161 |
| World Partition grid | 4 | The grid Unreal splits each Landscape into for streaming. 0 leaves it unsplit |
| Datum | NAD83 | Which UTM zone definition to project into. NAD83 matches USGS data in North America; use WGS84 elsewhere |
| Origin | area | `area` puts the north-west corner of the landscape at Unreal 0,0. `projected` uses real map coordinates, which needs Large World Coordinates for areas far from 0,0 |
| Blank terrain outside the polygon | on | With a KML area, terrain outside the outline is flattened to the lowest height, and segments entirely outside it are not built |

**Plan only** prints the layout (how many segments, how big) and builds nothing. **Build** builds it
into `<working folder>\landscape`.

**5. Aerial imagery**

| Field | Default | Meaning |
| --- | --- | --- |
| Metres per pixel | 0.5 | Ground size of one pixel. NAIP is photographed at 0.3 to 0.6 m; finer than that only enlarges it |
| Tile pixels | 8192 | Size of each output image. 8192 suits Unreal virtual textures; use 4096 for ordinary textures |
| Request pixels | 2048 | Size of each request to the server (its limit is 4000) |
| Parallel requests | 4 | How many requests at once. It is a free public service; please keep this modest |

When a landscape plan exists in the working folder, the imagery is fetched on exactly the
landscape's grid. Without one, it uses the area instead.

**Output.** Everything the tools say appears here as it happens, and each step's full command is
printed first, so it can be repeated from a command prompt ([section 12](#12-command-line-reference)).
*Clear* empties it.

**Your entries are remembered** between runs, in `.geodata_ui.json` beside the tools.

## 5. Choosing the area

Every tool takes the area in one of two forms.

**A box**: `--bbox WEST SOUTH EAST NORTH` in decimal degrees, for example
`--bbox -83.705 42.296 -83.690 42.308`. Longitudes west of Greenwich and latitudes south of the
equator are negative.

**A polygon** in a KML or KMZ file: `--aoi site.kml`. A polygon does three things a box cannot:
downloads skip tiles that only touch the box's corners, terrain outside the outline is blanked, and
landscape segments that fall entirely outside it are not built. For a long, thin area that is most
of it.

To draw a polygon:

- **Google Earth Pro** (free desktop app): *Add*, *Polygon*, draw the outline, then right-click it
  under *Places*, *Save Place As...*, and save as KMZ or KML.
- **QGIS**: draw a polygon layer, then *Export*, *Save Features As...*, format *Keyhole Markup
  Language [KML]*.
- **Any GIS** that writes KML. KML coordinates are always WGS84 longitude and latitude.

`--buffer-m 500` (the window's *Grow by*) widens the area by 500 m on every side.

## 6. Elevation data

### United States: USGS 3DEP

The USGS 3D Elevation Program publishes free, public-domain, **bare-earth** elevation for the whole
country. Bare earth (buildings and trees removed) is what belongs under a Landscape that will have
buildings and trees placed on it.

| Product | Resolution | Coverage | Use it for |
| --- | --- | --- | --- |
| `1m` | 1 m lidar | Most of the US, project by project, with gaps | The detailed near terrain |
| `opr` | Native lidar, often 0.5 to 2 m | As delivered by each lidar project | When `1m` has nothing but a project exists |
| `19` | 1/9 arc-second, about 3 m | Partial; retired but still served | Filling gaps in `1m` |
| `13` | 1/3 arc-second, about 10 m | **Seamless, all of the US** | The fallback that guarantees no holes |
| `1` | 1 arc-second, about 30 m | Seamless | Wide surroundings and quick previews |

**Download two and let the builder combine them**: `1m` for detail and `13` so that every gap in
the lidar is filled rather than left as a hole. The builder uses the finest data wherever it exists.

Downloads resume if interrupted, skip files already present, retry when the USGS servers are busy,
and write a `download_3dep_<product>.json` listing what was fetched. Coverage can also be browsed at
https://apps.nationalmap.gov/downloader/ and downloaded there by hand; the builder does not care
where a file came from.

### Anywhere on Earth: Copernicus DEM

Copernicus GLO-30 is the most accurate free global elevation model, covering every land surface.
GLO-90 is the same at 90 m. Two things to know:

- **It is a surface model, not bare earth.** Heights include buildings and tree canopy, so in a city
  or forest the ground is lumpy where they stand. Prefer a national bare-earth model where one exists
  ([section 7](#7-using-elevation-data-from-anywhere-else)).
- **It requires attribution** in anything you publish ([section 14](#14-data-licences-and-attribution)).

Areas of open ocean have no tile; the tool says so and carries on.

## 7. Using elevation data from anywhere else

`build_landscape.exe` is not tied to the downloaders. It reads **any raster file** a GIS can open
(GeoTIFF, Erdas IMG, BIL/HDR, ASCII grid, HGT, VRT and more), in **any projection**, and reprojects
it itself. Put the files in the working folder's `dem_cache`, or point `--dem` at them.

| Dataset | Resolution | Surface or bare earth | Where to get it |
| --- | --- | --- | --- |
| ASTER GDEM v3 | 30 m | Surface | NASA Earthdata Search, product ASTGTM v003 (free login) |
| SRTM GL1 / NASADEM | 30 m | Surface | NASA Earthdata Search, or OpenTopography |
| ALOS World 3D (AW3D30) | 30 m | Surface | JAXA (free registration) |
| FABDEM | 30 m | **Bare earth** (Copernicus with buildings and trees removed) | University of Bristol; non-commercial licence |
| OpenTopography | Varies | Both | https://opentopography.org (free API key) |
| National lidar: UK, Netherlands (AHN), Canada (HRDEM) and others | 0.5 to 2 m | Usually both | Each national portal |
| Your own drone or lidar survey | Any | Whatever you exported | Your processing software |

A raster works if:

1. **It is georeferenced.** The file carries its projection. A plain image, or a raster with its
   projection missing, is refused with a message saying so.
2. **Heights are in metres.** Some US state and county lidar is delivered in US survey feet, which
   makes terrain 3.28 times too tall. Convert it to metres in your GIS first.
3. **Mixed sources share a vertical reference.** Heights above sea level (NAVD88, EGM96, EGM2008)
   agree with each other to about a metre. Heights above the ellipsoid, which raw GPS and many drone
   exports use, differ from sea-level heights by up to 100 m (about 34 m in Michigan), and mixing
   them puts a cliff along every seam. Convert ellipsoid heights to sea level first.
4. **No-data is marked**, as the file's nodata value or as an impossible height. Anything below
   -500 m or above 9000 m is treated as no data.

List the files **finest first**. At every point, the first file that has data there wins:

```
build_landscape.exe --dem my_drone_dtm.tif "national_lidar\*.tif" "dem_cache\Copernicus_*.tif" ...
```

## 8. Building the landscape

`build_landscape.exe` writes, into its output folder:

| File | What it is |
| --- | --- |
| `<name>.json` | **The plan.** Everything Unreal needs: sizes, positions, scales, and the projection |
| `<name>.r16`, or `<name>_xNN_yNN.r16` for a large area | Heightmaps: raw 16-bit, little-endian, row 0 is north, no header |
| `<name>....provenance` | One byte per height point saying which source supplied it (0 = none) |

Keep the `.r16` files beside the `.json`: the plan names them.

**Why a large area becomes several segments.** Unreal imports a heightmap into memory whole, and one
Landscape actor is best kept to 8161 by 8161 points. A 1 m model of a 60 by 20 km area is 60,000 by
20,000 points, which does not import. So the area is cut into a grid of segments, each its own
Landscape actor and each built one at a time, so memory use stays at a few hundred MB whatever the
size. Neighbouring segments share their edge points exactly and use one height range, so there is
no step at any seam.

### Choosing the detail

*Metres per quad* (`--metres`) sets both detail and cost. It does not have to match the source: the
source is resampled to whatever you choose.

| Metres per quad | Points per square km | A 60 by 20 km area | Good for |
| ---: | ---: | --- | --- |
| 1 | 1,000,000 | 24 segments, 2.4 GB | Ground level, driving, low flight |
| 2 | 250,000 | 8 segments, 600 MB | Most flight simulation |
| 3 | 111,000 | 3 segments, 270 MB | Aerial views |
| 10 | 10,000 | 1 segment, 24 MB | Regional surroundings |
| 30 | 1,100 | 1 segment, 3 MB | Large-area context |

Finer quads than the data (1 m quads on 30 m data) cost memory and add no detail.

### Heights

Unreal stores Landscape heights as 16-bit numbers scaled by the actor's Z scale. The builder finds
the area's height range, picks the smallest Z scale that fits it (the finest height steps, usually
well under a centimetre), places every actor at the middle of the range, and writes the exact
conversion into the plan as `height_decode`.

If the output says `CLIPPED`, some points fell outside the estimated range. Build again with
`--zmin` and `--zmax` covering the real lowest and highest ground in metres.

## 9. Aerial imagery

### United States: NAIP

The USDA National Agriculture Imagery Program photographs the lower 48 states every two to three
years at 0.3 to 0.6 m per pixel, in natural colour. It is public domain.

Given the landscape plan (`--plan`), the imagery is fetched in the landscape's own projection and
starts exactly at its north-west corner, so each pixel sits on the ground it was photographed above
and a material can place the photos by world position alone.

It writes:

| File | What it is |
| --- | --- |
| `<name>.<UDIM>.png` | The tiles, for example `site_naip.1001.png`. Columns run east, rows run south |
| `<name>_uXX_vYY.png` | The same, for areas more than 10 tiles wide, which UDIM numbering cannot express |
| `<name>.json` | The index: every tile's ground extent, and how far edge tiles overhang the landscape |
| `.pgw` and `.prj` beside each PNG | So any GIS can overlay a tile to check it |

At 0.5 m per pixel, every square kilometre is 4 million pixels, about 8 MB. A 60 by 20 km area is
about 72 tiles of 8192 pixels, roughly 10 GB and a few hours. Requests are cached in
`<out>\_cache`, so a run that was stopped only fetches what is still missing. A tile marked
`NO IMAGERY HERE` is outside NAIP's coverage (outside the US, or over open water).

### Outside the United States

NAIP stops at the US border. Free alternatives:

- **Sentinel-2**, 10 m, worldwide: Copernicus Data Space Ecosystem, https://dataspace.copernicus.eu.
- **National orthophoto programmes**, often 0.1 to 0.5 m and openly licensed, for example the
  Netherlands' PDOK Luchtfoto and France's IGN BD ORTHO.
- **Your own drone orthomosaic.**

Reproject and tile any of them to the landscape's grid in QGIS or GDAL, using the plan's
`projection` and its north-west corner (`utm_origin`), then follow [section 11](#11-putting-the-imagery-on-the-landscape).
Commercial web maps (Google, Bing, Esri, Mapbox) generally forbid downloading their imagery for
reuse.

## 10. Importing into Unreal

Create or open a **World Partition** level first: *File*, *New Level*, *Open World* or *Empty Open
World*.

### With the MAirCorridor plugin

If your project has the MAirCorridor Unreal plugin enabled: *Tools*, *M-Air Corridor*, *Build
Unreal Landscape from Plan...*, pick `<name>.json`, then save the level. It builds every segment as
its own Landscape actor, in place. It checks the plan first and refuses one whose heightmaps are
missing, truncated or an illegal size, with the reason.

### By hand, in any Unreal project

Repeat for each segment. A plan with one segment has the fields below at its top level; a plan with
several lists them under `"segments"`, one entry per heightmap.

1. Open **Landscape** mode (*Selection Mode* menu, *Landscape*), *Manage*, *New*, **Import from
   File**.
2. *Heightmap File*: the segment's `.r16`. If Unreal offers several resolutions for the file, pick
   the one the plan lists.
3. Fill in the settings from the plan:

| Unreal setting | From the plan |
| --- | --- |
| Section Size | `section_size_quads` quads (255 by default, shown as 255x255) |
| Sections Per Component | `sections_per_component` (2 means 2x2) |
| Number of Components | `components`, X then Y |
| Overall Resolution | `resolution`, X then Y. It must come out exactly this |
| Location | `actor_location_cm`, X, Y, Z |
| Scale | `actor_scale`, X, Y, Z |
| Enable World Partition, grid size | `world_partition_grid_size` (0: leave it off) |

4. Press **Import**, then save the level.

The location and scale matter as much as the heights. With the scale wrong the terrain is the wrong
size or height; with the location wrong, segments overlap or leave gaps. Every number Unreal needs
is in the plan; nothing has to be worked out.

The Landscape has no material yet. Give it one with the actor's *Landscape Material* property, or
build the imagery material in the next section.

## 11. Putting the imagery on the landscape

With *Origin* `area` (the default), the landscape's north-west corner is at Unreal X 0, Y 0, Unreal
+X points east and Unreal +Y points south. Imagery tile `u, v` from the index covers, in centimetres:

```
west  = u * tile_px * metres * 100
north = v * tile_px * metres * 100
size  = tile_px * metres * 100
```

where `tile_px` is *Tile pixels* and `metres` is *Metres per pixel*. In a material, for one tile:

```
UV = (AbsoluteWorldPosition.xy - float2(west, north)) / size
```

No flip is needed: Unreal +Y points south and an image's first row is its north edge, so V 0 is the
tile's north edge.

**Many tiles.** Import them as a UDIM virtual texture (select the `.1001.png`; Unreal gathers the
rest), and use `UV = AbsoluteWorldPosition.xy / size` so the whole-number part picks the tile.
Unreal's UDIM convention counts rows upward while these tiles count south, so check the result and
flip the row index if needed.

**Checking it.** Look at a road, field edge or building. If the photo sits on the terrain's matching
features, it is right. Mirrored north to south: flip V. Off by one whole tile: `u` or `v` is off by
one.

## 12. Command line reference

Every tool runs from a command prompt opened in this folder (in Explorer, type `cmd` in the address
bar and press Enter). Paths with spaces need quotes. `--help` on any tool lists all its options.
The window prints the exact command for each step it runs, which is a good starting point.

### download_3dep.exe

```
download_3dep.exe (--bbox W S E N | --aoi FILE) --product {1m,19,13,1,opr} --out DIR
                  [--buffer-m M] [--dry-run] [--max-files N]
```

```
download_3dep.exe --aoi site.kml --product 1m --out work\dem_cache --dry-run
download_3dep.exe --aoi site.kml --product 1m --out work\dem_cache
download_3dep.exe --aoi site.kml --product 13 --out work\dem_cache
download_3dep.exe --bbox -83.71 42.29 -83.69 42.31 --product 13 --out work\dem_cache
```

| Option | Meaning |
| --- | --- |
| `--product` | Which product ([section 6](#6-elevation-data)) |
| `--out` | Folder to download into; reused as a cache, so files already there are skipped |
| `--buffer-m` | Widen the area by this many metres |
| `--dry-run` | List the files and total size, download nothing |
| `--max-files` | Stop after this many files (0, the default, means all) |

### download_copernicus_dem.exe

```
download_copernicus_dem.exe (--bbox W S E N | --aoi FILE) --out DIR
                            [--resolution {30,90}] [--buffer-m M] [--dry-run]
```

```
download_copernicus_dem.exe --aoi site.kml --out work\dem_cache
download_copernicus_dem.exe --bbox 7.40 46.90 7.50 46.98 --resolution 90 --out work\dem_cache
```

### build_landscape.exe

```
build_landscape.exe --dem FILES... --out DIR --name NAME
                    [--bbox W S E N | --aoi FILE | --projected-bounds MINX MINY MAXX MAXY]
                    [--metres M] [--epsg CODE] [--datum {WGS84,NAD83}] [--origin {area,projected}]
                    [--max-vertices N] [--wp-grid N] [--no-mask] [--zmin M] [--zmax M]
                    [--resampling {bilinear,cubic,nearest}] [--plan-only] [--buffer-m M]
                    [--section-quads N] [--sections-per-component {1,2}]
```

```
build_landscape.exe --dem "work\dem_cache\USGS_one_meter_*.tif" "work\dem_cache\USGS_13_*.tif" --aoi site.kml --metres 1 --datum NAD83 --out work\landscape --name site
build_landscape.exe --dem my_srtm.tif --metres 30 --out work\landscape --name valley
```

| Option | Default | Meaning |
| --- | --- | --- |
| `--dem` | required | Files, wildcards or folders, **finest first** |
| `--bbox`, `--aoi` | all of the files | The area |
| `--projected-bounds` | | The area in the output projection's metres, used exactly, for matching a known grid (needs `--epsg`) |
| `--metres` | 1 | Metres per quad ([Choosing the detail](#choosing-the-detail)) |
| `--epsg` | UTM zone of the area | Output projection; must be in metres |
| `--datum` | WGS84 | Datum for the automatic UTM zone; NAD83 to match USGS in North America |
| `--origin` | area | `area` puts the north-west corner at Unreal 0,0; `projected` uses map coordinates |
| `--max-vertices` | 8161 | Largest segment side |
| `--wp-grid` | 4 | World Partition grid size; 0 leaves each Landscape unsplit |
| `--section-quads`, `--sections-per-component` | 255, 2 | Unreal's component layout |
| `--no-mask` | off | Keep the whole rectangle instead of blanking outside the KML outline |
| `--zmin`, `--zmax` | estimated | Force the height range, in metres |
| `--resampling` | bilinear | `nearest` keeps source values exactly; `cubic` is smoother |
| `--plan-only` | | Print the layout and build nothing |

### download_naip.exe

```
download_naip.exe (--plan PLAN.json | --bbox W S E N | --aoi FILE) --out DIR --name NAME
                  [--metres M] [--tile-px N] [--request-px N] [--workers N]
                  [--epsg CODE] [--datum {WGS84,NAD83}] [--buffer-m M] [--dry-run]
```

```
download_naip.exe --plan work\landscape\site.json --metres 0.5 --out work\naip --name site_naip --dry-run
download_naip.exe --plan work\landscape\site.json --metres 0.5 --out work\naip --name site_naip
download_naip.exe --aoi site.kml --metres 1 --out work\naip --name site_naip
```

`--epsg` and `--datum` apply only without `--plan`; with a plan, the plan's projection is used.

### Stopping a run

Ctrl+C stops a tool at the command prompt; **Cancel** does the same in the window. Downloads keep
every finished file and continue from there when run again.

## 13. What ends up where

The window keeps everything in the working folder:

```
<working folder>\
    dem_cache\                       elevation: .tif and .img files, and download_*.json records
    landscape\
        <name>.json                  the plan: what you give Unreal
        <name>.r16                   heightmap (or <name>_xNN_yNN.r16, one per segment)
        <name>.provenance            which source supplied each point
    naip\
        <name>_naip.1001.png ...     imagery tiles, with .pgw and .prj beside each
        <name>_naip.json             the tile index
        _cache\                      partial downloads; safe to delete once finished
```

For Unreal you need the `landscape` folder (the `.json` and every `.r16`) and the `naip` tiles.
`dem_cache` can be kept to rebuild at a different detail later, or deleted.

## 14. Data licences and attribution

The data keeps its own terms, whichever tool fetched it.

| Data | Licence | Attribution |
| --- | --- | --- |
| USGS 3DEP | Public domain | "Elevation data: U.S. Geological Survey, 3D Elevation Program" (requested, not required) |
| USDA NAIP | Public domain | "Imagery: USDA Farm Service Agency, National Agriculture Imagery Program" (requested) |
| Copernicus DEM | Free with attribution | **Required**: "produced using Copernicus WorldDEM-30 (c) DLR e.V. 2010-2014 and (c) Airbus Defence and Space GmbH 2014-2018 provided under COPERNICUS by the European Union and ESA; all rights reserved" |
| Map tiles in the window | OpenStreetMap, ODbL | "(c) OpenStreetMap contributors". The map is for choosing the area; nothing from it ends up in your landscape |
| Anything else you add | Its own terms | Check before you publish |

## 15. Troubleshooting

| Symptom | Cause and fix |
| --- | --- |
| "Windows protected your PC" | The tools are not signed. *More info*, then *Run anyway* |
| A tool does not start, or its `.exe` is 0 bytes | Antivirus quarantined it. Restore it from quarantine and allow it, or copy the folder again |
| A tool says something is missing from `_internal` | The folder was split up. Keep every `.exe` beside `_internal` |
| The window opens off screen or too large | It sizes itself to the screen it opens on; move it with Alt+Space, *Move*, then the arrow keys |
| The map stays grey | No internet, or a proxy is blocking tile.openstreetmap.org. The area can still be typed in as a box or a KML |
| `The National Map API did not answer` | The USGS service is busy. Wait a few minutes and run again; finished files are kept |
| `Nothing found` from download_3dep | No lidar there. Use product `13`, which covers the whole US |
| `no elevation data inside the area` | The files do not cover the area. Check the box reads west, south, east, north |
| `CLIPPED` | Build again with `--zmin` and `--zmax` covering the real lowest and highest ground |
| Terrain about 3 times too tall | The source heights are in feet ([section 7](#7-using-elevation-data-from-anywhere-else)) |
| A cliff along a seam between two sources | They use different vertical references ([section 7](#7-using-elevation-data-from-anywhere-else)) |
| Unreal refuses the plan, or the import is the wrong size | An `.r16` was moved, renamed or cut short, or a setting does not match the plan ([section 10](#10-importing-into-unreal)) |
| Segments overlap or leave gaps in Unreal | A segment's Location or Scale was not copied from the plan |
| `NO IMAGERY HERE` | NAIP has nothing there: outside the US, or over water |
| Imagery mirrored or offset | See *Checking it* in [section 11](#11-putting-the-imagery-on-the-landscape) |
| A download is very slow | Large areas genuinely take hours. Run the dry run to see the size, and leave it overnight; stopping and starting loses nothing |
