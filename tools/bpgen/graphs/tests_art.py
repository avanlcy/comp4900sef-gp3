"""Phase 7 FT_DFArt_* tests (plan docs/superpowers/plans/2026-10-30-phase7-art-feel.md, Task 13 onward; spec §6.1): the car
visuals on BP_DFVehicle. The physics mesh is hidden, and the Body and the four wheels are static meshes on it, each wheel on its
bone's socket. The tests also cover the blown-tyre rim, the charred wreck, the rivals' gang paint, and the roof weapon that shows
the held item. Task 14 (spec §6.2): the on-foot character's helmet, vest and rifle on the mannequin's bones, its materials, and
the weapon's VisualOrigin. Task 15 (spec §7.1): the BP_DFFx effect family grows and fades its shells, destroys itself, and the
tracer spans its two ends; df.spawn_fx is the tinted spawn route (spawn, then SetTint in the same frame). Task 16 (spec §7.2,
§7.3): shots, explosions, tyre pops and smoke. Task 17 (spec §7.4, §7.5): the crate's colour, icon and beacon, its parts hidden
when collected, the shield bubble and the boost flames while they run, and the bomb's blink rate. Task 18 (spec §7.6): the race
HUD's hit marker, crate prompt and damage vignette (FT_DFHUD_*; the item row's icons are tests_items.py's). Task 21 (spec §8.2,
§8.3): only the player's next gate glows, the rock wall breaks into physics chunks that expire (and RestartRace sweeps), and the
scatter actor builds one instance per transform. Same shape as tests_menu.py; the helpers come from tests.py, tests_items.py,
tests_ai.py, tests_drive.py and tests_menu.py.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, ".."))
from bpgen import cls_ref, struct_ref  # noqa: E402
from df import (BOOL, BP_AI, BP_GM, BP_VEHICLE, BPC_RACER, BYTE, CAR_WHEELS, CONTROLLER, FLOAT, INT, ITEM_GUN, ITEM_RPG,  # noqa: E402
                MATERIAL_INTERFACE, MATH, MI_PAINT_CHARRED, MI_PAINT_GANG, NAME, OBJECT, OUT, ROTATOR, SCENE_COMP, SKEL_MESH_COMP,
                SM_EXHAUST_FLAME, SM_LIGHT_BAR, SM_ROOF_GUN, SM_ROOF_LAUNCHER, SM_SHIELD_BUBBLE, SM_WHEEL, SM_WHEEL_RIM,
                STATIC_MESH, STATIC_MESH_COMP, STRING, STRUCT, TRANSFORM, VECTOR, VEHICLES, Pin, art_material, art_mesh, as_pin,
                gen, get_game_mode, log_line, obj_pin, struct_pin)
from df import (BP_CHARACTER, BPC_WEAPON, CHARACTER_GEAR, MI_MANNEQUIN_BODY, MI_MANNEQUIN_TRIM, PRIMITIVE,  # noqa: E402  (Task 14)
                native_enum_pin)
from df import (ACTOR, BP_FX, BP_FX_EXPLOSION, BP_FX_LOOT_BURST, BP_FX_TRACER, FX_CHILDREN, LINEAR_COLOR, MID,  # noqa: E402  (Task 15)
                get_all_actors_of_class, name_of, spawn_fx)
from df import (BP_FX_MUZZLE, BP_FX_PUFF, BP_FX_SPARKS, DECAL_COMP, FX_VIEW_RADIUS, GAMEPLAY, MI_SCORCH, PAWN,  # noqa: E402  (Task 16)
                SCORCH_LIFE, SCORCH_SIZE, obj_spec)
from tests import FT, T, race_context, spawn_character, spawn_vehicle, tire  # noqa: E402
from tests_ai import ai_car, ai_controllers, despawn_npcs, flog  # noqa: E402
from tests_drive import (SETTLE, arcade_T, arcade_finish, check, fop, same_asset, set_input, speed_kph,  # noqa: E402
                         spawn_on_strip, tick_after_test)
from tests_drive import (DRIVE_DOC, actor_vec, greater_int, scaled, set_gear, set_speed, set_velocity, store, tvar,  # noqa: E402  (Task 16)
                         vec_part)
from tests_items import destroy, enum_int, grant, pawn_car, use_item  # noqa: E402
from tests_items import count_actors, explode, invalid  # noqa: E402  (Task 16)
from tests_menu import body_material, spawn_class  # noqa: E402
from df import MI_TRIM_GANG, TRIM_SLOT  # noqa: E402  (Task 22)
from df import (BILLBOARD_COMP, BOMB_LAMP_SLOT, BP_BOMB, BP_LOOTBOX, E_ITEM_TYPE, ITEM_BOOST, ITEM_LOOK, ITEM_SHIELD,  # noqa: E402  (Task 17)
                RANDOM_LOOK, SHIELD_BUBBLE_AT, SM_BOMB, TEXTURE, TEXTURE_2D, art_icon, enum_pin, linear_colour)
from tests_items import owned_character, spawn_bomb, spawn_crate  # noqa: E402  (Task 17)
from df import ACTOR, BOMB_TRIGGER_R, BOMB_TRIGGER_Z, CRATE_HALF_HEIGHT, LID_POP_SECONDS, SPHERE_COMP  # noqa: E402  (Task 17 fix round 1)
from df import BP_PC, HIT_RESULT, IMAGE, WBP_HUD  # noqa: E402  (Task 18)
from hud import CRATE_PROMPT, DAMAGE_SECONDS, HIT_MARKER_SCALE, HIT_MARKER_SECONDS, RED as HUD_RED, WHITE as HUD_WHITE  # noqa: E402  (Task 18)
from tests_items import TEXT_BLOCK, WIDGET_W, hud_part, move_to, widget_shown, widgets  # noqa: E402  (Task 18)
from df import (BP_CHECKPOINT, BP_DEBRIS, BP_DESTRUCTIBLE, BP_SCATTER, COLLISION_CHANNEL, DEBRIS_LIFE, GATE_GLOW_OFF,  # noqa: E402  (Task 21)
                GATE_GLOW_ON, HISM_COMP, ISM_COMP, ROCK_CHUNK_CELLS, ROCK_CHUNK_CM, SCATTER_CULL_CM, SM_ROCK_CHUNK,
                asset_object)
from tests import notify  # noqa: E402  (Task 21)

VC, GMC, RC, AIC = gen(BP_VEHICLE), gen(BP_GM), gen(BPC_RACER), gen(BP_AI)
CC, WC = gen(BP_CHARACTER), gen(BPC_WEAPON)
PLAYER_CAMERA_MANAGER = "/Script/Engine.PlayerCameraManager"
SKINNED_MESH_COMP = "/Script/Engine.SkinnedMeshComponent"
TICK_OPTION = "Enum'\"/Script/Engine.EVisibilityBasedAnimTickOption\"'"
ALWAYS_TICK_POSE_AND_REFRESH_BONES = 0  # EVisibilityBasedAnimTickOption's first value
WHEEL_TOLERANCE_CM = 5.0
DRIVE_SECONDS = 2.0


# ---- helpers ----
def comp(t: T, car, name, cls=STATIC_MESH_COMP):
    """One of the car's components (Body, WheelFL, RoofWeapon, ...)."""
    return t.get(VC, name, OBJECT, car, sub=cls_ref(cls))


def car_mesh(t: T, car):
    return comp(t, car, "Mesh", SKEL_MESH_COMP)


def visible(t: T, component):
    n = t.g.call_on(SCENE_COMP, "IsVisible", outputs=[Pin("ReturnValue", BOOL, "out")], pure=True)
    t.link(component, n, "self")
    return (n, "ReturnValue")


def mesh_of(t: T, component):
    """The static mesh a StaticMeshComponent shows."""
    return t.get(STATIC_MESH_COMP, "StaticMesh", OBJECT, component, sub=cls_ref(STATIC_MESH))


def parent_of(t: T, component):
    n = t.g.call_on(SCENE_COMP, "GetAttachParent", outputs=[obj_pin("ReturnValue", SCENE_COMP, "out")], pure=True)
    t.link(component, n, "self")
    return (n, "ReturnValue")


def socket_is(t: T, component, socket, message):
    """AssertTrue(the component's attach socket name == socket)."""
    n = t.g.call_on(SCENE_COMP, "GetAttachSocketName", outputs=[Pin("ReturnValue", NAME, "out")], pure=True)
    t.link(component, n, "self")
    eq = t.g.call_static(MATH, "EqualEqual_NameName", inputs=[Pin("A", NAME), Pin("B", NAME, default=socket)],
                         outputs=[Pin("ReturnValue", BOOL, "out")], pure=True)
    t.g.link(n, "ReturnValue", eq, "A")
    t.true((eq, "ReturnValue"), message)


def attached(t: T, car, component, parent, socket, what):
    """The component hangs on the car's parent component (Mesh or Body), at the socket ("" = none), at world scale 1 (an
    imported socket carried the FBX unit scale 100 until Task 13; the light bar on Roof came out 100 times too big)."""
    t.same(parent_of(t, component), parent, "%s: attached to %s" % (what, parent[1]))
    socket_is(t, component, socket or "None", "%s: on the socket '%s'" % (what, socket or "None"))
    scale = t.g.call_on(SCENE_COMP, "K2_GetComponentScale", outputs=[struct_pin("ReturnValue", VECTOR, "out")], pure=True)
    t.link(component, scale, "self")
    one = t.g.call_static(MATH, "EqualEqual_VectorVector", inputs=[struct_pin("A", VECTOR), struct_pin("B", VECTOR, default="1,1,1"),
                                                                 Pin("ErrorTolerance", FLOAT, default="0.001")],
                          outputs=[Pin("ReturnValue", BOOL, "out")], pure=True)
    t.g.link(scale, "ReturnValue", one, "A")
    t.true((one, "ReturnValue"), "%s: world scale 1" % what)


def fl_rotation_in_car(t: T, car):
    """WheelFL's world rotation expressed in the car's (Mesh component's) frame: constant for a wheel that only rides along,
    changing while the wheel bone spins and steers. (Its RelativeRotation is relative to the bone socket, so it never changes.)"""
    xf = t.g.call_on(SCENE_COMP, "K2_GetComponentToWorld", outputs=[struct_pin("ReturnValue", TRANSFORM, "out")], pure=True)
    t.link(car_mesh(t, car), xf, "self")
    rot = t.g.call_on(SCENE_COMP, "K2_GetComponentRotation", outputs=[struct_pin("ReturnValue", ROTATOR, "out")], pure=True)
    t.link(comp(t, car, "WheelFL"), rot, "self")
    n = t.g.call_static(MATH, "InverseTransformRotation", inputs=[struct_pin("T", TRANSFORM), struct_pin("Rotation", ROTATOR)],
                        outputs=[struct_pin("ReturnValue", ROTATOR, "out")], pure=True)
    t.g.link(xf, "ReturnValue", n, "T")
    t.g.link(rot, "ReturnValue", n, "Rotation")
    return (n, "ReturnValue")


def rot_str(t: T, src):
    n = t.g.call_static("KismetStringLibrary", "Conv_RotatorToString", inputs=[struct_pin("InRot", ROTATOR)],
                        outputs=[Pin("ReturnValue", STRING, "out")], pure=True)
    t.link(src, n, "InRot")
    return (n, "ReturnValue")


def bind_cleanup(t: T, event_name):
    """The test's first step binds a custom event to OnTestFinished (FinishTest broadcasts it on every finish: a pass, a
    failure, a time-out), so the shared PIE world never keeps what the test changed. Returns the event to chain the clean-up on."""
    t.g.section("Clean-up on every finish (tests share one PIE world)")
    ev = t.g.custom_event(event_name)
    bind = t.step(t.g.add_delegate(FT, "OnTestFinished", "FunctionalTestEventSignature__DelegateSignature", "/Script/FunctionalTesting"))
    t.g.link(ev, "OutputDelegate", bind, "Delegate")
    return ev


# ---- Task 13: the car visuals (spec §6.1) ----
def car_visuals_test():
    t = T("FT_DFArt_CarVisualsAttached", "Spec §6.1, for SEDAN, BRUTE and VIPER: the physics Mesh is hidden but keeps refreshing its bones; "
          "Body (visible, SM_DF_Car_<X>) rides on Mesh; each wheel (SM_DF_Wheel) rides on Mesh at its wheel bone's socket; the light "
          "bar (SEDAN only) and the hidden roof weapon sit on the Body's Roof socket; the shield bubble and the boost flames start hidden. "
          "Every part is at world scale 1.")
    cars = [(row, spawn_class(t, row.asset, dy=dy)) for row, dy in zip(VEHICLES, (-600.0, 0.0, 600.0))]
    for row, car in cars:
        n = row.name
        mesh, body = car_mesh(t, car), comp(t, car, "Body")
        t.false(visible(t, mesh), "%s: the physics mesh (Mesh) is hidden" % n)
        tick = t.get(SKINNED_MESH_COMP, "VisibilityBasedAnimTickOption", BYTE, mesh, sub=TICK_OPTION)
        t.eq_int(enum_int(t, tick), ALWAYS_TICK_POSE_AND_REFRESH_BONES, "%s: Mesh ticks its pose and refreshes its bones while hidden" % n)
        t.true(visible(t, body), "%s: Body is visible" % n)
        same_asset(t, mesh_of(t, body), art_mesh(row.body), "%s: Body shows %s" % (n, row.body))
        attached(t, car, body, mesh, "", "%s Body" % n)
        for name, bone in CAR_WHEELS:
            wheel = comp(t, car, name)
            attached(t, car, wheel, mesh, bone, "%s %s" % (n, name))
            same_asset(t, mesh_of(t, wheel), SM_WHEEL, "%s: %s shows SM_DF_Wheel" % (n, name))
            t.true(visible(t, wheel), "%s: %s is visible" % (n, name))
        bar = comp(t, car, "LightBar")
        attached(t, car, bar, body, "Roof", "%s LightBar" % n)
        same_asset(t, mesh_of(t, bar), SM_LIGHT_BAR, "%s: LightBar shows SM_DF_LightBar" % n)
        (t.true if n == "SEDAN" else t.false)(visible(t, bar), "%s: the light bar is %s" % (n, "shown" if n == "SEDAN" else "hidden"))
        weapon = comp(t, car, "RoofWeapon")
        attached(t, car, weapon, body, "Roof", "%s RoofWeapon" % n)
        t.false(visible(t, weapon), "%s: no item held, so the roof weapon is hidden" % n)
        shield = comp(t, car, "ShieldBubble")
        attached(t, car, shield, body, "", "%s ShieldBubble" % n)
        same_asset(t, mesh_of(t, shield), SM_SHIELD_BUBBLE, "%s: ShieldBubble shows SM_DF_ShieldBubble" % n)
        t.false(visible(t, shield), "%s: the shield bubble starts hidden" % n)
        for name, socket in (("BoostFlameL", "Exhaust_L"), ("BoostFlameR", "Exhaust_R")):
            flame = comp(t, car, name)
            attached(t, car, flame, body, socket, "%s %s" % (n, name))
            same_asset(t, mesh_of(t, flame), SM_EXHAUST_FLAME, "%s: %s shows SM_DF_ExhaustFlame" % (n, name))
            t.false(visible(t, flame), "%s: %s starts hidden" % (n, name))
    for row, car in cars:
        destroy(t, car)
    return t.finish()


