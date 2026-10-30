"""Blueprint generator for Unreal Engine 4.27.

A Blueprint is described in Python (variables, dispatchers, functions, graphs) and written out as
  comp4900sef/Script/paste/<Blueprint>/manifest.json   what to create, in order, and which links to make
  comp4900sef/Script/paste/<Blueprint>/<Graph>.txt     the editor's clipboard text for that graph
The in-editor runner comp4900sef/Script/df_apply_blueprint.py applies a manifest through the
DF Blueprint Authoring plugin (tools/DFBlueprintAuthoring): it creates the variables, dispatchers and
function signatures, imports each graph's text (the same path as Ctrl+V: FEdGraphUtilities::ImportNodesFromText,
which reconstructs every node so pins follow the real signatures), connects the links the text cannot
express (to a function's pre-existing `entry` / `result` nodes), compiles and saves.
The text files are also valid for a manual Ctrl+V into the graph, which is the fallback without the plugin.

Usage (see graphs/*.py):
    bp = Blueprint("/Game/DeadFire/Blueprints/BP_DFVehicle", parent="/Game/VehicleBP/Sedan/Sedan")
    bp.variable("Health", "float", "100", "Dead Fire|Health", editable=True)
    f = bp.function("GetThrottleScale", outputs=["Scale:float"], pure=True)
    n = f.call_static("KismetMathLibrary", "MultiplyMultiply_FloatFloat", ...)
    f.link_result(n, "ReturnValue", "Scale")
    g = bp.event_graph(); ...
    bp.write(OUT)
"""
from __future__ import annotations

import json
import os
import uuid
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

# ---- pin categories (UEdGraphSchema_K2::PC_*) ----
EXEC, BOOL, INT, FLOAT, STRING, NAME, TEXT, OBJECT, CLASS, STRUCT, BYTE, DELEGATE, WILDCARD = (
    "exec", "bool", "int", "float", "string", "name", "text", "object", "class", "struct", "byte", "delegate", "wildcard")

STANDARD_MACROS = "/Engine/EditorBlueprintResources/StandardMacros.StandardMacros"


def guid() -> str:
    return uuid.uuid4().hex.upper()


def cls_ref(path: str) -> str:
    """Object reference text for a native or Blueprint class path."""
    if path.startswith("/Script/"):
        return "Class'\"%s\"'" % path
    return "BlueprintGeneratedClass'\"%s\"'" % path


def struct_ref(path: str) -> str:
    return "ScriptStruct'\"%s\"'" % path


def enum_ref(path: str) -> str:
    if path.startswith("/Script/"):
        return "Enum'\"%s\"'" % path
    return "UserDefinedEnum'\"%s\"'" % path


def bp_class(asset_path: str) -> str:
    """'/Game/DeadFire/Blueprints/BP_DFVehicle' -> generated class path."""
    name = asset_path.rsplit("/", 1)[1]
    return "%s.%s_C" % (asset_path, name)


def bp_display(asset_path: str) -> str:
    return asset_path.rsplit("/", 1)[1]


def cast_result_pin(class_path: str) -> str:
    """Name of a cast node's result pin: 'As' + the class display name (UK2Node_DynamicCast::AllocateDefaultPins)."""
    name = class_path.rsplit(".", 1)[1]
    if name.endswith("_C"):
        name = name[:-2]
    return "As" + name_to_display(name)


_ARTICLES = ["In", "As", "To", "Or", "At", "On", "If", "Be", "By", "The", "For", "And", "With", "When", "From"]


def name_to_display(name: str, is_bool: bool = False) -> str:
    """Port of FName::NameToDisplayString (UE 4.27, Runtime/Core/Private/UObject/UnrealNames.cpp); used for pin names
    the engine derives from display names, e.g. a cast's 'As<Class Display Name>' output."""
    out = []
    in_run = was_space = was_paren = was_number = was_minus = False
    n = len(name)
    for i, ch in enumerate(name):
        lower, upper, digit, underscore = ch.islower(), ch.isupper(), ch.isdigit(), ch == "_"
        if i == 0 and is_bool and ch == "b" and n > 1 and name[1].isupper():
            continue
        if (upper or (digit and not was_minus)) and not in_run and not was_paren and not was_number:
            if not was_space and out:
                out.append(" ")
                was_space = True
            in_run = True
        if lower:
            in_run = False
        if underscore:
            ch = " "
            in_run = True
        if not out:
            ch = ch.upper()
        elif not digit and (was_space or was_paren):
            article = False
            for a in _ARTICLES:
                if n - i > len(a) and not name[i + len(a)].islower() and name[i:i + len(a)] == a:
                    article = True
                    break
            ch = ch.lower() if article else ch.upper()
        was_space = ch == " "
        was_paren = ch == "("
        was_minus = ch == "-"
        was_number = digit or (was_number and (was_minus or ch == "."))
        out.append(ch)
    return "".join(out)


def escape(s: str) -> str:
    return s.replace("\\", "\\\\").replace('"', '\\"')


@dataclass
class Pin:
    name: str
    category: str
    direction: str = "in"  # "in" | "out"
    sub_object: Optional[str] = None  # already-formatted object reference text
    sub_category: str = ""
    default: Optional[str] = None
    hidden: bool = False
    container: Optional[str] = None  # None | "Array"
    member_ref: Optional[str] = None  # for delegate pins
    default_object: Optional[str] = None  # object/class pin default, as an object path
    id: str = field(default_factory=guid)
    links: List[Tuple[str, str]] = field(default_factory=list)  # (node name, pin id)

    def text(self) -> str:
        parts = ["PinId=%s" % self.id, 'PinName="%s"' % self.name]
        if self.direction == "out":
            parts.append('Direction="EGPD_Output"')
        parts.append('PinType.PinCategory="%s"' % self.category)
        parts.append('PinType.PinSubCategory="%s"' % self.sub_category)
        parts.append("PinType.PinSubCategoryObject=%s" % (self.sub_object or "None"))
        parts.append("PinType.PinSubCategoryMemberReference=%s" % (self.member_ref or "()"))
        parts.append("PinType.PinValueType=()")
        parts.append("PinType.ContainerType=%s" % (self.container or "None"))
        parts.append("PinType.bIsReference=False")
        parts.append("PinType.bIsConst=False")
        parts.append("PinType.bIsWeakPointer=False")
        parts.append("PinType.bIsUObjectWrapper=False")
        if self.default is not None:
            parts.append('DefaultValue="%s"' % escape(self.default))
        if self.default_object is not None:
            parts.append('DefaultObject="%s"' % escape(self.default_object))
        if self.links:
            parts.append("LinkedTo=(%s)" % "".join("%s %s," % l for l in self.links))
        parts.append("PersistentGuid=00000000000000000000000000000000")
        parts.append("bHidden=%s" % ("True" if self.hidden else "False"))
        parts.append("bNotConnectable=False")
        parts.append("bDefaultValueIsReadOnly=False")
        parts.append("bDefaultValueIsIgnored=False")
        parts.append("bAdvancedView=False")
        parts.append("bOrphanedPin=False")
        return "CustomProperties Pin (%s,)" % ",".join(parts)


