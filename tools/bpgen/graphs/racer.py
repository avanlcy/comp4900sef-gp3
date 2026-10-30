"""BPC_DFRacer and BP_DFPlayerController (plan Task 5; Phase 3 adds the item inventory to the racer).

The racer component holds per-racer race state and lives on the controller, so it survives vehicle respawns and
lets the GameMode rank NPC racers against the player. Phase 3 (spec §4): Inventory = up to MaxSlots stacks of
S_DFItemStack, SelectedSlot, and the pickup stamp the HUD flashes; the caps come in from the GameMode (GetItemInfo).
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from bpgen import struct_ref  # noqa: E402
from df import (BOOL, BP_CHARACTER, BP_CHECKPOINT, BP_PC, BP_VEHICLE, BPC_RACER, E_ITEM_TYPE, INT, ITEM_NONE, MATH,  # noqa: E402
                OBJECT, OUT, PAWN, PLAYER_CONTROLLER, S_ITEM_STACK, STRUCT, Blueprint, Graph, Node, Pin, as_pin,
                cast_to, cls_ref, compare, enum_pin, enum_spec, gen, math2, member, obj_pin, obj_spec, struct_path,
                struct_spec)
from df import BP_GS, CLASS, FLOAT, GAMEPLAY, LINEAR_COLOR, USER_WIDGET, WBP_PAUSE, is_valid, native_enum_pin, struct_pin  # noqa: E402  (Phase 5)

VC = gen(BP_VEHICLE)
ITEM = struct_path(S_ITEM_STACK)
STACK_PIN = ITEM.rsplit(".", 1)[1]
ENUM = enum_pin("x", E_ITEM_TYPE).sub_object  # pin sub-object text of the item enum
ARR = "KismetArrayLibrary"


# ---- inventory recipes ----
def stack_elem() -> Pin:
    return Pin("e", STRUCT, sub_object=struct_ref(ITEM))


def inventory(g: Graph) -> Node:
    return g.var_get("Inventory", STRUCT, struct_ref(ITEM), container="Array")


def inv_call(g: Graph, fn: str, inputs=None, outputs=None, pure=True) -> Node:
    """KismetArrayLibrary call with Inventory as the TargetArray."""
    n = g.call_array(ARR, fn, stack_elem(), inputs=inputs, outputs=outputs, pure=pure)
    g.link(inventory(g), "Inventory", n, "TargetArray")
    return n


def inv_length(g: Graph) -> Node:
    return inv_call(g, "Array_Length", outputs=[Pin("ReturnValue", INT, "out")])


def inv_get(g: Graph, index_src) -> Node:
    n = inv_call(g, "Array_Get", inputs=[Pin("Index", INT)], outputs=[Pin("Item", STRUCT, "out", struct_ref(ITEM))])
    g.link(index_src[0], index_src[1], n, "Index")
    return n


def break_stack(g: Graph, item_src) -> Node:
    n = g.break_struct(ITEM, [enum_pin(member(S_ITEM_STACK, "Type"), E_ITEM_TYPE, "out"),
                              Pin(member(S_ITEM_STACK, "Charges"), INT, "out")])
    g.link(item_src[0], item_src[1], n, STACK_PIN)
    return n


def make_stack(g: Graph, type_src, charges_src) -> Node:
    n = g.make_struct(ITEM, [enum_pin(member(S_ITEM_STACK, "Type"), E_ITEM_TYPE), Pin(member(S_ITEM_STACK, "Charges"), INT)])
    g.link(type_src[0], type_src[1], n, member(S_ITEM_STACK, "Type"))
    g.link(charges_src[0], charges_src[1], n, member(S_ITEM_STACK, "Charges"))
    return n


def inv_set(g: Graph, index_src, item_src) -> Node:
    n = inv_call(g, "Array_Set", inputs=[Pin("Index", INT), Pin("Item", STRUCT, sub_object=struct_ref(ITEM)),
                                         Pin("bSizeToFit", BOOL, default="false")], pure=False)
    g.link(index_src[0], index_src[1], n, "Index")
    g.link(item_src[0], item_src[1], n, "Item")
    return n


def int_min(g: Graph, a_src, b_src) -> Node:
    n = g.call_static(MATH, "Min", inputs=[Pin("A", INT), Pin("B", INT)], outputs=[Pin("ReturnValue", INT, "out")], pure=True)
    g.link(a_src[0], a_src[1], n, "A")
    g.link(b_src[0], b_src[1], n, "B")
    return n


def selected_in_range(g: Graph):
    """(branch node, SelectedSlot get node): the branch takes 'then' when SelectedSlot < Array_Length(Inventory)."""
    sel = g.var_get("SelectedSlot", INT)
    ln = inv_length(g)
    ok = compare(g, "Less_IntInt", INT)
    g.link(sel, "SelectedSlot", ok, "A")
    g.link(ln, "ReturnValue", ok, "B")
    b = g.branch()
    g.link(ok, "ReturnValue", b, "Condition")
    return b, sel


def add_inventory(bp: Blueprint) -> None:
    I = "Dead Fire|Items"
    bp.variable("Inventory", "array<%s>" % struct_spec(S_ITEM_STACK), "", I)
    bp.variable("SelectedSlot", "int", "0", I)
    bp.variable("MaxSlots", "int", "3", I, editable=True)
    bp.variable("LastPickupTime", "float", "-1", I)
    bp.variable("LastPickupType", enum_spec(E_ITEM_TYPE), "", I)

    # AddItem(Type, Charges, MaxCharges) -> bool: stack onto the slot of the same type (capped), else a new slot
    g = bp.function("AddItem", doc="Stacks onto the slot of the same type (capped) or takes a free slot; false when nothing was added.", inputs=["Type:" + enum_spec(E_ITEM_TYPE), "Charges:int", "MaxCharges:int"],
                    outputs=["ReturnValue:bool"], locals=["Index:int=-1", "Old:int=0"])
    loop = g.for_each(stack_elem())
    g.link(inventory(g), "Inventory", loop, "Array")
    g.link_entry("then", loop, "Exec")
    br = break_stack(g, (loop, "Array Element"))
    same = g.call_static(MATH, "EqualEqual_ByteByte", inputs=[Pin("A", "byte"), Pin("B", "byte")],
                         outputs=[Pin("ReturnValue", BOOL, "out")], pure=True)
    g.link(br, member(S_ITEM_STACK, "Type"), same, "A")
    g.link_entry("Type", same, "B")
    b = g.branch()
    g.link(same, "ReturnValue", b, "Condition")
    g.link(loop, "LoopBody", b, "execute")
    si = g.local_set("Index", INT)
    g.link(loop, "Array Index", si, "Index")
    so = g.local_set("Old", INT)
    g.link(br, member(S_ITEM_STACK, "Charges"), so, "Old")
    g.link(b, "then", si, "execute")
    g.exec(si, so)
    idx = g.local_get("Index", INT)
    found = compare(g, "GreaterEqual_IntInt", INT, b="0")
    g.link(idx, "Index", found, "A")
    bf = g.branch()
    g.link(found, "ReturnValue", bf, "Condition")
    g.link(loop, "Completed", bf, "execute")
    old = g.local_get("Old", INT)
    total = math2(g, "Add_IntInt", INT)
    g.link(old, "Old", total, "A")
    g.link_entry("Charges", total, "B")
    new = int_min(g, (total, "ReturnValue"), ("entry", "MaxCharges"))
    mk = make_stack(g, ("entry", "Type"), (new, "ReturnValue"))
    idx2 = g.local_get("Index", INT)
    st = inv_set(g, (idx2, "Index"), (mk, STACK_PIN))
    g.link(bf, "then", st, "execute")
    grew = compare(g, "Greater_IntInt", INT)
    g.link(new, "ReturnValue", grew, "A")
    old2 = g.local_get("Old", INT)
    g.link(old2, "Old", grew, "B")
    r1 = g.function_result([Pin("ReturnValue", BOOL)])
    g.link(grew, "ReturnValue", r1, "ReturnValue")
    g.exec(st, r1)
    ln = inv_length(g)
    mx = g.var_get("MaxSlots", INT)
    room = compare(g, "Less_IntInt", INT)
    g.link(ln, "ReturnValue", room, "A")
    g.link(mx, "MaxSlots", room, "B")
    br2 = g.branch()
    g.link(room, "ReturnValue", br2, "Condition")
    g.link(bf, "else", br2, "execute")
    capped = int_min(g, ("entry", "Charges"), ("entry", "MaxCharges"))
    mk2 = make_stack(g, ("entry", "Type"), (capped, "ReturnValue"))
    add = inv_call(g, "Array_Add", inputs=[Pin("NewItem", STRUCT, sub_object=struct_ref(ITEM))],
                   outputs=[Pin("ReturnValue", INT, "out")], pure=False)
    g.link(mk2, STACK_PIN, add, "NewItem")
    g.link(br2, "then", add, "execute")
    r_yes = g.function_result([Pin("ReturnValue", BOOL, default="true")])
    g.exec(add, r_yes)
    r_no = g.function_result([Pin("ReturnValue", BOOL, default="false")])
    g.link(br2, "else", r_no, "execute")

    # GetSelected() -> Type, Charges (None / 0 when the selection is empty)
    g = bp.function("GetSelected", doc="The selected stack (None / 0 when empty).", outputs=["Type:" + enum_spec(E_ITEM_TYPE), "Charges:int"], pure=True)
    b, sel = selected_in_range(g)
    g.link_entry("then", b, "execute")
    item = inv_get(g, (sel, "SelectedSlot"))
    br = break_stack(g, (item, "Item"))
    r = g.function_result([enum_pin("Type", E_ITEM_TYPE), Pin("Charges", INT)])
    g.link(br, member(S_ITEM_STACK, "Type"), r, "Type")
    g.link(br, member(S_ITEM_STACK, "Charges"), r, "Charges")
    g.link(b, "then", r, "execute")
    r0 = g.function_result([enum_pin("Type", E_ITEM_TYPE, default=ITEM_NONE), Pin("Charges", INT, default="0")])
    g.link(b, "else", r0, "execute")

    # ConsumeSelected() -> Type: one charge off the selected stack; an empty stack is removed and the selection reset
    g = bp.function("ConsumeSelected", doc="One charge off the selected stack; an empty stack is removed.", outputs=["Type:" + enum_spec(E_ITEM_TYPE)], locals=["Taken:" + enum_spec(E_ITEM_TYPE)])
    b, sel = selected_in_range(g)
    g.link_entry("then", b, "execute")
    r_none = g.function_result([enum_pin("Type", E_ITEM_TYPE, default=ITEM_NONE)])
    g.link(b, "else", r_none, "execute")
    item = inv_get(g, (sel, "SelectedSlot"))
    br = break_stack(g, (item, "Item"))
    st = g.local_set("Taken", "byte", sub_object=ENUM)
    g.link(br, member(S_ITEM_STACK, "Type"), st, "Taken")
    g.link(b, "then", st, "execute")
    left = math2(g, "Subtract_IntInt", INT, b="1")
    g.link(br, member(S_ITEM_STACK, "Charges"), left, "A")
    empty = compare(g, "LessEqual_IntInt", INT, b="0")
    g.link(left, "ReturnValue", empty, "A")
    b2 = g.branch()
    g.link(empty, "ReturnValue", b2, "Condition")
    g.exec(st, b2)
    rm = inv_call(g, "Array_Remove", inputs=[Pin("IndexToRemove", INT)], pure=False)
    sel2 = g.var_get("SelectedSlot", INT)
    g.link(sel2, "SelectedSlot", rm, "IndexToRemove")
    g.link(b2, "then", rm, "execute")
    zero = g.var_set("SelectedSlot", INT, default="0")
    g.exec(rm, zero)
    taken = g.local_get("Taken", "byte", sub_object=ENUM)
    r1 = g.function_result([enum_pin("Type", E_ITEM_TYPE)])
    g.link(taken, "Taken", r1, "Type")
    g.exec(zero, r1)
    taken2 = g.local_get("Taken", "byte", sub_object=ENUM)
    mk = make_stack(g, (taken2, "Taken"), (left, "ReturnValue"))
    sel3 = g.var_get("SelectedSlot", INT)
    setn = inv_set(g, (sel3, "SelectedSlot"), (mk, STACK_PIN))
    g.link(b2, "else", setn, "execute")
    taken3 = g.local_get("Taken", "byte", sub_object=ENUM)
    r2 = g.function_result([enum_pin("Type", E_ITEM_TYPE)])
    g.link(taken3, "Taken", r2, "Type")
    g.exec(setn, r2)

    # CycleSelected(): next slot, wrapping; 0 when empty
    g = bp.function("CycleSelected", doc="Next slot, wrapping.")
    ln = inv_length(g)
    some = compare(g, "Greater_IntInt", INT, b="0")
    g.link(ln, "ReturnValue", some, "A")
    b = g.branch()
    g.link(some, "ReturnValue", b, "Condition")
    g.link_entry("then", b, "execute")
    sel = g.var_get("SelectedSlot", INT)
    inc = math2(g, "Add_IntInt", INT, b="1")
    g.link(sel, "SelectedSlot", inc, "A")
    ln2 = inv_length(g)
    wrap = math2(g, "Percent_IntInt", INT)
    g.link(inc, "ReturnValue", wrap, "A")
    g.link(ln2, "ReturnValue", wrap, "B")
    sn = g.var_set("SelectedSlot", INT)
    g.link(wrap, "ReturnValue", sn, "SelectedSlot")
    g.link(b, "then", sn, "execute")
    s0 = g.var_set("SelectedSlot", INT, default="0")
    g.link(b, "else", s0, "execute")

    # Phase 4 (spec §3.2): the AI picks a stack by type
    g = bp.function("HasType", inputs=["Type:" + enum_spec(E_ITEM_TYPE)], outputs=["ReturnValue:bool"], pure=True,
                    doc="Whether the inventory holds a stack of this type.")
    loop = g.for_each(stack_elem())
    g.link(inventory(g), "Inventory", loop, "Array")
    g.link_entry("then", loop, "Exec")
    br = break_stack(g, (loop, "Array Element"))
    same = g.call_static(MATH, "EqualEqual_ByteByte", inputs=[Pin("A", "byte"), Pin("B", "byte")], outputs=[Pin("ReturnValue", BOOL, "out")], pure=True)
    g.link(br, member(S_ITEM_STACK, "Type"), same, "A")
    g.link_entry("Type", same, "B")
    b = g.branch()
    g.link(same, "ReturnValue", b, "Condition")
    g.link(loop, "LoopBody", b, "execute")
    g.link(b, "then", g.function_result([Pin("ReturnValue", BOOL, default="true")]), "execute")
    g.link(loop, "Completed", g.function_result([Pin("ReturnValue", BOOL, default="false")]), "execute")

    g = bp.function("SelectType", inputs=["Type:" + enum_spec(E_ITEM_TYPE)], outputs=["ReturnValue:bool"],
                    doc="Selects the stack of this type; false when the inventory has none.")
    loop = g.for_each(stack_elem())
    g.link(inventory(g), "Inventory", loop, "Array")
    g.link_entry("then", loop, "Exec")
    br = break_stack(g, (loop, "Array Element"))
    same = g.call_static(MATH, "EqualEqual_ByteByte", inputs=[Pin("A", "byte"), Pin("B", "byte")], outputs=[Pin("ReturnValue", BOOL, "out")], pure=True)
    g.link(br, member(S_ITEM_STACK, "Type"), same, "A")
    g.link_entry("Type", same, "B")
    b = g.branch()
    g.link(same, "ReturnValue", b, "Condition")
    g.link(loop, "LoopBody", b, "execute")
    sel = g.var_set("SelectedSlot", INT)
    g.link(loop, "Array Index", sel, "SelectedSlot")
    g.link(b, "then", sel, "execute")
    g.exec(sel, g.function_result([Pin("ReturnValue", BOOL, default="true")]))
    g.link(loop, "Completed", g.function_result([Pin("ReturnValue", BOOL, default="false")]), "execute")

    # ClearInventory()
    g = bp.function("ClearInventory", doc="Empties the inventory.")
    clear = inv_call(g, "Array_Clear", pure=False)
    g.link_entry("then", clear, "execute")
    s0 = g.var_set("SelectedSlot", INT, default="0")
    lp = g.var_set("LastPickupTime", "float", default="-1.0")
    g.exec(clear, s0, lp)


def build_racer() -> Blueprint:
    bp = Blueprint(BPC_RACER, parent="/Script/Engine.ActorComponent", description="Per-racer race state and the item inventory; lives on the controller (player or AI).")
    R = "Dead Fire|Race"
    bp.variable("Score", "int", "0", R, editable=True)
    bp.variable("LapsCompleted", "int", "0", R, editable=True)
    bp.variable("Kills", "int", "0", R, editable=True)
    bp.variable("Deaths", "int", "0", R, editable=True)
    bp.variable("Rank", "int", "0", R)  # Phase 4: 1-based place written by the GameMode's UpdateRanks (0 before the first pass)
    bp.variable("RespawnDueTime", "float", "-1", R)  # Phase 4: game time this racer comes back at; -1 = no respawn pending
    bp.variable("NextCheckpointIndex", "int", "1", R, editable=True)
    bp.variable("LastCheckpoint", obj_spec(BP_CHECKPOINT), "", R)
    bp.variable("LastCheckpointTime", "float", "-1", R)
    bp.variable("OffTrackSeconds", "float", "0", R)
    bp.variable("DistanceAlongTrack", "float", "0", R)
    bp.variable("RacerName", "text", "Player", R, editable=True)
    add_inventory(bp)
    return bp


def build_controller() -> Blueprint:
    bp = Blueprint(BP_PC, parent=PLAYER_CONTROLLER, description="The player's controller: possession between car and character; carries the racer.")
    bp.component("Racer", gen(BPC_RACER))
    S = "Dead Fire|State"
    bp.variable("OnFootCharacter", obj_spec(BP_CHARACTER), "", S)
    bp.variable("CurrentVehicle", obj_spec(BP_VEHICLE), "", S)  # the possessed car, empty on foot (HUD)
    bp.variable("LastVehicle", obj_spec(BP_VEHICLE), "", S)  # the last car possessed, kept on foot (respawn)
    # Phase 5 (spec 2026-10-30 phase 5 §5.3): the pause menu
    MN = "Dead Fire|Menu"
    bp.variable("PauseWidgetClass", "class:" + USER_WIDGET, "", MN, editable=True)
    bp.variable("PauseWidget", "object:" + USER_WIDGET, "", MN)
    bp.default("PauseWidgetClass", "class:" + WBP_PAUSE)

    g = bp.function("TogglePause", doc="Pauses the world with the pause menu up, or resumes; refused once the race is over (the summary owns the screen).")
    gs = g.call_static(GAMEPLAY, "GetGameState", inputs=[Pin("WorldContextObject", OBJECT, hidden=True)],
                       outputs=[obj_pin("ReturnValue", "/Script/Engine.GameStateBase", "out")], pure=True)
    cgs = g.cast(gen(BP_GS))
    g.link(gs, "ReturnValue", cgs, "Object")
    g.link_entry("then", cgs, "execute")
    active = g.var_get_on(gen(BP_GS), "bRaceActive", BOOL)
    g.link(cgs, as_pin(BP_GS), active, "self")
    bact = g.branch()
    g.note(bact, "no pause once the race is over")
    g.link(active, "bRaceActive", bact, "Condition")
    g.link(cgs, "then", bact, "execute")
    paused = g.call_static(GAMEPLAY, "IsGamePaused", inputs=[Pin("WorldContextObject", OBJECT, hidden=True)], outputs=[Pin("ReturnValue", BOOL, "out")], pure=True)
    bp_ = g.branch()
    g.note(bp_, "paused now? then resume")
    g.link(paused, "ReturnValue", bp_, "Condition")
    g.link(bact, "then", bp_, "execute")
    # resume
    pw = g.var_get("PauseWidget", OBJECT, cls_ref(USER_WIDGET))
    has = is_valid(g)
    g.link(pw, "PauseWidget", has, "Object")
    bw = g.branch()
    g.link(has, "ReturnValue", bw, "Condition")
    g.link(bp_, "then", bw, "execute")
    rm = g.call_on("/Script/UMG.Widget", "RemoveFromParent")
    g.link(pw, "PauseWidget", rm, "self")
    g.link(bw, "then", rm, "execute")
    clr = g.var_set("PauseWidget", OBJECT, sub_object=cls_ref(USER_WIDGET))
    g.exec(rm, clr)
    g.link(bw, "else", clr, "execute")
    unp = g.call_static(GAMEPLAY, "SetGamePaused", inputs=[Pin("WorldContextObject", OBJECT, hidden=True), Pin("bPaused", BOOL, default="false")],
                        outputs=[Pin("ReturnValue", BOOL, "out")])
    g.exec(clr, unp)
    cur_off = g.var_set_on(PLAYER_CONTROLLER, "bShowMouseCursor", BOOL, default="false")
    g.link(g.self_node(), "self", cur_off, "self")
    g.exec(unp, cur_off)
    gonly = g.call_static("WidgetBlueprintLibrary", "SetInputMode_GameOnly", inputs=[obj_pin("PlayerController", PLAYER_CONTROLLER)], module="UMG")
    g.link(g.self_node(), "self", gonly, "PlayerController")
    g.exec(cur_off, gonly)
    # pause
    pse = g.call_static(GAMEPLAY, "SetGamePaused", inputs=[Pin("WorldContextObject", OBJECT, hidden=True), Pin("bPaused", BOOL, default="true")],
                        outputs=[Pin("ReturnValue", BOOL, "out")])
    g.link(bp_, "else", pse, "execute")
    cw = g.create_widget()
    g.link(g.var_get("PauseWidgetClass", CLASS, cls_ref(USER_WIDGET)), "PauseWidgetClass", cw, "Class")
    g.link(g.self_node(), "self", cw, "OwningPlayer")
    g.exec(pse, cw)
    sw = g.var_set("PauseWidget", OBJECT, sub_object=cls_ref(USER_WIDGET))
    g.link(cw, "ReturnValue", sw, "PauseWidget")
    g.exec(cw, sw)
    add = g.call_on(USER_WIDGET, "AddToViewport", inputs=[Pin("ZOrder", INT, default="20")])
    g.link(cw, "ReturnValue", add, "self")
    g.exec(sw, add)
    cur_on = g.var_set_on(PLAYER_CONTROLLER, "bShowMouseCursor", BOOL, default="true")
    g.link(g.self_node(), "self", cur_on, "self")
    g.exec(add, cur_on)
    # Game-and-UI, not UI-only: the P key must still reach this controller to resume
    gui = g.call_static("WidgetBlueprintLibrary", "SetInputMode_GameAndUIEx",
                        inputs=[obj_pin("PlayerController", PLAYER_CONTROLLER), obj_pin("InWidgetToFocus", "/Script/UMG.Widget"),
                                native_enum_pin("InMouseLockMode", "/Script/UMG.EMouseLockMode", "DoNotLock"),
                                Pin("bHideCursorDuringCapture", BOOL, default="false")], module="UMG")
    g.link(g.self_node(), "self", gui, "PlayerController")
    g.link(cw, "ReturnValue", gui, "InWidgetToFocus")
    g.exec(cur_on, gui)

    g = bp.function("SwitchToPawn", doc="Possesses the given pawn.", inputs=["NewPawn:object:" + PAWN])
    poss = g.call_self_native("/Script/Engine.Controller", "Possess", inputs=[obj_pin("InPawn", PAWN)])
    g.link_entry("NewPawn", poss, "InPawn")
    g.link_entry("then", poss, "execute")

    g = bp.event_graph()
    g.section("Possess: remember the car being driven")
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

    g.section("Pause: toggle the pause menu (fires while paused too)")
    pa = g.input_action("Pause", execute_when_paused=True)
    tp = g.call_self("TogglePause")
    g.link(pa, "Pressed", tp, "execute")

    g.section("Begin Play: fade in from black (the GameInstance fades out before every level change)")
    bpl = g.begin_play()
    cam = g.var_get_on(PLAYER_CONTROLLER, "PlayerCameraManager", OBJECT, cls_ref("/Script/Engine.PlayerCameraManager"))
    g.link(g.self_node(), "self", cam, "self")
    fade = g.call_on("/Script/Engine.PlayerCameraManager", "StartCameraFade",
                     inputs=[Pin("FromAlpha", FLOAT, default="1.0"), Pin("ToAlpha", FLOAT, default="0.0"), Pin("Duration", FLOAT, default="0.5"),
                             struct_pin("Color", LINEAR_COLOR, default="(R=0.000000,G=0.000000,B=0.000000,A=1.000000)"),
                             Pin("bShouldFadeAudio", BOOL, default="false"), Pin("bHoldWhenFinished", BOOL, default="false")])
    g.link(cam, "PlayerCameraManager", fade, "self")
    g.exec(bpl, fade)
    return bp


def build():
    return [build_racer(), build_controller()]


if __name__ == "__main__":
    for b in build():
        print(b.write(OUT))