def wheels_follow_test():
    t = arcade_T("FT_DFArt_WheelsFollowBones", "Spec §6.1: a SEDAN on the drive strip (raw AI controller) drives 2 s at full throttle with "
                 "steer 0.5. At the end each wheel component is within 5 cm of its bone's socket on the hidden Mesh, and WheelFL's "
                 "rotation in the car's frame differs from its start (the bone spins and steers it). Physics in step with game time "
                 "(time dilation 0.25).")
    t.bp.variable("FLRot0", "struct:" + ROTATOR, "")
    race_context(t)
    car, ai = spawn_on_strip(t, VC)
    tick_after_test(t, car)
    set_input(t, car, 0.0, 0.0, False)
    t.delay(SETTLE)
    s = t.step(t.g.var_set("FLRot0", STRUCT, sub_object=struct_ref(ROTATOR)))
    t.link(fl_rotation_in_car(t, car), s, "FLRot0")
    set_input(t, car, 1.0, 0.5, False)
    t.delay(DRIVE_SECONDS)
    flog(t, "ART WHEELS kph after the drive", speed_kph(t, car))
    for name, bone in CAR_WHEELS:
        where = t.g.call_on(SCENE_COMP, "K2_GetComponentLocation", outputs=[struct_pin("ReturnValue", VECTOR, "out")], pure=True)
        t.link(comp(t, car, name), where, "self")
        bone_at = t.g.call_on(SCENE_COMP, "GetSocketLocation", inputs=[Pin("InSocketName", NAME, default=bone)],
                              outputs=[struct_pin("ReturnValue", VECTOR, "out")], pure=True)
        t.link(car_mesh(t, car), bone_at, "self")
        gap = t.distance((where, "ReturnValue"), (bone_at, "ReturnValue"))
        flog(t, "ART WHEELS %s cm from %s" % (name, bone), gap)
        check(t, "LessEqual_FloatFloat", gap, WHEEL_TOLERANCE_CM, "%s is within %g cm of the %s socket" % (name, WHEEL_TOLERANCE_CM, bone))
    start = (t.g.var_get("FLRot0", STRUCT, struct_ref(ROTATOR)), "FLRot0")
    now = fl_rotation_in_car(t, car)
    t.step(log_line(t.g, "ART WHEELS FL rotation in the car frame: start ", rot_str(t, start), " end ", rot_str(t, now)))
    same = t.g.call_static(MATH, "EqualEqual_RotatorRotator", inputs=[struct_pin("A", ROTATOR), struct_pin("B", ROTATOR), Pin("ErrorTolerance", FLOAT, default="1.0")],
                           outputs=[Pin("ReturnValue", BOOL, "out")], pure=True)
    t.link(now, same, "A")
    t.link(start, same, "B")
    t.false((same, "ReturnValue"), "WheelFL's rotation in the car's frame changed while driving (the wheel follows its spinning bone)")
    destroy(t, car)
    return arcade_finish(t)


def blown_tire_test():
    t = T("FT_DFArt_BlownTireShowsRim", "Spec §6.1, §7.5: a blown front-left tyre shows SM_DF_WheelRim on WheelFL (the other wheels keep "
          "SM_DF_Wheel); InitTires puts SM_DF_Wheel back.")
    car = spawn_vehicle(t)
    fl, fr = comp(t, car, "WheelFL"), comp(t, car, "WheelFR")
    same_asset(t, mesh_of(t, fl), SM_WHEEL, "a fresh car's WheelFL shows SM_DF_Wheel")
    t.call(VC, "ApplyTireDamage", car, inputs=[Pin("Index", INT, default="0"), Pin("Damage", FLOAT, default="100.0")])
    t.true(tire(t, car, 0, "bBlown", BOOL), "the front-left tyre is blown")
    same_asset(t, mesh_of(t, fl), SM_WHEEL_RIM, "the blown front-left tyre shows SM_DF_WheelRim")
    same_asset(t, mesh_of(t, fr), SM_WHEEL, "WheelFR keeps SM_DF_Wheel")
    t.call(VC, "InitTires", car)
    same_asset(t, mesh_of(t, fl), SM_WHEEL, "InitTires: WheelFL shows SM_DF_Wheel again")
    destroy(t, car)
    return t.finish()


def wreck_test():
    t = T("FT_DFArt_WreckCharred", "Spec §6.1: a fresh SEDAN wears MI_DF_Paint_Sedan; DestroyVehicle puts MI_DF_Paint_Charred on the "
          "Body's slots 0 (paint) and 1 (trim). Spec §7.1 (Task 16): the wreck's fire on the bonnet (WreckFire) is hidden on a fresh "
          "car and shown on the wreck.")
    race_context(t)
    car = spawn_vehicle(t)
    t.delay(0.5)
    same_asset(t, body_material(t, car, 0), art_material("MI_DF_Paint_Sedan"), "a fresh SEDAN's Body slot 0 is MI_DF_Paint_Sedan")
    t.false(visible(t, comp(t, car, "WreckFire")), "a fresh car shows no wreck fire")
    t.call(VC, "DestroyVehicle", car, inputs=[obj_pin("Killer", CONTROLLER)])
    same_asset(t, body_material(t, car, 0), MI_PAINT_CHARRED, "the wreck's Body slot 0 is MI_DF_Paint_Charred")
    same_asset(t, body_material(t, car, 1), MI_PAINT_CHARRED, "the wreck's Body slot 1 is MI_DF_Paint_Charred")
    t.true(visible(t, comp(t, car, "WreckFire")), "the wreck shows its fire (WreckFire)")
    destroy(t, car)
    return t.finish()


def rival_paint_test():
    t = T("FT_DFArt_RivalPaint", "Spec §6.1, §3: with NPCCount 1, SpawnNPCs gives the NPC's car MI_DF_Paint_Gang on Body slot 0, the "
          "gang's flame-orange MI_DF_Trim_Gang on slot 1 and no light bar (the player's car alone has one); wrecked, both slots turn "
          "MI_DF_Paint_Charred, and the NPC is back 2.5 s later in a fresh car with the same gang look. The NPCs are despawned and "
          "NPCCount set back to 0 on every finish.")
    ev = bind_cleanup(t, "CleanUpRivals")
    to_gm = t.g.cast(GMC)
    t.g.link(get_game_mode(t.g), "ReturnValue", to_gm, "Object")
    t.g.link(ev, "then", to_gm, "execute")
    gone = t.g.call_on(GMC, "DespawnNPCs")
    t.g.link(to_gm, as_pin(BP_GM), gone, "self")
    t.g.link(to_gm, "then", gone, "execute")
    zero = t.g.var_set_on(GMC, "NPCCount", INT, default="0")
    t.g.link(to_gm, as_pin(BP_GM), zero, "self")
    t.g.exec(gone, zero, log_line(t.g, "ART CLEANUP FT_DFArt_RivalPaint: NPCs despawned, NPCCount 0"))
    pc, gm, gs, racer, gates = race_context(t)
    t.set(GMC, "NPCCount", INT, gm, default="1")
    spawn = t.call(GMC, "SpawnNPCs", gm, inputs=[Pin("Count", INT)])
    t.link(t.get(GMC, "NPCCount", INT, gm), spawn, "Count")
    ais = ai_controllers(t)
    t.eq_int(t.length(ais, AIC), 1, "one NPC spawned")
    ai = t.item(ais, AIC)
    npc_car = ai_car(t, ai)
    same_asset(t, t.get(VC, "PaintMaterial", OBJECT, npc_car, sub=cls_ref(MATERIAL_INTERFACE)), MI_PAINT_GANG,
               "the NPC car's PaintMaterial is MI_DF_Paint_Gang")
    same_asset(t, body_material(t, npc_car, 0), MI_PAINT_GANG, "the NPC car's Body slot 0 is MI_DF_Paint_Gang")
    # Task 22 (spec §3): the gang's flame-orange trim and no light bar, on the spawned car and on its replacement
    same_asset(t, body_material(t, npc_car, TRIM_SLOT), MI_TRIM_GANG, "the NPC car's Body slot 1 (trim) is MI_DF_Trim_Gang")
    t.false(visible(t, comp(t, npc_car, "LightBar")), "the NPC car shows no light bar")
    t.delay(0.5)
    t.damage(npc_car, 100)  # wrecked: RespawnRacer replaces the car after the respawn delay (as in FT_DFAI_TwoRacersRespawnTogether)
    same_asset(t, body_material(t, npc_car, 0), MI_PAINT_CHARRED, "the NPC's wreck: Body slot 0 is MI_DF_Paint_Charred")
    same_asset(t, body_material(t, npc_car, TRIM_SLOT), MI_PAINT_CHARRED, "the NPC's wreck: Body slot 1 is MI_DF_Paint_Charred")
    t.delay(2.5)
    fresh = ai_car(t, ai)
    t.false(t.get(VC, "bIsDestroyed", BOOL, fresh), "the NPC is back in an intact car")
    same_asset(t, body_material(t, fresh, 0), MI_PAINT_GANG, "the NPC's replacement car's Body slot 0 is MI_DF_Paint_Gang")
    same_asset(t, body_material(t, fresh, TRIM_SLOT), MI_TRIM_GANG, "the NPC's replacement car's Body slot 1 (trim) is MI_DF_Trim_Gang")
    t.false(visible(t, comp(t, fresh, "LightBar")), "the NPC's replacement car shows no light bar")
    despawn_npcs(t, gm)
    t.set(GMC, "NPCCount", INT, gm, default="0")
    return t.finish()


def roof_weapon_test():
    t = T("FT_DFArt_RoofWeaponShowsHeldItem", "Spec §6.1: the player's car shows no roof weapon after a restart; a granted Gun shows "
          "SM_DF_RoofGun; a granted RPG shows SM_DF_RoofLauncher (RPG wins when both are held); ClearInventory and "
          "RefreshRoofWeapon hide it; using the last Gun charge hides it again.")
    pc, gm, gs, racer, gates = race_context(t)
    car = pawn_car(t, pc)
    weapon = comp(t, car, "RoofWeapon")
    t.false(visible(t, weapon), "no item after the restart: the roof weapon is hidden")
    t.true(grant(t, gm, pc, ITEM_GUN, 8), "Gun granted")
    t.true(visible(t, weapon), "holding a Gun: the roof weapon is shown")
    same_asset(t, mesh_of(t, weapon), SM_ROOF_GUN, "holding a Gun: the roof weapon is SM_DF_RoofGun")
    t.true(grant(t, gm, pc, ITEM_RPG, 1), "RPG granted")
    t.true(visible(t, weapon), "holding a Gun and an RPG: the roof weapon is shown")
    same_asset(t, mesh_of(t, weapon), SM_ROOF_LAUNCHER, "holding a Gun and an RPG: the roof weapon is SM_DF_RoofLauncher")
    t.call(RC, "ClearInventory", racer)
    t.call(VC, "RefreshRoofWeapon", car)
    t.false(visible(t, weapon), "inventory cleared and refreshed: the roof weapon is hidden")
    t.true(grant(t, gm, pc, ITEM_GUN, 1), "one Gun charge granted")
    t.true(visible(t, weapon), "one Gun charge: the roof weapon is shown")
    t.true(use_item(t, car), "the Gun's last charge is used")
    t.false(visible(t, weapon), "the last Gun charge used: the roof weapon is hidden")
    return t.finish()


def task13_tests():
    return [car_visuals_test(), wheels_follow_test(), blown_tire_test(), wreck_test(), rival_paint_test(), roof_weapon_test()]


# ---- Task 14: the character's gear (spec §6.2) ----
def char_comp(t: T, ch, name, cls=STATIC_MESH_COMP):
    """One of the character's components (Mesh, Helmet, Vest, Rifle, Weapon, ...)."""
    return t.get(CC, name, OBJECT, ch, sub=cls_ref(cls))


def unit_scale(t: T, xf_src, message):
    """AssertTrue(the transform's scale == (1, 1, 1))."""
    brk = t.g.call_static(MATH, "BreakTransform", inputs=[struct_pin("InTransform", TRANSFORM)],
                          outputs=[struct_pin("Location", VECTOR, "out"), struct_pin("Rotation", ROTATOR, "out"),
                                   struct_pin("Scale", VECTOR, "out")], pure=True)
    t.link(xf_src, brk, "InTransform")
    one = t.g.call_static(MATH, "EqualEqual_VectorVector", inputs=[struct_pin("A", VECTOR), struct_pin("B", VECTOR, default="1,1,1"),
                                                                 Pin("ErrorTolerance", FLOAT, default="0.001")],
                          outputs=[Pin("ReturnValue", BOOL, "out")], pure=True)
    t.g.link(brk, "Scale", one, "A")
    t.true((one, "ReturnValue"), message)


def character_gear_test():
    t = T("FT_DFArt_CharacterGear", "Spec §6.2: a fresh BP_DFCharacter wears SM_DF_Helmet on its Mesh's head socket, SM_DF_Vest on "
          "spine_03 and SM_DF_Rifle on hand_r (each visible, at world scale 1); the rifle has a Muzzle socket at world scale 1; the "
          "mannequin's slots 0 and 1 are MI_DF_Mannequin_Body and MI_DF_Mannequin_Trim; the Weapon's bDebugTrace is off and BeginPlay "
          "made the Rifle its VisualOrigin.")
    ch = spawn_character(t)
    mesh = char_comp(t, ch, "Mesh", SKEL_MESH_COMP)
    for name, asset, socket in CHARACTER_GEAR:
        part = char_comp(t, ch, name)
        attached(t, ch, part, mesh, socket, name)
        same_asset(t, mesh_of(t, part), art_mesh(asset), "%s shows %s" % (name, asset))
        t.true(visible(t, part), "%s is visible" % name)
    rifle = char_comp(t, ch, "Rifle")
    has = t.g.call_on(SCENE_COMP, "DoesSocketExist", inputs=[Pin("InSocketName", NAME, default="Muzzle")],
                      outputs=[Pin("ReturnValue", BOOL, "out")], pure=True)
    t.link(rifle, has, "self")
    t.true((has, "ReturnValue"), "the Rifle has a Muzzle socket")
    muzzle = t.g.call_on(SCENE_COMP, "GetSocketTransform",
                         inputs=[Pin("InSocketName", NAME, default="Muzzle"),
                                 native_enum_pin("TransformSpace", "/Script/Engine.ERelativeTransformSpace", "RTS_World")],
                         outputs=[struct_pin("ReturnValue", TRANSFORM, "out")], pure=True)
    t.link(rifle, muzzle, "self")
    unit_scale(t, (muzzle, "ReturnValue"), "the Rifle's Muzzle socket is at world scale 1")
    for slot, mi in ((0, MI_MANNEQUIN_BODY), (1, MI_MANNEQUIN_TRIM)):
        gm = t.g.call_on(PRIMITIVE, "GetMaterial", inputs=[Pin("ElementIndex", INT, default=str(slot))],
                         outputs=[obj_pin("ReturnValue", MATERIAL_INTERFACE, "out")], pure=True)
        t.link(mesh, gm, "self")
        same_asset(t, (gm, "ReturnValue"), mi, "the mannequin's slot %d is %s" % (slot, mi.rsplit("/", 1)[1]))
    weapon = char_comp(t, ch, "Weapon", WC)
    t.false(t.get(WC, "bDebugTrace", BOOL, weapon), "the character's Weapon has bDebugTrace off")
    t.same(t.get(WC, "VisualOrigin", OBJECT, weapon, sub=cls_ref(SCENE_COMP)), rifle, "the Weapon's VisualOrigin is the Rifle")
    destroy(t, ch)
    return t.finish()


