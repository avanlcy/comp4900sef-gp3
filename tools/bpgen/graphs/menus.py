"""The menus (Phase 5, spec 2026-10-30 §5): the pause menu, and (Task 5) the menu level's GameMode and player
controller with the main, car, track and settings pages. Widget recipes come from hud.py so the menus match the HUD.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from bpgen import WidgetBlueprint, cls_ref  # noqa: E402,F401
from df import (ACTOR, BOOL, BP_GI, BP_GM, BP_MENU_GM, BP_MENU_PC, BP_PC, BP_VEHICLE, CAMERA_ACTOR, CLASS, FLOAT, GAME_MODE_BASE,  # noqa: E402
                GAMEPLAY, INT, LINEAR_COLOR, MATH, NAME, OBJECT, OUT, PLAYER_CONTROLLER, STRING, USER_WIDGET, WBP_LEVEL_SELECT,
                WBP_MAIN_MENU, WBP_PAUSE, WBP_SETTINGS, WBP_VEHICLE_SELECT, Blueprint, Pin, as_pin, compare, game_instance, gen,
                is_valid, math2, native_enum_pin, obj_pin, struct_pin)
from hud import AMBER, BORDER, BUTTON, HBOX, SIZEBOX, TEXT_BLOCK, UMG, VBOX, WIDGET, add_text_helpers, cat, label, pick, s_int, text_props  # noqa: E402

ARR = "KismetArrayLibrary"

GIC, GMC, PCC = gen(BP_GI), gen(BP_GM), gen(BP_PC)
DARK = [0.05, 0.05, 0.05, 1]


def button(bp, name, label, parent, padding=(0, 0, 0, 12), size=28):
    bp.widget(name, BUTTON, parent, slot={"padding": list(padding), "h_align": "Fill"})
    bp.widget(name[:-6] + "Label", TEXT_BLOCK, name, text_props(label, size, DARK, "Center"))


def clicked(g, name, row):
    return g.component_event(name, "OnClicked", BUTTON, [], "OnButtonClickedEvent__DelegateSignature", UMG, col=0, row=row)


def owning_player(g):
    return g.call_self_native(WIDGET, "GetOwningPlayer", outputs=[obj_pin("ReturnValue", PLAYER_CONTROLLER, "out")], pure=True)


def quit_game(g, prev):
    q = g.call_static("KismetSystemLibrary", "QuitGame", inputs=[Pin("WorldContextObject", OBJECT, hidden=True), obj_pin("SpecificPlayer", PLAYER_CONTROLLER),
                                                                  native_enum_pin("QuitPreference", "/Script/Engine.EQuitPreference", "Quit"),
                                                                  Pin("bIgnorePlatformRestrictions", BOOL, default="false")])
    g.link(owning_player(g), "ReturnValue", q, "SpecificPlayer")
    g.link(prev[0], prev[1], q, "execute")
    return q


# ---------- pause ----------
def build_pause() -> WidgetBlueprint:
    bp = WidgetBlueprint(WBP_PAUSE, description="The pause menu: RESUME, RESTART, MAIN MENU, QUIT over a dark backdrop.")
    bp.widget("Backdrop", BORDER, None, {"brush_color": [0, 0, 0, 0.65]}, {"anchors": [0, 0, 1, 1], "position": [0, 0], "size": [0, 0]})
    bp.widget("PauseBox", VBOX, None, slot={"anchors": [0.5, 0.5, 0.5, 0.5], "alignment": [0.5, 0.5], "auto_size": True})
    bp.widget("TitleText", TEXT_BLOCK, "PauseBox", text_props("PAUSED", 60, AMBER, "Center"), {"h_align": "Center", "padding": [0, 0, 0, 24]})
    button(bp, "ResumeButton", "RESUME", "PauseBox")
    button(bp, "RestartButton", "RESTART", "PauseBox")
    button(bp, "MenuButton", "MAIN MENU", "PauseBox")
    button(bp, "QuitButton", "QUIT", "PauseBox", padding=(0, 0, 0, 0))
    add_text_helpers(bp)

    g = bp.event_graph()
    g.section("Resume: the controller toggles the pause off")
    ev = clicked(g, "ResumeButton", 1)
    pc = g.cast(PCC)
    g.link(owning_player(g), "ReturnValue", pc, "Object")
    g.exec(ev, pc)
    tp = g.call_on(PCC, "TogglePause")
    g.link(pc, as_pin(BP_PC), tp, "self")
    g.link(pc, "then", tp, "execute")

    g.section("Restart: a fresh race (RestartRace resumes the world itself)")
    ev = clicked(g, "RestartButton", 3)
    gm_ = g.call_static(GAMEPLAY, "GetGameMode", inputs=[Pin("WorldContextObject", OBJECT, hidden=True)],
                        outputs=[obj_pin("ReturnValue", "/Script/Engine.GameModeBase", "out")], pure=True)
    gm = g.cast(GMC)
    g.link(gm_, "ReturnValue", gm, "Object")
    g.exec(ev, gm)
    pc2 = g.cast(PCC)
    g.link(owning_player(g), "ReturnValue", pc2, "Object")
    g.link(gm, "then", pc2, "execute")
    tp2 = g.call_on(PCC, "TogglePause")  # drops the menu and the cursor; the restart below keeps the world running
    g.link(pc2, as_pin(BP_PC), tp2, "self")
    g.link(pc2, "then", tp2, "execute")
    rs = g.call_on(GMC, "RestartRace")
    g.link(gm, as_pin(BP_GM), rs, "self")
    g.exec(tp2, rs)
    g.link(pc2, "CastFailed", rs, "execute")

    g.section("Main menu: resume the world, then back to the menu")
    ev = clicked(g, "MenuButton", 5)
    unp = g.call_static(GAMEPLAY, "SetGamePaused", inputs=[Pin("WorldContextObject", OBJECT, hidden=True), Pin("bPaused", BOOL, default="false")],
                        outputs=[Pin("ReturnValue", BOOL, "out")])
    g.exec(ev, unp)
    gi = game_instance(g)
    g.exec(unp, gi)
    back = g.call_on(GIC, "OpenMainMenu")
    g.link(gi, as_pin(BP_GI), back, "self")
    g.link(gi, "then", back, "execute")

    g.section("Quit: leave the game")
    ev = clicked(g, "QuitButton", 7)
    quit_game(g, (ev, "then"))
    return bp


# ---------- the menu level: GameMode and player controller ----------
MPCC = gen(BP_MENU_PC)
SLIDER = "/Script/UMG.Slider"
CAMERA_MANAGER = "/Script/Engine.PlayerCameraManager"
MN = "Dead Fire|Menu"


def gi_on(g, GI, fn, inputs=None, outputs=None, pure=False, **defaults):
    n = g.call_on(GIC, fn, inputs=inputs, outputs=outputs, pure=pure, **defaults)
    g.link(GI[0], GI[1], n, "self")
    return n


def vehicle_info(g, GI, index_src):
    n = gi_on(g, GI, "GetVehicleInfo", inputs=[Pin("Index", INT)],
              outputs=[Pin("Name", STRING, "out"), Pin("VehicleClass", CLASS, "out", cls_ref(gen(BP_VEHICLE))), Pin("UnlockLevel", INT, "out"),
                       Pin("Speed", INT, "out"), Pin("Acceleration", INT, "out"), Pin("Armor", INT, "out"), Pin("Boost", INT, "out"),
                       Pin("Description", STRING, "out")], pure=True)
    g.link(index_src[0], index_src[1], n, "Index")
    return n


def level_info(g, GI, index_src):
    n = gi_on(g, GI, "GetLevelInfo", inputs=[Pin("Index", INT)],
              outputs=[Pin("Name", STRING, "out"), Pin("MapName", NAME, "out"), Pin("Description", STRING, "out"),
                       Pin("ScoreRequirement", INT, "out"), Pin("TimeLimit", FLOAT, "out"), Pin("NPCCount", INT, "out")], pure=True)
    g.link(index_src[0], index_src[1], n, "Index")
    return n


def menu_pc(g, prev):
    """The owning player cast to BP_DFMenuPlayerController (impure); in the test world the cast fails and nothing happens."""
    c = g.cast(MPCC)
    g.link(owning_player(g), "ReturnValue", c, "Object")
    g.link(prev[0], prev[1], c, "execute")
    return c


def show_page(g, prev, asset):
    c = menu_pc(g, prev)
    n = g.call_on(MPCC, "ShowPage", inputs=[Pin("PageClass", CLASS, sub_object=cls_ref(USER_WIDGET), default_object=gen(asset))])
    g.link(c, as_pin(BP_MENU_PC), n, "self")
    g.link(c, "then", n, "execute")
    return n


def set_enabled(g, button_name, cond_src, prev):
    n = g.call_on(WIDGET, "SetIsEnabled", inputs=[Pin("bInIsEnabled", BOOL)])
    g.link(g.var_get(button_name, OBJECT, cls_ref(BUTTON)), button_name, n, "self")
    g.link(cond_src[0], cond_src[1], n, "bInIsEnabled")
    g.link(prev[0], prev[1], n, "execute")
    return n


def wrapped(props, width=480.0):
    """Text that wraps inside the left panel instead of running over the showcase."""
    props.update({"wrap_text_at": width})  # a fixed wrap width (AutoWrapText is shadowed by a deprecated property in Python)
    return props


def page_frame(bp, title, subtitle=None):
    """A translucent panel over the left third of the screen with a title; the cars stay visible to the right."""
    bp.widget("Panel", BORDER, None, {"brush_color": [0, 0, 0, 0.7]}, {"anchors": [0, 0, 0, 1], "position": [0, 0], "size": [560, 0]})
    bp.widget("Column", VBOX, None, slot={"anchors": [0, 0, 0, 0], "position": [40, 60], "auto_size": True})
    bp.widget("TitleText", TEXT_BLOCK, "Column", text_props(title, 48, AMBER), {"padding": [0, 0, 0, 6 if subtitle else 28]})
    if subtitle:
        bp.widget("SubtitleText", TEXT_BLOCK, "Column", text_props(subtitle, 28), {"padding": [0, 0, 0, 28]})


def nav_row(bp, confirm_name, confirm_label):
    bp.widget("NavRow", HBOX, "Column", slot={"padding": [0, 24, 0, 16]})
    bp.widget("LeftButton", BUTTON, "NavRow", slot={"padding": [0, 0, 12, 0]})
    bp.widget("LeftLabel", TEXT_BLOCK, "LeftButton", text_props("<", 28, DARK, "Center"))
    bp.widget("RightButton", BUTTON, "NavRow", slot={"padding": [0, 0, 24, 0]})
    bp.widget("RightLabel", TEXT_BLOCK, "RightButton", text_props(">", 28, DARK, "Center"))
    bp.widget(confirm_name, BUTTON, "NavRow")
    bp.widget(confirm_name[:-6] + "Label", TEXT_BLOCK, confirm_name, text_props(confirm_label, 28, DARK, "Center"))
    button(bp, "BackButton", "BACK", "Column", padding=(0, 0, 0, 0), size=24)


def wrap_step(g, prev, count_fn, delta):
    """Index = (Index + delta) mod count, then Refresh; returns the Refresh node."""
    gi = game_instance(g)
    g.link(prev[0], prev[1], gi, "execute")
    GI = (gi, as_pin(BP_GI))
    cnt = gi_on(g, GI, count_fn, outputs=[Pin("Count", INT, "out")], pure=True)
    add = math2(g, "Add_IntInt", INT)
    g.link(g.var_get("Index", INT), "Index", add, "A")
    if delta >= 0:
        add.pin("B").default = str(delta)
    else:
        minus = math2(g, "Add_IntInt", INT, b=str(delta))
        g.link(cnt, "Count", minus, "A")
        g.link(minus, "ReturnValue", add, "B")
    mod = g.call_static(MATH, "Percent_IntInt", inputs=[Pin("A", INT), Pin("B", INT)], outputs=[Pin("ReturnValue", INT, "out")], pure=True)
    g.link(add, "ReturnValue", mod, "A")
    g.link(cnt, "Count", mod, "B")
    st = g.var_set("Index", INT)
    g.link(mod, "ReturnValue", st, "Index")
    g.link(gi, "then", st, "execute")
    rf = g.call_self("Refresh")
    g.exec(st, rf)
    return rf


def construct_index(g, selected_var):
    """Construct: Index from the GameInstance's selection, then Refresh."""
    g.section("Construct: start on the selected entry")
    ev = g.event(USER_WIDGET, "Construct")
    gi = game_instance(g)
    g.exec(ev, gi)
    GI = (gi, as_pin(BP_GI))
    sel = g.var_get_on(GIC, selected_var, INT)
    g.link(GI[0], GI[1], sel, "self")
    st = g.var_set("Index", INT)
    g.link(sel, selected_var, st, "Index")
    g.link(gi, "then", st, "execute")
    rf = g.call_self("Refresh")
    g.exec(st, rf)
    g.link(gi, "CastFailed", rf, "execute")


