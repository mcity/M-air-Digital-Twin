#!/bin/bash
# Open the project in the Unreal Editor (press Play there to start the simulator).
. "$(dirname "$0")/_env.sh"
exec "$UE_ROOT/Engine/Binaries/Linux/UnrealEditor" "$MAIR_PROJECT" "$@"
