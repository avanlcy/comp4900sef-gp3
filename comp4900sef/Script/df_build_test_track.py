"""Builds the test levels: ground, lights, a looped road with four checkpoint gates, a few infield props and the
player start. Run inside the Unreal Editor after the Blueprints are applied (df_apply_blueprint.py).

    exec(open(r'<repo>/comp4900sef/Script/df_build_test_track.py').read())

Builds /Game/DeadFire/Maps/L_TestTrack (the playable level) and /Game/DeadFire/Tests/L_DF_FunctionalTests (the same
track plus one actor per FT_DF* functional test Blueprint found under /Game/DeadFire/Tests). Re-running empties each
level and rebuilds it from scratch. Phase 7 Task 22: the shipped levels (L_TestTrack, L_Switchback, L_MainMenu) stand on a
landscape from art/terrain (run tools/artgen/build_all.py --kind terrain first) with its scatter; crates, the target car and
props are snapped to the ground there; every level gets the dusk light; the test level keeps its flat Ground cube.

A subset, or the art look-dev level (Phase 7; never part of the default list), without building everything first:

    DF_NO_MAIN=1; exec(open(r'<repo>/comp4900sef/Script/df_build_test_track.py').read()); main(maps=['/Game/DeadFire/Art/L_DF_LookDev'])

Blueprint functions are not called from here (UE 4.27 Python mis-binds Blueprint function parameters); the track is
driven through its native Spline component, and setting a property re-runs its construction script.
"""
import gc
import json
import math
import os
import unreal

MAPS = ['/Game/DeadFire/Maps/L_TestTrack', '/Game/DeadFire/Maps/L_Switchback', '/Game/DeadFire/Maps/L_MainMenu',
        '/Game/DeadFire/Tests/L_DF_FunctionalTests']
MENU_MAP = '/Game/DeadFire/Maps/L_MainMenu'
TEST_MAP = '/Game/DeadFire/Tests/L_DF_FunctionalTests'
TESTS_DIR = '/Game/DeadFire/Tests'
BP_DIR = '/Game/DeadFire/Blueprints'
ART_MESHES = '/Game/DeadFire/Art/Meshes'
RAMP, WEDGE, PYLON = ART_MESHES + '/SM_DF_Ramp', ART_MESHES + '/SM_DF_BumpWedge', ART_MESHES + '/SM_DF_GatePylon'  # Phase 7 Task 20

# Phase 7 Task 22 (spec §8.1, §8.3, §8.5): the shipped levels stand on their terrain (tools/artgen/terrain.py writes
# art/terrain/<name>.r16, .terrain.json and .scatter.json); the menu reuses PROVING GROUND's at its own origin, so the menu's
# (0, 0) is PROVING GROUND's start line on the flat valley floor. L_DF_FunctionalTests keeps its flat Ground cube.
TERRAINS = {'/Game/DeadFire/Maps/L_TestTrack': 'ProvingGround', '/Game/DeadFire/Maps/L_Switchback': 'Switchback',
            MENU_MAP: 'ProvingGround'}
TERRAIN_VERTICES = 1009                 # 8 x 8 components of 2 x 2 sections of 63 quads
TERRAIN_SCALE = 100.0                   # cm per vertex and the Z scale (terrain.json z_scale)
SNAP_FROM_Z = 20000.0                   # snap_to_ground traces down from here (over the 120 m ridge) to -SNAP_FROM_Z
CRATE_HALF_HEIGHT = 40.0                # SM_DF_Crate's origin is its centre (Task 17): the actor stands 40 cm over the ground
TARGET_CAR_DROP = 40.0                  # the target car's actor over the ground, as before (z 30 over the Ground cube's -10 top)
TARGET_CAR_PAINT = '/Game/DeadFire/Art/Materials/MI_DF_Paint_Gang'  # the parked target car wears the rivals' look (spec §3)
TARGET_CAR_TRIM = '/Game/DeadFire/Art/Materials/MI_DF_Trim_Gang'
TARGET_CAR_TRIM_SLOT = 1                # the Body's trim slot (df.TRIM_SLOT)
SCATTER_ROAD_CLEAR = 1400.0             # stale-json guard: no blocking scatter instance nearer a road centre line (spec §8.3)
SCATTER_MAX = 500                       # instances per map (spec §8.3)

# Kidney-shaped loop, world units (cm), about 490 m around. Road top surface is Z 0.
TRACK_POINTS = [
    (0, 0), (6000, -600), (11500, 1200), (14000, 5500), (12000, 9500),
    (7000, 9000), (3000, 11500), (-2500, 9000), (-4000, 4500), (-2500, 1200),
]
CHECKPOINT_COUNT = 4  # gates at equal distances along the road, the first on the start line

# Phase 7 Task 22: the Dead Fire meshes in the VehicleAdv props' places (SM_DF_Ramp and SM_DF_BumpWedge match RampLarge's and
# BumpWedge's bounds and pivots within 2 cm; the 6 m SM_DF_GatePylon stands where each pole stood). Z is the ground in the
# shipped maps (snap_to_ground), and as listed in the test level.
PROPS = [
    (RAMP, (6000, 4500, 0), 90),
    (PYLON, (4000, 3000, 0), 0),
    (PYLON, (8000, 3000, 0), 0),
    (PYLON, (4000, 6500, 0), 0),
    (PYLON, (8000, 6500, 0), 0),
    (WEDGE, (3000, 5000, 0), 45),
]

# Phase 3 (spec 2026-10-30 §3): loot crates off the road (at least MIN_CRATE_DISTANCE from every road centre line, so a car
# needs the off-track timer to reach one and a character on foot does not), and one parked target car for playtests.
LOOT_BOXES = [('Boost', (5000, 2500)), ('Shield', (7000, 6500)), ('Bomb', (2500, 8500)),
              ('Gun', (16500, 5500)), ('RPG', (-6500, 4500)), (None, (3000, 14000))]  # None = random
MIN_CRATE_DISTANCE = 1500
TARGET_CAR_DISTANCE = 3000  # cm along the main road from the start line
TARGET_CAR_OFFSET = 1500    # cm sideways, toward the infield

# Shortcut road (spec 2026-10-30 §7): an open second track from just after gate 1 to just before gate 2, bent toward the
# middle of the loop, with a destructible rock across it ROCK_DISTANCE in from its entrance.
SHORTCUT_FROM, SHORTCUT_TO = 0.25, 0.5          # fractions of the main loop (gates 1 and 2 sit at these)

# Phase 5 (spec 2026-10-30 phase 5 §2.2): SWITCHBACK, a longer loop (about 790 m) with a hairpin at the east end and an
# S-section on the way back; five gates; the shortcut cuts the hairpin between gates 1 and 2. Checked offline
# (Catmull-Rom approximation): no self-intersection, shortcut saving about 13 m, every crate 35 m or more from both roads.
SWITCHBACK_POINTS = [
    (0, 0), (9000, -600), (18000, 800), (25500, 3200), (25500, 9800), (18000, 12200), (12500, 10200),
    (8000, 13200), (3000, 14500), (-3000, 11500), (-4500, 5500), (-2500, 1200),
]
SWITCHBACK_PROPS = [
    (RAMP, (9000, 6500, 0), 0),
    (PYLON, (5000, 4000, 0), 0),
    (PYLON, (13000, 4000, 0), 0),
    (PYLON, (5000, 9000, 0), 0),
    (PYLON, (13000, 9000, 0), 0),
    (WEDGE, (16500, 6500, 0), 30),
]
SWITCHBACK_CRATES = [('Boost', (14000, 4500)), ('Shield', (6000, 6000)), ('Bomb', (-9000, 8000)),
                     ('Gun', (30000, 6500)), ('RPG', (16000, 17000)), (None, (3000, -5500))]

