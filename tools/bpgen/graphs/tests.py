"""FT_DF* Blueprint Functional Tests (plan Tasks 3-8). Each test is a FunctionalTest child whose Start Test event runs
a straight chain of steps: set-up, asserts (AssertTrue / AssertEqual_Int / AssertEqual_Float, which log an error and
fail the automation test when they do not hold), then FinishTest(Succeeded). df_build_test_track.py places one actor
per test in /Game/DeadFire/Tests/L_DF_FunctionalTests; tools/run_tests.ps1 runs them headless.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from bpgen import cls_ref, struct_ref  # noqa: E402
from df import (ACTOR, BOOL, BP_CHARACTER, BP_CHECKPOINT, BP_GM, BP_GS, BP_PC, BP_TRACK, BP_VEHICLE, BPC_RACER,  # noqa: E402
                BPC_WEAPON, CONTROLLER, FLOAT, GAMEPLAY, HIT_RESULT, INT, MATH, NAME, OBJECT, OUT, PAWN, PRIMITIVE,
                ROTATOR, S_RESULT, S_TIRE, SPACE, SPLINE_COMP, STRING, STRUCT, TESTS, TRANSFORM, VECTOR, Blueprint,
                Graph, Node, Pin, as_pin, enum_pin, gen, get_player_controller, is_valid, math2, member,
                native_enum_pin, obj_pin, struct_path, struct_pin)

FT = "/Script/FunctionalTesting.FunctionalTest"
RESULT_ENUM = "/Script/FunctionalTesting.EFunctionalTestResult"
VC, CC, PCC, GMC, GSC, TC, CPC, RC, WC = (gen(BP_VEHICLE), gen(BP_CHARACTER), gen(BP_PC), gen(BP_GM), gen(BP_GS),
                                         gen(BP_TRACK), gen(BP_CHECKPOINT), gen(BPC_RACER), gen(BPC_WEAPON))
TIRE, RESULT = struct_path(S_TIRE), struct_path(S_RESULT)
OBJ = "/Script/CoreUObject.Object"
ARR = "KismetArrayLibrary"


class T:
    """One functional test: a Blueprint plus a linear exec chain on its Start Test event."""

    def __init__(self, name: str, doc: str):
        self.bp = Blueprint("%s/%s" % (TESTS, name), parent=FT, description=doc)
        self.g = self.bp.event_graph()
        self.g.section(doc)
        start = self.g.event(FT, "ReceiveStartTest", col=0, row=1)
        self.prev = (start, "then")

    # ---- plumbing ----
    def step(self, node: Node, in_pin="execute", out_pin="then") -> Node:
        self.g.link(self.prev[0], self.prev[1], node, in_pin)
        self.prev = (node, out_pin)
        return node

    def link(self, src, node, pin):
        self.g.link(src[0], src[1], node, pin)

    # ---- context ----
    def self_loc(self):
        n = self.g.call_self_native(ACTOR, "K2_GetActorLocation", outputs=[struct_pin("ReturnValue", VECTOR, "out")], pure=True)
        return (n, "ReturnValue")

    def offset(self, base, x=0.0, y=0.0, z=0.0):
        n = self.g.call_static(MATH, "Add_VectorVector", inputs=[struct_pin("A", VECTOR), struct_pin("B", VECTOR, default="%f,%f,%f" % (x, y, z))],
                               outputs=[struct_pin("ReturnValue", VECTOR, "out")], pure=True)
        self.link(base, n, "A")
        return (n, "ReturnValue")

    def transform(self, loc):
        n = self.g.call_static(MATH, "MakeTransform", inputs=[struct_pin("Location", VECTOR), struct_pin("Rotation", ROTATOR),
                                                                struct_pin("Scale", VECTOR, default="1,1,1")],
                               outputs=[struct_pin("ReturnValue", TRANSFORM, "out")], pure=True)
        self.link(loc, n, "Location")
        return (n, "ReturnValue")

    def spawn(self, cls, loc):
        n = self.step(self.g.spawn_actor(cls))
        self.link(self.transform(loc), n, "SpawnTransform")
        return (n, "ReturnValue")

    def player(self):
        """Player controller 0 cast to BP_DFPlayerController (impure cast, stepped)."""
        pc = get_player_controller(self.g)
        c = self.step(self.g.cast(PCC))
        self.g.link(pc, "ReturnValue", c, "Object")
        return (c, as_pin(BP_PC))

    def game_mode(self):
        gm = self.g.call_static(GAMEPLAY, "GetGameMode", inputs=[Pin("WorldContextObject", OBJECT, hidden=True)],
                                outputs=[obj_pin("ReturnValue", "/Script/Engine.GameModeBase", "out")], pure=True)
        c = self.step(self.g.cast(GMC))
        self.g.link(gm, "ReturnValue", c, "Object")
        return (c, as_pin(BP_GM))

    def game_state(self):
        gs = self.g.call_static(GAMEPLAY, "GetGameState", inputs=[Pin("WorldContextObject", OBJECT, hidden=True)],
                                outputs=[obj_pin("ReturnValue", "/Script/Engine.GameStateBase", "out")], pure=True)
        c = self.step(self.g.cast(GSC))
        self.g.link(gs, "ReturnValue", c, "Object")
        return (c, as_pin(BP_GS))

    def racer(self, gm, pc):
        n = self.g.call_on(GMC, "FindRacer", inputs=[obj_pin("C", CONTROLLER)], outputs=[obj_pin("Racer", RC, "out")], pure=True)
        self.link(gm, n, "self")
        self.link(pc, n, "C")
        return (n, "Racer")

    def get(self, cls, var, cat, obj, sub=None, container=None):
        n = self.g.var_get_on(cls, var, cat, sub, container=container)
        self.link(obj, n, "self")
        return (n, var)

    def set(self, cls, var, cat, obj, value=None, default=None, sub=None):
        n = self.step(self.g.var_set_on(cls, var, cat, default=default, sub_object=sub))
        self.link(obj, n, "self")
        if value:
            self.link(value, n, var)
        return n

    def call(self, cls, fn, obj, inputs=None, outputs=None, pure=False, **defaults):
        n = self.g.call_on(cls, fn, inputs=inputs, outputs=outputs, pure=pure, **defaults)
        self.link(obj, n, "self")
        if not pure:
            self.step(n)
        return n

    def static(self, lib, fn, inputs=None, outputs=None, pure=False, **defaults):
        n = self.g.call_static(lib, fn, inputs=inputs, outputs=outputs, pure=pure, **defaults)
        if not pure:
            self.step(n)
        return n

    def item(self, arr, cls, index="0"):
        n = self.g.call_array(ARR, "Array_Get", Pin("e", OBJECT, sub_object=cls_ref(cls)), inputs=[Pin("Index", INT, default=index)],
                              outputs=[Pin("Item", OBJECT, "out", cls_ref(cls))])
        self.link(arr, n, "TargetArray")
        return (n, "Item")

    def length(self, arr, cls):
        n = self.g.call_array(ARR, "Array_Length", Pin("e", OBJECT, sub_object=cls_ref(cls)), outputs=[Pin("ReturnValue", INT, "out")])
        self.link(arr, n, "TargetArray")
        return (n, "ReturnValue")

    def loc(self, obj):
        n = self.g.call_on(ACTOR, "K2_GetActorLocation", outputs=[struct_pin("ReturnValue", VECTOR, "out")], pure=True)
        self.link(obj, n, "self")
        return (n, "ReturnValue")

    def distance(self, a, b):
        n = self.g.call_static(MATH, "Vector_Distance", inputs=[struct_pin("V1", VECTOR), struct_pin("V2", VECTOR)],
                               outputs=[Pin("ReturnValue", FLOAT, "out")], pure=True)
        self.link(a, n, "V1")
        self.link(b, n, "V2")
        return (n, "ReturnValue")

    def transform_loc(self, xf):
        n = self.g.call_static(MATH, "BreakTransform", inputs=[struct_pin("InTransform", TRANSFORM)],
                               outputs=[struct_pin("Location", VECTOR, "out"), struct_pin("Rotation", ROTATOR, "out"),
                                        struct_pin("Scale", VECTOR, "out")], pure=True)
        self.link(xf, n, "InTransform")
        return (n, "Location")

    def delay(self, seconds):
        self.static("KismetSystemLibrary", "Delay", inputs=[Pin("WorldContextObject", OBJECT, hidden=True),
                                                             Pin("Duration", FLOAT, default="%f" % seconds)])

    def damage(self, actor, amount, instigator=None):
        n = self.static(GAMEPLAY, "ApplyDamage", inputs=[obj_pin("DamagedActor", ACTOR), Pin("BaseDamage", FLOAT, default="%f" % amount),
                                                          obj_pin("EventInstigator", CONTROLLER), obj_pin("DamageCauser", ACTOR),
                                                          Pin("DamageTypeClass", "class", sub_object=cls_ref("/Script/Engine.DamageType"))],
                        outputs=[Pin("ReturnValue", FLOAT, "out")])
        self.link(actor, n, "DamagedActor")
        if instigator:
            self.link(instigator, n, "EventInstigator")
        return n

    def point_damage(self, actor, amount, bone):
        hit = self.g.call_static(GAMEPLAY, "MakeHitResult",
                                 inputs=[Pin("bBlockingHit", BOOL, default="true"), Pin("bInitialOverlap", BOOL, default="false"),
                                         Pin("Time", FLOAT, default="0.0"), Pin("Distance", FLOAT, default="0.0"),
                                         struct_pin("Location", VECTOR), struct_pin("ImpactPoint", VECTOR), struct_pin("Normal", VECTOR),
                                         struct_pin("ImpactNormal", VECTOR), obj_pin("PhysMat", "/Script/PhysicsCore.PhysicalMaterial"),
                                         obj_pin("HitActor", ACTOR), obj_pin("HitComponent", PRIMITIVE),
                                         Pin("HitBoneName", NAME, default=bone), Pin("HitItem", INT, default="0"),
                                         Pin("ElementIndex", INT, default="0"), Pin("FaceIndex", INT, default="0"),
                                         struct_pin("TraceStart", VECTOR), struct_pin("TraceEnd", VECTOR)],
                                 outputs=[struct_pin("ReturnValue", HIT_RESULT, "out")], pure=True)
        self.link(actor, hit, "HitActor")
        n = self.static(GAMEPLAY, "ApplyPointDamage",
                        inputs=[obj_pin("DamagedActor", ACTOR), Pin("BaseDamage", FLOAT, default="%f" % amount),
                                struct_pin("HitFromDirection", VECTOR, default="1,0,0"), struct_pin("HitInfo", HIT_RESULT),
                                obj_pin("EventInstigator", CONTROLLER), obj_pin("DamageCauser", ACTOR),
                                Pin("DamageTypeClass", "class", sub_object=cls_ref("/Script/Engine.DamageType"))],
                        outputs=[Pin("ReturnValue", FLOAT, "out")])
        self.link(actor, n, "DamagedActor")
        self.g.link(hit, "ReturnValue", n, "HitInfo")
        # HitFromDirection is a by-ref parameter: it needs a wired value, not a literal
        direction = self.g.call_static(MATH, "MakeVector", inputs=[Pin("X", FLOAT, default="1.0"), Pin("Y", FLOAT, default="0.0"),
                                                                    Pin("Z", FLOAT, default="0.0")],
                                       outputs=[struct_pin("ReturnValue", VECTOR, "out")], pure=True)
        self.g.link(direction, "ReturnValue", n, "HitFromDirection")
        return n

    # ---- asserts ----
    def true(self, cond, message):
        n = self.step(self.g.call_self_native(FT, "AssertTrue", inputs=[Pin("Condition", BOOL), Pin("Message", STRING, default=message)],
                                              outputs=[Pin("ReturnValue", BOOL, "out")]))
        self.link(cond, n, "Condition")

    def false(self, cond, message):
        n = self.step(self.g.call_self_native(FT, "AssertFalse", inputs=[Pin("Condition", BOOL), Pin("Message", STRING, default=message)],
                                              outputs=[Pin("ReturnValue", BOOL, "out")]))
        self.link(cond, n, "Condition")

    def eq_int(self, actual, expected, what):
        n = self.step(self.g.call_self_native(FT, "AssertEqual_Int", inputs=[Pin("Actual", INT), Pin("Expected", INT, default=str(expected)),
                                                                              Pin("What", STRING, default=what)],
                                              outputs=[Pin("ReturnValue", BOOL, "out")]))
        self.link(actual, n, "Actual")

    def eq_float(self, actual, expected, what, tolerance=0.01):
        n = self.step(self.g.call_self_native(FT, "AssertEqual_Float",
                                              inputs=[Pin("Actual", FLOAT), Pin("Expected", FLOAT, default="%f" % expected),
                                                      Pin("What", STRING, default=what), Pin("Tolerance", FLOAT, default="%f" % tolerance)],
                                              outputs=[Pin("ReturnValue", BOOL, "out")]))
        self.link(actual, n, "Actual")

    def less(self, a, b_value, what):
        n = self.g.call_static(MATH, "Less_FloatFloat", inputs=[Pin("A", FLOAT), Pin("B", FLOAT, default="%f" % b_value)],
                               outputs=[Pin("ReturnValue", BOOL, "out")], pure=True)
        self.link(a, n, "A")
        self.true((n, "ReturnValue"), what)

    def same(self, a, b, message):
        n = self.g.call_static(MATH, "EqualEqual_ObjectObject", inputs=[obj_pin("A", OBJ), obj_pin("B", OBJ)],
                               outputs=[Pin("ReturnValue", BOOL, "out")], pure=True)
        self.link(a, n, "A")
        self.link(b, n, "B")
        self.true((n, "ReturnValue"), message)

    def valid(self, obj, message):
        v = is_valid(self.g)
        self.link(obj, v, "Object")
        self.true((v, "ReturnValue"), message)

    def finish(self):
        self.step(self.g.call_self_native(FT, "FinishTest", inputs=[native_enum_pin("TestResult", RESULT_ENUM, "Succeeded"),
                                                                     Pin("Message", STRING, default="")]))
        return self.bp


# ---------- tests ----------
def tire(t: T, vehicle, index, field, cat):
    arr = t.get(VC, "Tires", STRUCT, vehicle, sub=struct_ref(TIRE), container="Array")
    get = t.g.call_array(ARR, "Array_Get", Pin("e", STRUCT, sub_object=struct_ref(TIRE)), inputs=[Pin("Index", INT, default=str(index))],
                         outputs=[Pin("Item", STRUCT, "out", struct_ref(TIRE))])
    t.link(arr, get, "TargetArray")
    br = t.g.break_struct(TIRE, [Pin(member(S_TIRE, "BoneName"), NAME), Pin(member(S_TIRE, "Health"), FLOAT),
                                 Pin(member(S_TIRE, "MaxHealth"), FLOAT), Pin(member(S_TIRE, "bBlown"), BOOL)])
    t.g.link(get, "Item", br, TIRE.rsplit(".", 1)[1])
    return (br, member(S_TIRE, field))


def spawn_vehicle(t: T, dx=0.0, dy=0.0):
    return t.spawn(VC, t.offset(t.self_loc(), dx, dy, -120.0))


def spawn_character(t: T, dx=0.0, dy=0.0):
    return t.spawn(CC, t.offset(t.self_loc(), dx, dy, -60.0))


def vehicle_tests():
    out = []
    t = T("FT_DFVehicle_TireDamageByBone", "A 10-point hit on the front-left wheel bone takes 10 from that tire only.")
    v = spawn_vehicle(t)
    t.delay(0.5)
    t.point_damage(v, 10, "Wheel_Front_Left")
    t.eq_float(tire(t, v, 0, "Health", FLOAT), 20.0, "front-left tire health")
    t.eq_float(t.get(VC, "Health", FLOAT, v), 100.0, "body health")
    out.append(t.finish())

    t = T("FT_DFVehicle_TireBlowsAndScalesThrottle", "30 damage blows a tire; one blown tire scales the throttle by 0.8.")
    v = spawn_vehicle(t)
    t.delay(0.5)
    t.point_damage(v, 30, "Wheel_Front_Left")
    t.true(tire(t, v, 0, "bBlown", BOOL), "front-left tire blown")
    cnt = t.g.call_on(VC, "GetBlownTireCount", outputs=[Pin("Count", INT, "out")], pure=True)
    t.link(v, cnt, "self")
    t.eq_int((cnt, "Count"), 1, "blown tire count")
    sc = t.g.call_on(VC, "GetThrottleScale", outputs=[Pin("Scale", FLOAT, "out")], pure=True)
    t.link(v, sc, "self")
    t.eq_float((sc, "Scale"), 0.8, "throttle scale", 0.001)
    out.append(t.finish())

    t = T("FT_DFVehicle_BodyDamageDestroysOnce", "100 body damage wrecks the car once; later damage is ignored (one death counted).")
    pc = t.player()
    gm = t.game_mode()
    t.call(GMC, "RestartRace", gm)  # deaths start at 0 (tests share one play session)
    v = spawn_vehicle(t)
    t.delay(0.5)
    t.set(VC, "LastDriver", OBJECT, v, value=pc, sub=cls_ref(CONTROLLER))
    t.damage(v, 100)
    t.true(t.get(VC, "bIsDestroyed", BOOL, v), "wrecked after 100 damage")
    t.eq_float(t.get(VC, "Health", FLOAT, v), 0.0, "health after 100 damage")
    t.damage(v, 50)
    t.eq_float(t.get(VC, "Health", FLOAT, v), 0.0, "health after further damage")
    t.eq_int(t.get(RC, "Deaths", INT, t.racer(gm, pc)), 1, "deaths counted for the wreck")
    out.append(t.finish())
    return out


def weapon_and_character_tests():
    out = []

    def fire(t, ch, v):
        weapon = t.get(CC, "Weapon", OBJECT, ch, sub=cls_ref(WC))
        origin = t.offset(t.loc(v), -400.0, 0.0, 80.0)
        n = t.call(WC, "Fire", weapon, inputs=[struct_pin("Origin", VECTOR), struct_pin("Direction", VECTOR, default="1,0,0")],
                   outputs=[Pin("bHit", BOOL, "out"), struct_pin("Hit", HIT_RESULT, "out")])
        t.link(origin, n, "Origin")
        return n

    t = T("FT_DFWeapon_HitscanDamagesVehicle", "The weapon's hitscan from 4 m behind a car hits its body for 20.")
    ch = spawn_character(t)
    v = spawn_vehicle(t, 400.0)
    t.delay(1.0)
    f = fire(t, ch, v)
    t.true((f, "bHit"), "the trace hit something")
    t.eq_float(t.get(VC, "Health", FLOAT, v), 80.0, "car body health after one shot")
    out.append(t.finish())

    t = T("FT_DFWeapon_RespectsCooldown", "A second shot in the same frame is refused by the cooldown.")
    ch = spawn_character(t)
    v = spawn_vehicle(t, 400.0)
    t.delay(1.0)
    fire(t, ch, v)
    f2 = fire(t, ch, v)
    t.false((f2, "bHit"), "second shot refused")
    t.eq_float(t.get(VC, "Health", FLOAT, v), 80.0, "car body health after two calls")
    out.append(t.finish())

    t = T("FT_DFCharacter_DiesAtZeroHealth", "100 damage kills the on-foot character.")
    ch = spawn_character(t)
    t.delay(0.3)
    t.damage(ch, 100)
    t.eq_float(t.get(CC, "Health", FLOAT, ch), 0.0, "character health")
    dead = t.g.call_on(CC, "IsDead", outputs=[Pin("ReturnValue", BOOL, "out")], pure=True)
    t.link(ch, dead, "self")
    t.true((dead, "ReturnValue"), "character is dead")
    out.append(t.finish())

    t = T("FT_DFCharacter_FindsNearestVehicle", "The nearest enterable car inside 3 m is found; none when all are farther.")
    ch = spawn_character(t)
    near = spawn_vehicle(t, 250.0)
    spawn_vehicle(t, -900.0)
    t.delay(1.0)
    n = t.g.call_on(CC, "FindNearestEnterableVehicle", outputs=[obj_pin("ReturnValue", VC, "out")])
    t.link(ch, n, "self")
    t.step(n)
    t.same((n, "ReturnValue"), near, "nearest car is the one 2.5 m away")
    mv = t.call(ACTOR, "K2_SetActorLocation", ch, inputs=[struct_pin("NewLocation", VECTOR), Pin("bSweep", BOOL, default="false"),
                                                          Pin("bTeleport", BOOL, default="true")],
                outputs=[struct_pin("SweepHitResult", HIT_RESULT, "out"), Pin("ReturnValue", BOOL, "out")])
    t.link(t.offset(t.self_loc(), 0.0, 3000.0, 0.0), mv, "NewLocation")
    t.delay(0.3)
    n2 = t.g.call_on(CC, "FindNearestEnterableVehicle", outputs=[obj_pin("ReturnValue", VC, "out")])
    t.link(ch, n2, "self")
    t.step(n2)
    v2 = is_valid(t.g)
    t.g.link(n2, "ReturnValue", v2, "Object")
    t.false((v2, "ReturnValue"), "no car within reach after moving away")
    out.append(t.finish())
    return out


def enter_exit_tests():
    out = []

    def setup(t):
        v = spawn_vehicle(t)
        ch = spawn_character(t, 0.0, -400.0)
        t.delay(1.0)
        e = t.call(VC, "EnterVehicle", v, inputs=[obj_pin("Character", CC)], outputs=[Pin("ReturnValue", BOOL, "out")])
        t.link(ch, e, "Character")
        return v, ch, e

    t = T("FT_DFEnterExit_RoundTrip", "Entering stows the character in the car; exiting puts it beside the car.")
    v, ch, e = setup(t)
    t.true((e, "ReturnValue"), "EnterVehicle succeeds")
    t.same(t.get(VC, "Occupant", OBJECT, v, sub=cls_ref(CC)), ch, "car occupant is the character")
    t.true(t.get(ACTOR, "bHidden", BOOL, ch), "stowed character is hidden")
    can = t.g.call_on(VC, "CanBeEntered", outputs=[Pin("ReturnValue", BOOL, "out")], pure=True)
    t.link(v, can, "self")
    t.false((can, "ReturnValue"), "an occupied car cannot be entered")
    x = t.call(VC, "ExitVehicle", v, outputs=[Pin("ReturnValue", BOOL, "out")])
    t.true((x, "ReturnValue"), "ExitVehicle succeeds")
    t.false(t.get(ACTOR, "bHidden", BOOL, ch), "character visible after exit")
    d = t.distance(t.loc(ch), t.loc(v))
    rng = t.g.call_static(MATH, "InRange_FloatFloat", inputs=[Pin("Value", FLOAT), Pin("Min", FLOAT, default="150.0"), Pin("Max", FLOAT, default="500.0"),
                                                                Pin("InclusiveMin", BOOL, default="true"), Pin("InclusiveMax", BOOL, default="true")],
                          outputs=[Pin("ReturnValue", BOOL, "out")], pure=True)
    t.link(d, rng, "Value")
    t.true((rng, "ReturnValue"), "character placed 1.5 to 5 m from the car")
    out.append(t.finish())

    t = T("FT_DFEnterExit_BlockedExitFails", "With the left, right and rear exit spots blocked, exiting fails and the character stays in.")
    v, ch, e = setup(t)
    for dx, dy in ((0.0, -220.0), (0.0, 220.0), (-350.0, 0.0)):
        cube = t.spawn("/Script/Engine.StaticMeshActor", t.offset(t.loc(v), dx, dy, 100.0))
        comp = t.get("/Script/Engine.StaticMeshActor", "StaticMeshComponent", OBJECT, cube, sub=cls_ref("/Script/Engine.StaticMeshComponent"))
        t.call("/Script/Engine.SceneComponent", "SetMobility", comp,
               inputs=[native_enum_pin("NewMobility", "/Script/Engine.EComponentMobility", "Movable")])
        sm = t.call("/Script/Engine.StaticMeshComponent", "SetStaticMesh", comp,
                    inputs=[Pin("NewMesh", OBJECT, sub_object=cls_ref("/Script/Engine.StaticMesh"), default_object="/Engine/BasicShapes/Cube.Cube")],
                    outputs=[Pin("ReturnValue", BOOL, "out")])
        sc = t.call(ACTOR, "SetActorScale3D", cube, inputs=[struct_pin("NewScale3D", VECTOR, default="2.5,2.5,2.5")])
    t.delay(0.2)
    x = t.call(VC, "ExitVehicle", v, outputs=[Pin("ReturnValue", BOOL, "out")])
    t.false((x, "ReturnValue"), "ExitVehicle refused")
    inv = t.g.call_on(CC, "IsInVehicle", outputs=[Pin("ReturnValue", BOOL, "out")], pure=True)
    t.link(ch, inv, "self")
    t.true((inv, "ReturnValue"), "character still in the car")
    out.append(t.finish())

    t = T("FT_DFEnterExit_RefusedWhileMoving", "Exiting a car moving faster than 10 km/h is refused.")
    v, ch, e = setup(t)
    mesh = t.get(VC, "Mesh", OBJECT, v, sub=cls_ref("/Script/Engine.SkeletalMeshComponent"))
    t.call(PRIMITIVE, "SetPhysicsLinearVelocity", mesh, inputs=[struct_pin("NewVel", VECTOR, default="1500,0,0"),
                                                               Pin("bAddToCurrent", BOOL, default="false"), Pin("BoneName", NAME, default="None")])
    t.delay(0.15)
    can = t.g.call_on(VC, "CanExit", outputs=[Pin("ReturnValue", BOOL, "out")], pure=True)
    t.link(v, can, "self")
    t.false((can, "ReturnValue"), "CanExit false while moving")
    x = t.call(VC, "ExitVehicle", v, outputs=[Pin("ReturnValue", BOOL, "out")])
    t.false((x, "ReturnValue"), "ExitVehicle refused while moving")
    out.append(t.finish())

    t = T("FT_DFEnterExit_EnterRefusedWhenOccupied", "A second character cannot enter an occupied car.")
    v, ch, e = setup(t)
    ch2 = spawn_character(t, 0.0, 400.0)
    t.delay(0.3)
    e2 = t.call(VC, "EnterVehicle", v, inputs=[obj_pin("Character", CC)], outputs=[Pin("ReturnValue", BOOL, "out")])
    t.link(ch2, e2, "Character")
    t.false((e2, "ReturnValue"), "second EnterVehicle refused")
    out.append(t.finish())
    return out


def track_tests():
    out = []

    def main_track(t):
        # Phase 3 adds a shortcut track actor, so the main loop is the one the GameMode flagged, not actor [0]
        gm = t.game_mode()
        return t.get(GMC, "MainTrack", OBJECT, gm, sub=cls_ref(TC))

    t = T("FT_DFTrack_ClosedLoopGeneratesSegments", "The test track's loop is about 491 m and is laid with road pieces only (no barriers).")
    tr = main_track(t)
    seg = t.g.call_on(TC, "GetSegmentCount", outputs=[Pin("Count", INT, "out")], pure=True)
    t.link(tr, seg, "self")
    gen_ = t.g.call_on(TC, "GetGeneratedMeshCount", outputs=[Pin("Count", INT, "out")], pure=True)
    t.link(tr, gen_, "self")
    pos = t.g.call_static(MATH, "Greater_IntInt", inputs=[Pin("A", INT), Pin("B", INT, default="0")], outputs=[Pin("ReturnValue", BOOL, "out")], pure=True)
    t.g.link(seg, "Count", pos, "A")
    t.true((pos, "ReturnValue"), "road pieces generated")
    eq = t.g.call_static(MATH, "EqualEqual_IntInt", inputs=[Pin("A", INT), Pin("B", INT)], outputs=[Pin("ReturnValue", BOOL, "out")], pure=True)
    t.g.link(seg, "Count", eq, "A")
    t.g.link(gen_, "Count", eq, "B")
    t.true((eq, "ReturnValue"), "one mesh per road piece (no barriers)")
    ln = t.g.call_on(TC, "GetTrackLength", outputs=[Pin("Length", FLOAT, "out")], pure=True)
    t.link(tr, ln, "self")
    t.eq_float((ln, "Length"), 49126.0, "track length (cm)", 100.0)
    out.append(t.finish())

    t = T("FT_DFTrack_LateralDistance", "A point 5 m beside the road centre is 5 m off the line and on the road; 10 m is off the road.")
    tr = main_track(t)
    spline = t.get(TC, "Spline", OBJECT, tr, sub=cls_ref(SPLINE_COMP))

    def beside(metres):
        loc = t.g.call_on(SPLINE_COMP, "GetLocationAtDistanceAlongSpline", inputs=[Pin("Distance", FLOAT, default="1000.0"), native_enum_pin("CoordinateSpace", SPACE, "World")],
                          outputs=[struct_pin("ReturnValue", VECTOR, "out")], pure=True)
        t.link(spline, loc, "self")
        right = t.g.call_on(SPLINE_COMP, "GetRightVectorAtDistanceAlongSpline", inputs=[Pin("Distance", FLOAT, default="1000.0"), native_enum_pin("CoordinateSpace", SPACE, "World")],
                            outputs=[struct_pin("ReturnValue", VECTOR, "out")], pure=True)
        t.link(spline, right, "self")
        scaled = t.g.call_static(MATH, "Multiply_VectorFloat", inputs=[struct_pin("A", VECTOR), Pin("B", FLOAT, default="%f" % (metres * 100))],
                                 outputs=[struct_pin("ReturnValue", VECTOR, "out")], pure=True)
        t.g.link(right, "ReturnValue", scaled, "A")
        p = t.g.call_static(MATH, "Add_VectorVector", inputs=[struct_pin("A", VECTOR), struct_pin("B", VECTOR)],
                            outputs=[struct_pin("ReturnValue", VECTOR, "out")], pure=True)
        t.g.link(loc, "ReturnValue", p, "A")
        t.g.link(scaled, "ReturnValue", p, "B")
        return (p, "ReturnValue")

    p5 = beside(5)
    lat = t.g.call_on(TC, "GetLateralDistanceFromTrack", inputs=[struct_pin("WorldLocation", VECTOR)], outputs=[Pin("Distance", FLOAT, "out")], pure=True)
    t.link(tr, lat, "self")
    t.link(p5, lat, "WorldLocation")
    t.eq_float((lat, "Distance"), 500.0, "lateral distance 5 m beside the line", 5.0)
    on5 = t.g.call_on(TC, "IsOnRoad", inputs=[struct_pin("WorldLocation", VECTOR)], outputs=[Pin("ReturnValue", BOOL, "out")], pure=True)
    t.link(tr, on5, "self")
    t.link(p5, on5, "WorldLocation")
    t.true((on5, "ReturnValue"), "5 m beside the line is on the 14 m road")
    on10 = t.g.call_on(TC, "IsOnRoad", inputs=[struct_pin("WorldLocation", VECTOR)], outputs=[Pin("ReturnValue", BOOL, "out")], pure=True)
    t.link(tr, on10, "self")
    t.link(beside(10), on10, "WorldLocation")
    t.false((on10, "ReturnValue"), "10 m beside the line is off the road")
    out.append(t.finish())
    return out


def race_context(t: T):
    """Player, GameMode, GameState, racer and gates, after RestartRace (all tests share one play session)."""
    pc = t.player()
    gm = t.game_mode()
    t.call(GMC, "RestartRace", gm)
    t.delay(0.5)
    gs = t.game_state()
    racer = t.racer(gm, pc)
    gates = t.get(GMC, "Checkpoints", OBJECT, gm, sub=cls_ref(CPC), container="Array")
    return pc, gm, gs, racer, gates


def notify(t: T, gm, pc, gate):
    n = t.call(GMC, "NotifyCheckpointReached", gm, inputs=[obj_pin("Racer", CONTROLLER), obj_pin("Checkpoint", CPC)],
               outputs=[Pin("ReturnValue", BOOL, "out")])
    t.link(pc, n, "Racer")
    t.link(gate, n, "Checkpoint")
    return (n, "ReturnValue")


def checkpoint_and_race_tests():
    out = []

    t = T("FT_DFRace_PlayerStartsInCar", "The player starts in a BP_DFVehicle with the on-foot character stowed in it; four gates, clock running.")
    pc, gm, gs, racer, gates = race_context(t)
    pawn = t.g.call_on(CONTROLLER, "K2_GetPawn", outputs=[obj_pin("ReturnValue", PAWN, "out")], pure=True)
    t.link(pc, pawn, "self")
    car = t.step(t.g.cast(VC))
    t.g.link(pawn, "ReturnValue", car, "Object")
    ch = t.get(PCC, "OnFootCharacter", OBJECT, pc, sub=cls_ref(CC))
    t.same(t.get(VC, "Occupant", OBJECT, (car, as_pin(BP_VEHICLE)), sub=cls_ref(CC)), ch, "the player's car holds the on-foot character")
    t.same(t.get(CC, "OwningController", OBJECT, ch, sub=cls_ref(CONTROLLER)), pc, "the character knows its controller")
    t.true(t.get(GSC, "bRaceActive", BOOL, gs), "race active")
    t.eq_int(t.length(gates, CPC), 4, "registered gates")
    t.less(t.get(GSC, "RemainingTime", FLOAT, gs), 120.01, "clock at or below the 120 s limit")
    out.append(t.finish())

    t = T("FT_DFCheckpoint_OnlyTheNextGateCounts", "Only the next gate credits: skipping or repeating a gate gives nothing; a valid gate gives +8 s.")
    pc, gm, gs, racer, gates = race_context(t)
    t.false(notify(t, gm, pc, t.item(gates, CPC, "2")), "skipping to gate 2 is refused")
    t.eq_int(t.get(RC, "NextCheckpointIndex", INT, racer), 1, "next gate still 1")
    before = t.step(t.g.var_set_on(GSC, "RemainingTime", FLOAT, default="50.0"))
    t.link(gs, before, "self")
    t.true(notify(t, gm, pc, t.item(gates, CPC, "1")), "gate 1 credits")
    t.eq_int(t.get(RC, "NextCheckpointIndex", INT, racer), 2, "next gate is 2")
    t.eq_float(t.get(GSC, "RemainingTime", FLOAT, gs), 58.0, "clock gained 8 s", 0.05)
    t.false(notify(t, gm, pc, t.item(gates, CPC, "1")), "gate 1 again is refused")
    out.append(t.finish())

    t = T("FT_DFCheckpoint_LapResetsAndScores", "Crossing the start line when it is next completes a lap: +1 lap, +100, next gate 1, +8 s.")
    pc, gm, gs, racer, gates = race_context(t)
    t.set(RC, "NextCheckpointIndex", INT, racer, default="0")
    st = t.step(t.g.var_set_on(GSC, "RemainingTime", FLOAT, default="50.0"))
    t.link(gs, st, "self")
    t.true(notify(t, gm, pc, t.item(gates, CPC, "0")), "start line credits")
    t.eq_int(t.get(RC, "LapsCompleted", INT, racer), 1, "laps")
    t.eq_int(t.get(RC, "Score", INT, racer), 100, "score")
    t.eq_int(t.get(RC, "NextCheckpointIndex", INT, racer), 1, "next gate reset to 1")
    t.eq_float(t.get(GSC, "RemainingTime", FLOAT, gs), 58.0, "clock gained 8 s", 0.05)
    out.append(t.finish())

    def player_car(t, pc):
        return t.get(PCC, "CurrentVehicle", OBJECT, pc, sub=cls_ref(VC))

    def pawn_car(t, pc):
        pawn = t.g.call_on(CONTROLLER, "K2_GetPawn", outputs=[obj_pin("ReturnValue", PAWN, "out")], pure=True)
        t.link(pc, pawn, "self")
        c = t.step(t.g.cast(VC))
        t.g.link(pawn, "ReturnValue", c, "Object")
        return (c, as_pin(BP_VEHICLE))

    def gate_respawn_loc(t, gate):
        xf = t.g.call_on(CPC, "GetRespawnTransform", outputs=[struct_pin("Transform", TRANSFORM, "out")], pure=True)
        t.link(gate, xf, "self")
        return t.transform_loc((xf, "Transform"))

    t = T("FT_DFRespawn_WreckRespawnsAtLastGate", "A wrecked car costs a life; 2 s later the player is in a fresh car at the last gate.")
    pc, gm, gs, racer, gates = race_context(t)
    g1 = t.item(gates, CPC, "1")
    t.set(RC, "LastCheckpoint", OBJECT, racer, value=g1, sub=cls_ref(CPC))
    t.damage(player_car(t, pc), 100)
    t.delay(2.5)
    t.eq_int(t.get(RC, "Deaths", INT, racer), 1, "deaths")
    car = pawn_car(t, pc)
    t.false(t.get(VC, "bIsDestroyed", BOOL, car), "the new car is intact")
    t.less(t.distance(t.loc(car), gate_respawn_loc(t, t.item(gates, CPC, "1"))), 300.0, "new car within 3 m of gate 1")
    t.same(t.get(VC, "Occupant", OBJECT, car, sub=cls_ref(CC)), t.get(PCC, "OnFootCharacter", OBJECT, pc, sub=cls_ref(CC)), "character inside the new car")
    out.append(t.finish())

    t = T("FT_DFRespawn_WreckedParkedCarPullsCharacterIn", "Wrecking the parked car while on foot costs a life and puts the character in a fresh car.")
    pc, gm, gs, racer, gates = race_context(t)
    car0 = player_car(t, pc)
    x = t.call(VC, "ExitVehicle", car0, outputs=[Pin("ReturnValue", BOOL, "out")])
    t.true((x, "ReturnValue"), "got out of the parked car")
    last = t.get(PCC, "LastVehicle", OBJECT, pc, sub=cls_ref(VC))
    t.damage(last, 100)
    t.delay(2.5)
    t.eq_int(t.get(RC, "Deaths", INT, racer), 1, "deaths")
    car = pawn_car(t, pc)
    t.false(t.get(VC, "bIsDestroyed", BOOL, car), "the player now drives an intact car")
    inv = t.g.call_on(CC, "IsInVehicle", outputs=[Pin("ReturnValue", BOOL, "out")], pure=True)
    t.link(t.get(PCC, "OnFootCharacter", OBJECT, pc, sub=cls_ref(CC)), inv, "self")
    t.true((inv, "ReturnValue"), "character is in a car")
    out.append(t.finish())

    t = T("FT_DFRespawn_DeathLimitEndsRace", "The third death ends the race with game over and no respawn.")
    pc, gm, gs, racer, gates = race_context(t)
    t.set(RC, "Deaths", INT, racer, default="2")
    t.damage(player_car(t, pc), 100)
    t.false(t.get(GSC, "bRaceActive", BOOL, gs), "race over")
    res = t.get(GSC, "Result", STRUCT, gs, sub=struct_ref(RESULT))
    br = t.g.break_struct(RESULT, [enum_pin(member(S_RESULT, "Reason"), "/Game/DeadFire/Data/E_DFRaceEndReason", direction="out")])
    t.link(res, br, RESULT.rsplit(".", 1)[1])
    as_int = t.g.call_static(MATH, "Conv_ByteToInt", inputs=[Pin("InByte", "byte")], outputs=[Pin("ReturnValue", INT, "out")], pure=True)
    t.g.link(br, member(S_RESULT, "Reason"), as_int, "InByte")
    t.eq_int((as_int, "ReturnValue"), 2, "end reason DeathLimit")
    t.delay(2.5)
    car = pawn_car(t, pc)
    t.true(t.get(VC, "bIsDestroyed", BOOL, car), "the player is still in the wreck (no respawn)")
    out.append(t.finish())

    t = T("FT_DFRespawn_NothingAfterRaceEnd", "A respawn pending when the race ends never happens.")
    pc, gm, gs, racer, gates = race_context(t)
    t.damage(player_car(t, pc), 100)
    end = t.call(GMC, "EndRace", gm, inputs=[enum_pin("Reason", "/Game/DeadFire/Data/E_DFRaceEndReason", default=1)])
    t.delay(2.5)
    car = pawn_car(t, pc)
    t.true(t.get(VC, "bIsDestroyed", BOOL, car), "still in the wreck after the race ended")
    t.eq_int(t.get(RC, "Deaths", INT, racer), 1, "deaths")
    out.append(t.finish())

    t = T("FT_DFOffTrack_RespawnsWithoutDeath", "Five seconds more than 5 m off every road puts the car back at the last gate without costing a life.")
    pc, gm, gs, racer, gates = race_context(t)
    car = player_car(t, pc)
    tp = t.call(VC, "TeleportAndStop", car, inputs=[struct_pin("NewTransform", TRANSFORM)])
    t.link(t.transform(t.offset(t.loc(car), 0.0, -5000.0, 100.0)), tp, "NewTransform")
    t.delay(5.8)
    t.eq_int(t.get(RC, "Deaths", INT, racer), 0, "deaths")
    t.less(t.distance(t.loc(player_car(t, pc)), gate_respawn_loc(t, t.item(gates, CPC, "0"))), 300.0, "car back within 3 m of the start gate")
    out.append(t.finish())

    t = T("FT_DFRaceEnd_TimeUpSetsResult", "When the clock runs out with 300 points the result is RACE COMPLETE material: time up, passed, 1st of 1.")
    pc, gm, gs, racer, gates = race_context(t)
    t.set(RC, "Score", INT, racer, default="300")
    t.set(GSC, "RemainingTime", FLOAT, gs, default="0.01")
    t.delay(1.0)  # headless frames are long: give the GameMode at least one tick after the clock change
    res = t.get(GSC, "Result", STRUCT, gs, sub=struct_ref(RESULT))
    br = t.g.break_struct(RESULT, [enum_pin(member(S_RESULT, "Reason"), "/Game/DeadFire/Data/E_DFRaceEndReason", direction="out"),
                                   Pin(member(S_RESULT, "bPassed"), BOOL), Pin(member(S_RESULT, "Rank"), INT), Pin(member(S_RESULT, "RacerCount"), INT)])
    t.link(res, br, RESULT.rsplit(".", 1)[1])
    as_int = t.g.call_static(MATH, "Conv_ByteToInt", inputs=[Pin("InByte", "byte")], outputs=[Pin("ReturnValue", INT, "out")], pure=True)
    t.g.link(br, member(S_RESULT, "Reason"), as_int, "InByte")
    t.eq_int((as_int, "ReturnValue"), 1, "end reason TimeUp")
    t.true((br, member(S_RESULT, "bPassed")), "passed with 300 points")
    t.eq_int((br, member(S_RESULT, "Rank")), 1, "rank")
    t.eq_int((br, member(S_RESULT, "RacerCount")), 1, "racer count")
    out.append(t.finish())
    return out


def hud_tests():
    t = T("FT_DFHUD_SummaryShownAtRaceEnd", "At race end the race HUD leaves the screen and the summary shows TIME UP; RestartRace brings the HUD back.")
    pc, gm, gs, racer, gates = race_context(t)
    t.call(GMC, "EndRace", gm, inputs=[enum_pin("Reason", "/Game/DeadFire/Data/E_DFRaceEndReason", default=1)])
    t.delay(0.3)
    WSUM, WHUD = gen("/Game/DeadFire/UI/WBP_DFRaceSummary"), gen("/Game/DeadFire/UI/WBP_DFRaceHUD")

    def widgets(cls, top_level):
        n = t.static("WidgetBlueprintLibrary", "GetAllWidgetsOfClass",
                     inputs=[Pin("WorldContextObject", OBJECT, hidden=True),
                             Pin("WidgetClass", "class", sub_object=cls_ref("/Script/UMG.UserWidget"), default_object=cls),
                             Pin("TopLevelOnly", BOOL, default="true" if top_level else "false")],
                     outputs=[Pin("FoundWidgets", OBJECT, "out", cls_ref(cls), container="Array")], module="UMG")
        return (n, "FoundWidgets")

    summaries = widgets(WSUM, True)
    t.eq_int(t.length(summaries, WSUM), 1, "summary widgets on screen")
    title = t.get(WSUM, "TitleText", OBJECT, t.item(summaries, WSUM), sub=cls_ref("/Script/UMG.TextBlock"))
    txt = t.g.call_on("/Script/UMG.TextBlock", "GetText", outputs=[Pin("ReturnValue", "text", "out")], pure=True)
    t.link(title, txt, "self")
    s = t.g.call_static("KismetTextLibrary", "Conv_TextToString", inputs=[Pin("InText", "text")], outputs=[Pin("ReturnValue", STRING, "out")], pure=True)
    t.g.link(txt, "ReturnValue", s, "InText")
    eq = t.g.call_static("KismetStringLibrary", "EqualEqual_StrStr", inputs=[Pin("A", STRING), Pin("B", STRING, default="TIME UP")],
                         outputs=[Pin("ReturnValue", BOOL, "out")], pure=True)
    t.g.link(s, "ReturnValue", eq, "A")
    t.true((eq, "ReturnValue"), "summary title reads TIME UP")
    t.eq_int(t.length(widgets(WHUD, True), WHUD), 0, "race HUD widgets on screen at race end")
    t.call(GMC, "RestartRace", gm)
    t.delay(0.3)
    t.eq_int(t.length(widgets(WHUD, True), WHUD), 1, "race HUD back after restart")
    t.eq_int(t.length(widgets(WSUM, True), WSUM), 0, "summary gone after restart")
    return [t.finish()]


def screenshot_test():
    """Not an assertion test: captures the race HUD, the on-foot view and the summary (Saved/Screenshots/Windows) when
    run in a rendering editor; headless runs produce black images. Sorted last (ZZ) so it runs after the others."""
    t = T("FT_DFZZ_Screenshots", "Captures race HUD, on-foot and summary screenshots (run in the editor for real images).")
    pc, gm, gs, racer, gates = race_context(t)
    from df import E_ITEM_TYPE, ITEM_BOMB, ITEM_SHIELD  # Phase 3: two items in the inventory so the HUD row shows
    for item in (ITEM_SHIELD, ITEM_BOMB):
        gi = t.call(GMC, "GrantItem", gm, inputs=[obj_pin("C", CONTROLLER), enum_pin("Type", E_ITEM_TYPE, default=item), Pin("Charges", INT, default="1")],
                    outputs=[Pin("ReturnValue", BOOL, "out")])
        t.link(pc, gi, "C")

    def shot():
        t.static("KismetSystemLibrary", "ExecuteConsoleCommand",
                 inputs=[Pin("WorldContextObject", OBJECT, hidden=True), Pin("Command", STRING, default="shot showui"),
                         obj_pin("SpecificPlayer", "/Script/Engine.PlayerController")])
        t.delay(1.0)

    # Phase 4: three NPCs on the grid behind the player (POS 1 / 4 on the line), then driving past into the chase camera's view
    t.call(GMC, "SpawnNPCs", gm, inputs=[Pin("Count", INT, default="3")])
    t.delay(1.0)
    shot()
    t.delay(4.0)
    shot()
    car = t.get(PCC, "CurrentVehicle", OBJECT, pc, sub=cls_ref(VC))
    t.call(VC, "ExitVehicle", car, outputs=[Pin("ReturnValue", BOOL, "out")])
    t.delay(1.0)
    shot()
    # Phase 5: a passed race in first place on fresh progress, so the summary shows the unlock line and NEXT (reset again after)
    gi0 = t.g.call_static(GAMEPLAY, "GetGameInstance", inputs=[Pin("WorldContextObject", OBJECT, hidden=True)],
                          outputs=[obj_pin("ReturnValue", "/Script/Engine.GameInstance", "out")], pure=True)
    gic0 = t.step(t.g.cast(gen("/Game/DeadFire/Blueprints/BP_DFGameInstance")))
    t.g.link(gi0, "ReturnValue", gic0, "Object")
    rp0 = t.g.call_on(gen("/Game/DeadFire/Blueprints/BP_DFGameInstance"), "ResetProgress")
    t.link((gic0, as_pin("/Game/DeadFire/Blueprints/BP_DFGameInstance")), rp0, "self")
    t.step(rp0)
    t.set(RC, "Score", INT, racer, default="350")
    t.call(GMC, "EndRace", gm, inputs=[enum_pin("Reason", "/Game/DeadFire/Data/E_DFRaceEndReason", default=1)])
    t.delay(0.5)
    shot()
    t.call(GMC, "DespawnNPCs", gm)
    t.call(GMC, "RestartRace", gm)
    gi_ = t.g.call_static(GAMEPLAY, "GetGameInstance", inputs=[Pin("WorldContextObject", OBJECT, hidden=True)],
                          outputs=[obj_pin("ReturnValue", "/Script/Engine.GameInstance", "out")], pure=True)
    gic = t.step(t.g.cast(gen("/Game/DeadFire/Blueprints/BP_DFGameInstance")))
    t.g.link(gi_, "ReturnValue", gic, "Object")
    rp = t.g.call_on(gen("/Game/DeadFire/Blueprints/BP_DFGameInstance"), "ResetProgress")
    t.link((gic, as_pin("/Game/DeadFire/Blueprints/BP_DFGameInstance")), rp, "self")
    t.step(rp)
    # Phase 7 Task 17 (spec §7.4, §7.5): the item looks after the restart (the player back in the car): a crate from the road at
    # 40 m and close up, a bomb, the shield and the boost (shots.item_look_shots; imported here, as shots.py imports this module)
    from shots import item_look_shots
    item_look_shots(t, pc, gm, shot)
    return [t.finish()]


def build():
    return (vehicle_tests() + weapon_and_character_tests() + enter_exit_tests() + track_tests() + checkpoint_and_race_tests()
            + hud_tests() + screenshot_test())


if __name__ == "__main__":
    for b in build():
        print(b.write(OUT))
