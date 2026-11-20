# Manual install

Everything `install.py` does, by hand. Paths below assume you cloned this repository to
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
