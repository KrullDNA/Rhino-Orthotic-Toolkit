# -*- coding: utf-8 -*-
"""Orthotic Toolkit - OT_ExportInsole Command

Validates the insole, then exports it in the user-selected format
(STL, STEP, OBJ, 3DM). Supports export by layer and rocker inclusion.
"""

import os
import System
import Rhino
import Rhino.Geometry as rg
import Rhino.Commands as rc
import Rhino.DocObjects as rd
import Rhino.UI as rui
import Eto.Forms as ef
import Eto.Drawing as ed
import scriptcontext as sc

import state
from commands.cmd_validate import run_validation


PANEL_GUID = System.Guid("B2C3D4E5-F6A7-8901-BCDE-F12345678901")

# Format to file extension and filter mapping
FORMAT_MAP = {
    "STL": (".stl", "STL Files (*.stl)|*.stl"),
    "STEP": (".stp", "STEP Files (*.stp)|*.stp"),
    "OBJ": (".obj", "OBJ Files (*.obj)|*.obj"),
    "3DM": (".3dm", "Rhino Files (*.3dm)|*.3dm"),
}

# Mesh tolerance presets
MESH_PRESETS = {
    "Draft (0.5mm)": 0.5,
    "Standard (0.2mm)": 0.2,
    "Fine (0.1mm)": 0.1,
    "Ultra (0.05mm)": 0.05,
}


def _get_panel_values():
    """Read export parameters from the panel."""
    try:
        panels = rui.Panels.GetOpenPanelContents(PANEL_GUID)
        if panels is not None:
            for panel in panels:
                if hasattr(panel, "get_export_params"):
                    return panel.get_export_params()
    except Exception:
        pass
    return (
        state.export_format,
        state.mesh_tolerance,
        state.export_by_layer,
        state.include_rocker,
    )


def _export_brep_as_mesh(brep, filepath, tolerance):
    """Export a Brep as a mesh file (STL or OBJ)."""
    mp = rg.MeshingParameters(tolerance)
    meshes = rg.Mesh.CreateFromBrep(brep, mp)
    if meshes is None or len(meshes) == 0:
        return False

    # Combine all meshes
    combined = rg.Mesh()
    for m in meshes:
        combined.Append(m)

    if not combined.IsValid:
        combined.Normals.ComputeNormals()
        combined.Compact()

    # Write via RunScript with a temporary object
    tol = sc.doc.ModelAbsoluteTolerance
    attrs = rd.ObjectAttributes()
    guid = sc.doc.Objects.AddMesh(combined, attrs)

    if guid == System.Guid.Empty:
        return False

    try:
        # Select only this object
        sc.doc.Objects.UnselectAll()
        obj = sc.doc.Objects.FindId(guid)
        if obj is not None:
            obj.Select(True)

        ext = os.path.splitext(filepath)[1].lower()
        if ext == ".stl":
            script = '_-Export "{}" _Enter'.format(filepath)
        else:
            script = '_-Export "{}" _Enter'.format(filepath)

        Rhino.RhinoApp.RunScript(script, False)
        return os.path.exists(filepath)
    finally:
        sc.doc.Objects.Delete(guid, True)
        sc.doc.Objects.UnselectAll()


def _export_step(brep, filepath):
    """Export a Brep as STEP via RunScript."""
    attrs = rd.ObjectAttributes()
    guid = sc.doc.Objects.AddBrep(brep, attrs)

    if guid == System.Guid.Empty:
        return False

    try:
        sc.doc.Objects.UnselectAll()
        obj = sc.doc.Objects.FindId(guid)
        if obj is not None:
            obj.Select(True)

        script = '_-Export "{}" _Enter'.format(filepath)
        Rhino.RhinoApp.RunScript(script, False)
        return os.path.exists(filepath)
    finally:
        sc.doc.Objects.Delete(guid, True)
        sc.doc.Objects.UnselectAll()


def _export_3dm(brep, filepath):
    """Export a Brep as 3DM."""
    try:
        file_3dm = Rhino.FileIO.File3dm()
        file_3dm.Objects.AddBrep(brep)
        result = file_3dm.Write(filepath, 8)
        return result
    except Exception as ex:
        Rhino.RhinoApp.WriteLine(
            "Orthotic Toolkit: 3DM export failed -- {}".format(ex)
        )
        return False


