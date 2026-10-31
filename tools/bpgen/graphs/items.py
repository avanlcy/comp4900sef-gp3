"""Phase 3 item actors (spec docs/superpowers/specs/2026-10-30-phase3-items-design.md §5-§6):
BP_DFExplosiveDamage (the damage type explosions use; Task 1), BP_DFBomb (Task 3), BP_DFProjectile (Task 4),
BP_DFLootBox (Task 5), BP_DFDestructible (Task 6). The vehicle spawns bombs and rockets; the GameMode owns the
explosion rule (SpawnExplosion) that all of them call. Phase 7 Task 17 (spec §7.4, §7.5): the crate's own look (SM_DF_Crate and
its lid, the glowing stripe, the floating icon and the beacon pillar in the item's colour: ApplyLook, ShowLook, BobIcon; the
loot burst and the open / deny sounds) and the bomb as a mine whose red lamp blinks faster as its fuse runs (ComputeBlinkHz,
TickBlink; the arm and beep sounds). Task 21 (spec §8.2): the rock is SM_DF_RockWall and breaks into eight BP_DFDebris chunks
(SpawnChunk), its explosion at the wall's foot.
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

from df import (AUDIO_COMP, BP_FX_PUFF, FX_VIEW_RADIUS, MI_FX_FLAME, NO_COLLISION, ROTATOR, SM_EXHAUST_FLAME, SM_ROCKET,  # noqa: E402
                STRING, SW_ROCKET_LOOP, TRANSFORM, spawn_fx)  # Phase 7 Task 16
from df import (BILLBOARD_COMP, BOMB_LAMP_SLOT, BP_FX_LOOT_BURST, CRATE_STRIPE_SLOT, LINEAR_COLOR, MI_ICON, MID, NAME,  # noqa: E402
                POINT_LIGHT_COMP, SCENE_COMP, SM_BEACON, SM_BOMB, SM_CRATE, SM_CRATE_LID, SOUND_BASE, SW_BOMB_ARM, SW_BOMB_BEEP,
                SW_DENY, SW_LOOT_OPEN, TEXTURE_2D, cls_ref, play_sound_at, transform_at)  # Phase 7 Task 17
from df import BOMB_TRIGGER_R, BOMB_TRIGGER_Z, CRATE_HALF_HEIGHT, LID_POP_SECONDS, ROTATOR  # noqa: E402  (Task 17 fix round 1)
from df import (BP_DEBRIS, DEBRIS_SPEED, ROCK_CHUNK_CELLS, ROCK_CHUNK_CM, SM_ROCK_WALL, STATIC_MESH, TRANSFORM,  # noqa: E402
                vec)  # Task 21

DEBRISC = gen(BP_DEBRIS)
BOX_SPHERE_BOUNDS = "/Script/CoreUObject.BoxSphereBounds"

GMC, VC, CC = gen(BP_GM), gen(BP_VEHICLE), gen(BP_CHARACTER)
ITEM_ENUM = enum_pin("x", E_ITEM_TYPE).sub_object
# Phase 7 Task 17 (spec §7.4, §7.5): where the crate's look sits on its 58 cm body and 9 cm lid (cm, the crate's frame), the
# bomb's blink (1 Hz at the drop, 6 Hz when the fuse runs out) and the mine's touch sphere
# Fix round 1: the actor stands at the crate's centre, so the lid's top is CRATE_HALF_HEIGHT (40) over it
ICON_HALF, ICON_BOB = 35.0, 20.0    # a 70 cm icon, bobbing 20 cm peak to peak
ICON_Z = CRATE_HALF_HEIGHT + 20.0 + ICON_BOB / 2 + ICON_HALF   # 105: the icon's bottom 20 cm over the lid at the low bob
BEACON_Z = ICON_Z + ICON_HALF + ICON_BOB / 2 + 10.0            # 160: the beacon stands on the icon's top, so its light never covers it
BLINK_HZ_START, BLINK_HZ_END = 1.0, 6.0
# the bomb's touch (df.BOMB_TRIGGER_Z / _R, fix round 1): the old bomb's 25 cm sphere 55 cm over the ground, so a car's chassis
# (20-152 cm up) catches it within 25 cm sideways, as before
# the red blink light hangs this far over the lamp (cm): right on it (4000 unitless) it burnt the mine's top out to white in the first
# capture; from here it reddens the road around the mine
BLINK_LIGHT_UP = 40.0


def build_explosive_damage() -> Blueprint:
    """A DamageType child with no logic: explosions apply it, the on-foot character ignores it, the destructible
    rock only accepts it (spec §5, §6)."""
    return Blueprint(BP_EXPLOSIVE_DAMAGE, parent=DAMAGE_TYPE, description="The damage type explosions apply: the rock accepts only this, the character ignores it.")


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
    bp = Blueprint(BP_BOMB, parent=ACTOR,
                   description="The dropped bomb, a mine with a red lamp that blinks faster as its fuse runs: arms after a delay, then "
                               "detonates when a car touches it or when its fuse runs out.")
    # Phase 7 Task 17 (spec §7.5): the mine (SM_DF_Bomb, its own slots, scale 1) rests on the ground; the touch is its Trigger sphere
    # (the flat mesh has no collision), and the red BlinkLight hangs BLINK_LIGHT_UP over the lamp (socket Lamp)
    bp.component("Shell", STATIC_MESH_COMP, static_mesh=SM_BOMB, relative_scale3d={"vector": [1.0, 1.0, 1.0]}, override_materials=[],
                 **NO_COLLISION)
    bp.component("Trigger", SPHERE_COMP, "Shell", sphere_radius=BOMB_TRIGGER_R, relative_location={"vector": [0.0, 0.0, BOMB_TRIGGER_Z]},
                 **{"call:set_collision_profile_name": "OverlapOnlyPawn"})
    bp.component("BlinkLight", POINT_LIGHT_COMP, "Shell", socket="Lamp", relative_location={"vector": [0.0, 0.0, BLINK_LIGHT_UP]},
                 intensity_units={"enum": "LightUnits.UNITLESS"}, intensity=0.0, attenuation_radius=400.0, cast_shadows=False,
                 **{"call:set_light_color": {"color": [1.0, 0.05, 0.03, 1.0]}})
    B = "Dead Fire|Bomb"
    bp.variable("ArmDelay", "float", "1", B, editable=True)
    bp.variable("FuseSeconds", "float", "8", B, editable=True)
    bp.variable("Damage", "float", "60", B, editable=True)
    bp.variable("Radius", "float", "500", B, editable=True)
    bp.variable("bArmed", "bool", "false", B)
    bp.variable("bExploded", "bool", "false", B)
    bp.variable("SpawnTime", "float", "0", B)
    bp.variable("InstigatorController", "object:" + CONTROLLER, "", B)
    # Phase 7 Task 17 (spec §7.5): the blink (the lamp's Glow and the light's intensity while on) and the sounds
    BL = "Dead Fire|Bomb Look"
    for name, default in (("BlinkGlow", 3.0), ("BlinkLightIntensity", 1500.0)):
        bp.variable(name, "float", repr(default), BL, editable=True)
        bp.default(name, default)
    for name, sound in (("ArmSound", SW_BOMB_ARM), ("BeepSound", SW_BOMB_BEEP)):
        bp.variable(name, "object:" + SOUND_BASE, "", BL, editable=True)
        bp.default(name, sound)
    bp.variable("BlinkLamp", "object:" + MID, "", BL)  # the Shell's BombLamp slot as a dynamic material
    bp.variable("bBlinkOn", "bool", "false", BL)
    bp.variable("NextBlinkTime", "float", "0", BL)

    g = bp.function("Arm", doc="Arms the bomb (the arming click): the next car to touch it detonates it.")
    a = g.var_set("bArmed", BOOL, default="true")
    g.link_entry("then", a, "execute")
    g.exec(a, play_sound_at(g, (g.var_get("ArmSound", OBJECT, cls_ref(SOUND_BASE)), "ArmSound"), (self_actor_location(g), "ReturnValue")))

    # ComputeBlinkHz(Elapsed) -> Hz (Phase 7 Task 17, spec §7.5): 1 Hz at the drop, 6 Hz when the fuse runs out
    g = bp.function("ComputeBlinkHz", doc="The lamp's blink rate Elapsed seconds after the drop: lerp(%g, %g, clamp(Elapsed / FuseSeconds, 0, 1)) Hz."
                    % (BLINK_HZ_START, BLINK_HZ_END), inputs=["Elapsed:float"], outputs=["Hz:float"], pure=True)
    frac = math2(g, "Divide_FloatFloat", FLOAT)
    g.link_entry("Elapsed", frac, "A")
    fuse = g.call_static(MATH, "FMax", inputs=[Pin("A", FLOAT), Pin("B", FLOAT, default="0.001")], outputs=[Pin("ReturnValue", FLOAT, "out")], pure=True)
    g.link(g.var_get("FuseSeconds", FLOAT), "FuseSeconds", fuse, "A")
    g.link(fuse, "ReturnValue", frac, "B")
    clamp = g.call_static(MATH, "FClamp", inputs=[Pin("Value", FLOAT), Pin("Min", FLOAT, default="0.0"), Pin("Max", FLOAT, default="1.0")],
                          outputs=[Pin("ReturnValue", FLOAT, "out")], pure=True)
    g.link(frac, "ReturnValue", clamp, "Value")
    hz = g.call_static(MATH, "Lerp", inputs=[Pin("A", FLOAT, default=repr(BLINK_HZ_START)), Pin("B", FLOAT, default=repr(BLINK_HZ_END)),
                                            Pin("Alpha", FLOAT)], outputs=[Pin("ReturnValue", FLOAT, "out")], pure=True)
    g.link(clamp, "ReturnValue", hz, "Alpha")
    g.link_result(hz, "ReturnValue", "Hz")
    g.link_entry("then", "result", "execute")

    # TickBlink (Phase 7 Task 17): when the next blink is due, the lamp and the light toggle (a beep as the lamp comes on), and the
    # next one is half a period later at the rate the fuse has reached
    g = bp.function("TickBlink", doc="Toggles the lamp (BlinkLamp Glow, BlinkLight) when a blink is due, beeping as it comes on; the "
                    "next toggle is half a period of ComputeBlinkHz later.")
    now = game_time(g)
    due = compare(g, "GreaterEqual_FloatFloat", FLOAT)
    g.link(now, "ReturnValue", due, "A")
    g.link(g.var_get("NextBlinkTime", FLOAT), "NextBlinkTime", due, "B")
    b = g.branch()
    g.note(b, "a blink due?")
    g.link(due, "ReturnValue", b, "Condition")
    g.link_entry("then", b, "execute")
    flip = not_bool(g)
    g.link(g.var_get("bBlinkOn", BOOL), "bBlinkOn", flip, "A")
    on = g.var_set("bBlinkOn", BOOL)
    g.link(flip, "ReturnValue", on, "bBlinkOn")
    g.link(b, "then", on, "execute")

    def when_on(var):
        n = g.call_static(MATH, "SelectFloat", inputs=[Pin("A", FLOAT), Pin("B", FLOAT, default="0.0"), Pin("bPickA", BOOL)],
                          outputs=[Pin("ReturnValue", FLOAT, "out")], pure=True)
        g.link(g.var_get(var, FLOAT), var, n, "A")
        g.link(on, "Output_Get", n, "bPickA")
        return n

    glow = g.call_on(MID, "SetScalarParameterValue", inputs=[Pin("ParameterName", NAME, default="Glow"), Pin("Value", FLOAT)])
    g.link(g.var_get("BlinkLamp", OBJECT, cls_ref(MID)), "BlinkLamp", glow, "self")
    g.link(when_on("BlinkGlow"), "ReturnValue", glow, "Value")
    light = g.call_on(POINT_LIGHT_COMP, "SetIntensity", inputs=[Pin("NewIntensity", FLOAT)])
    g.link(g.var_get("BlinkLight", OBJECT, cls_ref(POINT_LIGHT_COMP)), "BlinkLight", light, "self")
    g.link(when_on("BlinkLightIntensity"), "ReturnValue", light, "NewIntensity")
    g.exec(on, glow, light)
    lit = g.branch()
    g.note(lit, "the lamp just came on? beep")
    g.link(g.var_get("bBlinkOn", BOOL), "bBlinkOn", lit, "Condition")
    g.exec(light, lit)
    lamp_at = g.call_on(SCENE_COMP, "K2_GetComponentLocation", outputs=[struct_pin("ReturnValue", VECTOR, "out")], pure=True)
    g.link(g.var_get("BlinkLight", OBJECT, cls_ref(POINT_LIGHT_COMP)), "BlinkLight", lamp_at, "self")
    beep = play_sound_at(g, (g.var_get("BeepSound", OBJECT, cls_ref(SOUND_BASE)), "BeepSound"), (lamp_at, "ReturnValue"))
    g.link(lit, "then", beep, "execute")
    rate = g.call_self("ComputeBlinkHz", inputs=[Pin("Elapsed", FLOAT)], outputs=[Pin("Hz", FLOAT, "out")], pure=True)
    g.link(age_since(g, "SpawnTime"), "ReturnValue", rate, "Elapsed")
    half = math2(g, "Divide_FloatFloat", FLOAT, a="0.5")
    g.link(rate, "Hz", half, "B")
    later = math2(g, "Add_FloatFloat", FLOAT)
    g.link(game_time(g), "ReturnValue", later, "A")
    g.link(half, "ReturnValue", later, "B")
    nxt = g.var_set("NextBlinkTime", FLOAT)
    g.link(later, "ReturnValue", nxt, "NextBlinkTime")
    g.exec(beep, nxt)
    g.link(lit, "else", nxt, "execute")

    # Detonate(): once; the explosion rule lives on the GameMode
    g = bp.function("Detonate", doc="Explodes once through the GameMode's explosion rule, then removes the bomb.")
    ex = g.var_get("bExploded", BOOL)
    b = g.branch()
    g.link(ex, "bExploded", b, "Condition")
    g.link_entry("then", b, "execute")
    mark = g.var_set("bExploded", BOOL, default="true")
    g.link(b, "else", mark, "execute")
    explode_here(g, (mark, "then"), "Damage", "Radius", what="bomb")

    # PlaceOnGround(): short trace down from the drop point; the mine (origin at its base, Phase 7 Task 17) rests on the hit
    g = bp.function("PlaceOnGround", doc="Settles the mine on the ground found by a short trace down from the drop point.")
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
    rest = add_vec(g, (brk, "ImpactPoint"), z=0.0)
    mv = g.call_self_native(ACTOR, "K2_SetActorLocation",
                            inputs=[struct_pin("NewLocation", VECTOR), Pin("bSweep", BOOL, default="false"), Pin("bTeleport", BOOL, default="true")],
                            outputs=[struct_pin("SweepHitResult", HIT_RESULT, "out"), Pin("ReturnValue", BOOL, "out")])
    g.link(rest, "ReturnValue", mv, "NewLocation")
    g.link(b, "then", mv, "execute")

    g = bp.event_graph()
    g.section("Begin Play: stamp the spawn time, settle on the ground, the lamp's dynamic material")
    bpl = g.begin_play(col=0, row=1)
    now = game_time(g, col=0, row=2)
    st = g.var_set("SpawnTime", FLOAT, col=1, row=1)
    g.link(now, "ReturnValue", st, "SpawnTime")
    g.exec(bpl, st)
    pg = g.call_self("PlaceOnGround", col=2, row=1)
    g.exec(st, pg)
    lamp = g.call_on(PRIMITIVE, "CreateDynamicMaterialInstance", inputs=[Pin("ElementIndex", INT, default=str(BOMB_LAMP_SLOT)),
                                                                        obj_pin("SourceMaterial", "/Script/Engine.MaterialInterface"),
                                                                        Pin("OptionalName", NAME, default="None")],
                     outputs=[obj_pin("ReturnValue", MID, "out")])
    g.link(g.var_get("Shell", OBJECT, cls_ref(STATIC_MESH_COMP)), "Shell", lamp, "self")
    keep = g.var_set("BlinkLamp", OBJECT, sub_object=cls_ref(MID))
    g.link(lamp, "ReturnValue", keep, "BlinkLamp")
    g.exec(pg, lamp, keep)

    g.section("Tick: blink, arm after ArmDelay, detonate after FuseSeconds")
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
    g.note(b1, "unarmed and the arm delay is over?")
    g.link(should_arm, "ReturnValue", b1, "Condition")
    g.exec(tick, g.call_self("TickBlink"), b1)
    arm = g.call_self("Arm", col=2, row=3)
    g.link(b1, "then", arm, "execute")
    fuse = g.var_get("FuseSeconds", FLOAT)
    fuse_due = compare(g, "GreaterEqual_FloatFloat", FLOAT)
    g.link(age, "ReturnValue", fuse_due, "A")
    g.link(fuse, "FuseSeconds", fuse_due, "B")
    b2 = g.branch(col=3, row=3)
    g.note(b2, "fuse run out?")
    g.link(fuse_due, "ReturnValue", b2, "Condition")
    g.link(b1, "else", b2, "execute")
    g.exec(arm, b2)
    det = g.call_self("Detonate", col=4, row=3)
    g.link(b2, "then", det, "execute")

    g.section("Overlap: a car touching an armed bomb detonates it")
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
    bp = Blueprint(BP_PROJECTILE, parent=ACTOR, description="The rocket: flies on its projectile movement with its flame, smoke trail and "
                                                            "engine sound, and explodes on whatever it hits.")
    bp.component("Collision", SPHERE_COMP, **{"sphere_radius": 15.0, "call:set_collision_profile_name": "BlockAllDynamic",
                                            "call:set_notify_rigid_body_collision": True})
    # Phase 7 Task 16 (spec §7.1, §7.5): the rocket mesh (centred on the collision sphere, flying along +X, its own slots) and the
    # flame at its Exhaust socket (yawed 180, so SM_DF_ExhaustFlame's +X runs backwards) in the RPG's orange MI_DF_FxFlame
    bp.component("Mesh", STATIC_MESH_COMP, "Collision", **{"static_mesh": SM_ROCKET, "relative_scale3d": {"vector": [1.0, 1.0, 1.0]},
                                                        "call:set_collision_profile_name": "NoCollision", "override_materials": []})
    bp.component("Exhaust", STATIC_MESH_COMP, "Mesh", socket="Exhaust", static_mesh=SM_EXHAUST_FLAME, override_materials=[MI_FX_FLAME],
                 relative_scale3d={"vector": [1.0, 0.7, 0.7]}, cast_shadow=False, **NO_COLLISION)
    # the stock P_Fire trail is gone: the runner cannot delete a component from an existing asset (the plugin has no
    # RemoveComponent), so Trail stays an empty, inactive, hidden particle component with no template (no stock reference)
    bp.component("Trail", "/Script/Engine.ParticleSystemComponent", "Collision",
                 **{"template": None, "auto_activate": False, "visible": False, "relative_scale3d": {"vector": [1.0, 1.0, 1.0]}})
    bp.component("LoopAudio", AUDIO_COMP, "Collision", auto_activate=True, sound=SW_ROCKET_LOOP)  # the rocket's motor, looping
    bp.component("Movement", "/Script/Engine.ProjectileMovementComponent",
                 **{"initial_speed": 6000.0, "max_speed": 6000.0, "projectile_gravity_scale": 0.05, "rotation_follows_velocity": True,
                    "should_bounce": False, "initial_velocity_in_local_space": True})
    R = "Dead Fire|Rocket"
    bp.variable("Damage", "float", "80", R, editable=True)
    bp.variable("Radius", "float", "600", R, editable=True)
    bp.variable("LifeSeconds", "float", "4", R, editable=True)
    bp.variable("InstigatorController", "object:" + CONTROLLER, "", R)
    bp.variable("bExploded", "bool", "false", R)
    bp.variable("TrailPuffInterval", "float", "0.05", R, editable=True)  # Phase 7 Task 16: s between smoke-trail puffs
    bp.default("TrailPuffInterval", 0.05)

    # SpawnTrailPuff (Phase 7 Task 16, spec §7.1; a looping timer from BeginPlay): a smoke puff at the flame's root, only near the
    # player's camera (GameMode.IsNearPlayerView; Review Focus 2)
    g = bp.function("SpawnTrailPuff", doc="A BP_DFFxPuff at the exhaust while the rocket is within %g cm of the player's camera." % FX_VIEW_RADIUS)
    gm = get_game_mode(g)
    cast = cast_to(g, BP_GM)
    g.link(gm, "ReturnValue", cast, "Object")
    g.link_entry("then", cast, "execute")
    tail = g.call_on(SCENE_COMP, "K2_GetComponentLocation", outputs=[struct_pin("ReturnValue", VECTOR, "out")], pure=True)
    g.link(g.var_get("Exhaust", OBJECT, cls_ref(STATIC_MESH_COMP)), "Exhaust", tail, "self")
    near = g.call_on(GMC, "IsNearPlayerView", inputs=[struct_pin("Location", VECTOR), Pin("Radius", FLOAT, default="%f" % FX_VIEW_RADIUS)],
                     outputs=[Pin("ReturnValue", BOOL, "out")], pure=True)
    g.link(cast, as_pin(BP_GM), near, "self")
    g.link(tail, "ReturnValue", near, "Location")
    b = g.branch()
    g.note(b, "near the player's camera?")
    g.link(near, "ReturnValue", b, "Condition")
    g.link(cast, "then", b, "execute")
    xf = g.call_static(MATH, "MakeTransform", inputs=[struct_pin("Location", VECTOR), struct_pin("Rotation", ROTATOR),
                                                        struct_pin("Scale", VECTOR, default="1,1,1")],
                       outputs=[struct_pin("ReturnValue", TRANSFORM, "out")], pure=True)
    g.link(tail, "ReturnValue", xf, "Location")
    first, _, _ = spawn_fx(g, BP_FX_PUFF, (xf, "ReturnValue"))
    g.link(b, "then", first, "execute")

    g = bp.function("Explode", doc="Explodes once through the GameMode's explosion rule, then removes the rocket.")
    ex = g.var_get("bExploded", BOOL)
    b = g.branch()
    g.link(ex, "bExploded", b, "Condition")
    g.link_entry("then", b, "execute")
    mark = g.var_set("bExploded", BOOL, default="true")
    g.link(b, "else", mark, "execute")
    explode_here(g, (mark, "then"), "Damage", "Radius", what="rocket")

    g = bp.event_graph()
    g.section("Begin Play: lifespan, the smoke trail's timer, and ignore the car that fired it")
    bpl = g.begin_play(col=0, row=1)
    life = g.var_get("LifeSeconds", FLOAT, col=0, row=2)
    ls = g.call_self_native(ACTOR, "SetLifeSpan", inputs=[Pin("InLifespan", FLOAT)], col=1, row=1)
    g.link(life, "LifeSeconds", ls, "InLifespan")
    g.exec(bpl, ls)
    trail = g.call_static(SYS, "K2_SetTimer", inputs=[obj_pin("Object", "/Script/CoreUObject.Object"), Pin("FunctionName", STRING, default="SpawnTrailPuff"),
                                                      Pin("Time", FLOAT), Pin("bLooping", BOOL, default="true"),
                                                      Pin("InitialStartDelay", FLOAT, default="0.0"), Pin("InitialStartDelayVariance", FLOAT, default="0.0")],
                          outputs=[struct_pin("ReturnValue", "/Script/Engine.TimerHandle", "out")])
    g.link(g.self_node(), "self", trail, "Object")
    g.link(g.var_get("TrailPuffInterval", FLOAT), "TrailPuffInterval", trail, "Time")
    g.exec(ls, trail)
    owner = g.call_self_native(ACTOR, "GetOwner", outputs=[obj_pin("ReturnValue", ACTOR, "out")], pure=True, col=1, row=2)
    ov = is_valid(g, col=2, row=2)
    g.link(owner, "ReturnValue", ov, "Object")
    b = g.branch(col=2, row=1)
    g.link(ov, "ReturnValue", b, "Condition")
    g.exec(trail, b)
    col = g.var_get("Collision", OBJECT, cls_ref(SPHERE_COMP), col=3, row=2)
    ign = g.call_on(PRIMITIVE, "IgnoreActorWhenMoving", inputs=[obj_pin("Actor", ACTOR), Pin("bShouldIgnore", BOOL, default="true")], col=3, row=1)
    g.link(col, "Collision", ign, "self")
    g.link(owner, "ReturnValue", ign, "Actor")
    g.link(b, "then", ign, "execute")

    g.section("Hit: explode")
    hit = g.event(ACTOR, "ReceiveHit", [obj_pin("MyComp", PRIMITIVE), obj_pin("Other", ACTOR), obj_pin("OtherComp", PRIMITIVE),
                                        Pin("bSelfMoved", BOOL), struct_pin("HitLocation", VECTOR), struct_pin("HitNormal", VECTOR),
                                        struct_pin("NormalImpulse", VECTOR), struct_pin("Hit", HIT_RESULT)], col=0, row=4)
    boom = g.call_self("Explode", col=1, row=4)
    g.exec(hit, boom)
    return bp


# ---- BP_DFLootBox's look (Phase 7 Task 17, spec §7.4) ----
def _mid_param(g: Graph, var: str, kind: str, name: str, src) -> Node:
    """<var>.Set<kind>ParameterValue(name, src) on one of the crate's MIDs (kind Vector / Scalar / Texture; impure)."""
    value = {"Vector": struct_pin("Value", LINEAR_COLOR), "Scalar": Pin("Value", FLOAT), "Texture": obj_pin("Value", "/Script/Engine.Texture")}[kind]
    n = g.call_on(MID, "Set%sParameterValue" % kind, inputs=[Pin("ParameterName", NAME, default=name), value])
    g.link(g.var_get(var, OBJECT, cls_ref(MID)), var, n, "self")
    g.link(src[0], src[1], n, "Value")
    return n


