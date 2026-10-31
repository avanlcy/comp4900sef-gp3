"""UI images for Dead Fire: item icons, crosshair, damage vignette and the title logo (spec 3, 9).
Each recipe is `recipe(size) -> RGBA uint8 (h, w, 4)`; shapes are drawn 4x oversampled and reduced, so edges are smooth.

    python -I tools/artgen/build_all.py --kind images      (writes art/images/T_DF_<Name>.png)
"""
import os

import numpy as np
from PIL import Image as PILImage
from PIL import ImageDraw, ImageFilter, ImageFont

try:
    from . import catalog
except ImportError:  # run as a plain script
    import catalog

HERE = os.path.dirname(os.path.abspath(__file__))
RUSSO = os.path.join(HERE, "fonts", "RussoOne-Regular.ttf")
YAHEI_BOLD = "C:/Windows/Fonts/msyhbd.ttc"  # 死火 (Russo One has no CJK glyphs)
LANCZOS = getattr(PILImage, "Resampling", PILImage).LANCZOS
SS = 4  # oversampling
OUTLINE = (16, 12, 12)


def _rgb(hex_colour):
    return tuple(int(hex_colour[i:i + 2], 16) for i in (0, 2, 4))


def _dilate(mask, px):
    """Grow an 'L' mask by about `px` pixels (blur, then threshold: round corners, no slow rank filter)."""
    blurred = mask.filter(ImageFilter.GaussianBlur(px / 1.5))
    return blurred.point(lambda v: 255 if v > 16 else 0)


def _finish(layers, size):
    """Composite a list of RGBA layers at SS x size, reduce, return uint8. Transparent pixels keep the outline colour."""
    big = PILImage.new("RGBA", (size[0] * SS, size[1] * SS), OUTLINE + (0,))
    for layer in layers:
        big = PILImage.alpha_composite(big, layer)
    return np.asarray(big.resize(size, LANCZOS))


def _solid(mask, colour):
    layer = PILImage.new("RGBA", mask.size, colour + (0,))
    layer.putalpha(mask)
    return layer


def _draw_shapes(mask, shapes, u):
    """Shapes use a 100-unit square; ('poly'|'ell'|'rect'|'line'|'text', args, fill 255|0)."""
    d = ImageDraw.Draw(mask)
    for kind, args, fill in shapes:
        if kind == "poly":
            d.polygon([(x * u, y * u) for x, y in args], fill=fill)
        elif kind == "ell":
            d.ellipse([c * u for c in args], fill=fill)
        elif kind == "rect":
            d.rectangle([c * u for c in args], fill=fill)
        elif kind == "line":
            pts, w = args
            d.line([(x * u, y * u) for x, y in pts], fill=fill, width=int(w * u))
            for x, y in pts:  # round caps
                d.ellipse([(x - w / 2) * u, (y - w / 2) * u, (x + w / 2) * u, (y + w / 2) * u], fill=fill)
        elif kind == "text":
            text, px = args
            d.text((50 * u, 52 * u), text, fill=fill, font=ImageFont.truetype(RUSSO, int(px * u)), anchor="mm")


def _scaled(pts, k, cx=50, cy=50):
    return [(cx + (x - cx) * k, cy + (y - cy) * k) for x, y in pts]


def _lighter(colour, k=0.55):
    return tuple(int(c + (255 - c) * k) for c in colour)


def _icon(shapes, colour, details=None, size=(256, 256), outline=4.2):
    u = size[0] * SS / 100.0
    sil = PILImage.new("L", (size[0] * SS, size[1] * SS), 0)
    _draw_shapes(sil, shapes, u)
    layers = [_solid(_dilate(sil, outline * u), OUTLINE), _solid(sil, colour)]
    if details:
        overlay = PILImage.new("RGBA", sil.size, (0, 0, 0, 0))
        details(ImageDraw.Draw(overlay), u, colour)
        alpha = np.minimum(np.asarray(overlay.getchannel("A")), np.asarray(sil))  # details stay inside the shape
        overlay.putalpha(PILImage.fromarray(alpha))
        layers.append(overlay)
    return _finish(layers, size)


def _poly(d, u, pts, fill):
    d.polygon([(x * u, y * u) for x, y in pts], fill=fill)


def _box(d, u, box, fill):
    d.rectangle([c * u for c in box], fill=fill)


def _disc(d, u, box, fill):
    d.ellipse([c * u for c in box], fill=fill)


# --- icons -------------------------------------------------------------------------------------------
def icon_boost(size):
    bolt = [(60, 8), (24, 55), (44, 55), (36, 93), (78, 42), (55, 42)]
    return _icon([("poly", bolt, 255)], _rgb(catalog.ITEM_COLOURS["Boost"]), size=size)


