"""Builds the Phase 1 test level L_TestTrack: ground, lights, a looped road, a few
infield props and the player start. Run inside the Unreal Editor after
df_create_blueprints.py. Re-running recreates the level from scratch.

    exec(open(r'E:/VSC projects/comp4900sef-gp3/comp4900sef/Script/df_build_test_track.py').read())
"""
import math
import unreal

MAP_PATH = '/Game/DeadFire/Maps/L_TestTrack'
BP_DIR = '/Game/DeadFire/Blueprints'

# Kidney-shaped loop, world units (cm), about 400 m around. Road top surface is Z 0.
TRACK_POINTS = [
    (0, 0), (6000, -600), (11500, 1200), (14000, 5500), (12000, 9500),
    (7000, 9000), (3000, 11500), (-2500, 9000), (-4000, 4500), (-2500, 1200),
]

# (mesh path, location, yaw) props dropped in the infield so leaving the road has a purpose.
PROPS = [
    ('/Game/VehicleAdv/ArenaMesh/RampLarge', (6000, 4500, 0), 90),
    ('/Game/VehicleAdv/ArenaMesh/pole', (4000, 3000, 0), 0),
    ('/Game/VehicleAdv/ArenaMesh/pole', (8000, 3000, 0), 0),
    ('/Game/VehicleAdv/ArenaMesh/pole', (4000, 6500, 0), 0),
    ('/Game/VehicleAdv/ArenaMesh/pole', (8000, 6500, 0), 0),
    ('/Game/VehicleAdv/ArenaMesh/BumpWedge', (3000, 5000, 0), 45),
]

ell = unreal.EditorLevelLibrary
eal = unreal.EditorAssetLibrary


def vec(x, y, z=0.0):
    return unreal.Vector(float(x), float(y), float(z))


def rot(pitch=0.0, yaw=0.0, roll=0.0):
    return unreal.Rotator(roll=float(roll), pitch=float(pitch), yaw=float(yaw))


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


def main():
    if not ell.new_level(MAP_PATH):
        raise RuntimeError('could not create level {}'.format(MAP_PATH))

    # Ground: a 500 m square slab whose top is 10 cm below the road surface.
    spawn_static_mesh('/Engine/BasicShapes/Cube', vec(5000, 5000, -60), scale=(500, 500, 1),
                      label='Ground', material_path='/Game/VehicleAdv/Materials/MaterialInstances/LandscapeNoHole')

    # Lighting.
    spawn(unreal.DirectionalLight, vec(0, 0, 2000), rot(pitch=-45, yaw=30), label='Sun')
    spawn(unreal.SkyLight, vec(0, 0, 2000), label='SkyLight')
    spawn(unreal.SkyAtmosphere, vec(0, 0, 0), label='SkyAtmosphere')
    fog = spawn(unreal.ExponentialHeightFog, vec(0, 0, 0), label='HeightFog')
    fog_comp = fog.get_component_by_class(unreal.ExponentialHeightFogComponent)
    fog_comp.set_editor_property('fog_density', 0.004)
    fog_comp.set_editor_property('start_distance', 3000.0)

    # Track.
    track_class = eal.load_blueprint_class('{}/BP_DFTrackSpline'.format(BP_DIR))
    track = spawn(track_class, vec(0, 0, 0), label='MainTrack')
    track.set_points_from_array([vec(x, y, 0) for x, y in TRACK_POINTS], True)

    # Infield props.
    for mesh_path, (x, y, z), yaw in PROPS:
        spawn_static_mesh(mesh_path, vec(x, y, z), rot(yaw=yaw), label=mesh_path.rsplit('/', 1)[-1])

    # Player start on the start line, facing along the track.
    (x0, y0), (x1, y1) = TRACK_POINTS[0], TRACK_POINTS[1]
    yaw = math.degrees(math.atan2(y1 - y0, x1 - x0))
    spawn(unreal.PlayerStart, vec(x0, y0, 30), rot(yaw=yaw), label='PlayerStart')

    # Game mode for this level.
    gm_class = eal.load_blueprint_class('{}/BP_DFRaceGameMode'.format(BP_DIR))
    world = ell.get_editor_world()
    settings = world.get_world_settings() if hasattr(world, 'get_world_settings') else None
    if settings is None:
        for actor in ell.get_all_level_actors():
            if isinstance(actor, unreal.WorldSettings):
                settings = actor
                break
    if settings is None:
        raise RuntimeError('world settings not found')
    settings.set_editor_property('default_game_mode', gm_class)

    if not ell.save_current_level():
        raise RuntimeError('could not save {}'.format(MAP_PATH))

    unreal.log('track length (cm): {}'.format(track.get_track_length()))
    unreal.log('track pieces: {}'.format(track.get_generated_mesh_count()))
    print('df_build_test_track: OK')


main()