def add_look_functions(bp: Blueprint) -> None:
    """ApplyLook (the item's colour on the stripes, icon and beacon), ShowLook (all four parts shown or hidden) and BobIcon."""
    g = bp.function("ApplyLook", doc="The item's look (GameMode.GetItemLook of ItemType, bRandom): the crate's and the lid's stripe "
                    "glow in its colour (EmissiveColor and Tint, Glow StripeGlow), the icon shows its texture in that colour, the beacon "
                    "takes the colour. Makes the dynamic materials the first time (the same ones after).")
    prev = ("entry", "then")
    for comp, cls, slot, var in (("Crate", STATIC_MESH_COMP, CRATE_STRIPE_SLOT, "StripeMID"), ("Lid", STATIC_MESH_COMP, CRATE_STRIPE_SLOT, "LidStripeMID"),
                                 ("Icon", BILLBOARD_COMP, 0, "IconMID"), ("Beacon", STATIC_MESH_COMP, 0, "BeaconMID")):
        # an existing MID in the slot is returned as it is (UPrimitiveComponent::CreateDynamicMaterialInstance), so this repeats safely
        mk = g.call_on(PRIMITIVE, "CreateDynamicMaterialInstance", inputs=[Pin("ElementIndex", INT, default=str(slot)),
                                                                          obj_pin("SourceMaterial", "/Script/Engine.MaterialInterface"),
                                                                          Pin("OptionalName", NAME, default="None")],
                       outputs=[obj_pin("ReturnValue", MID, "out")])
        g.link(g.var_get(comp, OBJECT, cls_ref(cls)), comp, mk, "self")
        keep = g.var_set(var, OBJECT, sub_object=cls_ref(MID))
        g.link(mk, "ReturnValue", keep, var)
        g.link(prev[0], prev[1], mk, "execute")
        g.exec(mk, keep)
        prev = (keep, "then")
    cast = cast_to(g, BP_GM)
    g.link(get_game_mode(g), "ReturnValue", cast, "Object")
    g.link(prev[0], prev[1], cast, "execute")
    look = g.call_on(GMC, "GetItemLook", inputs=[enum_pin("Type", E_ITEM_TYPE), Pin("bRandom", BOOL)],
                     outputs=[struct_pin("Colour", LINEAR_COLOR, "out"), obj_pin("Icon", TEXTURE_2D, "out")], pure=True)
    g.link(cast, as_pin(BP_GM), look, "self")
    g.link(g.var_get("ItemType", "byte", ITEM_ENUM), "ItemType", look, "Type")
    g.link(g.var_get("bRandom", BOOL), "bRandom", look, "bRandom")
    keep = g.var_set("LootColour", STRUCT, sub_object=struct_ref(LINEAR_COLOR))
    g.link(look, "Colour", keep, "LootColour")
    g.link(cast, "then", keep, "execute")

    def colour():
        return (g.var_get("LootColour", STRUCT, struct_ref(LINEAR_COLOR)), "LootColour")

    sets = []
    for var in ("StripeMID", "LidStripeMID"):  # M_DF_Surface: EmissiveColor's alpha (1) switches it on; Tint the stripe's lit colour
        sets += [_mid_param(g, var, "Vector", "EmissiveColor", colour()), _mid_param(g, var, "Vector", "Tint", colour()),
                 _mid_param(g, var, "Scalar", "Glow", (g.var_get("StripeGlow", FLOAT), "StripeGlow"))]
    sets += [_mid_param(g, "IconMID", "Texture", "Icon", (look, "Icon")), _mid_param(g, "IconMID", "Vector", "Color", colour()),
             _mid_param(g, "BeaconMID", "Vector", "Color", colour())]
    g.exec(keep, *sets)

    g = bp.function("ShowLook", doc="Shows or hides the crate and everything on it (Lid, Icon, Beacon).", inputs=["bShown:bool"])
    vis = g.call_on(SCENE_COMP, "SetVisibility", inputs=[Pin("bNewVisibility", BOOL), Pin("bPropagateToChildren", BOOL, default="true")])
    g.link(g.var_get("Crate", OBJECT, cls_ref(STATIC_MESH_COMP)), "Crate", vis, "self")
    g.link_entry("bShown", vis, "bNewVisibility")
    g.link_entry("then", vis, "execute")

    g = bp.function("BobIcon", doc="The icon floats at IconHeight, bobbing IconBobHeight (peak to peak) on an IconBobPeriod cycle.")
    phase = math2(g, "Multiply_FloatFloat", FLOAT, b="6.283185")
    g.link(game_time(g), "ReturnValue", phase, "A")
    period = g.call_static(MATH, "FMax", inputs=[Pin("A", FLOAT), Pin("B", FLOAT, default="0.01")], outputs=[Pin("ReturnValue", FLOAT, "out")], pure=True)
    g.link(g.var_get("IconBobPeriod", FLOAT), "IconBobPeriod", period, "A")
    angle = math2(g, "Divide_FloatFloat", FLOAT)
    g.link(phase, "ReturnValue", angle, "A")
    g.link(period, "ReturnValue", angle, "B")
    sine = g.call_static(MATH, "Sin", inputs=[Pin("A", FLOAT)], outputs=[Pin("ReturnValue", FLOAT, "out")], pure=True)
    g.link(angle, "ReturnValue", sine, "A")
    half = math2(g, "Multiply_FloatFloat", FLOAT, b="0.5")
    g.link(g.var_get("IconBobHeight", FLOAT), "IconBobHeight", half, "A")
    swing = math2(g, "Multiply_FloatFloat", FLOAT)
    g.link(sine, "ReturnValue", swing, "A")
    g.link(half, "ReturnValue", swing, "B")
    z = math2(g, "Add_FloatFloat", FLOAT)
    g.link(g.var_get("IconHeight", FLOAT), "IconHeight", z, "A")
    g.link(swing, "ReturnValue", z, "B")
    at = g.call_static(MATH, "MakeVector", inputs=[Pin("X", FLOAT, default="0.0"), Pin("Y", FLOAT, default="0.0"), Pin("Z", FLOAT)],
                       outputs=[struct_pin("ReturnValue", VECTOR, "out")], pure=True)
    g.link(z, "ReturnValue", at, "Z")
    move = g.call_on(SCENE_COMP, "K2_SetRelativeLocation",
                     inputs=[struct_pin("NewLocation", VECTOR), Pin("bSweep", BOOL, default="false"), Pin("bTeleport", BOOL, default="false")],
                     outputs=[struct_pin("SweepHitResult", HIT_RESULT, "out")])
    g.link(g.var_get("Icon", OBJECT, cls_ref(BILLBOARD_COMP)), "Icon", move, "self")
    g.link(at, "ReturnValue", move, "NewLocation")
    g.link_entry("then", move, "execute")

    add_lid_pop_functions(bp)


