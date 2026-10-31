"""Presentation captures (Phase 6, plan Task 6): FunctionalTest actors that take engine screenshots ("shot showui", the
game's own viewport only) of screens the functional-test level cannot show. They are NOT tests: the level builder
never places FT_DFShot_* in L_DF_FunctionalTests. A capture run places one in its level for the run only:

    FT_DFShot_Menu  in L_MainMenu:  main page, car page (SEDAN, BRUTE locked), track page (PROVING GROUND, SWITCHBACK
                                    locked), settings
    FT_DFShot_Pause in L_TestTrack: the race with its three rivals, then the pause menu over it
    FT_DFShot_LookDev in L_DF_LookDev (Phase 7): one image through each camera tagged LookDevShot00..47 that the level
                                    builder placed (material balls and meshes under the dusk light)
    FT_DFShot_Fx    in L_DF_LookDev (Phase 7 Task 15): each BP_DFFx effect at mid-life, through a camera it spawns
    FT_DFShot_Combat in L_DF_FunctionalTests (Phase 7 Task 16): the car's gun shot, a rocket in flight, an explosion and its
                    scorch, through the real paths (the race GameMode the look-dev level does not have)
    FT_DFShot_Scorch in L_DF_LookDev or L_DF_FunctionalTests (Phase 7 Task 16 fix round 1): one scorch decal on a clear patch
                    of floor, lit and through the buffer visualisation (BaseColor, Specular, Roughness, Metallic)
    FT_DFShot_Track in L_DF_FunctionalTests (Phase 7 Task 21): the player's next gate lit and another dim, and the shortcut's
                    rock wall whole, breaking into its chunks and broken
    FT_DFShot_Points in L_TestTrack or L_Switchback (Phase 7 Task 22): the grid, four fixed points along the main road, the item
                    looks and the player on foot, on the shipped level's terrain under its dusk light
    FT_DFShot_Race  in L_TestTrack (Phase 7 Task 24): the deck's race images with the HUD (the grid, the rivals ahead, on foot,
                    the summary's unlock line, the item looks), as FT_DFZZ_Screenshots takes them in the functional-test level
    FT_DFShot_Top   in L_Switchback or L_TestTrack (Phase 7 Task 24): the track from straight above
    FT_DFShot_Drift in L_TestTrack (Phase 7 Task 24 fix round 1): the player's car mid-drift with its tyre smoke, from the chase
                    camera (with the HUD) and from beside the road

The menu, pause, race and top captures switch the GameInstance to a save slot that has no file (DeadFireShots), so every lock
shows and the developer's progress is neither read nor written. Images land in comp4900sef/Saved/Screenshots/Windows/.
"""
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, ".."))
from bpgen import CLASS, cls_ref  # noqa: E402
from df import (ACTOR, BOOL, BP_MENU_PC, FLOAT, GAMEPLAY, NAME, OBJECT, OUT, PLAYER_CONTROLLER, STRING, USER_WIDGET,  # noqa: E402
                WBP_LEVEL_SELECT, WBP_MAIN_MENU, WBP_PAUSE, WBP_SETTINGS, WBP_VEHICLE_SELECT, INT, Pin, as_pin, compare, gen,
                get_player_controller, native_enum_pin, obj_pin)
from df import (BP_FX_EXPLOSION, BP_FX_IMPACT, BP_FX_LOOT_BURST, BP_FX_MUZZLE, BP_FX_PUFF, BP_FX_SPARKS,  # noqa: E402  (Task 15)
                BP_FX_TRACER, CAMERA_ACTOR, CAMERA_COMP, MATH, ROTATOR, TRANSFORM, VECTOR, log_line, spawn_fx, struct_pin)
from tests import T, TC  # noqa: E402
from tests_art import bind_cleanup  # noqa: E402
from tests_menu import game_instance  # noqa: E402
from tests_ship import delete_slot, use_slot  # noqa: E402
from df import BP_GM, ITEM_GUN, ITEM_RPG  # noqa: E402  (Task 16)
from df import DECAL_COMP, MATERIAL_INTERFACE, MI_SCORCH, SCORCH_SIZE, asset_object  # noqa: E402  (Task 16 fix round 1)
from tests_items import GMC, PROJC, VC, explode, grant, pawn_car  # noqa: E402  (Task 16)
from df import BP_CHECKPOINT, BP_DESTRUCTIBLE, get_all_actors_of_class  # noqa: E402  (Task 21)
from df import CONTROLLER, PAWN  # noqa: E402  (Task 22)

MPCC = gen(BP_MENU_PC)
SLOT = "DeadFireShots"


def shot(t: T, settle=1.0, command="shot showui"):
    t.delay(settle)
    t.static("KismetSystemLibrary", "ExecuteConsoleCommand",
             inputs=[Pin("WorldContextObject", OBJECT, hidden=True), Pin("Command", STRING, default=command),
                     obj_pin("SpecificPlayer", "/Script/Engine.PlayerController")])
    t.delay(1.0)


def fresh_slot(t: T):
    gi = game_instance(t)
    delete_slot(t, SLOT)
    use_slot(t, gi, SLOT)
    return gi


def menu_pc(t: T):
    c = t.step(t.g.cast(MPCC))
    t.g.link(get_player_controller(t.g), "ReturnValue", c, "Object")
    return (c, as_pin(BP_MENU_PC))


def show_page(t: T, pc, asset):
    t.call(MPCC, "ShowPage", pc, inputs=[Pin("PageClass", CLASS, sub_object=cls_ref(USER_WIDGET), default_object=gen(asset))])


def current_page(t: T, pc, asset):
    c = t.step(t.g.cast(gen(asset)))
    t.link(t.get(MPCC, "CurrentPage", OBJECT, pc, sub=cls_ref(USER_WIDGET)), c, "Object")
    return (c, as_pin(asset))


LOOKDEV_SHOTS = 48  # df_build_test_track.LOOKDEV_MAX_SHOTS (Task 20: 32 -> 48, the level now needs 37)
LOOKDEV_TIME_LIMIT = 150.0  # s; each shot takes about 2 s of game time (settle, shot, wait), past AFunctionalTest's default 60 s


def lookdev_shot(t: T, tag: str, settle: float):
    """Views through the actor tagged `tag` and takes a shot; skips both when the level has no such actor. Returns the
    branch, whose else pin the caller wires to the next step."""
    get = t.static(GAMEPLAY, "GetAllActorsWithTag", inputs=[Pin("WorldContextObject", OBJECT, hidden=True), Pin("Tag", NAME, default=tag)],
                   outputs=[Pin("OutActors", OBJECT, "out", cls_ref(ACTOR), container="Array")])
    has = compare(t.g, "Greater_IntInt", INT, b="0")
    t.link(t.length((get, "OutActors"), ACTOR), has, "A")
    branch = t.step(t.g.branch())
    t.link((has, "ReturnValue"), branch, "Condition")
    view = t.call(PLAYER_CONTROLLER, "SetViewTargetWithBlend", (get_player_controller(t.g), "ReturnValue"),
           inputs=[obj_pin("NewViewTarget", ACTOR), Pin("BlendTime", FLOAT, default="0.0"),
                   native_enum_pin("BlendFunc", "/Script/Engine.EViewTargetBlendFunction", "VTBlend_Linear"),
                   Pin("BlendExp", FLOAT, default="0.0"), Pin("bLockOutgoing", BOOL, default="false")])
    t.link(t.item((get, "OutActors"), ACTOR), view, "NewViewTarget")
    shot(t, settle, "shot")  # the scene only: no UI to show, and no window frame around a new-window PIE viewport
    return get, branch