PROVING_GROUND = dict(points=TRACK_POINTS, gates=CHECKPOINT_COUNT, props=PROPS, crates=LOOT_BOXES,
                      target_car=(TARGET_CAR_DISTANCE, TARGET_CAR_OFFSET), shortcut=(SHORTCUT_FROM, SHORTCUT_TO),
                      game_mode=BP_DIR + '/BP_DFRaceGameMode')
LAYOUTS = {
    '/Game/DeadFire/Maps/L_TestTrack': PROVING_GROUND,
    '/Game/DeadFire/Maps/L_Switchback': dict(points=SWITCHBACK_POINTS, gates=5, props=SWITCHBACK_PROPS, crates=SWITCHBACK_CRATES,
                                             target_car=(3000, 1500), shortcut=(0.2, 0.4), game_mode=BP_DIR + '/BP_DFSwitchbackGameMode'),
    # Phase 4: the test level's GameMode spawns no NPCs (BP_DFTestGameMode, NPCCount 0); the AI tests spawn their own
    TEST_MAP: dict(PROVING_GROUND, game_mode=TESTS_DIR + '/BP_DFTestGameMode'),
}
SHORTCUT_GATE_CLEARANCE = 1500                  # cm after gate 1 / before gate 2
SHORTCUT_PULL = 0.1                             # how far the middle point moves toward the loop's centroid (more bows it as long as the main road)
SHORTCUT_Z = -2.0                               # slab top 2 cm under the main road (no flicker at the junctions)
MIN_SHORTCUT_SAVING = 1000                      # cm shorter than the main road between its junctions, or the builder refuses it
ROCK_DISTANCE = 1000                            # first distance in from the entrance tried for the rock (then +250 steps)
ROCK_SCALE = (4.0, 16.0, 4.0)                   # metres along the road, across it, tall (the mesh is a 1 m cube)
ROCK_CLEARANCE = 900                            # cm from the main centre line for every rock corner (2 m outside the 7 m half-width)

# Functional tests are laid out in rows south of the loop (open ground, away from the road and the infield props);
# each test spawns its own cars within about 10 m of its actor.
TEST_ORIGIN = (-4000, -7000, 200)
TEST_SPACING = 2500
DRIVE_STRIP_CENTRE = (5000, 45000, -50)         # Phase 7: cube 1000 x 40 x 1 -> 100,000 x 4,000 x 100 cm, top at Z 0
DRIVE_STRIP_TAG = 'DFDriveStrip'
TESTS_PER_ROW = 10

ell = unreal.EditorLevelLibrary
eal = unreal.EditorAssetLibrary
WORLD = unreal.SplineCoordinateSpace.WORLD


def vec(x, y, z=0.0):
    return unreal.Vector(float(x), float(y), float(z))


def rot(pitch=0.0, yaw=0.0, roll=0.0):
    return unreal.Rotator(roll=float(roll), pitch=float(pitch), yaw=float(yaw))


def bp_class(path):
    return unreal.load_class(None, '%s.%s_C' % (path, path.rsplit('/', 1)[1]))


def spawn(cls, location, rotation=None, label=None):
    actor = ell.spawn_actor_from_class(cls, location, rotation or rot())
    if actor is None:
        raise RuntimeError('could not spawn {}'.format(cls))
    if label:
        actor.set_actor_label(label)
    return actor


def spawn_light(cls, location, rotation=None, label=None):
    """A Movable light (Phase 6): nothing in the generated levels needs a lighting build, so no level ever shows
    "LIGHTING NEEDS TO BE REBUILT", and a rebuilt level never undoes a lighting build someone made by hand."""
    actor = spawn(cls, location, rotation, label)
    actor.get_component_by_class(unreal.LightComponentBase).set_mobility(unreal.ComponentMobility.MOVABLE)
    return actor


def spawn_static_mesh(mesh_path, location, rotation=None, scale=None, label=None, material_path=None):
    mesh = eal.load_asset(mesh_path)
    if mesh is None:
        raise RuntimeError('mesh not found: {}'.format(mesh_path))
    actor = spawn(unreal.StaticMeshActor, location, rotation, label)
    comp = actor.static_mesh_component
    comp.set_static_mesh(mesh)
    if material_path:
        material = eal.load_asset(material_path)
        if material:
            comp.set_material(0, material)
    if scale:
        actor.set_actor_scale3d(vec(*scale))
    return actor


def open_empty_level(path):
    """Opens the map with no actors in it (new_level refuses an existing asset, so a second run loads and clears).
    Tries to load first: the asset registry can lag behind the files on disk (e.g. after an in-editor test run)."""
    package_file = unreal.Paths.convert_relative_path_to_full(
        unreal.Paths.project_content_dir() + path[len('/Game/'):] + '.umap')
    exists = eal.does_asset_exist(path) or unreal.Paths.file_exists(package_file)
    if not exists:
        if not ell.new_level(path):
            raise RuntimeError('could not create level {}'.format(path))
        return
    if not ell.load_level(path):
        raise RuntimeError('could not load level {}'.format(path))
    for actor in ell.get_all_level_actors():
        ell.destroy_actor(actor)


def world_settings():
    world = ell.get_editor_world()
    settings = world.get_world_settings() if hasattr(world, 'get_world_settings') else None
    if settings is None:
        for actor in ell.get_all_level_actors():
            if isinstance(actor, unreal.WorldSettings):
                return actor
    if settings is None:
        raise RuntimeError('world settings not found')
    return settings


def item_type_entry(cls, name):
    """The Python enum entry for E_DFItemType.<name>: the editor wraps a Blueprint enum the first time one of its
    values is read, so read the class default first."""
    current = unreal.get_default_object(cls).get_editor_property('ItemType')
    return getattr(type(current), name.upper())


def centroid(points):
    return vec(sum(x for x, _ in points) / len(points), sum(y for _, y in points) / len(points), 0)


def distance_to_spline(spline, loc):
    closest = spline.find_location_closest_to_world_location(loc, WORLD)
    return (closest - loc).length()


def place_crates(splines, crates, on_terrain=False):
    """On terrain each crate's centre stands CRATE_HALF_HEIGHT over the ground under it (its pad); otherwise at z 30, 40 cm over
    the Ground cube's top."""
    cls = bp_class(BP_DIR + '/BP_DFLootBox')
    for name, (x, y) in crates:
        loc = vec(x, y, snap_to_ground(vec(x, y)) + CRATE_HALF_HEIGHT if on_terrain else 30)
        for spline in splines:
            d = distance_to_spline(spline, loc)
            if d < MIN_CRATE_DISTANCE:
                raise RuntimeError('crate %s at (%d, %d) is only %.0f cm from a road' % (name, x, y, d))
        crate = spawn(cls, loc, label='Crate_%s' % (name or 'Random'))
        if name:
            crate.set_editor_property('ItemType', item_type_entry(cls, name))
        else:
            crate.set_editor_property('bRandom', True)
    return len(crates)


