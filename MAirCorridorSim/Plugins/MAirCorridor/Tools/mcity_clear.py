"""mcity_clear.py - which of the corridor's own buildings and trees are under M-City's scan, its twin, or both.

    py -3.10 mcity_clear.py

The corridor level was built from OpenStreetMap and a foliage placer before M-City was put in it, so
where the photogrammetric scan or Mcity's digital twin now stands there are also the corridor's own
buildings and trees, poking through. This decides which, from two inputs:

  Saved/MAirCorridor/mcity_corridor_items.json    the corridor's buildings and trees around M-City
                                                  (Tools/unreal/mcity_clear_level.py, MAIR_STEP=survey)
  Saved/MAirCorridor/mcity_twin_footprint.json    where the twin has geometry, in its own frame
                                                  (Tools/unreal/mcity_twin_footprint.py)

and the scan itself (Content/Scans/mcity_scan_mesh). Each becomes a 1 m mask on the level: the
scan's coarsest vertices marked, gaps closed (GAP_M) and holes filled; the twin's ground and roads
drawn triangle by triangle and its smaller pieces as their boxes; all placed as the level places them
(the scan's affine from MAirScanMeshComponent.h, the twin's yaw and offset from
MAirMcityViewSubsystem.cpp).

A building is under a mask when at least UNDER_SHARE of its ground plan is; a tree when its trunk is
within CANOPY_M of it. Writes Saved/MAirCorridor/mcity_clear_plan.json for mcity_clear_level.py
(MAIR_STEP=apply) and mcity_clear_preview.png beside it to look at first:

  both        deleted (whichever M-City is shown covers it)
  scan        hidden while the scan is shown
  twin        hidden while the twin is shown

Buildings only partly under (between EDGE_SHARE and UNDER_SHARE) are left alone and listed.
"""
import io
import json
import os
import re
import struct
import sys

import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage

HERE = os.path.dirname(os.path.abspath(__file__))
PLUGIN = os.path.dirname(HERE)
PROJECT = os.path.dirname(os.path.dirname(PLUGIN))
SAVED = os.path.join(PROJECT, "Saved", "MAirCorridor")
ITEMS = os.path.join(SAVED, "mcity_corridor_items.json")
TWIN = os.path.join(SAVED, "mcity_twin_footprint.json")
PLAN = os.path.join(SAVED, "mcity_clear_plan.json")
PREVIEW = os.path.join(SAVED, "mcity_clear_preview.png")
SCAN = os.path.join(PLUGIN, "Content", "Scans", "mcity_scan_mesh")
SCAN_HEADER = os.path.join(PLUGIN, "Source", "MAirCorridorScan", "Public", "MAirScanMeshComponent.h")
VIEW_SOURCE = os.path.join(PLUGIN, "Source", "MAirCorridorScan", "Private", "MAirMcityViewSubsystem.cpp")

CELL_CM = 100.0          # the masks' cell: 1 m
GAP_M = 6                # gaps closed between marked cells: the scan's coarsest vertices are 4 m apart
UNDER_SHARE = 0.3        # a building with this much of its ground plan under a mask is under it
EDGE_SHARE = 0.05        # less than this is clear of it; between the two it is listed, not touched
CANOPY_M = 3             # a trunk this close outside a mask still puts its crown into what is there


def floats(pattern, text):
    m = re.search(pattern, text)
    if not m:
        raise SystemExit("could not find %s" % pattern)
    return [float(v) for v in m.groups()]


