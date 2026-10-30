"""Phase 4 FT_DFAI_* tests (plan docs/superpowers/plans/2026-10-30-phase4-ai.md): NPC spawning and ranking, the vehicle's AI
inputs, driving maths, avoidance, respawn for every racer, item supply and use. Same shape as tests_items.py; the helpers
come from tests.py and tests_items.py. Every test starts from race_context (RestartRace despawns NPCs) and despawns what
it spawned.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, ".."))
from bpgen import cls_ref, struct_ref  # noqa: E402
from df import (ACTOR, BOOL, BP_AI, BP_BOMB, BP_CHARACTER, BP_CHECKPOINT, BP_GM, BP_GS, BP_PC, BP_PROJECTILE, BP_TRACK, BP_VEHICLE,  # noqa: E402
                BPC_RACER, CONTROLLER, E_END_REASON, FLOAT, INT, ITEM_BOMB, ITEM_BOOST, ITEM_GUN, ITEM_RPG, ITEM_SHIELD, MATH, OBJECT,
                OUT, PAWN, ROTATOR, STRING, TRANSFORM, VECTOR, WBP_HUD, Pin, as_pin, enum_pin, gen, get_all_actors_of_class, obj_pin,
                struct_pin)
from tests import T, race_context, spawn_vehicle  # noqa: E402
from tests_items import (TEXT_BLOCK, count_actors, destroy, grant, greater, inventory_length, move_to, park_player, pawn_car,  # noqa: E402
                         selected, text_reads, widgets)

AIC, GMC, GSC, VC, RC, TC, WHUD = gen(BP_AI), gen(BP_GM), gen(BP_GS), gen(BP_VEHICLE), gen(BPC_RACER), gen(BP_TRACK), gen(WBP_HUD)
CC, PCC, CPC = gen(BP_CHARACTER), gen(BP_PC), gen(BP_CHECKPOINT)


# ---- helpers ----
def ai_controllers(t: T):
    n = t.step(get_all_actors_of_class(t.g, AIC))
    return (n, "OutActors")


def ai_count(t: T):
    return t.length(ai_controllers(t), AIC)


def ai_racer(t: T, gm, ai):
    n = t.g.call_on(GMC, "FindRacer", inputs=[obj_pin("C", CONTROLLER)], outputs=[obj_pin("Racer", RC, "out")], pure=True)
    t.link(gm, n, "self")
    t.link(ai, n, "C")
    return (n, "Racer")


def pawn_of(t: T, controller):
    n = t.g.call_on(CONTROLLER, "K2_GetPawn", outputs=[obj_pin("ReturnValue", PAWN, "out")], pure=True)
    t.link(controller, n, "self")
    return (n, "ReturnValue")


def ai_car(t: T, ai):
    """The controller's pawn cast to BP_DFVehicle (stepped: a failed cast ends the chain and the test times out)."""
    c = t.step(t.g.cast(VC))
    t.link(pawn_of(t, ai), c, "Object")
    return (c, as_pin(BP_VEHICLE))


def spawn_npcs(t: T, gm, count):
    t.call(GMC, "SpawnNPCs", gm, inputs=[Pin("Count", INT, default=str(count))])


def despawn_npcs(t: T, gm):
    t.call(GMC, "DespawnNPCs", gm)


def on_any_track(t: T, gm, loc):
    n = t.call(GMC, "IsOnAnyTrack", gm, inputs=[struct_pin("Location", VECTOR)], outputs=[Pin("ReturnValue", BOOL, "out")])
    t.link(loc, n, "Location")
    return (n, "ReturnValue")


def text_equals(t: T, text_src, expected, message):
    s = t.g.call_static("KismetTextLibrary", "Conv_TextToString", inputs=[Pin("InText", "text")], outputs=[Pin("ReturnValue", STRING, "out")], pure=True)
    t.link(text_src, s, "InText")
    eq = t.g.call_static("KismetStringLibrary", "EqualEqual_StrStr", inputs=[Pin("A", STRING), Pin("B", STRING, default=expected)],
                         outputs=[Pin("ReturnValue", BOOL, "out")], pure=True)
    t.g.link(s, "ReturnValue", eq, "A")
    t.true((eq, "ReturnValue"), message)


def hud_position_reads(t: T, expected):
    huds = widgets(t, WHUD)
    hud = t.item(huds, WHUD)
    text_reads(t, t.get(WHUD, "PositionText", OBJECT, hud, sub=cls_ref(TEXT_BLOCK)), expected, "HUD position line reads %s" % expected)


def possess(t: T, controller, pawn):
    n = t.call(CONTROLLER, "Possess", controller, inputs=[obj_pin("InPawn", PAWN)])
    t.link(pawn, n, "InPawn")


