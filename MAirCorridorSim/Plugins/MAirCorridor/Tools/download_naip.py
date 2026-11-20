"""download_naip.py - download USDA NAIP aerial imagery as tiles lined up with a Landscape.

    py -3.10 download_naip.py --plan landscape/corridor.json --metres 0.5 --out naip --name corridor_naip
    py -3.10 download_naip.py --aoi site.kml --metres 1 --out naip --name site_naip

WHAT NAIP IS. The USDA National Agriculture Imagery Program flies the continental United States
every two to three years in leaf-on season. It is natural-colour (plus near-infrared) aerial
photography at 0.3-1 m per pixel, orthorectified, and PUBLIC DOMAIN. It does not cover areas outside
the lower 48 states; see README.md for imagery elsewhere.

WHERE IT COMES FROM. The USGS "USGSNAIPPlus" ImageServer, which serves the most recent NAIP for any
location in any projection through ArcGIS REST exportImage. No account or key is needed. The server
returns at most 4000 x 4000 pixels per request, so large areas are fetched as many requests (cached
under <out>/_cache, so an interrupted run resumes) and assembled into large tiles here.

LINED UP WITH THE TERRAIN. Given --plan (a JSON from build_landscape.py), tile 0,0 starts exactly at
the Landscape's north-west corner in the Landscape's projection, and every pixel is --metres wide, so
imagery and terrain share one grid and a material can place the photos by world position alone. The
index JSON written beside the tiles records every tile's ground extent.

TILE LAYOUT. Tiles are named <name>.<UDIM>.png. UDIM u increases EAST and v increases SOUTH (row 0 is
north, as in the heightmap). Tiles on the east and south edges are full squares of real photography
that extend past the terrain; overhang_px in the index says by how much. Past 10 tiles across, UDIM
numbering cannot express the column, so files are named <name>_uXX_vYY.png instead.
"""
import argparse
import concurrent.futures as cf
import json
import math
import os
import sys

import numpy as np

try:
    import rasterio
    from rasterio.crs import CRS
    from rasterio.warp import transform_bounds
    from PIL import Image
except ImportError:
    sys.exit("download_naip.py needs rasterio and Pillow: py -3.10 -m pip install -r requirements.txt")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import geodata_common as gc

Image.MAX_IMAGE_PIXELS = None
SERVICE = "https://imagery.nationalmap.gov/arcgis/rest/services/USGSNAIPPlus/ImageServer/exportImage"
MAX_REQUEST_PX = 4000


def fmt(v):
    return ("%.3f" % v).rstrip("0").rstrip(".")


