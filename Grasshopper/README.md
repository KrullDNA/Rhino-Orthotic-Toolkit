# Orthotic Toolkit — Grasshopper Build

Grasshopper port of the Rhino plugin in `../Rhino/`. Built so the insole rebuilds
live as you drag sliders; outputs are smooth NURBS curves with editable control
points and a SubD insole.

## Why Grasshopper

The Rhino .rhi build hits IronPython crashes on grip edits and the
display-conduit live preview. Grasshopper gives us:
- **Live updating** — every slider change re-runs the pipeline.
- **Real CP editing** — bake `TopEdge` / `BottomEdge` into the document, drag
  control points, then feed them back into `OverrideOutline` /
  `OverrideBottom` to override the auto-generated outline.
- **No state machine** — no global `state.py`, no command ordering issues.

## Files

```
Grasshopper/
├── README.md                                  ← this file
└── components/
    ├── 00_orthotic_insole_all_in_one.py       ← single-component pipeline (start here)
    ├── 01_extract_footprint.py
    ├── 02_detect_orientation.py
    ├── 03_build_outline.py
    ├── 04_build_insole_mesh.py
    └── 05_extract_edges_and_subd.py
```

## Quick start (single component)

1. In Grasshopper, drop a **GhPython Script** component.
2. Right-click each input/output and rename + set type as listed in the
   docstring of `00_orthotic_insole_all_in_one.py`. Inputs are item access
   except `Last`. Required type hints:
   - `Last` → `Brep`
   - `OverrideOutline`, `OverrideBottom` → `Curve`
   - everything else → `float` or `int`
3. Paste the contents of `00_orthotic_insole_all_in_one.py` into the editor.
4. Wire:
   - `Brep` param (referenced shoe last) → `Last`
   - Number sliders → `PerimeterOffset` (2.0), `ToeExtension` (0.0),
     `HeelExtension` (0.0), `CoverThk` (2.0), `ShellThk` (3.0),
     `BaseThk` (5.0)
5. Connect `SubD` to a SubD param to preview, and `TopEdge` / `BottomEdge`
   to Curve params.

Sliders update the SubD in real time.

## Modular setup (5 components)

Use the numbered files for a readable canvas:

```
[Brep:Last] ─┬─► (01 Footprint) ─┬─► (02 Orientation) ─┐
             │                   │                      │
             └────────────[Footprint]──────────► (03 Outline) ◄── [sliders]
                                                       │
                                            [Outline]  │
                                                       ▼
                       [sliders thk] ──► (04 InsoleMesh) ─► (05 EdgesSubD)
                                              ▲
                                       [Last]─┘
```

Inputs/outputs match the docstring at the top of each file.

## Editing the outline interactively

To reshape the insole by dragging control points:
1. Right-click `TopEdge` output → **Bake** (closed NURBS curve, 20 CPs).
2. In Rhino, turn on its grips and drag.
3. Reference the edited curve back in via a `Curve` param feeding
   `OverrideOutline` (all-in-one) or feeding component 04's `Outline` input
   directly.
4. Bottom edge: same flow with `BottomEdge` → `OverrideBottom`.

The override outline must be a closed planar curve in XY for the offset path,
or any curve flat in XY for the conforming-mesh path. The conforming step
will project each mesh vertex up onto the sole regardless of where the
outline came from.

## Parameter defaults (matches `Rhino/OrthoticToolkit/state.py`)

| Slider          | Default | Range          |
|-----------------|---------|----------------|
| PerimeterOffset | 2.0 mm  | 0.0 – 10.0 mm  |
| ToeExtension    | 0.0 mm  | -10.0 – 30.0   |
| HeelExtension   | 0.0 mm  | -10.0 – 30.0   |
| CoverThk        | 2.0 mm  | 0.5 – 10.0     |
| ShellThk        | 3.0 mm  | 0.5 – 15.0     |
| BaseThk         | 5.0 mm  | 0.5 – 20.0     |
| MaxEdge         | 3.0 mm  | 1.0 – 10.0     |
| MinEdge         | 1.0 mm  | 0.5 – 5.0      |
| RebuildCount    | 20      | 8 – 60         |

## Algorithm provenance

| Component | Source | Functions |
|-----------|--------|-----------|
| 01 Footprint | `Rhino/OrthoticToolkit/commands/cmd_setlast.py` | `_get_footprint_by_section` |
| 02 Orientation | same file | `_detect_orientation` |
| 03 Outline | `Rhino/OrthoticToolkit/commands/cmd_outline.py` | `_build_outline_curve` |
| 04 Mesh | same file | `_build_insole_mesh`, `_sole_z_at` |
| 05 Edges + SubD | same file | `_curves_from_boundary`, `SubD.CreateFromMesh` |

## Requirements

- Rhino 8 (Grasshopper 1.x with the GhPython 3 component, CPython 3 runtime)
- The shoe last must be roughly oriented with the sole facing -Z.
