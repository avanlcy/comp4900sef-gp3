"""SM_DF_LightBar: SEDAN's blue roof light bar (spec 3, 6.1): a dark base on two feet with two rounded blue lamps.

The vehicle Blueprint mounts it on the body's Roof socket, where the roof weapon also mounts. So the bar is modelled
FORWARD_M ahead of its origin, over the front of SEDAN's roof, and stays below TOP_M; the roof weapons keep their
mount behind it and everything ahead of its back edge above it (roof_gun, roof_launcher). Origin at the base, +X forward.
Slots: Dark (base, feet), LightBlue (lamps).
"""
import dfmesh
from meshes import carkit as ck

FORWARD_M = 0.33   # the bar's centre ahead of the Roof socket
DEPTH_M = 0.22     # so it spans FORWARD_M +- 0.11
TOP_M = 0.14       # its height above the roof
BLUE = "MI_DF_LightBlue"


def build(dims):
    x = FORWARD_M
    lamp_h = TOP_M - 0.065
    parts = [ck.box((DEPTH_M, 1.10, 0.035), (x, 0.0, 0.045), ck.DARK, bevel=0.008),
             ck.box((DEPTH_M - 0.03, 0.05, 0.06), (x, 0.0, 0.092), ck.DARK)]
    for s in (1, -1):
        parts.append(ck.box((0.16, 0.06, 0.03), (x, s * 0.42, 0.015), ck.DARK))
        parts.append(ck.box((DEPTH_M - 0.02, 0.50, lamp_h), (x, s * 0.28, 0.0625 + lamp_h / 2), BLUE, bevel=0.02))
    return dfmesh.assemble(parts, "SM_DF_LightBar", [ck.DARK, BLUE])
