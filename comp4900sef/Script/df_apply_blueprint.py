"""Applies generated Blueprint manifests inside the editor through the DF Blueprint Authoring plugin.

Run inside the editor (MCP run_python or tools/ue_remote.py), e.g.
    exec(open(r'<repo>/comp4900sef/Script/df_apply_blueprint.py').read()); apply_all(r'<repo>/comp4900sef/Script/paste')
    exec(...); apply_all(r'<repo>/comp4900sef/Script/paste', only=['BP_DFVehicle'])

Two passes over every manifest.json under the folder: pass 1 creates assets, components, variables, dispatchers,
function signatures, struct members and enum values (so cross-Blueprint references resolve); pass 2 imports the
graphs, connects the extra links, compiles, sets class defaults and saves. Any compiler error fails the run.

Plugin convention: mutating functions return "" (done), "exists" (already there) or "ERROR: ..."; compile returns
"errors=N warnings=M" followed by one line per compiler message.
"""
import json
import os
import re
import uuid

import unreal

A = unreal.DFBlueprintAuthoringLibrary
LOG_PATH = os.path.join(os.path.dirname(os.path.abspath(unreal.Paths.project_saved_dir())), "Saved", "df_apply.log")
_LOG = []


def log(msg):
    """Collected and written to Saved/df_apply.log; only the summary is printed (remote execution replies are small)."""
    _LOG.append(msg)


def _gen_class_path(asset):
    return "%s.%s_C" % (asset, asset.rsplit("/", 1)[1])


def _load_class(path):
    """'/Script/Engine.Actor' or a Blueprint asset path -> UClass."""
    if path.startswith("/Script/"):
        return unreal.load_class(None, path)
    if path.endswith("_C"):
        return unreal.load_class(None, path)
    return unreal.load_class(None, _gen_class_path(path))


def _existing(asset):
    """The loaded asset, or None. Loading first: the asset registry can lag (e.g. right after an in-editor test run)."""
    try:
        obj = unreal.load_asset(asset)
    except Exception:
        obj = None
    return obj


def _ensure_blueprint(asset, parent):
    found = _existing(asset)
    if found:
        return found
    package, name = asset.rsplit("/", 1)
    factory = unreal.BlueprintFactory()
    factory.set_editor_property("parent_class", _load_class(parent))
    bp = unreal.AssetToolsHelpers.get_asset_tools().create_asset(name, package, unreal.Blueprint, factory)
    log("created %s (parent %s)" % (asset, parent))
    return bp


def _ensure_asset(asset, cls, factory):
    found = _existing(asset)
    if found:
        return found
    package, name = asset.rsplit("/", 1)
    obj = unreal.AssetToolsHelpers.get_asset_tools().create_asset(name, package, cls, factory)
    log("created %s" % asset)
    return obj


def _check(result, what):
    if result is None or str(result).startswith("ERROR"):
        raise RuntimeError("%s: %s" % (what, result))
    if result and result != "exists":
        log("%s: %s" % (what, result))


def _save(asset):
    """Saves the asset to disk and fails loudly when the editor could not write it (typically the file is locked by
    another editor process, such as a headless test run): a silent failure leaves the on-disk copy stale while the
    in-memory one is what verify and the tests see."""
    if not unreal.EditorAssetLibrary.save_asset(asset, False):
        raise RuntimeError("%s: save failed (is the file locked by another editor process, e.g. a headless test run?)" % asset)


def _compile(bp, what):
    msgs = A.compile(bp)
    first, _, rest = msgs.partition("\n")
    for line in rest.splitlines():
        if line.startswith("[ERROR]") or line.startswith("[WARN]"):
            log("%s %s" % (what, line))
    if not first.startswith("errors=0"):
        errors = [l for l in rest.splitlines() if l.startswith("[ERROR]")]
        raise RuntimeError("%s compile failed (%s):\n%s" % (what, first, "\n".join(errors[:12])))
    # the compiler only warns about a call to a function (or a read of a variable) another Blueprint has not compiled yet,
    # and drops the node: treat it as a failure so the retry rounds re-import the graph once that Blueprint has compiled
    unresolved = [l for l in rest.splitlines() if l.startswith("[WARN]") and "Could not find" in l]
    if unresolved:
        raise RuntimeError("%s compile left unresolved references:\n%s" % (what, "\n".join(unresolved[:12])))


