# -*- coding: utf-8 -*-
"""Orthotic Toolkit - OT_ImportScan Command

Opens a file dialog for STL/OBJ/PLY, imports the mesh into Rhino,
prompts the user to select the imported mesh, and stores it in state.
"""

import os
import System
import Rhino
import Rhino.Geometry as rg
import Rhino.Input as ri
import Rhino.Commands as rc
import Rhino.DocObjects as rd
import Rhino.UI as rui
import Eto.Forms as ef
import scriptcontext as sc

import state


PANEL_GUID = System.Guid("B2C3D4E5-F6A7-8901-BCDE-F12345678901")
OT_FOOTSCAN_LAYER = "OT_FootScan"
FOOTSCAN_COLOR = System.Drawing.Color.FromArgb(100, 149, 237)  # Cornflower blue


def _ensure_layer(name, color):
    """Create a layer if it does not exist; return its index."""
    layer_index = sc.doc.Layers.FindByFullPath(name, -1)
    if layer_index < 0:
        layer = rd.Layer()
        layer.Name = name
        layer.Color = color
        layer_index = sc.doc.Layers.Add(layer)
    return layer_index


def _refresh_panel_scan(filename):
    """Update the panel scan label."""
    try:
        panels = rui.Panels.GetOpenPanelContents(PANEL_GUID)
        if panels is not None:
            for panel in panels:
                if hasattr(panel, "update_scan_label"):
                    panel.update_scan_label(filename)
    except Exception:
        pass


class OT_ImportScan(rc.Command):
    """Import a foot scan mesh from STL, OBJ, or PLY file."""

    def __init__(self):
        super().__init__()

    @property
    def EnglishName(self):
        return "OT_ImportScan"

    def RunCommand(self, doc, mode):
        # Open file dialog filtered to mesh formats
        dlg = ef.OpenFileDialog()
        dlg.Title = "Import Foot Scan"
        dlg.Filters.Add(ef.FileFilter("Mesh Files", ".stl", ".obj", ".ply"))
        dlg.Filters.Add(ef.FileFilter("STL Files", ".stl"))
        dlg.Filters.Add(ef.FileFilter("OBJ Files", ".obj"))
        dlg.Filters.Add(ef.FileFilter("PLY Files", ".ply"))
        dlg.Filters.Add(ef.FileFilter("All Files", ".*"))

        result = dlg.ShowDialog(None)
        if result != ef.DialogResult.Ok:
            return rc.Result.Cancel

        filepath = dlg.FileName
        if not filepath or not os.path.exists(filepath):
            Rhino.RhinoApp.WriteLine(
                "Orthotic Toolkit: File not found."
            )
            return rc.Result.Failure

        filename = os.path.basename(filepath)

        # Import the file using Rhino's built-in importer
        import_script = '_-Import "{}" _Enter'.format(filepath)
        Rhino.RhinoApp.RunScript(import_script, False)

        # Prompt user to select the imported mesh
        Rhino.RhinoApp.WriteLine(
            "Orthotic Toolkit: Please select the imported mesh object."
        )

        go = ri.Custom.GetObject()
        go.SetCommandPrompt("Select imported foot scan mesh")
        go.GeometryFilter = rd.ObjectType.Mesh
        go.SubObjectSelect = False
        go.Get()

        if go.CommandResult() != rc.Result.Success:
            return go.CommandResult()

        obj_ref = go.Object(0)
        mesh = obj_ref.Mesh()
        if mesh is None:
            ef.MessageBox.Show(
                "The selected object is not a mesh. Please select a "
                "mesh object imported from a scan file.",
                "Orthotic Toolkit - Invalid Selection",
                ef.MessageBoxButtons.OK,
                ef.MessageBoxType.Warning,
            )
            Rhino.RhinoApp.WriteLine(
                "Orthotic Toolkit: Selected object is not a mesh."
            )
            return rc.Result.Failure

        # Store in state
        state.foot_scan_mesh = mesh.DuplicateMesh()
        state.foot_scan_filename = filename

        # Move the object to the OT_FootScan layer
        layer_index = _ensure_layer(OT_FOOTSCAN_LAYER, FOOTSCAN_COLOR)
        rhino_obj = obj_ref.Object()
        attrs = rhino_obj.Attributes.Duplicate()
        attrs.LayerIndex = layer_index
        doc.Objects.ModifyAttributes(rhino_obj.Id, attrs, True)

        doc.Views.Redraw()

        # Update panel
        _refresh_panel_scan(filename)

        Rhino.RhinoApp.WriteLine(
            "Orthotic Toolkit: Foot scan '{}' imported successfully. "
            "{} faces, {} vertices.".format(
                filename, mesh.Faces.Count, mesh.Vertices.Count
            )
        )
        return rc.Result.Success
