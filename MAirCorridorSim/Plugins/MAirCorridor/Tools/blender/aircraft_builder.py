"""aircraft_builder.py - a generic aircraft builder: any aircraft from a list of parts, in Blender.

    blender --factory-startup -b -P aircraft_builder.py -- [--only NAME ...] [--out DIR] [--no-render]
            [--manifest FILE]

Reads Tools/aircraft/fleet.json (or --manifest) and writes, for each aircraft, into <out>/<name>/
(default Tools/work/aircraft): <name>.glb, <name>.fbx, <name>.blend, model.json (its measured size
against the real one) and four review renders, views/*.png. --factory-startup keeps the user's own
Blender add-ons out of a background run.

WHY BUILT, NOT GENERATED. Single-picture 3D reconstruction folds and tears thin wings, and an aircraft
is mostly thin wing. A model built from dimensions is the right size, faces the right way and has
clean surfaces, which is what a simulator measures: a lidar return off a wing is only as good as the
wing.

ANY AIRCRAFT IS A LIST OF PARTS. Nothing here knows what a Cessna, an airliner or a helicopter is. An
aircraft is "parts": a fuselage or several, lifting surfaces of any number and arrangement, engines,
propellers and rotors facing any way, tubes, wheels, canopies, lathed shapes, boxes, and radial
patterns of any of those. The same few parts make a high-wing single, a T-tailed twin, a swept
airliner with podded engines and winglets, a canard pusher, a twin-boom, a V-tail, a flying wing, a
biplane, a helicopter, a multirotor, a balloon. See PARTS below for every field.

THE SPEC FRAME. Metres. x is measured AFT from the aircraft's datum (the nose), y is to the LEFT and
z is UP. A part with "mirror": true is built again reflected to the right (y -> -y), so a pair is
described once. The built model is in Blender's frame: +X forward (the nose), +Y left, +Z up, with
the origin at the middle of its bounding box. Each aircraft is one mesh with a material per kind of
surface (paint, accent, glass, dark, metal, tyre, fabric, ...), so a segmentation pass or a livery
change can tell them apart.

SPINNING PARTS. A propeller marked "spin": true is part of the whole model as usual, and the build
also writes <name>_body (everything else) and <name>_rotor (one of them alone, centred on its hub,
turning about +Z), and lists in model.json where every one of them goes. That is what a
simulator that turns each rotor as its own mesh needs, Project AirSim among them
(Tools/drone_configs.py). "origin" in the build puts the model's origin at a spec-frame point,
such as the centre of mass, instead of the middle of its bounding box.

ATTACHING ONE PART TO ANOTHER. A position can be a point [x, y, z], or a place on a named part, so
that what is attached follows when that part changes:
    {"on": "wing", "span": 0.34, "chord": -0.3, "offset": [0, 0, -0.8]}
        on a surface: at 34 % of its half span (0 root, 1 tip), 30 % of the local chord AHEAD of the
        leading edge, then offset; z follows the dihedral.
    {"on": "body", "station": 2.3, "angle": 180, "offset": [...]}
        on a fuselage: at 2.3 m aft of its own nose, on its skin at the given angle around it
        (0 top, 90 left, 180 bottom, 270 right).

PARTS ("type" and its fields; anything left out takes the default shown):
    fuselage   name, x, y, z, length, width, height, nose 0.18, tail 0.35 (fractions of length),
               nose_tip 0.08, tail_tip 0.12 (fraction of the section left at the ends), tail_up
               0.25, nose_drop 0 (fractions of height the centreline rises at the tail / drops at
               the nose), squareness 2.2 (2 round, higher boxier), material paint,
               glass [[x0, x1, z_from, side_only], ...] (x from the fuselage's own nose, z as a
               fraction of height from the centre), stripe [z_lo, z_hi, x0, x1] (fractions of each
               section's own height), window_band [z_lo, z_hi, x0, x1] (an airliner's cabin windows)
    surface    name, x, y, z (the root leading edge), span (tip to tip if mirrored, else the length
               from root to tip), root_chord, tip_chord, sweep 0 (leading edge, degrees), dihedral 0
               (negative is anhedral; 35 makes a V-tail), thickness 0.12, camber 0, root_offset 0
               (where the exposed span starts), vertical false (a fin: span goes up from z),
               mirror (true for a horizontal surface, false for a fin), material paint, sections 8
    nacelle    kind turbofan | turboprop | piston, length, diameter, at (a position: its front),
               pylon false, propeller {diameter, blades} (on the front), material, mirror
    propeller  at, facing forward | aft | up | down | left, diameter, blades 2, spinner true,
               chord, material dark, mirror, spin false (true: a propeller the simulator turns;
               see SPINNING PARTS)
    tube       from, to, radius, material metal, sides 10, mirror
    gear       at (where the leg starts), length, wheel 0.5 (diameter), wheels 1, splay 0,
               strut 0.05, tyre_width, mirror
    wheel      at (its centre), diameter, width, mirror
    canopy     at (its front, on the centreline of the body), length, width, height
    lathe      at, axis x (along the body, profile runs aft) | z (upright, profile runs up),
               profile [[distance, radius], ...], material, gores 0 and gore_material (alternating
               panels, as on a balloon), sides 24, open false, mirror
    box        at (its centre), size [length, width, height], yaw 0, material, mirror
    radial     at (the centre), count, phase 0 (degrees), axis z, parts [...] (built count times,
               turned about the axis; their positions are relative to the centre)
"""
import io
import json
import math
import os
import sys
import traceback

