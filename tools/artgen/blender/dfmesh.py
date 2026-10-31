"""Helpers the Dead Fire mesh scripts share. Runs inside Blender 5.2 (bundled Python), never outside it.

Conventions: metres, facing +X, Z up, origin at the base centre unless the catalogue says otherwise.
A mesh script's build(dims) returns the root mesh object; sockets are SOCKET_<Name> empties and collision hulls are
UCX_<Name>_NN children (build_mesh renames the hulls after the root so Unreal matches them to the mesh).
"""
import json
import math

import bmesh
import bpy
from mathutils import Euler, Matrix, Vector

SOCKET = "SOCKET_"
UCX = "UCX_"

# The one set of flags every mesh is exported with. Task 5 checked them on the axis fixture in Unreal: FBX_SCALE_NONE
# (unit scaling applied to the objects, FBX scale 1.0) imports 1 m as 100 cm (FBX_SCALE_UNITS came in 100x too small);
# +X stays forward, Z up, and Blender +Y (left) becomes Unreal -Y (also left: Unreal's +Y is right).
FBX_FLAGS = dict(use_selection=True, apply_scale_options="FBX_SCALE_NONE", axis_forward="X", axis_up="Z",
                 mesh_smooth_type="FACE", add_leaf_bones=False)


def _link(obj):
    bpy.context.scene.collection.objects.link(obj)
    return obj


def _from_bmesh(name, bm, loc=(0, 0, 0)):
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    for p in me.polygons:
        p.use_smooth = False
    obj = bpy.data.objects.new(name, me)
    obj.location = loc
    return _link(obj)


def box(name, size_m, bevel_m=0.0, loc=(0, 0, 0)):
    """A box of size (x, y, z) metres centred on loc; bevel_m > 0 rounds the edges with two segments."""
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    bmesh.ops.scale(bm, vec=Vector(size_m), verts=bm.verts)
    if bevel_m > 0:
        bmesh.ops.bevel(bm, geom=list(bm.edges), offset=bevel_m, segments=2, affect="EDGES")
    return _from_bmesh(name, bm, loc)


def cylinder(name, radius_m, depth_m, verts=16, loc=(0, 0, 0), axis="Z"):
    """A capped cylinder centred on loc, its length along `axis` ('X', 'Y' or 'Z')."""
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=verts, radius1=radius_m, radius2=radius_m, depth=depth_m)
    rot = {"Z": None, "X": Matrix.Rotation(math.radians(90), 4, "Y"), "Y": Matrix.Rotation(math.radians(90), 4, "X")}[axis]
    if rot is not None:
        bmesh.ops.transform(bm, matrix=rot, verts=bm.verts)
    return _from_bmesh(name, bm, loc)


def prism(name, outline_m, height_m, loc=(0, 0, 0)):
    """The polygon `outline_m` (x, y points, counter-clockwise from above) extruded up by height_m from z = 0."""
    bm = bmesh.new()
    verts = [bm.verts.new((x, y, 0.0)) for x, y in outline_m]
    face = bm.faces.new(verts)
    ext = bmesh.ops.extrude_face_region(bm, geom=[face])
    top = [v for v in ext["geom"] if isinstance(v, bmesh.types.BMVert)]
    bmesh.ops.translate(bm, vec=(0, 0, height_m), verts=top)
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    return _from_bmesh(name, bm, loc)


def _finish(bm, bevel_m=0.0, segments=1, min_angle_deg=30.0):
    """Outward normals, then an optional bevel of the edges sharper than min_angle_deg, then n-gons split into
    triangles (concave n-gons such as an arch-notched side would otherwise be triangulated wrongly by the importer)."""
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    if bevel_m > 0:
        bm.normal_update()
        edges = [e for e in bm.edges if len(e.link_faces) == 2 and e.calc_face_angle(0.0) > math.radians(min_angle_deg)]
        if edges:
            bmesh.ops.bevel(bm, geom=edges, offset=bevel_m, segments=segments, profile=0.5, affect="EDGES",
                            clamp_overlap=True, material=-1)
    ngons = [f for f in bm.faces if len(f.verts) > 4]
    if ngons:
        bmesh.ops.triangulate(bm, faces=ngons, quad_method="BEAUTY", ngon_method="BEAUTY")
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))


