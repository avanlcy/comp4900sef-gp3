"""BP_DFCharacter (plan Task 4): child of the Third Person template character.

Interact (enter vehicle), fire, health, death/revive, stowed state. Movement, camera and jump come from the parent.
Phase 7 Task 14 (spec §6.2): the mannequin in navy and grey, with a helmet, a vest and a rifle on its bones; the rifle is
where the weapon's shots are seen to start (Weapon.VisualOrigin).
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from df import (ACTOR, BOOL, BP_CHARACTER, BP_EXPLOSIVE_DAMAGE, BP_GM, BP_VEHICLE, BPC_WEAPON, CHAR_MOVE, CONTROLLER,  # noqa: E402
                FLOAT, HIT_RESULT, MATH, OBJECT, OUT, PAWN, PRIMITIVE, SCENE_COMP, SPHERE_COMP, TPC, VECTOR, Blueprint, Pin,
                and_bool, as_pin, cast_to, cls_ref, compare, gen, get_game_mode, is_valid, math2, not_bool, obj_pin,
                obj_spec, or_bool, struct_pin)
from df import BP_SHAKE_LIGHT, CAMERA_SHAKE_BASE, CLASS, PLAYER_CONTROLLER, start_camera_shake  # noqa: E402  (Phase 7 Task 10)
from df import (CHARACTER_GEAR, MI_MANNEQUIN_BODY, MI_MANNEQUIN_TRIM, NAME, NO_COLLISION, SKEL_MESH_COMP,  # noqa: E402  (Task 14)
                STATIC_MESH_COMP, art_mesh, native_enum_pin)
from df import SW_RIFLE, weapon_look  # noqa: E402  (Task 16)

CC, VC, GMC, WC = gen(BP_CHARACTER), gen(BP_VEHICLE), gen(BP_GM), gen(BPC_WEAPON)
CAMERA = "/Script/Engine.CameraComponent"
ATTACHMENT_RULE = "/Script/Engine.EAttachmentRule"
# Phase 7 Task 14 (spec §6.2): each gear part's transform relative to its bone (location cm, rotation pitch / yaw / roll),
# measured in the editor on SK_Mannequin. Helmet and vest: their meshes' frame (X forward, Y right, Z up) upright at the
# bone in the reference pose, the pose they were fitted to (an SCS component cannot be parented to the inherited Mesh, so
# the construction script attaches each one keeping these offsets). Rifle: its hold point in the right fist of the idle pose
# (the knuckles' centre, 2.5 cm towards the palm and 2 cm towards the wrist), barrel forward, pitched down 10 degrees.
GEAR_MOUNTS = {
    "Helmet": ((0.0, 0.0, 0.0), (0.0, 91.32, -90.0)),
    "Vest": ((0.0, 0.0, 0.0), (0.0, 99.48, -90.0)),
    "Rifle": ((-9.49, 4.27, -1.49), (38.30, -124.42, 68.68)),
}


def build() -> Blueprint:
    bp = Blueprint(BP_CHARACTER, parent=TPC, description="The on-foot player: enter cars, fire, health, death and revive; movement and camera come from the Third Person template.")
    bp.component("InteractionSphere", SPHERE_COMP, sphere_radius=300.0)
    # bDebugTrace off as on the car (Phase 7, spec §6.2): the component template keeps its own value, whatever the weapon's default;
    # Phase 7 Task 16 (spec §7.2): the rifle's shot sound and the shot effects, set on the template for the same reason
    bp.component("Weapon", WC, bDebugTrace=False, **weapon_look(SW_RIFLE))
    # Phase 7 Task 14 (spec §6.2): the mannequin's slots (0 body, 1 trim), and the gear; it never collides, so it adds no
    # physics state to the character
    bp.component_default("Mesh", "override_materials", [MI_MANNEQUIN_BODY, MI_MANNEQUIN_TRIM])
    for name, asset, _ in CHARACTER_GEAR:
        (lx, ly, lz), (pitch, yaw, roll) = GEAR_MOUNTS[name]
        bp.component(name, STATIC_MESH_COMP, static_mesh=art_mesh(asset), relative_location={"vector": [lx, ly, lz]},
                     relative_rotation={"rotator": {"pitch": pitch, "yaw": yaw, "roll": roll}}, **NO_COLLISION)
    H = "Dead Fire|Health"
    bp.variable("MaxHealth", "float", "100", H, editable=True)
    bp.variable("Health", "float", "100", H)
    bp.variable("CurrentVehicle", obj_spec(BP_VEHICLE), "", "Dead Fire|State")
    bp.variable("bIsStowed", "bool", "false", "Dead Fire|State")
    bp.variable("bIsDead", "bool", "false", "Dead Fire|State")
    bp.variable("OwningController", "object:" + CONTROLLER, "", "Dead Fire|State")
    # Phase 7 Task 10 (spec §5.3): on foot nothing changes but the camera shake on hits taken
    bp.variable("HitShake", "class:" + CAMERA_SHAKE_BASE, "", "Dead Fire|Camera", editable=True)
    bp.default("HitShake", "class:" + BP_SHAKE_LIGHT)
    bp.dispatcher("OnCharacterDamaged", ["Damage:float"])
    bp.dispatcher("OnCharacterDied", [])
    bp.dispatcher("OnCharacterRevived", [])
    bp.dispatcher("OnEnteredVehicle", ["Vehicle:" + obj_spec(BP_VEHICLE)])
    bp.dispatcher("OnExitedVehicle", ["Vehicle:" + obj_spec(BP_VEHICLE)])

    g = bp.function("IsInVehicle", doc="Riding in a car.", outputs=["ReturnValue:bool"], pure=True)
    cv = g.var_get("CurrentVehicle", OBJECT, cls_ref(VC))
    v = is_valid(g)
    g.link(cv, "CurrentVehicle", v, "Object")
    g.link_result(v, "ReturnValue", "ReturnValue")
    g.link_entry("then", "result", "execute")

    g = bp.function("IsDead", doc="Health reached 0.", outputs=["ReturnValue:bool"], pure=True)
    d = g.var_get("bIsDead", BOOL)
    g.link_result(d, "bIsDead", "ReturnValue")
    g.link_entry("then", "result", "execute")

    # FindNearestEnterableVehicle: nearest overlapping BP_DFVehicle that CanBeEntered
    g = bp.function("FindNearestEnterableVehicle", doc="The nearest overlapping car that can be entered.", outputs=["ReturnValue:" + obj_spec(BP_VEHICLE)],
                    locals=["Best:" + obj_spec(BP_VEHICLE), "BestDist:float=1000000000"])
    sphere = g.var_get("InteractionSphere", OBJECT, cls_ref(SPHERE_COMP))
    ov = g.call_on(PRIMITIVE, "GetOverlappingActors",
                   inputs=[Pin("ClassFilter", "class", sub_object=cls_ref(ACTOR), default_object=VC)],
                   outputs=[Pin("OverlappingActors", OBJECT, "out", cls_ref(ACTOR), container="Array")], pure=True)
    g.link(sphere, "InteractionSphere", ov, "self")
    loop = g.for_each(obj_pin("e", ACTOR))
    g.link(ov, "OverlappingActors", loop, "Array")
    g.link_entry("then", loop, "Exec")
    cast = cast_to(g, BP_VEHICLE)
    g.link(loop, "Array Element", cast, "Object")
    g.link(loop, "LoopBody", cast, "execute")
    can = g.call_on(VC, "CanBeEntered", outputs=[Pin("ReturnValue", BOOL, "out")], pure=True)
    g.link(cast, as_pin(BP_VEHICLE), can, "self")
    b = g.branch()
    g.link(can, "ReturnValue", b, "Condition")
    g.link(cast, "then", b, "execute")
    vloc = g.call_on(ACTOR, "K2_GetActorLocation", outputs=[struct_pin("ReturnValue", VECTOR, "out")], pure=True)
    g.link(cast, as_pin(BP_VEHICLE), vloc, "self")
    mloc = g.call_self_native(ACTOR, "K2_GetActorLocation", outputs=[struct_pin("ReturnValue", VECTOR, "out")], pure=True)
    dist = g.call_static(MATH, "Vector_Distance", inputs=[struct_pin("V1", VECTOR), struct_pin("V2", VECTOR)],
                         outputs=[Pin("ReturnValue", FLOAT, "out")], pure=True)
    g.link(vloc, "ReturnValue", dist, "V1")
    g.link(mloc, "ReturnValue", dist, "V2")
    bd = g.local_get("BestDist", FLOAT)
    lt = compare(g, "Less_FloatFloat", FLOAT)
    g.link(dist, "ReturnValue", lt, "A")
    g.link(bd, "BestDist", lt, "B")
    b2 = g.branch()
    g.link(lt, "ReturnValue", b2, "Condition")
    g.link(b, "then", b2, "execute")
    sd = g.local_set("BestDist", FLOAT)
    g.link(dist, "ReturnValue", sd, "BestDist")
    sb = g.local_set("Best", OBJECT, sub_object=cls_ref(VC))
    g.link(cast, as_pin(BP_VEHICLE), sb, "Best")
    g.link(b2, "then", sd, "execute")
    g.exec(sd, sb)
    best = g.local_get("Best", OBJECT, cls_ref(VC))
    g.link_result(best, "Best", "ReturnValue")
    g.link_extra(loop, "Completed", "result", "execute")

    # TryEnterVehicle(Vehicle) -> bool
    g = bp.function("TryEnterVehicle", doc="Enters the given car, or the nearest enterable one.", inputs=["Vehicle:" + obj_spec(BP_VEHICLE)], outputs=["ReturnValue:bool"],
                    locals=["Target:" + obj_spec(BP_VEHICLE)])
    dead = g.var_get("bIsDead", BOOL)
    b = g.branch()
    g.link(dead, "bIsDead", b, "Condition")
    g.link_entry("then", b, "execute")
    r_dead = g.function_result([Pin("ReturnValue", BOOL, default="false")])
    g.link(b, "then", r_dead, "execute")
    st = g.local_set("Target", OBJECT, sub_object=cls_ref(VC))
    g.link_entry("Vehicle", st, "Target")
    g.link(b, "else", st, "execute")
    v = is_valid(g)
    g.link(st, "Output_Get", v, "Object")
    bv = g.branch()
    g.link(v, "ReturnValue", bv, "Condition")
    g.exec(st, bv)
    find = g.call_self("FindNearestEnterableVehicle", outputs=[obj_pin("ReturnValue", VC, "out")])
    g.link(bv, "else", find, "execute")
    st2 = g.local_set("Target", OBJECT, sub_object=cls_ref(VC))
    g.link(find, "ReturnValue", st2, "Target")
    g.exec(find, st2)
    t = g.local_get("Target", OBJECT, cls_ref(VC))
    v2 = is_valid(g)
    g.link(t, "Target", v2, "Object")
    bv2 = g.branch()
    g.link(v2, "ReturnValue", bv2, "Condition")
    g.link(bv, "then", bv2, "execute")
    g.exec(st2, bv2)
    r_none = g.function_result([Pin("ReturnValue", BOOL, default="false")])
    g.link(bv2, "else", r_none, "execute")
    enter = g.call_on(VC, "EnterVehicle", inputs=[obj_pin("Character", CC)], outputs=[Pin("ReturnValue", BOOL, "out")])
    t2 = g.local_get("Target", OBJECT, cls_ref(VC))
    g.link(t2, "Target", enter, "self")
    me = g.self_node()
    g.link(me, "self", enter, "Character")
    g.link(bv2, "then", enter, "execute")
    r = g.function_result([Pin("ReturnValue", BOOL)])
    g.link(enter, "ReturnValue", r, "ReturnValue")
    g.exec(enter, r)

    # SetStowed(bStowed, AttachTo)
    g = bp.function("SetStowed", doc="Hides and attaches the character inside a car, or lets it out again.", inputs=["bStowed:bool", "AttachTo:object:" + ACTOR])
    b = g.branch()
    g.link_entry("bStowed", b, "Condition")
    g.link_entry("then", b, "execute")
    # stow
    hide = g.call_self_native(ACTOR, "SetActorHiddenInGame", inputs=[Pin("bNewHidden", BOOL, default="true")])
    nocol = g.call_self_native(ACTOR, "SetActorEnableCollision", inputs=[Pin("bNewActorEnableCollision", BOOL, default="false")])
    cm = g.var_get("CharacterMovement", OBJECT, cls_ref(CHAR_MOVE))
    stop = g.call_on(CHAR_MOVE, "DisableMovement")
    g.link(cm, "CharacterMovement", stop, "self")
    attach = g.call_self_native(ACTOR, "K2_AttachToActor",
                                inputs=[obj_pin("ParentActor", ACTOR), Pin("SocketName", "name", default="None"),
                                        Pin("LocationRule", "byte", default="SnapToTarget"), Pin("RotationRule", "byte", default="SnapToTarget"),
                                        Pin("ScaleRule", "byte", default="KeepWorld"), Pin("bWeldSimulatedBodies", BOOL, default="true")])
    g.link_entry("AttachTo", attach, "ParentActor")
    notick = g.call_self_native(ACTOR, "SetActorTickEnabled", inputs=[Pin("bEnabled", BOOL, default="false")])
    flag = g.var_set("bIsStowed", BOOL, default="true")
    g.link(b, "then", hide, "execute")
    g.exec(hide, nocol, stop, attach, notick, flag)
    # un-stow
    detach = g.call_self_native(ACTOR, "K2_DetachFromActor",
                                inputs=[Pin("LocationRule", "byte", default="KeepWorld"), Pin("RotationRule", "byte", default="KeepWorld"),
                                        Pin("ScaleRule", "byte", default="KeepWorld")])
    show = g.call_self_native(ACTOR, "SetActorHiddenInGame", inputs=[Pin("bNewHidden", BOOL, default="false")])
    col = g.call_self_native(ACTOR, "SetActorEnableCollision", inputs=[Pin("bNewActorEnableCollision", BOOL, default="true")])
    cm2 = g.var_get("CharacterMovement", OBJECT, cls_ref(CHAR_MOVE))
    walk = g.call_on(CHAR_MOVE, "SetMovementMode", inputs=[Pin("NewMovementMode", "byte", default="MOVE_Walking"), Pin("NewCustomMode", "byte", default="0")])
    g.link(cm2, "CharacterMovement", walk, "self")
    tick = g.call_self_native(ACTOR, "SetActorTickEnabled", inputs=[Pin("bEnabled", BOOL, default="true")])
    flag2 = g.var_set("bIsStowed", BOOL, default="false")
    g.link(b, "else", detach, "execute")
    g.exec(detach, show, col, walk, tick, flag2)

    # Fire -> bool
    g = bp.function("Fire", doc="Fires the hitscan weapon from the camera, credited to the controller.", outputs=["ReturnValue:bool"])
    dead = g.var_get("bIsDead", BOOL)
    stowed = g.var_get("bIsStowed", BOOL)
    either = or_bool(g)
    g.link(dead, "bIsDead", either, "A")
    g.link(stowed, "bIsStowed", either, "B")
    b = g.branch()
    g.link(either, "ReturnValue", b, "Condition")
    g.link_entry("then", b, "execute")
    r_no = g.function_result([Pin("ReturnValue", BOOL, default="false")])
    g.link(b, "then", r_no, "execute")
    cam = g.var_get("FollowCamera", OBJECT, cls_ref(CAMERA))
    loc = g.call_on(SCENE_COMP, "K2_GetComponentLocation", outputs=[struct_pin("ReturnValue", VECTOR, "out")], pure=True)
    g.link(cam, "FollowCamera", loc, "self")
    cam2 = g.var_get("FollowCamera", OBJECT, cls_ref(CAMERA))
    fwd = g.call_on(SCENE_COMP, "GetForwardVector", outputs=[struct_pin("ReturnValue", VECTOR, "out")], pure=True)
    g.link(cam2, "FollowCamera", fwd, "self")
    wp = g.var_get("Weapon", OBJECT, cls_ref(WC))
    fire = g.call_on(WC, "Fire", inputs=[struct_pin("Origin", VECTOR), struct_pin("Direction", VECTOR), obj_pin("Instigator", CONTROLLER)],
                     outputs=[Pin("bHit", BOOL, "out"), struct_pin("Hit", HIT_RESULT, "out")])
    g.link(wp, "Weapon", fire, "self")
    g.link(loc, "ReturnValue", fire, "Origin")
    g.link(fwd, "ReturnValue", fire, "Direction")
    my_ctrl = g.call_self_native(PAWN, "GetController", outputs=[obj_pin("ReturnValue", CONTROLLER, "out")], pure=True)
    g.link(my_ctrl, "ReturnValue", fire, "Instigator")
    g.link(b, "else", fire, "execute")
    r = g.function_result([Pin("ReturnValue", BOOL)])
    g.link(fire, "bHit", r, "ReturnValue")
    g.exec(fire, r)

    # Revive
    g = bp.function("Revive", doc="Full health, alive and walking again.")
    mx = g.var_get("MaxHealth", FLOAT)
    sh = g.var_set("Health", FLOAT)
    g.link(mx, "MaxHealth", sh, "Health")
    g.link_entry("then", sh, "execute")
    alive = g.var_set("bIsDead", BOOL, default="false")
    cm = g.var_get("CharacterMovement", OBJECT, cls_ref(CHAR_MOVE))
    walk = g.call_on(CHAR_MOVE, "SetMovementMode", inputs=[Pin("NewMovementMode", "byte", default="MOVE_Walking"), Pin("NewCustomMode", "byte", default="0")])
    g.link(cm, "CharacterMovement", walk, "self")
    fire = g.call_delegate("OnCharacterRevived")
    g.exec(sh, alive, walk, fire)

    # Construction script (Phase 7 Task 14, spec §6.2): each gear part onto its bone of the inherited Mesh, keeping the
    # part's relative transform (GEAR_MOUNTS) as its offset from the bone
    g = bp.construction_script()
    prev = g.call_parent(gen(TPC), "UserConstructionScript")
    g.link_entry("then", prev, "execute")
    for name, _, bone in CHARACTER_GEAR:
        att = g.call_on(SCENE_COMP, "K2_AttachToComponent",
                        inputs=[obj_pin("Parent", SCENE_COMP), Pin("SocketName", NAME, default=bone),
                                native_enum_pin("LocationRule", ATTACHMENT_RULE, "KeepRelative"),
                                native_enum_pin("RotationRule", ATTACHMENT_RULE, "KeepRelative"),
                                native_enum_pin("ScaleRule", ATTACHMENT_RULE, "KeepRelative"),
                                Pin("bWeldSimulatedBodies", BOOL, default="false")],
                        outputs=[Pin("ReturnValue", BOOL, "out")])
        g.link(g.var_get(name, OBJECT, cls_ref(STATIC_MESH_COMP)), name, att, "self")
        g.link(g.var_get("Mesh", OBJECT, cls_ref(SKEL_MESH_COMP)), "Mesh", att, "Parent")
        g.exec(prev, att)
        prev = att

    # Event graph
    g = bp.event_graph()
    g.section("Begin Play: the rifle is where the weapon's shots are seen to start (Phase 7 Task 14; the weapon draws them from its Muzzle)")
    bpl = g.begin_play(col=0, row=10)
    par = g.call_parent(gen(TPC), "ReceiveBeginPlay", col=1, row=10)
    origin = g.var_set_on(WC, "VisualOrigin", OBJECT, sub_object=cls_ref(SCENE_COMP), col=2, row=10)
    g.link(g.var_get("Weapon", OBJECT, cls_ref(WC), col=2, row=11), "Weapon", origin, "self")
    g.link(g.var_get("Rifle", OBJECT, cls_ref(STATIC_MESH_COMP), col=1, row=11), "Rifle", origin, "VisualOrigin")
    g.exec(bpl, par, origin)
    g.section("Any damage: lose health (explosions excepted); at 0 die and tell the GameMode")
    ad = g.event(ACTOR, "ReceiveAnyDamage",
                 [Pin("Damage", FLOAT), obj_pin("DamageType", "/Script/Engine.DamageType"), obj_pin("InstigatedBy", CONTROLLER),
                  obj_pin("DamageCauser", ACTOR)], col=0, row=1)
    dead = g.var_get("bIsDead", BOOL, col=0, row=2)
    stowed = g.var_get("bIsStowed", BOOL, col=0, row=3)
    either = or_bool(g, col=1, row=2)
    g.link(dead, "bIsDead", either, "A")
    g.link(stowed, "bIsStowed", either, "B")
    b = g.branch(col=1, row=1)
    g.link(either, "ReturnValue", b, "Condition")
    # Phase 3 (spec §5): explosive damage never hurts the on-foot character; leaving the car is not a death trap
    ex = cast_to(g, BP_EXPLOSIVE_DAMAGE, col=1, row=0)
    g.link(ad, "DamageType", ex, "Object")
    g.exec(ad, ex)
    g.link(ex, "CastFailed", b, "execute")
    h = g.var_get("Health", FLOAT, col=2, row=2)
    sub = math2(g, "Subtract_FloatFloat", FLOAT, col=3, row=2)
    g.link(h, "Health", sub, "A")
    g.link(ad, "Damage", sub, "B")
    clamp = g.call_static(MATH, "FMax", inputs=[Pin("A", FLOAT), Pin("B", FLOAT, default="0.0")],
                          outputs=[Pin("ReturnValue", FLOAT, "out")], pure=True, col=4, row=2)
    g.link(sub, "ReturnValue", clamp, "A")
    seth = g.var_set("Health", FLOAT, col=2, row=1)
    g.link(clamp, "ReturnValue", seth, "Health")
    g.link(b, "else", seth, "execute")
    f1 = g.call_delegate("OnCharacterDamaged", [Pin("Damage", FLOAT)], col=3, row=1)
    g.link(ad, "Damage", f1, "Damage")
    g.exec(seth, f1)
    # Phase 7 Task 10 (spec §5.3): a hit taken shakes the player's view (an AI never controls the character)
    my_ctrl = g.call_self_native(PAWN, "GetController", outputs=[obj_pin("ReturnValue", CONTROLLER, "out")], pure=True)
    to_pc = g.cast(PLAYER_CONTROLLER)
    g.note(to_pc, "a player's character?")
    g.link(my_ctrl, "ReturnValue", to_pc, "Object")
    g.exec(f1, to_pc)
    shake = start_camera_shake(g, (to_pc, as_pin(PLAYER_CONTROLLER)), (g.var_get("HitShake", CLASS, cls_ref(CAMERA_SHAKE_BASE)), "HitShake"))
    g.link(to_pc, "then", shake, "execute")
    le = compare(g, "LessEqual_FloatFloat", FLOAT, b="0.0", col=4, row=3)
    g.link(seth, "Output_Get", le, "A")
    bd = g.branch(col=4, row=1)
    g.link(le, "ReturnValue", bd, "Condition")
    g.exec(shake, bd)
    g.link(to_pc, "CastFailed", bd, "execute")
    mark = g.var_set("bIsDead", BOOL, default="true", col=5, row=1)
    g.link(bd, "then", mark, "execute")
    cm = g.var_get("CharacterMovement", OBJECT, cls_ref(CHAR_MOVE), col=5, row=2)
    stop = g.call_on(CHAR_MOVE, "DisableMovement", col=6, row=1)
    g.link(cm, "CharacterMovement", stop, "self")
    g.exec(mark, stop)
    f2 = g.call_delegate("OnCharacterDied", col=7, row=1)
    g.exec(stop, f2)
    gm = get_game_mode(g, col=7, row=2)
    cast = cast_to(g, BP_GM, col=8, row=1)
    g.link(gm, "ReturnValue", cast, "Object")
    g.exec(f2, cast)
    notify = g.call_on(GMC, "NotifyCharacterDied", inputs=[obj_pin("Character", CC)], col=9, row=1)
    g.link(cast, as_pin(BP_GM), notify, "self")
    me = g.self_node(col=8, row=2)
    g.link(me, "self", notify, "Character")
    g.link(cast, "then", notify, "execute")

    g.section("Interact: enter the nearest car")
    ia = g.input_action("Interact", col=0, row=5)
    enter = g.call_self("TryEnterVehicle", inputs=[obj_pin("Vehicle", VC)], outputs=[Pin("ReturnValue", BOOL, "out")], col=1, row=5)
    g.link(ia, "Pressed", enter, "execute")
    g.section("Fire: shoot from the camera")
    fa = g.input_action("Fire", col=0, row=6)
    fire = g.call_self("Fire", outputs=[Pin("ReturnValue", BOOL, "out")], col=1, row=6)
    g.link(fa, "Pressed", fire, "execute")
    # Phase 3: NextItem cycles the inventory on foot as well (spec §9)
    g.section("Next item: cycle the inventory on foot")
    ni = g.input_action("NextItem", col=0, row=7)
    gm2 = get_game_mode(g, col=0, row=8)
    cast2 = cast_to(g, BP_GM, col=1, row=7)
    g.link(gm2, "ReturnValue", cast2, "Object")
    g.link(ni, "Pressed", cast2, "execute")
    ctrl = g.call_self_native(PAWN, "GetController", outputs=[obj_pin("ReturnValue", CONTROLLER, "out")], pure=True, col=1, row=8)
    cy = g.call_on(GMC, "CycleItem", inputs=[obj_pin("C", CONTROLLER)], col=2, row=7)
    g.link(cast2, as_pin(BP_GM), cy, "self")
    g.link(ctrl, "ReturnValue", cy, "C")
    g.link(cast2, "then", cy, "execute")
    return bp


if __name__ == "__main__":
    print(build().write(OUT))
