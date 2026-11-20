"""download_copernicus_dem.py - download the Copernicus global 30 m DEM for ANY area on Earth.

    py -3.10 download_copernicus_dem.py --bbox 7.40 46.90 7.50 46.98 --out dem_cache
    py -3.10 download_copernicus_dem.py --aoi my_site.kml --resolution 90 --out dem_cache

WHY THIS ONE. Copernicus GLO-30 is the most accurate free global elevation model, covers every land
surface, and is published as open data on AWS with no account or API key. Use it anywhere outside
the United States, or inside it as a coarse fallback beneath 3DEP.

IT IS A SURFACE MODEL (DSM), not bare earth: heights include buildings and tree canopy. For a
Landscape under placed buildings and trees prefer a bare-earth DTM where one exists (3DEP in the
US, national lidar programmes elsewhere). See README.md, "Using any elevation data".

LICENCE. Free for any use with attribution. Keep this line with anything you publish:

    produced using Copernicus WorldDEM-30 (c) DLR e.V. 2010-2014 and (c) Airbus Defence and Space
    GmbH 2014-2018 provided under COPERNICUS by the European Union and ESA; all rights reserved.
"""
import argparse
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import geodata_common as gc

BUCKETS = {
    30: ("https://copernicus-dem-30m.s3.amazonaws.com", "10"),
    90: ("https://copernicus-dem-90m.s3.amazonaws.com", "30"),
}


def tile_name(lat, lon, arcsec):
    """Tiles are 1x1 degree, named by their SOUTH-WEST corner."""
    ns = "N%02d_00" % lat if lat >= 0 else "S%02d_00" % -lat
    ew = "E%03d_00" % lon if lon >= 0 else "W%03d_00" % -lon
    return "Copernicus_DSM_COG_%s_%s_%s_DEM" % (arcsec, ns, ew)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    gc.add_aoi_arguments(ap)
    ap.add_argument("--resolution", type=int, choices=[30, 90], default=30,
                    help="30 m (GLO-30, default) or 90 m (GLO-90)")
    ap.add_argument("--out", required=True)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    aoi = gc.aoi_from_args(args)
    base, arcsec = BUCKETS[args.resolution]
    poly = aoi.polygon()
    tiles = []
    for lat in range(int(math.floor(aoi.south)), int(math.ceil(aoi.north))):
        for lon in range(int(math.floor(aoi.west)), int(math.ceil(aoi.east))):
            if poly is not None:
                from shapely.geometry import box
                if not poly.intersects(box(lon, lat, lon + 1, lat + 1)):
                    continue
            tiles.append(tile_name(lat, lon, arcsec))
    print("area      %.5f %.5f %.5f %.5f" % aoi.bbox)
    print("tiles     %d x GLO-%d" % (len(tiles), args.resolution))
    for t in tiles:
        print("  %s.tif" % t)
    if args.dry_run:
        return

    sess, got = gc.session(), []
    for t in tiles:
        url = "%s/%s/%s.tif" % (base, t, t)
        dest = os.path.join(args.out, t + ".tif")
        try:
            gc.download(url, dest, sess)
            got.append(os.path.basename(dest))
        except FileNotFoundError:
            print("  none     %s (open ocean: no tile is published)" % t)
    gc.write_json(os.path.join(args.out, "download_copernicus_%dm.json" % args.resolution), {
        "product": "Copernicus DEM GLO-%d (DSM)" % args.resolution,
        "aoi_bbox_wgs84": list(aoi.bbox), "files": got,
        "attribution": "produced using Copernicus WorldDEM-30 (c) DLR e.V. 2010-2014 and (c) Airbus "
                       "Defence and Space GmbH 2014-2018 provided under COPERNICUS by the European "
                       "Union and ESA; all rights reserved.",
    })
    print("\n%d raster(s) ready in %s" % (len(got), args.out))


if __name__ == "__main__":
    main()
