# -*- coding: utf-8 -*-
"""Orthotic Toolkit - Plugin Registration

Rhino 8 Python plugin entry point. Registers the plugin and the
dockable OrthoticPanel on load.
"""

import System
import Rhino
import Rhino.PlugIns as rpi
import Rhino.UI as rui


PLUGIN_GUID = System.Guid("A1B2C3D4-E5F6-7890-ABCD-EF1234567890")
PANEL_GUID = System.Guid("B2C3D4E5-F6A7-8901-BCDE-F12345678901")


class OrthoticToolkitPlugin(rpi.PlugIn):
    """Main plugin class for the Orthotic Toolkit."""

    def __init__(self):
        super().__init__()
        OrthoticToolkitPlugin.Instance = self

    Instance = None

    @property
    def Id(self):
        return PLUGIN_GUID

    def OnLoad(self, errorMessage):
        """Called when the plugin is loaded. Registers the dockable panel."""
        try:
            from panel import OrthoticPanel
            panel_type = type(OrthoticPanel)
            rui.Panels.RegisterPanel(
                self,
                panel_type,
                "Orthotic Toolkit",
                rui.Resources.GetEmbeddedResourceIcon(None),
                PANEL_GUID,
            )
            Rhino.RhinoApp.WriteLine("Orthotic Toolkit plugin loaded successfully.")
        except Exception as ex:
            errorMessage = str(ex)
            Rhino.RhinoApp.WriteLine(
                "OrthoticToolkit ERROR: Failed to register panel - {}".format(ex)
            )
            return rpi.LoadReturnCode.ErrorShowDialog
        return rpi.LoadReturnCode.Success

    @property
    def PlugInName(self):
        return "Orthotic Toolkit"

    @property
    def PlugInDescription(self):
        return "Professional orthotic insole design tools for Rhino 8"

    @property
    def PlugInVersion(self):
        return "1.0.0"