@dataclass
class Node:
    cls: str  # e.g. "/Script/BlueprintGraph.K2Node_CallFunction"
    name: str
    props: List[str] = field(default_factory=list)  # raw "Key=Value" lines
    pins: List[Pin] = field(default_factory=list)
    x: int = 0
    y: int = 0
    width: int = 0
    height: int = 0

    def pin(self, name: str) -> Pin:
        for p in self.pins:
            if p.name == name:
                return p
        raise KeyError("%s has no pin %r (pins: %s)" % (self.name, name, [p.name for p in self.pins]))

    def text(self) -> str:
        lines = ['Begin Object Class=%s Name="%s"' % (self.cls, self.name)]
        lines += ["   " + p for p in self.props]
        lines.append("   NodePosX=%d" % self.x)
        lines.append("   NodePosY=%d" % self.y)
        if self.width:
            lines.append("   NodeWidth=%d" % self.width)
            lines.append("   NodeHeight=%d" % self.height)
        lines.append("   NodeGuid=%s" % guid())
        lines += ["   " + p.text() for p in self.pins]
        lines.append("End Object")
        return "\n".join(lines)


def _input_copy(p: "Pin", defaults: dict) -> "Pin":
    """An input pin for a call node: keeps every field of the template pin (class/object default, hidden flag...)
    and applies a per-call literal default when one is given by name."""
    return Pin(p.name, p.category, "in", p.sub_object, p.sub_category, defaults.get(p.name, p.default),
               hidden=p.hidden, container=p.container, member_ref=p.member_ref, default_object=p.default_object)


