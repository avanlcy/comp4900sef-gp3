"""SM_DF_Crate: the loot crate's body (spec 7.4); SM_DF_CrateLid sits on its Lid socket.

A steel supply crate 100 x 70 cm, 68 cm to the lid seat, on two skids: a bevelled shell, four proud corner posts, a rim band
at the top and the bottom of the shell, and a carry handle on each end. Round its middle runs the glowing stripe, its own
slot (CrateStripe), which BP_DFLootBox's ApplyLook turns to the item's colour; it shows between the posts on all four sides.
With the 12 cm lid the crate is 80 cm tall (the stock 80 cm cube it replaces), and its origin is the centre of that height
(Task 17 fix round 1, controller ruling: a crate actor stands at the crate's centre, 40 cm over the ground where the levels
place it), so the base is HALF_M below the origin. +X along the long side. Socket Lid at the centre of the lid seat. One box
hull over the body (the crate overlaps cars, it never blocks them). Slots: CrateMetal, CrateStripe.
"""
from mathutils import Matrix

import dfmesh

METAL, STRIPE = "MI_DF_CrateMetal", "MI_DF_CrateStripe"
L, W, H = 1.00, 0.70, 0.68   # length (X), width (Y), height to the lid seat (Z), from the base
HALF_M = 0.40                # the origin over the base: half of the crate (68 cm) and lid (12.1 cm) together
SKID_H = 0.05                # the skids lift the shell off the ground
POST = 0.075                 # corner post section
POST_OUT = 0.012             # how far the posts stand proud of the shell
STRIPE_Z, STRIPE_H = 0.36, 0.09
HANDLE_Z = 0.53


def _box(size, loc, slot, bevel=0.0):
    return dfmesh.part(dfmesh.box("part", size, bevel, loc), slot)


def build(dims):
    shell_h = H - SKID_H
    mid = SKID_H + shell_h / 2
    parts = [_box((L, W, shell_h), (0, 0, mid), METAL, 0.015)]
    for s in (1, -1):  # skids along X
        parts.append(_box((L - 0.06, 0.09, SKID_H), (0, s * (W / 2 - 0.08), SKID_H / 2), METAL, 0.01))
    for sx in (1, -1):
        for sy in (1, -1):
            parts.append(_box((POST, POST, shell_h + 0.01), (sx * (L / 2 - POST / 2 + POST_OUT), sy * (W / 2 - POST / 2 + POST_OUT), mid),
                              METAL, 0.012))
    for z in (SKID_H + 0.03, H - 0.03):  # rim bands
        parts.append(_box((L + 0.012, W + 0.012, 0.045), (0, 0, z), METAL, 0.006))
    parts.append(_box((L + 0.008, W + 0.008, STRIPE_H), (0, 0, STRIPE_Z), STRIPE))  # the glowing stripe all round
    for sx in (1, -1):  # a carry handle on each end: a bar on two brackets
        parts.append(_box((0.035, 0.30, 0.035), (sx * (L / 2 + 0.05), 0, HANDLE_Z), METAL, 0.008))
        for sy in (1, -1):
            parts.append(_box((0.06, 0.03, 0.035), (sx * (L / 2 + 0.025), sy * 0.13, HANDLE_Z), METAL))
    root = dfmesh.assemble(parts, "SM_DF_Crate", [METAL, STRIPE])
    root.data.transform(Matrix.Translation((0.0, 0.0, -HALF_M)))  # built on the ground, then the origin to the crate's centre
    dfmesh.socket(root, "Lid", (0.0, 0.0, H - HALF_M))
    dfmesh.ucx_box(root, (L, W, H), (0.0, 0.0, H / 2 - HALF_M))
    return root
