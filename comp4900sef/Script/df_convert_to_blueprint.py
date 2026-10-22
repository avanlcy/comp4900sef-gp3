"""Task 1 check (run inside the editor): the Blueprint-only project loads the template Blueprints and their content.

    exec(open(r'<repo>/comp4900sef/Script/df_convert_to_blueprint.py').read())
"""
import unreal

REQUIRED = [
    '/Game/VehicleBP/Sedan/Sedan',
    '/Game/VehicleBP/Sedan/Sedan_FrontWheel',
    '/Game/VehicleBP/Sedan/Sedan_BackWheel',
    '/Game/ThirdPersonBP/Blueprints/ThirdPersonCharacter',
    '/Game/Vehicle/Sedan/Sedan_SkelMesh',
    '/Game/Vehicle/Sedan/Sedan_AnimBP',
    '/Game/Mannequin/Character/Mesh/SK_Mannequin',
    '/Game/Mannequin/Animations/ThirdPerson_AnimBP',
]

ok = True
for path in REQUIRED:
    exists = unreal.EditorAssetLibrary.does_asset_exist(path)
    print('%s %s' % ('OK ' if exists else 'MISSING', path))
    ok = ok and exists

for bp_path in ('/Game/VehicleBP/Sedan/Sedan', '/Game/ThirdPersonBP/Blueprints/ThirdPersonCharacter'):
    bp = unreal.load_asset(bp_path)
    cls = unreal.load_class(None, '%s.%s_C' % (bp_path, bp_path.rsplit('/', 1)[1])) if bp else None
    print('%s -> %s' % (bp_path, cls.get_name() if cls else 'FAILED TO LOAD'))
    ok = ok and cls is not None

print('CONVERT CHECK %s' % ('PASSED' if ok else 'FAILED'))
