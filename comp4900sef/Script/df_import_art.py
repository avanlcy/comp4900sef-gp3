"""Imports (and reimports) the generated Dead Fire art into /Game/DeadFire/Art (Phase 7, spec 4.1), inside the editor:

    exec(open(r'<repo>/comp4900sef/Script/df_import_art.py').read()); import_all(r'<repo>/art'[, only=['T_DF_Rock', ...]])

Reads art/catalog.json and imports every built entry (its recipe or script is not "todo") with AssetImportTask
(replace_existing, automated), then applies the catalogue's settings and saves:
- Textures: compression and sRGB as catalogued (_N TC_NORMALMAP, _ORM TC_MASKS with sRGB off, BC sRGB on), LOD group.
  A PNG must be 8 bits per channel (tools/artgen/polyhaven.py converts Poly Haven's 16-bit maps); a deeper one fails.
- Images: UI images (icons, logo, crosshair, vignette) TC_DEFAULT, sRGB on, TEXTUREGROUP_UI; terrain splats sRGB off.
- Meshes (FBX from tools/artgen/build_meshes.py): no materials or textures from the file, no lightmap UVs, collision
  auto-generated only for the catalogue's "box" (a "ucx" mesh brings its UCX_ hulls, "none" has no simple collision),
  normals as exported; each material slot gets its catalogue MI_DF_* by name (falling back to slot order). A slot
  whose instance does not exist yet is left for build_materials, which assigns it once the instance is made.
`only` limits the run to the named catalogue entries (a texture set name such as T_DF_Rock covers its maps).
- Sounds (16-bit mono WAV from tools/artgen/sfx.py): `looping` as catalogued, sound class /Engine/EngineSounds/Master, and
  every non-UI sound gets the attenuation SA_DF_World, which is created when missing (natural-sound falloff, spherical,
  inner radius 400 cm, falloff distance 6000 cm). A sound that is unchanged keeps its settings; a changed WAV is replaced.
- Fonts (Task 18; build_all --kind fonts copies the .ttf into art/fonts): the .ttf becomes the FontFace (catalogue `face`), and
  the Font (catalogue `name`, made with FontFactory when missing) gets it as its default typeface "Default" through the
  plugin's SetFontFace (Runtime cache type), as the editor's own font import does. A reimport replaces the face in place.
Prints `ART IMPORT OK: N assets` (or ART IMPORT FAILED and the reasons).
"""
import json
import os
import re

import unreal

eal = unreal.EditorAssetLibrary


def _wanted(only, *names):
    return not only or any(n in only for n in names)


def _built(entry):
    if entry.get('source', 'gen') != 'gen':
        return True
    return entry.get('recipe', entry.get('script')) != 'todo'


def png_bit_depth(path):
    """Bits per channel from a PNG's header, or None for another file type. A 16-bit PNG imports as linear RGBA16, and
    the sRGB flag set below would then encode it to sRGB a second time (colour maps 2.5-3x too bright)."""
    with open(path, 'rb') as f:
        head = f.read(26)
    return head[24] if head[1:4] == b'PNG' and len(head) > 24 else None


def _task(filename, asset_path, options=None):
    t = unreal.AssetImportTask()
    folder, name = asset_path.rsplit('/', 1)
    t.set_editor_property('filename', filename)
    t.set_editor_property('destination_path', folder)
    t.set_editor_property('destination_name', name)
    t.set_editor_property('replace_existing', True)
    t.set_editor_property('automated', True)
    t.set_editor_property('save', False)
    if options is not None:
        t.set_editor_property('options', options)
    return t


def fbx_options(collision):
    ui = unreal.FbxImportUI()
    ui.set_editor_property('import_mesh', True)
    ui.set_editor_property('import_as_skeletal', False)
    ui.set_editor_property('mesh_type_to_import', unreal.FBXImportType.FBXIT_STATIC_MESH)
    ui.set_editor_property('import_materials', False)
    ui.set_editor_property('import_textures', False)
    ui.set_editor_property('import_animations', False)
    ui.set_editor_property('automated_import_should_detect_type', False)
    data = ui.get_editor_property('static_mesh_import_data')
    data.set_editor_property('auto_generate_collision', collision == 'box')
    data.set_editor_property('generate_lightmap_u_vs', False)
    data.set_editor_property('combine_meshes', True)
    data.set_editor_property('one_convex_hull_per_ucx', True)
    data.set_editor_property('normal_import_method', unreal.FBXNormalImportMethod.FBXNIM_IMPORT_NORMALS)
    return ui


def texture_group(name):
    """The catalogue's C++ name (TEXTUREGROUP_World, TEXTUREGROUP_UI) -> the Python enum value (TEXTUREGROUP_WORLD, ...)."""
    prefix, suffix = name.split('_', 1)
    return getattr(unreal.TextureGroup, prefix + '_' + re.sub(r'(?<=[a-z])(?=[A-Z])', '_', suffix).upper())