def _value(v):
    """JSON default -> Python value for set_editor_property (asset paths are loaded; lists element-wise)."""
    if isinstance(v, list):
        return [_value(x) for x in v]
    if isinstance(v, dict) and "vector" in v:
        return unreal.Vector(*[float(x) for x in v["vector"]])
    if isinstance(v, str):
        if v.startswith("class:"):
            return _load_class(v[6:])
        if v.startswith("/Script/"):
            return unreal.load_object(None, v)
        if v.startswith("/"):
            return unreal.load_asset(v)
    return v


_STRUCT_NAMES = {}


def _struct_member_names(asset):
    """{display name: real property name} for a user-defined struct (property names carry a GUID suffix)."""
    if asset not in _STRUCT_NAMES:
        s = unreal.load_asset(asset)
        d = json.loads(A.describe_struct(s))
        _STRUCT_NAMES[asset] = {mem["display"]: mem["name"] for mem in d["members"]}
    return _STRUCT_NAMES[asset]


def _substitute(text):
    """Replace {{/Game/Path/S_Struct.Member}} placeholders with the struct's real property names."""
    import re

    def repl(match):
        asset, member = match.group(1).rsplit(".", 1)
        names = _struct_member_names(asset)
        if member not in names:
            raise RuntimeError("struct %s has no member %s (has %s)" % (asset, member, list(names)))
        return names[member]

    return re.sub(r"\{\{([^}]+)\}\}", repl, text)


def pass0(m):
    """Make sure every asset exists before any member typed as another Blueprint is added."""
    kind = m["kind"]
    if kind == "struct":
        _ensure_asset(m["asset"], unreal.UserDefinedStruct, unreal.StructureFactory())
    elif kind == "enum":
        _ensure_asset(m["asset"], unreal.UserDefinedEnum, unreal.EnumFactory())
    elif kind == "widget":
        if not _existing(m["asset"]):
            factory = unreal.WidgetBlueprintFactory()
            factory.set_editor_property("parent_class", _load_class(m["parent"]))
            package, name = m["asset"].rsplit("/", 1)
            unreal.AssetToolsHelpers.get_asset_tools().create_asset(name, package, unreal.WidgetBlueprint, factory)
            log("created %s (widget, parent %s)" % (m["asset"], m["parent"]))
    else:
        _ensure_blueprint(m["asset"], m["parent"])
    for r in m.get("requires", []):  # support assets (e.g. a SoundMix) a Blueprint's defaults point at
        _ensure_asset(r["asset"], getattr(unreal, r["class"]), getattr(unreal, r["factory"])())


def _vec2(v):
    return unreal.Vector2D(float(v[0]), float(v[1]))


def _color(v):
    return unreal.LinearColor(*[float(x) for x in v])


def _apply_widget_props(w, props):
    for k, v in props.items():
        if k == "text":
            w.set_editor_property("text", unreal.Text(v))
        elif k == "font_size":
            font = w.get_editor_property("font")
            font.size = int(v)
            w.set_editor_property("font", font)
        elif k == "color":
            sc = w.get_editor_property("color_and_opacity")
            sc.specified_color = _color(v)
            w.set_editor_property("color_and_opacity", sc)
        elif k == "shadow":
            w.set_editor_property("shadow_offset", unreal.Vector2D(1.5, 1.5))
            w.set_editor_property("shadow_color_and_opacity", _color(v))
        elif k == "justify":
            w.set_editor_property("justification", getattr(unreal.TextJustify, v.upper()))
        elif k == "fill_color":
            w.set_editor_property("fill_color_and_opacity", _color(v))
        elif k == "brush_color":
            w.set_editor_property("brush_color", _color(v))
        elif k == "width_override":
            w.set_width_override(float(v))
        elif k == "height_override":
            w.set_height_override(float(v))
        elif k == "visibility":
            w.set_editor_property("visibility", getattr(unreal.SlateVisibility, v.upper()))
        else:
            w.set_editor_property(k, v)


def _apply_slot(w, slot):
    if not slot:
        return
    s = w.get_editor_property("slot")
    if isinstance(s, unreal.CanvasPanelSlot):
        if "anchors" in slot:
            a = slot["anchors"]
            s.set_anchors(unreal.Anchors(minimum=_vec2(a[:2]), maximum=_vec2(a[2:])))
        if "alignment" in slot:
            s.set_alignment(_vec2(slot["alignment"]))
        if "position" in slot:
            s.set_position(_vec2(slot["position"]))
        if "size" in slot:
            s.set_size(_vec2(slot["size"]))
        if "auto_size" in slot:
            s.set_auto_size(bool(slot["auto_size"]))
    else:
        if "padding" in slot:
            p = slot["padding"]
            s.set_padding(unreal.Margin(left=p[0], top=p[1], right=p[2], bottom=p[3]))
        if "h_align" in slot:
            s.set_horizontal_alignment(getattr(unreal.HorizontalAlignment, "H_ALIGN_" + slot["h_align"].upper()))
        if "v_align" in slot:
            s.set_vertical_alignment(getattr(unreal.VerticalAlignment, "V_ALIGN_" + slot["v_align"].upper()))


