"""SM_DF_Container: a 20 ft shipping container for the scatter (spec 8.3; at least 25 m from the road).

6.06 x 2.44 x 2.59 m along X: a steel frame (corner posts, top and bottom rails, corner castings), corrugated side and back
walls (trapezoid ribs), a roof, and the double doors at the +X end with four vertical locking bars, their handles, three
pressed ribs across each leaf and the hinges. Origin at the bottom centre. Collision: the auto box (an 18-DOP, i.e. its
box). Slot: ContainerPaint (rust-red painted steel), box-projected UVs.
"""
import math

from mathutils import Matrix

import dfmesh

SLOT = "MI_DF_ContainerPaint"
L, W, H = 6.06, 2.44, 2.59
POST = 0.16            # corner post and bottom rail section
TOP_RAIL = 0.12
RIB, DEPTH = 0.28, 0.035  # the corrugation's pitch and depth


def _box(size, loc, bevel=0.0):
    return dfmesh.part(dfmesh.box("part", size, bevel, loc), SLOT)


def _wall(length):
    """A corrugated wall `length` long on X between the rails, its ribs standing out towards -Y from y = 0 (the inside face
    at y = +0.012), centred on x = 0, from the bottom rail to the top rail."""
    n = max(1, int(round(length / RIB)))
    pitch = length / n
    pts = []
    for k in range(n):  # trapezoid ribs: flat in, slope, flat out, slope
        x = -length / 2 + k * pitch
        pts += [(x, 0.0), (x + pitch * 0.30, 0.0), (x + pitch * 0.42, DEPTH), (x + pitch * 0.88, DEPTH)]
    pts += [(length / 2, 0.0), (length / 2, -0.012), (-length / 2, -0.012)]
    z0, z1 = POST, H - TOP_RAIL
    wall = dfmesh.profile("wall", pts, (z1 - z0) / 2, [SLOT], y_m=(z0 + z1) / 2)
    wall.data.transform(Matrix.Rotation(math.radians(90), 4, "X"))  # the section's depth becomes -Y, its width the height
    return wall


def build(dims):
    parts = []
    inner = L - 2 * POST
    for side in (1, -1):  # the long walls, the ribs' outer faces just inside the frame
        w = _wall(inner)
        w.data.transform(Matrix.Rotation(math.pi if side > 0 else 0.0, 4, "Z") @ Matrix.Translation((0, -(W / 2 - DEPTH - 0.006), 0)))
        parts.append(w)
    back = _wall(W - 2 * POST)
    back.data.transform(Matrix.Rotation(math.radians(-90), 4, "Z") @ Matrix.Translation((0, -(L / 2 - DEPTH - 0.006), 0)))
    parts.append(back)
    parts.append(_box((L - 0.04, W - 0.04, 0.05), (0, 0, H - 0.045)))  # roof
    for sx in (1, -1):
        for sy in (1, -1):
            parts.append(_box((POST, POST, H), (sx * (L / 2 - POST / 2), sy * (W / 2 - POST / 2), H / 2), 0.01))  # posts
            for z in (0.06, H - 0.06):  # corner castings, a little proud
                parts.append(_box((0.18, 0.17, 0.12), (sx * (L / 2 - 0.085), sy * (W / 2 - 0.08), z), 0.008))
        parts.append(_box((POST * 0.8, W - 2 * POST, POST), (sx * (L / 2 - POST * 0.4), 0, POST / 2)))  # end sills
        parts.append(_box((POST * 0.8, W - 2 * POST, TOP_RAIL), (sx * (L / 2 - POST * 0.4), 0, H - TOP_RAIL / 2)))
    for sy in (1, -1):  # long bottom and top rails
        parts.append(_box((L - 2 * POST, POST, POST), (0, sy * (W / 2 - POST / 2), POST / 2)))
        parts.append(_box((L - 2 * POST, 0.10, TOP_RAIL), (0, sy * (W / 2 - 0.05), H - TOP_RAIL / 2)))
    # the doors at +X: two leaves, pressed ribs, locking bars with handles, hinges
    door_x, leaf = L / 2 - 0.05, (W - 2 * POST) / 2
    for sy in (1, -1):
        cy = sy * leaf / 2
        parts.append(_box((0.04, leaf - 0.01, H - POST - TOP_RAIL), (door_x, cy, (POST + H - TOP_RAIL) / 2)))
        for z in (0.55, 1.30, 2.05):
            parts.append(_box((0.025, leaf - 0.12, 0.10), (door_x + 0.03, cy, z)))
        for bar_y in (cy - sy * leaf * 0.18, cy + sy * leaf * 0.30):
            parts.append(dfmesh.part(dfmesh.tube("bar", (door_x + 0.07, bar_y, POST + 0.04), (door_x + 0.07, bar_y, H - TOP_RAIL - 0.04),
                                                 0.022, [SLOT], verts=6), SLOT))
            parts.append(_box((0.05, 0.05, 0.05), (door_x + 0.06, bar_y, 1.10)))  # the cam keeper
            parts.append(_box((0.035, 0.03, 0.32), (door_x + 0.10, bar_y - sy * 0.04, 1.02)))  # the handle
        for z in (0.45, 1.30, 2.15):  # hinges at the outer edge
            parts.append(_box((0.06, 0.09, 0.12), (door_x + 0.03, sy * (W / 2 - POST - 0.02), z)))
    root = dfmesh.assemble(parts, "SM_DF_Container", [SLOT], unwrap=False)
    return dfmesh.box_uv(root, 2.0)
