# -*- coding: utf-8 -*-
"""Orthotic Toolkit - OT_GenerateOutline Command

Generates the insole outline by offsetting the footprint curve,
then creates a sole-conforming insole Brep whose top surface matches
the shoe last's sole shape.  Falls back to flat extrusion if the
conforming approach fails.
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
from geometry.layer_utils import ensure_layer


PANEL_GUID = System.Guid("B2C3D4E5-F6A7-8901-BCDE-F12345678901")
OT_OUTLINE_LAYER = "OT_Outline"
OT_INSOLE_LAYER = "OT_Insole"

# Grid resolution for sole surface ray sampling
SOLE_GRID_U = 30
SOLE_GRID_V = 15


def _get_panel_values():
    """Read outline parameters from the panel, falling back to state defaults."""
    try:
        panels = rui.Panels.GetOpenPanelContents(PANEL_GUID)
        if panels is not None:
            for panel in panels:
                if hasattr(panel, "get_outline_params"):
                    return panel.get_outline_params()
    except Exception:
        pass
    return state.perimeter_offset, state.toe_extension, state.heel_extension


def _show_panel_warning(message):
    """Show an amber warning on the panel's Outline tab."""
    try:
        panels = rui.Panels.GetOpenPanelContents(PANEL_GUID)
        if panels is not None:
            for panel in panels:
                if hasattr(panel, "show_tab_warning"):
                    panel.show_tab_warning("Outline", message)
    except Exception:
        pass


def _sole_z_at(last_brep, x, y, z_start):
    """Ray-shoot upward from (x, y, z_start) into the last brep.

    Returns the Z coordinate of the first hit (sole surface), or None.
    """
    origin = rg.Point3d(x, y, z_start)
    ray = rg.Ray3d(origin, rg.Vector3d(0, 0, 1))
    hits = rg.Intersect.Intersection.RayShoot(ray, [last_brep], 1)
    if hits is not None and len(hits) > 0:
        return ray.PointAt(hits[0]).Z
    return None


