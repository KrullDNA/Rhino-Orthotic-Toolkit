# -*- coding: utf-8 -*-
"""Orthotic Toolkit - OT_SetThickness Command

Splits the insole Brep into three thickness layers (cover, shell, base),
performs a minimum thickness check, and updates the insole on OT_Insole.
"""

import random
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
OT_WARNINGS_LAYER = "OT_Warnings"
WARNINGS_COLOR = System.Drawing.Color.FromArgb(220, 0, 0)
INSOLE_COLOR = System.Drawing.Color.FromArgb(180, 180, 180)
MIN_THICKNESS_MM = 2.0


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
    """Read thickness parameters from the panel."""
    try:
        panels = rui.Panels.GetOpenPanelContents(PANEL_GUID)
        if panels is not None:
            for panel in panels:
                if hasattr(panel, "get_thickness_params"):
                    return panel.get_thickness_params()
    except Exception:
        pass
    return state.cover_thickness_mm, state.shell_thickness_mm, state.base_thickness_mm


def _update_panel_total(total):
    """Update the total thickness label on the panel."""
    try:
        panels = rui.Panels.GetOpenPanelContents(PANEL_GUID)
        if panels is not None:
            for panel in panels:
                if hasattr(panel, "update_total_thickness"):
                    panel.update_total_thickness(total)
    except Exception:
        pass


def _show_panel_warning(message):
    """Show an amber warning on the panel's Thickness tab."""
    try:
        panels = rui.Panels.GetOpenPanelContents(PANEL_GUID)
        if panels is not None:
            for panel in panels:
                if hasattr(panel, "show_tab_warning"):
                    panel.show_tab_warning("Thickness", message)
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
    layer_index = _ensure_layer(OT_INSOLE_LAYER, INSOLE_COLOR)
    attrs = rd.ObjectAttributes()
    attrs.LayerIndex = layer_index
    attrs.ColorSource = rd.ObjectColorSource.ColorFromLayer
    doc.Objects.AddBrep(new_brep, attrs)


def _classify_region(x, y, bbox):
    """Classify a point as heel, arch, or forefoot based on Y position."""
    y_range = bbox.Max.Y - bbox.Min.Y
    y_pct = (y - bbox.Min.Y) / y_range if y_range > 0 else 0.5
    if y_pct < 0.35:
        return "heel"
    elif y_pct < 0.65:
        return "arch"
    else:
        return "forefoot"


def check_minimum_thickness(brep, n_samples=200, threshold=MIN_THICKNESS_MM):
    """Sample the brep and return thin points with their regions.

    Returns:
        (min_thickness, thin_points) where thin_points is a list of
        (Point3d, region_name, thickness) tuples.
    """
    if brep is None:
        return 0.0, []

    bbox = brep.GetBoundingBox(True)
    if not bbox.IsValid:
        return 0.0, []

    thin_points = []
    min_thick = float("inf")

    # Sample random points on the top face and measure to bottom
    for _ in range(n_samples):
        x = bbox.Min.X + random.random() * (bbox.Max.X - bbox.Min.X)
        y = bbox.Min.Y + random.random() * (bbox.Max.Y - bbox.Min.Y)

        # Cast ray downward from above the brep
        ray_start = rg.Point3d(x, y, bbox.Max.Z + 1.0)
        ray = rg.Ray3d(ray_start, rg.Vector3d(0, 0, -1))

        intersections = rg.Intersect.Intersection.RayShoot(
            ray, [brep], 1
        )

        if intersections is not None and len(intersections) >= 2:
            # First hit is top, second is bottom
            top_t = intersections[0]
            bot_t = intersections[1]
            top_pt = ray.PointAt(top_t)
            bot_pt = ray.PointAt(bot_t)
            thickness = top_pt.Z - bot_pt.Z

            if thickness < min_thick:
                min_thick = thickness

            if thickness < threshold:
                region = _classify_region(x, y, bbox)
                thin_points.append((top_pt, region, thickness))
        elif intersections is not None and len(intersections) == 1:
            # Only one intersection -- likely very thin or edge
            min_thick = min(min_thick, 0.1)
            region = _classify_region(x, y, bbox)
            thin_points.append((
                ray.PointAt(intersections[0]), region, 0.1
            ))

    if min_thick == float("inf"):
        min_thick = 0.0

    return min_thick, thin_points