def apply_widget_tree(bp, m):
    root = A.reset_widget_tree(bp, m["root_class"], m["root_name"])
    if root is None:
        raise RuntimeError("%s: could not reset the widget tree" % m["asset"])
    for e in m["tree"]:
        w = A.add_widget(bp, e["name"], e["class"], e["parent"] or "None")
        if w is None:
            raise RuntimeError("%s: could not add widget %s (%s) under %s" % (m["asset"], e["name"], e["class"], e["parent"] or "root"))
        _apply_widget_props(w, e.get("props", {}))
        _apply_slot(w, e.get("slot", {}))


def pass1(m):
    kind = m["kind"]
    if kind == "struct":
        s = _ensure_asset(m["asset"], unreal.UserDefinedStruct, unreal.StructureFactory())
        for mem in m["members"]:
            _check(A.add_struct_member(s, mem["name"], mem["type"], mem.get("default", "")), "%s.%s" % (m["asset"], mem["name"]))
        _save(m["asset"])
        return
    if kind == "enum":
        e = _ensure_asset(m["asset"], unreal.UserDefinedEnum, unreal.EnumFactory())
        for v in m["values"]:
            _check(A.add_enum_value(e, v), "%s.%s" % (m["asset"], v))
        _save(m["asset"])
        return
    bp = _ensure_blueprint(m["asset"], m["parent"])
    if kind == "widget":
        apply_widget_tree(bp, m)
    for c in m.get("components", []):
        _check(A.add_component(bp, c["name"], c["class"], c.get("parent", "") or "None"), "%s component %s" % (m["asset"], c["name"]))
        if c.get("properties"):
            tmpl = A.get_component_template(bp, c["name"])
            for k, v in c["properties"].items():
                if k.startswith("call:"):  # e.g. "call:set_collision_profile_name": "OverlapOnlyPawn"
                    getattr(tmpl, k[5:])(_value(v))
                else:
                    tmpl.set_editor_property(k, _value(v))
    for v in m.get("variables", []):
        _check(A.add_variable(bp, v["name"], v["type"], v.get("default", ""), v.get("category", ""), v.get("editable", False)), "%s var %s" % (m["asset"], v["name"]))
    for d in m.get("dispatchers", []):
        _check(A.add_event_dispatcher(bp, d["name"], d.get("params", [])), "%s dispatcher %s" % (m["asset"], d["name"]))
    # a function that already exists is removed and re-added so a changed signature (inputs, outputs, pure) takes effect;
    # its graph is re-imported in pass 2 anyway and callers resolve it by name
    existing = set(json.loads(A.describe_blueprint(bp))["functions"])
    for f in m.get("functions", []):
        if f["name"] in existing:
            _check(A.remove_function(bp, f["name"]), "%s remove function %s" % (m["asset"], f["name"]))
        _check(A.add_function(bp, f["name"], f.get("inputs", []), f.get("outputs", []), f.get("pure", False), f.get("category", "")), "%s function %s" % (m["asset"], f["name"]))
        for loc in f.get("locals", []):
            lname, _, rest = loc.partition(":")
            ltype, _, ldefault = rest.partition("=")
            _check(A.add_local_variable(bp, f["name"], lname, ltype, ldefault), "%s local %s.%s" % (m["asset"], f["name"], lname))
        if f.get("doc") and hasattr(A, "set_function_description"):  # the function's tooltip (plugin >= Phase 4)
            _check(A.set_function_description(bp, f["name"], f["doc"]), "%s describe %s" % (m["asset"], f["name"]))
    # no full compile here: the plugin regenerates the skeleton class after each change, which is all pass 2 of
    # other Blueprints needs to resolve references; graphs may still hold a previous, broken version until pass 2.


