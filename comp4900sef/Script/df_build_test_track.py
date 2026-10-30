"""Builds the test levels: ground, lights, a looped road with four checkpoint gates, a few infield props and the
player start. Run inside the Unreal Editor after the Blueprints are applied (df_apply_blueprint.py).

    exec(open(r'<repo>/comp4900sef/Script/df_build_test_track.py').read())

Builds /Game/DeadFire/Maps/L_TestTrack (the playable level) and /Game/DeadFire/Tests/L_DF_FunctionalTests (the same
track plus one actor per FT_DF* functional test Blueprint found under /Game/DeadFire/Tests). Re-running empties each
level and rebuilds it from scratch.

Blueprint functions are not called from here (UE 4.27 Python mis-binds Blueprint function parameters); the track is
driven through its native Spline component, and setting a property re-runs its construction script.
"""
import math
import unreal

MAPS = ['/Game/DeadFire/Maps/L_TestTrack', '/Game/DeadFire/Tests/L_DF_FunctionalTests']
TEST_MAP = '/Game/DeadFire/Tests/L_DF_FunctionalTests'
TESTS_DIR = '/Game/DeadFire/Tests'
BP_DIR = '/Game/DeadFire/Blueprints'

# Kidney-shaped loop, world units (cm), about 490 m around. Road top surface is Z 0.
TRACK_POINTS = [
    (0, 0), (6000, -600), (11500, 1200), (14000, 5500), (12000, 9500),
    (7000, 9000), (3000, 11500), (-2500, 9000), (-4000, 4500), (-2500, 1200),
]
CHECKPOINT_COUNT = 4  # gates at equal distances along the road, the first on the start line

