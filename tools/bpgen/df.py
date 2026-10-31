"""Dead Fire shared names and node recipes for the generator modules in graphs/."""
import os
from typing import Optional

from bpgen import (BOOL, BYTE, CLASS, EXEC, FLOAT, INT, NAME, OBJECT, STRING, STRUCT, TEXT, WILDCARD,  # noqa: F401
                   Blueprint, Graph, Node, Pin, bp_class, cls_ref, enum_ref, struct_ref)

OUT = os.path.join(os.path.dirname(__file__), "..", "..", "comp4900sef", "Script", "paste")

# ---- asset paths ----
BPS = "/Game/DeadFire/Blueprints"
COMPS = "/Game/DeadFire/Components"
DATA = "/Game/DeadFire/Data"
UI = "/Game/DeadFire/UI"
TESTS = "/Game/DeadFire/Tests"

SEDAN = "/Game/VehicleBP/Sedan/Sedan"
TPC = "/Game/ThirdPersonBP/Blueprints/ThirdPersonCharacter"

BP_VEHICLE = BPS + "/BP_DFVehicle"
BP_CHARACTER = BPS + "/BP_DFCharacter"
BP_PC = BPS + "/BP_DFPlayerController"
BP_GM = BPS + "/BP_DFRaceGameMode"
BP_GS = BPS + "/BP_DFRaceGameState"
BP_HUD = BPS + "/BP_DFHUD"
BP_TRACK = BPS + "/BP_DFTrackSpline"
BP_CHECKPOINT = BPS + "/BP_DFCheckpoint"
BPC_WEAPON = COMPS + "/BPC_DFWeapon"
BPC_RACER = COMPS + "/BPC_DFRacer"
WBP_HUD = UI + "/WBP_DFRaceHUD"
WBP_SUMMARY = UI + "/WBP_DFRaceSummary"
E_END_REASON = DATA + "/E_DFRaceEndReason"
S_TIRE = DATA + "/S_DFTireState"
S_RESULT = DATA + "/S_DFRaceResult"


def gen(asset: str) -> str:
    """Generated-class path of a Blueprint asset (for object:/class: type specs and cls_ref)."""
    return bp_class(asset)


def obj_spec(asset: str) -> str:
    return "object:" + gen(asset)


def class_spec(asset: str) -> str:
    return "class:" + gen(asset)


def struct_spec(asset: str) -> str:
    return "struct:%s.%s" % (asset, asset.rsplit("/", 1)[1])


def enum_spec(asset: str) -> str:
    return "enum:%s.%s" % (asset, asset.rsplit("/", 1)[1])


def struct_path(asset: str) -> str:
    return "%s.%s" % (asset, asset.rsplit("/", 1)[1])


def member(asset: str, name: str) -> str:
    """Pin name of a user-defined struct member; the runner substitutes the GUID-suffixed property name."""
    return "{{%s.%s}}" % (asset, name)


def enum_value(index: int) -> str:
    """Internal name of the index-th value of a user-defined enum (pin default text)."""
    return "NewEnumerator%d" % index


def enum_pin(name: str, asset: str, direction: str = "in", default: Optional[int] = None) -> Pin:
    return Pin(name, BYTE, direction, enum_ref(struct_path(asset)),
               default=None if default is None else enum_value(default))


# ---- engine type references used in pins ----
ACTOR = "/Script/Engine.Actor"
PAWN = "/Script/Engine.Pawn"
CONTROLLER = "/Script/Engine.Controller"
PLAYER_CONTROLLER = "/Script/Engine.PlayerController"
GAME_MODE_BASE = "/Script/Engine.GameModeBase"
GAME_STATE_BASE = "/Script/Engine.GameStateBase"
PRIMITIVE = "/Script/Engine.PrimitiveComponent"
SCENE_COMP = "/Script/Engine.SceneComponent"
SKEL_MESH_COMP = "/Script/Engine.SkeletalMeshComponent"
STATIC_MESH_COMP = "/Script/Engine.StaticMeshComponent"
SPLINE_COMP = "/Script/Engine.SplineComponent"
SPLINE_MESH_COMP = "/Script/Engine.SplineMeshComponent"
BOX_COMP = "/Script/Engine.BoxComponent"
SPHERE_COMP = "/Script/Engine.SphereComponent"
CHAR_MOVE = "/Script/Engine.CharacterMovementComponent"
WHEELED_MOVE = "/Script/PhysXVehicles.WheeledVehicleMovementComponent"
VECTOR = "/Script/CoreUObject.Vector"
ROTATOR = "/Script/CoreUObject.Rotator"
TRANSFORM = "/Script/CoreUObject.Transform"
LINEAR_COLOR = "/Script/CoreUObject.LinearColor"
HIT_RESULT = "/Script/Engine.HitResult"
DAMAGE_TYPE = "/Script/Engine.DamageType"
MATH = "KismetMathLibrary"
SYS = "KismetSystemLibrary"
GAMEPLAY = "GameplayStatics"
ARRAY = "KismetArrayLibrary"


def native_enum_pin(name: str, enum_path: str, default: Optional[str] = None, direction: str = "in") -> Pin:
    """Pin of a native enum, e.g. native_enum_pin('CoordinateSpace', '/Script/Engine.ESplineCoordinateSpace', 'World')."""
    return Pin(name, BYTE, direction, "Enum'\"%s\"'" % enum_path, default=default)


SPACE = "/Script/Engine.ESplineCoordinateSpace"


def obj_pin(name: str, class_path: str, direction: str = "in", hidden: bool = False) -> Pin:
    return Pin(name, OBJECT, direction, cls_ref(class_path), hidden=hidden)


def struct_pin(name: str, struct: str, direction: str = "in", default=None) -> Pin:
    return Pin(name, STRUCT, direction, struct_ref(struct), default=default)


def vec(x=0.0, y=0.0, z=0.0) -> str:
    return "%f,%f,%f" % (x, y, z)


