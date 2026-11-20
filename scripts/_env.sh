# Sourced by the other scripts: loads what install.py wrote.
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
if [ ! -f "$REPO/maircorridor.env" ]; then
    echo "maircorridor.env not found. Run install.py first (see README.md)." >&2
    exit 1
fi
set -a
. "$REPO/maircorridor.env"
set +a
export PYTHONUNBUFFERED=1
# Project AirSim's client is used from its source tree.
export PYTHONPATH="$PROJECTAIRSIM_ROOT/client/python/projectairsim/src${PYTHONPATH:+:$PYTHONPATH}"
# Ports the simulator listens on. Change both here and for run_sim.sh if 8989/8990 are taken.
export AIRSIM_TOPICS_PORT="${AIRSIM_TOPICS_PORT:-8989}"
export AIRSIM_SERVICES_PORT="${AIRSIM_SERVICES_PORT:-8990}"
