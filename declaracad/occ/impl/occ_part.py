"""
Copyright (c) 2016-2020, Jairus Martin.

Distributed under the terms of the GPL v3 License.

The full license is in the file LICENSE, distributed with this software.

Created on Sep 30, 2016

@author: jrm
"""
import os
from math import pi
from atom.api import Typed, List, set_default

from OCCT.BRep import BRep_Builder
from OCCT.BRepTools import BRepTools
from OCCT.gp import gp, gp_Trsf, gp_Ax1, gp_Ax3, gp_Vec, gp_Dir
from OCCT.Quantity import Quantity_Color
from OCCT.TopLoc import TopLoc_Location
from OCCT.TopoDS import TopoDS_Iterator, TopoDS_Shape, TopoDS_Compound
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

from declaracad.occ.part import Shape, ProxyPart, ProxyRawPart, ProxyLoadPart
from declaracad.occ.shape import TopoShape
from .occ_shape import OccDependentShape, OccShape


DX = gp.DX_()
AY = gp_Ax1()
AY.SetDirection(gp.DY_())


class OccPart(OccDependentShape, ProxyPart):
    #: A reference to the toolkit shape created by the proxy.
    builder = Typed(BRep_Builder)

    #: Location
    location = Typed(TopLoc_Location)

    def _default_location(self):
        d = self.declaration
        # Move to position and align along direction axis
        result = gp_Trsf()
        if d.direction == DX:
            # The "normal" direction is DX so if we want this to point
            # in DX the gp_Ax3 method does not work
            result.SetRotation(AY, -pi/2)
        else:
            axis = gp_Ax3()
            axis.SetDirection(d.direction.proxy)
            result.SetTransformation(axis)

        result.SetTranslationPart(gp_Vec(*d.position))
        if d.rotation:
            t = gp_Trsf()
            t.SetRotation(gp_Ax1(d.position.proxy, d.direction.proxy),
                            d.rotation)
            result.Multiply(t)
        return TopLoc_Location(result)

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
        self.shapes = self.declaration.create_shape(self.parent_shape())

    # -------------------------------------------------------------------------
    # ProxyRawShape API
    # -------------------------------------------------------------------------
    def get_shapes(self):
        """ Retrieve the underlying toolkit shape.
        """
        return self.shapes



