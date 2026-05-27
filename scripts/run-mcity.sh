#!/bin/bash
# ============================================
#  M-Air Digital Twin :: run-mcity.sh
#  Boots CarlaAir using the stock launcher with Town10HD, then RPC-switches
#  the running world to McityMap_Main via CARLA's Python API.
#
#  Why the indirection: CarlaAir-v0.1.7's UE4 shipping binary resolves
#  command-line map names only against /Game/Carla/Maps/. Maps shipped under
#  any other package path (like /Game/McityMap/) must be swapped at runtime
#  via load_world() instead of passed on the command line.
#
#  This script does NOT modify CarlaAir.sh — it wraps it.
# ============================================

set -e

DT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
CARLAAIR_DIR="$(cd "${DT_DIR}/.." && pwd)"
LAUNCHER="${CARLAAIR_DIR}/CarlaAir.sh"
SWITCHER="${DT_DIR}/scripts/switch-to-mcity.sh"
MAP="McityMap_Main"
BOOT_MAP="Town10HD"

if [ ! -x "${LAUNCHER}" ]; then
    echo "ERROR: ${LAUNCHER} not found or not executable."
    exit 1
fi
if [ ! -L "${CARLAAIR_DIR}/CarlaUE4/Content/McityMap" ] && \
   [ ! -d "${CARLAAIR_DIR}/CarlaUE4/Content/McityMap" ]; then
    echo "ERROR: CarlaUE4/Content/McityMap is missing."
    echo "  Run: ${DT_DIR}/scripts/install.sh"
    exit 1
fi

echo "============================================"
echo "  M-Air Digital Twin Launcher"
echo "    Booting ${BOOT_MAP}, will RPC-switch to ${MAP}"
echo "============================================"
echo ""

# Boot CarlaAir using the stock launcher (pass through any extra flags)
"${LAUNCHER}" "${BOOT_MAP}" "$@"

# Stock launcher returns once ports are ready and traffic has spawned.
# Now switch to McityMap_Main. switch-to-mcity.sh handles the cleanup +
# load_world dance and verifies that the map actually changed.
echo ""
echo "Switching world to ${MAP}..."
"${SWITCHER}"
