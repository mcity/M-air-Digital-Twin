"""build_landscape.py - turn ANY elevation rasters into Unreal Landscape heightmaps and a plan.

    py -3.10 build_landscape.py --dem "dem_cache/USGS_one_meter_*.tif" "dem_cache/USGS_13_*.tif" \
        --aoi corridor.kml --metres 1 --out landscape --name corridor

    py -3.10 build_landscape.py --dem my_srtm.tif --metres 30 --out landscape --name valley

The output is one or more .r16 heightmaps plus <name>.json. In Unreal, Tools > M-Air Corridor >
"Build Unreal Landscape from Plan..." reads that JSON and builds every Landscape actor it describes.

WHAT IT ACCEPTS. Any raster GDAL can read: GeoTIFF, Erdas .img, .bil/.hdr, ASCII grid, .vrt, and
so on, in any projection and any vertical unit of metres. USGS 3DEP, Copernicus, SRTM, ASTER GDEM,
ALOS, national lidar DTMs, your own drone survey - they are all just rasters. List several and the
FIRST one that has data at a point wins, so give the finest data first and a coarse seamless product
last to fill the gaps.

WHY SEGMENTS. Unreal's Landscape import reads the whole source into memory and one actor is best
kept to about 8161 x 8161 vertices. A 1 m corridor is far bigger than that. So the area is cut into
a grid of segments, each its own Landscape actor, each built here one at a time, so memory stays
at a few hundred MB whatever the size of the area. Adjacent segments share their edge vertices
and ONE vertical range, so the terrain is continuous across every seam.

HEIGHTS. Unreal stores height as uint16. A Landscape with Z scale S turns a value H into
    world_cm = (H - 32768) * S / 128
so the tool picks the smallest S that fits the whole area's elevation range (finest height steps),
places every actor at the middle of that range, and writes the exact decode into the plan.
"""
import argparse
import glob
import math
import os
import sys

import numpy as np

try:
    import rasterio
    from rasterio.crs import CRS
    from rasterio.enums import Resampling
    from rasterio.features import geometry_mask
    from rasterio.transform import Affine
    from rasterio.warp import reproject, transform_bounds, transform as warp_points
    from rasterio.windows import from_bounds
except ImportError:
    sys.exit("build_landscape.py needs rasterio: py -3.10 -m pip install -r requirements.txt")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import geodata_common as gc

LEGAL_SECTIONS = (7, 15, 31, 63, 127, 255)
WGS84 = CRS.from_epsg(4326)
PLAUSIBLE_M = (-500.0, 9000.0)       # below the Dead Sea shore, above Everest: anything else is fill


# ---------------------------------------------------------------------------------------------

class Source:
    def __init__(self, path, rank):
        self.path, self.rank = path, rank
        self.ds = rasterio.open(path)
        if self.ds.crs is None:
            raise SystemExit("%s has no coordinate reference system; cannot place it" % path)
        rx = abs(self.ds.transform.a)
        self.res_m = rx * 111320.0 if self.ds.crs.is_geographic else rx * self._unit()
        self.bounds_wgs84 = transform_bounds(self.ds.crs, WGS84, *self.ds.bounds, densify_pts=21)

    def _unit(self):
        try:
            f = self.ds.crs.linear_units_factor[1]
            return float(f) if f else 1.0
        except Exception:
            return 1.0

    def describe(self):
        return {"class": self.rank, "file": os.path.basename(self.path),
                "native_resolution_m": round(self.res_m, 3), "crs": str(self.ds.crs)}


def expand(patterns):
    out = []
    for p in patterns:
        if os.path.isdir(p):
            hits = sorted(glob.glob(os.path.join(p, "*.tif")) + glob.glob(os.path.join(p, "*.img")))
        else:
            hits = sorted(glob.glob(p))
        if not hits:
            print("warning: nothing matched %s" % p)
        for h in hits:
            if h not in out:
                out.append(h)
    return out


