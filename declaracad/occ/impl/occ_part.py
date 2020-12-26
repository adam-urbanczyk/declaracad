"""
Copyright (c) 2016-2020, Jairus Martin.

Distributed under the terms of the GPL v3 License.

The full license is in the file LICENSE, distributed with this software.

Created on Sep 30, 2016

@author: jrm
"""
import os
from atom.api import Typed, List, set_default

from OCCT.BRep import BRep_Builder
from OCCT.BRepTools import BRepTools
from OCCT.gp import gp, gp_Trsf, gp_Ax1, gp_Ax3, gp_Vec, gp_Dir
from OCCT.Quantity import Quantity_Color
from OCCT.TopLoc import TopLoc_Location
from OCCT.TopoDS import (
    TopoDS_Iterator, TopoDS_Shape, TopoDS_Compound, TopoDS_Face
)
from OCCT.TDF import TDF_LabelSequence, TDF_Label
from OCCT.TDataStd import TDataStd_Name
from OCCT.TDocStd import TDocStd_Document
from OCCT.TNaming import TNaming_NamedShape
from OCCT.TopAbs import (
    TopAbs_COMPSOLID, TopAbs_COMPOUND, TopAbs_SOLID, TopAbs_SHELL,
    TopAbs_FACE
)
from OCCT.TopExp import TopExp
from OCCT.TopTools import TopTools_IndexedMapOfShape

from OCCT.TCollection import TCollection_ExtendedString
from OCCT.XCAFApp import XCAFApp_Application
from OCCT.XCAFDoc import (
    XCAFDoc_DocumentTool, XCAFDoc_ShapeTool, XCAFDoc_ColorTool,
    XCAFDoc_ColorSurf, XCAFDoc_ColorCurv, XCAFDoc_ColorGen
)

from OCCT.IFSelect import IFSelect_RetDone, IFSelect_ItemsByEntity

from OCCT.IGESCAFControl import IGESCAFControl_Reader
from OCCT.STEPCAFControl import STEPCAFControl_Reader

from declaracad.occ.part import Shape, ProxyPart, ProxyRawPart
from declaracad.occ.shape import TopoShape
from .occ_shape import OccDependentShape, OccShape


class OccPart(OccDependentShape, ProxyPart):
    #: A reference to the toolkit shape created by the proxy.
    builder = Typed(BRep_Builder)

    #: Location
    location = Typed(TopLoc_Location)

    def _default_location(self):
        return TopLoc_Location(self.get_transform())

    def update_shape(self, change=None):
        """ Create the toolkit shape for the proxy object.

        """
        d = self.declaration
        builder = self.builder = BRep_Builder()
        shape = TopoDS_Compound()
        builder.MakeCompound(shape)
        for c in self.children():
            if not isinstance(c, OccShape):
                continue
            if c.shape is None or not c.declaration.display:
                continue
            # Note infinite planes cannot be added to a compound!
            builder.Add(shape, c.shape)
        location = self.location = self._default_location()
        shape.Location(location)
        self.shape = shape


class OccRawPart(OccPart, ProxyRawPart):
    #: Update the class reference
    reference = set_default('https://dev.opencascade.org/doc/refman/html/'
                            'class_topo_d_s___shape.html')

    shapes = List(TopoDS_Shape)

    def create_shapes(self):
        """ Delegate shape creation to the declaration implementation. """
        self.shapes = self.declaration.create_shapes(self.parent_shape())

    # -------------------------------------------------------------------------
    # ProxyRawShape API
    # -------------------------------------------------------------------------
    def get_shapes(self):
        """ Retrieve the underlying toolkit shape.
        """
        return self.shapes
