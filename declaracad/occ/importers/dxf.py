"""
Copyright (c) 2020, Jairus Martin.

Distributed under the terms of the GPL v3 License.

The full license is in the file LICENSE, distributed with this software.

Created on May 16, 2020

@author: jrm
"""
import ezdxf
from math import radians
from declaracad.core.utils import log
from declaracad.occ.api import *

from OCCT.BRep import BRep_Builder
from OCCT.TopoDS import TopoDS_Compound
from OCCT.TopTools import TopTools_HSequenceOfShape
from OCCT.ShapeAnalysis import ShapeAnalysis_FreeBounds


def importer(path, output_path):
    """ Attempt to import a dxf file into DeclaraCAD code

    """
    pass


def load(path):
    doc = ezdxf.readfile(path)
    edges = TopTools_HSequenceOfShape()

    for element in doc.modelspace():
        dxf_type = element.dxftype()
        d = element.dxf
        if dxf_type == 'LINE':
            node = Segment(points=[d.start, d.end]).render()
        elif dxf_type == 'ARC':
            node = Arc(
                position=d.center,
                radius=d.radius,
                alpha1=radians(d.start_angle),
                alpha2=radians(d.end_angle)).render()
        elif dxf_type == 'CIRCLE':
            node = Circle(radius=d.radius, position=d.center).render()
        else:
            log.warning(f"Unhandled element: {element}")
            continue
        edges.Append(node)

    wires = ShapeAnalysis_FreeBounds.ConnectEdgesToWires_(edges, 1e-6, False)

    builder = BRep_Builder()
    shape = TopoDS_Compound()
    builder.MakeCompound(shape)

    for i in range(1, wires.Size() + 1):
        builder.Add(shape, wires.Value(i))

    return shape
