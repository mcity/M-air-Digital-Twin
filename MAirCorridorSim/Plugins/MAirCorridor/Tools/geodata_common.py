"""Shared pieces for the MAirCorridor geodata tools: areas of interest, downloads, UTM zones.

Nothing in here is specific to M-City. An area of interest is either a longitude/latitude box or
a KML/KMZ polygon drawn in Google Earth, QGIS or any GIS, and every tool takes the same two forms.
"""
import io
import json
import math
import os
import sys
import time
import xml.etree.ElementTree as ET
import zipfile

import requests

USER_AGENT = "MAirCorridor-geodata/1.0 (+https://github.com/sriceumich/MAirCorridor)"


# ---------------------------------------------------------------------------------------------
# Areas of interest
# ---------------------------------------------------------------------------------------------

class AOI:
    """A region in WGS84 longitude/latitude. `ring` is the polygon outline when one was given,
    otherwise the four corners of the box."""

    def __init__(self, west, south, east, north, ring=None, name="aoi"):
        if not (west < east and south < north):
            raise ValueError("AOI box must be west < east and south < north, got %r"
                             % ((west, south, east, north),))
        self.west, self.south, self.east, self.north = west, south, east, north
        self.ring = ring or [(west, south), (east, south), (east, north), (west, north)]
        self.name = name

    @property
    def bbox(self):
        return (self.west, self.south, self.east, self.north)

    def centre(self):
        return ((self.west + self.east) / 2.0, (self.south + self.north) / 2.0)

    def polygon(self):
        """A shapely Polygon, or None when shapely is not installed."""
        try:
            from shapely.geometry import Polygon
        except ImportError:
            return None
        return Polygon(self.ring)


def _kml_text(path):
    if path.lower().endswith(".kmz"):
        with zipfile.ZipFile(path) as z:
            names = [n for n in z.namelist() if n.lower().endswith(".kml")]
            if not names:
                raise ValueError("%s contains no .kml" % path)
            return z.read(names[0])
    with open(path, "rb") as f:
        return f.read()


def load_kml_aoi(path):
    """Read the FIRST polygon (or, failing that, every coordinate) from a KML or KMZ file.

    KML coordinates are always WGS84 longitude,latitude[,altitude], whatever tool wrote them."""
    root = ET.fromstring(_kml_text(path))
    ns = {"k": "http://www.opengis.net/kml/2.2"}
    rings = root.findall(".//k:Polygon//k:outerBoundaryIs//k:coordinates", ns)
    nodes = rings[:1] if rings else root.findall(".//k:coordinates", ns)
    pts = []
    for node in nodes:
        for tok in (node.text or "").split():
            parts = tok.split(",")
            if len(parts) >= 2:
                pts.append((float(parts[0]), float(parts[1])))
    if len(pts) < 2:
        raise ValueError("%s: no coordinates found" % path)
    lons = [p[0] for p in pts]
    lats = [p[1] for p in pts]
    name = os.path.splitext(os.path.basename(path))[0].replace(" ", "_")
    ring = pts if (rings and len(pts) >= 3) else None
    return AOI(min(lons), min(lats), max(lons), max(lats), ring=ring, name=name)


def add_aoi_arguments(parser):
    g = parser.add_mutually_exclusive_group(required=True)
    g.add_argument("--bbox", nargs=4, type=float, metavar=("WEST", "SOUTH", "EAST", "NORTH"),
                   help="area of interest in WGS84 degrees, e.g. --bbox -83.71 42.29 -83.69 42.31")
    g.add_argument("--aoi", metavar="FILE.kml|FILE.kmz",
                   help="area of interest as a KML/KMZ polygon (Google Earth, QGIS, Global Mapper...)")
    parser.add_argument("--buffer-m", type=float, default=0.0,
                        help="grow the area by this many metres on every side (default 0)")


