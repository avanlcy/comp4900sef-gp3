"""Builds the nine Dead Fire master materials and every catalogue material instance (Phase 7, spec 4.1), in the editor:

    exec(open(r'<repo>/comp4900sef/Script/df_build_materials.py').read()); build_materials(r'<repo>/art'[, only=[...]])

Masters are rebuilt from scratch with MaterialEditingLibrary on every run (the asset is kept, so instances and meshes
keep their references). Instances are created with MaterialInstanceConstantFactoryNew when missing; their overrides
are cleared and set again from art/catalog.json. Then every imported catalogue mesh gets its material slots (the
importer leaves a slot open when its instance did not exist yet). Run df_import_art.py first: the masters' default
textures and the instances' textures are the imported T_DF_* assets.

Parameter conventions:
- A vector parameter's alpha switches it on: Tint (1,1,1,0), EmissiveColor (0,0,0,0) and FlatORM (1,0.5,0,0) do nothing
  until an instance sets them (the catalogue writes alpha 1). Tint recolours the texture around its own average colour
  (the BC's last mip), so a full-colour texture keeps its detail at the tint's brightness instead of being darkened by
  a multiply. FlatORM's RGB replaces the ORM texture with a flat AO / roughness / metal: the catalogue gives it to every
  untextured M_DF_Surface instance (glossy Glass, satin Dark, clean Lights), which would otherwise show the default
  ORM's rubber detail (a Masks sampler needs a TC_Masks default, so the default stays T_DF_Rubber_ORM).
- Glow 0, FresnelPower 0 and NearFade 0 are off.
- M_DF_Terrain: splat R dirt, G ash and dry grass (split by a large world-space noise), B rock, A sand, laid over the
  ash/grass base in that order; every set samples with the shared wrap sampler (22 samples, beyond 16 own samplers).
  Task 22: <set>_Tint (Dirt, Ash, Grass, Rock, Sand) recolours a set around its own average, as Tint does.
Prints `MATERIALS OK: 9 masters, N instances`.
"""
import json
import os

import unreal

MEL = unreal.MaterialEditingLibrary
eal = unreal.EditorAssetLibrary
U = unreal

MAT_DIR = '/Game/DeadFire/Art/Materials'
TEX_DIR = '/Game/DeadFire/Art/Textures'
TERRAIN_DIR = '/Game/DeadFire/Art/Terrain'      # the splat maps (T_DF_Splat_*), beside their MI_DF_Terrain_* instances
WHITE = '/Engine/EngineResources/WhiteSquareTexture'
FLAT_NORMAL = '/Engine/EngineMaterials/FlatNormal'
GREY_LINEAR = '/Engine/ArtTools/RenderToTexture/Textures/127grey'
ORM_DEFAULT = TEX_DIR + '/T_DF_Rubber_ORM'      # matte, not metal: what an untextured instance gets
WORLD_TILE_CM = 400.0                           # one texture repeat in world-aligned UVs (road, terrain, bWorldAligned)
TERRAIN_SIZE_CM = 100800.0                      # spec 8.1: 1008 m landscapes
MACRO_TILE_CM = 6000.0                          # the terrain's ash/grass and tint noise
SMOKE_RIM_EXPONENT = 1.0                        # Task 22: a smoke puff's opacity x (1 - (1 - N.V)^this): it thins from the centre out
DECAL_SPECULAR = 0.1                            # Task 22: the scorch's specular (soot)

COLOR, NORMAL, MASKS, LINEAR = (U.MaterialSamplerType.SAMPLERTYPE_COLOR, U.MaterialSamplerType.SAMPLERTYPE_NORMAL,
                                U.MaterialSamplerType.SAMPLERTYPE_MASKS, U.MaterialSamplerType.SAMPLERTYPE_LINEAR_COLOR)
SHARED_WRAP = U.SamplerSourceMode.SSM_WRAP_WORLD_GROUP_SETTINGS
SHARED_CLAMP = U.SamplerSourceMode.SSM_CLAMP_WORLD_GROUP_SETTINGS


def _load(path):
    obj = eal.load_asset(path)
    if obj is None:
        raise RuntimeError('missing asset %s (run df_import_art.py first)' % path)
    return obj


