# -*- coding: utf-8 -*-
"""Orthotic Toolkit - Plugin State Module

All plugin state is stored as module-level variables.
Every variable listed in the project brief (Section 8.4) is included here.
Call reset_all() to restore all state to default values.
"""

# --- Shoe Last State ---
active_last_brep = None        # Brep polysurface of the selected shoe last
sole_face = None               # BrepFace identified as the sole
footprint_curve = None         # Closed curve projected to XY plane
insole_top_surface = None      # Inverse sole NURBS surface

# --- Foot Scan State ---
foot_scan_mesh = None          # Imported mesh from STL/OBJ/PLY
foot_scan_filename = None      # Original filename of imported scan

# --- Insole Geometry State ---
insole_outline = None          # Closed planar curve defining insole perimeter
insole_brep = None             # Current insole solid Brep (built up by tools)

# --- Thickness Layer State ---
cover_thickness_mm = 2.0       # Cover layer thickness in mm
shell_thickness_mm = 3.0       # Shell layer thickness in mm
base_thickness_mm = 5.0        # Base layer thickness in mm
layer_cover = None             # Brep for cover layer
layer_shell = None             # Brep for shell layer
layer_base = None              # Brep for base layer

# --- Outline Parameters ---
perimeter_offset = 2.0         # Perimeter offset in mm
toe_extension = 0.0            # Toe extension in mm
heel_extension = 0.0           # Heel extension in mm

# --- Arch Parameters ---
arch_height_mm = 10.0          # Arch height in mm
arch_apex_pct = 50.0           # Apex position as percentage along arch
arch_width_mm = 20.0           # Arch width in mm
arch_blend_radius = 3.0        # Blend fillet radius in mm

# --- Heel Cup Parameters ---
cup_depth_mm = 12.0            # Heel cup depth in mm
posterior_angle_deg = 90.0     # Posterior wall angle in degrees
lateral_flare_deg = 10.0       # Lateral flare angle in degrees
medial_flare_deg = 10.0        # Medial flare angle in degrees
cup_width_pct = 100.0          # Cup width as percentage of heel width

# --- Metatarsal Dome Parameters ---
dome_count = 1                 # Number of metatarsal domes
dome_positions = None          # List of (x_pct, y_pct, height_mm, diameter_mm)

# --- Posting Parameters ---
rf_medial_deg = 0.0            # Rearfoot medial posting angle
rf_lateral_deg = 0.0           # Rearfoot lateral posting angle
ff_medial_deg = 0.0            # Forefoot medial posting angle
ff_lateral_deg = 0.0           # Forefoot lateral posting angle
split_pct = 50.0               # Rearfoot/forefoot split percentage

# --- Export State ---
export_format = "STL"          # Current export format selection
mesh_tolerance = 0.1           # Mesh chord tolerance in mm
export_by_layer = False        # Export each layer as separate file
include_rocker = False         # Include rocker outline in export

# --- UI / Document Object References ---
active_last_name = None        # Display name of the selected last
preview_object_ids = []        # List of Guids for preview objects in document


def reset_all():
    """Reset all state variables back to None or their default values."""
    global active_last_brep, sole_face, footprint_curve, insole_top_surface
    global foot_scan_mesh, foot_scan_filename
    global insole_outline, insole_brep
    global cover_thickness_mm, shell_thickness_mm, base_thickness_mm
    global layer_cover, layer_shell, layer_base
    global perimeter_offset, toe_extension, heel_extension
    global arch_height_mm, arch_apex_pct, arch_width_mm, arch_blend_radius
    global cup_depth_mm, posterior_angle_deg, lateral_flare_deg
    global medial_flare_deg, cup_width_pct
    global dome_count, dome_positions
    global rf_medial_deg, rf_lateral_deg, ff_medial_deg, ff_lateral_deg, split_pct
    global export_format, mesh_tolerance, export_by_layer, include_rocker
    global active_last_name, preview_object_ids

    # Shoe Last
    active_last_brep = None
    sole_face = None
    footprint_curve = None
    insole_top_surface = None

    # Foot Scan
    foot_scan_mesh = None
    foot_scan_filename = None

    # Insole Geometry
    insole_outline = None
    insole_brep = None

    # Thickness Layers
    cover_thickness_mm = 2.0
    shell_thickness_mm = 3.0
    base_thickness_mm = 5.0
    layer_cover = None
    layer_shell = None
    layer_base = None

    # Outline Parameters
    perimeter_offset = 2.0
    toe_extension = 0.0
    heel_extension = 0.0

    # Arch Parameters
    arch_height_mm = 10.0
    arch_apex_pct = 50.0
    arch_width_mm = 20.0
    arch_blend_radius = 3.0

    # Heel Cup Parameters
    cup_depth_mm = 12.0
    posterior_angle_deg = 90.0
    lateral_flare_deg = 10.0
    medial_flare_deg = 10.0
    cup_width_pct = 100.0

    # Metatarsal Dome Parameters
    dome_count = 1
    dome_positions = None

    # Posting Parameters
    rf_medial_deg = 0.0
    rf_lateral_deg = 0.0
    ff_medial_deg = 0.0
    ff_lateral_deg = 0.0
    split_pct = 50.0

    # Export State
    export_format = "STL"
    mesh_tolerance = 0.1
    export_by_layer = False
    include_rocker = False

    # UI / Document References
    active_last_name = None
    preview_object_ids = []