def fetch(sess, cache, epsg, west, north, m, px, retries=5):
    east, south = west + px * m, north - px * m
    name = "USGSNAIPPlus_%d_%s_%s_%s_%s_%dx%d.tif" % (epsg, fmt(west), fmt(south), fmt(east), fmt(north), px, px)
    dest = os.path.join(cache, name)
    params = {"bbox": "%s,%s,%s,%s" % (fmt(west), fmt(south), fmt(east), fmt(north)),
              "bboxSR": epsg, "imageSR": epsg, "size": "%d,%d" % (px, px), "format": "tiff",
              "pixelType": "U8", "bandIds": "0,1,2", "interpolation": "RSP_BilinearInterpolation",
              "f": "image"}
    if not os.path.exists(dest):
        gc.download(SERVICE, dest, sess, retries=retries, quiet=True, params=params)
    with rasterio.open(dest) as d:
        if d.count < 3 or d.width != px or d.height != px:
            os.remove(dest)
            raise RuntimeError("unexpected response for %s (%d bands, %dx%d)" % (name, d.count, d.width, d.height))
        return d.read([1, 2, 3])


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--plan", help="landscape plan JSON from build_landscape.py: imagery aligns to it")
    src.add_argument("--bbox", nargs=4, type=float, metavar=("WEST", "SOUTH", "EAST", "NORTH"))
    src.add_argument("--aoi", metavar="FILE.kml|FILE.kmz")
    ap.add_argument("--buffer-m", type=float, default=0.0)
    ap.add_argument("--epsg", type=int, default=0, help="projection when not using --plan (default: UTM)")
    ap.add_argument("--datum", choices=["WGS84", "NAD83"], default="NAD83")
    ap.add_argument("--metres", type=float, default=1.0,
                    help="ground metres per pixel (NAIP is natively 0.3-0.6 m; default 1)")
    ap.add_argument("--tile-px", type=int, default=8192, choices=[1024, 2048, 4096, 8192, 16384],
                    help="output tile edge in pixels (default 8192)")
    ap.add_argument("--request-px", type=int, default=2048, choices=[512, 1024, 2048],
                    help="pixels per server request (default 2048; the server maximum is 4000)")
    ap.add_argument("--workers", type=int, default=4, help="parallel requests (be polite; default 4)")
    ap.add_argument("--out", required=True)
    ap.add_argument("--name", required=True)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    m = args.metres
    if args.plan:
        plan = json.load(open(args.plan))
        epsg = int(plan["projection"].split(":")[1])
        X0, Y1 = plan["utm_origin"]
        wm, hm = plan["world_metres"] if "world_metres" in plan else (
            (plan["resolution"][0] - 1) * plan["quad_metres"], (plan["resolution"][1] - 1) * plan["quad_metres"])
        for_landscape = os.path.basename(args.plan)
    else:
        aoi = gc.aoi_from_args(args)
        lon, lat = aoi.centre()
        epsg = args.epsg or gc.utm_epsg_for(lon, lat, args.datum)
        minx, miny, maxx, maxy = transform_bounds(CRS.from_epsg(4326), CRS.from_epsg(epsg), *aoi.bbox, densify_pts=41)
        X0, Y1 = math.floor(minx / m) * m, math.ceil(maxy / m) * m
        wm, hm = maxx - X0, Y1 - miny
        for_landscape = None

    T, R = args.tile_px, args.request_px
    px_w, px_h = int(math.ceil(wm / m)), int(math.ceil(hm / m))
    tx, ty = int(math.ceil(px_w / float(T))), int(math.ceil(px_h / float(T)))
    per_tile = (T // R) ** 2
    udim_ok = tx <= 10
    print("grid      EPSG:%d, origin %s %s, %.3g m/px, %d x %d px" % (epsg, fmt(X0), fmt(Y1), m, px_w, px_h))
    print("tiles     %d x %d of %d px (%d server requests each, %d total, ~%s of PNG)"
          % (tx, ty, T, per_tile, tx * ty * per_tile, gc.human_bytes(tx * ty * T * T * 3 * 0.6)))
    if not udim_ok:
        print("note      more than 10 tiles across: files are named _uXX_vYY instead of by UDIM")
    if args.dry_run:
        return

    cache = os.path.join(args.out, "_cache")
    os.makedirs(cache, exist_ok=True)
    sess = gc.session()
    entries, empty = [], 0
    for v in range(ty):
        for u in range(tx):
            fname = ("%s.%d.png" % (args.name, 1001 + u + 10 * v)) if udim_ok else \
                    ("%s_u%02d_v%02d.png" % (args.name, u, v))
            west, north = X0 + u * T * m, Y1 - v * T * m
            path = os.path.join(args.out, fname)
            if not os.path.exists(path):
                tile = np.zeros((T, T, 3), dtype="uint8")
                jobs = {}
                with cf.ThreadPoolExecutor(max_workers=args.workers) as ex:
                    for j in range(T // R):
                        for i in range(T // R):
                            jobs[ex.submit(fetch, sess, cache, epsg, west + i * R * m,
                                           north - j * R * m, m, R)] = (i, j)
                    done = 0
                    for fut in cf.as_completed(jobs):
                        i, j = jobs[fut]
                        tile[j * R:(j + 1) * R, i * R:(i + 1) * R] = np.moveaxis(fut.result(), 0, -1)
                        done += 1
                        sys.stdout.write("\r  %s  %d/%d requests" % (fname, done, len(jobs)))
                        sys.stdout.flush()
                has = bool(tile.any())
                empty += 0 if has else 1
                Image.fromarray(tile).save(path, compress_level=6)
                del tile
                print("\r  %s  written%s          " % (fname, "" if has else "  (NO IMAGERY HERE)"))
            else:
                print("  %s  cached" % fname)
            # A world file and projection beside each PNG, so any GIS can overlay it for checking.
            with open(os.path.splitext(path)[0] + ".pgw", "w") as f:
                f.write("%r\n0\n0\n%r\n%r\n%r\n" % (m, -m, west + m / 2.0, north - m / 2.0))
            with open(os.path.splitext(path)[0] + ".prj", "w") as f:
                f.write(CRS.from_epsg(epsg).to_wkt())
            entries.append({
                "udim": (1001 + u + 10 * v) if udim_ok else None, "u": u, "v": v, "file": fname,
                "px": [T, T], "overhang_px": [max(0, (u + 1) * T - px_w), max(0, (v + 1) * T - px_h)],
                "utm_west": west, "utm_north": north, "utm_east": west + T * m, "utm_south": north - T * m,
            })

    gc.write_json(os.path.join(args.out, args.name + ".json"), {
        "name": args.name, "for_landscape": for_landscape, "projection": "EPSG:%d" % epsg,
        "metres_per_pixel": m, "pixels": [px_w, px_h], "tile_px": T, "tiles": [tx, ty],
        "utm_origin_nw": [X0, Y1], "world_metres": [px_w * m, px_h * m],
        "udim_base": 1001 if udim_ok else None, "row0_is_north": True,
        "source": "USDA NAIP via USGS USGSNAIPPlus ImageServer exportImage (public domain)",
        "tiles_without_imagery": empty,
        "UV_CONVENTION": "u increases EAST, v increases SOUTH. Unreal's UDIM v conventionally increases "
                         "upward, so a material sampling these must flip V.",
        "entries": entries,
    })
    print("\nindex     %s" % os.path.join(args.out, args.name + ".json"))


if __name__ == "__main__":
    main()
