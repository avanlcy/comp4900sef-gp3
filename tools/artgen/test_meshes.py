"""Checks the generated meshes: file present, triangle budget, UVs, material slots, sockets, bounds (plan Task 4), and
the car parts against the template vehicle's measurements in tools/artgen/data/dims.json (plan Task 12), the rifle's length
and muzzle (plan Task 14), where the effect shells' origins sit (plan Task 15), the rocket's centre and exhaust (Task 16),
the crate's stripe slot and lid seat and the flat bomb (Task 17), and the environment meshes (Task 20): the unit-contract
meshes' 100 cm cube centred on the origin, the ramp and wedge on the VehicleAdv originals' bounds (dims.json), the road
slab's top-face UVs, and the gate: a 6 m pylon and a 100 cm banner hung clear of the cars.
Reads art/meshes/<name>.fbx and the <name>.json stats the Blender runner wrote beside it.

    python -I tools/artgen/test_meshes.py
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
from artgen import catalog  # noqa: E402

ART = os.path.join(os.path.dirname(os.path.dirname(HERE)), "art")
MESHES = os.path.join(ART, "meshes")
DIMS = os.path.join(HERE, "data", "dims.json")
TOL_CM = 2.0
ARCH_TOL_CM = 2.0      # an arch centre (socket Arch_<bone>) from its wheel bone
BODY_TOL_CM = 15.0     # each face of a body's bounds from the physics asset's chassis box
BRUTE_RISE_CM = 40.0   # BRUTE may stand this much taller than the box
WHEEL_TOL_CM = 1.0     # the wheel's radius from the wheel classes' ShapeRadius
CARS = ("SM_DF_Car_Sedan", "SM_DF_Car_Brute", "SM_DF_Car_Viper")
RIFLE_CM = 90.0        # SM_DF_Rifle's length (spec 6.2, plan Task 14)
ROCKET_CM = 70.0       # SM_DF_Rocket's length (plan Task 16)
CRATE_HALF_CM = 40.0   # SM_DF_Crate: its base this far below the origin, the lid's top as far above (Task 17 fix round 1)
# Task 20 (spec 8.2): the meshes that replace the engine cube keep its unit contract (100 cm, centred), so the Blueprints'
# scaling code is unchanged; the ramp and wedge sit on the VehicleAdv originals' bounds (dims.json key), so the layout and
# the AI are unchanged; the road slab's top face maps U 0..1 along X and V 0..1 across Y (M_DF_Road's lines).
# The gate (controller ruling, Task 20): the pylons no longer keep the VehicleAdv pole's bounds (they never collide); each is
# GATE_PYLON_CM tall from the gate's origin on the road, its foot sunk at most GATE_FOOT_CM; the banner is 100 cm on Y (scaled
# to the pylon spacing at run time), centred, its underside at least GATE_CLEAR_CM over the road and its top no higher than
# the pylons'.
UNIT_CONTRACT = ("SM_DF_RoadSlab", "SM_DF_Barrier", "SM_DF_RockWall")
UNIT_CM, UNIT_TOL_CM = 100.0, 0.5
MATCHED = {"SM_DF_Ramp": "ramp", "SM_DF_BumpWedge": "bump_wedge"}
GATE_PYLON_CM, GATE_PYLON_TOL_CM, GATE_FOOT_CM = 600.0, 5.0, 30.0
GATE_CLEAR_CM = 400.0
UV_TOL = 0.01

checks = 0
failures = []


def check(ok, msg):
    global checks
    checks += 1
    if not ok:
        failures.append(msg)


def _stats(name):
    path = os.path.join(MESHES, name + ".json")
    if not os.path.isfile(path):
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def ue_point(p):
    """A stats point (Blender frame, cm) in Unreal's frame: Blender +Y is Unreal -Y (Task 5)."""
    return [p[0], -p[1], p[2]]


def ue_box(st):
    """(min, max) of a stats JSON's bounds in Unreal's frame."""
    lo, size = st["min_cm"], st["bounds_cm"]
    return [lo[0], -(lo[1] + size[1]), lo[2]], [lo[0] + size[0], -lo[1], lo[2] + size[2]]