def _create_conforming_insole(last_brep, outline, total_thickness):
    """Create an insole Brep whose top surface conforms to the shoe last sole.

    Shoots a grid of rays upward from below the shoe last to capture the
    sole surface shape, builds a 3D boundary curve on the sole, creates
    a patch surface through the interior points, then builds a solid with
    uniform thickness below.

    Falls back to None if the conforming approach fails.
    """
    tol = sc.doc.ModelAbsoluteTolerance
    brep_bbox = last_brep.GetBoundingBox(True)
    outline_bbox = outline.GetBoundingBox(True)

    if not brep_bbox.IsValid or not outline_bbox.IsValid:
        return None

    z_start = brep_bbox.Min.Z - 10.0

    # --- Step 1: Create 3D boundary curve on the sole surface ---
    div_params = outline.DivideByCount(80, True)
    if div_params is None or len(div_params) < 10:
        return None

    z_values = []
    boundary_pts = []
    for t in div_params:
        pt = outline.PointAt(t)
        z = _sole_z_at(last_brep, pt.X, pt.Y, z_start)
        if z is None:
            z = brep_bbox.Min.Z
        z_values.append(z)
        boundary_pts.append(rg.Point3d(pt.X, pt.Y, z))

    # Close the boundary
    boundary_pts.append(boundary_pts[0])

    top_boundary = rg.Curve.CreateInterpolatedCurve(boundary_pts, 3)
    if top_boundary is None:
        return None
    if not top_boundary.IsClosed:
        top_boundary.MakeClosed(tol * 10)

    z_min_sole = min(z_values)
    z_bottom = z_min_sole - total_thickness

    # --- Step 2: Collect interior sole points ---
    x_min = outline_bbox.Min.X
    x_max = outline_bbox.Max.X
    y_min = outline_bbox.Min.Y
    y_max = outline_bbox.Max.Y
    dx = (x_max - x_min) / (SOLE_GRID_U - 1)
    dy = (y_max - y_min) / (SOLE_GRID_V - 1)
    xy_plane = rg.Plane.WorldXY

    interior_points = []
    for iu in range(SOLE_GRID_U):
        for iv in range(SOLE_GRID_V):
            x = x_min + iu * dx
            y = y_min + iv * dy
            pt = rg.Point3d(x, y, 0)
            if outline.Contains(pt, xy_plane, tol) == rg.PointContainment.Outside:
                continue
            z = _sole_z_at(last_brep, x, y, z_start)
            if z is not None:
                interior_points.append(rg.Point(rg.Point3d(x, y, z)))

    if len(interior_points) < 10:
        return None

    # --- Step 3: Create top surface via Brep.CreatePatch ---
    geometry = [top_boundary]
    geometry.extend(interior_points)

    top_patch = None
    try:
        top_patch = rg.Brep.CreatePatch(
            geometry,
            None,           # no starting surface
            10, 10,         # u/v spans
            True,           # trim to boundary
            False,          # no tangency
            1.0,            # point spacing
            1.0,            # flexibility
            0.0,            # surface pull
            [True],         # fix boundary edge
            tol,
        )
    except Exception:
        pass

    if top_patch is None:
        return None

    # --- Step 4: Create bottom boundary + flat bottom surface ---
    bottom_pts = []
    for p in boundary_pts[:-1]:
        bottom_pts.append(rg.Point3d(p.X, p.Y, z_bottom))
    bottom_pts.append(bottom_pts[0])

    bottom_boundary = rg.Curve.CreateInterpolatedCurve(bottom_pts, 3)
    if bottom_boundary is None:
        return None
    if not bottom_boundary.IsClosed:
        bottom_boundary.MakeClosed(tol * 10)

    bottom_breps = rg.Brep.CreatePlanarBreps(bottom_boundary, tol)
    if bottom_breps is None or len(bottom_breps) == 0:
        return None
    bottom_patch = bottom_breps[0]

    # --- Step 5: Create side walls by lofting top → bottom boundary ---
    lofts = rg.Brep.CreateFromLoft(
        [top_boundary, bottom_boundary],
        rg.Point3d.Unset, rg.Point3d.Unset,
        rg.LoftType.Straight, False,
    )
    if lofts is None or len(lofts) == 0:
        return None

    # --- Step 6: Join into a solid ---
    all_breps = [top_patch] + list(lofts) + [bottom_patch]
    joined = rg.Brep.JoinBreps(all_breps, tol)
    if joined is not None and len(joined) > 0:
        result = joined[0]
        if not result.IsSolid:
            capped = result.CapPlanarHoles(tol)
            if capped is not None:
                result = capped
        return result

    return None


def _create_flat_insole(outline, total_thickness):
    """Fallback: create a simple flat-extruded insole from the outline."""
    tol = sc.doc.ModelAbsoluteTolerance
    extrude_vec = rg.Vector3d(0, 0, -total_thickness)
    srf = rg.Surface.CreateExtrusion(outline, extrude_vec)
    if srf is None:
        return None
    brep = srf.ToBrep()
    if brep is None:
        return None
    capped = brep.CapPlanarHoles(tol)
    return capped if capped is not None else brep


