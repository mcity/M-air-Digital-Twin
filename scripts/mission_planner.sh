#!/bin/bash
# Draw a mission on a map (the plugin's flight planner). Needs a desktop session.
. "$(dirname "$0")/_env.sh"
exec "$MAIR_PYTHON" -u "$MAIR_PLUGIN/Tools/flightplan_ui.py" "$@"