class Graph:
    """A thin builder over MaterialEditingLibrary: expressions, wires with constant fallbacks, outputs."""

    def __init__(self, mat):
        self.mat = mat

    def e(self, cls, **props):
        x = MEL.create_material_expression(self.mat, getattr(U, 'MaterialExpression' + cls), 0, 0)
        for k, v in props.items():
            x.set_editor_property(k, v)
        return x

    def wire(self, src, dst, pin=''):
        expr, out = src if isinstance(src, tuple) else (src, '')
        if not MEL.connect_material_expressions(expr, out, dst, pin):
            raise RuntimeError('%s: cannot wire %s.%s -> %s.%s' % (self.mat.get_name(), expr.get_class().get_name(), out,
                                                                   dst.get_class().get_name(), pin))

    def _bin(self, cls, a, b):
        x = self.e(cls)
        for pin, v, const in (('A', a, 'const_a'), ('B', b, 'const_b')):
            if isinstance(v, (int, float)):
                x.set_editor_property(const, float(v))
            else:
                self.wire(v, x, pin)
        return x

    def mul(self, a, b):
        return self._bin('Multiply', a, b)

    def add(self, a, b):
        return self._bin('Add', a, b)

    def sub(self, a, b):
        return self._bin('Subtract', a, b)

    def div(self, a, b):
        return self._bin('Divide', a, b)

    def max(self, a, b):
        return self._bin('Max', a, b)

    def min(self, a, b):
        return self._bin('Min', a, b)

    def lerp(self, a, b, alpha):
        x = self.e('LinearInterpolate')
        for pin, v, const in (('A', a, 'const_a'), ('B', b, 'const_b'), ('Alpha', alpha, 'const_alpha')):
            if isinstance(v, (int, float)):
                x.set_editor_property(const, float(v))
            else:
                self.wire(v, x, pin)
        return x

    def one(self, cls, v):
        x = self.e(cls)
        self.wire(v, x)
        return x

    def sat(self, v):
        return self.one('Saturate', v)

    def mask(self, v, channels):
        x = self.e('ComponentMask', r='r' in channels, g='g' in channels, b='b' in channels, a='a' in channels)
        self.wire(v, x)
        return x

    def append(self, a, b):
        x = self.e('AppendVector')
        self.wire(a, x, 'A')
        self.wire(b, x, 'B')
        return x

    def c3(self, rgb):
        return self.e('Constant3Vector', constant=U.LinearColor(rgb[0], rgb[1], rgb[2], 1.0))

    def scalar(self, name, default):
        return self.e('ScalarParameter', parameter_name=name, default_value=float(default))

    def vector(self, name, rgba):
        return self.e('VectorParameter', parameter_name=name, default_value=U.LinearColor(*[float(c) for c in rgba]))

    def tex(self, name, path, sampler, uv=None, source=None, mip=None):
        """mip = a fixed mip level (12 = the 1x1 average of a 1024 or 2048 map), as sample()."""
        x = self.e('TextureSampleParameter2D', parameter_name=name, texture=_load(path), sampler_type=sampler)
        if source is not None:
            x.set_editor_property('sampler_source', source)
        if mip is not None:
            x.set_editor_property('mip_value_mode', U.TextureMipValueMode.TMVM_MIP_LEVEL)
            x.set_editor_property('const_mip_value', int(mip))
        if uv is not None:
            self.wire(uv, x, 'UVs')
        return x

    def sample(self, tex_object, sampler, uv=None, mip=None):
        """A TextureSample of a TextureObjectParameter; mip = a fixed mip level (12 = the 1x1 average of a 1024 map)."""
        x = self.e('TextureSample', sampler_type=sampler)
        if mip is not None:
            x.set_editor_property('mip_value_mode', U.TextureMipValueMode.TMVM_MIP_LEVEL)
            x.set_editor_property('const_mip_value', int(mip))
        self.wire(tex_object, x, 'Tex')
        if uv is not None:
            self.wire(uv, x, 'UVs')
        return x

    def world_uv(self, tile_cm=WORLD_TILE_CM):
        return self.div(self.mask(self.e('WorldPosition'), 'rg'), float(tile_cm))

    def ramp(self, edge, value, sharp=2000.0):
        """1 where value < edge, 0 above, with a one-pixel-ish ramp: saturate((edge - value) * sharp)."""
        return self.sat(self.mul(self.sub(edge, value), sharp))

    def on(self, scalar):
        """1 when the scalar parameter is > 0, else 0."""
        return self.one('Ceil', self.sat(scalar))

    def out(self, src, prop):
        expr, pin = src if isinstance(src, tuple) else (src, '')
        if not MEL.connect_material_property(expr, pin, getattr(U.MaterialProperty, prop)):
            raise RuntimeError('%s: cannot connect %s' % (self.mat.get_name(), prop))