import bmesh
import bpy
from mathutils import Matrix, Vector

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.dirname(HERE)
MANIFEST = os.path.join(TOOLS, "aircraft", "fleet.json")
DEFAULT_OUT = os.path.join(TOOLS, "work", "aircraft")

COLOURS = {
    "white": (0.85, 0.86, 0.87), "blue": (0.06, 0.20, 0.55), "red": (0.60, 0.05, 0.05),
    "grey": (0.45, 0.47, 0.50), "light_grey": (0.65, 0.67, 0.70), "dark_grey": (0.12, 0.12, 0.13),
    "black": (0.02, 0.02, 0.02), "yellow": (0.85, 0.65, 0.05), "orange": (0.85, 0.35, 0.03),
    "amber": (0.95, 0.50, 0.02), "silver": (0.62, 0.63, 0.65), "carbon": (0.05, 0.05, 0.06),
    "wicker": (0.42, 0.28, 0.13), "green": (0.10, 0.35, 0.12), "navy": (0.03, 0.07, 0.22),
}
FACING = {"forward": (1, 0, 0), "aft": (-1, 0, 0), "up": (0, 0, 1), "down": (0, 0, -1), "left": (0, 1, 0)}


# ---------------------------------------------------------------------------------------------
# Materials
# ---------------------------------------------------------------------------------------------

def colour(name):
    if isinstance(name, (list, tuple)):
        return tuple(name)
    return COLOURS.get(name, COLOURS["white"])


def material(name, rgb, metallic=0.0, roughness=0.5):
    mat = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = (*rgb, 1.0)
    bsdf.inputs["Metallic"].default_value = metallic
    bsdf.inputs["Roughness"].default_value = roughness
    mat.diffuse_color = (*rgb, 1.0)            # what the workbench review render shows
    return mat


def palette(spec):
    """The aircraft's materials. 'colours' in the spec sets paint, accent and any others by name."""
    c = dict({"paint": "white", "accent": "blue"}, **spec.get("colours", {}))
    P = {
        "glass": material("glass", (0.03, 0.05, 0.08), 0.0, 0.05),
        "dark": material("dark", COLOURS["dark_grey"], 0.2, 0.6),
        "metal": material("metal", COLOURS["silver"], 0.9, 0.3),
        "tyre": material("tyre", (0.015, 0.015, 0.015), 0.0, 0.9),
        "wicker": material("wicker", COLOURS["wicker"], 0.0, 0.9),
    }
    for name, value in c.items():
        rough = 0.8 if name.startswith("fabric") else 0.35
        P[name] = material(name, colour(value), 0.1 if rough < 0.5 else 0.0, rough)
    P.setdefault("fabric", material("fabric", colour(c["paint"]), 0.0, 0.8))
    P.setdefault("fabric_accent", material("fabric_accent", colour(c["accent"]), 0.0, 0.8))
    return P


# ---------------------------------------------------------------------------------------------
# Geometry: one bmesh, a transform stack, a material slot per material
# ---------------------------------------------------------------------------------------------

def to_blender(p):
    """Spec frame (x aft, y left, z up) to Blender's (X forward, Y left, Z up)."""
    return Vector((-p[0], p[1], p[2]))


