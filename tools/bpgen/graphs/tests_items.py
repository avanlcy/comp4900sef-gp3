"""Phase 3 FT_DF* tests (plan docs/superpowers/plans/2026-10-30-phase3-items.md): inventory, items, explosions, bombs,
rockets, loot boxes, destructibles, the shortcut track and the HUD item row. Same shape as tests.py (one FunctionalTest
child per rule with a straight Start Test chain; df_build_test_track.py places them); the helpers come from tests.py.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, ".."))
from bpgen import cls_ref, struct_ref  # noqa: E402,F401
from df import (ACTOR, BOOL, BP_BOMB, BP_CHARACTER, BP_DESTRUCTIBLE, BP_EXPLOSIVE_DAMAGE, BP_GM, BP_LOOTBOX, BP_PC,  # noqa: E402
                BP_PROJECTILE, BP_TRACK, BP_VEHICLE, BPC_RACER, CONTROLLER, DAMAGE_TYPE, E_ITEM_TYPE, FLOAT, GAMEPLAY,
                HIT_RESULT, INT, ITEM_BOMB, ITEM_BOOST, ITEM_GUN, ITEM_SHIELD, MATH, OBJECT, OUT, PAWN, ROTATOR, S_ITEM_STACK,
                SPLINE_COMP, STRING, STRUCT, TRANSFORM, VECTOR, WBP_HUD, Pin, as_pin, enum_pin, enum_value, gen,
                get_all_actors_of_class, is_valid, obj_pin, struct_path, struct_pin)
from tests import T, race_context, spawn_character, spawn_vehicle, tire  # noqa: E402
from df import art_icon, asset_object, enum_is, native_enum_pin, not_bool, or_bool  # noqa: E402  (Phase 7 Task 18)

RC, GMC, VC, CC, PCC, BOMBC, PROJC, LOOTC = (gen(BPC_RACER), gen(BP_GM), gen(BP_VEHICLE), gen(BP_CHARACTER), gen(BP_PC), gen(BP_BOMB),
                                            gen(BP_PROJECTILE), gen(BP_LOOTBOX))
DESTC, TC, WHUD = gen(BP_DESTRUCTIBLE), gen(BP_TRACK), gen(WBP_HUD)
TEXT_BLOCK = "/Script/UMG.TextBlock"
ITEM_ENUM = enum_pin("x", E_ITEM_TYPE).sub_object
ITEM = struct_path(S_ITEM_STACK)
ARR = "KismetArrayLibrary"


# ---- helpers ----
def enum_int(t: T, src):
    n = t.g.call_static(MATH, "Conv_ByteToInt", inputs=[Pin("InByte", "byte")], outputs=[Pin("ReturnValue", INT, "out")], pure=True)
    t.link(src, n, "InByte")
    return (n, "ReturnValue")


def inventory_length(t: T, racer):
    arr = t.get(RC, "Inventory", STRUCT, racer, sub=struct_ref(ITEM), container="Array")
    n = t.g.call_array(ARR, "Array_Length", Pin("e", STRUCT, sub_object=struct_ref(ITEM)), outputs=[Pin("ReturnValue", INT, "out")])
    t.link(arr, n, "TargetArray")
    return (n, "ReturnValue")


def add_item(t: T, racer, item, charges, max_charges):
    n = t.call(RC, "AddItem", racer, inputs=[enum_pin("Type", E_ITEM_TYPE, default=item), Pin("Charges", INT, default=str(charges)),
                                            Pin("MaxCharges", INT, default=str(max_charges))],
               outputs=[Pin("ReturnValue", BOOL, "out")])
    return (n, "ReturnValue")


def selected(t: T, racer):
    return t.call(RC, "GetSelected", racer, outputs=[enum_pin("Type", E_ITEM_TYPE, "out"), Pin("Charges", INT, "out")], pure=True)


def consume(t: T, racer):
    n = t.call(RC, "ConsumeSelected", racer, outputs=[enum_pin("Type", E_ITEM_TYPE, "out")])
    return (n, "Type")


def blown_tires(t: T, car):
    n = t.g.call_on(VC, "GetBlownTireCount", outputs=[Pin("Count", INT, "out")], pure=True)
    t.link(car, n, "self")
    return (n, "Count")


def player_car(t: T, pc):
    """The car the player controller currently drives (CurrentVehicle)."""
    return t.get(PCC, "CurrentVehicle", OBJECT, pc, sub=cls_ref(VC))


def pawn_car(t: T, pc):
    """The player's pawn cast to BP_DFVehicle (after a restart the CurrentVehicle variable may lag a frame)."""
    pawn = t.g.call_on(CONTROLLER, "K2_GetPawn", outputs=[obj_pin("ReturnValue", PAWN, "out")], pure=True)
    t.link(pc, pawn, "self")
    c = t.step(t.g.cast(VC))
    t.g.link(pawn, "ReturnValue", c, "Object")
    return (c, as_pin("/Game/DeadFire/Blueprints/BP_DFVehicle"))


