"""Phase 7 FT_DFDrive_* tests (plan docs/superpowers/plans/2026-10-30-phase7-art-feel.md, Task 7): the flat drive strip in the
functional-test level (actor tag DFDriveStrip, 100,000 x 4,000 cm, top at Z 0) and the top-speed baselines of the three cars,
measured BEFORE any handling change (df.BASELINE_TOP_SPEED). Later tasks add the handling tests to this module.
"""
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, ".."))
from bpgen import cls_ref, struct_ref  # noqa: E402
from df import (ACTOR, BASELINE_TOP_SPEED, BOOL, BP_AI, BP_VEHICLE, CONTROLLER, FLOAT, GAMEPLAY, INT, MATH, NAME, OBJECT,  # noqa: E402
                OUT, PAWN, PRIMITIVE, ROTATOR, STRING, TRANSFORM, VECTOR, VEHICLES, WHEELED_MOVE, Pin, gen, log_line, obj_pin,
                struct_pin)
from df import (BP_CHARACTER, BP_GM, BP_PC, BPC_RACER, CAMERA_COMP, SCENE_COMP, SPRING_ARM, STRUCT, as_pin,  # noqa: E402  (Task 10)
                obj_spec)
from df import ACTOR_COMP, AUDIO_COMP, SOUND_BASE, SW_SKID, art_sound, asset_object  # noqa: E402  (Task 11)
from tests import FT, OBJ, T, race_context  # noqa: E402
from tests_items import destroy  # noqa: E402
from tests_ai import abs_of, flog, teleport  # noqa: E402

VC, AIC = gen(BP_VEHICLE), gen(BP_AI)
GMC, PCC, RC, CHAR_C = gen(BP_GM), gen(BP_PC), gen(BPC_RACER), gen(BP_CHARACTER)
STRIP_TAG = "DFDriveStrip"
START_BACK = 45000.0   # cm behind the strip centre on X
START_UP = 110.0       # cm above the strip actor's centre (its top is 50 cm higher): the car stands 60 cm up
HOLD_SECONDS = 12.0
SAMPLE_STEP = 0.5


# ---- helpers ----
def strip_start(t: T, dy=0.0, dz=0.0, roll=0.0):
    """(location, rotation) sources: the tagged strip's centre minus 45,000 on X, 60 cm above its top, facing +X;
    dy moves the start sideways (a lane), dz raises it, roll banks it (degrees)."""
    get = t.static(GAMEPLAY, "GetAllActorsWithTag", inputs=[Pin("WorldContextObject", OBJECT, hidden=True), Pin("Tag", NAME, default=STRIP_TAG)],
                   outputs=[Pin("OutActors", OBJECT, "out", cls_ref(ACTOR), container="Array")])
    t.true(greater_int(t, t.length((get, "OutActors"), ACTOR), 0), "the drive strip (tag %s) is in the level" % STRIP_TAG)
    strip = t.item((get, "OutActors"), ACTOR)
    loc = t.offset(t.loc(strip), -START_BACK, dy, START_UP + dz)
    rot = t.g.call_static(MATH, "MakeRotator", inputs=[Pin("Roll", FLOAT, default="%f" % roll), Pin("Pitch", FLOAT, default="0.0"),
                                                       Pin("Yaw", FLOAT, default="0.0")],
                          outputs=[struct_pin("ReturnValue", ROTATOR, "out")], pure=True)
    return loc, (rot, "ReturnValue")


def greater_int(t: T, a, b):
    n = t.g.call_static(MATH, "Greater_IntInt", inputs=[Pin("A", INT), Pin("B", INT, default=str(b))], outputs=[Pin("ReturnValue", BOOL, "out")], pure=True)
    t.link(a, n, "A")
    return (n, "ReturnValue")


def spawn_on_strip(t: T, vehicle_class, speed_kph=0.0, dy=0.0, dz=0.0, roll=0.0):
    """Spawns the car at strip_start (dy, dz, roll as there), driven by a raw AI controller (bAutoDrive off, so only SetAIInput
    steers it), and gives it speed_kph along +X. Returns (car, controller)."""
    loc, rot = strip_start(t, dy, dz, roll)
    xf = t.g.call_static(MATH, "MakeTransform", inputs=[struct_pin("Location", VECTOR), struct_pin("Rotation", ROTATOR),
                                                          struct_pin("Scale", VECTOR, default="1,1,1")],
                         outputs=[struct_pin("ReturnValue", TRANSFORM, "out")], pure=True)
    t.link(loc, xf, "Location")
    t.link(rot, xf, "Rotation")
    car_node = t.step(t.g.spawn_actor(vehicle_class))
    t.g.link(xf, "ReturnValue", car_node, "SpawnTransform")
    car = (car_node, "ReturnValue")
    ai_node = t.step(t.g.spawn_actor(AIC))
    t.g.link(xf, "ReturnValue", ai_node, "SpawnTransform")
    ai = (ai_node, "ReturnValue")
    t.set(AIC, "bAutoDrive", BOOL, ai, default="false")
    poss = t.call(CONTROLLER, "Possess", ai, inputs=[obj_pin("InPawn", PAWN)])
    t.link(car, poss, "InPawn")
    if speed_kph:
        mesh = t.get(VC, "Mesh", OBJECT, car, sub=cls_ref("/Script/Engine.SkeletalMeshComponent"))
        t.call(PRIMITIVE, "SetPhysicsLinearVelocity", mesh,
               inputs=[struct_pin("NewVel", VECTOR, default="%f,0,0" % (speed_kph / 0.036)), Pin("bAddToCurrent", BOOL, default="false"),
                       Pin("BoneName", NAME, default="None")])
    return car, ai


def speed_kph(t: T, car):
    n = t.g.call_on(VC, "GetSpeedKPH", outputs=[Pin("KPH", FLOAT, "out")], pure=True)
    t.link(car, n, "self")
    return (n, "KPH")


def float_str(t: T, src):
    fs = t.g.call_static("KismetStringLibrary", "Conv_FloatToString", inputs=[Pin("InFloat", FLOAT)], outputs=[Pin("ReturnValue", STRING, "out")], pure=True)
    t.link(src, fs, "InFloat")
    return (fs, "ReturnValue")


def track_max(t: T, car, var):
    """Max of the variable and the car's current speed, stored back in the variable."""
    mx = t.g.call_static(MATH, "FMax", inputs=[Pin("A", FLOAT), Pin("B", FLOAT)], outputs=[Pin("ReturnValue", FLOAT, "out")], pure=True)
    t.link(speed_kph(t, car), mx, "A")
    t.g.link(t.g.var_get(var, FLOAT), var, mx, "B")
    s = t.step(t.g.var_set(var, FLOAT))
    t.g.link(mx, "ReturnValue", s, var)


