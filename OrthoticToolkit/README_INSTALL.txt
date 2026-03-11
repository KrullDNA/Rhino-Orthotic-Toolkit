========================================================
  ORTHOTIC TOOLKIT - Installation Guide
  Version 1.0 | Rhino 8 Python Plugin
========================================================

SYSTEM REQUIREMENTS
-------------------
- Rhinoceros 3D version 8.0 or later (Windows)
- No additional software, compilers, or SDKs required


INSTALLATION
------------
1. Close Rhino 8 if it is currently running.

2. Locate the file:  OrthoticToolkit_Session1.rhi
   (This is the installer file you received.)

3. Double-click the .rhi file.
   The Rhino Package Installer will open automatically.

4. Click "Install" when prompted.
   You should see a confirmation message that the plugin
   was installed successfully.

5. Open Rhino 8.
   The plugin loads automatically on startup.


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

3. The toolbar buttons provide quick access to plugin
   commands (currently: OT_ResetAll).


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

Problem:  "Unknown command: OT_ResetAll"
Solution: The plugin may not have loaded. Check
          Tools > Options > Plug-ins and ensure the
          plugin is enabled. Restart Rhino.

Problem:  The .rhi file does not open when double-clicked.
Solution: Right-click the file > Open With > and select
          Rhino. If Rhino is not listed, open Rhino first,
          then drag and drop the .rhi file onto the Rhino
          window.


CONTACT / SUPPORT
-----------------
If you encounter any issues not covered above, please
contact your plugin provider or submit a support request
with the following information:

  - Rhino version (Help > About Rhinoceros)
  - Windows version
  - A screenshot of any error message
  - Steps to reproduce the problem

========================================================
