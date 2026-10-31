"""Checks the generated terrain of every shipped track against spec 8.1 (terrain) and 8.3 (scatter) (plan Task 19).
Reads art/terrain/ as build_all.py wrote it, rebuilds each terrain into a temporary folder to prove the output is
deterministic by seed, and writes art/terrain/_preview_<Terrain>.png (hillshade, roads in red, pads in white, scatter as
dots: yellow blocking, cyan debris) for a visual check.

    python -I tools/artgen/build_all.py --kind terrain
    python -I tools/artgen/test_terrain.py
"""
import hashlib
import json
import math
import os
import sys
import tempfile

import numpy as np
from PIL import Image as PILImage
from PIL import ImageDraw

BILINEAR = getattr(PILImage, "Resampling", PILImage).BILINEAR

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
from artgen import catalog  # noqa: E402

try:
    from artgen import terrain  # noqa: E402
except ImportError as _e:  # reported as a failure, so the output checks below still run
    terrain, TERRAIN_IMPORT_ERROR = None, str(_e)

ART = os.path.join(os.path.dirname(os.path.dirname(HERE)), "art")
OUT = os.path.join(ART, "terrain")
TRACKS = os.path.join(HERE, "data", "tracks")

# The spec's values, literal on purpose (the generator must not define what it is checked against).
N, STEP_CM, SIZE_CM, SPLAT = 1009, 100, 100800, 1024                     # 8.1: 1009 x 1009 at 100 cm; 1024^2 splat
ROAD_CM, ROAD_TOL_CM = -8.0, 1.0                                         # 8.1: -8 cm under the roads and on the pads
SLOPE_ZONE_CM, MAX_SLOPE_DEG = 2500.0, 8.0
FLAT_ZONE_CM, FLAT_TOL_CM = 6000.0, 60.0                                 # 8.1: fBm amplitude 0.5 m up to 60 m
MAX_HEIGHT_CM = 12000.0                                                  # 8.1: the ridge ring rises to 120 m
EDGE_INSET, EDGE_MIN_CM = 20, 5000.0                                     # the ring 20 m inside the border
PADS_CM = {"crates": 600.0, "target_car": 600.0, "gates": 1200.0, "props": 1200.0}
ROCK_TEST_DEG = 35.0                                                     # 8.1: rock above 28 deg (checked at 35)
SCATTER_RULES = {  # 8.3: mesh -> (minimum distance from a road centre line, cm; blocking)
    **{m: (1000.0, False) for m in ("SM_DF_Debris01", "SM_DF_Debris02")},
    **{m: (1400.0, True) for m in ("SM_DF_Rock01", "SM_DF_Rock02", "SM_DF_Rock03", "SM_DF_Rock04", "SM_DF_Barrel",
                                   "SM_DF_TyreStack", "SM_DF_CarWreck")},
    **{m: (2500.0, True) for m in ("SM_DF_DeadTree01", "SM_DF_DeadTree02", "SM_DF_Container", "SM_DF_Billboard",
                                   "SM_DF_LightTower")},
    "SM_DF_ScrapFence": (2500.0, True),  # listed among the meshes but in no distance band: it takes the farthest one
}
FEATURE_CLEAR_CM = 1000.0                                                # 8.3: 10 m from crates, gates, props, target car
START_BOX_CM = (6000.0, 2000.0)                                          # 8.3: 60 m past the start line, +-20 m
MAX_INSTANCES, MIN_INSTANCES = 500, 150                                  # 8.3: at most 500 (the floor: scatter exists)
Z_TOL_CM = 5.0

checks = 0
failures = []


def check(ok, msg):
    global checks
    checks += 1
    if not ok:
        failures.append(msg)


def digest(path):
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def outputs(name, folder=OUT):
    return {k: os.path.join(folder, f) for k, f in (("r16", name + ".r16"), ("splat", "T_DF_Splat_%s.png" % name),
                                                     ("meta", name + ".terrain.json"), ("scatter", name + ".scatter.json"))}


def heights_cm(path):
    """The r16 as Z in cm: row j = Y, column i = X; Z = (h - 32768) * 100 / 128 (Z scale 100)."""
    h = np.fromfile(path, dtype="<u2")
    return (h.reshape(N, N).astype(np.float64) - 32768.0) * 100.0 / 128.0 if h.size == N * N else None


