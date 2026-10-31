"""SM_DF_ShieldBubble: the shield's fresnel bubble round the whole car (spec 6.1, 7.1, 7.5).

A rounded-box shell (a superellipsoid, exponent EXPONENT) centred on its origin, sized from dims.json to hold every
body (the chassis box plus the 15 cm bodies may stand out, BRUTE's extra 40 cm, the wheels down to the ground) with
MARGIN_M to spare. centre(dims) is where its origin goes in the vehicle's actor space (the Blueprint sets that as the
component's relative location). Slot: FxShield.
"""
import bmesh
import bpy

import dfmesh

SEGMENTS, RINGS = 18, 10
EXPONENT = 3.4   # with MARGIN_M: the boxiest-but-still-a-bubble shell that holds every body, its wheels
MARGIN_M = 0.38  # and both roof weapons (worst superellipsoid norm 0.96 in the Task 12 fit check)
BODY_TOL_M, BRUTE_RISE_M = 0.15, 0.40


def extent(dims):
    """(min, max) corners in metres, Blender frame, of the space the bodies and wheels may fill."""
    b = dims["body_box"]
    lo = [b["min"][0] / 100 - BODY_TOL_M, -b["max"][1] / 100 - BODY_TOL_M, 0.0]
    hi = [b["max"][0] / 100 + BODY_TOL_M, -b["min"][1] / 100 + BODY_TOL_M, b["max"][2] / 100 + BRUTE_RISE_M]
    ground = min(p[2] for p in dims["wheels"].values()) / 100 - dims["wheel_radius"] / 100
    lo[2] = ground
    return lo, hi


def centre(dims):
    """The bubble's centre in Unreal actor space, cm (x, y, z)."""
    lo, hi = extent(dims)
    return [round((lo[0] + hi[0]) * 50, 1), 0.0, round((lo[2] + hi[2]) * 50, 1)]


def build(dims):
    lo, hi = extent(dims)
    semi = [(h - l) / 2 + MARGIN_M for l, h in zip(lo, hi)]
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=SEGMENTS, v_segments=RINGS, radius=1.0)
    for v in bm.verts:  # push each vertex along its ray onto the superellipsoid
        d = v.co.normalized()
        s = sum(abs(d[i] / semi[i]) ** EXPONENT for i in range(3)) ** (-1.0 / EXPONENT)
        v.co = d * s
    for f in bm.faces:
        f.smooth = False
    me = bpy.data.meshes.new("SM_DF_ShieldBubble")
    bm.to_mesh(me)
    bm.free()
    obj = bpy.data.objects.new("SM_DF_ShieldBubble", me)
    bpy.context.scene.collection.objects.link(obj)
    dfmesh.slot(obj, "MI_DF_FxShield")
    dfmesh.smart_uv(obj)
    return obj
