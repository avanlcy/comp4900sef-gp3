"""Checks the art catalogue: names, prefixes, sources, third-party records, material wiring and spec coverage (plan Task 1).

    python -I tools/artgen/test_catalog.py
"""
import hashlib
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
from artgen import catalog  # noqa: E402
from artgen.blender_path import find_blender  # noqa: E402

REPO = os.path.dirname(os.path.dirname(HERE))
ART = os.path.join(REPO, "art")

# Every mesh, texture and sound the spec names in §5–§8 (literals on purpose: the catalogue must not define its own coverage).
SPEC_MESHES = [
    "SM_DF_Car_Sedan", "SM_DF_Car_Brute", "SM_DF_Car_Viper", "SM_DF_Wheel", "SM_DF_WheelRim",
    "SM_DF_RoofGun", "SM_DF_RoofLauncher", "SM_DF_Helmet", "SM_DF_Vest", "SM_DF_Rifle",
    "SM_DF_Crate", "SM_DF_CrateLid", "SM_DF_Bomb", "SM_DF_Rocket",
    "SM_DF_RoadSlab", "SM_DF_Barrier", "SM_DF_GatePylon", "SM_DF_GateBanner", "SM_DF_Ramp", "SM_DF_BumpWedge",
    "SM_DF_RockWall", "SM_DF_RockChunk",
    "SM_DF_Rock01", "SM_DF_Rock02", "SM_DF_Rock03", "SM_DF_Rock04", "SM_DF_DeadTree01", "SM_DF_DeadTree02",
    "SM_DF_CarWreck", "SM_DF_Barrel", "SM_DF_TyreStack", "SM_DF_Container", "SM_DF_ScrapFence", "SM_DF_Billboard",
    "SM_DF_LightTower", "SM_DF_Debris01", "SM_DF_Debris02", "SM_DF_Plinth",
]
SPEC_TEXTURES = [
    "T_DF_Icon_Boost", "T_DF_Icon_Shield", "T_DF_Icon_Bomb", "T_DF_Icon_Gun", "T_DF_Icon_RPG", "T_DF_Logo",
]
SPEC_SOUNDS = [
    "SW_DF_EngineSedan", "SW_DF_EngineBrute", "SW_DF_EngineViper", "SW_DF_Crash", "SW_DF_CarGun", "SW_DF_Rifle",
    "SW_DF_Explosion", "SW_DF_LootOpen", "SW_DF_Deny", "SW_DF_Boost", "SW_DF_ShieldUp", "SW_DF_ShieldHit",
    "SW_DF_ShieldDown", "SW_DF_BombArm", "SW_DF_BombBeep", "SW_DF_RocketLaunch", "SW_DF_RocketLoop",
    "SW_DF_TirePop", "SW_DF_UIHover", "SW_DF_UIClick", "SW_DF_Checkpoint", "SW_DF_Lap",
]
SPEC_MATERIALS = [
    "MI_DF_Paint_Sedan", "MI_DF_Paint_Brute", "MI_DF_Paint_Viper", "MI_DF_Paint_Gang", "MI_DF_Paint_Charred",
    "MI_DF_Mannequin_Body", "MI_DF_Mannequin_Trim", "MI_DF_Trim_Gang",
]

PH_SOURCE = re.compile(r"^polyhaven:([a-z0-9_]+)@(1k|2k)$")

checks = 0
failures = []


def check(ok, msg):
    global checks
    checks += 1
    if not ok:
        failures.append(msg)


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 16), b""):
            h.update(block)
    return h.hexdigest()