def build_main_menu() -> WidgetBlueprint:
    bp = WidgetBlueprint(WBP_MAIN_MENU, description="The main menu: PLAY, SETTINGS, QUIT and how much is unlocked.")
    page_frame(bp, "DEAD FIRE", "\u6b7b\u706b")
    button(bp, "PlayButton", "PLAY", "Column")
    button(bp, "SettingsButton", "SETTINGS", "Column")
    button(bp, "QuitButton", "QUIT", "Column", padding=(0, 0, 0, 28))
    bp.widget("FooterText", TEXT_BLOCK, "Column", text_props("CARS 1 / 3   TRACKS 1 / 2", 20))
    add_text_helpers(bp)

    g = bp.function("Refresh", doc="The footer: how many cars and tracks are open.")
    gi = game_instance(g)
    g.link_entry("then", gi, "execute")
    GI = (gi, as_pin(BP_GI))
    cars = gi_on(g, GI, "CountUnlockedVehicles", outputs=[Pin("Count", INT, "out")])
    g.link(gi, "then", cars, "execute")
    tracks = gi_on(g, GI, "CountUnlockedLevels", outputs=[Pin("Count", INT, "out")])
    g.exec(cars, tracks)
    total_cars = gi_on(g, GI, "GetVehicleCount", outputs=[Pin("Count", INT, "out")], pure=True)
    total_tracks = gi_on(g, GI, "GetLevelCount", outputs=[Pin("Count", INT, "out")], pure=True)
    label(g, "FooterText", cat(g, "CARS ", s_int(g, (cars, "Count")), " / ", s_int(g, (total_cars, "Count")),
                              "   TRACKS ", s_int(g, (tracks, "Count")), " / ", s_int(g, (total_tracks, "Count"))), (tracks, "then"))

    g = bp.event_graph()
    g.section("Construct: fill the footer")
    ev = g.event(USER_WIDGET, "Construct")
    g.exec(ev, g.call_self("Refresh"))
    g.section("Play: the car page")
    show_page(g, (clicked(g, "PlayButton", 3), "then"), WBP_VEHICLE_SELECT)
    g.section("Settings page")
    show_page(g, (clicked(g, "SettingsButton", 5), "then"), WBP_SETTINGS)
    g.section("Quit: leave the game")
    quit_game(g, (clicked(g, "QuitButton", 7), "then"))
    return bp


