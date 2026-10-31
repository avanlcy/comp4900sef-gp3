"""SM_DF_Bomb: the dropped bomb (spec 7.5), a pressure mine that sits flat on the road, not a ball.

A gunmetal disc 64 cm across and 13 cm tall with a sloped top, a dark band round its side, eight dark bolts on the slope,
a dark pressure plate in the middle with four ribs, and on top of it the red lamp (BombLamp) that BP_DFBomb blinks faster
as its fuse runs. Origin at the base centre (it rests on the ground). Socket Lamp at the top of the lamp, where the bomb's
red BlinkLight hangs. No collision (BP_DFBomb's Trigger sphere does the touching). Slots: GunMetal, Dark, BombLamp.
"""
import math

import dfmesh

GUN, DARK, LAMP = "MI_DF_GunMetal", "MI_DF_Dark", "MI_DF_BombLamp"
R, H = 0.32, 0.13            # the disc's radius and the height of its top
PLATE_R, PLATE_TOP = 0.115, 0.165
LAMP_TOP = 0.215
SEGMENTS = 24


def build(dims):
    body = dfmesh.lathe("body", [(0.0, 0.0), (R - 0.03, 0.0), (R, 0.025), (R, 0.075), (R - 0.02, 0.10), (0.20, H - 0.005), (0.0, H)],
                        SEGMENTS, [GUN], axis="Z")
    band = dfmesh.lathe("band", [(R - 0.02, 0.032), (R + 0.006, 0.036), (R + 0.006, 0.066), (R - 0.02, 0.07)], SEGMENTS, [DARK], axis="Z")
    plate = dfmesh.lathe("plate", [(0.0, H - 0.01), (PLATE_R, H - 0.01), (PLATE_R + 0.006, H + 0.002), (PLATE_R, PLATE_TOP),
                                   (PLATE_R - 0.012, PLATE_TOP + 0.006), (0.0, PLATE_TOP + 0.006)], 20, [DARK], axis="Z")
    lamp = dfmesh.lathe("lamp", [(0.0, PLATE_TOP), (0.045, PLATE_TOP), (0.045, PLATE_TOP + 0.015), (0.034, LAMP_TOP - 0.012),
                                 (0.016, LAMP_TOP - 0.002), (0.0, LAMP_TOP)], 12, [LAMP], axis="Z")
    parts = [dfmesh.part(body, GUN), dfmesh.part(band, DARK), dfmesh.part(plate, DARK), dfmesh.part(lamp, LAMP)]
    for k in range(8):  # bolts on the slope
        a = 2 * math.pi * (k + 0.5) / 8
        bolt = dfmesh.cylinder("bolt", 0.016, 0.03, 6, loc=(0.255 * math.cos(a), 0.255 * math.sin(a), 0.105))
        parts.append(dfmesh.part(bolt, DARK))
    for k in range(4):  # ribs from the plate out over the slope
        a = math.radians(45 + 90 * k)
        rib = dfmesh.box("rib", (0.09, 0.022, 0.02), loc=((PLATE_R + 0.04) * math.cos(a), (PLATE_R + 0.04) * math.sin(a), H - 0.006))
        rib.rotation_euler = (0.0, 0.0, a)
        parts.append(dfmesh.part(rib, DARK))
    root = dfmesh.assemble(parts, "SM_DF_Bomb", [GUN, DARK, LAMP])
    dfmesh.socket(root, "Lamp", (0.0, 0.0, LAMP_TOP))
    return root
