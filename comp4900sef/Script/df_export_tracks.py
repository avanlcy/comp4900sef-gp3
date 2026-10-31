"""Exports the shipped tracks' layouts for the Dead Fire terrain generator (Phase 7, spec 8.1 and 8.3), inside the editor:

    exec(open(r'<repo>/comp4900sef/Script/df_export_tracks.py').read()); export_tracks(r'<repo>/tools/artgen/data/tracks')

Opens L_TestTrack and L_Switchback in turn (a map that is already open is read as it is), never saves either, and opens
the level that was open before again at the end. Writes <out_dir>/<MapName>.json in world space, centimetres:
- roads: [[x, y, z], ...] per BP_DFTrackSpline (the main loop first, then the others by label), sampled every 200 cm
  along the spline from distance 0; an open spline also gets its end point, a closed one stops short of its start.
- crates: [[x, y]] of every BP_DFLootBox.
- gates: [[x, y]] of every BP_DFCheckpoint, in CheckpointIndex order.
- props: [[x, y]] the bounds centres of what the terrain pads flatten (spec 8.1 "pads ... around gates and props"):
  every StaticMeshActor except the Ground cube (today the ramp, the bump wedge and the four poles; the ramp's pivot is a
  corner of the mesh, hence the bounds centre) and every BP_DFDestructible (the shortcut's rock).
- target_car: [x, y] of the parked BP_DFVehicle labelled TargetCar.
- start: [x, y, yaw] of the PlayerStart: the GameMode spawns the player there, on the start line with gate 0 (the NPC
  grid is laid behind that line).
Prints one line per map, then `TRACKS OK: 2 maps` (or TRACKS FAILED and the reason).
"""
import gc
import json
import os
import re

import unreal

MAPS = ['/Game/DeadFire/Maps/L_TestTrack', '/Game/DeadFire/Maps/L_Switchback']
BP_DIR = '/Game/DeadFire/Blueprints'
SAMPLE_CM = 200.0
GROUND_LABEL = 'Ground'      # the builder's flat ground cube (no longer spawned in shipped maps after Task 22)
TARGET_CAR_LABEL = 'TargetCar'

ell = unreal.EditorLevelLibrary
WORLD = unreal.SplineCoordinateSpace.WORLD


def _bp(name):
    cls = unreal.load_class(None, '%s/%s.%s_C' % (BP_DIR, name, name))
    if cls is None:
        raise RuntimeError('missing class %s' % name)
    return cls


def _actors(world, cls):
    return sorted(unreal.GameplayStatics.get_all_actors_of_class(world, cls), key=lambda a: a.get_actor_label())


def _xy(v):
    return [round(v.x, 1), round(v.y, 1)]


