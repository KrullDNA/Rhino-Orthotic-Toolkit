# -*- coding: utf-8 -*-
"""Orthotic Toolkit - OT_GenerateOutline Command

Generates the insole outline by offsetting the footprint curve,
then creates a sole-conforming insole Brep whose top surface matches
the shoe last's sole shape.  Falls back to flat extrusion if the
conforming approach fails.
"""

import clr
import System
clr.AddReference("System.Drawing")
import System.Drawing
import Rhino
import Rhino.Display
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

# ---------------------------------------------------------------------------
# Display conduit for live insole preview
# ---------------------------------------------------------------------------

class _InsolePreviewConduit(Rhino.Display.DisplayConduit):
    """Draws a translucent insole mesh preview in the viewport.

    Set ``mesh`` to a Rhino.Geometry.Mesh and call ``Enabled = True``
    to start drawing.  Set ``mesh = None`` and ``Enabled = False``
    to stop.
    """

    def __init__(self):
        super(_InsolePreviewConduit, self).__init__()
        self.mesh = None
        self._material = Rhino.Display.DisplayMaterial()
        self._material.Diffuse = System.Drawing.Color.FromArgb(100, 0, 120, 255)
        self._material.Transparency = 0.55

    def CalculateBoundingBox(self, e):
        if self.mesh is not None:
            e.IncludeBoundingBox(self.mesh.GetBoundingBox(False))

    def PostDrawObjects(self, e):
        if self.mesh is not None:
            e.Display.DrawMeshShaded(self.mesh, self._material)


# Module-level singleton so it survives across command invocations
_preview_conduit = _InsolePreviewConduit()


# ---------------------------------------------------------------------------
# Outline curve builder (shared by command and live preview)
# ---------------------------------------------------------------------------

def _build_outline_curve(footprint, perimeter_offset, toe_ext, heel_ext):
    """Build the offset insole outline curve from the footprint.

    Returns a closed curve or None.
    """
    tol = sc.doc.ModelAbsoluteTolerance
    plane = rg.Plane.WorldXY

    offset_curves = footprint.Offset(
        plane, -perimeter_offset, tol, rg.CurveOffsetCornerStyle.Sharp
    )
    if offset_curves is None or len(offset_curves) == 0:
        offset_curves = footprint.Offset(
            plane, perimeter_offset, tol, rg.CurveOffsetCornerStyle.Sharp
        )
    if offset_curves is None or len(offset_curves) == 0:
        return None

    outline = offset_curves[0]

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

    if not outline.IsClosed:
        outline.MakeClosed(tol)

    return outline


def update_insole_preview(perimeter_offset, toe_ext, heel_ext):
    """Rebuild the live insole mesh preview from current state.

    Called by panel sliders on value change.  If prerequisites are
    missing the preview is silently cleared.
    """
    if state.active_last_brep is None or state.footprint_curve is None:
        _preview_conduit.mesh = None
        _preview_conduit.Enabled = False
        return

    outline = _build_outline_curve(
        state.footprint_curve, perimeter_offset, toe_ext, heel_ext,
    )
    if outline is None:
        _preview_conduit.mesh = None
        _preview_conduit.Enabled = False
        return

    total_thickness = (
        state.cover_thickness_mm
        + state.shell_thickness_mm
        + state.base_thickness_mm
    )

    mesh = _build_insole_mesh(state.active_last_brep, outline, total_thickness)
    _preview_conduit.mesh = mesh
    _preview_conduit.Enabled = mesh is not None

    # Redraw viewports to show updated preview
    try:
        sc.doc.Views.Redraw()
    except Exception:
        pass


def disable_insole_preview():
    """Turn off the live preview conduit (e.g. after committing geometry)."""
    _preview_conduit.mesh = None
    _preview_conduit.Enabled = False


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


