"""BPC_DFWeapon (plan Task 4): hitscan weapon component (damage, range, cooldown, Fire(Origin, Direction))."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from df import (ACTOR, BOOL, BPC_WEAPON, CONTROLLER, DAMAGE_TYPE, FLOAT, GAMEPLAY, HIT_RESULT, MATH, OBJECT, OUT, SYS,  # noqa: E402
                VECTOR, Blueprint, Pin, cls_ref, compare, game_time, math2, not_bool, obj_pin, struct_pin)


def build() -> Blueprint:
    bp = Blueprint(BPC_WEAPON, parent="/Script/Engine.ActorComponent")
    W = "Dead Fire|Weapon"
    bp.variable("Damage", "float", "20", W, editable=True)
    bp.variable("Range", "float", "8000", W, editable=True)
    bp.variable("Cooldown", "float", "0.15", W, editable=True)
    bp.variable("bDebugTrace", "bool", "true", W, editable=True)
    bp.variable("DamageTypeClass", "class:" + DAMAGE_TYPE, DAMAGE_TYPE, W, editable=True)
    bp.variable("LastFireTime", "float", "-1", W)
    bp.dispatcher("OnFired", ["Hit:struct:" + HIT_RESULT, "bHit:bool"])

    # CanFire: now - LastFireTime >= Cooldown
    g = bp.function("CanFire", outputs=["ReturnValue:bool"], pure=True)
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
    g = bp.function("Fire", inputs=["Origin:struct:" + VECTOR, "Direction:struct:" + VECTOR, "Instigator:object:" + CONTROLLER],
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
    bh = g.branch()
    g.link(trace, "ReturnValue", bh, "Condition")
    g.exec(stamp, bh)
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
    return bp


if __name__ == "__main__":
    print(build().write(OUT))