class OT_GenerateOutline(rc.Command):
    """Generate the insole outline and sole-conforming Brep."""

    def __init__(self):
        super().__init__()

    @property
    def EnglishName(self):
        return "OT_GenerateOutline"

    def RunCommand(self, doc, mode):
        # Check prerequisite: shoe last must be selected
        if state.active_last_brep is None:
            ef.MessageBox.Show(
                "No shoe last selected. Please use Select Last first.",
                "Orthotic Toolkit - No Last",
                ef.MessageBoxButtons.OK,
                ef.MessageBoxType.Warning,
            )
            Rhino.RhinoApp.WriteLine(
                "Orthotic Toolkit: No shoe last selected."
            )
            return rc.Result.Failure

        if state.footprint_curve is None:
            Rhino.RhinoApp.WriteLine(
                "Orthotic Toolkit: No footprint curve available. "
                "Run Select Last first."
            )
            return rc.Result.Failure

        # Read parameters
        perimeter_offset, toe_ext, heel_ext = _get_panel_values()
        state.perimeter_offset = perimeter_offset
        state.toe_extension = toe_ext
        state.heel_extension = heel_ext

        tol = sc.doc.ModelAbsoluteTolerance
        plane = rg.Plane.WorldXY

        # Offset the footprint curve inward by perimeter_offset
        footprint = state.footprint_curve
        offset_curves = footprint.Offset(
            plane, -perimeter_offset, tol, rg.CurveOffsetCornerStyle.Sharp
        )

        if offset_curves is None or len(offset_curves) == 0:
            # Try outward offset if inward failed
            offset_curves = footprint.Offset(
                plane, perimeter_offset, tol, rg.CurveOffsetCornerStyle.Sharp
            )

        if offset_curves is None or len(offset_curves) == 0:
            Rhino.RhinoApp.WriteLine(
                "Orthotic Toolkit: Footprint offset failed."
            )
            _show_panel_warning("Footprint offset failed.")
            return rc.Result.Failure

        outline = offset_curves[0]

        # Apply toe and heel extensions by scaling the outline
        # at the toe (max Y) and heel (min Y) ends
        if toe_ext != 0 or heel_ext != 0:
            bbox = outline.GetBoundingBox(True)
            if bbox.IsValid:
                center = bbox.Center
                y_range = bbox.Max.Y - bbox.Min.Y
                if y_range > 0:
                    total_ext = toe_ext + heel_ext
                    scale_y = (y_range + total_ext) / y_range
                    shift_y = (toe_ext - heel_ext) / 2.0

                    xform_scale = rg.Transform.Scale(
                        rg.Plane(center, rg.Vector3d.XAxis, rg.Vector3d.YAxis),
                        1.0, scale_y, 1.0,
                    )
                    outline.Transform(xform_scale)

                    if abs(shift_y) > 0.001:
                        xform_move = rg.Transform.Translation(0, shift_y, 0)
                        outline.Transform(xform_move)

        # Ensure the outline is closed
        if not outline.IsClosed:
            outline.MakeClosed(tol)

        # Store outline in state
        state.insole_outline = outline

        # Calculate total thickness for extrusion
        total_thickness = (
            state.cover_thickness_mm
            + state.shell_thickness_mm
            + state.base_thickness_mm
        )

        # --- Create sole-conforming insole ---
        Rhino.RhinoApp.WriteLine(
            "Orthotic Toolkit: Creating sole-conforming insole..."
        )

        insole_brep = _create_conforming_insole(
            state.active_last_brep, outline, total_thickness
        )

        conforming = insole_brep is not None
        if not conforming:
            Rhino.RhinoApp.WriteLine(
                "Orthotic Toolkit: Conforming approach unavailable, "
                "using flat extrusion."
            )
            insole_brep = _create_flat_insole(outline, total_thickness)

        if insole_brep is None:
            Rhino.RhinoApp.WriteLine(
                "Orthotic Toolkit: Failed to create insole solid."
            )
            _show_panel_warning("Insole creation failed.")
            return rc.Result.Failure

        state.insole_brep = insole_brep

        # Also store the top surface for later use by thickness layers
        if conforming:
            state.insole_top_surface = insole_brep

        # Add outline to OT_Outline layer
        outline_layer = ensure_layer(OT_OUTLINE_LAYER)
        attrs = rd.ObjectAttributes()
        attrs.LayerIndex = outline_layer
        attrs.ColorSource = rd.ObjectColorSource.ColorFromLayer
        doc.Objects.AddCurve(outline, attrs)

        # Add insole Brep to OT_Insole layer
        insole_layer = ensure_layer(OT_INSOLE_LAYER)
        attrs2 = rd.ObjectAttributes()
        attrs2.LayerIndex = insole_layer
        attrs2.ColorSource = rd.ObjectColorSource.ColorFromLayer
        doc.Objects.AddBrep(insole_brep, attrs2)

        doc.Views.Redraw()

        method = "sole-conforming" if conforming else "flat"
        Rhino.RhinoApp.WriteLine(
            "Orthotic Toolkit: Insole outline generated ({}). "
            "Offset: {:.1f}mm, Toe ext: {:.1f}mm, Heel ext: {:.1f}mm. "
            "Thickness: {:.1f}mm.".format(
                method, perimeter_offset, toe_ext, heel_ext, total_thickness
            )
        )
        return rc.Result.Success
