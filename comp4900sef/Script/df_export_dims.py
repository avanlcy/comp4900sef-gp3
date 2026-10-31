"""Measures the template vehicle for the Dead Fire art generators (Phase 7, spec 4.1 and 6.1), inside the editor:

    exec(open(r'<repo>/comp4900sef/Script/df_export_dims.py').read()); export_dims(r'<repo>/tools/artgen/data/dims.json')

Spawns BP_DFVehicle in the open editor level (destroyed afterwards; the level is never saved) and writes, in Unreal
actor space and centimetres (X forward, Y right, Z up):
- wheels: {bone: [x, y, z]} - each wheel bone of the movement's wheel setups, in the reference pose.
- wheel_rot: {bone: [pitch, yaw, roll]} - the same bones' rotations (a wheel mesh on a bone socket inherits them).
- wheel_offset: {bone: [x, y, z]} - the wheel setups' AdditionalOffset (where the physics wheel sits from the bone).
- wheel_radius, wheel_width: ShapeRadius and ShapeWidth of the Sedan_FrontWheel / Sedan_BackWheel class defaults (they
  must agree), plus suspension_max_raise / suspension_max_drop and steer_angle (the largest of the two classes).
- body_box: {min, max} - the combined bounds of the physics asset's chassis bodies (every body except the wheel bones'
  spheres) in the reference pose.
- ramp, bump_wedge, pole: {min, max} local bounds of the VehicleAdv RampLarge, BumpWedge and pole meshes (Task 20).
- mannequin_sockets: {head, spine_03, hand_r: bool} - whether SK_Mannequin has each bone or socket (Task 14).
It also exports those three VehicleAdv meshes as FBX to <repo>/art/reference/ for the Task 20 side-by-side review.
Prints `DIMS OK: <path>` (or DIMS FAILED and the reason).
"""
import json
import os

import unreal

VEHICLE = '/Game/DeadFire/Blueprints/BP_DFVehicle.BP_DFVehicle_C'
WHEEL_CLASSES = ('/Game/VehicleBP/Sedan/Sedan_FrontWheel.Sedan_FrontWheel_C', '/Game/VehicleBP/Sedan/Sedan_BackWheel.Sedan_BackWheel_C')
REFERENCE_MESHES = {'ramp': '/Game/VehicleAdv/ArenaMesh/RampLarge', 'bump_wedge': '/Game/VehicleAdv/ArenaMesh/BumpWedge',
                    'pole': '/Game/VehicleAdv/ArenaMesh/pole'}
MANNEQUIN = '/Game/Mannequin/Character/Mesh/SK_Mannequin'
MANNEQUIN_SOCKETS = ('head', 'spine_03', 'hand_r')


def _v(vec):
    return [round(vec.x, 3), round(vec.y, 3), round(vec.z, 3)]


def _xf(location, rotation):
    return unreal.Transform(location=location, rotation=rotation, scale=unreal.Vector(1, 1, 1))


def _corners(half):
    hx, hy, hz = half
    return [unreal.Vector(sx * hx, sy * hy, sz * hz) for sx in (-1, 1) for sy in (-1, 1) for sz in (-1, 1)]


def _element_points(agg):
    """(element transform, local corner points) for every box, capsule and sphere of a body; convex hulls are refused."""
    if len(agg.get_editor_property('convex_elems')) > 0:
        raise RuntimeError('a chassis body has convex hulls; their vertices are not readable from Python')
    out = []
    for b in agg.get_editor_property('box_elems'):
        half = (b.get_editor_property('x') / 2, b.get_editor_property('y') / 2, b.get_editor_property('z') / 2)
        out.append((_xf(b.get_editor_property('center'), b.get_editor_property('rotation')), _corners(half)))
    for s in agg.get_editor_property('sphyl_elems'):
        r, ln = s.get_editor_property('radius'), s.get_editor_property('length')
        out.append((_xf(s.get_editor_property('center'), s.get_editor_property('rotation')), _corners((r, r, ln / 2 + r))))
    for s in agg.get_editor_property('sphere_elems'):
        r = s.get_editor_property('radius')
        out.append((_xf(s.get_editor_property('center'), unreal.Rotator(0, 0, 0)), _corners((r, r, r))))
    return out


def _body_box(mesh_comp, physics_asset, wheel_bones):
    lo, hi = [1e9] * 3, [-1e9] * 3
    found = 0
    for body in unreal.ObjectIterator(unreal.BodySetup):
        if body.get_outer() != physics_asset or str(body.get_editor_property('bone_name')) in wheel_bones:
            continue
        found += 1
        bone_xf = mesh_comp.get_socket_transform(body.get_editor_property('bone_name'), unreal.RelativeTransformSpace.RTS_ACTOR)
        for elem_xf, pts in _element_points(body.get_editor_property('agg_geom')):
            for p in pts:
                a = unreal.MathLibrary.transform_location(bone_xf, unreal.MathLibrary.transform_location(elem_xf, p))
                for i, c in enumerate((a.x, a.y, a.z)):
                    lo[i], hi[i] = min(lo[i], c), max(hi[i], c)
    if not found:
        raise RuntimeError('no chassis bodies in %s' % physics_asset.get_path_name())
    return {'min': [round(c, 3) for c in lo], 'max': [round(c, 3) for c in hi]}


