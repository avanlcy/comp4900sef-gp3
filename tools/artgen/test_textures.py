"""Checks the generated textures and images: sizes, seamless tiling, determinism, normal maps, roughness, icon corners (plan Task 2).
Also writes contact sheets to art/_contact_textures.png and art/_contact_images.png for a visual check.

    python -I tools/artgen/test_textures.py
"""
import hashlib
import os
import sys
import tempfile

import numpy as np
from PIL import Image as PILImage
from PIL import ImageDraw

LANCZOS = getattr(PILImage, "Resampling", PILImage).LANCZOS

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
from artgen import catalog, images, noise, textures  # noqa: E402

ART = os.path.join(os.path.dirname(os.path.dirname(HERE)), "art")
NOT_TILING = ("smoke_puff", "scorch")  # radial decals: transparent at the edge instead of tiling

checks = 0
failures = []


def check(ok, msg):
    global checks
    checks += 1
    if not ok:
        failures.append(msg)


def load(path):
    return np.asarray(PILImage.open(path))


def digest(path):
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def seam_ratio(a):
    """(wrap difference, neighbouring difference) for rows and columns."""
    a = a.astype(np.float32)
    out = []
    for axis in (0, 1):
        wrap = np.abs(np.take(a, -1, axis) - np.take(a, 0, axis)).mean()
        inner = np.abs(np.diff(a, axis=axis)).mean()
        out.append((wrap, inner))
    return out


def test_noise():
    n = noise.fbm_tileable(128, 1)
    check(n.shape == (128, 128) and n.dtype == np.float32, "fbm shape/dtype %s %s" % (n.shape, n.dtype))
    check(0.0 <= float(n.min()) and float(n.max()) <= 1.0 and float(n.max() - n.min()) > 0.9, "fbm range")
    check(np.array_equal(n, noise.fbm_tileable(128, 1)), "fbm deterministic")
    check(not np.array_equal(n, noise.fbm_tileable(128, 2)), "fbm seed matters")
    for wrap, inner in seam_ratio(n):
        check(wrap <= 1.5 * inner, "fbm seamless %.4f vs %.4f" % (wrap, inner))
    ramp = np.tile(np.linspace(0, 1, 64, dtype=np.float32), (64, 1))  # rises towards +x
    nm = noise.height_to_normal(ramp, 16.0).astype(np.float32) / 255 * 2 - 1
    check(nm[32, 32, 0] < -0.1 and abs(nm[32, 32, 1]) < 0.02 and nm[32, 32, 2] > 0.5, "normal of an x ramp %s" % nm[32, 32])
    down = np.tile(np.linspace(0, 1, 64, dtype=np.float32)[:, None], (1, 64))  # rises towards +row (image down)
    nd = noise.height_to_normal(down, 16.0).astype(np.float32) / 255 * 2 - 1
    check(nd[32, 32, 1] < -0.1, "DirectX green: a slope rising downwards must give green < 0.5, got %s" % nd[32, 32, 1])
    pts = noise.poisson_disc(100, 80, 8, 3)
    check(len(pts) > 30 and pts == noise.poisson_disc(100, 80, 8, 3), "poisson_disc count / deterministic (%d)" % len(pts))
    check(all(0 <= x < 100 and 0 <= y < 80 for x, y in pts), "poisson_disc in bounds")
    p = np.array(pts)
    d = np.hypot(p[:, None, 0] - p[None, :, 0], p[:, None, 1] - p[None, :, 1]) + np.eye(len(p)) * 1e9
    check(d.min() >= 8 - 1e-6, "poisson_disc minimum spacing %.3f" % d.min())
    left = noise.poisson_disc(100, 80, 8, 3, accept=lambda x, y: x < 50)
    check(len(left) > 5 and all(x < 50 for x, y in left), "poisson_disc accept")


def test_png_bit_depth():
    """Every PNG the editor imports is 8 bits per channel: UE 4.27 imports a 16-bit PNG as linear RGBA16 and, with the
    sRGB flag the importer sets on colour maps, encodes it to sRGB twice (Task 5 fix round 1)."""
    for sub in ("textures", "images", "terrain"):
        folder = os.path.join(ART, sub)
        if not os.path.isdir(folder):
            continue
        for f in sorted(os.listdir(folder)):
            if f.lower().endswith(".png"):
                with open(os.path.join(folder, f), "rb") as h:
                    head = h.read(26)
                check(head[:4] == b"\x89PNG" and head[24] == 8, "%s/%s is %s-bit, not 8-bit" % (sub, f, head[24] if len(head) > 24 else "?"))