def check_cars(dims):
    """Plan Task 12 / spec 6.1: arch centres on the wheel bones, bodies on the physics box, the wheel's radius."""
    wheels, box = dims.get("wheels", {}), dims.get("body_box", {})
    check(len(wheels) == 4, "dims.json has %d wheels, want 4" % len(wheels))
    check("min" in box and "max" in box, "dims.json has no body_box")
    for name in CARS:
        st = _stats(name)
        check(st is not None, "%s: stats missing" % name)
        if st is None or "min" not in box:
            continue
        for bone, want in sorted(wheels.items()):
            sock = st["sockets"].get("Arch_" + bone)
            check(sock is not None, "%s: socket Arch_%s missing" % (name, bone))
            if sock is not None:
                d = sum((a - b) ** 2 for a, b in zip(ue_point(sock), want)) ** 0.5
                check(d <= ARCH_TOL_CM, "%s: Arch_%s is %.1f cm from the bone (%s vs %s)" % (name, bone, d, ue_point(sock), want))
        lo, hi = ue_box(st)
        for i, axis in enumerate("XYZ"):
            check(abs(lo[i] - box["min"][i]) <= BODY_TOL_CM,
                  "%s: min %s %.1f cm, body_box %.1f +-%g" % (name, axis, lo[i], box["min"][i], BODY_TOL_CM))
            top = BRUTE_RISE_CM if (name == "SM_DF_Car_Brute" and axis == "Z") else BODY_TOL_CM
            check(-BODY_TOL_CM <= hi[i] - box["max"][i] <= top,
                  "%s: max %s %.1f cm, body_box %.1f -%g/+%g" % (name, axis, hi[i], box["max"][i], BODY_TOL_CM, top))
    r = dims.get("wheel_radius")
    check(r is not None, "dims.json has no wheel_radius")
    st = _stats("SM_DF_Wheel")
    check(st is not None, "SM_DF_Wheel: stats missing")
    if st is not None and r is not None:
        # radius in X and Z, and centred on its hub there (the wheel hangs on the bone socket)
        for i, axis in ((0, "X"), (2, "Z")):
            check(abs(st["bounds_cm"][i] / 2 - r) <= WHEEL_TOL_CM, "SM_DF_Wheel: radius along %s %.1f cm, want %g" % (axis, st["bounds_cm"][i] / 2, r))
            check(abs(st["min_cm"][i] + r) <= WHEEL_TOL_CM, "SM_DF_Wheel: min %s %.1f cm, want %g (origin at the hub)" % (axis, st["min_cm"][i], -r))
        # the tyre runs where the physics wheel runs: centred AdditionalOffset out from the bone (Blender +Y)
        off = max(abs(o[1]) for o in dims.get("wheel_offset", {"": [0, 0, 0]}).values())
        mid = st["min_cm"][1] + st["bounds_cm"][1] / 2
        check(abs(mid - off) <= WHEEL_TOL_CM, "SM_DF_Wheel: tyre centred %.1f cm out from the hub, want %g" % (mid, off))


def check_rifle():
    """Plan Task 14 / spec 6.2: the rifle is about 90 cm long along +X, its Muzzle socket at the barrel tip on the bore."""
    st = _stats("SM_DF_Rifle")
    check(st is not None, "SM_DF_Rifle: stats missing")
    if st is None:
        return
    check(abs(st["bounds_cm"][0] - RIFLE_CM) <= TOL_CM, "SM_DF_Rifle: %.1f cm long, want %g +-%g" % (st["bounds_cm"][0], RIFLE_CM, TOL_CM))
    m = st["sockets"].get("Muzzle")
    if m is not None:
        tip = st["min_cm"][0] + st["bounds_cm"][0]
        check(abs(m[0] - tip) <= 1.0 and abs(m[1]) <= 0.5, "SM_DF_Rifle: Muzzle %s, want x at the tip %.1f on the bore" % (m, tip))


FX_CENTRED = ("SM_DF_FxSphere", "SM_DF_FxRing", "SM_DF_FxStar")  # symmetric shells: the bounds' centre on the origin
FX_ALONG_X = ("SM_DF_FxBeam", "SM_DF_FxCone")  # start at the origin, run along +X, centred on the X axis