def _wheel_shape():
    shapes = []
    for path in WHEEL_CLASSES:
        d = unreal.get_default_object(unreal.load_class(None, path))
        shapes.append({k: d.get_editor_property(k) for k in ('shape_radius', 'shape_width', 'suspension_max_raise',
                                                              'suspension_max_drop', 'steer_angle')})
    for k in ('shape_radius', 'shape_width'):
        if abs(shapes[0][k] - shapes[1][k]) > 0.01:
            raise RuntimeError('front and back wheel %s differ: %s' % (k, [s[k] for s in shapes]))
    return {'wheel_radius': round(shapes[0]['shape_radius'], 3), 'wheel_width': round(shapes[0]['shape_width'], 3),
            'suspension_max_raise': round(max(s['suspension_max_raise'] for s in shapes), 3),
            'suspension_max_drop': round(max(s['suspension_max_drop'] for s in shapes), 3),
            'steer_angle': round(max(s['steer_angle'] for s in shapes), 3)}


def _reference_meshes(ref_dir):
    out = {}
    os.makedirs(ref_dir, exist_ok=True)
    for key, path in REFERENCE_MESHES.items():
        mesh = unreal.load_asset(path)
        if mesh is None:
            raise RuntimeError('missing %s' % path)
        box = mesh.get_bounding_box()
        out[key] = {'min': _v(box.min), 'max': _v(box.max)}
        task = unreal.AssetExportTask()
        task.set_editor_property('object', mesh)
        task.set_editor_property('filename', os.path.join(ref_dir, path.rsplit('/', 1)[1] + '.fbx'))
        task.set_editor_property('exporter', unreal.StaticMeshExporterFBX())
        task.set_editor_property('automated', True)
        task.set_editor_property('prompt', False)
        task.set_editor_property('replace_identical', True)
        task.set_editor_property('selected', False)
        task.set_editor_property('options', unreal.FbxExportOption())  # without options 4.27 reports success and writes nothing
        fbx = task.get_editor_property('filename')
        if os.path.isfile(fbx):
            os.remove(fbx)
        if not unreal.Exporter.run_asset_export_task(task) or not os.path.isfile(fbx):
            raise RuntimeError('FBX export of %s failed' % path)
    return out


def _mannequin_sockets():
    sk = unreal.load_asset(MANNEQUIN)
    comp = unreal.new_object(unreal.SkeletalMeshComponent)
    comp.set_skeletal_mesh(sk)
    return {n: bool(comp.get_bone_index(n) != -1 or sk.find_socket(n) is not None) for n in MANNEQUIN_SOCKETS}


def _measure_vehicle():
    world = unreal.EditorLevelLibrary.get_editor_world()
    cls = unreal.load_class(None, VEHICLE)
    actor = unreal.EditorLevelLibrary.spawn_actor_from_class(cls, unreal.Vector(0, 0, 50000), unreal.Rotator(0, 0, 0))
    if actor is None:
        raise RuntimeError('could not spawn %s in %s' % (VEHICLE, world.get_name()))
    try:
        mesh = actor.get_editor_property('mesh')
        setups = actor.get_editor_property('vehicle_movement').get_editor_property('wheel_setups')
        wheels, rots, offsets = {}, {}, {}
        for ws in setups:
            bone = str(ws.get_editor_property('bone_name'))
            xf = mesh.get_socket_transform(bone, unreal.RelativeTransformSpace.RTS_ACTOR)
            wheels[bone] = _v(xf.translation)
            r = xf.rotation.rotator()
            rots[bone] = [round(r.pitch, 3), round(r.yaw, 3), round(r.roll, 3)]
            offsets[bone] = _v(ws.get_editor_property('additional_offset'))
        pa = mesh.get_editor_property('skeletal_mesh').get_editor_property('physics_asset')
        box = _body_box(mesh, pa, set(wheels))
        return {'wheels': wheels, 'wheel_rot': rots, 'wheel_offset': offsets, 'body_box': box,
                'source': {'vehicle': VEHICLE, 'skeletal_mesh': mesh.get_editor_property('skeletal_mesh').get_path_name(),
                           'physics_asset': pa.get_path_name(), 'level': world.get_name()}}
    finally:
        unreal.EditorLevelLibrary.destroy_actor(actor)


def export_dims(out_path):
    try:
        if len(unreal.EditorLevelLibrary.get_pie_worlds(False)) > 0:
            raise RuntimeError('Play-In-Editor is running; end it first (EditorLevelLibrary.editor_end_play)')
        repo = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(out_path)))))
        dims = _measure_vehicle()
        dims.update(_wheel_shape())
        dims.update(_reference_meshes(os.path.join(repo, 'art', 'reference')))
        dims['mannequin_sockets'] = _mannequin_sockets()
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        with open(out_path, 'w', encoding='utf-8', newline='\n') as f:
            json.dump(dims, f, indent=1, sort_keys=True)
            f.write('\n')
    except Exception as e:  # one short line back through remote execution
        print('DIMS FAILED: %s' % e)
        return False
    print('DIMS OK: %s' % out_path)
    return True