def bilinear(z, origin, x, y):
    """Bilinear height of the vertex grid at world (x, y) cm."""
    u = np.clip((np.asarray(x, np.float64) - origin[0]) / STEP_CM, 0, N - 1 - 1e-9)
    v = np.clip((np.asarray(y, np.float64) - origin[1]) / STEP_CM, 0, N - 1 - 1e-9)
    i, j = np.floor(u).astype(int), np.floor(v).astype(int)
    fu, fv = u - i, v - j
    return (z[j, i] * (1 - fu) * (1 - fv) + z[j, i + 1] * fu * (1 - fv) + z[j + 1, i] * (1 - fu) * fv
            + z[j + 1, i + 1] * fu * fv)


def min_distance(px, py, q):
    """Distance (cm) from each point to the nearest of the points q (n x 2): plain broadcast, chunked."""
    px, py = np.ravel(px).astype(np.float64), np.ravel(py).astype(np.float64)
    q = np.asarray(q, np.float64).reshape(-1, 2)
    out = np.empty(px.size)
    for k in range(0, px.size, 4096):
        dx = px[k:k + 4096, None] - q[None, :, 0]
        dy = py[k:k + 4096, None] - q[None, :, 1]
        out[k:k + 4096] = np.sqrt((dx * dx + dy * dy).min(axis=1))
    return out


def slope_deg(z):
    gy, gx = np.gradient(z, STEP_CM)
    return np.degrees(np.arctan(np.hypot(gx, gy)))


def splat_pixel(origin, x, y):
    c = np.clip(np.floor((np.asarray(x) - origin[0]) / SIZE_CM * SPLAT).astype(int), 0, SPLAT - 1)
    r = np.clip(np.floor((np.asarray(y) - origin[1]) / SIZE_CM * SPLAT).astype(int), 0, SPLAT - 1)
    return r, c


def track_points(track):
    pts = [p[:2] for road in track["roads"] for p in road]
    pts += track["crates"] + track["gates"] + track["props"] + [track["target_car"], track["start"][:2]]
    return np.array(pts, np.float64)


def test_catalogue():
    check(set(catalog.TERRAINS.values()) == {"ProvingGround", "Switchback"}, "terrains %s" % catalog.TERRAINS)
    splats = {i.name: i for i in catalog.IMAGES if i.name.startswith("T_DF_Splat_")}
    for t in catalog.TERRAINS.values():
        im = splats.get("T_DF_Splat_" + t)
        check(im is not None and im.recipe != "todo" and not im.srgb and tuple(im.size) == (SPLAT, SPLAT),
              "T_DF_Splat_%s must be a built 1024^2 linear image (recipe %s)" % (t, im and im.recipe))
    check(terrain is not None, "artgen.terrain does not import: %s" % (TERRAIN_IMPORT_ERROR if terrain is None else ""))


