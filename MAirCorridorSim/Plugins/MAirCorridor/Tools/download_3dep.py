"""download_3dep.py - download USGS 3DEP elevation for any area of the United States.

    py -3.10 download_3dep.py --aoi corridor.kml --product 1m    --out dem_cache
    py -3.10 download_3dep.py --bbox -83.71 42.29 -83.69 42.31 --product 13 --out dem_cache
    py -3.10 download_3dep.py --aoi corridor.kml --product 1m --dry-run

PRODUCTS (all bare-earth, all public domain, all from the USGS 3D Elevation Program):

    1m    1 metre lidar DEM, UTM/NAD83. Best detail. Coverage is project-by-project and not
          complete; where two projects overlap you get both, newest listed first.
    19    1/9 arc-second (~3 m) lidar DEM. Retired by USGS but still served; fills gaps in 1m.
    13    1/3 arc-second (~10 m). SEAMLESS across the United States. The safe fallback.
    1     1 arc-second (~30 m). Seamless, tiny files, good for wide surrounds.
    opr   Original Product Resolution: whatever each lidar project delivered, usually 0.5-2 m.

A typical high-detail build downloads 1m AND 13 and hands both to build_landscape.py: the 1 m
data is used wherever it exists and the 10 m data fills every gap, so there are no holes.

HOW IT FINDS DATA. 1m, 19 and opr are indexed through The National Map Access API
(https://tnmaccess.nationalmap.gov/api/v1/docs). The seamless 13 and 1 products are addressed
directly on the 1-degree grid USGS publishes them on, because the API also returns superseded
"historical" copies of those tiles and the current one is what you want.

Outside the United States use download_copernicus_dem.py, or any DEM you already have - see
README.md, "Using any elevation data".
"""
import argparse
import math
import os
import sys
import time
import zipfile

import requests

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import geodata_common as gc

TNM_API = "https://tnmaccess.nationalmap.gov/api/v1/products"
S3 = "https://prd-tnm.s3.amazonaws.com/StagedProducts/Elevation"

API_DATASETS = {
    "1m": "Digital Elevation Model (DEM) 1 meter",
    "19": "National Elevation Dataset (NED) 1/9 arc-second",
    "opr": "Original Product Resolution (OPR) Digital Elevation Model (DEM)",
}
SEAMLESS = {"13": "13", "1": "1"}          # product -> directory and file prefix on S3


def _query(params, sess, retries=6):
    """The National Map API times out under load (HTTP 502/503/504). Those are worth waiting out;
    anything else is a real error and is raised."""
    for attempt in range(1, retries + 1):
        try:
            r = sess.get(TNM_API, params=params, timeout=180)
            if r.status_code in (429, 500, 502, 503, 504):
                raise requests.HTTPError("HTTP %d" % r.status_code)
            r.raise_for_status()
            return r.json()
        except (requests.ConnectionError, requests.Timeout, requests.HTTPError, ValueError) as e:
            if attempt == retries:
                raise SystemExit("The National Map API did not answer after %d tries (%s). It is "
                                 "often briefly overloaded; try again in a few minutes." % (retries, e))
            wait = min(60, 5 * attempt)
            print("  API busy (%s), retrying in %ds" % (e, wait))
            time.sleep(wait)


def api_products(aoi, product, sess):
    """Every product the API lists for the box, newest first, de-duplicated by URL."""
    items, offset = [], 0
    bbox = "%.6f,%.6f,%.6f,%.6f" % aoi.bbox
    while True:
        d = _query({"datasets": API_DATASETS[product], "bbox": bbox, "max": 500,
                    "offset": offset, "outputFormat": "JSON"}, sess)
        batch = d.get("items", [])
        items.extend(batch)
        offset += len(batch)
        if not batch or offset >= int(d.get("total", 0)):
            break
    seen, out = set(), []
    for it in sorted(items, key=lambda i: i.get("publicationDate") or "", reverse=True):
        url = it.get("downloadURL")
        if not url or url in seen:
            continue
        seen.add(url)
        out.append({"url": url, "size": it.get("sizeInBytes"), "title": it.get("title"),
                    "published": it.get("publicationDate"), "format": it.get("format")})
    return _intersecting(out, aoi, items)


def _intersecting(out, aoi, items):
    """The API matches on a generous footprint. Keep what the polygon (not just its box) touches."""
    poly = aoi.polygon()
    if poly is None:
        return out
    from shapely.geometry import box
    extent = {it.get("downloadURL"): it.get("boundingBox") for it in items}
    kept = []
    for o in out:
        bb = extent.get(o["url"])
        if not bb or poly.intersects(box(bb["minX"], bb["minY"], bb["maxX"], bb["maxY"])):
            kept.append(o)
    return kept


