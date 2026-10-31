"""SM_DF_Barrel: a 58 x 58 x 88 cm oil drum with rolled rims and two ribs, rust metal, one box hull."""
import dfmesh

R_BODY, R_RIB, H = 0.27, 0.29, 0.88


def build(dims):
    verts = 24
    parts = [dfmesh.cylinder("body", R_BODY, H - 0.04, verts, loc=(0, 0, H / 2))]
    for z in (0.02, H - 0.02):  # rolled rims at the bottom and the top
        parts.append(dfmesh.cylinder("rim", R_RIB, 0.04, verts, loc=(0, 0, z)))
    for z in (H * 0.33, H * 0.67):  # ribs
        parts.append(dfmesh.cylinder("rib", R_RIB, 0.03, verts, loc=(0, 0, z)))
    parts.append(dfmesh.cylinder("lid", 0.22, 0.02, verts, loc=(0, 0, H - 0.01)))
    obj = dfmesh.join(parts, "SM_DF_Barrel")
    dfmesh.slot(obj, "MI_DF_RustMetal")
    dfmesh.smart_uv(obj)
    dfmesh.ucx_box(obj, (2 * R_RIB, 2 * R_RIB, H), (0, 0, H / 2))
    return obj