class Graph:
    """One graph (event graph or function body) of one Blueprint.

    Node positions are computed by layout() when the text is written (see the layout contract in the plan
    docs/superpowers/plans/2026-10-30-phase4-ai.md, Task 1a): exec flow left to right, one row per branch, pure inputs
    left of and below their consumer, titled comment boxes per section, nothing overlapping.
    """

    COL_GAP = 80        # between an exec column's right edge and the next column's pure band
    ROW_GAP = 60        # between rows
    SECTION_GAP = 100   # extra space between two sections' rows
    PURE_DX = 40        # between pure depth columns
    PURE_DY = 40        # a consumer's first pure input starts this far below the consumer's top
    PURE_GAP = 24       # between stacked pure nodes
    PAD = 24            # comment box padding
    TITLE_H = 36        # comment box title bar
    ROOT_CLASSES = ("K2Node_Event", "K2Node_CustomEvent", "K2Node_InputAction", "K2Node_ComponentBoundEvent",
                    "K2Node_InputAxisEvent")

    def __init__(self, blueprint: str, graph: str, setup: Optional[List[str]] = None):
        self.blueprint = blueprint  # asset name, e.g. BP_DFVehicle
        self.graph = graph  # "EventGraph", "UserConstructionScript" or a function name
        self.nodes: List[Node] = []
        self.counts: Dict[str, int] = {}
        self.manual: List[str] = []  # human-readable list of the extra links (for the fallback paste)
        self.extra_links: List[Tuple[str, str, str, str]] = []  # (node id, pin, node id, pin); ids may be "entry"/"result"
        self.setup = setup or []
        self.sections: Dict[str, str] = {}  # root node name -> section title
        self._pending_section: Optional[str] = None
        self.doc: Optional[str] = None  # a function graph's description: one section around the whole body
        self.entry_pins = 1  # exec + inputs on the pre-existing entry node (size estimate)
        self.result_pins = 0  # exec + outputs on the pre-existing result node; 0 = the function has no result node
        self._layout_info: Optional[Dict[str, Optional[List[int]]]] = None

    # ---- plumbing ----
    def _add(self, cls_short: str, props: List[str], pins: List[Pin], col: Optional[int], row: Optional[int],
             module: str = "BlueprintGraph") -> Node:
        n = self.counts.get(cls_short, 0)
        self.counts[cls_short] = n + 1
        # "DFN_" prefix: never collides with engine-created nodes (K2Node_FunctionEntry_0 ...); the runner replaces it
        # with a per-run token so a re-apply never collides with removed-but-not-yet-collected nodes either.
        node = Node("/Script/%s.%s" % (module, cls_short), "DFN_%s_%d" % (cls_short, n), props, pins)
        # col/row are accepted for compatibility and ignored: layout() places every node
        if self._pending_section is not None and (cls_short in self.ROOT_CLASSES or any(p.category == EXEC for p in pins)):
            self.sections[node.name] = self._pending_section
            self._pending_section = None
        self._layout_info = None
        self.nodes.append(node)
        return node

    def section(self, title: str) -> None:
        """Titles the section that starts with the next event (or exec node) created: a comment box around that
        event's whole chain in the editor."""
        self._pending_section = title

    def note(self, node: Node, text: str) -> None:
        """A comment bubble shown above the node in the editor."""
        node.props = [p for p in node.props if not p.startswith("NodeComment=") and not p.startswith("bCommentBubbleVisible=")]
        node.props += ['NodeComment="%s"' % escape(text), "bCommentBubbleVisible=True"]

    def link(self, a, a_pin: str, b, b_pin: str) -> None:
        """Link two pins. Either side may be "entry" / "result" (the function's pre-existing terminators): those
        links are made by the runner after import (manifest), since pasted text cannot reference existing nodes."""
        if isinstance(a, str) or isinstance(b, str):
            self.link_extra(a, a_pin, b, b_pin)
            return
        pa, pb = a.pin(a_pin), b.pin(b_pin)
        pa.links.append((b.name, pb.id))
        pb.links.append((a.name, pa.id))

    def exec(self, *chain: Node, out: str = "then", **kw) -> None:
        """Link an exec chain: a.then -> b.execute -> c.execute ... (first link may use out=)."""
        for i in range(len(chain) - 1):
            self.link(chain[i], out if i == 0 else "then", chain[i + 1], "execute")

    def wire_manually(self, text: str) -> None:
        self.manual.append(text)

    def link_extra(self, a, a_pin: str, b, b_pin: str) -> None:
        """Link to a node that exists before the import: pass "entry" / "result" or a Node."""
        ida = a if isinstance(a, str) else a.name
        idb = b if isinstance(b, str) else b.name
        self.extra_links.append((ida, a_pin, idb, b_pin))
        self.manual.append("%s.%s -> %s.%s" % (ida, a_pin, idb, b_pin))

    def link_entry(self, entry_pin: str, node: Node, node_pin: str) -> None:
        """Function entry pin ('then' for exec, or an input parameter name) -> a pasted node's pin."""
        self.link_extra("entry", entry_pin, node, node_pin)

    def link_result(self, node: Node, node_pin: str, result_pin: str) -> None:
        """A pasted node's pin -> the function's result node ('execute' or an output name)."""
        self.link_extra(node, node_pin, "result", result_pin)

    # ---- node constructors ----
    def event(self, parent_class: str, member: str, params: Optional[List[Pin]] = None,
              col=None, row=None) -> Node:
        """Override event, e.g. event('/Script/Engine.Actor', 'ReceiveBeginPlay')."""
        pins = [Pin("OutputDelegate", DELEGATE, "out",
                    member_ref="(MemberParent=%s,MemberName=\"%s\")" % (cls_ref(parent_class), member)),
                Pin("then", EXEC, "out")] + [Pin(p.name, p.category, "out", p.sub_object, p.sub_category,
                                                  container=p.container) for p in (params or [])]
        props = ['EventReference=(MemberParent=%s,MemberName="%s")' % (cls_ref(parent_class), member),
                 "bOverrideFunction=True"]
        return self._add("K2Node_Event", props, pins, col, row)

    def begin_play(self, col=None, row=None) -> Node:
        return self.event("/Script/Engine.Actor", "ReceiveBeginPlay", col=col, row=row)

    def tick(self, col=None, row=None) -> Node:
        return self.event("/Script/Engine.Actor", "ReceiveTick", [Pin("DeltaSeconds", FLOAT)], col, row)

    def custom_event(self, name: str, params: Optional[List[Pin]] = None, col=None, row=None) -> Node:
        pins = [Pin("OutputDelegate", DELEGATE, "out",
                    member_ref='(MemberName="%s",bSelfContext=True)' % name),
                Pin("then", EXEC, "out")] + [Pin(p.name, p.category, "out", p.sub_object, p.sub_category,
                                                  container=p.container) for p in (params or [])]
        return self._add("K2Node_CustomEvent", ['CustomFunctionName="%s"' % name], pins, col, row)

    def input_action(self, action: str, col=None, row=None, execute_when_paused: bool = False) -> Node:
        """Input action event; execute_when_paused lets it fire while the game is paused (a pause toggle)."""
        pins = [Pin("Pressed", EXEC, "out"), Pin("Released", EXEC, "out"),
                Pin("Key", STRUCT, "out", struct_ref("/Script/InputCore.Key"))]
        props = ['InputActionName="%s"' % action] + (["bExecuteWhenPaused=True"] if execute_when_paused else [])
        return self._add("K2Node_InputAction", props, pins, col, row)

    def component_event(self, component: str, delegate: str, owner_class: str, params: List[Pin],
                        signature: str, signature_package: str = "/Script/Engine", col=None, row=None) -> Node:
        """Component-bound event, e.g. component_event('Trigger', 'OnComponentBeginOverlap', PRIMITIVE, [...],
        'ComponentBeginOverlapSignature__DelegateSignature')."""
        fn = "BndEvt__%s_%s_%s" % (self.blueprint, component, delegate)
        pins = [Pin("OutputDelegate", DELEGATE, "out"), Pin("then", EXEC, "out")] + [
            Pin(p.name, p.category, "out", p.sub_object, p.sub_category, container=p.container) for p in params]
        props = ['DelegatePropertyName="%s"' % delegate, "DelegateOwnerClass=%s" % cls_ref(owner_class),
                 'ComponentPropertyName="%s"' % component,
                 'EventReference=(MemberParent=Package\'"%s"\',MemberName="%s")' % (signature_package, signature),
                 'CustomFunctionName="%s"' % fn, "bInternalEvent=True"]
        return self._add("K2Node_ComponentBoundEvent", props, pins, col, row)

    def add_component_by_class(self, component_class: str, col=None, row=None) -> Node:
        """'Add <Component>' node (UK2Node_AddComponentByClass) on self; ReturnValue is typed as the class."""
        pins = [Pin("execute", EXEC), Pin("then", EXEC, "out"), Pin("self", OBJECT, hidden=True, sub_category="self"),
                Pin("Class", CLASS, sub_object=cls_ref("/Script/Engine.ActorComponent"), default_object=component_class),
                Pin("bManualAttachment", BOOL, default="false"),
                Pin("RelativeTransform", STRUCT, sub_object=struct_ref("/Script/CoreUObject.Transform")),
                Pin("ReturnValue", OBJECT, "out", cls_ref(component_class))]
        return self._add("K2Node_AddComponentByClass", [], pins, col, row)

    def create_widget(self, widget_class: Optional[str] = None, result_class: str = "/Script/UMG.UserWidget",
                      col=None, row=None) -> Node:
        """'Create Widget' (UK2Node_CreateWidget); link Class (or give widget_class) and OwningPlayer."""
        pins = [Pin("execute", EXEC), Pin("then", EXEC, "out"),
                Pin("Class", CLASS, sub_object=cls_ref("/Script/UMG.UserWidget"), default_object=widget_class),
                Pin("OwningPlayer", OBJECT, sub_object=cls_ref("/Script/Engine.PlayerController")),
                Pin("ReturnValue", OBJECT, "out", cls_ref(result_class))]
        return self._add("K2Node_CreateWidget", [], pins, col, row, module="UMGEditor")

    def spawn_actor(self, actor_class: Optional[str], result_class: Optional[str] = None, col=None, row=None) -> Node:
        """'Spawn Actor from Class' (UK2Node_SpawnActorFromClass); link SpawnTransform, optionally Owner.
        actor_class None leaves the Class pin to be linked (a class variable); ReturnValue is then typed result_class."""
        pins = [Pin("execute", EXEC), Pin("then", EXEC, "out"),
                Pin("WorldContextObject", OBJECT, hidden=True, sub_object=cls_ref("/Script/CoreUObject.Object")),
                Pin("Class", CLASS, sub_object=cls_ref("/Script/Engine.Actor"), default_object=actor_class),
                Pin("SpawnTransform", STRUCT, sub_object=struct_ref("/Script/CoreUObject.Transform")),
                Pin("CollisionHandlingOverride", BYTE, sub_object="Enum'\"/Script/Engine.ESpawnActorCollisionHandlingMethod\"'",
                    default="AlwaysSpawn"),
                Pin("Owner", OBJECT, sub_object=cls_ref("/Script/Engine.Actor")),
                Pin("ReturnValue", OBJECT, "out", cls_ref(result_class or actor_class))]
        return self._add("K2Node_SpawnActorFromClass", [], pins, col, row)

    def _call(self, member_ref: str, pure: bool, inputs: List[Pin], outputs: List[Pin], self_pin: Optional[Pin],
              col, row, cls_short="K2Node_CallFunction") -> Node:
        pins: List[Pin] = []
        if not pure:
            pins += [Pin("execute", EXEC), Pin("then", EXEC, "out")]
        if self_pin is not None:
            pins.append(self_pin)
        pins += inputs + outputs
        return self._add(cls_short, ["FunctionReference=%s" % member_ref], pins, col, row)

    def call_static(self, library: str, fn: str, inputs: Optional[List[Pin]] = None,
                    outputs: Optional[List[Pin]] = None, pure: bool = False, module: str = "Engine",
                    col=None, row=None, **defaults) -> Node:
        """Call a static library function, e.g. call_static('KismetMathLibrary', 'Multiply_FloatFloat', ...).
        defaults: pin name -> default value text for inputs listed in `inputs`."""
        inputs = [_input_copy(p, defaults) for p in (inputs or [])]
        ref = '(MemberParent=%s,MemberName="%s")' % (cls_ref("/Script/%s.%s" % (module, library)), fn)
        return self._call(ref, pure, inputs, outputs or [], None, col, row)

    def call_self(self, fn: str, inputs: Optional[List[Pin]] = None, outputs: Optional[List[Pin]] = None,
                  pure: bool = False, col=None, row=None, **defaults) -> Node:
        """Call a function (or custom event) of this Blueprint."""
        inputs = [_input_copy(p, defaults) for p in (inputs or [])]
        ref = '(MemberName="%s",bSelfContext=True)' % fn
        return self._call(ref, pure, inputs, outputs or [], Pin("self", OBJECT, hidden=True, sub_category="self"),
                          col, row)

    def call_on(self, target_class: str, fn: str, inputs: Optional[List[Pin]] = None,
                outputs: Optional[List[Pin]] = None, pure: bool = False, col=None, row=None, **defaults) -> Node:
        """Call a member function on another object; link its 'self' pin to the target."""
        inputs = [_input_copy(p, defaults) for p in (inputs or [])]
        ref = '(MemberParent=%s,MemberName="%s")' % (cls_ref(target_class), fn)
        return self._call(ref, pure, inputs, outputs or [], Pin("self", OBJECT, sub_object=cls_ref(target_class)),
                          col, row)

    def call_self_native(self, parent_class: str, fn: str, inputs: Optional[List[Pin]] = None,
                         outputs: Optional[List[Pin]] = None, pure: bool = False, col=None, row=None, **defaults) -> Node:
        """Call an inherited native function on self (e.g. Actor.K2_GetActorLocation)."""
        inputs = [_input_copy(p, defaults) for p in (inputs or [])]
        ref = '(MemberParent=%s,MemberName="%s",bSelfContext=True)' % (cls_ref(parent_class), fn)
        return self._call(ref, pure, inputs, outputs or [], Pin("self", OBJECT, hidden=True, sub_category="self"),
                          col, row)

    def input_axis_value(self, axis: str, col=None, row=None) -> Node:
        """'Get <Axis>' node (UK2Node_GetInputAxisValue); Actor.GetInputAxisValue itself is internal-only."""
        pins = [Pin("self", OBJECT, hidden=True, sub_category="self"),
                Pin("InputAxisName", NAME, default=axis, hidden=True), Pin("ReturnValue", FLOAT, "out")]
        return self._add("K2Node_GetInputAxisValue",
                         ['InputAxisName="%s"' % axis,
                          'FunctionReference=(MemberParent=Class\'"/Script/Engine.Actor"\',MemberName="GetInputAxisValue")'],
                         pins, col, row)

    def call_array(self, library: str, fn: str, elem: Pin, inputs: Optional[List[Pin]] = None,
                   outputs: Optional[List[Pin]] = None, pure: bool = True, col=None, row=None) -> Node:
        """KismetArrayLibrary call (Array_Get/Length/Add/Set/Clear...); link the TargetArray pin to an array."""
        target = Pin("TargetArray", WILDCARD, "in", container="Array")
        ref = '(MemberParent=%s,MemberName="%s")' % (cls_ref("/Script/Engine.%s" % library), fn)
        return self._call(ref, pure, [target] + list(inputs or []), outputs or [], None, col, row,
                          cls_short="K2Node_CallArrayFunction")

    def var_get_on(self, owner_class: str, name: str, category: str, sub_object: Optional[str] = None,
                   container: Optional[str] = None, col=None, row=None) -> Node:
        """Read a variable of another object (link the 'self' pin to the target)."""
        pins = [Pin(name, category, "out", sub_object, container=container),
                Pin("self", OBJECT, sub_object=cls_ref(owner_class))]
        return self._add("K2Node_VariableGet", ['VariableReference=(MemberParent=%s,MemberName="%s")'
                                                % (cls_ref(owner_class), name)], pins, col, row)

    def var_set_on(self, owner_class: str, name: str, category: str, default: Optional[str] = None,
                   sub_object: Optional[str] = None, container: Optional[str] = None, col=None, row=None) -> Node:
        """Write a variable of another object (link the 'self' pin to the target)."""
        pins = [Pin("execute", EXEC), Pin("then", EXEC, "out"),
                Pin(name, category, "in", sub_object, default=default, container=container),
                Pin("Output_Get", category, "out", sub_object, container=container),
                Pin("self", OBJECT, sub_object=cls_ref(owner_class))]
        return self._add("K2Node_VariableSet", ['VariableReference=(MemberParent=%s,MemberName="%s")'
                                                % (cls_ref(owner_class), name)], pins, col, row)

    def local_get(self, name: str, category: str, sub_object: Optional[str] = None, container: Optional[str] = None,
                  col=None, row=None) -> Node:
        """Read a local variable of this function graph (declared in Blueprint.function(..., locals=[...]))."""
        pins = [Pin(name, category, "out", sub_object, container=container)]
        return self._add("K2Node_VariableGet", ['VariableReference=(MemberScope="%s",MemberName="%s",bSelfContext=True)'
                                                % (self.graph, name)], pins, col, row)

    def local_set(self, name: str, category: str, default: Optional[str] = None, sub_object: Optional[str] = None,
                  container: Optional[str] = None, col=None, row=None) -> Node:
        pins = [Pin("execute", EXEC), Pin("then", EXEC, "out"),
                Pin(name, category, "in", sub_object, default=default, container=container),
                Pin("Output_Get", category, "out", sub_object, container=container)]
        return self._add("K2Node_VariableSet", ['VariableReference=(MemberScope="%s",MemberName="%s",bSelfContext=True)'
                                                % (self.graph, name)], pins, col, row)

    def call_delegate_on(self, owner_class: str, name: str, params: Optional[List[Pin]] = None, col=None, row=None) -> Node:
        """Fire an event dispatcher of another object (link the 'self' pin to the target)."""
        pins = [Pin("execute", EXEC), Pin("then", EXEC, "out"),
                Pin("self", OBJECT, sub_object=cls_ref(owner_class))] + list(params or [])
        return self._add("K2Node_CallDelegate", ['DelegateReference=(MemberParent=%s,MemberName="%s")'
                                                 % (cls_ref(owner_class), name)], pins, col, row)

    def call_parent(self, parent_class: str, fn: str, params: Optional[List[Pin]] = None, col=None, row=None) -> Node:
        """'Call Parent Function' for an overridden event, e.g. call_parent(gen(SEDAN), 'ReceiveBeginPlay')."""
        pins = [Pin("execute", EXEC), Pin("then", EXEC, "out"), Pin("self", OBJECT, hidden=True, sub_category="self")] + [
            Pin(p.name, p.category, "in", p.sub_object, p.sub_category, container=p.container) for p in (params or [])]
        return self._add("K2Node_CallParentFunction",
                         ['FunctionReference=(MemberParent=%s,MemberName="%s",bSelfContext=True)' % (cls_ref(parent_class), fn)],
                         pins, col, row)

    def make_array(self, elem: Pin, defaults: List[Optional[str]], col=None, row=None) -> Node:
        """Make Array with len(defaults) inputs named [0], [1], ...; link or default each."""
        pins = [Pin("[%d]" % i, elem.category, "in", elem.sub_object, default=d) for i, d in enumerate(defaults)]
        pins.append(Pin("Array", elem.category, "out", elem.sub_object, container="Array"))
        return self._add("K2Node_MakeArray", ["NumInputs=%d" % len(defaults)], pins, col, row)

    def var_get(self, name: str, category: str, sub_object: Optional[str] = None, container: Optional[str] = None,
                col=None, row=None) -> Node:
        pins = [Pin(name, category, "out", sub_object, container=container),
                Pin("self", OBJECT, hidden=True, sub_category="self")]
        return self._add("K2Node_VariableGet", ['VariableReference=(MemberName="%s",bSelfContext=True)' % name],
                         pins, col, row)

    def var_set(self, name: str, category: str, default: Optional[str] = None, sub_object: Optional[str] = None,
                container: Optional[str] = None, col=None, row=None) -> Node:
        pins = [Pin("execute", EXEC), Pin("then", EXEC, "out"),
                Pin(name, category, "in", sub_object, default=default, container=container),
                Pin("Output_Get", category, "out", sub_object, container=container),
                Pin("self", OBJECT, hidden=True, sub_category="self")]
        return self._add("K2Node_VariableSet", ['VariableReference=(MemberName="%s",bSelfContext=True)' % name],
                         pins, col, row)

    def branch(self, col=None, row=None) -> Node:
        pins = [Pin("execute", EXEC), Pin("Condition", BOOL, default="true"), Pin("then", EXEC, "out"),
                Pin("else", EXEC, "out")]
        return self._add("K2Node_IfThenElse", [], pins, col, row)

    def sequence(self, outputs: int = 2, col=None, row=None) -> Node:
        pins = [Pin("execute", EXEC)] + [Pin("then_%d" % i, EXEC, "out") for i in range(outputs)]
        return self._add("K2Node_ExecutionSequence", [], pins, col, row)

    def cast(self, target_class: str, col=None, row=None) -> Node:
        pins = [Pin("execute", EXEC), Pin("then", EXEC, "out"), Pin("CastFailed", EXEC, "out"),
                Pin("Object", OBJECT, sub_object=cls_ref("/Script/CoreUObject.Object")),
                Pin(cast_result_pin(target_class), OBJECT, "out", cls_ref(target_class)), Pin("bSuccess", BOOL, "out", hidden=True)]
        return self._add("K2Node_DynamicCast", ["TargetType=%s" % cls_ref(target_class), "bIsPureCast=False"], pins,
                         col, row)

    def self_node(self, col=None, row=None) -> Node:
        return self._add("K2Node_Self", [], [Pin("self", OBJECT, "out", sub_category="self")], col, row)

    def call_delegate(self, name: str, params: Optional[List[Pin]] = None, col=None, row=None) -> Node:
        """Fire an event dispatcher of this Blueprint."""
        pins = [Pin("execute", EXEC), Pin("then", EXEC, "out"),
                Pin("self", OBJECT, hidden=True, sub_category="self")] + list(params or [])
        return self._add("K2Node_CallDelegate", ['DelegateReference=(MemberName="%s",bSelfContext=True)' % name],
                         pins, col, row)

    def break_struct(self, struct_path: str, fields: List[Pin], col=None, row=None) -> Node:
        pins = [Pin(struct_path.rsplit(".", 1)[1], STRUCT, "in", struct_ref(struct_path))] + [
            Pin(p.name, p.category, "out", p.sub_object, p.sub_category) for p in fields]
        return self._add("K2Node_BreakStruct", ["StructType=%s" % struct_ref(struct_path)], pins, col, row)

    def make_struct(self, struct_path: str, fields: List[Pin], col=None, row=None) -> Node:
        pins = [Pin(p.name, p.category, "in", p.sub_object, p.sub_category, p.default) for p in fields] + [
            Pin(struct_path.rsplit(".", 1)[1], STRUCT, "out", struct_ref(struct_path))]
        return self._add("K2Node_MakeStruct", ["StructType=%s" % struct_ref(struct_path)], pins, col, row)

    def macro(self, name: str, pins: List[Pin], col=None, row=None) -> Node:
        """Standard macro instance, e.g. ForEachLoop / ForLoop / WhileLoop / IsValid."""
        props = ["MacroGraphReference=(MacroGraph=EdGraph'\"%s:%s\"',GraphBlueprint=Blueprint'\"%s\"')"
                 % (STANDARD_MACROS, name, STANDARD_MACROS)]
        return self._add("K2Node_MacroInstance", props, pins, col, row)

    def for_each(self, element: Pin, col=None, row=None) -> Node:
        # wildcard pins: the macro resolves them from the linked array (UK2Node_MacroInstance::NotifyPinConnectionListChanged)
        pins = [Pin("Exec", EXEC), Pin("Array", WILDCARD, "in", container="Array"),
                Pin("LoopBody", EXEC, "out"), Pin("Array Element", WILDCARD, "out"),
                Pin("Array Index", INT, "out"), Pin("Completed", EXEC, "out")]
        return self.macro("ForEachLoop", pins, col, row)

    def for_loop(self, col=None, row=None) -> Node:
        # StandardMacros' ForLoop names its exec input "execute" (ForEachLoop uses "Exec")
        pins = [Pin("execute", EXEC), Pin("FirstIndex", INT, default="0"), Pin("LastIndex", INT, default="0"),
                Pin("LoopBody", EXEC, "out"), Pin("Index", INT, "out"), Pin("Completed", EXEC, "out")]
        return self.macro("ForLoop", pins, col, row)

    def function_result(self, outputs: List[Pin], col=None, row=None) -> Node:
        """Return node for a function body paste (the entry node already exists in the graph)."""
        pins = [Pin("execute", EXEC)] + [Pin(p.name, p.category, "in", p.sub_object, p.sub_category, p.default,
                                             container=p.container, default_object=p.default_object) for p in outputs]
        return self._add("K2Node_FunctionResult", [], pins, col, row)

    def _comment_box(self, text: str, x: int, y: int, width: int, height: int) -> Node:
        node = self._add("EdGraphNode_Comment", ['NodeComment="%s"' % escape(text), "CommentColor=(R=0.35,G=0.45,B=0.6,A=1.0)",
                                                 "FontSize=18"], [], None, None, module="UnrealEd")
        node.x, node.y, node.width, node.height = x, y, width, height
        return node

    # ---- layout ----
    @staticmethod
    def _is_comment(n: Node) -> bool:
        return n.cls.endswith("EdGraphNode_Comment")

    @staticmethod
    def _member_name(n: Node) -> str:
        import re
        for p in n.props:
            m = re.search(r'MemberName="([^"]+)"', p)
            if m:
                return m.group(1)
        return ""

    def _estimate(self, n: Node) -> Tuple[int, int]:
        """Approximate rendered size of a node (px at zoom 1), from its class and visible pins."""
        short = n.cls.rsplit(".", 1)[1]
        ins = [p for p in n.pins if p.direction == "in" and not p.hidden]
        outs = [p for p in n.pins if p.direction == "out" and not p.hidden]
        tall_header = short in ("K2Node_Event", "K2Node_CustomEvent", "K2Node_ComponentBoundEvent", "K2Node_DynamicCast",
                                "K2Node_MacroInstance", "K2Node_SpawnActorFromClass", "K2Node_CreateWidget",
                                "K2Node_AddComponentByClass", "K2Node_CallParentFunction", "K2Node_InputAction") or (
            short in ("K2Node_CallFunction", "K2Node_CallArrayFunction") and any(p.category == EXEC for p in n.pins))
        height = (48 if tall_header else 32) + 24 * max(len(ins), len(outs), 1) + 12
        name = self._member_name(n)
        title = {"K2Node_IfThenElse": "Branch", "K2Node_ExecutionSequence": "Sequence", "K2Node_Self": "Self",
                 "K2Node_FunctionResult": "Return Node", "K2Node_MakeArray": "Make Array",
                 "K2Node_SpawnActorFromClass": "SpawnActor from class", "K2Node_CreateWidget": "Create Widget",
                 "K2Node_AddComponentByClass": "Add Component", "K2Node_DynamicCast": "Cast To Something",
                 "K2Node_MacroInstance": "ForEachLoop", "K2Node_Event": "Event " + name, "K2Node_CustomEvent": name,
                 "K2Node_InputAction": "InputAction " + name, "K2Node_ComponentBoundEvent": "On Component Begin Overlap (X)",
                 "K2Node_CallParentFunction": "Parent: " + name, "K2Node_CallDelegate": "Call " + name,
                 "K2Node_GetInputAxisValue": "Get " + name}.get(short, name)
        if short in ("K2Node_MakeStruct", "K2Node_BreakStruct"):
            title = "Make Struct"
        title_w = 7.5 * len(title) + (60 if tall_header else 40)
        in_w = (7 * max([len(p.name) for p in ins] or [0]) + 24) if ins else 0
        out_w = (7 * max([len(p.name) for p in outs] or [0]) + 24) if outs else 0
        width = max(title_w, in_w + out_w + 30, 110)
        if short in ("K2Node_VariableGet", "K2Node_Self"):
            width = max(100, 7 * len(name) + 70)
        return int(min(max(width, 110), 460)), int(height)

    def layout(self) -> Dict[str, Optional[List[int]]]:
        """Assigns x/y to every node (and adds the section comment boxes); idempotent until the graph changes."""
        if self._layout_info is not None:
            return self._layout_info
        self.nodes = [n for n in self.nodes if not self._is_comment(n)]
        by_name = {n.name: n for n in self.nodes}
        for n in self.nodes:
            n.width, n.height = self._estimate(n)
        has_entry = self.graph != "EventGraph"
        exec_nodes = [n for n in self.nodes if any(p.category == EXEC for p in n.pins)]
        exec_set = set(id(n) for n in exec_nodes)
        succ: Dict[int, List[Node]] = {}
        pred: Dict[int, List[Node]] = {id(n): [] for n in exec_nodes}
        for n in exec_nodes:
            succ[id(n)] = []
            for p in n.pins:
                if p.category == EXEC and p.direction == "out":
                    for tname, _ in p.links:
                        t = by_name.get(tname)
                        if t is not None and id(t) in exec_set:
                            succ[id(n)].append(t)
                            pred[id(t)].append(n)
        to_result = [a for a, _, b, _ in self.extra_links if b == "result"]
        roots = [n for n in exec_nodes if not pred[id(n)]]
        base_col = 1 if has_entry else 0
        col: Dict[int, int] = {}

        def column(n: Node, stack=()) -> int:
            if id(n) in col:
                return col[id(n)]
            if id(n) in stack:
                return base_col
            c = base_col
            for p in pred[id(n)]:
                c = max(c, column(p, stack + (id(n),)) + 1)
            col[id(n)] = c
            return c

        for n in exec_nodes:
            column(n)
        rows: Dict[int, int] = {}
        sec_of: Dict[int, str] = {}
        counter = [0]

        def visit(n: Node, row: int, sec: str) -> None:
            if id(n) in rows:
                return
            rows[id(n)], sec_of[id(n)] = row, sec
            for i, s in enumerate(succ[id(n)]):
                if id(s) in rows:
                    continue
                if i == 0:
                    visit(s, row, sec)
                else:
                    counter[0] += 1
                    visit(s, counter[0], sec)

        for r in roots + [n for n in exec_nodes if id(n) not in rows]:
            if id(r) not in rows:
                visit(r, counter[0], r.name)
                counter[0] += 1
        # pure trees hang from their first consumer in (column, row) order; nodes feeding only the result node hang
        # from a virtual sink in the last column
        order = sorted(exec_nodes, key=lambda n: (col[id(n)], rows[id(n)]))
        pure_set = set(id(n) for n in self.nodes if id(n) not in exec_set)
        placed: set = set()
        trees: Dict[int, Dict[int, List[Node]]] = {}
        consumers_of: Dict[int, List[Node]] = {}
        for n in self.nodes:
            for p in n.pins:
                if p.direction == "in" and p.category != EXEC:
                    for tname, _ in p.links:
                        t = by_name.get(tname)
                        if t is not None and id(t) in pure_set:
                            consumers_of.setdefault(id(t), []).append(n)

        def gather(consumer: Node, members: List[Node]) -> None:
            for p in consumer.pins:
                if p.direction == "in" and p.category != EXEC:
                    for tname, _ in p.links:
                        t = by_name.get(tname)
                        if t is not None and id(t) in pure_set and id(t) not in placed:
                            placed.add(id(t))
                            members.append(t)
                            gather(t, members)

        def depth_of(t: Node, members_ids: set, memo: Dict[int, int], root_ids: set) -> int:
            if id(t) in memo:
                return memo[id(t)]
            memo[id(t)] = 1
            d = 1
            for c in consumers_of.get(id(t), []):
                if id(c) in root_ids:
                    d = max(d, 1)
                elif id(c) in members_ids:
                    d = max(d, depth_of(c, members_ids, memo, root_ids) + 1)
            memo[id(t)] = d
            return d

        def build_tree(key: int, roots_: List[Node]) -> None:
            members: List[Node] = []
            for r in roots_:
                gather(r, members)
            ids = set(id(m) for m in members)
            memo: Dict[int, int] = {}
            tree: Dict[int, List[Node]] = {}
            for m in members:
                tree.setdefault(depth_of(m, ids, memo, set(id(r) for r in roots_)), []).append(m)
            trees[key] = tree

        for e in order:
            build_tree(id(e), [e])
        result_key = -1
        result_pure = [by_name[a] for a in to_result if a in by_name and id(by_name[a]) in pure_set]
        if has_entry and self.result_pins:
            placed_before = set(placed)
            fake = Node("result", "result", [], [Pin("execute", EXEC)] + [Pin("o%d" % i, INT) for i in range(self.result_pins - 1)])
            members: List[Node] = []
            for t in result_pure:
                if id(t) not in placed:
                    placed.add(id(t))
                    members.append(t)
                    gather(t, members)
            ids = set(id(m) for m in members)
            memo = {}
            tree = {}
            for m in members:
                tree.setdefault(depth_of(m, ids, memo, set()), []).append(m)
            trees[result_key] = tree
            del placed_before
        dangling = [n for n in self.nodes if id(n) in pure_set and id(n) not in placed]

        def tree_size(tree: Dict[int, List[Node]]) -> Tuple[int, int, Dict[int, int]]:
            widths = {d: max(m.width for m in ms) for d, ms in tree.items()}
            total_w = sum(w + self.PURE_DX for w in widths.values())
            total_h = max([sum(m.height + self.PURE_GAP for m in ms) for ms in tree.values()] or [0])
            return total_w, total_h, widths

        # columns and rows
        max_col = max([col[id(n)] for n in exec_nodes] or [base_col - 1])
        result_col = max_col + 1 if (has_entry and self.result_pins) else None
        ncols = (result_col if result_col is not None else max_col) + 1
        col_nodes: Dict[int, List[Node]] = {c: [] for c in range(ncols)}
        for n in exec_nodes:
            col_nodes[col[id(n)]].append(n)
        entry_w, entry_h = (200, 48 + 24 * self.entry_pins) if has_entry else (0, 0)
        result_w, result_h = (200, 48 + 24 * self.result_pins) if result_col is not None else (0, 0)
        col_w = {c: max([n.width for n in col_nodes[c]] or [0]) for c in range(ncols)}
        col_pure = {c: max([tree_size(trees[id(n)])[0] for n in col_nodes[c]] or [0]) for c in range(ncols)}
        if has_entry:
            col_w[0] = max(col_w[0], entry_w)
        if result_col is not None:
            col_w[result_col] = max(col_w[result_col], result_w)
            col_pure[result_col] = max(col_pure[result_col], tree_size(trees[result_key])[0])
        col_x = {0: 0}
        for c in range(1, ncols):
            col_x[c] = col_x[c - 1] + col_w[c - 1] + self.COL_GAP + col_pure[c]
        nrows = counter[0] if exec_nodes else 1
        row_h = {r: 0 for r in range(nrows)}
        row_sec = {}
        for n in exec_nodes:
            r = rows[id(n)]
            _, th, _ = tree_size(trees[id(n)])
            row_h[r] = max(row_h[r], n.height, self.PURE_DY + th)
            row_sec.setdefault(r, sec_of[id(n)])
        if has_entry:
            row_h[0] = max(row_h.get(0, 0), entry_h)
        result_row = 0
        for n in exec_nodes:
            if any(a == n.name and b == "result" for a, _, b, _ in self.extra_links):
                result_row = rows[id(n)]
                break
        if result_col is not None:
            _, th, _ = tree_size(trees[result_key])
            row_h[result_row] = max(row_h.get(result_row, 0), result_h, self.PURE_DY + th)
        row_y = {}
        y = 0
        for r in range(nrows):
            if r > 0:
                y += row_h[r - 1] + self.ROW_GAP
                if row_sec.get(r) != row_sec.get(r - 1):
                    y += self.SECTION_GAP
            row_y[r] = y

        def place_tree(tree: Dict[int, List[Node]], x_right: int, y_top: int) -> None:
            _, _, widths = tree_size(tree)
            x = x_right
            for d in sorted(tree):
                x -= widths[d] + self.PURE_DX
                yy = y_top + self.PURE_DY
                for m in tree[d]:
                    m.x, m.y = x, yy
                    yy += m.height + self.PURE_GAP

        for n in exec_nodes:
            n.x, n.y = col_x[col[id(n)]], row_y[rows[id(n)]]
            place_tree(trees[id(n)], n.x, n.y)
        info: Dict[str, Optional[List[int]]] = {"entry": [0, 0] if has_entry else None, "result": None}
        if result_col is not None:
            rx, ry = col_x[result_col], row_y[result_row]
            info["result"] = [rx, ry]
            place_tree(trees[result_key], rx, ry)
        if dangling:
            x = (col_x[ncols - 1] + col_w[ncols - 1] + self.COL_GAP) if exec_nodes or has_entry else 0
            yy = 0
            for m in dangling:
                m.x, m.y = x, yy
                yy += m.height + self.PURE_GAP
        # section comment boxes
        boxes: List[Tuple[str, List[Node]]] = []
        if self.doc is not None:
            boxes.append((self.doc, list(self.nodes)))
        else:
            members_by_sec: Dict[str, List[Node]] = {}
            for n in exec_nodes:
                members_by_sec.setdefault(sec_of[id(n)], []).append(n)
                for ms in trees[id(n)].values():
                    members_by_sec[sec_of[id(n)]].extend(ms)
            for root_name, title in self.sections.items():
                if root_name in members_by_sec:
                    boxes.append((title, members_by_sec[root_name]))
        for title, members in boxes:
            rects = [(m.x, m.y, m.x + m.width, m.y + m.height) for m in members]
            if self.doc is not None and has_entry:
                rects.append((0, 0, entry_w, entry_h))
                if info["result"]:
                    rects.append((info["result"][0], info["result"][1], info["result"][0] + result_w, info["result"][1] + result_h))
            if not rects:
                continue
            x0, y0 = min(r[0] for r in rects) - self.PAD, min(r[1] for r in rects) - self.PAD - self.TITLE_H
            x1, y1 = max(r[2] for r in rects) + self.PAD, max(r[3] for r in rects) + self.PAD
            self._comment_box(title, x0, y0, x1 - x0, y1 - y0)
        self._layout_info = info
        return info

    @property
    def layout_info(self) -> Dict[str, Optional[List[int]]]:
        return self.layout()

    def overlaps(self, margin: int = 8) -> List[str]:
        """Pairs of nodes whose rectangles intersect (comment boxes excluded; the entry/result rectangles included)."""
        info = self.layout()
        rects = [(n.name, n.x, n.y, n.x + n.width, n.y + n.height) for n in self.nodes if not self._is_comment(n)]
        if info["entry"]:
            rects.append(("entry", 0, 0, 200, 48 + 24 * self.entry_pins))
        if info["result"]:
            rects.append(("result", info["result"][0], info["result"][1], info["result"][0] + 200, info["result"][1] + 48 + 24 * self.result_pins))
        out = []
        for i, a in enumerate(rects):
            for b in rects[i + 1:]:
                if a[1] < b[3] - margin and b[1] < a[3] - margin and a[2] < b[4] - margin and b[2] < a[4] - margin:
                    out.append("%s x %s" % (a[0], b[0]))
        return out

    # ---- output ----
    def text(self) -> str:
        self.layout()
        return "\n".join(n.text() for n in self.nodes) + "\n"

    def write(self, out_dir: str) -> str:
        d = os.path.join(out_dir, self.blueprint)
        os.makedirs(d, exist_ok=True)
        path = os.path.join(d, "%s.txt" % self.graph)
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            f.write(self.text())
        return path


