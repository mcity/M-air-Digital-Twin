# MAirCorridor geodata tools

Python tools that download elevation data and aerial imagery for **any area** and turn them into
Unreal Engine Landscapes. The M-Air corridor is one example; nothing here is specific to it.

| Tool | What it does | Coverage |
| --- | --- | --- |
| [`download_3dep.py`](download_3dep.py) | Downloads USGS 3DEP bare-earth elevation (1 m lidar down to 30 m) | United States |
| [`download_copernicus_dem.py`](download_copernicus_dem.py) | Downloads the Copernicus 30 m or 90 m global surface model | Worldwide |
| [`build_landscape.py`](build_landscape.py) | Turns **any** elevation rasters into Unreal heightmaps and a landscape plan | Any |
| [`download_naip.py`](download_naip.py) | Downloads USDA NAIP aerial imagery as tiles aligned to a landscape | Lower 48 US states |
| [`launcher.py`](launcher.py) | **MCity Digital Air Command**: plays the simulation, opens the editor and every tool below, and says whether Unreal is running | |
| [`package_release.py`](package_release.py) | **Bakes the project into a release** that runs without the editor | Windows |
| [`geodata_ui.py`](geodata_ui.py) | **A window that runs all of it**: draw the area on a map, then download, build and fetch imagery | |
| [`mapview.py`](mapview.py) | The map inside those windows: OpenStreetMap tiles, pan and zoom, drag out an area or place waypoints | |
| [`flightplan_ui.py`](flightplan_ui.py) | **The flight planner**: name waypoints on a map, set heights and speeds, fly them | |
| [`flightplan.py`](flightplan.py) | Mission model, and the ground and frames behind it | |
| [`fly_mission.py`](fly_mission.py) | Fly a saved mission with no window, and record everything the drone carries | |
| [`recording.py`](recording.py) | What a flight writes down, and the manifest that makes it a dataset | |
| [`realflight.py`](realflight.py) | **A real flight into a mission**, and one flight measured against another | |
| [`recover_video.py`](recover_video.py) | Makes a video playable again after a recording was cut short | |
| [`adsb.py`](adsb.py) | **Real aircraft overhead** from the OpenSky Network, in this landscape's frame | |
| [`airspace.py`](airspace.py) | **A mission as declared airspace**: 4D volumes, conformance, and the operation's lifecycle | |
| [`geofences.py`](geofences.py) | Geofences, ED-269 import, and the strategic check every operation must pass | |
| [`geoid.py`](geoid.py) | Between GPS heights and this landscape's heights, from NOAA's GEOID18 | |
| [`tests/`](tests) | The control loop, deconfliction, geoid and traffic feed, testable with no simulator | |
| [`geodata_common.py`](geodata_common.py) | Shared code: areas of interest, resumable downloads, UTM zones | |
| [`uikit.py`](uikit.py) | Keeps the windows on screen: sized to fit, panels that scroll | |
| [`examples/mair_corridor_boundary.kml`](examples/mair_corridor_boundary.kml) | The M-Air corridor outline, for reproducing this project's area | |

## The window

```
py -3.10 geodata_ui.py
```

Everything below can be done from one window instead of the command line. The area is chosen on a map:
pan with the left button, zoom with the wheel, hold Shift (or press "Draw box") and drag out the
ground you want, and the four numbers fill themselves in. A KML you load is drawn on the map too, so
you can see what you picked. "Find place" jumps to a named town or landmark.

Set a working folder and each step hands the next what it made. The elevation lands in `<work>/dem_cache`,
the landscape plan in `<work>/landscape`, the imagery in `<work>/naip`. Output streams into the log
as it happens, with Cancel, and the command for each step is printed so it can be repeated by hand.

It needs only Python and tkinter, which ships with Python, so it runs on a machine with no engine
installed: download overnight, build the plan, import it in Unreal later. Your entries are remembered
between runs.

Read on for what each step means and what the arguments do; the window sets the same ones.

The whole workflow is:

```
area (KML or box)  ->  download elevation  ->  build_landscape.py  ->  Unreal: Build Landscape from Plan
                   ->  download imagery (aligned to the plan)   ->  Unreal: material on the Landscape
```

---

## MCity Digital Air Command

```
run            from the project or plugin root, or:  py -3.10 launcher.py
```

The launcher: one window listing everything here and what it is for: play the simulation, open
the editor, plan a flight, fly a saved mission, fly on the keyboard, download terrain, build a
release. It shows whether Unreal is running, because anything that flies needs the simulation
playing, and it warns rather than failing silently when it is not. Each button starts the same
program you could start yourself.

**Play** opens the M-City corridor level straight into play mode, with no editor around it:

```
UnrealEditor.exe TheUniverse.uproject /MAirCorridor/Scene/CorridorTerrain -game -windowed -ResX=1600 -ResY=900
```

The simulator starts with the level, so a flight can go as soon as it is up. It is also lighter
than Play in the editor, which renders its own viewport and interface on top of the game. To change
the level, use **Open the editor** instead and press Play in it. **Release** runs the packaged build
the same way, once one has been made.

## Flight planning

```
py -3.10 flightplan_ui.py            or, from the project or plugin root:  run plan
```

Click the map to place waypoints, drag one to move it, name them, and give each a height and a
speed. Press Fly and the drone takes off, flies them in order and lands. The editor must already be
in Play, because Project AirSim's sim server starts with the game.

**Height means one of two things, per waypoint.** `agl` is metres above the ground directly beneath
it, read from the landscape's own heightmap, so a waypoint at 80 m is 80 m over a hill or a valley
alike. Between two waypoints the leg is a straight line, so it follows the ground only as closely
as the waypoints do: to hold a height over changing ground, put more waypoints where it changes.
`msl` is an absolute altitude above sea level, for a cruise leg that should hold one height. `sim`
is metres up in the simulator itself (Unreal Z / 100, the frame the level and Project AirSim use),
flown at exactly that number: a waypoint at `sim` 29.7 is flown to NED down -29.7. The panel shows
the numbers for whichever waypoint is selected, and refuses anything within 2 m of the ground,
except the first and last waypoints, which may sit on it: the last is where it lands. No move goes
lower than 0.75 m above the ground.

Landing is Project AirSim's land command, which finishes after a full second with no vertical speed.
A heavy drone on rough ground can keep bouncing by centimetres long after it is down: the hexa sat on
the M-City scan for 90 s before the command finished, and ran past its declared landing window. So a
landing also counts as done once the drone has come down at least 1 m under the land command and
then stayed within 10 cm up and down and 30 cm sideways for 5 simulated seconds, and the flight says
so (`down: still for 5 s`).

### Where it starts

**Start** sets where the drone is when the flight begins: a longitude and latitude, and a height
above the ground (0 is on it) or above sea level. Pick on map takes the next click, At first
waypoint puts it on the ground under the first waypoint, and Scene's clears it. A mission with no
start uses the spawn in its scene config, which every mission sharing that scene shares; a start
moves the drone for this mission only (`fly_mission.py` loads a copy of the scene with the drone's
origin moved, `<scene>.flight.jsonc`, and leaves the scene itself alone). The declared airspace and
the strategic check climb out from the same point. Only the landscape counts as ground: a start on
a building, a tree or the M-City scan needs a height that clears it. In the mission file it is

```
"start": {"lon": -83.696641, "lat": 42.299961, "height": 0.0, "reference": "agl"}
```

with an optional `yaw_deg` for the heading it starts facing.

The level streams in around the camera after Play starts, so the drone arrives before the ground
under it has loaded, with nothing to stand on. So the scene `fly_mission.py` loads starts paused
(`<scene>.flight.jsonc` always sets `pause-on-start`), and before letting the sim go it takes
control, arms the drone and gives the controller its start to hold. The drone never drops, and it
hovers there on every run, including **List** (`--list-capabilities`): the controller keeps holding
after the script has gone.

**A flight leaves from the start, with no takeoff and no landing first.** The start is where the
planner put it, in the air or on the ground, and the route is flown from there: every waypoint in
order, the first one included. A first waypoint at the start is a move of nothing, and the drone
simply goes on to the second. It does not wait for the level to stream in under it, so the first
seconds of a recording can show the world still loading.

The trees have collision. A start inside or under a tree climbs into its canopy and sits there,
flying hard and going nowhere, until the conformance check calls a contingency. Every collision is
printed with the name of what was hit (`COLLISION with ...`), so the output says when this is what
happened; move the start clear of it.

### Which way it faces

A multirotor can fly east while pointing north, and the controller's own default does exactly that:
it holds whatever heading it took off with, so every camera films sideways. **Cameras look** in the
planner decides this for the mission, and `--yaw` overrides it for one flight:

| Mode | What the aircraft does |
| --- | --- |
| `forward` | Turns the nose along the direction of travel, so the view is of what is coming. The default. |
| `waypoint` | Holds one heading down each leg, aimed at the waypoint being flown to, and keeps it while it waits there. Steadier for an inspection shot. |
| `free` | Leaves the heading alone, for a mission that points the aircraft some other way. |

```
py -3.10 fly_mission.py missions/patrol.json --yaw waypoint
```

`--dry-run` prints the heading of every leg in degrees from north, so a route can be checked for
where it will be looking before anything flies. The first leg is flown from the mission's start, so
`waypoint` aims from there.

A leg less than 2 m across the ground, such as a climb from the start to a WP1 straight above it,
keeps the heading the aircraft has (`kept` in the dry run), and the next leg turns it. The heading
of a straight climb is just the angle of a few centimetres of rounding between the two points, and
following it, a 6.3 kg quad spun 190° and back on the way up.

### Watching a flight

While a mission flies, the window draws the drone and the path it has actually taken against the one
you planned, and reads out how far off the line it is:

```
off path 14.3 m (worst 17.9 m), 326 m above sea level on TrackCentre to Cruise
```

**Deviation is measured to the line, not to the next waypoint.** A drone cutting a corner is where it
should be; one 40 m to the side of a leg is not, even sitting halfway between two waypoints. The
readout turns amber past 10 m and red past 25 m, and every sample is written to `track.jsonl` in the
flight's folder, so a run can be examined afterwards.

The runner owns the connection and prints the positions; the window only draws them. A flight
started from a terminal is therefore still a flight, and the same lines can be watched here.

### Recording everything

**Record everything the drone carries** in the planner, or `--all` on the runner, subscribes to
every stream the drone actually has: each camera as video, each sensor, the camera metadata that
arrives beside every image stream, and the aircraft's own collision and rotor state.

```
py -3.10 fly_mission.py missions/patrol.json --all
py -3.10 fly_mission.py missions/patrol.json --all --frames       and lossless stills
py -3.10 fly_mission.py missions/patrol.json --record-all --no-video --frames
py -3.10 fly_mission.py missions/patrol.json --record DownCamera --log-sensor IMU1
py -3.10 fly_mission.py missions/patrol.json --dry-run --all       what it would record
py -3.10 fly_mission.py missions/patrol.json --list-capabilities   what the drone has
```

`--record CAMERA` takes every image stream that camera publishes, or one of them with
`--record CAMERA:depth_camera`. `--log-sensor NAME` takes a sensor's data streams, and
`--log-sensor robot:collision_info` takes one of the aircraft's own. Everything from one flight
lands in `missions/flights/<timestamp>`.

**`--dry-run --all` prints the whole recording plan without connecting to anything**, worked out
from the scene and robot configs on disk. `--list-capabilities` asks the running simulator instead,
and that answer is the authority:

```
would record
  Chase          scene_camera               video
  DownCamera     depth_camera               lossless frames (sixteen bit)
  DownCamera     scene_camera               video
  DownCamera     segmentation_camera        video
  DownCamera     scene_camera_info          data
  IMU1           imu_kinematics             data
  robot          collision_info             data
  the flight     track.jsonl                pose and deviation
```

**A sensor that is declared but switched off publishes nothing.** `"enabled": false` in the robot
config still leaves the sensor in the list the client builds, so recording it would write empty
files and look like a fault. Those are skipped and named in a warning. On the drone this project
ships, the GPS, barometer and magnetometer are off; switch them on in the robot config if a flight
needs them.

**Depth is never written as video.** A depth or disparity image arrives as sixteen bit single
channel pixels, and an eight bit video codec would throw away the measurement that makes it useful.
Those streams are always written as sixteen bit PNG frames, whatever was asked for, and the
manifest says so. Eight bit streams honour `--video` and `--frames`, which can both be on: the
video is for watching, the stills are for training.

**Sensors are not created here**: they are whatever the robot config declares for the drone. To add
a camera, a lidar or a radar, add it to that config; this records what exists.