def scan_points():
    """The scan's coarsest vertices, X and Y in level cm, as MAirScanMeshComponent places them."""
    header = io.open(SCAN_HEADER, encoding="utf-8").read()
    num = r"(-?[\d.]+)"
    ax = floats(r"AlignRowX = FVector\(%s, %s, %s\)" % (num, num, num), header)
    ay = floats(r"AlignRowY = FVector\(%s, %s, %s\)" % (num, num, num), header)
    with io.open(os.path.join(SCAN, "index.json"), encoding="utf-8") as f:
        index = json.load(f)
    out = []
    for tile in index["tiles"]:
        path = tile["levels"][-1]["file"]
        path = path if os.path.isabs(path) else os.path.join(SCAN, path)
        blob = open(path, "rb").read()
        _magic, version, count, _indices = struct.unpack_from("<4sIII", blob, 0)
        pos = np.frombuffer(blob, dtype="<f4", count=3 * count, offset=48 if version >= 2 else 40).reshape(-1, 3)
        x, y = pos[:, 0] * 100.0, pos[:, 2] * 100.0          # metres, y up, to Unreal cm: X = x, Y = z
        out.append(np.c_[x * ax[0] + y * ax[1] + ax[2], x * ay[0] + y * ay[1] + ay[2]])
    return np.vstack(out)


def twin_placement():
    src = io.open(VIEW_SOURCE, encoding="utf-8").read()
    offset = floats(r"TwinOffsetCm\((-?[\d.]+), (-?[\d.]+), (-?[\d.]+)\)", src)
    yaw = floats(r"TwinYawDeg = (-?[\d.]+);", src)[0]
    a = np.radians(yaw)
    rot = np.array([[np.cos(a), -np.sin(a)], [np.sin(a), np.cos(a)]])
    return lambda xy: np.asarray(xy, float) @ rot.T + np.array(offset[:2])


