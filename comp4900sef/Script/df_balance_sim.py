"""Editor side of the balance simulation (Phase 6 spec section 3.2). Driven by tools/balance_sim.py through
tools/ue_remote.py; every function prints exactly one JSON line and nothing else.

    exec(open(r'<repo>/comp4900sef/Script/df_balance_sim.py').read()); balance_start('/Game/DeadFire/Maps/L_TestTrack', 1)
    exec(open(r'<repo>/comp4900sef/Script/df_balance_sim.py').read()); balance_sample()
    exec(open(r'<repo>/comp4900sef/Script/df_balance_sim.py').read()); balance_stop()

balance_start writes a save with the requested difficulty into the slot DeadFireBalance and points both race GameModes'
SaveSlotOverride at it on their class defaults for the run, so the real code path (ApplyGameInstanceSettings) applies
the difficulty and the developer's DeadFire.sav is never read for settings or written. Simulate has no player: the
NPCs race, the clock runs down (only a player's gates add time), items are handed out and used. balance_stop ends
the simulation, restores the class defaults and deletes the balance save.
"""
import json
import os

import unreal

ELL = unreal.EditorLevelLibrary
GS = unreal.GameplayStatics
BP = '/Game/DeadFire/Blueprints'
SLOT = 'DeadFireBalance'
GAME_MODES = [BP + '/BP_DFRaceGameMode', BP + '/BP_DFSwitchbackGameMode']


def _cls(path):
    return unreal.load_class(None, '%s.%s_C' % (path, path.rsplit('/', 1)[1]))


def _save_file():
    return os.path.join(unreal.Paths.project_saved_dir(), 'SaveGames', SLOT + '.sav')


def _set_overrides(value):
    for gm in GAME_MODES:
        unreal.get_default_object(_cls(gm)).set_editor_property('SaveSlotOverride', value)


def _out(obj):
    print(json.dumps(obj, separators=(',', ':')))


def balance_start(map_path, difficulty):
    if len(ELL.get_pie_worlds(False)) > 0:
        _out({'error': 'a play session is running; stop it first'})
        return
    if not ELL.load_level(map_path):
        _out({'error': 'could not load %s' % map_path})
        return
    if os.path.exists(_save_file()):
        os.remove(_save_file())
    save = GS.create_save_game_object(_cls(BP + '/BP_DFSaveGame'))
    save.set_editor_property('Difficulty', int(difficulty))
    if not GS.save_game_to_slot(save, SLOT, 0):
        _out({'error': 'could not write the balance save'})
        return
    _set_overrides(SLOT)
    try:
        # a background editor throttles its frame rate, which changes the vehicle physics; run at full speed
        _set_throttle(False)
        track_cm = 0.0
        for actor in ELL.get_all_level_actors():
            if actor.get_actor_label() == 'MainTrack':
                track_cm = actor.get_component_by_class(unreal.SplineComponent).get_spline_length()
        ELL.editor_play_simulate()
    except Exception as e:
        _set_overrides('')  # never leave the GameModes pointed at the balance slot
        _set_throttle(True)
        _out({'error': 'start failed: %s' % str(e)[:200]})
        return
    _out({'started': map_path, 'difficulty': int(difficulty), 'track_cm': round(track_cm, 1)})


def _set_throttle(on):
    """The editor's "use less CPU in the background" preference (the class has no Python names: raw property name)."""
    perf = unreal.get_default_object(unreal.load_class(None, '/Script/UnrealEd.EditorPerformanceSettings'))
    perf.set_editor_property('bThrottleCPUWhenNotForeground', bool(on))


def balance_sample():
    world = ELL.get_game_world()
    if world is None:
        _out({'error': 'no simulation running'})
        return
    gm = GS.get_game_mode(world)
    gs = GS.get_game_state(world)
    gi = GS.get_game_instance(world)
    racer_cls = unreal.load_class(None, '/Game/DeadFire/Components/BPC_DFRacer.BPC_DFRacer_C')
    racers = []
    for ai in GS.get_all_actors_of_class(world, _cls(BP + '/BP_DFVehicleAIController')):
        r = ai.get_component_by_class(racer_cls)
        if r is None:
            continue
        pawn = ai.get_controlled_pawn()
        kph = pawn.get_velocity().length() * 0.036 if pawn else 0.0
        racers.append({'name': str(r.get_editor_property('RacerName')), 'laps': r.get_editor_property('LapsCompleted'),
                       'score': r.get_editor_property('Score'), 'kills': r.get_editor_property('Kills'),
                       'deaths': r.get_editor_property('Deaths'), 'rank': r.get_editor_property('Rank'),
                       'dist': round(r.get_editor_property('DistanceAlongTrack'), 1), 'kph': round(kph, 1)})
    _out({'t': round(GS.get_time_seconds(world), 2), 'remaining': round(gs.get_editor_property('RemainingTime'), 2),
          'active': bool(gs.get_editor_property('bRaceActive')), 'slot': str(gi.get_editor_property('SaveSlotName')),
          'limit': gm.get_editor_property('RaceTimeLimit'), 'bonus': gm.get_editor_property('CheckpointTimeBonus'),
          'gates': len(gm.get_editor_property('Checkpoints')), 'npc_scale': gm.get_editor_property('NPCSpeedScale'),
          'item_interval': gm.get_editor_property('AIItemInterval'), 'racers': racers})


def balance_stop():
    if len(ELL.get_pie_worlds(False)) > 0:
        ELL.editor_end_play()
    _set_overrides('')
    _set_throttle(True)  # the editor default
    if os.path.exists(_save_file()):
        os.remove(_save_file())
    left = [str(unreal.get_default_object(_cls(gm)).get_editor_property('SaveSlotOverride')) for gm in GAME_MODES]
    _out({'stopped': True, 'overrides': left})