# Phase 7 Task 15 (spec §7.1): each BP_DFFx child photographed at mid-life in the look-dev level. The effects are spawned at
# FX_SPOT, a clear patch of floor 26 m in front of the ball row; each camera looks +Y at it (screen left is +X; the dusk sun
# is behind the camera, to its right). Time is slowed to Lifetime / 3 while an effect lives, so its half-life wait is 1.5 s of real time and the "shot"
# lands within a frame of mid-life (a 60 ms muzzle flash could not be caught at full speed); dilation is back to 1 right
# after the shot and on every finish. (name, asset, lifetime s, offset from FX_SPOT cm, (pitch, yaw, roll), camera distance
# and height cm, aim height cm). tools/capture_shots.py fx saves them, in this order, as art/lookdev/fx-<n>-<name>.png.
FX_SPOT = (-1000.0, -2600.0, 0.0)
FX_SHOTS = [
    ("muzzle", BP_FX_MUZZLE, 0.06, (0.0, 0.0, 100.0), (0.0, 0.0, 0.0), 220.0, 150.0, 100.0),
    ("tracer", BP_FX_TRACER, 0.08, (-500.0, 0.0, 100.0), (0.0, 0.0, 0.0), 900.0, 300.0, 100.0),  # SetEnds to +1000 cm along X
    ("impact", BP_FX_IMPACT, 0.3, (0.0, 0.0, 0.0), (90.0, 0.0, 0.0), 320.0, 170.0, 40.0),  # +X (the surface normal) pointing up
    ("explosion", BP_FX_EXPLOSION, 1.2, (0.0, 0.0, 0.0), (0.0, 0.0, 0.0), 1700.0, 450.0, 250.0),
    ("puff", BP_FX_PUFF, 1.2, (0.0, 0.0, 60.0), (0.0, 0.0, 0.0), 420.0, 180.0, 110.0),
    ("lootburst", BP_FX_LOOT_BURST, 0.6, (0.0, 0.0, 0.0), (0.0, 0.0, 0.0), 600.0, 260.0, 90.0),
    ("sparks", BP_FX_SPARKS, 0.25, (0.0, 0.0, 80.0), (0.0, 0.0, 0.0), 260.0, 140.0, 80.0),
]
FX_LOOT_TINT = "(R=0.644480,G=0.070360,B=1.000000,A=1.000000)"  # the random crate's #D24BFF, linear (spec §3)


def literal_vec(t: T, x, y, z):
    n = t.g.call_static(MATH, "MakeVector", inputs=[Pin("X", FLOAT, default="%f" % x), Pin("Y", FLOAT, default="%f" % y),
                                                     Pin("Z", FLOAT, default="%f" % z)],
                        outputs=[struct_pin("ReturnValue", VECTOR, "out")], pure=True)
    return (n, "ReturnValue")


def make_transform(t: T, loc_src, rot_src):
    n = t.g.call_static(MATH, "MakeTransform", inputs=[struct_pin("Location", VECTOR), struct_pin("Rotation", ROTATOR),
                                                         struct_pin("Scale", VECTOR, default="1,1,1")],
                        outputs=[struct_pin("ReturnValue", TRANSFORM, "out")], pure=True)
    t.link(loc_src, n, "Location")
    t.link(rot_src, n, "Rotation")
    return (n, "ReturnValue")


def dilate(t: T, value):
    t.static(GAMEPLAY, "SetGlobalTimeDilation", inputs=[Pin("WorldContextObject", OBJECT, hidden=True), Pin("TimeDilation", FLOAT, default="%f" % value)])


def fx_shot(t: T, name, asset, life, offset, rot, distance, height, aim_z, settle):
    sx, sy, sz = FX_SPOT
    cam_at, aim_at = literal_vec(t, sx, sy - distance, height), literal_vec(t, sx, sy, aim_z)
    look = t.g.call_static(MATH, "FindLookAtRotation", inputs=[struct_pin("Start", VECTOR), struct_pin("Target", VECTOR)],
                           outputs=[struct_pin("ReturnValue", ROTATOR, "out")], pure=True)
    t.link(cam_at, look, "Start")
    t.link(aim_at, look, "Target")
    cam_spawn = t.step(t.g.spawn_actor(CAMERA_ACTOR))
    t.link(make_transform(t, cam_at, (look, "ReturnValue")), cam_spawn, "SpawnTransform")
    cam = (cam_spawn, "ReturnValue")
    lens = t.get(CAMERA_ACTOR, "CameraComponent", OBJECT, cam, sub=cls_ref(CAMERA_COMP))
    t.call(CAMERA_COMP, "SetFieldOfView", lens, inputs=[Pin("InFieldOfView", FLOAT, default="70.0")])
    t.call(CAMERA_COMP, "SetConstraintAspectRatio", lens, inputs=[Pin("bInConstrainAspectRatio", BOOL, default="false")])
    view = t.call(PLAYER_CONTROLLER, "SetViewTargetWithBlend", (get_player_controller(t.g), "ReturnValue"),
                  inputs=[obj_pin("NewViewTarget", ACTOR), Pin("BlendTime", FLOAT, default="0.0"),
                          native_enum_pin("BlendFunc", "/Script/Engine.EViewTargetBlendFunction", "VTBlend_Linear"),
                          Pin("BlendExp", FLOAT, default="0.0"), Pin("bLockOutgoing", BOOL, default="false")])
    t.link(cam, view, "NewViewTarget")
    t.delay(settle)
    dilate(t, min(1.0, life / 3.0))
    turn = t.g.call_static(MATH, "MakeRotator", inputs=[Pin("Roll", FLOAT, default="%f" % rot[2]), Pin("Pitch", FLOAT, default="%f" % rot[0]),
                                                        Pin("Yaw", FLOAT, default="%f" % rot[1])],
                           outputs=[struct_pin("ReturnValue", ROTATOR, "out")], pure=True)
    fx_at = literal_vec(t, sx + offset[0], sy + offset[1], sz + offset[2])
    first, last, fx = spawn_fx(t.g, asset, make_transform(t, fx_at, (turn, "ReturnValue")),
                               tint=FX_LOOT_TINT if asset == BP_FX_LOOT_BURST else None)
    t.g.link(t.prev[0], t.prev[1], first, "execute")
    t.prev = (last, "then")
    if asset == BP_FX_TRACER:
        ends = t.call(gen(BP_FX_TRACER), "SetEnds", fx, inputs=[struct_pin("Start", VECTOR), struct_pin("End", VECTOR)])
        t.link(fx_at, ends, "Start")
        t.link(literal_vec(t, sx + offset[0] + 1000.0, sy + offset[1], sz + offset[2]), ends, "End")
    t.delay(life / 2.0)
    t.step(log_line(t.g, "FX SHOT %s" % name))
    t.static("KismetSystemLibrary", "ExecuteConsoleCommand",
             inputs=[Pin("WorldContextObject", OBJECT, hidden=True), Pin("Command", STRING, default="shot"),
                     obj_pin("SpecificPlayer", "/Script/Engine.PlayerController")])
    dilate(t, 1.0)
    t.delay(1.0)
    t.call(ACTOR, "K2_DestroyActor", cam)


