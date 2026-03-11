# -*- coding: utf-8 -*-
"""Orthotic Toolkit - Dockable Panel

OrthoticPanel is an Eto.Forms.Panel with eight tabs (one per tool group)
and a status bar at the bottom. All layouts use DynamicLayout with no
fixed pixel sizes.
"""

import Eto.Forms as ef
import Eto.Drawing as ed
import Rhino


# Tab definitions: (title, description)
TAB_DEFINITIONS = [
    (
        "Foot Scan",
        "Import and prepare a foot scan mesh. Orient the scan and extract "
        "the plantar surface for insole design.",
    ),
    (
        "Outline",
        "Generate the insole outline from the shoe last footprint. Adjust "
        "perimeter offset, toe extension, and heel extension.",
    ),
    (
        "Arch",
        "Add medial arch support to the insole. Control arch height, apex "
        "position, width, and blend radius.",
    ),
    (
        "Heel Cup",
        "Design the heel cup geometry. Set cup depth, posterior angle, and "
        "medial/lateral flare angles.",
    ),
    (
        "Forefoot",
        "Add metatarsal dome pads to the forefoot region. Set dome count, "
        "positions, height, and diameter.",
    ),
    (
        "Posting",
        "Apply rearfoot and forefoot posting wedges. Set medial and lateral "
        "angles for both regions.",
    ),
    (
        "Thickness",
        "Control the layered thickness of the insole. Set cover, shell, and "
        "base layer thicknesses independently.",
    ),
    (
        "Export",
        "Validate and export the finished insole. Choose format (STL, STEP, "
        "OBJ, 3DM) and resolution settings.",
    ),
]


