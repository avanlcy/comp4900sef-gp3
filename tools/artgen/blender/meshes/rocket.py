"""SM_DF_Rocket: the RPG's rocket (spec 7.1, 7.5), the BP_DFProjectile's mesh in flight.

Centred on its origin (the projectile's collision sphere) and flying along +X: a grey body with a dark ogive nose tip,
a dark band behind the nose, four dark tail fins in an X and a dark nozzle at the tail. Socket Exhaust at the nozzle's
mouth, yawed 180 so its +X points backwards: SM_DF_ExhaustFlame (which runs along +X from its origin) hangs there as the
rocket's flame. Chunky enough (11 cm body, 25 cm across the fins, 70 cm long) to read at a few metres in flight.
Slots: RocketBody, Dark.
"""
import math

import dfmesh
from meshes import carkit as ck

BODY = "MI_DF_RocketBody"
LENGTH_M = 0.70
HALF = LENGTH_M / 2
R = 0.055                                  # body radius
SEGMENTS = 16
NOZZLE_R = (0.038, 0.046)                  # throat, mouth
NOZZLE_X = (-HALF + 0.05, -HALF)           # from the boat-tail back to the mouth (the tail end)
FIN = [(-0.29, R - 0.004), (-0.18, R - 0.004), (-0.27, R + 0.07), (-0.33, R + 0.07)]  # (x, out from the axis), root to tip
FIN_HALF_T = 0.006


def _fin(roll_deg):
    """One fin: the FIN outline in the XZ plane (up from the axis), rolled about X."""
    f = dfmesh.part(dfmesh.profile("fin", FIN, FIN_HALF_T, [ck.DARK]), ck.DARK)
    f.rotation_euler = (math.radians(roll_deg), 0.0, 0.0)
    return f


def build(dims):
    nose_tip, nose_base = HALF, HALF - 0.17
    # the grey body: ogive nose (from the band back), the tube, then a short boat-tail into the nozzle
    body = dfmesh.lathe("body", [(0.032, nose_base + 0.09), (0.046, nose_base + 0.05), (R, nose_base), (R, -HALF + 0.09),
                                 (0.05, NOZZLE_X[0]), (0.0, NOZZLE_X[0])], SEGMENTS, [BODY], axis="X")
    tip = dfmesh.lathe("tip", [(0.0, nose_tip), (0.012, nose_tip - 0.015), (0.025, nose_tip - 0.04), (0.032, nose_base + 0.09)],
                       SEGMENTS, [ck.DARK], axis="X")
    band = dfmesh.lathe("band", [(R + 0.003, nose_base - 0.005), (R + 0.003, nose_base - 0.035)], SEGMENTS, [ck.DARK], axis="X")
    nozzle = dfmesh.lathe("nozzle", [(0.0, NOZZLE_X[0] + 0.004), (NOZZLE_R[0], NOZZLE_X[0] + 0.004), (NOZZLE_R[0], NOZZLE_X[0]),
                                     (NOZZLE_R[1], NOZZLE_X[1]), (NOZZLE_R[1] - 0.008, NOZZLE_X[1]), (0.0, NOZZLE_X[1] + 0.02)],
                          SEGMENTS, [ck.DARK], axis="X")
    parts = [dfmesh.part(body, BODY), dfmesh.part(tip, ck.DARK), dfmesh.part(band, ck.DARK), dfmesh.part(nozzle, ck.DARK)]
    parts += [_fin(45.0 + 90.0 * k) for k in range(4)]
    root = dfmesh.assemble(parts, "SM_DF_Rocket", [BODY, ck.DARK])
    dfmesh.socket(root, "Exhaust", (NOZZLE_X[1], 0.0, 0.0), (0, 0, 180))
    return root
