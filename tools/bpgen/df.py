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
