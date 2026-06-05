"""
gps_ws_server.py - GPS bridge for the Mcity live map UI.

IMPORTANT: Project AirSim's topics channel is an nng Pair0 (strictly 1:1)
socket, so only ONE pub-sub client can talk to the sim at a time - and the
flight script is that client. This bridge therefore does NOT connect to the
sim at all. Instead, the flight script (e.g. keyboard_control_gnss.py)
relays each GPS fix here as a small JSON datagram over localhost UDP, and
this bridge fans it out to browser clients over a WebSocket. It also serves
the static UI files over HTTP.

    flight script --UDP:9092--> gps_ws_server --WS:9091--> browser (UI :8080)

Usage (no sudo needed):
    conda activate proj_airsim
    pip install websockets   # one-time
    python gps_ws_server.py  # then open http://localhost:8080

Expected UDP payload (JSON, one datagram per fix):
    {"name": "Drone1", "lat": 42.3, "lon": -83.7, "alt": 270.0,
     "vel": [vn, ve, vd], "eph": 0.3, "fix_type": 3}
"""

import argparse
import asyncio
import http.server
import json
import threading
import time
from pathlib import Path

import websockets

UI_DIR = Path(__file__).parent.resolve()

# Latest GPS fix per drone name, guarded by a lock (UDP datagrams arrive on
# the asyncio loop; HTTP runs on its own thread).
latest = {}
latest_lock = threading.Lock()


def load_dotenv(path=UI_DIR / ".env"):
    """Minimal KEY=VALUE .env parser (stdlib only)."""
    env = {}
    try:
        for line in Path(path).read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            env[key.strip()] = value.strip().strip('"').strip("'")
    except FileNotFoundError:
        print(f"[gps_ws_server] No .env file at {path}")
    return env


DOTENV = load_dotenv()


class GpsDatagramProtocol(asyncio.DatagramProtocol):
    """Receives GPS fixes from flight scripts as JSON datagrams."""

    def datagram_received(self, data, addr):
        try:
            fix = json.loads(data.decode())
            name = str(fix.get("name", "drone"))
            with latest_lock:
                latest[name] = {"fix": fix, "recv_time": time.time()}
        except Exception as exc:
            print(f"[gps_ws_server] Bad UDP datagram from {addr}: {exc}")


def build_payload():
    drones = []
    now = time.time()
    with latest_lock:
        for name, entry in latest.items():
            fix = entry["fix"]
            drones.append({
                "name": name,
                "lat": fix.get("lat"),
                "lon": fix.get("lon"),
                "alt": fix.get("alt"),
                "vel": fix.get("vel"),
                "eph": fix.get("eph"),
                "fix_type": fix.get("fix_type"),
                "age_s": round(now - entry["recv_time"], 2),
            })
    return {"type": "gps", "time": now, "drones": drones}


async def ws_main(args):
    clients = set()

    async def handler(websocket):
        clients.add(websocket)
        print(f"[gps_ws_server] UI client connected ({len(clients)} total)")
        try:
            await websocket.wait_closed()
        finally:
            clients.discard(websocket)
            print(f"[gps_ws_server] UI client disconnected "
                  f"({len(clients)} total)")

    async def broadcaster():
        interval = 1.0 / args.rate
        while True:
            if clients:
                # Always send (even with no drones) so the UI can show a
                # "waiting" state instead of staying blank.
                message = json.dumps(build_payload())
                await asyncio.gather(
                    *(ws.send(message) for ws in clients),
                    return_exceptions=True,
                )
            await asyncio.sleep(interval)

    loop = asyncio.get_running_loop()
    transport, _ = await loop.create_datagram_endpoint(
        GpsDatagramProtocol, local_addr=("127.0.0.1", args.udpport))
    print(f"[gps_ws_server] Listening for GPS fixes on udp://127.0.0.1:"
          f"{args.udpport}")

    try:
        async with websockets.serve(handler, "0.0.0.0", args.wsport):
            print(f"[gps_ws_server] WebSocket stream on "
                  f"ws://localhost:{args.wsport}")
            await broadcaster()  # runs forever
    finally:
        transport.close()


class UIRequestHandler(http.server.SimpleHTTPRequestHandler):
    """Static file server plus a dynamic /env.js built from .env.

    Never serves the .env file itself.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(UI_DIR), **kwargs)

    def do_GET(self):
        path = self.path.split("?", 1)[0]
        if ".env" in path:
            self.send_error(404)  # never expose the raw .env
            return
        if path == "/env.js":
            body = ("window.ENV = "
                    + json.dumps({"GOOGLE_MAPS_API_KEY":
                                  DOTENV.get("GOOGLE_MAPS_API_KEY", "")})
                    + ";\n").encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/javascript")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)
            return
        super().do_GET()


def serve_http(port):
    httpd = http.server.ThreadingHTTPServer(("0.0.0.0", port),
                                            UIRequestHandler)
    print(f"[gps_ws_server] UI served at http://localhost:{port}")
    httpd.serve_forever()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--httpport", type=int, default=8080,
                        help="UI port")
    parser.add_argument("--wsport", type=int, default=9091,
                        help="WebSocket stream port")
    parser.add_argument("--udpport", type=int, default=9092,
                        help="UDP port receiving GPS fixes from flight scripts")
    parser.add_argument("--rate", type=float, default=5.0,
                        help="UI broadcast rate (Hz)")
    args = parser.parse_args()

    http_thread = threading.Thread(
        target=serve_http, args=(args.httpport,), daemon=True)
    http_thread.start()

    try:
        asyncio.run(ws_main(args))
    except KeyboardInterrupt:
        print("[gps_ws_server] Stopped.")


if __name__ == "__main__":
    main()
