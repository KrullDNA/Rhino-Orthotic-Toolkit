# -*- coding: utf-8 -*-
"""Orthotic Toolkit - OT_ExtractPlantar Command

Extracts a NURBS plantar surface from the foot scan mesh using a
ray-grid intersection algorithm (40x20 grid shooting rays in +Z).
"""

import System
import Rhino
import Rhino.Geometry as rg
import Rhino.Commands as rc
import Rhino.DocObjects as rd
import Rhino.UI as rui
import Eto.Forms as ef
import scriptcontext as sc

import state
from geometry import mesh_utils


PANEL_GUID = System.Guid("B2C3D4E5-F6A7-8901-BCDE-F12345678901")
OT_PLANTAR_LAYER = "OT_PlantarSurface"
PLANTAR_COLOR = System.Drawing.Color.FromArgb(255, 165, 0)  # Orange

GRID_U = 40
GRID_V = 20
SURFACE_DEGREE = 3


def _ensure_layer(name, color):
    """Create a layer if it does not exist; return its index."""
    layer_index = sc.doc.Layers.FindByFullPath(name, -1)
    if layer_index < 0:
        layer = rd.Layer()
        layer.Name = name
        layer.Color = color
        layer_index = sc.doc.Layers.Add(layer)
    return layer_index


def _get_smoothing_passes():
    """Get the smoothing passes value from the panel, default 2."""
    try:
        panels = rui.Panels.GetOpenPanelContents(PANEL_GUID)
        if panels is not None:
            for panel in panels:
                if hasattr(panel, "get_smoothing_passes"):
                    return panel.get_smoothing_passes()
    except Exception:
        pass
    return 2


def _refresh_panel_extraction(message):
    """Update the panel extraction status label."""
    try:
        panels = rui.Panels.GetOpenPanelContents(PANEL_GUID)
        if panels is not None:
            for panel in panels:
                if hasattr(panel, "update_extraction_label"):
                    panel.update_extraction_label(message)
    except Exception:
        pass


def _extract_plantar_surface(mesh):
    """Extract a NURBS surface from the plantar side of a mesh.

    Shoots a grid of rays in the +Z direction from below the mesh
    bounding box, collects intersection points on the bottom-most
    hits (plantar surface), and fits a NURBS surface through them.

    Args:
        mesh: A Mesh object oriented with plantar surface facing -Z.

    Returns:
        A tuple (surface, point_count) or (None, 0) on failure.
    """
    bbox = mesh.GetBoundingBox(True)
    if not bbox.IsValid:
        return None, 0

    # Ray origin plane sits below the mesh
    z_start = bbox.Min.Z - 10.0
    x_min = bbox.Min.X
    x_max = bbox.Max.X
    y_min = bbox.Min.Y
    y_max = bbox.Max.Y

    dx = (x_max - x_min) / (GRID_U - 1) if GRID_U > 1 else 0
    dy = (y_max - y_min) / (GRID_V - 1) if GRID_V > 1 else 0

    ray_dir = rg.Vector3d(0, 0, 1)
    hit_points = []

    for iu in range(GRID_U):
        for iv in range(GRID_V):
            x = x_min + iu * dx
            y = y_min + iv * dy
            origin = rg.Point3d(x, y, z_start)
            ray = rg.Ray3d(origin, ray_dir)

            t = rg.Intersect.Intersection.MeshRay(mesh, ray)
            if t >= 0:
                hit_pt = ray.PointAt(t)
                hit_points.append(hit_pt)

    point_count = len(hit_points)
    if point_count < 4:
        return None, point_count

    # Fit a NURBS surface through the hit points
    # Create a point grid for NurbsSurface.CreateThroughPoints
    # We need to reorganise hit_points back into a grid structure.
    # Since some rays may miss, rebuild a clean grid with only
    # rows/columns that have full coverage, or use point cloud fitting.

    # Approach: use the grid structure directly, replacing misses with
    # nearest-neighbour interpolation. Build a U x V point array.
    grid = [[None] * GRID_V for _ in range(GRID_U)]
    idx = 0
    for iu in range(GRID_U):
        for iv in range(GRID_V):
            x = x_min + iu * dx
            y = y_min + iv * dy
            origin = rg.Point3d(x, y, z_start)
            ray = rg.Ray3d(origin, ray_dir)
            t = rg.Intersect.Intersection.MeshRay(mesh, ray)
            if t >= 0:
                grid[iu][iv] = ray.PointAt(t)

    # Fill gaps by nearest-neighbour interpolation
    for iu in range(GRID_U):
        for iv in range(GRID_V):
            if grid[iu][iv] is None:
                # Find nearest non-None point
                best_pt = None
                best_dist_sq = float("inf")
                for su in range(GRID_U):
                    for sv in range(GRID_V):
                        if grid[su][sv] is not None:
                            d = (su - iu) ** 2 + (sv - iv) ** 2
                            if d < best_dist_sq:
                                best_dist_sq = d
                                best_pt = grid[su][sv]
                if best_pt is not None:
                    # Project the neighbour Z to this XY position
                    x = x_min + iu * dx
                    y = y_min + iv * dy
                    grid[iu][iv] = rg.Point3d(x, y, best_pt.Z)

    # Flatten to a list for CreateThroughPoints
    points = []
    for iu in range(GRID_U):
        for iv in range(GRID_V):
            pt = grid[iu][iv]
            if pt is None:
                # Fallback -- should not happen after gap fill
                points.append(rg.Point3d(
                    x_min + iu * dx,
                    y_min + iv * dy,
                    bbox.Min.Z,
                ))
            else:
                points.append(pt)

    try:
        surface = rg.NurbsSurface.CreateThroughPoints(
            points, GRID_U, GRID_V, SURFACE_DEGREE, SURFACE_DEGREE, False, False
        )
        return surface, point_count
    except Exception:
        return None, point_count


