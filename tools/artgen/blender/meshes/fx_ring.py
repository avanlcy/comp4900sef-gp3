"""SM_DF_FxRing: the ring effect shell (spec 7.1): a shockwave or a burst ring that spreads out as BP_DFFx grows it.

A flat band in the XY plane (it lies on the ground; an effect pitches the component for an upright ring), 100 cm across
and 6 cm tall, its inner edge at 40 cm from the centre, with a rectangular cross-section of SEGMENTS steps. Centred on its
origin. UVs: U around the ring, V across its four faces. Slot: FxFlash (an effect's component overrides it).
"""
import math

import bmesh
import bpy

import dfmesh

R_OUT_M, R_IN_M, HEIGHT_M = 0.50, 0.40, 0.06
SEGMENTS = 24


def build(dims):
    bm = bmesh.new()
    section = [(R_IN_M, -HEIGHT_M / 2), (R_OUT_M, -HEIGHT_M / 2), (R_OUT_M, HEIGHT_M / 2), (R_IN_M, HEIGHT_M / 2)]
    rings = []
    for k in range(SEGMENTS):
        a = 2 * math.pi * k / SEGMENTS
        rings.append([bm.verts.new((r * math.cos(a), r * math.sin(a), z)) for r, z in section])
    uv = bm.loops.layers.uv.new("UVMap")
    for k in range(SEGMENTS):
        ra, rb = rings[k], rings[(k + 1) % SEGMENTS]
        for s in range(4):
            s1 = (s + 1) % 4
            f = bm.faces.new((ra[s], rb[s], rb[s1], ra[s1]))
            f.smooth = False
            corners = {ra[s]: (k, s), rb[s]: (k + 1, s), rb[s1]: (k + 1, s + 1), ra[s1]: (k, s + 1)}
            for loop in f.loops:
                u, v = corners[loop.vert]
                loop[uv].uv = (u / SEGMENTS, v / 4.0)
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    me = bpy.data.meshes.new("SM_DF_FxRing")
    bm.to_mesh(me)
    bm.free()
    obj = bpy.data.objects.new("SM_DF_FxRing", me)
    bpy.context.scene.collection.objects.link(obj)
    return dfmesh.slot(obj, "MI_DF_FxFlash")
