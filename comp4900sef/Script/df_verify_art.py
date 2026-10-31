"""ART VERIFY (Phase 7, spec 9): checks the imported art against the catalogue, inside the editor:

    exec(open(r'<repo>/comp4900sef/Script/df_verify_art.py').read()); verify_art(r'<repo>/art')

An entry is checked once it has been built: its recipe (texture, image) or script (mesh) is not "todo", or it comes
from Poly Haven. Material instances are checked once every texture they use is built; the nine masters always.
- Every checked entry exists at its asset_path with the right class.
- Textures and images: compression, sRGB and LOD group as catalogued (_N normal map, _ORM masks, UI images UI group).
- Meshes: LOD0 triangles within budget; bounds and their minimum corner match the Blender stats JSON within 1 cm
  (Blender +Y is Unreal -Y: the FBX importer mirrors Y); the catalogue bounds when set; material slots in catalogue
  order; sockets at their stats position and with the forward/up axes the stats record (Y mirrored); simple
  collision present exactly when the catalogue asks for
  it; and the axis fixture's arrow head on +X.
- Masters expose their parameters; instances have their catalogued parent and parameter values.
- Sounds (a recipe other than "todo"): a SoundWave at its path whose duration matches the catalogue, `looping` as catalogued,
  sound class /Engine/EngineSounds/Master, and SA_DF_World (natural-sound falloff, inner radius 400, falloff 6000) on every
  non-UI sound and no attenuation on UI sounds. SA_DF_World itself is checked once any non-UI sound is built.
- Fonts (Task 18): the face is a FontFace imported from the catalogue's .ttf; the Font has the Runtime cache type and uses the
  face (its package depends on the face's).
audit=True adds the stock audit (Task 23, spec 4.4 and 9): from every package under /Game/DeadFire (except the
functional-test folder and the look-dev level, which never ship) and the three shipped maps, it walks the AssetRegistry's
hard and soft package dependencies. A dependency under STOCK_FORBIDDEN fails, with the chain from the root that reaches it;
one under STOCK_ALLOWED passes and is not walked into; /Script packages (native classes) are skipped; anything else is
walked. Prints `STOCK AUDIT PASSED: N packages` (N = every package the walk reached, roots included) or
`STOCK AUDIT FAILED: ...` with at most 12 more lines, and writes the full list to Saved/df_stock_audit.txt either way.
Prints `ART VERIFY PASSED: N assets` or `ART VERIFY FAILED: ...` followed by at most 20 lines; returns True/False
(with audit=True, True only when both pass).
"""
import json
import os
import re

import unreal

eal = unreal.EditorAssetLibrary
MEL = unreal.MaterialEditingLibrary
TOLERANCE_CM = 1.0
MAX_LINES = 20
FIXTURE = 'SM_DF_AxisFixture'

# Parameters each master must expose (plan Task 5). Texture parameters named by the catalogue's texture keys.
MASTER_PARAMS = {
    'M_DF_Surface': dict(texture=['BC', 'N', 'ORM'], scalar=['Tiling', 'Glow'], vector=['Tint', 'EmissiveColor', 'FlatORM'], switch=['bWorldAligned']),
    'M_DF_CarPaint': dict(texture=['BC', 'N', 'ORM'], scalar=['Wear', 'Char'], vector=['PaintColor']),
    'M_DF_Road': dict(texture=['BC', 'N', 'ORM'], scalar=['DashCount'], vector=['LineColor', 'KerbA', 'KerbB']),
    'M_DF_Terrain': dict(texture=['Splat', 'Dirt_BC', 'Dirt_N', 'Dirt_ORM', 'Ash_BC', 'Ash_N', 'Ash_ORM', 'Grass_BC', 'Grass_N',
                                  'Grass_ORM', 'Rock_BC', 'Rock_N', 'Rock_ORM', 'Sand_BC', 'Sand_N', 'Sand_ORM'],
                         scalar=['TerrainSize'], vector=['TerrainOrigin', 'MacroTint', 'Dirt_Tint', 'Ash_Tint', 'Grass_Tint',
                                                          'Rock_Tint', 'Sand_Tint']),  # the set tints: Task 22
    'M_DF_FxAdditive': dict(texture=['Mask'], scalar=['Glow', 'Fade', 'FresnelPower', 'NearFade'], vector=['Color']),
    'M_DF_FxSmoke': dict(texture=['BC'], scalar=['Fade', 'RimFade', 'Density'], vector=['Color']),  # RimFade, Density: Task 22
    'M_DF_FxFlame': dict(texture=['BC'], scalar=['Fade', 'PanSpeed'], vector=['Color']),
    'M_DF_Decal': dict(texture=['BC'], scalar=['Fade']),
    'M_DF_Icon': dict(texture=['Icon'], vector=['Color']),
}


