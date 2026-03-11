# -*- coding: utf-8 -*-
"""Orthotic Toolkit - OT_AddPosting Command

Creates rearfoot and forefoot posting wedges and unions them into
the insole Brep. Skips any wedge whose angle is 0.
"""

import math
import System
import Rhino
import Rhino.Geometry as rg
import Rhino.Commands as rc
import Rhino.DocObjects as rd
import Rhino.UI as rui
import Eto.Forms as ef
import scriptcontext as sc

import state
from geometry import brep_utils


PANEL_GUID = System.Guid("B2C3D4E5-F6A7-8901-BCDE-F12345678901")
OT_INSOLE_LAYER = "OT_Insole"


def _get_panel_values():
    """Read posting parameters from the panel."""
    try:
        panels = rui.Panels.GetOpenPanelContents(PANEL_GUID)
        if panels is not None:
            for panel in panels:
                if hasattr(panel, "get_posting_params"):
                    return panel.get_posting_params()
    except Exception:
        pass
    return (
        state.rf_medial_deg,
        state.rf_lateral_deg,
        state.ff_medial_deg,
        state.ff_lateral_deg,
        state.split_pct,
    )


def _show_panel_warning(message):
    """Show an amber warning on the panel's Posting tab."""
    try:
        panels = rui.Panels.GetOpenPanelContents(PANEL_GUID)
        if panels is not None:
            for panel in panels:
                if hasattr(panel, "show_tab_warning"):
                    panel.show_tab_warning("Posting", message)
    except Exception:
        pass


def _update_insole_layer(doc, new_brep):
    """Replace the insole Brep on the OT_Insole layer."""
    layer_index = doc.Layers.FindByFullPath(OT_INSOLE_LAYER, -1)
    if layer_index >= 0:
        settings = rd.ObjectEnumeratorSettings()
        settings.LayerIndexFilter = layer_index
        settings.ObjectTypeFilter = rd.ObjectType.Brep
        for obj in doc.Objects.GetObjectList(settings):
            doc.Objects.Replace(obj.Id, new_brep)
            return
    if layer_index < 0:
        layer = rd.Layer()
        layer.Name = OT_INSOLE_LAYER
        layer.Color = System.Drawing.Color.FromArgb(180, 180, 180)
        layer_index = doc.Layers.Add(layer)
    attrs = rd.ObjectAttributes()
    attrs.LayerIndex = layer_index
    attrs.ColorSource = rd.ObjectColorSource.ColorFromLayer
    doc.Objects.AddBrep(new_brep, attrs)


def _create_wedge_from_region(outline, y_min, y_max, angle_deg, side, tol):
    """Create a wedge solid for a region of the insole.

    Args:
        outline: The insole outline curve.
        y_min, y_max: Y-axis bounds for this wedge region.
        angle_deg: Tilt angle in degrees.
        side: 'medial' (+X tilt) or 'lateral' (-X tilt).
        tol: Model tolerance.

    Returns:
        A Brep solid or None.
    """
    bbox = outline.GetBoundingBox(True)
    x_min = bbox.Min.X
    x_max = bbox.Max.X
    width = x_max - x_min
    center_x = (x_min + x_max) / 2.0

    # Height of the wedge at the tilt edge
    height = width * math.tan(math.radians(abs(angle_deg))) / 2.0
    if height < 0.01:
        return None

    # Build wedge corners: a trapezoidal cross-section
    # For medial posting: higher on medial (+X) side
    # For lateral posting: higher on lateral (-X) side
    if side == "medial":
        z_left = 0.0
        z_right = height
    else:
        z_left = height
        z_right = 0.0

    # Create the wedge as a set of 8 corner points (box with tilted top)
    pts = [
        rg.Point3d(x_min, y_min, 0),          # 0: bottom-left-front
        rg.Point3d(x_max, y_min, 0),          # 1: bottom-right-front
        rg.Point3d(x_max, y_max, 0),          # 2: bottom-right-back
        rg.Point3d(x_min, y_max, 0),          # 3: bottom-left-back
        rg.Point3d(x_min, y_min, z_left),     # 4: top-left-front
        rg.Point3d(x_max, y_min, z_right),    # 5: top-right-front
        rg.Point3d(x_max, y_max, z_right),    # 6: top-right-back
        rg.Point3d(x_min, y_max, z_left),     # 7: top-left-back
    ]

    # Create the box as 6 planar faces
    faces = [
        [pts[0], pts[1], pts[2], pts[3]],  # bottom
        [pts[4], pts[5], pts[6], pts[7]],  # top
        [pts[0], pts[1], pts[5], pts[4]],  # front
        [pts[2], pts[3], pts[7], pts[6]],  # back
        [pts[0], pts[3], pts[7], pts[4]],  # left
        [pts[1], pts[2], pts[6], pts[5]],  # right
    ]

    breps = []
    for face_pts in faces:
        srf = rg.NurbsSurface.CreateFromCorners(
            face_pts[0], face_pts[1], face_pts[2], face_pts[3]
        )
        if srf is not None:
            breps.append(srf.ToBrep())

    if len(breps) < 6:
        return None

    joined = rg.Brep.JoinBreps(breps, tol)
    if joined and len(joined) > 0:
        result = joined[0]
        if not result.IsSolid:
            capped = result.CapPlanarHoles(tol)
            if capped is not None:
                result = capped
        return result

    return None