#### What a flight leaves behind

| Path | What it holds |
| --- | --- |
| `manifest.json` | Every stream below, described: files, counts, sizes, camera geometry, and the frame the numbers live in |
| `mission.json` | The mission as flown, copied in |
| `track.jsonl` | Pose as the simulator reported it, with the deviation from the plan measured alongside |
| `<sensor>_<stream>/<sensor>.mp4` | The stream as video |
| `<sensor>_<stream>/000000.png` | Lossless frames, sixteen bit for depth |
| `<sensor>_<stream>/index.jsonl` | Frame number, wall time, **sim timestamp**, size and encoding |
| `<sensor>_<stream>/annotations.jsonl` | Object ids and bounding boxes, when the camera publishes them |
| `<sensor>_<stream>.jsonl` | One line per message of a data stream |
| `<sensor>_<stream>.<field>.f32` | Bulk arrays, such as a lidar point cloud, as raw binary |

**Every stream carries the simulator's own clock**, not just wall time, which is what lets a frame
be lined up with the IMU sample and the pose that go with it. `--sensor-hz N` caps a data stream if
needed; the default keeps every message.

**A lidar message is tens of thousands of floats**, so bulk arrays leave the JSON. Any array of 48
numbers or more is appended to `<stream>.<field>.f32` (or `.i32` for whole numbers, so segmentation
ids come back exactly), and the line keeps `{"f32": [offset, count]}` in its place, counted in
elements rather than bytes. Reading the third message's point cloud is then two lines:

```python
row = json.loads(open("Lidar1_lidar.jsonl").readlines()[2])
offset, count = row["msg"]["point_cloud"]["f32"]
points = numpy.memmap("Lidar1_lidar.point_cloud.f32", dtype="<f4",
                      mode="r")[offset:offset + count].reshape(-1, 3)
```

### The drone has to carry the sensors

**A sensor that a robot config declares with `"enabled": false` is never updated by the simulator**,
so it publishes nothing: `Robot::Impl::UpdateSensors` only touches enabled sensors. Project AirSim's
own sample configs ship with the GPS, barometer and magnetometer switched off and no lidar at all,
and the scene this project started from names one of those samples. Flying needs none of them.
Collecting data does.

So there are two scenes, and a mission names the one it wants:

| Scene | Drone | What it carries |
| --- | --- | --- |
| `scene_mcity.jsonc` | Project AirSim's `robot_quadrotor_fastphysics_weather` sample | Chase camera, a 400x225 down camera with colour, depth and segmentation, an IMU. GPS, barometer and magnetometer declared but off |
| `scene_mcity_sensors.jsonc` | `robot_mcity_sensors.jsonc`, ours | The same flight model, and **every sensor on**: chase camera at 1280x720; down camera at 640x360 in colour, depth, segmentation and surface normals; IMU, GPS, barometer, magnetometer, airspeed, battery, a 16 channel 120 m lidar and a downward distance sensor |

Two scenes rather than one because the sensored drone renders four camera streams and sweeps a
lidar, which costs frames. Keyboard flying and quick missions can stay on the light one.
`missions/mcity_collect.json` is the patrol route on the sensored scene, flown at 50 m and 8 m/s.

The flight model is deliberately identical: the links, joints, controller and actuators in our
config are copied from the sample this project has always flown, so the aircraft handles the same
and a route flown on one scene is comparable with the same route flown on the other.

#### What the sensors actually produce, measured

Flights over the corridor were checked against their own tracks. Every flight before the
correction below was flown about 236 m higher than the tools said, which is what the range sensors
were reporting; the table is from the first flight at the corrected heights, `mcity_collect` on 4
October 2026, flown against a packaged release.

| Stream | What came back |
| --- | --- |
| `scene_camera` (both cameras) | Real imagery, 42 KB a frame on the down camera and 140 KB on the chase view |
| `surface_normals_camera` | Real, varying imagery |
| `segmentation_camera` | Recorded before the level was labelled: Project AirSim's own ids, one arbitrary class per actor name. See **Segmentation classes** below for what it carries now |
| `depth_planar_camera` | **Metres, in whole metres.** Centre depth tracks the distance sensor within a few percent: 34 against 31.6 m, 40 against 38.5 m, 29 against 27.7 m. The camera sits about 1.5 m above the distance sensor |
| `lidar` | Switched off (see below), so not yet seen at the corrected heights. It was empty at the old ones, 200 m and more above anything |
| `distance_sensor` | **Real ranges, in centimetres**: 1059 readings, median 3558, longest 5520 against its 60 m reach. 38 were zero, out of range. It read exactly 0.00 at the old heights |
| `collision_info` | One report: the landing, on the corridor terrain tile at Z 63.78 m with the surface normal up |

**A correction.** An earlier version of this README called the depth stream flat and not
measuring the scene. That came from comparing a 10 m band of heights, over which depth changed by
about 12 units, against an expectation of millimetres, which would have changed by 10,000. It was
measuring all along. A flight that climbed from the ground to 46 m shows the relationship clearly.

**Every flight was 236 m too high.** The tools turn heights into Unreal coordinates using the
landscape's placement, and they took it from the landscape plan, which says the landscape actor is
at Z 23599.85 cm. In the level it is at **Z 0**: it was moved down after import, along with the
corridor tiles and the scan. Read from the level and traced straight down at the drone's start:

| | The tools believed | The level, measured |
| --- | --- | --- |
| Landscape actor | Z 23599.85 cm | Z 0 |
| Ground under the start | Z 26570 cm | Z 2982 cm, a trace hitting the landscape |
| The drone's start, NED down -291 | 25 m above the ground | 261 m above it |

So a mission at 40 m above the ground flew about 276 m above it. That accounts for what the range
sensors did, and the first flight at the corrected heights bore it out (the table above):

- **The lidar** (120 m range) and **the distance sensor** (60 m) had nothing within reach.
- **Depth's offset near 215** is the extra height: depth reads about one unit per metre, and "on
  the ground" the drone was a couple of hundred metres up.
- **The drop after takeoff**: the drone starts in the air and falls until the controller catches
  it, and there was nothing under it for 260 m.
- **A landing that never finished**: the descent timed out on its way down to ground the tools
  thought it had already reached.

Fixed in the tools, not the level. `level.json` records where the landscape actually is, measured
by `unreal/measure_level.py`, and `flightplan.py` uses it in place of the plan's placement. The
ground the tools now compute under the start is Z 2975 cm, against 2982 traced. Measure again
whenever the landscape is moved:

```
UnrealEditor-Cmd.exe <project>.uproject -run=pythonscript -script=<absolute path>/Tools/unreal/measure_level.py "-EnablePlugins=PythonScriptPlugin,EditorScriptingUtilities" -unattended -nullrhi
```

The scene's start was not moved, because it is to move to the vertiport. Until then a flight
begins 261 m up and descends to its first waypoint.

**The scan sits 8.45 m above the landscape.** Its vertical offset (`Align Z Offset Cm` on the scan
component) was fitted as 16404.7 cm when the landscape was at Z 23599.85. Moving with the
landscape makes it 16404.7 - 23599.85 = **-7195.15 cm**; the level has **-6350**. Computed from the
tiles at the drone's start, the scan's lowest point there is Z 3827 cm, against 2982 for the
landscape: 8.45 m. Heights above the ground in a mission are above the landscape, so over the scan
they are 8.45 m less than they say.

The lidar and the distance sensor trace on Unreal's **Visibility** channel from their own mounting
point (`UnrealLidar.cpp`, `UnrealDistanceSensor.cpp`), and that trace does hit the landscape: the
measurement above used it.

`lidar1` is now **switched off** in `robot_mcity_sensors.jsonc`. In its GPU form it costs eight
scene renders every frame (see below) while returning nothing. Set `"enabled": true` to work on it.

#### Segmentation classes

The segmentation camera draws each surface in the colour of its class. The classes are
[`segmentation.json`](segmentation.json), written into the level's components by
`unreal/label_segmentation.py` (run in the open editor; it saves only the actors it changes):

| Class | Id | Colour (RGB in a recorded frame) | What carries it |
| --- | --- | --- | --- |
| unlabelled | 0 | 55, 181, 57 | Anything else, and the sky |
| ground | 1 | 153, 108, 6 | The landscape |
| building | 2 | 112, 105, 191 | The OpenStreetMap building tiles |
| tree | 3 | 89, 121, 72 | Every tree model in the vegetation library |
| rock | 4 | 190, 225, 64 | Every rock model |
| scan | 5 | 206, 190, 59 | The M-City scan: one mesh, so its buildings, trees and roads are one class |
| drone | 6 | 81, 13, 36 | The flown aircraft, labelled by `fly_mission.py` when the scene loads |

Every recorded flight's manifest carries this table as `segmentation_classes`, colours included.
The colour is Project AirSim's palette entry for the id, as it lists it; checked against a recorded
segmentation video decoded to RGB, pixels sit a median 4 units from the entry as listed (video
compression) and 34 from it reversed.

**Why the ids are in the level, and Project AirSim's own labelling is off.** Its pass at scene
start (`InitSegmentationIDs`) makes an id by adding up the letters of each mesh owner's name,
**overwrites** whatever the level holds (`"ignore-existing": false` only stops a name being
assigned twice), and reaches only what is loaded at that moment. With the foliage in one actor per
square kilometre, each square kilometre would have been a different arbitrary class, and anything
World Partition streams in after the scene starts would have had none. Written into the
components, an id streams in with them. The scene configs set `"initialize-ids": false`, and
`stream_foliage.py` and `place_scan_mesh.py` label what they make, so running them again keeps the
classes.

Labelled in the corridor level: 12,560 tree components (339 foliage actors), 5,494 rock
components, 100 building tiles, the landscape and its 44 streaming proxies, and the scan.

**A dead sensor says so.** A stream whose every message has empty lists, and an image stream whose
every pixel holds one value for the whole flight, are both called out in the summary and the
manifest:

```
lidar1/lidar: 140 messages, EVERY ONE EMPTY: the sensor published but measured nothing.
```

Only a single constant value is flagged for an image stream. An earlier version flagged anything
within 2 percent of full scale, which would have called the working depth stream broken: at about
one unit per metre, a whole cruise fits in a few dozen units.

**On depth units.** Depth is metres, checked against the distance sensor. The simulator's packing
code (`ImagePackingAsyncTask.cpp`) names its variable `DepthMilli` but holds metres in it, and
casts to `uint16` by truncation, so **everything below a metre is thrown away** before the
recording sees it. Finer depth needs that packing changed in Project AirSim: centimetres would
still reach 655 m.

#### How fast a flight can actually record

Four camera streams plus a lidar sweep cost frames. The `capture-interval` asks for 10 a second;
the flight above managed **2.14 a second**, measured from the simulator's own clock. Nothing is
wrong with that recording, but it is a quarter of the rate it asked for, and a video written at
the rate that was *requested* plays nearly five times too fast.

So a video is written at the rate the frames actually arrived at, measured over the first few
frames rather than assumed, and `index.jsonl` carries the exact timestamp of every frame either
way. The manifest reports both numbers, and says so when they disagree:

```
"fps_written": 2.0, "fps_measured": 2.143
```

To record faster, record less: fewer streams, smaller frames, or a longer capture interval that
the sim can actually keep.

#### Keeping it fast

A slow flight can be slow in two ways, and they have different cures:

- **The simulation falls behind real time.** Physics and the controller cannot keep up. Read it
  as `speed`: simulated seconds per real second, from the pose's two clocks.
- **The cameras fall behind their rate.** Physics keeps up, but every capture is a full extra
  render of the scene and the frame cannot fit them all. Read it from each camera's delivered
  rate against the rate its `capture-interval` asked for.

Every recorded flight now reports both when it ends (`speed: the simulation ran at 0.97 of real
time`, then a line naming the camera that fell furthest short) and keeps them in the manifest's
`performance` block. `flight_perf.py` sets flights side by side:

```
py -3.10 flight_perf.py
```

The first flights over M-City, all with the full sensor drone:

| Flights | Recording | Speed | Cameras, frames a second |
| --- | --- | --- | --- |
| 110108, 125139 | everything | 0.87, 0.90 | 1.7 to 2.8 delivered, against 10 asked (down camera) and 33 (chase) |
| 131256, 131701, 131822 | nothing | 0.93 to 0.95 | none recorded |

**Where the frames went**, from Project AirSim's source:

- A camera renders an image type only while something subscribes to it (`UnrealCamera.cpp`,
  `HasSubscribers`). A flight that records nothing pays nothing for cameras. One that records
  everything pays for every type: the down camera's colour, depth, segmentation and normals are
  four separate renders.