class Builder:
    def __init__(self, P):
        self.bm = bmesh.new()
        self.P = P
        self.mat_index, self.mats = {}, []
        self.stack = [Matrix.Identity(4)]
        self.skip_spin = False      # leave parts marked "spin" out, and note where they go
        self.rotors = []

    @property
    def xf(self):
        return self.stack[-1]

    def push(self, m):
        self.stack.append(self.xf @ m)

    def pop(self):
        self.stack.pop()

    def mat(self, name):
        m = self.P.get(name) or self.P["paint"]
        if m.name not in self.mat_index:
            self.mat_index[m.name] = len(self.mats)
            self.mats.append(m)
        return self.mat_index[m.name]

    def verts(self, pts):
        xf = self.xf
        return [self.bm.verts.new(xf @ Vector(p)) for p in pts]

    def face(self, vs, mat_name):
        try:
            f = self.bm.faces.new(vs)
        except ValueError:
            return None
        f.material_index = self.mat(mat_name)
        return f

    def finish(self, name):
        bmesh.ops.remove_doubles(self.bm, verts=self.bm.verts, dist=1e-5)
        bmesh.ops.recalc_face_normals(self.bm, faces=self.bm.faces)
        mesh = bpy.data.meshes.new(name)
        self.bm.to_mesh(mesh)
        self.bm.free()
        for m in self.mats:
            mesh.materials.append(m)
        for p in mesh.polygons:
            p.use_smooth = True
        obj = bpy.data.objects.new(name, mesh)
        bpy.context.scene.collection.objects.link(obj)
        return obj


def loft(b, rings, mat_for, cap_start=True, cap_end=True, spans=False):
    """Join rings of points (Blender frame, before the transform) with quads; cap the ends with fans."""
    loops = [b.verts(r) for r in rings]
    n = len(rings[0])
    for k in range(len(loops) - 1):
        for i in range(n):
            j = (i + 1) % n
            corners = (Vector(rings[k][i]), Vector(rings[k][j]), Vector(rings[k + 1][i]), Vector(rings[k + 1][j]))
            centre = sum(corners, Vector()) / 4
            # spans: the facet's height range too, so a band thinner than a facet is still found
            if spans:
                m = mat_for(k, i, centre, (min(c.z for c in corners), max(c.z for c in corners)))
            else:
                m = mat_for(k, i, centre)
            b.face([loops[k][i], loops[k][j], loops[k + 1][j], loops[k + 1][i]], m)
    for cap, ring, loop in ((cap_start, rings[0], loops[0]), (cap_end, rings[-1], loops[-1])):
        if cap:
            centre = sum((Vector(p) for p in ring), Vector()) / len(ring)
            c = b.verts([centre])[0]
            for i in range(n):
                b.face([loop[i], loop[(i + 1) % n], c], mat_for(0, i, centre, (centre.z, centre.z)) if spans
                       else mat_for(0, i, centre))


def ring(cx, cy, cz, hw, hh, n=32, exp=2.0):
    """A superellipse ring at station cx (Blender X), lying in Y, Z."""
    pts = []
    for i in range(n):
        a = 2 * math.pi * i / n
        c, s = math.cos(a), math.sin(a)
        pts.append((cx, cy + hw * math.copysign(abs(c) ** (2.0 / exp), c),
                    cz + hh * math.copysign(abs(s) ** (2.0 / exp), s)))
    return pts


def smoothstep(t):
    t = max(0.0, min(1.0, t))
    return t * t * (3 - 2 * t)


def naca(t, m=0.0, p=0.4, n=18):
    """A NACA 4-digit airfoil as one closed loop, chord 0..1 from the leading edge: (x, z) pairs."""
    up, lo = [], []
    for i in range(n + 1):
        x = 0.5 * (1 - math.cos(math.pi * i / n))
        yt = 5 * t * (0.2969 * math.sqrt(x) - 0.1260 * x - 0.3516 * x ** 2 + 0.2843 * x ** 3 - 0.1036 * x ** 4)
        yc = 0.0
        if m > 0:
            yc = m / p ** 2 * (2 * p * x - x * x) if x < p else m / (1 - p) ** 2 * ((1 - 2 * p) + 2 * p * x - x * x)
        up.append((x, yc + yt))
        lo.append((x, yc - yt))
    return up[::-1] + lo[1:-1]


# ---------------------------------------------------------------------------------------------
# Where things are: the shape of fuselages and surfaces, for attaching parts to them
# ---------------------------------------------------------------------------------------------

def fuselage_section(f, station):
    """Centre z, half width and half height of a fuselage at a station aft of its own nose."""
    L, W, H = f["length"], f["width"], f["height"]
    nose, tail = f.get("nose", 0.18) * L, f.get("tail", 0.35) * L
    nose_tip, tail_tip = f.get("nose_tip", 0.08), f.get("tail_tip", 0.12)
    z0 = f.get("z", 0.0)
    if station < nose:
        t = station / nose
        k = nose_tip + (1 - nose_tip) * math.sqrt(max(0.0, 1 - (1 - t) ** 2))
        cz = z0 - f.get("nose_drop", 0.0) * H * (1 - t) ** 2
    elif station > L - tail:
        t = (station - (L - tail)) / tail
        k = 1 - (1 - tail_tip) * smoothstep(t) ** 0.9
        cz = z0 + f.get("tail_up", 0.25) * H * smoothstep(t)
    else:
        k, cz = 1.0, z0
    return cz, W / 2 * k, H / 2 * k


