"""SM_DF_FxSphere: the round effect shell (spec 7.1): fireballs, flashes and smoke puffs of the BP_DFFx family.

A 100 cm icosphere (three subdivisions, 320 flat faces: a low-poly ball that still reads round), centred on its origin.
UVs: a top-down planar projection into the middle of the texture, U, V = 0.5 + UV_SPREAD * (x, y) / radius: on the smoke
master (MI_DF_FxSmoke / FxPuff) the ball samples only the puff texture's dense middle, so it is an evenly translucent ball
with a soft light-and-billow shading and no seam (a wider spread stretched the texture into streaks at the sides in the
look-dev capture); the additive master ignores the UVs (its Mask is white).
Slot: FxFlash (an effect's component overrides it).
"""
import bmesh
import bpy

import dfmesh

RADIUS_M = 0.5
SUBDIVISIONS = 3
UV_SPREAD = 0.15  # the equator lands at 0.3 of the texture's radius: only the dense middle, no streaks at the sides


def build(dims):
    bm = bmesh.new()
    bmesh.ops.create_icosphere(bm, subdivisions=SUBDIVISIONS, radius=RADIUS_M)
    uv = bm.loops.layers.uv.new("UVMap")
    for f in bm.faces:
        f.smooth = False
        for loop in f.loops:
            co = loop.vert.co
            loop[uv].uv = (0.5 + UV_SPREAD * co.x / RADIUS_M, 0.5 + UV_SPREAD * co.y / RADIUS_M)
    me = bpy.data.meshes.new("SM_DF_FxSphere")
    bm.to_mesh(me)
    bm.free()
    obj = bpy.data.objects.new("SM_DF_FxSphere", me)
    bpy.context.scene.collection.objects.link(obj)
    return dfmesh.slot(obj, "MI_DF_FxFlash")
