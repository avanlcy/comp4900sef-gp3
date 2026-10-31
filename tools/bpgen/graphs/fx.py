"""Phase 7 effects (plan docs/superpowers/plans/2026-10-30-phase7-art-feel.md). Task 10: the two camera shakes (spec §5.3).
Task 15: the BP_DFFx effect family (spec §7.1).

BP_DFShakeLight: landing after more than 0.5 s airborne, a hit taken (vehicle and on foot); later tasks add a crash and a tyre
pop. BP_DFShakeHeavy: an explosion nearby (Task 16, PlayWorldCameraShake scaled by distance). Both are MatineeCameraShake
children with class defaults only (oscillation amplitudes in degrees / cm, frequencies in Hz).

BP_DFFx is a short-lived, mesh-shell effect actor (no Cascade or Niagara). Its static mesh components tagged FxShell grow
from StartScale to EndScale (eased out: lerp by 1 - (1 - t)^2, t = Age / Lifetime) and fade: each shell's material
instance gets Fade = (1 - t)^FadeExponent. The actor rises at RiseSpeed cm/s, an optional PointLight (the child's "Flash")
dims from LightStart to 0, and the actor destroys itself once its Age reaches Lifetime + 0.1 s (SetLifeSpan(Lifetime + 0.1)
at BeginPlay is the backstop for an actor that stops ticking). Tint multiplies every shell's material
Color (Color = Tint x the instance's Color). The seven children only add their shells (and the explosion its light) and
set the values; BP_DFFxTracer adds SetEnds. Callers: Tasks 16-17 (df.spawn_fx spawns one, tinted or not).
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from df import BP_SHAKE_HEAVY, BP_SHAKE_LIGHT, MATINEE_SHAKE, OUT, Blueprint  # noqa: E402
from df import (ACTOR, ACTOR_COMP, BOOL, BP_FX, BP_FX_EXPLOSION, BP_FX_IMPACT, BP_FX_LOOT_BURST, BP_FX_MUZZLE,  # noqa: E402
                BP_FX_PUFF, BP_FX_SPARKS, BP_FX_TRACER, CLASS, FLOAT, FX_SHELL_TAG, HIT_RESULT, INT, LINEAR_COLOR, MATH,
                MATERIAL_INTERFACE, MID, NAME, NO_COLLISION, OBJECT, POINT_LIGHT_COMP, PRIMITIVE, ROTATOR, SCENE_COMP,
                STATIC_MESH_COMP, STRUCT, VECTOR, Graph, Pin, art_fx, art_material, cls_ref, compare, is_valid, obj_pin,
                struct_pin, struct_ref)

# (asset, description, {dotted class default: value}) -- the plan's values, verbatim
SHAKES = [
    (BP_SHAKE_LIGHT, "Light camera shake: a landing after more than 0.5 s in the air, a hit taken.",
     {"OscillationDuration": 0.25,
      "RotOscillation.Pitch.Amplitude": 1.5, "RotOscillation.Pitch.Frequency": 30.0,
      "RotOscillation.Yaw.Amplitude": 1.0, "RotOscillation.Yaw.Frequency": 25.0}),
    (BP_SHAKE_HEAVY, "Heavy camera shake: an explosion nearby, scaled by distance.",
     {"OscillationDuration": 0.6,
      "RotOscillation.Pitch.Amplitude": 4.0, "RotOscillation.Pitch.Frequency": 20.0,
      "RotOscillation.Yaw.Amplitude": 3.0, "RotOscillation.Yaw.Frequency": 18.0,
      "LocOscillation.Z.Amplitude": 6.0, "LocOscillation.Z.Frequency": 15.0}),
]


def build_shakes() -> list:
    out = []
    for asset, description, defaults in SHAKES:
        bp = Blueprint(asset, parent=MATINEE_SHAKE, description=description)
        for name, value in defaults.items():
            bp.default(name, value)
        out.append(bp)
    return out


# ---- Task 15: the effect family (spec §7.1) ----
ARR = "KismetArrayLibrary"
LIGHT_COMP = "/Script/Engine.LightComponent"
WHITE = "(R=1.000000,G=1.000000,B=1.000000,A=1.000000)"
TUNE, STATE = "Dead Fire|Effect", "Dead Fire|Effect State"
# the tunables every effect has (spec §7.1 / plan Task 15 defaults); the children set their own
FX_DEFAULTS = {"Lifetime": 1.0, "StartScale": 0.3, "EndScale": 1.0, "FadeExponent": 1.5, "RiseSpeed": 0.0, "LightStart": 0.0}
# the untinted default, written as a class default on every apply (a declared default reaches the asset only on creation)
TINT_DEFAULT = {"color": [1.0, 1.0, 1.0, 1.0]}
LIFE_MARGIN_S = 0.1  # an effect lives until Age = Lifetime + this (SetLifeSpan(Lifetime + this) is the backstop)


def shell_elem():
    return Pin("e", OBJECT, sub_object=cls_ref(STATIC_MESH_COMP))


def mid_elem():
    return Pin("e", OBJECT, sub_object=cls_ref(MID))


def vec_elem():
    return Pin("e", STRUCT, sub_object=struct_ref(VECTOR))


def colour_elem():
    return Pin("e", STRUCT, sub_object=struct_ref(LINEAR_COLOR))


def var(g: Graph, name, cat=FLOAT, elem=None):
    """(node, pin) of a variable of this Blueprint; elem: the Pin of an array variable's element."""
    if elem is not None:
        return (g.var_get(name, elem.category, elem.sub_object, container="Array"), name)
    return (g.var_get(name, cat), name)


