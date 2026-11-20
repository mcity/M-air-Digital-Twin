# Troubleshooting

## Installing

**`the download from Hugging Face failed`.** Check the dataset id (`--hf-repo`). If the dataset is private
or gated, log in first: `.venv/bin/hf auth login` (older versions: `huggingface-cli login`). Running the
installer again resumes where it stopped.

**`could not create a Python environment`.** On Ubuntu: `sudo apt install python3-venv`.

**The build fails in `ProjectAirSim`.** Build *Development* only. The prebuilt plugin has no debug sim
libs. Check that `ProjectAirSim`, `Drone` and `Rover` sit directly in the project's `Plugins/` folder.

**Source build of Project AirSim: the sim-libs configure step fails downloading onnxruntime 1.12.1
(HTTP 404).** The URL in Project AirSim 1.0.1's CMake files no longer exists. What worked for us: take
`onnxruntime-linux-x64-gpu-1.12.1` (its `include/` and `lib/` folders; the prebuilt plugin release
contains the same files under `Plugins/ProjectAirSim/SimLibs/shared_libs`), and configure the build with
`-DFETCHCONTENT_SOURCE_DIR_ONNXRUNTIME=/path/to/onnxruntime-linux-x64-gpu-1.12.1`. The setting is lost
after `./build.sh clean`.

## Starting the simulator

**Nothing appears for minutes on the first start.** Expected: Unreal is compiling shaders and building
the scan mesh (about 3 minutes on our machine). Watch progress with `scripts/run_sim.sh -log`.

**The terrain is grey or untextured.** The aerial imagery is a very large virtual texture that Unreal
builds once, on first use: about 15 minutes and roughly 25 GB of memory on our machine. Leave the
simulator running; the imagery appears when it finishes, and later starts are immediate. If it never
appears, check that `Content/AnchorBaked/mcity_066m_naip.uasset` exists in the plugin (6.8 GB).

**It crashes with `Assertion failed: SceneInfo->bIsCachedRayTracingInstanceValid`.** That is hardware
ray tracing. The bundled project turns it off and `scripts/run_sim.sh` passes `-noraytracing`; make sure
you are not starting with `MAIR_RAYTRACING=1`.

**Vulkan or RHI errors at start.** Update the NVIDIA driver and check `vulkaninfo` runs cleanly.

## Flying

**`Connection refused`.** The simulator is not running, or not on the ports the script uses.

**A script stops at `Getting the list of available topic info` and times out.** Another client is still
connected: the simulator serves one at a time, and a forgotten one reconnects by itself whenever the
simulator restarts. Find it with `ss -tnp | grep 8989` and close it. To work around it without closing
it, use other ports for both sides:

```bash
AIRSIM_TOPICS_PORT=8991 AIRSIM_SERVICES_PORT=8992 scripts/run_sim.sh
AIRSIM_TOPICS_PORT=8991 AIRSIM_SERVICES_PORT=8992 scripts/fly_mission.sh missions/mcity_circle.json
```

**The drone falls when the scene loads.** The stock scene spawns it about 250 m up, and nothing holds
it until a script takes control. `fly_mission.sh` and `hover_test.sh` take control immediately.

**`No landscape plan at ...`.** `MAIRCORRIDOR_PLAN` in `maircorridor.env` must point at
`MAirCorridor_Assets/ue_rect_3m/mcity_rect_3m.json`.

**Keyboard flight does nothing.** Keys are read from the X session; a Wayland session may not deliver
them. Log in with "Ubuntu on Xorg".

**Camera recordings have a low frame rate.** Each camera capture is a full extra render of the scene.
Record fewer or smaller cameras.

## Known limitations

- In the drone's downward camera the Mcity scan can look much darker than it does in the main view.
- Generated trees render white in places.
- The Ouster lidar plugins used by some upstream scenes need hardware ray tracing and are not part of
  this package.
