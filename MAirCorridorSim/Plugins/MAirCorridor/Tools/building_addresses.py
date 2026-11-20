"""building_addresses.py - an address for every building in the corridor level, and where it came from.

    py -3.10 Tools/building_addresses.py [--assets <MAirCorridor_Assets>] [--out <json>]

Reads, all in MAirCorridor_Assets unless given:

  corridor_osm_tags.json      each building's OpenStreetMap id and tags, by its name in the level
                              (Tools/blender/building_osm_tags.py, from the January blosm scene)
  osm_files/fullcorridor.osm  the OpenStreetMap extracts the scene was built from: the buildings'
  osm_files/aircorridor.osm   true footprints, address points, streets, address interpolation
                              lines, and the Canada-US boundary along the Detroit River
  tiger/                      TIGER/Line address ranges (ADDRFEAT) for Washtenaw and Wayne counties,
                              downloaded from the Census Bureau the first time (public domain)

and writes building_addresses.json beside them. Each building gets its address from the first
of these that has one, and "source" says which:

  osm         its own addr:housenumber and addr:street in OpenStreetMap. Exact.
  osm-point   an OpenStreetMap address point inside its footprint. Exact.
  osm-line    an OpenStreetMap address interpolation line within 40 m: the number at the point of
              the line opposite the building, between the numbers at its ends. An estimate.
  neighbours  an estimate on the street the census puts it on, interpolated between the real
              OpenStreetMap addresses of buildings on the same side of that street within 250 m
              (or carried on from one of them at the census range's numbers per metre).
  census      the nearest street segment, within 150 m, with a house number range on the
              building's side in TIGER/Line: the number at the point of the segment opposite the
              building, with the side's parity. The way a geocoder interpolates.
  street      no number: the nearest street with ranges, within 500 m, its ZIP code and city;
              in Canada, the nearest street OpenStreetMap names within 150 m.
  none        nothing within reach.

The corridor crosses the Detroit River into Windsor, Ontario, about 400 of its buildings. Which side
of the Canada-US boundary a building stands on is decided from the boundary in the extract; a
building in Canada gets no census estimate (TIGER/Line is the United States only), its province is
ON and its postcode is kept whole.

The ZIP code comes from OpenStreetMap when the building or its address point has one, else from
the census range on the building's side. The city is OpenStreetMap's, else the city OpenStreetMap
gives most often for that ZIP code (the mailing city, which in Michigan's townships is often not
the municipality). Street names are OpenStreetMap's spelling where a street of the same name runs
beside the building, else the census name with its abbreviations written out.

HOW GOOD THE ESTIMATES ARE is measured on the buildings OpenStreetMap does give an address: each
is estimated as if it had none, its own address left out of its neighbours, and compared with the
real one. Streets are compared by their names without direction or type ("W Fort St" is "Fort
Street West"). The result goes into the output's "validation" and is printed.

OpenStreetMap data (c) OpenStreetMap contributors, Open Database License; the output is a derived
database under the same licence. TIGER/Line is public domain.
"""
import argparse
import array
import collections
import io
import json
import math
import os
import re
import time
import xml.etree.ElementTree as ET
import zipfile

import numpy as np
import requests
import shapefile
from shapely.geometry import LineString, MultiLineString, Point, Polygon
from shapely.ops import linemerge, unary_union
from shapely.strtree import STRtree

from toolpaths import ASSETS                                                       # noqa: E402
COUNTIES = {"26161": "Washtenaw", "26163": "Wayne"}
TIGER_URL = "https://www2.census.gov/geo/tiger/TIGER2024/ADDRFEAT/tl_2024_%s_addrfeat.zip"
LINE_M, CENSUS_M, STREET_M, NAME_M, NEIGHBOUR_M = 40.0, 150.0, 500.0, 80.0, 250.0
BORDER_NAME = "Detroit River section"
WINDSOR = (-83.0375, 42.3149)          # Windsor city hall: which side of the boundary is Canada

# Metres in a plane tangent near the corridor's middle: plenty for "which street is nearest".
LAT0, LON0 = 42.29, -83.38
KX, KY = 111320.0 * math.cos(math.radians(LAT0)), 110574.0


