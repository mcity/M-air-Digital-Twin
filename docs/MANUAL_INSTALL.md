# Manual install

Everything `install.py` does, by hand. The steps below are for Linux; the same steps with Windows
commands are under [Windows](#windows) at the end. Paths below assume you cloned this repository to
`~/M-air-Digital-Twin` and that `UE_ROOT` is your Unreal Engine 5.7 folder (the one containing `Engine/`).

```bash
export UE_ROOT=/path/to/UnrealEngine
cd ~/M-air-Digital-Twin
```

## 1. Python environment

```bash
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements.txt
```

## 2. Download the assets

```bash
.venv/bin/hf download M-Air/m-air_digital_twin --repo-type dataset --local-dir .downloads
```

(With an older `huggingface_hub` the command is `huggingface-cli download` with the same arguments. You
can also download the files in a browser from the dataset's *Files* tab; keep the folder structure.)

Optionally check the downloads against `manifest.json`, which lists the SHA-256 of every file:

```bash
cd .downloads && sha256sum unreal_content/*.tar* && cd ..
```

## 3. Unpack the assets into the plugin

Every archive holds a `Content/` folder and unpacks into the plugin folder:

```bash
PLUGIN=MAirCorridorSim/Plugins/MAirCorridor
for a in .downloads/unreal_content/*.tar.gz .downloads/unreal_content/*.tar; do
    tar -xf "$a" -C "$PLUGIN"
done
```

Two things are shipped as plain files:

```bash
# the terrain's aerial imagery
cp .downloads/unreal_content/terrain_imagery/mcity_066m_naip.uasset "$PLUGIN/Content/AnchorBaked/"

# the terrain heights the mission tools use
mkdir -p MAirCorridor_Assets/ue_rect_3m
cp .downloads/terrain_heightmap/ue_rect_3m/* MAirCorridor_Assets/ue_rect_3m/
```

Check: `MAirCorridorSim/Plugins/MAirCorridor/Content/Scene/CorridorTerrain.umap` exists. You can now
delete `.downloads/`.

## 4. Add the Project AirSim plugin

The project needs three plugin folders, `ProjectAirSim`, `Drone` and `Rover`, directly inside
`MAirCorridorSim/Plugins/`. Do not nest them deeper.

**Prebuilt.** Download `ProjectAirSim-Plugin-Linux-UE5_7-1.0.1.zip` from the
[Project AirSim releases](https://github.com/iamaisim/ProjectAirSim/releases/tag/v1.0.1), then:

```bash
unzip ProjectAirSim-Plugin-Linux-UE5_7-1.0.1.zip -d /tmp/pas
cp -r /tmp/pas/Plugins/ProjectAirSim /tmp/pas/Plugins/Drone /tmp/pas/Plugins/Rover MAirCorridorSim/Plugins/
```

**Source.** In your Project AirSim clone, build the sim libs, then copy the plugins without their build
output:

```bash
(cd /path/to/ProjectAirSim && ./build.sh simlibs_release)
for p in ProjectAirSim Drone Rover; do
    rsync -a --delete --exclude Binaries --exclude Intermediate \
        /path/to/ProjectAirSim/unreal/Blocks/Plugins/$p/ MAirCorridorSim/Plugins/$p/
done
```

Repeat this copy, and step 6, whenever you rebuild the sim libs.

## 5. Project AirSim's Python client

The flight tools use the client and the sample robot configurations from Project AirSim's repository.

**Source users** already have them: use your clone as `PROJECTAIRSIM_ROOT` in step 7.

**Prebuilt users** fetch just that part:

```bash
git clone --depth 1 --branch v1.0.1 --filter=blob:none --sparse https://github.com/iamaisim/ProjectAirSim.git ProjectAirSim
git -C ProjectAirSim sparse-checkout set client/python
```

## 6. Build

```bash
"$UE_ROOT/Engine/Build/BatchFiles/Linux/Build.sh" MAirCorridorSimEditor Linux Development \
    -Project="$PWD/MAirCorridorSim/MAirCorridorSim.uproject" -WaitMutex
```

Build **Development**, not Debug: the prebuilt plugin ships release sim libs only.

## 7. Tell the scripts where things are

```bash
cp maircorridor.env.example maircorridor.env
```

Edit `maircorridor.env` so every path is right for your machine.

## 8. Run

```bash
scripts/run_sim.sh          # first start is slow: see the README
scripts/hover_test.sh       # in a second terminal
```

## Into your own project instead

Copy `MAirCorridorSim/Plugins/MAirCorridor` (with its `Content/`) into your project's `Plugins/` folder,
make sure `ProjectAirSim`, `Drone` and `Rover` are there too, build your project's editor target, and set
`MAIR_PROJECT` and `MAIR_PLUGIN` in `maircorridor.env` to your project. `scripts/run_sim.sh` opens the
corridor level and Project AirSim's game mode by name, so no project setting has to change. If you start
the level another way, the level is `/MAirCorridor/Scene/CorridorTerrain` and the game mode is
`ProjectAirSimGameMode`.

## Windows

> Not yet tested on Windows: these are the Linux steps above with Windows commands. Please report what
> does not work.

You need Unreal Engine 5.7, Visual Studio 2022 with the *Game development with C++* workload, Python
3.10 to 3.12 and Git for Windows. Use **PowerShell**, and clone to a short path (Windows limits paths to
260 characters):

```powershell
cd C:\
git clone https://github.com/mcity/M-air-Digital-Twin.git MAir
cd C:\MAir
$UE = "C:\Program Files\Epic Games\UE_5.7"
```

**1. Python environment**

```powershell
py -3 -m venv .venv
.venv\Scripts\python.exe -m pip install --upgrade pip
.venv\Scripts\python.exe -m pip install -r requirements.txt
```

**2. Download the assets**

```powershell
.venv\Scripts\hf.exe download M-Air/m-air_digital_twin --repo-type dataset --local-dir .downloads
```

To check a download, compare `Get-FileHash <file> -Algorithm SHA256` with its entry in
`.downloads\manifest.json`.

**3. Unpack the assets into the plugin** (`tar` is part of Windows 10 and 11)

```powershell
$PLUGIN = "MAirCorridorSim\Plugins\MAirCorridor"
Get-ChildItem .downloads\unreal_content\*.tar* | ForEach-Object { tar -xf $_.FullName -C $PLUGIN }

Copy-Item .downloads\unreal_content\terrain_imagery\mcity_066m_naip.uasset "$PLUGIN\Content\AnchorBaked\"

New-Item -ItemType Directory -Force MAirCorridor_Assets\ue_rect_3m | Out-Null
Copy-Item .downloads\terrain_heightmap\ue_rect_3m\* MAirCorridor_Assets\ue_rect_3m\
```

Check: `MAirCorridorSim\Plugins\MAirCorridor\Content\Scene\CorridorTerrain.umap` exists.

**4. Add the Project AirSim plugin.** `ProjectAirSim`, `Drone` and `Rover` go directly inside
`MAirCorridorSim\Plugins\`.

*Prebuilt:* download `ProjectAirSim-Plugin-Windows-UE5_7-1.0.1.zip` from the
[Project AirSim releases](https://github.com/iamaisim/ProjectAirSim/releases/tag/v1.0.1), then:

```powershell
Expand-Archive "$HOME\Downloads\ProjectAirSim-Plugin-Windows-UE5_7-1.0.1.zip" -DestinationPath .downloads\pas
$P = (Get-ChildItem .downloads\pas -Recurse -Filter ProjectAirSim.uplugin | Select-Object -First 1).Directory.Parent.FullName
Copy-Item "$P\ProjectAirSim", "$P\Drone", "$P\Rover" MAirCorridorSim\Plugins\ -Recurse
```

*Source:* build the sim libs in your clone from the *x64 Native Tools Command Prompt for VS 2022*
(`set UE_ROOT=...` then `build.cmd simlibs_release`), then copy the plugins without their build output:

```powershell
foreach ($p in "ProjectAirSim", "Drone", "Rover") {
    robocopy "C:\src\ProjectAirSim\unreal\Blocks\Plugins\$p" "MAirCorridorSim\Plugins\$p" /MIR /XD Binaries Intermediate
}
```

**5. Project AirSim's Python client.** Source users use their clone. Prebuilt users:

```powershell
git clone --depth 1 --branch v1.0.1 --filter=blob:none --sparse https://github.com/iamaisim/ProjectAirSim.git ProjectAirSim
git -C ProjectAirSim sparse-checkout set client/python
```

**6. Build** (Development, not Debug)

```powershell
& "$UE\Engine\Build\BatchFiles\Build.bat" MAirCorridorSimEditor Win64 Development "-Project=$PWD\MAirCorridorSim\MAirCorridorSim.uproject" -WaitMutex
```

**7. Tell the scripts where things are.** Copy `maircorridor.env.example` to `maircorridor.env` and set
every path, in the same `NAME="value"` form, with Windows paths written as they are:

```
UE_ROOT="C:\Program Files\Epic Games\UE_5.7"
MAIR_PROJECT="C:\MAir\MAirCorridorSim\MAirCorridorSim.uproject"
MAIR_PLUGIN="C:\MAir\MAirCorridorSim\Plugins\MAirCorridor"
MAIR_PYTHON="C:\MAir\.venv\Scripts\python.exe"
PROJECTAIRSIM_ROOT="C:\MAir\ProjectAirSim"
MAIRCORRIDOR_ASSETS="C:\MAir\MAirCorridor_Assets"
MAIRCORRIDOR_PLAN="C:\MAir\MAirCorridor_Assets\ue_rect_3m\mcity_rect_3m.json"
```

**8. Run**

```powershell
scripts\run_sim.bat          # first start is slow: see the README
scripts\hover_test.bat       # in a second window
```
