/* Mcity drone GPS live map: receives fixes over WebSocket, plots them on a
 * Google Map with a trail per drone. */

let map = null;
const drones = {}; // name -> { marker, trail, path }
const COLORS = ["#e53935", "#1e88e5", "#43a047", "#fb8c00", "#8e24aa"];
let colorIdx = 0;

// ---- Google Maps bootstrap --------------------------------------------------

function loadGoogleMaps() {
  if (!CONFIG.GOOGLE_MAPS_API_KEY) {
    document.getElementById("key-warning").hidden = false;
    return; // WS still runs; panel shows live numbers without the map
  }
  const s = document.createElement("script");
  s.src = "https://maps.googleapis.com/maps/api/js?key=" +
    encodeURIComponent(CONFIG.GOOGLE_MAPS_API_KEY) + "&callback=initMap";
  s.async = true;
  s.defer = true;
  document.head.appendChild(s);
}

window.initMap = function () {
  map = new google.maps.Map(document.getElementById("map"), {
    center: { lat: CONFIG.START_LAT, lng: CONFIG.START_LON },
    zoom: CONFIG.START_ZOOM,
    mapTypeId: "hybrid",
    streetViewControl: false,
  });
};

function getDrone(name) {
  if (!drones[name]) {
    const color = COLORS[colorIdx++ % COLORS.length];
    drones[name] = { marker: null, trail: null, path: [], color };
    if (map) {
      drones[name].marker = new google.maps.Marker({
        map,
        title: name,
        icon: {
          path: google.maps.SymbolPath.CIRCLE,
          scale: 8,
          fillColor: color,
          fillOpacity: 1,
          strokeColor: "#ffffff",
          strokeWeight: 2,
        },
      });
      drones[name].trail = new google.maps.Polyline({
        map,
        path: [],
        strokeColor: color,
        strokeOpacity: 0.8,
        strokeWeight: 3,
      });
    }
  }
  return drones[name];
}

// ---- WebSocket --------------------------------------------------------------

function setConn(ok, text) {
  const el = document.getElementById("conn");
  el.textContent = "WS: " + text;
  el.className = "status " + (ok ? "connected" : "disconnected");
}

function connectWS() {
  const ws = new WebSocket(CONFIG.WS_URL);

  ws.onopen = () => setConn(true, "connected");
  ws.onclose = () => {
    setConn(false, "disconnected - retrying...");
    setTimeout(connectWS, 2000);
  };
  ws.onerror = () => ws.close();

  ws.onmessage = (event) => {
    const data = JSON.parse(event.data);
    if (data.type !== "gps") return;
    updatePanel(data.drones);
    updateMap(data.drones);
  };
}

// ---- UI updates -------------------------------------------------------------

function speedOf(d) {
  if (!d.vel || d.vel[0] == null) return null;
  return Math.hypot(d.vel[0], d.vel[1], d.vel[2]);
}

function updatePanel(list) {
  const root = document.getElementById("drones");
  root.innerHTML = "";
  if (!list.length) {
    const div = document.createElement("div");
    div.className = "drone stale";
    div.textContent = "Waiting for GPS data from sim…";
    root.appendChild(div);
    return;
  }
  for (const d of list) {
    const spd = speedOf(d);
    const div = document.createElement("div");
    div.className = "drone" + (d.age_s > 5 ? " stale" : "");
    div.innerHTML =
      `<b>${d.name}</b>${d.age_s > 5 ? " (stale)" : ""}<br>` +
      `Lat: ${d.lat?.toFixed(7)}&deg;<br>` +
      `Lon: ${d.lon?.toFixed(7)}&deg;<br>` +
      `Alt: ${d.alt?.toFixed(2)} m` +
      (spd != null ? `<br>Speed: ${spd.toFixed(1)} m/s` : "");
    root.appendChild(div);
  }
}

function updateMap(list) {
  if (!map) return;
  const follow = document.getElementById("follow").checked;
  for (const d of list) {
    if (d.lat == null || d.lon == null) continue;
    const pos = { lat: d.lat, lng: d.lon };
    const entry = getDrone(d.name);
    if (entry.marker) {
      entry.marker.setPosition(pos);
      entry.path.push(pos);
      if (entry.path.length > 2000) entry.path.shift();
      entry.trail.setPath(entry.path);
    }
  }
  if (follow && list.length && list[0].lat != null) {
    map.panTo({ lat: list[0].lat, lng: list[0].lon });
  }
}

document.getElementById("clear-trail").addEventListener("click", () => {
  for (const name of Object.keys(drones)) {
    drones[name].path = [];
    if (drones[name].trail) drones[name].trail.setPath([]);
  }
});

// ---- Go ---------------------------------------------------------------------

loadGoogleMaps();
connectWS();