def _lid_pose(g: Graph, loc_src, rot_src) -> Node:
    """Lid.K2_SetRelativeLocationAndRotation(loc, rot) (relative to the Crate's Lid socket; impure). None = (0, 0, 0)."""
    n = g.call_on(SCENE_COMP, "K2_SetRelativeLocationAndRotation",
                  inputs=[struct_pin("NewLocation", VECTOR, default=None if loc_src else "0,0,0"),
                          struct_pin("NewRotation", ROTATOR, default=None if rot_src else "0,0,0"),
                          Pin("bSweep", BOOL, default="false"), Pin("bTeleport", BOOL, default="false")],
                  outputs=[struct_pin("SweepHitResult", HIT_RESULT, "out")])
    g.link(g.var_get("Lid", OBJECT, cls_ref(STATIC_MESH_COMP)), "Lid", n, "self")
    if loc_src:
        g.link(loc_src[0], loc_src[1], n, "NewLocation")
    if rot_src:
        g.link(rot_src[0], rot_src[1], n, "NewRotation")
    return n


def _lid_shown(g: Graph, value: str) -> Node:
    n = g.call_on(SCENE_COMP, "SetVisibility", inputs=[Pin("bNewVisibility", BOOL, default=value), Pin("bPropagateToChildren", BOOL, default="false")])
    g.link(g.var_get("Lid", OBJECT, cls_ref(STATIC_MESH_COMP)), "Lid", n, "self")
    return n