# ---- Task 2: spawning, registration, ranking, HUD position, AI inputs ----
def spawn_and_rank_tests():
    out = []
    t = T("FT_DFAI_SpawnGridAndRanking", "Three NPCs spawn on a track with racers named NPC 1..3; ranks and the HUD position follow "
          "their scores; despawn removes them; no main track means no NPCs.")
    pc, gm, gs, racer, gates = race_context(t)
    spawn_npcs(t, gm, 3)
    ais = ai_controllers(t)
    t.eq_int(t.length(ais, AIC), 3, "three NPC controllers")
    ai0 = t.item(ais, AIC, "0")
    car0 = ai_car(t, ai0)
    t.false(t.get(VC, "bIsDestroyed", BOOL, car0), "NPC 1's car is intact")
    t.true(on_any_track(t, gm, t.loc(car0)), "NPC 1 spawned on a track")
    text_equals(t, t.get(RC, "RacerName", "text", ai_racer(t, gm, ai0)), "NPC 1", "first NPC is named NPC 1")
    ranked = t.call(GMC, "GetRankedRacers", gm, outputs=[Pin("Racers", OBJECT, "out", cls_ref(RC), container="Array")])
    t.eq_int(t.length((ranked, "Racers"), RC), 4, "four racers ranked")
    t.set(RC, "Score", INT, ai_racer(t, gm, ai0), default="200")
    t.set(RC, "Score", INT, racer, default="100")  # ahead of the other NPCs whatever their track distance says
    t.call(GMC, "UpdateRanks", gm)
    t.eq_int(t.get(RC, "Rank", INT, racer), 2, "player ranked second behind NPC 1")
    t.eq_int(t.get(GSC, "RacerCount", INT, gs), 4, "racer count on the game state")
    t.delay(0.5)
    hud_position_reads(t, "POS 2 / 4")
    despawn_npcs(t, gm)
    t.eq_int(ai_count(t), 0, "no NPC controllers after despawn")
    t.call(GMC, "UpdateRanks", gm)
    t.eq_int(t.get(GSC, "RacerCount", INT, gs), 1, "racer count back to one")
    t.set(GMC, "MainTrack", OBJECT, gm, sub=cls_ref(TC))  # no main track
    spawn_npcs(t, gm, 1)
    t.eq_int(ai_count(t), 0, "no NPC without a main track")
    t.call(GMC, "CollectLevelActors", gm)
    t.valid(t.get(GMC, "MainTrack", OBJECT, gm, sub=cls_ref(TC)), "main track restored")
    out.append(t.finish())

    t = T("FT_DFAI_StartGridRanksBehindThePole", "With every score 0, NPCs parked on the grid before the start line rank behind "
          "the player on the line: the player is first and the HUD reads POS 1 / 4.")
    pc, gm, gs, racer, gates = race_context(t)
    spawn_npcs(t, gm, 3)
    ais = ai_controllers(t)
    for i in range(3):
        t.set(AIC, "bAutoDrive", BOOL, t.item(ais, AIC, str(i)), default="false")  # hold the grid where it spawned
    t.delay(1.5)  # a few ticks: every racer's DistanceAlongTrack is measured and the rank timer has run
    t.call(GMC, "UpdateRanks", gm)
    t.eq_int(t.get(RC, "Score", INT, racer), 0, "every score is 0")
    t.eq_int(t.get(RC, "Rank", INT, racer), 1, "the player on the line is first")
    hud_position_reads(t, "POS 1 / 4")
    despawn_npcs(t, gm)
    out.append(t.finish())

    t = T("FT_DFAI_SkippedGateRanksBehindTheGrid", "Ranking counts progress through the gates, not raw spline distance: a racer "
          "teleported past gate 1 without crossing it (still waiting for gate 1) ranks behind an NPC still on the grid.")
    pc, gm, gs, racer, gates = race_context(t)
    TC_ = gen(BP_TRACK)
    mt = t.get(GMC, "MainTrack", OBJECT, gm, sub=cls_ref(TC_))
    length = t.g.call_on(TC_, "GetTrackLength", outputs=[Pin("Length", FLOAT, "out")], pure=True)
    t.link(mt, length, "self")
    frac = t.g.call_static(MATH, "Multiply_FloatFloat", inputs=[Pin("A", FLOAT), Pin("B", FLOAT, default="0.35")],
                           outputs=[Pin("ReturnValue", FLOAT, "out")], pure=True)
    t.g.link(length, "Length", frac, "A")
    xf = t.g.call_on(TC_, "GetTransformAtDistance", inputs=[Pin("Distance", FLOAT)], outputs=[struct_pin("Transform", TRANSFORM, "out")], pure=True)
    t.link(mt, xf, "self")
    t.g.link(frac, "ReturnValue", xf, "Distance")
    up = t.g.call_static(MATH, "Add_VectorVector", inputs=[struct_pin("A", VECTOR), struct_pin("B", VECTOR, default="0,0,60")],
                         outputs=[struct_pin("ReturnValue", VECTOR, "out")], pure=True)
    t.link(t.transform_loc((xf, "Transform")), up, "A")
    car = pawn_car(t, pc)
    teleport(t, car, (up, "ReturnValue"), car_rotation(t, car))  # 35 % of the lap: past gate 1 (25 %), before gate 2 (50 %)
    t.set(RC, "NextCheckpointIndex", INT, racer, default="1")
    spawn_npcs(t, gm, 1)
    ais = ai_controllers(t)
    t.set(AIC, "bAutoDrive", BOOL, t.item(ais, AIC, "0"), default="false")
    t.delay(1.5)
    t.call(GMC, "UpdateRanks", gm)
    t.eq_int(t.get(RC, "NextCheckpointIndex", INT, racer), 1, "gate 1 was not crossed")
    t.eq_int(t.get(RC, "Rank", INT, racer), 2, "a racer who skipped gate 1 ranks behind a racer still on the grid")
    despawn_npcs(t, gm)
    out.append(t.finish())

    t = T("FT_DFAI_StuckBudgetKeepsAcrossWedges", "UpdateStuck's give-up budget is cumulative: it does not drain while the car has "
          "not moved, and the give-up resets it and respawns the car at its gate.")
    pc, gm, gs, racer, gates = race_context(t)
    spawn_npcs(t, gm, 1)
    ais = ai_controllers(t)
    ai = t.item(ais, AIC, "0")
    t.set(AIC, "bAutoDrive", BOOL, ai, default="false")
    car = ai_car(t, ai)
    t.delay(1.0)

    def stuck(seconds):
        n = t.call(AIC, "UpdateStuck", ai, inputs=[obj_pin("Car", VC), Pin("DeltaSeconds", FLOAT, default="%f" % seconds)],
                   outputs=[Pin("bReversing", BOOL, "out")])
        t.link(car, n, "Car")
        return n

    def pushing(on):
        t.set(AIC, "Throttle", FLOAT, ai, default="1.0" if on else "0.0")
        t.set(AIC, "LastKPH", FLOAT, ai, default="0.0")

    pushing(True)
    stuck(2.0)
    t.eq_float(ai_get_float(t, ai, "StuckTotal"), 2.0, "two seconds wedged count")
    u2 = stuck(2.0)
    t.true((u2, "bReversing"), "after StuckSeconds the car backs out")
    t.call(VC, "SetAIInput", car, inputs=[Pin("Throttle", FLOAT, default="0.0"), Pin("Steering", FLOAT, default="0.0"), Pin("bHandbrake", BOOL, default="true")])
    pushing(False)
    t.delay(2.0)  # the reverse window (1.5 s) passes; the car is held
    stuck(3.0)
    t.eq_float(ai_get_float(t, ai, "StuckTotal"), 4.0, "the budget does not drain while the car has not moved")
    pushing(True)
    u4 = stuck(6.0)
    t.false((u4, "bReversing"), "ten seconds in all: the car gives up")
    t.eq_float(ai_get_float(t, ai, "StuckTotal"), 0.0, "the give-up resets the budget")
    t.less(t.distance(t.loc(car), gate_loc(t, t.item(gates, CPC, "0"))), 700.0, "back within 7 m of gate 0 (lane offset included)")
    despawn_npcs(t, gm)
    out.append(t.finish())

    t = T("FT_DFAI_RestartRespawnsNPCs", "A restart removes spawned NPCs and spawns NPCCount of them.")
    pc, gm, gs, racer, gates = race_context(t)
    spawn_npcs(t, gm, 2)
    t.call(GMC, "RestartRace", gm)
    t.delay(0.5)
    t.eq_int(ai_count(t), 0, "NPCCount 0: none after the restart")
    t.set(GMC, "NPCCount", INT, gm, default="2")
    t.call(GMC, "RestartRace", gm)
    t.delay(0.5)
    t.eq_int(ai_count(t), 2, "NPCCount 2: two after the restart")
    t.set(GMC, "NPCCount", INT, gm, default="0")
    t.call(GMC, "RestartRace", gm)
    t.delay(0.5)
    t.eq_int(ai_count(t), 0, "NPCCount 0 again: none")
    out.append(t.finish())

    t = T("FT_DFAI_VehicleTakesAIInput", "A possessed car applies the AI inputs each tick and parks when unpossessed; despawn clears a "
          "controller that has no car.")
    pc, gm, gs, racer, gates = race_context(t)
    spawn_npcs(t, gm, 1)
    t.delay(0.5)
    ai = t.item(ai_controllers(t), AIC, "0")
    car = ai_car(t, ai)
    t.true(t.get(VC, "bAIControlled", BOOL, car), "car under AI control after possession")
    t.same(t.get(VC, "LastDriver", OBJECT, car, sub=cls_ref(CONTROLLER)), ai, "the AI is the car's last driver")
    t.set(AIC, "bAutoDrive", BOOL, ai, default="false")  # the driver would overwrite the inputs below
    t.call(VC, "SetAIInput", car, inputs=[Pin("Throttle", FLOAT, default="1.0"), Pin("Steering", FLOAT, default="0.5"),
                                          Pin("bHandbrake", BOOL, default="false")])
    t.delay(1.5)
    t.eq_float(t.get(VC, "AIThrottle", FLOAT, car), 1.0, "stored AI throttle")
    t.eq_float(t.get(VC, "AISteering", FLOAT, car), 0.5, "stored AI steering")
    sp = t.g.call_on(VC, "GetSpeedKPH", outputs=[Pin("KPH", FLOAT, "out")], pure=True)
    t.link(car, sp, "self")
    t.true(greater(t, (sp, "KPH"), 0.0), "the car moves under AI throttle")
    t.call(CONTROLLER, "UnPossess", ai)
    t.delay(0.5)
    t.false(t.get(VC, "bAIControlled", BOOL, car), "AI control released on unpossess")
    t.true(t.get(VC, "bAIHandbrake", BOOL, car), "parked with the handbrake on unpossess")
    destroy(t, car)
    despawn_npcs(t, gm)
    t.eq_int(ai_count(t), 0, "a controller without a car is gone after despawn")
    out.append(t.finish())
    return out