class OT_SetThickness(rc.Command):
    """Set the insole layer thicknesses and build layered Breps."""

    def __init__(self):
        super().__init__()

    @property
    def EnglishName(self):
        return "OT_SetThickness"

    def RunCommand(self, doc, mode):
        if state.active_last_brep is None:
            ef.MessageBox.Show(
                "No shoe last selected. Please use Select Last first.",
                "Orthotic Toolkit - No Last",
                ef.MessageBoxButtons.OK,
                ef.MessageBoxType.Warning,
            )
            return rc.Result.Failure

        if state.insole_brep is None:
            ef.MessageBox.Show(
                "No insole Brep to modify. Please run Generate Outline first.",
                "Orthotic Toolkit - No Insole",
                ef.MessageBoxButtons.OK,
                ef.MessageBoxType.Warning,
            )
            return rc.Result.Failure

        # Read parameters
        cover_mm, shell_mm, base_mm = _get_panel_values()
        state.cover_thickness_mm = cover_mm
        state.shell_thickness_mm = shell_mm
        state.base_thickness_mm = base_mm

        total = cover_mm + shell_mm + base_mm
        tol = sc.doc.ModelAbsoluteTolerance

        Rhino.RhinoApp.WriteLine(
            "Orthotic Toolkit: Building layers -- "
            "Cover: {:.1f}mm, Shell: {:.1f}mm, Base: {:.1f}mm, "
            "Total: {:.1f}mm".format(cover_mm, shell_mm, base_mm, total)
        )

        # Get the top surface of the insole brep (highest Z face)
        insole = state.insole_brep
        bbox = insole.GetBoundingBox(True)

        if not bbox.IsValid:
            Rhino.RhinoApp.WriteLine(
                "Orthotic Toolkit: Insole bounding box invalid."
            )
            return rc.Result.Failure

        # Build layer Breps by offsetting the insole outline at different
        # Z levels and creating capped extrusions for each layer
        outline = state.insole_outline
        if outline is None:
            Rhino.RhinoApp.WriteLine(
                "Orthotic Toolkit: No insole outline. "
                "Run Generate Outline first."
            )
            return rc.Result.Failure

        z_top = bbox.Max.Z
        z_cover_bot = z_top - cover_mm
        z_shell_bot = z_cover_bot - shell_mm
        z_base_bot = z_shell_bot - base_mm

        # Create each layer as an extruded solid from the outline
        layers_built = 0

        # Cover layer
        try:
            cover_brep = self._extrude_layer(
                outline, z_top, z_cover_bot, tol
            )
            if cover_brep is not None:
                state.layer_cover = cover_brep
                layers_built += 1
        except Exception as ex:
            Rhino.RhinoApp.WriteLine(
                "Orthotic Toolkit: Cover layer failed -- {}".format(ex)
            )
            _show_panel_warning("Cover layer creation failed.")

        # Shell layer
        try:
            shell_brep = self._extrude_layer(
                outline, z_cover_bot, z_shell_bot, tol
            )
            if shell_brep is not None:
                state.layer_shell = shell_brep
                layers_built += 1
        except Exception as ex:
            Rhino.RhinoApp.WriteLine(
                "Orthotic Toolkit: Shell layer failed -- {}".format(ex)
            )
            _show_panel_warning("Shell layer creation failed.")

        # Base layer
        try:
            base_brep = self._extrude_layer(
                outline, z_shell_bot, z_base_bot, tol
            )
            if base_brep is not None:
                state.layer_base = base_brep
                layers_built += 1
        except Exception as ex:
            Rhino.RhinoApp.WriteLine(
                "Orthotic Toolkit: Base layer failed -- {}".format(ex)
            )
            _show_panel_warning("Base layer creation failed.")

        if layers_built == 0:
            Rhino.RhinoApp.WriteLine(
                "Orthotic Toolkit: Failed to build any thickness layers."
            )
            _show_panel_warning("All layer builds failed.")
            return rc.Result.Failure

        # Join all layer Breps into a single full insole solid
        layer_breps = [
            b for b in [state.layer_cover, state.layer_shell, state.layer_base]
            if b is not None
        ]

        if len(layer_breps) > 1:
            try:
                result = brep_utils.safe_boolean_union(
                    layer_breps[0], layer_breps[1], tol
                )
                if result is not None and len(layer_breps) > 2:
                    result = brep_utils.safe_boolean_union(
                        result, layer_breps[2], tol
                    )
                if result is not None:
                    state.insole_brep = result
            except Exception as ex:
                Rhino.RhinoApp.WriteLine(
                    "Orthotic Toolkit: Layer union exception -- {}".format(ex)
                )
                _show_panel_warning(
                    "Layer union failed: {}".format(ex)
                )
        elif len(layer_breps) == 1:
            state.insole_brep = layer_breps[0]

        # Update the insole on the OT_Insole layer
        _update_insole_layer(doc, state.insole_brep)

        # Minimum thickness check
        min_thick, thin_points = check_minimum_thickness(
            state.insole_brep, 200, MIN_THICKNESS_MM
        )

        if thin_points:
            # Collect which regions are thin
            thin_regions = set()
            for _, region, _ in thin_points:
                thin_regions.add(region)

            region_list = ", ".join(sorted(thin_regions))
            msg = (
                "Minimum thickness warning!\n\n"
                "Thinnest point: {:.1f}mm (threshold: {:.1f}mm)\n"
                "Thin regions: {}\n\n"
                "Proceed anyway?".format(min_thick, MIN_THICKNESS_MM, region_list)
            )

            result = ef.MessageBox.Show(
                msg,
                "Orthotic Toolkit - Thickness Warning",
                ef.MessageBoxButtons.YesNo,
                ef.MessageBoxType.Warning,
            )

            # Add red point cloud on OT_Warnings layer
            warn_layer = _ensure_layer(OT_WARNINGS_LAYER, WARNINGS_COLOR)

            # Clear previous warnings
            settings = rd.ObjectEnumeratorSettings()
            settings.LayerIndexFilter = warn_layer
            for obj in doc.Objects.GetObjectList(settings):
                doc.Objects.Delete(obj.Id, True)

            # Add thin points
            points = [pt for pt, _, _ in thin_points]
            if points:
                cloud = rg.PointCloud(points)
                attrs = rd.ObjectAttributes()
                attrs.LayerIndex = warn_layer
                attrs.ColorSource = rd.ObjectColorSource.ColorFromLayer
                doc.Objects.AddPointCloud(cloud, attrs)

            Rhino.RhinoApp.WriteLine(
                "Orthotic Toolkit: Thickness warning -- "
                "{} thin points in: {}. Min: {:.1f}mm".format(
                    len(thin_points), region_list, min_thick
                )
            )
        else:
            Rhino.RhinoApp.WriteLine(
                "Orthotic Toolkit: Minimum thickness OK -- "
                "{:.1f}mm (threshold {:.1f}mm)".format(
                    min_thick, MIN_THICKNESS_MM
                )
            )

        # Update panel total
        _update_panel_total(total)

        doc.Views.Redraw()

        Rhino.RhinoApp.WriteLine(
            "Orthotic Toolkit: {} of 3 thickness layers built. "
            "Total: {:.1f}mm.".format(layers_built, total)
        )
        return rc.Result.Success

    def _extrude_layer(self, outline, z_top, z_bot, tol):
        """Extrude the outline between two Z levels to create a layer Brep."""
        # Move outline to z_top
        outline_copy = outline.DuplicateCurve()
        move_to_top = rg.Transform.Translation(0, 0, z_top)
        outline_copy.Transform(move_to_top)

        # Extrude downward
        thickness = z_top - z_bot
        extrude_vec = rg.Vector3d(0, 0, -thickness)
        srf = rg.Surface.CreateExtrusion(outline_copy, extrude_vec)
        if srf is None:
            return None

        brep = srf.ToBrep()
        if brep is None:
            return None

        capped = brep.CapPlanarHoles(tol)
        return capped if capped is not None else brep
