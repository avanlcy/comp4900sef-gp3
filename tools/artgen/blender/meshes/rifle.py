"""SM_DF_Rifle: the on-foot character's carbine (spec 3, 6.2), carried in SK_Mannequin's right hand.

90 cm long along +X, the bore on the X axis. The origin is where the hand holds it, on the handguard; BP_DFCharacter
puts that point in the fist of hand_r with the barrel forward. Socket Muzzle at the barrel tip, +X along the bore (the
tracer starts there, Task 16). GunMetal receiver, handguard and barrel; Dark stock, grip, magazine, optic and muzzle
brake; chunky bevelled side profiles.
Slots: GunMetal, Dark.
"""
import dfmesh

GM, DARK = "MI_DF_GunMetal", "MI_DF_Dark"
BUTT_X, MUZZLE_X = -0.56, 0.34          # metres from the hold point: 90 cm overall
TOP = 0.032                             # the receiver's and the handguard's top
BEVEL = 0.004


def side(name, outline_xz, half_w, slot):
    """A side profile (x, z metres) extruded across the rifle, its sharp edges bevelled."""
    return dfmesh.profile(name, outline_xz, half_w, [slot], bevel_m=BEVEL)


def build(dims):
    parts = [
        side("receiver", [(-0.31, -0.032), (-0.07, -0.032), (-0.07, TOP), (-0.31, TOP)], 0.027, GM),
        side("handguard", [(-0.07, -0.028), (0.15, -0.026), (0.17, -0.016), (0.17, 0.024), (0.15, TOP), (-0.07, TOP)], 0.024, GM),
        side("stock", [(-0.31, 0.024), (-0.31, -0.026), (-0.40, -0.052), (-0.535, -0.098), (BUTT_X, -0.104),
                       (BUTT_X, 0.030), (-0.42, 0.034), (-0.36, 0.024)], 0.021, DARK),
        side("grip", [(-0.236, -0.032), (-0.205, -0.032), (-0.236, -0.128), (-0.268, -0.122)], 0.016, DARK),
        side("guard", [(-0.205, -0.052), (-0.150, -0.052), (-0.150, -0.032), (-0.158, -0.032), (-0.158, -0.046),
                       (-0.205, -0.046)], 0.006, DARK),
        side("magazine", [(-0.150, -0.032), (-0.092, -0.032), (-0.070, -0.110), (-0.058, -0.182), (-0.112, -0.192),
                          (-0.122, -0.110)], 0.017, DARK),
        dfmesh.part(dfmesh.box("rail", (0.47, 0.024, 0.010), BEVEL / 2, (-0.075, 0.0, TOP + 0.005)), DARK),
        dfmesh.part(dfmesh.box("optic", (0.10, 0.042, 0.042), BEVEL, (-0.16, 0.0, TOP + 0.031)), DARK),
        dfmesh.part(dfmesh.cylinder("lens", 0.024, 0.02, 12, (-0.10, 0.0, TOP + 0.034), axis="X"), DARK),
        side("sight", [(0.140, TOP + 0.008), (0.165, TOP + 0.008), (0.158, TOP + 0.038), (0.146, TOP + 0.038)], 0.008, DARK),
        dfmesh.part(dfmesh.box("gas_block", (0.026, 0.026, 0.030), BEVEL / 2, (0.183, 0.0, 0.004)), GM),
        dfmesh.tube("barrel", (0.17, 0.0, 0.0), (0.305, 0.0, 0.0), 0.0115, [GM], verts=10),
        dfmesh.tube("brake", (0.300, 0.0, 0.0), (MUZZLE_X, 0.0, 0.0), 0.017, [DARK], verts=10),
    ]
    root = dfmesh.assemble(parts, "SM_DF_Rifle", [GM, DARK])
    dfmesh.socket(root, "Muzzle", (MUZZLE_X, 0.0, 0.0))
    return root