class OrthoticPanel(ef.Panel):
    """Dockable panel for the Orthotic Toolkit plugin."""

    def __init__(self):
        super().__init__()
        self._build_ui()

    def _build_ui(self):
        """Build the complete panel UI."""
        # Main vertical layout
        main_layout = ef.DynamicLayout()
        main_layout.DefaultSpacing = ed.Size(5, 5)
        main_layout.DefaultPadding = ed.Padding(5)

        # Tab control with all eight tabs
        self._tab_control = ef.TabControl()

        # First tab is Foot Scan -- built with full controls
        foot_scan_page = self._create_foot_scan_tab()
        self._tab_control.Pages.Add(foot_scan_page)

        # Remaining tabs use placeholder stubs
        for title, description in TAB_DEFINITIONS[1:]:
            page = self._create_tab_page(title, description)
            self._tab_control.Pages.Add(page)

        main_layout.Add(self._tab_control, yscale=True)

        # Status bar at the bottom
        status_layout = self._create_status_bar()
        main_layout.Add(status_layout)

        self.Content = main_layout

    def _create_foot_scan_tab(self):
        """Create the Foot Scan tab with full controls."""
        page = ef.TabPage()
        page.Text = "Foot Scan"

        layout = ef.DynamicLayout()
        layout.DefaultSpacing = ed.Size(5, 5)
        layout.DefaultPadding = ed.Padding(8)

        # Description
        desc_label = ef.Label()
        desc_label.Text = (
            "Import and prepare a foot scan mesh. Orient the scan and "
            "extract the plantar surface for insole design."
        )
        desc_label.Wrap = ef.WrapMode.Word
        desc_label.ToolTip = "Description of the Foot Scan tab functionality."
        layout.Add(desc_label)

        layout.AddSpace()

        # Import Scan button
        btn_import = ef.Button()
        btn_import.Text = "Import Scan..."
        btn_import.ToolTip = (
            "Open a file dialog to import a foot scan mesh from "
            "STL, OBJ, or PLY format."
        )
        btn_import.Click += self._on_import_scan_click
        layout.Add(btn_import)

        layout.AddSpace()

        # Orientation preset dropdown
        orient_label = ef.Label()
        orient_label.Text = "Orientation Preset:"
        orient_label.ToolTip = "Choose how the scan was oriented by the scanner."
        layout.Add(orient_label)

        self._orient_dropdown = ef.DropDown()
        self._orient_dropdown.Items.Add(ef.ListItem(Text="Scanner Default", Key="default"))
        self._orient_dropdown.Items.Add(ef.ListItem(Text="Rotated 90 X", Key="rot90x"))
        self._orient_dropdown.Items.Add(ef.ListItem(Text="Rotated 180 Z", Key="rot180z"))
        self._orient_dropdown.SelectedIndex = 0
        self._orient_dropdown.ToolTip = (
            "Select the orientation preset that matches your scanner's "
            "default output orientation."
        )
        layout.Add(self._orient_dropdown)

        # Auto-Orient button
        btn_orient = ef.Button()
        btn_orient.Text = "Auto-Orient"
        btn_orient.ToolTip = (
            "Automatically rotate the foot scan mesh so the plantar "
            "(sole) surface faces downward (-Z direction)."
        )
        btn_orient.Click += self._on_orient_scan_click
        layout.Add(btn_orient)

        layout.AddSpace()

        # Smoothing slider
        smooth_label = ef.Label()
        smooth_label.Text = "Smoothing Passes:"
        smooth_label.ToolTip = (
            "Number of Laplacian smoothing passes to apply before "
            "extracting the plantar surface. Higher values produce "
            "smoother but less detailed surfaces."
        )
        layout.Add(smooth_label)

        smooth_row = ef.DynamicLayout()
        smooth_row.DefaultSpacing = ed.Size(5, 0)

        self._smooth_slider = ef.Slider()
        self._smooth_slider.MinValue = 0
        self._smooth_slider.MaxValue = 5
        self._smooth_slider.Value = 2
        self._smooth_slider.ToolTip = "Smoothing passes (0 = none, 5 = maximum)"
        self._smooth_slider.ValueChanged += self._on_smooth_changed

        self._smooth_value_label = ef.Label()
        self._smooth_value_label.Text = "2"
        self._smooth_value_label.ToolTip = "Current smoothing passes value"

        smooth_row.BeginHorizontal()
        smooth_row.Add(self._smooth_slider, xscale=True)
        smooth_row.Add(self._smooth_value_label)
        smooth_row.EndHorizontal()
        layout.Add(smooth_row)

        layout.AddSpace()

        # Extract Plantar Surface button
        btn_extract = ef.Button()
        btn_extract.Text = "Extract Plantar Surface"
        btn_extract.ToolTip = (
            "Extract a NURBS surface from the plantar (bottom) region "
            "of the foot scan mesh using ray-grid intersection."
        )
        btn_extract.Click += self._on_extract_plantar_click
        layout.Add(btn_extract)

        layout.AddSpace()

        # Extraction result status label (read-only)
        self._extraction_label = ef.Label()
        self._extraction_label.Text = "Extraction: Not run"
        self._extraction_label.ToolTip = (
            "Shows the result of the last plantar surface extraction."
        )
        layout.Add(self._extraction_label)

        layout.AddSpace()

        page.Content = layout
        return page

    def _on_import_scan_click(self, sender, e):
        """Handle Import Scan button click."""
        Rhino.RhinoApp.RunScript("OT_ImportScan", False)
        import state
        if state.foot_scan_filename:
            self.update_scan_label(state.foot_scan_filename)

    def _on_orient_scan_click(self, sender, e):
        """Handle Auto-Orient button click."""
        Rhino.RhinoApp.RunScript("OT_OrientScan", False)

    def _on_smooth_changed(self, sender, e):
        """Update the smoothing value display label."""
        self._smooth_value_label.Text = str(self._smooth_slider.Value)

    def _on_extract_plantar_click(self, sender, e):
        """Handle Extract Plantar Surface button click."""
        Rhino.RhinoApp.RunScript("OT_ExtractPlantar", False)
        import state
        if state.insole_top_surface is not None:
            self._extraction_label.Text = "Extraction: Success"
            self._extraction_label.TextColor = ed.SystemColors.ControlText
        else:
            self._extraction_label.Text = "Extraction: Failed"
            self._extraction_label.TextColor = ed.Color.FromArgb(220, 0, 0)

    def get_smoothing_passes(self):
        """Return the current smoothing slider value."""
        try:
            return self._smooth_slider.Value
        except Exception:
            return 2

    def update_extraction_label(self, message):
        """Update the extraction result status label."""
        self._extraction_label.Text = "Extraction: {}".format(message)
        self._extraction_label.TextColor = ed.SystemColors.ControlText

    def _create_tab_page(self, title, description):
        """Create a single tab page with description label and placeholder button."""
        page = ef.TabPage()
        page.Text = title

        layout = ef.DynamicLayout()
        layout.DefaultSpacing = ed.Size(5, 5)
        layout.DefaultPadding = ed.Padding(8)

        # Descriptive label at the top
        desc_label = ef.Label()
        desc_label.Text = description
        desc_label.Wrap = ef.WrapMode.Word
        desc_label.ToolTip = "Description of the {} tab functionality.".format(title)
        layout.Add(desc_label)

        layout.AddSpace()

        # Placeholder button
        btn = ef.Button()
        btn.Text = "Coming Soon"
        btn.ToolTip = (
            "{} tools will be added in a future session. "
            "This button is a placeholder.".format(title)
        )
        btn.Enabled = False
        layout.Add(btn)

        layout.AddSpace()

        page.Content = layout
        return page

    def _create_status_bar(self):
        """Create the status bar with Active Last, Scan labels, and Select Last button."""
        status_layout = ef.DynamicLayout()
        status_layout.DefaultSpacing = ed.Size(5, 3)
        status_layout.DefaultPadding = ed.Padding(5, 3)

        # Separator line
        separator = ef.Label()
        separator.Text = "─" * 40
        separator.TextColor = ed.Colors.Gray
        separator.ToolTip = "Status bar separator"
        status_layout.Add(separator)

        # Active Last label
        self._last_label = ef.Label()
        self._last_label.Text = "Active Last: None"
        self._last_label.ToolTip = (
            "Shows the name of the currently selected shoe last. "
            "Use 'Select Last' to pick a shoe last from the viewport."
        )
        status_layout.Add(self._last_label)

        # Scan label
        self._scan_label = ef.Label()
        self._scan_label.Text = "Scan: None"
        self._scan_label.ToolTip = (
            "Shows the filename of the currently imported foot scan mesh."
        )
        status_layout.Add(self._scan_label)

        # Select Last button
        self._select_last_btn = ef.Button()
        self._select_last_btn.Text = "Select Last"
        self._select_last_btn.ToolTip = (
            "Select a shoe last polysurface from the Rhino viewport. "
            "The plugin will detect the sole face and create the "
            "inverse sole surface for insole design."
        )
        self._select_last_btn.Click += self._on_select_last_click
        status_layout.Add(self._select_last_btn)

        return status_layout

    def _on_select_last_click(self, sender, e):
        """Handle the Select Last button click by running OT_SetLast."""
        import state

        Rhino.RhinoApp.RunScript("OT_SetLast", False)

        # After the command completes, refresh the label from state
        if state.active_last_name:
            self.update_last_label(state.active_last_name)
        else:
            # Command may have failed -- check if state is still empty
            if state.active_last_brep is None:
                self.show_last_error()

    def update_last_label(self, name):
        """Update the Active Last status label."""
        if name:
            self._last_label.Text = "Active Last: {}".format(name)
            self._last_label.TextColor = ed.SystemColors.ControlText
        else:
            self._last_label.Text = "Active Last: None"
            self._last_label.TextColor = ed.SystemColors.ControlText

    def show_last_error(self):
        """Show the Active Last label in red to indicate an error."""
        self._last_label.Text = "Active Last: ERROR -- see command line"
        self._last_label.TextColor = ed.Color.FromArgb(220, 0, 0)

    def update_scan_label(self, filename):
        """Update the Scan status label."""
        if filename:
            self._scan_label.Text = "Scan: {}".format(filename)
        else:
            self._scan_label.Text = "Scan: None"

    def reset_labels(self):
        """Reset all status labels to defaults."""
        self.update_last_label(None)
        self.update_scan_label(None)
