"""BP_DFVehicle (plan Tasks 3 and 5): child of the Vehicle template's Sedan.

Health, tires, damage routing, destruction, drive overrides, enter/exit, teleport. Driving, cameras and the
in-car HUD text come from the Sedan parent untouched.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from df import *  # noqa: E402,F401,F403
from df import (ACTOR, BOOL, BP_CHARACTER, BP_GM, BP_VEHICLE, CONTROLLER, FLOAT, HIT_RESULT, INT, MATH, NAME, OBJECT,  # noqa: E402
                OUT, PAWN, PRIMITIVE, S_TIRE, SCENE_COMP, SEDAN, SKEL_MESH_COMP, STRUCT, SYS, TRANSFORM, VECTOR,
                WHEELED_MOVE, Blueprint, Graph, Node, Pin, and_bool, as_pin, cast_to, cls_ref, compare, gen,
                get_game_mode, is_valid, math2, member, not_bool, obj_pin, obj_spec, struct_path, struct_pin,
                struct_spec)
from df import MATERIAL_INTERFACE, PAINT_SLOT, SEDAN_MASS, STRING, VEHICLES  # noqa: E402

VC, CC, GMC = gen(BP_VEHICLE), gen(BP_CHARACTER), gen(BP_GM)
TIRE = struct_path(S_TIRE)
WHEEL_BONES = ["Wheel_Front_Left", "Wheel_Front_Right", "Wheel_Rear_Left", "Wheel_Rear_Right"]


def mesh(g: Graph, col=None, row=None) -> Node:
    return g.var_get("Mesh", OBJECT, cls_ref(SKEL_MESH_COMP), col=col, row=row)


def movement(g: Graph, col=None, row=None) -> Node:
    return g.var_get("VehicleMovement", OBJECT, cls_ref(WHEELED_MOVE), col=col, row=row)


def mv_call(g: Graph, fn: str, inputs=None, outputs=None, pure=False, col=None, row=None, **defaults) -> Node:
    """Call a WheeledVehicleMovementComponent function on this vehicle's movement component."""
    mv = movement(g)
    n = g.call_on(WHEELED_MOVE, fn, inputs=inputs, outputs=outputs, pure=pure, col=col, row=row, **defaults)
    g.link(mv, "VehicleMovement", n, "self")
    return n


def set_throttle(g, value_default=None):
    return mv_call(g, "SetThrottleInput", inputs=[Pin("Throttle", FLOAT, default=value_default)])


def drive_throttle(g: Graph, input_src) -> Node:
    """self.ComputeDriveThrottle(input, GetSpeedKPH()) (pure): the car's throttle scale and speed limiter (Phase 5)."""
    n = g.call_self("ComputeDriveThrottle", inputs=[Pin("Input", FLOAT), Pin("SpeedKPH", FLOAT)], outputs=[Pin("Throttle", FLOAT, "out")], pure=True)
    g.link(input_src[0], input_src[1], n, "Input")
    kph = g.call_self("GetSpeedKPH", outputs=[Pin("KPH", FLOAT, "out")], pure=True)
    g.link(kph, "KPH", n, "SpeedKPH")
    return n


def set_steering(g, value_default=None):
    return mv_call(g, "SetSteeringInput", inputs=[Pin("Steering", FLOAT, default=value_default)])


def set_handbrake(g, value: str):
    return mv_call(g, "SetHandbrakeInput", inputs=[Pin("bNewHandbrake", BOOL, default=value)])


def break_tire(g: Graph, col=None, row=None) -> Node:
    return g.break_struct(TIRE, [Pin(member(S_TIRE, "BoneName"), NAME), Pin(member(S_TIRE, "Health"), FLOAT),
                                 Pin(member(S_TIRE, "MaxHealth"), FLOAT), Pin(member(S_TIRE, "bBlown"), BOOL)],
                          col=col, row=row)


def make_tire(g: Graph, bone_default=None, col=None, row=None) -> Node:
    return g.make_struct(TIRE, [Pin(member(S_TIRE, "BoneName"), NAME, default=bone_default),
                                Pin(member(S_TIRE, "Health"), FLOAT), Pin(member(S_TIRE, "MaxHealth"), FLOAT),
                                Pin(member(S_TIRE, "bBlown"), BOOL, default="false")], col=col, row=row)


def tires_get(g: Graph) -> Node:
    return g.var_get("Tires", STRUCT, struct_ref_tire(), container="Array")


def struct_ref_tire():
    from bpgen import struct_ref
    return struct_ref(TIRE)


def tire_elem() -> Pin:
    return Pin("e", STRUCT, sub_object=struct_ref_tire())


def result_bool(g: Graph, value: str) -> Node:
    return g.function_result([Pin("ReturnValue", BOOL, default=value)])


