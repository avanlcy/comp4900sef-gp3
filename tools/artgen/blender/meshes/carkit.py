"""Shared pieces of the three Dead Fire car bodies (plan Task 12, spec 6.1), built to tools/artgen/data/dims.json.

Blender frame, metres: X forward, Y left (Unreal -Y), Z up; the origin is the vehicle actor's origin, so a body on the
hidden Sedan skeletal mesh lines up with its wheel bones. The physics wheel sits AdditionalOffset (12 cm) out from each
bone; SM_DF_Wheel carries that offset itself, so the arches are centred on the bones in X and Z and open across the
whole width. Each body joins its parts into one mesh with the slots Paint, Trim, Glass, Dark, Lights (in that order)
and gets the sockets Roof, Muzzle, Exhaust_L, Exhaust_R (yawed 180: their +X points backwards, along the flame) and
Arch_<bone> (test_meshes checks them against the bones).
"""
import math

import bpy

import dfmesh

TRIM, GLASS, DARK, LIGHTS = "MI_DF_Trim", "MI_DF_Glass", "MI_DF_Dark", "MI_DF_Lights"
ARCH_CLEAR_M = 0.04                  # above the tyre at full suspension raise
GUN_MUZZLE_M = (0.75, 0.0, 0.24)     # SM_DF_RoofGun's Muzzle from its origin; a body's Muzzle = Roof + this


def wheels(dims):
    """{bone: (x, y, z)} wheel bone positions in metres (Blender frame)."""
    return {b: dfmesh.ue_cm_to_m(p) for b, p in sorted(dims["wheels"].items())}


def axles(dims):
    """[(x, z)] wheel-bone centres per axle, rear first."""
    seen = {}
    for x, _, z in wheels(dims).values():
        seen[round(x, 4)] = (x, z)
    return [seen[k] for k in sorted(seen)]


def wheel_radius(dims):
    return dims["wheel_radius"] / 100.0


def arch_radius(dims):
    return wheel_radius(dims) + dims.get("suspension_max_raise", 0.0) / 100.0 + ARCH_CLEAR_M


def _arc(xc, zc, r, z_b, segs, outward=0.0):
    """Points of the circle (xc, zc, r + outward) from where radius r meets z = z_b behind the centre, over the top, to
    where it meets it in front (both ends clipped to z_b)."""
    d = math.sqrt(max(r * r - (zc - z_b) ** 2, 0.0))
    a0 = math.atan2(z_b - zc, -d)
    a0 += 2 * math.pi if a0 < 0 else 0.0
    a1 = math.atan2(z_b - zc, d)
    rr = r + outward
    pts = [(xc + rr * math.cos(a0 + (a1 - a0) * k / segs), zc + rr * math.sin(a0 + (a1 - a0) * k / segs)) for k in range(segs + 1)]
    if outward:  # the flare's ends come straight down to z_b
        pts[0] = (pts[0][0], max(pts[0][1], z_b))
        pts[-1] = (pts[-1][0], max(pts[-1][1], z_b))
    return pts


def side_outline(dims, z_bottom, upper, segs=10):
    """A body's side profile with the wheel arches: `upper` runs from the front-bottom corner over the top to the
    rear-bottom corner; the bottom edge (z_bottom) runs back to the front, notched by an arch at each axle.
    Returns (points, edge_slots): the arch edges take slot 1 (Dark), the rest slot 0 (Paint)."""
    r = arch_radius(dims)
    pts, slots = list(upper), [0] * len(upper)
    for xc, zc in axles(dims):  # rear axle first: the bottom edge runs rear to front
        arc = _arc(xc, zc, r, z_bottom, segs)
        slots[-1] = 0           # the edge from the previous point to the arch start is plain bottom
        pts += arc
        slots += [1] * len(arc)
    slots[-1] = 0               # the last arch point back to the front-bottom corner
    return pts, slots


def flares(dims, paint_or_dark, half_w, z_bottom, width_m=0.08, thick_m=0.05, segs=10):
    """A fender flare round each arch on both sides: a band width_m wide standing thick_m off the side at half_w."""
    r = arch_radius(dims)
    out = []
    for xc, zc in axles(dims):
        inner = _arc(xc, zc, r, z_bottom, segs)
        outer = _arc(xc, zc, r, z_bottom, segs, outward=width_m)
        band = outer + list(reversed(inner))
        for side in (1, -1):
            out.append(dfmesh.profile("flare", band, thick_m / 2, [paint_or_dark], bevel_m=0.012,
                                      y_m=side * (half_w + thick_m / 2 - 0.01)))
    return out