# ---- common recipes ----
def print_string(g: Graph, text: str, col=None, row=None, duration="2.000000") -> Node:
    return g.call_static(SYS, "PrintString",
                         inputs=[Pin("WorldContextObject", OBJECT, hidden=True), Pin("InString", STRING),
                                 Pin("bPrintToScreen", BOOL, default="true"), Pin("bPrintToLog", BOOL, default="true"),
                                 struct_pin("TextColor", LINEAR_COLOR, default="(R=0.000000,G=0.660000,B=1.000000,A=1.000000)"),
                                 Pin("Duration", FLOAT, default=duration)],
                         InString=text, col=col, row=row)


def log_line(g: Graph, *parts) -> Node:
    """Impure PrintString to the output log only ("DF: ..." lines for debugging race flow). parts are literal strings
    or (node, pin) string sources, concatenated in order. Returns the PrintString node (exec in/out)."""
    acc = None
    for part in parts:
        if isinstance(part, str):
            src = None
        else:
            src = part
        n = g.call_static("KismetStringLibrary", "Concat_StrStr", inputs=[Pin("A", STRING), Pin("B", STRING, default=part if src is None else None)],
                          outputs=[Pin("ReturnValue", STRING, "out")], pure=True)
        if acc is not None:
            g.link(acc, "ReturnValue", n, "A")
        else:
            n.pins[0].default = "DF: "
        if src is not None:
            g.link(src[0], src[1], n, "B")
        acc = n
    p = g.call_static(SYS, "PrintString",
                      inputs=[Pin("WorldContextObject", OBJECT, hidden=True), Pin("InString", STRING),
                              Pin("bPrintToScreen", BOOL, default="false"), Pin("bPrintToLog", BOOL, default="true"),
                              struct_pin("TextColor", LINEAR_COLOR, default="(R=0.000000,G=0.660000,B=1.000000,A=1.000000)"),
                              Pin("Duration", FLOAT, default="0.0")])
    g.link(acc, "ReturnValue", p, "InString")
    return p


def name_of(g: Graph, obj_src) -> tuple:
    n = g.call_static(SYS, "GetDisplayName", inputs=[obj_pin("Object", "/Script/CoreUObject.Object")],
                      outputs=[Pin("ReturnValue", STRING, "out")], pure=True)
    g.link(obj_src[0], obj_src[1], n, "Object")
    return (n, "ReturnValue")


def int_str(g: Graph, src) -> tuple:
    n = g.call_static("KismetStringLibrary", "Conv_IntToString", inputs=[Pin("InInt", INT)], outputs=[Pin("ReturnValue", STRING, "out")], pure=True)
    g.link(src[0], src[1], n, "InInt")
    return (n, "ReturnValue")


def math2(g: Graph, fn: str, cat: str, a=None, b=None, col=None, row=None, out_cat=None) -> Node:
    """Pure KismetMathLibrary binary op, e.g. math2(g, 'Multiply_FloatFloat', FLOAT, b='2.0')."""
    return g.call_static(MATH, fn, inputs=[Pin("A", cat, default=a), Pin("B", cat, default=b)],
                         outputs=[Pin("ReturnValue", out_cat or cat, "out")], pure=True, col=col, row=row)


def compare(g: Graph, fn: str, cat: str, a=None, b=None, col=None, row=None) -> Node:
    return math2(g, fn, cat, a, b, col, row, out_cat=BOOL)


def not_bool(g: Graph, col=None, row=None) -> Node:
    return g.call_static(MATH, "Not_PreBool", inputs=[Pin("A", BOOL)], outputs=[Pin("ReturnValue", BOOL, "out")],
                         pure=True, col=col, row=row)


def and_bool(g: Graph, col=None, row=None) -> Node:
    return math2(g, "BooleanAND", BOOL, col=col, row=row)


def or_bool(g: Graph, col=None, row=None) -> Node:
    return math2(g, "BooleanOR", BOOL, col=col, row=row)


def is_valid(g: Graph, col=None, row=None) -> Node:
    """Pure IsValid(Object) -> bool."""
    return g.call_static(SYS, "IsValid", inputs=[obj_pin("Object", "/Script/CoreUObject.Object")],
                         outputs=[Pin("ReturnValue", BOOL, "out")], pure=True, col=col, row=row)


def get_game_mode(g: Graph, col=None, row=None) -> Node:
    return g.call_static(GAMEPLAY, "GetGameMode", inputs=[Pin("WorldContextObject", OBJECT, hidden=True)],
                         outputs=[obj_pin("ReturnValue", GAME_MODE_BASE, "out")], pure=True, col=col, row=row)


def get_game_state(g: Graph, col=None, row=None) -> Node:
    return g.call_static(GAMEPLAY, "GetGameState", inputs=[Pin("WorldContextObject", OBJECT, hidden=True)],
                         outputs=[obj_pin("ReturnValue", GAME_STATE_BASE, "out")], pure=True, col=col, row=row)


def get_player_controller(g: Graph, index="0", col=None, row=None) -> Node:
    return g.call_static(GAMEPLAY, "GetPlayerController",
                         inputs=[Pin("WorldContextObject", OBJECT, hidden=True), Pin("PlayerIndex", INT, default=index)],
                         outputs=[obj_pin("ReturnValue", PLAYER_CONTROLLER, "out")], pure=True, col=col, row=row)


def game_time(g: Graph, col=None, row=None) -> Node:
    return g.call_static(GAMEPLAY, "GetTimeSeconds", inputs=[Pin("WorldContextObject", OBJECT, hidden=True)],
                         outputs=[Pin("ReturnValue", FLOAT, "out")], pure=True, col=col, row=row)


def cast_to(g: Graph, asset: str, col=None, row=None) -> Node:
    """Impure cast to a Dead Fire Blueprint class; result pin is 'As<Name>' (bpgen strips the _C)."""
    return g.cast(gen(asset), col=col, row=row)


def as_pin(asset_or_class: str) -> str:
    """Result pin of a cast to a Dead Fire Blueprint asset (or a native class path such as /Script/Engine.Controller)."""
    from bpgen import cast_result_pin
    path = asset_or_class if asset_or_class.startswith("/Script/") else gen(asset_or_class)
    return cast_result_pin(path)