def test_names_and_prefixes():
    lists = [(catalog.TEXTURES, "T_DF_"), (catalog.IMAGES, "T_DF_"), (catalog.MESHES, "SM_DF_"),
             (catalog.SOUNDS, "SW_DF_"), (catalog.MATERIALS, "MI_DF_"), (catalog.FONTS, "F_DF_")]
    seen = set()
    for entries, prefix in lists:
        for e in entries:
            check(e.name.startswith(prefix), "%s lacks prefix %s" % (e.name, prefix))
            check(e.name not in seen, "duplicate name %s" % e.name)
            seen.add(e.name)
    for m in catalog.MASTERS:
        check(m.startswith("M_DF_"), "master %s lacks prefix M_DF_" % m)
    check(catalog.ATTENUATION.startswith("SA_DF_"), "attenuation lacks prefix SA_DF_")


def test_sources():
    for e in catalog.TEXTURES + catalog.MESHES:
        if e.source == "gen":
            continue
        m = PH_SOURCE.match(e.source)
        check(m is not None, "%s source %r is not polyhaven:<slug>@<1k|2k>" % (e.name, e.source))
        check(bool(e.reason.strip()), "%s has a Poly Haven source but no reason" % e.name)
        if isinstance(e, catalog.TextureSet):
            check(e.recipe in catalog.POLYHAVEN_ALLOWED_TEXTURES, "%s: recipe %s may not come from Poly Haven" % (e.name, e.recipe))
            if m and m.group(2) == "2k":
                check(e.recipe in catalog.POLYHAVEN_2K_TEXTURES, "%s: 2k only for terrain sets and asphalt" % e.name)
        else:
            check(e.name in catalog.POLYHAVEN_ALLOWED_MESHES, "%s may not come from Poly Haven" % e.name)
            check(m is None or m.group(2) == "1k", "%s: models are fetched at 1k" % e.name)


def test_third_party_records():
    path = os.path.join(HERE, "THIRD_PARTY.md")
    check(os.path.exists(path), "THIRD_PARTY.md missing (run build_all.py)")
    text = open(path, encoding="utf-8").read() if os.path.exists(path) else ""
    check("Russo One" in text and "SIL Open Font License" in text, "THIRD_PARTY.md lacks the Russo One / OFL line")
    lock_path = os.path.join(HERE, "polyhaven.lock.json")
    lock = json.load(open(lock_path, encoding="utf-8")) if os.path.exists(lock_path) else {}
    for e in catalog.polyhaven_entries():
        slug = catalog.polyhaven_slug(e)
        res = e.source.rsplit("@", 1)[-1]
        check("https://polyhaven.com/a/%s" % slug in text, "THIRD_PARTY.md lacks %s" % slug)
        files = [k for k in lock if lock[k].get("slug") == slug]
        check(len(files) > 0, "polyhaven.lock.json has no files for %s" % slug)
        for rel in files:
            # sha256 is the upstream download (spec 13: a changed upstream file is refused); sha256_art is the file
            # written to art/ (PNGs converted to 8 bits per channel), which is what this check compares
            check(bool(lock[rel].get("sha256")) and bool(lock[rel].get("sha256_art")), "lock entry %s lacks sha256/sha256_art" % rel)
            check(lock[rel].get("res") == res, "lock entry %s is %s, the catalogue pins %s" % (rel, lock[rel].get("res"), res))
            local = os.path.join(ART, rel)
            if os.path.exists(local):
                check(sha256(local) == lock[rel].get("sha256_art"), "%s does not match its lock hash (sha256_art)" % rel)


def test_material_wiring():
    texture_names = set(catalog.texture_asset_names())
    material_names = {m.name for m in catalog.MATERIALS}
    for mi in catalog.MATERIALS:
        check(mi.parent in catalog.MASTERS, "%s parent %s is not a master" % (mi.name, mi.parent))
        for param, tex in mi.textures.items():
            check(tex in texture_names, "%s.%s references unknown texture %s" % (mi.name, param, tex))
    for mesh in catalog.MESHES:
        check(len(mesh.slots) > 0, "%s has no material slots" % mesh.name)
        for slot in mesh.slots:
            check(slot in material_names, "%s slot %s is not a catalogue material" % (mesh.name, slot))
        check(mesh.collision in ("none", "box", "ucx"), "%s collision %r" % (mesh.name, mesh.collision))


