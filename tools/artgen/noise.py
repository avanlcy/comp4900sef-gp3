"""Tileable noise and helpers for the Dead Fire texture recipes (numpy only).

Everything that fills a whole texture is periodic by construction (FFT-filtered noise, wrapped cells, integer-frequency
waves), so a texture tiles without a seam. Every function is deterministic in its seed.
"""
import numpy as np


def _rng(seed):
    return np.random.default_rng(int(seed) & 0xFFFFFFFF)


def smoothstep(a, b, x):
    t = np.clip((x - a) / (b - a), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def fbm_tileable(size, seed, octaves=5, base_freq=4, persistence=0.5, aniso=1.0):
    """Fractal noise in 0..1, float32 (size, size), periodic. `aniso` > 1 stretches the features along the image y axis."""
    rng = _rng(seed)
    white = rng.standard_normal((size, size))
    f = np.fft.fftfreq(size) * size  # cycles per image
    kx, ky = np.meshgrid(f, f)
    k = np.sqrt(kx * kx + (ky * aniso) ** 2)
    k[0, 0] = 1.0
    lk = np.log2(k)
    w = np.zeros_like(k)
    for o in range(octaves):  # one soft band per octave, so one FFT gives the whole fractal sum
        w += persistence ** o * np.exp(-((lk - np.log2(base_freq * 2.0 ** o)) ** 2) / (2 * 0.45 ** 2))
    w[0, 0] = 0.0
    n = np.fft.ifft2(np.fft.fft2(white) * w).real
    n = (n - n.min()) / (n.max() - n.min())
    return n.astype(np.float32)


def cellular(size, cells, seed, jitter=0.9):
    """Tileable cellular (Worley) noise. Returns (f1, f2, cell_value): the distances to the nearest and second nearest
    feature point in cell units, and a random 0..1 value per nearest cell."""
    rng = _rng(seed)
    px = rng.random((cells, cells)) * jitter + (1 - jitter) / 2
    py = rng.random((cells, cells)) * jitter + (1 - jitter) / 2
    val = rng.random((cells, cells))
    u = (np.arange(size) + 0.5) * cells / size
    cu = np.floor(u).astype(int)
    fu = u - cu
    f1 = np.full((size, size), 9.0)
    f2 = np.full((size, size), 9.0)
    cv = np.zeros((size, size))
    for dy in (-1, 0, 1):
        iy = (cu + dy) % cells
        for dx in (-1, 0, 1):
            ix = (cu + dx) % cells
            ox = px[iy[:, None], ix[None, :]] + dx - fu[None, :]
            oy = py[iy[:, None], ix[None, :]] + dy - fu[:, None]
            d = np.sqrt(ox * ox + oy * oy)
            nearer = d < f1
            f2 = np.where(nearer, f1, np.minimum(f2, d))
            cv = np.where(nearer, val[iy[:, None], ix[None, :]], cv)
            f1 = np.where(nearer, d, f1)
    return f1.astype(np.float32), f2.astype(np.float32), cv.astype(np.float32)


def height_to_normal(h, strength):
    """Height 0..1 (periodic) -> uint8 (n, n, 3) tangent-space normal, DirectX convention (green up-down flipped from OpenGL)."""
    h = np.asarray(h, np.float32)
    gx = (np.roll(h, -1, axis=1) - np.roll(h, 1, axis=1)) * 0.5 * strength
    gy = (np.roll(h, -1, axis=0) - np.roll(h, 1, axis=0)) * 0.5 * strength  # per image row, rows run down
    # OpenGL: (-dh/dx, -dh/dy_up, 1) = (-gx, +gy, 1); DirectX flips Y: (-gx, -gy, 1)
    n = np.stack([-gx, -gy, np.ones_like(h)], axis=-1)
    n /= np.linalg.norm(n, axis=-1, keepdims=True)
    return np.clip(np.rint((n * 0.5 + 0.5) * 255), 0, 255).astype(np.uint8)


def poisson_disc(width, height, radius, seed, accept=lambda x, y: True, k=30):
    """Bridson Poisson-disc sampling in a width x height rectangle (no wrapping). Points are (x, y) floats; those the
    `accept(x, y)` callback refuses are dropped before they can seed neighbours."""
    rng = _rng(seed)
    cell = radius / np.sqrt(2)
    gw, gh = int(np.ceil(width / cell)), int(np.ceil(height / cell))
    grid = -np.ones((gh, gw), int)
    pts, active = [], []

    def fits(x, y):
        gx, gy = int(x / cell), int(y / cell)
        for j in range(max(gy - 2, 0), min(gy + 3, gh)):
            for i in range(max(gx - 2, 0), min(gx + 3, gw)):
                q = grid[j, i]
                if q >= 0 and (pts[q][0] - x) ** 2 + (pts[q][1] - y) ** 2 < radius * radius:
                    return False
        return True

    def add(x, y):
        grid[int(y / cell), int(x / cell)] = len(pts)
        pts.append((x, y))
        active.append(len(pts) - 1)

    for _ in range(200):  # the accept region may exclude a random start point
        x, y = rng.random() * width, rng.random() * height
        if accept(x, y):
            add(x, y)
            break
    while active:
        a = int(rng.integers(len(active)))
        bx, by = pts[active[a]]
        for _ in range(k):
            ang, r = rng.random() * 2 * np.pi, radius * (1 + rng.random())
            x, y = bx + r * np.cos(ang), by + r * np.sin(ang)
            if 0 <= x < width and 0 <= y < height and accept(x, y) and fits(x, y):
                add(x, y)
                break
        else:
            active.pop(a)
    return pts