def surface_frame(s, frac, chord_frac=0.0, side=1):
    """A point on a surface at a fraction of its span from the root, chord_frac of the chord aft of
    the leading edge (negative is ahead of it): spec frame."""
    vertical = s.get("vertical", False)
    mirrored = s.get("mirror", not vertical)
    half = s["span"] / 2 if (mirrored and not vertical) else s["span"]
    y0 = s.get("root_offset", 0.0)
    d = y0 + (half - y0) * frac
    chord = s["root_chord"] + (s.get("tip_chord", s["root_chord"]) - s["root_chord"]) * frac
    le = s.get("x", 0.0) + (d - y0) * math.tan(math.radians(s.get("sweep", 0.0)))
    x = le + chord_frac * chord
    if vertical:
        return (x, s.get("y", 0.0), s.get("z", 0.0) + d), chord
    return (x, s.get("y", 0.0) + side * d, s.get("z", 0.0) + (d - y0) * math.tan(math.radians(s.get("dihedral", 0.0)))), chord


class Resolver:
    """Turns a position (a point, or a place on a named part) into a spec-frame point."""

    def __init__(self, parts):
        self.named = {}
        self._collect(parts)

    def _collect(self, parts):
        for p in parts:
            if p.get("name"):
                self.named[p["name"]] = p
            if p.get("type") == "radial":
                self._collect(p.get("parts", []))

    def point(self, pos):
        if pos is None:
            return (0.0, 0.0, 0.0)
        if isinstance(pos, (list, tuple)):
            return tuple(float(v) for v in pos)
        ref = self.named.get(pos["on"])
        if ref is None:
            raise ValueError("no part called %r to attach to" % pos["on"])
        off = pos.get("offset", (0.0, 0.0, 0.0))
        if ref["type"] == "surface":
            (x, y, z), _ = surface_frame(ref, pos.get("span", 0.0), pos.get("chord", 0.0))
        elif ref["type"] == "fuselage":
            st = pos.get("station", 0.0)
            cz, hw, hh = fuselage_section(ref, st)
            a = math.radians(pos.get("angle", 0.0))
            x, y, z = ref.get("x", 0.0) + st, ref.get("y", 0.0) + hw * math.sin(a), cz + hh * math.cos(a)
        else:
            x, y, z = self.point(ref.get("at", (ref.get("x", 0.0), ref.get("y", 0.0), ref.get("z", 0.0))))
        return (x + off[0], y + off[1], z + off[2])


# ---------------------------------------------------------------------------------------------
# PARTS
# ---------------------------------------------------------------------------------------------

def part_fuselage(b, f, R):
    L, W, H = f["length"], f["width"], f["height"]
    nose, tail = f.get("nose", 0.18) * L, f.get("tail", 0.35) * L
    x0, y0, z0 = f.get("x", 0.0), f.get("y", 0.0), f.get("z", 0.0)
    exp = f.get("squareness", 2.2)
    stations = [nose * (1 - math.cos(math.pi / 2 * i / 24)) for i in range(25)]
    stations += [nose + (L - nose - tail) * i / 12 for i in range(1, 12)]
    stations += [L - tail + tail * i / 24 for i in range(25)]
    rings, sec = [], []
    for st in stations:
        cz, hw, hh = fuselage_section(f, st)
        rings.append(ring(-(x0 + st), y0, cz, hw, hh, f.get("sides", 40), exp))
        sec.append((cz, hh))
    glass, stripe, band = f.get("glass", []), f.get("stripe"), f.get("window_band")
    base = f.get("material", "paint")

    def mat_for(k, i, c, zspan):
        st = -c.x - x0
        rz = (c.z - z0) / H
        rlo, rhi = (zspan[0] - z0) / H, (zspan[1] - z0) / H
        side = abs(c.y - y0)
        for g in glass:
            if g[0] <= st <= g[1] and rz >= g[2] and (not (len(g) > 3 and g[3]) or side > W * 0.3):
                return "glass"
        if band and band[2] <= st <= band[3] and rlo <= band[1] and rhi >= band[0] and side > W * 0.35:
            return "glass"
        if stripe:
            kk = min(k, len(sec) - 2)
            lz = (c.z - (sec[kk][0] + sec[kk + 1][0]) / 2) / max(1e-6, sec[kk][1] + sec[kk + 1][1])
            if stripe[0] <= lz <= stripe[1] and (stripe[2] if len(stripe) > 2 else nose * 0.5) <= st \
                    <= (stripe[3] if len(stripe) > 3 else L):
                return "accent"
        return base
    loft(b, rings, mat_for, spans=True)