def build_vehicle_select() -> WidgetBlueprint:
    bp = WidgetBlueprint(WBP_VEHICLE_SELECT, description="The car page: stats, description and lock state of each car; < > NEXT BACK.")
    page_frame(bp, "CHOOSE YOUR CAR")
    bp.widget("NameText", TEXT_BLOCK, "Column", text_props("SEDAN", 40), {"padding": [0, 0, 0, 12]})
    for name, text in (("SpeedText", "TOP SPEED     [###--]"), ("AccelText", "ACCELERATION  [###--]"),
                       ("ArmorText", "ARMOR         [###--]"), ("BoostText", "BOOST         [###--]")):
        bp.widget(name, TEXT_BLOCK, "Column", text_props(text, 22), {"padding": [0, 0, 0, 4]})
    bp.widget("DescriptionText", TEXT_BLOCK, "Column", wrapped(text_props("", 20)), {"padding": [0, 12, 0, 8]})
    bp.widget("LockText", TEXT_BLOCK, "Column", wrapped(text_props("", 22, AMBER)), {"padding": [0, 0, 0, 4]})
    nav_row(bp, "ConfirmButton", "NEXT")
    bp.variable("Index", "int", "0", MN)
    add_text_helpers(bp)

    g = bp.function("Bar", doc="Five cells: [###--] for 3.", inputs=["Value:int"], outputs=["Text:string"], pure=True)
    prev = ("entry", "then")
    for v in range(0, 5):
        eq = compare(g, "EqualEqual_IntInt", INT, b=str(v))
        g.link_entry("Value", eq, "A")
        b = g.branch()
        g.link(eq, "ReturnValue", b, "Condition")
        g.link(prev[0], prev[1], b, "execute")
        r = g.function_result([Pin("Text", STRING, default="[" + "#" * v + "-" * (5 - v) + "]")])
        g.link(b, "then", r, "execute")
        prev = (b, "else")
    r = g.function_result([Pin("Text", STRING, default="[#####]")])
    g.link(prev[0], prev[1], r, "execute")

    g = bp.function("Refresh", doc="Fills the page for Index and moves the showcase camera to that car.")
    gi = game_instance(g)
    g.link_entry("then", gi, "execute")
    GI = (gi, as_pin(BP_GI))
    idx = (g.var_get("Index", INT), "Index")
    info = vehicle_info(g, GI, idx)

    def bar(pin):
        n = g.call_self("Bar", inputs=[Pin("Value", INT)], outputs=[Pin("Text", STRING, "out")], pure=True)
        g.link(info, pin, n, "Value")
        return (n, "Text")

    n = label(g, "NameText", (info, "Name"), (gi, "then"))
    n = label(g, "SpeedText", cat(g, "TOP SPEED     ", bar("Speed")), (n, "then"))
    n = label(g, "AccelText", cat(g, "ACCELERATION  ", bar("Acceleration")), (n, "then"))
    n = label(g, "ArmorText", cat(g, "ARMOR         ", bar("Armor")), (n, "then"))
    n = label(g, "BoostText", cat(g, "BOOST         ", bar("Boost")), (n, "then"))
    n = label(g, "DescriptionText", (info, "Description"), (n, "then"))
    unlocked = gi_on(g, GI, "IsVehicleUnlocked", inputs=[Pin("Index", INT)], outputs=[Pin("ReturnValue", BOOL, "out")], pure=True)
    g.link(idx[0], idx[1], unlocked, "Index")
    where = level_info(g, GI, (info, "UnlockLevel"))
    n = label(g, "LockText", pick(g, "", cat(g, "LOCKED  -  FINISH 1ST ON ", (where, "Name")), (unlocked, "ReturnValue")), (n, "then"))
    n = set_enabled(g, "ConfirmButton", (unlocked, "ReturnValue"), (n, "then"))
    c = menu_pc(g, (n, "then"))
    sv = g.call_on(MPCC, "ShowVehicle", inputs=[Pin("Index", INT)])
    g.link(c, as_pin(BP_MENU_PC), sv, "self")
    g.link(idx[0], idx[1], sv, "Index")
    g.link(c, "then", sv, "execute")

    g = bp.function("SelectNext", doc="The next car, wrapping.")
    wrap_step(g, ("entry", "then"), "GetVehicleCount", 1)
    g = bp.function("SelectPrevious", doc="The previous car, wrapping.")
    wrap_step(g, ("entry", "then"), "GetVehicleCount", -1)

    g = bp.function("Confirm", doc="Stores the car when it is open and moves on to the track page.")
    gi = game_instance(g)
    g.link_entry("then", gi, "execute")
    GI = (gi, as_pin(BP_GI))
    unlocked = gi_on(g, GI, "IsVehicleUnlocked", inputs=[Pin("Index", INT)], outputs=[Pin("ReturnValue", BOOL, "out")], pure=True)
    g.link(g.var_get("Index", INT), "Index", unlocked, "Index")
    b = g.branch()
    g.link(unlocked, "ReturnValue", b, "Condition")
    g.link(gi, "then", b, "execute")
    st = g.var_set_on(GIC, "SelectedVehicle", INT)
    g.link(GI[0], GI[1], st, "self")
    g.link(g.var_get("Index", INT), "Index", st, "SelectedVehicle")
    g.link(b, "then", st, "execute")
    show_page(g, (st, "then"), WBP_LEVEL_SELECT)

    g = bp.event_graph()
    construct_index(g, "SelectedVehicle")
    g.section("Previous car")
    g.exec(clicked(g, "LeftButton", 3), g.call_self("SelectPrevious"))
    g.section("Next car")
    g.exec(clicked(g, "RightButton", 5), g.call_self("SelectNext"))
    g.section("Confirm: on to the tracks")
    g.exec(clicked(g, "ConfirmButton", 7), g.call_self("Confirm"))
    g.section("Back: the main menu")
    show_page(g, (clicked(g, "BackButton", 9), "then"), WBP_MAIN_MENU)
    return bp