PROPS = [
    ('/Game/VehicleAdv/ArenaMesh/RampLarge', (6000, 4500, 0), 90),
    ('/Game/VehicleAdv/ArenaMesh/pole', (4000, 3000, 0), 0),
    ('/Game/VehicleAdv/ArenaMesh/pole', (8000, 3000, 0), 0),
    ('/Game/VehicleAdv/ArenaMesh/pole', (4000, 6500, 0), 0),
    ('/Game/VehicleAdv/ArenaMesh/pole', (8000, 6500, 0), 0),
    ('/Game/VehicleAdv/ArenaMesh/BumpWedge', (3000, 5000, 0), 45),
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


def centroid():
    return vec(sum(x for x, _ in TRACK_POINTS) / len(TRACK_POINTS), sum(y for _, y in TRACK_POINTS) / len(TRACK_POINTS), 0)


def distance_to_spline(spline, loc):
    closest = spline.find_location_closest_to_world_location(loc, WORLD)
    return (closest - loc).length()


def place_crates(splines):
    cls = bp_class(BP_DIR + '/BP_DFLootBox')
    for name, (x, y) in LOOT_BOXES:
        loc = vec(x, y, 30)
        for spline in splines:
            d = distance_to_spline(spline, loc)
            if d < MIN_CRATE_DISTANCE:
                raise RuntimeError('crate %s at (%d, %d) is only %.0f cm from a road' % (name, x, y, d))
        crate = spawn(cls, loc, label='Crate_%s' % (name or 'Random'))
        if name:
            crate.set_editor_property('ItemType', item_type_entry(cls, name))
        else:
            crate.set_editor_property('bRandom', True)
    return len(LOOT_BOXES)


def build_shortcut(main_spline, length):
    """Spawns the Shortcut track and its rock; returns (spline, pieces)."""
    d1 = length * SHORTCUT_FROM + SHORTCUT_GATE_CLEARANCE
    d2 = length * SHORTCUT_TO - SHORTCUT_GATE_CLEARANCE
    p1 = main_spline.get_location_at_distance_along_spline(d1, WORLD)
    p2 = main_spline.get_location_at_distance_along_spline(d2, WORLD)
    c = centroid()
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
    # Shape_Cube's pivot is at its base: the block stands on the road top
    rock = spawn(bp_class(BP_DIR + '/BP_DFDestructible'), vec(t.translation.x, t.translation.y, SHORTCUT_Z),
                 rot(yaw=t.rotation.rotator().yaw), label='Rock')
    rock.set_actor_scale3d(vec(*ROCK_SCALE))
    return spline, pieces, saving, rock_distance


def place_target_car(spline):
    t = spline.get_transform_at_distance_along_spline(TARGET_CAR_DISTANCE, WORLD)
    right = spline.get_right_vector_at_distance_along_spline(TARGET_CAR_DISTANCE, WORLD)
    c = centroid()
    a = t.translation + right * TARGET_CAR_OFFSET
    b = t.translation - right * TARGET_CAR_OFFSET
    loc = a if (a - c).length() < (b - c).length() else b
    spawn(bp_class(BP_DIR + '/BP_DFVehicle'), vec(loc.x, loc.y, 30), rot(yaw=t.rotation.rotator().yaw), label='TargetCar')


def functional_test_classes():
    classes = []
    for path in sorted(eal.list_assets(TESTS_DIR, recursive=False)):
        name = path.rsplit('/', 1)[1].split('.')[0]
        if name.startswith('FT_DF'):
            cls = bp_class('%s/%s' % (TESTS_DIR, name))
            if cls:
                classes.append((name, cls))
    return classes


def build(path):
    open_empty_level(path)

    spawn_static_mesh('/Engine/BasicShapes/Cube', vec(5000, 5000, -60), scale=(500, 500, 1),
                      label='Ground', material_path='/Game/VehicleAdv/Materials/MaterialInstances/LandscapeNoHole')
    spawn(unreal.DirectionalLight, vec(0, 0, 2000), rot(pitch=-45, yaw=30), label='Sun')
    spawn(unreal.SkyLight, vec(0, 0, 2000), label='SkyLight')
    spawn(unreal.SkyAtmosphere, vec(0, 0, 0), label='SkyAtmosphere')
    fog = spawn(unreal.ExponentialHeightFog, vec(0, 0, 0), label='HeightFog')
    fog_comp = fog.get_component_by_class(unreal.ExponentialHeightFogComponent)
    fog_comp.set_editor_property('fog_density', 0.004)
    fog_comp.set_editor_property('start_distance', 3000.0)

    # Track: set the instance's spline points, flag them as edited so they survive construction-script reruns,
    # then touch a property to re-run the construction script (which lays the road pieces).
    track = spawn(bp_class(BP_DIR + '/BP_DFTrackSpline'), vec(0, 0, 0), label='MainTrack')
    spline = track.get_component_by_class(unreal.SplineComponent)
    spline.set_spline_points([vec(x, y, 0) for x, y in TRACK_POINTS], WORLD, True)
    spline.set_closed_loop(True, True)
    spline.set_editor_property('spline_has_been_edited', True)
    track.set_editor_property('RoadWidth', float(track.get_editor_property('RoadWidth')))
    spline = track.get_component_by_class(unreal.SplineComponent)  # the rerun replaced the component
    pieces = track.get_editor_property('GeneratedMeshCount')
    length = spline.get_spline_length()
    if pieces < 1 or spline.get_number_of_spline_points() != len(TRACK_POINTS):
        raise RuntimeError('track construction failed: %d pieces, %d spline points'
                           % (pieces, spline.get_number_of_spline_points()))

    checkpoint_class = bp_class(BP_DIR + '/BP_DFCheckpoint')
    for k in range(CHECKPOINT_COUNT):
        t = spline.get_transform_at_distance_along_spline(length * k / float(CHECKPOINT_COUNT), WORLD)
        gate = spawn(checkpoint_class, t.translation, rot(yaw=t.rotation.rotator().yaw), label='Checkpoint_{}'.format(k))
        gate.set_editor_property('CheckpointIndex', k)

    for mesh_path, (x, y, z), yaw in PROPS:
        spawn_static_mesh(mesh_path, vec(x, y, z), rot(yaw=yaw), label=mesh_path.rsplit('/', 1)[-1])

    shortcut, shortcut_pieces, shortcut_saving, rock_distance = build_shortcut(spline, length)
    crates = place_crates([spline, shortcut])
    place_target_car(spline)

    (x0, y0), (x1, y1) = TRACK_POINTS[0], TRACK_POINTS[1]
    yaw = math.degrees(math.atan2(y1 - y0, x1 - x0))
    spawn(unreal.PlayerStart, vec(x0, y0, 30), rot(yaw=yaw), label='PlayerStart')

    # Phase 4: the test level's GameMode spawns no NPCs (BP_DFTestGameMode, NPCCount 0); the AI tests spawn their own
    game_mode = TESTS_DIR + '/BP_DFTestGameMode' if path == TEST_MAP else BP_DIR + '/BP_DFRaceGameMode'
    world_settings().set_editor_property('default_game_mode', bp_class(game_mode))

    tests = []
    if path == TEST_MAP:
        for i, (name, cls) in enumerate(functional_test_classes()):
            x, y, z = TEST_ORIGIN
            spawn(cls, vec(x + (i % TESTS_PER_ROW) * TEST_SPACING, y - (i // TESTS_PER_ROW) * TEST_SPACING, z), label=name)
            tests.append(name)

    if not ell.save_current_level():
        raise RuntimeError('could not save {}'.format(path))
    return 'track %.0f cm, %d pieces, %d gates, shortcut %.0f cm in %d pieces saving %.0f cm with the rock at %d cm, %d crates, %d tests' % (
        length, pieces, CHECKPOINT_COUNT, shortcut.get_spline_length(), shortcut_pieces, shortcut_saving, rock_distance, crates, len(tests))


def main(maps=None):
    if len(ell.get_pie_worlds(False)) > 0:
        raise RuntimeError('a Play-In-Editor session is running (editor scripting is disabled during play); stop it first')
    results = []
    for path in maps or MAPS:
        results.append('%s: %s' % (path.rsplit('/', 1)[1], build(path)))
    ell.load_level(MAPS[0])
    print('df_build_test_track: OK; ' + '; '.join(results))


main()
