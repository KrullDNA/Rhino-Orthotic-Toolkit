# -*- coding: utf-8 -*-
"""Orthotic Toolkit - OT_GenerateOutline Command

Generates the insole outline by offsetting the footprint curve,
then extrudes it into an initial flat insole Brep.
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


PANEL_GUID = System.Guid("B2C3D4E5-F6A7-8901-BCDE-F12345678901")
OT_OUTLINE_LAYER = "OT_Outline"
OT_INSOLE_LAYER = "OT_Insole"
OUTLINE_COLOR = System.Drawing.Color.FromArgb(0, 120, 215)    # Blue
INSOLE_COLOR = System.Drawing.Color.FromArgb(180, 180, 180)   # Gray


def _ensure_layer(name, color):
    """Create a layer if it does not exist; return its index."""
    layer_index = sc.doc.Layers.FindByFullPath(name, -1)
    if layer_index < 0:
        layer = rd.Layer()
        layer.Name = name
        layer.Color = color
        layer_index = sc.doc.Layers.Add(layer)
    return layer_index


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


class OT_GenerateOutline(rc.Command):
    """Generate the insole outline and initial flat Brep."""

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
                # Extend by moving endpoints in Y direction
                # For a closed curve, we use a non-uniform scale approach
                center = bbox.Center
                y_range = bbox.Max.Y - bbox.Min.Y
                if y_range > 0:
                    # Scale factor for Y axis
                    total_ext = toe_ext + heel_ext
                    scale_y = (y_range + total_ext) / y_range
                    # Shift center to account for asymmetric extension
                    shift_y = (toe_ext - heel_ext) / 2.0

                    xform_scale = rg.Transform.Scale(
                        rg.Plane(center, rg.Vector3d.XAxis, rg.Vector3d.YAxis),
                        1.0, scale_y, 1.0
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

        # Extrude outline downward to create the initial insole Brep
        extrude_vec = rg.Vector3d(0, 0, -total_thickness)
        srf = rg.Surface.CreateExtrusion(outline, extrude_vec)
        insole_brep = None
        if srf is not None:
            brep = srf.ToBrep()
            if brep is not None:
                insole_brep = brep.CapPlanarHoles(tol)
                if insole_brep is None:
                    insole_brep = brep

        if insole_brep is None:
            Rhino.RhinoApp.WriteLine(
                "Orthotic Toolkit: Failed to create insole solid."
            )
            _show_panel_warning("Insole extrusion failed.")
            return rc.Result.Failure

        state.insole_brep = insole_brep

        # Add outline to OT_Outline layer
        outline_layer = _ensure_layer(OT_OUTLINE_LAYER, OUTLINE_COLOR)
        attrs = rd.ObjectAttributes()
        attrs.LayerIndex = outline_layer
        attrs.ColorSource = rd.ObjectColorSource.ColorFromLayer
        doc.Objects.AddCurve(outline, attrs)

        # Add insole Brep to OT_Insole layer
        insole_layer = _ensure_layer(OT_INSOLE_LAYER, INSOLE_COLOR)
        attrs2 = rd.ObjectAttributes()
        attrs2.LayerIndex = insole_layer
        attrs2.ColorSource = rd.ObjectColorSource.ColorFromLayer
        doc.Objects.AddBrep(insole_brep, attrs2)

        doc.Views.Redraw()

        Rhino.RhinoApp.WriteLine(
            "Orthotic Toolkit: Insole outline generated. "
            "Offset: {:.1f}mm, Toe ext: {:.1f}mm, Heel ext: {:.1f}mm. "
            "Thickness: {:.1f}mm.".format(
                perimeter_offset, toe_ext, heel_ext, total_thickness
            )
        )
        return rc.Result.Success