def get_component(g: Graph, class_path: str, col=None, row=None) -> Node:
    """Actor.GetComponentByClass(class) -> ActorComponent (pure)."""
    return g.call_on(ACTOR, "GetComponentByClass",
                     inputs=[Pin("ComponentClass", CLASS, sub_object=cls_ref("/Script/Engine.ActorComponent"),
                                 default_object=class_path)],
                     outputs=[obj_pin("ReturnValue", "/Script/Engine.ActorComponent", "out")], pure=True, col=col, row=row)


def actor_location(g: Graph, col=None, row=None) -> Node:
    return g.call_on(ACTOR, "K2_GetActorLocation", outputs=[struct_pin("ReturnValue", VECTOR, "out")], pure=True,
                     col=col, row=row)


def self_actor_location(g: Graph, col=None, row=None) -> Node:
    """GetActorLocation on self (self pin left unlinked = self context)."""
    return g.call_self_native(ACTOR, "K2_GetActorLocation", outputs=[struct_pin("ReturnValue", VECTOR, "out")],
                              pure=True, col=col, row=row)


def array_length(g: Graph, elem: Pin, col=None, row=None) -> Node:
    return g.call_array(ARRAY, "Array_Length", elem, outputs=[Pin("ReturnValue", INT, "out")], col=col, row=row)


def array_get(g: Graph, elem: Pin, col=None, row=None) -> Node:
    return g.call_array(ARRAY, "Array_Get", elem, inputs=[Pin("Index", INT, default="0")],
                        outputs=[Pin("Item", elem.category, "out", elem.sub_object)], col=col, row=row)


def array_add(g: Graph, elem: Pin, col=None, row=None) -> Node:
    return g.call_array(ARRAY, "Array_Add", elem, inputs=[Pin("NewItem", elem.category, "in", elem.sub_object)],
                        outputs=[Pin("ReturnValue", INT, "out")], col=col, row=row, pure=False)


def array_set(g: Graph, elem: Pin, col=None, row=None) -> Node:
    return g.call_array(ARRAY, "Array_Set", elem,
                        inputs=[Pin("Index", INT, default="0"), Pin("Item", elem.category, "in", elem.sub_object),
                                Pin("bSizeToFit", BOOL, default="false")], col=col, row=row, pure=False)


def array_clear(g: Graph, elem: Pin, col=None, row=None) -> Node:
    return g.call_array(ARRAY, "Array_Clear", elem, col=col, row=row, pure=False)


# ---- Phase 3: items ----
BP_LOOTBOX = BPS + "/BP_DFLootBox"
BP_BOMB = BPS + "/BP_DFBomb"
BP_PROJECTILE = BPS + "/BP_DFProjectile"
BP_DESTRUCTIBLE = BPS + "/BP_DFDestructible"
BP_EXPLOSIVE_DAMAGE = BPS + "/BP_DFExplosiveDamage"
E_ITEM_TYPE = DATA + "/E_DFItemType"
S_ITEM_STACK = DATA + "/S_DFItemStack"
ITEM_NONE, ITEM_BOOST, ITEM_SHIELD, ITEM_BOMB, ITEM_GUN, ITEM_RPG = range(6)  # E_DFItemType order
ITEM_NAMES = ["-", "BOOST", "SHIELD", "BOMB", "GUN", "RPG"]
PARTICLE_SYSTEM = "/Script/Engine.ParticleSystem"
SOUND_BASE = "/Script/Engine.SoundBase"


# ---- Phase 4: AI racers ----
BP_AI = BPS + "/BP_DFVehicleAIController"
BP_GM_TEST = TESTS + "/BP_DFTestGameMode"
AI_CONTROLLER = "/Script/AIModule.AIController"


def enum_is(g: Graph, src, index: int, col=None, row=None) -> Node:
    """Pure EqualEqual_ByteByte(enum pin, index) -> bool; src is (node, pin) or ("entry", pin)."""
    n = g.call_static(MATH, "EqualEqual_ByteByte", inputs=[Pin("A", BYTE), Pin("B", BYTE, default=str(index))],
                      outputs=[Pin("ReturnValue", BOOL, "out")], pure=True, col=col, row=row)
    g.link(src[0], src[1], n, "A")
    return n


def get_all_actors_of_class(g: Graph, class_path: str, col=None, row=None) -> Node:
    """Impure GetAllActorsOfClass(class) -> OutActors (array typed as the class)."""
    return g.call_static(GAMEPLAY, "GetAllActorsOfClass",
                         inputs=[Pin("WorldContextObject", OBJECT, hidden=True),
                                 Pin("ActorClass", CLASS, sub_object=cls_ref(ACTOR), default_object=class_path)],
                         outputs=[Pin("OutActors", OBJECT, "out", cls_ref(class_path), container="Array")], col=col, row=row)


def vec_str(g: Graph, src) -> tuple:
    n = g.call_static("KismetStringLibrary", "Conv_VectorToString", inputs=[struct_pin("InVec", VECTOR)],
                      outputs=[Pin("ReturnValue", STRING, "out")], pure=True)
    g.link(src[0], src[1], n, "InVec")
    return (n, "ReturnValue")


def bool_str(g: Graph, src) -> tuple:
    n = g.call_static("KismetStringLibrary", "Conv_BoolToString", inputs=[Pin("InBool", BOOL)],
                      outputs=[Pin("ReturnValue", STRING, "out")], pure=True)
    g.link(src[0], src[1], n, "InBool")
    return (n, "ReturnValue")


