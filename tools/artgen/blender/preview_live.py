"""Live review in the person's Blender, run through the MCP execute_blender_code (spec 4.5):

    exec(open(r"<REPO>/tools/artgen/blender/preview_live.py").read())
    preview("barrel", "SM_DF_Barrel")
    ...
    restore()

preview() builds into the scene DF_Preview and never touches any other scene; restore() switches the window back.
"""
import importlib
import json
import math
import os
import sys

import bmesh
import bpy

_FILE = globals().get("__file__")  # absent when the MCP runs this through exec
REPO = "E:/VSC projects/comp4900sef-gp3"
if _FILE and os.path.isdir(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(_FILE))))), "tools", "artgen")):
    REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(_FILE)))))
BLENDER_DIR = os.path.join(REPO, "tools", "artgen", "blender")
DIMS = os.path.join(REPO, "tools", "artgen", "data", "dims.json")
SCENE = "DF_Preview"
MEMORY = "df_preview_original_scene"  # key in bpy.app.driver_namespace


def _window():
    wins = bpy.context.window_manager.windows
    return wins[0] if wins else None


def _show(scene):
    win = _window()
    if win is not None:
        win.scene = scene


def _human_obj(name="REF_Human", height_m=1.8, radius_m=0.22):
    """A capsule (cylinder with a sphere at each end) standing on z = 0."""
    bm = bmesh.new()
    cyl = height_m - 2 * radius_m
    bmesh.ops.create_cone(bm, cap_ends=True, segments=16, radius1=radius_m, radius2=radius_m, depth=cyl)
    bmesh.ops.translate(bm, vec=(0, 0, radius_m + cyl / 2), verts=bm.verts)
    for z in (radius_m, height_m - radius_m):
        ret = bmesh.ops.create_uvsphere(bm, u_segments=16, v_segments=8, radius=radius_m)
        bmesh.ops.translate(bm, vec=(0, 0, z), verts=ret["verts"])
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    return bpy.data.objects.new(name, me)


def _frame(objs):
    """Frames the 3D views of the window on objs (no-op without a 3D view, e.g. headless)."""
    win = _window()
    if win is None:
        return
    for o in bpy.context.view_layer.objects:
        o.select_set(o in objs)
    for area in win.screen.areas:
        if area.type == "VIEW_3D":
            region = next((r for r in area.regions if r.type == "WINDOW"), None)
            with bpy.context.temp_override(window=win, area=area, region=region):
                bpy.ops.view3d.view_selected()


def preview(script, name, with_wheels=False, attach=()):
    """Builds meshes.<script> as `name` in the DF_Preview scene next to a 1.8 m reference figure and prints a PREVIEW line.
    with_wheels places SM_DF_Wheel at the dims.json wheel bones (dfmesh.place_wheels, as preview.py --with-wheels);
    attach = ["script:name:socket", ...] builds more meshes onto the main mesh's sockets (as preview.py --attach)."""
    if BLENDER_DIR not in sys.path:
        sys.path.insert(0, BLENDER_DIR)
    ns = bpy.app.driver_namespace
    if MEMORY not in ns:
        win = _window()
        ns[MEMORY] = (win.scene if win is not None else bpy.context.scene).name
    scene = bpy.data.scenes.get(SCENE) or bpy.data.scenes.new(SCENE)
    for o in list(scene.objects):
        bpy.data.objects.remove(o, do_unlink=True)
    for c in list(scene.collection.children):
        scene.collection.children.unlink(c)
        bpy.data.collections.remove(c)
    _show(scene)
    coll = bpy.data.collections.new("DF_Preview_Collection")
    scene.collection.children.link(coll)

    import dfmesh
    importlib.reload(dfmesh)
    importlib.import_module("meshes")
    dims = {}
    if os.path.isfile(DIMS):
        with open(DIMS, encoding="utf-8") as f:
            dims = json.load(f)
    # The helpers link new objects into bpy.context.scene, which follows the window scene set above; in headless
    # runs (no window to follow) the scene is made current through the window of the factory startup file.
    before = set(scene.objects)
    root = dfmesh.build_mesh(script, name, dims)
    if with_wheels:
        wheel = dfmesh.build_mesh("wheel", "SM_DF_Wheel", dims)
        dfmesh.place_wheels(wheel, dims, scene.collection.objects.link)
        bpy.data.objects.remove(wheel, do_unlink=True)
    for spec in attach:
        a_script, a_name, a_socket = spec.split(":")
        bpy.context.view_layer.update()
        loc = next(o for o in dfmesh._family(root) if o.name == dfmesh.SOCKET + a_socket).matrix_world.translation.copy()
        dfmesh.build_mesh(a_script, a_name, dims).location = loc
    made = [o for o in scene.objects if o not in before]
    for o in made:
        for c in list(o.users_collection):
            c.objects.unlink(o)
        coll.objects.link(o)
    human = _human_obj()
    human.location = (0, -2.0, 0)
    coll.objects.link(human)
    s = dfmesh.stats(root)
    print("PREVIEW %s tris=%d bounds_cm=%s sockets=%s" % (name, s["tris"], ",".join("%g" % b for b in s["bounds_cm"]), ",".join(s["sockets"]) or "-"))
    _frame([root, human])


def restore():
    """Switches the window back to the scene that was active before the first preview (DF_Preview is kept for the next one)."""
    ns = bpy.app.driver_namespace
    scene = bpy.data.scenes.get(ns.get(MEMORY, ""))
    if scene is None:
        print("RESTORE nothing to restore")
        return
    _show(scene)
    del ns[MEMORY]
    print("RESTORE scene=%s" % scene.name)
