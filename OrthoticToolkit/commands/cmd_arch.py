# -*- coding: utf-8 -*-
"""Orthotic Toolkit - OT_AddArch Command

Creates medial arch support geometry and unions it into the insole Brep.
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
    """Read arch parameters from the panel."""
    try:
        panels = rui.Panels.GetOpenPanelContents(PANEL_GUID)
        if panels is not None:
            for panel in panels:
                if hasattr(panel, "get_arch_params"):
                    return panel.get_arch_params()
    except Exception:
        pass
    return (
        state.arch_height_mm,
        state.arch_apex_pct,
        state.arch_width_mm,
        state.arch_blend_radius,
    )


def _show_panel_warning(message):
    """Show an amber warning on the panel's Arch tab."""
    try:
        panels = rui.Panels.GetOpenPanelContents(PANEL_GUID)
        if panels is not None:
            for panel in panels:
                if hasattr(panel, "show_tab_warning"):
                    panel.show_tab_warning("Arch", message)
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
    # If no existing object, add a new one
    if layer_index < 0:
        layer = rd.Layer()
        layer.Name = OT_INSOLE_LAYER
        layer.Color = System.Drawing.Color.FromArgb(180, 180, 180)
        layer_index = doc.Layers.Add(layer)
    attrs = rd.ObjectAttributes()
    attrs.LayerIndex = layer_index
    attrs.ColorSource = rd.ObjectColorSource.ColorFromLayer
    doc.Objects.AddBrep(new_brep, attrs)


class OT_AddArch(rc.Command):
    """Add medial arch support to the insole."""

    def __init__(self):
        super().__init__()

    @property
    def EnglishName(self):
        return "OT_AddArch"

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
        arch_height, apex_pct, arch_width, blend_radius = _get_panel_values()
        state.arch_height_mm = arch_height
        state.arch_apex_pct = apex_pct
        state.arch_width_mm = arch_width
        state.arch_blend_radius = blend_radius

        tol = sc.doc.ModelAbsoluteTolerance

        # Determine arch placement from outline bounding box
        bbox = state.insole_outline.GetBoundingBox(True)
        if not bbox.IsValid:
            Rhino.RhinoApp.WriteLine(
                "Orthotic Toolkit: Cannot compute outline bounding box."
            )
            return rc.Result.Failure

        # The medial arch runs along the medial (inner) side of the insole
        # We place it on the +X side (right foot convention) at the midfoot
        x_center = bbox.Max.X - arch_width / 2.0
        y_length = bbox.Max.Y - bbox.Min.Y
        apex_y = bbox.Min.Y + y_length * (apex_pct / 100.0)

        # Create the arch profile as a parabolic curve along the medial side
        # Build control points for a raised arch shape
        n_pts = 7
        arch_pts = []
        for i in range(n_pts):
            t = i / (n_pts - 1.0)
            y = bbox.Min.Y + t * y_length
            # Parabolic height profile: peak at apex
            dy = (y - apex_y) / (y_length * 0.4)
            z = arch_height * max(0.0, 1.0 - dy * dy)
            arch_pts.append(rg.Point3d(x_center, y, z))

        profile = rg.Curve.CreateInterpolatedCurve(
            arch_pts, 3, rg.CurveKnotStyle.Chord
        )
        if profile is None:
            Rhino.RhinoApp.WriteLine(
                "Orthotic Toolkit: Failed to create arch profile curve."
            )
            _show_panel_warning("Arch profile creation failed.")
            return rc.Result.Failure

        # Create a cross-section circle perpendicular to the profile
        # at several points, then sweep to create arch solid
        cross_section = rg.Circle(
            rg.Plane(arch_pts[n_pts // 2], rg.Vector3d.YAxis),
            arch_width / 2.0,
        ).ToNurbsCurve()

        # Create the arch solid via sweep
        sweep = rg.Brep.CreateFromSweep(
            profile, cross_section, True, tol
        )
        arch_brep = None
        if sweep is not None and len(sweep) > 0:
            arch_brep = sweep[0]
            if not arch_brep.IsSolid:
                arch_brep = arch_brep.CapPlanarHoles(tol)
                if arch_brep is None:
                    arch_brep = sweep[0]

        if arch_brep is None:
            # Fallback: create a simple extruded ellipse at the arch location
            arch_plane = rg.Plane(
                rg.Point3d(x_center, apex_y, 0),
                rg.Vector3d.ZAxis,
            )
            ellipse = rg.Ellipse(arch_plane, arch_width / 2.0, y_length * 0.3)
            ellipse_curve = ellipse.ToNurbsCurve()
            extrude_vec = rg.Vector3d(0, 0, arch_height)
            srf = rg.Surface.CreateExtrusion(ellipse_curve, extrude_vec)
            if srf is not None:
                arch_brep = srf.ToBrep()
                if arch_brep is not None:
                    capped = arch_brep.CapPlanarHoles(tol)
                    if capped is not None:
                        arch_brep = capped

        if arch_brep is None:
            Rhino.RhinoApp.WriteLine(
                "Orthotic Toolkit: Failed to create arch geometry."
            )
            _show_panel_warning("Arch geometry creation failed.")
            return rc.Result.Failure

        # Boolean union with insole
        try:
            result = brep_utils.safe_boolean_union(
                state.insole_brep, arch_brep, tol
            )
        except Exception as ex:
            Rhino.RhinoApp.WriteLine(
                "Orthotic Toolkit: Arch boolean union exception -- {}".format(ex)
            )
            _show_panel_warning(
                "Boolean union failed: {}".format(ex)
            )
            return rc.Result.Failure

        if result is None:
            Rhino.RhinoApp.WriteLine(
                "Orthotic Toolkit: Arch boolean union failed. "
                "Insole Brep unchanged."
            )
            _show_panel_warning(
                "Boolean union failed. Try adjusting arch parameters."
            )
            return rc.Result.Failure

        state.insole_brep = result
        _update_insole_layer(doc, result)
        doc.Views.Redraw()

        Rhino.RhinoApp.WriteLine(
            "Orthotic Toolkit: Arch added. Height: {:.1f}mm, "
            "Apex: {:.0f}%, Width: {:.1f}mm.".format(
                arch_height, apex_pct, arch_width
            )
        )
        return rc.Result.Success