def _normalised_bc(g, bco, uv):
    """(sample RGB, sample / its texture's average colour)."""
    bc = g.sample(bco, COLOR, uv)
    mean = g.sample(bco, COLOR, mip=12)
    return (bc, 'RGB'), g.div((bc, 'RGB'), g.max((mean, 'RGB'), 0.002))


def build_surface(g):
    tiling = g.scalar('Tiling', 1.0)
    uv_mesh = g.mul(g.e('TextureCoordinate'), tiling)
    uv_world = g.mul(g.world_uv(), tiling)
    uv = g.e('StaticSwitchParameter', parameter_name='bWorldAligned', default_value=False)
    g.wire(uv_world, uv, 'True')
    g.wire(uv_mesh, uv, 'False')
    bco = g.e('TextureObjectParameter', parameter_name='BC', texture=_load(WHITE), sampler_type=COLOR)
    bc, detail = _normalised_bc(g, bco, uv)
    tint = g.vector('Tint', (1, 1, 1, 0))
    base = g.lerp(bc, g.mul(detail, g.mask(tint, 'rgb')), (tint, 'A'))
    orm_tex = g.tex('ORM', ORM_DEFAULT, MASKS, uv)
    flat = g.vector('FlatORM', (1, 0.5, 0, 0))  # alpha 1: a flat AO/roughness/metal instead of the ORM texture
    orm = g.lerp((orm_tex, 'RGB'), g.mask(flat, 'rgb'), (flat, 'A'))
    g.out(base, 'MP_BASE_COLOR')
    g.out(g.tex('N', FLAT_NORMAL, NORMAL, uv), 'MP_NORMAL')
    g.out(g.mask(orm, 'r'), 'MP_AMBIENT_OCCLUSION')
    g.out(g.mask(orm, 'g'), 'MP_ROUGHNESS')
    g.out(g.mask(orm, 'b'), 'MP_METALLIC')
    emissive = g.vector('EmissiveColor', (0, 0, 0, 0))
    g.out(g.mul(g.lerp(base, g.mask(emissive, 'rgb'), (emissive, 'A')), g.scalar('Glow', 0.0)), 'MP_EMISSIVE_COLOR')


def build_car_paint(g):
    uv = g.e('TextureCoordinate')
    bco = g.e('TextureObjectParameter', parameter_name='BC', texture=_load(TEX_DIR + '/T_DF_PaintedMetal_BC'), sampler_type=COLOR)
    _, grime = _normalised_bc(g, bco, uv)
    orm = g.tex('ORM', TEX_DIR + '/T_DF_PaintedMetal_ORM', MASKS, uv)
    paint = g.mul(g.mask(g.vector('PaintColor', (0.5, 0.5, 0.5, 1)), 'rgb'), grime)
    # chips: the painted-metal metal mask above its 0.15 floor, scaled by Wear; they show bare grey metal
    chip = g.mul(g.sat(g.mul(g.sub((orm, 'B'), 0.15), 1.5)), g.scalar('Wear', 0.5))
    base = g.lerp(paint, g.c3((0.45, 0.45, 0.45)), chip)
    metal = g.mul(chip, 0.9)
    char = g.scalar('Char', 0.0)
    g.out(g.lerp(base, g.mul(g.c3((0.02, 0.018, 0.016)), grime), char), 'MP_BASE_COLOR')
    g.out(g.lerp((orm, 'G'), 0.9, char), 'MP_ROUGHNESS')
    g.out(g.lerp(metal, 0.0, char), 'MP_METALLIC')
    g.out((orm, 'R'), 'MP_AMBIENT_OCCLUSION')
    g.out(g.tex('N', TEX_DIR + '/T_DF_PaintedMetal_N', NORMAL, uv), 'MP_NORMAL')


