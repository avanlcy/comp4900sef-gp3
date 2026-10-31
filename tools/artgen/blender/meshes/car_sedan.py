"""SM_DF_Car_Sedan: the player's undercover-cop interceptor (spec 3, 6.1): a four-door saloon with a long hood, a push
bar, white side stripes, an A-pillar spotlight and dark B-pillars. The blue light bar is SM_DF_LightBar, mounted on the
Roof socket by the vehicle Blueprint (SEDAN only).
Built to dims.json; see carkit for the frame, slots and sockets.
"""
import dfmesh
from meshes import carkit as ck

PAINT = "MI_DF_Paint_Sedan"
W = 0.86            # half width of the lower body
Z0 = 0.24           # underside of the lower body
UPPER = [(2.20, Z0), (2.26, 0.36), (2.27, 0.62), (2.22, 0.76), (2.05, 0.83), (0.98, 0.95), (-1.28, 0.97),
         (-1.95, 0.98), (-2.17, 0.93), (-2.22, 0.72), (-2.20, 0.40), (-2.14, Z0)]
CABIN_BOTTOM = (-1.30, 1.00, 0.80, 0.94)   # x rear, x front, half width, z
CABIN_TOP = (-0.80, 0.12, 0.64, 1.46)
ROOF = ((CABIN_TOP[0] + CABIN_TOP[1]) / 2, 0.0, CABIN_TOP[3])
EXHAUST = (-2.30, 0.50, 0.27)


def build(dims):
    outline, slots = ck.side_outline(dims, Z0, UPPER)
    parts = [dfmesh.profile("body", outline, W, [PAINT, ck.DARK], slots, bevel_m=0.035, segments=2)]
    parts.append(dfmesh.frustum("cabin", CABIN_BOTTOM, CABIN_TOP, [PAINT, ck.GLASS], bevel_m=0.03, segments=2,
                                glass=(1, 0.07, 0.012)))
    parts += ck.well_liners(dims, Z0)
    parts.append(ck.box((1.80, 1.40, 0.04), (0.02, 0.0, 0.225), ck.DARK))                    # undertray
    # bumpers, grille, lights
    parts.append(ck.box((0.16, 1.70, 0.22), (2.24, 0.0, 0.32), ck.DARK, bevel=0.03))
    parts.append(ck.box((0.16, 1.70, 0.22), (-2.20, 0.0, 0.34), ck.DARK, bevel=0.03))
    parts.append(ck.box((0.04, 0.70, 0.16), (2.262, 0.0, 0.55), ck.DARK))
    parts += ck.mirrored(lambda s: ck.box((0.05, 0.30, 0.10), (2.245, s * 0.58, 0.64), ck.LIGHTS, bevel=0.015))
    parts += ck.mirrored(lambda s: ck.box((0.05, 0.30, 0.10), (-2.21, s * 0.60, 0.80), ck.LIGHTS, bevel=0.015))
    # push bar: two uprights, two cross bars, two mounts
    for s in (1, -1):
        parts.append(dfmesh.tube("bar", (2.33, s * 0.36, 0.26), (2.37, s * 0.36, 0.80), 0.03, [ck.DARK]))
        parts.append(dfmesh.tube("mount", (2.25, s * 0.36, 0.42), (2.35, s * 0.36, 0.42), 0.025, [ck.DARK]))
    parts.append(dfmesh.tube("bar", (2.345, 0.48, 0.46), (2.345, -0.48, 0.46), 0.03, [ck.DARK]))
    parts.append(dfmesh.tube("bar", (2.365, 0.40, 0.74), (2.365, -0.40, 0.74), 0.03, [ck.DARK]))
    # four doors: white stripe, dark seams, B-pillars, handles
    parts += ck.mirrored(lambda s: ck.box((1.80, 0.012, 0.08), (0.02, s * (W + 0.004), 0.64), ck.TRIM))
    for x in (0.93, -0.33, -0.90):
        parts += ck.mirrored(lambda s, x=x: ck.box((0.012, 0.01, 0.62), (x, s * (W + 0.003), 0.62), ck.DARK))
    parts += ck.mirrored(lambda s: ck.cabin_strip(CABIN_BOTTOM, CABIN_TOP, -0.33, s, ck.DARK))
    for x in (0.60, -0.62):
        parts += ck.mirrored(lambda s, x=x: ck.box((0.12, 0.02, 0.03), (x, s * (W + 0.008), 0.78), ck.TRIM))
    # mirrors, spotlight (driver's side = left), antenna
    for s in (1, -1):
        parts.append(dfmesh.tube("stalk", (0.86, s * 0.79, 1.00), (0.83, s * 0.90, 1.02), 0.015, [ck.DARK], verts=6))
        parts.append(ck.box((0.10, 0.12, 0.09), (0.80, s * 0.94, 1.03), PAINT, bevel=0.015))
    parts.append(dfmesh.tube("spot", (0.76, 0.86, 1.02), (0.90, 0.86, 1.02), 0.055, [ck.TRIM], verts=10))
    parts.append(dfmesh.tube("lens", (0.90, 0.86, 1.02), (0.915, 0.86, 1.02), 0.045, [ck.LIGHTS], verts=10))
    parts.append(dfmesh.tube("antenna", (-1.90, -0.40, 0.98), (-1.96, -0.40, 1.40), 0.006, [ck.DARK], verts=4))
    for s in (1, -1):
        parts.append(dfmesh.tube("exhaust", (-2.16, s * EXHAUST[1], EXHAUST[2]), EXHAUST[:1] + (s * EXHAUST[1], EXHAUST[2]),
                                 0.045, [ck.DARK], verts=10))
    root = ck.finish(parts, "SM_DF_Car_Sedan", PAINT)
    return ck.sockets(root, dims, ROOF, EXHAUST)