# ---- Phase 5: menus and meta ----
BP_GI = BPS + "/BP_DFGameInstance"
BP_SAVE = BPS + "/BP_DFSaveGame"
BP_VEHICLE_BRUTE = BPS + "/BP_DFVehicleBrute"
BP_VEHICLE_VIPER = BPS + "/BP_DFVehicleViper"
BP_GM_SWITCHBACK = BPS + "/BP_DFSwitchbackGameMode"
BP_MENU_GM = BPS + "/BP_DFMenuGameMode"
BP_MENU_PC = BPS + "/BP_DFMenuPlayerController"
WBP_MAIN_MENU = UI + "/WBP_DFMainMenu"
WBP_VEHICLE_SELECT = UI + "/WBP_DFVehicleSelect"
WBP_LEVEL_SELECT = UI + "/WBP_DFLevelSelect"
WBP_SETTINGS = UI + "/WBP_DFSettings"
WBP_PAUSE = UI + "/WBP_DFPauseMenu"
AUDIO = "/Game/DeadFire/Audio"
SM_MASTER = AUDIO + "/SM_DFMaster"
MAPS = "/Game/DeadFire/Maps"
L_TEST_TRACK = MAPS + "/L_TestTrack"
L_SWITCHBACK = MAPS + "/L_Switchback"
L_MAIN_MENU = MAPS + "/L_MainMenu"
GAME_INSTANCE = "/Script/Engine.GameInstance"
SAVE_GAME = "/Script/Engine.SaveGame"
SOUND_MIX = "/Script/Engine.SoundMix"
SOUND_CLASS = "/Script/Engine.SoundClass"
MATERIAL_INTERFACE = "/Script/Engine.MaterialInterface"
CAMERA_ACTOR = "/Script/Engine.CameraActor"
USER_WIDGET = "/Script/UMG.UserWidget"

SEDAN_MASS = 1500.0  # the Sedan template's VehicleMovement.Mass (read in the editor 2026-10-30)
PAINT_SLOT = 0       # Phase 7 Task 13 (spec §6.1): the Body's paint slot (slots: 0 Paint, 1 Trim, 2 Glass, 3 Dark, 4 Lights)

# Phase 7 Task 13 (spec §6.1): the car visuals, imported by the art pipeline (Tasks 5 and 12) under /Game/DeadFire/Art
ART_MESHES = "/Game/DeadFire/Art/Meshes"
ART_MATERIALS = "/Game/DeadFire/Art/Materials"
STATIC_MESH = "/Script/Engine.StaticMesh"


def art_mesh(name: str) -> str:
    """Asset path of a catalogue mesh, e.g. art_mesh('SM_DF_Wheel')."""
    return "%s/%s" % (ART_MESHES, name)


def art_material(name: str) -> str:
    """Asset path of a catalogue material instance, e.g. art_material('MI_DF_Paint_Gang')."""
    return "%s/%s" % (ART_MATERIALS, name)


SM_WHEEL, SM_WHEEL_RIM = art_mesh("SM_DF_Wheel"), art_mesh("SM_DF_WheelRim")
SM_LIGHT_BAR, SM_ROOF_GUN, SM_ROOF_LAUNCHER = art_mesh("SM_DF_LightBar"), art_mesh("SM_DF_RoofGun"), art_mesh("SM_DF_RoofLauncher")
SM_SHIELD_BUBBLE, SM_EXHAUST_FLAME = art_mesh("SM_DF_ShieldBubble"), art_mesh("SM_DF_ExhaustFlame")
MI_PAINT_GANG, MI_PAINT_CHARRED = art_material("MI_DF_Paint_Gang"), art_material("MI_DF_Paint_Charred")
# Task 22 (controller ruling, spec §3): the Fire syndicate rivals' flame-orange trim on the Body's TRIM_SLOT (their cars show no light bar)
MI_TRIM_GANG = art_material("MI_DF_Trim_Gang")
TRIM_SLOT = 1
SHIELD_BUBBLE_AT = (2.2, 0.0, 95.8)  # cm, actor space: SM_DF_ShieldBubble is centred on its origin (Task 12, shield_bubble.centre)
# the car's wheel components and the wheel bones (= the Sedan skeleton's socket names) they ride on, in Tires order
CAR_WHEELS = (("WheelFL", "Wheel_Front_Left"), ("WheelFR", "Wheel_Front_Right"),
              ("WheelRL", "Wheel_Rear_Left"), ("WheelRR", "Wheel_Rear_Right"))
# the visible parts never collide: no physics state, so nothing welds onto the body they ride on (a car's Mesh, a character's)
NO_COLLISION = {"call:set_collision_profile_name": "NoCollision", "generate_overlap_events": False}

# Phase 7 Task 14 (spec §6.2): the on-foot character's gear components, their catalogue meshes and the SK_Mannequin bones
# they ride on, and the mannequin's two material slots
CHARACTER_GEAR = (("Helmet", "SM_DF_Helmet", "head"), ("Vest", "SM_DF_Vest", "spine_03"), ("Rifle", "SM_DF_Rifle", "hand_r"))
MI_MANNEQUIN_BODY, MI_MANNEQUIN_TRIM = art_material("MI_DF_Mannequin_Body"), art_material("MI_DF_Mannequin_Trim")


class VehicleRow:
    """One catalogue row (spec 2026-10-30 phase 5 §3.1): display, unlock rule, tuning and the stat bars (1-5)."""

    def __init__(self, index, name, asset, unlock_level, max_health, throttle_scale, top_speed, boost_duration, boost_kick,
                 mass_factor, paint, bars, description, steer_at_speed=0.45, grip_assist=3.0, downforce_g=0.25, body=None,
                 engine_sound=None, light_bar=False):
        self.index, self.name, self.asset, self.unlock_level = index, name, asset, unlock_level
        self.max_health, self.throttle_scale, self.top_speed = max_health, throttle_scale, top_speed
        self.boost_duration, self.boost_kick, self.mass_factor, self.paint = boost_duration, boost_kick, mass_factor, paint
        self.speed, self.acceleration, self.armor, self.boost = bars
        self.description = description
        # Phase 7 (spec §5.2): handling columns (class defaults from Task 7); body is used from Task 13, engine_sound from Task 11
        self.steer_at_speed, self.grip_assist, self.downforce_g = steer_at_speed, grip_assist, downforce_g
        self.body, self.engine_sound = body, engine_sound
        # Phase 7 Task 13 (spec §6.1): paint is the class's MI_DF_Paint_<X> (the Body's slot 0), body its SM_DF_Car_<X>, and
        # light_bar whether the light bar on the Roof socket shows (SEDAN only)
        self.light_bar = light_bar


