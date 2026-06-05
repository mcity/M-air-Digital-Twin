// Edit these values for your setup.
const CONFIG = {
  // Google Maps JavaScript API key. Comes from the .env file next to
  // gps_ws_server.py (GOOGLE_MAPS_API_KEY=...), served to the page as
  // /env.js. A non-empty value set here would override the .env one.
  GOOGLE_MAPS_API_KEY: (window.ENV && window.ENV.GOOGLE_MAPS_API_KEY) || "",

  // WebSocket stream from gps_ws_server.py
  WS_URL: "ws://localhost:9091",

  // Initial map view (Mcity)
  START_LAT: 42.2995934,
  START_LON: -83.6986589,
  START_ZOOM: 17,
};
