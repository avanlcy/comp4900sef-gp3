"""BP_DFVehicle (plan Tasks 3 and 5): child of the Vehicle template's Sedan.

Health, tires, damage routing, destruction, drive overrides, enter/exit, teleport. Driving comes from the Sedan parent
with Dead Fire's arcade layer on top (Phase 7 Task 9: TickArcade); the cameras and the in-car HUD text are the parent's,
with the speed FOV, camera lag, look-back, the reset and the camera shakes on top (Phase 7 Task 10). The engine and skid
loops and the crash sound are Phase 7 Task 11 (TickAudio, HandleCrashHit). The visible car is Phase 7 Task 13: the physics Mesh
is hidden and the Dead Fire body, wheels, light bar, roof weapon, shield bubble and boost flames are static meshes on it
(RefreshWheels, ApplyPaint, RefreshRoofWeapon, the charred wreck). Phase 7 Task 16: the gun and rocket sounds and effects, the
tyre pop, tyre smoke and the burning wreck (TickTyreSmoke, SpawnWreckSmoke). Phase 7 Task 17: the boost flames and the shield
bubble follow the item timers (RefreshEffectLook), with the boost and shield sounds and a blocked hit's flash (ShieldHit).
Phase 7 Task 18: a hit taken shows the driving player's damage vignette (ShowDriverDamage).
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from df import *  # noqa: E402,F401,F403
from df import (ACTOR, BOOL, BP_CHARACTER, BP_GM, BP_VEHICLE, CONTROLLER, FLOAT, HIT_RESULT, INT, MATH, NAME, OBJECT,  # noqa: E402
                OUT, PAWN, PRIMITIVE, S_TIRE, SCENE_COMP, SEDAN, SKEL_MESH_COMP, STRUCT, SYS, TRANSFORM, VECTOR,
                WHEELED_MOVE, Blueprint, Graph, Node, Pin, and_bool, as_pin, cast_to, cls_ref, compare, gen,
                get_game_mode, is_valid, math2, member, not_bool, obj_pin, obj_spec, struct_path, struct_pin,
                struct_spec)
from df import MATERIAL_INTERFACE, PAINT_SLOT, SEDAN_MASS, STRING, VEHICLES  # noqa: E402
from df import (BP_SHAKE_LIGHT, CAMERA_COMP, CAMERA_SHAKE_BASE, CLASS, PLAYER_CONTROLLER, ROTATOR, SPRING_ARM,  # noqa: E402  (Task 10)
                start_camera_shake)
from df import AUDIO_COMP, SOUND_BASE, SW_CRASH, SW_SKID, art_sound  # noqa: E402  (Task 11)
from df import (CAR_WHEELS, MI_PAINT_CHARRED, NO_COLLISION, SHIELD_BUBBLE_AT, SM_EXHAUST_FLAME, SM_LIGHT_BAR,  # noqa: E402  (Task 13)
                SM_ROOF_GUN, SM_ROOF_LAUNCHER, SM_SHIELD_BUBBLE, SM_WHEEL, SM_WHEEL_RIM, STATIC_MESH, STATIC_MESH_COMP, art_mesh,
                asset_object)
from df import (BP_FX_PUFF, BP_FX_SPARKS, FX_VIEW_RADIUS, LINEAR_COLOR, MI_FX_FLAME, SW_CAR_GUN, SW_ROCKET_LAUNCH,  # noqa: E402  (Task 16)
                SW_TIRE_POP, play_sound_at, spawn_fx, weapon_look)
from df import MID, SW_BOOST, SW_SHIELD_DOWN, SW_SHIELD_HIT, SW_SHIELD_UP, transform_at  # noqa: E402  (Task 17)
from df import BP_HUD, USER_WIDGET, WBP_HUD, timer  # noqa: E402  (Task 18: timer moved to df.py, shared with the race HUD)

VC, CC, GMC = gen(BP_VEHICLE), gen(BP_CHARACTER), gen(BP_GM)
TIRE = struct_path(S_TIRE)
WHEEL_BONES = ["Wheel_Front_Left", "Wheel_Front_Right", "Wheel_Rear_Left", "Wheel_Rear_Right"]
assert [bone for _, bone in CAR_WHEELS] == WHEEL_BONES  # Tires index i drives the i-th wheel component (RefreshWheels)
# Phase 7 Task 13 (spec §6.1): the hidden physics Mesh keeps ticking its pose and refreshing its bones (the wheels ride on them)
TICK_REFRESH_BONES = {"enum": "VisibilityBasedAnimTickOption.ALWAYS_TICK_POSE_AND_REFRESH_BONES"}
# the visible parts never collide (df.NO_COLLISION): no physics state, so the mass stays the template's
# Phase 7 Task 11 (spec §5.4): a hit plays the crash sound when its normal impulse (kg cm/s) is above this. Set from the logged
# run of 2026-10-31 (three SEDANs at 40 km/h into three parked BRUTEs on the drive strip): each impact's contact impulse was
# 1,300,269 / 1,300,270 / 1,300,272, median 1,300,270, half 650,135, rounded to 650,000 (about a 20 km/h hit). The resting
# pushes that follow an impact (2,600-14,000) are not the hit and stay far below it; the chassis never touched the strip.
CRASH_IMPULSE = 650000.0
# Phase 7 Task 16 (spec §7.1): the wreck's fire, SM_DF_ExhaustFlame (80 cm along +X) stood up (pitch 90) on the front of the Body,
# about where the bonnet is on all three bodies (a lower bonnet hides a little more of its root), 1.3 m tall and 50 cm across
WRECK_FIRE_AT, WRECK_FIRE_SCALE = (165.0, 0.0, 85.0), (1.6, 3.0, 3.0)
WRECK_SMOKE_TINT = [0.3, 0.28, 0.26, 1.0]  # x MI_DF_FxPuff's light ash grey: a dark smoke (a tint can only darken it)


def comp_location(g: Graph, name: str) -> tuple:
    """A static mesh component's world location (WheelRL, WreckFire, ...)."""
    n = g.call_on(SCENE_COMP, "K2_GetComponentLocation", outputs=[struct_pin("ReturnValue", VECTOR, "out")], pure=True)
    c = look_comp(g, name)
    g.link(c[0], c[1], n, "self")
    return (n, "ReturnValue")


def near_player_view(g: Graph, loc_src, prev) -> Node:
    """After prev: the GameMode cast to BP_DFRaceGameMode, then a branch on IsNearPlayerView(loc, FX_VIEW_RADIUS) (cosmetic
    smoke only near the player's camera, Review Focus 2; no race GameMode, e.g. the menu, = no smoke). Returns the branch."""
    cast = cast_to(g, BP_GM)
    g.link(get_game_mode(g), "ReturnValue", cast, "Object")
    g.link(prev[0], prev[1], cast, "execute")
    near = g.call_on(GMC, "IsNearPlayerView", inputs=[struct_pin("Location", VECTOR), Pin("Radius", FLOAT, default="%f" % FX_VIEW_RADIUS)],
                     outputs=[Pin("ReturnValue", BOOL, "out")], pure=True)
    g.link(cast, as_pin(BP_GM), near, "self")
    g.link(loc_src[0], loc_src[1], near, "Location")
    b = g.branch()
    g.note(b, "near the player's camera?")
    g.link(near, "ReturnValue", b, "Condition")
    g.link(cast, "then", b, "execute")
    return b


def car_sound(g: Graph, var: str) -> Node:
    """One of the car's SoundBase variables (BoostSound, ShieldUpSound, ...) at the car (df.play_sound_at; impure)."""
    return play_sound_at(g, (g.var_get(var, OBJECT, cls_ref(SOUND_BASE)), var), (self_actor_location(g), "ReturnValue"))


def mid_glow(g: Graph, value_src) -> Node:
    """ShieldMID.SetScalarParameterValue("Glow", value) (Task 17: the shield bubble's flash on a blocked hit; impure)."""
    n = g.call_on(MID, "SetScalarParameterValue", inputs=[Pin("ParameterName", NAME, default="Glow"), Pin("Value", FLOAT)])
    g.link(g.var_get("ShieldMID", OBJECT, cls_ref(MID)), "ShieldMID", n, "self")
    g.link(value_src[0], value_src[1], n, "Value")
    return n


def mesh(g: Graph, col=None, row=None) -> Node:
    return g.var_get("Mesh", OBJECT, cls_ref(SKEL_MESH_COMP), col=col, row=row)


def movement(g: Graph, col=None, row=None) -> Node:
    return g.var_get("VehicleMovement", OBJECT, cls_ref(WHEELED_MOVE), col=col, row=row)


def mv_call(g: Graph, fn: str, inputs=None, outputs=None, pure=False, col=None, row=None, **defaults) -> Node:
    """Call a WheeledVehicleMovementComponent function on this vehicle's movement component."""
    mv = movement(g)
    n = g.call_on(WHEELED_MOVE, fn, inputs=inputs, outputs=outputs, pure=pure, col=col, row=row, **defaults)
    g.link(mv, "VehicleMovement", n, "self")
    return n


def set_throttle(g, value_default=None):
    return mv_call(g, "SetThrottleInput", inputs=[Pin("Throttle", FLOAT, default=value_default)])


def drive_throttle(g: Graph, input_src) -> Node:
    """self.ComputeDriveThrottle(input, GetSpeedKPH()) (pure): the car's throttle scale and speed limiter (Phase 5)."""
    n = g.call_self("ComputeDriveThrottle", inputs=[Pin("Input", FLOAT), Pin("SpeedKPH", FLOAT)], outputs=[Pin("Throttle", FLOAT, "out")], pure=True)
    g.link(input_src[0], input_src[1], n, "Input")
    kph = g.call_self("GetSpeedKPH", outputs=[Pin("KPH", FLOAT, "out")], pure=True)
    g.link(kph, "KPH", n, "SpeedKPH")
    return n


def set_steering(g, value_default=None):
    return mv_call(g, "SetSteeringInput", inputs=[Pin("Steering", FLOAT, default=value_default)])


def set_handbrake(g, value: str):
    return mv_call(g, "SetHandbrakeInput", inputs=[Pin("bNewHandbrake", BOOL, default=value)])


def break_tire(g: Graph, col=None, row=None) -> Node:
    return g.break_struct(TIRE, [Pin(member(S_TIRE, "BoneName"), NAME), Pin(member(S_TIRE, "Health"), FLOAT),
                                 Pin(member(S_TIRE, "MaxHealth"), FLOAT), Pin(member(S_TIRE, "bBlown"), BOOL)],
                          col=col, row=row)


def make_tire(g: Graph, bone_default=None, col=None, row=None) -> Node:
    return g.make_struct(TIRE, [Pin(member(S_TIRE, "BoneName"), NAME, default=bone_default),
                                Pin(member(S_TIRE, "Health"), FLOAT), Pin(member(S_TIRE, "MaxHealth"), FLOAT),
                                Pin(member(S_TIRE, "bBlown"), BOOL, default="false")], col=col, row=row)


def tires_get(g: Graph) -> Node:
    return g.var_get("Tires", STRUCT, struct_ref_tire(), container="Array")


def struct_ref_tire():
    from bpgen import struct_ref
    return struct_ref(TIRE)


def tire_elem() -> Pin:
    return Pin("e", STRUCT, sub_object=struct_ref_tire())


def result_bool(g: Graph, value: str) -> Node:
    return g.function_result([Pin("ReturnValue", BOOL, default=value)])


# ---- Phase 7 Task 9 helpers: sources are (node, pin) tuples; a float may also be a literal string ----
def _f(g: Graph, fn: str, a, b=None, out=FLOAT) -> tuple:
    """Pure KismetMathLibrary float op (b None: one input A, e.g. Abs)."""
    ins = [Pin("A", FLOAT, default=a if isinstance(a, str) else None)]
    if b is not None:
        ins.append(Pin("B", FLOAT, default=b if isinstance(b, str) else None))
    n = g.call_static(MATH, fn, inputs=ins, outputs=[Pin("ReturnValue", out, "out")], pure=True)
    if not isinstance(a, str):
        g.link(a[0], a[1], n, "A")
    if b is not None and not isinstance(b, str):
        g.link(b[0], b[1], n, "B")
    return (n, "ReturnValue")


def _fvar(g: Graph, name: str, cat=FLOAT) -> tuple:
    return (g.var_get(name, cat), name)


def _self_vec(g: Graph, fn: str) -> tuple:
    """Actor.GetActorForwardVector / GetActorRightVector / GetActorUpVector / GetVelocity on self (pure)."""
    return (g.call_self_native(ACTOR, fn, outputs=[struct_pin("ReturnValue", VECTOR, "out")], pure=True), "ReturnValue")


def _vscale(g: Graph, v, f) -> tuple:
    n = g.call_static(MATH, "Multiply_VectorFloat", inputs=[struct_pin("A", VECTOR), Pin("B", FLOAT, default=f if isinstance(f, str) else None)],
                      outputs=[struct_pin("ReturnValue", VECTOR, "out")], pure=True)
    g.link(v[0], v[1], n, "A")
    if not isinstance(f, str):
        g.link(f[0], f[1], n, "B")
    return (n, "ReturnValue")


def _vbin(g: Graph, fn: str, a, b, out_cat=None) -> tuple:
    """Add_VectorVector / Dot_VectorVector / Cross_VectorVector; b may be a literal vector string such as '0,0,1'."""
    out = Pin("ReturnValue", FLOAT, "out") if fn == "Dot_VectorVector" else struct_pin("ReturnValue", VECTOR, "out")
    n = g.call_static(MATH, fn, inputs=[struct_pin("A", VECTOR), struct_pin("B", VECTOR, default=b if isinstance(b, str) else None)],
                      outputs=[out], pure=True)
    g.link(a[0], a[1], n, "A")
    if not isinstance(b, str):
        g.link(b[0], b[1], n, "B")
    return (n, "ReturnValue")


def _ang_vel(g: Graph) -> tuple:
    """The Mesh body's angular velocity in degrees/s (pure: the engine function is const)."""
    n = g.call_on(PRIMITIVE, "GetPhysicsAngularVelocityInDegrees", inputs=[Pin("BoneName", NAME, default="None")],
                  outputs=[struct_pin("ReturnValue", VECTOR, "out")], pure=True)
    g.link(mesh(g), "Mesh", n, "self")
    return (n, "ReturnValue")


def _mesh_call(g: Graph, fn: str, vec_pin: str, vec_src, flag_pin: str) -> Node:
    """Mesh.AddForce / AddTorqueInDegrees / AddImpulse(vec, None, flag true): mass-independent (bAccelChange / bVelChange)."""
    n = g.call_on(PRIMITIVE, fn, inputs=[struct_pin(vec_pin, VECTOR), Pin("BoneName", NAME, default="None"), Pin(flag_pin, BOOL, default="true")])
    g.link(mesh(g), "Mesh", n, "self")
    g.link(vec_src[0], vec_src[1], n, vec_pin)
    return n


def spring_arm(g: Graph) -> tuple:
    """The Sedan template's SpringArm (an inherited Blueprint component: set its members at run time, not as class defaults)."""
    return (g.var_get("SpringArm", OBJECT, cls_ref(SPRING_ARM)), "SpringArm")


def chase_camera(g: Graph) -> tuple:
    return (g.var_get("ChaseCamera", OBJECT, cls_ref(CAMERA_COMP)), "ChaseCamera")


def arm_set(g: Graph, prop: str, cat: str, value=None, src=None) -> Node:
    """SpringArm.<prop> := value (a literal) or src (a source tuple)."""
    n = g.var_set_on(SPRING_ARM, prop, cat, default=value)
    arm = spring_arm(g)
    g.link(arm[0], arm[1], n, "self")
    if src is not None:
        g.link(src[0], src[1], n, prop)
    return n


def audio(g: Graph, name: str) -> tuple:
    """EngineAudio / SkidAudio (Task 11): this car's AudioComponents."""
    return (g.var_get(name, OBJECT, cls_ref(AUDIO_COMP)), name)


def audio_call(g: Graph, name: str, fn: str, inputs=None, outputs=None, pure=False) -> Node:
    """An AudioComponent function (SetSound, Play, IsPlaying, SetPitchMultiplier, SetVolumeMultiplier) on EngineAudio / SkidAudio."""
    n = g.call_on(AUDIO_COMP, fn, inputs=inputs, outputs=outputs, pure=pure)
    a = audio(g, name)
    g.link(a[0], a[1], n, "self")
    return n


def look_comp(g: Graph, name: str) -> tuple:
    """Body / WheelFL / LightBar / RoofWeapon ... (Task 13): this car's static mesh components."""
    return (g.var_get(name, OBJECT, cls_ref(STATIC_MESH_COMP)), name)


def set_mesh(g: Graph, name: str, src=None, asset=None) -> Node:
    """<name>.SetStaticMesh(src or the asset) (impure; link execute)."""
    n = g.call_on(STATIC_MESH_COMP, "SetStaticMesh",
                  inputs=[Pin("NewMesh", OBJECT, sub_object=cls_ref(STATIC_MESH), default_object=asset_object(asset) if asset else None)],
                  outputs=[Pin("ReturnValue", BOOL, "out")])
    c = look_comp(g, name)
    g.link(c[0], c[1], n, "self")
    if src is not None:
        g.link(src[0], src[1], n, "NewMesh")
    return n


def set_shown(g: Graph, name: str, value=None, src=None) -> Node:
    """<name>.SetVisibility(value or src, no propagation) (impure; link execute)."""
    n = g.call_on(SCENE_COMP, "SetVisibility", inputs=[Pin("bNewVisibility", BOOL, default=value), Pin("bPropagateToChildren", BOOL, default="false")])
    c = look_comp(g, name)
    g.link(c[0], c[1], n, "self")
    if src is not None:
        g.link(src[0], src[1], n, "bNewVisibility")
    return n


def set_body_material(g: Graph, slot_src, material_src, slot=None) -> Node:
    """Body.SetMaterial(slot, material) (impure; link execute); slot_src None uses the literal slot."""
    n = g.call_on(PRIMITIVE, "SetMaterial", inputs=[Pin("ElementIndex", INT, default=slot), obj_pin("Material", MATERIAL_INTERFACE)])
    c = look_comp(g, "Body")
    g.link(c[0], c[1], n, "self")
    if slot_src is not None:
        g.link(slot_src[0], slot_src[1], n, "ElementIndex")
    g.link(material_src[0], material_src[1], n, "Material")
    return n


def driver_shake(g: Graph, scale="1.0") -> Node:
    """self.PlayDriverShake(LightShake, scale): the light camera shake on the driver's view (players only)."""
    n = g.call_self("PlayDriverShake", inputs=[Pin("Shake", CLASS, sub_object=cls_ref(CAMERA_SHAKE_BASE)), Pin("Scale", FLOAT, default=scale)])
    g.link(g.var_get("LightShake", CLASS, cls_ref(CAMERA_SHAKE_BASE)), "LightShake", n, "Shake")
    return n


def _limited(g: Graph, accel, value) -> tuple:
    """self.LimitDamping(accel, value, DeltaSeconds) inside a function with a DeltaSeconds input."""
    n = g.call_self("LimitDamping", inputs=[Pin("Accel", FLOAT), Pin("Value", FLOAT), Pin("DeltaSeconds", FLOAT)],
                    outputs=[Pin("Limited", FLOAT, "out")], pure=True)
    g.link(accel[0], accel[1], n, "Accel")
    g.link(value[0], value[1], n, "Value")
    g.link_entry("DeltaSeconds", n, "DeltaSeconds")
    return (n, "Limited")


