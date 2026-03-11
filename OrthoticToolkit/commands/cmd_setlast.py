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
        # Sample the face center normal
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

        dot = normal * down  # dot product
        if dot > best_dot:
            best_dot = dot
            best_face = face

    if best_dot > 0.6:
        return best_face
    return None


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

        # Detect the sole face
        sole_face = _find_sole_face(brep)
        if sole_face is None:
            ef.MessageBox.Show(
                "Could not detect sole face automatically. Please ensure "
                "the last is oriented with the sole facing downward "
                "(-Z direction).",
                "Orthotic Toolkit - Sole Detection Failed",
                ef.MessageBoxButtons.OK,
                ef.MessageBoxType.Warning,
            )
            Rhino.RhinoApp.WriteLine(
                "Orthotic Toolkit: Sole face detection failed. "
                "Ensure the last is oriented sole-down (-Z)."
            )
            _refresh_panel(None, error=True)
            return rc.Result.Failure

        # Get the sole face boundary curve
        boundary = _get_face_boundary(sole_face)
        if boundary is None:
            Rhino.RhinoApp.WriteLine(
                "Orthotic Toolkit: Could not extract sole face boundary."
            )
            _refresh_panel(None, error=True)
            return rc.Result.Failure

        # Project boundary to world XY plane
        xy_plane = rg.Plane.WorldXY
        projected = surface_utils.project_curve_to_plane(boundary, xy_plane)
        if len(projected) == 0:
            Rhino.RhinoApp.WriteLine(
                "Orthotic Toolkit: Failed to project sole boundary to XY plane."
            )
            _refresh_panel(None, error=True)
            return rc.Result.Failure
        footprint = projected[0]

        # Create inverse sole surface
        inverse_sole = surface_utils.create_inverse_sole_surface(
            sole_face, state.cover_thickness_mm
        )
        if inverse_sole is None:
            Rhino.RhinoApp.WriteLine(
                "Orthotic Toolkit: Failed to create inverse sole surface."
            )
            _refresh_panel(None, error=True)
            return rc.Result.Failure

        # Remove previous preview objects
        for obj_id in state.preview_object_ids:
            try:
                doc.Objects.Delete(obj_id, True)
            except Exception:
                pass

        # Store results in state
        state.active_last_brep = brep
        state.sole_face = sole_face
        state.footprint_curve = footprint
        state.insole_top_surface = inverse_sole
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
            "Sole face detected, footprint curve projected to XY plane, "
            "inverse sole surface created.".format(last_name)
        )
        return rc.Result.Success
