"""Headless fallback for the live review (spec 4.7): renders Workbench views of one mesh next to a 1.8 m reference figure.

    blender -b --factory-startup --python preview.py -- --script <s> --name <n> --out <dir>
            [--with-wheels] [--attach <script>:<name>:<socket> ...] [--reference <fbx>] [--far <metres>]

Loads tools/artgen/data/dims.json like run_mesh does. --with-wheels places SM_DF_Wheel (meshes.wheel) at every
dims["wheels"] bone, the right ones yawed 180 (dfmesh.place_wheels, shared with preview_live). --attach builds another
mesh and puts its origin on one of the main mesh's sockets (e.g. light_bar:SM_DF_LightBar:Roof).
--reference imports an FBX that Unreal exported (e.g. art/reference/RampLarge.fbx, df_export_dims.py), prints a REFERENCE
line with the furthest any reference vertex lies from the mesh's surface and any mesh vertex from the reference's (both at
the same origin), and shows it in magenta beside the mesh, moved along +Y: in the front and top views the two stand side
by side, and in the side view the mesh hides it wherever their outlines agree (magenta shows only where they differ).
--far adds a far view: the persp direction from that many metres with a 50 mm lens, the size a player sees it at.
--place script:name:x,y,z[:sx,sy,sz] builds another mesh with its origin at that point (metres, Blender frame) and that
scale, e.g. a gate's two pylons and its banner stretched between them round a car.
Faces are coloured by material slot (the catalogue's colours), so paint, trim, glass, dark and lights read apart.

Writes <dir>/<name>_<view>.png at 768 x 768 for front, side, top, persp and rear (and far). The mesh faces +X: front looks
at its nose from +X, side looks from -Y (the nose points right), top looks down (the nose points right), persp is a
three-quarter view from the front left, rear a three-quarter view from behind and above (a chase camera).
The reference figure stands off the front-right corner, clear of the side and front views.
"""
import argparse
import json
import math
import os
import sys

import bpy
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(os.path.dirname(HERE)))
import dfmesh  # noqa: E402

DIMS = os.path.join(os.path.dirname(HERE), "data", "dims.json")
SIZE = 768
VIEWS = ("front", "side", "top", "persp", "rear")


def _human(height_m=1.8, radius_m=0.22):
    import bmesh
    bm = bmesh.new()
    cyl = height_m - 2 * radius_m
    bmesh.ops.create_cone(bm, cap_ends=True, segments=16, radius1=radius_m, radius2=radius_m, depth=cyl)
    bmesh.ops.translate(bm, vec=(0, 0, radius_m + cyl / 2), verts=bm.verts)
    for z in (radius_m, height_m - radius_m):
        ret = bmesh.ops.create_uvsphere(bm, u_segments=16, v_segments=8, radius=radius_m)
        bmesh.ops.translate(bm, vec=(0, 0, z), verts=ret["verts"])
    me = bpy.data.meshes.new("REF_Human")
    bm.to_mesh(me)
    bm.free()
    obj = bpy.data.objects.new("REF_Human", me)
    bpy.context.scene.collection.objects.link(obj)
    return obj


def slot_colours():
    """{MI name: (r, g, b, 1)} viewport colours from the catalogue (linear), for material-coloured previews."""
    try:
        from artgen import catalog
    except ImportError:
        return {}
    out = {}
    for mi in catalog.MATERIALS:
        c = mi.vectors.get("PaintColor") or mi.vectors.get("Tint") or mi.vectors.get("Color")
        if c:
            out[mi.name] = tuple(c[:3]) + (1.0,)
    return out


def colour_materials():
    cols = slot_colours()
    for m in bpy.data.materials:
        m.diffuse_color = cols.get(m.name, (0.8, 0.55, 0.3, 1.0))


