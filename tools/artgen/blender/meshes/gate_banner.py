"""SM_DF_GateBanner: the banner across a gate (spec 8.2), hung overhead between the two SM_DF_GatePylon.

100 cm long on Y and centred there, so BP_DFCheckpoint scales it on Y to the pylon spacing at run time (2 x PoleOffset 700 =
14 m: it then runs from one pylon's centre to the other's, its ends inside the columns and heads). Its origin is the gate's
origin on the road, like the pylons' (controller ruling, Task 20), so the component needs no offset: the banner hangs from
BOTTOM_M to TOP_M over the road, its underside well clear of the tallest car with its roof weapon (BRUTE about 2.1 m).
Nothing along it varies, so the stretch does not show: a dark board between a glowing rail at the top and the bottom, with
a glowing band along the middle of both faces, 20 cm thick at the rails. The glowing parts are the Gate slot (slot 0,
whose Glow BP_DFCheckpoint raises on the player's next gate); the board is Dark (slot 1, untextured, so nothing stretches).
No collision (cars pass under it). Slots: Gate, Dark.
"""
import dfmesh

GATE, BOARD = "MI_DF_Gate", "MI_DF_Dark"
BOTTOM_M, TOP_M = 4.70, 5.50
RAIL_H = 0.10


def _bar(depth, z0, z1, slot, bevel):
    return dfmesh.part(dfmesh.box("bar", (depth, 1.0, z1 - z0), bevel, (0.0, 0.0, (z0 + z1) / 2)), slot)


def build(dims):
    mid = (BOTTOM_M + TOP_M) / 2
    parts = [_bar(0.12, BOTTOM_M + RAIL_H - 0.01, TOP_M - RAIL_H + 0.01, BOARD, 0.015),   # the board
             _bar(0.20, BOTTOM_M, BOTTOM_M + RAIL_H, GATE, 0.02),                       # bottom rail
             _bar(0.20, TOP_M - RAIL_H, TOP_M, GATE, 0.02),                             # top rail
             _bar(0.15, mid - 0.07, mid + 0.07, GATE, 0.01)]                            # the band along both faces
    root = dfmesh.assemble(parts, "SM_DF_GateBanner", [GATE, BOARD], unwrap=False)
    return dfmesh.box_uv(root, 0.5)
