** use ```git lfs``` to clone and pull from repo
# M-Air Digital Twin :: McityMap for CarlaAir

This repo integrates the **McityMap** digital twin into a stock
[CarlaAir v0.1.7](https://github.com/louiszengCN/CarlaAir) install.

The integration is intentionally non-invasive: the only CarlaAir source file
touched is `CarlaUE4/Config/DefaultGame.ini`, and that change is applied
through a reversible patch that gets backed up before any edit. Everything
else lives inside this folder as standalone scripts.

---

## What's in this repo

```
M-Air_DigitalTwin/
├── README.md                          # This file
├── McityMap/                          # Map assets (umap, xodr, sublevels, statics)
├── config/
│   └── DefaultGame.ini.patch          # Cook entries appended by install.sh
└── scripts/
    ├── install.sh                     # Link map + patch DefaultGame.ini
    ├── uninstall.sh                   # Reverse install
    ├── run-mcity.sh                   # Boot CarlaAir straight into McityMap
    └── switch-to-mcity.sh             # Swap a running CarlaAir to McityMap
```

---

## Prerequisites

- A working CarlaAir v0.1.7 install. This folder must sit at the root of
  that install, i.e.:
  ```
  CarlaAir-v0.1.7/
  ├── CarlaAir.sh
  ├── CarlaUE4/...
  └── M-Air_DigitalTwin/      <-- here
  ```
- The `carlaAir` conda env activated (or any python with `import carla`
  working), needed by the runtime map switch.

---

## Step-by-step

### 1. Install

```bash
cd M-Air_DigitalTwin
chmod +x scripts/*.sh        # one-time, scripts ship as text
./scripts/install.sh
```

What happens:

1. `CarlaUE4/Content/McityMap` is created as a symlink to
   `M-Air_DigitalTwin/McityMap`. Editing assets in this repo is reflected
   immediately in the simulator.
2. `CarlaUE4/Config/DefaultGame.ini` is backed up (timestamped `.bak.*`)
   and patched with the cook entries from `config/DefaultGame.ini.patch`,
   bracketed by `# === M-Air DT McityMap entries BEGIN/END ===` markers.

The DefaultGame.ini patch matters only if you ever **re-package** the
CarlaAir binary. The pre-built shipping binary that ships with CarlaAir
v0.1.7 picks up loose assets in `CarlaUE4/Content/` at startup, so the
symlink alone is enough to make `McityMap_Main` show up in
`client.get_available_maps()`.

### 2. Launch CarlaAir into McityMap

Use the wrapper instead of `./CarlaAir.sh`:

```bash
./M-Air_DigitalTwin/scripts/run-mcity.sh
```

The wrapper:

1. Calls the stock `./CarlaAir.sh Town10HD` (because the UE4 shipping
   binary's command-line map loader only resolves `/Game/Carla/Maps/*`).
2. Once the CARLA RPC port is open, calls `client.load_world("McityMap_Main")`
   to swap the world to the digital twin.
3. Verifies the loaded map name and exits non-zero if the server silently
   fell back.

Pass-through flags work — for example:

```bash
./M-Air_DigitalTwin/scripts/run-mcity.sh --res 1920x1080 --quality High
```

### 3. (Optional) Switch an already-running CarlaAir to McityMap

If CarlaAir is already up on Town10HD or another map:

```bash
./M-Air_DigitalTwin/scripts/switch-to-mcity.sh
```

This destroys spawned actors, forces async mode, calls
`client.load_world("McityMap_Main")`, and waits for the new world to
become ready.

### 4. Uninstall

```bash
./M-Air_DigitalTwin/scripts/uninstall.sh
```

- Removes the `Content/McityMap` symlink (real directories are left alone).
- Strips the patch block from `DefaultGame.ini` and writes a fresh backup.
- Points you at the original install-era backup if you want to fully revert.

---

## Why the indirection (boot map ≠ target map)

The CarlaAir v0.1.7 shipping binary has two different map-resolution paths
and they behave differently:

| Mechanism                       | Search scope              | Custom paths? |
|---------------------------------|---------------------------|---------------|
| `CarlaUE4 <MapName>` cmdline    | `/Game/Carla/Maps/` only  | No            |
| `client.load_world(name)` (RPC) | full cooked AssetRegistry | Yes           |

McityMap lives at `/Game/McityMap/McityMap_Main`, outside the cmdline
search path. Passing it on the command line silently falls back to the
`GameDefaultMap` (Town10HD) without raising an error. `run-mcity.sh`
sidesteps this by booting a Town map and using the runtime RPC to swap.

This is also why `CarlaUE4/Config/DefaultEngine.ini`'s `GameDefaultMap`
is left untouched — fighting it would require modifying CarlaAir source.

---

## Asset layout

The McityMap assets follow CarlaAir's naming convention so that the OpenDrive
and navigation lookups work correctly:

| File                                             | Used by                              |
|--------------------------------------------------|--------------------------------------|
| `McityMap/McityMap_Main.umap`                    | UE4 — base level                     |
| `McityMap/Sublevels/McityMap_*.umap`             | UE4 — streamed sublevels             |
| `McityMap/OpenDrive/McityMap_Main.xodr`          | CARLA — road network / waypoints     |
| `McityMap/Nav/McityMap_Main.bin`                 | CARLA — pedestrian navmesh           |
| `McityMap/Static/`, `Blueprints/`, `Splash/`     | UE4 — referenced assets              |

CARLA looks up `.xodr` and `.bin` files by the umap basename, so the
`_Main` suffix on every file must stay consistent. Don't rename one without
the others.

---

## Troubleshooting

**`traffic.log` shows `Connected: Town10HD` after running `run-mcity.sh`**
The RPC switch step failed. Check that the `carlaAir` conda env is active
and `python3 -c "import carla"` works, then run
`./scripts/switch-to-mcity.sh` to see the actual error.

**`McityMap_Main` doesn't appear in `client.get_available_maps()`**
The shipping binary didn't pick up the loose assets. Verify:
- `CarlaUE4/Content/McityMap` resolves (`readlink -f`) to this repo's `McityMap/`.
- `CarlaUE4/Content/McityMap/McityMap_Main.umap` exists.
- The CarlaAir process was restarted after install (the AssetRegistry is
  scanned at boot, not on hot-reload).

**Want McityMap to be the default boot map**
The cmdline limitation prevents this without modifying CarlaAir source.
If you're willing to edit `CarlaUE4/Config/DefaultEngine.ini` directly,
change `GameDefaultMap=/Game/Carla/Maps/Town10HD` to
`GameDefaultMap=/Game/McityMap/McityMap_Main`. That edit is outside the
scope of this repo's install/uninstall flow.
