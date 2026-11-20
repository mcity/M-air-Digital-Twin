#!/usr/bin/env python
"""
fetch_osm_roads.py - ANC-1346: pull the REAL road network and building footprints of a lon/lat box
into the engine's near-field import format, projected to world metres on the SAME georef the
terrain uses.

It is the third member of the same-box family: fetch_dem_exr.py gives the heightmap,
fetch_sat_texture.py gives the albedo for that identical box, and this gives what stands on it.
All three take the box the same way, so a road lands on the track visible in the imagery because
all three agree on where the box is - that alignment IS the acceptance test and it costs nothing
to look at.

NO FABRICATION. A box with no roads imports no roads and says so. Heights, widths and surfaces come
from OSM tags or from a stated per-class default; nothing is invented to make a place look busier
than it is.

THE PROJECTION is the engine's georef convention, matching geo-import.ts latLonToWorld with
flipZ=true - the EXR convention, because fetch_dem_exr.py writes the raster bottom-up:

    x = (lon - west) / (east - west) * extent_x        world X: 0 at the WEST edge
    z = (lat - south) / (north - south) * extent_z     world Z: 0 at the SOUTH edge

This is the PRE-handedness coordinate system - the same one the ground height lookup and the
terrain mesher use. Converting to a left-handed renderer is the consumer's business and must not
be baked in here, or the roads rotate off the ground they belong to.

JUNCTIONS ARE NOT GUESSED. OSM shares a node id where ways genuinely meet, so an intersection is
a node referenced by two or more drivable ways - counted, not inferred from proximity. That is
what the engine's road junction connector pads are placed on.

  Usage:
    python fetch_osm_roads.py WEST SOUTH EAST NORTH EXTENT_M [out.json] [--from raw_overpass.json]
  Example (the 8 km Grand Canyon box that canyon_8km.exr covers):
    python fetch_osm_roads.py -112.15228 36.02556 -112.06312 36.09764 8000 canyon_roads.json

  --from reads a saved Overpass response instead of querying. The public mirrors load-shed hard -
  all three returned 504 for nine straight attempts while this was being written - and the
  projection, the class table and the junction detection are the parts that change; re-querying to
  re-run them is both slow and rude. The raw response is always written beside the output as
  <out>.overpass.json so a later run can be replayed from it exactly.
"""
import json, os, sys, time, urllib.parse, urllib.request, urllib.error

# Public Overpass mirrors - tried in order (any one is load-shed/504-prone, so we fail over + retry).
OVERPASS_MIRRORS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
]

# highway= -> road class. The same table osm-import.ts classOf() uses, deliberately: the two
# importers feed the same engine road generator, and a way that is drivable in one and not the
# other would put a road in the web client that the native client has never heard of.
# A value absent here is NOT drivable (footway, path, cycleway, steps, pedestrian, track) and is
# dropped - counted in the report, never silently.
ROAD_CLASS = {
    "motorway": "highway", "trunk": "highway",
    "motorway_link": "highway", "trunk_link": "highway",
    "raceway": "highway",          # ANC-639: on a circuit world the raceway IS the road
    "primary": "arterial", "secondary": "arterial", "tertiary": "arterial",
    "primary_link": "arterial", "secondary_link": "arterial", "tertiary_link": "arterial",
    "residential": "surface", "unclassified": "surface", "service": "surface",
    "living_street": "surface", "road": "surface",
}

# Carriageway width in metres per class when the way does not say. A lane is ~3.5 m; these are the
# widths the engine's road generator extrudes, and they are defaults, not measurements - which is
# why `lanes` on the way wins whenever it is present.
CLASS_WIDTH_M = {"highway": 12.0, "arterial": 8.0, "surface": 5.5}
LANE_WIDTH_M = 3.5

# surface= -> the engine's road material. Unknown or absent reads as paved, which is what OSM's own
# default is for a tagged carriageway.
PAVED = {"asphalt", "paved", "concrete", "concrete:plates", "paving_stones", "sett", "cobblestone"}
GRAVEL = {"gravel", "fine_gravel", "compacted", "pebblestone", "unpaved"}
DIRT = {"dirt", "ground", "earth", "mud", "sand", "grass"}

# building:levels -> metres when no explicit height. 3 m per storey is the common planning figure;
# it is a default and the report says how many footprints had to fall back to it.
STOREY_M = 3.0
DEFAULT_BUILDING_M = 6.0


def overpass(query):
    data = urllib.parse.urlencode({"data": query}).encode()
    last = None
    for attempt in range(3):
        for url in OVERPASS_MIRRORS:
            try:
                req = urllib.request.Request(url, data=data, headers={"User-Agent": "mcity-terrain/1.0"})
                with urllib.request.urlopen(req, timeout=180) as r:
                    return json.load(r)
            except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, OSError) as e:
                last = e
                print(f"  overpass {url.split('/')[2]} failed ({type(e).__name__}: {e}); trying next...")
        time.sleep(5 * (attempt + 1))
    raise SystemExit(f"all Overpass mirrors failed: {last}")


