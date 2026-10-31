"""Poly Haven downloader (CC0 textures and models), used only where Task 5's review swaps a generated asset for a scan.
Every download is recorded in polyhaven.lock.json: its url, `sha256` of the upstream file (a later download of the same
url whose hash differs is refused, spec 13) and `sha256_art` of the file written to art/.

PNGs are written at 8 bits per channel: Poly Haven ships most maps as 16-bit PNGs, which UE 4.27 imports as linear
RGBA16 and, once the importer marks a colour map sRGB, encodes to sRGB a second time (base colours 2.5-3x too bright).
Pillow keeps the high byte of each 16-bit sample, so the conversion is deterministic.

    python -I -c "from artgen import polyhaven; print(polyhaven.info('asphalt_02'))"
"""
import datetime
import hashlib
import io
import json
import os
import urllib.request

USER_AGENT = "DeadFire-artgen/1.0 (COMP4900SEF Group 3)"
API = "https://api.polyhaven.com"
HERE = os.path.dirname(os.path.abspath(__file__))
ART = os.path.join(os.path.dirname(os.path.dirname(HERE)), "art")
LOCK_PATH = os.path.join(HERE, "polyhaven.lock.json")

# Poly Haven map key -> suffix of the Unreal asset (arm = ambient occlusion / roughness / metallic, i.e. our ORM)
_MAPS = (("Diffuse", "BC"), ("nor_dx", "N"), ("arm", "ORM"))


def _get(url):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=120) as r:
        return r.read()


def _api(path):
    return json.loads(_get(API + path).decode("utf-8"))


def info(slug):
    """`/info/<slug>`: name, authors (dict of name -> role), categories, ..."""
    return _api("/info/" + slug)


def _load_lock(path):
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return {}


def _save_lock(path, lock):
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(lock, f, indent=1, sort_keys=True)
        f.write("\n")


def _lock_key(path):
    """Lock entries are keyed by the path relative to art/ (the committed lock describes art/ files)."""
    try:
        rel = os.path.relpath(path, ART).replace("\\", "/")
    except ValueError:  # another drive (a temporary folder)
        return os.path.basename(path)
    return os.path.basename(path) if rel.startswith("..") else rel


PNG_SIGNATURE = bytes([0x89]) + b"PNG" + bytes([13, 10, 26, 10])


def png_bit_depth(data):
    """Bits per channel of a PNG (its IHDR), or None when `data` is not a PNG."""
    return data[24] if data[:8] == PNG_SIGNATURE and len(data) > 25 else None


def to_8bit(data):
    """PNG bytes at 8 bits per channel (the same bytes when they already are); other files unchanged."""
    depth = png_bit_depth(data)
    if depth is None or depth <= 8:
        return data
    import numpy as np
    from PIL import Image
    im = Image.open(io.BytesIO(data))
    if im.mode.startswith("I"):  # 16-bit grey: Pillow keeps it 16-bit, scale it down with rounding
        im = Image.fromarray(((np.asarray(im).astype(np.uint32) + 128) // 257).astype(np.uint8), "L")
    else:  # RGB / RGBA / LA from 16-bit: Pillow already holds the high byte of each sample
        im = im.convert(im.mode)
    out = io.BytesIO()
    im.save(out, format="PNG")
    return out.getvalue()


def _sha(data):
    return hashlib.sha256(data).hexdigest()


def _download(url, path, slug, res, lock, pending, files):
    """Downloads url and checks it against the lock; queues (path, 8-bit bytes) in `files` (written by _write, after
    every file of the asset passed its check) and the lock entry in `pending`."""
    data = _get(url)
    digest = _sha(data)
    key = _lock_key(path)
    old = lock.get(key)
    if old and old.get("url") == url and old["sha256"] != digest:
        raise RuntimeError("%s: downloaded hash %s differs from the locked %s (%s)" % (key, digest, old["sha256"], url))
    art = to_8bit(data) if path.lower().endswith(".png") else data
    files.append((path, art))
    same = old and old.get("url") == url  # a new url (another resolution) is a new download
    pending[key] = {"slug": slug, "res": res, "url": url, "sha256": digest, "sha256_art": _sha(art),
                    "fetched": (old.get("fetched") if same else None) or datetime.date.today().isoformat()}


def _write(files):
    for path, data in files:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as f:
            f.write(data)


def fetch_texture(slug, res, out_dir, name, lock_path=None):
    """Download Diffuse, nor_dx and arm PNGs of `slug` at `res` ("1k", "2k") as T_DF_<name>_BC/_N/_ORM.png in out_dir."""
    lock_path = lock_path or LOCK_PATH
    lock = _load_lock(lock_path)
    files = _api("/files/" + slug)
    pending, paths, data = {}, [], []
    for ph_key, suffix in _MAPS:
        try:
            url = files[ph_key][res]["png"]["url"]
        except KeyError:
            raise RuntimeError("%s has no %s/%s/png" % (slug, ph_key, res))
        path = os.path.join(out_dir, "T_DF_%s_%s.png" % (name, suffix))
        _download(url, path, slug, res, lock, pending, data)
        paths.append(path)
    _write(data)
    lock.update(pending)
    _save_lock(lock_path, lock)
    return paths


def fetch_model(slug, res, out_dir=None, lock_path=None):
    """Download `gltf/<res>/gltf` and its included files into art/polyhaven/<slug>/; returns the .gltf path."""
    lock_path = lock_path or LOCK_PATH
    lock = _load_lock(lock_path)
    folder = os.path.join(out_dir or os.path.join(ART, "polyhaven"), slug)
    entry = _api("/files/" + slug)["gltf"][res]["gltf"]
    pending, data = {}, []
    main = os.path.join(folder, os.path.basename(entry["url"]))
    _download(entry["url"], main, slug, res, lock, pending, data)
    for rel, inc in entry.get("include", {}).items():
        _download(inc["url"], os.path.join(folder, *rel.split("/")), slug, res, lock, pending, data)
    _write(data)
    lock.update(pending)
    _save_lock(lock_path, lock)
    return main