def _camera(kind, centre, span, subject=None, far_m=None):
    """The orthographic views frame (centre, span) - the subject and the figure; the perspective views frame
    subject = (centre, span) of the subject alone; far looks along the persp direction from far_m metres."""
    if subject is not None and kind in ("persp", "rear", "far"):
        centre, span = subject
    cam = bpy.data.objects.new("Cam_" + kind, bpy.data.cameras.new("Cam_" + kind))
    bpy.context.scene.collection.objects.link(cam)
    d = span * 3
    p = span * 2.0  # the perspective views (50 mm lens) frame the subject at about this distance
    # (offset from the centre, euler rotation); a camera looks down its -Z with +Y up.
    views = {
        "front": ((d, 0, 0), (math.radians(90), 0, math.radians(90))),
        "side": ((0, -d, 0), (math.radians(90), 0, 0)),
        "top": ((0, 0, d), (0, 0, 0)),
        "persp": ((p * 0.7, p * 0.7, p * 0.45), None),
        "rear": ((-p * 0.8, -p * 0.45, p * 0.35), None),
        "far": (Vector((0.7, 0.7, 0.45)).normalized() * (far_m or 20.0), None),
    }
    off, rot = views[kind]
    cam.location = centre + Vector(off)
    if rot is None:
        cam.rotation_euler = (centre - cam.location).to_track_quat("-Z", "Y").to_euler()
        cam.data.lens = 50
    else:
        cam.rotation_euler = rot
        cam.data.type = "ORTHO"
        cam.data.ortho_scale = span * 1.15
    cam.data.clip_end = max(d * 4, (far_m or 0.0) * 3)
    return cam


def load_dims():
    if os.path.isfile(DIMS):
        with open(DIMS, encoding="utf-8") as f:
            return json.load(f)
    return {}


def socket_location(root, name):
    for o in dfmesh._family(root):
        if o.name == dfmesh.SOCKET + name:
            return o.matrix_world.translation.copy()
    raise KeyError("%s has no socket %s" % (root.name, name))


def attach(root, spec, dims):
    """Builds script:name and puts its origin on the root's socket; returns the new root."""
    script, name, sock = spec.split(":")
    bpy.context.view_layer.update()
    loc = socket_location(root, sock)
    other = dfmesh.build_mesh(script, name, dims)
    other.location = loc
    return other


def place(spec, dims):
    """Builds script:name and puts its origin at x,y,z with the scale sx,sy,sz when given; returns it."""
    parts = spec.split(":")
    other = dfmesh.build_mesh(parts[0], parts[1], dims)
    other.location = [float(v) for v in parts[2].split(",")]
    if len(parts) > 3:
        other.scale = [float(v) for v in parts[3].split(",")]
    return other


REF_COLOUR = (1.0, 0.0, 1.0, 1.0)


