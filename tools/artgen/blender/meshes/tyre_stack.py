"""SM_DF_TyreStack: a stack of old tyres for the scatter (spec 8.3; blocking, at least 14 m from the road).

Five car tyres stacked, each a little off centre and tipped, with a sixth leaning against the stack. A tyre is a rounded
section (tread, shoulders and the bead round the hole) turned round its axis. Origin at the bottom centre of the stack.
Collision: the auto box (an 18-DOP round the stack). Slot: Rubber, box-projected UVs.
"""
import math
import random

from mathutils import Matrix

import dfmesh

SLOT = "MI_DF_Rubber"
SEED = 2060
R_OUT, R_IN, WIDTH = 0.36, 0.21, 0.23
SEGMENTS = 16
STACK = 5
# the tyre's section (radius, height) from the bottom bead round the outside to the top bead and back through the hole
SECTION = [(R_IN, 0.02), (R_IN + 0.05, 0.0), (R_OUT - 0.04, 0.0), (R_OUT, 0.04), (R_OUT, WIDTH - 0.04), (R_OUT - 0.04, WIDTH),
           (R_IN + 0.05, WIDTH), (R_IN, WIDTH - 0.02), (R_IN, 0.02)]


def tyre(matrix):
    t = dfmesh.lathe("tyre", SECTION, SEGMENTS, [SLOT], axis="Z")
    t.data.transform(matrix)
    return t


def build(dims):
    rng = random.Random(SEED)
    parts = []
    for i in range(STACK):
        tip = Matrix.Rotation(math.radians(rng.uniform(-3.0, 3.0)), 4, "X") @ Matrix.Rotation(math.radians(rng.uniform(-3.0, 3.0)), 4, "Y")
        at = Matrix.Translation((rng.uniform(-0.04, 0.04), rng.uniform(-0.04, 0.04), i * (WIDTH - 0.01)))
        parts.append(tyre(at @ tip))
    # the sixth stands on its tread on the stack's -Y side, its top tipped 12 degrees onto the stack (centred on its own
    # middle, turned 78 degrees about X: its axis lies nearly flat and its top leans towards +Y)
    stand = Matrix.Translation((0.05, -(R_OUT + WIDTH / 2 + 0.13), R_OUT * 0.98)) @ Matrix.Rotation(math.radians(78), 4, "X")
    parts.append(tyre(stand @ Matrix.Translation((0, 0, -WIDTH / 2))))
    root = dfmesh.assemble(parts, "SM_DF_TyreStack", [SLOT], unwrap=False)
    dfmesh.ground(root)
    return dfmesh.box_uv(root, 1.0)
