"""SM_DF_Rock01..04: the scatter rocks (spec 8.3), one parametric script for the four (dfmesh.rock, with each one's seed).

Faceted low-poly rocks with flat fractured faces, each a different shape so a scattered field does not repeat: 01 a
rounded boulder, 02 a long low slab, 03 a tall split crag, 04 a small rock. Each stands on its flattened underside with the
origin at its bottom centre (the scatter rests it on the terrain). Collision: the auto box (an 18-DOP round the rock;
spec 8.3: rocks block). Slot: Rock (T_DF_Rock, Poly Haven rock_face_03), box-projected UVs.
"""
import dfmesh

SLOT = "MI_DF_Rock"
# number: (size x, y, z metres, seed, hull points, facet splits, slicing planes, roughness)
ROCKS = {
    1: ((2.3, 1.9, 1.5), 2001, 30, 1, 5, 0.10),
    2: ((3.2, 1.7, 0.9), 2002, 26, 1, 6, 0.08),
    3: ((1.5, 1.3, 2.5), 2003, 24, 1, 5, 0.10),
    4: ((1.2, 1.0, 0.75), 2004, 18, 1, 4, 0.08),
}


def build(dims, name):
    size, seed, points, subdiv, cuts, rough = ROCKS[int(name[-2:])]
    return dfmesh.rock(name, size, seed, SLOT, points=points, subdiv=subdiv, cuts=cuts, rough=rough)
