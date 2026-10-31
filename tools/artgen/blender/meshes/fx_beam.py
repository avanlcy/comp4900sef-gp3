"""SM_DF_FxBeam: the tracer shell (spec 7.1). BP_DFFxTracer.SetEnds stands it at the shot's start, aims it at the end and
scales X to the distance / 100.

It starts at its origin and runs exactly 100 cm along +X, 10 cm across, centred on the X axis (catalogue bounds 100 x 10 x
10): an eight-sided sleeve with pointed ends, and a thinner six-sided core inside it (the additive material adds up where
they overlap, so the streak has a hot middle). Cylindrical UVs. Slot: FxFlash (BP_DFFxTracer overrides it with FxTracer).
"""
import dfmesh

LENGTH_M, RADIUS_M, CORE_M = 1.0, 0.05, 0.02


def build(dims):
    sleeve = dfmesh.lathe("SM_DF_FxBeam", [(0.0, 0.0), (RADIUS_M, 0.08), (RADIUS_M, 0.92), (0.0, LENGTH_M)], 8,
                          ["MI_DF_FxFlash"], axis="X", uv_along=True)
    core = dfmesh.lathe("core", [(0.0, 0.02), (CORE_M, 0.10), (CORE_M, 0.90), (0.0, 0.98)], 6, ["MI_DF_FxFlash"],
                        axis="X", uv_along=True)
    return dfmesh.assemble([sleeve, core], "SM_DF_FxBeam", ["MI_DF_FxFlash"], unwrap=False)
