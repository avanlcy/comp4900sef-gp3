"""The art catalogue: the single list of every art asset Phase 7 generates, imports and verifies (spec 4.2).

    python -I tools/artgen/build_all.py        (writes art/catalog.json and THIRD_PARTY.md)

Recipes and scripts that a later task has not implemented yet are "todo"; each task switches its own entries.
"""
import json
import os
import re
from dataclasses import asdict, dataclass, field

ROOT = "/Game/DeadFire/Art"


@dataclass
class TextureSet:
    name: str
    recipe: str
    seed: int
    size: int = 1024
    maps: tuple = ("BC", "N", "ORM")
    source: str = "gen"
    reason: str = ""


@dataclass
class Image:
    name: str
    recipe: str
    size: tuple
    srgb: bool = True


@dataclass
class Mesh:
    name: str
    script: str
    budget: int
    slots: tuple
    collision: str = "none"  # "none" | "box" | "ucx"
    sockets: tuple = ()
    bounds: tuple = None  # expected size in cm (X, Y, Z); None = free
    origin: str = "base"  # "base" | "center" (unit-contract meshes and FX shells are centred) | "actor" (a car body:
    #                       the vehicle actor's origin, on the ground under the chassis; the body starts at its clearance)
    #                       | "mount" (character gear: the SK_Mannequin bone it is worn on, or the rifle's hold point)
    #                       | "original" (the VehicleAdv mesh it replaces: its pivot, and its bounds from dims.json)
    #                       | "gate" (BP_DFCheckpoint's origin on the road: the pylon stands on it, its foot sunk below;
    #                       the banner hangs over it)
    source: str = "gen"
    reason: str = ""


@dataclass
class Sound:
    name: str
    recipe: str
    seed: int
    seconds: float
    loop: bool = False
    ui: bool = False


@dataclass
class MaterialInstance:
    name: str
    parent: str
    scalars: dict = field(default_factory=dict)
    vectors: dict = field(default_factory=dict)
    textures: dict = field(default_factory=dict)


@dataclass
class Font:
    name: str
    file: str  # relative to art/
    face: str  # the face asset the importer creates


# --- colours (spec 3), sRGB hex ---------------------------------------------------------------------
ITEM_COLOURS = {"Boost": "00D9FF", "Shield": "3DFF7A", "Bomb": "FF3030", "Gun": "FFD21F", "RPG": "FF7A1A", "Random": "D24BFF"}
SEDAN, BRUTE, VIPER, TRIM, GANG, GANG_TRIM = "1B2A4A", "3C4148", "149E9E", "E6E6E6", "151515", "FF5A1F"
GROUND = {"ash": "4A4540", "dirt": "6B5440", "grass": "8A7A4E", "rock": "5E5A55", "sand": "B49A72"}
SUN, FOG = "FFB27A", "C8693A"
# Task 22: the player's paints one step lighter than the swatches above (same hue and saturation; HSV value 0.29 -> 0.47
# for SEDAN, 0.28 -> 0.40 for BRUTE): at the swatches the navy SEDAN and the gunmetal BRUTE read near-black at 30 m under
# the dusk light, beside the black rivals. The player's navy gear and suit follow the car.
SEDAN_LIT, BRUTE_LIT = "2B4378", "545B66"


def linear(hex_colour):
    """sRGB hex string -> linear (r, g, b, a), alpha 1.0 (IEC 61966-2-1)."""
    def one(c):
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
    h = hex_colour.lstrip("#")
    return tuple(one(int(h[i:i + 2], 16) / 255.0) for i in (0, 2, 4)) + (1.0,)


MASTERS = ["M_DF_Surface", "M_DF_CarPaint", "M_DF_Road", "M_DF_Terrain", "M_DF_FxAdditive",
           "M_DF_FxSmoke", "M_DF_FxFlame", "M_DF_Decal", "M_DF_Icon"]
ATTENUATION = "SA_DF_World"
TERRAINS = {"L_TestTrack": "ProvingGround", "L_Switchback": "Switchback"}
TERRAIN_SEEDS = {"ProvingGround": 400, "Switchback": 401}  # terrain.py (Task 19): heights, splat and scatter per terrain
TERRAIN_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "art", "terrain")