def _with_slots(obj, slot_names):
    for n in slot_names:
        obj.data.materials.append(bpy.data.materials.get(n) or bpy.data.materials.new(n))
    return obj


def solid(name, bm, slot_names, triangulate=False):
    """A mesh object from a bmesh a script built itself: outward normals, n-gons split (triangulate: every face, for
    lofted quads that are not flat), the slots in order."""
    _finish(bm)
    if triangulate:
        bmesh.ops.triangulate(bm, faces=list(bm.faces))
    return _with_slots(_from_bmesh(name, bm), slot_names)


def profile(name, outline_xz, half_w_m, slot_names, edge_slots=None, bevel_m=0.0, segments=1, y_m=0.0):
    """A side profile: the polygon outline_xz ((x, z) metres, in order around the outline) extruded across Y from
    y_m - half_w_m to y_m + half_w_m. Face material = slot index 0, except the faces swept by outline edge i, which take
    edge_slots[i] when given (e.g. the inside of a wheel arch). Edges sharper than 30 degrees are bevelled by bevel_m."""
    bm = bmesh.new()
    n = len(outline_xz)
    a = [bm.verts.new((x, y_m - half_w_m, z)) for x, z in outline_xz]
    b = [bm.verts.new((x, y_m + half_w_m, z)) for x, z in outline_xz]
    bm.faces.new(a)
    bm.faces.new(list(reversed(b)))
    for i in range(n):
        j = (i + 1) % n
        f = bm.faces.new((a[i], a[j], b[j], b[i]))
        f.material_index = edge_slots[i] if edge_slots else 0
    _finish(bm, bevel_m, segments)
    return _with_slots(_from_bmesh(name, bm), slot_names)


def extrude_x(name, outline_yz, slot_names, x0=-0.5, x1=0.5, segments=1):
    """A cross-section outline_yz ((y, z) metres, in order around it) swept along X from x0 to x1 in `segments` even
    steps, capped at both ends. The steps give a spline mesh (the road, the barriers) vertices to bend at."""
    bm = bmesh.new()
    rings = [[bm.verts.new((x0 + (x1 - x0) * i / segments, y, z)) for y, z in outline_yz] for i in range(segments + 1)]
    n = len(outline_yz)
    for a, b in zip(rings, rings[1:]):
        for k in range(n):
            bm.faces.new((a[k], a[(k + 1) % n], b[(k + 1) % n], b[k]))
    bm.faces.new(rings[0])
    bm.faces.new(list(reversed(rings[-1])))
    _finish(bm)
    return _with_slots(_from_bmesh(name, bm), slot_names)


def ground(obj):
    """Moves obj's geometry up or down so its lowest vertex is at z = 0 (a base-origin prop resting on the ground after
    its parts were tilted); returns the shift in metres."""
    dz = -min((obj.matrix_world @ v.co).z for v in obj.data.vertices)
    obj.data.transform(Matrix.Translation((0.0, 0.0, dz)))
    return dz


def corrugated_sheet(name, width_m, height_m, slot_name, pitch_m=0.2, depth_m=0.03, rows=2, thickness_m=0.006,
                     jag_m=0.0, curl_m=0.0, seed=0):
    """A corrugated metal sheet standing on the XZ plane: width_m along X (centred), height_m up from z = 0, ribs
    pitch_m apart and depth_m deep along Y, thickness_m thick (both sides are drawn). jag_m tears the top edge down by up
    to that much and curl_m bends the top out along +Y (a sheet that has been knocked about); deterministic from seed.
    The tear runs between three random depths (the two corners and the middle) with a little jitter, so it reads as one
    ragged edge rather than a row of broken pickets."""
    import random
    rng = random.Random(seed)
    cols = max(2, int(round(width_m / pitch_m * 3)))
    tear = [rng.uniform(0.0, 1.0) for _ in range(3)]
    bm = bmesh.new()
    grid = []
    for r in range(rows + 1):
        row = []
        for c in range(cols + 1):
            x = -width_m / 2 + width_m * c / cols
            z = height_m * r / rows
            if r == rows and jag_m > 0:
                t = 2.0 * c / cols
                k = int(min(t, 1.0))
                depth = tear[k] + (tear[k + 1] - tear[k]) * (t - k)
                z -= jag_m * min(1.0, max(0.0, depth + rng.uniform(-0.12, 0.12)))
            y = depth_m * math.sin(2 * math.pi * c / 3.0) * 0.5 + curl_m * (z / height_m) ** 2
            row.append(bm.verts.new((x, y, z)))
        grid.append(row)
    faces = [bm.faces.new((grid[r][c], grid[r][c + 1], grid[r + 1][c + 1], grid[r + 1][c]))
             for r in range(rows) for c in range(cols)]
    bmesh.ops.solidify(bm, geom=faces, thickness=thickness_m)
    _finish(bm)
    return _with_slots(_from_bmesh(name, bm), [slot_name])