# Phase 7 Task 16 (spec §7.2, §7.3): the shots, the rocket and the explosion through their real paths (the car's FireGun and
# FireRPG, the race GameMode's SpawnExplosion and IsNearPlayerView), so this capture runs in the functional-test level
# (BP_DFTestGameMode, no rivals): the look-dev level's GameModeBase has neither. Each camera is placed from the player's car on
# the start line; time is slowed so the 0.06 s muzzle flash and the 1.2 s explosion are caught mid-life. The explosion's
# camera stands beyond the heavy shake's 25 m outer radius. tools/capture_shots.py combat saves art/lookdev/combat-<n>-<name>.png.
COMBAT_SHOTS = ["gunshot", "rocket", "explosion", "scorch"]


def view_from(t: T, cam_src, aim_src):
    """A camera at cam_src looking at aim_src (FOV 70), made the player's view target; returns the camera actor."""
    look = t.g.call_static(MATH, "FindLookAtRotation", inputs=[struct_pin("Start", VECTOR), struct_pin("Target", VECTOR)],
                           outputs=[struct_pin("ReturnValue", ROTATOR, "out")], pure=True)
    t.link(cam_src, look, "Start")
    t.link(aim_src, look, "Target")
    return view_at(t, cam_src, (look, "ReturnValue"))


def view_at(t: T, cam_src, rot_src, fov=70.0):
    """A camera at cam_src with rotation rot_src (lens fov degrees across), made the player's view target; returns the
    camera actor."""
    cam_spawn = t.step(t.g.spawn_actor(CAMERA_ACTOR))
    t.link(make_transform(t, cam_src, rot_src), cam_spawn, "SpawnTransform")
    cam = (cam_spawn, "ReturnValue")
    lens = t.get(CAMERA_ACTOR, "CameraComponent", OBJECT, cam, sub=cls_ref(CAMERA_COMP))
    t.call(CAMERA_COMP, "SetFieldOfView", lens, inputs=[Pin("InFieldOfView", FLOAT, default="%.1f" % fov)])
    t.call(CAMERA_COMP, "SetConstraintAspectRatio", lens, inputs=[Pin("bInConstrainAspectRatio", BOOL, default="false")])
    view = t.call(PLAYER_CONTROLLER, "SetViewTargetWithBlend", (get_player_controller(t.g), "ReturnValue"),
                  inputs=[obj_pin("NewViewTarget", ACTOR), Pin("BlendTime", FLOAT, default="0.0"),
                          native_enum_pin("BlendFunc", "/Script/Engine.EViewTargetBlendFunction", "VTBlend_Linear"),
                          Pin("BlendExp", FLOAT, default="0.0"), Pin("bLockOutgoing", BOOL, default="false")])
    t.link(cam, view, "NewViewTarget")
    return cam


# Phase 7 Task 17 (spec §7.4, §7.5): the item looks, appended to FT_DFZZ_Screenshots (tests.py screenshot_test, which is placed in
# L_DF_FunctionalTests, so the suite's count is unchanged); since Task 24 tools/capture_shots.py race takes them as 26-30 through FT_DFShot_Race in L_TestTrack. A Shield crate on the
# open ground about 40 m ahead of the player's car, seen from 2.5 m over the car (the road), then close up; a bomb just dropped,
# its lamp lit (it blinks from its first tick); the car's shield bubble; the boost flames through the car's own chase camera.
ITEM_SHOTS = ["crate-road-40m", "crate-close", "bomb", "shield", "boost"]
CRATE_AHEAD_CM, CRATE_SIDE_CM = 3800.0, 1200.0  # 39.8 m from the car
CRATE_Z = 30.0  # df_build_test_track.place_crates' height: the crate's centre, 40 cm over the -10 ground top (fix round 1)


def along(t: T, base, car, fwd=0.0, right=0.0, up=0.0):
    """base + the car's forward vector x fwd + its right vector x right + (0, 0, up) (pure)."""
    out = base
    for fn, k in (("GetActorForwardVector", fwd), ("GetActorRightVector", right)):
        if k:
            v = t.g.call_on(ACTOR, fn, outputs=[struct_pin("ReturnValue", VECTOR, "out")], pure=True)
            t.link(car, v, "self")
            m = t.g.call_static(MATH, "Multiply_VectorFloat", inputs=[struct_pin("A", VECTOR), Pin("B", FLOAT, default="%f" % k)],
                                outputs=[struct_pin("ReturnValue", VECTOR, "out")], pure=True)
            t.g.link(v, "ReturnValue", m, "A")
            a = t.g.call_static(MATH, "Add_VectorVector", inputs=[struct_pin("A", VECTOR), struct_pin("B", VECTOR)],
                                outputs=[struct_pin("ReturnValue", VECTOR, "out")], pure=True)
            t.link(out, a, "A")
            t.g.link(m, "ReturnValue", a, "B")
            out = (a, "ReturnValue")
    return t.offset(out, 0.0, 0.0, up) if up else out


def item_look_shots(t: T, pc, gm, shot):
    """The five item-look images (ITEM_SHOTS), each through shot() (the caller's "shot showui" and its wait); the race is
    restarted at the end (the car stands back on the line, its effects cleared)."""
    from df import BP_BOMB, BP_LOOTBOX, E_ITEM_TYPE, ITEM_SHIELD, enum_pin, enum_value
    lootc, bombc = gen(BP_LOOTBOX), gen(BP_BOMB)
    car = pawn_car(t, pc)
    t.step(log_line(t.g, "ITEM SHOTS %s" % ", ".join(ITEM_SHOTS)))
    ahead = t.g.call_static(MATH, "BreakVector", inputs=[struct_pin("InVec", VECTOR)],
                            outputs=[Pin("X", FLOAT, "out"), Pin("Y", FLOAT, "out"), Pin("Z", FLOAT, "out")], pure=True)
    t.link(along(t, t.loc(car), car, CRATE_AHEAD_CM, CRATE_SIDE_CM), ahead, "InVec")
    on_ground = t.g.call_static(MATH, "MakeVector", inputs=[Pin("X", FLOAT), Pin("Y", FLOAT), Pin("Z", FLOAT, default="%f" % CRATE_Z)],
                                outputs=[struct_pin("ReturnValue", VECTOR, "out")], pure=True)
    t.g.link(ahead, "X", on_ground, "X")
    t.g.link(ahead, "Y", on_ground, "Y")
    crate = t.spawn(lootc, (on_ground, "ReturnValue"))  # where a level puts a crate: resting on the ground
    t.set(lootc, "ItemType", "byte", crate, default=enum_value(ITEM_SHIELD), sub=enum_pin("x", E_ITEM_TYPE).sub_object)
    t.call(lootc, "ApplyLook", crate)
    # the crate actor stands at the crate's centre, 40 cm over the ground: aim at its icon from the road, at its lid close up
    for cam_at, aim in ((along(t, t.loc(car), car, up=250.0), t.offset(t.loc(crate), 0.0, 0.0, 110.0)),
                        (along(t, t.loc(crate), car, -300.0, -180.0, 130.0), t.offset(t.loc(crate), 0.0, 0.0, 40.0))):
        cam = view_from(t, cam_at, aim)
        t.delay(2.0)  # exposure settles
        shot()
        t.call(ACTOR, "K2_DestroyActor", cam)
    t.call(ACTOR, "K2_DestroyActor", crate)
    spot = along(t, t.loc(car), car, 700.0, -350.0, 30.0)
    cam = view_from(t, along(t, spot, car, -240.0, -110.0, 100.0), spot)
    t.delay(2.0)
    bomb = t.spawn(bombc, spot)  # PlaceOnGround drops it on the ground; its lamp comes on at its first tick (on for 0.5 s at 1 Hz)
    t.delay(0.15)
    shot()
    t.call(ACTOR, "K2_DestroyActor", bomb)
    t.call(ACTOR, "K2_DestroyActor", cam)
    t.call(VC, "ActivateShield", car)
    cam = view_from(t, along(t, t.loc(car), car, 450.0, 550.0, 220.0), t.offset(t.loc(car), 0.0, 0.0, 90.0))
    t.delay(2.0)
    shot()
    t.call(ACTOR, "K2_DestroyActor", cam)
    t.call(VC, "ClearEffects", car)
    back = t.call(PLAYER_CONTROLLER, "SetViewTargetWithBlend", pc,
                  inputs=[obj_pin("NewViewTarget", ACTOR), Pin("BlendTime", FLOAT, default="0.0"),
                          native_enum_pin("BlendFunc", "/Script/Engine.EViewTargetBlendFunction", "VTBlend_Linear"),
                          Pin("BlendExp", FLOAT, default="0.0"), Pin("bLockOutgoing", BOOL, default="false")])
    t.link(car, back, "NewViewTarget")
    t.delay(1.5)
    t.call(VC, "ActivateBoost", car)
    t.delay(0.4)
    shot()
    t.call(GMC, "RestartRace", gm)


