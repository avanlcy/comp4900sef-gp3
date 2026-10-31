"""SM_DF_Vest: the undercover cop's plate carrier (spec 3, 6.2), worn on SK_Mannequin's spine_03 bone.

Origin at the spine_03 bone, in the frame BP_DFCharacter mounts it in: X forward, Y left, Z up when the mannequin stands
upright (character.py turns it from the bone's own axes). TORSO is the inner surface the vest sits on: the bind-pose
torso of SK_Mannequin (measured on its FBX export, Task 14) plus 1.2 cm, as the front and back depth and the half width
of a superellipse cross-section at each height. A front and a back plate follow it over the chest and the shoulder
blades, leaving the armholes free; a cummerbund wraps the waist below the arms; a strap over each shoulder joins the
plates. Dark magazine pouches and a radio pouch sit on the front; the plates' edges are Dark binding.
Slots: Fabric, Dark.
"""
import math

import dfmesh

FABRIC, DARK = "MI_DF_Fabric", "MI_DF_Dark"
# --- fit (cm) ---
# height: (front, back, half width) of the inner surface, from the torso + 1.2 cm
TORSO = [(-30, 16.7, 7.5, 16.1), (-27, 17.0, 7.6, 16.0), (-24, 17.1, 8.9, 16.6), (-21, 17.6, 10.3, 17.5),
         (-18, 17.8, 12.7, 17.7), (-15, 18.1, 13.5, 18.9), (-12, 18.1, 15.1, 20.1), (-9, 18.3, 16.3, 21.2),
         (-6, 18.3, 17.6, 21.4), (-3, 17.6, 19.0, 20.9), (0, 17.6, 19.4, 20.1), (3, 15.8, 19.7, 20.1),
         (6, 14.4, 19.2, 19.8), (9, 12.4, 18.2, 19.3), (12, 9.0, 17.2, 19.1), (15, 5.1, 15.8, 18.7), (18, 3.0, 13.6, 15.8)]
N_FRONT, N_BACK = 2.5, 3.2      # superellipse exponents of the front and the (flatter) back
FRONT_ROWS = (-24, -16, -8, -1, 4, 7.5)
BACK_ROWS = (-24, -16, -8, 0, 7, 12, 14.5)
FRONT_HALF_W, BACK_HALF_W = 13.0, 14.0
PLATE_T, BAND_T, STRAP_T = 2.2, 1.4, 1.0
BAND_ROWS = (-27, -20, -13)
STRAP_Y, STRAP_HALF_W = 10.8, 2.2
# the strap's inside, from the front plate's top over the shoulder to the back plate's top: (x, z)
STRAP = [(12.6, 7.0), (8.0, 12.5), (3.5, 16.5), (0.5, 20.0), (-4.0, 21.8), (-9.0, 21.0), (-13.0, 18.0), (-15.8, 14.5)]
# --- end fit ---
AROUND = 24


def torso(z):
    """(front, back, half width) of the inner surface at height z (cm), interpolated in TORSO."""
    for (z0, *a), (z1, *b) in zip(TORSO, TORSO[1:]):
        if z0 <= z <= z1:
            t = (z - z0) / float(z1 - z0)
            return tuple(u + (v - u) * t for u, v in zip(a, b))
    return tuple(TORSO[0][1:] if z < TORSO[0][0] else TORSO[-1][1:])


def surface_x(y, z, side, grow=0.0):
    """x (cm) of the inner surface (grown by grow cm) at (y, z) on the front (side +1) or the back (side -1)."""
    front, back, w = torso(z)
    n, d = (N_FRONT, front) if side > 0 else (N_BACK, back)
    f = max(0.0, 1.0 - abs(y / w) ** n) ** (1.0 / n)
    return side * (d * f + grow)


def ring(z, grow):
    """The superellipse cross-section at height z, grown by grow cm, as AROUND points (metres), counter-clockwise from the front."""
    front, back, w = torso(z)
    pts = []
    for k in range(AROUND):
        c, s = dfmesh.superellipse(2 * math.pi * k / AROUND, N_FRONT if math.cos(2 * math.pi * k / AROUND) >= 0 else N_BACK)
        pts.append((c * ((front if c >= 0 else back) + grow) / 100.0, s * (w + grow) / 100.0, z / 100.0))
    return pts


def plate(rows, half_w, side, cols=7):
    """A plate over the front (side +1) or the back (side -1): PLATE_T thick, following the inner surface."""
    ys = [-half_w + 2 * half_w * k / (cols - 1) for k in range(cols)]
    if side < 0:
        ys.reverse()
    inner = [[(surface_x(y, z, side) / 100.0, y / 100.0, z / 100.0) for y in ys] for z in rows]
    outer = [[(surface_x(y, z, side, PLATE_T) / 100.0, y / 100.0, z / 100.0) for y in ys] for z in rows]
    return dfmesh.shell("plate", outer, inner, [FABRIC, DARK], wrap=False, wall_slot=1)


def strap(side):
    """A shoulder strap: STRAP thickened outwards by STRAP_T, STRAP_HALF_W either side of y = side * STRAP_Y."""
    out = []
    for i, (x, z) in enumerate(STRAP):
        (xa, za), (xb, zb) = STRAP[max(i - 1, 0)], STRAP[min(i + 1, len(STRAP) - 1)]
        tx, tz = xb - xa, zb - za
        ln = math.hypot(tx, tz)
        out.append((x + tz / ln * STRAP_T, z - tx / ln * STRAP_T))  # the path runs front to back: (tz, -tx) points outwards
    outline = [(x / 100.0, z / 100.0) for x, z in STRAP + list(reversed(out))]
    return dfmesh.profile("strap", outline, STRAP_HALF_W / 100.0, [DARK], y_m=side * STRAP_Y / 100.0)


def pouch(y, z, size, sink=0.3):
    """A Dark pouch (size: width, depth, height cm) on the front plate's face at (y, z)."""
    w, d, h = size
    x = surface_x(y, z, 1, PLATE_T) + d / 2.0 - sink
    return dfmesh.part(dfmesh.box("pouch", (d / 100.0, w / 100.0, h / 100.0), 0.006, (x / 100.0, y / 100.0, z / 100.0)), DARK)


def build(dims):
    band = dfmesh.shell("band", [ring(z, BAND_T) for z in BAND_ROWS], [ring(z, 0.0) for z in BAND_ROWS],
                        [FABRIC, DARK], wall_slot=1)
    parts = [plate(FRONT_ROWS, FRONT_HALF_W, 1), plate(BACK_ROWS, BACK_HALF_W, -1), band, strap(1), strap(-1)]
    parts += [pouch(y, -17.5, (7.0, 3.5, 10.0)) for y in (-7.6, 0.0, 7.6)]   # magazine pouches
    parts.append(pouch(8.0, -2.0, (5.5, 3.0, 8.5)))                          # radio pouch, left chest
    return dfmesh.assemble(parts, "SM_DF_Vest", [FABRIC, DARK])
