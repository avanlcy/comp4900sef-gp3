"""SM_DF_Ramp: the large jump ramp (spec 8.2), in place of VehicleAdv's RampLarge.

It keeps the original's outline and pivot so the track layout and the AI are unchanged: the side profile is RampLarge's
(measured from art/reference/RampLarge.fbx, df_export_dims.py): a 5 cm lip at the origin rising through four straight
pieces, steeper each time, to 242.7 cm at 5 m behind it (-X), with an upright back; 440 cm wide towards Unreal -Y
(Blender +Y) from the origin. Bounds as dims.json "ramp" within 2 cm (test_meshes). A poured concrete block with its edges
chamfered (BEVEL_M, kept small so the outline holds) and box-projected UVs (2 m a tile). Collision: one UCX hull per
straight piece of the profile; a single hull would fill the curve and launch cars off a flat slope. Slot: Concrete.
"""
import dfmesh

SLOT = "MI_DF_Concrete"
WIDTH_M = 4.40
# (x, z) metres of RampLarge's top edge, from the lip at the origin back to the top of the upright back
PROFILE = [(0.0, 0.05), (-1.25, 0.42495), (-2.50, 0.96111), (-3.75, 1.61245), (-5.00, 2.42712)]
BEVEL_M = 0.02


def build(dims):
    outline = [(0.0, 0.0)] + PROFILE + [(PROFILE[-1][0], 0.0)]
    root = dfmesh.profile("SM_DF_Ramp", outline, WIDTH_M / 2, [SLOT], bevel_m=BEVEL_M, y_m=WIDTH_M / 2)
    dfmesh.box_uv(root, 2.0)
    for (xa, za), (xb, zb) in zip(PROFILE, PROFILE[1:]):
        dfmesh.ucx_hull(root, [(x, y, z) for x, top in ((xa, za), (xb, zb)) for y in (0.0, WIDTH_M) for z in (0.0, top)])
    return root
