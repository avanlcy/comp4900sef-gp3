"""SM_DF_CarWreck: a burnt-out car for the scatter (spec 8.3), built from SM_DF_Car_Sedan's own code (car_sedan.build, not a
copy), so it is the same car the player drives, after a fire.

The sedan body loses its sockets and its five slots fold into two: paint and trim become Paint_Charred
(MI_DF_Paint_Charred, the wrecked-car material, spec 6.1), glass and lights go Dark (burnt out). Its long panels are split
so they can buckle; it is dented (DENTS: the front corner crushed back, the doors stove in, the roof caved, the hood
buckled, the rear quarter and corner pushed in) and the whole shell crumpled a little by noise. The tyres have burnt away:
it rests on three dark steel rims (the front-left one is gone), so it sits low and tips onto that corner. Origin at the
bottom centre under the car's middle. Collision: the auto box (an 18-DOP round the shell). Slots: Paint_Charred, Dark.
"""
import math

import bmesh
import bpy
from mathutils import Matrix, Vector, noise

import dfmesh
from meshes import car_sedan
from meshes import carkit as ck

CHARRED, DARK = "MI_DF_Paint_Charred", "MI_DF_Dark"
RENAME = {car_sedan.PAINT: CHARRED, ck.TRIM: CHARRED, ck.GLASS: DARK, ck.LIGHTS: DARK}
SEED = 2050             # mathutils.noise.noise_vector reads a random offset that differs per process unless seeded
SPLIT_M = 0.45          # edges longer than this are split once, so the panels can buckle
CRUMPLE_M = 0.035       # the noise's push on every vertex
RIM_R, RIM_W = 0.25, 0.16
LOST_RIM = "Wheel_Front_Left"
TILT_DEG = (-3.5, 2.0)  # roll (left side down) and pitch (nose down), degrees
# (centre metres in the sedan's frame, push direction, radius m, depth m)
DENTS = [((2.35, 0.55, 0.65), (-1.0, -0.25, -0.3), 0.90, 0.34),   # front-left corner crushed back
         ((0.25, 0.92, 0.62), (0.0, -1.0, 0.0), 0.90, 0.16),      # left doors stove in
         ((-1.05, -0.92, 0.55), (0.0, 1.0, 0.0), 0.65, 0.12),     # right rear quarter
         ((-0.35, 0.10, 1.50), (0.0, 0.0, -1.0), 0.80, 0.20),     # roof caved
         ((1.40, -0.30, 0.95), (0.0, 0.0, 1.0), 0.55, 0.08),      # the hood buckled up
         ((-2.25, -0.35, 0.75), (1.0, 0.1, -0.1), 0.60, 0.14)]    # rear corner


def _buckle(obj):
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    long_edges = [e for e in bm.edges if e.calc_length() > SPLIT_M]
    bmesh.ops.subdivide_edges(bm, edges=long_edges, cuts=1, use_grid_fill=True)
    bmesh.ops.triangulate(bm, faces=[f for f in bm.faces if len(f.verts) > 4])
    noise.seed_set(SEED)
    for v in bm.verts:
        for c, d, r, depth in DENTS:
            dist = (v.co - Vector(c)).length
            if dist < r:
                v.co += Vector(d).normalized() * depth * (1.0 - dist / r) ** 2
        v.co += noise.noise_vector(v.co * 2.5 + Vector((7.1, 3.3, 1.9)), noise_basis="PERLIN_ORIGINAL") * CRUMPLE_M
    bm.to_mesh(obj.data)
    bm.free()


def build(dims):
    body = car_sedan.build(dims)
    for c in list(body.children):  # the sockets: a wreck carries none
        bpy.data.objects.remove(c, do_unlink=True)
    dfmesh.order_slots(body, [CHARRED, DARK], rename=RENAME)
    _buckle(body)
    rims = []
    for bone, (x, y, z) in ck.wheels(dims).items():
        if bone == LOST_RIM:
            continue
        rim_y = math.copysign(abs(y) + 0.10, y)
        rims.append(dfmesh.box_uv(dfmesh.part(dfmesh.cylinder("rim", RIM_R, RIM_W, 14, loc=(x, rim_y, z), axis="Y"), DARK), 1.0))
    root = dfmesh.assemble([body] + rims, "SM_DF_CarWreck", [CHARRED, DARK], unwrap=False)
    bone_z = next(iter(ck.wheels(dims).values()))[2]
    roll, pitch = (math.radians(a) for a in TILT_DEG)
    root.data.transform(Matrix.Rotation(pitch, 4, "Y") @ Matrix.Rotation(roll, 4, "X") @ Matrix.Translation((0, 0, RIM_R - bone_z)))
    dfmesh.ground(root)
    return root
