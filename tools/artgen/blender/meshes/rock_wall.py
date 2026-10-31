"""SM_DF_RockWall: the destructible rock that closes the shortcut (spec 8.2), BP_DFDestructible's mesh (only explosives
demolish it; it then breaks into 8 BP_DFDebris chunks of SM_DF_RockChunk).

Unit contract: it fills the 100 cm cube centred on the origin, so the Blueprint's scaling is unchanged (note: the stock
Shape_Cube it replaces has its pivot at its base, this one at its centre). A big fractured boulder (dfmesh.rock) with a
flat underside, filling the cube so it closes the road like the block did. Collision: the auto box (an 18-DOP round the
rock). Slot: Rock, box-projected UVs.
"""
import dfmesh

SLOT = "MI_DF_Rock"


def build(dims):
    return dfmesh.rock("SM_DF_RockWall", (1.0, 1.0, 1.0), 2010, SLOT, points=44, subdiv=2, cuts=6, rough=0.08,
                       origin="center", flat_base=0.2)