def build_level_select() -> WidgetBlueprint:
    bp = WidgetBlueprint(WBP_LEVEL_SELECT, description="The track page: description, rules, best result and lock state of each track; < > RACE BACK.")
    page_frame(bp, "CHOOSE A TRACK")
    bp.widget("NameText", TEXT_BLOCK, "Column", text_props("PROVING GROUND", 40), {"padding": [0, 0, 0, 12]})
    bp.widget("DescriptionText", TEXT_BLOCK, "Column", wrapped(text_props("", 20)), {"padding": [0, 0, 0, 12]})
    bp.widget("RulesText", TEXT_BLOCK, "Column", text_props("PASS 300   CLOCK 120 s   RIVALS 3", 22), {"padding": [0, 0, 0, 4]})
    bp.widget("BestText", TEXT_BLOCK, "Column", text_props("NOT RACED YET", 22), {"padding": [0, 0, 0, 8]})
    bp.widget("LockText", TEXT_BLOCK, "Column", wrapped(text_props("", 22, AMBER)), {"padding": [0, 0, 0, 4]})
    nav_row(bp, "RaceButton", "RACE")
    bp.variable("Index", "int", "0", MN)
    add_text_helpers(bp)

    g = bp.function("Refresh", doc="Fills the page for Index: rules, best result, lock state.")
    gi = game_instance(g)
    g.link_entry("then", gi, "execute")
    GI = (gi, as_pin(BP_GI))
    idx = (g.var_get("Index", INT), "Index")
    info = level_info(g, GI, idx)
    n = label(g, "NameText", (info, "Name"), (gi, "then"))
    n = label(g, "DescriptionText", (info, "Description"), (n, "then"))
    secs = g.call_static(MATH, "FTrunc", inputs=[Pin("A", FLOAT)], outputs=[Pin("ReturnValue", INT, "out")], pure=True)
    g.link(info, "TimeLimit", secs, "A")
    rivals = gi_on(g, GI, "GetNPCCountFor", inputs=[Pin("LevelCount", INT)], outputs=[Pin("Count", INT, "out")], pure=True)
    g.link(info, "NPCCount", rivals, "LevelCount")
    n = label(g, "RulesText", cat(g, "PASS ", s_int(g, (info, "ScoreRequirement")), "   CLOCK ", s_int(g, (secs, "ReturnValue")), " s   RIVALS ",
                                 s_int(g, (rivals, "Count"))), (n, "then"))
    best = gi_on(g, GI, "GetBestScore", inputs=[Pin("Level", INT)], outputs=[Pin("Score", INT, "out")], pure=True)
    g.link(idx[0], idx[1], best, "Level")
    rank = gi_on(g, GI, "GetBestRank", inputs=[Pin("Level", INT)], outputs=[Pin("Rank", INT, "out")], pure=True)
    g.link(idx[0], idx[1], rank, "Level")
    has_score = compare(g, "Greater_IntInt", INT, b="0")
    g.link(best, "Score", has_score, "A")
    has_rank = compare(g, "Greater_IntInt", INT, b="0")
    g.link(rank, "Rank", has_rank, "A")
    raced = g.call_static(MATH, "BooleanOR", inputs=[Pin("A", BOOL), Pin("B", BOOL)], outputs=[Pin("ReturnValue", BOOL, "out")], pure=True)
    g.link(has_score, "ReturnValue", raced, "A")
    g.link(has_rank, "ReturnValue", raced, "B")
    place = pick(g, s_int(g, (rank, "Rank")), "-", (has_rank, "ReturnValue"))
    n = label(g, "BestText", pick(g, cat(g, "BEST ", s_int(g, (best, "Score")), "   PLACE ", place), "NOT RACED YET", (raced, "ReturnValue")), (n, "then"))
    unlocked = gi_on(g, GI, "IsLevelUnlocked", inputs=[Pin("Index", INT)], outputs=[Pin("ReturnValue", BOOL, "out")], pure=True)
    g.link(idx[0], idx[1], unlocked, "Index")
    prev_i = math2(g, "Subtract_IntInt", INT, b="1")
    g.link(idx[0], idx[1], prev_i, "A")
    prev_info = level_info(g, GI, (prev_i, "ReturnValue"))
    n = label(g, "LockText", pick(g, "", cat(g, "LOCKED  -  PASS ", (prev_info, "Name")), (unlocked, "ReturnValue")), (n, "then"))
    set_enabled(g, "RaceButton", (unlocked, "ReturnValue"), (n, "then"))

    g = bp.function("SelectNext", doc="The next track, wrapping.")
    wrap_step(g, ("entry", "then"), "GetLevelCount", 1)
    g = bp.function("SelectPrevious", doc="The previous track, wrapping.")
    wrap_step(g, ("entry", "then"), "GetLevelCount", -1)

    g = bp.function("Confirm", doc="Stores the track when it is open and starts the race.")
    gi = game_instance(g)
    g.link_entry("then", gi, "execute")
    GI = (gi, as_pin(BP_GI))
    unlocked = gi_on(g, GI, "IsLevelUnlocked", inputs=[Pin("Index", INT)], outputs=[Pin("ReturnValue", BOOL, "out")], pure=True)
    g.link(g.var_get("Index", INT), "Index", unlocked, "Index")
    b = g.branch()
    g.link(unlocked, "ReturnValue", b, "Condition")
    g.link(gi, "then", b, "execute")
    st = g.var_set_on(GIC, "SelectedLevel", INT)
    g.link(GI[0], GI[1], st, "self")
    g.link(g.var_get("Index", INT), "Index", st, "SelectedLevel")
    g.link(b, "then", st, "execute")
    go = gi_on(g, GI, "StartRace")
    g.exec(st, go)

    g = bp.event_graph()
    construct_index(g, "SelectedLevel")
    g.section("Previous track")
    g.exec(clicked(g, "LeftButton", 3), g.call_self("SelectPrevious"))
    g.section("Next track")
    g.exec(clicked(g, "RightButton", 5), g.call_self("SelectNext"))
    g.section("Race!")
    g.exec(clicked(g, "RaceButton", 7), g.call_self("Confirm"))
    g.section("Back: the car page")
    show_page(g, (clicked(g, "BackButton", 9), "then"), WBP_VEHICLE_SELECT)
    return bp