def frustum(name, bottom, top, slot_names, bevel_m=0.0, segments=1, glass=None):
    """A six-sided block between two horizontal rectangles, each (x_rear, x_front, half_w, z) in metres (a car cabin).
    glass = (slot index, pillar width m, depth m): the front, rear and side faces are inset by the pillar width and the
    inner faces take that slot, pushed in by depth (negative pushes out)."""
    bm = bmesh.new()
    (bx0, bx1, bw, bz), (tx0, tx1, tw, tz) = bottom, top
    v = [bm.verts.new(p) for p in ((bx0, -bw, bz), (bx1, -bw, bz), (bx1, bw, bz), (bx0, bw, bz),
                                   (tx0, -tw, tz), (tx1, -tw, tz), (tx1, tw, tz), (tx0, tw, tz))]
    faces = {"bottom": (v[0], v[3], v[2], v[1]), "top": (v[4], v[5], v[6], v[7]), "right": (v[0], v[1], v[5], v[4]),
             "front": (v[1], v[2], v[6], v[5]), "left": (v[2], v[3], v[7], v[6]), "rear": (v[3], v[0], v[4], v[7])}
    made = {k: bm.faces.new(f) for k, f in faces.items()}
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    if glass:
        slot_i, pillar, depth = glass
        panes = [made[k] for k in ("front", "rear", "left", "right")]
        bmesh.ops.inset_individual(bm, faces=panes, thickness=pillar, depth=-depth, use_even_offset=True)
        for f in panes:  # the original faces are now the inner panes
            f.material_index = slot_i
    if bevel_m > 0:
        corners = set(v)
        outer = [e for e in bm.edges if e.verts[0] in corners and e.verts[1] in corners]
        bmesh.ops.bevel(bm, geom=outer, offset=bevel_m, segments=segments, profile=0.5, affect="EDGES",
                        clamp_overlap=True, material=-1)
    _finish(bm)
    return _with_slots(_from_bmesh(name, bm), slot_names)


def lathe(name, profile_ry, segments, slot_names, axis="Y", loc=(0, 0, 0), uv_along=False):
    """Spins the open profile [(radius, along) ...] metres around `axis` (a point with radius 0 is on the axis).
    uv_along writes cylindrical UVs: U around the axis, V from 0 at the first profile point to 1 at the last (along
    the axis), as the flame master expects (it pans along V and fades towards V = 1)."""
    bm = bmesh.new()
    rings = []
    for r, t in profile_ry:
        if r < 1e-6:
            rings.append([bm.verts.new(_axis_point(axis, 0.0, 0.0, t))])
            continue
        rings.append([bm.verts.new(_axis_point(axis, r * math.cos(2 * math.pi * k / segments),
                                               r * math.sin(2 * math.pi * k / segments), t)) for k in range(segments)])
    t0, t1 = profile_ry[0][1], profile_ry[-1][1]
    vs = [abs(t - t0) / max(abs(t1 - t0), 1e-9) for _, t in profile_ry]
    uv_faces = []
    for i, (ra, rb) in enumerate(zip(rings, rings[1:])):
        for k in range(segments):
            k1 = (k + 1) % segments
            corners = [(ra[k % len(ra)], k / segments, vs[i]), (ra[k1 % len(ra)], (k + 1) / segments, vs[i]),
                       (rb[k1 % len(rb)], (k + 1) / segments, vs[i + 1]), (rb[k % len(rb)], k / segments, vs[i + 1])]
            uniq = []
            for c in corners:
                if c[0] not in [u[0] for u in uniq]:
                    uniq.append(c)
            if len(uniq) >= 3:
                uv_faces.append((bm.faces.new([c[0] for c in uniq]), {c[0]: (c[1], c[2]) for c in uniq}))
    if uv_along:
        layer = bm.loops.layers.uv.new("UVMap")
        for f, uvs in uv_faces:
            for loop in f.loops:
                loop[layer].uv = uvs[loop.vert]
    _finish(bm)
    return _with_slots(_from_bmesh(name, bm, loc), slot_names)


