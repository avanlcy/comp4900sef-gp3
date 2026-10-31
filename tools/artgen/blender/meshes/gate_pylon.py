"""SM_DF_GatePylon: a gate's pylon (spec 8.2: two SM_DF_GatePylon with SM_DF_GateBanner across them), in place of the
VehicleAdv pole on BP_DFCheckpoint.

Controller ruling (Task 20): the pylons no longer keep the pole's bounds (BP_DFCheckpoint's poles never collide; its
Trigger box does the work), so the gate can be seen from the road. A chunky 6 m steel pylon on the gate's origin, which
lies on the road like the pole's did; its foot is sunk FOOT_M below it, as the pole's was (dims.json pole min Z -25.8), so
it never floats where the ground beside the road is a little lower. A bevelled plinth with a glowing kick band, a square
column with a glowing strip up each face and two glowing rings, and a wide head with a glowing band and a cap; the banner
(4.7 to 5.5 m) hangs between two of them, its ends against the columns and heads. The glowing parts are the Gate slot
(slot 0, flame orange, whose Glow BP_DFCheckpoint raises on the player's next gate); the steel is GunMetal (slot 1).
Collision: one UCX hull round it (the Blueprint gives it none). Slots: Gate, GunMetal.
"""
import dfmesh

GATE, STEEL = "MI_DF_Gate", "MI_DF_GunMetal"
HEIGHT_M, FOOT_M = 6.0, 0.25
PLINTH, PLINTH_TOP = 0.90, 0.45      # plinth width and the top of it
COLUMN, HEAD_Z0 = 0.60, 5.15         # column width; the head starts here
HEAD, CAP_Z0 = 0.86, 5.90            # head width; the cap starts here


def _box(size, z0, z1, slot, bevel=0.0):
    return dfmesh.part(dfmesh.box("part", (size[0], size[1], z1 - z0), bevel, (0.0, 0.0, (z0 + z1) / 2)), slot)


def build(dims):
    parts = [_box((PLINTH, PLINTH), -FOOT_M, PLINTH_TOP, STEEL, 0.04),          # plinth, down into its foot
             _box((PLINTH + 0.03, PLINTH + 0.03), 0.22, 0.32, GATE, 0.012),     # kick band
             _box((COLUMN, COLUMN), PLINTH_TOP - 0.02, HEAD_Z0 + 0.02, STEEL, 0.035),
             _box((HEAD, HEAD), HEAD_Z0, CAP_Z0, STEEL, 0.05),                   # head
             _box((HEAD + 0.03, HEAD + 0.03), 5.38, 5.56, GATE, 0.012),         # head band
             _box((COLUMN - 0.16, COLUMN - 0.16), CAP_Z0 - 0.02, HEIGHT_M, STEEL, 0.03)]  # cap
    for z in (1.70, 3.20):  # glowing rings round the column
        parts.append(_box((COLUMN + 0.03, COLUMN + 0.03), z, z + 0.10, GATE, 0.01))
    for sx, sy in ((1, 0), (-1, 0), (0, 1), (0, -1)):  # a glowing strip up the middle of each face
        w = (0.04 if sx else 0.14, 0.14 if sx else 0.04)
        strip = dfmesh.part(dfmesh.box("strip", (w[0], w[1], 4.20), 0.008,
                                       (sx * COLUMN / 2, sy * COLUMN / 2, (0.62 + 4.82) / 2)), GATE)
        parts.append(strip)
    root = dfmesh.assemble(parts, "SM_DF_GatePylon", [GATE, STEEL], unwrap=False)
    dfmesh.box_uv(root, 1.0)
    h = PLINTH / 2
    dfmesh.ucx_hull(root, [(sx * h, sy * h, z) for sx in (1, -1) for sy in (1, -1) for z in (-FOOT_M, HEIGHT_M)])
    return root
