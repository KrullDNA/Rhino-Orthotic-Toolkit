# -*- coding: utf-8 -*-
"""GHPython component: Build Insole Outline.

INPUTS:
    Footprint        : Curve  (item)  - from component 01
    Axis             : str    (item)  - "X" or "Y", from component 02
    ToeDir           : int    (item)  - +1 or -1, from component 02
    PerimeterOffset  : float  (item)  - mm, default 2.0
    ToeExtension     : float  (item)  - mm, default 0.0
    HeelExtension    : float  (item)  - mm, default 0.0
    RebuildCount     : int    (item)  - control point count, default 20

OUTPUT:
    Outline          : Curve  - closed NURBS outline with editable CPs

Adapted from cmd_outline.py::_build_outline_curve.
"""

import Rhino.Geometry as rg
import scriptcontext as sc


def build_outline(footprint, perimeter_offset, toe_ext, heel_ext, axis, toe_dir, rebuild_count):
    tol = sc.doc.ModelAbsoluteTolerance
    plane = rg.Plane.WorldXY

    offset_curves = footprint.Offset(plane, -perimeter_offset, tol, rg.CurveOffsetCornerStyle.Sharp)
    if not offset_curves:
        offset_curves = footprint.Offset(plane, perimeter_offset, tol, rg.CurveOffsetCornerStyle.Sharp)
    if not offset_curves:
        return None

    outline = offset_curves[0]

    if toe_ext != 0 or heel_ext != 0:
        bbox = outline.GetBoundingBox(True)
        if bbox.IsValid:
            center = bbox.Center
            ax_range = (bbox.Max.X - bbox.Min.X) if axis == "X" else (bbox.Max.Y - bbox.Min.Y)
            if ax_range > 0:
                total_ext = toe_ext + heel_ext
                scale_factor = (ax_range + total_ext) / ax_range
                shift = toe_dir * (toe_ext - heel_ext) / 2.0
                base_plane = rg.Plane(center, rg.Vector3d.XAxis, rg.Vector3d.YAxis)
                if axis == "X":
                    outline.Transform(rg.Transform.Scale(base_plane, scale_factor, 1.0, 1.0))
                    if abs(shift) > 0.001:
                        outline.Transform(rg.Transform.Translation(shift, 0, 0))
                else:
                    outline.Transform(rg.Transform.Scale(base_plane, 1.0, scale_factor, 1.0))
                    if abs(shift) > 0.001:
                        outline.Transform(rg.Transform.Translation(0, shift, 0))

    if not outline.IsClosed:
        outline.MakeClosed(tol)

    if rebuild_count and rebuild_count >= 4:
        rebuilt = outline.Rebuild(rebuild_count, 3, False)
        if rebuilt is not None:
            outline = rebuilt

    return outline


# --- Defaults ---
po = PerimeterOffset if PerimeterOffset is not None else 2.0
te = ToeExtension if ToeExtension is not None else 0.0
he = HeelExtension if HeelExtension is not None else 0.0
ax = Axis if Axis else "Y"
td = ToeDir if ToeDir is not None else 1
rc = RebuildCount if RebuildCount else 20

Outline = build_outline(Footprint, po, te, he, ax, td, rc) if Footprint else None
