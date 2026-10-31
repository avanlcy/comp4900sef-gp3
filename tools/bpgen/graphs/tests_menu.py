"""Phase 5 FT_DFMenu_* tests (plan docs/superpowers/plans/2026-10-30-phase5-menus.md): vehicle stats, progress and
unlocks, race hooks, the summary's unlock line, pause, the menu pages. Same shape as tests.py; the test GameMode points
the GameInstance at the DeadFireTest save slot, so no test touches a developer's real progress.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, ".."))
from bpgen import CLASS, cls_ref  # noqa: E402,F401
from df import (BOOL, BP_GI, BP_GM, BP_PC, BP_SAVE, BP_VEHICLE, BP_VEHICLE_BRUTE, BP_VEHICLE_VIPER, BPC_RACER, CONTROLLER, FLOAT,  # noqa: E402
                GAME_INSTANCE, GAMEPLAY, INT, MATERIAL_INTERFACE, MATH, OBJECT, OUT, PRIMITIVE, SKEL_MESH_COMP, STATIC_MESH_COMP, STRING, WBP_LEVEL_SELECT,
                WBP_PAUSE, WBP_SUMMARY, WBP_VEHICLE_SELECT, Pin, as_pin, enum_pin, gen, name_of, obj_pin)
from tests import T, race_context  # noqa: E402
from tests_ai import ai_count  # noqa: E402
from tests_items import destroy, pawn_car, text_reads, widgets  # noqa: E402

VC = gen(BP_VEHICLE)


# ---- helpers ----
def spawn_class(t: T, asset, dx=0.0, dy=0.0):
    return t.spawn(gen(asset), t.offset(t.self_loc(), dx, dy, -120.0))


def str_equals(t: T, src, expected, message):
    eq = t.g.call_static("KismetStringLibrary", "EqualEqual_StrStr", inputs=[Pin("A", STRING), Pin("B", STRING, default=expected)],
                         outputs=[Pin("ReturnValue", "bool", "out")], pure=True)
    t.link(src, eq, "A")
    t.true((eq, "ReturnValue"), message)


def body_material(t: T, car, slot):
    """The material in one slot of the car's Body (Phase 7 Task 13: the visible car is the Body static mesh; the physics
    Mesh is hidden)."""
    body = t.get(VC, "Body", OBJECT, car, sub=cls_ref(STATIC_MESH_COMP))
    gm = t.g.call_on(PRIMITIVE, "GetMaterial", inputs=[Pin("ElementIndex", INT, default=str(slot))],
                     outputs=[obj_pin("ReturnValue", MATERIAL_INTERFACE, "out")], pure=True)
    t.link(body, gm, "self")
    return (gm, "ReturnValue")


def material_name(t: T, car, slot):
    """Display name of the material in one slot of the car's Body."""
    return name_of(t.g, body_material(t, car, slot))


def drive_throttle(t: T, car, value, kph):
    n = t.g.call_on(VC, "ComputeDriveThrottle", inputs=[Pin("Input", FLOAT, default="%f" % value), Pin("SpeedKPH", FLOAT, default="%f" % kph)],
                    outputs=[Pin("Throttle", FLOAT, "out")], pure=True)
    t.link(car, n, "self")
    return (n, "Throttle")


# ---- Task 1: vehicle stats ----
def vehicle_tests():
    t = T("FT_DFMenu_ThrottleStats", "Each car's throttle scale, speed limiter, health, boost and paint match the catalogue.")
    brute = spawn_class(t, BP_VEHICLE_BRUTE)
    t.eq_float(drive_throttle(t, brute, 1, 50), 0.8, "BRUTE throttle scale", 0.001)
    t.eq_float(drive_throttle(t, brute, 1, 125), 0.0, "BRUTE limiter above 120 km/h", 0.001)
    t.eq_float(drive_throttle(t, brute, -0.5, 125), -0.4, "BRUTE braking is scaled, never cut", 0.001)
    t.eq_float(t.get(VC, "MaxHealth", FLOAT, brute), 160, "BRUTE max health")
    t.eq_float(t.get(VC, "Health", FLOAT, brute), 160, "BRUTE starts at full health")
    str_equals(t, t.get(VC, "VehicleName", STRING, brute), "BRUTE", "BRUTE name")
    str_equals(t, material_name(t, brute, 0), "MI_DF_Paint_Brute", "BRUTE paint (Body slot 0)")
    viper = spawn_class(t, BP_VEHICLE_VIPER, dy=600.0)
    t.eq_float(t.get(VC, "MaxHealth", FLOAT, viper), 70, "VIPER max health")
    t.eq_float(t.get(VC, "BoostDuration", FLOAT, viper), 3, "VIPER boost duration")
    t.eq_float(t.get(VC, "BoostKickSpeed", FLOAT, viper), 1600, "VIPER boost kick")
    str_equals(t, material_name(t, viper, 0), "MI_DF_Paint_Viper", "VIPER paint (Body slot 0)")
    sedan = spawn_class(t, BP_VEHICLE, dy=-600.0)
    t.eq_float(drive_throttle(t, sedan, 1, 200), 1.0, "SEDAN has no limiter", 0.001)
    t.eq_float(drive_throttle(t, sedan, 0.5, 10), 0.5, "SEDAN throttle scale 1", 0.001)
    str_equals(t, material_name(t, sedan, 0), "MI_DF_Paint_Sedan", "SEDAN paint (Body slot 0)")
    for car in (brute, viper, sedan):
        destroy(t, car)
    return [t.finish()]


