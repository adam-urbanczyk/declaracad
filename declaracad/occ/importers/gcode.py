"""
Copyright (c) 2020, Jairus Martin.

Distributed under the terms of the GPL v3 License.

The full license is in the file LICENSE, distributed with this software.

Created on Aug 31, 2020

@author: jrm
"""
from declaracad.cnc import gcode
from declaracad.occ.api import Point, Polyline, Arc


def load_gcode(filename):
    """ Load a GCode file into a list of shapes to render

    """
    cmds = gcode.parse(filename)
    for cmd in cmds:
        pass
    return []
