"""BP_DFSaveGame and BP_DFGameInstance (Phase 5, spec 2026-10-30 §4): the vehicle and level catalogues, saved progress
(unlocked cars and tracks, best score and place per track, settings), the unlock rules, the settings, and the level
transitions with a fade. The catalogue numbers come from VEHICLES and LEVELS in df.py.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from bpgen import CLASS, cls_ref  # noqa: E402
from df import (BOOL, BP_GI, BP_GM, BP_SAVE, BP_VEHICLE, DIFFICULTY_DELTA, DIFFICULTY_NAMES, FLOAT, GAME_INSTANCE, GAMEPLAY, INT,  # noqa: E402
                L_MAIN_MENU, LEVELS, LINEAR_COLOR, MATH, NAME, OBJECT, OUT, PLAYER_CONTROLLER, SAVE_GAME, SM_MASTER, SOUND_CLASS,
                SOUND_MIX, STRING, SYS, VEHICLES, Blueprint, Graph, Node, Pin, and_bool, as_pin, compare, gen, get_player_controller,
                is_valid, log_line, math2, native_enum_pin, obj_pin, obj_spec, struct_pin)

SAVEC, GIC, VC = gen(BP_SAVE), gen(BP_GI), gen(BP_VEHICLE)
ARR = "KismetArrayLibrary"
WINDOW_MODE = "/Script/Engine.EWindowMode"
CAMERA_MANAGER = "/Script/Engine.PlayerCameraManager"
GAME_USER_SETTINGS = "/Script/Engine.GameUserSettings"
M = "Dead Fire|Meta"


# ---------- graph helpers ----------
def branch_on(g: Graph, cond_src, prev=None) -> Node:
    b = g.branch()
    g.link(cond_src[0], cond_src[1], b, "Condition")
    if prev is not None:
        g.link(prev[0], prev[1], b, "execute")
    return b


def valid(g: Graph, src) -> Node:
    n = is_valid(g)
    g.link(src[0], src[1], n, "Object")
    return n


def save(g: Graph):
    return (g.var_get("Save", OBJECT, cls_ref(SAVEC)), "Save")


def save_get(g: Graph, name: str, cat: str):
    n = g.var_get_on(SAVEC, name, cat)
    s = save(g)
    g.link(s[0], s[1], n, "self")
    return (n, name)


def save_set(g: Graph, name: str, cat: str, value_src=None, default=None) -> Node:
    n = g.var_set_on(SAVEC, name, cat, default=default)
    s = save(g)
    g.link(s[0], s[1], n, "self")
    if value_src is not None:
        g.link(value_src[0], value_src[1], n, name)
    return n


def save_arr(g: Graph, name: str, cat: str):
    n = g.var_get_on(SAVEC, name, cat, container="Array")
    s = save(g)
    g.link(s[0], s[1], n, "self")
    return (n, name)


def arr_len(g: Graph, arr, cat: str):
    n = g.call_array(ARR, "Array_Length", Pin("e", cat), outputs=[Pin("ReturnValue", INT, "out")])
    g.link(arr[0], arr[1], n, "TargetArray")
    return (n, "ReturnValue")


def arr_valid_index(g: Graph, arr, cat: str, index_src):
    n = g.call_array(ARR, "Array_IsValidIndex", Pin("e", cat), inputs=[Pin("IndexToTest", INT)], outputs=[Pin("ReturnValue", BOOL, "out")])
    g.link(arr[0], arr[1], n, "TargetArray")
    g.link(index_src[0], index_src[1], n, "IndexToTest")
    return (n, "ReturnValue")


def arr_get(g: Graph, arr, cat: str, index_src):
    n = g.call_array(ARR, "Array_Get", Pin("e", cat), inputs=[Pin("Index", INT)], outputs=[Pin("Item", cat, "out")])
    g.link(arr[0], arr[1], n, "TargetArray")
    g.link(index_src[0], index_src[1], n, "Index")
    return (n, "Item")


def arr_set(g: Graph, arr, cat: str, index_src, item_src=None, item_default=None, index_default=None, size_to_fit="false") -> Node:
    n = g.call_array(ARR, "Array_Set", Pin("e", cat), inputs=[Pin("Index", INT, default=index_default), Pin("Item", cat, default=item_default),
                                                            Pin("bSizeToFit", BOOL, default=size_to_fit)], pure=False)
    g.link(arr[0], arr[1], n, "TargetArray")
    if index_src is not None:
        g.link(index_src[0], index_src[1], n, "Index")
    if item_src is not None:
        g.link(item_src[0], item_src[1], n, "Item")
    return n


def leaf(g: Graph, prev, pins, links=None) -> Node:
    """A function result node reached from prev=(node, pin): literal defaults in pins, linked values in links."""
    r = g.function_result(pins)
    g.link(prev[0], prev[1], r, "execute")
    for name, src in (links or {}).items():
        g.link(src[0], src[1], r, name)
    return r


def int_eq(g: Graph, src, value: int) -> Node:
    n = compare(g, "EqualEqual_IntInt", INT, b=str(value))
    g.link(src[0], src[1], n, "A")
    return n


def gi_pure(g: Graph, fn: str, outputs, **inputs) -> Node:
    """A pure call on this GameInstance's own function; inputs are (node, pin) sources or literals."""
    n = g.call_self(fn, inputs=[Pin(k, INT, default=None if isinstance(v, tuple) else str(v)) for k, v in inputs.items()],
                    outputs=outputs, pure=True)
    for k, v in inputs.items():
        if isinstance(v, tuple):
            g.link(v[0], v[1], n, k)
    return n