def build_settings() -> WidgetBlueprint:
    bp = WidgetBlueprint(WBP_SETTINGS, description="Settings: master volume, difficulty, display mode, reset progress.")
    page_frame(bp, "SETTINGS")
    bp.widget("VolumeLabel", TEXT_BLOCK, "Column", text_props("MASTER VOLUME", 22), {"padding": [0, 0, 0, 6]})
    bp.widget("VolumeRow", HBOX, "Column", slot={"padding": [0, 0, 0, 24]})
    bp.widget("VolumeBox", SIZEBOX, "VolumeRow", {"width_override": 320, "height_override": 28}, {"v_align": "Center"})
    bp.widget("VolumeSlider", SLIDER, "VolumeBox", {"min_value": 0.0, "max_value": 1.0, "step_size": 0.05, "value": 1.0})
    bp.widget("VolumeText", TEXT_BLOCK, "VolumeRow", text_props("100 %", 22), {"padding": [16, 0, 0, 0], "v_align": "Center"})
    bp.widget("DifficultyLabel", TEXT_BLOCK, "Column", text_props("DIFFICULTY", 22), {"padding": [0, 0, 0, 6]})
    bp.widget("DiffRow", HBOX, "Column", slot={"padding": [0, 0, 0, 6]})
    bp.widget("DiffLeftButton", BUTTON, "DiffRow")
    bp.widget("DiffLeftLabel", TEXT_BLOCK, "DiffLeftButton", text_props("<", 24, DARK, "Center"))
    bp.widget("DifficultyText", TEXT_BLOCK, "DiffRow", text_props("NORMAL", 28, justify="Center"), {"padding": [16, 0, 16, 0], "v_align": "Center"})
    bp.widget("DiffRightButton", BUTTON, "DiffRow")
    bp.widget("DiffRightLabel", TEXT_BLOCK, "DiffRightButton", text_props(">", 24, DARK, "Center"))
    bp.widget("DifficultyHint", TEXT_BLOCK, "Column", wrapped(text_props("EASY 2, NORMAL 3, HARD 5 RIVALS ON PROVING GROUND", 16)), {"padding": [0, 0, 0, 24]})
    button(bp, "ModeButton", "WINDOWED", "Column")
    button(bp, "ResetButton", "RESET PROGRESS", "Column", padding=(0, 0, 0, 28))
    button(bp, "BackButton", "BACK", "Column", padding=(0, 0, 0, 0), size=24)
    add_text_helpers(bp)

    def volume_text(g, GI, prev):
        vol = gi_on(g, GI, "GetMasterVolume", outputs=[Pin("Volume", FLOAT, "out")], pure=True)
        pct = math2(g, "Multiply_FloatFloat", FLOAT, b="100.0")
        g.link(vol, "Volume", pct, "A")
        rounded = g.call_static(MATH, "Round", inputs=[Pin("A", FLOAT)], outputs=[Pin("ReturnValue", INT, "out")], pure=True)
        g.link(pct, "ReturnValue", rounded, "A")
        return label(g, "VolumeText", cat(g, s_int(g, (rounded, "ReturnValue")), " %"), prev), vol

    g = bp.function("Refresh", doc="Slider, labels and the display mode from the saved settings.")
    gi = game_instance(g)
    g.link_entry("then", gi, "execute")
    GI = (gi, as_pin(BP_GI))
    n, vol = volume_text(g, GI, (gi, "then"))
    sv = g.call_on(SLIDER, "SetValue", inputs=[Pin("InValue", FLOAT)])
    g.link(g.var_get("VolumeSlider", OBJECT, cls_ref(SLIDER)), "VolumeSlider", sv, "self")
    g.link(vol, "Volume", sv, "InValue")
    g.exec(n, sv)
    dn = gi_on(g, GI, "GetDifficultyName", outputs=[Pin("Name", STRING, "out")], pure=True)
    n = label(g, "DifficultyText", (dn, "Name"), (sv, "then"))
    full = gi_on(g, GI, "IsFullscreen", outputs=[Pin("ReturnValue", BOOL, "out")], pure=True)
    label(g, "ModeLabel", pick(g, "FULLSCREEN", "WINDOWED", (full, "ReturnValue")), (n, "then"))

    def step_difficulty(g, delta):
        gi = game_instance(g)
        g.link_entry("then", gi, "execute")
        GI = (gi, as_pin(BP_GI))
        cur = gi_on(g, GI, "GetDifficulty", outputs=[Pin("Difficulty", INT, "out")], pure=True)
        add = math2(g, "Add_IntInt", INT, b=str(delta))
        g.link(cur, "Difficulty", add, "A")
        mod = g.call_static(MATH, "Percent_IntInt", inputs=[Pin("A", INT), Pin("B", INT, default="3")], outputs=[Pin("ReturnValue", INT, "out")], pure=True)
        g.link(add, "ReturnValue", mod, "A")
        sd = gi_on(g, GI, "SetDifficulty", inputs=[Pin("Difficulty", INT)])
        g.link(mod, "ReturnValue", sd, "Difficulty")
        g.link(gi, "then", sd, "execute")
        g.exec(sd, g.call_self("Refresh"))

    g = bp.function("EasierDifficulty", doc="One step down (wrapping).")
    step_difficulty(g, 2)
    g = bp.function("HarderDifficulty", doc="One step up (wrapping).")
    step_difficulty(g, 1)

    g = bp.event_graph()
    g.section("Construct: show the saved settings")
    g.exec(g.event(USER_WIDGET, "Construct"), g.call_self("Refresh"))
    g.section("Volume slider: save and apply as it moves")
    ev = g.component_event("VolumeSlider", "OnValueChanged", SLIDER, [Pin("Value", FLOAT)], "OnFloatValueChangedEvent__DelegateSignature", UMG, col=0, row=2)
    gi = game_instance(g)
    g.exec(ev, gi)
    GI = (gi, as_pin(BP_GI))
    smv = gi_on(g, GI, "SetMasterVolume", inputs=[Pin("Volume", FLOAT)])
    g.link(ev, "Value", smv, "Volume")
    g.link(gi, "then", smv, "execute")
    volume_text(g, GI, (smv, "then"))
    g.section("Difficulty down")
    g.exec(clicked(g, "DiffLeftButton", 4), g.call_self("EasierDifficulty"))
    g.section("Difficulty up")
    g.exec(clicked(g, "DiffRightButton", 6), g.call_self("HarderDifficulty"))
    g.section("Display: windowed or fullscreen")
    ev = clicked(g, "ModeButton", 8)
    gi = game_instance(g)
    g.exec(ev, gi)
    tf = gi_on(g, (gi, as_pin(BP_GI)), "ToggleFullscreen")
    g.link(gi, "then", tf, "execute")
    g.exec(tf, g.call_self("Refresh"))
    g.section("Reset progress")
    ev = clicked(g, "ResetButton", 10)
    gi = game_instance(g)
    g.exec(ev, gi)
    rp = gi_on(g, (gi, as_pin(BP_GI)), "ResetProgress")
    g.link(gi, "then", rp, "execute")
    label(g, "ResetLabel", cat(g, "PROGRESS RESET"), (rp, "then"))
    g.section("Back: the main menu")
    show_page(g, (clicked(g, "BackButton", 12), "then"), WBP_MAIN_MENU)
    return bp


