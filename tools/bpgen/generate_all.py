"""Regenerates every Blueprint manifest and graph text under comp4900sef/Script/paste.

    python -I tools/bpgen/generate_all.py

Order matters only for stubs (written first, overwritten by the real module of the same asset).
"""
import importlib.util
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from df import OUT  # noqa: E402

MODULES = ["stubs", "data", "weapon", "character", "vehicle", "racer", "track", "checkpoint", "game_mode", "hud", "items", "tests", "tests_items"]


def load(name):
    path = os.path.join(HERE, "graphs", name + ".py")
    if not os.path.exists(path):
        return None
    spec = importlib.util.spec_from_file_location("graph_" + name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main():
    out = os.path.abspath(OUT)
    if os.path.isdir(out):
        shutil.rmtree(out)  # stale graph files of renamed functions must not linger
    count = 0
    for name in MODULES:
        mod = load(name)
        if mod is None:
            continue
        assets = mod.build()
        for asset in assets if isinstance(assets, list) else [assets]:
            asset.write(out)
            count += 1
    print("generated %d manifests into %s" % (count, out))


if __name__ == "__main__":
    main()
