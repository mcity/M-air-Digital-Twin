#!/bin/bash
# setup_mcity_env.sh - Integrate the McityMap environment into an existing
# Project AirSim source tree.
#
# Usage:
#   export UE_ROOT=/path/to/UnrealEngine-5.7
#   ./setup_mcity_env.sh /path/to/your/projectairsim/repo
#
# What it does (see README.md "Manual installation" for the same steps):
#   1. Creates <repo>/unreal/McityMap as a sibling project of Blocks,
#      reusing YOUR repo's own project files (uproject/Config/Source) so it
#      always matches your Project AirSim version.
#   2. Symlinks the ProjectAirSim plugin from Blocks (shared build).
#   3. Copies the McityMap content (UE 5.7, geo-aligned, north-corrected).
#   4. Builds the McityMap editor target.

set -e

PKG_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$1"

fail() { echo "ERROR: $1" >&2; exit 1; }

# ---- Preflight checks -------------------------------------------------------
[ -n "$REPO" ] || fail "Usage: ./setup_mcity_env.sh /path/to/projectairsim/repo"
REPO="$(cd "$REPO" 2>/dev/null && pwd)" || fail "Repo path not found: $1"

[ -f "$REPO/unreal/Blocks/Blocks.uproject" ] \
    || fail "$REPO does not look like a Project AirSim repo (missing unreal/Blocks/Blocks.uproject)"

[ -n "$UE_ROOT" ] || fail "UE_ROOT is not set. Export it to your Unreal Engine 5.7 install path."
[ -x "$UE_ROOT/Engine/Binaries/Linux/UnrealEditor" ] \
    || fail "UnrealEditor not found under UE_ROOT=$UE_ROOT"

UE_MINOR=$(grep -o '"MinorVersion": [0-9]*' "$UE_ROOT/Engine/Build/Build.version" | grep -o '[0-9]*' || echo "?")
if [ "$UE_MINOR" != "7" ]; then
    echo "WARNING: McityMap content was saved with UE 5.7.x; your engine reports 5.$UE_MINOR." >&2
    echo "         Older engines (e.g. 5.2) CANNOT load it." >&2
fi

[ -d "$REPO/unreal/Blocks/Plugins/ProjectAirSim/SimLibs/core_sim" ] \
    || fail "Sim libs not built yet. Run './build.sh simlibs_release' in $REPO first."

[ ! -e "$REPO/unreal/McityMap" ] \
    || fail "$REPO/unreal/McityMap already exists. Remove it first if you want a fresh install."

# ---- 1. Project scaffold (from the user's own Blocks project) ---------------
echo "==> Creating $REPO/unreal/McityMap ..."
mkdir -p "$REPO/unreal/McityMap"
cd "$REPO/unreal/McityMap"

cp ../Blocks/Blocks.uproject McityMap.uproject
cp -r ../Blocks/Config Config
cp Config/DefaultEngine.ini Config/DefaultEngine_orig.ini   # untouched backup
cp -r ../Blocks/Source Source

# Point the default maps at McityMap
sed -i \
    -e 's|EditorStartupMap=/Game/BlocksMap|EditorStartupMap=/Game/McityMap/McityMap_Main|' \
    -e 's|GameDefaultMap=/Game/BlocksMap|GameDefaultMap=/Game/McityMap/McityMap_Main|' \
    -e 's|ServerDefaultMap=/Game/BlocksMap|ServerDefaultMap=/Game/McityMap/McityMap_Main|' \
    Config/DefaultEngine.ini

# ---- 2. Shared ProjectAirSim plugin ------------------------------------------
ln -s ../Blocks/Plugins Plugins

# ---- 3. Map content ----------------------------------------------------------
echo "==> Copying McityMap content (~1 GB) ..."
cp -r "$PKG_DIR/McityMap/Content" Content

# ---- 4. Build the editor target ----------------------------------------------
echo "==> Building McityMap editor target (BlocksEditor, Development) ..."
"$UE_ROOT/Engine/Build/BatchFiles/Linux/Build.sh" BlocksEditor Linux Development \
    -project="$REPO/unreal/McityMap/McityMap.uproject"

echo
echo "=========================================================================="
echo " McityMap installed."
echo
echo " Launch the editor with:"
echo "   \"\$UE_ROOT/Engine/Binaries/Linux/UnrealEditor\" \\"
echo "       \"$REPO/unreal/McityMap/McityMap.uproject\""
echo
echo " Then follow README.md 'Run & verify' to fly with keyboard_control_gnss.py."
echo " Optional: see README.md 'Optional: live Google-Maps view' to watch the"
echo " drone live at http://localhost:8080 (needs a Google Maps API key)."
echo "=========================================================================="
