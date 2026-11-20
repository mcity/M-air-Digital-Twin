"""Run one of the Python tools against the simulator's ports.

    python run_tool.py <tool.py> [its arguments]

Project AirSim's client defaults to ports 8989/8990 and the tools do not expose them, so this sets
the defaults from AIRSIM_TOPICS_PORT / AIRSIM_SERVICES_PORT and then runs the tool unchanged.
"""
import os
import runpy
import sys

import projectairsim.client as client

client.ProjectAirSimClient.__init__.__defaults__ = (
    os.environ.get("AIRSIM_ADDRESS", "127.0.0.1"),
    int(os.environ.get("AIRSIM_TOPICS_PORT", 8989)),
    int(os.environ.get("AIRSIM_SERVICES_PORT", 8990)),
)
tool = os.path.abspath(sys.argv[1])
sys.argv = sys.argv[1:]
sys.path.insert(0, os.path.dirname(tool))
runpy.run_path(tool, run_name="__main__")
