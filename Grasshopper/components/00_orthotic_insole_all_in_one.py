# -*- coding: utf-8 -*-
"""GHPython component: Orthotic Insole (All-In-One).

Self-contained pipeline: Last -> Footprint -> Outline -> Conforming Mesh
-> SubD + Edge Curves. Live updates as sliders move.

INPUTS  (configure on the GHPython component, all "item access" except Last):
    Last             : Brep   - shoe last polysurface
    PerimeterOffset  : float  - mm, default 2.0
    ToeExtension     : float  - mm, default 0.0
    HeelExtension    : float  - mm, default 0.0
    CoverThk         : float  - mm, default 2.0
    ShellThk         : float  - mm, default 3.0
    BaseThk          : float  - mm, default 5.0
    OverrideOutline  : Curve  - optional; bypass auto outline
    OverrideBottom   : Curve  - optional; sculpt the bottom edge
    MaxEdge          : float  - mesh max edge, default 3.0
    MinEdge          : float  - mesh min edge, default 1.0
    RebuildCount     : int    - CP count on output curves, default 20

OUTPUTS:
    SubD             : SubD     - smooth insole
    Mesh             : Mesh     - underlying mesh (fallback / debugging)
    Footprint        : Curve    - XY footprint outline
    Outline          : Curve    - offset insole perimeter (top, XY)
    TopEdge          : Curve    - 3D top edge along sole
    BottomEdge       : Curve    - 3D bottom edge (flat plane)
    Axis             : str      - detected toe-heel axis
    ToeDir           : int      - detected toe direction sign
"""

import Rhino.Geometry as rg
import scriptcontext as sc

DEFAULT_SECTION_PCTS = [0.02, 0.05, 0.08, 0.10, 0.13, 0.15, 0.18, 0.20,
                        0.25, 0.30, 0.35, 0.40, 0.45, 0.50]


# --- 1. Footprint ----------------------------------------------------------

def extract_footprint(brep):
    tol = sc.doc.ModelAbsoluteTolerance
    bbox = brep.GetBoundingBox(True)
    if not bbox.IsValid:
        return None
    z_range = bbox.Max.Z - bbox.Min.Z
    if z_range < tol:
        return None

    xy = rg.Plane.WorldXY
    closed_curves = []
    for pct in DEFAULT_SECTION_PCTS:
        z = bbox.Min.Z + z_range * pct
        plane = rg.Plane(rg.Point3d(0, 0, z), rg.Vector3d.ZAxis)
        sec = rg.Brep.CreateContourCurves(brep, plane)
        if not sec:
            continue
        joined = rg.Curve.JoinCurves(sec, tol * 10) or sec
        for crv in joined:
            if not crv.IsClosed:
                if crv.IsClosable(tol * 100):
                    crv.MakeClosed(tol * 100)
                else:
                    continue
            flat = rg.Curve.ProjectToPlane(crv, xy)
            if flat is not None and flat.IsClosed:
                closed_curves.append(flat)

    if not closed_curves:
        return None
    if len(closed_curves) == 1:
        return closed_curves[0]
    try:
        union = rg.Curve.CreateBooleanUnion(closed_curves, tol)
        if union:
            best, best_area = None, 0.0
            for crv in union:
                if crv.IsClosed:
                    bb = crv.GetBoundingBox(True)
                    a = (bb.Max.X - bb.Min.X) * (bb.Max.Y - bb.Min.Y)
                    if a > best_area:
                        best_area, best = a, crv
            if best is not None:
                return best
    except Exception:
        pass
    best, best_area = None, 0.0
    for crv in closed_curves:
        bb = crv.GetBoundingBox(True)
        a = (bb.Max.X - bb.Min.X) * (bb.Max.Y - bb.Min.Y)
        if a > best_area:
            best_area, best = a, crv
    return best


# --- 2. Orientation --------------------------------------------------------

