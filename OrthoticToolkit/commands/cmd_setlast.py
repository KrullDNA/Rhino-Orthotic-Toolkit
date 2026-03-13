# -*- coding: utf-8 -*-
"""Orthotic Toolkit - OT_SetLast Command

Prompts the user to select a shoe last polysurface, detects the sole face,
projects the footprint to the XY plane, creates the inverse sole surface,
and stores all results in plugin state.
"""

import System
import Rhino
import Rhino.Geometry as rg
import Rhino.Input as ri
import Rhino.Commands as rc
import Rhino.DocObjects as rd
import Rhino.UI as rui
import Eto.Forms as ef
import scriptcontext as sc

import state
from geometry import surface_utils
from geometry.layer_utils import ensure_layer


PANEL_GUID = System.Guid("B2C3D4E5-F6A7-8901-BCDE-F12345678901")
OT_PREVIEW_LAYER = "OT_Preview"


def _find_sole_face(brep):
    """Find the face whose average normal points most strongly in -Z.

    Returns the BrepFace if the best dot product with (0,0,-1) exceeds 0.6,
    otherwise returns None.
    """
    down = rg.Vector3d(0, 0, -1)
    best_face = None
    best_dot = -1.0

    for i in range(brep.Faces.Count):
        face = brep.Faces[i]
        u_domain = face.Domain(0)
        v_domain = face.Domain(1)
        u_mid = u_domain.Mid
        v_mid = v_domain.Mid

        success, frame = face.FrameAt(u_mid, v_mid)
        if not success:
            continue

        normal = frame.ZAxis
        if face.OrientationIsReversed:
            normal = -normal

        dot = normal * down
        if dot > best_dot:
            best_dot = dot
            best_face = face

    if best_dot > 0.6:
        return best_face
    return None


def _get_footprint_by_section(brep):
    """Get the footprint by taking horizontal cross-sections at many heights.

    Sub-D lasts have curved soles, so a single low section only captures
    a small area (e.g. the heel).  This function takes sections at many
    heights from the bottom of the bounding box, projects them all to
    the XY plane, and combines them via boolean union to produce the
    full sole outline.
    """
    tol = sc.doc.ModelAbsoluteTolerance
    bbox = brep.GetBoundingBox(True)
    if not bbox.IsValid:
        return None

    z_range = bbox.Max.Z - bbox.Min.Z
    if z_range < tol:
        return None

    # Take sections at many heights in the lower half of the last
    section_pcts = [0.02, 0.05, 0.08, 0.10, 0.13, 0.15, 0.18, 0.20,
                    0.25, 0.30, 0.35, 0.40, 0.45, 0.50]

    xy_plane = rg.Plane.WorldXY
    all_closed = []

    for pct in section_pcts:
        section_z = bbox.Min.Z + z_range * pct
        section_plane = rg.Plane(
            rg.Point3d(0, 0, section_z), rg.Vector3d.ZAxis
        )
        section_curves = rg.Brep.CreateContourCurves(brep, section_plane)
        if section_curves is None or len(section_curves) == 0:
            continue

        # Join fragments from this section
        joined = rg.Curve.JoinCurves(section_curves, tol * 10)
        if joined is None or len(joined) == 0:
            joined = section_curves

        for crv in joined:
            if not crv.IsClosed:
                if crv.IsClosable(tol * 100):
                    crv.MakeClosed(tol * 100)
                else:
                    continue

            # Project this closed curve down to Z=0
            flat = rg.Curve.ProjectToPlane(crv, xy_plane)
            if flat is not None and flat.IsClosed:
                all_closed.append(flat)

    if len(all_closed) == 0:
        return None

    # If only one curve, return it directly
    if len(all_closed) == 1:
        return all_closed[0]

    # Boolean-union all projected curves to get the outer envelope
    try:
        union = rg.Curve.CreateBooleanUnion(all_closed, tol)
        if union is not None and len(union) > 0:
            # Pick the largest curve from the union result
            best = None
            best_area = 0.0
            for crv in union:
                if crv.IsClosed:
                    bb = crv.GetBoundingBox(True)
                    area = (bb.Max.X - bb.Min.X) * (bb.Max.Y - bb.Min.Y)
                    if area > best_area:
                        best_area = area
                        best = crv
            if best is not None:
                return best
    except Exception:
        pass

    # Fallback: if boolean union fails, return the largest individual curve
    best = None
    best_area = 0.0
    for crv in all_closed:
        bb = crv.GetBoundingBox(True)
        area = (bb.Max.X - bb.Min.X) * (bb.Max.Y - bb.Min.Y)
        if area > best_area:
            best_area = area
            best = crv
    return best


