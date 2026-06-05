# McityMap for Project AirSim

A digital-twin Unreal environment of the **[Mcity](https://mcity.umich.edu/)
test facility** (University of Michigan) for
**[Project AirSim](https://github.com/iamaisim/ProjectAirSim)**, with:

- **Real-world-accurate GNSS** — the map is geo-anchored to Mcity's true
  location and rotated so the simulated GPS reports genuine WGS84
  latitude/longitude (verified against survey coordinates)
- **A live map UI (optional)** — fly a drone with the keyboard while watching
  its real position on a Google satellite map in the browser (needs a Google
  Maps API key; not required to install or fly)

```
mcity_proj_airsim/
├── setup_mcity_env.sh        # one-command installer (run this)
├── McityMap/
│   ├── Content/McityMap/     # UE 5.7 map content (geo-aligned, ~1 GB)
│   └── verify_mcity_rotation.py  # optional: verify map orientation on disk
└── mcity_scripts/
    ├── keyboard_control_gnss.py  # flight script with GNSS overlay + map relay
    ├── sim_config/               # Mcity-anchored scene + GPS-enabled robot
    ├── gps_ws_server.py          # web UI backend (UDP in → WebSocket out)
    ├── index.html / app.js / style.css / config.js
    ├── .env.example              # → copy to .env, add your Google Maps key
    └── requirements.txt          # extra python deps (websockets, python-xlib)
```

---

## Prerequisites

1. **Ubuntu 22.04** (what this package is tested on).
2. **Unreal Engine 5.7.x** installed, with `UE_ROOT` exported.
   ⚠️ The map content is saved in UE 5.7 format — **UE 5.2 cannot load it**.
3. **Project AirSim built from source** — follow the
   [official source build docs](https://iamaisim.github.io/ProjectAirSim/development/use_source.html):
   ```bash
   ./setup_linux_dev_tools.sh
   export UE_ROOT=/path/to/UnrealEngine-5.7
   ./build.sh simlibs_release        # required before installing McityMap
   ```
4. **Project AirSim Python client** installed in a Python 3.10 environment
   (conda or venv), per the official client setup. Then add this package's
   extras:
   ```bash
   pip install -r mcity_scripts/requirements.txt
   ```
5. *(Optional)* **A Google Maps JavaScript API key** (free tier is fine) —
   only needed for the optional live map UI (see **Optional: live Google-Maps
   view** below). Not required to install or fly.

---

## Install

```bash
export UE_ROOT=/path/to/UnrealEngine-5.7
./setup_mcity_env.sh /path/to/your/projectairsim/repo
```

The script creates `unreal/McityMap/` inside your Project AirSim repo as a
sibling of Blocks (reusing *your* repo's project files so versions always
match), symlinks the ProjectAirSim plugin, copies the map content, and builds
the editor target. It refuses to run if prerequisites are missing and prints
the launch command when done. See **Manual installation** below for the
equivalent steps by hand.

---

## Run & verify

Two terminals (A: editor, B: flight script).

**A — launch the sim and press Play:**
```bash
"$UE_ROOT/Engine/Binaries/Linux/UnrealEditor" \
    /path/to/projectairsim/unreal/McityMap/McityMap.uproject
```
First launch takes several minutes (shader compilation). When the editor
opens on the Mcity map, click **Play (▶)**.
*Expected warnings:* missing CARLA vegetation meshes — harmless, some trees
are simply absent.

**B — fly** (works from any directory — configs resolve next to the script):
```bash
python mcity_scripts/keyboard_control_gnss.py
```

### ✅ You have installed it correctly when:

Terminal B arms and takes off, you can fly the drone around the Mcity
environment (W/S/A/D move, arrows = altitude/yaw, **L = land, Q = quit**),
and a **"Chase Cam + GNSS"** window shows the camera view with a green GNSS
overlay reading approximately:
`Lat 42.30087°, Lon −83.69772°, Alt ≈ 270–281 m`

> ℹ️ Flight keys are read from the **"Chase Cam + GNSS" window** — click it
> once to give it focus before flying. Keys typed anywhere else (browser,
> terminal) are ignored, and closing the window quits (same as **Q**).

---

## Optional: live Google-Maps view

To watch the drone's real-world position live on a Google satellite map, you
need a **Google Maps JavaScript API key** (free tier is fine):

```bash
cd mcity_scripts
cp .env.example .env     # then edit .env and paste your key
python gps_ws_server.py
```

Open <http://localhost:8080> — satellite view of Mcity ("Waiting for GPS data
from sim…" until a flight script runs). With `keyboard_control_gnss.py`
flying, the map shows a **marker on the Mcity facility** (north-east section
of the track) with a trail as you fly, and flying toward real-world locations
on the satellite map matches what you see in the simulator's world.

---

## Using the GNSS data in your own code

- The drone's GPS topic (`…/sensors/GPS/gps`) publishes true WGS84
  `latitude`/`longitude` and EGM96 (MSL) `altitude` in meters.
- Geo-reference: UE world origin = OpenDRIVE origin =
  `lat 42.3005934157, lon −83.69928318881136` (from
  `Content/McityMap/OpenDrive/McityMap_Main.xodr`); UE **+X = true north**,
  **+Y = true east**; UE Z is true MSL elevation (Mcity ground ≈ 270 m).
- NED → UE: `x_ned = X_ue/100 (m, north)`, `y_ned = Y_ue/100 (m, east)`,
  `z_ned = −Z_ue/100` — use this to place spawn points in
  `sim_config/scene_basic_drone.jsonc` (`origin.xyz`, NED meters).
- ⚠️ Project AirSim's topics channel is **one client at a time** (nng Pair0).
  Don't connect a second client while a flight script runs; relay data
  instead (see `send_gps_beacon()` in `keyboard_control_gnss.py`, which feeds
  the web UI over localhost UDP).

---

## Manual installation (what the script does)

```bash
cd /path/to/projectairsim/unreal
mkdir McityMap && cd McityMap
cp ../Blocks/Blocks.uproject McityMap.uproject
cp -r ../Blocks/Config Config        # then edit Config/DefaultEngine.ini:
                                     #   EditorStartupMap/GameDefaultMap/ServerDefaultMap
                                     #   → /Game/McityMap/McityMap_Main
cp -r ../Blocks/Source Source
ln -s ../Blocks/Plugins Plugins
cp -r /path/to/mcity_proj_airsim/McityMap/Content Content
"$UE_ROOT/Engine/Build/BatchFiles/Linux/Build.sh" BlocksEditor Linux Development \
    -project="$(pwd)/McityMap.uproject"
```

---

## Troubleshooting

| Symptom | Cause / fix |
|---|---|
| `Timeout waiting to get topic info` in the flight script | Another client is connected to the sim — the topics channel is strictly one-client (nng Pair0). Close other client scripts/tools. Also occurs if the editor isn't in **Play**. |
| Flight keys do nothing | Keys only act while the **"Chase Cam + GNSS" window has focus** — click it once. Typing in the terminal or browser is intentionally ignored. |
| `python-xlib is required` on startup | `pip install python-xlib` (also in `requirements.txt`). Key state is read from the X server, scoped to the GNSS window — works on X11 and XWayland. |
| Map page loads but stays gray / watermarked | Missing or unrestricted-invalid Google Maps API key — check `mcity_scripts/.env`, restart `gps_ws_server.py`. |
| Overlay shows "waiting for GPS fix…" | The robot config must have the GPS sensor enabled — the shipped `sim_config/robot_quadrotor_fastphysics.jsonc` already does; make sure you didn't override `--simconfigpath` to a config set without GPS. |
| Editor fails to load the map / assets show as errors | Engine too old — the content requires UE 5.7.x. |
| `Sim libs not built yet` from the setup script | Run `./build.sh simlibs_release` in your Project AirSim repo first. |
| Plugin compile errors: `member access into incomplete type 'UUnrealCamera'` (UnrealScene.cpp) or `use of undeclared identifier 'WorldSimApi'` | Known latent includes in Project AirSim, normally masked by Unreal's unity build. Fixes: add `#include "Sensors/UnrealCamera.h"` to `UnrealScene.cpp`, and remove the unused `#include "UnrealScene.h"` from `World/WorldSimApi.h`. |
| Wrong-looking orientation after editing the map | Run `McityMap/verify_mcity_rotation.py` headlessly (see its docstring) — it prints a ROTATED/UNROTATED verdict. Never run any rotation script on this content; it ships already rotated. |

---

## Credits & licenses

- **McityMap content**: University of Michigan / Mcity —
  [mcity/mcity-digital-twin](https://github.com/mcity/mcity-digital-twin)
  (v1.6.0, converted to UE 5.7 and geo-aligned). See
  `McityMap/Content/McityMap/LICENSE.txt`.
- **Project AirSim**: IAMAI Consulting Corp / Microsoft, MIT License —
  [iamaisim/ProjectAirSim](https://github.com/iamaisim/ProjectAirSim).
