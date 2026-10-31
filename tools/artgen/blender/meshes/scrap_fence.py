"""SM_DF_ScrapFence: a run of scrap-metal fence for the scatter (spec 8.3).

About 4.2 m along X and 2.3 m tall: three leaning pipe posts with two rails, and corrugated sheets of mixed widths and
heights hung on them, overlapping, each tipped and twisted a little, with torn tops and one curling out
(dfmesh.corrugated_sheet). Origin at the bottom centre. Collision: one UCX box over the run (a hull round the leaning
sheets would stand out from it). Slot: RustMetal, box-projected UVs.
"""
import math

from mathutils import Matrix

import dfmesh

SLOT = "MI_DF_RustMetal"
POSTS_X = (-2.0, 0.05, 2.05)
POST_H, POST_R = 2.30, 0.045
# sheets: (centre x, width, height, y offset, lean degrees about X, twist degrees about Z, torn top m, curl m, seed)
SHEETS = [(-1.55, 1.00, 2.05, 0.06, -3.0, 4.0, 0.25, 0.0, 1),
          (-0.70, 0.95, 1.80, 0.10, 2.0, -3.0, 0.10, 0.0, 2),
          (0.15, 1.05, 2.15, 0.06, -1.5, 2.0, 0.35, 0.12, 3),
          (1.00, 0.90, 1.65, 0.11, 4.0, -5.0, 0.15, 0.0, 4),
          (1.70, 0.85, 1.95, 0.06, -2.5, 6.0, 0.30, 0.0, 5)]


def build(dims):
    parts = []
    for k, x in enumerate(POSTS_X):  # pipe posts, each leaning a little
        lean = (0.04, -0.03, 0.05)[k]
        parts.append(dfmesh.part(dfmesh.tube("post", (x, 0.0, 0.0), (x + lean, 0.02, POST_H), POST_R, [SLOT], verts=8), SLOT))
    for z in (0.45, 1.75):  # rails
        parts.append(dfmesh.part(dfmesh.tube("rail", (POSTS_X[0], 0.0, z), (POSTS_X[-1], 0.03, z + 0.04), 0.03, [SLOT], verts=6), SLOT))
    for x, w, h, y, lean, twist, jag, curl, seed in SHEETS:
        s = dfmesh.corrugated_sheet("sheet", w, h, SLOT, pitch_m=0.16, depth_m=0.035, rows=3, jag_m=jag, curl_m=curl, seed=seed)
        s.data.transform(Matrix.Translation((x, y, 0.02)) @ Matrix.Rotation(math.radians(twist), 4, "Z")
                         @ Matrix.Rotation(math.radians(lean), 4, "X"))
        parts.append(s)
    root = dfmesh.assemble(parts, "SM_DF_ScrapFence", [SLOT], unwrap=False)
    dfmesh.ground(root)
    dfmesh.box_uv(root, 1.5)
    dfmesh.ucx_box(root, (4.3, 0.30, POST_H), (0.0, 0.07, POST_H / 2))
    return root