def estimate_range(sources, dst_crs, box_dst):
    """Elevation min/max over the area, from decimated reads. Cheap, and within a metre or two;
    the margin added afterwards absorbs the difference, and clipping is counted if it ever bites."""
    lo, hi = math.inf, -math.inf
    for s in sources:
        try:
            b = transform_bounds(dst_crs, s.ds.crs, *box_dst, densify_pts=21)
            win = from_bounds(*b, transform=s.ds.transform).intersection(
                rasterio.windows.Window(0, 0, s.ds.width, s.ds.height))
        except Exception:
            continue
        if win.width < 1 or win.height < 1:
            continue
        k = max(1, int(max(win.width, win.height) // 1024))
        a = s.ds.read(1, window=win, out_shape=(max(1, int(win.height // k)), max(1, int(win.width // k))),
                      masked=True, resampling=Resampling.nearest).astype("float64")
        v = a.compressed()
        v = v[(v > PLAUSIBLE_M[0]) & (v < PLAUSIBLE_M[1])]
        if v.size:
            lo, hi = min(lo, float(v.min())), max(hi, float(v.max()))
    return lo, hi


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dem", nargs="+", required=True,
                    help="rasters, globs or directories, FINEST FIRST (first with data wins)")
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--bbox", nargs=4, type=float, metavar=("WEST", "SOUTH", "EAST", "NORTH"))
    g.add_argument("--aoi", metavar="FILE.kml|FILE.kmz")
    g.add_argument("--projected-bounds", nargs=4, type=float, metavar=("MINX", "MINY", "MAXX", "MAXY"),
                   help="the area in the OUTPUT projection's metres (needs --epsg), used exactly: "
                        "the north-west corner is not snapped to whole quads")
    ap.add_argument("--buffer-m", type=float, default=0.0)
    ap.add_argument("--out", required=True)
    ap.add_argument("--name", required=True, help="base name for the plan and heightmaps")
    ap.add_argument("--metres", type=float, default=1.0, help="metres per landscape quad (default 1)")
    ap.add_argument("--epsg", type=int, default=0, help="output projection (default: UTM zone of the area)")
    ap.add_argument("--datum", choices=["WGS84", "NAD83"], default="WGS84",
                    help="datum for the automatic UTM zone (NAD83 matches USGS in North America)")
    ap.add_argument("--section-quads", type=int, default=255, choices=LEGAL_SECTIONS)
    ap.add_argument("--sections-per-component", type=int, default=2, choices=[1, 2])
    ap.add_argument("--max-vertices", type=int, default=8161,
                    help="largest segment edge in vertices (default 8161, Unreal's recommended maximum)")
    ap.add_argument("--wp-grid", type=int, default=4, help="World Partition grid size, 0 to leave unsplit")
    ap.add_argument("--origin", choices=["area", "projected"], default="area",
                    help="'area' puts the north-west corner at Unreal 0,0 (default); 'projected' uses "
                         "real projected coordinates, which needs large world coordinates enabled")
    ap.add_argument("--no-mask", action="store_true",
                    help="keep the full rectangle instead of blanking terrain outside a KML polygon")
    ap.add_argument("--zmin", type=float, help="override the estimated lowest elevation (m)")
    ap.add_argument("--zmax", type=float, help="override the estimated highest elevation (m)")
    ap.add_argument("--resampling", choices=["bilinear", "cubic", "nearest"], default="bilinear")
    ap.add_argument("--plan-only", action="store_true", help="print the segment layout and stop")
    args = ap.parse_args()

    files = expand(args.dem)
    if not files:
        sys.exit("no DEM rasters found")
    sources = [Source(p, i + 1) for i, p in enumerate(files)]

    # ---- area --------------------------------------------------------------------------------
    if args.projected_bounds:
        if not args.epsg:
            sys.exit("--projected-bounds needs --epsg to say which projection they are in")
        b = transform_bounds(CRS.from_epsg(args.epsg), WGS84, *args.projected_bounds, densify_pts=41)
        aoi = gc.AOI(*b, name=args.name)
    elif args.aoi or args.bbox:
        aoi = gc.aoi_from_args(args)
    else:
        w = min(s.bounds_wgs84[0] for s in sources); so = min(s.bounds_wgs84[1] for s in sources)
        e = max(s.bounds_wgs84[2] for s in sources); n = max(s.bounds_wgs84[3] for s in sources)
        aoi = gc.AOI(w, so, e, n, name=args.name)
    lon, lat = aoi.centre()
    dst_epsg = args.epsg or gc.utm_epsg_for(lon, lat, args.datum)
    dst = CRS.from_epsg(dst_epsg)
    m = float(args.metres)
    if args.projected_bounds:
        minx, miny, maxx, maxy = args.projected_bounds
        X0, Y1 = minx, maxy
    else:
        minx, miny, maxx, maxy = transform_bounds(WGS84, dst, *aoi.bbox, densify_pts=41)
        X0 = math.floor(minx / m) * m
        Y1 = math.ceil(maxy / m) * m
    W = int(math.ceil((maxx - X0) / m))
    H = int(math.ceil((Y1 - miny) / m))

    qc = args.section_quads * args.sections_per_component         # quads per component
    qs = max(qc, ((args.max_vertices - 1) // qc) * qc)             # quads per full segment
    nx, ny = int(math.ceil(W / qs)), int(math.ceil(H / qs))

    ring_dst = None
    if aoi.ring and len(aoi.ring) > 4 and not args.no_mask:
        xs, ys = warp_points(WGS84, dst, [p[0] for p in aoi.ring], [p[1] for p in aoi.ring])
        from shapely.geometry import Polygon
        ring_dst = Polygon(list(zip(xs, ys)))

    segs = []
    for iy in range(ny):
        for ix in range(nx):
            sx, sy = ix * qs, iy * qs
            wq = int(math.ceil(min(qs, W - sx) / qc)) * qc
            hq = int(math.ceil(min(qs, H - sy) / qc)) * qc
            ex0, ey1 = X0 + sx * m, Y1 - sy * m
            if ring_dst is not None:
                from shapely.geometry import box
                if not ring_dst.intersects(box(ex0, ey1 - hq * m, ex0 + wq * m, ey1)):
                    continue
            segs.append((ix, iy, sx, sy, wq, hq))

    print("area       %.5f %.5f %.5f %.5f (WGS84)" % aoi.bbox)
    print("projection EPSG:%d, %.3g m quads, %d x %d quads (%.2f x %.2f km)"
          % (dst_epsg, m, W, H, W * m / 1000, H * m / 1000))
    print("segments   %d (of a %d x %d grid), up to %d x %d vertices each, components of %d quads"
          % (len(segs), nx, ny, qs + 1, qs + 1, qc))
    for i, s in enumerate(sources):
        print("source %d   %-60s %.2f m  %s" % (i + 1, os.path.basename(s.path), s.res_m, s.ds.crs))
    heightmap_mb = sum((w + 1) * (h + 1) * 2 for _, _, _, _, w, h in segs) / 1e6
    print("output     %.0f MB of heightmap" % heightmap_mb)
    if args.plan_only:
        return

    # ---- vertical range ------------------------------------------------------------------------
    # Over the PADDED grid, not just the area: segments round up to whole components, so their
    # east and south edges carry real terrain beyond the area, and it must fit the range too.
    pad_w = max(sx + wq for _, _, sx, _, wq, _ in segs) if segs else W
    pad_h = max(sy + hq for _, _, _, sy, _, hq in segs) if segs else H
    lo, hi = estimate_range(sources, dst, (X0, Y1 - pad_h * m, X0 + pad_w * m, Y1))
    if not math.isfinite(lo):
        sys.exit("no elevation data inside the area - check the rasters cover it")
    margin = max(1.0, 0.02 * (hi - lo))
    zmin = args.zmin if args.zmin is not None else lo - margin
    zmax = args.zmax if args.zmax is not None else hi + margin
    mid = (zmin + zmax) / 2.0
    half_cm = (zmax - zmin) / 2.0 * 100.0
    scale_z = max(1.0, math.ceil(half_cm * 128.0 / 32767.0 * 100.0) / 100.0)
    print("elevation  %.2f .. %.2f m (estimated %.2f .. %.2f), Z scale %.2f, step %.2f cm"
          % (zmin, zmax, lo, hi, scale_z, scale_z / 128.0))

    os.makedirs(args.out, exist_ok=True)
    resampling = getattr(Resampling, args.resampling)
    fine = {s.rank for s in sources if s.res_m <= 1.5}
    totals = {"fine": 0, "coarse": 0, "nodata": 0, "clipped": 0}
    per_source = {s.rank: 0 for s in sources}
    out_segs = []
    # East column and south row of every segment built so far. The next segment COPIES its shared
    # west and north edges from these: GDAL warps each window on its own and bilinear sampling at a
    # window edge is not bit-identical between two windows, and one step of difference is a crack.
    edges = {}

    for n, (ix, iy, sx, sy, wq, hq) in enumerate(segs):
        rx, ry = wq + 1, hq + 1
        name = args.name if len(segs) == 1 else "%s_x%02d_y%02d" % (args.name, ix, iy)
        # One sample per VERTEX: pixel centres sit on the vertex positions.
        tr = Affine(m, 0.0, X0 + sx * m - m / 2.0, 0.0, -m, Y1 - sy * m + m / 2.0)
        z = np.full((ry, rx), np.nan, dtype="float32")
        prov = np.zeros((ry, rx), dtype="uint8")
        seg_box = (X0 + sx * m - m, Y1 - sy * m - hq * m - m, X0 + sx * m + wq * m + m, Y1 - sy * m + m)

        for s in sources:
            b = transform_bounds(s.ds.crs, dst, *s.ds.bounds, densify_pts=21)
            if b[0] > seg_box[2] or b[2] < seg_box[0] or b[1] > seg_box[3] or b[3] < seg_box[1]:
                continue
            tmp = np.full((ry, rx), np.nan, dtype="float32")
            reproject(source=rasterio.band(s.ds, 1), destination=tmp, src_transform=s.ds.transform,
                      src_crs=s.ds.crs, src_nodata=s.ds.nodata, dst_transform=tr, dst_crs=dst,
                      dst_nodata=np.nan, resampling=resampling)
            tmp[(tmp <= PLAUSIBLE_M[0]) | (tmp >= PLAUSIBLE_M[1])] = np.nan
            take = np.isnan(z) & np.isfinite(tmp)
            z[take] = tmp[take]
            prov[take] = s.rank
            per_source[s.rank] += int(take.sum())
            del tmp
            if not np.isnan(z).any():
                break

        if ring_dst is not None:
            outside = geometry_mask([ring_dst.__geo_interface__], out_shape=(ry, rx), transform=tr,
                                    invert=False, all_touched=True)
            z[outside] = np.nan
            prov[outside] = 0

        empty = np.isnan(z)
        cells_nodata = int(empty.sum())
        z[empty] = zmin
        h = np.rint((z.astype("float64") - mid) * 12800.0 / scale_z + 32768.0)
        clipped = int(((h < 0) | (h > 65535)).sum())
        h = np.clip(h, 0, 65535).astype("<u2")
        if (ix - 1, iy) in edges:
            h[:, 0], prov[:, 0] = edges[(ix - 1, iy)][0], edges[(ix - 1, iy)][1]
        if (ix, iy - 1) in edges:
            h[0, :], prov[0, :] = edges[(ix, iy - 1)][2], edges[(ix, iy - 1)][3]
        edges[(ix, iy)] = (h[:, -1].copy(), prov[:, -1].copy(), h[-1, :].copy(), prov[-1, :].copy())

        r16 = name + ".r16"
        h.tofile(os.path.join(args.out, r16))
        prov.tofile(os.path.join(args.out, name + ".provenance"))

        c_fine = int(np.isin(prov, list(fine)).sum()) if fine else 0
        c_coarse = int((prov > 0).sum()) - c_fine
        totals["fine"] += c_fine; totals["coarse"] += c_coarse
        totals["nodata"] += cells_nodata; totals["clipped"] += clipped

        if args.origin == "area":
            loc = [sx * m * 100.0, sy * m * 100.0, mid * 100.0]
        else:
            loc = [(X0 + sx * m) * 100.0, -(Y1 - sy * m) * 100.0, mid * 100.0]

        seg = {
            "name": name, "heightmap_r16": r16, "provenance": name + ".provenance",
            "resolution": [rx, ry], "section_size_quads": args.section_quads,
            "sections_per_component": args.sections_per_component,
            "components": [wq // qc, hq // qc], "actor_scale": [m * 100.0, m * 100.0, scale_z],
            "actor_location_cm": loc, "projected_origin": [X0 + sx * m, Y1 - sy * m],
            "elev_min_m": zmin, "elev_max_m": zmax, "elev_mid_m": mid,
            "height_decode": "metres = (H - 32768) * %.6g / 12800 + %.6f" % (scale_z, mid),
            "cells_1m": c_fine, "cells_19_resampled": c_coarse, "cells_nodata": cells_nodata,
            "cells_clipped": clipped,
        }
        # Same law Unreal's importer enforces, checked here so a bad plan never reaches the editor.
        assert rx == seg["components"][0] * qc + 1 and ry == seg["components"][1] * qc + 1
        assert os.path.getsize(os.path.join(args.out, r16)) == rx * ry * 2
        out_segs.append(seg)
        print("  [%d/%d] %s  %d x %d  data %.1f%%%s"
              % (n + 1, len(segs), r16, rx, ry, 100.0 * (1 - cells_nodata / float(rx * ry)),
                 ("  CLIPPED %d" % clipped) if clipped else ""))

    plan = {
        "name": args.name,
        "tool": "MAirCorridor Tools/build_landscape.py",
        "projection": "EPSG:%d" % dst_epsg,
        "quad_metres": m,
        "world_partition_grid_size": args.wp_grid,
        "origin_mode": args.origin,
        "utm_origin": [X0, Y1],
        "extent_quads": [W, H],
        "world_metres": [W * m, H * m],
        "aoi_bbox_wgs84": list(aoi.bbox),
        "aoi": os.path.basename(args.aoi) if args.aoi else None,
        "heightmap_format": "uint16 little-endian, row-major, row 0 = NORTH, no header",
        "provenance_format": "uint8 per vertex, same size as its heightmap: 0 = no data or outside "
                             "the area, otherwise the 'class' of the source that supplied it",
        "sources": [s.describe() for s in sources],
        "cells_per_source": {str(k): v for k, v in per_source.items()},
        "elev_min_m": zmin, "elev_max_m": zmax, "elev_mid_m": mid,
        "cells_1m": totals["fine"], "cells_19_resampled": totals["coarse"],
        "cells_nodata": totals["nodata"], "cells_clipped": totals["clipped"],
        "CELL_COUNTS": "cells_1m counts vertices from sources of 1.5 m or finer; cells_19_resampled "
                       "counts every coarser source. The names are what the Unreal importer reads.",
        "source": "; ".join("%d: %s" % (s.rank, os.path.basename(s.path)) for s in sources),
    }
    if len(out_segs) == 1:
        plan.update(out_segs[0])
        plan["name"] = args.name
    else:
        plan["segments"] = out_segs
    path = os.path.join(args.out, args.name + ".json")
    gc.write_json(path, plan)

    total = totals["fine"] + totals["coarse"] + totals["nodata"]
    print("\nplan       %s" % path)
    print("coverage   %.1f%% fine, %.1f%% coarse, %.1f%% no data"
          % tuple(100.0 * totals[k] / max(1, total) for k in ("fine", "coarse", "nodata")))
    if totals["clipped"]:
        print("WARNING    %d vertices fell outside the vertical range and were clipped; rerun with "
              "--zmin/--zmax covering them" % totals["clipped"])
    print("next       Unreal: Tools > M-Air Corridor > Build Unreal Landscape from Plan... and pick %s"
          % os.path.basename(path))


if __name__ == "__main__":
    main()