def xy(lon, lat):
    return (lon - LON0) * KX, (lat - LAT0) * KY


def lonlat(x, y):
    return x / KX + LON0, y / KY + LAT0


# ---- street names ---------------------------------------------------------------------------
ABBR = {
    "street": "st", "avenue": "ave", "road": "rd", "drive": "dr", "boulevard": "blvd", "court": "ct",
    "lane": "ln", "place": "pl", "parkway": "pkwy", "highway": "hwy", "circle": "cir", "terrace": "ter",
    "trail": "trl", "square": "sq", "expressway": "expy", "freeway": "fwy", "crescent": "cres",
    "north": "n", "south": "s", "east": "e", "west": "w", "northeast": "ne", "northwest": "nw",
    "southeast": "se", "southwest": "sw", "saint": "st", "mount": "mt", "point": "pt", "heights": "hts",
    "center": "ctr", "centre": "ctr", "plaza": "plz", "alley": "aly", "commons": "cmns", "crossing": "xing",
    "ridge": "rdg", "hill": "hl", "hills": "hls", "glen": "gln", "meadow": "mdw", "meadows": "mdws",
    "creek": "crk", "view": "vw", "village": "vlg", "woods": "wds", "estates": "est", "grove": "grv",
    "harbor": "hbr", "junction": "jct", "landing": "lndg", "manor": "mnr", "orchard": "orch",
    "pointe": "pte", "shore": "shr", "shores": "shrs", "spring": "spg", "springs": "spgs",
    "station": "sta", "valley": "vly", "vista": "vis", "first": "1st", "second": "2nd", "third": "3rd",
    "fourth": "4th", "fifth": "5th", "sixth": "6th", "seventh": "7th", "eighth": "8th", "ninth": "9th",
    "tenth": "10th", "one": "1", "two": "2", "three": "3", "five": "5", "six": "6", "seven": "7",
    "eight": "8", "nine": "9", "ten": "10",
}
DIRECTIONS = {"n", "s", "e", "w", "ne", "nw", "se", "sw"}
TYPES = {"st", "ave", "rd", "dr", "blvd", "ct", "ln", "pl", "pkwy", "hwy", "cir", "ter", "trl", "sq", "expy",
         "fwy", "cres", "plz", "aly", "xing", "cmns", "way", "loop", "run", "row", "walk", "pike", "path"}
SUFFIX = {"St": "Street", "Ave": "Avenue", "Rd": "Road", "Dr": "Drive", "Blvd": "Boulevard", "Ct": "Court",
          "Ln": "Lane", "Pl": "Place", "Pkwy": "Parkway", "Hwy": "Highway", "Cir": "Circle", "Ter": "Terrace",
          "Trl": "Trail", "Sq": "Square", "Expy": "Expressway", "Fwy": "Freeway", "Cres": "Crescent",
          "Plz": "Plaza", "Aly": "Alley", "Xing": "Crossing", "Cmns": "Commons"}
DIRECTION = {"N": "North", "S": "South", "E": "East", "W": "West",
             "NE": "Northeast", "NW": "Northwest", "SE": "Southeast", "SW": "Southwest"}


def key(name):
    return " ".join(ABBR.get(t, t) for t in re.findall(r"[a-z0-9]+", (name or "").lower()))


def base(name):
    """A street's name without its direction or type, for telling whether two names are the same
    street: "W Fort St" and "Fort Street West" are both "fort"."""
    words = key(name).split()
    if len(words) > 1 and words[0] in DIRECTIONS:
        words = words[1:]
    if len(words) > 1 and words[-1] in DIRECTIONS:
        words = words[:-1]
    if len(words) > 1 and words[-1] in TYPES:
        words = words[:-1]
    return "".join(words)


def written_out(name):
    """A census name with its abbreviations written out: "W Stadium Blvd" to "West Stadium Boulevard"."""
    words = name.split()
    if words and words[0] in DIRECTION and len(words) > 1:
        words[0] = DIRECTION[words[0]]
    if words and words[-1] in SUFFIX and len(words) > 1:
        words[-1] = SUFFIX[words[-1]]
    if len(words) > 2 and words[-1] in DIRECTION:
        words[-1] = DIRECTION[words[-1]]
    return " ".join(words)