def grant(t: T, gm, pc, item, charges=1):
    n = t.call(GMC, "GrantItem", gm, inputs=[obj_pin("C", CONTROLLER), enum_pin("Type", E_ITEM_TYPE, default=item),
                                              Pin("Charges", INT, default=str(charges))],
               outputs=[Pin("ReturnValue", BOOL, "out")])
    t.link(pc, n, "C")
    return (n, "ReturnValue")


def use_item(t: T, car):
    n = t.call(VC, "UseSelectedItem", car, outputs=[Pin("ReturnValue", BOOL, "out")])
    return (n, "ReturnValue")


def invalid(t: T, obj, message):
    v = is_valid(t.g)
    t.link(obj, v, "Object")
    t.false((v, "ReturnValue"), message)


def count_actors(t: T, cls):
    n = t.step(get_all_actors_of_class(t.g, cls))
    return t.length((n, "OutActors"), cls)


def move_to(t: T, actor, loc):
    n = t.call(ACTOR, "K2_SetActorLocation", actor,
               inputs=[struct_pin("NewLocation", VECTOR), Pin("bSweep", BOOL, default="false"), Pin("bTeleport", BOOL, default="true")],
               outputs=[struct_pin("SweepHitResult", HIT_RESULT, "out"), Pin("ReturnValue", BOOL, "out")])
    t.link(loc, n, "NewLocation")
    return n


def park_player(t: T, pc):
    """TeleportAndStop the player's car onto this test's spot, facing +X (RestartRace puts it back on the line)."""
    car = player_car(t, pc)
    n = t.call(VC, "TeleportAndStop", car, inputs=[struct_pin("NewTransform", TRANSFORM)])
    t.link(t.transform(t.offset(t.self_loc(), 0.0, 0.0, -100.0)), n, "NewTransform")
    return car


def destroy(t: T, actor):
    return t.call(ACTOR, "K2_DestroyActor", actor)


def fire_rpg(t: T, car):
    n = t.call(VC, "FireRPG", car, outputs=[obj_pin("Projectile", PROJC, "out")])
    return (n, "Projectile")


def spawn_crate(t: T, item, dx=0.0, dy=0.0):
    """A BP_DFLootBox at this test's spot holding one item of the given type."""
    crate = t.spawn(LOOTC, t.offset(t.self_loc(), dx, dy, -150.0))
    t.set(LOOTC, "ItemType", "byte", crate, default=enum_value(item), sub=ITEM_ENUM)
    return crate


def owned_character(t: T, pc, dx=600.0, dy=0.0):
    """An on-foot character 6 m from the spot, owned by the player controller (so pickups reach the player's racer)."""
    ch = spawn_character(t, dx, dy)
    t.set(CC, "OwningController", OBJECT, ch, value=pc, sub=cls_ref(CONTROLLER))
    return ch


def widgets(t: T, cls, top_level=True):
    n = t.static("WidgetBlueprintLibrary", "GetAllWidgetsOfClass",
                 inputs=[Pin("WorldContextObject", OBJECT, hidden=True),
                         Pin("WidgetClass", "class", sub_object=cls_ref("/Script/UMG.UserWidget"), default_object=cls),
                         Pin("TopLevelOnly", BOOL, default="true" if top_level else "false")],
                 outputs=[Pin("FoundWidgets", OBJECT, "out", cls_ref(cls), container="Array")], module="UMG")
    return (n, "FoundWidgets")


def text_reads(t: T, text_block, expected, message):
    """AssertTrue(TextBlock.GetText == expected)."""
    txt = t.g.call_on(TEXT_BLOCK, "GetText", outputs=[Pin("ReturnValue", "text", "out")], pure=True)
    t.link(text_block, txt, "self")
    as_str = t.g.call_static("KismetTextLibrary", "Conv_TextToString", inputs=[Pin("InText", "text")], outputs=[Pin("ReturnValue", STRING, "out")], pure=True)
    t.g.link(txt, "ReturnValue", as_str, "InText")
    eq = t.g.call_static("KismetStringLibrary", "EqualEqual_StrStr", inputs=[Pin("A", STRING), Pin("B", STRING, default=expected)],
                         outputs=[Pin("ReturnValue", BOOL, "out")], pure=True)
    t.g.link(as_str, "ReturnValue", eq, "A")
    t.true((eq, "ReturnValue"), message)


def spawn_bomb(t: T, dx=0.0, dy=0.0):
    return t.spawn(BOMBC, t.offset(t.self_loc(), dx, dy, -150.0))


def greater(t: T, a, b_value):
    n = t.g.call_static(MATH, "Greater_FloatFloat", inputs=[Pin("A", FLOAT), Pin("B", FLOAT, default="%f" % b_value)],
                        outputs=[Pin("ReturnValue", BOOL, "out")], pure=True)
    t.link(a, n, "A")
    return (n, "ReturnValue")


