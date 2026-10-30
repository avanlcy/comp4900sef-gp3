"""Shared data types (plan Task 2; Phase 3 adds E_DFItemType and S_DFItemStack): E_DFRaceEndReason, S_DFTireState,
S_DFRaceResult, E_DFItemType, S_DFItemStack."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from bpgen import Enum, Struct  # noqa: E402

OUT = os.path.join(os.path.dirname(__file__), "..", "..", "..", "comp4900sef", "Script", "paste")
DATA = "/Game/DeadFire/Data"
E_END_REASON = DATA + "/E_DFRaceEndReason"
S_TIRE = DATA + "/S_DFTireState"
S_RESULT = DATA + "/S_DFRaceResult"
E_ITEM_TYPE = DATA + "/E_DFItemType"
S_ITEM_STACK = DATA + "/S_DFItemStack"


def enum_spec(asset):
    return "enum:%s.%s" % (asset, asset.rsplit("/", 1)[1])


def struct_spec(asset):
    return "struct:%s.%s" % (asset, asset.rsplit("/", 1)[1])


def build():
    return [
        Enum(E_END_REASON, ["None", "TimeUp", "DeathLimit"]),
        Struct(S_TIRE)
        .member("BoneName", "name")
        .member("Health", "float", "30")
        .member("MaxHealth", "float", "30")
        .member("bBlown", "bool", "false"),
        Struct(S_RESULT)
        .member("Reason", enum_spec(E_END_REASON))
        .member("bPassed", "bool", "false")
        .member("Rank", "int", "0")
        .member("RacerCount", "int", "0")
        .member("Score", "int", "0")
        .member("Laps", "int", "0")
        .member("Kills", "int", "0")
        .member("Deaths", "int", "0"),
        # Phase 3
        Enum(E_ITEM_TYPE, ["None", "Boost", "Shield", "Bomb", "Gun", "RPG"]),
        Struct(S_ITEM_STACK)
        .member("Type", enum_spec(E_ITEM_TYPE))
        .member("Charges", "int", "0"),
    ]


if __name__ == "__main__":
    for a in build():
        print(a.write(OUT))