# ---- Task 2: progress, unlocks, settings (BP_DFGameInstance) ----
GIC, SAVEC = gen(BP_GI), gen(BP_SAVE)
ARR = "KismetArrayLibrary"


def game_instance(t: T):
    """The world's GameInstance cast to BP_DFGameInstance (impure cast, stepped: a wrong project setting fails loudly)."""
    gi = t.g.call_static(GAMEPLAY, "GetGameInstance", inputs=[Pin("WorldContextObject", OBJECT, hidden=True)],
                         outputs=[obj_pin("ReturnValue", GAME_INSTANCE, "out")], pure=True)
    c = t.step(t.g.cast(GIC))
    t.g.link(gi, "ReturnValue", c, "Object")
    return (c, as_pin(BP_GI))


def fresh_progress(t: T, gi):
    """Guards that the test GameMode pointed the save at the test slot, then resets the progress."""
    str_equals(t, t.get(GIC, "SaveSlotName", STRING, gi), "DeadFireTest", "test GameMode points the save at the test slot")
    t.call(GIC, "ResetProgress", gi)
    # ResetProgress keeps the settings on purpose; a test run must not inherit them from a crashed one
    t.call(GIC, "SetDifficulty", gi, inputs=[Pin("Difficulty", INT, default="1")])
    t.call(GIC, "SetMasterVolume", gi, inputs=[Pin("Volume", FLOAT, default="1.0")])


def gi_pure(t: T, gi, fn, out, cat, **inputs):
    """A pure GameInstance query with int inputs, e.g. gi_pure(t, gi, "IsVehicleUnlocked", "ReturnValue", BOOL, Index=2)."""
    n = t.g.call_on(GIC, fn, inputs=[Pin(k, INT, default=str(v)) for k, v in inputs.items()], outputs=[Pin(out, cat, "out")], pure=True)
    t.link(gi, n, "self")
    return (n, out)


def unlock_vehicle(t: T, gi, index):
    n = t.call(GIC, "UnlockVehicle", gi, inputs=[Pin("Index", INT, default=str(index))], outputs=[Pin("ReturnValue", BOOL, "out")])
    return (n, "ReturnValue")


def record(t: T, gi, level, score, rank, passed):
    n = t.call(GIC, "RecordResult", gi,
               inputs=[Pin("LevelIndex", INT, default=str(level)), Pin("Score", INT, default=str(score)), Pin("Rank", INT, default=str(rank)),
                       Pin("bPassed", BOOL, default="true" if passed else "false")],
               outputs=[Pin("UnlockedVehicle", INT, "out"), Pin("bUnlockedLevel", BOOL, "out")])
    return n


def expect_record(t: T, gi, level, score, rank, passed, vehicle, level_unlocked, what):
    n = record(t, gi, level, score, rank, passed)
    t.eq_int((n, "UnlockedVehicle"), vehicle, what + ": unlocked vehicle")
    (t.true if level_unlocked else t.false)((n, "bUnlockedLevel"), what + ": unlocked level")


def save_array(t: T, gi, name):
    save = t.get(GIC, "Save", OBJECT, gi, sub=cls_ref(SAVEC))
    return t.get(SAVEC, name, BOOL, save, container="Array")


def bool_array_length(t: T, arr):
    n = t.g.call_array(ARR, "Array_Length", Pin("e", BOOL), outputs=[Pin("ReturnValue", INT, "out")])
    t.link(arr, n, "TargetArray")
    return (n, "ReturnValue")