def explode(t: T, gm, at, damage, radius, instigator=None, blow_tires=True):
    """GameMode.SpawnExplosion(at, damage, radius, instigator, no causer, blow_tires)."""
    n = t.call(GMC, "SpawnExplosion", gm, inputs=[struct_pin("Location", VECTOR), Pin("Damage", FLOAT, default="%f" % damage),
                                                   Pin("Radius", FLOAT, default="%f" % radius), obj_pin("InstigatedBy", CONTROLLER),
                                                   obj_pin("Causer", ACTOR), Pin("bBlowTires", BOOL, default="true" if blow_tires else "false")])
    t.link(at, n, "Location")
    if instigator:
        t.link(instigator, n, "InstigatedBy")
    return n


# ---- Task 0: inventory ----
def inventory_tests():
    t = T("FT_DFItem_InventoryStacksAndCaps", "Items stack to their cap, a fourth type is refused, cycling and consuming walk the slots.")
    pc, gm, gs, racer, gates = race_context(t)
    t.true(add_item(t, racer, ITEM_SHIELD, 1, 2), "first shield added")
    t.true(add_item(t, racer, ITEM_SHIELD, 1, 2), "second shield stacks")
    t.false(add_item(t, racer, ITEM_SHIELD, 1, 2), "third shield refused at the cap")
    t.true(add_item(t, racer, ITEM_BOOST, 1, 3), "boost added")
    t.true(add_item(t, racer, ITEM_BOMB, 1, 3), "bomb added")
    t.false(add_item(t, racer, ITEM_GUN, 8, 24), "fourth type refused: no free slot")
    t.eq_int(inventory_length(t, racer), 3, "slots in use")
    s = selected(t, racer)
    t.eq_int(enum_int(t, (s, "Type")), ITEM_SHIELD, "selected type is shield")
    t.eq_int((s, "Charges"), 2, "selected charges")
    t.call(RC, "CycleSelected", racer)
    t.eq_int(t.get(RC, "SelectedSlot", INT, racer), 1, "selected slot after one cycle")
    t.call(RC, "CycleSelected", racer)
    t.call(RC, "CycleSelected", racer)
    t.eq_int(t.get(RC, "SelectedSlot", INT, racer), 0, "selection wraps to slot 0")
    t.eq_int(enum_int(t, consume(t, racer)), ITEM_SHIELD, "first consume returns shield")
    t.eq_int(enum_int(t, consume(t, racer)), ITEM_SHIELD, "second consume returns shield")
    t.eq_int(inventory_length(t, racer), 2, "empty stack removed")
    s2 = selected(t, racer)
    t.eq_int(enum_int(t, (s2, "Type")), ITEM_BOOST, "selection moves to the first slot (boost)")
    t.call(RC, "ClearInventory", racer)
    t.eq_int(inventory_length(t, racer), 0, "inventory cleared")
    return [t.finish()]


# ---- Task 1: explosions ----
def explosion_tests():
    t = T("FT_DFExplosion_DamagesKicksAndBlowsTire", "An explosion damages a car in range for the full amount, blows its nearest tire, "
          "spares a character beside it; an effects-only explosion hurts nobody.")
    pc, gm, gs, racer, gates = race_context(t)
    car = spawn_vehicle(t)
    ch = spawn_character(t, 0.0, 200.0)
    t.delay(1.0)
    explode(t, gm, t.offset(t.loc(car), 150.0, 0.0, 0.0), 60.0, 500.0, pc)
    t.eq_float(t.get(VC, "Health", FLOAT, car), 40.0, "car health after a 60-point explosion", 0.5)
    t.eq_int(blown_tires(t, car), 1, "one tire blown by the blast")
    t.eq_float(t.get(CC, "Health", FLOAT, ch), 100.0, "character beside the blast unhurt")
    car2 = spawn_vehicle(t, 800.0)
    t.delay(0.5)
    explode(t, gm, t.loc(car2), 0.0, 500.0, None, False)
    t.eq_float(t.get(VC, "Health", FLOAT, car2), 100.0, "effects-only explosion does no damage")
    t.eq_int(blown_tires(t, car2), 0, "effects-only explosion blows no tire")
    return [t.finish()]