def detect_orientation(footprint):
    bb = footprint.GetBoundingBox(True)
    if not bb.IsValid:
        return "Y", 1
    xL = bb.Max.X - bb.Min.X
    yL = bb.Max.Y - bb.Min.Y
    if yL >= xL:
        axis = "Y"
        lo = rg.Plane(rg.Point3d(0, bb.Min.Y + yL * 0.15, 0), rg.Vector3d.ZAxis)
        hi = rg.Plane(rg.Point3d(0, bb.Max.Y - yL * 0.15, 0), rg.Vector3d.ZAxis)
    else:
        axis = "X"
        lo = rg.Plane(rg.Point3d(bb.Min.X + xL * 0.15, 0, 0), rg.Vector3d.ZAxis)
        hi = rg.Plane(rg.Point3d(bb.Max.X - xL * 0.15, 0, 0), rg.Vector3d.ZAxis)

    def width(plane):
        try:
            ev = rg.Intersect.Intersection.CurvePlane(footprint, plane, 0.01)
            if ev and len(ev) >= 2:
                pts = [e.PointA for e in ev]
                if axis == "Y":
                    return max(p.X for p in pts) - min(p.X for p in pts)
                return max(p.Y for p in pts) - min(p.Y for p in pts)
        except Exception:
            pass
        return 0.0

    return axis, (1 if width(hi) <= width(lo) else -1)


# --- 3. Outline ------------------------------------------------------------

def build_outline(footprint, perim, toe, heel, axis, toe_dir, rebuild):
    tol = sc.doc.ModelAbsoluteTolerance
    plane = rg.Plane.WorldXY
    offs = footprint.Offset(plane, -perim, tol, rg.CurveOffsetCornerStyle.Sharp)
    if not offs:
        offs = footprint.Offset(plane, perim, tol, rg.CurveOffsetCornerStyle.Sharp)
    if not offs:
        return None
    outline = offs[0]
    if toe != 0 or heel != 0:
        bb = outline.GetBoundingBox(True)
        if bb.IsValid:
            ax_range = (bb.Max.X - bb.Min.X) if axis == "X" else (bb.Max.Y - bb.Min.Y)
            if ax_range > 0:
                scale = (ax_range + toe + heel) / ax_range
                shift = toe_dir * (toe - heel) / 2.0
                bp = rg.Plane(bb.Center, rg.Vector3d.XAxis, rg.Vector3d.YAxis)
                if axis == "X":
                    outline.Transform(rg.Transform.Scale(bp, scale, 1.0, 1.0))
                    if abs(shift) > 0.001:
                        outline.Transform(rg.Transform.Translation(shift, 0, 0))
                else:
                    outline.Transform(rg.Transform.Scale(bp, 1.0, scale, 1.0))
                    if abs(shift) > 0.001:
                        outline.Transform(rg.Transform.Translation(0, shift, 0))
    if not outline.IsClosed:
        outline.MakeClosed(tol)
    if rebuild and rebuild >= 4:
        rb = outline.Rebuild(rebuild, 3, False)
        if rb is not None:
            outline = rb
    return outline


# --- 4. Conforming mesh ---------------------------------------------------

