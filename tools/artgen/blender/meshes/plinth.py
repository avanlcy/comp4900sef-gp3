"""SM_DF_Plinth: the menu's showcase turntable (spec 8.5: the plinths become SM_DF_Plinth turntables on the terrain).

A round concrete drum 5.9 m across (a 4.7 m car stands on it with room to spare) and 40 cm tall, with a chamfered foot and
a stepped rim: a white trim ring round the deck's edge, an inlaid trim ring on the deck and a trim hub in its middle, so
it reads as a turntable from the menu camera. Origin at its bottom centre; the deck is DECK_M above it. Collision: the auto
box (an 18-DOP round the drum). Slots: Concrete, Trim.
"""
import dfmesh

CONCRETE, TRIM = "MI_DF_Concrete", "MI_DF_Trim"
R = 2.95          # the drum's radius
DECK_M = 0.40     # the deck's height
SEGMENTS = 40


def _ring(r_in, r_out, z0, z1, slot):
    return dfmesh.part(dfmesh.lathe("ring", [(r_in, z0), (r_out, z0), (r_out, z1), (r_in, z1), (r_in, z0)], SEGMENTS,
                                    [slot], axis="Z"), slot)


def build(dims):
    drum = dfmesh.lathe("drum", [(0.0, 0.0), (R - 0.03, 0.0), (R, 0.03), (R, DECK_M - 0.10), (R - 0.05, DECK_M - 0.06),
                                 (R - 0.13, DECK_M - 0.06), (R - 0.13, DECK_M), (0.0, DECK_M)], SEGMENTS, [CONCRETE], axis="Z")
    hub = dfmesh.lathe("hub", [(0.0, DECK_M + 0.012), (0.42, DECK_M + 0.012), (0.45, DECK_M - 0.01), (0.0, DECK_M - 0.01)],
                       SEGMENTS, [TRIM], axis="Z")
    parts = [dfmesh.part(drum, CONCRETE),
             _ring(R - 0.13, R - 0.045, DECK_M - 0.06, DECK_M - 0.005, TRIM),   # the trim ring round the deck's edge
             _ring(1.60, 1.66, DECK_M - 0.01, DECK_M + 0.006, TRIM),           # an inlaid ring on the deck
             dfmesh.part(hub, TRIM)]
    root = dfmesh.assemble(parts, "SM_DF_Plinth", [CONCRETE, TRIM], unwrap=False)
    return dfmesh.box_uv(root, 2.0)
