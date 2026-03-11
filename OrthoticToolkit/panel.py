# -*- coding: utf-8 -*-
"""Orthotic Toolkit - Dockable Panel

OrthoticPanel is an Eto.Forms.Panel with eight tabs (one per tool group)
and a status bar at the bottom. All layouts use DynamicLayout with no
fixed pixel sizes.
"""

import Eto.Forms as ef
import Eto.Drawing as ed


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
        for title, description in TAB_DEFINITIONS:
            page = self._create_tab_page(title, description)
            self._tab_control.Pages.Add(page)

        main_layout.Add(self._tab_control, yscale=True)

        # Status bar at the bottom
        status_layout = self._create_status_bar()
        main_layout.Add(status_layout)

        self.Content = main_layout

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
            "This will be wired up in Session 2."
        )
        self._select_last_btn.Enabled = False  # Wired in Session 2
        status_layout.Add(self._select_last_btn)

        return status_layout

    def update_last_label(self, name):
        """Update the Active Last status label."""
        if name:
            self._last_label.Text = "Active Last: {}".format(name)
            self._last_label.TextColor = ed.SystemColors.ControlText
        else:
            self._last_label.Text = "Active Last: None"
            self._last_label.TextColor = ed.SystemColors.ControlText

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