def _built(entry):
    if entry.get('source', 'gen') != 'gen':
        return True
    return entry.get('recipe', entry.get('script')) != 'todo'


def _load(path):
    return eal.load_asset(path) if eal.does_asset_exist(path) else None


def _name(obj):
    return obj.get_name() if obj else 'None'


def _close(a, b, tol=TOLERANCE_CM):
    return abs(float(a) - float(b)) <= tol


def _fmt(v):
    return '(%s)' % ', '.join('%.1f' % c for c in v)


def texture_group(name):
    """The catalogue's C++ name (TEXTUREGROUP_World, TEXTUREGROUP_UI) -> the Python enum value (TEXTUREGROUP_WORLD, ...)."""
    prefix, suffix = name.split('_', 1)
    return getattr(unreal.TextureGroup, prefix + '_' + re.sub(r'(?<=[a-z])(?=[A-Z])', '_', suffix).upper())


def check_texture(e, asset_name, problems):
    tex = _load(e['asset_path'])
    if not isinstance(tex, unreal.Texture2D):
        problems.append('%s: missing (not imported)' % asset_name if tex is None else '%s: not a Texture2D' % asset_name)
        return
    want = getattr(unreal.TextureCompressionSettings, e['compression'])
    if tex.get_editor_property('compression_settings') != want:
        problems.append('%s: compression %s, want %s' % (asset_name, tex.get_editor_property('compression_settings'), e['compression']))
    if bool(tex.get_editor_property('srgb')) != bool(e['srgb']):
        problems.append('%s: sRGB %s, want %s' % (asset_name, tex.get_editor_property('srgb'), e['srgb']))
    want_group = texture_group(e['lod_group'])
    if tex.get_editor_property('lod_group') != want_group:
        problems.append('%s: LOD group %s, want %s' % (asset_name, tex.get_editor_property('lod_group'), e['lod_group']))


def triangles(mesh, lod=0):
    """LOD0 triangle count, read section by section from the render data."""
    n = 0
    for s in range(mesh.get_num_sections(lod)):
        tris = unreal.ProceduralMeshLibrary.get_section_from_static_mesh(mesh, lod, s)[1]
        n += len(tris) // 3
    return n


def vertices(mesh, lod=0):
    out = []
    for s in range(mesh.get_num_sections(lod)):
        out += list(unreal.ProceduralMeshLibrary.get_section_from_static_mesh(mesh, lod, s)[0])
    return out


def arrow_points_plus_x(mesh):
    """The fixture's arrow head (its widest part, |Y| = 25 cm) sits at X > 0 and its tip (Y = 0) at the largest X."""
    verts = vertices(mesh)
    if not verts:
        return False
    widest = max(abs(v.y) for v in verts)
    head = [v for v in verts if abs(abs(v.y) - widest) < 0.5]
    tip_x = max(v.x for v in verts)
    tip = [v for v in verts if abs(v.x - tip_x) < 0.5]
    return all(v.x > 0 for v in head) and all(abs(v.y) < 0.5 for v in tip)