def build() -> Blueprint:
    bp = Blueprint(BP_VEHICLE, parent=SEDAN, description="The race car: health and tires, damage, wrecking, enter/exit, item use; driving and cameras come from the Sedan template.")
    # the car's gun (spec §2); Phase 7 Task 16 (spec §7.2): its shot sound and effects (df.weapon_look), its VisualOrigin the RoofWeapon
    bp.component("Weapon", gen(BPC_WEAPON), Damage=15.0, Range=10000.0, Cooldown=0.2, bDebugTrace=False, **weapon_look(SW_CAR_GUN))
    # Phase 7 Task 11 (spec §5.4): the engine loop (BeginPlay sets the class's EngineSound) and the skid loop, both on the car's
    # root, the Mesh (an SCS root node attaches to the inherited native root); TickAudio drives their pitch and volume
    bp.component("EngineAudio", AUDIO_COMP, "Mesh", auto_activate=True, sound=art_sound(VEHICLES[0].engine_sound))
    bp.component("SkidAudio", AUDIO_COMP, "Mesh", auto_activate=True, sound=SW_SKID, volume_multiplier=0.0)
    # Phase 7 Task 13 (spec §6.1): the visible car. Physics stays on the Sedan template's skeletal Mesh, hidden here while it keeps
    # refreshing its bones; the Dead Fire body and wheels are static meshes on it (Body: the construction script sets the class's
    # BodyMesh). The wheel mesh's rim faces the car's left (-Y), so the right wheels are turned round; the tyre's outward offset is
    # modelled in. The light bar and roof weapon share the Body's Roof socket (the bar is modelled ahead of it); the shield bubble
    # is centred on its origin, so it sits at the Body's centre (Task 12). The shield and flames start hidden; Task 17's
    # RefreshEffectLook shows them while the shield or the boost runs.
    bp.component_default("Mesh", "visible", False)
    bp.component_default("Mesh", "visibility_based_anim_tick_option", TICK_REFRESH_BONES)
    bp.component("Body", STATIC_MESH_COMP, "Mesh", static_mesh=art_mesh(VEHICLES[0].body), **NO_COLLISION)
    for name, bone in CAR_WHEELS:
        turned = {"relative_rotation": {"rotator": {"yaw": 180.0}}} if bone.endswith("Right") else {}
        bp.component(name, STATIC_MESH_COMP, "Mesh", socket=bone, static_mesh=SM_WHEEL, **turned, **NO_COLLISION)
    bp.component("LightBar", STATIC_MESH_COMP, "Body", socket="Roof", static_mesh=SM_LIGHT_BAR, **NO_COLLISION)
    bp.component("RoofWeapon", STATIC_MESH_COMP, "Body", socket="Roof", visible=False, **NO_COLLISION)
    bp.component("ShieldBubble", STATIC_MESH_COMP, "Body", static_mesh=SM_SHIELD_BUBBLE, relative_location={"vector": list(SHIELD_BUBBLE_AT)},
                 visible=False, **NO_COLLISION)
    for name, socket in (("BoostFlameL", "Exhaust_L"), ("BoostFlameR", "Exhaust_R")):
        bp.component(name, STATIC_MESH_COMP, "Body", socket=socket, static_mesh=SM_EXHAUST_FLAME, visible=False, **NO_COLLISION)
    # Phase 7 Task 16 (spec §7.1): the wreck's fire on the bonnet, shown by DestroyVehicle (replaces the stock P_Smoke emitter)
    bp.component("WreckFire", STATIC_MESH_COMP, "Body", static_mesh=SM_EXHAUST_FLAME, override_materials=[MI_FX_FLAME],
                 relative_location={"vector": list(WRECK_FIRE_AT)}, relative_rotation={"rotator": {"pitch": 90.0}},
                 relative_scale3d={"vector": list(WRECK_FIRE_SCALE)}, visible=False, cast_shadow=False, **NO_COLLISION)
    H, E = "Dead Fire|Health", "Dead Fire|Enter Exit"
    bp.variable("MaxHealth", "float", "100", H, editable=True)
    bp.variable("Health", "float", "100", H)
    bp.variable("TireMaxHealth", "float", "30", H, editable=True)
    bp.variable("BlownTireSpeedScale", "float", "0.8", H, editable=True)
    bp.variable("TireHitRadius", "float", "60", H, editable=True)
    bp.variable("Tires", "array<%s>" % struct_spec(S_TIRE), "", H)
    bp.variable("BlownTireCount", "int", "0", H)
    bp.variable("bIsDestroyed", "bool", "false", H)
    bp.variable("bPointDamageHandled", "bool", "false", H)
    bp.variable("ExitMaxSpeedKPH", "float", "10", E, editable=True)
    bp.variable("ExitSideOffset", "float", "220", E, editable=True)
    bp.variable("ExitUpOffset", "float", "100", E, editable=True)
    bp.variable("ExitBehindOffset", "float", "350", E, editable=True)
    bp.variable("Occupant", obj_spec(BP_CHARACTER), "", E)
    bp.variable("LastDriver", "object:" + CONTROLLER, "", E)
    I = "Dead Fire|Items"
    bp.variable("WreckHopImpulse", "float", "600", I, editable=True)
    bp.remove_variable("WreckSmokeEffect")  # Phase 7 Task 16: the stock P_Smoke emitter, replaced by SpawnWreckSmoke and WreckFire
    # Phase 7 Task 16 (spec §5.5, §7.1): tyre smoke and the wreck's smoke (TickTyreSmoke, SpawnWreckSmoke)
    EF = "Dead Fire|Effects"
    for name, default in (("TyreSmokeInterval", 0.08), ("TyreSmokeLateral", 500.0), ("WreckSmokeInterval", 0.15)):
        bp.variable(name, "float", repr(default), EF, editable=True)
        bp.default(name, default)
    bp.variable("WreckSmokeTint", "struct:" + LINEAR_COLOR, "", EF, editable=True)
    bp.default("WreckSmokeTint", {"color": WRECK_SMOKE_TINT})
    bp.variable("BoostRemaining", "float", "0", I)
    bp.variable("ShieldRemaining", "float", "0", I)
    bp.variable("BoostDuration", "float", "2", I, editable=True)
    bp.variable("BoostKickSpeed", "float", "1200", I, editable=True)
    bp.variable("BoostAcceleration", "float", "2500", I, editable=True)
    bp.variable("ShieldDuration", "float", "6", I, editable=True)
    bp.variable("BombDropOffset", "float", "400", I, editable=True)
    bp.variable("MuzzleForward", "float", "300", I, editable=True)
    bp.variable("MuzzleUp", "float", "80", I, editable=True)
    A = "Dead Fire|AI"  # Phase 4: an AI controller's inputs (spec §2.1); the axis events never fire for an AI-possessed pawn
    bp.variable("bAIControlled", "bool", "false", A)
    bp.variable("AIThrottle", "float", "0", A)
    bp.variable("AISteering", "float", "0", A)
    bp.variable("bAIHandbrake", "bool", "false", A)
    bp.variable("AimTarget", "object:" + ACTOR, "", A)  # set by an AI for one shot: the gun and the rocket aim at it (spec §3.2)
    # Phase 5 (spec 2026-10-30 phase 5 §3.2): what makes one car differ from another; the children override these defaults
    ST = "Dead Fire|Stats"
    bp.variable("VehicleName", "string", "SEDAN", ST, editable=True)
    bp.variable("ThrottleScale", "float", "1", ST, editable=True)
    bp.variable("TopSpeedKPH", "float", "0", ST, editable=True)  # 0 = no limiter
    bp.variable("PaintMaterial", "object:" + MATERIAL_INTERFACE, "", ST, editable=True)  # none = the Body mesh's own slot material
    bp.variable("PaintSlot", "int", str(PAINT_SLOT), ST, editable=True)
    # Phase 7 Task 13 (spec §6.1): the class's paint goes on the Body's slot 0 (class defaults: written every apply)
    bp.default("PaintMaterial", VEHICLES[0].paint)
    bp.default("PaintSlot", PAINT_SLOT)
    LK = "Dead Fire|Look"
    for name, spec, default, value in (("BodyMesh", "object:" + STATIC_MESH, "", art_mesh(VEHICLES[0].body)),
                                       ("bHasLightBar", "bool", "true" if VEHICLES[0].light_bar else "false", VEHICLES[0].light_bar),
                                       ("WheelMesh", "object:" + STATIC_MESH, "", SM_WHEEL),
                                       ("RimMesh", "object:" + STATIC_MESH, "", SM_WHEEL_RIM),
                                       ("CharredMaterial", "object:" + MATERIAL_INTERFACE, "", MI_PAINT_CHARRED)):
        bp.variable(name, spec, default, LK, editable=True)
        bp.default(name, value)
    # Phase 7 Task 7 (spec §5.2): handling data, read by the arcade handling from Task 8; no behaviour change yet.
    # SteerAtSpeed, GripAssist and DownforceG are per class (class defaults from VEHICLES, like ThrottleScale).
    HD = "Dead Fire|Handling"
    row0 = VEHICLES[0]
    for name, default in (("SteerRiseRate", 4), ("SteerReturnRate", 7), ("SteerAtSpeed", row0.steer_at_speed), ("SteerSpeedRef", 150),
                          ("GripAssist", row0.grip_assist), ("DriftGrip", 0.3), ("DownforceG", row0.downforce_g), ("DownforceCap", 1960),
                          ("StabilityDamping", 2.0), ("CenterOfMassZ", -25), ("DriftMinSpeed", 40), ("DriftExitSpeed", 25),
                          ("DriftSteerMin", 0.3), ("DriftYawAccel", 120), ("DriftBoostMinSeconds", 1.0), ("DriftBoostSpeed", 500),
                          ("AirDelay", 0.25), ("AirDamping", 1.5), ("AirLevelAccel", 180), ("AirControlAccel", 90), ("GroundProbe", 150),
                          ("ResetMaxSpeed", 15), ("ResetCooldown", 3), ("ResetLift", 150)):
        bp.variable(name, "float", repr(float(default)), HD, editable=True)
        bp.default(name, float(default))
    # Phase 7 Task 9 (spec §5.2): the arcade layer's state. ArcadeSteer / ArcadeThrottle / bArcadeHandbrake are the inputs the
    # layer reads, written by TickDriveOverrides every frame (player: smoothed steer + held handbrake; AI: its own inputs).
    HS = "Dead Fire|Handling State"
    for name, spec, default in (("SmoothedSteer", "float", "0.0"), ("bDrifting", "bool", "false"), ("DriftStartTime", "float", "0.0"),
                                ("AirborneSince", "float", "-1.0"), ("bGrounded", "bool", "false"), ("DriftBoostCount", "int", "0"),
                                ("ArcadeSteer", "float", "0.0"), ("ArcadeThrottle", "float", "0.0"), ("bArcadeHandbrake", "bool", "false"),
                                ("bHandbrakeHeld", "bool", "false"),
                                # Phase 7 Task 10: the reset cooldown's clock, look-back, the chase rotation the arm returns to,
                                # and the look-back snap (the arm's rotation lag stays off for one frame after a turn)
                                ("LastResetTime", "float", "-1000.0"), ("bLookBack", "bool", "false"),
                                ("ArmBaseRotation", "struct:" + ROTATOR, ""), ("bSnapArm", "bool", "false")):
        bp.variable(name, spec, default, HS)
    bp.default("AirborneSince", -1.0)
    bp.default("LastResetTime", -1000.0)
    bp.dispatcher("OnDriftBoost", [])
    # Phase 7 Task 10 (spec §5.3): the chase camera and the camera shakes
    CAM = "Dead Fire|Camera"
    for name, default in (("FOVInterpSpeed", 4), ("ChaseLagSpeed", 10), ("ChaseRotationLagSpeed", 8), ("LandShakeAirTime", 0.5)):
        bp.variable(name, "float", repr(float(default)), CAM, editable=True)
        bp.default(name, float(default))
    bp.variable("LightShake", "class:" + CAMERA_SHAKE_BASE, "", CAM, editable=True)
    bp.default("LightShake", "class:" + BP_SHAKE_LIGHT)
    # Phase 7 Task 11 (spec §5.4): the engine loop per class (VEHICLES engine_sound), the crash sound, the crash threshold (a
    # hit's normal impulse, kg cm/s, set from the logged run in Task 11 Step 3) and its cooldown; LastCrashTime is state
    AU = "Dead Fire|Audio"
    bp.variable("EngineSound", "object:" + SOUND_BASE, "", AU, editable=True)
    bp.default("EngineSound", art_sound(VEHICLES[0].engine_sound))
    bp.variable("CrashSound", "object:" + SOUND_BASE, "", AU, editable=True)
    bp.default("CrashSound", SW_CRASH)
    for name, default in (("CrashImpulse", CRASH_IMPULSE), ("CrashCooldown", 0.5)):
        bp.variable(name, "float", repr(float(default)), AU, editable=True)
        bp.default(name, float(default))
    bp.variable("LastCrashTime", "float", "-1000.0", HS)
    bp.default("LastCrashTime", -1000.0)
    bp.variable("NextTyreSmokeTime", "float", "0.0", HS)  # Phase 7 Task 16: the next tyre-smoke puff, game seconds
    # Phase 7 Task 16 (spec §7.2, §7.5): the tyre pop and the rocket launch
    for name, sound in (("TirePopSound", SW_TIRE_POP), ("RocketLaunchSound", SW_ROCKET_LAUNCH)):
        bp.variable(name, "object:" + SOUND_BASE, "", AU, editable=True)
        bp.default(name, sound)
    # Phase 7 Task 17 (spec §7.5): the boost and shield sounds, the blocked hit's flash on the bubble, and the look's state (the
    # bubble's dynamic material, its own glow, and whether the bubble shows, so the shield's end is heard once)
    for name, sound in (("BoostSound", SW_BOOST), ("ShieldUpSound", SW_SHIELD_UP), ("ShieldDownSound", SW_SHIELD_DOWN),
                        ("ShieldHitSound", SW_SHIELD_HIT)):
        bp.variable(name, "object:" + SOUND_BASE, "", AU, editable=True)
        bp.default(name, sound)
    for name, default in (("ShieldHitGlow", 3.0), ("ShieldHitSeconds", 0.15)):
        bp.variable(name, "float", repr(default), EF, editable=True)
        bp.default(name, default)
    bp.variable("ShieldMID", "object:" + MID, "", HS)
    bp.variable("ShieldBaseGlow", "float", "1.0", HS)
    bp.variable("bShieldShown", "bool", "false", HS)

    bp.dispatcher("OnVehicleDamaged", ["Damage:float", "TireIndex:int"])
    bp.dispatcher("OnTireBlown", ["TireIndex:int"])
    bp.dispatcher("OnVehicleDestroyed", ["Vehicle:" + obj_spec(BP_VEHICLE), "Killer:object:" + CONTROLLER])
    bp.dispatcher("OnOccupantEntered", ["Character:" + obj_spec(BP_CHARACTER)])
    bp.dispatcher("OnOccupantExited", ["Character:" + obj_spec(BP_CHARACTER)])

    # ---- InitTires: Tires = four fresh entries ----
    g = bp.function("InitTires", doc="Four fresh tires at TireMaxHealth (the wheels show their tyres again).")
    clear = g.call_array("KismetArrayLibrary", "Array_Clear", tire_elem(), pure=False)
    arr = tires_get(g)
    g.link(arr, "Tires", clear, "TargetArray")
    g.link_entry("then", clear, "execute")
    prev = clear
    for bone in WHEEL_BONES:
        mk = make_tire(g, bone_default=bone)
        mx = g.var_get("TireMaxHealth", FLOAT)
        g.link(mx, "TireMaxHealth", mk, member(S_TIRE, "Health"))
        g.link(mx, "TireMaxHealth", mk, member(S_TIRE, "MaxHealth"))
        add = g.call_array("KismetArrayLibrary", "Array_Add", tire_elem(),
                           inputs=[Pin("NewItem", STRUCT, sub_object=struct_ref_tire())],
                           outputs=[Pin("ReturnValue", INT, "out")], pure=False)
        a2 = tires_get(g)
        g.link(a2, "Tires", add, "TargetArray")
        g.link(mk, TIRE.rsplit(".", 1)[1], add, "NewItem")
        g.exec(prev, add)
        prev = add
    zero = g.var_set("BlownTireCount", INT, default="0")
    g.exec(prev, zero, g.call_self("RefreshWheels"))  # Phase 7 Task 13

    # ---- Phase 7 Task 13 (spec §6.1, §7.5): the car's look ----
    g = bp.function("RefreshWheels", doc="Each wheel shows RimMesh while its tyre is blown, else WheelMesh (Tires index i is the i-th wheel: FL, FR, RL, RR).")
    prev = [("entry", "then")]
    for i, (name, bone) in enumerate(CAR_WHEELS):
        get = g.call_array("KismetArrayLibrary", "Array_Get", tire_elem(), inputs=[Pin("Index", INT, default=str(i))],
                           outputs=[Pin("Item", STRUCT, "out", struct_ref_tire())])
        g.link(tires_get(g), "Tires", get, "TargetArray")
        br = break_tire(g)
        g.link(get, "Item", br, TIRE.rsplit(".", 1)[1])
        b = g.branch()
        g.note(b, "%s blown?" % bone)
        g.link(br, member(S_TIRE, "bBlown"), b, "Condition")
        for src in prev:
            g.link(src[0], src[1], b, "execute")
        rim = set_mesh(g, name, src=(g.var_get("RimMesh", OBJECT, cls_ref(STATIC_MESH)), "RimMesh"))
        tyre = set_mesh(g, name, src=(g.var_get("WheelMesh", OBJECT, cls_ref(STATIC_MESH)), "WheelMesh"))
        g.link(b, "then", rim, "execute")
        g.link(b, "else", tyre, "execute")
        prev = [(rim, "then"), (tyre, "then")]

    g = bp.function("ApplyPaint", doc="PaintMaterial, when set, on the Body's PaintSlot (BeginPlay; SpawnNPCs after giving a rival the gang paint).")
    paint = g.var_get("PaintMaterial", OBJECT, cls_ref(MATERIAL_INTERFACE))
    has_paint = is_valid(g)
    g.link(paint, "PaintMaterial", has_paint, "Object")
    bpaint = g.branch()
    g.note(bpaint, "a paint of its own?")
    g.link(has_paint, "ReturnValue", bpaint, "Condition")
    g.link_entry("then", bpaint, "execute")
    put = set_body_material(g, (g.var_get("PaintSlot", INT), "PaintSlot"), (paint, "PaintMaterial"))
    g.link(bpaint, "then", put, "execute")

    RCL = gen(BPC_RACER)
    g = bp.function("RefreshRoofWeapon", locals=["Racer:object:" + RCL],
                    doc="The roof weapon shows the driver's held weapon: SM_DF_RoofLauncher while its racer holds an RPG, else SM_DF_RoofGun "
                        "while it holds a Gun, else hidden (also with no driver or outside a race). Called after ApplyItem, on "
                        "GrantItem and respawn, and on Enter/Exit.")
    to_gm = cast_to(g, BP_GM)
    g.link(get_game_mode(g), "ReturnValue", to_gm, "Object")
    g.link_entry("then", to_gm, "execute")
    hide = set_shown(g, "RoofWeapon", "false")
    g.link(to_gm, "CastFailed", hide, "execute")
    driver = g.call_self_native(PAWN, "GetController", outputs=[obj_pin("ReturnValue", CONTROLLER, "out")], pure=True)
    find = g.call_on(GMC, "FindRacer", inputs=[obj_pin("C", CONTROLLER)], outputs=[obj_pin("Racer", RCL, "out")], pure=True)
    g.link(to_gm, as_pin(BP_GM), find, "self")
    g.link(driver, "ReturnValue", find, "C")
    keep = g.local_set("Racer", OBJECT, sub_object=cls_ref(RCL))
    g.link(find, "Racer", keep, "Racer")
    g.link(to_gm, "then", keep, "execute")
    has_racer = is_valid(g)
    g.link(keep, "Output_Get", has_racer, "Object")
    bracer = g.branch()
    g.note(bracer, "a driver with a racer?")
    g.link(has_racer, "ReturnValue", bracer, "Condition")
    g.exec(keep, bracer)
    g.link(bracer, "else", hide, "execute")

    def holds(item):
        n = g.call_on(RCL, "HasType", inputs=[enum_pin("Type", E_ITEM_TYPE, default=item)], outputs=[Pin("ReturnValue", BOOL, "out")], pure=True)
        g.link(g.local_get("Racer", OBJECT, cls_ref(RCL)), "Racer", n, "self")
        return n

    brpg = g.branch()
    g.note(brpg, "holds an RPG? (wins over a Gun)")
    g.link(holds(ITEM_RPG), "ReturnValue", brpg, "Condition")
    g.link(bracer, "then", brpg, "execute")
    launcher = set_mesh(g, "RoofWeapon", asset=SM_ROOF_LAUNCHER)
    g.link(brpg, "then", launcher, "execute")
    bgun = g.branch()
    g.note(bgun, "holds a Gun?")
    g.link(holds(ITEM_GUN), "ReturnValue", bgun, "Condition")
    g.link(brpg, "else", bgun, "execute")
    gun = set_mesh(g, "RoofWeapon", asset=SM_ROOF_GUN)
    g.link(bgun, "then", gun, "execute")
    g.link(bgun, "else", hide, "execute")
    show = set_shown(g, "RoofWeapon", "true")
    g.link(launcher, "then", show, "execute")
    g.link(gun, "then", show, "execute")

    # ---- GetSpeedKPH ----
    g = bp.function("GetSpeedKPH", doc="Absolute forward speed in km/h.", outputs=["KPH:float"], pure=True)
    fwd = mv_call(g, "GetForwardSpeed", outputs=[Pin("ReturnValue", FLOAT, "out")], pure=True)
    ab = g.call_static(MATH, "Abs", inputs=[Pin("A", FLOAT)], outputs=[Pin("ReturnValue", FLOAT, "out")], pure=True)
    mul = math2(g, "Multiply_FloatFloat", FLOAT, b="0.036")
    g.link(fwd, "ReturnValue", ab, "A")
    g.link(ab, "ReturnValue", mul, "A")
    g.link_result(mul, "ReturnValue", "KPH")
    g.link_entry("then", "result", "execute")

    # ---- GetGearString: R / N / number ----
    g = bp.function("GetGearString", doc="R, N or the gear number for the HUD.", outputs=["Gear:string"], pure=True)
    gear = mv_call(g, "GetCurrentGear", outputs=[Pin("ReturnValue", INT, "out")], pure=True)
    lt = compare(g, "Less_IntInt", INT, b="0")
    eq = compare(g, "EqualEqual_IntInt", INT, b="0")
    g.link(gear, "ReturnValue", lt, "A")
    g.link(gear, "ReturnValue", eq, "A")
    b1 = g.branch()
    b2 = g.branch()
    g.link(lt, "ReturnValue", b1, "Condition")
    g.link(eq, "ReturnValue", b2, "Condition")
    r_r = g.function_result([Pin("Gear", "string", default="R")])
    r_n = g.function_result([Pin("Gear", "string", default="N")])
    conv = g.call_static("KismetStringLibrary", "Conv_IntToString", inputs=[Pin("InInt", INT)], outputs=[Pin("ReturnValue", "string", "out")], pure=True)
    g.link(gear, "ReturnValue", conv, "InInt")
    r_num = g.function_result([Pin("Gear", "string")])
    g.link(conv, "ReturnValue", r_num, "Gear")
    g.link_entry("then", b1, "execute")
    g.link(b1, "then", r_r, "execute")
    g.link(b1, "else", b2, "execute")
    g.link(b2, "then", r_n, "execute")
    g.link(b2, "else", r_num, "execute")

    # ---- GetBlownTireCount / GetThrottleScale / IsBelowExitSpeed / CanBeEntered ----
    g = bp.function("GetBlownTireCount", doc="How many tires are blown.", outputs=["Count:int"], pure=True)
    c = g.var_get("BlownTireCount", INT)
    g.link_result(c, "BlownTireCount", "Count")
    g.link_entry("then", "result", "execute")

    g = bp.function("GetThrottleScale", doc="BlownTireSpeedScale to the power of the blown tire count.", outputs=["Scale:float"], pure=True)
    base = g.var_get("BlownTireSpeedScale", FLOAT)
    cnt = g.var_get("BlownTireCount", INT)
    conv = g.call_static(MATH, "Conv_IntToFloat", inputs=[Pin("InInt", INT)], outputs=[Pin("ReturnValue", FLOAT, "out")], pure=True)
    pw = g.call_static(MATH, "MultiplyMultiply_FloatFloat", inputs=[Pin("Base", FLOAT), Pin("Exp", FLOAT)],
                       outputs=[Pin("ReturnValue", FLOAT, "out")], pure=True)
    g.link(cnt, "BlownTireCount", conv, "InInt")
    g.link(base, "BlownTireSpeedScale", pw, "Base")
    g.link(conv, "ReturnValue", pw, "Exp")
    g.link_result(pw, "ReturnValue", "Scale")
    g.link_entry("then", "result", "execute")

    g = bp.function("IsBelowExitSpeed", doc="Slow enough to get out.", outputs=["ReturnValue:bool"], pure=True)
    sp = g.call_self("GetSpeedKPH", outputs=[Pin("KPH", FLOAT, "out")], pure=True)
    mx = g.var_get("ExitMaxSpeedKPH", FLOAT)
    lt = compare(g, "Less_FloatFloat", FLOAT)
    g.link(sp, "KPH", lt, "A")
    g.link(mx, "ExitMaxSpeedKPH", lt, "B")
    g.link_result(lt, "ReturnValue", "ReturnValue")
    g.link_entry("then", "result", "execute")

    g = bp.function("CanBeEntered", doc="No occupant and not wrecked.", outputs=["ReturnValue:bool"], pure=True)
    occ = g.var_get("Occupant", OBJECT, cls_ref(CC))
    valid = is_valid(g)
    g.link(occ, "Occupant", valid, "Object")
    no_occ = not_bool(g)
    g.link(valid, "ReturnValue", no_occ, "A")
    dest = g.var_get("bIsDestroyed", BOOL)
    no_dest = not_bool(g)
    g.link(dest, "bIsDestroyed", no_dest, "A")
    both = and_bool(g)
    g.link(no_occ, "ReturnValue", both, "A")
    g.link(no_dest, "ReturnValue", both, "B")
    g.link_result(both, "ReturnValue", "ReturnValue")
    g.link_entry("then", "result", "execute")

    # ---- FindTireIndexForHit(BoneName, ImpactPoint) -> Index ----
    g = bp.function("FindTireIndexForHit", doc="The tire hit: by wheel bone, else the nearest wheel socket within TireHitRadius; -1 for the body.", inputs=["BoneName:name", "ImpactPoint:struct:" + VECTOR],
                    outputs=["Index:int"], locals=["Best:int=-1", "BestDist:float=0"])
    init = g.local_set("BestDist", FLOAT)
    rad = g.var_get("TireHitRadius", FLOAT)
    g.link(rad, "TireHitRadius", init, "BestDist")
    g.link_entry("then", init, "execute")
    loop1 = g.for_each(tire_elem())
    t1 = tires_get(g)
    g.link(t1, "Tires", loop1, "Array")
    g.link(init, "then", loop1, "Exec")
    br1 = break_tire(g)
    g.link(loop1, "Array Element", br1, TIRE.rsplit(".", 1)[1])
    eqn = compare(g, "EqualEqual_NameName", NAME)
    g.link(br1, member(S_TIRE, "BoneName"), eqn, "A")
    g.link_entry("BoneName", eqn, "B")
    b1 = g.branch()
    g.link(loop1, "LoopBody", b1, "execute")
    g.link(eqn, "ReturnValue", b1, "Condition")
    ret_match = g.function_result([Pin("Index", INT)])
    g.link(b1, "then", ret_match, "execute")
    g.link(loop1, "Array Index", ret_match, "Index")
    # second pass: nearest wheel socket within the radius
    loop2 = g.for_each(tire_elem())
    t2 = tires_get(g)
    g.link(t2, "Tires", loop2, "Array")
    g.link(loop1, "Completed", loop2, "Exec")
    br2 = break_tire(g)
    g.link(loop2, "Array Element", br2, TIRE.rsplit(".", 1)[1])
    m = mesh(g)
    sock = g.call_on(SCENE_COMP, "GetSocketLocation", inputs=[Pin("InSocketName", NAME)],
                     outputs=[struct_pin("ReturnValue", VECTOR, "out")], pure=True)
    g.link(m, "Mesh", sock, "self")
    g.link(br2, member(S_TIRE, "BoneName"), sock, "InSocketName")
    dist = g.call_static(MATH, "Vector_Distance", inputs=[struct_pin("V1", VECTOR), struct_pin("V2", VECTOR)],
                         outputs=[Pin("ReturnValue", FLOAT, "out")], pure=True)
    g.link(sock, "ReturnValue", dist, "V1")
    g.link_entry("ImpactPoint", dist, "V2")
    bd = g.local_get("BestDist", FLOAT)
    lt = compare(g, "Less_FloatFloat", FLOAT)
    g.link(dist, "ReturnValue", lt, "A")
    g.link(bd, "BestDist", lt, "B")
    b2 = g.branch()
    g.link(loop2, "LoopBody", b2, "execute")
    g.link(lt, "ReturnValue", b2, "Condition")
    sd = g.local_set("BestDist", FLOAT)
    g.link(dist, "ReturnValue", sd, "BestDist")
    sb = g.local_set("Best", INT)
    g.link(loop2, "Array Index", sb, "Best")
    g.link(b2, "then", sd, "execute")
    g.exec(sd, sb)
    best = g.local_get("Best", INT)
    g.link_result(best, "Best", "Index")
    g.link_extra(loop2, "Completed", "result", "execute")

    # ---- ApplyTireDamage(Index, Damage) ----
    g = bp.function("ApplyTireDamage", doc="Takes health off one tire; at 0 it is blown, the count and OnTireBlown update and the wheel shows its rim.",
                    inputs=["Index:int", "Damage:float"])
    get = g.call_array("KismetArrayLibrary", "Array_Get", tire_elem(), inputs=[Pin("Index", INT)],
                       outputs=[Pin("Item", STRUCT, "out", struct_ref_tire())])
    ta = tires_get(g)
    g.link(ta, "Tires", get, "TargetArray")
    g.link_entry("Index", get, "Index")
    br = break_tire(g)
    g.link(get, "Item", br, TIRE.rsplit(".", 1)[1])
    already = g.branch()
    g.link(br, member(S_TIRE, "bBlown"), already, "Condition")
    g.link_entry("then", already, "execute")
    sub = math2(g, "Subtract_FloatFloat", FLOAT)
    g.link(br, member(S_TIRE, "Health"), sub, "A")
    g.link_entry("Damage", sub, "B")
    clamp = g.call_static(MATH, "FMax", inputs=[Pin("A", FLOAT), Pin("B", FLOAT, default="0.0")],
                          outputs=[Pin("ReturnValue", FLOAT, "out")], pure=True)
    g.link(sub, "ReturnValue", clamp, "A")
    blown = compare(g, "LessEqual_FloatFloat", FLOAT, b="0.0")
    g.link(clamp, "ReturnValue", blown, "A")
    mk = make_tire(g)
    g.link(br, member(S_TIRE, "BoneName"), mk, member(S_TIRE, "BoneName"))
    g.link(clamp, "ReturnValue", mk, member(S_TIRE, "Health"))
    g.link(br, member(S_TIRE, "MaxHealth"), mk, member(S_TIRE, "MaxHealth"))
    g.link(blown, "ReturnValue", mk, member(S_TIRE, "bBlown"))
    setn = g.call_array("KismetArrayLibrary", "Array_Set", tire_elem(),
                        inputs=[Pin("Index", INT), Pin("Item", STRUCT, sub_object=struct_ref_tire()),
                                Pin("bSizeToFit", BOOL, default="false")], pure=False)
    tb = tires_get(g)
    g.link(tb, "Tires", setn, "TargetArray")
    g.link_entry("Index", setn, "Index")
    g.link(mk, TIRE.rsplit(".", 1)[1], setn, "Item")
    g.link(already, "else", setn, "execute")
    bb = g.branch()
    g.link(blown, "ReturnValue", bb, "Condition")
    g.exec(setn, bb)
    cnt = g.var_get("BlownTireCount", INT)
    inc = math2(g, "Add_IntInt", INT, b="1")
    g.link(cnt, "BlownTireCount", inc, "A")
    setc = g.var_set("BlownTireCount", INT)
    g.link(inc, "ReturnValue", setc, "BlownTireCount")
    g.link(bb, "then", setc, "execute")
    fire = g.call_delegate("OnTireBlown", [Pin("TireIndex", INT)])
    g.link_entry("Index", fire, "TireIndex")
    refresh = g.call_self("RefreshWheels")  # Phase 7 Task 13: the blown wheel shows its bare rim
    g.exec(setc, fire, refresh)
    # Phase 7 Task 16 (spec §7.1): the pop at the wheel: sparks, SW_DF_TirePop and a light shake for a player driver
    wheel_at = g.call_on(SCENE_COMP, "GetSocketLocation", inputs=[Pin("InSocketName", NAME)], outputs=[struct_pin("ReturnValue", VECTOR, "out")], pure=True)
    g.link(mesh(g), "Mesh", wheel_at, "self")
    g.link(br, member(S_TIRE, "BoneName"), wheel_at, "InSocketName")
    sp_first, sp_last, _ = spawn_fx(g, BP_FX_SPARKS, transform_at(g, (wheel_at, "ReturnValue")))
    g.exec(refresh, sp_first)
    pop = play_sound_at(g, (g.var_get("TirePopSound", OBJECT, cls_ref(SOUND_BASE)), "TirePopSound"), (wheel_at, "ReturnValue"))
    g.exec(sp_last, pop, driver_shake(g))

    # ---- BlowNearestTire(Point, Damage): explosion tire blast on the wheel socket nearest the point (spec §5) ----
    g = bp.function("BlowNearestTire", doc="Explosion tire blast on the wheel nearest the point (skipped when wrecked or shielded).", inputs=["Point:struct:" + VECTOR, "Damage:float"], locals=["Best:int=-1", "BestDist:float=1000000000"])
    dead = g.var_get("bIsDestroyed", BOOL)
    shielded = g.call_self("IsShielded", outputs=[Pin("ReturnValue", BOOL, "out")], pure=True)
    skip = or_bool(g)
    g.link(dead, "bIsDestroyed", skip, "A")
    g.link(shielded, "ReturnValue", skip, "B")
    b = g.branch()
    g.link(skip, "ReturnValue", b, "Condition")
    g.link_entry("then", b, "execute")
    loop = g.for_each(tire_elem())
    t0 = tires_get(g)
    g.link(t0, "Tires", loop, "Array")
    g.link(b, "else", loop, "Exec")
    br = break_tire(g)
    g.link(loop, "Array Element", br, TIRE.rsplit(".", 1)[1])
    m = mesh(g)
    sock = g.call_on(SCENE_COMP, "GetSocketLocation", inputs=[Pin("InSocketName", NAME)],
                     outputs=[struct_pin("ReturnValue", VECTOR, "out")], pure=True)
    g.link(m, "Mesh", sock, "self")
    g.link(br, member(S_TIRE, "BoneName"), sock, "InSocketName")
    dist = g.call_static(MATH, "Vector_Distance", inputs=[struct_pin("V1", VECTOR), struct_pin("V2", VECTOR)],
                         outputs=[Pin("ReturnValue", FLOAT, "out")], pure=True)
    g.link(sock, "ReturnValue", dist, "V1")
    g.link_entry("Point", dist, "V2")
    bd = g.local_get("BestDist", FLOAT)
    lt = compare(g, "Less_FloatFloat", FLOAT)
    g.link(dist, "ReturnValue", lt, "A")
    g.link(bd, "BestDist", lt, "B")
    b2 = g.branch()
    g.link(loop, "LoopBody", b2, "execute")
    g.link(lt, "ReturnValue", b2, "Condition")
    sd = g.local_set("BestDist", FLOAT)
    g.link(dist, "ReturnValue", sd, "BestDist")
    sb = g.local_set("Best", INT)
    g.link(loop, "Array Index", sb, "Best")
    g.link(b2, "then", sd, "execute")
    g.exec(sd, sb)
    best = g.local_get("Best", INT)
    ge0 = compare(g, "GreaterEqual_IntInt", INT, b="0")
    g.link(best, "Best", ge0, "A")
    bb = g.branch()
    g.link(ge0, "ReturnValue", bb, "Condition")
    g.link(loop, "Completed", bb, "execute")
    apply = g.call_self("ApplyTireDamage", inputs=[Pin("Index", INT), Pin("Damage", FLOAT)])
    best2 = g.local_get("Best", INT)
    g.link(best2, "Best", apply, "Index")
    g.link_entry("Damage", apply, "Damage")
    g.link(bb, "then", apply, "execute")

    # ---- TakeDamageInternal(Damage, TireIndex, Instigator) ----
    g = bp.function("TakeDamageInternal", doc="Routes damage to a tire or the body (ignored while shielded or wrecked); the body at 0 wrecks the car.", inputs=["Damage:float", "TireIndex:int", "Instigator:object:" + CONTROLLER])
    dead = g.var_get("bIsDestroyed", BOOL)
    bdead = g.branch()
    g.link(dead, "bIsDestroyed", bdead, "Condition")
    g.link_entry("then", bdead, "execute")
    ge0 = compare(g, "GreaterEqual_IntInt", INT, b="0")
    g.link_entry("TireIndex", ge0, "A")
    btire = g.branch()
    g.link(ge0, "ReturnValue", btire, "Condition")
    shielded = g.call_self("IsShielded", outputs=[Pin("ReturnValue", BOOL, "out")], pure=True)
    bsh = g.branch()
    g.link(shielded, "ReturnValue", bsh, "Condition")
    g.link(bdead, "else", bsh, "execute")
    g.link(bsh, "else", btire, "execute")  # shielded: nothing happens (spec §2) but the bubble's flash
    real = _f(g, "Greater_FloatFloat", ("entry", "Damage"), "0.0", BOOL)  # Phase 7 Task 17 (spec §7.5): a blocked hit flashes the bubble
    bblock = g.branch()
    g.note(bblock, "a real hit blocked? flash the bubble")
    g.link(real[0], real[1], bblock, "Condition")
    g.link(bsh, "then", bblock, "execute")
    g.link(bblock, "then", g.call_self("ShieldHit"), "execute")
    apply = g.call_self("ApplyTireDamage", inputs=[Pin("Index", INT), Pin("Damage", FLOAT)])
    g.link_entry("TireIndex", apply, "Index")
    g.link_entry("Damage", apply, "Damage")
    g.link(btire, "then", apply, "execute")
    h = g.var_get("Health", FLOAT)
    sub = math2(g, "Subtract_FloatFloat", FLOAT)
    g.link(h, "Health", sub, "A")
    g.link_entry("Damage", sub, "B")
    clamp = g.call_static(MATH, "FMax", inputs=[Pin("A", FLOAT), Pin("B", FLOAT, default="0.0")],
                          outputs=[Pin("ReturnValue", FLOAT, "out")], pure=True)
    g.link(sub, "ReturnValue", clamp, "A")
    seth = g.var_set("Health", FLOAT)
    g.link(clamp, "ReturnValue", seth, "Health")
    g.link(btire, "else", seth, "execute")
    fire = g.call_delegate("OnVehicleDamaged", [Pin("Damage", FLOAT), Pin("TireIndex", INT)])
    g.link_entry("Damage", fire, "Damage")
    g.link_entry("TireIndex", fire, "TireIndex")
    g.exec(apply, fire)
    g.exec(seth, fire)
    # Phase 7 Task 10 (spec §5.3): a hit taken shakes the driver's view (players only)
    hit = _f(g, "Greater_FloatFloat", ("entry", "Damage"), "0.0", BOOL)
    bhit = g.branch()
    g.note(bhit, "a real hit? shake the driver's view")
    g.link(hit[0], hit[1], bhit, "Condition")
    g.exec(fire, bhit)
    hit_shake = driver_shake(g)
    g.link(bhit, "then", hit_shake, "execute")
    hit_hud = g.call_self("ShowDriverDamage")  # Phase 7 Task 18 (spec §7.6): and the driver's damage vignette
    g.exec(hit_shake, hit_hud)
    h2 = g.var_get("Health", FLOAT)
    le = compare(g, "LessEqual_FloatFloat", FLOAT, b="0.0")
    g.link(h2, "Health", le, "A")
    bdie = g.branch()
    g.link(le, "ReturnValue", bdie, "Condition")
    g.exec(hit_hud, bdie)
    g.link(bhit, "else", bdie, "execute")
    kill = g.call_self("DestroyVehicle", inputs=[obj_pin("Killer", CONTROLLER)])
    g.link_entry("Instigator", kill, "Killer")
    g.link(bdie, "then", kill, "execute")

    # ---- DestroyVehicle(Killer) ----
    g = bp.function("DestroyVehicle", doc="Wrecks the car once: handbrake, charred paint and trim, hop, smoke, effects-only explosion, OnVehicleDestroyed, "
                    "the GameMode notified.", inputs=["Killer:object:" + CONTROLLER])
    dead = g.var_get("bIsDestroyed", BOOL)
    b = g.branch()
    g.link(dead, "bIsDestroyed", b, "Condition")
    g.link_entry("then", b, "execute")
    mark = g.var_set("bIsDestroyed", BOOL, default="true")
    g.link(b, "else", mark, "execute")
    hb = set_handbrake(g, "true")
    # Phase 7 Task 13 (spec §6.1): the wreck's paint (slot 0) and trim (slot 1) turn to CharredMaterial
    charred = [set_body_material(g, None, (g.var_get("CharredMaterial", OBJECT, cls_ref(MATERIAL_INTERFACE)), "CharredMaterial"), slot=str(i))
               for i in (0, 1)]
    g.exec(mark, hb, *charred)
    # Phase 3 wreck effects (spec §5): hop, smoke, then the effects-only explosion through the GameMode
    m = mesh(g)
    hop = g.call_on(PRIMITIVE, "AddImpulse", inputs=[struct_pin("Impulse", VECTOR), Pin("BoneName", NAME, default="None"),
                                                     Pin("bVelChange", BOOL, default="true")])
    g.link(m, "Mesh", hop, "self")
    hopv = g.call_static(MATH, "MakeVector", inputs=[Pin("X", FLOAT, default="0.0"), Pin("Y", FLOAT, default="0.0"), Pin("Z", FLOAT)],
                         outputs=[struct_pin("ReturnValue", VECTOR, "out")], pure=True)
    hi = g.var_get("WreckHopImpulse", FLOAT)
    g.link(hi, "WreckHopImpulse", hopv, "Z")
    g.link(hopv, "ReturnValue", hop, "Impulse")
    g.exec(charred[-1], hop)
    # Phase 7 Task 16 (spec §7.1): the fire on the bonnet and a looping timer for the dark smoke (SpawnWreckSmoke)
    burn = set_shown(g, "WreckFire", "true")
    smoke = timer(g, "SpawnWreckSmoke", (g.var_get("WreckSmokeInterval", FLOAT), "WreckSmokeInterval"))
    g.exec(hop, burn, smoke)
    fire = g.call_delegate("OnVehicleDestroyed", [obj_pin("Vehicle", VC), obj_pin("Killer", CONTROLLER)])
    me = g.self_node()
    g.link(me, "self", fire, "Vehicle")
    g.link_entry("Killer", fire, "Killer")
    g.exec(smoke, fire)
    gm = get_game_mode(g)
    cast = cast_to(g, BP_GM)
    g.link(gm, "ReturnValue", cast, "Object")
    g.exec(fire, cast)
    loc = self_actor_location(g)
    boom = g.call_on(GMC, "SpawnExplosion", inputs=[struct_pin("Location", VECTOR), Pin("Damage", FLOAT, default="0.0"),
                                                    Pin("Radius", FLOAT, default="0.0"), obj_pin("InstigatedBy", CONTROLLER),
                                                    obj_pin("Causer", ACTOR), Pin("bBlowTires", BOOL, default="false")])
    g.link(cast, as_pin(BP_GM), boom, "self")
    g.link(loc, "ReturnValue", boom, "Location")
    g.link_entry("Killer", boom, "InstigatedBy")
    me3 = g.self_node()
    g.link(me3, "self", boom, "Causer")
    g.link(cast, "then", boom, "execute")
    notify = g.call_on(GMC, "NotifyVehicleDestroyed", inputs=[obj_pin("Victim", VC), obj_pin("Killer", CONTROLLER)])
    g.link(cast, as_pin(BP_GM), notify, "self")
    me2 = g.self_node()
    g.link(me2, "self", notify, "Victim")
    g.link_entry("Killer", notify, "Killer")
    g.exec(boom, notify)

    # ---- TeleportAndStop(NewTransform) ----
    g = bp.function("TeleportAndStop", doc="Clears the drive state, cuts the camera lag for a frame, moves the car and zeroes its velocity "
                    "(respawns, resets and tests).",
                    inputs=["NewTransform:struct:" + TRANSFORM])
    clear = g.call_self("ClearDriveState")  # Phase 7 Task 10 (Review Focus 5): no look-back or drift carried over a respawn
    g.link_entry("then", clear, "execute")
    # the chase camera cuts to the new spot: the spring arm's location lag has no teleport detection (it would fly in from the
    # old spot for ~0.5 s); ClearDriveState already cut the rotation lag, and TickCamera turns both back on a frame later
    no_lag = arm_set(g, "bEnableCameraLag", BOOL, "false")
    cut = g.var_set("bSnapArm", BOOL, default="true")
    m = mesh(g)
    lin = g.call_on(PRIMITIVE, "SetPhysicsLinearVelocity",
                    inputs=[struct_pin("NewVel", VECTOR, default="0,0,0"), Pin("bAddToCurrent", BOOL, default="false"),
                            Pin("BoneName", NAME, default="None")])
    g.link(m, "Mesh", lin, "self")
    g.exec(clear, no_lag, cut, lin)
    m2 = mesh(g)
    ang = g.call_on(PRIMITIVE, "SetPhysicsAngularVelocityInDegrees",
                    inputs=[struct_pin("NewAngVel", VECTOR, default="0,0,0"), Pin("bAddToCurrent", BOOL, default="false"),
                            Pin("BoneName", NAME, default="None")])
    g.link(m2, "Mesh", ang, "self")
    g.exec(lin, ang)
    tp = g.call_self_native(ACTOR, "K2_SetActorTransform",
                            inputs=[struct_pin("NewTransform", TRANSFORM), Pin("bSweep", BOOL, default="false"),
                                    Pin("bTeleport", BOOL, default="true")],
                            outputs=[struct_pin("SweepHitResult", HIT_RESULT, "out"), Pin("ReturnValue", BOOL, "out")])
    g.link_entry("NewTransform", tp, "NewTransform")
    g.exec(ang, tp)
    hb = set_handbrake(g, "false")
    g.exec(tp, hb)

    # ---- CanExit ----
    g = bp.function("CanExit", doc="An occupant, not wrecked, below the exit speed.", outputs=["ReturnValue:bool"], pure=True)
    occ = g.var_get("Occupant", OBJECT, cls_ref(CC))
    valid = is_valid(g)
    g.link(occ, "Occupant", valid, "Object")
    dest = g.var_get("bIsDestroyed", BOOL)
    nd = not_bool(g)
    g.link(dest, "bIsDestroyed", nd, "A")
    slow = g.call_self("IsBelowExitSpeed", outputs=[Pin("ReturnValue", BOOL, "out")], pure=True)
    a1 = and_bool(g)
    a2 = and_bool(g)
    g.link(valid, "ReturnValue", a1, "A")
    g.link(nd, "ReturnValue", a1, "B")
    g.link(a1, "ReturnValue", a2, "A")
    g.link(slow, "ReturnValue", a2, "B")
    g.link_result(a2, "ReturnValue", "ReturnValue")
    g.link_entry("then", "result", "execute")

    # ---- IsExitSpotFree(Location) -> bool : capsule trace at the spot, ignoring self ----
    g = bp.function("IsExitSpotFree", doc="Capsule trace at a spot beside the car.", inputs=["Location:struct:" + VECTOR], outputs=["ReturnValue:bool"])
    tr = g.call_static(SYS, "CapsuleTraceSingle",
                       inputs=[Pin("WorldContextObject", OBJECT, hidden=True), struct_pin("Start", VECTOR),
                               struct_pin("End", VECTOR), Pin("Radius", FLOAT, default="42.0"),
                               Pin("HalfHeight", FLOAT, default="96.0"), Pin("TraceChannel", "byte", default="TraceTypeQuery1"),
                               Pin("bTraceComplex", BOOL, default="false"), Pin("bIgnoreSelf", BOOL, default="true")],
                       outputs=[struct_pin("OutHit", HIT_RESULT, "out"), Pin("ReturnValue", BOOL, "out")])
    g.link_entry("Location", tr, "Start")
    g.link_entry("Location", tr, "End")
    g.link_entry("then", tr, "execute")
    nb = not_bool(g)
    g.link(tr, "ReturnValue", nb, "A")
    g.link_result(nb, "ReturnValue", "ReturnValue")
    g.link_extra(tr, "then", "result", "execute")

    # ---- FindExitLocation -> bFound, Location : left, right, behind ----
    g = bp.function("FindExitLocation", doc="Left door, then right, then behind the car.", outputs=["bFound:bool", "Location:struct:" + VECTOR],
                    locals=["Candidate:struct:" + VECTOR])
    prev_exec = ("entry", "then")
    for axis_fn, offset_var, sign in (("GetActorRightVector", "ExitSideOffset", -1.0),
                                       ("GetActorRightVector", "ExitSideOffset", 1.0),
                                       ("GetActorForwardVector", "ExitBehindOffset", -1.0)):
        loc = g.call_self_native(ACTOR, "K2_GetActorLocation", outputs=[struct_pin("ReturnValue", VECTOR, "out")], pure=True)
        axis = g.call_self_native(ACTOR, axis_fn, outputs=[struct_pin("ReturnValue", VECTOR, "out")], pure=True)
        up = g.call_self_native(ACTOR, "GetActorUpVector", outputs=[struct_pin("ReturnValue", VECTOR, "out")], pure=True)
        off = g.var_get(offset_var, FLOAT)
        upoff = g.var_get("ExitUpOffset", FLOAT)
        sgn = math2(g, "Multiply_FloatFloat", FLOAT, b="%f" % sign)
        g.link(off, offset_var, sgn, "A")
        side = g.call_static(MATH, "Multiply_VectorFloat", inputs=[struct_pin("A", VECTOR), Pin("B", FLOAT)],
                             outputs=[struct_pin("ReturnValue", VECTOR, "out")], pure=True)
        g.link(axis, "ReturnValue", side, "A")
        g.link(sgn, "ReturnValue", side, "B")
        upv = g.call_static(MATH, "Multiply_VectorFloat", inputs=[struct_pin("A", VECTOR), Pin("B", FLOAT)],
                            outputs=[struct_pin("ReturnValue", VECTOR, "out")], pure=True)
        g.link(up, "ReturnValue", upv, "A")
        g.link(upoff, "ExitUpOffset", upv, "B")
        add1 = g.call_static(MATH, "Add_VectorVector", inputs=[struct_pin("A", VECTOR), struct_pin("B", VECTOR)],
                             outputs=[struct_pin("ReturnValue", VECTOR, "out")], pure=True)
        add2 = g.call_static(MATH, "Add_VectorVector", inputs=[struct_pin("A", VECTOR), struct_pin("B", VECTOR)],
                             outputs=[struct_pin("ReturnValue", VECTOR, "out")], pure=True)
        g.link(loc, "ReturnValue", add1, "A")
        g.link(side, "ReturnValue", add1, "B")
        g.link(add1, "ReturnValue", add2, "A")
        g.link(upv, "ReturnValue", add2, "B")
        setc = g.local_set("Candidate", STRUCT, sub_object=cls_ref(VECTOR).replace("Class'", "ScriptStruct'"))
        g.link(add2, "ReturnValue", setc, "Candidate")
        g.link_extra(prev_exec[0], prev_exec[1], setc, "execute")
        free = g.call_self("IsExitSpotFree", inputs=[struct_pin("Location", VECTOR)], outputs=[Pin("ReturnValue", BOOL, "out")])
        g.link(setc, "Output_Get", free, "Location")
        g.exec(setc, free)
        b = g.branch()
        g.link(free, "ReturnValue", b, "Condition")
        g.exec(free, b)
        ret = g.function_result([Pin("bFound", BOOL, default="true"), struct_pin("Location", VECTOR)])
        cand = g.local_get("Candidate", STRUCT, sub_object=cls_ref(VECTOR).replace("Class'", "ScriptStruct'"))
        g.link(cand, "Candidate", ret, "Location")
        g.link(b, "then", ret, "execute")
        prev_exec = (b, "else")
    ret_none = g.function_result([Pin("bFound", BOOL, default="false"), struct_pin("Location", VECTOR)])
    g.link(prev_exec[0], prev_exec[1], ret_none, "execute")

    # ---- EnterVehicle(Character) -> bool ----
    g = bp.function("EnterVehicle", doc="The character gets in: stowed, its controller possesses the car, OnOccupantEntered.", inputs=["Character:" + obj_spec(BP_CHARACTER)], outputs=["ReturnValue:bool"])
    can = g.call_self("CanBeEntered", outputs=[Pin("ReturnValue", BOOL, "out")], pure=True)
    dead = g.call_on(CC, "IsDead", outputs=[Pin("ReturnValue", BOOL, "out")], pure=True)
    g.link_entry("Character", dead, "self")
    nd = not_bool(g)
    g.link(dead, "ReturnValue", nd, "A")
    ok = and_bool(g)
    g.link(can, "ReturnValue", ok, "A")
    g.link(nd, "ReturnValue", ok, "B")
    b = g.branch()
    g.link(ok, "ReturnValue", b, "Condition")
    g.link_entry("then", b, "execute")
    r_false = result_bool(g, "false")
    g.link(b, "else", r_false, "execute")
    seto = g.var_set("Occupant", OBJECT, sub_object=cls_ref(CC))
    g.link_entry("Character", seto, "Occupant")
    g.link(b, "then", seto, "execute")
    setcv = g.var_set_on(CC, "CurrentVehicle", OBJECT, sub_object=cls_ref(VC))
    g.link_entry("Character", setcv, "self")
    me = g.self_node()
    g.link(me, "self", setcv, "CurrentVehicle")
    g.exec(seto, setcv)
    stow = g.call_on(CC, "SetStowed", inputs=[Pin("bStowed", BOOL, default="true"), obj_pin("AttachTo", ACTOR)])
    g.link_entry("Character", stow, "self")
    me2 = g.self_node()
    g.link(me2, "self", stow, "AttachTo")
    g.exec(setcv, stow)
    ctrl = g.call_on(PAWN, "GetController", outputs=[obj_pin("ReturnValue", CONTROLLER, "out")], pure=True)
    g.link_entry("Character", ctrl, "self")
    cv = is_valid(g)
    g.link(ctrl, "ReturnValue", cv, "Object")
    bc = g.branch()
    g.link(cv, "ReturnValue", bc, "Condition")
    g.exec(stow, bc)
    poss = g.call_on(CONTROLLER, "Possess", inputs=[obj_pin("InPawn", PAWN)])
    g.link(ctrl, "ReturnValue", poss, "self")
    me3 = g.self_node()
    g.link(me3, "self", poss, "InPawn")
    g.link(bc, "then", poss, "execute")
    setld = g.var_set("LastDriver", OBJECT, sub_object=cls_ref(CONTROLLER))
    g.link(ctrl, "ReturnValue", setld, "LastDriver")
    g.exec(poss, setld)
    g.link(bc, "else", setld, "execute")
    # UE 4.27 keeps the handbrake input latched from parking; release it for the new driver
    release = set_handbrake(g, "false")
    g.exec(setld, release)
    f1 = g.call_delegate("OnOccupantEntered", [obj_pin("Character", CC)])
    g.link_entry("Character", f1, "Character")
    g.exec(release, f1)
    f2 = g.call_delegate_on(CC, "OnEnteredVehicle", [obj_pin("Vehicle", VC)])
    g.link_entry("Character", f2, "self")
    me4 = g.self_node()
    g.link(me4, "self", f2, "Vehicle")
    g.exec(f1, f2)
    r_true = result_bool(g, "true")
    g.exec(f2, g.call_self("RefreshRoofWeapon"), r_true)  # Phase 7 Task 13: the new driver's held weapon on the roof

    # ---- ExitVehicle -> bool ----
    g = bp.function("ExitVehicle", doc="The driver gets out beside the car and the controller possesses the character.", outputs=["ReturnValue:bool"],
                    locals=["Leaving:" + obj_spec(BP_CHARACTER), "Driver:object:" + CONTROLLER])
    can = g.call_self("CanExit", outputs=[Pin("ReturnValue", BOOL, "out")], pure=True)
    b = g.branch()
    g.link(can, "ReturnValue", b, "Condition")
    g.link_entry("then", b, "execute")
    r_false = result_bool(g, "false")
    g.link(b, "else", r_false, "execute")
    find = g.call_self("FindExitLocation", outputs=[Pin("bFound", BOOL, "out"), struct_pin("Location", VECTOR, "out")])
    g.link(b, "then", find, "execute")
    bf = g.branch()
    g.link(find, "bFound", bf, "Condition")
    g.exec(find, bf)
    r_false2 = result_bool(g, "false")
    g.link(bf, "else", r_false2, "execute")
    clear = g.call_self("ClearDriveState")  # Phase 7 Task 10 (Review Focus 5): the parked car keeps no look-back or drift
    g.link(bf, "then", clear, "execute")
    hb = set_handbrake(g, "true")
    g.exec(clear, hb)
    th = set_throttle(g, "0.0")
    g.exec(hb, th)
    occ = g.var_get("Occupant", OBJECT, cls_ref(CC))
    setl = g.local_set("Leaving", OBJECT, sub_object=cls_ref(CC))
    g.link(occ, "Occupant", setl, "Leaving")
    g.exec(th, setl)
    ctrl = g.call_self_native(PAWN, "GetController", outputs=[obj_pin("ReturnValue", CONTROLLER, "out")], pure=True)
    setd = g.local_set("Driver", OBJECT, sub_object=cls_ref(CONTROLLER))
    g.link(ctrl, "ReturnValue", setd, "Driver")
    g.exec(setl, setd)
    unstow = g.call_on(CC, "SetStowed", inputs=[Pin("bStowed", BOOL, default="false"), obj_pin("AttachTo", ACTOR)])
    g.link(setl, "Output_Get", unstow, "self")
    g.exec(setd, unstow)
    place = g.call_on(ACTOR, "K2_SetActorLocation",
                      inputs=[struct_pin("NewLocation", VECTOR), Pin("bSweep", BOOL, default="false"), Pin("bTeleport", BOOL, default="true")],
                      outputs=[struct_pin("SweepHitResult", HIT_RESULT, "out"), Pin("ReturnValue", BOOL, "out")])
    lv = g.local_get("Leaving", OBJECT, cls_ref(CC))
    g.link(lv, "Leaving", place, "self")
    g.link(find, "Location", place, "NewLocation")
    g.exec(unstow, place)
    dv = g.local_get("Driver", OBJECT, cls_ref(CONTROLLER))
    valid = is_valid(g)
    g.link(dv, "Driver", valid, "Object")
    bc = g.branch()
    g.link(valid, "ReturnValue", bc, "Condition")
    g.exec(place, bc)
    poss = g.call_on(CONTROLLER, "Possess", inputs=[obj_pin("InPawn", PAWN)])
    dv2 = g.local_get("Driver", OBJECT, cls_ref(CONTROLLER))
    g.link(dv2, "Driver", poss, "self")
    lv2 = g.local_get("Leaving", OBJECT, cls_ref(CC))
    g.link(lv2, "Leaving", poss, "InPawn")
    g.link(bc, "then", poss, "execute")
    setld = g.var_set("LastDriver", OBJECT, sub_object=cls_ref(CONTROLLER))
    dv3 = g.local_get("Driver", OBJECT, cls_ref(CONTROLLER))
    g.link(dv3, "Driver", setld, "LastDriver")
    g.exec(poss, setld)
    g.link(bc, "else", setld, "execute")
    clearcv = g.var_set_on(CC, "CurrentVehicle", OBJECT, sub_object=cls_ref(VC))
    lv3 = g.local_get("Leaving", OBJECT, cls_ref(CC))
    g.link(lv3, "Leaving", clearcv, "self")
    g.exec(setld, clearcv)
    clearo = g.var_set("Occupant", OBJECT, sub_object=cls_ref(CC))
    g.exec(clearcv, clearo)
    f1 = g.call_delegate("OnOccupantExited", [obj_pin("Character", CC)])
    lv4 = g.local_get("Leaving", OBJECT, cls_ref(CC))
    g.link(lv4, "Leaving", f1, "Character")
    g.exec(clearo, f1)
    f2 = g.call_delegate_on(CC, "OnExitedVehicle", [obj_pin("Vehicle", VC)])
    lv5 = g.local_get("Leaving", OBJECT, cls_ref(CC))
    g.link(lv5, "Leaving", f2, "self")
    me = g.self_node()
    g.link(me, "self", f2, "Vehicle")
    g.exec(f1, f2)
    r_true = result_bool(g, "true")
    g.exec(f2, g.call_self("RefreshRoofWeapon"), r_true)  # Phase 7 Task 13: no driver, no roof weapon

    # ---- EjectOccupant: un-stow beside the car without possession changes (used by respawn) ----
    g = bp.function("EjectOccupant", doc="Puts the occupant beside the car without changing possession (respawn).", locals=["Leaving:" + obj_spec(BP_CHARACTER)])
    occ = g.var_get("Occupant", OBJECT, cls_ref(CC))
    valid = is_valid(g)
    g.link(occ, "Occupant", valid, "Object")
    b = g.branch()
    g.link(valid, "ReturnValue", b, "Condition")
    g.link_entry("then", b, "execute")
    setl = g.local_set("Leaving", OBJECT, sub_object=cls_ref(CC))
    g.link(occ, "Occupant", setl, "Leaving")
    g.link(b, "then", setl, "execute")
    unstow = g.call_on(CC, "SetStowed", inputs=[Pin("bStowed", BOOL, default="false"), obj_pin("AttachTo", ACTOR)])
    g.link(setl, "Output_Get", unstow, "self")
    g.exec(setl, unstow)
    find = g.call_self("FindExitLocation", outputs=[Pin("bFound", BOOL, "out"), struct_pin("Location", VECTOR, "out")])
    g.exec(unstow, find)
    loc = g.call_self_native(ACTOR, "K2_GetActorLocation", outputs=[struct_pin("ReturnValue", VECTOR, "out")], pure=True)
    above = g.call_static(MATH, "Add_VectorVector", inputs=[struct_pin("A", VECTOR), struct_pin("B", VECTOR, default="0,0,200")],
                          outputs=[struct_pin("ReturnValue", VECTOR, "out")], pure=True)
    g.link(loc, "ReturnValue", above, "A")
    pick = g.call_static(MATH, "SelectVector", inputs=[struct_pin("A", VECTOR), struct_pin("B", VECTOR), Pin("bPickA", BOOL)],
                         outputs=[struct_pin("ReturnValue", VECTOR, "out")], pure=True)
    g.link(find, "Location", pick, "A")
    g.link(above, "ReturnValue", pick, "B")
    g.link(find, "bFound", pick, "bPickA")
    place = g.call_on(ACTOR, "K2_SetActorLocation",
                      inputs=[struct_pin("NewLocation", VECTOR), Pin("bSweep", BOOL, default="false"), Pin("bTeleport", BOOL, default="true")],
                      outputs=[struct_pin("SweepHitResult", HIT_RESULT, "out"), Pin("ReturnValue", BOOL, "out")])
    lv = g.local_get("Leaving", OBJECT, cls_ref(CC))
    g.link(lv, "Leaving", place, "self")
    g.link(pick, "ReturnValue", place, "NewLocation")
    g.exec(find, place)
    clearcv = g.var_set_on(CC, "CurrentVehicle", OBJECT, sub_object=cls_ref(VC))
    lv2 = g.local_get("Leaving", OBJECT, cls_ref(CC))
    g.link(lv2, "Leaving", clearcv, "self")
    g.exec(place, clearcv)
    clearo = g.var_set("Occupant", OBJECT, sub_object=cls_ref(CC))
    g.exec(clearcv, clearo)

    # ---- TickDriveOverrides(DeltaSeconds): parked/wrecked cars brake; blown tires cap the throttle ----
    g = bp.function("TickDriveOverrides", doc="Per-frame input: parked or wrecked cars brake; blown tires cap the throttle; the player's steering is "
                    "smoothed and scaled with speed; writes the inputs the arcade layer reads (ArcadeSteer/Throttle/Handbrake).",
                    inputs=["DeltaSeconds:float"])
    dead = g.var_get("bIsDestroyed", BOOL)
    ctrl = g.call_self_native(PAWN, "GetController", outputs=[obj_pin("ReturnValue", CONTROLLER, "out")], pure=True)
    valid = is_valid(g)
    g.link(ctrl, "ReturnValue", valid, "Object")
    nv = not_bool(g)
    g.link(valid, "ReturnValue", nv, "A")
    park = g.call_static(MATH, "BooleanOR", inputs=[Pin("A", BOOL), Pin("B", BOOL)], outputs=[Pin("ReturnValue", BOOL, "out")], pure=True)
    g.link(dead, "bIsDestroyed", park, "A")
    g.link(nv, "ReturnValue", park, "B")
    b = g.branch()
    g.link(park, "ReturnValue", b, "Condition")
    g.link_entry("then", b, "execute")
    t0 = set_throttle(g, "0.0")
    s0 = set_steering(g, "0.0")
    hb = set_handbrake(g, "true")
    g.link(b, "then", t0, "execute")
    g.exec(t0, s0, hb)
    # Phase 4: an AI controller feeds its own throttle, steering and handbrake (spec §2.1)
    ai = g.var_get("bAIControlled", BOOL)
    bai = g.branch()
    g.note(bai, "driven by an AI controller?")
    g.link(ai, "bAIControlled", bai, "Condition")
    g.link(b, "else", bai, "execute")
    at = g.var_get("AIThrottle", FLOAT)
    scale_ai = g.call_self("GetThrottleScale", outputs=[Pin("Scale", FLOAT, "out")], pure=True)
    mul_ai = math2(g, "Multiply_FloatFloat", FLOAT)
    g.link(at, "AIThrottle", mul_ai, "A")
    g.link(scale_ai, "Scale", mul_ai, "B")
    th_ai = set_throttle(g)
    g.link(drive_throttle(g, (mul_ai, "ReturnValue")), "Throttle", th_ai, "Throttle")
    g.link(bai, "then", th_ai, "execute")
    ast = g.var_get("AISteering", FLOAT)
    st_ai = set_steering(g)
    g.link(ast, "AISteering", st_ai, "Steering")
    ahb = g.var_get("bAIHandbrake", BOOL)
    hb_ai = mv_call(g, "SetHandbrakeInput", inputs=[Pin("bNewHandbrake", BOOL)])
    g.link(ahb, "bAIHandbrake", hb_ai, "bNewHandbrake")
    g.exec(th_ai, st_ai, hb_ai)
    axis = g.input_axis_value("MoveForward")
    scale = g.call_self("GetThrottleScale", outputs=[Pin("Scale", FLOAT, "out")], pure=True)
    mul = math2(g, "Multiply_FloatFloat", FLOAT)
    g.link(axis, "ReturnValue", mul, "A")
    g.link(scale, "Scale", mul, "B")
    th = set_throttle(g)
    g.link(drive_throttle(g, (mul, "ReturnValue")), "Throttle", th, "Throttle")
    g.link(bai, "else", th, "execute")
    # Phase 7 Task 9 (spec §5.1, §5.2): the player's steering is smoothed and scaled down with speed; the AI's is not [call],
    # because the AI controller already computes its own line. Each branch then writes the inputs the arcade layer reads.
    sm = g.call_self("SmoothSteer", inputs=[Pin("Current", FLOAT), Pin("Target", FLOAT), Pin("DeltaSeconds", FLOAT)],
                     outputs=[Pin("Steer", FLOAT, "out")], pure=True)
    g.link(g.var_get("SmoothedSteer", FLOAT), "SmoothedSteer", sm, "Current")
    g.link(g.input_axis_value("MoveRight"), "ReturnValue", sm, "Target")
    g.link_entry("DeltaSeconds", sm, "DeltaSeconds")
    ss = g.var_set("SmoothedSteer", FLOAT)
    g.link(sm, "Steer", ss, "SmoothedSteer")
    g.exec(th, ss)
    sc = g.call_self("ComputeSteerScale", inputs=[Pin("SpeedKPH", FLOAT)], outputs=[Pin("Scale", FLOAT, "out")], pure=True)
    g.link(g.call_self("GetSpeedKPH", outputs=[Pin("KPH", FLOAT, "out")], pure=True), "KPH", sc, "SpeedKPH")
    steer = _f(g, "Multiply_FloatFloat", (ss, "Output_Get"), (sc, "Scale"))
    st = set_steering(g)
    g.link(steer[0], steer[1], st, "Steering")
    g.exec(ss, st)

    def arcade_inputs(prev, steer_src, throttle_src, handbrake_src, steer_default=None, throttle_default=None, handbrake_default=None,
                      reset_player=False, parked=False):
        """ArcadeSteer, ArcadeThrottle, bArcadeHandbrake := the sources (or literals); reset_player also clears the player's
        smoothed steer and held handbrake (a parked or AI-driven car starts clean when a player takes it); parked ends a drift."""
        chain = []
        for name, cat, src, lit in (("ArcadeSteer", FLOAT, steer_src, steer_default), ("ArcadeThrottle", FLOAT, throttle_src, throttle_default),
                                    ("bArcadeHandbrake", BOOL, handbrake_src, handbrake_default)):
            s = g.var_set(name, cat, default=lit)
            if src is not None:
                g.link(src[0], src[1], s, name)
            chain.append(s)
        if reset_player:
            chain += [g.var_set("SmoothedSteer", FLOAT, default="0.0"), g.var_set("bHandbrakeHeld", BOOL, default="false")]
        if parked:
            chain.append(g.var_set("bDrifting", BOOL, default="false"))  # a parked or wrecked car brakes: no drift, no boost
        g.exec(prev, *chain)

    arcade_inputs(hb, None, None, None, "0.0", "0.0", "true", reset_player=True, parked=True)
    arcade_inputs(hb_ai, _fvar(g, "AISteering"), _fvar(g, "AIThrottle"), _fvar(g, "bAIHandbrake", BOOL), reset_player=True)
    arcade_inputs(st, (ss, "Output_Get"), (g.input_axis_value("MoveForward"), "ReturnValue"), _fvar(g, "bHandbrakeHeld", BOOL))

    # ComputeDriveThrottle(Input, SpeedKPH) -> Throttle (Phase 5 spec §3.2): the car's throttle scale, and a speed limiter
    # that cuts positive throttle at TopSpeedKPH (0 = none); braking and reverse are only scaled, never cut
    g = bp.function("ComputeDriveThrottle", doc="Input x ThrottleScale; 0 when accelerating at or above TopSpeedKPH (0 = no limiter).",
                    inputs=["Input:float", "SpeedKPH:float"], outputs=["Throttle:float"], pure=True)
    scaled = math2(g, "Multiply_FloatFloat", FLOAT)
    g.link_entry("Input", scaled, "A")
    g.link(g.var_get("ThrottleScale", FLOAT), "ThrottleScale", scaled, "B")
    accelerating = compare(g, "Greater_FloatFloat", FLOAT, b="0.0")
    g.link_entry("Input", accelerating, "A")
    has_limit = compare(g, "Greater_FloatFloat", FLOAT, b="0.0")
    g.link(g.var_get("TopSpeedKPH", FLOAT), "TopSpeedKPH", has_limit, "A")
    at_limit = compare(g, "GreaterEqual_FloatFloat", FLOAT)
    g.link_entry("SpeedKPH", at_limit, "A")
    g.link(g.var_get("TopSpeedKPH", FLOAT), "TopSpeedKPH", at_limit, "B")
    both = and_bool(g)
    g.link(has_limit, "ReturnValue", both, "A")
    g.link(at_limit, "ReturnValue", both, "B")
    limited = and_bool(g)
    g.link(accelerating, "ReturnValue", limited, "A")
    g.link(both, "ReturnValue", limited, "B")
    pick = g.call_static(MATH, "SelectFloat", inputs=[Pin("A", FLOAT, default="0.0"), Pin("B", FLOAT), Pin("bPickA", BOOL)],
                         outputs=[Pin("ReturnValue", FLOAT, "out")], pure=True)
    g.link(scaled, "ReturnValue", pick, "B")
    g.link(limited, "ReturnValue", pick, "bPickA")
    g.link_result(pick, "ReturnValue", "Throttle")
    g.link_entry("then", "result", "execute")

    # ---- Phase 7 Task 8: the handling math (pure; spec §5.2), used by the arcade driving layer ----
    def fm(g, fn, a=None, b=None):
        return math2(g, fn, FLOAT, a, b)

    def var(g, name):
        return (g.var_get(name, FLOAT), name)

    def ln(g, src, node, pin):
        g.link(src[0], src[1], node, pin)

    def clamp01(g, src):
        c = g.call_static(MATH, "FClamp", inputs=[Pin("Value", FLOAT), Pin("Min", FLOAT, default="0.0"), Pin("Max", FLOAT, default="1.0")],
                          outputs=[Pin("ReturnValue", FLOAT, "out")], pure=True)
        ln(g, src, c, "Value")
        return (c, "ReturnValue")

    def pick(g, cond, a, b):
        """SelectFloat: a when cond, else b (a, b = source tuples or literal strings)."""
        n = g.call_static(MATH, "SelectFloat", inputs=[Pin("A", FLOAT, default=a if isinstance(a, str) else None),
                                                       Pin("B", FLOAT, default=b if isinstance(b, str) else None), Pin("bPickA", BOOL)],
                          outputs=[Pin("ReturnValue", FLOAT, "out")], pure=True)
        if not isinstance(a, str):
            ln(g, a, n, "A")
        if not isinstance(b, str):
            ln(g, b, n, "B")
        ln(g, cond, n, "bPickA")
        return (n, "ReturnValue")

    def ratio(g, src_pin, ref):
        d = fm(g, "Divide_FloatFloat", b=ref if isinstance(ref, str) else None)
        g.link_entry(src_pin, d, "A")
        if not isinstance(ref, str):
            ln(g, ref, d, "B")
        return (d, "ReturnValue")

    g = bp.function("ComputeSteerScale", doc="lerp(1, SteerAtSpeed, clamp(SpeedKPH / SteerSpeedRef, 0, 1)): less steering at speed.",
                    inputs=["SpeedKPH:float"], outputs=["Scale:float"], pure=True)
    alpha = clamp01(g, ratio(g, "SpeedKPH", var(g, "SteerSpeedRef")))
    lp = g.call_static(MATH, "Lerp", inputs=[Pin("A", FLOAT, default="1.0"), Pin("B", FLOAT), Pin("Alpha", FLOAT)],
                       outputs=[Pin("ReturnValue", FLOAT, "out")], pure=True)
    ln(g, var(g, "SteerAtSpeed"), lp, "B")
    ln(g, alpha, lp, "Alpha")
    g.link_result(lp, "ReturnValue", "Scale")
    g.link_entry("then", "result", "execute")

    g = bp.function("SmoothSteer", doc="Moves Current toward Target at SteerRiseRate when Target is larger and on the same side, else at SteerReturnRate; never overshoots.",
                    inputs=["Current:float", "Target:float", "DeltaSeconds:float"], outputs=["Steer:float"], pure=True)
    abs_t = g.call_static(MATH, "Abs", inputs=[Pin("A", FLOAT)], outputs=[Pin("ReturnValue", FLOAT, "out")], pure=True)
    g.link_entry("Target", abs_t, "A")
    abs_c = g.call_static(MATH, "Abs", inputs=[Pin("A", FLOAT)], outputs=[Pin("ReturnValue", FLOAT, "out")], pure=True)
    g.link_entry("Current", abs_c, "A")
    larger = compare(g, "Greater_FloatFloat", FLOAT)
    g.link(abs_t, "ReturnValue", larger, "A")
    g.link(abs_c, "ReturnValue", larger, "B")
    prod = fm(g, "Multiply_FloatFloat")
    g.link_entry("Current", prod, "A")
    g.link_entry("Target", prod, "B")
    same = compare(g, "GreaterEqual_FloatFloat", FLOAT, b="0.0")
    g.link(prod, "ReturnValue", same, "A")
    rising = and_bool(g)
    g.link(larger, "ReturnValue", rising, "A")
    g.link(same, "ReturnValue", rising, "B")
    rate = pick(g, (rising, "ReturnValue"), var(g, "SteerRiseRate"), var(g, "SteerReturnRate"))
    step = fm(g, "Multiply_FloatFloat")
    ln(g, rate, step, "A")
    g.link_entry("DeltaSeconds", step, "B")
    neg = fm(g, "Multiply_FloatFloat", b="-1.0")
    g.link(step, "ReturnValue", neg, "A")
    diff = fm(g, "Subtract_FloatFloat")
    g.link_entry("Target", diff, "A")
    g.link_entry("Current", diff, "B")
    cl = g.call_static(MATH, "FClamp", inputs=[Pin("Value", FLOAT), Pin("Min", FLOAT), Pin("Max", FLOAT)],
                       outputs=[Pin("ReturnValue", FLOAT, "out")], pure=True)
    g.link(diff, "ReturnValue", cl, "Value")
    g.link(neg, "ReturnValue", cl, "Min")
    g.link(step, "ReturnValue", cl, "Max")
    res = fm(g, "Add_FloatFloat")
    g.link_entry("Current", res, "A")
    g.link(cl, "ReturnValue", res, "B")
    g.link_result(res, "ReturnValue", "Steer")
    g.link_entry("then", "result", "execute")

    g = bp.function("ComputeDownforce", doc="min(DownforceG x 980 x (SpeedKPH / 100)^2, DownforceCap) in cm/s^2.",
                    inputs=["SpeedKPH:float"], outputs=["Accel:float"], pure=True)
    sq = g.call_static(MATH, "Square", inputs=[Pin("A", FLOAT)], outputs=[Pin("ReturnValue", FLOAT, "out")], pure=True)
    ln(g, ratio(g, "SpeedKPH", "100.0"), sq, "A")
    gm = fm(g, "Multiply_FloatFloat", b="980.0")
    ln(g, var(g, "DownforceG"), gm, "A")
    raw = fm(g, "Multiply_FloatFloat")
    g.link(gm, "ReturnValue", raw, "A")
    g.link(sq, "ReturnValue", raw, "B")
    mn = g.call_static(MATH, "FMin", inputs=[Pin("A", FLOAT), Pin("B", FLOAT)], outputs=[Pin("ReturnValue", FLOAT, "out")], pure=True)
    g.link(raw, "ReturnValue", mn, "A")
    ln(g, var(g, "DownforceCap"), mn, "B")
    g.link_result(mn, "ReturnValue", "Accel")
    g.link_entry("then", "result", "execute")

    g = bp.function("ComputeGripAccel", doc="-LateralSpeed x GripAssist (x DriftGrip while drifting): the sideways grip acceleration.",
                    inputs=["LateralSpeed:float", "bDriftingNow:bool"], outputs=["Accel:float"], pure=True)
    gr = fm(g, "Multiply_FloatFloat")
    ln(g, var(g, "GripAssist"), gr, "A")
    ln(g, pick(g, ("entry", "bDriftingNow"), var(g, "DriftGrip"), "1.0"), gr, "B")
    lat = fm(g, "Multiply_FloatFloat")
    g.link_entry("LateralSpeed", lat, "A")
    g.link(gr, "ReturnValue", lat, "B")
    ng = fm(g, "Multiply_FloatFloat", b="-1.0")
    g.link(lat, "ReturnValue", ng, "A")
    g.link_result(ng, "ReturnValue", "Accel")
    g.link_entry("then", "result", "execute")

    g = bp.function("ComputeTargetFOV", doc="90 + 15 x clamp(SpeedKPH / 160, 0, 1) + 8 while boosting.",
                    inputs=["SpeedKPH:float", "bBoosting:bool"], outputs=["FOV:float"], pure=True)
    sp = fm(g, "Multiply_FloatFloat", b="15.0")
    ln(g, clamp01(g, ratio(g, "SpeedKPH", "160.0")), sp, "A")
    bo = pick(g, ("entry", "bBoosting"), "8.0", "0.0")
    a1 = fm(g, "Add_FloatFloat", a="90.0")
    g.link(sp, "ReturnValue", a1, "B")
    a2 = fm(g, "Add_FloatFloat")
    g.link(a1, "ReturnValue", a2, "A")
    ln(g, bo, a2, "B")
    g.link_result(a2, "ReturnValue", "FOV")
    g.link_entry("then", "result", "execute")

    g = bp.function("ComputeEnginePitch", doc="0.6 + 1.4 x clamp(RPMRatio, 0, 1).", inputs=["RPMRatio:float"], outputs=["Pitch:float"], pure=True)
    cr = clamp01(g, ("entry", "RPMRatio"))
    pm = fm(g, "Multiply_FloatFloat", b="1.4")
    ln(g, cr, pm, "A")
    pa = fm(g, "Add_FloatFloat", a="0.6")
    g.link(pm, "ReturnValue", pa, "B")
    g.link_result(pa, "ReturnValue", "Pitch")
    g.link_entry("then", "result", "execute")

    # ---- Phase 7 Task 9: the arcade layer (spec §5.1, §5.2); forces and torques are mass-independent (bAccelChange) ----
    # Long frames: a damping acceleration -Value x Rate acts for the frame's physics time (at most DeltaSeconds; headless runs
    # throttle to 3 fps, so DeltaSeconds is about 0.33 s), so LimitDamping caps it at |Value| / DeltaSeconds: one frame can
    # remove all of a slide or a spin, never reverse it.
    g = bp.function("LimitDamping", doc="Caps a damping acceleration at |Value| / DeltaSeconds, so one long frame never reverses Value.",
                    inputs=["Accel:float", "Value:float", "DeltaSeconds:float"], outputs=["Limited:float"], pure=True)
    dt = _f(g, "FMax", ("entry", "DeltaSeconds"), "0.001")
    cap = _f(g, "Divide_FloatFloat", _f(g, "Abs", ("entry", "Value")), dt)
    cl = g.call_static(MATH, "FClamp", inputs=[Pin("Value", FLOAT), Pin("Min", FLOAT), Pin("Max", FLOAT)],
                       outputs=[Pin("ReturnValue", FLOAT, "out")], pure=True)
    g.link_entry("Accel", cl, "Value")
    ln(g, _f(g, "Multiply_FloatFloat", cap, "-1.0"), cl, "Min")
    ln(g, cap, cl, "Max")
    g.link_result(cl, "ReturnValue", "Limited")
    g.link_entry("then", "result", "execute")

    g = bp.function("IsGrounded", doc="A Visibility line trace from the actor origin GroundProbe cm straight down hits (self ignored).",
                    outputs=["ReturnValue:bool"])
    origin = self_actor_location(g)
    below = g.call_static(MATH, "Subtract_VectorVector", inputs=[struct_pin("A", VECTOR), struct_pin("B", VECTOR)],
                          outputs=[struct_pin("ReturnValue", VECTOR, "out")], pure=True)
    g.link(origin, "ReturnValue", below, "A")
    probe = g.call_static(MATH, "MakeVector", inputs=[Pin("X", FLOAT, default="0.0"), Pin("Y", FLOAT, default="0.0"), Pin("Z", FLOAT)],
                          outputs=[struct_pin("ReturnValue", VECTOR, "out")], pure=True)
    ln(g, _fvar(g, "GroundProbe"), probe, "Z")
    g.link(probe, "ReturnValue", below, "B")
    tr = g.call_static(SYS, "LineTraceSingle",
                       inputs=[Pin("WorldContextObject", OBJECT, hidden=True), struct_pin("Start", VECTOR), struct_pin("End", VECTOR),
                               Pin("TraceChannel", "byte", default="TraceTypeQuery1"), Pin("bTraceComplex", BOOL, default="false"),
                               Pin("DrawDebugType", "byte", default="None"), Pin("bIgnoreSelf", BOOL, default="true")],
                       outputs=[struct_pin("OutHit", HIT_RESULT, "out"), Pin("ReturnValue", BOOL, "out")])
    g.link(origin, "ReturnValue", tr, "Start")
    g.link(below, "ReturnValue", tr, "End")
    g.link_entry("then", tr, "execute")
    r = g.function_result([Pin("ReturnValue", BOOL)])
    g.link(tr, "ReturnValue", r, "ReturnValue")
    g.exec(tr, r)

    g = bp.function("UpdateDrift", inputs=["Steer:float", "SpeedKPH:float", "bHandbrake:bool"],
                    doc="Drift starts with the handbrake, |Steer| >= DriftSteerMin, SpeedKPH >= DriftMinSpeed and grounded; it ends on "
                        "a handbrake release, below DriftExitSpeed or airborne. A release after DriftBoostMinSeconds kicks the car "
                        "forward by DriftBoostSpeed (DriftBoostCount, OnDriftBoost).")
    bd = g.branch()
    g.note(bd, "drifting already?")
    ln(g, _fvar(g, "bDrifting", BOOL), bd, "Condition")
    g.link_entry("then", bd, "execute")
    # start
    steer_ok = _f(g, "GreaterEqual_FloatFloat", _f(g, "Abs", ("entry", "Steer")), _fvar(g, "DriftSteerMin"), BOOL)
    fast = _f(g, "GreaterEqual_FloatFloat", ("entry", "SpeedKPH"), _fvar(g, "DriftMinSpeed"), BOOL)
    start = and_bool(g)
    g.link_entry("bHandbrake", start, "A")
    ln(g, steer_ok, start, "B")
    start2 = and_bool(g)
    g.link(start, "ReturnValue", start2, "A")
    ln(g, fast, start2, "B")
    start3 = and_bool(g)
    g.link(start2, "ReturnValue", start3, "A")
    ln(g, _fvar(g, "bGrounded", BOOL), start3, "B")
    bs = g.branch()
    g.note(bs, "handbrake + steer + speed + grounded?")
    g.link(start3, "ReturnValue", bs, "Condition")
    g.link(bd, "else", bs, "execute")
    on = g.var_set("bDrifting", BOOL, default="true")
    g.link(bs, "then", on, "execute")
    since = g.var_set("DriftStartTime", FLOAT)
    g.link(game_time(g), "ReturnValue", since, "DriftStartTime")
    g.exec(on, since)
    # end
    released = not_bool(g)
    g.link_entry("bHandbrake", released, "A")
    slow = _f(g, "Less_FloatFloat", ("entry", "SpeedKPH"), _fvar(g, "DriftExitSpeed"), BOOL)
    airborne = not_bool(g)
    ln(g, _fvar(g, "bGrounded", BOOL), airborne, "A")
    end1 = or_bool(g)
    g.link(released, "ReturnValue", end1, "A")
    ln(g, slow, end1, "B")
    end2 = or_bool(g)
    g.link(end1, "ReturnValue", end2, "A")
    g.link(airborne, "ReturnValue", end2, "B")
    be = g.branch()
    g.note(be, "released, too slow or airborne?")
    g.link(end2, "ReturnValue", be, "Condition")
    g.link(bd, "then", be, "execute")
    off = g.var_set("bDrifting", BOOL, default="false")
    g.link(be, "then", off, "execute")
    held = _f(g, "Subtract_FloatFloat", (game_time(g), "ReturnValue"), _fvar(g, "DriftStartTime"))
    long_enough = _f(g, "GreaterEqual_FloatFloat", held, _fvar(g, "DriftBoostMinSeconds"), BOOL)
    boost_ok = and_bool(g)
    g.link(released, "ReturnValue", boost_ok, "A")
    ln(g, long_enough, boost_ok, "B")
    bb = g.branch()
    g.note(bb, "ended by a release after DriftBoostMinSeconds?")
    g.link(boost_ok, "ReturnValue", bb, "Condition")
    g.exec(off, bb)
    kick = _mesh_call(g, "AddImpulse", "Impulse", _vscale(g, _self_vec(g, "GetActorForwardVector"), _fvar(g, "DriftBoostSpeed")), "bVelChange")
    g.link(bb, "then", kick, "execute")
    count = g.var_set("DriftBoostCount", INT)
    inc = math2(g, "Add_IntInt", INT, b="1")
    ln(g, _fvar(g, "DriftBoostCount", INT), inc, "A")
    g.link(inc, "ReturnValue", count, "DriftBoostCount")
    fire = g.call_delegate("OnDriftBoost")
    g.exec(kick, count, fire)

    g = bp.function("TickArcade", inputs=["DeltaSeconds:float"],
                    doc="Per-frame arcade handling: ground probe and drift state; the handbrake input (held, but not while drifting); grounded: grip assist, downforce, stability or "
                        "drift yaw; airborne past AirDelay: pitch/roll damping, levelling, and air control for the player's car.")
    probe_hit = g.call_self("IsGrounded", outputs=[Pin("ReturnValue", BOOL, "out")])
    g.link_entry("then", probe_hit, "execute")
    sg = g.var_set("bGrounded", BOOL)
    g.link(probe_hit, "ReturnValue", sg, "bGrounded")
    g.exec(probe_hit, sg)
    bg = g.branch()
    g.link(sg, "Output_Get", bg, "Condition")
    g.exec(sg, bg)
    landed = g.var_set("AirborneSince", FLOAT, default="-1.0")
    # Phase 7 Task 10 (spec §5.3): landing after more than LandShakeAirTime in the air shakes the driver's view
    was_up = and_bool(g)
    ln(g, _f(g, "GreaterEqual_FloatFloat", _fvar(g, "AirborneSince"), "0.0", BOOL), was_up, "A")
    ln(g, _f(g, "Greater_FloatFloat", _f(g, "Subtract_FloatFloat", (game_time(g), "ReturnValue"), _fvar(g, "AirborneSince")),
             _fvar(g, "LandShakeAirTime"), BOOL), was_up, "B")
    bland = g.branch()
    g.note(bland, "landing after more than LandShakeAirTime in the air?")
    g.link(was_up, "ReturnValue", bland, "Condition")
    g.link(bg, "then", bland, "execute")
    land_shake = driver_shake(g)
    g.link(bland, "then", land_shake, "execute")
    g.exec(land_shake, landed)
    g.link(bland, "else", landed, "execute")
    took_off = g.branch()
    g.note(took_off, "just left the ground?")
    ln(g, _f(g, "Less_FloatFloat", _fvar(g, "AirborneSince"), "0.0", BOOL), took_off, "Condition")
    g.link(bg, "else", took_off, "execute")
    mark = g.var_set("AirborneSince", FLOAT)
    g.link(game_time(g), "ReturnValue", mark, "AirborneSince")
    g.link(took_off, "then", mark, "execute")
    kph = lambda: (g.call_self("GetSpeedKPH", outputs=[Pin("KPH", FLOAT, "out")], pure=True), "KPH")
    upd = g.call_self("UpdateDrift", inputs=[Pin("Steer", FLOAT), Pin("SpeedKPH", FLOAT), Pin("bHandbrake", BOOL)])
    ln(g, _fvar(g, "ArcadeSteer"), upd, "Steer")
    # the drift rules use the speed over the ground: a car sliding sideways at 60 km/h is not "below 25 km/h" just because
    # its forward component is (GetSpeedKPH is the forward speed)
    ground_speed = g.call_static(MATH, "VSize", inputs=[struct_pin("A", VECTOR)], outputs=[Pin("ReturnValue", FLOAT, "out")], pure=True)
    ln(g, _self_vec(g, "GetVelocity"), ground_speed, "A")
    ln(g, _f(g, "Multiply_FloatFloat", (ground_speed, "ReturnValue"), "0.036"), upd, "SpeedKPH")
    ln(g, _fvar(g, "bArcadeHandbrake", BOOL), upd, "bHandbrake")
    for src, pin in ((landed, "then"), (mark, "then"), (took_off, "else")):
        g.link(src, pin, upd, "execute")
    # the handbrake button starts and holds a drift, but the wheels are not locked while drifting [call]: the arcade yaw
    # turns the car, and locked rear wheels scrubbed a full-lock drift from 80 km/h to 4 km/h in 1 s (a spin, no boost)
    lock = and_bool(g)
    ln(g, _fvar(g, "bArcadeHandbrake", BOOL), lock, "A")
    no_drift = not_bool(g)
    ln(g, _fvar(g, "bDrifting", BOOL), no_drift, "A")
    g.link(no_drift, "ReturnValue", lock, "B")
    hb_in = mv_call(g, "SetHandbrakeInput", inputs=[Pin("bNewHandbrake", BOOL)])
    g.link(lock, "ReturnValue", hb_in, "bNewHandbrake")
    g.exec(upd, hb_in)
    smoke = g.call_self("TickTyreSmoke")  # Phase 7 Task 16 (spec §5.5)
    ground = g.branch()
    g.note(ground, "on the ground?")
    ln(g, _fvar(g, "bGrounded", BOOL), ground, "Condition")
    g.exec(hb_in, smoke, ground)
    # grounded: grip assist on the sideways speed (x DriftGrip while drifting), then downforce
    right, up = _self_vec(g, "GetActorRightVector"), _self_vec(g, "GetActorUpVector")
    lateral = _vbin(g, "Dot_VectorVector", _self_vec(g, "GetVelocity"), right)
    grip = g.call_self("ComputeGripAccel", inputs=[Pin("LateralSpeed", FLOAT), Pin("bDriftingNow", BOOL)], outputs=[Pin("Accel", FLOAT, "out")], pure=True)
    ln(g, lateral, grip, "LateralSpeed")
    ln(g, _fvar(g, "bDrifting", BOOL), grip, "bDriftingNow")
    f_grip = _mesh_call(g, "AddForce", "Force", _vscale(g, right, _limited(g, (grip, "Accel"), lateral)), "bAccelChange")
    g.link(ground, "then", f_grip, "execute")
    down = g.call_self("ComputeDownforce", inputs=[Pin("SpeedKPH", FLOAT)], outputs=[Pin("Accel", FLOAT, "out")], pure=True)
    ln(g, kph(), down, "SpeedKPH")
    f_down = _mesh_call(g, "AddForce", "Force", _vscale(g, up, _f(g, "Multiply_FloatFloat", (down, "Accel"), "-1.0")), "bAccelChange")
    g.exec(f_grip, f_down)
    bdr = g.branch()
    g.note(bdr, "drifting?")
    ln(g, _fvar(g, "bDrifting", BOOL), bdr, "Condition")
    g.exec(f_down, bdr)
    # drifting: yaw acceleration = steer x DriftYawAccel (positive steer turns right, a positive yaw rate about up)
    yaw_acc = _f(g, "Multiply_FloatFloat", _fvar(g, "ArcadeSteer"), _fvar(g, "DriftYawAccel"))
    t_drift = _mesh_call(g, "AddTorqueInDegrees", "Torque", _vscale(g, up, yaw_acc), "bAccelChange")
    g.link(bdr, "then", t_drift, "execute")
    # not drifting, steering near the centre: stability damps the yaw rate
    centred = _f(g, "Less_FloatFloat", _f(g, "Abs", _fvar(g, "ArcadeSteer")), "0.1", BOOL)
    bst = g.branch()
    g.note(bst, "|steer| < 0.1?")
    ln(g, centred, bst, "Condition")
    g.link(bdr, "else", bst, "execute")
    yaw_rate = _vbin(g, "Dot_VectorVector", _ang_vel(g), up)
    damp_yaw = _f(g, "Multiply_FloatFloat", _f(g, "Multiply_FloatFloat", yaw_rate, _fvar(g, "StabilityDamping")), "-1.0")
    t_stab = _mesh_call(g, "AddTorqueInDegrees", "Torque", _vscale(g, up, _limited(g, damp_yaw, yaw_rate)), "bAccelChange")
    g.link(bst, "then", t_stab, "execute")
    # airborne for longer than AirDelay: damp pitch and roll rates, level toward world up, and (player) air control
    in_air = _f(g, "Subtract_FloatFloat", (game_time(g), "ReturnValue"), _fvar(g, "AirborneSince"))
    bair = g.branch()
    g.note(bair, "airborne longer than AirDelay?")
    ln(g, _f(g, "Greater_FloatFloat", in_air, _fvar(g, "AirDelay"), BOOL), bair, "Condition")
    g.link(ground, "else", bair, "execute")
    fwd, right2, up2 = _self_vec(g, "GetActorForwardVector"), _self_vec(g, "GetActorRightVector"), _self_vec(g, "GetActorUpVector")
    w = _ang_vel(g)
    pitch_rate, roll_rate = _vbin(g, "Dot_VectorVector", w, right2), _vbin(g, "Dot_VectorVector", w, fwd)
    damp = lambda rate: _limited(g, _f(g, "Multiply_FloatFloat", _f(g, "Multiply_FloatFloat", rate, _fvar(g, "AirDamping")), "-1.0"), rate)
    damping = _vbin(g, "Add_VectorVector", _vscale(g, right2, damp(pitch_rate)), _vscale(g, fwd, damp(roll_rate)))
    levelling = _vscale(g, _vbin(g, "Cross_VectorVector", up2, "0,0,1"), _fvar(g, "AirLevelAccel"))
    # air control: throttle pitches (forward = nose down, a positive rate about right), steer rolls (right = right side down,
    # a negative rate about forward); AI cars get none [call]
    control_gain = pick(g, _fvar(g, "bAIControlled", BOOL), "0.0", _fvar(g, "AirControlAccel"))
    control = _vscale(g, _vbin(g, "Add_VectorVector", _vscale(g, right2, _fvar(g, "ArcadeThrottle")),
                               _vscale(g, fwd, _f(g, "Multiply_FloatFloat", _fvar(g, "ArcadeSteer"), "-1.0"))), control_gain)
    total = _vbin(g, "Add_VectorVector", _vbin(g, "Add_VectorVector", damping, levelling), control)
    t_air = _mesh_call(g, "AddTorqueInDegrees", "Torque", total, "bAccelChange")
    g.link(bair, "then", t_air, "execute")

    # SetAIInput(Throttle, Steering, bHandbrake): what TickDriveOverrides applies while bAIControlled
    g = bp.function("SetAIInput", inputs=["Throttle:float", "Steering:float", "bHandbrake:bool"],
                    doc="The AI controller's inputs; TickDriveOverrides applies them every frame while bAIControlled.")
    s1 = g.var_set("AIThrottle", FLOAT)
    g.link_entry("Throttle", s1, "AIThrottle")
    g.link_entry("then", s1, "execute")
    s2 = g.var_set("AISteering", FLOAT)
    g.link_entry("Steering", s2, "AISteering")
    s3 = g.var_set("bAIHandbrake", BOOL)
    g.link_entry("bHandbrake", s3, "bAIHandbrake")
    g.exec(s1, s2, s3)

    # ---- Phase 7 Task 16: tyre smoke (spec §5.5) and the wreck's smoke (spec §7.1), only near the player's camera ----
    g = bp.function("TickTyreSmoke", doc="Spec §5.5: on the ground and drifting or sliding (|lateral speed| > TyreSmokeLateral), a "
                    "BP_DFFxPuff at each rear wheel every TyreSmokeInterval, only within %g cm of the player's camera "
                    "(GameMode.IsNearPlayerView; Review Focus 2)." % FX_VIEW_RADIUS)
    lateral = _vbin(g, "Dot_VectorVector", _self_vec(g, "GetVelocity"), _self_vec(g, "GetActorRightVector"))
    sliding = _f(g, "Greater_FloatFloat", _f(g, "Abs", lateral), _fvar(g, "TyreSmokeLateral"), BOOL)
    smoky = or_bool(g)
    ln(g, _fvar(g, "bDrifting", BOOL), smoky, "A")
    ln(g, sliding, smoky, "B")
    on_ground = and_bool(g)
    ln(g, _fvar(g, "bGrounded", BOOL), on_ground, "A")
    g.link(smoky, "ReturnValue", on_ground, "B")
    due = _f(g, "GreaterEqual_FloatFloat", (game_time(g), "ReturnValue"), _fvar(g, "NextTyreSmokeTime"), BOOL)
    go = and_bool(g)
    g.link(on_ground, "ReturnValue", go, "A")
    ln(g, due, go, "B")
    b = g.branch()
    g.note(b, "on the ground, drifting or sliding, and the next puff due?")
    g.link(go, "ReturnValue", b, "Condition")
    g.link_entry("then", b, "execute")
    near = near_player_view(g, _self_vec(g, "K2_GetActorLocation"), (b, "then"))
    nxt = g.var_set("NextTyreSmokeTime", FLOAT)
    ln(g, _f(g, "Add_FloatFloat", (game_time(g), "ReturnValue"), _fvar(g, "TyreSmokeInterval")), nxt, "NextTyreSmokeTime")
    g.link(near, "then", nxt, "execute")
    prev = (nxt, "then")
    for wheel in ("WheelRL", "WheelRR"):
        first, last, _ = spawn_fx(g, BP_FX_PUFF, transform_at(g, comp_location(g, wheel)))
        g.link(prev[0], prev[1], first, "execute")
        prev = (last, "then")

    g = bp.function("SpawnWreckSmoke", doc="The wreck's looping timer (every WreckSmokeInterval from DestroyVehicle): a BP_DFFxPuff "
                    "darkened by WreckSmokeTint over the WreckFire while within %g cm of the player's camera; the timer stops if the "
                    "car is no longer wrecked." % FX_VIEW_RADIUS)
    wrecked = g.branch()
    g.note(wrecked, "still a wreck?")
    ln(g, _fvar(g, "bIsDestroyed", BOOL), wrecked, "Condition")
    g.link_entry("then", wrecked, "execute")
    g.link(wrecked, "else", timer(g, "SpawnWreckSmoke", None, clear=True), "execute")
    above = _vbin(g, "Add_VectorVector", comp_location(g, "WreckFire"), "0,0,60")
    near = near_player_view(g, above, (wrecked, "then"))
    tint = (g.var_get("WreckSmokeTint", STRUCT, struct_ref(LINEAR_COLOR)), "WreckSmokeTint")
    first, _, _ = spawn_fx(g, BP_FX_PUFF, transform_at(g, above), tint_src=tint)
    g.link(near, "then", first, "execute")

    # ---- Phase 7 Task 10: reset, look-back, the chase camera, camera shakes (spec §5.2 Reset, §5.3) ----
    g = bp.function("PlayDriverShake", inputs=["Shake:class:" + CAMERA_SHAKE_BASE, "Scale:float"],
                    doc="Plays a camera shake on the driver's view when a player drives this car (an AI driver has no view).")
    ctrl = g.call_self_native(PAWN, "GetController", outputs=[obj_pin("ReturnValue", CONTROLLER, "out")], pure=True)
    to_pc = g.cast(PLAYER_CONTROLLER)
    g.note(to_pc, "driven by a player?")
    g.link(ctrl, "ReturnValue", to_pc, "Object")
    g.link_entry("then", to_pc, "execute")
    shake = start_camera_shake(g, (to_pc, as_pin(PLAYER_CONTROLLER)), ("entry", "Shake"), ("entry", "Scale"))
    g.link(to_pc, "then", shake, "execute")

    # Phase 7 Task 18 (spec §7.6): a hit taken shows the damage vignette on the driving player's race HUD
    g = bp.function("ShowDriverDamage", doc="The damage vignette (WBP_DFRaceHUD.ShowDamage) on the race HUD of the player driving this car.")
    ctrl = g.call_self_native(PAWN, "GetController", outputs=[obj_pin("ReturnValue", CONTROLLER, "out")], pure=True)
    to_pc = g.cast(PLAYER_CONTROLLER)
    g.note(to_pc, "driven by a player?")
    g.link(ctrl, "ReturnValue", to_pc, "Object")
    g.link_entry("then", to_pc, "execute")
    hud = g.call_on(PLAYER_CONTROLLER, "GetHUD", outputs=[obj_pin("ReturnValue", "/Script/Engine.HUD", "out")], pure=True)
    g.link(to_pc, as_pin(PLAYER_CONTROLLER), hud, "self")
    to_hud = cast_to(g, BP_HUD)
    g.link(hud, "ReturnValue", to_hud, "Object")
    g.link(to_pc, "then", to_hud, "execute")
    widget = g.var_get_on(gen(BP_HUD), "HUDWidget", OBJECT, cls_ref(USER_WIDGET))
    g.link(to_hud, as_pin(BP_HUD), widget, "self")
    to_race = cast_to(g, WBP_HUD)
    g.link(widget, "HUDWidget", to_race, "Object")
    g.link(to_hud, "then", to_race, "execute")
    show = g.call_on(gen(WBP_HUD), "ShowDamage")
    g.link(to_race, as_pin(WBP_HUD), show, "self")
    g.link(to_race, "then", show, "execute")

    g = bp.function("ResetCar", outputs=["ReturnValue:bool"],
                    doc="Spec §5.2: below ResetMaxSpeed km/h over the ground and ResetCooldown s after the last reset, the car is lifted "
                        "ResetLift cm with pitch and roll zeroed and its velocities zeroed (TeleportAndStop): no death, no position gain. "
                        "Refused (false) otherwise, and for a wreck.")
    ground_kph = g.call_static(MATH, "VSize", inputs=[struct_pin("A", VECTOR)], outputs=[Pin("ReturnValue", FLOAT, "out")], pure=True)
    ln(g, _self_vec(g, "GetVelocity"), ground_kph, "A")
    fast = _f(g, "GreaterEqual_FloatFloat", _f(g, "Multiply_FloatFloat", (ground_kph, "ReturnValue"), "0.036"), _fvar(g, "ResetMaxSpeed"), BOOL)
    cooling = _f(g, "Less_FloatFloat", _f(g, "Subtract_FloatFloat", (game_time(g), "ReturnValue"), _fvar(g, "LastResetTime")),
                 _fvar(g, "ResetCooldown"), BOOL)
    refuse = or_bool(g)
    ln(g, _fvar(g, "bIsDestroyed", BOOL), refuse, "A")
    ln(g, fast, refuse, "B")
    refuse2 = or_bool(g)
    g.link(refuse, "ReturnValue", refuse2, "A")
    ln(g, cooling, refuse2, "B")
    br = g.branch()
    g.note(br, "wrecked, too fast or cooling down?")
    g.link(refuse2, "ReturnValue", br, "Condition")
    g.link_entry("then", br, "execute")
    g.link(br, "then", result_bool(g, "false"), "execute")
    stamp = g.var_set("LastResetTime", FLOAT)
    g.link(game_time(g), "ReturnValue", stamp, "LastResetTime")
    g.link(br, "else", stamp, "execute")
    lift = g.call_static(MATH, "MakeVector", inputs=[Pin("X", FLOAT, default="0.0"), Pin("Y", FLOAT, default="0.0"), Pin("Z", FLOAT)],
                         outputs=[struct_pin("ReturnValue", VECTOR, "out")], pure=True)
    ln(g, _fvar(g, "ResetLift"), lift, "Z")
    lifted = _vbin(g, "Add_VectorVector", (self_actor_location(g), "ReturnValue"), (lift, "ReturnValue"))
    rot = g.call_self_native(ACTOR, "K2_GetActorRotation", outputs=[struct_pin("ReturnValue", ROTATOR, "out")], pure=True)
    yaw = g.call_static(MATH, "BreakRotator", inputs=[struct_pin("InRot", ROTATOR)],
                        outputs=[Pin("Roll", FLOAT, "out"), Pin("Pitch", FLOAT, "out"), Pin("Yaw", FLOAT, "out")], pure=True)
    g.link(rot, "ReturnValue", yaw, "InRot")
    level = g.call_static(MATH, "MakeRotator", inputs=[Pin("Roll", FLOAT, default="0.0"), Pin("Pitch", FLOAT, default="0.0"), Pin("Yaw", FLOAT)],
                          outputs=[struct_pin("ReturnValue", ROTATOR, "out")], pure=True)
    g.link(yaw, "Yaw", level, "Yaw")
    xf = g.call_static(MATH, "MakeTransform", inputs=[struct_pin("Location", VECTOR), struct_pin("Rotation", ROTATOR),
                                                        struct_pin("Scale", VECTOR, default="1,1,1")],
                       outputs=[struct_pin("ReturnValue", TRANSFORM, "out")], pure=True)
    ln(g, lifted, xf, "Location")
    g.link(level, "ReturnValue", xf, "Rotation")
    tp = g.call_self("TeleportAndStop", inputs=[struct_pin("NewTransform", TRANSFORM)])
    g.link(xf, "ReturnValue", tp, "NewTransform")
    g.exec(stamp, tp)
    said = log_line(g, "reset ", name_of(g, (g.self_node(), "self")))
    g.exec(tp, said)
    g.exec(said, result_bool(g, "true"))

    g = bp.function("SetLookBack", inputs=["bOn:bool"],
                    doc="Look-back (spec §5.3): the spring arm turns to the rear (ArmBaseRotation + 180 degrees of yaw) or back to the chase "
                        "view; the turn is a cut, not a swing (the arm's rotation lag is off until TickCamera's next frame).")
    s = g.var_set("bLookBack", BOOL)
    g.link_entry("bOn", s, "bLookBack")
    g.link_entry("then", s, "execute")
    base = g.call_static(MATH, "BreakRotator", inputs=[struct_pin("InRot", ROTATOR)],
                         outputs=[Pin("Roll", FLOAT, "out"), Pin("Pitch", FLOAT, "out"), Pin("Yaw", FLOAT, "out")], pure=True)
    g.link(g.var_get("ArmBaseRotation", STRUCT, struct_ref(ROTATOR)), "ArmBaseRotation", base, "InRot")
    turned = _f(g, "Add_FloatFloat", (base, "Yaw"), pick(g, ("entry", "bOn"), "180.0", "0.0"))
    want = g.call_static(MATH, "MakeRotator", inputs=[Pin("Roll", FLOAT), Pin("Pitch", FLOAT), Pin("Yaw", FLOAT)],
                         outputs=[struct_pin("ReturnValue", ROTATOR, "out")], pure=True)
    g.link(base, "Roll", want, "Roll")
    g.link(base, "Pitch", want, "Pitch")
    ln(g, turned, want, "Yaw")
    turn = g.call_on(SCENE_COMP, "K2_SetRelativeRotation", inputs=[struct_pin("NewRotation", ROTATOR), Pin("bSweep", BOOL, default="false"),
                                                                   Pin("bTeleport", BOOL, default="false")],
                     outputs=[struct_pin("SweepHitResult", HIT_RESULT, "out")])
    arm = spring_arm(g)
    g.link(arm[0], arm[1], turn, "self")
    g.link(want, "ReturnValue", turn, "NewRotation")
    no_lag = arm_set(g, "bEnableCameraRotationLag", BOOL, "false")
    snap = g.var_set("bSnapArm", BOOL, default="true")
    g.exec(s, turn, no_lag, snap)

    g = bp.function("ClearDriveState", doc="Ends look-back (the arm faces forward again), any drift (no boost), the smoothed steer and the held "
                    "handbrake. Called on exit, on TeleportAndStop (respawns, resets) and on pause, where a key release can be missed.")
    back = g.call_self("SetLookBack", inputs=[Pin("bOn", BOOL, default="false")])
    g.link_entry("then", back, "execute")
    g.exec(back, g.var_set("bDrifting", BOOL, default="false"), g.var_set("SmoothedSteer", FLOAT, default="0.0"),
           g.var_set("bHandbrakeHeld", BOOL, default="false"))

    g = bp.function("TickCamera", inputs=["DeltaSeconds:float"],
                    doc="A player's car only: the chase camera's FOV moves toward ComputeTargetFOV(speed, boosting) at FOVInterpSpeed /s "
                        "(spec §5.3); the spring arm's rotation and location lag come back on the frame after a look-back or teleport cut.")
    mine = g.call_self_native(PAWN, "IsPlayerControlled", outputs=[Pin("ReturnValue", BOOL, "out")], pure=True)
    bpl = g.branch()
    g.note(bpl, "driven by a player?")
    g.link(mine, "ReturnValue", bpl, "Condition")
    g.link_entry("then", bpl, "execute")
    target = g.call_self("ComputeTargetFOV", inputs=[Pin("SpeedKPH", FLOAT), Pin("bBoosting", BOOL)], outputs=[Pin("FOV", FLOAT, "out")], pure=True)
    ln(g, (g.call_self("GetSpeedKPH", outputs=[Pin("KPH", FLOAT, "out")], pure=True), "KPH"), target, "SpeedKPH")
    ln(g, _f(g, "Greater_FloatFloat", _fvar(g, "BoostRemaining"), "0.0", BOOL), target, "bBoosting")
    cam = chase_camera(g)
    fov = g.var_get_on(CAMERA_COMP, "FieldOfView", FLOAT)
    g.link(cam[0], cam[1], fov, "self")
    step = g.call_static(MATH, "FInterpTo", inputs=[Pin("Current", FLOAT), Pin("Target", FLOAT), Pin("DeltaTime", FLOAT), Pin("InterpSpeed", FLOAT)],
                         outputs=[Pin("ReturnValue", FLOAT, "out")], pure=True)
    g.link(fov, "FieldOfView", step, "Current")
    g.link(target, "FOV", step, "Target")
    g.link_entry("DeltaSeconds", step, "DeltaTime")
    ln(g, _fvar(g, "FOVInterpSpeed"), step, "InterpSpeed")
    set_fov = g.call_on(CAMERA_COMP, "SetFieldOfView", inputs=[Pin("InFieldOfView", FLOAT)])
    cam2 = chase_camera(g)
    g.link(cam2[0], cam2[1], set_fov, "self")
    g.link(step, "ReturnValue", set_fov, "InFieldOfView")
    g.link(bpl, "then", set_fov, "execute")
    bsnap = g.branch()
    g.note(bsnap, "a look-back or teleport cut this frame? keep the lag off once more")
    ln(g, _fvar(g, "bSnapArm", BOOL), bsnap, "Condition")
    g.exec(set_fov, bsnap)
    g.link(bsnap, "then", g.var_set("bSnapArm", BOOL, default="false"), "execute")
    rot_on = arm_set(g, "bEnableCameraRotationLag", BOOL, "true")
    g.link(bsnap, "else", rot_on, "execute")
    g.exec(rot_on, arm_set(g, "bEnableCameraLag", BOOL, "true"))

    # ---- Phase 7 Task 11: engine, skid and crash audio (spec §5.4) ----
    g = bp.function("TickAudio", inputs=["DeltaSeconds:float"],
                    doc="Spec §5.4, every frame: EngineAudio's pitch = ComputeEnginePitch(engine rpm / max rpm) and its volume = 0.35 + "
                        "0.65 x |throttle input| (clamped to 1), 0 for a parked or wrecked car (engine off) [call]; SkidAudio's volume = "
                        "clamp((|lateral speed| - 300) / 700, 0, 1) on the ground, 0 in the air.")
    rpm = mv_call(g, "GetEngineRotationSpeed", outputs=[Pin("ReturnValue", FLOAT, "out")], pure=True)
    max_rpm = mv_call(g, "GetEngineMaxRotationSpeed", outputs=[Pin("ReturnValue", FLOAT, "out")], pure=True)
    pitch = g.call_self("ComputeEnginePitch", inputs=[Pin("RPMRatio", FLOAT)], outputs=[Pin("Pitch", FLOAT, "out")], pure=True)
    ln(g, _f(g, "SafeDivide", (rpm, "ReturnValue"), (max_rpm, "ReturnValue")), pitch, "RPMRatio")
    set_pitch = audio_call(g, "EngineAudio", "SetPitchMultiplier", inputs=[Pin("NewPitchMultiplier", FLOAT)])
    g.link(pitch, "Pitch", set_pitch, "NewPitchMultiplier")
    g.link_entry("then", set_pitch, "execute")
    # a car nobody drives (parked, the menu's showcase cars) or a wreck has its engine off: TickDriveOverrides' "parked"
    driver = g.call_self_native(PAWN, "GetController", outputs=[obj_pin("ReturnValue", CONTROLLER, "out")], pure=True)
    has_driver = is_valid(g)
    g.link(driver, "ReturnValue", has_driver, "Object")
    intact = not_bool(g)
    ln(g, _fvar(g, "bIsDestroyed", BOOL), intact, "A")
    running = and_bool(g)
    g.link(has_driver, "ReturnValue", running, "A")
    g.link(intact, "ReturnValue", running, "B")
    throttle = _f(g, "FMin", _f(g, "Abs", _fvar(g, "ArcadeThrottle")), "1.0")
    volume = _f(g, "Add_FloatFloat", "0.35", _f(g, "Multiply_FloatFloat", throttle, "0.65"))
    set_vol = audio_call(g, "EngineAudio", "SetVolumeMultiplier", inputs=[Pin("NewVolumeMultiplier", FLOAT)])
    ln(g, pick(g, (running, "ReturnValue"), volume, "0.0"), set_vol, "NewVolumeMultiplier")
    lateral = _vbin(g, "Dot_VectorVector", _self_vec(g, "GetVelocity"), _self_vec(g, "GetActorRightVector"))
    slip = clamp01(g, _f(g, "Divide_FloatFloat", _f(g, "Subtract_FloatFloat", _f(g, "Abs", lateral), "300.0"), "700.0"))
    set_skid = audio_call(g, "SkidAudio", "SetVolumeMultiplier", inputs=[Pin("NewVolumeMultiplier", FLOAT)])
    ln(g, pick(g, _fvar(g, "bGrounded", BOOL), slip, "0.0"), set_skid, "NewVolumeMultiplier")
    g.exec(set_pitch, set_vol, set_skid)

    g = bp.function("HandleCrashHit", inputs=["NormalImpulse:struct:" + VECTOR, "Location:struct:" + VECTOR], outputs=["ReturnValue:bool"],
                    doc="Spec §5.4: a hit whose normal impulse is above CrashImpulse, at least CrashCooldown s after the last crash, plays "
                        "CrashSound at the contact and gives the driver a light camera shake (§5.3). Returns whether it did.")
    size = g.call_static(MATH, "VSize", inputs=[struct_pin("A", VECTOR)], outputs=[Pin("ReturnValue", FLOAT, "out")], pure=True)
    g.link_entry("NormalImpulse", size, "A")
    hard = _f(g, "Greater_FloatFloat", (size, "ReturnValue"), _fvar(g, "CrashImpulse"), BOOL)
    since = _f(g, "Subtract_FloatFloat", (game_time(g), "ReturnValue"), _fvar(g, "LastCrashTime"))
    ready = _f(g, "GreaterEqual_FloatFloat", since, _fvar(g, "CrashCooldown"), BOOL)
    crash = and_bool(g)
    ln(g, hard, crash, "A")
    ln(g, ready, crash, "B")
    bc = g.branch()
    g.note(bc, "hard enough, and CrashCooldown since the last crash?")
    g.link(crash, "ReturnValue", bc, "Condition")
    g.link_entry("then", bc, "execute")
    g.link(bc, "else", result_bool(g, "false"), "execute")
    stamp = g.var_set("LastCrashTime", FLOAT)
    g.link(game_time(g), "ReturnValue", stamp, "LastCrashTime")
    g.link(bc, "then", stamp, "execute")
    bang = g.call_static(GAMEPLAY, "PlaySoundAtLocation",
                         inputs=[Pin("WorldContextObject", OBJECT, hidden=True), obj_pin("Sound", SOUND_BASE), struct_pin("Location", VECTOR),
                                 struct_pin("Rotation", ROTATOR), Pin("VolumeMultiplier", FLOAT, default="1.0"),
                                 Pin("PitchMultiplier", FLOAT, default="1.0"), Pin("StartTime", FLOAT, default="0.0"),
                                 obj_pin("AttenuationSettings", "/Script/Engine.SoundAttenuation"),
                                 obj_pin("ConcurrencySettings", "/Script/Engine.SoundConcurrency"), obj_pin("OwningActor", ACTOR)])
    g.link(g.var_get("CrashSound", OBJECT, cls_ref(SOUND_BASE)), "CrashSound", bang, "Sound")
    g.link_entry("Location", bang, "Location")
    g.exec(stamp, bang, driver_shake(g), result_bool(g, "true"))

    # ---- Phase 3: effects and item use (spec 2026-10-30 §2) ----
    g = bp.function("IsShielded", doc="A shield is running.", outputs=["ReturnValue:bool"], pure=True)
    sr = g.var_get("ShieldRemaining", FLOAT)
    gt = compare(g, "Greater_FloatFloat", FLOAT, b="0.0")
    g.link(sr, "ShieldRemaining", gt, "A")
    g.link_result(gt, "ReturnValue", "ReturnValue")
    g.link_entry("then", "result", "execute")

    # ActivateBoost: timer + an instant forward kick
    g = bp.function("ActivateBoost", doc="Starts the boost timer and kicks the car forward.")
    dur = g.var_get("BoostDuration", FLOAT)
    sb = g.var_set("BoostRemaining", FLOAT)
    g.link(dur, "BoostDuration", sb, "BoostRemaining")
    g.link_entry("then", sb, "execute")
    fwd = g.call_self_native(ACTOR, "GetActorForwardVector", outputs=[struct_pin("ReturnValue", VECTOR, "out")], pure=True)
    ks = g.var_get("BoostKickSpeed", FLOAT)
    kick = g.call_static(MATH, "Multiply_VectorFloat", inputs=[struct_pin("A", VECTOR), Pin("B", FLOAT)],
                         outputs=[struct_pin("ReturnValue", VECTOR, "out")], pure=True)
    g.link(fwd, "ReturnValue", kick, "A")
    g.link(ks, "BoostKickSpeed", kick, "B")
    m = mesh(g)
    vel = g.call_on(PRIMITIVE, "SetPhysicsLinearVelocity",
                    inputs=[struct_pin("NewVel", VECTOR), Pin("bAddToCurrent", BOOL, default="true"), Pin("BoneName", NAME, default="None")])
    g.link(m, "Mesh", vel, "self")
    g.link(kick, "ReturnValue", vel, "NewVel")
    g.exec(sb, vel, car_sound(g, "BoostSound"), g.call_self("RefreshEffectLook"))  # Phase 7 Task 17: the sound, the flames at once

    g = bp.function("ActivateShield", doc="Starts the shield timer (the shield-up sound; the bubble shows at once).")
    dur = g.var_get("ShieldDuration", FLOAT)
    ss = g.var_set("ShieldRemaining", FLOAT)
    g.link(dur, "ShieldDuration", ss, "ShieldRemaining")
    g.link_entry("then", ss, "execute")
    g.exec(ss, car_sound(g, "ShieldUpSound"), g.call_self("RefreshEffectLook"))  # Phase 7 Task 17

    g = bp.function("ClearEffects", doc="Ends boost and shield (silently: a restart or a respawn, not the shield running out).")
    cb = g.var_set("BoostRemaining", FLOAT, default="0.0")
    cs = g.var_set("ShieldRemaining", FLOAT, default="0.0")
    g.link_entry("then", cb, "execute")
    g.exec(cb, cs, g.var_set("bShieldShown", BOOL, default="false"), g.call_self("RefreshEffectLook"))  # Phase 7 Task 17

    # ---- Phase 7 Task 17 (spec §7.5): the items on the car: boost flames, the shield bubble and its sounds ----
    g = bp.function("RefreshEffectLook", doc="BoostFlameL/R show while BoostRemaining > 0 and ShieldBubble while IsShielded(); "
                    "the shield's end (shown, now not shielded) plays ShieldDownSound.")
    boosting = _f(g, "Greater_FloatFloat", _fvar(g, "BoostRemaining"), "0.0", BOOL)
    flames = [set_shown(g, name, src=boosting) for name in ("BoostFlameL", "BoostFlameR")]
    g.link_entry("then", flames[0], "execute")
    g.exec(*flames)
    shielded = (g.call_self("IsShielded", outputs=[Pin("ReturnValue", BOOL, "out")], pure=True), "ReturnValue")
    unshielded = not_bool(g)
    g.link(shielded[0], shielded[1], unshielded, "A")
    ended = and_bool(g)
    g.link(g.var_get("bShieldShown", BOOL), "bShieldShown", ended, "A")
    g.link(unshielded, "ReturnValue", ended, "B")
    bend = g.branch()
    g.note(bend, "the shield just ran out?")
    g.link(ended, "ReturnValue", bend, "Condition")
    g.exec(flames[-1], bend)
    down = car_sound(g, "ShieldDownSound")
    g.link(bend, "then", down, "execute")
    keep = g.var_set("bShieldShown", BOOL)
    g.link(shielded[0], shielded[1], keep, "bShieldShown")
    g.exec(down, keep)
    g.link(bend, "else", keep, "execute")
    g.exec(keep, set_shown(g, "ShieldBubble", src=shielded))

    g = bp.function("ShieldHit", doc="A blocked hit: ShieldHitSound, and the bubble glows ShieldHitGlow for ShieldHitSeconds.")
    flash = mid_glow(g, (g.var_get("ShieldHitGlow", FLOAT), "ShieldHitGlow"))
    g.link_entry("then", flash, "execute")
    g.exec(flash, car_sound(g, "ShieldHitSound"), timer(g, "EndShieldHit", (g.var_get("ShieldHitSeconds", FLOAT), "ShieldHitSeconds"), looping=False))

    g = bp.function("EndShieldHit", doc="The bubble's flash is over: its own glow again (ShieldBaseGlow).")
    g.link_entry("then", mid_glow(g, (g.var_get("ShieldBaseGlow", FLOAT), "ShieldBaseGlow")), "execute")

    # TickEffects(DeltaSeconds): sustained boost force; both timers run down to 0
    g = bp.function("TickEffects", doc="Per-frame boost force; both effect timers run down; the flames and the bubble follow them "
                    "(RefreshEffectLook).", inputs=["DeltaSeconds:float"])
    br_ = g.var_get("BoostRemaining", FLOAT)
    on = compare(g, "Greater_FloatFloat", FLOAT, b="0.0")
    g.link(br_, "BoostRemaining", on, "A")
    b = g.branch()
    g.link(on, "ReturnValue", b, "Condition")
    g.link_entry("then", b, "execute")
    fwd = g.call_self_native(ACTOR, "GetActorForwardVector", outputs=[struct_pin("ReturnValue", VECTOR, "out")], pure=True)
    acc = g.var_get("BoostAcceleration", FLOAT)
    force = g.call_static(MATH, "Multiply_VectorFloat", inputs=[struct_pin("A", VECTOR), Pin("B", FLOAT)],
                          outputs=[struct_pin("ReturnValue", VECTOR, "out")], pure=True)
    g.link(fwd, "ReturnValue", force, "A")
    g.link(acc, "BoostAcceleration", force, "B")
    m = mesh(g)
    af = g.call_on(PRIMITIVE, "AddForce", inputs=[struct_pin("Force", VECTOR), Pin("BoneName", NAME, default="None"),
                                                  Pin("bAccelChange", BOOL, default="true")])
    g.link(m, "Mesh", af, "self")
    g.link(force, "ReturnValue", af, "Force")
    g.link(b, "then", af, "execute")
    for var, prev_out in (("BoostRemaining", None), ("ShieldRemaining", None)):
        cur = g.var_get(var, FLOAT)
        sub = math2(g, "Subtract_FloatFloat", FLOAT)
        g.link(cur, var, sub, "A")
        g.link_entry("DeltaSeconds", sub, "B")
        mx = g.call_static(MATH, "FMax", inputs=[Pin("A", FLOAT), Pin("B", FLOAT, default="0.0")],
                           outputs=[Pin("ReturnValue", FLOAT, "out")], pure=True)
        g.link(sub, "ReturnValue", mx, "A")
        setv = g.var_set(var, FLOAT)
        g.link(mx, "ReturnValue", setv, var)
        if var == "BoostRemaining":
            g.exec(af, setv)
            g.link(b, "else", setv, "execute")
            first = setv
        else:
            g.exec(first, setv, g.call_self("RefreshEffectLook"))  # Phase 7 Task 17: flames and bubble follow the timers

    # CanUseItem(Type): the gun waits for its cooldown (no charge wasted on a dry press); every other item is always usable
    WC = gen(BPC_WEAPON)
    g = bp.function("CanUseItem", doc="The gun waits for its cooldown; every other item is always usable.", inputs=["Type:" + enum_spec(E_ITEM_TYPE)], outputs=["ReturnValue:bool"], pure=True)
    b = g.branch()
    g.link(enum_is(g, ("entry", "Type"), ITEM_GUN), "ReturnValue", b, "Condition")
    g.link_entry("then", b, "execute")
    wp = g.var_get("Weapon", OBJECT, cls_ref(WC))
    can = g.call_on(WC, "CanFire", outputs=[Pin("ReturnValue", BOOL, "out")], pure=True)
    g.link(wp, "Weapon", can, "self")
    r_gun = g.function_result([Pin("ReturnValue", BOOL)])
    g.link(can, "ReturnValue", r_gun, "ReturnValue")
    g.link(b, "then", r_gun, "execute")
    g.link(b, "else", result_bool(g, "true"), "execute")

    # GetMuzzleLocation(): in front of the bumper, above the hood
    g = bp.function("GetMuzzleLocation", doc="In front of the bumper, above the hood.", outputs=["Location:struct:" + VECTOR], pure=True)
    loc = self_actor_location(g)
    fwd = g.call_self_native(ACTOR, "GetActorForwardVector", outputs=[struct_pin("ReturnValue", VECTOR, "out")], pure=True)
    up = g.call_self_native(ACTOR, "GetActorUpVector", outputs=[struct_pin("ReturnValue", VECTOR, "out")], pure=True)
    mf, mu = g.var_get("MuzzleForward", FLOAT), g.var_get("MuzzleUp", FLOAT)
    f = g.call_static(MATH, "Multiply_VectorFloat", inputs=[struct_pin("A", VECTOR), Pin("B", FLOAT)], outputs=[struct_pin("ReturnValue", VECTOR, "out")], pure=True)
    g.link(fwd, "ReturnValue", f, "A")
    g.link(mf, "MuzzleForward", f, "B")
    u = g.call_static(MATH, "Multiply_VectorFloat", inputs=[struct_pin("A", VECTOR), Pin("B", FLOAT)], outputs=[struct_pin("ReturnValue", VECTOR, "out")], pure=True)
    g.link(up, "ReturnValue", u, "A")
    g.link(mu, "MuzzleUp", u, "B")
    a1 = g.call_static(MATH, "Add_VectorVector", inputs=[struct_pin("A", VECTOR), struct_pin("B", VECTOR)], outputs=[struct_pin("ReturnValue", VECTOR, "out")], pure=True)
    g.link(loc, "ReturnValue", a1, "A")
    g.link(f, "ReturnValue", a1, "B")
    a2 = g.call_static(MATH, "Add_VectorVector", inputs=[struct_pin("A", VECTOR), struct_pin("B", VECTOR)], outputs=[struct_pin("ReturnValue", VECTOR, "out")], pure=True)
    g.link(a1, "ReturnValue", a2, "A")
    g.link(u, "ReturnValue", a2, "B")
    g.link_result(a2, "ReturnValue", "Location")
    g.link_entry("then", "result", "execute")

    # GetAimDirection(): straight ahead, or at an AI's AimTarget (its centre, 60 cm up) for one shot
    g = bp.function("GetAimDirection", outputs=["Direction:struct:" + VECTOR], pure=True,
                    doc="Where a shot goes: at AimTarget's centre (60 cm up) when an AI set one, else straight ahead.")
    at = g.var_get("AimTarget", OBJECT, cls_ref(ACTOR))
    av = is_valid(g)
    g.link(at, "AimTarget", av, "Object")
    b = g.branch()
    g.link(av, "ReturnValue", b, "Condition")
    g.link_entry("then", b, "execute")
    tloc = g.call_on(ACTOR, "K2_GetActorLocation", outputs=[struct_pin("ReturnValue", VECTOR, "out")], pure=True)
    g.link(at, "AimTarget", tloc, "self")
    raised = g.call_static(MATH, "Add_VectorVector", inputs=[struct_pin("A", VECTOR), struct_pin("B", VECTOR, default="0,0,60")],
                           outputs=[struct_pin("ReturnValue", VECTOR, "out")], pure=True)
    g.link(tloc, "ReturnValue", raised, "A")
    mz = g.call_self("GetMuzzleLocation", outputs=[struct_pin("Location", VECTOR, "out")], pure=True)
    diff = g.call_static(MATH, "Subtract_VectorVector", inputs=[struct_pin("A", VECTOR), struct_pin("B", VECTOR)],
                         outputs=[struct_pin("ReturnValue", VECTOR, "out")], pure=True)
    g.link(raised, "ReturnValue", diff, "A")
    g.link(mz, "Location", diff, "B")
    unit = g.call_static(MATH, "Normal", inputs=[struct_pin("A", VECTOR), Pin("Tolerance", FLOAT, default="0.0001")],
                         outputs=[struct_pin("ReturnValue", VECTOR, "out")], pure=True)
    g.link(diff, "ReturnValue", unit, "A")
    r_aim = g.function_result([struct_pin("Direction", VECTOR)])
    g.link(unit, "ReturnValue", r_aim, "Direction")
    g.link(b, "then", r_aim, "execute")
    fwd0 = g.call_self_native(ACTOR, "GetActorForwardVector", outputs=[struct_pin("ReturnValue", VECTOR, "out")], pure=True)
    r_fwd = g.function_result([struct_pin("Direction", VECTOR)])
    g.link(fwd0, "ReturnValue", r_fwd, "Direction")
    g.link(b, "else", r_fwd, "execute")

    # FireGun() -> bool: one hitscan shot from the muzzle along the aim direction, credited to the driver
    g = bp.function("FireGun", doc="One hitscan shot from the muzzle along the aim direction, credited to the driver.", outputs=["ReturnValue:bool"])
    muzzle = g.call_self("GetMuzzleLocation", outputs=[struct_pin("Location", VECTOR, "out")], pure=True)
    fwd = g.call_self("GetAimDirection", outputs=[struct_pin("Direction", VECTOR, "out")], pure=True)
    ctrl = g.call_self_native(PAWN, "GetController", outputs=[obj_pin("ReturnValue", CONTROLLER, "out")], pure=True)
    wp = g.var_get("Weapon", OBJECT, cls_ref(WC))
    shot = g.call_on(WC, "Fire", inputs=[struct_pin("Origin", VECTOR), struct_pin("Direction", VECTOR), obj_pin("Instigator", CONTROLLER)],
                     outputs=[Pin("bHit", BOOL, "out"), struct_pin("Hit", HIT_RESULT, "out")])
    g.link(wp, "Weapon", shot, "self")
    g.link(muzzle, "Location", shot, "Origin")
    g.link(fwd, "Direction", shot, "Direction")
    g.link(ctrl, "ReturnValue", shot, "Instigator")
    g.link_entry("then", shot, "execute")
    r = g.function_result([Pin("ReturnValue", BOOL)])
    g.link(shot, "bHit", r, "ReturnValue")
    g.exec(shot, r)

    # FireRPG() -> Projectile: a BP_DFProjectile from the muzzle, owned by the car, credited to the driver
    PROJC = gen(BP_PROJECTILE)
    g = bp.function("FireRPG", doc="Launches a rocket from the muzzle (short of anything blocking it), credited to the driver.", outputs=["Projectile:" + obj_spec(BP_PROJECTILE)])
    muzzle = g.call_self("GetMuzzleLocation", outputs=[struct_pin("Location", VECTOR, "out")], pure=True)
    # point-blank: when something blocks the way from the car's centre to the muzzle, the rocket starts 25 cm short of it
    # (spawning inside a rock or a car would push the rocket through without a hit)
    loc = self_actor_location(g)
    up = g.call_self_native(ACTOR, "GetActorUpVector", outputs=[struct_pin("ReturnValue", VECTOR, "out")], pure=True)
    mu = g.var_get("MuzzleUp", FLOAT)
    upv = g.call_static(MATH, "Multiply_VectorFloat", inputs=[struct_pin("A", VECTOR), Pin("B", FLOAT)], outputs=[struct_pin("ReturnValue", VECTOR, "out")], pure=True)
    g.link(up, "ReturnValue", upv, "A")
    g.link(mu, "MuzzleUp", upv, "B")
    start = g.call_static(MATH, "Add_VectorVector", inputs=[struct_pin("A", VECTOR), struct_pin("B", VECTOR)], outputs=[struct_pin("ReturnValue", VECTOR, "out")], pure=True)
    g.link(loc, "ReturnValue", start, "A")
    g.link(upv, "ReturnValue", start, "B")
    tr = g.call_static(SYS, "LineTraceSingle",
                       inputs=[Pin("WorldContextObject", OBJECT, hidden=True), struct_pin("Start", VECTOR), struct_pin("End", VECTOR),
                               Pin("TraceChannel", "byte", default="TraceTypeQuery1"), Pin("bTraceComplex", BOOL, default="false"),
                               Pin("DrawDebugType", "byte", default="None"), Pin("bIgnoreSelf", BOOL, default="true")],
                       outputs=[struct_pin("OutHit", HIT_RESULT, "out"), Pin("ReturnValue", BOOL, "out")])
    g.link(start, "ReturnValue", tr, "Start")
    g.link(muzzle, "Location", tr, "End")
    g.link_entry("then", tr, "execute")
    brk = g.call_static(GAMEPLAY, "BreakHitResult", inputs=[struct_pin("Hit", HIT_RESULT)],
                        outputs=[struct_pin("ImpactPoint", VECTOR, "out")], pure=True)
    g.link(tr, "OutHit", brk, "Hit")
    fwd = g.call_self_native(ACTOR, "GetActorForwardVector", outputs=[struct_pin("ReturnValue", VECTOR, "out")], pure=True)
    back = g.call_static(MATH, "Multiply_VectorFloat", inputs=[struct_pin("A", VECTOR), Pin("B", FLOAT, default="-25.0")], outputs=[struct_pin("ReturnValue", VECTOR, "out")], pure=True)
    g.link(fwd, "ReturnValue", back, "A")
    short = g.call_static(MATH, "Add_VectorVector", inputs=[struct_pin("A", VECTOR), struct_pin("B", VECTOR)], outputs=[struct_pin("ReturnValue", VECTOR, "out")], pure=True)
    g.link(brk, "ImpactPoint", short, "A")
    g.link(back, "ReturnValue", short, "B")
    at = g.call_static(MATH, "SelectVector", inputs=[struct_pin("A", VECTOR), struct_pin("B", VECTOR), Pin("bPickA", BOOL)],
                       outputs=[struct_pin("ReturnValue", VECTOR, "out")], pure=True)
    g.link(short, "ReturnValue", at, "A")
    g.link(muzzle, "Location", at, "B")
    g.link(tr, "ReturnValue", at, "bPickA")
    aim = g.call_self("GetAimDirection", outputs=[struct_pin("Direction", VECTOR, "out")], pure=True)
    rot = g.call_static(MATH, "MakeRotFromX", inputs=[struct_pin("X", VECTOR)], outputs=[struct_pin("ReturnValue", ROTATOR, "out")], pure=True)
    g.link(aim, "Direction", rot, "X")
    xf = g.call_static(MATH, "MakeTransform", inputs=[struct_pin("Location", VECTOR), struct_pin("Rotation", ROTATOR),
                                                        struct_pin("Scale", VECTOR, default="1,1,1")],
                       outputs=[struct_pin("ReturnValue", TRANSFORM, "out")], pure=True)
    g.link(at, "ReturnValue", xf, "Location")
    g.link(rot, "ReturnValue", xf, "Rotation")
    sp = g.spawn_actor(PROJC)
    g.link(xf, "ReturnValue", sp, "SpawnTransform")
    me = g.self_node()
    g.link(me, "self", sp, "Owner")
    g.exec(tr, sp)
    launched = log_line(g, "rocket fired at ", vec_str(g, (at, "ReturnValue")), " (muzzle blocked: ", bool_str(g, (tr, "ReturnValue")), ")")
    whoosh = play_sound_at(g, (g.var_get("RocketLaunchSound", OBJECT, cls_ref(SOUND_BASE)), "RocketLaunchSound"), (at, "ReturnValue"))  # Task 16
    g.exec(sp, whoosh, launched)
    ctrl = g.call_self_native(PAWN, "GetController", outputs=[obj_pin("ReturnValue", CONTROLLER, "out")], pure=True)
    sic = g.var_set_on(PROJC, "InstigatorController", OBJECT, sub_object=cls_ref(CONTROLLER))
    g.link(sp, "ReturnValue", sic, "self")
    g.link(ctrl, "ReturnValue", sic, "InstigatorController")
    g.exec(launched, sic)
    r = g.function_result([obj_pin("Projectile", PROJC)])
    g.link(sp, "ReturnValue", r, "Projectile")
    g.exec(sic, r)

    # ApplyItem(Type): the item's effect on this car
    g = bp.function("ApplyItem", doc="Runs an item's effect on this car.", inputs=["Type:" + enum_spec(E_ITEM_TYPE)])
    prev = ("entry", "then")
    for idx, fn_name in ((ITEM_BOOST, "ActivateBoost"), (ITEM_SHIELD, "ActivateShield"), (ITEM_BOMB, "DropBomb"),
                         (ITEM_GUN, "FireGun"), (ITEM_RPG, "FireRPG")):
        b = g.branch()
        g.link(enum_is(g, ("entry", "Type"), idx), "ReturnValue", b, "Condition")
        g.link(prev[0], prev[1], b, "execute")
        n = g.call_self(fn_name)
        g.link(b, "then", n, "execute")
        prev = (b, "else")

    # DropBomb() -> Bomb: a BP_DFBomb BombDropOffset behind the car, owned by it, credited to its controller (spec §2, §6)
    BOMBC = gen(BP_BOMB)
    g = bp.function("DropBomb", doc="Drops a bomb behind the car, credited to the driver.", outputs=["Bomb:" + obj_spec(BP_BOMB)])
    loc = self_actor_location(g)
    fwd = g.call_self_native(ACTOR, "GetActorForwardVector", outputs=[struct_pin("ReturnValue", VECTOR, "out")], pure=True)
    off = g.var_get("BombDropOffset", FLOAT)
    neg = math2(g, "Multiply_FloatFloat", FLOAT, b="-1.0")
    g.link(off, "BombDropOffset", neg, "A")
    back = g.call_static(MATH, "Multiply_VectorFloat", inputs=[struct_pin("A", VECTOR), Pin("B", FLOAT)],
                         outputs=[struct_pin("ReturnValue", VECTOR, "out")], pure=True)
    g.link(fwd, "ReturnValue", back, "A")
    g.link(neg, "ReturnValue", back, "B")
    at = g.call_static(MATH, "Add_VectorVector", inputs=[struct_pin("A", VECTOR), struct_pin("B", VECTOR)],
                       outputs=[struct_pin("ReturnValue", VECTOR, "out")], pure=True)
    g.link(loc, "ReturnValue", at, "A")
    g.link(back, "ReturnValue", at, "B")
    lift = g.call_static(MATH, "Add_VectorVector", inputs=[struct_pin("A", VECTOR), struct_pin("B", VECTOR, default="0,0,30")],
                         outputs=[struct_pin("ReturnValue", VECTOR, "out")], pure=True)
    g.link(at, "ReturnValue", lift, "A")
    rot = g.call_self_native(ACTOR, "K2_GetActorRotation", outputs=[struct_pin("ReturnValue", ROTATOR, "out")], pure=True)
    # the spawn transform's scale becomes the root (Shell) scale: 1, the mine's own size (Phase 7 Task 17; the stock sphere was 0.5)
    xf = g.call_static(MATH, "MakeTransform", inputs=[struct_pin("Location", VECTOR), struct_pin("Rotation", ROTATOR),
                                                        struct_pin("Scale", VECTOR, default="1,1,1")],
                       outputs=[struct_pin("ReturnValue", TRANSFORM, "out")], pure=True)
    g.link(lift, "ReturnValue", xf, "Location")
    g.link(rot, "ReturnValue", xf, "Rotation")
    sp = g.spawn_actor(BOMBC)
    g.link(xf, "ReturnValue", sp, "SpawnTransform")
    me = g.self_node()
    g.link(me, "self", sp, "Owner")
    g.link_entry("then", sp, "execute")
    ctrl = g.call_self_native(PAWN, "GetController", outputs=[obj_pin("ReturnValue", CONTROLLER, "out")], pure=True)
    sic = g.var_set_on(BOMBC, "InstigatorController", OBJECT, sub_object=cls_ref(CONTROLLER))
    g.link(sp, "ReturnValue", sic, "self")
    g.link(ctrl, "ReturnValue", sic, "InstigatorController")
    g.exec(sp, sic)
    r = g.function_result([obj_pin("Bomb", BOMBC)])
    g.link(sp, "ReturnValue", r, "Bomb")
    g.exec(sic, r)

    # UseSelectedItem() -> bool: wrecked / no controller / no racer / nothing selected / cannot use -> false; else consume + apply
    g = bp.function("UseSelectedItem", doc="Consumes and applies the driver's selected item; refused when wrecked, empty or on cooldown.", outputs=["ReturnValue:bool"], locals=["Racer:object:" + gen(BPC_RACER)])
    RC_ = gen(BPC_RACER)
    dead = g.var_get("bIsDestroyed", BOOL)
    b0 = g.branch()
    g.link(dead, "bIsDestroyed", b0, "Condition")
    g.link_entry("then", b0, "execute")
    g.link(b0, "then", result_bool(g, "false"), "execute")
    ctrl = g.call_self_native(PAWN, "GetController", outputs=[obj_pin("ReturnValue", CONTROLLER, "out")], pure=True)
    gm = get_game_mode(g)
    cast = cast_to(g, BP_GM)
    g.link(gm, "ReturnValue", cast, "Object")
    g.link(b0, "else", cast, "execute")
    g.link(cast, "CastFailed", result_bool(g, "false"), "execute")
    racer = g.call_on(GMC, "FindRacer", inputs=[obj_pin("C", CONTROLLER)], outputs=[obj_pin("Racer", RC_, "out")], pure=True)
    g.link(cast, as_pin(BP_GM), racer, "self")
    g.link(ctrl, "ReturnValue", racer, "C")
    sl = g.local_set("Racer", OBJECT, sub_object=cls_ref(RC_))
    g.link(racer, "Racer", sl, "Racer")
    g.link(cast, "then", sl, "execute")
    rv = is_valid(g)
    g.link(sl, "Output_Get", rv, "Object")
    bv = g.branch()
    g.link(rv, "ReturnValue", bv, "Condition")
    g.exec(sl, bv)
    g.link(bv, "else", result_bool(g, "false"), "execute")
    lr = lambda: (g.local_get("Racer", OBJECT, cls_ref(RC_)), "Racer")
    sel = g.call_on(RC_, "GetSelected", outputs=[enum_pin("Type", E_ITEM_TYPE, "out"), Pin("Charges", INT, "out")], pure=True)
    r0 = lr()
    g.link(r0[0], r0[1], sel, "self")
    bn = g.branch()
    g.link(enum_is(g, (sel, "Type"), ITEM_NONE), "ReturnValue", bn, "Condition")
    g.link(bv, "then", bn, "execute")
    g.link(bn, "then", result_bool(g, "false"), "execute")
    can = g.call_self("CanUseItem", inputs=[enum_pin("Type", E_ITEM_TYPE)], outputs=[Pin("ReturnValue", BOOL, "out")], pure=True)
    g.link(sel, "Type", can, "Type")
    bc = g.branch()
    g.link(can, "ReturnValue", bc, "Condition")
    g.link(bn, "else", bc, "execute")
    g.link(bc, "else", result_bool(g, "false"), "execute")
    cons = g.call_on(RC_, "ConsumeSelected", outputs=[enum_pin("Type", E_ITEM_TYPE, "out")])
    r1 = lr()
    g.link(r1[0], r1[1], cons, "self")
    g.link(bc, "then", cons, "execute")
    ap = g.call_self("ApplyItem", inputs=[enum_pin("Type", E_ITEM_TYPE)])
    g.link(cons, "Type", ap, "Type")
    g.exec(cons, ap)
    info = g.call_on(GMC, "GetItemInfo", inputs=[enum_pin("Type", E_ITEM_TYPE)],
                     outputs=[Pin("Name", STRING, "out"), Pin("BoxCharges", INT, "out"), Pin("MaxCharges", INT, "out")], pure=True)
    g.link(cast, as_pin(BP_GM), info, "self")
    g.link(cons, "Type", info, "Type")
    log = log_line(g, "used ", (info, "Name"), " by ", name_of(g, (ctrl, "ReturnValue")))
    g.exec(ap, g.call_self("RefreshRoofWeapon"), log)  # Phase 7 Task 13: a used-up Gun or RPG leaves the roof
    g.exec(log, result_bool(g, "true"))

    # CycleItem(): next slot of the driver's inventory
    g = bp.function("CycleItem", doc="Selects the driver's next inventory slot.")
    ctrl = g.call_self_native(PAWN, "GetController", outputs=[obj_pin("ReturnValue", CONTROLLER, "out")], pure=True)
    gm = get_game_mode(g)
    cast = cast_to(g, BP_GM)
    g.link(gm, "ReturnValue", cast, "Object")
    g.link_entry("then", cast, "execute")
    cy = g.call_on(GMC, "CycleItem", inputs=[obj_pin("C", CONTROLLER)])
    g.link(cast, as_pin(BP_GM), cy, "self")
    g.link(ctrl, "ReturnValue", cy, "C")
    g.link(cast, "then", cy, "execute")

    # ---- Construction script (Phase 7 Task 13, spec §6.1): the class's body, and its light bar if it has one ----
    g = bp.construction_script()
    par = g.call_parent(gen(SEDAN), "UserConstructionScript")
    g.link_entry("then", par, "execute")
    body = set_mesh(g, "Body", src=(g.var_get("BodyMesh", OBJECT, cls_ref(STATIC_MESH)), "BodyMesh"))
    bar = set_shown(g, "LightBar", src=(g.var_get("bHasLightBar", BOOL), "bHasLightBar"))
    g.exec(par, body, bar)

    # ---- Event graph ----
    g = bp.event_graph()
    g.section("Begin Play: fresh tires, full health, the paint, the gun seen to fire from the roof weapon")
    bpl = g.begin_play(col=0, row=1)
    par = g.call_parent(gen(SEDAN), "ReceiveBeginPlay", col=1, row=1)
    init = g.call_self("InitTires", col=2, row=1)
    g.exec(bpl, par, init)
    full = g.var_set("Health", FLOAT)  # Phase 5: a child with more MaxHealth starts full
    g.link(g.var_get("MaxHealth", FLOAT), "MaxHealth", full, "Health")
    g.exec(init, full)
    # Phase 7 Task 9 (spec §5.2): a lower centre of mass (the vehicle re-reads it through OnRecalculatedMassProperties)
    com = g.call_on(PRIMITIVE, "SetCenterOfMass", inputs=[struct_pin("CenterOfMassOffset", VECTOR), Pin("BoneName", NAME, default="None")])
    g.link(mesh(g), "Mesh", com, "self")
    com_v = g.call_static(MATH, "MakeVector", inputs=[Pin("X", FLOAT, default="0.0"), Pin("Y", FLOAT, default="0.0"), Pin("Z", FLOAT)],
                          outputs=[struct_pin("ReturnValue", VECTOR, "out")], pure=True)
    g.link(g.var_get("CenterOfMassZ", FLOAT), "CenterOfMassZ", com_v, "Z")
    g.link(com_v, "ReturnValue", com, "CenterOfMassOffset")
    g.exec(full, com)
    # Phase 7 Task 11 (spec §5.4): hit events for the crash sound. A skeletal body notifies only when the component AND its
    # physics-asset body ask for it (FBodyInstance::BuildBodyFilterData); the Sedan physics asset's body
    # does not, so no OnComponentHit ever fired. USkeletalMeshComponent::SetNotifyRigidBodyCollision sets it on every body.
    notify = g.call_on(PRIMITIVE, "SetNotifyRigidBodyCollision", inputs=[Pin("bNewNotifyRigidBodyCollision", BOOL, default="true")])
    g.link(mesh(g), "Mesh", notify, "self")
    g.exec(com, notify)
    # Phase 7 Task 10 (spec §5.3): the chase rotation look-back returns to, and the camera lags; the SpringArm is the Sedan
    # Blueprint's component (component_defaults only reach native components), so its members are set here
    base = g.var_set("ArmBaseRotation", STRUCT, sub_object=struct_ref(ROTATOR))
    rel = g.var_get_on(SCENE_COMP, "RelativeRotation", STRUCT, struct_ref(ROTATOR))
    arm = spring_arm(g)
    g.link(arm[0], arm[1], rel, "self")
    g.link(rel, "RelativeRotation", base, "ArmBaseRotation")
    lag = arm_set(g, "bEnableCameraLag", BOOL, "true")
    lag_speed = arm_set(g, "CameraLagSpeed", FLOAT, src=(g.var_get("ChaseLagSpeed", FLOAT), "ChaseLagSpeed"))
    rot_lag = arm_set(g, "bEnableCameraRotationLag", BOOL, "true")
    rot_speed = arm_set(g, "CameraRotationLagSpeed", FLOAT, src=(g.var_get("ChaseRotationLagSpeed", FLOAT), "ChaseRotationLagSpeed"))
    g.exec(notify, base, lag, lag_speed, rot_lag, rot_speed)
    # Phase 7 Task 11 (spec §5.4): the engine loop of this class; SetSound restarts a playing component (auto-activation
    # already started the template's sound), Play starts it when nothing was playing
    engine = audio_call(g, "EngineAudio", "SetSound", inputs=[obj_pin("NewSound", SOUND_BASE)])
    g.link(g.var_get("EngineSound", OBJECT, cls_ref(SOUND_BASE)), "EngineSound", engine, "NewSound")
    g.exec(rot_speed, engine)
    bplay = g.branch()
    g.note(bplay, "the engine loop playing already?")
    g.link(audio_call(g, "EngineAudio", "IsPlaying", outputs=[Pin("ReturnValue", BOOL, "out")], pure=True), "ReturnValue", bplay, "Condition")
    g.exec(engine, bplay)
    start = audio_call(g, "EngineAudio", "Play", inputs=[Pin("StartTime", FLOAT, default="0.0")])
    g.link(bplay, "else", start, "execute")
    paint = g.call_self("ApplyPaint")  # Phase 7 Task 13: the paint goes on the Body
    g.link(bplay, "then", paint, "execute")
    g.link(start, "then", paint, "execute")
    # Phase 7 Task 16 (spec §6.1, §7.2): the gun's shots are seen to leave from the roof weapon (its Muzzle socket when it shows one)
    origin = g.var_set_on(gen(BPC_WEAPON), "VisualOrigin", OBJECT, sub_object=cls_ref(SCENE_COMP))
    g.link(g.var_get("Weapon", OBJECT, cls_ref(gen(BPC_WEAPON))), "Weapon", origin, "self")
    g.link(*look_comp(g, "RoofWeapon"), origin, "VisualOrigin")
    g.exec(paint, origin)
    # Phase 7 Task 17 (spec §7.5): the shield bubble's dynamic material (a blocked hit flashes its Glow) and its own glow
    bubble = g.call_on(PRIMITIVE, "CreateDynamicMaterialInstance", inputs=[Pin("ElementIndex", INT, default="0"),
                                                                          obj_pin("SourceMaterial", MATERIAL_INTERFACE),
                                                                          Pin("OptionalName", NAME, default="None")],
                       outputs=[obj_pin("ReturnValue", MID, "out")])
    g.link(*look_comp(g, "ShieldBubble"), bubble, "self")
    keep_mid = g.var_set("ShieldMID", OBJECT, sub_object=cls_ref(MID))
    g.link(bubble, "ReturnValue", keep_mid, "ShieldMID")
    own = g.call_on(MID, "K2_GetScalarParameterValue", inputs=[Pin("ParameterName", NAME, default="Glow")], outputs=[Pin("ReturnValue", FLOAT, "out")])
    g.link(bubble, "ReturnValue", own, "self")
    keep_glow = g.var_set("ShieldBaseGlow", FLOAT)
    g.link(own, "ReturnValue", keep_glow, "ShieldBaseGlow")
    g.exec(origin, bubble, keep_mid, own, keep_glow)

    g.section("Tick: drive overrides, the arcade layer, item effects, the chase camera, then the engine and skid sounds")
    tick = g.tick(col=0, row=2)
    part = g.call_parent(gen(SEDAN), "ReceiveTick", [Pin("DeltaSeconds", FLOAT)], col=1, row=2)
    g.link(tick, "DeltaSeconds", part, "DeltaSeconds")
    ov = g.call_self("TickDriveOverrides", inputs=[Pin("DeltaSeconds", FLOAT)], col=2, row=2)
    g.link(tick, "DeltaSeconds", ov, "DeltaSeconds")
    arcade = g.call_self("TickArcade", inputs=[Pin("DeltaSeconds", FLOAT)])
    g.link(tick, "DeltaSeconds", arcade, "DeltaSeconds")
    fx = g.call_self("TickEffects", inputs=[Pin("DeltaSeconds", FLOAT)], col=3, row=2)
    g.link(tick, "DeltaSeconds", fx, "DeltaSeconds")
    camera = g.call_self("TickCamera", inputs=[Pin("DeltaSeconds", FLOAT)])
    g.link(tick, "DeltaSeconds", camera, "DeltaSeconds")
    sound = g.call_self("TickAudio", inputs=[Pin("DeltaSeconds", FLOAT)])
    g.link(tick, "DeltaSeconds", sound, "DeltaSeconds")
    g.exec(tick, part, ov, arcade, fx, camera, sound)

    g.section("Crash: a hard hit plays the crash sound at the contact and shakes the driver's view (spec §5.4)")
    hit = g.component_event("Mesh", "OnComponentHit", PRIMITIVE,
                            [obj_pin("HitComponent", PRIMITIVE), obj_pin("OtherActor", ACTOR), obj_pin("OtherComp", PRIMITIVE),
                             struct_pin("NormalImpulse", VECTOR), struct_pin("Hit", HIT_RESULT)],
                            "ComponentHitSignature__DelegateSignature")
    contact = g.call_static(GAMEPLAY, "BreakHitResult", inputs=[struct_pin("Hit", HIT_RESULT)],
                            outputs=[struct_pin("ImpactPoint", VECTOR, "out")], pure=True)
    g.link(hit, "Hit", contact, "Hit")
    crash = g.call_self("HandleCrashHit", inputs=[struct_pin("NormalImpulse", VECTOR), struct_pin("Location", VECTOR)],
                        outputs=[Pin("ReturnValue", BOOL, "out")])
    g.link(hit, "NormalImpulse", crash, "NormalImpulse")
    g.link(contact, "ImpactPoint", crash, "Location")
    g.exec(hit, crash)

    g.section("Handbrake: held state for the drift rules (replaces the template's binding, so it sets the input too)")
    hba = g.input_action("Handbrake")
    for pin, value in (("Pressed", "true"), ("Released", "false")):
        held = g.var_set("bHandbrakeHeld", BOOL, default=value)
        g.link(hba, pin, held, "execute")
        g.exec(held, set_handbrake(g, value))

    g.section("Point damage: route by hit bone (tire or body)")
    pd = g.event(ACTOR, "ReceivePointDamage",
                 [Pin("Damage", FLOAT), obj_pin("DamageType", "/Script/Engine.DamageType"), struct_pin("HitLocation", VECTOR),
                  struct_pin("HitNormal", VECTOR), obj_pin("HitComponent", PRIMITIVE), Pin("BoneName", NAME),
                  struct_pin("ShotFromDirection", VECTOR), obj_pin("InstigatedBy", CONTROLLER), obj_pin("DamageCauser", ACTOR),
                  struct_pin("HitInfo", HIT_RESULT)], col=0, row=3)
    find = g.call_self("FindTireIndexForHit", inputs=[Pin("BoneName", NAME), struct_pin("ImpactPoint", VECTOR)],
                       outputs=[Pin("Index", INT, "out")], col=1, row=3)
    g.link(pd, "BoneName", find, "BoneName")
    g.link(pd, "HitLocation", find, "ImpactPoint")
    take = g.call_self("TakeDamageInternal", inputs=[Pin("Damage", FLOAT), Pin("TireIndex", INT), obj_pin("Instigator", CONTROLLER)], col=2, row=3)
    g.link(pd, "Damage", take, "Damage")
    g.link(find, "Index", take, "TireIndex")
    g.link(pd, "InstigatedBy", take, "Instigator")
    flag = g.var_set("bPointDamageHandled", BOOL, default="true", col=3, row=3)
    g.exec(pd, find, take, flag)

    g.section("Any damage: the body, unless point damage already handled it")
    ad = g.event(ACTOR, "ReceiveAnyDamage",
                 [Pin("Damage", FLOAT), obj_pin("DamageType", "/Script/Engine.DamageType"), obj_pin("InstigatedBy", CONTROLLER),
                  obj_pin("DamageCauser", ACTOR)], col=0, row=4)
    handled = g.var_get("bPointDamageHandled", BOOL, col=1, row=5)
    b = g.branch(col=1, row=4)
    g.link(handled, "bPointDamageHandled", b, "Condition")
    g.exec(ad, b)
    reset = g.var_set("bPointDamageHandled", BOOL, default="false", col=2, row=5)
    g.link(b, "then", reset, "execute")
    take2 = g.call_self("TakeDamageInternal", inputs=[Pin("Damage", FLOAT), Pin("TireIndex", INT, default="-1"), obj_pin("Instigator", CONTROLLER)], col=2, row=4)
    g.link(ad, "Damage", take2, "Damage")
    g.link(ad, "InstigatedBy", take2, "Instigator")
    g.link(b, "else", take2, "execute")

    g.section("Interact: get out")
    ia = g.input_action("Interact", col=0, row=6)
    ex = g.call_self("ExitVehicle", outputs=[Pin("ReturnValue", BOOL, "out")], col=1, row=6)
    g.link(ia, "Pressed", ex, "execute")
    g.section("Use item: the selected item")
    ui = g.input_action("UseItem", col=0, row=7)
    use = g.call_self("UseSelectedItem", outputs=[Pin("ReturnValue", BOOL, "out")], col=1, row=7)
    g.link(ui, "Pressed", use, "execute")
    g.section("Next item: cycle the inventory")
    ni = g.input_action("NextItem", col=0, row=8)
    cy = g.call_self("CycleItem", col=1, row=8)
    g.link(ni, "Pressed", cy, "execute")
    g.section("Reset: back on the wheels where the car stands (spec §5.2)")
    ra = g.input_action("ResetCar")
    rs = g.call_self("ResetCar", outputs=[Pin("ReturnValue", BOOL, "out")])
    g.link(ra, "Pressed", rs, "execute")
    g.section("Look back: the rear view while held (spec §5.3)")
    la = g.input_action("LookBack")
    for pin, value in (("Pressed", "true"), ("Released", "false")):
        lb = g.call_self("SetLookBack", inputs=[Pin("bOn", BOOL, default=value)])
        g.link(la, pin, lb, "execute")
    return bp


