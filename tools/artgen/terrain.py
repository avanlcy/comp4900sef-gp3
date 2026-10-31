"""Terrain and scatter for the shipped tracks (Phase 7, spec 8.1 and 8.3), from a track export (df_export_tracks.py):

    build(track_json, out_dir, seed) -> dict

track_json is tools/artgen/data/tracks/<MapName>.json; <T> is that map's terrain name in catalog.TERRAINS. Writes into
out_dir (art/terrain/ from build_all.py --kind terrain):
- <T>.r16: N x N little-endian uint16, row-major with the row index j = Y and the column index i = X (what the plugin's
  CreateLandscapeFromRaw / ALandscapeProxy::Import read). Vertex (i, j) is at world (origin.x + i * STEP_CM,
  origin.y + j * STEP_CM) cm and Z = (h - 32768) * Z_SCALE / 128 cm, the landscape standing at Z 0 with scale
  (100, 100, Z_SCALE).
- T_DF_Splat_<T>.png: SPLAT^2 RGBA, R dirt, G ash and dry grass, B rock, A sand, the four summing to 255. Pixel (c, r)
  covers world origin + ((c, r) + 0.5) * SIZE_CM / SPLAT, which is where M_DF_Terrain samples it
  ((WorldPosition.xy - TerrainOrigin) / TerrainSize).
- <T>.terrain.json: {"origin": [x, y] (the landscape's location = its corner, vertex (0, 0); a multiple of 100 cm, chosen
  so the square is centred on the track's bounding box), "size_cm", "z_scale", "vertices", "spacing_cm", ...}.
- <T>.scatter.json: [{"mesh": "SM_DF_Rock01", "blocking": true, "transforms": [[x, y, z, yaw, scale], ...]}, ...] in
  world cm and degrees; z is the generated heightmap under (x, y), so the editor never needs numpy.
Every random choice comes from the seed: the same seed gives the same bytes.
"""
import json
import math
import os

import numpy as np
from PIL import Image as PILImage

from artgen import catalog, noise

N = 1009                  # vertices per side: 126 x 8 + 1 (8 x 8 components of 2 x 2 sections of 63 quads)
STEP_CM = 100             # vertex spacing, the landscape's X/Y scale
SIZE_CM = (N - 1) * STEP_CM   # 100,800 cm square
L_M = SIZE_CM / 100.0     # side in metres (vertex index i is at i metres from the origin)
Z_SCALE = 100             # Z (cm) = (h - 32768) * Z_SCALE / 128
SPLAT = 1024

# spec 8.1 (metres)
ROAD_Z = -0.08                       # just under the road tops (0 and -2 cm)
ROAD_FLAT, ROAD_BLEND = 9.0, 25.0    # -8 cm to 9 m from a road centre line, smoothstep into the field by 25 m
FIELD_AMPLITUDE = ((60.0, 0.5), (150.0, 6.0), (300.0, 40.0))  # fBm amplitude by road distance, smooth between
RIDGE_BAND, RIDGE_TOP = 150.0, 120.0  # the ring within 150 m of the edge rises to 120 m
RIDGE_WOBBLE = 40.0                   # the ring's foot wanders by this much (noise), so it is not a straight wall
RIDGE_CORNER = 300.0                  # the ring's corners are rounded (no crease along the square's diagonals)
PADS = {"crates": 6.0, "target_car": 6.0, "gates": 12.0, "props": 12.0}  # flattened to -8 cm within these radii
PAD_BLEND = 10.0                      # back to the surrounding height over this far beyond a pad
SHOULDER = 14.0                       # splat R: dirt to 14 m from a road centre line
ROCK_SLOPE, ROCK_HEIGHT = 28.0, 30.0  # splat B: rock above 28 degrees or 30 m
SAND_LOW = 3.0                        # splat A: sand patches only below this height

