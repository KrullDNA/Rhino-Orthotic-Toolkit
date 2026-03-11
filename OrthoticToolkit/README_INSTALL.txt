========================================================
  ORTHOTIC TOOLKIT v1.0 - Installation & Quick Start
  Professional Insole Design Plugin for Rhino 8
========================================================


SYSTEM REQUIREMENTS
-------------------
- Rhinoceros 3D version 8.0 or later (Windows)
- No additional software, compilers, or SDKs required
- Recommended: 8 GB RAM, dedicated GPU for viewport


INSTALLATION
------------
1. Close Rhino 8 if it is currently running.

2. Locate the file:  OrthoticToolkit_v1.0.rhi
   (This is the installer file you received.)

3. Double-click the .rhi file.
   The Rhino Package Installer will open automatically.

4. Click "Install" when prompted.
   You should see a confirmation message that the plugin
   was installed successfully.

5. Open Rhino 8.
   The plugin loads automatically on startup.
   You should see "Orthotic Toolkit plugin loaded
   successfully." in the command history.


OPENING THE PANEL
-----------------
1. In Rhino, go to the menu bar and click:
      View  >  Panels

2. In the panel list, check "Orthotic Toolkit".
   The panel will appear as a floating window.


DOCKING THE PANEL
-----------------
1. Click and drag the panel's title bar toward the right
   side of the Rhino window (next to the Properties panel).

2. When you see a blue docking indicator appear, release
   the mouse button.

3. The panel will snap into place beside your other panels.

4. Rhino remembers the docked position -- the panel will
   reopen in the same spot next time you launch Rhino.


USING THE TOOLBAR
-----------------
1. In Rhino, go to:
      View  >  Toolbars

2. Find "Orthotic Toolkit" in the toolbar list and
   enable it.

3. The toolbar contains 14 command buttons arranged in
   five groups:
   - Setup:  Select Last
   - Scan:   Import Scan, Orient Scan, Extract Plantar
   - Shape:  Generate Outline, Add Arch, Add Heel Cup,
             Add Met Dome, Add Posting
   - Finish: Set Thickness, Validate, Rocker Outline,
             Export
   - Utility: Reset All


QUICK START WORKFLOW
--------------------
Follow these steps in order to design a complete insole:

 1. SELECT LAST
    Open a Rhino scene containing a shoe last polysurface.
    Click "Select Last" in the panel status bar or toolbar.
    Pick the shoe last. A green footprint curve appears.

 2. IMPORT SCAN
    Switch to the "Foot Scan" tab.
    Click "Import Scan..." and choose an STL, OBJ, or PLY
    foot scan file. The mesh loads on the OT_FootScan layer.

 3. AUTO-ORIENT
    Click "Auto-Orient" to rotate the scan so the plantar
    (sole) surface faces downward (-Z direction).

 4. EXTRACT PLANTAR
    Adjust the smoothing slider (2 passes recommended).
    Click "Extract Plantar Surface". A NURBS surface appears
    on the OT_PlantarSurface layer.

 5. GENERATE OUTLINE
    Switch to the "Outline" tab.
    Adjust perimeter offset (2mm default).
    Click "Generate Outline". The insole outline and a flat
    base Brep appear on OT_Outline and OT_Insole layers.

 6. ADD ARCH
    Switch to the "Arch" tab.
    Set arch height (8-12mm typical), apex position, width.
    Click "Apply Arch". The arch merges into the insole.

 7. ADD HEEL CUP (optional)
    Switch to the "Heel Cup" tab.
    Set cup depth (10-14mm typical), angles, flares.
    Click "Apply Heel Cup".

 8. ADD MET DOMES (optional)
    Switch to the "Forefoot" tab.
    Set dome count, height, diameter.
    Click "Apply Met Domes".

 9. ADD POSTING (optional)
    Switch to the "Posting" tab.
    Set rearfoot/forefoot medial and lateral angles.
    Click "Apply Posting".

10. SET THICKNESS
    Switch to the "Thickness" tab.
    Set cover (2mm), shell (3mm), and base (5mm) values.
    Click "Apply Thickness". Three layer Breps are built.

11. VALIDATE
    Click "Run Validation". A report dialog shows whether
    the insole passes all checks (validity, solidity,
    minimum thickness, overhangs).

12. EXPORT
    Switch to the "Export" tab.
    Choose format (STL, STEP, OBJ, or 3DM).
    Choose mesh resolution (Fine 0.1mm recommended).
    Click "Export..." and save to your desired location.


VERIFYING THE INSTALLATION
---------------------------
1. Open the Orthotic Toolkit panel (View > Panels).
   You should see eight tabs: Foot Scan, Outline, Arch,
   Heel Cup, Forefoot, Posting, Thickness, Export.

2. Type  OT_ResetAll  in the Rhino command line and
   press Enter.
   You should see:
      "Orthotic Toolkit: All state cleared."

If both of these work, the installation is successful.


TROUBLESHOOTING
---------------
Problem:  The panel does not appear in View > Panels.
Solution: Go to Tools > Options > Plug-ins. Look for
          "Orthotic Toolkit" in the list. Make sure it
          is enabled. Restart Rhino.

Problem:  "Unknown command: OT_SetLast" (or any OT_ cmd)
Solution: The plugin may not have loaded. Check
          Tools > Options > Plug-ins and ensure the
          plugin is enabled. Restart Rhino.

Problem:  The .rhi file does not open when double-clicked.
Solution: Right-click the file > Open With > and select
          Rhino. If Rhino is not listed, open Rhino first,
          then drag and drop the .rhi file onto the Rhino
          window.

Problem:  Scan import shows no mesh / empty viewport.
Solution: Make sure the scan file is a valid mesh format
          (STL, OBJ, or PLY). After import, the command
          will ask you to select the mesh -- click on it
          in the viewport.

Problem:  Boolean union fails (amber warning appears).
Solution: Try using less extreme parameter values. Boolean
          operations can fail with very tall arches or
          very deep heel cups. The plugin will show a
          warning but will not crash.

Problem:  Export produces an empty or corrupt file.
Solution: Run "Validate" first and ensure the report shows
          "READY FOR EXPORT". Fix any issues before export.


CONTACT / SUPPORT
-----------------
If you encounter any issues not covered above, please
contact your plugin provider or submit a support request
with the following information:

  - Rhino version (Help > About Rhinoceros)
  - Windows version
  - The command history output (copy from the command line)
  - A screenshot of any error message or dialog
  - Steps to reproduce the problem

========================================================