def _build_insole_mesh(last_brep, outline, total_thickness):
    """Build the insole as a Rhino.Geometry.Mesh.

    Creates a planar mesh from the outline curve using Rhino's mesher,
    then projects vertices onto the shoe last sole via ray-shooting.
    Bottom surface is a flat plane at z_bottom = min(sole_z) - thickness.
    Side walls connect top perimeter to bottom perimeter.

    Returns a Mesh or None on failure.
    """
    tol = sc.doc.ModelAbsoluteTolerance
    brep_bbox = last_brep.GetBoundingBox(True)
    if not brep_bbox.IsValid:
        return None

    z_start = brep_bbox.Min.Z - 10.0
    fallback_z = brep_bbox.Min.Z

    def sole_z(x, y):
        z = _sole_z_at(last_brep, x, y, z_start)
        return z if z is not None else fallback_z

    # --- Step 1: Create a planar Brep from the outline ---
    planar_breps = rg.Brep.CreatePlanarBreps(outline, tol)
    if planar_breps is None or len(planar_breps) == 0:
        return None
    planar_brep = planar_breps[0]

    # --- Step 2: Mesh the planar Brep with Rhino's mesher ---
    # Use fine meshing for a smooth, uniform triangulation
    mp = rg.MeshingParameters.DefaultAnalysisMesh
    mp.MaximumEdgeLength = 3.0   # ~3mm max edge for smooth surface
    mp.MinimumEdgeLength = 1.0
    mp.GridAspectRatio = 1.0     # keep triangles roughly equilateral
    mp.SimplePlanes = False

    flat_meshes = rg.Mesh.CreateFromBrep(planar_brep, mp)
    if flat_meshes is None or len(flat_meshes) == 0:
        return None
    flat_mesh = flat_meshes[0]

    if flat_mesh.Vertices.Count < 4:
        return None

    # --- Step 3: Project each vertex onto the sole surface ---
    all_z = []
    for i in range(flat_mesh.Vertices.Count):
        v = flat_mesh.Vertices[i]
        z = sole_z(v.X, v.Y)
        all_z.append(z)

    z_bottom = min(all_z) - total_thickness

    # --- Step 4: Build the final mesh with top, bottom, and side walls ---
    mesh = rg.Mesh()
    n_verts = flat_mesh.Vertices.Count

    # Add top vertices (projected onto sole)
    for i in range(n_verts):
        v = flat_mesh.Vertices[i]
        mesh.Vertices.Add(v.X, v.Y, all_z[i])

    # Add bottom vertices (flat plane)
    for i in range(n_verts):
        v = flat_mesh.Vertices[i]
        mesh.Vertices.Add(v.X, v.Y, z_bottom)

    # Top faces (same topology as the planar mesh)
    for fi in range(flat_mesh.Faces.Count):
        f = flat_mesh.Faces[fi]
        if f.IsQuad:
            mesh.Faces.AddFace(f.A, f.B, f.C, f.D)
        else:
            mesh.Faces.AddFace(f.A, f.B, f.C)

    # Bottom faces (reversed winding for outward normals)
    for fi in range(flat_mesh.Faces.Count):
        f = flat_mesh.Faces[fi]
        if f.IsQuad:
            mesh.Faces.AddFace(
                f.A + n_verts, f.D + n_verts,
                f.C + n_verts, f.B + n_verts,
            )
        else:
            mesh.Faces.AddFace(
                f.A + n_verts, f.C + n_verts, f.B + n_verts,
            )

    # --- Step 5: Side walls from naked edges (boundary edges) ---
    # Naked edges are boundary edges of the flat mesh — the outline perimeter
    boundary_edges = []
    top = flat_mesh.TopologyEdges
    for ei in range(top.Count):
        conn_faces = top.GetConnectedFaces(ei)
        if conn_faces is not None and len(conn_faces) == 1:
            edge_verts = top.GetTopologyVertices(ei)
            # Map topology vertex indices to mesh vertex indices
            a = flat_mesh.TopologyVertices.MeshVertexIndices(edge_verts.I)[0]
            b = flat_mesh.TopologyVertices.MeshVertexIndices(edge_verts.J)[0]
            boundary_edges.append((a, b))

    for a, b in boundary_edges:
        # Quad: top_a, top_b, bottom_b, bottom_a
        mesh.Faces.AddFace(a, b, b + n_verts, a + n_verts)

    # --- Step 6: Finalise ---
    mesh.Normals.ComputeNormals()
    mesh.Compact()
    if not mesh.IsValid:
        mesh.RebuildNormals()

    return mesh


def _create_conforming_insole(last_brep, outline, total_thickness):
    """Create an insole Brep whose top conforms to the sole, bottom is flat.

    Returns a Brep or None on failure.
    """
    mesh = _build_insole_mesh(last_brep, outline, total_thickness)
    if mesh is None:
        return None

    brep_result = rg.Brep.CreateFromMesh(mesh, False)
    return brep_result


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

        # Disable live preview — we are committing final geometry
        disable_insole_preview()

        # Build the outline curve from footprint + parameters
        outline = _build_outline_curve(
            state.footprint_curve, perimeter_offset, toe_ext, heel_ext,
        )
        if outline is None:
            Rhino.RhinoApp.WriteLine(
                "Orthotic Toolkit: Footprint offset failed."
            )
            _show_panel_warning("Footprint offset failed.")
            return rc.Result.Failure

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

        # Remove previous outline/insole objects if they exist
        if state.insole_outline_guid is not None:
            doc.Objects.Delete(state.insole_outline_guid, True)
            state.insole_outline_guid = None
        if state.insole_brep_guid is not None:
            doc.Objects.Delete(state.insole_brep_guid, True)
            state.insole_brep_guid = None

        # Add outline to OT_Outline layer
        outline_layer = ensure_layer(OT_OUTLINE_LAYER)
        attrs = rd.ObjectAttributes()
        attrs.LayerIndex = outline_layer
        attrs.ColorSource = rd.ObjectColorSource.ColorFromLayer
        state.insole_outline_guid = doc.Objects.AddCurve(outline, attrs)

        # Add insole Brep to OT_Insole layer
        insole_layer = ensure_layer(OT_INSOLE_LAYER)
        attrs2 = rd.ObjectAttributes()
        attrs2.LayerIndex = insole_layer
        attrs2.ColorSource = rd.ObjectColorSource.ColorFromLayer
        state.insole_brep_guid = doc.Objects.AddBrep(insole_brep, attrs2)

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