def add_lid_pop_functions(bp: Blueprint) -> None:
    """Fix round 1 (spec §7.4 "On Pickup: the lid pops off"): PopLid starts it, TickLidPop lifts and tumbles the lid for
    LidPopSeconds and then hides it and the actor, RestLid puts it back on its socket (Reset)."""
    g = bp.function("PopLid", doc="The lid pops off: it shows (the crate, icon and beacon are hidden) and TickLidPop moves it from now.")
    shown = _lid_shown(g, "true")
    g.link_entry("then", shown, "execute")
    g.exec(shown, g.var_set("LidPopAge", FLOAT, default="0.0"), g.var_set("bLidPopping", BOOL, default="true"))

    g = bp.function("TickLidPop", doc="While the lid pops: t = LidPopAge / LidPopSeconds; it rises LidPopHeight x (1 - (1 - t)^2), drifts "
                    "LidPopDrift x t along +X and tilts LidPopTilt x t; at t = 1 it hides, and so does the collected actor.",
                    inputs=["DeltaSeconds:float"])
    b = g.branch()
    g.note(b, "the lid popping?")
    g.link(g.var_get("bLidPopping", BOOL), "bLidPopping", b, "Condition")
    g.link_entry("then", b, "execute")
    older = math2(g, "Add_FloatFloat", FLOAT)
    g.link(g.var_get("LidPopAge", FLOAT), "LidPopAge", older, "A")
    g.link_entry("DeltaSeconds", older, "B")
    age = g.var_set("LidPopAge", FLOAT)
    g.link(older, "ReturnValue", age, "LidPopAge")
    g.link(b, "then", age, "execute")
    span = g.call_static(MATH, "FMax", inputs=[Pin("A", FLOAT), Pin("B", FLOAT, default="0.01")], outputs=[Pin("ReturnValue", FLOAT, "out")], pure=True)
    g.link(g.var_get("LidPopSeconds", FLOAT), "LidPopSeconds", span, "A")
    frac = math2(g, "Divide_FloatFloat", FLOAT)
    g.link(age, "Output_Get", frac, "A")
    g.link(span, "ReturnValue", frac, "B")
    t_ = g.call_static(MATH, "FClamp", inputs=[Pin("Value", FLOAT), Pin("Min", FLOAT, default="0.0"), Pin("Max", FLOAT, default="1.0")],
                       outputs=[Pin("ReturnValue", FLOAT, "out")], pure=True)
    g.link(frac, "ReturnValue", t_, "Value")
    left = math2(g, "Subtract_FloatFloat", FLOAT, a="1.0")
    g.link(t_, "ReturnValue", left, "B")
    sq = math2(g, "Multiply_FloatFloat", FLOAT)
    g.link(left, "ReturnValue", sq, "A")
    g.link(left, "ReturnValue", sq, "B")
    ease = math2(g, "Subtract_FloatFloat", FLOAT, a="1.0")
    g.link(sq, "ReturnValue", ease, "B")

    def scaled(var, src):
        n = math2(g, "Multiply_FloatFloat", FLOAT)
        g.link(g.var_get(var, FLOAT), var, n, "A")
        g.link(src[0], src[1], n, "B")
        return (n, "ReturnValue")

    where = g.call_static(MATH, "MakeVector", inputs=[Pin("X", FLOAT), Pin("Y", FLOAT, default="0.0"), Pin("Z", FLOAT)],
                          outputs=[struct_pin("ReturnValue", VECTOR, "out")], pure=True)
    drift, up = scaled("LidPopDrift", (t_, "ReturnValue")), scaled("LidPopHeight", (ease, "ReturnValue"))
    g.link(drift[0], drift[1], where, "X")
    g.link(up[0], up[1], where, "Z")
    tilt = g.call_static(MATH, "MakeRotator", inputs=[Pin("Roll", FLOAT, default="0.0"), Pin("Pitch", FLOAT), Pin("Yaw", FLOAT, default="0.0")],
                         outputs=[struct_pin("ReturnValue", ROTATOR, "out")], pure=True)
    pitch = scaled("LidPopTilt", (t_, "ReturnValue"))
    g.link(pitch[0], pitch[1], tilt, "Pitch")
    pose = _lid_pose(g, (where, "ReturnValue"), (tilt, "ReturnValue"))
    g.exec(age, pose)
    done = compare(g, "GreaterEqual_FloatFloat", FLOAT, b="1.0")
    g.link(t_, "ReturnValue", done, "A")
    bd = g.branch()
    g.note(bd, "the pop over? hide the lid and the collected crate")
    g.link(done, "ReturnValue", bd, "Condition")
    g.exec(pose, bd)
    stop = g.var_set("bLidPopping", BOOL, default="false")
    g.link(bd, "then", stop, "execute")
    hide = g.call_self_native(ACTOR, "SetActorHiddenInGame", inputs=[Pin("bNewHidden", BOOL, default="true")])
    g.exec(stop, _lid_shown(g, "false"), hide)

    g = bp.function("RestLid", doc="Ends any pop and puts the lid back on the Crate's Lid socket (its rest transform).")
    stop = g.var_set("bLidPopping", BOOL, default="false")
    g.link_entry("then", stop, "execute")
    g.exec(stop, _lid_pose(g, None, None))


