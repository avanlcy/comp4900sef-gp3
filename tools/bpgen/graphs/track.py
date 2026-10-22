"""BP_DFTrackSpline (plan Task 6): closed spline whose construction script lays road slabs (and optional barriers)
along it in pieces of about PieceLength, plus progress / lateral-distance queries for checkpoints, AI and the
off-track timer. Same algorithm as the Phase 1 C++ ADFTrackSpline::RebuildTrack.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from df import (BOOL, BP_TRACK, FLOAT, INT, MATH, OBJECT, OUT, SPACE, SPLINE_COMP, SPLINE_MESH_COMP, STRUCT,  # noqa: E402
                TRANSFORM, VECTOR, Blueprint, Graph, Node, Pin, and_bool, cls_ref, compare, math2, native_enum_pin,
                struct_pin)

V2D = "/Script/CoreUObject.Vector2D"
STATIC_MESH = "/Script/Engine.StaticMesh"
MATERIAL = "/Script/Engine.MaterialInterface"
STATIC_MESH_COMP = "/Script/Engine.StaticMeshComponent"


def spline(g: Graph) -> Node:
    return g.var_get("Spline", OBJECT, cls_ref(SPLINE_COMP))


def spline_call(g: Graph, fn, inputs=None, outputs=None, pure=True, **defaults) -> Node:
    s = spline(g)
    n = g.call_on(SPLINE_COMP, fn, inputs=inputs, outputs=outputs, pure=pure, **defaults)
    g.link(s, "Spline", n, "self")
    return n


def vec2(g: Graph, x_src=None, y_src=None, x="0.0", y="0.0") -> Node:
    """MakeVector2D; x_src / y_src are (node, pin) tuples or None for the literal default."""
    n = g.call_static(MATH, "MakeVector2D", inputs=[Pin("X", FLOAT, default=x), Pin("Y", FLOAT, default=y)],
                      outputs=[struct_pin("ReturnValue", V2D, "out")], pure=True)
    if x_src:
        g.link(x_src[0], x_src[1], n, "X")
    if y_src:
        g.link(y_src[0], y_src[1], n, "Y")
    return n


def div(g: Graph, a_src, b_src) -> Node:
    n = math2(g, "Divide_FloatFloat", FLOAT)
    g.link(a_src[0], a_src[1], n, "A")
    g.link(b_src[0], b_src[1], n, "B")
    return n


def mul(g: Graph, a_src, b=None, b_src=None) -> Node:
    n = math2(g, "Multiply_FloatFloat", FLOAT, b=b)
    g.link(a_src[0], a_src[1], n, "A")
    if b_src:
        g.link(b_src[0], b_src[1], n, "B")
    return n


def add_piece(g: Graph, prev, s_src, e_src, mesh_var: str, material_var: str, offset: Node, scale: Node):
    """Inline chain: one SplineMeshComponent from distance s to e. prev = (node, exec pin). Returns the last node."""
    length = math2(g, "Subtract_FloatFloat", FLOAT)
    g.link(e_src[0], e_src[1], length, "A")
    g.link(s_src[0], s_src[1], length, "B")

    def at(fn, d_src):
        n = spline_call(g, fn, inputs=[Pin("Distance", FLOAT), native_enum_pin("CoordinateSpace", SPACE, "Local")],
                        outputs=[struct_pin("ReturnValue", VECTOR, "out")])
        g.link(d_src[0], d_src[1], n, "Distance")
        return n

    def tangent(d_src):
        d = at("GetDirectionAtDistanceAlongSpline", d_src)
        t = g.call_static(MATH, "Multiply_VectorFloat", inputs=[struct_pin("A", VECTOR), Pin("B", FLOAT)],
                          outputs=[struct_pin("ReturnValue", VECTOR, "out")], pure=True)
        g.link(d, "ReturnValue", t, "A")
        g.link(length, "ReturnValue", t, "B")
        return t

    sl, el = at("GetLocationAtDistanceAlongSpline", s_src), at("GetLocationAtDistanceAlongSpline", e_src)
    st, et = tangent(s_src), tangent(e_src)

    add = g.add_component_by_class(SPLINE_MESH_COMP)
    g.link(prev[0], prev[1], add, "execute")

    def on_piece(owner, fn, inputs, **defaults):
        n = g.call_on(owner, fn, inputs=inputs, **defaults)
        g.link(add, "ReturnValue", n, "self")
        return n

    mesh = g.var_get(mesh_var, OBJECT, cls_ref(STATIC_MESH))
    set_mesh = on_piece(STATIC_MESH_COMP, "SetStaticMesh", [Pin("NewMesh", OBJECT, sub_object=cls_ref(STATIC_MESH))])
    set_mesh.pins.append(Pin("ReturnValue", BOOL, "out"))
    g.link(mesh, mesh_var, set_mesh, "NewMesh")
    mat = g.var_get(material_var, OBJECT, cls_ref(MATERIAL))
    set_mat = on_piece("/Script/Engine.PrimitiveComponent", "SetMaterial",
                       [Pin("ElementIndex", INT, default="0"), Pin("Material", OBJECT, sub_object=cls_ref(MATERIAL))])
    g.link(mat, material_var, set_mat, "Material")
    se = on_piece(SPLINE_MESH_COMP, "SetStartAndEnd",
                  [struct_pin("StartPos", VECTOR), struct_pin("StartTangent", VECTOR), struct_pin("EndPos", VECTOR),
                   struct_pin("EndTangent", VECTOR), Pin("bUpdateMesh", BOOL, default="false")])
    g.link(sl, "ReturnValue", se, "StartPos")
    g.link(st, "ReturnValue", se, "StartTangent")
    g.link(el, "ReturnValue", se, "EndPos")
    g.link(et, "ReturnValue", se, "EndTangent")
    chain = [add, set_mesh, set_mat, se]
    for fn, pin, src in (("SetStartScale", "StartScale", scale), ("SetEndScale", "EndScale", scale),
                         ("SetStartOffset", "StartOffset", offset), ("SetEndOffset", "EndOffset", offset)):
        n = on_piece(SPLINE_MESH_COMP, fn, [struct_pin(pin, V2D), Pin("bUpdateMesh", BOOL, default="true" if fn == "SetEndOffset" else "false")])
        g.link(src, "ReturnValue", n, pin)
        chain.append(n)
    col = on_piece("/Script/Engine.PrimitiveComponent", "SetCollisionProfileName",
                   [Pin("InCollisionProfileName", "name", default="BlockAll"), Pin("bUpdateOverlaps", BOOL, default="true")])
    chain.append(col)
    cnt = g.var_get("GeneratedMeshCount", INT)
    inc = math2(g, "Add_IntInt", INT, b="1")
    g.link(cnt, "GeneratedMeshCount", inc, "A")
    setc = g.var_set("GeneratedMeshCount", INT)
    g.link(inc, "ReturnValue", setc, "GeneratedMeshCount")
    chain.append(setc)
    for a, b in zip(chain, chain[1:]):
        g.link(a, "then", b, "execute")
    return setc


def build() -> Blueprint:
    bp = Blueprint(BP_TRACK, parent="/Script/Engine.Actor")
    bp.component("Spline", SPLINE_COMP, closed_loop=True)
    T = "Dead Fire|Track"
    bp.variable("bIsMainTrack", "bool", "true", T, editable=True)
    bp.variable("RoadMesh", "object:" + STATIC_MESH, "", T, editable=True)
    bp.variable("RoadMaterial", "object:" + MATERIAL, "", T, editable=True)
    bp.variable("RoadWidth", "float", "1400", T, editable=True)
    bp.variable("RoadThickness", "float", "20", T, editable=True)
    bp.variable("PieceLength", "float", "1000", T, editable=True)
    bp.variable("bGenerateBarriers", "bool", "false", T, editable=True)
    bp.variable("BarrierMesh", "object:" + STATIC_MESH, "", T, editable=True)
    bp.variable("BarrierMaterial", "object:" + MATERIAL, "", T, editable=True)
    bp.variable("BarrierHeight", "float", "80", T, editable=True)
    bp.variable("BarrierThickness", "float", "30", T, editable=True)
    bp.variable("MeshNativeSize", "float", "100", T, editable=True)
    I = "Dead Fire|Track|Generated"
    bp.variable("SegmentCount", "int", "0", I)
    bp.variable("GeneratedMeshCount", "int", "0", I)
    bp.variable("PieceStep", "float", "0", I)
    bp.default("RoadMesh", "/Engine/BasicShapes/Cube")
    bp.default("BarrierMesh", "/Engine/BasicShapes/Cube")
    bp.default("RoadMaterial", "/Game/VehicleAdv/Materials/MaterialInstances/BlackGrid")
    bp.default("BarrierMaterial", "/Game/VehicleAdv/Materials/MaterialInstances/SolidOrange")

    # ---- queries ----
    g = bp.function("GetSegmentCount", outputs=["Count:int"], pure=True)
    v = g.var_get("SegmentCount", INT)
    g.link_result(v, "SegmentCount", "Count")
    g.link_entry("then", "result", "execute")

    g = bp.function("GetGeneratedMeshCount", outputs=["Count:int"], pure=True)
    v = g.var_get("GeneratedMeshCount", INT)
    g.link_result(v, "GeneratedMeshCount", "Count")
    g.link_entry("then", "result", "execute")

    g = bp.function("GetTrackLength", outputs=["Length:float"], pure=True)
    n = spline_call(g, "GetSplineLength", outputs=[Pin("ReturnValue", FLOAT, "out")])
    g.link_result(n, "ReturnValue", "Length")
    g.link_entry("then", "result", "execute")

    g = bp.function("GetDistanceAlongTrack", inputs=["WorldLocation:struct:" + VECTOR], outputs=["Distance:float"], pure=True)
    key = spline_call(g, "FindInputKeyClosestToWorldLocation", inputs=[struct_pin("WorldLocation", VECTOR)],
                      outputs=[Pin("ReturnValue", FLOAT, "out")])
    g.link_entry("WorldLocation", key, "WorldLocation")
    d = spline_call(g, "GetDistanceAlongSplineAtSplineInputKey", inputs=[Pin("InKey", FLOAT)], outputs=[Pin("ReturnValue", FLOAT, "out")])
    g.link(key, "ReturnValue", d, "InKey")
    g.link_result(d, "ReturnValue", "Distance")
    g.link_entry("then", "result", "execute")

    g = bp.function("GetLateralDistanceFromTrack", inputs=["WorldLocation:struct:" + VECTOR], outputs=["Distance:float"], pure=True)
    p = spline_call(g, "FindLocationClosestToWorldLocation",
                    inputs=[struct_pin("WorldLocation", VECTOR), native_enum_pin("CoordinateSpace", SPACE, "World")],
                    outputs=[struct_pin("ReturnValue", VECTOR, "out")])
    g.link_entry("WorldLocation", p, "WorldLocation")
    d = g.call_static(MATH, "Vector_Distance2D", inputs=[struct_pin("V1", VECTOR), struct_pin("V2", VECTOR)],
                      outputs=[Pin("ReturnValue", FLOAT, "out")], pure=True)
    g.link(p, "ReturnValue", d, "V1")
    g.link_entry("WorldLocation", d, "V2")
    g.link_result(d, "ReturnValue", "Distance")
    g.link_entry("then", "result", "execute")

    g = bp.function("IsOnRoad", inputs=["WorldLocation:struct:" + VECTOR], outputs=["ReturnValue:bool"], pure=True)
    lat = g.call_self("GetLateralDistanceFromTrack", inputs=[struct_pin("WorldLocation", VECTOR)], outputs=[Pin("Distance", FLOAT, "out")], pure=True)
    g.link_entry("WorldLocation", lat, "WorldLocation")
    w = g.var_get("RoadWidth", FLOAT)
    half = mul(g, (w, "RoadWidth"), b="0.5")
    le = compare(g, "LessEqual_FloatFloat", FLOAT)
    g.link(lat, "Distance", le, "A")
    g.link(half, "ReturnValue", le, "B")
    g.link_result(le, "ReturnValue", "ReturnValue")
    g.link_entry("then", "result", "execute")

    g = bp.function("GetTransformAtDistance", inputs=["Distance:float"], outputs=["Transform:struct:" + TRANSFORM], pure=True)
    t = spline_call(g, "GetTransformAtDistanceAlongSpline",
                    inputs=[Pin("Distance", FLOAT), native_enum_pin("CoordinateSpace", SPACE, "World"), Pin("bUseScale", BOOL, default="false")],
                    outputs=[struct_pin("ReturnValue", TRANSFORM, "out")])
    g.link_entry("Distance", t, "Distance")
    g.link_result(t, "ReturnValue", "Transform")
    g.link_entry("then", "result", "execute")

    # ---- construction script -> RebuildTrack ----
    # Add-Component-by-Class nodes are refused in the construction script graph itself (editor rule in
    # UK2Node_ConstructObjectFromClass::IsCompatibleWithGraph) but are fine in a function it calls: the runtime marks
    # the components as construction-script components (AActor::PostCreateBlueprintComponent).
    ucs = bp.construction_script()
    call = ucs.call_self("RebuildTrack")
    ucs.link_entry("then", call, "execute")

    g = bp.function("RebuildTrack")
    z1 = g.var_set("SegmentCount", INT, default="0")
    z2 = g.var_set("GeneratedMeshCount", INT, default="0")
    g.link_entry("then", z1, "execute")
    g.exec(z1, z2)
    npts = spline_call(g, "GetNumberOfSplinePoints", outputs=[Pin("ReturnValue", INT, "out")])
    ge2 = compare(g, "GreaterEqual_IntInt", INT, b="2")
    g.link(npts, "ReturnValue", ge2, "A")
    length = spline_call(g, "GetSplineLength", outputs=[Pin("ReturnValue", FLOAT, "out")])
    gt1 = compare(g, "Greater_FloatFloat", FLOAT, b="1.0")
    g.link(length, "ReturnValue", gt1, "A")
    ok = and_bool(g)
    g.link(ge2, "ReturnValue", ok, "A")
    g.link(gt1, "ReturnValue", ok, "B")
    b = g.branch()
    g.link(ok, "ReturnValue", b, "Condition")
    g.exec(z2, b)
    # pieces = max(1, ceil(length / max(100, PieceLength)))
    pl = g.var_get("PieceLength", FLOAT)
    pmax = g.call_static(MATH, "FMax", inputs=[Pin("A", FLOAT), Pin("B", FLOAT, default="100.0")], outputs=[Pin("ReturnValue", FLOAT, "out")], pure=True)
    g.link(pl, "PieceLength", pmax, "A")
    ratio = div(g, (length, "ReturnValue"), (pmax, "ReturnValue"))
    ceil = g.call_static(MATH, "FCeil", inputs=[Pin("A", FLOAT)], outputs=[Pin("ReturnValue", INT, "out")], pure=True)
    g.link(ratio, "ReturnValue", ceil, "A")
    pieces = g.call_static(MATH, "Max", inputs=[Pin("A", INT), Pin("B", INT, default="1")], outputs=[Pin("ReturnValue", INT, "out")], pure=True)
    g.link(ceil, "ReturnValue", pieces, "A")
    set_seg = g.var_set("SegmentCount", INT)
    g.link(pieces, "ReturnValue", set_seg, "SegmentCount")
    g.link(b, "then", set_seg, "execute")
    seg = g.var_get("SegmentCount", INT)
    segf = g.call_static(MATH, "Conv_IntToFloat", inputs=[Pin("InInt", INT)], outputs=[Pin("ReturnValue", FLOAT, "out")], pure=True)
    g.link(seg, "SegmentCount", segf, "InInt")
    step = div(g, (length, "ReturnValue"), (segf, "ReturnValue"))
    set_step = g.var_set("PieceStep", FLOAT)
    g.link(step, "ReturnValue", set_step, "PieceStep")
    g.exec(set_seg, set_step)
    loop = g.for_loop()
    seg2 = g.var_get("SegmentCount", INT)
    last = math2(g, "Subtract_IntInt", INT, b="1")
    g.link(seg2, "SegmentCount", last, "A")
    g.link(last, "ReturnValue", loop, "LastIndex")
    g.link(set_step, "then", loop, "execute")
    # s = i * step, e = (i + 1) * step
    i_f = g.call_static(MATH, "Conv_IntToFloat", inputs=[Pin("InInt", INT)], outputs=[Pin("ReturnValue", FLOAT, "out")], pure=True)
    g.link(loop, "Index", i_f, "InInt")
    stp = g.var_get("PieceStep", FLOAT)
    s = mul(g, (i_f, "ReturnValue"), b_src=(stp, "PieceStep"))
    i1 = math2(g, "Add_IntInt", INT, b="1")
    g.link(loop, "Index", i1, "A")
    i1f = g.call_static(MATH, "Conv_IntToFloat", inputs=[Pin("InInt", INT)], outputs=[Pin("ReturnValue", FLOAT, "out")], pure=True)
    g.link(i1, "ReturnValue", i1f, "InInt")
    stp2 = g.var_get("PieceStep", FLOAT)
    e = mul(g, (i1f, "ReturnValue"), b_src=(stp2, "PieceStep"))
    # road: scale (W/U, T/U), offset (0, -T/2) so the slab's top sits on the spline
    unit = g.var_get("MeshNativeSize", FLOAT)
    rw, rt = g.var_get("RoadWidth", FLOAT), g.var_get("RoadThickness", FLOAT)
    road_scale = vec2(g, (div(g, (rw, "RoadWidth"), (unit, "MeshNativeSize")), "ReturnValue"),
                      (div(g, (rt, "RoadThickness"), (unit, "MeshNativeSize")), "ReturnValue"))
    road_off = vec2(g, None, (mul(g, (rt, "RoadThickness"), b="-0.5"), "ReturnValue"))
    road_end = add_piece(g, (loop, "LoopBody"), (s, "ReturnValue"), (e, "ReturnValue"), "RoadMesh", "RoadMaterial", road_off, road_scale)
    # barriers
    gb = g.var_get("bGenerateBarriers", BOOL)
    bb = g.branch()
    g.link(gb, "bGenerateBarriers", bb, "Condition")
    g.exec(road_end, bb)
    bt, bh = g.var_get("BarrierThickness", FLOAT), g.var_get("BarrierHeight", FLOAT)
    bar_scale = vec2(g, (div(g, (bt, "BarrierThickness"), (unit, "MeshNativeSize")), "ReturnValue"),
                     (div(g, (bh, "BarrierHeight"), (unit, "MeshNativeSize")), "ReturnValue"))
    half_w = mul(g, (rw, "RoadWidth"), b="0.5")
    half_t = mul(g, (bt, "BarrierThickness"), b="0.5")
    lateral = math2(g, "Add_FloatFloat", FLOAT)
    g.link(half_w, "ReturnValue", lateral, "A")
    g.link(half_t, "ReturnValue", lateral, "B")
    neg_lateral = mul(g, (lateral, "ReturnValue"), b="-1.0")
    vertical = mul(g, (bh, "BarrierHeight"), b="0.5")
    left_off = vec2(g, (neg_lateral, "ReturnValue"), (vertical, "ReturnValue"))
    right_off = vec2(g, (lateral, "ReturnValue"), (vertical, "ReturnValue"))
    left_end = add_piece(g, (bb, "then"), (s, "ReturnValue"), (e, "ReturnValue"), "BarrierMesh", "BarrierMaterial", left_off, bar_scale)
    add_piece(g, (left_end, "then"), (s, "ReturnValue"), (e, "ReturnValue"), "BarrierMesh", "BarrierMaterial", right_off, bar_scale)
    return bp


if __name__ == "__main__":
    print(build().write(OUT))