def mirrored(p):
    """A Blender-frame point (X forward, Y left, Z up) in Unreal's frame (X forward, Y right, Z up)."""
    return (p[0], -p[1], p[2])


def check_mesh(e, art_dir, problems):
    name = e['name']
    mesh = _load(e['asset_path'])
    if not isinstance(mesh, unreal.StaticMesh):
        problems.append('%s: missing (not imported)' % name if mesh is None else '%s: not a StaticMesh' % name)
        return
    stats_path = os.path.join(art_dir, os.path.splitext(e['file'])[0] + '.json')
    if not os.path.exists(stats_path):
        problems.append('%s: stats %s missing (build the mesh)' % (name, os.path.relpath(stats_path, art_dir)))
        return
    with open(stats_path, encoding='utf-8') as f:
        stats = json.load(f)
    tris = triangles(mesh)
    if tris > e['budget']:
        problems.append('%s: %d triangles, budget %d' % (name, tris, e['budget']))
    box = mesh.get_bounding_box()
    lo, hi = box.min, box.max
    size = (hi.x - lo.x, hi.y - lo.y, hi.z - lo.z)
    want_size = stats['bounds_cm']
    if not all(_close(a, b) for a, b in zip(size, want_size)):
        problems.append('%s: bounds %s cm, stats %s' % (name, _fmt(size), _fmt(want_size)))
    j_lo, j_size = stats['min_cm'], stats['bounds_cm']
    want_lo = (j_lo[0], -(j_lo[1] + j_size[1]), j_lo[2])
    if not all(_close(a, b) for a, b in zip((lo.x, lo.y, lo.z), want_lo)):
        problems.append('%s: minimum corner %s cm, stats say %s' % (name, _fmt((lo.x, lo.y, lo.z)), _fmt(want_lo)))
    if e.get('bounds') and not all(_close(a, b) for a, b in zip(size, e['bounds'])):
        problems.append('%s: bounds %s cm, catalogue %s' % (name, _fmt(size), _fmt(e['bounds'])))
    slots = list(mesh.get_editor_property('static_materials'))
    if len(slots) != len(e['slots']):
        problems.append('%s: %d material slots, catalogue %d' % (name, len(slots), len(e['slots'])))
    for i, mi_name in enumerate(e['slots'][:len(slots)]):
        have = slots[i].get_editor_property('material_interface')
        if _name(have) != mi_name:
            problems.append('%s: slot %d is %s, want %s' % (name, i, _name(have), mi_name))
    for sock in e['sockets']:
        s = mesh.find_socket(sock)
        if s is None:
            problems.append('%s: socket %s missing' % (name, sock))
            continue
        if sock not in stats['sockets']:
            problems.append('%s: socket %s not in the stats JSON' % (name, sock))
            continue
        loc = s.get_editor_property('relative_location')
        want = mirrored(stats['sockets'][sock])
        if not all(_close(a, b) for a, b in zip((loc.x, loc.y, loc.z), want)):
            problems.append('%s: socket %s at %s, stats (Y mirrored) %s' % (name, sock, _fmt((loc.x, loc.y, loc.z)), _fmt(want)))
        axes = stats.get('socket_axes', {}).get(sock)
        if axes:  # its forward (X) and up (Z) axes as the mesh script meant them (a socket's +X is where things point)
            r = s.get_editor_property('relative_rotation')
            for label, have, want_axis in (('X', unreal.MathLibrary.get_forward_vector(r), axes['x']),
                                           ('Z', unreal.MathLibrary.get_up_vector(r), axes['z'])):
                w = mirrored(want_axis)
                if any(abs(a - b) > 0.02 for a, b in zip((have.x, have.y, have.z), w)):
                    problems.append('%s: socket %s %s axis %s, stats (Y mirrored) %s' % (
                        name, sock, label, _fmt((have.x, have.y, have.z)), _fmt(w)))
    # every socket the mesh script made (the catalogue's and the extra ones, e.g. Arch_*) has scale 1: a socket only places
    # what is attached to it (Task 13 found every imported socket at 100, the FBX unit conversion, which made the light bar
    # on the Roof socket 100 times too big); df_import_art resets it after each import
    for sock in sorted(set(e['sockets']) | set(stats.get('sockets', {}))):
        s = mesh.find_socket(sock)
        if s is None:
            continue  # a missing catalogue socket is reported above
        sc = s.get_editor_property('relative_scale')
        if any(abs(v - 1.0) > 1e-3 for v in (sc.x, sc.y, sc.z)):
            problems.append('%s: socket %s scale %s, want 1' % (name, sock, _fmt((sc.x, sc.y, sc.z))))
    # get_simple_collision_count counts boxes, spheres and capsules only; UCX hulls are convex elements
    simple = unreal.EditorStaticMeshLibrary.get_simple_collision_count(mesh) + unreal.EditorStaticMeshLibrary.get_convex_collision_count(mesh)
    if e['collision'] == 'none' and simple != 0:
        problems.append('%s: %d simple collision shapes, catalogue says none' % (name, simple))
    if e['collision'] in ('box', 'ucx') and simple < 1:
        problems.append('%s: no simple collision (catalogue: %s)' % (name, e['collision']))
    if name == FIXTURE and not arrow_points_plus_x(mesh):
        problems.append('%s: the arrow does not point +X' % name)