# ---- the top-speed baselines ----
def top_speed_tests():
    out = []
    for row in VEHICLES:
        baseline = BASELINE_TOP_SPEED[row.name]
        t = T("FT_DFDrive_TopSpeed%s" % row.name.capitalize(), "%s at full throttle for %d s on the drive strip: top speed within 5%% of the "
              "recorded baseline (measured before the Phase 7 handling change)." % (row.name, HOLD_SECONDS))
        t.bp.variable("MaxKPH", "float", "0.0")
        pc, gm, gs, racer, gates = race_context(t)  # the AI controller drives only while a race is on
        car, ai = spawn_on_strip(t, gen(row.asset))
        t.call(VC, "SetAIInput", car, inputs=[Pin("Throttle", FLOAT, default="1.0"), Pin("Steering", FLOAT, default="0.0"),
                                              Pin("bHandbrake", BOOL, default="false")])
        for _ in range(int(HOLD_SECONDS / SAMPLE_STEP)):
            t.delay(SAMPLE_STEP)
            track_max(t, car, "MaxKPH")
        mx = (t.g.var_get("MaxKPH", FLOAT), "MaxKPH")
        t.step(log_line(t.g, "DRIVE BASELINE %s " % row.name, float_str(t, mx)))
        destroy(t, car)
        if baseline is None:
            t.step(t.g.call_self_native(FT, "AssertTrue", inputs=[Pin("Condition", BOOL, default="false"),
                                                                  Pin("Message", STRING, default="no baseline for %s" % row.name)],
                                        outputs=[Pin("ReturnValue", BOOL, "out")]))
        else:
            diff = t.g.call_static(MATH, "Subtract_FloatFloat", inputs=[Pin("A", FLOAT), Pin("B", FLOAT, default="%f" % baseline)],
                                   outputs=[Pin("ReturnValue", FLOAT, "out")], pure=True)
            t.link(mx, diff, "A")
            ab = t.g.call_static(MATH, "Abs", inputs=[Pin("A", FLOAT)], outputs=[Pin("ReturnValue", FLOAT, "out")], pure=True)
            t.g.link(diff, "ReturnValue", ab, "A")
            ok = t.g.call_static(MATH, "LessEqual_FloatFloat", inputs=[Pin("A", FLOAT), Pin("B", FLOAT, default="%f" % (0.05 * baseline))],
                                 outputs=[Pin("ReturnValue", BOOL, "out")], pure=True)
            t.g.link(ab, "ReturnValue", ok, "A")
            t.true((ok, "ReturnValue"), "top speed within 5%% of the %s baseline %.1f km/h" % (row.name, baseline))
        out.append(t.finish())
    return out

# ---- Task 8: the handling math (pure functions on BP_DFVehicle, SEDAN defaults) ----
def pure_call(t: T, car, fn, args, out):
    """car.fn(args...) as a pure call; args = [(name, category, literal)]. Returns the output source."""
    n = t.g.call_on(VC, fn, inputs=[Pin(a, c, default=str(v)) for a, c, v in args], outputs=[Pin(out, FLOAT, "out")], pure=True)
    t.link(car, n, "self")
    return (n, out)


def math_test(name, doc, cases):
    """cases = [(fn, out, [(arg, cat, literal)...], expected)]; one SEDAN is spawned on the strip and destroyed."""
    t = T(name, doc)
    car, ai = spawn_on_strip(t, VC)
    for fn, out, args, expected in cases:
        label = "%s(%s)" % (fn, ", ".join(str(v) for _, _, v in args))
        t.eq_float(pure_call(t, car, fn, args, out), expected, label, 0.001)
    destroy(t, car)
    return t.finish()


def f(name, v):
    return (name, FLOAT, "%f" % v)


def b(name, v):
    return (name, BOOL, "true" if v else "false")


def math_tests():
    steer = [("ComputeSteerScale", "Scale", [f("SpeedKPH", s)], e) for s, e in ((0, 1.0), (75, 0.725), (150, 0.45), (300, 0.45))]
    steer += [("SmoothSteer", "Steer", [f("Current", c), f("Target", tg), f("DeltaSeconds", d)], e)
              for c, tg, d, e in ((0, 1, 0.1, 0.4), (1, 0, 0.1, 0.3), (0.5, -1, 0.1, -0.2), (0, 1, 1.0, 1.0), (0.9, 1, 0.1, 1.0))]
    force = [("ComputeDownforce", "Accel", [f("SpeedKPH", s)], e) for s, e in ((0, 0), (100, 245), (200, 980), (400, 1960))]
    force += [("ComputeGripAccel", "Accel", [f("LateralSpeed", l), b("bDriftingNow", d)], e)
              for l, d, e in ((1000, False, -3000), (1000, True, -900), (-500, False, 1500))]
    force += [("ComputeTargetFOV", "FOV", [f("SpeedKPH", s), b("bBoosting", bo)], e)
              for s, bo, e in ((0, False, 90), (80, False, 97.5), (160, False, 105), (320, True, 113))]
    force += [("ComputeEnginePitch", "Pitch", [f("RPMRatio", r)], e) for r, e in ((0, 0.6), (0.5, 1.3), (1.5, 2.0))]
    return [math_test("FT_DFDrive_SteerMath", "Steer scale by speed and the smoothed steering input, SEDAN defaults.", steer),
            math_test("FT_DFDrive_ForceMath", "Downforce, grip, target FOV and engine pitch formulas, SEDAN defaults.", force)]


# ---- Task 9: the arcade layer (spec §5.1, §5.2) ----
# Two lanes 30 m apart (strip half-width 20 m); both cars steer right (+Y), so each lane keeps room on that side.
LANE_A, LANE_B = -1800.0, 1200.0
SETTLE = 1.0  # the car starts 60 cm up: let it land before the measured part starts
DRIVE_DOC = ("SEDAN on the drive strip in the gear the auto-box holds at its start speed, raw AI controller (unsmoothed, unscaled "
             "inputs), the car ticking after the test, physics in step with game time (time dilation 0.25).")


def fop(t: T, fn, a, b=None, out_cat=FLOAT):
    """Pure KismetMathLibrary float op on sources or literals (b None for a one-input op such as Abs/NormalizeAxis)."""
    ins = [Pin("A", FLOAT, default=None if isinstance(a, tuple) else "%f" % a)]
    if fn == "NormalizeAxis":
        ins = [Pin("Angle", FLOAT, default=None if isinstance(a, tuple) else "%f" % a)]
    if b is not None:
        ins.append(Pin("B", FLOAT, default=None if isinstance(b, tuple) else "%f" % b))
    n = t.g.call_static(MATH, fn, inputs=ins, outputs=[Pin("ReturnValue", out_cat, "out")], pure=True)
    if isinstance(a, tuple):
        t.link(a, n, ins[0].name)
    if isinstance(b, tuple):
        t.link(b, n, "B")
    return (n, "ReturnValue")


def check(t: T, fn, a, b, message):
    """AssertTrue(fn(a, b)) for a float comparison such as LessEqual_FloatFloat / GreaterEqual_FloatFloat."""
    t.true(fop(t, fn, a, b, BOOL), message)


def store(t: T, var, src, cat=FLOAT):
    """The test's variable var := src at this point of the chain (pure sources re-evaluate at use time)."""
    s = t.step(t.g.var_set(var, cat))
    t.link(src, s, var)


def tvar(t: T, var, cat=FLOAT):
    return (t.g.var_get(var, cat), var)


def actor_vec(t: T, car, fn):
    n = t.g.call_on(ACTOR, fn, outputs=[struct_pin("ReturnValue", VECTOR, "out")], pure=True)
    t.link(car, n, "self")
    return (n, "ReturnValue")


def dot(t: T, a, b):
    n = t.g.call_static(MATH, "Dot_VectorVector", inputs=[struct_pin("A", VECTOR), struct_pin("B", VECTOR)],
                        outputs=[Pin("ReturnValue", FLOAT, "out")], pure=True)
    t.link(a, n, "A")
    t.link(b, n, "B")
    return (n, "ReturnValue")


def lateral_speed(t: T, car):
    """Velocity along the car's right vector, cm/s."""
    return dot(t, actor_vec(t, car, "GetVelocity"), actor_vec(t, car, "GetActorRightVector"))


def forward_speed(t: T, car):
    """Velocity along the car's forward vector, cm/s."""
    return dot(t, actor_vec(t, car, "GetVelocity"), actor_vec(t, car, "GetActorForwardVector"))


def rot_part(t: T, car, part):
    n = t.g.call_static(MATH, "BreakRotator", inputs=[struct_pin("InRot", ROTATOR)],
                        outputs=[Pin("Roll", FLOAT, "out"), Pin("Pitch", FLOAT, "out"), Pin("Yaw", FLOAT, "out")], pure=True)
    r = t.g.call_on(ACTOR, "K2_GetActorRotation", outputs=[struct_pin("ReturnValue", ROTATOR, "out")], pure=True)
    t.link(car, r, "self")
    t.g.link(r, "ReturnValue", n, "InRot")
    return (n, part)


