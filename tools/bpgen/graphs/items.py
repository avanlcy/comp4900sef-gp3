"""Phase 3 item actors (spec docs/superpowers/specs/2026-10-30-phase3-items-design.md §5-§6):
BP_DFExplosiveDamage (the damage type explosions use; Task 1), BP_DFBomb (Task 3), BP_DFProjectile (Task 4),
BP_DFLootBox (Task 5), BP_DFDestructible (Task 6). The vehicle spawns bombs and rockets; the GameMode owns the
explosion rule (SpawnExplosion) that all of them call.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from df import *  # noqa: E402,F401,F403
from df import (ACTOR, BOOL, BP_BOMB, BP_CHARACTER, BP_DESTRUCTIBLE, BP_EXPLOSIVE_DAMAGE, BP_GM, BP_LOOTBOX, BP_PROJECTILE,  # noqa: E402
                BP_VEHICLE, CONTROLLER, DAMAGE_TYPE, E_ITEM_TYPE, FLOAT, GAMEPLAY, HIT_RESULT, INT, ITEM_BOMB, ITEM_BOOST,
                ITEM_GUN, ITEM_RPG, ITEM_SHIELD, MATH, OBJECT, OUT, PRIMITIVE, SPHERE_COMP, STATIC_MESH_COMP, STRING, SYS,
                VECTOR, Blueprint, Graph, Node, Pin, and_bool, as_pin, cast_to, cls_ref, compare, enum_pin, enum_spec,
                enum_value, game_time, gen, get_game_mode, is_valid, log_line, math2, name_of, not_bool, obj_pin, obj_spec,
                self_actor_location, struct_pin, vec_str)

GMC, VC, CC = gen(BP_GM), gen(BP_VEHICLE), gen(BP_CHARACTER)
ITEM_ENUM = enum_pin("x", E_ITEM_TYPE).sub_object
SHAPES = "/Game/StarterContent/Shapes"
MATERIALS = "/Game/VehicleAdv/Materials/MaterialInstances"  # already committed; keeps the Starter Content closure small


def build_explosive_damage() -> Blueprint:
    """A DamageType child with no logic: explosions apply it, the on-foot character ignores it, the destructible
    rock only accepts it (spec §5, §6)."""
    return Blueprint(BP_EXPLOSIVE_DAMAGE, parent=DAMAGE_TYPE)


# ---- shared recipes ----
def add_vec(g: Graph, a_src, x=0.0, y=0.0, z=0.0) -> Node:
    """a + (x, y, z)."""
    n = g.call_static(MATH, "Add_VectorVector", inputs=[struct_pin("A", VECTOR), struct_pin("B", VECTOR, default="%f,%f,%f" % (x, y, z))],
                      outputs=[struct_pin("ReturnValue", VECTOR, "out")], pure=True)
    g.link(a_src[0], a_src[1], n, "A")
    return n


def age_since(g: Graph, var: str) -> Node:
    """GetTimeSeconds - <var> (pure)."""
    now = game_time(g)
    then = g.var_get(var, FLOAT)
    sub = math2(g, "Subtract_FloatFloat", FLOAT)
    g.link(now, "ReturnValue", sub, "A")
    g.link(then, var, sub, "B")
    return sub


def explode_here(g: Graph, prev, damage_var: str, radius_var: str, blow_tires: str = "true", what: str = "item") -> Node:
    """Log, then GameMode.SpawnExplosion(my location, <damage_var>, <radius_var>, InstigatorController, self, blow_tires),
    then DestroyActor. prev = (node, exec pin). Returns the destroy node."""
    loc = self_actor_location(g)
    log = log_line(g, what, " exploded at ", vec_str(g, (loc, "ReturnValue")))
    g.link(prev[0], prev[1], log, "execute")
    gm = get_game_mode(g)
    cast = cast_to(g, BP_GM)
    g.link(gm, "ReturnValue", cast, "Object")
    g.exec(log, cast)
    boom = g.call_on(GMC, "SpawnExplosion", inputs=[struct_pin("Location", VECTOR), Pin("Damage", FLOAT), Pin("Radius", FLOAT),
                                                    obj_pin("InstigatedBy", CONTROLLER), obj_pin("Causer", ACTOR),
                                                    Pin("bBlowTires", BOOL, default=blow_tires)])
    g.link(cast, as_pin(BP_GM), boom, "self")
    g.link(loc, "ReturnValue", boom, "Location")
    dmg = g.var_get(damage_var, FLOAT)
    g.link(dmg, damage_var, boom, "Damage")
    rad = g.var_get(radius_var, FLOAT)
    g.link(rad, radius_var, boom, "Radius")
    who = g.var_get("InstigatorController", OBJECT, cls_ref(CONTROLLER))
    g.link(who, "InstigatorController", boom, "InstigatedBy")
    me = g.self_node()
    g.link(me, "self", boom, "Causer")
    g.link(cast, "then", boom, "execute")
    kill = g.call_self_native(ACTOR, "K2_DestroyActor")
    g.exec(boom, kill)
    g.link(cast, "CastFailed", kill, "execute")
    return kill


# ---- BP_DFBomb (spec §6) ----
def build_bomb() -> Blueprint:
    bp = Blueprint(BP_BOMB, parent=ACTOR)
    bp.component("Shell", STATIC_MESH_COMP, **{"static_mesh": SHAPES + "/Shape_Sphere", "relative_scale3d": {"vector": [0.5, 0.5, 0.5]},
                                             "call:set_collision_profile_name": "OverlapOnlyPawn",
                                             "override_materials": [MATERIALS + "/SolidRed"]})
    B = "Dead Fire|Bomb"
    bp.variable("ArmDelay", "float", "1", B, editable=True)
    bp.variable("FuseSeconds", "float", "8", B, editable=True)
    bp.variable("Damage", "float", "60", B, editable=True)
    bp.variable("Radius", "float", "500", B, editable=True)
    bp.variable("bArmed", "bool", "false", B)
    bp.variable("bExploded", "bool", "false", B)
    bp.variable("SpawnTime", "float", "0", B)
    bp.variable("InstigatorController", "object:" + CONTROLLER, "", B)

    g = bp.function("Arm")
    a = g.var_set("bArmed", BOOL, default="true")
    g.link_entry("then", a, "execute")

    # Detonate(): once; the explosion rule lives on the GameMode
    g = bp.function("Detonate")
    ex = g.var_get("bExploded", BOOL)
    b = g.branch()
    g.link(ex, "bExploded", b, "Condition")
    g.link_entry("then", b, "execute")
    mark = g.var_set("bExploded", BOOL, default="true")
    g.link(b, "else", mark, "execute")
    explode_here(g, (mark, "then"), "Damage", "Radius", what="bomb")

    # PlaceOnGround(): short trace down from the drop point, rest 30 cm above the hit
    g = bp.function("PlaceOnGround")
    loc = self_actor_location(g)
    start = add_vec(g, (loc, "ReturnValue"), z=100.0)
    end = add_vec(g, (loc, "ReturnValue"), z=-400.0)
    tr = g.call_static(SYS, "LineTraceSingle",
                       inputs=[Pin("WorldContextObject", OBJECT, hidden=True), struct_pin("Start", VECTOR), struct_pin("End", VECTOR),
                               Pin("TraceChannel", "byte", default="TraceTypeQuery1"), Pin("bTraceComplex", BOOL, default="false"),
                               Pin("DrawDebugType", "byte", default="None"), Pin("bIgnoreSelf", BOOL, default="true")],
                       outputs=[struct_pin("OutHit", HIT_RESULT, "out"), Pin("ReturnValue", BOOL, "out")])
    g.link(start, "ReturnValue", tr, "Start")
    g.link(end, "ReturnValue", tr, "End")
    g.link_entry("then", tr, "execute")
    b = g.branch()
    g.link(tr, "ReturnValue", b, "Condition")
    g.exec(tr, b)
    brk = g.call_static(GAMEPLAY, "BreakHitResult", inputs=[struct_pin("Hit", HIT_RESULT)],
                        outputs=[struct_pin("ImpactPoint", VECTOR, "out")], pure=True)
    g.link(tr, "OutHit", brk, "Hit")
    rest = add_vec(g, (brk, "ImpactPoint"), z=30.0)
    mv = g.call_self_native(ACTOR, "K2_SetActorLocation",
                            inputs=[struct_pin("NewLocation", VECTOR), Pin("bSweep", BOOL, default="false"), Pin("bTeleport", BOOL, default="true")],
                            outputs=[struct_pin("SweepHitResult", HIT_RESULT, "out"), Pin("ReturnValue", BOOL, "out")])
    g.link(rest, "ReturnValue", mv, "NewLocation")
    g.link(b, "then", mv, "execute")

    g = bp.event_graph()
    g.comment("Generated by tools/bpgen/graphs/items.py (BP_DFBomb). Arms after ArmDelay, detonates on a car or after FuseSeconds.", 0, 0, cols=6, rows=1)
    bpl = g.begin_play(col=0, row=1)
    now = game_time(g, col=0, row=2)
    st = g.var_set("SpawnTime", FLOAT, col=1, row=1)
    g.link(now, "ReturnValue", st, "SpawnTime")
    g.exec(bpl, st)
    pg = g.call_self("PlaceOnGround", col=2, row=1)
    g.exec(st, pg)

    tick = g.tick(col=0, row=3)
    age = age_since(g, "SpawnTime")
    armed = g.var_get("bArmed", BOOL)
    not_armed = not_bool(g)
    g.link(armed, "bArmed", not_armed, "A")
    arm_delay = g.var_get("ArmDelay", FLOAT)
    arm_due = compare(g, "GreaterEqual_FloatFloat", FLOAT)
    g.link(age, "ReturnValue", arm_due, "A")
    g.link(arm_delay, "ArmDelay", arm_due, "B")
    should_arm = and_bool(g)
    g.link(not_armed, "ReturnValue", should_arm, "A")
    g.link(arm_due, "ReturnValue", should_arm, "B")
    b1 = g.branch(col=1, row=3)
    g.link(should_arm, "ReturnValue", b1, "Condition")
    g.exec(tick, b1)
    arm = g.call_self("Arm", col=2, row=3)
    g.link(b1, "then", arm, "execute")
    fuse = g.var_get("FuseSeconds", FLOAT)
    fuse_due = compare(g, "GreaterEqual_FloatFloat", FLOAT)
    g.link(age, "ReturnValue", fuse_due, "A")
    g.link(fuse, "FuseSeconds", fuse_due, "B")
    b2 = g.branch(col=3, row=3)
    g.link(fuse_due, "ReturnValue", b2, "Condition")
    g.link(b1, "else", b2, "execute")
    g.exec(arm, b2)
    det = g.call_self("Detonate", col=4, row=3)
    g.link(b2, "then", det, "execute")

    ov = g.event(ACTOR, "ReceiveActorBeginOverlap", [obj_pin("OtherActor", ACTOR)], col=0, row=5)
    armed2 = g.var_get("bArmed", BOOL, col=0, row=6)
    b3 = g.branch(col=1, row=5)
    g.link(armed2, "bArmed", b3, "Condition")
    g.exec(ov, b3)
    cv = cast_to(g, BP_VEHICLE, col=2, row=5)
    g.link(ov, "OtherActor", cv, "Object")
    g.link(b3, "then", cv, "execute")
    det2 = g.call_self("Detonate", col=3, row=5)
    g.link(cv, "then", det2, "execute")
    return bp


# ---- BP_DFProjectile (spec §6) ----
def build_projectile() -> Blueprint:
    bp = Blueprint(BP_PROJECTILE, parent=ACTOR)
    bp.component("Collision", SPHERE_COMP, **{"sphere_radius": 15.0, "call:set_collision_profile_name": "BlockAllDynamic",
                                            "call:set_notify_rigid_body_collision": True})
    bp.component("Mesh", STATIC_MESH_COMP, "Collision", **{"static_mesh": SHAPES + "/Shape_Sphere", "relative_scale3d": {"vector": [0.3, 0.3, 0.3]},
                                                        "call:set_collision_profile_name": "NoCollision",
                                                        "override_materials": [MATERIALS + "/SolidOrange"]})
    bp.component("Trail", "/Script/Engine.ParticleSystemComponent", "Collision",
                 **{"template": "/Game/StarterContent/Particles/P_Fire", "relative_scale3d": {"vector": [0.3, 0.3, 0.3]}})
    bp.component("Movement", "/Script/Engine.ProjectileMovementComponent",
                 **{"initial_speed": 6000.0, "max_speed": 6000.0, "projectile_gravity_scale": 0.05, "rotation_follows_velocity": True,
                    "should_bounce": False, "initial_velocity_in_local_space": True})
    R = "Dead Fire|Rocket"
    bp.variable("Damage", "float", "80", R, editable=True)
    bp.variable("Radius", "float", "600", R, editable=True)
    bp.variable("LifeSeconds", "float", "4", R, editable=True)
    bp.variable("InstigatorController", "object:" + CONTROLLER, "", R)
    bp.variable("bExploded", "bool", "false", R)

    g = bp.function("Explode")
    ex = g.var_get("bExploded", BOOL)
    b = g.branch()
    g.link(ex, "bExploded", b, "Condition")
    g.link_entry("then", b, "execute")
    mark = g.var_set("bExploded", BOOL, default="true")
    g.link(b, "else", mark, "execute")
    explode_here(g, (mark, "then"), "Damage", "Radius", what="rocket")

    g = bp.event_graph()
    g.comment("Generated by tools/bpgen/graphs/items.py (BP_DFProjectile). Flies on its ProjectileMovement, explodes on any hit.", 0, 0, cols=6, rows=1)
    bpl = g.begin_play(col=0, row=1)
    life = g.var_get("LifeSeconds", FLOAT, col=0, row=2)
    ls = g.call_self_native(ACTOR, "SetLifeSpan", inputs=[Pin("InLifespan", FLOAT)], col=1, row=1)
    g.link(life, "LifeSeconds", ls, "InLifespan")
    g.exec(bpl, ls)
    owner = g.call_self_native(ACTOR, "GetOwner", outputs=[obj_pin("ReturnValue", ACTOR, "out")], pure=True, col=1, row=2)
    ov = is_valid(g, col=2, row=2)
    g.link(owner, "ReturnValue", ov, "Object")
    b = g.branch(col=2, row=1)
    g.link(ov, "ReturnValue", b, "Condition")
    g.exec(ls, b)
    col = g.var_get("Collision", OBJECT, cls_ref(SPHERE_COMP), col=3, row=2)
    ign = g.call_on(PRIMITIVE, "IgnoreActorWhenMoving", inputs=[obj_pin("Actor", ACTOR), Pin("bShouldIgnore", BOOL, default="true")], col=3, row=1)
    g.link(col, "Collision", ign, "self")
    g.link(owner, "ReturnValue", ign, "Actor")
    g.link(b, "then", ign, "execute")

    hit = g.event(ACTOR, "ReceiveHit", [obj_pin("MyComp", PRIMITIVE), obj_pin("Other", ACTOR), obj_pin("OtherComp", PRIMITIVE),
                                        Pin("bSelfMoved", BOOL), struct_pin("HitLocation", VECTOR), struct_pin("HitNormal", VECTOR),
                                        struct_pin("NormalImpulse", VECTOR), struct_pin("Hit", HIT_RESULT)], col=0, row=4)
    boom = g.call_self("Explode", col=1, row=4)
    g.exec(hit, boom)
    return bp


# ---- BP_DFLootBox (spec §3) ----
def build_lootbox() -> Blueprint:
    bp = Blueprint(BP_LOOTBOX, parent=ACTOR)
    bp.component("Crate", STATIC_MESH_COMP, **{"static_mesh": SHAPES + "/Shape_Cube", "relative_scale3d": {"vector": [0.8, 0.8, 0.8]},
                                             "call:set_collision_profile_name": "OverlapAllDynamic",  # cars drive through it
                                             "override_materials": [MATERIALS + "/SolidOrange"]})
    bp.component("Trigger", SPHERE_COMP, "Crate", **{"sphere_radius": 150.0, "absolute_scale": True,
                                                   "call:set_collision_profile_name": "OverlapOnlyPawn"})
    L = "Dead Fire|Loot"
    bp.variable("ItemType", enum_spec(E_ITEM_TYPE), enum_value(ITEM_BOOST), L, editable=True)
    bp.variable("Charges", "int", "0", L, editable=True)  # 0 = the type's box charges (GetItemInfo)
    bp.variable("bRandom", "bool", "false", L, editable=True)
    bp.variable("bRespawns", "bool", "true", L, editable=True)
    bp.variable("RespawnSeconds", "float", "30", L, editable=True)
    bp.variable("bCollected", "bool", "false", L)
    bp.variable("CollectedTime", "float", "-1", L)
    bp.dispatcher("OnLootCollected", ["Character:" + obj_spec(BP_CHARACTER), "Type:" + enum_spec(E_ITEM_TYPE)])

    def item_type(g):
        return g.var_get("ItemType", "byte", ITEM_ENUM)

    def gm_cast(g, prev):
        gm = get_game_mode(g)
        cast = cast_to(g, BP_GM)
        g.link(gm, "ReturnValue", cast, "Object")
        g.link(prev[0], prev[1], cast, "execute")
        return cast

    # ResolveCharges() -> Charges: the instance's Charges when set, else the type's box charges
    g = bp.function("ResolveCharges", outputs=["Charges:int"], pure=True)
    ch = g.var_get("Charges", INT)
    some = compare(g, "Greater_IntInt", INT, b="0")
    g.link(ch, "Charges", some, "A")
    b = g.branch()
    g.link(some, "ReturnValue", b, "Condition")
    g.link_entry("then", b, "execute")
    r_own = g.function_result([Pin("Charges", INT)])
    ch2 = g.var_get("Charges", INT)
    g.link(ch2, "Charges", r_own, "Charges")
    g.link(b, "then", r_own, "execute")
    cast = gm_cast(g, (b, "else"))
    info = g.call_on(GMC, "GetItemInfo", inputs=[enum_pin("Type", E_ITEM_TYPE)],
                     outputs=[Pin("Name", STRING, "out"), Pin("BoxCharges", INT, "out"), Pin("MaxCharges", INT, "out")], pure=True)
    g.link(cast, as_pin(BP_GM), info, "self")
    it = item_type(g)
    g.link(it, "ItemType", info, "Type")
    r_box = g.function_result([Pin("Charges", INT)])
    g.link(info, "BoxCharges", r_box, "Charges")
    g.link(cast, "then", r_box, "execute")
    r_none = g.function_result([Pin("Charges", INT, default="1")])
    g.link(cast, "CastFailed", r_none, "execute")

    # Pickup(Character) -> bool: an alive, un-stowed, controller-owned character takes the item through GrantItem
    g = bp.function("Pickup", inputs=["Character:" + obj_spec(BP_CHARACTER)], outputs=["ReturnValue:bool"])
    col = g.var_get("bCollected", BOOL)
    cv = is_valid(g)
    g.link_entry("Character", cv, "Object")
    taken_or_null = g.call_static(MATH, "BooleanOR", inputs=[Pin("A", BOOL), Pin("B", BOOL)], outputs=[Pin("ReturnValue", BOOL, "out")], pure=True)
    g.link(col, "bCollected", taken_or_null, "A")
    ncv = not_bool(g)
    g.link(cv, "ReturnValue", ncv, "A")
    g.link(ncv, "ReturnValue", taken_or_null, "B")
    b0 = g.branch()
    g.link(taken_or_null, "ReturnValue", b0, "Condition")
    g.link_entry("then", b0, "execute")
    g.link(b0, "then", g.function_result([Pin("ReturnValue", BOOL, default="false")]), "execute")
    dead = g.call_on(CC, "IsDead", outputs=[Pin("ReturnValue", BOOL, "out")], pure=True)
    g.link_entry("Character", dead, "self")
    stowed = g.var_get_on(CC, "bIsStowed", BOOL)
    g.link_entry("Character", stowed, "self")
    owner = g.var_get_on(CC, "OwningController", OBJECT, cls_ref(CONTROLLER))
    g.link_entry("Character", owner, "self")
    ov = is_valid(g)
    g.link(owner, "OwningController", ov, "Object")
    busy = g.call_static(MATH, "BooleanOR", inputs=[Pin("A", BOOL), Pin("B", BOOL)], outputs=[Pin("ReturnValue", BOOL, "out")], pure=True)
    g.link(dead, "ReturnValue", busy, "A")
    g.link(stowed, "bIsStowed", busy, "B")
    nbusy = not_bool(g)
    g.link(busy, "ReturnValue", nbusy, "A")
    ok = and_bool(g)
    g.link(nbusy, "ReturnValue", ok, "A")
    g.link(ov, "ReturnValue", ok, "B")
    b1 = g.branch()
    g.link(ok, "ReturnValue", b1, "Condition")
    g.link(b0, "else", b1, "execute")
    g.link(b1, "else", g.function_result([Pin("ReturnValue", BOOL, default="false")]), "execute")
    cast = gm_cast(g, (b1, "then"))
    g.link(cast, "CastFailed", g.function_result([Pin("ReturnValue", BOOL, default="false")]), "execute")
    charges = g.call_self("ResolveCharges", outputs=[Pin("Charges", INT, "out")], pure=True)
    grant = g.call_on(GMC, "GrantItem", inputs=[obj_pin("C", CONTROLLER), enum_pin("Type", E_ITEM_TYPE), Pin("Charges", INT)],
                      outputs=[Pin("ReturnValue", BOOL, "out")])
    g.link(cast, as_pin(BP_GM), grant, "self")
    g.link(owner, "OwningController", grant, "C")
    it = item_type(g)
    g.link(it, "ItemType", grant, "Type")
    g.link(charges, "Charges", grant, "Charges")
    g.link(cast, "then", grant, "execute")
    bg = g.branch()
    g.link(grant, "ReturnValue", bg, "Condition")
    g.exec(grant, bg)
    g.link(bg, "else", g.function_result([Pin("ReturnValue", BOOL, default="false")]), "execute")
    mark = g.var_set("bCollected", BOOL, default="true")
    g.link(bg, "then", mark, "execute")
    now = game_time(g)
    stamp = g.var_set("CollectedTime", FLOAT)
    g.link(now, "ReturnValue", stamp, "CollectedTime")
    hide = g.call_self_native(ACTOR, "SetActorHiddenInGame", inputs=[Pin("bNewHidden", BOOL, default="true")])
    nocol = g.call_self_native(ACTOR, "SetActorEnableCollision", inputs=[Pin("bNewActorEnableCollision", BOOL, default="false")])
    fire = g.call_delegate("OnLootCollected", [obj_pin("Character", CC), enum_pin("Type", E_ITEM_TYPE)])
    g.link_entry("Character", fire, "Character")
    it2 = item_type(g)
    g.link(it2, "ItemType", fire, "Type")
    g.exec(mark, stamp, hide, nocol, fire)
    g.exec(fire, g.function_result([Pin("ReturnValue", BOOL, default="true")]))

    # Reset(): roll a type when random, then show and collide again
    g = bp.function("Reset")
    rnd = g.var_get("bRandom", BOOL)
    b = g.branch()
    g.link(rnd, "bRandom", b, "Condition")
    g.link_entry("then", b, "execute")
    roll = g.call_static(MATH, "RandomIntegerInRange", inputs=[Pin("Min", INT, default="1"), Pin("Max", INT, default="5")],
                         outputs=[Pin("ReturnValue", INT, "out")], pure=True)
    clear = g.var_set("bCollected", BOOL, default="false")
    prev = (b, "then")
    for idx in (ITEM_BOOST, ITEM_SHIELD, ITEM_BOMB, ITEM_GUN):
        eq = compare(g, "EqualEqual_IntInt", INT, b=str(idx))
        g.link(roll, "ReturnValue", eq, "A")
        bi = g.branch()
        g.link(eq, "ReturnValue", bi, "Condition")
        g.link(prev[0], prev[1], bi, "execute")
        st = g.var_set("ItemType", "byte", default=enum_value(idx), sub_object=ITEM_ENUM)
        g.link(bi, "then", st, "execute")
        g.exec(st, clear)
        prev = (bi, "else")
    st = g.var_set("ItemType", "byte", default=enum_value(ITEM_RPG), sub_object=ITEM_ENUM)
    g.link(prev[0], prev[1], st, "execute")
    g.exec(st, clear)
    g.link(b, "else", clear, "execute")
    show = g.call_self_native(ACTOR, "SetActorHiddenInGame", inputs=[Pin("bNewHidden", BOOL, default="false")])
    col = g.call_self_native(ACTOR, "SetActorEnableCollision", inputs=[Pin("bNewActorEnableCollision", BOOL, default="true")])
    g.exec(clear, show, col)

    g = bp.event_graph()
    g.comment("Generated by tools/bpgen/graphs/items.py (BP_DFLootBox). Collected on touch by a character on foot; back after RespawnSeconds.", 0, 0, cols=6, rows=1)
    bpl = g.begin_play(col=0, row=1)
    rnd = g.var_get("bRandom", BOOL, col=0, row=2)
    b = g.branch(col=1, row=1)
    g.link(rnd, "bRandom", b, "Condition")
    g.exec(bpl, b)
    rs = g.call_self("Reset", col=2, row=1)
    g.link(b, "then", rs, "execute")

    tick = g.tick(col=0, row=3)
    col_ = g.var_get("bCollected", BOOL)
    resp = g.var_get("bRespawns", BOOL)
    both = and_bool(g)
    g.link(col_, "bCollected", both, "A")
    g.link(resp, "bRespawns", both, "B")
    age = age_since(g, "CollectedTime")
    delay = g.var_get("RespawnSeconds", FLOAT)
    due = compare(g, "GreaterEqual_FloatFloat", FLOAT)
    g.link(age, "ReturnValue", due, "A")
    g.link(delay, "RespawnSeconds", due, "B")
    go = and_bool(g)
    g.link(both, "ReturnValue", go, "A")
    g.link(due, "ReturnValue", go, "B")
    bt = g.branch(col=1, row=3)
    g.link(go, "ReturnValue", bt, "Condition")
    g.exec(tick, bt)
    rs2 = g.call_self("Reset", col=2, row=3)
    g.link(bt, "then", rs2, "execute")

    ov = g.event(ACTOR, "ReceiveActorBeginOverlap", [obj_pin("OtherActor", ACTOR)], col=0, row=5)
    cc = cast_to(g, BP_CHARACTER, col=1, row=5)
    g.link(ov, "OtherActor", cc, "Object")
    g.exec(ov, cc)
    pk = g.call_self("Pickup", inputs=[obj_pin("Character", CC)], outputs=[Pin("ReturnValue", BOOL, "out")], col=2, row=5)
    g.link(cc, as_pin(BP_CHARACTER), pk, "Character")
    g.link(cc, "then", pk, "execute")
    return bp


# ---- BP_DFDestructible (spec §6): a dark block that only explosives demolish ----
def build_destructible() -> Blueprint:
    bp = Blueprint(BP_DESTRUCTIBLE, parent=ACTOR)
    bp.component("Rock", STATIC_MESH_COMP, **{"static_mesh": SHAPES + "/Shape_Cube", "relative_scale3d": {"vector": [3.0, 3.0, 3.0]},
                                            "call:set_collision_profile_name": "BlockAllDynamic",
                                            "override_materials": [MATERIALS + "/BlackGrid"]})
    D = "Dead Fire|Destructible"
    bp.variable("Health", "float", "60", D, editable=True)
    bp.variable("bExplosivesOnly", "bool", "true", D, editable=True)
    bp.variable("bDestroyed", "bool", "false", D)
    bp.dispatcher("OnDestructibleDestroyed", [])

    # Demolish(): once; effects-only explosion, then hidden and non-colliding (the road behind it is open)
    g = bp.function("Demolish")
    done = g.var_get("bDestroyed", BOOL)
    b = g.branch()
    g.link(done, "bDestroyed", b, "Condition")
    g.link_entry("then", b, "execute")
    mark = g.var_set("bDestroyed", BOOL, default="true")
    g.link(b, "else", mark, "execute")
    gm = get_game_mode(g)
    cast = cast_to(g, BP_GM)
    g.link(gm, "ReturnValue", cast, "Object")
    g.exec(mark, cast)
    loc = self_actor_location(g)
    boom = g.call_on(GMC, "SpawnExplosion", inputs=[struct_pin("Location", VECTOR), Pin("Damage", FLOAT, default="0.0"),
                                                    Pin("Radius", FLOAT, default="0.0"), obj_pin("InstigatedBy", CONTROLLER),
                                                    obj_pin("Causer", ACTOR), Pin("bBlowTires", BOOL, default="false")])
    g.link(cast, as_pin(BP_GM), boom, "self")
    g.link(loc, "ReturnValue", boom, "Location")
    me = g.self_node()
    g.link(me, "self", boom, "Causer")
    g.link(cast, "then", boom, "execute")
    hide = g.call_self_native(ACTOR, "SetActorHiddenInGame", inputs=[Pin("bNewHidden", BOOL, default="true")])
    g.exec(boom, hide)
    g.link(cast, "CastFailed", hide, "execute")
    nocol = g.call_self_native(ACTOR, "SetActorEnableCollision", inputs=[Pin("bNewActorEnableCollision", BOOL, default="false")])
    fire = g.call_delegate("OnDestructibleDestroyed")
    me2 = g.self_node()
    log = log_line(g, "destructible demolished ", name_of(g, (me2, "self")))
    g.exec(hide, nocol, fire, log)

    g = bp.event_graph()
    g.comment("Generated by tools/bpgen/graphs/items.py (BP_DFDestructible). Only BP_DFExplosiveDamage hurts it while bExplosivesOnly.", 0, 0, cols=6, rows=1)
    ad = g.event(ACTOR, "ReceiveAnyDamage",
                 [Pin("Damage", FLOAT), obj_pin("DamageType", DAMAGE_TYPE), obj_pin("InstigatedBy", CONTROLLER), obj_pin("DamageCauser", ACTOR)],
                 col=0, row=1)
    done = g.var_get("bDestroyed", BOOL, col=0, row=2)
    b0 = g.branch(col=1, row=1)
    g.link(done, "bDestroyed", b0, "Condition")
    g.exec(ad, b0)
    only = g.var_get("bExplosivesOnly", BOOL, col=1, row=2)
    bx = g.branch(col=2, row=1)
    g.link(only, "bExplosivesOnly", bx, "Condition")
    g.link(b0, "else", bx, "execute")
    ex = cast_to(g, BP_EXPLOSIVE_DAMAGE, col=3, row=1)
    g.link(ad, "DamageType", ex, "Object")
    g.link(bx, "then", ex, "execute")
    h = g.var_get("Health", FLOAT, col=3, row=3)
    sub = math2(g, "Subtract_FloatFloat", FLOAT, col=4, row=3)
    g.link(h, "Health", sub, "A")
    g.link(ad, "Damage", sub, "B")
    clamp = g.call_static(MATH, "FMax", inputs=[Pin("A", FLOAT), Pin("B", FLOAT, default="0.0")], outputs=[Pin("ReturnValue", FLOAT, "out")],
                          pure=True, col=5, row=3)
    g.link(sub, "ReturnValue", clamp, "A")
    seth = g.var_set("Health", FLOAT, col=4, row=2)
    g.link(clamp, "ReturnValue", seth, "Health")
    g.link(ex, "then", seth, "execute")
    g.link(bx, "else", seth, "execute")
    gone = compare(g, "LessEqual_FloatFloat", FLOAT, b="0.0", col=5, row=4)
    g.link(seth, "Output_Get", gone, "A")
    bd = g.branch(col=5, row=2)
    g.link(gone, "ReturnValue", bd, "Condition")
    g.exec(seth, bd)
    dem = g.call_self("Demolish", col=6, row=2)
    g.link(bd, "then", dem, "execute")
    return bp


def build():
    return [build_explosive_damage(), build_bomb(), build_projectile(), build_lootbox(), build_destructible()]


if __name__ == "__main__":
    for b in build():
        print(b.write(OUT))
