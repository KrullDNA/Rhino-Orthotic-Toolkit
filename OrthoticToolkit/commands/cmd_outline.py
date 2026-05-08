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
OT_BOTTOM_OUTLINE_LAYER = "OT_BottomOutline"

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

    mesh, _info = _build_insole_mesh(state.active_last_brep, outline, total_thickness)
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
    Side walls connect top perimeter to bottom perimeter.

    Returns (mesh, boundary_info) where boundary_info is a dict with
    'ordered_indices', 'n_verts', 'z_bottom', or (None, None) on failure.
    """
    tol = sc.doc.ModelAbsoluteTolerance
    brep_bbox = last_brep.GetBoundingBox(True)
    if not brep_bbox.IsValid:
        return None, None

    z_start = brep_bbox.Min.Z - 10.0
    fallback_z = brep_bbox.Min.Z

    def sole_z(x, y):
        z = _sole_z_at(last_brep, x, y, z_start)
        return z if z is not None else fallback_z

    # --- Step 1: Create a planar Brep from the outline ---
    planar_breps = rg.Brep.CreatePlanarBreps(outline, tol)
    if planar_breps is None or len(planar_breps) == 0:
        return None, None
    planar_brep = planar_breps[0]

    # --- Step 2: Mesh the planar Brep with Rhino's mesher ---
    mp = rg.MeshingParameters.DefaultAnalysisMesh
    mp.MaximumEdgeLength = 3.0
    mp.MinimumEdgeLength = 1.0
    mp.GridAspectRatio = 1.0
    mp.SimplePlanes = False

    flat_meshes = rg.Mesh.CreateFromBrep(planar_brep, mp)
    if flat_meshes is None or len(flat_meshes) == 0:
        return None, None
    flat_mesh = flat_meshes[0]

    if flat_mesh.Vertices.Count < 4:
        return None, None

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
    boundary_edges = []
    boundary_verts = set()
    top = flat_mesh.TopologyEdges
    for ei in range(top.Count):
        conn_faces = top.GetConnectedFaces(ei)
        if conn_faces is not None and len(conn_faces) == 1:
            edge_verts = top.GetTopologyVertices(ei)
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

    # --- Step 5b: Chain boundary edges into ordered vertex list ---
    adj = {}
    for a, b in boundary_edges:
        adj.setdefault(a, []).append(b)
        adj.setdefault(b, []).append(a)

    ordered = []
    if len(boundary_edges) > 0:
        start = boundary_edges[0][0]
        ordered.append(start)
        visited = {start}
        current = start
        while True:
            nxt = None
            for nb in adj.get(current, []):
                if nb not in visited:
                    nxt = nb
                    break
            if nxt is None:
                break
            ordered.append(nxt)
            visited.add(nxt)
            current = nxt

    # --- Step 6: Finalise ---
    mesh.Normals.ComputeNormals()
    mesh.Compact()
    if not mesh.IsValid:
        mesh.RebuildNormals()

    boundary_info = {
        "ordered": ordered,
        "n_verts": n_verts,
        "z_bottom": z_bottom,
    }

    return mesh, boundary_info


def _create_conforming_insole(last_brep, outline, total_thickness, bottom_outline=None):
    """Create an insole Brep whose top conforms to the sole, bottom is flat.

    Returns a Brep or None on failure.
    """
    mesh, _info = _build_insole_mesh(last_brep, outline, total_thickness, bottom_outline)
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


def _remove_previous_objects(doc):
    """Delete previous outline, bottom outline, and insole objects."""
    for attr in ("insole_outline_guid", "insole_bottom_outline_guid",
                 "insole_brep_guid"):
        guid = getattr(state, attr, None)
        if guid is not None:
            doc.Objects.Delete(guid, True)
            setattr(state, attr, None)


def _curves_from_boundary(mesh, boundary_info):
    """Build smooth top and bottom edge curves from mesh boundary vertices.

    Uses the ordered boundary vertex indices (found on the flat_mesh before
    side walls were added) to read positions from the final mesh.

    Returns (top_curve, bottom_curve) or (None, None).
    """
    ordered = boundary_info.get("ordered", [])
    n_verts = boundary_info.get("n_verts", 0)
    z_bottom = boundary_info.get("z_bottom", 0)

    if len(ordered) < 3 or n_verts == 0:
        return None, None

    top_pts = []
    bot_pts = []
    for vi in ordered:
        tv = mesh.Vertices[vi]
        top_pts.append(rg.Point3d(tv.X, tv.Y, tv.Z))
        bv = mesh.Vertices[vi + n_verts]
        bot_pts.append(rg.Point3d(bv.X, bv.Y, bv.Z))

    top_pts.append(top_pts[0])
    bot_pts.append(bot_pts[0])

    top_crv = rg.Curve.CreateInterpolatedCurve(
        top_pts, 3, rg.CurveKnotStyle.ChordSquareRoot,
    )
    bot_crv = rg.Curve.CreateInterpolatedCurve(
        bot_pts, 3, rg.CurveKnotStyle.ChordSquareRoot,
    )

    if top_crv is not None:
        rebuilt = top_crv.Rebuild(20, 3, False)
        if rebuilt is not None:
            top_crv = rebuilt
    if bot_crv is not None:
        rebuilt = bot_crv.Rebuild(20, 3, False)
        if rebuilt is not None:
            bot_crv = rebuilt

    return top_crv, bot_crv


def _build_and_add_insole(doc, top_outline, bottom_outline, total_thickness):
    """Build the insole and add all objects to the document with grips enabled."""
    Rhino.RhinoApp.WriteLine(
        "Orthotic Toolkit: Creating sole-conforming insole..."
    )

    insole_mesh, boundary_info = _build_insole_mesh(
        state.active_last_brep, top_outline, total_thickness,
        bottom_outline,
    )
    if insole_mesh is None:
        Rhino.RhinoApp.WriteLine(
            "Orthotic Toolkit: Failed to build insole mesh."
        )
        return False

    insole_brep = rg.Brep.CreateFromMesh(insole_mesh, False)
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

    _remove_previous_objects(doc)

    # Build edge curves from mesh boundary vertices
    top_edge, bot_edge = _curves_from_boundary(insole_mesh, boundary_info)

    if top_edge is None:
        top_edge = top_outline
    if bot_edge is None:
        bot_edge = top_outline.DuplicateCurve()
        z_bot = boundary_info.get("z_bottom", 0) if boundary_info else 0
        xform = rg.Transform.Translation(0, 0, z_bot)
        bot_edge.Transform(xform)

    # Add top edge curve with grips
    outline_layer = ensure_layer(OT_OUTLINE_LAYER)
    attrs = rd.ObjectAttributes()
    attrs.LayerIndex = outline_layer
    attrs.ColorSource = rd.ObjectColorSource.ColorFromLayer
    guid = doc.Objects.AddCurve(top_edge, attrs)
    state.insole_outline_guid = guid
    obj = doc.Objects.FindId(guid)
    if obj is not None:
        obj.GripsOn = True

    # Add bottom edge curve with grips
    bot_layer = ensure_layer(OT_BOTTOM_OUTLINE_LAYER)
    attrs_bot = rd.ObjectAttributes()
    attrs_bot.LayerIndex = bot_layer
    attrs_bot.ColorSource = rd.ObjectColorSource.ColorFromLayer
    bot_guid = doc.Objects.AddCurve(bot_edge, attrs_bot)
    state.insole_bottom_outline_guid = bot_guid
    bot_obj = doc.Objects.FindId(bot_guid)
    if bot_obj is not None:
        bot_obj.GripsOn = True

    # Add insole as mesh — set blue color and lock it
    insole_layer = ensure_layer(OT_INSOLE_LAYER)
    attrs2 = rd.ObjectAttributes()
    attrs2.LayerIndex = insole_layer
    attrs2.ColorSource = rd.ObjectColorSource.ColorFromObject
    attrs2.ObjectColor = System.Drawing.Color.FromArgb(0, 120, 255)
    state.insole_brep_guid = doc.Objects.AddMesh(insole_mesh, attrs2)
    mesh_obj = doc.Objects.FindId(state.insole_brep_guid)
    if mesh_obj is not None:
        mesh_obj.Attributes.Mode = rd.ObjectMode.Locked
        mesh_obj.CommitChanges()

    doc.Views.Redraw()
    return True


def apply_edited_outline():
    """Read back edited outline curves and rebuild the insole.

    Flattens the edited top curve to XY to get the new perimeter shape,
    then rebuilds the insole mesh using _build_insole_mesh (which
    ray-shoots onto the sole surface for correct Z heights).  Only the
    mesh is replaced — the curves stay where the user dragged them.
    """
    doc = sc.doc

    if state.active_last_brep is None:
        Rhino.RhinoApp.WriteLine(
            "Orthotic Toolkit: No shoe last selected."
        )
        return

    # Deselect everything to force Rhino to commit grip edits
    Rhino.RhinoApp.RunScript("_SelNone", False)

    top_curve = None
    if state.insole_outline_guid is not None:
        obj = doc.Objects.FindId(state.insole_outline_guid)
        if obj is not None:
            # Try reading grip positions directly
            grips = obj.GetGrips()
            if grips is not None and len(grips) > 0:
                pts = [g.CurrentLocation for g in grips]
                grip_crv = rg.Curve.CreateInterpolatedCurve(
                    pts, 3, rg.CurveKnotStyle.ChordSquareRoot,
                )
                if grip_crv is not None:
                    top_curve = grip_crv
                    Rhino.RhinoApp.WriteLine(
                        "Orthotic Toolkit: Apply - read {} grip positions".format(
                            len(pts)
                        )
                    )
            # Fallback to stored geometry
            if top_curve is None:
                top_curve = obj.Geometry.DuplicateCurve()

    if top_curve is None:
        Rhino.RhinoApp.WriteLine(
            "Orthotic Toolkit: No outline curve found. "
            "Run Generate Outline first."
        )
        return

    # Flatten to XY to get the new perimeter shape
    top_bb = top_curve.GetBoundingBox(True)
    flat_top = rg.Curve.ProjectToPlane(top_curve, rg.Plane.WorldXY)
    if flat_top is None:
        flat_top = top_curve

    flat_bb = flat_top.GetBoundingBox(True)
    Rhino.RhinoApp.WriteLine(
        "Orthotic Toolkit: Apply - edited curve bbox X: {:.1f}-{:.1f}, "
        "Y: {:.1f}-{:.1f} -> flat X: {:.1f}-{:.1f}, Y: {:.1f}-{:.1f}".format(
            top_bb.Min.X, top_bb.Max.X, top_bb.Min.Y, top_bb.Max.Y,
            flat_bb.Min.X, flat_bb.Max.X, flat_bb.Min.Y, flat_bb.Max.Y,
        )
    )

    # Read bottom curve if edited, flatten to XY
    bottom_outline = None
    if state.insole_bottom_outline_guid is not None:
        obj = doc.Objects.FindId(state.insole_bottom_outline_guid)
        if obj is not None:
            bot_crv = None
            grips = obj.GetGrips()
            if grips is not None and len(grips) > 0:
                pts = [g.CurrentLocation for g in grips]
                grip_crv = rg.Curve.CreateInterpolatedCurve(
                    pts, 3, rg.CurveKnotStyle.ChordSquareRoot,
                )
                if grip_crv is not None:
                    bot_crv = grip_crv
            if bot_crv is None:
                bot_crv = obj.Geometry.DuplicateCurve()
            flat_bot = rg.Curve.ProjectToPlane(bot_crv, rg.Plane.WorldXY)
            if flat_bot is not None:
                bottom_outline = flat_bot

    disable_insole_preview()

    total_thickness = (
        state.cover_thickness_mm
        + state.shell_thickness_mm
        + state.base_thickness_mm
    )

    # Rebuild insole mesh using the new XY outline shape
    Rhino.RhinoApp.WriteLine(
        "Orthotic Toolkit: Apply - rebuilding with thickness {:.1f}mm...".format(
            total_thickness
        )
    )

    new_mesh, _info = _build_insole_mesh(
        state.active_last_brep, flat_top, total_thickness, bottom_outline,
    )
    if new_mesh is None:
        Rhino.RhinoApp.WriteLine(
            "Orthotic Toolkit: Failed to rebuild insole from edited outline."
        )
        return

    mesh_bb = new_mesh.GetBoundingBox(True)
    Rhino.RhinoApp.WriteLine(
        "Orthotic Toolkit: Apply - new mesh verts: {}, "
        "bbox X: {:.1f}-{:.1f}, Y: {:.1f}-{:.1f}, Z: {:.1f}-{:.1f}".format(
            new_mesh.Vertices.Count,
            mesh_bb.Min.X, mesh_bb.Max.X,
            mesh_bb.Min.Y, mesh_bb.Max.Y,
            mesh_bb.Min.Z, mesh_bb.Max.Z,
        )
    )

    # Remove old insole mesh only (keep the curves in place)
    if state.insole_brep_guid is not None:
        doc.Objects.Delete(state.insole_brep_guid, True)
        state.insole_brep_guid = None

    # Add new insole mesh — set blue color and lock it
    insole_layer = ensure_layer(OT_INSOLE_LAYER)
    attrs = rd.ObjectAttributes()
    attrs.LayerIndex = insole_layer
    attrs.ColorSource = rd.ObjectColorSource.ColorFromObject
    attrs.ObjectColor = System.Drawing.Color.FromArgb(0, 120, 255)
    state.insole_brep_guid = doc.Objects.AddMesh(new_mesh, attrs)
    mesh_obj = doc.Objects.FindId(state.insole_brep_guid)
    if mesh_obj is not None:
        mesh_obj.Attributes.Mode = rd.ObjectMode.Locked
        mesh_obj.CommitChanges()

    state.insole_outline = flat_top
    state.insole_brep = new_mesh

    doc.Views.Redraw()

    Rhino.RhinoApp.WriteLine(
        "Orthotic Toolkit: Insole rebuilt from edited outline shape."
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

        state.insole_outline = outline

        total_thickness = (
            state.cover_thickness_mm
            + state.shell_thickness_mm
            + state.base_thickness_mm
        )

        result = _build_and_add_insole(doc, outline, None, total_thickness)
        if not result:
            _show_panel_warning("Insole creation failed.")
            return rc.Result.Failure

        Rhino.RhinoApp.WriteLine(
            "Orthotic Toolkit: Insole outline generated. "
            "Grips enabled - drag control points then click Apply Outline."
        )
        return rc.Result.Success