def task14_tests():
    return [character_gear_test()]


# ---- Task 15: the effect family (spec §7.1) ----
FXC = gen(BP_FX)
FX_NEAR_CM = 2000.0          # "within 20 m of the test": effects other tests spawn elsewhere do not count
FX_ALL_GONE_S = 1.5          # longer than every child's Lifetime + 0.1 (the longest, Explosion and Puff, is 1.2 s)
TRACER_CM = 1000.0           # SetEnds from origin + (0, 0, 100) to origin + (1000, 0, 100)
TRACER_SIZE_TOL_CM, TRACER_CENTRE_TOL_CM = 50.0, 25.0
TEST_TINT = (0.5, 0.25, 1.0, 1.0)
TRACER_TICK_WAIT_S = 0.5  # at least one headless frame (0.25-0.4 s)


def fx_array(t: T, fx, var, cat=OBJECT, cls=STATIC_MESH_COMP):
    """One of BP_DFFx's internal arrays (Shells, MIDs: object arrays of cls; BaseScales: cat STRUCT, a Vector array)."""
    sub = struct_ref(VECTOR) if cat == STRUCT else cls_ref(cls)
    return t.get(FXC, var, cat, fx, sub=sub, container="Array")


def fx_first(t: T, fx, var, cat=OBJECT, cls=STATIC_MESH_COMP):
    """Element 0 of one of BP_DFFx's internal arrays."""
    sub = struct_ref(VECTOR) if cat == STRUCT else cls_ref(cls)
    n = t.g.call_array("KismetArrayLibrary", "Array_Get", Pin("e", cat, sub_object=sub), inputs=[Pin("Index", INT, default="0")],
                       outputs=[Pin("Item", cat, "out", sub)])
    t.link(fx_array(t, fx, var, cat, cls), n, "TargetArray")
    return (n, "Item")


def vec_x(t: T, src):
    n = t.g.call_static(MATH, "BreakVector", inputs=[struct_pin("InVec", VECTOR)],
                        outputs=[Pin("X", FLOAT, "out"), Pin("Y", FLOAT, "out"), Pin("Z", FLOAT, "out")], pure=True)
    t.link(src, n, "InVec")
    return (n, "X")


def first_shell_scale_x(t: T, fx):
    """X of the first shell's RelativeScale3D (what Tick writes)."""
    rel = t.get(SCENE_COMP, "RelativeScale3D", STRUCT, fx_first(t, fx, "Shells"), sub=struct_ref(VECTOR))
    return vec_x(t, rel)


def first_fade(t: T, fx):
    n = t.g.call_on(MID, "K2_GetScalarParameterValue", inputs=[Pin("ParameterName", NAME, default="Fade")],
                    outputs=[Pin("ReturnValue", FLOAT, "out")])
    t.link(fx_first(t, fx, "MIDs", OBJECT, MID), n, "self")
    t.step(n)
    return (n, "ReturnValue")


def near_equal(t: T, a, b, tol, message):
    """AssertTrue(|a - b| <= tol) for two float sources."""
    check(t, "LessEqual_FloatFloat", fop(t, "Abs", fop(t, "Subtract_FloatFloat", a, b)), tol, message)


def count_fx_near(t: T, var):
    """var := how many BP_DFFx actors stand within FX_NEAR_CM of the test (a ForEach over GetAllActorsOfClass)."""
    t.step(t.g.var_set(var, INT, default="0"))
    found = t.step(get_all_actors_of_class(t.g, FXC))
    loop = t.g.for_each(Pin("e", OBJECT, sub_object=cls_ref(FXC)))
    t.g.link(found, "OutActors", loop, "Array")
    t.step(loop, in_pin="Exec", out_pin="Completed")
    near = t.g.call_static(MATH, "LessEqual_FloatFloat", inputs=[Pin("A", FLOAT), Pin("B", FLOAT, default="%f" % FX_NEAR_CM)],
                           outputs=[Pin("ReturnValue", BOOL, "out")], pure=True)
    t.link(t.distance(t.loc((loop, "Array Element")), t.self_loc()), near, "A")
    b = t.g.branch()
    t.g.link(loop, "LoopBody", b, "execute")
    t.g.link(near, "ReturnValue", b, "Condition")
    plus = t.g.call_static(MATH, "Add_IntInt", inputs=[Pin("A", INT), Pin("B", INT, default="1")], outputs=[Pin("ReturnValue", INT, "out")],
                           pure=True)
    t.g.link(t.g.var_get(var, INT), var, plus, "A")
    inc = t.g.var_set(var, INT)
    t.g.link(plus, "ReturnValue", inc, var)
    t.g.link(b, "then", inc, "execute")
    # each counted effect in the log: its name, Age and the life span its timer has left (diagnoses a survivor)
    age = t.g.var_get_on(FXC, "Age", FLOAT)
    left = t.g.call_on(ACTOR, "GetLifeSpan", outputs=[Pin("ReturnValue", FLOAT, "out")], pure=True)  # const: pure
    texts = []
    for node, pin in ((age, "Age"), (left, "ReturnValue")):
        t.g.link(loop, "Array Element", node, "self")
        fs = t.g.call_static("KismetStringLibrary", "Conv_FloatToString", inputs=[Pin("InFloat", FLOAT)],
                             outputs=[Pin("ReturnValue", STRING, "out")], pure=True)
        t.g.link(node, pin, fs, "InFloat")
        texts.append((fs, "ReturnValue"))
    t.g.exec(inc, log_line(t.g, "FX NEAR ", name_of(t.g, (loop, "Array Element")), " age ", texts[0], " life span left ", texts[1]))
    return (t.g.var_get(var, INT), var)


def shells_grow_and_fade_test():
    t = T("FT_DFFx_ShellsGrowAndFade", "Spec §7.1: a BP_DFFxExplosion starts with its first shell at base x StartScale and Fade 1 "
          "(BeginPlay applies the t = 0 look); 0.6 s later (about 0.66 s headless) that shell's relative scale X is greater than its "
          "base x StartScale (and not past base x EndScale), its MID's Fade is below 0.9, and that MID is the shell's material.")
    fx = t.spawn(gen(BP_FX_EXPLOSION), t.self_loc())
    t.true(compare_int(t, t.length(fx_array(t, fx, "Shells"), STATIC_MESH_COMP), "Greater_IntInt", 0), "the explosion has FxShell shells")
    base_x = vec_x(t, fx_first(t, fx, "BaseScales", STRUCT))
    start = fop(t, "Multiply_FloatFloat", base_x, t.get(FXC, "StartScale", FLOAT, fx))
    end = fop(t, "Multiply_FloatFloat", base_x, t.get(FXC, "EndScale", FLOAT, fx))
    flog(t, "FX GROW at spawn: base X, scale X", base_x, first_shell_scale_x(t, fx))
    near_equal(t, first_shell_scale_x(t, fx), start, 0.001, "at spawn the first shell is at base x StartScale")
    near_equal(t, first_fade(t, fx), 1.0, 0.001, "at spawn the first shell's Fade is 1")
    t.delay(0.6)
    flog(t, "FX GROW at 0.6 s: Age, scale X, Fade", t.get(FXC, "Age", FLOAT, fx), first_shell_scale_x(t, fx), first_fade(t, fx))
    check(t, "Greater_FloatFloat", first_shell_scale_x(t, fx), start, "at 0.6 s the first shell has grown past base x StartScale")
    check(t, "LessEqual_FloatFloat", first_shell_scale_x(t, fx), fop(t, "Add_FloatFloat", end, 0.001),
          "at 0.6 s the first shell is not past base x EndScale")
    check(t, "Less_FloatFloat", first_fade(t, fx), 0.9, "at 0.6 s the first shell's Fade is below 0.9")
    mat = t.g.call_on(PRIMITIVE, "GetMaterial", inputs=[Pin("ElementIndex", INT, default="0")],
                      outputs=[obj_pin("ReturnValue", MATERIAL_INTERFACE, "out")], pure=True)
    t.link(fx_first(t, fx, "Shells"), mat, "self")
    t.same((mat, "ReturnValue"), fx_first(t, fx, "MIDs", OBJECT, MID), "the first shell shows its MID")
    destroy(t, fx)
    return t.finish()


def tick_before_test(t: T, fx):
    """The test ticks after the effect in every frame, so in the frame a Delay ends the effect has already aged (and, past
    Lifetime + 0.1 s, destroyed itself); the brief's 1.5 s leaves 0.2 s over the longest life, under one headless frame."""
    n = t.g.call_self_native(ACTOR, "AddTickPrerequisiteActor", inputs=[obj_pin("PrerequisiteActor", ACTOR)])
    t.link(fx, n, "PrerequisiteActor")
    t.step(n)


def compare_int(t: T, src, fn, value):
    n = t.g.call_static(MATH, fn, inputs=[Pin("A", INT), Pin("B", INT, default=str(value))], outputs=[Pin("ReturnValue", BOOL, "out")],
                        pure=True)
    t.link(src, n, "A")
    return (n, "ReturnValue")


def self_destroys_test():
    t = T("FT_DFFx_SelfDestroys", "Spec §7.1: all seven effects spawned at the test origin (the LootBurst tinted the way callers do it, "
          "df.spawn_fx: spawn, then SetTint in the same frame, so its shells' Color is the tint x MI_DF_FxBurst's white = the tint) "
          "are there at once, and %g s later no BP_DFFx is left within 20 m of the test." % FX_ALL_GONE_S)
    t.bp.variable("Near", "int", "0")
    for asset in FX_CHILDREN:
        if asset != BP_FX_LOOT_BURST:
            tick_before_test(t, t.spawn(gen(asset), t.self_loc()))
    tint = "(R=%f,G=%f,B=%f,A=%f)" % TEST_TINT
    first, last, burst = spawn_fx(t.g, BP_FX_LOOT_BURST, t.transform(t.self_loc()), tint=tint)
    t.g.link(t.prev[0], t.prev[1], first, "execute")
    t.prev = (last, "then")
    tick_before_test(t, burst)
    colour = t.g.call_on(MID, "K2_GetVectorParameterValue", inputs=[Pin("ParameterName", NAME, default="Color")],
                         outputs=[struct_pin("ReturnValue", LINEAR_COLOR, "out")])
    t.link(fx_first(t, burst, "MIDs", OBJECT, MID), colour, "self")
    t.step(colour)
    same = t.g.call_static(MATH, "LinearColor_IsNearEqual", inputs=[struct_pin("A", LINEAR_COLOR), struct_pin("B", LINEAR_COLOR, default=tint),
                                                                   Pin("Tolerance", FLOAT, default="0.0001")],
                           outputs=[Pin("ReturnValue", BOOL, "out")], pure=True)
    t.g.link(colour, "ReturnValue", same, "A")
    t.true((same, "ReturnValue"), "the tinted LootBurst's first shell has Color = the tint (white MI_DF_FxBurst x the tint)")
    t.eq_int(count_fx_near(t, "Near"), len(FX_CHILDREN), "effects within 20 m right after spawning all seven")
    t.delay(FX_ALL_GONE_S)
    t.eq_int(count_fx_near(t, "Near"), 0, "effects within 20 m %g s later (each destroys itself after its Lifetime)" % FX_ALL_GONE_S)
    return t.finish()


def tracer_bounds_check(t: T, beam, when):
    """The beam's world bounds span the 10 m shot along X, centred 5 m out from the test."""
    b = t.g.call_static("KismetSystemLibrary", "GetComponentBounds", inputs=[obj_pin("Component", SCENE_COMP)],
                        outputs=[struct_pin("Origin", VECTOR, "out"), struct_pin("BoxExtent", VECTOR, "out"), Pin("SphereRadius", FLOAT, "out")],
                        pure=True)
    t.link(beam, b, "Component")
    size = fop(t, "Multiply_FloatFloat", vec_x(t, (b, "BoxExtent")), 2.0)
    centre = fop(t, "Subtract_FloatFloat", vec_x(t, (b, "Origin")), vec_x(t, t.self_loc()))
    flog(t, "FX TRACER %s: bounds X size, centre X from the test" % when, size, centre)
    check(t, "GreaterEqual_FloatFloat", size, TRACER_CM - TRACER_SIZE_TOL_CM, "%s: the beam's bounds are at least 950 cm long in X" % when)
    check(t, "LessEqual_FloatFloat", size, TRACER_CM + TRACER_SIZE_TOL_CM, "%s: the beam's bounds are at most 1050 cm long in X" % when)
    near_equal(t, centre, TRACER_CM / 2, TRACER_CENTRE_TOL_CM, "%s: the beam's bounds are centred 500 +- 25 cm along X" % when)


def tracer_spans_ends_test():
    t = T("FT_DFFx_TracerSpansEnds", "Spec §7.1: SetEnds(origin + (0, 0, 100), origin + (1000, 0, 100)) on a BP_DFFxTracer puts it "
          "at Start aimed at End with the beam %g cm long: its world bounds are 950-1050 cm in X, centred at +500 +- 25 cm. Kept "
          "alive (Lifetime and life span 10 s) and ticking before the test, %g s later it has ticked (Age > 0) and still spans the "
          "shot: Tick scales from the base SetEnds updated, not the 1 m beam it was spawned with." % (TRACER_CM, TRACER_TICK_WAIT_S))
    trc = gen(BP_FX_TRACER)
    tr = t.spawn(trc, t.self_loc())
    tick_before_test(t, tr)
    # kept alive past its 0.08 s: a long Lifetime (its Age-based end) and life span (the backstop), set before its first tick;
    # the tracer does not grow (StartScale = EndScale = 1), so the longer Lifetime does not change its scale
    t.set(FXC, "Lifetime", FLOAT, tr, default="10.0")
    t.call(ACTOR, "SetLifeSpan", tr, inputs=[Pin("InLifespan", FLOAT, default="10.0")])
    ends = t.call(trc, "SetEnds", tr, inputs=[struct_pin("Start", VECTOR), struct_pin("End", VECTOR)])
    t.link(t.offset(t.self_loc(), 0.0, 0.0, 100.0), ends, "Start")
    t.link(t.offset(t.self_loc(), TRACER_CM, 0.0, 100.0), ends, "End")
    check(t, "LessEqual_FloatFloat", t.distance(t.loc(tr), t.offset(t.self_loc(), 0.0, 0.0, 100.0)), 1.0, "the tracer stands at Start")
    beam = t.get(trc, "Beam", OBJECT, tr, sub=cls_ref(STATIC_MESH_COMP))
    tracer_bounds_check(t, beam, "after SetEnds")
    # a Delay can end in the very tick that started it, and a fresh actor may not have ticked yet: wait at least one headless
    # frame, and fail (not pass vacuously) if the tracer has still not ticked
    t.delay(TRACER_TICK_WAIT_S)
    age = t.get(FXC, "Age", FLOAT, tr)
    flog(t, "FX TRACER Age at the second check", age)
    check(t, "Greater_FloatFloat", age, 0.0, "the tracer has ticked since SetEnds (Age > 0)")
    tracer_bounds_check(t, beam, "after its ticks")
    destroy(t, tr)
    return t.finish()


def task15_tests():
    return [shells_grow_and_fade_test(), self_destroys_test(), tracer_spans_ends_test()]