def int_array_length(t: T, gi, name):
    save = t.get(GIC, "Save", OBJECT, gi, sub=cls_ref(SAVEC))
    arr = t.get(SAVEC, name, INT, save, container="Array")
    n = t.g.call_array(ARR, "Array_Length", Pin("e", INT), outputs=[Pin("ReturnValue", INT, "out")])
    t.link(arr, n, "TargetArray")
    return (n, "ReturnValue")


def meta_tests():
    out = []
    t = T("FT_DFMenu_SaveRoundTrip", "Progress survives a save and a load in the test slot; a short array from an older save is padded; reset locks everything but the first car and track.")
    gi = game_instance(t)
    fresh_progress(t, gi)
    t.true(unlock_vehicle(t, gi, 2), "unlocking VIPER the first time")
    t.false(unlock_vehicle(t, gi, 2), "unlocking VIPER again")
    sp = t.call(GIC, "SaveProgress", gi, outputs=[Pin("ReturnValue", BOOL, "out")])
    t.true((sp, "ReturnValue"), "save written")
    t.call(GIC, "LoadProgress", gi)
    t.true(gi_pure(t, gi, "IsVehicleUnlocked", "ReturnValue", BOOL, Index=2), "VIPER unlocked after the load")
    t.false(gi_pure(t, gi, "IsVehicleUnlocked", "ReturnValue", BOOL, Index=1), "BRUTE still locked")
    t.true(gi_pure(t, gi, "IsVehicleUnlocked", "ReturnValue", BOOL, Index=0), "SEDAN always unlocked")
    t.false(gi_pure(t, gi, "IsLevelUnlocked", "ReturnValue", BOOL, Index=1), "SWITCHBACK locked")
    t.eq_int(gi_pure(t, gi, "GetBestScore", "Score", INT, Level=0), 0, "no best score yet")
    ex = t.static(GAMEPLAY, "DoesSaveGameExist", inputs=[Pin("SlotName", STRING, default="DeadFireTest"), Pin("UserIndex", INT, default="0")],
                  outputs=[Pin("ReturnValue", BOOL, "out")])
    t.true((ex, "ReturnValue"), "the test slot exists on disk")
    arr = save_array(t, gi, "UnlockedVehicles")
    shrink = t.g.call_array(ARR, "Array_Resize", Pin("e", BOOL), inputs=[Pin("Size", INT, default="1")], pure=False)
    t.link(arr, shrink, "TargetArray")
    t.step(shrink)
    t.call(GIC, "SaveProgress", gi, outputs=[Pin("ReturnValue", BOOL, "out")])
    t.call(GIC, "LoadProgress", gi)
    t.eq_int(bool_array_length(t, save_array(t, gi, "UnlockedVehicles")), 3, "a short array is padded on load")
    t.true(gi_pure(t, gi, "IsVehicleUnlocked", "ReturnValue", BOOL, Index=0), "SEDAN open after padding")
    t.false(gi_pure(t, gi, "IsVehicleUnlocked", "ReturnValue", BOOL, Index=2), "VIPER locked after padding")
    fresh_progress(t, gi)
    t.false(gi_pure(t, gi, "IsVehicleUnlocked", "ReturnValue", BOOL, Index=2), "reset locks VIPER")
    out.append(t.finish())

    t = T("FT_DFMenu_UnlockRules", "First place on a passed level unlocks that level's car; passing unlocks the next track; game over and later places change only the best score.")
    gi = game_instance(t)
    fresh_progress(t, gi)
    expect_record(t, gi, 0, 400, 1, True, 1, True, "first place on PROVING GROUND")
    t.true(gi_pure(t, gi, "IsVehicleUnlocked", "ReturnValue", BOOL, Index=1), "BRUTE unlocked")
    t.true(gi_pure(t, gi, "IsLevelUnlocked", "ReturnValue", BOOL, Index=1), "SWITCHBACK unlocked")
    t.eq_int(gi_pure(t, gi, "GetBestScore", "Score", INT, Level=0), 400, "best score 400")
    t.eq_int(gi_pure(t, gi, "GetBestRank", "Rank", INT, Level=0), 1, "best rank 1")
    expect_record(t, gi, 0, 500, 2, True, -1, False, "second place later")
    t.eq_int(gi_pure(t, gi, "GetBestScore", "Score", INT, Level=0), 500, "best score 500")
    t.eq_int(gi_pure(t, gi, "GetBestRank", "Rank", INT, Level=0), 1, "best rank stays 1")
    expect_record(t, gi, 1, 100, 1, False, -1, False, "game over on SWITCHBACK")
    t.eq_int(gi_pure(t, gi, "GetBestScore", "Score", INT, Level=1), 100, "SWITCHBACK best score 100")
    t.eq_int(gi_pure(t, gi, "GetBestRank", "Rank", INT, Level=1), 0, "no place from a game over")
    t.false(gi_pure(t, gi, "IsVehicleUnlocked", "ReturnValue", BOOL, Index=2), "VIPER still locked")
    expect_record(t, gi, 1, 450, 1, True, 2, False, "first place on SWITCHBACK")
    expect_record(t, gi, 0, 400, 1, True, -1, False, "BRUTE already unlocked")
    expect_record(t, gi, 7, 100, 1, True, -1, False, "a level the catalogue does not have")
    t.eq_int(int_array_length(t, gi, "BestScores"), 2, "best scores keep the catalogue size")
    t.eq_int(t.get(GIC, "LastUnlockedVehicle", INT, gi), -1, "nothing unlocked by the last call")
    fresh_progress(t, gi)
    out.append(t.finish())

    t = T("FT_DFMenu_SettingsApply", "Volume clamps and saves; difficulty names and rival counts follow the table; reset keeps the settings.")
    gi = game_instance(t)
    fresh_progress(t, gi)
    t.call(GIC, "SetMasterVolume", gi, inputs=[Pin("Volume", FLOAT, default="0.3")])
    t.eq_float(gi_pure(t, gi, "GetMasterVolume", "Volume", FLOAT), 0.3, "volume 0.3")
    t.call(GIC, "SetMasterVolume", gi, inputs=[Pin("Volume", FLOAT, default="1.7")])
    t.eq_float(gi_pure(t, gi, "GetMasterVolume", "Volume", FLOAT), 1.0, "volume clamps to 1")
    t.call(GIC, "SetDifficulty", gi, inputs=[Pin("Difficulty", INT, default="2")])
    str_equals(t, gi_pure(t, gi, "GetDifficultyName", "Name", STRING), "HARD", "HARD name")
    t.eq_int(gi_pure(t, gi, "GetNPCCountFor", "Count", INT, LevelCount=3), 5, "HARD: 3 rivals become 5")
    t.eq_int(gi_pure(t, gi, "GetNPCCountFor", "Count", INT, LevelCount=0), 0, "HARD: none stay none")
    t.call(GIC, "SetDifficulty", gi, inputs=[Pin("Difficulty", INT, default="0")])
    t.eq_int(gi_pure(t, gi, "GetNPCCountFor", "Count", INT, LevelCount=1), 1, "EASY: at least one rival")
    t.eq_int(gi_pure(t, gi, "GetNPCCountFor", "Count", INT, LevelCount=3), 2, "EASY: 3 rivals become 2")
    t.call(GIC, "SetDifficulty", gi, inputs=[Pin("Difficulty", INT, default="1")])
    t.eq_int(gi_pure(t, gi, "GetNPCCountFor", "Count", INT, LevelCount=3), 3, "NORMAL: 3 rivals stay 3")
    t.call(GIC, "SetDifficulty", gi, inputs=[Pin("Difficulty", INT, default="0")])
    t.call(GIC, "SetMasterVolume", gi, inputs=[Pin("Volume", FLOAT, default="0.3")])
    t.call(GIC, "ResetProgress", gi)
    t.eq_int(gi_pure(t, gi, "GetDifficulty", "Difficulty", INT), 0, "reset keeps the difficulty")
    t.eq_float(gi_pure(t, gi, "GetMasterVolume", "Volume", FLOAT), 0.3, "reset keeps the volume")
    fresh_progress(t, gi)
    t.eq_int(gi_pure(t, gi, "GetDifficulty", "Difficulty", INT), 1, "fresh progress puts the difficulty back to NORMAL")
    t.eq_float(gi_pure(t, gi, "GetMasterVolume", "Volume", FLOAT), 1.0, "fresh progress puts the volume back to 100 %")
    out.append(t.finish())

    t = T("FT_DFMenu_MapLoadDelayNeverZero", "A zero fade still loads the map: the load timer runs for at least a hundredth of a second.")
    gi = game_instance(t)
    t.set(GIC, "FadeSeconds", FLOAT, gi, default="0.0")
    t.eq_float(gi_pure(t, gi, "GetMapLoadDelay", "Seconds", FLOAT), 0.01, "a zero fade becomes a 0.01 s timer", 0.0001)
    t.set(GIC, "FadeSeconds", FLOAT, gi, default="0.5")
    t.eq_float(gi_pure(t, gi, "GetMapLoadDelay", "Seconds", FLOAT), 0.5, "a real fade keeps its time", 0.0001)
    out.append(t.finish())
    return out


