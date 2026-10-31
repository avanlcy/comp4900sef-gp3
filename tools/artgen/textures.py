"""Procedural PBR texture sets for Dead Fire: dusk in a burnt-out wasteland (spec 3). Each recipe is
`recipe(seed, size) -> {"BC": RGB[A] uint8, "N": RGB uint8 (DirectX), "ORM": RGB uint8}` and tiles seamlessly.

    python -I tools/artgen/build_all.py --kind textures      (writes art/textures/T_DF_<Name>_<Map>.png)

Every pattern is built from periodic noise (noise.py) or integer-frequency waves, so nothing needs a seam fix afterwards.
Feature sizes are fractions of the image, so a recipe looks the same at 128 px (tests) and 1024 px (shipping).
"""
import os

import numpy as np
from PIL import Image as PILImage

try:
    from . import catalog
    from .noise import cellular, fbm_tileable, height_to_normal, smoothstep
except ImportError:  # run as a plain script
    import catalog
    from noise import cellular, fbm_tileable, height_to_normal, smoothstep


def _rgb(hex_colour):
    h = hex_colour.lstrip("#")
    return np.array([int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4)], np.float32)


def _c(r, g, b):
    return np.array([r, g, b], np.float32)


def _mix(a, b, t):
    t = np.asarray(t, np.float32)[..., None]
    return a * (1 - t) + b * t


def _f(s, seed, base, octaves=4, aniso=1.0, p=0.5):
    return fbm_tileable(s, seed, octaves=octaves, base_freq=base, persistence=p, aniso=aniso)


def _grain(s, seed, px):
    """Noise with features about `px` pixels wide at 1024 px (scaled with the image)."""
    return fbm_tileable(s, seed, octaves=2, base_freq=max(2, int(round(s / px))), persistence=0.6)


def _ridge(n, width):
    """Thin lines along the 0.5 contour of a noise field (1 on the line)."""
    return 1.0 - smoothstep(0.0, width, np.abs(n - 0.5))


def _spread(n):
    """Re-centre a noise field on 0.5 with a spread of about +-0.25 (fbm min/max normalising leaves most pixels near the middle)."""
    return np.clip((n - n.mean()) / (n.std() * 4.0) + 0.5, 0.0, 1.0)


def _norm(a):
    a = a.astype(np.float32)
    return (a - a.min()) / max(float(a.max() - a.min()), 1e-6)


def _u8(a):
    return np.clip(np.rint(np.asarray(a, np.float32) * 255), 0, 255).astype(np.uint8)


def _finish(bc, height, strength, rough, ao=1.0, metal=0.0):
    """Pack the three maps. `strength` is the normal slope in pixels-per-height at 1024 px (scaled for smaller images)."""
    s = bc.shape[0]
    full = lambda v: np.broadcast_to(np.asarray(v, np.float32), (s, s))  # noqa: E731
    return {
        "BC": _u8(bc),
        "N": height_to_normal(height, strength * s / 1024.0),
        "ORM": _u8(np.stack([full(ao), full(rough), full(metal)], axis=-1)),
    }


def _coords(s):
    y, x = np.mgrid[0:s, 0:s].astype(np.float32) / s
    return x, y


# --- ground ------------------------------------------------------------------------------------------
def asphalt(seed, s):
    broad, grain, agg = _f(s, seed + 1, 3, 3), _spread(_grain(s, seed + 2, 2)), _spread(_grain(s, seed + 3, 4))
    f1, f2, _ = cellular(s, 3, seed + 6, jitter=1.0)
    stones = smoothstep(0.62, 0.78, agg)
    dark = smoothstep(0.38, 0.22, agg)
    # a few hairline cracks along cell borders, broken up by noise
    crack = (1 - smoothstep(0.0, 0.018, f2 - f1 + 0.1 * (broad - 0.5))) * smoothstep(0.45, 0.6, _f(s, seed + 5, 3, 3))
    col = _mix(_c(0.19, 0.19, 0.20), _c(0.30, 0.29, 0.28), broad)
    col = col * (0.68 + 0.64 * grain[..., None])
    col = _mix(col, _mix(_c(0.40, 0.38, 0.36), _c(0.62, 0.60, 0.57), grain), stones * 0.7)
    col = _mix(col, _c(0.06, 0.06, 0.07), dark * 0.55)
    col = _mix(col, _c(0.04, 0.04, 0.04), crack)
    h = 0.45 * grain + 0.5 * stones - 0.8 * crack + 0.15 * broad
    return _finish(col, _norm(h), 6, 0.88 - 0.12 * stones, 1.0 - 0.7 * crack - 0.25 * dark)