def test_textures():
    sheet = []
    for ts in [t for t in catalog.TEXTURES if t.source == "gen"]:
        check(ts.recipe in textures.RECIPES, "no texture recipe for %s (%s)" % (ts.name, ts.recipe))
        if ts.recipe not in textures.RECIPES:
            continue
        with tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as b:
            files_a = textures.build(ts, a)
            files_b = textures.build(ts, b)
            want = sorted("%s_%s.png" % (ts.name, m) for m in ts.maps)
            check(sorted(os.path.basename(f) for f in files_a) == want, "%s files %s" % (ts.name, files_a))
            maps = {}
            for f in files_a:
                m = os.path.basename(f)[len(ts.name) + 1:-4]
                img = load(f)
                maps[m] = img
                check(img.shape[:2] == (ts.size, ts.size), "%s_%s size %s" % (ts.name, m, img.shape))
                other = os.path.join(b, os.path.basename(f))
                check(os.path.exists(other) and digest(f) == digest(other), "%s_%s not deterministic" % (ts.name, m))
                if ts.recipe in NOT_TILING:
                    edge = [img[:, 0, 3], img[:, -1, 3], img[0, :, 3], img[-1, :, 3]] if img.shape[2] == 4 else [np.array([255])]
                    check(img.shape[2] == 4 and max(e.max() for e in edge) == 0, "%s_%s edge alpha must be 0" % (ts.name, m))
                    check(img.shape[2] == 4 and img[..., 3].max() > 128, "%s_%s is empty" % (ts.name, m))
                else:
                    for axis, (wrap, inner) in zip("rc", seam_ratio(img)):
                        check(wrap <= 1.5 * inner + 1e-6, "%s_%s seam (%s) %.3f > 1.5 x %.3f" % (ts.name, m, axis, wrap, inner))
            check(set(maps) == set(ts.maps), "%s maps %s" % (ts.name, sorted(maps)))
            if "N" in maps:
                n = maps["N"].astype(np.float32)[..., :3] / 255 * 2 - 1
                mean_len = float(np.linalg.norm(n, axis=2).mean())
                check(0.98 <= mean_len <= 1.02, "%s_N mean |n| %.3f" % (ts.name, mean_len))
                check(float(n[..., 2].min()) > 0, "%s_N has z <= 0" % ts.name)
            if "ORM" in maps:
                rough = float(maps["ORM"][..., 1].mean()) / 255
                check(0.3 <= rough <= 0.95, "%s_ORM roughness mean %.3f" % (ts.name, rough))
        small_a = textures.RECIPES[ts.recipe](ts.seed, 128)
        small_b = textures.RECIPES[ts.recipe](ts.seed + 1, 128)
        small_c = textures.RECIPES[ts.recipe](ts.seed, 128)
        key = sorted(small_a)[0]
        check(small_a[key].shape[:2] == (128, 128), "%s recipe ignores the size argument" % ts.name)
        check(all(np.array_equal(small_a[k], small_c[k]) for k in small_a), "%s recipe not deterministic in memory" % ts.name)
        check(any(not np.array_equal(small_a[k], small_b[k]) for k in small_a), "%s: a different seed gives the same maps" % ts.name)
        sheet.append((ts, maps))
    write_texture_sheet(sheet)


def lit_tile(maps, tile):
    """The base colour lit through its normal map and occlusion, so the sheet shows relief as well as colour."""
    bc = maps["BC"].astype(np.float32) / 255
    rgb = bc[..., :3]
    if "N" in maps:
        n = maps["N"].astype(np.float32)[..., :3] / 255 * 2 - 1
        light = np.array([-0.5, -0.5, 0.7], np.float32)  # from the upper left; the map is DirectX (+Y down)
        light /= np.linalg.norm(light)
        shade = np.clip(n @ light, 0, 1)[..., None] * 0.9 + 0.25
        ao = maps["ORM"][..., :1].astype(np.float32) / 255 if "ORM" in maps else 1.0
        rgb = rgb * shade * (0.5 + 0.5 * ao)
    if bc.shape[2] == 4:
        rgb = rgb * bc[..., 3:4] + 0.12 * (1 - bc[..., 3:4])
    return PILImage.fromarray((np.clip(rgb, 0, 1) * 255).astype(np.uint8)).resize((tile, tile), LANCZOS)


