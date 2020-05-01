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

from OCCT.BRep import BRep_Builder
from OCCT.gp import gp, gp_Trsf, gp_Ax1, gp_Ax3, gp_Vec, gp_Dir
from OCCT.TopLoc import TopLoc_Location
from OCCT.TopoDS import TopoDS_Compound, TopoDS_Shape


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