def apply_texture_settings(tex, e):
    tex.set_editor_property('compression_settings', getattr(unreal.TextureCompressionSettings, e['compression']))
    tex.set_editor_property('srgb', bool(e['srgb']))
    tex.set_editor_property('lod_group', texture_group(e['lod_group']))


def assign_slots(mesh, slots):
    """Gives each material slot its catalogue instance: by slot name (the FBX material is named after the MI), else by
    order. Returns the number of slots whose instance does not exist yet."""
    pending = 0
    for i, sm in enumerate(list(mesh.get_editor_property('static_materials'))):
        slot_name = str(sm.get_editor_property('material_slot_name'))
        mi_name = slot_name if slot_name in slots else (slots[i] if i < len(slots) else None)
        if mi_name is None:
            continue
        path = '/Game/DeadFire/Art/Materials/' + mi_name
        mi = eal.load_asset(path) if eal.does_asset_exist(path) else None
        if mi is None:
            pending += 1
            continue
        mesh.set_material(i, mi)
    return pending


def reset_socket_scale(mesh, names):
    """The FBX importer gives every SOCKET_ empty the file's unit conversion as its scale (100: Blender metres to
    centimetres). A socket only places what is attached to it, so its scale goes back to 1; otherwise a light bar or roof
    weapon on it is 100 times too big (found in Task 13). names: the catalogue's and the stats JSON's socket names (Python
    cannot list StaticMesh.sockets, it is protected). Returns how many sockets were reset."""
    n = 0
    for name in names:
        s = mesh.find_socket(name)
        if s is not None:
            sc = s.get_editor_property('relative_scale')
            if (sc.x, sc.y, sc.z) != (1.0, 1.0, 1.0):
                s.set_editor_property('relative_scale', unreal.Vector(1.0, 1.0, 1.0))
                n += 1
    return n


def _socket_names(e, art_dir):
    names = set(e.get('sockets', []))
    stats_path = os.path.join(art_dir, os.path.splitext(e['file'])[0] + '.json')
    if os.path.exists(stats_path):
        with open(stats_path, encoding='utf-8') as f:
            names |= set(json.load(f).get('sockets', {}))
    return sorted(names)


SOUND_CLASS = '/Engine/EngineSounds/Master'


def ensure_attenuation(att):
    """SA_DF_World: created when missing; its settings are (re)applied every run so a hand edit does not linger."""
    path = att['asset_path']
    asset = eal.load_asset(path) if eal.does_asset_exist(path) else None
    if asset is None:
        folder, name = path.rsplit('/', 1)
        asset = unreal.AssetToolsHelpers.get_asset_tools().create_asset(name, folder, unreal.SoundAttenuation, unreal.SoundAttenuationFactory())
    if asset is None:
        return None
    a = asset.get_editor_property('attenuation')
    a.set_editor_property('attenuate', True)
    a.set_editor_property('attenuation_shape', unreal.AttenuationShape.SPHERE)
    a.set_editor_property('attenuation_shape_extents', unreal.Vector(400.0, 0.0, 0.0))
    a.set_editor_property('falloff_distance', 6000.0)
    a.set_editor_property('distance_algorithm', unreal.AttenuationDistanceModel.NATURAL_SOUND)
    asset.set_editor_property('attenuation', a)
    eal.save_asset(path, only_if_is_dirty=False)
    return asset


def apply_sound_settings(wave, e, attenuation):
    wave.set_editor_property('looping', bool(e['loop']))
    wave.set_editor_property('sound_class_object', eal.load_asset(SOUND_CLASS))
    wave.set_editor_property('attenuation_settings', None if e['ui'] else attenuation)


def _run(tasks):
    unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([t for t, _ in tasks])
    failed = []
    for t, e in tasks:
        if len(t.get_editor_property('imported_object_paths')) == 0:
            failed.append('%s: import failed (%s)' % (e.get('asset', e['name']), os.path.basename(t.get_editor_property('filename'))))
    return failed


