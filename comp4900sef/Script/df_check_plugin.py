"""Checks the DF Blueprint Authoring plugin functions added in Phase 7, inside the running editor (kept as a tool):

    python tools/ue_remote.py --code "exec(open(r'<repo>/comp4900sef/Script/df_check_plugin.py').read())"

1. CreateLandscapeFromRaw: writes a 127 x 127 16-bit ramp to Saved/df_check_ramp.r16, opens a new untitled level and
   imports it at (0, 0, 0) with scale (100, 100, 100). The landscape must be 12,600 cm square and carry its label and
   material, and line traces at sample points must hit the ramp's heights (+-2 cm). A size that breaks the plugin's
   (Size - 1) % 126 == 0 rule must be refused.
2. SetComponentSocket: on a throwaway Blueprint, the socket must read back through DescribeBlueprint; setting the same
   socket again reports "exists", "None" clears it, and a missing component is an error.
3. SetFontFace: a throwaway Font takes the engine's Roboto face as its default typeface; setting it again reports
   "exists".

Prints PLUGIN CHECK OK, or PLUGIN CHECK FAILED: followed by one line per failure. The temporary assets (under
/Game/DFCheckTemp, never saved) and the raw file are deleted, and the level that was open before is loaded again (the
untitled level is discarded). Refuses to run during Play-In-Editor or while a map has unsaved changes.
"""
import json
import os
import struct

import unreal

A = unreal.DFBlueprintAuthoringLibrary
ELL = unreal.EditorLevelLibrary
EAL = unreal.EditorAssetLibrary

TEMP_DIR = "/Game/DFCheckTemp"
SIZE = 127            # one component of 2 x 2 sections of 63 quads
SCALE = 100.0         # cm per quad, and the Z scale
LABEL = "DFCheckLandscape"
MATERIAL = "/Engine/EngineMaterials/WorldGridMaterial"
FONT_FACE = "/Engine/EngineFonts/Faces/RobotoRegular"
RAMP_X, RAMP_Y = 20, 10   # height units per vertex along X and along Y: a plane, so every point of every triangle is exact
SAMPLES = [(30, 90), (100, 20), (63.5, 40.25)]  # vertex coordinates; the last lies between vertices
TOLERANCE = 2.0       # cm
CREATED = []          # asset paths to delete afterwards (unsaved, so the folder never exists on disk)


def _create(name, cls, factory):
    asset = unreal.AssetToolsHelpers.get_asset_tools().create_asset(name, TEMP_DIR, cls, factory)
    if asset is not None:
        CREATED.append("%s/%s" % (TEMP_DIR, name))
    return asset


def _ramp_z(x, y):
    """World Z (cm) of the ramp at vertex coordinates (x, y): (h - 32768) / 128 * Z scale."""
    return (RAMP_X * x + RAMP_Y * y) / 128.0 * SCALE


def _raw_path():
    saved = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir())
    return os.path.join(saved, "df_check_ramp.r16")


def _write_ramp(path):
    """Size x Size little-endian uint16, row-major with the row index = Y (the layout ALandscape::Import reads)."""
    values = [32768 + RAMP_X * x + RAMP_Y * y for y in range(SIZE) for x in range(SIZE)]
    with open(path, "wb") as f:
        f.write(struct.pack("<%dH" % len(values), *values))


def _trace_z(world, x_cm, y_cm):
    """Z of the first blocking hit straight down at (x, y), or None."""
    hit = unreal.SystemLibrary.line_trace_single(
        world, unreal.Vector(x_cm, y_cm, 50000.0), unreal.Vector(x_cm, y_cm, -50000.0),
        unreal.TraceTypeQuery.TRACE_TYPE_QUERY1, True, [], unreal.DrawDebugTrace.NONE, True)
    if hit is None:
        return None
    fields = hit.to_tuple()  # BreakHitResult order: blocking hit, initial overlap, time, distance, location, ...
    return fields[4].z if fields[0] else None


def check_landscape(failures):
    path = _raw_path()
    _write_ramp(path)
    try:
        world = unreal.EditorLoadingAndSavingUtils.new_blank_map(False)
        if world is None:
            failures.append("landscape: could not open a new untitled level")
            return
        material = unreal.load_asset(MATERIAL)
        scale = unreal.Vector(SCALE, SCALE, SCALE)
        bad = A.create_landscape_from_raw(world, path, 64, unreal.Vector(0, 0, 0), scale, material, "DFCheckBadSize")
        if not str(bad).startswith("ERROR"):
            failures.append("landscape: size 64 was not refused (%r)" % bad)
        res = A.create_landscape_from_raw(world, path, SIZE, unreal.Vector(0, 0, 0), scale, material, LABEL)
        if res:
            failures.append("landscape: CreateLandscapeFromRaw returned %r" % res)
            return
        lands = [a for a in ELL.get_all_level_actors() if isinstance(a, unreal.Landscape)]
        if len(lands) != 1:
            failures.append("landscape: %d landscapes in the level, expected 1" % len(lands))
            return
        land = lands[0]
        if land.get_actor_label() != LABEL:
            failures.append("landscape: label %r, expected %r" % (land.get_actor_label(), LABEL))
        if land.get_editor_property("landscape_material") != material:
            failures.append("landscape: material %r, expected %s" % (land.get_editor_property("landscape_material"), MATERIAL))
        origin, extent = land.get_actor_bounds(False)
        side = (SIZE - 1) * SCALE
        if abs(2 * extent.x - side) > 1 or abs(2 * extent.y - side) > 1 or abs(origin.x - side / 2) > 1 or abs(origin.y - side / 2) > 1:
            failures.append("landscape: bounds centre (%.0f, %.0f) size %.0f x %.0f, expected a %.0f cm square from (0, 0)"
                            % (origin.x, origin.y, 2 * extent.x, 2 * extent.y, side))
        for x, y in SAMPLES:
            z = _trace_z(world, x * SCALE, y * SCALE)
            want = _ramp_z(x, y)
            if z is None or abs(z - want) > TOLERANCE:
                failures.append("landscape: trace at vertex (%s, %s) hit Z %s, expected %.2f" % (x, y, z, want))
    finally:
        if os.path.exists(path):
            os.remove(path)