# Spec 4.6: where Poly Haven may stand in for a generated asset (recipe keys, see TEXTURE_SURFACE).
POLYHAVEN_ALLOWED_TEXTURES = ["asphalt", "concrete", "dirt", "ash_ground", "dry_grass", "rock", "sand",
                              "rust_metal", "painted_metal", "crate_metal", "wood"]
POLYHAVEN_2K_TEXTURES = ["asphalt", "dirt", "ash_ground", "dry_grass", "rock", "sand"]  # terrain sets and asphalt
POLYHAVEN_ALLOWED_MESHES = ["SM_DF_Rock01", "SM_DF_Rock02", "SM_DF_Rock03", "SM_DF_Rock04", "SM_DF_RockWall",
                            "SM_DF_RockChunk", "SM_DF_DeadTree01", "SM_DF_DeadTree02", "SM_DF_Debris01", "SM_DF_Debris02"]

FONTS = [Font("F_DF_Display", "fonts/RussoOne-Regular.ttf", "F_DF_Display_Face")]

# --- textures ---------------------------------------------------------------------------------------
# The recipe key doubles as the Poly Haven category.
_SETS = [("Asphalt", "asphalt"), ("Dirt", "dirt"), ("AshGround", "ash_ground"), ("DryGrass", "dry_grass"),
         ("Rock", "rock"), ("Sand", "sand"), ("Concrete", "concrete"), ("RustMetal", "rust_metal"),
         ("PaintedMetal", "painted_metal"), ("CrateMetal", "crate_metal"), ("Rubber", "rubber"),
         ("Fabric", "fabric"), ("Wood", "wood")]
# Task 5's Poly Haven gate (spec 4.6): the sets whose generated version failed the look-dev review (a material ball and
# a flat swatch under dusk light, judged at 5 m and 30 m). Terrain sets at 2k, the rest at 1k; polyhaven.py writes every
# map at 8 bits per channel (the 16-bit originals double-encoded sRGB in UE 4.27 and overran the art budget).
_POLYHAVEN = {
    "Concrete": ("brushed_concrete@1k", "generated concrete showed hard tile seams and worm-like crack lines at 5 m"),
    "AshGround": ("burned_ground_01@2k", "generated ash ground read as flagstone paving (polygon plates), not burnt ground"),
    "DryGrass": ("grass_ground@2k", "generated dry grass read as combed straw or fur (one-way streaks), not grass on soil"),
    "Rock": ("rock_face_03@2k", "generated rock read as crazy paving (polygon cells with dark joints), not rock"),
    "RustMetal": ("rusty_metal_04@1k", "generated rust read as black-and-orange lava camouflage at 30 m, not rusted steel"),
}


def _texture_set(name, key, seed):
    if name not in _POLYHAVEN:
        return TextureSet("T_DF_" + name, key, seed)
    pin, reason = _POLYHAVEN[name]
    return TextureSet("T_DF_" + name, key, seed, 2048 if pin.endswith("@2k") else 1024, source="polyhaven:" + pin, reason=reason)


TEXTURES = [_texture_set(n, key, 100 + i) for i, (n, key) in enumerate(_SETS)]
TEXTURES += [TextureSet("T_DF_FxNoise", "fx_noise", 200, 512, ("BC",)),
             TextureSet("T_DF_SmokePuff", "smoke_puff", 201, 256, ("BC",)),
             TextureSet("T_DF_Scorch", "scorch", 202, 512, ("BC",))]

IMAGES = [Image("T_DF_Icon_" + n, "icon_" + n.lower(), (256, 256)) for n in ("Boost", "Shield", "Bomb", "Gun", "RPG", "Random", "Empty")]
IMAGES += [Image("T_DF_Crosshair", "crosshair", (64, 64)), Image("T_DF_Vignette", "vignette", (512, 512)),
           Image("T_DF_Logo", "logo", (1024, 256))]
# the splat maps are written by terrain.py with the heightmap (build_all.py --kind terrain), not by images.py
IMAGES += [Image("T_DF_Splat_" + t, "terrain", (1024, 1024), srgb=False) for t in TERRAINS.values()]


