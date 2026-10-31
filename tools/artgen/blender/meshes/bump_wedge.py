"""SM_DF_BumpWedge: the bump wedge (spec 8.2), in place of VehicleAdv's BumpWedge.

It keeps the original's shape and pivot so the layout and the AI are unchanged (measured from
art/reference/BumpWedge.fbx, df_export_dims.py): a rounded speed bump 125 cm long (towards -X from the origin) and 34.9 cm
high at its Y = 0 end, tapering across 218.3 cm (towards Unreal -Y, Blender +Y) to a bump 39 % as long and 27 % as high,
lofted straight between the two ends. Bounds as dims.json "bump_wedge" within 2 cm (test_meshes). Concrete, box-projected
UVs (1 m a tile). Collision: one UCX hull per strip of the profile (the bump's flanks are concave, a single hull would
fill them). Slot: Concrete.
"""
import bmesh

import dfmesh

SLOT = "MI_DF_Concrete"
DEPTH_M = 2.183  # across Y
# (x, z) metres of the bump's top at Y = 0, end to end; the original is symmetric about its crest
PROFILE = [(-1.25112, 0.05136), (-1.17293, 0.07273), (-1.09473, 0.11217), (-0.93834, 0.20366), (-0.78195, 0.30373),
           (-0.70376, 0.33614), (-0.62556, 0.34875), (-0.54737, 0.33614), (-0.46917, 0.30373), (-0.31278, 0.20366),
           (-0.15639, 0.11217), (-0.07819, 0.07273), (0.0, 0.05136)]
CREST_X = -0.62556
FAR_X, FAR_Z = 0.38882, 0.26847  # the far end's profile: this share of the near one's length (about the crest) and height


def _far(p):
    return CREST_X + (p[0] - CREST_X) * FAR_X, p[1] * FAR_Z


def _section(profile, y):
    """The closed end section at y: along the bottom, then up and over the top."""
    return [(profile[0][0], y, 0.0)] + [(x, y, z) for x, z in profile] + [(profile[-1][0], y, 0.0)]


def build(dims):
    far = [_far(p) for p in PROFILE]
    bm = bmesh.new()
    a = [bm.verts.new(p) for p in _section(PROFILE, 0.0)]
    b = [bm.verts.new(p) for p in _section(far, DEPTH_M)]
    n = len(a)
    for k in range(n):
        bm.faces.new((a[k], a[(k + 1) % n], b[(k + 1) % n], b[k]))
    bm.faces.new(a)
    bm.faces.new(list(reversed(b)))
    root = dfmesh.box_uv(dfmesh.solid("SM_DF_BumpWedge", bm, [SLOT], triangulate=True), 1.0)  # the lofted quads twist
    for (pa, pb), (fa, fb) in zip(zip(PROFILE, PROFILE[1:]), zip(far, far[1:])):
        pts = []
        for (x, z), y in ((pa, 0.0), (pb, 0.0), (fa, DEPTH_M), (fb, DEPTH_M)):
            pts += [(x, y, 0.0), (x, y, z)]
        dfmesh.ucx_hull(root, pts)
    return root