def check_fx():
    """Plan Task 15 / spec 7.1: the effect shells scale about their origin, so it must sit where the effect starts:
    the centre of the round shells, the start of the beam (SetEnds scales X by distance / 100) and the cone's tip."""
    for name in FX_CENTRED + FX_ALONG_X:
        st = _stats(name)
        check(st is not None, "%s: stats missing" % name)
        if st is None:
            continue
        mid = [lo + size / 2 for lo, size in zip(st["min_cm"], st["bounds_cm"])]
        axes = (1, 2) if name in FX_ALONG_X else (0, 1, 2)
        for i in axes:
            check(abs(mid[i]) <= 0.5, "%s: bounds centre %s %.2f cm from the origin" % (name, "XYZ"[i], mid[i]))
        if name in FX_ALONG_X:
            check(abs(st["min_cm"][0]) <= 0.5, "%s: starts at X %.2f cm, want 0 (the origin)" % (name, st["min_cm"][0]))
    beam = _stats("SM_DF_FxBeam")
    if beam is not None:
        check(abs(beam["bounds_cm"][0] - 100.0) <= 0.5, "SM_DF_FxBeam: %.2f cm long, want 100" % beam["bounds_cm"][0])


def check_rocket():
    """Plan Task 16: the rocket is centred on its origin (the projectile's collision sphere), 70 cm along +X, with its Exhaust
    socket on the axis at the tail (min X), where the flame hangs."""
    st = _stats("SM_DF_Rocket")
    check(st is not None, "SM_DF_Rocket: stats missing")
    if st is None:
        return
    check(abs(st["bounds_cm"][0] - ROCKET_CM) <= TOL_CM, "SM_DF_Rocket: %.1f cm long, want %g +-%g" % (st["bounds_cm"][0], ROCKET_CM, TOL_CM))
    mid = [lo + size / 2 for lo, size in zip(st["min_cm"], st["bounds_cm"])]
    for i in range(3):
        check(abs(mid[i]) <= 0.5, "SM_DF_Rocket: bounds centre %s %.2f cm from the origin" % ("XYZ"[i], mid[i]))
    e = st["sockets"].get("Exhaust")
    if e is not None:
        check(abs(e[0] - st["min_cm"][0]) <= 1.0 and abs(e[1]) <= 0.5 and abs(e[2]) <= 0.5,
              "SM_DF_Rocket: Exhaust %s, want x at the tail %.1f on the axis" % (e, st["min_cm"][0]))


def check_items():
    """Plan Task 17: the crate's and the lid's glowing stripe is a slot of its own (BP_DFLootBox tints slot 1); the crate's Lid
    socket is centred on its top, where the lid sits; the bomb is a mine, not a ball (round, and at most half as tall as it is
    wide) with its Lamp socket centred on its top."""
    for name in ("SM_DF_Crate", "SM_DF_CrateLid"):
        st = _stats(name)
        check(st is not None, "%s: stats missing" % name)
        if st is not None:
            check(st["slots"][1:2] == ["MI_DF_CrateStripe"], "%s: slot 1 is %s, want the stripe MI_DF_CrateStripe" % (name, st["slots"][1:2]))
    crate, lid_st = _stats("SM_DF_Crate"), _stats("SM_DF_CrateLid")
    if crate is not None and "Lid" in crate["sockets"]:
        top = crate["min_cm"][2] + crate["bounds_cm"][2]
        lid = crate["sockets"]["Lid"]
        check(abs(lid[0]) <= 0.5 and abs(lid[1]) <= 0.5, "SM_DF_Crate: Lid socket %s, want it on the vertical axis" % lid)
        check(top - 1.0 <= lid[2] <= top + 0.5, "SM_DF_Crate: Lid socket at z %.1f, want the crate's top %.1f" % (lid[2], top))
        # fix round 1: the origin is the centre of the crate and lid together (a crate actor stands 40 cm over the ground)
        check(abs(crate["min_cm"][2] + CRATE_HALF_CM) <= 0.5,
              "SM_DF_Crate: base at z %.1f, want %g (the origin at the crate's centre)" % (crate["min_cm"][2], -CRATE_HALF_CM))
        if lid_st is not None:
            lid_top = lid[2] + lid_st["min_cm"][2] + lid_st["bounds_cm"][2]
            check(abs(lid_top - CRATE_HALF_CM) <= 1.0, "SM_DF_Crate + lid: top at z %.1f, want %g" % (lid_top, CRATE_HALF_CM))
    bomb = _stats("SM_DF_Bomb")
    check(bomb is not None, "SM_DF_Bomb: stats missing")
    if bomb is None:
        return
    x, y, z = bomb["bounds_cm"]
    check(abs(x - y) <= TOL_CM, "SM_DF_Bomb: %.1f x %.1f cm across, want it round" % (x, y))
    check(z <= 0.5 * x, "SM_DF_Bomb: %.1f cm tall and %.1f cm across: a ball, not a flat mine" % (z, x))
    lamp = bomb["sockets"].get("Lamp")
    if lamp is not None:
        check(abs(lamp[0]) <= 0.5 and abs(lamp[1]) <= 0.5 and abs(lamp[2] - (bomb["min_cm"][2] + z)) <= 1.0,
              "SM_DF_Bomb: Lamp socket %s, want it centred on the top" % lamp)