class OT_AddPosting(rc.Command):
    """Add rearfoot and forefoot posting wedges to the insole."""

    def __init__(self):
        super().__init__()

    @property
    def EnglishName(self):
        return "OT_AddPosting"

    def RunCommand(self, doc, mode):
        if state.active_last_brep is None:
            ef.MessageBox.Show(
                "No shoe last selected. Please use Select Last first.",
                "Orthotic Toolkit - No Last",
                ef.MessageBoxButtons.OK,
                ef.MessageBoxType.Warning,
            )
            return rc.Result.Failure

        if state.insole_outline is None:
            ef.MessageBox.Show(
                "No insole outline generated. Please run Generate Outline first.",
                "Orthotic Toolkit - No Outline",
                ef.MessageBoxButtons.OK,
                ef.MessageBoxType.Warning,
            )
            return rc.Result.Failure

        if state.insole_brep is None:
            Rhino.RhinoApp.WriteLine(
                "Orthotic Toolkit: No insole Brep to modify."
            )
            return rc.Result.Failure

        # Read parameters
        rf_med, rf_lat, ff_med, ff_lat, split_pct = _get_panel_values()
        state.rf_medial_deg = rf_med
        state.rf_lateral_deg = rf_lat
        state.ff_medial_deg = ff_med
        state.ff_lateral_deg = ff_lat
        state.split_pct = split_pct

        tol = sc.doc.ModelAbsoluteTolerance

        bbox = state.insole_outline.GetBoundingBox(True)
        if not bbox.IsValid:
            Rhino.RhinoApp.WriteLine(
                "Orthotic Toolkit: Cannot compute outline bounding box."
            )
            return rc.Result.Failure

        y_range = bbox.Max.Y - bbox.Min.Y
        split_y = bbox.Min.Y + y_range * (split_pct / 100.0)

        # Rearfoot region: min_y to split_y
        # Forefoot region: split_y to max_y
        current_brep = state.insole_brep
        wedges_added = 0
        wedge_defs = []

        if abs(rf_med) > 0.01:
            wedge_defs.append(
                ("Rearfoot medial", bbox.Min.Y, split_y, rf_med, "medial")
            )
        if abs(rf_lat) > 0.01:
            wedge_defs.append(
                ("Rearfoot lateral", bbox.Min.Y, split_y, rf_lat, "lateral")
            )
        if abs(ff_med) > 0.01:
            wedge_defs.append(
                ("Forefoot medial", split_y, bbox.Max.Y, ff_med, "medial")
            )
        if abs(ff_lat) > 0.01:
            wedge_defs.append(
                ("Forefoot lateral", split_y, bbox.Max.Y, ff_lat, "lateral")
            )

        if len(wedge_defs) == 0:
            Rhino.RhinoApp.WriteLine(
                "Orthotic Toolkit: All posting angles are 0. No wedges to add."
            )
            return rc.Result.Success

        for name, y_min, y_max, angle, side in wedge_defs:
            wedge = _create_wedge_from_region(
                state.insole_outline, y_min, y_max, angle, side, tol
            )
            if wedge is None:
                Rhino.RhinoApp.WriteLine(
                    "Orthotic Toolkit: {} wedge creation failed.".format(name)
                )
                continue

            try:
                result = brep_utils.safe_boolean_union(
                    current_brep, wedge, tol
                )
            except Exception as ex:
                Rhino.RhinoApp.WriteLine(
                    "Orthotic Toolkit: {} boolean union exception -- {}".format(
                        name, ex
                    )
                )
                _show_panel_warning(
                    "Boolean union failed for {}: {}".format(name, ex)
                )
                continue

            if result is None:
                Rhino.RhinoApp.WriteLine(
                    "Orthotic Toolkit: {} boolean union failed.".format(name)
                )
                _show_panel_warning(
                    "Boolean union failed for {}. "
                    "Try adjusting angle.".format(name)
                )
                continue

            current_brep = result
            wedges_added += 1
            Rhino.RhinoApp.WriteLine(
                "Orthotic Toolkit: {} wedge added ({:.1f} deg).".format(
                    name, angle
                )
            )

        if wedges_added > 0:
            state.insole_brep = current_brep
            _update_insole_layer(doc, current_brep)
            doc.Views.Redraw()

        Rhino.RhinoApp.WriteLine(
            "Orthotic Toolkit: {} of {} posting wedge(s) applied.".format(
                wedges_added, len(wedge_defs)
            )
        )
        return rc.Result.Success if wedges_added > 0 else rc.Result.Failure