def postcode(s):
    """A ZIP code to its five digits; a Canadian postcode whole."""
    s = (s or "").strip()
    if re.match(r"^\d{5}", s):
        return s[:5]
    return s.upper() or None


def number(s):
    return int(s) if s and s.isdigit() else None


# ---- OpenStreetMap ----------------------------------------------------------------------------
NOT_STREETS = {"footway", "cycleway", "path", "steps", "pedestrian", "track", "bridleway", "corridor",
               "proposed", "construction", "platform", "elevator", "bus_stop", "raceway"}


def read_osm(paths, wanted):
    """Footprints for the wanted building ids; every address point, named street and address
    interpolation line; and the Canada-US boundary along the Detroit River. The first file that has
    a building wins."""
    buildings, points, streets, lines, border = {}, {}, {}, {}, {}
    for path in paths:
        started = time.time()
        nid, nlat, nlon = array.array("q"), array.array("d"), array.array("d")
        refs_of, outers, file_points = {}, {}, {}
        for _, el in ET.iterparse(path, events=("end",)):
            t = el.tag
            if t == "node":
                i = int(el.get("id"))
                la, lo = float(el.get("lat")), float(el.get("lon"))
                nid.append(i); nlat.append(la); nlon.append(lo)
                tags = {x.get("k"): x.get("v") for x in el.findall("tag")}
                if "addr:housenumber" in tags:
                    file_points["n%d" % i] = {"node": i, "xy": xy(lo, la),
                                              "tags": {k: v for k, v in tags.items() if k.startswith("addr:")}}
                el.clear()
            elif t == "way":
                i = el.get("id")
                refs = array.array("q", (int(n.get("ref")) for n in el.findall("nd")))
                tags = {x.get("k"): x.get("v") for x in el.findall("tag")}
                refs_of[i] = (refs, "building" in tags)
                if tags.get("highway") and tags.get("name") and tags["highway"] not in NOT_STREETS:
                    streets.setdefault(i, {"name": tags["name"], "refs": refs})
                if "addr:interpolation" in tags:
                    lines.setdefault(i, {"tags": tags, "refs": refs})
                if tags.get("admin_level") == "2" and BORDER_NAME in tags.get("name", ""):
                    border.setdefault(i, {"refs": refs})
                if "addr:housenumber" in tags and "building" not in tags:
                    file_points["w" + i] = {"way": refs, "tags": {k: v for k, v in tags.items()
                                                                  if k.startswith("addr:")}}
                el.clear()
            elif t == "relation":
                i = el.get("id")
                if i in wanted:
                    outers[i] = [m.get("ref") for m in el.findall("member")
                                 if m.get("type") == "way" and m.get("role") in ("outer", "")]
                el.clear()
        ids = np.frombuffer(nid, dtype=np.int64)
        order = np.argsort(ids)
        ids = ids[order]
        lat = np.frombuffer(nlat, dtype=np.float64)[order]
        lon = np.frombuffer(nlon, dtype=np.float64)[order]

        def coords(refs):
            r = np.frombuffer(refs, dtype=np.int64)
            k = np.minimum(np.searchsorted(ids, r), len(ids) - 1)
            ok = ids[k] == r
            return [xy(a, b) for a, b in zip(lon[k[ok]], lat[k[ok]])]

        for i in wanted:
            if i in buildings:
                continue
            if i in refs_of and refs_of[i][1]:
                buildings[i] = ("way", [coords(refs_of[i][0])])
            elif i in outers:
                buildings[i] = ("relation", [coords(refs_of[w][0]) for w in outers[i] if w in refs_of])
        for group in (streets, lines, border):
            for s in group.values():
                if "line" not in s:
                    c = coords(s["refs"])
                    if len(c) >= 2:
                        s["line"] = c
                        s["ends"] = (int(s["refs"][0]), int(s["refs"][-1]))
        for k, p in file_points.items():
            if k in points:
                continue
            if "way" in p:
                c = coords(p.pop("way"))
                if not c:
                    continue
                p["xy"] = (sum(q[0] for q in c) / len(c), sum(q[1] for q in c) / len(c))
            points[k] = p
        print("  %s: %d of %d buildings found so far, %d address points, %d streets, %d interpolation lines, "
              "in %.0f s" % (os.path.basename(path), len(buildings), len(wanted), len(points), len(streets),
                             len(lines), time.time() - started), flush=True)
    return buildings, points, streets, lines, border