def part_surface(b, s, R):
    vertical = s.get("vertical", False)
    foil = naca(s.get("thickness", 0.12), s.get("camber", 0.0))
    steps = s.get("sections", 8)
    mat = s.get("material", "paint")
    rings = []
    for k in range(steps + 1):
        (x, y, z), chord = surface_frame(s, k / steps, 0.0, 1)
        r = []
        for cx, cz in foil:
            px = -(x + cx * chord)
            if vertical:
                r.append((px, y + cz * chord, z))
            else:
                r.append((px, y, z + cz * chord))
        rings.append(r)
    loft(b, rings, lambda k, i, c: mat)


def part_nacelle(b, n, R):
    x, y, z = R.point(n.get("at"))
    L, Rr = n["length"], n["diameter"] / 2
    kind = n.get("kind", "turbofan")
    if kind == "turbofan":
        prof = [(0.0, Rr * 0.92), (0.05 * L, Rr), (0.45 * L, Rr * 0.98), (0.85 * L, Rr * 0.75), (L, Rr * 0.45)]
        mat = n.get("material", "metal")
    else:
        prof = [(0.0, Rr * 0.45), (0.12 * L, Rr * 0.88), (0.35 * L, Rr), (0.8 * L, Rr * 0.8), (L, Rr * 0.3)]
        mat = n.get("material", "paint")
    lathe(b, (x, y, z), "x", prof, mat)
    if kind == "turbofan":
        lathe(b, (x + 0.02 * L, y, z), "x", [(0.0, Rr * 0.86), (0.01, Rr * 0.2)], "dark")
    if n.get("pylon"):
        box(b, (x + L * 0.6, y, z + Rr * 0.95), (L * 0.6, Rr * 0.22, Rr * 0.9), n.get("pylon_material", "paint"))
    if n.get("propeller"):
        pr = n["propeller"]
        propeller(b, (x - 0.03, y, z), FACING["forward"], pr["diameter"], pr.get("blades", 4),
                  spinner=pr.get("spinner", True), chord=pr.get("chord"))


