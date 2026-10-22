"""Prints the C++ declaration of engine functions so generator modules use the exact names and parameter names.

    python -I tools/bpgen/sig.py KismetMathLibrary.SelectVector SplineComponent.GetLocationAndTangentAtSplinePoint
"""
import os
import re
import sys

ENGINE = os.environ.get("UE_ENGINE", r"D:\UE_4.27\Engine")
ROOTS = [os.path.join(ENGINE, "Source", "Runtime"), os.path.join(ENGINE, "Source", "Developer"),
         os.path.join(ENGINE, "Source", "Editor"), os.path.join(ENGINE, "Plugins")]
_INDEX = None


def class_header(cls):
    """Finds the header declaring class U<cls>/A<cls>."""
    global _INDEX
    if _INDEX is None:
        _INDEX = {}
        for root in ROOTS:
            for dp, _, files in os.walk(root):
                for f in files:
                    if f.endswith(".h"):
                        _INDEX.setdefault(f[:-2], []).append(os.path.join(dp, f))
    for name in (cls, cls.replace("Component", "Component")):
        for path in _INDEX.get(name, []):
            text = open(path, encoding="utf-8", errors="ignore").read()
            if re.search(r"class\s+\w*_API\s+[UA]%s\b|class\s+[UA]%s\b" % (cls, cls), text):
                return path, text
    for paths in _INDEX.values():
        for path in paths:
            if cls.lower() in os.path.basename(path).lower():
                text = open(path, encoding="utf-8", errors="ignore").read()
                if re.search(r"class\s+\w*_API\s+[UA]%s\b" % cls, text):
                    return path, text
    return None, None


def find(cls, fn):
    path, text = class_header(cls)
    if not text:
        return "%s.%s: class header not found" % (cls, fn)
    m = re.search(r"((?:UFUNCTION\([^\n]*\)\s*\n\s*)?[^\n;{]*\b%s\s*\([^;{]*\)[^;{]*)[;{]" % re.escape(fn), text)
    if not m:
        return "%s.%s: NOT FOUND in %s" % (cls, fn, os.path.relpath(path, ENGINE))
    decl = " ".join(m.group(1).split())
    return "%s.%s: %s" % (cls, fn, decl)


if __name__ == "__main__":
    for arg in sys.argv[1:]:
        cls, fn = arg.split(".", 1)
        print(find(cls, fn))
