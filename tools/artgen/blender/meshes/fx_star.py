"""SM_DF_FxStar: the spiky burst shell (spec 7.1): sparks, a muzzle flash (squashed along X) and the loot burst.

A small core ball with 26 three-sided spikes, one along each axis (50 cm), each cube-edge diagonal (40 cm) and each cube
corner diagonal (32 cm), so the star is 100 cm across and spiky from every side. Each spike's base is turned a little from
its neighbours', so the spikes do not line up. Centred on its origin. Slot: FxFlash (an effect's component overrides it).
"""
import itertools
import math

import bmesh
import bpy
from mathutils import Matrix, Vector

import dfmesh

CORE_M = 0.08
BASE_AT_M, BASE_HALF_M = 0.05, 0.045  # where a spike's triangular base sits, and its corner radius
LENGTHS_M = {1: 0.50, 2: 0.40, 3: 0.32}  # by the number of non-zero axes in the direction


def _spike(bm, direction, length, twist):
    d = direction.normalized()
    side = d.orthogonal().normalized()
    side = Matrix.Rotation(twist, 3, d) @ side
    other = d.cross(side)
    base = [bm.verts.new(d * BASE_AT_M + (side * math.cos(a) + other * math.sin(a)) * BASE_HALF_M)
            for a in (0.0, 2 * math.pi / 3, 4 * math.pi / 3)]
    tip = bm.verts.new(d * length)
    for i in range(3):
        bm.faces.new((base[i], base[(i + 1) % 3], tip))


def build(dims):
    bm = bmesh.new()
    bmesh.ops.create_icosphere(bm, subdivisions=1, radius=CORE_M)
    dirs = [Vector(v) for v in itertools.product((-1, 0, 1), repeat=3) if any(v)]
    for i, d in enumerate(dirs):
        _spike(bm, d, LENGTHS_M[sum(1 for c in d if c)], math.radians(37.0 * i))
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    for f in bm.faces:
        f.smooth = False
    me = bpy.data.meshes.new("SM_DF_FxStar")
    bm.to_mesh(me)
    bm.free()
    obj = bpy.data.objects.new("SM_DF_FxStar", me)
    bpy.context.scene.collection.objects.link(obj)
    dfmesh.slot(obj, "MI_DF_FxFlash")
    return dfmesh.smart_uv(obj)
