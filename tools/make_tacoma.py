# Builds the 3rd-gen (2016-2023) double cab short bed pickup used on /parts as 22 separately named parts
# and exports models/tacoma-style.glb. Our own geometry, modelled from published dimensions and reference
# photos (research/tacoma, not shipped). No badges, logos or grille lettering.
#
#   "C:\Program Files\Blender Foundation\Blender 5.2\blender.exe" -b --factory-startup -P tools/make_tacoma.py
#   ... -P tools/make_tacoma.py -- --render  (also writes preview renders to research/renders)
#
# Axes while building: X = forward, Y = driver side (left), Z = up, metres. The glTF exporter turns that into
# three.js axes: X forward, Y up, driver side = -Z. Mesh names are the contract with parts.html / parts.json.
#
# Dimensions (2016-2023 double cab 5 ft bed 4x4): length 5.392, wheelbase 3.236, width 1.890, height ~1.80,
# track 1.600, tyres 265/70R16 (radius 0.39).
import bpy, bmesh, math, os, sys
import numpy as np
from mathutils import Vector, Matrix

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.environ.get("AG_ROOT") or os.path.dirname(HERE)
OUT = os.path.join(ROOT, "models", "tacoma-style.glb")
ARGS = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []

bpy.ops.wm.read_factory_settings(use_empty=True)
coll = bpy.context.scene.collection

FA, RA = 1.795, -1.441          # axle x
WR, WY = 0.392, 0.80            # tyre radius, wheel centre y
AR = 0.475                      # wheel arch radius

# =============================================================== materials
def material(name, rgb, metallic=0.0, rough=0.5, alpha=1.0, emit=None, estr=1.0, coat=0.0, trans=0.0):
    m = bpy.data.materials.new(name)
    b = next(n for n in m.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    b.inputs["Base Color"].default_value = (*rgb, 1)
    b.inputs["Metallic"].default_value = metallic
    b.inputs["Roughness"].default_value = rough
    if coat:
        b.inputs["Coat Weight"].default_value = coat
        b.inputs["Coat Roughness"].default_value = 0.03
    if trans:
        b.inputs["Transmission Weight"].default_value = trans
    if alpha < 1:
        b.inputs["Alpha"].default_value = alpha
        try: m.surface_render_method = "BLENDED"
        except Exception: pass
    if emit:
        b.inputs["Emission Color"].default_value = (*emit, 1)
        b.inputs["Emission Strength"].default_value = estr
    return m

PAINT_RGB = (0.32, 0.012, 0.016)
M = {
    "paint": material("paint", PAINT_RGB, 0.55, 0.32, coat=1.0),
    "trim": material("trim_black", (0.022, 0.022, 0.022), 0.0, 0.62),
    "gloss": material("gloss_black", (0.006, 0.006, 0.006), 0.0, 0.12, coat=1.0),
    "glass": material("glass", (0.03, 0.04, 0.045), 0.0, 0.02, alpha=0.62),
    "tire": material("tire", (0.028, 0.028, 0.028), 0.0, 0.88),
    "rim": material("rim", (0.48, 0.49, 0.50), 1.0, 0.26),
    "rim_dark": material("rim_dark", (0.07, 0.072, 0.075), 0.85, 0.38),
    "chrome": material("chrome", (0.9, 0.9, 0.9), 1.0, 0.06),
    "lamp": material("lamp_clear", (0.95, 0.96, 1.0), 0.0, 0.1, emit=(0.9, 0.95, 1.0), estr=3.0),
    "lamp_glass": material("lamp_glass", (0.85, 0.88, 0.9), 0.0, 0.02, alpha=0.18),
    "lamp_red": material("lamp_red", (0.42, 0.01, 0.01), 0.0, 0.08, coat=1.0),
    "lamp_redlit": material("lamp_red_lit", (0.6, 0.02, 0.02), 0.0, 0.2, emit=(0.8, 0.02, 0.01), estr=2.0),
    "amber": material("lamp_amber", (0.9, 0.42, 0.05), 0.0, 0.15, emit=(0.9, 0.4, 0.02), estr=0.4),
    "housing": material("lamp_housing", (0.05, 0.05, 0.055), 0.6, 0.3),
    "engine": material("engine_metal", (0.10, 0.105, 0.11), 0.8, 0.45),
    "alu": material("engine_alu", (0.30, 0.31, 0.32), 1.0, 0.42),
    "under": material("underbody", (0.015, 0.015, 0.015), 0.0, 0.9),
    "interior": material("interior", (0.035, 0.035, 0.038), 0.0, 0.8),
    "rubber": material("rubber", (0.01, 0.01, 0.01), 0.0, 0.7),
    "skid": material("skid_gray", (0.16, 0.165, 0.17), 0.4, 0.5),
    "grille_hex": material("grille_hex", (0.10, 0.105, 0.11), 1.0, 0.28),
    "step": material("step_black", (0.03, 0.03, 0.032), 0.6, 0.42),
    "vinyl": material("tonneau_black", (0.018, 0.018, 0.019), 0.0, 0.72),
}

# =============================================================== helpers
def link(ob):
    coll.objects.link(ob)
    return ob

def activate(ob):
    for o in list(bpy.context.view_layer.objects):
        if o is not None: o.select_set(False)
    ob.select_set(True)
    bpy.context.view_layer.objects.active = ob

def apply_mods(ob):
    activate(ob)
    for m in list(ob.modifiers):
        try:
            bpy.ops.object.modifier_apply(modifier=m.name)
        except RuntimeError as e:
            print("modifier failed", ob.name, m.name, e)
            ob.modifiers.remove(m)

def set_mat(ob, mat):
    ob.data.materials.clear()
    ob.data.materials.append(M[mat] if isinstance(mat, str) else mat)
    return ob

def mesh_from_bm(name, bm, mat=None):
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me); bm.free()
    ob = link(bpy.data.objects.new(name, me))
    if mat: set_mat(ob, mat)
    return ob

def grid(name, P, mat, close_v=False, close_u=False, inside=None, smooth=True, sharp_cols=(), sharp_rows=()):
    """Quad surface from a (nu, nv, 3) array. inside = a point the normals should face away from."""
    P = np.asarray(P, dtype=float)
    nu, nv = P.shape[:2]
    bm = bmesh.new()
    V = [[bm.verts.new(tuple(P[i, j])) for j in range(nv)] for i in range(nu)]
    iu = nu if close_u else nu - 1
    iv = nv if close_v else nv - 1
    for i in range(iu):
        for j in range(iv):
            a, b, c, d = V[i][j], V[(i + 1) % nu][j], V[(i + 1) % nu][(j + 1) % nv], V[i][(j + 1) % nv]
            if len({a, b, c, d}) < 3: continue
            try:
                bm.faces.new([a, b, c, d] if len({a, b, c, d}) == 4 else list(dict.fromkeys([a, b, c, d])))
            except ValueError:
                pass
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-6)
    bm.normal_update()
    if inside is not None:
        ins = Vector(inside)
        s = sum((f.calc_center_median() - ins).dot(f.normal) * f.calc_area() for f in bm.faces)
        if s < 0:
            for f in bm.faces: f.normal_flip()
    for f in bm.faces: f.smooth = smooth
    # sharp seams along chosen grid columns / rows
    if sharp_cols or sharp_rows:
        idx = {}
        for i in range(nu):
            for j in range(nv):
                idx[V[i][j]] = (i, j) if V[i][j].is_valid else None
        for e in bm.edges:
            a, b = idx.get(e.verts[0]), idx.get(e.verts[1])
            if not a or not b: continue
            if a[1] == b[1] and a[1] in sharp_cols: e.smooth = False
            if a[0] == b[0] and a[0] in sharp_rows: e.smooth = False
    return mesh_from_bm(name, bm, mat)

def solidify(ob, t, offset=-1.0):
    m = ob.modifiers.new("solid", "SOLIDIFY")
    m.thickness = t; m.offset = offset; m.use_even_offset = False; m.use_quality_normals = True
    apply_mods(ob)
    return ob

def subsurf(ob, lvl=1):
    m = ob.modifiers.new("sub", "SUBSURF"); m.levels = lvl; m.render_levels = lvl
    apply_mods(ob)
    return ob

def bevel(ob, width, seg=3, angle=35):
    m = ob.modifiers.new("bev", "BEVEL")
    m.width = width; m.segments = seg; m.limit_method = "ANGLE"; m.angle_limit = math.radians(angle)
    m.harden_normals = False
    apply_mods(ob)
    return ob

def boolean(ob, cutter, op="DIFFERENCE", keep=False):
    m = ob.modifiers.new("bool", "BOOLEAN")
    m.operation = op; m.object = cutter; m.solver = "EXACT"
    try: m.use_self = True
    except Exception: pass
    apply_mods(ob)
    if not keep: bpy.data.objects.remove(cutter, do_unlink=True)
    return ob

def dup(ob, name=None):
    c = ob.copy(); c.data = ob.data.copy()
    if name: c.name = name
    return link(c)

def join(name, obs):
    obs = [o for o in obs if o is not None]
    for o in list(bpy.context.view_layer.objects):
        if o is not None: o.select_set(False)
    for o in obs: o.select_set(True)
    bpy.context.view_layer.objects.active = obs[0]
    if len(obs) > 1: bpy.ops.object.join()
    ob = bpy.context.active_object
    ob.name = name; ob.data.name = name
    return ob

