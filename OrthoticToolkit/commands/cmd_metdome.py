# -*- coding: utf-8 -*-
"""Orthotic Toolkit - OT_AddMetDome Command

Creates metatarsal dome pads in the forefoot region and unions
them into the insole Brep.
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
from geometry import brep_utils


PANEL_GUID = System.Guid("B2C3D4E5-F6A7-8901-BCDE-F12345678901")
OT_INSOLE_LAYER = "OT_Insole"

# Default dome parameters when not specified
DEFAULT_DOME_HEIGHT = 5.0
DEFAULT_DOME_DIAMETER = 10.0


def _get_panel_values():
    """Read metatarsal dome parameters from the panel."""
    try:
        panels = rui.Panels.GetOpenPanelContents(PANEL_GUID)
        if panels is not None:
            for panel in panels:
                if hasattr(panel, "get_metdome_params"):
                    return panel.get_metdome_params()
    except Exception:
        pass
    return state.dome_count, state.dome_positions


def _show_panel_warning(message):
    """Show an amber warning on the panel's Forefoot tab."""
    try:
        panels = rui.Panels.GetOpenPanelContents(PANEL_GUID)
        if panels is not None:
            for panel in panels:
                if hasattr(panel, "show_tab_warning"):
                    panel.show_tab_warning("Forefoot", message)
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


class OT_AddMetDome(rc.Command):
    """Add metatarsal dome pads to the forefoot region."""

    def __init__(self):
        super().__init__()

    @property
    def EnglishName(self):
        return "OT_AddMetDome"

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
        dome_count, dome_positions = _get_panel_values()
        state.dome_count = dome_count

        tol = sc.doc.ModelAbsoluteTolerance

        bbox = state.insole_outline.GetBoundingBox(True)
        if not bbox.IsValid:
            Rhino.RhinoApp.WriteLine(
                "Orthotic Toolkit: Cannot compute outline bounding box."
            )
            return rc.Result.Failure

        x_range = bbox.Max.X - bbox.Min.X
        y_range = bbox.Max.Y - bbox.Min.Y

        # Generate dome positions if not explicitly set
        if dome_positions is None or len(dome_positions) < dome_count:
            dome_positions = []
            # Forefoot region is the top ~30% of the insole (max Y region)
            forefoot_y_start = bbox.Min.Y + y_range * 0.65
            forefoot_y_end = bbox.Min.Y + y_range * 0.85

            for i in range(dome_count):
                if dome_count == 1:
                    x_pct = 50.0
                else:
                    # Space domes evenly across the forefoot width
                    x_pct = 25.0 + (50.0 * i / (dome_count - 1))
                y_pct = 75.0  # Center of forefoot region
                dome_positions.append(
                    (x_pct, y_pct, DEFAULT_DOME_HEIGHT, DEFAULT_DOME_DIAMETER)
                )

        state.dome_positions = dome_positions

        current_brep = state.insole_brep
        domes_added = 0

        for idx, (x_pct, y_pct, height_mm, diameter_mm) in enumerate(dome_positions):
            if idx >= dome_count:
                break

            # Convert percentages to absolute positions
            dome_x = bbox.Min.X + x_range * (x_pct / 100.0)
            dome_y = bbox.Min.Y + y_range * (y_pct / 100.0)
            radius = diameter_mm / 2.0

            # Create a hemisphere (half-sphere) for the dome
            sphere = rg.Sphere(rg.Point3d(dome_x, dome_y, 0), radius)
            sphere_brep = rg.Brep.CreateFromSphere(sphere)

            if sphere_brep is None:
                Rhino.RhinoApp.WriteLine(
                    "Orthotic Toolkit: Failed to create dome {} geometry.".format(
                        idx + 1
                    )
                )
                continue

            # Cut the sphere in half at Z=0 to get a hemisphere
            cut_plane = rg.Plane.WorldXY
            pieces = sphere_brep.Trim(cut_plane, tol)
            dome_brep = None
            if pieces is not None and len(pieces) > 0:
                # Take the piece above Z=0
                for piece in pieces:
                    piece_bbox = piece.GetBoundingBox(True)
                    if piece_bbox.Max.Z > 0:
                        capped = piece.CapPlanarHoles(tol)
                        dome_brep = capped if capped is not None else piece
                        break

            if dome_brep is None:
                # Fallback: use a scaled cylinder
                circle = rg.Circle(
                    rg.Plane(rg.Point3d(dome_x, dome_y, 0), rg.Vector3d.ZAxis),
                    radius,
                )
                cylinder = rg.Cylinder(circle, height_mm)
                dome_brep = rg.Brep.CreateFromCylinder(cylinder, True, True)

            if dome_brep is None:
                continue

            # Boolean union
            try:
                result = brep_utils.safe_boolean_union(
                    current_brep, dome_brep, tol
                )
            except Exception as ex:
                Rhino.RhinoApp.WriteLine(
                    "Orthotic Toolkit: Dome {} boolean union exception -- {}".format(
                        idx + 1, ex
                    )
                )
                _show_panel_warning(
                    "Boolean union failed for dome {}: {}".format(idx + 1, ex)
                )
                continue

            if result is None:
                Rhino.RhinoApp.WriteLine(
                    "Orthotic Toolkit: Dome {} boolean union failed.".format(
                        idx + 1
                    )
                )
                _show_panel_warning(
                    "Boolean union failed for dome {}. "
                    "Try adjusting position.".format(idx + 1)
                )
                continue

            current_brep = result
            domes_added += 1

        if domes_added > 0:
            state.insole_brep = current_brep
            _update_insole_layer(doc, current_brep)
            doc.Views.Redraw()

        Rhino.RhinoApp.WriteLine(
            "Orthotic Toolkit: {} of {} metatarsal dome(s) added.".format(
                domes_added, dome_count
            )
        )
        return rc.Result.Success if domes_added > 0 else rc.Result.Failure