def _verify_import(bp, asset, graph, text, prefix):
    """Every node in the text must exist in the graph under its (prefixed) name (the engine silently drops nodes
    whose function/variable/class does not resolve), and every pin the text gives a default or a link must exist on
    the real signature (a misnamed pin survives only as an orphan, silently losing its default)."""
    expected = re.findall(r'Begin Object Class=(\S+) Name="([^"]+)"', text)
    nodes = {n["name"]: n for n in json.loads(A.describe_graph(bp, graph))["nodes"]}
    problems = []
    for cls, name in expected:
        short = name.replace(prefix, "DFN_")
        if name not in nodes:
            ref = re.search(r'Begin Object Class=\S+ Name="%s"\n(.*?)\n' % re.escape(name), text)
            problems.append("missing node %s (%s; %s)" % (short, cls.rsplit(".", 1)[1], ref.group(1).strip()[:160] if ref else ""))
            continue
        for p in nodes[name]["pins"]:
            if p.get("orphaned"):
                problems.append("pin %s.%s does not exist on %s" % (short, p["name"], nodes[name]["title"]))
    # every link written in the text must exist after import (a link to a pin name the real node lacks can be
    # dropped by reconstruction without leaving an orphan, e.g. macro instances)
    pin_of = {}
    blocks = re.split(r"(?m)^Begin Object ", text)
    for block in blocks[1:]:
        node = re.search(r'Name="([^"]+)"', block).group(1)
        for pid, pname in re.findall(r'PinId=([0-9A-F]{32}),PinName="([^"]+)"', block):
            pin_of[pid] = (node, pname)
    want = set()
    for block in blocks[1:]:
        node = re.search(r'Name="([^"]+)"', block).group(1)
        for pname, linked in re.findall(r'PinName="([^"]+)"[^\n]*?LinkedTo=\(([^)]*)\)', block):
            for other_node, other_pid in re.findall(r"(\S+) ([0-9A-F]{32}),", linked):
                if other_pid in pin_of:
                    a, b = (node, pname), pin_of[other_pid]
                    want.add(tuple(sorted([a, b])))
    have = set()
    for n in nodes.values():
        for p in n["pins"]:
            for l in p.get("links", []):
                other_node, _, other_pin = l.partition(".")
                have.add(tuple(sorted([(n["name"], p["name"]), (other_node, other_pin)])))
    for (an, ap), (bn, bpn) in sorted(want - have):
        if an in nodes and bn in nodes:
            problems.append("link lost %s.%s -- %s.%s" % (an.replace(prefix, "DFN_"), ap, bn.replace(prefix, "DFN_"), bpn))
    # every class/object default written in the text must be on the imported pin
    for block in blocks[1:]:
        node = re.search(r'Name="([^"]+)"', block).group(1)
        if node not in nodes:
            continue
        actual = {p["name"]: p.get("default_object", "") for p in nodes[node]["pins"]}
        for pname, obj in re.findall(r'PinName="([^"]+)"[^\n]*?DefaultObject="([^"]+)"', block):
            if pname in actual and actual[pname] != obj:
                problems.append("default lost %s.%s (wanted %s, got %r)" % (node.replace(prefix, "DFN_"), pname, obj, actual[pname]))
    if problems:
        raise RuntimeError("%s %s: %d import problem(s):\n  %s" % (asset, graph, len(problems), "\n  ".join(problems)))


def _same_default(want, got):
    """Pin default equality: case-insensitive, numeric lists compared as numbers ("0,0,150" == "0.000000,0.000000,150.0")."""
    if want.strip().lower() == got.strip().lower():
        return True
    nums = lambda s: [float(x) for x in re.findall(r"-?\d+(?:\.\d+)?(?:e-?\d+)?", s)]
    a, b = nums(want), nums(got)
    if a and len(a) == len(b) and not re.search(r"[A-Za-z]{2,}", re.sub(r"\b[XYZWRGBA]=", "", want + got)):
        return all(abs(x - y) < 1e-4 for x, y in zip(a, b))
    return False