# ---------- the save ----------
def build_save() -> Blueprint:
    bp = Blueprint(BP_SAVE, parent=SAVE_GAME, description="Saved progress: unlocked cars and tracks, best score and place per track, the settings.")
    S = "Dead Fire|Save"
    bp.variable("UnlockedVehicles", "array<bool>", "", S)
    bp.variable("UnlockedLevels", "array<bool>", "", S)
    bp.variable("BestScores", "array<int>", "", S)
    bp.variable("BestRanks", "array<int>", "", S)  # 0 = never placed
    bp.variable("MasterVolume", "float", "1", S)
    bp.variable("Difficulty", "int", "1", S)
    return bp


# ---------- the game instance ----------
def vehicle_pins(row):
    return [Pin("Name", STRING, default=row.name), Pin("VehicleClass", CLASS, sub_object=cls_ref(VC), default_object=gen(row.asset)),
            Pin("UnlockLevel", INT, default=str(row.unlock_level)), Pin("Speed", INT, default=str(row.speed)),
            Pin("Acceleration", INT, default=str(row.acceleration)), Pin("Armor", INT, default=str(row.armor)),
            Pin("Boost", INT, default=str(row.boost)), Pin("Description", STRING, default=row.description)]


def level_pins(row):
    return [Pin("Name", STRING, default=row.name), Pin("MapName", NAME, default=row.map), Pin("Description", STRING, default=row.description),
            Pin("ScoreRequirement", INT, default=str(row.score)), Pin("TimeLimit", FLOAT, default="%f" % row.time),
            Pin("NPCCount", INT, default=str(row.npcs))]


VEHICLE_OUTPUTS = ["Name:string", "VehicleClass:class:" + VC, "UnlockLevel:int", "Speed:int", "Acceleration:int", "Armor:int", "Boost:int",
                   "Description:string"]
LEVEL_OUTPUTS = ["Name:string", "MapName:name", "Description:string", "ScoreRequirement:int", "TimeLimit:float", "NPCCount:int"]


def catalogue_function(bp: Blueprint, name: str, doc: str, outputs, rows, pins_of):
    """A pure Index -> row lookup: a branch per row 1..n-1, the last branch falling through to row 0 (also the out-of-range answer)."""
    g = bp.function(name, doc=doc, inputs=["Index:int"], outputs=outputs, pure=True)
    prev = ("entry", "then")
    for row in rows[1:]:
        b = branch_on(g, (int_eq(g, ("entry", "Index"), row.index), "ReturnValue"), prev)
        leaf(g, (b, "then"), pins_of(row))
        prev = (b, "else")
    leaf(g, prev, pins_of(rows[0]))