def prism(name, pts, axis, a0, a1, mat="trim"):
    """Extrude a 2D polygon along an axis. pts are (x,z) for axis Y, (y,z) for X, (x,y) for Z."""
    def p3(u, v, a):
        if axis == "Y": return (u, a, v)
        if axis == "X": return (a, u, v)
        return (u, v, a)
    bm = bmesh.new()
    v0 = [bm.verts.new(p3(u, v, a0)) for u, v in pts]
    v1 = [bm.verts.new(p3(u, v, a1)) for u, v in pts]
    bm.faces.new(v0); bm.faces.new(list(reversed(v1)))
    n = len(pts)
    for i in range(n):
        j = (i + 1) % n
        bm.faces.new((v0[i], v0[j], v1[j], v1[i]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return mesh_from_bm(name, bm, mat)

def box(name, x0, x1, y0, y1, z0, z1, mat="trim", bev=0.0, seg=3):
    ob = prism(name, [(x0, z0), (x1, z0), (x1, z1), (x0, z1)], "Y", min(y0, y1), max(y0, y1), mat)
    if bev: bevel(ob, bev, seg)
    for p in ob.data.polygons: p.use_smooth = True
    return ob

def cyl(name, x, y, z, r, depth, mat, axis="Y", verts=48, bev=0.0, seg=2, r2=None):
    rot = {"Y": (math.pi / 2, 0, 0), "X": (0, math.pi / 2, 0), "Z": (0, 0, 0)}[axis]
    if r2 is None:
        bpy.ops.mesh.primitive_cylinder_add(vertices=verts, radius=r, depth=depth, location=(x, y, z), rotation=rot)
    else:
        bpy.ops.mesh.primitive_cone_add(vertices=verts, radius1=r, radius2=r2, depth=depth, location=(x, y, z), rotation=rot)
    ob = bpy.context.active_object; ob.name = name
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    set_mat(ob, mat)
    if bev: bevel(ob, bev, seg)
    for p in ob.data.polygons: p.use_smooth = True
    return ob

def mirror_y(ob, name=None):
    c = dup(ob, name or ob.name + "_m")
    c.data.transform(Matrix.Scale(-1, 4, (0, 1, 0)))
    c.data.flip_normals()
    return c

def smooth_all(ob, angle=40):
    for p in ob.data.polygons: p.use_smooth = True
    m = ob.modifiers.new("ws", "EDGE_SPLIT"); m.split_angle = math.radians(angle); m.use_edge_sharp = True
    apply_mods(ob)
    return ob

def mats_by(ob, fn):
    """Reassign per-face material: fn(center, normal) -> material key or None (keep)."""
    keys = []
    for p in ob.data.polygons:
        k = fn(p.center, p.normal)
        keys.append(k)
    for k in set(k for k in keys if k):
        if M[k].name not in [m.name for m in ob.data.materials if m]:
            ob.data.materials.append(M[k])
    names = [m.name for m in ob.data.materials]
    for p, k in zip(ob.data.polygons, keys):
        if k: p.material_index = names.index(M[k].name)

def pchip(xs, ys):
    xs = np.asarray(xs, float); ys = np.asarray(ys, float)
    h = np.diff(xs); d = np.diff(ys) / h
    m = np.zeros_like(ys)
    for k in range(1, len(xs) - 1):
        if d[k - 1] * d[k] > 0:
            w1, w2 = 2 * h[k] + h[k - 1], h[k] + 2 * h[k - 1]
            m[k] = (w1 + w2) / (w1 / d[k - 1] + w2 / d[k])
    m[0], m[-1] = d[0], d[-1]
    def f(x):
        x = np.clip(x, xs[0], xs[-1])
        k = int(np.clip(np.searchsorted(xs, x) - 1, 0, len(xs) - 2))
        t = (x - xs[k]) / h[k]
        h00, h10, h01, h11 = 2*t**3 - 3*t**2 + 1, t**3 - 2*t**2 + t, -2*t**3 + 3*t**2, t**3 - t**2
        return h00 * ys[k] + h10 * h[k] * m[k] + h01 * ys[k + 1] + h11 * h[k] * m[k + 1]
    return f

def smoothstep(a, b, x):
    t = min(1.0, max(0.0, (x - a) / (b - a)))
    return t * t * (3 - 2 * t)

def bump(x, c, w):
    d = (x - c) / w
    return math.exp(-d * d)

def crspline(ctrl, n_per):
    """Centripetal Catmull-Rom through ctrl (list of 2D tuples, flags) -> polyline. ctrl item = (y, z, crisp)."""
    out = []
    runs, cur = [], [ctrl[0]]
    for c in ctrl[1:]:
        cur.append(c)
        if c[2]:
            runs.append(cur); cur = [c]
    if len(cur) > 1: runs.append(cur)
    for r in runs:
        pts = [np.array(c[:2], float) for c in r]
        ext = [2 * pts[0] - pts[1]] + pts + [2 * pts[-1] - pts[-2]]
        for k in range(1, len(ext) - 2):
            p0, p1, p2, p3 = ext[k - 1], ext[k], ext[k + 1], ext[k + 2]
            for s in range(n_per):
                t = s / n_per
                t2, t3 = t * t, t * t * t
                out.append(0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t2 + (-p0 + 3 * p1 - 3 * p2 + p3) * t3))
    out.append(np.array(ctrl[-1][:2], float))
    return out

def offset_poly(pts, d):
    """Offset a closed CCW-or-CW polygon by d (positive = grow)."""
    P = [np.array(p, float) for p in pts]
    n = len(P)
    area = sum(P[i][0] * P[(i + 1) % n][1] - P[(i + 1) % n][0] * P[i][1] for i in range(n))
    sgn = 1 if area > 0 else -1
    lines = []
    for i in range(n):
        a, b = P[i], P[(i + 1) % n]
        t = (b - a) / np.linalg.norm(b - a)
        nrm = np.array([t[1], -t[0]]) * sgn
        lines.append((a + nrm * d, t))
    out = []
    for i in range(n):
        (p1, t1), (p2, t2) = lines[i - 1], lines[i]
        den = t1[0] * t2[1] - t1[1] * t2[0]
        if abs(den) < 1e-9: out.append(tuple(p2)); continue
        s = ((p2[0] - p1[0]) * t2[1] - (p2[1] - p1[1]) * t2[0]) / den
        out.append(tuple(p1 + t1 * s))
    return out

def split_by(src, cutter_inside, cutter_outside, name_in):
    """Part = src ∩ inside-cutter; src -= outside-cutter (the gap between them is the panel gap)."""
    part = dup(src, name_in)
    boolean(part, cutter_inside, "INTERSECT")
    boolean(src, cutter_outside, "DIFFERENCE")
    return part

def side_cutters(poly, y0, y1, gap=0.0035):
    ci = prism("ci", offset_poly(poly, -gap / 2), "Y", y0, y1)
    co = prism("co", offset_poly(poly, gap / 2), "Y", y0, y1)
    return ci, co

def arch_cutter(x, side, r=AR, z=WR + 0.035):
    y0, y1 = (0.55, 1.2) if side > 0 else (-1.2, -0.55)
    return cyl("arch", x, (y0 + y1) / 2, z, r, y1 - y0, "trim", verts=72)

def finish(ob, angle=None):
    """Origin at the part's own centre (the explode pivot)."""
    activate(ob)
    bpy.ops.object.origin_set(type="ORIGIN_GEOMETRY", center="BOUNDS")
    return ob


# =============================================================== side profile (shared by cab, fender, bed)
belt_z = pchip([-2.70, -1.05, 0.0, 1.10, 1.6, 2.0, 2.32, 2.70], [1.300, 1.300, 1.294, 1.286, 1.264, 1.238, 1.214, 1.18])

def half_w(x):
    """Body half width at the door crease, swelling over both wheel flares."""
    return 0.926 + 0.010 * bump(x, FA, 0.40) + 0.012 * bump(x, RA, 0.42)

def fender_inner(x):
    return 0.835 + (0.80 - 0.835) * smoothstep(1.05, 1.30, x) - 0.05 * smoothstep(1.6, 2.31, x)

def side_ctrl(x, kind):
    """Half cross-section control points (y, z, crisp), bottom inner edge -> top inner edge."""
    zb = belt_z(x); w = half_w(x)
    fz = smoothstep(1.05, 1.35, x)
    zr = 0.60 if kind == "bed" else 0.468 + 0.10 * fz
    c = [(w - 0.090, zr, True), (w - 0.046, zr + 0.010, False), (w - 0.033, zr + 0.05, False)]
    if zr < 0.60: c.append((w - 0.030, 0.62, False))
    c += [(w - 0.024, 0.72, False), (w - 0.010, 0.815, False),
          (w, 0.868, True),                                     # the door / bed crease
          (w + 0.002, 0.95, False), (w - 0.003, 1.07, False), (w - 0.016, 1.18, False),
          (w - 0.038, zb - 0.022, False), (w - 0.058, zb, True)]
    if kind == "bed":
        c += [(0.80, zb + 0.004, True), (0.787, zb - 0.025, True), (0.786, 0.845, True)]
    else:
        c += [(fender_inner(x), zb + 0.012, True)]
    return c

def side_section(x, kind, n_per=3):
    return crspline(side_ctrl(x, kind), n_per)

def side_loft(name, xs, kind, n_per=3, mat="paint"):
    rows = [[(x, y, z) for y, z in side_section(x, kind, n_per)] for x in xs]
    return grid(name, np.array(rows), mat, inside=(float(np.mean(xs)), 0.0, 0.9))

def flip_side(ob):
    ob.data.transform(Matrix.Scale(-1, 4, (0, 1, 0))); ob.data.flip_normals()
    return ob

# ---- wheel arch outline (squared-off arc like the real flares), shared by cutter, lip and liner
def arch_pts(cx, n=56, ax=0.505, az=0.462, cz=WR + 0.035, ex=2.7, a0=-12, a1=192):
    pts = []
    for k in range(n + 1):
        t = math.radians(a0 + (a1 - a0) * k / n)
        c, s_ = math.cos(t), math.sin(t)
        x = cx + ax * math.copysign(abs(c) ** (2 / ex), c)
        z = cz + az * math.copysign(abs(s_) ** (2 / ex), s_)
        nx = math.copysign(abs(c) ** (2 - 2 / ex), c) / ax
        nz = math.copysign(abs(s_) ** (2 - 2 / ex), s_) / az
        L = math.hypot(nx, nz) or 1
        pts.append((x, z, nx / L, nz / L))
    return pts

def arch_cutter_obj(cx, side, grow=0.0):
    p = arch_pts(cx, ax=0.505 + grow, az=0.462 + grow)
    poly = [(x, z) for x, z, _, _ in p]
    poly = [(poly[0][0], -0.2)] + poly + [(poly[-1][0], -0.2)]
    y0, y1 = (0.45, 1.3) if side > 0 else (-1.3, -0.45)
    return prism("archcut", poly, "Y", y0, y1)

def body_y(x, z, kind):
    """Outer skin half width at height z (from the section polyline)."""
    sec = side_section(x, kind)
    best, bd = sec[0][0], 9
    for (y0, z0), (y1, z1) in zip(sec[:-1], sec[1:]):
        if min(z0, z1) <= z <= max(z0, z1) and y0 > 0.84 and abs(z1 - z0) > 1e-6:
            return y0 + (y1 - y0) * (z - z0) / (z1 - z0)
        d = abs(z0 - z)
        if d < bd and y0 > 0.84: best, bd = y0, d
    return best

def arch_lip(cx, side):
    """Moulded flare lip around the arch, swept along the arch outline, sitting on the real skin."""
    kind = "bed" if cx < 0 else "body"
    zr = 0.60 if kind == "bed" else 0.57
    p = [q for q in arch_pts(cx, n=80, a0=-30, a1=210) if q[1] >= zr + 0.004]
    prof = [(-0.014, -0.034), (-0.003, 0.008), (0.008, 0.034), (0.030, 0.040), (0.058, 0.030), (0.082, 0.010), (0.098, -0.004)]
    rows = []
    for x, z, nx, nz in p:
        row = []
        for d, dy in prof:
            px, pz = x + nx * d, z + nz * d
            row.append((px, side * (body_y(px, max(pz, zr + 0.01), kind) + dy), pz))
        rows.append(row)
    ob = grid("lip", np.array(rows), "paint", inside=(cx, side * 0.5, WR))
    solidify(ob, 0.004)
    return ob

def wheel_liner(cx, side):
    """Black wheel-well tub so you never see into the body through the arch."""
    zmin = 0.60 if cx < 0 else 0.56
    p = [q for q in arch_pts(cx, n=48, ax=0.50, az=0.455, a0=-30, a1=210) if q[1] >= zmin]
    rows = [[(x, side * y, z) for y in (0.58, 0.93)] for x, z, nx, nz in p]
    ob = grid("liner", np.array(rows), "under", inside=(cx, side * 0.75, WR))
    solidify(ob, 0.01, 0)
    return ob

# =============================================================== body: lower sides (cab + front fenders)
X_CAB_BACK, X_FENDER_FRONT = -1.035, 2.31
side_shells = []
for s in (1, -1):
    sh = side_loft("side", list(np.linspace(X_CAB_BACK, X_FENDER_FRONT, 170)), "body")
    if s < 0: flip_side(sh)
    solidify(sh, 0.004)
    boolean(sh, arch_cutter_obj(FA, s))
    side_shells.append(sh)

# doors (side-view outlines), panel gap 3.5 mm
DOOR_POLY = {
    "fl": [(1.150, 0.555), (0.098, 0.555), (0.098, 1.34), (1.178, 1.34)],
    "rl": [(0.080, 0.555), (-0.865, 0.555), (-0.875, 1.34), (0.080, 1.34)],
}
door_lower = {}
for s, sh in zip((1, -1), side_shells):
    for k, poly in DOOR_POLY.items():
        key = k if s > 0 else k.replace("l", "r")
        y0, y1 = (0.6, 1.2) if s > 0 else (-1.2, -0.6)
        ci, co = side_cutters(poly, y0, y1)
        door_lower[key] = split_by(sh, ci, co, "door_" + key)

# ---- greenhouse: horizontal slices from the belt to the roof edge, then the roof crown
GH_Z0, GH_Z1 = 1.300, 1.768
def gh_w(t): return 0.840 - 0.150 * t - 0.022 * t * t
def gh_slice(t):
    z = GH_Z0 + (GH_Z1 - GH_Z0) * t
    xf = 1.178 - 0.818 * t ** 0.97          # windshield line (side view)
    xb = -0.998 + 0.075 * t                 # back glass line
    w = gh_w(t)
    rf, rb = 0.11 + 0.05 * t, 0.06
    bow_f, bow_b = 0.075, 0.03
    pts = []
    yc = w - rf
    for k in range(12):                      # front edge, centre -> A pillar, bowed in plan
        y = yc * k / 12
        pts.append((xf + bow_f * (1 - (y / w) ** 2), y))
    xfc = xf + bow_f * (1 - (yc / w) ** 2)
    for k in range(7):                       # front corner
        a = math.pi / 2 * k / 6
        pts.append((xfc - rf * 0.85 * (1 - math.cos(a)), yc + rf * math.sin(a)))
    x0s, x1s = xfc - rf * 0.85, xb + rb
    for k in range(1, 30):                   # side
        pts.append((x0s + (x1s - x0s) * k / 30, w))
    for k in range(7):                       # back corner
        a = math.pi / 2 * k / 6
        pts.append((xb + rb * (1 - math.sin(a)), w - rb * (1 - math.cos(a))))
    yb0 = w - rb
    for k in range(1, 9):                    # back edge -> centre
        y = yb0 * (1 - k / 8)
        pts.append((xb - bow_b * (1 - (y / w) ** 2) + bow_b * (1 - (yb0 / w) ** 2), y))
    full = pts + [(x, -y) for x, y in reversed(pts[1:-1])]
    return [(x, y, z) for x, y in full]

rings = [gh_slice(t) for t in np.linspace(0, 1, 18)]
edge = np.array(rings[-1])
cx_roof = (edge[:, 0].max() + edge[:, 0].min()) / 2
for sy, sx, dz in ((0.985, 0.995, 0.010), (0.95, 0.985, 0.020), (0.88, 0.97, 0.028), (0.75, 0.95, 0.034),
                   (0.55, 0.93, 0.038), (0.30, 0.92, 0.040), (0.03, 0.92, 0.041)):
    rings.append([(cx_roof + (x - cx_roof) * sx, y * sy, GH_Z1 + dz) for x, y, z in edge])
gh = grid("greenhouse", np.array(rings), "paint", close_v=True, inside=(0.0, 0.0, 1.5))
solidify(gh, 0.004)

def front_window(margin, z0, z1, xr):
    pts = []
    for k in range(13):
        z = z0 + (z1 - z0) * k / 12
        pts.append((gh_w((z - GH_Z0) / (GH_Z1 - GH_Z0)) - margin, z))
    poly = [(-y, z) for y, z in pts] + [(y, z) for y, z in reversed(pts)]
    return prism("fw", poly, "X", xr[0], xr[1])

def split_same(src, make, name):
    return split_by(src, make(), make(), name)

ws_glass = split_same(gh, lambda: front_window(0.085, 1.325, 1.735, (0.2, 1.5)), "ws")
frit = split_same(gh, lambda: front_window(0.058, 1.31, 1.75, (0.2, 1.5)), "frit")
bk_glass = split_same(gh, lambda: front_window(0.10, 1.36, 1.725, (-1.3, -0.5)), "bk")
bk_frit = split_same(gh, lambda: front_window(0.075, 1.345, 1.74, (-1.3, -0.5)), "bkfrit")
for o in (ws_glass, bk_glass): set_mat(o, "glass")
for o in (frit, bk_frit): set_mat(o, "trim")

# door frames + door glass from the greenhouse sides
FRAME_POLY = {
    "fl": [(1.170, 1.288), (0.098, 1.288), (0.098, 1.748), (0.33, 1.748)],
    "rl": [(0.080, 1.288), (-0.865, 1.288), (-0.875, 1.70), (-0.835, 1.748), (0.080, 1.748)],
}
WIN_POLY = {
    "fl": [(0.985, 1.338), (0.135, 1.338), (0.135, 1.722), (0.37, 1.722)],
    "rl": [(0.040, 1.338), (-0.655, 1.338), (-0.775, 1.43), (-0.81, 1.69), (-0.775, 1.722), (0.040, 1.722)],
}
door_upper = {}
for s in (1, -1):
    for k in FRAME_POLY:
        key = k if s > 0 else k.replace("l", "r")
        y0, y1 = (0.3, 1.2) if s > 0 else (-1.2, -0.3)
        ci, co = side_cutters(FRAME_POLY[k], y0, y1)
        frame = split_by(gh, ci, co, "frame_" + key)
        set_mat(frame, "trim")
        glass = split_same(frame, lambda: prism("w", WIN_POLY[k], "Y", y0, y1), "dglass_" + key)
        set_mat(glass, "glass")
        door_upper[key] = (frame, glass)

# =============================================================== hood
def hood_w(x):
    if x <= 2.31: return fender_inner(x) - 0.004
    return pchip([2.31, 2.45, 2.56, 2.64], [fender_inner(2.31) - 0.004, 0.715, 0.66, 0.60])(x)

def hood_front(y): return 2.600 + 0.036 * (y / 0.6) ** 2
HOOD_X0 = 1.252

def hood_z(x, y):
    w = hood_w(x)
    ze = belt_z(min(x, 2.31)) + 0.014 - (0.11 * (x - 2.31) if x > 2.31 else 0)
    zz = ze + 0.032 * max(0.0, 1 - (y / w) ** 2)
    yl = 0.40 + 0.17 * smoothstep(1.3, 2.6, x)                 # the two hood character lines
    zz += 0.016 * smoothstep(yl + 0.035, yl - 0.005, abs(y))
    xf = hood_front(y)
    if x > xf - 0.09: zz -= 0.055 * ((x - (xf - 0.09)) / 0.09) ** 2.2   # rounded leading edge
    if x < HOOD_X0 + 0.03: zz -= 0.006 * ((HOOD_X0 + 0.03 - x) / 0.03) ** 2
    return zz

rows = []
NU, NV = 90, 70
for i in range(NU):
    u = i / (NU - 1)
    row = []
    for j in range(NV):
        v = -1 + 2 * j / (NV - 1)
        v = math.copysign(abs(v) ** 0.85, v)
        x = HOOD_X0 + u * (hood_front(0) - HOOD_X0)
        for _ in range(4):
            y = v * hood_w(x)
            x = HOOD_X0 + u * (hood_front(y) - HOOD_X0)
        row.append((x, y, hood_z(x, y)))
    rows.append(row)
hood = grid("hood", np.array(rows), "paint", inside=(1.9, 0, 0.5))
solidify(hood, 0.006)
# TRD Sport style hood scoop
def scoop():
    rows = []
    for i in range(24):
        u = i / 23
        x = 1.86 + 0.36 * u
        hgt = 0.048 * smoothstep(0.0, 0.75, u)
        row = []
        for j in range(26):
            v = -1 + 2 * j / 25
            hw = 0.245 - 0.03 * u
            y = v * hw
            z0 = hood_z(x, y) - 0.004
            prof = max(0.0, 1 - abs(v) ** 4)
            row.append((x, y, z0 + hgt * prof))
        rows.append(row)
    ob = grid("scoop", np.array(rows), "paint", inside=(2.0, 0, 0.8))
    solidify(ob, 0.004)
    mouth = box("mouth", 2.205, 2.222, -0.205, 0.205, hood_z(2.21, 0) + 0.004, hood_z(2.21, 0) + 0.044, "housing", 0.004)
    return [ob, mouth]
hood_obj = join("hood", [hood])

# =============================================================== front clip structure, cowl, wipers
cowl = box("cowl", 1.13, 1.262, -0.84, 0.84, 1.272, 1.296, "trim", 0.006)
wipers = [box("wiper", 1.135, 1.152, y0, y1, 1.300, 1.312, "gloss", 0.003) for y0, y1 in ((0.04, 0.62), (-0.50, 0.06))]
rad_support = box("radsupport", 2.47, 2.50, -0.66, 0.66, 0.46, 1.15, "under")
radiator = box("radiator", 2.41, 2.47, -0.60, 0.60, 0.56, 1.10, "engine", 0.01)
aprons = [box("apron", 1.26, 2.48, s * 0.60, s * 0.625, 0.70, 1.20, "under") for s in (1, -1)]
firewall = box("firewall", 1.18, 1.21, -0.80, 0.80, 0.58, 1.28, "under")

# =============================================================== cab: back wall, floor, inner walls, interior
cab_back = box("cabback", -1.035, -1.025, -0.87, 0.87, 0.50, 1.302, "paint", 0.004)
cab_floor = box("cabfloor", -1.02, 1.20, -0.86, 0.86, 0.50, 0.56, "under")
inner_walls = [box("innerwall", -1.0, 1.16, s * 0.80, s * 0.82, 0.56, 1.29, "interior") for s in (1, -1)]

def rot_obj(ob, rx=0, ry=0, rz=0, pivot=(0, 0, 0)):
    M_ = Matrix.Translation(pivot) @ Matrix.Rotation(rz, 4, "Z") @ Matrix.Rotation(ry, 4, "Y") @ Matrix.Rotation(rx, 4, "X") @ Matrix.Translation(-Vector(pivot))
    ob.data.transform(M_)
    return ob

interior = []
interior.append(box("dash", 0.78, 1.16, -0.79, 0.79, 0.98, 1.22, "interior", 0.04, 3))
interior.append(box("dashtop", 0.80, 1.10, -0.79, 0.79, 1.20, 1.25, "interior", 0.02))
interior.append(box("console", 0.05, 0.85, -0.12, 0.12, 0.56, 0.86, "interior", 0.03))
for y in (0.40, -0.40):
    interior.append(box("seat", 0.12, 0.62, y - 0.25, y + 0.25, 0.70, 0.82, "interior", 0.04, 3))
    back = box("seatback", 0.06, 0.18, y - 0.25, y + 0.25, 0.80, 1.40, "interior", 0.04, 3)
    rot_obj(back, ry=math.radians(-14), pivot=(0.12, 0, 0.80))
    interior.append(back)
    hr = box("headrest", 0.0, 0.10, y - 0.12, y + 0.12, 1.42, 1.58, "interior", 0.035, 3)
    rot_obj(hr, ry=math.radians(-14), pivot=(0.12, 0, 0.80))
    interior.append(hr)
interior.append(box("bench", -0.90, -0.40, -0.76, 0.76, 0.66, 0.79, "interior", 0.04, 3))
rb_ = box("benchback", -0.98, -0.86, -0.76, 0.76, 0.78, 1.38, "interior", 0.04, 3)
rot_obj(rb_, ry=math.radians(-10), pivot=(-0.90, 0, 0.78)); interior.append(rb_)
sw = cyl("steer", 0.66, 0.40, 1.14, 0.19, 0.035, "interior", axis="X", verts=40)
boolean(sw, cyl("sw_in", 0.66, 0.40, 1.14, 0.16, 0.2, "interior", axis="X", verts=40))
hub = cyl("swhub", 0.68, 0.40, 1.14, 0.06, 0.05, "interior", axis="X", verts=24)
column = cyl("swcol", 0.80, 0.40, 1.10, 0.04, 0.26, "interior", axis="X", verts=16)
for o in (sw, hub, column):
    rot_obj(o, ry=math.radians(24), pivot=(0.66, 0.40, 1.14)); interior.append(o)
interior.append(box("spokeh", 0.655, 0.67, 0.24, 0.56, 1.13, 1.15, "interior"))

# =============================================================== underbody (frame, axles, tank, spare, exhaust)
under = []
for s in (1, -1):
    under.append(box("rail", -2.55, 2.45, s * 0.42, s * 0.50, 0.40, 0.56, "under", 0.01))
for x in (-2.4, -1.6, -0.6, 0.6, 1.4, 2.35):
    under.append(box("xm", x - 0.04, x + 0.04, -0.46, 0.46, 0.42, 0.52, "under"))
under.append(cyl("axle", RA, 0, WR, 0.048, 1.46, "under", axis="Y", verts=20))
diff = cyl("diff", RA + 0.02, -0.06, WR, 0.15, 0.22, "under", axis="X", verts=28, bev=0.03)
under.append(diff)
under.append(cyl("dshaft", -0.30, -0.03, 0.46, 0.035, 2.10, "under", axis="X", verts=16))
for s in (1, -1):
    under.append(box("leaf", RA - 0.65, RA + 0.65, s * 0.47, s * 0.54, 0.30, 0.37, "under", 0.01))
    under.append(cyl("cv", FA, s * 0.42, WR, 0.03, 0.70, "under", axis="Y", verts=16))
    arm = box("larm", FA - 0.25, FA + 0.08, s * 0.35, s * 0.72, 0.30, 0.34, "under", 0.01)
    under.append(arm)
under.append(cyl("fdiff", FA - 0.05, 0.05, WR + 0.02, 0.11, 0.26, "under", axis="Y", verts=24, bev=0.02))
under.append(box("tank", -0.95, -0.10, -0.72, -0.25, 0.40, 0.62, "under", 0.03))
spare = cyl("spare", -2.20, 0, 0.47, 0.37, 0.24, "tire", axis="Z", verts=48, bev=0.06, seg=3)
under.append(spare)
under.append(cyl("spare_rim", -2.20, 0, 0.475, 0.21, 0.245, "rim_dark", axis="Z", verts=32))
ex = cyl("exhaust", -1.0, -0.56, 0.42, 0.035, 3.0, "engine", axis="X", verts=16)
under.append(ex)
under.append(cyl("muffler", -0.55, -0.40, 0.44, 0.11, 0.55, "engine", axis="X", verts=24))
under.append(cyl("tip", -2.55, -0.56, 0.42, 0.045, 0.12, "chrome", axis="X", verts=20))

# front wheel arches: lip + liner
body_bits = [arch_lip(FA, s) for s in (1, -1)] + [wheel_liner(FA, s) for s in (1, -1)]

# =============================================================== bed
bed_sides = []
for s in (1, -1):
    xs = list(np.linspace(-2.632, -1.075, 90))
    sh = side_loft("bedside", xs, "bed")
    if s < 0: flip_side(sh)
    solidify(sh, 0.004)
    # end caps (rear pillar + front edge): fill between skin and inner wall
    for xc, t in ((-2.632, 0.004), (-1.075, -0.004)):
        sec = side_section(xc, "bed")
        poly = [(s * y, z) for y, z in sec]
        cap = prism("cap", poly, "X", min(xc, xc + t), max(xc, xc + t), "paint")
        sh = join("bedside", [sh, cap])
    boolean(sh, arch_cutter_obj(RA, s))
    # taillight pocket
    y0, y1 = (0.70, 1.2) if s > 0 else (-1.2, -0.70)
    boolean(sh, prism("tlcut", [(-2.556, 0.935), (-2.75, 0.935), (-2.75, 1.283), (-2.556, 1.283)], "Y", y0, y1))
    # black rail caps and black composite inner bed
    def bedmat(c, n, s=s):
        if c.z > 1.27 and abs(c.y) < 0.905 and n.z > 0.5: return "trim"
        if abs(c.y) < 0.80 and n.y * s < -0.5: return "trim"
        if abs(c.y) < 0.80 and c.z > 1.24: return "trim"
        return None
    mats_by(sh, bedmat)
    bed_sides.append(sh)
    bed_sides.append(arch_lip(RA, s))
    bed_sides.append(wheel_liner(RA, s))
    # inner wheel housing
    pts = []
    for k in range(25):
        a = math.pi * k / 24
        pts.append((RA + 0.47 * math.cos(a), max(0.845, 0.60 + 0.47 * math.sin(a))))
    bed_sides.append(prism("housing", pts, "Y", min(s * 0.56, s * 0.787), max(s * 0.56, s * 0.787), "trim"))

# ribbed bed floor
rows = []
ys = np.linspace(-0.786, 0.786, 121)
for x in np.linspace(-2.628, -1.08, 3):
    rows.append([(x, y, 0.845 + 0.010 * smoothstep(0.35, 0.65, 0.5 + 0.5 * math.cos(y / 0.786 * math.pi * 6.5))) for y in ys])
floor = grid("bedfloor", np.array(rows), "trim", inside=(-1.8, 0, 0.0))
solidify(floor, 0.04)
bed_front = box("bedfront", -1.105, -1.075, -0.786, 0.786, 0.845, 1.300, "trim")
bed_under = box("bedunder", -2.62, -1.08, -0.80, 0.80, 0.60, 0.805, "under")
bed_obj = join("bed", bed_sides + [floor, bed_front, bed_under])

# =============================================================== tailgate
rows = []
TG_Y, TG_Z0, TG_Z1 = 0.783, 0.628, 1.292
for z in np.linspace(TG_Z0, TG_Z1, 40):
    t = (z - TG_Z0) / (TG_Z1 - TG_Z0)
    row = []
    for y in np.linspace(-TG_Y, TG_Y, 60):
        x = -2.634 - 0.010 * math.sin(math.pi * t) - 0.007 * (1 - (y / TG_Y) ** 2)
        if t > 0.94: x -= 0.010 * (t - 0.94) / 0.06          # little spoiler lip on top
        row.append((x, y, z))
    rows.append(row)
tg = grid("tg", np.array(rows), "paint", inside=(0, 0, 0.95))
solidify(tg, 0.05)
tg_handle = box("tghandle", -2.662, -2.640, -0.13, 0.13, 1.195, 1.245, "trim", 0.006)
tg_lip = box("tgcap", -2.655, -2.585, -TG_Y, TG_Y, 1.288, 1.300, "trim", 0.004)
tailgate_obj = join("tailgate", [tg, tg_handle, tg_lip])

# =============================================================== side doors: assemble
def door_bits(key, s):
    x_hi = {"f": 1.12, "r": 0.06}[key[0]]
    x_lo = {"f": 0.13, "r": -0.84}[key[0]]
    yy = sorted((s * 0.76, s * 0.80))
    panel = box("dpanel", x_lo, x_hi, yy[0], yy[1], 0.60, 1.27, "interior", 0.02)
    hx = {"f": 0.20, "r": -0.70}[key[0]]
    hy = sorted((s * (half_w(hx) - 0.001), s * (half_w(hx) + 0.016)))
    handle = box("handle", hx, hx + 0.17, hy[0], hy[1], 1.115, 1.150, "paint", 0.007, 3)
    ry = sorted((s * (half_w(hx) - 0.012), s * (half_w(hx) + 0.002)))
    recess = box("recess", hx + 0.01, hx + 0.16, ry[0], ry[1], 1.105, 1.162, "trim", 0.006)
    frame, glass = door_upper[key]
    # door glass a few mm inboard of its frame
    for v in glass.data.vertices:
        v.co.y -= s * 0.006
    return [panel, handle, recess, frame, glass]

doors = {}
for key, lower in door_lower.items():
    s = 1 if key[1] == "l" else -1
    doors[key] = join("door_" + key, [lower] + door_bits(key, s))

# =============================================================== mirrors
def mirror(s):
    rows = []
    xc, zc = 1.005, 1.43
    for k in range(20):
        v = k / 19
        y = 0.93 + 0.255 * v
        sc_ = 1.0 - 0.30 * smoothstep(0.78, 1.0, v) ** 1.4
        hx, hz = 0.050 * sc_, (0.090 + 0.016 * v) * sc_
        ring = []
        for m in range(36):
            a = 2 * math.pi * m / 36
            c, s_ = math.cos(a), math.sin(a)
            ex = 3.6
            px = math.copysign(abs(c) ** (2 / ex), c) * hx
            pz = math.copysign(abs(s_) ** (2 / ex), s_) * hz
            if px > 0: px *= 1.45                     # rounded front, flat back (glass side)
            ring.append((xc + px, s * y, zc + pz + 0.018 * v))
        rows.append(ring)
    head = grid("mhead", np.array(rows), "paint", close_v=True, inside=(xc, s * 1.05, zc))
    bm = bmesh.new()
    vs = [bm.verts.new(tuple(p)) for p in rows[-1]]
    bm.faces.new(vs)
    capo = mesh_from_bm("mcap", bm, "paint")
    if (Vector(rows[-1][0]) - Vector(rows[-2][0])).dot(capo.data.polygons[0].normal) < 0: capo.data.flip_normals()
    head = join("mhead", [head, capo])
    mats_by(head, lambda c, n: "trim" if c.z < zc - 0.035 else None)
    yy = sorted((s * 0.945, s * 1.165))
    glass = box("mglass", xc - 0.054, xc - 0.046, yy[0], yy[1], zc - 0.074, zc + 0.092, "chrome", 0.012)
    by = sorted((s * 0.83, s * 0.94))
    base = prism("msail", [(0.955, 1.305), (1.14, 1.305), (0.975, 1.43)], "Y", by[0], by[1], "trim")
    bevel(base, 0.01, 2)
    ay = sorted((s * 0.90, s * 0.99))
    arm = box("marm", 0.965, 1.055, ay[0], ay[1], 1.335, 1.375, "trim", 0.012)
    return join("mirror_" + ("l" if s > 0 else "r"), [head, glass, base, arm])
mirrors = [mirror(1), mirror(-1)]

# =============================================================== power running boards (retracted under the rocker)
RB_X0, RB_X1 = -0.86, 1.10
RB_PIVOT_Y, RB_PIVOT_Z = 0.60, 0.50
def running_board(s):
    # extruded aluminium step: ribbed tread on top, rounded nose outboard
    prof = [(0.0, 0.0), (0.150, 0.0), (0.168, 0.012), (0.170, 0.030), (0.160, 0.040)]
    k = 0.150
    while k > 0.012:
        prof += [(k, 0.040), (k - 0.006, 0.040), (k - 0.008, 0.034), (k - 0.014, 0.034)]
        k -= 0.016
    prof += [(0.004, 0.040), (0.0, 0.034)]
    yb, zb = 0.705, 0.405                       # inner edge of the board (retracted)
    poly = [(s * (yb + u), zb + v) for u, v in prof]
    if s < 0: poly = list(reversed(poly))
    board = prism("rboard", poly, "X", RB_X0, RB_X1, "step")
    bits = [board]
    for xe, d in ((RB_X0 - 0.03, 0.03), (RB_X1, 0.03)):
        cap = box("rcap", xe, xe + d, s * (yb - 0.004), s * (yb + 0.174), zb - 0.003, zb + 0.044, "rubber", 0.01, 2)
        bits.append(cap)
    for xa in (-0.55, 0.78):
        # hinged arm: frame bracket -> board, plus the motor/bracket block on the frame side
        L = math.hypot(yb + 0.03 - RB_PIVOT_Y, RB_PIVOT_Z - zb - 0.024)
        arm = box("rarm", xa - 0.025, xa + 0.025, s * RB_PIVOT_Y, s * (RB_PIVOT_Y + L), RB_PIVOT_Z - 0.012, RB_PIVOT_Z + 0.012, "step", 0.006)
        rot_obj(arm, rx=-s * math.atan2(RB_PIVOT_Z - zb - 0.024, yb + 0.03 - RB_PIVOT_Y), pivot=(xa, s * RB_PIVOT_Y, RB_PIVOT_Z))
        bits.append(arm)
        bits.append(box("rbrk", xa - 0.05, xa + 0.05, s * (RB_PIVOT_Y - 0.04), s * (RB_PIVOT_Y + 0.02), RB_PIVOT_Z - 0.04, RB_PIVOT_Z + 0.05, "step", 0.008))
        bits.append(cyl("rpin", xa, s * RB_PIVOT_Y, RB_PIVOT_Z, 0.012, 0.11, "alu", axis="X", verts=12))
    ob = join("running_board_" + ("l" if s > 0 else "r"), bits)
    for p in ob.data.polygons: p.use_smooth = False
    return ob
running_boards = [running_board(1), running_board(-1)]

# =============================================================== hard tri-fold tonneau cover (three flat aluminium panels)
TX0, TX1, TY = -2.600, -1.110, 0.800
ztop = belt_z(-1.8) + 0.012
tc_bits = []
edges = np.linspace(TX0, TX1, 4)
for k in range(3):
    x0, x1 = edges[k] + (0.004 if k else 0), edges[k + 1] - (0.004 if k < 2 else 0)
    rows = []
    for x in np.linspace(x0, x1, 8):
        row = []
        for y in np.linspace(-TY, TY, 40):
            t = abs(y) / TY
            z = ztop + 0.010 * (1 - t ** 6)
            if t > 0.985: z -= 0.008 * (t - 0.985) / 0.015
            row.append((x, y, z))
        rows.append(row)
    pnl = grid("tpanel", np.array(rows), "vinyl", inside=(-1.8, 0, 0.8))
    solidify(pnl, 0.022)
    bevel(pnl, 0.004, 2, angle=50)
    tc_bits.append(pnl)
    # stiffening ribs pressed into each panel
    for yr in (-0.42, 0.0, 0.42):
        tc_bits.append(box("trib", x0 + 0.03, x1 - 0.03, yr - 0.012, yr + 0.012, ztop + 0.009, ztop + 0.014, "vinyl", 0.003))
for xh in edges[1:3]:
    tc_bits.append(cyl("thinge", xh, 0, ztop + 0.006, 0.007, 1.56, "step", axis="Y", verts=12))
for s in (1, -1):
    tc_bits.append(box("trail", TX0, TX1, s * 0.775, s * 0.812, ztop - 0.020, ztop - 0.002, "step", 0.004))
tc_bits.append(box("tlatch", TX0 + 0.01, TX0 + 0.05, -0.05, 0.05, ztop + 0.006, ztop + 0.016, "step", 0.003))
tonneau_obj = join("tonneau_cover", tc_bits)

# =============================================================== front corner plan path (bumper, headlights)
FC_X, FC_A, FC_B, FC_N = 2.31, 0.395, 0.94, 2.7
def fc_point(th):
    c, s_ = math.cos(th), math.sin(th)
    x = FC_X + FC_A * c ** (2 / FC_N)
    y = FC_B * s_ ** (2 / FC_N)
    # outward normal of the superellipse
    nx = c ** (FC_N - 1) / FC_A ** FC_N if c > 1e-9 else 0.0
    ny = s_ ** (FC_N - 1) / FC_B ** FC_N if s_ > 1e-9 else 0.0
    nx = (c ** (2 - 2 / FC_N)) / FC_A if c > 1e-9 else 0.0
    ny = (s_ ** (2 - 2 / FC_N)) / FC_B if s_ > 1e-9 else 0.0
    L = math.hypot(nx, ny) or 1
    return x, y, nx / L, ny / L

def th_for_y(y):
    return math.asin(min(1.0, (y / FC_B) ** (FC_N / 2)))

TH_A = th_for_y(0.585)        # headlight inner end
def hl_s(th): return (th - TH_A) / (math.pi / 2 - TH_A)
def hl_bot(s): return 1.006 + 0.168 * max(0.0, s) ** 1.5
def hl_top(s): return 1.170 + 0.044 * s
GB = 0.745
def grille_half(z): return 0.45 + 0.135 * (z - GB) / 0.42

def bumper_top(th):
    x, y, nx, ny = fc_point(th)
    t = GB
    if y > 0.415: t = GB + (y - 0.415) / 0.135 * 0.42
    t = min(t, hl_bot(max(0.0, hl_s(th))) - 0.006)
    return t

def th_samples(n):
    # denser around the corner
    return [math.pi / 2 * (k / (n - 1)) ** 0.9 for k in range(n)]

# =============================================================== front bumper
rows = []
for th in th_samples(64):
    x, y, nx, ny = fc_point(th)
    top = bumper_top(th)
    lo = [(-0.20, 0.395), (-0.035, 0.40), (-0.012, 0.425), (-0.014, 0.50), (-0.018, 0.572), (-0.034, 0.594), (-0.006, 0.616)]
    zm = top - 0.05
    lean = 0.035 * smoothstep(0.5, 0.85, y)          # corners lean in toward the headlight
    mid = [(0.004, 0.618 + (zm - 0.618) * 0.33), (0.002 - lean * 0.4, 0.618 + (zm - 0.618) * 0.7)]
    prof = lo + mid + [(-0.008 - lean, zm), (-0.016 - lean, top - 0.012), (-0.03 - lean, top), (-0.11, top + 0.002)]
    rows.append([(x + nx * d, y + ny * d, z) for d, z in prof])
half = np.array(rows)
full = np.concatenate([half[::-1] * np.array([1, -1, 1]), half[1:]], axis=0)
fb = grid("fbumper", full, "paint", inside=(2.0, 0, 0.6))
solidify(fb, 0.004)
def fbmat(c, n):
    if c.z < 0.598:
        if abs(c.y) < 0.52 and 0.455 < c.z < 0.580 and n.x > 0.3: return "under"   # lower intake
        return "trim"
    return None
mats_by(fb, fbmat)
fb_bits = [fb]
# lower intake bar + fog lights + skid plate
fb_bits.append(box("intakebar", 2.66, 2.685, -0.48, 0.48, 0.505, 0.525, "trim", 0.005))
for s in (1, -1):
    th = th_for_y(0.70)
    x, y, nx, ny = fc_point(th)
    ang = math.atan2(ny, nx)
    for nm, r, d, dep, mat in (("fogbez", 0.058, -0.005, 0.03, "gloss"), ("fog", 0.036, 0.004, 0.012, "lamp_glass"), ("fogbulb", 0.022, -0.012, 0.02, "chrome")):
        o = cyl(nm, 0, 0, 0, r, dep, mat, axis="X", verts=32, bev=0.004 if nm == "fogbez" else 0)
        o.data.transform(Matrix.Translation((x + nx * d, s * (y + ny * d), 0.525)) @ Matrix.Rotation(s * ang, 4, "Z"))
        fb_bits.append(o)
skid = box("skid", 2.50, 2.69, -0.42, 0.42, 0.385, 0.415, "skid", 0.008)
fb_bits.append(skid)
bumper_front_obj = join("bumper_front", fb_bits)

# =============================================================== grille (rounded trapezoid, hex mesh, no badge)
def grille_x(y, z): return 2.652 + 0.022 * (1.165 - z) / 0.42 - 0.075 * (y / 0.6) ** 2

def trap(margin, n=10, r=0.035):
    z0, z1 = GB + margin, 1.165 - margin
    pts = []
    corners = [(grille_half(z0) - margin, z0), (grille_half(z1) - margin, z1), (-(grille_half(z1) - margin), z1), (-(grille_half(z0) - margin), z0)]
    return corners

def bend_to_grille(ob, dx=0.0):
    for v in ob.data.vertices:
        v.co.x += grille_x(v.co.y, v.co.z) - 2.652 + dx

g_outer = prism("gouter", trap(-0.035), "X", 2.635, 2.672, "chrome")
boolean(g_outer, prism("ginner", trap(0.0), "X", 2.6, 2.70))
bevel(g_outer, 0.008, 3)
for p in g_outer.data.polygons: p.use_smooth = True
# subdivide long faces so the bend follows the curve
m = g_outer.modifiers.new("rm", "REMESH") if False else None
bm = bmesh.new(); bm.from_mesh(g_outer.data)
bmesh.ops.subdivide_edges(bm, edges=[e for e in bm.edges if e.calc_length() > 0.05], cuts=8, use_grid_fill=True)
bm.to_mesh(g_outer.data); bm.free()
bend_to_grille(g_outer)
backing = prism("gback", trap(0.0), "X", 2.585, 2.60, "under")
bend_to_grille(backing, -0.03)
cells = []
CW, CH = 0.066, 0.046
row_i = 0
z = GB + 0.03
while z < 1.165 - 0.03:
    off = (CW / 2) if row_i % 2 else 0
    y = -0.70 + off
    while y < 0.70:
        hw, hh = CW * 0.5, CH * 0.5
        hexo = [(y - hw, z), (y - hw * 0.55, z - hh), (y + hw * 0.55, z - hh), (y + hw, z), (y + hw * 0.55, z + hh), (y - hw * 0.55, z + hh)]
        if all(abs(py) < grille_half(pz) - 0.012 and GB + 0.006 < pz < 1.16 for py, pz in hexo):
            c = prism("cell", hexo, "X", 2.625, 2.650, "grille_hex")
            boolean(c, prism("cin", offset_poly(hexo, -0.0075), "X", 2.6, 2.7))
            for v in c.data.vertices:
                v.co.x += grille_x(y, z) - 2.652
            cells.append(c)
        y += CW
    z += CH * 0.98
    row_i += 1
grille_obj = join("grille", [g_outer, backing] + cells)
mats_by(grille_obj, lambda c, n: None)

# =============================================================== headlights
def headlight(s):
    rows_l, rows_h = [], []
    N = 34
    for k in range(N):
        sv = k / (N - 1)
        th = TH_A + sv * (math.pi / 2 - TH_A)
        x, y, nx, ny = fc_point(th)
        x -= nx * 0.028; y -= ny * 0.028
        b, t = hl_bot(sv), hl_top(sv)
        h = t - b
        depth_top = max(0.02, min(0.24, (y - hood_w(x)) / max(0.35, ny))) if x <= 2.64 else 0.02
        lens = [(-0.05, b + 0.004), (-0.006, b + 0.002), (0.004, b + 0.25 * h), (0.006, b + 0.6 * h), (-0.006, t - 0.006), (-depth_top * 0.5, t + 0.003), (-depth_top, t + 0.004)]
        rows_l.append([(x + nx * d, s * (y + ny * d), z) for d, z in lens])
        hous = [(-0.045, b + 0.006), (-0.07, b + 0.02), (-0.075, t - 0.01), (-0.06, t - 0.002)]
        rows_h.append([(x + nx * d, s * (y + ny * d), z) for d, z in hous])
    lens = grid("lens", np.array(rows_l), "lamp_glass", inside=(2.2, s * 0.5, 1.0))
    solidify(lens, 0.003)
    hous = grid("hous", np.array(rows_h), "housing", inside=(2.2, s * 0.5, 1.0))
    solidify(hous, 0.003)
    bits = [lens, hous]
    # projector + reflector + DRL light guide + amber strip
    for sv, r, mat in ((0.22, 0.040, "chrome"), (0.45, 0.034, "chrome")):
        th = TH_A + sv * (math.pi / 2 - TH_A)
        x, y, nx, ny = fc_point(th)
        cz = (hl_bot(sv) + hl_top(sv)) / 2 + 0.005
        ang = math.atan2(ny, nx)
        bowl = cyl("bowl", 0, 0, 0, r, 0.03, mat, axis="X", verts=32, r2=r * 0.55)
        lensb = cyl("proj", 0, 0, 0, r * 0.62, 0.02, "lamp_glass", axis="X", verts=24)
        ring = cyl("projring", 0, 0, 0, r * 0.75, 0.012, "housing", axis="X", verts=24)
        for o, d in ((bowl, -0.055), (ring, -0.035), (lensb, -0.03)):
            o.data.transform(Matrix.Translation((x + nx * d, s * (y + ny * d), cz)) @ Matrix.Rotation(s * ang, 4, "Z"))
            bits.append(o)
    drl = []
    for k in range(40):
        sv = 0.03 + 0.80 * k / 39
        th = TH_A + sv * (math.pi / 2 - TH_A)
        x, y, nx, ny = fc_point(th)
        drl.append((x - nx * 0.036, s * (y - ny * 0.036), hl_bot(sv) + 0.016))
    # light guide as a thin flat strip
    rows_d = [[(p[0], p[1], p[2] - 0.006), (p[0], p[1], p[2] + 0.006)] for p in drl]
    d = grid("drl", np.array(rows_d), "lamp", inside=(2.0, s * 0.3, 1.1))
    solidify(d, 0.004, 0)
    bits.append(d)
    rows_a = []
    for k in range(10):
        sv = 0.80 + 0.17 * k / 9
        th = TH_A + sv * (math.pi / 2 - TH_A)
        x, y, nx, ny = fc_point(th)
        zc = (hl_bot(sv) + hl_top(sv)) / 2
        hh = (hl_top(sv) - hl_bot(sv)) * 0.32
        rows_a.append([(x - nx * 0.04, s * (y - ny * 0.04), zc - hh), (x - nx * 0.04, s * (y - ny * 0.04), zc + hh)])
    a = grid("amber", np.array(rows_a), "amber", inside=(2.0, s * 0.3, 1.1))
    solidify(a, 0.004, 0)
    bits.append(a)
    return join("headlight_" + ("l" if s > 0 else "r"), bits)
headlights = [headlight(1), headlight(-1)]

# =============================================================== taillights
bed_rear_sec = side_section(-2.60, "bed")
def bed_side_y(z):
    pts = [(yy, zz) for yy, zz in bed_rear_sec[:len(bed_rear_sec) - 6]]
    best = min(pts, key=lambda p: abs(p[1] - z))
    return best[0]

def taillight(s):
    rows = []
    zs = np.linspace(0.938, 1.280, 26)
    for z in zs:
        ys = bed_side_y(z)
        path = []
        # rear face from inner edge to the corner, then wrap forward along the side
        for k in range(10):
            path.append((-2.639, 0.792 + (ys - 0.035 - 0.792) * k / 9))
        for k in range(1, 7):
            a = math.pi / 2 * k / 6
            path.append((-2.639 + 0.035 * (1 - math.cos(a)), ys - 0.035 + 0.035 * math.sin(a) + 0.003))
        for k in range(1, 6):
            path.append((-2.604 + (0.046 if z > 1.0 else 0.03) * k / 5, ys + 0.003))
        rows.append([(x, s * y, z) for x, y in path])
    lens = grid("tlens", np.array(rows), "lamp_red", inside=(-2.5, s * 0.75, 1.1))
    solidify(lens, 0.006)
    # inner details: clear reverse section + lit LED bars, seen through the lens
    def tlmat(c, n):
        if 1.07 < c.z < 1.135: return "lamp_glass"
        return None
    mats_by(lens, tlmat)
    yy = sorted((s * 0.80, s * 0.90))
    bits = [lens]
    bits.append(box("tlback", -2.60, -2.585, yy[0], yy[1], 0.94, 1.275, "chrome", 0.004))
    for z0 in (0.98, 1.17, 1.22):
        bits.append(box("tlbar", -2.636, -2.628, yy[0] + 0.012, yy[1] - 0.012, z0, z0 + 0.018, "lamp_redlit", 0.003))
    bits.append(box("tlrev", -2.632, -2.626, yy[0] + 0.015, yy[1] - 0.015, 1.078, 1.128, "lamp_glass", 0.003))
    return join("taillight_" + ("l" if s > 0 else "r"), bits)
taillights = [taillight(1), taillight(-1)]

# =============================================================== rear bumper (chrome, black step pad, hitch)
rows = []
RB_N = 6.0
for k in range(48):
    th = math.pi / 2 * (k / 47)
    c, s_ = math.cos(th), math.sin(th)
    x = -2.50 - 0.175 * c ** (2 / RB_N)
    y = 0.935 * s_ ** (2 / RB_N)
    nx = -(c ** (2 - 2 / RB_N)) / 0.175 if c > 1e-9 else 0.0
    ny = (s_ ** (2 - 2 / RB_N)) / 0.935 if s_ > 1e-9 else 0.0
    L = math.hypot(nx, ny) or 1; nx /= L; ny /= L
    prof = [(-0.14, 0.432), (-0.02, 0.428), (0.0, 0.452), (0.010, 0.50), (0.014, 0.56), (0.004, 0.598), (-0.02, 0.612), (-0.16, 0.614)]
    rows.append([(x + nx * d, y + ny * d, z) for d, z in prof])
half = np.array(rows)
full = np.concatenate([half[::-1] * np.array([1, -1, 1]), half[1:]], axis=0)
rbm = grid("rbumper", full, "chrome", inside=(-2.3, 0, 0.5))
solidify(rbm, 0.004)
mats_by(rbm, lambda c, n: "trim" if (n.z > 0.6 and abs(c.y) < 0.40) or c.z < 0.44 else None)
pad = box("rpad", -2.66, -2.52, -0.40, 0.40, 0.606, 0.622, "trim", 0.004)
hitch = box("hitch", -2.74, -2.40, -0.035, 0.035, 0.40, 0.47, "under", 0.005)
plate = box("plate", -2.667, -2.660, -0.155, 0.155, 0.47, 0.575, "under", 0.004)
bumper_rear_obj = join("bumper_rear", [rbm, pad, hitch, plate])

# =============================================================== engine (V6, transmission behind)
eng = []
eng.append(box("block", 1.48, 2.05, -0.22, 0.22, 0.62, 0.90, "engine", 0.025, 3))
eng.append(box("pan", 1.52, 2.00, -0.17, 0.17, 0.52, 0.63, "engine", 0.02))
for s in (1, -1):
    hd = box("head", 1.46, 2.07, -0.09, 0.09, 0.0, 0.10, "alu", 0.015)
    vc = box("vcover", 1.47, 2.06, -0.085, 0.085, 0.10, 0.16, "trim", 0.03, 3)
    ribs = [box("rib", x, x + 0.012, -0.06, 0.06, 0.155, 0.17, "trim", 0.003) for x in np.linspace(1.56, 1.96, 6)]
    bank = join("bank", [hd, vc] + ribs)
    rot_obj(bank, rx=s * math.radians(32))
    bank.data.transform(Matrix.Translation((0, s * 0.16, 0.90)))
    eng.append(bank)
    eng.append(cyl("exman", 1.76, s * 0.25, 0.86, 0.035, 0.52, "alu", axis="X", verts=16))
eng.append(box("plenum", 1.56, 2.00, -0.13, 0.13, 1.02, 1.15, "alu", 0.05, 4))
eng.append(box("cover", 1.62, 1.94, -0.10, 0.10, 1.13, 1.165, "trim", 0.015, 3))
eng.append(cyl("tbody", 2.05, 0.05, 1.08, 0.045, 0.12, "alu", axis="X", verts=24))
eng.append(cyl("intake", 2.22, 0.30, 1.06, 0.05, 0.40, "trim", axis="Y", verts=24))
eng.append(box("airbox", 2.10, 2.40, 0.42, 0.70, 0.93, 1.12, "trim", 0.03, 3))
eng.append(box("tcover", 2.05, 2.10, -0.20, 0.20, 0.66, 1.02, "alu", 0.02))
for y, z, r in ((0.0, 0.70, 0.085), (0.15, 0.94, 0.06), (-0.15, 0.95, 0.06), (0.20, 0.76, 0.05), (-0.22, 0.74, 0.055)):
    eng.append(cyl("pulley", 2.13, y, z, r, 0.035, "alu", axis="X", verts=32, bev=0.004))
belt_pts = [(0.0, 0.70, 0.085), (0.20, 0.76, 0.05), (0.15, 0.94, 0.06), (-0.15, 0.95, 0.06), (-0.22, 0.74, 0.055)]
eng.append(cyl("alt", 2.0, 0.27, 0.95, 0.07, 0.14, "alu", axis="X", verts=24, bev=0.01))
eng.append(cyl("ac", 2.0, -0.28, 0.72, 0.065, 0.16, "alu", axis="X", verts=24, bev=0.01))
eng.append(cyl("bell", 1.30, 0, 0.72, 0.24, 0.36, "alu", axis="X", verts=36, r2=0.17))
eng.append(cyl("trans", 0.95, 0, 0.66, 0.17, 0.50, "engine", axis="X", verts=32, r2=0.11))
eng.append(box("res", 2.25, 2.38, -0.55, -0.40, 0.95, 1.10, "skid", 0.02))
engine_obj = join("engine", eng)

# =============================================================== wheels (one shared mesh, 4 objects)
def tire_mesh():
    prof = [(0.206, 0.104), (0.214, 0.116), (0.232, 0.127), (0.262, 0.134), (0.30, 0.136), (0.335, 0.133),
            (0.356, 0.128), (0.372, 0.122), (0.384, 0.114), (0.390, 0.105)]
    tread_a = list(np.linspace(0.100, -0.100, 41))
    P = prof + [(0.392, a) for a in tread_a] + [(r, -a) for r, a in reversed(prof)]
    NS = 240
    rows = []
    for i in range(NS):
        phi = 2 * math.pi * i / NS
        row = []
        for j, (r, a) in enumerate(P):
            rr = r
            # all-terrain tread: staggered blocks, zig-zag centre groove, shoulder lugs
            if r > 0.37:
                pitch = (phi / (2 * math.pi)) * 40
                cell = pitch % 1.0
                side = 1 if a > 0 else -1
                aa = abs(a)
                stag = 0.5 if side > 0 else 0.0
                c2 = (pitch + stag) % 1.0
                groove = False
                if aa < 0.012 + 0.008 * (1 if c2 < 0.5 else -1): groove = True            # centre zig-zag
                if 0.012 < aa < 0.06 and abs(c2 - 0.5) < 0.09: groove = True                # lateral sipes
                if 0.06 < aa < 0.072: groove = True                                         # shoulder channel
                if aa > 0.072 and abs(((pitch + stag + 0.25) % 1.0) - 0.5) < 0.16: groove = True  # lug gaps
                if groove: rr -= 0.011 if r > 0.388 else 0.006
            if 0.30 < r < 0.312: rr += 0.0015 * (1 if abs(a) > 0.13 else 0)
            row.append((rr * math.sin(phi), a, rr * math.cos(phi)))
        rows.append(row)
    ob = grid("tire", np.array(rows), "tire", close_u=True, inside=(0, 0, 0))
    # sharp groove walls
    for p in ob.data.polygons: p.use_smooth = True
    m = ob.modifiers.new("es", "EDGE_SPLIT"); m.split_angle = math.radians(50)
    apply_mods(ob)
    return ob

def rim_parts():
    out = []
    # barrel + outer lip (revolved)
    prof = [(0.214, 0.112), (0.216, 0.102), (0.203, 0.094), (0.192, 0.080), (0.190, -0.06), (0.198, -0.092), (0.206, -0.104)]
    rows = []
    for i in range(96):
        phi = 2 * math.pi * i / 96
        rows.append([(r * math.sin(phi), a, r * math.cos(phi)) for r, a in prof])
    barrel = grid("barrel", np.array(rows), "rim_dark", close_u=True, inside=(0, 0.3, 0))
    solidify(barrel, 0.006, 0)
    out.append(barrel)
    lip = cyl("lip", 0, 0.103, 0, 0.214, 0.014, "rim", axis="Y", verts=96)
    boolean(lip, cyl("lipin", 0, 0.103, 0, 0.196, 0.1, "rim", axis="Y", verts=96))
    out.append(lip)
    # 6 split spokes, machined faces + dark pockets
    for k in range(6):
        for side in (-1, 1):
            a0 = math.radians(k * 60) + side * math.radians(6.5)
            pts = []
            for r, wdt in ((0.075, 0.020), (0.13, 0.016), (0.19, 0.020), (0.197, 0.024)):
                pass
            q = [(0.072, -0.016), (0.196, -0.010 - 0.004), (0.196, 0.017 + 0.004), (0.072, 0.012)]
            if side < 0: q = [(r, -w) for r, w in reversed(q)]
            P2 = [(r * math.sin(a0) + w * math.cos(a0), r * math.cos(a0) - w * math.sin(a0)) for r, w in q]
            sp = prism("spoke", [(x, z) for x, z in P2], "Y", 0.055, 0.092, "rim")
            bevel(sp, 0.004, 2)
            # dish: spokes lean outward toward the lip
            for v in sp.data.vertices:
                r = math.hypot(v.co.x, v.co.z)
                v.co.y += 0.018 * smoothstep(0.08, 0.19, r)
            mats_by(sp, lambda c, n: "rim" if n.y > 0.7 else "rim_dark")
            out.append(sp)
    hub = cyl("hub", 0, 0.072, 0, 0.085, 0.045, "rim_dark", axis="Y", verts=48, bev=0.01)
    out.append(hub)
    cap = cyl("cap", 0, 0.097, 0, 0.042, 0.012, "rim_dark", axis="Y", verts=32, bev=0.004)
    out.append(cap)
    for k in range(6):
        a = math.radians(k * 60 + 30)
        out.append(cyl("nut", 0.0698 * math.sin(a), 0.098, 0.0698 * math.cos(a), 0.011, 0.022, "chrome", axis="Y", verts=6, bev=0.002))
    rotor = cyl("rotor", 0, -0.005, 0, 0.165, 0.026, "engine_alu" if False else "alu", axis="Y", verts=64)
    boolean(rotor, cyl("rotorin", 0, -0.005, 0, 0.09, 0.1, "alu", axis="Y", verts=32))
    out.append(rotor)
    cal = box("caliper", -0.07, 0.07, 0.005, 0.045, 0.10, 0.185, "rim_dark", 0.015, 3)
    rot_obj(cal, ry=math.radians(-35))
    out.append(cal)
    return out

wheel_src = join("wheel_src", [tire_mesh()] + rim_parts())
wheel_mesh = wheel_src.data
bpy.data.objects.remove(wheel_src, do_unlink=True)
wheel_mesh.name = "wheel"
wheels = []
for name, x, s in (("wheel_fl", FA, 1), ("wheel_fr", FA, -1), ("wheel_rl", RA, 1), ("wheel_rr", RA, -1)):
    ob = link(bpy.data.objects.new(name, wheel_mesh))
    ob.location = (x, s * WY, WR)
    ob.rotation_euler = (0, 0, 0 if s > 0 else math.pi)
    wheels.append(ob)

# =============================================================== assemble body_cab
body_parts = side_shells + [gh, ws_glass, frit, bk_glass, bk_frit, cowl, rad_support, radiator, firewall, cab_back,
                            cab_floor] + wipers + aprons + inner_walls + interior + under + body_bits
body_cab_obj = join("body_cab", body_parts)

PARTS = ["body_cab", "hood", "door_fl", "door_fr", "door_rl", "door_rr", "tailgate", "bed", "bumper_front", "bumper_rear",
         "grille", "headlight_l", "headlight_r", "taillight_l", "taillight_r", "mirror_l", "mirror_r",
         "wheel_fl", "wheel_fr", "wheel_rl", "wheel_rr", "engine", "running_board_l", "running_board_r", "tonneau_cover"]
for o in list(bpy.data.objects):
    if o.type == "MESH" and o.name not in PARTS:
        print("STRAY", o.name); bpy.data.objects.remove(o, do_unlink=True)
for n in PARTS:
    ob = bpy.data.objects.get(n)
    assert ob, n
    if n.startswith("running_board"):
        # origin on the arm pivot so the page can swing the board down and out
        s_ = 1 if n.endswith("l") else -1
        piv = Vector((0.12, s_ * RB_PIVOT_Y, RB_PIVOT_Z))
        ob.data.transform(Matrix.Translation(-piv)); ob.location = piv
    elif not n.startswith("wheel"):
        finish(ob)
tris = 0
for n in PARTS:
    ob = bpy.data.objects[n]
    t = sum(len(p.vertices) - 2 for p in ob.data.polygons)
    tris += t
    print("PART", n, t)
print("TRIS", tris)

# =============================================================== export (Draco-compressed GLB)
os.makedirs(os.path.dirname(OUT), exist_ok=True)
for o in bpy.data.objects: o.select_set(o.name in PARTS)
bpy.ops.export_scene.gltf(filepath=OUT, export_format="GLB", use_selection=True, export_apply=False, export_yup=True,
                          export_materials="EXPORT", export_normals=True, export_texcoords=False,
                          export_draco_mesh_compression_enable=True, export_draco_mesh_compression_level=7,
                          export_draco_position_quantization=14, export_draco_normal_quantization=10)
print("WROTE", OUT, os.path.getsize(OUT))

if "--render" in ARGS:
    PREVIEW_SHOTS = [("side", (0, 9, 0.9), 50, 6.2), ("q34", (4.6, 3.5, 1.05), 34, None, (0.5, 0, 0.85)),
                     ("r34", (-4.4, -3.9, 1.9), 30, None, (-0.6, 0, 0.85))]

    # ---- quick preview (appended temporarily while building)
    import bpy, math, os
    from mathutils import Vector
    sc = bpy.context.scene
    try: sc.render.engine = "BLENDER_EEVEE_NEXT"
    except TypeError:
        sc.render.engine = "BLENDER_EEVEE"
    w = bpy.data.worlds.new("w"); sc.world = w
    nt = w.node_tree
    env = nt.nodes.new("ShaderNodeTexEnvironment")
    env.image = bpy.data.images.load(os.path.join(os.path.dirname(bpy.app.binary_path), "5.2", "datafiles", "studiolights", "world", "courtyard.exr"))
    bg = next(n for n in nt.nodes if n.type == "BACKGROUND")
    nt.links.new(env.outputs[0], bg.inputs[0]); bg.inputs[1].default_value = 1.0
    bpy.ops.mesh.primitive_plane_add(size=40)
    fl = bpy.context.active_object
    fm = bpy.data.materials.new("floor"); fb = next(n for n in fm.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    fb.inputs["Base Color"].default_value = (0.25, 0.25, 0.25, 1); fb.inputs["Roughness"].default_value = 0.85
    fl.data.materials.append(fm)
    sun = bpy.data.objects.new("sun", bpy.data.lights.new("sun", "SUN")); sc.collection.objects.link(sun)
    sun.data.energy = 3.5; sun.rotation_euler = (math.radians(40), math.radians(10), math.radians(150))
    sun.data.angle = math.radians(3)
    cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam")); sc.collection.objects.link(cam); sc.camera = cam
    sc.render.resolution_x, sc.render.resolution_y = 1600, 900
    sc.view_settings.view_transform = "AgX"
    OUTD = os.path.join(ROOT, "research", "renders"); os.makedirs(OUTD, exist_ok=True)
    def shot(name, loc, target=(0, 0, 0.85), lens=50, ortho=None):
        cam.location = loc
        d = Vector(target) - Vector(loc)
        cam.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()
        cam.data.lens = lens
        if ortho:
            cam.data.type = "ORTHO"; cam.data.ortho_scale = ortho
        else:
            cam.data.type = "PERSP"
        sc.render.filepath = os.path.join(OUTD, name + ".png")
        bpy.ops.render.render(write_still=True)
    for nm, loc, lens, ortho, *rest in PREVIEW_SHOTS:
        shot(nm, loc, target=rest[0] if rest else (0, 0, 0.85), lens=lens, ortho=ortho)