def snap(t: T, name, label="COMBAT SHOT"):
    t.step(log_line(t.g, "%s %s" % (label, name)))
    t.static("KismetSystemLibrary", "ExecuteConsoleCommand",
             inputs=[Pin("WorldContextObject", OBJECT, hidden=True), Pin("Command", STRING, default="shot"),
                     obj_pin("SpecificPlayer", "/Script/Engine.PlayerController")])


def combat_capture():
    t = T("FT_DFShot_Combat", "Phase 7 Task 16 capture: the car's gun shot (muzzle flash and tracer from the roof gun), a rocket in "
                              "flight (flame and smoke trail), an explosion and the scorch it leaves (placed in L_DF_FunctionalTests "
                              "for a capture run only).")
    ev = bind_cleanup(t, "RestoreTimeDilation")
    t.g.link(ev, "then", t.g.call_static(GAMEPLAY, "SetGlobalTimeDilation", inputs=[Pin("WorldContextObject", OBJECT, hidden=True),
                                                                                       Pin("TimeDilation", FLOAT, default="1.0")]), "execute")
    pc = t.player()
    gm = t.game_mode()
    t.call(GMC, "RestartRace", gm)
    t.delay(0.5)
    car = pawn_car(t, pc)
    grant(t, gm, pc, ITEM_GUN, 8)
    # the gun: the muzzle flash on the roof gun and the tracer down the road
    cam = view_from(t, t.offset(t.loc(car), -250.0, -650.0, 260.0), t.offset(t.loc(car), 600.0, 0.0, 160.0))
    t.delay(3.0)  # exposure and the sky capture settle
    dilate(t, 0.02)
    t.call(VC, "FireGun", car, outputs=[Pin("ReturnValue", BOOL, "out")])
    t.delay(0.03)
    snap(t, COMBAT_SHOTS[0])
    dilate(t, 1.0)
    t.delay(1.0)
    t.call(ACTOR, "K2_DestroyActor", cam)
    # the rocket about 7 m past the muzzle, from 5 m: its body, its flame and the first puffs of its trail (time almost stopped, so
    # a 60 m/s rocket is not smeared by motion blur)
    grant(t, gm, pc, ITEM_RPG, 1)
    cam = view_from(t, t.offset(t.loc(car), 850.0, -500.0, 170.0), t.offset(t.loc(car), 1000.0, 0.0, 100.0))
    t.delay(1.0)
    dilate(t, 0.01)
    t.call(VC, "FireRPG", car, outputs=[obj_pin("Projectile", PROJC, "out")])
    t.delay(0.12)
    snap(t, COMBAT_SHOTS[1])
    dilate(t, 1.0)
    t.delay(4.5)  # the rocket lands far down the road (or its 4 s life ends)
    t.call(ACTOR, "K2_DestroyActor", cam)
    # an effects-only explosion beside the start line at mid-life, from 26 m (beyond the heavy shake), then its scorch
    at = t.offset(t.loc(car), 1500.0, 1500.0, 0.0)
    cam = view_from(t, t.offset(at, -1900.0, -1700.0, 700.0), t.offset(at, 0.0, 0.0, 150.0))
    t.delay(1.0)
    dilate(t, 0.4)
    explode(t, gm, at, 0.0, 0.0, None, False)
    t.delay(0.6)
    snap(t, COMBAT_SHOTS[2])
    dilate(t, 1.0)
    t.delay(2.0)
    t.call(ACTOR, "K2_DestroyActor", cam)
    cam = view_from(t, t.offset(at, -650.0, -650.0, 450.0), at)
    t.delay(1.0)
    snap(t, COMBAT_SHOTS[3])
    t.delay(1.0)
    t.call(ACTOR, "K2_DestroyActor", cam)
    return t.finish()


# Task 16 fix round 1 (the scorch reads lighter than the ground): one scorch decal as SpawnExplosion spawns it (MI_DF_Scorch,
# df.SCORCH_SIZE, pitch -90), but without its 20 s fade so the evidence is at full opacity, on FX_SPOT: a clear patch of floor in
# the look-dev level and of the VehicleAdv ground in the functional-test level (30 m south of the road there). Photographed lit,
# then through the buffer visualisation (ShowFlag.VisualizeBuffer + r.BufferVisualizationTarget, put back on every finish).
# tools/capture_shots.py scorch-lookdev / scorch-test save art/lookdev/scorch-<level>-<n>-<view>.png.
SCORCH_VIEWS = ["lit", "BaseColor", "Specular", "Roughness", "Metallic"]


def console(t: T, command):
    t.static("KismetSystemLibrary", "ExecuteConsoleCommand",
             inputs=[Pin("WorldContextObject", OBJECT, hidden=True), Pin("Command", STRING, default=command),
                     obj_pin("SpecificPlayer", "/Script/Engine.PlayerController")])


