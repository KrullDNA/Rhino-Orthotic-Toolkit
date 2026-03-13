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
        return hits[0].Z
    return None


def _create_conforming_insole(last_brep, outline, total_thickness):
    """Create an insole Brep whose top surface conforms to the shoe last sole.

    Builds a closed mesh by:
      1. Sampling the outline perimeter densely and ray-shooting each
         point upward to get the sole Z height.
      2. Creating concentric inner rings (interpolated toward the centroid)
         with ray-shot Z values for interior detail.
      3. Connecting rings with quad faces (top + bottom), adding a
         triangle fan to the centroid, and stitching side walls.
      4. Converting the closed mesh to a Brep.

    Returns a Brep or None on failure.
    """
    tol = sc.doc.ModelAbsoluteTolerance
    brep_bbox = last_brep.GetBoundingBox(True)

    if not brep_bbox.IsValid:
        return None

    z_start = brep_bbox.Min.Z - 10.0

    # --- Helper: ray-shoot with fallback ---
    fallback_z = brep_bbox.Min.Z

    def sole_z(x, y):
        z = _sole_z_at(last_brep, x, y, z_start)
        return z if z is not None else fallback_z

    # --- Step 1: Sample outline perimeter ---
    N_PERIM = 80
    div_params = outline.DivideByCount(N_PERIM, True)
    if div_params is None or len(div_params) < 10:
        return None

    perim_xy = []
    for t in div_params:
        pt = outline.PointAt(t)
        perim_xy.append((pt.X, pt.Y))

    # --- Step 2: Compute centroid ---
    area_props = rg.AreaMassProperties.Compute(outline)
    if area_props is None:
        return None
    centroid = area_props.Centroid

    # --- Step 3: Build concentric rings ---
    # ring_fractions: 0.0 = perimeter, approaching 1.0 = centroid
    ring_fractions = [0.0, 0.20, 0.40, 0.60, 0.80]
    rings = []  # each ring is a list of (x, y)

    for frac in ring_fractions:
        ring = []
        for px, py in perim_xy:
            x = px + frac * (centroid.X - px)
            y = py + frac * (centroid.Y - py)
            ring.append((x, y))
        rings.append(ring)

    # --- Step 4: Build mesh vertices ---
    mesh = rg.Mesh()

    ring_top = []   # ring_top[r][i] = vertex index
    ring_bot = []

    for ring in rings:
        row_top = []
        row_bot = []
        for x, y in ring:
            z = sole_z(x, y)
            ti = mesh.Vertices.Add(x, y, z)
            bi = mesh.Vertices.Add(x, y, z - total_thickness)
            row_top.append(ti)
            row_bot.append(bi)
        ring_top.append(row_top)
        ring_bot.append(row_bot)

    # Centroid vertex
    cz = sole_z(centroid.X, centroid.Y)
    ct = mesh.Vertices.Add(centroid.X, centroid.Y, cz)
    cb = mesh.Vertices.Add(centroid.X, centroid.Y, cz - total_thickness)

    n = len(perim_xy)

    # --- Step 5: Quad faces between consecutive rings ---
    for r in range(len(rings) - 1):
        ot = ring_top[r]
        ob = ring_bot[r]
        it_ = ring_top[r + 1]
        ib = ring_bot[r + 1]
        for i in range(n):
            j = (i + 1) % n
            # Top quad (normal up → CCW from above)
            mesh.Faces.AddFace(ot[i], ot[j], it_[j], it_[i])
            # Bottom quad (normal down → CW from above)
            mesh.Faces.AddFace(ob[i], ib[i], ib[j], ob[j])

    # --- Step 6: Triangle fan from innermost ring to centroid ---
    inner_t = ring_top[-1]
    inner_b = ring_bot[-1]
    for i in range(n):
        j = (i + 1) % n
        mesh.Faces.AddFace(inner_t[i], inner_t[j], ct)
        mesh.Faces.AddFace(inner_b[i], cb, inner_b[j])

    # --- Step 7: Side walls on outermost ring (perimeter) ---
    outer_t = ring_top[0]
    outer_b = ring_bot[0]
    for i in range(n):
        j = (i + 1) % n
        mesh.Faces.AddFace(outer_t[i], outer_b[i], outer_b[j], outer_t[j])

    # --- Step 8: Finalise mesh ---
    mesh.Normals.ComputeNormals()
    mesh.Compact()

    if not mesh.IsValid:
        Rhino.RhinoApp.WriteLine(
            "Orthotic Toolkit: Conforming mesh invalid, attempting repair."
        )
        mesh.RebuildNormals()

    # Convert to Brep
    brep_result = rg.Brep.CreateFromMesh(mesh, False)
    if brep_result is not None:
        return brep_result

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
