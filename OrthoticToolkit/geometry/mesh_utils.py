# -*- coding: utf-8 -*-
"""Orthotic Toolkit - Mesh Utility Functions

Provides mesh orientation and plantar boundary extraction for
foot scan processing. Used by Session 3 scan import tools and
as a fallback path in surface_utils.py.
"""

import Rhino.Geometry as rg


def apply_laplacian_smoothing(mesh, passes):
    """Apply iterative Laplacian smoothing to a mesh.

    Each pass sets every vertex position to the average of its
    topological neighbours. Uses mesh.TopologyVertices for neighbour
    lookup.

    Args:
        mesh: A Mesh object to smooth.
        passes: Number of smoothing iterations (0-5 typical).

    Returns:
        A new smoothed Mesh, or the original mesh if passes <= 0.
    """
    if mesh is None or passes <= 0:
        return mesh

    smoothed = mesh.DuplicateMesh()
    topo = smoothed.TopologyVertices

    for _ in range(passes):
        new_positions = []
        for vi in range(topo.Count):
            neighbours = topo.ConnectedTopologyVertices(vi)
            if neighbours is None or len(neighbours) == 0:
                new_positions.append(topo[vi])
                continue
            avg = rg.Point3f(0, 0, 0)
            for ni in neighbours:
                pt = topo[ni]
                avg.X += pt.X
                avg.Y += pt.Y
                avg.Z += pt.Z
            count = len(neighbours)
            avg.X /= count
            avg.Y /= count
            avg.Z /= count
            new_positions.append(avg)

        for vi in range(topo.Count):
            topo[vi] = new_positions[vi]

    smoothed.Normals.ComputeNormals()
    smoothed.FaceNormals.ComputeFaceNormals()
    return smoothed


def validate_mesh_for_extraction(mesh):
    """Validate that a mesh is suitable for plantar surface extraction.

    Checks that the mesh has faces, is not empty, and has no
    degenerate faces (faces with zero area).

    Args:
        mesh: A Mesh object to validate.

    Returns:
        A tuple (is_valid, message) where is_valid is True if the mesh
        passes all checks, and message describes any issue found.
    """
    if mesh is None:
        return False, "Mesh is None."

    if mesh.Vertices.Count == 0:
        return False, "Mesh has no vertices."

    if mesh.Faces.Count == 0:
        return False, "Mesh has no faces."

    # Check for degenerate faces (zero area)
    degenerate_count = 0
    for i in range(mesh.Faces.Count):
        face = mesh.Faces[i]
        v0 = mesh.Vertices[face.A]
        v1 = mesh.Vertices[face.B]
        v2 = mesh.Vertices[face.C]
        edge1 = rg.Vector3f(v1.X - v0.X, v1.Y - v0.Y, v1.Z - v0.Z)
        edge2 = rg.Vector3f(v2.X - v0.X, v2.Y - v0.Y, v2.Z - v0.Z)
        cross = rg.Vector3f(
            edge1.Y * edge2.Z - edge1.Z * edge2.Y,
            edge1.Z * edge2.X - edge1.X * edge2.Z,
            edge1.X * edge2.Y - edge1.Y * edge2.X,
        )
        area = (cross.X ** 2 + cross.Y ** 2 + cross.Z ** 2) ** 0.5
        if area < 1e-12:
            degenerate_count += 1

    if degenerate_count > 0:
        ratio = degenerate_count / mesh.Faces.Count
        if ratio > 0.5:
            return False, (
                "Mesh has {} degenerate faces out of {} total ({:.0f}%). "
                "Too many degenerate faces for extraction.".format(
                    degenerate_count, mesh.Faces.Count, ratio * 100
                )
            )

    return True, "Mesh is valid for extraction."