class OccLoadPart(OccPart, ProxyLoadPart):
    #: Update the class reference
    reference = set_default('https://dev.opencascade.org/doc/refman/html/'
                            'class_topo_d_s___shape.html')

    app = Typed(XCAFApp_Application)

    #:
    loaded_shapes = List(TopoShape)

    def _default_app(self):
        return XCAFApp_Application.GetApplication_()

    def create_shape(self):
        """ Create the shape by loading it from the given path. """
        d = self.declaration
        shapes = self.load_shapes()

        # Remove old
        for shape in self.loaded_shapes:
            if not shape.is_destroyed:
                shape.destroy()
        self.loaded_shapes = shapes

        # Insert new
        d.insert_children(None, shapes)

        #t = self.get_transform()
        #loaded_shape = BRepBuilderAPI_Transform(shape, t, False)
        #self.shape = loaded_shape.Shape()

    def get_transform(self):
        d = self.declaration
        t = gp_Trsf()
        t.SetTransformation(gp_Ax3(coerce_axis(d.axis)))
        return t

    def load_shapes(self):
        d = self.declaration
        if not os.path.exists(d.path):
            raise ValueError("Can't load shape from `{}`, "
                             "the path does not exist".format(d.path))
        path, ext = os.path.splitext(d.path)
        name = ext[1:] if d.loader == 'auto' else d.loader
        loader = getattr(self, 'load_{}'.format(name.lower()))
        return loader(d.path)

    def load_brep(self, path):
        """ Load a brep model """
        shape = TopoDS_Shape()
        builder = BRep_Builder()
        BRepTools.Read_(shape, path, builder, None)
        return [TopoShape(shape=shape)]

    def load_igs(self, path):
        """ Alias for iges """
        return self.load_iges(path)

    def load_iges(self, path):
        """ Load an iges model """
        reader = IGESCAFControl_Reader()
        reader.SetColorMode(True)
        status = reader.ReadFile(path)
        if status != IFSelect_RetDone:
            raise ValueError("Failed to read: {}".format(path))

        if not reader.NbRootsForTransfer():
            raise ValueError("File has no shapes: {}".format(path))

        name = TCollection_ExtendedString("IGES-{}".format(id(self)))
        doc = TDocStd_Document(name)
        if not reader.Transfer(doc):
            raise ValueError("Failed to transfer: {}".format(path))

        return self._process_doc(doc)

    def load_step(self, path):
        """ Alias for stp """
        return self.load_stp(path)

    def load_stp(self, path):
        """ Load a stp model """
        d = self.declaration
        reader = STEPCAFControl_Reader()
        reader.SetColorMode(True)
        status = reader.ReadFile(path)
        if status != IFSelect_RetDone:
            raise ValueError("Failed to read: {}".format(path))

        if not reader.NbRootsForTransfer():
            raise ValueError("File has no shapes: {}".format(path))

        name = TCollection_ExtendedString("STEP-{}".format(id(self)))
        doc = TDocStd_Document(name)
        if not reader.Transfer(doc):
            raise ValueError("Failed to transfer: {}".format(path))

        return self._process_doc(doc)

    def load_stl(self, path):
        """ Load a stl model """
        builder = BRep_Builder()
        shape = TopoDS_Face()
        builder.MakeFace(shape)
        poly = RWStl.ReadFile_(path, None)
        builder.UpdateFace(shape, poly)
        return [TopoShape(shape=shape)]

    def _process_doc(self, doc):
        main = doc.Main()
        color_tool = XCAFDoc_DocumentTool.ColorTool_(main)
        shape_tool = XCAFDoc_DocumentTool.ShapeTool_(main)
        labels = TDF_LabelSequence()
        shape_tool.GetFreeShapes(labels)

        shapes = []
        for i  in range(1, labels.Length() + 1):
            shape = shape_tool.GetShape_(labels.Value(i))
            shapes.extend(self._process_shape(shape, color_tool))
        return shapes

    def _process_shape(self, shape, color_tool):
        shapes = []
        shape_type = shape.ShapeType()
        print("Process {}".format(shape_type))
        if shape_type in (TopAbs_COMPOUND, TopAbs_COMPSOLID):
            it = TopoDS_Iterator()
            it.Initialize(shape, False, False)
            while it.More():
                shapes.extend(self._process_shape(it.Value(), color_tool))
                it.Next()
        elif shape_type == TopAbs_SOLID:
            shapes.extend(self._process_solid(shape, color_tool))
        elif shape_type == TopAbs_SHELL:
            shapes.extend(self._process_shell(shape, color_tool))
        elif shape_type == TopAbs_FACE:
            shapes.append(self._process_face(shape, color_tool))
        else:
            color = self._get_color(shape, color_tool)
            shapes.append(TopoShape(shape=shape, color=color))
        return shapes

    def _process_solid(self, shape, color_tool):
        shapes = []
        color = self._get_color(shape, color_tool)
        it = TopoDS_Iterator()
        it.Initialize(shape, False, False)
        while it.More():
            #shapes.append(TopoShape(shape=shape, color=color))
            shapes.extend(self._process_shell(it.Value(), color_tool, color))
            it.Next()
        return shapes

    def _process_shell(self, shape, color_tool, default_color=None):
        shapes = []
        color = self._get_color(shape, color_tool) or default_color
        it = TopoDS_Iterator()
        it.Initialize(shape, False, False)
        while it.More():
            shapes.append(TopoShape(shape=shape, color=color))
            #shapes.append(self._process_face(it.Value(), color_tool, color))
            it.Next()
        return shapes

    def _process_face(self, shape, color_tool, default_color=None):
        color = self._get_color(shape, color_tool) or default_color
        return TopoShape(shape=shape, color=color)

    def _get_color(self, shape, color_tool):
        label = TDF_Label()
        color_tool.ShapeTool().Search(shape, label)
        if label.IsNull():
            return None
        color = Quantity_Color()
        while True:
            if color_tool.GetColor(label, color):
                return Quantity_Color.ColorToHex_(color).ToCString()
            #elif color_tool.GetColor(label, XCAFDoc_ColorSurf, color):
            #    return Quantity_Color.ColorToHex_(color)
            #elif color_tool.GetColor(label, XCAFDoc_ColorCurv, color):
            #    return Quantity_Color.ColorToHex_(color)
            label = label.Father()
            if label.IsNull():
                break
        print("Color not found")
        return None
    # -------------------------------------------------------------------------
    # ProxyLoadShape API
    # -------------------------------------------------------------------------
    def set_path(self, path):
        self.create_shape()

    def set_loader(self, loader):
        self.create_shape()