def dirt(seed, s):
    base = _rgb(catalog.GROUND["dirt"])
    macro, clod, grain = _f(s, seed + 1, 3, 3), _f(s, seed + 2, 14, 4), _grain(s, seed + 3, 2)
    f1, _, cv = cellular(s, 56, seed + 4, jitter=1.0)
    peb = (1 - smoothstep(0.16, 0.30, f1)) * (cv > 0.55)
    col = _mix(base * 0.72, base * 1.25, macro)
    col = col * (0.85 + 0.3 * clod[..., None]) * (0.92 + 0.16 * grain[..., None])
    col = _mix(col, _mix(_c(0.30, 0.27, 0.24), _c(0.52, 0.45, 0.38), cv), peb * 0.9)
    h = 0.55 * clod + 0.15 * grain + 0.6 * peb
    return _finish(col, _norm(h), 7, 0.92 - 0.08 * peb, 0.7 + 0.3 * clod - 0.3 * peb)


def ash_ground(seed, s):
    base = _rgb(catalog.GROUND["ash"])
    macro, soft, grain = _f(s, seed + 1, 2, 4), _f(s, seed + 2, 10, 4), _grain(s, seed + 3, 2)
    f1, f2, cv = cellular(s, 7, seed + 4)
    crack = 1 - smoothstep(0.0, 0.03, f2 - f1 + 0.1 * (soft - 0.5))
    col = _mix(base * 0.65, base * 1.45, macro * 0.7 + soft * 0.3)
    col = col * (0.8 + 0.4 * grain[..., None]) * (0.9 + 0.2 * cv[..., None])
    col = _mix(col, _c(0.06, 0.055, 0.05), crack * 0.45)
    h = 0.5 * soft + 0.3 * grain + 0.25 * cv - 0.3 * crack
    return _finish(col, _norm(h), 5, 0.93 - 0.05 * macro, 1 - 0.6 * crack)


def dry_grass(seed, s):
    base = _rgb(catalog.GROUND["grass"])
    blades, fine, patch = _f(s, seed + 1, 28, 4, aniso=7.0), _f(s, seed + 2, 90, 2, aniso=6.0), _f(s, seed + 3, 3, 3)
    clump = _f(s, seed + 4, 12, 3)
    col = _mix(_c(0.35, 0.28, 0.16), base * 1.2, blades * 0.6 + patch * 0.4)
    col = _mix(col, _c(0.55, 0.50, 0.33), smoothstep(0.62, 0.8, fine) * 0.6)
    col = col * (0.62 + 0.55 * clump[..., None] * (0.5 + 0.5 * blades[..., None]))
    h = 0.6 * blades + 0.3 * fine + 0.4 * clump
    return _finish(col, _norm(h), 7, 0.9 - 0.1 * blades, 0.45 + 0.55 * clump)


def rock(seed, s):
    base = _rgb(catalog.GROUND["rock"])
    f1, f2, cv = cellular(s, 4, seed + 1, jitter=1.0)
    x, y = _coords(s)
    warp = _f(s, seed + 2, 3, 3)
    strata = 0.5 + 0.5 * np.sin(2 * np.pi * (7 * y + 1.4 * warp))
    detail, fine = _f(s, seed + 3, 8, 5), _grain(s, seed + 4, 3)
    edge = 1 - smoothstep(0.0, 0.07, f2 - f1 + 0.22 * (detail - 0.5))  # ragged, not paving-straight
    col = _mix(base * 0.55, base * 1.4, cv * 0.45 + detail * 0.55)
    col = _mix(col, _c(0.36, 0.28, 0.22), smoothstep(0.55, 0.9, warp) * 0.35)  # iron-stained bands
    col = col * (0.82 + 0.18 * strata[..., None]) * (0.88 + 0.24 * fine[..., None])
    col = _mix(col, _c(0.05, 0.05, 0.05), edge * 0.6)
    h = 0.55 * cv + 0.35 * detail + 0.15 * strata + 0.15 * fine - 0.7 * edge
    return _finish(col, _norm(h), 12, 0.88 - 0.1 * detail - 0.06 * fine, (1 - 0.65 * edge) * (0.85 + 0.15 * fine))