# --- meshes -----------------------------------------------------------------------------------------
def _m(name, budget, slots, collision="none", sockets=(), bounds=None, origin="base", script="todo"):
    return Mesh("SM_DF_" + name, script, budget, tuple("MI_DF_" + s for s in slots), collision, tuple(sockets), bounds, origin)


_CAR_SLOTS = ("Trim", "Glass", "Dark", "Lights")
_CAR_SOCKETS = ("Roof", "Muzzle", "Exhaust_L", "Exhaust_R")
_GUN = ("GunMetal", "Dark")
MESHES = [
    _m("AxisFixture", 500, ["Concrete"], sockets=["Left"], bounds=(200, 50, 100), script="axis_fixture"),
    _m("Barrel", 1500, ["RustMetal"], "box", bounds=(58, 58, 88), script="barrel"),
]
# Car parts (Task 12) are built to tools/artgen/data/dims.json. The bodies also carry Arch_<wheel bone> sockets (checked
# by test_meshes). The wheel and the rim hang on the wheel bone, so their origin is the hub ("center" in X and Z; the tyre
# sits out from the bone by the wheel setups' AdditionalOffset). The exhaust flame starts at its origin and runs along
# +X ("center" in Y and Z); the Exhaust_L/R sockets are yawed 180 so it points backwards.
MESHES += [_m("Car_" + c, 8000, ("Paint_" + c,) + _CAR_SLOTS, sockets=_CAR_SOCKETS, origin="actor", script="car_" + c.lower())
           for c in ("Sedan", "Brute", "Viper")]
MESHES += [
    _m("Wheel", 1000, ["Rubber", "Rim"], origin="center", script="wheel"),
    _m("WheelRim", 1000, ["Rim"], origin="center", script="wheel_rim"),
    _m("LightBar", 2000, ["Dark", "LightBlue"], script="light_bar"),
    _m("RoofGun", 2000, _GUN, sockets=["Muzzle"], script="roof_gun"),
    _m("RoofLauncher", 2000, _GUN, sockets=["Muzzle"], script="roof_launcher"),
    # character gear (Task 14), fitted to SK_Mannequin: the helmet's origin is the head bone, the vest's spine_03, the
    # rifle's the point the right hand holds (BP_DFCharacter mounts each on its bone); the rifle is 90 cm long, Muzzle at its tip
    _m("Rifle", 2000, _GUN, sockets=["Muzzle"], origin="mount", script="rifle"),
    _m("Helmet", 2000, ["GearNavy", "Dark"], origin="mount", script="helmet"),
    _m("Vest", 2000, ["Fabric", "Dark"], origin="mount", script="vest"),
    _m("ShieldBubble", 500, ["FxShield"], origin="center", script="shield_bubble"),
    _m("ExhaustFlame", 500, ["FxBoostFlame"], origin="center", script="exhaust_flame"),
    # the loot crate (Task 17, spec 7.4): the lid sits on the crate's Lid socket; CrateStripe is the stripe slot (index 1) that
    # BP_DFLootBox tints with the item colour; the beacon is a 30 m pillar of light standing on its origin. The crate's origin is
    # the centre of the 80 cm crate and lid (fix round 1: a crate actor stands 40 cm over the ground, at the crate's centre)
    _m("Crate", 3000, ["CrateMetal", "CrateStripe"], "box", sockets=["Lid"], origin="center", script="crate"),
    _m("CrateLid", 1000, ["CrateMetal", "CrateStripe"], "box", script="crate_lid"),
    _m("BeaconPillar", 500, ["FxBeacon"], bounds=(60, 60, 3000), script="beacon"),
    # the dropped bomb (Task 17, spec 7.5): a flat pressure mine on the road; socket Lamp on top of its blinking lamp
    _m("Bomb", 2000, ["GunMetal", "Dark", "BombLamp"], sockets=["Lamp"], script="bomb"),
    # the RPG's rocket (Task 16): centred on its origin (the projectile's collision sphere), flying along +X; socket Exhaust at
    # the nozzle, yawed 180, where SM_DF_ExhaustFlame hangs as its flame
    _m("Rocket", 2000, ["RocketBody", "Dark"], sockets=["Exhaust"], origin="center", script="rocket"),
]
# Effect shells (Task 15, spec 7.1): 100 cm across, centred on the origin; the cone's tip and the beam's start are at the
# origin and they run along +X ("center" in Y and Z, like the exhaust flame). The BP_DFFx children override the FxFlash slot.
MESHES += [_m("Fx" + n, 500, ["FxFlash"], bounds=(100, 100, 6) if n == "Ring" else None, origin="center", script="fx_" + n.lower())
           for n in ("Sphere", "Ring", "Cone", "Star", "Chunk")]
