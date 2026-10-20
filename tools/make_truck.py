# Builds the Tacoma-style mid-size crew cab pickup used on /parts, as separate named meshes,
# and exports models/tacoma-style.glb. Our own geometry: no downloaded models, no badges.
#
#   "C:\Program Files\Blender Foundation\Blender 5.2\blender.exe" -b -P tools/make_truck.py
#
# Axes while building: X = forward, Y = driver side (left), Z = up, metres.
# The glTF exporter turns that into three.js axes: X forward, Y up, driver side = -Z.
# Mesh names are the contract with parts.html and data/parts.json. Keep them if you swap models.
import bpy, bmesh, math, os

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(os.path.dirname(HERE), "models", "tacoma-style.glb")

bpy.ops.wm.read_factory_settings(use_empty=True)

# ---------------------------------------------------------------- materials
# parts.html swaps these by name for tuned three.js materials; the values here are sane fallbacks.
def material(name, rgb, metallic=0.0, rough=0.5, alpha=1.0, emit=None):
    m = bpy.data.materials.new(name)
    b = next(n for n in m.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    b.inputs["Base Color"].default_value = (*rgb, 1)
    b.inputs["Metallic"].default_value = metallic
    b.inputs["Roughness"].default_value = rough
    if alpha < 1:
        b.inputs["Alpha"].default_value = alpha
    if emit:
        b.inputs["Emission Color"].default_value = (*emit, 1)
        b.inputs["Emission Strength"].default_value = 1.0
    return m

M = {
    "paint": material("paint", (0.20, 0.23, 0.16), 0.3, 0.35),
    "trim": material("trim_black", (0.03, 0.03, 0.03), 0.0, 0.6),
    "gloss": material("gloss_black", (0.01, 0.01, 0.01), 0.0, 0.15),
    "glass": material("glass", (0.05, 0.07, 0.08), 0.0, 0.05, alpha=0.55),
    "tire": material("tire", (0.02, 0.02, 0.02), 0.0, 0.9),
    "rim": material("rim", (0.35, 0.36, 0.37), 1.0, 0.3),
    "rim_dark": material("rim_dark", (0.05, 0.05, 0.05), 0.6, 0.45),
    "chrome": material("chrome", (0.8, 0.8, 0.8), 1.0, 0.12),
    "lamp": material("lamp_clear", (0.9, 0.92, 0.95), 0.0, 0.05, emit=(0.9, 0.95, 1.0)),
    "lamp_red": material("lamp_red", (0.6, 0.02, 0.02), 0.0, 0.1, emit=(0.6, 0.0, 0.0)),
    "lens": material("lamp_lens", (0.12, 0.13, 0.14), 0.6, 0.08),
    "engine": material("engine_metal", (0.25, 0.26, 0.27), 0.9, 0.4),
    "alu": material("engine_alu", (0.7, 0.7, 0.72), 1.0, 0.3),
    "under": material("underbody", (0.02, 0.02, 0.02), 0.0, 0.9),
}

coll = bpy.context.scene.collection

def new_obj(name, bm, mat):
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    coll.objects.link(ob)
    me.materials.append(M[mat])
    return ob

def prism(name, pts, axis, a0, a1, mat):
    """Extrude a 2D polygon along an axis. pts are (x,z) for axis Y, (y,z) for X, (x,y) for Z."""
    def p3(u, v, a):
        if axis == "Y": return (u, a, v)
        if axis == "X": return (a, u, v)
        return (u, v, a)
    bm = bmesh.new()
    v0 = [bm.verts.new(p3(u, v, a0)) for u, v in pts]
    v1 = [bm.verts.new(p3(u, v, a1)) for u, v in pts]
    bm.faces.new(v0)
    bm.faces.new(list(reversed(v1)))
    n = len(pts)
    for i in range(n):
        j = (i + 1) % n
        bm.faces.new((v0[i], v0[j], v1[j], v1[i]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return new_obj(name, bm, mat)

def box(name, x0, x1, y0, y1, z0, z1, mat, bevel=0.0, seg=3):
    ob = prism(name, [(x0, z0), (x1, z0), (x1, z1), (x0, z1)], "Y", y0, y1, mat)
    if bevel: bevel_mod(ob, bevel, seg)
    return ob

def annulus(name, cx, cz, r0, r1, y0, y1, a0, a1, mat, segs=48):
    """Ring segment in the XZ plane (angles in degrees, 0 = +X), extruded along Y."""
    outer, inner = [], []
    for i in range(segs + 1):
        a = math.radians(a0 + (a1 - a0) * i / segs)
        outer.append((cx + r1 * math.cos(a), cz + r1 * math.sin(a)))
        inner.append((cx + r0 * math.cos(a), cz + r0 * math.sin(a)))
    if a1 - a0 >= 360:
        bm = bmesh.new()
        rings = []
        for y in (y0, y1):
            rings.append(([bm.verts.new((u, y, v)) for u, v in outer[:-1]],
                          [bm.verts.new((u, y, v)) for u, v in inner[:-1]]))
        (o0, i0), (o1, i1) = rings
        n = segs
        for k in range(n):
            j = (k + 1) % n
            bm.faces.new((o0[k], o0[j], o1[j], o1[k]))
            bm.faces.new((i0[k], i1[k], i1[j], i0[j]))
            bm.faces.new((o0[k], i0[k], i0[j], o0[j]))
            bm.faces.new((o1[k], o1[j], i1[j], i1[k]))
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        return new_obj(name, bm, mat)
    return prism(name, outer + list(reversed(inner)), "Y", y0, y1, mat)

def cyl(name, x, y, z, r, depth, mat, axis="Y", verts=64, bevel=0.0, seg=3):
    rot = {"Y": (math.pi / 2, 0, 0), "X": (0, math.pi / 2, 0), "Z": (0, 0, 0)}[axis]
    bpy.ops.mesh.primitive_cylinder_add(vertices=verts, radius=r, depth=depth, location=(x, y, z), rotation=rot)
    ob = bpy.context.active_object
    ob.name = name
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    ob.data.materials.append(M[mat])
    if bevel: bevel_mod(ob, bevel, seg)
    return ob

def activate(ob):
    bpy.ops.object.select_all(action="DESELECT")
    ob.select_set(True)
    bpy.context.view_layer.objects.active = ob

def apply_mods(ob):
    activate(ob)
    for m in list(ob.modifiers):
        bpy.ops.object.modifier_apply(modifier=m.name)

def bevel_mod(ob, width, seg=3, angle=40):
    m = ob.modifiers.new("bev", "BEVEL")
    m.width = width
    m.segments = seg
    m.limit_method = "ANGLE"
    m.angle_limit = math.radians(angle)
    apply_mods(ob)

def boolean(ob, cutter, op="DIFFERENCE"):
    m = ob.modifiers.new("bool", "BOOLEAN")
    m.operation = op
    m.object = cutter
    m.solver = "EXACT"
    apply_mods(ob)
    bpy.data.objects.remove(cutter, do_unlink=True)

def join(name, obs):
    bpy.ops.object.select_all(action="DESELECT")
    for o in obs: o.select_set(True)
    bpy.context.view_layer.objects.active = obs[0]
    bpy.ops.object.join()
    ob = bpy.context.active_object
    ob.name = name
    ob.data.name = name
    return ob

def deform(ob, fn):
    for v in ob.data.vertices:
        v.co = fn(v.co.copy())

def nose(k=0.55, start=0.50):
    """Sweep the front corners back so the nose is rounded in plan view."""
    def f(c):
        d = max(0.0, abs(c.y) - start)
        if c.x > 1.9:
            c.x -= k * d * d * min(1.0, (c.x - 1.9) / 0.5)
        return c
    return f

def crown(amount, half, zmin):
    """Bow a flat top upward across the width (hood, roof)."""
    def f(c):
        if c.z > zmin:
            c.z += amount * max(0.0, 1 - (c.y / half) ** 2)
        return c
    return f

def finish(ob):
    """Smooth shading with crisp edges, origin at the part's own centre (the explode pivot)."""
    for p in ob.data.polygons: p.use_smooth = True
    m = ob.modifiers.new("split", "EDGE_SPLIT")
    m.split_angle = math.radians(32)
    apply_mods(ob)
    activate(ob)
    bpy.ops.object.origin_set(type="ORIGIN_GEOMETRY", center="BOUNDS")
    return ob

W = 0.955          # half body width
FA, RA = 1.82, -1.48  # axle x
WR, WY = 0.405, 0.80  # wheel radius, wheel centre y
AR = 0.50          # arch radius

def arch_cutters(x):
    cs = []
    for s in (1, -1):
        y0, y1 = (0.64, 1.1) if s > 0 else (-1.1, -0.64)
        c = cyl("cut", x, (y0 + y1) / 2, WR, AR, y1 - y0, "trim", verts=64)
        cs.append(c)
    return cs

def flare(name, x, side):
    y0, y1 = (0.925, 0.99) if side > 0 else (-0.99, -0.925)
    f = annulus(name, x, WR, AR - 0.005, AR + 0.075, y0, y1, -8, 188, "trim")
    bevel_mod(f, 0.012, 2)
    return f

# ---------------------------------------------------------------- body_cab
clip = prism("clip", [(1.20, 0.50), (2.46, 0.50), (2.60, 0.66), (2.64, 0.80), (2.63, 1.08), (2.56, 1.165), (1.20, 1.17)],
             "Y", -W, W, "paint")
bay = box("bay", 1.32, 2.42, -0.80, 0.80, 0.70, 1.40, "trim")
boolean(clip, bay)
for c in arch_cutters(FA): boolean(clip, c)
bevel_mod(clip, 0.05, 4)
deform(clip, nose())
bayfloor = box("bayfloor", 1.32, 2.42, -0.80, 0.80, 0.69, 0.72, "under")

cab = box("cablow", -0.88, 1.21, -0.915, 0.915, 0.50, 1.17, "paint", 0.02)

# greenhouse: windshield + back glass are glass, sides are black (door glass sits over them)
bm = bmesh.new()
gb = [(1.20, 0.88), (-0.86, 0.88), (-0.86, -0.88), (1.20, -0.88)]
gt = [(0.42, 0.76), (-0.78, 0.76), (-0.78, -0.76), (0.42, -0.76)]
vb = [bm.verts.new((x, y, 1.165)) for x, y in gb]
vt = [bm.verts.new((x, y, 1.765)) for x, y in gt]
bm.faces.new(list(reversed(vb)))
bm.faces.new(vt)
for i in range(4):
    j = (i + 1) % 4
    bm.faces.new((vb[i], vb[j], vt[j], vt[i]))
bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
gh = new_obj("greenhouse", bm, "trim")
gh.data.materials.append(M["glass"])
for p in gh.data.polygons:
    if abs(p.normal.x) > 0.5: p.material_index = 1
bevel_mod(gh, 0.03, 3, angle=30)

roof = box("roof", -0.81, 0.45, -0.785, 0.785, 1.735, 1.80, "paint", 0.035, 4)
deform(roof, crown(0.03, 0.8, 1.77))
cowl = box("cowl", 1.12, 1.30, -0.80, 0.80, 1.12, 1.20, "trim", 0.01)
rocker = box("rocker", -0.88, 1.22, -0.94, 0.94, 0.42, 0.53, "trim", 0.025)
underbody = box("under", -2.45, 2.30, -0.70, 0.70, 0.30, 0.50, "under", 0.02)
steps = []
for s in (1, -1):
    steps.append(cyl("step", 0.17, s * 0.985, 0.43, 0.035, 1.75, "trim", axis="X", verts=24))
flares_f = [flare("flare", FA, s) for s in (1, -1)]

body = join("body_cab", [clip, bayfloor, cab, gh, roof, cowl, rocker, underbody] + steps + flares_f)
finish(body)

# ---------------------------------------------------------------- hood
hood = prism("hood", [(1.26, 1.165), (2.54, 1.165), (2.585, 1.18), (2.54, 1.225), (2.30, 1.248), (1.26, 1.262)],
             "Y", -0.885, 0.885, "paint")
bevel_mod(hood, 0.03, 3)
deform(hood, nose())
deform(hood, crown(0.035, 0.9, 1.2))
scoop = prism("scoop", [(1.62, 1.24), (2.02, 1.24), (2.02, 1.30), (1.66, 1.315)], "Y", -0.24, 0.24, "paint")
bevel_mod(scoop, 0.02, 3)
mouth = box("mouth", 2.005, 2.03, -0.21, 0.21, 1.255, 1.29, "gloss", 0.005)
finish(join("hood", [hood, scoop, mouth]))

# ---------------------------------------------------------------- doors (with their window glass)
def gh_point(x_rel, t, side):
    """Point on the greenhouse side plane at height fraction t, nudged 6 mm outward."""
    z = 1.165 + 0.60 * t
    y = (0.88 - 0.12 * t + 0.006) * side
    return x_rel, y, z

def door(name, x0, x1, side, front):
    y0, y1 = (0.912, 0.958) if side > 0 else (-0.958, -0.912)
    d = box(name, x1, x0, y0, y1, 0.505, 1.168, "paint", 0.018)
    hy = sorted((side * 0.955, side * 0.972))
    handle = box("handle", x1 + 0.10, x1 + 0.27, hy[0], hy[1], 1.03, 1.065, "trim", 0.008)
    # window glass on the greenhouse plane
    t0, t1 = 0.05, 0.92
    if front:
        xf = lambda t: 1.20 - 0.78 * t - 0.07
        quad = [(xf(t0), t0), (0.13, t0), (0.13, t1), (xf(t1), t1)]
    else:
        xr = lambda t: -0.86 + 0.08 * t + 0.13
        quad = [(0.05, t0), (xr(t0), t0), (xr(t1), t1), (0.05, t1)]
    bm = bmesh.new()
    vs = [bm.verts.new(gh_point(x, t, side)) for x, t in quad]
    f = bm.faces.new(vs)
    ext = bmesh.ops.extrude_face_region(bm, geom=[f])
    nv = [e for e in ext["geom"] if isinstance(e, bmesh.types.BMVert)]
    nz = 0.12 / 0.60
    ln = math.sqrt(1 + nz * nz)
    for v in nv:
        v.co.y += side * 0.006 / ln
        v.co.z += 0.006 * nz / ln
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    glass = new_obj("dglass", bm, "glass")
    return finish(join(name, [d, handle, glass]))

door("door_fl", 1.185, 0.105, 1, True)
door("door_fr", 1.185, 0.105, -1, True)
door("door_rl", 0.085, -0.845, 1, False)
door("door_rr", 0.085, -0.845, -1, False)

# ---------------------------------------------------------------- mirrors
for name, s in (("mirror_l", 1), ("mirror_r", -1)):
    arm = box("arm", 0.92, 1.05, min(s * 0.93, s * 1.02), max(s * 0.93, s * 1.02), 1.20, 1.24, "trim", 0.01)
    yy = sorted((s * 1.0, s * 1.21))
    house = box("house", 0.90, 1.04, yy[0], yy[1], 1.19, 1.37, "trim", 0.035, 4)
    finish(join(name, [house, arm]))

# ---------------------------------------------------------------- bed (shell, tub, wheel housings, rail caps)
bed = box("bed", -2.60, -0.92, -W, W, 0.55, 1.19, "paint")
boolean(bed, box("tub", -2.80, -0.98, -0.865, 0.865, 0.74, 1.40, "trim"))
for s in (1, -1):
    hump = box("hump", RA - 0.52, RA + 0.52, min(s * 0.62, s * 0.87), max(s * 0.62, s * 0.87), 0.70, 0.97, "paint")
    boolean(bed, hump, "UNION")
for c in arch_cutters(RA): boolean(bed, c)
bevel_mod(bed, 0.025, 3)
liner = box("liner", -2.58, -0.99, -0.86, 0.86, 0.735, 0.75, "under")
rails = [box("rail", -2.60, -0.93, min(s * 0.855, s * 0.962), max(s * 0.855, s * 0.962), 1.185, 1.215, "trim", 0.01) for s in (1, -1)]
flares_r = [flare("flare", RA, s) for s in (1, -1)]
finish(join("bed", [bed, liner] + rails + flares_r))

# ---------------------------------------------------------------- tailgate, taillights, rear bumper
tg = box("tailgate", -2.668, -2.60, -0.795, 0.795, 0.58, 1.19, "paint", 0.02)
tgh = box("tgh", -2.676, -2.66, -0.13, 0.13, 1.08, 1.13, "trim", 0.008)
finish(join("tailgate", [tg, tgh]))
for name, s in (("taillight_l", 1), ("taillight_r", -1)):
    yy = sorted((s * 0.80, s * 0.955))
    lens = box(name, -2.672, -2.57, yy[0], yy[1], 0.80, 1.17, "lamp_red", 0.02)
    strip = box("strip", -2.68, -2.66, yy[0] + 0.03, yy[1] - 0.03, 0.95, 1.00, "lamp", 0.004)
    finish(join(name, [lens, strip]))
rb = prism("bumper_rear", [(-2.57, 0.44), (-2.76, 0.44), (-2.78, 0.52), (-2.76, 0.66), (-2.57, 0.66)], "Y", -0.93, 0.93, "trim")
bevel_mod(rb, 0.025, 3)
step = box("rstep", -2.785, -2.70, -0.30, 0.30, 0.60, 0.665, "rim_dark", 0.01)
finish(join("bumper_rear", [rb, step]))

# ---------------------------------------------------------------- front: bumper, grille, headlights
fu = prism("fb_up", [(2.40, 0.585), (2.765, 0.585), (2.755, 0.72), (2.60, 0.775), (2.40, 0.765)], "Y", -0.965, 0.965, "paint")
bevel_mod(fu, 0.03, 3)
fl = prism("fb_low", [(2.40, 0.40), (2.69, 0.41), (2.775, 0.50), (2.785, 0.595), (2.40, 0.595)], "Y", -0.95, 0.95, "trim")
bevel_mod(fl, 0.03, 3)
skid = prism("skid", [(2.50, 0.375), (2.70, 0.385), (2.75, 0.45), (2.50, 0.45)], "Y", -0.42, 0.42, "rim_dark")
bevel_mod(skid, 0.012, 2)
fogs = []
for s in (1, -1):
    yy = sorted((s * 0.66, s * 0.80))
    fogs.append(box("fogbez", 2.74, 2.795, yy[0], yy[1], 0.47, 0.555, "gloss", 0.012))
    fogs.append(box("fog", 2.79, 2.80, yy[0] + 0.03, yy[1] - 0.03, 0.495, 0.53, "lamp", 0.006))
fbo = join("bumper_front", [fu, fl, skid] + fogs)
deform(fbo, nose(0.75, 0.45))
finish(fbo)

gr = prism("grille", [(-0.50, 0.775), (0.50, 0.775), (0.60, 0.97), (0.54, 1.10), (-0.54, 1.10), (-0.60, 0.97)], "X", 2.60, 2.672, "gloss")
bevel_mod(gr, 0.015, 3)
slats = []
for i, z in enumerate((0.83, 0.90, 0.97, 1.04)):
    half = 0.50 + 0.07 * min(1, (z - 0.775) / 0.2)
    slats.append(box("slat", 2.66, 2.69, -half + 0.05, half - 0.05, z - 0.012, z + 0.012, "rim_dark", 0.006))
g = join("grille", [gr] + slats)
deform(g, nose(0.35, 0.40))
finish(g)

for name, s in (("headlight_l", 1), ("headlight_r", -1)):
    pts = [(0.60, 1.10), (0.925, 1.085), (0.94, 1.0), (0.64, 0.975)]
    if s < 0: pts = [(-u, v) for u, v in reversed(pts)]
    h = prism(name, pts, "X", 2.47, 2.64, "lens")
    bevel_mod(h, 0.012, 3)
    dpts = [(0.63, 1.075), (0.91, 1.062), (0.915, 1.048), (0.635, 1.06)]
    if s < 0: dpts = [(-u, v) for u, v in reversed(dpts)]
    drl = prism("drl", dpts, "X", 2.64, 2.652, "lamp")
    parts_h = [h, drl]
    for yc in (0.70, 0.82):
        parts_h.append(cyl("proj", 2.645, s * yc, 1.015, 0.03, 0.02, "chrome", axis="X", verts=24))
        parts_h.append(cyl("projlens", 2.656, s * yc, 1.015, 0.02, 0.006, "lamp", axis="X", verts=24))
    hl = join(name, parts_h)
    deform(hl, nose())
    finish(hl)

# ---------------------------------------------------------------- engine (V6 under the hood)
blk = box("engine", 1.48, 2.10, -0.26, 0.26, 0.72, 0.98, "engine", 0.02)
heads = []
for s in (1, -1):
    hd = box("head", 1.46, 2.12, min(s * 0.10, s * 0.36), max(s * 0.10, s * 0.36), 0.96, 1.06, "alu", 0.03)
    heads.append(hd)
plenum = box("plenum", 1.52, 2.02, -0.14, 0.14, 1.02, 1.14, "engine", 0.04, 4)
pulleys = [cyl("pulley", 2.15, y, z, r, 0.04, "alu", axis="X", verts=40) for y, z, r in ((0.0, 0.84, 0.09), (0.17, 0.96, 0.06), (-0.16, 0.98, 0.055))]
airbox = box("airbox", 1.70, 2.05, 0.42, 0.72, 0.92, 1.10, "trim", 0.03, 4)
finish(join("engine", [blk, plenum, airbox] + heads + pulleys))

# ---------------------------------------------------------------- wheels
def wheel(name, x, side):
    y = WY * side
    tire = cyl("tire", x, y, WR, WR, 0.28, "tire", verts=72, bevel=0.075, seg=6)
    oy = y + side * 0.141          # outer face
    barrel = cyl("barrel", x, y - side * 0.005, WR, 0.262, 0.272, "rim_dark", verts=72)
    lip = annulus("lip", x, WR, 0.238, 0.268, min(oy - side * 0.012, oy + side * 0.004), max(oy - side * 0.012, oy + side * 0.004), 0, 360, "rim", segs=72)
    parts = [tire, barrel, lip]
    for k in range(6):
        a = math.radians(k * 60 + 15)
        ca, sa = math.cos(a), math.sin(a)
        r0, r1, hw = 0.06, 0.245, 0.045
        q = [(r0, -hw * 1.2), (r1, -hw), (r1, hw), (r0, hw * 1.2)]
        pts = [(x + u * ca - v * sa, WR + u * sa + v * ca) for u, v in q]
        sp = prism("spoke", pts, "Y", min(oy - side * 0.03, oy + side * 0.008), max(oy - side * 0.03, oy + side * 0.008), "rim")
        bevel_mod(sp, 0.006, 2)
        parts.append(sp)
    cap = cyl("cap", x, oy, WR, 0.07, 0.03, "rim", verts=40, bevel=0.01, seg=2)
    parts.append(cap)
    for k in range(6):
        a = math.radians(k * 60 + 45)
        parts.append(cyl("nut", x + 0.10 * math.cos(a), oy - side * 0.004, WR + 0.10 * math.sin(a), 0.014, 0.02, "chrome", verts=12))
    finish(join(name, parts))

wheel("wheel_fl", FA, 1)
wheel("wheel_fr", FA, -1)
wheel("wheel_rl", RA, 1)
wheel("wheel_rr", RA, -1)

# ---------------------------------------------------------------- export
os.makedirs(os.path.dirname(OUT), exist_ok=True)
names = sorted(o.name for o in bpy.data.objects)
print("PARTS", len(names), names)
tris = sum(sum(len(p.vertices) - 2 for p in o.data.polygons) for o in bpy.data.objects)
print("TRIS", tris)
bpy.ops.export_scene.gltf(filepath=OUT, export_format="GLB", export_apply=True, export_yup=True,
                          export_materials="EXPORT", export_normals=True)
print("WROTE", OUT, os.path.getsize(OUT))
