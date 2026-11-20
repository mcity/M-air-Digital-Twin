#!/bin/bash
# A one-minute check that everything works: spawn on the ground, take off, move, land.
. "$(dirname "$0")/_env.sh"
exec "$MAIR_PYTHON" -u "$REPO/scripts/run_tool.py" "$REPO/scripts/hover_test.py" "$@"
