"""SM_DF_BeaconPillar: the crate's beacon (spec 7.4), a pillar of light 30 m tall that marks a crate from the road.

Two open tubes standing on the origin: an outer sleeve 60 cm across tapering to a third of that at the top, and a 24 cm
core. Drawn additive (MI_DF_FxBeacon, M_DF_FxAdditive, two-sided), the overlapping layers make the middle brightest; the
material's NearFade fades it out within 10 m of the camera, so it does not clutter the crate close up. BP_DFLootBox tints its
MID with the item colour. Cylindrical UVs (U around, V up). No collision. Slot: FxBeacon.
"""
import dfmesh

SLOT = "MI_DF_FxBeacon"
HEIGHT_M = 30.0
R_OUT, R_CORE = 0.30, 0.12
SEGMENTS = 12


def build(dims):
    outer = dfmesh.lathe("outer", [(R_OUT, 0.0), (R_OUT * 0.8, HEIGHT_M * 0.5), (R_OUT * 0.35, HEIGHT_M)], SEGMENTS, [SLOT],
                         axis="Z", uv_along=True)
    core = dfmesh.lathe("core", [(R_CORE, 0.0), (R_CORE, HEIGHT_M)], SEGMENTS, [SLOT], axis="Z", uv_along=True)
    return dfmesh.assemble([outer, core], "SM_DF_BeaconPillar", [SLOT], unwrap=False)
