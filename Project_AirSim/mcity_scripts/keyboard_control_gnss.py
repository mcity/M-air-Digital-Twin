import argparse
import asyncio
import json
import os
import socket
import threading
import time

import cv2
import numpy as np
import projectairsim
from projectairsim import Drone, World
from projectairsim.utils import unpack_image

try:
    from Xlib import X
    from Xlib.display import Display
except ImportError:
    raise SystemExit(
        "python-xlib is required for window-scoped keyboard input. Install it with:\n"
        "    pip install python-xlib"
    )

# --- Shared state updated by topic callbacks (pub-sub receiving thread) ---

latest_gps = None  # latest GPS message dict from the drone's GPS sensor
latest_frame = None  # latest decoded chase camera frame (OpenCV BGR array)
frame_lock = threading.Lock()

GNSS_WINDOW = "Chase Cam + GNSS"

# Relay GPS fixes to the Mcity live-map bridge (mcity_scripts/gps_ws_server.py)
# as fire-and-forget UDP datagrams. The sim's topics channel is 1:1 (nng
# Pair0), so the map bridge can't connect to the sim itself - this script is
# the sole sim client and forwards the data instead.
GPS_BEACON_ADDR = ("127.0.0.1", 9092)
gps_beacon_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)


def send_gps_beacon(gps):
    """Best-effort relay of a GPS fix to the map bridge. Never raises."""
    try:
        vel = gps.get("velocity") or {}
        fix = {
            "name": "Drone1",
            "lat": gps.get("latitude"),
            "lon": gps.get("longitude"),
            "alt": gps.get("altitude"),
            "vel": [vel.get("x"), vel.get("y"), vel.get("z")],
            "eph": gps.get("eph"),
            "fix_type": gps.get("fix_type"),
        }
        gps_beacon_sock.sendto(json.dumps(fix).encode(), GPS_BEACON_ADDR)
    except Exception:
        pass  # the map is optional - flying must never be affected


def on_gps_message(_, gps):
    """Stores the latest GPS data. Message fields include:
    time_stamp, time_utc_millis, latitude, longitude, altitude, epv, eph,
    position_cov_type, fix_type, velocity
    """
    global latest_gps
    latest_gps = gps
    send_gps_beacon(gps)


def on_chase_image(_, image_msg):
    """Decodes the chase camera image and stores the latest frame."""
    global latest_frame
    frame = unpack_image(image_msg)
    with frame_lock:
        latest_frame = frame


# --- Window-scoped keyboard input ---
#
# True key press/release state (like keyboard.is_pressed) is polled from the
# X server via XQueryKeymap, but it is only honored while the GNSS window has
# input focus - so typing in the browser or terminal never reaches the drone,
# and releasing a key stops the drone immediately. No root/sudo is needed
# (unlike the `keyboard` library, which hooks /dev/input system-wide).

