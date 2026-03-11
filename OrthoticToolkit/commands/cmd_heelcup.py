# -*- coding: utf-8 -*-
"""Orthotic Toolkit - OT_AddHeelCup Command

Creates heel cup geometry and unions it into the insole Brep.
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
    """Read heel cup parameters from the panel."""
    try:
        panels = rui.Panels.GetOpenPanelContents(PANEL_GUID)
        if panels is not None:
            for panel in panels:
                if hasattr(panel, "get_heelcup_params"):
                    return panel.get_heelcup_params()
    except Exception:
        pass
    return (
        state.cup_depth_mm,
        state.posterior_angle_deg,
        state.lateral_flare_deg,
        state.medial_flare_deg,
        state.cup_width_pct,
    )


def _show_panel_warning(message):
    """Show an amber warning on the panel's Heel Cup tab."""
    try:
        panels = rui.Panels.GetOpenPanelContents(PANEL_GUID)
        if panels is not None:
            for panel in panels:
                if hasattr(panel, "show_tab_warning"):
                    panel.show_tab_warning("Heel Cup", message)
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


class OT_AddHeelCup(rc.Command):
    """Add a heel cup to the insole."""

    def __init__(self):
        super().__init__()

    @property
    def EnglishName(self):
        return "OT_AddHeelCup"

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
        cup_depth, posterior_angle, lateral_flare, medial_flare, cup_width_pct = (
            _get_panel_values()
        )
        state.cup_depth_mm = cup_depth
        state.posterior_angle_deg = posterior_angle
        state.lateral_flare_deg = lateral_flare
        state.medial_flare_deg = medial_flare
        state.cup_width_pct = cup_width_pct

        tol = sc.doc.ModelAbsoluteTolerance

        # Determine heel cup placement from outline bounding box
        bbox = state.insole_outline.GetBoundingBox(True)
        if not bbox.IsValid:
            Rhino.RhinoApp.WriteLine(
                "Orthotic Toolkit: Cannot compute outline bounding box."
            )
            return rc.Result.Failure

        # Heel is at the min Y end of the outline
        heel_center_x = (bbox.Min.X + bbox.Max.X) / 2.0
        heel_center_y = bbox.Min.Y
        heel_width = (bbox.Max.X - bbox.Min.X) * (cup_width_pct / 100.0)
        heel_length = (bbox.Max.Y - bbox.Min.Y) * 0.3  # Heel is ~30% of length

        # Build the heel cup as a U-shaped trough
        # Create a cross-section profile (U-shape) and sweep along heel region
        n_profile = 9
        profile_pts = []
        for i in range(n_profile):
            t = i / (n_profile - 1.0)
            x = heel_center_x - heel_width / 2.0 + t * heel_width

            # U-shape: walls on sides, flat at bottom
            wall_t = min(t, 1.0 - t) * 2.0  # 0 at edges, 1 at center
            if wall_t < 0.3:
                # Wall region -- rises with flare angle
                flare_angle = lateral_flare if t < 0.5 else medial_flare
                wall_height = cup_depth * (1.0 - wall_t / 0.3)
                # Apply flare by shifting outward at top
                flare_shift = wall_height * math.tan(math.radians(flare_angle))
                if t < 0.5:
                    x -= flare_shift
                else:
                    x += flare_shift
                z = wall_height
            else:
                z = 0.0

            profile_pts.append(rg.Point3d(x, heel_center_y, z))

        profile_curve = rg.Curve.CreateInterpolatedCurve(
            profile_pts, 3, rg.CurveKnotStyle.Chord
        )
        if profile_curve is None:
            Rhino.RhinoApp.WriteLine(
                "Orthotic Toolkit: Failed to create heel cup profile."
            )
            _show_panel_warning("Heel cup profile creation failed.")
            return rc.Result.Failure

        # Create posterior wall by extruding the profile along Y
        # Apply posterior angle to tilt the back wall
        posterior_rad = math.radians(posterior_angle)
        extrude_y = heel_length
        extrude_z = extrude_y * math.cos(posterior_rad) if posterior_angle != 90 else 0
        extrude_vec = rg.Vector3d(0, extrude_y, -extrude_z)

        srf = rg.Surface.CreateExtrusion(profile_curve, extrude_vec)
        cup_brep = None
        if srf is not None:
            cup_brep = srf.ToBrep()
            if cup_brep is not None:
                capped = cup_brep.CapPlanarHoles(tol)
                if capped is not None:
                    cup_brep = capped

        if cup_brep is None:
            Rhino.RhinoApp.WriteLine(
                "Orthotic Toolkit: Failed to create heel cup solid."
            )
            _show_panel_warning("Heel cup solid creation failed.")
            return rc.Result.Failure

        # Boolean union with insole
        try:
            result = brep_utils.safe_boolean_union(
                state.insole_brep, cup_brep, tol
            )
        except Exception as ex:
            Rhino.RhinoApp.WriteLine(
                "Orthotic Toolkit: Heel cup boolean union exception -- {}".format(ex)
            )
            _show_panel_warning("Boolean union failed: {}".format(ex))
            return rc.Result.Failure

        if result is None:
            Rhino.RhinoApp.WriteLine(
                "Orthotic Toolkit: Heel cup boolean union failed. "
                "Insole Brep unchanged."
            )
            _show_panel_warning(
                "Boolean union failed. Try adjusting heel cup parameters."
            )
            return rc.Result.Failure

        state.insole_brep = result
        _update_insole_layer(doc, result)
        doc.Views.Redraw()

        Rhino.RhinoApp.WriteLine(
            "Orthotic Toolkit: Heel cup added. Depth: {:.1f}mm, "
            "Posterior: {:.0f}deg, Lateral flare: {:.0f}deg, "
            "Medial flare: {:.0f}deg.".format(
                cup_depth, posterior_angle, lateral_flare, medial_flare
            )
        )
        return rc.Result.Success
