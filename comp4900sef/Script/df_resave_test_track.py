"""Loads L_TestTrack, regenerates every track's road pieces and saves the level.

Needed after changing ADFTrackSpline so the saved map carries the current road
geometry (Play-In-Editor and packaged builds use the saved pieces). Runs inside the
editor, or headless:

    UE4Editor-Cmd.exe <project.uproject> -ExecutePythonScript="<repo>/comp4900sef/Script/df_resave_test_track.py"
"""
import unreal

MAP_PATH = '/Game/DeadFire/Maps/L_TestTrack'

ell = unreal.EditorLevelLibrary
world = ell.get_editor_world()
if world is None or world.get_name() != 'L_TestTrack':
    if not ell.load_level(MAP_PATH):
        raise RuntimeError('could not load {}'.format(MAP_PATH))
    world = ell.get_editor_world()

tracks = [a for a in ell.get_all_level_actors() if a.get_class().get_name().startswith('BP_DFTrackSpline')]
for track in tracks:
    track.rebuild_track()
    track.modify(True)
    unreal.log('{}: {} pieces, {:.0f} cm'.format(track.get_actor_label(), track.get_generated_mesh_count(), track.get_track_length()))

if not ell.save_current_level():
    raise RuntimeError('could not save {}'.format(MAP_PATH))
print('df_resave_test_track: OK ({} tracks)'.format(len(tracks)))
