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
            axis = getattr(state, "toe_heel_axis", "Y")
            toe_dir = getattr(state, "toe_direction", 1)

            if axis == "X":
                ax_range = bbox.Max.X - bbox.Min.X
            else:
                ax_range = bbox.Max.Y - bbox.Min.Y

            if ax_range > 0:
                total_ext = toe_ext + heel_ext
                scale_factor = (ax_range + total_ext) / ax_range
                shift = toe_dir * (toe_ext - heel_ext) / 2.0

                if axis == "X":
                    xform_scale = rg.Transform.Scale(
                        rg.Plane(center, rg.Vector3d.XAxis, rg.Vector3d.YAxis),
                        scale_factor, 1.0, 1.0,
                    )
                    outline.Transform(xform_scale)
                    if abs(shift) > 0.001:
                        xform_move = rg.Transform.Translation(shift, 0, 0)
                        outline.Transform(xform_move)
                else:
                    xform_scale = rg.Transform.Scale(
                        rg.Plane(center, rg.Vector3d.XAxis, rg.Vector3d.YAxis),
                        1.0, scale_factor, 1.0,
                    )
                    outline.Transform(xform_scale)
                    if abs(shift) > 0.001:
                        xform_move = rg.Transform.Translation(0, shift, 0)
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
    """Read outline parameters from state (synced by panel before command runs)."""
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


