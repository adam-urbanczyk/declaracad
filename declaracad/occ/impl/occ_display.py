"""
Copyright (c) 2020, Jairus Martin.

Distributed under the terms of the GPL v3 License.

The full license is in the file LICENSE, distributed with this software.

Created on Dec 27, 2020

@author: jrm
"""
from atom.api import Typed, Instance
from OCCT.gp import gp_Ax2
from OCCT.Graphic3d import Graphic3d_Text
from OCCT.Prs3d import (
    Prs3d_Arrow, Prs3d_ArrowAspect, Prs3d_Text, Prs3d_TextAspect
)
from OCCT.TCollection import TCollection_ExtendedString

from declaracad.core.utils import log


from ..display import ProxyDisplayItem, ProxyDisplayArrow, ProxyDisplayText
from ..shape import Point
from .occ_shape import coerce_axis
from .utils import color_to_quantity_color


class OccDisplayItem(ProxyDisplayItem):
    context = Instance(object)

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
        pass

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


class OccDisplayArrow(OccDisplayItem, ProxyDisplayArrow):
    #: A reference to the toolkit item created by the proxy.
    item = Typed(Prs3d_Arrow)

    def create_item(self, context):
        d = self.declaration
        #aspect = Prs3d_ArrowAspect()
        #color, alpha = color_to_quantity_color(d.color)
        #aspect.SetColor(color)
        #context.SetPrimitivesAspect(aspect)
        self.context = context
        self.item = Prs3d_Arrow.Draw_(
            context, d.position.proxy, d.direction.proxy, d
            .angle or d.size, d.size)


class OccDisplayText(OccDisplayItem, ProxyDisplayText):
    #: A reference to the toolkit item created by the proxy.
    item = Typed(Graphic3d_Text)

    def create_item(self, context):
        self.context = context
        d = self.declaration
        text = TCollection_ExtendedString(d.text)
        axis = gp_Ax2(d.position.proxy, d.direction.proxy)
        aspect = Prs3d_TextAspect()
        color, alpha = color_to_quantity_color(d.color)
        aspect.SetColor(color)
        aspect.SetHeight(d.size)
        if d.font:
            aspect.SetFont(d.font)

        self.item = Prs3d_Text.Draw_(context, aspect, text, axis)

    def set_text(self, text):
        self.update_item()

    def set_size(self, size):
        self.update_item()

    def set_font(self, font):
        self.update_item()
