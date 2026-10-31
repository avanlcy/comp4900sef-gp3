"""WBP_DFRaceHUD, WBP_DFRaceSummary and BP_DFHUD (plan Task 8). Layout and copy from the Phase 2 design §6:
top-left SCORE / LAPS / KILLS / LIVES; top-centre clock (red under 10 s); bottom-right speed and gear (R in red);
bottom-left car health bar + tires, or character health on foot; crosshair on foot; prompt line at 72 % height;
warning line at 40 % height (RETURN TO TRACK countdown, WRECKED, YOU DIED, CHECKPOINT +8 s for 1.5 s).
Phase 7 Task 18 (spec §7.6): every text in Russo One (F_DF_Display); the item row is three icon tiles (GetItemLook's icon or
T_DF_Icon_Empty, the charges, the selected slot framed); the crosshair is an image that HitMarker turns red when the player's
shot hits a car or a character; ShowDamage flashes a red vignette (the player's car calls it, the character's hits are bound); DRIFT on a drift
boost; the warning line ends with the crate prompt when the car is stopped near a crate; every button has the UI sounds.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from bpgen import WidgetBlueprint, cls_ref, struct_ref  # noqa: E402
from df import BP_GI, game_instance  # noqa: E402  (Phase 5)
from df import (BOOL, BP_CHARACTER, BP_GM, BP_GS, BP_HUD, BP_PC, BP_VEHICLE, BPC_RACER, CONTROLLER, E_ITEM_TYPE, FLOAT,  # noqa: E402
                GAMEPLAY, INT, LINEAR_COLOR, MATH, OBJECT, OUT, PLAYER_CONTROLLER, S_ITEM_STACK, S_RESULT, S_TIRE, STRING,
                STRUCT, VECTOR, WBP_HUD, WBP_SUMMARY, Blueprint, Graph, Node, Pin, and_bool, as_pin, compare, enum_pin,
                game_time, gen, is_valid, math2, member, native_enum_pin, not_bool, obj_pin, obj_spec, struct_path,
                struct_pin, struct_spec)
from df import (ACTOR, BP_LOOTBOX, BPC_WEAPON, EMPTY_ICON, F_DISPLAY, HIT_RESULT, IMAGE, SW_UI_CLICK, SW_UI_HOVER,  # noqa: E402
                T_CROSSHAIR, T_VIGNETTE, TEXTURE_2D, art_icon, asset_object, timer)  # Phase 7 Task 18

UMG = "/Script/UMG"
TEXT_BLOCK, PROGRESS, VBOX, HBOX, BUTTON, BORDER, SIZEBOX, WIDGET, USER_WIDGET = (
    UMG + ".TextBlock", UMG + ".ProgressBar", UMG + ".VerticalBox", UMG + ".HorizontalBox", UMG + ".Button",
    UMG + ".Border", UMG + ".SizeBox", UMG + ".Widget", UMG + ".UserWidget")
OVERLAY = UMG + ".Overlay"
VECTOR2D = "/Script/CoreUObject.Vector2D"
SLATE_COLOR = "/Script/SlateCore.SlateColor"
GEOMETRY = "/Script/SlateCore.Geometry"
VIS = "/Script/UMG.ESlateVisibility"
VC, CC, PCC, GMC, GSC, RC = gen(BP_VEHICLE), gen(BP_CHARACTER), gen(BP_PC), gen(BP_GM), gen(BP_GS), gen(BPC_RACER)
WHUD, WSUM, HUDC = gen(WBP_HUD), gen(WBP_SUMMARY), gen(BP_HUD)
GIC = gen(BP_GI)  # Phase 5
TIRE, RESULT, ITEM = struct_path(S_TIRE), struct_path(S_RESULT), struct_path(S_ITEM_STACK)
ITEM_ENUM = enum_pin("x", E_ITEM_TYPE).sub_object
PICKUP_FLASH_SECONDS = 1.5
WHITE, RED, AMBER, SHADOW = [1, 1, 1, 1], [1, 0.15, 0.1, 1], [1, 0.75, 0.2, 1], [0, 0, 0, 0.8]
# Phase 7 Task 18 (spec §7.6): the timed HUD looks and the crate prompt
HIT_MARKER_SECONDS, HIT_MARKER_SCALE = 0.15, 1.3  # a hit turns the crosshair red at 1.3x for this long
DAMAGE_SECONDS = 0.3                              # the damage vignette after a hit taken
DRIFT_SECONDS = 0.6                               # the DRIFT label after a drift boost
CRATE_PROMPT = "CRATE NEARBY - E TO GET OUT"
CRATE_PROMPT_CM = 4000.0                          # driving below exit speed this close to an uncollected crate shows the prompt


# ---------- graph helpers ----------
def s_int(g, src):
    n = g.call_static("KismetStringLibrary", "Conv_IntToString", inputs=[Pin("InInt", INT)], outputs=[Pin("ReturnValue", STRING, "out")], pure=True)
    g.link(src[0], src[1], n, "InInt")
    return (n, "ReturnValue")


def s_floor(g, src):
    f = g.call_static(MATH, "FFloor", inputs=[Pin("A", FLOAT)], outputs=[Pin("ReturnValue", INT, "out")], pure=True)
    g.link(src[0], src[1], f, "A")
    return s_int(g, (f, "ReturnValue"))


def cat(g, *parts):
    """String concatenation of literals and (node, pin) sources."""
    acc = None
    for p in parts:
        n = g.call_static("KismetStringLibrary", "Concat_StrStr", inputs=[Pin("A", STRING, default=""), Pin("B", STRING, default=p if isinstance(p, str) else None)],
                          outputs=[Pin("ReturnValue", STRING, "out")], pure=True)
        if acc:
            g.link(acc[0], acc[1], n, "A")
        if not isinstance(p, str):
            g.link(p[0], p[1], n, "B")
        acc = (n, "ReturnValue")
    return acc


def pick(g, a, b, cond):
    """SelectString(a if cond else b); a/b are literals or sources."""
    n = g.call_static(MATH, "SelectString", inputs=[Pin("A", STRING, default=a if isinstance(a, str) else None),
                                                     Pin("B", STRING, default=b if isinstance(b, str) else None), Pin("bPickA", BOOL)],
                      outputs=[Pin("ReturnValue", STRING, "out")], pure=True)
    for v, pin in ((a, "A"), (b, "B")):
        if not isinstance(v, str):
            g.link(v[0], v[1], n, pin)
    g.link(cond[0], cond[1], n, "bPickA")
    return (n, "ReturnValue")


def one_decimal(g, src):
    """Seconds as a string with one decimal, rounded up (4.2)."""
    tenths = math2(g, "Multiply_FloatFloat", FLOAT, b="10.0")
    g.link(src[0], src[1], tenths, "A")
    ceil = g.call_static(MATH, "FCeil", inputs=[Pin("A", FLOAT)], outputs=[Pin("ReturnValue", INT, "out")], pure=True)
    g.link(tenths, "ReturnValue", ceil, "A")
    tf = g.call_static(MATH, "Conv_IntToFloat", inputs=[Pin("InInt", INT)], outputs=[Pin("ReturnValue", FLOAT, "out")], pure=True)
    g.link(ceil, "ReturnValue", tf, "InInt")
    secs = math2(g, "Divide_FloatFloat", FLOAT, b="10.0")
    g.link(tf, "ReturnValue", secs, "A")
    fs = g.call_static("KismetStringLibrary", "Conv_FloatToString", inputs=[Pin("InFloat", FLOAT)], outputs=[Pin("ReturnValue", STRING, "out")], pure=True)
    g.link(secs, "ReturnValue", fs, "InFloat")
    return (fs, "ReturnValue")


def label(g, widget: str, text_src, prev):
    """self.SetLabel(widget, text): returns the call node (exec chain)."""
    w = g.var_get(widget, OBJECT, cls_ref(TEXT_BLOCK))
    n = g.call_self("SetLabel", inputs=[obj_pin("Target", TEXT_BLOCK), Pin("Value", STRING)])
    g.link(w, widget, n, "Target")
    g.link(text_src[0], text_src[1], n, "Value")
    g.link(prev[0], prev[1], n, "execute")
    return n


def shown(g, widget: str, cls: str, cond, prev):
    w = g.var_get(widget, OBJECT, cls_ref(cls))
    n = g.call_self("SetShown", inputs=[obj_pin("Target", WIDGET), Pin("bShown", BOOL)])
    g.link(w, widget, n, "Target")
    g.link(cond[0], cond[1], n, "bShown")
    g.link(prev[0], prev[1], n, "execute")
    return n


def red(g, widget: str, cond, prev):
    w = g.var_get(widget, OBJECT, cls_ref(TEXT_BLOCK))
    n = g.call_self("SetRed", inputs=[obj_pin("Target", TEXT_BLOCK), Pin("bRed", BOOL)])
    g.link(w, widget, n, "Target")
    g.link(cond[0], cond[1], n, "bRed")
    g.link(prev[0], prev[1], n, "execute")
    return n


def get_on(g, cls, var, cat_, obj, sub=None, container=None):
    n = g.var_get_on(cls, var, cat_, sub, container=container)
    g.link(obj[0], obj[1], n, "self")
    return (n, var)


def add_text_helpers(bp: Blueprint):
    g = bp.function("SetLabel", doc="Sets a text block from a string.", inputs=["Target:object:" + TEXT_BLOCK, "Value:string"])
    t = g.call_static("KismetTextLibrary", "Conv_StringToText", inputs=[Pin("InString", STRING)], outputs=[Pin("ReturnValue", "text", "out")], pure=True)
    g.link_entry("Value", t, "InString")
    st = g.call_on(TEXT_BLOCK, "SetText", inputs=[Pin("InText", "text")])
    g.link_entry("Target", st, "self")
    g.link(t, "ReturnValue", st, "InText")
    g.link_entry("then", st, "execute")


def add_widget_helpers(bp: Blueprint):
    add_text_helpers(bp)
    g = bp.function("SetShown", doc="Shows or collapses a widget.", inputs=["Target:object:" + WIDGET, "bShown:bool"])
    b = g.branch()
    g.link_entry("bShown", b, "Condition")
    g.link_entry("then", b, "execute")
    for out, vis in (("then", "HitTestInvisible"), ("else", "Collapsed")):
        n = g.call_on(WIDGET, "SetVisibility", inputs=[native_enum_pin("InVisibility", VIS, vis)])
        g.link_entry("Target", n, "self")
        g.link(b, out, n, "execute")

    g = bp.function("SetAmber", doc="Amber or white text.", inputs=["Target:object:" + TEXT_BLOCK, "bAmber:bool"])
    col = g.call_static(MATH, "SelectColor", inputs=[struct_pin("A", LINEAR_COLOR, default="(R=1.000000,G=0.750000,B=0.200000,A=1.000000)"),
                                                      struct_pin("B", LINEAR_COLOR, default="(R=1.000000,G=1.000000,B=1.000000,A=1.000000)"),
                                                      Pin("bPickA", BOOL)],
                        outputs=[struct_pin("ReturnValue", LINEAR_COLOR, "out")], pure=True)
    g.link_entry("bAmber", col, "bPickA")
    sc = g.make_struct(SLATE_COLOR, [struct_pin("SpecifiedColor", LINEAR_COLOR),
                                     native_enum_pin("ColorUseRule", "/Script/SlateCore.ESlateColorStylingMode", "UseColor_Specified")])
    g.link(col, "ReturnValue", sc, "SpecifiedColor")
    st = g.call_on(TEXT_BLOCK, "SetColorAndOpacity", inputs=[struct_pin("InColorAndOpacity", SLATE_COLOR)])
    g.link_entry("Target", st, "self")
    g.link(sc, "SlateColor", st, "InColorAndOpacity")
    g.link_entry("then", st, "execute")

    g = bp.function("SetRed", doc="Red or white text.", inputs=["Target:object:" + TEXT_BLOCK, "bRed:bool"])
    col = g.call_static(MATH, "SelectColor", inputs=[struct_pin("A", LINEAR_COLOR, default="(R=1.000000,G=0.150000,B=0.100000,A=1.000000)"),
                                                      struct_pin("B", LINEAR_COLOR, default="(R=1.000000,G=1.000000,B=1.000000,A=1.000000)"),
                                                      Pin("bPickA", BOOL)],
                        outputs=[struct_pin("ReturnValue", LINEAR_COLOR, "out")], pure=True)
    g.link_entry("bRed", col, "bPickA")
    sc = g.make_struct(SLATE_COLOR, [struct_pin("SpecifiedColor", LINEAR_COLOR),
                                     native_enum_pin("ColorUseRule", "/Script/SlateCore.ESlateColorStylingMode", "UseColor_Specified")])
    g.link(col, "ReturnValue", sc, "SpecifiedColor")
    st = g.call_on(TEXT_BLOCK, "SetColorAndOpacity", inputs=[struct_pin("InColorAndOpacity", SLATE_COLOR)])
    g.link_entry("Target", st, "self")
    g.link(sc, "SlateColor", st, "InColorAndOpacity")
    g.link_entry("then", st, "execute")


def text_props(text, size, color=WHITE, justify="Left"):
    # Phase 7 Task 18 (spec §7.6): every text in Russo One; F_DF_Display's one typeface entry is "Default" (SetFontFace)
    return {"text": text, "font_size": size, "color": color, "shadow": SHADOW, "justify": justify,
            "font_object": F_DISPLAY, "typeface_font_name": "Default"}


def button_props(**props):
    """A Button's props: Phase 7 Task 18 (spec §7.6), every button plays SW_DF_UIHover when hovered and SW_DF_UIClick when pressed."""
    return dict(props, sounds=[SW_UI_HOVER, SW_UI_CLICK])