def _restore_defaults(bp, graph, text, prefix):
    """Re-applies literal pin defaults that reconstruction dropped. A pasted pin carries no 'autogenerated default',
    so a value equal to the type's zero (false, 0, "") reads as 'unchanged' and the function's own default wins
    (e.g. PrintString bPrintToScreen=false came back true). Returns how many pins were fixed."""
    nodes = {n["name"]: n for n in json.loads(A.describe_graph(bp, graph))["nodes"]}
    fixed = 0
    for block in re.split(r"(?m)^Begin Object ", text)[1:]:
        node = re.search(r'Name="([^"]+)"', block).group(1)
        if node not in nodes:
            continue
        actual = {p["name"]: p for p in nodes[node]["pins"]}
        for pline in re.findall(r"CustomProperties Pin \((.*)\)\s*$", block, re.M):
            pname = re.search(r'PinName="([^"]+)"', pline).group(1)
            dv = re.search(r'DefaultValue="((?:[^"\\]|\\.)*)"', pline)
            if not dv or 'Direction="EGPD_Output"' in pline or pname not in actual or actual[pname].get("links"):
                continue
            want = dv.group(1).replace('\\"', '"')
            got = actual[pname].get("default", "")
            if not _same_default(want, got):
                _check(A.set_pin_default(bp, graph, node, pname, want), "set default %s.%s" % (node.replace(prefix, "DFN_"), pname))
                fixed += 1
    return fixed


def pass2(m, folder):
    if m["kind"] not in ("blueprint", "widget"):
        return
    bp = unreal.load_asset(m["asset"])
    prefix = "DFN%s_" % uuid.uuid4().hex[:6]
    fix = lambda s: s.replace("DFN_", prefix) if isinstance(s, str) else s
    for g in m.get("graphs", []):
        name = g["name"]
        text = fix(_substitute(open(os.path.join(folder, g["file"]), encoding="utf-8").read()))
        _check(A.clear_graph(bp, name), "%s clear %s" % (m["asset"], name))
        _check(A.import_nodes(bp, name, text), "%s import %s" % (m["asset"], name))
        _verify_import(bp, m["asset"], name, text, prefix)
        for a, ap, b, bp_ in g.get("links", []):
            ap, bp_ = _substitute(ap), _substitute(bp_)
            _check(A.connect_pins(bp, name, fix(a), ap, fix(b), bp_), "%s link %s.%s -> %s.%s in %s" % (m["asset"], a, ap, b, bp_, name))
        restored = _restore_defaults(bp, name, text, prefix)
        if restored:
            log("%s %s: restored %d pin default(s)" % (m["asset"], name, restored))
        # the generator lays the graph out and tells us where the pre-existing entry/result nodes belong
        layout = g.get("layout") or {}
        if hasattr(A, "set_node_position"):
            for key in ("entry", "result"):
                if layout.get(key):
                    res = A.set_node_position(bp, name, key, int(layout[key][0]), int(layout[key][1]))
                    if not str(res).startswith("ERROR: node not found"):
                        _check(res, "%s position %s in %s" % (m["asset"], key, name))
    if m.get("description"):
        bp.set_editor_property("blueprint_description", m["description"])
    _compile(bp, m["asset"])
    inherited = _inherited_defaults(m)
    component_defaults = m.get("component_defaults") or {}
    if m.get("defaults") or inherited or component_defaults:
        cdo = unreal.get_default_object(_load_class(m["asset"]))
        # a child of a generated Blueprint: variables its parent declares take the parent's class-default value unless the
        # child sets its own (a child created before the parent's variables existed keeps zeros for them otherwise)
        for k, v in inherited.items():
            if k not in (m.get("defaults") or {}):
                cdo.set_editor_property(k, v)
        for k, v in (m.get("defaults") or {}).items():
            cdo.set_editor_property(k, _value(v))
        # defaults of an inherited component (e.g. the Sedan's VehicleMovement): set on the class-default object's own
        # component instance, which is how the editor stores a child Blueprint's override of a native component property
        for comp, props in component_defaults.items():
            obj = cdo.get_editor_property(comp)
            if obj is None:
                raise RuntimeError("%s: component %s not found on the class defaults" % (m["asset"], comp))
            for k, v in props.items():
                obj.set_editor_property(k, _value(v))
                log("%s component default %s.%s = %r" % (m["asset"], comp, k, v))
        _compile(bp, m["asset"] + " (defaults)")
    _save(m["asset"])
    log("applied %s" % m["asset"])


_MANIFESTS_BY_ASSET = {}


def _inherited_defaults(m):
    """{variable: value} for every variable declared by a generated ancestor of this Blueprint, read from the ancestor's
    class defaults (empty for Blueprints whose parent is native or not generated)."""
    out = {}
    parent = m.get("parent", "")
    while parent in _MANIFESTS_BY_ASSET:
        pm = _MANIFESTS_BY_ASSET[parent]
        pcdo = unreal.get_default_object(_load_class(parent))
        for v in pm.get("variables", []):
            # only the Instance Editable ones (tunables): a plain state variable cannot be set on a class default object
            if v.get("editable") and v["name"] not in out:
                try:
                    out[v["name"]] = pcdo.get_editor_property(v["name"])
                except Exception as e:  # a type Python cannot carry: leave it
                    log("inherit %s.%s skipped: %s" % (parent, v["name"], e))
        parent = pm.get("parent", "")
    return out


