"""Editor side of the balance time-step keeper (Phase 7 Task 23). Driven by tools/balance_timestep.py through
tools/ue_remote.py; every function prints exactly one JSON line.

    exec(open(r'<repo>/comp4900sef/Script/df_balance_timestep.py').read()); timestep_on(1/60.0)
    exec(open(r'<repo>/comp4900sef/Script/df_balance_timestep.py').read()); timestep_stats()
    exec(open(r'<repo>/comp4900sef/Script/df_balance_timestep.py').read()); timestep_off()

Why: the project substeps physics at 1/60 s with at most 6 substeps, so a frame advances physics by at most 0.1 s. Below
about 10 fps physics falls behind the game clock that tools/balance_sim.py measures lap times in, and the lap time comes
out too long (a 4 fps Simulate gave rivals moving at about half their speedometer speed). A busy machine can drop the
editor that low.

What: while on, a Slate post-tick callback sets the play world's global time dilation to target_dt / (the last real frame
time), clamped to [0.01, 1], so each frame advances about target_dt of game time. Physics stays within its substep
budget and the AI ticks at 1/target_dt Hz of game time; physics, timers and the race clock all run in game time, so a slow
editor only stretches the wall-clock time of a run. At 60 fps or more (target 1/60 s) the dilation stays 1: no effect.
With no play world (the editor between runs) the callback does nothing.

The callback holds no engine reference between ticks (the World is looked up and dropped in each call), so it is safe
across level loads; its state (_DF_TS: the callback handle and plain numbers) survives re-exec of this file.
"""
import json

import unreal

_TS = globals().setdefault('_DF_TS', {'handle': None})


def _tick(real_dt):
    try:
        w = unreal.EditorLevelLibrary.get_game_world()
        if w is None:
            return
        game_dt = unreal.GameplayStatics.get_world_delta_seconds(w)
        if real_dt > 0:
            d = min(1.0, max(0.01, _TS['target'] / real_dt))
            unreal.GameplayStatics.set_global_time_dilation(w, d)
            _TS['n'] += 1
            _TS['real'] += real_dt
            _TS['game'] += game_dt
            _TS['max_game_dt'] = max(_TS['max_game_dt'], game_dt)
            _TS['over_2step'] += game_dt > 2.0 / 60.0 + 1e-4
            _TS['over_budget'] += game_dt > 0.1 + 1e-4
        del w
    except Exception as e:  # never let the callback throw every tick
        _TS['errors'] += 1
        _TS['last_error'] = str(e)[:200]


def timestep_on(target_dt=1.0 / 60.0):
    if _TS.get('handle') is not None:
        unreal.unregister_slate_post_tick_callback(_TS['handle'])
    _TS.update(target=float(target_dt), n=0, real=0.0, game=0.0, max_game_dt=0.0, over_2step=0, over_budget=0, errors=0, last_error='')
    _TS['handle'] = unreal.register_slate_post_tick_callback(_tick)
    print(json.dumps({'timestep_on': target_dt}))


def timestep_stats():
    n = max(1, _TS.get('n', 0))
    print(json.dumps({'on': _TS.get('handle') is not None, 'frames': _TS.get('n', 0), 'real_s': round(_TS.get('real', 0), 1),
                      'game_s': round(_TS.get('game', 0), 1), 'fps': round(_TS.get('n', 0) / max(1e-6, _TS.get('real', 0)), 1),
                      'mean_game_dt': round(_TS.get('game', 0) / n, 4), 'max_game_dt': round(_TS.get('max_game_dt', 0), 4),
                      'frames_over_2_substeps': _TS.get('over_2step', 0), 'frames_over_physics_budget': _TS.get('over_budget', 0),
                      'errors': _TS.get('errors', 0), 'last_error': _TS.get('last_error', '')}))


def timestep_off():
    if _TS.get('handle') is not None:
        unreal.unregister_slate_post_tick_callback(_TS['handle'])
        _TS['handle'] = None
    w = unreal.EditorLevelLibrary.get_game_world()
    if w is not None:
        unreal.GameplayStatics.set_global_time_dilation(w, 1.0)
    del w
    timestep_stats()