# ---- Task 3: race hooks ----
RC, GMC = gen(BPC_RACER), gen(BP_GM)
END_REASON = "/Game/DeadFire/Data/E_DFRaceEndReason"


def wreck_and_wait(t: T, pc):
    """Wrecks the player's car and returns the car the respawn put the player in 2.5 s later."""
    car = pawn_car(t, pc)
    t.call(VC, "DestroyVehicle", car, inputs=[obj_pin("Killer", CONTROLLER)])
    t.delay(2.5)
    return pawn_car(t, pc)


def car_class_is(t: T, car, asset):
    cls = t.g.call_static(GAMEPLAY, "GetObjectClass", inputs=[obj_pin("Object", "/Script/CoreUObject.Object")],
                          outputs=[Pin("ReturnValue", CLASS, "out", cls_ref("/Script/CoreUObject.Object"))], pure=True)
    t.link(car, cls, "Object")
    eq = t.g.call_static(MATH, "EqualEqual_ClassClass", inputs=[Pin("A", CLASS, sub_object=cls_ref("/Script/CoreUObject.Object")),
                                                                 Pin("B", CLASS, sub_object=cls_ref("/Script/CoreUObject.Object"), default_object=gen(asset))],
                         outputs=[Pin("ReturnValue", BOOL, "out")], pure=True)
    t.g.link(cls, "ReturnValue", eq, "A")
    return (eq, "ReturnValue")