def scorch_capture():
    t = T("FT_DFShot_Scorch", "Phase 7 Task 16 fix round 1 capture: one scorch decal (as SpawnExplosion spawns it, unfaded) on a clear "
                              "patch of floor, lit and in the BaseColor, Specular, Roughness and Metallic buffers (placed in "
                              "L_DF_LookDev or L_DF_FunctionalTests for a capture run only).")
    ev = bind_cleanup(t, "RestoreView")
    put_back = t.g.call_static("KismetSystemLibrary", "ExecuteConsoleCommand",
                               inputs=[Pin("WorldContextObject", OBJECT, hidden=True), Pin("Command", STRING, default="ShowFlag.VisualizeBuffer 2"),
                                       obj_pin("SpecificPlayer", "/Script/Engine.PlayerController")])
    t.g.link(ev, "then", put_back, "execute")
    sx, sy, sz = FX_SPOT
    cam = view_from(t, literal_vec(t, sx, sy - 900.0, 520.0), literal_vec(t, sx, sy, 0.0))
    down = t.g.call_static(MATH, "MakeRotator", inputs=[Pin("Roll", FLOAT, default="0.0"), Pin("Pitch", FLOAT, default="-90.0"),
                                                        Pin("Yaw", FLOAT, default="0.0")],
                           outputs=[struct_pin("ReturnValue", ROTATOR, "out")], pure=True)
    decal = t.static(GAMEPLAY, "SpawnDecalAtLocation",
                     inputs=[Pin("WorldContextObject", OBJECT, hidden=True),
                             Pin("DecalMaterial", OBJECT, sub_object=cls_ref(MATERIAL_INTERFACE), default_object=asset_object(MI_SCORCH)),
                             struct_pin("DecalSize", VECTOR, default="%g,%g,%g" % SCORCH_SIZE), struct_pin("Location", VECTOR),
                             struct_pin("Rotation", ROTATOR), Pin("LifeSpan", FLOAT, default="0.0")],
                     outputs=[obj_pin("ReturnValue", DECAL_COMP, "out")])
    t.link(literal_vec(t, sx, sy, sz), decal, "Location")
    t.g.link(down, "ReturnValue", decal, "Rotation")
    t.delay(3.0)  # exposure and the sky capture settle
    snap(t, "scorch lit")
    t.delay(1.0)  # "shot" grabs a later frame: switch the view only after it is written
    for target in SCORCH_VIEWS[1:]:
        console(t, "r.BufferVisualizationTarget %s" % target)
        console(t, "ShowFlag.VisualizeBuffer 1")
        t.delay(1.0)
        snap(t, "scorch %s" % target)
        t.delay(1.0)
    console(t, "ShowFlag.VisualizeBuffer 2")
    t.call("/Script/Engine.ActorComponent", "K2_DestroyComponent", (decal, "ReturnValue"),
           inputs=[obj_pin("Object", "/Script/CoreUObject.Object", hidden=True)])
    t.call(ACTOR, "K2_DestroyActor", cam)
    return t.finish()


# Phase 7 Task 21 (spec §8.2): the track dressing in L_DF_FunctionalTests after a restart (the player's next gate is 1): gate 1 lit and
# gate 2 dim, each from 30 m down the road at a driver's eye height, then the level's rock wall from 28 m (beyond the heavy shake's
# 25 m), whole, 0.4 s after Demolish (the chunks flying) and 3 s after (the chunks down). tools/capture_shots.py track saves
# art/lookdev/track-<n>-<name>.png.
TRACK_SHOTS = ["gate-next", "gate-dim", "rock", "rock-broken", "rock-settled"]


def track_capture():
    cpc, destc = gen(BP_CHECKPOINT), gen(BP_DESTRUCTIBLE)
    t = T("FT_DFShot_Track", "Phase 7 Task 21 capture: the player's next gate lit and another dim, then the shortcut's rock wall whole, "
                             "breaking and broken (placed in L_DF_FunctionalTests for a capture run only).")
    gm = t.game_mode()
    t.call(GMC, "RestartRace", gm)
    t.delay(0.5)
    gates = t.get(GMC, "Checkpoints", OBJECT, gm, sub=cls_ref(cpc), container="Array")
    for index, name in ((1, TRACK_SHOTS[0]), (2, TRACK_SHOTS[1])):
        gate = t.item(gates, cpc, str(index))
        cam = view_from(t, along(t, t.loc(gate), gate, -3000.0, 0.0, 250.0), t.offset(t.loc(gate), 0.0, 0.0, 300.0))
        t.delay(3.0 if index == 1 else 1.5)  # the first waits for exposure and the sky capture
        snap(t, name)
        t.delay(1.0)
        t.call(ACTOR, "K2_DestroyActor", cam)
    rocks = t.step(get_all_actors_of_class(t.g, destc))
    rock = t.item((rocks, "OutActors"), destc)
    cam = view_from(t, along(t, t.loc(rock), rock, -2600.0, 900.0, 300.0), t.loc(rock))
    t.delay(1.5)
    snap(t, TRACK_SHOTS[2])
    t.delay(1.0)
    t.call(destc, "Demolish", rock)
    t.delay(0.4)
    snap(t, TRACK_SHOTS[3])
    t.delay(3.0)
    snap(t, TRACK_SHOTS[4])
    t.delay(1.0)
    t.call(ACTOR, "K2_DestroyActor", cam)
    t.call(GMC, "RestartRace", gm)
    return t.finish()


# Phase 7 Task 22 (spec §8.1, §8.3, §8.4): a shipped race level (L_TestTrack or L_Switchback, its landscape, scatter and dusk light) seen
# from the race. First the grid from 30 m ahead of the player's car (the navy car beside the black rivals), then, with the rivals gone,
# four fixed points along the main road at POINT_FRACTIONS of its length: a camera POINT_BACK_CM behind the centre line and
# POINT_UP_CM up, looking POINT_AHEAD_CM down the road. Then the item looks on this ground (item_look_shots: a crate from the road and
# close up, a bomb, the shield, the boost), and the player on foot beside the car. Plain "shot" (scene only, no window frame).
# tools/capture_shots.py points-proving / points-switchback save art/lookdev/points-<track>-<nn>-<name>.png.
POINT_FRACTIONS = (0.1, 0.35, 0.6, 0.85)  # of the main road from the start line: between the gates on both tracks
POINT_BACK_CM, POINT_UP_CM, POINT_AHEAD_CM, POINT_AIM_UP_CM = 1000.0, 350.0, 3000.0, 100.0
GRID_AHEAD_CM, GRID_UP_CM = 3000.0, 300.0
POINTS_SHOTS = ["grid"] + ["point-%d" % (i + 1) for i in range(len(POINT_FRACTIONS))] + ITEM_SHOTS + ["on-foot"]
POINTS_TIME_LIMIT = 120.0  # s; about 45 s of shots and waits, past AFunctionalTest's default 60 s with margin


def plus(t: T, a, b):
    n = t.g.call_static(MATH, "Add_VectorVector", inputs=[struct_pin("A", VECTOR), struct_pin("B", VECTOR)],
                        outputs=[struct_pin("ReturnValue", VECTOR, "out")], pure=True)
    t.link(a, n, "A")
    t.link(b, n, "B")
    return (n, "ReturnValue")


def scaled(t: T, v, k):
    n = t.g.call_static(MATH, "Multiply_VectorFloat", inputs=[struct_pin("A", VECTOR), Pin("B", FLOAT, default="%f" % k)],
                        outputs=[struct_pin("ReturnValue", VECTOR, "out")], pure=True)
    t.link(v, n, "A")
    return (n, "ReturnValue")


