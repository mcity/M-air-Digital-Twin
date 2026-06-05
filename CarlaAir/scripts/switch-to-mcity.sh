#!/bin/bash
# ============================================
#  M-Air Digital Twin :: switch-to-mcity.sh
#  Swap the running CarlaAir world to McityMap_Main without restarting.
#  Talks to the CARLA RPC server (default port 2000).
# ============================================

set -e

DT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
CARLAAIR_DIR="$(cd "${DT_DIR}/.." && pwd)"
PORT=2000
TARGET="McityMap_Main"
TIMEOUT=300

usage() {
    cat <<EOF
Usage: $0 [--port PORT] [--map NAME]

Switch the running CarlaAir simulator to the McityMap digital twin.

Options:
  --port PORT     CARLA RPC port (default: 2000)
  --map NAME      Override target map (default: McityMap_Main)
  --help, -h      Show this help
EOF
}

while [ $# -gt 0 ]; do
    case "$1" in
        --port) shift; PORT="$1" ;;
        --map)  shift; TARGET="$1" ;;
        --help|-h) usage; exit 0 ;;
        *) echo "Unknown arg: $1"; usage; exit 1 ;;
    esac
    shift
done

# Find a python with the carla module
find_python() {
    for cand in \
        "${CARLAAIR_DIR}/.venv/bin/python3" \
        "${HOME}/miniconda3/envs/carlaAir/bin/python3" \
        "${HOME}/anaconda3/envs/carlaAir/bin/python3"; do
        if [ -x "${cand}" ] && "${cand}" -c "import carla" 2>/dev/null; then
            echo "${cand}"; return
        fi
    done
    if command -v python3 &>/dev/null && python3 -c "import carla" 2>/dev/null; then
        echo "python3"; return
    fi
    echo ""
}

PY="$(find_python)"
if [ -z "${PY}" ]; then
    echo "ERROR: no python3 with the 'carla' module found." >&2
    echo "  Activate the carlaAir env first: conda activate carlaAir" >&2
    exit 1
fi

"${PY}" - "${PORT}" "${TARGET}" "${TIMEOUT}" <<'PYEOF'
import sys, time, carla

port, target, timeout = int(sys.argv[1]), sys.argv[2], float(sys.argv[3])

client = carla.Client("localhost", port)
client.set_timeout(10.0)

try:
    world = client.get_world()
    current = world.get_map().name
    print(f"Current map: {current}")
except Exception as e:
    print(f"ERROR: cannot reach CarlaAir on port {port}: {e}")
    sys.exit(1)

available = sorted(set(client.get_available_maps()))
match = None
if target in available:
    match = target
else:
    for m in available:
        if m.endswith("/" + target) or m.split("/")[-1] == target:
            match = m
            break
if match is None:
    print(f"ERROR: '{target}' not in available maps.")
    print("  Available:")
    for m in available:
        print(f"    {m}")
    sys.exit(1)

print(f"Resolved target: {match}")

# Cleanup before load_world (sensors and spawned actors can stall the load)
n = 0
for filt in ("sensor.*", "vehicle.*", "walker.*"):
    for a in world.get_actors().filter(filt):
        try:
            if filt == "sensor.*":
                a.stop()
            a.destroy()
            n += 1
        except Exception:
            pass
print(f"Cleaned {n} actors")

# Force async mode (load_world deadlocks in sync mode)
s = world.get_settings()
if s.synchronous_mode:
    s.synchronous_mode = False
    s.fixed_delta_seconds = None
    world.apply_settings(s)
    time.sleep(0.5)

print(f"Loading {match} (this can take a few minutes for HD maps)...")
client.set_timeout(timeout)
t0 = time.time()
try:
    client.load_world(match)
except RuntimeError as e:
    print(f"  load_world raised: {e} (verifying...)")

deadline = time.time() + 120
while time.time() < deadline:
    try:
        world = client.get_world()
        sps = world.get_map().get_spawn_points()
        if sps:
            break
    except Exception:
        pass
    time.sleep(0.5)
else:
    print("ERROR: world did not become ready")
    sys.exit(1)

loaded = world.get_map().name
elapsed = time.time() - t0
print(f"Loaded {loaded} in {elapsed:.1f}s ({len(sps)} spawn points)")

if loaded == current:
    print("WARNING: map name unchanged — server may have silently fallen back.")
    sys.exit(2)
PYEOF