def sand(seed, s):
    base = _rgb(catalog.GROUND["sand"])
    x, y = _coords(s)
    warp, grain, wind = _f(s, seed + 1, 2, 3), _grain(s, seed + 2, 1.5), _f(s, seed + 3, 6, 3)
    ripple = 0.5 + 0.5 * np.sin(2 * np.pi * (11 * y + 1.3 * warp + 0.5 * wind))  # integer frequency in y keeps the wrap seamless
    col = _mix(base * 0.78, base * 1.12, ripple * 0.7 + wind * 0.3)
    col = col * (0.9 + 0.2 * grain[..., None])
    col = _mix(col, _c(0.30, 0.24, 0.18), smoothstep(0.82, 0.95, grain) * 0.5)
    h = 0.6 * ripple + 0.2 * wind + 0.15 * grain
    return _finish(col, _norm(h), 5, 0.9 - 0.06 * ripple, 0.8 + 0.2 * ripple)


# --- structures --------------------------------------------------------------------------------------
def concrete(seed, s):
    mott, soot, grain = _f(s, seed + 1, 4, 5), _f(s, seed + 2, 2, 3), _grain(s, seed + 3, 2)
    pits = smoothstep(0.80, 0.9, _grain(s, seed + 4, 4))
    crack = _ridge(_f(s, seed + 5, 3, 4), 0.008) * smoothstep(0.45, 0.7, _f(s, seed + 6, 2, 2))
    yy = np.arange(s) + s // 4  # joints sit a quarter off the wrap, so no groove flank lands on the image edge
    half = s // 2
    d = np.minimum(yy % half, half - yy % half).astype(np.float32)  # joints at row/column 0 and s/2 (they wrap)
    joint = 1 - smoothstep(0.0, max(1.5, s / 400.0), d)
    joints = np.maximum(joint[:, None], joint[None, :])
    col = _mix(_c(0.40, 0.39, 0.37), _c(0.58, 0.57, 0.54), mott)
    col = col * (0.9 + 0.2 * grain[..., None])
    col = _mix(col, _c(0.10, 0.095, 0.09), smoothstep(0.5, 0.85, soot) * 0.55)  # scorched
    col = _mix(col, _c(0.07, 0.07, 0.07), np.maximum(pits * 0.7, crack * 0.85))
    col = _mix(col, _c(0.12, 0.12, 0.12), joints * 0.7)
    h = 0.5 * mott + 0.3 * grain - 0.5 * pits - 0.6 * crack - 0.7 * joints
    return _finish(col, _norm(h), 6, 0.9 - 0.12 * mott, 1 - 0.5 * pits - 0.5 * crack - 0.6 * joints)


def rust_metal(seed, s):
    big, mid, grain = _f(s, seed + 1, 3, 4), _f(s, seed + 2, 12, 4), _grain(s, seed + 3, 2)
    rust = smoothstep(0.42, 0.62, big * 0.7 + mid * 0.3)
    deep = smoothstep(0.55, 0.8, mid) * rust
    pit = smoothstep(0.78, 0.9, _grain(s, seed + 4, 3)) * rust
    steel = _mix(_c(0.20, 0.21, 0.23), _c(0.34, 0.35, 0.37), grain)
    rusty = _mix(_c(0.40, 0.17, 0.07), _c(0.70, 0.33, 0.12), mid)
    col = _mix(steel, rusty, rust)
    col = _mix(col, _c(0.20, 0.08, 0.04), deep * 0.6)
    col = _mix(col, _c(0.05, 0.03, 0.02), pit * 0.7)
    h = 0.4 * grain + 0.5 * mid * rust - 0.6 * pit
    return _finish(col, _norm(h), 8, 0.4 + 0.5 * rust, 1 - 0.5 * pit - 0.2 * rust, 1.0 - 0.9 * rust)


def painted_metal(seed, s):
    """BC is white times a grime mask: the paint colour comes from the material (MI_DF_Paint_*, MI_DF_Trim, ...)."""
    broad, grain = _f(s, seed + 1, 3, 3), _grain(s, seed + 2, 2)
    drips = _f(s, seed + 3, 10, 3, aniso=6.0)
    scratch = _ridge(_f(s, seed + 4, 40, 2, aniso=0.12), 0.02) * smoothstep(0.5, 0.7, _f(s, seed + 5, 5, 2))
    chips = smoothstep(0.84, 0.92, _grain(s, seed + 6, 4))
    grime = 1 - 0.22 * smoothstep(0.4, 0.9, broad) - 0.18 * smoothstep(0.55, 0.85, drips) - 0.08 * grain
    grime = grime - 0.35 * scratch - 0.45 * chips
    col = np.repeat(np.clip(grime, 0, 1)[..., None], 3, axis=-1)
    h = 0.12 * grain - 0.5 * scratch - 0.6 * chips + 0.05 * broad
    return _finish(col, _norm(h), 5, 0.42 + 0.25 * (1 - grime) + 0.15 * chips, 1 - 0.4 * chips, 0.15 + 0.7 * np.maximum(scratch, chips))


