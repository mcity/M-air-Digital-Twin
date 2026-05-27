# CARLA AIR Documentation

> Version: 0.1.7 | Language: English | Generated: 2026-05-27T16:40:56.993Z

## Table of Contents

### Getting Started
- [Getting Started](#getting-started)
  - [Installation](#getting-started-installation)
  - [Quick Start](#getting-started-quick-start)
  - [First Simulation](#getting-started-first-simulation)

### Core Concepts
  - [Sensors](#core-concepts-sensors)
  - [Vehicles & Traffic](#core-concepts-vehicles)
  - [World & Maps](#core-concepts-world-maps)
  - [Weather & Environment](#core-concepts-weather)
  - [Traffic & Pedestrians](#core-concepts-traffic)
- [Core Concepts](#core-concepts)

### API Reference
  - [Client API](#api-reference-client)
  - [Drone API Reference](#api-reference-drone)
  - [Vehicle API](#api-reference-vehicle)
  - [Sensor API](#api-reference-sensor)
  - [World API](#api-reference-world)
  - [ROS Integration](#api-reference-ros)
- [API Reference](#api-reference)

### Tutorials
  - [Sensors](#tutorials-sensors)
  - [Drone Navigation](#tutorials-drone-navigation)
  - [Data Collection](#tutorials-data-collection)
- [Tutorials](#tutorials)

### Advanced Topics
  - [Coordinate Systems](#advanced-coordinate-systems)
  - [Synchronization](#advanced-synchronization)
  - [Performance Optimization](#advanced-performance)
- [Advanced Topics](#advanced)

### Air-Ground Co-Simulation
  - [Drone-Vehicle Following](#air-ground-drone-following)
  - [Drone-Pedestrian-Following](#air-ground-drone-pedestrian-following)
  - [Multi-Agent Scenarios](#air-ground-multi-agent)
  - [Trajectory Recording](#air-ground-trajectory-recording)
- [Air-Ground Co-Simulation](#air-ground)

---

<a id="getting-started"></a>

## Getting Started

> v0.1.7 Welcome to Carla Air! This guide will help you get up and running with the Carla Air simulation platform for autonomous vehicles and drones.

# Getting Started v0.1.7

Welcome to Carla Air! This guide will help you get up and running with the Carla Air simulation platform for autonomous vehicles and drones.

## What is Carla Air?

Carla Air is a next-generation open-source simulator that combines the best features of CARLA and AirSim. It provides a high-fidelity environment for developing, testing, and validating autonomous systems for both ground vehicles and aerial drones.

## Key Features

- High-fidelity physics simulation powered by Unreal Engine
- Comprehensive sensor suite including LiDAR, cameras, radar, IMU, and GPS
- Support for autonomous vehicles, drones, and multi-agent scenarios
- Intuitive Python API with ROS/ROS2 integration
- Customizable environments, weather, and traffic conditions
- Built-in data collection and recording capabilities

## Prerequisites

Before installing Carla Air, ensure your system meets the following requirements:

Operating System: Ubuntu 20.04/22.04 LTS or Windows 10/11

GPU: NVIDIA GPU with 8GB+ VRAM (RTX 2070 or better recommended)

RAM: 16GB minimum, 32GB recommended

Storage: 50GB free disk space

Python: 3.8 - 3.11

## Next Steps

Ready to get started? Follow these guides in order:

### 1. Installation

Download and install Carla Air on your system

### 2. Quick Start

Connect to the simulator and spawn your first vehicle

### 3. First Simulation

Run your first complete simulation with sensors and data collection



---

<a id="getting-started-installation"></a>

### Installation

> This guide covers the installation of Carla Air on different operating systems. Carla Air combines CARLA and AirSim for air-ground cooperative simulation.

# Installation Guide

This guide walks you through the complete installation process for CARLA-Air v0.1.7, a unified simulation platform that combines CARLA (autonomous driving) and AirSim (drone simulation) in a single environment.

## System Requirements

Before installation, ensure your system meets the following requirements:

| Component | Minimum | Recommended |
|-----------|---------|-------------|
| OS | Ubuntu 20.04 LTS | Ubuntu 22.04 LTS |
| GPU | NVIDIA GTX 1060 | NVIDIA RTX 3070+ |
| VRAM | 6 GB | 8+ GB |
| RAM | 16 GB | 32 GB |
| Storage | 25 GB | 50 GB SSD |
| CUDA | 11.0+ | 11.8+ |

## Download CARLA-Air

CARLA-Air v0.1.7 is available from multiple sources:

### Option 1: Baidu Netdisk (Binary Release)

```bash
# Download link
https://pan.baidu.com/s/1RguWqwKrN-3KEgyKvWiiug?pwd=d5ai
```

### Option 2: Hugging Face (Binary Release)

```bash
# Clone from Hugging Face
git lfs install
git clone https://huggingface.co/tianlezeng/CarlaAIr-v0.1.7
```

### Option 3: GitHub Releases (Source Code)

```bash
# Download from GitHub
wget https://github.com/louiszengCN/CarlaAir/releases/download/v0.1.7/CarlaAir-v0.1.7.tar.gz
```

## Extract and Setup

After downloading, extract the archive:

```bash
# Extract the archive (approximately 18GB)
tar xzf CarlaAir-v0.1.7.tar.gz
cd CarlaAir-v0.1.7
```

## Environment Setup

CARLA-Air requires a specific Python environment with pre-compiled modules. Use the provided setup script:

```bash
# Run the automated setup script
bash env_setup/setup_env.sh
```

This script will:
1. Create a Conda environment named `carlaAir`
2. Install Python 3.8 with required dependencies
3. Install the pre-compiled CARLA and AirSim Python modules
4. Configure environment variables

### Manual Setup (Alternative)

If you prefer manual installation:

```bash
# Create conda environment
conda create -n carlaAir python=3.8 -y
conda activate carlaAir

# Install dependencies
pip install numpy opencv-python pygame

# Install CARLA Python API (use the bundled version)
pip install CarlaAir-v0.1.7/PythonAPI/carla/dist/carla-0.9.15-cp38-cp38-linux_x86_64.whl

# Install AirSim Python API
pip install airsim
```

**Important:** Do not use `pip install carla` from PyPI - it is incompatible with CARLA-Air due to ABI differences.

## Verify Installation

Run the verification script to ensure everything is properly installed:

```bash
# Activate the environment
conda activate carlaAir

# Run verification
bash env_setup/test_env.sh
```

You should see output confirming both CARLA and AirSim modules are available:

```
[OK] carla module imported successfully
[OK] airsim module imported successfully
[OK] numpy version: 1.24.x
[OK] opencv version: 4.x.x
Environment setup complete!
```

## Launch the Simulator

To start CARLA-Air:

```bash
# Navigate to the installation directory
cd /path/to/CarlaAir-v0.1.7

# Activate the environment
conda activate carlaAir

# Launch with default map (Town10HD)
./CarlaAir.sh Town10HD
```

Wait for the message:
```
Ready! Both servers are running.
CARLA server: localhost:2000
AirSim server: localhost:41451
```

## Available Maps

CARLA-Air includes several pre-built maps:

| Map | Description |
|-----|-------------|
| Town01 | Small town with simple road network |
| Town02 | Residential area with T-junctions |
| Town03 | Urban downtown with roundabouts |
| Town04 | Highway with on/off ramps |
| Town05 | Urban grid with multi-lane roads |
| Town10HD | High-definition coastal city (default) |

To launch with a specific map:

```bash
./CarlaAir.sh Town03
```

## Troubleshooting

### GPU Driver Issues

If you encounter rendering issues:

```bash
# Check NVIDIA driver
nvidia-smi

# Ensure driver version is 470+
```

### Port Conflicts

If ports 2000 or 41451 are in use:

```bash
# Check for processes using these ports
lsof -i :2000
lsof -i :41451

# Kill conflicting processes if needed
kill -9 <PID>
```

### Display Issues

For headless servers or remote connections:

```bash
# Run with off-screen rendering
./CarlaAir.sh Town10HD -RenderOffScreen
```

## Next Steps

Once installation is complete:

- [Quick Start Guide](/docs/0.1.7/getting-started/quick-start) - Connect and run your first script
- [First Simulation](/docs/0.1.7/getting-started/first-simulation) - Create your first simulation scenario


---

<a id="getting-started-quick-start"></a>

### Quick Start

> Get up and running with Carla Air in just a few minutes. This guide will walk you through starting the simulator, spawning your first vehicle and drone.

# Quick Start Guide

This guide will help you connect to CARLA-Air and run your first Python script. By the end, you'll understand the dual-API architecture and be ready to build your own simulations.

## Prerequisites

- CARLA-Air v0.1.7 installed ([Installation Guide](../01-installation/installation.md))
- Conda environment `carlaAir` activated
- Simulator running (`./CarlaAir.sh Town10HD`)

## Understanding the Dual-API Architecture

CARLA-Air is unique because it runs two simulation APIs simultaneously in a single process:

```
┌─────────────────────────────────────────────┐
│              CARLA-Air Simulator            │
│                                             │
│  ┌─────────────────┐  ┌─────────────────┐  │
│  │   CARLA API     │  │   AirSim API    │  │
│  │   Port 2000     │  │   Port 41451    │  │
│  │                 │  │                 │  │
│  │  - Vehicles     │  │  - Drones       │  │
│  │  - Pedestrians  │  │  - Flight Ctrl  │  │
│  │  - Weather      │  │  - Air Sensors  │  │
│  │  - Traffic      │  │                 │  │
│  └─────────────────┘  └─────────────────┘  │
│                                             │
│         Shared Unreal Engine World          │
└─────────────────────────────────────────────┘
```

| API | Port | Python Library | Primary Use |
|-----|------|----------------|-------------|
| CARLA | 2000 | `import carla` | Vehicles, pedestrians, weather, ground sensors |
| AirSim | 41451 | `import airsim` | Drone flight control, aerial cameras |

## Connecting to Both APIs

Here's the standard pattern for connecting to CARLA-Air:

```python
import carla
import airsim

# Connect to CARLA API
client = carla.Client("localhost", 2000)
client.set_timeout(10.0)
world = client.get_world()
blueprint_library = world.get_blueprint_library()

# Connect to AirSim API
air_client = airsim.MultirotorClient(port=41451)
air_client.confirmConnection()
```

## Your First Script

Let's create a simple script that connects to both APIs and retrieves basic information:

```python
#!/usr/bin/env python3
"""
hello_carla_air.py - First CARLA-Air script
"""

import carla
import airsim

def main():
    # ════════════════════════════════════════════════════════
    # Connect to CARLA
    # ════════════════════════════════════════════════════════
    print("Connecting to CARLA...")
    client = carla.Client("localhost", 2000)
    client.set_timeout(10.0)

    world = client.get_world()
    map_name = world.get_map().name.split("/")[-1]

    print(f"  CARLA connected!")
    print(f"  Current map: {map_name}")
    print(f"  Available blueprints: {len(world.get_blueprint_library())}")

    # ════════════════════════════════════════════════════════
    # Connect to AirSim
    # ════════════════════════════════════════════════════════
    print("\nConnecting to AirSim...")
    air_client = airsim.MultirotorClient(port=41451)
    air_client.confirmConnection()

    state = air_client.getMultirotorState()
    pos = state.kinematics_estimated.position

    print(f"  AirSim connected!")
    print(f"  Drone position: ({pos.x_val:.1f}, {pos.y_val:.1f}, {pos.z_val:.1f})")

    # ════════════════════════════════════════════════════════
    # Summary
    # ════════════════════════════════════════════════════════
    print("\n" + "=" * 40)
    print("CARLA-Air is ready!")
    print("  CARLA: localhost:2000")
    print("  AirSim: localhost:41451")
    print("=" * 40)

if __name__ == "__main__":
    main()
```

## Running the Script

1. Ensure the simulator is running:
   ```bash
   cd /path/to/CarlaAir-v0.1.7
   ./CarlaAir.sh Town10HD
   ```

2. In a new terminal, run your script:
   ```bash
   conda activate carlaAir
   python hello_carla_air.py
   ```

Expected output:
```
Connecting to CARLA...
  CARLA connected!
  Current map: Town10HD
  Available blueprints: 258

Connecting to AirSim...
  AirSim connected!
  Drone position: (100.0, 80.0, -5.0)

========================================
CARLA-Air is ready!
  CARLA: localhost:2000
  AirSim: localhost:41451
========================================
```

## Spawning Your First Vehicle

Let's spawn a vehicle and attach a camera:

```python
import carla
import time

# Connect
client = carla.Client("localhost", 2000)
client.set_timeout(10.0)
world = client.get_world()
bp_lib = world.get_blueprint_library()

# Get vehicle blueprint
vehicle_bp = bp_lib.find("vehicle.tesla.model3")

# Get spawn point
spawn_points = world.get_map().get_spawn_points()
spawn_point = spawn_points[0]

# Spawn vehicle
vehicle = world.try_spawn_actor(vehicle_bp, spawn_point)
print(f"Spawned: {vehicle.type_id}")

# Enable autopilot
vehicle.set_autopilot(True)
print("Autopilot enabled")

# Let it drive for 10 seconds
time.sleep(10)

# Cleanup
vehicle.destroy()
print("Vehicle destroyed")
```

## Taking Off with the Drone

Control the AirSim drone:

```python
import airsim
import time

# Connect
air_client = airsim.MultirotorClient(port=41451)
air_client.confirmConnection()

# Initialize drone (required sequence)
air_client.enableApiControl(True)
air_client.armDisarm(True)

# Take off
print("Taking off...")
air_client.takeoffAsync().join()

# Fly up 10 meters
print("Flying up...")
air_client.moveToZAsync(-10, 2).join()  # NED coordinates: negative Z = up

# Hover for 5 seconds
print("Hovering...")
time.sleep(5)

# Land
print("Landing...")
air_client.landAsync().join()

# Release control
air_client.armDisarm(False)
air_client.enableApiControl(False)
print("Done!")
```

## Important Notes

### Always Clean Up Resources

Use try-finally blocks to ensure proper cleanup:

```python
actors = []
try:
    vehicle = world.spawn_actor(bp, transform)
    actors.append(vehicle)
    # ... your code ...
finally:
    for actor in actors:
        actor.destroy()
```

### Drone Initialization Sequence

The drone requires a specific initialization order:

```python
air_client.confirmConnection()    # 1. Confirm connection
air_client.enableApiControl(True) # 2. Enable API control
air_client.armDisarm(True)        # 3. Arm the drone
air_client.takeoffAsync().join()  # 4. Take off
```

Skipping any step will cause the drone to not respond.

### Use try_spawn_actor

Always use `try_spawn_actor` instead of `spawn_actor`:

```python
# Good - returns None if spawn fails
vehicle = world.try_spawn_actor(bp, transform)
if vehicle is None:
    print("Spawn failed, trying another location")

# Bad - throws exception if spawn fails
vehicle = world.spawn_actor(bp, transform)
```

## Next Steps

- [First Simulation](/docs/0.1.7/getting-started/first-simulation) - Build a complete simulation scenario
- [World & Maps](/docs/0.1.7/core-concepts/world-maps) - Learn about the simulation environment
- [Weather Control](/docs/0.1.7/core-concepts/weather) - Change weather conditions


---

<a id="getting-started-first-simulation"></a>

### First Simulation

> In this tutorial, you'll learn how to set up a complete simulation with sensors, data collection, and environment configuration.

In this tutorial, you'll build a complete simulation scenario that demonstrates the core capabilities of CARLA-Air: ground vehicles with traffic, aerial drone surveillance, and sensor data collection.

## What You'll Build

By the end of this tutorial, you'll have created a simulation that:
- Spawns multiple vehicles with autopilot
- Launches a drone for aerial observation
- Attaches cameras to capture footage
- Records video from both ground and air perspectives

## Prerequisites

- CARLA-Air running (`./CarlaAir.sh Town10HD`)
- Completed [Quick Start Guide](../02-quick-start/quick-start.md)

## The Complete Simulation Script

Here's the full script we'll be building. Each section is explained below.

```python
#!/usr/bin/env python3
"""
first_simulation.py - Complete CARLA-Air simulation scenario
"""

import carla
import airsim
import time
import numpy as np

def main():
    actors = []
    air_client = None

    try:
        # ════════════════════════════════════════════════════════
        # Connect to both APIs
        # ════════════════════════════════════════════════════════
        print("Connecting to CARLA-Air...")

        client = carla.Client("localhost", 2000)
        client.set_timeout(10.0)
        world = client.get_world()
        bp_lib = world.get_blueprint_library()

        air_client = airsim.MultirotorClient(port=41451)
        air_client.confirmConnection()

        print("Connected!")

        # ════════════════════════════════════════════════════════
        # Spawn traffic vehicles
        # ════════════════════════════════════════════════════════
        print("\nSpawning traffic...")

        spawn_points = world.get_map().get_spawn_points()
        vehicle_bps = list(bp_lib.filter("vehicle.*"))

        # Spawn 5 vehicles
        for i, sp in enumerate(spawn_points[:5]):
            bp = vehicle_bps[i % len(vehicle_bps)]
            vehicle = world.try_spawn_actor(bp, sp)
            if vehicle:
                actors.append(vehicle)
                vehicle.set_autopilot(True)

        print(f"  Spawned {len(actors)} vehicles")

        # ════════════════════════════════════════════════════════
        # Launch drone
        # ════════════════════════════════════════════════════════
        print("\nLaunching drone...")

        air_client.enableApiControl(True)
        air_client.armDisarm(True)
        air_client.takeoffAsync().join()

        # Fly to observation altitude
        air_client.moveToZAsync(-20, 3).join()

        state = air_client.getMultirotorState()
        pos = state.kinematics_estimated.position
        print(f"  Drone at altitude: {-pos.z_val:.1f}m")

        # ════════════════════════════════════════════════════════
        # Run simulation for 30 seconds
        # ════════════════════════════════════════════════════════
        print("\nSimulation running...")
        print("  Press Ctrl+C to stop early")

        for i in range(30):
            # Keep drone hovering
            air_client.hoverAsync()

            # Print status every 5 seconds
            if i % 5 == 0:
                print(f"  Time: {i}s")

            time.sleep(1)

        print("\nSimulation complete!")

    except KeyboardInterrupt:
        print("\nStopped by user")

    finally:
        # ════════════════════════════════════════════════════════
        # Cleanup
        # ════════════════════════════════════════════════════════
        print("\nCleaning up...")

        if air_client:
            air_client.landAsync().join()
            air_client.armDisarm(False)
            air_client.enableApiControl(False)

        for actor in actors:
            try:
                actor.destroy()
            except:
                pass

        print("Done!")

if __name__ == "__main__":
    main()
```

## Understanding the Code

### 1. Connecting to Both APIs

```python
client = carla.Client("localhost", 2000)
client.set_timeout(10.0)
world = client.get_world()
bp_lib = world.get_blueprint_library()

air_client = airsim.MultirotorClient(port=41451)
air_client.confirmConnection()
```

The `world` object is your gateway to the CARLA simulation. The `bp_lib` (blueprint library) contains templates for all spawnable objects.

### 2. Spawning Traffic

```python
spawn_points = world.get_map().get_spawn_points()
vehicle_bps = list(bp_lib.filter("vehicle.*"))

for i, sp in enumerate(spawn_points[:5]):
    bp = vehicle_bps[i % len(vehicle_bps)]
    vehicle = world.try_spawn_actor(bp, sp)
    if vehicle:
        actors.append(vehicle)
        vehicle.set_autopilot(True)
```

Key points:
- `get_spawn_points()` returns predefined safe locations for spawning
- `bp_lib.filter("vehicle.*")` gets all vehicle blueprints
- `try_spawn_actor` returns `None` if the spawn fails (instead of throwing an exception)
- `set_autopilot(True)` hands control to the Traffic Manager

### 3. Drone Control

```python
air_client.enableApiControl(True)  # Take control from manual input
air_client.armDisarm(True)         # Arm motors
air_client.takeoffAsync().join()   # Take off and wait

air_client.moveToZAsync(-20, 3).join()  # Fly to 20m altitude at 3 m/s
```

AirSim uses the NED (North-East-Down) coordinate system:
- Positive Z is down, so `-20` means 20 meters up
- Most movement commands are async; use `.join()` to wait for completion

### 4. Proper Cleanup

```python
finally:
    if air_client:
        air_client.landAsync().join()
        air_client.armDisarm(False)
        air_client.enableApiControl(False)

    for actor in actors:
        actor.destroy()
```

The `finally` block ensures cleanup happens even if an error occurs:
- Land the drone before releasing control
- Disarm motors and release API control
- Destroy all spawned actors

## Adding Camera Recording

Extend the simulation to record video:

```python
# Setup camera on main vehicle
cam_bp = bp_lib.find("sensor.camera.rgb")
cam_bp.set_attribute("image_size_x", "1280")
cam_bp.set_attribute("image_size_y", "720")

cam_transform = carla.Transform(
    carla.Location(x=-6.0, z=3.0),
    carla.Rotation(pitch=-10)
)

# Attach to first vehicle
camera = world.spawn_actor(cam_bp, cam_transform, attach_to=actors[0])
actors.append(camera)

# Collect frames
frames = []
camera.listen(lambda image: frames.append(process_image(image)))

def process_image(image):
    arr = np.frombuffer(image.raw_data, dtype=np.uint8)
    arr = arr.reshape((image.height, image.width, 4))[:, :, :3]
    return arr[:, :, ::-1].copy()  # Convert BGRA to BGR
```

## Getting Drone Camera Feed

AirSim provides direct image capture:

```python
# Get image from drone camera
responses = air_client.simGetImages([
    airsim.ImageRequest("0", airsim.ImageType.Scene, False, False)
])

if responses:
    response = responses[0]
    img = np.frombuffer(response.image_data_uint8, dtype=np.uint8)
    img = img.reshape(response.height, response.width, 3)
```

## Best Practices

### 1. Resource Management

Always track actors for cleanup:
```python
actors = []
sensors = []

try:
    vehicle = world.spawn_actor(bp, transform)
    actors.append(vehicle)

    camera = world.spawn_actor(cam_bp, cam_tf, attach_to=vehicle)
    actors.append(camera)
    sensors.append(camera)
finally:
    for s in sensors:
        s.stop()
    for a in actors:
        a.destroy()
```

### 2. Limit Vehicle Count with Drone

When the drone is active, limit autopilot vehicles to 8 or fewer:
```python
max_vehicles = 8 if drone_active else 20
```

### 3. Handle Spawn Failures

```python
vehicle = world.try_spawn_actor(bp, spawn_point)
if vehicle is None:
    print(f"Spawn failed at {spawn_point.location}")
    continue  # Try next spawn point
```

## Next Steps

Now that you have a working simulation:

- [World & Maps](/docs/0.1.7/core-concepts/world-maps) - Explore different environments
- [Weather Control](/docs/0.1.7/core-concepts/weather) - Add dynamic weather
- [Sensors](/docs/0.1.7/core-concepts/sensors) - Attach depth, lidar, and other sensors


---

<a id="core-concepts-sensors"></a>

### Sensors

> Carla Air provides a comprehensive suite of sensors for perception and localization. This guide covers all available sensors and their configuration options.

Sensors are actors that collect data from the simulation environment. CARLA-Air provides various sensor types including cameras, LiDAR, radar, and more. This guide covers sensor setup, data processing, and best practices.

## Sensor Types Overview

| Sensor | Blueprint | Output |
|--------|-----------|--------|
| RGB Camera | `sensor.camera.rgb` | Color images (BGRA) |
| Depth Camera | `sensor.camera.depth` | Depth encoded images |
| Semantic Segmentation | `sensor.camera.semantic_segmentation` | Class-labeled images |
| LiDAR | `sensor.lidar.ray_cast` | 3D point cloud |
| Radar | `sensor.other.radar` | Velocity/distance data |
| IMU | `sensor.other.imu` | Acceleration/orientation |
| GNSS | `sensor.other.gnss` | GPS coordinates |
| Collision | `sensor.other.collision` | Collision events |

## Attaching Sensors

Sensors are typically attached to vehicles:

```python
import carla

# Get sensor blueprint
cam_bp = world.get_blueprint_library().find("sensor.camera.rgb")

# Configure sensor
cam_bp.set_attribute("image_size_x", "1280")
cam_bp.set_attribute("image_size_y", "720")
cam_bp.set_attribute("fov", "90")

# Define attachment position (relative to vehicle)
cam_transform = carla.Transform(
    carla.Location(x=1.5, z=2.4),  # Front, above hood
    carla.Rotation(pitch=-5)       # Slightly downward
)

# Attach to vehicle
camera = world.spawn_actor(cam_bp, cam_transform, attach_to=vehicle)
```

## RGB Camera

### Setup

```python
cam_bp = bp_lib.find("sensor.camera.rgb")
cam_bp.set_attribute("image_size_x", "1920")
cam_bp.set_attribute("image_size_y", "1080")
cam_bp.set_attribute("fov", "90")

# Disable motion blur for clearer images
cam_bp.set_attribute("motion_blur_intensity", "0.0")
cam_bp.set_attribute("motion_blur_max_distortion", "0.0")
```

### Processing Images

```python
import numpy as np

def process_rgb(image):
    # Convert raw data to numpy array
    arr = np.frombuffer(image.raw_data, dtype=np.uint8)

    # Reshape to image dimensions (BGRA format)
    arr = arr.reshape((image.height, image.width, 4))

    # Remove alpha channel, convert to BGR (OpenCV format)
    bgr = arr[:, :, :3]

    return bgr

camera.listen(process_rgb)
```

## Depth Camera

### Setup

```python
depth_bp = bp_lib.find("sensor.camera.depth")
depth_bp.set_attribute("image_size_x", "1280")
depth_bp.set_attribute("image_size_y", "720")
```

### Processing Depth Data

```python
def process_depth(image):
    arr = np.frombuffer(image.raw_data, dtype=np.uint8)
    arr = arr.reshape((image.height, image.width, 4))

    # Decode depth from RGB channels
    # Depth = (R + G*256 + B*256*256) / (256^3 - 1) * 1000 meters
    r = arr[:, :, 2].astype(np.float32)
    g = arr[:, :, 1].astype(np.float32)
    b = arr[:, :, 0].astype(np.float32)

    depth = (r + g * 256 + b * 256 * 256) / (256**3 - 1) * 1000

    return depth  # Depth in meters

depth_camera.listen(process_depth)
```

### Visualizing Depth

```python
import cv2

def visualize_depth(depth):
    # Normalize to 0-255 (assuming max depth of 100m)
    depth_normalized = np.clip(depth / 100.0 * 255, 0, 255).astype(np.uint8)

    # Apply colormap
    colored = cv2.applyColorMap(depth_normalized, cv2.COLORMAP_JET)

    return colored
```

## Semantic Segmentation Camera

### Setup

```python
seg_bp = bp_lib.find("sensor.camera.semantic_segmentation")
seg_bp.set_attribute("image_size_x", "1280")
seg_bp.set_attribute("image_size_y", "720")
```

### Processing Segmentation

```python
# Class ID is stored in the red channel
def process_segmentation(image):
    arr = np.frombuffer(image.raw_data, dtype=np.uint8)
    arr = arr.reshape((image.height, image.width, 4))

    # Class labels are in red channel
    labels = arr[:, :, 2]

    return labels

# Common class IDs:
# 0: Unlabeled, 1: Building, 2: Fence, 3: Other
# 4: Pedestrian, 5: Pole, 6: Road line, 7: Road
# 8: Sidewalk, 9: Vegetation, 10: Vehicle, 11: Wall
# 12: Traffic sign, 13: Sky, 14: Ground, 15: Bridge
```

### Colorizing Segmentation

```python
def colorize_segmentation(labels):
    # Simple color mapping
    colored = np.zeros((labels.shape[0], labels.shape[1], 3), dtype=np.uint8)

    colored[:, :, 0] = (labels * 12 % 256)  # B
    colored[:, :, 1] = (labels * 37 % 256)  # G
    colored[:, :, 2] = (labels * 83 % 256)  # R

    return colored
```

## LiDAR

### Setup

```python
lidar_bp = bp_lib.find("sensor.lidar.ray_cast")
lidar_bp.set_attribute("channels", "64")
lidar_bp.set_attribute("range", "100")
lidar_bp.set_attribute("points_per_second", "1000000")
lidar_bp.set_attribute("rotation_frequency", "20")
lidar_bp.set_attribute("upper_fov", "15")
lidar_bp.set_attribute("lower_fov", "-25")
```

### Processing Point Cloud

```python
def process_lidar(point_cloud):
    # Get point cloud data
    data = np.frombuffer(point_cloud.raw_data, dtype=np.float32)
    data = data.reshape((-1, 4))  # x, y, z, intensity

    points = data[:, :3]
    intensity = data[:, 3]

    return points, intensity
```

## Multiple Sensors

### Sensor Array Setup

```python
# RGB camera
rgb_bp = bp_lib.find("sensor.camera.rgb")
rgb_bp.set_attribute("image_size_x", "640")
rgb_bp.set_attribute("image_size_y", "360")

# Depth camera
depth_bp = bp_lib.find("sensor.camera.depth")
depth_bp.set_attribute("image_size_x", "640")
depth_bp.set_attribute("image_size_y", "360")

# Semantic segmentation
seg_bp = bp_lib.find("sensor.camera.semantic_segmentation")
seg_bp.set_attribute("image_size_x", "640")
seg_bp.set_attribute("image_size_y", "360")

# Same position for all
cam_tf = carla.Transform(
    carla.Location(x=-6.0, z=3.0),
    carla.Rotation(pitch=-10)
)

# Spawn all sensors
rgb_cam = world.spawn_actor(rgb_bp, cam_tf, attach_to=vehicle)
depth_cam = world.spawn_actor(depth_bp, cam_tf, attach_to=vehicle)
seg_cam = world.spawn_actor(seg_bp, cam_tf, attach_to=vehicle)
```

### Synchronized Data Collection

```python
sensor_data = {
    "rgb": None,
    "depth": None,
    "seg": None
}

def on_rgb(image):
    sensor_data["rgb"] = process_rgb(image)

def on_depth(image):
    sensor_data["depth"] = process_depth(image)

def on_seg(image):
    sensor_data["seg"] = process_segmentation(image)

rgb_cam.listen(on_rgb)
depth_cam.listen(on_depth)
seg_cam.listen(on_seg)
```

## Sensor Cleanup

Always stop and destroy sensors properly:

```python
sensors = [rgb_cam, depth_cam, seg_cam]

# Stop listening
for sensor in sensors:
    sensor.stop()

# Destroy actors
for sensor in sensors:
    sensor.destroy()
```

## Camera Positions

Common camera placements:

```python
# Third-person view (behind and above)
third_person = carla.Transform(
    carla.Location(x=-8.0, z=5.0),
    carla.Rotation(pitch=-15)
)

# Hood camera (driver view)
hood_cam = carla.Transform(
    carla.Location(x=1.5, z=1.2),
    carla.Rotation(pitch=0)
)

# Bird's eye view
birds_eye = carla.Transform(
    carla.Location(x=0, z=20),
    carla.Rotation(pitch=-90)
)

# Side mirror
side_mirror = carla.Transform(
    carla.Location(x=0.5, y=-0.8, z=1.3),
    carla.Rotation(yaw=-150)
)
```

## Best Practices

1. **Match resolutions**: Use same resolution for sensors that will be combined
2. **Disable motion blur**: Set `motion_blur_intensity` to 0 for cleaner data
3. **Use appropriate FOV**: 90-100 degrees typical for driving scenarios
4. **Manage memory**: Process and discard images promptly
5. **Stop sensors before destroy**: Always call `sensor.stop()` first

## Next Steps

- [Basic Flight](../../chapter-03-drone-flight/01-basic-flight/basic-flight.md) - Drone control
- [Navigation](../../chapter-03-drone-flight/02-navigation/navigation.md) - Waypoint navigation
- [Drone Following](../../chapter-04-air-ground/01-drone-following/drone-following.md) - Track vehicles from air


---

<a id="core-concepts-vehicles"></a>

### Vehicles & Traffic

> Carla Air supports various vehicle types including cars, trucks, motorcycles, and drones. This guide covers vehicle spawning, control, and physics.

CARLA-Air provides comprehensive vehicle simulation including spawning, control, and traffic management. This guide covers vehicle creation, autopilot behavior, and traffic system configuration.

## Spawning Vehicles

### Basic Vehicle Spawning

```python
import carla

client = carla.Client("localhost", 2000)
world = client.get_world()
bp_lib = world.get_blueprint_library()

# Get a vehicle blueprint
vehicle_bp = bp_lib.find("vehicle.tesla.model3")

# Get a spawn point
spawn_points = world.get_map().get_spawn_points()
spawn_point = spawn_points[0]

# Spawn the vehicle
vehicle = world.try_spawn_actor(vehicle_bp, spawn_point)
```

### Available Vehicle Types

```python
# List all vehicle blueprints
vehicles = bp_lib.filter("vehicle.*")
for v in vehicles:
    print(v.id)
```

Categories include:
- **Cars**: `vehicle.tesla.model3`, `vehicle.audi.a2`, `vehicle.bmw.grandtourer`
- **Trucks**: `vehicle.carlamotors.carlacola`, `vehicle.tesla.cybertruck`
- **Motorcycles**: `vehicle.yamaha.yzf`, `vehicle.kawasaki.ninja`
- **Bicycles**: `vehicle.bh.crossbike`, `vehicle.gazelle.omafiets`

### Customizing Vehicle Appearance

```python
vehicle_bp = bp_lib.find("vehicle.audi.a2")

# Set color (RGB as comma-separated string)
if vehicle_bp.has_attribute('color'):
    vehicle_bp.set_attribute('color', '255,0,0')  # Red

# Check all available attributes
for attr in vehicle_bp:
    print(f"{attr.id}: {attr.recommended_values}")
```

## Vehicle Control

### Manual Control

```python
# Get current control state
control = vehicle.get_control()

# Apply control
control = carla.VehicleControl(
    throttle=0.5,      # 0.0 to 1.0
    steer=0.0,         # -1.0 (left) to 1.0 (right)
    brake=0.0,         # 0.0 to 1.0
    hand_brake=False,
    reverse=False
)
vehicle.apply_control(control)
```

### Autopilot Mode

```python
# Enable autopilot (uses Traffic Manager)
vehicle.set_autopilot(True)

# Disable autopilot
vehicle.set_autopilot(False)
```

### Getting Vehicle State

```python
# Location and transform
transform = vehicle.get_transform()
location = vehicle.get_location()

print(f"Position: ({location.x:.1f}, {location.y:.1f}, {location.z:.1f})")

# Velocity
velocity = vehicle.get_velocity()
speed_ms = (velocity.x**2 + velocity.y**2 + velocity.z**2)**0.5
speed_kmh = speed_ms * 3.6
print(f"Speed: {speed_kmh:.1f} km/h")

# Acceleration
acceleration = vehicle.get_acceleration()
```

## Traffic Manager

The Traffic Manager controls autopilot vehicle behavior:

```python
# Get Traffic Manager
tm = client.get_trafficmanager(8000)

# Enable autopilot for a vehicle using the TM port
vehicle.set_autopilot(True, 8000)
```

### Global Traffic Settings

```python
# Set global speed limit percentage (negative = faster)
tm.global_percentage_speed_difference(-20)  # 20% faster than limit

# Set following distance
tm.set_global_distance_to_leading_vehicle(2.5)  # meters

# Enable hybrid physics mode (improves performance)
tm.set_hybrid_physics_mode(True)
tm.set_hybrid_physics_radius(50.0)  # Full physics within 50m
```

### Per-Vehicle Settings

```python
# Set specific vehicle speed
tm.vehicle_percentage_speed_difference(vehicle, 10)  # 10% slower

# Ignore traffic lights
tm.ignore_lights_percentage(vehicle, 100)  # Always ignore

# Ignore other vehicles
tm.ignore_vehicles_percentage(vehicle, 50)  # 50% chance to ignore

# Force lane change
tm.force_lane_change(vehicle, True)  # Change to right lane
```

## Spawning Traffic

### Multiple Vehicles

```python
import random

spawn_points = world.get_map().get_spawn_points()
vehicle_bps = list(bp_lib.filter("vehicle.*"))

vehicles = []
for i, sp in enumerate(spawn_points[:10]):
    bp = random.choice(vehicle_bps)

    # Randomize color
    if bp.has_attribute('color'):
        colors = bp.get_attribute('color').recommended_values
        bp.set_attribute('color', random.choice(colors))

    vehicle = world.try_spawn_actor(bp, sp)
    if vehicle:
        vehicles.append(vehicle)
        vehicle.set_autopilot(True, 8000)

print(f"Spawned {len(vehicles)} vehicles")
```

### Batch Spawning (More Efficient)

```python
batch = []
for i, sp in enumerate(spawn_points[:20]):
    bp = random.choice(vehicle_bps)
    batch.append(carla.command.SpawnActor(bp, sp).then(
        carla.command.SetAutopilot(carla.command.FutureActor, True, 8000)
    ))

results = client.apply_batch_sync(batch)
vehicles = [r.actor_id for r in results if not r.error]
print(f"Spawned {len(vehicles)} vehicles")
```

## Vehicle Physics

### Physics Control

```python
physics = vehicle.get_physics_control()

# Modify physics
physics.mass = 1500  # kg
physics.drag_coefficient = 0.3

# Apply changes
vehicle.apply_physics_control(physics)
```

### Wheel Configuration

```python
physics = vehicle.get_physics_control()

for i, wheel in enumerate(physics.wheels):
    print(f"Wheel {i}:")
    print(f"  Radius: {wheel.radius}")
    print(f"  Max steer angle: {wheel.max_steer_angle}")
```

## Vehicle Lights

```python
# Get current light state
lights = vehicle.get_light_state()

# Set lights
vehicle.set_light_state(carla.VehicleLightState(
    carla.VehicleLightState.Position |
    carla.VehicleLightState.LowBeam
))

# Available light states
# Position, LowBeam, HighBeam, Brake, RightBlinker, LeftBlinker,
# Reverse, Fog, Interior, Special1, Special2
```

## Best Practices

### 1. Use try_spawn_actor

```python
vehicle = world.try_spawn_actor(bp, spawn_point)
if vehicle is None:
    print("Spawn failed, point may be occupied")
```

### 2. Limit Vehicles with Drone Active

```python
max_vehicles = 8 if drone_active else 20
```

### 3. Always Cleanup

```python
actors = []
try:
    # Spawn vehicles
    vehicle = world.spawn_actor(bp, sp)
    actors.append(vehicle)
finally:
    for actor in actors:
        actor.destroy()
```

### 4. Use Traffic Manager for Complex Scenarios

```python
tm = client.get_trafficmanager(8000)
tm.set_synchronous_mode(True)  # If using sync mode
```

## Example: Traffic Simulation

```python
import carla
import random
import time

def create_traffic(client, world, num_vehicles=10):
    bp_lib = world.get_blueprint_library()
    spawn_points = world.get_map().get_spawn_points()
    vehicle_bps = list(bp_lib.filter("vehicle.*"))

    tm = client.get_trafficmanager(8000)
    tm.set_global_distance_to_leading_vehicle(2.5)

    vehicles = []
    random.shuffle(spawn_points)

    for sp in spawn_points[:num_vehicles]:
        bp = random.choice(vehicle_bps)
        if bp.has_attribute('color'):
            bp.set_attribute('color', random.choice(
                bp.get_attribute('color').recommended_values
            ))

        vehicle = world.try_spawn_actor(bp, sp)
        if vehicle:
            vehicle.set_autopilot(True, 8000)
            vehicles.append(vehicle)

    return vehicles

# Usage
vehicles = create_traffic(client, world, num_vehicles=15)
print(f"Created traffic with {len(vehicles)} vehicles")
```

## Next Steps

- [Sensors](../04-sensors/sensors.md) - Attach sensors to vehicles
- [Basic Flight](../../chapter-03-drone-flight/01-basic-flight/basic-flight.md) - Drone control
- [Drone Following](../../chapter-04-air-ground/01-drone-following/drone-following.md) - Air-ground coordination


---

<a id="core-concepts-world-maps"></a>

### World & Maps

> Learn about Carla Air worlds, maps, and how to manage simulation environments.

The CARLA-Air simulation environment consists of a world containing a map, actors (vehicles, sensors, etc.), and environmental settings. Understanding how to interact with the world is fundamental to building effective simulations.

## The World Object

The `world` object is your primary interface for interacting with the simulation:

```python
import carla

client = carla.Client("localhost", 2000)
client.set_timeout(10.0)
world = client.get_world()
```

### Key World Methods

| Method | Description |
|--------|-------------|
| `get_map()` | Returns the current map object |
| `get_blueprint_library()` | Returns blueprints for spawning actors |
| `get_actors()` | Returns all actors currently in the world |
| `spawn_actor()` | Spawns a new actor |
| `try_spawn_actor()` | Spawns actor, returns None on failure |
| `get_weather()` | Returns current weather parameters |
| `set_weather()` | Sets weather parameters |
| `get_spectator()` | Returns the spectator camera |

## Available Maps

CARLA-Air includes several pre-built maps, each designed for different scenarios:

| Map | Description | Best For |
|-----|-------------|----------|
| Town01 | Small town, simple roads | Basic testing |
| Town02 | Residential area, T-junctions | Urban navigation |
| Town03 | Downtown with roundabouts | Complex traffic |
| Town04 | Highway with ramps | High-speed scenarios |
| Town05 | Urban grid, multi-lane | Lane changing |
| Town10HD | HD coastal city | Production demos |

### Launching with Different Maps

```bash
# Launch with specific map
./CarlaAir.sh Town03
```

### Loading Maps at Runtime

```python
# Get available maps
available_maps = client.get_available_maps()
print("Available maps:", available_maps)

# Load a different map
client.load_world('Town03')

# Wait for world to reload
import time
time.sleep(5)
world = client.get_world()
```

## Working with the Map

The map object provides information about the road network and spawn points:

```python
carla_map = world.get_map()

# Get map name
map_name = carla_map.name.split("/")[-1]
print(f"Current map: {map_name}")

# Get spawn points
spawn_points = carla_map.get_spawn_points()
print(f"Available spawn points: {len(spawn_points)}")

# Get waypoints (road network)
waypoint = carla_map.get_waypoint(
    carla.Location(x=0, y=0, z=0),
    project_to_road=True
)
```

## Spawn Points

Spawn points are predefined locations where actors can be safely spawned:

```python
spawn_points = world.get_map().get_spawn_points()

# Each spawn point is a Transform with location and rotation
for i, sp in enumerate(spawn_points[:5]):
    print(f"Point {i}: Location({sp.location.x:.1f}, {sp.location.y:.1f}, {sp.location.z:.1f})")
    print(f"         Rotation(pitch={sp.rotation.pitch:.1f}, yaw={sp.rotation.yaw:.1f})")
```

### Finding Specific Spawn Locations

```python
# Find spawn points near a specific location
target = carla.Location(x=100, y=50, z=0)

def distance(sp):
    loc = sp.location
    return ((loc.x - target.x)**2 + (loc.y - target.y)**2)**0.5

nearby_points = sorted(spawn_points, key=distance)[:5]
print("Nearest spawn points to target:")
for sp in nearby_points:
    print(f"  {sp.location}")
```

## The Blueprint Library

Blueprints define templates for spawnable actors:

```python
bp_lib = world.get_blueprint_library()

# List all blueprints
for bp in bp_lib:
    print(bp.id)

# Filter blueprints
vehicles = bp_lib.filter("vehicle.*")
sensors = bp_lib.filter("sensor.*")
walkers = bp_lib.filter("walker.*")

# Find specific blueprint
tesla = bp_lib.find("vehicle.tesla.model3")
```

### Blueprint Attributes

Many blueprints have configurable attributes:

```python
# Get a vehicle blueprint
vehicle_bp = bp_lib.find("vehicle.audi.a2")

# Check available attributes
for attr in vehicle_bp:
    print(f"  {attr.id}: {attr.type} = {attr.recommended_values}")

# Set color
if vehicle_bp.has_attribute('color'):
    vehicle_bp.set_attribute('color', '255,0,0')  # Red
```

## Transforms and Locations

CARLA uses a coordinate system with:
- X: Forward (positive = east)
- Y: Right (positive = south)
- Z: Up (positive = up)

```python
# Create a location
location = carla.Location(x=100.0, y=50.0, z=0.5)

# Create a rotation (in degrees)
rotation = carla.Rotation(pitch=0.0, yaw=90.0, roll=0.0)

# Combine into transform
transform = carla.Transform(location, rotation)

# Spawn actor at transform
vehicle = world.spawn_actor(vehicle_bp, transform)
```

## The Spectator

The spectator is a special actor representing the viewport:

```python
spectator = world.get_spectator()

# Move spectator to a specific location
spectator.set_transform(carla.Transform(
    carla.Location(x=0, y=0, z=50),
    carla.Rotation(pitch=-90)  # Looking down
))
```

## Managing Actors

### Listing Actors

```python
# Get all actors
all_actors = world.get_actors()
print(f"Total actors: {len(all_actors)}")

# Filter by type
vehicles = world.get_actors().filter("vehicle.*")
sensors = world.get_actors().filter("sensor.*")
walkers = world.get_actors().filter("walker.*")

print(f"Vehicles: {len(vehicles)}")
print(f"Sensors: {len(sensors)}")
print(f"Walkers: {len(walkers)}")
```

### Destroying Actors

```python
# Destroy a specific actor
actor.destroy()

# Destroy multiple actors
for actor in world.get_actors().filter("vehicle.*"):
    actor.destroy()
```

## World Settings

### Tick and Timing

```python
settings = world.get_settings()

# Check if synchronous mode
print(f"Synchronous mode: {settings.synchronous_mode}")
print(f"Fixed delta seconds: {settings.fixed_delta_seconds}")
```

### Synchronous Mode

For deterministic simulations:

```python
settings = world.get_settings()
settings.synchronous_mode = True
settings.fixed_delta_seconds = 0.05  # 20 FPS
world.apply_settings(settings)

try:
    # Your simulation code
    for _ in range(100):
        world.tick()  # Advance simulation
finally:
    # Always restore async mode
    settings.synchronous_mode = False
    world.apply_settings(settings)
```

## Next Steps

- [Weather Control](../02-weather/weather.md) - Change environmental conditions
- [Vehicles & Traffic](../03-vehicles/vehicles.md) - Spawn and control vehicles
- [Sensors](../04-sensors/sensors.md) - Attach sensors to actors


---

<a id="core-concepts-weather"></a>

### Weather & Environment

> Configure weather conditions, time of day, and atmospheric effects in your simulations.

# Weather Control

CARLA-Air provides comprehensive weather control, allowing you to simulate various environmental conditions from clear sunny days to heavy rain, fog, and night scenarios. Weather affects visibility, sensor data, and vehicle behavior.

## Weather Parameters

Weather in CARLA is controlled through the `WeatherParameters` class:

```python
import carla

weather = carla.WeatherParameters(
    cloudiness=0.0,          # 0-100: Cloud coverage
    precipitation=0.0,       # 0-100: Rain intensity
    precipitation_deposits=0.0,  # 0-100: Puddles on ground
    wind_intensity=0.0,      # 0-100: Wind strength
    sun_azimuth_angle=0.0,   # 0-360: Sun horizontal position
    sun_altitude_angle=45.0, # -90 to 90: Sun height (-90=midnight)
    fog_density=0.0,         # 0-100: Fog thickness
    fog_distance=0.0,        # Fog start distance
    fog_falloff=0.0,         # Fog density falloff
    wetness=0.0              # 0-100: Surface wetness
)

world.set_weather(weather)
```

### Parameter Details

| Parameter | Range | Description |
|-----------|-------|-------------|
| `cloudiness` | 0-100 | Cloud cover percentage |
| `precipitation` | 0-100 | Active rainfall intensity |
| `precipitation_deposits` | 0-100 | Standing water/puddles |
| `wind_intensity` | 0-100 | Wind speed affecting particles |
| `sun_azimuth_angle` | 0-360 | Sun position around horizon |
| `sun_altitude_angle` | -90 to 90 | Sun height (negative = below horizon) |
| `fog_density` | 0-100 | Fog opacity |
| `fog_distance` | 0+ | Distance where fog starts |
| `fog_falloff` | 0+ | Rate of fog density increase |
| `wetness` | 0-100 | Road surface wetness |

## Preset Weather Conditions

CARLA provides convenient preset weather conditions:

```python
# Clear conditions
world.set_weather(carla.WeatherParameters.ClearNoon)
world.set_weather(carla.WeatherParameters.ClearSunset)

# Cloudy conditions
world.set_weather(carla.WeatherParameters.CloudyNoon)
world.set_weather(carla.WeatherParameters.CloudySunset)

# Rainy conditions
world.set_weather(carla.WeatherParameters.SoftRainNoon)
world.set_weather(carla.WeatherParameters.SoftRainSunset)
world.set_weather(carla.WeatherParameters.HardRainNoon)
world.set_weather(carla.WeatherParameters.HardRainSunset)

# Wet conditions (after rain)
world.set_weather(carla.WeatherParameters.WetNoon)
world.set_weather(carla.WeatherParameters.WetSunset)
world.set_weather(carla.WeatherParameters.WetCloudyNoon)
world.set_weather(carla.WeatherParameters.WetCloudySunset)

# Midrain conditions
world.set_weather(carla.WeatherParameters.MidRainyNoon)
world.set_weather(carla.WeatherParameters.MidRainSunset)
```

## Custom Weather Examples

### Sunrise Scene

```python
sunrise = carla.WeatherParameters(
    cloudiness=10.0,
    precipitation=0.0,
    precipitation_deposits=0.0,
    wind_intensity=5.0,
    sun_azimuth_angle=90.0,    # East
    sun_altitude_angle=10.0,   # Just above horizon
    fog_density=10.0,          # Light morning mist
    fog_distance=50.0,
    fog_falloff=1.0,
    wetness=20.0               # Morning dew
)
world.set_weather(sunrise)
```

### Dense Fog

```python
fog = carla.WeatherParameters(
    cloudiness=90.0,
    precipitation=0.0,
    precipitation_deposits=0.0,
    wind_intensity=10.0,
    sun_azimuth_angle=0.0,
    sun_altitude_angle=45.0,
    fog_density=80.0,
    fog_distance=10.0,         # Fog starts very close
    fog_falloff=2.0,
    wetness=50.0
)
world.set_weather(fog)
```

### Night Scene

```python
night = carla.WeatherParameters(
    cloudiness=20.0,
    precipitation=0.0,
    precipitation_deposits=0.0,
    wind_intensity=5.0,
    sun_azimuth_angle=0.0,
    sun_altitude_angle=-90.0,  # Sun below horizon
    fog_density=2.0,
    fog_distance=0.0,
    fog_falloff=0.0,
    wetness=0.0
)
world.set_weather(night)
```

### Heavy Storm

```python
storm = carla.WeatherParameters(
    cloudiness=100.0,
    precipitation=100.0,
    precipitation_deposits=100.0,
    wind_intensity=100.0,
    sun_azimuth_angle=0.0,
    sun_altitude_angle=30.0,
    fog_density=30.0,
    fog_distance=20.0,
    fog_falloff=1.0,
    wetness=100.0
)
world.set_weather(storm)
```

## Reading Current Weather

```python
current_weather = world.get_weather()

print(f"Cloudiness: {current_weather.cloudiness}")
print(f"Precipitation: {current_weather.precipitation}")
print(f"Sun altitude: {current_weather.sun_altitude_angle}")
print(f"Fog density: {current_weather.fog_density}")
```

## Dynamic Weather Changes

Create smooth weather transitions:

```python
import time

def interpolate_weather(start, end, t):
    """Interpolate between two weather states (t: 0 to 1)"""
    return carla.WeatherParameters(
        cloudiness=start.cloudiness + (end.cloudiness - start.cloudiness) * t,
        precipitation=start.precipitation + (end.precipitation - start.precipitation) * t,
        precipitation_deposits=start.precipitation_deposits + (end.precipitation_deposits - start.precipitation_deposits) * t,
        wind_intensity=start.wind_intensity + (end.wind_intensity - start.wind_intensity) * t,
        sun_azimuth_angle=start.sun_azimuth_angle + (end.sun_azimuth_angle - start.sun_azimuth_angle) * t,
        sun_altitude_angle=start.sun_altitude_angle + (end.sun_altitude_angle - start.sun_altitude_angle) * t,
        fog_density=start.fog_density + (end.fog_density - start.fog_density) * t,
        fog_distance=start.fog_distance + (end.fog_distance - start.fog_distance) * t,
        fog_falloff=start.fog_falloff + (end.fog_falloff - start.fog_falloff) * t,
        wetness=start.wetness + (end.wetness - start.wetness) * t
    )

# Transition from clear to rainy
start_weather = carla.WeatherParameters.ClearNoon
end_weather = carla.WeatherParameters.HardRainNoon

for i in range(100):
    t = i / 100.0
    weather = interpolate_weather(start_weather, end_weather, t)
    world.set_weather(weather)
    time.sleep(0.1)
```

## Day/Night Cycle

Simulate a day/night cycle by changing sun altitude:

```python
import time
import math

def simulate_day_cycle(world, duration_seconds=60):
    """Simulate one day/night cycle"""
    start_time = time.time()

    while time.time() - start_time < duration_seconds:
        elapsed = time.time() - start_time
        progress = elapsed / duration_seconds

        # Sun altitude: -90 (midnight) to 90 (noon) back to -90
        sun_altitude = 90 * math.sin(progress * 2 * math.pi)

        # Sun azimuth: moves 360 degrees
        sun_azimuth = progress * 360

        weather = carla.WeatherParameters(
            cloudiness=20.0,
            sun_azimuth_angle=sun_azimuth,
            sun_altitude_angle=sun_altitude
        )
        world.set_weather(weather)
        time.sleep(0.1)
```

## Weather Effects on Sensors

Different weather conditions affect sensor outputs:

| Condition | RGB Camera | Depth Camera | LiDAR |
|-----------|------------|--------------|-------|
| Rain | Droplets, reduced visibility | Noise | Point dropout |
| Fog | Reduced visibility | Increased noise | Reduced range |
| Night | Dark, headlights needed | No effect | No effect |
| Wet roads | Reflections | Reflections | Minor effect |

## Best Practices

1. **Start with presets**: Use built-in presets as starting points
2. **Gradual transitions**: Avoid abrupt weather changes
3. **Consider sensors**: Test how weather affects your sensor data
4. **Save configurations**: Store custom weather as constants

```python
# Define weather configurations
WEATHER_CONFIGS = {
    'sunny': carla.WeatherParameters.ClearNoon,
    'rainy': carla.WeatherParameters.HardRainNoon,
    'foggy': carla.WeatherParameters(fog_density=80, fog_distance=10),
    'night': carla.WeatherParameters(sun_altitude_angle=-90),
}

# Use configurations
world.set_weather(WEATHER_CONFIGS['rainy'])
```

## Next Steps

- [Vehicles & Traffic](../03-vehicles/vehicles.md) - Spawn and control vehicles
- [Sensors](../04-sensors/sensors.md) - Attach sensors to actors
- [Basic Flight](../../chapter-03-drone-flight/01-basic-flight/basic-flight.md) - Drone control


---

<a id="core-concepts-traffic"></a>

### Traffic & Pedestrians

> Create realistic traffic scenarios with NPC vehicles, pedestrians, and the traffic manager.

Create realistic traffic scenarios with NPC vehicles, pedestrians, and the traffic manager.

## Traffic Manager

```python
import carla

client = carla.Client('localhost', 2000)
world = client.get_world()

# Get Traffic Manager
tm = client.get_trafficmanager(8000)  # Default port

# Global settings
tm.set_global_distance_to_leading_vehicle(2.5)  # meters
tm.set_synchronous_mode(True)
tm.set_random_device_seed(42)  # For reproducibility

# Enable hybrid physics mode (better performance)
tm.set_hybrid_physics_mode(True)
tm.set_hybrid_physics_radius(50.0)  # meters
```

## Spawning Traffic Vehicles

```python
import carla
import random

client = carla.Client('localhost', 2000)
world = client.get_world()
bp_lib = world.get_blueprint_library()
spawn_points = world.get_map().get_spawn_points()

# Spawn multiple vehicles
num_vehicles = 30
vehicles = []
vehicle_bps = bp_lib.filter('vehicle.*')

for i in range(num_vehicles):
    bp = random.choice(vehicle_bps)

    # Set random color if available
    if bp.has_attribute('color'):
        color = random.choice(bp.get_attribute('color').recommended_values)
        bp.set_attribute('color', color)

    spawn_point = random.choice(spawn_points)
    vehicle = world.try_spawn_actor(bp, spawn_point)

    if vehicle:
        vehicle.set_autopilot(True)
        vehicles.append(vehicle)

print(f"Spawned {len(vehicles)} vehicles")
```

## Per-Vehicle Traffic Settings

```python
tm = client.get_trafficmanager()

# Set behavior for specific vehicle
tm.ignore_lights_percentage(vehicle, 50)  # 50% chance to run red lights
tm.ignore_signs_percentage(vehicle, 0)    # Always obey signs
tm.ignore_walkers_percentage(vehicle, 0)  # Always avoid pedestrians

# Speed control
tm.vehicle_percentage_speed_difference(vehicle, -20)  # 20% faster than limit

# Lane change behavior
tm.auto_lane_change(vehicle, True)
tm.distance_to_leading_vehicle(vehicle, 3.0)
```

## Spawning Pedestrians

```python
import carla
import random

client = carla.Client('localhost', 2000)
world = client.get_world()
bp_lib = world.get_blueprint_library()

# Get walker blueprints
walker_bps = bp_lib.filter('walker.pedestrian.*')

# Get spawn locations for walkers
spawn_points = []
for i in range(50):
    loc = world.get_random_location_from_navigation()
    if loc:
        spawn_points.append(carla.Transform(loc))

# Spawn walkers
walkers = []
for spawn_point in spawn_points:
    bp = random.choice(walker_bps)
    walker = world.try_spawn_actor(bp, spawn_point)
    if walker:
        walkers.append(walker)

print(f"Spawned {len(walkers)} pedestrians")
```

## Traffic Lights

```python
import carla

# Get all traffic lights
traffic_lights = world.get_actors().filter('traffic.traffic_light')

for tl in traffic_lights:
    # Get current state
    state = tl.get_state()
    print(f"Light {tl.id}: {state}")

    # Set state manually
    tl.set_state(carla.TrafficLightState.Green)

    # Set timing
    tl.set_green_time(10.0)
    tl.set_yellow_time(3.0)
    tl.set_red_time(15.0)
```

## Cleanup Traffic

```python
# Destroy all vehicles
for actor in world.get_actors().filter('vehicle.*'):
    actor.destroy()

# Destroy all walkers
for actor in world.get_actors().filter('walker.*'):
    actor.destroy()
```

## Next Steps

- [Vehicles](../02-vehicles/vehicles.md) - Vehicle control details
- [World & Maps](../03-world-maps/world-maps.md) - Map navigation


---

<a id="core-concepts"></a>

## Core Concepts

> Understanding the fundamental concepts of Carla Air will help you build more effective autonomous systems. This section covers the key components and how they work together.

Understanding the fundamental concepts of Carla Air will help you build more effective autonomous systems. This section covers the key components and how they work together.


---

<a id="api-reference-client"></a>

### Client API

> The Client class is your entry point to the Carla Air simulator. It manages the connection to the server and provides access to world management, traffic manager, and server settings.

The Client class is your entry point to the CARLA-Air simulator. It manages connections to both CARLA and AirSim servers.

## CARLA Client

### Connection

```python
import carla

# Connect to CARLA server
client = carla.Client(host='localhost', port=2000)

# Set timeout for blocking operations (seconds)
client.set_timeout(10.0)

# Get world reference
world = client.get_world()
```

### Version Information

```python
# Check versions
print(f"Server: {client.get_server_version()}")
print(f"Client: {client.get_client_version()}")
```

### Map Management

```python
# Get current map name
map_name = world.get_map().name
print(f"Current map: {map_name}")

# List available maps
maps = client.get_available_maps()
print(f"Available maps: {maps}")

# Load different map
client.load_world('Town03')

# Reload current map
client.reload_world()
```

### Traffic Manager

```python
# Get Traffic Manager on port 8000
tm = client.get_trafficmanager(8000)

# Configure TM
tm.set_global_distance_to_leading_vehicle(2.5)
tm.set_synchronous_mode(True)

# Set random seed for reproducibility
tm.set_random_device_seed(42)
```

## AirSim Client

### Connection

```python
import airsim

# Connect to AirSim
air_client = airsim.MultirotorClient(ip='127.0.0.1', port=41451)

# Confirm connection
air_client.confirmConnection()

# Enable API control
air_client.enableApiControl(True)

# Arm the drone
air_client.armDisarm(True)
```

### Connection Verification

```python
# Check if connected
is_connected = air_client.ping()
print(f"Connected: {is_connected}")

# Get connection info
air_client.confirmConnection()  # Prints version info
```

### Control Release

```python
# Release control (important for cleanup)
air_client.armDisarm(False)
air_client.enableApiControl(False)
```

## Complete Dual-API Connection

```python
import carla
import airsim

def connect_carla_air():
    """Establish connections to both APIs."""
    # CARLA connection
    carla_client = carla.Client('localhost', 2000)
    carla_client.set_timeout(10.0)
    world = carla_client.get_world()
    bp_lib = world.get_blueprint_library()

    # AirSim connection
    air_client = airsim.MultirotorClient(port=41451)
    air_client.confirmConnection()
    air_client.enableApiControl(True)
    air_client.armDisarm(True)

    print(f"CARLA: {world.get_map().name}")
    print("AirSim: Connected")

    return carla_client, world, bp_lib, air_client
```

## Error Handling

```python
import carla

try:
    client = carla.Client('localhost', 2000)
    client.set_timeout(5.0)
    world = client.get_world()
except RuntimeError as e:
    print(f"Failed to connect: {e}")
    # Handle connection failure
```

## Next Steps

- [Drone API](../02-drone-api/drone-api.md) - Drone control methods
- [Vehicle API](../03-vehicle-api/vehicle-api.md) - Vehicle control


---

<a id="api-reference-drone"></a>

### Drone API Reference

> Carla Air uses AirSim's Python API for drone control. This reference covers the most commonly used methods for multirotor drones.

CARLA-Air uses AirSim's Python API for drone control. This reference covers the most commonly used methods for multirotor drones.

## Initialization

```python
import airsim

client = airsim.MultirotorClient(port=41451)
client.confirmConnection()
client.enableApiControl(True)
client.armDisarm(True)

# Takeoff
client.takeoffAsync().join()

# ... flight operations ...

# Land and cleanup
client.landAsync().join()
client.armDisarm(False)
client.enableApiControl(False)
```

## Movement Commands

### Position Control

```python
# Move to absolute position in NED coordinates
# NED: x=North, y=East, z=Down (negative z = up)
client.moveToPositionAsync(
    x=10,      # 10 meters north
    y=5,       # 5 meters east
    z=-20,     # 20 meters altitude
    velocity=5 # 5 m/s
).join()

# With yaw control
client.moveToPositionAsync(
    x=10, y=5, z=-20, velocity=5,
    yaw_mode=airsim.YawMode(is_rate=False, yaw_or_rate=90)  # Face east
).join()
```

### Velocity Control

```python
# Move with velocity for duration
client.moveByVelocityAsync(
    vx=5,        # 5 m/s north
    vy=0,        # No east movement
    vz=0,        # Maintain altitude
    duration=2   # For 2 seconds
).join()

# Move in body frame (relative to drone orientation)
client.moveByVelocityBodyFrameAsync(
    vx=5,        # Forward
    vy=2,        # Right
    vz=0,        # Maintain altitude
    duration=2
).join()
```

### Altitude Control

```python
# Move to specific altitude
client.moveToZAsync(z=-30, velocity=3).join()  # Go to 30m altitude
```

### Hover

```python
# Stop and hover at current position
client.hoverAsync().join()
```

## State Retrieval

```python
# Get current state
state = client.getMultirotorState()

# Position (NED)
pos = state.kinematics_estimated.position
print(f"Position: x={pos.x_val}, y={pos.y_val}, z={pos.z_val}")

# Velocity
vel = state.kinematics_estimated.linear_velocity
print(f"Velocity: vx={vel.x_val}, vy={vel.y_val}, vz={vel.z_val}")

# Orientation (quaternion)
orient = state.kinematics_estimated.orientation
print(f"Orientation: w={orient.w_val}, x={orient.x_val}")

# GPS data
gps = client.getGpsData()
print(f"GPS: lat={gps.gnss.geo_point.latitude}")
```

## Camera Control

```python
# Get camera image
responses = client.simGetImages([
    airsim.ImageRequest("front_center", airsim.ImageType.Scene, False, False)
])

# Process image
if responses:
    response = responses[0]
    img_rgb = np.frombuffer(response.image_data_uint8, dtype=np.uint8)
    img_rgb = img_rgb.reshape(response.height, response.width, 3)

# Get depth image
depth_responses = client.simGetImages([
    airsim.ImageRequest("front_center", airsim.ImageType.DepthPerspective, True)
])
```

## Async Operations

```python
# All movement commands return futures
future = client.moveToPositionAsync(10, 0, -20, 5)

# Check if complete
if future.done():
    print("Movement complete")

# Wait for completion
future.join()

# Chain operations
client.takeoffAsync().join()
client.moveToPositionAsync(10, 0, -20, 5).join()
client.moveToPositionAsync(10, 10, -20, 5).join()
client.landAsync().join()
```

## Pose Control

```python
import math

# Directly set drone pose (teleport)
pose = airsim.Pose(
    airsim.Vector3r(x=10, y=5, z=-20),
    airsim.to_quaternion(
        pitch=math.radians(0),
        roll=math.radians(0),
        yaw=math.radians(90)
    )
)
client.simSetVehiclePose(pose, ignore_collision=True)
```

## Low-Level Control

```python
import math

# Direct control with angular rates
client.moveByAngleRatesThrottleAsync(
    roll_rate=0,
    pitch_rate=math.radians(10),  # 10 deg/s pitch
    yaw_rate=0,
    throttle=0.6,
    duration=1
).join()
```

## Next Steps

- [Vehicle API](../03-vehicle-api/vehicle-api.md) - Ground vehicle control
- [Sensor API](../04-sensor-api/sensor-api.md) - Sensor configuration


---

<a id="api-reference-vehicle"></a>

### Vehicle API

The Vehicle class provides control over ground vehicles in the CARLA simulation.

## Spawning Vehicles

```python
import carla

client = carla.Client('localhost', 2000)
world = client.get_world()
bp_lib = world.get_blueprint_library()

# Find vehicle blueprint
vehicle_bp = bp_lib.find('vehicle.tesla.model3')

# Get spawn points
spawn_points = world.get_map().get_spawn_points()
spawn_point = spawn_points[0]

# Spawn vehicle
vehicle = world.spawn_actor(vehicle_bp, spawn_point)

# Or use try_spawn_actor (returns None on failure)
vehicle = world.try_spawn_actor(vehicle_bp, spawn_point)
```

## Manual Control

```python
# Apply control
control = carla.VehicleControl(
    throttle=0.5,      # 0.0 to 1.0
    steer=0.0,         # -1.0 (left) to 1.0 (right)
    brake=0.0,         # 0.0 to 1.0
    hand_brake=False,
    reverse=False,
    manual_gear_shift=False,
    gear=0
)
vehicle.apply_control(control)

# Get current control state
current_control = vehicle.get_control()
```

## Autopilot

```python
# Enable autopilot (uses Traffic Manager)
vehicle.set_autopilot(True)

# With specific Traffic Manager port
vehicle.set_autopilot(True, tm_port=8000)

# Configure Traffic Manager behavior
tm = client.get_trafficmanager(8000)
tm.vehicle_percentage_speed_difference(vehicle, 10)  # 10% slower
tm.auto_lane_change(vehicle, True)
tm.distance_to_leading_vehicle(vehicle, 2.0)
```

## Transform & Location

```python
# Get transform (location + rotation)
transform = vehicle.get_transform()
location = transform.location
rotation = transform.rotation

print(f"Position: ({location.x}, {location.y}, {location.z})")
print(f"Rotation: yaw={rotation.yaw}")

# Set transform (teleport)
new_transform = carla.Transform(
    carla.Location(x=100, y=-50, z=2),
    carla.Rotation(yaw=90)
)
vehicle.set_transform(new_transform)

# Get/set location only
loc = vehicle.get_location()
vehicle.set_location(carla.Location(x=100, y=-50, z=2))
```

## Velocity & Physics

```python
import math

# Get velocity (m/s)
velocity = vehicle.get_velocity()
speed_ms = math.sqrt(velocity.x**2 + velocity.y**2 + velocity.z**2)
speed_kmh = speed_ms * 3.6

print(f"Speed: {speed_kmh:.1f} km/h")

# Get acceleration
accel = vehicle.get_acceleration()

# Set target velocity
vehicle.set_target_velocity(carla.Vector3D(x=10, y=0, z=0))

# Enable constant velocity
vehicle.enable_constant_velocity(carla.Vector3D(x=10, y=0, z=0))
```

## Physics Control

```python
# Get physics control
physics = vehicle.get_physics_control()

print(f"Mass: {physics.mass} kg")
print(f"Max RPM: {physics.max_rpm}")

# Modify physics
physics.mass = 1500
physics.drag_coefficient = 0.3
vehicle.apply_physics_control(physics)

# Enable/disable physics
vehicle.set_simulate_physics(True)
```

## Lights

```python
# Get current light state
light_state = vehicle.get_light_state()

# Set lights
vehicle.set_light_state(carla.VehicleLightState(
    carla.VehicleLightState.Position |
    carla.VehicleLightState.LowBeam |
    carla.VehicleLightState.Brake
))
```

## Cleanup

```python
# Destroy vehicle
vehicle.destroy()
```

## Next Steps

- [Sensor API](../04-sensor-api/sensor-api.md) - Attach sensors
- [World API](../05-world-api/world-api.md) - World management


---

<a id="api-reference-sensor"></a>

### Sensor API

CARLA-Air provides a comprehensive suite of sensors for perception and localization.

## RGB Camera

```python
import carla
import numpy as np

# Create camera blueprint
bp_lib = world.get_blueprint_library()
camera_bp = bp_lib.find('sensor.camera.rgb')

# Set attributes
camera_bp.set_attribute('image_size_x', '1920')
camera_bp.set_attribute('image_size_y', '1080')
camera_bp.set_attribute('fov', '90')
camera_bp.set_attribute('sensor_tick', '0.05')  # 20 FPS

# Spawn attached to vehicle
camera_transform = carla.Transform(
    carla.Location(x=1.5, z=2.4),
    carla.Rotation(pitch=-15)
)
camera = world.spawn_actor(camera_bp, camera_transform, attach_to=vehicle)

# Process callback
def process_image(image):
    array = np.frombuffer(image.raw_data, dtype=np.uint8)
    array = array.reshape((image.height, image.width, 4))  # BGRA
    rgb = array[:, :, :3][:, :, ::-1]  # Convert to RGB

camera.listen(process_image)
```

## Depth Camera

```python
depth_bp = bp_lib.find('sensor.camera.depth')
depth_bp.set_attribute('image_size_x', '1920')
depth_bp.set_attribute('image_size_y', '1080')

depth_camera = world.spawn_actor(depth_bp, camera_transform, attach_to=vehicle)

def process_depth(image):
    array = np.frombuffer(image.raw_data, dtype=np.uint8)
    array = array.reshape((image.height, image.width, 4))

    # Decode depth (in meters)
    r = array[:, :, 2].astype(np.float32)
    g = array[:, :, 1].astype(np.float32)
    b = array[:, :, 0].astype(np.float32)
    depth = (r + g * 256 + b * 256 * 256) / (256**3 - 1) * 1000

depth_camera.listen(process_depth)
```

## Semantic Segmentation

```python
seg_bp = bp_lib.find('sensor.camera.semantic_segmentation')
seg_bp.set_attribute('image_size_x', '1280')
seg_bp.set_attribute('image_size_y', '720')

seg_camera = world.spawn_actor(seg_bp, camera_transform, attach_to=vehicle)

def process_segmentation(image):
    array = np.frombuffer(image.raw_data, dtype=np.uint8)
    array = array.reshape((image.height, image.width, 4))
    # Red channel contains class ID
    labels = array[:, :, 2]

seg_camera.listen(process_segmentation)
```

## LiDAR

```python
lidar_bp = bp_lib.find('sensor.lidar.ray_cast')

# LiDAR attributes
lidar_bp.set_attribute('channels', '64')
lidar_bp.set_attribute('range', '100')
lidar_bp.set_attribute('points_per_second', '1200000')
lidar_bp.set_attribute('rotation_frequency', '20')
lidar_bp.set_attribute('upper_fov', '15')
lidar_bp.set_attribute('lower_fov', '-25')

lidar_transform = carla.Transform(carla.Location(z=2.5))
lidar = world.spawn_actor(lidar_bp, lidar_transform, attach_to=vehicle)

def process_lidar(point_cloud):
    data = np.frombuffer(point_cloud.raw_data, dtype=np.float32)
    points = data.reshape(-1, 4)  # x, y, z, intensity

lidar.listen(process_lidar)
```

## IMU

```python
imu_bp = bp_lib.find('sensor.other.imu')
imu = world.spawn_actor(imu_bp, carla.Transform(), attach_to=vehicle)

def process_imu(imu_data):
    # Accelerometer (m/s^2)
    accel = imu_data.accelerometer
    # Gyroscope (rad/s)
    gyro = imu_data.gyroscope
    # Compass (radians)
    compass = imu_data.compass

imu.listen(process_imu)
```

## GNSS

```python
gnss_bp = bp_lib.find('sensor.other.gnss')
gnss = world.spawn_actor(gnss_bp, carla.Transform(), attach_to=vehicle)

def process_gnss(gnss_data):
    print(f"Lat: {gnss_data.latitude}")
    print(f"Lon: {gnss_data.longitude}")
    print(f"Alt: {gnss_data.altitude}")

gnss.listen(process_gnss)
```

## Collision Sensor

```python
collision_bp = bp_lib.find('sensor.other.collision')
collision = world.spawn_actor(collision_bp, carla.Transform(), attach_to=vehicle)

def on_collision(event):
    other_actor = event.other_actor
    impulse = event.normal_impulse
    intensity = (impulse.x**2 + impulse.y**2 + impulse.z**2) ** 0.5
    print(f"Collision with {other_actor.type_id}, intensity: {intensity}")

collision.listen(on_collision)
```

## Sensor Cleanup

```python
# Stop listening and destroy
camera.stop()
camera.destroy()

# Or destroy all sensors
for actor in world.get_actors().filter('sensor.*'):
    actor.stop()
    actor.destroy()
```

## Next Steps

- [World API](../05-world-api/world-api.md) - World management
- [ROS Integration](../06-ros-integration/ros-integration.md) - ROS bridge


---

<a id="api-reference-world"></a>

### World API

The World class represents the simulation environment and provides methods for managing actors, weather, and simulation settings.

## Getting World Reference

```python
import carla

client = carla.Client('localhost', 2000)
world = client.get_world()
```

## World Settings

```python
# Get current settings
settings = world.get_settings()

# Configure synchronous mode
settings.synchronous_mode = True
settings.fixed_delta_seconds = 0.05  # 20 FPS
settings.no_rendering_mode = False
settings.substepping = True
settings.max_substep_delta_time = 0.01
settings.max_substeps = 10

# Apply settings
world.apply_settings(settings)

# Tick the world (required in sync mode)
world.tick()

# Reset to async mode
settings.synchronous_mode = False
settings.fixed_delta_seconds = None
world.apply_settings(settings)
```

## Blueprint Library

```python
bp_lib = world.get_blueprint_library()

# Find specific blueprint
vehicle_bp = bp_lib.find('vehicle.tesla.model3')

# Filter blueprints
all_vehicles = bp_lib.filter('vehicle.*')
all_sensors = bp_lib.filter('sensor.*')

# List all vehicle blueprints
for bp in bp_lib.filter('vehicle.*'):
    print(bp.id)
```

## Spawning Actors

```python
# Get spawn points
spawn_points = world.get_map().get_spawn_points()
spawn_transform = spawn_points[0]

# Spawn actor
vehicle = world.spawn_actor(vehicle_bp, spawn_transform)

# Spawn attached to another actor
camera_bp = bp_lib.find('sensor.camera.rgb')
camera_transform = carla.Transform(carla.Location(z=2))
camera = world.spawn_actor(camera_bp, camera_transform, attach_to=vehicle)

# Try spawn (returns None on failure)
vehicle2 = world.try_spawn_actor(vehicle_bp, spawn_points[1])
```

## Querying Actors

```python
# Get all actors
all_actors = world.get_actors()
print(f"Total actors: {len(all_actors)}")

# Filter by type
vehicles = world.get_actors().filter('vehicle.*')
walkers = world.get_actors().filter('walker.*')
sensors = world.get_actors().filter('sensor.*')
traffic_lights = world.get_actors().filter('traffic.traffic_light')

# Get specific actor by ID
actor = world.get_actor(actor_id)
```

## Weather Control

```python
# Get current weather
weather = world.get_weather()

# Set weather parameters
weather = carla.WeatherParameters(
    cloudiness=80.0,
    precipitation=30.0,
    sun_altitude_angle=45.0,
    fog_density=10.0
)
world.set_weather(weather)

# Use presets
world.set_weather(carla.WeatherParameters.ClearNoon)
world.set_weather(carla.WeatherParameters.HardRainNoon)
world.set_weather(carla.WeatherParameters.CloudySunset)
```

## World Snapshot

```python
# Get current snapshot (frozen state)
snapshot = world.get_snapshot()

print(f"Frame: {snapshot.frame}")
print(f"Timestamp: {snapshot.timestamp.elapsed_seconds}")

# Iterate actor snapshots
for actor_snapshot in snapshot:
    transform = actor_snapshot.get_transform()
    velocity = actor_snapshot.get_velocity()
```

## Debug Drawing

```python
debug = world.debug

# Draw point
debug.draw_point(
    carla.Location(x=0, y=0, z=2),
    size=0.1,
    color=carla.Color(255, 0, 0),
    life_time=5.0
)

# Draw line
debug.draw_line(
    carla.Location(x=0, y=0, z=2),
    carla.Location(x=10, y=0, z=2),
    thickness=0.1,
    color=carla.Color(0, 255, 0),
    life_time=5.0
)

# Draw string
debug.draw_string(
    carla.Location(x=0, y=0, z=3),
    "Hello World",
    color=carla.Color(255, 255, 255),
    life_time=5.0
)
```

## Event Callbacks

```python
# Register callback for each tick
def on_tick(snapshot):
    print(f"Frame {snapshot.frame}")

callback_id = world.on_tick(on_tick)

# Remove callback
world.remove_on_tick(callback_id)
```

## Next Steps

- [ROS Integration](../06-ros-integration/ros-integration.md) - ROS bridge
- [Client API](../01-client-api/client-api.md) - Client management


---

<a id="api-reference-ros"></a>

### ROS Integration

CARLA-Air provides integration with ROS2, allowing you to use standard robotics tools with the simulator.

## Overview

The CARLA ROS2 bridge publishes sensor data and accepts control commands through standard ROS2 topics.

## Installation

```bash
# Install ROS2 Humble (Ubuntu 22.04)
sudo apt install ros-humble-desktop

# Install CARLA ROS2 bridge
sudo apt install ros-humble-carla-ros-bridge

# Source ROS2
source /opt/ros/humble/setup.bash
```

## Launching the Bridge

```bash
# Start CarlaAir first
./CarlaAir.sh

# In another terminal, launch the ROS2 bridge
ros2 launch carla_ros_bridge carla_ros_bridge.launch.py

# With custom parameters
ros2 launch carla_ros_bridge carla_ros_bridge.launch.py \
    host:=localhost \
    port:=2000 \
    synchronous_mode:=True \
    fixed_delta_seconds:=0.05
```

## Published Topics

| Topic | Type | Description |
|-------|------|-------------|
| `/carla/ego_vehicle/rgb_front/image` | sensor_msgs/Image | RGB camera |
| `/carla/ego_vehicle/depth_front/image` | sensor_msgs/Image | Depth camera |
| `/carla/ego_vehicle/lidar` | sensor_msgs/PointCloud2 | LiDAR |
| `/carla/ego_vehicle/imu` | sensor_msgs/Imu | IMU data |
| `/carla/ego_vehicle/gnss` | sensor_msgs/NavSatFix | GPS |
| `/carla/ego_vehicle/odometry` | nav_msgs/Odometry | Odometry |

## Subscribed Topics (Control)

| Topic | Type | Description |
|-------|------|-------------|
| `/carla/ego_vehicle/vehicle_control_cmd` | CarlaEgoVehicleControl | Vehicle control |

## Subscribe to Camera

```python
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image
from cv_bridge import CvBridge
import cv2

class CameraSubscriber(Node):
    def __init__(self):
        super().__init__('camera_subscriber')
        self.subscription = self.create_subscription(
            Image,
            '/carla/ego_vehicle/rgb_front/image',
            self.image_callback,
            10
        )
        self.bridge = CvBridge()

    def image_callback(self, msg):
        cv_image = self.bridge.imgmsg_to_cv2(msg, 'bgr8')
        cv2.imshow('Camera', cv_image)
        cv2.waitKey(1)

def main():
    rclpy.init()
    node = CameraSubscriber()
    rclpy.spin(node)

if __name__ == '__main__':
    main()
```

## Publish Vehicle Control

```python
import rclpy
from rclpy.node import Node
from carla_msgs.msg import CarlaEgoVehicleControl

class VehicleController(Node):
    def __init__(self):
        super().__init__('vehicle_controller')
        self.publisher = self.create_publisher(
            CarlaEgoVehicleControl,
            '/carla/ego_vehicle/vehicle_control_cmd',
            10
        )
        self.timer = self.create_timer(0.05, self.control_callback)

    def control_callback(self):
        msg = CarlaEgoVehicleControl()
        msg.throttle = 0.5
        msg.steer = 0.0
        msg.brake = 0.0
        msg.hand_brake = False
        msg.reverse = False
        self.publisher.publish(msg)

def main():
    rclpy.init()
    node = VehicleController()
    rclpy.spin(node)

if __name__ == '__main__':
    main()
```

## TF Frames

The ROS2 bridge publishes TF transforms for all actors:

```bash
# View TF tree
ros2 run tf2_tools view_frames

# Echo specific transform
ros2 run tf2_ros tf2_echo map ego_vehicle
```

## Visualization with RViz2

```bash
# Launch RViz2 with CARLA config
ros2 launch carla_ros_bridge carla_ros_bridge_with_rviz.launch.py
```

## Note

ROS integration requires the CARLA ROS2 bridge package which is separate from the main CARLA-Air installation. Refer to the official CARLA ROS bridge documentation for detailed setup instructions.

## Next Steps

- [Client API](../01-client-api/client-api.md) - Python API basics
- [Tutorials](../../chapter-04-tutorials/01-sensors-tutorial/sensors-tutorial.md) - Hands-on examples


---

<a id="api-reference"></a>

## API Reference

> Complete reference documentation for the Carla Air Python API. This section provides detailed information about all classes, methods, and parameters.

Complete reference documentation for the Carla Air Python API. This section provides detailed information about all classes, methods, and parameters.


---

<a id="tutorials-sensors"></a>

### Sensors

> Carla Air provides a comprehensive suite of sensors for perception and localization. This guide covers all available sensors and their configuration options.

# Sensors Tutorial

This hands-on tutorial demonstrates collecting synchronized sensor data from multiple sensors in CARLA-Air.

## Overview

We'll create a multi-sensor setup that collects:
- RGB camera images
- Depth camera data
- Semantic segmentation
- IMU readings

## Setup

```python
import carla
import numpy as np
import queue
import cv2
import os

# Connect
client = carla.Client('localhost', 2000)
client.set_timeout(10.0)
world = client.get_world()
bp_lib = world.get_blueprint_library()
```

## Enable Synchronous Mode

For synchronized sensor data:

```python
settings = world.get_settings()
settings.synchronous_mode = True
settings.fixed_delta_seconds = 0.05  # 20 FPS
world.apply_settings(settings)
```

## Spawn Vehicle and Sensors

```python
# Spawn ego vehicle
vehicle_bp = bp_lib.find('vehicle.tesla.model3')
spawn_point = world.get_map().get_spawn_points()[0]
vehicle = world.spawn_actor(vehicle_bp, spawn_point)
vehicle.set_autopilot(True)

# Sensor queue
sensor_queue = queue.Queue()

def sensor_callback(data, sensor_name):
    sensor_queue.put((sensor_name, data))

# Camera transform
camera_transform = carla.Transform(carla.Location(x=1.5, z=2.4))

# RGB Camera
camera_bp = bp_lib.find('sensor.camera.rgb')
camera_bp.set_attribute('image_size_x', '1280')
camera_bp.set_attribute('image_size_y', '720')
camera = world.spawn_actor(camera_bp, camera_transform, attach_to=vehicle)
camera.listen(lambda data: sensor_callback(data, 'rgb'))

# Depth Camera
depth_bp = bp_lib.find('sensor.camera.depth')
depth_bp.set_attribute('image_size_x', '1280')
depth_bp.set_attribute('image_size_y', '720')
depth_camera = world.spawn_actor(depth_bp, camera_transform, attach_to=vehicle)
depth_camera.listen(lambda data: sensor_callback(data, 'depth'))

# Semantic Segmentation
seg_bp = bp_lib.find('sensor.camera.semantic_segmentation')
seg_bp.set_attribute('image_size_x', '1280')
seg_bp.set_attribute('image_size_y', '720')
seg_camera = world.spawn_actor(seg_bp, camera_transform, attach_to=vehicle)
seg_camera.listen(lambda data: sensor_callback(data, 'segmentation'))

# IMU
imu_bp = bp_lib.find('sensor.other.imu')
imu = world.spawn_actor(imu_bp, carla.Transform(), attach_to=vehicle)
imu.listen(lambda data: sensor_callback(data, 'imu'))
```

## Collect Synchronized Data

```python
os.makedirs('output/rgb', exist_ok=True)
os.makedirs('output/depth', exist_ok=True)
os.makedirs('output/segmentation', exist_ok=True)

frame_count = 0
num_frames = 100

try:
    while frame_count < num_frames:
        # Advance simulation
        world.tick()

        # Collect all sensor data
        frame_data = {}
        expected_sensors = {'rgb', 'depth', 'segmentation', 'imu'}

        while len(frame_data) < len(expected_sensors):
            sensor_name, data = sensor_queue.get(timeout=2.0)
            frame_data[sensor_name] = data

        # Process RGB
        rgb_array = np.frombuffer(frame_data['rgb'].raw_data, dtype=np.uint8)
        rgb_array = rgb_array.reshape((720, 1280, 4))[:, :, :3]
        cv2.imwrite(f'output/rgb/{frame_count:06d}.png', rgb_array)

        # Process Depth
        depth_array = np.frombuffer(frame_data['depth'].raw_data, dtype=np.uint8)
        depth_array = depth_array.reshape((720, 1280, 4))
        cv2.imwrite(f'output/depth/{frame_count:06d}.png', depth_array)

        # Process Segmentation
        seg_array = np.frombuffer(frame_data['segmentation'].raw_data, dtype=np.uint8)
        seg_array = seg_array.reshape((720, 1280, 4))
        cv2.imwrite(f'output/segmentation/{frame_count:06d}.png', seg_array)

        # IMU data
        imu_data = frame_data['imu']
        print(f"Frame {frame_count}: IMU accel=({imu_data.accelerometer.x:.2f}, "
              f"{imu_data.accelerometer.y:.2f}, {imu_data.accelerometer.z:.2f})")

        frame_count += 1

finally:
    # Cleanup
    camera.stop()
    depth_camera.stop()
    seg_camera.stop()
    imu.stop()

    camera.destroy()
    depth_camera.destroy()
    seg_camera.destroy()
    imu.destroy()
    vehicle.destroy()

    settings.synchronous_mode = False
    world.apply_settings(settings)

print(f"Collected {frame_count} frames")
```

## Output Structure

```
output/
├── rgb/
│   ├── 000000.png
│   ├── 000001.png
│   └── ...
├── depth/
│   ├── 000000.png
│   └── ...
└── segmentation/
    ├── 000000.png
    └── ...
```

## Next Steps

- [Drone Navigation](../02-drone-navigation/drone-navigation.md) - Autonomous flight
- [Data Collection](../03-data-collection/data-collection.md) - ML dataset creation


---

<a id="tutorials-drone-navigation"></a>

### Drone Navigation

> Learn how to build an autonomous drone navigation system with waypoint following, camera control, and basic obstacle awareness using AirSim in Carla Air.

# Drone Navigation Tutorial

Learn how to build an autonomous drone navigation system with waypoint following and basic obstacle awareness.

## Basic Waypoint Navigation

```python
import airsim
import time

client = airsim.MultirotorClient(port=41451)
client.confirmConnection()
client.enableApiControl(True)
client.armDisarm(True)

# Define waypoints (x, y, z in NED)
waypoints = [
    (0, 0, -20),     # Start position
    (50, 0, -20),    # Forward
    (50, 50, -20),   # Right
    (0, 50, -20),    # Back
    (0, 0, -20),     # Return
]

# Takeoff
print("Taking off...")
client.takeoffAsync().join()
time.sleep(2)

# Navigate
for i, (x, y, z) in enumerate(waypoints):
    print(f"Flying to waypoint {i+1}: ({x}, {y}, {z})")
    client.moveToPositionAsync(x, y, z, velocity=5).join()
    time.sleep(1)

# Land
print("Landing...")
client.landAsync().join()
client.armDisarm(False)
client.enableApiControl(False)
```

## Smooth Path Following

```python
import airsim
import numpy as np

def generate_circular_path(center, radius, altitude, num_points=36):
    """Generate circular path waypoints."""
    waypoints = []
    for i in range(num_points):
        angle = 2 * np.pi * i / num_points
        x = center[0] + radius * np.cos(angle)
        y = center[1] + radius * np.sin(angle)
        waypoints.append(airsim.Vector3r(x, y, altitude))
    return waypoints

# Generate path
path = generate_circular_path(
    center=(0, 0),
    radius=30,
    altitude=-25,
    num_points=36
)

# Fly along path
client.takeoffAsync().join()

client.moveOnPathAsync(
    path,
    velocity=5,
    timeout_sec=120,
    drivetrain=airsim.DrivetrainType.ForwardOnly,
    yaw_mode=airsim.YawMode(is_rate=False, yaw_or_rate=0)
).join()
```

## Obstacle Avoidance with Depth

```python
import airsim
import numpy as np

SAFE_DISTANCE = 5.0
CRUISE_SPEED = 3.0

def get_depth_front():
    """Get minimum distance ahead."""
    response = client.simGetImages([
        airsim.ImageRequest("front_center", airsim.ImageType.DepthPerspective, True)
    ])[0]

    depth = np.array(response.image_data_float, dtype=np.float32)
    depth = depth.reshape(response.height, response.width)

    # Get center region
    h, w = depth.shape
    center_region = depth[h//3:2*h//3, w//3:2*w//3]

    return np.min(center_region)

try:
    while True:
        min_distance = get_depth_front()
        print(f"Min distance: {min_distance:.2f}m")

        if min_distance < SAFE_DISTANCE:
            # Obstacle detected - turn
            print("Turning...")
            client.moveByVelocityAsync(0, 0, 0, 0.5).join()
            client.rotateByYawRateAsync(45, 1).join()
        else:
            # Move forward
            client.moveByVelocityAsync(CRUISE_SPEED, 0, 0, 0.5)

except KeyboardInterrupt:
    pass

client.landAsync().join()
```

## Return to Home

```python
def return_to_home(client, home_position, altitude=-20):
    """Safely return drone to home."""
    current_state = client.getMultirotorState()
    current_pos = current_state.kinematics_estimated.position

    # Ascend to safe altitude
    print("Ascending...")
    client.moveToPositionAsync(
        current_pos.x_val,
        current_pos.y_val,
        altitude,
        velocity=3
    ).join()

    # Fly to home
    print("Flying home...")
    client.moveToPositionAsync(
        home_position[0],
        home_position[1],
        altitude,
        velocity=5
    ).join()

    # Land
    print("Landing...")
    client.landAsync().join()

# Usage
home = (0, 0)
return_to_home(client, home)
```

## Next Steps

- [Data Collection](../03-data-collection/data-collection.md) - Collect training data
- [Drone Following](../../chapter-06-air-ground/01-drone-following/drone-following.md) - Track vehicles


---

<a id="tutorials-data-collection"></a>

### Data Collection

> Build a complete data collection pipeline to generate training datasets for perception models, including synchronized multi-sensor data from both ground vehicles and aerial drones.

# Data Collection Tutorial

Learn how to collect training data for machine learning models, including synchronized sensor data with ground truth labels.

## Dataset Structure

```
dataset/
├── train/
│   ├── images/          # RGB images
│   ├── depth/           # Depth maps
│   ├── segmentation/    # Semantic labels
│   └── labels/          # Bounding boxes
└── metadata.json        # Dataset info
```

## Data Collector Class

```python
import carla
import numpy as np
import json
import os
import threading

class DataCollector:
    def __init__(self, output_dir='dataset'):
        self.client = carla.Client('localhost', 2000)
        self.world = self.client.get_world()
        self.bp_lib = self.world.get_blueprint_library()
        self.output_dir = output_dir
        self.frame_id = 0

        # Create directories
        for subdir in ['images', 'depth', 'segmentation', 'labels']:
            os.makedirs(f'{output_dir}/{subdir}', exist_ok=True)

        # Enable sync mode
        settings = self.world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = 0.1
        self.world.apply_settings(settings)

    def spawn_ego_vehicle(self):
        vehicle_bp = self.bp_lib.find('vehicle.tesla.model3')
        spawn_point = self.world.get_map().get_spawn_points()[0]
        self.vehicle = self.world.spawn_actor(vehicle_bp, spawn_point)
        self.vehicle.set_autopilot(True)
        return self.vehicle

    def setup_sensors(self):
        self.sensors = []
        self.data_queue = {}
        self.sensor_events = {}

        # RGB Camera
        rgb_bp = self.bp_lib.find('sensor.camera.rgb')
        rgb_bp.set_attribute('image_size_x', '1920')
        rgb_bp.set_attribute('image_size_y', '1080')
        rgb_transform = carla.Transform(carla.Location(x=1.5, z=2.4))
        self.rgb_camera = self.world.spawn_actor(
            rgb_bp, rgb_transform, attach_to=self.vehicle)
        self.rgb_camera.listen(lambda data: self._on_sensor('rgb', data))
        self.sensors.append(self.rgb_camera)
        self.sensor_events['rgb'] = threading.Event()

        # Depth Camera
        depth_bp = self.bp_lib.find('sensor.camera.depth')
        depth_bp.set_attribute('image_size_x', '1920')
        depth_bp.set_attribute('image_size_y', '1080')
        self.depth_camera = self.world.spawn_actor(
            depth_bp, rgb_transform, attach_to=self.vehicle)
        self.depth_camera.listen(lambda data: self._on_sensor('depth', data))
        self.sensors.append(self.depth_camera)
        self.sensor_events['depth'] = threading.Event()

    def _on_sensor(self, name, data):
        self.data_queue[name] = data
        self.sensor_events[name].set()

    def get_bounding_boxes(self):
        """Get 3D bounding boxes for all vehicles."""
        boxes = []
        for actor in self.world.get_actors().filter('vehicle.*'):
            if actor.id == self.vehicle.id:
                continue

            bb = actor.bounding_box
            transform = actor.get_transform()

            boxes.append({
                'class': 'vehicle',
                'location': {
                    'x': transform.location.x,
                    'y': transform.location.y,
                    'z': transform.location.z
                },
                'extent': {
                    'x': bb.extent.x,
                    'y': bb.extent.y,
                    'z': bb.extent.z
                }
            })
        return boxes

    def collect_frame(self):
        self.world.tick()
        self.data_queue.clear()
        for event in self.sensor_events.values():
            event.clear()

        # Wait for sensors
        for name, event in self.sensor_events.items():
            event.wait(timeout=5.0)

        # Save RGB
        self.data_queue['rgb'].save_to_disk(
            f'{self.output_dir}/images/{self.frame_id:06d}.png'
        )

        # Save Depth
        self.data_queue['depth'].save_to_disk(
            f'{self.output_dir}/depth/{self.frame_id:06d}.png'
        )

        # Save Labels
        boxes = self.get_bounding_boxes()
        ego_transform = self.vehicle.get_transform()

        label = {
            'frame_id': self.frame_id,
            'ego_pose': {
                'x': ego_transform.location.x,
                'y': ego_transform.location.y,
                'z': ego_transform.location.z,
                'yaw': ego_transform.rotation.yaw
            },
            'objects': boxes
        }

        with open(f'{self.output_dir}/labels/{self.frame_id:06d}.json', 'w') as f:
            json.dump(label, f, indent=2)

        self.frame_id += 1
        return self.frame_id

    def cleanup(self):
        for sensor in self.sensors:
            sensor.stop()
            sensor.destroy()
        self.vehicle.destroy()

        settings = self.world.get_settings()
        settings.synchronous_mode = False
        self.world.apply_settings(settings)
```

## Usage

```python
collector = DataCollector('dataset/train')
collector.spawn_ego_vehicle()
collector.setup_sensors()

try:
    for _ in range(1000):  # Collect 1000 frames
        frame = collector.collect_frame()
        if frame % 100 == 0:
            print(f"Collected {frame} frames")
finally:
    collector.cleanup()
```

## Weather Variation

```python
import random

weather_presets = [
    carla.WeatherParameters.ClearNoon,
    carla.WeatherParameters.CloudyNoon,
    carla.WeatherParameters.WetNoon,
    carla.WeatherParameters.ClearSunset,
]

# Change weather periodically
if frame_id % 200 == 0:
    weather = random.choice(weather_presets)
    world.set_weather(weather)
```

## Next Steps

- [Sensors Tutorial](../01-sensors-tutorial/sensors-tutorial.md) - Sensor details
- [Coordinate Systems](../../chapter-05-advanced/01-coordinate-systems/coordinate-systems.md) - Coordinate conversion


---

<a id="tutorials"></a>

## Tutorials

> Step-by-step tutorials to help you build real autonomous systems with Carla Air. Each tutorial includes complete code examples and explanations.

Step-by-step tutorials to help you build real autonomous systems with Carla Air. Each tutorial includes complete code examples and explanations.


---

<a id="advanced-coordinate-systems"></a>

### Coordinate Systems

> Understanding the different coordinate systems used by CARLA and AirSim and how to convert between them.

Understanding coordinate system conversion is essential for CARLA-Air development. This guide covers the differences between CARLA and AirSim coordinate systems and how to convert between them.

## Coordinate System Comparison

| Property | CARLA | AirSim (NED) |
|----------|-------|--------------|
| X-axis | Forward | North |
| Y-axis | Right | East |
| Z-axis | Up (positive) | Down (positive) |
| Origin | UE4 world origin | PlayerStart + offset |
| Units | Meters | Meters |

## Visual Representation

```
CARLA:                    AirSim (NED):
    Z↑                        X (North)
    |                         ↗
    |                        /
    +----→ X               +----→ Y (East)
   /                       |
  Y                        Z↓ (Down)
```

## The Key Conversion

The most important conversion is the Z-axis inversion:

```python
# CARLA to AirSim NED
airsim_z = -carla_z

# AirSim NED to CARLA
carla_z = -airsim_z
```

## Offset Calibration

CARLA and AirSim may have different world origins. Never hardcode offsets - always calibrate at runtime:

```python
def calibrate_offset(world, air_client):
    """
    Calculate coordinate offset by finding the drone in both systems.

    Returns:
        tuple: (offset_x, offset_y, offset_z) to add to CARLA coords
    """
    # Find drone actor in CARLA
    for actor in world.get_actors():
        if 'drone' in actor.type_id.lower():
            carla_loc = actor.get_location()

            # Get drone position from AirSim
            state = air_client.getMultirotorState()
            air_pos = state.kinematics_estimated.position

            # Calculate offset
            offset_x = air_pos.x_val - carla_loc.x
            offset_y = air_pos.y_val - carla_loc.y
            offset_z = air_pos.z_val - (-carla_loc.z)

            return (offset_x, offset_y, offset_z)

    return (0, 0, 0)
```

## Complete Conversion Functions

```python
def carla_to_airsim(carla_location, offset=(0, 0, 0)):
    """
    Convert CARLA location to AirSim NED coordinates.

    Args:
        carla_location: carla.Location object
        offset: Calibrated offset tuple (ox, oy, oz)

    Returns:
        tuple: (x, y, z) in AirSim NED coordinates
    """
    airsim_x = carla_location.x + offset[0]
    airsim_y = carla_location.y + offset[1]
    airsim_z = -carla_location.z + offset[2]

    return (airsim_x, airsim_y, airsim_z)


def airsim_to_carla(airsim_position, offset=(0, 0, 0)):
    """
    Convert AirSim NED coordinates to CARLA location.

    Args:
        airsim_position: Position with x_val, y_val, z_val
        offset: Calibrated offset tuple (ox, oy, oz)

    Returns:
        tuple: (x, y, z) in CARLA coordinates
    """
    carla_x = airsim_position.x_val - offset[0]
    carla_y = airsim_position.y_val - offset[1]
    carla_z = -(airsim_position.z_val - offset[2])

    return (carla_x, carla_y, carla_z)
```

## Common Patterns

### Moving Drone to Vehicle Position

```python
def move_drone_to_vehicle(air_client, vehicle, altitude_offset=15):
    """Move drone above a CARLA vehicle."""
    loc = vehicle.get_location()

    # Convert to AirSim coordinates
    # X and Y stay the same (with offset), Z is inverted
    target_x = loc.x
    target_y = loc.y
    target_z = -(loc.z + altitude_offset)  # NED: negative = up

    air_client.moveToPositionAsync(target_x, target_y, target_z, 5)
```

### Getting Drone Position in CARLA Frame

```python
def get_drone_carla_position(air_client):
    """Get drone position in CARLA coordinate frame."""
    state = air_client.getMultirotorState()
    pos = state.kinematics_estimated.position

    carla_x = pos.x_val
    carla_y = pos.y_val
    carla_z = -pos.z_val  # Invert Z

    return (carla_x, carla_y, carla_z)
```

### Following with Offset Behind Vehicle

```python
import math

def calculate_follow_position(vehicle_transform, distance_behind=15, height_above=10):
    """
    Calculate drone position behind and above vehicle.

    Returns:
        tuple: (x, y, z) in AirSim NED coordinates
    """
    loc = vehicle_transform.location
    yaw_rad = math.radians(vehicle_transform.rotation.yaw)

    # Position behind vehicle
    target_x = loc.x - distance_behind * math.cos(yaw_rad)
    target_y = loc.y - distance_behind * math.sin(yaw_rad)

    # Height in NED (negative = up)
    target_z = -(loc.z + height_above)

    return (target_x, target_y, target_z)
```

## Rotation Conversion

Rotations are consistent between CARLA and AirSim:

| Angle | CARLA | AirSim |
|-------|-------|--------|
| Pitch | Nose up = positive | Same |
| Yaw | Clockwise = positive | Same |
| Roll | Right wing down = positive | Same |

No conversion needed for rotation angles.

## Debugging Coordinates

```python
def debug_positions(world, air_client):
    """Print positions in both coordinate systems for debugging."""
    # Find drone in CARLA
    drone_carla = None
    for actor in world.get_actors():
        if 'drone' in actor.type_id.lower():
            drone_carla = actor.get_location()
            break

    # Get from AirSim
    state = air_client.getMultirotorState()
    drone_air = state.kinematics_estimated.position

    print(f"CARLA:  x={drone_carla.x:.2f}, y={drone_carla.y:.2f}, z={drone_carla.z:.2f}")
    print(f"AirSim: x={drone_air.x_val:.2f}, y={drone_air.y_val:.2f}, z={drone_air.z_val:.2f}")
    print(f"Z check: CARLA z={drone_carla.z:.2f} should equal -AirSim z={-drone_air.z_val:.2f}")
```

## Common Mistakes

1. **Forgetting Z inversion**: Always remember `airsim_z = -carla_z`
2. **Hardcoding offsets**: Offsets vary by map; always calibrate
3. **Mixing coordinates**: Keep track of which system you're working in
4. **Altitude confusion**: In NED, going up means decreasing Z (more negative)

## Quick Reference

```python
# Drone goes UP to 50m in CARLA frame
airsim_z = -50  # Negative in NED

# Drone at CARLA position (100, 200, 30)
airsim_coords = (100, 200, -30)

# Vehicle at CARLA (x=50, y=100, z=0), drone 20m above
drone_airsim_z = -(0 + 20) = -20
```

## Next Steps

- [Synchronization](../02-synchronization/synchronization.md) - Frame-perfect simulation
- [Performance](../03-performance/performance.md) - Optimization tips


---

<a id="advanced-synchronization"></a>

### Synchronization

> Understanding synchronous simulation mode in Carla Air and how to configure it correctly.

This guide covers synchronization modes in CARLA-Air for frame-perfect simulations and reproducible experiments.

## Asynchronous vs Synchronous Mode

| Mode | Description | Use Case |
|------|-------------|----------|
| Asynchronous | Simulation runs in real-time | Visualization, demos |
| Synchronous | Simulation waits for tick | Data collection, training |

## Enabling Synchronous Mode

```python
import carla

def enable_sync_mode(world, fixed_delta=0.05):
    """
    Enable synchronous mode with fixed time step.

    Args:
        world: CARLA world object
        fixed_delta: Time step in seconds (0.05 = 20 FPS)
    """
    settings = world.get_settings()
    settings.synchronous_mode = True
    settings.fixed_delta_seconds = fixed_delta
    world.apply_settings(settings)
    print(f"Sync mode enabled: {1/fixed_delta:.0f} FPS")
```

## Traffic Manager Synchronization

When using Traffic Manager with synchronous mode, TM must also be synchronized:

```python
def setup_sync_traffic(client, world, fixed_delta=0.05):
    """Setup synchronized Traffic Manager."""
    # Enable world sync mode
    settings = world.get_settings()
    settings.synchronous_mode = True
    settings.fixed_delta_seconds = fixed_delta
    world.apply_settings(settings)

    # Synchronize Traffic Manager
    tm = client.get_trafficmanager(8000)
    tm.set_synchronous_mode(True)

    return tm
```

## The Simulation Loop

In synchronous mode, you must call `world.tick()` to advance the simulation:

```python
def sync_simulation_loop(world, num_frames=100):
    """Run synchronized simulation."""
    for frame_id in range(num_frames):
        # Advance simulation by one step
        world.tick()

        # Now read sensor data, actor positions, etc.
        # All data is from the same simulation frame

        # Your logic here
        pass
```

## Sensor Data Synchronization

Use sensor queues for synchronized data collection:

```python
import queue

def create_sync_camera(world, bp_lib, transform, parent=None):
    """Create camera with synchronized data queue."""
    cam_bp = bp_lib.find("sensor.camera.rgb")
    cam_bp.set_attribute("image_size_x", "1280")
    cam_bp.set_attribute("image_size_y", "720")

    if parent:
        camera = world.spawn_actor(cam_bp, transform, attach_to=parent)
    else:
        camera = world.spawn_actor(cam_bp, transform)

    # Create queue for synchronized access
    image_queue = queue.Queue()
    camera.listen(image_queue.put)

    return camera, image_queue


def get_sync_image(image_queue, timeout=2.0):
    """Get image from queue with timeout."""
    try:
        image = image_queue.get(timeout=timeout)
        return image
    except queue.Empty:
        return None
```

## Complete Synchronized Recording

```python
import carla
import queue
import numpy as np
import cv2

def synchronized_recording(num_frames=200):
    client = carla.Client("localhost", 2000)
    client.set_timeout(10.0)
    world = client.get_world()
    bp_lib = world.get_blueprint_library()

    original_settings = world.get_settings()
    actors = []

    try:
        # Enable sync mode
        settings = world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = 0.05
        world.apply_settings(settings)

        # Setup Traffic Manager in sync mode
        tm = client.get_trafficmanager(8000)
        tm.set_synchronous_mode(True)

        # Spawn vehicle
        vehicle_bp = bp_lib.find("vehicle.tesla.model3")
        spawn_point = world.get_map().get_spawn_points()[0]
        vehicle = world.try_spawn_actor(vehicle_bp, spawn_point)
        actors.append(vehicle)
        vehicle.set_autopilot(True, 8000)

        # Create synchronized camera
        camera, image_queue = create_sync_camera(
            world, bp_lib,
            carla.Transform(carla.Location(x=-6, z=3), carla.Rotation(pitch=-10)),
            parent=vehicle
        )
        actors.append(camera)

        frames = []

        # Synchronized loop
        for frame_id in range(num_frames):
            # Advance simulation
            world.tick()

            # Get synchronized image
            image = get_sync_image(image_queue)
            if image:
                arr = np.frombuffer(image.raw_data, dtype=np.uint8)
                arr = arr.reshape((image.height, image.width, 4))[:, :, :3]
                frame = arr[:, :, ::-1].copy()

                # Add frame number
                cv2.putText(frame, f"Frame: {frame_id}", (10, 30),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
                frames.append(frame)

            if frame_id % 50 == 0:
                print(f"Frame {frame_id}/{num_frames}")

        return frames

    finally:
        # CRITICAL: Restore async mode
        world.apply_settings(original_settings)
        for actor in actors:
            try:
                actor.destroy()
            except:
                pass
```

## Restoring Async Mode

**Critical**: Always restore async mode in a `finally` block to prevent simulation freeze:

```python
def safe_sync_session(world):
    """Template for safe sync mode usage."""
    original_settings = world.get_settings()

    try:
        # Enable sync mode
        settings = world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = 0.05
        world.apply_settings(settings)

        # Your synchronized code here
        pass

    finally:
        # ALWAYS restore original settings
        world.apply_settings(original_settings)
        print("Async mode restored")
```

## Frame Rate Control

```python
def variable_framerate(world, slow_frames=50, fast_frames=50):
    """Demonstrate variable frame rate."""
    settings = world.get_settings()
    settings.synchronous_mode = True

    # Slow motion (10 FPS simulation)
    settings.fixed_delta_seconds = 0.1
    world.apply_settings(settings)
    for _ in range(slow_frames):
        world.tick()

    # Normal speed (20 FPS simulation)
    settings.fixed_delta_seconds = 0.05
    world.apply_settings(settings)
    for _ in range(fast_frames):
        world.tick()
```

## Multi-Sensor Synchronization

```python
def multi_sensor_sync(world, bp_lib, vehicle):
    """Synchronize multiple sensors."""
    sensors = []
    queues = []

    # RGB Camera
    rgb_cam, rgb_q = create_sync_camera(world, bp_lib,
        carla.Transform(carla.Location(x=2, z=1.5)),
        parent=vehicle)
    sensors.append(rgb_cam)
    queues.append(('rgb', rgb_q))

    # Depth Camera
    depth_bp = bp_lib.find("sensor.camera.depth")
    depth_bp.set_attribute("image_size_x", "640")
    depth_bp.set_attribute("image_size_y", "480")
    depth_cam = world.spawn_actor(depth_bp,
        carla.Transform(carla.Location(x=2, z=1.5)),
        attach_to=vehicle)
    depth_q = queue.Queue()
    depth_cam.listen(depth_q.put)
    sensors.append(depth_cam)
    queues.append(('depth', depth_q))

    return sensors, queues


def get_all_sensor_data(queues, timeout=2.0):
    """Get data from all sensors for current frame."""
    data = {}
    for name, q in queues:
        try:
            data[name] = q.get(timeout=timeout)
        except queue.Empty:
            data[name] = None
    return data
```

## Common Issues

1. **Simulation freezes**: Forgot to restore async mode
2. **Missing frames**: Queue timeout too short
3. **TM not synced**: Traffic Manager must be synchronized separately
4. **Sensor lag**: Call tick() before reading sensor data

## Tips

1. **Always use try-finally**: Ensure async mode restoration
2. **Match TM sync state**: TM and world must have same sync setting
3. **Use queues**: For reliable sensor data access
4. **Set appropriate timeout**: Account for rendering time

## Next Steps

- [Performance](../03-performance/performance.md) - Optimization techniques
- [Trajectory Recording](../../chapter-04-air-ground/03-trajectory-recording/trajectory-recording.md) - Data collection


---

<a id="advanced-performance"></a>

### Performance Optimization

> This guide covers various tips and techniques for optimizing Carla Air simulation performance.

This guide covers techniques to optimize CARLA-Air simulations for better performance and stability.

## Graphics Quality Settings

Reduce rendering quality for higher FPS:

```python
import carla

def set_low_quality(world):
    """Configure low quality settings for better performance."""
    settings = world.get_settings()
    settings.no_rendering_mode = False  # Keep rendering
    world.apply_settings(settings)

    # Note: Most quality settings are controlled via launch parameters
    # or Unreal Engine configuration files


def enable_no_rendering(world):
    """Disable rendering completely for maximum performance."""
    settings = world.get_settings()
    settings.no_rendering_mode = True
    world.apply_settings(settings)
    print("No-rendering mode enabled (headless)")
```

## Reducing Actor Count

Limit actors to improve performance:

```python
def spawn_limited_traffic(world, bp_lib, max_vehicles=8, max_walkers=0):
    """Spawn traffic with limits for stability with drone."""
    spawn_points = world.get_map().get_spawn_points()
    vehicle_bp = bp_lib.find("vehicle.tesla.model3")

    vehicles = []
    for i in range(min(max_vehicles, len(spawn_points))):
        v = world.try_spawn_actor(vehicle_bp, spawn_points[i])
        if v:
            vehicles.append(v)

    # Note: With active drone, keep vehicles under 8
    return vehicles
```

## Camera Resolution

Lower resolution improves performance:

```python
def create_efficient_camera(world, bp_lib, transform, parent=None):
    """Create camera with performance-optimized settings."""
    cam_bp = bp_lib.find("sensor.camera.rgb")

    # Lower resolution for better FPS
    cam_bp.set_attribute("image_size_x", "640")  # Instead of 1920
    cam_bp.set_attribute("image_size_y", "480")  # Instead of 1080

    # Disable expensive effects
    cam_bp.set_attribute("motion_blur_intensity", "0.0")
    cam_bp.set_attribute("enable_postprocess_effects", "false")

    if parent:
        return world.spawn_actor(cam_bp, transform, attach_to=parent)
    return world.spawn_actor(cam_bp, transform)
```

## Sensor Update Rates

Reduce sensor tick rates:

```python
def create_low_rate_camera(world, bp_lib, transform, tick_rate=0.1):
    """Create camera with reduced update rate."""
    cam_bp = bp_lib.find("sensor.camera.rgb")
    cam_bp.set_attribute("image_size_x", "640")
    cam_bp.set_attribute("image_size_y", "480")

    # Sensor tick every 100ms instead of every frame
    cam_bp.set_attribute("sensor_tick", str(tick_rate))

    return world.spawn_actor(cam_bp, transform)
```

## Cleanup Between Sessions

Proper cleanup prevents memory leaks:

```python
def thorough_cleanup(world):
    """Remove all dynamic actors from the world."""
    # Stop all sensors first
    for actor in world.get_actors().filter("sensor.*"):
        try:
            actor.stop()
            actor.destroy()
        except:
            pass

    # Destroy vehicles
    for actor in world.get_actors().filter("vehicle.*"):
        try:
            actor.destroy()
        except:
            pass

    # Destroy walkers
    for actor in world.get_actors().filter("walker.*"):
        try:
            actor.destroy()
        except:
            pass

    # Small delay for cleanup to complete
    import time
    time.sleep(0.5)
```

## Fixed Time Step

Use consistent time steps:

```python
def setup_fixed_timestep(world, delta=0.05):
    """Configure fixed time step for consistent physics."""
    settings = world.get_settings()
    settings.fixed_delta_seconds = delta
    settings.substepping = True
    settings.max_substep_delta_time = 0.01
    settings.max_substeps = 10
    world.apply_settings(settings)
```

## Drone Performance Tips

```python
def optimize_drone_flight(air_client):
    """Tips for efficient drone operations."""
    import airsim

    # Use velocity control instead of position for smoother flight
    # Position control requires more computation

    # Reduce image requests
    # Only request images when needed, not every frame

    # Use lower resolution for drone cameras
    camera_settings = airsim.ImageRequest(
        "0",  # Camera name
        airsim.ImageType.Scene,
        False,  # Not compressed
        False   # Not floating point
    )

    return camera_settings
```

## Profiling Tips

```python
import time

class PerformanceMonitor:
    """Simple performance monitoring."""

    def __init__(self):
        self.frame_times = []
        self.last_time = time.time()

    def tick(self):
        """Call once per frame."""
        now = time.time()
        self.frame_times.append(now - self.last_time)
        self.last_time = now

        # Keep last 100 frames
        if len(self.frame_times) > 100:
            self.frame_times.pop(0)

    def get_fps(self):
        """Get average FPS."""
        if not self.frame_times:
            return 0
        avg_time = sum(self.frame_times) / len(self.frame_times)
        return 1.0 / avg_time if avg_time > 0 else 0

    def report(self):
        """Print performance report."""
        fps = self.get_fps()
        min_time = min(self.frame_times) if self.frame_times else 0
        max_time = max(self.frame_times) if self.frame_times else 0
        print(f"FPS: {fps:.1f}, Frame time: {min_time*1000:.1f}-{max_time*1000:.1f}ms")
```

## Memory Management

```python
import gc

def optimize_memory():
    """Force garbage collection."""
    gc.collect()


def process_images_efficiently(image_queue, max_buffer=10):
    """Process images without accumulating memory."""
    frames = []

    while len(frames) < max_buffer:
        try:
            image = image_queue.get_nowait()
            # Process immediately, don't store raw data
            processed = process_image(image)
            frames.append(processed)
        except:
            break

    return frames
```

## Launch Parameters

Start CARLA with performance flags:

```bash
# Low quality preset
./CarlaAir.sh Town10HD -quality-level=Low

# Specific resolution
./CarlaAir.sh Town10HD -ResX=1280 -ResY=720

# No sound
./CarlaAir.sh Town10HD -nosound
```

## Recommended Settings

| Scenario | Vehicles | Resolution | Sync Mode | Notes |
|----------|----------|------------|-----------|-------|
| Demo/Visualization | 5-8 | 1280x720 | Async | Balance quality/performance |
| Data Collection | 2-4 | 640x480 | Sync | Consistent timing |
| Training | 1-2 | 320x240 | Sync | Maximum throughput |
| Testing | 0-2 | 640x480 | Either | Quick iteration |

## Summary

1. **Reduce resolution** when high quality isn't needed
2. **Limit actors** to 8 vehicles with active drone
3. **Clean up properly** between sessions
4. **Use sync mode** for consistent frame timing
5. **Monitor FPS** to detect performance issues
6. **Lower sensor rates** when real-time isn't required

## Next Steps

- [Installation](../../chapter-01-getting-started/01-installation/installation.md) - System requirements
- [Basic Flight](../../chapter-03-drone-flight/01-basic-flight/basic-flight.md) - Efficient flight patterns


---

<a id="advanced"></a>

## Advanced Topics

> Deep dive into advanced Carla Air concepts including performance optimization, synchronization, and coordinate system conversions.

Deep dive into advanced Carla Air concepts including performance optimization, synchronization, and coordinate system conversions.


---

<a id="air-ground-drone-following"></a>

### Drone-Vehicle Following

> Learn how to make drones follow ground vehicles for aerial monitoring and tracking scenarios.

# Drone Following Vehicle

This guide demonstrates how to use the drone to follow and track ground vehicles, combining CARLA vehicle control with AirSim drone operations.

## Coordinate System Conversion

CARLA and AirSim use different coordinate systems:

| System | X | Y | Z |
|--------|---|---|---|
| CARLA | Forward | Right | Up (positive) |
| AirSim (NED) | North | East | Down (positive) |

Conversion formula:
```python
def carla_to_ned(carla_location, offset):
    """Convert CARLA location to AirSim NED coordinates."""
    ned_x = carla_location.x + offset[0]
    ned_y = carla_location.y + offset[1]
    ned_z = -carla_location.z + offset[2]
    return ned_x, ned_y, ned_z

def calibrate_offset(world, air_client):
    """Calculate coordinate offset by finding the drone in CARLA."""
    for actor in world.get_actors():
        if 'drone' in actor.type_id.lower():
            carla_loc = actor.get_location()
            air_pos = air_client.getMultirotorState().kinematics_estimated.position
            return (
                air_pos.x_val - carla_loc.x,
                air_pos.y_val - carla_loc.y,
                air_pos.z_val - (-carla_loc.z)
            )
    return (0, 0, 0)
```

## Basic Following

Follow a vehicle at fixed offset:

```python
import carla
import airsim
import time

def follow_vehicle(client, world, air_client, vehicle, offset_back=15, offset_up=10, velocity=5):
    """
    Follow a vehicle from behind and above.

    Args:
        offset_back: Distance behind the vehicle (meters)
        offset_up: Height above the vehicle (meters)
    """
    # Get vehicle transform
    transform = vehicle.get_transform()
    location = transform.location

    # Calculate target position behind vehicle
    import math
    yaw_rad = math.radians(transform.rotation.yaw)

    target_x = location.x - offset_back * math.cos(yaw_rad)
    target_y = location.y - offset_back * math.sin(yaw_rad)
    target_z = location.z + offset_up

    # Convert to NED
    ned_x = target_x
    ned_y = target_y
    ned_z = -target_z

    # Move drone
    air_client.moveToPositionAsync(ned_x, ned_y, ned_z, velocity)
```

## Continuous Tracking

```python
def track_vehicle_loop(air_client, vehicle, duration=30, offset_back=15, offset_up=10):
    """Continuously track a vehicle for specified duration."""
    import math
    start_time = time.time()

    while time.time() - start_time < duration:
        transform = vehicle.get_transform()
        location = transform.location
        yaw_rad = math.radians(transform.rotation.yaw)

        # Calculate target behind vehicle
        target_x = location.x - offset_back * math.cos(yaw_rad)
        target_y = location.y - offset_back * math.sin(yaw_rad)
        ned_z = -(location.z + offset_up)

        # Non-blocking move
        air_client.moveToPositionAsync(target_x, target_y, ned_z, 8)

        time.sleep(0.1)  # Update rate
```

## Smooth Following with Velocity Control

```python
def smooth_follow(air_client, vehicle, follow_distance=15, altitude_offset=10, speed_factor=1.5):
    """Smooth following using velocity control."""
    import math

    transform = vehicle.get_transform()
    vehicle_loc = transform.location
    yaw_rad = math.radians(transform.rotation.yaw)

    # Target position
    target_x = vehicle_loc.x - follow_distance * math.cos(yaw_rad)
    target_y = vehicle_loc.y - follow_distance * math.sin(yaw_rad)
    target_z = -(vehicle_loc.z + altitude_offset)

    # Current drone position
    state = air_client.getMultirotorState()
    pos = state.kinematics_estimated.position

    # Calculate velocity towards target
    dx = target_x - pos.x_val
    dy = target_y - pos.y_val
    dz = target_z - pos.z_val

    distance = (dx**2 + dy**2 + dz**2)**0.5
    if distance < 0.5:
        return  # Close enough

    # Normalize and scale
    speed = min(distance * speed_factor, 10)  # Cap at 10 m/s
    vx = dx / distance * speed
    vy = dy / distance * speed
    vz = dz / distance * speed

    air_client.moveByVelocityAsync(vx, vy, vz, 0.1)
```

## Complete Example

```python
import carla
import airsim
import time

def air_ground_tracking():
    # Connect to both APIs
    client = carla.Client("localhost", 2000)
    client.set_timeout(10.0)
    world = client.get_world()
    bp_lib = world.get_blueprint_library()

    air_client = airsim.MultirotorClient(port=41451)
    air_client.confirmConnection()

    actors = []

    try:
        # Spawn vehicle
        vehicle_bp = bp_lib.find("vehicle.tesla.model3")
        spawn_point = world.get_map().get_spawn_points()[0]
        vehicle = world.try_spawn_actor(vehicle_bp, spawn_point)
        actors.append(vehicle)

        # Enable autopilot
        vehicle.set_autopilot(True)

        # Initialize drone
        air_client.enableApiControl(True)
        air_client.armDisarm(True)
        air_client.takeoffAsync().join()

        # Fly to initial tracking position
        loc = vehicle.get_location()
        air_client.moveToPositionAsync(loc.x - 15, loc.y, -(loc.z + 15), 5).join()

        # Track for 30 seconds
        print("Tracking vehicle...")
        track_vehicle_loop(air_client, vehicle, duration=30)

        # Land
        air_client.landAsync().join()

    finally:
        air_client.armDisarm(False)
        air_client.enableApiControl(False)
        for actor in actors:
            actor.destroy()
```

## Multiple Camera Views

Combine ground and aerial views:

```python
def setup_dual_cameras(world, bp_lib, vehicle):
    """Setup both ground vehicle camera and aerial drone view."""

    # Vehicle camera
    vehicle_cam_bp = bp_lib.find("sensor.camera.rgb")
    vehicle_cam_bp.set_attribute("image_size_x", "640")
    vehicle_cam_bp.set_attribute("image_size_y", "360")

    vehicle_cam = world.spawn_actor(
        vehicle_cam_bp,
        carla.Transform(carla.Location(x=-6, z=3), carla.Rotation(pitch=-10)),
        attach_to=vehicle
    )

    # Use AirSim for drone camera
    # Get images via air_client.simGetImages()

    return vehicle_cam
```

## Tips

1. **Update frequently**: Track at 10Hz or higher for smooth following
2. **Use velocity control**: Smoother than position-based movement
3. **Handle lost target**: Re-acquire if vehicle moves too fast
4. **Limit speed**: Cap drone speed to avoid overshooting
5. **Consider latency**: Account for communication delays

## Next Steps

- [Drone Following Pedestrian](../02-drone-following-pedestrian/drone-following-pedestrian.md) - Track pedestrians
- [Multi-Agent Scenarios](../03-multi-agent-scenarios/multi-agent.md) - Multiple vehicles and drones
- [Trajectory Recording](../04-trajectory-recording/trajectory-recording.md) - Record and replay paths


---

<a id="air-ground-drone-pedestrian-following"></a>

### Drone-Pedestrian-Following

> Learn how to make drones follow ground pedestrians for aerial monitoring and tracking scenarios.

# Drone Following Pedestrian

This guide demonstrates how to use the drone to follow and track pedestrians, combining CARLA walker control with AirSim drone operations.

## Pedestrian Tracking Basics

Tracking pedestrians is similar to vehicle tracking but requires:
- Lower altitude (pedestrians are shorter)
- Slower speeds (pedestrians move slower than vehicles)
- No heading-based offset (pedestrians can change direction quickly)

## Spawning Pedestrians

```python
import carla
import random

def spawn_pedestrian(world, bp_lib):
    """Spawn a pedestrian at a random navigation point."""
    walker_bps = bp_lib.filter('walker.pedestrian.*')
    walker_bp = random.choice(list(walker_bps))

    # Make pedestrian visible (not invincible)
    if walker_bp.has_attribute('is_invincible'):
        walker_bp.set_attribute('is_invincible', 'false')

    # Get spawn location from navigation mesh
    spawn_loc = world.get_random_location_from_navigation()
    if spawn_loc:
        spawn_transform = carla.Transform(spawn_loc)
        walker = world.try_spawn_actor(walker_bp, spawn_transform)
        return walker
    return None
```

## Basic Pedestrian Following

```python
import carla
import airsim
import time

def follow_pedestrian(air_client, walker, offset_back=8, offset_up=6, velocity=3):
    """
    Follow a pedestrian from above.

    Args:
        offset_back: Distance behind the pedestrian (meters)
        offset_up: Height above the pedestrian (meters)
        velocity: Drone speed (m/s)
    """
    # Get pedestrian location
    location = walker.get_location()

    # Calculate target position above pedestrian
    # For pedestrians, we hover directly above rather than behind
    target_x = location.x - offset_back
    target_y = location.y
    target_z = -(location.z + offset_up)  # NED coordinates

    # Move drone
    air_client.moveToPositionAsync(target_x, target_y, target_z, velocity)
```

## Continuous Pedestrian Tracking

```python
def track_pedestrian_loop(air_client, walker, duration=30, altitude=8):
    """Continuously track a pedestrian for specified duration."""
    start_time = time.time()

    while time.time() - start_time < duration:
        location = walker.get_location()

        # Hover above pedestrian
        target_x = location.x
        target_y = location.y
        ned_z = -(location.z + altitude)

        # Non-blocking move with slower speed for pedestrians
        air_client.moveToPositionAsync(target_x, target_y, ned_z, 4)

        time.sleep(0.1)  # Update rate
```

## Smooth Following with Velocity Control

```python
def smooth_follow_pedestrian(air_client, walker, altitude=8, speed_factor=1.2):
    """Smooth following using velocity control for pedestrians."""

    walker_loc = walker.get_location()

    # Target position directly above pedestrian
    target_x = walker_loc.x
    target_y = walker_loc.y
    target_z = -(walker_loc.z + altitude)

    # Current drone position
    state = air_client.getMultirotorState()
    pos = state.kinematics_estimated.position

    # Calculate velocity towards target
    dx = target_x - pos.x_val
    dy = target_y - pos.y_val
    dz = target_z - pos.z_val

    distance = (dx**2 + dy**2 + dz**2)**0.5
    if distance < 0.3:
        return  # Close enough

    # Slower speed for pedestrian tracking
    speed = min(distance * speed_factor, 5)  # Cap at 5 m/s
    vx = dx / distance * speed
    vy = dy / distance * speed
    vz = dz / distance * speed

    air_client.moveByVelocityAsync(vx, vy, vz, 0.1)
```

## Moving Pedestrian with set_transform

Since Walker AI Controllers can cause issues, we move pedestrians manually:

```python
import math

def move_pedestrian_manually(walker, world, speed=1.4, duration=10):
    """Move pedestrian in a direction using set_transform."""
    start_loc = walker.get_location()
    direction = random.uniform(0, 2 * math.pi)

    start_time = time.time()
    while time.time() - start_time < duration:
        elapsed = time.time() - start_time

        # Calculate new position
        new_x = start_loc.x + speed * elapsed * math.cos(direction)
        new_y = start_loc.y + speed * elapsed * math.sin(direction)

        new_transform = carla.Transform(
            carla.Location(x=new_x, y=new_y, z=start_loc.z)
        )
        walker.set_transform(new_transform)

        world.tick()
        time.sleep(0.05)
```

## Complete Example

```python
import carla
import airsim
import time
import random
import math

def drone_follow_pedestrian():
    # Connect to both APIs
    client = carla.Client("localhost", 2000)
    client.set_timeout(10.0)
    world = client.get_world()
    bp_lib = world.get_blueprint_library()

    air_client = airsim.MultirotorClient(port=41451)
    air_client.confirmConnection()

    actors = []

    try:
        # Spawn pedestrian
        walker_bps = bp_lib.filter('walker.pedestrian.*')
        walker_bp = random.choice(list(walker_bps))

        spawn_loc = world.get_random_location_from_navigation()
        if not spawn_loc:
            spawn_points = world.get_map().get_spawn_points()
            spawn_loc = spawn_points[0].location

        walker = world.try_spawn_actor(walker_bp, carla.Transform(spawn_loc))
        actors.append(walker)
        print(f"Pedestrian spawned at: {spawn_loc}")

        # Initialize drone
        air_client.enableApiControl(True)
        air_client.armDisarm(True)
        air_client.takeoffAsync().join()

        # Fly to initial tracking position
        air_client.moveToPositionAsync(
            spawn_loc.x,
            spawn_loc.y,
            -(spawn_loc.z + 10),
            5
        ).join()

        # Track for 20 seconds
        print("Tracking pedestrian...")
        track_pedestrian_loop(air_client, walker, duration=20, altitude=10)

        # Land
        air_client.landAsync().join()

    finally:
        air_client.armDisarm(False)
        air_client.enableApiControl(False)
        for actor in actors:
            actor.destroy()
```

## Tracking Multiple Pedestrians

```python
def track_nearest_pedestrian(air_client, world, altitude=10):
    """Track the nearest pedestrian to the drone."""

    # Get all walkers
    walkers = world.get_actors().filter('walker.pedestrian.*')
    if not walkers:
        return None

    # Get drone position
    state = air_client.getMultirotorState()
    drone_pos = state.kinematics_estimated.position

    # Find nearest walker
    nearest = None
    min_dist = float('inf')

    for walker in walkers:
        loc = walker.get_location()
        dist = ((loc.x - drone_pos.x_val)**2 +
                (loc.y - drone_pos.y_val)**2)**0.5
        if dist < min_dist:
            min_dist = dist
            nearest = walker

    if nearest:
        loc = nearest.get_location()
        air_client.moveToPositionAsync(
            loc.x, loc.y, -(loc.z + altitude), 4
        )

    return nearest
```

## Tips for Pedestrian Tracking

1. **Lower altitude**: Pedestrians are shorter than vehicles, use 6-10m altitude
2. **Slower speeds**: Pedestrians move at ~1.4 m/s, cap drone at 4-5 m/s
3. **Hover above**: Unlike vehicles, hover directly above rather than behind
4. **Handle static pedestrians**: Pedestrians may stop walking
5. **Avoid AI controller**: Use `set_transform` instead of walker controllers

## Differences from Vehicle Tracking

| Aspect | Vehicle | Pedestrian |
|--------|---------|------------|
| Typical speed | 10-50 km/h | 1.4 m/s (~5 km/h) |
| Altitude offset | 10-15m | 6-10m |
| Following mode | Behind + above | Directly above |
| Direction changes | Gradual | Sudden |
| Drone speed | 8-10 m/s | 3-5 m/s |

## Next Steps

- [Drone Following Vehicle](../01-drone-following-vehicle/drone-following-vehicle.md) - Track vehicles
- [Multi-Agent Scenarios](../03-multi-agent-scenarios/multi-agent.md) - Multiple agents
- [Trajectory Recording](../04-trajectory-recording/trajectory-recording.md) - Record paths


---

<a id="air-ground-multi-agent"></a>

### Multi-Agent Scenarios

> Learn to create and manage multi-agent scenarios in Carla Air, coordinating multiple vehicles, drones, and pedestrians.

# Multi-Agent Coordination

This guide demonstrates coordinating multiple vehicles and a drone in CARLA-Air simulations.

## Spawning Multiple Vehicles

```python
import carla
import time

def spawn_vehicle_convoy(world, bp_lib, num_vehicles=5):
    """Spawn multiple vehicles on the map."""
    vehicle_bp = bp_lib.find("vehicle.tesla.model3")
    spawn_points = world.get_map().get_spawn_points()

    vehicles = []
    for i in range(min(num_vehicles, len(spawn_points))):
        vehicle = world.try_spawn_actor(vehicle_bp, spawn_points[i])
        if vehicle:
            vehicles.append(vehicle)

    return vehicles
```

## Traffic Manager for Autopilot

Configure Traffic Manager for coordinated vehicle behavior:

```python
def setup_traffic_manager(client, vehicles, target_speed_diff=10):
    """Configure Traffic Manager for vehicles."""
    tm = client.get_trafficmanager(8000)
    tm.set_global_distance_to_leading_vehicle(2.5)

    for vehicle in vehicles:
        vehicle.set_autopilot(True, 8000)
        # Reduce speed compared to speed limit
        tm.vehicle_percentage_speed_difference(vehicle, target_speed_diff)
        # Allow lane changes
        tm.auto_lane_change(vehicle, True)

    return tm
```

## Drone Patrol Over Traffic

```python
import airsim
import math

def drone_patrol(air_client, center_x, center_y, altitude, radius=30, duration=30):
    """Fly drone in patrol pattern over traffic."""
    start_time = time.time()
    angle = 0

    while time.time() - start_time < duration:
        # Circular patrol
        x = center_x + radius * math.cos(angle)
        y = center_y + radius * math.sin(angle)
        z = -altitude  # NED coordinates

        air_client.moveToPositionAsync(x, y, z, 8)

        angle += 0.05
        time.sleep(0.1)
```

## Monitoring Multiple Vehicles

Track all vehicles from drone perspective:

```python
def get_vehicle_positions(vehicles):
    """Get positions of all vehicles."""
    positions = []
    for v in vehicles:
        loc = v.get_location()
        vel = v.get_velocity()
        speed = (vel.x**2 + vel.y**2)**0.5 * 3.6  # km/h
        positions.append({
            'id': v.id,
            'x': loc.x,
            'y': loc.y,
            'z': loc.z,
            'speed': speed
        })
    return positions

def calculate_centroid(vehicles):
    """Calculate center point of all vehicles."""
    if not vehicles:
        return None

    total_x = sum(v.get_location().x for v in vehicles)
    total_y = sum(v.get_location().y for v in vehicles)

    return total_x / len(vehicles), total_y / len(vehicles)
```

## Drone Following Convoy Centroid

```python
def follow_convoy(air_client, vehicles, altitude=25, duration=30):
    """Drone follows the center of a vehicle convoy."""
    start_time = time.time()

    while time.time() - start_time < duration:
        centroid = calculate_centroid(vehicles)
        if centroid:
            x, y = centroid
            air_client.moveToPositionAsync(x, y, -altitude, 10)

        time.sleep(0.1)
```

## Complete Multi-Agent Example

```python
import carla
import airsim
import time

def multi_agent_simulation():
    # Connect to both APIs
    client = carla.Client("localhost", 2000)
    client.set_timeout(10.0)
    world = client.get_world()
    bp_lib = world.get_blueprint_library()

    air_client = airsim.MultirotorClient(port=41451)
    air_client.confirmConnection()

    vehicles = []

    try:
        # Spawn vehicles
        vehicles = spawn_vehicle_convoy(world, bp_lib, 5)
        print(f"Spawned {len(vehicles)} vehicles")

        # Setup autopilot
        tm = setup_traffic_manager(client, vehicles)

        # Initialize drone
        air_client.enableApiControl(True)
        air_client.armDisarm(True)
        air_client.takeoffAsync().join()

        # Fly to initial position
        centroid = calculate_centroid(vehicles)
        if centroid:
            air_client.moveToPositionAsync(centroid[0], centroid[1], -30, 5).join()

        # Follow convoy
        follow_convoy(air_client, vehicles, altitude=30, duration=30)

        # Land
        air_client.landAsync().join()

    finally:
        air_client.armDisarm(False)
        air_client.enableApiControl(False)
        for v in vehicles:
            try:
                v.destroy()
            except:
                pass
```

## Coordinated Scenarios

### Intersection Monitoring
```python
def monitor_intersection(air_client, intersection_x, intersection_y, altitude=40):
    """Position drone to monitor an intersection."""
    air_client.moveToPositionAsync(
        intersection_x,
        intersection_y,
        -altitude,
        5
    ).join()

    # Hover and observe
    air_client.hoverAsync().join()
```

### Dynamic Target Switching
```python
def switch_target(air_client, vehicles, current_idx):
    """Switch drone focus to a different vehicle."""
    next_idx = (current_idx + 1) % len(vehicles)
    target = vehicles[next_idx]
    loc = target.get_location()

    air_client.moveToPositionAsync(
        loc.x - 10,  # Behind
        loc.y,
        -(loc.z + 15),  # Above
        8
    )

    return next_idx
```

## Tips

1. **Limit vehicle count**: With drone active, keep vehicles under 8 for stability
2. **Use Traffic Manager**: Let TM handle vehicle AI for realistic behavior
3. **Update frequently**: Poll positions at 10Hz for smooth tracking
4. **Handle despawns**: Vehicles may be destroyed; check validity before accessing

## Next Steps

- [Trajectory Recording](../03-trajectory-recording/trajectory-recording.md) - Record and replay paths
- [Coordinate Systems](../../chapter-05-advanced/01-coordinate-systems/coordinate-systems.md) - Detailed coordinate conversion


---

<a id="air-ground-trajectory-recording"></a>

### Trajectory Recording

> Carla Air provides tools to record walker, vehicle, and drone trajectories, then replay them together for synchronized multi-agent scenarios.

This guide demonstrates how to record and replay vehicle and drone trajectories for analysis and visualization.

## Recording Vehicle Trajectory

```python
import carla
import time
import json

def record_vehicle_trajectory(vehicle, duration=30, sample_rate=10):
    """
    Record vehicle trajectory over time.

    Args:
        vehicle: CARLA vehicle actor
        duration: Recording duration in seconds
        sample_rate: Samples per second

    Returns:
        List of trajectory points
    """
    trajectory = []
    start_time = time.time()

    while time.time() - start_time < duration:
        transform = vehicle.get_transform()
        velocity = vehicle.get_velocity()

        point = {
            'timestamp': time.time() - start_time,
            'location': {
                'x': transform.location.x,
                'y': transform.location.y,
                'z': transform.location.z
            },
            'rotation': {
                'pitch': transform.rotation.pitch,
                'yaw': transform.rotation.yaw,
                'roll': transform.rotation.roll
            },
            'velocity': {
                'x': velocity.x,
                'y': velocity.y,
                'z': velocity.z
            },
            'speed_kmh': (velocity.x**2 + velocity.y**2)**0.5 * 3.6
        }
        trajectory.append(point)

        time.sleep(1.0 / sample_rate)

    return trajectory
```

## Recording Drone Trajectory

```python
import airsim

def record_drone_trajectory(air_client, duration=30, sample_rate=10):
    """Record drone trajectory from AirSim."""
    trajectory = []
    start_time = time.time()

    while time.time() - start_time < duration:
        state = air_client.getMultirotorState()
        pos = state.kinematics_estimated.position
        vel = state.kinematics_estimated.linear_velocity
        orient = state.kinematics_estimated.orientation

        # Convert quaternion to Euler (simplified)
        import math
        pitch = math.asin(2 * (orient.w_val * orient.y_val - orient.z_val * orient.x_val))
        yaw = math.atan2(2 * (orient.w_val * orient.z_val + orient.x_val * orient.y_val),
                        1 - 2 * (orient.y_val**2 + orient.z_val**2))

        point = {
            'timestamp': time.time() - start_time,
            'position': {
                'x': pos.x_val,
                'y': pos.y_val,
                'z': pos.z_val
            },
            'velocity': {
                'x': vel.x_val,
                'y': vel.y_val,
                'z': vel.z_val
            },
            'orientation': {
                'pitch': math.degrees(pitch),
                'yaw': math.degrees(yaw)
            },
            'speed': (vel.x_val**2 + vel.y_val**2 + vel.z_val**2)**0.5
        }
        trajectory.append(point)

        time.sleep(1.0 / sample_rate)

    return trajectory
```

## Saving Trajectory to File

```python
def save_trajectory(trajectory, filename):
    """Save trajectory to JSON file."""
    with open(filename, 'w') as f:
        json.dump(trajectory, f, indent=2)
    print(f"Trajectory saved: {filename}")

def load_trajectory(filename):
    """Load trajectory from JSON file."""
    with open(filename, 'r') as f:
        return json.load(f)
```

## Visualizing Trajectory on Frame

```python
import cv2
import numpy as np

def draw_trajectory_overlay(frame, trajectory, current_idx, color=(0, 255, 0)):
    """Draw trajectory path on video frame."""
    result = frame.copy()
    h, w = frame.shape[:2]

    # Convert world coordinates to screen (simplified projection)
    def world_to_screen(point, scale=5, offset_x=w//2, offset_y=h//2):
        x = int(point['x'] * scale + offset_x)
        y = int(point['y'] * scale + offset_y)
        return (x, y)

    # Draw past trajectory
    for i in range(1, min(current_idx + 1, len(trajectory))):
        pt1 = world_to_screen(trajectory[i-1]['location'])
        pt2 = world_to_screen(trajectory[i]['location'])

        # Fade older points
        alpha = 0.3 + 0.7 * (i / current_idx) if current_idx > 0 else 1
        cv2.line(result, pt1, pt2, color, 2, cv2.LINE_AA)

    # Draw current position
    if current_idx < len(trajectory):
        current_pt = world_to_screen(trajectory[current_idx]['location'])
        cv2.circle(result, current_pt, 8, (0, 0, 255), -1)
        cv2.circle(result, current_pt, 10, (255, 255, 255), 2)

    return result
```

## Recording Both Vehicle and Drone

```python
def record_dual_trajectory(vehicle, air_client, duration=30, sample_rate=10):
    """Record synchronized vehicle and drone trajectories."""
    vehicle_traj = []
    drone_traj = []
    start_time = time.time()

    while time.time() - start_time < duration:
        timestamp = time.time() - start_time

        # Vehicle data
        v_transform = vehicle.get_transform()
        v_velocity = vehicle.get_velocity()
        vehicle_traj.append({
            'timestamp': timestamp,
            'x': v_transform.location.x,
            'y': v_transform.location.y,
            'z': v_transform.location.z,
            'yaw': v_transform.rotation.yaw,
            'speed': (v_velocity.x**2 + v_velocity.y**2)**0.5 * 3.6
        })

        # Drone data
        state = air_client.getMultirotorState()
        pos = state.kinematics_estimated.position
        vel = state.kinematics_estimated.linear_velocity
        drone_traj.append({
            'timestamp': timestamp,
            'x': pos.x_val,
            'y': pos.y_val,
            'z': pos.z_val,
            'speed': (vel.x_val**2 + vel.y_val**2 + vel.z_val**2)**0.5
        })

        time.sleep(1.0 / sample_rate)

    return {'vehicle': vehicle_traj, 'drone': drone_traj}
```

## Trajectory Statistics

```python
def analyze_trajectory(trajectory):
    """Calculate trajectory statistics."""
    if not trajectory:
        return None

    speeds = [p.get('speed_kmh', p.get('speed', 0)) for p in trajectory]

    # Calculate total distance
    total_distance = 0
    for i in range(1, len(trajectory)):
        loc_key = 'location' if 'location' in trajectory[i] else 'position'
        prev = trajectory[i-1][loc_key] if loc_key in trajectory[i-1] else trajectory[i-1]
        curr = trajectory[i][loc_key] if loc_key in trajectory[i] else trajectory[i]

        dx = curr['x'] - prev['x']
        dy = curr['y'] - prev['y']
        dz = curr.get('z', 0) - prev.get('z', 0)
        total_distance += (dx**2 + dy**2 + dz**2)**0.5

    return {
        'duration': trajectory[-1]['timestamp'],
        'total_distance': total_distance,
        'avg_speed': sum(speeds) / len(speeds) if speeds else 0,
        'max_speed': max(speeds) if speeds else 0,
        'min_speed': min(speeds) if speeds else 0,
        'num_samples': len(trajectory)
    }
```

## Complete Example

```python
import carla
import airsim
import time
import json

def trajectory_recording_demo():
    client = carla.Client("localhost", 2000)
    client.set_timeout(10.0)
    world = client.get_world()
    bp_lib = world.get_blueprint_library()

    air_client = airsim.MultirotorClient(port=41451)
    air_client.confirmConnection()

    vehicle = None

    try:
        # Spawn vehicle
        vehicle_bp = bp_lib.find("vehicle.tesla.model3")
        spawn_point = world.get_map().get_spawn_points()[0]
        vehicle = world.try_spawn_actor(vehicle_bp, spawn_point)
        vehicle.set_autopilot(True)

        # Initialize drone
        air_client.enableApiControl(True)
        air_client.armDisarm(True)
        air_client.takeoffAsync().join()

        # Record trajectories
        print("Recording trajectories...")
        data = record_dual_trajectory(vehicle, air_client, duration=20)

        # Save to file
        save_trajectory(data, "trajectories.json")

        # Analyze
        v_stats = analyze_trajectory(data['vehicle'])
        d_stats = analyze_trajectory(data['drone'])

        print(f"Vehicle: {v_stats['total_distance']:.1f}m, avg {v_stats['avg_speed']:.1f} km/h")
        print(f"Drone: {d_stats['total_distance']:.1f}m, avg {d_stats['avg_speed']:.1f} m/s")

    finally:
        air_client.landAsync().join()
        air_client.armDisarm(False)
        air_client.enableApiControl(False)
        if vehicle:
            vehicle.destroy()
```

## Tips

1. **Consistent sample rate**: Use fixed intervals for easier analysis
2. **Include timestamps**: Essential for synchronization and replay
3. **Store metadata**: Include map name, weather, and configuration
4. **Compress large files**: Use gzip for long recordings
5. **Validate data**: Check for NaN or outlier values

## Next Steps

- [Coordinate Systems](../../chapter-05-advanced/01-coordinate-systems/coordinate-systems.md) - Deep dive into coordinate conversion
- [Synchronization](../../chapter-05-advanced/02-synchronization/synchronization.md) - Frame-perfect simulation


---

<a id="air-ground"></a>

## Air-Ground Co-Simulation

> Carla Air's unique capability is unified air-ground cooperative simulation, combining CARLA's ground vehicle simulation with AirSim's drone simulation in a single environment.

Carla Air's unique capability is unified air-ground cooperative simulation, combining CARLA's ground vehicle simulation with AirSim's drone simulation in a single environment.

Description


---


## Document Statistics

- Total Sections: 6
- Total Documents: 30
- Total Characters: 140,649
