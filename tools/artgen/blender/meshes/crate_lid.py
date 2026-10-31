"""SM_DF_CrateLid: the loot crate's lid (spec 7.4), on SM_DF_Crate's Lid socket.

A bevelled plate 103 x 73 cm (it overhangs the 100 x 70 cm crate a little), 9 cm thick, with a raised centre panel, a latch
on each end and the glowing stripe, its own slot (CrateStripe, the item's colour through BP_DFLootBox's ApplyLook): a band
round the plate's edge and a strip across the top. Origin at the base centre (the crate's lid seat), +X along the long side.
One box hull. Slots: CrateMetal, CrateStripe.
"""
import dfmesh

METAL, STRIPE = "MI_DF_CrateMetal", "MI_DF_CrateStripe"
L, W, T = 1.03, 0.73, 0.09
PANEL_H = 0.025


def _box(size, loc, slot, bevel=0.0):
    return dfmesh.part(dfmesh.box("part", size, bevel, loc), slot)


def build(dims):
    parts = [_box((L, W, T), (0, 0, T / 2), METAL, 0.015),
             _box((L - 0.24, W - 0.20, PANEL_H), (0, 0, T + PANEL_H / 2 - 0.004), METAL, 0.008),
             _box((L + 0.006, W + 0.006, 0.03), (0, 0, T * 0.45), STRIPE),                  # the band round the edge
             _box((0.10, W - 0.06, 0.012), (0, 0, T + PANEL_H - 0.004 + 0.004), STRIPE)]   # the strip across the top
    for sx in (1, -1):  # latches on the ends, within the plate's height
        parts.append(_box((0.035, 0.14, T - 0.01), (sx * (L / 2 + 0.012), 0, (T - 0.01) / 2), METAL, 0.006))
    root = dfmesh.assemble(parts, "SM_DF_CrateLid", [METAL, STRIPE])
    dfmesh.ucx_box(root, (L, W, T), (0.0, 0.0, T / 2))
    return root