# spec 8.3: (minimum distance from any road centre line in m, blocking, meshes, category weight)
SCATTER = [
    (10.0, False, ("SM_DF_Debris01", "SM_DF_Debris02"), 0.25),                                    # debris, no collision
    (14.0, True, ("SM_DF_Rock01", "SM_DF_Rock02", "SM_DF_Rock03", "SM_DF_Rock04", "SM_DF_Barrel",
                  "SM_DF_TyreStack", "SM_DF_CarWreck"), 0.45),                                    # rocks, barrels, tyres, wrecks
    # dead trees, containers, billboards, light towers; the spec lists the scrap fence among the meshes but in no
    # distance band, so it takes the farthest one with the other large structures
    (25.0, True, ("SM_DF_DeadTree01", "SM_DF_DeadTree02", "SM_DF_Container", "SM_DF_ScrapFence", "SM_DF_Billboard",
                  "SM_DF_LightTower"), 0.30),
]
SCATTER_SPACING = 18.0      # Poisson-disc radius
SCATTER_REACH = 220.0       # no scatter farther than this from a road (the hills beyond are out of play)
SCATTER_MAX_SLOPE = 25.0    # nothing stands on a steeper face
SCATTER_KEEP = (0.2, 10.0, 100.0)  # keep probability 0.2 at 10 m rising smoothly to 1 at 100 m: density rises with distance
SCATTER_ROAD_MARGIN = 0.1   # on top of the minima: the samples are 2 m apart, so the spline can be ~4 cm nearer than
#                             the nearest sample at 14 m (Task 22 checks blocking instances against the splines)
FEATURE_CLEAR = 10.0        # from crates, gates, props and the target car
START_BOX = (60.0, 20.0)    # 60 m past the start line (along the start's yaw), +-20 m to either side
MAX_INSTANCES = 500
SCALE_RANGE = (0.85, 1.2)


def _smooth(a, b, x):
    return noise.smoothstep(a, b, x)


def _noise(seed, base_freq, octaves, persistence=0.25):
    """fBm 0..1 on the vertex grid (1 px = 1 m; the 1024 px tile is cropped to N). fbm_tileable filters white noise, so
    an octave holds 4x the modes of the one below: persistence 0.25 halves the amplitude per octave (rolling hills);
    the textures' 0.5 keeps every octave as strong, which at 40 m gives 60-degree rubble."""
    return noise.fbm_tileable(1024, seed, octaves=octaves, base_freq=base_freq, persistence=persistence)[:N, :N].astype(np.float64)


def _max3(a):
    """3 x 3 maximum filter (edges repeated)."""
    p = np.pad(a, 1, mode="edge")
    return np.max([p[dj:dj + a.shape[0], di:di + a.shape[1]] for dj in range(3) for di in range(3)], axis=0)


def track_points(track):
    """(n, 2) world cm: every road sample, crate, gate, prop, the target car and the start."""
    pts = [p[:2] for road in track["roads"] for p in road]
    pts += track["crates"] + track["gates"] + track["props"] + [track["target_car"], track["start"][:2]]
    return np.array(pts, np.float64)


def origin_for(track):
    """The landscape corner (cm, a multiple of 100) that centres the SIZE_CM square on the track's bounding box."""
    pts = track_points(track)
    centre = (pts.min(axis=0) + pts.max(axis=0)) / 2
    return [int(math.floor((c - SIZE_CM / 2) / 100.0 + 0.5)) * 100 for c in centre]


def road_distance(px, py, samples, chunk=8192):
    """Distance (m) from every point to the nearest road sample: brute force over the samples, chunked, using
    |p - s|^2 = |p|^2 + |s|^2 - 2 p.s (float64, local metres)."""
    p = np.stack([np.ravel(px), np.ravel(py)], axis=1).astype(np.float64)
    s = np.asarray(samples, np.float64)
    s2 = (s * s).sum(axis=1)
    out = np.empty(len(p))
    for k in range(0, len(p), chunk):
        q = p[k:k + chunk]
        out[k:k + chunk] = ((q * q).sum(axis=1)[:, None] + s2[None, :] - 2.0 * (q @ s.T)).min(axis=1)
    return np.sqrt(np.maximum(out, 0.0)).reshape(np.shape(px))


