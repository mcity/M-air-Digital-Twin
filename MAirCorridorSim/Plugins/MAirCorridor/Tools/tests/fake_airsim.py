"""fake_airsim.py - just enough of the Project AirSim client to fly fly_mission.py without a sim.

WHY THIS EXISTS. The control loop in fly_mission.py (a route running as one task, a monitor beside
it, a contingency that cancels the route and takes over) is exactly the part that cannot be seen
working without a simulator, and a simulator is an editor in Play mode on a big GPU. This stands in
for the client: a drone that moves towards where it is told at the speed it is told, publishes its
pose twenty times a second, and can be pushed off course or made to go silent, which are the two
things the loop exists to catch.

It imitates the client's calling convention, not its physics. Commands are coroutines returning a
task, as the real ones are, so `await (await drone.move_to_position_async(...))` reads the same.

Install it in place of the real package with install(), before fly_mission imports projectairsim.
"""
import asyncio
import math
import sys
import types


class FakeClient:
    def __init__(self, address="127.0.0.1"):
        self.address = address
        self.subscribers = {}

    def connect(self):
        pass

    def subscribe(self, topic, callback):
        self.subscribers.setdefault(topic, []).append(callback)

    def unsubscribe_all(self):
        self.subscribers = {}

    def disconnect(self):
        pass

    def publish(self, topic, message):
        for callback in list(self.subscribers.get(topic, [])):
            callback(topic, message)


class FakeWorld:
    def __init__(self, client, scene, delay_after_load_sec=0, sim_config_path=None):
        self.client = client
        self.scene = scene
        self.sim_config_path = sim_config_path

    def get_configuration(self):
        return {"actors": [{"name": "Drone1", "type": "robot", "robot-config": {"sensors": []}}]}

    # The scene loads paused, as fly_mission stages it, and the ground is there at once: the
    # start is put 0.75 m above it, as flightplan.START_CLEARANCE_M puts a start on the ground.
    paused = True

    def is_paused(self):
        return self.paused

    def resume(self):
        self.paused = False

    def get_surface_elevation_at_point(self, x, y):
        return (FakeDrone.spawn or (0.0, 0.0, 0.0))[2] + 0.75