def build_shortcut(main_spline, length, layout):
    """Spawns the Shortcut track and its rock; returns (spline, pieces)."""
    d1 = length * layout['shortcut'][0] + SHORTCUT_GATE_CLEARANCE
    d2 = length * layout['shortcut'][1] - SHORTCUT_GATE_CLEARANCE
    p1 = main_spline.get_location_at_distance_along_spline(d1, WORLD)
    p2 = main_spline.get_location_at_distance_along_spline(d2, WORLD)
    c = centroid(layout['points'])
    mid = (p1 + p2) * 0.5
    mid = mid + (c - mid) * SHORTCUT_PULL
    points = [vec(q.x, q.y, SHORTCUT_Z) for q in (p1, mid, p2)]
    track = spawn(bp_class(BP_DIR + '/BP_DFTrackSpline'), vec(0, 0, 0), label='Shortcut')
    track.set_editor_property('bIsMainTrack', False)
    track.set_editor_property('bClosedTrack', False)  # RebuildTrack applies this flag itself; an instance's SetClosedLoop does not survive the rerun
    spline = track.get_component_by_class(unreal.SplineComponent)
    spline.set_spline_points(points, WORLD, True)
    spline.set_closed_loop(False, True)
    spline.set_editor_property('spline_has_been_edited', True)
    track.set_editor_property('RoadWidth', float(track.get_editor_property('RoadWidth')))
    spline = track.get_component_by_class(unreal.SplineComponent)
    pieces = track.get_editor_property('GeneratedMeshCount')
    shortcut_length = spline.get_spline_length()
    want = max(1, int(math.ceil(shortcut_length / max(100.0, float(track.get_editor_property('PieceLength'))))))
    if pieces != want or spline.is_closed_loop():
        raise RuntimeError('shortcut construction failed: %d pieces (expected %d for %.0f cm), closed=%s'
                           % (pieces, want, shortcut_length, spline.is_closed_loop()))
    saving = (d2 - d1) - shortcut_length
    if saving < MIN_SHORTCUT_SAVING:
        raise RuntimeError('the shortcut saves only %.0f cm against %.0f cm of main road' % (saving, d2 - d1))
    # the rock: the first distance in from the entrance where all four footprint corners clear the main road
    half_x, half_y = 50.0 * ROCK_SCALE[0], 50.0 * ROCK_SCALE[1]
    for rock_distance in range(ROCK_DISTANCE, 3001, 250):
        t = spline.get_transform_at_distance_along_spline(rock_distance, WORLD)
        fwd = spline.get_direction_at_distance_along_spline(rock_distance, WORLD)
        right = spline.get_right_vector_at_distance_along_spline(rock_distance, WORLD)
        corners = [t.translation + fwd * sx + right * sy for sx in (-half_x, half_x) for sy in (-half_y, half_y)]
        clearance = min(distance_to_spline(main_spline, c) for c in corners)
        if clearance >= ROCK_CLEARANCE:
            break
    else:
        raise RuntimeError('no rock position on the shortcut clears the main road by %d cm' % ROCK_CLEARANCE)
    # Phase 7 Task 21: SM_DF_RockWall is centred (the unit contract) and Rock is BP_DFDestructible's root, so the actor stands
    # at the wall's centre: raised by half its height, the wall stands on the road top as Shape_Cube's base pivot made it
    rock = spawn(bp_class(BP_DIR + '/BP_DFDestructible'),
                 vec(t.translation.x, t.translation.y, SHORTCUT_Z + 50.0 * ROCK_SCALE[2]),
                 rot(yaw=t.rotation.rotator().yaw), label='Rock')
    rock.set_actor_scale3d(vec(*ROCK_SCALE))
    return spline, pieces, saving, rock_distance


def place_target_car(spline, layout, on_terrain=False):
    distance, offset = layout['target_car']
    t = spline.get_transform_at_distance_along_spline(distance, WORLD)
    right = spline.get_right_vector_at_distance_along_spline(distance, WORLD)
    c = centroid(layout['points'])
    a = t.translation + right * offset
    b = t.translation - right * offset
    loc = a if (a - c).length() < (b - c).length() else b
    z = snap_to_ground(loc) + TARGET_CAR_DROP if on_terrain else 30
    car = spawn(bp_class(BP_DIR + '/BP_DFVehicle'), vec(loc.x, loc.y, z), rot(yaw=t.rotation.rotator().yaw), label='TargetCar')
    # Task 22 fix round 1 (controller ruling, spec §3): the parked car is a rival, not a second player car: the gang paint (BeginPlay's
    # ApplyPaint), no light bar (the construction script reads bHasLightBar; setting it re-runs it), and the gang trim on the Body's
    # trim slot as an instance override of the Body component, set last so no rerun follows it
    car.set_editor_property('PaintMaterial', eal.load_asset(TARGET_CAR_PAINT))
    car.set_editor_property('bHasLightBar', False)
    body = [c for c in car.get_components_by_class(unreal.StaticMeshComponent) if c.get_name() == 'Body'][0]
    body.set_material(TARGET_CAR_TRIM_SLOT, eal.load_asset(TARGET_CAR_TRIM))


# ---- Phase 7 Task 22: terrain, ground snapping and scatter (spec §8.1, §8.3) ----

def repo_dir():
    return os.path.dirname(os.path.normpath(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())))


def terrain_file(map_name, suffix):
    """art/terrain/<terrain name><suffix> for a map in TERRAINS; raises when tools/artgen has not built it."""
    path = os.path.join(repo_dir(), 'art', 'terrain', TERRAINS[map_name] + suffix)
    if not os.path.isfile(path):
        raise RuntimeError('%s is missing: run build_all --kind terrain' % path)
    return path


def place_landscape(map_name):
    """The map's landscape from its terrain files through the plugin's CreateLandscapeFromRaw: TERRAIN_VERTICES square, the
    terrain.json origin as its corner (vertex 0, 0; Task 3), Z 0, scale 100, MI_DF_Terrain_<terrain>, labelled Terrain.
    Returns 'landscape NxN'."""
    raw = terrain_file(map_name, '.r16')
    with open(terrain_file(map_name, '.terrain.json')) as f:
        meta = json.load(f)
    n = TERRAIN_VERTICES
    if meta['vertices'] != n or meta['spacing_cm'] != TERRAIN_SCALE or meta['z_scale'] != TERRAIN_SCALE:
        raise RuntimeError('%s: terrain.json grid %s / %s / %s, the builder expects %d vertices at %g cm' % (
            map_name, meta['vertices'], meta['spacing_cm'], meta['z_scale'], n, TERRAIN_SCALE))
    ox, oy = meta['origin']
    material_path = '%s/Terrain/MI_DF_Terrain_%s' % (ART, TERRAINS[map_name])
    material = eal.load_asset(material_path)
    if material is None:
        raise RuntimeError('missing ' + material_path)
    result = unreal.DFBlueprintAuthoringLibrary.create_landscape_from_raw(
        ell.get_editor_world(), raw, n, vec(ox, oy, 0), vec(TERRAIN_SCALE, TERRAIN_SCALE, TERRAIN_SCALE), material, 'Terrain')
    if result:
        raise RuntimeError('CreateLandscapeFromRaw: %s' % result)
    lands = [a for a in ell.get_all_level_actors() if isinstance(a, unreal.Landscape)]
    side = (n - 1) * TERRAIN_SCALE
    centre, extent = lands[0].get_actor_bounds(False) if len(lands) == 1 else (None, None)
    if centre is None or abs(centre.x - (ox + side / 2)) > 1 or abs(centre.y - (oy + side / 2)) > 1 or abs(2 * extent.x - side) > 1:
        raise RuntimeError('%s: %d landscape(s), not one %.0f cm square from (%d, %d)' % (map_name, len(lands), side, ox, oy))
    return 'landscape %dx%d' % (n, n)


