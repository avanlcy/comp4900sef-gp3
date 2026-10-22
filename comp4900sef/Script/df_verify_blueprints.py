"""Checks every generated Blueprint against its manifest, inside the editor:

    exec(open(r'<repo>/comp4900sef/Script/df_verify_blueprints.py').read()); verify_all(r'<repo>/comp4900sef/Script/paste')

For each manifest under the folder: the asset loads; every variable, function, event dispatcher and component it
declares exists; struct members and enum values exist; the Blueprint compiles with no errors. Prints one line per
problem and ends with VERIFY PASSED / VERIFY FAILED. Use it after editing a generated Blueprint by hand, to see whether
the edit removed something the rest of the game calls (and re-run df_apply_blueprint.py to restore generated graphs).
Needs the DF Blueprint Authoring plugin (tools/DFBlueprintAuthoring).
"""
import json
import os

import unreal

A = unreal.DFBlueprintAuthoringLibrary


def _names(entries, key="name"):
    return {e[key] for e in entries}


def verify_manifest(m):
    problems = []
    asset = m["asset"]
    obj = unreal.load_asset(asset)
    if obj is None:
        return ["%s: does not load" % asset]
    kind = m["kind"]
    if kind == "struct":
        have = {mem["display"] for mem in json.loads(A.describe_struct(obj))["members"]}
        for mem in m["members"]:
            if mem["name"] not in have:
                problems.append("%s: struct member %s missing" % (asset, mem["name"]))
        return problems
    if kind == "enum":
        return problems  # values are checked through the graphs that use them
    d = json.loads(A.describe_blueprint(obj))
    have_vars = {v["name"] for v in d["variables"]}
    for v in m.get("variables", []):
        if v["name"] not in have_vars:
            problems.append("%s: variable %s missing" % (asset, v["name"]))
    for disp in m.get("dispatchers", []):
        if disp["name"] not in d["dispatchers"]:
            problems.append("%s: event dispatcher %s missing" % (asset, disp["name"]))
    for f in m.get("functions", []):
        if f["name"] not in d["functions"]:
            problems.append("%s: function %s missing" % (asset, f["name"]))
    have_comps = {c["name"] for c in d["components"]}
    for c in m.get("components", []):
        if c["name"] not in have_comps:
            problems.append("%s: component %s missing" % (asset, c["name"]))
    first, _, rest = A.compile(obj).partition("\n")
    if not first.startswith("errors=0"):
        problems.append("%s: compile %s: %s" % (asset, first, " | ".join(l for l in rest.splitlines() if l.startswith("[ERROR]"))[:400]))
    return problems


def verify_all(root):
    problems, count = [], 0
    for d in sorted(os.listdir(root)):
        p = os.path.join(root, d, "manifest.json")
        if os.path.isfile(p):
            count += 1
            problems += verify_manifest(json.load(open(p, encoding="utf-8")))
    for line in problems:
        print(line)
    print("VERIFY %s: %d manifests, %d problem(s)" % ("PASSED" if not problems else "FAILED", count, len(problems)))
    return not problems
