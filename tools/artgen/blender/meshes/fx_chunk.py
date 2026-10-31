"""SM_DF_FxChunk: the debris shell (spec 7.1): hot bits and chunks that fly out as BP_DFFx grows the shell.

CHUNKS small, rough blocks (3.5-7 cm: a cube with its corners pushed about, turned at random) spread over a sphere of 40-48 cm
round the origin, more of them above the middle than below (debris kicks up and out). Scaling the shell from StartScale
to EndScale moves every chunk outwards from the centre while it grows. Deterministic (seed SEED). Slot: FxFlash (an
effect's component overrides it).
"""
import math
import random

import bmesh
import bpy
from mathutils import Euler, Vector

import dfmesh

CHUNKS = 14
SEED = 15
RADIUS_M = (0.40, 0.48)
SIZE_M = (0.035, 0.07)  # small against the spread, so they read as bits, not boxes
Z_RANGE = (-0.25, 1.0)  # the directions' height on the unit sphere: from a little below the middle to straight up


def build(dims):
    rng = random.Random(SEED)
    bm = bmesh.new()
    golden = math.pi * (3.0 - math.sqrt(5.0))
    for i in range(CHUNKS):
        z = Z_RANGE[1] - (Z_RANGE[1] - Z_RANGE[0]) * (i + 0.5) / CHUNKS  # spread evenly in height, then round (Fibonacci)
        r = math.sqrt(max(0.0, 1.0 - z * z))
        a = golden * i
        centre = Vector((r * math.cos(a), r * math.sin(a), z)) * rng.uniform(*RADIUS_M)
        size = rng.uniform(*SIZE_M)
        turn = Euler([rng.uniform(0, 2 * math.pi) for _ in range(3)], "XYZ").to_matrix()
        made = bmesh.ops.create_cube(bm, size=1.0)
        for v in made["verts"]:
            jitter = Vector([c * rng.uniform(0.6, 1.25) for c in v.co])
            v.co = centre + turn @ (jitter * size)
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    for f in bm.faces:
        f.smooth = False
    bmesh.ops.triangulate(bm, faces=list(bm.faces))  # the pushed corners leave non-planar quads
    me = bpy.data.meshes.new("SM_DF_FxChunk")
    bm.to_mesh(me)
    bm.free()
    obj = bpy.data.objects.new("SM_DF_FxChunk", me)
    bpy.context.scene.collection.objects.link(obj)
    dfmesh.slot(obj, "MI_DF_FxFlash")
    return dfmesh.smart_uv(obj)