# ---- Task 3: driving ----
def ai_get_float(t: T, ai, var):
    return t.get(AIC, var, FLOAT, ai)


def abs_of(t: T, src):
    n = t.g.call_static(MATH, "Abs", inputs=[Pin("A", FLOAT)], outputs=[Pin("ReturnValue", FLOAT, "out")], pure=True)
    t.link(src, n, "A")
    return (n, "ReturnValue")


def teleport(t: T, car, loc, rot):
    xf = t.g.call_static(MATH, "MakeTransform", inputs=[struct_pin("Location", VECTOR), struct_pin("Rotation", ROTATOR),
                                                          struct_pin("Scale", VECTOR, default="1,1,1")],
                         outputs=[struct_pin("ReturnValue", TRANSFORM, "out")], pure=True)
    t.link(loc, xf, "Location")
    t.link(rot, xf, "Rotation")
    n = t.call(VC, "TeleportAndStop", car, inputs=[struct_pin("NewTransform", TRANSFORM)])
    t.g.link(xf, "ReturnValue", n, "NewTransform")


def car_rotation(t: T, car):
    n = t.g.call_on(ACTOR, "K2_GetActorRotation", outputs=[struct_pin("ReturnValue", ROTATOR, "out")], pure=True)
    t.link(car, n, "self")
    return (n, "ReturnValue")


