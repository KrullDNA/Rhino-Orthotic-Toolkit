# -*- coding: utf-8 -*-
"""Orthotic Toolkit - Layer Management Utilities

Centralised helpers for creating, clearing, and colouring Rhino document
layers used by the Orthotic Toolkit plugin.  All commands should import
these helpers instead of managing layers inline.
"""

import System
import Rhino.DocObjects as rd
import scriptcontext as sc


# Canonical layer names and RGB colours
LAYER_COLORS = {
    "OT_Preview":         (0, 180, 0),       # green
    "OT_FootScan":        (100, 180, 255),    # light blue
    "OT_PlantarSurface":  (255, 200, 0),      # yellow
    "OT_Outline":         (255, 100, 0),      # orange
    "OT_Insole":          (0, 120, 200),      # blue
    "OT_Warnings":        (220, 0, 0),        # red
    "OT_RockerContact":   (160, 0, 200),      # purple
}


def ensure_layer(name, color=None):
    """Create a layer if it does not already exist and return its index.

    Args:
        name:  Layer name (e.g. 'OT_Preview').
        color: Optional System.Drawing.Color or (r, g, b) tuple.
               If omitted, the canonical colour from LAYER_COLORS is used,
               falling back to medium grey.

    Returns:
        int -- the layer table index.
    """
    layer_index = sc.doc.Layers.FindByFullPath(name, -1)
    if layer_index >= 0:
        return layer_index

    layer = rd.Layer()
    layer.Name = name

    if color is None:
        rgb = LAYER_COLORS.get(name, (160, 160, 160))
        color = System.Drawing.Color.FromArgb(rgb[0], rgb[1], rgb[2])
    elif isinstance(color, tuple):
        color = System.Drawing.Color.FromArgb(color[0], color[1], color[2])

    layer.Color = color
    layer_index = sc.doc.Layers.Add(layer)
    return layer_index


def clear_layer(name):
    """Delete every object on the named layer.

    Does nothing if the layer does not exist.
    """
    layer_index = sc.doc.Layers.FindByFullPath(name, -1)
    if layer_index < 0:
        return

    settings = rd.ObjectEnumeratorSettings()
    settings.LayerIndexFilter = layer_index
    for obj in sc.doc.Objects.GetObjectList(settings):
        sc.doc.Objects.Delete(obj.Id, True)


def set_layer_color(name, r, g, b):
    """Change the display colour of an existing layer.

    Creates the layer first if it does not exist.
    """
    layer_index = ensure_layer(name)
    layer = sc.doc.Layers[layer_index]
    layer.Color = System.Drawing.Color.FromArgb(r, g, b)
    sc.doc.Layers.Modify(layer, layer_index, True)