def check_master(m, problems):
    mat = _load(m['asset_path'])
    if not isinstance(mat, unreal.Material):
        problems.append('%s: missing' % m['name'] if mat is None else '%s: not a Material' % m['name'])
        return
    want = MASTER_PARAMS.get(m['name'], {})
    have = dict(texture=MEL.get_texture_parameter_names(mat), scalar=MEL.get_scalar_parameter_names(mat),
                vector=MEL.get_vector_parameter_names(mat), switch=MEL.get_static_switch_parameter_names(mat))
    for kind, names in want.items():
        got = {str(n) for n in have[kind]}
        missing = [n for n in names if n not in got]
        if missing:
            problems.append('%s: %s parameters missing: %s' % (m['name'], kind, ', '.join(missing)))


def check_instance(e, problems):
    name = e['name']
    mi = _load(e['asset_path'])
    if not isinstance(mi, unreal.MaterialInstanceConstant):
        problems.append('%s: missing' % name if mi is None else '%s: not a MaterialInstanceConstant' % name)
        return
    parent = mi.get_editor_property('parent')
    if _name(parent) != e['parent']:
        problems.append('%s: parent %s, want %s' % (name, _name(parent), e['parent']))
        return
    for p, tex in e['textures'].items():
        have = MEL.get_material_instance_texture_parameter_value(mi, p)
        if _name(have) != tex:
            problems.append('%s: %s = %s, want %s' % (name, p, _name(have), tex))
    for p, v in e['scalars'].items():
        have = MEL.get_material_instance_scalar_parameter_value(mi, p)
        if abs(have - v) > 1e-3:
            problems.append('%s: %s = %.3f, want %.3f' % (name, p, have, v))
    for p, v in e['vectors'].items():
        c = MEL.get_material_instance_vector_parameter_value(mi, p)
        if not all(abs(a - b) <= 1e-3 for a, b in zip((c.r, c.g, c.b, c.a), v)):
            problems.append('%s: %s = (%.3f, %.3f, %.3f, %.3f), want %s' % (name, p, c.r, c.g, c.b, c.a, tuple(round(x, 3) for x in v)))


SOUND_CLASS = '/Engine/EngineSounds/Master'
ATTENUATION_INNER_CM = 400.0
ATTENUATION_FALLOFF_CM = 6000.0