def along_right(t: T, car, cm):
    """The car's location moved cm along its right vector."""
    right = t.g.call_on(ACTOR, "GetActorRightVector", outputs=[struct_pin("ReturnValue", VECTOR, "out")], pure=True)
    t.link(car, right, "self")
    shift = t.g.call_static(MATH, "Multiply_VectorFloat", inputs=[struct_pin("A", VECTOR), Pin("B", FLOAT, default="%f" % cm)],
                            outputs=[struct_pin("ReturnValue", VECTOR, "out")], pure=True)
    t.g.link(right, "ReturnValue", shift, "A")
    moved = t.g.call_static(MATH, "Add_VectorVector", inputs=[struct_pin("A", VECTOR), struct_pin("B", VECTOR)],
                            outputs=[struct_pin("ReturnValue", VECTOR, "out")], pure=True)
    t.link(t.loc(car), moved, "A")
    t.g.link(shift, "ReturnValue", moved, "B")
    return (moved, "ReturnValue")


def yawed(t: T, rot, degrees):
    """The rotator with its yaw turned by degrees."""
    br = t.g.call_static(MATH, "BreakRotator", inputs=[struct_pin("InRot", ROTATOR)],
                         outputs=[Pin("Roll", FLOAT, "out"), Pin("Pitch", FLOAT, "out"), Pin("Yaw", FLOAT, "out")], pure=True)
    t.link(rot, br, "InRot")
    add = t.g.call_static(MATH, "Add_FloatFloat", inputs=[Pin("A", FLOAT), Pin("B", FLOAT, default="%f" % degrees)],
                          outputs=[Pin("ReturnValue", FLOAT, "out")], pure=True)
    t.g.link(br, "Yaw", add, "A")
    mk = t.g.call_static(MATH, "MakeRotator", inputs=[Pin("Roll", FLOAT, default="0.0"), Pin("Pitch", FLOAT, default="0.0"), Pin("Yaw", FLOAT)],
                         outputs=[struct_pin("ReturnValue", ROTATOR, "out")], pure=True)
    t.g.link(add, "ReturnValue", mk, "Yaw")
    return (mk, "ReturnValue")


def flog(t: T, label, *srcs):
    """DF: <label> v1 v2 ... in the log (floats), for diagnosing a headless run."""
    from df import log_line
    parts = [label]
    for src in srcs:
        fs = t.g.call_static("KismetStringLibrary", "Conv_FloatToString", inputs=[Pin("InFloat", FLOAT)], outputs=[Pin("ReturnValue", STRING, "out")], pure=True)
        t.link(src, fs, "InFloat")
        parts += [" ", (fs, "ReturnValue")]
    t.step(log_line(t.g, *parts))