MESHES += [_m("FxBeam", 500, ["FxFlash"], bounds=(100, 10, 10), origin="center", script="fx_beam")]  # 100 cm along +X from its start
# Environment (Task 20, spec 8.2 and 8.3). The unit-contract meshes fill the engine cube's 100 cm centred on the origin
# (the track and the destructible scale them as before); the ramp and the bump wedge keep the VehicleAdv originals' pivot
# and bounds (dims.json ramp, bump_wedge; test_meshes). The gate (controller ruling): 6 m pylons and a banner hung 4.7 m up,
# both on the gate's origin; the banner is 100 cm on Y, scaled to the pylon spacing at run time; Gate is slot 0 of both.
# "box" collision is the importer's auto 18-DOP unless the script brings UCX hulls (the billboard, light tower and fence,
# whose open frames a hull round the whole would fill). Rocks, dead trees and debris are
# scripted: each read as natural in Task 20's review (headless previews at 20 m, the look-dev row under dusk light), so the
# spec 4.6 Poly Haven gate pinned no model; a pin would load its gltf through dfmesh.import_polyhaven_model.
# The rock chunk's origin is its centre (BP_DFDebris simulates physics); rock, dead_tree and debris are parametric
# scripts (one script, the mesh's number picks its seed and shape).
MESHES += [
    _m("RoadSlab", 3000, ["Road"], "box", bounds=(100, 100, 100), origin="center", script="road_slab"),
    _m("Barrier", 3000, ["Concrete"], "box", bounds=(100, 100, 100), origin="center", script="barrier"),
    _m("RockWall", 1500, ["Rock"], "box", bounds=(100, 100, 100), origin="center", script="rock_wall"),
    _m("GatePylon", 3000, ["Gate", "GunMetal"], "ucx", origin="gate", script="gate_pylon"),
    _m("GateBanner", 3000, ["Gate", "Dark"], bounds=(20, 100, 80), origin="gate", script="gate_banner"),
    _m("Ramp", 3000, ["Concrete"], "ucx", origin="original", script="ramp"),
    _m("BumpWedge", 3000, ["Concrete"], "ucx", origin="original", script="bump_wedge"),
    _m("RockChunk", 1500, ["Rock"], "box", origin="center", script="rock_chunk"),
]
MESHES += [_m("Rock0%d" % i, 1500, ["Rock"], "box", script="rock") for i in range(1, 5)]
MESHES += [_m("DeadTree0%d" % i, 3000, ["DeadWood"], "ucx", script="dead_tree") for i in (1, 2)]
MESHES += [
    _m("CarWreck", 3000, ["Paint_Charred", "Dark"], "box", script="car_wreck"),
    _m("TyreStack", 3000, ["Rubber"], "box", script="tyre_stack"),
    _m("Container", 3000, ["ContainerPaint"], "box", script="container"),
    _m("ScrapFence", 3000, ["RustMetal"], "box", script="scrap_fence"),
    _m("Billboard", 3000, ["RustMetal", "BillboardTag"], "box", script="billboard"),
    _m("LightTower", 3000, ["RustMetal", "Lights"], "box", script="light_tower"),
]
MESHES += [_m("Debris0%d" % i, 1500, ["RustMetal", "Concrete"], script="debris") for i in (1, 2)]
MESHES += [_m("Plinth", 3000, ["Concrete", "Trim"], "box", script="plinth")]

