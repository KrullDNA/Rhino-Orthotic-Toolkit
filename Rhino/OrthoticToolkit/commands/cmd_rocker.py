# -*- coding: utf-8 -*-
"""Orthotic Toolkit - OT_RockerOutline Command

Creates a 2D rocker-bottom contact outline curve representing the flat
contact zone between forefoot and rearfoot tangent points of the insole.
"""

import System
import Rhino
import Rhino.Geometry as rg
import Rhino.Commands as rc
import Rhino.DocObjects as rd
import Eto.Forms as ef
import scriptcontext as sc

import state
from geometry.layer_utils import ensure_layer, clear_layer


OT_ROCKER_LAYER = "OT_RockerContact"
ROCKER_OFFSET_Z = 2.0  # Offset upward from base plane


class OT_RockerOutline(rc.Command):
    """Create the rocker-bottom contact outline curve."""

    def __init__(self):
        super().__init__()

    @property
    def EnglishName(self):
        return "OT_RockerOutline"

    def RunCommand(self, doc, mode):
        if state.active_last_brep is None:
            ef.MessageBox.Show(
                "No shoe last selected. Please use Select Last first.",
                "Orthotic Toolkit - No Last",
                ef.MessageBoxButtons.OK,
                ef.MessageBoxType.Warning,
            )
            return rc.Result.Failure

        if state.insole_brep is None:
            ef.MessageBox.Show(
                "No insole Brep available. Build an insole first.",
                "Orthotic Toolkit - No Insole",
                ef.MessageBoxButtons.OK,
                ef.MessageBoxType.Warning,
            )
            return rc.Result.Failure

        brep = state.insole_brep
        bbox = brep.GetBoundingBox(True)

        if not bbox.IsValid:
            Rhino.RhinoApp.WriteLine(
                "Orthotic Toolkit: Insole bounding box invalid."
            )
            return rc.Result.Failure

        tol = sc.doc.ModelAbsoluteTolerance

        # Find tangent points along the bottom of the insole profile
        # by casting rays upward along a longitudinal grid and finding
        # the lowest intersection points
        x_center = (bbox.Min.X + bbox.Max.X) / 2.0
        y_min = bbox.Min.Y
        y_max = bbox.Max.Y
        y_range = y_max - y_min
        z_base = bbox.Min.Z

        # Sample the bottom profile along Y
        n_samples = 40
        profile_points = []

        for i in range(n_samples):
            t = i / (n_samples - 1.0)
            y = y_min + t * y_range

            # Scan across X at this Y level to find the bottom contact width
            x_min_contact = None
            x_max_contact = None

            for j in range(20):
                tx = j / 19.0
                x = bbox.Min.X + tx * (bbox.Max.X - bbox.Min.X)

                ray = rg.Ray3d(
                    rg.Point3d(x, y, z_base - 1.0),
                    rg.Vector3d(0, 0, 1),
                )
                hits = rg.Intersect.Intersection.RayShoot(ray, [brep], 1)

                if hits is not None and len(hits) > 0:
                    hit_z = z_base - 1.0 + hits[0]
                    # Check if this point is near the base plane
                    # (within 1mm of the lowest Z -- the "flat contact zone")
                    if hit_z <= z_base + 1.0:
                        if x_min_contact is None or x < x_min_contact:
                            x_min_contact = x
                        if x_max_contact is None or x > x_max_contact:
                            x_max_contact = x

            if x_min_contact is not None and x_max_contact is not None:
                # Add the left and right contact edges
                profile_points.append(rg.Point3d(
                    x_min_contact, y, z_base + ROCKER_OFFSET_Z
                ))
                profile_points.append(rg.Point3d(
                    x_max_contact, y, z_base + ROCKER_OFFSET_Z
                ))

        if len(profile_points) < 6:
            # Fallback: use the outline projected to base plane + offset
            if state.insole_outline is not None:
                outline_copy = state.insole_outline.DuplicateCurve()
                move_xform = rg.Transform.Translation(
                    0, 0, z_base + ROCKER_OFFSET_Z
                )
                outline_copy.Transform(move_xform)

                # Flatten to Z plane
                flatten = rg.Transform.PlanarProjection(
                    rg.Plane(
                        rg.Point3d(0, 0, z_base + ROCKER_OFFSET_Z),
                        rg.Vector3d.ZAxis,
                    )
                )
                outline_copy.Transform(flatten)

                rocker_curve = outline_copy
            else:
                Rhino.RhinoApp.WriteLine(
                    "Orthotic Toolkit: Not enough contact points "
                    "for rocker outline."
                )
                return rc.Result.Failure
        else:
            # Build a closed curve from the contact perimeter
            # Separate left and right edges
            left_pts = profile_points[0::2]
            right_pts = profile_points[1::2]
            right_pts.reverse()

            # Create a closed loop: left edge forward, right edge backward
            loop_pts = left_pts + right_pts
            loop_pts.append(loop_pts[0])  # Close the loop

            rocker_curve = rg.Curve.CreateInterpolatedCurve(
                loop_pts, 3, rg.CurveKnotStyle.Chord
            )

        if rocker_curve is None:
            Rhino.RhinoApp.WriteLine(
                "Orthotic Toolkit: Failed to create rocker contact curve."
            )
            return rc.Result.Failure

        # Clear previous rocker objects
        clear_layer(OT_ROCKER_LAYER)
        layer_index = ensure_layer(OT_ROCKER_LAYER)

        # Add the rocker curve to the document
        attrs = rd.ObjectAttributes()
        attrs.LayerIndex = layer_index
        attrs.ColorSource = rd.ObjectColorSource.ColorFromLayer
        guid = doc.Objects.AddCurve(rocker_curve, attrs)

        if guid == System.Guid.Empty:
            Rhino.RhinoApp.WriteLine(
                "Orthotic Toolkit: Failed to add rocker curve to document."
            )
            return rc.Result.Failure

        doc.Views.Redraw()

        Rhino.RhinoApp.WriteLine(
            "Orthotic Toolkit: Rocker contact outline created on "
            "{} layer, offset {:.0f}mm above base.".format(
                OT_ROCKER_LAYER, ROCKER_OFFSET_Z
            )
        )
        return rc.Result.Success