# ---- BP_DFLootBox (spec §3) ----
def build_lootbox() -> Blueprint:
    bp = Blueprint(BP_LOOTBOX, parent=ACTOR, description="A crate collected on touch by a character on foot; fixed or random item; comes "
                                                          "back after a delay. Its stripe, floating icon and beacon pillar show the item's colour.")
    # Phase 7 Task 17 (spec §7.4): SM_DF_Crate (its own slots, scale 1) with SM_DF_CrateLid on its Lid socket, the item's icon on a
    # material billboard (MI_DF_Icon; a 70 cm square facing the camera) floating over the lid, and the 30 m beacon pillar
    # (MI_DF_FxBeacon, additive, faded out within 10 m by its NearFade) standing on the icon's top. ApplyLook tints them.
    bp.component("Crate", STATIC_MESH_COMP, **{"static_mesh": SM_CRATE, "relative_scale3d": {"vector": [1.0, 1.0, 1.0]},
                                             "call:set_collision_profile_name": "OverlapAllDynamic",  # cars drive through it
                                             "override_materials": []})
    bp.component("Trigger", SPHERE_COMP, "Crate", **{"sphere_radius": 150.0, "absolute_scale": True,
                                                   "call:set_collision_profile_name": "OverlapOnlyPawn"})
    bp.component("Lid", STATIC_MESH_COMP, "Crate", socket="Lid", static_mesh=SM_CRATE_LID, **NO_COLLISION)
    bp.component("Icon", BILLBOARD_COMP, "Crate", relative_location={"vector": [0.0, 0.0, ICON_Z]},
                 elements=[{"struct": "MaterialSpriteElement", "props": {"material": MI_ICON, "base_size_x": ICON_HALF,
                                                                         "base_size_y": ICON_HALF, "size_is_in_screen_space": False}}],
                 **NO_COLLISION)
    bp.component("Beacon", STATIC_MESH_COMP, "Crate", static_mesh=SM_BEACON, relative_location={"vector": [0.0, 0.0, BEACON_Z]},
                 cast_shadow=False, **NO_COLLISION)
    L = "Dead Fire|Loot"
    bp.variable("ItemType", enum_spec(E_ITEM_TYPE), enum_value(ITEM_BOOST), L, editable=True)
    bp.variable("Charges", "int", "0", L, editable=True)  # 0 = the type's box charges (GetItemInfo)
    bp.variable("bRandom", "bool", "false", L, editable=True)
    bp.variable("bRespawns", "bool", "true", L, editable=True)
    bp.variable("RespawnSeconds", "float", "30", L, editable=True)
    bp.variable("bCollected", "bool", "false", L)
    bp.variable("CollectedTime", "float", "-1", L)
    bp.dispatcher("OnLootCollected", ["Character:" + obj_spec(BP_CHARACTER), "Type:" + enum_spec(E_ITEM_TYPE)])
    # Phase 7 Task 17 (spec §7.4): the look's tunables (the stripe's glow, the icon's float and bob) and sounds, and its dynamic
    # materials and colour (state, made by ApplyLook)
    LL = "Dead Fire|Loot Look"
    for name, default in (("StripeGlow", 2.0), ("IconHeight", ICON_Z), ("IconBobHeight", ICON_BOB), ("IconBobPeriod", 2.0),
                          # fix round 1 (spec §7.4 "the lid pops off"): the lid's lift, tilt (degrees) and drift on a pickup
                          ("LidPopSeconds", LID_POP_SECONDS), ("LidPopHeight", 60.0), ("LidPopTilt", 40.0), ("LidPopDrift", 25.0)):
        bp.variable(name, "float", repr(default), LL, editable=True)
        bp.default(name, default)
    for name, sound in (("LootOpenSound", SW_LOOT_OPEN), ("DenySound", SW_DENY)):
        bp.variable(name, "object:" + SOUND_BASE, "", LL, editable=True)
        bp.default(name, sound)
    for name in ("StripeMID", "LidStripeMID", "IconMID", "BeaconMID"):
        bp.variable(name, "object:" + MID, "", LL)
    bp.variable("LootColour", "struct:" + LINEAR_COLOR, "", LL)  # the colour the crate shows (GetItemLook), for the loot burst
    bp.variable("bLidPopping", "bool", "false", LL)  # fix round 1: the lid's pop is running (TickLidPop)
    bp.variable("LidPopAge", "float", "0", LL)

    def item_type(g):
        return g.var_get("ItemType", "byte", ITEM_ENUM)

    def loot_sound(g, var):
        return play_sound_at(g, (g.var_get(var, OBJECT, cls_ref(SOUND_BASE)), var), (self_actor_location(g), "ReturnValue"))

    def gm_cast(g, prev):
        gm = get_game_mode(g)
        cast = cast_to(g, BP_GM)
        g.link(gm, "ReturnValue", cast, "Object")
        g.link(prev[0], prev[1], cast, "execute")
        return cast

    # ResolveCharges() -> Charges: the instance's Charges when set, else the type's box charges
    g = bp.function("ResolveCharges", doc="This crate's Charges when set, else the type's charges per crate.", outputs=["Charges:int"], pure=True)
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
    g = bp.function("Pickup", doc="An alive, un-stowed, controller-owned character takes the item through GrantItem.", inputs=["Character:" + obj_spec(BP_CHARACTER)], outputs=["ReturnValue:bool"])
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
    deny = loot_sound(g, "DenySound")  # Phase 7 Task 17: the item fits nothing (GrantItem refused it)
    g.link(bg, "else", deny, "execute")
    g.exec(deny, g.function_result([Pin("ReturnValue", BOOL, default="false")]))
    mark = g.var_set("bCollected", BOOL, default="true")
    g.link(bg, "then", mark, "execute")
    now = game_time(g)
    stamp = g.var_set("CollectedTime", FLOAT)
    g.link(now, "ReturnValue", stamp, "CollectedTime")
    nocol = g.call_self_native(ACTOR, "SetActorEnableCollision", inputs=[Pin("bNewActorEnableCollision", BOOL, default="false")])
    # Phase 7 Task 17 (spec §7.4): the crate, icon and beacon hide, the lid pops off (TickLidPop hides it and the actor when its pop
    # ends), the loot burst in the crate's colour and the opening sound
    gone = g.call_self("ShowLook", inputs=[Pin("bShown", BOOL, default="false")])
    pop = g.call_self("PopLid")
    burst_first, burst_last, _ = spawn_fx(g, BP_FX_LOOT_BURST, transform_at(g, (self_actor_location(g), "ReturnValue")),
                                          tint_src=(g.var_get("LootColour", STRUCT, struct_ref(LINEAR_COLOR)), "LootColour"))
    g.exec(mark, stamp, nocol, gone, pop, burst_first)
    opened = loot_sound(g, "LootOpenSound")
    fire = g.call_delegate("OnLootCollected", [obj_pin("Character", CC), enum_pin("Type", E_ITEM_TYPE)])
    g.link_entry("Character", fire, "Character")
    it2 = item_type(g)
    g.link(it2, "ItemType", fire, "Type")
    g.exec(burst_last, opened, fire)
    g.exec(fire, g.function_result([Pin("ReturnValue", BOOL, default="true")]))

    # Reset(): roll a type when random, then show and collide again
    g = bp.function("Reset", doc="Rolls a random type when asked, then shows and collides again.")
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
    g.exec(clear, show, col, g.call_self("RestLid"), g.call_self("ShowLook", inputs=[Pin("bShown", BOOL, default="true")]),
           g.call_self("ApplyLook"))

    add_look_functions(bp)

    g = bp.event_graph()
    g.section("Begin Play: roll a random item when asked (Reset ends with ApplyLook), else show the item's look")
    bpl = g.begin_play(col=0, row=1)
    rnd = g.var_get("bRandom", BOOL, col=0, row=2)
    b = g.branch(col=1, row=1)
    g.link(rnd, "bRandom", b, "Condition")
    g.exec(bpl, b)
    rs = g.call_self("Reset", col=2, row=1)
    g.link(b, "then", rs, "execute")
    g.link(b, "else", g.call_self("ApplyLook"), "execute")

    g.section("Tick: the icon bobs, the lid pops; come back RespawnSeconds after being collected")
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
    lid_tick = g.call_self("TickLidPop", inputs=[Pin("DeltaSeconds", FLOAT)])
    g.link(tick, "DeltaSeconds", lid_tick, "DeltaSeconds")
    g.exec(tick, g.call_self("BobIcon"), lid_tick, bt)
    rs2 = g.call_self("Reset", col=2, row=3)
    g.link(bt, "then", rs2, "execute")

    g.section("Overlap: a character on foot collects the crate")
    ov = g.event(ACTOR, "ReceiveActorBeginOverlap", [obj_pin("OtherActor", ACTOR)], col=0, row=5)
    cc = cast_to(g, BP_CHARACTER, col=1, row=5)
    g.link(ov, "OtherActor", cc, "Object")
    g.exec(ov, cc)
    pk = g.call_self("Pickup", inputs=[obj_pin("Character", CC)], outputs=[Pin("ReturnValue", BOOL, "out")], col=2, row=5)
    g.link(cc, as_pin(BP_CHARACTER), pk, "Character")
    g.link(cc, "then", pk, "execute")
    return bp