def fop(g: Graph, fn, a, b=None):
    """Pure KismetMathLibrary float op on (node, pin) sources or literal numbers (b None for a one-input op)."""
    ins = [Pin("A", FLOAT, default=None if isinstance(a, tuple) else "%f" % a)]
    if b is not None:
        ins.append(Pin("B", FLOAT, default=None if isinstance(b, tuple) else "%f" % b))
    n = g.call_static(MATH, fn, inputs=ins, outputs=[Pin("ReturnValue", FLOAT, "out")], pure=True)
    for name, src in (("A", a), ("B", b)):
        if isinstance(src, tuple):
            g.link(src[0], src[1], n, name)
    return (n, "ReturnValue")


def arr_get(g: Graph, name, elem, index_src):
    n = g.call_array(ARR, "Array_Get", elem, inputs=[Pin("Index", INT)], outputs=[Pin("Item", elem.category, "out", elem.sub_object)])
    g.link(*var(g, name, elem=elem), n, "TargetArray")
    g.link(index_src[0], index_src[1], n, "Index")
    return (n, "Item")


def arr_add(g: Graph, name, elem, item_src):
    """Impure Array_Add(the array variable `name`, item)."""
    n = g.call_array(ARR, "Array_Add", elem, inputs=[Pin("NewItem", elem.category, "in", elem.sub_object)],
                     outputs=[Pin("ReturnValue", INT, "out")], pure=False)
    g.link(*var(g, name, elem=elem), n, "TargetArray")
    g.link(item_src[0], item_src[1], n, "NewItem")
    return n


def relative_scale(g: Graph, comp_src):
    n = g.var_get_on(SCENE_COMP, "RelativeScale3D", STRUCT, struct_ref(VECTOR))
    g.link(comp_src[0], comp_src[1], n, "self")
    return (n, "RelativeScale3D")


def set_relative_scale(g: Graph, comp_src, scale_src):
    n = g.call_on(SCENE_COMP, "SetRelativeScale3D", inputs=[struct_pin("NewScale3D", VECTOR)])
    g.link(comp_src[0], comp_src[1], n, "self")
    g.link(scale_src[0], scale_src[1], n, "NewScale3D")
    return n


