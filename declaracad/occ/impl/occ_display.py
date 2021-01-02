"""
Copyright (c) 2020, Jairus Martin.

Distributed under the terms of the GPL v3 License.

The full license is in the file LICENSE, distributed with this software.

Created on Dec 27, 2020

@author: jrm
"""
from atom.api import Typed, Instance
from OCCT.AIS import AIS_Line, AIS_TextLabel, AIS_Plane
from OCCT.gp import gp_Ax2
from OCCT.Graphic3d import Graphic3d_Text
from OCCT.Geom import Geom_Line, Geom_Plane
from OCCT.Prs3d import (
    Prs3d_Arrow, Prs3d_ArrowAspect, Prs3d_Text, Prs3d_TextAspect
)
from OCCT.TCollection import TCollection_ExtendedString

from declaracad.core.utils import log


from ..display import (
    ProxyDisplayItem, ProxyDisplayArrow, ProxyDisplayText, ProxyDisplayLine,
    ProxyDisplayPlane,
)
from ..shape import Point
from .occ_shape import coerce_axis
from .utils import color_to_quantity_color


class OccDisplayItem(ProxyDisplayItem):
    # -------------------------------------------------------------------------
    # Initialization API
    # -------------------------------------------------------------------------
    def create_item(self, context):
        pass

    def update_item(self):
        """ Recreates the dimension catching any errors

        """
        if not self.context:
            return
        try:
            self.create_item(self.context)
        except Exception as e:
            log.exception(e)

    def activate_top_down(self):
        """ Activate the proxy for the top-down pass.

        """
        self.create_item()

    def activate_bottom_up(self):
        """ Activate the proxy tree for the bottom-up pass.

        """
        pass

    # -------------------------------------------------------------------------
    # Proxy API
    # -------------------------------------------------------------------------
    def set_position(self, position):
        self.update_item()

    def set_color(self, color):
        self.update_item()

    def set_direction(self, direction):
        self.update_item()


class OccDisplayLine(OccDisplayItem, ProxyDisplayLine):
    #: A reference to the toolkit item created by the proxy.
    item = Typed(AIS_Line)

    def create_item(self):
        d = self.declaration
        line = Geom_Line(d.position.proxy, d.direction.proxy)
        ais_item = AIS_Line(line)
        color, alpha = color_to_quantity_color(d.color)
        ais_item.SetColor(color)
        self.item = ais_item


class OccDisplayPlane(OccDisplayItem, ProxyDisplayPlane):
    #: A reference to the toolkit item created by the proxy.
    item = Typed(AIS_Plane)

    def create_item(self):
        d = self.declaration
        plane = Geom_Plane(d.position.proxy, d.direction.proxy)
        ais_item = AIS_Plane(plane)
        color, alpha = color_to_quantity_color(d.color)
        ais_item.SetColor(color)
        self.item = ais_item


class OccDisplayArrow(OccDisplayItem, ProxyDisplayArrow):
    #: A reference to the toolkit item created by the proxy.
    item = Typed(Prs3d_Arrow)

    def create_item(self):
        d = self.declaration
        #aspect = Prs3d_ArrowAspect()
        #color, alpha = color_to_quantity_color(d.color)
        #aspect.SetColor(color)
        #context.SetPrimitivesAspect(aspect)
        #self.context = context
        #self.item = Prs3d_Arrow.Draw_(
            #context, d.position.proxy, d.direction.proxy, d
            #.angle or d.size, d.size)


class OccDisplayText(OccDisplayItem, ProxyDisplayText):
    #: A reference to the toolkit item created by the proxy.
    item = Typed(AIS_TextLabel)

    def create_item(self):
        d = self.declaration
        text = TCollection_ExtendedString(d.text)
        ais_item = AIS_TextLabel()
        ais_item.SetText(text)
        ais_item.SetPosition(d.position.proxy)
        ais_item.SetHeight(d.size)
        if d.font:
            ais_item.SetFont(d.font)

        color, alpha = color_to_quantity_color(d.color)
        ais_item.SetColor(color)
        self.item = ais_item

    def set_text(self, text):
        self.update_item()

    def set_size(self, size):
        self.update_item()

    def set_font(self, font):
        self.update_item()
