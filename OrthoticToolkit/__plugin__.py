# -*- coding: utf-8 -*-
"""Orthotic Toolkit - Plugin Registration

Rhino 8 Python plugin entry point. Registers the plugin and the
dockable OrthoticPanel on load. Installs a global exception handler
so that unhandled Python errors are logged to the command history
and shown in a dialog rather than producing raw tracebacks.
"""

import sys
import traceback
import System
import Rhino
import Rhino.PlugIns as rpi
import Rhino.UI as rui
import Eto.Forms as ef


PLUGIN_GUID = System.Guid("A1B2C3D4-E5F6-7890-ABCD-EF1234567890")
PANEL_GUID = System.Guid("B2C3D4E5-F6A7-8901-BCDE-F12345678901")


def _global_exception_handler(exc_type, exc_value, exc_tb):
    """Catch any unhandled exception from plugin code and report it."""
    try:
        tb_text = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
        Rhino.RhinoApp.WriteLine(
            "OrthoticToolkit ERROR: Unhandled exception --"
        )
        for line in tb_text.splitlines():
            Rhino.RhinoApp.WriteLine("  {}".format(line))

        ef.MessageBox.Show(
            "An unexpected error occurred in the Orthotic Toolkit plugin.\n\n"
            "{}: {}\n\n"
            "Details have been printed to the Rhino command history.\n"
            "Please report this issue to the plugin developer.".format(
                exc_type.__name__, exc_value
            ),
            "OrthoticToolkit - Unexpected Error",
            ef.MessageBoxButtons.OK,
            ef.MessageBoxType.Error,
        )
    except Exception:
        # Absolutely last resort -- do not allow the handler itself to crash
        pass


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
        # Install global exception handler
        sys.excepthook = _global_exception_handler

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