# --- sounds -----------------------------------------------------------------------------------------
_SOUNDS = [  # (name, seconds, loop, ui)
    ("EngineSedan", 2.0, True, False), ("EngineBrute", 2.0, True, False), ("EngineViper", 2.0, True, False),
    ("Skid", 1.0, True, False), ("Crash", 0.6, False, False), ("CarGun", 0.25, False, False),
    ("Rifle", 0.35, False, False), ("RocketLaunch", 0.8, False, False), ("RocketLoop", 1.0, True, False),
    ("Explosion", 2.5, False, False), ("BombArm", 0.3, False, False), ("BombBeep", 0.08, False, False),
    ("LootOpen", 0.6, False, False), ("Pickup", 0.4, False, False), ("Deny", 0.25, False, False),
    ("Boost", 1.2, False, False), ("ShieldUp", 0.6, False, False), ("ShieldHit", 0.3, False, False),
    ("ShieldDown", 0.5, False, False), ("TirePop", 0.4, False, False), ("ImpactMetal", 0.3, False, False),
    ("ImpactDirt", 0.3, False, False), ("Checkpoint", 0.5, False, False), ("Lap", 1.2, False, False),
    ("UIClick", 0.06, False, True), ("UIHover", 0.04, False, True),
]
SOUNDS = [Sound("SW_DF_" + n, re.sub(r"(?<=[a-z])(?=[A-Z])", "_", n.replace("UI", "Ui")).lower(), 300 + i, s, loop, ui)  # recipe: key in sfx.RECIPES
          for i, (n, s, loop, ui) in enumerate(_SOUNDS)]


# --- materials --------------------------------------------------------------------------------------
def _set(tex, maps=("BC", "N", "ORM")):
    return {m: "T_DF_%s_%s" % (tex, m) for m in maps}


def _mi(name, parent, tint=None, tex=None, glow=None, textures=None, rough=0.6, **scalars):
    """rough: an untextured M_DF_Surface instance's roughness. It gets a flat ORM (FlatORM: AO 1, this roughness, no
    metal) instead of the master's default ORM texture (Task 12: glass glossy, trim and lights clean)."""
    vectors = {}
    if tint:
        vectors["Tint" if parent == "M_DF_Surface" else "Color"] = linear(tint)
    if glow is not None:
        scalars["Glow"] = glow
    textures = textures or (_set(tex) if tex else {})
    if parent == "M_DF_Surface" and not textures:
        vectors["FlatORM"] = (1.0, float(rough), 0.0, 1.0)
    return MaterialInstance("MI_DF_" + name, parent, scalars, vectors, textures)


TERRAIN_TINTS = [("Dirt", "dirt"), ("Ash", "ash"), ("Grass", "grass"), ("Rock", "rock"), ("Sand", "sand")]  # M_DF_Terrain set: GROUND


def terrain_material(terrain):
    """MI_DF_Terrain_<terrain>: its splat map, plus TerrainOrigin (the landscape corner, cm) and TerrainSize from
    art/terrain/<terrain>.terrain.json, which terrain.py writes; before the first build_all --kind terrain the instance
    carries only its splat (write_json re-reads the json, so the catalogue written after a terrain build is current)."""
    mi = MaterialInstance("MI_DF_Terrain_" + terrain, "M_DF_Terrain", textures={"Splat": "T_DF_Splat_" + terrain})
    # Task 22: each set at its spec §3 ground colour (M_DF_Terrain recolours it around its own average): under the dusk sun the
    # scanned sets' own browns read as orange sand everywhere, the ridge's rock included
    for key, ground in TERRAIN_TINTS:
        mi.vectors[key + "_Tint"] = linear(GROUND[ground])
    path = os.path.join(TERRAIN_DIR, terrain + ".terrain.json")
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            meta = json.load(f)
        mi.vectors["TerrainOrigin"] = (float(meta["origin"][0]), float(meta["origin"][1]), 0.0, 0.0)
        mi.scalars["TerrainSize"] = float(meta["size_cm"])
    return mi


def _paint(name, hex_colour, **scalars):
    mi = _mi(name, "M_DF_CarPaint", tex="PaintedMetal", **scalars)
    mi.vectors["PaintColor"] = linear(hex_colour)
    return mi