def snap_to_ground(location):
    """Z of the first blocking surface straight down at location's X and Y: a line trace from Z +SNAP_FROM_Z to -SNAP_FROM_Z
    (the landscape, or a road where one runs). Raises when nothing is there."""
    hit = unreal.SystemLibrary.line_trace_single(
        ell.get_editor_world(), vec(location.x, location.y, SNAP_FROM_Z), vec(location.x, location.y, -SNAP_FROM_Z),
        unreal.TraceTypeQuery.TRACE_TYPE_QUERY1, True, [], unreal.DrawDebugTrace.NONE, True)
    fields = hit.to_tuple() if hit is not None else None  # BreakHitResult order: blocking hit, initial overlap, time, distance, location
    if not fields or not fields[0]:
        raise RuntimeError('snap_to_ground: nothing under (%.0f, %.0f)' % (location.x, location.y))
    return fields[4].z


def spawn_scatter(mesh, blocking, transforms, label):
    """One BP_DFScatter (Task 21) at the world origin, so its instance transforms are world ones: Mesh and bBlocking, then
    Transforms ([x, y, z, yaw, scale] each), every set re-running its construction script (RebuildInstances). Returns the count."""
    mesh_asset = eal.load_asset('%s/%s' % (ART_MESHES, mesh))
    if mesh_asset is None:
        raise RuntimeError('scatter mesh not found: ' + mesh)
    actor = spawn(bp_class(BP_DIR + '/BP_DFScatter'), vec(0, 0, 0), label=label)
    actor.set_editor_property('Mesh', mesh_asset)
    actor.set_editor_property('bBlocking', bool(blocking))
    actor.set_editor_property('Transforms', [unreal.Transform(vec(x, y, z), rot(yaw=yaw), vec(s, s, s)) for x, y, z, yaw, s in transforms])
    count = actor.get_component_by_class(unreal.HierarchicalInstancedStaticMeshComponent).get_instance_count()
    if count != len(transforms):
        raise RuntimeError('%s: %d instances built from %d transforms' % (label, count, len(transforms)))
    return count


def scatter_entries(map_name):
    with open(terrain_file(map_name, '.scatter.json')) as f:
        return json.load(f)


def xy_distance_to_spline(spline, x, y):
    closest = spline.find_location_closest_to_world_location(vec(x, y, 0), WORLD)
    return math.hypot(closest.x - x, closest.y - y)


def place_scatter(map_name, splines):
    """One BP_DFScatter per entry of the map's scatter json (Task 19). Stale-json guard first: no blocking instance may lie within
    SCATTER_ROAD_CLEAR of a road centre line of the level as built, and at most SCATTER_MAX instances. Returns the count."""
    entries = scatter_entries(map_name)
    total = sum(len(e['transforms']) for e in entries)
    if total > SCATTER_MAX:
        raise RuntimeError('%s: %d scatter instances, over %d' % (map_name, total, SCATTER_MAX))
    for e in entries:
        for x, y, _, _, _ in (e['transforms'] if e['blocking'] else []):
            d = min(xy_distance_to_spline(s, x, y) for s in splines)
            if d < SCATTER_ROAD_CLEAR:
                raise RuntimeError('stale scatter json: blocking %s at (%.0f, %.0f) is %.0f cm from a road (want %.0f); run build_all '
                                   '--kind terrain' % (e['mesh'], x, y, d, SCATTER_ROAD_CLEAR))
    return sum(spawn_scatter(e['mesh'], e['blocking'], e['transforms'], 'Scatter_' + e['mesh'][len('SM_DF_'):]) for e in entries)


def functional_test_classes():
    classes = []
    for path in sorted(eal.list_assets(TESTS_DIR, recursive=False)):
        name = path.rsplit('/', 1)[1].split('.')[0]
        if name.startswith('FT_DF') and not name.startswith('FT_DFShot'):  # FT_DFShot_*: presentation captures, not tests
            cls = bp_class('%s/%s' % (TESTS_DIR, name))
            if cls:
                classes.append((name, cls))
    return classes


