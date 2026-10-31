"""SM_DF_ExhaustFlame: a boost flame (spec 7.5), shown at the body's Exhaust_L / Exhaust_R sockets while boosting.

It starts at its origin (the exhaust tip) and runs LENGTH_M along +X; the sockets are yawed 180, so it points backwards.
An outer flame and a brighter inner core (the additive material adds up where they overlap), with cylindrical UVs:
V = 0 at the root, 1 at the tip, as M_DF_FxFlame pans and fades along V. Slot: FxBoostFlame.
"""
import dfmesh

LENGTH_M = 0.80
SEGMENTS = 12


def build(dims):
    outer = dfmesh.lathe("SM_DF_ExhaustFlame", [(0.0, 0.0), (0.065, 0.0), (0.085, 0.10), (0.07, 0.30), (0.04, 0.55),
                                                 (0.0, LENGTH_M)], SEGMENTS, ["MI_DF_FxBoostFlame"], axis="X", uv_along=True)
    core = dfmesh.lathe("core", [(0.0, 0.0), (0.04, 0.0), (0.045, 0.08), (0.025, 0.30), (0.0, LENGTH_M * 0.55)],
                        SEGMENTS, ["MI_DF_FxBoostFlame"], axis="X", uv_along=True)
    return dfmesh.assemble([outer, core], "SM_DF_ExhaustFlame", ["MI_DF_FxBoostFlame"], unwrap=False)