def road_point(t: T, track, length, fraction):
    """The main road's centre line and its direction (world) at `fraction` of its length (pure)."""
    d = t.g.call_static(MATH, "Multiply_FloatFloat", inputs=[Pin("A", FLOAT), Pin("B", FLOAT, default="%f" % fraction)],
                        outputs=[Pin("ReturnValue", FLOAT, "out")], pure=True)
    t.link(length, d, "A")
    xf = t.call(TC, "GetTransformAtDistance", track, inputs=[Pin("Distance", FLOAT)], outputs=[struct_pin("Transform", TRANSFORM, "out")], pure=True)
    t.g.link(d, "ReturnValue", xf, "Distance")
    ahead = t.call(TC, "GetDirectionAtDistance", track, inputs=[Pin("Distance", FLOAT)], outputs=[struct_pin("Direction", VECTOR, "out")], pure=True)
    t.g.link(d, "ReturnValue", ahead, "Distance")
    return t.transform_loc((xf, "Transform")), (ahead, "Direction")


def points_capture():
    t = T("FT_DFShot_Points", "Phase 7 Task 22 capture: a shipped race level from the race: the grid, four fixed points along the main "
                              "road, the item looks on its ground and the player on foot (placed in L_TestTrack or L_Switchback for a "
                              "capture run only).")
    t.bp.default("TimeLimit", POINTS_TIME_LIMIT)
    fresh_slot(t)
    pc = t.player()
    gm = t.game_mode()
    t.delay(2.5)  # exposure and the sky capture settle; the rivals are still round the grid
    car = pawn_car(t, pc)
    cam = view_from(t, along(t, t.loc(car), car, GRID_AHEAD_CM, 0.0, GRID_UP_CM), t.offset(t.loc(car), 0.0, 0.0, 80.0))
    t.delay(0.3)
    snap(t, POINTS_SHOTS[0], "POINTS SHOT")
    t.delay(1.0)
    t.call(ACTOR, "K2_DestroyActor", cam)
    t.call(GMC, "DespawnNPCs", gm)  # the fixed points show the level alone (item_look_shots' restart brings the rivals back)
    track = t.get(GMC, "MainTrack", OBJECT, gm, sub=cls_ref(TC))
    length = t.call(TC, "GetTrackLength", track, outputs=[Pin("Length", FLOAT, "out")], pure=True)
    for i, fraction in enumerate(POINT_FRACTIONS):
        at, ahead = road_point(t, track, (length, "Length"), fraction)
        cam = view_from(t, t.offset(plus(t, at, scaled(t, ahead, -POINT_BACK_CM)), 0.0, 0.0, POINT_UP_CM),
                        t.offset(plus(t, at, scaled(t, ahead, POINT_AHEAD_CM)), 0.0, 0.0, POINT_AIM_UP_CM))
        t.delay(1.5)
        snap(t, POINTS_SHOTS[1 + i], "POINTS SHOT")
        t.delay(1.0)
        t.call(ACTOR, "K2_DestroyActor", cam)
    item_look_shots(t, pc, gm, lambda: shot(t, 0.1, "shot"))  # ends with RestartRace: the player is back in the car on the line
    t.delay(0.5)
    t.call(VC, "ExitVehicle", pawn_car(t, pc), outputs=[Pin("ReturnValue", BOOL, "out")])
    t.delay(1.0)
    me = t.g.call_on(CONTROLLER, "K2_GetPawn", outputs=[obj_pin("ReturnValue", PAWN, "out")], pure=True)
    t.link(pc, me, "self")
    cam = view_from(t, along(t, t.loc((me, "ReturnValue")), (me, "ReturnValue"), 300.0, -120.0, 40.0),
                    t.offset(t.loc((me, "ReturnValue")), 0.0, 0.0, 10.0))
    t.delay(1.5)
    snap(t, POINTS_SHOTS[-1], "POINTS SHOT")
    t.delay(1.0)
    t.call(ACTOR, "K2_DestroyActor", cam)
    delete_slot(t, SLOT)
    return t.finish()


# Phase 7 Task 24: the deck's race images (tools/capture_shots.py race: 20-23, 26-30) on a shipped level's terrain under its dusk
# light. FT_DFZZ_Screenshots (tests.py screenshot_test) takes the same shots in the functional-test level, whose flat ground is not
# the game's; this capture runs them in L_TestTrack with its own three rivals (no SpawnNPCs) and on the DeadFireShots slot, so the
# summary's unlock line comes from fresh progress and the developer's save is neither read nor written. "shot showui": the HUD shows.
RACE_TIME_LIMIT = 90.0  # s; about 40 s of shots and waits, past AFunctionalTest's default 60 s with margin


def race_capture():
    from df import ITEM_BOMB, ITEM_SHIELD, enum_pin
    from tests import PCC, RC
    t = T("FT_DFShot_Race", "Phase 7 Task 24 presentation capture: the race HUD on the grid, the rivals ahead, the player on foot, the "
                            "summary with its unlock line and the item looks, on a shipped level's terrain (placed in L_TestTrack "
                            "for a capture run only).")
    t.bp.default("TimeLimit", RACE_TIME_LIMIT)
    fresh_slot(t)
    pc = t.player()
    gm = t.game_mode()
    t.call(GMC, "RestartRace", gm)  # the grid again: the level's rivals behind the player's car, a full clock
    t.delay(0.5)
    racer = t.racer(gm, pc)
    for item in (ITEM_SHIELD, ITEM_BOMB):  # two items, so the HUD's item row shows
        grant(t, gm, pc, item)
    shot(t, 1.0)  # 20: the grid, POS 1 / 4, the item row
    shot(t, 4.0)  # 21: the rivals driving past into the chase camera's view
    car = t.get(PCC, "CurrentVehicle", OBJECT, pc, sub=cls_ref(VC))
    t.call(VC, "ExitVehicle", car, outputs=[Pin("ReturnValue", BOOL, "out")])
    shot(t, 1.0)  # 22: on foot beside the car
    t.set(RC, "Score", INT, racer, default="350")
    t.call(GMC, "EndRace", gm, inputs=[enum_pin("Reason", "/Game/DeadFire/Data/E_DFRaceEndReason", default=1)])
    shot(t, 0.5)  # 23: a passed race in first place on fresh progress: the unlock line and NEXT
    t.call(GMC, "RestartRace", gm)  # the player back in the car on the line
    t.delay(0.5)
    t.call(GMC, "DespawnNPCs", gm)  # the item looks show the item alone (item_look_shots' restart brings the rivals back)
    item_look_shots(t, pc, gm, lambda: shot(t))  # 26-30
    delete_slot(t, SLOT)
    return t.finish()


# Phase 7 Task 24: the deck's "track from above" image (tools/capture_shots.py switchback-top: 31). A camera straight above the centre
# of the main road's bounds, its image's long side along the bounds' long side, high enough that the road fills about 1 / TOP_MARGIN
# of the frame. The lens is TOP_FOV degrees across the 16:9 view, so a height h shows h x tan(TOP_FOV / 2) to each side and 9/16 of
# that up and down. The rotation is made directly (pitch -90; yaw 90 puts world +Y at the image's top, so X runs across; yaw 0
# puts X at the top): FindLookAtRotation goes through FRotationMatrix::MakeFromX, which takes world X as its up reference for any
# direction within about 0.8 degrees of vertical, so a look-at from straight above always comes out with X at the top. Plain
# "shot": no HUD.
TOP_FOV = 70.0
TOP_MARGIN = 1.15


