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

    (x0, y0), (x1, y1) = TRACK_POINTS[0], TRACK_POINTS[1]
    yaw = math.degrees(math.atan2(y1 - y0, x1 - x0))
    spawn(unreal.PlayerStart, vec(x0, y0, 30), rot(yaw=yaw), label='PlayerStart')

    world_settings().set_editor_property('default_game_mode', bp_class(BP_DIR + '/BP_DFRaceGameMode'))

    tests = []
    if path == TEST_MAP:
        for i, (name, cls) in enumerate(functional_test_classes()):
            x, y, z = TEST_ORIGIN
            spawn(cls, vec(x + (i % TESTS_PER_ROW) * TEST_SPACING, y - (i // TESTS_PER_ROW) * TEST_SPACING, z), label=name)
            tests.append(name)

    if not ell.save_current_level():
        raise RuntimeError('could not save {}'.format(path))
    return 'track %.0f cm, %d pieces, %d gates, %d tests' % (length, pieces, CHECKPOINT_COUNT, len(tests))


def main(maps=None):
    if len(ell.get_pie_worlds(False)) > 0:
        raise RuntimeError('a Play-In-Editor session is running (editor scripting is disabled during play); stop it first')
    results = []
    for path in maps or MAPS:
        results.append('%s: %s' % (path.rsplit('/', 1)[1], build(path)))
    ell.load_level(MAPS[0])
    print('df_build_test_track: OK; ' + '; '.join(results))


main()
