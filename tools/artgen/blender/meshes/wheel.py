"""SM_DF_Wheel: tyre and rim (spec 6.1), sized from dims.json.

The origin is the hub on the wheel bone; the axle is Y. The tyre is centred AdditionalOffset (dims wheel_offset, 12 cm)
out from the bone along +Y, where the physics wheel runs, with the rim face outermost. That is the left wheels' outside
(Blender +Y is Unreal -Y, the left); the right wheels are yawed 180 so their rims face out too.
- Radius: the wheel classes' ShapeRadius (dims wheel_radius, 35 cm).
- Width: NOT the classes' ShapeWidth (dims wheel_width, 10 cm), which is the engine default the template never set; a
  10 cm tyre read as a thin sliver in the review. The tyre fills the space the template's own tyre fills, from 2 cm
  outside the bone to 2 cm short of twice the offset: 2 x 12 - 4 = 20 cm, centred on the physics wheel.
Slots: Rubber (tyre), Rim (rim, hub and five spokes).
"""
import math

import dfmesh

SEGMENTS = 20
SPOKES = 5


def layout(dims):
    """(tyre radius, tyre width, the tyre's centre out from the bone, the rim radius) in metres."""
    r = dims["wheel_radius"] / 100.0
    off = max(abs(o[1]) for o in dims["wheel_offset"].values()) / 100.0
    w = 2 * off - 0.04
    return r, w, off, round(r * 0.62, 4)


def rim(dims, name="rim"):
    """The rim, hub and spokes (Rim slot), as one object; shared with SM_DF_WheelRim."""
    r, w, off, rr = layout(dims)
    y_in, y_out = off - w / 2, off + w / 2
    dish = y_out - min(0.04, w * 0.4)
    prof = [(0.0, y_out - 0.012), (0.08, y_out - 0.012), (0.095, dish), (rr - 0.03, dish), (rr - 0.006, y_out - 0.006),
            (rr + 0.012, y_out - 0.002), (rr + 0.012, y_out - 0.016), (rr, y_out - 0.022), (rr, y_in + 0.01), (0.0, y_in + 0.01)]
    parts = [dfmesh.lathe(name, prof, SEGMENTS, ["MI_DF_Rim"])]
    length = rr - 0.03 - 0.09
    for k in range(SPOKES):
        a = 2 * math.pi * k / SPOKES
        mid = 0.09 + length / 2
        spoke = dfmesh.box("spoke", (0.035, 0.02, length), 0.0, (mid * math.sin(a), dish + 0.008, mid * math.cos(a)))
        spoke.rotation_euler = (0.0, a, 0.0)
        parts.append(dfmesh.part(spoke, "MI_DF_Rim"))
    return parts


def build(dims):
    r, w, off, rr = layout(dims)
    y_in, y_out = off - w / 2, off + w / 2
    c = min(0.03, w / 4)  # the tread's chamfer
    tyre = dfmesh.lathe("SM_DF_Wheel", [(rr + 0.004, y_in), (r - c, y_in), (r, y_in + c), (r, y_out - c), (r - c, y_out),
                                        (rr + 0.004, y_out)], SEGMENTS, ["MI_DF_Rubber"])
    return dfmesh.assemble([tyre] + rim(dims), "SM_DF_Wheel", ["MI_DF_Rubber", "MI_DF_Rim"])