def top_capture():
    t = T("FT_DFShot_Top", "Phase 7 Task 24 presentation capture: a shipped track from straight above, framed on its main road's "
                           "bounds (placed in L_Switchback or L_TestTrack for a capture run only).")
    fresh_slot(t)
    gm = t.game_mode()
    t.delay(2.0)  # exposure and the sky capture settle
    track = t.get(GMC, "MainTrack", OBJECT, gm, sub=cls_ref(TC))
    bounds = t.g.call_on(ACTOR, "GetActorBounds", inputs=[Pin("bOnlyCollidingComponents", BOOL, default="false"),
                                                          Pin("bIncludeFromChildActors", BOOL, default="false")],
                         outputs=[struct_pin("Origin", VECTOR, "out"), struct_pin("BoxExtent", VECTOR, "out")], pure=True)
    t.link(track, bounds, "self")
    ext = t.g.call_static(MATH, "BreakVector", inputs=[struct_pin("InVec", VECTOR)],
                          outputs=[Pin("X", FLOAT, "out"), Pin("Y", FLOAT, "out"), Pin("Z", FLOAT, "out")], pure=True)
    t.g.link(bounds, "BoxExtent", ext, "InVec")

    def two(fn, a, b, out=FLOAT, pin_type=FLOAT):
        n = t.g.call_static(MATH, fn, inputs=[Pin("A", pin_type), Pin("B", pin_type)], outputs=[Pin("ReturnValue", out, "out")], pure=True)
        t.link(a, n, "A")
        t.link(b, n, "B")
        return (n, "ReturnValue")

    def times(a, k):
        n = t.g.call_static(MATH, "Multiply_FloatFloat", inputs=[Pin("A", FLOAT), Pin("B", FLOAT, default="%f" % k)],
                            outputs=[Pin("ReturnValue", FLOAT, "out")], pure=True)
        t.link(a, n, "A")
        return (n, "ReturnValue")

    half_across = math.tan(math.radians(TOP_FOV / 2.0))
    x, y = (ext, "X"), (ext, "Y")
    height = two("FMax", times(two("FMax", x, y), TOP_MARGIN / half_across),
                 times(two("FMin", x, y), TOP_MARGIN / (half_across * 9.0 / 16.0)))
    rise = t.g.call_static(MATH, "MakeVector", inputs=[Pin("X", FLOAT, default="0.0"), Pin("Y", FLOAT, default="0.0"), Pin("Z", FLOAT)],
                           outputs=[struct_pin("ReturnValue", VECTOR, "out")], pure=True)
    t.link(height, rise, "Z")
    cam_at = plus(t, (bounds, "Origin"), (rise, "ReturnValue"))
    # the image's long side along the bounds' long side
    yaw = t.g.call_static(MATH, "SelectFloat", inputs=[Pin("A", FLOAT, default="90.0"), Pin("B", FLOAT, default="0.0"), Pin("bPickA", BOOL)],
                          outputs=[Pin("ReturnValue", FLOAT, "out")], pure=True)
    t.link(two("GreaterEqual_FloatFloat", x, y, out=BOOL), yaw, "bPickA")
    down = t.g.call_static(MATH, "MakeRotator", inputs=[Pin("Roll", FLOAT, default="0.0"), Pin("Pitch", FLOAT, default="-90.0"), Pin("Yaw", FLOAT)],
                           outputs=[struct_pin("ReturnValue", ROTATOR, "out")], pure=True)
    t.link((yaw, "ReturnValue"), down, "Yaw")
    as_text = []
    for fn, pin, src in (("Conv_VectorToString", "InVec", (bounds, "Origin")), ("Conv_VectorToString", "InVec", (bounds, "BoxExtent")),
                         ("Conv_FloatToString", "InFloat", height), ("Conv_FloatToString", "InFloat", (yaw, "ReturnValue"))):
        n = t.g.call_static("KismetStringLibrary", fn, inputs=[struct_pin(pin, VECTOR) if pin == "InVec" else Pin(pin, FLOAT)],
                            outputs=[Pin("ReturnValue", STRING, "out")], pure=True)
        t.link(src, n, pin)
        as_text.append((n, "ReturnValue"))
    t.step(log_line(t.g, "TOP SHOT track origin ", as_text[0], " extent ", as_text[1], " camera height ", as_text[2], " yaw ", as_text[3]))
    cam = view_at(t, cam_at, (down, "ReturnValue"), TOP_FOV)
    shot(t, 2.0, "shot")  # exposure settles on the new view first
    t.call(ACTOR, "K2_DestroyActor", cam)
    delete_slot(t, SLOT)
    return t.finish()


# Phase 7 Task 24 fix round 1 (spec §12 "a drift"): the player's car mid-drift on PROVING GROUND with its tyre smoke
# (tools/capture_shots.py drift: 34-drift-chase, 35-drift). The car is driven the way the Task 9 drift tests drive one
# (tests_drive: set_speed puts it at DRIFT_KPH along its own forward vector in the matching gear, then SetAIInput gives full
# lock with the handbrake), through the AI input path: bAIControlled is set on the player's own car for the shot (only the AI
# controller's possess / unpossess write it otherwise) and cleared after. Steering left follows PROVING GROUND's first bend.
# After DRIFT_SECONDS the world is slowed to DRIFT_FREEZE, so the two images show the same moment: the chase camera with the
# HUD ("shot showui"), then a camera ahead of the car on the outside of the turn, looking back at it (plain "shot").
# The rivals are despawned so none drives into the shot; RestartRace at the end brings them back.
DRIFT_KPH = 80.0
DRIFT_STEER = -1.0          # full left lock
DRIFT_SECONDS = 0.7         # of drifting before the shots (tyre smoke every 0.08 s from each rear wheel)
DRIFT_FREEZE = 0.02         # global time dilation for the shots: a delay of 0.02 s game time is 1 s of real time
DRIFT_CAM_AHEAD, DRIFT_CAM_SIDE, DRIFT_CAM_UP = 1000.0, 500.0, 200.0  # cm, along the car's travel, to its right, up