def sample(grid, u, v):
    """Bilinear sample of a vertex grid (row = Y) at local metres (u along X, v along Y)."""
    u = np.clip(u, 0, N - 1 - 1e-9)
    v = np.clip(v, 0, N - 1 - 1e-9)
    i, j = np.floor(u).astype(int), np.floor(v).astype(int)
    fu, fv = u - i, v - j
    return (grid[j, i] * (1 - fu) * (1 - fv) + grid[j, i + 1] * fu * (1 - fv) + grid[j + 1, i] * (1 - fu) * fv
            + grid[j + 1, i + 1] * fu * fv)


def edge_distance(x, y):
    """Distance (m) in from the landscape border, to a rounded-corner square (local metres)."""
    ex, ey = np.minimum(x, L_M - x), np.minimum(y, L_M - y)
    return RIDGE_CORNER - np.hypot(np.maximum(RIDGE_CORNER - ex, 0.0), np.maximum(RIDGE_CORNER - ey, 0.0))


def _amplitude(d):
    (d0, a0), (d1, a1), (d2, a2) = FIELD_AMPLITUDE
    return a0 + (a1 - a0) * _smooth(d0, d1, d) + (a2 - a1) * _smooth(d1, d2, d)


def _pads(track, origin):
    """[(x, y, radius)] in local metres."""
    out = []
    for key, radius in PADS.items():
        for x, y in ([track[key]] if key == "target_car" else track[key]):
            out.append(((x - origin[0]) / 100.0, (y - origin[1]) / 100.0, radius))
    return out


def heights(track, origin, seed):
    """(h, d): heights (m) and road distance (m) on the vertex grid, rows = Y."""
    samples = np.array([[(p[0] - origin[0]) / 100.0, (p[1] - origin[1]) / 100.0] for road in track["roads"] for p in road])
    edge_gap = float(edge_distance(samples[:, 0], samples[:, 1]).min())
    if edge_gap < RIDGE_BAND + RIDGE_WOBBLE + ROAD_BLEND:
        raise ValueError("a road comes within %.0f m of the landscape edge (the ridge ring needs %.0f m)"
                         % (edge_gap, RIDGE_BAND + RIDGE_WOBBLE + ROAD_BLEND))
    ax = np.arange(N, dtype=np.float64)
    gx, gy = np.meshgrid(ax, ax)
    d = road_distance(gx, gy, samples)
    # the field: fBm whose amplitude grows from 0.5 m near the roads to 40 m at 300 m (the roads lie in valleys)
    h = _amplitude(d) * _noise(seed, 5, 5)
    # the ridge ring: crests 84-120 m (ridged noise along the ring), rising from a wobbling foot 150 m in from the edge
    crest = 1.0 - np.abs(2.0 * _noise(seed + 1, 9, 4) - 1.0)
    edge = edge_distance(gx, gy) + RIDGE_WOBBLE * (_noise(seed + 2, 7, 3) - 0.5)
    w = _smooth(RIDGE_BAND, 0.0, edge)
    h = h * (1 - w) + RIDGE_TOP * (0.7 + 0.3 * crest) * w
    # the roads: -8 cm to 9 m, smoothstep into the field by 25 m; then the pads
    t = _smooth(ROAD_FLAT, ROAD_BLEND, d)
    h = ROAD_Z + (h - ROAD_Z) * t
    for x, y, r in _pads(track, origin):
        h = ROAD_Z + (h - ROAD_Z) * _smooth(r, r + PAD_BLEND, np.hypot(gx - x, gy - y))
    return h, d


def encode(h):
    """Heights (m) -> uint16 codes: Z (cm) = (code - 32768) * Z_SCALE / 128."""
    return np.clip(np.rint(32768.0 + h * 100.0 * 128.0 / Z_SCALE), 0, 65535).astype("<u2")


def decode_cm(code):
    return (code.astype(np.float64) - 32768.0) * Z_SCALE / 128.0


def slope_deg(h):
    gy, gx = np.gradient(h, 1.0)
    return np.degrees(np.arctan(np.hypot(gx, gy)))


