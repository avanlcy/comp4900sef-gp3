"""SM_DF_RoofLauncher: the four-tube rocket pod shown on the roof while the racer holds an RPG (spec 6.1, 7.5).

Origin at the base of its turret ring (the body's Roof socket), +X forward. Socket Muzzle at the centre of the pod's
front face, where rockets visually leave. The pod stays behind SEDAN's light bar (light_bar.FORWARD_M - DEPTH_M/2
ahead of the socket) and above its top.
Slots: GunMetal, Dark.
"""
import dfmesh
from meshes import carkit as ck

GM = "MI_DF_GunMetal"
POD = (-0.36, 0.18, 0.21, 0.17, 0.43)   # x rear, x front, half width, z bottom, z top
MUZZLE = (POD[1] + 0.02, 0.0, (POD[3] + POD[4]) / 2)


def build(dims):
    x0, x1, hw, z0, z1 = POD
    zc = (z0 + z1) / 2
    parts = [dfmesh.part(dfmesh.cylinder("ring", 0.17, 0.05, 16, (0, 0, 0.025)), ck.DARK),
             dfmesh.part(dfmesh.cylinder("post", 0.07, 0.14, 12, (-0.05, 0, 0.11)), GM),
             ck.box((x1 - x0, 2 * hw, z1 - z0), ((x0 + x1) / 2, 0.0, zc), GM, bevel=0.02),    # pod
             ck.box((0.03, 2 * hw - 0.04, z1 - z0 - 0.04), (x0 - 0.01, 0.0, zc), ck.DARK)]    # rear cap
    for s in (1, -1):
        parts.append(ck.box((0.16, 0.03, 0.18), (-0.05, s * (hw + 0.015), zc - 0.04), GM, bevel=0.01))  # yoke
        for dz in (0.06, -0.06):
            parts.append(dfmesh.tube("tube", (x1 - 0.02, s * 0.095, zc + dz), (MUZZLE[0], s * 0.095, zc + dz),
                                     0.048, [ck.DARK], verts=10))
    root = dfmesh.assemble(parts, "SM_DF_RoofLauncher", [GM, ck.DARK])
    dfmesh.socket(root, "Muzzle", MUZZLE)
    return root
