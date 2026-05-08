# -*- coding: utf-8 -*-
"""GHPython component: Extract Footprint from Shoe Last.

INPUTS  (set on the GHPython component):
    Last        : Brep         (item access)   - shoe last polysurface
    SectionPcts : list[float]  (list access)   - optional, defaults provided

OUTPUT:
    Footprint   : Curve        - closed curve projected to XY plane

Adapted from cmd_setlast.py::_get_footprint_by_section.
"""

import Rhino.Geometry as rg
import scriptcontext as sc

DEFAULT_SECTION_PCTS = [0.02, 0.05, 0.08, 0.10, 0.13, 0.15, 0.18, 0.20,
                        0.25, 0.30, 0.35, 0.40, 0.45, 0.50]


def extract_footprint(brep, section_pcts):
    tol = sc.doc.ModelAbsoluteTolerance
    bbox = brep.GetBoundingBox(True)
    if not bbox.IsValid:
        return None

    z_range = bbox.Max.Z - bbox.Min.Z
    if z_range < tol:
        return None

    xy_plane = rg.Plane.WorldXY
    all_closed = []

    for pct in section_pcts:
        section_z = bbox.Min.Z + z_range * pct
        section_plane = rg.Plane(rg.Point3d(0, 0, section_z), rg.Vector3d.ZAxis)
        section_curves = rg.Brep.CreateContourCurves(brep, section_plane)
        if not section_curves:
            continue

        joined = rg.Curve.JoinCurves(section_curves, tol * 10) or section_curves
        for crv in joined:
            if not crv.IsClosed:
                if crv.IsClosable(tol * 100):
                    crv.MakeClosed(tol * 100)
                else:
                    continue
            flat = rg.Curve.ProjectToPlane(crv, xy_plane)
            if flat is not None and flat.IsClosed:
                all_closed.append(flat)

    if not all_closed:
        return None
    if len(all_closed) == 1:
        return all_closed[0]

    try:
        union = rg.Curve.CreateBooleanUnion(all_closed, tol)
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
    for crv in all_closed:
        bb = crv.GetBoundingBox(True)
        a = (bb.Max.X - bb.Min.X) * (bb.Max.Y - bb.Min.Y)
        if a > best_area:
            best_area, best = a, crv
    return best


# --- Component body ---
pcts = SectionPcts if SectionPcts else DEFAULT_SECTION_PCTS
Footprint = extract_footprint(Last, pcts) if Last else None