def material_of(surface):
    if not surface:
        return "paved"
    if surface in PAVED:
        return "paved"
    if surface in GRAVEL:
        return "gravel"
    if surface in DIRT:
        return "dirt"
    return "paved"


def width_of(tags, cls):
    """Metres across the carriageway. An explicit width= wins, then lanes x lane width, then the
    class default. Each path is distinguishable in the output so the report can say which."""
    w = tags.get("width")
    if w:
        try:
            v = float(str(w).split()[0])
            if 0.5 <= v <= 60.0:
                return v, "tag"
        except ValueError:
            pass
    lanes = tags.get("lanes")
    if lanes:
        try:
            n = int(str(lanes).split(";")[0])
            if 1 <= n <= 12:
                return n * LANE_WIDTH_M, "lanes"
        except ValueError:
            pass
    return CLASS_WIDTH_M[cls], "class"


def height_of(tags):
    """Metres to the roof. Explicit height=, else building:levels x storey, else the class default.
    Returns (metres, source) so the caller can report how much of the skyline is defaulted."""
    h = tags.get("height")
    if h:
        try:
            v = float(str(h).split()[0])
            if 0.5 <= v <= 400.0:
                return v, "tag"
        except ValueError:
            pass
    lv = tags.get("building:levels")
    if lv:
        try:
            n = float(str(lv).split(";")[0])
            if 0 < n <= 120:
                return n * STOREY_M, "levels"
        except ValueError:
            pass
    return DEFAULT_BUILDING_M, "default"


