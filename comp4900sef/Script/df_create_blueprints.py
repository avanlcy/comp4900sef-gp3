"""Creates the Dead Fire Blueprint children of the C++ classes.

Run inside the Unreal Editor (Python console, or through the MCP server's
manage_editor.run_python). Safe to run again: existing assets are reused.

    exec(open(r'E:/VSC projects/comp4900sef-gp3/comp4900sef/Script/df_create_blueprints.py').read())
"""
import unreal

BP_DIR = '/Game/DeadFire/Blueprints'

# (asset name, C++ parent class path)
SPECS = [
    ('BP_DFVehicle', '/Script/comp4900sef.DFVehiclePawn'),
    ('BP_DFCharacter', '/Script/comp4900sef.DFCharacter'),
    ('BP_DFPlayerController', '/Script/comp4900sef.DFPlayerController'),
    ('BP_DFHUD', '/Script/comp4900sef.DFHUD'),
    ('BP_DFTrackSpline', '/Script/comp4900sef.DFTrackSpline'),
    ('BP_DFRaceGameMode', '/Script/comp4900sef.DFRaceGameMode'),
]


def create_blueprint(name, parent_path):
    asset_path = '{}/{}'.format(BP_DIR, name)
    if unreal.EditorAssetLibrary.does_asset_exist(asset_path):
        unreal.log('exists: {}'.format(asset_path))
        return unreal.EditorAssetLibrary.load_asset(asset_path)

    parent = unreal.load_class(None, parent_path)
    if parent is None:
        raise RuntimeError('parent class not found: {}'.format(parent_path))

    factory = unreal.BlueprintFactory()
    factory.set_editor_property('parent_class', parent)
    tools = unreal.AssetToolsHelpers.get_asset_tools()
    bp = tools.create_asset(name, BP_DIR, unreal.Blueprint, factory)
    if bp is None:
        raise RuntimeError('could not create {}'.format(asset_path))
    unreal.log('created: {}'.format(asset_path))
    return bp


def generated_class(name):
    """The compiled _C class of a Blueprint (UE 4.27 Python does not expose Blueprint.generated_class)."""
    cls = unreal.EditorAssetLibrary.load_blueprint_class('{}/{}'.format(BP_DIR, name))
    if cls is None:
        raise RuntimeError('generated class not found for {}'.format(name))
    return cls


def main():
    if not unreal.EditorAssetLibrary.does_directory_exist(BP_DIR):
        unreal.EditorAssetLibrary.make_directory(BP_DIR)

    bps = {name: create_blueprint(name, parent) for name, parent in SPECS}

    # Wire the GameMode to the Blueprint children so visual/tuning swaps never need C++.
    gm_cdo = unreal.get_default_object(generated_class('BP_DFRaceGameMode'))
    gm_cdo.set_editor_property('default_pawn_class', generated_class('BP_DFVehicle'))
    gm_cdo.set_editor_property('on_foot_character_class', generated_class('BP_DFCharacter'))
    gm_cdo.set_editor_property('player_controller_class', generated_class('BP_DFPlayerController'))
    gm_cdo.set_editor_property('hud_class', generated_class('BP_DFHUD'))

    # A Python property change does not dirty the package, so force the save.
    gm_cdo.modify(True)
    bps['BP_DFRaceGameMode'].modify(True)
    for name, bp in bps.items():
        unreal.EditorAssetLibrary.save_loaded_asset(bp, False)
        unreal.log('saved: {}/{}'.format(BP_DIR, name))

    # Report what the GameMode now points at.
    for prop in ('default_pawn_class', 'on_foot_character_class', 'player_controller_class', 'hud_class'):
        unreal.log('BP_DFRaceGameMode.{} = {}'.format(prop, gm_cdo.get_editor_property(prop)))
    print('df_create_blueprints: OK')


main()
