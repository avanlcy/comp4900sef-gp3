"""SM_DF_Barrier: a concrete jersey barrier (spec 8.2), BP_DFTrackSpline's optional barrier pieces (off by default).

Unit contract: the 100 cm cube's bounds, centred on the origin, so the track's barrier scaling (BarrierThickness and
BarrierHeight over MeshNativeSize 100) is unchanged. The cross-section is a jersey barrier's in proportion to its base and
height: a short upright toe, the steep lower slope (55 degrees), the near-upright upper face and a chamfered top, swept along
X in SEGMENTS steps so a piece bends with the spline. Collision: the auto box (an 18-DOP; the section is convex). Slot:
Concrete, box-projected UVs.
"""
import dfmesh

SLOT = "MI_DF_Concrete"
SEGMENTS = 8
# (half width, z) up one side of the unit section: a 61 cm-based, 81 cm-tall jersey barrier scaled to 1 x 1
SIDE = [(0.5, -0.5), (0.5, -0.41), (0.207, -0.093), (0.125, 0.455), (0.085, 0.5)]


def build(dims):
    outline = [(-w, z) for w, z in SIDE] + [(w, z) for w, z in reversed(SIDE)]
    obj = dfmesh.extrude_x("SM_DF_Barrier", outline, [SLOT], segments=SEGMENTS)
    return dfmesh.box_uv(obj, 1.0)