def vec_part(t: T, src, part):
    n = t.g.call_static(MATH, "BreakVector", inputs=[struct_pin("InVec", VECTOR)],
                        outputs=[Pin("X", FLOAT, "out"), Pin("Y", FLOAT, "out"), Pin("Z", FLOAT, "out")], pure=True)
    t.link(src, n, "InVec")
    return (n, part)


def heading_change(t: T, car, yaw0_var):
    """The car's yaw now minus the stored yaw, normalised to (-180, 180]: positive = turned right."""
    return fop(t, "NormalizeAxis", fop(t, "Subtract_FloatFloat", rot_part(t, car, "Yaw"), tvar(t, yaw0_var)))


def set_input(t: T, car, throttle, steer, handbrake):
    t.call(VC, "SetAIInput", car, inputs=[Pin("Throttle", FLOAT, default="%f" % throttle), Pin("Steering", FLOAT, default="%f" % steer),
                                          Pin("bHandbrake", BOOL, default="true" if handbrake else "false")])


def car_mesh(t: T, car):
    return t.get(VC, "Mesh", OBJECT, car, sub=cls_ref("/Script/Engine.SkeletalMeshComponent"))


def set_velocity(t: T, car, vec_src, add=False):
    n = t.call(PRIMITIVE, "SetPhysicsLinearVelocity", car_mesh(t, car),
               inputs=[struct_pin("NewVel", VECTOR), Pin("bAddToCurrent", BOOL, default="true" if add else "false"),
                       Pin("BoneName", NAME, default="None")])
    t.link(vec_src, n, "NewVel")


def scaled(t: T, vec_src, factor):
    n = t.g.call_static(MATH, "Multiply_VectorFloat", inputs=[struct_pin("A", VECTOR), Pin("B", FLOAT, default="%f" % factor)],
                        outputs=[struct_pin("ReturnValue", VECTOR, "out")], pure=True)
    t.link(vec_src, n, "A")
    return (n, "ReturnValue")


def set_speed(t: T, car, kph):
    """The car's velocity := kph along its own forward vector (a known start speed after it has landed), in the gear the
    auto-box would hold at that speed."""
    set_velocity(t, car, scaled(t, actor_vec(t, car, "GetActorForwardVector"), kph / 0.036))
    set_gear(t, car, kph)


# The SEDAN template's transmission (read from BP_DFVehicle's VehicleMovement on 2026-10-31): forward ratios 4.0/2.0/1.5/1.1/1.0,
# final ratio 4.0, 5730 rpm, 35 cm wheels, up-shift at 0.65 of max rpm after a 2 s auto-box latency. A car simply given a start
# speed sits in first gear, its engine far past max rpm and braking hard (100 -> 64 km/h in 3 s at full throttle), for about
# 10 s of shifting; a car really driving at that speed would be in the gear chosen here.
GEAR_RATIOS, FINAL_RATIO, MAX_RPM, WHEEL_RADIUS_CM, UP_RATIO = (4.0, 2.0, 1.5, 1.1, 1.0), 4.0, 5729.6, 35.0, 0.65


def gear_for(kph):
    """The lowest forward gear whose engine speed at kph is at or below the up-shift point."""
    wheel_rad_s = kph / 0.036 / WHEEL_RADIUS_CM
    for i, ratio in enumerate(GEAR_RATIOS):
        if wheel_rad_s * ratio * FINAL_RATIO * 60.0 / (2.0 * math.pi) <= UP_RATIO * MAX_RPM:
            return i + 1
    return len(GEAR_RATIOS)


def set_gear(t: T, car, kph):
    mv = t.get(VC, "VehicleMovement", OBJECT, car, sub=cls_ref(WHEELED_MOVE))
    t.call(WHEELED_MOVE, "SetTargetGear", mv, inputs=[Pin("GearNum", INT, default=str(gear_for(kph))), Pin("bImmediate", BOOL, default="true")])


def tick_after_test(t: T, car):
    """The car ticks after this test in every frame, as a pawn ticks after its controller: an input the test sets is
    applied by the car in the same frame (TickDriveOverrides / TickArcade), never one frame later."""
    n = t.call(ACTOR, "AddTickPrerequisiteActor", car, inputs=[obj_pin("PrerequisiteActor", ACTOR)])
    t.g.link(t.g.self_node(), "self", n, "PrerequisiteActor")


def drive_car(t: T, kph, dy=0.0, dz=0.0, roll=0.0, throttle=0.0):
    """A SEDAN on the strip at kph, inputs (throttle, 0, no handbrake), ticking after the test."""
    car, ai = spawn_on_strip(t, VC, kph, dy, dz, roll)
    tick_after_test(t, car)
    if kph:
        set_gear(t, car, kph)
    set_input(t, car, throttle, 0.0, False)
    return car


# Headless runs are throttled to 3 fps (UEditorEngine::GetMaxTickRate returns 3 when every editor window is hidden), and
# substepping simulates at most MaxSubsteps x MaxSubstepDeltaTime = 6 x 1/60 = 0.1 s of physics per frame: at 1.0 dilation
# physics runs at about 0.3x game time. The arcade tests' seconds are seconds of driving, so they run at this global time
# dilation: a 0.33 s frame is then 0.083 s of game time, all of it simulated. Restored to 1.0 when the test finishes.
PHYSICS_REALTIME_DILATION = 0.25


def time_dilation(t: T, value):
    t.static(GAMEPLAY, "SetGlobalTimeDilation", inputs=[Pin("WorldContextObject", OBJECT, hidden=True), Pin("TimeDilation", FLOAT, default="%f" % value)])


def arcade_T(name, doc):
    """A test whose first step binds RestoreTimeDilation to OnTestFinished, then slows time. FinishTest broadcasts
    OnTestFinished on every finish (a pass, a failure, a time-out), so the shared PIE world never keeps the dilation."""
    t = T(name, doc)
    t.g.section("Clean-up on every finish (tests share one PIE world): time dilation back to 1.0")
    ev = t.g.custom_event("RestoreTimeDilation")
    restore = t.g.call_static(GAMEPLAY, "SetGlobalTimeDilation", inputs=[Pin("WorldContextObject", OBJECT, hidden=True),
                                                                          Pin("TimeDilation", FLOAT, default="1.0")])
    t.g.link(ev, "then", restore, "execute")
    now = t.g.call_static(GAMEPLAY, "GetGlobalTimeDilation", inputs=[Pin("WorldContextObject", OBJECT, hidden=True)],
                          outputs=[Pin("ReturnValue", FLOAT, "out")], pure=True)
    done = log_line(t.g, "DRIVE CLEANUP %s time dilation " % name, float_str(t, (now, "ReturnValue")))
    t.g.exec(restore, done)
    t.cleanup_tail = done  # a test may chain more clean-up after it (Task 10: SpeedFOV)
    bind = t.step(t.g.add_delegate(FT, "OnTestFinished", "FunctionalTestEventSignature__DelegateSignature", "/Script/FunctionalTesting"))
    t.g.link(ev, "OutputDelegate", bind, "Delegate")
    time_dilation(t, PHYSICS_REALTIME_DILATION)
    return t


def arcade_finish(t: T):
    time_dilation(t, 1.0)  # also restored by RestoreTimeDilation (bound to OnTestFinished)
    return t.finish()