_S = "M_DF_Surface"
_FX = "M_DF_FxAdditive"
MANNEQUIN_FABRIC_TILING = 4.0
DUST_DENSITY = 2.5
DUST_COLOUR = "D8CCB4"  # pale dust, lighter than every GROUND colour
MATERIALS = [
    _paint("Paint_Sedan", SEDAN_LIT), _paint("Paint_Brute", BRUTE_LIT), _paint("Paint_Viper", VIPER),
    _paint("Paint_Gang", GANG), _paint("Paint_Charred", GANG, Char=1.0),
    # Task 22 (controller ruling, spec §3): the Fire syndicate rivals' flame-orange trim, as MI_DF_Trim but GANG_TRIM
    _mi("Trim_Gang", _S, GANG_TRIM, "PaintedMetal"),
    _mi("Trim", _S, TRIM, "PaintedMetal"), _mi("Glass", _S, "0B1218", rough=0.06), _mi("Dark", _S, "1A1A1C", rough=0.55),
    _mi("Lights", _S, "FFE9B0", glow=2.0, rough=0.3), _mi("LightBlue", _S, "2A6BFF", glow=3.0, rough=0.3),
    _mi("Rubber", _S, "1C1C1C", "Rubber"), _mi("Rim", _S, "9A9EA3", "PaintedMetal"),
    _mi("GunMetal", _S, BRUTE, "PaintedMetal"), _mi("GearNavy", _S, SEDAN_LIT, "Fabric"), _mi("Fabric", _S, "3A3A36", "Fabric"),
    # Task 22: the mannequin's UVs spread one Fabric repeat over the body, so the weave read as a checker at 3 m; four repeats
    # bring it under a few pixels there
    _mi("Mannequin_Body", _S, SEDAN_LIT, "Fabric", Tiling=MANNEQUIN_FABRIC_TILING),
    _mi("Mannequin_Trim", _S, "8A8F94", "Fabric", Tiling=MANNEQUIN_FABRIC_TILING),
    _mi("RustMetal", _S, tex="RustMetal"), _mi("Concrete", _S, tex="Concrete"),
    _mi("Rock", _S, GROUND["rock"], "Rock"), _mi("CrateMetal", _S, tex="CrateMetal"),
    _mi("CrateStripe", _S, ITEM_COLOURS["Gun"], glow=2.0), _mi("Gate", _S, GANG_TRIM, glow=0.6),
    _mi("BombLamp", _S, ITEM_COLOURS["Bomb"], glow=3.0), _mi("RocketBody", _S, "6B6F73", "PaintedMetal"),
    _mi("DeadWood", _S, "5A4636", "Wood"), _mi("ContainerPaint", _S, "7A3B2A", "PaintedMetal"),
    _mi("BillboardTag", _S, GANG_TRIM),
    _mi("Road", "M_DF_Road", tex="Asphalt"),
    # the terrain sets as plain surfaces: the look-dev level shows them as material balls (Task 5's Poly Haven gate)
    _mi("Dirt", _S, tex="Dirt"), _mi("AshGround", _S, tex="AshGround"), _mi("DryGrass", _S, tex="DryGrass"), _mi("Sand", _S, tex="Sand"),
    *[terrain_material(t) for t in TERRAINS.values()],  # Task 19: splat, TerrainOrigin, TerrainSize
    _mi("FxFlash", _FX, "FFFFFF", glow=4.0), _mi("FxTracer", _FX, ITEM_COLOURS["Gun"], glow=6.0),
    _mi("FxSpark", _FX, SUN, glow=5.0), _mi("FxBlast", _FX, ITEM_COLOURS["RPG"], glow=4.0),
    _mi("FxShield", _FX, ITEM_COLOURS["Shield"], glow=1.0, FresnelPower=3.0),
    _mi("FxBeacon", _FX, "FFFFFF", glow=2.0, NearFade=1000.0),
    _mi("FxSmoke", "M_DF_FxSmoke", "3A3631", textures=_set("SmokePuff", ("BC",))),
    # Task 22 fix round 1: the impact dust (a cone) takes no rim fade and a denser opacity (at the shot's half-life, Fade ~0.35,
    # it read faint, and the smoke rim fade had thinned it by a third), and a pale dust colour: in the sand colour it vanished
    # against the sand patches of the shipped ground
    _mi("FxDust", "M_DF_FxSmoke", DUST_COLOUR, textures=_set("SmokePuff", ("BC",)), RimFade=0.0, Density=DUST_DENSITY),
    # Task 15: BP_DFFxPuff's light ash-grey smoke (rocket trail, tyre smoke); a caller tints it darker for wreck smoke
    # (Color = Tint x this colour, so the base must be the lightest use)
    _mi("FxPuff", "M_DF_FxSmoke", "CFCAC2", textures=_set("SmokePuff", ("BC",))),
    # Task 15: BP_DFFxLootBurst's white, tinted with the item colour by its caller; a low glow, because brighter (FxFlash's 4,
    # then 2.5) the dusk exposure and the tonemapper washed the item's hue out to pink-white in the look-dev capture
    _mi("FxBurst", _FX, "FFFFFF", glow=1.2),
    _mi("FxFlame", "M_DF_FxFlame", ITEM_COLOURS["RPG"], textures=_set("FxNoise", ("BC",))),
    _mi("FxBoostFlame", "M_DF_FxFlame", ITEM_COLOURS["Boost"], textures=_set("FxNoise", ("BC",))),
    _mi("Scorch", "M_DF_Decal", textures=_set("Scorch", ("BC",))), _mi("Icon", "M_DF_Icon", "FFFFFF"),
]


