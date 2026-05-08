# -*- coding: utf-8 -*-
"""Orthotic Toolkit - OT_ValidateInsole Command

Runs a full validation suite on the insole Brep and produces a report.
Can be run silently (returns dict) or interactively (shows Eto dialog).
"""

import math
import System
import Rhino
import Rhino.Geometry as rg
import Rhino.Commands as rc
import Rhino.UI as rui
import Eto.Forms as ef
import Eto.Drawing as ed
import scriptcontext as sc

import state
from commands.cmd_thickness import check_minimum_thickness


PANEL_GUID = System.Guid("B2C3D4E5-F6A7-8901-BCDE-F12345678901")
MIN_THICKNESS_MM = 2.0
OVERHANG_THRESHOLD_DEG = 45.0


def run_validation(silent=False):
    """Run all validation checks and return a results dict.

    Args:
        silent: If True, skip the Eto dialog and only return results.

    Returns:
        A dict with keys: is_valid, is_solid, min_thickness, overhang_count,
        overall, report_text.
    """
    results = {
        "is_valid": False,
        "is_solid": False,
        "min_thickness": 0.0,
        "overhang_count": 0,
        "overall": "ISSUES FOUND",
        "report_text": "",
    }

    tol = sc.doc.ModelAbsoluteTolerance

    # Check a) -- brep exists
    if state.insole_brep is None:
        results["report_text"] = _format_report(results)
        if not silent:
            _show_report_dialog(results["report_text"])
        return results

    brep = state.insole_brep

    # Check b) -- IsValid
    results["is_valid"] = brep.IsValid
    if not results["is_valid"]:
        # Attempt repair
        try:
            repaired = brep.Repair(tol)
            if repaired:
                results["is_valid"] = brep.IsValid
                if results["is_valid"]:
                    Rhino.RhinoApp.WriteLine(
                        "Orthotic Toolkit: Brep repaired successfully."
                    )
        except Exception:
            pass

    # Check c) -- IsSolid
    results["is_solid"] = brep.IsSolid

    # Check d) -- Minimum thickness
    min_thick, thin_points = check_minimum_thickness(
        brep, 200, MIN_THICKNESS_MM
    )
    results["min_thickness"] = min_thick

    # Check e) -- Overhangs > 45 degrees
    overhang_count = 0
    up = rg.Vector3d(0, 0, 1)
    cos_threshold = math.cos(math.radians(OVERHANG_THRESHOLD_DEG))

    for i in range(brep.Faces.Count):
        face = brep.Faces[i]
        u_domain = face.Domain(0)
        v_domain = face.Domain(1)
        u_mid = u_domain.Mid
        v_mid = v_domain.Mid

        success, frame = face.FrameAt(u_mid, v_mid)
        if not success:
            continue

        normal = frame.ZAxis
        if face.OrientationIsReversed:
            normal = -normal

        # Dot product with up vector
        dot = normal * up
        # If normal points significantly downward, it's an overhang
        if dot < -cos_threshold:
            overhang_count += 1

    results["overhang_count"] = overhang_count

    # Determine overall status
    all_pass = (
        results["is_valid"]
        and results["is_solid"]
        and min_thick >= MIN_THICKNESS_MM
        and overhang_count == 0
    )
    results["overall"] = "READY FOR EXPORT" if all_pass else "ISSUES FOUND"

    # Format report
    results["report_text"] = _format_report(results)

    # Print to command history
    for line in results["report_text"].split("\n"):
        Rhino.RhinoApp.WriteLine(line)

    if not silent:
        _show_report_dialog(results["report_text"])

    return results


def _format_report(results):
    """Format validation results into a text report."""
    lines = [
        "OT Validation Report:",
        "  IsValid:  {}".format(
            "PASS" if results["is_valid"] else "FAIL"
        ),
        "  IsSolid:  {}".format(
            "PASS" if results["is_solid"] else "FAIL"
        ),
        "  Min thickness: {:.1f}mm ({})".format(
            results["min_thickness"],
            "PASS" if results["min_thickness"] >= MIN_THICKNESS_MM else "WARN",
        ),
        "  Overhangs > 45deg: {} faces ({})".format(
            results["overhang_count"],
            "PASS" if results["overhang_count"] == 0 else "WARN",
        ),
        "  Overall: {}".format(results["overall"]),
    ]
    return "\n".join(lines)


def _show_report_dialog(report_text):
    """Show the validation report in a scrollable Eto dialog."""
    dialog = ef.Dialog()
    dialog.Title = "Orthotic Toolkit - Validation Report"
    dialog.ClientSize = ed.Size(400, 280)
    dialog.Resizable = True

    layout = ef.DynamicLayout()
    layout.DefaultSpacing = ed.Size(5, 5)
    layout.DefaultPadding = ed.Padding(10)

    text_area = ef.TextArea()
    text_area.Text = report_text
    text_area.ReadOnly = True
    text_area.Font = ed.Fonts.Monospace(10)
    text_area.ToolTip = "Validation report for the current insole Brep."
    layout.Add(text_area, yscale=True)

    btn_ok = ef.Button()
    btn_ok.Text = "OK"
    btn_ok.ToolTip = "Close this dialog."
    btn_ok.Click += lambda s, e: dialog.Close()
    layout.Add(btn_ok)

    dialog.Content = layout
    dialog.ShowModal()


class OT_ValidateInsole(rc.Command):
    """Run a full validation of the insole Brep."""

    def __init__(self):
        super().__init__()

    @property
    def EnglishName(self):
        return "OT_ValidateInsole"

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
                "No insole Brep to validate. Build an insole first.",
                "Orthotic Toolkit - No Insole",
                ef.MessageBoxButtons.OK,
                ef.MessageBoxType.Warning,
            )
            return rc.Result.Failure

        results = run_validation(silent=False)

        if results["overall"] == "READY FOR EXPORT":
            return rc.Result.Success
        return rc.Result.Success  # Still success -- just informational
