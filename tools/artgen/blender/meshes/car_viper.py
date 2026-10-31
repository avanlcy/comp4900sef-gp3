"""SM_DF_Car_Viper: the low wedge (spec 3, 6.1): teal, a knife nose rising to a high tail, a low cabin with a steeply
raked windshield, a big rear wing on struts with white end plates, twin white stripes, dark flares, splitter, skirts,
side intakes, hood vents and a diffuser, slit headlights and a full-width tail light.
Built to dims.json; see carkit for the frame, slots and sockets. The fenders must clear the arches (arch tops at
wheel bone + arch radius = 0.78 m), so the wedge is in the nose, the cabin and the tail.
"""
import math

import dfmesh
from meshes import carkit as ck

PAINT = "MI_DF_Paint_Viper"
W = 0.88
Z0 = 0.22
HOOD = [(2.20, 0.50), (2.05, 0.66), (1.80, 0.83), (1.05, 0.86), (0.78, 0.84)]   # nose top to cowl
DECK = [(-1.30, 0.88), (-2.05, 0.93), (-2.22, 0.91)]                           # behind the cabin to the tail
UPPER = [(2.24, Z0), (2.32, 0.30), (2.33, 0.40)] + HOOD + DECK + [(-2.25, 0.62), (-2.20, 0.34), (-2.12, Z0)]
CAB_BOTTOM = (-1.36, 0.80, 0.80, 0.82)
CAB_TOP = (-0.92, -0.16, 0.60, 1.18)
ROOF = ((CAB_TOP[0] + CAB_TOP[1]) / 2, 0.0, CAB_TOP[3])
EXHAUST = (-2.30, 0.22, 0.36)
WING = [(-1.84, 1.40), (-1.97, 1.445), (-2.20, 1.43), (-2.24, 1.39), (-1.92, 1.375)]   # airfoil, nose first


def build(dims):
    outline, slots = ck.side_outline(dims, Z0, UPPER)
    parts = [dfmesh.profile("body", outline, W, [PAINT, ck.DARK], slots, bevel_m=0.035, segments=2)]
    parts.append(dfmesh.frustum("cabin", CAB_BOTTOM, CAB_TOP, [PAINT, ck.GLASS], bevel_m=0.03, segments=2,
                                glass=(1, 0.06, 0.012)))
    parts += ck.well_liners(dims, Z0)
    parts += ck.flares(dims, ck.DARK, W, Z0, width_m=0.08, thick_m=0.06)
    parts.append(ck.box((1.80, 1.40, 0.04), (0.02, 0.0, 0.205), ck.DARK))                       # undertray
    # aero: splitter, skirts, diffuser, side intakes, hood vents
    parts.append(ck.box((0.22, 1.76, 0.03), (2.27, 0.0, 0.235), ck.DARK, bevel=0.01))
    parts += ck.mirrored(lambda s: ck.box((1.86, 0.05, 0.10), (0.02, s * (W + 0.01), 0.27), ck.DARK, bevel=0.012))
    parts.append(ck.box((0.26, 1.30, 0.12), (-2.15, 0.0, 0.30), ck.DARK, bevel=0.015))
    parts += ck.mirrored(lambda s: ck.box((0.34, 0.03, 0.16), (-0.72, s * (W + 0.008), 0.58), ck.DARK, bevel=0.01))
    slope = math.degrees(math.atan2(HOOD[3][1] - HOOD[2][1], HOOD[2][0] - HOOD[3][0]))
    parts += ck.mirrored(lambda s: ck.box((0.34, 0.16, 0.02), (1.42, s * 0.34, 0.851), ck.DARK, rot_deg=(0, slope, 0)))
    # twin white stripes over hood, roof and deck
    roof_line = [(CAB_TOP[1] - 0.03, CAB_TOP[3]), (CAB_TOP[0] + 0.03, CAB_TOP[3])]
    for s in (1, -1):
        parts.append(ck.strip(HOOD, s * 0.17, 0.07, ck.TRIM))
        parts.append(ck.strip(roof_line, s * 0.17, 0.07, ck.TRIM))
        parts.append(ck.strip([(-1.42, 0.888), DECK[1]], s * 0.17, 0.07, ck.TRIM))
    # lights: slit headlights on the nose, a full-width tail light
    nose = math.degrees(math.atan2(HOOD[0][1] - UPPER[2][1], UPPER[2][0] - HOOD[0][0]))  # the nose's slope
    parts += ck.mirrored(lambda s: ck.box((0.16, 0.34, 0.02), (2.27, s * 0.56, 0.455), ck.LIGHTS, rot_deg=(0, nose, 0)))
    parts.append(ck.box((0.03, 1.40, 0.06), (-2.235, 0.0, 0.80), ck.LIGHTS))
    # rear wing: airfoil, end plates, struts
    parts.append(dfmesh.profile("wing", WING, 0.86, [PAINT], bevel_m=0.008))
    parts += ck.mirrored(lambda s: ck.box((0.40, 0.02, 0.16), (-2.04, s * 0.87, 1.39), ck.TRIM, bevel=0.006))
    for s in (1, -1):
        parts.append(ck.box((0.12, 0.03, 0.50), (-2.00, s * 0.52, 1.14), ck.DARK, rot_deg=(0, -8, 0)))
        parts.append(dfmesh.tube("exhaust", (-2.16, s * EXHAUST[1], EXHAUST[2]), (EXHAUST[0], s * EXHAUST[1], EXHAUST[2]),
                                 0.05, [ck.DARK], verts=10))
        parts.append(dfmesh.tube("stalk", (0.56, s * 0.74, 0.91), (0.54, s * 0.86, 0.93), 0.015, [ck.DARK], verts=6))
        parts.append(ck.box((0.10, 0.10, 0.07), (0.52, s * 0.90, 0.94), PAINT, bevel=0.015))
    root = ck.finish(parts, "SM_DF_Car_Viper", PAINT)
    return ck.sockets(root, dims, ROOF, EXHAUST)
