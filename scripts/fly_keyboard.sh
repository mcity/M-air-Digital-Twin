#!/bin/bash
# Fly on the keyboard. The simulator must be running. Keys are read whichever window has focus.
. "$(dirname "$0")/_env.sh"
export PYTHONPATH="$REPO/scripts/keyboard_shim:$PYTHONPATH"
exec "$MAIR_PYTHON" -u "$MAIR_PLUGIN/AirSim/fly_mcity.py" "$@"
