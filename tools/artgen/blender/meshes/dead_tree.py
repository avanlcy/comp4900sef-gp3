"""SM_DF_DeadTree01..02: dead trees for the scatter (spec 8.3; at least 25 m from the road), one parametric script for the
two (each one's seed and shape from TREES).

A bare, burnt tree grown from tapered six-sided pieces (dfmesh.tube with an end radius): a root flare, a gnarled trunk
that leans, and limbs that fork `depth` times into thinner, bent branches ending in twigs (four-sided once they are thin).
01 is a tall spreading tree; 02 a smaller leaning one whose trunk has snapped off, with splinters standing up from the
break and its two limbs growing from below it. Origin at the bottom centre of the trunk. Collision: one UCX hull round the trunk only; the
branches have none (spec 8.3). Slot: DeadWood, box-projected UVs.
"""
import math
import random

from mathutils import Matrix, Vector

import dfmesh

SLOT = "MI_DF_DeadWood"
TWIG_R = 0.035   # thinner than this a piece is four-sided
# number: seed, trunk (height m, base radius m, lean degrees, pieces), limbs at the top, fork depth, snapped top
TREES = {
    1: dict(seed=2101, height=4.0, radius=0.27, lean=5.0, pieces=4, limbs=3, depth=3, snapped=False),
    2: dict(seed=2102, height=3.3, radius=0.24, lean=14.0, pieces=3, limbs=2, depth=3, snapped=True),
}


def _piece(parts, a, b, r0, r1):
    parts.append(dfmesh.part(dfmesh.tube("wood", a, b, r0, [SLOT], verts=6 if r0 > TWIG_R else 4, radius_end_m=r1), SLOT))


def _turn(rng, d, degrees):
    """d turned by `degrees` about a random axis across it."""
    side = d.cross(Vector((rng.uniform(-1, 1), rng.uniform(-1, 1), rng.uniform(-1, 1)))).normalized()
    return (Matrix.Rotation(math.radians(degrees), 3, side) @ d).normalized()


def _branch(parts, rng, start, d, length, r0, depth):
    """A bent branch of two or three pieces from `start` along d, tapering from r0; it forks at its end until depth runs out."""
    pieces = 3 if depth >= 2 else 2
    p, r = start, r0
    for i in range(pieces):
        r1 = max(0.008, r0 * (1.0 - 0.55 * (i + 1) / pieces))
        q = p + d * (length / pieces)
        _piece(parts, p, q, r, r1)
        p, r = q, r1
        d = _turn(rng, d, rng.uniform(8, 22))
        d = (d + Vector((0, 0, 0.12))).normalized()  # dead wood still reaches up a little
    if depth > 0:
        for k in range(rng.choice((2, 2, 3))):
            _branch(parts, rng, p, _turn(rng, d, rng.uniform(22, 48)), length * rng.uniform(0.55, 0.75), r * 0.95, depth - 1)


def build(dims, name):
    t = TREES[int(name[-2:])]
    rng = random.Random(t["seed"])
    parts = []
    lean_axis = Vector((math.cos(rng.uniform(0, 6.28)), math.sin(rng.uniform(0, 6.28)), 0.0)).normalized()
    d = (Matrix.Rotation(math.radians(t["lean"]), 3, lean_axis) @ Vector((0, 0, 1))).normalized()
    # the root flare: short tapering roots splayed out and down to the ground
    for k in range(5):
        a = 2 * math.pi * (k + rng.uniform(-0.2, 0.2)) / 5
        out = Vector((math.cos(a), math.sin(a), 0.0))
        _piece(parts, Vector((0, 0, 0.45)), out * rng.uniform(0.55, 0.85) + Vector((0, 0, 0.03)), t["radius"] * 0.55, 0.03)
    # the trunk
    p, r = Vector((0, 0, 0)), t["radius"]
    trunk = [(p, r)]
    for i in range(t["pieces"]):
        r1 = t["radius"] * (1.0 - 0.45 * (i + 1) / t["pieces"])
        q = p + d * (t["height"] / t["pieces"])
        _piece(parts, p, q, r, r1)
        p, r = q, r1
        trunk.append((p, r))
        d = _turn(rng, d, rng.uniform(4, 12))
        d = (d + Vector((0, 0, 0.25))).normalized()
    # the limbs from the top of the trunk (below the break on a snapped one), and one lower down
    fork, fork_r = trunk[-2] if t["snapped"] else trunk[-1]
    for k in range(t["limbs"]):
        _branch(parts, rng, fork, _turn(rng, d, rng.uniform(25, 45)), t["height"] * rng.uniform(0.55, 0.7), fork_r * 0.85,
                t["depth"] - 1)
    lower = trunk[len(trunk) // 2]
    _branch(parts, rng, lower[0], _turn(rng, d, 70), t["height"] * 0.45, lower[1] * 0.45, 1)
    if t["snapped"]:  # splinters standing up round the break
        for k in range(4):
            a = 2 * math.pi * k / 4 + rng.uniform(-0.4, 0.4)
            base = p + Vector((math.cos(a), math.sin(a), 0.0)) * r * 0.5
            _piece(parts, base - d * 0.05, base + _turn(rng, d, rng.uniform(5, 20)) * rng.uniform(0.25, 0.6), r * 0.35, 0.004)
    root = dfmesh.assemble(parts, name, [SLOT], unwrap=False)
    lift = dfmesh.ground(root)
    dfmesh.box_uv(root, 1.0)
    # the trunk's hull: an octagon round its foot and round its top
    hull = []
    for (c, rr) in (trunk[0], trunk[-1]):
        for k in range(8):
            a = 2 * math.pi * k / 8
            hull.append(c + Vector((math.cos(a), math.sin(a), 0.0)) * rr + Vector((0, 0, lift)))
    dfmesh.ucx_hull(root, hull)
    return root