def tyre_inner_y(dims):
    """|y| of a tyre's inner face (metres), from SM_DF_Wheel's layout."""
    from meshes import wheel
    _, w, off, _ = wheel.layout(dims)
    return abs(next(iter(wheels(dims).values()))[1]) + off - w / 2


def liner_half_widths(dims, clear_m=0.03):
    """(rear, front) half widths of the well liners: clear of the tyres' inner faces, and at the front clear of the
    inner corner of a tyre steered to full lock (dims steer_angle) about its bone."""
    from meshes import wheel
    r, w, off, _ = wheel.layout(dims)
    bone_y = abs(next(iter(wheels(dims).values()))[1])
    a = math.radians(dims.get("steer_angle", 0.0))
    swing = r * math.sin(a) - (off - w / 2) * math.cos(a)  # how far the inner tread corner swings inside the bone
    return tyre_inner_y(dims) - clear_m, bone_y - max(swing, 0.0) - clear_m


def well_liners(dims, z_bottom, segs=10):
    """Dark plugs in each arch between the tyres (liner_half_widths), so an arch shows a wheel well instead of the
    far side of the car."""
    r = arch_radius(dims)
    return [dfmesh.profile("liner", _arc(xc, zc, r - 0.005, z_bottom, segs), hw, [DARK])
            for (xc, zc), hw in zip(axles(dims), liner_half_widths(dims))]


def cabin_strip(bottom, top, x, side, slot, width=0.07):
    """A strip lying up a dfmesh.frustum cabin's side face at x (it leans in with the tumblehome), e.g. a B-pillar."""
    (_, _, bw, bz), (_, _, tw, tz) = bottom, top
    lean = math.atan2(bw - tw, tz - bz)
    h = math.hypot(bw - tw, tz - bz)
    return box((width, 0.02, h - 0.02), (x, side * ((bw + tw) / 2 + 0.004), (bz + tz) / 2), slot,
               rot_deg=(math.degrees(lean) * side, 0, 0))


def strip(points_xz, y_c, half_w, slot, lift=0.004, thick=0.008):
    """A thin band lying on a top surface along the polyline points_xz (e.g. a stripe over a sloping hood)."""
    pts = [(x, z + lift) for x, z in points_xz] + [(x, z + lift + thick) for x, z in reversed(points_xz)]
    return dfmesh.profile("strip", pts, half_w, [slot], y_m=y_c)


def box(size, loc, slot, bevel=0.0, rot_deg=(0, 0, 0)):
    o = dfmesh.part(dfmesh.box("part", size, bevel, loc), slot)
    o.rotation_euler = [math.radians(a) for a in rot_deg]
    return o


def mirrored(make):
    """make(side) for side = +1 (left) and -1 (right)."""
    return [make(1), make(-1)]


def finish(parts, name, paint):
    """The body as one mesh with the slots Paint, Trim, Glass, Dark, Lights, unwrapped."""
    return dfmesh.assemble(parts, name, [paint, TRIM, GLASS, DARK, LIGHTS])


def sockets(root, dims, roof_m, exhaust_m):
    """Roof (top of the roof, where the roof weapon and SEDAN's light bar mount), Muzzle (the roof gun's muzzle seen
    from the Roof socket), Exhaust_L/_R (exhaust_m is the left tip; yawed 180) and Arch_<bone> at each wheel bone."""
    dfmesh.socket(root, "Roof", roof_m)
    dfmesh.socket(root, "Muzzle", tuple(a + b for a, b in zip(roof_m, GUN_MUZZLE_M)))
    x, y, z = exhaust_m
    dfmesh.socket(root, "Exhaust_L", (x, abs(y), z), (0, 0, 180))
    dfmesh.socket(root, "Exhaust_R", (x, -abs(y), z), (0, 0, 180))
    for bone, p in wheels(dims).items():
        dfmesh.socket(root, "Arch_" + bone, p)
    bpy.context.view_layer.update()
    return root
