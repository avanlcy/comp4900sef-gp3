"""BP_DFVehicleAIController (plan Tasks 2-5, spec docs/superpowers/specs/2026-10-30-phase4-ai-design.md §2-§3): the NPC
driver. An AIController with a BPC_DFRacer, so the GameMode's scoring, gates, kills and ranking treat it like the player.

Every tick while the race runs and it has an intact car: flip check, stuck check (reverse out), then Drive: a target point
ahead on the main track on its own lane (plus an avoidance bias from three forward traces), steering toward it, a target
speed from the corner ahead, a throttle from the speed error. Task 5 adds the items.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from bpgen import struct_ref  # noqa: E402
from df import (ACTOR, AI_CONTROLLER, BOOL, BP_AI, BP_GM, BP_GS, BP_TRACK, BP_VEHICLE, BPC_RACER, CONTROLLER, E_ITEM_TYPE,  # noqa: E402
                FLOAT, GAMEPLAY, HIT_RESULT, INT, ITEM_BOMB, ITEM_BOOST, ITEM_GUN, ITEM_RPG, ITEM_SHIELD, MATH, OBJECT, OUT, PAWN,
                ROTATOR, SYS, TRANSFORM, VECTOR, Blueprint, Graph, Node, Pin, and_bool, as_pin, cast_to, cls_ref, compare, enum_pin,
                game_time, gen, get_all_actors_of_class, get_game_mode, get_game_state, is_valid, math2, not_bool, obj_pin,
                obj_spec, or_bool, struct_pin)

VC, GSC, GMC, TC, RC = gen(BP_VEHICLE), gen(BP_GS), gen(BP_GM), gen(BP_TRACK), gen(BPC_RACER)


# ---- recipes ----
def fmath(g: Graph, fn: str, ins, outs=None, **defaults) -> Node:
    """Pure KismetMathLibrary call; ins/outs are Pin lists."""
    return g.call_static(MATH, fn, inputs=ins, outputs=outs or [Pin("ReturnValue", FLOAT, "out")], pure=True, **defaults)


def f1(g: Graph, fn: str, src, a_name="A") -> Node:
    """Pure one-float-in, one-float-out math call."""
    n = fmath(g, fn, [Pin(a_name, FLOAT)])
    g.link(src[0], src[1], n, a_name)
    return n


def fclamp(g: Graph, src, lo: str, hi: str) -> Node:
    n = fmath(g, "FClamp", [Pin("Value", FLOAT), Pin("Min", FLOAT, default=lo), Pin("Max", FLOAT, default=hi)])
    g.link(src[0], src[1], n, "Value")
    return n


def vmul(g: Graph, v_src, f_src=None, f=None) -> Node:
    n = g.call_static(MATH, "Multiply_VectorFloat", inputs=[struct_pin("A", VECTOR), Pin("B", FLOAT, default=f)],
                      outputs=[struct_pin("ReturnValue", VECTOR, "out")], pure=True)
    g.link(v_src[0], v_src[1], n, "A")
    if f_src:
        g.link(f_src[0], f_src[1], n, "B")
    return n


def vadd(g: Graph, a_src, b_src) -> Node:
    n = g.call_static(MATH, "Add_VectorVector", inputs=[struct_pin("A", VECTOR), struct_pin("B", VECTOR)],
                      outputs=[struct_pin("ReturnValue", VECTOR, "out")], pure=True)
    g.link(a_src[0], a_src[1], n, "A")
    g.link(b_src[0], b_src[1], n, "B")
    return n


def car_call(g: Graph, fn: str, car_src, inputs=None, outputs=None, pure=False, **defaults) -> Node:
    n = g.call_on(VC, fn, inputs=inputs, outputs=outputs, pure=pure, **defaults)
    g.link(car_src[0], car_src[1], n, "self")
    return n


def actor_call(g: Graph, fn: str, actor_src, outputs) -> Node:
    n = g.call_on(ACTOR, fn, outputs=outputs, pure=True)
    g.link(actor_src[0], actor_src[1], n, "self")
    return n


def car_loc(g: Graph, car_src) -> tuple:
    return (actor_call(g, "K2_GetActorLocation", car_src, [struct_pin("ReturnValue", VECTOR, "out")]), "ReturnValue")


def car_fwd(g: Graph, car_src) -> tuple:
    return (actor_call(g, "GetActorForwardVector", car_src, [struct_pin("ReturnValue", VECTOR, "out")]), "ReturnValue")


def car_up(g: Graph, car_src) -> tuple:
    return (actor_call(g, "GetActorUpVector", car_src, [struct_pin("ReturnValue", VECTOR, "out")]), "ReturnValue")


def car_kph(g: Graph, car_src) -> tuple:
    return (car_call(g, "GetSpeedKPH", car_src, outputs=[Pin("KPH", FLOAT, "out")], pure=True), "KPH")


def set_ai_input(g: Graph, car_src, throttle=None, steering=None, handbrake="false") -> Node:
    """Car.SetAIInput(...); throttle/steering are (node, pin) sources or None for 0."""
    n = car_call(g, "SetAIInput", car_src, inputs=[Pin("Throttle", FLOAT, default=None if throttle else "0.0"),
                                                   Pin("Steering", FLOAT, default=None if steering else "0.0"),
                                                   Pin("bHandbrake", BOOL, default=handbrake)])
    if throttle:
        g.link(throttle[0], throttle[1], n, "Throttle")
    if steering:
        g.link(steering[0], steering[1], n, "Steering")
    return n


def park(g: Graph, car_src) -> Node:
    return set_ai_input(g, car_src, handbrake="true")


def respawn_self(g: Graph, prev) -> Node:
    """GameMode.RespawnRacer(self); prev = (node, exec pin). Returns the last exec node."""
    gm = get_game_mode(g)
    cast = cast_to(g, BP_GM)
    g.link(gm, "ReturnValue", cast, "Object")
    g.link(prev[0], prev[1], cast, "execute")
    rs = g.call_on(GMC, "RespawnRacer", inputs=[obj_pin("C", CONTROLLER)])
    g.link(cast, as_pin(BP_GM), rs, "self")
    me = g.self_node()
    g.link(me, "self", rs, "C")
    g.link(cast, "then", rs, "execute")
    return rs


def branch_on(g: Graph, cond_src, prev=None, note=None) -> Node:
    b = g.branch()
    g.link(cond_src[0], cond_src[1], b, "Condition")
    if prev:
        g.link(prev[0], prev[1], b, "execute")
    if note:
        g.note(b, note)
    return b


def var(g: Graph, name: str, cat=FLOAT) -> tuple:
    return (g.var_get(name, cat), name)


def build() -> Blueprint:
    bp = Blueprint(BP_AI, parent=AI_CONTROLLER,
                   description="An NPC driver: follows the main track on its own lane, avoids cars, uses items against the "
                               "player, and is respawned by the GameMode like any racer.")
    bp.component("Racer", gen(BPC_RACER))
    D = "Dead Fire|AI|Driving"
    bp.variable("bAutoDrive", "bool", "true", D, editable=True)  # off: the controller holds the car still (tests, debugging)
    bp.variable("MaxSpeedKPH", "float", "110", D, editable=True)
    bp.variable("CornerSpeedKPH", "float", "45", D, editable=True)
    bp.variable("SpeedScale", "float", "1", D, editable=True)
    bp.variable("LaneOffset", "float", "0", D, editable=True)
    bp.variable("LookaheadBase", "float", "1200", D, editable=True)
    bp.variable("LookaheadPerKPH", "float", "12", D, editable=True)
    bp.variable("CornerLookahead", "float", "2500", D, editable=True)
    bp.variable("CornerAngleFull", "float", "60", D, editable=True)
    bp.variable("SteerFullLockDegrees", "float", "35", D, editable=True)
    bp.variable("BrakeMarginKPH", "float", "10", D, editable=True)
    V = "Dead Fire|AI|Avoidance"
    bp.variable("AvoidanceDistance", "float", "1500", V, editable=True)
    bp.variable("AvoidanceAngle", "float", "20", V, editable=True)
    bp.variable("AvoidanceOffset", "float", "350", V, editable=True)
    bp.variable("AvoidInterpSpeed", "float", "3", V, editable=True)
    R = "Dead Fire|AI|Recovery"
    bp.variable("StuckSpeedKPH", "float", "5", R, editable=True)
    bp.variable("StuckSeconds", "float", "2.5", R, editable=True)
    bp.variable("ReverseSeconds", "float", "1.5", R, editable=True)
    bp.variable("GiveUpSeconds", "float", "10", R, editable=True)
    bp.variable("RecoverDistance", "float", "2000", R, editable=True)  # cm of track progress, either way, that ends a stuck episode
    bp.variable("FlipSeconds", "float", "2", R, editable=True)
    bp.variable("NoPawnSeconds", "float", "1", R, editable=True)
    I = "Dead Fire|AI|Items"
    bp.variable("bUseItems", "bool", "true", I, editable=True)
    bp.variable("ItemThinkInterval", "float", "0.5", I, editable=True)
    bp.variable("GunRange", "float", "6000", I, editable=True)
    bp.variable("RPGRange", "float", "4000", I, editable=True)
    bp.variable("RPGMinRange", "float", "1200", I, editable=True)
    bp.variable("AimCone", "float", "0.96", I, editable=True)
    bp.variable("BombRange", "float", "1500", I, editable=True)
    bp.variable("ShieldHealthFraction", "float", "0.5", I, editable=True)
    bp.variable("BoostMaxSeverity", "float", "0.2", I, editable=True)
    bp.variable("bPreferPlayer", "bool", "true", I, editable=True)
    S = "Dead Fire|AI|State"
    bp.variable("CurrentVehicle", obj_spec(BP_VEHICLE), "", S)
    bp.variable("Track", obj_spec(BP_TRACK), "", S)
    bp.variable("Throttle", "float", "0", S)
    bp.variable("Steering", "float", "0", S)
    bp.variable("AvoidBias", "float", "0", S)
    bp.variable("LastSeverity", "float", "0", S)
    bp.variable("TargetPoint", "struct:" + VECTOR, "", S)
    bp.variable("StuckTimer", "float", "0", S)
    bp.variable("StuckTotal", "float", "0", S)
    bp.variable("ReverseUntil", "float", "-1", S)
    bp.variable("FlipTimer", "float", "0", S)
    bp.variable("NoPawnTimer", "float", "0", S)
    bp.variable("LastKPH", "float", "0", S)
    bp.variable("StuckStartDistance", "float", "-1", S)  # racer.DistanceAlongTrack when the stuck episode began; -1 = none
    bp.variable("NextThinkTime", "float", "0", S)

    # ---- GetTrack() -> Track: the GameMode's main track, cached ----
    g = bp.function("GetTrack", outputs=["Track:" + obj_spec(BP_TRACK)], doc="The main track from the GameMode, looked up once and cached.")
    cached_get = g.var_get("Track", OBJECT, cls_ref(TC))
    cv = is_valid(g)
    g.link(cached_get, "Track", cv, "Object")
    b = branch_on(g, (cv, "ReturnValue"))
    g.link_entry("then", b, "execute")
    r_cached = g.function_result([obj_pin("Track", TC)])
    g.link(cached_get, "Track", r_cached, "Track")
    g.link(b, "then", r_cached, "execute")
    gm = get_game_mode(g)
    cast = cast_to(g, BP_GM)
    g.link(gm, "ReturnValue", cast, "Object")
    g.link(b, "else", cast, "execute")
    mt = g.var_get_on(GMC, "MainTrack", OBJECT, cls_ref(TC))
    g.link(cast, as_pin(BP_GM), mt, "self")
    st = g.var_set("Track", OBJECT, sub_object=cls_ref(TC))
    g.link(mt, "MainTrack", st, "Track")
    g.link(cast, "then", st, "execute")
    r_found = g.function_result([obj_pin("Track", TC)])
    g.link(st, "Output_Get", r_found, "Track")
    g.exec(st, r_found)
    r_none = g.function_result([obj_pin("Track", TC)])
    g.link(cast, "CastFailed", r_none, "execute")

    # ---- ComputeSteering(FromLocation, FromYaw, Target) -> Steering ----
    g = bp.function("ComputeSteering", inputs=["FromLocation:struct:" + VECTOR, "FromYaw:float", "Target:struct:" + VECTOR],
                    outputs=["Steering:float"], pure=True,
                    doc="Steering in [-1, 1] toward a target: the yaw to turn divided by SteerFullLockDegrees, clamped.")
    look = g.call_static(MATH, "FindLookAtRotation", inputs=[struct_pin("Start", VECTOR), struct_pin("Target", VECTOR)],
                         outputs=[struct_pin("ReturnValue", ROTATOR, "out")], pure=True)
    g.link_entry("FromLocation", look, "Start")
    g.link_entry("Target", look, "Target")
    br = g.call_static(MATH, "BreakRotator", inputs=[struct_pin("InRot", ROTATOR)],
                       outputs=[Pin("Roll", FLOAT, "out"), Pin("Pitch", FLOAT, "out"), Pin("Yaw", FLOAT, "out")], pure=True)
    g.link(look, "ReturnValue", br, "InRot")
    delta = math2(g, "Subtract_FloatFloat", FLOAT)
    g.link(br, "Yaw", delta, "A")
    g.link_entry("FromYaw", delta, "B")
    norm = f1(g, "NormalizeAxis", (delta, "ReturnValue"), "Angle")
    lock = var(g, "SteerFullLockDegrees")
    ratio = math2(g, "Divide_FloatFloat", FLOAT)
    g.link(norm, "ReturnValue", ratio, "A")
    g.link(lock[0], lock[1], ratio, "B")
    steer = fclamp(g, (ratio, "ReturnValue"), "-1.0", "1.0")
    g.link_result(steer, "ReturnValue", "Steering")
    g.link_entry("then", "result", "execute")

    # ---- ComputeTargetSpeed(Severity) -> KPH ----
    g = bp.function("ComputeTargetSpeed", inputs=["Severity:float"], outputs=["KPH:float"], pure=True,
                    doc="MaxSpeedKPH on a straight down to CornerSpeedKPH in a full corner, times this driver's SpeedScale.")
    sev = fclamp(g, ("entry", "Severity"), "0.0", "1.0")
    lerp = fmath(g, "Lerp", [Pin("A", FLOAT), Pin("B", FLOAT), Pin("Alpha", FLOAT)])
    mx, cs = var(g, "MaxSpeedKPH"), var(g, "CornerSpeedKPH")
    g.link(mx[0], mx[1], lerp, "A")
    g.link(cs[0], cs[1], lerp, "B")
    g.link(sev, "ReturnValue", lerp, "Alpha")
    scaled = math2(g, "Multiply_FloatFloat", FLOAT)
    g.link(lerp, "ReturnValue", scaled, "A")
    sc = var(g, "SpeedScale")
    g.link(sc[0], sc[1], scaled, "B")
    g.link_result(scaled, "ReturnValue", "KPH")
    g.link_entry("then", "result", "execute")

    # ---- ComputeThrottle(SpeedKPH, TargetKPH, Steering) -> Throttle ----
    g = bp.function("ComputeThrottle", inputs=["SpeedKPH:float", "TargetKPH:float", "Steering:float"], outputs=["Throttle:float"], pure=True,
                    doc="1 below the target speed, -0.5 (brake) more than BrakeMarginKPH above it, 0.2 between; at most 0.3 while steering hard above the corner speed.")
    below = compare(g, "Less_FloatFloat", FLOAT)
    g.link_entry("SpeedKPH", below, "A")
    g.link_entry("TargetKPH", below, "B")
    margin = var(g, "BrakeMarginKPH")
    limit = math2(g, "Add_FloatFloat", FLOAT)
    g.link_entry("TargetKPH", limit, "A")
    g.link(margin[0], margin[1], limit, "B")
    above = compare(g, "Greater_FloatFloat", FLOAT)
    g.link_entry("SpeedKPH", above, "A")
    g.link(limit, "ReturnValue", above, "B")
    brake_or_coast = fmath(g, "SelectFloat", [Pin("A", FLOAT, default="-0.5"), Pin("B", FLOAT, default="0.2"), Pin("bPickA", BOOL)])
    g.link(above, "ReturnValue", brake_or_coast, "bPickA")
    base = fmath(g, "SelectFloat", [Pin("A", FLOAT, default="1.0"), Pin("B", FLOAT), Pin("bPickA", BOOL)])
    g.link(brake_or_coast, "ReturnValue", base, "B")
    g.link(below, "ReturnValue", base, "bPickA")
    hard = compare(g, "Greater_FloatFloat", FLOAT, b="0.8")
    g.link(f1(g, "Abs", ("entry", "Steering")), "ReturnValue", hard, "A")
    fast = compare(g, "Greater_FloatFloat", FLOAT)
    g.link_entry("SpeedKPH", fast, "A")
    cs2 = var(g, "CornerSpeedKPH")
    g.link(cs2[0], cs2[1], fast, "B")
    both = and_bool(g)
    g.link(hard, "ReturnValue", both, "A")
    g.link(fast, "ReturnValue", both, "B")
    capped = fmath(g, "FMin", [Pin("A", FLOAT), Pin("B", FLOAT, default="0.3")])
    g.link(base, "ReturnValue", capped, "A")
    pick = fmath(g, "SelectFloat", [Pin("A", FLOAT), Pin("B", FLOAT), Pin("bPickA", BOOL)])
    g.link(capped, "ReturnValue", pick, "A")
    g.link(base, "ReturnValue", pick, "B")
    g.link(both, "ReturnValue", pick, "bPickA")
    g.link_result(pick, "ReturnValue", "Throttle")
    g.link_entry("then", "result", "execute")

    # ---- ComputeTargetPoint(Car) -> Location, Severity ----
    g = bp.function("ComputeTargetPoint", inputs=["Car:" + obj_spec(BP_VEHICLE)], outputs=["Location:struct:" + VECTOR, "Severity:float"],
                    locals=["Distance:float"],
                    doc="The point to steer at: the track a speed-scaled look-ahead further on, moved onto this driver's lane (plus the avoidance bias); and how sharp the road turns ahead.")
    car = ("entry", "Car")
    tr = g.call_self("GetTrack", outputs=[obj_pin("Track", TC, "out")])
    g.link_entry("then", tr, "execute")
    T = (tr, "Track")
    tv = is_valid(g)
    g.link(tr, "Track", tv, "Object")
    btr = branch_on(g, (tv, "ReturnValue"), (tr, "then"), note="is there a main track?")
    # no track: 10 m ahead of the car, no corner
    ahead = vadd(g, car_loc(g, car), (vmul(g, car_fwd(g, car), f="1000.0"), "ReturnValue"))
    r_none = g.function_result([struct_pin("Location", VECTOR), Pin("Severity", FLOAT, default="0.0")])
    g.link(ahead, "ReturnValue", r_none, "Location")
    g.link(btr, "else", r_none, "execute")
    # progress along the track
    d = g.call_on(TC, "GetDistanceAlongTrack", inputs=[struct_pin("WorldLocation", VECTOR)], outputs=[Pin("Distance", FLOAT, "out")], pure=True)
    g.link(T[0], T[1], d, "self")
    loc = car_loc(g, car)
    g.link(loc[0], loc[1], d, "WorldLocation")
    s_d = g.local_set("Distance", FLOAT)
    g.link(d, "Distance", s_d, "Distance")
    g.link(btr, "then", s_d, "execute")
    dist = lambda: (g.local_get("Distance", FLOAT), "Distance")
    # look-ahead = LookaheadBase + kph * LookaheadPerKPH
    kph = car_kph(g, car)
    per = var(g, "LookaheadPerKPH")
    extra = math2(g, "Multiply_FloatFloat", FLOAT)
    g.link(kph[0], kph[1], extra, "A")
    g.link(per[0], per[1], extra, "B")
    base = var(g, "LookaheadBase")
    la = math2(g, "Add_FloatFloat", FLOAT)
    g.link(base[0], base[1], la, "A")
    g.link(extra, "ReturnValue", la, "B")
    d_la = math2(g, "Add_FloatFloat", FLOAT)
    dd = dist()
    g.link(dd[0], dd[1], d_la, "A")
    g.link(la, "ReturnValue", d_la, "B")

    def wrap(src):
        n = g.call_on(TC, "WrapDistance", inputs=[Pin("Distance", FLOAT)], outputs=[Pin("Wrapped", FLOAT, "out")], pure=True)
        g.link(T[0], T[1], n, "self")
        g.link(src[0], src[1], n, "Distance")
        return (n, "Wrapped")

    def direction(src):
        n = g.call_on(TC, "GetDirectionAtDistance", inputs=[Pin("Distance", FLOAT)], outputs=[struct_pin("Direction", VECTOR, "out")], pure=True)
        g.link(T[0], T[1], n, "self")
        g.link(src[0], src[1], n, "Distance")
        return (n, "Direction")

    xf = g.call_on(TC, "GetTransformAtDistance", inputs=[Pin("Distance", FLOAT)], outputs=[struct_pin("Transform", TRANSFORM, "out")], pure=True)
    g.link(T[0], T[1], xf, "self")
    w = wrap((d_la, "ReturnValue"))
    g.link(w[0], w[1], xf, "Distance")
    brk = g.call_static(MATH, "BreakTransform", inputs=[struct_pin("InTransform", TRANSFORM)],
                        outputs=[struct_pin("Location", VECTOR, "out"), struct_pin("Rotation", ROTATOR, "out"), struct_pin("Scale", VECTOR, "out")], pure=True)
    g.link(xf, "Transform", brk, "InTransform")
    right = g.call_static(MATH, "GetRightVector", inputs=[struct_pin("InRot", ROTATOR)], outputs=[struct_pin("ReturnValue", VECTOR, "out")], pure=True)
    g.link(brk, "Rotation", right, "InRot")
    lane, bias = var(g, "LaneOffset"), var(g, "AvoidBias")
    offset = math2(g, "Add_FloatFloat", FLOAT)
    g.link(lane[0], lane[1], offset, "A")
    g.link(bias[0], bias[1], offset, "B")
    target = vadd(g, (brk, "Location"), (vmul(g, (right, "ReturnValue"), f_src=(offset, "ReturnValue")), "ReturnValue"))
    # corner severity: the angle between the road here and CornerLookahead further on
    cl = var(g, "CornerLookahead")
    d_cl = math2(g, "Add_FloatFloat", FLOAT)
    dd2 = dist()
    g.link(dd2[0], dd2[1], d_cl, "A")
    g.link(cl[0], cl[1], d_cl, "B")
    here, there = direction(dist()), direction(wrap((d_cl, "ReturnValue")))
    dot = g.call_static(MATH, "Dot_VectorVector", inputs=[struct_pin("A", VECTOR), struct_pin("B", VECTOR)], outputs=[Pin("ReturnValue", FLOAT, "out")], pure=True)
    g.link(here[0], here[1], dot, "A")
    g.link(there[0], there[1], dot, "B")
    angle = f1(g, "DegAcos", (fclamp(g, (dot, "ReturnValue"), "-1.0", "1.0"), "ReturnValue"))
    full = var(g, "CornerAngleFull")
    frac = math2(g, "Divide_FloatFloat", FLOAT)
    g.link(angle, "ReturnValue", frac, "A")
    g.link(full[0], full[1], frac, "B")
    sev = fclamp(g, (frac, "ReturnValue"), "0.0", "1.0")
    s_tp = g.var_set("TargetPoint", "struct", sub_object=struct_ref(VECTOR))
    g.link(target, "ReturnValue", s_tp, "TargetPoint")
    g.exec(s_d, s_tp)
    r = g.function_result([struct_pin("Location", VECTOR), Pin("Severity", FLOAT)])
    g.link(s_tp, "Output_Get", r, "Location")
    g.link(sev, "ReturnValue", r, "Severity")
    g.exec(s_tp, r)

    # ---- ComputeAvoidance(Car) -> Bias ----
    g = bp.function("ComputeAvoidance", inputs=["Car:" + obj_spec(BP_VEHICLE)], outputs=["Bias:float"],
                    doc="Three traces ahead (straight, left, right): a blocked side pushes the lane the other way; a blocked centre picks the free side.")
    car = ("entry", "Car")
    fwd, up = car_fwd(g, car), car_up(g, car)
    nose = vadd(g, car_loc(g, car), (vmul(g, fwd, f="300.0"), "ReturnValue"))
    origin = vadd(g, (nose, "ReturnValue"), (vmul(g, up, f="80.0"), "ReturnValue"))
    ang = var(g, "AvoidanceAngle")
    neg_ang = math2(g, "Multiply_FloatFloat", FLOAT, b="-1.0")
    g.link(ang[0], ang[1], neg_ang, "A")
    ignore = g.make_array(obj_pin("e", ACTOR), [None])
    g.link_entry("Car", ignore, "[0]")
    dist = var(g, "AvoidanceDistance")

    def trace(dir_src, prev):
        end = vadd(g, (origin, "ReturnValue"), (vmul(g, dir_src, f_src=dist), "ReturnValue"))
        n = g.call_static(SYS, "LineTraceSingle",
                          inputs=[Pin("WorldContextObject", OBJECT, hidden=True), struct_pin("Start", VECTOR), struct_pin("End", VECTOR),
                                  Pin("TraceChannel", "byte", default="TraceTypeQuery1"), Pin("bTraceComplex", BOOL, default="false"),
                                  Pin("ActorsToIgnore", OBJECT, sub_object=cls_ref(ACTOR), container="Array"),
                                  Pin("DrawDebugType", "byte", default="None"), Pin("bIgnoreSelf", BOOL, default="true")],
                          outputs=[struct_pin("OutHit", HIT_RESULT, "out"), Pin("ReturnValue", BOOL, "out")])
        g.link(origin, "ReturnValue", n, "Start")
        g.link(end, "ReturnValue", n, "End")
        g.link(ignore, "Array", n, "ActorsToIgnore")
        g.link(prev[0], prev[1], n, "execute")
        return n

    def rotated(angle_src):
        n = g.call_static(MATH, "RotateAngleAxis", inputs=[struct_pin("InVect", VECTOR), Pin("AngleDeg", FLOAT), struct_pin("Axis", VECTOR)],
                          outputs=[struct_pin("ReturnValue", VECTOR, "out")], pure=True)
        g.link(fwd[0], fwd[1], n, "InVect")
        g.link(angle_src[0], angle_src[1], n, "AngleDeg")
        g.link(up[0], up[1], n, "Axis")
        return (n, "ReturnValue")

    tc = trace(fwd, ("entry", "then"))
    tl = trace(rotated((neg_ang, "ReturnValue")), (tc, "then"))
    tr_ = trace(rotated(ang), (tl, "then"))
    hit_c, hit_l, hit_r = (tc, "ReturnValue"), (tl, "ReturnValue"), (tr_, "ReturnValue")
    off = var(g, "AvoidanceOffset")
    neg_off = math2(g, "Multiply_FloatFloat", FLOAT, b="-1.0")
    g.link(off[0], off[1], neg_off, "A")
    half = math2(g, "Multiply_FloatFloat", FLOAT, b="0.5")
    g.link(off[0], off[1], half, "A")
    neg_half = math2(g, "Multiply_FloatFloat", FLOAT, b="-0.5")
    g.link(off[0], off[1], neg_half, "A")

    def result(src):
        rr = g.function_result([Pin("Bias", FLOAT)])
        g.link(src[0], src[1], rr, "Bias")
        return rr

    bc = branch_on(g, hit_c, (tr_, "then"), note="something straight ahead?")
    l_only = and_bool(g)
    g.link(hit_l[0], hit_l[1], l_only, "A")
    nr = not_bool(g)
    g.link(hit_r[0], hit_r[1], nr, "A")
    g.link(nr, "ReturnValue", l_only, "B")
    bl_only = branch_on(g, (l_only, "ReturnValue"), (bc, "then"), note="left blocked too, right free: go right")
    g.link(bl_only, "then", result((off[0], off[1])), "execute")
    r_only = and_bool(g)
    g.link(hit_r[0], hit_r[1], r_only, "A")
    nl = not_bool(g)
    g.link(hit_l[0], hit_l[1], nl, "A")
    g.link(nl, "ReturnValue", r_only, "B")
    br_only = branch_on(g, (r_only, "ReturnValue"), (bl_only, "else"), note="right blocked too, left free: go left")
    g.link(br_only, "then", result((neg_off, "ReturnValue")), "execute")
    cur = var(g, "AvoidBias")
    keep_right = compare(g, "GreaterEqual_FloatFloat", FLOAT, b="0.0")
    g.link(cur[0], cur[1], keep_right, "A")
    same_side = fmath(g, "SelectFloat", [Pin("A", FLOAT), Pin("B", FLOAT), Pin("bPickA", BOOL)])
    g.link(off[0], off[1], same_side, "A")
    g.link(neg_off, "ReturnValue", same_side, "B")
    g.link(keep_right, "ReturnValue", same_side, "bPickA")
    g.link(br_only, "else", result((same_side, "ReturnValue")), "execute")
    bl = branch_on(g, hit_l, (bc, "else"), note="only the left is blocked: half a lane right")
    g.link(bl, "then", result((half, "ReturnValue")), "execute")
    br = branch_on(g, hit_r, (bl, "else"), note="only the right is blocked: half a lane left")
    g.link(br, "then", result((neg_half, "ReturnValue")), "execute")
    g.link(br, "else", g.function_result([Pin("Bias", FLOAT, default="0.0")]), "execute")

    # ---- Drive(Car, DeltaSeconds) ----
    g = bp.function("Drive", inputs=["Car:" + obj_spec(BP_VEHICLE), "DeltaSeconds:float"],
                    doc="One frame of driving: target point and corner ahead, avoidance bias, steering, target speed, throttle, then SetAIInput.")
    car = ("entry", "Car")
    tp = g.call_self("ComputeTargetPoint", inputs=[obj_pin("Car", VC)], outputs=[struct_pin("Location", VECTOR, "out"), Pin("Severity", FLOAT, "out")])
    g.link_entry("Car", tp, "Car")
    g.link_entry("then", tp, "execute")
    av = g.call_self("ComputeAvoidance", inputs=[obj_pin("Car", VC)], outputs=[Pin("Bias", FLOAT, "out")])
    g.link_entry("Car", av, "Car")
    g.exec(tp, av)
    interp = fmath(g, "FInterpTo", [Pin("Current", FLOAT), Pin("Target", FLOAT), Pin("DeltaTime", FLOAT), Pin("InterpSpeed", FLOAT)])
    cur = var(g, "AvoidBias")
    g.link(cur[0], cur[1], interp, "Current")
    g.link(av, "Bias", interp, "Target")
    g.link_entry("DeltaSeconds", interp, "DeltaTime")
    spd = var(g, "AvoidInterpSpeed")
    g.link(spd[0], spd[1], interp, "InterpSpeed")
    s_bias = g.var_set("AvoidBias", FLOAT)
    g.link(interp, "ReturnValue", s_bias, "AvoidBias")
    g.exec(av, s_bias)
    s_sev = g.var_set("LastSeverity", FLOAT)
    g.link(tp, "Severity", s_sev, "LastSeverity")
    g.exec(s_bias, s_sev)
    rot = actor_call(g, "K2_GetActorRotation", car, [struct_pin("ReturnValue", ROTATOR, "out")])
    brr = g.call_static(MATH, "BreakRotator", inputs=[struct_pin("InRot", ROTATOR)],
                        outputs=[Pin("Roll", FLOAT, "out"), Pin("Pitch", FLOAT, "out"), Pin("Yaw", FLOAT, "out")], pure=True)
    g.link(rot, "ReturnValue", brr, "InRot")
    steer = g.call_self("ComputeSteering", inputs=[struct_pin("FromLocation", VECTOR), Pin("FromYaw", FLOAT), struct_pin("Target", VECTOR)],
                        outputs=[Pin("Steering", FLOAT, "out")], pure=True)
    loc = car_loc(g, car)
    g.link(loc[0], loc[1], steer, "FromLocation")
    g.link(brr, "Yaw", steer, "FromYaw")
    g.link(tp, "Location", steer, "Target")
    tspeed = g.call_self("ComputeTargetSpeed", inputs=[Pin("Severity", FLOAT)], outputs=[Pin("KPH", FLOAT, "out")], pure=True)
    g.link(tp, "Severity", tspeed, "Severity")
    thr = g.call_self("ComputeThrottle", inputs=[Pin("SpeedKPH", FLOAT), Pin("TargetKPH", FLOAT), Pin("Steering", FLOAT)],
                      outputs=[Pin("Throttle", FLOAT, "out")], pure=True)
    kph = car_kph(g, car)
    g.link(kph[0], kph[1], thr, "SpeedKPH")
    g.link(tspeed, "KPH", thr, "TargetKPH")
    g.link(steer, "Steering", thr, "Steering")
    s_thr = g.var_set("Throttle", FLOAT)
    g.link(thr, "Throttle", s_thr, "Throttle")
    g.exec(s_sev, s_thr)
    s_st = g.var_set("Steering", FLOAT)
    g.link(steer, "Steering", s_st, "Steering")
    g.exec(s_thr, s_st)
    apply = set_ai_input(g, car, (s_thr, "Output_Get"), (s_st, "Output_Get"))
    g.exec(s_st, apply)

    # ---- UpdateFlip(Car, DeltaSeconds) -> bRespawned ----
    g = bp.function("UpdateFlip", inputs=["Car:" + obj_spec(BP_VEHICLE), "DeltaSeconds:float"], outputs=["bRespawned:bool"],
                    doc="A car on its side or roof for FlipSeconds is put back at its gate by the GameMode (no death counted).")
    car = ("entry", "Car")
    upz = g.call_static(MATH, "BreakVector", inputs=[struct_pin("InVec", VECTOR)],
                        outputs=[Pin("X", FLOAT, "out"), Pin("Y", FLOAT, "out"), Pin("Z", FLOAT, "out")], pure=True)
    u = car_up(g, car)
    g.link(u[0], u[1], upz, "InVec")
    flipped = compare(g, "Less_FloatFloat", FLOAT, b="0.3")
    g.link(upz, "Z", flipped, "A")
    b = branch_on(g, (flipped, "ReturnValue"), note="wheels off the ground (up vector Z under 0.3)?")
    g.link_entry("then", b, "execute")
    ft = var(g, "FlipTimer")
    acc = math2(g, "Add_FloatFloat", FLOAT)
    g.link(ft[0], ft[1], acc, "A")
    g.link_entry("DeltaSeconds", acc, "B")
    s_ft = g.var_set("FlipTimer", FLOAT)
    g.link(acc, "ReturnValue", s_ft, "FlipTimer")
    g.link(b, "then", s_ft, "execute")
    limit = var(g, "FlipSeconds")
    due = compare(g, "GreaterEqual_FloatFloat", FLOAT)
    g.link(s_ft, "Output_Get", due, "A")
    g.link(limit[0], limit[1], due, "B")
    bd = branch_on(g, (due, "ReturnValue"), (s_ft, "then"))
    z1 = g.var_set("FlipTimer", FLOAT, default="0.0")
    g.link(bd, "then", z1, "execute")
    rs = respawn_self(g, (z1, "then"))
    g.exec(rs, g.function_result([Pin("bRespawned", BOOL, default="true")]))
    g.link(bd, "else", g.function_result([Pin("bRespawned", BOOL, default="false")]), "execute")
    z2 = g.var_set("FlipTimer", FLOAT, default="0.0")
    g.link(b, "else", z2, "execute")
    g.exec(z2, g.function_result([Pin("bRespawned", BOOL, default="false")]))

    # ---- UpdateStuck(Car, DeltaSeconds) -> bReversing ----
    g = bp.function("UpdateStuck", inputs=["Car:" + obj_spec(BP_VEHICLE), "DeltaSeconds:float"], outputs=["bReversing:bool"],
                    doc="Not moving while asking for throttle: after StuckSeconds reverse for ReverseSeconds; stuck for GiveUpSeconds in all (the budget only clears after RecoverDistance of progress, or a respawn), ask the GameMode for a respawn.")
    car = ("entry", "Car")
    now = game_time(g)
    ru = var(g, "ReverseUntil")
    reversing = compare(g, "Less_FloatFloat", FLOAT)
    g.link(now, "ReturnValue", reversing, "A")
    g.link(ru[0], ru[1], reversing, "B")
    b0 = branch_on(g, (reversing, "ReturnValue"), note="still reversing out?")
    g.link_entry("then", b0, "execute")
    st = var(g, "Steering")
    inv = math2(g, "Multiply_FloatFloat", FLOAT, b="-1.0")
    g.link(st[0], st[1], inv, "A")
    back = car_call(g, "SetAIInput", car, inputs=[Pin("Throttle", FLOAT, default="-1.0"), Pin("Steering", FLOAT), Pin("bHandbrake", BOOL, default="false")])
    g.link(inv, "ReturnValue", back, "Steering")
    g.link(b0, "then", back, "execute")
    g.exec(back, g.function_result([Pin("bReversing", BOOL, default="true")]))
    kph = car_kph(g, car)
    slow = compare(g, "Less_FloatFloat", FLOAT)
    g.link(kph[0], kph[1], slow, "A")
    ss = var(g, "StuckSpeedKPH")
    g.link(ss[0], ss[1], slow, "B")
    pushing = compare(g, "Greater_FloatFloat", FLOAT, b="0.5")
    th = var(g, "Throttle")
    g.link(th[0], th[1], pushing, "A")
    lk = var(g, "LastKPH")
    no_gain = compare(g, "LessEqual_FloatFloat", FLOAT)
    g.link(kph[0], kph[1], no_gain, "A")
    plus = math2(g, "Add_FloatFloat", FLOAT, b="0.05")
    g.link(lk[0], lk[1], plus, "A")
    g.link(plus, "ReturnValue", no_gain, "B")
    a1, a2 = and_bool(g), and_bool(g)
    g.link(slow, "ReturnValue", a1, "A")
    g.link(pushing, "ReturnValue", a1, "B")
    g.link(a1, "ReturnValue", a2, "A")
    g.link(no_gain, "ReturnValue", a2, "B")
    s_lk = g.var_set("LastKPH", FLOAT)
    g.link(kph[0], kph[1], s_lk, "LastKPH")
    g.link(b0, "else", s_lk, "execute")
    bs = branch_on(g, (a2, "ReturnValue"), (s_lk, "then"), note="slow, pushing, and not gaining speed?")
    # stuck: both timers grow
    t1 = var(g, "StuckTimer")
    inc1 = math2(g, "Add_FloatFloat", FLOAT)
    g.link(t1[0], t1[1], inc1, "A")
    g.link_entry("DeltaSeconds", inc1, "B")
    s_t1 = g.var_set("StuckTimer", FLOAT)
    g.link(inc1, "ReturnValue", s_t1, "StuckTimer")
    ssd = var(g, "StuckStartDistance")
    fresh = compare(g, "Less_FloatFloat", FLOAT, b="0.0")
    g.link(ssd[0], ssd[1], fresh, "A")
    bf = branch_on(g, (fresh, "ReturnValue"), (bs, "then"), note="first stuck tick of an episode: remember where")
    racer_d = g.var_get_on(RC, "DistanceAlongTrack", FLOAT)
    g.link(g.var_get("Racer", OBJECT, cls_ref(RC)), "Racer", racer_d, "self")
    s_ssd = g.var_set("StuckStartDistance", FLOAT)
    g.link(racer_d, "DistanceAlongTrack", s_ssd, "StuckStartDistance")
    g.link(bf, "then", s_ssd, "execute")
    g.exec(s_ssd, s_t1)
    g.link(bf, "else", s_t1, "execute")
    t2 = var(g, "StuckTotal")
    inc2 = math2(g, "Add_FloatFloat", FLOAT)
    g.link(t2[0], t2[1], inc2, "A")
    g.link_entry("DeltaSeconds", inc2, "B")
    s_t2 = g.var_set("StuckTotal", FLOAT)
    g.link(inc2, "ReturnValue", s_t2, "StuckTotal")
    g.exec(s_t1, s_t2)
    give = var(g, "GiveUpSeconds")
    hopeless = compare(g, "GreaterEqual_FloatFloat", FLOAT)
    g.link(s_t2, "Output_Get", hopeless, "A")
    g.link(give[0], give[1], hopeless, "B")
    bg = branch_on(g, (hopeless, "ReturnValue"), (s_t2, "then"), note="stuck for GiveUpSeconds in all: respawn")
    z_a = g.var_set("StuckTotal", FLOAT, default="0.0")
    z_b = g.var_set("StuckTimer", FLOAT, default="0.0")
    g.link(bg, "then", z_a, "execute")
    z_e = g.var_set("StuckStartDistance", FLOAT, default="-1.0")
    g.exec(z_a, z_b, z_e)
    rs2 = respawn_self(g, (z_e, "then"))
    g.exec(rs2, g.function_result([Pin("bReversing", BOOL, default="false")]))
    ssec = var(g, "StuckSeconds")
    long_enough = compare(g, "GreaterEqual_FloatFloat", FLOAT)
    g.link(s_t1, "Output_Get", long_enough, "A")
    g.link(ssec[0], ssec[1], long_enough, "B")
    bl = branch_on(g, (long_enough, "ReturnValue"), (bg, "else"), note="stuck for StuckSeconds: back out")
    rsec = var(g, "ReverseSeconds")
    until = math2(g, "Add_FloatFloat", FLOAT)
    now2 = game_time(g)
    g.link(now2, "ReturnValue", until, "A")
    g.link(rsec[0], rsec[1], until, "B")
    s_ru = g.var_set("ReverseUntil", FLOAT)
    g.link(until, "ReturnValue", s_ru, "ReverseUntil")
    g.link(bl, "then", s_ru, "execute")
    z_c = g.var_set("StuckTimer", FLOAT, default="0.0")
    g.exec(s_ru, z_c)
    back2 = car_call(g, "SetAIInput", car, inputs=[Pin("Throttle", FLOAT, default="-1.0"), Pin("Steering", FLOAT), Pin("bHandbrake", BOOL, default="false")])
    inv2 = math2(g, "Multiply_FloatFloat", FLOAT, b="-1.0")
    st2 = var(g, "Steering")
    g.link(st2[0], st2[1], inv2, "A")
    g.link(inv2, "ReturnValue", back2, "Steering")
    g.exec(z_c, back2)
    g.exec(back2, g.function_result([Pin("bReversing", BOOL, default="true")]))
    g.link(bl, "else", g.function_result([Pin("bReversing", BOOL, default="false")]), "execute")
    # moving: the short timer resets; the budget (StuckTotal) is cumulative (spec §2.5) and only clears once the car has made
    # RecoverDistance of track progress, either way, since the episode began (a wedge-reverse-wedge cycle keeps counting)
    z_d = g.var_set("StuckTimer", FLOAT, default="0.0")
    g.link(bs, "else", z_d, "execute")
    ssd2 = var(g, "StuckStartDistance")
    open_ep = compare(g, "GreaterEqual_FloatFloat", FLOAT, b="0.0")
    g.link(ssd2[0], ssd2[1], open_ep, "A")
    racer_d2 = g.var_get_on(RC, "DistanceAlongTrack", FLOAT)
    g.link(g.var_get("Racer", OBJECT, cls_ref(RC)), "Racer", racer_d2, "self")
    moved = math2(g, "Subtract_FloatFloat", FLOAT)
    g.link(racer_d2, "DistanceAlongTrack", moved, "A")
    g.link(ssd2[0], ssd2[1], moved, "B")
    far = fmath(g, "Abs", [Pin("A", FLOAT)])
    g.link(moved, "ReturnValue", far, "A")
    rd = var(g, "RecoverDistance")
    enough = compare(g, "GreaterEqual_FloatFloat", FLOAT)
    g.link(far, "ReturnValue", enough, "A")
    g.link(rd[0], rd[1], enough, "B")
    recovered = and_bool(g)
    g.link(open_ep, "ReturnValue", recovered, "A")
    g.link(enough, "ReturnValue", recovered, "B")
    br = branch_on(g, (recovered, "ReturnValue"), (z_d, "then"), note="RecoverDistance of progress since the episode began: budget cleared")
    z_f = g.var_set("StuckTotal", FLOAT, default="0.0")
    z_g = g.var_set("StuckStartDistance", FLOAT, default="-1.0")
    g.link(br, "then", z_f, "execute")
    g.exec(z_f, z_g)
    g.exec(z_g, g.function_result([Pin("bReversing", BOOL, default="false")]))
    g.link(br, "else", g.function_result([Pin("bReversing", BOOL, default="false")]), "execute")

    # ---- FindTarget(Car, MinRange, MaxRange, MinDot, bBehind) -> Target ----
    g = bp.function("FindTarget", inputs=["Car:" + obj_spec(BP_VEHICLE), "MinRange:float", "MaxRange:float", "MinDot:float", "bBehind:bool"],
                    outputs=["Target:" + obj_spec(BP_VEHICLE)], locals=["Best:" + obj_spec(BP_VEHICLE), "BestDist:float=1000000000"],
                    doc="A driven car (not ours, not wrecked) inside the cone ahead (or behind) and the range band: the player's car at once when it qualifies, else the nearest.")
    car = ("entry", "Car")
    cars = get_all_actors_of_class(g, VC)
    g.link_entry("then", cars, "execute")
    pp = g.call_static(GAMEPLAY, "GetPlayerPawn", inputs=[Pin("WorldContextObject", OBJECT, hidden=True), Pin("PlayerIndex", INT, default="0")],
                       outputs=[obj_pin("ReturnValue", PAWN, "out")], pure=True)
    loop = g.for_each(Pin("e", OBJECT, sub_object=cls_ref(VC)))
    g.link(cars, "OutActors", loop, "Array")
    g.link(cars, "then", loop, "Exec")
    E = (loop, "Array Element")
    other = g.call_static(MATH, "NotEqual_ObjectObject", inputs=[obj_pin("A", "/Script/CoreUObject.Object"), obj_pin("B", "/Script/CoreUObject.Object")],
                          outputs=[Pin("ReturnValue", BOOL, "out")], pure=True)
    g.link(E[0], E[1], other, "A")
    g.link_entry("Car", other, "B")
    wrecked = g.var_get_on(VC, "bIsDestroyed", BOOL)
    g.link(E[0], E[1], wrecked, "self")
    intact = not_bool(g)
    g.link(wrecked, "bIsDestroyed", intact, "A")
    ctrl = g.call_on(PAWN, "GetController", outputs=[obj_pin("ReturnValue", CONTROLLER, "out")], pure=True)
    g.link(E[0], E[1], ctrl, "self")
    driven = is_valid(g)
    g.link(ctrl, "ReturnValue", driven, "Object")
    offset = g.call_static(MATH, "Subtract_VectorVector", inputs=[struct_pin("A", VECTOR), struct_pin("B", VECTOR)],
                           outputs=[struct_pin("ReturnValue", VECTOR, "out")], pure=True)
    eloc, cloc = car_loc(g, E), car_loc(g, car)
    g.link(eloc[0], eloc[1], offset, "A")
    g.link(cloc[0], cloc[1], offset, "B")
    unit = g.call_static(MATH, "Normal", inputs=[struct_pin("A", VECTOR), Pin("Tolerance", FLOAT, default="0.0001")],
                         outputs=[struct_pin("ReturnValue", VECTOR, "out")], pure=True)
    g.link(offset, "ReturnValue", unit, "A")
    dot = g.call_static(MATH, "Dot_VectorVector", inputs=[struct_pin("A", VECTOR), struct_pin("B", VECTOR)], outputs=[Pin("ReturnValue", FLOAT, "out")], pure=True)
    fwd = car_fwd(g, car)
    g.link(fwd[0], fwd[1], dot, "A")
    g.link(unit, "ReturnValue", dot, "B")
    dist = g.call_static(MATH, "VSize", inputs=[struct_pin("A", VECTOR)], outputs=[Pin("ReturnValue", FLOAT, "out")], pure=True)
    g.link(offset, "ReturnValue", dist, "A")
    ahead = compare(g, "GreaterEqual_FloatFloat", FLOAT)
    g.link(dot, "ReturnValue", ahead, "A")
    g.link_entry("MinDot", ahead, "B")
    neg_dot = math2(g, "Multiply_FloatFloat", FLOAT, b="-1.0")
    g.link_entry("MinDot", neg_dot, "A")
    behind = compare(g, "LessEqual_FloatFloat", FLOAT)
    g.link(dot, "ReturnValue", behind, "A")
    g.link(neg_dot, "ReturnValue", behind, "B")
    want_behind = ("entry", "bBehind")
    not_behind = not_bool(g)
    g.link_entry("bBehind", not_behind, "A")
    cone_a = and_bool(g)
    g.link(not_behind, "ReturnValue", cone_a, "A")
    g.link(ahead, "ReturnValue", cone_a, "B")
    cone_b = and_bool(g)
    g.link_entry("bBehind", cone_b, "A")
    g.link(behind, "ReturnValue", cone_b, "B")
    in_cone = or_bool(g)
    g.link(cone_a, "ReturnValue", in_cone, "A")
    g.link(cone_b, "ReturnValue", in_cone, "B")
    far_enough = compare(g, "GreaterEqual_FloatFloat", FLOAT)
    g.link(dist, "ReturnValue", far_enough, "A")
    g.link_entry("MinRange", far_enough, "B")
    near_enough = compare(g, "LessEqual_FloatFloat", FLOAT)
    g.link(dist, "ReturnValue", near_enough, "A")
    g.link_entry("MaxRange", near_enough, "B")
    conds = [other, intact, driven, in_cone, far_enough, near_enough]
    acc = conds[0]
    for c in conds[1:]:
        a = and_bool(g)
        g.link(acc, "ReturnValue", a, "A")
        g.link(c, "ReturnValue", a, "B")
        acc = a
    bok = branch_on(g, (acc, "ReturnValue"), (loop, "LoopBody"), note="another driven, intact car in the cone and the range band?")
    is_pp = g.call_static(MATH, "EqualEqual_ObjectObject", inputs=[obj_pin("A", "/Script/CoreUObject.Object"), obj_pin("B", "/Script/CoreUObject.Object")],
                          outputs=[Pin("ReturnValue", BOOL, "out")], pure=True)
    g.link(E[0], E[1], is_pp, "A")
    g.link(pp, "ReturnValue", is_pp, "B")
    prefer = var(g, "bPreferPlayer", BOOL)
    take_player = and_bool(g)
    g.link(is_pp, "ReturnValue", take_player, "A")
    g.link(prefer[0], prefer[1], take_player, "B")
    bpl = branch_on(g, (take_player, "ReturnValue"), (bok, "then"), note="the player's car: take it at once")
    r_player = g.function_result([obj_pin("Target", VC)])
    g.link(E[0], E[1], r_player, "Target")
    g.link(bpl, "then", r_player, "execute")
    bd = g.local_get("BestDist", FLOAT)
    closer = compare(g, "Less_FloatFloat", FLOAT)
    g.link(dist, "ReturnValue", closer, "A")
    g.link(bd, "BestDist", closer, "B")
    bcl = branch_on(g, (closer, "ReturnValue"), (bpl, "else"))
    s_bd = g.local_set("BestDist", FLOAT)
    g.link(dist, "ReturnValue", s_bd, "BestDist")
    g.link(bcl, "then", s_bd, "execute")
    s_best = g.local_set("Best", OBJECT, sub_object=cls_ref(VC))
    g.link(E[0], E[1], s_best, "Best")
    g.exec(s_bd, s_best)
    best = g.local_get("Best", OBJECT, cls_ref(VC))
    r_best = g.function_result([obj_pin("Target", VC)])
    g.link(best, "Best", r_best, "Target")
    g.link(loop, "Completed", r_best, "execute")

    # ---- ThinkItems(Car): the item rules of spec §3.2, first match wins ----
    g = bp.function("ThinkItems", inputs=["Car:" + obj_spec(BP_VEHICLE)], locals=["Target:" + obj_spec(BP_VEHICLE)],
                    doc="Item rules, first match wins: shield when hurt; rocket, then gun, at a car ahead (aimed); bomb for a car close behind; boost on a straight. Nothing once the race is over.")
    car = ("entry", "Car")
    racer = (g.var_get("Racer", OBJECT, cls_ref(RC)), "Racer")
    gs = get_game_state(g)
    cgs = g.cast(GSC)
    g.link(gs, "ReturnValue", cgs, "Object")
    g.link_entry("then", cgs, "execute")
    active = g.var_get_on(GSC, "bRaceActive", BOOL)
    g.link(cgs, as_pin(BP_GS), active, "self")
    wrecked = g.var_get_on(VC, "bIsDestroyed", BOOL)
    g.link_entry("Car", wrecked, "self")
    alive = not_bool(g)
    g.link(wrecked, "bIsDestroyed", alive, "A")
    go = and_bool(g)
    g.link(active, "bRaceActive", go, "A")
    g.link(alive, "ReturnValue", go, "B")
    bgo = branch_on(g, (go, "ReturnValue"), (cgs, "then"), note="race on and the car intact?")

    def has(idx):
        n = g.call_on(RC, "HasType", inputs=[enum_pin("Type", E_ITEM_TYPE, default=idx)], outputs=[Pin("ReturnValue", BOOL, "out")], pure=True)
        g.link(racer[0], racer[1], n, "self")
        return (n, "ReturnValue")

    def use(idx, prev):
        """SelectType(idx) then UseSelectedItem on the car; returns the last exec node."""
        sel = g.call_on(RC, "SelectType", inputs=[enum_pin("Type", E_ITEM_TYPE, default=idx)], outputs=[Pin("ReturnValue", BOOL, "out")])
        g.link(racer[0], racer[1], sel, "self")
        g.link(prev[0], prev[1], sel, "execute")
        u = car_call(g, "UseSelectedItem", car, outputs=[Pin("ReturnValue", BOOL, "out")])
        g.exec(sel, u)
        return u

    def find(minr, maxr, dot_src, behind):
        n = g.call_self("FindTarget", inputs=[obj_pin("Car", VC), Pin("MinRange", FLOAT, default=None if minr else "0.0"), Pin("MaxRange", FLOAT),
                                              Pin("MinDot", FLOAT, default=None if dot_src else "0.5"), Pin("bBehind", BOOL, default="true" if behind else "false")],
                        outputs=[obj_pin("Target", VC, "out")])
        g.link_entry("Car", n, "Car")
        if minr:
            g.link(minr[0], minr[1], n, "MinRange")
        g.link(maxr[0], maxr[1], n, "MaxRange")
        if dot_src:
            g.link(dot_src[0], dot_src[1], n, "MinDot")
        return n

    # 1. shield when hurt
    hp = g.var_get_on(VC, "Health", FLOAT)
    g.link_entry("Car", hp, "self")
    mhp = g.var_get_on(VC, "MaxHealth", FLOAT)
    g.link_entry("Car", mhp, "self")
    frac = var(g, "ShieldHealthFraction")
    limit = math2(g, "Multiply_FloatFloat", FLOAT)
    g.link(mhp, "MaxHealth", limit, "A")
    g.link(frac[0], frac[1], limit, "B")
    hurt = compare(g, "Less_FloatFloat", FLOAT)
    g.link(hp, "Health", hurt, "A")
    g.link(limit, "ReturnValue", hurt, "B")
    shielded = car_call(g, "IsShielded", car, outputs=[Pin("ReturnValue", BOOL, "out")], pure=True)
    unshielded = not_bool(g)
    g.link(shielded, "ReturnValue", unshielded, "A")
    s1 = and_bool(g)
    hs = has(ITEM_SHIELD)
    g.link(hs[0], hs[1], s1, "A")
    g.link(hurt, "ReturnValue", s1, "B")
    s2 = and_bool(g)
    g.link(s1, "ReturnValue", s2, "A")
    g.link(unshielded, "ReturnValue", s2, "B")
    b1 = branch_on(g, (s2, "ReturnValue"), (bgo, "then"), note="shield: hurt, holding one, none running")
    use(ITEM_SHIELD, (b1, "then"))
    # 2. rocket at a car ahead, beyond the blast radius
    hr = has(ITEM_RPG)
    b2 = branch_on(g, hr, (b1, "else"), note="rocket: a car ahead between RPGMinRange and RPGRange?")
    f2 = find(var(g, "RPGMinRange"), var(g, "RPGRange"), var(g, "AimCone"), False)
    g.link(b2, "then", f2, "execute")
    t2 = g.local_set("Target", OBJECT, sub_object=cls_ref(VC))
    g.link(f2, "Target", t2, "Target")
    g.exec(f2, t2)
    v2 = is_valid(g)
    g.link(t2, "Output_Get", v2, "Object")
    bt2 = branch_on(g, (v2, "ReturnValue"), (t2, "then"))
    aim2 = g.var_set_on(VC, "AimTarget", OBJECT, sub_object=cls_ref(ACTOR))
    g.link_entry("Car", aim2, "self")
    g.link(t2, "Output_Get", aim2, "AimTarget")
    g.link(bt2, "then", aim2, "execute")
    u2 = use(ITEM_RPG, (aim2, "then"))
    clear2 = g.var_set_on(VC, "AimTarget", OBJECT, sub_object=cls_ref(ACTOR))
    g.link_entry("Car", clear2, "self")
    g.exec(u2, clear2)
    # 3. gun at a car ahead
    hg = has(ITEM_GUN)
    b3 = branch_on(g, hg, note="gun: a car ahead within GunRange?")
    g.link(b2, "else", b3, "execute")
    g.link(bt2, "else", b3, "execute")
    f3 = find(None, var(g, "GunRange"), var(g, "AimCone"), False)
    g.link(b3, "then", f3, "execute")
    t3 = g.local_set("Target", OBJECT, sub_object=cls_ref(VC))
    g.link(f3, "Target", t3, "Target")
    g.exec(f3, t3)
    v3 = is_valid(g)
    g.link(t3, "Output_Get", v3, "Object")
    bt3 = branch_on(g, (v3, "ReturnValue"), (t3, "then"))
    aim3 = g.var_set_on(VC, "AimTarget", OBJECT, sub_object=cls_ref(ACTOR))
    g.link_entry("Car", aim3, "self")
    g.link(t3, "Output_Get", aim3, "AimTarget")
    g.link(bt3, "then", aim3, "execute")
    u3 = use(ITEM_GUN, (aim3, "then"))
    clear3 = g.var_set_on(VC, "AimTarget", OBJECT, sub_object=cls_ref(ACTOR))
    g.link_entry("Car", clear3, "self")
    g.exec(u3, clear3)
    # 4. bomb for a car close behind
    hb = has(ITEM_BOMB)
    b4 = branch_on(g, hb, note="bomb: a car close behind?")
    g.link(b3, "else", b4, "execute")
    g.link(bt3, "else", b4, "execute")
    f4 = find(None, var(g, "BombRange"), None, True)
    g.link(b4, "then", f4, "execute")
    v4 = is_valid(g)
    g.link(f4, "Target", v4, "Object")
    bt4 = branch_on(g, (v4, "ReturnValue"), (f4, "then"))
    use(ITEM_BOMB, (bt4, "then"))
    # 5. boost on a straight, below the target speed, none running
    hbo = has(ITEM_BOOST)
    sev = var(g, "LastSeverity")
    straight = compare(g, "Less_FloatFloat", FLOAT)
    g.link(sev[0], sev[1], straight, "A")
    bms = var(g, "BoostMaxSeverity")
    g.link(bms[0], bms[1], straight, "B")
    tsp = g.call_self("ComputeTargetSpeed", inputs=[Pin("Severity", FLOAT)], outputs=[Pin("KPH", FLOAT, "out")], pure=True)
    g.link(sev[0], sev[1], tsp, "Severity")
    kph = car_kph(g, car)
    slow = compare(g, "Less_FloatFloat", FLOAT)
    g.link(kph[0], kph[1], slow, "A")
    g.link(tsp, "KPH", slow, "B")
    brem = g.var_get_on(VC, "BoostRemaining", FLOAT)
    g.link_entry("Car", brem, "self")
    idle = compare(g, "LessEqual_FloatFloat", FLOAT, b="0.0")
    g.link(brem, "BoostRemaining", idle, "A")
    acc = hbo
    for c in (straight, slow, idle):
        a = and_bool(g)
        g.link(acc[0], acc[1], a, "A")
        g.link(c, "ReturnValue", a, "B")
        acc = (a, "ReturnValue")
    b5 = branch_on(g, acc, note="boost: a straight ahead, under the target speed, none running")
    g.link(b4, "else", b5, "execute")
    g.link(bt4, "else", b5, "execute")
    use(ITEM_BOOST, (b5, "then"))

    # ---- event graph ----
    g = bp.event_graph()
    g.section("Possess: take the wheel of the car")
    ev = g.event(CONTROLLER, "ReceivePossess", [obj_pin("PossessedPawn", PAWN)])
    cast = cast_to(g, BP_VEHICLE)
    g.link(ev, "PossessedPawn", cast, "Object")
    g.exec(ev, cast)
    Vp = (cast, as_pin(BP_VEHICLE))
    set_cv = g.var_set("CurrentVehicle", OBJECT, sub_object=cls_ref(VC))
    g.link(Vp[0], Vp[1], set_cv, "CurrentVehicle")
    g.link(cast, "then", set_cv, "execute")
    set_ai = g.var_set_on(VC, "bAIControlled", BOOL, default="true")
    g.link(Vp[0], Vp[1], set_ai, "self")
    g.exec(set_cv, set_ai)
    set_ld = g.var_set_on(VC, "LastDriver", OBJECT, sub_object=cls_ref(CONTROLLER))
    g.link(Vp[0], Vp[1], set_ld, "self")
    me = g.self_node()
    g.link(me, "self", set_ld, "LastDriver")
    g.exec(set_ai, set_ld)
    z_np = g.var_set("NoPawnTimer", FLOAT, default="0.0")
    g.exec(set_ld, z_np)

    g.section("UnPossess: hand the car back, parked")
    uv = g.event(CONTROLLER, "ReceiveUnPossess", [obj_pin("UnpossessedPawn", PAWN)])
    cast2 = cast_to(g, BP_VEHICLE)
    g.link(uv, "UnpossessedPawn", cast2, "Object")
    g.exec(uv, cast2)
    V2 = (cast2, as_pin(BP_VEHICLE))
    parked = park(g, V2)
    g.link(cast2, "then", parked, "execute")
    off = g.var_set_on(VC, "bAIControlled", BOOL, default="false")
    g.link(V2[0], V2[1], off, "self")
    g.exec(parked, off)
    clear = g.var_set("CurrentVehicle", OBJECT, sub_object=cls_ref(VC))
    g.exec(off, clear)
    g.link(cast2, "CastFailed", clear, "execute")

    g.section("Tick: drive while the race runs; park when it is over; ask for a car when there is none")
    tk = g.tick()
    gs = get_game_state(g)
    cgs = g.cast(GSC)
    g.link(gs, "ReturnValue", cgs, "Object")
    g.exec(tk, cgs)
    active = g.var_get_on(GSC, "bRaceActive", BOOL)
    g.link(cgs, as_pin(BP_GS), active, "self")
    cv = g.var_get("CurrentVehicle", OBJECT, cls_ref(VC))
    car_ok = is_valid(g)
    g.link(cv, "CurrentVehicle", car_ok, "Object")
    CAR = (cv, "CurrentVehicle")
    bact = branch_on(g, (active, "bRaceActive"), (cgs, "then"), note="is the race on?")
    bcar = branch_on(g, (car_ok, "ReturnValue"), (bact, "then"), note="a car to drive?")
    # no car (the player took it, or it was removed): ask the GameMode for one after NoPawnSeconds
    npt = var(g, "NoPawnTimer")
    inc = math2(g, "Add_FloatFloat", FLOAT)
    g.link(npt[0], npt[1], inc, "A")
    g.link(tk, "DeltaSeconds", inc, "B")
    s_np = g.var_set("NoPawnTimer", FLOAT)
    g.link(inc, "ReturnValue", s_np, "NoPawnTimer")
    g.link(bcar, "else", s_np, "execute")
    nps = var(g, "NoPawnSeconds")
    np_due = compare(g, "GreaterEqual_FloatFloat", FLOAT)
    g.link(s_np, "Output_Get", np_due, "A")
    g.link(nps[0], nps[1], np_due, "B")
    bnp = branch_on(g, (np_due, "ReturnValue"), (s_np, "then"))
    z_np2 = g.var_set("NoPawnTimer", FLOAT, default="0.0")
    g.link(bnp, "then", z_np2, "execute")
    respawn_self(g, (z_np2, "then"))
    # a wreck waits for the GameMode's respawn
    wrecked = g.var_get_on(VC, "bIsDestroyed", BOOL)
    g.link(CAR[0], CAR[1], wrecked, "self")
    bw = branch_on(g, (wrecked, "bIsDestroyed"), (bcar, "then"), note="wrecked? then wait for the respawn")
    auto = g.var_get("bAutoDrive", BOOL)
    bauto = branch_on(g, (auto, "bAutoDrive"), (bw, "else"), note="driving switched on?")
    flip = g.call_self("UpdateFlip", inputs=[obj_pin("Car", VC), Pin("DeltaSeconds", FLOAT)], outputs=[Pin("bRespawned", BOOL, "out")])
    g.link(CAR[0], CAR[1], flip, "Car")
    g.link(tk, "DeltaSeconds", flip, "DeltaSeconds")
    g.link(bauto, "then", flip, "execute")
    bf = branch_on(g, (flip, "bRespawned"), (flip, "then"))
    stuck = g.call_self("UpdateStuck", inputs=[obj_pin("Car", VC), Pin("DeltaSeconds", FLOAT)], outputs=[Pin("bReversing", BOOL, "out")])
    g.link(CAR[0], CAR[1], stuck, "Car")
    g.link(tk, "DeltaSeconds", stuck, "DeltaSeconds")
    g.link(bf, "else", stuck, "execute")
    bst = branch_on(g, (stuck, "bReversing"), (stuck, "then"))
    drive = g.call_self("Drive", inputs=[obj_pin("Car", VC), Pin("DeltaSeconds", FLOAT)])
    g.link(CAR[0], CAR[1], drive, "Car")
    g.link(tk, "DeltaSeconds", drive, "DeltaSeconds")
    g.link(bst, "else", drive, "execute")
    # items every ItemThinkInterval
    use_items = var(g, "bUseItems", BOOL)
    ntt = var(g, "NextThinkTime")
    now_t = game_time(g)
    think_due = compare(g, "GreaterEqual_FloatFloat", FLOAT)
    g.link(now_t, "ReturnValue", think_due, "A")
    g.link(ntt[0], ntt[1], think_due, "B")
    think_go = and_bool(g)
    g.link(use_items[0], use_items[1], think_go, "A")
    g.link(think_due, "ReturnValue", think_go, "B")
    bthink = branch_on(g, (think_go, "ReturnValue"), (drive, "then"), note="time to think about items?")
    think = g.call_self("ThinkItems", inputs=[obj_pin("Car", VC)])
    g.link(CAR[0], CAR[1], think, "Car")
    g.link(bthink, "then", think, "execute")
    interval = var(g, "ItemThinkInterval")
    next_t = math2(g, "Add_FloatFloat", FLOAT)
    g.link(now_t, "ReturnValue", next_t, "A")
    g.link(interval[0], interval[1], next_t, "B")
    s_ntt = g.var_set("NextThinkTime", FLOAT)
    g.link(next_t, "ReturnValue", s_ntt, "NextThinkTime")
    g.exec(think, s_ntt)
    # race over: park
    bpark = branch_on(g, (car_ok, "ReturnValue"), (bact, "else"))
    stop = park(g, CAR)
    g.link(bpark, "then", stop, "execute")
    return bp


if __name__ == "__main__":
    print(build().write(OUT))
