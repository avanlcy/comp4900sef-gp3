"""BP_DFCheckpoint (plan Task 6): gate with a trigger across the road and two poles; reports vehicle crossings to
the GameMode, which owns the ordering rules. Index 0 is the start/finish line.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from df import (ACTOR, BOOL, BOX_COMP, BP_CHECKPOINT, BP_GM, BP_VEHICLE, CONTROLLER, FLOAT, HIT_RESULT, INT, MATH,  # noqa: E402
                OBJECT, OUT, PAWN, PRIMITIVE, SCENE_COMP, STATIC_MESH_COMP, TRANSFORM, VECTOR, Blueprint, Pin, as_pin,
                cast_to, cls_ref, gen, get_game_mode, is_valid, math2, obj_pin, struct_pin)

CPC, VC, GMC = gen(BP_CHECKPOINT), gen(BP_VEHICLE), gen(BP_GM)
POLE = "/Game/VehicleAdv/ArenaMesh/pole"


def build() -> Blueprint:
    bp = Blueprint(BP_CHECKPOINT, parent="/Script/Engine.Actor")
    bp.component("Trigger", BOX_COMP, **{"box_extent": {"vector": [100, 1400, 250]},
                                         "call:set_collision_profile_name": "Trigger",
                                         "generate_overlap_events": True})
    bp.component("LeftPole", STATIC_MESH_COMP, **{"static_mesh": POLE, "relative_location": {"vector": [0, -700, 0]},
                                                   "call:set_collision_profile_name": "NoCollision"})
    bp.component("RightPole", STATIC_MESH_COMP, **{"static_mesh": POLE, "relative_location": {"vector": [0, 700, 0]},
                                                    "call:set_collision_profile_name": "NoCollision"})
    C = "Dead Fire|Checkpoint"
    bp.variable("CheckpointIndex", "int", "0", C, editable=True)
    bp.variable("TriggerHalfExtent", "struct:" + VECTOR, "(X=100.000000,Y=1400.000000,Z=250.000000)", C, editable=True)
    bp.variable("PoleOffset", "float", "700", C, editable=True)
    bp.variable("RespawnHeightOffset", "float", "50", C, editable=True)

    # GetRespawnTransform: actor rotation, location raised by RespawnHeightOffset
    g = bp.function("GetRespawnTransform", outputs=["Transform:struct:" + TRANSFORM], pure=True)
    loc = g.call_self_native(ACTOR, "K2_GetActorLocation", outputs=[struct_pin("ReturnValue", VECTOR, "out")], pure=True)
    rot = g.call_self_native(ACTOR, "K2_GetActorRotation", outputs=[struct_pin("ReturnValue", "/Script/CoreUObject.Rotator", "out")], pure=True)
    h = g.var_get("RespawnHeightOffset", FLOAT)
    up = g.call_static(MATH, "MakeVector", inputs=[Pin("X", FLOAT, default="0.0"), Pin("Y", FLOAT, default="0.0"), Pin("Z", FLOAT)],
                       outputs=[struct_pin("ReturnValue", VECTOR, "out")], pure=True)
    g.link(h, "RespawnHeightOffset", up, "Z")
    raised = g.call_static(MATH, "Add_VectorVector", inputs=[struct_pin("A", VECTOR), struct_pin("B", VECTOR)],
                           outputs=[struct_pin("ReturnValue", VECTOR, "out")], pure=True)
    g.link(loc, "ReturnValue", raised, "A")
    g.link(up, "ReturnValue", raised, "B")
    t = g.call_static(MATH, "MakeTransform", inputs=[struct_pin("Location", VECTOR), struct_pin("Rotation", "/Script/CoreUObject.Rotator"),
                                                       struct_pin("Scale", VECTOR, default="1,1,1")],
                      outputs=[struct_pin("ReturnValue", TRANSFORM, "out")], pure=True)
    g.link(raised, "ReturnValue", t, "Location")
    g.link(rot, "ReturnValue", t, "Rotation")
    g.link_result(t, "ReturnValue", "Transform")
    g.link_entry("then", "result", "execute")

    # NotifyVehicle(Vehicle) -> bool: the racer is the driver, or the last driver of a parked car
    g = bp.function("NotifyVehicle", inputs=["Vehicle:object:" + VC], outputs=["ReturnValue:bool"])
    ctrl = g.call_on(PAWN, "GetController", outputs=[obj_pin("ReturnValue", CONTROLLER, "out")], pure=True)
    g.link_entry("Vehicle", ctrl, "self")
    last = g.var_get_on(VC, "LastDriver", OBJECT, cls_ref(CONTROLLER))
    g.link_entry("Vehicle", last, "self")
    valid = is_valid(g)
    g.link(ctrl, "ReturnValue", valid, "Object")
    pick = g.call_static(MATH, "SelectObject", inputs=[obj_pin("A", "/Script/CoreUObject.Object"), obj_pin("B", "/Script/CoreUObject.Object"), Pin("bSelectA", BOOL)],
                         outputs=[obj_pin("ReturnValue", "/Script/CoreUObject.Object", "out")], pure=True)
    g.link(ctrl, "ReturnValue", pick, "A")
    g.link(last, "LastDriver", pick, "B")
    g.link(valid, "ReturnValue", pick, "bSelectA")
    racer = g.cast("/Script/Engine.Controller")
    g.link(pick, "ReturnValue", racer, "Object")
    g.link_entry("then", racer, "execute")
    gm = get_game_mode(g)
    cast = cast_to(g, BP_GM)
    g.link(gm, "ReturnValue", cast, "Object")
    g.link(racer, "then", cast, "execute")
    r_no = g.function_result([Pin("ReturnValue", BOOL, default="false")])
    g.link(racer, "CastFailed", r_no, "execute")
    g.link(cast, "CastFailed", r_no, "execute")
    notify = g.call_on(GMC, "NotifyCheckpointReached", inputs=[obj_pin("Racer", CONTROLLER), obj_pin("Checkpoint", CPC)],
                       outputs=[Pin("ReturnValue", BOOL, "out")])
    g.link(cast, as_pin(BP_GM), notify, "self")
    g.link(racer, "AsController", notify, "Racer")
    me = g.self_node()
    g.link(me, "self", notify, "Checkpoint")
    g.link(cast, "then", notify, "execute")
    r = g.function_result([Pin("ReturnValue", BOOL)])
    g.link(notify, "ReturnValue", r, "ReturnValue")
    g.exec(notify, r)

    # Construction script: apply extent and pole offsets so edits in the level update the gate
    g = bp.construction_script()
    trig = g.var_get("Trigger", OBJECT, cls_ref(BOX_COMP))
    ext = g.var_get("TriggerHalfExtent", "struct", sub_object="ScriptStruct'\"%s\"'" % VECTOR)
    set_ext = g.call_on(BOX_COMP, "SetBoxExtent", inputs=[struct_pin("InBoxExtent", VECTOR), Pin("bUpdateOverlaps", BOOL, default="true")])
    g.link(trig, "Trigger", set_ext, "self")
    g.link(ext, "TriggerHalfExtent", set_ext, "InBoxExtent")
    g.link_entry("then", set_ext, "execute")
    prev = set_ext
    for comp, sign in (("LeftPole", -1.0), ("RightPole", 1.0)):
        po = g.var_get("PoleOffset", FLOAT)
        y = math2(g, "Multiply_FloatFloat", FLOAT, b="%f" % sign)
        g.link(po, "PoleOffset", y, "A")
        v = g.call_static(MATH, "MakeVector", inputs=[Pin("X", FLOAT, default="0.0"), Pin("Y", FLOAT), Pin("Z", FLOAT, default="0.0")],
                          outputs=[struct_pin("ReturnValue", VECTOR, "out")], pure=True)
        g.link(y, "ReturnValue", v, "Y")
        pole = g.var_get(comp, OBJECT, cls_ref(STATIC_MESH_COMP))
        setl = g.call_on(SCENE_COMP, "K2_SetRelativeLocation",
                         inputs=[struct_pin("NewLocation", VECTOR), Pin("bSweep", BOOL, default="false"), Pin("bTeleport", BOOL, default="false")],
                         outputs=[struct_pin("SweepHitResult", HIT_RESULT, "out")])
        g.link(pole, comp, setl, "self")
        g.link(v, "ReturnValue", setl, "NewLocation")
        g.exec(prev, setl)
        prev = setl

    g = bp.event_graph()
    bpl = g.begin_play(col=0, row=0)
    gm = get_game_mode(g, col=0, row=1)
    cast = cast_to(g, BP_GM, col=1, row=0)
    g.link(gm, "ReturnValue", cast, "Object")
    g.exec(bpl, cast)
    reg = g.call_on(GMC, "RegisterCheckpoint", inputs=[obj_pin("Checkpoint", CPC)], col=2, row=0)
    g.link(cast, as_pin(BP_GM), reg, "self")
    me = g.self_node(col=1, row=1)
    g.link(me, "self", reg, "Checkpoint")
    g.link(cast, "then", reg, "execute")

    ov = g.component_event("Trigger", "OnComponentBeginOverlap", PRIMITIVE,
                           [obj_pin("OverlappedComponent", PRIMITIVE), obj_pin("OtherActor", ACTOR), obj_pin("OtherComp", PRIMITIVE),
                            Pin("OtherBodyIndex", INT), Pin("bFromSweep", BOOL), struct_pin("SweepResult", HIT_RESULT)],
                           "ComponentBeginOverlapSignature__DelegateSignature", col=0, row=3)
    vc = cast_to(g, BP_VEHICLE, col=1, row=3)
    g.link(ov, "OtherActor", vc, "Object")
    g.exec(ov, vc)
    nv = g.call_self("NotifyVehicle", inputs=[obj_pin("Vehicle", VC)], outputs=[Pin("ReturnValue", BOOL, "out")], col=2, row=3)
    g.link(vc, as_pin(BP_VEHICLE), nv, "Vehicle")
    g.link(vc, "then", nv, "execute")
    return bp


if __name__ == "__main__":
    print(build().write(OUT))
