"""SM_DF_AxisFixture: a 2 m arrow on +X, 0.5 m wide and 1 m tall; Task 5 imports it to confirm the FBX orientation.
Its Left socket sits on the shaft's left face (Blender +Y when facing +X with Z up), so the import shows the Y mapping."""
import dfmesh

SHAFT_HALF = 0.10  # half width of the shaft, m


def build(dims):
    # Outline seen from above, counter-clockwise, tip at +X; centred on X so the origin is the base centre.
    pts = [(-1.0, -SHAFT_HALF), (0.2, -SHAFT_HALF), (0.2, -0.25), (1.0, 0.0), (0.2, 0.25), (0.2, SHAFT_HALF), (-1.0, SHAFT_HALF)]
    obj = dfmesh.prism("SM_DF_AxisFixture", pts, 1.0)
    dfmesh.slot(obj, "MI_DF_Concrete")
    dfmesh.socket(obj, "Left", (0.0, SHAFT_HALF, 0.5))
    dfmesh.smart_uv(obj)
    return obj