def crate_metal(seed, s):
    x, y = _coords(s)
    grain, mott, scuff = _grain(s, seed + 1, 2), _f(s, seed + 2, 4, 4), _f(s, seed + 3, 10, 3)
    px = np.arange(s, dtype=np.float32) + s / 4  # seams and rivets sit away from the wrap edge

    def wrapd(v, period):  # signed distance to the nearest multiple of `period`, wrapping
        return (v + period / 2) % period - period / 2
    dseam = np.abs(wrapd(px, s / 2))  # panel seams at 0 and s/2
    seam = (1 - smoothstep(0.0, max(2.0, s / 256.0), dseam))
    seams = np.maximum(seam[:, None], seam[None, :])
    r = s / 70.0
    ry = np.minimum(np.abs(wrapd(px - s / 24, s / 2)), np.abs(wrapd(px + s / 24, s / 2)))  # a row of rivets either side of a seam
    rx = np.abs(wrapd(px, s / 8))
    rivet_h = np.maximum(
        (1 - smoothstep(r * 0.55, r, np.hypot(rx[None, :], ry[:, None]))) * (np.abs(wrapd(px, s / 2))[None, :] > s / 40),
        (1 - smoothstep(r * 0.55, r, np.hypot(ry[None, :], rx[:, None]))) * (np.abs(wrapd(px, s / 2))[:, None] > s / 40))
    wear = smoothstep(0.55, 0.9, scuff) * 0.6 + seams * 0.25
    col = _mix(_c(0.25, 0.28, 0.27), _c(0.38, 0.40, 0.39), mott) * (0.9 + 0.2 * grain[..., None])
    col = _mix(col, _c(0.62, 0.62, 0.60), wear * 0.55)
    col = _mix(col, _c(0.05, 0.05, 0.05), seams * 0.7)
    col = _mix(col, col * 1.25, rivet_h * 0.6)
    h = 0.3 * grain + 0.25 * mott + 0.8 * rivet_h - 0.9 * seams
    return _finish(col, _norm(h), 8, 0.5 + 0.25 * (1 - wear) - 0.1 * rivet_h, 1 - 0.7 * seams, 0.85 - 0.3 * grain)


def rubber(seed, s):
    x, y = _coords(s)
    grain, mott = _grain(s, seed + 1, 1.5), _f(s, seed + 2, 5, 4)
    bump = np.sin(2 * np.pi * 24 * (x + y)) * np.sin(2 * np.pi * 24 * (x - y))  # fine diamond tread (integer frequencies)
    wornout = smoothstep(0.55, 0.9, mott)
    col = _mix(_c(0.07, 0.07, 0.07), _c(0.17, 0.165, 0.16), grain * 0.6 + wornout * 0.4)
    h = 0.35 * grain + 0.45 * (0.5 + 0.5 * bump) * (1 - 0.5 * wornout) + 0.1 * mott
    return _finish(col, _norm(h), 5, 0.82 - 0.15 * wornout, 0.8 + 0.2 * (0.5 + 0.5 * bump))


def fabric(seed, s):
    x, y = _coords(s)
    n = 64
    weave = np.cos(2 * np.pi * n * x) * np.cos(2 * np.pi * n * y)  # basket weave from integer frequencies
    over = 0.5 + 0.5 * np.sign(np.sin(2 * np.pi * (n / 2) * x) * np.sin(2 * np.pi * (n / 2) * y))
    thread, mott = _grain(s, seed + 1, 1.5), _f(s, seed + 2, 4, 4)
    col = _mix(_c(0.40, 0.40, 0.40), _c(0.72, 0.72, 0.72), 0.5 + 0.28 * weave * (0.4 + 0.6 * over) + 0.25 * (thread - 0.5))
    col = col * (0.85 + 0.3 * mott[..., None])
    h = 0.5 + 0.28 * weave * (0.4 + 0.6 * over) + 0.2 * thread
    return _finish(col, _norm(h), 7, 0.82 + 0.08 * (1 - thread), 0.6 + 0.4 * (0.5 + 0.5 * weave))