VEHICLES = [
    VehicleRow(0, "SEDAN", BP_VEHICLE, -1, 100, 1.0, 0, 2, 1200, None, art_material("MI_DF_Paint_Sedan"), (3, 3, 3, 3),
               "Balanced. Takes a beating, keeps its speed.",
               steer_at_speed=0.45, grip_assist=3.0, downforce_g=0.25,
               body="SM_DF_Car_Sedan", engine_sound="SW_DF_EngineSedan", light_bar=True),
    VehicleRow(1, "BRUTE", BP_VEHICLE_BRUTE, 0, 160, 0.8, 120, 2, 1200, 1.3, art_material("MI_DF_Paint_Brute"), (2, 2, 5, 3),
               "Armoured and heavy: slow to get going, hard to kill, limited to 120.",
               steer_at_speed=0.50, grip_assist=3.5, downforce_g=0.20,
               body="SM_DF_Car_Brute", engine_sound="SW_DF_EngineBrute"),
    VehicleRow(2, "VIPER", BP_VEHICLE_VIPER, 1, 70, 1.0, 0, 3, 1600, 0.8, art_material("MI_DF_Paint_Viper"), (5, 4, 2, 5),
               "Light and fragile: fastest off the line, with a longer, harder boost.",
               steer_at_speed=0.38, grip_assist=2.5, downforce_g=0.35,
               body="SM_DF_Car_Viper", engine_sound="SW_DF_EngineViper"),
]

# Phase 7 Task 10: camera shakes (graphs/fx.py) and the Sedan template's camera components (spec §5.3)
BP_SHAKE_LIGHT = BPS + "/BP_DFShakeLight"
BP_SHAKE_HEAVY = BPS + "/BP_DFShakeHeavy"
MATINEE_SHAKE = "/Script/GameplayCameras.MatineeCameraShake"  # UE 4.27: in the GameplayCameras plugin, not /Script/Engine
CAMERA_SHAKE_BASE = "/Script/Engine.CameraShakeBase"
SPRING_ARM = "/Script/Engine.SpringArmComponent"  # the Sedan's "SpringArm" (relative pitch -15, inherits yaw only)
CAMERA_COMP = "/Script/Engine.CameraComponent"    # the Sedan's "ChaseCamera" (FOV 90) and "InternalCamera"


def start_camera_shake(g: Graph, pc_src, shake_src, scale_src=None, scale="1.0") -> Node:
    """PlayerController.ClientStartCameraShake(Shake, Scale, CameraLocal) on pc_src (impure: link execute); the 4.27 name
    (ClientPlayCameraShake is the deprecated C++-only alias). Sources are (node, pin) tuples or ("entry", pin)."""
    n = g.call_on(PLAYER_CONTROLLER, "ClientStartCameraShake",
                  inputs=[Pin("Shake", CLASS, sub_object=cls_ref(CAMERA_SHAKE_BASE)), Pin("Scale", FLOAT, default=None if scale_src else scale),
                          native_enum_pin("PlaySpace", "/Script/Engine.ECameraShakePlaySpace", "CameraLocal"),
                          struct_pin("UserPlaySpaceRot", ROTATOR)])
    g.link(pc_src[0], pc_src[1], n, "self")
    g.link(shake_src[0], shake_src[1], n, "Shake")
    if scale_src:
        g.link(scale_src[0], scale_src[1], n, "Scale")
    return n


# Phase 7 Task 15 (spec §7.1): the effect family (graphs/fx.py). BP_DFFx is a short-lived actor whose static mesh components
# tagged FX_SHELL_TAG grow from StartScale to EndScale and fade; its seven children set the shells and the values. The
# shell meshes are imported by the art pipeline under /Game/DeadFire/Art/Fx (catalog.asset_path), not Art/Meshes.
ART_FX = "/Game/DeadFire/Art/Fx"
POINT_LIGHT_COMP = "/Script/Engine.PointLightComponent"
MID = "/Script/Engine.MaterialInstanceDynamic"
FX_SHELL_TAG = "FxShell"


def art_fx(name: str) -> str:
    """Asset path of a catalogue effect shell mesh, e.g. art_fx('SM_DF_FxSphere')."""
    return "%s/%s" % (ART_FX, name)


BP_FX = BPS + "/BP_DFFx"
BP_FX_MUZZLE, BP_FX_TRACER, BP_FX_IMPACT, BP_FX_EXPLOSION = (BP_FX + n for n in ("Muzzle", "Tracer", "Impact", "Explosion"))
BP_FX_PUFF, BP_FX_LOOT_BURST, BP_FX_SPARKS = (BP_FX + n for n in ("Puff", "LootBurst", "Sparks"))
FX_CHILDREN = (BP_FX_MUZZLE, BP_FX_TRACER, BP_FX_IMPACT, BP_FX_EXPLOSION, BP_FX_PUFF, BP_FX_LOOT_BURST, BP_FX_SPARKS)


def spawn_fx(g: Graph, fx_asset: str, transform_src, tint_src=None, tint: Optional[str] = None, class_src=None) -> tuple:
    """Spawns an effect (SpawnActorFromClass) and, when a tint is given, calls its SetTint(Color) right after, in the same
    frame: SetTint re-tints the shells' materials BeginPlay has just made (Color = Tint x the instance's Color), so the first
    frame drawn is tinted. This is the route for a tinted effect: a deferred spawn cannot be generated (the editor refuses
    to paste the BlueprintInternalUseOnly BeginDeferredActorSpawnFromClass / FinishSpawningActor), and the generator has
    no expose-on-spawn variables. transform_src: (node, pin) of the spawn transform. tint_src: (node, pin) of a
    LinearColor, or the literal `tint` text "(R=..,G=..,B=..,A=..)"; neither = untinted (white). class_src (Task 16): the
    (node, pin) of a class variable to spawn (e.g. a weapon's MuzzleFxClass); fx_asset is then the class the effect is typed
    as (BP_FX, or BP_FX_TRACER for a tracer class). Returns (first, last, actor): link first's execute, continue from last's
    then; actor is the (node, pin) of the effect (typed as its class)."""
    if class_src:
        spawn = g.spawn_actor(None, result_class=gen(fx_asset))
        g.link(class_src[0], class_src[1], spawn, "Class")
    else:
        spawn = g.spawn_actor(gen(fx_asset))
    g.link(transform_src[0], transform_src[1], spawn, "SpawnTransform")
    if tint_src is None and tint is None:
        return spawn, spawn, (spawn, "ReturnValue")
    set_tint = g.call_on(gen(BP_FX), "SetTint", inputs=[struct_pin("Color", LINEAR_COLOR, default=None if tint_src else tint)])
    g.link(spawn, "ReturnValue", set_tint, "self")
    if tint_src:
        g.link(tint_src[0], tint_src[1], set_tint, "Color")
    g.exec(spawn, set_tint)
    return spawn, set_tint, (spawn, "ReturnValue")

