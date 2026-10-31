"""SM_DF_FxCone: the cone effect shell (spec 7.1): a muzzle blast or a spray of dust thrown out along +X.

An open bell: its tip at the origin, 100 cm long along +X and 64 cm across its mouth, centred on the X axis (like the
exhaust flame), so growing it pushes the blast forward from the muzzle or the hit point. Cylindrical UVs (V = 0 at the tip,
1 at the mouth). Slot: FxFlash (an effect's component overrides it).
"""
import dfmesh

SEGMENTS = 16
PROFILE = [(0.0, 0.0), (0.09, 0.12), (0.20, 0.42), (0.28, 0.75), (0.32, 1.0)]  # (radius, along +X), metres


def build(dims):
    return dfmesh.lathe("SM_DF_FxCone", PROFILE, SEGMENTS, ["MI_DF_FxFlash"], axis="X", uv_along=True)