# ---- Task 2: effects and item use ----
def item_use_tests():
    out = []
    t = T("FT_DFItem_UseConsumesAndRefusesWhenEmpty", "Using the selected item consumes one charge; an empty inventory and a wrecked car refuse.")
    pc, gm, gs, racer, gates = race_context(t)
    t.true(grant(t, gm, pc, ITEM_BOOST), "boost granted")
    car = player_car(t, pc)
    t.true(use_item(t, car), "use consumes the boost")
    t.eq_int(inventory_length(t, racer), 0, "inventory empty after the use")
    t.false(use_item(t, car), "empty inventory refuses")
    t.true(grant(t, gm, pc, ITEM_SHIELD), "shield granted")
    t.call(VC, "DestroyVehicle", car, inputs=[obj_pin("Killer", CONTROLLER)])
    t.false(use_item(t, car), "a wrecked car refuses")
    t.eq_int(inventory_length(t, racer), 1, "nothing consumed by the refused use")
    out.append(t.finish())

    t = T("FT_DFItem_BoostKicksCar", "Boost sets its timer and kicks the car to at least 35 km/h at once; ClearEffects ends it.")
    pc, gm, gs, racer, gates = race_context(t)
    car = player_car(t, pc)
    t.call(VC, "ActivateBoost", car)
    t.true(greater(t, t.get(VC, "BoostRemaining", FLOAT, car), 1.5), "boost timer running")
    t.delay(0.2)
    sp = t.g.call_on(VC, "GetSpeedKPH", outputs=[Pin("KPH", FLOAT, "out")], pure=True)
    t.link(car, sp, "self")
    t.true(greater(t, (sp, "KPH"), 35.0), "kicked above 35 km/h")
    t.call(VC, "ClearEffects", car)
    t.eq_float(t.get(VC, "BoostRemaining", FLOAT, car), 0.0, "boost cleared")
    out.append(t.finish())

    t = T("FT_DFItem_ShieldBlocksDamage", "While shielded, body and tire damage are ignored; after the shield they apply.")
    pc, gm, gs, racer, gates = race_context(t)
    car = spawn_vehicle(t)
    t.delay(1.0)
    t.call(VC, "ActivateShield", car)
    sh = t.g.call_on(VC, "IsShielded", outputs=[Pin("ReturnValue", BOOL, "out")], pure=True)
    t.link(car, sh, "self")
    t.true((sh, "ReturnValue"), "shield active")
    t.damage(car, 50)
    t.eq_float(t.get(VC, "Health", FLOAT, car), 100.0, "body damage ignored while shielded")
    t.point_damage(car, 30, "Wheel_Front_Left")
    t.false(tire(t, car, 0, "bBlown", BOOL), "tire damage ignored while shielded")
    t.call(VC, "ClearEffects", car)
    t.damage(car, 50)
    t.eq_float(t.get(VC, "Health", FLOAT, car), 50.0, "damage applies after the shield")
    out.append(t.finish())

    t = T("FT_DFItem_RestartClearsItemsAndEffects", "RestartRace empties the inventory and clears the car's effects.")
    pc, gm, gs, racer, gates = race_context(t)
    t.true(grant(t, gm, pc, ITEM_SHIELD), "shield granted")
    t.call(VC, "ActivateShield", player_car(t, pc))
    t.call(VC, "DropBomb", player_car(t, pc), outputs=[obj_pin("Bomb", BOMBC, "out")])
    t.call(GMC, "RestartRace", gm)
    t.delay(0.5)
    t.eq_int(inventory_length(t, racer), 0, "inventory cleared by the restart")
    t.eq_int(count_actors(t, BOMBC), 0, "no bomb left after the restart")
    t.eq_float(t.get(VC, "ShieldRemaining", FLOAT, pawn_car(t, pc)), 0.0, "shield cleared by the restart")
    out.append(t.finish())
    return out


# ---- Task 3: bombs ----
def bomb_tests():
    out = []
    t = T("FT_DFBomb_ArmedBombDamagesAndBlowsTire", "A dropped bomb starts unarmed and leaves its dropper alone; an armed bomb under a car "
          "damages it, blows a tire and disappears.")
    pc, gm, gs, racer, gates = race_context(t)
    mine = t.call(VC, "DropBomb", player_car(t, pc), outputs=[obj_pin("Bomb", BOMBC, "out")])
    t.valid((mine, "Bomb"), "DropBomb spawned a bomb")
    t.false(t.get(BOMBC, "bArmed", BOOL, (mine, "Bomb")), "a fresh bomb is unarmed")
    t.delay(0.5)
    t.eq_float(t.get(VC, "Health", FLOAT, player_car(t, pc)), 100.0, "the dropper is untouched")
    bomb = spawn_bomb(t, 0.0, 600.0)
    t.call(BOMBC, "Arm", bomb)
    car = spawn_vehicle(t, 0.0, 1400.0)
    t.delay(1.0)
    move_to(t, car, t.offset(t.self_loc(), 0.0, 600.0, -100.0))
    t.delay(1.5)
    t.eq_float(t.get(VC, "Health", FLOAT, car), 40.0, "car health after the bomb", 0.5)
    t.eq_int(blown_tires(t, car), 1, "one tire blown by the bomb")
    invalid(t, bomb, "the bomb is gone after detonating")
    out.append(t.finish())

    t = T("FT_DFBomb_FuseDetonates", "With its fuse run out a bomb detonates on its own and damages a car 3 m away.")
    pc, gm, gs, racer, gates = race_context(t)
    bomb = spawn_bomb(t)
    t.set(BOMBC, "ArmDelay", FLOAT, bomb, default="0.0")
    t.set(BOMBC, "FuseSeconds", FLOAT, bomb, default="0.3")
    car = spawn_vehicle(t, 300.0)
    t.delay(1.5)
    t.eq_float(t.get(VC, "Health", FLOAT, car), 40.0, "car health after the fuse detonation", 0.5)
    invalid(t, bomb, "the bomb is gone after the fuse")
    out.append(t.finish())
    return out