def icon_shield(size):
    outer = [(50, 8), (86, 20), (86, 50), (72, 74), (50, 92), (28, 74), (14, 50), (14, 20)]
    col = _rgb(catalog.ITEM_COLOURS["Shield"])

    def details(d, u, c):
        _poly(d, u, _scaled(outer, 0.66, 50, 48), OUTLINE + (255,))
        _poly(d, u, _scaled(outer, 0.5, 50, 48), c + (255,))
        _poly(d, u, [(50, 28), (64, 34), (64, 52), (50, 70)], _lighter(c, 0.5) + (255,))
    return _icon([("poly", outer, 255)], col, details, size=size)


def icon_bomb(size):
    col = _rgb(catalog.ITEM_COLOURS["Bomb"])
    shapes = [("ell", (18, 32, 84, 98), 255), ("rect", (42, 24, 60, 38), 255),
              ("line", ([(51, 26), (58, 14), (68, 12)], 5), 255),
              ("poly", [(74, 4), (77, 11), (85, 11), (79, 16), (82, 24), (74, 19), (67, 24), (69, 16), (63, 11), (71, 11)], 255)]

    def details(d, u, c):
        _box(d, u, (40, 34, 62, 41), OUTLINE + (255,))
        _disc(d, u, (28, 50, 42, 66), _lighter(c, 0.55) + (255,))
        _poly(d, u, [(74, 4), (77, 11), (85, 11), (79, 16), (82, 24), (74, 19), (67, 24), (69, 16), (63, 11), (71, 11)], (255, 210, 31, 255))
    return _icon(shapes, col, details, size=size)


def icon_gun(size):
    col = _rgb(catalog.ITEM_COLOURS["Gun"])
    shapes = [("rect", (8, 24, 90, 46), 255),
              ("poly", [(54, 44), (80, 44), (88, 88), (64, 88)], 255),
              ("ell", (30, 42, 58, 70), 255), ("ell", (37, 49, 51, 63), 0)]

    def details(d, u, c):
        for x in (58, 66, 74):
            _box(d, u, (x, 28, x + 3, 42), OUTLINE + (255,))
        _box(d, u, (10, 28, 22, 31), _lighter(c, 0.55) + (255,))
        _box(d, u, (6, 31, 10, 41), OUTLINE + (255,))
    return _icon(shapes, col, details, size=size)


def icon_rpg(size):
    col = _rgb(catalog.ITEM_COLOURS["RPG"])
    nose = [(66, 32), (82, 32), (98, 47), (82, 62), (66, 62)]
    shapes = [("rect", (8, 40, 70, 56), 255), ("poly", [(8, 40), (2, 30), (2, 66), (8, 56)], 255), ("poly", nose, 255),
              ("poly", [(66, 32), (74, 16), (80, 32)], 255), ("poly", [(66, 62), (74, 78), (80, 62)], 255),
              ("rect", (30, 54, 42, 84), 255), ("rect", (48, 30, 58, 42), 255)]

    def details(d, u, c):
        _box(d, u, (12, 43, 60, 47), _lighter(c, 0.5) + (255,))
        _box(d, u, (62, 33, 66, 61), OUTLINE + (255,))
        _poly(d, u, [(82, 34), (96, 47), (82, 60)], _lighter(c, 0.35) + (255,))
        _box(d, u, (47, 40, 50, 56), OUTLINE + (255,))
    return _icon(shapes, col, details, size=size)


def icon_random(size):
    return _icon([("text", ("?", 96), 255)], _rgb(catalog.ITEM_COLOURS["Random"]), size=size)


def icon_empty(size):
    shapes = [("ell", (12, 12, 88, 88), 255), ("ell", (26, 26, 74, 74), 0), ("line", ([(28, 72), (72, 28)], 7), 255)]
    return _icon(shapes, (138, 143, 148), size=size)


# --- the rest ----------------------------------------------------------------------------------------
CROSSHAIR_OUTLINE_PX = 1.5   # Task 18 fix round 1: the dark outline round the white cross, in final pixels
CROSSHAIR_OUTLINE_ALPHA = 0.9