# ---- Task 16: shots, rockets, explosions, tyre pops, smoke (spec §5.5, §7.2, §7.3; Review Focus 2 and 3) ----
SHOT_NEAR_CM = 1500.0      # an effect "near" the shooter, the blast or the car (the tests' spots are 25 m apart)
MUZZLE_TOL_CM = 30.0       # the tracer starts at the visual muzzle (the brief's 30 cm)
SPARKS_TOL_CM = 30.0       # the tyre-pop sparks stand at the wheel
DECAL_TOL_CM = 1.0
NEAR_VIEW_CM, FAR_VIEW_CM = 2000.0, 10000.0  # 20 m and 100 m from the player's camera (FX_VIEW_RADIUS is 80 m)
GROUND_TOP_Z = -10.0       # the functional-test level's ground cube (df_build_test_track: centre z -60, 100 cm tall)
SMOKE_KPH, SMOKE_HALF_S = 80.0, 0.5  # the drift: 80 km/h, full lock and the handbrake, for 2 x 0.5 s
SMOKE_COUNT_CM = 4000.0    # puffs counted around each car (it drifts about 20 m in 1 s; the two end 55 m or more apart)


def count_near(t: T, var, cls, centre, radius, label, keep=None):
    """var := how many actors of cls stand within radius cm of centre (a ForEach over GetAllActorsOfClass); keep: a test
    variable (an object of cls) set to the last one counted. Each counted actor is logged with its distance."""
    t.step(t.g.var_set(var, INT, default="0"))
    found = t.step(get_all_actors_of_class(t.g, cls))
    loop = t.g.for_each(Pin("e", OBJECT, sub_object=cls_ref(cls)))
    t.g.link(found, "OutActors", loop, "Array")
    t.step(loop, in_pin="Exec", out_pin="Completed")
    elem = (loop, "Array Element")
    gap = t.distance(t.loc(elem), centre)
    near = t.g.call_static(MATH, "LessEqual_FloatFloat", inputs=[Pin("A", FLOAT), Pin("B", FLOAT, default="%f" % radius)],
                           outputs=[Pin("ReturnValue", BOOL, "out")], pure=True)
    t.link(gap, near, "A")
    b = t.g.branch()
    t.g.link(loop, "LoopBody", b, "execute")
    t.g.link(near, "ReturnValue", b, "Condition")
    plus = t.g.call_static(MATH, "Add_IntInt", inputs=[Pin("A", INT), Pin("B", INT, default="1")], outputs=[Pin("ReturnValue", INT, "out")],
                           pure=True)
    t.g.link(t.g.var_get(var, INT), var, plus, "A")
    last = t.g.var_set(var, INT)
    t.g.link(plus, "ReturnValue", last, var)
    t.g.link(b, "then", last, "execute")
    if keep:
        k = t.g.var_set(keep, OBJECT, sub_object=cls_ref(cls))
        t.g.link(loop, "Array Element", k, keep)
        t.g.exec(last, k)
        last = k
    fs = t.g.call_static("KismetStringLibrary", "Conv_FloatToString", inputs=[Pin("InFloat", FLOAT)], outputs=[Pin("ReturnValue", STRING, "out")],
                         pure=True)
    t.link(gap, fs, "InFloat")
    t.g.exec(last, log_line(t.g, "FX COUNT %s " % label, name_of(t.g, elem), " at ", (fs, "ReturnValue"), " cm"))
    return (t.g.var_get(var, INT), var)


def tobj(t: T, var, cls):
    """A test variable holding an object of cls."""
    return (t.g.var_get(var, OBJECT, cls_ref(cls)), var)


def has_socket(t: T, component, socket):
    n = t.g.call_on(SCENE_COMP, "DoesSocketExist", inputs=[Pin("InSocketName", NAME, default=socket)],
                    outputs=[Pin("ReturnValue", BOOL, "out")], pure=True)
    t.link(component, n, "self")
    return (n, "ReturnValue")


def socket_at(t: T, component, socket):
    n = t.g.call_on(SCENE_COMP, "GetSocketLocation", inputs=[Pin("InSocketName", NAME, default=socket)],
                    outputs=[struct_pin("ReturnValue", VECTOR, "out")], pure=True)
    t.link(component, n, "self")
    return (n, "ReturnValue")


def shot_fx_checks(t: T, shooter, muzzle_component, what):
    """The frame of the shot: one tracer and one muzzle flash near the shooter, the tracer starting at the visual muzzle."""
    trc = gen(BP_FX_TRACER)
    t.eq_int(count_near(t, "Tracers", trc, t.loc(shooter), SHOT_NEAR_CM, "tracer", keep="Tracer"), 1,
             "tracers within 15 m of the %s in the frame of the shot" % what)
    t.eq_int(count_near(t, "Muzzles", gen(BP_FX_MUZZLE), t.loc(shooter), SHOT_NEAR_CM, "muzzle"), 1,
             "muzzle flashes within 15 m of the %s in the frame of the shot" % what)
    gap = t.distance(t.loc(tobj(t, "Tracer", trc)), socket_at(t, muzzle_component[0], "Muzzle"))
    flog(t, "FX SHOT %s: the tracer starts this far (cm) from %s's Muzzle socket" % (what, muzzle_component[1]), gap)
    check(t, "LessEqual_FloatFloat", gap, MUZZLE_TOL_CM, "the tracer starts within 30 cm of %s's Muzzle socket" % muzzle_component[1])


def shot_vars(t: T):
    for v in ("Tracers", "Muzzles"):
        t.bp.variable(v, "int", "0")
    t.bp.variable("Tracer", obj_spec(BP_FX_TRACER), "")


def gun_shot_tracer_test():
    t = T("FT_DFFx_GunShotSpawnsTracer", "Spec §7.2: the player's car is granted a Gun (its roof shows SM_DF_RoofGun, and the car's "
          "Weapon is seen to fire from RoofWeapon: its VisualOrigin) and fires once. In the frame of the shot (the muzzle flash lives "
          "0.06 s and the tracer 0.08 s; a headless frame is about 0.33 s) exactly one BP_DFFxTracer and one BP_DFFxMuzzle stand "
          "within 15 m of the car, and the tracer starts within 30 cm of RoofWeapon's Muzzle socket.")
    shot_vars(t)
    pc, gm, gs, racer, gates = race_context(t)
    car = pawn_car(t, pc)
    t.true(grant(t, gm, pc, ITEM_GUN, 8), "Gun granted")
    roof = comp(t, car, "RoofWeapon")
    t.same(t.get(WC, "VisualOrigin", OBJECT, comp(t, car, "Weapon", WC), sub=cls_ref(SCENE_COMP)), roof,
           "the car's Weapon is seen to fire from RoofWeapon (its VisualOrigin, set at BeginPlay)")
    t.true(has_socket(t, roof, "Muzzle"), "holding a Gun, RoofWeapon (SM_DF_RoofGun) has a Muzzle socket")
    t.true(use_item(t, car), "the Gun fires")
    shot_fx_checks(t, car, (roof, "RoofWeapon"), "car")
    return t.finish()


def rifle_shot_tracer_test():
    t = T("FT_DFFx_RifleShotSpawnsTracer", "Spec §6.2, §7.2: a fresh BP_DFCharacter fires (Fire: the trace from its camera). In the "
          "frame of the shot exactly one BP_DFFxTracer and one BP_DFFxMuzzle stand within 15 m of it, and the tracer starts within "
          "30 cm of the Rifle's Muzzle socket (the Weapon's VisualOrigin is the Rifle).")
    shot_vars(t)
    ch = spawn_character(t)
    rifle = char_comp(t, ch, "Rifle")
    t.call(CC, "Fire", ch, outputs=[Pin("ReturnValue", BOOL, "out")])
    shot_fx_checks(t, ch, (rifle, "Rifle"), "character")
    destroy(t, ch)
    return t.finish()


def scorch_decals(t: T, gm):
    return t.get(GMC, "ScorchDecals", OBJECT, gm, sub=cls_ref(DECAL_COMP), container="Array")


def explosion_fx_test():
    t = T("FT_DFFx_ExplosionSpawnsFx", "Spec §7.3: SpawnExplosion (effects only: no damage) spawns one BP_DFFxExplosion within 15 m "
          "of the blast in the same frame, and the GameMode keeps the scorch decal it spawned (MI_DF_Scorch, at the blast; the "
          "restart before cleared the earlier ones): 4 m across (DecalSize, a half-extent, = (200, 200, 200)) and fading out "
          "over 20 s (GetFadeDuration).")
    t.bp.variable("Explosions", "int", "0")
    pc, gm, gs, racer, gates = race_context(t)
    at = t.offset(t.self_loc(), 0.0, 0.0, -200.0)
    explode(t, gm, at, 0.0, 500.0, None, False)
    t.eq_int(count_near(t, "Explosions", gen(BP_FX_EXPLOSION), at, SHOT_NEAR_CM, "explosion"), 1,
             "explosion effects within 15 m of the blast in its frame")
    decals = scorch_decals(t, gm)
    t.eq_int(t.length(decals, DECAL_COMP), 1, "scorch decals the GameMode keeps after one explosion")
    decal = t.item(decals, DECAL_COMP)
    mat = t.g.call_on(DECAL_COMP, "GetDecalMaterial", outputs=[obj_pin("ReturnValue", MATERIAL_INTERFACE, "out")], pure=True)
    t.link(decal, mat, "self")
    same_asset(t, (mat, "ReturnValue"), MI_SCORCH, "the scorch decal shows MI_DF_Scorch")
    where = t.g.call_on(SCENE_COMP, "K2_GetComponentLocation", outputs=[struct_pin("ReturnValue", VECTOR, "out")], pure=True)
    t.link(decal, where, "self")
    check(t, "LessEqual_FloatFloat", t.distance((where, "ReturnValue"), at), DECAL_TOL_CM, "the scorch decal is at the blast")
    # fix round 1 (controller ruling): spec §7.3's 4 m. DecalSize is a half-extent, so 4 m across is (200, 200, 200)
    size = t.get(DECAL_COMP, "DecalSize", STRUCT, decal, sub=struct_ref(VECTOR))
    flog(t, "FX SCORCH DecalSize X Y Z (half-extents, cm)", vec_part(t, size, "X"), vec_part(t, size, "Y"), vec_part(t, size, "Z"))
    same = t.g.call_static(MATH, "EqualEqual_VectorVector", inputs=[struct_pin("A", VECTOR), struct_pin("B", VECTOR, default="%g,%g,%g" % SCORCH_SIZE),
                                                                  Pin("ErrorTolerance", FLOAT, default="0.01")],
                           outputs=[Pin("ReturnValue", BOOL, "out")], pure=True)
    t.link(size, same, "A")
    t.true((same, "ReturnValue"), "the scorch decal is 4 m across and 4 m deep: DecalSize (half-extents) = (%g, %g, %g)" % SCORCH_SIZE)
    fade = t.g.call_on(DECAL_COMP, "GetFadeDuration", outputs=[Pin("ReturnValue", FLOAT, "out")], pure=True)
    t.link(decal, fade, "self")
    t.eq_float((fade, "ReturnValue"), SCORCH_LIFE, "the scorch decal's fade-out duration (s)", 0.01)
    return t.finish()


def tire_pop_sparks_test():
    t = T("FT_DFFx_TirePopSparks", "Spec §7.1: blowing a tyre (ApplyTireDamage(0, 100) on a fresh car) spawns exactly one "
          "BP_DFFxSparks within 15 m of the car in the same frame (it lives 0.25 s), within 30 cm of the front-left wheel bone.")
    t.bp.variable("Sparks", "int", "0")
    t.bp.variable("Spark", obj_spec(BP_FX_SPARKS), "")
    car = spawn_vehicle(t)
    t.call(VC, "ApplyTireDamage", car, inputs=[Pin("Index", INT, default="0"), Pin("Damage", FLOAT, default="100.0")])
    t.true(tire(t, car, 0, "bBlown", BOOL), "the front-left tyre is blown")
    t.eq_int(count_near(t, "Sparks", gen(BP_FX_SPARKS), t.loc(car), SHOT_NEAR_CM, "sparks", keep="Spark"), 1,
             "spark effects within 15 m of the car in the frame of the blow-out")
    gap = t.distance(t.loc(tobj(t, "Spark", gen(BP_FX_SPARKS))), socket_at(t, car_mesh(t, car), "Wheel_Front_Left"))
    flog(t, "FX TIRE POP sparks from the front-left wheel bone (cm)", gap)
    check(t, "LessEqual_FloatFloat", gap, SPARKS_TOL_CM, "the sparks stand within 30 cm of the front-left wheel bone")
    destroy(t, car)
    return t.finish()


def camera_location(t: T):
    """The player's camera (GetPlayerCameraManager(0)), where IsNearPlayerView measures from."""
    cm = t.g.call_static(GAMEPLAY, "GetPlayerCameraManager", inputs=[Pin("WorldContextObject", OBJECT, hidden=True), Pin("PlayerIndex", INT, default="0")],
                         outputs=[obj_pin("ReturnValue", PLAYER_CAMERA_MANAGER, "out")], pure=True)
    n = t.g.call_on(PLAYER_CAMERA_MANAGER, "GetCameraLocation", outputs=[struct_pin("ReturnValue", VECTOR, "out")], pure=True)
    t.g.link(cm, "ReturnValue", n, "self")
    return (n, "ReturnValue")


def cam_loc(t: T):
    """The camera location the smoke test stored (CamLoc)."""
    return (t.g.var_get("CamLoc", STRUCT, struct_ref(VECTOR)), "CamLoc")


def near_view(t: T, gm, loc):
    n = t.g.call_on(GMC, "IsNearPlayerView", inputs=[struct_pin("Location", VECTOR), Pin("Radius", FLOAT, default="%f" % FX_VIEW_RADIUS)],
                    outputs=[Pin("ReturnValue", BOOL, "out")], pure=True)
    t.link(gm, n, "self")
    t.link(loc, n, "Location")
    return (n, "ReturnValue")


def west_of_camera(t: T, dx):
    """The ground dx cm west of the stored camera location (CamLoc), 60 cm above the ground cube's top."""
    brk = t.g.call_static(MATH, "BreakVector", inputs=[struct_pin("InVec", VECTOR)],
                          outputs=[Pin("X", FLOAT, "out"), Pin("Y", FLOAT, "out"), Pin("Z", FLOAT, "out")], pure=True)
    t.link(cam_loc(t), brk, "InVec")
    mk = t.g.call_static(MATH, "MakeVector", inputs=[Pin("X", FLOAT), Pin("Y", FLOAT), Pin("Z", FLOAT, default="%f" % (GROUND_TOP_Z + 60.0))],
                         outputs=[struct_pin("ReturnValue", VECTOR, "out")], pure=True)
    t.link(fop(t, "Subtract_FloatFloat", (brk, "X"), dx), mk, "X")
    t.g.link(brk, "Y", mk, "Y")
    return (mk, "ReturnValue")