class Blueprint:
    """A whole Blueprint: asset, parent, components, variables, dispatchers, functions and graphs."""

    def __init__(self, asset_path: str, parent: str, description: str = ""):
        self.asset = asset_path
        self.name = asset_path.rsplit("/", 1)[1]
        self.parent = parent  # "/Script/Engine.Actor" or a Blueprint asset path
        self.description = description  # the Blueprint's description (content browser tooltip, class settings)
        self.components: List[dict] = []
        self.variables: List[dict] = []
        self.dispatchers: List[dict] = []
        self.functions: List[dict] = []
        self.graphs: List[Graph] = []
        self.defaults: Dict[str, object] = {}
        self.component_defaults: Dict[str, Dict[str, object]] = {}  # inherited component -> {property: value}
        self.required: List[dict] = []  # support assets the runner creates when missing

    def component_default(self, component: str, prop: str, value) -> None:
        """Class-default value of a property on an inherited (native or parent) component, e.g.
        component_default("VehicleMovement", "mass", 1950.0); property names as Python's set_editor_property takes them."""
        self.component_defaults.setdefault(component, {})[prop] = value

    def requires(self, asset: str, cls: str, factory: str) -> None:
        """An asset this Blueprint needs to exist (created by the runner through unreal.<cls> / unreal.<factory>())."""
        self.required.append({"asset": asset, "class": cls, "factory": factory})

    def component(self, name: str, cls: str, parent: str = "", **props) -> None:
        self.components.append({"name": name, "class": cls, "parent": parent, "properties": props})

    def variable(self, name: str, type_spec: str, default: str = "", category: str = "", editable: bool = False) -> None:
        self.variables.append({"name": name, "type": type_spec, "default": default, "category": category,
                               "editable": editable})

    def dispatcher(self, name: str, params: Optional[List[str]] = None) -> None:
        self.dispatchers.append({"name": name, "params": params or []})

    def function(self, name: str, inputs: Optional[List[str]] = None, outputs: Optional[List[str]] = None,
                 pure: bool = False, category: str = "Dead Fire", locals: Optional[List[str]] = None, doc: str = "") -> Graph:
        """locals: ["Name:TypeSpec[=Default]", ...] local variables of the function. doc: one-line description, shown
        as the function's tooltip and as the title of the comment box around its body."""
        self.functions.append({"name": name, "inputs": inputs or [], "outputs": outputs or [], "pure": pure,
                               "category": category, "locals": locals or [], "doc": doc})
        g = Graph(self.name, name)
        g.entry_pins = 1 + len(inputs or [])
        g.result_pins = (1 + len(outputs)) if outputs else 0
        g.doc = doc or None
        self.graphs.append(g)
        return g

    def event_graph(self) -> Graph:
        g = Graph(self.name, "EventGraph")
        self.graphs.append(g)
        return g

    def construction_script(self) -> Graph:
        g = Graph(self.name, "UserConstructionScript")
        self.graphs.append(g)
        return g

    def default(self, name: str, value) -> None:
        """Class-default value set on the CDO after compiling (numbers, bools, strings, or asset paths)."""
        self.defaults[name] = value

    def manifest(self) -> dict:
        return {
            "kind": "blueprint", "asset": self.asset, "parent": self.parent, "description": self.description,
            "components": self.components, "variables": self.variables, "dispatchers": self.dispatchers,
            "functions": self.functions,
            "graphs": [{"name": g.graph, "file": "%s.txt" % g.graph, "links": [list(l) for l in g.extra_links],
                        "layout": g.layout()}
                       for g in self.graphs if g.nodes],
            "defaults": self.defaults,
            "component_defaults": self.component_defaults,
            "requires": self.required,
        }

    def write(self, out_dir: str) -> str:
        d = os.path.join(out_dir, self.name)
        os.makedirs(d, exist_ok=True)
        for g in self.graphs:
            if g.nodes:
                g.write(out_dir)
                for pair in g.overlaps():
                    print("WARNING %s %s: overlap %s" % (self.name, g.graph, pair))
        path = os.path.join(d, "manifest.json")
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            json.dump(self.manifest(), f, indent=1)
        return path