def crosshair(size):
    """Four white ticks with a gap round a centre dot, outlined in dark (OUTLINE) so the cross reads over a light sky or the
    light mannequin as well as over dark ground. The HUD tints the image red on a hit: the white turns red, the outline stays dark."""
    w, h = size
    k = 8
    mask = PILImage.new("L", (w * k, h * k), 0)
    d = ImageDraw.Draw(mask)
    c, t = w * k / 2, 1.6 * k
    for ang in range(4):  # four ticks with a gap around the centre
        dx, dy = [(1, 0), (0, 1), (-1, 0), (0, -1)][ang]
        d.line([(c + dx * 8 * k, c + dy * 8 * k), (c + dx * 26 * k, c + dy * 26 * k)], fill=255, width=int(t * 2))
    d.ellipse([c - 2.2 * k, c - 2.2 * k, c + 2.2 * k, c + 2.2 * k], fill=255)
    halo = mask.filter(ImageFilter.MaxFilter(2 * int(round(CROSSHAIR_OUTLINE_PX * k)) + 1))  # the cross grown by the outline width
    big = PILImage.new("RGBA", mask.size, OUTLINE + (0,))  # transparent pixels keep the outline colour (no light fringe)
    big = PILImage.alpha_composite(big, _solid(halo.point(lambda v: int(v * CROSSHAIR_OUTLINE_ALPHA)), OUTLINE))
    big = PILImage.alpha_composite(big, _solid(mask, (255, 255, 255)))
    return np.asarray(big.resize(size, LANCZOS))


def vignette(size):
    w, h = size
    y, x = np.mgrid[0:h, 0:w].astype(np.float32)
    r = np.hypot((x + 0.5 - w / 2) / (w / 2), (y + 0.5 - h / 2) / (h / 2))
    t = np.clip((r - 0.55) / (1.25 - 0.55), 0, 1)
    alpha = t * t * (3 - 2 * t) * 0.92
    rgb = np.empty((h, w, 3), np.uint8)
    rgb[...] = (200, 20, 20)
    return np.dstack([rgb, np.rint(alpha * 255).astype(np.uint8)])


def logo(size):
    w, h = size
    big = (w * SS, h * SS)
    mx, my = 40 * SS, 30 * SS

    probe = ImageDraw.Draw(PILImage.new("L", big, 0))

    def text_mask(text, font_path, px):
        font = ImageFont.truetype(font_path, px)
        return font, probe.textbbox((0, 0), text, font=font)
    latin_px = 200 * SS
    while True:  # largest Latin size at which "DEAD FIRE" + gap + 死火 fits the canvas
        lf, lb = text_mask("DEAD FIRE", RUSSO, latin_px)
        cf, cb = text_mask("死火", YAHEI_BOLD, int(latin_px * 0.82))
        gap = int(latin_px * 0.22)
        total = (lb[2] - lb[0]) + gap + (cb[2] - cb[0])
        tall = max(lb[3] - lb[1], cb[3] - cb[1])
        if total <= big[0] - 2 * mx and tall <= big[1] - 2 * my:
            break
        latin_px -= 4 * SS
    x0 = (big[0] - total) // 2
    mask = PILImage.new("L", big, 0)
    d = ImageDraw.Draw(mask)
    d.text((x0 - lb[0], (big[1] - (lb[3] - lb[1])) // 2 - lb[1]), "DEAD FIRE", font=lf, fill=255)
    d.text((x0 + (lb[2] - lb[0]) + gap - cb[0], (big[1] - (cb[3] - cb[1])) // 2 - cb[1]), "死火", font=cf, fill=255)
    ys, xs = np.mgrid[0:big[1], 0:big[0]].astype(np.float32)
    rows = np.where(np.asarray(mask).any(axis=1))[0]
    top, bottom = rows[0], rows[-1]
    t = (ys - top) / max(bottom - top, 1) + 0.05 * np.sin(xs / (22.0 * SS)) + 0.03 * np.sin(xs / (7.0 * SS) + 1.3)
    t = np.clip(t, 0, 1)
    stops = np.array([[255, 226, 80], [255, 150, 30], [236, 70, 18], [160, 22, 14]], np.float32)  # yellow core to ember red
    pos = t * (len(stops) - 1)
    i = np.minimum(pos.astype(int), len(stops) - 2)
    f = (pos - i)[..., None]
    fire = (stops[i] * (1 - f) + stops[i + 1] * f).astype(np.uint8)
    face = PILImage.fromarray(np.dstack([fire, np.full(big[::-1], 255, np.uint8)]), "RGBA")
    face.putalpha(mask)
    shadow = _solid(_dilate(mask, 7 * SS), OUTLINE)
    return _finish([shadow, face], size)


RECIPES = {
    "icon_boost": icon_boost, "icon_shield": icon_shield, "icon_bomb": icon_bomb, "icon_gun": icon_gun,
    "icon_rpg": icon_rpg, "icon_random": icon_random, "icon_empty": icon_empty,
    "crosshair": crosshair, "vignette": vignette, "logo": logo,
}


def build(spec, out_dir):
    """Generate one Image into out_dir as <name>.png; returns the written paths."""
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, spec.name + ".png")
    PILImage.fromarray(RECIPES[spec.recipe](tuple(spec.size))).save(path, optimize=False, compress_level=6)
    return [path]