def shell(name, outer, inner, slot_names, wrap=True, cap=False, wall_slot=0, bevel_m=0.0):
    """A solid between two matching grids of points (metres): outer[i][k] and inner[i][k] are row i, column k, the rows
    running bottom to top and the columns across (wrap: round, the last column joins the first). Both surfaces take slot
    0; the walls between them take wall_slot: the first row's, the last row's (unless cap, which closes each grid's
    last row with one face instead, as on a dome) and, without wrap, the first and last columns' (e.g. a gear's edge)."""
    bm = bmesh.new()
    o = [[bm.verts.new(p) for p in row] for row in outer]
    n = [[bm.verts.new(p) for p in row] for row in inner]
    rows, cols = len(o), len(o[0])
    across = range(cols) if wrap else range(cols - 1)

    def quad(a, b, c, d, slot):
        bm.faces.new((a, b, c, d)).material_index = slot

    for i in range(rows - 1):
        for k in across:
            k1 = (k + 1) % cols
            quad(o[i][k], o[i][k1], o[i + 1][k1], o[i + 1][k], 0)
            quad(n[i][k], n[i + 1][k], n[i + 1][k1], n[i][k1], 0)
    for i in ([0] if cap else [0, rows - 1]):
        for k in across:
            k1 = (k + 1) % cols
            quad(o[i][k], n[i][k], n[i][k1], o[i][k1], wall_slot)
    if cap:
        bm.faces.new(o[-1])
        bm.faces.new(list(reversed(n[-1])))
    if not wrap:
        for k in (0, cols - 1):
            for i in range(rows - 1):
                quad(o[i][k], o[i + 1][k], n[i + 1][k], n[i][k], wall_slot)
    _finish(bm, bevel_m)
    return _with_slots(_from_bmesh(name, bm), slot_names)


def superellipse(t, n):
    """(cos-like, sin-like) of angle t on a superellipse of exponent n (2: a circle; larger: squarer)."""
    c, s = math.cos(t), math.sin(t)
    return (math.copysign(abs(c) ** (2.0 / n), c), math.copysign(abs(s) ** (2.0 / n), s))


def _axis_point(axis, u, w, t):
    """A point at distance t along `axis`, (u, w) across it."""
    return {"X": (t, u, w), "Y": (u, t, w), "Z": (u, w, t)}[axis]


def tube(name, a_m, b_m, radius_m, slot_names, verts=8, radius_end_m=None):
    """A capped cylinder from point a_m to point b_m (metres); radius_end_m tapers it to that radius at b_m (a branch)."""
    a, b = Vector(a_m), Vector(b_m)
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=verts, radius1=radius_m,
                          radius2=radius_m if radius_end_m is None else radius_end_m, depth=(b - a).length)
    rot = Vector((0, 0, 1)).rotation_difference((b - a).normalized()).to_matrix().to_4x4()
    bmesh.ops.transform(bm, matrix=rot, verts=bm.verts)
    _finish(bm)
    return _with_slots(_from_bmesh(name, bm, (a + b) / 2), slot_names)


def part(obj, slot_name):
    """slot() for a part that will be joined: one material, returned for chaining."""
    return slot(obj, slot_name)


def order_slots(obj, names, rename=None):
    """Rebuilds obj's material slots as exactly `names` in that order, keeping every face on its material (the
    importer assigns instances by slot name, and the catalogue's slot order is checked). rename {old: new} first moves the
    faces of material `old` to slot `new` (e.g. a car body's slots onto a wreck's two)."""
    me = obj.data
    rename = rename or {}
    old = [m.name if m else None for m in me.materials]
    remap = [names.index(rename.get(n, n)) for n in old]
    idx = [p.material_index for p in me.polygons]
    me.materials.clear()
    for n in names:
        me.materials.append(bpy.data.materials.get(n) or bpy.data.materials.new(n))
    for p, i in zip(me.polygons, idx):
        p.material_index = remap[i]
    return obj