def grip_test():
    t = arcade_T("FT_DFDrive_GripAssistKillsSlide", "At 60 km/h a 1000 cm/s sideways kick is down to 200 cm/s or less after 1.0 s. " + DRIVE_DOC)
    for v in ("KickKPH", "T0"):
        t.bp.variable(v, "float", "0.0")
    race_context(t)
    car = drive_car(t, 60.0)
    t.delay(SETTLE)
    set_speed(t, car, 60.0)
    store(t, "KickKPH", speed_kph(t, car))
    set_velocity(t, car, scaled(t, actor_vec(t, car, "GetActorRightVector"), 1000.0), add=True)
    store(t, "T0", game_seconds(t))
    t.delay(1.0)
    lat = lateral_speed(t, car)
    flog(t, "DRIVE GRIP kickKPH lateralAfter elapsed", tvar(t, "KickKPH"), lat, elapsed(t, "T0"))
    check(t, "LessEqual_FloatFloat", abs_of(t, lat), 200.0, "the sideways slide is down to 200 cm/s or less after 1.0 s")
    destroy(t, car)
    return arcade_finish(t)


def handbrake_test():
    t = arcade_T("FT_DFDrive_HandbrakeDrifts", "Two cars 30 m apart at 80 km/h, full right lock for 1.0 s, one with the handbrake: its heading changes "
          "at least 1.4 times as much, and it is drifting at 0.5 s. " + DRIVE_DOC)
    for v in ("YawA0", "YawB0", "T0"):
        t.bp.variable(v, "float", "0.0")
    t.bp.variable("bDriftAtHalf", "bool", "false")
    race_context(t)
    hb = drive_car(t, 80.0, LANE_A)
    plain = drive_car(t, 80.0, LANE_B)
    t.delay(SETTLE)
    set_speed(t, hb, 80.0)
    set_speed(t, plain, 80.0)
    store(t, "YawA0", rot_part(t, hb, "Yaw"))
    store(t, "YawB0", rot_part(t, plain, "Yaw"))
    store(t, "T0", game_seconds(t))
    set_input(t, hb, 0.0, 1.0, True)
    set_input(t, plain, 0.0, 1.0, False)
    t.delay(0.5)
    store(t, "bDriftAtHalf", t.get(VC, "bDrifting", BOOL, hb), BOOL)
    t.delay(0.5)
    d_hb, d_plain = heading_change(t, hb, "YawA0"), heading_change(t, plain, "YawB0")
    flog(t, "DRIVE HANDBRAKE headingHandbrake headingPlain kphHandbrake kphPlain elapsed", d_hb, d_plain, speed_kph(t, hb), speed_kph(t, plain),
         elapsed(t, "T0"))
    t.true(tvar(t, "bDriftAtHalf", BOOL), "the handbrake car is drifting 0.5 s into the turn")
    check(t, "GreaterEqual_FloatFloat", d_hb, fop(t, "Multiply_FloatFloat", d_plain, 1.4),
          "the handbrake car's heading change is at least 1.4 times the plain car's")
    destroy(t, hb)
    destroy(t, plain)
    return arcade_finish(t)


def drift_boost_test():
    t = arcade_T("FT_DFDrive_DriftBoost", "A 1.2 s drift released gives one boost: forward speed 0.2 s later at least 400 cm/s up, net of the "
          "coast-down of a control car that drifts and releases the same way with DriftBoostSpeed 0. A fresh car's 0.5 s drift "
          "released gives none. " + DRIVE_DOC)
    for v in ("VA0", "VC0", "VA1", "VC1", "T0"):
        t.bp.variable(v, "float", "0.0")
    t.bp.variable("bShortDrift", "bool", "false")
    race_context(t)
    car = drive_car(t, 80.0, LANE_A)
    ctrl = drive_car(t, 80.0, LANE_B)
    t.set(VC, "DriftBoostSpeed", FLOAT, ctrl, default="0.0")  # the control: the same drift and release, no kick
    t.delay(SETTLE)
    set_speed(t, car, 80.0)
    set_speed(t, ctrl, 80.0)
    store(t, "T0", game_seconds(t))
    set_input(t, car, 0.0, 1.0, True)
    set_input(t, ctrl, 0.0, 1.0, True)
    t.delay(1.2)
    store(t, "VA0", forward_speed(t, car))
    store(t, "VC0", forward_speed(t, ctrl))
    set_input(t, car, 0.0, 0.0, False)  # release: handbrake off, steering centred
    set_input(t, ctrl, 0.0, 0.0, False)
    t.delay(0.2)
    store(t, "VA1", forward_speed(t, car))
    store(t, "VC1", forward_speed(t, ctrl))
    gain = fop(t, "Subtract_FloatFloat", tvar(t, "VA1"), tvar(t, "VA0"))
    coast = fop(t, "Subtract_FloatFloat", tvar(t, "VC0"), tvar(t, "VC1"))
    flog(t, "DRIVE BOOST before after ctrlBefore ctrlAfter elapsed", tvar(t, "VA0"), tvar(t, "VA1"), tvar(t, "VC0"), tvar(t, "VC1"), elapsed(t, "T0"))
    t.eq_int(t.get(VC, "DriftBoostCount", INT, car), 1, "one drift boost after a 1.2 s drift is released")
    check(t, "GreaterEqual_FloatFloat", gain, fop(t, "Subtract_FloatFloat", 400.0, coast),
          "forward speed 0.2 s after the release is at least 400 cm/s up, net of the control car's coast-down")
    destroy(t, car)
    destroy(t, ctrl)
    # a fresh car drifts for only 0.5 s
    short = drive_car(t, 80.0, LANE_A)
    t.delay(SETTLE)
    set_speed(t, short, 80.0)
    set_input(t, short, 0.0, 1.0, True)
    t.delay(0.5)
    store(t, "bShortDrift", t.get(VC, "bDrifting", BOOL, short), BOOL)
    set_input(t, short, 0.0, 0.0, False)
    t.delay(0.5)
    t.true(tvar(t, "bShortDrift", BOOL), "the fresh car was drifting before its release")
    t.eq_int(t.get(VC, "DriftBoostCount", INT, short), 0, "no boost after a 0.5 s drift")
    destroy(t, short)
    return arcade_finish(t)


def air_test():
    t = arcade_T("FT_DFDrive_AirLevelsOut", "Dropped at rest from 600 cm above the strip with 40 degrees of roll: 2.5 s later it is grounded and "
          "|roll| < 10 degrees. " + DRIVE_DOC)
    for v in ("T0", "Z0"):
        t.bp.variable(v, "float", "0.0")
    race_context(t)
    car = drive_car(t, 0.0, 0.0, 600.0 - (START_UP - 50.0), 40.0)  # strip top + 600 cm (START_UP is 60 cm above the top)
    store(t, "T0", game_seconds(t))
    store(t, "Z0", vec_part(t, t.loc(car), "Z"))
    t.delay(2.5)
    grounded = t.call(VC, "IsGrounded", car, outputs=[Pin("ReturnValue", BOOL, "out")])
    roll = rot_part(t, car, "Roll")
    flog(t, "DRIVE AIR roll dropped(cm, from 600 above the top) verticalSpeed grounded(1/0) elapsed", roll,
         fop(t, "Subtract_FloatFloat", tvar(t, "Z0"), vec_part(t, t.loc(car), "Z")),
         vec_part(t, actor_vec(t, car, "GetVelocity"), "Z"), bool_float(t, (grounded, "ReturnValue")), elapsed(t, "T0"))
    t.true((grounded, "ReturnValue"), "grounded 2.5 s after the drop")
    check(t, "Less_FloatFloat", abs_of(t, roll), 10.0, "|roll| under 10 degrees 2.5 s after the drop")
    destroy(t, car)
    return arcade_finish(t)


