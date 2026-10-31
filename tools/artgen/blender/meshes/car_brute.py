"""SM_DF_Car_Brute: the armoured pickup (spec 3, 6.1): gunmetal, a tall boxy cab with slit windows behind plates and
windshield bars, an open bed with a roll cage, bolted door plates, dark fender flares, a heavy bull bar with lamps and
a snorkel. Taller than the others (test_meshes lets it rise 40 cm over the chassis box).
Built to dims.json; see carkit for the frame, slots and sockets.
"""
import math

import dfmesh
from meshes import carkit as ck

PAINT = "MI_DF_Paint_Brute"
W = 0.88
Z0 = 0.26
BED_FLOOR, BED_TOP, BED_FRONT, BED_REAR = 0.86, 1.14, -0.52, -2.20
UPPER = [(2.22, Z0), (2.28, 0.45), (2.28, 0.98), (2.18, 1.08), (0.80, 1.12), (BED_FRONT + 0.02, 1.12),
         (BED_FRONT, BED_FLOOR), (BED_REAR + 0.06, BED_FLOOR), (BED_REAR, 0.80), (-2.23, 0.45), (-2.17, Z0)]
CAB_BOTTOM = (BED_FRONT, 0.80, 0.86, 1.10)
CAB_TOP = (-0.46, 0.34, 0.80, 1.78)
ROOF = ((CAB_TOP[0] + CAB_TOP[1]) / 2, 0.0, CAB_TOP[3])
EXHAUST = (-2.32, 0.45, 0.32)
CAGE_X, CAGE_TOP = -0.66, 1.86


def _windshield_point(f, out=0.02):
    """A point a fraction f up the windshield, `out` metres off the glass."""
    (bx0, bx1, bw, bz), (tx0, tx1, tw, tz) = CAB_BOTTOM, CAB_TOP
    run, rise = bx1 - tx1, tz - bz
    n = math.hypot(run, rise)
    return bx1 - run * f + out * rise / n, bz + rise * f + out * run / n


