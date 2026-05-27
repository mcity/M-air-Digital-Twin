#!/bin/bash
# ============================================
#  M-Air Digital Twin :: install.sh
#  Integrates the McityMap digital twin into a stock CarlaAir v0.1.7 install.
#
#  Actions:
#    1. Symlinks M-Air_DigitalTwin/McityMap -> CarlaUE4/Content/McityMap
#    2. Patches CarlaUE4/Config/DefaultGame.ini with cook entries
#       (a timestamped backup is written before any edit)
#
#  No CarlaAir source files are modified outside the steps above, and the
#  patch is reversible via uninstall.sh.
# ============================================

set -e

DT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
CARLAAIR_DIR="$(cd "${DT_DIR}/.." && pwd)"
CONTENT_DIR="${CARLAAIR_DIR}/CarlaUE4/Content"
CONFIG_FILE="${CARLAAIR_DIR}/CarlaUE4/Config/DefaultGame.ini"
MAP_SRC="${DT_DIR}/McityMap"
MAP_LINK="${CONTENT_DIR}/McityMap"
PATCH_MARK_BEGIN="# === M-Air DT McityMap entries BEGIN ==="
PATCH_MARK_END="# === M-Air DT McityMap entries END ==="

echo "M-Air Digital Twin installer"
echo "  CarlaAir root : ${CARLAAIR_DIR}"
echo "  DT root       : ${DT_DIR}"
echo ""

# --- 1. Verify CarlaAir layout ---
if [ ! -d "${CONTENT_DIR}" ]; then
    echo "ERROR: ${CONTENT_DIR} not found."
    echo "  Run this script from inside a CarlaAir-v0.1.7 install."
    exit 1
fi
if [ ! -f "${CONFIG_FILE}" ]; then
    echo "ERROR: ${CONFIG_FILE} not found."
    exit 1
fi
if [ ! -d "${MAP_SRC}" ]; then
    echo "ERROR: McityMap assets not found at ${MAP_SRC}"
    exit 1
fi
if [ ! -f "${MAP_SRC}/McityMap_Main.umap" ]; then
    echo "ERROR: ${MAP_SRC}/McityMap_Main.umap missing — is the asset complete?"
    exit 1
fi

# --- 2. Symlink the map into Content/ ---
echo "[1/2] Linking McityMap into CarlaUE4/Content/..."
if [ -L "${MAP_LINK}" ]; then
    EXISTING="$(readlink -f "${MAP_LINK}")"
    if [ "${EXISTING}" = "$(readlink -f "${MAP_SRC}")" ]; then
        echo "  Already linked correctly. Skipping."
    else
        echo "  Existing symlink points elsewhere: ${EXISTING}"
        echo "  Removing and re-creating."
        rm "${MAP_LINK}"
        ln -s "${MAP_SRC}" "${MAP_LINK}"
        echo "  Linked: ${MAP_LINK} -> ${MAP_SRC}"
    fi
elif [ -e "${MAP_LINK}" ]; then
    echo "  ERROR: ${MAP_LINK} exists but is not a symlink."
    echo "  Move or remove it manually, then re-run install."
    exit 1
else
    ln -s "${MAP_SRC}" "${MAP_LINK}"
    echo "  Linked: ${MAP_LINK} -> ${MAP_SRC}"
fi

# --- 3. Patch DefaultGame.ini (backup first) ---
echo ""
echo "[2/2] Patching CarlaUE4/Config/DefaultGame.ini..."

if grep -q "${PATCH_MARK_BEGIN}" "${CONFIG_FILE}"; then
    echo "  Patch markers already present. Skipping."
else
    BACKUP="${CONFIG_FILE}.bak.$(date +%Y%m%d_%H%M%S)"
    cp "${CONFIG_FILE}" "${BACKUP}"
    echo "  Backup: ${BACKUP}"

    # Insert the new entries after the [/Script/UnrealEd.ProjectPackagingSettings]
    # block's existing +MapsToCook lines. We append the patch immediately before
    # the bNativizeBlueprintAssets line, which is the stable closing tag of that
    # section in CarlaAir v0.1.7.
    PATCH_FILE="${DT_DIR}/config/DefaultGame.ini.patch"
    if [ ! -f "${PATCH_FILE}" ]; then
        echo "  ERROR: patch file missing: ${PATCH_FILE}"
        exit 1
    fi

    awk -v patch="${PATCH_FILE}" -v begin="${PATCH_MARK_BEGIN}" -v end="${PATCH_MARK_END}" '
        /^bNativizeBlueprintAssets=/ && !done {
            print begin
            while ((getline line < patch) > 0) print line
            close(patch)
            print end
            done = 1
        }
        { print }
    ' "${CONFIG_FILE}" > "${CONFIG_FILE}.tmp"

    if ! grep -q "${PATCH_MARK_BEGIN}" "${CONFIG_FILE}.tmp"; then
        echo "  ERROR: failed to find anchor in DefaultGame.ini."
        echo "  No changes written. Backup preserved at ${BACKUP}."
        rm -f "${CONFIG_FILE}.tmp"
        exit 1
    fi

    mv "${CONFIG_FILE}.tmp" "${CONFIG_FILE}"
    echo "  Patched. Restore via: ./scripts/uninstall.sh"
fi

# --- 4. Done ---
echo ""
echo "Install complete."
echo ""
echo "Launch with:"
echo "  ./M-Air_DigitalTwin/scripts/run-mcity.sh"
echo ""
echo "Or live-switch on a running CarlaAir:"
echo "  ./M-Air_DigitalTwin/scripts/switch-to-mcity.sh"