def set_icon(g, widget: str, texture_src, prev):
    """SetBrushFromTexture on an Image widget of this Blueprint (keeps the widget's size); texture_src is a (node, pin) source or
    an asset path (a literal). Returns the call node."""
    literal = isinstance(texture_src, str)
    n = g.call_on(IMAGE, "SetBrushFromTexture", inputs=[Pin("Texture", OBJECT, sub_object=cls_ref(TEXTURE_2D),
                                                            default_object=asset_object(texture_src) if literal else None),
                                                        Pin("bMatchSize", BOOL, default="false")])
    g.link(g.var_get(widget, OBJECT, cls_ref(IMAGE)), widget, n, "self")
    if not literal:
        g.link(texture_src[0], texture_src[1], n, "Texture")
    g.link(prev[0], prev[1], n, "execute")
    return n


def crosshair_look(g, rgba, scale, prev):
    """CrosshairImage's colour and render scale (both axes); returns the last call node."""
    cross = g.var_get("CrosshairImage", OBJECT, cls_ref(IMAGE))
    col = g.call_on(IMAGE, "SetColorAndOpacity", inputs=[struct_pin("InColorAndOpacity", LINEAR_COLOR, default="(R=%f,G=%f,B=%f,A=%f)" % tuple(rgba))])
    g.link(cross, "CrosshairImage", col, "self")
    g.link(prev[0], prev[1], col, "execute")
    size = g.call_static(MATH, "MakeVector2D", inputs=[Pin("X", FLOAT, default="%f" % scale), Pin("Y", FLOAT, default="%f" % scale)],
                         outputs=[struct_pin("ReturnValue", VECTOR2D, "out")], pure=True)
    sc = g.call_on(WIDGET, "SetRenderScale", inputs=[struct_pin("Scale", VECTOR2D)])
    g.link(cross, "CrosshairImage", sc, "self")
    g.link(size, "ReturnValue", sc, "Scale")
    g.exec(col, sc)
    return sc


def timed_show(bp, show_fn, hide_fn, widget, cls, seconds, show_doc, hide_doc):
    """show_fn(): the widget shown (SetShown) and hide_fn armed for `seconds` (a repeat restarts the countdown); hide_fn():
    the widget collapsed again."""
    for fn, shown_, doc in ((show_fn, "true", show_doc), (hide_fn, "false", hide_doc)):
        g = bp.function(fn, doc=doc)
        n = g.call_self("SetShown", inputs=[obj_pin("Target", WIDGET), Pin("bShown", BOOL, default=shown_)])
        g.link(g.var_get(widget, OBJECT, cls_ref(cls)), widget, n, "Target")
        g.link_entry("then", n, "execute")
        if fn == show_fn:
            g.exec(n, timer(g, hide_fn, seconds, looping=False))