def check_environment(dims):
    """Plan Task 20 / spec 8.2: the unit-contract meshes are a 100 cm cube centred on the origin; the ramp, the bump wedge
    match their VehicleAdv original's bounds (Unreal frame, the same origin) within TOL_CM; the road
    slab's top face runs U 0..1 along X and V 0..1 across Y (stats top_uv: the range, and the change from the -X end to the
    +X end and from the -Y side to the +Y side)."""
    for name in UNIT_CONTRACT:
        st = _stats(name)
        check(st is not None, "%s: stats missing" % name)
        if st is None:
            continue
        for i, axis in enumerate("XYZ"):
            size, mid = st["bounds_cm"][i], st["min_cm"][i] + st["bounds_cm"][i] / 2
            check(abs(size - UNIT_CM) <= UNIT_TOL_CM, "%s: %s size %.2f cm, want the unit %g" % (name, axis, size, UNIT_CM))
            check(abs(mid) <= UNIT_TOL_CM, "%s: bounds centre %s %.2f cm from the origin, want centred" % (name, axis, mid))
    for name, key in sorted(MATCHED.items()):
        st, want = _stats(name), dims.get(key)
        check(st is not None, "%s: stats missing" % name)
        check(want is not None, "dims.json has no %s" % key)
        if st is None or want is None:
            continue
        lo, hi = ue_box(st)
        for i, axis in enumerate("XYZ"):
            check(abs(lo[i] - want["min"][i]) <= TOL_CM, "%s: min %s %.2f cm, dims %s %.2f +-%g" % (name, axis, lo[i], key, want["min"][i], TOL_CM))
            check(abs(hi[i] - want["max"][i]) <= TOL_CM, "%s: max %s %.2f cm, dims %s %.2f +-%g" % (name, axis, hi[i], key, want["max"][i], TOL_CM))
    st = _stats("SM_DF_RoadSlab")
    uv = st.get("top_uv") if st else None
    check(uv is not None, "SM_DF_RoadSlab: stats have no top_uv (top-face UV range)")
    if uv is not None:
        ok = all(abs(a - b) <= UV_TOL for a, b in zip(uv["min"] + uv["max"], (0.0, 0.0, 1.0, 1.0)))
        check(ok, "SM_DF_RoadSlab: top-face UVs %s..%s, want (0, 0)..(1, 1)" % (uv["min"], uv["max"]))
        du, dv = uv["along_x"]
        check(abs(du - 1.0) <= UV_TOL and abs(dv) <= UV_TOL, "SM_DF_RoadSlab: from -X to +X the top UV changes by %s, want U +1 (U along X)" % uv["along_x"])
        du, dv = uv["along_y"]
        check(abs(du) <= UV_TOL and abs(abs(dv) - 1.0) <= UV_TOL, "SM_DF_RoadSlab: across Y the top UV changes by %s, want V 1 (V across Y)" % uv["along_y"])