def assemble(parts, name, slot_names, unwrap=True):
    """Joins the parts into one object named `name` with an identity transform (the joined geometry stays where it
    was), its slots exactly slot_names in that order, and (unwrap) Smart UV Project."""
    root = join(parts, name)
    root.data.transform(root.matrix_world)
    root.matrix_world = Matrix.Identity(4)
    order_slots(root, list(slot_names))
    if unwrap:
        smart_uv(root)
    return root


def ue_cm_to_m(p_cm):
    """An Unreal actor-space point (cm; X forward, Y right, Z up) in Blender metres (Y left): (x, -y, z) / 100."""
    return (p_cm[0] / 100.0, -p_cm[1] / 100.0, p_cm[2] / 100.0)


def place_wheels(wheel, dims, link):
    """Instances of the wheel object at each dims["wheels"] bone (spec 6.1: the right wheels yawed 180 degrees, so the
    tyre's outer face and its AdditionalOffset point outwards on both sides). link(obj) adds each copy to a collection."""
    out = []
    for bone, pos in sorted(dims.get("wheels", {}).items()):
        copy = wheel.copy()
        copy.data = wheel.data
        copy.name = "WHEEL_" + bone
        copy.location = ue_cm_to_m(pos)
        copy.rotation_euler = (0.0, 0.0, math.pi if pos[1] > 0 else 0.0)  # Unreal +Y is the right side
        link(copy)
        out.append(copy)
    return out


def join(objs, name):
    """Joins the mesh objects into the first one, which is renamed; returns it."""
    bpy.ops.object.select_all(action="DESELECT")
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
    bpy.ops.object.join()
    out = bpy.context.view_layer.objects.active
    out.name = name
    out.data.name = name
    return out


def slot(obj, slot_name):
    """Gives the whole object one material named slot_name (the catalogue's MI name; the importer assigns by slot order)."""
    mat = bpy.data.materials.get(slot_name) or bpy.data.materials.new(slot_name)
    obj.data.materials.clear()
    obj.data.materials.append(mat)
    return obj


# Unreal's FBX import makes a socket's local X axis the exported empty's local Z (and its Y = -empty Y, Z = -empty X):
# an unrotated empty arrived as pitch 90 (measured on a probe mesh, Task 12). So an empty is turned by this before
# export, and the socket arrives with the rotation the script asked for.
SOCKET_FIX = Matrix.Rotation(math.radians(90), 4, "Y")


def socket(parent, name, loc_m, rot_deg=(0, 0, 0)):
    """An empty named SOCKET_<name> under parent, at loc_m (metres, in the parent's frame), turned by rot_deg (XYZ
    Euler degrees, Blender frame; e.g. (0, 0, 180) makes the socket's +X point backwards). The intended X and Z axes
    are kept on the empty ("df_axes") for the stats JSON, which df_verify_art checks against the imported socket."""
    want = Euler([math.radians(a) for a in rot_deg], "XYZ").to_matrix()
    e = bpy.data.objects.new(SOCKET + name, None)
    e.empty_display_type = "ARROWS"
    e.empty_display_size = 0.1
    e.location = loc_m
    e.rotation_euler = (want.to_4x4() @ SOCKET_FIX).to_euler()
    e["df_axes"] = [list(want.col[0]), list(want.col[2])]
    _link(e)
    e.parent = parent
    return e


def ucx_box(parent, size_m, loc_m):
    """A box collision hull UCX_<parent>_NN under parent, centred on loc_m (metres, in the parent's frame)."""
    n = sum(1 for c in parent.children if c.name.startswith(UCX))
    hull = box("%s%s_%02d" % (UCX, parent.name, n), size_m, loc=loc_m)
    hull.display_type = "WIRE"
    hull.parent = parent
    return hull


def hull(name, points_m, loc=(0, 0, 0)):
    """The convex hull of points_m (metres) as a mesh object (a collision hull, or a convex solid)."""
    bm = bmesh.new()
    for p in points_m:
        bm.verts.new(p)
    bmesh.ops.convex_hull(bm, input=list(bm.verts))
    for v in [v for v in bm.verts if not v.link_faces]:  # points inside the hull
        bm.verts.remove(v)
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    return _from_bmesh(name, bm, loc)