def select_vehicle(t: T, gi, index):
    t.set(GIC, "SelectedVehicle", INT, gi, default=str(index))


def end_race(t: T, gm, reason):
    t.call(GMC, "EndRace", gm, inputs=[enum_pin("Reason", END_REASON, default=reason)])


def race_hook_tests():
    out = []
    t = T("FT_DFMenu_SelectedVehicleSpawns", "The car chosen in the GameInstance is what a respawn puts the player in, once it is unlocked.")
    pc, gm, gs, racer, gates = race_context(t)
    gi = game_instance(t)
    fresh_progress(t, gi)
    t.true(unlock_vehicle(t, gi, 1), "BRUTE unlocked for the test")
    select_vehicle(t, gi, 1)
    t.call(GMC, "RestartRace", gm)
    t.delay(0.5)
    car = wreck_and_wait(t, pc)
    t.true(car_class_is(t, car, BP_VEHICLE_BRUTE), "the respawn car is a BRUTE")
    t.eq_float(t.get(VC, "MaxHealth", FLOAT, car), 160, "the BRUTE's health")
    select_vehicle(t, gi, 0)
    t.call(GMC, "RestartRace", gm)
    t.delay(0.5)
    car = wreck_and_wait(t, pc)
    t.true(car_class_is(t, car, BP_VEHICLE), "back to the SEDAN")
    fresh_progress(t, gi)
    out.append(t.finish())

    t = T("FT_DFMenu_LockedSelectionFallsBack", "A locked or unknown selection puts the player in the SEDAN.")
    pc, gm, gs, racer, gates = race_context(t)
    gi = game_instance(t)
    fresh_progress(t, gi)
    select_vehicle(t, gi, 2)
    t.call(GMC, "RestartRace", gm)
    t.delay(0.5)
    t.true(car_class_is(t, wreck_and_wait(t, pc), BP_VEHICLE), "a locked VIPER falls back to the SEDAN")
    select_vehicle(t, gi, 9)
    t.call(GMC, "RestartRace", gm)
    t.delay(0.5)
    t.true(car_class_is(t, wreck_and_wait(t, pc), BP_VEHICLE), "an unknown index falls back to the SEDAN")
    select_vehicle(t, gi, 0)
    t.call(GMC, "RestartRace", gm)
    out.append(t.finish())

    t = T("FT_DFMenu_EndRaceRecordsProgress", "A passed race in first place records the score and unlocks the car and the next track; a game over records only the score; the GameMode syncs the selected level.")
    pc, gm, gs, racer, gates = race_context(t)
    gi = game_instance(t)
    fresh_progress(t, gi)
    t.eq_int(t.get(GIC, "SelectedLevel", INT, gi), 0, "the GameMode synced SelectedLevel from LevelIndex")
    t.set(RC, "Score", INT, racer, default="350")
    end_race(t, gm, 1)
    t.eq_int(gi_pure(t, gi, "GetBestScore", "Score", INT, Level=0), 350, "best score recorded")
    t.eq_int(gi_pure(t, gi, "GetBestRank", "Rank", INT, Level=0), 1, "best rank recorded")
    t.true(gi_pure(t, gi, "IsVehicleUnlocked", "ReturnValue", BOOL, Index=1), "BRUTE unlocked by the race")
    t.true(gi_pure(t, gi, "IsLevelUnlocked", "ReturnValue", BOOL, Index=1), "SWITCHBACK unlocked by the race")
    # the summary consumes LastUnlockedVehicle / bLastUnlockedLevel as soon as it shows them: FT_DFMenu_SummaryShowsUnlock checks the line
    t.call(GMC, "RestartRace", gm)
    t.delay(0.5)
    t.call(GIC, "ResetProgress", gi)
    t.set(RC, "Score", INT, racer, default="350")
    end_race(t, gm, 2)
    t.eq_int(gi_pure(t, gi, "GetBestScore", "Score", INT, Level=0), 350, "a game over still records the score")
    t.eq_int(gi_pure(t, gi, "GetBestRank", "Rank", INT, Level=0), 0, "a game over places nobody")
    t.false(gi_pure(t, gi, "IsVehicleUnlocked", "ReturnValue", BOOL, Index=1), "a game over unlocks nothing")
    t.eq_int(t.get(GIC, "LastUnlockedVehicle", INT, gi), -1, "nothing remembered")
    t.call(GMC, "RestartRace", gm)
    fresh_progress(t, gi)
    out.append(t.finish())

    t = T("FT_DFMenu_HardKeepsTestLevelEmpty", "Difficulty never adds rivals to a level that has none, and a restart while paused resumes the world.")
    pc, gm, gs, racer, gates = race_context(t)
    gi = game_instance(t)
    t.call(GIC, "SetDifficulty", gi, inputs=[Pin("Difficulty", INT, default="2")])
    t.static(GAMEPLAY, "SetGamePaused", inputs=[Pin("WorldContextObject", OBJECT, hidden=True), Pin("bPaused", BOOL, default="true")],
             outputs=[Pin("ReturnValue", BOOL, "out")])
    t.call(GMC, "RestartRace", gm)
    paused = t.g.call_static(GAMEPLAY, "IsGamePaused", inputs=[Pin("WorldContextObject", OBJECT, hidden=True)], outputs=[Pin("ReturnValue", BOOL, "out")], pure=True)
    t.false((paused, "ReturnValue"), "a restart resumes a paused world")
    t.static(GAMEPLAY, "SetGamePaused", inputs=[Pin("WorldContextObject", OBJECT, hidden=True), Pin("bPaused", BOOL, default="false")],
             outputs=[Pin("ReturnValue", BOOL, "out")])  # cleanup, so a failure here never stalls the suite
    t.delay(1.0)
    t.eq_int(ai_count(t), 0, "HARD adds no rivals to a level with none")
    t.call(GIC, "SetDifficulty", gi, inputs=[Pin("Difficulty", INT, default="1")])
    out.append(t.finish())
    return out


