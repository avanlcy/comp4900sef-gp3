"""Finds the Blender executable the mesh pipeline runs headless (spec §4.1)."""
import os

DEFAULT = "C:/Program Files/Blender Foundation/Blender 5.2/blender.exe"
DOWNLOAD = "https://www.blender.org/download/lts/5-2/"


def find_blender():
    path = os.environ.get("DF_BLENDER") or DEFAULT
    if not os.path.isfile(path):
        raise FileNotFoundError("Blender 5.2 LTS not found at %s; install it from %s or set DF_BLENDER" % (path, DOWNLOAD))
    return path