def driving_tests():
    out = []
    t = T("FT_DFAI_SteeringAndSpeedMath", "Steering turns toward the target and saturates at the lock angle; the target speed drops "
          "with corner severity; throttle follows the speed error and the hard-steer cap.")
    pc, gm, gs, racer, gates = race_context(t)
    spawn_npcs(t, gm, 1)
    ai = t.item(ai_controllers(t), AIC, "0")
    t.set(AIC, "SpeedScale", FLOAT, ai, default="1.0")

    def steer(x, y):
        n = t.g.call_on(AIC, "ComputeSteering", inputs=[struct_pin("FromLocation", VECTOR, default="0,0,0"), Pin("FromYaw", FLOAT, default="0.0"),
                                                         struct_pin("Target", VECTOR, default="%f,%f,0" % (x, y))],
                        outputs=[Pin("Steering", FLOAT, "out")], pure=True)
        t.link(ai, n, "self")
        return (n, "Steering")

    def target_speed(severity):
        n = t.g.call_on(AIC, "ComputeTargetSpeed", inputs=[Pin("Severity", FLOAT, default="%f" % severity)], outputs=[Pin("KPH", FLOAT, "out")], pure=True)
        t.link(ai, n, "self")
        return (n, "KPH")

    def throttle(speed, target, steering):
        n = t.g.call_on(AIC, "ComputeThrottle", inputs=[Pin("SpeedKPH", FLOAT, default="%f" % speed), Pin("TargetKPH", FLOAT, default="%f" % target),
                                                         Pin("Steering", FLOAT, default="%f" % steering)],
                        outputs=[Pin("Throttle", FLOAT, "out")], pure=True)
        t.link(ai, n, "self")
        return (n, "Throttle")

    t.true(greater(t, steer(1000.0, 500.0), 0.5), "a target to the right steers right (26.6 of 35 degrees)")
    t.less(steer(1000.0, -500.0), -0.5, "a target to the left steers left")
    t.eq_float(steer(1000.0, 0.0), 0.0, "a target straight ahead needs no steering", 0.01)
    t.eq_float(steer(0.0, 1000.0), 1.0, "a target 90 degrees off saturates at full lock", 0.001)
    t.eq_float(target_speed(0.0), 110.0, "straight: MaxSpeedKPH", 0.01)
    t.eq_float(target_speed(1.0), 45.0, "full corner: CornerSpeedKPH", 0.01)
    t.eq_float(target_speed(0.5), 77.5, "half severity: halfway", 0.01)
    t.eq_float(throttle(50.0, 100.0, 0.0), 1.0, "below the target: full throttle", 0.001)
    t.eq_float(throttle(120.0, 100.0, 0.0), -0.5, "well above the target: brake", 0.001)
    t.eq_float(throttle(105.0, 100.0, 0.0), 0.2, "just above the target: coast", 0.001)
    t.eq_float(throttle(80.0, 100.0, 0.9), 0.3, "hard steering above the corner speed caps the throttle", 0.001)
    despawn_npcs(t, gm)
    out.append(t.finish())

    t = T("FT_DFAI_DrivesTowardItsLane", "An NPC on the track at its spawn asks for full throttle and little steering; moved 3 m left of "
          "its lane it steers right; turned 60 degrees off the road it steers back.")
    pc, gm, gs, racer, gates = race_context(t)
    spawn_npcs(t, gm, 1)
    t.delay(1.5)
    ai = t.item(ai_controllers(t), AIC, "0")
    car = ai_car(t, ai)
    kph0 = t.g.call_on(VC, "GetSpeedKPH", outputs=[Pin("KPH", FLOAT, "out")], pure=True)
    t.link(car, kph0, "self")
    flog(t, "lane-test throttle/steering/scale/severity/kph", ai_get_float(t, ai, "Throttle"), ai_get_float(t, ai, "Steering"),
         ai_get_float(t, ai, "SpeedScale"), ai_get_float(t, ai, "LastSeverity"), (kph0, "KPH"))
    tp = t.get(AIC, "TargetPoint", "struct", ai, sub=struct_ref(VECTOR))
    btp = t.g.call_static(MATH, "BreakVector", inputs=[struct_pin("InVec", VECTOR)], outputs=[Pin("X", FLOAT, "out"), Pin("Y", FLOAT, "out"), Pin("Z", FLOAT, "out")], pure=True)
    t.link(tp, btp, "InVec")
    bcl = t.g.call_static(MATH, "BreakVector", inputs=[struct_pin("InVec", VECTOR)], outputs=[Pin("X", FLOAT, "out"), Pin("Y", FLOAT, "out"), Pin("Z", FLOAT, "out")], pure=True)
    t.link(t.loc(car), bcl, "InVec")
    brot = t.g.call_static(MATH, "BreakRotator", inputs=[struct_pin("InRot", ROTATOR)], outputs=[Pin("Roll", FLOAT, "out"), Pin("Pitch", FLOAT, "out"), Pin("Yaw", FLOAT, "out")], pure=True)
    t.link(car_rotation(t, car), brot, "InRot")
    flog(t, "lane-test target x/y, car x/y, yaw, bias, lane", (btp, "X"), (btp, "Y"), (bcl, "X"), (bcl, "Y"), (brot, "Yaw"),
         ai_get_float(t, ai, "AvoidBias"), ai_get_float(t, ai, "LaneOffset"))
    t.true(greater(t, ai_get_float(t, ai, "Throttle"), 0.9), "full throttle off the line")
    t.less(abs_of(t, ai_get_float(t, ai, "Steering")), 0.3, "little steering on its own lane")
    teleport(t, car, along_right(t, car, -300.0), car_rotation(t, car))
    t.delay(1.5)
    flog(t, "lane-test steering after 3 m left", ai_get_float(t, ai, "Steering"))
    t.true(greater(t, ai_get_float(t, ai, "Steering"), 0.2), "3 m left of the lane: steers right")
    teleport(t, car, along_right(t, car, 300.0), yawed(t, car_rotation(t, car), 60.0))
    t.delay(1.5)
    t.less(ai_get_float(t, ai, "Steering"), -0.2, "pointed 60 degrees right of the road: steers left")
    despawn_npcs(t, gm)
    out.append(t.finish())

    t = T("FT_DFAI_AvoidsBlockedSide", "A car ahead-left pushes the lane bias right, ahead-right pushes it left, nothing ahead clears it.")
    pc, gm, gs, racer, gates = race_context(t)
    spawn_npcs(t, gm, 1)
    ai = t.item(ai_controllers(t), AIC, "0")
    t.set(AIC, "bAutoDrive", BOOL, ai, default="false")  # hold the car still for the traces
    car = ai_car(t, ai)
    zero_rot = t.g.call_static(MATH, "MakeRotator", inputs=[Pin("Roll", FLOAT, default="0.0"), Pin("Pitch", FLOAT, default="0.0"), Pin("Yaw", FLOAT, default="0.0")],
                               outputs=[struct_pin("ReturnValue", ROTATOR, "out")], pure=True)
    teleport(t, car, t.offset(t.self_loc(), 0.0, 0.0, -120.0), (zero_rot, "ReturnValue"))
    blocker = spawn_vehicle(t, 1000.0, -150.0)
    t.delay(1.0)

    def avoidance():
        n = t.call(AIC, "ComputeAvoidance", ai, inputs=[obj_pin("Car", VC)], outputs=[Pin("Bias", FLOAT, "out")])
        t.link(car, n, "Car")
        return (n, "Bias")

    t.true(greater(t, avoidance(), 0.0), "a car ahead-left pushes the bias right")
    move_to(t, blocker, t.offset(t.self_loc(), 1000.0, 150.0, -120.0))
    t.delay(0.5)
    t.less(avoidance(), 0.0, "a car ahead-right pushes the bias left")
    move_to(t, blocker, t.offset(t.self_loc(), 0.0, 3000.0, -120.0))
    t.delay(0.5)
    t.eq_float(avoidance(), 0.0, "nothing ahead: no bias", 0.001)
    destroy(t, blocker)
    despawn_npcs(t, gm)
    out.append(t.finish())

    t = T("FT_DFAI_RaceEndStopsDriving", "After the race ends the NPC parks: throttle 0, handbrake on.")
    pc, gm, gs, racer, gates = race_context(t)
    spawn_npcs(t, gm, 1)
    t.delay(1.0)
    t.call(GMC, "EndRace", gm, inputs=[enum_pin("Reason", E_END_REASON, default=1)])
    t.delay(1.0)
    ai = t.item(ai_controllers(t), AIC, "0")
    car = ai_car(t, ai)
    t.eq_float(t.get(VC, "AIThrottle", FLOAT, car), 0.0, "throttle 0 after the race", 0.001)
    t.true(t.get(VC, "bAIHandbrake", BOOL, car), "handbrake on after the race")
    t.call(GMC, "RestartRace", gm)
    t.delay(0.5)
    out.append(t.finish())
    return out