def check_attenuation(att, problems):
    asset = _load(att['asset_path'])
    if not isinstance(asset, unreal.SoundAttenuation):
        problems.append('%s: %s' % (att['name'], 'missing (not imported)' if asset is None else 'is a ' + asset.get_class().get_name()))
        return
    a = asset.get_editor_property('attenuation')
    if a.get_editor_property('distance_algorithm') != unreal.AttenuationDistanceModel.NATURAL_SOUND:
        problems.append('%s: distance algorithm %s, want NATURAL_SOUND' % (att['name'], a.get_editor_property('distance_algorithm')))
    if not _close(a.get_editor_property('attenuation_shape_extents').x, ATTENUATION_INNER_CM):
        problems.append('%s: inner radius %s, want %s' % (att['name'], a.get_editor_property('attenuation_shape_extents').x, ATTENUATION_INNER_CM))
    if not _close(a.get_editor_property('falloff_distance'), ATTENUATION_FALLOFF_CM):
        problems.append('%s: falloff distance %s, want %s' % (att['name'], a.get_editor_property('falloff_distance'), ATTENUATION_FALLOFF_CM))


def check_sound(e, att, problems):
    wave = _load(e['asset_path'])
    if not isinstance(wave, unreal.SoundWave):
        problems.append('%s: %s' % (e['name'], 'missing (not imported)' if wave is None else 'is a ' + wave.get_class().get_name()))
        return
    if abs(float(wave.get_editor_property('duration')) - e['seconds']) > 0.01:
        problems.append('%s: duration %.3f s, want %s' % (e['name'], wave.get_editor_property('duration'), e['seconds']))
    if bool(wave.get_editor_property('looping')) != bool(e['loop']):
        problems.append('%s: looping %s, want %s' % (e['name'], wave.get_editor_property('looping'), e['loop']))
    sc = wave.get_editor_property('sound_class_object')
    if _name(sc) != SOUND_CLASS.rsplit('/', 1)[1] or (sc and sc.get_path_name().split('.')[0] != SOUND_CLASS):
        problems.append('%s: sound class %s, want %s' % (e['name'], sc.get_path_name() if sc else 'None', SOUND_CLASS))
    got = wave.get_editor_property('attenuation_settings')
    if e['ui']:
        if got is not None:
            problems.append('%s: UI sound has attenuation %s' % (e['name'], got.get_name()))
    elif got is None or got.get_name() != att['name']:
        problems.append('%s: attenuation %s, want %s' % (e['name'], _name(got), att['name']))


def check_font(e, problems):
    """Task 18: the face (a FontFace imported from the catalogue's .ttf) and the Font (Runtime cache; its package depends on the
    face: SetFontFace made the face its default typeface. Python cannot read a Font's composite font, the registry can)."""
    face_path = e['asset_path'].rsplit('/', 1)[0] + '/' + e['face']
    face = _load(face_path)
    if not isinstance(face, unreal.FontFace):
        problems.append('%s: %s' % (e['face'], 'missing (not imported)' if face is None else 'is a ' + face.get_class().get_name()))
    elif os.path.basename(face.get_editor_property('source_filename')) != os.path.basename(e['file']):
        problems.append('%s: imported from %s, want %s' % (e['face'], face.get_editor_property('source_filename'), e['file']))
    font = _load(e['asset_path'])
    if not isinstance(font, unreal.Font):
        problems.append('%s: %s' % (e['name'], 'missing (not imported)' if font is None else 'is a ' + font.get_class().get_name()))
        return
    if font.get_editor_property('font_cache_type') != unreal.FontCacheType.RUNTIME:
        problems.append('%s: font cache type %s, want RUNTIME' % (e['name'], font.get_editor_property('font_cache_type')))
    deps = unreal.AssetRegistryHelpers.get_asset_registry().get_dependencies(e['asset_path'], unreal.AssetRegistryDependencyOptions())
    if face_path not in [str(d) for d in (deps or [])]:
        problems.append('%s: its typeface does not use %s' % (e['name'], e['face']))