def aoi_from_args(args):
    aoi = load_kml_aoi(args.aoi) if args.aoi else AOI(*args.bbox)
    if args.buffer_m:
        lat = math.radians((aoi.south + aoi.north) / 2.0)
        dlat = args.buffer_m / 111320.0
        dlon = args.buffer_m / (111320.0 * max(0.01, math.cos(lat)))
        aoi = AOI(aoi.west - dlon, aoi.south - dlat, aoi.east + dlon, aoi.north + dlat,
                  ring=aoi.ring if aoi.ring and len(aoi.ring) > 4 else None, name=aoi.name)
    return aoi


# ---------------------------------------------------------------------------------------------
# Projections
# ---------------------------------------------------------------------------------------------

def utm_epsg_for(lon, lat, datum="WGS84"):
    """The UTM zone EPSG code covering a point. WGS84 works everywhere; NAD83 (the datum USGS
    publishes in) is offered for North America and differs from WGS84 by about a metre."""
    zone = int(math.floor((lon + 180.0) / 6.0)) + 1
    zone = min(max(zone, 1), 60)
    if datum.upper() == "NAD83":
        if lat < 0 or not (1 <= zone <= 23):
            raise ValueError("NAD83 UTM zones only cover North America (zones 1-23, north)")
        return 26900 + zone
    return (32600 if lat >= 0 else 32700) + zone


# ---------------------------------------------------------------------------------------------
# Downloads
# ---------------------------------------------------------------------------------------------

def session():
    s = requests.Session()
    s.headers["User-Agent"] = USER_AGENT
    return s


def download(url, dest, sess=None, retries=5, quiet=False, params=None):
    """Download to `dest`, resuming a partial file and retrying with backoff.

    The file is written to dest + ".part" and renamed only when complete, so an interrupted run
    never leaves something that looks finished. Completeness is checked against the SERVER's
    Content-Length, never a catalogue size: the USGS API's sizeInBytes can be stale by a few
    bytes, and trusting it rejects good files. Returns the path, or raises on final failure."""
    sess = sess or session()
    if os.path.exists(dest):
        if not quiet:
            print("  cached   %s" % os.path.basename(dest))
        return dest
    os.makedirs(os.path.dirname(os.path.abspath(dest)), exist_ok=True)
    part = dest + ".part"
    last = None
    total = 0
    for attempt in range(1, retries + 1):
        have = os.path.getsize(part) if os.path.exists(part) else 0
        headers = {"Range": "bytes=%d-" % have} if have and params is None else {}
        try:
            with sess.get(url, stream=True, timeout=(30, 300), headers=headers, params=params) as r:
                if r.status_code == 416:          # already complete
                    break
                if r.status_code == 404:
                    raise FileNotFoundError(url)
                r.raise_for_status()
                mode = "ab" if (have and r.status_code == 206) else "wb"
                total = int(r.headers.get("Content-Length", 0)) + (have if mode == "ab" else 0)
                done = have if mode == "ab" else 0
                t0 = time.time()
                with open(part, mode) as f:
                    for chunk in r.iter_content(chunk_size=1 << 20):
                        f.write(chunk)
                        done += len(chunk)
                        if not quiet and total and time.time() - t0 > 2:
                            sys.stdout.write("\r  %5.1f%%  %s" % (100.0 * done / total,
                                                               os.path.basename(dest)))
                            sys.stdout.flush()
                            t0 = time.time()
            break
        except FileNotFoundError:
            raise
        except Exception as e:                       # network trouble: back off and resume
            last = e
            wait = min(60, 2 ** attempt)
            if not quiet:
                print("\n  retry %d/%d after %s (%s)" % (attempt, retries, wait, e))
            time.sleep(wait)
    else:
        raise RuntimeError("download failed after %d attempts: %s (%s)" % (retries, url, last))
    if total and os.path.getsize(part) != total:
        raise RuntimeError("%s: got %d bytes, server said %d"
                           % (url, os.path.getsize(part), total))
    os.replace(part, dest)
    if not quiet:
        print("\r  fetched  %s (%.1f MB)" % (os.path.basename(dest), os.path.getsize(dest) / 1e6))
    return dest


def write_json(path, obj):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with io.open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(obj, f, indent=2)
        f.write("\n")


def human_bytes(n):
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024 or unit == "TB":
            return "%.1f %s" % (n, unit)
        n /= 1024.0