def check_terrain(map_name, name):
    files = outputs(name)
    for k, p in files.items():
        check(os.path.exists(p), "%s: %s missing (run build_all.py --kind terrain)" % (name, os.path.relpath(p, ART)))
    track_path = os.path.join(TRACKS, map_name + ".json")
    check(os.path.exists(track_path), "%s missing (run df_export_tracks.py in the editor)" % track_path)
    if not all(os.path.exists(p) for p in list(files.values()) + [track_path]):
        return
    with open(track_path, encoding="utf-8") as f:
        track = json.load(f)
    with open(files["meta"], encoding="utf-8") as f:
        meta = json.load(f)
    with open(files["scatter"], encoding="utf-8") as f:
        scatter = json.load(f)

    # metadata: the origin is the landscape's corner, a multiple of 100 cm, and the square is centred on the track
    origin = meta.get("origin", [0.5, 0.5])
    check(all(float(c) % 100 == 0 for c in origin), "%s: origin %s is not a multiple of 100 cm" % (name, origin))
    check(meta.get("size_cm") == SIZE_CM and meta.get("z_scale") == 100, "%s: size_cm/z_scale %s" % (name, meta))
    pts = track_points(track)
    centre = (pts.min(axis=0) + pts.max(axis=0)) / 2
    off = np.abs(np.array(origin, np.float64) + SIZE_CM / 2 - centre)
    check(off.max() <= 50.0, "%s: the square's centre is %s cm off the track's bounding-box centre" % (name, off.round(1)))
    check(os.path.getsize(files["r16"]) == N * N * 2, "%s.r16 is %d bytes, want %d" % (name, os.path.getsize(files["r16"]), N * N * 2))
    z = heights_cm(files["r16"])
    if z is None:
        return

    # roads: every sample at -8 +- 1 cm
    samples = np.array([p for road in track["roads"] for p in road], np.float64)
    zr = bilinear(z, origin, samples[:, 0], samples[:, 1])
    worst = float(np.abs(zr - ROAD_CM).max())
    check(worst <= ROAD_TOL_CM, "%s: a road sample's height is %.2f cm off -8 cm" % (name, worst))

    # distance to the roads on the 1 m grid, within the roads' bounding box + 150 m (all that is within 150 m)
    lo = np.floor((samples[:, :2].min(axis=0) - 15000 - origin) / STEP_CM).astype(int).clip(0, N - 1)
    hi = np.ceil((samples[:, :2].max(axis=0) + 15000 - origin) / STEP_CM).astype(int).clip(0, N - 1)
    ii, jj = np.meshgrid(np.arange(lo[0], hi[0] + 1), np.arange(lo[1], hi[1] + 1))
    gx, gy = origin[0] + ii * STEP_CM, origin[1] + jj * STEP_CM
    d = min_distance(gx, gy, samples[:, :2]).reshape(ii.shape)
    zs = z[jj, ii]
    slope = slope_deg(z)
    near = d <= SLOPE_ZONE_CM
    s_near = float(slope[jj, ii][near].max())
    check(s_near <= MAX_SLOPE_DEG, "%s: slope %.2f deg within 25 m of a road (max 8)" % (name, s_near))
    flat = d <= FLAT_ZONE_CM
    z_flat = float(np.abs(zs[flat]).max())
    check(z_flat <= FLAT_TOL_CM, "%s: height %.1f cm within 60 m of a road (max +-60)" % (name, z_flat))
    check(float(z.max()) <= MAX_HEIGHT_CM, "%s: maximum height %.0f cm (max 12,000)" % (name, z.max()))
    k = EDGE_INSET
    ring = np.concatenate([z[k, k:N - k], z[N - 1 - k, k:N - k], z[k:N - k, k], z[k:N - k, N - 1 - k]])
    check(float(ring.mean()) >= EDGE_MIN_CM, "%s: the ring 20 m inside the border averages %.0f cm (min 5,000)" % (name, ring.mean()))

    # pads: -8 +- 1 cm within the radius of every crate, the target car, every gate and prop
    for key, radius in PADS_CM.items():
        centres = [track[key]] if key == "target_car" else track[key]
        for cx, cy in centres:
            sel = np.hypot(origin[0] + np.arange(N)[None, :] * STEP_CM - cx, origin[1] + np.arange(N)[:, None] * STEP_CM - cy) <= radius
            dev = float(np.abs(z[sel] - ROAD_CM).max()) if sel.any() else 99.0
            check(dev <= ROAD_TOL_CM, "%s: %s pad at (%.0f, %.0f) is %.2f cm off -8 cm" % (name, key, cx, cy, dev))

    # splat: 1024^2 RGBA, 8-bit, channels summing to 255; R at the roads, B on the steep slopes
    img = PILImage.open(files["splat"])
    check(img.mode == "RGBA" and img.size == (SPLAT, SPLAT), "%s splat %s %s" % (name, img.mode, img.size))
    sp = np.asarray(img.convert("RGBA")).astype(np.int32)
    check(bool((sp.sum(axis=2) == 255).all()), "%s splat: channels do not sum to 255 everywhere" % name)
    r, c = splat_pixel(origin, samples[:, 0], samples[:, 1])
    not_r = int((sp[r, c].argmax(axis=1) != 0).sum())
    check(not_r == 0, "%s splat: %d of %d road samples are not R-dominant" % (name, not_r, len(samples)))
    steep_j, steep_i = np.nonzero(slope > ROCK_TEST_DEG)
    check(steep_j.size > 0, "%s: no slope above 35 deg (the ridge ring should have them)" % name)
    r, c = splat_pixel(origin, origin[0] + steep_i * STEP_CM, origin[1] + steep_j * STEP_CM)
    not_b = int((sp[r, c].argmax(axis=1) != 2).sum())
    check(not_b == 0, "%s splat: %d of %d vertices steeper than 35 deg are not B-dominant" % (name, not_b, steep_j.size))

    # scatter (8.3)
    check_scatter(name, track, origin, z, samples, scatter, d)

    # the catalogue's terrain instance carries the splat, TerrainOrigin and TerrainSize (and art/catalog.json, rewritten after terrain)
    want = {"Splat": "T_DF_Splat_" + name}
    mi = {m.name: m for m in catalog.MATERIALS}.get("MI_DF_Terrain_" + name)
    check(mi is not None and mi.textures == want and mi.scalars.get("TerrainSize") == SIZE_CM
          and tuple(mi.vectors.get("TerrainOrigin", ()))[:2] == tuple(float(v) for v in origin),
          "%s: MI_DF_Terrain_%s does not carry the splat/origin/size (%s)" % (name, name, mi))
    cat_path = os.path.join(ART, "catalog.json")
    entry = None
    if os.path.exists(cat_path):
        with open(cat_path, encoding="utf-8") as f:
            entry = {m["name"]: m for m in json.load(f)["materials"]}.get("MI_DF_Terrain_" + name)
    check(entry is not None and entry["textures"] == want and entry["vectors"].get("TerrainOrigin", [None])[:2] == list(map(float, origin))
          and entry["scalars"].get("TerrainSize") == SIZE_CM, "%s: art/catalog.json's MI_DF_Terrain_%s is stale (%s)" % (name, name, entry))

    # deterministic by seed: a rebuild matches art/terrain byte for byte; another seed gives other heights
    if terrain is not None:
        seed = catalog.TERRAIN_SEEDS[name]
        with tempfile.TemporaryDirectory() as tmp:
            terrain.build(track_path, tmp, seed)
            again = outputs(name, tmp)
            for key in files:
                check(os.path.exists(again[key]) and digest(again[key]) == digest(files[key]),
                      "%s: %s differs on a rebuild with seed %d" % (name, os.path.basename(files[key]), seed))
        with tempfile.TemporaryDirectory() as tmp:
            terrain.build(track_path, tmp, seed + 1)
            check(digest(outputs(name, tmp)["r16"]) != digest(files["r16"]), "%s: seed %d gives the same heights" % (name, seed + 1))

    write_preview(name, track, origin, z, scatter)


