# -*- coding: utf-8 -*-
"""GHPython component: Detect Toe-Heel Orientation.

INPUT:
    Footprint  : Curve   (item)  - closed XY curve from component 01

OUTPUTS:
    Axis       : str     - "X" or "Y" (which axis runs toe-to-heel)
    ToeDir     : int     - +1 or -1 (sign along axis pointing toward toe)

Adapted from cmd_setlast.py::_detect_orientation.
"""

import Rhino.Geometry as rg


def detect_orientation(footprint):
    bbox = footprint.GetBoundingBox(True)
    if not bbox.IsValid:
        return "Y", 1

    x_len = bbox.Max.X - bbox.Min.X
    y_len = bbox.Max.Y - bbox.Min.Y

    if y_len >= x_len:
        axis = "Y"
        low_y = bbox.Min.Y + y_len * 0.15
        high_y = bbox.Max.Y - y_len * 0.15
        low_plane = rg.Plane(rg.Point3d(0, low_y, 0), rg.Vector3d.ZAxis)
        high_plane = rg.Plane(rg.Point3d(0, high_y, 0), rg.Vector3d.ZAxis)
    else:
        axis = "X"
        low_x = bbox.Min.X + x_len * 0.15
        high_x = bbox.Max.X - x_len * 0.15
        low_plane = rg.Plane(rg.Point3d(low_x, 0, 0), rg.Vector3d.ZAxis)
        high_plane = rg.Plane(rg.Point3d(high_x, 0, 0), rg.Vector3d.ZAxis)

    tol = 0.01
    low_w = high_w = 0.0
    try:
        ev = rg.Intersect.Intersection.CurvePlane(footprint, low_plane, tol)
        if ev and len(ev) >= 2:
            pts = [e.PointA for e in ev]
            if axis == "Y":
                low_w = max(p.X for p in pts) - min(p.X for p in pts)
            else:
                low_w = max(p.Y for p in pts) - min(p.Y for p in pts)
    except Exception:
        pass

    try:
        ev = rg.Intersect.Intersection.CurvePlane(footprint, high_plane, tol)
        if ev and len(ev) >= 2:
            pts = [e.PointA for e in ev]
            if axis == "Y":
                high_w = max(p.X for p in pts) - min(p.X for p in pts)
            else:
                high_w = max(p.Y for p in pts) - min(p.Y for p in pts)
    except Exception:
        pass

    toe_dir = 1 if high_w <= low_w else -1
    return axis, toe_dir


if Footprint:
    Axis, ToeDir = detect_orientation(Footprint)
else:
    Axis, ToeDir = "Y", 1