def with_x(g: Graph, vec_src, x_src):
    """MakeVector(x, vec.Y, vec.Z)."""
    brk = g.call_static(MATH, "BreakVector", inputs=[struct_pin("InVec", VECTOR)],
                        outputs=[Pin("X", FLOAT, "out"), Pin("Y", FLOAT, "out"), Pin("Z", FLOAT, "out")], pure=True)
    g.link(vec_src[0], vec_src[1], brk, "InVec")
    mk = g.call_static(MATH, "MakeVector", inputs=[Pin("X", FLOAT), Pin("Y", FLOAT), Pin("Z", FLOAT)],
                       outputs=[struct_pin("ReturnValue", VECTOR, "out")], pure=True)
    g.link(x_src[0], x_src[1], mk, "X")
    g.link(brk, "Y", mk, "Y")
    g.link(brk, "Z", mk, "Z")
    return (mk, "ReturnValue")


def build_fx() -> Blueprint:
    bp = Blueprint(BP_FX, parent=ACTOR, description="A short-lived mesh-shell effect (spec §7.1): its FxShell meshes grow and fade "
                   "over Lifetime, then it destroys itself. Children add the shells; Tint multiplies their colour.")
    bp.component("FxRoot", SCENE_COMP)  # the children's shells (root nodes of their own construction scripts) attach here
    bp.variable("Lifetime", "float", "1.0", TUNE, editable=True)
    bp.variable("StartScale", "float", "0.3", TUNE, editable=True)
    bp.variable("EndScale", "float", "1.0", TUNE, editable=True)
    bp.variable("FadeExponent", "float", "1.5", TUNE, editable=True)
    bp.variable("RiseSpeed", "float", "0.0", TUNE, editable=True)
    bp.variable("LightStart", "float", "0.0", TUNE, editable=True)
    bp.variable("Tint", "struct:" + LINEAR_COLOR, WHITE, TUNE, editable=True)
    for name, value in FX_DEFAULTS.items():
        bp.default(name, value)
    bp.default("Tint", TINT_DEFAULT)
    # internals, filled at BeginPlay: index i of each array belongs to the same shell
    bp.variable("Shells", "array<object:%s>" % STATIC_MESH_COMP, "", STATE)
    bp.variable("BaseScales", "array<struct:%s>" % VECTOR, "", STATE)  # each shell's relative scale as built
    bp.variable("MIDs", "array<object:%s>" % MID, "", STATE)
    bp.variable("BaseColors", "array<struct:%s>" % LINEAR_COLOR, "", STATE)  # each material instance's own Color
    bp.variable("FlashLight", "object:" + POINT_LIGHT_COMP, "", STATE)
    bp.variable("Age", "float", "0", STATE)

    g = bp.function("UpdateLook", doc="The look at the current Age: each shell's scale = its base x lerp(StartScale, EndScale, "
                    "1 - (1 - t)^2), each material's Fade = (1 - t)^FadeExponent, the flash light at LightStart x (1 - t); t = Age / Lifetime, clamped to 0..1.")
    ratio = fop(g, "Divide_FloatFloat", var(g, "Age"), fop(g, "FMax", var(g, "Lifetime"), 0.001))
    clamp = g.call_static(MATH, "FClamp", inputs=[Pin("Value", FLOAT), Pin("Min", FLOAT, default="0.0"), Pin("Max", FLOAT, default="1.0")],
                          outputs=[Pin("ReturnValue", FLOAT, "out")], pure=True)
    g.link(ratio[0], ratio[1], clamp, "Value")
    left = fop(g, "Subtract_FloatFloat", 1.0, (clamp, "ReturnValue"))  # 1 - t
    grow = fop(g, "Subtract_FloatFloat", 1.0, fop(g, "Multiply_FloatFloat", left, left))
    lerp = g.call_static(MATH, "Lerp", inputs=[Pin("A", FLOAT), Pin("B", FLOAT), Pin("Alpha", FLOAT)],
                         outputs=[Pin("ReturnValue", FLOAT, "out")], pure=True)
    g.link(*var(g, "StartScale"), lerp, "A")
    g.link(*var(g, "EndScale"), lerp, "B")
    g.link(grow[0], grow[1], lerp, "Alpha")
    shells = g.for_each(shell_elem())
    g.link(*var(g, "Shells", elem=shell_elem()), shells, "Array")
    g.link_entry("then", shells, "Exec")
    scaled = g.call_static(MATH, "Multiply_VectorFloat", inputs=[struct_pin("A", VECTOR), Pin("B", FLOAT)],
                           outputs=[struct_pin("ReturnValue", VECTOR, "out")], pure=True)
    g.link(*arr_get(g, "BaseScales", vec_elem(), (shells, "Array Index")), scaled, "A")
    g.link(lerp, "ReturnValue", scaled, "B")
    grow_shell = set_relative_scale(g, (shells, "Array Element"), (scaled, "ReturnValue"))
    g.link(shells, "LoopBody", grow_shell, "execute")
    mids = g.for_each(mid_elem())
    g.link(*var(g, "MIDs", elem=mid_elem()), mids, "Array")
    g.link(shells, "Completed", mids, "Exec")
    power = g.call_static(MATH, "MultiplyMultiply_FloatFloat", inputs=[Pin("Base", FLOAT), Pin("Exp", FLOAT)],
                          outputs=[Pin("ReturnValue", FLOAT, "out")], pure=True)
    g.link(left[0], left[1], power, "Base")
    g.link(*var(g, "FadeExponent"), power, "Exp")
    fade = g.call_on(MID, "SetScalarParameterValue", inputs=[Pin("ParameterName", NAME, default="Fade"), Pin("Value", FLOAT)])
    g.link(mids, "Array Element", fade, "self")
    g.link(power, "ReturnValue", fade, "Value")
    g.link(mids, "LoopBody", fade, "execute")
    has_light = is_valid(g)
    g.link(*(g.var_get("FlashLight", OBJECT, cls_ref(POINT_LIGHT_COMP)), "FlashLight"), has_light, "Object")
    lit = g.branch()
    g.link(has_light, "ReturnValue", lit, "Condition")
    g.link(mids, "Completed", lit, "execute")
    dim = g.call_on(LIGHT_COMP, "SetIntensity", inputs=[Pin("NewIntensity", FLOAT)])
    g.link(*(g.var_get("FlashLight", OBJECT, cls_ref(POINT_LIGHT_COMP)), "FlashLight"), dim, "self")
    g.link(*fop(g, "Multiply_FloatFloat", var(g, "LightStart"), left), dim, "NewIntensity")
    g.link(lit, "then", dim, "execute")

    g = bp.function("ApplyTint", doc="Each shell material's Color = Tint x the Color its material instance had (BaseColors).")
    loop = g.for_each(mid_elem())
    g.link(*var(g, "MIDs", elem=mid_elem()), loop, "Array")
    g.link_entry("then", loop, "Exec")
    mul = g.call_static(MATH, "Multiply_LinearColorLinearColor", inputs=[struct_pin("A", LINEAR_COLOR), struct_pin("B", LINEAR_COLOR)],
                        outputs=[struct_pin("ReturnValue", LINEAR_COLOR, "out")], pure=True)
    g.link(g.var_get("Tint", STRUCT, struct_ref(LINEAR_COLOR)), "Tint", mul, "A")
    g.link(*arr_get(g, "BaseColors", colour_elem(), (loop, "Array Index")), mul, "B")
    paint = g.call_on(MID, "SetVectorParameterValue", inputs=[Pin("ParameterName", NAME, default="Color"), struct_pin("Value", LINEAR_COLOR)])
    g.link(loop, "Array Element", paint, "self")
    g.link(mul, "ReturnValue", paint, "Value")
    g.link(loop, "LoopBody", paint, "execute")

    g = bp.function("SetTint", inputs=["Color:struct:" + LINEAR_COLOR],
                    doc="Tint := Color, and re-tints the shells when BeginPlay has made their materials: call it right after the spawn (df.spawn_fx).")
    st = g.var_set("Tint", STRUCT, sub_object=struct_ref(LINEAR_COLOR))
    g.link_entry("Color", st, "Tint")
    g.link_entry("then", st, "execute")
    g.exec(st, g.call_self("ApplyTint"))

    g = bp.event_graph()
    g.section("Begin Play: gather the FxShell meshes, give each its own material instance and remember its scale and colour, "
              "then the flash light, the life span, the tint and the look at t = 0")
    ev = g.begin_play()
    tagged = g.call_self_native(ACTOR, "GetComponentsByTag",
                                inputs=[Pin("ComponentClass", CLASS, sub_object=cls_ref(ACTOR_COMP), default_object=STATIC_MESH_COMP),
                                        Pin("Tag", NAME, default=FX_SHELL_TAG)],
                                outputs=[Pin("ReturnValue", OBJECT, "out", cls_ref(STATIC_MESH_COMP), container="Array")], pure=True)
    loop = g.for_each(shell_elem())
    g.link(tagged, "ReturnValue", loop, "Array")
    g.link(ev, "then", loop, "Exec")
    shell = (loop, "Array Element")
    add_shell = arr_add(g, "Shells", shell_elem(), shell)
    g.link(loop, "LoopBody", add_shell, "execute")
    add_base = arr_add(g, "BaseScales", vec_elem(), relative_scale(g, shell))
    make = g.call_on(PRIMITIVE, "CreateDynamicMaterialInstance",
                     inputs=[Pin("ElementIndex", INT, default="0"), obj_pin("SourceMaterial", MATERIAL_INTERFACE), Pin("OptionalName", NAME, default="None")],
                     outputs=[obj_pin("ReturnValue", MID, "out")])
    g.link(shell[0], shell[1], make, "self")
    add_mid = arr_add(g, "MIDs", mid_elem(), (make, "ReturnValue"))
    colour = g.call_on(MID, "K2_GetVectorParameterValue", inputs=[Pin("ParameterName", NAME, default="Color")],
                       outputs=[struct_pin("ReturnValue", LINEAR_COLOR, "out")])
    g.link(make, "ReturnValue", colour, "self")
    add_colour = arr_add(g, "BaseColors", colour_elem(), (colour, "ReturnValue"))
    g.exec(add_shell, add_base, make, add_mid, colour, add_colour)
    light = g.call_self_native(ACTOR, "GetComponentByClass",
                               inputs=[Pin("ComponentClass", CLASS, sub_object=cls_ref(ACTOR_COMP), default_object=POINT_LIGHT_COMP)],
                               outputs=[obj_pin("ReturnValue", POINT_LIGHT_COMP, "out")], pure=True)
    keep_light = g.var_set("FlashLight", OBJECT, sub_object=cls_ref(POINT_LIGHT_COMP))
    g.link(light, "ReturnValue", keep_light, "FlashLight")
    g.link(loop, "Completed", keep_light, "execute")
    span = g.call_self_native(ACTOR, "SetLifeSpan", inputs=[Pin("InLifespan", FLOAT)])
    g.link(*fop(g, "Add_FloatFloat", var(g, "Lifetime"), LIFE_MARGIN_S), span, "InLifespan")
    g.exec(keep_light, span, g.call_self("ApplyTint"), g.call_self("UpdateLook"))

    g.section("Tick: older by DeltaSeconds, up by RiseSpeed, the look at the new age, and gone once Age reaches Lifetime + 0.1 s "
              "(the life span timer is only the backstop: headless, it ran about 25 % behind the ticks' DeltaSeconds)")
    tk = g.tick()
    older = g.var_set("Age", FLOAT)
    g.link(*fop(g, "Add_FloatFloat", var(g, "Age"), (tk, "DeltaSeconds")), older, "Age")
    g.link(tk, "then", older, "execute")
    up = g.call_static(MATH, "MakeVector", inputs=[Pin("X", FLOAT, default="0.0"), Pin("Y", FLOAT, default="0.0"), Pin("Z", FLOAT)],
                       outputs=[struct_pin("ReturnValue", VECTOR, "out")], pure=True)
    g.link(*fop(g, "Multiply_FloatFloat", var(g, "RiseSpeed"), (tk, "DeltaSeconds")), up, "Z")
    rise = g.call_self_native(ACTOR, "K2_AddActorWorldOffset",
                              inputs=[struct_pin("DeltaLocation", VECTOR), Pin("bSweep", BOOL, default="false"), Pin("bTeleport", BOOL, default="false")],
                              outputs=[struct_pin("SweepHitResult", HIT_RESULT, "out")])
    g.link(up, "ReturnValue", rise, "DeltaLocation")
    look = g.call_self("UpdateLook")
    g.exec(older, rise, look)
    done = compare(g, "GreaterEqual_FloatFloat", FLOAT)
    g.link(*var(g, "Age"), done, "A")
    g.link(*fop(g, "Add_FloatFloat", var(g, "Lifetime"), LIFE_MARGIN_S), done, "B")
    over = g.branch()
    g.link(done, "ReturnValue", over, "Condition")
    g.exec(look, over)
    g.link(over, "then", g.call_self_native(ACTOR, "K2_DestroyActor"), "execute")
    return bp