def build_road(g):
    wuv = g.world_uv()
    bc = g.tex('BC', TEX_DIR + '/T_DF_Asphalt_BC', COLOR, wuv)
    n = g.tex('N', TEX_DIR + '/T_DF_Asphalt_N', NORMAL, wuv)
    orm = g.tex('ORM', TEX_DIR + '/T_DF_Asphalt_ORM', MASKS, wuv)
    uv0 = g.e('TextureCoordinate')
    u, v = g.mask(uv0, 'r'), g.mask(uv0, 'g')       # U along the segment, V across it (spec 8.2)
    dashes = g.scalar('DashCount', 4.0)
    edge = g.min(v, g.one('OneMinus', v))           # 0 at either edge, 0.5 on the centre line
    kerb = g.ramp(0.04, edge)                       # red-and-white bands along both edges
    stripe = g.ramp(0.5, g.one('Frac', g.mul(u, g.mul(dashes, 2.0))))
    kerb_col = g.lerp(g.mask(g.vector('KerbB', (0.85, 0.85, 0.85, 1)), 'rgb'), g.mask(g.vector('KerbA', (0.6, 0.02, 0.02, 1)), 'rgb'), stripe)
    edge_line = g.ramp(0.012, g.one('Abs', g.sub(edge, 0.07)))
    centre = g.mul(g.ramp(0.006, g.one('Abs', g.sub(v, 0.5))), g.ramp(0.5, g.one('Frac', g.mul(u, dashes))))
    paint = g.max(edge_line, centre)
    col = g.lerp(g.lerp((bc, 'RGB'), g.mask(g.vector('LineColor', (0.8, 0.8, 0.8, 1)), 'rgb'), paint), kerb_col, kerb)
    marked = g.max(paint, kerb)
    g.out(col, 'MP_BASE_COLOR')
    g.out(g.lerp((orm, 'G'), 0.6, marked), 'MP_ROUGHNESS')
    g.out((orm, 'R'), 'MP_AMBIENT_OCCLUSION')
    g.out(g.lerp((n, 'RGB'), g.c3((0, 0, 1)), marked), 'MP_NORMAL')


TERRAIN_SETS = [('Dirt', 'Dirt'), ('Ash', 'AshGround'), ('Grass', 'DryGrass'), ('Rock', 'Rock'), ('Sand', 'Sand')]


def build_terrain(g):
    origin = g.vector('TerrainOrigin', (0, 0, 0, 0))
    splat_uv = g.div(g.sub(g.mask(g.e('WorldPosition'), 'rg'), g.mask(origin, 'rg')), g.scalar('TerrainSize', TERRAIN_SIZE_CM))
    splat = g.tex('Splat', GREY_LINEAR, LINEAR, splat_uv, SHARED_CLAMP)
    wuv = g.world_uv()
    sets = {}
    for key, tex in TERRAIN_SETS:
        bc_path = '%s/T_DF_%s_BC' % (TEX_DIR, tex)
        bc = g.tex('%s_BC' % key, bc_path, COLOR, wuv, SHARED_WRAP)
        # Task 22: <key>_Tint recolours the set around its own average colour (its BC's last mip, the same parameter), as
        # M_DF_Surface's Tint does, so a scanned set keeps its detail at the spec §3 ground colour; alpha switches it on
        mean = g.tex('%s_BC' % key, bc_path, COLOR, source=SHARED_WRAP, mip=12)
        tint = g.vector('%s_Tint' % key, (1, 1, 1, 0))
        recoloured = g.mul(g.div((bc, 'RGB'), g.max((mean, 'RGB'), 0.002)), g.mask(tint, 'rgb'))
        sets[key] = [g.lerp((bc, 'RGB'), recoloured, (tint, 'A')),
                     (g.tex('%s_N' % key, '%s/T_DF_%s_N' % (TEX_DIR, tex), NORMAL, wuv, SHARED_WRAP), 'RGB'),
                     (g.tex('%s_ORM' % key, '%s/T_DF_%s_ORM' % (TEX_DIR, tex), MASKS, wuv, SHARED_WRAP), 'RGB')]
    noise = g.e('TextureSample', texture=_load(TEX_DIR + '/T_DF_FxNoise_BC'), sampler_type=COLOR, sampler_source=SHARED_WRAP)
    g.wire(g.world_uv(MACRO_TILE_CM), noise, 'UVs')
    grass = g.sat(g.mul(g.sub((noise, 'R'), 0.45), 4.0))   # G channel: dry grass where the macro noise is high, else ash
    out = []
    for i in range(3):
        c = g.lerp(sets['Ash'][i], sets['Grass'][i], grass)
        c = g.lerp(c, sets['Dirt'][i], (splat, 'R'))
        c = g.lerp(c, sets['Sand'][i], (splat, 'A'))
        out.append(g.lerp(c, sets['Rock'][i], (splat, 'B')))
    tint = g.vector('MacroTint', (1, 1, 1, 0))
    tint_mul = g.lerp(g.c3((1, 1, 1)), g.mask(tint, 'rgb'), g.mul((noise, 'G'), (tint, 'A')))
    g.out(g.mul(out[0], tint_mul), 'MP_BASE_COLOR')
    g.out(out[1], 'MP_NORMAL')
    g.out(g.mask(out[2], 'r'), 'MP_AMBIENT_OCCLUSION')
    g.out(g.mask(out[2], 'g'), 'MP_ROUGHNESS')
    g.out(g.mask(out[2], 'b'), 'MP_METALLIC')


