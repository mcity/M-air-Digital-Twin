# M-Air Digital Twin: the M-Air corridor for Project AirSim

A drone-simulation environment of the M-Air / Mcity corridor in Ann Arbor, Michigan, for
[Project AirSim](https://github.com/iamaisim/ProjectAirSim) on Unreal Engine 5.7: real terrain and
aerial imagery, every building along the corridor, and the photogrammetric scan of the Mcity test track.

> **The environment is the work of Sean Rice, University of Michigan.** The corridor level, the
> MAirCorridor Unreal plugin, the flight and geodata tools and the pipeline that built the content are his
> [MAirCorridor](https://github.com/sriceumich/MAirCorridor) project. This repository packages that work
> for easy installation. If you use it, please [cite MAirCorridor](#credits-and-citation).

This repository holds the **code**: the Unreal plugin's source, a small host project, the flight tools
and an installer. The **3D assets** (about 13.5 GB) live in a Hugging Face dataset and are downloaded by
the installer:

> Assets: https://huggingface.co/datasets/M-Air/m-air_digital_twin

## What you need

| | |
| --- | --- |
| Unreal Engine | **5.7**, able to build C++ projects (an installed build or a source build) |
| Project AirSim | **1.0.1**: either the prebuilt *plugin* release or a source build (see below) |
| OS | Ubuntu 22.04 is what this was built and tested on. Windows 10/11: see [Windows](#windows) (not yet tested) |
| GPU | A recent NVIDIA card (tested on an RTX 4090). Linux: Vulkan drivers. Windows: DirectX 12 |
| Disk | About 35 GB free for the install, plus Unreal's own caches on first launch |
| Memory | 32 GB or more: the first launch builds the terrain's virtual texture |
| Other | Python 3.9+, `git`, and `python3-venv` on Ubuntu. Windows also needs Visual Studio 2022 |

**Which Project AirSim do I have?**

- *Prebuilt*: you use the release downloads from Project AirSim's
  [releases page](https://github.com/iamaisim/ProjectAirSim/releases). The one this needs is
  `ProjectAirSim-Plugin-Linux-UE5_7-1.0.1.zip`. You do not have to download it: the installer does.
- *Source*: you cloned Project AirSim and build its sim libs yourself with `./build.sh`.

> The packaged demo environments (`Blocks-Linux-1.0.1.zip` and the others) are finished games. A new
> environment cannot be added to them, so they are not used here.

## Install (automatic)

These are the Linux commands. On Windows the steps are the same with different commands: see
[Windows](#windows).

```bash
git clone https://github.com/mcity/M-air-Digital-Twin.git
cd M-air-Digital-Twin
```

**Prebuilt Project AirSim**

```bash
python3 install.py --ue-root /path/to/UnrealEngine
```

If you already downloaded the plugin release, point at the zip or the unzipped folder to skip that download:

```bash
python3 install.py --ue-root /path/to/UnrealEngine --airsim ~/Downloads/ProjectAirSim-Plugin-Linux-UE5_7-1.0.1.zip
```

**Project AirSim built from source**

Build the sim libs in your clone first (`export UE_ROOT=/path/to/UnrealEngine; ./build.sh simlibs_release`),
then:

```bash
python3 install.py --ue-root /path/to/UnrealEngine --airsim /path/to/ProjectAirSim
```

Either way the installer checks your machine, makes a Python environment in `.venv`, downloads and
verifies the assets, unpacks them into the bundled Unreal project `MAirCorridorSim`, adds the Project
AirSim plugin to it, and builds it. It can be run again at any time: finished steps are skipped and an
interrupted download resumes. `python3 install.py --help` lists every option.

`--ue-root` is the folder that contains `Engine/`. You can set `UE_ROOT` instead.

Prefer to do it by hand, or want to see exactly what happens? [docs/MANUAL_INSTALL.md](docs/MANUAL_INSTALL.md).

### Into your own Unreal project

To add the corridor to a C++ Unreal 5.7 project you already have (for example Project AirSim's own
`unreal/Blocks/Blocks.uproject` in a source clone) instead of the bundled one:

```bash
python3 install.py --ue-root /path/to/UnrealEngine --project /path/to/YourProject.uproject
```

If the project does not have the Project AirSim plugin yet, add `--airsim` as above.

## Run

Start the simulator and leave it running:

```bash
scripts/run_sim.sh
```

**The first start is slow.** Unreal compiles shaders and builds caches for the scan and the terrain
imagery. Expect several minutes before the window appears, and the terrain can look untextured for
around 15 minutes more while its virtual texture builds. Later starts take about a minute.

In a second terminal, check that everything works:

```bash
scripts/hover_test.sh        # holds a hover, flies 20 m, prints PASS
```

## Fly your own simulations

**A route, no keyboard.** A mission is a JSON list of waypoints (longitude, latitude, height, speed):

```bash
scripts/fly_mission.sh missions/mcity_circle.json --dry-run     # check the route without flying
scripts/fly_mission.sh missions/mcity_circle.json               # a circle around the Mcity test track
scripts/fly_mission.sh missions/mcity_to_motts.json --record Chase
```

Copy one of the files in `missions/` to make your own. Each flight writes its track, and anything
recorded, to `flights/<time>/`. The mission format, recording options and the map-based planner
(`scripts/mission_planner.sh`) are documented in
[the tools guide](MAirCorridorSim/Plugins/MAirCorridor/Tools/README.md).

**On the keyboard.**

```bash
scripts/fly_keyboard.sh
```

**From your own Python.** [scripts/hover_test.py](scripts/hover_test.py) is a complete, short example of
loading the scene and commanding the drone with Project AirSim's client. Run your script the same way:

```bash
source scripts/_env.sh && "$MAIR_PYTHON" scripts/run_tool.py my_script.py
```

Things worth knowing:

- Positions are north/east/down in metres from the level's origin, so *up is negative*. The level's
  axes are rotated relative to true north; the mission tools convert longitude/latitude for you.
- The stock scene spawns the drone about 250 m above the test track. It falls until something commands it.
- The simulator serves one client at a time. Close one script before starting another.
- Scene and drone configurations are in `MAirCorridorSim/Plugins/MAirCorridor/AirSim/sim_config/`.

## What is where

```
install.py                 the installer (install.bat runs it on Windows)
scripts/                   run the simulator, fly missions, hover test (.sh for Linux, .bat for Windows)
missions/                  example missions
MAirCorridorSim/           the Unreal project
  Plugins/MAirCorridor/    the environment: C++ source, flight tools, and (after install) Content/
docs/                      manual install, troubleshooting
maintainer/                how the Hugging Face dataset is packed (not needed by users)
```

Created by the installer and not in git: `.venv/`, `.downloads/`, `ProjectAirSim/` (its Python client),
`MAirCorridor_Assets/` (terrain heights for the mission tools), `maircorridor.env` (paths the scripts read).

## Updating

- **This repository changed:** `git pull`, then `python3 install.py ...` again.
- **The assets changed:** the same; only archives whose checksum changed are fetched and unpacked.
- **You rebuilt Project AirSim's sim libs (source users):** `python3 install.py ... --airsim /path/to/ProjectAirSim --refresh-airsim`.

## Windows

> **Not yet tested.** The environment itself was authored on Windows, and the installer and the `.bat`
> scripts are written for it, but this packaging has only been run on Linux. If something fails, please
> open an issue with the output.

**What you need, besides the list at the top**

- Windows 10 or 11, 64-bit, with a DirectX 12 graphics card.
- Unreal Engine 5.7 from the Epic Games Launcher (or a source build).
- [Visual Studio 2022](https://visualstudio.microsoft.com/vs/) with the **Game development with C++**
  workload (the free Community edition is fine). Unreal needs it to compile the plugins.
- [Python](https://www.python.org/downloads/windows/) 3.10, 3.11 or 3.12 (64-bit) and
  [Git for Windows](https://git-scm.com/download/win).

**Install.** Open a *Command Prompt*. Clone into a **short path**: Windows limits paths to 260
characters and the assets go deep.

```bat
cd /d C:\
git clone https://github.com/mcity/M-air-Digital-Twin.git MAir
cd MAir
install.bat
```

`install.bat` takes the same options as `install.py` on Linux. With no options it looks for Unreal Engine
in `C:\Program Files\Epic Games\UE_5.7` and downloads the prebuilt Project AirSim plugin
(`ProjectAirSim-Plugin-Windows-UE5_7-1.0.1.zip`). The other cases:

```bat
rem Unreal Engine somewhere else
install.bat --ue-root "D:\Epic Games\UE_5.7"

rem the plugin release already downloaded
install.bat --airsim "%USERPROFILE%\Downloads\ProjectAirSim-Plugin-Windows-UE5_7-1.0.1.zip"

rem Project AirSim built from source (build its sim libs first: build.cmd simlibs_release)
install.bat --airsim C:\src\ProjectAirSim

rem into your own C++ Unreal project
install.bat --project C:\src\MyProject\MyProject.uproject
```

**Run.** The same scripts as on Linux, as `.bat` files:

```bat
scripts\run_sim.bat
```

Windows may ask whether to allow Unreal Engine through the firewall; the simulator and the tools talk
over local ports 8989 and 8990. The first start is slow, as described under [Run](#run). Then, in a
second Command Prompt:

```bat
scripts\hover_test.bat
scripts\fly_mission.bat missions\mcity_circle.json --dry-run
scripts\fly_mission.bat missions\mcity_circle.json
scripts\fly_mission.bat missions\mcity_to_motts.json --record Chase
scripts\fly_keyboard.bat
scripts\mission_planner.bat
scripts\open_editor.bat
```

Your own Python script: `scripts\run_python.bat my_script.py`.

| Linux | Windows |
| --- | --- |
| `python3 install.py ...` | `install.bat ...` |
| `scripts/run_sim.sh` | `scripts\run_sim.bat` |
| `scripts/hover_test.sh` | `scripts\hover_test.bat` |
| `scripts/fly_mission.sh <mission>` | `scripts\fly_mission.bat <mission>` |
| `scripts/fly_keyboard.sh` | `scripts\fly_keyboard.bat` |
| `scripts/mission_planner.sh` | `scripts\mission_planner.bat` |
| `scripts/open_editor.sh` | `scripts\open_editor.bat` |
| `source scripts/_env.sh && "$MAIR_PYTHON" scripts/run_tool.py my_script.py` | `scripts\run_python.bat my_script.py` |
| `AIRSIM_TOPICS_PORT=8991 scripts/run_sim.sh` | `set AIRSIM_TOPICS_PORT=8991` then `scripts\run_sim.bat` |

The `.bat` files are thin wrappers around [scripts/mair.py](scripts/mair.py), which also works on Linux
(`python3 scripts/mair.py sim`). The manual steps for Windows are in
[docs/MANUAL_INSTALL.md](docs/MANUAL_INSTALL.md#windows).

## Problems

See [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md).

## Credits and citation

### MAirCorridor, by [Sean Rice](https://github.com/sriceumich)

This environment was created by **Sean Rice, University of Michigan**. His
[MAirCorridor](https://github.com/sriceumich/MAirCorridor) project is the source of essentially everything
you fly in and fly with here:

- the corridor level, its terrain, buildings, vegetation and the placement of the Mcity scan;
- the MAirCorridor Unreal Engine plugin (`MAirCorridorSim/Plugins/MAirCorridor/Source`);
- the flight, mission, recording and geodata tools (`MAirCorridorSim/Plugins/MAirCorridor/Tools` and `AirSim`);
- the data pipeline and its documentation, including [PROVENANCE.md](MAirCorridorSim/Plugins/MAirCorridor/PROVENANCE.md).

The plugin's code and documents are included here unchanged. What this repository adds is packaging only:
the installer, the host project, the helper scripts in `scripts/`, the example missions and these
instructions.

**If you use this environment, its tools or its pipeline in research or a publication, please cite
MAirCorridor.** GitHub's *Cite this repository* button (from [CITATION.cff](CITATION.cff)) gives APA and
BibTeX; or use:

> Sean Rice - University of Michigan. (2026). *MAirCorridor: an Unreal Engine plugin and geodata toolchain
> for the M-Air corridor* (Version 1.0.0) [Computer software]. https://github.com/sriceumich/MAirCorridor

```bibtex
@software{maircorridor_2026,
  author  = {{Sean Rice - University of Michigan}},
  title   = {{MAirCorridor}: an Unreal Engine plugin and geodata toolchain for the {M-Air} corridor},
  year    = {2026},
  version = {1.0.0},
  url     = {https://github.com/sriceumich/MAirCorridor}
}
```

### Data and software it is built on

- **Buildings** were modelled from OpenStreetMap data with [blosm](https://github.com/vvoovv/blosm) by
  Vladimir Elistratov. Placement data: (c) [OpenStreetMap contributors](https://www.openstreetmap.org/copyright),
  Open Database License 1.0. Building textures come from the blosm asset pack, including
  [ambientCG](https://ambientcg.com) (CC0).
- **Trees** were generated with [tree-gen](https://github.com/friggog/tree-gen) by friggog.
- **Terrain:** U.S. Geological Survey, [3D Elevation Program](https://www.usgs.gov/3d-elevation-program).
- **Aerial imagery:** USDA Farm Service Agency, National Agriculture Imagery Program.
- **Mcity scan:** photogrammetric scan of the [Mcity](https://mcity.umich.edu/) test facility, University of Michigan.
- **Drone simulation:** [Project AirSim](https://github.com/iamaisim/ProjectAirSim) (MIT License).
- Built for [Unreal Engine](https://www.unrealengine.com) 5.7.

When you publish images, video or derived data made with this environment, also credit the underlying data:

> Elevation: U.S. Geological Survey 3D Elevation Program. Imagery: USDA National Agriculture Imagery
> Program. Buildings: (c) OpenStreetMap contributors, modelled with blosm.