def import_all(art_dir, only=None):
    if len(unreal.EditorLevelLibrary.get_pie_worlds(False)) > 0:
        raise RuntimeError('a Play-In-Editor session is running (editor scripting is disabled during play); stop it first')
    if isinstance(only, str):
        only = [only]
    with open(os.path.join(art_dir, 'catalog.json'), encoding='utf-8') as f:
        cat = json.load(f)
    failed, imported, pending = [], 0, 0

    # textures and images
    tex_tasks = []
    for e in cat['textures']:
        if _built(e) and _wanted(only, e['name'], e['asset']):
            tex_tasks.append((_task(os.path.join(art_dir, e['file']), e['asset_path']), e))
    for e in cat['images']:
        if _built(e) and _wanted(only, e['name']):
            tex_tasks.append((_task(os.path.join(art_dir, e['file']), e['asset_path']), e))
    missing = [e for t, e in tex_tasks if not os.path.exists(t.get_editor_property('filename'))]
    failed += ['%s: %s not built' % (e.get('asset', e['name']), e['file']) for e in missing]
    deep = [e for t, e in tex_tasks if e not in missing and png_bit_depth(t.get_editor_property('filename')) not in (None, 8)]
    failed += ['%s: %s is not 8 bits per channel (UE 4.27 would encode it to sRGB twice)' % (e.get('asset', e['name']), e['file'])
               for e in deep]
    tex_tasks = [(t, e) for t, e in tex_tasks if e not in missing and e not in deep]
    if tex_tasks:
        failed += _run(tex_tasks)
    for t, e in tex_tasks:
        tex = eal.load_asset(e['asset_path'])
        if isinstance(tex, unreal.Texture2D):
            apply_texture_settings(tex, e)
            eal.save_asset(e['asset_path'], only_if_is_dirty=False)
            imported += 1

    # meshes (one task each: the FBX options differ by collision)
    for e in cat['meshes']:
        if not (_built(e) and _wanted(only, e['name'])):
            continue
        path = os.path.join(art_dir, e['file'])
        if not os.path.exists(path):
            failed.append('%s: %s not built' % (e['name'], e['file']))
            continue
        bad = _run([(_task(path, e['asset_path'], fbx_options(e['collision'])), e)])
        failed += bad
        mesh = eal.load_asset(e['asset_path']) if not bad else None
        if isinstance(mesh, unreal.StaticMesh):
            pending += assign_slots(mesh, e['slots'])
            reset_socket_scale(mesh, _socket_names(e, art_dir))
            eal.save_asset(e['asset_path'], only_if_is_dirty=False)
            imported += 1

    # sounds
    attenuation = None
    for e in cat['sounds']:
        if not (_built(e) and _wanted(only, e['name'])):
            continue
        path = os.path.join(art_dir, e['file'])
        if not os.path.exists(path):
            failed.append('%s: %s not built' % (e['name'], e['file']))
            continue
        if attenuation is None and not e['ui']:
            attenuation = ensure_attenuation(cat['attenuation'])
            if attenuation is None:
                failed.append('%s: could not be created' % cat['attenuation']['name'])
                break
            imported += 1
        bad = _run([(_task(path, e['asset_path']), e)])
        failed += bad
        wave = eal.load_asset(e['asset_path']) if not bad else None
        if isinstance(wave, unreal.SoundWave):
            apply_sound_settings(wave, e, attenuation)
            eal.save_asset(e['asset_path'], only_if_is_dirty=False)
            imported += 1
        elif not bad:
            failed.append('%s: imported as %s, not a SoundWave' % (e['name'], wave.get_class().get_name() if wave else 'nothing'))

    # fonts (Task 18): the face from the .ttf (an automated import makes only the FontFace: UFontFileImportFactory asks about a
    # Font only in its dialog), then the Font through FontFactory and the plugin's SetFontFace ("exists" when it already holds it)
    for e in cat['fonts']:
        if not _wanted(only, e['name'], e['face']):
            continue
        path = os.path.join(art_dir, e['file'])
        if not os.path.exists(path):
            failed.append('%s: %s not built (build_all --kind fonts)' % (e['name'], e['file']))
            continue
        folder = e['asset_path'].rsplit('/', 1)[0]
        face_path = folder + '/' + e['face']
        bad = _run([(_task(path, face_path), e)])
        failed += bad
        face = eal.load_asset(face_path) if not bad else None
        if not isinstance(face, unreal.FontFace):
            if not bad:
                failed.append('%s: imported as %s, not a FontFace' % (e['face'], face.get_class().get_name() if face else 'nothing'))
            continue
        eal.save_asset(face_path, only_if_is_dirty=False)
        imported += 1
        font = eal.load_asset(e['asset_path']) if eal.does_asset_exist(e['asset_path']) else None
        if font is None:
            font = unreal.AssetToolsHelpers.get_asset_tools().create_asset(e['name'], folder, unreal.Font, unreal.FontFactory())
        if not isinstance(font, unreal.Font):
            failed.append('%s: could not be created as a Font' % e['name'])
            continue
        r = unreal.DFBlueprintAuthoringLibrary.set_font_face(font, face)
        if r not in ('', 'exists'):
            failed.append('%s: SetFontFace %s' % (e['name'], r))
            continue
        eal.save_asset(e['asset_path'], only_if_is_dirty=False)
        imported += 1

    if failed:
        print('ART IMPORT FAILED: %d of %d\n%s' % (len(failed), imported + len(failed), '\n'.join(failed[:20])))
        return False
    print('ART IMPORT OK: %d assets' % imported)
    if pending:
        print('(%d mesh material slots wait for their instances: build_materials assigns them)' % pending)
    return True