def _get_face_boundary(face):
    """Get the outer boundary curve of a BrepFace.

    Returns a joined curve representing the outer loop, or None.
    """
    loop = face.OuterLoop
    if loop is None:
        return None

    trims = loop.Trims
    curves = []
    for i in range(trims.Count):
        trim = trims[i]
        edge = trim.Edge
        if edge is not None:
            curve = edge.DuplicateCurve()
            if curve is not None:
                curves.append(curve)

    if len(curves) == 0:
        return None

    tol = sc.doc.ModelAbsoluteTolerance
    joined = rg.Curve.JoinCurves(curves, tol)
    if joined is not None and len(joined) > 0:
        return joined[0]
    return None


def _refresh_panel(last_name, error=False):
    """Update the panel status bar with the last name or error."""
    try:
        panels = rui.Panels.GetOpenPanelContents(PANEL_GUID)
        if panels is not None:
            for panel in panels:
                if error and hasattr(panel, "show_last_error"):
                    panel.show_last_error()
                elif hasattr(panel, "update_last_label"):
                    panel.update_last_label(last_name)
    except Exception:
        pass


class OT_SetLast(rc.Command):
    """Select a shoe last and set up the sole surface for insole design."""

    def __init__(self):
        super().__init__()

    @property
    def EnglishName(self):
        return "OT_SetLast"

    def RunCommand(self, doc, mode):
        # Prompt user to select a Brep polysurface
        go = ri.Custom.GetObject()
        go.SetCommandPrompt("Select shoe last polysurface")
        go.GeometryFilter = rd.ObjectType.Brep
        go.SubObjectSelect = False
        go.Get()

        if go.CommandResult() != rc.Result.Success:
            return go.CommandResult()

        obj_ref = go.Object(0)
        brep = obj_ref.Brep()
        if brep is None:
            Rhino.RhinoApp.WriteLine(
                "Orthotic Toolkit: Selected object is not a valid Brep."
            )
            _refresh_panel(None, error=True)
            return rc.Result.Failure

        rhino_obj = obj_ref.Object()
        last_name = rhino_obj.Name if rhino_obj.Name else rhino_obj.Id.ToString()[:8]

        # Get footprint using horizontal cross-section (robust for Sub-D lasts)
        footprint = _get_footprint_by_section(brep)

        if footprint is None:
            # Fallback: try single sole face approach for simple lasts
            sole_face = _find_sole_face(brep)
            if sole_face is not None:
                boundary = _get_face_boundary(sole_face)
                if boundary is not None:
                    xy_plane = rg.Plane.WorldXY
                    projected = surface_utils.project_curve_to_plane(
                        boundary, xy_plane
                    )
                    if projected is not None and len(projected) > 0:
                        footprint = projected[0]

        if footprint is None:
            ef.MessageBox.Show(
                "Could not extract footprint from the shoe last. Please "
                "ensure the last is oriented with the sole facing downward "
                "(-Z direction).",
                "Orthotic Toolkit - Footprint Extraction Failed",
                ef.MessageBoxButtons.OK,
                ef.MessageBoxType.Warning,
            )
            Rhino.RhinoApp.WriteLine(
                "Orthotic Toolkit: Footprint extraction failed. "
                "Ensure the last is oriented sole-down (-Z)."
            )
            _refresh_panel(None, error=True)
            return rc.Result.Failure

        # Project footprint to XY plane (flatten Z to 0)
        xy_plane = rg.Plane.WorldXY
        projected = surface_utils.project_curve_to_plane(footprint, xy_plane)
        if projected is not None and len(projected) > 0:
            footprint = projected[0]

        # Remove previous preview objects
        for obj_id in state.preview_object_ids:
            try:
                doc.Objects.Delete(obj_id, True)
            except Exception:
                pass

        # Store results in state
        state.active_last_brep = brep
        state.sole_face = _find_sole_face(brep)
        state.footprint_curve = footprint
        state.insole_top_surface = None
        state.active_last_name = last_name
        state.preview_object_ids = []

        # Add green footprint preview to OT_Preview layer
        layer_index = ensure_layer(OT_PREVIEW_LAYER)

        attrs = rd.ObjectAttributes()
        attrs.LayerIndex = layer_index
        attrs.ColorSource = rd.ObjectColorSource.ColorFromLayer

        guid = doc.Objects.AddCurve(footprint, attrs)
        if guid != System.Guid.Empty:
            state.preview_object_ids.append(guid)

        # Redraw
        doc.Views.Redraw()

        # Update panel
        _refresh_panel(last_name)

        Rhino.RhinoApp.WriteLine(
            "Orthotic Toolkit: Shoe last '{}' selected. "
            "Footprint curve projected to XY plane. "
            "Ready for Generate Outline.".format(last_name)
        )
        return rc.Result.Success
