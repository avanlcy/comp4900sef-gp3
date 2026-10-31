"""SM_DF_RoadSlab: the road (spec 8.2), laid by BP_DFTrackSpline as one spline mesh per piece of the track.

It keeps the engine cube's unit contract: a 100 cm box centred on the origin, so the track's scaling (RoadWidth and
RoadThickness over MeshNativeSize 100) and its offset are unchanged. It is cut into SEGMENTS steps along X, so a piece bends
with the spline instead of running straight from end to end. UV0 is M_DF_Road's: on the top face U runs 0..1 along X (the
piece; four centre-line dashes per piece) and V 0..1 across Y (edge lines and kerbs at V 0 and 1). The sides carry the kerb
edge of the V range down them and the ends the U edge, each over a thin band, so no face has a zero-area UV (Unreal builds
the tangents from UV0). Collision: the auto box (the cube's). Slot: Road.
"""
import bmesh

import dfmesh

SLOT = "MI_DF_Road"
SEGMENTS = 8
BAND = 0.02  # the UV band a side or an end face spans


def _uv(co, n):
    x, y, z = co.x + 0.5, co.y + 0.5, co.z + 0.5  # 0..1 over the unit box
    if abs(n.z) > 0.9:  # top and bottom
        return x, y
    if abs(n.y) > 0.9:  # the sides: the kerb edge of V
        return x, (BAND * z if n.y < 0 else 1.0 - BAND * z)
    return (BAND * z if n.x < 0 else 1.0 - BAND * z), y  # the ends: the U edge


def build(dims):
    obj = dfmesh.extrude_x("SM_DF_RoadSlab", [(-0.5, -0.5), (0.5, -0.5), (0.5, 0.5), (-0.5, 0.5)], [SLOT], segments=SEGMENTS)
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bm.normal_update()
    layer = bm.loops.layers.uv.verify()
    for f in bm.faces:
        for loop in f.loops:
            loop[layer].uv = _uv(loop.vert.co, f.normal)
    bm.to_mesh(obj.data)
    bm.free()
    return obj