# ---------- in-race HUD ----------
def build_hud() -> WidgetBlueprint:
    bp = WidgetBlueprint(WBP_HUD, description="The in-race HUD.")
    # Phase 7 Task 18 (spec §7.6): the red damage vignette over the whole screen, first so it draws behind the rest; ShowDamage
    bp.widget("Vignette", IMAGE, None, {"texture": T_VIGNETTE, "visibility": "Collapsed"},
              {"anchors": [0, 0, 1, 1], "position": [0, 0], "size": [0, 0]})
    bp.widget("StatsBox", VBOX, slot={"anchors": [0, 0, 0, 0], "position": [40, 30], "auto_size": True})
    for name, text in (("ScoreText", "SCORE 0"), ("LapText", "LAPS 0"), ("KillsText", "KILLS 0"), ("LivesText", "LIVES 3"),
                       ("PositionText", "POS 1 / 1")):  # Phase 4 (spec §5): rank among every racer
        bp.widget(name, TEXT_BLOCK, "StatsBox", text_props(text, 26), {"padding": [0, 0, 0, 2]})
    bp.widget("TimeText", TEXT_BLOCK, None, text_props("2:00", 44, justify="Center"),
              {"anchors": [0.5, 0, 0.5, 0], "alignment": [0.5, 0], "position": [0, 24], "auto_size": True})
    bp.widget("DrivePanel", VBOX, None, slot={"anchors": [1, 1, 1, 1], "alignment": [1, 1], "position": [-40, -36], "auto_size": True})
    bp.widget("SpeedText", TEXT_BLOCK, "DrivePanel", text_props("0 km/h", 40, justify="Right"), {"h_align": "Right"})
    bp.widget("GearText", TEXT_BLOCK, "DrivePanel", text_props("GEAR N", 26, justify="Right"), {"h_align": "Right"})
    bp.widget("VehiclePanel", VBOX, None, slot={"anchors": [0, 1, 0, 1], "alignment": [0, 1], "position": [40, -36], "auto_size": True})
    bp.widget("VehicleHealthText", TEXT_BLOCK, "VehiclePanel", text_props("CAR 100 / 100", 24))
    bp.widget("VehicleHealthBox", SIZEBOX, "VehiclePanel", {"width_override": 320, "height_override": 14}, {"padding": [0, 4, 0, 4]})
    bp.widget("VehicleHealthBar", PROGRESS, "VehicleHealthBox", {"percent": 1.0, "fill_color": [0.2, 0.85, 0.3, 1]})
    bp.widget("TireText", TEXT_BLOCK, "VehiclePanel", text_props("TIRES [30] [30] [30] [30]", 20))
    bp.widget("CharacterPanel", VBOX, None, slot={"anchors": [0, 1, 0, 1], "alignment": [0, 1], "position": [40, -36], "auto_size": True})
    bp.widget("CharacterHealthText", TEXT_BLOCK, "CharacterPanel", text_props("HEALTH 100 / 100", 24))
    bp.widget("CharacterHealthBox", SIZEBOX, "CharacterPanel", {"width_override": 320, "height_override": 14}, {"padding": [0, 4, 0, 4]})
    bp.widget("CharacterHealthBar", PROGRESS, "CharacterHealthBox", {"percent": 1.0, "fill_color": [0.25, 0.6, 1.0, 1]})
    # Phase 7 Task 18: the crosshair is an image (64 px, white; HitMarker turns it red and larger for a moment)
    bp.widget("CrosshairImage", IMAGE, None, {"texture": T_CROSSHAIR},
              {"anchors": [0.5, 0.5, 0.5, 0.5], "alignment": [0.5, 0.5], "auto_size": True})
    bp.widget("DriftText", TEXT_BLOCK, None, dict(text_props("DRIFT", 56, AMBER, "Center"), visibility="Collapsed"),
              {"anchors": [0.5, 0.28, 0.5, 0.28], "alignment": [0.5, 0.5], "auto_size": True})
    bp.widget("PromptText", TEXT_BLOCK, None, text_props("", 26, justify="Center"),
              {"anchors": [0.5, 0.72, 0.5, 0.72], "alignment": [0.5, 0.5], "auto_size": True})
    bp.widget("WarningText", TEXT_BLOCK, None, text_props("", 40, AMBER, "Center"),
              {"anchors": [0.5, 0.4, 0.5, 0.4], "alignment": [0.5, 0.5], "auto_size": True})
    # Phase 3 (spec §9): item row at the bottom centre, effect line above, key hint below
    bp.widget("ItemPanel", VBOX, None, slot={"anchors": [0.5, 1, 0.5, 1], "alignment": [0.5, 1], "position": [0, -120], "auto_size": True})
    bp.widget("EffectText", TEXT_BLOCK, "ItemPanel", text_props("", 22, AMBER, "Center"), {"h_align": "Center", "padding": [0, 0, 0, 4]})
    bp.widget("ItemRow", HBOX, "ItemPanel", slot={"h_align": "Center"})
    # Phase 7 Task 18 (spec §7.6): each slot an 80 px tile: the frame (the selected slot, in its item's colour) under a dark
    # inset, the item's icon, and its charges in the corner
    for i in range(3):
        bp.widget("ItemSlot%d" % i, SIZEBOX, "ItemRow", {"width_override": 80, "height_override": 80}, {"padding": [8, 0, 8, 0]})
        bp.widget("ItemStack%d" % i, OVERLAY, "ItemSlot%d" % i)
        fill = {"h_align": "Fill", "v_align": "Fill"}
        bp.widget("ItemFrame%d" % i, BORDER, "ItemStack%d" % i, {"brush_color": AMBER, "visibility": "Collapsed"}, fill)
        bp.widget("ItemBack%d" % i, BORDER, "ItemStack%d" % i, {"brush_color": [0, 0, 0, 0.55]}, dict(fill, padding=[4, 4, 4, 4]))
        bp.widget("ItemIcon%d" % i, IMAGE, "ItemStack%d" % i, {"texture": art_icon(EMPTY_ICON)}, dict(fill, padding=[10, 10, 10, 10]))
        bp.widget("ItemCount%d" % i, TEXT_BLOCK, "ItemStack%d" % i, text_props("", 22, justify="Right"),
                  {"h_align": "Right", "v_align": "Bottom", "padding": [0, 0, 7, 3]})
    bp.widget("ItemHintText", TEXT_BLOCK, "ItemPanel", text_props("[Q] USE   [R] NEXT", 18, justify="Center"), {"h_align": "Center", "padding": [0, 4, 0, 0]})
    add_widget_helpers(bp)

    # RefreshCar(Car): speed, gear, health, tires, exit prompt
    g = bp.function("RefreshCar", doc="Speed, gear, health bar, tires and the exit prompt.", inputs=["Car:" + obj_spec(BP_VEHICLE)], locals=["Tires:string"])
    car = ("entry", "Car")
    sp = g.call_on(VC, "GetSpeedKPH", outputs=[Pin("KPH", FLOAT, "out")], pure=True)
    g.link_entry("Car", sp, "self")
    n1 = label(g, "SpeedText", cat(g, s_floor(g, (sp, "KPH")), " km/h"), ("entry", "then"))
    gear = g.call_on(VC, "GetGearString", outputs=[Pin("Gear", STRING, "out")], pure=True)
    g.link_entry("Car", gear, "self")
    n2 = label(g, "GearText", cat(g, "GEAR ", (gear, "Gear")), (n1, "then"))
    is_r = g.call_static("KismetStringLibrary", "EqualEqual_StrStr", inputs=[Pin("A", STRING), Pin("B", STRING, default="R")],
                         outputs=[Pin("ReturnValue", BOOL, "out")], pure=True)
    g.link(gear, "Gear", is_r, "A")
    n3 = red(g, "GearText", (is_r, "ReturnValue"), (n2, "then"))
    h = g.var_get_on(VC, "Health", FLOAT)
    g.link_entry("Car", h, "self")
    mh = g.var_get_on(VC, "MaxHealth", FLOAT)
    g.link_entry("Car", mh, "self")
    n4 = label(g, "VehicleHealthText", cat(g, "CAR ", s_floor(g, (h, "Health")), " / ", s_floor(g, (mh, "MaxHealth"))), (n3, "then"))
    frac = math2(g, "Divide_FloatFloat", FLOAT)
    g.link(h, "Health", frac, "A")
    g.link(mh, "MaxHealth", frac, "B")
    bar = g.var_get("VehicleHealthBar", OBJECT, cls_ref(PROGRESS))
    sp_ = g.call_on(PROGRESS, "SetPercent", inputs=[Pin("InPercent", FLOAT)])
    g.link(bar, "VehicleHealthBar", sp_, "self")
    g.link(frac, "ReturnValue", sp_, "InPercent")
    g.exec(n4, sp_)
    init = g.local_set("Tires", STRING, default="TIRES")
    g.exec(sp_, init)
    tires = g.var_get_on(VC, "Tires", STRUCT, struct_ref(TIRE), container="Array")
    g.link_entry("Car", tires, "self")
    loop = g.for_each(Pin("e", STRUCT, sub_object=struct_ref(TIRE)))
    g.link(tires, "Tires", loop, "Array")
    g.link(init, "then", loop, "Exec")
    br = g.break_struct(TIRE, [Pin(member(S_TIRE, "Health"), FLOAT), Pin(member(S_TIRE, "bBlown"), BOOL)])
    g.link(loop, "Array Element", br, TIRE.rsplit(".", 1)[1])
    one = pick(g, " [X]", cat(g, " [", s_floor(g, (br, member(S_TIRE, "Health"))), "]"), (br, member(S_TIRE, "bBlown")))
    acc = g.local_get("Tires", STRING)
    more = g.local_set("Tires", STRING)
    g.link(cat(g, (acc, "Tires"), one)[0], "ReturnValue", more, "Tires")
    g.link(loop, "LoopBody", more, "execute")
    done = g.local_get("Tires", STRING)
    n5 = label(g, "TireText", (done, "Tires"), (loop, "Completed"))
    slow = g.call_on(VC, "IsBelowExitSpeed", outputs=[Pin("ReturnValue", BOOL, "out")], pure=True)
    g.link_entry("Car", slow, "self")
    b = g.branch()
    g.link(slow, "ReturnValue", b, "Condition")
    g.exec(n5, b)
    label(g, "PromptText", cat(g, "Stop to exit  [E]"), (b, "else"))
    find = g.call_on(VC, "FindExitLocation", outputs=[Pin("bFound", BOOL, "out"), struct_pin("Location", VECTOR, "out")])
    g.link_entry("Car", find, "self")
    g.link(b, "then", find, "execute")
    label(g, "PromptText", pick(g, "[E] Exit vehicle", "No room to exit", (find, "bFound")), (find, "then"))

    # RefreshFoot(Character): health and the enter prompt
    g = bp.function("RefreshFoot", doc="Character health and the enter prompt.", inputs=["Character:" + obj_spec(BP_CHARACTER)])
    v = is_valid(g)
    g.link_entry("Character", v, "Object")
    b = g.branch()
    g.link(v, "ReturnValue", b, "Condition")
    g.link_entry("then", b, "execute")
    h = g.var_get_on(CC, "Health", FLOAT)
    g.link_entry("Character", h, "self")
    mh = g.var_get_on(CC, "MaxHealth", FLOAT)
    g.link_entry("Character", mh, "self")
    n1 = label(g, "CharacterHealthText", cat(g, "HEALTH ", s_floor(g, (h, "Health")), " / ", s_floor(g, (mh, "MaxHealth"))), (b, "then"))
    frac = math2(g, "Divide_FloatFloat", FLOAT)
    g.link(h, "Health", frac, "A")
    g.link(mh, "MaxHealth", frac, "B")
    bar = g.var_get("CharacterHealthBar", OBJECT, cls_ref(PROGRESS))
    sp_ = g.call_on(PROGRESS, "SetPercent", inputs=[Pin("InPercent", FLOAT)])
    g.link(bar, "CharacterHealthBar", sp_, "self")
    g.link(frac, "ReturnValue", sp_, "InPercent")
    g.exec(n1, sp_)
    near = g.call_on(CC, "FindNearestEnterableVehicle", outputs=[obj_pin("ReturnValue", VC, "out")])
    g.link_entry("Character", near, "self")
    g.exec(sp_, near)
    nv = is_valid(g)
    g.link(near, "ReturnValue", nv, "Object")
    label(g, "PromptText", pick(g, "[E] Enter vehicle", "", (nv, "ReturnValue")), (near, "then"))

    # RefreshItems(Racer, Car): three icon slots (Phase 7 Task 18, spec §7.6: the icon from GetItemLook or T_DF_Icon_Empty, the
    # charges, the selected filled slot framed in its item's colour), the effect line and the key hint (spec §9)
    g = bp.function("RefreshItems", doc="The three item slots (icon, charges, the selected one framed), the effect line and the key hint.",
                    inputs=["Racer:object:" + RC, "Car:" + obj_spec(BP_VEHICLE)])
    gm_ = g.call_static(GAMEPLAY, "GetGameMode", inputs=[Pin("WorldContextObject", OBJECT, hidden=True)],
                        outputs=[obj_pin("ReturnValue", "/Script/Engine.GameModeBase", "out")], pure=True)
    gm = g.cast(GMC)
    g.link(gm_, "ReturnValue", gm, "Object")
    g.link_entry("then", gm, "execute")
    inv = g.var_get_on(RC, "Inventory", STRUCT, struct_ref(ITEM), container="Array")
    g.link_entry("Racer", inv, "self")
    ln = g.call_array("KismetArrayLibrary", "Array_Length", Pin("e", STRUCT, sub_object=struct_ref(ITEM)), outputs=[Pin("ReturnValue", INT, "out")])
    g.link(inv, "Inventory", ln, "TargetArray")
    sel = g.var_get_on(RC, "SelectedSlot", INT)
    g.link_entry("Racer", sel, "self")
    prev = (gm, "then")
    for i in range(3):
        has = compare(g, "Less_IntInt", INT, a=str(i))
        g.link(ln, "ReturnValue", has, "B")
        bi = g.branch()
        g.link(has, "ReturnValue", bi, "Condition")
        g.link(prev[0], prev[1], bi, "execute")
        item = g.call_array("KismetArrayLibrary", "Array_Get", Pin("e", STRUCT, sub_object=struct_ref(ITEM)), inputs=[Pin("Index", INT, default=str(i))],
                            outputs=[Pin("Item", STRUCT, "out", struct_ref(ITEM))])
        inv_i = g.var_get_on(RC, "Inventory", STRUCT, struct_ref(ITEM), container="Array")
        g.link_entry("Racer", inv_i, "self")
        g.link(inv_i, "Inventory", item, "TargetArray")
        br = g.break_struct(ITEM, [enum_pin(member(S_ITEM_STACK, "Type"), E_ITEM_TYPE, "out"), Pin(member(S_ITEM_STACK, "Charges"), INT, "out")])
        g.link(item, "Item", br, ITEM.rsplit(".", 1)[1])
        look = g.call_on(GMC, "GetItemLook", inputs=[enum_pin("Type", E_ITEM_TYPE), Pin("bRandom", BOOL, default="false")],
                         outputs=[struct_pin("Colour", LINEAR_COLOR, "out"), obj_pin("Icon", TEXTURE_2D, "out")], pure=True)
        g.link(gm, as_pin(BP_GM), look, "self")
        g.link(br, member(S_ITEM_STACK, "Type"), look, "Type")
        icon = set_icon(g, "ItemIcon%d" % i, (look, "Icon"), (bi, "then"))
        count = label(g, "ItemCount%d" % i, s_int(g, (br, member(S_ITEM_STACK, "Charges"))), (icon, "then"))
        tint = g.call_on(BORDER, "SetBrushColor", inputs=[struct_pin("InBrushColor", LINEAR_COLOR)])
        g.link(g.var_get("ItemFrame%d" % i, OBJECT, cls_ref(BORDER)), "ItemFrame%d" % i, tint, "self")
        g.link(look, "Colour", tint, "InBrushColor")
        g.exec(count, tint)
        empty = label(g, "ItemCount%d" % i, cat(g, ""), (set_icon(g, "ItemIcon%d" % i, art_icon(EMPTY_ICON), (bi, "else")), "then"))
        is_sel = compare(g, "EqualEqual_IntInt", INT, a=str(i))
        g.link(sel, "SelectedSlot", is_sel, "B")
        both = and_bool(g)
        g.link(is_sel, "ReturnValue", both, "A")
        g.link(has, "ReturnValue", both, "B")
        frame = shown(g, "ItemFrame%d" % i, BORDER, (both, "ReturnValue"), (tint, "then"))
        g.link(empty, "then", frame, "execute")
        prev = (frame, "then")
    cv = is_valid(g)
    g.link_entry("Car", cv, "Object")
    hint = shown(g, "ItemHintText", TEXT_BLOCK, (cv, "ReturnValue"), prev)
    bc = g.branch()
    g.link(cv, "ReturnValue", bc, "Condition")
    g.exec(hint, bc)
    boost = g.var_get_on(VC, "BoostRemaining", FLOAT)
    g.link_entry("Car", boost, "self")
    shield = g.var_get_on(VC, "ShieldRemaining", FLOAT)
    g.link_entry("Car", shield, "self")
    b_on = compare(g, "Greater_FloatFloat", FLOAT, b="0.0")
    g.link(boost, "BoostRemaining", b_on, "A")
    s_on = compare(g, "Greater_FloatFloat", FLOAT, b="0.0")
    g.link(shield, "ShieldRemaining", s_on, "A")
    shield_text = cat(g, "SHIELD ", one_decimal(g, (shield, "ShieldRemaining")))
    with_boost = pick(g, cat(g, "BOOST   ", shield_text), "BOOST", (s_on, "ReturnValue"))
    without = pick(g, shield_text, "", (s_on, "ReturnValue"))
    label(g, "EffectText", pick(g, with_boost, without, (b_on, "ReturnValue")), (bc, "then"))
    label(g, "EffectText", cat(g, ""), (bc, "else"))

    # RefreshWarning(PC, GM, Racer): WRECKED > YOU DIED > RETURN TO TRACK n.n > CHECKPOINT +8 s (1.5 s) > PICKED UP > (Phase 7 Task 18,
    # in a car below exit speed) CRATE NEARBY > nothing
    g = bp.function("RefreshWarning", doc="WRECKED > YOU DIED > RETURN TO TRACK > CHECKPOINT > PICKED UP > CRATE NEARBY (in a car, stopped).",
                    inputs=["PC:" + obj_spec(BP_PC), "GM:" + obj_spec(BP_GM), "Racer:object:" + RC])
    car = g.var_get_on(PCC, "CurrentVehicle", OBJECT, cls_ref(VC))
    g.link_entry("PC", car, "self")
    ch = g.var_get_on(PCC, "OnFootCharacter", OBJECT, cls_ref(CC))
    g.link_entry("PC", ch, "self")
    car_ok = is_valid(g)
    g.link(car, "CurrentVehicle", car_ok, "Object")
    ch_ok = is_valid(g)
    g.link(ch, "OnFootCharacter", ch_ok, "Object")
    b = g.branch()
    g.link(car_ok, "ReturnValue", b, "Condition")
    g.link_entry("then", b, "execute")
    # in a car: WRECKED or the timers; on foot: YOU DIED or the timers
    off = g.var_get_on(RC, "OffTrackSeconds", FLOAT)
    g.link_entry("Racer", off, "self")
    is_off = compare(g, "Greater_FloatFloat", FLOAT, b="0.0")
    g.link(off, "OffTrackSeconds", is_off, "A")
    grace = g.var_get_on(GMC, "OffTrackGraceSeconds", FLOAT)
    g.link_entry("GM", grace, "self")
    left = math2(g, "Subtract_FloatFloat", FLOAT)
    g.link(grace, "OffTrackGraceSeconds", left, "A")
    g.link(off, "OffTrackSeconds", left, "B")
    tenths = math2(g, "Multiply_FloatFloat", FLOAT, b="10.0")
    g.link(left, "ReturnValue", tenths, "A")
    ceil = g.call_static(MATH, "FCeil", inputs=[Pin("A", FLOAT)], outputs=[Pin("ReturnValue", INT, "out")], pure=True)
    g.link(tenths, "ReturnValue", ceil, "A")
    tf = g.call_static(MATH, "Conv_IntToFloat", inputs=[Pin("InInt", INT)], outputs=[Pin("ReturnValue", FLOAT, "out")], pure=True)
    g.link(ceil, "ReturnValue", tf, "InInt")
    secs = math2(g, "Divide_FloatFloat", FLOAT, b="10.0")
    g.link(tf, "ReturnValue", secs, "A")
    fs = g.call_static("KismetStringLibrary", "Conv_FloatToString", inputs=[Pin("InFloat", FLOAT)], outputs=[Pin("ReturnValue", STRING, "out")], pure=True)
    g.link(secs, "ReturnValue", fs, "InFloat")
    off_text = cat(g, "RETURN TO TRACK  ", (fs, "ReturnValue"))
    last = g.var_get_on(RC, "LastCheckpointTime", FLOAT)
    g.link_entry("Racer", last, "self")
    now = game_time(g)
    since = math2(g, "Subtract_FloatFloat", FLOAT)
    g.link(now, "ReturnValue", since, "A")
    g.link(last, "LastCheckpointTime", since, "B")
    fresh = compare(g, "Less_FloatFloat", FLOAT, b="1.5")
    g.link(since, "ReturnValue", fresh, "A")
    ever = compare(g, "GreaterEqual_FloatFloat", FLOAT, b="0.0")
    g.link(last, "LastCheckpointTime", ever, "A")
    recent = and_bool(g)
    g.link(fresh, "ReturnValue", recent, "A")
    g.link(ever, "ReturnValue", recent, "B")
    bonus = g.var_get_on(GMC, "CheckpointTimeBonus", FLOAT)
    g.link_entry("GM", bonus, "self")
    cp_text = cat(g, "CHECKPOINT  +", s_floor(g, (bonus, "CheckpointTimeBonus")), " s")
    # Phase 3: PICKED UP <item> for PICKUP_FLASH_SECONDS after a crate (spec §9)
    lpt = g.var_get_on(RC, "LastPickupTime", FLOAT)
    g.link_entry("Racer", lpt, "self")
    since_p = math2(g, "Subtract_FloatFloat", FLOAT)
    g.link(game_time(g), "ReturnValue", since_p, "A")
    g.link(lpt, "LastPickupTime", since_p, "B")
    fresh_p = compare(g, "Less_FloatFloat", FLOAT, b="%f" % PICKUP_FLASH_SECONDS)
    g.link(since_p, "ReturnValue", fresh_p, "A")
    ever_p = compare(g, "GreaterEqual_FloatFloat", FLOAT, b="0.0")
    g.link(lpt, "LastPickupTime", ever_p, "A")
    recent_p = and_bool(g)
    g.link(fresh_p, "ReturnValue", recent_p, "A")
    g.link(ever_p, "ReturnValue", recent_p, "B")
    lptype = g.var_get_on(RC, "LastPickupType", "byte", ITEM_ENUM)
    g.link_entry("Racer", lptype, "self")
    pinfo = g.call_on(GMC, "GetItemInfo", inputs=[enum_pin("Type", E_ITEM_TYPE)],
                      outputs=[Pin("Name", STRING, "out"), Pin("BoxCharges", INT, "out"), Pin("MaxCharges", INT, "out")], pure=True)
    g.link_entry("GM", pinfo, "self")
    g.link(lptype, "LastPickupType", pinfo, "Type")

    def timers_then(last):
        """RETURN TO TRACK > CHECKPOINT > PICKED UP > last (a literal or a source)."""
        pickup_text = pick(g, cat(g, "PICKED UP ", (pinfo, "Name")), last, (recent_p, "ReturnValue"))
        return pick(g, off_text, pick(g, cp_text, pickup_text, (recent, "ReturnValue")), (is_off, "ReturnValue"))

    timers = timers_then("")
    wrecked = g.var_get_on(VC, "bIsDestroyed", BOOL)
    g.link(car, "CurrentVehicle", wrecked, "self")
    # Phase 7 Task 18 (spec §7.6, §7.4): below exit speed, last in line, CRATE_PROMPT within CRATE_PROMPT_CM of an uncollected crate
    slow = g.call_on(VC, "IsBelowExitSpeed", outputs=[Pin("ReturnValue", BOOL, "out")], pure=True)
    g.link(car, "CurrentVehicle", slow, "self")
    bslow = g.branch()
    g.note(bslow, "stopped? a crate nearby?")
    g.link(slow, "ReturnValue", bslow, "Condition")
    g.link(b, "then", bslow, "execute")
    car_at = g.call_on(ACTOR, "K2_GetActorLocation", outputs=[struct_pin("ReturnValue", VECTOR, "out")], pure=True)
    g.link(car, "CurrentVehicle", car_at, "self")
    nearest = g.call_on(GMC, "FindNearestCrate", inputs=[struct_pin("Location", VECTOR)],
                        outputs=[obj_pin("Crate", gen(BP_LOOTBOX), "out"), Pin("Distance", FLOAT, "out")])
    g.link_entry("GM", nearest, "self")
    g.link(car_at, "ReturnValue", nearest, "Location")
    g.link(bslow, "then", nearest, "execute")
    crate_ok = is_valid(g)
    g.link(nearest, "Crate", crate_ok, "Object")
    close = compare(g, "LessEqual_FloatFloat", FLOAT, b="%f" % CRATE_PROMPT_CM)
    g.link(nearest, "Distance", close, "A")
    near = and_bool(g)
    g.link(crate_ok, "ReturnValue", near, "A")
    g.link(close, "ReturnValue", near, "B")
    crate_line = timers_then(pick(g, CRATE_PROMPT, "", (near, "ReturnValue")))
    label(g, "WarningText", pick(g, "WRECKED", crate_line, (wrecked, "bIsDestroyed")), (nearest, "then"))
    label(g, "WarningText", pick(g, "WRECKED", timers, (wrecked, "bIsDestroyed")), (bslow, "else"))
    dead = g.call_on(CC, "IsDead", outputs=[Pin("ReturnValue", BOOL, "out")], pure=True)
    g.link(ch, "OnFootCharacter", dead, "self")
    bd = g.branch()
    g.link(ch_ok, "ReturnValue", bd, "Condition")
    g.link(b, "else", bd, "execute")
    label(g, "WarningText", pick(g, "YOU DIED", timers, (dead, "ReturnValue")), (bd, "then"))
    label(g, "WarningText", timers, (bd, "else"))

    # Refresh: called every frame from Tick
    g = bp.function("Refresh", doc="Every frame: stats, clock, panels, then the car or foot details.")
    own = g.call_self_native(WIDGET, "GetOwningPlayer", outputs=[obj_pin("ReturnValue", PLAYER_CONTROLLER, "out")], pure=True)
    pc = g.cast(PCC)
    g.link(own, "ReturnValue", pc, "Object")
    g.link_entry("then", pc, "execute")
    gm_ = g.call_static(GAMEPLAY, "GetGameMode", inputs=[Pin("WorldContextObject", OBJECT, hidden=True)],
                        outputs=[obj_pin("ReturnValue", "/Script/Engine.GameModeBase", "out")], pure=True)
    gm = g.cast(GMC)
    g.link(gm_, "ReturnValue", gm, "Object")
    g.link(pc, "then", gm, "execute")
    gs_ = g.call_static(GAMEPLAY, "GetGameState", inputs=[Pin("WorldContextObject", OBJECT, hidden=True)],
                        outputs=[obj_pin("ReturnValue", "/Script/Engine.GameStateBase", "out")], pure=True)
    gs = g.cast(GSC)
    g.link(gs_, "ReturnValue", gs, "Object")
    g.link(gm, "then", gs, "execute")
    PC, GM, GS = (pc, as_pin(BP_PC)), (gm, as_pin(BP_GM)), (gs, as_pin(BP_GS))
    racer = g.call_on(GMC, "FindRacer", inputs=[obj_pin("C", CONTROLLER)], outputs=[obj_pin("Racer", RC, "out")], pure=True)
    g.link(GM[0], GM[1], racer, "self")
    g.link(PC[0], PC[1], racer, "C")
    rv = is_valid(g)
    g.link(racer, "Racer", rv, "Object")
    b = g.branch()
    g.link(rv, "ReturnValue", b, "Condition")
    g.link(gs, "then", b, "execute")
    R = (racer, "Racer")
    n = label(g, "ScoreText", cat(g, "SCORE ", s_int(g, get_on(g, RC, "Score", INT, R))), (b, "then"))
    n = label(g, "LapText", cat(g, "LAPS ", s_int(g, get_on(g, RC, "LapsCompleted", INT, R))), (n, "then"))
    n = label(g, "KillsText", cat(g, "KILLS ", s_int(g, get_on(g, RC, "Kills", INT, R))), (n, "then"))
    lives = math2(g, "Subtract_IntInt", INT)
    mx = get_on(g, GMC, "MaxDeaths", INT, GM)
    g.link(mx[0], mx[1], lives, "A")
    dd = get_on(g, RC, "Deaths", INT, R)
    g.link(dd[0], dd[1], lives, "B")
    n = label(g, "LivesText", cat(g, "LIVES ", s_int(g, (lives, "ReturnValue"))), (n, "then"))
    rank = get_on(g, RC, "Rank", INT, R)
    place = g.call_static(MATH, "Max", inputs=[Pin("A", INT), Pin("B", INT, default="1")], outputs=[Pin("ReturnValue", INT, "out")], pure=True)
    g.link(rank[0], rank[1], place, "A")
    count = get_on(g, GSC, "RacerCount", INT, GS)
    n = label(g, "PositionText", cat(g, "POS ", s_int(g, (place, "ReturnValue")), " / ", s_int(g, count)), (n, "then"))
    clock = g.call_on(GSC, "GetRemainingTimeString", outputs=[Pin("Text", STRING, "out")], pure=True)
    g.link(GS[0], GS[1], clock, "self")
    n = label(g, "TimeText", (clock, "Text"), (n, "then"))
    low = compare(g, "Less_FloatFloat", FLOAT, b="10.0")
    rt = get_on(g, GSC, "RemainingTime", FLOAT, GS)
    g.link(rt[0], rt[1], low, "A")
    n = red(g, "TimeText", (low, "ReturnValue"), (n, "then"))
    car = get_on(g, PCC, "CurrentVehicle", OBJECT, PC, sub=cls_ref(VC))
    in_car = is_valid(g)
    g.link(car[0], car[1], in_car, "Object")
    on_foot = not_bool(g)
    g.link(in_car, "ReturnValue", on_foot, "A")
    n = shown(g, "DrivePanel", VBOX, (in_car, "ReturnValue"), (n, "then"))
    n = shown(g, "VehiclePanel", VBOX, (in_car, "ReturnValue"), (n, "then"))
    n = shown(g, "CharacterPanel", VBOX, (on_foot, "ReturnValue"), (n, "then"))
    n = shown(g, "CrosshairImage", IMAGE, (on_foot, "ReturnValue"), (n, "then"))
    bc = g.branch()
    g.link(in_car, "ReturnValue", bc, "Condition")
    g.exec(n, bc)
    rc = g.call_self("RefreshCar", inputs=[obj_pin("Car", VC)])
    g.link(car[0], car[1], rc, "Car")
    g.link(bc, "then", rc, "execute")
    rf = g.call_self("RefreshFoot", inputs=[obj_pin("Character", CC)])
    ch = get_on(g, PCC, "OnFootCharacter", OBJECT, PC, sub=cls_ref(CC))
    g.link(ch[0], ch[1], rf, "Character")
    g.link(bc, "else", rf, "execute")
    ri = g.call_self("RefreshItems", inputs=[obj_pin("Racer", RC), obj_pin("Car", VC)])
    g.link(R[0], R[1], ri, "Racer")
    g.link(car[0], car[1], ri, "Car")
    g.exec(rc, ri)
    g.exec(rf, ri)
    rw = g.call_self("RefreshWarning", inputs=[obj_pin("PC", PCC), obj_pin("GM", GMC), obj_pin("Racer", RC)])
    g.link(PC[0], PC[1], rw, "PC")
    g.link(GM[0], GM[1], rw, "GM")
    g.link(R[0], R[1], rw, "Racer")
    g.exec(ri, rw)

    # Phase 7 Task 18 (spec §7.6): the timed looks. A repeat restarts the countdown (K2_SetTimer finds the function's timer).
    g = bp.function("HitMarker", doc="The player's shot hit a car or a character: the crosshair turns red at %gx for %g s (EndHitMarker)." % (HIT_MARKER_SCALE, HIT_MARKER_SECONDS))
    g.exec(crosshair_look(g, RED, HIT_MARKER_SCALE, ("entry", "then")), timer(g, "EndHitMarker", HIT_MARKER_SECONDS, looping=False))
    g = bp.function("EndHitMarker", doc="The crosshair back to white at 1x.")
    crosshair_look(g, WHITE, 1.0, ("entry", "then"))
    timed_show(bp, "ShowDamage", "HideDamage", "Vignette", IMAGE, DAMAGE_SECONDS,
               "A hit taken by the player's car (its TakeDamageInternal) or character: the red vignette for %g s." % DAMAGE_SECONDS, "The vignette off.")
    timed_show(bp, "ShowDrift", "HideDrift", "DriftText", TEXT_BLOCK, DRIFT_SECONDS,
               "A drift boost of the player's car: DRIFT for %g s." % DRIFT_SECONDS, "DRIFT off.")

    g = bp.event_graph()
    g.section("Tick: refresh everything, then bind the player's car and character (Phase 7 Task 18; a binding is added once)")
    tick = g.event(USER_WIDGET, "Tick", [struct_pin("MyGeometry", GEOMETRY), Pin("InDeltaTime", FLOAT)], col=0, row=1)
    r = g.call_self("Refresh", col=1, row=1)
    g.exec(tick, r)
    shot = g.custom_event("OnPlayerShot", [struct_pin("Hit", HIT_RESULT), Pin("bHit", BOOL)])  # BPC_DFWeapon.OnFired's parameters
    drift = g.custom_event("OnPlayerDriftBoost")                                                # BP_DFVehicle.OnDriftBoost's
    hurt = g.custom_event("OnPlayerHurt", [Pin("Damage", FLOAT)])                               # BP_DFCharacter.OnCharacterDamaged's
    own = g.call_self_native(WIDGET, "GetOwningPlayer", outputs=[obj_pin("ReturnValue", PLAYER_CONTROLLER, "out")], pure=True)
    pc = g.cast(PCC)
    g.link(own, "ReturnValue", pc, "Object")
    g.exec(r, pc)

    def bind(owner_class, delegate, target_src, event, prev):
        n = g.add_delegate_on(owner_class, delegate)
        g.link(target_src[0], target_src[1], n, "self")
        g.link(event, "OutputDelegate", n, "Delegate")
        g.link(prev[0], prev[1], n, "execute")
        return n

    def weapon_of(cls, owner):
        n = g.var_get_on(cls, "Weapon", OBJECT, cls_ref(gen(BPC_WEAPON)))
        g.link(owner[0], owner[1], n, "self")
        return (n, "Weapon")

    car = get_on(g, PCC, "CurrentVehicle", OBJECT, (pc, as_pin(BP_PC)), sub=cls_ref(VC))
    car_ok = is_valid(g)
    g.link(car[0], car[1], car_ok, "Object")
    bcar = g.branch()
    g.note(bcar, "in a car? its gun and its drift boosts")
    g.link(car_ok, "ReturnValue", bcar, "Condition")
    g.link(pc, "then", bcar, "execute")
    car_gun = bind(gen(BPC_WEAPON), "OnFired", weapon_of(VC, car), shot, (bcar, "then"))
    car_drift = bind(VC, "OnDriftBoost", car, drift, (car_gun, "then"))
    ch = get_on(g, PCC, "OnFootCharacter", OBJECT, (pc, as_pin(BP_PC)), sub=cls_ref(CC))
    ch_ok = is_valid(g)
    g.link(ch[0], ch[1], ch_ok, "Object")
    bch = g.branch()
    g.note(bch, "the character: its rifle and its hits taken")
    g.link(ch_ok, "ReturnValue", bch, "Condition")
    g.exec(car_drift, bch)
    g.link(bcar, "else", bch, "execute")
    ch_gun = bind(gen(BPC_WEAPON), "OnFired", weapon_of(CC, ch), shot, (bch, "then"))
    bind(CC, "OnCharacterDamaged", ch, hurt, (ch_gun, "then"))

    # fix round 1 (controller ruling, spec §7.2 "on a hit"): only a hit on a car or a character is a target; the road, the
    # ground, a rock or a crate block the trace too (bHit) but get no marker
    g.section("The player's shot hit a car or a character: the hit marker")
    what = g.call_static(GAMEPLAY, "BreakHitResult", inputs=[struct_pin("Hit", HIT_RESULT)], outputs=[obj_pin("HitActor", ACTOR, "out")], pure=True)
    g.link(shot, "Hit", what, "Hit")
    on_car = g.cast(VC)
    g.note(on_car, "a car?")
    g.link(what, "HitActor", on_car, "Object")
    g.exec(shot, on_car)
    on_person = g.cast(CC)
    g.note(on_person, "a character?")
    g.link(what, "HitActor", on_person, "Object")
    g.link(on_car, "CastFailed", on_person, "execute")
    marker = g.call_self("HitMarker")
    g.link(on_car, "then", marker, "execute")
    g.link(on_person, "then", marker, "execute")
    g.section("The player's drift boost: DRIFT")
    g.exec(drift, g.call_self("ShowDrift"))
    g.section("The player's character took a hit: the vignette (the car's own hits come through its TakeDamageInternal)")
    g.exec(hurt, g.call_self("ShowDamage"))
    return bp