# ---- Task 4: the summary's unlock line and NEXT, the pause menu ----
PCC, WSUM, WPAUSE = gen(BP_PC), gen(WBP_SUMMARY), gen(WBP_PAUSE)
TEXT_BLOCK, BUTTON, WIDGET = "/Script/UMG.TextBlock", "/Script/UMG.Button", "/Script/UMG.Widget"


def summary_widget(t: T):
    arr = widgets(t, WSUM)
    t.eq_int(t.length(arr, WSUM), 1, "one summary on screen")
    return t.item(arr, WSUM)


def summary_text(t: T, sw, name, expected, message):
    text_reads(t, t.get(WSUM, name, OBJECT, sw, sub=cls_ref(TEXT_BLOCK)), expected, message)


def button_visible(t: T, sw, name):
    btn = t.get(WSUM, name, OBJECT, sw, sub=cls_ref(BUTTON))
    n = t.g.call_on(WIDGET, "IsVisible", outputs=[Pin("ReturnValue", BOOL, "out")], pure=True)
    t.link(btn, n, "self")
    return (n, "ReturnValue")


def toggle_pause(t: T, pc):
    t.call(PCC, "TogglePause", pc)


def is_paused(t: T):
    n = t.g.call_static(GAMEPLAY, "IsGamePaused", inputs=[Pin("WorldContextObject", OBJECT, hidden=True)], outputs=[Pin("ReturnValue", BOOL, "out")], pure=True)
    return (n, "ReturnValue")