class WidgetBlueprint(Blueprint):
    """A UMG Widget Blueprint: designer tree (applied by the runner through the plugin) plus graphs.

    widget(name, cls, parent, props, slot): cls like '/Script/UMG.TextBlock'; parent None = the root panel.
    props: text, font_size, color [r,g,b,a], justify (Left|Center|Right), percent, fill_color, brush_color,
           width_override, height_override, visibility (Visible|Collapsed|HitTestInvisible|...), or any property name.
    slot (canvas): anchors [minx,miny,maxx,maxy], alignment [x,y], position [x,y], size [w,h], auto_size bool.
    slot (boxes): padding [l,t,r,b], h_align (Left|Center|Right|Fill), v_align.
    """

    def __init__(self, asset_path: str, parent: str = "/Script/UMG.UserWidget", root_class: str = "/Script/UMG.CanvasPanel",
                 root_name: str = "Root", description: str = ""):
        super().__init__(asset_path, parent, description)
        self.root_class, self.root_name = root_class, root_name
        self.tree: List[dict] = []

    def widget(self, name: str, cls: str, parent: Optional[str] = None, props: Optional[dict] = None,
               slot: Optional[dict] = None) -> str:
        self.tree.append({"name": name, "class": cls, "parent": parent or "", "props": props or {}, "slot": slot or {}})
        return name

    def manifest(self) -> dict:
        m = super().manifest()
        m.update({"kind": "widget", "root_class": self.root_class, "root_name": self.root_name, "tree": self.tree})
        return m


class Struct:
    def __init__(self, asset_path: str):
        self.asset = asset_path
        self.name = asset_path.rsplit("/", 1)[1]
        self.members: List[dict] = []

    def member(self, name: str, type_spec: str, default: str = "") -> "Struct":
        self.members.append({"name": name, "type": type_spec, "default": default})
        return self

    def write(self, out_dir: str) -> str:
        d = os.path.join(out_dir, self.name)
        os.makedirs(d, exist_ok=True)
        path = os.path.join(d, "manifest.json")
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            json.dump({"kind": "struct", "asset": self.asset, "members": self.members}, f, indent=1)
        return path


class Enum:
    def __init__(self, asset_path: str, values: List[str]):
        self.asset = asset_path
        self.name = asset_path.rsplit("/", 1)[1]
        self.values = values

    def write(self, out_dir: str) -> str:
        d = os.path.join(out_dir, self.name)
        os.makedirs(d, exist_ok=True)
        path = os.path.join(d, "manifest.json")
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            json.dump({"kind": "enum", "asset": self.asset, "values": self.values}, f, indent=1)
        return path
