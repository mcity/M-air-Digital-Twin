# M-air Digital Twin

> ⚠️ This repo stores its map assets (~2 GB of `.uasset`/`.umap` files) in
> **[Git LFS](https://git-lfs.com/)** — install `git-lfs` before cloning or
> pulling, otherwise you'll get tiny pointer files instead of the real assets.

A digital-twin Unreal environment of the **[Mcity](https://mcity.umich.edu/) test
facility** (University of Michigan), packaged for two drone-simulation platforms.
Each integration is self-contained in its own folder with its own README,
installer scripts, and copy of the McityMap assets.

```
M-Air_DigitalTwin/
├── CarlaAir/          # McityMap for CarlaAir v0.1.7 (UE4 / CARLA-based)
└── Project_AirSim/    # McityMap for Project AirSim (UE 5.7), with real-world GNSS
```

---

## Which one do you want?

| | [CarlaAir](CarlaAir/README.md) | [Project_AirSim](Project_AirSim/README.md) |
|---|---|---|
| Simulator | [CarlaAir v0.1.7](https://github.com/louiszengCN/CarlaAir) (CARLA-based) | [Project AirSim](https://github.com/iamaisim/ProjectAirSim) |
| Engine | Unreal Engine 4 (pre-built shipping binary) | Unreal Engine 5.7 (built from source) |
| Install style | Non-invasive: symlink + reversible `DefaultGame.ini` patch into an existing CarlaAir install | One-command setup script that creates a `McityMap` project inside your Project AirSim repo |
| Geo-referencing | OpenDRIVE road network + pedestrian navmesh | Geo-anchored to Mcity's true location — simulated GPS reports genuine WGS84 lat/lon |
| Extras | Launch/switch wrappers (`run-mcity.sh`, `switch-to-mcity.sh`) | Keyboard flight script with GNSS overlay; optional live Google-Maps tracking UI |

## Getting started

- **CarlaAir** — place the `CarlaAir/` folder contents at the root of a CarlaAir
  v0.1.7 install and run its `scripts/install.sh`. Full instructions:
  [`CarlaAir/README.md`](CarlaAir/README.md)
- **Project AirSim** — build Project AirSim from source against UE 5.7, then run
  `setup_mcity_env.sh` pointing at your repo. Full instructions:
  [`Project_AirSim/README.md`](Project_AirSim/README.md)

The two integrations are independent — installing one does not affect the other.

---

## Credits & licenses

- **McityMap content**: University of Michigan / Mcity —
  [mcity/mcity-digital-twin](https://github.com/mcity/mcity-digital-twin)
- **CarlaAir**: [louiszengCN/CarlaAir](https://github.com/louiszengCN/CarlaAir)
- **Project AirSim**: IAMAI Consulting Corp / Microsoft, MIT License —
  [iamaisim/ProjectAirSim](https://github.com/iamaisim/ProjectAirSim)

See each folder's README for integration-specific licensing details.
