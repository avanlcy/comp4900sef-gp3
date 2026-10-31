"""SM_DF_Billboard: a roadside billboard for the scatter (spec 8.3: SM_DF_Billboard, the Fire syndicate's tag; at least
25 m from the road).

A 6 x 3 m steel board facing +X, its bottom 4 m up, on two I-beam legs behind it that run up to its top, with diagonal
braces, a catwalk with a rail along its foot and stringers across its back. The Fire syndicate has tagged it: a flame
emblem 2.1 m tall and a slashed underline in their flame orange (BillboardTag) across the face. Origin at the bottom centre
between the legs. Collision: a UCX box round each leg and one round the board (a hull round the whole would block the empty
space under the board). Slots: RustMetal, BillboardTag.
"""
import math

from mathutils import Matrix

import dfmesh

METAL, TAG = "MI_DF_RustMetal", "MI_DF_BillboardTag"
BOARD_W, BOARD_H, BOARD_Z, BOARD_T = 6.0, 3.0, 4.0, 0.16
LEG_Y, LEG_X = 1.8, -0.26
# the flame emblem (across, up) metres from the board's middle: three tongues over a rounded base
FLAME = [(0.0, -1.0), (0.55, -0.86), (0.82, -0.46), (0.76, 0.0), (0.56, 0.36), (0.66, 0.78), (0.38, 0.46), (0.30, 0.88),
         (0.12, 0.56), (0.0, 1.12), (-0.16, 0.60), (-0.34, 0.92), (-0.42, 0.40), (-0.64, 0.66), (-0.56, 0.20), (-0.80, -0.10),
         (-0.76, -0.50), (-0.50, -0.88)]


def _box(size, loc, slot=METAL, bevel=0.0):
    return dfmesh.part(dfmesh.box("part", size, bevel, loc), slot)


def _on_face(outline, x, y0, z0, slot):
    """A flat shape (across, up) on the board's front face: 2.4 cm thick, standing out from x."""
    shape = dfmesh.profile("tag", outline, 0.012, [slot])
    shape.data.transform(Matrix.Translation((x + 0.012, y0, z0)) @ Matrix.Rotation(math.radians(90), 4, "Z"))
    return shape


def build(dims):
    parts = []
    top = BOARD_Z + BOARD_H
    for sy in (1, -1):  # I-beam legs: web and two flanges, up to the board's top
        y = sy * LEG_Y
        parts.append(_box((0.24, 0.03, top - 0.05), (LEG_X, y, (top - 0.05) / 2)))
        for fx in (0.12, -0.12):
            parts.append(_box((0.03, 0.26, top - 0.05), (LEG_X + fx, y, (top - 0.05) / 2)))
        parts.append(_box((0.60, 0.60, 0.10), (LEG_X, y, 0.05), bevel=0.01))  # base plate
        parts.append(dfmesh.part(dfmesh.tube("brace", (LEG_X - 0.05, y, 0.8), (LEG_X - 1.4, y, 0.0), 0.05, [METAL], verts=6), METAL))
    parts.append(dfmesh.part(dfmesh.tube("cross", (LEG_X - 0.14, LEG_Y, 1.0), (LEG_X - 0.14, -LEG_Y, 3.4), 0.04, [METAL], verts=6), METAL))
    parts.append(dfmesh.part(dfmesh.tube("cross", (LEG_X - 0.14, -LEG_Y, 1.0), (LEG_X - 0.14, LEG_Y, 3.4), 0.04, [METAL], verts=6), METAL))
    # the board: a frame round a panel, stringers across its back
    parts.append(_box((BOARD_T, BOARD_W, BOARD_H), (0.0, 0.0, BOARD_Z + BOARD_H / 2), bevel=0.02))
    for z in (BOARD_Z + 0.5, BOARD_Z + 1.5, BOARD_Z + 2.5):
        parts.append(_box((0.10, BOARD_W - 0.2, 0.12), (-BOARD_T / 2 - 0.05, 0.0, z)))
    for z in (BOARD_Z + 0.04, top - 0.04):  # a lip round the face
        parts.append(_box((0.08, BOARD_W + 0.06, 0.08), (BOARD_T / 2 + 0.02, 0.0, z)))
    for sy in (1, -1):
        parts.append(_box((0.08, 0.08, BOARD_H + 0.06), (BOARD_T / 2 + 0.02, sy * (BOARD_W / 2 + 0.03), BOARD_Z + BOARD_H / 2)))
    # catwalk along the foot, with a rail on posts and brackets back to the legs
    parts.append(_box((0.75, BOARD_W, 0.05), (0.45, 0.0, BOARD_Z - 0.18)))
    for y in (-2.9, -1.45, 0.0, 1.45, 2.9):
        parts.append(dfmesh.part(dfmesh.tube("post", (0.80, y, BOARD_Z - 0.16), (0.80, y, BOARD_Z + 0.85), 0.022, [METAL], verts=6), METAL))
    parts.append(dfmesh.part(dfmesh.tube("rail", (0.80, -2.95, BOARD_Z + 0.85), (0.80, 2.95, BOARD_Z + 0.85), 0.025, [METAL], verts=6), METAL))
    for sy in (1, -1):
        parts.append(dfmesh.part(dfmesh.tube("bracket", (LEG_X, sy * LEG_Y, BOARD_Z - 1.0), (0.75, sy * LEG_Y, BOARD_Z - 0.2), 0.035,
                                             [METAL], verts=6), METAL))
    # the Fire syndicate's tag: the flame and a slashed underline, off centre like a sprayed tag
    front = BOARD_T / 2
    parts.append(_on_face(FLAME, front, -0.9, BOARD_Z + BOARD_H / 2 + 0.05, TAG))
    parts.append(_on_face([(-1.1, -0.10), (1.6, 0.05), (1.65, 0.20), (-1.05, 0.06)], front, 0.6, BOARD_Z + 0.55, TAG))
    parts.append(_on_face([(0.0, -0.25), (0.14, -0.25), (0.42, 0.85), (0.28, 0.85)], front, 1.55, BOARD_Z + 1.30, TAG))
    root = dfmesh.assemble(parts, "SM_DF_Billboard", [METAL, TAG], unwrap=False)
    dfmesh.ground(root)  # the kickers' ends dip under the ground
    dfmesh.box_uv(root, 1.5)
    for sy in (1, -1):
        dfmesh.ucx_box(root, (0.30, 0.30, top), (LEG_X, sy * LEG_Y, top / 2))
    dfmesh.ucx_box(root, (BOARD_T + 0.1, BOARD_W + 0.1, BOARD_H + 0.1), (0.02, 0.0, BOARD_Z + BOARD_H / 2))
    return root