- The GPU lidar (`gpu_cylindrical`) renders **eight** captures every tick, four 90 degree depth
  views and four intensity views, whether anything subscribes or not, with no rate limit
  (`GPULidar.cpp`, `Simulate`). That is why the flights that recorded nothing still ran below
  real time.

With everything on, a frame asked for up to 14 renders: the viewport, the chase camera, four from
the down camera and eight from the lidar. The chase camera's interval was shorter than any frame,
so it captured whenever it could; its 2.8 a second is about the frame rate the editor managed.
Each of those renders draws the scan, and Lumen and virtual shadow maps run inside captures as
well. Ray tracing does not: scene captures leave it off unless told otherwise.

**What changed:**

| Change | Where | Why |
| --- | --- | --- |
| `lidar1` off | `robot_mcity_sensors.jsonc` | Eight renders a frame for empty clouds |
| Chase camera at 10 a second, not 33 | `robot_mcity_sensors.jsonc` | The costliest capture (1280x720), and it never got above three |
| The scan casts no shadows | `Cast Shadows` on the scan component, off by default | Every capture keeps shadow maps of its own and the scan is the heaviest thing in them. Its photographs already hold the day's shadows, and the unlit material receives none |

A flight with these changes has not been measured yet. Fly `mcity_collect` once and run
`flight_perf.py`; the flights above are the baseline.

**Further levers**, cheapest first:

1. **Record only what you need.** A stream nobody subscribes to costs nothing, and `--all`
   subscribes to everything. Colour from the down camera alone is one render, not four:
   `--record DownCamera:scene_camera --log-all` keeps every sensor's data and that one video.
2. **Longer intervals and smaller frames.** A camera can never deliver more than one frame per
   rendered frame, so asking for more only fills the capture queue.
3. **Run the game standalone rather than Play In Editor.** The editor's viewport and interface are
   rendered too.
4. **Find out which side is slow before changing anything else.** In the editor during a flight,
   `stat unit` shows whether the game thread or the GPU sets the frame time, and `stat gpu` shows
   where GPU time goes. Hiding the scan actor for a few seconds shows what the scan costs.
5. **Project render settings.** Lumen, virtual shadow maps and hardware ray tracing are on for the
   whole project (`Config/DefaultEngine.ini`). They affect every level, not just this one, so they
   are left alone here.

### M-City: the scan or the digital twin

