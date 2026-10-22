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
    bp = Blueprint(BP_VEHICLE, parent=SEDAN)
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

    bp.dispatcher("OnVehicleDamaged", ["Damage:float", "TireIndex:int"])
    bp.dispatcher("OnTireBlown", ["TireIndex:int"])
    bp.dispatcher("OnVehicleDestroyed", ["Vehicle:" + obj_spec(BP_VEHICLE), "Killer:object:" + CONTROLLER])
    bp.dispatcher("OnOccupantEntered", ["Character:" + obj_spec(BP_CHARACTER)])
    bp.dispatcher("OnOccupantExited", ["Character:" + obj_spec(BP_CHARACTER)])

    # ---- InitTires: Tires = four fresh entries ----
    g = bp.function("InitTires")
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
    g = bp.function("GetSpeedKPH", outputs=["KPH:float"], pure=True)
    fwd = mv_call(g, "GetForwardSpeed", outputs=[Pin("ReturnValue", FLOAT, "out")], pure=True)
    ab = g.call_static(MATH, "Abs", inputs=[Pin("A", FLOAT)], outputs=[Pin("ReturnValue", FLOAT, "out")], pure=True)
    mul = math2(g, "Multiply_FloatFloat", FLOAT, b="0.036")
    g.link(fwd, "ReturnValue", ab, "A")
    g.link(ab, "ReturnValue", mul, "A")
    g.link_result(mul, "ReturnValue", "KPH")
    g.link_entry("then", "result", "execute")

    # ---- GetGearString: R / N / number ----
    g = bp.function("GetGearString", outputs=["Gear:string"], pure=True)
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
    g = bp.function("GetBlownTireCount", outputs=["Count:int"], pure=True)
    c = g.var_get("BlownTireCount", INT)
    g.link_result(c, "BlownTireCount", "Count")
    g.link_entry("then", "result", "execute")

    g = bp.function("GetThrottleScale", outputs=["Scale:float"], pure=True)
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

    g = bp.function("IsBelowExitSpeed", outputs=["ReturnValue:bool"], pure=True)
    sp = g.call_self("GetSpeedKPH", outputs=[Pin("KPH", FLOAT, "out")], pure=True)
    mx = g.var_get("ExitMaxSpeedKPH", FLOAT)
    lt = compare(g, "Less_FloatFloat", FLOAT)
    g.link(sp, "KPH", lt, "A")
    g.link(mx, "ExitMaxSpeedKPH", lt, "B")
    g.link_result(lt, "ReturnValue", "ReturnValue")
    g.link_entry("then", "result", "execute")

    g = bp.function("CanBeEntered", outputs=["ReturnValue:bool"], pure=True)
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
    g = bp.function("FindTireIndexForHit", inputs=["BoneName:name", "ImpactPoint:struct:" + VECTOR],
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
    g = bp.function("ApplyTireDamage", inputs=["Index:int", "Damage:float"])
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

    # ---- TakeDamageInternal(Damage, TireIndex, Instigator) ----
    g = bp.function("TakeDamageInternal", inputs=["Damage:float", "TireIndex:int", "Instigator:object:" + CONTROLLER])
    dead = g.var_get("bIsDestroyed", BOOL)
    bdead = g.branch()
    g.link(dead, "bIsDestroyed", bdead, "Condition")
    g.link_entry("then", bdead, "execute")
    ge0 = compare(g, "GreaterEqual_IntInt", INT, b="0")
    g.link_entry("TireIndex", ge0, "A")
    btire = g.branch()
    g.link(ge0, "ReturnValue", btire, "Condition")
    g.link(bdead, "else", btire, "execute")
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
    g = bp.function("DestroyVehicle", inputs=["Killer:object:" + CONTROLLER])
    dead = g.var_get("bIsDestroyed", BOOL)
    b = g.branch()
    g.link(dead, "bIsDestroyed", b, "Condition")
    g.link_entry("then", b, "execute")
    mark = g.var_set("bIsDestroyed", BOOL, default="true")
    g.link(b, "else", mark, "execute")
    hb = set_handbrake(g, "true")
    g.exec(mark, hb)
    fire = g.call_delegate("OnVehicleDestroyed", [obj_pin("Vehicle", VC), obj_pin("Killer", CONTROLLER)])
    me = g.self_node()
    g.link(me, "self", fire, "Vehicle")
    g.link_entry("Killer", fire, "Killer")
    g.exec(hb, fire)
    gm = get_game_mode(g)
    cast = cast_to(g, BP_GM)
    g.link(gm, "ReturnValue", cast, "Object")
    g.exec(fire, cast)
    notify = g.call_on(GMC, "NotifyVehicleDestroyed", inputs=[obj_pin("Victim", VC), obj_pin("Killer", CONTROLLER)])
    g.link(cast, as_pin(BP_GM), notify, "self")
    me2 = g.self_node()
    g.link(me2, "self", notify, "Victim")
    g.link_entry("Killer", notify, "Killer")
    g.link(cast, "then", notify, "execute")

    # ---- TeleportAndStop(NewTransform) ----
    g = bp.function("TeleportAndStop", inputs=["NewTransform:struct:" + TRANSFORM])
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
    g = bp.function("CanExit", outputs=["ReturnValue:bool"], pure=True)
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
    g = bp.function("IsExitSpotFree", inputs=["Location:struct:" + VECTOR], outputs=["ReturnValue:bool"])
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
    g = bp.function("FindExitLocation", outputs=["bFound:bool", "Location:struct:" + VECTOR],
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
    g = bp.function("EnterVehicle", inputs=["Character:" + obj_spec(BP_CHARACTER)], outputs=["ReturnValue:bool"])
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
    g = bp.function("ExitVehicle", outputs=["ReturnValue:bool"],
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
    g = bp.function("EjectOccupant", locals=["Leaving:" + obj_spec(BP_CHARACTER)])
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
    g = bp.function("TickDriveOverrides", inputs=["DeltaSeconds:float"])
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
    axis = g.input_axis_value("MoveForward")
    scale = g.call_self("GetThrottleScale", outputs=[Pin("Scale", FLOAT, "out")], pure=True)
    mul = math2(g, "Multiply_FloatFloat", FLOAT)
    g.link(axis, "ReturnValue", mul, "A")
    g.link(scale, "Scale", mul, "B")
    th = set_throttle(g)
    g.link(mul, "ReturnValue", th, "Throttle")
    g.link(b, "else", th, "execute")

    # ---- Event graph ----
    g = bp.event_graph()
    g.comment("Generated by tools/bpgen/graphs/vehicle.py. Driving/cameras live in the Sedan parent.", 0, 0, cols=6, rows=1)
    bpl = g.begin_play(col=0, row=1)
    par = g.call_parent(gen(SEDAN), "ReceiveBeginPlay", col=1, row=1)
    init = g.call_self("InitTires", col=2, row=1)
    g.exec(bpl, par, init)

    tick = g.tick(col=0, row=2)
    part = g.call_parent(gen(SEDAN), "ReceiveTick", [Pin("DeltaSeconds", FLOAT)], col=1, row=2)
    g.link(tick, "DeltaSeconds", part, "DeltaSeconds")
    ov = g.call_self("TickDriveOverrides", inputs=[Pin("DeltaSeconds", FLOAT)], col=2, row=2)
    g.link(tick, "DeltaSeconds", ov, "DeltaSeconds")
    g.exec(tick, part, ov)

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

    ia = g.input_action("Interact", col=0, row=6)
    ex = g.call_self("ExitVehicle", outputs=[Pin("ReturnValue", BOOL, "out")], col=1, row=6)
    g.link(ia, "Pressed", ex, "execute")
    return bp


if __name__ == "__main__":
    print(build().write(OUT))