def ucx_hull(parent, points_m):
    """A convex collision hull UCX_<parent>_NN under parent: the convex hull of points_m (metres, in the parent's frame).
    Unreal keeps each UCX as one convex element, so a concave shape (a curved ramp) takes one hull per convex piece."""
    n = sum(1 for c in parent.children if c.name.startswith(UCX))
    h = hull("%s%s_%02d" % (UCX, parent.name, n), points_m)
    h.display_type = "WIRE"
    h.parent = parent
    return h


def box_uv(obj, tile_m):
    """Box-projected UVs at world scale: each face is mapped from the plane its normal faces most (X: Y-Z, Y: X-Z,
    Z: X-Y), one UV unit per tile_m metres, so a tiling texture keeps the same size on every prop however big it is
    (Smart UV Project scales each mesh into 0..1 instead)."""
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bm.normal_update()
    layer = bm.loops.layers.uv.verify()
    for f in bm.faces:
        n = f.normal
        ax = max(range(3), key=lambda i: abs(n[i]))
        s = 1.0 if n[ax] >= 0 else -1.0
        for loop in f.loops:
            x, y, z = loop.vert.co
            u, v = {0: (-s * y, z), 1: (s * x, z), 2: (x, s * y)}[ax]
            loop[layer].uv = (u / tile_m, v / tile_m)
    bm.to_mesh(obj.data)
    bm.free()
    return obj


def rock(name, size_m, seed, slot_name, points=32, subdiv=1, cuts=5, rough=0.08, origin="base", flat_base=0.12):
    """A faceted low-poly rock exactly size_m (x, y, z metres) across: the convex hull of `points` random points in a
    shell round the origin (big flat facets), each facet split `subdiv` times and the surface pushed in and out by noise
    (rough, as a share of the radius) so the outline is not a clean polyhedron, then sliced by `cuts` random planes (each
    pushes the vertices beyond it onto it: the flat, fractured faces a rock has), flattened underneath by flat_base (a share
    of the height) so it sits, and scaled to fill size_m. origin "base" puts the bottom centre on the origin, "center" the
    bounds' centre. Deterministic from `seed`; one material, box-projected UVs (2 m a tile)."""
    import random
    from mathutils import noise
    rng = random.Random(seed)
    bm = bmesh.new()
    for _ in range(points):
        bm.verts.new(Vector([rng.gauss(0, 1) for _ in range(3)]).normalized() * rng.uniform(0.75, 1.0))
    bmesh.ops.convex_hull(bm, input=list(bm.verts))
    for v in [v for v in bm.verts if not v.link_faces]:
        bm.verts.remove(v)
    if subdiv:
        bmesh.ops.subdivide_edges(bm, edges=list(bm.edges), cuts=subdiv, use_grid_fill=True)
    off = Vector([rng.uniform(-100, 100) for _ in range(3)])
    for v in bm.verts:
        v.co *= 1.0 + rough * noise.fractal(v.co * 1.8 + off, 0.8, 2.0, 3, noise_basis="PERLIN_ORIGINAL")
    for _ in range(cuts):
        n = Vector([rng.gauss(0, 1) for _ in range(3)]).normalized()
        d = rng.uniform(0.62, 0.86)
        for v in bm.verts:
            over = v.co.dot(n) - d
            if over > 0:
                v.co -= n * over
    lo_z = min(v.co.z for v in bm.verts)
    floor = lo_z + flat_base * (max(v.co.z for v in bm.verts) - lo_z)
    for v in bm.verts:
        v.co.z = max(v.co.z, floor)
    lo = Vector([min(v.co[i] for v in bm.verts) for i in range(3)])
    hi = Vector([max(v.co[i] for v in bm.verts) for i in range(3)])
    for v in bm.verts:
        v.co = Vector([(v.co[i] - (lo[i] + hi[i]) / 2) / (hi[i] - lo[i]) * size_m[i] for i in range(3)])
        if origin == "base":
            v.co.z += size_m[2] / 2
    bmesh.ops.remove_doubles(bm, verts=list(bm.verts), dist=0.002)  # the slices leave coincident vertices
    bmesh.ops.dissolve_degenerate(bm, edges=list(bm.edges), dist=0.002)
    bmesh.ops.triangulate(bm, faces=list(bm.faces))
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    obj = _from_bmesh(name, bm)
    slot(obj, slot_name)
    return box_uv(obj, 2.0)