def splat(track, origin, h, d, seed):
    """SPLAT^2 x 4 uint8 (R dirt, G ash/grass, B rock, A sand) summing to 255, rows = Y."""
    c = (np.arange(SPLAT, dtype=np.float64) + 0.5) * L_M / SPLAT
    u, v = np.meshgrid(c, c)
    # the slope is the steepest of each vertex and its neighbours, so a pixel is never less rocky than a corner of its
    # cell (a crest's own vertex has a low central-difference slope between two steep faces)
    hs, ds, ss = sample(h, u, v), sample(d, u, v), sample(_max3(slope_deg(h)), u, v)
    pad = np.zeros_like(u)
    for x, y, r in _pads(track, origin):
        pad = np.maximum(pad, 1.0 - _smooth(r, r + 2.0, np.hypot(u - x, v - y)))
    sand_noise = sample(_noise(seed + 3, 12, 4, persistence=0.5), u, v)  # ragged patch edges
    rock = np.maximum(_smooth(ROCK_SLOPE - 2, ROCK_SLOPE + 2, ss), _smooth(ROCK_HEIGHT - 1, ROCK_HEIGHT + 1, hs))
    dirt = np.maximum(1.0 - _smooth(SHOULDER - 1, SHOULDER + 1, ds), pad)
    sand = _smooth(0.58, 0.66, sand_noise) * (1.0 - _smooth(SAND_LOW - 1, SAND_LOW + 1, hs))
    b = rock                      # rock wins, then dirt, then sand; ash and grass take the rest
    r = (1 - b) * dirt
    a = (1 - b - r) * sand
    cum = np.rint(np.stack([b, b + r, b + r + a], axis=-1).clip(0, 1) * 255).astype(np.int32)
    out = np.empty(u.shape + (4,), np.uint8)
    out[..., 2] = cum[..., 0]                    # B
    out[..., 0] = cum[..., 1] - cum[..., 0]      # R
    out[..., 3] = cum[..., 2] - cum[..., 1]      # A
    out[..., 1] = 255 - cum[..., 2]              # G
    return out


def scatter(track, origin, h, d, z_cm, seed):
    """Seeded Poisson-disc placement by the spec 8.3 rules; returns the scatter json list."""
    samples = np.array([[(p[0] - origin[0]) / 100.0, (p[1] - origin[1]) / 100.0] for road in track["roads"] for p in road])
    slope = slope_deg(h)

    def region(x, y):  # within reach of the roads, off the ridge ring
        i, j = int(x + 0.5), int(y + 0.5)
        return d[j, i] <= SCATTER_REACH and edge_distance(x, y) >= RIDGE_BAND + RIDGE_WOBBLE / 2

    pts = np.array(noise.poisson_disc(L_M, L_M, SCATTER_SPACING, seed + 5, accept=region), np.float64).reshape(-1, 2)
    if not len(pts):
        return []
    rng = np.random.default_rng(seed + 6)
    draws = rng.random((len(pts), 5))  # keep, category, mesh, yaw, scale: the same draws per point whatever is kept
    dist = road_distance(pts[:, 0], pts[:, 1], samples) - SCATTER_ROAD_MARGIN
    features = np.array([[(x - origin[0]) / 100.0, (y - origin[1]) / 100.0]
                         for x, y in track["crates"] + track["gates"] + track["props"] + [track["target_car"]]])
    clear = np.sqrt(((pts[:, None, :] - features[None, :, :]) ** 2).sum(axis=2)).min(axis=1)
    sx, sy = (track["start"][0] - origin[0]) / 100.0, (track["start"][1] - origin[1]) / 100.0
    yaw = math.radians(track["start"][2])
    along = (pts[:, 0] - sx) * math.cos(yaw) + (pts[:, 1] - sy) * math.sin(yaw)
    side = -(pts[:, 0] - sx) * math.sin(yaw) + (pts[:, 1] - sy) * math.cos(yaw)
    in_start = (along >= 0) & (along <= START_BOX[0]) & (np.abs(side) <= START_BOX[1])
    steep = slope[(pts[:, 1] + 0.5).astype(int), (pts[:, 0] + 0.5).astype(int)] > SCATTER_MAX_SLOPE
    p0, d0, d1 = SCATTER_KEEP
    keep_p = p0 + (1 - p0) * _smooth(d0, d1, dist)
    chosen = []  # (point index, category, mesh)
    for k in range(len(pts)):
        if dist[k] < SCATTER[0][0] or clear[k] < FEATURE_CLEAR or in_start[k] or steep[k] or draws[k, 0] >= keep_p[k]:
            continue
        allowed = [c for c, cat in enumerate(SCATTER) if dist[k] >= cat[0]]
        weights = np.array([SCATTER[c][3] for c in allowed])
        cat = allowed[int(np.searchsorted(np.cumsum(weights / weights.sum()), draws[k, 1], side="right").clip(0, len(allowed) - 1))]
        meshes = SCATTER[cat][2]
        chosen.append((k, cat, meshes[min(int(draws[k, 2] * len(meshes)), len(meshes) - 1)]))
    if len(chosen) > MAX_INSTANCES:
        pick = np.sort(rng.choice(len(chosen), MAX_INSTANCES, replace=False))
        chosen = [chosen[i] for i in pick]
    by_mesh = {}
    for k, cat, mesh in chosen:
        x, y = pts[k]
        wx, wy = origin[0] + x * 100.0, origin[1] + y * 100.0
        z = float(sample(z_cm, np.array([x]), np.array([y]))[0])
        scale = SCALE_RANGE[0] + (SCALE_RANGE[1] - SCALE_RANGE[0]) * draws[k, 4]
        by_mesh.setdefault(mesh, []).append([round(wx, 1), round(wy, 1), round(z, 1), round(360.0 * draws[k, 3], 1), round(scale, 3)])
    return [{"mesh": m, "blocking": blocking, "transforms": by_mesh[m]}
            for _, blocking, meshes, _ in SCATTER for m in meshes if m in by_mesh]


