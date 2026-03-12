#!/usr/bin/env python3
"""Build the Orthotic Toolkit .rhi package in the correct Rhino Python plugin format.

The Rhino Python plugin .rhi format requires:
  - A zip file with .rhi extension
  - Containing a folder: PluginName {GUID}/
  - Inside that folder, a 'dev/' subfolder
  - dev/__plugin__.py with just: id, version, title
  - dev/CommandName_cmd.py files with RunCommand(is_interactive) functions
  - Any supporting .py modules in dev/
"""

import os
import re
import zipfile
import textwrap

PLUGIN_GUID = "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
PLUGIN_NAME = "OrthoticToolkit"
FOLDER_NAME = "{} {{{}}}".format(PLUGIN_NAME, PLUGIN_GUID)
RHI_FILE = "OrthoticToolkit_v1.0.rhi"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SRC_DIR = os.path.join(BASE_DIR, "OrthoticToolkit")

# Map of original command file -> (command name, class name)
COMMANDS = {
    "cmd_setlast.py": "OT_SetLast",
    "cmd_importscan.py": "OT_ImportScan",
    "cmd_orientscan.py": "OT_OrientScan",
    "cmd_extractplantar.py": "OT_ExtractPlantar",
    "cmd_outline.py": "OT_GenerateOutline",
    "cmd_arch.py": "OT_AddArch",
    "cmd_heelcup.py": "OT_AddHeelCup",
    "cmd_metdome.py": "OT_AddMetDome",
    "cmd_posting.py": "OT_AddPosting",
    "cmd_thickness.py": "OT_SetThickness",
    "cmd_validate.py": "OT_ValidateInsole",
    "cmd_rocker.py": "OT_RockerOutline",
    "cmd_export.py": "OT_ExportInsole",
    "cmd_resetall.py": "OT_ResetAll",
}


def convert_command_file(src_path, command_name):
    """Convert a class-based command file to a _cmd.py function-based format.

    Reads the source file, extracts:
    - Module-level imports and helper functions
    - The RunCommand method body from the class

    Produces a _cmd.py file with RunCommand(is_interactive) function.
    """
    with open(src_path, "r", encoding="utf-8") as f:
        source = f.read()

    lines = source.split("\n")

    # Find where the class starts
    class_line_idx = None
    for i, line in enumerate(lines):
        if re.match(r"^class\s+\w+\(", line):
            class_line_idx = i
            break

    if class_line_idx is None:
        # No class found - return source as-is with a RunCommand wrapper
        return source

    # Everything before the class is module-level code (imports, helpers, constants)
    preamble_lines = lines[:class_line_idx]

    # Find RunCommand method inside the class
    run_cmd_start = None
    run_cmd_indent = None
    for i in range(class_line_idx, len(lines)):
        if "def RunCommand(self" in lines[i]:
            run_cmd_start = i
            # Determine indentation of the def line
            run_cmd_indent = len(lines[i]) - len(lines[i].lstrip())
            break

    if run_cmd_start is None:
        return source

    # Extract the RunCommand body (everything after the def line until next
    # method at same indent level or end of class/file)
    body_lines = []
    body_indent = None
    for i in range(run_cmd_start + 1, len(lines)):
        line = lines[i]
        stripped = line.lstrip()

        # Empty lines are part of the body
        if not stripped:
            body_lines.append("")
            continue

        current_indent = len(line) - len(stripped)

        if body_indent is None:
            body_indent = current_indent

        # If we hit a line at or less than the method def indent, we're done
        # (unless it's a decorator or new method)
        if current_indent <= run_cmd_indent and stripped:
            break

        # De-indent by the body indent amount
        if current_indent >= body_indent:
            body_lines.append(line[body_indent:])
        else:
            body_lines.append(line)

    # Strip trailing empty lines
    while body_lines and not body_lines[-1].strip():
        body_lines.pop()

    # Build the converted file
    output_lines = []

    # Add modified preamble - fix imports
    # Need to add scriptcontext if not present, and ensure doc is available
    has_scriptcontext = False
    for line in preamble_lines:
        if "scriptcontext" in line:
            has_scriptcontext = True
        output_lines.append(line)

    if not has_scriptcontext:
        # Insert scriptcontext import after the last import line
        last_import = 0
        for i, line in enumerate(output_lines):
            if line.startswith("import ") or line.startswith("from "):
                last_import = i
        output_lines.insert(last_import + 1, "import scriptcontext as sc")

    output_lines.append("")
    output_lines.append("")

    # Add the command name variable and RunCommand function
    output_lines.append('__commandname__ = "{}"'.format(command_name))
    output_lines.append("")
    output_lines.append("")
    output_lines.append("def RunCommand(is_interactive):")

    # Process body: replace 'doc' references with 'scriptcontext.doc' / 'sc.doc'
    # and convert return values
    for line in body_lines:
        # Replace doc. with sc.doc. (the doc parameter from RunCommand(self, doc, mode))
        # But be careful not to replace 'doc' inside strings or other words
        modified = line
        # Replace standalone 'doc.' references (was passed as parameter)
        modified = re.sub(r'\bdoc\.', 'sc.doc.', modified)
        # Fix double-substitution: sc.sc.doc -> sc.doc
        modified = modified.replace('sc.sc.doc.', 'sc.doc.')

        # Convert return values
        modified = modified.replace("return rc.Result.Success", "return 0  # Success")
        modified = modified.replace("return rc.Result.Failure", "return 1  # Failure")
        modified = modified.replace("return rc.Result.Cancel", "return 1  # Cancel")
        modified = modified.replace("return go.CommandResult()", "return 1  # Cancelled")

        output_lines.append("    " + modified if modified.strip() else "")

    # If body doesn't end with a return, add one
    last_real = ""
    for bl in reversed(body_lines):
        if bl.strip():
            last_real = bl.strip()
            break
    if not last_real.startswith("return"):
        output_lines.append("    return 0  # Success")

    output_lines.append("")

    # Also check: any helper functions that reference check_minimum_thickness
    # from cmd_thickness need to be handled
    result = "\n".join(output_lines)

    # Fix cross-file imports: 'from commands.cmd_xxx import' -> direct import
    result = result.replace("from commands.", "from ")
    # Fix 'from cmd_thickness import' -> since files are now in same dir
    # but named differently, we need to handle this
    result = result.replace("from cmd_thickness import check_minimum_thickness",
                           "from OT_SetThickness_cmd import check_minimum_thickness")
    result = result.replace("from cmd_validate import run_validation",
                           "from OT_ValidateInsole_cmd import run_validation")

    return result