# ---- BP_DFDestructible (spec §6): a rock wall that only explosives demolish ----
def _rock_point(g: Graph, cell_src=None, cell=None) -> Node:
    """RockPoint(Cell) inline (pure): the world point at Cell (-1..1 per axis: a fraction of the half-extent from the centre) of
    the Rock mesh's bounds, through the Rock's world transform. cell_src: (node, pin) of the fraction, or the literal `cell`."""
    rock = g.var_get("Rock", OBJECT, cls_ref(STATIC_MESH_COMP))
    mesh = g.var_get_on(STATIC_MESH_COMP, "StaticMesh", OBJECT, cls_ref(STATIC_MESH))
    g.link(rock, "Rock", mesh, "self")
    bounds = g.call_on(STATIC_MESH, "GetBounds", outputs=[struct_pin("ReturnValue", BOX_SPHERE_BOUNDS, "out")], pure=True)
    g.link(mesh, "StaticMesh", bounds, "self")
    brk = g.break_struct(BOX_SPHERE_BOUNDS, [struct_pin("Origin", VECTOR, "out"), struct_pin("BoxExtent", VECTOR, "out")])
    g.link(bounds, "ReturnValue", brk, BOX_SPHERE_BOUNDS.rsplit(".", 1)[1])
    off = g.call_static(MATH, "Multiply_VectorVector", inputs=[struct_pin("A", VECTOR), struct_pin("B", VECTOR, default=None if cell_src else vec(*cell))],
                        outputs=[struct_pin("ReturnValue", VECTOR, "out")], pure=True)
    g.link(brk, "BoxExtent", off, "A")
    if cell_src:
        g.link(cell_src[0], cell_src[1], off, "B")
    local = g.call_static(MATH, "Add_VectorVector", inputs=[struct_pin("A", VECTOR), struct_pin("B", VECTOR)],
                          outputs=[struct_pin("ReturnValue", VECTOR, "out")], pure=True)
    g.link(brk, "Origin", local, "A")
    g.link(off, "ReturnValue", local, "B")
    xf = g.call_on(SCENE_COMP, "K2_GetComponentToWorld", outputs=[struct_pin("ReturnValue", TRANSFORM, "out")], pure=True)
    g.link(g.var_get("Rock", OBJECT, cls_ref(STATIC_MESH_COMP)), "Rock", xf, "self")
    at = g.call_static(MATH, "TransformLocation", inputs=[struct_pin("T", TRANSFORM), struct_pin("Location", VECTOR)],
                       outputs=[struct_pin("ReturnValue", VECTOR, "out")], pure=True)
    g.link(xf, "ReturnValue", at, "T")
    g.link(local, "ReturnValue", at, "Location")
    return at