def turn_test():
    t = arcade_T("FT_DFDrive_TurnsAtSpeed", "Review Focus 1: at 120 km/h the player's settled full lock (steer = the car's ComputeSteerScale(120), "
                 "the speed-scaled value the player's branch applies) without the handbrake for 1.5 s turns the car 45 degrees or more "
                 "and it stays upright (up Z > 0.7). " + DRIVE_DOC)
    for v in ("Yaw0", "KPH0", "T0", "Steer"):
        t.bp.variable(v, "float", "0.0")
    race_context(t)
    car = drive_car(t, 120.0, throttle=1.0)
    t.delay(SETTLE)
    set_speed(t, car, 120.0)
    store(t, "KPH0", speed_kph(t, car))
    store(t, "Yaw0", rot_part(t, car, "Yaw"))
    store(t, "T0", game_seconds(t))
    # the player's branch applies SmoothedSteer x ComputeSteerScale(speed); SmoothedSteer reaches full lock (1.0) in 0.25 s
    store(t, "Steer", pure_call(t, car, "ComputeSteerScale", [f("SpeedKPH", 120.0)], "Scale"))
    steer = t.call(VC, "SetAIInput", car, inputs=[Pin("Throttle", FLOAT, default="1.0"), Pin("Steering", FLOAT),
                                                  Pin("bHandbrake", BOOL, default="false")])
    t.link(tvar(t, "Steer"), steer, "Steering")
    t.delay(1.5)
    d = heading_change(t, car, "Yaw0")
    upz = vec_part(t, actor_vec(t, car, "GetActorUpVector"), "Z")
    flog(t, "DRIVE TURN steer startKPH heading upZ endKPH elapsed", tvar(t, "Steer"), tvar(t, "KPH0"), d, upz, speed_kph(t, car),
         elapsed(t, "T0"))
    check(t, "GreaterEqual_FloatFloat", d, 45.0, "the player's full lock at 120 km/h turns the car 45 degrees or more in 1.5 s")
    check(t, "Greater_FloatFloat", upz, 0.7, "the car stays upright (up Z > 0.7)")
    destroy(t, car)
    return arcade_finish(t)


def straight_test():
    t = arcade_T("FT_DFDrive_StraightStable", "At 100 km/h with no steering for 3 s the heading changes 3 degrees or less and the car stays within "
          "150 cm of its line. " + DRIVE_DOC)
    for v in ("Yaw0", "Y0", "T0"):
        t.bp.variable(v, "float", "0.0")
    race_context(t)
    car = drive_car(t, 100.0, throttle=1.0)
    t.delay(SETTLE)
    set_speed(t, car, 100.0)
    store(t, "Yaw0", rot_part(t, car, "Yaw"))
    store(t, "Y0", vec_part(t, t.loc(car), "Y"))
    store(t, "T0", game_seconds(t))
    t.delay(3.0)
    d = heading_change(t, car, "Yaw0")
    dy = fop(t, "Subtract_FloatFloat", vec_part(t, t.loc(car), "Y"), tvar(t, "Y0"))
    flog(t, "DRIVE STRAIGHT heading lateralOffset kph elapsed", d, dy, speed_kph(t, car), elapsed(t, "T0"))
    check(t, "LessEqual_FloatFloat", abs_of(t, d), 3.0, "heading change of 3 degrees or less over 3 s")
    check(t, "LessEqual_FloatFloat", abs_of(t, dy), 150.0, "within 150 cm of its line after 3 s")
    destroy(t, car)
    return arcade_finish(t)


def game_seconds(t: T):
    n = t.g.call_static(GAMEPLAY, "GetTimeSeconds", inputs=[Pin("WorldContextObject", OBJECT, hidden=True)],
                        outputs=[Pin("ReturnValue", FLOAT, "out")], pure=True)
    return (n, "ReturnValue")


def elapsed(t: T, t0_var):
    """Game seconds since the stored time (logged: headless frames are about 0.33 s, so a Delay overshoots)."""
    return fop(t, "Subtract_FloatFloat", game_seconds(t), tvar(t, t0_var))


def bool_float(t: T, src):
    n = t.g.call_static(MATH, "SelectFloat", inputs=[Pin("A", FLOAT, default="1.0"), Pin("B", FLOAT, default="0.0"), Pin("bPickA", BOOL)],
                        outputs=[Pin("ReturnValue", FLOAT, "out")], pure=True)
    t.link(src, n, "bPickA")
    return (n, "ReturnValue")


def arcade_tests():
    return [grip_test(), handbrake_test(), drift_boost_test(), air_test(), turn_test(), straight_test()]


# ---- Task 10: reset, look-back, camera (spec §5.2 Reset, §5.3 Camera) ----
FLIP_DZ = 150.0      # the flipped car starts this much higher, so its roof (underneath now) clears the strip
FLIP_SETTLE = 2.0    # it lands on its roof and comes to rest
FOV_KPH = 160.0      # 90 + 15 x clamp(160 / 160) = 105
RESET_DOC = ("SEDAN on the drive strip, raw AI controller (its racer component is the racer), the car ticking after the test, physics in "
             "step with game time (time dilation 0.25).")


def ground_kph(t: T, car):
    """|velocity| in km/h (the reset rule's speed: a car sliding sideways or falling is not at rest)."""
    n = t.g.call_static(MATH, "VSize", inputs=[struct_pin("A", VECTOR)], outputs=[Pin("ReturnValue", FLOAT, "out")], pure=True)
    t.link(actor_vec(t, car, "GetVelocity"), n, "A")
    return fop(t, "Multiply_FloatFloat", (n, "ReturnValue"), 0.036)


def reset_car(t: T, car):
    return (t.call(VC, "ResetCar", car, outputs=[Pin("ReturnValue", BOOL, "out")]), "ReturnValue")


def up_z(t: T, car):
    return vec_part(t, actor_vec(t, car, "GetActorUpVector"), "Z")


def int_float(t: T, src):
    n = t.g.call_static(MATH, "Conv_IntToFloat", inputs=[Pin("InInt", INT)], outputs=[Pin("ReturnValue", FLOAT, "out")], pure=True)
    t.link(src, n, "InInt")
    return (n, "ReturnValue")


def int_equal(t: T, a, b):
    n = t.g.call_static(MATH, "EqualEqual_IntInt", inputs=[Pin("A", INT), Pin("B", INT)], outputs=[Pin("ReturnValue", BOOL, "out")], pure=True)
    t.link(a, n, "A")
    t.link(b, n, "B")
    return (n, "ReturnValue")


def player_car(t: T, pc):
    """The player's pawn cast to BP_DFVehicle (impure cast, stepped): a snapshot that survives ExitVehicle."""
    pawn = t.g.call_on(CONTROLLER, "K2_GetPawn", outputs=[obj_pin("ReturnValue", PAWN, "out")], pure=True)
    t.link(pc, pawn, "self")
    c = t.step(t.g.cast(VC))
    t.g.link(pawn, "ReturnValue", c, "Object")
    return (c, as_pin(BP_VEHICLE))


def reset_uprights_test():
    t = arcade_T("FT_DFDrive_ResetCarUprights", "A SEDAN dropped upside down comes to rest on its roof; ResetCar() then returns true, 1.0 s later the "
                 "car is upright (up Z > 0.95) and its racer's deaths are unchanged (a reset is no death). " + RESET_DOC)
    for v in ("UpZ0", "KPH0", "T0"):
        t.bp.variable(v, "float", "0.0")
    t.bp.variable("Deaths0", "int", "0")
    pc, gm, gs, racer, gates = race_context(t)
    car, ai = spawn_on_strip(t, VC, 0.0, 0.0, FLIP_DZ, 180.0)
    tick_after_test(t, car)
    set_input(t, car, 0.0, 0.0, False)
    t.delay(FLIP_SETTLE)
    car_racer = t.racer(gm, ai)
    store(t, "UpZ0", up_z(t, car))
    store(t, "KPH0", ground_kph(t, car))
    store(t, "Deaths0", t.get(RC, "Deaths", INT, car_racer), INT)
    ok = reset_car(t, car)
    store(t, "T0", game_seconds(t))
    t.delay(1.0)
    upz = up_z(t, car)
    deaths = t.get(RC, "Deaths", INT, car_racer)
    flog(t, "DRIVE RESET upZBefore kphBefore result(1/0) upZAfter deathsBefore deathsAfter elapsed", tvar(t, "UpZ0"), tvar(t, "KPH0"),
         bool_float(t, ok), upz, int_float(t, tvar(t, "Deaths0", INT)), int_float(t, deaths), elapsed(t, "T0"))
    check(t, "Less_FloatFloat", tvar(t, "UpZ0"), -0.5, "the car lay on its roof before the reset (up Z < -0.5)")
    t.true(ok, "ResetCar() on the flipped car at rest returns true")
    check(t, "Greater_FloatFloat", upz, 0.95, "1.0 s after the reset the car is upright (up Z > 0.95)")
    t.true(int_equal(t, deaths, tvar(t, "Deaths0", INT)), "the racer's deaths are unchanged by the reset")
    destroy(t, car)
    return arcade_finish(t)