class FakeDrone:
    """A point that flies in straight lines, with knobs for the things that go wrong.

    wind      metres a second of drift added to every move, as (north, east)
    silent_at seconds after takeoff at which it stops reporting its position, or None
    """

    RATE_HZ = 20.0

    def __init__(self, client, world, name, start=(0.0, 0.0, 0.0)):
        self.client = client
        self.name = name
        self.sensors = {}
        self.robot_info = {"actual_pose": "pose", "collision_info": "collision",
                           "rotor_info": "rotor"}
        self.position = list(FakeDrone.spawn or start)
        self.home = tuple(self.position)
        self.target = None
        self.speed = 0.0
        self.flown_s = 0.0
        self.commands = []
        self._pump = None

    # Knobs, set on the class by a test before the runner creates its drone.
    spawn = None
    wind = (0.0, 0.0)
    silent_at = None

    # ---- the background loop that moves it and reports where it is ---------------------------
    def _ensure_running(self):
        if self._pump is None:
            self._pump = asyncio.get_event_loop().create_task(self._run())

    async def _run(self):
        dt = 1.0 / self.RATE_HZ
        try:
            while True:
                await asyncio.sleep(dt)
                self.flown_s += dt
                if self.target is not None:
                    step = [t - p for t, p in zip(self.target, self.position)]
                    dist = math.sqrt(sum(c * c for c in step))
                    move = min(dist, self.speed * dt)
                    if dist > 1e-6:
                        self.position = [p + c / dist * move for p, c in zip(self.position, step)]
                # Wind pushes it only while it is flying the route. A contingency hovers or goes
                # home, then descends in moves and lands, and the stand-in's controller is assumed
                # to hold station against wind from then on; a stand-in that drifted away during a
                # descent would never finish one.
                taken_over = "hover" in self.commands or "go_home" in self.commands
                if self.commands and self.commands[-1] == "move" and not taken_over:
                    self.position[0] += FakeDrone.wind[0] * dt
                    self.position[1] += FakeDrone.wind[1] * dt
                if FakeDrone.silent_at is not None and self.flown_s >= FakeDrone.silent_at:
                    continue
                self.client.publish("pose", {
                    "time_stamp": int(self.flown_s * 1e9),
                    "position": {"x": self.position[0], "y": self.position[1],
                                 "z": self.position[2]}})
        except asyncio.CancelledError:
            pass

    async def _go(self, target, speed, label):
        """Fly towards a point until close, ignoring wind for arrival so a move can finish."""
        self._ensure_running()
        self.commands.append(label)
        self.target = list(target)
        self.speed = speed
        while True:
            gap = math.dist([self.target[0], self.target[1]],
                            [self.position[0], self.position[1]])
            if gap < max(1.0, speed * 0.2) and abs(self.target[2] - self.position[2]) < 1.0:
                return True
            await asyncio.sleep(0.05)

    def _task(self, coro):
        return asyncio.get_event_loop().create_task(coro)

    # ---- the client's interface ----------------------------------------------------------------
    def enable_api_control(self):
        self.commands.append("enable_api_control")

    def disable_api_control(self):
        self.commands.append("disable_api_control")

    def arm(self):
        self.commands.append("arm")

    def disarm(self):
        self.commands.append("disarm")

    def get_ground_truth_kinematics(self):
        return {"pose": {"position": {"x": self.position[0], "y": self.position[1],
                                      "z": self.position[2]},
                         "orientation": {"w": 1.0, "x": 0.0, "y": 0.0, "z": 0.0}}}

    def set_pose(self, pose, reset_kinematics=True):
        t = pose["translation"]
        self.position = [t["x"], t["y"], t["z"]]
        return True

    async def move_by_velocity_async(self, v_north, v_east, v_down, duration=0.001, **_kw):
        self.commands.append("hold")
        self.target = list(self.position)

        async def done():
            return True
        return self._task(done())

    async def takeoff_async(self, timeout_sec=20, callback=None):
        up = (self.position[0], self.position[1], self.position[2] - 3.0)
        return self._task(self._go(up, 3.0, "takeoff"))

    async def move_to_position_async(self, north, east, down, velocity, timeout_sec=3e38,
                                     yaw_control_mode=0, yaw_is_rate=True, yaw=0.0,
                                     lookahead=-1, adaptive_lookahead=1, callback=None):
        return self._task(self._go((north, east, down), velocity, "move"))

    async def hover_async(self, callback=None):
        self.commands.append("hover")
        self.target = list(self.position)

        async def done():
            return True
        return self._task(done())

    async def land_async(self, timeout_sec=3e38, callback=None):
        ground = (self.position[0], self.position[1], self.home[2])
        return self._task(self._go(ground, 3.0, "land"))

    async def go_home_async(self, timeout_sec=60, velocity=0.5, callback=None):
        return self._task(self._go(self.home, velocity, "go_home"))

    def stop(self):
        if self._pump:
            self._pump.cancel()


class YawControlMode:
    MaxDegreeOfFreedom = 0
    ForwardOnly = 1


def install():
    """Put this in sys.modules as projectairsim, so the runner imports it instead."""
    package = types.ModuleType("projectairsim")
    package.ProjectAirSimClient = FakeClient
    package.World = FakeWorld
    package.Drone = FakeDrone
    drone_module = types.ModuleType("projectairsim.drone")
    drone_module.YawControlMode = YawControlMode
    package.drone = drone_module
    types_module = types.ModuleType("projectairsim.types")
    types_module.Pose = types_module.Quaternion = types_module.Vector3 = dict
    package.types = types_module
    package.__path__ = []                    # a package, so its submodules import
    sys.modules["projectairsim"] = package
    sys.modules["projectairsim.drone"] = drone_module
    sys.modules["projectairsim.types"] = types_module
    return package