def _chunk_scale(g: Graph) -> Node:
    """MakeVector(s, s, s), s = the smallest side of a grid cell (half the Rock's world size per axis: mesh half-extent x world
    scale) over the chunk mesh's longest side, so the eight chunks fit their cells."""
    rock = g.var_get("Rock", OBJECT, cls_ref(STATIC_MESH_COMP))
    mesh = g.var_get_on(STATIC_MESH_COMP, "StaticMesh", OBJECT, cls_ref(STATIC_MESH))
    g.link(rock, "Rock", mesh, "self")
    bounds = g.call_on(STATIC_MESH, "GetBounds", outputs=[struct_pin("ReturnValue", BOX_SPHERE_BOUNDS, "out")], pure=True)
    g.link(mesh, "StaticMesh", bounds, "self")
    brk = g.break_struct(BOX_SPHERE_BOUNDS, [struct_pin("BoxExtent", VECTOR, "out")])
    g.link(bounds, "ReturnValue", brk, BOX_SPHERE_BOUNDS.rsplit(".", 1)[1])
    scale = g.call_on(SCENE_COMP, "K2_GetComponentScale", outputs=[struct_pin("ReturnValue", VECTOR, "out")], pure=True)
    g.link(g.var_get("Rock", OBJECT, cls_ref(STATIC_MESH_COMP)), "Rock", scale, "self")
    cell = g.call_static(MATH, "Multiply_VectorVector", inputs=[struct_pin("A", VECTOR), struct_pin("B", VECTOR)],
                         outputs=[struct_pin("ReturnValue", VECTOR, "out")], pure=True)
    g.link(brk, "BoxExtent", cell, "A")
    g.link(scale, "ReturnValue", cell, "B")
    xyz = g.call_static(MATH, "BreakVector", inputs=[struct_pin("InVec", VECTOR)],
                        outputs=[Pin("X", FLOAT, "out"), Pin("Y", FLOAT, "out"), Pin("Z", FLOAT, "out")], pure=True)
    g.link(cell, "ReturnValue", xyz, "InVec")
    m1 = math2(g, "FMin", FLOAT)
    g.link(xyz, "X", m1, "A")
    g.link(xyz, "Y", m1, "B")
    m2 = math2(g, "FMin", FLOAT)
    g.link(m1, "ReturnValue", m2, "A")
    g.link(xyz, "Z", m2, "B")
    s = math2(g, "Divide_FloatFloat", FLOAT, b="%f" % ROCK_CHUNK_CM)
    g.link(m2, "ReturnValue", s, "A")
    v = g.call_static(MATH, "Conv_FloatToVector", inputs=[Pin("InFloat", FLOAT)], outputs=[struct_pin("ReturnValue", VECTOR, "out")], pure=True)
    g.link(s, "ReturnValue", v, "InFloat")
    return v