def test_spec_coverage():
    meshes = {m.name for m in catalog.MESHES}
    textures = set(catalog.texture_asset_names())
    sounds = {s.name for s in catalog.SOUNDS}
    materials = {m.name for m in catalog.MATERIALS}
    for n in SPEC_MESHES:
        check(n in meshes, "spec mesh %s missing" % n)
    for n in SPEC_TEXTURES:
        check(n in textures, "spec texture %s missing" % n)
    for n in SPEC_SOUNDS:
        check(n in sounds, "spec sound %s missing" % n)
    for n in SPEC_MATERIALS:
        check(n in materials, "spec material %s missing" % n)
    for terrain in catalog.TERRAINS.values():
        check("T_DF_Splat_" + terrain in textures, "splat for %s missing" % terrain)
        check("MI_DF_Terrain_" + terrain in materials, "terrain material for %s missing" % terrain)


def test_asset_paths():
    check(catalog.asset_path("SM_DF_Barrel") == "/Game/DeadFire/Art/Meshes/SM_DF_Barrel", "asset_path(SM_DF_Barrel)")
    check(catalog.asset_path("T_DF_Asphalt_BC") == "/Game/DeadFire/Art/Textures/T_DF_Asphalt_BC", "asset_path(texture)")
    check(catalog.asset_path("T_DF_Icon_Boost") == "/Game/DeadFire/Art/UI/T_DF_Icon_Boost", "asset_path(icon)")
    check(catalog.asset_path("T_DF_Logo") == "/Game/DeadFire/Art/UI/T_DF_Logo", "asset_path(logo)")
    check(catalog.asset_path("T_DF_Splat_Switchback") == "/Game/DeadFire/Art/Terrain/T_DF_Splat_Switchback", "asset_path(splat)")
    check(catalog.asset_path("MI_DF_Terrain_Switchback") == "/Game/DeadFire/Art/Terrain/MI_DF_Terrain_Switchback", "asset_path(terrain MI)")
    check(catalog.asset_path("SM_DF_FxRing") == "/Game/DeadFire/Art/Fx/SM_DF_FxRing", "asset_path(fx mesh)")
    check(catalog.asset_path("MI_DF_Rock") == "/Game/DeadFire/Art/Materials/MI_DF_Rock", "asset_path(MI)")
    check(catalog.asset_path("M_DF_Surface") == "/Game/DeadFire/Art/Materials/M_DF_Surface", "asset_path(master)")
    check(catalog.asset_path("SW_DF_Crash") == "/Game/DeadFire/Art/Sounds/SW_DF_Crash", "asset_path(sound)")
    check(catalog.asset_path("SA_DF_World") == "/Game/DeadFire/Art/Sounds/SA_DF_World", "asset_path(attenuation)")
    check(catalog.asset_path("F_DF_Display") == "/Game/DeadFire/Art/UI/F_DF_Display", "asset_path(font)")


def test_colours():
    check(catalog.linear("FFFFFF") == (1.0, 1.0, 1.0, 1.0), "linear(white)")
    r, g, b, a = catalog.linear("1B2A4A")
    check(abs(r - 0.0103) < 0.001 and abs(b - 0.0685) < 0.001, "linear(navy) = %s" % ((r, g, b),))


def test_blender():
    path = find_blender()
    check(os.path.isfile(path), "find_blender() returned %s" % path)


def main():
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
            except Exception as e:  # a crashing check is a failure, not a traceback that hides the others
                failures.append("%s raised %s: %s" % (name, type(e).__name__, e))
    if failures:
        for f in failures[:40]:
            print("FAIL: " + f)
        print("%d of %d checks failed" % (len(failures), checks))
        sys.exit(1)
    print("OK: %d checks" % checks)


if __name__ == "__main__":
    main()