def summary_and_pause_tests():
    out = []
    t = T("FT_DFMenu_SummaryShowsUnlock", "The summary names what the race unlocked and offers NEXT when the next track is open; on the last track NEXT stays hidden.")
    pc, gm, gs, racer, gates = race_context(t)
    gi = game_instance(t)
    fresh_progress(t, gi)
    t.set(RC, "Score", INT, racer, default="350")
    end_race(t, gm, 1)
    t.delay(0.3)
    sw = summary_widget(t)
    summary_text(t, sw, "UnlockText", "NEW CAR UNLOCKED: BRUTE   NEXT TRACK UNLOCKED: SWITCHBACK", "the unlock line names the car and the track")
    summary_text(t, sw, "MenuLabel", "MENU", "the quit button became MENU")
    t.true(button_visible(t, sw, "NextButton"), "NEXT offered when the next track is open")
    t.call(GMC, "RestartRace", gm)
    t.delay(0.5)
    t.set(GMC, "LevelIndex", INT, gm, default="1")
    t.set(RC, "Score", INT, racer, default="450")
    end_race(t, gm, 1)
    t.delay(0.3)
    sw = summary_widget(t)
    summary_text(t, sw, "UnlockText", "NEW CAR UNLOCKED: VIPER", "the last track unlocks its car and no track")
    t.false(button_visible(t, sw, "NextButton"), "no NEXT on the last track")
    t.eq_int(gi_pure(t, gi, "GetBestScore", "Score", INT, Level=1), 450, "the last track's score recorded")
    t.set(GMC, "LevelIndex", INT, gm, default="0")
    t.call(GMC, "RestartRace", gm)
    fresh_progress(t, gi)
    out.append(t.finish())

    t = T("FT_DFMenu_SummaryGameOverNoUnlock", "A game over shows no unlock line and no NEXT.")
    pc, gm, gs, racer, gates = race_context(t)
    gi = game_instance(t)
    fresh_progress(t, gi)
    t.set(RC, "Score", INT, racer, default="350")
    end_race(t, gm, 2)
    t.delay(0.3)
    sw = summary_widget(t)
    summary_text(t, sw, "UnlockText", "", "no unlock line after a game over")
    t.false(button_visible(t, sw, "NextButton"), "no NEXT after a game over")
    t.call(GMC, "RestartRace", gm)
    fresh_progress(t, gi)
    out.append(t.finish())

    t = T("FT_DFMenu_PauseToggles", "P pauses the world with the pause menu up and resumes it; the summary refuses a pause.")
    pc, gm, gs, racer, gates = race_context(t)
    toggle_pause(t, pc)
    t.true(is_paused(t), "paused")
    t.eq_int(t.length(widgets(t, WPAUSE), WPAUSE), 1, "the pause menu is up")
    toggle_pause(t, pc)
    t.false(is_paused(t), "resumed")
    t.eq_int(t.length(widgets(t, WPAUSE), WPAUSE), 0, "the pause menu is gone")
    end_race(t, gm, 1)
    toggle_pause(t, pc)
    t.false(is_paused(t), "the summary refuses a pause")
    t.eq_int(t.length(widgets(t, WPAUSE), WPAUSE), 0, "no pause menu over the summary")
    t.call(GMC, "RestartRace", gm)
    out.append(t.finish())
    return out


# ---- Task 5: the car and track pages ----
WVEH, WLVL = gen(WBP_VEHICLE_SELECT), gen(WBP_LEVEL_SELECT)


def create_page(t: T, pc, asset):
    """A menu page created for the player (not added to the viewport: Construct never runs, the test drives Refresh)."""
    n = t.step(t.g.create_widget(gen(asset), result_class=gen(asset)))
    t.link(pc, n, "OwningPlayer")
    return (n, "ReturnValue")


def page_text(t: T, page, cls, name, expected, message):
    text_reads(t, t.get(cls, name, OBJECT, page, sub=cls_ref(TEXT_BLOCK)), expected, message)


def button_enabled(t: T, page, cls, name):
    btn = t.get(cls, name, OBJECT, page, sub=cls_ref(BUTTON))
    n = t.g.call_on(WIDGET, "GetIsEnabled", outputs=[Pin("ReturnValue", BOOL, "out")], pure=True)
    t.link(btn, n, "self")
    return (n, "ReturnValue")


def remove_page(t: T, page):
    t.call(WIDGET, "RemoveFromParent", page)


