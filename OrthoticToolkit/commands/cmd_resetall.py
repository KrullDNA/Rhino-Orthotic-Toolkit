# -*- coding: utf-8 -*-
"""Orthotic Toolkit - OT_ResetAll Command

Resets all plugin state to defaults and refreshes the panel labels.
"""

import Rhino
import Rhino.Commands as rc
import Rhino.UI as rui
import System

import state


PANEL_GUID = System.Guid("B2C3D4E5-F6A7-8901-BCDE-F12345678901")


class OT_ResetAll(rc.Command):
    """Clears all Orthotic Toolkit state and resets the panel."""

    def __init__(self):
        super().__init__()

    @property
    def EnglishName(self):
        return "OT_ResetAll"

    def RunCommand(self, doc, mode):
        # Remove any preview objects from the document before clearing IDs
        for obj_id in state.preview_object_ids:
            try:
                doc.Objects.Delete(obj_id, True)
            except Exception:
                pass

        # Reset all state variables
        state.reset_all()

        doc.Views.Redraw()

        # Try to refresh the panel labels
        try:
            panels = rui.Panels.GetOpenPanelContents(PANEL_GUID)
            if panels is not None:
                for panel in panels:
                    if hasattr(panel, "reset_labels"):
                        panel.reset_labels()
        except Exception:
            pass  # Panel may not be open

        Rhino.RhinoApp.WriteLine("Orthotic Toolkit: All state cleared.")
        return rc.Result.Success