class OT_ExportInsole(rc.Command):
    """Export the finished insole in the selected format."""

    def __init__(self):
        super().__init__()

    @property
    def EnglishName(self):
        return "OT_ExportInsole"

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
                "No insole Brep to export. Build an insole first.",
                "Orthotic Toolkit - No Insole",
                ef.MessageBoxButtons.OK,
                ef.MessageBoxType.Warning,
            )
            return rc.Result.Failure

        # Run validation silently
        results = run_validation(silent=True)

        if results["overall"] == "ISSUES FOUND":
            # Show confirmation dialog
            answer = ef.MessageBox.Show(
                "Validation found issues:\n\n{}\n\n"
                "Export anyway?".format(results["report_text"]),
                "Orthotic Toolkit - Validation Warning",
                ef.MessageBoxButtons.YesNo,
                ef.MessageBoxType.Warning,
            )
            if answer != ef.DialogResult.Yes:
                Rhino.RhinoApp.WriteLine(
                    "Orthotic Toolkit: Export cancelled by user."
                )
                return rc.Result.Cancel

        # Read export parameters
        fmt, mesh_tol, by_layer, include_rocker = _get_panel_values()
        state.export_format = fmt
        state.mesh_tolerance = mesh_tol
        state.export_by_layer = by_layer
        state.include_rocker = include_rocker

        # Include rocker outline if requested
        if include_rocker:
            Rhino.RhinoApp.RunScript("OT_RockerOutline", False)

        # Get file extension and filter
        ext, file_filter = FORMAT_MAP.get(fmt, (".stl", "STL Files (*.stl)|*.stl"))

        # Open save dialog
        save_dialog = ef.SaveFileDialog()
        save_dialog.Title = "Export Insole"
        save_dialog.Filters.Add(ef.FileFilter(
            "{} Files".format(fmt), "*{}".format(ext)
        ))
        save_dialog.CurrentFilterIndex = 0

        if save_dialog.ShowDialog(None) != ef.DialogResult.Ok:
            return rc.Result.Cancel

        filepath = save_dialog.FileName
        if not filepath.lower().endswith(ext):
            filepath += ext

        if by_layer and (
            state.layer_cover is not None
            or state.layer_shell is not None
            or state.layer_base is not None
        ):
            # Export each layer separately
            base_name = os.path.splitext(filepath)[0]
            exported = 0

            layer_map = [
                ("_cover", state.layer_cover),
                ("_shell", state.layer_shell),
                ("_base", state.layer_base),
            ]

            for suffix, layer_brep in layer_map:
                if layer_brep is None:
                    continue

                layer_path = "{}{}{}".format(base_name, suffix, ext)
                success = self._export_single(
                    layer_brep, layer_path, fmt, mesh_tol, doc
                )
                if success:
                    exported += 1
                    Rhino.RhinoApp.WriteLine(
                        "Orthotic Toolkit: Exported {}".format(layer_path)
                    )

            if exported > 0:
                ef.MessageBox.Show(
                    "Export complete: {} layer files exported to\n{}".format(
                        exported, os.path.dirname(filepath)
                    ),
                    "Orthotic Toolkit - Export Complete",
                    ef.MessageBoxButtons.OK,
                    ef.MessageBoxType.Information,
                )
                return rc.Result.Success
            else:
                Rhino.RhinoApp.WriteLine(
                    "Orthotic Toolkit: No layers exported."
                )
                return rc.Result.Failure
        else:
            # Export single piece
            success = self._export_single(
                state.insole_brep, filepath, fmt, mesh_tol, doc
            )

            if success:
                Rhino.RhinoApp.WriteLine(
                    "Orthotic Toolkit: Exported {}".format(filepath)
                )
                ef.MessageBox.Show(
                    "Export complete: {}".format(filepath),
                    "Orthotic Toolkit - Export Complete",
                    ef.MessageBoxButtons.OK,
                    ef.MessageBoxType.Information,
                )
                return rc.Result.Success
            else:
                Rhino.RhinoApp.WriteLine(
                    "Orthotic Toolkit: Export failed."
                )
                return rc.Result.Failure

    def _export_single(self, brep, filepath, fmt, mesh_tol, doc):
        """Export a single Brep to a file."""
        try:
            if fmt in ("STL", "OBJ"):
                return _export_brep_as_mesh(brep, filepath, mesh_tol)
            elif fmt == "STEP":
                return _export_step(brep, filepath)
            elif fmt == "3DM":
                return _export_3dm(brep, filepath)
            else:
                Rhino.RhinoApp.WriteLine(
                    "Orthotic Toolkit: Unknown format '{}'.".format(fmt)
                )
                return False
        except Exception as ex:
            Rhino.RhinoApp.WriteLine(
                "Orthotic Toolkit: Export error -- {}".format(ex)
            )
            return False