M-City can be shown two ways, one at a time: the **photogrammetric scan** (the M-City Scan actor,
the default), or **Mcity's digital twin**, the authored McityMap level from
[mcity/M-Air-Digital-Twin](https://github.com/mcity/M-Air-Digital-Twin) (version 1.9.1, UE 5.7),
installed as the `McityMap` plugin beside this one. Switch with any of:

```
mair.McityView Scan | Twin | Toggle                  the console, in Play or a game
-MAirMcityView=Twin                                  the command line, to start that way
py -3.10 fly_mission.py <mission> --mcity twin       for a flight (the planner's M-City box)
```

In twin mode the scan is hidden, with its collision and tile streaming off, and the twin's levels
are loaded in its place. The scan here is the one Nanite mesh `place_scan_mesh.py` put in the
corridor level ("M-City Scan (Nanite)", known by its mesh, `/MAirCorridor/Scan/20M16`), or the
streamed scan actor it replaced, whichever the level has. At first only the streamed actor was
switched, so the twin view showed the scan as well, and drones landed on it.

The twin's levels are the main map and its terrain, props, street lights, cables, signs, traffic
lights and road network, but not its own lighting or splash screen. The lights, sky and fog the twin
brings are removed, so the corridor keeps one sun.

**Where it goes.** The twin is geo-anchored: its origin is lat 42.3005934157, lon -83.69928318881136
(the transverse Mercator in its OpenDRIVE file), +X true north, +Y true east, Z elevation above sea
level. Fitted onto this level's UTM grid over the twin's whole extent, that is a yaw of -88.1826 deg
and a move of (959207.9, 1089057.1, -23599.85) cm, with a worst residual of 0.08 cm. UTM's scale
factor here (1.0002) is left out, since a level cannot be scaled: at most 5 cm at the twin's edge.
Its ground stands about 1.4 m above this landscape's elevation model at Mcity, the same difference
the scan was measured to have, so the landscape stays underneath it.

Not yet: the planner's map and the flight tools' terrain still measure heights from the landscape,
not from the twin's own ground; and a few of the twin's props sit at its zero height, 236 m below
the ground, where nothing sees them.

**The redirect it depends on.** The twin's assets were authored under `/Game/McityMap`, and every
reference inside them says so; the plugin mounts at `/McityMap`. One redirect maps the first onto
the second, in the plugin's `Config/DefaultMcityMap.ini`. It has to be in that file, named after
the plugin: Unreal reads redirects only from the config it loads at startup, and a plugin's
`DefaultEngine.ini`, where it was at first, is not part of that. There it was never read, every mesh
the twin's levels place came back empty, and the twin view showed nothing.

#### What was under them

The corridor level was built from OpenStreetMap and a foliage placer before M-City was in it, so
where the scan and the twin stand it also had its own buildings and trees, poking through. They
were found and cleared in three steps:

```
UnrealEditor.exe ... -ExecutePythonScript=".../unreal/mcity_twin_footprint.py"   the twin's footprint
UnrealEditor.exe ... -ExecutePythonScript=".../unreal/mcity_clear_level.py"      MAIR_STEP=survey: what is around M-City
py -3.10 mcity_clear.py                                                          what is under what
UnrealEditor.exe ... -ExecutePythonScript=".../unreal/mcity_clear_level.py"      MAIR_STEP=apply (MAIR_DRY=1 first)
```

(each editor run off screen, with `MAIR_QUIT=1`; the scripts' docstrings have the full lines.)
[`mcity_clear.py`](mcity_clear.py) makes a 1 m mask of each on the level: the scan from its
coarsest vertices, gaps closed and holes filled; the twin from every triangle of its ground and
roads and the box of each smaller piece. A building is under a mask when 30 % of its ground plan
is, and a tree when its trunk is within 3 m of it. It writes a preview to look at first
(`Saved/MAirCorridor/mcity_clear_preview.png`).

The twin's footprint is 0.174 km², all of it inside the scan's 1.954 km², so nothing was under the
twin alone. Of the 917 buildings and 12,116 trees and rocks around M-City:

| under | buildings | trees and rocks | done |
|---|---|---|---|
| both | 8 | 1,296 | deleted |
| the scan only | 371 | 6,128 | tagged `MAirUnderScan`: hidden, with no collision, while the scan is shown |

The scan-only trees moved out of their square kilometre's foliage actor into one beside it
(`Foliage_<cell>_UnderScan`), because a tag hides a whole actor. MAirMcityViewSubsystem applies the
tags at the start, on every switch, and to each level World Partition streams in. In the editor's
own viewport nothing is hidden. Six buildings only partly under the scan (5 to 30 %) were left as
they are; `mcity_clear.py` lists them.

Before anything changed, each changed actor's file was copied to
`Saved/MAirCorridor/mcity_clear_backup/<time>/`. To undo it, with the editor closed, copy those
back and delete the four `Foliage_*_UnderScan` actors, whose trees the copied-back actors hold
again. [`mcity_cleared.json`](mcity_cleared.json) records each deleted building's mesh, materials,
transform and folder, and each deleted tree's mesh and transform.

### The lidar

```
py -3.10 fly_mission.py missions/CorridorMission.json --lidar
```

or tick **Lidar** under Record in the planner. The drone then carries a simulated **Ouster
OS-1-256-RGB**, the sensor on the real drone: 256 beams by 4096 columns, 5 scans a second, each
column cast from its own moment of the flight (the rolling shutter), with range, colour and
reflectivity per beam. It needs two plugins beside this one in the project's `Plugins` folder:

- **OusterSim**, the sensor itself: hardware ray tracing against the level, written as OSRAW/1 raw
  scans. Its `Tools/` validate them (`osraw.py`) and convert them to an OSF file that `ouster-sdk`
  reads as it would a recording of the real sensor (`osraw_to_osf.py`).
- **MAirLidar**, which mounts it: when a flight asks, it adds the sensor to Project AirSim's drone,
  records until the flight ends, and reports back. The flight and MAirLidar talk through two files
  in the project's `Saved/MAirLidar/`, so the same flight works in the editor and in a release.

**Where it goes.** OusterSim writes only under the project's `Saved/`, so the scans are in
`Saved/OusterSim/<flight folder name>/part_000/raw/`, and the flight's `manifest.json` says where,
how many scans and how many parts. A run holds at most 9999 scans (33 minutes of sensor time), so
a longer flight continues in `part_001` and on, with nothing missed between them.

**It is big and slow.** 25.6 MB a scan, 128 MB per simulated second: about 900 GB for the whole
400 ft corridor course. And the simulator runs several times slower while it records (0.12 of real
time in the first tests, against 0.4 without it), because every sector is a scene capture and a
ray trace of the whole level.

**One clock for the drone and the sensor.** A lidar flight changes the scene's clock: Project
AirSim's `engine-driven` clock at a 3.125 ms step instead of the usual `steppable` 3 ms. The usual
clock runs on its own thread at wall pace while the sensor runs on Unreal's frames, and in the
first tests the drone moved three times as far per sensor second as it should, smearing every
scan. `engine-driven` moves the drone exactly as Unreal ticks, and 3.125 ms is 25 ms / 8 exactly,
so the sensor traces one 512-column sector every eighth frame. The editor or game **must run with
a fixed time step** (start it with `-UseFixedTimeStep`), or MAirLidar refuses to record and says
so. With this clock the scene does not start paused (Project AirSim never unpauses it), so the
drone may drop for a fraction of a second before it is caught at its start.

**The mount** is the mission's `lidar_mount`: an offset in centimetres and a rotation in degrees in
the drone's own frame (x forward, y right, z up). Without one it is 20 cm forward on the nose,
level, which is a placeholder until the real airframe's mount is measured:

```
"lidar_mount": {"x_cm": 20, "y_cm": 0, "z_cm": 0, "roll_deg": 0, "pitch_deg": 0, "yaw_deg": 0}
```

The drone's own meshes are hidden from the sensor while it records (its ray trace and its colour
capture, not the cameras), since the quadrotor model is not the real airframe; they come back when
recording stops.

### Stopping a flight, and picking up the pieces

**Stop in the planner now asks the flight to wind up** and waits for it. The flight closes its
video, flushes its files and writes its manifest on the way out, and only gets killed if it will
not go within twelve seconds. Ctrl-C in a terminal does the same thing.

That was not free. An MP4 keeps its frame index in a `moov` box written when the file is CLOSED,
so a killed recording leaves every frame in place and no index: 147 MB that no player will open,
reported by ffmpeg as `moov atom not found`. The request travels down the flight's **stdin**, not
as a signal, because a Windows console control event only reaches processes sharing the sender's
console and these are started with `CREATE_NO_WINDOW`, so Ctrl-Break is silently discarded.
Measured, not assumed: the first attempt ran straight through the grace period every time.

Every text file in a recording is **line buffered** for the same reason. When that killed flight
was examined, `index.jsonl` held 833 rows for 987 recorded frames: the last 8 KB never reached the
disk. It now loses at most the line being written.

For the times nothing gets a chance to run, such as a power cut:

```
py -3.10 recover_video.py missions/flights/20261004-104219
py -3.10 recover_video.py missions/flights/20261004-104219 --replace
py -3.10 recover_video.py missions/flights/20261004-110108 --retime
```

It rebuilds the missing header from a throwaway file made by the same encoder at the same size,
taking the frame size and the rate from the `index.jsonl` that survived, and remuxes the orphaned
picture data against it. The 147 MB file above came back with all 987 frames. `--retime` does the
same rebuild to fix a video recorded before the frame rate was measured, and `--replace` puts the
result in place of the original, keeping the original beside it.

## Flight control

A mission is not just flown; it is **declared as airspace** first, **checked** against everything
else in the sky, and **watched** while it flies, with a defined response when it stops doing what
it declared. The model is ASTM F3548's, the standard UTM services use to coordinate drone
operations, as the OpenUTM project's
[Flight Blender](https://github.com/openutm/flight-blender) implements it. Nothing is copied from
Flight Blender; the ideas are, and a few of its choices are deliberately not (below).

### Declared airspace

`airspace.py` turns a mission into 4D volumes: a shape, an altitude band and a time window each.
The departure from the spawn point and the landing are declared too, because the aircraft flies
them even though the mission does not describe them.

```
py -3.10 fly_mission.py missions/mcity_patrol.json --dry-run
```

```
declared  18 volumes, 30 m across and 20 m up and down from the route, about 325 s including slack
contingency hold after 20 s outside, or 15 s with no position report

volume                       kind        lower m   upper m   from s     to s   area m2
departure to Launch          departure     245.7     328.4      -60      104     16205
Launch to NorthGate (1 of 3) leg           288.4     344.9      -28      115     10984
...
landing at Return            landing       248.4     328.4       94      325      2823
```

**Conformance is a yes or no**: inside the declared volume at the declared time. That replaces a
distance off a line with thresholds somebody chose. On a test flight the old line metric reported a
42 m worst deviation for the climb to a route 40 m up; the same flight was 100 percent inside its
declared departure volume, which is the right answer. When it is a no, it says why: across the
route, above or below it, or in the right place at the wrong time.

**A climbing leg is cut into pieces**, each spanning no more height than the vertical margin. A
volume has one altitude band, so a 50 m climb declared as one volume gets a band 90 m deep and an
aircraft 40 m too high halfway along would be called conforming. That test passed before the split
existed.

**Everything is built in metres**, in the landscape's projected frame, and compared as true shapes.
Flight Blender buffers geometry by 0.0005 degrees, which is 55 m one way and 41 m the other at this
latitude, and its default deconfliction compares bounding boxes, which for a diagonal route is
mostly empty sky. Neither is copied.

### The operation's lifecycle

| State | Means | Becomes |
| --- | --- | --- |
| NotSubmitted | Not yet checked | Accepted, or Rejected |
| Accepted | Passed the strategic check | Activated on leaving the start |
| Activated | Flying, inside its volumes | Nonconforming on leaving them, Ended on landing |
| Nonconforming | Outside its volumes | Activated after 3 s back inside, Contingent after the timeout |
| Contingent | The contingency is being executed | Ended |
| Rejected, Cancelled, Ended | Finished | Nothing |

Leaving the volumes for longer than the timeout (20 s), or no position report for 15 s (Flight
Blender's C9a check), makes the operation **Contingent**, and the runner then does what the mission
says: `hold` (hover 30 s, then land, the default), `land`, `home` (return to the launch point, then
land) or `continue` (record it and carry on). The route runs as one task with a monitor beside it,
so a contingency can interrupt a move part way rather than waiting for it to finish. A return to the
volumes counts only after 3 s inside, so an aircraft skimming a boundary does not flicker between
states.

**A long leg is flown as several moves.** The Project AirSim client gives up on any single
command after five minutes, whatever the command's own timeout says, and a mission whose first leg
was 8.5 km died with "Timed out" 2.2 km short of it. Each move is now planned to take at most two
minutes. Timing uses the speed the airframe actually reaches, about 21 m/s, rather than whatever a
waypoint asks for: one asked for 200 m/s, and the planner and dry run now say so.

Every transition is printed for the planner (which shows the state in colour and highlights the
volume the aircraft should be in), written to `operation.jsonl` in the flight folder, and
summarised in the manifest. The volumes themselves go into `intent.json`, including in F3548's
`Volume4D` exchange shape with real WGS84 heights.

Per mission, in the mission file's `intent`:

```json
"intent": { "lateral_m": 30, "vertical_m": 20, "contingency": "hold",
            "nonconforming_timeout_s": 20, "telemetry_stale_s": 15,
            "planned_start": "2026-10-05T14:00:00Z" }
```

or per flight with `--lateral`, `--vertical`, `--contingency` and `--nonconforming-timeout`.

### The strategic check

Before an operation is accepted its volumes are compared with **geofences** and with **other
scheduled operations**. A volume overlapping a no-fly or restricted fence in plan view, in height
and in time rejects it; an advisory fence is reported and does not. The planner says so in red as
the route is drawn, and the runner refuses a rejected operation unless given `--force`.

```
py -3.10 geofences.py                              list the fences loaded
py -3.10 geofences.py --check missions/x.json      accepted, or why not
py -3.10 geofences.py --import zones.json          convert an ED-269 file
```

Fences are GeoJSON in `Tools/geofences`, or wherever `MAIRCORRIDOR_GEOFENCES` points, with a
`severity` of `no-fly`, `restricted` or `advisory`, an altitude band in `agl`, `msl` or `w84`, and
optionally a time window. ED-269, the EUROCAE format for UAS geographical zones, converts with
`--import`: polygons and circles, metres and feet, all three references. An AGL band is placed over
the actual overlap, from the lowest ground under it to the highest above it, so uneven ground errs
towards finding a conflict.

**The fence shipped in `Tools/geofences` is ILLUSTRATIVE, not airspace data**: a 1.5 km circle at
Ann Arbor Municipal, labelled as such in its name and its note. Real United States drone airspace
comes from the FAA's UAS Facility Maps and LAANC.

**Only missions with a `planned_start` are deconflicted against each other.** An F3548 operation is
a declared intent with times; a mission file with no start is a plan, not a booking. Without that
rule the two missions here that fly the same route as alternatives would reject each other for ever.

### The geoid

The landscape is in NAVD88 orthometric heights. GPS, ADS-B and F3548 use heights above the WGS84
ellipsoid. They differ by the geoid separation, about **-34 m** here: the geoid is below the
ellipsoid, so the landscape's numbers are the larger ones.

```
py -3.10 geoid.py --fetch                 once: NOAA's GEOID18, 16 MB, outside the repository
py -3.10 geoid.py --at -83.699 42.2995    GEOID18 at -83.69900, 42.29950: N = -33.939 m
```

It is used wherever a height crosses datums: each ADS-B aircraft at its own position, a GPS log
with `realflight.py --geoid`, WGS84 geofences, and the F3548 export.

**The silent zero is the trap.** Asked for the same transformation without the grid installed,
rasterio's bundled PROJ returned the height unchanged and reported success. So `geoid.py` never
returns a separation it did not read from a grid: outside the grid, on a missing value, or with no
grid at all it raises, and an exact zero is refused as what a missing grid looks like.

One approximation, stated: GEOID18 relates NAD83(2011) ellipsoidal heights to NAVD88, and GPS
reports WGS84, which differs from NAD83 by about a metre here. That is not corrected; it is an order
of magnitude below the vertical error of an ADS-B report.

### Testing it without a simulator

```
py -3.10 tests/test_control_loop.py    clean flight, blown off course, and gone silent
py -3.10 tests/test_deconfliction.py   twelve cases of fences and scheduled operations
py -3.10 tests/test_geoid.py           the separation, its sign, and refusing to guess
py -3.10 tests/test_feed_health.py     a failing feed keeps its picture and says so
```

`tests/fake_airsim.py` stands in for the Project AirSim client: a drone that moves where it is told,
reports its pose twenty times a second, and can be blown off course or made to go silent. The
control loop test flies all three against it and checks the lifecycle each one produced.

**What has not been seen:** a contingency against the real controller. A new command is documented
to preempt the move in flight, and that is what the runner relies on, but it has only been watched
happening against the stand-in.

## Live air traffic

A flight planned over M-City shares the sky with real aircraft. Detroit Metro is twenty miles east,
Ann Arbor Municipal three miles south, and there is usually something in the box. `adsb.py` fetches
what is actually up there from the [OpenSky Network](https://opensky-network.org/), puts it in this
landscape's own frame, draws it on the planner's map and flies it in the level.

```
py -3.10 adsb.py --once                             what is overhead right now
py -3.10 adsb.py --watch --snapshot D:/temp/traffic.json      keep a file up to date for Unreal
py -3.10 adsb.py --watch --record traffic.jsonl     keep the history
py -3.10 adsb.py --replay traffic.jsonl             play it back, no network, no credits
```

```
callsign  icao24          lon        lat     alt m     agl m      kt    trk   age
DAL293    abbb2c     -83.3291    42.2263       255        63     129    209    44
CXK206    a25e55     -83.7712    42.2285       560       293     103     60    13
AAL1683   aa0701     -83.2156    42.3571       918       731     163    270    13
```

**Credentials.** OpenSky now uses OAuth2: a `clientId` and `clientSecret` in a JSON file, which
`adsb.py` looks for at `<project>/api/credentials.json`, or wherever `OPENSKY_CREDENTIALS` or
`--credentials` points. Keep that file out of any repository. Without it everything still works
anonymously, with fewer credits and a coarser update. [`OPENSKY.md`](../OPENSKY.md) walks through
the whole of it: the account, the API client, several clients, and feeding OpenSky from a receiver
of your own for 8,000 credits a day.

### Credential rotation

The file takes more than one client, and `adsb.py` moves between them:

```json
{
  "clients": [
    { "label": "collection", "clientId": "...", "clientSecret": "...", "added": "2026-10-04" },
    { "label": "spare",      "clientId": "...", "clientSecret": "env:OPENSKY_SPARE_SECRET" }
  ]
}
```

A secret can be given as the string itself, as `env:NAME` to read an environment variable, or as
`file:/path/to/secret` to read a file, so a rotation can change a secret without the JSON ever
holding one. A single `{"clientId": ..., "clientSecret": ...}` object still works exactly as before,
and so does the older `{"username": ..., "password": ...}`.

```
py -3.10 adsb.py --check-credentials          try every one, print none of them
py -3.10 adsb.py --check-credentials --probe  and spend a credit each to read the credits left
py -3.10 adsb.py --watch --rotation newest-first
py -3.10 adsb.py --watch --credential spare   use only that one
```

```
label                account      kind     secret   credits   note
retiring             7d00356ca3   oauth2   REFUSED  ?         HTTP 401 from the token endpoint
current              7d00356ca3   oauth2   ok       ?
```

**Three policies**, because two different jobs want rotation and they want different things:

| `--rotation` | What it does | What it is for |
| --- | --- | --- |
| `exhaustion` | Stays on one credential until its credits run low or the network refuses it, then moves on | Spreading a day's requests across more than one account |
| `round-robin` | Takes turns, one request each | Spending two accounts evenly rather than one at a time |
| `newest-first` | Prefers the entry with the latest `added` date, keeping the others as fallbacks | A secret being replaced: the new one serves, the old one covers a mistake |

**Failing over is automatic.** A credential that returns 429 is rested, for as long as the network
asks or fifteen minutes if it does not say, and the request is retried once on the next credential.
A credential whose secret is refused is rested for five minutes and handed over the same way. One
retry per request, never a loop. Credits and cooldowns are remembered between runs in the system
temporary folder, keyed by a hash of the client id, holding no secret and nothing that matters if
it is lost.

#### Replacing a secret without a gap

Nothing here can mint a secret: OpenSky's clients are created in their web interface, so the new
one has to come from there. What this does is let the changeover happen without stopping anything.

1. Create the new client in your OpenSky account.
2. Add it to the file beside the old one, with today's date as `added`.
3. `py -3.10 adsb.py --check-credentials`. The new entry must say `ok`. **This asks the token
   endpoint every time rather than trusting a cached token**, which matters: an early version
   accepted a cached token and so reported a credential with a dead secret as working.
4. Run with `--rotation newest-first` and watch the new one serve traffic.
5. Delete the old entry from the file, and delete the old client in OpenSky.

**Two entries with the same `clientId` share one budget of credits**, and `--check-credentials`
says so when it sees them. Rotating between those replaces a secret; it does not buy more requests.
For more requests the second client has to belong to a different OpenSky account.

**No secret is ever printed, logged or written** by any of this. Output names a credential by its
label and by an account fingerprint, which is a hash of the client id: enough to tell two apart in
a log, useless to anyone reading one. The token cache in the temporary folder holds bearer tokens,
which is what it is for, and they expire in half an hour.

**Credits are the real constraint.** An authenticated account gets 4000 a day and a bounded request
costs one, which is a request every 21.6 seconds sustained. So the default interval is twenty
seconds, every response's remaining credits are read back and reported, and asking faster than five
seconds is refused outright. The gap between reports is filled by **dead reckoning** rather than by
asking again: a state vector carries a ground speed, a track and a vertical rate, which is enough to
move an aircraft believably for twenty seconds. Nothing is carried forward for ever: an aircraft
whose last report is older than `--forget` is dropped rather than flown on faith.

### Altitude, and the sign of the thirty four metres

OpenSky reports barometric and geometric altitude in metres, and the geometric one is height above
the **WGS84 ellipsoid**. This landscape's elevations come from USGS 3DEP, which measures from the
**NAVD88 geoid**. Around Ann Arbor the geoid sits about 34 m BELOW the ellipsoid (GEOID18 gives 33.94 m at
M-City), so an NAVD88 elevation is the **larger** number.

Each geometric altitude is converted with the geoid model at that aircraft's own position, and
every aircraft says how its height was placed. Only when the model is not installed does a
constant +34 m stand in, and the feed says so. Barometric altitude is pressure altitude rather than
an ellipsoidal height, so it is never geoid corrected; it is used only when there is no geometric
one, and labelled. See [The geoid](#the-geoid).

### When the feed fails

**A failed request is not an empty sky.** The feed used to treat them the same, which meant a feed
that had stopped working looked exactly like a quiet afternoon: the planner said nothing was too
close and the level cleared the sky. Now a failure keeps the last good picture, which goes on ageing
and being dead reckoned until it is forgotten, and the feed reports its own health in every
snapshot: `starting`, `healthy`, `degraded` (failures in a row, and why), `stale` (no good report
for 90 s) or `down`. The planner leads with it when it is not healthy and says outright that nothing
shown as too close does not mean nothing is there; the level's traffic actor puts it at the front
of its status. This follows the heartbeat and health reporting ASTM F3623 asks of a surveillance
provider, cut down to one feed.

### In the planner

**Show aircraft from the ADS-B feed** in the planner turns the feed on. Aircraft are drawn as
chevrons pointing along their track, labelled with callsign and height above the ground, and the
panel reads out what is up there and what is in the way:

```
38 aircraft, 7 over the landscape, 3996 credits left.  1 too close: N9176H is 740 m from the
route and +48 m on TrackCentre.
```

**Too close is two numbers, horizontal and vertical**, because that is how airspace works:
something directly overhead at ten thousand feet is not a conflict, and something at your height a
kilometre away is worth knowing about. The horizontal distance is measured to the nearest point on
the route, the same way the planner measures its own deviation. The defaults are 1000 m across and
300 m vertically.

It is off until asked for, because turning it on spends credits.

### In the level

The plugin's **M-Air Live Traffic** actor (`AMAirTrafficActor`) flies those aircraft in the level.
Drop one in, point `Snapshot File` at the file the feed writes, and they appear, moving, at the
right height, pointing where they are going. It ticks in the editor viewport as well as in Play,
because planning around traffic means seeing the traffic while planning.

The planner writes that snapshot itself while it is showing traffic, and the launcher's **Live air
traffic** entry starts a feed for when the planner is not open. Either way it is one feed: asking
the network twice for the same aircraft would spend twice the credits for the same answer.

**Why a file rather than a socket.** The fetching needs an OAuth2 token, a credit budget, a
projection and a datum decision, all of which already exist, tested, in Python. A level that reads
one JSON file has nothing to get wrong, behaves the same in the editor as in a packaged build, and
can be driven from a recording when there is no network.

**The frame is worked out in Python, not in C++.** The snapshot carries `unreal_cm`,
`unreal_velocity_cm_s` and `unreal_yaw_deg` ready to use, so the plugin moves a marker along a
vector and points it at a yaw. It never has to know that Unreal +X is this landscape's grid east,
that +Y is grid south, or that a true bearing differs from a grid one by 1.8 degrees of meridian
convergence at M-City. All of that is in one place, in a language that can be checked without an
editor open.

### Assigning your own models

A state vector never says "Boeing 737". It says `large`, if it says anything at all: in a sample of
43 aircraft over Ann Arbor, three broadcast an emitter category. So when the category says nothing,
the **callsign** is asked instead, and every aircraft carries `class_source` saying which answered:

| Signal | Rule | Class |
| --- | --- | --- |
| `category` | The ADS-B emitter category, when broadcast | `light`, `small`, `large`, `heavy`, `rotorcraft`, `glider`, `balloon`, `uav`, `vehicle`, `obstacle` and so on |
| `callsign` | Three letters then a flight number, as in `DAL293` or `NKS123` | `large` |
| `callsign` | `N` then a digit, as in `N479DV`, or `C-F`/`C-G` with no digits | `light` |
| `default` | Nothing to go on | `unknown` |

`N479DV` is a registration and `NKS123` is Spirit Airlines, and both begin with N and hold three
letters, so what separates them is where the digits start. That is a guess, it is wrong for a
business jet on an airline callsign, and `class_source` says so.

The actor's **Models By Class** map takes a mesh for each of those class names. By default it holds
the aircraft built below, one per class (a Cessna 172 for `light`, a King Air for `small`, a 737 for
`large`, a 777 for `heavy`, a T-38 for `fast`, a Bell 407 for `rotorcraft`, a glider, a balloon, an
ultralight, a fixed-wing UAV and an airport truck for `vehicle`); assign your own over any of them.
Anything with no model falls back to a plain shape: a sphere in the air, a
cylinder on the ground, both scaled to the real wingspan of the class (36 m for an airliner, 11 m
for a light aircraft) because **a marker of the wrong size reads worse than a marker of the wrong
shape**. `Scale To Span` does that scaling for any model, whatever size it was authored at, so your
own aircraft come out right without resizing them.

Nothing the actor makes is ever saved into the level: the components are transient, so an actor
saved with forty aircraft attached does not bake this afternoon's traffic into the map.

### Building the aircraft

```
blender --factory-startup -b -P blender/aircraft_builder.py                 every aircraft
blender --factory-startup -b -P blender/aircraft_builder.py -- --only large_b737
py -3.10 aircraft_sheet.py --view side                                      look them over
```

The models for those classes, and the drones, are built in Blender from their real dimensions by
[`blender/aircraft_builder.py`](blender/aircraft_builder.py), a generic builder: it knows nothing
about any particular aircraft. An aircraft is a list of parts in
[`aircraft/fleet.json`](aircraft/fleet.json): fuselages, lifting surfaces of any number and
arrangement (wings, tailplanes, fins, canards, V-tails, winglets, flying wings), engine nacelles,
propellers and rotors facing any way, tubes, gear, wheels, canopies, lathed shapes, boxes, and
radial patterns of any of them. A part can be mirrored, and can be attached to another part by
name (an engine at 34 % of the wing's span, a strut from a station on the fuselage to a point on
the wing), so it follows when that part changes. The builder's docstring lists every part and
field. To add an aircraft, add an entry and build it.

Each comes out as one mesh in metres, nose along +X, with a material per kind of surface (paint,
accent, glass, dark, metal, tyre, fabric), so segmentation and liveries can tell them apart, as
`<name>.glb`, `.fbx` and `.blend` with four review renders, in `work/aircraft/<name>/`. The build
measures each model and checks its span and length against the real aircraft's.

Into Unreal with [`unreal/import_aircraft.py`](unreal/import_aircraft.py), run in the editor (its
docstring has the off-screen command line; the FBX importer will not run as a commandlet). It puts
each in `/MAirCorridor/Aircraft/<name>/` and checks it came in at the built size with its nose
along +X, the way the traffic actor faces a model.

Built, not generated: single-picture 3D reconstruction was tried first and folded and tore the
wings, which on an aircraft is most of it.

### Flying a built drone

```
blender --factory-startup -b -P blender/aircraft_builder.py -- --only drone_quad_industrial
py -3.10 drone_configs.py                                                    its robot config
UnrealEditor.exe ... -ExecutePythonScript=".../unreal/import_aircraft.py"   its meshes
py -3.10 fly_mission.py missions/<mission>.json --robot drone_quad_industrial
```

Project AirSim draws a drone as a frame mesh plus one mesh per rotor, and turns each rotor mesh as
its rotor spins. A drone whose propellers are marked `"spin": true` in `fleet.json` is built three
ways: the whole model as before (for traffic and pictures), `<name>_body` without its propellers,
and `<name>_rotor`, one propeller lying flat about its own centre. Where each propeller sat goes
into `model.json` as `rotors`.

[`drone_configs.py`](drone_configs.py) turns that into `AirSim/sim_config/robot_<name>.jsonc` for
each drone with a `"flight"` entry. It starts from Project AirSim's own config for the airframe
(`robot_quadrotor_fastphysics.jsonc`, `robot_hexarotor_fastphysics.jsonc`) and keeps its controller,
actuator order and turning directions, moving each rotor to the built rotor at the nearest angle so
every corner keeps the direction the controller expects. It sets the frame's mass and inertia
(`mass_kg`, `inertia_box_m`), each rotor's real diameter, and a top speed for the rotors that lifts
`thrust_to_weight` times the weight. The drone carries the same sensors as `robot_mcity_sensors.jsonc`;
`sensor_origins` moves any of them (metres, x forward, y right, z down), as a camera inside a bigger
body sees only the inside of it. The body gets a collision box when it is imported. Without one,
Project AirSim never sees the drone touch anything, and a landing drone sinks through the ground.

Both lift 1.4 times their weight, as Project AirSim's own quadrotor does. Its controller is tuned
for that. At 2.2 the quad climbed at 10 m/s and overshot WP1 by 11 m.

| drone | airframe | mass | rotors | max rpm |
|---|---|---|---|---|
| `drone_quad_industrial` | quadrotor x | 6.3 kg | 4 of 0.53 m | 2754 |
| `drone_hexa_heavy_lift` | hexarotor x | 9.5 kg | 6 of 0.53 m | 2761 |

Flown off screen on a short test (climb 30 m from the start, 200 m at 12 m/s, land), against the
stock drone:

| | climb overshoot at WP1 | off the line in cruise | landed |
|---|---|---|---|
| stock (`robot_quadrotor_fastphysics_weather`) | 7.3 m | 0.6 to 0.8 m | yes |
| `drone_quad_industrial` | 3.1 m | 0.6 m | yes |
| `drone_hexa_heavy_lift` | 3.7 m | 0.5 to 0.65 m | yes |

A flight flies as one with `--robot`, by the drone's name or the config's file name; a mission can
name one as its `robot_config`; the planner's **Drone** list offers every built drone. Without any
of these the drone is whatever the scene names. The two VTOL drones have no Project AirSim airframe
to fly on. Its controller flies quadrotors, hexarotors and one VTOL, a quad tilt-rotor whose four
rotors tilt forward to cruise. `drone_vtol_quadplane` lifts on four fixed rotors and cruises on a
separate pusher, and `drone_vtol_tailsitter` tips the whole aircraft over; neither is that.

## Sim to real, and real to sim

A recorded flight is meant to be useful in both directions, which is why the manifest carries the
geometry and not just the file list.

**Going out**, a simulated flight is material for something that will fly for real: lossless pixels
on request, sixteen bit depth, the labels the camera publishes, the camera's size, field of view
and mounting from the robot config, and the sim clock on every stream so they can be joined.

**Coming back**, a flight flown for real can be turned into a mission and flown here over the same
ground, then the two tracks can be measured against each other:

```
py -3.10 realflight.py mission real_log.csv -o missions/from_real.json
py -3.10 realflight.py mission missions/flights/20261004-095445
py -3.10 realflight.py compare real_log.csv missions/flights/20261004-095445 --csv deviation.csv
```

The launcher has both as **Import a real flight** and **Compare two flights**.

`mission` reads a flight folder recorded here, a CSV with longitude, latitude and altitude columns
under almost any spelling, JSON lines with the same fields, or a GPX track. A vendor's binary log
has to be exported to one of those first, which ArduPilot, PX4 and DJI tools all do. It thins the
track with Douglas-Peucker so a 10 Hz log becomes the handful of waypoints that actually describe
it (`--tolerance`, `--max-waypoints`), takes each leg's speed from the log's own timestamps, and
with `--agl` stores heights above the ground so the route survives a landscape rebuild.

`compare` measures the second flight against the first the same way the planner measures deviation
while flying: to the nearest point on the nearest leg, never to the nearest waypoint. It reports
the distance in three dimensions and across the ground separately, because a height datum that is
out by a constant shows up in one and not the other:

```
how far the second flight was from the first
  in 3D        mean 53.70 m, median 53.70 m, 95th 53.70 m, worst 53.78 m, over 3 samples
  horizontal   mean 0.06 m, median 0.07 m, 95th 0.07 m, worst 0.10 m, over 3 samples
```

### Altitude is the trap

This project's ground elevations come from USGS 3DEP, which measures from the **NAVD88 geoid**. A
GPS receiver usually reports height above the **WGS84 ellipsoid**, and around Ann Arbor the geoid
sits about 34 m **below** the ellipsoid. So an NAVD88 elevation is roughly 34 m **larger** than the
ellipsoidal height of the same point, and a log of ellipsoidal heights needs about **+34** to match
this landscape. Thirty four metres is the difference between flying over the trees and flying
through them.

`--geoid` converts every height in a GPS log with NOAA's GEOID18 model at that sample's own
position (see [The geoid](#the-geoid)), which is the right answer for a GPS or drone log. The
import reports what the heights come out as above the landscape either way. A log flown at 60 m:

```
raw         clearance 26.1 m above the ground as a median, 26.0 m to 26.1 m over 320 positions
--geoid     clearance 60.0 m above the ground as a median, 59.9 m to 60.0 m over 320 positions
```

**The error hides, which is what makes it dangerous.** Ellipsoidal heights read about 34 m LOW
here, and 26 m is a perfectly plausible height for a drone, so nothing about the raw numbers looks
wrong. The import's plausibility check cannot catch it; only knowing the log is GPS heights can.
`--altitude-offset` still exists for a log in some other datum, and is added to every height.

Missions are JSON in `Tools/missions`, holding longitude and latitude rather than Unreal
coordinates, so they survive the landscape being rebuilt at a different size or origin. Anything the
window can fly can also be flown from a terminal:

```
py -3.10 fly_mission.py missions/patrol.json --dry-run     check it without connecting
py -3.10 fly_mission.py missions/patrol.json               fly it
```

`--dry-run` resolves every waypoint against the terrain and prints the NED coordinates, ground
height and speeds without touching the simulator, which is the quickest way to see that a route is
sane.

## On a new machine

Everything here runs on a machine other than the one it was written on, but a few things are
machine specific and have to be pointed at.

**The source data first.** The landscape plan, imagery, building tiles, vegetation libraries and
survey are in [MAirCorridor_Assets](https://github.com/sriceumich/MAirCorridor_Assets), in Git LFS,
and [ASSEMBLY.md](../ASSEMBLY.md) builds the level from them. Cloned to `MAirCorridor_Assets` beside the project folder (`<workspace>/MAirCorridor_Assets`, with the project at `<workspace>/<project>`),
every default below already points at it:

```
git lfs install
git clone git@github.com:sriceumich/MAirCorridor_Assets.git <workspace>/MAirCorridor_Assets
```

| What | Where it is looked for | To change it |
| --- | --- | --- |
| Python packages | `requirements.txt` here and in the plugin root | `first_install.cmd` in the plugin root installs both |
| The landscape plan | `<workspace>/MAirCorridor_Assets/ue_rect_3m/mcity_rect_3m.json` | Set `MAIRCORRIDOR_PLAN`. A mission's stored plan path that does not exist falls back to it, with a note |
| The imagery index, for the editor's imagery tool | `<workspace>/MAirCorridor_Assets/naip_rect_066m/mcity_066m_naip.json` | Set `MAIRCORRIDOR_IMAGERY`, or pick it when asked |
| The foliage survey and libraries, for the editor's foliage placer | `<workspace>/MAirCorridor_Assets/corridor_scene.json`, `corridor_trees`, `corridor_rocks` | Set `MAIRCORRIDOR_SCENE`, `MAIRCORRIDOR_TREES`, `MAIRCORRIDOR_ROCKS`, or pick them when asked |
| Project AirSim | `<workspace>/ProjectAirSim` | Set `PROJECTAIRSIM_ROOT`, or pass `--clone` |
| OpenSky credentials | `<project>/api/credentials.json` | Set `OPENSKY_CREDENTIALS`, or pass `--credentials`. Keep it out of any repository |

And one that is fetched once:

- The geoid model: `py -3.10 geoid.py --fetch`. Without it the traffic feed falls back to a
  constant and says so, and WGS84 geofences are reported as unchecked.

Then run the tests above: they need the landscape plan and nothing else.

## A release

```
py -3.10 package_release.py                 a Development build, the default
py -3.10 package_release.py --shipping      smaller and faster, but no console and no log
py -3.10 package_release.py --dry-run       print the packager's command and stop
```

Or **Build a release** in the launcher, which runs the same thing in its own window. It bakes the
project into a build that runs without the editor or the source: the M-City corridor level, the
drone and the scan, cooked for Windows. It lands in `Releases/<project>-<config>` beside the
project folder, with `Play MCity Air Command.bat` and a `README.txt` beside the executable. The
first build compiles every shader for the game and takes an hour or more; later ones reuse what
they can. The packager's whole account goes to `Releases/<project>-<config>.log`.

The simulator in a release is the same one the editor runs, so everything here flies it the same
way: the planner, `fly_mission.py`, the keyboard. Start it with **Release** in the launcher, or

```
run release                                  the newest release, on the corridor level
run mission mcity_patrol                     then fly it, exactly as against the editor
run package                                  build one (the same as package_release.py)
```

A release keeps its own `Saved` folder: `Releases/<project>-Development/Windows/<project>/Saved`,
or `%LOCALAPPDATA%/<project>/Saved` for a Shipping build. The lidar (MAirLidar) and the M-City
view switch are asked through files in it, so while a release is running `fly_mission.py` writes
there instead of the project's, and says so (`a packaged release is running; its Saved folder
is ...`). The lidar's scans land under that `Saved/OusterSim`. `MAIR_PROJECT_SAVED` overrides it.

Content that code loads by name is cooked whole, because the cooker only follows references:
Project AirSim's and the Drone plugin's content, the McityMap twin, and this plugin's Materials,
Aircraft and Scan. They are the project's **Directories to Always Cook**, in its
`Config/DefaultGame.ini` (`+DirectoriesToAlwaysCook=(Path="/McityMap")` and so on), so packaging
from the editor's menu cooks them too. `package_release.py` checks that every one is listed before
it starts, and names any that is not with the line to add. An entry has to be quoted as shown:
unquoted, Unreal rejects it with a warning and leaves that content out of the release.

That packages the simulator; the tools are built separately, below.

### The tools as executables

```
py -3.10 -m pip install pyinstaller          once
py -3.10 build_tools.py                      builds dist/MAirCorridor
py -3.10 build_tools.py --no-landscape       without the 300 MB heightmap
```

Every tool here becomes a Windows executable that needs no Python: `launcher.exe`,
`flightplan_ui.exe`, `fly_mission.exe` and the rest, one per tool tracked in git, plus
`fly_mcity.exe` for the keyboard. They share one copy of Python and the libraries in `_internal`.
`dist/MAirCorridor` is laid out like the plugin, so the tools find their files where they always
do:

```
dist/MAirCorridor/
    Tools/              the executables, level.json, segmentation.json, missions, geofences
        _internal/      Python and the libraries, once for all of them
        landscape/      the landscape plan and heightmap the flights are measured against
        projectairsim/  Project AirSim's sample configs, which our scenes name robots from
    AirSim/sim_config/  our scene and robot configs
```

Copy the folder anywhere and start `Tools/launcher.exe`. The Project AirSim client is built in
from the clone, so the machine needs neither Python nor the clone, but the simulator still has to
be running (the editor in Play, or a release from above). A mission names the landscape plan it
was drawn against by its path on the machine that drew it; where that path does not exist, the
release uses the landscape it carries. The OpenSky credentials are never copied: `adsb.exe` looks
for `api/credentials.json` above the plugin, as the script does, or takes `OPENSKY_CREDENTIALS`.

Built, one tool starts another as its executable rather than as a script (`toolpaths.py`), and
the folder the tools read and write is the executables' folder, so missions and flights saved by
a release stay in the release. After building, every console tool is started with `--help`, so a
library the build left out fails there, by name, rather than on whoever runs it.

**The terrain and imagery tools on their own.** The same build also makes `dist2/Anchor`: the
Terrain and imagery window (`geodata_ui.exe`), the three downloaders and `build_landscape.exe`,
with only the libraries they need and the example boundary. They have nothing to do with the
corridor or the simulator, so they travel without either. Its `README.md` is
[`terrain_imagery_guide.md`](terrain_imagery_guide.md): the whole of using them from that folder,
the window, every option, and importing the result into Unreal with or without this plugin. Its window is titled by the tool's own
name, from a `release.json` beside the executable; in `dist/MAirCorridor` it keeps the suite's.
`Tools/build`, `Tools/dist` and `Tools/dist2` are not tracked.

**What a release needs that the editor does not.** The editor loads anything on demand. A release
has only what was cooked into it, and the cooker follows references, nothing else:

| What | Why it is not found by itself | How it gets in |
| --- | --- | --- |
| The corridor level | A level is opened, not referenced | Cooked by name, and named by the batch file |
| Drone meshes, `/Drone/Quadrotor1` and the rest | Robot configs name them in text | The Drone plugin's content is cooked whole |
| Project AirSim's camera and weather materials | Loaded by path in its code | Its content is cooked whole |
| The scan's default material, `M_MCityScan` | Loaded by path when no material is set | This plugin's `Content/Materials` is cooked whole |
| The scan's tiles and photographs | Not assets at all | Staged as runtime dependencies by `MAirCorridorScan.Build.cs` |

All of it is passed on the packager's command line. Nothing in the project's settings changes, so
packaging from the editor's own menu is untouched, and would leave these out.

**The batch file opens the level by name.** `TheUniverse.exe` on its own opens the project's
default map. That is the same level, provided the setting names it where it is now: a path that
reaches it through a redirector, which a moved level leaves behind, fails to load in a release.
The cooker says so (`GameDefaultMap contains a redirected reference`), and `package_release.py`
checks the setting before it starts. The batch file names the corridor level either way, and
passes anything after it on, so `-ResX=2560 -ResY=1440` or `-fullscreen` override the window.

## Contents

1. [Install](#1-install)
2. [Define your area](#2-define-your-area)
3. [Get elevation data](#3-get-elevation-data)
4. [Using any elevation data](#4-using-any-elevation-data)
5. [Build the landscape](#5-build-the-landscape)
6. [Import into Unreal](#6-import-into-unreal)
7. [Get aerial imagery](#7-get-aerial-imagery)
8. [Put the imagery on the Landscape](#8-put-the-imagery-on-the-landscape)
9. [Buildings from OpenStreetMap with blosm](#9-buildings-from-openstreetmap-with-blosm)
10. [Vegetation inputs](#10-vegetation-inputs)
11. [Reproducing the M-Air corridor](#11-reproducing-the-m-air-corridor)
12. [Data licences and attribution](#12-data-licences-and-attribution)
13. [Troubleshooting](#13-troubleshooting)

---

## 1. Install

You need **Python 3.9 or newer** (3.10 is what these tools were tested with) and five packages:

```
py -3.10 -m pip install -r requirements.txt
```

`rasterio` ships its own copy of GDAL on Windows, macOS and Linux, so nothing else needs to be
installed. On macOS or Linux, use `python3` wherever these instructions say `py -3.10`.

No accounts, API keys or logins are needed for any of the four tools.

## 2. Define your area

Every tool takes the area of interest in one of two forms.

**A box**, as west, south, east and north in decimal degrees (WGS84):

```
--bbox -83.705 42.296 -83.690 42.308
```

**A polygon** in a KML or KMZ file:

```
--aoi examples/mair_corridor_boundary.kml
```

A polygon does three things a box cannot: downloads skip tiles that only touch the box's corners,
terrain outside the polygon is blanked, and landscape segments that fall entirely outside it are
not built at all. For a long, thin corridor that is most of the area.

To draw one:

- **Google Earth Pro** (free desktop app): *Add > Polygon*, draw the outline, then right-click it in
  *Places* and choose *Save Place As...* and save as KMZ or KML.
- **QGIS**: draw a polygon layer, then *Export > Save Features As...* with format *Keyhole Markup
  Language [KML]*.
- **Any GIS** that writes KML works; KML coordinates are always WGS84 longitude, latitude.

`--buffer-m 500` grows the area by 500 m on every side, which is useful when the area is a route and
you want a margin around it.

## 3. Get elevation data

### United States: USGS 3DEP

The USGS 3D Elevation Program publishes free, public-domain, **bare-earth** elevation for the whole
country. Bare earth (buildings and trees removed) is what you want under a Landscape that will have
buildings and trees placed on it.

```
py -3.10 download_3dep.py --aoi site.kml --product 1m --out dem_cache --dry-run
py -3.10 download_3dep.py --aoi site.kml --product 1m --out dem_cache
py -3.10 download_3dep.py --aoi site.kml --product 13 --out dem_cache
```

| `--product` | Resolution | Coverage | File size | Use it for |
| --- | --- | --- | --- | --- |
| `1m` | 1 m lidar | Most of the US, project by project, with gaps | 100-450 MB per 10 km tile | The detailed near terrain |
| `opr` | Native lidar, often 0.5-2 m | As delivered by each lidar project | Varies | When `1m` has no tile but a project exists |
| `19` | 1/9 arc-second, about 3 m | Partial; retired but still served | 20-130 MB per quarter-degree tile | Filling `1m` gaps |
| `13` | 1/3 arc-second, about 10 m | **Seamless**, all of the US | 100-450 MB per 1 degree tile | The fallback that guarantees no holes |
| `1` | 1 arc-second, about 30 m | Seamless | about 50 MB per 1 degree tile | Wide surroundings, previews |

Always run with `--dry-run` first: it lists every file and the total size without downloading.

**Download two products and let the builder combine them.** For example, `1m` for detail and `13`
so that any gap in the lidar is filled rather than left as a hole. See
[Build the landscape](#5-build-the-landscape).

Downloads resume if interrupted, skip files that are already present, retry when the USGS servers
are busy, and write a `download_3dep_<product>.json` listing what was fetched.

You can also browse coverage visually at The National Map Downloader,
https://apps.nationalmap.gov/downloader/, and download there by hand; the builder does not care
where a file came from.

### Anywhere on Earth: Copernicus DEM

```
py -3.10 download_copernicus_dem.py --aoi site.kml --out dem_cache
py -3.10 download_copernicus_dem.py --bbox 7.40 46.90 7.50 46.98 --resolution 90 --out dem_cache
```

Copernicus GLO-30 is the most accurate free global elevation model, published as open data on AWS.
Two things to know:

- **It is a surface model (DSM)**, not bare earth: it includes buildings and tree canopy. In a city
  or a forest the ground will be lumpy where buildings and trees stand. Prefer a national bare-earth
  model where one exists (see the next section).
- **It requires attribution** in anything you publish. The exact wording is in the script's header and
  in [section 12](#12-data-licences-and-attribution).

Ocean-only 1 degree cells have no tile; the tool reports them and carries on.

## 4. Using any elevation data

`build_landscape.py` is not tied to the downloaders. It reads **any raster GDAL can open** (GeoTIFF,
Erdas IMG, BIL/HDR, ASCII grid, HGT, VRT and many more), in **any projection**, and reprojects it
itself. That includes ASTER GDEM, which is where "GDEM" comes from, and every other global or
national model:

| Dataset | Resolution | Surface or bare earth | Where to get it | Terms |
| --- | --- | --- | --- | --- |
| ASTER GDEM v3 | 30 m | Surface | NASA Earthdata Search, product ASTGTM v003 (free Earthdata login) | Free, cite NASA/METI |
| SRTM GL1 / NASADEM | 30 m | Surface (radar) | NASA Earthdata Search, or OpenTopography | Public domain |
| ALOS World 3D (AW3D30) | 30 m | Surface | JAXA Earth Observation Research Center (free registration) | Free with attribution |
| Copernicus GLO-30 / GLO-90 | 30 m / 90 m | Surface | `download_copernicus_dem.py` | Free with attribution |
| FABDEM | 30 m | **Bare earth** (Copernicus with buildings and trees removed) | University of Bristol data repository | CC BY-NC-SA 4.0 |
| OpenTopography global and lidar datasets | Varies | Both | https://opentopography.org (free API key) | Per dataset |
| National lidar: UK (Environment Agency), Netherlands (AHN), Canada (HRDEM), and many others | 0.5-2 m | Usually both | Each national portal | Usually open licences |
| Your own survey (drone photogrammetry, lidar) | Any | Whatever you exported | Your processing software | Yours |

A raster works if it meets four conditions:

1. **It is georeferenced.** The file carries its projection. A plain image, or a raster whose
   projection is missing, is refused with a clear message.
2. **Heights are in metres.** Some US state and county lidar is delivered in US survey feet. Convert
   first; heights in feet will produce terrain 3.28 times too tall. A one-off conversion:

   ```python
   import rasterio
   with rasterio.open("feet.tif") as s:
       p = s.profile; a = s.read(1).astype("float32"); nd = s.nodata
   m = a * 0.3048006096
   if nd is not None: m[a == nd] = nd
   p.update(dtype="float32")
   with rasterio.open("metres.tif", "w", **p) as d: d.write(m, 1)
   ```

3. **Mixed sources share a vertical datum.** Heights above sea level (a geoid, such as NAVD88, EGM96 or
   EGM2008) agree with each other to within a metre or so, which is fine for mixing. Heights above
   the **ellipsoid**, which raw GNSS and many drone exports use, differ from sea-level heights by up to
   100 m depending on location (about 34 m in Michigan). Mixing the two puts a cliff at every seam, so
   convert ellipsoidal data to a geoid first, usually in the software that produced it.
4. **No-data is marked.** Either as the file's nodata value, or as an implausible number. Anything
   below -500 m or above 9000 m is treated as no data automatically.

Then list the files **finest first**. At every point the first raster that has data wins:

```
py -3.10 build_landscape.py --dem my_drone_dtm.tif "national_lidar/*.tif" "dem_cache/Copernicus_*.tif" ...
```

Here the drone survey is used where it exists, national lidar around it, and Copernicus fills
whatever is left.

## 5. Build the landscape

```
py -3.10 build_landscape.py --dem "dem_cache/USGS_one_meter_*.tif" "dem_cache/USGS_13_*.tif" \
    --aoi site.kml --metres 1 --datum NAD83 --out landscape --name site
```

It prints the layout, builds each segment, and writes:

| File | What it is |
| --- | --- |
| `<name>.json` | The **plan**. This is what you pick in Unreal |
| `<name>.r16` or `<name>_xNN_yNN.r16` | Heightmaps: raw 16-bit little-endian, row 0 north, no header |
| `<name>....provenance` | One byte per vertex: 0 for no data, otherwise which `--dem` source supplied that point |

Add `--plan-only` to see the layout and sizes without building anything.

### Why it gets past Unreal's size limits

Unreal's own Landscape import reads the entire heightmap into memory and one Landscape actor is best
kept to about 8161 by 8161 vertices. A 1 m model of a 60 by 20 km corridor is 60,000 by 20,000
vertices: 1.2 billion points and several GB even before the editor makes copies of it. That import
does not complete.

This tool never builds one giant heightmap. It divides the area into a grid of **segments**, each
at most `--max-vertices` on a side and each its own Landscape actor, and it reads and reprojects the
sources **one segment at a time**, so memory use stays at a few hundred MB whatever the size of the
area. The sources themselves are never loaded whole either; GDAL reads just the window each segment
needs. The Unreal importer then builds the segments one actor at a time as well.

The segments join exactly:

- Neighbouring segments **share their edge vertices**. The builder copies each shared edge from the
  segment built before it, so the heights on both sides of every seam are identical, not merely close.
- **Every segment uses one vertical range** and one height decode, so a shared edge sits at the same
  world height in both actors.
- Each segment's position is written into the plan, so they tile without gaps.

### Options

| Option | Default | What it controls |
| --- | --- | --- |
| `--dem` | required | Rasters, globs or folders, finest first |
| `--bbox` or `--aoi` | union of the rasters | The area |
| `--projected-bounds` | | The area as min X, min Y, max X, max Y in the `--epsg` projection's metres, used exactly (no snapping). For reproducing a known grid |
| `--metres` | 1 | Size of one Landscape quad. See the table below |
| `--epsg` | UTM zone of the area | Output projection. Must be in metres |
| `--datum` | WGS84 | Datum for the automatic UTM zone. Use NAD83 in North America to match USGS exactly |
| `--max-vertices` | 8161 | Largest segment side |
| `--section-quads`, `--sections-per-component` | 255, 2 | Unreal component layout (510 quads per component) |
| `--wp-grid` | 4 | World Partition grid size; 0 leaves each Landscape unsplit |
| `--origin` | `area` | `area` puts the north-west corner at Unreal 0,0. `projected` uses true projected coordinates, which needs Large World Coordinates for areas far from the origin |
| `--no-mask` | off | Keep the whole rectangle instead of blanking terrain outside the KML polygon |
| `--zmin`, `--zmax` | estimated | Force the vertical range, for example to share it with another build |
| `--resampling` | bilinear | `nearest` keeps original values exactly; `cubic` is smoother |

### Choosing `--metres`

The quad size sets both detail and cost. It does not need to match the source resolution: the source
is resampled to whatever you choose.

| `--metres` | Vertices per km squared | A 60 by 20 km area | Good for |
| ---: | ---: | --- | --- |
| 1 | 1,000,000 | 24 segments, 2.4 GB of heightmap | Ground-level driving, low flight |
| 2 | 250,000 | 8 segments, 600 MB | Most flight simulation |
| 3 | 111,000 | 3 segments, 270 MB | Aerial views (the M-Air corridor Landscape uses 3 m) |
| 10 | 10,000 | 1 segment, 24 MB | Regional surroundings |
| 30 | 1,100 | 1 segment, 3 MB | Large-area context |

Segment counts assume the default `--max-vertices 8161`.

Using finer quads than the data (1 m quads on 30 m data) costs memory and adds no detail.

### Heights

Unreal stores Landscape heights as 16-bit integers scaled by the actor's Z scale:
`world_cm = (H - 32768) * ZScale / 128`. The builder estimates the elevation range over the whole
padded grid, adds a small margin, picks the **smallest** Z scale that fits it (the finest possible
height steps, typically well under a centimetre), and places every actor at the middle of the range.
The exact decode is written into the plan as `height_decode`.

If it prints `CLIPPED`, some vertices fell outside the estimate. Rerun with `--zmin` and `--zmax`
covering them.

## 6. Import into Unreal

1. Enable the MAirCorridor plugin in your project and restart the editor.
2. Open or create a **World Partition** level (*File > New Level > Open World*, or *Empty Open World*).
3. *Tools > M-Air Corridor > Build Unreal Landscape from Plan...* and pick `<name>.json`.
4. Save the level.

The importer checks the plan **before** spawning anything: that each resolution is a legal Unreal
size (`quads per component x components + 1`), that each section size is one Unreal accepts, and that
each `.r16` file is exactly the size the plan says. A plan that fails is refused with the reason, so a
wrong or truncated file never produces a Landscape that looks right and is not.

Keep the `.r16` files beside the JSON; the plan refers to them by name.

The Landscape has no material yet. Assign one with the Landscape actor's *Landscape Material*
property, or build the imagery material in [section 8](#8-put-the-imagery-on-the-landscape).

## 7. Get aerial imagery

### United States: NAIP

The USDA National Agriculture Imagery Program flies the lower 48 states every two to three years at
0.3-0.6 m per pixel. It is public domain, orthorectified, and served free by USGS.

```
py -3.10 download_naip.py --plan landscape/site.json --metres 0.5 --out naip --name site_naip --dry-run
py -3.10 download_naip.py --plan landscape/site.json --metres 0.5 --out naip --name site_naip
```

With `--plan`, the imagery is fetched in the Landscape's own projection and starts exactly at its
north-west corner, so one pixel lines up with one patch of ground and a material can place the photos
by world position alone. You can also use `--aoi` or `--bbox` without a plan.

| Option | Default | Notes |
| --- | --- | --- |
| `--metres` | 1 | Ground metres per pixel. NAIP is natively 0.3-0.6 m; finer than that only enlarges it |
| `--tile-px` | 8192 | Output tile size. 8192 suits Unreal virtual textures; use 4096 for plain textures |
| `--request-px` | 2048 | Pixels per server request (the server's limit is 4000) |
| `--workers` | 4 | Parallel requests. Please keep this modest; it is a free public service |

Size guide at 0.5 m per pixel: every km squared is 4 million pixels, about 8 MB of PNG. A 60 by 20 km
corridor is 4.8 billion pixels in about 72 tiles of 8192, roughly 10 GB, and a few hours to download.

Outputs are `<name>.<UDIM>.png` tiles, a `<name>.json` index giving every tile's ground extent, and a
`.pgw` world file and `.prj` beside each PNG so any GIS (QGIS, Global Mapper) can overlay them to check.
Requests are cached in `<out>/_cache`, so rerunning after an interruption only fetches what is
missing.

### Outside the United States

NAIP stops at the US border. Alternatives:

- **Sentinel-2** (10 m, worldwide, free): Copernicus Data Space Ecosystem, https://dataspace.copernicus.eu.
  Coarse, but seamless and current.
- **National orthophoto programmes** (often 0.1-0.5 m, many openly licensed): for example the
  Netherlands' PDOK Luchtfoto and France's IGN BD ORTHO.
- **Your own drone orthomosaic.**

Commercial web basemaps (Google, Bing, Esri World Imagery, Mapbox) generally do not permit downloading
their imagery for reuse; check the terms before using any of them.

Any georeferenced image can be used: reproject and tile it to the Landscape's grid in QGIS or GDAL,
then follow the next section.

## 8. Put the imagery on the Landscape

With `--origin area` (the default), the Landscape's north-west corner is at Unreal X=0, Y=0, Unreal
+X is east and Unreal +Y is south. Tile `u, v` of the imagery index covers, in centimetres:

```
west  = u * tile_px * metres * 100        north = v * tile_px * metres * 100
size  = tile_px * metres * 100
```

In a material, for one tile:

```
UV = (AbsoluteWorldPosition.xy - float2(west, north)) / size
```

Because Unreal +Y points south and an image's first row is its north edge, this UV needs no flip:
`V = 0` is the tile's north edge.

**Checking the result.** Look at a road, field edge or building footprint. If the photo sits on the
terrain's matching features, it is right. If it is mirrored north to south, flip V. If it is offset by
a whole tile, `u` or `v` is off by one.

**Many tiles.** Import them as a UDIM virtual texture (select the `.1001.png` file; Unreal gathers the
rest), and use `UV = (AbsoluteWorldPosition.xy / size)` so the whole number part picks the tile. Note
that Unreal's UDIM convention counts rows **upward**, while these tiles count **south**, so check the
result as described above and flip the V row index if needed.

## 9. Buildings from OpenStreetMap with blosm

The corridor's buildings were made with [blosm](https://github.com/vvoovv/blosm), a Blender add-on by
Vladimir Elistratov that turns OpenStreetMap footprints into 3D buildings. To make buildings for
another area:

1. **Get OpenStreetMap data** for the area. For a small area, blosm downloads it directly. For a
   large one, download a regional extract from Geofabrik (https://download.geofabrik.de) and cut it to
   your area with `osmconvert` or `osmium`.
2. **Install blosm** in Blender. The free version extrudes footprints and roofs; Blosm Pro adds
   facade textures. Point blosm at its asset pack if you have one.
3. **Import** the `.osm` file with blosm (*Import: OpenStreetMap*). Buildings get their tagged height
   and levels, and roofs by shape.
4. **Export** as FBX, splitting into tiles if the area is large (a single FBX of tens of thousands of
   buildings is slow to import).
5. **Georeference.** blosm places the scene in its own transverse Mercator frame centred on a
   latitude and longitude near the import area, in metres. To put buildings on a Landscape built by
   `build_landscape.py`, find that centre, convert it to the Landscape's projection, and offset by the
   plan's `utm_origin`. The most reliable way to find the centre is the way this project did: match
   named buildings in the OSM data to their meshes and solve for the offset (387 buildings gave a
   34.6 m RMS fit here), then check a few well-known buildings by eye.
6. **Trace heights.** blosm's own terrain is not your Landscape's terrain. Place each building's
   footprint position, then trace down onto the Landscape for its height, rather than keeping the Z
   from Blender.

OpenStreetMap data requires attribution: "(c) OpenStreetMap contributors", under the Open Database
License.

The building tile meshes used in this project are included in `Content/Buildings`. Their placement
data, each tile's position relative to the Landscape, is `corridor_tiles_baked/corridor_tiles.json`
in [MAirCorridor_Assets](https://github.com/sriceumich/MAirCorridor_Assets), with the tile FBX files, the Blender scene they were baked from and
its upscaled textures. [ASSEMBLY.md](../ASSEMBLY.md#5-buildings) step 5 places them and splits
them into one actor per building on the Landscape, with `blender/building_index.py` and
`unreal/split_buildings.py`.

### Addresses

Every building in the level has an address, its OpenStreetMap id, its building type and its use,
as tags on its actor (`address:...`, `osm:way/...`, `building_type:...`, `use:...`) and in
`building_addresses.json` in the assets. blosm wrote every building's OpenStreetMap tags and id
onto its Blender object, and the January blosm scene still has them; the building's name in the
level finds it there (all 73,403 matched, each to a different OpenStreetMap element, sizes equal
to the millimetre). Its true footprint comes from the OpenStreetMap extract the scene was built
from, so nothing depends on how well the scene was georeferenced.

| Source | Buildings | What it is |
| --- | ---: | --- |
| `osm` | 3,180 | Its own address in OpenStreetMap |
| `osm-point` | 508 | An OpenStreetMap address point inside its footprint |
| `neighbours` | 5,165 | Estimated between the real addresses of neighbours on the same side of the same street |
| `census` | 63,297 | Estimated from the census house number range of the street segment beside it |
| `street` | 1,229 | The street, ZIP code and city, no number (in Windsor, Ontario, the street only) |
| `none` | 24 | Inside large industrial sites, no addressed street within 500 m |

How good the estimates are was measured on the buildings whose real address is known, each
estimated as if it were not. The street is right for 91% of houses, 81% of apartment buildings
and 55% of other buildings (large ones, set back from the road or on a corner, are the hard
case). Where the street is right, the census range alone puts the number within 10 of the real
one 24% of the time and within 50 78% of the time (median error 24); taken from neighbours,
63% and 89% (median error 6). The ZIP code is right 96% of the time. So an estimated address is
a good guess at the block, not a mailing address; `address_source` says which kind each is.

To make them again:

```
blender --background --factory-startup <January corridor_new.blend> --python Tools/blender/building_osm_tags.py -- <project>/Saved/MAirCorridor/building_index <assets>/corridor_osm_tags.json
py -3.10 Tools/building_addresses.py
UnrealEditor-Cmd.exe <project>.uproject -run=pythonscript -script=<absolute path>/Tools/unreal/tag_building_addresses.py "-EnablePlugins=PythonScriptPlugin,EditorScriptingUtilities" -unattended -nullrhi
```

The assets already hold what the first makes, `corridor_osm_tags.json`, so it is only needed to
read the tags again: it reads the JANUARY `corridor_new.blend`, which is not in the assets (the
September one in `New Folder` lost the tags in an FBX round trip). The second reads
`osm_files/fullcorridor.osm` and `osm_files/aircorridor.osm` from the assets and downloads the
census ranges the first time; its header says what each source means. The third needs the
editor closed.

## 10. Vegetation inputs

*Tools > M-Air Corridor > Place Corridor Trees and Rocks...* reads four inputs. The corridor's own
are in [MAirCorridor_Assets](https://github.com/sriceumich/MAirCorridor_Assets): `corridor_scene.json`, `corridor_trees/` and `corridor_rocks/`
([ASSEMBLY.md](../ASSEMBLY.md#6-vegetation) step 6). The formats below are for making them for
another area.

**A scene file** (any name, for example `corridor_scene.json`): positions in **centimetres relative to
the Landscape actor**, X east and Y south, with no heights (every instance is traced onto the
Landscape).

```json
{
  "points": { "tree": [ { "x": 4933139.5, "y": 1040562.5 } ] },
  "areas":  {
    "wood":  [ { "pts": [ [934641.2, 1358997.8], [933752.5, 1359507.6], [932010.0, 1357400.1] ] } ],
    "scrub": [], "park": [], "grass": [], "farmland": []
  }
}
```

`points.tree` are individual surveyed trees, placed exactly. `areas` are polygons to scatter inside;
the layer names match the density table. Build this from OpenStreetMap (`natural=tree`,
`natural=wood`, `landuse=forest`, `natural=scrub`, `leisure=park`, `landuse=grass`,
`landuse=farmland`) in any GIS, converting coordinates with the plan's `utm_origin` and
`quad_metres`.

**A tree folder** of `.fbx` meshes plus `trees.json`, and optionally **a rock folder** of `.fbx` plus
`rocks.json`, each listing `{"name": "...", "height_m": ...}` per mesh. The height is used to correct
the import scale by measuring each mesh.

**Optionally `foliage_density.json`**, beside the scene file or in the plugin's `Content/Vegetation`:

```json
{
  "scale": 1.0,
  "layers": {
    "wood":     { "trees_per_ha": 240, "rocks_per_ha": 4 },
    "scrub":    { "trees_per_ha": 40,  "rocks_per_ha": 14 },
    "park":     { "trees_per_ha": 35,  "rocks_per_ha": 1 },
    "grass":    { "trees_per_ha": 6,   "rocks_per_ha": 2 },
    "farmland": { "trees_per_ha": 1.5, "rocks_per_ha": 0.5 }
  },
  "instance_variation": {
    "tree_scale_min": 0.8, "tree_scale_max": 1.25,
    "rock_scale_min": 0.35, "rock_scale_max": 1.6, "rock_tilt_degrees": 12
  }
}
```

Without it the values above are used. The random seed is fixed, so the same inputs always produce the
same forest.

## 11. Reproducing the M-Air corridor

The corridor's own landscape plan and imagery, as the level uses them, are in
[MAirCorridor_Assets](https://github.com/sriceumich/MAirCorridor_Assets) (`ue_rect_3m/`, `naip_rect_066m/`), and [ASSEMBLY.md](../ASSEMBLY.md)
builds the level from them. These commands regenerate them from the public sources instead, for the
same area with these tools. The originals were produced by earlier scripts writing the same formats;
the results match in source data, projection and grid.

```
cd Tools

# Elevation: USGS 3DEP 1/9 arc-second, which is what the corridor Landscape uses, plus 1/3
# arc-second to fill any gap. The box is the Landscape's rectangle in longitude and latitude.
py -3.10 download_3dep.py --bbox -83.8199 42.2052 -83.0212 42.4125 --product 19 --out dem_cache
py -3.10 download_3dep.py --bbox -83.8199 42.2052 -83.0212 42.4125 --product 13 --out dem_cache

# Landscape: the exact UTM rectangle, 3 m quads, one actor, as shipped.
# Result: 21931 x 7141 vertices, 43 x 14 components, north-west corner 267907 E 4697571 N.
py -3.10 build_landscape.py --dem "dem_cache/*.img" "dem_cache/USGS_13_*.tif" \
    --epsg 26917 --projected-bounds 267907 4676390 333186 4697571 --metres 3 \
    --max-vertices 22000 --out landscape --name mcity_rect_3m

# Imagery: NAIP at 0.5 m, aligned to that Landscape.
py -3.10 download_naip.py --plan landscape/mcity_rect_3m.json --metres 0.5 --out naip --name mcity_naip_05m
```

The shipped Landscape used Z scale 100; this tool picks a finer one for the same range, so the heights
are the same with smaller steps. `--max-vertices 22000` keeps it as a single actor to match; leaving
the default splits it into 3 by 1 segments instead, which is lighter on the editor.

For a 1 m build of the corridor itself, download `--product 1m` as well, list those files first in
`--dem`, use `--aoi` instead of `--bbox`, and `--metres 1`.

## 12. Data licences and attribution

| Data | Licence | Attribution to include |
| --- | --- | --- |
| USGS 3DEP | Public domain | "Elevation data: U.S. Geological Survey, 3D Elevation Program" (requested, not required) |
| USDA NAIP | Public domain | "Imagery: USDA Farm Service Agency, National Agriculture Imagery Program" (requested) |
| Copernicus DEM | Free with attribution | "produced using Copernicus WorldDEM-30 (c) DLR e.V. 2010-2014 and (c) Airbus Defence and Space GmbH 2014-2018 provided under COPERNICUS by the European Union and ESA; all rights reserved" |
| OpenStreetMap | ODbL 1.0 | "(c) OpenStreetMap contributors" |
| US Census Bureau TIGER/Line | Public domain | "Address ranges: U.S. Census Bureau, TIGER/Line Shapefiles" (requested) |
| Any other dataset | Its own terms | Check before you publish |

Data you download keeps its own terms, whatever the tool that fetched it.

## 13. Troubleshooting

| Symptom | Cause and fix |
| --- | --- |
| `needs rasterio` | Run `py -3.10 -m pip install -r requirements.txt` with the same Python you run the tool with |
| `The National Map API did not answer` | The USGS API is briefly overloaded. Wait a few minutes and rerun; finished files are kept |
| `Nothing found` from `download_3dep.py` | No lidar product there. Use `--product 13`, which covers the whole US |
| `no elevation data inside the area` | The rasters do not overlap the area. Check `--bbox` is west, south, east, north |
| `CLIPPED` | Rerun with `--zmin` / `--zmax` covering the real range |
| Terrain 3 times too tall | Source heights are in feet. Convert them ([section 4](#4-using-any-elevation-data)) |
| A cliff along a seam between two sources | The sources use different vertical datums ([section 4](#4-using-any-elevation-data)) |
| Unreal refuses the plan | The message names the rule broken. Usually a `.r16` was moved or truncated; keep it beside the JSON |
| `NO IMAGERY HERE` | NAIP does not cover that tile (outside the US, or over water) |
| Imagery mirrored or offset | See *Checking the result* in [section 8](#8-put-the-imagery-on-the-landscape) |