def import_polyhaven_model(gltf_path, budget, slots, target_size_m):
    """A Poly Haven model (spec 4.6) as one mesh object: imports the gltf headless, joins its meshes with every transform
    applied, decimates it (collapse) to at most `budget` triangles, scales it so its largest dimension is target_size_m,
    puts its bottom centre on the origin, keeps the asset's first UV map, and gives its materials our slots in order (any
    material past the last slot takes the last slot)."""
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=gltf_path)
    new = [o for o in bpy.data.objects if o not in before]
    meshes = [o for o in new if o.type == "MESH"]
    if not meshes:
        raise RuntimeError("%s has no mesh" % gltf_path)
    bpy.context.view_layer.update()
    for o in meshes:  # bake the hierarchy's transforms into the vertices, then detach
        o.data = o.data.copy()
        o.data.transform(o.matrix_world)
        o.parent = None
        o.matrix_world = Matrix.Identity(4)
    for o in new:
        if o not in meshes:
            bpy.data.objects.remove(o, do_unlink=True)
    obj = join(meshes, "polyhaven") if len(meshes) > 1 else meshes[0]
    me = obj.data
    while len(me.uv_layers) > 1:
        me.uv_layers.remove(me.uv_layers[-1])
    me.calc_loop_triangles()
    tris = len(me.loop_triangles)
    for _ in range(6):  # collapse can land a little over its ratio: repeat until within the budget
        if tris <= budget:
            break
        mod = obj.modifiers.new("decimate", "DECIMATE")
        mod.decimate_type = "COLLAPSE"
        mod.ratio = budget / float(tris) * 0.98
        dg = bpy.context.evaluated_depsgraph_get()
        reduced = bpy.data.meshes.new_from_object(obj.evaluated_get(dg))
        obj.modifiers.clear()
        obj.data = reduced
        me = reduced
        me.calc_loop_triangles()
        tris = len(me.loop_triangles)
    if tris > budget:
        raise RuntimeError("%s: %d triangles after decimating, budget %d" % (gltf_path, tris, budget))
    pts = [v.co for v in me.vertices]  # scaled and placed after the decimation, which moves the outline a little
    lo = Vector([min(p[i] for p in pts) for i in range(3)])
    hi = Vector([max(p[i] for p in pts) for i in range(3)])
    k = target_size_m / max(hi - lo)
    me.transform(Matrix.Scale(k, 4) @ Matrix.Translation((-(lo.x + hi.x) / 2, -(lo.y + hi.y) / 2, -lo.z)))
    idx = [p.material_index for p in me.polygons]
    me.materials.clear()
    for n in slots:
        me.materials.append(bpy.data.materials.get(n) or bpy.data.materials.new(n))
    for p, i in zip(me.polygons, idx):
        p.material_index = min(i, len(slots) - 1)
    return obj


def smart_uv(obj):
    """Unwraps every face with Smart UV Project (angle limit 66 degrees, small island margin)."""
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.smart_project(angle_limit=math.radians(66), island_margin=0.02)
    bpy.ops.object.mode_set(mode="OBJECT")
    return obj


def _family(obj):
    """obj and every descendant."""
    out = [obj]
    for c in obj.children:
        out += _family(c)
    return out


def _render_meshes(root):
    return [o for o in _family(root) if o.type == "MESH" and not o.name.startswith(UCX)]


def export(obj, path):
    """Exports obj with its sockets and collision hulls as FBX using FBX_FLAGS."""
    bpy.ops.object.select_all(action="DESELECT")
    for o in _family(obj):
        o.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.export_scene.fbx(filepath=path, **FBX_FLAGS)