def write_texture_sheet(sheet, cols=6, tile=256):
    rows = (len(sheet) + cols - 1) // cols
    canvas = PILImage.new("RGB", (cols * tile, rows * (tile + 16)), (20, 20, 20))
    d = ImageDraw.Draw(canvas)
    for i, (ts, maps) in enumerate(sheet):
        x, y = (i % cols) * tile, (i // cols) * (tile + 16)
        canvas.paste(lit_tile(maps, tile), (x, y + 16))
        d.text((x + 4, y + 3), ts.name[5:], fill=(230, 230, 230))
    os.makedirs(ART, exist_ok=True)
    canvas.save(os.path.join(ART, "_contact_textures.png"))


def test_images():
    sheet = {}
    for im in [i for i in catalog.IMAGES if i.recipe not in ("todo", "terrain")]:  # the splats: test_terrain.py
        check(im.recipe in images.RECIPES, "no image recipe for %s (%s)" % (im.name, im.recipe))
        if im.recipe not in images.RECIPES:
            continue
        with tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as b:
            fa = images.build(im, a)
            fb = images.build(im, b)
            check(len(fa) == 1 and os.path.basename(fa[0]) == im.name + ".png", "%s files %s" % (im.name, fa))
            arr = load(fa[0])
            check(arr.shape == (im.size[1], im.size[0], 4), "%s size %s, catalogue %s" % (im.name, arr.shape, im.size))
            check(digest(fa[0]) == digest(fb[0]), "%s not deterministic" % im.name)
            check(arr[..., 3].max() > 200, "%s is empty" % im.name)
            if im.name.startswith("T_DF_Icon_"):
                corners = [arr[0, 0, 3], arr[0, -1, 3], arr[-1, 0, 3], arr[-1, -1, 3]]
                check(max(corners) == 0, "%s corner alpha %s" % (im.name, corners))
                kind = im.name.split("_")[-1]
                if kind in catalog.ITEM_COLOURS:
                    want = np.array([int(catalog.ITEM_COLOURS[kind][i:i + 2], 16) for i in (0, 2, 4)])
                    opaque = arr[arr[..., 3] > 200][:, :3].astype(int)
                    near = (np.abs(opaque - want).max(axis=1) < 24).mean()
                    check(near > 0.25, "%s: only %.0f%% of its pixels are the item colour" % (im.name, near * 100))
                    dark = (opaque.max(axis=1) < 60).mean()
                    check(dark > 0.03, "%s has no dark outline (%.1f%%)" % (im.name, dark * 100))
            if im.name == "T_DF_Crosshair":
                # Task 18 fix round 1: a white cross (the HUD tints it red on a hit) with a dark outline, so it reads over a light
                # sky or the mannequin: every near-white opaque pixel is white, and a ring of dark opaque pixels surrounds it
                opaque = arr[arr[..., 3] > 200][:, :3].astype(int)
                white = (opaque.min(axis=1) >= 250).sum()
                dark = (opaque.max(axis=1) < 60).sum()
                check(white > 20, "crosshair must have a white core (%d white pixels)" % white)
                check(dark >= white, "crosshair has no dark outline (%d dark vs %d white opaque pixels)" % (dark, white))
                check(arr[0, 0, 3] == 0 and arr[32, 32, :3].min() >= 250, "crosshair: clear corner, white centre dot %s" % arr[32, 32])
            if im.name == "T_DF_Vignette":
                check(arr[256, 256, 3] == 0 and arr[0, 256, 3] > 100 and arr[256, 0, 3] > 100, "vignette: clear centre, red edge")
                check(arr[0, 256, 0] > 150 and arr[0, 256, 1] < 80, "vignette must be red %s" % arr[0, 256])
            if im.name == "T_DF_Logo":
                check((arr[..., 3] > 128).mean() > 0.12, "logo is nearly empty")
                check(arr[0, 0, 3] == 0, "logo background must be transparent")
            sheet[im.name] = arr
    write_image_sheet(sheet)


def write_image_sheet(pick):
    canvas = PILImage.new("RGBA", (1024, 700), (64, 64, 70, 255))

    def put(name, xy, size=None):
        if name not in pick:
            return
        img = PILImage.fromarray(pick[name], "RGBA")
        canvas.alpha_composite(img.resize(size, LANCZOS) if size else img, xy)
    icons = sorted(n for n in pick if n.startswith("T_DF_Icon_"))
    for i, name in enumerate(icons):
        put(name, (8 + i * 72, 4), (64, 64))     # the size they are read at in the HUD
        put(name, (8 + i * 136, 80), (128, 128))
    put("T_DF_Logo", (0, 230))
    put("T_DF_Vignette", (8, 500), (180, 180))
    put("T_DF_Crosshair", (300, 560), (64, 64))
    os.makedirs(ART, exist_ok=True)
    canvas.convert("RGB").save(os.path.join(ART, "_contact_images.png"))


def main():
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
            except Exception as e:  # a crashing check is a failure, not a traceback that hides the others
                failures.append("%s raised %s: %s" % (name, type(e).__name__, e))
    if failures:
        for f in failures[:60]:
            print("FAIL: " + f)
        print("%d of %d checks failed" % (len(failures), checks))
        sys.exit(1)
    print("OK: %d checks" % checks)


if __name__ == "__main__":
    main()