def main():
    argv = list(sys.argv[1:])
    cached = None
    if "--from" in argv:
        k = argv.index("--from")
        cached = argv[k + 1]
        del argv[k:k + 2]
    if len(argv) < 5:
        print(__doc__)
        sys.exit(2)
    west, south, east, north, extent = (float(argv[i]) for i in range(0, 5))
    out_path = argv[5] if len(argv) > 5 else "osm_roads.json"
    if not (west < east and south < north):
        sys.exit(f"the box needs west<east and south<north - got W{west} S{south} E{east} N{north}")
    if extent <= 0:
        sys.exit(f"extent must be positive metres - got {extent}")
    bbox = f"{south},{west},{north},{east}"   # Overpass order: S,W,N,E

    def to_world(lat, lon):
        """The georef projection. Returns None OUTSIDE the box rather than extrapolating: a way
        that leaves the terrain has no ground to sit on, and a clamped vertex would draw a road
        running along the map edge that does not exist."""
        if lon < west or lon > east or lat < south or lat > north:
            return None
        fx = (lon - west) / (east - west)
        fz = (lat - south) / (north - south)   # flipZ: world Z=0 is the SOUTH edge
        return [round(fx * extent, 3), round(fz * extent, 3)]

    print(f"box W{west} S{south} E{east} N{north} -> {extent:.0f} m across")
    if cached:
        with open(cached) as f:
            doc = json.load(f)
        print(f"replayed from {cached} - no network call")
    else:
        q = (f'[out:json][timeout:180];'
             f'(way["highway"]({bbox});way["building"]({bbox}););out geom;')
        doc = overpass(q)
        with open(out_path + ".overpass.json", "w") as f:
            json.dump(doc, f)
        print(f"raw response saved to {out_path}.overpass.json")
    elements = doc.get("elements", [])

    roads, buildings = [], []
    skipped_class = {}
    clipped_ways = 0
    width_src = {"tag": 0, "lanes": 0, "class": 0}
    height_src = {"tag": 0, "levels": 0, "default": 0}
    # node id -> how many DRIVABLE ways use it. Shared ids are how OSM records a real junction.
    node_uses = {}

    for e in elements:
        if e.get("type") != "way":
            continue
        tags = e.get("tags", {})
        geom = e.get("geometry") or []
        nodes = e.get("nodes") or []
        if len(geom) < 2:
            continue

        if "highway" in tags:
            hw = tags["highway"]
            cls = ROAD_CLASS.get(hw)
            if cls is None:
                skipped_class[hw] = skipped_class.get(hw, 0) + 1
                continue
            pts, kept_nodes = [], []
            for i, g in enumerate(geom):
                p = to_world(g["lat"], g["lon"])
                if p is None:
                    continue
                pts.append(p)
                if i < len(nodes):
                    kept_nodes.append(nodes[i])
            if len(pts) < 2:
                clipped_ways += 1
                continue
            if len(pts) < len(geom):
                clipped_ways += 1
            w, wsrc = width_of(tags, cls)
            width_src[wsrc] += 1
            for nid in kept_nodes:
                node_uses[nid] = node_uses.get(nid, 0) + 1
            roads.append({
                "osmId": e.get("id"),
                "name": tags.get("name", ""),
                "highway": hw,
                "roadClass": cls,
                "material": material_of(tags.get("surface")),
                "widthM": round(w, 2),
                "widthFrom": wsrc,
                "oneway": tags.get("oneway") in ("yes", "true", "1", "-1"),
                "bridge": "bridge" in tags,
                "tunnel": "tunnel" in tags,
                "nodes": kept_nodes,
                "points": pts,
            })

        elif "building" in tags:
            ring = []
            for g in geom:
                p = to_world(g["lat"], g["lon"])
                if p is None:
                    continue
                ring.append(p)
            if len(ring) < 3:
                if ring:
                    clipped_ways += 1
                continue
            if len(ring) < len(geom):
                clipped_ways += 1
            # OSM closes a way by repeating the first node; the engine wants the ring once.
            if len(ring) > 3 and ring[0] == ring[-1]:
                ring.pop()
            h, hsrc = height_of(tags)
            height_src[hsrc] += 1
            buildings.append({
                "osmId": e.get("id"),
                "name": tags.get("name", ""),
                "building": tags["building"],
                "heightM": round(h, 2),
                "heightFrom": hsrc,
                "roof": tags.get("roof:shape", ""),
                "footprint": ring,
            })

    # A junction is a node two or more DRIVABLE ways share. Its pad radius must cover the widest
    # road arriving at it, so it is taken from those roads rather than guessed.
    at_node = {}
    for r in roads:
        for nid in r["nodes"]:
            at_node.setdefault(nid, []).append(r)
    junctions = []
    for nid, ways in at_node.items():
        if len(ways) < 2:
            continue
        pt = None
        for r in ways:
            try:
                pt = r["points"][r["nodes"].index(nid)]
                break
            except (ValueError, IndexError):
                continue
        if pt is None:
            continue
        junctions.append({
            "osmNode": nid,
            "x": pt[0], "z": pt[1],
            "radiusM": round(max(w["widthM"] for w in ways) * 0.75, 2),
            "ways": len(ways),
        })

    out = {
        "georef": {"west": west, "south": south, "east": east, "north": north, "flipZ": True},
        "extentM": extent,
        "source": "OpenStreetMap / Overpass",
        "roads": roads,
        "junctions": junctions,
        "buildings": buildings,
    }
    with open(out_path, "w") as f:
        json.dump(out, f, indent=1)

    # ── AND A FLAT BINARY THE ENGINE READS WITHOUT A JSON PARSER ──────────────────────────────
    # The JSON above is for people and for re-import. The native package that feeds her renderer
    # is C++ with no third-party deps, and hand-rolling a JSON parser there to read numbers we
    # already have is work that buys nothing. This is the same choice the heightmap path already
    # made: a raw .r32 with an 8-byte header rather than an image library.
    #
    # Layout, little-endian throughout, which is every platform this runs on:
    #   magic "ANRD", u32 version=1, f32 extent_m, u32 n_roads, u32 n_junctions
    #   per road:      u8 road_class (0 highway, 1 arterial, 2 surface), u8 pad[3],
    #                  f32 width_m, u32 n_pts, n_pts * (f32 x, f32 z)
    #   per junction:  f32 x, f32 z, f32 radius_m
    # Points are WORLD METRES in the engine's pre-handedness frame - the same frame
    # the ground height lookup takes - so the consumer drapes them and converts for its own
    # renderer, exactly as the terrain mesh does.
    import struct
    CLASS_ID = {"highway": 0, "arterial": 1, "surface": 2}
    bin_path = os.path.splitext(out_path)[0] + ".bin"
    with open(bin_path, "wb") as f:
        f.write(b"ANRD")
        f.write(struct.pack("<IfII", 1, extent, len(roads), len(junctions)))
        for r in roads:
            f.write(struct.pack("<BBBBfI", CLASS_ID.get(r["roadClass"], 2), 0, 0, 0,
                                r["widthM"], len(r["points"])))
            for x, z in r["points"]:
                f.write(struct.pack("<ff", x, z))
        for j in junctions:
            f.write(struct.pack("<fff", j["x"], j["z"], j["radiusM"]))
    print(f"wrote {bin_path} ({os.path.getsize(bin_path):,} bytes) - the engine-side input")

    cls_count = {}
    for r in roads:
        cls_count[r["roadClass"]] = cls_count.get(r["roadClass"], 0) + 1
    road_pts = sum(len(r["points"]) for r in roads)
    print(f"wrote {out_path}")
    print(f"  roads      {len(roads):5d} ways, {road_pts} vertices  {cls_count}")
    print(f"             widths from: tag {width_src['tag']}, lanes {width_src['lanes']}, "
          f"class default {width_src['class']}")
    print(f"  junctions  {len(junctions):5d} shared nodes where 2+ drivable ways meet")
    print(f"  buildings  {len(buildings):5d} footprints, "
          f"{sum(len(b['footprint']) for b in buildings)} vertices")
    print(f"             heights from: tag {height_src['tag']}, levels {height_src['levels']}, "
          f"default {height_src['default']}")
    if skipped_class:
        total = sum(skipped_class.values())
        print(f"  NOT DRIVABLE, dropped: {total} way(s) {dict(sorted(skipped_class.items(), key=lambda kv: -kv[1]))}")
    if clipped_ways:
        print(f"  {clipped_ways} way(s) crossed the box edge and were clipped to the part inside it")
    if not roads and not buildings:
        print("  THE BOX IS EMPTY. That is the answer, not a failure - nothing is generated to fill it.")


if __name__ == "__main__":
    main()