def check_scatter(name, track, origin, z, samples, scatter, d_grid):
    total, used = 0, set()
    xs, ys, mins = [], [], []
    for entry in scatter:
        mesh, transforms = entry.get("mesh"), entry.get("transforms", [])
        rule = SCATTER_RULES.get(mesh)
        check(rule is not None, "%s scatter: %s is not a spec 8.3 scatter mesh" % (name, mesh))
        check(mesh in {m.name for m in catalog.MESHES}, "%s scatter: %s is not in the catalogue" % (name, mesh))
        if rule is None:
            continue
        check(entry.get("blocking") is rule[1], "%s scatter: %s blocking %s, spec %s" % (name, mesh, entry.get("blocking"), rule[1]))
        check(all(len(t) == 5 for t in transforms), "%s scatter: %s transforms are not [x, y, z, yaw, scale]" % (name, mesh))
        if transforms:
            used.add(mesh)
        for t in transforms:
            xs.append(t[0]), ys.append(t[1]), mins.append(rule[0])
        total += len(transforms)
        t = np.array(transforms, np.float64).reshape(-1, 5)
        if len(t):
            dz = float(np.abs(t[:, 2] - bilinear(z, origin, t[:, 0], t[:, 1])).max())
            check(dz <= Z_TOL_CM, "%s scatter: a %s is %.1f cm off the heightmap" % (name, mesh, dz))
            check(bool(((t[:, 0] >= origin[0]) & (t[:, 0] <= origin[0] + SIZE_CM) & (t[:, 1] >= origin[1])
                        & (t[:, 1] <= origin[1] + SIZE_CM)).all()), "%s scatter: a %s is off the landscape" % (name, mesh))
    check(MIN_INSTANCES <= total <= MAX_INSTANCES, "%s scatter: %d instances (want %d..%d)" % (name, total, MIN_INSTANCES, MAX_INSTANCES))
    missing = sorted(set(SCATTER_RULES) - used)
    check(not missing, "%s scatter: never places %s" % (name, missing))
    if not xs:
        return
    xs, ys, mins = np.array(xs), np.array(ys), np.array(mins)
    d = min_distance(xs, ys, samples[:, :2])
    close = int((d < mins).sum())
    check(close == 0, "%s scatter: %d instances nearer a road sample than their category allows (closest %.0f cm)" % (name, close, (d - mins).min() + mins[(d - mins).argmin()]))
    features = np.array(track["crates"] + track["gates"] + track["props"] + [track["target_car"]], np.float64)
    df = min_distance(xs, ys, features)
    check(float(df.min()) >= FEATURE_CLEAR_CM, "%s scatter: an instance %.0f cm from a crate, gate, prop or the target car" % (name, df.min()))
    sx, sy, yaw = track["start"]
    fx, fy = math.cos(math.radians(yaw)), math.sin(math.radians(yaw))
    along, side = (xs - sx) * fx + (ys - sy) * fy, -(xs - sx) * fy + (ys - sy) * fx
    inside = int(((along >= 0) & (along <= START_BOX_CM[0]) & (np.abs(side) <= START_BOX_CM[1])).sum())
    check(inside == 0, "%s scatter: %d instances in the start box" % (name, inside))
    # density rises with distance from the road: instances per square metre of open ground, 10-40 m against 40-150 m
    near_area = float(((d_grid >= 1000) & (d_grid < 4000)).sum())
    far_area = float(((d_grid >= 4000) & (d_grid < 15000)).sum())
    near_n, far_n = int(((d >= 1000) & (d < 4000)).sum()), int(((d >= 4000) & (d < 15000)).sum())
    check(far_n / far_area > near_n / near_area, "%s scatter: density 10-40 m %.2e/m2 is not below 40-150 m %.2e/m2"
          % (name, near_n / near_area, far_n / far_area))


