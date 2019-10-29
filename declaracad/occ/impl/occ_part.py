"""
Copyright (c) 2016-2018, Jairus Martin.

Distributed under the terms of the GPL v3 License.

The full license is in the file LICENSE, distributed with this software.

Created on Sep 30, 2016

@author: jrm
"""
from math import pi
from atom.api import Typed
from ..part import ProxyPart
from .occ_shape import OccDependentShape, OccShape

from OCCT.TopoDS import TopoDS_Compound, TopoDS_Shape
from OCCT.BRep import BRep_Builder
from OCCT.BRepBuilderAPI import BRepBuilderAPI_Transform
from OCCT.gp import gp, gp_Trsf, gp_Ax1, gp_Ax3, gp_Vec, gp_Dir



DX = gp.DX_()
AY = gp_Ax1()
AY.SetDirection(gp.DY_())


class OccPart(OccDependentShape, ProxyPart):
    #: A reference to the toolkit shape created by the proxy.
    builder = Typed(BRep_Builder)

    #: Transform
    transform = Typed(gp_Trsf)

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

        bbox = self.get_bounding_box(shape)

        # Move to position and align along direction axis
        t = gp_Trsf()
        if d.direction == DX:
            # The "normal" direction is DX so if we want this to point
            # in DX the gp_Ax3 method does not work
            t.SetRotation(AY, -pi/2)
        else:
            axis = gp_Ax3()
            axis.SetDirection(d.direction.proxy)
            t.SetTransformation(axis)

        t.SetTranslationPart(gp_Vec(*d.position))
        self.transform = t
        part = BRepBuilderAPI_Transform(shape, t, False)
        self.shape = part.Shape()
