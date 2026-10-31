"""SM_DF_RoofGun: the twin machine gun shown on the roof while the racer holds a Gun (spec 6.1, 7.2).

Origin at the base of its turret ring (the body's Roof socket), +X forward. Socket Muzzle between the two barrel tips
(carkit.GUN_MUZZLE_M; each body's own Muzzle socket is Roof + that offset). On SEDAN it shares the roof with the light
bar, which spans light_bar.FORWARD_M +- DEPTH_M/2 ahead of the socket below light_bar.TOP_M: the gun shield stays behind
the bar, and the receiver and barrels that pass over it stay above its top.
Slots: GunMetal, Dark.
"""
import dfmesh
from meshes import carkit as ck

GM = "MI_DF_GunMetal"


def build(dims):
    mx, _, mz = ck.GUN_MUZZLE_M
    parts = [dfmesh.part(dfmesh.cylinder("ring", 0.17, 0.05, 16, (0, 0, 0.025)), ck.DARK),
             dfmesh.part(dfmesh.cylinder("turntable", 0.13, 0.05, 16, (0, 0, 0.075)), GM),
             ck.box((0.30, 0.22, 0.09), (0.0, 0.0, 0.145), GM, bevel=0.02),          # cradle
             ck.box((0.42, 0.16, 0.12), (0.09, 0.0, mz), GM, bevel=0.02),            # receiver, 0.18..0.30 high
             ck.box((0.025, 0.42, 0.24), (0.14, 0.0, 0.215), GM, bevel=0.008),       # gun shield
             ck.box((0.16, 0.10, 0.11), (0.0, 0.135, mz), ck.DARK, bevel=0.01),      # ammo box (left)
             dfmesh.tube("grip", (-0.12, 0.05, mz - 0.02), (-0.20, 0.05, mz - 0.07), 0.015, [ck.DARK], verts=6),
             dfmesh.tube("grip", (-0.12, -0.05, mz - 0.02), (-0.20, -0.05, mz - 0.07), 0.015, [ck.DARK], verts=6)]
    for s in (1, -1):
        parts.append(dfmesh.tube("barrel", (0.28, s * 0.045, mz), (mx - 0.05, s * 0.045, mz), 0.022, [GM]))
        parts.append(dfmesh.tube("brake", (mx - 0.06, s * 0.045, mz), (mx, s * 0.045, mz), 0.032, [ck.DARK]))
    root = dfmesh.assemble(parts, "SM_DF_RoofGun", [GM, ck.DARK])
    dfmesh.socket(root, "Muzzle", ck.GUN_MUZZLE_M)
    return root