def page_tests():
    out = []
    t = T("FT_DFMenu_VehiclePage", "The car page shows the catalogue, its lock state and bars, wraps, and confirms the selection.")
    pc, gm, gs, racer, gates = race_context(t)
    gi = game_instance(t)
    fresh_progress(t, gi)
    page = create_page(t, pc, WBP_VEHICLE_SELECT)
    t.call(WVEH, "Refresh", page)
    page_text(t, page, WVEH, "NameText", "SEDAN", "first car")
    page_text(t, page, WVEH, "ArmorText", "ARMOR         [###--]", "SEDAN armor bar")
    page_text(t, page, WVEH, "SpeedText", "TOP SPEED     [###--]", "SEDAN speed bar")
    page_text(t, page, WVEH, "LockText", "", "SEDAN is open")
    t.true(button_enabled(t, page, WVEH, "ConfirmButton"), "NEXT enabled for an open car")
    t.call(WVEH, "SelectNext", page)
    page_text(t, page, WVEH, "NameText", "BRUTE", "second car")
    page_text(t, page, WVEH, "ArmorText", "ARMOR         [#####]", "BRUTE armor bar")
    page_text(t, page, WVEH, "LockText", "LOCKED  -  FINISH 1ST ON PROVING GROUND", "BRUTE lock hint")
    t.false(button_enabled(t, page, WVEH, "ConfirmButton"), "NEXT disabled for a locked car")
    t.true(unlock_vehicle(t, gi, 1), "BRUTE unlocked")
    t.call(WVEH, "Refresh", page)
    t.true(button_enabled(t, page, WVEH, "ConfirmButton"), "NEXT enabled once unlocked")
    t.call(WVEH, "SelectNext", page)
    page_text(t, page, WVEH, "NameText", "VIPER", "third car")
    page_text(t, page, WVEH, "LockText", "LOCKED  -  FINISH 1ST ON SWITCHBACK", "VIPER lock hint")
    t.call(WVEH, "SelectNext", page)
    page_text(t, page, WVEH, "NameText", "SEDAN", "wraps to the first car")
    t.call(WVEH, "SelectPrevious", page)
    page_text(t, page, WVEH, "NameText", "VIPER", "wraps back to the last car")
    t.call(WVEH, "SelectPrevious", page)
    t.call(WVEH, "Confirm", page)
    t.eq_int(t.get(GIC, "SelectedVehicle", INT, gi), 1, "confirm stores the selection")
    select_vehicle(t, gi, 0)
    remove_page(t, page)
    fresh_progress(t, gi)
    out.append(t.finish())

    t = T("FT_DFMenu_LevelPage", "The track page shows rules, best result and lock state.")
    pc, gm, gs, racer, gates = race_context(t)
    gi = game_instance(t)
    fresh_progress(t, gi)
    page = create_page(t, pc, WBP_LEVEL_SELECT)
    t.call(WLVL, "Refresh", page)
    page_text(t, page, WLVL, "NameText", "PROVING GROUND", "first track")
    page_text(t, page, WLVL, "RulesText", "PASS 300   CLOCK 120 s   RIVALS 3", "first track rules")
    page_text(t, page, WLVL, "BestText", "NOT RACED YET", "no result yet")
    t.true(button_enabled(t, page, WLVL, "RaceButton"), "RACE enabled for an open track")
    t.call(WLVL, "SelectNext", page)
    page_text(t, page, WLVL, "NameText", "SWITCHBACK", "second track")
    page_text(t, page, WLVL, "RulesText", "PASS 400   CLOCK 150 s   RIVALS 4", "second track rules")
    page_text(t, page, WLVL, "LockText", "LOCKED  -  PASS PROVING GROUND", "second track lock hint")
    t.false(button_enabled(t, page, WLVL, "RaceButton"), "RACE disabled for a locked track")
    record(t, gi, 0, 420, 2, True)
    t.call(WLVL, "SelectPrevious", page)
    page_text(t, page, WLVL, "BestText", "BEST 420   PLACE 2", "best result line")
    t.call(WLVL, "SelectNext", page)
    page_text(t, page, WLVL, "LockText", "", "second track open after passing the first")
    t.true(button_enabled(t, page, WLVL, "RaceButton"), "RACE enabled once unlocked")
    record(t, gi, 1, 50, 3, False)
    t.call(WLVL, "Refresh", page)
    page_text(t, page, WLVL, "BestText", "BEST 50   PLACE -", "a game over shows the score and no place")
    remove_page(t, page)
    fresh_progress(t, gi)
    out.append(t.finish())
    return out


def build():
    return vehicle_tests() + meta_tests() + race_hook_tests() + summary_and_pause_tests() + page_tests()


if __name__ == "__main__":
    for b in build():
        print(b.write(OUT))
