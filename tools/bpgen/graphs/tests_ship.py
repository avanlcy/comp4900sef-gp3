"""Phase 6 FT_DFShip_* tests (plan docs/superpowers/plans/2026-10-30-phase6-ship.md): the ship fixes (race end closes the
pause menu, the volume preview, dead racer entries, RecordResult without a save, a fresh save slot, the player's car class)
and the difficulty table. Same shape and world as tests_menu.py: the test GameMode points the GameInstance at the
DeadFireTest save slot, so no test touches a developer's real progress.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, ".."))
from bpgen import CLASS, cls_ref  # noqa: E402
from df import (BOOL, BP_GS, BP_VEHICLE, CONTROLLER, FLOAT, GAME_MODE_BASE, GAMEPLAY, INT, MATH, OBJECT, OUT, PAWN,  # noqa: E402
                STRING, SYS, Pin, gen)
from tests import T, race_context  # noqa: E402
from tests_menu import (GIC, GMC, SAVEC, WPAUSE, end_race, expect_record, fresh_progress, game_instance, gi_pure,  # noqa: E402
                        is_paused, str_equals, toggle_pause)
from tests_items import widgets  # noqa: E402
from tests_ai import AIC, ai_controllers, despawn_npcs, spawn_npcs  # noqa: E402

GSC, VC = gen(BP_GS), gen(BP_VEHICLE)
ARR = "KismetArrayLibrary"
OBJ = "/Script/CoreUObject.Object"


# ---- helpers ----
def racer_controllers(t: T, gm):
    """The GameMode's registered racer controllers (a reference: array nodes on it change the GameMode's own array)."""
    return t.get(GMC, "RacerControllers", OBJECT, gm, sub=cls_ref(CONTROLLER), container="Array")


def add_none_controller(t: T, gm):
    """Appends an empty entry to the racer list (a controller that died mid-frame looks like this); returns its index."""
    n = t.g.call_array(ARR, "Array_Add", Pin("e", OBJECT, sub_object=cls_ref(CONTROLLER)),
                       inputs=[Pin("NewItem", OBJECT, "in", cls_ref(CONTROLLER))], outputs=[Pin("ReturnValue", INT, "out")], pure=False)
    t.link(racer_controllers(t, gm), n, "TargetArray")
    t.step(n)
    return (n, "ReturnValue")


def remove_controller_at(t: T, gm, index_src):
    n = t.g.call_array(ARR, "Array_Remove", Pin("e", OBJECT, sub_object=cls_ref(CONTROLLER)), inputs=[Pin("IndexToRemove", INT)], pure=False)
    t.link(racer_controllers(t, gm), n, "TargetArray")
    t.link(index_src, n, "IndexToRemove")
    t.step(n)


def pause_widgets(t: T):
    return widgets(t, WPAUSE)


def set_save_none(t: T, gi):
    t.set(GIC, "Save", OBJECT, gi, sub=cls_ref(SAVEC))


def save_exists(t: T, slot):
    n = t.static(GAMEPLAY, "DoesSaveGameExist", inputs=[Pin("SlotName", STRING, default=slot), Pin("UserIndex", INT, default="0")],
                 outputs=[Pin("ReturnValue", BOOL, "out")])
    return (n, "ReturnValue")


def delete_slot(t: T, slot):
    t.static(GAMEPLAY, "DeleteGameInSlot", inputs=[Pin("SlotName", STRING, default=slot), Pin("UserIndex", INT, default="0")],
             outputs=[Pin("ReturnValue", BOOL, "out")])


def use_slot(t: T, gi, slot):
    t.call(GIC, "UseSaveSlot", gi, inputs=[Pin("SlotName", STRING, default=slot)])


def is_valid_class(t: T, cls_src):
    n = t.g.call_static(SYS, "IsValidClass", inputs=[Pin("Class", CLASS, sub_object=cls_ref(OBJ))],
                        outputs=[Pin("ReturnValue", BOOL, "out")], pure=True)
    t.link(cls_src, n, "Class")
    return (n, "ReturnValue")


def classes_equal(t: T, a, b):
    n = t.g.call_static(MATH, "EqualEqual_ClassClass", inputs=[Pin("A", CLASS, sub_object=cls_ref(OBJ)), Pin("B", CLASS, sub_object=cls_ref(OBJ))],
                        outputs=[Pin("ReturnValue", BOOL, "out")], pure=True)
    t.link(a, n, "A")
    t.link(b, n, "B")
    return (n, "ReturnValue")


# ---- Task 1: the ship fixes ----
def fix_tests():
    out = []

    t = T("FT_DFShip_EndRaceClosesPauseMenu", "Ending the race while paused closes the pause menu and unpauses; pausing afterwards is refused.")
    pc, gm, gs, racer, gates = race_context(t)
    toggle_pause(t, pc)
    t.true(is_paused(t), "paused")
    t.eq_int(t.length(pause_widgets(t), WPAUSE), 1, "pause menu up")
    end_race(t, gm, 1)
    t.false(is_paused(t), "race end unpaused")
    t.eq_int(t.length(pause_widgets(t), WPAUSE), 0, "pause menu gone")
    toggle_pause(t, pc)
    t.false(is_paused(t), "no pause after the race")
    t.call(GMC, "RestartRace", gm)
    out.append(t.finish())

    t = T("FT_DFShip_VolumePreviewDoesNotSave", "Dragging the volume slider previews the mix without saving; SetMasterVolume saves.")
    gi = game_instance(t)
    fresh_progress(t, gi)
    t.call(GIC, "PreviewMasterVolume", gi, inputs=[Pin("Volume", FLOAT, default="0.4")])
    t.eq_float(gi_pure(t, gi, "GetMasterVolume", "Volume", FLOAT), 1.0, "preview leaves the save alone", 0.001)
    t.call(GIC, "SetMasterVolume", gi, inputs=[Pin("Volume", FLOAT, default="0.4")])
    t.eq_float(gi_pure(t, gi, "GetMasterVolume", "Volume", FLOAT), 0.4, "SetMasterVolume saves", 0.001)
    fresh_progress(t, gi)
    out.append(t.finish())

    t = T("FT_DFShip_TickSkipsDeadControllers", "A dead entry in the racer list never raises a runtime error.")
    pc, gm, gs, racer, gates = race_context(t)
    idx = add_none_controller(t, gm)
    t.delay(1.0)
    remove_controller_at(t, gm, idx)
    t.true(t.get(GSC, "bRaceActive", BOOL, gs), "race still active")
    t.call(GMC, "RestartRace", gm)
    out.append(t.finish())

    t = T("FT_DFShip_RecordResultWithoutSave", "RecordResult with no save object records nothing and raises no error.")
    gi = game_instance(t)
    fresh_progress(t, gi)
    set_save_none(t, gi)
    expect_record(t, gi, 0, 100, 1, True, -1, False, "no save")
    t.call(GIC, "LoadProgress", gi)
    t.valid(t.get(GIC, "Save", OBJECT, gi, sub=cls_ref(SAVEC)), "save back after LoadProgress")
    t.true(gi_pure(t, gi, "IsVehicleUnlocked", "ReturnValue", BOOL, Index=0), "SEDAN open")
    fresh_progress(t, gi)
    out.append(t.finish())

    t = T("FT_DFShip_FreshSlotLoadsCleanly", "A slot with no file gives a fresh save with the first car and track open.")
    gi = game_instance(t)
    delete_slot(t, "DeadFireFresh")
    use_slot(t, gi, "DeadFireFresh")
    t.valid(t.get(GIC, "Save", OBJECT, gi, sub=cls_ref(SAVEC)), "a fresh save object")
    t.true(gi_pure(t, gi, "IsVehicleUnlocked", "ReturnValue", BOOL, Index=0), "SEDAN open")
    t.false(gi_pure(t, gi, "IsVehicleUnlocked", "ReturnValue", BOOL, Index=1), "BRUTE locked")
    t.false(save_exists(t, "DeadFireFresh"), "nothing written by a load")
    use_slot(t, gi, "DeadFireTest")
    delete_slot(t, "DeadFireFresh")
    fresh_progress(t, gi)
    out.append(t.finish())

    t = T("FT_DFShip_RefreshKeepsAValidClass", "RefreshPlayerVehicleClass always leaves a valid car class as the pawn class.")
    pc, gm, gs, racer, gates = race_context(t)
    t.call(GMC, "RefreshPlayerVehicleClass", gm)
    pvc = t.get(GMC, "PlayerVehicleClass", CLASS, gm, sub=cls_ref(VC))
    t.true(is_valid_class(t, pvc), "PlayerVehicleClass is a valid class")
    dpc = t.get(GAME_MODE_BASE, "DefaultPawnClass", CLASS, gm, sub=cls_ref(PAWN))
    t.true(classes_equal(t, pvc, dpc), "DefaultPawnClass follows PlayerVehicleClass")
    out.append(t.finish())
    return out


# ---- Task 3: the difficulty table and the rivals' speed ----
def difficulty_info(t: T, gi, index):
    n = t.g.call_on(GIC, "GetDifficultyInfo", inputs=[Pin("Index", INT, default=str(index))],
                    outputs=[Pin("Name", STRING, "out"), Pin("RivalDelta", INT, "out"), Pin("SpeedScale", FLOAT, "out"),
                             Pin("ItemIntervalScale", FLOAT, "out")], pure=True)
    t.link(gi, n, "self")
    return n


def expect_difficulty(t: T, gi, index, name, delta, speed, items):
    d = difficulty_info(t, gi, index)
    str_equals(t, (d, "Name"), name, "difficulty %d name" % index)
    t.eq_int((d, "RivalDelta"), delta, "difficulty %d rival delta" % index)
    t.eq_float((d, "SpeedScale"), speed, "difficulty %d speed scale" % index, 0.001)
    t.eq_float((d, "ItemIntervalScale"), items, "difficulty %d item interval scale" % index, 0.001)


def float_cmp(t: T, fn, src, value, message):
    n = t.g.call_static(MATH, fn, inputs=[Pin("A", FLOAT), Pin("B", FLOAT, default="%f" % value)], outputs=[Pin("ReturnValue", BOOL, "out")], pure=True)
    t.link(src, n, "A")
    t.true((n, "ReturnValue"), message)


def difficulty_tests():
    out = []
    t = T("FT_DFShip_DifficultyInfo", "The difficulty table: rival delta, NPC speed scale and item interval scale per level; out of range reads NORMAL.")
    gi = game_instance(t)
    fresh_progress(t, gi)
    expect_difficulty(t, gi, 0, "EASY", -1, 0.85, 1.5)
    expect_difficulty(t, gi, 2, "HARD", 2, 1.1, 0.6)
    expect_difficulty(t, gi, 7, "NORMAL", 0, 1.0, 1.0)
    t.call(GIC, "SetDifficulty", gi, inputs=[Pin("Difficulty", INT, default="2")])
    t.eq_int(gi_pure(t, gi, "GetNPCCountFor", "Count", INT, LevelCount=3), 5, "HARD gives 5 rivals for 3")
    n = t.g.call_on(GIC, "GetDifficultyName", outputs=[Pin("Name", STRING, "out")], pure=True)
    t.link(gi, n, "self")
    str_equals(t, (n, "Name"), "HARD", "the difficulty name comes from the table")
    fresh_progress(t, gi)
    out.append(t.finish())

    t = T("FT_DFShip_NPCSpeedScaleApplied", "NPCSpeedScale multiplies each spawned rival's speed scale.")
    pc, gm, gs, racer, gates = race_context(t)
    t.set(GMC, "NPCSpeedScale", FLOAT, gm, default="1.1")
    spawn_npcs(t, gm, 1)
    t.delay(1.0)
    ai = t.item(ai_controllers(t), AIC)
    s = t.get(AIC, "SpeedScale", FLOAT, ai)
    float_cmp(t, "GreaterEqual_FloatFloat", s, 0.989, "speed scale at least 0.9 x 1.1")
    float_cmp(t, "LessEqual_FloatFloat", s, 1.1001, "speed scale at most 1.1")
    despawn_npcs(t, gm)
    t.set(GMC, "NPCSpeedScale", FLOAT, gm, default="1.0")
    t.call(GMC, "RestartRace", gm)
    out.append(t.finish())
    return out


def build():
    return fix_tests() + difficulty_tests()


if __name__ == "__main__":
    for b in build():
        print(b.write(OUT))