def seamless_tiles(aoi, product):
    """1x1 degree tiles on USGS's grid. A tile is named by its NORTH-WEST corner: n43w084 spans
    42-43 N and 84-83 W."""
    prefix = SEAMLESS[product]
    out = []
    for lat in range(int(math.floor(aoi.south)), int(math.ceil(aoi.north))):
        for lon in range(int(math.floor(aoi.west)), int(math.ceil(aoi.east))):
            north = lat + 1
            ns = "n%02d" % north if north >= 0 else "s%02d" % -north
            ew = "w%03d" % -lon if lon < 0 else "e%03d" % lon
            key = ns + ew
            out.append({"url": "%s/%s/TIFF/current/%s/USGS_%s_%s.tif" % (S3, prefix, key, prefix, key),
                        "size": None, "title": "USGS %s %s" % (prefix, key),
                        "published": "current", "format": "GeoTIFF"})
    poly = aoi.polygon()
    if poly is not None:
        from shapely.geometry import box
        def touches(o):
            k = o["url"].rsplit("_", 1)[-1][:-4]
            n = int(k[1:3]) * (1 if k[0] == "n" else -1)
            w = int(k[4:7]) * (-1 if k[3] == "w" else 1)
            return poly.intersects(box(w, n - 1, w + 1, n))
        out = [o for o in out if touches(o)]
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    gc.add_aoi_arguments(ap)
    ap.add_argument("--product", required=True, choices=["1m", "19", "13", "1", "opr"])
    ap.add_argument("--out", required=True, help="directory to download into (reused as a cache)")
    ap.add_argument("--dry-run", action="store_true", help="list what would be downloaded, then stop")
    ap.add_argument("--max-files", type=int, default=0, help="stop after this many files (0 = all)")
    args = ap.parse_args()

    aoi = gc.aoi_from_args(args)
    sess = gc.session()
    print("area      %.5f %.5f %.5f %.5f  (%s)" % (aoi.bbox + (aoi.name,)))

    files = seamless_tiles(aoi, args.product) if args.product in SEAMLESS \
        else api_products(aoi, args.product, sess)
    if args.max_files:
        files = files[:args.max_files]
    known = sum(f["size"] or 0 for f in files)
    print("product   %s: %d file(s)%s" % (args.product, len(files),
          ", %s" % gc.human_bytes(known) if known else ""))
    for f in files:
        print("  %-10s %9s  %s" % (f["published"] or "", gc.human_bytes(f["size"]) if f["size"] else "?",
                                    f["url"].rsplit("/", 1)[-1]))
    if args.dry_run or not files:
        if not files:
            print("Nothing found. 1m and 19 coverage is incomplete; try --product 13.")
        return

    got, missing = [], 0
    for f in files:
        dest = os.path.join(args.out, f["url"].rsplit("/", 1)[-1])
        try:
            gc.download(f["url"], dest, sess)
        except FileNotFoundError:
            missing += 1                              # open water: USGS publishes no tile there
            print("  none     %s (no tile at this location)" % os.path.basename(dest))
            continue
        if dest.lower().endswith(".zip"):             # the 1/9 product ships as zipped .img
            with zipfile.ZipFile(dest) as z:
                for n in z.namelist():
                    if n.lower().endswith((".img", ".tif", ".tiff")):
                        target = os.path.join(args.out, os.path.basename(n))
                        if not os.path.exists(target):
                            with z.open(n) as src, open(target, "wb") as out:
                                out.write(src.read())
                        got.append(target)
        else:
            got.append(dest)

    manifest = os.path.join(args.out, "download_3dep_%s.json" % args.product)
    gc.write_json(manifest, {
        "product": args.product, "aoi_bbox_wgs84": list(aoi.bbox), "aoi_name": aoi.name,
        "source": "USGS 3D Elevation Program (3DEP), public domain",
        "files": [os.path.basename(p) for p in got],
        "urls": [f["url"] for f in files],
    })
    print("\n%d raster(s) ready in %s%s" % (len(got), args.out,
          ", %d location(s) had no tile" % missing if missing else ""))
    print("next: py -3.10 build_landscape.py --dem \"%s\" ...   (a directory takes its .tif and .img)" % args.out)


if __name__ == "__main__":
    main()
