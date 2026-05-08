# Grasshopper Beginner's Walkthrough — Orthotic Insole

Zero Grasshopper experience required. Follow each step in order. Estimated
time the first time: 20–30 minutes. After that, opening the file and moving
sliders takes seconds.

---

## 0. What is Grasshopper?

Grasshopper is a visual programming canvas that lives **inside Rhino**. You
drop "components" (boxes) and connect their outputs to other components'
inputs with wires. When you change a value, everything downstream rebuilds
automatically. That live-updating is exactly what we want for the insole.

You will not write any code. You'll **paste** Python code that I've already
written into a special "Python 3 Script" component.

---

## 1. Open Grasshopper

1. Open **Rhino 8**.
2. In the Rhino command line, type `Grasshopper` and press Enter.
3. A second window opens — that's the Grasshopper canvas. Keep both windows
   visible side by side.

The Grasshopper canvas has:
- A **ribbon** at the top with tabs (Params, Maths, Sets, Vector, Curve,
  Surface, Mesh, Intersect, Transform, Display, **Script**).
- A **blank canvas** below.

---

## 2. Reference your shoe last from Rhino

The shoe last lives in your Rhino document. We need to "reference" it into
Grasshopper.

1. In Rhino, **open the file containing your shoe last** (the polysurface or
   SubD you've been working with).
2. In Grasshopper, go to the **Params** tab → **Geometry** group → drag a
   **Brep** parameter onto the canvas. (It's an empty grey hexagon labelled
   `Brep`.)
3. **Right-click** the Brep parameter → **Set one Brep**.
4. Grasshopper hides itself and Rhino activates. Click your shoe last.
5. The Brep parameter on the canvas turns from grey to having a small
   preview indicator. Done — the last is now an input.

> If your last is a **SubD**, drop a `SubD` parameter from Params → Geometry
> instead, then add a **SubD to Brep** component (Surface → SubD → SubD to
> Brep) between it and the script. Convert once, you don't have to do it
> every session.

---

## 3. Drop the Python script component

1. **Double-click on the empty canvas** anywhere. A search box appears.
2. Type `python 3` and pick **Python 3 Script** (green/cyan icon, the one
   that says "CPython 3"). Press Enter.
3. A small component appears with default inputs `x` and `y` and output `a`.

This is the component we'll fill with the insole code.

---

## 4. Configure the script component's inputs

The all-in-one script needs 11 inputs. We'll add them one by one.

### 4a. Open the script editor

**Double-click** the `Python 3 Script` component. The script editor opens.

### 4b. Replace the default code

1. Select all the placeholder code in the editor (Ctrl+A) and delete it.
2. Open `Grasshopper/components/00_orthotic_insole_all_in_one.py` from this
   repo in any text editor.
3. Copy its **entire contents** and paste into the GH script editor.
4. Click **Test** (bottom of the editor) — you'll see errors about undefined
   names like `Last`, `PerimeterOffset`. That's expected — we haven't created
   the inputs yet. Click **OK** to close any error popup.
5. Close the editor (the X). The component now lives on the canvas with the
   pasted code.

### 4c. Add the inputs

The script component starts with two inputs (`x`, `y`). We need 11. Here's
how to add and rename them:

**To rename an input:**
- **Right-click on the input name** (e.g. `x` on the left side of the
  component) → choose **"x"** at the top → a text field appears → type the
  new name → press Enter.

**To add more inputs:**
- **Zoom in** on the component until you see small `+` and `−` icons next to
  the inputs. Click `+` to add an input.
- (Alternative: right-click the component header → **Add Input**.)

Rename and add until your component has these 11 inputs, top to bottom:

| Input name        | Type hint         | Access   |
|-------------------|-------------------|----------|
| `Last`            | Brep              | Item     |
| `PerimeterOffset` | float / Number    | Item     |
| `ToeExtension`    | float / Number    | Item     |
| `HeelExtension`   | float / Number    | Item     |
| `CoverThk`        | float / Number    | Item     |
| `ShellThk`        | float / Number    | Item     |
| `BaseThk`         | float / Number    | Item     |
| `OverrideOutline` | Curve             | Item     |
| `OverrideBottom`  | Curve             | Item     |
| `MaxEdge`         | float / Number    | Item     |
| `MinEdge`         | float / Number    | Item     |

(`RebuildCount` is optional — add it if you want to control curve smoothness;
otherwise default 20.)

**To set a type hint:**
- Right-click the input name → **Type hint** → pick from the list.
- Pick exactly one of these for each input:

| Input             | Type hint  |
|-------------------|------------|
| `Last`            | **Brep**   |
| `OverrideOutline` | **Curve**  |
| `OverrideBottom`  | **Curve**  |
| `PerimeterOffset` | **float**  |
| `ToeExtension`    | **float**  |
| `HeelExtension`   | **float**  |
| `CoverThk`        | **float**  |
| `ShellThk`        | **float**  |
| `BaseThk`         | **float**  |
| `MaxEdge`         | **float**  |
| `MinEdge`         | **float**  |
| `RebuildCount`    | **int**    |

If your GH version shows `Number` instead of `float`, pick that — same thing.

`RebuildCount` is optional. Leave it unwired and the script uses 20 (a good
default). Add it only if you want to tune how many control points the output
curves have — feed it from a slider like `20..8..60`.

**To set access:**
- Right-click the input name → **Access** → **Item Access**.

### 4d. Add the outputs

The default output is `a`. We need 8 outputs. Same procedure on the right
side:

| Output name |
|-------------|
| `SubD`      |
| `Mesh`      |
| `Footprint` |
| `Outline`   |
| `TopEdge`   |
| `BottomEdge`|
| `Axis`      |
| `ToeDir`    |

Outputs don't need type hints — Grasshopper figures them out.

---

## 5. Wire the shoe last in

1. Drag a wire from the **Brep** parameter (right-side circle) on the
   referenced last to the **Last** input (left-side circle) on the script
   component.
2. The script component now has the last as input. If you hover over the
   component, you'll see "Last: 1 Brep" in the tooltip.

If the script border is **red**, hover over it — Grasshopper will say what's
missing. Most likely: "PerimeterOffset is None" because we haven't wired
sliders yet. Continue.

---

## 6. Add number sliders

You need 6 sliders for the everyday parameters. Here's the fast way:

1. **Double-click empty canvas** → type `2..0..10` and press Enter.
   - This is shorthand: **default=2, min=0, max=10**. A slider drops onto
     the canvas pre-set.
2. **Right-click the slider** → **Edit** → change **Name** to
   `PerimeterOffset` (helpful when you have many sliders).
3. Drag a wire from the slider's right side to `PerimeterOffset` on the
   script.

Repeat for each slider:

| Slider name        | Shorthand to type  | Default |
|--------------------|--------------------|---------|
| PerimeterOffset    | `2..0..10`         | 2.0 mm  |
| ToeExtension       | `0..-10..30`       | 0.0 mm  |
| HeelExtension      | `0..-10..30`       | 0.0 mm  |
| CoverThk           | `2..0.5..10`       | 2.0 mm  |
| ShellThk           | `3..0.5..15`       | 3.0 mm  |
| BaseThk            | `5..0.5..20`       | 5.0 mm  |

For `MaxEdge` and `MinEdge`, leave them unwired — the script falls back to
defaults (3.0 and 1.0). Or add sliders if you want finer control.

---

## 7. Preview the SubD

1. The **SubD** output on the right of the script is what you want to see.
2. Right-click in empty canvas → search **SubD** → drop a `SubD` parameter.
3. Wire `SubD` output → the SubD parameter input.
4. The SubD parameter has a small icon showing the geometry preview is on
   (a grey/coloured bulb). If it's off, right-click the parameter → **Preview**.
5. Look at your Rhino viewport — the insole should now be visible as a blue
   SubD shape sitting on top of your shoe last.

If you don't see anything in Rhino:
- Check the script component isn't red. Hover for the error message.
- Make sure the Brep parameter is correctly referenced (right-click → "Set
  one Brep" again if needed).
- Ensure your shoe last is oriented sole-down (sole facing −Z).

---

## 8. Move sliders — this is the live updating

Drag the `PerimeterOffset` slider. The insole rebuilds every time you let
go (or in real time if you hold and drag — depends on your GH solver mode).

Try:
- `PerimeterOffset` from 2 to 5 — the insole shrinks inward.
- `ToeExtension` to 10 — the toe end gets longer.
- `BaseThk` to 10 — the insole gets thicker.

That's the whole live-updating workflow. Move sliders, watch geometry update.

---

## 9. View the outline curves

To see the editable top and bottom edges:
1. Drop two `Curve` parameters from Params → Geometry.
2. Wire `TopEdge` → first Curve param, `BottomEdge` → second.
3. Both curves now preview in Rhino as orange/red lines hugging the insole.

---

## 10. Edit control points (the "drag points to reshape" workflow)

This is the big advantage over the .rhi plugin.

1. Right-click the **TopEdge Curve parameter** → **Bake**.
   - A dialog asks for layer / attributes — accept defaults, click OK.
   - The curve is now a real Rhino object in your document.
2. In **Rhino**, select that curve and turn on its grips: type `PointsOn`
   (or press F10).
3. Drag the control points wherever you want. Each drag moves the curve.
4. Back in **Grasshopper**, drop a **Curve** parameter from Params →
   Geometry. Right-click → **Set one Curve** → pick the edited curve in
   Rhino.
5. Wire that Curve param into the script's `OverrideOutline` input.
6. The insole rebuilds using your dragged shape. Sliders still work, but
   `PerimeterOffset` / `ToeExtension` / `HeelExtension` are now ignored —
   your manual outline takes over.

Same procedure for `BottomEdge` → `OverrideBottom` if you want to sculpt
the underside.

To go back to auto-generated outline: right-click the Curve param feeding
`OverrideOutline` → **Disconnect** the wire. The script will generate the
outline from sliders again.

---

## 11. Save the definition

1. In Grasshopper: **File → Save As** → name it `OrthoticInsole.gh`.
2. Next time you want to use it: open Rhino with your shoe last, then in
   Grasshopper **File → Open** → pick the .gh file. The slider values and
   Last reference are saved with the file.

---

## 12. Bake the final insole to your Rhino document

When you're happy with the shape:
1. Right-click the script component's **SubD** output → **Bake**.
2. Pick a layer, click OK.
3. The SubD is now a permanent Rhino object you can export, mesh, 3D print,
   or process further.
4. Same for `TopEdge`, `BottomEdge`, `Footprint`, `Outline` if you want
   them as documented curves.

---

## Common problems

**"The script component is red"**
- Hover over it. Read the error message at the top of the popup.
- Most common cause: a required input is unwired or the wrong type. Check
  your wires.

**"My insole is upside down / wrong size"**
- The shoe last needs to have the sole facing −Z (downward). In Rhino,
  rotate it before referencing.

**"Insole is missing — only outline shows up"**
- Probably `Last` is not wired or the Brep param has lost its reference.
  Right-click the Brep param → "Set one Brep" again.

**"Sliders don't update the geometry live"**
- Check Solver menu (top of GH window) → make sure it's not in **Disabled**
  state (the icon should NOT have a red slash through it).

**"Component is yellow with a warning"**
- Yellow = warning, not error. Hover for details. Often it's "no curves
  found in section X" — usually safe to ignore if the SubD output still
  comes through.

---

## What each output does

- **SubD** — smooth subdivision surface, the deliverable. Bake this.
- **Mesh** — the underlying mesh before SubD conversion. Useful if SubD
  fails (then SubD will be empty and you fall back to baking the mesh).
- **Footprint** — flat XY outline traced from the shoe last sections.
- **Outline** — the offset insole perimeter (still flat XY).
- **TopEdge** — 3D NURBS curve following the sole-conforming top.
- **BottomEdge** — 3D NURBS curve along the flat underside.
- **Axis** — `"X"` or `"Y"`, just informational.
- **ToeDir** — `+1` or `-1`, just informational.

---

## Tip: snapshot your slider settings

Once you've got values that work for a particular last:
1. Note down the slider values, OR
2. Save the .gh file with that last as a custom file
   (`Mens_Size_10_Insole.gh`).

Each .gh file is just a definition + slider state. You can keep many of
them per shoe last / customer.
