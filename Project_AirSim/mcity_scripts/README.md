# Mcity Drone GPS — Live Map UI

Live Google-Maps view of the drone's GNSS position while a Project AirSim
simulation is running.

**Architecture note:** Project AirSim's topics channel is an nng **Pair0**
(strictly one-to-one) socket — only ONE pub-sub client can talk to the sim at
a time, and the flight script is that client. So the bridge never connects to
the sim. Instead, the flight script relays each GPS fix as a JSON datagram
over localhost UDP, and the bridge fans it out to browsers over a WebSocket:

```
flight script (sole sim client) --UDP:9092--> gps_ws_server.py --WS:9091--> browser (UI :8080)
```

`keyboard_control_gnss.py` already sends the UDP beacon. To add it to any
other script that subscribes to GPS, copy its `send_gps_beacon()` helper
(stdlib-only, fire-and-forget, never affects flight).

## One-time setup

```bash
conda activate proj_airsim
pip install websockets
```

Put your Google Maps JavaScript API key in a `.env` file next to
`gps_ws_server.py`:

```
GOOGLE_MAPS_API_KEY=your-key-here
```

The server reads it and hands it to the page as `/env.js` (the raw `.env`
file itself is never served). Without a key the panel still shows live
numbers, but the map stays blank.

## Run

1. Start the bridge (any time — it does not need the sim):
   ```bash
   conda activate proj_airsim
   python gps_ws_server.py
   ```
2. Start the sim (McityMap editor → Play) and a GPS-relaying flight script
   (e.g. `keyboard_control_gnss.py`).
3. Open <http://localhost:8080>.

Options: `--httpport` (default 8080), `--wsport` (default 9091), `--udpport`
(default 9092), `--rate` (broadcast Hz, default 5).

## Notes

- Requires the robot config to have its GPS sensor enabled
  (`robot_quadrotor_fastphysics.jsonc` → `"id": "GPS"` → `"enabled": true`).
- Multiple drones: send beacons with distinct `"name"` values — each gets its
  own marker color and trail.
- Flight keys are scoped to the flight script's "Chase Cam + GNSS" window
  (read via `cv2.waitKeyEx`): typing in the browser or terminal never reaches
  the drone. Click that window to fly; closing it lands the drone.
- "Follow drone" keeps the map centered on the first drone; trails keep the
  last 2000 points (Clear trail button resets).