class WindowScopedKeys:
    """Polls held keys from the X server, gated on a window title having focus."""

    # X keysyms we care about -> key names used by the control loop
    KEYSYM_NAMES = {
        ord("w"): "w", ord("s"): "s", ord("a"): "a", ord("d"): "d",
        ord("l"): "l", ord("q"): "q",
        65362: "up", 65364: "down", 65361: "left", 65363: "right",  # XK_ arrows
    }

    def __init__(self, window_title):
        self.window_title = window_title
        self.display = Display()
        self.net_wm_name = self.display.intern_atom("_NET_WM_NAME")
        # keycode -> key name, built once from this X server's keyboard mapping
        self.keycode_names = {}
        for keycode in range(8, 256):
            keysym = self.display.keycode_to_keysym(keycode, 0)
            if keysym in self.KEYSYM_NAMES:
                self.keycode_names[keycode] = self.KEYSYM_NAMES[keysym]

    def _window_name(self, win):
        try:
            prop = win.get_full_property(self.net_wm_name, 0)
            if prop and prop.value:
                value = prop.value
                return value.decode("utf-8", "replace") if isinstance(value, bytes) else str(value)
            return win.get_wm_name() or None
        except Exception:
            return None

    def _has_focus(self):
        try:
            win = self.display.get_input_focus().focus
            # Input focus may be on an unnamed child; walk up to a titled ancestor
            for _ in range(16):
                if isinstance(win, int):  # X.NONE / X.PointerRoot
                    return False
                if self._window_name(win) == self.window_title:
                    return True
                win = win.query_tree().parent
        except Exception:
            pass
        return False

    def poll(self):
        """Returns the set of key names currently held down, or an empty set
        when the GNSS window does not have focus (keys are then ignored)."""
        if not self._has_focus():
            return set()
        try:
            keymap = self.display.query_keymap()  # 256-bit keycode bitmask
        except Exception:
            return set()
        held = set()
        for keycode, name in self.keycode_names.items():
            if keymap[keycode // 8] & (1 << (keycode % 8)):
                held.add(name)
        return held


def draw_gnss_overlay(frame, gps):
    """Draws the GNSS data block onto the camera frame."""
    if gps is None:
        lines = ["GNSS: waiting for GPS fix..."]
    else:
        lines = [
            f"Lat: {gps['latitude']:.7f} deg",
            f"Lon: {gps['longitude']:.7f} deg",
            f"Alt: {gps['altitude']:.2f} m",
        ]
        velocity = gps.get("velocity")
        if velocity is not None:
            lines.append(
                "Vel NED: "
                f"({velocity['x']:.1f}, {velocity['y']:.1f}, {velocity['z']:.1f}) m/s"
            )

    font = cv2.FONT_HERSHEY_SIMPLEX
    scale = 0.55
    thickness = 1
    line_height = 22
    pad = 8

    # Semi-transparent background box for readability
    box_w = 360
    box_h = pad * 2 + line_height * len(lines)
    overlay = frame.copy()
    cv2.rectangle(overlay, (0, 0), (box_w, box_h), (0, 0, 0), -1)
    cv2.addWeighted(overlay, 0.5, frame, 0.5, 0, frame)

    for i, line in enumerate(lines):
        y = pad + line_height * (i + 1) - 6
        cv2.putText(
            frame, line, (pad, y), font, scale, (0, 255, 0), thickness, cv2.LINE_AA
        )
    return frame


def show_gnss_frame():
    """Renders the latest camera frame with the GNSS overlay (call from main loop)."""
    with frame_lock:
        frame = None if latest_frame is None else latest_frame.copy()
    if frame is None:
        # Placeholder so the window exists (and can take key focus) before
        # the first chase-camera frame arrives.
        frame = np.zeros((480, 854, 3), dtype=np.uint8)
        cv2.putText(
            frame, "Waiting for chase camera...", (280, 250),
            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (200, 200, 200), 1, cv2.LINE_AA,
        )
    frame = draw_gnss_overlay(frame, latest_gps)
    cv2.imshow(GNSS_WINDOW, frame)
    cv2.waitKey(1)  # pump the OpenCV GUI event loop


def gnss_window_closed():
    """True if the user closed the GNSS window (our only input surface)."""
    try:
        return cv2.getWindowProperty(GNSS_WINDOW, cv2.WND_PROP_VISIBLE) < 1
    except cv2.error:
        return True


# --- Drone Control Functions ---

async def takeoff(drone):
    """Arms the drone and takes off to a default altitude."""
    print("Arming the drone...")
    drone.arm()
    print("Taking off...")
    await drone.takeoff_async()
    time.sleep(1)


async def land(drone):
    """Lands the drone."""
    print("Landing...")
    await drone.land_async()
    print("Disarming the drone...")
    drone.disarm()

# --- Main Control Loop ---

async def run_keyboard_control(drone):
    """
    Controls the drone using keyboard inputs.

    Args:
        drone: The Drone object.
    """

    # Enable API control
    drone.enable_api_control()

    # Window-scoped key state (replaces the system-wide `keyboard` library)
    scoped_keys = WindowScopedKeys(GNSS_WINDOW)

    # Create the GNSS window up front so the user can focus it during takeoff
    cv2.namedWindow(GNSS_WINDOW, cv2.WINDOW_AUTOSIZE)
    show_gnss_frame()

    # Takeoff
    await takeoff(drone)

    # Speed settings
    speed = 5  # m/s
    yaw_speed = 20  # degrees/s
    duration = 0.1  # seconds

    print("\n--- Keyboard Control ---")
    print("W/S: Pitch (Forward/Backward)")
    print("A/D: Roll (Left/Right)")
    print("Up/Down Arrows: Throttle (Altitude)")
    print("Left/Right Arrows: Yaw (Rotation)")
    print("L: Land")
    print("Q: Quit")
    print("--------------------")
    print(f"Keys act while the '{GNSS_WINDOW}' window has focus - click it once.")
    print("Closing that window quits (same as Q).")

    keep_running = True

    while keep_running:
        # Closing the GNSS window removes the input surface - quit, same as Q
        if gnss_window_closed():
            print("GNSS window closed - quitting.")
            break

        # Keys currently held down (empty unless the GNSS window is focused);
        # window-scoped equivalent of the default script's keyboard.is_pressed
        keys = scoped_keys.poll()

        # Reset velocity components
        vx, vy, vz, yaw_rate = 0, 0, 0, 0

        # Pitch
        if 'w' in keys:
            vx = speed

        elif 's' in keys:
            vx = -speed

        # Roll
        if 'a' in keys:
            vy = -speed

        elif 'd' in keys:
            vy = speed

        # Throttle
        if 'up' in keys:
            vz = -speed  # Negative Z is up

        elif 'down' in keys:
            vz = speed

        # Yaw
        if 'left' in keys:
            yaw_rate = -yaw_speed

        elif 'right' in keys:
            yaw_rate = yaw_speed

        # Land and exit
        if 'l' in keys:
            await land(drone)
            keep_running = False

        # Quit
        if 'q' in keys:
            keep_running = False

        # Move the drone in its body frame
        # vx, vy, vz are now interpreted as forward/backward, right/left, up/down relative to the drone
        if vx != 0 or vy != 0 or vz != 0:
            await drone.move_by_velocity_body_frame_async(vx, vy, vz, duration)
        if yaw_rate != 0:
            await drone.rotate_by_yaw_rate_async(yaw_rate, duration)

        # Update the GNSS overlay window with the latest camera frame + GPS data
        show_gnss_frame()

        await asyncio.sleep(0.01)

# --- Main Execution ---

async def main():
    parser = argparse.ArgumentParser(
        description=(
            "Example of using keyboard to control a drone in Project AirSim, "
            "with a GNSS (latitude/longitude/altitude) overlay on the chase camera. "
            "Input is read while the overlay window has focus - no sudo needed."
        )
    )

    # ... (parser arguments remain the same) ...
    parser.add_argument(
        "--address",
        help=("the IP address of the host running Project AirSim"),
        type=str,
        default="127.0.0.1",
    )

    parser.add_argument(
        "--sceneconfigfile",
        help=(
            'the Project AirSim scene config file to load, defaults to "scene_basic_drone.jsonc"'
        ),

        type=str,
        default="scene_basic_drone.jsonc",
    )

    parser.add_argument(
        "--simconfigpath",
        help=(
            'the directory containing Project AirSim config files, defaults to the '
            '"sim_config" directory next to this script (so it works from any cwd)'
        ),
        type=str,
        default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "sim_config"),
    )

    parser.add_argument(
        "--topicsport",
        help=(
            "the TCP/IP port of Project AirSim's topic pub-sub client connection "
            '(see the Project AirSim command line switch "-topicsport")'
        ),
        type=int,
        default=8989,
    )

    parser.add_argument(
        "--servicesport",
        help=(
            "the TCP/IP port of Project AirSim's services client connection "
            '(see the Project AirSim command line switch "-servicessport")'
        ),
        type=int,
        default=8990,
    )

    args = parser.parse_args()
    client = projectairsim.ProjectAirSimClient(
        address=args.address,
        port_topics=args.topicsport,
        port_services=args.servicesport,
    )

    drone = None
    try:
        client.connect()
        world = projectairsim.World(
            client=client,
            scene_config_name=args.sceneconfigfile,
            sim_config_path=args.simconfigpath,
        )
        drone = Drone(client, world, "Drone1")

        # Subscribe to the GNSS (GPS) sensor and the chase camera for the overlay
        client.subscribe(drone.sensors["GPS"]["gps"], on_gps_message)
        client.subscribe(drone.sensors["Chase"]["scene_camera"], on_chase_image)

        await run_keyboard_control(drone)

    except Exception as e:
        print(f"An error occurred: {e}")

    finally:
        if drone:
            drone.disarm()
            drone.disable_api_control()
        client.disconnect()
        cv2.destroyAllWindows()

        print("Cleaned up and disconnected.")

if __name__ == "__main__":
    asyncio.run(main())
