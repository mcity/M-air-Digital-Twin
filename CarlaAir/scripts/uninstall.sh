#!/bin/bash
# ============================================
#  M-Air Digital Twin :: uninstall.sh
#  Reverses install.sh:
#    1. Removes the symlink CarlaUE4/Content/McityMap (only if symlink)
#    2. Strips the patch block from CarlaUE4/Config/DefaultGame.ini
#       (and offers to restore the most recent .bak if found)
# ============================================

set -e

DT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
CARLAAIR_DIR="$(cd "${DT_DIR}/.." && pwd)"
CONTENT_DIR="${CARLAAIR_DIR}/CarlaUE4/Content"
CONFIG_FILE="${CARLAAIR_DIR}/CarlaUE4/Config/DefaultGame.ini"
MAP_LINK="${CONTENT_DIR}/McityMap"
PATCH_MARK_BEGIN="# === M-Air DT McityMap entries BEGIN ==="
PATCH_MARK_END="# === M-Air DT McityMap entries END ==="

echo "M-Air Digital Twin uninstaller"
echo ""

# --- 1. Remove symlink ---
echo "[1/2] Removing Content/McityMap link..."
if [ -L "${MAP_LINK}" ]; then
    rm "${MAP_LINK}"
    echo "  Removed symlink: ${MAP_LINK}"
elif [ -d "${MAP_LINK}" ]; then
    echo "  ${MAP_LINK} is a real directory (not a symlink)."
    echo "  Leaving it untouched. Delete manually if intentional."
else
    echo "  Nothing to remove."
fi

# --- 2. Strip the patch block ---
echo ""
echo "[2/2] Cleaning DefaultGame.ini..."
if [ -f "${CONFIG_FILE}" ] && grep -q "${PATCH_MARK_BEGIN}" "${CONFIG_FILE}"; then
    BACKUP="${CONFIG_FILE}.bak.$(date +%Y%m%d_%H%M%S).pre-uninstall"
    cp "${CONFIG_FILE}" "${BACKUP}"
    echo "  Backup: ${BACKUP}"

    awk -v begin="${PATCH_MARK_BEGIN}" -v end="${PATCH_MARK_END}" '
        $0 == begin { skipping = 1; next }
        $0 == end   { skipping = 0; next }
        !skipping
    ' "${CONFIG_FILE}" > "${CONFIG_FILE}.tmp"
    mv "${CONFIG_FILE}.tmp" "${CONFIG_FILE}"
    echo "  Patch block removed."
else
    echo "  No patch markers found. Nothing to strip."
fi

LATEST_BAK="$(ls -t "${CONFIG_FILE}".bak.* 2>/dev/null | grep -v 'pre-uninstall' | head -1)"
if [ -n "${LATEST_BAK}" ]; then
    echo ""
    echo "  An install-era backup is available: ${LATEST_BAK}"
    echo "  To fully restore the original DefaultGame.ini, run:"
    echo "    cp \"${LATEST_BAK}\" \"${CONFIG_FILE}\""
fi

echo ""
echo "Uninstall complete."
