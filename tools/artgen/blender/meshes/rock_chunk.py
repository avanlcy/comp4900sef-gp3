"""SM_DF_RockChunk: a chunk of the demolished rock wall (spec 8.2): BP_DFDebris flings 8 of them, simulating physics, for
8 s. An angular broken piece about an eighth of the 3 m wall (the wall is SM_DF_RockWall at scale 3), cut by more planes
than a scatter rock so it reads as freshly broken. Its origin is its centre, where a physics body turns. Collision: the auto
box (an 18-DOP round it). Slot: Rock, box-projected UVs.
"""
import dfmesh

SLOT = "MI_DF_Rock"


def build(dims):
    return dfmesh.rock("SM_DF_RockChunk", (1.15, 0.95, 0.8), 2020, SLOT, points=16, subdiv=1, cuts=6, rough=0.05,
                       origin="center", flat_base=0.0)
