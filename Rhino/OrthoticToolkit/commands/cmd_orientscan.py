# -*- coding: utf-8 -*-
"""Orthotic Toolkit - OT_OrientScan Command

Orients the imported foot scan mesh so the plantar surface faces -Z.
"""

import System
import Rhino
import Rhino.Geometry as rg
import Rhino.Commands as rc
import Rhino.DocObjects as rd
import Eto.Forms as ef
import scriptcontext as sc

import state
from geometry import mesh_utils


OT_FOOTSCAN_LAYER = "OT_FootScan"


class OT_OrientScan(rc.Command):
    """Auto-orient the foot scan mesh so the plantar surface faces down."""

    def __init__(self):
        super().__init__()

    @property
    def EnglishName(self):
        return "OT_OrientScan"

    def RunCommand(self, doc, mode):
        if state.foot_scan_mesh is None:
            ef.MessageBox.Show(
                "No foot scan mesh loaded. Please use Import Scan first.",
                "Orthotic Toolkit - No Scan",
                ef.MessageBoxButtons.OK,
                ef.MessageBoxType.Warning,
            )
            Rhino.RhinoApp.WriteLine(
                "Orthotic Toolkit: No foot scan mesh loaded."
            )
            return rc.Result.Failure

        # Orient the mesh
        rotated_mesh, angle_deg = mesh_utils.orient_mesh_plantar_down(
            state.foot_scan_mesh
        )

        if angle_deg < 10.0:
            Rhino.RhinoApp.WriteLine(
                "Orthotic Toolkit: Scan is already correctly oriented."
            )
            return rc.Result.Success

        # Update state
        state.foot_scan_mesh = rotated_mesh

        # Find and update the mesh object on the OT_FootScan layer
        layer_index = doc.Layers.FindByFullPath(OT_FOOTSCAN_LAYER, -1)
        if layer_index >= 0:
            settings = rd.ObjectEnumeratorSettings()
            settings.LayerIndexFilter = layer_index
            settings.ObjectTypeFilter = rd.ObjectType.Mesh
            for obj in doc.Objects.GetObjectList(settings):
                doc.Objects.Replace(obj.Id, rotated_mesh)
                break

        doc.Views.Redraw()

        Rhino.RhinoApp.WriteLine(
            "Orthotic Toolkit: Scan oriented. "
            "Rotation applied: {:.1f} degrees.".format(angle_deg)
        )
        return rc.Result.Success
