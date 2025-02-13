"""
Copyright (c) 2020, Jairus Martin.

Distributed under the terms of the GPL v3 License.

The full license is in the file LICENSE, distributed with this software.

Created on Dec 27, 2020

@author: jrm
"""

import math
from atom.api import (
    Bool, Coerced, Float, List, Str, Typed, ForwardTyped, observe
)
from enaml.colors import ColorMember, Color
from enaml.core.declarative import d_
from enaml.widgets.control import ProxyControl
from enaml.widgets.toolkit_object import ToolkitObject

from .geom import Direction, Point, coerce_point, coerce_direction


class ProxyDisplayItem(ProxyControl):
    #: A reference to the Shape declaration.
    declaration = ForwardTyped(lambda: DisplayItem)

    def set_position(self, position):
        raise NotImplementedError

    def set_color(self, color):
        raise NotImplementedError

    def set_direction(self, direction):
        raise NotImplementedError


class ProxyDisplayLine(ProxyDisplayItem):
    #: A reference to the Shape declaration.
    declaration = ForwardTyped(lambda: DisplayLine)


class ProxyDisplayPlane(ProxyDisplayItem):
    #: A reference to the Shape declaration.
    declaration = ForwardTyped(lambda: DisplayPlane)


class ProxyDisplayArrow(ProxyDisplayItem):
    #: A reference to the Shape declaration.
    declaration = ForwardTyped(lambda: DisplayArrow)

    def set_size(self, size):
        raise NotImplementedError


class ProxyDisplayText(ProxyDisplayItem):
    #: A reference to the Shape declaration.
    declaration = ForwardTyped(lambda: DisplayText)

    def set_text(self, text):
        raise NotImplementedError

    def set_size(self, size):
        raise NotImplementedError

    def set_font(self, font):
        raise NotImplementedError


class DisplayItem(ToolkitObject):
    """ Basic display item. This represents an item in the display
    that has no effect on the model.

    """
    #: Reference to the implementation control
    proxy = Typed(ProxyDisplayItem)

    #: Whether the item should be displayed
    display = d_(Bool(True))

    #: A string representing the color of the shape.
    color = d_(ColorMember()).tag(view=True, group='Display')

    def _default_color(self):
        return Color(0, 0, 0)

    #: A tuple or list of the (x, y, z) direction of this shape. This is
    #: coerced into a Point. The direction is relative to the dimensions axis.
    position = d_(Coerced(Point, coercer=coerce_point))

    def _default_position(self):
        return Point(0, 0, 0)

    #: A tuple or list of the (x, y, z) direction of this shape. This is
    #: coerced into a Point. The direction is relative to the dimensions axis.
    direction = d_(Coerced(Direction, coercer=coerce_direction))

    def _default_direction(self):
        return Point(0, 0, 1)

    @observe('position', 'color', 'direction')
    def _update_proxy(self, change):
        super()._update_proxy(change)

    def show(self):
        """ Generates the display item

        Returns
        -------
        item: Graphic3d item
            The item generated by this declaration.

        """
        if not self.is_initialized:
            self.initialize()
        if not self.proxy_is_active:
            self.activate_proxy()
        return self.proxy.item


class DisplayLine(DisplayItem):
    #: Reference to the implementation control
    proxy = Typed(ProxyDisplayLine)


class DisplayPlane(DisplayItem):
    #: Reference to the implementation control
    proxy = Typed(ProxyDisplayPlane)

class DisplayArrow(DisplayItem):
    """ Add an arrow to the 3d display.

    """
    #: Reference to the implementation control
    proxy = Typed(ProxyDisplayArrow)

    #: Arrow size
    size = d_(Float(12))

    #: Arrow angle
    angle = d_(Float())

    @observe('size', 'angle')
    def _update_proxy(self, change):
        super()._update_proxy(change)


class DisplayText(DisplayItem):
    """ Add text to the 3d display.

    """
    #: Reference to the implementation control
    proxy = Typed(ProxyDisplayText)

    #: Text to display
    text = d_(Str())

    #: Font size
    size = d_(Float(12))

    #: Font family
    font = d_(Str())

    @observe('text', 'size', 'font')
    def _update_proxy(self, change):
        super()._update_proxy(change)