def reset_fast_test():
    t = arcade_T("FT_DFDrive_ResetRefusedWhenFast", "At 60 km/h ResetCar() returns false and the car is not lifted (a reset needs less than "
                 "15 km/h). " + RESET_DOC)
    for v in ("KPH0", "Z0", "Lift"):
        t.bp.variable(v, "float", "0.0")
    race_context(t)
    car = drive_car(t, 60.0)
    t.delay(SETTLE)
    set_speed(t, car, 60.0)
    store(t, "KPH0", ground_kph(t, car))
    store(t, "Z0", vec_part(t, t.loc(car), "Z"))
    ok = reset_car(t, car)
    store(t, "Lift", fop(t, "Subtract_FloatFloat", vec_part(t, t.loc(car), "Z"), tvar(t, "Z0")))
    lift = tvar(t, "Lift")
    flog(t, "DRIVE RESETFAST kph result(1/0) lift", tvar(t, "KPH0"), bool_float(t, ok), lift)
    t.false(ok, "ResetCar() at 60 km/h returns false")
    check(t, "LessEqual_FloatFloat", abs_of(t, lift), 50.0, "the refused reset did not lift the car")
    destroy(t, car)
    return arcade_finish(t)


def reset_cooldown_test():
    t = arcade_T("FT_DFDrive_ResetCooldown", "A reset at rest returns true; a second one 1.0 s later, with the car below 15 km/h again, returns "
                 "false (3 s cooldown); a third one 3.5 s after the first returns true. " + RESET_DOC)
    for v in ("T0", "KPH1", "Z1", "Lift2", "KPH2", "Elapsed1", "Elapsed2"):
        t.bp.variable(v, "float", "0.0")
    race_context(t)
    car = drive_car(t, 0.0)
    t.delay(SETTLE)
    first = reset_car(t, car)
    store(t, "T0", game_seconds(t))
    t.delay(1.0)
    store(t, "KPH1", ground_kph(t, car))
    store(t, "Z1", vec_part(t, t.loc(car), "Z"))
    store(t, "Elapsed1", elapsed(t, "T0"))
    second = reset_car(t, car)
    # stored now: a pure node re-evaluates where it is read, and the third reset lifts the car again
    store(t, "Lift2", fop(t, "Subtract_FloatFloat", vec_part(t, t.loc(car), "Z"), tvar(t, "Z1")))
    lift = tvar(t, "Lift2")
    t.delay(2.5)
    store(t, "KPH2", ground_kph(t, car))
    store(t, "Elapsed2", elapsed(t, "T0"))
    third = reset_car(t, car)
    flog(t, "DRIVE COOLDOWN first second third kph1 kph2 lift2 elapsed1 elapsed2", bool_float(t, first), bool_float(t, second),
         bool_float(t, third), tvar(t, "KPH1"), tvar(t, "KPH2"), lift, tvar(t, "Elapsed1"), tvar(t, "Elapsed2"))
    t.true(first, "the first reset at rest returns true")
    check(t, "Less_FloatFloat", tvar(t, "KPH1"), 15.0, "below 15 km/h at the second call, so only the cooldown can refuse it")
    t.false(second, "a second reset 1.0 s after the first is refused (3 s cooldown)")
    check(t, "LessEqual_FloatFloat", abs_of(t, lift), 50.0, "the refused reset did not lift the car")
    t.true(third, "a reset 3.5 s after the first is allowed again")
    destroy(t, car)
    return arcade_finish(t)