# ---------- summary ----------
def build_summary() -> WidgetBlueprint:
    bp = WidgetBlueprint(WBP_SUMMARY, description="The end-of-race summary with Retry and Quit.")
    bp.widget("Backdrop", BORDER, None, {"brush_color": [0, 0, 0, 0.65]}, {"anchors": [0, 0, 1, 1], "position": [0, 0], "size": [0, 0]})
    bp.widget("SummaryBox", VBOX, None, slot={"anchors": [0.5, 0.5, 0.5, 0.5], "alignment": [0.5, 0.5], "auto_size": True})
    bp.widget("TitleText", TEXT_BLOCK, "SummaryBox", text_props("RACE COMPLETE", 60, AMBER, "Center"), {"h_align": "Center", "padding": [0, 0, 0, 16]})
    bp.widget("PlaceText", TEXT_BLOCK, "SummaryBox", text_props("Place 1 of 1", 32, justify="Center"), {"h_align": "Center", "padding": [0, 0, 0, 8]})
    bp.widget("StatsText", TEXT_BLOCK, "SummaryBox", text_props("Score 0 / 300    Laps 0    Kills 0    Deaths 0", 26, justify="Center"),
              {"h_align": "Center", "padding": [0, 0, 0, 8]})
    # Phase 5 (spec §5.2): what the race unlocked, NEXT when the next track is open, QUIT became MENU
    bp.widget("UnlockText", TEXT_BLOCK, "SummaryBox", text_props("", 26, AMBER, "Center"), {"h_align": "Center", "padding": [0, 0, 0, 20]})
    bp.widget("ButtonRow", HBOX, "SummaryBox", slot={"h_align": "Center"})
    bp.widget("RetryButton", BUTTON, "ButtonRow", button_props(), slot={"padding": [0, 0, 24, 0]})
    bp.widget("RetryLabel", TEXT_BLOCK, "RetryButton", text_props("RETRY", 28, [0.05, 0.05, 0.05, 1], "Center"))
    bp.widget("NextButton", BUTTON, "ButtonRow", button_props(visibility="Collapsed"), slot={"padding": [0, 0, 24, 0]})
    bp.widget("NextLabel", TEXT_BLOCK, "NextButton", text_props("NEXT", 28, [0.05, 0.05, 0.05, 1], "Center"))
    bp.widget("MenuButton", BUTTON, "ButtonRow", button_props())
    bp.widget("MenuLabel", TEXT_BLOCK, "MenuButton", text_props("MENU", 28, [0.05, 0.05, 0.05, 1], "Center"))
    bp.variable("LevelIndex", "int", "0", "Dead Fire|Summary")  # the track just raced (NEXT starts LevelIndex + 1)
    add_text_helpers(bp)

    g = bp.function("ShowResult", doc="Fills the summary from the race result, the unlock line and NEXT from the GameInstance.",
                    inputs=["Result:" + struct_spec(S_RESULT), "ScoreRequirement:int", "LevelIndex:int"])
    br = g.break_struct(RESULT, [enum_pin(member(S_RESULT, "Reason"), "/Game/DeadFire/Data/E_DFRaceEndReason", direction="out"),
                                 Pin(member(S_RESULT, "bPassed"), BOOL), Pin(member(S_RESULT, "Rank"), INT),
                                 Pin(member(S_RESULT, "RacerCount"), INT), Pin(member(S_RESULT, "Score"), INT),
                                 Pin(member(S_RESULT, "Laps"), INT), Pin(member(S_RESULT, "Kills"), INT), Pin(member(S_RESULT, "Deaths"), INT)])
    g.link_entry("Result", br, RESULT.rsplit(".", 1)[1])
    reason = g.call_static(MATH, "Conv_ByteToInt", inputs=[Pin("InByte", "byte")], outputs=[Pin("ReturnValue", INT, "out")], pure=True)
    g.link(br, member(S_RESULT, "Reason"), reason, "InByte")
    death = compare(g, "EqualEqual_IntInt", INT, b="2")
    g.link(reason, "ReturnValue", death, "A")
    title = pick(g, "GAME OVER", pick(g, "RACE COMPLETE", "TIME UP", (br, member(S_RESULT, "bPassed"))), (death, "ReturnValue"))
    m = lambda n: (br, member(S_RESULT, n))
    n = label(g, "TitleText", title, ("entry", "then"))
    n = label(g, "PlaceText", cat(g, "Place ", s_int(g, m("Rank")), " of ", s_int(g, m("RacerCount"))), (n, "then"))
    req = ("entry", "ScoreRequirement")
    req_s = g.call_static("KismetStringLibrary", "Conv_IntToString", inputs=[Pin("InInt", INT)], outputs=[Pin("ReturnValue", STRING, "out")], pure=True)
    g.link_entry("ScoreRequirement", req_s, "InInt")
    n = label(g, "StatsText", cat(g, "Score ", s_int(g, m("Score")), " / ", (req_s, "ReturnValue"), "    Laps ", s_int(g, m("Laps")),
                                   "    Kills ", s_int(g, m("Kills")), "    Deaths ", s_int(g, m("Deaths"))), (n, "then"))
    keep = g.var_set("LevelIndex", INT)
    g.link_entry("LevelIndex", keep, "LevelIndex")
    g.exec(n, keep)
    gi = game_instance(g)
    g.exec(keep, gi)
    GI = (gi, as_pin(BP_GI))
    luv = get_on(g, GIC, "LastUnlockedVehicle", INT, GI)
    has_car = compare(g, "GreaterEqual_IntInt", INT, b="0")
    g.link(luv[0], luv[1], has_car, "A")
    vinfo = g.call_on(GIC, "GetVehicleInfo", inputs=[Pin("Index", INT)],
                      outputs=[Pin("Name", STRING, "out"), Pin("VehicleClass", "class", "out", cls_ref(VC)), Pin("UnlockLevel", INT, "out"),
                               Pin("Speed", INT, "out"), Pin("Acceleration", INT, "out"), Pin("Armor", INT, "out"), Pin("Boost", INT, "out"),
                               Pin("Description", STRING, "out")], pure=True)
    g.link(GI[0], GI[1], vinfo, "self")
    g.link(luv[0], luv[1], vinfo, "Index")
    car_line = pick(g, cat(g, "NEW CAR UNLOCKED: ", (vinfo, "Name")), "", (has_car, "ReturnValue"))
    bll = get_on(g, GIC, "bLastUnlockedLevel", BOOL, GI)
    nxt = math2(g, "Add_IntInt", INT, b="1")
    g.link_entry("LevelIndex", nxt, "A")
    linfo = g.call_on(GIC, "GetLevelInfo", inputs=[Pin("Index", INT)],
                      outputs=[Pin("Name", STRING, "out"), Pin("MapName", "name", "out"), Pin("Description", STRING, "out"),
                               Pin("ScoreRequirement", INT, "out"), Pin("TimeLimit", FLOAT, "out"), Pin("NPCCount", INT, "out")], pure=True)
    g.link(GI[0], GI[1], linfo, "self")
    g.link(nxt, "ReturnValue", linfo, "Index")
    track_line = pick(g, cat(g, "NEXT TRACK UNLOCKED: ", (linfo, "Name")), "", bll)
    both = and_bool(g)
    g.link(has_car, "ReturnValue", both, "A")
    g.link(bll[0], bll[1], both, "B")
    sep = pick(g, "   ", "", (both, "ReturnValue"))
    n = label(g, "UnlockText", cat(g, car_line, sep, track_line), (gi, "then"))
    clr_v = g.var_set_on(GIC, "LastUnlockedVehicle", INT, default="-1")
    g.link(GI[0], GI[1], clr_v, "self")
    g.exec(n, clr_v)
    clr_l = g.var_set_on(GIC, "bLastUnlockedLevel", BOOL, default="false")
    g.link(GI[0], GI[1], clr_l, "self")
    g.exec(clr_v, clr_l)
    # NEXT: passed, and the next track exists and is open
    count = g.call_on(GIC, "GetLevelCount", outputs=[Pin("Count", INT, "out")], pure=True)
    g.link(GI[0], GI[1], count, "self")
    exists = compare(g, "Less_IntInt", INT)
    g.link(nxt, "ReturnValue", exists, "A")
    g.link(count, "Count", exists, "B")
    open_ = g.call_on(GIC, "IsLevelUnlocked", inputs=[Pin("Index", INT)], outputs=[Pin("ReturnValue", BOOL, "out")], pure=True)
    g.link(GI[0], GI[1], open_, "self")
    g.link(nxt, "ReturnValue", open_, "Index")
    a1 = and_bool(g)
    g.link(exists, "ReturnValue", a1, "A")
    g.link(open_, "ReturnValue", a1, "B")
    show_next = and_bool(g)
    g.link(br, member(S_RESULT, "bPassed"), show_next, "A")
    g.link(a1, "ReturnValue", show_next, "B")
    bn = g.branch()
    g.note(bn, "offer NEXT?")
    g.link(show_next, "ReturnValue", bn, "Condition")
    g.exec(clr_l, bn)
    nb = g.var_get("NextButton", OBJECT, cls_ref(BUTTON))
    vis = g.call_on(WIDGET, "SetVisibility", inputs=[native_enum_pin("InVisibility", VIS, "Visible")])
    g.link(nb, "NextButton", vis, "self")
    g.link(bn, "then", vis, "execute")
    hid = g.call_on(WIDGET, "SetVisibility", inputs=[native_enum_pin("InVisibility", VIS, "Collapsed")])
    g.link(nb, "NextButton", hid, "self")
    g.link(bn, "else", hid, "execute")
    # without our GameInstance: no line, no NEXT
    blank = label(g, "UnlockText", cat(g, ""), (gi, "CastFailed"))
    hid2 = g.call_on(WIDGET, "SetVisibility", inputs=[native_enum_pin("InVisibility", VIS, "Collapsed")])
    g.link(nb, "NextButton", hid2, "self")
    g.exec(blank, hid2)

    g = bp.event_graph()
    g.section("Retry: reload the level (through the GameInstance's fade when it is ours)")
    retry = g.component_event("RetryButton", "OnClicked", BUTTON, [], "OnButtonClickedEvent__DelegateSignature", UMG, col=0, row=1)
    own = g.call_self_native(WIDGET, "GetOwningPlayer", outputs=[obj_pin("ReturnValue", PLAYER_CONTROLLER, "out")], pure=True, col=1, row=2)
    gonly = g.call_static("WidgetBlueprintLibrary", "SetInputMode_GameOnly", inputs=[obj_pin("PlayerController", PLAYER_CONTROLLER)], module="UMG", col=2, row=1)
    g.link(own, "ReturnValue", gonly, "PlayerController")
    g.exec(retry, gonly)
    gi = game_instance(g)
    g.exec(gonly, gi)
    reload = g.call_on(GIC, "ReloadCurrentLevel")
    g.link(gi, as_pin(BP_GI), reload, "self")
    g.link(gi, "then", reload, "execute")
    lvl = g.call_static(GAMEPLAY, "GetCurrentLevelName", inputs=[Pin("WorldContextObject", OBJECT, hidden=True), Pin("bRemovePrefixString", BOOL, default="true")],
                        outputs=[Pin("ReturnValue", STRING, "out")], col=3, row=1)
    g.link(gi, "CastFailed", lvl, "execute")
    nm = g.call_static("KismetStringLibrary", "Conv_StringToName", inputs=[Pin("InString", STRING)], outputs=[Pin("ReturnValue", "name", "out")], pure=True, col=3, row=2)
    g.link(lvl, "ReturnValue", nm, "InString")
    op = g.call_static(GAMEPLAY, "OpenLevel", inputs=[Pin("WorldContextObject", OBJECT, hidden=True), Pin("LevelName", "name"),
                                                        Pin("bAbsolute", BOOL, default="true"), Pin("Options", STRING, default="")], col=4, row=1)
    g.link(nm, "ReturnValue", op, "LevelName")
    g.exec(lvl, op)
    g.section("Next: the next track with the same car")
    nxt_ev = g.component_event("NextButton", "OnClicked", BUTTON, [], "OnButtonClickedEvent__DelegateSignature", UMG, col=0, row=3)
    gi2 = game_instance(g)
    g.exec(nxt_ev, gi2)
    nxt_i = math2(g, "Add_IntInt", INT, b="1")
    g.link(g.var_get("LevelIndex", INT), "LevelIndex", nxt_i, "A")
    sel = g.var_set_on(GIC, "SelectedLevel", INT)
    g.link(gi2, as_pin(BP_GI), sel, "self")
    g.link(nxt_i, "ReturnValue", sel, "SelectedLevel")
    g.link(gi2, "then", sel, "execute")
    start = g.call_on(GIC, "StartRace")
    g.link(gi2, as_pin(BP_GI), start, "self")
    g.exec(sel, start)

    g.section("Menu: back to the main menu (quit when the GameInstance is not ours)")
    menu = g.component_event("MenuButton", "OnClicked", BUTTON, [], "OnButtonClickedEvent__DelegateSignature", UMG, col=0, row=5)
    gi3 = game_instance(g)
    g.exec(menu, gi3)
    back = g.call_on(GIC, "OpenMainMenu")
    g.link(gi3, as_pin(BP_GI), back, "self")
    g.link(gi3, "then", back, "execute")
    own2 = g.call_self_native(WIDGET, "GetOwningPlayer", outputs=[obj_pin("ReturnValue", PLAYER_CONTROLLER, "out")], pure=True, col=1, row=4)
    q = g.call_static("KismetSystemLibrary", "QuitGame", inputs=[Pin("WorldContextObject", OBJECT, hidden=True), obj_pin("SpecificPlayer", PLAYER_CONTROLLER),
                                                                  native_enum_pin("QuitPreference", "/Script/Engine.EQuitPreference", "Quit"),
                                                                  Pin("bIgnorePlatformRestrictions", BOOL, default="false")], col=2, row=3)
    g.link(own2, "ReturnValue", q, "SpecificPlayer")
    g.link(gi3, "CastFailed", q, "execute")
    return bp