class Shell:
    """One FxShell component of an effect: a catalogue shell mesh (100 cm across, Art/Fx), the material instance it wears
    (None: the mesh's own MI_DF_FxFlash), and its transform (location cm, rotation pitch/yaw/roll, scale = size in metres).
    sort: translucency sort priority (higher draws later, on top: the additive fire over the smoke)."""

    def __init__(self, name, mesh, mi=None, at=(0.0, 0.0, 0.0), scale=(1.0, 1.0, 1.0), rot=None, sort=0):
        self.name, self.mesh, self.mi, self.at, self.scale, self.rot, self.sort = name, mesh, mi, at, scale, rot, sort

    def props(self):
        p = dict(static_mesh=art_fx(self.mesh), component_tags=[FX_SHELL_TAG], cast_shadow=False,
                 relative_location={"vector": list(self.at)}, relative_scale3d={"vector": list(self.scale)}, **NO_COLLISION)
        if self.rot:
            p["relative_rotation"] = {"rotator": dict(zip(("pitch", "yaw", "roll"), self.rot))}
        if self.mi:
            p["override_materials"] = [art_material(self.mi)]
        if self.sort:
            p["translucency_sort_priority"] = self.sort
        return p


def size(m):
    return (m, m, m)


# Each child: (asset, description, values, shells, flash light). The values are within spec §7.1's lifetimes; the shells
# and sizes are the look (plan Task 15: the implementer's call), checked in the look-dev capture (shots.py FT_DFShot_Fx).
# +X is the effect's direction where it has one (the shot, the surface normal); the explosion's centre sits on the ground.
CHILDREN = [
    (BP_FX_MUZZLE, "Muzzle flash at a gun's muzzle, +X along the shot: a squashed yellow star and a slim, hot blast cone.",
     dict(Lifetime=0.06, StartScale=0.6, EndScale=1.0, FadeExponent=1.0),
     [Shell("Star", "SM_DF_FxStar", "MI_DF_FxTracer", at=(6.0, 0.0, 0.0), scale=(0.25, 0.55, 0.55)),
      Shell("Blast", "SM_DF_FxCone", "MI_DF_FxSpark", scale=(0.5, 0.22, 0.22))], None),
    (BP_FX_TRACER, "A hitscan shot's tracer: SetEnds(Start, End) stands the yellow beam at Start, aims it at End and stretches it.",
     dict(Lifetime=0.08, StartScale=1.0, EndScale=1.0, FadeExponent=1.0),  # no growth: X is the shot's length
     [Shell("Beam", "SM_DF_FxBeam", "MI_DF_FxTracer", scale=(1.0, 0.6, 0.6))], None),
    (BP_FX_IMPACT, "A hitscan hit, +X along the surface normal: a hot spark star and a spray of dust thrown off the surface.",
     dict(Lifetime=0.3, StartScale=0.3, EndScale=1.0, FadeExponent=1.5),
     [Shell("Burst", "SM_DF_FxStar", "MI_DF_FxSpark", scale=size(0.45)),
      Shell("Dust", "SM_DF_FxCone", "MI_DF_FxDust", scale=(1.2, 0.9, 0.9))], None),
    (BP_FX_EXPLOSION, "An explosion on the ground (SpawnExplosion): a white-hot core in an orange fireball, dark smoke rising behind "
     "it, an orange shockwave ring, burning debris flying out and an orange flash of light.",
     dict(Lifetime=1.2, StartScale=0.3, EndScale=1.0, FadeExponent=1.5, LightStart=50000.0),
     [Shell("Smoke", "SM_DF_FxSphere", "MI_DF_FxSmoke", at=(0.0, 0.0, 200.0), scale=size(5.5), sort=-1),
      Shell("SmokeTop", "SM_DF_FxSphere", "MI_DF_FxSmoke", at=(-60.0, 50.0, 380.0), scale=size(4.0), sort=-1),
      Shell("Fireball", "SM_DF_FxSphere", "MI_DF_FxBlast", at=(0.0, 0.0, 80.0), scale=size(5.0), sort=1),
      Shell("Core", "SM_DF_FxSphere", at=(0.0, 0.0, 80.0), scale=size(2.6), sort=2),
      Shell("Shockwave", "SM_DF_FxRing", "MI_DF_FxBlast", at=(0.0, 0.0, 10.0), scale=(10.0, 10.0, 3.0), sort=1),
      Shell("Debris", "SM_DF_FxChunk", "MI_DF_FxBlast", at=(0.0, 0.0, 40.0), scale=size(6.0), sort=1)],
     dict(at=(0.0, 0.0, 150.0), radius=2500.0, colour=(1.0, 0.55, 0.25, 1.0))),
    (BP_FX_PUFF, "A puff of smoke that rises (rocket trail, tyre smoke, wreck smoke): three light ash-grey balls; tint it darker for a wreck.",
     dict(Lifetime=1.2, StartScale=0.3, EndScale=1.0, FadeExponent=1.0, RiseSpeed=80.0),
     [Shell("Puff", "SM_DF_FxSphere", "MI_DF_FxPuff", scale=size(1.1)),
      Shell("PuffSide", "SM_DF_FxSphere", "MI_DF_FxPuff", at=(15.0, 35.0, 25.0), scale=size(0.8)),
      Shell("PuffTop", "SM_DF_FxSphere", "MI_DF_FxPuff", at=(-20.0, -25.0, 40.0), scale=size(0.7))], None),
    (BP_FX_LOOT_BURST, "A crate opening: a ring, a star and bits in white MI_DF_FxBurst; spawn it tinted with the item's colour (df.spawn_fx).",
     dict(Lifetime=0.6, StartScale=0.3, EndScale=1.0, FadeExponent=1.0),
     [Shell("Ring", "SM_DF_FxRing", "MI_DF_FxBurst", at=(0.0, 0.0, 15.0), scale=(3.0, 3.0, 2.0)),
      Shell("Star", "SM_DF_FxStar", "MI_DF_FxBurst", at=(0.0, 0.0, 90.0), scale=size(1.4)),
      Shell("Bits", "SM_DF_FxChunk", "MI_DF_FxBurst", at=(0.0, 0.0, 40.0), scale=size(2.4))], None),
    (BP_FX_SPARKS, "Sparks (tyre pop, car-on-car crash): a hot yellow spiky star and small orange bits flying out.",
     dict(Lifetime=0.25, StartScale=0.3, EndScale=1.0, FadeExponent=1.0),
     [Shell("Star", "SM_DF_FxStar", "MI_DF_FxTracer", scale=size(0.8)),
      Shell("Bits", "SM_DF_FxChunk", "MI_DF_FxBlast", scale=size(1.2))], None),
]