def build(dims):
    outline, slots = ck.side_outline(dims, Z0, UPPER)
    parts = [dfmesh.profile("body", outline, W, [PAINT, ck.DARK], slots, bevel_m=0.03, segments=2)]
    parts.append(dfmesh.frustum("cab", CAB_BOTTOM, CAB_TOP, [PAINT, ck.GLASS], bevel_m=0.025, segments=2,
                                glass=(1, 0.09, 0.012)))
    parts += ck.well_liners(dims, Z0)
    parts += ck.flares(dims, ck.DARK, W, Z0, width_m=0.10, thick_m=0.06)
    parts.append(ck.box((1.80, 1.40, 0.05), (0.02, 0.0, 0.245), ck.DARK))                       # undertray
    # bed: side walls, tailgate, cargo (toolbox, two white jerry cans)
    bed_len = BED_FRONT - BED_REAR
    parts += ck.mirrored(lambda s: ck.box((bed_len, 0.06, BED_TOP - BED_FLOOR + 0.02),
                                          ((BED_FRONT + BED_REAR) / 2, s * (W - 0.03), (BED_TOP + BED_FLOOR) / 2), PAINT, bevel=0.012))
    parts.append(ck.box((0.06, 2 * W, BED_TOP - 0.78), (BED_REAR + 0.03, 0.0, (BED_TOP + 0.78) / 2), PAINT, bevel=0.012))
    parts.append(ck.box((0.30, 1.50, 0.22), (BED_FRONT - 0.22, 0.0, BED_FLOOR + 0.11), ck.DARK, bevel=0.015))
    parts += [ck.box((0.16, 0.10, 0.24), (-1.70, s * 0.62, BED_FLOOR + 0.12), ck.TRIM, bevel=0.012) for s in (1, -1)]
    # roll cage over the bed
    for s in (1, -1):
        parts.append(dfmesh.tube("cage", (CAGE_X, s * 0.80, BED_TOP), (CAGE_X, s * 0.80, CAGE_TOP), 0.04, [ck.DARK]))
        parts.append(dfmesh.tube("brace", (CAGE_X, s * 0.80, CAGE_TOP - 0.02), (-1.95, s * 0.80, BED_TOP), 0.035, [ck.DARK]))
    parts.append(dfmesh.tube("cage", (CAGE_X, 0.84, CAGE_TOP), (CAGE_X, -0.84, CAGE_TOP), 0.04, [ck.DARK]))
    parts.append(dfmesh.tube("cage", (CAGE_X, 0.84, CAGE_TOP - 0.30), (CAGE_X, -0.84, CAGE_TOP - 0.30), 0.03, [ck.DARK]))
    # armour: door plates with bolts and a white stripe, cab window plates (slit windows), windshield bars
    for s in (1, -1):
        parts.append(ck.box((1.36, 0.03, 0.62), (0.23, s * (W + 0.012), 0.72), PAINT, bevel=0.012))
        parts.append(ck.box((1.30, 0.012, 0.045), (0.23, s * (W + 0.03), 0.98), ck.TRIM))
        for x in (-0.38, 0.84):
            for z in (0.47, 0.92):
                parts.append(ck.box((0.035, 0.02, 0.035), (x, s * (W + 0.03), z), ck.DARK))
        parts.append(ck.box((1.10, 0.045, 0.30), (0.10, s * 0.852, 1.26), PAINT, bevel=0.01))
    for f in (0.30, 0.62):
        x, z = _windshield_point(f)
        parts.append(ck.box((0.035, 1.56, 0.035), (x, 0.0, z), ck.DARK))
    x, z = _windshield_point(0.5)
    parts.append(ck.box((0.035, 0.035, 0.82), (x, 0.0, z), ck.DARK, rot_deg=(0, -math.degrees(math.atan2(0.46, 0.68)), 0)))
    # front: bumper, grille, headlights; bull bar with two lamps
    parts.append(ck.box((0.20, 1.80, 0.26), (2.26, 0.0, 0.36), ck.DARK, bevel=0.03))
    parts.append(ck.box((0.04, 0.80, 0.36), (2.285, 0.0, 0.74), ck.DARK))
    parts += ck.mirrored(lambda s: ck.box((0.04, 0.24, 0.14), (2.28, s * 0.62, 0.84), ck.LIGHTS, bevel=0.012))
    for s in (1, -1):
        parts.append(dfmesh.tube("bull", (2.31, s * 0.55, 0.30), (2.38, s * 0.55, 1.05), 0.035, [ck.DARK]))
        parts.append(dfmesh.tube("bull", (2.37, s * 0.20, 0.42), (2.38, s * 0.20, 1.05), 0.025, [ck.DARK]))
        parts.append(dfmesh.tube("mount", (2.20, s * 0.55, 0.62), (2.36, s * 0.55, 0.62), 0.03, [ck.DARK]))
        parts.append(dfmesh.tube("lamp", (2.30, s * 0.34, 1.16), (2.385, s * 0.34, 1.16), 0.075, [ck.DARK], verts=10))
        parts.append(dfmesh.tube("lens", (2.385, s * 0.34, 1.16), (2.40, s * 0.34, 1.16), 0.06, [ck.LIGHTS], verts=10))
    parts.append(dfmesh.tube("bull", (2.38, 0.62, 1.05), (2.38, -0.62, 1.05), 0.035, [ck.DARK]))
    parts.append(dfmesh.tube("bull", (2.37, 0.70, 0.46), (2.37, -0.70, 0.46), 0.035, [ck.DARK]))
    # rear: bumper, tail lights, exhausts
    parts.append(ck.box((0.18, 1.80, 0.22), (-2.22, 0.0, 0.40), ck.DARK, bevel=0.03))
    parts += ck.mirrored(lambda s: ck.box((0.04, 0.10, 0.26), (-2.235, s * 0.80, 0.97), ck.LIGHTS, bevel=0.01))
    for s in (1, -1):
        parts.append(dfmesh.tube("exhaust", (-2.18, s * EXHAUST[1], EXHAUST[2]), (EXHAUST[0], s * EXHAUST[1], EXHAUST[2]),
                                 0.05, [ck.DARK], verts=10))
    # mirrors, snorkel (right A-pillar)
    for s in (1, -1):
        parts.append(dfmesh.tube("stalk", (0.72, s * 0.84, 1.24), (0.70, s * 0.97, 1.30), 0.02, [ck.DARK], verts=6))
        parts.append(ck.box((0.08, 0.06, 0.18), (0.68, s * 0.99, 1.32), PAINT, bevel=0.012))
    parts.append(dfmesh.tube("snorkel", (0.95, -0.90, 0.92), (0.72, -0.90, 1.74), 0.055, [ck.DARK], verts=10))
    parts.append(ck.box((0.16, 0.13, 0.10), (0.70, -0.90, 1.78), ck.DARK, bevel=0.02))
    root = ck.finish(parts, "SM_DF_Car_Brute", PAINT)
    return ck.sockets(root, dims, ROOF, EXHAUST)