# The stock audit (Task 23). Entries are package paths; an entry matches itself and everything below it.
AUDIT_ROOT = '/Game/DeadFire'
AUDIT_EXCLUDE = ('/Game/DeadFire/Tests', '/Game/DeadFire/Art/L_DF_LookDev', '/Game/DeadFire/Art/L_DF_LookDev_BuiltData')
SHIPPED_MAPS = ('/Game/DeadFire/Maps/L_TestTrack', '/Game/DeadFire/Maps/L_Switchback', '/Game/DeadFire/Maps/L_MainMenu')
STOCK_ALLOWED = (  # spec 4.4: the physics and animation backbone, engine content, and Phase 6's copied VehicleHUD
    '/Game/VehicleBP/Sedan', '/Game/Vehicle/Sedan',
    '/Game/Mannequin/Character/Mesh', '/Game/Mannequin/Animations', '/Game/ThirdPersonBP/Blueprints',
    '/Engine', '/Game/VehicleBP/Blueprints/VehicleHUD')
STOCK_FORBIDDEN = ('/Game/StarterContent', '/Game/VehicleAdv', '/Game/Geometry', '/Game/Vehicle/Meshes')
AUDIT_FILE = 'df_stock_audit.txt'  # under Saved/; the full list, whatever the result
AUDIT_MAX_LINES = 12  # printed failure lines (with ART VERIFY's 20, the remote reply stays under about 4 KB)


def _under(package, prefixes):
    return any(package == p or package.startswith(p + '/') for p in prefixes)


def _dependencies(registry, package, hard):
    options = unreal.AssetRegistryDependencyOptions()
    for name, value in (('include_hard_package_references', hard), ('include_soft_package_references', not hard),
                        ('include_searchable_names', False), ('include_soft_management_references', False),
                        ('include_hard_management_references', False)):
        options.set_editor_property(name, value)
    return [str(d) for d in (registry.get_dependencies(package, options) or [])]


def stock_audit():
    """Returns (passed, printed lines). Plain strings only: no asset or world is loaded."""
    registry = unreal.AssetRegistryHelpers.get_asset_registry()
    roots = {str(a.package_name) for a in registry.get_assets_by_path(AUDIT_ROOT, recursive=True)}
    roots = {p for p in roots if not _under(p, AUDIT_EXCLUDE)}
    missing = [m for m in SHIPPED_MAPS if m not in roots]
    roots |= set(SHIPPED_MAPS)
    parent = {p: None for p in roots}  # package -> the package the walk reached it from (None for a root)
    queue = sorted(roots)
    failures, allowed, other, excluded_reached = [], set(), set(), set()
    while queue:
        package = queue.pop()
        for kind, hard in (('hard', True), ('soft', False)):
            for dep in _dependencies(registry, package, hard):
                if dep.startswith('/Script/') or dep == package:
                    continue
                if _under(dep, STOCK_FORBIDDEN):
                    failures.append((package, dep, kind))  # reported, never walked into
                    continue
                if dep in parent:
                    continue
                parent[dep] = package
                if _under(dep, STOCK_ALLOWED):
                    allowed.add(dep)  # counted, never walked into
                    continue
                if not dep.startswith(AUDIT_ROOT + '/'):
                    other.add(dep)  # stock outside both lists: walked, so a forbidden package behind it is still found
                elif _under(dep, AUDIT_EXCLUDE):
                    excluded_reached.add(dep)  # a shipped asset reaches a test or look-dev package: it ships, so walk it
                queue.append(dep)

    def chain(package):
        steps = []
        while package is not None:
            steps.append(package)
            package = parent.get(package)
        return ' <- '.join(steps)

    total = len(parent)  # roots + every non-forbidden package reached
    lines_out = ['STOCK AUDIT: %d roots, %d packages walked, %d allowlisted (not walked), %d other stock walked, %d excluded reached'
                 % (len(roots), total - len(allowed), len(allowed), len(other), len(excluded_reached))]
    body = ['%s -> %s [%s]   chain: %s' % (ref, dep, kind, chain(ref)) for ref, dep, kind in sorted(failures)]
    body += ['missing shipped map: %s' % m for m in missing]
    report = lines_out + ['', 'FAILURES (%d)' % len(body)] + body
    report += ['', 'OTHER STOCK WALKED (%d)' % len(other)] + ['%s   chain: %s' % (p, chain(p)) for p in sorted(other)]
    report += ['', 'EXCLUDED PACKAGES REACHED (%d)' % len(excluded_reached)] + ['%s   chain: %s' % (p, chain(p)) for p in sorted(excluded_reached)]
    report += ['', 'ALLOWLISTED (%d)' % len(allowed)] + ['%s   from %s' % (p, parent[p]) for p in sorted(allowed)]
    path = os.path.join(unreal.Paths.project_saved_dir(), AUDIT_FILE)
    with open(path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(report) + '\n')
    if body:
        referencers = {ref for ref, _, _ in failures}
        shown = ['%s -> %s [%s]' % (ref.replace(AUDIT_ROOT + '/', ''), dep, kind) for ref, dep, kind in sorted(failures)]
        shown += ['missing shipped map: %s' % m for m in missing]
        if len(shown) > AUDIT_MAX_LINES:
            shown = shown[:AUDIT_MAX_LINES - 1] + ['... and %d more' % (len(shown) - AUDIT_MAX_LINES + 1)]
        return False, ['STOCK AUDIT FAILED: %d reference(s) from %d asset(s); %d packages audited; full list %s'
                       % (len(failures), len(referencers), total, os.path.abspath(path))] + shown
    return True, ['STOCK AUDIT PASSED: %d packages' % total, lines_out[0]]