def add_chunk_function(bp: Blueprint) -> None:
    """SpawnChunk(Cell): one BP_DFDebris at RockPoint(Cell), turned as the rock, sized to its cell, pushed DebrisSpeed cm/s straight
    out from the rock's centre (a velocity change, whatever the chunk's mass)."""
    g = bp.function("SpawnChunk", inputs=["Cell:struct:" + VECTOR],
                    doc="One rock chunk (BP_DFDebris) at Cell of the Rock's bounds, sized to its grid cell and pushed DebrisSpeed cm/s "
                        "away from the rock's centre.")
    at = _rock_point(g, cell_src=("entry", "Cell"))
    rot = g.call_self_native(ACTOR, "K2_GetActorRotation", outputs=[struct_pin("ReturnValue", ROTATOR, "out")], pure=True)
    xf = g.call_static(MATH, "MakeTransform", inputs=[struct_pin("Location", VECTOR), struct_pin("Rotation", ROTATOR), struct_pin("Scale", VECTOR)],
                       outputs=[struct_pin("ReturnValue", TRANSFORM, "out")], pure=True)
    g.link(at, "ReturnValue", xf, "Location")
    g.link(rot, "ReturnValue", xf, "Rotation")
    g.link(_chunk_scale(g), "ReturnValue", xf, "Scale")
    spawn = g.spawn_actor(DEBRISC)
    g.link(xf, "ReturnValue", spawn, "SpawnTransform")
    g.link_entry("then", spawn, "execute")
    away = g.call_static(MATH, "Subtract_VectorVector", inputs=[struct_pin("A", VECTOR), struct_pin("B", VECTOR)],
                         outputs=[struct_pin("ReturnValue", VECTOR, "out")], pure=True)
    g.link(at, "ReturnValue", away, "A")
    g.link(_rock_point(g, cell=(0.0, 0.0, 0.0)), "ReturnValue", away, "B")
    unit = g.call_static(MATH, "Normal", inputs=[struct_pin("A", VECTOR), Pin("Tolerance", FLOAT, default="0.0001")],
                         outputs=[struct_pin("ReturnValue", VECTOR, "out")], pure=True)
    g.link(away, "ReturnValue", unit, "A")
    push = g.call_static(MATH, "Multiply_VectorFloat", inputs=[struct_pin("A", VECTOR), Pin("B", FLOAT)],
                         outputs=[struct_pin("ReturnValue", VECTOR, "out")], pure=True)
    g.link(unit, "ReturnValue", push, "A")
    g.link(g.var_get("DebrisSpeed", FLOAT), "DebrisSpeed", push, "B")
    chunk = g.var_get_on(DEBRISC, "Chunk", OBJECT, cls_ref(STATIC_MESH_COMP))
    g.link(spawn, "ReturnValue", chunk, "self")
    kick = g.call_on(PRIMITIVE, "AddImpulse", inputs=[struct_pin("Impulse", VECTOR), Pin("BoneName", NAME, default="None"),
                                                      Pin("bVelChange", BOOL, default="true")])
    g.link(chunk, "Chunk", kick, "self")
    g.link(push, "ReturnValue", kick, "Impulse")
    g.exec(spawn, kick)


def build_destructible() -> Blueprint:
    bp = Blueprint(BP_DESTRUCTIBLE, parent=ACTOR, description="A rock wall only explosives demolish (it breaks into eight physics chunks); "
                   "it closes the shortcut road.")
    # Phase 7 Task 21 (spec §8.2): SM_DF_RockWall keeps the unit contract (a 100 cm cube, centred) with its own MI_DF_Rock; Rock is
    # the root, so the actor stands at the wall's centre (the level builder raises it by half its height onto the road)
    bp.component("Rock", STATIC_MESH_COMP, **{"static_mesh": SM_ROCK_WALL, "relative_scale3d": {"vector": [3.0, 3.0, 3.0]},
                                            "call:set_collision_profile_name": "BlockAllDynamic", "override_materials": []})
    D = "Dead Fire|Destructible"
    bp.variable("Health", "float", "60", D, editable=True)
    bp.variable("bExplosivesOnly", "bool", "true", D, editable=True)
    bp.variable("bDestroyed", "bool", "false", D)
    bp.variable("DebrisSpeed", "float", "%g" % DEBRIS_SPEED, D, editable=True)  # cm/s, each chunk's push out from the centre
    bp.default("DebrisSpeed", DEBRIS_SPEED)
    bp.dispatcher("OnDestructibleDestroyed", [])
    add_chunk_function(bp)

    # Demolish(): once; effects-only explosion at the wall's foot, hidden and non-colliding (the road behind it is open), and the
    # eight chunks (a 2 x 2 x 2 grid over its bounds) flying out
    g = bp.function("Demolish", doc="Once: effects-only explosion at the wall's foot, hidden and non-colliding (the road behind is open), "
                    "and eight physics chunks (a 2 x 2 x 2 grid over its bounds) pushed out.")
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
    foot = _rock_point(g, cell=(0.0, 0.0, -1.0))  # the explosion effect stands on the ground (the actor is the wall's centre)
    boom = g.call_on(GMC, "SpawnExplosion", inputs=[struct_pin("Location", VECTOR), Pin("Damage", FLOAT, default="0.0"),
                                                    Pin("Radius", FLOAT, default="0.0"), obj_pin("InstigatedBy", CONTROLLER),
                                                    obj_pin("Causer", ACTOR), Pin("bBlowTires", BOOL, default="false")])
    g.link(cast, as_pin(BP_GM), boom, "self")
    g.link(foot, "ReturnValue", boom, "Location")
    me = g.self_node()
    g.link(me, "self", boom, "Causer")
    g.link(cast, "then", boom, "execute")
    hide = g.call_self_native(ACTOR, "SetActorHiddenInGame", inputs=[Pin("bNewHidden", BOOL, default="true")])
    g.exec(boom, hide)
    g.link(cast, "CastFailed", hide, "execute")
    nocol = g.call_self_native(ACTOR, "SetActorEnableCollision", inputs=[Pin("bNewActorEnableCollision", BOOL, default="false")])
    chunks = [g.call_self("SpawnChunk", inputs=[struct_pin("Cell", VECTOR, default=vec(*cell))]) for cell in ROCK_CHUNK_CELLS]
    fire = g.call_delegate("OnDestructibleDestroyed")
    me2 = g.self_node()
    log = log_line(g, "destructible demolished ", name_of(g, (me2, "self")))
    g.exec(hide, nocol, *chunks, fire, log)  # the chunks after the collision is off: they start inside the wall

    g = bp.event_graph()
    g.section("Any damage: only explosive damage counts while bExplosivesOnly; at 0 demolish")
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