# --- helpers ----------------------------------------------------------------------------------------
def texture_asset_names():
    names = []
    for t in TEXTURES:
        names += ["%s_%s" % (t.name, m) for m in t.maps]
    return names + [i.name for i in IMAGES]


def polyhaven_entries():
    return [e for e in TEXTURES + MESHES if e.source != "gen"]


def polyhaven_slug(entry):
    return entry.source.split(":", 1)[1].split("@", 1)[0]


_UI_IMAGES = ("T_DF_Icon_", "T_DF_Logo", "T_DF_Crosshair", "T_DF_Vignette")


def asset_path(name):
    if name.startswith("F_") or name.startswith(_UI_IMAGES):
        folder = "UI"
    elif name.startswith(("T_DF_Splat_", "MI_DF_Terrain_")):
        folder = "Terrain"
    elif name.startswith("SM_DF_Fx"):
        folder = "Fx"
    elif name.startswith("T_"):
        folder = "Textures"
    elif name.startswith("SM_"):
        folder = "Meshes"
    elif name.startswith(("M_", "MI_")):
        folder = "Materials"
    elif name.startswith(("SW_", "SA_")):
        folder = "Sounds"
    else:
        raise ValueError("no art folder for %s" % name)
    return "%s/%s/%s" % (ROOT, folder, name)


def _compression(name):
    if name.endswith("_N"):
        return "TC_NORMALMAP"
    return "TC_MASKS" if name.endswith("_ORM") else "TC_DEFAULT"


def _entry(e, **extra):
    d = asdict(e)
    d["asset_path"] = asset_path(e.name)
    d.update(extra)
    return d


def to_dict():
    textures = []
    for t in TEXTURES:
        for m in t.maps:
            a = "%s_%s" % (t.name, m)
            textures.append(_entry(t, asset=a, map=m, asset_path=asset_path(a), file="textures/%s.png" % a,
                                   compression=_compression(a), srgb=(m == "BC"), lod_group="TEXTUREGROUP_World"))
    images = []
    for i in IMAGES:
        splat = i.name.startswith("T_DF_Splat_")
        images.append(_entry(i, file=("terrain/%s.png" if splat else "images/%s.png") % i.name, compression="TC_DEFAULT",
                             lod_group="TEXTUREGROUP_World" if splat else "TEXTUREGROUP_UI"))
    return {
        "masters": [{"name": m, "asset_path": asset_path(m)} for m in MASTERS],
        "attenuation": {"name": ATTENUATION, "asset_path": asset_path(ATTENUATION)},
        "fonts": [_entry(f) for f in FONTS],
        "textures": textures,
        "images": images,
        "meshes": [_entry(m, file="meshes/%s.fbx" % m.name) for m in MESHES],
        "sounds": [_entry(s, file="sounds/%s.wav" % s.name) for s in SOUNDS],
        "materials": [_entry(m) for m in MATERIALS],
        "terrains": TERRAINS,
    }


def write_json(path):
    MATERIALS[:] = [terrain_material(m.name[len("MI_DF_Terrain_"):]) if m.name.startswith("MI_DF_Terrain_") else m
                    for m in MATERIALS]  # the terrain instances re-read their terrain.json (it may be newer than this import)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(to_dict(), f, indent=1)
        f.write("\n")
