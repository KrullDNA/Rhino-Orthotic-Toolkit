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

        # Session 4 tabs: Outline, Arch, Heel Cup, Forefoot, Posting
        outline_page = self._create_outline_tab()
        self._tab_control.Pages.Add(outline_page)

        arch_page = self._create_arch_tab()
        self._tab_control.Pages.Add(arch_page)

        heelcup_page = self._create_heelcup_tab()
        self._tab_control.Pages.Add(heelcup_page)

        forefoot_page = self._create_forefoot_tab()
        self._tab_control.Pages.Add(forefoot_page)

        posting_page = self._create_posting_tab()
        self._tab_control.Pages.Add(posting_page)

        # Session 5 tabs: Thickness, Export
        thickness_page = self._create_thickness_tab()
        self._tab_control.Pages.Add(thickness_page)

        export_page = self._create_export_tab()
        self._tab_control.Pages.Add(export_page)

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

    # --- Warning label infrastructure ---

    def _make_warning_label(self):
        """Create a hidden amber warning label for a tab."""
        lbl = ef.Label()
        lbl.Text = ""
        lbl.TextColor = ed.Color.FromArgb(200, 150, 0)
        lbl.Wrap = ef.WrapMode.Word
        lbl.Visible = False
        lbl.ToolTip = "Warning message from the last operation."
        return lbl

    def show_tab_warning(self, tab_name, message):
        """Show an amber warning label on the specified tab."""
        key = "_warn_{}".format(tab_name.lower().replace(" ", "_"))
        lbl = getattr(self, key, None)
        if lbl is not None:
            lbl.Text = message
            lbl.Visible = True

    def _clear_tab_warning(self, tab_name):
        """Hide the warning label on the specified tab."""
        key = "_warn_{}".format(tab_name.lower().replace(" ", "_"))
        lbl = getattr(self, key, None)
        if lbl is not None:
            lbl.Text = ""
            lbl.Visible = False

    # --- Helper: slider row with value label ---

    def _make_slider_row(self, attr_name, min_val, max_val, default, step,
                         tooltip, fmt="{:.1f}"):
        """Create a slider + value label row. Returns (row_layout, slider, label)."""
        row = ef.DynamicLayout()
        row.DefaultSpacing = ed.Size(5, 0)

        # For integer-range sliders, map float to int range 0..steps
        steps = int(round((max_val - min_val) / step)) if step > 0 else 100
        default_tick = int(round((default - min_val) / step)) if step > 0 else 50

        slider = ef.Slider()
        slider.MinValue = 0
        slider.MaxValue = steps
        slider.Value = default_tick
        slider.ToolTip = tooltip

        val_label = ef.Label()
        val_label.Text = fmt.format(default)
        val_label.ToolTip = "Current value"

        def on_change(s, e):
            val = min_val + slider.Value * step
            val_label.Text = fmt.format(val)

        slider.ValueChanged += on_change

        row.BeginHorizontal()
        row.Add(slider, xscale=True)
        row.Add(val_label)
        row.EndHorizontal()

        # Store references for later retrieval
        setattr(self, "_slider_" + attr_name, slider)
        setattr(self, "_slbl_" + attr_name, val_label)
        setattr(self, "_smeta_" + attr_name, (min_val, step, fmt))

        return row

    def _get_slider_value(self, attr_name):
        """Read the current value from a named slider."""
        slider = getattr(self, "_slider_" + attr_name, None)
        meta = getattr(self, "_smeta_" + attr_name, None)
        if slider is not None and meta is not None:
            min_val, step, _ = meta
            return min_val + slider.Value * step
        return None

    # --- Outline tab ---

    def _create_outline_tab(self):
        page = ef.TabPage()
        page.Text = "Outline"

        layout = ef.DynamicLayout()
        layout.DefaultSpacing = ed.Size(5, 5)
        layout.DefaultPadding = ed.Padding(8)

        desc = ef.Label()
        desc.Text = TAB_DEFINITIONS[1][1]
        desc.Wrap = ef.WrapMode.Word
        desc.ToolTip = "Description of the Outline tab functionality."
        layout.Add(desc)

        self._warn_outline = self._make_warning_label()
        layout.Add(self._warn_outline)

        layout.AddSpace()

        lbl1 = ef.Label()
        lbl1.Text = "Perimeter Offset (mm):"
        lbl1.ToolTip = "Inward offset from the footprint curve."
        layout.Add(lbl1)
        layout.Add(self._make_slider_row(
            "perimeter_offset", 0.0, 10.0, 2.0, 0.5,
            "Perimeter offset in mm (0 - 10)"
        ))

        lbl2 = ef.Label()
        lbl2.Text = "Toe Extension (mm):"
        lbl2.ToolTip = "Extend the outline beyond the toe region."
        layout.Add(lbl2)
        layout.Add(self._make_slider_row(
            "toe_extension", 0.0, 20.0, 0.0, 0.5,
            "Toe extension in mm (0 - 20)"
        ))

        lbl3 = ef.Label()
        lbl3.Text = "Heel Extension (mm):"
        lbl3.ToolTip = "Extend the outline beyond the heel region."
        layout.Add(lbl3)
        layout.Add(self._make_slider_row(
            "heel_extension", 0.0, 20.0, 0.0, 0.5,
            "Heel extension in mm (0 - 20)"
        ))

        layout.AddSpace()

        btn = ef.Button()
        btn.Text = "Generate Outline"
        btn.ToolTip = "Generate the insole outline and initial flat Brep."
        btn.Click += self._on_generate_outline
        layout.Add(btn)

        layout.AddSpace()
        page.Content = layout
        return page

    def _on_generate_outline(self, sender, e):
        self._clear_tab_warning("Outline")
        Rhino.RhinoApp.RunScript("OT_GenerateOutline", False)

    def get_outline_params(self):
        return (
            self._get_slider_value("perimeter_offset") or 2.0,
            self._get_slider_value("toe_extension") or 0.0,
            self._get_slider_value("heel_extension") or 0.0,
        )

    # --- Arch tab ---

    def _create_arch_tab(self):
        page = ef.TabPage()
        page.Text = "Arch"

        layout = ef.DynamicLayout()
        layout.DefaultSpacing = ed.Size(5, 5)
        layout.DefaultPadding = ed.Padding(8)

        desc = ef.Label()
        desc.Text = TAB_DEFINITIONS[2][1]
        desc.Wrap = ef.WrapMode.Word
        desc.ToolTip = "Description of the Arch tab functionality."
        layout.Add(desc)

        self._warn_arch = self._make_warning_label()
        layout.Add(self._warn_arch)

        layout.AddSpace()

        lbl1 = ef.Label()
        lbl1.Text = "Arch Height (mm):"
        lbl1.ToolTip = "Maximum height of the medial arch support."
        layout.Add(lbl1)
        layout.Add(self._make_slider_row(
            "arch_height", 0.0, 30.0, 10.0, 0.5,
            "Arch height in mm (0 - 30)"
        ))

        lbl2 = ef.Label()
        lbl2.Text = "Apex Position (%):"
        lbl2.ToolTip = "Position of the arch apex as % along the arch."
        layout.Add(lbl2)
        layout.Add(self._make_slider_row(
            "arch_apex", 20.0, 80.0, 50.0, 1.0,
            "Apex position percentage (20 - 80)", fmt="{:.0f}"
        ))

        lbl3 = ef.Label()
        lbl3.Text = "Arch Width (mm):"
        lbl3.ToolTip = "Width of the arch support."
        layout.Add(lbl3)
        layout.Add(self._make_slider_row(
            "arch_width", 5.0, 40.0, 20.0, 0.5,
            "Arch width in mm (5 - 40)"
        ))

        lbl4 = ef.Label()
        lbl4.Text = "Blend Radius (mm):"
        lbl4.ToolTip = "Fillet radius for blending the arch into the insole."
        layout.Add(lbl4)
        layout.Add(self._make_slider_row(
            "arch_blend", 0.0, 10.0, 3.0, 0.5,
            "Blend fillet radius in mm (0 - 10)"
        ))

        layout.AddSpace()

        btn = ef.Button()
        btn.Text = "Apply Arch"
        btn.ToolTip = "Add medial arch support to the insole."
        btn.Click += self._on_add_arch
        layout.Add(btn)

        layout.AddSpace()
        page.Content = layout
        return page

    def _on_add_arch(self, sender, e):
        self._clear_tab_warning("Arch")
        Rhino.RhinoApp.RunScript("OT_AddArch", False)

    def get_arch_params(self):
        return (
            self._get_slider_value("arch_height") or 10.0,
            self._get_slider_value("arch_apex") or 50.0,
            self._get_slider_value("arch_width") or 20.0,
            self._get_slider_value("arch_blend") or 3.0,
        )

    # --- Heel Cup tab ---

    def _create_heelcup_tab(self):
        page = ef.TabPage()
        page.Text = "Heel Cup"

        layout = ef.DynamicLayout()
        layout.DefaultSpacing = ed.Size(5, 5)
        layout.DefaultPadding = ed.Padding(8)

        desc = ef.Label()
        desc.Text = TAB_DEFINITIONS[3][1]
        desc.Wrap = ef.WrapMode.Word
        desc.ToolTip = "Description of the Heel Cup tab functionality."
        layout.Add(desc)

        self._warn_heel_cup = self._make_warning_label()
        layout.Add(self._warn_heel_cup)

        layout.AddSpace()

        lbl1 = ef.Label()
        lbl1.Text = "Cup Depth (mm):"
        lbl1.ToolTip = "Depth of the heel cup walls."
        layout.Add(lbl1)
        layout.Add(self._make_slider_row(
            "cup_depth", 0.0, 30.0, 12.0, 0.5,
            "Heel cup depth in mm (0 - 30)"
        ))

        lbl2 = ef.Label()
        lbl2.Text = "Posterior Angle (deg):"
        lbl2.ToolTip = "Angle of the posterior (back) wall."
        layout.Add(lbl2)
        layout.Add(self._make_slider_row(
            "posterior_angle", 60.0, 120.0, 90.0, 1.0,
            "Posterior wall angle in degrees (60 - 120)", fmt="{:.0f}"
        ))

        lbl3 = ef.Label()
        lbl3.Text = "Lateral Flare (deg):"
        lbl3.ToolTip = "Outward flare angle of the lateral wall."
        layout.Add(lbl3)
        layout.Add(self._make_slider_row(
            "lateral_flare", 0.0, 30.0, 10.0, 1.0,
            "Lateral flare angle in degrees (0 - 30)", fmt="{:.0f}"
        ))

        lbl4 = ef.Label()
        lbl4.Text = "Medial Flare (deg):"
        lbl4.ToolTip = "Outward flare angle of the medial wall."
        layout.Add(lbl4)
        layout.Add(self._make_slider_row(
            "medial_flare", 0.0, 30.0, 10.0, 1.0,
            "Medial flare angle in degrees (0 - 30)", fmt="{:.0f}"
        ))

        lbl5 = ef.Label()
        lbl5.Text = "Cup Width (%):"
        lbl5.ToolTip = "Cup width as percentage of heel width."
        layout.Add(lbl5)
        layout.Add(self._make_slider_row(
            "cup_width_pct", 50.0, 150.0, 100.0, 5.0,
            "Cup width percentage (50 - 150)", fmt="{:.0f}"
        ))

        layout.AddSpace()

        btn = ef.Button()
        btn.Text = "Apply Heel Cup"
        btn.ToolTip = "Add heel cup to the insole."
        btn.Click += self._on_add_heelcup
        layout.Add(btn)

        layout.AddSpace()
        page.Content = layout
        return page

    def _on_add_heelcup(self, sender, e):
        self._clear_tab_warning("Heel Cup")
        Rhino.RhinoApp.RunScript("OT_AddHeelCup", False)

    def get_heelcup_params(self):
        return (
            self._get_slider_value("cup_depth") or 12.0,
            self._get_slider_value("posterior_angle") or 90.0,
            self._get_slider_value("lateral_flare") or 10.0,
            self._get_slider_value("medial_flare") or 10.0,
            self._get_slider_value("cup_width_pct") or 100.0,
        )

    # --- Forefoot (Met Dome) tab ---

    def _create_forefoot_tab(self):
        page = ef.TabPage()
        page.Text = "Forefoot"

        layout = ef.DynamicLayout()
        layout.DefaultSpacing = ed.Size(5, 5)
        layout.DefaultPadding = ed.Padding(8)

        desc = ef.Label()
        desc.Text = TAB_DEFINITIONS[4][1]
        desc.Wrap = ef.WrapMode.Word
        desc.ToolTip = "Description of the Forefoot tab functionality."
        layout.Add(desc)

        self._warn_forefoot = self._make_warning_label()
        layout.Add(self._warn_forefoot)

        layout.AddSpace()

        lbl1 = ef.Label()
        lbl1.Text = "Dome Count:"
        lbl1.ToolTip = "Number of metatarsal domes to add."
        layout.Add(lbl1)
        layout.Add(self._make_slider_row(
            "dome_count", 1, 5, 1, 1,
            "Number of metatarsal domes (1 - 5)", fmt="{:.0f}"
        ))

        lbl2 = ef.Label()
        lbl2.Text = "Dome Height (mm):"
        lbl2.ToolTip = "Height of each metatarsal dome."
        layout.Add(lbl2)
        layout.Add(self._make_slider_row(
            "dome_height", 1.0, 15.0, 5.0, 0.5,
            "Dome height in mm (1 - 15)"
        ))

        lbl3 = ef.Label()
        lbl3.Text = "Dome Diameter (mm):"
        lbl3.ToolTip = "Diameter of each metatarsal dome."
        layout.Add(lbl3)
        layout.Add(self._make_slider_row(
            "dome_diameter", 5.0, 30.0, 10.0, 0.5,
            "Dome diameter in mm (5 - 30)"
        ))

        layout.AddSpace()

        btn = ef.Button()
        btn.Text = "Apply Met Domes"
        btn.ToolTip = "Add metatarsal dome pads to the forefoot region."
        btn.Click += self._on_add_metdome
        layout.Add(btn)

        layout.AddSpace()
        page.Content = layout
        return page

    def _on_add_metdome(self, sender, e):
        self._clear_tab_warning("Forefoot")
        Rhino.RhinoApp.RunScript("OT_AddMetDome", False)

    def get_metdome_params(self):
        count = int(self._get_slider_value("dome_count") or 1)
        height = self._get_slider_value("dome_height") or 5.0
        diameter = self._get_slider_value("dome_diameter") or 10.0
        # Auto-generate positions using the count, height, diameter
        positions = []
        for i in range(count):
            if count == 1:
                x_pct = 50.0
            else:
                x_pct = 25.0 + (50.0 * i / (count - 1))
            positions.append((x_pct, 75.0, height, diameter))
        return count, positions

    # --- Posting tab ---

    def _create_posting_tab(self):
        page = ef.TabPage()
        page.Text = "Posting"

        layout = ef.DynamicLayout()
        layout.DefaultSpacing = ed.Size(5, 5)
        layout.DefaultPadding = ed.Padding(8)

        desc = ef.Label()
        desc.Text = TAB_DEFINITIONS[5][1]
        desc.Wrap = ef.WrapMode.Word
        desc.ToolTip = "Description of the Posting tab functionality."
        layout.Add(desc)

        self._warn_posting = self._make_warning_label()
        layout.Add(self._warn_posting)

        layout.AddSpace()

        lbl1 = ef.Label()
        lbl1.Text = "RF Medial (deg):"
        lbl1.ToolTip = "Rearfoot medial posting angle."
        layout.Add(lbl1)
        layout.Add(self._make_slider_row(
            "rf_medial", 0.0, 15.0, 0.0, 0.5,
            "Rearfoot medial posting angle (0 - 15)"
        ))

        lbl2 = ef.Label()
        lbl2.Text = "RF Lateral (deg):"
        lbl2.ToolTip = "Rearfoot lateral posting angle."
        layout.Add(lbl2)
        layout.Add(self._make_slider_row(
            "rf_lateral", 0.0, 15.0, 0.0, 0.5,
            "Rearfoot lateral posting angle (0 - 15)"
        ))

        lbl3 = ef.Label()
        lbl3.Text = "FF Medial (deg):"
        lbl3.ToolTip = "Forefoot medial posting angle."
        layout.Add(lbl3)
        layout.Add(self._make_slider_row(
            "ff_medial", 0.0, 15.0, 0.0, 0.5,
            "Forefoot medial posting angle (0 - 15)"
        ))

        lbl4 = ef.Label()
        lbl4.Text = "FF Lateral (deg):"
        lbl4.ToolTip = "Forefoot lateral posting angle."
        layout.Add(lbl4)
        layout.Add(self._make_slider_row(
            "ff_lateral", 0.0, 15.0, 0.0, 0.5,
            "Forefoot lateral posting angle (0 - 15)"
        ))

        lbl5 = ef.Label()
        lbl5.Text = "RF/FF Split (%):"
        lbl5.ToolTip = "Rearfoot/forefoot split position as percentage."
        layout.Add(lbl5)
        layout.Add(self._make_slider_row(
            "split_pct", 30.0, 70.0, 50.0, 1.0,
            "RF/FF split percentage (30 - 70)", fmt="{:.0f}"
        ))

        layout.AddSpace()

        btn = ef.Button()
        btn.Text = "Apply Posting"
        btn.ToolTip = "Add rearfoot and forefoot posting wedges."
        btn.Click += self._on_add_posting
        layout.Add(btn)

        layout.AddSpace()
        page.Content = layout
        return page

    def _on_add_posting(self, sender, e):
        self._clear_tab_warning("Posting")
        Rhino.RhinoApp.RunScript("OT_AddPosting", False)

    def get_posting_params(self):
        return (
            self._get_slider_value("rf_medial") or 0.0,
            self._get_slider_value("rf_lateral") or 0.0,
            self._get_slider_value("ff_medial") or 0.0,
            self._get_slider_value("ff_lateral") or 0.0,
            self._get_slider_value("split_pct") or 50.0,
        )

    # --- Thickness tab ---

    def _create_thickness_tab(self):
        page = ef.TabPage()
        page.Text = "Thickness"

        layout = ef.DynamicLayout()
        layout.DefaultSpacing = ed.Size(5, 5)
        layout.DefaultPadding = ed.Padding(8)

        desc = ef.Label()
        desc.Text = TAB_DEFINITIONS[6][1]
        desc.Wrap = ef.WrapMode.Word
        desc.ToolTip = "Description of the Thickness tab functionality."
        layout.Add(desc)

        self._warn_thickness = self._make_warning_label()
        layout.Add(self._warn_thickness)

        layout.AddSpace()

        # Cover thickness
        lbl1 = ef.Label()
        lbl1.Text = "Cover Thickness (mm):"
        lbl1.ToolTip = (
            "Thickness of the top cover layer. Typically 1.5-2.5mm "
            "for a cushioning top cover material."
        )
        layout.Add(lbl1)

        self._cover_stepper = ef.NumericStepper()
        self._cover_stepper.MinValue = 0.5
        self._cover_stepper.MaxValue = 4.0
        self._cover_stepper.Increment = 0.5
        self._cover_stepper.DecimalPlaces = 1
        self._cover_stepper.Value = 2.0
        self._cover_stepper.ToolTip = "Cover layer thickness in mm (0.5 - 4.0)"
        self._cover_stepper.ValueChanged += self._on_thickness_changed
        layout.Add(self._cover_stepper)

        # Shell thickness
        lbl2 = ef.Label()
        lbl2.Text = "Shell Thickness (mm):"
        lbl2.ToolTip = (
            "Thickness of the rigid shell layer. Controls arch support "
            "stiffness. 2-4mm for flexible, 4-6mm for rigid."
        )
        layout.Add(lbl2)

        self._shell_stepper = ef.NumericStepper()
        self._shell_stepper.MinValue = 1.0
        self._shell_stepper.MaxValue = 6.0
        self._shell_stepper.Increment = 0.5
        self._shell_stepper.DecimalPlaces = 1
        self._shell_stepper.Value = 3.0
        self._shell_stepper.ToolTip = "Shell layer thickness in mm (1.0 - 6.0)"
        self._shell_stepper.ValueChanged += self._on_thickness_changed
        layout.Add(self._shell_stepper)

        # Base thickness
        lbl3 = ef.Label()
        lbl3.Text = "Base Thickness (mm):"
        lbl3.ToolTip = (
            "Thickness of the bottom base layer. Provides cushioning "
            "and shock absorption. 3-8mm typical range."
        )
        layout.Add(lbl3)

        self._base_stepper = ef.NumericStepper()
        self._base_stepper.MinValue = 1.0
        self._base_stepper.MaxValue = 8.0
        self._base_stepper.Increment = 0.5
        self._base_stepper.DecimalPlaces = 1
        self._base_stepper.Value = 5.0
        self._base_stepper.ToolTip = "Base layer thickness in mm (1.0 - 8.0)"
        self._base_stepper.ValueChanged += self._on_thickness_changed
        layout.Add(self._base_stepper)

        layout.AddSpace()

        # Total thickness read-only label
        self._total_thickness_label = ef.Label()
        self._total_thickness_label.Text = "Total: 10.0mm"
        self._total_thickness_label.Font = ed.SystemFonts.Bold()
        self._total_thickness_label.ToolTip = (
            "Combined thickness of all three layers. "
            "Typical insoles range from 6mm to 15mm total."
        )
        layout.Add(self._total_thickness_label)

        layout.AddSpace()

        # Apply Thickness button
        btn_apply = ef.Button()
        btn_apply.Text = "Apply Thickness"
        btn_apply.ToolTip = (
            "Build the three thickness layers (cover, shell, base) "
            "and check for minimum thickness violations."
        )
        btn_apply.Click += self._on_apply_thickness
        layout.Add(btn_apply)

        # Run Validation button
        btn_validate = ef.Button()
        btn_validate.Text = "Run Validation"
        btn_validate.ToolTip = (
            "Run a full validation check on the insole Brep. "
            "Checks validity, solidity, thickness, and overhangs."
        )
        btn_validate.Click += self._on_run_validation
        layout.Add(btn_validate)

        layout.AddSpace()
        page.Content = layout
        return page

    def _on_thickness_changed(self, sender, e):
        """Update the total thickness label when any stepper changes."""
        try:
            total = (
                self._cover_stepper.Value
                + self._shell_stepper.Value
                + self._base_stepper.Value
            )
            self._total_thickness_label.Text = "Total: {:.1f}mm".format(total)
        except Exception:
            pass

    def _on_apply_thickness(self, sender, e):
        self._clear_tab_warning("Thickness")
        Rhino.RhinoApp.RunScript("OT_SetThickness", False)

    def _on_run_validation(self, sender, e):
        Rhino.RhinoApp.RunScript("OT_ValidateInsole", False)

    def get_thickness_params(self):
        try:
            return (
                self._cover_stepper.Value,
                self._shell_stepper.Value,
                self._base_stepper.Value,
            )
        except Exception:
            return 2.0, 3.0, 5.0

    def update_total_thickness(self, total):
        """Update the total thickness label externally."""
        try:
            self._total_thickness_label.Text = "Total: {:.1f}mm".format(total)
        except Exception:
            pass

    # --- Export tab ---

    def _create_export_tab(self):
        page = ef.TabPage()
        page.Text = "Export"

        layout = ef.DynamicLayout()
        layout.DefaultSpacing = ed.Size(5, 5)
        layout.DefaultPadding = ed.Padding(8)

        desc = ef.Label()
        desc.Text = TAB_DEFINITIONS[7][1]
        desc.Wrap = ef.WrapMode.Word
        desc.ToolTip = "Description of the Export tab functionality."
        layout.Add(desc)

        self._warn_export = self._make_warning_label()
        layout.Add(self._warn_export)

        layout.AddSpace()

        # Format dropdown
        lbl1 = ef.Label()
        lbl1.Text = "Export Format:"
        lbl1.ToolTip = "Select the file format for export."
        layout.Add(lbl1)

        self._format_dropdown = ef.DropDown()
        self._format_dropdown.Items.Add(
            ef.ListItem(Text="STL", Key="STL")
        )
        self._format_dropdown.Items.Add(
            ef.ListItem(Text="STEP", Key="STEP")
        )
        self._format_dropdown.Items.Add(
            ef.ListItem(Text="OBJ", Key="OBJ")
        )
        self._format_dropdown.Items.Add(
            ef.ListItem(Text="3DM", Key="3DM")
        )
        self._format_dropdown.SelectedIndex = 0
        self._format_dropdown.ToolTip = (
            "STL: Universal mesh format for 3D printing. "
            "STEP: Solid format for CNC and CAD interchange. "
            "OBJ: Mesh format with material support. "
            "3DM: Native Rhino format preserving NURBS data."
        )
        layout.Add(self._format_dropdown)

        layout.AddSpace()

        # Mesh resolution dropdown
        lbl2 = ef.Label()
        lbl2.Text = "Mesh Resolution:"
        lbl2.ToolTip = (
            "Controls mesh density for STL/OBJ export. "
            "Higher resolution = larger file, smoother surfaces."
        )
        layout.Add(lbl2)

        self._resolution_dropdown = ef.DropDown()
        self._resolution_dropdown.Items.Add(
            ef.ListItem(Text="Draft (0.5mm)", Key="0.5")
        )
        self._resolution_dropdown.Items.Add(
            ef.ListItem(Text="Standard (0.2mm)", Key="0.2")
        )
        self._resolution_dropdown.Items.Add(
            ef.ListItem(Text="Fine (0.1mm)", Key="0.1")
        )
        self._resolution_dropdown.Items.Add(
            ef.ListItem(Text="Ultra (0.05mm)", Key="0.05")
        )
        self._resolution_dropdown.SelectedIndex = 2  # Fine by default
        self._resolution_dropdown.ToolTip = (
            "Chord tolerance for meshing. Smaller values produce "
            "smoother but larger mesh files. Fine (0.1mm) recommended "
            "for SLA printing, Draft for quick previews."
        )
        layout.Add(self._resolution_dropdown)

        layout.AddSpace()

        # Export mode radio buttons
        lbl3 = ef.Label()
        lbl3.Text = "Export Mode:"
        lbl3.ToolTip = "Choose whether to export as a single piece or separate layers."
        layout.Add(lbl3)

        self._export_single_radio = ef.RadioButton()
        self._export_single_radio.Text = "Export Single Piece"
        self._export_single_radio.Checked = True
        self._export_single_radio.ToolTip = (
            "Export the entire insole as one solid piece. "
            "Use for single-material 3D printing or CNC milling."
        )
        layout.Add(self._export_single_radio)

        self._export_layer_radio = ef.RadioButton(self._export_single_radio)
        self._export_layer_radio.Text = "Export by Layer"
        self._export_layer_radio.ToolTip = (
            "Export cover, shell, and base as separate files "
            "with _cover, _shell, _base suffixes. Use for "
            "multi-material or bilayer EVA milling."
        )
        layout.Add(self._export_layer_radio)

        layout.AddSpace()

        # Include Rocker Outline checkbox
        self._rocker_checkbox = ef.CheckBox()
        self._rocker_checkbox.Text = "Include Rocker Outline"
        self._rocker_checkbox.Checked = False
        self._rocker_checkbox.ToolTip = (
            "Generate and include the rocker-bottom contact outline "
            "curve in the export. The curve shows the flat contact "
            "zone for rocker-bottom shoe design."
        )
        layout.Add(self._rocker_checkbox)

        layout.AddSpace()

        # Export button
        btn_export = ef.Button()
        btn_export.Text = "Export..."
        btn_export.ToolTip = (
            "Validate and export the insole in the selected format. "
            "A save dialog will appear to choose the output location."
        )
        btn_export.Click += self._on_export_click
        layout.Add(btn_export)

        layout.AddSpace()
        page.Content = layout
        return page

    def _on_export_click(self, sender, e):
        self._clear_tab_warning("Export")
        Rhino.RhinoApp.RunScript("OT_ExportInsole", False)

    def get_export_params(self):
        """Return (format, mesh_tolerance, export_by_layer, include_rocker)."""
        try:
            # Format
            fmt_idx = self._format_dropdown.SelectedIndex
            formats = ["STL", "STEP", "OBJ", "3DM"]
            fmt = formats[fmt_idx] if 0 <= fmt_idx < len(formats) else "STL"

            # Mesh tolerance
            res_idx = self._resolution_dropdown.SelectedIndex
            tolerances = [0.5, 0.2, 0.1, 0.05]
            mesh_tol = tolerances[res_idx] if 0 <= res_idx < len(tolerances) else 0.1

            # Export mode
            by_layer = self._export_layer_radio.Checked

            # Rocker
            include_rocker = self._rocker_checkbox.Checked

            return fmt, mesh_tol, by_layer, include_rocker
        except Exception:
            return "STL", 0.1, False, False

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