# ---- Task 4: deaths and respawn for every racer ----
def gate_loc(t: T, gate):
    xf = t.g.call_on(CPC, "GetRespawnTransform", outputs=[struct_pin("Transform", TRANSFORM, "out")], pure=True)
    t.link(gate, xf, "self")
    return t.transform_loc((xf, "Transform"))


def rotator(t: T, roll=0.0, pitch=0.0, yaw=0.0):
    n = t.g.call_static(MATH, "MakeRotator", inputs=[Pin("Roll", FLOAT, default="%f" % roll), Pin("Pitch", FLOAT, default="%f" % pitch),
                                                       Pin("Yaw", FLOAT, default="%f" % yaw)],
                        outputs=[struct_pin("ReturnValue", ROTATOR, "out")], pure=True)
    return (n, "ReturnValue")


def not_same(t: T, a, b, message):
    n = t.g.call_static(MATH, "NotEqual_ObjectObject", inputs=[obj_pin("A", "/Script/CoreUObject.Object"), obj_pin("B", "/Script/CoreUObject.Object")],
                        outputs=[Pin("ReturnValue", BOOL, "out")], pure=True)
    t.link(a, n, "A")
    t.link(b, n, "B")
    t.true((n, "ReturnValue"), message)


def respawn_tests():
    out = []
    t = T("FT_DFAI_RespawnsWithoutEndingRace", "An NPC's third death never ends the race; 2.5 s later it drives an intact car near its gate; "
          "the player's deaths are untouched.")
    pc, gm, gs, racer, gates = race_context(t)
    spawn_npcs(t, gm, 1)
    t.delay(0.5)
    ai = t.item(ai_controllers(t), AIC, "0")
    npc = ai_racer(t, gm, ai)
    t.set(RC, "Deaths", INT, npc, default="2")
    t.damage(ai_car(t, ai), 100)
    t.delay(2.5)
    t.true(t.get(GSC, "bRaceActive", BOOL, gs), "the race goes on after an NPC's third death")
    t.eq_int(t.get(RC, "Deaths", INT, npc), 3, "NPC deaths")
    car = ai_car(t, ai)
    t.false(t.get(VC, "bIsDestroyed", BOOL, car), "the NPC drives an intact car again")
    t.less(t.distance(t.loc(car), gate_loc(t, t.item(gates, CPC, "0"))), 700.0, "back within 7 m of gate 0 (lane offset included)")
    t.eq_int(t.get(RC, "Deaths", INT, racer), 0, "the player's deaths are untouched")
    despawn_npcs(t, gm)
    out.append(t.finish())

    t = T("FT_DFAI_TwoRacersRespawnTogether", "Two NPCs wrecked in the same frame both return.")
    pc, gm, gs, racer, gates = race_context(t)
    spawn_npcs(t, gm, 2)
    t.delay(0.5)
    ais = ai_controllers(t)
    a0, a1 = t.item(ais, AIC, "0"), t.item(ais, AIC, "1")
    t.damage(ai_car(t, a0), 100)
    t.damage(ai_car(t, a1), 100)
    t.delay(2.5)
    t.false(t.get(VC, "bIsDestroyed", BOOL, ai_car(t, a0)), "first NPC drives an intact car")
    t.false(t.get(VC, "bIsDestroyed", BOOL, ai_car(t, a1)), "second NPC drives an intact car")
    t.eq_int(t.get(RC, "Deaths", INT, ai_racer(t, gm, a0)), 1, "first NPC deaths")
    t.eq_int(t.get(RC, "Deaths", INT, ai_racer(t, gm, a1)), 1, "second NPC deaths")
    despawn_npcs(t, gm)
    out.append(t.finish())

    t = T("FT_DFAI_FlippedCarRespawns", "An NPC on its roof is upright at its gate about 3.5 s later with no death counted.")
    pc, gm, gs, racer, gates = race_context(t)
    spawn_npcs(t, gm, 1)
    t.delay(0.5)
    ai = t.item(ai_controllers(t), AIC, "0")
    teleport(t, ai_car(t, ai), t.offset(t.self_loc(), 0.0, 0.0, -60.0), rotator(t, roll=180.0))
    t.delay(3.5)
    car = ai_car(t, ai)
    up = t.g.call_on(ACTOR, "GetActorUpVector", outputs=[struct_pin("ReturnValue", VECTOR, "out")], pure=True)
    t.link(car, up, "self")
    upz = t.g.call_static(MATH, "BreakVector", inputs=[struct_pin("InVec", VECTOR)], outputs=[Pin("X", FLOAT, "out"), Pin("Y", FLOAT, "out"), Pin("Z", FLOAT, "out")], pure=True)
    t.g.link(up, "ReturnValue", upz, "InVec")
    t.true(greater(t, (upz, "Z"), 0.5), "the car is upright again")
    t.less(t.distance(t.loc(car), gate_loc(t, t.item(gates, CPC, "0"))), 700.0, "back within 7 m of gate 0")
    t.eq_int(t.get(RC, "Deaths", INT, ai_racer(t, gm, ai)), 0, "no death counted for a flip")
    despawn_npcs(t, gm)
    out.append(t.finish())

    t = T("FT_DFAI_PlayerTakesNPCCar", "The player entering an NPC's car keeps it; the NPC gets another car at its gate after a second, "
          "no death counted.")
    pc, gm, gs, racer, gates = race_context(t)
    spawn_npcs(t, gm, 1)
    t.delay(0.5)
    ai = t.item(ai_controllers(t), AIC, "0")
    t.set(AIC, "bAutoDrive", BOOL, ai, default="false")
    npc_car = ai_car(t, ai)
    teleport(t, npc_car, t.offset(t.self_loc(), 800.0, 0.0, -120.0), rotator(t))
    pcar = park_player(t, pc)
    x = t.call(VC, "ExitVehicle", pcar, outputs=[Pin("ReturnValue", BOOL, "out")])
    t.true((x, "ReturnValue"), "the player got out")
    ch = t.get(PCC, "OnFootCharacter", OBJECT, pc, sub=cls_ref(CC))
    move_to(t, ch, t.offset(t.self_loc(), 800.0, 260.0, -60.0))
    t.delay(0.5)
    e = t.call(VC, "EnterVehicle", npc_car, inputs=[obj_pin("Character", CC)], outputs=[Pin("ReturnValue", BOOL, "out")])
    t.link(ch, e, "Character")
    t.true((e, "ReturnValue"), "the player took the NPC's car")
    t.delay(2.0)
    t.same(pawn_of(t, pc), npc_car, "the player still drives it")
    new_car = ai_car(t, ai)
    not_same(t, new_car, npc_car, "the NPC drives a different car")
    t.false(t.get(VC, "bIsDestroyed", BOOL, new_car), "an intact one")
    t.eq_int(t.get(RC, "Deaths", INT, ai_racer(t, gm, ai)), 0, "no death counted")
    t.call(GMC, "RestartRace", gm)
    t.delay(0.5)
    out.append(t.finish())
    return out