def smoke_car(t: T, dx):
    """A SEDAN dx cm west of the player's camera, facing west (away from it) at SMOKE_KPH, driven by a raw AI controller
    (bAutoDrive off: only SetAIInput steers it), ticking after the test, inputs (0, 0, no handbrake)."""
    rot = t.g.call_static(MATH, "MakeRotator", inputs=[Pin("Roll", FLOAT, default="0.0"), Pin("Pitch", FLOAT, default="0.0"),
                                                       Pin("Yaw", FLOAT, default="180.0")],
                          outputs=[struct_pin("ReturnValue", ROTATOR, "out")], pure=True)
    xf = t.g.call_static(MATH, "MakeTransform", inputs=[struct_pin("Location", VECTOR), struct_pin("Rotation", ROTATOR),
                                                          struct_pin("Scale", VECTOR, default="1,1,1")],
                         outputs=[struct_pin("ReturnValue", TRANSFORM, "out")], pure=True)
    t.link(west_of_camera(t, dx), xf, "Location")
    t.g.link(rot, "ReturnValue", xf, "Rotation")
    car_node = t.step(t.g.spawn_actor(VC))
    t.g.link(xf, "ReturnValue", car_node, "SpawnTransform")
    car = (car_node, "ReturnValue")
    ai_node = t.step(t.g.spawn_actor(AIC))
    t.g.link(xf, "ReturnValue", ai_node, "SpawnTransform")
    ai = (ai_node, "ReturnValue")
    t.set(AIC, "bAutoDrive", BOOL, ai, default="false")
    poss = t.call(CONTROLLER, "Possess", ai, inputs=[obj_pin("InPawn", PAWN)])
    t.link(car, poss, "InPawn")
    tick_after_test(t, car)
    set_velocity(t, car, scaled(t, actor_vec(t, car, "GetActorForwardVector"), SMOKE_KPH / 0.036))
    set_gear(t, car, SMOKE_KPH)
    set_input(t, car, 0.0, 0.0, False)
    return car


def no_smoke_far_test():
    t = arcade_T("FT_DFFx_NoTyreSmokeFarAway", "Review Focus 2, spec §5.5: IsNearPlayerView(loc, 8000) is true 20 m and false 100 m "
                 "from the player's camera. Two SEDANs at 80 km/h on the open ground west of the start line, heading away from the "
                 "parked player's camera, drift for 1 s (full lock with the handbrake): the one that starts 20 m from the camera "
                 "leaves BP_DFFxPuff tyre smoke around it; the one that starts 100 m away (drifting at 0.5 s, and still beyond 80 m "
                 "at the end) leaves none. " + DRIVE_DOC)
    for v in ("FarPuffs", "NearPuffs"):
        t.bp.variable(v, "int", "0")
    t.bp.variable("CamLoc", "struct:" + VECTOR, "")
    t.bp.variable("bFarDrifting", "bool", "false")
    pc, gm, gs, racer, gates = race_context(t)
    s = t.step(t.g.var_set("CamLoc", STRUCT, sub_object=struct_ref(VECTOR)))
    t.link(camera_location(t), s, "CamLoc")
    flog(t, "FX SMOKE the player's camera X Y Z", vec_part(t, cam_loc(t), "X"),
         vec_part(t, cam_loc(t), "Y"), vec_part(t, cam_loc(t), "Z"))
    t.true(near_view(t, gm, t.offset(cam_loc(t), -NEAR_VIEW_CM, 0.0, 0.0)), "IsNearPlayerView: true 20 m from the player's camera")
    t.false(near_view(t, gm, t.offset(cam_loc(t), -FAR_VIEW_CM, 0.0, 0.0)), "IsNearPlayerView: false 100 m from the player's camera")
    near_car, far_car = smoke_car(t, NEAR_VIEW_CM), smoke_car(t, FAR_VIEW_CM)
    t.delay(SETTLE)
    for car in (near_car, far_car):
        set_speed(t, car, SMOKE_KPH)
        set_input(t, car, 0.0, 1.0, True)
    t.delay(SMOKE_HALF_S)
    store(t, "bFarDrifting", t.get(VC, "bDrifting", BOOL, far_car), BOOL)
    t.delay(SMOKE_HALF_S)
    cam = camera_location(t)
    flog(t, "FX SMOKE from the camera at the end (cm): near car, far car; kph near, far", t.distance(cam, t.loc(near_car)),
         t.distance(cam, t.loc(far_car)), speed_kph(t, near_car), speed_kph(t, far_car))
    t.true(tvar(t, "bFarDrifting", BOOL), "the far car is drifting 0.5 s into the turn")
    check(t, "Greater_FloatFloat", t.distance(cam, t.loc(far_car)), FX_VIEW_RADIUS, "the far car is still more than 80 m from the camera")
    t.eq_int(count_near(t, "FarPuffs", gen(BP_FX_PUFF), t.loc(far_car), SMOKE_COUNT_CM, "far puff"), 0,
             "tyre-smoke puffs around the car drifting 100 m from the camera")
    t.true(greater_int(t, count_near(t, "NearPuffs", gen(BP_FX_PUFF), t.loc(near_car), SMOKE_COUNT_CM, "near puff"), 0),
           "the car drifting 20 m from the camera leaves tyre-smoke puffs (the smoke works; only distance stops it)")
    destroy(t, near_car)
    destroy(t, far_car)
    return arcade_finish(t)


def restart_clears_test():
    t = T("FT_DFFx_RestartClearsEffects", "Review Focus 3: with two BP_DFFxExplosion spawned and one SpawnExplosion's effect and "
          "scorch decal live, and (Task 21) a test rock demolished into its %d BP_DFDebris chunks, RestartRace leaves no BP_DFFx "
          "and no BP_DFDebris in the world, destroys the scorch decal and empties the GameMode's ScorchDecals (checked in the "
          "frame of the restart)." % len(ROCK_CHUNK_CELLS))
    t.bp.variable("Scorch", "object:" + DECAL_COMP, "")
    pc, gm, gs, racer, gates = race_context(t)
    for dx in (0.0, 300.0):
        t.spawn(gen(BP_FX_EXPLOSION), t.offset(t.self_loc(), dx, 0.0, 0.0))
    explode(t, gm, t.offset(t.self_loc(), 0.0, 600.0, -200.0), 0.0, 500.0, None, False)
    t.eq_int(t.length(scorch_decals(t, gm), DECAL_COMP), 1, "scorch decals the GameMode keeps before the restart")
    s = t.step(t.g.var_set("Scorch", OBJECT, sub_object=cls_ref(DECAL_COMP)))
    t.link(t.item(scorch_decals(t, gm), DECAL_COMP), s, "Scorch")
    # Task 21: the rock's chunks are swept with the effects (GameMode.SweepEffects); its own explosion adds an effect and a decal
    rock = t.spawn(DESTC, t.offset(t.self_loc(), 0.0, -800.0, 0.0))
    t.call(DESTC, "Demolish", rock)
    t.eq_int(count_actors(t, DEBRISC), len(ROCK_CHUNK_CELLS), "BP_DFDebris live before the restart (the demolished test rock's chunks)")
    t.true(greater_int(t, count_actors(t, FXC), 2), "at least three BP_DFFx are live before the restart")
    t.call(GMC, "RestartRace", gm)
    t.eq_int(count_actors(t, FXC), 0, "BP_DFFx left in the world right after RestartRace")
    t.eq_int(count_actors(t, DEBRISC), 0, "BP_DFDebris left in the world right after RestartRace")
    invalid(t, tobj(t, "Scorch", DECAL_COMP), "RestartRace destroyed the scorch decal")
    t.eq_int(t.length(scorch_decals(t, gm), DECAL_COMP), 0, "scorch decals the GameMode keeps after RestartRace")
    destroy(t, rock)
    return t.finish()


def task16_tests():
    return [gun_shot_tracer_test(), rifle_shot_tracer_test(), explosion_fx_test(), tire_pop_sparks_test(), no_smoke_far_test(),
            restart_clears_test()]


# ---- Task 17: crates, bomb, boost, shield (spec §7.4, §7.5) ----
LOOTC, BOMBC = gen(BP_LOOTBOX), gen(BP_BOMB)
CRATE_PARTS = (("Crate", STATIC_MESH_COMP), ("Lid", STATIC_MESH_COMP), ("Icon", BILLBOARD_COMP), ("Beacon", STATIC_MESH_COMP))
COLOUR_TOL = 0.01          # the brief's "within 0.01"
LOOK_TOL_CM = 2.0          # a boost flame from its Exhaust socket, the bubble's centre from Body x SHIELD_BUBBLE_AT
EFFECT_OVER_S = 0.2        # the brief's margin past the boost's or the shield's duration (the test ticks after the car)
SHIELD_HIT_GLOW = 3.0      # the bubble's Glow for 0.15 s after a blocked hit
SHIELD_HIT_WAIT_S = 0.5    # past the 0.15 s flash by at least one headless frame (0.25-0.4 s)
LID_MOVED_CM = 10.0        # fix round 1: the popping lid has risen at least this far one frame after the pickup
FRAME_WAIT_S = 0.05        # ends in the next frame (the test ticks after the crate, so the crate has ticked in it)
HEADLESS_FRAME_S = 0.4     # one headless frame and a little (0.25-0.4 s)


def get_item_look(t: T, gm, item, random):
    """GameMode.GetItemLook(item, random) (pure): (node, "Colour") and (node, "Icon") sources."""
    n = t.call(GMC, "GetItemLook", gm, inputs=[enum_pin("Type", E_ITEM_TYPE, default=item), Pin("bRandom", BOOL, default="true" if random else "false")],
               outputs=[struct_pin("Colour", LINEAR_COLOR, "out"), obj_pin("Icon", TEXTURE_2D, "out")], pure=True)
    return (n, "Colour"), (n, "Icon")


def crate_part(t: T, crate, name, cls=STATIC_MESH_COMP):
    return t.get(LOOTC, name, OBJECT, crate, sub=cls_ref(cls))


def material_of(t: T, component, slot):
    n = t.g.call_on(PRIMITIVE, "GetMaterial", inputs=[Pin("ElementIndex", INT, default=str(slot))],
                    outputs=[obj_pin("ReturnValue", MATERIAL_INTERFACE, "out")], pure=True)
    t.link(component, n, "self")
    return (n, "ReturnValue")


def mid_param(t: T, mid, kind, name):
    """A MID's vector ("Vector": LinearColor), scalar ("Scalar": float) or texture ("Texture") parameter (impure: stepped)."""
    out = {"Vector": struct_pin("ReturnValue", LINEAR_COLOR, "out"), "Scalar": Pin("ReturnValue", FLOAT, "out"),
           "Texture": obj_pin("ReturnValue", TEXTURE, "out")}[kind]
    n = t.g.call_on(MID, "K2_Get%sParameterValue" % kind, inputs=[Pin("ParameterName", NAME, default=name)], outputs=[out])
    t.link(mid, n, "self")
    t.step(n)
    return (n, "ReturnValue")


def colour_near(t: T, a, b, message):
    """AssertTrue(a ~= b within COLOUR_TOL per channel, alpha too); b is a source or a literal "(R=..,G=..,B=..,A=..)"."""
    literal = isinstance(b, str)
    n = t.g.call_static(MATH, "LinearColor_IsNearEqual", inputs=[struct_pin("A", LINEAR_COLOR), struct_pin("B", LINEAR_COLOR, default=b if literal else None),
                                                                Pin("Tolerance", FLOAT, default="%f" % COLOUR_TOL)],
                        outputs=[Pin("ReturnValue", BOOL, "out")], pure=True)
    t.link(a, n, "A")
    if not literal:
        t.link(b, n, "B")
    t.true((n, "ReturnValue"), message)


def crate_shows(t: T, crate, gm, item, random, what):
    """The crate's stripe (Crate slot 1 is StripeMID: EmissiveColor = GetItemLook's colour, Glow 2), the lid's stripe, the icon
    (Icon's material is IconMID: texture = GetItemLook's icon, Color = the colour) and the beacon (shown, Color = the colour)."""
    colour, icon = get_item_look(t, gm, item, random)
    stripe = t.get(LOOTC, "StripeMID", OBJECT, crate, sub=cls_ref(MID))
    t.same(material_of(t, crate_part(t, crate, "Crate"), 1), stripe, "%s: the Crate's stripe slot (1) shows StripeMID" % what)
    colour_near(t, mid_param(t, stripe, "Vector", "EmissiveColor"), colour, "%s: the stripe's EmissiveColor is GetItemLook's colour (within 0.01)" % what)
    t.eq_float(mid_param(t, stripe, "Scalar", "Glow"), 2.0, "%s: the stripe's Glow" % what)
    lid = t.get(LOOTC, "LidStripeMID", OBJECT, crate, sub=cls_ref(MID))
    t.same(material_of(t, crate_part(t, crate, "Lid"), 1), lid, "%s: the Lid's stripe slot (1) shows LidStripeMID" % what)
    colour_near(t, mid_param(t, lid, "Vector", "EmissiveColor"), colour, "%s: the lid stripe's EmissiveColor is GetItemLook's colour" % what)
    icon_mid = t.get(LOOTC, "IconMID", OBJECT, crate, sub=cls_ref(MID))
    t.same(material_of(t, crate_part(t, crate, "Icon", BILLBOARD_COMP), 0), icon_mid, "%s: the Icon billboard shows IconMID" % what)
    t.same(mid_param(t, icon_mid, "Texture", "Icon"), icon, "%s: the icon's texture is GetItemLook's icon" % what)
    colour_near(t, mid_param(t, icon_mid, "Vector", "Color"), colour, "%s: the icon's Color is GetItemLook's colour" % what)
    beacon = t.get(LOOTC, "BeaconMID", OBJECT, crate, sub=cls_ref(MID))
    t.true(visible(t, crate_part(t, crate, "Beacon")), "%s: the beacon pillar is shown" % what)
    colour_near(t, mid_param(t, beacon, "Vector", "Color"), colour, "%s: the beacon's Color is GetItemLook's colour" % what)


def bounds_z(t: T, component, top):
    """The top (top=True) or bottom of a component's world bounds, Z."""
    b = t.g.call_static("KismetSystemLibrary", "GetComponentBounds", inputs=[obj_pin("Component", SCENE_COMP)],
                        outputs=[struct_pin("Origin", VECTOR, "out"), struct_pin("BoxExtent", VECTOR, "out"), Pin("SphereRadius", FLOAT, "out")],
                        pure=True)
    t.link(component, b, "Component")
    return fop(t, "Add_FloatFloat" if top else "Subtract_FloatFloat", vec_part(t, (b, "Origin"), "Z"), vec_part(t, (b, "BoxExtent"), "Z"))


def comp_loc(t: T, component):
    n = t.g.call_on(SCENE_COMP, "K2_GetComponentLocation", outputs=[struct_pin("ReturnValue", VECTOR, "out")], pure=True)
    t.link(component, n, "self")
    return (n, "ReturnValue")


def crate_rests_on_ground(t: T, crate):
    """Fix round 1 (controller ruling): the actor stands at the centre of the 80 cm crate, as the level places it (z 30 over the
    -10 ground top), so the crate's base is CRATE_HALF_HEIGHT below the actor and the lid's top as far above it; the pickup
    sphere stays centred on the actor."""
    z = vec_part(t, t.loc(crate), "Z")
    base, top = bounds_z(t, crate_part(t, crate, "Crate"), False), bounds_z(t, crate_part(t, crate, "Lid"), True)
    flog(t, "ART CRATE base and lid top from the actor (cm)", fop(t, "Subtract_FloatFloat", base, z), fop(t, "Subtract_FloatFloat", top, z))
    near_equal(t, base, fop(t, "Subtract_FloatFloat", z, CRATE_HALF_HEIGHT), 1.0,
               "the crate's base is %g cm below the actor (its centre): it rests on the ground where the level places it" % CRATE_HALF_HEIGHT)
    near_equal(t, top, fop(t, "Add_FloatFloat", z, CRATE_HALF_HEIGHT), 1.5, "the lid's top is %g cm above the actor" % CRATE_HALF_HEIGHT)
    check(t, "LessEqual_FloatFloat", t.distance(comp_loc(t, crate_part(t, crate, "Trigger", SPHERE_COMP)), t.loc(crate)), 0.5,
          "the pickup sphere (Trigger) is centred on the actor, as before")