def orient_mesh_plantar_down(mesh):
    """Rotate a foot scan mesh so the plantar (sole) surface faces -Z.

    Analyses mesh face normals to determine which cluster represents
    the plantar surface, then rotates the mesh so that cluster points
    in the -Z direction.

    Args:
        mesh: A Mesh object (foot scan).

    Returns:
        A tuple (rotated_mesh, angle_degrees) where rotated_mesh is
        the reoriented Mesh and angle_degrees is the rotation applied.
        Returns (mesh, 0.0) if already oriented or on failure.
    """
    if mesh is None:
        return mesh, 0.0

    mesh.Normals.ComputeNormals()
    mesh.FaceNormals.ComputeFaceNormals()

    # Compute the average normal of all faces
    avg_normal = rg.Vector3d.Zero
    for i in range(mesh.FaceNormals.Count):
        fn = mesh.FaceNormals[i]
        avg_normal += rg.Vector3d(fn.X, fn.Y, fn.Z)

    if avg_normal.Length < 0.001:
        return mesh, 0.0

    avg_normal.Unitize()

    # We want the plantar surface (bottom of foot) to face -Z.
    # The plantar region typically has normals pointing generally downward
    # in a correctly scanned foot. We find the dominant downward direction.
    down = rg.Vector3d(0, 0, -1)

    # Accumulate a weighted "plantar normal" from faces that point
    # somewhat downward (dot > 0 with -Z)
    plantar_normal = rg.Vector3d.Zero
    plantar_count = 0

    for i in range(mesh.FaceNormals.Count):
        fn = mesh.FaceNormals[i]
        normal = rg.Vector3d(fn.X, fn.Y, fn.Z)
        dot = normal * down
        if dot > 0.0:
            plantar_normal += normal
            plantar_count += 1

    if plantar_count == 0 or plantar_normal.Length < 0.001:
        # No downward-facing normals found; try flipping
        plantar_normal = -avg_normal

    plantar_normal.Unitize()

    # Calculate the rotation needed to align plantar_normal with -Z
    dot_with_down = plantar_normal * down

    # If already close to aligned (within ~10 degrees), skip rotation
    import math
    angle_rad = math.acos(max(-1.0, min(1.0, dot_with_down)))
    angle_deg = math.degrees(angle_rad)

    if angle_deg < 10.0:
        return mesh, 0.0

    # Compute rotation axis (cross product of plantar_normal and -Z)
    axis = rg.Vector3d.CrossProduct(plantar_normal, down)
    if axis.Length < 0.0001:
        # Vectors are nearly parallel or anti-parallel
        if dot_with_down < 0:
            # Need 180 degree flip around X axis
            axis = rg.Vector3d(1, 0, 0)
            angle_rad = math.pi
            angle_deg = 180.0
        else:
            return mesh, 0.0

    axis.Unitize()

    # Rotate around the mesh centroid
    centroid = mesh.GetBoundingBox(True).Center
    xform = rg.Transform.Rotation(angle_rad, axis, centroid)

    rotated = mesh.DuplicateMesh()
    rotated.Transform(xform)
    rotated.Normals.ComputeNormals()
    rotated.FaceNormals.ComputeFaceNormals()

    return rotated, angle_deg


def get_plantar_boundary(mesh):
    """Extract the outer boundary curve of the plantar region of a mesh.

    Returns the naked edge boundary of the mesh as a joined polyline curve,
    which represents the perimeter of the foot scan.

    Args:
        mesh: A Mesh object.

    Returns:
        A Curve representing the mesh boundary, or None on failure.
    """
    if mesh is None:
        return None

    try:
        polylines = mesh.GetNakedEdges()
        if polylines is None or len(polylines) == 0:
            return None

        # Return the longest boundary (most likely the outer perimeter)
        best = None
        best_length = 0.0

        for polyline in polylines:
            curve = polyline.ToNurbsCurve()
            if curve is not None:
                length = curve.GetLength()
                if length > best_length:
                    best_length = length
                    best = curve

        return best
    except Exception:
        return None
