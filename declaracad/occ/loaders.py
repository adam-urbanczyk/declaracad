"""
Copyright (c) 2020, Jairus Martin.

Distributed under the terms of the GPL v3 License.

The full license is in the file LICENSE, distributed with this software.

Created on Aug 31, 2020

@author: jrm
"""
import enaml

def load_gcode():
    from declaracad.occ.importers.gcode import load_gcode
    return load_gcode


def load_iges():
    from declaracad.occ.importers.iges import load_iges
    return load_iges


def load_svg():
    from declaracad.occ.importers.svg import load_svg
    return load_svg


def load_step():
    from declaracad.occ.importers.step import load_step
    return load_step


def load_stl():
    from declaracad.occ.importers.stl import load_stl
    return load_stl


def load_dxf():
    from declaracad.occ.importers.dxf import load_dxf
    return load_dxf


# Mapping of filename to function that returns a loader.
# A loader is just a function that takes a filename and returns a
# list of DeclaraCAD shapes. This allows deferring of imports until needed
# which improves startup time.
# Case is forced to lower before checking the mapping.
LOADER_REGISTRY = {
    '.dxf': load_dxf,
    '.iges': load_iges,
    '.ncc': load_gcode,
    '.nc': load_gcode,
    '.tap': load_gcode,
    '.svg': load_svg,
    '.stp': load_step,
    '.step': load_step,
    '.stl': load_stl,
}


with enaml.imports():
    from .loader import LoadedPart