def crate_colour_test():
    t = T("FT_DFArt_CrateShowsItemColour", "Spec §7.4: a crate with ItemType Shield shows GetItemLook(Shield, false): its stripe MID's "
          "EmissiveColor (within 0.01, Glow 2) on the Crate and the Lid, the icon billboard's T_DF_Icon_Shield in that colour, and its "
          "beacon shown in that colour. GetItemLook's icons are the catalogue's (Shield: T_DF_Icon_Shield; random: T_DF_Icon_Random). "
          "A random crate (bRandom, Reset) shows T_DF_Icon_Random and the random colour, whatever it rolled. Fix round 1: the crate "
          "rests on the ground where the level places it (base 40 cm below the actor, the lid's top 40 cm above), and its pickup "
          "sphere is centred on the actor.")
    gm = t.game_mode()
    _, shield_icon = get_item_look(t, gm, ITEM_SHIELD, False)
    same_asset(t, shield_icon, art_icon(ITEM_LOOK[ITEM_SHIELD][1]), "GetItemLook(Shield, false) gives T_DF_Icon_Shield")
    _, random_icon = get_item_look(t, gm, ITEM_GUN, True)
    same_asset(t, random_icon, art_icon(RANDOM_LOOK[1]), "GetItemLook(Gun, true) gives T_DF_Icon_Random")
    shield_colour, _ = get_item_look(t, gm, ITEM_SHIELD, False)
    colour_near(t, shield_colour, linear_colour(ITEM_LOOK[ITEM_SHIELD][0]),
                "GetItemLook(Shield, false)'s colour is the catalogue's #%s in linear" % ITEM_LOOK[ITEM_SHIELD][0])
    crate = spawn_crate(t, ITEM_SHIELD)
    t.call(LOOTC, "ApplyLook", crate)  # ItemType was set after the spawn (BeginPlay looked at the default)
    crate_shows(t, crate, gm, ITEM_SHIELD, False, "Shield crate")
    crate_rests_on_ground(t, crate)
    rnd = spawn_crate(t, ITEM_GUN, 0.0, 400.0)
    t.set(LOOTC, "bRandom", BOOL, rnd, default="true")
    t.call(LOOTC, "Reset", rnd)  # rolls a type, then ApplyLook
    icon_mid = t.get(LOOTC, "IconMID", OBJECT, rnd, sub=cls_ref(MID))
    same_asset(t, mid_param(t, icon_mid, "Texture", "Icon"), art_icon(RANDOM_LOOK[1]), "a random crate's icon is T_DF_Icon_Random")
    crate_shows(t, rnd, gm, ITEM_GUN, True, "random crate")
    destroy(t, crate)
    destroy(t, rnd)
    return t.finish()


def lid_z(t: T, crate):
    return vec_part(t, comp_loc(t, crate_part(t, crate, "Lid")), "Z")


def collected_crate_test():
    t = T("FT_DFArt_CollectedCrateHidesVisuals", "Spec §7.4: Pickup by an on-foot character (owned by the player) succeeds; in that "
          "frame the Crate, Icon and Beacon are hidden, the Lid still shows (it pops off), and one BP_DFFxLootBurst stands at the crate "
          "tinted with the crate's colour (GetItemLook). Fix round 1: one frame later the Lid has risen at least %g cm (the test ticks "
          "after the crate); %g s after the pickup (the pop's %g s and a headless frame) the Lid is hidden and so is the actor. Reset "
          "shows all four again, the Lid back at its rest transform on the Lid socket." % (LID_MOVED_CM, LID_POP_SECONDS + HEADLESS_FRAME_S,
                                                                                          LID_POP_SECONDS))
    t.bp.variable("Bursts", "int", "0")
    t.bp.variable("Burst", obj_spec(BP_FX_LOOT_BURST), "")
    t.bp.variable("LidZ0", "float", "0")
    pc, gm, gs, racer, gates = race_context(t)
    crate = spawn_crate(t, ITEM_BOOST)
    tick_before_test(t, crate)
    for name, cls in CRATE_PARTS:
        t.true(visible(t, crate_part(t, crate, name, cls)), "an uncollected crate shows its %s" % name)
    ch = owned_character(t, pc)
    store(t, "LidZ0", lid_z(t, crate))
    took = t.call(LOOTC, "Pickup", crate, inputs=[obj_pin("Character", CC)], outputs=[Pin("ReturnValue", BOOL, "out")])
    t.link(ch, took, "Character")
    t.true((took, "ReturnValue"), "the on-foot character's Pickup succeeds")
    for name, cls in CRATE_PARTS:
        if name != "Lid":
            t.false(visible(t, crate_part(t, crate, name, cls)), "in the pickup frame the crate hides its %s" % name)
    t.true(visible(t, crate_part(t, crate, "Lid")), "in the pickup frame the Lid still shows: it pops off")
    t.eq_int(count_near(t, "Bursts", gen(BP_FX_LOOT_BURST), t.loc(crate), SHOT_NEAR_CM, "loot burst", keep="Burst"), 1,
             "loot bursts within 15 m of the crate in the frame of the pickup")
    colour, _ = get_item_look(t, gm, ITEM_BOOST, False)
    burst_mid = fx_first(t, tobj(t, "Burst", gen(BP_FX_LOOT_BURST)), "MIDs", OBJECT, MID)
    colour_near(t, mid_param(t, burst_mid, "Vector", "Color"), colour, "the loot burst is tinted with the crate's colour (x MI_DF_FxBurst's white)")
    t.delay(FRAME_WAIT_S)
    rise = fop(t, "Subtract_FloatFloat", lid_z(t, crate), tvar(t, "LidZ0"))
    flog(t, "ART CRATE the lid's rise one frame after the pickup (cm)", rise)
    check(t, "GreaterEqual_FloatFloat", rise, LID_MOVED_CM, "one frame after the pickup the Lid has risen at least %g cm" % LID_MOVED_CM)
    t.delay(LID_POP_SECONDS + HEADLESS_FRAME_S)
    t.false(visible(t, crate_part(t, crate, "Lid")), "after its pop the Lid is hidden")
    t.true(t.get(ACTOR, "bHidden", BOOL, crate), "after the pop the collected crate actor is hidden")
    t.call(LOOTC, "Reset", crate)
    for name, cls in CRATE_PARTS:
        t.true(visible(t, crate_part(t, crate, name, cls)), "Reset shows the crate's %s again" % name)
    lid = crate_part(t, crate, "Lid")
    rel = t.get(SCENE_COMP, "RelativeLocation", STRUCT, lid, sub=struct_ref(VECTOR))
    at_rest = t.g.call_static(MATH, "EqualEqual_VectorVector", inputs=[struct_pin("A", VECTOR), struct_pin("B", VECTOR, default="0,0,0"),
                                                                     Pin("ErrorTolerance", FLOAT, default="0.1")],
                              outputs=[Pin("ReturnValue", BOOL, "out")], pure=True)
    t.link(rel, at_rest, "A")
    t.true((at_rest, "ReturnValue"), "after Reset the Lid's relative location is its rest, (0, 0, 0) on the Lid socket")
    rot = t.get(SCENE_COMP, "RelativeRotation", STRUCT, lid, sub=struct_ref(ROTATOR))
    level = t.g.call_static(MATH, "EqualEqual_RotatorRotator", inputs=[struct_pin("A", ROTATOR), struct_pin("B", ROTATOR, default="0,0,0"),
                                                                     Pin("ErrorTolerance", FLOAT, default="0.1")],
                            outputs=[Pin("ReturnValue", BOOL, "out")], pure=True)
    t.link(rot, level, "A")
    t.true((level, "ReturnValue"), "after Reset the Lid's relative rotation is its rest, (0, 0, 0)")
    seat = socket_at(t, crate_part(t, crate, "Crate"), "Lid")
    check(t, "LessEqual_FloatFloat", t.distance(comp_loc(t, lid), seat), 0.5, "after Reset the Lid sits on the Crate's Lid socket")
    destroy(t, crate)
    destroy(t, ch)
    return t.finish()


def delay_for(t: T, seconds_src):
    """Delay(Duration) with the duration wired from a float source."""
    n = t.static("KismetSystemLibrary", "Delay", inputs=[Pin("WorldContextObject", OBJECT, hidden=True), Pin("Duration", FLOAT)])
    t.link(seconds_src, n, "Duration")


def look_near(t: T, a, b, message):
    gap = t.distance(a, b)
    flog(t, "ART LOOK %s (cm)" % message, gap)
    check(t, "LessEqual_FloatFloat", gap, LOOK_TOL_CM, "%s: within %g cm" % (message, LOOK_TOL_CM))


def flames_at_sockets(t: T, car, n):
    for name, socket in (("BoostFlameL", "Exhaust_L"), ("BoostFlameR", "Exhaust_R")):
        where = t.g.call_on(SCENE_COMP, "K2_GetComponentLocation", outputs=[struct_pin("ReturnValue", VECTOR, "out")], pure=True)
        t.link(comp(t, car, name), where, "self")
        look_near(t, (where, "ReturnValue"), socket_at(t, comp(t, car, "Body"), socket), "%s %s from Body's %s socket" % (n, name, socket))


def boost_flames_test():
    row = VEHICLES[2]  # VIPER: its Body mesh is the construction script's swap (the flames ride on its own Exhaust sockets)
    t = T("FT_DFArt_BoostFlamesWhileBoosting", "Spec §7.5, on a %s: BoostFlameL/R are hidden on a fresh car, shown right after "
          "ActivateBoost (each within 2 cm of its Exhaust_L/R socket on the swapped Body), and hidden BoostDuration + 0.2 s later "
          "(the test ticks after the car; its kick and force are zeroed so it stands still)." % row.name)
    car = spawn_class(t, row.asset)
    tick_before_test(t, car)
    for var in ("BoostKickSpeed", "BoostAcceleration"):
        t.set(VC, var, FLOAT, car, default="0.0")
    for name in ("BoostFlameL", "BoostFlameR"):
        t.false(visible(t, comp(t, car, name)), "%s: %s hidden before the boost" % (row.name, name))
    t.call(VC, "ActivateBoost", car)
    for name in ("BoostFlameL", "BoostFlameR"):
        t.true(visible(t, comp(t, car, name)), "%s: %s shown while boosting" % (row.name, name))
    flames_at_sockets(t, car, row.name)
    delay_for(t, fop(t, "Add_FloatFloat", t.get(VC, "BoostDuration", FLOAT, car), EFFECT_OVER_S))
    t.eq_float(t.get(VC, "BoostRemaining", FLOAT, car), 0.0, "the boost has run out")
    for name in ("BoostFlameL", "BoostFlameR"):
        t.false(visible(t, comp(t, car, name)), "%s: %s hidden BoostDuration + %g s after the boost" % (row.name, name, EFFECT_OVER_S))
    destroy(t, car)
    return t.finish()


def shield_bubble_test():
    row = VEHICLES[1]  # BRUTE: a swapped Body mesh, much taller than SEDAN's (the bubble still sits at Body x SHIELD_BUBBLE_AT)
    t = T("FT_DFArt_ShieldBubbleWhileActive", "Spec §7.5, on a %s: ShieldBubble is hidden on a fresh car, shown right after "
          "ActivateShield (its centre within 2 cm of Body x (2.2, 0, 95.8)), and hidden ShieldDuration + 0.2 s later (the test "
          "ticks after the car). Shielded again, a blocked hit sets the bubble MID's Glow to 3, and 0.5 s later it is back to the "
          "MI's glow." % row.name)
    car = spawn_class(t, row.asset)
    tick_before_test(t, car)
    bubble = comp(t, car, "ShieldBubble")
    t.false(visible(t, bubble), "%s: the shield bubble is hidden before the shield" % row.name)
    t.call(VC, "ActivateShield", car)
    t.true(visible(t, bubble), "%s: the shield bubble is shown while shielded" % row.name)
    centre = t.g.call_on(SCENE_COMP, "K2_GetComponentLocation", outputs=[struct_pin("ReturnValue", VECTOR, "out")], pure=True)
    t.link(bubble, centre, "self")
    body_xf = t.g.call_on(SCENE_COMP, "K2_GetComponentToWorld", outputs=[struct_pin("ReturnValue", TRANSFORM, "out")], pure=True)
    t.link(comp(t, car, "Body"), body_xf, "self")
    want = t.g.call_static(MATH, "TransformLocation", inputs=[struct_pin("T", TRANSFORM), struct_pin("Location", VECTOR, default="%g,%g,%g" % SHIELD_BUBBLE_AT)],
                           outputs=[struct_pin("ReturnValue", VECTOR, "out")], pure=True)
    t.g.link(body_xf, "ReturnValue", want, "T")
    look_near(t, (centre, "ReturnValue"), (want, "ReturnValue"), "%s ShieldBubble from Body x (%g, %g, %g)" % ((row.name,) + SHIELD_BUBBLE_AT))
    delay_for(t, fop(t, "Add_FloatFloat", t.get(VC, "ShieldDuration", FLOAT, car), EFFECT_OVER_S))
    shielded = t.call(VC, "IsShielded", car, outputs=[Pin("ReturnValue", BOOL, "out")], pure=True)
    t.false((shielded, "ReturnValue"), "the shield has run out")
    t.false(visible(t, bubble), "%s: the shield bubble is hidden ShieldDuration + %g s after the shield" % (row.name, EFFECT_OVER_S))
    t.call(VC, "ActivateShield", car)
    mid = t.get(VC, "ShieldMID", OBJECT, car, sub=cls_ref(MID))
    t.same(material_of(t, bubble, 0), mid, "the shield bubble shows ShieldMID")
    t.damage(car, 10)
    t.eq_float(t.get(VC, "Health", FLOAT, car), float(row.max_health), "the hit is blocked")
    t.eq_float(mid_param(t, mid, "Scalar", "Glow"), SHIELD_HIT_GLOW, "the bubble's Glow right after a blocked hit")
    t.delay(SHIELD_HIT_WAIT_S)
    near_equal(t, mid_param(t, mid, "Scalar", "Glow"), t.get(VC, "ShieldBaseGlow", FLOAT, car), 0.001,
               "the bubble's Glow is back to the MI's %g s after the hit" % SHIELD_HIT_WAIT_S)
    check(t, "Less_FloatFloat", t.get(VC, "ShieldBaseGlow", FLOAT, car), SHIELD_HIT_GLOW, "the bubble's own glow is below the hit flash's")
    t.call(VC, "ClearEffects", car)
    destroy(t, car)
    return t.finish()