# Phase 7 Task 11: the car sounds (spec §5.4), imported by the art pipeline (Task 6) under /Game/DeadFire/Art/Sounds
ART_SOUNDS = "/Game/DeadFire/Art/Sounds"
AUDIO_COMP = "/Script/Engine.AudioComponent"
ACTOR_COMP = "/Script/Engine.ActorComponent"
SW_SKID = ART_SOUNDS + "/SW_DF_Skid"
SW_CRASH = ART_SOUNDS + "/SW_DF_Crash"


def art_sound(name: str) -> str:
    """Asset path of a catalogue sound, e.g. art_sound('SW_DF_EngineSedan')."""
    return "%s/%s" % (ART_SOUNDS, name)


def asset_object(asset: str) -> str:
    """Object path of an asset (Package.Name), as an object pin's DefaultObject takes it."""
    return "%s.%s" % (asset, asset.rsplit("/", 1)[1])


# Phase 7 Task 7: top speed (km/h) of each car at full throttle for 12 s on the flat drive strip, measured BEFORE any
# handling change (FT_DFDrive_TopSpeed* logs "DRIVE BASELINE <NAME> <kph>"); the tests allow +-5 %.
BASELINE_TOP_SPEED = {"SEDAN": 56.6, "BRUTE": 38.4, "VIPER": 63.2}


class LevelRow:
    """One track (spec §2.2): display, map, GameMode, pass score, clock, rivals, gates."""

    def __init__(self, index, name, map_path, game_mode, score, time, npcs, gates, description, bonus=8.0):
        self.index, self.name, self.map, self.game_mode = index, name, map_path, game_mode
        self.score, self.time, self.npcs, self.gates, self.description = score, time, npcs, gates, description
        self.bonus = bonus  # Phase 6: checkpoint time bonus (s per gate), set from the balance runs (spec 2026-10-30 phase 6 §3.3)


# bonus: checkpoint time bonus per gate, from docs/superpowers/balance-2026-10-30.md (6 laps / 4 laps at NPC pace);
# re-measured after the Phase 7 handling in docs/superpowers/balance-2026-10-31.md: the formula gives the same 3 s / 2 s
LEVELS = [
    LevelRow(0, "PROVING GROUND", L_TEST_TRACK, BP_GM, 300, 120, 3, 4,
             "The kidney loop you know: four gates, a shortcut behind a rock, crates in the infield.", bonus=3.0),
    LevelRow(1, "SWITCHBACK", L_SWITCHBACK, BP_GM_SWITCHBACK, 400, 150, 4, 5,
             "Longer and tighter: five gates, an S-bend you must brake for, more rivals, more time.", bonus=2.0),
]
class DifficultyRow:
    """One difficulty (Phase 6 spec §3.4): rival count delta, NPC speed scale, NPC item interval scale."""

    def __init__(self, index, name, rival_delta, speed_scale, item_interval_scale):
        self.index, self.name, self.rival_delta = index, name, rival_delta
        self.speed_scale, self.item_interval_scale = speed_scale, item_interval_scale


DIFFICULTIES = [
    DifficultyRow(0, "EASY", -1, 0.85, 1.5),
    DifficultyRow(1, "NORMAL", 0, 1.0, 1.0),
    DifficultyRow(2, "HARD", 2, 1.1, 0.6),
]
DIFFICULTY_NAMES = [d.name for d in DIFFICULTIES]
DIFFICULTY_DELTA = [d.rival_delta for d in DIFFICULTIES]


def game_instance(g: Graph, col=None, row=None) -> Node:
    """GetGameInstance cast to BP_DFGameInstance: an impure cast node (link its execute; use then / CastFailed and the
    as_pin(BP_GI) output). The cast fails only when the project runs another GameInstance class."""
    gi = g.call_static(GAMEPLAY, "GetGameInstance", inputs=[Pin("WorldContextObject", OBJECT, hidden=True)],
                       outputs=[obj_pin("ReturnValue", GAME_INSTANCE, "out")], pure=True, col=col, row=row)
    c = g.cast(gen(BP_GI), col=col, row=row)
    g.link(gi, "ReturnValue", c, "Object")
    return c


# Phase 7 Task 16 (spec §5.5, §7.2, §7.3): shots, rockets, explosions, tyre pops and smoke
DECAL_COMP = "/Script/Engine.DecalComponent"
MI_SCORCH, MI_FX_FLAME = art_material("MI_DF_Scorch"), art_material("MI_DF_FxFlame")
SM_ROCKET = art_mesh("SM_DF_Rocket")
SW_CAR_GUN, SW_RIFLE = art_sound("SW_DF_CarGun"), art_sound("SW_DF_Rifle")
SW_IMPACT_DIRT, SW_IMPACT_METAL = art_sound("SW_DF_ImpactDirt"), art_sound("SW_DF_ImpactMetal")
SW_ROCKET_LAUNCH, SW_ROCKET_LOOP = art_sound("SW_DF_RocketLaunch"), art_sound("SW_DF_RocketLoop")
SW_EXPLOSION, SW_TIRE_POP = art_sound("SW_DF_Explosion"), art_sound("SW_DF_TirePop")
# cosmetic smoke (tyre smoke, rocket trails, wreck smoke) spawns only this close to the player's camera (Review Focus 2:
# seven cars drifting or burning at once must not flood the world with smoke actors): GameMode.IsNearPlayerView(loc, this)
FX_VIEW_RADIUS = 8000.0
# spec §7.3: the scorch is 4 m across and fades out over 20 s. DecalSize is a half-extent (UDecalComponent::CalcBounds uses it
# as the box extent), so (200, 200, 200) is a 4 m footprint projected 4 m deep (controller ruling, Task 16 fix round 1: the
# brief's (200, 400, 400) drew 8 m)
SCORCH_SIZE, SCORCH_LIFE = (200.0, 200.0, 200.0), 20.0


