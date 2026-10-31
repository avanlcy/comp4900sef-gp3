"""Builds one mesh headless and writes <name>.fbx and <name>.json (spec 4.1):

    blender -b --factory-startup --python run_mesh.py -- --script <module> --name <SM_DF_x> --out <dir> [--dims <dims.json>]
"""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import dfmesh  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--script", required=True)
    ap.add_argument("--name", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--dims")
    a = ap.parse_args(sys.argv[sys.argv.index("--") + 1:])
    dims = {}
    if a.dims and os.path.isfile(a.dims):
        with open(a.dims, encoding="utf-8") as f:
            dims = json.load(f)
    os.makedirs(a.out, exist_ok=True)
    dfmesh.clear_scene()
    root = dfmesh.build_mesh(a.script, a.name, dims)
    dfmesh.export(root, os.path.join(a.out, a.name + ".fbx"))
    dfmesh.write_stats(root, os.path.join(a.out, a.name + ".json"))
    print("RUN_MESH OK %s" % a.name)


main()