class OT_ExtractPlantar(rc.Command):
    """Extract a NURBS plantar surface from the foot scan mesh."""

    def __init__(self):
        super().__init__()

    @property
    def EnglishName(self):
        return "OT_ExtractPlantar"

    def RunCommand(self, doc, mode):
        # Validate prerequisites
        if state.foot_scan_mesh is None:
            ef.MessageBox.Show(
                "No foot scan mesh loaded. Please use Import Scan first.",
                "Orthotic Toolkit - No Scan",
                ef.MessageBoxButtons.OK,
                ef.MessageBoxType.Warning,
            )
            Rhino.RhinoApp.WriteLine(
                "Orthotic Toolkit: No foot scan mesh loaded."
            )
            return rc.Result.Failure

        # Validate mesh quality
        is_valid, msg = mesh_utils.validate_mesh_for_extraction(
            state.foot_scan_mesh
        )
        if not is_valid:
            ef.MessageBox.Show(
                "Mesh validation failed: {}".format(msg),
                "Orthotic Toolkit - Invalid Mesh",
                ef.MessageBoxButtons.OK,
                ef.MessageBoxType.Warning,
            )
            Rhino.RhinoApp.WriteLine(
                "Orthotic Toolkit: Mesh validation failed - {}".format(msg)
            )
            return rc.Result.Failure

        # Get smoothing passes from panel
        smoothing_passes = _get_smoothing_passes()

        # Apply Laplacian smoothing
        working_mesh = mesh_utils.apply_laplacian_smoothing(
            state.foot_scan_mesh, smoothing_passes
        )

        Rhino.RhinoApp.WriteLine(
            "Orthotic Toolkit: Applied {} smoothing pass(es).".format(
                smoothing_passes
            )
        )

        # Extract plantar surface
        surface, point_count = _extract_plantar_surface(working_mesh)

        if point_count < 200:
            Rhino.RhinoApp.WriteLine(
                "Orthotic Toolkit: WARNING - Low point count ({} points). "
                "Result may be inaccurate. Try re-orienting the scan.".format(
                    point_count
                )
            )

        if surface is None:
            Rhino.RhinoApp.WriteLine(
                "Orthotic Toolkit: Failed to create plantar surface "
                "({} intersection points).".format(point_count)
            )
            _refresh_panel_extraction(
                "Extraction failed ({} pts)".format(point_count)
            )
            return rc.Result.Failure

        # Store in state
        brep = rg.Brep.CreateFromSurface(surface)
        if brep is None:
            brep = surface.ToBrep()
        state.insole_top_surface = brep if brep is not None else surface

        # Add to document on OT_PlantarSurface layer
        layer_index = _ensure_layer(OT_PLANTAR_LAYER, PLANTAR_COLOR)
        attrs = rd.ObjectAttributes()
        attrs.LayerIndex = layer_index
        attrs.ColorSource = rd.ObjectColorSource.ColorFromLayer

        if brep is not None:
            doc.Objects.AddBrep(brep, attrs)
        else:
            doc.Objects.AddSurface(surface, attrs)

        doc.Views.Redraw()

        # Determine surface degree for reporting
        try:
            deg_u = surface.Degree(0)
            deg_v = surface.Degree(1)
            degree_str = "{}x{}".format(deg_u, deg_v)
        except Exception:
            degree_str = str(SURFACE_DEGREE)

        result_msg = "{} pts, degree {}".format(point_count, degree_str)
        _refresh_panel_extraction(result_msg)

        Rhino.RhinoApp.WriteLine(
            "Orthotic Toolkit: Plantar surface extracted. "
            "{} intersection points, surface degree {}.".format(
                point_count, degree_str
            )
        )
        return rc.Result.Success
