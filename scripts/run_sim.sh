#!/bin/bash
# Start the simulator on the corridor level. Leave it running and fly from a second terminal.
#   scripts/run_sim.sh                      a 1280x720 window
#   scripts/run_sim.sh -ExecCmds="stat fps" show the frame rate
#   scripts/run_sim.sh -RenderOffScreen     no window
#   MAIR_RAYTRACING=1 scripts/run_sim.sh    allow hardware ray tracing (see docs/TROUBLESHOOTING.md)
. "$(dirname "$0")/_env.sh"
RT="-noraytracing"; [ -n "${MAIR_RAYTRACING:-}" ] && RT=""
exec "$UE_ROOT/Engine/Binaries/Linux/UnrealEditor" "$MAIR_PROJECT" \
    "/MAirCorridor/Scene/CorridorTerrain?game=/Script/ProjectAirSim.ProjectAirSimGameMode" \
    -game -windowed -ResX=1280 -ResY=720 $RT \
    -topicsport="$AIRSIM_TOPICS_PORT" -servicesport="$AIRSIM_SERVICES_PORT" "$@"