# ---- Task 5: items ----
def item_tests():
    out = []
    BOMBC, PROJC = gen(BP_BOMB), gen(BP_PROJECTILE)
    t = T("FT_DFAI_UsesItemsAtTargets", "ThinkItems shields a hurt car, shoots the player's car ahead, bombs a car behind, boosts on a "
          "straight, fires a rocket at 15 m but not at 8 m, leaves a parked player car alone, and does nothing once the race is over.")
    pc, gm, gs, racer, gates = race_context(t)
    pcar = park_player(t, pc)
    spawn_npcs(t, gm, 1)
    t.delay(0.5)
    ai = t.item(ai_controllers(t), AIC, "0")
    t.set(AIC, "bAutoDrive", BOOL, ai, default="false")
    car = ai_car(t, ai)
    teleport(t, car, t.offset(t.self_loc(), -800.0, 0.0, -120.0), rotator(t))  # 8 m behind the player's car, same heading
    t.delay(1.0)
    npc = ai_racer(t, gm, ai)

    def think():
        n = t.call(AIC, "ThinkItems", ai, inputs=[obj_pin("Car", VC)])
        t.link(car, n, "Car")

    def player_car_to(dx):
        teleport(t, pcar, t.offset(t.self_loc(), dx, 0.0, -100.0), rotator(t))

    # shield when hurt
    t.set(VC, "Health", FLOAT, car, default="30.0")
    t.true(grant(t, gm, ai, ITEM_SHIELD), "shield granted to the NPC")
    think()
    sh = t.g.call_on(VC, "IsShielded", outputs=[Pin("ReturnValue", BOOL, "out")], pure=True)
    t.link(car, sh, "self")
    t.true((sh, "ReturnValue"), "a hurt NPC raises its shield")
    t.call(VC, "ClearEffects", car)
    t.set(VC, "Health", FLOAT, car, default="100.0")
    # gun at the player's car 8 m ahead
    t.true(grant(t, gm, ai, ITEM_GUN, 8), "gun granted")
    think()
    t.eq_float(t.get(VC, "Health", FLOAT, pcar), 85.0, "the player's car is hit by the NPC's gun", 0.5)
    t.eq_int((selected(t, npc), "Charges"), 7, "one gun charge used")
    t.call(RC, "ClearInventory", npc)
    # bomb when a car is close behind
    player_car_to(-1400.0)
    t.true(grant(t, gm, ai, ITEM_BOMB), "bomb granted")
    think()
    t.eq_int(count_actors(t, BOMBC), 1, "a bomb is dropped for the car behind")
    t.call(GMC, "SweepItems", gm)
    player_car_to(0.0)
    t.call(RC, "ClearInventory", npc)
    # boost on a straight
    t.set(AIC, "LastSeverity", FLOAT, ai, default="0.0")
    t.true(grant(t, gm, ai, ITEM_BOOST), "boost granted")
    think()
    t.true(greater(t, t.get(VC, "BoostRemaining", FLOAT, car), 0.0), "boost used on a straight")
    t.call(VC, "ClearEffects", car)
    t.call(RC, "ClearInventory", npc)
    # rocket: not inside RPGMinRange, yes at 15 m
    t.true(grant(t, gm, ai, ITEM_RPG), "rocket granted")
    think()
    t.eq_int(count_actors(t, PROJC), 0, "no rocket at a car 8 m ahead (inside the minimum range)")
    player_car_to(700.0)
    think()
    t.eq_int(count_actors(t, PROJC), 1, "a rocket at the car 15 m ahead")
    t.delay(1.5)
    t.less(t.get(VC, "Health", FLOAT, pcar), 85.0, "the rocket hit the player's car")
    t.set(VC, "Health", FLOAT, pcar, default="100.0")
    player_car_to(0.0)
    t.call(RC, "ClearInventory", npc)
    # a parked player car (the player on foot) is not a target; CurrentVehicle empties on exit, so keep the car itself
    parked = pawn_car(t, pc)
    x = t.call(VC, "ExitVehicle", parked, outputs=[Pin("ReturnValue", BOOL, "out")])
    t.true((x, "ReturnValue"), "the player got out")
    t.true(grant(t, gm, ai, ITEM_GUN, 8), "gun granted again")
    think()
    t.eq_float(t.get(VC, "Health", FLOAT, parked), 100.0, "a parked player car is not shot")
    t.eq_int(inventory_length(t, npc), 1, "the gun is kept")
    ch = t.get(PCC, "OnFootCharacter", OBJECT, pc, sub=cls_ref(CC))
    e = t.call(VC, "EnterVehicle", parked, inputs=[obj_pin("Character", CC)], outputs=[Pin("ReturnValue", BOOL, "out")])
    t.link(ch, e, "Character")
    t.true((e, "ReturnValue"), "the player is back in the car")
    # race over: nothing is used
    t.call(GMC, "EndRace", gm, inputs=[enum_pin("Reason", E_END_REASON, default=1)])
    think()
    t.eq_int(inventory_length(t, npc), 1, "nothing used after the race ended")
    t.call(GMC, "RestartRace", gm)
    t.delay(0.5)
    out.append(t.finish())

    t = T("FT_DFAI_ItemSupply", "GrantNPCItems fills one slot of each NPC and none of the player's.")
    pc, gm, gs, racer, gates = race_context(t)
    spawn_npcs(t, gm, 2)
    t.delay(0.5)
    ais = ai_controllers(t)
    t.call(GMC, "GrantNPCItems", gm)
    t.eq_int(inventory_length(t, ai_racer(t, gm, t.item(ais, AIC, "0"))), 1, "first NPC holds one item")
    t.eq_int(inventory_length(t, ai_racer(t, gm, t.item(ais, AIC, "1"))), 1, "second NPC holds one item")
    t.eq_int(inventory_length(t, racer), 0, "the player got nothing")
    despawn_npcs(t, gm)
    out.append(t.finish())
    return out


def build():
    return spawn_and_rank_tests() + driving_tests() + respawn_tests() + item_tests()


if __name__ == "__main__":
    for b in build():
        print(b.write(OUT))