def build(path):
    layout = LAYOUTS[path]
    on_terrain = path in TERRAINS  # the shipped tracks; the functional-test level keeps its flat Ground cube (spec §8.1)
    open_empty_level(path)

    if on_terrain:
        land = place_landscape(path)
    else:
        spawn_static_mesh('/Engine/BasicShapes/Cube', vec(5000, 5000, -60), scale=(500, 500, 1),
                          label='Ground', material_path='/Game/VehicleAdv/Materials/MaterialInstances/LandscapeNoHole')
    apply_lighting('dusk')  # every map, the test level included (light is harmless to its tests)

    # Track: set the instance's spline points, flag them as edited so they survive construction-script reruns,
    # then touch a property to re-run the construction script (which lays the road pieces).
    track = spawn(bp_class(BP_DIR + '/BP_DFTrackSpline'), vec(0, 0, 0), label='MainTrack')
    spline = track.get_component_by_class(unreal.SplineComponent)
    spline.set_spline_points([vec(x, y, 0) for x, y in layout['points']], WORLD, True)
    spline.set_closed_loop(True, True)
    spline.set_editor_property('spline_has_been_edited', True)
    track.set_editor_property('RoadWidth', float(track.get_editor_property('RoadWidth')))
    spline = track.get_component_by_class(unreal.SplineComponent)  # the rerun replaced the component
    pieces = track.get_editor_property('GeneratedMeshCount')
    length = spline.get_spline_length()
    if pieces < 1 or spline.get_number_of_spline_points() != len(layout['points']):
        raise RuntimeError('track construction failed: %d pieces, %d spline points'
                           % (pieces, spline.get_number_of_spline_points()))

    checkpoint_class = bp_class(BP_DIR + '/BP_DFCheckpoint')
    for k in range(layout['gates']):
        t = spline.get_transform_at_distance_along_spline(length * k / float(layout['gates']), WORLD)
        gate = spawn(checkpoint_class, t.translation, rot(yaw=t.rotation.rotator().yaw), label='Checkpoint_{}'.format(k))
        gate.set_editor_property('CheckpointIndex', k)

    for mesh_path, (x, y, z), yaw in layout['props']:
        z = snap_to_ground(vec(x, y)) if on_terrain else z  # each prop's own pad (traced before it is spawned)
        spawn_static_mesh(mesh_path, vec(x, y, z), rot(yaw=yaw), label=mesh_path.rsplit('/', 1)[-1])

    shortcut, shortcut_pieces, shortcut_saving, rock_distance = build_shortcut(spline, length, layout)
    crates = place_crates([spline, shortcut], layout['crates'], on_terrain)
    place_target_car(spline, layout, on_terrain)
    scatter = place_scatter(path, [spline, shortcut]) if on_terrain else 0

    (x0, y0), (x1, y1) = layout['points'][0], layout['points'][1]
    yaw = math.degrees(math.atan2(y1 - y0, x1 - x0))
    spawn(unreal.PlayerStart, vec(x0, y0, 30), rot(yaw=yaw), label='PlayerStart')

    world_settings().set_editor_property('default_game_mode', bp_class(layout['game_mode']))

    tests = []
    if path == TEST_MAP:
        # Phase 7 Task 7: the flat drive strip (100,000 x 4,000 cm, top at Z 0, clear of the loop and the test rows) for the
        # top-speed and handling tests; tests find it by the actor tag
        strip = spawn_static_mesh('/Engine/BasicShapes/Cube', vec(*DRIVE_STRIP_CENTRE), scale=(1000, 40, 1), label='DriveStrip',
                                  material_path=ART + '/Materials/MI_DF_Concrete')
        strip.set_editor_property('tags', [DRIVE_STRIP_TAG])
        for i, (name, cls) in enumerate(functional_test_classes()):
            x, y, z = TEST_ORIGIN
            spawn(cls, vec(x + (i % TESTS_PER_ROW) * TEST_SPACING, y - (i // TESTS_PER_ROW) * TEST_SPACING, z), label=name)
            tests.append(name)

    summary = 'track %.0f cm, %d pieces, %d gates, shortcut %.0f cm in %d pieces saving %.0f cm with the rock at %d cm, %d crates, %d tests' % (
        length, pieces, layout['gates'], shortcut.get_spline_length(), shortcut_pieces, shortcut_saving, rock_distance, crates, len(tests))
    if not ell.save_current_level():
        raise RuntimeError('could not save {}'.format(path))
    return summary + (', %s, scatter %d' % (land, scatter) if on_terrain else '')


# Phase 5 (spec 2026-10-30 phase 5 §5.1): the main menu level shows the three cars on plinths, one camera each
SHOWCASE_CARS = ['/Game/DeadFire/Blueprints/BP_DFVehicle', '/Game/DeadFire/Blueprints/BP_DFVehicleBrute', '/Game/DeadFire/Blueprints/BP_DFVehicleViper']
SHOWCASE_SPACING = 700
SHOWCASE_CAMERA = (450, -650, 180)   # from the car, cm: forward-left of the nose
SHOWCASE_CAMERA_ROT = (-12, 125)     # pitch, yaw


# Phase 7 Task 22 (spec §8.5): the cars stand on SM_DF_Plinth turntables on PROVING GROUND's terrain (TERRAINS: its start line is
# the menu's (0, 0), on the flat valley floor), with MENU_PROPS of that terrain's own scatter instances in the cameras' view
# (yaw SHOWCASE_CAMERA_ROT[1] +- MENU_PROPS_CONE degrees from the origin, at least MENU_PROPS_MIN_CM out, the nearest first).
# The cars and cameras keep their heights over the deck as over the old cube plinths' tops.
PLINTH = ART_MESHES + '/SM_DF_Plinth'
PLINTH_FLAT_CM = 3.0      # the ground under a plinth's footprint (centre and rim) must be this level, or the build stops
MENU_PROPS = 20
MENU_PROPS_MIN_CM = 3000.0
MENU_PROPS_CONE = 55.0


def menu_props():
    """MENU_PROPS of the menu terrain's scatter instances in the showcase cameras' view, grouped per mesh:
    [(mesh, blocking, [transform, ...]), ...]."""
    view = SHOWCASE_CAMERA_ROT[1]
    pool = []
    for e in scatter_entries(MENU_MAP):
        for t in e['transforms']:
            x, y = t[0], t[1]
            off = (math.degrees(math.atan2(y, x)) - view + 180.0) % 360.0 - 180.0
            if math.hypot(x, y) >= MENU_PROPS_MIN_CM and abs(off) <= MENU_PROPS_CONE:
                pool.append((math.hypot(x, y), e['mesh'], e['blocking'], t))
    chosen = sorted(pool, key=lambda p: p[0])[:MENU_PROPS]
    if len(chosen) < MENU_PROPS:
        raise RuntimeError('only %d scatter instances in the menu view' % len(chosen))
    groups = {}
    for _, mesh, blocking, t in chosen:
        groups.setdefault((mesh, blocking), []).append(t)
    return [(mesh, blocking, ts) for (mesh, blocking), ts in sorted(groups.items())]


def build_menu_level(path):
    open_empty_level(path)
    land = place_landscape(path)
    apply_lighting('dusk')
    deck = eal.load_asset(PLINTH).get_bounding_box().max.z  # the plinth's base origin is its foot
    cars, cameras = 0, 0
    for k, car_path in enumerate(SHOWCASE_CARS):
        x = k * SHOWCASE_SPACING - SHOWCASE_SPACING
        ground = snap_to_ground(vec(x, 0))
        rim = [snap_to_ground(vec(x + 295 * math.cos(a), 295 * math.sin(a))) for a in (0, math.pi / 2, math.pi, 1.5 * math.pi)]
        if max(abs(z - ground) for z in rim) > PLINTH_FLAT_CM:
            raise RuntimeError('the ground under plinth %d is not flat: centre %.1f, rim %s cm' % (k, ground, ['%.1f' % z for z in rim]))
        spawn_static_mesh(PLINTH, vec(x, 0, ground), label='Plinth_%d' % k)
        top = ground + deck  # the old cube plinths' top was z 0: the car 60 cm and the camera SHOWCASE_CAMERA[2] over it
        spawn(bp_class(car_path), vec(x, 0, top + 60), rot(yaw=200), label='Showcase_%d' % k)
        cars += 1
        cam = spawn(unreal.CameraActor, vec(x + SHOWCASE_CAMERA[0], SHOWCASE_CAMERA[1], top + SHOWCASE_CAMERA[2]),
                    rot(pitch=SHOWCASE_CAMERA_ROT[0], yaw=SHOWCASE_CAMERA_ROT[1]), label='ShowcaseCamera_%d' % k)
        cam.set_editor_property('tags', ['Showcase%d' % k])
        cameras += 1
    props = sum(spawn_scatter(mesh, blocking, ts, 'Scatter_' + mesh[len('SM_DF_'):]) for mesh, blocking, ts in menu_props())
    spawn(unreal.AmbientSound, vec(0, 0, 200), label='MenuMusic')  # no sound set: the team drops a cue on it
    spawn(unreal.PlayerStart, vec(0, -1500, 100), label='PlayerStart')
    world_settings().set_editor_property('default_game_mode', bp_class(BP_DIR + '/BP_DFMenuGameMode'))
    if not ell.save_current_level():
        raise RuntimeError('could not save {}'.format(path))
    return '%d cars on plinths, %d cameras, %s, scatter %d' % (cars, cameras, land, props)


# Phase 7 (spec 8.4): light and post presets, starting values tuned on screenshots. sun_intensity is the value every
# builder used before Phase 7 (the DirectionalLight default, 10 lux); colours are sRGB 0-255.
# Task 22 tuning on the shipped levels' captures: at the spec's start (sun #FFB27A, fog 0.02) every frame read orange. The sky
# atmosphere scatters the sun's own colour (an orange sun made the whole sky orange) and already reddens a low sun, and the
# dense orange fog flattened the ridge into an orange wall. A warm-white sun and a third less fog keep the orange haze at the
# horizon and the warm light on the ground, with a dusky sky above and the ridge reading as rock.
LIGHTING = {
    'dusk': dict(sun_pitch=-14, sun_yaw=30, sun_color=(255, 205, 160), sun_intensity=10.0, fog_density=0.01,
                 fog_color=(200, 105, 58), bloom=0.8, exposure=(1.0, 1.5), vignette=0.4, saturation=1.05, white_temp=5800),
}


def srgb_to_linear(rgb):
    def one(c):
        c = c / 255.0
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
    return unreal.LinearColor(one(rgb[0]), one(rgb[1]), one(rgb[2]), 1.0)


def _find_or_spawn(cls, label, location, rotation=None, light=False):
    for actor in ell.get_all_level_actors():
        if type(actor) is cls:
            return actor
    return spawn_light(cls, location, rotation, label) if light else spawn(cls, location, rotation, label)


def apply_lighting(preset):
    """Spawns or updates, in the open level, the sun, a real-time-capture sky light, the sky atmosphere, the height fog
    and an unbound PostProcessVolume, with the LIGHTING[preset] values. Returns the preset name."""
    p = LIGHTING[preset]
    sun = _find_or_spawn(unreal.DirectionalLight, 'Sun', vec(0, 0, 2000), light=True)
    sun.set_actor_rotation(rot(pitch=p['sun_pitch'], yaw=p['sun_yaw']), False)
    sun_comp = sun.get_component_by_class(unreal.DirectionalLightComponent)
    sun_comp.set_mobility(unreal.ComponentMobility.MOVABLE)
    r, g, b = p['sun_color']
    sun_comp.set_editor_property('light_color', unreal.Color(r=r, g=g, b=b, a=255))
    sun_comp.set_editor_property('intensity', float(p['sun_intensity']))
    sun_comp.set_atmosphere_sun_light(True)
    sky = _find_or_spawn(unreal.SkyLight, 'SkyLight', vec(0, 0, 2000), light=True)
    sky_comp = sky.get_component_by_class(unreal.SkyLightComponent)
    sky_comp.set_mobility(unreal.ComponentMobility.MOVABLE)
    sky_comp.set_editor_property('real_time_capture', True)
    _find_or_spawn(unreal.SkyAtmosphere, 'SkyAtmosphere', vec(0, 0, 0))
    fog = _find_or_spawn(unreal.ExponentialHeightFog, 'HeightFog', vec(0, 0, 0))
    fog_comp = fog.get_component_by_class(unreal.ExponentialHeightFogComponent)
    fog_comp.set_editor_property('fog_density', float(p['fog_density']))
    fog_comp.set_editor_property('fog_inscattering_color', srgb_to_linear(p['fog_color']))
    post = None
    for actor in ell.get_all_level_actors():
        if isinstance(actor, unreal.PostProcessVolume) and actor.get_editor_property('unbound'):
            post = actor
    if post is None:
        post = spawn(unreal.PostProcessVolume, vec(0, 0, 0), label='PostProcess')
        post.set_editor_property('unbound', True)
    s = post.get_editor_property('settings')
    s.set_editor_property('override_bloom_intensity', True)
    s.set_editor_property('bloom_intensity', float(p['bloom']))
    s.set_editor_property('override_auto_exposure_min_brightness', True)
    s.set_editor_property('auto_exposure_min_brightness', float(p['exposure'][0]))
    s.set_editor_property('override_auto_exposure_max_brightness', True)
    s.set_editor_property('auto_exposure_max_brightness', float(p['exposure'][1]))
    s.set_editor_property('override_vignette_intensity', True)
    s.set_editor_property('vignette_intensity', float(p['vignette']))
    sat = float(p['saturation'])
    s.set_editor_property('override_color_saturation', True)
    s.set_editor_property('color_saturation', unreal.Vector4(sat, sat, sat, 1.0))
    s.set_editor_property('override_white_temp', True)
    s.set_editor_property('white_temp', float(p['white_temp']))
    post.set_editor_property('settings', s)
    return preset


# Phase 7 (plan Task 5): the look-dev level. Never cooked: not in the packaging map list and referenced by nothing.
# Ball row (y = 0): a 2 m sphere per MI_DF_* in the catalogue, centres 4 m apart, the natural surfaces of the Poly Haven
# gate first, each of those also on a flat 3.6 m swatch under its ball (ground is seen flat, and the road's world UVs
# smear on a sphere); a decal instance becomes a decal on the floor instead. Mesh row (y = LOOKDEV_MESH_ROW_Y): every imported
# mesh, centres at least 4 m apart (wider when the meshes would touch). Cameras tagged LookDevShot00.. frame them for
# FT_DFShot_LookDev (tools/capture_shots.py lookdev): the gate sets in pairs at 5 m and all together at 30 m, the other
# balls in groups, the meshes in groups. A mesh whose origin is its hub or centre (wheel, shield bubble, flame) rests on
# the floor. A car body (origin = the vehicle actor's) gets SM_DF_Wheel on its Arch_<bone> sockets and SEDAN its light
# bar on Roof, as the vehicle Blueprint mounts them (Task 12), and the cars get their own shots: side on and from behind
# at 30 m, and a three-quarter view of each at 7 m. A BP_DFCharacter (Task 14) stands beside SEDAN in its gear, with no
# controller (its idle animation plays and nothing moves it), and gets four shots: with the car, and close up from the
# front, the rifle side and behind. An assembled gate (Task 20: two pylons and the stretched banner, as BP_DFCheckpoint
# places them) stands beyond the rows' -X end with BRUTE and its roof gun under it, and gets two shots: from the road
# and a low view of the car's clearance.
LOOKDEV_MAP = '/Game/DeadFire/Art/L_DF_LookDev'
LOOKDEV_CHARACTER = '/Game/DeadFire/Blueprints/BP_DFCharacter'
ART = '/Game/DeadFire/Art'
LOOKDEV_SPACING = 400
LOOKDEV_BALL_SCALE = 2.0
LOOKDEV_MESH_ROW_Y = 1200
LOOKDEV_FLOOR_TILE = 800          # cm; the floor is MI_DF_Concrete on 8 m planes (the material uses mesh UVs)
LOOKDEV_SWATCH = 360              # cm; the flat swatch under each gate ball
LOOKDEV_MAX_SHOTS = 48            # FT_DFShot_LookDev visits LookDevShot00..47 and skips the tags that are absent
LOOKDEV_TALL_CM = 1250            # a mesh-row shot frames its group's height up to this (Task 20: trees, light tower, billboard)
LOOKDEV_FOV = 70.0
LOOKDEV_WHEEL = '/Game/DeadFire/Art/Meshes/SM_DF_Wheel'
LOOKDEV_LIGHT_BAR = ('SM_DF_Car_Sedan', 'Roof', '/Game/DeadFire/Art/Meshes/SM_DF_LightBar')
GATE_BALLS = ['MI_DF_Road', 'MI_DF_Concrete', 'MI_DF_Dirt', 'MI_DF_AshGround', 'MI_DF_DryGrass', 'MI_DF_Rock',
              'MI_DF_Sand', 'MI_DF_RustMetal', 'MI_DF_ContainerPaint', 'MI_DF_CrateMetal']  # spec 4.6 surfaces, in pairs


def _art_assets(folder, cls):
    out = []
    for path in sorted(eal.list_assets('%s/%s' % (ART, folder), recursive=False)):
        obj = eal.load_asset(path.split('.')[0])
        if isinstance(obj, cls):
            out.append(obj)
    return out


def _label(text, location, yaw):
    actor = spawn(unreal.TextRenderActor, location, rot(yaw=yaw), label='Label_' + text)
    comp = actor.get_component_by_class(unreal.TextRenderComponent)
    comp.set_text(text)
    comp.set_editor_property('horizontal_alignment', unreal.HorizTextAligment.EHTA_CENTER)
    comp.set_editor_property('world_size', 24.0)
    return actor


def _shot_camera(index, target, distance, height, facing_y):
    """A camera `distance` cm from `target` along -facing_y, looking at it along facing_y (+1 or -1)."""
    x, y, z = target
    cam_loc = vec(x, y - facing_y * distance, height)
    pitch = -math.degrees(math.atan2(height - z, distance))
    cam = spawn(unreal.CameraActor, cam_loc, rot(pitch=pitch, yaw=90 if facing_y > 0 else -90), label='LookDevShot%02d' % index)
    comp = cam.get_component_by_class(unreal.CameraComponent)
    comp.set_editor_property('field_of_view', LOOKDEV_FOV)
    comp.set_editor_property('constrain_aspect_ratio', False)
    cam.set_editor_property('tags', ['LookDevShot%02d' % index])
    return cam


def _aimed_camera(index, cam_loc, target):
    """A look-dev camera at cam_loc looking at target (both (x, y, z) cm)."""
    dx, dy, dz = (t - c for t, c in zip(target, cam_loc))
    yaw = math.degrees(math.atan2(dy, dx))
    pitch = math.degrees(math.atan2(dz, math.hypot(dx, dy)))
    cam = spawn(unreal.CameraActor, vec(*cam_loc), rot(pitch=pitch, yaw=yaw), label='LookDevShot%02d' % index)
    comp = cam.get_component_by_class(unreal.CameraComponent)
    comp.set_editor_property('field_of_view', LOOKDEV_FOV)
    comp.set_editor_property('constrain_aspect_ratio', False)
    cam.set_editor_property('tags', ['LookDevShot%02d' % index])
    return cam


def _car_parts(mesh, loc):
    """SM_DF_Wheel on a car body's Arch_<wheel bone> sockets (the right ones, +Y, yawed 180) and SEDAN's light bar on
    its Roof socket, so the look-dev row shows the car as it races. Returns the wheels placed."""
    vehicle = unreal.get_default_object(bp_class('/Game/DeadFire/Blueprints/BP_DFVehicle'))
    bones = [str(w.get_editor_property('bone_name'))
             for w in vehicle.get_editor_property('vehicle_movement').get_editor_property('wheel_setups')]
    names = ['Arch_' + b for b in bones] + ([LOOKDEV_LIGHT_BAR[1]] if mesh.get_name() == LOOKDEV_LIGHT_BAR[0] else [])
    n = 0
    for name in names:  # StaticMesh.Sockets is protected from Python: look each socket up by name
        sock = mesh.find_socket(name)
        if sock is None:
            continue
        p = sock.get_editor_property('relative_location')
        at = vec(loc.x + p.x, loc.y + p.y, loc.z + p.z)
        if name.startswith('Arch_'):
            spawn_static_mesh(LOOKDEV_WHEEL, at, rot(yaw=180.0 if p.y > 0 else 0.0), label='%s_%s' % (mesh.get_name(), name[5:]))
            n += 1
        else:
            spawn_static_mesh(LOOKDEV_LIGHT_BAR[2], at, label=mesh.get_name() + '_LightBar')
    return n


def _character_beside(car_x):
    """BP_DFCharacter by SEDAN's driver door, facing the cameras (+Y; its right hand is towards -X), its capsule on the
    floor; never possessed. Returns the camera (location, target) pairs of its shots."""
    x, y = car_x - 60.0, LOOKDEV_MESH_ROW_Y + 235.0
    ch = spawn(bp_class(LOOKDEV_CHARACTER), vec(x, y, 96.0), rot(yaw=90.0), label='Character')
    ch.set_editor_property('auto_possess_ai', unreal.AutoPossessAI.DISABLED)
    return [((x - 330, y + 480, 220), (x + 40, y - 130, 90)),   # with the car, front right
            ((x - 150, y + 210, 165), (x - 10, y, 105)),        # close up, front right
            ((x - 210, y - 20, 110), (x - 30, y, 90)),          # the rifle side
            ((x - 260, y - 90, 200), (x, y, 115))]              # behind right, as the chase camera sees it


LOOKDEV_GATE = (-5000.0, 600.0)   # Task 20: an assembled gate, clear of the rows and their cameras; the road runs along +X
LOOKDEV_GATE_POLE_Y = 800.0       # BP_DFCheckpoint's PoleOffset (df.GATE_POLE_OFFSET; Task 22: 700 -> 800)


def _gate_with_car():
    """Two SM_DF_GatePylon PoleOffset either side of LOOKDEV_GATE with SM_DF_GateBanner stretched between them (Y scale
    2 x PoleOffset / 100), all on the gate's origin as BP_DFCheckpoint will place them, and BRUTE (the tallest car) with its
    wheels and the roof gun under the banner. Returns the camera (location, target) pairs: from the road 25 m before the
    gate at a driver's eye height, and a low three-quarter view of the car passing under the banner."""
    gx, gy = LOOKDEV_GATE
    for side in (1, -1):
        spawn_static_mesh(ART + '/Meshes/SM_DF_GatePylon', vec(gx, gy + side * LOOKDEV_GATE_POLE_Y, 0), label='Gate_Pylon_%+d' % side)
    spawn_static_mesh(ART + '/Meshes/SM_DF_GateBanner', vec(gx, gy, 0), scale=(1, 2 * LOOKDEV_GATE_POLE_Y / 100.0, 1), label='Gate_Banner')
    car = eal.load_asset(ART + '/Meshes/SM_DF_Car_Brute')
    at = vec(gx + 60, gy - 150, 0)
    spawn_static_mesh(car.get_path_name().split('.')[0], at, label='Gate_Car_Brute')
    _car_parts(car, at)
    roof = car.find_socket('Roof').get_editor_property('relative_location')
    spawn_static_mesh(ART + '/Meshes/SM_DF_RoofGun', vec(at.x + roof.x, at.y + roof.y, at.z + roof.z), label='Gate_Car_RoofGun')
    return [((gx - 2500, gy - 120, 150), (gx, gy, 300)),
            ((gx - 900, gy - 1050, 110), (gx + 60, gy - 150, 260))]


def _span_distance(span_cm):
    """Camera distance that fits a row segment span_cm wide (plus 2 m) in the horizontal field of view."""
    return (span_cm / 2.0 + 200.0) / math.tan(math.radians(LOOKDEV_FOV / 2.0))


def build_lookdev(path):
    open_empty_level(path)
    instances = [m for folder in ('Materials', 'Terrain') for m in _art_assets(folder, unreal.MaterialInstanceConstant)
                 if m.get_name().startswith('MI_DF_')]
    meshes = [m for m in _art_assets('Meshes', unreal.StaticMesh) if m.get_name().startswith('SM_DF_')]
    meshes += [m for m in _art_assets('Fx', unreal.StaticMesh) if m.get_name().startswith('SM_DF_')]
    gate = [m for name in GATE_BALLS for m in instances if m.get_name() == name]
    balls = gate + [m for m in instances if m not in gate]
    sphere = eal.load_asset('/Engine/BasicShapes/Sphere')
    radius = 50.0 * LOOKDEV_BALL_SCALE
    for i, mi in enumerate(balls):
        x = i * LOOKDEV_SPACING
        short = mi.get_name()[len('MI_DF_'):]
        if mi.get_base_material().get_editor_property('material_domain') == unreal.MaterialDomain.MD_DEFERRED_DECAL:
            decal = spawn(unreal.DecalActor, vec(x, 0, 0), rot(pitch=-90), label='Decal_' + short)
            decal.get_component_by_class(unreal.DecalComponent).set_decal_material(mi)
            decal.set_actor_scale3d(vec(0.5, 0.4, 0.4))  # DecalSize (128, 256, 256) half-extents: a 2 m square, 64 cm deep
        else:
            ball = spawn(unreal.StaticMeshActor, vec(x, 0, radius), label='Ball_' + short)
            ball.static_mesh_component.set_static_mesh(sphere)
            ball.static_mesh_component.set_material(0, mi)
            ball.set_actor_scale3d(vec(LOOKDEV_BALL_SCALE, LOOKDEV_BALL_SCALE, LOOKDEV_BALL_SCALE))
            if mi in gate:
                spawn_static_mesh('/Engine/BasicShapes/Plane', vec(x, 0, 0.5), scale=(LOOKDEV_SWATCH / 100.0,) * 2 + (1,),
                                  label='Swatch_' + short, material_path=mi.get_path_name().split('.')[0])
        _label(short, vec(x, -radius - 60, 2), -90)
    placed, x_prev, half_prev, cars, sedan_x = [], None, 0.0, [], None
    for mesh in meshes:
        box = mesh.get_bounding_box()
        half = (box.max.x - box.min.x) / 2.0
        x = 0.0 if x_prev is None else x_prev + max(LOOKDEV_SPACING, half_prev + half + 200.0)
        centre_x = (box.max.x + box.min.x) / 2.0
        loc = vec(x - centre_x, LOOKDEV_MESH_ROW_Y, max(0.0, -box.min.z))  # a hub- or centre-origin mesh rests on the floor
        spawn_static_mesh(mesh.get_path_name().split('.')[0], loc, label=mesh.get_name())
        if mesh.get_name().startswith('SM_DF_Car_') and _car_parts(mesh, loc):
            cars.append(x)
            if mesh.get_name() == LOOKDEV_LIGHT_BAR[0]:
                sedan_x = x
        _label(mesh.get_name()[len('SM_DF_'):], vec(x, LOOKDEV_MESH_ROW_Y + box.max.y + 80, 2), 90)
        placed.append((x, half, loc.z + box.max.z))
        x_prev, half_prev = x, half
    # floor: 8 m tiles under the rows, and one wide plane beneath them out to the cameras and the horizon
    concrete = ART + '/Materials/MI_DF_Concrete'
    row_end = max((len(balls) - 1) * LOOKDEV_SPACING, placed[-1][0] if placed else 0)
    x0, x1 = -1600, row_end + 1600
    y0, y1 = -3400, LOOKDEV_MESH_ROW_Y + 1600
    tiles = 0
    for ix in range(int(math.ceil((x1 - x0) / float(LOOKDEV_FLOOR_TILE)))):
        for iy in range(int(math.ceil((y1 - y0) / float(LOOKDEV_FLOOR_TILE)))):
            spawn_static_mesh('/Engine/BasicShapes/Plane', vec(x0 + (ix + 0.5) * LOOKDEV_FLOOR_TILE, y0 + (iy + 0.5) * LOOKDEV_FLOOR_TILE, 0),
                              scale=(LOOKDEV_FLOOR_TILE / 100.0,) * 2 + (1,), label='Floor_%d_%d' % (ix, iy), material_path=concrete)
            tiles += 1
    spawn_static_mesh('/Engine/BasicShapes/Plane', vec((x0 + x1) / 2.0, 0, -2), scale=(2000, 2000, 1), label='FloorFar',
                      material_path=concrete)
    apply_lighting('dusk')
    # cameras: gate pairs at 5 m and the gate row at 30 m, then the other balls and the meshes in groups
    shots = []
    for k in range(0, len(gate), 2):
        shots.append(((k + 0.5) * LOOKDEV_SPACING, 0, radius, 500, 160, 1))
    if gate:
        shots.append(((len(gate) - 1) * LOOKDEV_SPACING / 2.0, 0, radius, 3000, 400, 1))
    rest = len(balls) - len(gate)
    groups = int(math.ceil(rest / 6.0))  # at most 6 balls a shot, the groups as even as possible
    k = len(gate)
    for g in range(groups):
        size = rest // groups + (1 if g < rest % groups else 0)
        last = k + size - 1
        span = (last - k) * LOOKDEV_SPACING
        shots.append(((k + last) * LOOKDEV_SPACING / 2.0, 0, radius, max(800.0, _span_distance(span)), 250, 1))
        k = last + 1
    k = 0
    while k < len(placed):
        j = k
        while j + 1 < len(placed) and (placed[j + 1][0] + placed[j + 1][1]) - (placed[k][0] - placed[k][1]) <= 1600:
            j += 1
        span = (placed[j][0] + placed[j][1]) - (placed[k][0] - placed[k][1])
        # a group with a tall mesh (over 5 m) is framed to its height, up to LOOKDEV_TALL_CM: aimed at half of it, from
        # far enough back that the 16:9 view's vertical field holds it
        tall = min(max(p[2] for p in placed[k:j + 1]), LOOKDEV_TALL_CM)
        aim = 80.0 if tall <= 500 else tall / 2.0
        reach = 0.0 if tall <= 500 else (tall / 2.0 + 150.0) / (math.tan(math.radians(LOOKDEV_FOV / 2.0)) * 9.0 / 16.0)
        shots.append(((placed[k][0] - placed[k][1] + placed[j][0] + placed[j][1]) / 2.0, LOOKDEV_MESH_ROW_Y, aim,
                      max(600.0, _span_distance(span), reach), max(250.0, aim + 170.0), -1))
        k = j + 1
    aimed = []  # (camera, target): the cars from behind at 30 m and each at 7 m
    if cars:
        cx = (cars[0] + cars[-1]) / 2.0
        shots.append((cx, LOOKDEV_MESH_ROW_Y, 80, 3000, 400, -1))  # side on at 30 m
        aimed.append(((cx - 2300, LOOKDEV_MESH_ROW_Y + 1850, 700), (cx, LOOKDEV_MESH_ROW_Y, 80)))
        aimed += [((x + 480, LOOKDEV_MESH_ROW_Y + 480, 260), (x, LOOKDEV_MESH_ROW_Y, 70)) for x in cars]
    if sedan_x is not None:
        aimed += _character_beside(sedan_x)
    if all(eal.does_asset_exist(ART + '/Meshes/' + n) for n in ('SM_DF_GatePylon', 'SM_DF_GateBanner', 'SM_DF_Car_Brute', 'SM_DF_RoofGun')):
        aimed += _gate_with_car()
    if len(shots) + len(aimed) > LOOKDEV_MAX_SHOTS:
        raise RuntimeError('look-dev needs %d shots; FT_DFShot_LookDev visits %d' % (len(shots) + len(aimed), LOOKDEV_MAX_SHOTS))
    for i, (x, y, z, distance, height, facing) in enumerate(shots):
        _shot_camera(i, (x, y, z), distance, height, facing)
    for i, (cam_loc, target) in enumerate(aimed):
        _aimed_camera(len(shots) + i, cam_loc, target)
    shots += aimed
    spawn(unreal.PlayerStart, vec(-4000, 0, -1000), label='PlayerStart')  # under the floor: the default pawn stays out of every shot
    world_settings().set_editor_property('default_game_mode', unreal.GameModeBase.static_class())
    if not ell.save_current_level():
        raise RuntimeError('could not save {}'.format(path))
    return '%d meshes, %d materials (%d floor tiles, %d shots)' % (len(meshes), len(balls), tiles, len(shots))


def main(maps=None):
    if len(ell.get_pie_worlds(False)) > 0:
        raise RuntimeError('a Play-In-Editor session is running (editor scripting is disabled during play); stop it first')
    results = []
    for path in maps or MAPS:
        # Task 19 lesson: no Python wrapper of a world or actor may live across a level load (the editor aborts with "World
        # Memory Leaks"). Each level is built in its own function frame that returns text; a failure keeps only its message
        # (its traceback would hold the frame's actors), and garbage is collected before the next load.
        gc.collect()
        error = None
        try:
            if path == MENU_MAP:
                result = build_menu_level(path)
            elif path == LOOKDEV_MAP:
                result = build_lookdev(path)
            else:
                result = build(path)
        except Exception as e:
            error = '%s: %s' % (type(e).__name__, e)
        if error:
            raise RuntimeError('df_build_test_track FAILED at %s: %s' % (path.rsplit('/', 1)[1], error))
        results.append('%s: %s' % (path.rsplit('/', 1)[1], result))
    gc.collect()
    ell.load_level(MAPS[0])
    print('df_build_test_track: OK; ' + '; '.join(results))


# DF_NO_MAIN=1 before exec() loads the functions without building (then call main(maps=[...])). Remote-execution globals
# persist between calls, so the flag is consumed here: the next plain exec() builds again.
if not globals().pop('DF_NO_MAIN', None):
    main()