def fov_test():
    t = arcade_T("FT_DFDrive_SpeedFOV", "The player's car teleported onto the strip (more than 100 m): the next frame its chase camera is "
                 "within 10 m of the car (no camera lag across a teleport); after 1 s at rest its FOV is 90 +- 0.5; held "
                 "at 160 km/h for 3 s it is 105 +- 1 (spec §5.3: 90 + 15 x clamp(speed / 160), interpolated at 4 /s). Its spring arm has "
                 "camera lag 10 and rotation lag 8 again. The off-track grace is raised while the car is on the strip (restored on every "
                 "finish), physics in step with game time (time dilation 0.25).")
    for v in ("Grace0", "FOVRest", "FOVFast", "KPHFast", "T0", "Jump", "CamGap"):
        t.bp.variable(v, "float", "0.0")
    t.bp.variable("bHold", "bool", "false")
    t.bp.variable("HoldCar", obj_spec(BP_VEHICLE), "")
    t.bp.variable("HoldGM", obj_spec(BP_GM), "")
    pc, gm, gs, racer, gates = race_context(t)
    car = player_car(t, pc)
    for var, src, cls in (("HoldCar", car, VC), ("HoldGM", gm, GMC)):
        s = t.step(t.g.var_set(var, OBJECT, sub_object=cls_ref(cls)))
        t.link(src, s, var)
    store(t, "Grace0", t.get(GMC, "OffTrackGraceSeconds", FLOAT, gm))
    t.set(GMC, "OffTrackGraceSeconds", FLOAT, gm, default="1000.0")  # the strip is off every road: no off-track respawn meanwhile
    loc, rot = strip_start(t)
    store(t, "Jump", t.distance(t.loc(car), loc))  # from the start line to the strip
    teleport(t, car, loc, rot)
    # Fix round 1: the next frame (the spring arm has ticked once since the teleport) the chase camera is at the car, not
    # flying in from the start line: the spring arm's location lag has no teleport detection of its own
    t.delay(0.01)
    cam = t.get(VC, "ChaseCamera", OBJECT, car, sub=cls_ref(CAMERA_COMP))
    cam_at = t.g.call_on(SCENE_COMP, "K2_GetComponentLocation", outputs=[struct_pin("ReturnValue", VECTOR, "out")], pure=True)
    t.link(cam, cam_at, "self")
    store(t, "CamGap", t.distance((cam_at, "ReturnValue"), t.loc(car)))
    t.delay(1.0)
    store(t, "FOVRest", t.get(CAMERA_COMP, "FieldOfView", FLOAT, cam))
    set_gear(t, car, FOV_KPH)
    store(t, "T0", game_seconds(t))
    t.step(t.g.var_set("bHold", BOOL, default="true"))
    t.delay(3.0)
    store(t, "FOVFast", t.get(CAMERA_COMP, "FieldOfView", FLOAT, cam))
    store(t, "KPHFast", speed_kph(t, car))
    t.step(t.g.var_set("bHold", BOOL, default="false"))
    flog(t, "DRIVE FOV jump(cm) cameraGapNextFrame(cm) rest fast kphFast elapsed", tvar(t, "Jump"), tvar(t, "CamGap"), tvar(t, "FOVRest"),
         tvar(t, "FOVFast"), tvar(t, "KPHFast"), elapsed(t, "T0"))
    check(t, "Greater_FloatFloat", tvar(t, "Jump"), 10000.0, "the teleport moved the car more than 100 m")
    check(t, "LessEqual_FloatFloat", tvar(t, "CamGap"), 1000.0, "the frame after the teleport the chase camera is within 10 m of the car")
    t.eq_float(tvar(t, "FOVRest"), 90.0, "chase camera FOV after 1 s at rest", 0.5)
    t.eq_float(tvar(t, "FOVFast"), 105.0, "chase camera FOV after 3 s at 160 km/h", 1.0)
    arm = t.get(VC, "SpringArm", OBJECT, car, sub=cls_ref(SPRING_ARM))
    t.true(t.get(SPRING_ARM, "bEnableCameraLag", BOOL, arm), "the spring arm has camera lag")
    t.eq_float(t.get(SPRING_ARM, "CameraLagSpeed", FLOAT, arm), 10.0, "spring arm camera lag speed", 0.001)
    t.true(t.get(SPRING_ARM, "bEnableCameraRotationLag", BOOL, arm), "the spring arm has camera rotation lag")
    t.eq_float(t.get(SPRING_ARM, "CameraRotationLagSpeed", FLOAT, arm), 8.0, "spring arm camera rotation lag speed", 0.001)
    t.set(GMC, "OffTrackGraceSeconds", FLOAT, gm, value=tvar(t, "Grace0"))
    t.call(GMC, "RestartRace", gm)  # the player's car back on the start line
    # every frame while bHold: the car's velocity := 160 km/h along its forward vector (it has no throttle: nobody presses a key)
    t.g.section("Hold: the player's car at 160 km/h every frame while bHold")
    tick = t.g.tick()
    hb = t.g.branch()
    t.g.link(tick, "then", hb, "execute")
    t.g.link(t.g.var_get("bHold", BOOL), "bHold", hb, "Condition")
    held = (t.g.var_get("HoldCar", OBJECT, cls_ref(VC)), "HoldCar")
    mesh = t.g.var_get_on(VC, "Mesh", OBJECT, cls_ref("/Script/Engine.SkeletalMeshComponent"))
    t.link(held, mesh, "self")
    vel = t.g.call_on(PRIMITIVE, "SetPhysicsLinearVelocity", inputs=[struct_pin("NewVel", VECTOR), Pin("bAddToCurrent", BOOL, default="false"),
                                                                     Pin("BoneName", NAME, default="None")])
    t.g.link(mesh, "Mesh", vel, "self")
    t.link(scaled(t, actor_vec(t, held, "GetActorForwardVector"), FOV_KPH / 0.036), vel, "NewVel")
    t.g.link(hb, "then", vel, "execute")
    # clean-up on every finish: stop holding and put the off-track grace back (Grace0 > 0 once it was read)
    stop = t.g.var_set("bHold", BOOL, default="false")
    t.g.exec(t.cleanup_tail, stop)
    stored = t.g.call_static(MATH, "Greater_FloatFloat", inputs=[Pin("A", FLOAT), Pin("B", FLOAT, default="0.0")],
                             outputs=[Pin("ReturnValue", BOOL, "out")], pure=True)
    t.g.link(t.g.var_get("Grace0", FLOAT), "Grace0", stored, "A")
    bg = t.g.branch()
    t.g.link(stored, "ReturnValue", bg, "Condition")
    t.g.exec(stop, bg)
    put_back = t.g.var_set_on(GMC, "OffTrackGraceSeconds", FLOAT)
    t.g.link(t.g.var_get("HoldGM", OBJECT, cls_ref(GMC)), "HoldGM", put_back, "self")
    t.g.link(t.g.var_get("Grace0", FLOAT), "Grace0", put_back, "OffTrackGraceSeconds")
    t.g.link(bg, "then", put_back, "execute")
    return arcade_finish(t)


def arm_yaw_off(t: T, car):
    """|NormalizeAxis(spring arm relative yaw - the car's ArmBaseRotation yaw)|: 0 in the chase view, 180 looking back."""
    arm = t.get(VC, "SpringArm", OBJECT, car, sub=cls_ref(SPRING_ARM))
    rel = t.get(SCENE_COMP, "RelativeRotation", STRUCT, arm, sub=struct_ref(ROTATOR))
    br = t.g.call_static(MATH, "BreakRotator", inputs=[struct_pin("InRot", ROTATOR)],
                         outputs=[Pin("Roll", FLOAT, "out"), Pin("Pitch", FLOAT, "out"), Pin("Yaw", FLOAT, "out")], pure=True)
    t.link(rel, br, "InRot")
    base = t.get(VC, "ArmBaseRotation", STRUCT, car, sub=struct_ref(ROTATOR))
    bb = t.g.call_static(MATH, "BreakRotator", inputs=[struct_pin("InRot", ROTATOR)],
                         outputs=[Pin("Roll", FLOAT, "out"), Pin("Pitch", FLOAT, "out"), Pin("Yaw", FLOAT, "out")], pure=True)
    t.link(base, bb, "InRot")
    return abs_of(t, fop(t, "NormalizeAxis", fop(t, "Subtract_FloatFloat", (br, "Yaw"), (bb, "Yaw"))))


def state_clears_test():
    t = T("FT_DFDrive_StateClearsOnExitAndRespawn", "Review Focus 5: look-back, drift, the smoothed steer and the held handbrake are cleared, "
          "and the spring arm faces forward again, after ExitVehicle, after TeleportAndStop (respawns) and after a pause (TogglePause twice).")
    pc, gm, gs, racer, gates = race_context(t)
    car = player_car(t, pc)

    def dirty():
        t.call(VC, "SetLookBack", car, inputs=[Pin("bOn", BOOL, default="true")])
        t.set(VC, "bDrifting", BOOL, car, default="true")
        t.set(VC, "SmoothedSteer", FLOAT, car, default="0.7")
        t.set(VC, "bHandbrakeHeld", BOOL, car, default="true")

    def clean(after):
        t.false(t.get(VC, "bLookBack", BOOL, car), "look-back off after %s" % after)
        t.false(t.get(VC, "bDrifting", BOOL, car), "not drifting after %s" % after)
        t.eq_float(t.get(VC, "SmoothedSteer", FLOAT, car), 0.0, "smoothed steer after %s" % after, 0.001)
        t.false(t.get(VC, "bHandbrakeHeld", BOOL, car), "handbrake not held after %s" % after)
        check(t, "LessEqual_FloatFloat", arm_yaw_off(t, car), 0.5, "the spring arm faces forward again after %s" % after)

    dirty()
    t.true(t.get(VC, "bLookBack", BOOL, car), "SetLookBack(true) turns look-back on")
    check(t, "GreaterEqual_FloatFloat", arm_yaw_off(t, car), 179.5, "looking back turns the spring arm 180 degrees")
    out = t.call(VC, "ExitVehicle", car, outputs=[Pin("ReturnValue", BOOL, "out")])
    t.true((out, "ReturnValue"), "the player got out of the car")
    clean("ExitVehicle")
    dirty()
    rot = t.g.call_on(ACTOR, "K2_GetActorRotation", outputs=[struct_pin("ReturnValue", ROTATOR, "out")], pure=True)
    t.link(car, rot, "self")
    teleport(t, car, t.loc(car), (rot, "ReturnValue"))
    clean("TeleportAndStop")
    back = t.call(VC, "EnterVehicle", car, inputs=[obj_pin("Character", CHAR_C)], outputs=[Pin("ReturnValue", BOOL, "out")])
    t.link(t.get(PCC, "OnFootCharacter", OBJECT, pc, sub=cls_ref(CHAR_C)), back, "Character")
    t.true((back, "ReturnValue"), "the player is back in the car")
    dirty()
    t.call(PCC, "TogglePause", pc)  # pause and resume with nothing latent in between (a paused world stalls every Delay)
    t.call(PCC, "TogglePause", pc)
    paused = t.g.call_static(GAMEPLAY, "IsGamePaused", inputs=[Pin("WorldContextObject", OBJECT, hidden=True)],
                             outputs=[Pin("ReturnValue", BOOL, "out")], pure=True)
    t.false((paused, "ReturnValue"), "the game runs again after two TogglePause calls")
    clean("a pause")
    return t.finish()