def _road(track):
    spline = track.get_component_by_class(unreal.SplineComponent)
    length = spline.get_spline_length()
    if length < SAMPLE_CM:
        raise RuntimeError('%s: spline only %.0f cm long' % (track.get_actor_label(), length))
    distances = [SAMPLE_CM * k for k in range(int(length // SAMPLE_CM) + 1)]
    if spline.is_closed_loop():
        if length - distances[-1] < 1.0:
            distances.pop()  # the start again
    elif length - distances[-1] >= 1.0:
        distances.append(length)
    pts = []
    for d in distances:
        p = spline.get_location_at_distance_along_spline(d, WORLD)
        pts.append([round(p.x, 1), round(p.y, 1), round(p.z, 1)])
    return pts


def _one(world, cls, what, label=None):
    found = _actors(world, cls)
    if label and len(found) > 1:
        found = [a for a in found if a.get_actor_label() == label]
    if len(found) != 1:
        raise RuntimeError('%s: %d %s actor(s), want 1' % (world.get_name(), len(found), what))
    return found[0]


def _export(world):
    tracks = _actors(world, _bp('BP_DFTrackSpline'))
    tracks.sort(key=lambda t: (not t.get_editor_property('bIsMainTrack'), t.get_actor_label()))
    if not tracks or not tracks[0].get_editor_property('bIsMainTrack'):
        raise RuntimeError('%s: no main BP_DFTrackSpline' % world.get_name())
    gates = sorted(_actors(world, _bp('BP_DFCheckpoint')), key=lambda g: g.get_editor_property('CheckpointIndex'))
    props = [a for a in _actors(world, unreal.StaticMeshActor) if a.get_actor_label() != GROUND_LABEL]
    props += _actors(world, _bp('BP_DFDestructible'))
    car = _one(world, _bp('BP_DFVehicle'), 'BP_DFVehicle', TARGET_CAR_LABEL)
    start = _one(world, unreal.PlayerStart, 'PlayerStart')
    data = {
        'roads': [_road(t) for t in tracks],
        'crates': [_xy(c.get_actor_location()) for c in _actors(world, _bp('BP_DFLootBox'))],
        'gates': [_xy(g.get_actor_location()) for g in gates],
        'props': [_xy(p.get_actor_bounds(False)[0]) for p in props],
        'target_car': _xy(car.get_actor_location()),
        'start': _xy(start.get_actor_location()) + [round(start.get_actor_rotation().yaw, 2)],
    }
    if not data['crates'] or not data['gates']:
        raise RuntimeError('%s: %d crates, %d gates' % (world.get_name(), len(data['crates']), len(data['gates'])))
    summary = '%s: roads %s samples, %d crates, %d gates, %d props (%s)' % (
        world.get_name(), '+'.join(str(len(r)) for r in data['roads']), len(data['crates']), len(data['gates']),
        len(props), ', '.join(sorted(set(p.get_actor_label() for p in props))))
    return data, summary


def _dumps(data):
    """Indented JSON with every innermost list of numbers on one line (one road sample per line)."""
    text = json.dumps(data, indent=1)
    return re.sub(r'\[\s*(-?[\d.]+(?:,\s*-?[\d.]+)*)\s*\]', lambda m: '[' + ', '.join(m.group(1).replace(',', ' ').split()) + ']', text)


def _open_package():
    return ell.get_editor_world().get_path_name().split('.', 1)[0]


def _load(path):
    """Loads a level. No Python wrapper of the old world or its actors may be alive here: the editor aborts the load
    ("Old level package ... not cleaned up by garbage collection", a fatal World Memory Leaks error) when Python still
    references them. So each map is read inside its own function frame, and leftover cycles are collected first."""
    gc.collect()
    if not ell.load_level(path):
        raise RuntimeError('could not open %s' % path)


def _export_map(path, out_dir):
    """Opens path (unless it is the open level), writes <out_dir>/<MapName>.json; returns the summary line. Holds no
    UObject once it returns."""
    if _open_package() != path:
        _load(path)
    world = ell.get_editor_world()
    if world.get_path_name().split('.', 1)[0] != path:
        raise RuntimeError('opened %s, the editor world is %s' % (path, world.get_path_name()))
    data, summary = _export(world)
    with open(os.path.join(out_dir, path.rsplit('/', 1)[1] + '.json'), 'w', encoding='utf-8', newline='\n') as f:
        f.write(_dumps(data) + '\n')
    return summary


def export_tracks(out_dir):
    previous, lines, error = None, [], None
    try:
        if len(ell.get_pie_worlds(False)) > 0:
            raise RuntimeError('Play-In-Editor is running; end it first (EditorLevelLibrary.editor_end_play)')
        previous = _open_package()
        os.makedirs(out_dir, exist_ok=True)
        for path in MAPS:
            lines.append(_export_map(path, out_dir))
    except Exception as e:  # one short line back through remote execution
        error = str(e)  # only the text: the traceback's frames would keep the open world alive through the reload below
    try:  # never saved: the level open before (and anything dirty in it) is back as the editor had it
        if previous and previous.startswith('/Game/') and _open_package() != previous:
            _load(previous)
    except Exception as e:
        error = error or str(e)
    if error:
        print('TRACKS FAILED: %s' % error)
        return False
    for line in lines:
        print(line)
    print('TRACKS OK: %d maps' % len(lines))
    return True
