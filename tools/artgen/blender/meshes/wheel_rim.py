"""SM_DF_WheelRim: the bare rim shown when that tyre is blown (spec 6.1, 7.5): SM_DF_Wheel without the tyre, on the
same hub origin and offset. Slot: Rim."""
import dfmesh
from meshes import wheel


def build(dims):
    parts = wheel.rim(dims, "SM_DF_WheelRim")
    return dfmesh.assemble(parts, "SM_DF_WheelRim", ["MI_DF_Rim"])