def lathe(b, at, axis, profile, mat, sides=24, gores=0, gore_mat=None, open_ends=False):
    x, y, z = at
    rings = []
    for d, r in profile:
        r = max(r, 1e-3)
        if axis == "x":
            rings.append(ring(-(x + d), y, z, r, r, sides, 2.0))
        else:
            rings.append([(-x + r * math.cos(2 * math.pi * i / sides), y + r * math.sin(2 * math.pi * i / sides), z + d)
                          for i in range(sides)])
    if gores:
        per = max(1, sides // gores)
        loft(b, rings, lambda k, i, c: mat if (i // per) % 2 == 0 else gore_mat, cap_start=not open_ends,
             cap_end=not open_ends)
    else:
        loft(b, rings, lambda k, i, c: mat, cap_start=not open_ends, cap_end=not open_ends)


def box(b, centre, size, mat, yaw=0.0):
    cx, cy, cz = to_blender(centre)
    sx, sy, sz = (s / 2 for s in size)
    c, s = math.cos(math.radians(yaw)), math.sin(math.radians(yaw))
    pts = [(cx + dx * c - dy * s, cy + dx * s + dy * c, cz + dz)
           for dz in (-sz, sz) for dx, dy in ((-sx, -sy), (sx, -sy), (sx, sy), (-sx, sy))]
    v = b.verts(pts)
    for q in ((0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)):
        b.face([v[i] for i in q], mat)


def tube(b, p0, p1, r, mat, sides=10):
    """A cylinder between two spec-frame points."""
    p0, p1 = to_blender(p0), to_blender(p1)
    axis = p1 - p0
    if axis.length < 1e-6:
        return
    w = axis.normalized()
    u = w.orthogonal().normalized()
    v = w.cross(u)
    rings = [[tuple(e + r * (math.cos(2 * math.pi * i / sides) * u + math.sin(2 * math.pi * i / sides) * v))
              for i in range(sides)] for e in (p0, p1)]
    loft(b, rings, lambda k, i, c: mat)


def wheel(b, centre, diameter, width):
    """A tyre and hub on an axle along Y, at a spec-frame centre."""
    c = Vector(centre)
    tube(b, c - Vector((0, width / 2, 0)), c + Vector((0, width / 2, 0)), diameter / 2, "tyre", 18)
    tube(b, c - Vector((0, width * 0.55, 0)), c + Vector((0, width * 0.55, 0)), diameter * 0.22, "metal", 12)


def propeller(b, centre, facing, diameter, blades, spinner=True, chord=None, phase=0.0, mat="dark"):
    """Blades in the plane normal to facing, around a spec-frame centre; a spinner in front."""
    c = to_blender(centre)
    a = Vector(facing).normalized()
    u = a.orthogonal().normalized()
    v = a.cross(u)
    r = diameter / 2
    chord = chord or max(0.04, diameter * 0.08)
    hub = max(0.03, diameter * 0.07)
    if spinner:
        prof = [(0.0, hub), (hub * 0.8, hub * 0.9), (hub * 1.8, hub * 0.4), (hub * 2.4, 0.004)]
        rings = [[tuple(c + a * d + rr * (math.cos(2 * math.pi * i / 16) * u + math.sin(2 * math.pi * i / 16) * v))
                  for i in range(16)] for d, rr in prof]
        loft(b, rings, lambda k, i, cc: "paint" if spinner == "paint" else "dark")
    for k in range(blades):
        ang = math.radians(phase) + 2 * math.pi * k / blades
        d = math.cos(ang) * u + math.sin(ang) * v
        side = a.cross(d).normalized()
        stations = [(0.12, 1.0), (0.6, 0.85), (1.0, 0.45)]
        edges = []
        for frac, w in stations:
            p = c + d * r * frac
            pitch = math.radians(35 - 20 * frac)
            off = side * math.cos(pitch) * chord * w / 2 + a * math.sin(pitch) * chord * w / 2
            edges.append((p - off, p + off))
        th = a * chord * 0.07
        for (pa, pb), (qa, qb) in zip(edges[:-1], edges[1:]):
            vs = b.verts([tuple(pa + th), tuple(pb + th), tuple(qb + th), tuple(qa + th),
                          tuple(pa - th), tuple(pb - th), tuple(qb - th), tuple(qa - th)])
            for q in ((0, 1, 2, 3), (7, 6, 5, 4), (0, 4, 5, 1), (1, 5, 6, 2), (2, 6, 7, 3), (3, 7, 4, 0)):
                b.face([vs[i] for i in q], mat)


def part_propeller(b, p, R):
    facing = p.get("facing", "forward")
    facing = FACING[facing] if isinstance(facing, str) else facing
    propeller(b, R.point(p.get("at")), facing, p["diameter"], p.get("blades", 2), spinner=p.get("spinner", True),
              chord=p.get("chord"), phase=p.get("phase", 0.0), mat=p.get("material", "dark"))


def part_tube(b, t, R):
    tube(b, R.point(t["from"]), R.point(t["to"]), t["radius"], t.get("material", "metal"), t.get("sides", 10))


def part_gear(b, g, R):
    x, y, z = R.point(g.get("at"))
    d = g.get("wheel", 0.5)
    bottom = (x, y + g.get("splay", 0.0), z - g["length"])
    tube(b, (x, y, z), (bottom[0], bottom[1], bottom[2] + d * 0.35), g.get("strut", 0.05), "metal")
    n = g.get("wheels", 1)
    for k in range(n):
        off = (k - (n - 1) / 2) * d * 0.45 * (2 if n == 2 else 1)
        wheel(b, (bottom[0], bottom[1] + off, bottom[2]), d, g.get("tyre_width", d * 0.35))


def part_wheel(b, w, R):
    wheel(b, R.point(w.get("at")), w["diameter"], w.get("width", w["diameter"] * 0.3))


def part_canopy(b, c, R):
    x, y, z = R.point(c.get("at"))
    rings = []
    for i in range(17):
        t = i / 16
        k = math.sin(math.pi * t) ** 0.6
        rings.append(ring(-(x + c["length"] * t), y, z, c["width"] / 2 * k + 1e-3, c["height"] * k + 1e-3, 24, 2.0))
    loft(b, rings, lambda k, i, cc: c.get("material", "glass"))


def part_lathe(b, p, R):
    x, y, z = R.point(p.get("at"))
    lathe(b, (x, y, z), p.get("axis", "x"), p["profile"], p.get("material", "paint"), p.get("sides", 24),
          p.get("gores", 0), p.get("gore_material", "accent"), p.get("open", False))


def part_box(b, p, R):
    box(b, R.point(p.get("at")), p["size"], p.get("material", "paint"), p.get("yaw", 0.0))


def part_radial(b, p, R):
    centre = to_blender(R.point(p.get("at")))
    axis = {"z": "Z", "x": "X", "y": "Y"}[p.get("axis", "z")]
    for k in range(p["count"]):
        ang = math.radians(p.get("phase", 0.0)) + 2 * math.pi * k / p["count"]
        b.push(Matrix.Translation(centre) @ Matrix.Rotation(ang, 4, axis))
        build_parts(b, p["parts"], R)
        b.pop()


PARTS = {"fuselage": part_fuselage, "surface": part_surface, "nacelle": part_nacelle,
         "propeller": part_propeller, "tube": part_tube, "gear": part_gear, "wheel": part_wheel,
         "canopy": part_canopy,
         "lathe": part_lathe, "box": part_box, "radial": part_radial}


def note_rotor(b, p, R):
    """Where a spinning part goes, in the model's frame, instead of building it."""
    facing = p.get("facing", "forward")
    facing = Vector(FACING[facing] if isinstance(facing, str) else facing)
    b.rotors.append({"position": b.xf @ to_blender(R.point(p.get("at"))),
                     "facing": (b.xf.to_3x3() @ facing).normalized(),
                     "diameter": p["diameter"], "blades": p.get("blades", 2), "part": p})


def build_parts(b, parts, R):
    for p in parts:
        fn = PARTS.get(p.get("type"))
        if fn is None:
            raise ValueError("unknown part type %r" % p.get("type"))
        if b.skip_spin and p.get("spin"):
            fn = note_rotor
        mirror = p.get("mirror", p.get("type") == "surface" and not p.get("vertical", False))
        fn(b, p, R)
        if mirror:
            b.push(Matrix.Scale(-1, 4, (0, 1, 0)))
            fn(b, p, R)
            b.pop()


# ---------------------------------------------------------------------------------------------
# Scene, export and review renders
# ---------------------------------------------------------------------------------------------

def reset_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)


def centre_object(obj, origin=None):
    """Put the model's origin at the middle of its bounding box, or at a spec-frame point (a
    drone's centre of mass, where its physics puts the frame). Returns its size and the offset."""
    bb = [Vector(c) for c in obj.bound_box]
    lo = Vector((min(v.x for v in bb), min(v.y for v in bb), min(v.z for v in bb)))
    hi = Vector((max(v.x for v in bb), max(v.y for v in bb), max(v.z for v in bb)))
    offset = to_blender(origin) if origin is not None else (lo + hi) / 2
    obj.data.transform(Matrix.Translation(-offset))
    return hi - lo, offset


def uv_unwrap(obj):
    bpy.ops.object.select_all(action="DESELECT")     # this object only
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.smart_project(angle_limit=math.radians(66), island_margin=0.003)
    bpy.ops.object.mode_set(mode="OBJECT")


def render_views(folder, size):
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_WORKBENCH"
    scene.display.shading.light = "STUDIO"
    scene.display.shading.color_type = "MATERIAL"
    scene.display.shading.show_cavity = True
    scene.render.resolution_x = scene.render.resolution_y = 640
    world = bpy.data.worlds.new("w")
    scene.world = world
    world.color = (0.55, 0.57, 0.6)
    cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam"))
    scene.collection.objects.link(cam)
    scene.camera = cam
    cam.data.type = "ORTHO"
    cam.data.ortho_scale = max(size) * 1.15
    os.makedirs(os.path.join(folder, "views"), exist_ok=True)
    for name, az, el in (("three_quarter", 35, 25), ("side", 90, 0.5), ("top", 0, 89.5), ("front", 0, 3)):
        a, e = math.radians(az), math.radians(el)
        pos = Vector((math.cos(e) * math.cos(a), math.cos(e) * math.sin(a), math.sin(e))) * max(size) * 3
        cam.location = pos
        cam.rotation_euler = (-pos).to_track_quat("-Z", "Y").to_euler()
        scene.render.filepath = os.path.join(folder, "views", name + ".png")
        bpy.ops.render.render(write_still=True)


def export(obj, folder, name, blend=True):
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.export_scene.gltf(filepath=os.path.join(folder, name + ".glb"), use_selection=True,
                              export_format="GLB", export_yup=True)
    bpy.ops.export_scene.fbx(filepath=os.path.join(folder, name + ".fbx"), use_selection=True,
                             apply_unit_scale=True, apply_scale_options="FBX_SCALE_UNITS",
                             axis_forward="-Y", axis_up="Z", mesh_smooth_type="FACE")
    if blend:
        bpy.ops.wm.save_as_mainfile(filepath=os.path.join(folder, name + ".blend"))


def rotors_of(entry, spec, offset, folder):
    """For an aircraft with parts marked "spin" (the propellers a simulator turns): build it again
    without them as <name>_body, build one of them on its own, centred on its hub and turning
    about +Z, as <name>_rotor, and return where each goes, in the model's frame (metres, +X
    forward, +Y left, +Z up, from the model's origin). Nothing when nothing spins."""
    if not any(p.get("spin") for p in walk(spec["parts"])):
        return []
    name = entry["name"]
    body = Builder(palette(spec))
    body.skip_spin = True
    build_parts(body, spec["parts"], Resolver(spec["parts"]))
    rotors = body.rotors
    obj = body.finish(name + "_body")
    obj.data.transform(Matrix.Translation(-offset))
    uv_unwrap(obj)
    export(obj, folder, name + "_body", blend=False)
    bpy.data.objects.remove(obj)          # out of the renders and the .blend

    first = rotors[0]["part"]
    rotor = Builder(palette(spec))
    propeller(rotor, (0.0, 0.0, 0.0), (0, 0, 1), first["diameter"], first.get("blades", 2),
              spinner=first.get("spinner", False), chord=first.get("chord"), mat=first.get("material", "dark"))
    obj = rotor.finish(name + "_rotor")
    uv_unwrap(obj)
    export(obj, folder, name + "_rotor", blend=False)
    bpy.data.objects.remove(obj)
    return [{"position_m": [round(v, 4) for v in (r["position"] - offset)],
             "facing": [round(v, 4) for v in r["facing"]], "diameter_m": r["diameter"],
             "blades": r["blades"]} for r in rotors]


def walk(parts):
    for p in parts:
        yield p
        if p.get("type") == "radial":
            yield from walk(p.get("parts", []))


def build_one(entry, out, render=True):
    reset_scene()
    spec = entry["build"]
    b = Builder(palette(spec))
    build_parts(b, spec["parts"], Resolver(spec["parts"]))
    obj = b.finish(entry["name"])
    size, offset = centre_object(obj, spec.get("origin"))
    uv_unwrap(obj)
    folder = os.path.join(out, entry["name"])
    os.makedirs(folder, exist_ok=True)
    tris = sum(len(p.vertices) - 2 for p in obj.data.polygons)
    checks = []
    for key, axis, label in (("span_m", 1, "span"), ("length_m", 0, "length")):
        want = entry.get(key)
        if want:
            got = size[axis]
            ok = abs(got - want) <= 0.05 * want
            checks.append("%s %.2f m (real %.2f)%s" % (label, got, want, "" if ok else " OFF BY %+.0f%%" % (100 * (got / want - 1))))
    with io.open(os.path.join(folder, "model.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump({"name": entry["name"], "class": entry.get("class"), "role": entry.get("role"),
                   "size_m": [round(v, 3) for v in size], "span_m": entry.get("span_m"),
                   "length_m": entry.get("length_m"), "triangles": tris,
                   "materials": [m.name for m in obj.data.materials],
                   "frame": "metres, +X forward, +Y left, +Z up, origin at %s" % (
                       "the spec's origin %s" % spec["origin"] if "origin" in spec else "the bounding box centre"),
                   "rotors": rotors_of(entry, spec, offset, folder)}, f, indent=1)
    if render:
        render_views(folder, size)
    export(obj, folder, entry["name"])
    print("BUILT %-24s %6.2f x %6.2f x %5.2f m  %7d triangles  %s" % (entry["name"], size.x, size.y, size.z, tris,
                                                                      "; ".join(checks)), flush=True)


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    only, out, render, manifest = [], DEFAULT_OUT, True, MANIFEST
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--only":
            i += 1
            while i < len(argv) and not argv[i].startswith("--"):
                only.append(argv[i])
                i += 1
            continue
        if a in ("--out", "--manifest"):
            out, manifest = (argv[i + 1], manifest) if a == "--out" else (out, argv[i + 1])
            i += 2
            continue
        render = render and a != "--no-render"
        i += 1
    with io.open(manifest, encoding="utf-8") as f:
        entries = json.load(f)["aircraft"]
    failed = []
    for e in entries:
        if (not only or e["name"] in only) and "build" in e:
            try:
                build_one(e, out, render)
            except Exception as err:          # one bad spec should not stop the fleet
                failed.append(e["name"])
                print("FAILED %s: %s" % (e["name"], err), flush=True)
                traceback.print_exc()
    if failed:
        print("FAILED: %s" % ", ".join(failed), flush=True)


if __name__ == "__main__":
    main()