# ---- Task 4: gun and rocket ----
def gun_and_rocket_tests():
    out = []
    t = T("FT_DFItem_GunShotHitsCarAhead", "The car's gun hits a car 8 m ahead for 15.")
    pc, gm, gs, racer, gates = race_context(t)
    car = park_player(t, pc)
    target = spawn_vehicle(t, 800.0)
    t.delay(1.0)
    shot = t.call(VC, "FireGun", car, outputs=[Pin("ReturnValue", BOOL, "out")])
    t.true((shot, "ReturnValue"), "the gun hit something")
    t.eq_float(t.get(VC, "Health", FLOAT, target), 85.0, "target health after one gun shot", 0.5)
    destroy(t, target)
    out.append(t.finish())

    t = T("FT_DFProjectile_ExplodesOnHitAndCreditsKill", "A rocket fired at a car 10 m ahead explodes on it; a lethal rocket credits the shooter "
          "with a kill and +50.")
    pc, gm, gs, racer, gates = race_context(t)
    car = park_player(t, pc)
    target = spawn_vehicle(t, 1000.0)
    t.delay(1.0)
    rocket = fire_rpg(t, car)
    t.valid(rocket, "FireRPG spawned a rocket")
    t.delay(1.5)
    t.eq_float(t.get(VC, "Health", FLOAT, target), 20.0, "target health after one rocket", 0.5)
    invalid(t, rocket, "the rocket is gone after exploding")
    rocket2 = fire_rpg(t, car)
    t.set(PROJC, "Damage", FLOAT, rocket2, default="200.0")
    t.delay(1.5)
    t.true(t.get(VC, "bIsDestroyed", BOOL, target), "a lethal rocket wrecks the target")
    t.eq_int(t.get(RC, "Kills", INT, racer), 1, "kill credited to the shooter")
    t.eq_int(t.get(RC, "Score", INT, racer), 50, "+50 for the kill")
    destroy(t, target)
    out.append(t.finish())
    return out


# ---- Task 5: loot boxes ----
def loot_tests():
    out = []
    t = T("FT_DFLoot_PickupOnFootOnly", "A crate ignores a car, is collected by a character on foot (into the player's inventory), "
          "and refuses a fourth item type.")
    pc, gm, gs, racer, gates = race_context(t)
    crate = spawn_crate(t, ITEM_SHIELD)
    car = spawn_vehicle(t)
    t.delay(1.0)
    t.false(t.get(LOOTC, "bCollected", BOOL, crate), "a car driving over the crate collects nothing")
    car_z = t.g.call_static(MATH, "BreakVector", inputs=[struct_pin("InVec", VECTOR)],
                            outputs=[Pin("X", FLOAT, "out"), Pin("Y", FLOAT, "out"), Pin("Z", FLOAT, "out")], pure=True)
    t.link(t.loc(car), car_z, "InVec")
    crate_z = t.g.call_static(MATH, "BreakVector", inputs=[struct_pin("InVec", VECTOR)],
                              outputs=[Pin("X", FLOAT, "out"), Pin("Y", FLOAT, "out"), Pin("Z", FLOAT, "out")], pure=True)
    t.link(t.loc(crate), crate_z, "InVec")
    below = t.g.call_static(MATH, "Less_FloatFloat", inputs=[Pin("A", FLOAT), Pin("B", FLOAT)], outputs=[Pin("ReturnValue", BOOL, "out")], pure=True)
    t.g.link(car_z, "Z", below, "A")
    t.g.link(crate_z, "Z", below, "B")
    t.true((below, "ReturnValue"), "the crate is no obstacle: the car settles on the ground, not on the crate")
    destroy(t, car)
    ch = owned_character(t, pc)
    t.delay(0.5)
    move_to(t, ch, t.offset(t.self_loc(), 0.0, 100.0, -60.0))
    t.delay(1.0)
    t.true(t.get(LOOTC, "bCollected", BOOL, crate), "the character collected the crate")
    t.eq_int(inventory_length(t, racer), 1, "one stack in the inventory")
    sel = selected(t, racer)
    t.eq_int(enum_int(t, (sel, "Type")), ITEM_SHIELD, "the crate's shield is selected")
    t.eq_int((sel, "Charges"), 1, "one shield charge")
    t.true(t.get(ACTOR, "bHidden", BOOL, crate), "a collected crate is hidden")
    t.true(grant(t, gm, pc, ITEM_BOOST), "boost granted")
    t.true(grant(t, gm, pc, ITEM_BOMB), "bomb granted")
    crate2 = spawn_crate(t, ITEM_GUN, 0.0, 800.0)
    move_to(t, ch, t.offset(t.self_loc(), 0.0, 900.0, -60.0))
    t.delay(1.0)
    t.false(t.get(LOOTC, "bCollected", BOOL, crate2), "a fourth type is refused and the crate stays")
    out.append(t.finish())

    t = T("FT_DFLoot_RespawnsAfterDelay", "A collected crate comes back after its respawn delay.")
    pc, gm, gs, racer, gates = race_context(t)
    crate = spawn_crate(t, ITEM_BOOST)
    t.set(LOOTC, "RespawnSeconds", FLOAT, crate, default="0.5")
    ch = owned_character(t, pc)
    t.delay(0.5)
    move_to(t, ch, t.offset(t.self_loc(), 0.0, 100.0, -60.0))
    t.delay(1.0)
    t.true(t.get(LOOTC, "bCollected", BOOL, crate), "collected")
    move_to(t, ch, t.offset(t.self_loc(), 600.0, 0.0, -60.0))
    t.delay(1.5)
    t.false(t.get(LOOTC, "bCollected", BOOL, crate), "the crate is back after its delay")
    t.false(t.get(ACTOR, "bHidden", BOOL, crate), "the crate is visible again")
    out.append(t.finish())
    return out