def build_fx_additive(g):
    color = g.mask(g.vector('Color', (1, 1, 1, 1)), 'rgb')
    mask = g.tex('Mask', WHITE, COLOR)
    fresnel_power = g.scalar('FresnelPower', 0.0)
    fres = g.e('Fresnel', base_reflect_fraction=0.0)
    g.wire(fresnel_power, fres, 'ExponentIn')
    fres_term = g.lerp(1.0, fres, g.on(fresnel_power))
    near_fade = g.scalar('NearFade', 0.0)
    near = g.sat(g.div(g.e('PixelDepth'), g.max(near_fade, 1.0)))
    near_term = g.lerp(1.0, near, g.on(near_fade))
    k = g.mul(g.mul(g.mul(g.scalar('Glow', 1.0), g.scalar('Fade', 1.0)), (mask, 'R')), g.mul(fres_term, near_term))
    g.out(g.mul(color, k), 'MP_EMISSIVE_COLOR')


def build_fx_smoke(g):
    bc = g.tex('BC', TEX_DIR + '/T_DF_SmokePuff_BC', COLOR)
    g.out(g.mul(g.mask(g.vector('Color', (0.25, 0.25, 0.25, 1)), 'rgb'), (bc, 'RGB')), 'MP_BASE_COLOR')
    soft = g.e('DepthFade', fade_distance_default=100.0)
    # Task 22: the puff is a sphere; its opacity fades out toward the silhouette (1 - Fresnel), so a puff reads as soft smoke,
    # not a hard-rimmed glassy ball (Task 15's look item). RimFade 1 = the full fade, 0 = none (the impact dust's cone keeps its
    # opacity); Density scales the opacity (saturated), for a puff that must read at a glance
    rim = g.lerp(1.0, g.one('OneMinus', g.e('Fresnel', exponent=SMOKE_RIM_EXPONENT, base_reflect_fraction=0.0)), g.scalar('RimFade', 1.0))
    alpha = g.mul(g.mul((bc, 'A'), g.scalar('Fade', 1.0)), rim)
    g.wire(g.sat(g.mul(alpha, g.scalar('Density', 1.0))), soft, 'Opacity')
    g.out(soft, 'MP_OPACITY')
    g.out(g.e('Constant', r=1.0), 'MP_ROUGHNESS')