def _build_insole_mesh(last_brep, outline, total_thickness, bottom_outline=None):
    """Build the insole as a Rhino.Geometry.Mesh.

    Creates a planar mesh from the outline curve using Rhino's mesher,
    then projects vertices onto the shoe last sole via ray-shooting.
    Bottom surface is a flat plane at z_bottom = min(sole_z) - thickness.
    If bottom_outline is provided and differs from outline, boundary
    vertices on the bottom are moved to match it (creating a flare).

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

    planar_breps = rg.Brep.CreatePlanarBreps(outline, tol)
    if planar_breps is None or len(planar_breps) == 0:
        return None
    planar_brep = planar_breps[0]

    mp = rg.MeshingParameters.DefaultAnalysisMesh
    mp.MaximumEdgeLength = 3.0
    mp.MinimumEdgeLength = 1.0
    mp.GridAspectRatio = 1.0
    mp.SimplePlanes = False

    flat_meshes = rg.Mesh.CreateFromBrep(planar_brep, mp)
    if flat_meshes is None or len(flat_meshes) == 0:
        return None
    flat_mesh = flat_meshes[0]

    if flat_mesh.Vertices.Count < 4:
        return None

    all_z = []
    for i in range(flat_mesh.Vertices.Count):
        v = flat_mesh.Vertices[i]
        z = sole_z(v.X, v.Y)
        all_z.append(z)

    z_bottom = min(all_z) - total_thickness

    mesh = rg.Mesh()
    n_verts = flat_mesh.Vertices.Count

    for i in range(n_verts):
        v = flat_mesh.Vertices[i]
        mesh.Vertices.Add(v.X, v.Y, all_z[i])

    for i in range(n_verts):
        v = flat_mesh.Vertices[i]
        mesh.Vertices.Add(v.X, v.Y, z_bottom)

    for fi in range(flat_mesh.Faces.Count):
        f = flat_mesh.Faces[fi]
        if f.IsQuad:
            mesh.Faces.AddFace(f.A, f.B, f.C, f.D)
        else:
            mesh.Faces.AddFace(f.A, f.B, f.C)

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

    # Find boundary edges and vertices
    boundary_edges = []
    boundary_verts = set()
    topo = flat_mesh.TopologyEdges
    for ei in range(topo.Count):
        conn_faces = topo.GetConnectedFaces(ei)
        if conn_faces is not None and len(conn_faces) == 1:
            edge_verts = topo.GetTopologyVertices(ei)
            a = flat_mesh.TopologyVertices.MeshVertexIndices(edge_verts.I)[0]
            b = flat_mesh.TopologyVertices.MeshVertexIndices(edge_verts.J)[0]
            boundary_edges.append((a, b))
            boundary_verts.add(a)
            boundary_verts.add(b)

    # If a separate bottom outline is given, move boundary bottom vertices
    if bottom_outline is not None:
        for vi in boundary_verts:
            v = flat_mesh.Vertices[vi]
            pt = rg.Point3d(v.X, v.Y, 0)
            success, t = bottom_outline.ClosestPoint(pt)
            if success:
                bp = bottom_outline.PointAt(t)
                mesh.Vertices.SetVertex(vi + n_verts, bp.X, bp.Y, z_bottom)

    for a, b in boundary_edges:
        mesh.Faces.AddFace(a, b, b + n_verts, a + n_verts)

    mesh.Normals.ComputeNormals()
    mesh.Compact()
    if not mesh.IsValid:
        mesh.RebuildNormals()

    return mesh


def _create_conforming_insole(last_brep, outline, total_thickness,
                              bottom_outline=None):
    """Create an insole Brep whose top conforms to the sole, bottom is flat.

    Returns a Brep or None on failure.
    """
    mesh = _build_insole_mesh(last_brep, outline, total_thickness,
                              bottom_outline)
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


OT_BOTTOM_OUTLINE_LAYER = "OT_BottomOutline"


def _remove_previous_objects(doc):
    """Delete previous outline, bottom outline, and insole objects."""
    for attr in ("insole_outline_guid", "insole_bottom_outline_guid",
                 "insole_brep_guid"):
        guid = getattr(state, attr, None)
        if guid is not None:
            doc.Objects.Delete(guid, True)
            setattr(state, attr, None)


def _build_and_add_insole(doc, top_outline, bottom_outline, total_thickness):
    """Build the insole mesh and add all objects to the document.

    Creates the insole from top_outline (and optional bottom_outline),
    adds curves and mesh to the document with grips enabled.
    Returns True on success.
    """
    Rhino.RhinoApp.WriteLine(
        "Orthotic Toolkit: Creating sole-conforming insole..."
    )

    insole_brep = _create_conforming_insole(
        state.active_last_brep, top_outline, total_thickness,
        bottom_outline,
    )

    conforming = insole_brep is not None
    if not conforming:
        Rhino.RhinoApp.WriteLine(
            "Orthotic Toolkit: Conforming approach unavailable, "
            "using flat extrusion."
        )
        insole_brep = _create_flat_insole(top_outline, total_thickness)

    if insole_brep is None:
        Rhino.RhinoApp.WriteLine(
            "Orthotic Toolkit: Failed to create insole solid."
        )
        return False

    state.insole_brep = insole_brep
    if conforming:
        state.insole_top_surface = insole_brep

    # Remove previous objects
    _remove_previous_objects(doc)

    # Add top outline to OT_Outline layer with grips
    outline_layer = ensure_layer(OT_OUTLINE_LAYER)
    attrs = rd.ObjectAttributes()
    attrs.LayerIndex = outline_layer
    attrs.ColorSource = rd.ObjectColorSource.ColorFromLayer
    guid = doc.Objects.AddCurve(top_outline, attrs)
    state.insole_outline_guid = guid
    obj = doc.Objects.FindId(guid)
    if obj is not None:
        obj.GripsOn = True

    # Create bottom outline at z_bottom with grips
    brep_bbox = state.active_last_brep.GetBoundingBox(True)
    z_start = brep_bbox.Min.Z - 10.0
    fallback_z = brep_bbox.Min.Z
    z_sample = _sole_z_at(
        state.active_last_brep,
        brep_bbox.Center.X, brep_bbox.Center.Y, z_start,
    )
    if z_sample is None:
        z_sample = fallback_z
    z_bottom = z_sample - total_thickness

    if bottom_outline is not None:
        bot_curve = bottom_outline.DuplicateCurve()
    else:
        bot_curve = top_outline.DuplicateCurve()

    # Move bottom curve to z_bottom
    xform = rg.Transform.Translation(0, 0, z_bottom)
    bot_curve.Transform(xform)

    bot_layer = ensure_layer(OT_BOTTOM_OUTLINE_LAYER)
    attrs_bot = rd.ObjectAttributes()
    attrs_bot.LayerIndex = bot_layer
    attrs_bot.ColorSource = rd.ObjectColorSource.ColorFromLayer
    bot_guid = doc.Objects.AddCurve(bot_curve, attrs_bot)
    state.insole_bottom_outline_guid = bot_guid
    bot_obj = doc.Objects.FindId(bot_guid)
    if bot_obj is not None:
        bot_obj.GripsOn = True

    # Add insole Brep to OT_Insole layer
    insole_layer = ensure_layer(OT_INSOLE_LAYER)
    attrs2 = rd.ObjectAttributes()
    attrs2.LayerIndex = insole_layer
    attrs2.ColorSource = rd.ObjectColorSource.ColorFromLayer
    state.insole_brep_guid = doc.Objects.AddBrep(insole_brep, attrs2)

    doc.Views.Redraw()
    return True


def apply_edited_outline():
    """Read back edited outline curves and rebuild the insole.

    Called from the panel's Apply Outline button.
    """
    doc = sc.doc

    if state.active_last_brep is None:
        Rhino.RhinoApp.WriteLine(
            "Orthotic Toolkit: No shoe last selected."
        )
        return

    # Read back the top outline curve
    top_outline = None
    if state.insole_outline_guid is not None:
        obj = doc.Objects.FindId(state.insole_outline_guid)
        if obj is not None:
            top_outline = obj.Geometry.DuplicateCurve()

    if top_outline is None:
        Rhino.RhinoApp.WriteLine(
            "Orthotic Toolkit: No outline curve found. "
            "Run Generate Outline first."
        )
        return

    # Read back the bottom outline curve (projected to XY for shape)
    bottom_outline = None
    if state.insole_bottom_outline_guid is not None:
        obj = doc.Objects.FindId(state.insole_bottom_outline_guid)
        if obj is not None:
            bot_crv = obj.Geometry.DuplicateCurve()
            # Project to Z=0 for XY shape comparison
            flat = rg.Curve.ProjectToPlane(bot_crv, rg.Plane.WorldXY)
            if flat is not None:
                bottom_outline = flat

    # Disable live preview
    disable_insole_preview()

    state.insole_outline = top_outline

    total_thickness = (
        state.cover_thickness_mm
        + state.shell_thickness_mm
        + state.base_thickness_mm
    )

    result = _build_and_add_insole(
        doc, top_outline, bottom_outline, total_thickness,
    )
    if result:
        Rhino.RhinoApp.WriteLine(
            "Orthotic Toolkit: Insole rebuilt from edited outlines."
        )
    else:
        Rhino.RhinoApp.WriteLine(
            "Orthotic Toolkit: Failed to rebuild insole."
        )


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

        # Rebuild outline as smooth NURBS with editable control points
        rebuilt = outline.Rebuild(20, 3, False)
        if rebuilt is not None:
            outline = rebuilt

        # Store outline in state
        state.insole_outline = outline

        total_thickness = (
            state.cover_thickness_mm
            + state.shell_thickness_mm
            + state.base_thickness_mm
        )

        # Build the insole
        result = _build_and_add_insole(doc, outline, None, total_thickness)
        if not result:
            _show_panel_warning("Insole creation failed.")
            return rc.Result.Failure

        Rhino.RhinoApp.WriteLine(
            "Orthotic Toolkit: Insole outline generated. "
            "Offset: {:.1f}mm, Toe ext: {:.1f}mm, Heel ext: {:.1f}mm. "
            "Grips enabled - drag control points to edit, "
            "then click Apply Outline.".format(
                perimeter_offset, toe_ext, heel_ext
            )
        )
        return rc.Result.Success
