"""
Copyright (c) 2020, Jairus Martin.

Distributed under the terms of the GPL v3 License.

The full license is in the file LICENSE, distributed with this software.

Created on March 25, 2020

@author: jrm
"""
from atom.api import Typed
from OCCT.AIS import (
    AIS_AngleDimension, AIS_DiameterDimension, AIS_LengthDimension,
    AIS_RadiusDimension, AIS_Dimension
)
from OCCT.BRep import BRep_Tool
from OCCT.GC import GC_MakePlane
from OCCT.gp import gp_Pnt
from OCCT.TopoDS import TopoDS_Edge, TopoDS_Vertex

from ..dimension import (
    ProxyDimension, ProxyAngleDimension, ProxyDiameterDimension,
    ProxyRadiusDimension, ProxyLengthDimension
)
from .occ_shape import Topology

from declaracad.core.utils import log

from declaracad.occ.qt.utils import color_to_quantity_color


class OccDimension(ProxyDimension):
    #: A reference to the toolkit dimension created by the proxy.
    dimension = Typed(AIS_Dimension)

    # -------------------------------------------------------------------------
    # Initialization API
    # -------------------------------------------------------------------------
    def create_dimension(self):
        pass

    def init_dimension(self):
        d = self.declaration
        dim = self.dimension
        if dim is None:
            return
        aspect = dim.DimensionAspect()
        if d.color:
            color, transparency = color_to_quantity_color(d.color)
            aspect.SetCommonColor(color)
        dim.SetDimensionAspect(aspect)

    def update_dimension(self):
        """ Recreates the dimension catching any errors

        """
        try:
            self.create_dimension()
            self.init_dimension()
        except Exception as e:
            self.dimension = None
            log.exception(e)

    def activate_top_down(self):
        """ Activate the proxy for the top-down pass.

        """
        self.update_dimension()

    def activate_bottom_up(self):
        """ Activate the proxy tree for the bottom-up pass.

        """
        pass

    # -------------------------------------------------------------------------
    # Proxy API
    # -------------------------------------------------------------------------
    def set_shapes(self, shapes):
        self.update_dimension()

    def set_display(self, display):
        self.update_dimension()

    def set_color(self, color):
        self.update_dimension()

    def set_position(self, position):
        self.update_dimension()


class OccAngleDimension(OccDimension, ProxyAngleDimension):
    #: A reference to the toolkit dimension created by the proxy.
    dimension = Typed(AIS_AngleDimension)

    def create_dimension(self):
        d = self.declaration
        self.dimension = AIS_AngleDimension(*d.shapes)


class OccLengthDimension(OccDimension, ProxyLengthDimension):
    #: A reference to the toolkit dimension created by the proxy.
    dimension = Typed(AIS_LengthDimension)

    def make_plane(self, v1, v2):
        d = self.declaration
        p1 = BRep_Tool.Pnt_(v1)
        p2 = BRep_Tool.Pnt_(v2)
        p3 = (d.position + p2).proxy
        return GC_MakePlane(p1, p2, p3).Value().Pln()

    def create_dimension(self):
        d = self.declaration
        s = d.shapes[0]
        args = []

        if isinstance(s, TopoDS_Edge):
            topo = Topology(shape=s)
            args = (s, self.make_plane(*topo.vertices_from_edge(s)[0:]))
        elif isinstance(s, TopoDS_Vertex):
            s2 = d.shapes[1]
            args = (s, s2, self.make_plane(s, s2))

        self.dimension = AIS_LengthDimension(*args)


class OccRadiusDimension(OccDimension, ProxyRadiusDimension):
    #: A reference to the toolkit dimension created by the proxy.
    dimension = Typed(AIS_RadiusDimension)

    def create_dimension(self):
        d = self.declaration
        self.dimension = AIS_RadiusDimension(*d.shapes)


class OccDiameterDimension(OccDimension, ProxyDiameterDimension):
    #: A reference to the toolkit dimension created by the proxy.
    dimension = Typed(AIS_DiameterDimension)

    def create_dimension(self):
        d = self.declaration
        self.dimension = AIS_DiameterDimension(*d.shapes)
