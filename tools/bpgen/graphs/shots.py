"""Presentation captures (Phase 6, plan Task 6): FunctionalTest actors that take engine screenshots ("shot showui", the
game's own viewport only) of screens the functional-test level cannot show. They are NOT tests: the level builder
never places FT_DFShot_* in L_DF_FunctionalTests. A capture run places one in its level for the run only:

    FT_DFShot_Menu  in L_MainMenu:  main page, car page (SEDAN, BRUTE locked), track page (PROVING GROUND, SWITCHBACK
                                    locked), settings
    FT_DFShot_Pause in L_TestTrack: the race with its three rivals, then the pause menu over it

Both switch the GameInstance to a save slot that has no file (DeadFireShots), so every lock shows and the developer's
progress is neither read nor written. Images land in comp4900sef/Saved/Screenshots/Windows/.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, ".."))
from bpgen import CLASS, cls_ref  # noqa: E402
from df import (BP_MENU_PC, OBJECT, OUT, STRING, USER_WIDGET, WBP_LEVEL_SELECT, WBP_MAIN_MENU, WBP_PAUSE, WBP_SETTINGS,  # noqa: E402
                WBP_VEHICLE_SELECT, INT, Pin, as_pin, gen, get_player_controller, obj_pin)
from tests import T  # noqa: E402
from tests_menu import game_instance  # noqa: E402
from tests_ship import delete_slot, use_slot  # noqa: E402

MPCC = gen(BP_MENU_PC)
SLOT = "DeadFireShots"


def shot(t: T, settle=1.0):
    t.delay(settle)
    t.static("KismetSystemLibrary", "ExecuteConsoleCommand",
             inputs=[Pin("WorldContextObject", OBJECT, hidden=True), Pin("Command", STRING, default="shot showui"),
                     obj_pin("SpecificPlayer", "/Script/Engine.PlayerController")])
    t.delay(1.0)


def fresh_slot(t: T):
    gi = game_instance(t)
    delete_slot(t, SLOT)
    use_slot(t, gi, SLOT)
    return gi


def menu_pc(t: T):
    c = t.step(t.g.cast(MPCC))
    t.g.link(get_player_controller(t.g), "ReturnValue", c, "Object")
    return (c, as_pin(BP_MENU_PC))


def show_page(t: T, pc, asset):
    t.call(MPCC, "ShowPage", pc, inputs=[Pin("PageClass", CLASS, sub_object=cls_ref(USER_WIDGET), default_object=gen(asset))])


def current_page(t: T, pc, asset):
    c = t.step(t.g.cast(gen(asset)))
    t.link(t.get(MPCC, "CurrentPage", OBJECT, pc, sub=cls_ref(USER_WIDGET)), c, "Object")
    return (c, as_pin(asset))


def build():
    out = []

    t = T("FT_DFShot_Menu", "Presentation captures of the menu pages (placed in L_MainMenu for a capture run only).")
    fresh_slot(t)
    pc = menu_pc(t)
    show_page(t, pc, WBP_MAIN_MENU)  # again, so the footer counts the fresh slot
    shot(t, 1.5)
    show_page(t, pc, WBP_VEHICLE_SELECT)
    shot(t, 1.5)
    t.call(gen(WBP_VEHICLE_SELECT), "SelectNext", current_page(t, pc, WBP_VEHICLE_SELECT))
    shot(t, 1.5)  # BRUTE, locked; the camera has moved to its plinth
    show_page(t, pc, WBP_LEVEL_SELECT)
    shot(t, 1.0)
    t.call(gen(WBP_LEVEL_SELECT), "SelectNext", current_page(t, pc, WBP_LEVEL_SELECT))
    shot(t, 1.0)  # SWITCHBACK, locked
    show_page(t, pc, WBP_SETTINGS)
    shot(t, 1.0)
    show_page(t, pc, WBP_MAIN_MENU)
    delete_slot(t, SLOT)
    out.append(t.finish())

    t = T("FT_DFShot_Pause", "Presentation capture of the pause menu over a race (placed in L_TestTrack for a capture run only).")
    fresh_slot(t)
    t.delay(6.0)  # the three rivals pull away from the grid behind the parked player
    shot(t, 0.5)
    pw = t.step(t.g.create_widget(gen(WBP_PAUSE), result_class=gen(WBP_PAUSE)))
    t.g.link(get_player_controller(t.g), "ReturnValue", pw, "OwningPlayer")
    t.call(USER_WIDGET, "AddToViewport", (pw, "ReturnValue"), inputs=[Pin("ZOrder", INT, default="20")])
    shot(t, 0.5)  # the widget over a running world: a still looks the same as a paused one, and a paused world stalls every delay
    t.call("/Script/UMG.Widget", "RemoveFromParent", (pw, "ReturnValue"))
    delete_slot(t, SLOT)
    out.append(t.finish())
    return out


if __name__ == "__main__":
    for b in build():
        print(b.write(OUT))