# ---------- HUD actor ----------
def build_hud_actor() -> Blueprint:
    bp = Blueprint(BP_HUD, parent="/Script/Engine.HUD", description="Creates the race HUD at start and the summary at race end.")
    U = "Dead Fire|HUD"
    bp.variable("HUDWidgetClass", "class:" + USER_WIDGET, "", U, editable=True)
    bp.variable("SummaryWidgetClass", "class:" + USER_WIDGET, "", U, editable=True)
    bp.variable("HUDWidget", "object:" + USER_WIDGET, "", U)
    bp.variable("SummaryWidget", "object:" + WSUM, "", U)
    bp.default("HUDWidgetClass", "class:" + WBP_HUD)
    bp.default("SummaryWidgetClass", "class:" + WBP_SUMMARY)

    def owner(g):
        return g.call_self_native("/Script/Engine.HUD", "GetOwningPlayerController", outputs=[obj_pin("ReturnValue", PLAYER_CONTROLLER, "out")], pure=True)

    # ShowRaceHUD: summary off, race HUD on (created once)
    g = bp.function("ShowRaceHUD", doc="Summary off, race HUD on (created once).")
    sw = g.var_get("SummaryWidget", OBJECT, cls_ref(WSUM))
    sv = is_valid(g)
    g.link(sw, "SummaryWidget", sv, "Object")
    b = g.branch()
    g.link(sv, "ReturnValue", b, "Condition")
    g.link_entry("then", b, "execute")
    rm = g.call_on(WIDGET, "RemoveFromParent")
    g.link(sw, "SummaryWidget", rm, "self")
    g.link(b, "then", rm, "execute")
    clr = g.var_set("SummaryWidget", OBJECT, sub_object=cls_ref(WSUM))
    g.exec(rm, clr)
    hw = g.var_get("HUDWidget", OBJECT, cls_ref(USER_WIDGET))
    hv = is_valid(g)
    g.link(hw, "HUDWidget", hv, "Object")
    bh = g.branch()
    g.link(hv, "ReturnValue", bh, "Condition")
    g.exec(clr, bh)
    g.link(b, "else", bh, "execute")
    o = owner(g)
    cw = g.create_widget()
    hc = g.var_get("HUDWidgetClass", "class", cls_ref(USER_WIDGET))
    g.link(hc, "HUDWidgetClass", cw, "Class")
    g.link(o, "ReturnValue", cw, "OwningPlayer")
    g.link(bh, "else", cw, "execute")
    sh = g.var_set("HUDWidget", OBJECT, sub_object=cls_ref(USER_WIDGET))
    g.link(cw, "ReturnValue", sh, "HUDWidget")
    g.exec(cw, sh)
    hw2 = g.var_get("HUDWidget", OBJECT, cls_ref(USER_WIDGET))
    inv = g.call_on(USER_WIDGET, "IsInViewport", outputs=[Pin("ReturnValue", BOOL, "out")], pure=True)
    g.link(hw2, "HUDWidget", inv, "self")
    hv2 = is_valid(g)
    g.link(hw2, "HUDWidget", hv2, "Object")
    ni = not_bool(g)
    g.link(inv, "ReturnValue", ni, "A")
    need = and_bool(g)
    g.link(hv2, "ReturnValue", need, "A")
    g.link(ni, "ReturnValue", need, "B")
    bv = g.branch()
    g.link(need, "ReturnValue", bv, "Condition")
    g.exec(sh, bv)
    g.link(bh, "then", bv, "execute")
    add = g.call_on(USER_WIDGET, "AddToViewport", inputs=[Pin("ZOrder", INT, default="0")])
    g.link(hw2, "HUDWidget", add, "self")
    g.link(bv, "then", add, "execute")

    # ShowSummary: race HUD off, summary on with the result, UI input
    g = bp.function("ShowSummary", doc="Race HUD off, summary on with the result, UI input.")
    hw = g.var_get("HUDWidget", OBJECT, cls_ref(USER_WIDGET))
    hv = is_valid(g)
    g.link(hw, "HUDWidget", hv, "Object")
    b = g.branch()
    g.link(hv, "ReturnValue", b, "Condition")
    g.link_entry("then", b, "execute")
    rm = g.call_on(WIDGET, "RemoveFromParent")
    g.link(hw, "HUDWidget", rm, "self")
    g.link(b, "then", rm, "execute")
    o = owner(g)
    sw = g.var_get("SummaryWidget", OBJECT, cls_ref(WSUM))
    sv = is_valid(g)
    g.link(sw, "SummaryWidget", sv, "Object")
    bs = g.branch()
    g.link(sv, "ReturnValue", bs, "Condition")
    g.exec(rm, bs)
    g.link(b, "else", bs, "execute")
    cw = g.create_widget()
    sc = g.var_get("SummaryWidgetClass", "class", cls_ref(USER_WIDGET))
    g.link(sc, "SummaryWidgetClass", cw, "Class")
    g.link(o, "ReturnValue", cw, "OwningPlayer")
    g.link(bs, "else", cw, "execute")
    cast = g.cast(WSUM)
    g.link(cw, "ReturnValue", cast, "Object")
    g.exec(cw, cast)
    ss = g.var_set("SummaryWidget", OBJECT, sub_object=cls_ref(WSUM))
    g.link(cast, as_pin(WBP_SUMMARY), ss, "SummaryWidget")
    g.link(cast, "then", ss, "execute")
    gs_ = g.call_static(GAMEPLAY, "GetGameState", inputs=[Pin("WorldContextObject", OBJECT, hidden=True)],
                        outputs=[obj_pin("ReturnValue", "/Script/Engine.GameStateBase", "out")], pure=True)
    gs = g.cast(GSC)
    g.link(gs_, "ReturnValue", gs, "Object")
    g.exec(ss, gs)
    g.link(bs, "then", gs, "execute")
    gm_ = g.call_static(GAMEPLAY, "GetGameMode", inputs=[Pin("WorldContextObject", OBJECT, hidden=True)],
                        outputs=[obj_pin("ReturnValue", "/Script/Engine.GameModeBase", "out")], pure=True)
    gm = g.cast(GMC)
    g.link(gm_, "ReturnValue", gm, "Object")
    g.link(gs, "then", gm, "execute")
    sw2 = g.var_get("SummaryWidget", OBJECT, cls_ref(WSUM))
    res = g.var_get_on(GSC, "Result", STRUCT, struct_ref(RESULT))
    g.link(gs, as_pin(BP_GS), res, "self")
    req = g.var_get_on(GMC, "ScoreRequirement", INT)
    g.link(gm, as_pin(BP_GM), req, "self")
    show = g.call_on(WSUM, "ShowResult", inputs=[Pin("Result", STRUCT, sub_object=struct_ref(RESULT)), Pin("ScoreRequirement", INT), Pin("LevelIndex", INT)])
    g.link(sw2, "SummaryWidget", show, "self")
    g.link(res, "Result", show, "Result")
    g.link(req, "ScoreRequirement", show, "ScoreRequirement")
    lvl = g.var_get_on(GMC, "LevelIndex", INT)  # Phase 5: the summary's NEXT and unlock line need the track just raced
    g.link(gm, as_pin(BP_GM), lvl, "self")
    g.link(lvl, "LevelIndex", show, "LevelIndex")
    g.link(gm, "then", show, "execute")
    inv = g.call_on(USER_WIDGET, "IsInViewport", outputs=[Pin("ReturnValue", BOOL, "out")], pure=True)
    g.link(sw2, "SummaryWidget", inv, "self")
    bi = g.branch()
    g.link(inv, "ReturnValue", bi, "Condition")
    g.exec(show, bi)
    add = g.call_on(USER_WIDGET, "AddToViewport", inputs=[Pin("ZOrder", INT, default="10")])
    g.link(sw2, "SummaryWidget", add, "self")
    g.link(bi, "else", add, "execute")
    ui = g.call_static("WidgetBlueprintLibrary", "SetInputMode_UIOnlyEx",
                       inputs=[obj_pin("PlayerController", PLAYER_CONTROLLER), obj_pin("InWidgetToFocus", WIDGET),
                               native_enum_pin("InMouseLockMode", "/Script/UMG.EMouseLockMode", "DoNotLock")], module="UMG")
    g.link(o, "ReturnValue", ui, "PlayerController")
    # focus the Retry button (focusable, so keyboard/gamepad can confirm; the user widget itself is not focusable)
    retry = g.var_get_on(WSUM, "RetryButton", OBJECT, cls_ref(BUTTON))
    g.link(sw2, "SummaryWidget", retry, "self")
    g.link(retry, "RetryButton", ui, "InWidgetToFocus")
    g.exec(add, ui)
    g.link(bi, "then", ui, "execute")

    g = bp.event_graph()
    g.section("Begin Play: show the race HUD")
    bpl = g.begin_play(col=0, row=1)
    show = g.call_self("ShowRaceHUD", col=1, row=1)
    g.exec(bpl, show)
    return bp


def build():
    return [build_hud(), build_summary(), build_hud_actor()]


if __name__ == "__main__":
    for b in build():
        print(b.write(OUT))