def footprint(rings):
    polys = []
    for r in rings:
        if len(r) >= 3:
            p = Polygon(r)
            polys.append(p if p.is_valid else p.buffer(0))
    if not polys:
        return None
    return polys[0] if len(polys) == 1 else unary_union(polys)


class Border:
    """Which side of the Canada-US boundary along the Detroit River a point is on."""

    def __init__(self, ways):
        merged = linemerge(MultiLineString([w["line"] for w in ways.values() if "line" in w]))
        self.lines = list(merged.geoms) if hasattr(merged, "geoms") else [merged]
        self.canada_sign = self._sign(Point(xy(*WINDSOR)))

    def _sign(self, p):
        line = min(self.lines, key=lambda ln: ln.distance(p))
        pts = np.array(line.coords)
        s = line.project(p)
        cum = np.concatenate([[0.0], np.cumsum(np.hypot(*np.diff(pts, axis=0).T))])
        j = min(max(int(np.searchsorted(cum, s, side="right")) - 1, 0), len(pts) - 2)
        dx, dy = pts[j + 1] - pts[j]
        q = line.interpolate(s)
        return 1 if dx * (p.y - q.y) - dy * (p.x - q.x) > 0 else -1

    def in_canada(self, p):
        # Only near the river: the boundary here says nothing about Ann Arbor.
        if not self.lines or min(ln.distance(p) for ln in self.lines) > 6000:
            return False
        return self._sign(p) == self.canada_sign


# ---- TIGER/Line --------------------------------------------------------------------------------
def tiger_files(folder):
    os.makedirs(folder, exist_ok=True)
    out = []
    for fips in COUNTIES:
        stem = os.path.join(folder, "tl_2024_%s_addrfeat" % fips)
        if not os.path.isfile(stem + ".shp"):
            print("  downloading the census address ranges for %s County" % COUNTIES[fips], flush=True)
            r = requests.get(TIGER_URL % fips, timeout=300)
            r.raise_for_status()
            zipfile.ZipFile(io.BytesIO(r.content)).extractall(folder)
        out.append(stem)
    return out


def read_tiger(stems):
    edges = []
    for stem in stems:
        sf = shapefile.Reader(stem)
        names = [f[0] for f in sf.fields[1:]]
        for shape, rec in zip(sf.iterShapes(), sf.iterRecords()):
            r = dict(zip(names, rec))
            if not r["FULLNAME"] or len(shape.points) < 2:
                continue
            sides = {}
            for s in ("L", "R"):
                a, b = number(r[s + "FROMHN"]), number(r[s + "TOHN"])
                if a is not None and b is not None:
                    sides[s] = (a, b, r["PARITY" + s] or "B", r["ZIP" + s] or None)
            if not sides:
                continue
            pts = [xy(lo, la) for lo, la in shape.points]
            edges.append({"name": r["FULLNAME"], "key": key(r["FULLNAME"]), "base": base(r["FULLNAME"]),
                          "sides": sides, "geom": LineString(pts), "pts": np.array(pts)})
    return edges


def snap(n, a, b, parity):
    lo, hi = min(a, b), max(a, b)
    r = int(round(n))
    if parity in ("E", "O"):
        want = 0 if parity == "E" else 1
        if r % 2 != want:
            r = r + 1 if n >= r else r - 1
        while r > hi:
            r -= 2
        while r < lo:
            r += 2
        return r
    return max(lo, min(hi, r))


def along(e, s):
    """The unit direction of the edge, first point to last, at distance s along it."""
    pts = e["pts"]
    cum = np.concatenate([[0.0], np.cumsum(np.hypot(*np.diff(pts, axis=0).T))])
    j = min(max(int(np.searchsorted(cum, s, side="right")) - 1, 0), len(pts) - 2)
    d = pts[j + 1] - pts[j]
    n = math.hypot(*d) or 1.0
    return d / n


