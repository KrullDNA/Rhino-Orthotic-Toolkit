# -*- coding: utf-8 -*-
"""GHPython component: Build Sole-Conforming Insole Mesh.

INPUTS:
    Last           : Brep   (item) - shoe last polysurface
    Outline        : Curve  (item) - top outline (XY, closed)
    BottomOutline  : Curve  (item) - optional override for bottom edge
    CoverThk       : float  (item) - mm, default 2.0
    ShellThk       : float  (item) - mm, default 3.0
    BaseThk        : float  (item) - mm, default 5.0
    MaxEdge        : float  (item) - meshing max edge length, default 3.0
    MinEdge        : float  (item) - meshing min edge length, default 1.0

OUTPUTS:
    Mesh           : Mesh   - top conforms to sole, flat bottom + side walls
    BoundaryIdx    : list[int] - ordered top-vertex indices (boundary loop)
    NVerts         : int    - vertex count of the original flat layer
    ZBottom        : float  - flat bottom Z coordinate

Adapted from cmd_outline.py::_build_insole_mesh.
"""

import Rhino.Geometry as rg
import scriptcontext as sc


def _sole_z_at(brep, x, y, z_start):
    ray = rg.Ray3d(rg.Point3d(x, y, z_start), rg.Vector3d(0, 0, 1))
    hits = rg.Intersect.Intersection.RayShoot(ray, [brep], 1)
    if hits and len(hits) > 0:
        return hits[0].Z
    return None


def build_insole_mesh(last_brep, outline, total_thickness, bottom_outline,
                     max_edge, min_edge):
    tol = sc.doc.ModelAbsoluteTolerance
    bb = last_brep.GetBoundingBox(True)
    if not bb.IsValid:
        return None, None, 0, 0.0

    z_start = bb.Min.Z - 10.0
    fallback_z = bb.Min.Z

    def sole_z(x, y):
        z = _sole_z_at(last_brep, x, y, z_start)
        return z if z is not None else fallback_z

    planar = rg.Brep.CreatePlanarBreps(outline, tol)
    if not planar:
        return None, None, 0, 0.0
    planar_brep = planar[0]

    mp = rg.MeshingParameters.DefaultAnalysisMesh
    mp.MaximumEdgeLength = max_edge
    mp.MinimumEdgeLength = min_edge
    mp.GridAspectRatio = 1.0
    mp.SimplePlanes = False

    flats = rg.Mesh.CreateFromBrep(planar_brep, mp)
    if not flats:
        return None, None, 0, 0.0
    flat = flats[0]
    if flat.Vertices.Count < 4:
        return None, None, 0, 0.0

    n_verts = flat.Vertices.Count
    all_z = []
    for i in range(n_verts):
        v = flat.Vertices[i]
        all_z.append(sole_z(v.X, v.Y))
    z_bottom = min(all_z) - total_thickness

    mesh = rg.Mesh()
    for i in range(n_verts):
        v = flat.Vertices[i]
        mesh.Vertices.Add(v.X, v.Y, all_z[i])
    for i in range(n_verts):
        v = flat.Vertices[i]
        mesh.Vertices.Add(v.X, v.Y, z_bottom)

    for fi in range(flat.Faces.Count):
        f = flat.Faces[fi]
        if f.IsQuad:
            mesh.Faces.AddFace(f.A, f.B, f.C, f.D)
        else:
            mesh.Faces.AddFace(f.A, f.B, f.C)

    for fi in range(flat.Faces.Count):
        f = flat.Faces[fi]
        if f.IsQuad:
            mesh.Faces.AddFace(f.A + n_verts, f.D + n_verts,
                               f.C + n_verts, f.B + n_verts)
        else:
            mesh.Faces.AddFace(f.A + n_verts, f.C + n_verts, f.B + n_verts)

    boundary_edges = []
    boundary_verts = set()
    top = flat.TopologyEdges
    for ei in range(top.Count):
        cf = top.GetConnectedFaces(ei)
        if cf is not None and len(cf) == 1:
            ev = top.GetTopologyVertices(ei)
            a = flat.TopologyVertices.MeshVertexIndices(ev.I)[0]
            b = flat.TopologyVertices.MeshVertexIndices(ev.J)[0]
            boundary_edges.append((a, b))
            boundary_verts.add(a)
            boundary_verts.add(b)

    if bottom_outline is not None:
        for vi in boundary_verts:
            v = flat.Vertices[vi]
            ok, t = bottom_outline.ClosestPoint(rg.Point3d(v.X, v.Y, 0))
            if ok:
                bp = bottom_outline.PointAt(t)
                mesh.Vertices.SetVertex(vi + n_verts, bp.X, bp.Y, z_bottom)

    for a, b in boundary_edges:
        mesh.Faces.AddFace(a, b, b + n_verts, a + n_verts)

    adj = {}
    for a, b in boundary_edges:
        adj.setdefault(a, []).append(b)
        adj.setdefault(b, []).append(a)

    ordered = []
    if boundary_edges:
        start = boundary_edges[0][0]
        ordered.append(start)
        visited = {start}
        cur = start
        while True:
            nxt = None
            for nb in adj.get(cur, []):
                if nb not in visited:
                    nxt = nb
                    break
            if nxt is None:
                break
            ordered.append(nxt)
            visited.add(nxt)
            cur = nxt

    mesh.Normals.ComputeNormals()
    mesh.Compact()
    if not mesh.IsValid:
        mesh.RebuildNormals()

    return mesh, ordered, n_verts, z_bottom


# --- Defaults ---
ct = CoverThk if CoverThk is not None else 2.0
st = ShellThk if ShellThk is not None else 3.0
bt = BaseThk if BaseThk is not None else 5.0
mx = MaxEdge if MaxEdge else 3.0
mn = MinEdge if MinEdge else 1.0
total = ct + st + bt

if Last and Outline:
    Mesh, BoundaryIdx, NVerts, ZBottom = build_insole_mesh(
        Last, Outline, total, BottomOutline, mx, mn,
    )
else:
    Mesh, BoundaryIdx, NVerts, ZBottom = None, [], 0, 0.0
