#!/bin/bash
# Fly a mission file: a list of waypoints, no keyboard. The simulator must be running.
#   scripts/fly_mission.sh missions/mcity_circle.json --dry-run        check the route, fly nothing
#   scripts/fly_mission.sh missions/mcity_circle.json
#   scripts/fly_mission.sh missions/mcity_circle.json --record Chase   and record the chase camera
. "$(dirname "$0")/_env.sh"
exec "$MAIR_PYTHON" -u "$REPO/scripts/run_tool.py" "$MAIR_PLUGIN/Tools/fly_mission.py" "$@"
