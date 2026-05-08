# -*- coding: utf-8 -*-
"""Orthotic Toolkit - Brep Utility Functions

Provides safe boolean union, layer capping, and wedge solid creation
for the insole shape tools (Outline, Arch, Heel Cup, Met Dome, Posting).
"""

import math

import Rhino
import Rhino.Geometry as rg
import scriptcontext as sc


def safe_boolean_union(brep_a, brep_b, tolerance=None):
    """Attempt a boolean union of two Breps, returning the result or None.

    On failure, logs an error to the Rhino command history but does not
    raise an exception.

    Args:
        brep_a: First Brep operand.
        brep_b: Second Brep operand.
        tolerance: Model tolerance override. Uses doc tolerance if None.

    Returns:
        The unioned Brep, or None on failure.
    """
    if brep_a is None or brep_b is None:
        Rhino.RhinoApp.WriteLine(
            "Orthotic Toolkit: Boolean union skipped -- null operand."
        )
        return None

    if tolerance is None:
        tolerance = sc.doc.ModelAbsoluteTolerance

    try:
        results = rg.Brep.CreateBooleanUnion([brep_a, brep_b], tolerance)
        if results is not None and len(results) > 0:
            return results[0]

        Rhino.RhinoApp.WriteLine(
            "Orthotic Toolkit: Boolean union returned no result. "
            "Operands may not overlap or may be invalid."
        )
        return None
    except Exception as ex:
        Rhino.RhinoApp.WriteLine(
            "Orthotic Toolkit: Boolean union failed -- {}".format(ex)
        )
        return None


def cap_layer(top_surface, bottom_surface):
    """Create a closed solid between two offset surfaces.

    Lofts the edges of the top and bottom surfaces to form side walls,
    then joins everything into a single closed Brep.

    Args:
        top_surface: A Brep or Surface representing the top.
        bottom_surface: A Brep or Surface representing the bottom.

    Returns:
        A closed Brep solid, or None on failure.
    """
    if top_surface is None or bottom_surface is None:
        return None

    tol = sc.doc.ModelAbsoluteTolerance

    # Ensure Breps
    top_brep = (
        top_surface
        if isinstance(top_surface, rg.Brep)
        else rg.Brep.CreateFromSurface(top_surface)
    )
    bot_brep = (
        bottom_surface
        if isinstance(bottom_surface, rg.Brep)
        else rg.Brep.CreateFromSurface(bottom_surface)
    )

    if top_brep is None or bot_brep is None:
        return None

    try:
        # Get edge curves from both surfaces
        top_edges = [
            e.DuplicateCurve() for e in top_brep.Edges if e is not None
        ]
        bot_edges = [
            e.DuplicateCurve() for e in bot_brep.Edges if e is not None
        ]

        if not top_edges or not bot_edges:
            return None

        top_joined = rg.Curve.JoinCurves(top_edges, tol)
        bot_joined = rg.Curve.JoinCurves(bot_edges, tol)

        if not top_joined or not bot_joined:
            return None

        # Loft between edge curves to create side walls
        loft_curves = [top_joined[0], bot_joined[0]]
        lofts = rg.Brep.CreateFromLoft(
            loft_curves, rg.Point3d.Unset, rg.Point3d.Unset,
            rg.LoftType.Straight, False
        )

        if not lofts:
            return None

        # Join all pieces: top, bottom, side walls
        all_breps = [top_brep, bot_brep] + list(lofts)
        joined = rg.Brep.JoinBreps(all_breps, tol)
        if joined and len(joined) > 0:
            result = joined[0]
            if not result.IsSolid:
                result.Cap(tol)
            return result
        return None
    except Exception as ex:
        Rhino.RhinoApp.WriteLine(
            "Orthotic Toolkit: cap_layer failed -- {}".format(ex)
        )
        return None


def make_wedge_solid(base_curve, angle_deg, axis_vec, height_mm):
    """Create a tapered wedge solid from a base curve.

    Extrudes the base curve upward by height_mm, then applies a taper
    transformation based on the angle and axis.

    Args:
        base_curve: A closed planar Curve defining the wedge base.
        angle_deg: Taper angle in degrees.
        axis_vec: The axis Vector3d about which the wedge tapers.
        height_mm: Height of the wedge extrusion in mm.

    Returns:
        A Brep solid representing the wedge, or None on failure.
    """
    if base_curve is None or abs(angle_deg) < 0.01 or height_mm <= 0:
        return None

    tol = sc.doc.ModelAbsoluteTolerance

    try:
        # Get the centroid of the base curve
        area_props = rg.AreaMassProperties.Compute(base_curve)
        if area_props is None:
            return None
        centroid = area_props.Centroid

        # Create the extrusion direction (upward in Z)
        extrude_vec = rg.Vector3d(0, 0, height_mm)

        # Extrude the base curve
        srf = rg.Surface.CreateExtrusion(base_curve, extrude_vec)
        if srf is None:
            return None

        brep = srf.ToBrep()
        if brep is None:
            return None

        # Cap the open ends
        brep = brep.CapPlanarHoles(tol)
        if brep is None:
            return None

        # Apply taper: rotate the top face edges around the axis
        angle_rad = math.radians(angle_deg)
        taper_origin = rg.Point3d(centroid.X, centroid.Y, 0)

        # Create a shear-like transform: vertices at Z=height_mm get
        # rotated by angle_deg around the axis passing through centroid
        # We approximate the taper by transforming vertices based on Z height
        mesh = rg.Mesh.CreateFromBrep(brep, rg.MeshingParameters.Default)
        if mesh and len(mesh) > 0:
            # Use the brep directly with a non-uniform scale taper
            # For a proper wedge, we scale the top relative to the bottom
            tan_a = math.tan(angle_rad)
            axis_unit = rg.Vector3d(axis_vec)
            axis_unit.Unitize()

            # Create a perpendicular direction to the axis in XY
            perp = rg.Vector3d.CrossProduct(axis_unit, rg.Vector3d(0, 0, 1))
            if perp.Length < 0.001:
                perp = rg.Vector3d.CrossProduct(
                    axis_unit, rg.Vector3d(0, 1, 0)
                )
            perp.Unitize()

            # Shear the brep: for each Z-level, shift by tan(angle)*z
            # along the perpendicular direction
            shift = rg.Vector3d(perp)
            shift *= tan_a * height_mm

            # Build a shear transform
            xform = rg.Transform.Shear(
                rg.Plane(taper_origin, axis_unit, perp),
                rg.Vector3d(0, 0, 1),
                shift,
                rg.Vector3d(0, 0, 0),
            )

            brep_copy = brep.DuplicateBrep()
            brep_copy.Transform(xform)
            return brep_copy

        return brep
    except Exception as ex:
        Rhino.RhinoApp.WriteLine(
            "Orthotic Toolkit: make_wedge_solid failed -- {}".format(ex)
        )
        # Fallback: return the un-tapered extrusion
        try:
            extrude_vec = rg.Vector3d(0, 0, height_mm)
            srf = rg.Surface.CreateExtrusion(base_curve, extrude_vec)
            if srf is None:
                return None
            brep = srf.ToBrep()
            if brep is not None:
                brep = brep.CapPlanarHoles(tol)
            return brep
        except Exception:
            return None