def build() -> Blueprint:
    bp = Blueprint(BP_VEHICLE, parent=SEDAN, description="The race car: health and tires, damage, wrecking, enter/exit, item use; driving and cameras come from the Sedan template.")
    bp.component("Weapon", gen(BPC_WEAPON), Damage=15.0, Range=10000.0, Cooldown=0.2, bDebugTrace=False)  # the car's gun (spec §2)
    H, E = "Dead Fire|Health", "Dead Fire|Enter Exit"
    bp.variable("MaxHealth", "float", "100", H, editable=True)
    bp.variable("Health", "float", "100", H)
    bp.variable("TireMaxHealth", "float", "30", H, editable=True)
    bp.variable("BlownTireSpeedScale", "float", "0.8", H, editable=True)
    bp.variable("TireHitRadius", "float", "60", H, editable=True)
    bp.variable("Tires", "array<%s>" % struct_spec(S_TIRE), "", H)
    bp.variable("BlownTireCount", "int", "0", H)
    bp.variable("bIsDestroyed", "bool", "false", H)
    bp.variable("bPointDamageHandled", "bool", "false", H)
    bp.variable("ExitMaxSpeedKPH", "float", "10", E, editable=True)
    bp.variable("ExitSideOffset", "float", "220", E, editable=True)
    bp.variable("ExitUpOffset", "float", "100", E, editable=True)
    bp.variable("ExitBehindOffset", "float", "350", E, editable=True)
    bp.variable("Occupant", obj_spec(BP_CHARACTER), "", E)
    bp.variable("LastDriver", "object:" + CONTROLLER, "", E)
    I = "Dead Fire|Items"
    bp.variable("WreckHopImpulse", "float", "600", I, editable=True)
    bp.variable("WreckSmokeEffect", "object:" + PARTICLE_SYSTEM, "", I, editable=True)
    bp.default("WreckSmokeEffect", "/Game/StarterContent/Particles/P_Smoke")
    bp.variable("BoostRemaining", "float", "0", I)
    bp.variable("ShieldRemaining", "float", "0", I)
    bp.variable("BoostDuration", "float", "2", I, editable=True)
    bp.variable("BoostKickSpeed", "float", "1200", I, editable=True)
    bp.variable("BoostAcceleration", "float", "2500", I, editable=True)
    bp.variable("ShieldDuration", "float", "6", I, editable=True)
    bp.variable("BombDropOffset", "float", "400", I, editable=True)
    bp.variable("MuzzleForward", "float", "300", I, editable=True)
    bp.variable("MuzzleUp", "float", "80", I, editable=True)
    A = "Dead Fire|AI"  # Phase 4: an AI controller's inputs (spec §2.1); the axis events never fire for an AI-possessed pawn
    bp.variable("bAIControlled", "bool", "false", A)
    bp.variable("AIThrottle", "float", "0", A)
    bp.variable("AISteering", "float", "0", A)
    bp.variable("bAIHandbrake", "bool", "false", A)
    bp.variable("AimTarget", "object:" + ACTOR, "", A)  # set by an AI for one shot: the gun and the rocket aim at it (spec §3.2)
    # Phase 5 (spec 2026-10-30 phase 5 §3.2): what makes one car differ from another; the children override these defaults
    ST = "Dead Fire|Stats"
    bp.variable("VehicleName", "string", "SEDAN", ST, editable=True)
    bp.variable("ThrottleScale", "float", "1", ST, editable=True)
    bp.variable("TopSpeedKPH", "float", "0", ST, editable=True)  # 0 = no limiter
    bp.variable("PaintMaterial", "object:" + MATERIAL_INTERFACE, "", ST, editable=True)  # none = the template paint
    bp.variable("PaintSlot", "int", str(PAINT_SLOT), ST, editable=True)

    bp.dispatcher("OnVehicleDamaged", ["Damage:float", "TireIndex:int"])
    bp.dispatcher("OnTireBlown", ["TireIndex:int"])
    bp.dispatcher("OnVehicleDestroyed", ["Vehicle:" + obj_spec(BP_VEHICLE), "Killer:object:" + CONTROLLER])
    bp.dispatcher("OnOccupantEntered", ["Character:" + obj_spec(BP_CHARACTER)])
    bp.dispatcher("OnOccupantExited", ["Character:" + obj_spec(BP_CHARACTER)])

    # ---- InitTires: Tires = four fresh entries ----
    g = bp.function("InitTires", doc="Four fresh tires at TireMaxHealth.")
    clear = g.call_array("KismetArrayLibrary", "Array_Clear", tire_elem(), pure=False)
    arr = tires_get(g)
    g.link(arr, "Tires", clear, "TargetArray")
    g.link_entry("then", clear, "execute")
    prev = clear
    for bone in WHEEL_BONES:
        mk = make_tire(g, bone_default=bone)
        mx = g.var_get("TireMaxHealth", FLOAT)
        g.link(mx, "TireMaxHealth", mk, member(S_TIRE, "Health"))
        g.link(mx, "TireMaxHealth", mk, member(S_TIRE, "MaxHealth"))
        add = g.call_array("KismetArrayLibrary", "Array_Add", tire_elem(),
                           inputs=[Pin("NewItem", STRUCT, sub_object=struct_ref_tire())],
                           outputs=[Pin("ReturnValue", INT, "out")], pure=False)
        a2 = tires_get(g)
        g.link(a2, "Tires", add, "TargetArray")
        g.link(mk, TIRE.rsplit(".", 1)[1], add, "NewItem")
        g.exec(prev, add)
        prev = add
    zero = g.var_set("BlownTireCount", INT, default="0")
    g.exec(prev, zero)

    # ---- GetSpeedKPH ----
    g = bp.function("GetSpeedKPH", doc="Absolute forward speed in km/h.", outputs=["KPH:float"], pure=True)
    fwd = mv_call(g, "GetForwardSpeed", outputs=[Pin("ReturnValue", FLOAT, "out")], pure=True)
    ab = g.call_static(MATH, "Abs", inputs=[Pin("A", FLOAT)], outputs=[Pin("ReturnValue", FLOAT, "out")], pure=True)
    mul = math2(g, "Multiply_FloatFloat", FLOAT, b="0.036")
    g.link(fwd, "ReturnValue", ab, "A")
    g.link(ab, "ReturnValue", mul, "A")
    g.link_result(mul, "ReturnValue", "KPH")
    g.link_entry("then", "result", "execute")

    # ---- GetGearString: R / N / number ----
    g = bp.function("GetGearString", doc="R, N or the gear number for the HUD.", outputs=["Gear:string"], pure=True)
    gear = mv_call(g, "GetCurrentGear", outputs=[Pin("ReturnValue", INT, "out")], pure=True)
    lt = compare(g, "Less_IntInt", INT, b="0")
    eq = compare(g, "EqualEqual_IntInt", INT, b="0")
    g.link(gear, "ReturnValue", lt, "A")
    g.link(gear, "ReturnValue", eq, "A")
    b1 = g.branch()
    b2 = g.branch()
    g.link(lt, "ReturnValue", b1, "Condition")
    g.link(eq, "ReturnValue", b2, "Condition")
    r_r = g.function_result([Pin("Gear", "string", default="R")])
    r_n = g.function_result([Pin("Gear", "string", default="N")])
    conv = g.call_static("KismetStringLibrary", "Conv_IntToString", inputs=[Pin("InInt", INT)], outputs=[Pin("ReturnValue", "string", "out")], pure=True)
    g.link(gear, "ReturnValue", conv, "InInt")
    r_num = g.function_result([Pin("Gear", "string")])
    g.link(conv, "ReturnValue", r_num, "Gear")
    g.link_entry("then", b1, "execute")
    g.link(b1, "then", r_r, "execute")
    g.link(b1, "else", b2, "execute")
    g.link(b2, "then", r_n, "execute")
    g.link(b2, "else", r_num, "execute")

    # ---- GetBlownTireCount / GetThrottleScale / IsBelowExitSpeed / CanBeEntered ----
    g = bp.function("GetBlownTireCount", doc="How many tires are blown.", outputs=["Count:int"], pure=True)
    c = g.var_get("BlownTireCount", INT)
    g.link_result(c, "BlownTireCount", "Count")
    g.link_entry("then", "result", "execute")

    g = bp.function("GetThrottleScale", doc="BlownTireSpeedScale to the power of the blown tire count.", outputs=["Scale:float"], pure=True)
    base = g.var_get("BlownTireSpeedScale", FLOAT)
    cnt = g.var_get("BlownTireCount", INT)
    conv = g.call_static(MATH, "Conv_IntToFloat", inputs=[Pin("InInt", INT)], outputs=[Pin("ReturnValue", FLOAT, "out")], pure=True)
    pw = g.call_static(MATH, "MultiplyMultiply_FloatFloat", inputs=[Pin("Base", FLOAT), Pin("Exp", FLOAT)],
                       outputs=[Pin("ReturnValue", FLOAT, "out")], pure=True)
    g.link(cnt, "BlownTireCount", conv, "InInt")
    g.link(base, "BlownTireSpeedScale", pw, "Base")
    g.link(conv, "ReturnValue", pw, "Exp")
    g.link_result(pw, "ReturnValue", "Scale")
    g.link_entry("then", "result", "execute")

    g = bp.function("IsBelowExitSpeed", doc="Slow enough to get out.", outputs=["ReturnValue:bool"], pure=True)
    sp = g.call_self("GetSpeedKPH", outputs=[Pin("KPH", FLOAT, "out")], pure=True)
    mx = g.var_get("ExitMaxSpeedKPH", FLOAT)
    lt = compare(g, "Less_FloatFloat", FLOAT)
    g.link(sp, "KPH", lt, "A")
    g.link(mx, "ExitMaxSpeedKPH", lt, "B")
    g.link_result(lt, "ReturnValue", "ReturnValue")
    g.link_entry("then", "result", "execute")

    g = bp.function("CanBeEntered", doc="No occupant and not wrecked.", outputs=["ReturnValue:bool"], pure=True)
    occ = g.var_get("Occupant", OBJECT, cls_ref(CC))
    valid = is_valid(g)
    g.link(occ, "Occupant", valid, "Object")
    no_occ = not_bool(g)
    g.link(valid, "ReturnValue", no_occ, "A")
    dest = g.var_get("bIsDestroyed", BOOL)
    no_dest = not_bool(g)
    g.link(dest, "bIsDestroyed", no_dest, "A")
    both = and_bool(g)
    g.link(no_occ, "ReturnValue", both, "A")
    g.link(no_dest, "ReturnValue", both, "B")
    g.link_result(both, "ReturnValue", "ReturnValue")
    g.link_entry("then", "result", "execute")

    # ---- FindTireIndexForHit(BoneName, ImpactPoint) -> Index ----
    g = bp.function("FindTireIndexForHit", doc="The tire hit: by wheel bone, else the nearest wheel socket within TireHitRadius; -1 for the body.", inputs=["BoneName:name", "ImpactPoint:struct:" + VECTOR],
                    outputs=["Index:int"], locals=["Best:int=-1", "BestDist:float=0"])
    init = g.local_set("BestDist", FLOAT)
    rad = g.var_get("TireHitRadius", FLOAT)
    g.link(rad, "TireHitRadius", init, "BestDist")
    g.link_entry("then", init, "execute")
    loop1 = g.for_each(tire_elem())
    t1 = tires_get(g)
    g.link(t1, "Tires", loop1, "Array")
    g.link(init, "then", loop1, "Exec")
    br1 = break_tire(g)
    g.link(loop1, "Array Element", br1, TIRE.rsplit(".", 1)[1])
    eqn = compare(g, "EqualEqual_NameName", NAME)
    g.link(br1, member(S_TIRE, "BoneName"), eqn, "A")
    g.link_entry("BoneName", eqn, "B")
    b1 = g.branch()
    g.link(loop1, "LoopBody", b1, "execute")
    g.link(eqn, "ReturnValue", b1, "Condition")
    ret_match = g.function_result([Pin("Index", INT)])
    g.link(b1, "then", ret_match, "execute")
    g.link(loop1, "Array Index", ret_match, "Index")
    # second pass: nearest wheel socket within the radius
    loop2 = g.for_each(tire_elem())
    t2 = tires_get(g)
    g.link(t2, "Tires", loop2, "Array")
    g.link(loop1, "Completed", loop2, "Exec")
    br2 = break_tire(g)
    g.link(loop2, "Array Element", br2, TIRE.rsplit(".", 1)[1])
    m = mesh(g)
    sock = g.call_on(SCENE_COMP, "GetSocketLocation", inputs=[Pin("InSocketName", NAME)],
                     outputs=[struct_pin("ReturnValue", VECTOR, "out")], pure=True)
    g.link(m, "Mesh", sock, "self")
    g.link(br2, member(S_TIRE, "BoneName"), sock, "InSocketName")
    dist = g.call_static(MATH, "Vector_Distance", inputs=[struct_pin("V1", VECTOR), struct_pin("V2", VECTOR)],
                         outputs=[Pin("ReturnValue", FLOAT, "out")], pure=True)
    g.link(sock, "ReturnValue", dist, "V1")
    g.link_entry("ImpactPoint", dist, "V2")
    bd = g.local_get("BestDist", FLOAT)
    lt = compare(g, "Less_FloatFloat", FLOAT)
    g.link(dist, "ReturnValue", lt, "A")
    g.link(bd, "BestDist", lt, "B")
    b2 = g.branch()
    g.link(loop2, "LoopBody", b2, "execute")
    g.link(lt, "ReturnValue", b2, "Condition")
    sd = g.local_set("BestDist", FLOAT)
    g.link(dist, "ReturnValue", sd, "BestDist")
    sb = g.local_set("Best", INT)
    g.link(loop2, "Array Index", sb, "Best")
    g.link(b2, "then", sd, "execute")
    g.exec(sd, sb)
    best = g.local_get("Best", INT)
    g.link_result(best, "Best", "Index")
    g.link_extra(loop2, "Completed", "result", "execute")

    # ---- ApplyTireDamage(Index, Damage) ----
    g = bp.function("ApplyTireDamage", doc="Takes health off one tire; at 0 it is blown and the count and OnTireBlown update.", inputs=["Index:int", "Damage:float"])
    get = g.call_array("KismetArrayLibrary", "Array_Get", tire_elem(), inputs=[Pin("Index", INT)],
                       outputs=[Pin("Item", STRUCT, "out", struct_ref_tire())])
    ta = tires_get(g)
    g.link(ta, "Tires", get, "TargetArray")
    g.link_entry("Index", get, "Index")
    br = break_tire(g)
    g.link(get, "Item", br, TIRE.rsplit(".", 1)[1])
    already = g.branch()
    g.link(br, member(S_TIRE, "bBlown"), already, "Condition")
    g.link_entry("then", already, "execute")
    sub = math2(g, "Subtract_FloatFloat", FLOAT)
    g.link(br, member(S_TIRE, "Health"), sub, "A")
    g.link_entry("Damage", sub, "B")
    clamp = g.call_static(MATH, "FMax", inputs=[Pin("A", FLOAT), Pin("B", FLOAT, default="0.0")],
                          outputs=[Pin("ReturnValue", FLOAT, "out")], pure=True)
    g.link(sub, "ReturnValue", clamp, "A")
    blown = compare(g, "LessEqual_FloatFloat", FLOAT, b="0.0")
    g.link(clamp, "ReturnValue", blown, "A")
    mk = make_tire(g)
    g.link(br, member(S_TIRE, "BoneName"), mk, member(S_TIRE, "BoneName"))
    g.link(clamp, "ReturnValue", mk, member(S_TIRE, "Health"))
    g.link(br, member(S_TIRE, "MaxHealth"), mk, member(S_TIRE, "MaxHealth"))
    g.link(blown, "ReturnValue", mk, member(S_TIRE, "bBlown"))
    setn = g.call_array("KismetArrayLibrary", "Array_Set", tire_elem(),
                        inputs=[Pin("Index", INT), Pin("Item", STRUCT, sub_object=struct_ref_tire()),
                                Pin("bSizeToFit", BOOL, default="false")], pure=False)
    tb = tires_get(g)
    g.link(tb, "Tires", setn, "TargetArray")
    g.link_entry("Index", setn, "Index")
    g.link(mk, TIRE.rsplit(".", 1)[1], setn, "Item")
    g.link(already, "else", setn, "execute")
    bb = g.branch()
    g.link(blown, "ReturnValue", bb, "Condition")
    g.exec(setn, bb)
    cnt = g.var_get("BlownTireCount", INT)
    inc = math2(g, "Add_IntInt", INT, b="1")
    g.link(cnt, "BlownTireCount", inc, "A")
    setc = g.var_set("BlownTireCount", INT)
    g.link(inc, "ReturnValue", setc, "BlownTireCount")
    g.link(bb, "then", setc, "execute")
    fire = g.call_delegate("OnTireBlown", [Pin("TireIndex", INT)])
    g.link_entry("Index", fire, "TireIndex")
    g.exec(setc, fire)

    # ---- BlowNearestTire(Point, Damage): explosion tire blast on the wheel socket nearest the point (spec §5) ----
    g = bp.function("BlowNearestTire", doc="Explosion tire blast on the wheel nearest the point (skipped when wrecked or shielded).", inputs=["Point:struct:" + VECTOR, "Damage:float"], locals=["Best:int=-1", "BestDist:float=1000000000"])
    dead = g.var_get("bIsDestroyed", BOOL)
    shielded = g.call_self("IsShielded", outputs=[Pin("ReturnValue", BOOL, "out")], pure=True)
    skip = or_bool(g)
    g.link(dead, "bIsDestroyed", skip, "A")
    g.link(shielded, "ReturnValue", skip, "B")
    b = g.branch()
    g.link(skip, "ReturnValue", b, "Condition")
    g.link_entry("then", b, "execute")
    loop = g.for_each(tire_elem())
    t0 = tires_get(g)
    g.link(t0, "Tires", loop, "Array")
    g.link(b, "else", loop, "Exec")
    br = break_tire(g)
    g.link(loop, "Array Element", br, TIRE.rsplit(".", 1)[1])
    m = mesh(g)
    sock = g.call_on(SCENE_COMP, "GetSocketLocation", inputs=[Pin("InSocketName", NAME)],
                     outputs=[struct_pin("ReturnValue", VECTOR, "out")], pure=True)
    g.link(m, "Mesh", sock, "self")
    g.link(br, member(S_TIRE, "BoneName"), sock, "InSocketName")
    dist = g.call_static(MATH, "Vector_Distance", inputs=[struct_pin("V1", VECTOR), struct_pin("V2", VECTOR)],
                         outputs=[Pin("ReturnValue", FLOAT, "out")], pure=True)
    g.link(sock, "ReturnValue", dist, "V1")
    g.link_entry("Point", dist, "V2")
    bd = g.local_get("BestDist", FLOAT)
    lt = compare(g, "Less_FloatFloat", FLOAT)
    g.link(dist, "ReturnValue", lt, "A")
    g.link(bd, "BestDist", lt, "B")
    b2 = g.branch()
    g.link(loop, "LoopBody", b2, "execute")
    g.link(lt, "ReturnValue", b2, "Condition")
    sd = g.local_set("BestDist", FLOAT)
    g.link(dist, "ReturnValue", sd, "BestDist")
    sb = g.local_set("Best", INT)
    g.link(loop, "Array Index", sb, "Best")
    g.link(b2, "then", sd, "execute")
    g.exec(sd, sb)
    best = g.local_get("Best", INT)
    ge0 = compare(g, "GreaterEqual_IntInt", INT, b="0")
    g.link(best, "Best", ge0, "A")
    bb = g.branch()
    g.link(ge0, "ReturnValue", bb, "Condition")
    g.link(loop, "Completed", bb, "execute")
    apply = g.call_self("ApplyTireDamage", inputs=[Pin("Index", INT), Pin("Damage", FLOAT)])
    best2 = g.local_get("Best", INT)
    g.link(best2, "Best", apply, "Index")
    g.link_entry("Damage", apply, "Damage")
    g.link(bb, "then", apply, "execute")

    # ---- TakeDamageInternal(Damage, TireIndex, Instigator) ----
    g = bp.function("TakeDamageInternal", doc="Routes damage to a tire or the body (ignored while shielded or wrecked); the body at 0 wrecks the car.", inputs=["Damage:float", "TireIndex:int", "Instigator:object:" + CONTROLLER])
    dead = g.var_get("bIsDestroyed", BOOL)
    bdead = g.branch()
    g.link(dead, "bIsDestroyed", bdead, "Condition")
    g.link_entry("then", bdead, "execute")
    ge0 = compare(g, "GreaterEqual_IntInt", INT, b="0")
    g.link_entry("TireIndex", ge0, "A")
    btire = g.branch()
    g.link(ge0, "ReturnValue", btire, "Condition")
    shielded = g.call_self("IsShielded", outputs=[Pin("ReturnValue", BOOL, "out")], pure=True)
    bsh = g.branch()
    g.link(shielded, "ReturnValue", bsh, "Condition")
    g.link(bdead, "else", bsh, "execute")
    g.link(bsh, "else", btire, "execute")  # shielded: nothing happens (spec §2)
    apply = g.call_self("ApplyTireDamage", inputs=[Pin("Index", INT), Pin("Damage", FLOAT)])
    g.link_entry("TireIndex", apply, "Index")
    g.link_entry("Damage", apply, "Damage")
    g.link(btire, "then", apply, "execute")
    h = g.var_get("Health", FLOAT)
    sub = math2(g, "Subtract_FloatFloat", FLOAT)
    g.link(h, "Health", sub, "A")
    g.link_entry("Damage", sub, "B")
    clamp = g.call_static(MATH, "FMax", inputs=[Pin("A", FLOAT), Pin("B", FLOAT, default="0.0")],
                          outputs=[Pin("ReturnValue", FLOAT, "out")], pure=True)
    g.link(sub, "ReturnValue", clamp, "A")
    seth = g.var_set("Health", FLOAT)
    g.link(clamp, "ReturnValue", seth, "Health")
    g.link(btire, "else", seth, "execute")
    fire = g.call_delegate("OnVehicleDamaged", [Pin("Damage", FLOAT), Pin("TireIndex", INT)])
    g.link_entry("Damage", fire, "Damage")
    g.link_entry("TireIndex", fire, "TireIndex")
    g.exec(apply, fire)
    g.exec(seth, fire)
    h2 = g.var_get("Health", FLOAT)
    le = compare(g, "LessEqual_FloatFloat", FLOAT, b="0.0")
    g.link(h2, "Health", le, "A")
    bdie = g.branch()
    g.link(le, "ReturnValue", bdie, "Condition")
    g.exec(fire, bdie)
    kill = g.call_self("DestroyVehicle", inputs=[obj_pin("Killer", CONTROLLER)])
    g.link_entry("Instigator", kill, "Killer")
    g.link(bdie, "then", kill, "execute")

    # ---- DestroyVehicle(Killer) ----
    g = bp.function("DestroyVehicle", doc="Wrecks the car once: handbrake, hop, smoke, effects-only explosion, OnVehicleDestroyed, the GameMode notified.", inputs=["Killer:object:" + CONTROLLER])
    dead = g.var_get("bIsDestroyed", BOOL)
    b = g.branch()
    g.link(dead, "bIsDestroyed", b, "Condition")
    g.link_entry("then", b, "execute")
    mark = g.var_set("bIsDestroyed", BOOL, default="true")
    g.link(b, "else", mark, "execute")
    hb = set_handbrake(g, "true")
    g.exec(mark, hb)
    # Phase 3 wreck effects (spec §5): hop, smoke, then the effects-only explosion through the GameMode
    m = mesh(g)
    hop = g.call_on(PRIMITIVE, "AddImpulse", inputs=[struct_pin("Impulse", VECTOR), Pin("BoneName", NAME, default="None"),
                                                     Pin("bVelChange", BOOL, default="true")])
    g.link(m, "Mesh", hop, "self")
    hopv = g.call_static(MATH, "MakeVector", inputs=[Pin("X", FLOAT, default="0.0"), Pin("Y", FLOAT, default="0.0"), Pin("Z", FLOAT)],
                         outputs=[struct_pin("ReturnValue", VECTOR, "out")], pure=True)
    hi = g.var_get("WreckHopImpulse", FLOAT)
    g.link(hi, "WreckHopImpulse", hopv, "Z")
    g.link(hopv, "ReturnValue", hop, "Impulse")
    g.exec(hb, hop)
    smoke_fx = g.var_get("WreckSmokeEffect", OBJECT, cls_ref(PARTICLE_SYSTEM))
    m2 = mesh(g)
    smoke = g.call_static(GAMEPLAY, "SpawnEmitterAttached",
                          inputs=[obj_pin("EmitterTemplate", PARTICLE_SYSTEM), obj_pin("AttachToComponent", SCENE_COMP),
                                  Pin("AttachPointName", NAME, default="None"), struct_pin("Location", VECTOR, default="0,0,100"),
                                  struct_pin("Rotation", ROTATOR), struct_pin("Scale", VECTOR, default="1,1,1"),
                                  native_enum_pin("LocationType", "/Script/Engine.EAttachLocation", "KeepRelativeOffset"),
                                  Pin("bAutoDestroy", BOOL, default="false"),
                                  native_enum_pin("PoolingMethod", "/Script/Engine.EPSCPoolMethod", "None"),
                                  Pin("bAutoActivate", BOOL, default="true")],
                          outputs=[obj_pin("ReturnValue", "/Script/Engine.ParticleSystemComponent", "out")])
    g.link(smoke_fx, "WreckSmokeEffect", smoke, "EmitterTemplate")
    g.link(m2, "Mesh", smoke, "AttachToComponent")
    g.exec(hop, smoke)
    fire = g.call_delegate("OnVehicleDestroyed", [obj_pin("Vehicle", VC), obj_pin("Killer", CONTROLLER)])
    me = g.self_node()
    g.link(me, "self", fire, "Vehicle")
    g.link_entry("Killer", fire, "Killer")
    g.exec(smoke, fire)
    gm = get_game_mode(g)
    cast = cast_to(g, BP_GM)
    g.link(gm, "ReturnValue", cast, "Object")
    g.exec(fire, cast)
    loc = self_actor_location(g)
    boom = g.call_on(GMC, "SpawnExplosion", inputs=[struct_pin("Location", VECTOR), Pin("Damage", FLOAT, default="0.0"),
                                                    Pin("Radius", FLOAT, default="0.0"), obj_pin("InstigatedBy", CONTROLLER),
                                                    obj_pin("Causer", ACTOR), Pin("bBlowTires", BOOL, default="false")])
    g.link(cast, as_pin(BP_GM), boom, "self")
    g.link(loc, "ReturnValue", boom, "Location")
    g.link_entry("Killer", boom, "InstigatedBy")
    me3 = g.self_node()
    g.link(me3, "self", boom, "Causer")
    g.link(cast, "then", boom, "execute")
    notify = g.call_on(GMC, "NotifyVehicleDestroyed", inputs=[obj_pin("Victim", VC), obj_pin("Killer", CONTROLLER)])
    g.link(cast, as_pin(BP_GM), notify, "self")
    me2 = g.self_node()
    g.link(me2, "self", notify, "Victim")
    g.link_entry("Killer", notify, "Killer")
    g.exec(boom, notify)

    # ---- TeleportAndStop(NewTransform) ----
    g = bp.function("TeleportAndStop", doc="Moves the car and zeroes its velocity (respawns and tests).", inputs=["NewTransform:struct:" + TRANSFORM])
    m = mesh(g)
    lin = g.call_on(PRIMITIVE, "SetPhysicsLinearVelocity",
                    inputs=[struct_pin("NewVel", VECTOR, default="0,0,0"), Pin("bAddToCurrent", BOOL, default="false"),
                            Pin("BoneName", NAME, default="None")])
    g.link(m, "Mesh", lin, "self")
    g.link_entry("then", lin, "execute")
    m2 = mesh(g)
    ang = g.call_on(PRIMITIVE, "SetPhysicsAngularVelocityInDegrees",
                    inputs=[struct_pin("NewAngVel", VECTOR, default="0,0,0"), Pin("bAddToCurrent", BOOL, default="false"),
                            Pin("BoneName", NAME, default="None")])
    g.link(m2, "Mesh", ang, "self")
    g.exec(lin, ang)
    tp = g.call_self_native(ACTOR, "K2_SetActorTransform",
                            inputs=[struct_pin("NewTransform", TRANSFORM), Pin("bSweep", BOOL, default="false"),
                                    Pin("bTeleport", BOOL, default="true")],
                            outputs=[struct_pin("SweepHitResult", HIT_RESULT, "out"), Pin("ReturnValue", BOOL, "out")])
    g.link_entry("NewTransform", tp, "NewTransform")
    g.exec(ang, tp)
    hb = set_handbrake(g, "false")
    g.exec(tp, hb)

    # ---- CanExit ----
    g = bp.function("CanExit", doc="An occupant, not wrecked, below the exit speed.", outputs=["ReturnValue:bool"], pure=True)
    occ = g.var_get("Occupant", OBJECT, cls_ref(CC))
    valid = is_valid(g)
    g.link(occ, "Occupant", valid, "Object")
    dest = g.var_get("bIsDestroyed", BOOL)
    nd = not_bool(g)
    g.link(dest, "bIsDestroyed", nd, "A")
    slow = g.call_self("IsBelowExitSpeed", outputs=[Pin("ReturnValue", BOOL, "out")], pure=True)
    a1 = and_bool(g)
    a2 = and_bool(g)
    g.link(valid, "ReturnValue", a1, "A")
    g.link(nd, "ReturnValue", a1, "B")
    g.link(a1, "ReturnValue", a2, "A")
    g.link(slow, "ReturnValue", a2, "B")
    g.link_result(a2, "ReturnValue", "ReturnValue")
    g.link_entry("then", "result", "execute")

    # ---- IsExitSpotFree(Location) -> bool : capsule trace at the spot, ignoring self ----
    g = bp.function("IsExitSpotFree", doc="Capsule trace at a spot beside the car.", inputs=["Location:struct:" + VECTOR], outputs=["ReturnValue:bool"])
    tr = g.call_static(SYS, "CapsuleTraceSingle",
                       inputs=[Pin("WorldContextObject", OBJECT, hidden=True), struct_pin("Start", VECTOR),
                               struct_pin("End", VECTOR), Pin("Radius", FLOAT, default="42.0"),
                               Pin("HalfHeight", FLOAT, default="96.0"), Pin("TraceChannel", "byte", default="TraceTypeQuery1"),
                               Pin("bTraceComplex", BOOL, default="false"), Pin("bIgnoreSelf", BOOL, default="true")],
                       outputs=[struct_pin("OutHit", HIT_RESULT, "out"), Pin("ReturnValue", BOOL, "out")])
    g.link_entry("Location", tr, "Start")
    g.link_entry("Location", tr, "End")
    g.link_entry("then", tr, "execute")
    nb = not_bool(g)
    g.link(tr, "ReturnValue", nb, "A")
    g.link_result(nb, "ReturnValue", "ReturnValue")
    g.link_extra(tr, "then", "result", "execute")

    # ---- FindExitLocation -> bFound, Location : left, right, behind ----
    g = bp.function("FindExitLocation", doc="Left door, then right, then behind the car.", outputs=["bFound:bool", "Location:struct:" + VECTOR],
                    locals=["Candidate:struct:" + VECTOR])
    prev_exec = ("entry", "then")
    for axis_fn, offset_var, sign in (("GetActorRightVector", "ExitSideOffset", -1.0),
                                       ("GetActorRightVector", "ExitSideOffset", 1.0),
                                       ("GetActorForwardVector", "ExitBehindOffset", -1.0)):
        loc = g.call_self_native(ACTOR, "K2_GetActorLocation", outputs=[struct_pin("ReturnValue", VECTOR, "out")], pure=True)
        axis = g.call_self_native(ACTOR, axis_fn, outputs=[struct_pin("ReturnValue", VECTOR, "out")], pure=True)
        up = g.call_self_native(ACTOR, "GetActorUpVector", outputs=[struct_pin("ReturnValue", VECTOR, "out")], pure=True)
        off = g.var_get(offset_var, FLOAT)
        upoff = g.var_get("ExitUpOffset", FLOAT)
        sgn = math2(g, "Multiply_FloatFloat", FLOAT, b="%f" % sign)
        g.link(off, offset_var, sgn, "A")
        side = g.call_static(MATH, "Multiply_VectorFloat", inputs=[struct_pin("A", VECTOR), Pin("B", FLOAT)],
                             outputs=[struct_pin("ReturnValue", VECTOR, "out")], pure=True)
        g.link(axis, "ReturnValue", side, "A")
        g.link(sgn, "ReturnValue", side, "B")
        upv = g.call_static(MATH, "Multiply_VectorFloat", inputs=[struct_pin("A", VECTOR), Pin("B", FLOAT)],
                            outputs=[struct_pin("ReturnValue", VECTOR, "out")], pure=True)
        g.link(up, "ReturnValue", upv, "A")
        g.link(upoff, "ExitUpOffset", upv, "B")
        add1 = g.call_static(MATH, "Add_VectorVector", inputs=[struct_pin("A", VECTOR), struct_pin("B", VECTOR)],
                             outputs=[struct_pin("ReturnValue", VECTOR, "out")], pure=True)
        add2 = g.call_static(MATH, "Add_VectorVector", inputs=[struct_pin("A", VECTOR), struct_pin("B", VECTOR)],
                             outputs=[struct_pin("ReturnValue", VECTOR, "out")], pure=True)
        g.link(loc, "ReturnValue", add1, "A")
        g.link(side, "ReturnValue", add1, "B")
        g.link(add1, "ReturnValue", add2, "A")
        g.link(upv, "ReturnValue", add2, "B")
        setc = g.local_set("Candidate", STRUCT, sub_object=cls_ref(VECTOR).replace("Class'", "ScriptStruct'"))
        g.link(add2, "ReturnValue", setc, "Candidate")
        g.link_extra(prev_exec[0], prev_exec[1], setc, "execute")
        free = g.call_self("IsExitSpotFree", inputs=[struct_pin("Location", VECTOR)], outputs=[Pin("ReturnValue", BOOL, "out")])
        g.link(setc, "Output_Get", free, "Location")
        g.exec(setc, free)
        b = g.branch()
        g.link(free, "ReturnValue", b, "Condition")
        g.exec(free, b)
        ret = g.function_result([Pin("bFound", BOOL, default="true"), struct_pin("Location", VECTOR)])
        cand = g.local_get("Candidate", STRUCT, sub_object=cls_ref(VECTOR).replace("Class'", "ScriptStruct'"))
        g.link(cand, "Candidate", ret, "Location")
        g.link(b, "then", ret, "execute")
        prev_exec = (b, "else")
    ret_none = g.function_result([Pin("bFound", BOOL, default="false"), struct_pin("Location", VECTOR)])
    g.link(prev_exec[0], prev_exec[1], ret_none, "execute")

    # ---- EnterVehicle(Character) -> bool ----
    g = bp.function("EnterVehicle", doc="The character gets in: stowed, its controller possesses the car, OnOccupantEntered.", inputs=["Character:" + obj_spec(BP_CHARACTER)], outputs=["ReturnValue:bool"])
    can = g.call_self("CanBeEntered", outputs=[Pin("ReturnValue", BOOL, "out")], pure=True)
    dead = g.call_on(CC, "IsDead", outputs=[Pin("ReturnValue", BOOL, "out")], pure=True)
    g.link_entry("Character", dead, "self")
    nd = not_bool(g)
    g.link(dead, "ReturnValue", nd, "A")
    ok = and_bool(g)
    g.link(can, "ReturnValue", ok, "A")
    g.link(nd, "ReturnValue", ok, "B")
    b = g.branch()
    g.link(ok, "ReturnValue", b, "Condition")
    g.link_entry("then", b, "execute")
    r_false = result_bool(g, "false")
    g.link(b, "else", r_false, "execute")
    seto = g.var_set("Occupant", OBJECT, sub_object=cls_ref(CC))
    g.link_entry("Character", seto, "Occupant")
    g.link(b, "then", seto, "execute")
    setcv = g.var_set_on(CC, "CurrentVehicle", OBJECT, sub_object=cls_ref(VC))
    g.link_entry("Character", setcv, "self")
    me = g.self_node()
    g.link(me, "self", setcv, "CurrentVehicle")
    g.exec(seto, setcv)
    stow = g.call_on(CC, "SetStowed", inputs=[Pin("bStowed", BOOL, default="true"), obj_pin("AttachTo", ACTOR)])
    g.link_entry("Character", stow, "self")
    me2 = g.self_node()
    g.link(me2, "self", stow, "AttachTo")
    g.exec(setcv, stow)
    ctrl = g.call_on(PAWN, "GetController", outputs=[obj_pin("ReturnValue", CONTROLLER, "out")], pure=True)
    g.link_entry("Character", ctrl, "self")
    cv = is_valid(g)
    g.link(ctrl, "ReturnValue", cv, "Object")
    bc = g.branch()
    g.link(cv, "ReturnValue", bc, "Condition")
    g.exec(stow, bc)
    poss = g.call_on(CONTROLLER, "Possess", inputs=[obj_pin("InPawn", PAWN)])
    g.link(ctrl, "ReturnValue", poss, "self")
    me3 = g.self_node()
    g.link(me3, "self", poss, "InPawn")
    g.link(bc, "then", poss, "execute")
    setld = g.var_set("LastDriver", OBJECT, sub_object=cls_ref(CONTROLLER))
    g.link(ctrl, "ReturnValue", setld, "LastDriver")
    g.exec(poss, setld)
    g.link(bc, "else", setld, "execute")
    # UE 4.27 keeps the handbrake input latched from parking; release it for the new driver
    release = set_handbrake(g, "false")
    g.exec(setld, release)
    f1 = g.call_delegate("OnOccupantEntered", [obj_pin("Character", CC)])
    g.link_entry("Character", f1, "Character")
    g.exec(release, f1)
    f2 = g.call_delegate_on(CC, "OnEnteredVehicle", [obj_pin("Vehicle", VC)])
    g.link_entry("Character", f2, "self")
    me4 = g.self_node()
    g.link(me4, "self", f2, "Vehicle")
    g.exec(f1, f2)
    r_true = result_bool(g, "true")
    g.exec(f2, r_true)

    # ---- ExitVehicle -> bool ----
    g = bp.function("ExitVehicle", doc="The driver gets out beside the car and the controller possesses the character.", outputs=["ReturnValue:bool"],
                    locals=["Leaving:" + obj_spec(BP_CHARACTER), "Driver:object:" + CONTROLLER])
    can = g.call_self("CanExit", outputs=[Pin("ReturnValue", BOOL, "out")], pure=True)
    b = g.branch()
    g.link(can, "ReturnValue", b, "Condition")
    g.link_entry("then", b, "execute")
    r_false = result_bool(g, "false")
    g.link(b, "else", r_false, "execute")
    find = g.call_self("FindExitLocation", outputs=[Pin("bFound", BOOL, "out"), struct_pin("Location", VECTOR, "out")])
    g.link(b, "then", find, "execute")
    bf = g.branch()
    g.link(find, "bFound", bf, "Condition")
    g.exec(find, bf)
    r_false2 = result_bool(g, "false")
    g.link(bf, "else", r_false2, "execute")
    hb = set_handbrake(g, "true")
    g.link(bf, "then", hb, "execute")
    th = set_throttle(g, "0.0")
    g.exec(hb, th)
    occ = g.var_get("Occupant", OBJECT, cls_ref(CC))
    setl = g.local_set("Leaving", OBJECT, sub_object=cls_ref(CC))
    g.link(occ, "Occupant", setl, "Leaving")
    g.exec(th, setl)
    ctrl = g.call_self_native(PAWN, "GetController", outputs=[obj_pin("ReturnValue", CONTROLLER, "out")], pure=True)
    setd = g.local_set("Driver", OBJECT, sub_object=cls_ref(CONTROLLER))
    g.link(ctrl, "ReturnValue", setd, "Driver")
    g.exec(setl, setd)
    unstow = g.call_on(CC, "SetStowed", inputs=[Pin("bStowed", BOOL, default="false"), obj_pin("AttachTo", ACTOR)])
    g.link(setl, "Output_Get", unstow, "self")
    g.exec(setd, unstow)
    place = g.call_on(ACTOR, "K2_SetActorLocation",
                      inputs=[struct_pin("NewLocation", VECTOR), Pin("bSweep", BOOL, default="false"), Pin("bTeleport", BOOL, default="true")],
                      outputs=[struct_pin("SweepHitResult", HIT_RESULT, "out"), Pin("ReturnValue", BOOL, "out")])
    lv = g.local_get("Leaving", OBJECT, cls_ref(CC))
    g.link(lv, "Leaving", place, "self")
    g.link(find, "Location", place, "NewLocation")
    g.exec(unstow, place)
    dv = g.local_get("Driver", OBJECT, cls_ref(CONTROLLER))
    valid = is_valid(g)
    g.link(dv, "Driver", valid, "Object")
    bc = g.branch()
    g.link(valid, "ReturnValue", bc, "Condition")
    g.exec(place, bc)
    poss = g.call_on(CONTROLLER, "Possess", inputs=[obj_pin("InPawn", PAWN)])
    dv2 = g.local_get("Driver", OBJECT, cls_ref(CONTROLLER))
    g.link(dv2, "Driver", poss, "self")
    lv2 = g.local_get("Leaving", OBJECT, cls_ref(CC))
    g.link(lv2, "Leaving", poss, "InPawn")
    g.link(bc, "then", poss, "execute")
    setld = g.var_set("LastDriver", OBJECT, sub_object=cls_ref(CONTROLLER))
    dv3 = g.local_get("Driver", OBJECT, cls_ref(CONTROLLER))
    g.link(dv3, "Driver", setld, "LastDriver")
    g.exec(poss, setld)
    g.link(bc, "else", setld, "execute")
    clearcv = g.var_set_on(CC, "CurrentVehicle", OBJECT, sub_object=cls_ref(VC))
    lv3 = g.local_get("Leaving", OBJECT, cls_ref(CC))
    g.link(lv3, "Leaving", clearcv, "self")
    g.exec(setld, clearcv)
    clearo = g.var_set("Occupant", OBJECT, sub_object=cls_ref(CC))
    g.exec(clearcv, clearo)
    f1 = g.call_delegate("OnOccupantExited", [obj_pin("Character", CC)])
    lv4 = g.local_get("Leaving", OBJECT, cls_ref(CC))
    g.link(lv4, "Leaving", f1, "Character")
    g.exec(clearo, f1)
    f2 = g.call_delegate_on(CC, "OnExitedVehicle", [obj_pin("Vehicle", VC)])
    lv5 = g.local_get("Leaving", OBJECT, cls_ref(CC))
    g.link(lv5, "Leaving", f2, "self")
    me = g.self_node()
    g.link(me, "self", f2, "Vehicle")
    g.exec(f1, f2)
    r_true = result_bool(g, "true")
    g.exec(f2, r_true)

    # ---- EjectOccupant: un-stow beside the car without possession changes (used by respawn) ----
    g = bp.function("EjectOccupant", doc="Puts the occupant beside the car without changing possession (respawn).", locals=["Leaving:" + obj_spec(BP_CHARACTER)])
    occ = g.var_get("Occupant", OBJECT, cls_ref(CC))
    valid = is_valid(g)
    g.link(occ, "Occupant", valid, "Object")
    b = g.branch()
    g.link(valid, "ReturnValue", b, "Condition")
    g.link_entry("then", b, "execute")
    setl = g.local_set("Leaving", OBJECT, sub_object=cls_ref(CC))
    g.link(occ, "Occupant", setl, "Leaving")
    g.link(b, "then", setl, "execute")
    unstow = g.call_on(CC, "SetStowed", inputs=[Pin("bStowed", BOOL, default="false"), obj_pin("AttachTo", ACTOR)])
    g.link(setl, "Output_Get", unstow, "self")
    g.exec(setl, unstow)
    find = g.call_self("FindExitLocation", outputs=[Pin("bFound", BOOL, "out"), struct_pin("Location", VECTOR, "out")])
    g.exec(unstow, find)
    loc = g.call_self_native(ACTOR, "K2_GetActorLocation", outputs=[struct_pin("ReturnValue", VECTOR, "out")], pure=True)
    above = g.call_static(MATH, "Add_VectorVector", inputs=[struct_pin("A", VECTOR), struct_pin("B", VECTOR, default="0,0,200")],
                          outputs=[struct_pin("ReturnValue", VECTOR, "out")], pure=True)
    g.link(loc, "ReturnValue", above, "A")
    pick = g.call_static(MATH, "SelectVector", inputs=[struct_pin("A", VECTOR), struct_pin("B", VECTOR), Pin("bPickA", BOOL)],
                         outputs=[struct_pin("ReturnValue", VECTOR, "out")], pure=True)
    g.link(find, "Location", pick, "A")
    g.link(above, "ReturnValue", pick, "B")
    g.link(find, "bFound", pick, "bPickA")
    place = g.call_on(ACTOR, "K2_SetActorLocation",
                      inputs=[struct_pin("NewLocation", VECTOR), Pin("bSweep", BOOL, default="false"), Pin("bTeleport", BOOL, default="true")],
                      outputs=[struct_pin("SweepHitResult", HIT_RESULT, "out"), Pin("ReturnValue", BOOL, "out")])
    lv = g.local_get("Leaving", OBJECT, cls_ref(CC))
    g.link(lv, "Leaving", place, "self")
    g.link(pick, "ReturnValue", place, "NewLocation")
    g.exec(find, place)
    clearcv = g.var_set_on(CC, "CurrentVehicle", OBJECT, sub_object=cls_ref(VC))
    lv2 = g.local_get("Leaving", OBJECT, cls_ref(CC))
    g.link(lv2, "Leaving", clearcv, "self")
    g.exec(place, clearcv)
    clearo = g.var_set("Occupant", OBJECT, sub_object=cls_ref(CC))
    g.exec(clearcv, clearo)

    # ---- TickDriveOverrides(DeltaSeconds): parked/wrecked cars brake; blown tires cap the throttle ----
    g = bp.function("TickDriveOverrides", doc="Per-frame input: parked or wrecked cars brake; blown tires cap the throttle.", inputs=["DeltaSeconds:float"])
    dead = g.var_get("bIsDestroyed", BOOL)
    ctrl = g.call_self_native(PAWN, "GetController", outputs=[obj_pin("ReturnValue", CONTROLLER, "out")], pure=True)
    valid = is_valid(g)
    g.link(ctrl, "ReturnValue", valid, "Object")
    nv = not_bool(g)
    g.link(valid, "ReturnValue", nv, "A")
    park = g.call_static(MATH, "BooleanOR", inputs=[Pin("A", BOOL), Pin("B", BOOL)], outputs=[Pin("ReturnValue", BOOL, "out")], pure=True)
    g.link(dead, "bIsDestroyed", park, "A")
    g.link(nv, "ReturnValue", park, "B")
    b = g.branch()
    g.link(park, "ReturnValue", b, "Condition")
    g.link_entry("then", b, "execute")
    t0 = set_throttle(g, "0.0")
    s0 = set_steering(g, "0.0")
    hb = set_handbrake(g, "true")
    g.link(b, "then", t0, "execute")
    g.exec(t0, s0, hb)
    # Phase 4: an AI controller feeds its own throttle, steering and handbrake (spec §2.1)
    ai = g.var_get("bAIControlled", BOOL)
    bai = g.branch()
    g.note(bai, "driven by an AI controller?")
    g.link(ai, "bAIControlled", bai, "Condition")
    g.link(b, "else", bai, "execute")
    at = g.var_get("AIThrottle", FLOAT)
    scale_ai = g.call_self("GetThrottleScale", outputs=[Pin("Scale", FLOAT, "out")], pure=True)
    mul_ai = math2(g, "Multiply_FloatFloat", FLOAT)
    g.link(at, "AIThrottle", mul_ai, "A")
    g.link(scale_ai, "Scale", mul_ai, "B")
    th_ai = set_throttle(g)
    g.link(drive_throttle(g, (mul_ai, "ReturnValue")), "Throttle", th_ai, "Throttle")
    g.link(bai, "then", th_ai, "execute")
    ast = g.var_get("AISteering", FLOAT)
    st_ai = set_steering(g)
    g.link(ast, "AISteering", st_ai, "Steering")
    ahb = g.var_get("bAIHandbrake", BOOL)
    hb_ai = mv_call(g, "SetHandbrakeInput", inputs=[Pin("bNewHandbrake", BOOL)])
    g.link(ahb, "bAIHandbrake", hb_ai, "bNewHandbrake")
    g.exec(th_ai, st_ai, hb_ai)
    axis = g.input_axis_value("MoveForward")
    scale = g.call_self("GetThrottleScale", outputs=[Pin("Scale", FLOAT, "out")], pure=True)
    mul = math2(g, "Multiply_FloatFloat", FLOAT)
    g.link(axis, "ReturnValue", mul, "A")
    g.link(scale, "Scale", mul, "B")
    th = set_throttle(g)
    g.link(drive_throttle(g, (mul, "ReturnValue")), "Throttle", th, "Throttle")
    g.link(bai, "else", th, "execute")

    # ComputeDriveThrottle(Input, SpeedKPH) -> Throttle (Phase 5 spec §3.2): the car's throttle scale, and a speed limiter
    # that cuts positive throttle at TopSpeedKPH (0 = none); braking and reverse are only scaled, never cut
    g = bp.function("ComputeDriveThrottle", doc="Input x ThrottleScale; 0 when accelerating at or above TopSpeedKPH (0 = no limiter).",
                    inputs=["Input:float", "SpeedKPH:float"], outputs=["Throttle:float"], pure=True)
    scaled = math2(g, "Multiply_FloatFloat", FLOAT)
    g.link_entry("Input", scaled, "A")
    g.link(g.var_get("ThrottleScale", FLOAT), "ThrottleScale", scaled, "B")
    accelerating = compare(g, "Greater_FloatFloat", FLOAT, b="0.0")
    g.link_entry("Input", accelerating, "A")
    has_limit = compare(g, "Greater_FloatFloat", FLOAT, b="0.0")
    g.link(g.var_get("TopSpeedKPH", FLOAT), "TopSpeedKPH", has_limit, "A")
    at_limit = compare(g, "GreaterEqual_FloatFloat", FLOAT)
    g.link_entry("SpeedKPH", at_limit, "A")
    g.link(g.var_get("TopSpeedKPH", FLOAT), "TopSpeedKPH", at_limit, "B")
    both = and_bool(g)
    g.link(has_limit, "ReturnValue", both, "A")
    g.link(at_limit, "ReturnValue", both, "B")
    limited = and_bool(g)
    g.link(accelerating, "ReturnValue", limited, "A")
    g.link(both, "ReturnValue", limited, "B")
    pick = g.call_static(MATH, "SelectFloat", inputs=[Pin("A", FLOAT, default="0.0"), Pin("B", FLOAT), Pin("bPickA", BOOL)],
                         outputs=[Pin("ReturnValue", FLOAT, "out")], pure=True)
    g.link(scaled, "ReturnValue", pick, "B")
    g.link(limited, "ReturnValue", pick, "bPickA")
    g.link_result(pick, "ReturnValue", "Throttle")
    g.link_entry("then", "result", "execute")

    # SetAIInput(Throttle, Steering, bHandbrake): what TickDriveOverrides applies while bAIControlled
    g = bp.function("SetAIInput", inputs=["Throttle:float", "Steering:float", "bHandbrake:bool"],
                    doc="The AI controller's inputs; TickDriveOverrides applies them every frame while bAIControlled.")
    s1 = g.var_set("AIThrottle", FLOAT)
    g.link_entry("Throttle", s1, "AIThrottle")
    g.link_entry("then", s1, "execute")
    s2 = g.var_set("AISteering", FLOAT)
    g.link_entry("Steering", s2, "AISteering")
    s3 = g.var_set("bAIHandbrake", BOOL)
    g.link_entry("bHandbrake", s3, "bAIHandbrake")
    g.exec(s1, s2, s3)

    # ---- Phase 3: effects and item use (spec 2026-10-30 §2) ----
    g = bp.function("IsShielded", doc="A shield is running.", outputs=["ReturnValue:bool"], pure=True)
    sr = g.var_get("ShieldRemaining", FLOAT)
    gt = compare(g, "Greater_FloatFloat", FLOAT, b="0.0")
    g.link(sr, "ShieldRemaining", gt, "A")
    g.link_result(gt, "ReturnValue", "ReturnValue")
    g.link_entry("then", "result", "execute")

    # ActivateBoost: timer + an instant forward kick
    g = bp.function("ActivateBoost", doc="Starts the boost timer and kicks the car forward.")
    dur = g.var_get("BoostDuration", FLOAT)
    sb = g.var_set("BoostRemaining", FLOAT)
    g.link(dur, "BoostDuration", sb, "BoostRemaining")
    g.link_entry("then", sb, "execute")
    fwd = g.call_self_native(ACTOR, "GetActorForwardVector", outputs=[struct_pin("ReturnValue", VECTOR, "out")], pure=True)
    ks = g.var_get("BoostKickSpeed", FLOAT)
    kick = g.call_static(MATH, "Multiply_VectorFloat", inputs=[struct_pin("A", VECTOR), Pin("B", FLOAT)],
                         outputs=[struct_pin("ReturnValue", VECTOR, "out")], pure=True)
    g.link(fwd, "ReturnValue", kick, "A")
    g.link(ks, "BoostKickSpeed", kick, "B")
    m = mesh(g)
    vel = g.call_on(PRIMITIVE, "SetPhysicsLinearVelocity",
                    inputs=[struct_pin("NewVel", VECTOR), Pin("bAddToCurrent", BOOL, default="true"), Pin("BoneName", NAME, default="None")])
    g.link(m, "Mesh", vel, "self")
    g.link(kick, "ReturnValue", vel, "NewVel")
    g.exec(sb, vel)

    g = bp.function("ActivateShield", doc="Starts the shield timer.")
    dur = g.var_get("ShieldDuration", FLOAT)
    ss = g.var_set("ShieldRemaining", FLOAT)
    g.link(dur, "ShieldDuration", ss, "ShieldRemaining")
    g.link_entry("then", ss, "execute")

    g = bp.function("ClearEffects", doc="Ends boost and shield.")
    cb = g.var_set("BoostRemaining", FLOAT, default="0.0")
    cs = g.var_set("ShieldRemaining", FLOAT, default="0.0")
    g.link_entry("then", cb, "execute")
    g.exec(cb, cs)

    # TickEffects(DeltaSeconds): sustained boost force; both timers run down to 0
    g = bp.function("TickEffects", doc="Per-frame boost force; both effect timers run down.", inputs=["DeltaSeconds:float"])
    br_ = g.var_get("BoostRemaining", FLOAT)
    on = compare(g, "Greater_FloatFloat", FLOAT, b="0.0")
    g.link(br_, "BoostRemaining", on, "A")
    b = g.branch()
    g.link(on, "ReturnValue", b, "Condition")
    g.link_entry("then", b, "execute")
    fwd = g.call_self_native(ACTOR, "GetActorForwardVector", outputs=[struct_pin("ReturnValue", VECTOR, "out")], pure=True)
    acc = g.var_get("BoostAcceleration", FLOAT)
    force = g.call_static(MATH, "Multiply_VectorFloat", inputs=[struct_pin("A", VECTOR), Pin("B", FLOAT)],
                          outputs=[struct_pin("ReturnValue", VECTOR, "out")], pure=True)
    g.link(fwd, "ReturnValue", force, "A")
    g.link(acc, "BoostAcceleration", force, "B")
    m = mesh(g)
    af = g.call_on(PRIMITIVE, "AddForce", inputs=[struct_pin("Force", VECTOR), Pin("BoneName", NAME, default="None"),
                                                  Pin("bAccelChange", BOOL, default="true")])
    g.link(m, "Mesh", af, "self")
    g.link(force, "ReturnValue", af, "Force")
    g.link(b, "then", af, "execute")
    for var, prev_out in (("BoostRemaining", None), ("ShieldRemaining", None)):
        cur = g.var_get(var, FLOAT)
        sub = math2(g, "Subtract_FloatFloat", FLOAT)
        g.link(cur, var, sub, "A")
        g.link_entry("DeltaSeconds", sub, "B")
        mx = g.call_static(MATH, "FMax", inputs=[Pin("A", FLOAT), Pin("B", FLOAT, default="0.0")],
                           outputs=[Pin("ReturnValue", FLOAT, "out")], pure=True)
        g.link(sub, "ReturnValue", mx, "A")
        setv = g.var_set(var, FLOAT)
        g.link(mx, "ReturnValue", setv, var)
        if var == "BoostRemaining":
            g.exec(af, setv)
            g.link(b, "else", setv, "execute")
            first = setv
        else:
            g.exec(first, setv)

    # CanUseItem(Type): the gun waits for its cooldown (no charge wasted on a dry press); every other item is always usable
    WC = gen(BPC_WEAPON)
    g = bp.function("CanUseItem", doc="The gun waits for its cooldown; every other item is always usable.", inputs=["Type:" + enum_spec(E_ITEM_TYPE)], outputs=["ReturnValue:bool"], pure=True)
    b = g.branch()
    g.link(enum_is(g, ("entry", "Type"), ITEM_GUN), "ReturnValue", b, "Condition")
    g.link_entry("then", b, "execute")
    wp = g.var_get("Weapon", OBJECT, cls_ref(WC))
    can = g.call_on(WC, "CanFire", outputs=[Pin("ReturnValue", BOOL, "out")], pure=True)
    g.link(wp, "Weapon", can, "self")
    r_gun = g.function_result([Pin("ReturnValue", BOOL)])
    g.link(can, "ReturnValue", r_gun, "ReturnValue")
    g.link(b, "then", r_gun, "execute")
    g.link(b, "else", result_bool(g, "true"), "execute")

    # GetMuzzleLocation(): in front of the bumper, above the hood
    g = bp.function("GetMuzzleLocation", doc="In front of the bumper, above the hood.", outputs=["Location:struct:" + VECTOR], pure=True)
    loc = self_actor_location(g)
    fwd = g.call_self_native(ACTOR, "GetActorForwardVector", outputs=[struct_pin("ReturnValue", VECTOR, "out")], pure=True)
    up = g.call_self_native(ACTOR, "GetActorUpVector", outputs=[struct_pin("ReturnValue", VECTOR, "out")], pure=True)
    mf, mu = g.var_get("MuzzleForward", FLOAT), g.var_get("MuzzleUp", FLOAT)
    f = g.call_static(MATH, "Multiply_VectorFloat", inputs=[struct_pin("A", VECTOR), Pin("B", FLOAT)], outputs=[struct_pin("ReturnValue", VECTOR, "out")], pure=True)
    g.link(fwd, "ReturnValue", f, "A")
    g.link(mf, "MuzzleForward", f, "B")
    u = g.call_static(MATH, "Multiply_VectorFloat", inputs=[struct_pin("A", VECTOR), Pin("B", FLOAT)], outputs=[struct_pin("ReturnValue", VECTOR, "out")], pure=True)
    g.link(up, "ReturnValue", u, "A")
    g.link(mu, "MuzzleUp", u, "B")
    a1 = g.call_static(MATH, "Add_VectorVector", inputs=[struct_pin("A", VECTOR), struct_pin("B", VECTOR)], outputs=[struct_pin("ReturnValue", VECTOR, "out")], pure=True)
    g.link(loc, "ReturnValue", a1, "A")
    g.link(f, "ReturnValue", a1, "B")
    a2 = g.call_static(MATH, "Add_VectorVector", inputs=[struct_pin("A", VECTOR), struct_pin("B", VECTOR)], outputs=[struct_pin("ReturnValue", VECTOR, "out")], pure=True)
    g.link(a1, "ReturnValue", a2, "A")
    g.link(u, "ReturnValue", a2, "B")
    g.link_result(a2, "ReturnValue", "Location")
    g.link_entry("then", "result", "execute")

    # GetAimDirection(): straight ahead, or at an AI's AimTarget (its centre, 60 cm up) for one shot
    g = bp.function("GetAimDirection", outputs=["Direction:struct:" + VECTOR], pure=True,
                    doc="Where a shot goes: at AimTarget's centre (60 cm up) when an AI set one, else straight ahead.")
    at = g.var_get("AimTarget", OBJECT, cls_ref(ACTOR))
    av = is_valid(g)
    g.link(at, "AimTarget", av, "Object")
    b = g.branch()
    g.link(av, "ReturnValue", b, "Condition")
    g.link_entry("then", b, "execute")
    tloc = g.call_on(ACTOR, "K2_GetActorLocation", outputs=[struct_pin("ReturnValue", VECTOR, "out")], pure=True)
    g.link(at, "AimTarget", tloc, "self")
    raised = g.call_static(MATH, "Add_VectorVector", inputs=[struct_pin("A", VECTOR), struct_pin("B", VECTOR, default="0,0,60")],
                           outputs=[struct_pin("ReturnValue", VECTOR, "out")], pure=True)
    g.link(tloc, "ReturnValue", raised, "A")
    mz = g.call_self("GetMuzzleLocation", outputs=[struct_pin("Location", VECTOR, "out")], pure=True)
    diff = g.call_static(MATH, "Subtract_VectorVector", inputs=[struct_pin("A", VECTOR), struct_pin("B", VECTOR)],
                         outputs=[struct_pin("ReturnValue", VECTOR, "out")], pure=True)
    g.link(raised, "ReturnValue", diff, "A")
    g.link(mz, "Location", diff, "B")
    unit = g.call_static(MATH, "Normal", inputs=[struct_pin("A", VECTOR), Pin("Tolerance", FLOAT, default="0.0001")],
                         outputs=[struct_pin("ReturnValue", VECTOR, "out")], pure=True)
    g.link(diff, "ReturnValue", unit, "A")
    r_aim = g.function_result([struct_pin("Direction", VECTOR)])
    g.link(unit, "ReturnValue", r_aim, "Direction")
    g.link(b, "then", r_aim, "execute")
    fwd0 = g.call_self_native(ACTOR, "GetActorForwardVector", outputs=[struct_pin("ReturnValue", VECTOR, "out")], pure=True)
    r_fwd = g.function_result([struct_pin("Direction", VECTOR)])
    g.link(fwd0, "ReturnValue", r_fwd, "Direction")
    g.link(b, "else", r_fwd, "execute")

    # FireGun() -> bool: one hitscan shot from the muzzle along the aim direction, credited to the driver
    g = bp.function("FireGun", doc="One hitscan shot from the muzzle along the aim direction, credited to the driver.", outputs=["ReturnValue:bool"])
    muzzle = g.call_self("GetMuzzleLocation", outputs=[struct_pin("Location", VECTOR, "out")], pure=True)
    fwd = g.call_self("GetAimDirection", outputs=[struct_pin("Direction", VECTOR, "out")], pure=True)
    ctrl = g.call_self_native(PAWN, "GetController", outputs=[obj_pin("ReturnValue", CONTROLLER, "out")], pure=True)
    wp = g.var_get("Weapon", OBJECT, cls_ref(WC))
    shot = g.call_on(WC, "Fire", inputs=[struct_pin("Origin", VECTOR), struct_pin("Direction", VECTOR), obj_pin("Instigator", CONTROLLER)],
                     outputs=[Pin("bHit", BOOL, "out"), struct_pin("Hit", HIT_RESULT, "out")])
    g.link(wp, "Weapon", shot, "self")
    g.link(muzzle, "Location", shot, "Origin")
    g.link(fwd, "Direction", shot, "Direction")
    g.link(ctrl, "ReturnValue", shot, "Instigator")
    g.link_entry("then", shot, "execute")
    r = g.function_result([Pin("ReturnValue", BOOL)])
    g.link(shot, "bHit", r, "ReturnValue")
    g.exec(shot, r)

    # FireRPG() -> Projectile: a BP_DFProjectile from the muzzle, owned by the car, credited to the driver
    PROJC = gen(BP_PROJECTILE)
    g = bp.function("FireRPG", doc="Launches a rocket from the muzzle (short of anything blocking it), credited to the driver.", outputs=["Projectile:" + obj_spec(BP_PROJECTILE)])
    muzzle = g.call_self("GetMuzzleLocation", outputs=[struct_pin("Location", VECTOR, "out")], pure=True)
    # point-blank: when something blocks the way from the car's centre to the muzzle, the rocket starts 25 cm short of it
    # (spawning inside a rock or a car would push the rocket through without a hit)
    loc = self_actor_location(g)
    up = g.call_self_native(ACTOR, "GetActorUpVector", outputs=[struct_pin("ReturnValue", VECTOR, "out")], pure=True)
    mu = g.var_get("MuzzleUp", FLOAT)
    upv = g.call_static(MATH, "Multiply_VectorFloat", inputs=[struct_pin("A", VECTOR), Pin("B", FLOAT)], outputs=[struct_pin("ReturnValue", VECTOR, "out")], pure=True)
    g.link(up, "ReturnValue", upv, "A")
    g.link(mu, "MuzzleUp", upv, "B")
    start = g.call_static(MATH, "Add_VectorVector", inputs=[struct_pin("A", VECTOR), struct_pin("B", VECTOR)], outputs=[struct_pin("ReturnValue", VECTOR, "out")], pure=True)
    g.link(loc, "ReturnValue", start, "A")
    g.link(upv, "ReturnValue", start, "B")
    tr = g.call_static(SYS, "LineTraceSingle",
                       inputs=[Pin("WorldContextObject", OBJECT, hidden=True), struct_pin("Start", VECTOR), struct_pin("End", VECTOR),
                               Pin("TraceChannel", "byte", default="TraceTypeQuery1"), Pin("bTraceComplex", BOOL, default="false"),
                               Pin("DrawDebugType", "byte", default="None"), Pin("bIgnoreSelf", BOOL, default="true")],
                       outputs=[struct_pin("OutHit", HIT_RESULT, "out"), Pin("ReturnValue", BOOL, "out")])
    g.link(start, "ReturnValue", tr, "Start")
    g.link(muzzle, "Location", tr, "End")
    g.link_entry("then", tr, "execute")
    brk = g.call_static(GAMEPLAY, "BreakHitResult", inputs=[struct_pin("Hit", HIT_RESULT)],
                        outputs=[struct_pin("ImpactPoint", VECTOR, "out")], pure=True)
    g.link(tr, "OutHit", brk, "Hit")
    fwd = g.call_self_native(ACTOR, "GetActorForwardVector", outputs=[struct_pin("ReturnValue", VECTOR, "out")], pure=True)
    back = g.call_static(MATH, "Multiply_VectorFloat", inputs=[struct_pin("A", VECTOR), Pin("B", FLOAT, default="-25.0")], outputs=[struct_pin("ReturnValue", VECTOR, "out")], pure=True)
    g.link(fwd, "ReturnValue", back, "A")
    short = g.call_static(MATH, "Add_VectorVector", inputs=[struct_pin("A", VECTOR), struct_pin("B", VECTOR)], outputs=[struct_pin("ReturnValue", VECTOR, "out")], pure=True)
    g.link(brk, "ImpactPoint", short, "A")
    g.link(back, "ReturnValue", short, "B")
    at = g.call_static(MATH, "SelectVector", inputs=[struct_pin("A", VECTOR), struct_pin("B", VECTOR), Pin("bPickA", BOOL)],
                       outputs=[struct_pin("ReturnValue", VECTOR, "out")], pure=True)
    g.link(short, "ReturnValue", at, "A")
    g.link(muzzle, "Location", at, "B")
    g.link(tr, "ReturnValue", at, "bPickA")
    aim = g.call_self("GetAimDirection", outputs=[struct_pin("Direction", VECTOR, "out")], pure=True)
    rot = g.call_static(MATH, "MakeRotFromX", inputs=[struct_pin("X", VECTOR)], outputs=[struct_pin("ReturnValue", ROTATOR, "out")], pure=True)
    g.link(aim, "Direction", rot, "X")
    xf = g.call_static(MATH, "MakeTransform", inputs=[struct_pin("Location", VECTOR), struct_pin("Rotation", ROTATOR),
                                                        struct_pin("Scale", VECTOR, default="1,1,1")],
                       outputs=[struct_pin("ReturnValue", TRANSFORM, "out")], pure=True)
    g.link(at, "ReturnValue", xf, "Location")
    g.link(rot, "ReturnValue", xf, "Rotation")
    sp = g.spawn_actor(PROJC)
    g.link(xf, "ReturnValue", sp, "SpawnTransform")
    me = g.self_node()
    g.link(me, "self", sp, "Owner")
    g.exec(tr, sp)
    launched = log_line(g, "rocket fired at ", vec_str(g, (at, "ReturnValue")), " (muzzle blocked: ", bool_str(g, (tr, "ReturnValue")), ")")
    g.exec(sp, launched)
    ctrl = g.call_self_native(PAWN, "GetController", outputs=[obj_pin("ReturnValue", CONTROLLER, "out")], pure=True)
    sic = g.var_set_on(PROJC, "InstigatorController", OBJECT, sub_object=cls_ref(CONTROLLER))
    g.link(sp, "ReturnValue", sic, "self")
    g.link(ctrl, "ReturnValue", sic, "InstigatorController")
    g.exec(launched, sic)
    r = g.function_result([obj_pin("Projectile", PROJC)])
    g.link(sp, "ReturnValue", r, "Projectile")
    g.exec(sic, r)

    # ApplyItem(Type): the item's effect on this car
    g = bp.function("ApplyItem", doc="Runs an item's effect on this car.", inputs=["Type:" + enum_spec(E_ITEM_TYPE)])
    prev = ("entry", "then")
    for idx, fn_name in ((ITEM_BOOST, "ActivateBoost"), (ITEM_SHIELD, "ActivateShield"), (ITEM_BOMB, "DropBomb"),
                         (ITEM_GUN, "FireGun"), (ITEM_RPG, "FireRPG")):
        b = g.branch()
        g.link(enum_is(g, ("entry", "Type"), idx), "ReturnValue", b, "Condition")
        g.link(prev[0], prev[1], b, "execute")
        n = g.call_self(fn_name)
        g.link(b, "then", n, "execute")
        prev = (b, "else")

    # DropBomb() -> Bomb: a BP_DFBomb BombDropOffset behind the car, owned by it, credited to its controller (spec §2, §6)
    BOMBC = gen(BP_BOMB)
    g = bp.function("DropBomb", doc="Drops a bomb behind the car, credited to the driver.", outputs=["Bomb:" + obj_spec(BP_BOMB)])
    loc = self_actor_location(g)
    fwd = g.call_self_native(ACTOR, "GetActorForwardVector", outputs=[struct_pin("ReturnValue", VECTOR, "out")], pure=True)
    off = g.var_get("BombDropOffset", FLOAT)
    neg = math2(g, "Multiply_FloatFloat", FLOAT, b="-1.0")
    g.link(off, "BombDropOffset", neg, "A")
    back = g.call_static(MATH, "Multiply_VectorFloat", inputs=[struct_pin("A", VECTOR), Pin("B", FLOAT)],
                         outputs=[struct_pin("ReturnValue", VECTOR, "out")], pure=True)
    g.link(fwd, "ReturnValue", back, "A")
    g.link(neg, "ReturnValue", back, "B")
    at = g.call_static(MATH, "Add_VectorVector", inputs=[struct_pin("A", VECTOR), struct_pin("B", VECTOR)],
                       outputs=[struct_pin("ReturnValue", VECTOR, "out")], pure=True)
    g.link(loc, "ReturnValue", at, "A")
    g.link(back, "ReturnValue", at, "B")
    lift = g.call_static(MATH, "Add_VectorVector", inputs=[struct_pin("A", VECTOR), struct_pin("B", VECTOR, default="0,0,30")],
                         outputs=[struct_pin("ReturnValue", VECTOR, "out")], pure=True)
    g.link(at, "ReturnValue", lift, "A")
    rot = g.call_self_native(ACTOR, "K2_GetActorRotation", outputs=[struct_pin("ReturnValue", ROTATOR, "out")], pure=True)
    # the spawn transform's scale becomes the root (Shell) scale, overriding the template's 0.5
    xf = g.call_static(MATH, "MakeTransform", inputs=[struct_pin("Location", VECTOR), struct_pin("Rotation", ROTATOR),
                                                        struct_pin("Scale", VECTOR, default="0.5,0.5,0.5")],
                       outputs=[struct_pin("ReturnValue", TRANSFORM, "out")], pure=True)
    g.link(lift, "ReturnValue", xf, "Location")
    g.link(rot, "ReturnValue", xf, "Rotation")
    sp = g.spawn_actor(BOMBC)
    g.link(xf, "ReturnValue", sp, "SpawnTransform")
    me = g.self_node()
    g.link(me, "self", sp, "Owner")
    g.link_entry("then", sp, "execute")
    ctrl = g.call_self_native(PAWN, "GetController", outputs=[obj_pin("ReturnValue", CONTROLLER, "out")], pure=True)
    sic = g.var_set_on(BOMBC, "InstigatorController", OBJECT, sub_object=cls_ref(CONTROLLER))
    g.link(sp, "ReturnValue", sic, "self")
    g.link(ctrl, "ReturnValue", sic, "InstigatorController")
    g.exec(sp, sic)
    r = g.function_result([obj_pin("Bomb", BOMBC)])
    g.link(sp, "ReturnValue", r, "Bomb")
    g.exec(sic, r)

    # UseSelectedItem() -> bool: wrecked / no controller / no racer / nothing selected / cannot use -> false; else consume + apply
    g = bp.function("UseSelectedItem", doc="Consumes and applies the driver's selected item; refused when wrecked, empty or on cooldown.", outputs=["ReturnValue:bool"], locals=["Racer:object:" + gen(BPC_RACER)])
    RC_ = gen(BPC_RACER)
    dead = g.var_get("bIsDestroyed", BOOL)
    b0 = g.branch()
    g.link(dead, "bIsDestroyed", b0, "Condition")
    g.link_entry("then", b0, "execute")
    g.link(b0, "then", result_bool(g, "false"), "execute")
    ctrl = g.call_self_native(PAWN, "GetController", outputs=[obj_pin("ReturnValue", CONTROLLER, "out")], pure=True)
    gm = get_game_mode(g)
    cast = cast_to(g, BP_GM)
    g.link(gm, "ReturnValue", cast, "Object")
    g.link(b0, "else", cast, "execute")
    g.link(cast, "CastFailed", result_bool(g, "false"), "execute")
    racer = g.call_on(GMC, "FindRacer", inputs=[obj_pin("C", CONTROLLER)], outputs=[obj_pin("Racer", RC_, "out")], pure=True)
    g.link(cast, as_pin(BP_GM), racer, "self")
    g.link(ctrl, "ReturnValue", racer, "C")
    sl = g.local_set("Racer", OBJECT, sub_object=cls_ref(RC_))
    g.link(racer, "Racer", sl, "Racer")
    g.link(cast, "then", sl, "execute")
    rv = is_valid(g)
    g.link(sl, "Output_Get", rv, "Object")
    bv = g.branch()
    g.link(rv, "ReturnValue", bv, "Condition")
    g.exec(sl, bv)
    g.link(bv, "else", result_bool(g, "false"), "execute")
    lr = lambda: (g.local_get("Racer", OBJECT, cls_ref(RC_)), "Racer")
    sel = g.call_on(RC_, "GetSelected", outputs=[enum_pin("Type", E_ITEM_TYPE, "out"), Pin("Charges", INT, "out")], pure=True)
    r0 = lr()
    g.link(r0[0], r0[1], sel, "self")
    bn = g.branch()
    g.link(enum_is(g, (sel, "Type"), ITEM_NONE), "ReturnValue", bn, "Condition")
    g.link(bv, "then", bn, "execute")
    g.link(bn, "then", result_bool(g, "false"), "execute")
    can = g.call_self("CanUseItem", inputs=[enum_pin("Type", E_ITEM_TYPE)], outputs=[Pin("ReturnValue", BOOL, "out")], pure=True)
    g.link(sel, "Type", can, "Type")
    bc = g.branch()
    g.link(can, "ReturnValue", bc, "Condition")
    g.link(bn, "else", bc, "execute")
    g.link(bc, "else", result_bool(g, "false"), "execute")
    cons = g.call_on(RC_, "ConsumeSelected", outputs=[enum_pin("Type", E_ITEM_TYPE, "out")])
    r1 = lr()
    g.link(r1[0], r1[1], cons, "self")
    g.link(bc, "then", cons, "execute")
    ap = g.call_self("ApplyItem", inputs=[enum_pin("Type", E_ITEM_TYPE)])
    g.link(cons, "Type", ap, "Type")
    g.exec(cons, ap)
    info = g.call_on(GMC, "GetItemInfo", inputs=[enum_pin("Type", E_ITEM_TYPE)],
                     outputs=[Pin("Name", STRING, "out"), Pin("BoxCharges", INT, "out"), Pin("MaxCharges", INT, "out")], pure=True)
    g.link(cast, as_pin(BP_GM), info, "self")
    g.link(cons, "Type", info, "Type")
    log = log_line(g, "used ", (info, "Name"), " by ", name_of(g, (ctrl, "ReturnValue")))
    g.exec(ap, log)
    g.exec(log, result_bool(g, "true"))

    # CycleItem(): next slot of the driver's inventory
    g = bp.function("CycleItem", doc="Selects the driver's next inventory slot.")
    ctrl = g.call_self_native(PAWN, "GetController", outputs=[obj_pin("ReturnValue", CONTROLLER, "out")], pure=True)
    gm = get_game_mode(g)
    cast = cast_to(g, BP_GM)
    g.link(gm, "ReturnValue", cast, "Object")
    g.link_entry("then", cast, "execute")
    cy = g.call_on(GMC, "CycleItem", inputs=[obj_pin("C", CONTROLLER)])
    g.link(cast, as_pin(BP_GM), cy, "self")
    g.link(ctrl, "ReturnValue", cy, "C")
    g.link(cast, "then", cy, "execute")

    # ---- Event graph ----
    g = bp.event_graph()
    g.section("Begin Play: fresh tires, full health, the paint")
    bpl = g.begin_play(col=0, row=1)
    par = g.call_parent(gen(SEDAN), "ReceiveBeginPlay", col=1, row=1)
    init = g.call_self("InitTires", col=2, row=1)
    g.exec(bpl, par, init)
    full = g.var_set("Health", FLOAT)  # Phase 5: a child with more MaxHealth starts full
    g.link(g.var_get("MaxHealth", FLOAT), "MaxHealth", full, "Health")
    g.exec(init, full)
    paint = g.var_get("PaintMaterial", OBJECT, cls_ref(MATERIAL_INTERFACE))
    has_paint = is_valid(g)
    g.link(paint, "PaintMaterial", has_paint, "Object")
    bpaint = g.branch()
    g.note(bpaint, "a paint of its own?")
    g.link(has_paint, "ReturnValue", bpaint, "Condition")
    g.exec(full, bpaint)
    sm = g.call_on(PRIMITIVE, "SetMaterial", inputs=[Pin("ElementIndex", INT), obj_pin("Material", MATERIAL_INTERFACE)])
    g.link(mesh(g), "Mesh", sm, "self")
    g.link(g.var_get("PaintSlot", INT), "PaintSlot", sm, "ElementIndex")
    g.link(paint, "PaintMaterial", sm, "Material")
    g.link(bpaint, "then", sm, "execute")

    g.section("Tick: drive overrides, then item effects")
    tick = g.tick(col=0, row=2)
    part = g.call_parent(gen(SEDAN), "ReceiveTick", [Pin("DeltaSeconds", FLOAT)], col=1, row=2)
    g.link(tick, "DeltaSeconds", part, "DeltaSeconds")
    ov = g.call_self("TickDriveOverrides", inputs=[Pin("DeltaSeconds", FLOAT)], col=2, row=2)
    g.link(tick, "DeltaSeconds", ov, "DeltaSeconds")
    fx = g.call_self("TickEffects", inputs=[Pin("DeltaSeconds", FLOAT)], col=3, row=2)
    g.link(tick, "DeltaSeconds", fx, "DeltaSeconds")
    g.exec(tick, part, ov, fx)

    g.section("Point damage: route by hit bone (tire or body)")
    pd = g.event(ACTOR, "ReceivePointDamage",
                 [Pin("Damage", FLOAT), obj_pin("DamageType", "/Script/Engine.DamageType"), struct_pin("HitLocation", VECTOR),
                  struct_pin("HitNormal", VECTOR), obj_pin("HitComponent", PRIMITIVE), Pin("BoneName", NAME),
                  struct_pin("ShotFromDirection", VECTOR), obj_pin("InstigatedBy", CONTROLLER), obj_pin("DamageCauser", ACTOR),
                  struct_pin("HitInfo", HIT_RESULT)], col=0, row=3)
    find = g.call_self("FindTireIndexForHit", inputs=[Pin("BoneName", NAME), struct_pin("ImpactPoint", VECTOR)],
                       outputs=[Pin("Index", INT, "out")], col=1, row=3)
    g.link(pd, "BoneName", find, "BoneName")
    g.link(pd, "HitLocation", find, "ImpactPoint")
    take = g.call_self("TakeDamageInternal", inputs=[Pin("Damage", FLOAT), Pin("TireIndex", INT), obj_pin("Instigator", CONTROLLER)], col=2, row=3)
    g.link(pd, "Damage", take, "Damage")
    g.link(find, "Index", take, "TireIndex")
    g.link(pd, "InstigatedBy", take, "Instigator")
    flag = g.var_set("bPointDamageHandled", BOOL, default="true", col=3, row=3)
    g.exec(pd, find, take, flag)

    g.section("Any damage: the body, unless point damage already handled it")
    ad = g.event(ACTOR, "ReceiveAnyDamage",
                 [Pin("Damage", FLOAT), obj_pin("DamageType", "/Script/Engine.DamageType"), obj_pin("InstigatedBy", CONTROLLER),
                  obj_pin("DamageCauser", ACTOR)], col=0, row=4)
    handled = g.var_get("bPointDamageHandled", BOOL, col=1, row=5)
    b = g.branch(col=1, row=4)
    g.link(handled, "bPointDamageHandled", b, "Condition")
    g.exec(ad, b)
    reset = g.var_set("bPointDamageHandled", BOOL, default="false", col=2, row=5)
    g.link(b, "then", reset, "execute")
    take2 = g.call_self("TakeDamageInternal", inputs=[Pin("Damage", FLOAT), Pin("TireIndex", INT, default="-1"), obj_pin("Instigator", CONTROLLER)], col=2, row=4)
    g.link(ad, "Damage", take2, "Damage")
    g.link(ad, "InstigatedBy", take2, "Instigator")
    g.link(b, "else", take2, "execute")

    g.section("Interact: get out")
    ia = g.input_action("Interact", col=0, row=6)
    ex = g.call_self("ExitVehicle", outputs=[Pin("ReturnValue", BOOL, "out")], col=1, row=6)
    g.link(ia, "Pressed", ex, "execute")
    g.section("Use item: the selected item")
    ui = g.input_action("UseItem", col=0, row=7)
    use = g.call_self("UseSelectedItem", outputs=[Pin("ReturnValue", BOOL, "out")], col=1, row=7)
    g.link(ui, "Pressed", use, "execute")
    g.section("Next item: cycle the inventory")
    ni = g.input_action("NextItem", col=0, row=8)
    cy = g.call_self("CycleItem", col=1, row=8)
    g.link(ni, "Pressed", cy, "execute")
    return bp


def build_children() -> list:
    """BRUTE and VIPER (spec 2026-10-30 phase 5 §3): children of BP_DFVehicle that only change class defaults, from the
    VEHICLES catalogue in df.py; the mass override lands on the inherited VehicleMovement component."""
    out = []
    for row in VEHICLES:
        if row.asset == BP_VEHICLE:
            continue
        child = Blueprint(row.asset, parent=BP_VEHICLE, description="%s: %s" % (row.name, row.description))
        child.default("MaxHealth", float(row.max_health))
        child.default("Health", float(row.max_health))
        child.default("VehicleName", row.name)
        child.default("ThrottleScale", float(row.throttle_scale))
        child.default("TopSpeedKPH", float(row.top_speed))
        child.default("BoostDuration", float(row.boost_duration))
        child.default("BoostKickSpeed", float(row.boost_kick))
        if row.paint:
            child.default("PaintMaterial", row.paint)
        if row.mass_factor:
            child.component_default("VehicleMovement", "mass", SEDAN_MASS * row.mass_factor)
        out.append(child)
    return out


def build_all() -> list:
    return [build()] + build_children()


if __name__ == "__main__":
    for b in build_all():
        print(b.write(OUT))