def weapon_look(fire_sound: str) -> dict:
    """BPC_DFWeapon's effects and sounds (spec §7.2) as properties of an owner's Weapon component template (the car's and the
    character's): a class default written after the weapon compiles never reaches an existing component template (Task 14's
    bDebugTrace), so each owner sets them on its own Weapon. fire_sound: the owner's shot sound."""
    return {"MuzzleFxClass": "class:" + BP_FX_MUZZLE, "TracerFxClass": "class:" + BP_FX_TRACER,
            "ImpactFxClass": "class:" + BP_FX_IMPACT, "VehicleImpactFxClass": "class:" + BP_FX_SPARKS,
            "FireSound": fire_sound, "ImpactSound": SW_IMPACT_DIRT, "VehicleImpactSound": SW_IMPACT_METAL}


def play_sound_at(g: Graph, sound_src, loc_src) -> Node:
    """GameplayStatics.PlaySoundAtLocation(sound, location) (impure: link execute); a null sound plays nothing. Sources are
    (node, pin) tuples or ("entry", pin)."""
    n = g.call_static(GAMEPLAY, "PlaySoundAtLocation",
                      inputs=[Pin("WorldContextObject", OBJECT, hidden=True), obj_pin("Sound", SOUND_BASE), struct_pin("Location", VECTOR),
                              struct_pin("Rotation", ROTATOR), Pin("VolumeMultiplier", FLOAT, default="1.0"),
                              Pin("PitchMultiplier", FLOAT, default="1.0"), Pin("StartTime", FLOAT, default="0.0"),
                              obj_pin("AttenuationSettings", "/Script/Engine.SoundAttenuation"),
                              obj_pin("ConcurrencySettings", "/Script/Engine.SoundConcurrency"), obj_pin("OwningActor", ACTOR)])
    g.link(sound_src[0], sound_src[1], n, "Sound")
    g.link(loc_src[0], loc_src[1], n, "Location")
    return n


# Phase 7 Task 17 (spec §3, §7.4, §7.5): the crates' own look (crate, lid, glowing stripe, floating icon, beacon pillar), the bomb
# as a blinking mine, the boost flames and the shield bubble driven by the item state, and their sounds. The item colours are
# the art catalogue's (tools/artgen/catalog.py ITEM_COLOURS, spec §3), imported rather than retyped; it is appended to the path
# (never in front), so no module here is shadowed by one under tools/.
import sys as _sys  # noqa: E402
_sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from artgen import catalog as _art_catalog  # noqa: E402

ART_UI = "/Game/DeadFire/Art/UI"
BILLBOARD_COMP = "/Script/Engine.MaterialBillboardComponent"
TEXTURE_2D = "/Script/Engine.Texture2D"
TEXTURE = "/Script/Engine.Texture"
SM_CRATE, SM_CRATE_LID = art_mesh("SM_DF_Crate"), art_mesh("SM_DF_CrateLid")
SM_BEACON, SM_BOMB = art_mesh("SM_DF_BeaconPillar"), art_mesh("SM_DF_Bomb")
MI_ICON = art_material("MI_DF_Icon")
SW_LOOT_OPEN, SW_DENY, SW_BOOST = art_sound("SW_DF_LootOpen"), art_sound("SW_DF_Deny"), art_sound("SW_DF_Boost")
SW_SHIELD_UP, SW_SHIELD_DOWN, SW_SHIELD_HIT = art_sound("SW_DF_ShieldUp"), art_sound("SW_DF_ShieldDown"), art_sound("SW_DF_ShieldHit")
SW_BOMB_ARM, SW_BOMB_BEEP = art_sound("SW_DF_BombArm"), art_sound("SW_DF_BombBeep")
CRATE_STRIPE_SLOT = 1  # SM_DF_Crate's and SM_DF_CrateLid's slots: 0 CrateMetal, 1 CrateStripe (the glowing stripe)
BOMB_LAMP_SLOT = 2     # SM_DF_Bomb's slots: 0 GunMetal, 1 Dark, 2 BombLamp (the blinking lamp)
# Task 17 fix round 1 (controller ruling): a crate actor stands at the centre of its 80 cm crate (crate and lid), so the level's
# crates (z 30 over the -10 ground top) rest on the ground: SM_DF_Crate's base is this far below its origin
CRATE_HALF_HEIGHT = 40.0
LID_POP_SECONDS = 0.4  # spec §7.4 "the lid pops off": its lift and tumble on a pickup, then it hides
# the bomb's touch (controller ruling: the old reach): the stock Shape_Sphere was base-pivoted and dropped at scale 0.5, 30 cm over
# the ground, so it touched from a 25 cm sphere centred 55 cm over the ground; the mine rests on the ground, so the same sphere
BOMB_TRIGGER_Z, BOMB_TRIGGER_R = 55.0, 25.0


def art_icon(name: str) -> str:
    """Asset path of a catalogue UI image, e.g. art_icon('T_DF_Icon_Boost')."""
    return "%s/%s" % (ART_UI, name)


# item -> (sRGB hex of its colour, its icon): the crate's stripe, icon and beacon, the loot burst and the HUD slot (spec §3)
ITEM_LOOK = {ITEM_BOOST: (_art_catalog.ITEM_COLOURS["Boost"], "T_DF_Icon_Boost"),
             ITEM_SHIELD: (_art_catalog.ITEM_COLOURS["Shield"], "T_DF_Icon_Shield"),
             ITEM_BOMB: (_art_catalog.ITEM_COLOURS["Bomb"], "T_DF_Icon_Bomb"),
             ITEM_GUN: (_art_catalog.ITEM_COLOURS["Gun"], "T_DF_Icon_Gun"),
             ITEM_RPG: (_art_catalog.ITEM_COLOURS["RPG"], "T_DF_Icon_RPG")}
RANDOM_LOOK = (_art_catalog.ITEM_COLOURS["Random"], "T_DF_Icon_Random")  # a random crate's look, whatever it rolled
EMPTY_ICON = "T_DF_Icon_Empty"  # no item (ITEM_NONE): white, the empty slot's icon