def _write_json(path, data):
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(data, f, indent=1)
        f.write("\n")


def build(track_json, out_dir, seed):
    """Writes <T>.r16, T_DF_Splat_<T>.png, <T>.terrain.json and <T>.scatter.json; returns a summary dict."""
    map_name = os.path.splitext(os.path.basename(track_json))[0]
    name = catalog.TERRAINS[map_name]
    with open(track_json, encoding="utf-8") as f:
        track = json.load(f)
    origin = origin_for(track)
    h, d = heights(track, origin, seed)
    code = encode(h)
    z_cm = decode_cm(code)
    os.makedirs(out_dir, exist_ok=True)
    files = {"r16": os.path.join(out_dir, name + ".r16"), "splat": os.path.join(out_dir, "T_DF_Splat_%s.png" % name),
             "meta": os.path.join(out_dir, name + ".terrain.json"), "scatter": os.path.join(out_dir, name + ".scatter.json")}
    code.tofile(files["r16"])
    PILImage.fromarray(splat(track, origin, h, d, seed), "RGBA").save(files["splat"])
    placed = scatter(track, origin, h, d, z_cm, seed)
    _write_json(files["scatter"], placed)
    meta = {"map": map_name, "terrain": name, "origin": origin, "size_cm": SIZE_CM, "z_scale": Z_SCALE,
            "vertices": N, "spacing_cm": STEP_CM, "seed": seed,
            "layout": "uint16 little-endian, row-major, row j = Y, column i = X; vertex (i, j) at origin + (i, j) * "
                      "spacing_cm; Z cm = (h - 32768) * z_scale / 128 with the landscape at Z 0",
            "height_cm": [round(float(z_cm.min()), 1), round(float(z_cm.max()), 1)]}
    _write_json(files["meta"], meta)
    roads = np.array([p[:2] for road in track["roads"] for p in road], np.float64)
    road_z = sample(z_cm, (roads[:, 0] - origin[0]) / 100.0, (roads[:, 1] - origin[1]) / 100.0)
    return {"terrain": name, "files": list(files.values()), "origin": origin, "height_cm": meta["height_cm"],
            "road_cm": [round(float(road_z.min()), 2), round(float(road_z.max()), 2)],
            "scatter": {e["mesh"]: len(e["transforms"]) for e in placed}}
