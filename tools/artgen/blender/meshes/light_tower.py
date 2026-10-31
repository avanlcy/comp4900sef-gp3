"""SM_DF_LightTower: a floodlight tower for the scatter (spec 8.3: emissive lamps, no light; at least 25 m from the road).

A 10.5 m four-legged lattice mast tapering from 1.2 m square at its foot to 0.5 m at the top (legs, a ring of ties and a
diagonal on each face every LEVEL_M), on a steel base frame with feet, and a head frame on top carrying two rows of four
floodlights that face +X, tipped down 15 degrees, their lenses in the Lights slot (they glow; there is no light), with a
ladder up the -X face. Origin at the bottom centre. Collision: UCX boxes round the base, the mast and the head (one hull
round the whole would fill the air under the head). Slots: RustMetal, Lights.
"""
import math

from mathutils import Matrix

import dfmesh

METAL, LIGHTS = "MI_DF_RustMetal", "MI_DF_Lights"
MAST_H, FOOT, TOP = 10.5, 0.60, 0.25   # height; the legs' half spacing at the foot and at the top
BASE_H = 0.35
LEVEL_M = 1.25
HEAD = (0.35, 2.6, 1.3)                # the lamp frame (depth, width, height)
TILT = 15.0


def _tube(a, b, r, verts=4):
    return dfmesh.part(dfmesh.tube("t", a, b, r, [METAL], verts=verts), METAL)


def _half(z):
    return FOOT + (TOP - FOOT) * (z - BASE_H) / (MAST_H - BASE_H)


def _corner(sx, sy, z):
    h = _half(z)
    return (sx * h, sy * h, z)


def build(dims):
    parts = [dfmesh.part(dfmesh.box("base", (1.6, 1.6, 0.12), 0.01, (0, 0, BASE_H - 0.06)), METAL)]
    for sx in (1, -1):
        for sy in (1, -1):
            parts.append(dfmesh.part(dfmesh.box("foot", (0.30, 0.30, BASE_H - 0.12), 0.01, (sx * 0.70, sy * 0.70, (BASE_H - 0.12) / 2)), METAL))
            parts.append(_tube(_corner(sx, sy, BASE_H), _corner(sx, sy, MAST_H), 0.045, verts=6))  # the legs
    corners = [(1, 1), (-1, 1), (-1, -1), (1, -1)]
    z = BASE_H
    level = 0
    while z + LEVEL_M <= MAST_H + 0.01:
        z1 = z + LEVEL_M
        for k, (sx, sy) in enumerate(corners):
            nx, ny = corners[(k + 1) % 4]
            parts.append(_tube(_corner(sx, sy, z1), _corner(nx, ny, z1), 0.025))  # a ring of ties
            a, b = ((sx, sy, z), (nx, ny, z1)) if (k + level) % 2 == 0 else ((nx, ny, z), (sx, sy, z1))
            parts.append(_tube(_corner(*a), _corner(*b), 0.02))  # the face's diagonal, alternating
        z, level = z1, level + 1
    for y in (0.16, -0.16):  # a ladder up the -X face
        parts.append(_tube((-_half(BASE_H) - 0.10, y, BASE_H), (-_half(MAST_H) - 0.10, y, MAST_H), 0.018))
    rung = BASE_H + 0.3
    while rung < MAST_H - 0.2:
        x = -_half(rung) - 0.10
        parts.append(_tube((x, 0.16, rung), (x, -0.16, rung), 0.012))
        rung += 0.6
    # the head: a platform, a frame and two rows of four floodlights on it, tipped down towards +X
    parts.append(dfmesh.part(dfmesh.box("deck", (1.0, HEAD[1] * 0.8, 0.06), 0.0, (0, 0, MAST_H + 0.03)), METAL))
    frame_z = MAST_H + 0.10 + HEAD[2] / 2
    for y in (HEAD[1] / 2, -HEAD[1] / 2):
        parts.append(dfmesh.part(dfmesh.box("upright", (0.08, 0.08, HEAD[2]), 0.0, (0, y, frame_z)), METAL))
    for zz in (MAST_H + 0.12, MAST_H + 0.10 + HEAD[2]):
        parts.append(dfmesh.part(dfmesh.box("bar", (0.08, HEAD[1] + 0.08, 0.08), 0.0, (0, 0, zz)), METAL))
    tip = Matrix.Rotation(math.radians(TILT), 4, "Y")
    for row, zz in enumerate((MAST_H + 0.50, MAST_H + 1.05)):
        for k in range(4):
            y = -HEAD[1] / 2 + HEAD[1] * (k + 0.5) / 4
            at = Matrix.Translation((0.10, y, zz)) @ tip
            housing = dfmesh.part(dfmesh.box("lamp", (0.22, 0.52, 0.40), 0.02, (0, 0, 0)), METAL)
            lens = dfmesh.part(dfmesh.box("lens", (0.03, 0.44, 0.32), 0.0, (0.12, 0, 0)), LIGHTS)
            for o in (housing, lens):
                o.data.transform(at)
            parts += [housing, lens]
    root = dfmesh.assemble(parts, "SM_DF_LightTower", [METAL, LIGHTS], unwrap=False)
    dfmesh.box_uv(root, 1.5)
    dfmesh.ucx_box(root, (1.6, 1.6, BASE_H), (0, 0, BASE_H / 2))
    dfmesh.ucx_hull(root, [_corner(sx, sy, zz) for sx in (1, -1) for sy in (1, -1) for zz in (BASE_H, MAST_H)])
    dfmesh.ucx_box(root, (0.7, HEAD[1] + 0.6, HEAD[2] + 0.3), (0.05, 0, MAST_H + 0.10 + HEAD[2] / 2))
    return root