def _is_test(m):
    """A functional-test Blueprint (placed in the test level; references everything, referenced by nothing)."""
    return m["asset"].rsplit("/", 1)[1].startswith("FT_DF")


def _pass2_with_retries(manifests):
    """Pass 2 over a group: a Blueprint's new variables are only visible to other Blueprints once it has been fully
    compiled, and pass 2 runs in name order, so a manifest that fails to compile is retried after the others (at most
    three rounds). Returns the (folder, manifest, text) failures left."""
    failures, pending = [], list(manifests)
    for attempt in range(3):
        failures = []
        for folder, m in pending:
            try:
                pass2(m, folder)
            except Exception as e:  # keep going so one Blueprint's errors do not hide the others'
                failures.append((folder, m, "%s: %s" % (m["asset"], e)))
                log("FAILED (round %d) %s: %s" % (attempt + 1, m["asset"], e))
        if not failures or len(failures) == len(pending):
            break
        log("retrying %d manifest(s) now that the others have compiled" % len(failures))
        pending = [(folder, m) for folder, m, _ in failures]
    return failures


def apply_all(root, only=None):
    if len(unreal.EditorLevelLibrary.get_pie_worlds(False)) > 0:
        raise RuntimeError("a Play-In-Editor session is running (editor scripting is disabled during play); stop it first")
    manifests = []
    for d in sorted(os.listdir(root)):
        p = os.path.join(root, d, "manifest.json")
        if os.path.isfile(p) and (only is None or d in only):
            manifests.append((os.path.join(root, d), json.load(open(p, encoding="utf-8"))))
    order = {"enum": 0, "struct": 1, "widget": 2, "blueprint": 3}
    manifests.sort(key=lambda fm: order.get(fm[1]["kind"], 9))
    _STRUCT_NAMES.clear()
    # every manifest under the folder (not only the ones applied now), so a child can inherit a parent's defaults
    _MANIFESTS_BY_ASSET.clear()
    for d in sorted(os.listdir(root)):
        p = os.path.join(root, d, "manifest.json")
        if os.path.isfile(p):
            mm = json.load(open(p, encoding="utf-8"))
            if mm["kind"] in ("blueprint", "widget"):
                _MANIFESTS_BY_ASSET[mm["asset"]] = mm
    del _LOG[:]
    # a child of a Blueprint applied in this same batch waits for a second round: creating the child and then recompiling
    # its parent with new members in one go trips the engine's compilation manager (ensure "ChildClass->ClassDefaultObject
    # == nullptr", which hung the editor on 2026-10-30); once the parent has compiled, the child is created and applied
    in_batch = set(m["asset"] for _, m in manifests)
    children = [fm for fm in manifests if fm[1].get("parent") in in_batch]
    tests = [fm for fm in manifests if fm[1].get("parent") not in in_batch and _is_test(fm[1])]
    core = [fm for fm in manifests if fm[1].get("parent") not in in_batch and not _is_test(fm[1])]
    if children:
        log("children of generated parents are created after the others have compiled: %s" % ", ".join(m["asset"] for _, m in children))
    for folder, m in core + tests:
        pass0(m)
    for folder, m in core + tests:
        pass1(m)
    # 1. the gameplay Blueprints, parents included, compile with no freshly created child class to reinstance
    failed = _pass2_with_retries(core)
    # 2. now the children may exist (tests and catalogues reference them by class)
    for folder, m in children:
        pass0(m)
    for folder, m in children:
        pass1(m)
    # 3. the tests, the children, and whatever failed above (a reference to a child, or to a Blueprint compiled later)
    failed_assets = set(f[1]["asset"] for f in failed)
    last = [fm for fm in manifests if _is_test(fm[1]) or fm in children or fm[1]["asset"] in failed_assets]
    failures = _pass2_with_retries(last)
    failures = [text for _, _, text in failures]
    log("DONE %d manifests, %d failed" % (len(manifests), len(failures)))
    with open(LOG_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(_LOG) + "\n")
    print("APPLY %s: %d manifests, %d failed; full log %s" % ("OK" if not failures else "FAILED", len(manifests), len(failures), LOG_PATH))
    for fl in failures:
        print(fl[:700])
    return not failures