def create_plugin_py():
    """Create the simple __plugin__.py metadata file."""
    return textwrap.dedent("""\
        id="{{{}}}"
        version="1.0.0.0"
        title="Orthotic Toolkit"
    """.format(PLUGIN_GUID))


def create_show_panel_cmd():
    """Create the OT_ShowPanel_cmd.py command to open the panel as a form."""
    return textwrap.dedent("""\
        # -*- coding: utf-8 -*-
        \"\"\"Orthotic Toolkit - OT_ShowPanel Command

        Opens the Orthotic Toolkit panel as a modeless form.
        \"\"\"

        import Rhino
        import Eto.Forms as ef
        import Eto.Drawing as ed


        __commandname__ = "OT_ShowPanel"

        # Module-level reference to keep the form alive
        _panel_form = None


        def RunCommand(is_interactive):
            global _panel_form

            # If form already exists and is visible, just bring it to front
            if _panel_form is not None:
                try:
                    if _panel_form.Visible:
                        _panel_form.BringToFront()
                        return 0
                except Exception:
                    _panel_form = None

            try:
                from panel import OrthoticPanel
                _panel_form = OrthoticPanel()
                _panel_form.Show()
                Rhino.RhinoApp.WriteLine("Orthotic Toolkit: Panel opened.")
            except Exception as ex:
                Rhino.RhinoApp.WriteLine(
                    "Orthotic Toolkit: Failed to open panel - {}".format(ex)
                )
                return 1

            return 0
    """)


