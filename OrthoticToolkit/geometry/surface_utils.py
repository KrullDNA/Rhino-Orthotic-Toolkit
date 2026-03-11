# -*- coding: utf-8 -*-
"""Orthotic Toolkit - Surface Utility Functions

Provides the inverse sole surface creation, surface projection,
bounding box helpers, and gap tolerance checking.
"""

import random

import Rhino.Geometry as rg
import scriptcontext as sc


def create_inverse_sole_surface(sole_face, cover_thickness_mm):
    """Create the inverse (offset) sole surface for insole top.

    Offsets the sole face inward by cover_thickness_mm. If the NURBS
    offset fails, falls back to meshing the surface, offsetting the
    mesh, and converting back to a Brep.

    Args:
        sole_face: A BrepFace representing the sole of the shoe last.
        cover_thickness_mm: Offset distance in mm (positive value).

    Returns:
        A Brep representing the inverse sole surface, or None on failure.
    """
    srf = sole_face.DuplicateSurface()
    if srf is None:
        return None

    tol = sc.doc.ModelAbsoluteTolerance

    # Try NURBS surface offset first (offset inward = negative direction)
    try:
        offset = srf.Offset(-cover_thickness_mm, tol)
        if offset is not None:
            brep = rg.Brep.CreateFromSurface(offset)
            if brep is not None:
                return brep
    except Exception:
        pass

    # Fallback: mesh the surface, offset the mesh, convert back to Brep
    try:
        mp = rg.MeshingParameters.Default
        brep_from_face = sole_face.DuplicateFace(True)
        if brep_from_face is None:
            return None
        meshes = rg.Mesh.CreateFromBrep(brep_from_face, mp)
        if meshes is None or len(meshes) == 0:
            return None
        mesh = meshes[0]
        mesh.Offset(-cover_thickness_mm)
        result = rg.Brep.CreateFromMesh(mesh, True)
        return result
    except Exception:
        return None


def get_surface_bbox(surface):
    """Return the bounding box of a surface or Brep.

    Args:
        surface: A Surface or Brep object.

    Returns:
        A BoundingBox, or BoundingBox.Empty on failure.
    """
    if surface is None:
        return rg.BoundingBox.Empty
    try:
        return surface.GetBoundingBox(True)
    except Exception:
        return rg.BoundingBox.Empty


def project_curve_to_plane(curve, plane):
    """Project a curve onto a plane.

    Args:
        curve: A Curve object to project.
        plane: A Plane to project onto.

    Returns:
        A list of projected Curve objects, or an empty list on failure.
    """
    if curve is None or plane is None:
        return []

    tol = sc.doc.ModelAbsoluteTolerance
    direction = plane.Normal

    try:
        projected = rg.Curve.ProjectToPlane(curve, plane)
        if projected is not None:
            return [projected]
    except Exception:
        pass

    # Fallback using ProjectToBrep with a large planar surface
    try:
        interval = rg.Interval(-100000, 100000)
        plane_srf = rg.PlaneSurface(plane, interval, interval)
        plane_brep = plane_srf.ToBrep()
        results = rg.Curve.ProjectToBrep(
            curve, [plane_brep], direction, tol
        )
        if results is not None and len(results) > 0:
            return list(results)
    except Exception:
        pass

    return []


def check_gap_tolerance(srf_a, srf_b, tolerance_mm):
    """Check that two surfaces are within gap tolerance everywhere.

    Samples 50 random points on srf_a, measures closest distance to
    srf_b, and returns True only if all distances are within tolerance_mm.

    Args:
        srf_a: A Brep or Surface to sample points from.
        srf_b: A Brep or Surface to measure distance to.
        tolerance_mm: Maximum allowed gap in mm.

    Returns:
        True if all sampled distances are within tolerance, False otherwise.
    """
    if srf_a is None or srf_b is None:
        return False

    # Ensure we have Breps for point sampling
    brep_a = srf_a if isinstance(srf_a, rg.Brep) else rg.Brep.CreateFromSurface(srf_a)
    brep_b = srf_b if isinstance(srf_b, rg.Brep) else rg.Brep.CreateFromSurface(srf_b)

    if brep_a is None or brep_b is None:
        return False

    bbox_a = brep_a.GetBoundingBox(True)
    if not bbox_a.IsValid:
        return False

    sample_count = 50
    max_dist = 0.0

    for i in range(sample_count):
        # Generate a random UV parameter on the first face of brep_a
        face = brep_a.Faces[0]
        u_domain = face.Domain(0)
        v_domain = face.Domain(1)

        u = u_domain.Min + random.random() * (u_domain.Max - u_domain.Min)
        v = v_domain.Min + random.random() * (v_domain.Max - v_domain.Min)

        pt = face.PointAt(u, v)

        # Find closest point on brep_b
        cp = brep_b.ClosestPoint(pt)
        if cp is not None:
            dist = pt.DistanceTo(cp)
            if dist > max_dist:
                max_dist = dist
            if dist > tolerance_mm:
                return False

    return True