def build_menu_game_mode() -> Blueprint:
    bp = Blueprint(BP_MENU_GM, parent=GAME_MODE_BASE, description="The main menu level's GameMode: no pawn, the menu player controller, the audio mix applied.")
    bp.default("PlayerControllerClass", "class:" + BP_MENU_PC)
    bp.default("DefaultPawnClass", None)
    g = bp.event_graph()
    g.section("Begin Play: apply the saved audio settings")
    bpl = g.begin_play()
    par = g.call_parent(GAME_MODE_BASE, "ReceiveBeginPlay")
    gi = game_instance(g)
    g.exec(bpl, par, gi)
    au = gi_on(g, (gi, as_pin(BP_GI)), "ApplyAudioSettings")
    g.link(gi, "then", au, "execute")
    return bp


def build_menu_controller() -> Blueprint:
    bp = Blueprint(BP_MENU_PC, parent=PLAYER_CONTROLLER, description="The menu's player controller: cursor and UI input, the page on screen, the showcase cameras.")
    bp.variable("CurrentPage", "object:" + USER_WIDGET, "", MN)
    bp.variable("ShowcaseCameras", "array<object:%s>" % CAMERA_ACTOR, "", MN)
    bp.variable("BlendSeconds", "float", "0.5", MN, editable=True)
    cam_elem = Pin("e", OBJECT, sub_object=cls_ref(CAMERA_ACTOR))

    g = bp.function("FindShowcaseCameras", doc="ShowcaseCameras[k] = the CameraActor tagged Showcase<k>, k = 0..2.")
    clr = g.call_array(ARR, "Array_Clear", cam_elem, pure=False)
    g.link(g.var_get("ShowcaseCameras", OBJECT, cls_ref(CAMERA_ACTOR), container="Array"), "ShowcaseCameras", clr, "TargetArray")
    g.link_entry("then", clr, "execute")
    loop = g.for_loop()
    loop.pin("LastIndex").default = "2"
    g.exec(clr, loop)
    tag_s = cat(g, "Showcase", s_int(g, (loop, "Index")))
    tag = g.call_static("KismetStringLibrary", "Conv_StringToName", inputs=[Pin("InString", STRING)], outputs=[Pin("ReturnValue", NAME, "out")], pure=True)
    g.link(tag_s[0], tag_s[1], tag, "InString")
    found = g.call_static(GAMEPLAY, "GetAllActorsOfClassWithTag",
                          inputs=[Pin("WorldContextObject", OBJECT, hidden=True),
                                  Pin("ActorClass", CLASS, sub_object=cls_ref(ACTOR), default_object=CAMERA_ACTOR), Pin("Tag", NAME)],
                          outputs=[Pin("OutActors", OBJECT, "out", cls_ref(ACTOR), container="Array")])
    g.link(tag, "ReturnValue", found, "Tag")
    g.link(loop, "LoopBody", found, "execute")
    ln = g.call_array(ARR, "Array_Length", Pin("e", OBJECT, sub_object=cls_ref(ACTOR)), outputs=[Pin("ReturnValue", INT, "out")])
    g.link(found, "OutActors", ln, "TargetArray")
    some = compare(g, "Greater_IntInt", INT, b="0")
    g.link(ln, "ReturnValue", some, "A")
    b = g.branch()
    g.link(some, "ReturnValue", b, "Condition")
    g.exec(found, b)
    first = g.call_array(ARR, "Array_Get", Pin("e", OBJECT, sub_object=cls_ref(ACTOR)), inputs=[Pin("Index", INT, default="0")],
                         outputs=[Pin("Item", OBJECT, "out", cls_ref(ACTOR))])
    g.link(found, "OutActors", first, "TargetArray")
    cast = g.cast(CAMERA_ACTOR)
    g.link(first, "Item", cast, "Object")
    g.link(b, "then", cast, "execute")
    add = g.call_array(ARR, "Array_Add", cam_elem, inputs=[Pin("NewItem", OBJECT, "in", cls_ref(CAMERA_ACTOR))], outputs=[Pin("ReturnValue", INT, "out")], pure=False)
    g.link(g.var_get("ShowcaseCameras", OBJECT, cls_ref(CAMERA_ACTOR), container="Array"), "ShowcaseCameras", add, "TargetArray")
    g.link(cast, as_pin(CAMERA_ACTOR), add, "NewItem")
    g.link(cast, "then", add, "execute")

    def view_camera(g, index_src, blend_src, prev):
        arr = g.var_get("ShowcaseCameras", OBJECT, cls_ref(CAMERA_ACTOR), container="Array")
        ok = g.call_array(ARR, "Array_IsValidIndex", cam_elem, inputs=[Pin("IndexToTest", INT)], outputs=[Pin("ReturnValue", BOOL, "out")])
        g.link(arr, "ShowcaseCameras", ok, "TargetArray")
        g.link(index_src[0], index_src[1], ok, "IndexToTest")
        b = g.branch()
        g.link(ok, "ReturnValue", b, "Condition")
        g.link(prev[0], prev[1], b, "execute")
        get = g.call_array(ARR, "Array_Get", cam_elem, inputs=[Pin("Index", INT)], outputs=[Pin("Item", OBJECT, "out", cls_ref(CAMERA_ACTOR))])
        g.link(g.var_get("ShowcaseCameras", OBJECT, cls_ref(CAMERA_ACTOR), container="Array"), "ShowcaseCameras", get, "TargetArray")
        g.link(index_src[0], index_src[1], get, "Index")
        vt = g.call_self_native(PLAYER_CONTROLLER, "SetViewTargetWithBlend",
                                inputs=[obj_pin("NewViewTarget", ACTOR), Pin("BlendTime", FLOAT, default="0.0"),
                                        native_enum_pin("BlendFunc", "/Script/Engine.EViewTargetBlendFunction", "VTBlend_Cubic"),
                                        Pin("BlendExp", FLOAT, default="0.0"), Pin("bLockOutgoing", BOOL, default="false")])
        g.link(get, "Item", vt, "NewViewTarget")
        if blend_src is not None:
            g.link(blend_src[0], blend_src[1], vt, "BlendTime")
        g.link(b, "then", vt, "execute")
        return b

    g = bp.function("ShowVehicle", doc="Blends the view to the showcase camera of car Index.", inputs=["Index:int"])
    view_camera(g, ("entry", "Index"), (g.var_get("BlendSeconds", FLOAT), "BlendSeconds"), ("entry", "then"))
    g = bp.function("SnapToVehicle", doc="Cuts the view to the showcase camera of car Index (Begin Play).", inputs=["Index:int"])
    view_camera(g, ("entry", "Index"), None, ("entry", "then"))

    g = bp.function("ShowPage", doc="Replaces the page on screen with a new widget of PageClass.", inputs=["PageClass:class:" + USER_WIDGET])
    cur = g.var_get("CurrentPage", OBJECT, cls_ref(USER_WIDGET))
    has = is_valid(g)
    g.link(cur, "CurrentPage", has, "Object")
    b = g.branch()
    g.link(has, "ReturnValue", b, "Condition")
    g.link_entry("then", b, "execute")
    rm = g.call_on(WIDGET, "RemoveFromParent")
    g.link(cur, "CurrentPage", rm, "self")
    g.link(b, "then", rm, "execute")
    cw = g.create_widget()
    g.link_entry("PageClass", cw, "Class")
    g.link(g.self_node(), "self", cw, "OwningPlayer")
    g.exec(rm, cw)
    g.link(b, "else", cw, "execute")
    st = g.var_set("CurrentPage", OBJECT, sub_object=cls_ref(USER_WIDGET))
    g.link(cw, "ReturnValue", st, "CurrentPage")
    g.exec(cw, st)
    add = g.call_on(USER_WIDGET, "AddToViewport", inputs=[Pin("ZOrder", INT, default="0")])
    g.link(cw, "ReturnValue", add, "self")
    g.exec(st, add)

    g = bp.event_graph()
    g.section("Begin Play: cursor and UI input, fade in, the cameras, the first page")
    bpl = g.begin_play()
    cur_on = g.var_set_on(PLAYER_CONTROLLER, "bShowMouseCursor", BOOL, default="true")
    g.link(g.self_node(), "self", cur_on, "self")
    g.exec(bpl, cur_on)
    ui = g.call_static("WidgetBlueprintLibrary", "SetInputMode_UIOnlyEx",
                       inputs=[obj_pin("PlayerController", PLAYER_CONTROLLER), obj_pin("InWidgetToFocus", WIDGET),
                               native_enum_pin("InMouseLockMode", "/Script/UMG.EMouseLockMode", "DoNotLock")], module="UMG")
    g.link(g.self_node(), "self", ui, "PlayerController")
    g.exec(cur_on, ui)
    cam = g.var_get_on(PLAYER_CONTROLLER, "PlayerCameraManager", OBJECT, cls_ref(CAMERA_MANAGER))
    g.link(g.self_node(), "self", cam, "self")
    fade = g.call_on(CAMERA_MANAGER, "StartCameraFade",
                     inputs=[Pin("FromAlpha", FLOAT, default="1.0"), Pin("ToAlpha", FLOAT, default="0.0"), Pin("Duration", FLOAT, default="0.5"),
                             struct_pin("Color", LINEAR_COLOR, default="(R=0.000000,G=0.000000,B=0.000000,A=1.000000)"),
                             Pin("bShouldFadeAudio", BOOL, default="false"), Pin("bHoldWhenFinished", BOOL, default="false")])
    g.link(cam, "PlayerCameraManager", fade, "self")
    g.exec(ui, fade)
    find = g.call_self("FindShowcaseCameras")
    g.exec(fade, find)
    gi = game_instance(g)
    g.exec(find, gi)
    GI = (gi, as_pin(BP_GI))
    sel = g.var_get_on(GIC, "SelectedVehicle", INT)
    g.link(GI[0], GI[1], sel, "self")
    snap = g.call_self("SnapToVehicle", inputs=[Pin("Index", INT)])
    g.link(sel, "SelectedVehicle", snap, "Index")
    g.link(gi, "then", snap, "execute")
    ret = g.var_get_on(GIC, "bReturnToVehicleSelect", BOOL)
    g.link(GI[0], GI[1], ret, "self")
    b = g.branch()
    g.note(b, "back from a race? then straight to the car page")
    g.link(ret, "bReturnToVehicleSelect", b, "Condition")
    g.exec(snap, b)
    clear = g.var_set_on(GIC, "bReturnToVehicleSelect", BOOL, default="false")
    g.link(GI[0], GI[1], clear, "self")
    g.link(b, "then", clear, "execute")
    cars = g.call_self("ShowPage", inputs=[Pin("PageClass", CLASS, sub_object=cls_ref(USER_WIDGET), default_object=gen(WBP_VEHICLE_SELECT))])
    g.exec(clear, cars)
    main = g.call_self("ShowPage", inputs=[Pin("PageClass", CLASS, sub_object=cls_ref(USER_WIDGET), default_object=gen(WBP_MAIN_MENU))])
    g.link(b, "else", main, "execute")
    snap0 = g.call_self("SnapToVehicle", inputs=[Pin("Index", INT, default="0")])
    g.link(gi, "CastFailed", snap0, "execute")
    g.exec(snap0, main)
    return bp


def build():
    return [build_pause(), build_main_menu(), build_vehicle_select(), build_level_select(), build_settings(),
            build_menu_game_mode(), build_menu_controller()]


if __name__ == "__main__":
    for b in build():
        print(b.write(OUT))