def side_of(e, p, s):
    """Which side of the edge the point is on, "L" or "R", as the census counts them: left and
    right going from the edge's first point to its last."""
    u = along(e, s)
    q = e["geom"].interpolate(s)
    return "L" if u[0] * (p.y - q.y) - u[1] * (p.x - q.x) > 0 else "R"


def census_estimate(p, edges, tree, street_base=None, limit=CENSUS_M):
    near = [int(i) for i in tree.query(p.buffer(limit))]
    near.sort(key=lambda i: edges[i]["geom"].distance(p))
    for i in near:
        e = edges[i]
        d = e["geom"].distance(p)
        if d > limit:
            break
        if street_base and e["base"] != street_base:
            continue
        s = e["geom"].project(p)
        side = side_of(e, p, s)
        if side not in e["sides"]:
            continue
        a, b, parity, zipcode = e["sides"][side]
        f = s / e["geom"].length if e["geom"].length else 0.0
        return {"housenumber": snap(a + f * (b - a), a, b, parity), "edge": e, "side": side, "s": s,
                "zip": zipcode, "distance_m": round(d, 1), "at": e["geom"].interpolate(s),
                "per_m": (b - a) / e["geom"].length if e["geom"].length else 0.0, "range": (a, b, parity)}
    return None


def from_neighbours(p, est, known, known_tree, exclude=None):
    """The census estimate moved onto the real addresses of neighbours on the same street and side:
    interpolated between the nearest on either hand along the street, or carried on from the nearest
    at the census range's numbers per metre. None when no neighbour qualifies."""
    e, (a, b, parity) = est["edge"], est["range"]
    u, q = along(e, est["s"]), est["at"]
    want = est["housenumber"] % 2 if parity in ("E", "O") else None
    my_side = np.sign(u[0] * (p.y - q.y) - u[1] * (p.x - q.x))
    left, right = None, None
    for i in known_tree.query(p.buffer(NEIGHBOUR_M)):
        k = known[int(i)]
        if k["base"] != e["base"] or (exclude and k["id"] in exclude):
            continue
        if want is not None and k["n"] % 2 != want:
            continue
        kx, ky = k["xy"]
        if np.sign(u[0] * (ky - q.y) - u[1] * (kx - q.x)) != my_side:
            continue
        if math.hypot(kx - p.x, ky - p.y) > NEIGHBOUR_M:
            continue
        t = (kx - q.x) * u[0] + (ky - q.y) * u[1]
        if t < 0 and (left is None or t > left[0]):
            left = (t, k["n"])
        elif t >= 0 and (right is None or t < right[0]):
            right = (t, k["n"])
    if left and right and right[0] - left[0] > 1.0:
        n = left[1] + (0.0 - left[0]) / (right[0] - left[0]) * (right[1] - left[1])
        lo, hi = min(left[1], right[1]), max(left[1], right[1])
    elif left or right:
        t, n0 = left or right
        n = n0 - t * est["per_m"]
        lo, hi = 1, 10 ** 6
    else:
        return None
    r = int(round(n))
    if want is not None and r % 2 != want:
        r += 1 if n >= r else -1
    return max(lo if want is None or lo % 2 == want else lo + 1, min(r, hi))


def nearest_street(p, edges, tree, limit=STREET_M):
    near = [int(i) for i in tree.query(p.buffer(limit))]
    if not near:
        return None
    i = min(near, key=lambda i: edges[i]["geom"].distance(p))
    e = edges[i]
    d = e["geom"].distance(p)
    if d > limit:
        return None
    s = e["geom"].project(p)
    rng = e["sides"].get(side_of(e, p, s)) or next(iter(e["sides"].values()))
    return {"edge": e, "zip": rng[3], "distance_m": round(d, 1), "at": e["geom"].interpolate(s)}