def wood(seed, s):
    """Dead-tree bark: tall, dark, deeply grooved."""
    gr = _f(s, seed + 1, 9, 4, aniso=9.0)
    fine, flake, tone = _f(s, seed + 2, 40, 3, aniso=7.0), _grain(s, seed + 3, 3), _f(s, seed + 4, 3, 3)
    groove = _ridge(gr, 0.1)
    col = _mix(_c(0.20, 0.15, 0.11), _c(0.42, 0.34, 0.26), 0.55 * fine + 0.45 * tone)
    col = _mix(col, _c(0.50, 0.48, 0.44), smoothstep(0.75, 0.9, flake) * 0.25)  # sun-bleached flakes
    col = _mix(col, _c(0.04, 0.03, 0.03), groove * 0.85)
    h = 0.55 * gr + 0.25 * fine - 0.8 * groove + 0.1 * flake
    return _finish(col, _norm(h), 10, 0.88 - 0.1 * fine, 1 - 0.7 * groove)


# --- effects -----------------------------------------------------------------------------------------
def fx_noise(seed, s):
    """Tileable noise in the three colour channels; the flame material scrolls and thresholds it."""
    return {"BC": np.stack([_u8(_f(s, seed + i, 4 + 2 * i, 5)) for i in range(3)], axis=-1)}


def _radius(s):
    y, x = np.mgrid[0:s, 0:s].astype(np.float32)
    c = (s - 1) / 2.0
    return np.hypot(x - c, y - c) / (s / 2.0), x - c, y - c


def smoke_puff(seed, s):
    r, dx, dy = _radius(s)
    billow, fine = _f(s, seed + 1, 3, 4), _f(s, seed + 2, 8, 3)
    shape = (1 - r) + (billow - 0.5) * 0.9 + (fine - 0.5) * 0.25
    alpha = smoothstep(0.0, 0.55, shape) * (1 - smoothstep(0.72, 0.98, r)) * 0.9
    light = np.clip(0.5 - 0.5 * (dx + dy) / (s / 2.0), 0, 1)  # lit from the upper left
    grey = 0.62 + 0.3 * light * 0.6 + 0.18 * (billow - 0.5) * 2
    rgb = np.repeat(np.clip(grey, 0, 1)[..., None], 3, axis=-1)
    return {"BC": np.concatenate([_u8(rgb), _u8(alpha)[..., None]], axis=-1)}


def scorch(seed, s):
    r, dx, dy = _radius(s)
    ang = np.arctan2(dy, dx)
    rng = np.random.default_rng(seed)
    ph = rng.random(4) * 6.28
    rays = 0.07 * np.sin(5 * ang + ph[0]) + 0.05 * np.sin(11 * ang + ph[1]) + 0.03 * np.sin(23 * ang + ph[2])  # integer multiples wrap at +-pi
    edge = r + (_f(s, seed + 1, 5, 4) - 0.5) * 0.7 + rays
    grain = _grain(s, seed + 2, 3)
    alpha = (1 - smoothstep(0.30, 0.85, edge)) * (0.8 + 0.2 * grain) * (1 - smoothstep(0.85, 0.99, r))
    rim = smoothstep(0.35, 0.8, edge)
    rgb = _mix(_c(0.05, 0.045, 0.04), _c(0.22, 0.14, 0.09), rim) * (0.8 + 0.4 * grain[..., None])
    return {"BC": np.concatenate([_u8(rgb), _u8(alpha)[..., None]], axis=-1)}


RECIPES = {
    "asphalt": asphalt, "dirt": dirt, "ash_ground": ash_ground, "dry_grass": dry_grass, "rock": rock, "sand": sand,
    "concrete": concrete, "rust_metal": rust_metal, "painted_metal": painted_metal, "crate_metal": crate_metal,
    "rubber": rubber, "fabric": fabric, "wood": wood, "fx_noise": fx_noise, "smoke_puff": smoke_puff, "scorch": scorch,
}


def save_png(array, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    PILImage.fromarray(array).save(path, optimize=False, compress_level=6)


def build(spec, out_dir):
    """Generate one TextureSet into out_dir as T_DF_<Name>_<Map>.png; returns the written paths."""
    maps = RECIPES[spec.recipe](spec.seed, spec.size)
    paths = []
    for m in spec.maps:
        path = os.path.join(out_dir, "%s_%s.png" % (spec.name, m))
        save_png(maps[m], path)
        paths.append(path)
    return paths