def build_children() -> list:
    """BRUTE and VIPER (spec 2026-10-30 phase 5 §3): children of BP_DFVehicle that only change class defaults, from the
    VEHICLES catalogue in df.py; the mass override lands on the inherited VehicleMovement component."""
    out = []
    for row in VEHICLES:
        if row.asset == BP_VEHICLE:
            continue
        child = Blueprint(row.asset, parent=BP_VEHICLE, description="%s: %s" % (row.name, row.description))
        child.default("MaxHealth", float(row.max_health))
        child.default("Health", float(row.max_health))
        child.default("VehicleName", row.name)
        child.default("ThrottleScale", float(row.throttle_scale))
        child.default("TopSpeedKPH", float(row.top_speed))
        child.default("SteerAtSpeed", float(row.steer_at_speed))
        child.default("GripAssist", float(row.grip_assist))
        child.default("DownforceG", float(row.downforce_g))
        child.default("BoostDuration", float(row.boost_duration))
        child.default("BoostKickSpeed", float(row.boost_kick))
        # a state variable's default is not inherited by the runner (only the tunables are): "never reset" must hold from
        # game time 0, or the first ResetCooldown seconds of a race would refuse a reset
        child.default("LastResetTime", -1000.0)
        child.default("LastCrashTime", -1000.0)  # Task 11: the same for the crash cooldown
        child.default("EngineSound", art_sound(row.engine_sound))
        # Phase 7 Task 13 (spec §6.1): the class's paint, body and light bar; the hidden Mesh set on the child's own class
        # defaults too (an inherited native component's override, like the mass below)
        child.default("PaintMaterial", row.paint)
        child.default("BodyMesh", art_mesh(row.body))
        child.default("bHasLightBar", row.light_bar)
        child.component_default("Mesh", "visible", False)
        child.component_default("Mesh", "visibility_based_anim_tick_option", TICK_REFRESH_BONES)
        if row.mass_factor:
            child.component_default("VehicleMovement", "mass", SEDAN_MASS * row.mass_factor)
        out.append(child)
    return out


def build_all() -> list:
    return [build()] + build_children()


if __name__ == "__main__":
    for b in build_all():
        print(b.write(OUT))