def _top_uv(objs, top_z, eps=0.005):
    """UV0 of the top face (the faces facing straight up at the mesh's highest Z): {min, max, along_x, along_y}, where
    along_x is the mean UV of its loops at the +X end minus that at the -X end (along_y the same across Y); None when the
    mesh has no such face or no UVs."""
    loops = []
    for o in objs:
        me = o.data
        if not me.uv_layers:
            continue
        uvs = me.uv_layers.active.data
        rot = o.matrix_world.to_3x3()
        for p in me.polygons:
            if (rot @ p.normal).normalized().z < 0.99:
                continue
            cos = {i: o.matrix_world @ me.vertices[i].co for i in p.vertices}
            if min(c.z for c in cos.values()) < top_z - eps:
                continue
            loops += [(cos[me.loops[li].vertex_index], tuple(uvs[li].uv)) for li in p.loop_indices]
    if not loops:
        return None

    def mean_uv(axis, high):
        edge = max(c[axis] for c, _ in loops) if high else min(c[axis] for c, _ in loops)
        at = [uv for c, uv in loops if abs(c[axis] - edge) <= eps]
        return [sum(uv[k] for uv in at) / len(at) for k in (0, 1)]

    def change(axis):
        hi, lo = mean_uv(axis, True), mean_uv(axis, False)
        return [round(hi[k] - lo[k], 4) for k in (0, 1)]

    return {"min": [round(min(uv[k] for _, uv in loops), 4) for k in (0, 1)],
            "max": [round(max(uv[k] for _, uv in loops), 4) for k in (0, 1)],
            "along_x": change(0), "along_y": change(1)}


def stats(obj):
    """{tris, bounds_cm, min_cm, slots, sockets, socket_axes, has_uv, top_uv} of obj's render meshes (collision hulls are
    not counted). socket_axes: each socket's intended X (forward) and Z (up) unit axes, Blender frame. top_uv: the top
    face's UV range (see _top_uv; the road slab's contract)."""
    bpy.context.view_layer.update()
    tris, slots, has_uv = 0, [], True
    lo, hi = Vector((1e9,) * 3), Vector((-1e9,) * 3)
    for o in _render_meshes(obj):
        me = o.data
        me.calc_loop_triangles()
        tris += len(me.loop_triangles)
        has_uv = has_uv and len(me.uv_layers) > 0
        for m in me.materials:
            if m and m.name not in slots:
                slots.append(m.name)
        for v in me.vertices:
            w = o.matrix_world @ v.co
            lo = Vector((min(lo[i], w[i]) for i in range(3)))
            hi = Vector((max(hi[i], w[i]) for i in range(3)))
    root_inv = obj.matrix_world.inverted()
    sockets, axes = {}, {}
    for o in _family(obj):
        if o.name.startswith(SOCKET):
            p = root_inv @ o.matrix_world.translation
            sockets[o.name[len(SOCKET):]] = [round(c * 100, 3) for c in p]
            if "df_axes" in o:
                x, z = (list(v) for v in o["df_axes"])
                axes[o.name[len(SOCKET):]] = {"x": [round(c, 4) for c in x], "z": [round(c, 4) for c in z]}
    return {"tris": tris, "bounds_cm": [round(c * 100, 3) for c in (hi - lo)], "min_cm": [round(c * 100, 3) for c in lo],
            "slots": slots, "sockets": sockets, "socket_axes": axes, "has_uv": bool(has_uv),
            "top_uv": _top_uv(_render_meshes(obj), hi.z)}


def write_stats(obj, path):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(stats(obj), f, indent=1)
        f.write("\n")


def clear_scene():
    """Removes every object (and orphan data) from the current scene."""
    for o in list(bpy.context.scene.objects):
        bpy.data.objects.remove(o, do_unlink=True)
    for coll in (bpy.data.meshes, bpy.data.materials):
        for d in list(coll):
            if d.users == 0:
                coll.remove(d)


def rename_root(root, name):
    """Names the root `name` and its collision hulls UCX_<name>_NN (Unreal matches hulls to the mesh by that name)."""
    root.name = name
    root.data.name = name
    n = 0
    for c in root.children:
        if c.name.startswith(UCX):
            c.name = "%s%s_%02d" % (UCX, name, n)
            n += 1


def build_mesh(script, name, dims):
    """Imports meshes.<script>, runs build(dims) in the current scene and names the result; shared by run_mesh and the
    previews. A parametric script (one script for several catalogue meshes, e.g. rock for SM_DF_Rock01..04) takes the
    mesh's name as well: build(dims, name)."""
    import importlib
    import sys
    for mod_name in [m for m in sys.modules if m.startswith("meshes.")]:  # shared helpers (carkit) in a live session
        importlib.reload(sys.modules[mod_name])
    mod = importlib.import_module("meshes." + script)
    importlib.reload(mod)
    root = mod.build(dims, name) if mod.build.__code__.co_argcount >= 2 else mod.build(dims)
    rename_root(root, name)
    return root