def build_fx_flame(g):
    uv0 = g.e('TextureCoordinate')
    pan = g.e('Panner', speed_x=0.0, speed_y=-1.0)
    g.wire(uv0, pan, 'Coordinate')
    g.wire(g.mul(g.e('Time'), g.scalar('PanSpeed', 1.5)), pan, 'Time')
    noise = g.tex('BC', TEX_DIR + '/T_DF_FxNoise_BC', COLOR, pan)
    shape = g.one('OneMinus', g.mask(uv0, 'g'))  # brightest at the root (V = 0), gone at the tip
    k = g.mul(g.mul(g.mul((noise, 'R'), shape), g.scalar('Fade', 1.0)), 4.0)
    g.out(g.mul(g.mask(g.vector('Color', (1.0, 0.25, 0.05, 1)), 'rgb'), k), 'MP_EMISSIVE_COLOR')


def build_decal(g):
    bc = g.tex('BC', TEX_DIR + '/T_DF_Scorch_BC', COLOR)
    g.out((bc, 'RGB'), 'MP_BASE_COLOR')
    # Task 16 (spec 7.3): a scorch fades out over its life; DecalLifetimeOpacity is the decal component's SetFadeOut ramp
    # (1 for a decal that never fades, e.g. one placed in a level)
    g.out(g.mul(g.mul((bc, 'A'), g.scalar('Fade', 1.0)), g.e('DecalLifetimeOpacity')), 'MP_OPACITY')
    g.out(g.e('Constant', r=0.9), 'MP_ROUGHNESS')
    # Task 22 (Task 16's diagnosis): soot is dull; the default Specular 0.5 lifted the burn above a ground whose look is mostly
    # specular, so the scorch read lighter than the test level's ground
    g.out(g.e('Constant', r=DECAL_SPECULAR), 'MP_SPECULAR')


def build_icon(g):
    icon = g.tex('Icon', WHITE, COLOR)
    g.out(g.mul((icon, 'RGB'), g.mask(g.vector('Color', (1, 1, 1, 1)), 'rgb')), 'MP_EMISSIVE_COLOR')
    g.out((icon, 'A'), 'MP_OPACITY_MASK')


BM, SM, MD = U.BlendMode, U.MaterialShadingModel, U.MaterialDomain
LIT_MESH = dict(used_with_instanced_static_meshes=True, used_with_skeletal_mesh=True)
MASTERS = {  # name: (builder, material properties)
    'M_DF_Surface': (build_surface, LIT_MESH),
    'M_DF_CarPaint': (build_car_paint, LIT_MESH),
    'M_DF_Road': (build_road, dict(used_with_instanced_static_meshes=True, used_with_spline_meshes=True)),
    'M_DF_Terrain': (build_terrain, {}),
    'M_DF_FxAdditive': (build_fx_additive, dict(blend_mode=BM.BLEND_ADDITIVE, shading_model=SM.MSM_UNLIT, two_sided=True)),
    'M_DF_FxSmoke': (build_fx_smoke, dict(blend_mode=BM.BLEND_TRANSLUCENT, two_sided=True)),
    'M_DF_FxFlame': (build_fx_flame, dict(blend_mode=BM.BLEND_ADDITIVE, shading_model=SM.MSM_UNLIT, two_sided=True)),
    'M_DF_Decal': (build_decal, dict(material_domain=MD.MD_DEFERRED_DECAL, blend_mode=BM.BLEND_TRANSLUCENT,
                                     decal_blend_mode=U.DecalBlendMode.DBM_TRANSLUCENT)),
    'M_DF_Icon': (build_icon, dict(blend_mode=BM.BLEND_MASKED, shading_model=SM.MSM_UNLIT, two_sided=True)),
}
DEFAULTS = dict(material_domain=MD.MD_SURFACE, blend_mode=BM.BLEND_OPAQUE, shading_model=SM.MSM_DEFAULT_LIT, two_sided=False)


def build_master(name, asset_path):
    builder, props = MASTERS[name]
    folder = asset_path.rsplit('/', 1)[0]
    mat = eal.load_asset(asset_path) if eal.does_asset_exist(asset_path) else None
    if mat is None:
        mat = unreal.AssetToolsHelpers.get_asset_tools().create_asset(name, folder, U.Material, U.MaterialFactoryNew())
    else:
        MEL.delete_all_material_expressions(mat)
    settings = dict(DEFAULTS, **props)
    for k in sorted(settings, key=lambda k: k == 'material_domain'):  # the domain last: a decal domain needs its blend mode first
        mat.set_editor_property(k, settings[k])
    builder(Graph(mat))
    MEL.layout_material_expressions(mat)
    MEL.recompile_material(mat)
    eal.save_asset(asset_path, only_if_is_dirty=False)
    return mat