def bomb_blink_test():
    t = T("FT_DFArt_BombBlinkSpeedsUp", "Spec §7.5: the bomb (Shell SM_DF_Bomb, its BombLamp slot the BlinkLamp MID) blinks faster "
          "as the fuse runs: ComputeBlinkHz is 1 at 0 s, 3.5 at FuseSeconds / 2, 6 at FuseSeconds and 6 beyond it.")
    bomb = spawn_bomb(t)
    shell = t.get(BOMBC, "Shell", OBJECT, bomb, sub=cls_ref(STATIC_MESH_COMP))
    # fix round 1 (controller ruling): the old bomb's touch, a 25 cm sphere centred 55 cm over the ground (the mine rests on it)
    trigger = t.get(BOMBC, "Trigger", OBJECT, bomb, sub=cls_ref(SPHERE_COMP))
    radius = t.call(SPHERE_COMP, "GetScaledSphereRadius", trigger, outputs=[Pin("ReturnValue", FLOAT, "out")], pure=True)
    t.eq_float((radius, "ReturnValue"), BOMB_TRIGGER_R, "the bomb's touch sphere radius (cm), the old bomb's reach", 0.01)
    t.eq_float(fop(t, "Subtract_FloatFloat", vec_part(t, comp_loc(t, trigger), "Z"), vec_part(t, t.loc(bomb), "Z")), BOMB_TRIGGER_Z,
               "the touch sphere's centre over the mine's base on the ground (cm), as the old bomb's", 0.5)
    same_asset(t, mesh_of(t, shell), SM_BOMB, "the bomb's Shell shows SM_DF_Bomb")
    t.same(material_of(t, shell, BOMB_LAMP_SLOT), t.get(BOMBC, "BlinkLamp", OBJECT, bomb, sub=cls_ref(MID)),
           "the Shell's lamp slot (%d) shows the BlinkLamp MID" % BOMB_LAMP_SLOT)
    fuse = t.get(BOMBC, "FuseSeconds", FLOAT, bomb)
    for elapsed, hz, what in (("0.0", 1.0, "at 0 s"), (fop(t, "Multiply_FloatFloat", fuse, 0.5), 3.5, "at FuseSeconds / 2"),
                              (fuse, 6.0, "at FuseSeconds"), (fop(t, "Multiply_FloatFloat", fuse, 2.0), 6.0, "at 2 x FuseSeconds")):
        n = t.call(BOMBC, "ComputeBlinkHz", bomb, inputs=[Pin("Elapsed", FLOAT, default=elapsed if isinstance(elapsed, str) else None)],
                   outputs=[Pin("Hz", FLOAT, "out")], pure=True)
        if not isinstance(elapsed, str):
            t.link(elapsed, n, "Elapsed")
        t.eq_float((n, "Hz"), hz, "ComputeBlinkHz %s (Hz)" % what, 0.001)
    destroy(t, bomb)
    return t.finish()


def task17_tests():
    return [crate_colour_test(), collected_crate_test(), shield_bubble_test(), boost_flames_test(), bomb_blink_test()]


# ---- Task 18: the race HUD's hit marker, crate prompt and damage vignette (spec §7.6) ----
WHUD, PCC = gen(WBP_HUD), gen(BP_PC)
WIDGET_TRANSFORM, VECTOR2D = "/Script/UMG.WidgetTransform", "/Script/CoreUObject.Vector2D"
CRATE_NEAR_CM, CRATE_FAR_CM = 2000.0, 6000.0  # the brief's 20 m and 60 m, either side of CRATE_PROMPT_CM (40 m)
VIGNETTE_HIT = 10.0                          # the brief's 10 damage


def colour_literal(rgba):
    return "(R=%f,G=%f,B=%f,A=%f)" % tuple(rgba)


def race_hud(t: T):
    """The one race HUD on screen (asserted)."""
    huds = widgets(t, WHUD)
    t.eq_int(t.length(huds, WHUD), 1, "one race HUD on screen")
    return t.item(huds, WHUD)


def crosshair_is(t: T, cross, rgba, scale, what):
    """The crosshair image's colour (ColorAndOpacity, within 0.01) and its render scale (both axes, within 0.001)."""
    colour_near(t, t.get(IMAGE, "ColorAndOpacity", STRUCT, cross, sub=struct_ref(LINEAR_COLOR)), colour_literal(rgba),
                "%s: the crosshair's colour is (%g, %g, %g, %g)" % ((what,) + tuple(rgba)))
    xf = t.get(WIDGET_W, "RenderTransform", STRUCT, cross, sub=struct_ref(WIDGET_TRANSFORM))
    br = t.g.break_struct(WIDGET_TRANSFORM, [struct_pin("Scale", VECTOR2D, "out")])
    t.link(xf, br, WIDGET_TRANSFORM.rsplit(".", 1)[1])
    want = t.g.call_static(MATH, "MakeVector2D", inputs=[Pin("X", FLOAT, default="%f" % scale), Pin("Y", FLOAT, default="%f" % scale)],
                           outputs=[struct_pin("ReturnValue", VECTOR2D, "out")], pure=True)  # wired: no Vector2D text default to parse
    eq = t.g.call_static(MATH, "EqualEqual_Vector2DVector2D", inputs=[struct_pin("A", VECTOR2D), struct_pin("B", VECTOR2D),
                                                                     Pin("ErrorTolerance", FLOAT, default="0.001")],
                         outputs=[Pin("ReturnValue", BOOL, "out")], pure=True)
    t.g.link(br, "Scale", eq, "A")
    t.g.link(want, "ReturnValue", eq, "B")
    t.true((eq, "ReturnValue"), "%s: the crosshair's render scale is %g" % (what, scale))


def hit_marker_test():
    t = T("FT_DFHUD_HitMarkerOnHit", "Spec §7.6, §7.2: the player gets out of the car (the crosshair shows on foot) and the player's "
          "character fires (its Weapon's Fire from 4 m behind a target car, along +X). In the frame of the hit the race HUD's "
          "crosshair is red (%s) at %gx; %g s later (the %g s marker plus one headless frame) it is white at 1x again. A shot "
          "straight down from the character into the road under it (a hit, but not on a car or a character) leaves it white at 1x."
          % (colour_literal(HUD_RED), HIT_MARKER_SCALE, HIT_MARKER_SECONDS + HEADLESS_FRAME_S, HIT_MARKER_SECONDS))
    pc, gm, gs, racer, gates = race_context(t)
    out = t.call(VC, "ExitVehicle", pawn_car(t, pc), outputs=[Pin("ReturnValue", BOOL, "out")])
    t.true((out, "ReturnValue"), "the player gets out of the car")
    target = spawn_vehicle(t)
    t.delay(1.0)  # the target settles; the HUD has refreshed on foot (and bound the character's weapon)
    cross = hud_part(t, race_hud(t), "CrosshairImage", IMAGE)
    t.true(widget_shown(t, cross), "on foot the crosshair is shown")
    crosshair_is(t, cross, HUD_WHITE, 1.0, "before the shot")
    ch = t.get(PCC, "OnFootCharacter", OBJECT, pc, sub=cls_ref(CC))

    def fire(origin, direction):
        """The player's character's Weapon.Fire(origin, direction), credited to the player (stepped); its (bHit, Hit) sources."""
        n = t.call(WC, "Fire", t.get(CC, "Weapon", OBJECT, ch, sub=cls_ref(WC)),
                   inputs=[struct_pin("Origin", VECTOR), struct_pin("Direction", VECTOR, default=direction), obj_pin("Instigator", CONTROLLER)],
                   outputs=[Pin("bHit", BOOL, "out"), struct_pin("Hit", HIT_RESULT, "out")])
        t.link(origin, n, "Origin")
        t.link(pc, n, "Instigator")
        return (n, "bHit"), (n, "Hit")

    hit, _ = fire(t.offset(t.loc(target), -400.0, 0.0, 80.0), "1,0,0")
    t.true(hit, "the player's character hits the target car")
    crosshair_is(t, cross, HUD_RED, HIT_MARKER_SCALE, "in the frame of the hit")
    t.delay(HIT_MARKER_SECONDS + HEADLESS_FRAME_S)
    crosshair_is(t, cross, HUD_WHITE, 1.0, "%g s after the hit" % (HIT_MARKER_SECONDS + HEADLESS_FRAME_S))
    # fix round 1 (controller ruling, spec §7.2 "on a hit"): the marker is for a car or a character; the road is no target. The
    # shot starts at the character (its own trace ignores it) beside the parked car on the start line, straight down
    ground, ground_hit = fire(t.loc(ch), "0,0,-1")
    t.true(ground, "the shot straight down hits the road under the character")
    what = t.g.call_static(GAMEPLAY, "BreakHitResult", inputs=[struct_pin("Hit", HIT_RESULT)], outputs=[obj_pin("HitActor", ACTOR, "out")], pure=True)
    t.link(ground_hit, what, "Hit")
    t.step(log_line(t.g, "HUD SHOT straight down hit ", name_of(t.g, (what, "HitActor"))))
    crosshair_is(t, cross, HUD_WHITE, 1.0, "in the frame of a shot into the road")
    destroy(t, target)
    return t.finish()


def warning_reads(t: T, hud, expected, equal, message):
    """Logs the race HUD's warning line, then AssertTrue / AssertFalse(it == expected)."""
    txt = t.g.call_on(TEXT_BLOCK, "GetText", outputs=[Pin("ReturnValue", "text", "out")], pure=True)
    t.link(hud_part(t, hud, "WarningText", TEXT_BLOCK), txt, "self")
    s = t.g.call_static("KismetTextLibrary", "Conv_TextToString", inputs=[Pin("InText", "text")], outputs=[Pin("ReturnValue", STRING, "out")], pure=True)
    t.g.link(txt, "ReturnValue", s, "InText")
    t.step(log_line(t.g, "HUD WARNING ", (s, "ReturnValue")))
    eq = t.g.call_static("KismetStringLibrary", "EqualEqual_StrStr", inputs=[Pin("A", STRING), Pin("B", STRING, default=expected)],
                         outputs=[Pin("ReturnValue", BOOL, "out")], pure=True)
    t.g.link(s, "ReturnValue", eq, "A")
    (t.true if equal else t.false)((eq, "ReturnValue"), message)


def nearest_crate(t: T, gm, car):
    """GameMode.FindNearestCrate(the car's location) -> (Crate, Distance) sources (impure: stepped)."""
    n = t.call(GMC, "FindNearestCrate", gm, inputs=[struct_pin("Location", VECTOR)],
               outputs=[obj_pin("Crate", LOOTC, "out"), Pin("Distance", FLOAT, "out")])
    t.link(t.loc(car), n, "Location")
    return (n, "Crate"), (n, "Distance")


def crate_prompt_test():
    t = T("FT_DFHUD_CratePromptNearCrate", "Spec §7.6, §7.4: the player's car stands on the start line (below exit speed, on the "
          "road) with a crate %g m to its side: FindNearestCrate finds it and the race HUD's warning line reads '%s'. With the "
          "crate moved %g m away it does not." % (CRATE_NEAR_CM / 100, CRATE_PROMPT, CRATE_FAR_CM / 100))
    pc, gm, gs, racer, gates = race_context(t)
    car = pawn_car(t, pc)
    slow = t.call(VC, "IsBelowExitSpeed", car, outputs=[Pin("ReturnValue", BOOL, "out")], pure=True)
    t.true((slow, "ReturnValue"), "the player's car stands below exit speed")
    crate = t.spawn(LOOTC, t.offset(t.loc(car), 0.0, -CRATE_NEAR_CM, 0.0))
    t.delay(HEADLESS_FRAME_S)  # the HUD refreshes with the crate there
    found, dist = nearest_crate(t, gm, car)
    flog(t, "HUD CRATE nearest crate distance (cm)", dist)
    t.same(found, crate, "FindNearestCrate finds the crate %g m away" % (CRATE_NEAR_CM / 100))
    t.eq_float(dist, CRATE_NEAR_CM, "its distance (cm)", 5.0)
    hud = race_hud(t)
    warning_reads(t, hud, CRATE_PROMPT, True, "%g m from a crate, stopped in the car, the warning line reads the crate prompt" % (CRATE_NEAR_CM / 100))
    move_to(t, crate, t.offset(t.loc(car), 0.0, -CRATE_FAR_CM, 0.0))
    t.delay(HEADLESS_FRAME_S)
    found2, dist2 = nearest_crate(t, gm, car)
    flog(t, "HUD CRATE nearest crate distance after the move (cm)", dist2)
    warning_reads(t, hud, CRATE_PROMPT, False, "%g m from the crate the warning line is not the crate prompt" % (CRATE_FAR_CM / 100))
    destroy(t, crate)
    return t.finish()


def damage_vignette_test():
    t = T("FT_DFHUD_DamageVignette", "Spec §7.6: the player's car takes %g damage: in that frame the race HUD's Vignette is shown, "
          "and %g s later (the %g s vignette plus one headless frame) it is hidden. Out of the car, a %g-point hit on the player's "
          "character shows it again." % (VIGNETTE_HIT, DAMAGE_SECONDS + HEADLESS_FRAME_S, DAMAGE_SECONDS, VIGNETTE_HIT))
    t.bp.variable("HealthBefore", "float", "0")
    pc, gm, gs, racer, gates = race_context(t)
    car = pawn_car(t, pc)
    vignette = hud_part(t, race_hud(t), "Vignette", IMAGE)
    t.false(widget_shown(t, vignette), "the vignette is hidden before the hit")
    before = t.get(VC, "Health", FLOAT, car)
    store(t, "HealthBefore", before)
    t.damage(car, VIGNETTE_HIT)
    t.eq_float(fop(t, "Subtract_FloatFloat", tvar(t, "HealthBefore"), t.get(VC, "Health", FLOAT, car)), VIGNETTE_HIT, "the car took the damage")
    t.true(widget_shown(t, vignette), "the vignette is shown in the frame of the hit")
    t.delay(DAMAGE_SECONDS + HEADLESS_FRAME_S)
    t.false(widget_shown(t, vignette), "the vignette is hidden %g s after the hit" % (DAMAGE_SECONDS + HEADLESS_FRAME_S))
    # beyond the brief, spec §7.6 "car or character": on foot, the character's hit shows it too (the HUD binds OnCharacterDamaged)
    out = t.call(VC, "ExitVehicle", car, outputs=[Pin("ReturnValue", BOOL, "out")])
    t.true((out, "ReturnValue"), "the player gets out of the car")
    ch = t.get(PCC, "OnFootCharacter", OBJECT, pc, sub=cls_ref(CC))
    t.damage(ch, VIGNETTE_HIT)
    t.eq_float(fop(t, "Subtract_FloatFloat", t.get(CC, "MaxHealth", FLOAT, ch), t.get(CC, "Health", FLOAT, ch)), VIGNETTE_HIT,
               "the character (full health after the restart) took the damage")
    t.true(widget_shown(t, vignette), "the vignette is shown in the frame of the character's hit")
    return t.finish()


def task18_tests():
    return [hit_marker_test(), crate_prompt_test(), damage_vignette_test()]