def check_socket(failures):
    factory = unreal.BlueprintFactory()
    factory.set_editor_property("parent_class", unreal.Actor)
    bp = _create("BP_DFCheckSocket", unreal.Blueprint, factory)
    for name, parent in (("Base", "None"), ("Child", "Base")):
        r = A.add_component(bp, name, "/Script/Engine.StaticMeshComponent", parent)
        if r:
            failures.append("socket: AddComponent %s returned %r" % (name, r))

    def socket_of(name):
        comps = {c["name"]: c for c in json.loads(A.describe_blueprint(bp))["components"]}
        return comps.get(name, {}).get("socket")

    r = A.set_component_socket(bp, "Child", "Muzzle")
    if r:
        failures.append("socket: SetComponentSocket returned %r" % r)
    if socket_of("Child") != "Muzzle":
        failures.append("socket: DescribeBlueprint reads %r, expected 'Muzzle'" % socket_of("Child"))
    if socket_of("Base") != "":
        failures.append("socket: the parent reads %r, expected ''" % socket_of("Base"))
    r = A.set_component_socket(bp, "Child", "Muzzle")
    if r != "exists":
        failures.append("socket: setting the same socket again returned %r, expected 'exists'" % r)
    first = A.compile(bp).partition("\n")[0]
    if not first.startswith("errors=0"):
        failures.append("socket: the Blueprint does not compile (%s)" % first)
    r = A.set_component_socket(bp, "Nope", "Muzzle")
    if not str(r).startswith("ERROR"):
        failures.append("socket: a missing component returned %r, expected an error" % r)
    r = A.set_component_socket(bp, "Child", "None")
    if r or socket_of("Child") != "":
        failures.append("socket: clearing returned %r and reads %r" % (r, socket_of("Child")))


def check_font(failures):
    font = _create("F_DFCheck", unreal.Font, unreal.FontFactory())
    face = unreal.load_asset(FONT_FACE)
    if font is None or face is None:
        failures.append("font: could not create the font (%r) or load %s (%r)" % (font, FONT_FACE, face))
        return
    r = A.set_font_face(font, face)
    if r:
        failures.append("font: SetFontFace returned %r" % r)
    r = A.set_font_face(font, face)
    if r != "exists":
        failures.append("font: setting the same face again returned %r, expected 'exists'" % r)
    if font.get_editor_property("font_cache_type") != unreal.FontCacheType.RUNTIME:
        failures.append("font: cache type %r, expected RUNTIME" % font.get_editor_property("font_cache_type"))
    r = A.set_font_face(font, None)
    if not str(r).startswith("ERROR"):
        failures.append("font: a null face returned %r, expected an error" % r)


def main():
    if len(ELL.get_pie_worlds(False)) > 0:
        raise RuntimeError("a Play-In-Editor session is running (editor scripting is disabled during play); stop it first")
    dirty = unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()
    if len(dirty) > 0:
        raise RuntimeError("unsaved map changes (%s): save or discard them first" % ", ".join(p.get_name() for p in dirty))
    previous = ELL.get_editor_world().get_path_name().split(".")[0]
    failures = []
    del CREATED[:]
    try:
        for name, check in (("landscape", check_landscape), ("socket", check_socket), ("font", check_font)):
            try:
                check(failures)
            except Exception as e:  # keep going so one missing function does not hide the others
                failures.append("%s: %s: %s" % (name, type(e).__name__, e))
    finally:
        # delete by path: the assets were never saved, so the folder does not exist on disk. The emptied packages may
        # stay dirty in memory; the editor's save skips empty packages (it only deletes their files, and there are none).
        for asset in CREATED:
            if EAL.does_asset_exist(asset):
                EAL.delete_asset(asset)
        if previous.startswith("/Game/"):
            ELL.load_level(previous)
    left = [a for a in CREATED if EAL.does_asset_exist(a)]
    if left:
        failures.append("cleanup: %s still exist" % left)
    if failures:
        print("PLUGIN CHECK FAILED: %d failure(s)" % len(failures))
        for f in failures:
            print("  " + f[:300])
    else:
        print("PLUGIN CHECK OK")
    return not failures


main()