# ---- Task 6: destructible rock and shortcut ----
def destructible_and_shortcut_tests():
    out = []
    t = T("FT_DFDestructible_ExplosivesOnlyOpensRoad", "A rock ignores plain damage, is demolished by explosive damage, and then neither blocks nor shows.")
    rock = t.spawn(DESTC, t.offset(t.self_loc(), 0.0, 800.0, 0.0))
    t.delay(0.5)
    t.damage(rock, 100)
    t.eq_float(t.get(DESTC, "Health", FLOAT, rock), 60.0, "plain damage ignored")
    t.false(t.get(DESTC, "bDestroyed", BOOL, rock), "rock intact after plain damage")
    n = t.static(GAMEPLAY, "ApplyDamage", inputs=[obj_pin("DamagedActor", ACTOR), Pin("BaseDamage", FLOAT, default="60.0"),
                                                  obj_pin("EventInstigator", CONTROLLER), obj_pin("DamageCauser", ACTOR),
                                                  Pin("DamageTypeClass", "class", sub_object=cls_ref(DAMAGE_TYPE), default_object=gen(BP_EXPLOSIVE_DAMAGE))],
                 outputs=[Pin("ReturnValue", FLOAT, "out")])
    t.link(rock, n, "DamagedActor")
    t.true(t.get(DESTC, "bDestroyed", BOOL, rock), "explosive damage demolishes the rock")
    t.true(t.get(ACTOR, "bHidden", BOOL, rock), "a demolished rock is hidden")
    col = t.g.call_on(ACTOR, "GetActorEnableCollision", outputs=[Pin("ReturnValue", BOOL, "out")], pure=True)
    t.link(rock, col, "self")
    t.false((col, "ReturnValue"), "a demolished rock no longer collides")
    destroy(t, rock)
    out.append(t.finish())

    t = T("FT_DFTrack_ShortcutIsOpenSplineOnTrack", "The level's shortcut is a second, open track actor with road pieces, counted as on-track, "
          "with a rock on it.")
    gm = t.game_mode()
    all_ = t.step(get_all_actors_of_class(t.g, TC))
    t.eq_int(t.length((all_, "OutActors"), TC), 2, "two track actors in the level")
    main = t.get(GMC, "MainTrack", OBJECT, gm, sub=cls_ref(TC))
    first, second = t.item((all_, "OutActors"), TC, "0"), t.item((all_, "OutActors"), TC, "1")
    is_main = t.g.call_static(MATH, "EqualEqual_ObjectObject", inputs=[obj_pin("A", "/Script/CoreUObject.Object"), obj_pin("B", "/Script/CoreUObject.Object")],
                              outputs=[Pin("ReturnValue", BOOL, "out")], pure=True)
    t.link(first, is_main, "A")
    t.link(main, is_main, "B")
    pick = t.g.call_static(MATH, "SelectObject", inputs=[obj_pin("A", "/Script/CoreUObject.Object"), obj_pin("B", "/Script/CoreUObject.Object"), Pin("bSelectA", BOOL)],
                           outputs=[obj_pin("ReturnValue", "/Script/CoreUObject.Object", "out")], pure=True)
    t.link(second, pick, "A")
    t.link(first, pick, "B")
    t.g.link(is_main, "ReturnValue", pick, "bSelectA")
    sc = t.step(t.g.cast(TC))
    t.g.link(pick, "ReturnValue", sc, "Object")
    SC = (sc, as_pin(BP_TRACK))
    t.false(t.get(TC, "bIsMainTrack", BOOL, SC), "the shortcut is not the main track")
    cnt = t.g.call_on(TC, "GetGeneratedMeshCount", outputs=[Pin("Count", INT, "out")], pure=True)
    t.link(SC, cnt, "self")
    pos = t.g.call_static(MATH, "Greater_IntInt", inputs=[Pin("A", INT), Pin("B", INT, default="0")], outputs=[Pin("ReturnValue", BOOL, "out")], pure=True)
    t.g.link(cnt, "Count", pos, "A")
    t.true((pos, "ReturnValue"), "the shortcut has road pieces")
    spline = t.get(TC, "Spline", OBJECT, SC, sub=cls_ref(SPLINE_COMP))
    closed = t.g.call_on(SPLINE_COMP, "IsClosedLoop", outputs=[Pin("ReturnValue", BOOL, "out")], pure=True)
    t.link(spline, closed, "self")
    t.false((closed, "ReturnValue"), "the shortcut spline is open")
    ln = t.g.call_on(TC, "GetTrackLength", outputs=[Pin("Length", FLOAT, "out")], pure=True)
    t.link(SC, ln, "self")
    half = t.g.call_static(MATH, "Multiply_FloatFloat", inputs=[Pin("A", FLOAT), Pin("B", FLOAT, default="0.5")], outputs=[Pin("ReturnValue", FLOAT, "out")], pure=True)
    t.g.link(ln, "Length", half, "A")
    xf = t.g.call_on(TC, "GetTransformAtDistance", inputs=[Pin("Distance", FLOAT)], outputs=[struct_pin("Transform", TRANSFORM, "out")], pure=True)
    t.link(SC, xf, "self")
    t.g.link(half, "ReturnValue", xf, "Distance")
    on = t.call(GMC, "IsOnAnyTrack", gm, inputs=[struct_pin("Location", VECTOR)], outputs=[Pin("ReturnValue", BOOL, "out")])
    t.link(t.transform_loc((xf, "Transform")), on, "Location")
    t.true((on, "ReturnValue"), "the middle of the shortcut counts as on-track")
    t.eq_int(count_actors(t, DESTC), 1, "one rock in the level")
    # pieces = ceil(length / PieceLength): laid along the open spline, not a closed loop through the same points
    pl = t.get(TC, "PieceLength", FLOAT, SC)
    ratio = t.g.call_static(MATH, "Divide_FloatFloat", inputs=[Pin("A", FLOAT), Pin("B", FLOAT)], outputs=[Pin("ReturnValue", FLOAT, "out")], pure=True)
    t.g.link(ln, "Length", ratio, "A")
    t.link(pl, ratio, "B")
    want = t.g.call_static(MATH, "FCeil", inputs=[Pin("A", FLOAT)], outputs=[Pin("ReturnValue", INT, "out")], pure=True)
    t.g.link(ratio, "ReturnValue", want, "A")
    same = t.g.call_static(MATH, "EqualEqual_IntInt", inputs=[Pin("A", INT), Pin("B", INT)], outputs=[Pin("ReturnValue", BOOL, "out")], pure=True)
    t.g.link(cnt, "Count", same, "A")
    t.g.link(want, "ReturnValue", same, "B")
    t.true((same, "ReturnValue"), "one road piece per PieceLength of the open spline")
    # it saves at least 10 m against the main road between its two junctions
    def main_distance_at(dist_src):
        xf2 = t.g.call_on(TC, "GetTransformAtDistance", inputs=[Pin("Distance", FLOAT)], outputs=[struct_pin("Transform", TRANSFORM, "out")], pure=True)
        t.link(SC, xf2, "self")
        if dist_src is not None:
            t.g.link(dist_src[0], dist_src[1], xf2, "Distance")
        d = t.g.call_on(TC, "GetDistanceAlongTrack", inputs=[struct_pin("WorldLocation", VECTOR)], outputs=[Pin("Distance", FLOAT, "out")], pure=True)
        t.link(main, d, "self")
        t.link(t.transform_loc((xf2, "Transform")), d, "WorldLocation")
        return (d, "Distance")
    d_in = main_distance_at(None)
    d_out = main_distance_at((ln, "Length"))
    around = t.g.call_static(MATH, "Subtract_FloatFloat", inputs=[Pin("A", FLOAT), Pin("B", FLOAT)], outputs=[Pin("ReturnValue", FLOAT, "out")], pure=True)
    t.link(d_out, around, "A")
    t.link(d_in, around, "B")
    saved = t.g.call_static(MATH, "Subtract_FloatFloat", inputs=[Pin("A", FLOAT), Pin("B", FLOAT)], outputs=[Pin("ReturnValue", FLOAT, "out")], pure=True)
    t.g.link(around, "ReturnValue", saved, "A")
    t.g.link(ln, "Length", saved, "B")
    t.true(greater(t, (saved, "ReturnValue"), 1000.0), "the shortcut is at least 10 m shorter than the main road it bypasses")
    out.append(t.finish())
    return out


