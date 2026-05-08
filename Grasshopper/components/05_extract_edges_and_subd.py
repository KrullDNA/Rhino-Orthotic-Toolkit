# -*- coding: utf-8 -*-
"""GHPython component: Extract Edge Curves + Convert to SubD.

INPUTS:
    Mesh         : Mesh       (item)
    BoundaryIdx  : list[int]  (list)  - ordered boundary indices on top layer
    NVerts       : int        (item)  - flat-layer vertex count
    RebuildCount : int        (item)  - control points on edge curves, default 20

OUTPUTS:
    SubD         : SubD       - smooth SubD insole
    TopEdge      : Curve      - smooth NURBS following sole contour
    BottomEdge   : Curve      - smooth NURBS along the flat bottom

Adapted from cmd_outline.py::_curves_from_boundary + SubD conversion.
"""

import Rhino.Geometry as rg


def edge_curves(mesh, ordered, n_verts, rebuild_count):
    if not ordered or len(ordered) < 3 or n_verts <= 0:
        return None, None

    top_pts = []
    bot_pts = []
    for vi in ordered:
        tv = mesh.Vertices[vi]
        top_pts.append(rg.Point3d(tv.X, tv.Y, tv.Z))
        bv = mesh.Vertices[vi + n_verts]
        bot_pts.append(rg.Point3d(bv.X, bv.Y, bv.Z))

    top_pts.append(top_pts[0])
    bot_pts.append(bot_pts[0])

    top = rg.Curve.CreateInterpolatedCurve(top_pts, 3, rg.CurveKnotStyle.ChordSquareRoot)
    bot = rg.Curve.CreateInterpolatedCurve(bot_pts, 3, rg.CurveKnotStyle.ChordSquareRoot)

    if top is not None and rebuild_count and rebuild_count >= 4:
        rb = top.Rebuild(rebuild_count, 3, False)
        if rb is not None:
            top = rb
    if bot is not None and rebuild_count and rebuild_count >= 4:
        rb = bot.Rebuild(rebuild_count, 3, False)
        if rb is not None:
            bot = rb

    return top, bot


rc = RebuildCount if RebuildCount else 20

if Mesh and BoundaryIdx and NVerts:
    TopEdge, BottomEdge = edge_curves(Mesh, list(BoundaryIdx), NVerts, rc)
    sd = rg.SubD.CreateFromMesh(Mesh)
    SubD = sd if (sd is not None and sd.IsValid) else None
else:
    SubD, TopEdge, BottomEdge = None, None, None
