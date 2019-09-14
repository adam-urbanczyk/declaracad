"""
Copyright (c) 2019, Jairus Martin.

Distributed under the terms of the GPL v3 License.

The full license is in the file LICENSE, distributed with this software.

"""
from OCCT.Quantity import Quantity_Color, Quantity_TOC_RGB


def color_to_quantity_color(color):
    """ Convert an enaml color to an Quantity_Color

    Parameters
    ----------
    color: enaml.colors.Color
        The color to convert

    Returns
    -------
    result: (Quantity_Color, float or None)
        A tuple of the color and transparency
    """
    transparency = None
    if color.alpha != 255:
        transparency = 1-color.alpha/255.0
    color = Quantity_Color(
        color.red/255., color.green/255., color.blue/255., Quantity_TOC_RGB)
    return (color, transparency)