def point_blank_rocket_tests():
    t = T("FT_DFProjectile_PointBlankRocketHitsRock", "A rocket fired with the car's nose against a rock explodes on the rock instead of spawning inside it.")
    pc, gm, gs, racer, gates = race_context(t)
    car = park_player(t, pc)
    # a 3 m cube spawned at scale 3 with its base on the ground (Shape_Cube's pivot is at its base, and a template scale on a root
    # component does not survive a spawn): face 2.5 m ahead of the car's centre, the muzzle 0.5 m inside it
    xf = t.g.call_static(MATH, "MakeTransform", inputs=[struct_pin("Location", VECTOR), struct_pin("Rotation", ROTATOR),
                                                          struct_pin("Scale", VECTOR, default="3,3,3")],
                         outputs=[struct_pin("ReturnValue", TRANSFORM, "out")], pure=True)
    t.link(t.offset(t.self_loc(), 400.0, 0.0, -210.0), xf, "Location")
    rock_node = t.step(t.g.spawn_actor(DESTC))
    t.g.link(xf, "ReturnValue", rock_node, "SpawnTransform")
    rock = (rock_node, "ReturnValue")
    t.delay(1.0)
    t.valid(fire_rpg(t, car), "FireRPG spawned a rocket")
    t.delay(1.5)
    t.true(t.get(DESTC, "bDestroyed", BOOL, rock), "the point-blank rocket demolished the rock")
    t.set(VC, "Health", FLOAT, car, default="100.0")  # the blast also hit the shooter; leave the shared car intact
    destroy(t, rock)
    return [t.finish()]