class Grid:
    def __init__(self, region):
        self.x0, self.y0 = region[0], region[1]
        self.nx = int(np.ceil((region[2] - region[0]) / CELL_CM))
        self.ny = int(np.ceil((region[3] - region[1]) / CELL_CM))

    def cells(self, xy):
        xy = np.asarray(xy, float).reshape(-1, 2)
        ix = ((xy[:, 0] - self.x0) // CELL_CM).astype(int)
        iy = ((xy[:, 1] - self.y0) // CELL_CM).astype(int)
        keep = (ix >= 0) & (ix < self.nx) & (iy >= 0) & (iy < self.ny)
        return ix, iy, keep

    def mark(self, xy):
        g = np.zeros((self.nx, self.ny), bool)
        ix, iy, keep = self.cells(xy)
        g[ix[keep], iy[keep]] = True
        return g

    def polygon(self, corners, image=None):
        """A filled polygon as a mask image (PIL: x across is ix, y down is iy)."""
        img = image or Image.new("1", (self.nx, self.ny), 0)
        pts = [((x - self.x0) / CELL_CM, (y - self.y0) / CELL_CM) for x, y in corners]
        ImageDraw.Draw(img).polygon(pts, fill=1)
        return img


def solid(g, gap=GAP_M):
    """Close gaps up to `gap` cells and fill what is enclosed."""
    disk = np.hypot(*np.mgrid[-gap:gap + 1, -gap:gap + 1]) <= gap
    g = ndimage.binary_closing(np.pad(g, gap), structure=disk)[gap:-gap, gap:-gap]
    return ndimage.binary_fill_holes(g)


def share_under(grid, mask, corners):
    img = grid.polygon(corners)
    inside = np.asarray(img, bool).T                       # back to [ix, iy]
    n = inside.sum()
    if n == 0:                                             # smaller than a cell: its middle decides
        cx, cy = np.mean(corners, axis=0)
        ix, iy, keep = grid.cells([(cx, cy)])
        return float(keep[0] and mask[ix[0], iy[0]])
    return float((inside & mask).sum()) / n


def main():
    for path in (ITEMS, TWIN):
        if not os.path.isfile(path):
            raise SystemExit("no %s: run %s first" % (path, "Tools/unreal/mcity_clear_level.py (survey)" if path == ITEMS
                                                    else "Tools/unreal/mcity_twin_footprint.py"))
    items = json.load(io.open(ITEMS, encoding="utf-8"))
    twin = json.load(io.open(TWIN, encoding="utf-8"))
    grid = Grid(items["region"])

    scan = solid(grid.mark(scan_points()))
    place = twin_placement()
    drawn = Image.new("1", (grid.nx, grid.ny), 0)
    tris = place(np.asarray(twin["triangles"], float).reshape(-1, 2)).reshape(-1, 3, 2)
    for tri in tris:
        grid.polygon(tri, drawn)
    for x0, y0, x1, y1 in twin["boxes"]:
        grid.polygon(place([(x0, y0), (x1, y0), (x1, y1), (x0, y1)]), drawn)
    twin_mask = solid(np.asarray(drawn, bool).T, gap=1)
    print("scan  %.3f km2 under it" % (scan.sum() / 1e6))
    print("twin  %.3f km2 under it" % (twin_mask.sum() / 1e6))
    print("both  %.3f km2" % ((scan & twin_mask).sum() / 1e6))

    grow = np.hypot(*np.mgrid[-CANOPY_M:CANOPY_M + 1, -CANOPY_M:CANOPY_M + 1]) <= CANOPY_M
    scan_c = ndimage.binary_dilation(scan, structure=grow)
    twin_c = ndimage.binary_dilation(twin_mask, structure=grow)

    def action(s, t):
        return "both" if s and t else "scan" if s else "twin" if t else None

    plan_b, edge = [], []
    for b in items["buildings"]:
        s, t = share_under(grid, scan, b["corners"]), share_under(grid, twin_mask, b["corners"])
        a = action(s >= UNDER_SHARE, t >= UNDER_SHARE)
        if a:
            plan_b.append(dict(b, action=a, scan=round(s, 2), twin=round(t, 2)))
        elif max(s, t) >= EDGE_SHARE:
            edge.append(dict(b, scan=round(s, 2), twin=round(t, 2)))
    plan_t = []
    tx, ty, keep = grid.cells([(t["x"], t["y"]) for t in items["trees"]])
    for k, t in enumerate(items["trees"]):
        if not keep[k]:
            continue
        a = action(scan_c[tx[k], ty[k]], twin_c[tx[k], ty[k]])
        if a:
            plan_t.append(dict(t, action=a))

    def count(rows):
        return {a: sum(1 for r in rows if r["action"] == a) for a in ("both", "scan", "twin")}

    summary = {"buildings": count(plan_b), "trees": count(plan_t), "buildings_on_the_edge": len(edge),
               "of": {"buildings": len(items["buildings"]), "trees": len(items["trees"])}}
    with io.open(PLAN, "w", encoding="utf-8") as f:
        json.dump({"summary": summary, "buildings": plan_b, "trees": plan_t, "edge": edge}, f, indent=1)
    print(json.dumps(summary))
    for b in edge:
        print("edge  %-24s scan %.2f twin %.2f  %s" % (b["label"], b["scan"], b["twin"], b["folder"]))

    # The preview, 2 m a pixel, north up (+X up, +Y right): scan blue, twin red, both magenta;
    # buildings outlined by what happens to them, trees dotted.
    rgb = np.full((grid.nx, grid.ny, 3), 235, np.uint8)
    rgb[scan] = (150, 180, 240)
    rgb[twin_mask] = (240, 160, 160)
    rgb[scan & twin_mask] = (210, 150, 230)
    img = Image.fromarray(rgb[::-1, :, :])                    # rows: +X up
    draw = ImageDraw.Draw(img)
    colour = {"both": (120, 0, 120), "scan": (0, 60, 200), "twin": (200, 0, 0), None: (90, 90, 90)}
    acted = {b["path"]: b["action"] for b in plan_b}

    def px(x, y):
        return ((y - grid.y0) / CELL_CM, grid.nx - 1 - (x - grid.x0) / CELL_CM)
    for b in items["buildings"]:
        draw.polygon([px(x, y) for x, y in b["corners"]], outline=colour[acted.get(b["path"])])
    tree_action = {(t["actor"], t["component"], t["index"]): t["action"] for t in plan_t}
    for t in items["trees"]:
        c = colour[tree_action.get((t["actor"], t["component"], t["index"]))]
        x, y = px(t["x"], t["y"])
        draw.point([(x, y)], fill=(0, 140, 0) if c == colour[None] else c)
    img = img.resize((grid.ny // 2, grid.nx // 2), Image.LANCZOS)
    img.save(PREVIEW)
    print("wrote %s and %s" % (PLAN, PREVIEW))
    return 0


if __name__ == "__main__":
    sys.exit(main())