def task10_tests():
    return [reset_uprights_test(), reset_fast_test(), reset_cooldown_test(), fov_test(), state_clears_test()]


# ---- Task 11: engine and skid audio (spec §5.4) ----
AUDIO_LANES = (-1500.0, 0.0, 1500.0)  # SEDAN / BRUTE / VIPER side by side, 15 m apart, inside the strip's 20 m half-width
AUDIO_FULL_THROTTLE = 3.0
SKID_KICK = 1000.0                   # cm/s sideways: clamp((1000 - 300) / 700) = 1


def audio_comp(t: T, car, name):
    return t.get(VC, name, OBJECT, car, sub=cls_ref(AUDIO_COMP))


def audio_value(t: T, comp, prop):
    """AudioComponent.PitchMultiplier / VolumeMultiplier (what SetPitchMultiplier / SetVolumeMultiplier wrote)."""
    return t.get(AUDIO_COMP, prop, FLOAT, comp)


def same_asset(t: T, src, asset, message):
    """AssertTrue(src == the asset) for an object source and an asset path."""
    n = t.g.call_static(MATH, "EqualEqual_ObjectObject", inputs=[obj_pin("A", OBJ), Pin("B", OBJECT, sub_object=cls_ref(OBJ),
                                                                                            default_object=asset_object(asset))],
                        outputs=[Pin("ReturnValue", BOOL, "out")], pure=True)
    t.link(src, n, "A")
    t.true((n, "ReturnValue"), message)


def engine_audio_test():
    t = arcade_T("FT_DFDrive_EngineAudioFollowsRPM",
                 "Spec §5.4, per car (SEDAN, BRUTE and VIPER side by side on the drive strip, raw AI controllers): 0.5 s after spawn "
                 "EngineAudio's sound is the car's EngineSound (the catalogue's SW_DF_Engine*), it auto-activates, and it is playing "
                 "(asserted when the world has an audio device, GetMaxAudioChannelCount > 0; a -nosound run has none, so there the "
                 "sound, auto-activation and multipliers stand in); at rest its volume is 0.35 and SkidAudio (SW_DF_Skid) is silent. "
                 "After 3 s at full throttle the engine pitch multiplier is above 1.0 and its volume 1.0, and a 1000 cm/s sideways "
                 "kick turns the SEDAN's skid volume up. Physics in step with game time (time dilation 0.25).")
    t.bp.variable("Channels", "int", "0")
    race_context(t)
    cars = []
    for row, lane in zip(VEHICLES, AUDIO_LANES):
        car, ai = spawn_on_strip(t, gen(row.asset), dy=lane)
        tick_after_test(t, car)
        set_input(t, car, 0.0, 0.0, False)
        cars.append((row, car))
    t.delay(0.5)
    channels = t.static(GAMEPLAY, "GetMaxAudioChannelCount", inputs=[Pin("WorldContextObject", OBJECT, hidden=True)],
                        outputs=[Pin("ReturnValue", INT, "out")])
    store(t, "Channels", (channels, "ReturnValue"), INT)
    no_device = t.g.call_static(MATH, "EqualEqual_IntInt", inputs=[Pin("A", INT), Pin("B", INT, default="0")],
                                outputs=[Pin("ReturnValue", BOOL, "out")], pure=True)
    t.link(tvar(t, "Channels", INT), no_device, "A")
    for row, car in cars:
        engine, skid = audio_comp(t, car, "EngineAudio"), audio_comp(t, car, "SkidAudio")
        playing = t.g.call_on(AUDIO_COMP, "IsPlaying", outputs=[Pin("ReturnValue", BOOL, "out")], pure=True)
        t.link(engine, playing, "self")
        flog(t, "DRIVE AUDIO %s rest: channels playing(1/0) pitch volume skidVolume" % row.name, int_float(t, tvar(t, "Channels", INT)),
             bool_float(t, (playing, "ReturnValue")), audio_value(t, engine, "PitchMultiplier"), audio_value(t, engine, "VolumeMultiplier"),
             audio_value(t, skid, "VolumeMultiplier"))
        sound = t.get(AUDIO_COMP, "Sound", OBJECT, engine, sub=cls_ref(SOUND_BASE))
        t.same(sound, t.get(VC, "EngineSound", OBJECT, car, sub=cls_ref(SOUND_BASE)), "%s: EngineAudio's sound is the car's EngineSound" % row.name)
        same_asset(t, sound, art_sound(row.engine_sound), "%s: EngineAudio plays %s" % (row.name, row.engine_sound))
        t.true(t.get(ACTOR_COMP, "bAutoActivate", BOOL, engine), "%s: EngineAudio auto-activates" % row.name)
        heard = t.g.call_static(MATH, "BooleanOR", inputs=[Pin("A", BOOL), Pin("B", BOOL)], outputs=[Pin("ReturnValue", BOOL, "out")], pure=True)
        t.g.link(playing, "ReturnValue", heard, "A")
        t.g.link(no_device, "ReturnValue", heard, "B")
        t.true((heard, "ReturnValue"), "%s: EngineAudio is playing 0.5 s after spawn (checked when the world has an audio device)" % row.name)
        t.eq_float(audio_value(t, engine, "VolumeMultiplier"), 0.35, "%s engine volume at rest (throttle 0)" % row.name, 0.01)
        same_asset(t, t.get(AUDIO_COMP, "Sound", OBJECT, skid, sub=cls_ref(SOUND_BASE)), SW_SKID, "%s: SkidAudio plays SW_DF_Skid" % row.name)
        t.true(t.get(ACTOR_COMP, "bAutoActivate", BOOL, skid), "%s: SkidAudio auto-activates" % row.name)
        t.eq_float(audio_value(t, skid, "VolumeMultiplier"), 0.0, "%s skid volume at rest" % row.name, 0.001)
    for row, car in cars:
        set_input(t, car, 1.0, 0.0, False)
    t.delay(AUDIO_FULL_THROTTLE)
    for row, car in cars:
        engine = audio_comp(t, car, "EngineAudio")
        pitch = audio_value(t, engine, "PitchMultiplier")
        flog(t, "DRIVE AUDIO %s full throttle: pitch volume kph" % row.name, pitch, audio_value(t, engine, "VolumeMultiplier"), speed_kph(t, car))
        check(t, "Greater_FloatFloat", pitch, 1.0, "%s: after 3 s at full throttle the engine pitch multiplier is above 1.0" % row.name)
        t.eq_float(audio_value(t, engine, "VolumeMultiplier"), 1.0, "%s engine volume at full throttle" % row.name, 0.01)
    # the skid: a sideways kick on the SEDAN (it ticks after the test, so the frame of the kick already sets the volume)
    sedan = cars[0][1]
    set_velocity(t, sedan, scaled(t, actor_vec(t, sedan, "GetActorRightVector"), SKID_KICK), add=True)
    t.delay(0.01)
    skid_now = audio_value(t, audio_comp(t, sedan, "SkidAudio"), "VolumeMultiplier")
    flog(t, "DRIVE AUDIO SEDAN skid after a %d cm/s sideways kick: volume lateral" % SKID_KICK, skid_now, lateral_speed(t, sedan))
    check(t, "Greater_FloatFloat", skid_now, 0.5, "a 1000 cm/s sideways slide turns the SEDAN's skid volume above 0.5")
    for row, car in cars:
        destroy(t, car)
    return arcade_finish(t)


def task11_tests():
    return [engine_audio_test()]


def build():
    return top_speed_tests() + math_tests() + arcade_tests() + task10_tests() + task11_tests()


if __name__ == "__main__":
    for b in build():
        print(b.write(OUT))