def transform_at(g: Graph, loc_src) -> tuple:
    """MakeTransform(location, no rotation, scale 1) (pure): (node, pin) of a spawn transform at loc_src (shared by the vehicle
    and the item actors' effect spawns)."""
    n = g.call_static(MATH, "MakeTransform", inputs=[struct_pin("Location", VECTOR), struct_pin("Rotation", ROTATOR),
                                                       struct_pin("Scale", VECTOR, default="1,1,1")],
                      outputs=[struct_pin("ReturnValue", TRANSFORM, "out")], pure=True)
    g.link(loc_src[0], loc_src[1], n, "Location")
    return (n, "ReturnValue")


def linear_colour(hex_colour: str) -> str:
    """A LinearColor pin default "(R=..,G=..,B=..,A=1.000000)" of an sRGB hex colour (catalog.linear, IEC 61966-2-1)."""
    return "(R=%f,G=%f,B=%f,A=%f)" % _art_catalog.linear(hex_colour)


def timer(g: Graph, fn: str, time_src, clear=False, looping=True) -> Node:
    """KismetSystemLibrary.K2_SetTimer(self, fn, time, looping) or K2_ClearTimer(self, fn) (impure; link execute); time_src is
    a (node, pin) source or a number (a literal). Setting it again restarts the countdown (K2_SetTimer finds the function's
    timer). Shared by the vehicle's effect timers and the race HUD's timed looks (Task 18)."""
    if clear:
        n = g.call_static(SYS, "K2_ClearTimer", inputs=[obj_pin("Object", "/Script/CoreUObject.Object"), Pin("FunctionName", STRING, default=fn)])
    else:
        literal = isinstance(time_src, (int, float))
        n = g.call_static(SYS, "K2_SetTimer", inputs=[obj_pin("Object", "/Script/CoreUObject.Object"), Pin("FunctionName", STRING, default=fn),
                                                      Pin("Time", FLOAT, default="%f" % time_src if literal else None),
                                                      Pin("bLooping", BOOL, default="true" if looping else "false"),
                                                      Pin("InitialStartDelay", FLOAT, default="0.0"), Pin("InitialStartDelayVariance", FLOAT, default="0.0")],
                          outputs=[struct_pin("ReturnValue", "/Script/Engine.TimerHandle", "out")])
        if not literal:
            g.link(time_src[0], time_src[1], n, "Time")
    g.link(g.self_node(), "self", n, "Object")
    return n


# Phase 7 Task 18 (spec §3, §7.6): the HUD and menu look. Russo One (F_DF_Display, imported by df_import_art.py) on every text,
# the catalogue's UI images (item icons, crosshair, damage vignette, logo), the button sounds and the gate and lap chimes
F_DISPLAY = ART_UI + "/F_DF_Display"
IMAGE = "/Script/UMG.Image"
T_CROSSHAIR, T_VIGNETTE, T_LOGO = art_icon("T_DF_Crosshair"), art_icon("T_DF_Vignette"), art_icon("T_DF_Logo")
SW_UI_HOVER, SW_UI_CLICK = art_sound("SW_DF_UIHover"), art_sound("SW_DF_UIClick")
SW_CHECKPOINT, SW_LAP = art_sound("SW_DF_Checkpoint"), art_sound("SW_DF_Lap")

# Phase 7 Task 21 (spec §8.2, §8.3): the track's road and barrier meshes, the gates' pylons and banner (their Gate slot glows: the
# player's next gate bright, the others dim), the rock wall and the chunks it breaks into (graphs/environment.py BP_DFDebris), and
# the instanced scatter actor Task 22's level builder places (BP_DFScatter)
BP_DEBRIS = BPS + "/BP_DFDebris"
BP_SCATTER = BPS + "/BP_DFScatter"
ISM_COMP = "/Script/Engine.InstancedStaticMeshComponent"
HISM_COMP = "/Script/Engine.HierarchicalInstancedStaticMeshComponent"
COLLISION_CHANNEL, COLLISION_RESPONSE = "/Script/Engine.ECollisionChannel", "/Script/Engine.ECollisionResponse"
SM_ROAD_SLAB, SM_BARRIER = art_mesh("SM_DF_RoadSlab"), art_mesh("SM_DF_Barrier")
MI_ROAD, MI_CONCRETE = art_material("MI_DF_Road"), art_material("MI_DF_Concrete")
SM_GATE_PYLON, SM_GATE_BANNER = art_mesh("SM_DF_GatePylon"), art_mesh("SM_DF_GateBanner")
SM_ROCK_WALL, SM_ROCK_CHUNK = art_mesh("SM_DF_RockWall"), art_mesh("SM_DF_RockChunk")
GATE_GLOW_ON, GATE_GLOW_OFF = 4.0, 0.6  # the Gate slot's Glow on the player's next gate and on every other one (MI_DF_Gate's own)
GATE_GLOW_SLOT = 0                      # SM_DF_GatePylon's and SM_DF_GateBanner's Gate slot (1 is GunMetal / Dark: never glows)
GATE_BANNER_Y_CM = 100.0                # SM_DF_GateBanner spans 100 cm on Y: scaled to the pole spacing, 2 x PoleOffset
GATE_POLE_OFFSET = 800.0                # Task 22: BP_DFCheckpoint's PoleOffset; at 700 the 93 cm pylons stood half on the 14 m
                                        # road's edge and a car hugging it drove through one (they have no collision)
# the rock breaks into a 2 x 2 x 2 grid of chunks over its mesh's bounds: each cell's centre, as a fraction of the half-extent
ROCK_CHUNK_CELLS = [(x, y, z) for z in (-0.5, 0.5) for y in (-0.5, 0.5) for x in (-0.5, 0.5)]
DEBRIS_SPEED = 600.0                    # cm/s: each chunk's outward velocity change when the rock breaks
DEBRIS_LIFE = 8.0                       # s
ROCK_CHUNK_CM = 115.0                   # SM_DF_RockChunk's longest side (115 x 95 x 80 cm, Task 20): sized to fit its grid cell
SCATTER_CULL_CM = 30000                 # BP_DFScatter's default CullDistance