def reference(path, root):
    """Imports an Unreal FBX export as one object, prints how far its vertices lie from the mesh's surface and the mesh's
    from its surface (cm) with both at the origin, then moves it beside the mesh along +Y. Returns the object."""
    from mathutils.bvhtree import BVHTree
    before = set(bpy.data.objects)
    bpy.ops.import_scene.fbx(filepath=path)
    new = [o for o in bpy.data.objects if o not in before]
    meshes = [o for o in new if o.type == "MESH"]
    bpy.context.view_layer.update()
    for o in meshes:  # Unreal's export carries a 0.01 object scale over centimetre vertices: bake it
        o.data.transform(o.matrix_world)
        o.parent = None
        o.matrix_world.identity()
    for o in new:
        if o not in meshes:
            bpy.data.objects.remove(o, do_unlink=True)
    ref = dfmesh.join(meshes, "REF_" + os.path.splitext(os.path.basename(path))[0]) if len(meshes) > 1 else meshes[0]
    ref.name = "REF_" + os.path.splitext(os.path.basename(path))[0]
    bpy.context.view_layer.update()
    dg = bpy.context.evaluated_depsgraph_get()
    tree_mesh, tree_ref = BVHTree.FromObject(root, dg), BVHTree.FromObject(ref, dg)

    def furthest(points, tree):
        return max(((tree.find_nearest(p)[3] or 0.0) for p in points), default=0.0) * 100

    mesh_pts = [root.matrix_world @ v.co for v in root.data.vertices]
    ref_pts = [v.co.copy() for v in ref.data.vertices]
    print("REFERENCE %s: reference vertices within %.2f cm of the mesh; mesh vertices within %.2f cm of the reference"
          % (ref.name, furthest(ref_pts, tree_mesh), furthest(mesh_pts, tree_ref)))
    ref.data.materials.clear()
    ref.data.materials.append(bpy.data.materials.new("REF_Original"))
    ref.location.y = max(p.y for p in mesh_pts) - min(p.y for p in ref_pts) + 0.5
    return ref


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--script", required=True)
    ap.add_argument("--name", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--with-wheels", action="store_true")
    ap.add_argument("--attach", action="append", default=[])
    ap.add_argument("--reference")
    ap.add_argument("--far", type=float)
    ap.add_argument("--place", action="append", default=[])
    a = ap.parse_args(sys.argv[sys.argv.index("--") + 1:])
    a.out = os.path.abspath(a.out)  # a relative render path does not resolve against the working directory
    os.makedirs(a.out, exist_ok=True)
    dfmesh.clear_scene()
    dims = load_dims()
    root = dfmesh.build_mesh(a.script, a.name, dims)
    shown = [root]
    if a.with_wheels:
        wheel = dfmesh.build_mesh("wheel", "SM_DF_Wheel", dims)
        shown += dfmesh.place_wheels(wheel, dims, bpy.context.scene.collection.objects.link)
        bpy.data.objects.remove(wheel, do_unlink=True)
    for spec in a.attach:
        shown.append(attach(root, spec, dims))
    for spec in a.place:
        shown.append(place(spec, dims))
    ref = reference(a.reference, root) if a.reference else None
    if ref is not None:
        shown.append(ref)
    bpy.context.view_layer.update()
    pts = []
    for o in shown:
        pts += [o.matrix_world @ Vector(c) for c in o.bound_box]
    lo = Vector((min(p[i] for p in pts) for i in range(3)))
    hi = Vector((max(p[i] for p in pts) for i in range(3)))
    subject = ((lo + hi) / 2, max(hi - lo))
    human = _human()
    human.location = (hi.x + 0.5, lo.y - 0.5, 0.0)
    bpy.context.view_layer.update()
    pts += [human.matrix_world @ Vector(c) for c in human.bound_box]
    lo = Vector((min(p[i] for p in pts) for i in range(3)))
    hi = Vector((max(p[i] for p in pts) for i in range(3)))
    centre, span = (lo + hi) / 2, max(hi - lo)

    sc = bpy.context.scene
    sc.render.engine = "BLENDER_WORKBENCH"
    sc.render.resolution_x = sc.render.resolution_y = SIZE
    sc.render.resolution_percentage = 100
    sc.display.shading.light = "STUDIO"
    sc.display.shading.color_type = "MATERIAL"
    sc.display.shading.show_cavity = True
    sc.render.film_transparent = False
    colour_materials()
    if ref is not None:
        ref.data.materials[0].diffuse_color = REF_COLOUR
    human.data.materials.append(bpy.data.materials.new("REF_Human"))
    human.data.materials[0].diffuse_color = (0.3, 0.6, 0.9, 1)
    for o in bpy.context.scene.objects:
        if o.name.startswith(dfmesh.UCX):
            o.hide_render = True
    world = bpy.data.worlds.new("PreviewWorld")
    world.color = (0.18, 0.18, 0.2)
    sc.world = world
    for view in VIEWS + (("far",) if a.far else ()):
        cam = _camera(view, centre, span, subject, a.far)
        sc.camera = cam
        sc.render.filepath = os.path.join(a.out, "%s_%s.png" % (a.name, view))
        bpy.ops.render.render(write_still=True)
    print("PREVIEW_PNG OK %s" % a.name)


main()
