"""SM_DF_Debris01..02: ground debris for the scatter (spec 8.3; at least 10 m from the road, no collision), one parametric
script for the two.

01 is a rubble heap: broken concrete lumps (dfmesh.rock, few facets) piled up with a slab leaning on them, rusty rebar
bent out of them and a buckled plate leaning on the pile. 02 is scrap strewn flat: two torn corrugated sheets lying on the ground, a length of pipe, a
crushed drum and a concrete slab fragment with a few small lumps. Each is about 2.5 m across and low. Origin at the bottom
centre. No collision. Slots: RustMetal, Concrete; box-projected UVs.
"""
import math
import random

from mathutils import Matrix, Vector

import dfmesh

METAL, CONCRETE = "MI_DF_RustMetal", "MI_DF_Concrete"


def _lump(rng, size, at, seed, points=16):
    obj = dfmesh.rock("lump", size, seed, CONCRETE, points=points, subdiv=0, cuts=3, rough=0.0, flat_base=0.15)
    obj.data.transform(Matrix.Translation(at) @ Matrix.Rotation(rng.uniform(0, 6.28), 4, "Z"))
    return obj


def _rebar(rng, start, d):
    """A bent rusty bar: two thin pieces from start along d, the second kinked."""
    d = Vector(d).normalized()
    mid = Vector(start) + d * rng.uniform(0.2, 0.35)
    kink = (d + Vector((rng.uniform(-0.6, 0.6), rng.uniform(-0.6, 0.6), rng.uniform(-0.5, 0.2)))).normalized()
    return [dfmesh.part(dfmesh.tube("bar", start, mid, 0.012, [METAL], verts=4), METAL),
            dfmesh.part(dfmesh.tube("bar", mid, mid + kink * rng.uniform(0.15, 0.3), 0.012, [METAL], verts=4), METAL)]


def _laid(obj, matrix):
    obj.data.transform(matrix)
    return obj


def rubble(rng):
    parts = []
    lumps = [((0.95, 0.75, 0.5), (0.0, 0.0, 0.0)), ((0.8, 0.6, 0.45), (0.55, 0.35, 0.0)), ((0.75, 0.6, 0.42), (-0.55, 0.3, 0.0)),
             ((0.7, 0.55, 0.4), (0.35, -0.45, 0.0)), ((0.65, 0.5, 0.38), (-0.4, -0.4, 0.0)), ((0.6, 0.5, 0.36), (0.05, 0.05, 0.36)),
             ((0.35, 0.3, 0.22), (1.0, -0.15, 0.0)), ((0.32, 0.26, 0.2), (-1.0, -0.05, 0.0))]
    for k, (size, at) in enumerate(lumps):
        parts.append(_lump(rng, size, at, 2200 + k))
    slab = dfmesh.rock("slab", (1.2, 0.8, 0.18), 2210, CONCRETE, points=12, subdiv=0, cuts=2, rough=0.0, flat_base=0.3)
    parts.append(_laid(slab, Matrix.Translation((0.35, 0.55, 0.2)) @ Matrix.Rotation(math.radians(24), 4, "X")))  # leaning on the pile
    for start, d in (((0.05, 0.05, 0.6), (0.3, 0.2, 1.0)), ((0.6, 0.35, 0.35), (1.0, 0.4, 0.5)), ((-0.55, 0.3, 0.3), (-0.8, 0.3, 0.6)),
                     ((0.35, -0.45, 0.3), (0.2, -1.0, 0.4))):
        parts += _rebar(rng, start, d)
    plate = dfmesh.corrugated_sheet("plate", 0.9, 0.7, METAL, pitch_m=0.15, depth_m=0.03, rows=2, jag_m=0.12, curl_m=0.1, seed=11)
    parts.append(_laid(plate, Matrix.Translation((-0.2, -0.75, 0.0)) @ Matrix.Rotation(math.radians(20), 4, "Z")
                       @ Matrix.Rotation(math.radians(-55), 4, "X")))
    return parts


def strewn(rng):
    parts = []
    for k, (x, y, yaw) in enumerate(((-0.6, 0.3, 15.0), (0.5, -0.2, -40.0))):
        sheet = dfmesh.corrugated_sheet("sheet", 1.1, 0.9, METAL, pitch_m=0.16, depth_m=0.03, rows=2, jag_m=0.2, curl_m=0.12, seed=20 + k)
        parts.append(_laid(sheet, Matrix.Translation((x, y, 0.03 + 0.02 * k)) @ Matrix.Rotation(math.radians(yaw), 4, "Z")
                           @ Matrix.Rotation(math.radians(-86), 4, "X") @ Matrix.Translation((0.0, 0.0, -0.45))))
    parts.append(dfmesh.part(dfmesh.tube("pipe", (-1.0, -0.6, 0.08), (0.45, -0.95, 0.08), 0.08, [METAL], verts=8), METAL))
    drum = dfmesh.part(dfmesh.cylinder("drum", 0.29, 0.85, 12, axis="X"), METAL)  # a drum crushed flat on its side
    parts.append(_laid(drum, Matrix.Translation((0.95, 0.65, 0.14)) @ Matrix.Rotation(math.radians(30), 4, "Z") @ Matrix.Scale(0.48, 4, (0, 0, 1))))
    slab = dfmesh.rock("slab", (0.95, 0.65, 0.16), 2230, CONCRETE, points=10, subdiv=0, cuts=2, rough=0.0, flat_base=0.3)
    parts.append(_laid(slab, Matrix.Translation((-0.2, 0.95, 0.0)) @ Matrix.Rotation(math.radians(-25), 4, "Z")))
    for k, at in enumerate(((0.25, 0.4, 0.0), (-0.95, 0.95, 0.0), (1.1, -0.45, 0.0))):
        parts.append(_lump(rng, (0.28, 0.22, 0.16), at, 2240 + k, points=10))
    return parts


def build(dims, name):
    number = int(name[-2:])
    rng = random.Random(2200 + number)
    parts = rubble(rng) if number == 1 else strewn(rng)
    root = dfmesh.assemble(parts, name, [METAL, CONCRETE], unwrap=False)
    dfmesh.ground(root)
    return dfmesh.box_uv(root, 1.0)
