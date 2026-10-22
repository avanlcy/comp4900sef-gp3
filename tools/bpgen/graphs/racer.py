"""BPC_DFRacer and BP_DFPlayerController (plan Task 5).

The racer component holds per-racer race state and lives on the controller, so it survives vehicle respawns and
lets the GameMode rank NPC racers against the player.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from df import (BP_CHARACTER, BP_CHECKPOINT, BP_PC, BP_VEHICLE, BPC_RACER, OBJECT, OUT, PAWN, PLAYER_CONTROLLER,  # noqa: E402
                Blueprint, as_pin, cast_to, cls_ref, gen, obj_pin, obj_spec)

VC = gen(BP_VEHICLE)


def build_racer() -> Blueprint:
    bp = Blueprint(BPC_RACER, parent="/Script/Engine.ActorComponent")
    R = "Dead Fire|Race"
    bp.variable("Score", "int", "0", R, editable=True)
    bp.variable("LapsCompleted", "int", "0", R, editable=True)
    bp.variable("Kills", "int", "0", R, editable=True)
    bp.variable("Deaths", "int", "0", R, editable=True)
    bp.variable("NextCheckpointIndex", "int", "1", R, editable=True)
    bp.variable("LastCheckpoint", obj_spec(BP_CHECKPOINT), "", R)
    bp.variable("LastCheckpointTime", "float", "-1", R)
    bp.variable("OffTrackSeconds", "float", "0", R)
    bp.variable("DistanceAlongTrack", "float", "0", R)
    bp.variable("RacerName", "text", "Player", R, editable=True)
    return bp


def build_controller() -> Blueprint:
    bp = Blueprint(BP_PC, parent=PLAYER_CONTROLLER)
    bp.component("Racer", gen(BPC_RACER))
    S = "Dead Fire|State"
    bp.variable("OnFootCharacter", obj_spec(BP_CHARACTER), "", S)
    bp.variable("CurrentVehicle", obj_spec(BP_VEHICLE), "", S)  # the possessed car, empty on foot (HUD)
    bp.variable("LastVehicle", obj_spec(BP_VEHICLE), "", S)  # the last car possessed, kept on foot (respawn)

    g = bp.function("SwitchToPawn", inputs=["NewPawn:object:" + PAWN])
    poss = g.call_self_native("/Script/Engine.Controller", "Possess", inputs=[obj_pin("InPawn", PAWN)])
    g.link_entry("NewPawn", poss, "InPawn")
    g.link_entry("then", poss, "execute")

    g = bp.event_graph()
    ev = g.event("/Script/Engine.Controller", "ReceivePossess", [obj_pin("PossessedPawn", PAWN)], col=0, row=0)
    cast = cast_to(g, BP_VEHICLE, col=1, row=0)
    g.link(ev, "PossessedPawn", cast, "Object")
    g.exec(ev, cast)
    set_cur = g.var_set("CurrentVehicle", OBJECT, sub_object=cls_ref(VC), col=2, row=0)
    g.link(cast, as_pin(BP_VEHICLE), set_cur, "CurrentVehicle")
    set_last = g.var_set("LastVehicle", OBJECT, sub_object=cls_ref(VC), col=3, row=0)
    g.link(cast, as_pin(BP_VEHICLE), set_last, "LastVehicle")
    g.exec(cast, set_cur, set_last)
    clear = g.var_set("CurrentVehicle", OBJECT, sub_object=cls_ref(VC), col=2, row=1)
    g.link(cast, "CastFailed", clear, "execute")
    return bp


def build():
    return [build_racer(), build_controller()]


if __name__ == "__main__":
    for b in build():
        print(b.write(OUT))