def verify_art(art_dir, audit=False):
    if len(unreal.EditorLevelLibrary.get_pie_worlds(False)) > 0:
        raise RuntimeError('a Play-In-Editor session is running (editor scripting is disabled during play); stop it first')
    with open(os.path.join(art_dir, 'catalog.json'), encoding='utf-8') as f:
        cat = json.load(f)
    problems, checked, skipped = [], 0, 0
    built_textures = set()
    for e in cat['textures']:
        if not _built(e):
            skipped += 1
            continue
        check_texture(e, e['asset'], problems)
        built_textures.add(e['asset'])
        checked += 1
    for e in cat['images']:
        if not _built(e):
            skipped += 1
            continue
        check_texture(e, e['name'], problems)
        built_textures.add(e['name'])
        checked += 1
    for e in cat['meshes']:
        if not _built(e):
            skipped += 1
            continue
        check_mesh(e, art_dir, problems)
        checked += 1
    for m in cat['masters']:
        check_master(m, problems)
        checked += 1
    for e in cat['materials']:
        if not all(t in built_textures for t in e['textures'].values()):
            skipped += 1
            continue
        check_instance(e, problems)
        checked += 1
    built_sounds = [e for e in cat['sounds'] if _built(e)]
    if any(not e['ui'] for e in built_sounds):
        check_attenuation(cat['attenuation'], problems)
        checked += 1
    for e in cat['sounds']:
        if not _built(e):
            skipped += 1
            continue
        check_sound(e, cat['attenuation'], problems)
        checked += 1
    for e in cat['fonts']:  # Task 18: the face and the font
        check_font(e, problems)
        checked += 2
    if problems:
        lines = problems if len(problems) <= MAX_LINES else problems[:MAX_LINES - 1] + ['... and %d more' % (len(problems) - MAX_LINES + 1)]
        print('ART VERIFY FAILED: %d problem(s) in %d checked assets\n%s' % (len(problems), checked, '\n'.join(lines)))
    else:
        print('ART VERIFY PASSED: %d assets' % checked)
        print('(%d catalogue entries not built yet: todo recipes)' % skipped)
    audit_ok = True
    if audit:
        audit_ok, audit_lines = stock_audit()
        print('\n'.join(audit_lines))
    return not problems and audit_ok