def shaded(z, interval_cm):
    """Hillshade (light from the north-west) tinted by height (tan low ground, grey from 40 m up), with contour lines
    every interval_cm offset by half an interval (so the -8..+50 cm valley floor has none)."""
    gy, gx = np.gradient(z, STEP_CM)
    light = np.array([-1.0, -1.0, 1.2]) / np.linalg.norm([-1.0, -1.0, 1.2])
    shade = np.clip((-gx * light[0] - gy * light[1] + light[2]) / np.sqrt(gx * gx + gy * gy + 1), 0, 1)
    t = np.clip(z / 4000.0, 0, 1)[..., None]
    rgb = (np.array([176, 154, 112]) * (1 - t) + np.array([120, 116, 110]) * t) * (0.35 + 0.65 * shade[..., None])
    lvl = np.floor((z - interval_cm / 2) / interval_cm)
    line = np.zeros(z.shape, bool)
    line[:, :-1] |= lvl[:, :-1] != lvl[:, 1:]
    line[:-1, :] |= lvl[:-1, :] != lvl[1:, :]
    rgb[line] *= 0.55
    return np.clip(rgb, 0, 255).astype(np.uint8)


def write_preview(name, track, origin, z, scatter):
    """Two panels: the whole landscape (contours every 5 m) and the track zoomed (its bounding box + 120 m, contours
    every 1 m); roads in red, pads in white, scatter dots (yellow blocking, cyan debris)."""
    pts = (track_points(track) - np.array(origin, np.float64)) / STEP_CM
    i0, j0 = np.maximum(np.floor(pts.min(axis=0) - 120), 0).astype(int)
    i1, j1 = np.minimum(np.ceil(pts.max(axis=0) + 120), N - 1).astype(int)
    k = float(N) / max(i1 - i0, j1 - j0)
    full = PILImage.fromarray(shaded(z, 500.0), "RGB")
    zoom = PILImage.fromarray(shaded(z[j0:j1 + 1, i0:i1 + 1], 100.0), "RGB")
    zoom = zoom.resize((int(zoom.width * k), int(zoom.height * k)), BILINEAR)
    panels = [(full, lambda x, y: ((x - origin[0]) / STEP_CM, (y - origin[1]) / STEP_CM, 1.0)),
              (zoom, lambda x, y: (((x - origin[0]) / STEP_CM - i0) * k, ((y - origin[1]) / STEP_CM - j0) * k, k))]
    for img, px in panels:  # drawn on each panel's own image, which clips what falls outside it
        draw = ImageDraw.Draw(img)
        for key, radius in PADS_CM.items():
            for cx, cy in ([track[key]] if key == "target_car" else track[key]):
                u, v, s = px(cx, cy)
                r = radius / STEP_CM * s
                draw.ellipse((u - r, v - r, u + r, v + r), outline=(255, 255, 255))
        for road in track["roads"]:
            draw.line([px(p[0], p[1])[:2] for p in road], fill=(220, 30, 30), width=3)
        for entry in scatter:
            colour = (255, 220, 40) if entry.get("blocking") else (60, 220, 255)
            for t in entry.get("transforms", []):
                u, v, s = px(t[0], t[1])
                r = 2 + s / 2
                draw.ellipse((u - r, v - r, u + r, v + r), fill=colour)
    canvas = PILImage.new("RGB", (2 * N + 8, N), (20, 20, 20))
    canvas.paste(full, (0, 0))
    canvas.paste(zoom, (N + 8, 0))
    os.makedirs(OUT, exist_ok=True)
    canvas.save(os.path.join(OUT, "_preview_%s.png" % name))


def test_terrains():
    for map_name, name in catalog.TERRAINS.items():
        check_terrain(map_name, name)


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