def check_gate():
    """Controller ruling (Task 20): the gate pylon stands GATE_PYLON_CM tall on the gate's origin (its foot sunk no more than
    GATE_FOOT_CM, the VehicleAdv pole's convention); the banner is 100 cm on Y and centred there (BP_DFCheckpoint scales it to
    the pylon spacing), hangs with its underside at least GATE_CLEAR_CM over the road, and its top is no higher than the
    pylons'."""
    pylon, banner = _stats("SM_DF_GatePylon"), _stats("SM_DF_GateBanner")
    check(pylon is not None, "SM_DF_GatePylon: stats missing")
    check(banner is not None, "SM_DF_GateBanner: stats missing")
    if pylon is not None:
        top = pylon["min_cm"][2] + pylon["bounds_cm"][2]
        check(abs(top - GATE_PYLON_CM) <= GATE_PYLON_TOL_CM, "SM_DF_GatePylon: %.1f cm tall, want %g +-%g" % (top, GATE_PYLON_CM, GATE_PYLON_TOL_CM))
        check(-GATE_FOOT_CM <= pylon["min_cm"][2] <= 0.5, "SM_DF_GatePylon: foot at z %.1f cm, want 0 to -%g" % (pylon["min_cm"][2], GATE_FOOT_CM))
    if banner is not None:
        y, mid = banner["bounds_cm"][1], banner["min_cm"][1] + banner["bounds_cm"][1] / 2
        check(abs(y - 100.0) <= 0.5 and abs(mid) <= 0.5, "SM_DF_GateBanner: %.2f cm on Y, centre %.2f, want 100 centred" % (y, mid))
        check(banner["min_cm"][2] >= GATE_CLEAR_CM, "SM_DF_GateBanner: underside %.1f cm over the road, want at least %g" % (banner["min_cm"][2], GATE_CLEAR_CM))
        if pylon is not None:
            top = pylon["min_cm"][2] + pylon["bounds_cm"][2]
            check(banner["min_cm"][2] + banner["bounds_cm"][2] <= top + 0.5,
                  "SM_DF_GateBanner: top %.1f cm, above the pylons' %.1f" % (banner["min_cm"][2] + banner["bounds_cm"][2], top))


def main():
    dims = {}
    if os.path.isfile(DIMS):
        with open(DIMS, encoding="utf-8") as f:
            dims = json.load(f)
    check(bool(dims),"%s missing (run comp4900sef/Script/df_export_dims.py in the editor)" % DIMS)
    check_cars(dims)
    check_rifle()
    check_fx()
    check_rocket()
    check_items()
    check_environment(dims)
    check_gate()
    built =[m for m in catalog.MESHES if m.script != "todo"]
    check(len(built) >= 2, "at least the fixture and the barrel have recipes")
    for m in built:
        fbx = os.path.join(MESHES, m.name + ".fbx")
        js = os.path.join(MESHES, m.name + ".json")
        check(os.path.isfile(fbx) and os.path.getsize(fbx) > 0, "%s: %s missing or empty" % (m.name, fbx))
        check(os.path.isfile(js), "%s: stats %s missing" % (m.name, js))
        if not os.path.isfile(js):
            continue
        with open(js, encoding="utf-8") as f:
            st = json.load(f)
        check(0 < st["tris"] <= m.budget, "%s: %s tris, budget %d" % (m.name, st["tris"], m.budget))
        check(st["has_uv"] is True, "%s: no UV layer" % m.name)
        check(list(st["slots"]) == list(m.slots), "%s: slots %s, catalogue %s" % (m.name, st["slots"], list(m.slots)))
        for s in m.sockets:
            check(s in st["sockets"], "%s: socket %s missing" % (m.name, s))
        if m.bounds:
            for axis, want, got in zip("XYZ", m.bounds, st["bounds_cm"]):
                check(abs(want - got) <= TOL_CM, "%s: bounds %s %.2f cm, want %s +-%s" % (m.name, axis, got, want, TOL_CM))
        if m.origin == "base":
            check(abs(st["min_cm"][2]) <= 0.5, "%s: base origin but min Z is %.2f cm" % (m.name, st["min_cm"][2]))
    fx = os.path.join(MESHES, "SM_DF_AxisFixture.json")
    if os.path.isfile(fx):
        with open(fx, encoding="utf-8") as f:
            b = json.load(f)["bounds_cm"]
        check(all(abs(a - e) <= TOL_CM for a, e in zip(b, (200, 50, 100))), "fixture bounds %s, want (200, 50, 100)" % b)
    if failures:
        print("FAIL: %d of %d checks" % (len(failures), checks))
        for f in failures:
            print("  - " + f)
        sys.exit(1)
    print("OK: %d checks" % checks)


if __name__ == "__main__":
    main()
