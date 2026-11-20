"""hover_test.py - the shortest proof that the environment works end to end.

Loads the M-City scene, takes control of the drone where it spawns (in the air over the test
track), holds a hover, flies 20 m north, and reports PASS or FAIL. Run it with scripts/hover_test.sh
while the simulator is running. It is also a small example of driving the drone from your own code.
"""
import asyncio
import glob
import logging
import os
import shutil
import sys
import tempfile

from projectairsim import Drone, ProjectAirSimClient, World
from projectairsim.utils import projectairsim_log

projectairsim_log().setLevel(logging.WARNING)


def sim_config_dir():
    """Our scene config beside the stock robot config it names: Project AirSim resolves
    "robot-config" relative to the folder the scene is in."""
    folder = tempfile.mkdtemp(prefix="maircorridor_")
    stock = os.path.join(os.environ["PROJECTAIRSIM_ROOT"], "client", "python", "example_user_scripts",
                         "sim_config")
    ours = os.path.join(os.environ["MAIR_PLUGIN"], "AirSim", "sim_config")
    for source in (stock, ours):
        for path in glob.glob(os.path.join(source, "*.jsonc")):
            shutil.copy2(path, folder)
    return folder


async def main():
    client = ProjectAirSimClient()
    client.connect()
    ok = False
    try:
        world = World(client, "scene_mcity.jsonc", delay_after_load_sec=2,
                      sim_config_path=sim_config_dir())
        drone = Drone(client, world, "Drone1")

        def position():
            p = drone.get_ground_truth_kinematics()["pose"]["position"]
            return p["x"], p["y"], p["z"]

        drone.enable_api_control()
        drone.arm()
        task = await drone.move_by_velocity_async(v_north=0.0, v_east=0.0, v_down=0.0, duration=3.0)
        await task                                    # let it stop falling and settle
        north0, east0, down0 = position()
        task = await drone.move_by_velocity_async(v_north=0.0, v_east=0.0, v_down=0.0, duration=5.0)
        await task
        north1, east1, down1 = position()
        print("hover: north %.1f east %.1f down %.1f, drifted %.2f m vertically in 5 s"
              % (north1, east1, down1, abs(down1 - down0)))
        task = await drone.move_by_velocity_async(v_north=5.0, v_east=0.0, v_down=0.0, duration=4.0)
        await task
        north2, _east2, _down2 = position()
        print("moved %.1f m north in 4 s at 5 m/s" % (north2 - north1))
        ok = abs(down1 - down0) < 2.0 and 10.0 < (north2 - north1) < 30.0
    finally:
        client.disconnect()
    print("PASS" if ok else "FAIL")
    sys.exit(0 if ok else 1)


asyncio.run(main())