def build_insole_mesh(brep, outline, thickness, bot_outline, max_e, min_e):
    tol = sc.doc.ModelAbsoluteTolerance
    bb = brep.GetBoundingBox(True)
    if not bb.IsValid:
        return None, [], 0, 0.0
    z_start = bb.Min.Z - 10.0
    fallback = bb.Min.Z

    def sole_z(x, y):
        ray = rg.Ray3d(rg.Point3d(x, y, z_start), rg.Vector3d(0, 0, 1))
        hits = rg.Intersect.Intersection.RayShoot(ray, [brep], 1)
        return hits[0].Z if (hits and len(hits) > 0) else fallback

    planar = rg.Brep.CreatePlanarBreps(outline, tol)
    if not planar:
        return None, [], 0, 0.0

    mp = rg.MeshingParameters.DefaultAnalysisMesh
    mp.MaximumEdgeLength = max_e
    mp.MinimumEdgeLength = min_e
    mp.GridAspectRatio = 1.0
    mp.SimplePlanes = False
    flats = rg.Mesh.CreateFromBrep(planar[0], mp)
    if not flats:
        return None, [], 0, 0.0
    flat = flats[0]
    if flat.Vertices.Count < 4:
        return None, [], 0, 0.0

    n = flat.Vertices.Count
    zs = [sole_z(flat.Vertices[i].X, flat.Vertices[i].Y) for i in range(n)]
    z_bot = min(zs) - thickness

    mesh = rg.Mesh()
    for i in range(n):
        v = flat.Vertices[i]
        mesh.Vertices.Add(v.X, v.Y, zs[i])
    for i in range(n):
        v = flat.Vertices[i]
        mesh.Vertices.Add(v.X, v.Y, z_bot)

    for fi in range(flat.Faces.Count):
        f = flat.Faces[fi]
        if f.IsQuad:
            mesh.Faces.AddFace(f.A, f.B, f.C, f.D)
        else:
            mesh.Faces.AddFace(f.A, f.B, f.C)
    for fi in range(flat.Faces.Count):
        f = flat.Faces[fi]
        if f.IsQuad:
            mesh.Faces.AddFace(f.A + n, f.D + n, f.C + n, f.B + n)
        else:
            mesh.Faces.AddFace(f.A + n, f.C + n, f.B + n)

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

    if bot_outline is not None:
        for vi in boundary_verts:
            v = flat.Vertices[vi]
            ok, t = bot_outline.ClosestPoint(rg.Point3d(v.X, v.Y, 0))
            if ok:
                bp = bot_outline.PointAt(t)
                mesh.Vertices.SetVertex(vi + n, bp.X, bp.Y, z_bot)

    for a, b in boundary_edges:
        mesh.Faces.AddFace(a, b, b + n, a + n)

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
    return mesh, ordered, n, z_bot


def edge_curves(mesh, ordered, n, rebuild):
    if not ordered or len(ordered) < 3 or n <= 0:
        return None, None
    top_pts, bot_pts = [], []
    for vi in ordered:
        tv = mesh.Vertices[vi]
        top_pts.append(rg.Point3d(tv.X, tv.Y, tv.Z))
        bv = mesh.Vertices[vi + n]
        bot_pts.append(rg.Point3d(bv.X, bv.Y, bv.Z))
    top_pts.append(top_pts[0])
    bot_pts.append(bot_pts[0])
    t = rg.Curve.CreateInterpolatedCurve(top_pts, 3, rg.CurveKnotStyle.ChordSquareRoot)
    b = rg.Curve.CreateInterpolatedCurve(bot_pts, 3, rg.CurveKnotStyle.ChordSquareRoot)
    if t is not None and rebuild and rebuild >= 4:
        rb = t.Rebuild(rebuild, 3, False)
        if rb is not None:
            t = rb
    if b is not None and rebuild and rebuild >= 4:
        rb = b.Rebuild(rebuild, 3, False)
        if rb is not None:
            b = rb
    return t, b


# --- Pipeline --------------------------------------------------------------

po = PerimeterOffset if PerimeterOffset is not None else 2.0
te = ToeExtension if ToeExtension is not None else 0.0
he = HeelExtension if HeelExtension is not None else 0.0
ct = CoverThk if CoverThk is not None else 2.0
st = ShellThk if ShellThk is not None else 3.0
bt = BaseThk if BaseThk is not None else 5.0
mx = MaxEdge if MaxEdge else 3.0
mn = MinEdge if MinEdge else 1.0
rb = RebuildCount if RebuildCount else 20
total = ct + st + bt

SubD = Mesh = Footprint = Outline = TopEdge = BottomEdge = None
Axis, ToeDir = "Y", 1

if Last:
    Footprint = extract_footprint(Last)
    if Footprint:
        Axis, ToeDir = detect_orientation(Footprint)
        Outline = OverrideOutline if OverrideOutline else build_outline(
            Footprint, po, te, he, Axis, ToeDir, rb,
        )
        if Outline:
            Mesh, ordered, nv, _ = build_insole_mesh(
                Last, Outline, total, OverrideBottom, mx, mn,
            )
            if Mesh:
                TopEdge, BottomEdge = edge_curves(Mesh, ordered, nv, rb)
                sd = rg.SubD.CreateFromMesh(Mesh)
                if sd is not None and sd.IsValid:
                    SubD = sd