def build_instance(e):
    path = e['asset_path']
    folder = path.rsplit('/', 1)[0]
    mi = eal.load_asset(path) if eal.does_asset_exist(path) else None
    if mi is None:
        mi = unreal.AssetToolsHelpers.get_asset_tools().create_asset(e['name'], folder, U.MaterialInstanceConstant,
                                                                     U.MaterialInstanceConstantFactoryNew())
    MEL.set_material_instance_parent(mi, _load('%s/%s' % (MAT_DIR, e['parent'])))
    MEL.clear_all_material_instance_parameters(mi)
    # UE 4.27's set_material_instance_*_parameter_value return False even when they set the value: read each one back
    bad = []
    for p, v in e['scalars'].items():
        MEL.set_material_instance_scalar_parameter_value(mi, p, float(v))
        if abs(MEL.get_material_instance_scalar_parameter_value(mi, p) - float(v)) > 1e-4:
            bad.append(p)
    for p, v in e['vectors'].items():
        MEL.set_material_instance_vector_parameter_value(mi, p, U.LinearColor(*[float(c) for c in v]))
        c = MEL.get_material_instance_vector_parameter_value(mi, p)
        if any(abs(a - float(b)) > 1e-4 for a, b in zip((c.r, c.g, c.b, c.a), v)):
            bad.append(p)
    for p, t in e['textures'].items():
        tex = _load('%s/%s' % (TERRAIN_DIR if t.startswith('T_DF_Splat_') else TEX_DIR, t))  # catalog.asset_path's folders
        MEL.set_material_instance_texture_parameter_value(mi, p, tex)
        if MEL.get_material_instance_texture_parameter_value(mi, p) != tex:
            bad.append(p)
    if bad:
        raise RuntimeError('%s: parameter(s) %s did not take on parent %s' % (e['name'], ', '.join(bad), e['parent']))
    MEL.update_material_instance(mi)
    eal.save_asset(path, only_if_is_dirty=False)
    return mi


def assign_mesh_slots(cat):
    """Gives every imported catalogue mesh its slot instances (by slot name, else order); returns slots assigned."""
    n = 0
    for e in cat['meshes']:
        if not eal.does_asset_exist(e['asset_path']):
            continue
        mesh = eal.load_asset(e['asset_path'])
        changed = False
        for i, sm in enumerate(list(mesh.get_editor_property('static_materials'))):
            slot_name = str(sm.get_editor_property('material_slot_name'))
            mi_name = slot_name if slot_name in e['slots'] else (e['slots'][i] if i < len(e['slots']) else None)
            path = '%s/%s' % (MAT_DIR, mi_name)
            if mi_name is None or not eal.does_asset_exist(path):
                continue
            have = sm.get_editor_property('material_interface')
            if have is None or have.get_name() != mi_name:
                mesh.set_material(i, eal.load_asset(path))
                changed = True
                n += 1
        if changed:
            eal.save_asset(e['asset_path'], only_if_is_dirty=False)
    return n


def build_materials(art_dir, only=None):
    if len(unreal.EditorLevelLibrary.get_pie_worlds(False)) > 0:
        raise RuntimeError('a Play-In-Editor session is running (editor scripting is disabled during play); stop it first')
    if isinstance(only, str):
        only = [only]
    with open(os.path.join(art_dir, 'catalog.json'), encoding='utf-8') as f:
        cat = json.load(f)
    masters = 0
    for m in cat['masters']:
        if not only or m['name'] in only:
            build_master(m['name'], m['asset_path'])
            masters += 1
    instances = 0
    for e in cat['materials']:
        if not only or e['name'] in only or e['parent'] in only:
            build_instance(e)
            instances += 1
    slots = assign_mesh_slots(cat)
    print('MATERIALS OK: %d masters, %d instances' % (masters, instances))
    if slots:
        print('(%d mesh material slots assigned)' % slots)
    return True
