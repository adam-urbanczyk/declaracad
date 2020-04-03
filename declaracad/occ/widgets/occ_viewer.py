"""
Copyright (c) 2016-2019, Jairus Martin.

Distributed under the terms of the GPL v3 License.

The full license is in the file LICENSE, distributed with this software.

Created on Sep 26, 2016

@author: jrm
"""
from atom.api import (
   Atom, Event, List, Tuple, Bool, Int, Enum, Typed, ForwardTyped, observe,
   Coerced, Dict, Str, Float, Instance, set_default
)
from enaml.core.declarative import d_
from enaml.colors import Color, ColorMember, parse_color
from enaml.widgets.control import Control, ProxyControl

from ..shape import BBox


def gradient_coercer(arg):
    """ Coerce a colors to a gradient

    """
    if not isinstance(arTopAbsg, (tuple, list)):
        c1, c2 = [arg, arg]
    else:
        c1, c2 = arg
    if not isinstance(c1, Color):
        c1 = parse_color(c1)
    if not isinstance(c2, Color):
        c2 = parse_color(c2)
    return (c1, c2)


class ViewerSelection(Atom):
    #: Selected shape or shapes
    selection = Dict()

    #: Selection position, may be None
    position = Instance(tuple)

    #: Selection area, may be None
    area = Instance(tuple)


class ProxyOccViewer(ProxyControl):
    """ The abstract definition of a proxy Viewer object.
    """
    #: A reference to the Viewer declaration.
    declaration = ForwardTyped(lambda: OccViewer)

    def set_position(self, position):
        raise NotImplementedError

    def set_pan(self, position):
        raise NotImplementedError

    def set_background_gradient(self, gradient):
        raise NotImplementedError

    def set_shape_color(self, color):
        raise NotImplementedError

    def set_rotation(self, rotation):
        raise NotImplementedError

    def set_selection_mode(self, mode):
        raise NotImplementedError

    def set_selected(self, position):
        raise NotImplementedError

    def set_selected_area(self, area):
        raise NotImplementedError

    def set_double_buffer(self, enabled):
        raise NotImplementedError

    def set_display_mode(self, mode):
        raise NotImplementedError

    def set_trihedron_mode(self, mode):
        raise NotImplementedError

    def set_view_mode(self, mode):
        raise NotImplementedError

    def set_shadows(self, enabled):
        raise NotImplementedError

    def set_reflections(self, enabled):
        raise NotImplementedError

    def set_antialiasing(self, enabled):
        raise NotImplementedError

    def set_raytracing(self, enabled):
        raise NotImplementedError

    def set_draw_boundaries(self, enabled):
        raise NotImplementedError

    def set_hlr(self, enabled):
        raise NotImplementedError

    def set_lock_rotation(self, locked):
        raise NotImplementedError

    def set_lock_zoom(self, locked):
        raise NotImplementedError

    def fit_all(self):
        raise NotImplementedError

    def fit_selection(self):
        raise NotImplementedError

    def take_screenshot(self, filename):
        raise NotImplementedError

    def zoom_factor(self, zoom):
        raise NotImplementedError

    def rotate_view(self, x=0, y=0, z=0):
        raise NotImplementedError

    def turn_view(self, x=0, y=0, z=0):
        raise NotImplementedError

    def reset_view(self):
        raise NotImplementedError


class OccViewer(Control):
    """ A widget to view OpenCascade shapes.
    """
    #: A reference to the ProxySpinBox object.
    proxy = Typed(ProxyOccViewer)

    #: Bounding box of displayed shapes. A tuple of the following values
    #: (xmin, ymin, zmin, xmax, ymax, zmax).
    bbox = d_(Typed(BBox), writable=False)

    #: Display mode
    display_mode = d_(Enum('shaded', 'wireframe'))

    #: Selection mode
    selection_mode = d_(Enum(
        'shape', 'shell', 'face', 'edge', 'wire', 'vertex'))

    #: Selected items
    selection = d_(Typed(ViewerSelection), writable=False)


    #: View direction
    view_mode = d_(Enum('iso', 'top', 'bottom', 'left', 'right', 'front',
                        'rear'))

    #: Selection event
    #reset_view = d_(Event(),writable=False)

    #: Show tahedron
    trihedron_mode = d_(Enum('right-lower', 'right-upper', 'left-lower',
                             'left-upper'))

    #: Background gradient this is corecred from a of strings
    background_gradient = d_(Coerced(tuple, coercer=gradient_coercer))

    def _default_background_gradient(self):
        return (parse_color('white'), parse_color('silver'))

    #: Default shape rendering color if none is defined
    shape_color = d_(ColorMember('steelblue'))

    #: Display shadows
    shadows = d_(Bool(False))

    #: Display reflections
    reflections = d_(Bool(True))

    #: Enable antialiasing
    antialiasing = d_(Bool(True))

    #: Enable raytracing
    raytracing = d_(Bool(False))

    #: Enable hidden line removal
    hlr = d_(Bool(False))

    #: Draw face boundaries
    draw_boundaries = d_(Bool(True))

    #: View expands freely in width by default.
    hug_width = set_default('ignore')

    #: View expands freely in height by default.
    hug_height = set_default('ignore')

    #: Lock rotation so the mouse cannot not rotate
    lock_rotation = d_(Bool())

    #: Lock zoom so the mouse wheel cannot not zoom
    lock_zoom = d_(Bool())

    #: Events
    #: Raise StopIteration to indicate handling should stop
    key_pressed = d_(Event(), writable=False)
    mouse_pressed = d_(Event(), writable=False)
    mouse_released = d_(Event(), writable=False)
    mouse_wheeled = d_(Event(), writable=False)
    mouse_moved = d_(Event(), writable=False)


    #: Loading status
    loading = d_(Bool(), writable=False)
    progress = d_(Float(strict=False), writable=False)

    # -------------------------------------------------------------------------
    # Observers
    # -------------------------------------------------------------------------
    @observe('position', 'display_mode', 'view_mode', 'trihedron_mode',
             'selection_mode', 'background_gradient', 'double_buffer',
             'shadows', 'reflections', 'antialiasing', 'lock_rotation',
             'lock_zoom', 'draw_boundaries', 'hlr', 'shape_color')
    def _update_proxy(self, change):
        """ An observer which sends state change to the proxy.
        """
        # The superclass handler implementation is sufficient.
        super(OccViewer, self)._update_proxy(change)

    # -------------------------------------------------------------------------
    # Viewer API
    # -------------------------------------------------------------------------
    def fit_all(self):
        """ Zoom in and center on all item(s) """
        self.proxy.fit_all()

    def fit_selection(self):
        """ Zoom in and center on the selected item(s) """
        self.proxy.fit_selection()

    def take_screenshot(self, filename):
        """ Take a screenshot and save it with the given filename """
        self.proxy.take_screenshot(filename)

    def zoom_factor(self, factor):
        """ Zoom in by a given factor """
        self.proxy.zoom_factor(factor)

    def rotate_view(self, *args, **kwargs):
        """ Rotate by the given number of degrees about the current axis"""
        self.proxy.rotate_view(*args, **kwargs)

    def turn_view(self, *args, **kwargs):
        """ Rotate by the given number of degrees about the current axis"""
        self.proxy.turn_view(*args, **kwargs)

    def reset_view(self):
        """ Reset zoom to defaults """
        self.proxy.reset_view()

    def clear_display(self):
        """ Clear the display, all children should be removed before calling
        this or they'll be rerendered.
        """
        self.proxy.clear_display()