def drift_capture():
    from tests_drive import set_input, set_speed, time_dilation
    t = T("FT_DFShot_Drift", "Phase 7 Task 24 presentation capture: the player's car mid-drift with its tyre smoke, from the chase "
                             "camera and from beside the road (placed in L_TestTrack for a capture run only).")
    ev = bind_cleanup(t, "RestoreTimeDilation")
    t.g.link(ev, "then", t.g.call_static(GAMEPLAY, "SetGlobalTimeDilation", inputs=[Pin("WorldContextObject", OBJECT, hidden=True),
                                                                                       Pin("TimeDilation", FLOAT, default="1.0")]), "execute")
    fresh_slot(t)
    pc = t.player()
    gm = t.game_mode()
    t.call(GMC, "RestartRace", gm)  # the player's car on the start line
    t.delay(0.5)
    t.call(GMC, "DespawnNPCs", gm)
    t.delay(1.0)  # the car settles; exposure and the sky capture settle
    car = pawn_car(t, pc)
    t.set(VC, "bAIControlled", BOOL, car, default="true")
    set_input(t, car, 0.0, 0.0, False)
    set_speed(t, car, DRIFT_KPH)
    t.delay(0.3)
    set_input(t, car, 0.0, DRIFT_STEER, True)
    t.delay(DRIFT_SECONDS)
    time_dilation(t, DRIFT_FREEZE)
    speed = t.g.call_on(VC, "GetSpeedKPH", outputs=[Pin("KPH", FLOAT, "out")], pure=True)
    t.link(car, speed, "self")
    as_text = []
    for fn, pin, src, cat in (("Conv_BoolToString", "InBool", t.get(VC, "bDrifting", BOOL, car), BOOL),
                              ("Conv_FloatToString", "InFloat", (speed, "KPH"), FLOAT)):
        n = t.g.call_static("KismetStringLibrary", fn, inputs=[Pin(pin, cat)], outputs=[Pin("ReturnValue", STRING, "out")], pure=True)
        t.link(src, n, pin)
        as_text.append((n, "ReturnValue"))
    t.step(log_line(t.g, "DRIFT SHOT drifting ", as_text[0], " kph ", as_text[1]))

    def frozen_shot(settle, command):
        """shot() with delays in frozen game time (shot()'s own 1 s wait would be 50 s of real time now)."""
        t.delay(settle)
        t.static("KismetSystemLibrary", "ExecuteConsoleCommand",
                 inputs=[Pin("WorldContextObject", OBJECT, hidden=True), Pin("Command", STRING, default=command),
                         obj_pin("SpecificPlayer", "/Script/Engine.PlayerController")])
        t.delay(0.02)

    frozen_shot(0.02, "shot showui")  # 34: the chase camera with the HUD (0.02 s of game time is 1 s of real time now)
    # beside the road: DRIFT_CAM_AHEAD along the car's travel and DRIFT_CAM_SIDE to its right (the outside of a left turn)
    vel = t.g.call_on(ACTOR, "GetVelocity", outputs=[struct_pin("ReturnValue", VECTOR, "out")], pure=True)
    t.link(car, vel, "self")
    travel = t.g.call_static(MATH, "Normal", inputs=[struct_pin("A", VECTOR), Pin("Tolerance", FLOAT, default="0.0001")],
                             outputs=[struct_pin("ReturnValue", VECTOR, "out")], pure=True)
    t.g.link(vel, "ReturnValue", travel, "A")
    right = t.g.call_static(MATH, "Cross_VectorVector", inputs=[struct_pin("A", VECTOR), struct_pin("B", VECTOR)],
                            outputs=[struct_pin("ReturnValue", VECTOR, "out")], pure=True)
    t.link(literal_vec(t, 0.0, 0.0, 1.0), right, "A")  # up x travel = the travel's right
    t.g.link(travel, "ReturnValue", right, "B")
    cam_at = t.offset(plus(t, plus(t, t.loc(car), scaled(t, (travel, "ReturnValue"), DRIFT_CAM_AHEAD)),
                           scaled(t, (right, "ReturnValue"), DRIFT_CAM_SIDE)), 0.0, 0.0, DRIFT_CAM_UP)
    cam = view_from(t, cam_at, t.offset(t.loc(car), 0.0, 0.0, 40.0))
    frozen_shot(0.03, "shot")  # 35: the drift and its smoke from beside the road
    t.call(ACTOR, "K2_DestroyActor", cam)
    time_dilation(t, 1.0)
    set_input(t, car, 0.0, 0.0, False)
    t.set(VC, "bAIControlled", BOOL, car, default="false")
    t.call(GMC, "RestartRace", gm)
    delete_slot(t, SLOT)
    return t.finish()


def build():
    out = []

    t = T("FT_DFShot_Menu", "Presentation captures of the menu pages (placed in L_MainMenu for a capture run only).")
    fresh_slot(t)
    pc = menu_pc(t)
    show_page(t, pc, WBP_MAIN_MENU)  # again, so the footer counts the fresh slot
    shot(t, 1.5)
    show_page(t, pc, WBP_VEHICLE_SELECT)
    shot(t, 1.5)
    t.call(gen(WBP_VEHICLE_SELECT), "SelectNext", current_page(t, pc, WBP_VEHICLE_SELECT))
    shot(t, 1.5)  # BRUTE, locked; the camera has moved to its plinth
    show_page(t, pc, WBP_LEVEL_SELECT)
    shot(t, 1.0)
    t.call(gen(WBP_LEVEL_SELECT), "SelectNext", current_page(t, pc, WBP_LEVEL_SELECT))
    shot(t, 1.0)  # SWITCHBACK, locked
    show_page(t, pc, WBP_SETTINGS)
    shot(t, 1.0)
    show_page(t, pc, WBP_MAIN_MENU)
    delete_slot(t, SLOT)
    out.append(t.finish())

    t = T("FT_DFShot_Pause", "Presentation capture of the pause menu over a race (placed in L_TestTrack for a capture run only).")
    fresh_slot(t)
    t.delay(6.0)  # the three rivals pull away from the grid behind the parked player
    shot(t, 0.5)
    pw = t.step(t.g.create_widget(gen(WBP_PAUSE), result_class=gen(WBP_PAUSE)))
    t.g.link(get_player_controller(t.g), "ReturnValue", pw, "OwningPlayer")
    t.call(USER_WIDGET, "AddToViewport", (pw, "ReturnValue"), inputs=[Pin("ZOrder", INT, default="20")])
    shot(t, 0.5)  # the widget over a running world: a still looks the same as a paused one, and a paused world stalls every delay
    t.call("/Script/UMG.Widget", "RemoveFromParent", (pw, "ReturnValue"))
    delete_slot(t, SLOT)
    out.append(t.finish())

    t = T("FT_DFShot_LookDev", "Presentation capture of the art look-dev level: one image per LookDevShot camera (placed in "
                               "L_DF_LookDev for a capture run only).")
    t.bp.default("TimeLimit", LOOKDEV_TIME_LIMIT)
    skipped = None
    for k in range(LOOKDEV_SHOTS):
        get, branch = lookdev_shot(t, "LookDevShot%02d" % k, 3.0 if k == 0 else 1.0)  # the first waits for exposure and the sky capture
        if skipped is not None:
            t.g.link(skipped, "else", get, "execute")
        skipped = branch
    join = t.static("KismetSystemLibrary", "Delay", inputs=[Pin("WorldContextObject", OBJECT, hidden=True), Pin("Duration", FLOAT, default="0.2")])
    t.g.link(skipped, "else", join, "execute")
    out.append(t.finish())

    t = T("FT_DFShot_Fx", "Phase 7 Task 15 capture: each BP_DFFx effect at mid-life on the look-dev floor, the LootBurst tinted with the "
                          "random crate's colour (placed in L_DF_LookDev for a capture run only).")
    ev = bind_cleanup(t, "RestoreTimeDilation")
    t.g.link(ev, "then", t.g.call_static(GAMEPLAY, "SetGlobalTimeDilation", inputs=[Pin("WorldContextObject", OBJECT, hidden=True),
                                                                                       Pin("TimeDilation", FLOAT, default="1.0")]), "execute")
    for i, (name, asset, life, offset, rot, distance, height, aim_z) in enumerate(FX_SHOTS):
        fx_shot(t, name, asset, life, offset, rot, distance, height, aim_z, 3.0 if i == 0 else 1.0)  # the first waits for exposure
    out.append(t.finish())
    out.append(combat_capture())
    out.append(scorch_capture())
    out.append(track_capture())
    out.append(points_capture())
    out.append(race_capture())
    out.append(top_capture())
    out.append(drift_capture())
    return out


if __name__ == "__main__":
    for b in build():
        print(b.write(OUT))
