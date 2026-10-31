"""BPC_DFWeapon (plan Task 4): hitscan weapon component (damage, range, cooldown, Fire(Origin, Direction)).
Phase 7 Task 16 (spec §7.2): every shot shows a muzzle flash and a tracer from where it is seen to start (VisualOrigin's
Muzzle socket), an impact (sparks on a car, dust elsewhere) and plays its fire and impact sounds.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from df import (ACTOR, BOOL, BPC_WEAPON, CONTROLLER, DAMAGE_TYPE, FLOAT, GAMEPLAY, HIT_RESULT, MATH, OBJECT, OUT, SCENE_COMP,  # noqa: E402
                SYS, VECTOR, Blueprint, Pin, cls_ref, compare, game_time, math2, not_bool, obj_pin, struct_pin)
from df import (BP_FX, BP_FX_TRACER, BP_VEHICLE, NAME, ROTATOR, SOUND_BASE, STRUCT, TRANSFORM, Graph, cast_to, gen,  # noqa: E402
                is_valid, play_sound_at, spawn_fx, weapon_look)  # Phase 7 Task 16
from bpgen import struct_ref  # noqa: E402

LOOK = "Dead Fire|Weapon|Look"


def play_at(g: Graph, sound_var: str, loc_src):
    """PlaySoundAtLocation(<sound_var>, loc) (impure; link execute); a null sound plays nothing."""
    return play_sound_at(g, (g.var_get(sound_var, OBJECT, cls_ref(SOUND_BASE)), sound_var), loc_src)


def transform_at(g: Graph, loc_src, rot_src):
    n = g.call_static(MATH, "MakeTransform", inputs=[struct_pin("Location", VECTOR), struct_pin("Rotation", ROTATOR),
                                                       struct_pin("Scale", VECTOR, default="1,1,1")],
                      outputs=[struct_pin("ReturnValue", TRANSFORM, "out")], pure=True)
    g.link(loc_src[0], loc_src[1], n, "Location")
    g.link(rot_src[0], rot_src[1], n, "Rotation")
    return (n, "ReturnValue")


def add_visual_start(bp: Blueprint) -> None:
    """GetVisualStart(Origin) -> Start: where a shot is seen to start (Task 14's VisualOrigin is set only at the owner's
    BeginPlay, so each step falls back)."""
    g = bp.function("GetVisualStart", doc="Where a shot is seen to start: VisualOrigin's Muzzle socket, else VisualOrigin, else Origin.",
                    inputs=["Origin:struct:" + VECTOR], outputs=["Start:struct:" + VECTOR], pure=True)

    def origin():
        return (g.var_get("VisualOrigin", OBJECT, cls_ref(SCENE_COMP)), "VisualOrigin")

    ok = is_valid(g)
    g.link(*origin(), ok, "Object")
    b = g.branch()
    g.note(b, "a visual origin set?")
    g.link(ok, "ReturnValue", b, "Condition")
    g.link_entry("then", b, "execute")
    r_origin = g.function_result([struct_pin("Start", VECTOR)])
    g.link_entry("Origin", r_origin, "Start")
    g.link(b, "else", r_origin, "execute")
    has = g.call_on(SCENE_COMP, "DoesSocketExist", inputs=[Pin("InSocketName", NAME, default="Muzzle")],
                    outputs=[Pin("ReturnValue", BOOL, "out")], pure=True)
    g.link(*origin(), has, "self")
    bs = g.branch()
    g.note(bs, "does it have a Muzzle socket?")
    g.link(has, "ReturnValue", bs, "Condition")
    g.link(b, "then", bs, "execute")
    sock = g.call_on(SCENE_COMP, "GetSocketLocation", inputs=[Pin("InSocketName", NAME, default="Muzzle")],
                     outputs=[struct_pin("ReturnValue", VECTOR, "out")], pure=True)
    g.link(*origin(), sock, "self")
    r_sock = g.function_result([struct_pin("Start", VECTOR)])
    g.link(sock, "ReturnValue", r_sock, "Start")
    g.link(bs, "then", r_sock, "execute")
    at = g.call_on(SCENE_COMP, "K2_GetComponentLocation", outputs=[struct_pin("ReturnValue", VECTOR, "out")], pure=True)
    g.link(*origin(), at, "self")
    r_at = g.function_result([struct_pin("Start", VECTOR)])
    g.link(at, "ReturnValue", r_at, "Start")
    g.link(bs, "else", r_at, "execute")


def add_shot_effects(bp: Blueprint) -> None:
    """PlayShotEffects(Origin, Direction, bHit, Hit): the muzzle flash and the tracer from the visual start to the hit point
    (or Origin + Direction x Range on a miss), the fire sound there; on a hit the impact (BP_DFFxSparks on a car, +X along
    the surface normal) and its sound. Effects go through df.spawn_fx (the class from the weapon's variables)."""
    g = bp.function("PlayShotEffects", inputs=["Origin:struct:" + VECTOR, "Direction:struct:" + VECTOR, "bHit:bool", "Hit:struct:" + HIT_RESULT],
                    locals=["Start:struct:" + VECTOR, "End:struct:" + VECTOR],
                    doc="The shot as seen and heard: muzzle flash and tracer from the visual start (GetVisualStart) to the hit point, "
                        "or Origin + Direction x Range on a miss, with FireSound; on a hit the impact (VehicleImpactFxClass and "
                        "VehicleImpactSound on a car, else ImpactFxClass and ImpactSound), its +X along the surface normal.")
    start_at = g.call_self("GetVisualStart", inputs=[struct_pin("Origin", VECTOR)], outputs=[struct_pin("Start", VECTOR, "out")], pure=True)
    g.link_entry("Origin", start_at, "Origin")
    s_start = g.local_set("Start", STRUCT, sub_object=struct_ref(VECTOR))
    g.link(start_at, "Start", s_start, "Start")
    g.link_entry("then", s_start, "execute")
    brk = g.call_static(GAMEPLAY, "BreakHitResult", inputs=[struct_pin("Hit", HIT_RESULT)],
                        outputs=[struct_pin("ImpactPoint", VECTOR, "out"), struct_pin("ImpactNormal", VECTOR, "out"),
                                 obj_pin("HitActor", ACTOR, "out")], pure=True)
    g.link_entry("Hit", brk, "Hit")
    reach = g.call_static(MATH, "Multiply_VectorFloat", inputs=[struct_pin("A", VECTOR), Pin("B", FLOAT)],
                          outputs=[struct_pin("ReturnValue", VECTOR, "out")], pure=True)
    g.link_entry("Direction", reach, "A")
    g.link(g.var_get("Range", FLOAT), "Range", reach, "B")
    miss = g.call_static(MATH, "Add_VectorVector", inputs=[struct_pin("A", VECTOR), struct_pin("B", VECTOR)],
                         outputs=[struct_pin("ReturnValue", VECTOR, "out")], pure=True)
    g.link_entry("Origin", miss, "A")
    g.link(reach, "ReturnValue", miss, "B")
    pick = g.call_static(MATH, "SelectVector", inputs=[struct_pin("A", VECTOR), struct_pin("B", VECTOR), Pin("bPickA", BOOL)],
                         outputs=[struct_pin("ReturnValue", VECTOR, "out")], pure=True)
    g.link(brk, "ImpactPoint", pick, "A")
    g.link(miss, "ReturnValue", pick, "B")
    g.link_entry("bHit", pick, "bPickA")
    s_end = g.local_set("End", STRUCT, sub_object=struct_ref(VECTOR))
    g.link(pick, "ReturnValue", s_end, "End")
    g.exec(s_start, s_end)

    def start():
        return (g.local_get("Start", STRUCT, struct_ref(VECTOR)), "Start")

    def end():
        return (g.local_get("End", STRUCT, struct_ref(VECTOR)), "End")

    def fx_class(name, cls):
        return (g.var_get(name, "class", cls_ref(cls)), name)

    aim = g.call_static(MATH, "FindLookAtRotation", inputs=[struct_pin("Start", VECTOR), struct_pin("Target", VECTOR)],
                        outputs=[struct_pin("ReturnValue", ROTATOR, "out")], pure=True)
    g.link(*start(), aim, "Start")
    g.link(*end(), aim, "Target")
    at_muzzle = transform_at(g, start(), (aim, "ReturnValue"))
    first, last, _ = spawn_fx(g, BP_FX, at_muzzle, class_src=fx_class("MuzzleFxClass", gen(BP_FX)))
    g.exec(s_end, first)
    t_first, t_last, tracer = spawn_fx(g, BP_FX_TRACER, at_muzzle, class_src=fx_class("TracerFxClass", gen(BP_FX_TRACER)))
    g.exec(last, t_first)
    ends = g.call_on(gen(BP_FX_TRACER), "SetEnds", inputs=[struct_pin("Start", VECTOR), struct_pin("End", VECTOR)])
    g.link(tracer[0], tracer[1], ends, "self")
    g.link(*start(), ends, "Start")
    g.link(*end(), ends, "End")
    g.exec(t_last, ends)
    fire = play_at(g, "FireSound", start())
    g.exec(ends, fire)
    bh = g.branch()
    g.note(bh, "did the shot hit something?")
    g.link_entry("bHit", bh, "Condition")
    g.exec(fire, bh)
    car = cast_to(g, BP_VEHICLE)
    g.note(car, "a car? sparks and metal")
    g.link(brk, "HitActor", car, "Object")
    g.link(bh, "then", car, "execute")
    normal = g.call_static(MATH, "MakeRotFromX", inputs=[struct_pin("X", VECTOR)], outputs=[struct_pin("ReturnValue", ROTATOR, "out")], pure=True)
    g.link(brk, "ImpactNormal", normal, "X")
    at_hit = transform_at(g, (brk, "ImpactPoint"), (normal, "ReturnValue"))
    for exec_pin, fx_var, sound_var in (("then", "VehicleImpactFxClass", "VehicleImpactSound"), ("CastFailed", "ImpactFxClass", "ImpactSound")):
        i_first, i_last, _ = spawn_fx(g, BP_FX, at_hit, class_src=fx_class(fx_var, gen(BP_FX)))
        g.link(car, exec_pin, i_first, "execute")
        g.exec(i_last, play_at(g, sound_var, (brk, "ImpactPoint")))


def build() -> Blueprint:
    bp = Blueprint(BPC_WEAPON, parent="/Script/Engine.ActorComponent", description="Hitscan weapon component: damage, range, cooldown.")
    W = "Dead Fire|Weapon"
    bp.variable("Damage", "float", "20", W, editable=True)
    bp.variable("Range", "float", "8000", W, editable=True)
    bp.variable("Cooldown", "float", "0.15", W, editable=True)
    bp.variable("bDebugTrace", "bool", "false", W, editable=True)
    bp.default("bDebugTrace", False)  # Phase 7 (spec §6.2): off; a declared default reaches an existing asset only through the CDO
    bp.variable("DamageTypeClass", "class:" + DAMAGE_TYPE, DAMAGE_TYPE, W, editable=True)
    bp.variable("LastFireTime", "float", "-1", W)
    # Phase 7 Task 14 (spec §7.2): the component the shots are seen to leave from (its Muzzle socket if it has one); the
    # owner sets it at BeginPlay (the character's Rifle; the car's RoofWeapon in Task 16), and Task 16 draws the tracer from it
    bp.variable("VisualOrigin", "object:" + SCENE_COMP, "", W)
    # Phase 7 Task 16 (spec §7.2): what every shot shows and sounds like (each owner also sets them on its Weapon template:
    # df.weapon_look); FireSound has no class default, each owner names its own (the car's gun, the character's rifle)
    for name, cls in (("MuzzleFxClass", BP_FX), ("TracerFxClass", BP_FX_TRACER), ("ImpactFxClass", BP_FX), ("VehicleImpactFxClass", BP_FX)):
        bp.variable(name, "class:" + gen(cls), "", LOOK, editable=True)
    for name in ("FireSound", "ImpactSound", "VehicleImpactSound"):
        bp.variable(name, "object:" + SOUND_BASE, "", LOOK, editable=True)
    for name, value in weapon_look(None).items():
        if value:
            bp.default(name, value)
    bp.dispatcher("OnFired", ["Hit:struct:" + HIT_RESULT, "bHit:bool"])

    # CanFire: now - LastFireTime >= Cooldown
    g = bp.function("CanFire", doc="The cooldown has passed.", outputs=["ReturnValue:bool"], pure=True)
    now = game_time(g)
    last = g.var_get("LastFireTime", FLOAT)
    sub = math2(g, "Subtract_FloatFloat", FLOAT)
    g.link(now, "ReturnValue", sub, "A")
    g.link(last, "LastFireTime", sub, "B")
    cd = g.var_get("Cooldown", FLOAT)
    ge = compare(g, "GreaterEqual_FloatFloat", FLOAT)
    g.link(sub, "ReturnValue", ge, "A")
    g.link(cd, "Cooldown", ge, "B")
    g.link_result(ge, "ReturnValue", "ReturnValue")
    g.link_entry("then", "result", "execute")

    # Fire(Origin, Direction) -> bHit, Hit
    # Fire(Origin, Direction, Instigator) -> bHit, Hit: the caller names the controller credited for the damage (Phase 3:
    # the character passes its controller, the vehicle its driver's)
    g = bp.function("Fire", doc="A hitscan shot: trace, its effects and sounds (PlayShotEffects), point damage credited to Instigator, OnFired.", inputs=["Origin:struct:" + VECTOR, "Direction:struct:" + VECTOR, "Instigator:object:" + CONTROLLER],
                    outputs=["bHit:bool", "Hit:struct:" + HIT_RESULT])
    can = g.call_self("CanFire", outputs=[Pin("ReturnValue", BOOL, "out")], pure=True)
    b = g.branch()
    g.link(can, "ReturnValue", b, "Condition")
    g.link_entry("then", b, "execute")
    r_no = g.function_result([Pin("bHit", BOOL, default="false"), struct_pin("Hit", HIT_RESULT)])
    g.link(b, "else", r_no, "execute")
    rng = g.var_get("Range", FLOAT)
    dirv = g.call_static(MATH, "Multiply_VectorFloat", inputs=[struct_pin("A", VECTOR), Pin("B", FLOAT)],
                         outputs=[struct_pin("ReturnValue", VECTOR, "out")], pure=True)
    g.link_entry("Direction", dirv, "A")
    g.link(rng, "Range", dirv, "B")
    end = g.call_static(MATH, "Add_VectorVector", inputs=[struct_pin("A", VECTOR), struct_pin("B", VECTOR)],
                        outputs=[struct_pin("ReturnValue", VECTOR, "out")], pure=True)
    g.link_entry("Origin", end, "A")
    g.link(dirv, "ReturnValue", end, "B")
    trace = g.call_static(SYS, "LineTraceSingle",
                          inputs=[Pin("WorldContextObject", OBJECT, hidden=True), struct_pin("Start", VECTOR),
                                  struct_pin("End", VECTOR), Pin("TraceChannel", "byte", default="TraceTypeQuery1"),
                                  Pin("bTraceComplex", BOOL, default="false"), Pin("DrawDebugType", "byte", default="None"),
                                  Pin("bIgnoreSelf", BOOL, default="true")],
                          outputs=[struct_pin("OutHit", HIT_RESULT, "out"), Pin("ReturnValue", BOOL, "out")])
    g.link_entry("Origin", trace, "Start")
    g.link(end, "ReturnValue", trace, "End")
    g.link(b, "then", trace, "execute")
    stamp = g.var_set("LastFireTime", FLOAT)
    now = game_time(g)
    g.link(now, "ReturnValue", stamp, "LastFireTime")
    g.exec(trace, stamp)
    # Phase 7 Task 16: the shot as seen and heard, right after the trace (before the damage, which may wreck the target)
    shown = g.call_self("PlayShotEffects", inputs=[struct_pin("Origin", VECTOR), struct_pin("Direction", VECTOR), Pin("bHit", BOOL),
                                                   struct_pin("Hit", HIT_RESULT)])
    g.link_entry("Origin", shown, "Origin")
    g.link_entry("Direction", shown, "Direction")
    g.link(trace, "ReturnValue", shown, "bHit")
    g.link(trace, "OutHit", shown, "Hit")
    bh = g.branch()
    g.link(trace, "ReturnValue", bh, "Condition")
    g.exec(stamp, shown, bh)
    brk = g.call_static(GAMEPLAY, "BreakHitResult", inputs=[struct_pin("Hit", HIT_RESULT)],
                        outputs=[obj_pin("HitActor", ACTOR, "out")], pure=True)
    g.link(trace, "OutHit", brk, "Hit")
    dmg = g.var_get("Damage", FLOAT)
    dtc = g.var_get("DamageTypeClass", "class", cls_ref(DAMAGE_TYPE))
    apply = g.call_static(GAMEPLAY, "ApplyPointDamage",
                          inputs=[obj_pin("DamagedActor", ACTOR), Pin("BaseDamage", FLOAT), struct_pin("HitFromDirection", VECTOR),
                                  struct_pin("HitInfo", HIT_RESULT), obj_pin("EventInstigator", CONTROLLER),
                                  obj_pin("DamageCauser", ACTOR), Pin("DamageTypeClass", "class", sub_object=cls_ref(DAMAGE_TYPE))],
                          outputs=[Pin("ReturnValue", FLOAT, "out")])
    g.link(brk, "HitActor", apply, "DamagedActor")
    g.link(dmg, "Damage", apply, "BaseDamage")
    g.link_entry("Direction", apply, "HitFromDirection")
    g.link(trace, "OutHit", apply, "HitInfo")
    g.link_entry("Instigator", apply, "EventInstigator")
    owner2 = g.call_self_native("/Script/Engine.ActorComponent", "GetOwner", outputs=[obj_pin("ReturnValue", ACTOR, "out")], pure=True)
    g.link(owner2, "ReturnValue", apply, "DamageCauser")
    g.link(dtc, "DamageTypeClass", apply, "DamageTypeClass")
    g.link(bh, "then", apply, "execute")
    fire = g.call_delegate("OnFired", [struct_pin("Hit", HIT_RESULT), Pin("bHit", BOOL)])
    g.link(trace, "OutHit", fire, "Hit")
    g.link(trace, "ReturnValue", fire, "bHit")
    g.exec(apply, fire)
    g.link(bh, "else", fire, "execute")
    r = g.function_result([Pin("bHit", BOOL), struct_pin("Hit", HIT_RESULT)])
    g.link(trace, "ReturnValue", r, "bHit")
    g.link(trace, "OutHit", r, "Hit")
    g.exec(fire, r)
    add_visual_start(bp)
    add_shot_effects(bp)
    return bp


if __name__ == "__main__":
    print(build().write(OUT))
