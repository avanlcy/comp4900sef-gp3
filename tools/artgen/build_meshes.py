"""Builds one catalogue mesh by running Blender headless (blender/run_mesh.py); returns the stats the runner wrote.

    from artgen import build_meshes;  build_meshes.build(spec, out_dir)
"""
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
from artgen.blender_path import find_blender  # noqa: E402

RUNNER = os.path.join(HERE, "blender", "run_mesh.py")
DIMS = os.path.join(HERE, "data", "dims.json")
TIMEOUT_S = 120


def build(spec, out_dir):
    """spec is a catalog.Mesh; writes out_dir/<name>.fbx and .json and returns the parsed stats."""
    os.makedirs(out_dir, exist_ok=True)
    cmd = [find_blender(), "-b", "--factory-startup", "--python", RUNNER, "--",
           "--script", spec.script, "--name", spec.name, "--out", out_dir]
    if os.path.isfile(DIMS):
        cmd += ["--dims", DIMS]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=TIMEOUT_S)
    stats_path = os.path.join(out_dir, spec.name + ".json")
    if r.returncode != 0 or "RUN_MESH OK" not in r.stdout or not os.path.isfile(stats_path):
        raise RuntimeError("Blender failed building %s (exit %s):\n%s\n%s" % (spec.name, r.returncode, r.stdout[-1500:], r.stderr[-1500:]))
    with open(stats_path, encoding="utf-8") as f:
        return json.load(f)
