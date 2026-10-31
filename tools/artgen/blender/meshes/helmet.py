"""SM_DF_Helmet: the undercover cop's ballistic helmet (spec 3, 6.2), worn on SK_Mannequin's head bone.

Origin at the head bone, in the frame BP_DFCharacter mounts it in: X forward, Y left, Z up when the mannequin stands
upright (character.py turns it from the bone's own axes). The shell is a superellipsoid fitted round the mannequin's
skull: its inner surface clears the bind-pose head by about 1 cm (measured on an FBX export of SK_Mannequin, Task 14),
and its rim drops from the brow at the front, over the ears, to the nape. The rim is a Dark edge; a Dark night-vision
mount sits on the front and a rail on each side. Slots: GearNavy, Dark.
"""
import math

import dfmesh

NAVY, DARK = "MI_DF_GearNavy", "MI_DF_Dark"
# --- fit (cm) ---
CX, CZ = 1.6, 4.0                           # the shell's centre, ahead of and above the head bone
RXF, RXB, RY, RZ = 13.0, 11.4, 9.7, 13.8    # inner radii: forward, back, sideways, up
N_H, N_V = 2.0, 2.5                         # superellipse exponents round and up (a flatter crown than an ellipsoid)
T = 1.5                                     # shell thickness
RIM_FRONT, RIM_SIDE, RIM_BACK = 9.5, 3.0, 0.0   # rim height at the brow, over the ears and at the nape


def rim_z(a):
    """The rim's height (cm) at azimuth a (radians; 0 forward, pi/2 left)."""
    c = math.cos(a)
    return RIM_SIDE + (RIM_FRONT - RIM_SIDE) * max(c, 0.0) ** 1.5 + (RIM_BACK - RIM_SIDE) * max(-c, 0.0) ** 1.5
# --- end fit ---


AROUND, UP = 24, 6       # columns round the shell, rows from the rim to the crown
TOP_DEG = 82.0           # the crown's last row; a cap closes it


def point(a, e, grow=0.0):
    """The shell surface at azimuth a and elevation e (radians), grown outwards by grow cm; metres."""
    ce, se = dfmesh.superellipse(e, N_V)
    ca, sa = dfmesh.superellipse(a, N_H)
    rx = (RXF if ca >= 0 else RXB) + grow
    return ((CX + rx * ce * ca) / 100.0, (RY + grow) * ce * sa / 100.0, (CZ + (RZ + grow) * se) / 100.0)


def elevation(z_cm):
    """The elevation whose inner-surface height is z_cm."""
    s = max(-1.0, min(1.0, (z_cm - CZ) / RZ))
    return math.copysign(math.asin(abs(s) ** (N_V / 2.0)), s)


def _mount(a, z_cm, size_cm, slot, sink_cm=0.3):
    """A box on the outer surface at azimuth a and height z_cm, its thin X axis along the surface normal there."""
    e = elevation(z_cm)
    p0, p1 = point(a, e, T), point(a, e + 0.05, T)
    ca, sa = math.cos(a), math.sin(a)
    r0, r1 = p0[0] * ca + p0[1] * sa, p1[0] * ca + p1[1] * sa  # distance along the azimuth direction
    tr, tz = r1 - r0, p1[2] - p0[2]
    nr, nz = tz, -tr
    ln = math.hypot(nr, nz)
    nr, nz = nr / ln, nz / ln
    off = (size_cm[0] / 2.0 - sink_cm) / 100.0
    loc = (p0[0] + nr * ca * off, p0[1] + nr * sa * off, p0[2] + nz * off)
    o = dfmesh.part(dfmesh.box("mount", [s / 100.0 for s in size_cm], 0.004, loc), slot)
    o.rotation_euler = (0.0, -math.atan2(nz, nr), a)
    return o


def build(dims):
    outer, inner = [], []
    for i in range(UP + 1):
        o_row, i_row = [], []
        for k in range(AROUND):
            a = 2 * math.pi * k / AROUND
            e0 = elevation(rim_z(a))
            e = e0 + (math.radians(TOP_DEG) - e0) * i / UP
            o_row.append(point(a, e, T))
            i_row.append(point(a, e))
        outer.append(o_row)
        inner.append(i_row)
    parts = [dfmesh.shell("shell", outer, inner, [NAVY, DARK], cap=True, wall_slot=1)]
    parts.append(_mount(0.0, 12.0, (1.2, 6.0, 4.5), DARK))                 # night-vision mount over the brow
    for side in (1, -1):                                                 # accessory rails
        parts.append(_mount(side * math.pi / 2, 7.5, (0.9, 9.0, 1.8), DARK))
    return dfmesh.assemble(parts, "SM_DF_Helmet", [NAVY, DARK])