# ---- Task 7: HUD item row; Phase 7 Task 18 (spec §7.6): icon slots, charge counts, the selected slot framed ----
IMAGE_W = "/Script/UMG.Image"
WIDGET_W = "/Script/UMG.Widget"
SLATE_BRUSH = "/Script/SlateCore.SlateBrush"
VISIBILITY = "/Script/UMG.ESlateVisibility"
COLLAPSED, HIDDEN = 1, 2  # ESlateVisibility: Visible, Collapsed, Hidden, HitTestInvisible, SelfHitTestInvisible


def hud_part(t: T, hud, name, cls):
    """A widget of the race HUD (ItemIcon0, Vignette, ...)."""
    return t.get(WHUD, name, OBJECT, hud, sub=cls_ref(cls))


def widget_shown(t: T, widget):
    """(node, pin) of a bool: the widget's visibility is neither Collapsed nor Hidden (GetVisibility, which is valid
    before Slate builds the widget)."""
    vis = t.g.call_on(WIDGET_W, "GetVisibility", outputs=[native_enum_pin("ReturnValue", VISIBILITY, direction="out")], pure=True)
    t.link(widget, vis, "self")
    gone = or_bool(t.g)
    for pin, value in (("A", COLLAPSED), ("B", HIDDEN)):
        t.g.link(enum_is(t.g, (vis, "ReturnValue"), value), "ReturnValue", gone, pin)
    shown = not_bool(t.g)
    t.g.link(gone, "ReturnValue", shown, "A")
    return (shown, "ReturnValue")


def icon_is(t: T, hud, index, icon, message):
    """AssertTrue(ItemIcon<index>'s brush resource is the catalogue UI image `icon`)."""
    brush = t.get(IMAGE_W, "Brush", STRUCT, hud_part(t, hud, "ItemIcon%d" % index, IMAGE_W), sub=struct_ref(SLATE_BRUSH))
    res = t.g.call_static("WidgetBlueprintLibrary", "GetBrushResource", inputs=[struct_pin("Brush", SLATE_BRUSH)],
                          outputs=[obj_pin("ReturnValue", "/Script/CoreUObject.Object", "out")], pure=True, module="UMG")
    t.link(brush, res, "Brush")
    same = t.g.call_static(MATH, "EqualEqual_ObjectObject", inputs=[obj_pin("A", "/Script/CoreUObject.Object"),
                                                                   Pin("B", OBJECT, sub_object=cls_ref("/Script/CoreUObject.Object"),
                                                                       default_object=asset_object(art_icon(icon)))],
                           outputs=[Pin("ReturnValue", BOOL, "out")], pure=True)
    t.g.link(res, "ReturnValue", same, "A")
    t.true((same, "ReturnValue"), message)


def hud_item_tests():
    t = T("FT_DFHUD_ItemRowShowsInventory", "The HUD item row shows the racer's slots as icons (spec §7.6): Boost x2 and a Gun "
          "show T_DF_Icon_Boost with the count 2 and T_DF_Icon_Gun, the third slot T_DF_Icon_Empty, and the selected slot 0 is framed.")
    pc, gm, gs, racer, gates = race_context(t)
    t.true(grant(t, gm, pc, ITEM_BOOST), "first boost granted")
    t.true(grant(t, gm, pc, ITEM_BOOST), "second boost granted")
    t.true(grant(t, gm, pc, ITEM_GUN), "gun granted")
    t.delay(0.5)
    huds = widgets(t, WHUD)
    t.eq_int(t.length(huds, WHUD), 1, "one race HUD on screen")
    hud = t.item(huds, WHUD)
    icon_is(t, hud, 0, "T_DF_Icon_Boost", "slot 0 shows T_DF_Icon_Boost")
    text_reads(t, hud_part(t, hud, "ItemCount0", TEXT_BLOCK), "2", "slot 0's count reads 2")
    icon_is(t, hud, 1, "T_DF_Icon_Gun", "slot 1 shows T_DF_Icon_Gun")
    icon_is(t, hud, 2, "T_DF_Icon_Empty", "the empty slot 2 shows T_DF_Icon_Empty")
    t.true(widget_shown(t, hud_part(t, hud, "ItemFrame0", "/Script/UMG.Border")), "the selected slot 0 is framed (ItemFrame0 shown)")
    t.false(widget_shown(t, hud_part(t, hud, "ItemFrame1", "/Script/UMG.Border")), "slot 1, not selected, has no frame")
    return [t.finish()]


def build():
    return (inventory_tests() + explosion_tests() + item_use_tests() + bomb_tests() + gun_and_rocket_tests() + loot_tests()
            + destructible_and_shortcut_tests() + point_blank_rocket_tests() + hud_item_tests())


if __name__ == "__main__":
    for b in build():
        print(b.write(OUT))