def build_instance() -> Blueprint:
    bp = Blueprint(BP_GI, parent=GAME_INSTANCE, description="The meta layer: car and track catalogues, saved progress and unlocks, settings, level transitions.")
    bp.requires(SM_MASTER, "SoundMix", "SoundMixFactory")
    bp.variable("Save", obj_spec(BP_SAVE), "", M)
    bp.variable("SaveSlotName", "string", "DeadFire", M, editable=True)
    bp.variable("SelectedVehicle", "int", "0", M)
    bp.variable("SelectedLevel", "int", "0", M)
    bp.variable("LastUnlockedVehicle", "int", "-1", M)
    bp.variable("bLastUnlockedLevel", "bool", "false", M)
    bp.variable("bReturnToVehicleSelect", "bool", "false", M)
    bp.variable("FadeSeconds", "float", "0.5", M, editable=True)
    bp.variable("PendingMap", "name", "", M)  # the map OpenMapWithFade loads once the fade has run
    bp.variable("MasterMix", "object:" + SOUND_MIX, "", M, editable=True)
    bp.variable("MasterClass", "object:" + SOUND_CLASS, "", M, editable=True)
    bp.default("MasterMix", SM_MASTER)
    bp.default("MasterClass", "/Engine/EngineSounds/Master")

    # ---- catalogues (pure) ----
    g = bp.function("GetVehicleCount", doc="How many cars the catalogue has.", outputs=["Count:int"], pure=True)
    leaf(g, ("entry", "then"), [Pin("Count", INT, default=str(len(VEHICLES)))])
    catalogue_function(bp, "GetVehicleInfo", "One car of the catalogue: name, class, the level whose first place unlocks it (-1 always open), stat bars 1-5, description.",
                       VEHICLE_OUTPUTS, VEHICLES, vehicle_pins)
    g = bp.function("GetLevelCount", doc="How many tracks the catalogue has.", outputs=["Count:int"], pure=True)
    leaf(g, ("entry", "then"), [Pin("Count", INT, default=str(len(LEVELS)))])
    catalogue_function(bp, "GetLevelInfo", "One track of the catalogue: name, map, description, pass score, clock, rivals.",
                       LEVEL_OUTPUTS, LEVELS, level_pins)

    # ---- progress queries (pure) ----
    def unlocked_query(name, array, doc):
        g = bp.function(name, doc=doc, inputs=["Index:int"], outputs=["ReturnValue:bool"], pure=True)
        b0 = branch_on(g, (int_eq(g, ("entry", "Index"), 0), "ReturnValue"), ("entry", "then"))
        g.note(b0, "the first one is always open")
        leaf(g, (b0, "then"), [Pin("ReturnValue", BOOL, default="true")])
        bs = branch_on(g, (valid(g, save(g)), "ReturnValue"), (b0, "else"))
        leaf(g, (bs, "else"), [Pin("ReturnValue", BOOL, default="false")])
        arr = save_arr(g, array, BOOL)
        bv = branch_on(g, arr_valid_index(g, arr, BOOL, ("entry", "Index")), (bs, "then"))
        leaf(g, (bv, "else"), [Pin("ReturnValue", BOOL, default="false")])
        leaf(g, (bv, "then"), [Pin("ReturnValue", BOOL)], {"ReturnValue": arr_get(g, save_arr(g, array, BOOL), BOOL, ("entry", "Index"))})

    unlocked_query("IsVehicleUnlocked", "UnlockedVehicles", "Is this car open? Car 0 always is; an unknown index is not.")
    unlocked_query("IsLevelUnlocked", "UnlockedLevels", "Is this track open? Track 0 always is; an unknown index is not.")

    def best_query(name, array, out, doc):
        g = bp.function(name, doc=doc, inputs=["Level:int"], outputs=[out + ":int"], pure=True)
        bs = branch_on(g, (valid(g, save(g)), "ReturnValue"), ("entry", "then"))
        leaf(g, (bs, "else"), [Pin(out, INT, default="0")])
        arr = save_arr(g, array, INT)
        bv = branch_on(g, arr_valid_index(g, arr, INT, ("entry", "Level")), (bs, "then"))
        leaf(g, (bv, "else"), [Pin(out, INT, default="0")])
        leaf(g, (bv, "then"), [Pin(out, INT)], {out: arr_get(g, save_arr(g, array, INT), INT, ("entry", "Level"))})

    best_query("GetBestScore", "BestScores", "Score", "Best score on a track (0 when never raced).")
    best_query("GetBestRank", "BestRanks", "Rank", "Best place on a track among passed races (0 when never placed).")

    g = bp.function("GetMasterVolume", doc="The saved master volume, 1 without a save.", outputs=["Volume:float"], pure=True)
    bs = branch_on(g, (valid(g, save(g)), "ReturnValue"), ("entry", "then"))
    leaf(g, (bs, "else"), [Pin("Volume", FLOAT, default="1.0")])
    leaf(g, (bs, "then"), [Pin("Volume", FLOAT)], {"Volume": save_get(g, "MasterVolume", FLOAT)})

    g = bp.function("GetDifficulty", doc="The saved difficulty (0 EASY, 1 NORMAL, 2 HARD), NORMAL without a save.", outputs=["Difficulty:int"], pure=True)
    bs = branch_on(g, (valid(g, save(g)), "ReturnValue"), ("entry", "then"))
    leaf(g, (bs, "else"), [Pin("Difficulty", INT, default="1")])
    leaf(g, (bs, "then"), [Pin("Difficulty", INT)], {"Difficulty": save_get(g, "Difficulty", INT)})

    g = bp.function("GetDifficultyName", doc="EASY, NORMAL or HARD.", outputs=["Name:string"], pure=True)
    d = gi_pure(g, "GetDifficulty", [Pin("Difficulty", INT, "out")])
    prev = ("entry", "then")
    for idx, label in ((0, DIFFICULTY_NAMES[0]), (2, DIFFICULTY_NAMES[2])):
        b = branch_on(g, (int_eq(g, (d, "Difficulty"), idx), "ReturnValue"), prev)
        leaf(g, (b, "then"), [Pin("Name", STRING, default=label)])
        prev = (b, "else")
    leaf(g, prev, [Pin("Name", STRING, default=DIFFICULTY_NAMES[1])])

    g = bp.function("GetNPCCountFor", doc="Rivals for a level that asks for LevelCount: EASY -1, NORMAL 0, HARD +2, at least 1; 0 stays 0.",
                    inputs=["LevelCount:int"], outputs=["Count:int"], pure=True)
    some = compare(g, "Greater_IntInt", INT, b="0")
    g.link_entry("LevelCount", some, "A")
    b = branch_on(g, (some, "ReturnValue"), ("entry", "then"))
    g.note(b, "a level with no rivals keeps none on every difficulty")
    leaf(g, (b, "else"), [Pin("Count", INT, default="0")])
    d = gi_pure(g, "GetDifficulty", [Pin("Difficulty", INT, "out")])
    hard = g.call_static(MATH, "SelectInt", inputs=[Pin("A", INT, default=str(DIFFICULTY_DELTA[2])), Pin("B", INT, default=str(DIFFICULTY_DELTA[1])), Pin("bPickA", BOOL)],
                         outputs=[Pin("ReturnValue", INT, "out")], pure=True)
    g.link(int_eq(g, (d, "Difficulty"), 2), "ReturnValue", hard, "bPickA")
    delta = g.call_static(MATH, "SelectInt", inputs=[Pin("A", INT, default=str(DIFFICULTY_DELTA[0])), Pin("B", INT), Pin("bPickA", BOOL)],
                          outputs=[Pin("ReturnValue", INT, "out")], pure=True)
    g.link(hard, "ReturnValue", delta, "B")
    g.link(int_eq(g, (d, "Difficulty"), 0), "ReturnValue", delta, "bPickA")
    total = math2(g, "Add_IntInt", INT)
    g.link_entry("LevelCount", total, "A")
    g.link(delta, "ReturnValue", total, "B")
    floor = g.call_static(MATH, "Max", inputs=[Pin("A", INT, default="1"), Pin("B", INT)], outputs=[Pin("ReturnValue", INT, "out")], pure=True)
    g.link(total, "ReturnValue", floor, "B")
    leaf(g, (b, "then"), [Pin("Count", INT)], {"Count": (floor, "ReturnValue")})

    g = bp.function("IsFullscreen", doc="The window is fullscreen or borderless fullscreen.", outputs=["ReturnValue:bool"], pure=True)
    gus = g.call_static("GameUserSettings", "GetGameUserSettings", outputs=[obj_pin("ReturnValue", GAME_USER_SETTINGS, "out")])
    g.link_entry("then", gus, "execute")
    fm = g.call_on(GAME_USER_SETTINGS, "GetFullscreenMode", outputs=[native_enum_pin("ReturnValue", WINDOW_MODE, direction="out")], pure=True)
    g.link(gus, "ReturnValue", fm, "self")
    windowed = g.call_static(MATH, "NotEqual_ByteByte", inputs=[Pin("A", "byte"), Pin("B", "byte", default="2")], outputs=[Pin("ReturnValue", BOOL, "out")], pure=True)
    g.link(fm, "ReturnValue", windowed, "A")
    leaf(g, (gus, "then"), [Pin("ReturnValue", BOOL)], {"ReturnValue": (windowed, "ReturnValue")})

    # ---- progress (impure) ----
    g = bp.function("EnsureArrays", doc="Pads the save's arrays to the catalogue sizes (an older save survives a new car or track) and opens car 0 and track 0.")
    bs = branch_on(g, (valid(g, save(g)), "ReturnValue"), ("entry", "then"))
    prev = [(bs, "then")]
    for array, cat, count in (("UnlockedVehicles", BOOL, len(VEHICLES)), ("UnlockedLevels", BOOL, len(LEVELS)),
                              ("BestScores", INT, len(LEVELS)), ("BestRanks", INT, len(LEVELS))):
        short = compare(g, "Less_IntInt", INT, b=str(count))
        g.link(arr_len(g, save_arr(g, array, cat), cat)[0], "ReturnValue", short, "A")
        b = branch_on(g, (short, "ReturnValue"))
        for p in prev:
            g.link(p[0], p[1], b, "execute")
        rs = g.call_array(ARR, "Array_Resize", Pin("e", cat), inputs=[Pin("Size", INT, default=str(count))], pure=False)
        g.link(save_arr(g, array, cat)[0], array, rs, "TargetArray")
        g.link(b, "then", rs, "execute")
        prev = [(b, "else"), (rs, "then")]
    open_car = arr_set(g, save_arr(g, "UnlockedVehicles", BOOL), BOOL, None, index_default="0", item_default="true", size_to_fit="true")
    for p in prev:
        g.link(p[0], p[1], open_car, "execute")
    open_track = arr_set(g, save_arr(g, "UnlockedLevels", BOOL), BOOL, None, index_default="0", item_default="true", size_to_fit="true")
    g.exec(open_car, open_track)

    def new_save(g, prev):
        """CreateSaveGameObject(BP_DFSaveGame) cast and stored in Save; returns the set node."""
        cr = g.call_static(GAMEPLAY, "CreateSaveGameObject", inputs=[Pin("SaveGameClass", CLASS, sub_object=cls_ref(SAVE_GAME), default_object=SAVEC)],
                           outputs=[obj_pin("ReturnValue", SAVE_GAME, "out")])
        g.link(prev[0], prev[1], cr, "execute")
        c = g.cast(SAVEC)
        g.link(cr, "ReturnValue", c, "Object")
        g.exec(cr, c)
        st = g.var_set("Save", OBJECT, sub_object=cls_ref(SAVEC))
        g.link(c, as_pin(BP_SAVE), st, "Save")
        g.link(c, "then", st, "execute")
        return st

    g = bp.function("LoadProgress", doc="Loads the save slot, or starts a fresh save; pads the arrays.")
    slot = g.var_get("SaveSlotName", STRING)
    ld = g.call_static(GAMEPLAY, "LoadGameFromSlot", inputs=[Pin("SlotName", STRING), Pin("UserIndex", INT, default="0")],
                       outputs=[obj_pin("ReturnValue", SAVE_GAME, "out")])
    g.link(slot, "SaveSlotName", ld, "SlotName")
    g.link_entry("then", ld, "execute")
    c = g.cast(SAVEC)
    g.link(ld, "ReturnValue", c, "Object")
    g.exec(ld, c)
    st = g.var_set("Save", OBJECT, sub_object=cls_ref(SAVEC))
    g.link(c, as_pin(BP_SAVE), st, "Save")
    g.link(c, "then", st, "execute")
    fresh = new_save(g, (c, "CastFailed"))
    ens = g.call_self("EnsureArrays")
    g.exec(st, ens)
    g.exec(fresh, ens)
    lg = log_line(g, "progress loaded from slot ", (g.var_get("SaveSlotName", STRING), "SaveSlotName"))
    g.exec(ens, lg)

    g = bp.function("SaveProgress", doc="Writes the save to its slot.", outputs=["ReturnValue:bool"])
    bs = branch_on(g, (valid(g, save(g)), "ReturnValue"), ("entry", "then"))
    sv = g.call_static(GAMEPLAY, "SaveGameToSlot", inputs=[obj_pin("SaveGameObject", SAVE_GAME), Pin("SlotName", STRING), Pin("UserIndex", INT, default="0")],
                       outputs=[Pin("ReturnValue", BOOL, "out")])
    s = save(g)
    g.link(s[0], s[1], sv, "SaveGameObject")
    g.link(g.var_get("SaveSlotName", STRING), "SaveSlotName", sv, "SlotName")
    g.link(bs, "then", sv, "execute")
    lg = log_line(g, "progress saved")
    g.exec(sv, lg)
    leaf(g, (lg, "then"), [Pin("ReturnValue", BOOL)], {"ReturnValue": (sv, "ReturnValue")})
    leaf(g, (bs, "else"), [Pin("ReturnValue", BOOL, default="false")])

    g = bp.function("ResetProgress", doc="A fresh save that keeps the settings; the selections go back to the first car and track.",
                    locals=["Old:" + obj_spec(BP_SAVE)])
    old = g.local_set("Old", OBJECT, sub_object=cls_ref(SAVEC))
    s = save(g)
    g.link(s[0], s[1], old, "Old")
    g.link_entry("then", old, "execute")
    st = new_save(g, (old, "then"))
    had = branch_on(g, (valid(g, (g.local_get("Old", OBJECT, cls_ref(SAVEC)), "Old")), "ReturnValue"), (st, "then"))
    g.note(had, "keep the settings of the old save")
    ov = g.var_get_on(SAVEC, "MasterVolume", FLOAT)
    g.link(g.local_get("Old", OBJECT, cls_ref(SAVEC)), "Old", ov, "self")
    sv_ = save_set(g, "MasterVolume", FLOAT, (ov, "MasterVolume"))
    g.link(had, "then", sv_, "execute")
    od = g.var_get_on(SAVEC, "Difficulty", INT)
    g.link(g.local_get("Old", OBJECT, cls_ref(SAVEC)), "Old", od, "self")
    sd_ = save_set(g, "Difficulty", INT, (od, "Difficulty"))
    g.exec(sv_, sd_)
    ens = g.call_self("EnsureArrays")
    g.exec(sd_, ens)
    g.link(had, "else", ens, "execute")
    prev = (ens, "then")
    for var, cat, val in (("SelectedVehicle", INT, "0"), ("SelectedLevel", INT, "0"), ("LastUnlockedVehicle", INT, "-1"), ("bLastUnlockedLevel", BOOL, "false")):
        n = g.var_set(var, cat, default=val)
        g.link(prev[0], prev[1], n, "execute")
        prev = (n, "then")
    sp = g.call_self("SaveProgress", outputs=[Pin("ReturnValue", BOOL, "out")])
    g.link(prev[0], prev[1], sp, "execute")
    lg = log_line(g, "progress reset")
    g.exec(sp, lg)

    def unlock_function(name, array, doc, what):
        g = bp.function(name, doc=doc, inputs=["Index:int"], outputs=["ReturnValue:bool"])
        bs = branch_on(g, (valid(g, save(g)), "ReturnValue"), ("entry", "then"))
        leaf(g, (bs, "else"), [Pin("ReturnValue", BOOL, default="false")])
        bv = branch_on(g, arr_valid_index(g, save_arr(g, array, BOOL), BOOL, ("entry", "Index")), (bs, "then"))
        leaf(g, (bv, "else"), [Pin("ReturnValue", BOOL, default="false")])
        already = branch_on(g, arr_get(g, save_arr(g, array, BOOL), BOOL, ("entry", "Index")), (bv, "then"))
        g.note(already, "already open?")
        leaf(g, (already, "then"), [Pin("ReturnValue", BOOL, default="false")])
        st = arr_set(g, save_arr(g, array, BOOL), BOOL, ("entry", "Index"), item_default="true")
        g.link(already, "else", st, "execute")
        conv = g.call_static("KismetStringLibrary", "Conv_IntToString", inputs=[Pin("InInt", INT)], outputs=[Pin("ReturnValue", STRING, "out")], pure=True)
        g.link_entry("Index", conv, "InInt")
        lg = log_line(g, "unlocked %s " % what, (conv, "ReturnValue"))
        g.exec(st, lg)
        leaf(g, (lg, "then"), [Pin("ReturnValue", BOOL, default="true")])

    unlock_function("UnlockVehicle", "UnlockedVehicles", "Opens a car; true when it was locked.", "car")
    unlock_function("UnlockLevel", "UnlockedLevels", "Opens a track; true when it was locked.", "track")

    g = bp.function("RecordResult", doc="A finished race: best score, best place when passed, the car for first place, the next track when passed; saved.",
                    inputs=["LevelIndex:int", "Score:int", "Rank:int", "bPassed:bool"], outputs=["UnlockedVehicle:int", "bUnlockedLevel:bool"],
                    locals=["Vehicle:int=-1", "bLevel:bool=false"])
    ok = and_bool(g)
    g.link(valid(g, save(g)), "ReturnValue", ok, "A")
    g.link(arr_valid_index(g, save_arr(g, "BestScores", INT), INT, ("entry", "LevelIndex"))[0], "ReturnValue", ok, "B")
    b = branch_on(g, (ok, "ReturnValue"), ("entry", "then"))
    g.note(b, "a level the catalogue knows?")
    leaf(g, (b, "else"), [Pin("UnlockedVehicle", INT, default="-1"), Pin("bUnlockedLevel", BOOL, default="false")])
    best = g.call_static(MATH, "Max", inputs=[Pin("A", INT), Pin("B", INT)], outputs=[Pin("ReturnValue", INT, "out")], pure=True)
    g.link(arr_get(g, save_arr(g, "BestScores", INT), INT, ("entry", "LevelIndex"))[0], "Item", best, "A")
    g.link_entry("Score", best, "B")
    set_best = arr_set(g, save_arr(g, "BestScores", INT), INT, ("entry", "LevelIndex"), (best, "ReturnValue"))
    g.link(b, "then", set_best, "execute")
    passed = g.branch()
    g.link_entry("bPassed", passed, "Condition")
    g.note(passed, "only a passed race places and unlocks")
    g.exec(set_best, passed)
    # place: the first placed result, then the better of the two
    cur = arr_get(g, save_arr(g, "BestRanks", INT), INT, ("entry", "LevelIndex"))
    better = g.call_static(MATH, "Min", inputs=[Pin("A", INT), Pin("B", INT)], outputs=[Pin("ReturnValue", INT, "out")], pure=True)
    g.link(cur[0], "Item", better, "A")
    g.link_entry("Rank", better, "B")
    never = int_eq(g, cur, 0)
    new_rank = g.call_static(MATH, "SelectInt", inputs=[Pin("A", INT), Pin("B", INT), Pin("bPickA", BOOL)], outputs=[Pin("ReturnValue", INT, "out")], pure=True)
    g.link_entry("Rank", new_rank, "A")
    g.link(better, "ReturnValue", new_rank, "B")
    g.link(never, "ReturnValue", new_rank, "bPickA")
    set_rank = arr_set(g, save_arr(g, "BestRanks", INT), INT, ("entry", "LevelIndex"), (new_rank, "ReturnValue"))
    g.link(passed, "then", set_rank, "execute")
    # first place: the car whose UnlockLevel is this level
    first = branch_on(g, (int_eq(g, ("entry", "Rank"), 1), "ReturnValue"), (set_rank, "then"))
    g.note(first, "first place?")
    loop = g.for_loop()
    last = math2(g, "Subtract_IntInt", INT, b="1")
    g.link(gi_pure(g, "GetVehicleCount", [Pin("Count", INT, "out")]), "Count", last, "A")
    g.link(last, "ReturnValue", loop, "LastIndex")
    g.link(first, "then", loop, "execute")
    info = gi_pure(g, "GetVehicleInfo", [Pin(p.split(":")[0], {"string": STRING, "int": INT}.get(p.split(":")[1], CLASS), "out",
                                             cls_ref(VC) if p.startswith("VehicleClass") else None) for p in VEHICLE_OUTPUTS], Index=(loop, "Index"))
    mine = compare(g, "EqualEqual_IntInt", INT)
    g.link(info, "UnlockLevel", mine, "A")
    g.link_entry("LevelIndex", mine, "B")
    bm = branch_on(g, (mine, "ReturnValue"), (loop, "LoopBody"))
    un = g.call_self("UnlockVehicle", inputs=[Pin("Index", INT)], outputs=[Pin("ReturnValue", BOOL, "out")])
    g.link(loop, "Index", un, "Index")
    g.link(bm, "then", un, "execute")
    bu = branch_on(g, (un, "ReturnValue"), (un, "then"))
    sv = g.local_set("Vehicle", INT)
    g.link(loop, "Index", sv, "Vehicle")
    g.link(bu, "then", sv, "execute")
    # the next track
    nxt = math2(g, "Add_IntInt", INT, b="1")
    g.link_entry("LevelIndex", nxt, "A")
    ul = g.call_self("UnlockLevel", inputs=[Pin("Index", INT)], outputs=[Pin("ReturnValue", BOOL, "out")])
    g.link(nxt, "ReturnValue", ul, "Index")
    g.link(loop, "Completed", ul, "execute")
    g.link(first, "else", ul, "execute")
    sl = g.local_set("bLevel", BOOL)
    g.link(ul, "ReturnValue", sl, "bLevel")
    g.exec(ul, sl)
    # common tail: remember what this race unlocked, save, answer
    rem_v = g.var_set("LastUnlockedVehicle", INT)
    g.link(g.local_get("Vehicle", INT), "Vehicle", rem_v, "LastUnlockedVehicle")
    g.exec(sl, rem_v)
    g.link(passed, "else", rem_v, "execute")
    rem_l = g.var_set("bLastUnlockedLevel", BOOL)
    g.link(g.local_get("bLevel", BOOL), "bLevel", rem_l, "bLastUnlockedLevel")
    g.exec(rem_v, rem_l)
    sp = g.call_self("SaveProgress", outputs=[Pin("ReturnValue", BOOL, "out")])
    g.exec(rem_l, sp)
    leaf(g, (sp, "then"), [Pin("UnlockedVehicle", INT), Pin("bUnlockedLevel", BOOL)],
         {"UnlockedVehicle": (g.local_get("Vehicle", INT), "Vehicle"), "bUnlockedLevel": (g.local_get("bLevel", BOOL), "bLevel")})

    def count_function(name, query, count_fn, doc):
        g = bp.function(name, doc=doc, outputs=["Count:int"], locals=["N:int=0"])
        loop = g.for_loop()
        last = math2(g, "Subtract_IntInt", INT, b="1")
        g.link(gi_pure(g, count_fn, [Pin("Count", INT, "out")]), "Count", last, "A")
        g.link(last, "ReturnValue", loop, "LastIndex")
        g.link_entry("then", loop, "execute")
        q = gi_pure(g, query, [Pin("ReturnValue", BOOL, "out")], Index=(loop, "Index"))
        b = branch_on(g, (q, "ReturnValue"), (loop, "LoopBody"))
        inc = math2(g, "Add_IntInt", INT, b="1")
        g.link(g.local_get("N", INT), "N", inc, "A")
        sn = g.local_set("N", INT)
        g.link(inc, "ReturnValue", sn, "N")
        g.link(b, "then", sn, "execute")
        leaf(g, (loop, "Completed"), [Pin("Count", INT)], {"Count": (g.local_get("N", INT), "N")})

    count_function("CountUnlockedVehicles", "IsVehicleUnlocked", "GetVehicleCount", "How many cars are open.")
    count_function("CountUnlockedLevels", "IsLevelUnlocked", "GetLevelCount", "How many tracks are open.")

    # ---- settings ----
    g = bp.function("ApplyAudioSettings", doc="Pushes the master sound mix with the saved volume on the Master sound class.")
    ok = and_bool(g)
    g.link(valid(g, save(g)), "ReturnValue", ok, "A")
    g.link(valid(g, (g.var_get("MasterMix", OBJECT, cls_ref(SOUND_MIX)), "MasterMix")), "ReturnValue", ok, "B")
    b = branch_on(g, (ok, "ReturnValue"), ("entry", "then"))
    ov = g.call_static(GAMEPLAY, "SetSoundMixClassOverride",
                       inputs=[Pin("WorldContextObject", OBJECT, hidden=True), obj_pin("InSoundMixModifier", SOUND_MIX), obj_pin("InSoundClass", SOUND_CLASS),
                               Pin("Volume", FLOAT), Pin("Pitch", FLOAT, default="1.0"), Pin("FadeInTime", FLOAT, default="0.2"), Pin("bApplyToChildren", BOOL, default="true")])
    g.link(g.var_get("MasterMix", OBJECT, cls_ref(SOUND_MIX)), "MasterMix", ov, "InSoundMixModifier")
    g.link(g.var_get("MasterClass", OBJECT, cls_ref(SOUND_CLASS)), "MasterClass", ov, "InSoundClass")
    g.link(save_get(g, "MasterVolume", FLOAT)[0], "MasterVolume", ov, "Volume")
    g.link(b, "then", ov, "execute")
    push = g.call_static(GAMEPLAY, "PushSoundMixModifier", inputs=[Pin("WorldContextObject", OBJECT, hidden=True), obj_pin("InSoundMixModifier", SOUND_MIX)])
    g.link(g.var_get("MasterMix", OBJECT, cls_ref(SOUND_MIX)), "MasterMix", push, "InSoundMixModifier")
    g.exec(ov, push)

    g = bp.function("SetMasterVolume", doc="Saves and applies the master volume (0-1).", inputs=["Volume:float"])
    bs = branch_on(g, (valid(g, save(g)), "ReturnValue"), ("entry", "then"))
    cl = g.call_static(MATH, "FClamp", inputs=[Pin("Value", FLOAT), Pin("Min", FLOAT, default="0.0"), Pin("Max", FLOAT, default="1.0")],
                       outputs=[Pin("ReturnValue", FLOAT, "out")], pure=True)
    g.link_entry("Volume", cl, "Value")
    st = save_set(g, "MasterVolume", FLOAT, (cl, "ReturnValue"))
    g.link(bs, "then", st, "execute")
    sp = g.call_self("SaveProgress", outputs=[Pin("ReturnValue", BOOL, "out")])
    ap = g.call_self("ApplyAudioSettings")
    g.exec(st, sp, ap)

    g = bp.function("SetDifficulty", doc="Saves the difficulty (0 EASY, 1 NORMAL, 2 HARD).", inputs=["Difficulty:int"])
    bs = branch_on(g, (valid(g, save(g)), "ReturnValue"), ("entry", "then"))
    cl = g.call_static(MATH, "Clamp", inputs=[Pin("Value", INT), Pin("Min", INT, default="0"), Pin("Max", INT, default="2")],
                       outputs=[Pin("ReturnValue", INT, "out")], pure=True)
    g.link_entry("Difficulty", cl, "Value")
    st = save_set(g, "Difficulty", INT, (cl, "ReturnValue"))
    g.link(bs, "then", st, "execute")
    sp = g.call_self("SaveProgress", outputs=[Pin("ReturnValue", BOOL, "out")])
    g.exec(st, sp)

    g = bp.function("ToggleFullscreen", doc="Windowed <-> borderless fullscreen, applied at once (the engine saves this itself).")
    gus = g.call_static("GameUserSettings", "GetGameUserSettings", outputs=[obj_pin("ReturnValue", GAME_USER_SETTINGS, "out")])
    g.link_entry("then", gus, "execute")
    full = gi_pure(g, "IsFullscreen", [Pin("ReturnValue", BOOL, "out")])
    b = branch_on(g, (full, "ReturnValue"), (gus, "then"))
    g.note(b, "fullscreen now? then back to a window")
    to_win = g.call_on(GAME_USER_SETTINGS, "SetFullscreenMode", inputs=[native_enum_pin("InFullscreenMode", WINDOW_MODE, "Windowed")])
    g.link(gus, "ReturnValue", to_win, "self")
    g.link(b, "then", to_win, "execute")
    to_full = g.call_on(GAME_USER_SETTINGS, "SetFullscreenMode", inputs=[native_enum_pin("InFullscreenMode", WINDOW_MODE, "WindowedFullscreen")])
    g.link(gus, "ReturnValue", to_full, "self")
    g.link(b, "else", to_full, "execute")
    ap = g.call_on(GAME_USER_SETTINGS, "ApplySettings", inputs=[Pin("bCheckForCommandLineOverrides", BOOL, default="false")])
    g.link(gus, "ReturnValue", ap, "self")
    g.exec(to_win, ap)
    g.exec(to_full, ap)

    g = bp.function("UseSaveSlot", doc="Switches to another save slot and loads it (the functional tests' DeadFireTest).", inputs=["SlotName:string"])
    ne = g.call_static("KismetStringLibrary", "NotEqual_StrStr", inputs=[Pin("A", STRING), Pin("B", STRING)], outputs=[Pin("ReturnValue", BOOL, "out")], pure=True)
    g.link_entry("SlotName", ne, "A")
    g.link(g.var_get("SaveSlotName", STRING), "SaveSlotName", ne, "B")
    b = branch_on(g, (ne, "ReturnValue"), ("entry", "then"))
    st = g.var_set("SaveSlotName", STRING)
    g.link_entry("SlotName", st, "SaveSlotName")
    g.link(b, "then", st, "execute")
    ld = g.call_self("LoadProgress")
    g.exec(st, ld)

    # ---- navigation ----
    def open_map(g, prev, name_src=None, name_default=None):
        n = g.call_self("OpenMapWithFade", inputs=[Pin("MapName", NAME, default=name_default)])
        if name_src is not None:
            g.link(name_src[0], name_src[1], n, "MapName")
        g.link(prev[0], prev[1], n, "execute")
        return n

    g = bp.function("StartRace", doc="Loads the selected track (with the fade).")
    info = gi_pure(g, "GetLevelInfo", [Pin("Name", STRING, "out"), Pin("MapName", NAME, "out"), Pin("Description", STRING, "out"),
                                      Pin("ScoreRequirement", INT, "out"), Pin("TimeLimit", FLOAT, "out"), Pin("NPCCount", INT, "out")],
                   Index=(g.var_get("SelectedLevel", INT), "SelectedLevel"))
    open_map(g, ("entry", "then"), (info, "MapName"))

    g = bp.function("StartNextLevel", doc="Selects the next track when it is open and starts it.")
    nxt = math2(g, "Add_IntInt", INT, b="1")
    g.link(g.var_get("SelectedLevel", INT), "SelectedLevel", nxt, "A")
    unlocked = gi_pure(g, "IsLevelUnlocked", [Pin("ReturnValue", BOOL, "out")], Index=(nxt, "ReturnValue"))
    b = branch_on(g, (unlocked, "ReturnValue"), ("entry", "then"))
    st = g.var_set("SelectedLevel", INT)
    g.link(nxt, "ReturnValue", st, "SelectedLevel")
    g.link(b, "then", st, "execute")
    sr = g.call_self("StartRace")
    g.exec(st, sr)

    g = bp.function("OpenMainMenu", doc="Back to the main menu; from a race it opens on the car page (the flowchart's continue loop).")
    gm = g.call_static(GAMEPLAY, "GetGameMode", inputs=[Pin("WorldContextObject", OBJECT, hidden=True)],
                       outputs=[obj_pin("ReturnValue", "/Script/Engine.GameModeBase", "out")], pure=True)
    c = g.cast(gen(BP_GM))
    g.link(gm, "ReturnValue", c, "Object")
    g.link_entry("then", c, "execute")
    st = g.var_set("bReturnToVehicleSelect", BOOL, default="true")
    g.link(c, "then", st, "execute")
    om = open_map(g, (st, "then"), name_default=L_MAIN_MENU)
    g.link(c, "CastFailed", om, "execute")

    g = bp.function("ReloadCurrentLevel", doc="Reloads the level being played (the summary's RETRY), with the fade.")
    cur = g.call_static(GAMEPLAY, "GetCurrentLevelName", inputs=[Pin("WorldContextObject", OBJECT, hidden=True), Pin("bRemovePrefixString", BOOL, default="true")],
                        outputs=[Pin("ReturnValue", STRING, "out")])
    g.link_entry("then", cur, "execute")
    nm = g.call_static("KismetStringLibrary", "Conv_StringToName", inputs=[Pin("InString", STRING)], outputs=[Pin("ReturnValue", NAME, "out")], pure=True)
    g.link(cur, "ReturnValue", nm, "InString")
    open_map(g, (cur, "then"), (nm, "ReturnValue"))

    # ---- the fade, then the map (a function plus a timer: functions cannot hold latent nodes, and a call to a custom
    # event cannot resolve before the event graph is imported) ----
    g = bp.function("GetMapLoadDelay", doc="The load timer: FadeSeconds, but never under 0.01 s (a zero timer never fires).",
                    outputs=["Seconds:float"], pure=True)
    floor = g.call_static(MATH, "FMax", inputs=[Pin("A", FLOAT), Pin("B", FLOAT, default="0.01")], outputs=[Pin("ReturnValue", FLOAT, "out")], pure=True)
    g.link(g.var_get("FadeSeconds", FLOAT), "FadeSeconds", floor, "A")
    g.link_result(floor, "ReturnValue", "Seconds")
    g.link_entry("then", "result", "execute")

    g = bp.function("OpenMapWithFade", doc="Fades the local camera to black over FadeSeconds, then loads the map (OpenPendingMap on a timer).",
                    inputs=["MapName:name"])
    pend = g.var_set("PendingMap", NAME)
    g.link_entry("MapName", pend, "PendingMap")
    g.link_entry("then", pend, "execute")
    pc = get_player_controller(g)
    has_pc = branch_on(g, (valid(g, (pc, "ReturnValue")), "ReturnValue"), (pend, "then"))
    cam = g.var_get_on(PLAYER_CONTROLLER, "PlayerCameraManager", OBJECT, cls_ref(CAMERA_MANAGER))
    g.link(pc, "ReturnValue", cam, "self")
    fade = g.call_on(CAMERA_MANAGER, "StartCameraFade",
                     inputs=[Pin("FromAlpha", FLOAT, default="0.0"), Pin("ToAlpha", FLOAT, default="1.0"), Pin("Duration", FLOAT),
                             struct_pin("Color", LINEAR_COLOR, default="(R=0.000000,G=0.000000,B=0.000000,A=1.000000)"),
                             Pin("bShouldFadeAudio", BOOL, default="false"), Pin("bHoldWhenFinished", BOOL, default="true")])
    g.link(cam, "PlayerCameraManager", fade, "self")
    g.link(g.var_get("FadeSeconds", FLOAT), "FadeSeconds", fade, "Duration")
    g.link(has_pc, "then", fade, "execute")
    timer = g.call_static(SYS, "K2_SetTimer", inputs=[obj_pin("Object", "/Script/CoreUObject.Object"), Pin("FunctionName", STRING, default="OpenPendingMap"),
                                                      Pin("Time", FLOAT), Pin("bLooping", BOOL, default="false"),
                                                      Pin("InitialStartDelay", FLOAT, default="0.0"), Pin("InitialStartDelayVariance", FLOAT, default="0.0")],
                          outputs=[struct_pin("ReturnValue", "/Script/Engine.TimerHandle", "out")])
    g.link(g.self_node(), "self", timer, "Object")
    g.link(gi_pure(g, "GetMapLoadDelay", [Pin("Seconds", FLOAT, "out")]), "Seconds", timer, "Time")
    g.exec(fade, timer)
    g.link(has_pc, "else", timer, "execute")

    g = bp.function("OpenPendingMap", doc="Loads PendingMap (the timer's target after the fade).")
    op = g.call_static(GAMEPLAY, "OpenLevel", inputs=[Pin("WorldContextObject", OBJECT, hidden=True), Pin("LevelName", NAME),
                                                        Pin("bAbsolute", BOOL, default="true"), Pin("Options", STRING, default="")])
    g.link(g.var_get("PendingMap", NAME), "PendingMap", op, "LevelName")
    g.link_entry("then", op, "execute")

    # ---- event graph ----
    g = bp.event_graph()
    g.section("Init: load the progress")
    init = g.event(GAME_INSTANCE, "ReceiveInit")
    ld = g.call_self("LoadProgress")
    g.exec(init, ld)
    return bp


def build():
    return [build_save(), build_instance()]


if __name__ == "__main__":
    for b in build():
        print(b.write(OUT))