def add_set_ends(bp: Blueprint) -> None:
    """BP_DFFxTracer.SetEnds(Start, End): at Start, aimed at End, Beam's X scale = |End - Start| / 100 (SM_DF_FxBeam is
    100 cm along +X). After BeginPlay the beam's BaseScales entry changes too and the look is re-applied, so Tick keeps
    the new length; before BeginPlay only the component changes, and BeginPlay takes it as the base."""
    g = bp.function("SetEnds", inputs=["Start:struct:" + VECTOR, "End:struct:" + VECTOR],
                    doc="Stands the tracer at Start, aims it at End and stretches the beam to |End - Start|.")
    move = g.call_self_native(ACTOR, "K2_SetActorLocation",
                              inputs=[struct_pin("NewLocation", VECTOR), Pin("bSweep", BOOL, default="false"), Pin("bTeleport", BOOL, default="true")],
                              outputs=[struct_pin("SweepHitResult", HIT_RESULT, "out"), Pin("ReturnValue", BOOL, "out")])
    g.link_entry("Start", move, "NewLocation")
    g.link_entry("then", move, "execute")
    look = g.call_static(MATH, "FindLookAtRotation", inputs=[struct_pin("Start", VECTOR), struct_pin("Target", VECTOR)],
                         outputs=[struct_pin("ReturnValue", ROTATOR, "out")], pure=True)
    g.link_entry("Start", look, "Start")
    g.link_entry("End", look, "Target")
    aim = g.call_self_native(ACTOR, "K2_SetActorRotation", inputs=[struct_pin("NewRotation", ROTATOR), Pin("bTeleportPhysics", BOOL, default="false")],
                             outputs=[Pin("ReturnValue", BOOL, "out")])
    g.link(look, "ReturnValue", aim, "NewRotation")
    g.exec(move, aim)
    dist = g.call_static(MATH, "Vector_Distance", inputs=[struct_pin("V1", VECTOR), struct_pin("V2", VECTOR)],
                         outputs=[Pin("ReturnValue", FLOAT, "out")], pure=True)
    g.link_entry("Start", dist, "V1")
    g.link_entry("End", dist, "V2")
    length = fop(g, "Divide_FloatFloat", (dist, "ReturnValue"), 100.0)
    beam = (g.var_get("Beam", OBJECT, cls_ref(STATIC_MESH_COMP)), "Beam")
    find = g.call_array(ARR, "Array_Find", shell_elem(), inputs=[Pin("ItemToFind", OBJECT, sub_object=cls_ref(STATIC_MESH_COMP))],
                        outputs=[Pin("ReturnValue", INT, "out")])
    g.link(*var(g, "Shells", elem=shell_elem()), find, "TargetArray")
    g.link(beam[0], beam[1], find, "ItemToFind")
    known = compare(g, "GreaterEqual_IntInt", INT, b="0")
    g.link(find, "ReturnValue", known, "A")
    b = g.branch()
    g.link(known, "ReturnValue", b, "Condition")
    g.exec(aim, b)
    base = g.call_array(ARR, "Array_Set", vec_elem(), inputs=[Pin("Index", INT), struct_pin("Item", VECTOR), Pin("bSizeToFit", BOOL, default="false")],
                        pure=False)
    g.link(*var(g, "BaseScales", elem=vec_elem()), base, "TargetArray")
    g.link(find, "ReturnValue", base, "Index")
    g.link(*with_x(g, arr_get(g, "BaseScales", vec_elem(), (find, "ReturnValue")), length), base, "Item")
    g.link(b, "then", base, "execute")
    g.exec(base, g.call_self("UpdateLook"))
    stretch = set_relative_scale(g, beam, with_x(g, relative_scale(g, beam), length))
    g.link(b, "else", stretch, "execute")


def build_children() -> list:
    out = []
    for asset, description, values, shells, light in CHILDREN:
        child = Blueprint(asset, parent=BP_FX, description=description)
        for sh in shells:
            child.component(sh.name, STATIC_MESH_COMP, **sh.props())
        if light:
            child.component("Flash", POINT_LIGHT_COMP, intensity_units={"enum": "LightUnits.UNITLESS"}, intensity=0.0,
                            attenuation_radius=light["radius"], cast_shadows=False, relative_location={"vector": list(light["at"])},
                            **{"call:set_light_color": {"color": list(light["colour"])}})
        for name in FX_DEFAULTS:
            child.default(name, float(values.get(name, FX_DEFAULTS[name])))
        child.default("Tint", TINT_DEFAULT)
        if asset == BP_FX_TRACER:
            add_set_ends(child)
        out.append(child)
    return out


def build_all() -> list:
    return build_shakes() + [build_fx()] + build_children()


if __name__ == "__main__":
    for b in build_all():
        print(b.write(OUT))