# ---- Task 21: the gates' glow, the rock's chunks, the scatter actor (spec §8.2, §8.3) ----
CPC, DESTC, DEBRISC, SCATTERC = gen(BP_CHECKPOINT), gen(BP_DESTRUCTIBLE), gen(BP_DEBRIS), gen(BP_SCATTER)
TEST_GATES = 4             # the functional-test level's gates (PROVING GROUND's layout; FT_DFRace_PlayerStartsInCar counts them)
GATE_PARTS = ("LeftPole", "RightPole", "Banner")  # the gate's three glowing meshes, in GlowMIDs order
ROCK_GROUND_Z = -2.0       # df_build_test_track.SHORTCUT_Z: the shortcut's slab top, where the level's rock stands
ROCK_LEVEL_HEIGHT = 400.0  # df_build_test_track.ROCK_SCALE's 4 on Z x SM_DF_RockWall's 100 cm
ROCK_TOL_CM = 5.0          # SM_DF_RockWall fills its 100 cm cube to +-0.5 cm per axis (Task 20), x 4
TEST_ROCK_SCALE = 3.0      # the test rock: BP_DFDestructible's template scale, a 3 m block
CHUNK_NEAR_CM = 150.0      # every cell centre of a 3 m rock lies 130 cm from its centre (sqrt(3) x 75)
DEBRIS_GONE_S = 9.0        # past the chunks' 8 s life span by about three headless frames
SCATTER_AT = ((0.0, 0.0, 0.0), (400.0, 0.0, 0.0), (0.0, 400.0, 0.0))  # the three instances, relative to the scatter actor
COLLISION_NONE, COLLISION_QUERY_AND_PHYSICS = 0, 3  # ECollisionEnabled
CHANNEL_PAWN, CHANNEL_PHYSICS_BODY, CHANNEL_VEHICLE, RESPONSE_IGNORE = 2, 5, 6, 0  # ECollisionChannel / ECollisionResponse


def gate_glows(t: T, gates, bright, what, parts_check=False):
    """Every gate's three GlowMIDs (LeftPole, RightPole, Banner): Glow 4.0 on gate `bright`, 0.6 on the others; parts_check: also
    that each gate has three, and that each is its mesh's slot 0 (Gate) material."""
    for i in range(TEST_GATES):
        gate = t.item(gates, CPC, str(i))
        mids = t.get(CPC, "GlowMIDs", OBJECT, gate, sub=cls_ref(MID), container="Array")
        if parts_check:
            t.eq_int(t.length(mids, MID), len(GATE_PARTS), "gate %d: glow MIDs (LeftPole, RightPole, Banner)" % i)
        for k, part in enumerate(GATE_PARTS):
            mid = t.item(mids, MID, str(k))
            if parts_check:
                t.same(material_of(t, t.get(CPC, part, OBJECT, gate, sub=cls_ref(STATIC_MESH_COMP)), 0), mid,
                       "gate %d: its %s's Gate slot (0) shows glow MID %d" % (i, part, k))
            glow = GATE_GLOW_ON if i == bright else GATE_GLOW_OFF
            t.eq_float(mid_param(t, mid, "Scalar", "Glow"), glow, "%s: gate %d's %s Glow (%s)" % (what, i, part, "the next gate" if i == bright else "dim"),
                       0.001)


def next_gate_test():
    t = T("FT_DFArt_NextGateHighlighted", "Spec §8.2: after RestartRace the player's next gate (1) glows (its pylons' and banner's "
          "Gate MIDs at Glow %g) and the other gates are dim (%g). Passing gate 1 (NotifyCheckpointReached, which advances the gate "
          "through NotifyCheckpointPassed) lights gate 2 and dims gate 1; passing 2 and 3 lights the start line (0); crossing it "
          "(a lap) lights gate 1 again." % (GATE_GLOW_ON, GATE_GLOW_OFF))
    pc, gm, gs, racer, gates = race_context(t)
    t.eq_int(t.length(gates, CPC), TEST_GATES, "registered gates")
    t.eq_int(t.get(RC, "NextCheckpointIndex", INT, racer), 1, "the player's next gate after the restart")
    gate_glows(t, gates, 1, "after RestartRace", parts_check=True)
    t.true(notify(t, gm, pc, t.item(gates, CPC, "1")), "gate 1 credits")
    t.eq_int(t.get(RC, "NextCheckpointIndex", INT, racer), 2, "the player's next gate after gate 1")
    gate_glows(t, gates, 2, "after gate 1")
    for k in (2, 3):
        t.true(notify(t, gm, pc, t.item(gates, CPC, str(k))), "gate %d credits" % k)
    t.eq_int(t.get(RC, "NextCheckpointIndex", INT, racer), 0, "the player's next gate after gate 3 (the start line)")
    gate_glows(t, gates, 0, "after gate 3")
    t.true(notify(t, gm, pc, t.item(gates, CPC, "0")), "the start line credits (a lap)")
    t.eq_int(t.get(RC, "NextCheckpointIndex", INT, racer), 1, "the player's next gate after the lap")
    gate_glows(t, gates, 1, "after the lap")
    return t.finish()


def rock_part(t: T, rock):
    return t.get(DESTC, "Rock", OBJECT, rock, sub=cls_ref(STATIC_MESH_COMP))


def byte_is(t: T, src, value):
    """An enum (byte) source == value."""
    n = t.g.call_static(MATH, "EqualEqual_ByteByte", inputs=[Pin("A", BYTE), Pin("B", BYTE, default=str(value))],
                        outputs=[Pin("ReturnValue", BOOL, "out")], pure=True)
    t.link(src, n, "A")
    return (n, "ReturnValue")


def response_to(t: T, component, channel):
    n = t.g.call_on(PRIMITIVE, "GetCollisionResponseToChannel", inputs=[native_enum_pin("Channel", COLLISION_CHANNEL, channel)],
                    outputs=[native_enum_pin("ReturnValue", "/Script/Engine.ECollisionResponse", direction="out")], pure=True)
    t.link(component, n, "self")
    return (n, "ReturnValue")


def rock_chunks_test():
    t = T("FT_DFArt_RockBreaksIntoChunks", "Spec §8.2: the level's rock (centred SM_DF_RockWall) stands on the shortcut's road top, "
          "4 m tall as before. A %g m test rock's Demolish spawns %d BP_DFDebris (the restart before swept every earlier one), all "
          "within %g cm of its centre (a 2 x 2 x 2 grid over its bounds); a chunk is SM_DF_RockChunk sized to its cell, simulates "
          "physics as a PhysicsBody that ignores pawns and cars, and has an 8 s life span. %g s later none is left."
          % (TEST_ROCK_SCALE, len(ROCK_CHUNK_CELLS), CHUNK_NEAR_CM, DEBRIS_GONE_S))
    t.bp.variable("Chunks", "int", "0")
    t.bp.variable("Chunk", obj_spec(BP_DEBRIS), "")
    race_context(t)
    rocks = t.step(get_all_actors_of_class(t.g, DESTC))
    t.eq_int(t.length((rocks, "OutActors"), DESTC), 1, "one rock in the level before the test spawns its own")
    level_rock = rock_part(t, t.item((rocks, "OutActors"), DESTC))
    bottom, top = bounds_z(t, level_rock, False), bounds_z(t, level_rock, True)
    flog(t, "ART ROCK the level's rock: bottom, top Z (cm)", bottom, top)
    near_equal(t, bottom, ROCK_GROUND_Z, ROCK_TOL_CM, "the level's rock stands on the shortcut's road top (z %g): SM_DF_RockWall "
               "is centred, so the level raises it by half its height" % ROCK_GROUND_Z)
    near_equal(t, fop(t, "Subtract_FloatFloat", top, bottom), ROCK_LEVEL_HEIGHT, ROCK_TOL_CM, "the level's rock is 4 m tall, as before")
    rock = t.spawn(DESTC, t.offset(t.self_loc(), 0.0, 800.0, 0.0))
    t.call(ACTOR, "SetActorScale3D", rock, inputs=[struct_pin("NewScale3D", VECTOR, default="%g,%g,%g" % ((TEST_ROCK_SCALE,) * 3))])
    t.call(DESTC, "Demolish", rock)
    t.eq_int(count_actors(t, DEBRISC), len(ROCK_CHUNK_CELLS), "BP_DFDebris in the world right after Demolish")
    t.eq_int(count_near(t, "Chunks", DEBRISC, t.loc(rock), CHUNK_NEAR_CM, "rock chunk", keep="Chunk"), len(ROCK_CHUNK_CELLS),
             "chunks within %g cm of the rock's centre in the frame it breaks (a 2 x 2 x 2 grid over its bounds)" % CHUNK_NEAR_CM)
    chunk = t.get(DEBRISC, "Chunk", OBJECT, tobj(t, "Chunk", DEBRISC), sub=cls_ref(STATIC_MESH_COMP))
    same_asset(t, mesh_of(t, chunk), SM_ROCK_CHUNK, "a chunk shows SM_DF_RockChunk")
    scale = t.g.call_on(SCENE_COMP, "K2_GetComponentScale", outputs=[struct_pin("ReturnValue", VECTOR, "out")], pure=True)
    t.link(chunk, scale, "self")
    t.eq_float(vec_part(t, (scale, "ReturnValue"), "X"), 50.0 * TEST_ROCK_SCALE / ROCK_CHUNK_CM,
               "a chunk's scale: its cell (half the rock's %g cm) over the chunk's %g cm" % (100.0 * TEST_ROCK_SCALE, ROCK_CHUNK_CM), 0.01)
    sim = t.g.call_on(SCENE_COMP, "IsSimulatingPhysics", inputs=[Pin("BoneName", NAME, default="None")], outputs=[Pin("ReturnValue", BOOL, "out")],
                      pure=True)
    t.link(chunk, sim, "self")
    t.true((sim, "ReturnValue"), "a chunk simulates physics")
    kind = t.g.call_on(PRIMITIVE, "GetCollisionObjectType", outputs=[native_enum_pin("ReturnValue", COLLISION_CHANNEL, direction="out")], pure=True)
    t.link(chunk, kind, "self")
    t.true(byte_is(t, (kind, "ReturnValue"), CHANNEL_PHYSICS_BODY), "a chunk is a PhysicsBody (the PhysicsActor profile's object type)")
    for channel, value, what in (("ECC_Pawn", CHANNEL_PAWN, "pawns (the on-foot character)"), ("ECC_Vehicle", CHANNEL_VEHICLE, "cars")):
        t.true(byte_is(t, response_to(t, chunk, channel), RESPONSE_IGNORE), "a chunk ignores %s" % what)
    span = t.g.call_on(ACTOR, "GetLifeSpan", outputs=[Pin("ReturnValue", FLOAT, "out")], pure=True)
    t.link(tobj(t, "Chunk", DEBRISC), span, "self")
    flog(t, "ART ROCK a chunk's life span left (s)", (span, "ReturnValue"))
    check(t, "Greater_FloatFloat", (span, "ReturnValue"), DEBRIS_LIFE - 1.0, "a chunk's life span is set (more than 7 s left)")
    check(t, "LessEqual_FloatFloat", (span, "ReturnValue"), DEBRIS_LIFE + 0.001, "a chunk's life span is at most 8 s")
    t.delay(DEBRIS_GONE_S)
    t.eq_int(count_actors(t, DEBRISC), 0, "BP_DFDebris in the world %g s after Demolish (8 s life span)" % DEBRIS_GONE_S)
    destroy(t, rock)
    return t.finish()


def scatter_shows(t: T, inst, blocking, what):
    """The scatter's HISM has one instance per transform, and its collision profile and state follow bBlocking."""
    count =t.g.call_on(ISM_COMP, "GetInstanceCount", outputs=[Pin("ReturnValue", INT, "out")], pure=True)
    t.link(inst, count, "self")
    t.eq_int((count, "ReturnValue"), len(SCATTER_AT), "%s: the scatter's instances (one per transform)" % what)
    name = t.g.call_on(PRIMITIVE, "GetCollisionProfileName", outputs=[Pin("ReturnValue", NAME, "out")], pure=True)
    t.link(inst, name, "self")
    profile = "BlockAll" if blocking else "NoCollision"
    eq = t.g.call_static(MATH, "EqualEqual_NameName", inputs=[Pin("A", NAME), Pin("B", NAME, default=profile)],
                         outputs=[Pin("ReturnValue", BOOL, "out")], pure=True)
    t.g.link(name, "ReturnValue", eq, "A")
    t.true((eq, "ReturnValue"), "%s: the collision profile is %s" % (what, profile))
    enabled = t.g.call_on(PRIMITIVE, "GetCollisionEnabled", outputs=[native_enum_pin("ReturnValue", "/Script/Engine.ECollisionEnabled", direction="out")],
                          pure=True)
    t.link(inst, enabled, "self")
    t.true(byte_is(t, (enabled, "ReturnValue"), COLLISION_QUERY_AND_PHYSICS if blocking else COLLISION_NONE),
           "%s: collision is %s" % (what, "query and physics" if blocking else "off"))


def scatter_test():
    t = T("FT_DFArt_ScatterBuildsInstances", "Spec §8.3: a spawned BP_DFScatter given SM_DF_Rock01, three transforms and bBlocking "
          "false, then RebuildInstances (what its construction script runs; a deferred spawn cannot be generated), has 3 instances "
          "of SM_DF_Rock01, NoCollision, culled at %d cm. Rebuilt with bBlocking true it still has 3 (the old ones are cleared) and "
          "collides (BlockAll)." % SCATTER_CULL_CM)
    sc = t.spawn(SCATTERC, t.self_loc())
    mesh = t.set(SCATTERC, "Mesh", OBJECT, sc, sub=cls_ref(STATIC_MESH))
    mesh.pin("Mesh").default_object = asset_object(art_mesh("SM_DF_Rock01"))
    elem = Pin("e", STRUCT, sub_object=struct_ref(TRANSFORM))
    arr = t.g.make_array(elem, [None] * len(SCATTER_AT))
    for k, at in enumerate(SCATTER_AT):
        xf = t.g.call_static(MATH, "MakeTransform", inputs=[struct_pin("Location", VECTOR, default="%g,%g,%g" % at), struct_pin("Rotation", ROTATOR),
                                                              struct_pin("Scale", VECTOR, default="1,1,1")],
                             outputs=[struct_pin("ReturnValue", TRANSFORM, "out")], pure=True)
        t.g.link(xf, "ReturnValue", arr, "[%d]" % k)
    xfs = t.step(t.g.var_set_on(SCATTERC, "Transforms", STRUCT, sub_object=struct_ref(TRANSFORM), container="Array"))
    t.link(sc, xfs, "self")
    t.g.link(arr, "Array", xfs, "Transforms")
    t.set(SCATTERC, "bBlocking", BOOL, sc, default="false")
    t.call(SCATTERC, "RebuildInstances", sc)
    inst = t.get(SCATTERC, "Instances", OBJECT, sc, sub=cls_ref(HISM_COMP))
    scatter_shows(t, inst, False, "bBlocking false")
    same_asset(t, mesh_of(t, inst), art_mesh("SM_DF_Rock01"), "the scatter shows SM_DF_Rock01")
    t.eq_int(t.get(ISM_COMP, "InstanceEndCullDistance", INT, inst), SCATTER_CULL_CM, "the scatter's cull distance (cm)")
    t.set(SCATTERC, "bBlocking", BOOL, sc, default="true")
    t.call(SCATTERC, "RebuildInstances", sc)
    scatter_shows(t, inst, True, "rebuilt with bBlocking true")
    destroy(t, sc)
    return t.finish()


def task21_tests():
    return [next_gate_test(), rock_chunks_test(), scatter_test()]


def build():
    return (task13_tests() + task14_tests() + task15_tests() + task16_tests() + task17_tests() + task18_tests()
            + task21_tests())


if __name__ == "__main__":
    for b in build():
        print(b.write(OUT))