# ---- main ----------------------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--assets", default=ASSETS)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()
    out_path = args.out or os.path.join(args.assets, "building_addresses.json")

    with io.open(os.path.join(args.assets, "corridor_osm_tags.json"), encoding="utf-8") as f:
        ours = json.load(f)["buildings"]
    wanted = set(b["osm_id"] for b in ours.values())
    print("%d buildings, %d OpenStreetMap elements" % (len(ours), len(wanted)), flush=True)

    osm_paths = [os.path.join(args.assets, "osm_files", n) for n in ("fullcorridor.osm", "aircorridor.osm")]
    buildings, points, streets, lines, border_ways = read_osm(osm_paths, wanted)
    border = Border(border_ways)
    edges = read_tiger(tiger_files(os.path.join(args.assets, "tiger")))
    print("  %d census street segments with house number ranges; the boundary in %d pieces" % (
        len(edges), len(border.lines)), flush=True)

    edge_tree = STRtree([e["geom"] for e in edges])
    street_list = [s for s in streets.values() if "line" in s]
    street_geoms = [LineString(s["line"]) for s in street_list]
    street_tree = STRtree(street_geoms)
    point_list = [p for p in points.values() if p["tags"].get("addr:housenumber") and p["tags"].get("addr:street")]
    point_tree = STRtree([Point(p["xy"]) for p in point_list])
    node_points = {p["node"]: p for p in points.values() if "node" in p}

    usable_lines, line_trouble = [], collections.Counter()
    for ln in lines.values():
        if "line" not in ln:
            line_trouble["no geometry"] += 1
            continue
        a, b = (node_points.get(n) for n in ln["ends"])
        if not a or not b:
            line_trouble["an end without an address"] += 1
            continue
        na, nb = number(a["tags"].get("addr:housenumber")), number(b["tags"].get("addr:housenumber"))
        street = a["tags"].get("addr:street") or b["tags"].get("addr:street") or ln["tags"].get("addr:street")
        if na is None or nb is None or not street:
            line_trouble["an end without a number or street"] += 1
            continue
        parity = {"even": "E", "odd": "O"}.get(ln["tags"].get("addr:interpolation"), "B")
        usable_lines.append({"geom": LineString(ln["line"]), "a": na, "b": nb, "parity": parity, "street": street,
                             "zip": postcode(a["tags"].get("addr:postcode") or b["tags"].get("addr:postcode")),
                             "city": a["tags"].get("addr:city") or b["tags"].get("addr:city")})
    line_trouble["usable"] = len(usable_lines)
    print("  address interpolation lines: %s" % dict(line_trouble), flush=True)
    line_tree = STRtree([ln["geom"] for ln in usable_lines]) if usable_lines else None

    # Every real address with a plain number, for estimates taken from neighbours.
    known = []
    for name, b in ours.items():
        t = b["tags"]
        if number(t.get("addr:housenumber")) is not None and t.get("addr:street") and b["osm_id"] in buildings:
            poly = footprint(buildings[b["osm_id"]][1])
            if poly is not None and not poly.is_empty:
                known.append({"id": name, "xy": (poly.centroid.x, poly.centroid.y), "n": number(t["addr:housenumber"]),
                              "base": base(t["addr:street"])})
    for k, p in points.items():
        if number(p["tags"].get("addr:housenumber")) is not None and p["tags"].get("addr:street"):
            known.append({"id": k, "xy": p["xy"], "n": number(p["tags"]["addr:housenumber"]),
                          "base": base(p["tags"]["addr:street"])})
    known_tree = STRtree([Point(k["xy"]) for k in known])

    # The mailing city of each ZIP code, as OpenStreetMap's addresses give it most often.
    votes = collections.defaultdict(collections.Counter)
    for tags in [b["tags"] for b in ours.values()] + [p["tags"] for p in points.values()]:
        z, c = postcode(tags.get("addr:postcode")), tags.get("addr:city")
        if z and c:
            votes[z][c.strip()] += 1
    zip_city = {z: c.most_common(1)[0][0] for z, c in votes.items()}
    city_points = [p for p in points.values() if p["tags"].get("addr:city")]
    city_tree = STRtree([Point(p["xy"]) for p in city_points])

    def osm_spelling(name, at):
        """OpenStreetMap's name for a census street, if a street of that name runs beside the point."""
        k = base(name)
        for i in street_tree.query(at.buffer(NAME_M)):
            if base(street_list[int(i)]["name"]) == k:
                return street_list[int(i)]["name"]
        return written_out(name)

    def nearby_city(p):
        near = [int(i) for i in city_tree.query(p.buffer(2000))]
        if not near:
            return None
        return city_points[min(near, key=lambda i: Point(city_points[i]["xy"]).distance(p))]["tags"]["addr:city"]

    results, counts = {}, collections.Counter()
    footprints = {}
    started = time.time()
    for n, (name, b) in enumerate(sorted(ours.items())):
        tags = b["tags"]
        kind, rings = buildings.get(b["osm_id"], (None, None))
        poly = footprint(rings) if rings else None
        if poly is None or poly.is_empty:
            counts["no footprint"] += 1
            continue
        footprints[name] = poly
        c = poly.centroid if poly.contains(poly.centroid) else poly.representative_point()
        lo, la = lonlat(c.x, c.y)
        canada = border.in_canada(c)
        rec = {"tile": b["tile"], "osm": "%s/%s" % (kind, b["osm_id"]), "lon": round(lo, 7), "lat": round(la, 7),
               "country": "CA" if canada else "US"}
        for k in ("name", "building", "amenity", "shop", "office", "tourism", "leisure", "healthcare",
                  "religion", "building:levels", "height", "website"):
            if tags.get(k):
                rec.setdefault("osm_tags", {})[k] = tags[k]
        house, street = tags.get("addr:housenumber"), tags.get("addr:street")
        zipcode, city = postcode(tags.get("addr:postcode")), tags.get("addr:city")
        source = "osm" if house and street else None
        if source is None:
            grown = poly.buffer(1.0)
            inside = [point_list[int(i)] for i in point_tree.query(grown)]
            inside = [p for p in inside if grown.contains(Point(p["xy"]))]
            if inside:
                inside.sort(key=lambda p: Point(p["xy"]).distance(c))
                t = inside[0]["tags"]
                house, street, source = t["addr:housenumber"], t["addr:street"], "osm-point"
                zipcode = zipcode or postcode(t.get("addr:postcode"))
                city = city or t.get("addr:city")
                others = sorted(set("%s %s" % (p["tags"]["addr:housenumber"], p["tags"]["addr:street"])
                                    for p in inside[1:]) - {"%s %s" % (house, street)})
                if others:
                    rec["other_addresses"] = others[:20]
        if source is None and line_tree is not None and not street:
            near = [int(i) for i in line_tree.query(c.buffer(LINE_M))]
            if near:
                ln = usable_lines[min(near, key=lambda i: usable_lines[i]["geom"].distance(c))]
                if ln["geom"].distance(c) <= LINE_M:
                    f = ln["geom"].project(c) / ln["geom"].length if ln["geom"].length else 0.0
                    house = str(snap(ln["a"] + f * (ln["b"] - ln["a"]), ln["a"], ln["b"], ln["parity"]))
                    street, source = ln["street"], "osm-line"
                    zipcode = zipcode or ln["zip"]
                    city = city or ln["city"]
        est = None
        if source is None and not canada:
            est = census_estimate(c, edges, edge_tree, street_base=base(street) if street else None,
                                  limit=CENSUS_M if not street else 2 * CENSUS_M)
            if est:
                pinned = from_neighbours(c, est, known, known_tree, exclude={name})
                house, source = str(pinned if pinned is not None else est["housenumber"]), \
                    "neighbours" if pinned is not None else "census"
                street = street or osm_spelling(est["edge"]["name"], est["at"])
                rec["street_distance_m"] = est["distance_m"]
        ns = None
        if source is None and not canada:
            ns = nearest_street(c, edges, edge_tree)
            if ns:
                source = "street"
                street = street or osm_spelling(ns["edge"]["name"], ns["at"])
                rec["street_distance_m"] = ns["distance_m"]
        if source is None and canada:
            # No census across the river, and too few address points in Windsor to estimate a
            # number from: the nearest street OpenStreetMap names, and no number.
            near = [int(i) for i in street_tree.query(c.buffer(CENSUS_M))]
            if near:
                i = min(near, key=lambda i: street_geoms[i].distance(c))
                if street_geoms[i].distance(c) <= CENSUS_M:
                    street, source = street or street_list[i]["name"], "street"
                    rec["street_distance_m"] = round(street_geoms[i].distance(c), 1)
        if not zipcode and not canada:
            z = est or ns or nearest_street(c, edges, edge_tree)
            zipcode = z["zip"] if z else None
        city = city or zip_city.get(zipcode or "") or nearby_city(c)
        region = "ON" if canada else "MI"
        rec.update({"housenumber": house, "street": street, "city": city, "state": region, "postcode": zipcode,
                    "source": source or "none"})
        parts = [" ".join(x for x in (house, street) if x), city, " ".join(x for x in (region, zipcode) if x)]
        rec["address"] = ", ".join(x for x in parts if x) if (street or city) else None
        results[name] = rec
        counts[source or "none"] += 1
        counts["in Canada"] += canada
        if (n + 1) % 10000 == 0:
            print("  %d buildings addressed, %.0f s" % (n + 1, time.time() - started), flush=True)

    # ---- how good the estimates are, where the real address is known -----------------------------
    trial = collections.Counter()
    plain, pinned_d = [], []
    by_kind = collections.defaultdict(collections.Counter)
    for name, rec in results.items():
        if rec["source"] != "osm" or number(rec["housenumber"]) is None or rec["country"] != "US":
            continue
        c = Point(xy(rec["lon"], rec["lat"]))
        est = census_estimate(c, edges, edge_tree)
        trial["tried"] += 1
        if not est:
            continue
        trial["estimated"] += 1
        kind = rec.get("osm_tags", {}).get("building", "yes")
        kind = "houses" if kind in ("house", "detached", "residential", "semidetached_house", "bungalow") else \
            "apartments" if kind == "apartments" else "other buildings"
        right = est["edge"]["base"] == base(rec["street"])
        by_kind[kind]["estimated"] += 1
        by_kind[kind]["street right"] += right
        if right:
            truth = number(rec["housenumber"])
            plain.append(abs(est["housenumber"] - truth))
            # Leave out the building's own address, and any address point standing inside it.
            grown = footprints[name].buffer(1.0)
            own = {name} | {known[int(i)]["id"] for i in known_tree.query(grown)
                            if grown.contains(Point(known[int(i)]["xy"]))}
            p = from_neighbours(c, est, known, known_tree, exclude=own)
            if p is not None:
                pinned_d.append(abs(p - truth))
        if rec["postcode"] and est["zip"]:
            trial["zip compared"] += 1
            trial["zip right"] += est["zip"] == rec["postcode"]

    def spread(d):
        d = np.array(d) if d else np.array([0])
        return {"count": int(len(d)), "exact": "%.0f%%" % (100.0 * (d == 0).mean()),
                "within 10": "%.0f%%" % (100.0 * (d <= 10).mean()), "within 50": "%.0f%%" % (100.0 * (d <= 50).mean()),
                "median error": int(np.median(d))}

    validation = {
        "tested": "%d US buildings with a real OpenStreetMap address, each estimated as if it had none (%d "
                  "got an estimate)" % (trial["tried"], trial["estimated"]),
        "street right": {k: "%d of %d (%.0f%%)" % (v["street right"], v["estimated"],
                                                  100.0 * v["street right"] / max(v["estimated"], 1))
                         for k, v in sorted(by_kind.items())},
        "house number from the census range alone, where the street was right": spread(plain),
        "house number from neighbours, where the street was right and a neighbour qualified": spread(pinned_d),
        "ZIP code right": "%d of %d (%.0f%%)" % (trial["zip right"], trial["zip compared"],
                                                 100.0 * trial["zip right"] / max(trial["zip compared"], 1)),
    }
    out = {
        "WHAT": "An address for every building in the corridor level, keyed by the building's actor label. "
                "'source' says where each came from; Tools/building_addresses.py says what each source means "
                "and 'validation' how far the estimates can be trusted. OpenStreetMap data (c) OpenStreetMap "
                "contributors, Open Database License; this is a derived database under the same licence. "
                "TIGER/Line address ranges are public domain.",
        "sources": dict(counts), "validation": validation, "buildings": results}
    with io.open(out_path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(out, f, ensure_ascii=False, indent=0, sort_keys=True)
    print("wrote %s" % out_path)
    print("sources: %s" % dict(counts))
    print(json.dumps(validation, indent=1))


if __name__ == "__main__":
    main()