def convert_panel_to_form(src_path):
    """Convert the panel from ef.Panel to ef.Form for modeless display."""
    with open(src_path, "r", encoding="utf-8") as f:
        source = f.read()

    # Change base class from ef.Panel to ef.Form
    source = source.replace(
        "class OrthoticPanel(ef.Panel):",
        "class OrthoticPanel(ef.Form):"
    )
    source = source.replace(
        '"""Dockable panel for the Orthotic Toolkit plugin."""',
        '"""Modeless form for the Orthotic Toolkit plugin."""'
    )

    # Fix super() for IronPython 2.7 compatibility and add form configuration
    source = source.replace(
        "        super().__init__()\n        self._build_ui()",
        '        super(OrthoticPanel, self).__init__()\n'
        '        self.Title = "Orthotic Toolkit"\n'
        '        self.MinimumSize = ed.Size(340, 600)\n'
        '        self.Size = ed.Size(380, 750)\n'
        '        self.Resizable = True\n'
        '        self.ShowInTaskbar = True\n'
        '        self._build_ui()'
    )

    # Fix all remaining super() calls without arguments (IronPython 2.7)
    source = source.replace("super().__init__()", "super(OrthoticPanel, self).__init__()")

    # Update docstring
    source = source.replace(
        "OrthoticPanel is an Eto.Forms.Panel with eight tabs",
        "OrthoticPanel is an Eto.Forms.Form with eight tabs"
    )
    source = source.replace("Dockable Panel", "Modeless Panel Form")

    return source


def build_rhi():
    """Build the .rhi package with the correct structure."""
    rhi_path = os.path.join(BASE_DIR, RHI_FILE)

    with zipfile.ZipFile(rhi_path, "w", zipfile.ZIP_DEFLATED) as zf:
        # RHI installer expects all files at the ROOT of the zip.
        # It recognises Python plugins by finding __plugin__.py at root.
        # The installer handles creating the PluginName {GUID}/dev/ structure
        # in the PythonPlugIns directory on the user's machine.

        # 1. __plugin__.py (metadata only)
        zf.writestr("__plugin__.py", create_plugin_py())
        print("  Added __plugin__.py")

        # 2. Convert and add all command files
        cmd_dir = os.path.join(SRC_DIR, "commands")
        for src_file, cmd_name in COMMANDS.items():
            src_path = os.path.join(cmd_dir, src_file)
            if not os.path.exists(src_path):
                print("  WARNING: {} not found, skipping".format(src_file))
                continue

            converted = convert_command_file(src_path, cmd_name)
            target_name = "{}_cmd.py".format(cmd_name)
            zf.writestr(target_name, converted)
            print("  Added {} (from {})".format(target_name, src_file))

        # 3. Add OT_ShowPanel command
        zf.writestr("OT_ShowPanel_cmd.py", create_show_panel_cmd())
        print("  Added OT_ShowPanel_cmd.py")

        # 4. Convert and add panel.py
        panel_path = os.path.join(SRC_DIR, "panel.py")
        converted_panel = convert_panel_to_form(panel_path)
        zf.writestr("panel.py", converted_panel)
        print("  Added panel.py (converted to Form)")

        # 5. Add state.py
        state_path = os.path.join(SRC_DIR, "state.py")
        with open(state_path, "r", encoding="utf-8") as f:
            zf.writestr("state.py", f.read())
        print("  Added state.py")

        # 6. Add geometry package
        geom_dir = os.path.join(SRC_DIR, "geometry")
        for geom_file in os.listdir(geom_dir):
            if geom_file.endswith(".py"):
                geom_path = os.path.join(geom_dir, geom_file)
                with open(geom_path, "r", encoding="utf-8") as f:
                    zf.writestr("geometry/" + geom_file, f.read())
                print("  Added geometry/{}".format(geom_file))

        # 7. Add toolbar .rui file
        rui_path = os.path.join(SRC_DIR, "OrthoticToolkit.rui")
        if os.path.exists(rui_path):
            with open(rui_path, "rb") as f:
                zf.writestr("OrthoticToolkit.rui", f.read())
            print("  Added OrthoticToolkit.rui")

        # 8. Add documentation
        for doc_file in ["README_INSTALL.txt", "QUICK_REFERENCE.txt"]:
            doc_path = os.path.join(SRC_DIR, doc_file)
            if os.path.exists(doc_path):
                with open(doc_path, "r", encoding="utf-8") as f:
                    zf.writestr(doc_file, f.read())
                print("  Added {}".format(doc_file))

    print("\nBuilt: {}".format(rhi_path))
    print("\nPackage structure:")
    with zipfile.ZipFile(rhi_path, "r") as zf:
        for name in sorted(zf.namelist()):
            print("  {}".format(name))


if __name__ == "__main__":
    print("Building Orthotic Toolkit .rhi package...\n")
    build_rhi()
    print("\nDone!")
