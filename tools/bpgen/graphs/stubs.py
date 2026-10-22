"""Signature-only manifests for Blueprints a later module fills in, so earlier modules can reference them.

generate_all.py runs this first; the real module for the same asset overwrites the folder afterwards. Every Blueprint
of the migration now has a real module, so this is empty; add a stub here when a new phase introduces a Blueprint
that existing graphs must call before its own module is written.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from df import OUT  # noqa: E402


def build():
    return []


if __name__ == "__main__":
    for b in build():
        print(b.write(OUT))
