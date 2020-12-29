"""
Copyright (c) 2019, Jairus Martin.

Distributed under the terms of the GPL v3 License.

The full license is in the file LICENSE, distributed with this software.

"""
from OCCT import Graphic3d
from OCCT.Graphic3d import Graphic3d_MaterialAspect
from OCCT.Quantity import Quantity_Color, Quantity_TOC_RGB


OCC_COLOR_CACHE = {}
OCC_MATERIAL_CACHE = {}


def color_to_quantity_color(color):

    """ Convert an enaml color to an Quantity_Color. The result is cached.

    Parameters
    ----------
    color: enaml.colors.Color
        The color to convert

    Returns
    -------
    result: (Quantity_Color, float or None)
        A tuple of the color and transparency
    """
    result = OCC_COLOR_CACHE.get(color.argb)
    if result is None:
        transparency = None
        if color.alpha != 255:
            transparency = 1-color.alpha/255.0
        occ_color = Quantity_Color(
            color.red/255., color.green/255., color.blue/255., Quantity_TOC_RGB)
        result = (occ_color, transparency)
        OCC_COLOR_CACHE[color.argb] = result
    return result


def material_to_material_aspect(material):
    """ Convert a material name to a Graphic3d material

    Parameters
    ----------
    material: declaracad.shape.Material
        The material definition

    Returns
    -------
    result: Graphic3d_MaterialAspect or None
        The material

    """
    name = 'DEFAULT' if material is None else material.name
    if name:
        ma = OCC_MATERIAL_CACHE.get(name)
        if ma is None:
            material_type = 'Graphic3d_NOM_%s' % name.upper()
            ma = Graphic3d_MaterialAspect(getattr(Graphic3d, material_type))
            OCC_MATERIAL_CACHE[name] = ma
        return ma
    a = Graphic3d_MaterialAspect()
    a.SetTransparency(material.transparency)
    a.SetShininess(material.shininess)
    a.SetRefractionIndex(material.refraction_index)
    if material.color:
        c, t = color_to_quantity_color(material.color)
        a.SetColor(c)
    if material.ambient_color:
        c, t = color_to_quantity_color(material.ambient_color)
        a.SetAmbientColor(c)
    if material.diffuse_color:
        c, t = color_to_quantity_color(material.diffuse_color)
        a.SetDiffuseColor(c)
    if material.specular_color:
        c, t = color_to_quantity_color(material.specular_color)
        a.SetSpecularColor(c)
    if material.emissive_color:
        c, t = color_to_quantity_color(material.emissive_color)
        a.SetEmissiveColor(c)
    return a
