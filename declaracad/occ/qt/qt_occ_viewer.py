"""
Copyright (c) 2016-2020, Jairus Martin.

Distributed under the terms of the GPL v3 License.

The full license is in the file LICENSE, distributed with this software.

Created on Sep 26, 2016

"""
import os
import sys
import logging
import traceback
from datetime import datetime
from contextlib import contextmanager
from atom.api import List, Dict, Typed, Int, Value, Property, Bool

from enaml.qt import QtCore, QtGui
from enaml.qt.QtWidgets import QOpenGLWidget
from enaml.qt.QtCore import Qt, QRect
from enaml.qt.QtGui import QPainter, QPalette
from enaml.qt.qt_control import QtControl
from enaml.qt.qt_toolkit_object import QtToolkitObject
from enaml.application import deferred_call, timed_call, Application


from OCCT import Aspect, Graphic3d, TopAbs, V3d
from OCCT import __version__ as OCCT_VERSION

from OCCT.AIS import (
    AIS_InteractiveContext, AIS_Shape, AIS_Shaded, AIS_WireFrame,
    AIS_ColoredDrawer, AIS_TexturedShape,
)
from OCCT.Aspect import (
    Aspect_DisplayConnection, Aspect_TOTP_LEFT_LOWER, Aspect_GFM_VER,
    Aspect_GridType, Aspect_GridDrawMode
)
from OCCT.Bnd import Bnd_Box
from OCCT.BRepBndLib import BRepBndLib
from OCCT.BRepBuilderAPI import (
    BRepBuilderAPI_MakeEdge, BRepBuilderAPI_MakeEdge2d,
    BRepBuilderAPI_MakeFace, BRepBuilderAPI_MakeShape,
    BRepBuilderAPI_MakeVertex
)
from OCCT.Geom import Geom_Curve, Geom_Surface
from OCCT.gp import gp_Pnt, gp_Dir, gp_Ax3
from OCCT.Graphic3d import (
    Graphic3d_MaterialAspect, Graphic3d_StereoMode_QuadBuffer,
    Graphic3d_RM_RASTERIZATION, Graphic3d_RM_RAYTRACING,
    Graphic3d_RenderingParams, Graphic3d_TypeOfShadingModel,
    Graphic3d_StructureManager, Graphic3d_Structure,
    Graphic3d_Camera
)

from OCCT.MeshVS import (
    MeshVS_DA_DisplayNodes, MeshVS_DA_EdgeColor, MeshVS_Mesh,
    MeshVS_MeshPrsBuilder
)
from OCCT.OpenGl import OpenGl_GraphicDriver
from OCCT.Quantity import (
    Quantity_Color, Quantity_NOC_BLACK, Quantity_NOC_WHITE
)
from OCCT.Prs3d import Prs3d_Drawer
from OCCT.PrsMgr import PrsMgr_PresentationManager
from OCCT.TopAbs import TopAbs_FACE, TopAbs_EDGE, TopAbs_WIRE
from OCCT.TCollection import TCollection_AsciiString
from OCCT.TopLoc import TopLoc_Location
from OCCT.V3d import V3d_Viewer, V3d_View, V3d_TypeOfOrientation

from declaracad.occ.qt.utils import (
    color_to_quantity_color, material_to_material_aspect
)
from declaracad.occ.impl.occ_part import OccPart
from declaracad.occ.impl.occ_shape import OccShape
from declaracad.occ.impl.occ_dimension import OccDimension
from declaracad.occ.impl.occ_display import OccDisplayItem
from declaracad.occ.widgets.occ_viewer import (
    ProxyOccViewer, ViewerSelection
)

from declaracad.occ.dimension import Dimension
from declaracad.occ.display import DisplayItem
from declaracad.occ.shape import BBox

from declaracad.core.utils import log

if sys.platform == 'win32':
    from OCCT.WNT import WNT_Window
    V3d_Window = WNT_Window
elif sys.platform == 'darwin':
    from OCCT.Cocoa import Cocoa_Window
    V3d_Window = Cocoa_Window
else:
    if "7.2" in OCCT_VERSION or OCCT_VERSION.startswith("0"):
        from OCCT.XwWindow import Xw_Window
    else:
        from OCCT.Xw import Xw_Window
    V3d_Window = Xw_Window


V3D_VIEW_MODES = {
    'top': V3d.V3d_Zpos,
    'bottom': V3d.V3d_Zneg,
    'left': V3d.V3d_Xneg,
    'right': V3d.V3d_Xpos,
    'front': V3d.V3d_Yneg,
    'back': V3d.V3d_Ypos,
    'iso': V3d.V3d_XposYnegZpos
}

V3D_DISPLAY_MODES = {
    'shaded': AIS_Shaded,
    'wireframe': AIS_WireFrame
}

BLACK = Quantity_Color(Quantity_NOC_BLACK)
WHITE = Quantity_Color(Quantity_NOC_WHITE)


class QtViewer3d(QOpenGLWidget):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._lock_rotation = False
        self._lock_zoom = False
        self._drawbox = None
        self._zoom_area = False
        self._select_area = False
        self._inited = False
        self._leftisdown = False
        self._middleisdown = False
        self._rightisdown = False
        self._selection = None
        self._drawtext = True
        self._select_pen = QtGui.QPen(QtGui.QColor(0, 0, 0), 2)
        self._callbacks = {
            'key_pressed': [],
            'mouse_dragged': [],
            'mouse_scrolled': [],
            'mouse_moved': [],
            'mouse_pressed': [],
            'mouse_released': [],
        }
        self.proxy = None
        self._last_code = None

        # enable Mouse Tracking
        self.setMouseTracking(True)
        # Strong focus
        self.setFocusPolicy(Qt.StrongFocus)

        # required for overpainting the widget
        self.setBackgroundRole(QPalette.NoRole)
        self.setAttribute(Qt.WA_PaintOnScreen)
        self.setAttribute(Qt.WA_NoSystemBackground)

    def get_window_id(self):
        """ Returns an the identifier of the GUI widget.
        """
        hwnd = self.winId()
        if sys.platform == 'win32':
            import ctypes
            ctypes.pythonapi.PyCapsule_New.restype = ctypes.py_object
            ctypes.pythonapi.PyCapsule_New.argtypes = [
                ctypes.c_int, ctypes.c_void_p, ctypes.c_void_p]
            return ctypes.pythonapi.PyCapsule_New(hwnd, None, None)
        return hwnd

    def resizeEvent(self, event):
        self.proxy.v3d_view.MustBeResized()

    def keyPressEvent(self, event):
        if self._fire_event('key_pressed', event):
            return

    def focusInEvent(self, event):
        self.proxy.v3d_view.Redraw()

    def focusOutEvent(self, event):
        self.proxy.v3d_view.Redraw()

    def paintEvent(self, event):
        self.proxy.v3d_view.Redraw()
        # important to allow overpainting of the OCC OpenGL context in Qt

        if self._drawbox:
            painter = QPainter(self)
            painter.setPen(self._select_pen)
            painter.drawRect(QRect(*self._drawbox))

    def wheelEvent(self, event):
        if self._fire_event('mouse_scrolled', event):
            return
        if self._lock_zoom:
            return
        delta = event.angleDelta().y()  # PyQt5
        view = self.proxy.v3d_view
        view.Redraw()
        view.SetZoom(1.25 if delta > 0 else 0.8)

    def dragMoveEvent(self, event):
        if self._fire_event('mouse_dragged', event):
            return

    def _fire_event(self, name, event):
        handled = False
        view = self.proxy.v3d_view
        for cb in self._callbacks.get(name, []):
            # Raise StopIteration to ignore the default handlers
            try:
                cb((view, event))
            except StopIteration:
                handled = True
            except Exception as e:
                log.exception(e)
        return handled

    def mousePressEvent(self, event):
        self.setFocus()
        pos = self.dragStartPos = event.pos()
        if self._fire_event('mouse_pressed', event):
            return
        self.proxy.v3d_view.StartRotation(pos.x(), pos.y())

    def mouseReleaseEvent(self, event):
        if self._fire_event('mouse_released', event):
            return
        # pt = event.pos()

        view = self.proxy.v3d_view
        btn = event.button()

        if btn == Qt.LeftButton:
            pt = event.pos()
            pos = (pt.x(), pt.y())
            shift = event.modifiers() == Qt.ShiftModifier
            area = self._drawbox if self._select_area else None
            self.proxy.update_selection(pos=pos, area=area, shift=shift)
            if area:
                self._select_area = False
        elif btn == Qt.RightButton:
            if self._zoom_area:
                xmin, ymin, dx, dy = self._drawbox
                view.WindowFit(xmin, ymin, xmin + dx, ymin + dy)
                self._zoom_area = False

    def draw_box(self, event):
        tolerance = 2
        pt = event.pos()
        start = self.dragStartPos
        sx, sy = start.x(), start.y()
        dx, dy = pt.x() - sx, pt.y() - start.y()
        if abs(dx) <= tolerance and abs(dy) <= tolerance:
            return
        self._drawbox = (sx, sy, dx, dy)

    def mouseMoveEvent(self, event):
        if self._fire_event('mouse_moved', event):
            return
        pt = event.pos()
        buttons = int(event.buttons())
        modifiers = event.modifiers()
        view = self.proxy.v3d_view
        # ROTATE
        if (buttons == Qt.LeftButton and not modifiers == Qt.ShiftModifier):
            #dx = pt.x() - self.dragStartPos.x()
            #dy = pt.y() - self.dragStartPos.y()
            if not self._lock_rotation:
                view.Rotation(pt.x(), pt.y())
            self._drawbox = None
        # DYNAMIC ZOOM
        elif (buttons == Qt.RightButton and not modifiers == Qt.ShiftModifier):
            view.Redraw()
            view.Zoom(abs(self.dragStartPos.x()), abs(self.dragStartPos.y()),
                      abs(pt.x()), abs(pt.y()))
            self.dragStartPos = pt
            self._drawbox = None
        # PAN
        elif buttons == Qt.MidButton:
            dx = pt.x() - self.dragStartPos.x()
            dy = pt.y() - self.dragStartPos.y()
            self.dragStartPos = pt
            view.Pan(dx, -dy)
            self._drawbox = None
        # DRAW BOX
        # ZOOM WINDOW
        elif (buttons == Qt.RightButton and modifiers == Qt.ShiftModifier):
            self._zoom_area = True
            self.draw_box(event)
        # SELECT AREA
        elif (buttons == Qt.LeftButton and modifiers == Qt.ShiftModifier):
            self._select_area = True
            self.draw_box(event)
        else:
            self._drawbox = None
            ais_context = self.proxy.ais_context
            ais_context.MoveTo(pt.x(), pt.y(), view, True)


class QtOccViewer(QtControl, ProxyOccViewer):

    #: Viewer widget
    widget = Typed(QtViewer3d)

    #: Update count
    _update_count = Int(0)
    _redraw_blocked = Bool()

    #: Displayed Shapes
    _displayed_shapes = Dict()
    _displayed_dimensions = Dict()
    _displayed_graphics = Dict()
    _selected_shapes = List()

    #: Errors
    errors = Dict()

    #: Tuple of (Quantity_Color, transparency)
    shape_color = Typed(tuple)

    #: Grid colors
    grid_colors = Dict()

    #: Shapes
    shapes = Property(lambda self: self.get_shapes(), cached=True)

    #: Dimensions
    dimensions = Typed(set)
    graphics = Typed(set)

    # -------------------------------------------------------------------------
    # OpenCascade specific members
    # -------------------------------------------------------------------------
    display_connection = Typed(Aspect_DisplayConnection)
    v3d_viewer = Typed(V3d_Viewer)
    v3d_view = Typed(V3d_View)

    ais_context = Typed(AIS_InteractiveContext)
    prs3d_drawer = Typed(Prs3d_Drawer)
    prs_mgr = Typed(PrsMgr_PresentationManager)
    v3d_window = Typed(V3d_Window)
    gfx_structure_manager = Typed(Graphic3d_StructureManager)
    gfx_structure = Typed(Graphic3d_Structure)
    graphics_driver = Typed(OpenGl_GraphicDriver)
    camera = Typed(Graphic3d_Camera)

    #: List of lights
    lights = List()

    def get_shapes(self):
        return [c for c in self.children() if not isinstance(c, QtControl)]

    def create_widget(self):
        self.widget = QtViewer3d(parent=self.parent_widget())

    def init_widget(self):
        super().init_widget()
        d = self.declaration
        widget = self.widget
        widget.proxy = self

        if sys.platform == 'win32':
            display = Aspect_DisplayConnection()
        else:
            display_name = TCollection_AsciiString(
                os.environ.get('DISPLAY', '0'))
            display = Aspect_DisplayConnection(display_name)
        self.display_connection = display

        # Create viewer
        graphics_driver = self.graphics_driver = OpenGl_GraphicDriver(display)

        viewer = self.v3d_viewer = V3d_Viewer(graphics_driver)
        view = self.v3d_view = viewer.CreateView()

        # Setup window
        win_id = widget.get_window_id()
        if sys.platform == 'win32':
            window = WNT_Window(win_id)
        elif sys.platform == 'darwin':
            window = Cocoa_Window(win_id)
        else:
            window = Xw_Window(self.display_connection, win_id)
        if not window.IsMapped():
            window.Map()
        self.v3d_window = window
        view.SetWindow(window)

        # Setup viewer
        ais_context = self.ais_context = AIS_InteractiveContext(viewer)
        drawer = self.prs3d_drawer = ais_context.DefaultDrawer()

        # Needed for displaying graphics
        prs_mgr = self.prs_mgr = ais_context.MainPrsMgr()
        gfx_mgr = self.gfx_structure_manager = prs_mgr.StructureManager()
        self.gfx_structure = Graphic3d_Structure(gfx_mgr)

        # Lights camera
        self.camera = view.Camera()
        try:
            self.set_lights(d.lights)
        except Exception as e:
            log.exception(e)
            viewer.SetDefaultLights()

        #viewer.DisplayPrivilegedPlane(True, 1)
        #view.SetShadingModel(Graphic3d_TypeOfShadingModel.V3d_PHONG)

        # background gradient
        with self.redraw_blocked():
            self.set_background_gradient(d.background_gradient)
            self.set_draw_boundaries(d.draw_boundaries)
            self.set_trihedron_mode(d.trihedron_mode)
            self.set_display_mode(d.display_mode)
            self.set_hidden_line_removal(d.hidden_line_removal)
            self.set_selection_mode(d.selection_mode)
            self.set_view_mode(d.view_mode)
            self.set_view_projection(d.view_projection)
            self.set_lock_rotation(d.lock_rotation)
            self.set_lock_zoom(d.lock_zoom)
            self.set_shape_color(d.shape_color)
            self.set_chordial_deviation(d.chordial_deviation)
            self._update_rendering_params()
            self.set_grid_mode(d.grid_mode)
            self.set_grid_colors(d.grid_colors)

            self.init_signals()
            self.dump_gl_info()

        self.redraw()

    def dump_gl_info(self):
        # Debug info
        try:
            ctx = self.graphics_driver.GetSharedContext()
            if ctx is None or not ctx.IsValid():
                return
            v1 = ctx.VersionMajor()
            v2 = ctx.VersionMinor()
            log.info("OpenGL version: {}.{}".format(v1, v2))
            log.info("GPU memory: {}".format(ctx.AvailableMemory()))
            log.info("GPU memory info: {}".format(ctx.MemoryInfo().ToCString()))
            log.info("Max MSAA samples: {}".format(ctx.MaxMsaaSamples()))

            supports_raytracing = ctx.HasRayTracing()
            log.info("Supports ray tracing: {}".format(supports_raytracing))
            if supports_raytracing:
                log.info("Supports textures: {}".format(
                    ctx.HasRayTracingTextures()))
                log.info("Supports adaptive sampling: {}".format(
                    ctx.HasRayTracingAdaptiveSampling()))
                log.info("Supports adaptive sampling atomic: {}".format(
                    ctx.HasRayTracingAdaptiveSamplingAtomic()))
            else:
                ver_too_low = ctx.IsGlGreaterEqual(3, 1)
                if not ver_too_low:
                    log.info("OpenGL version must be >= 3.1")
                else:
                    ext = "GL_ARB_texture_buffer_object_rgb32"
                    if not ctx.CheckExtension(ext):
                        log.info("OpenGL extension {} is missing".format(ext))
                    else:
                        log.info("OpenGL glBlitFramebuffer is missing")
        except Exception as e:
            log.exception(e)

    def init_signals(self):
        d = self.declaration
        callbacks = self.widget._callbacks
        for name in callbacks.keys():
            cb = getattr(d, name, None)
            if cb is not None:
                callbacks[name].append(cb)

    def init_layout(self):
        super().init_layout()
        for child in self.children():
            self.child_added(child, update=False)
        self.update_display()
        self.v3d_view.MustBeResized()

    def child_added(self, child, update=True):
        if isinstance(child, OccShape):
            self.get_member('shapes').reset(self)
            child.observe('shape', self.update_display)
            if update:
                self.update_display()
        elif isinstance(child, OccDimension):
            child.observe('dimension', self.update_display)
            if update:
                self.update_display()
        else:
            return super().child_added(child)

    def child_removed(self, child, update=True):
        if isinstance(child, OccShape):
            self.get_member('shapes').reset(self)
            child.unobserve('shape', self.update_display)
            if update:
                self.update_display()
        elif isinstance(child, OccDimension):
            child.observe('dimension', self.update_display)
            if update:
                self.update_display()
        else:
            return super().child_removed(child)

    # -------------------------------------------------------------------------
    # Viewer API
    # -------------------------------------------------------------------------
    def get_bounding_box(self, shapes):
        """ Compute the bounding box for the given list of shapes.
        Return values are in 3d coordinate space.

        Parameters
        ----------
        shapes: List
            A list of TopoDS_Shape to compute a bbox for

        Returns
        -------
        bbox: Tuple
            A tuple of (xmin, ymin, zmin, xmax, ymax, zmax).

        """
        bbox = Bnd_Box()
        for shape in shapes:
            BRepBndLib.Add_(shape, bbox)
        try:
            pmin = bbox.CornerMin()
            pmax = bbox.CornerMax()
        except RuntimeError:
            return (0, 0, 0, 0, 0, 0)
        return (pmin.X(), pmin.Y(), pmin.Z(), pmax.X(), pmax.Y(), pmax.Z())

    def get_screen_coordinate(self, point):
        """ Convert a 3d coordinate to a 2d screen coordinate

        Parameters
        ----------
        (x, y, z): Tuple
            A 3d coordinate
        """
        return self.v3d_view.Convert(point[0], point[1], point[2], 0, 0)

    def set_chordial_deviation(self, deviation):
        # Turn up tesselation defaults
        self.prs3d_drawer.SetMaximalChordialDeviation(deviation)

    # -------------------------------------------------------------------------
    # Rendering parameters
    # -------------------------------------------------------------------------
    def set_lights(self, lights):
        viewer = self.v3d_viewer
        new_lights = []

        for d in lights:
            color, _ = color_to_quantity_color(d.color)
            if d.type == "directional":
                if '_' in d.orientation:
                    attr = 'V3d_TypeOfOrientation_{}'.format(d.orientation)
                else:
                    attr = 'V3d_{}'.format(d.orientation)
                orientation = getattr(
                    V3d.V3d_TypeOfOrientation, attr, V3d.V3d_Zneg)
                light = V3d.V3d_DirectionalLight(
                    orientation, color, d.headlight)
            elif d.type == "spot":
                light = V3d.V3d_SpotLight(d.position, d.direction, color)
                light.SetAngle(d.angle)
            else:
                light = V3d.V3d_AmbientLight(color)
            light.SetIntensity(d.intensity)

            if d.range:
                light.SetRange(d.range)

            viewer.AddLight(light)
            if d.enabled:
                viewer.SetLightOn(light)
            new_lights.append(light)

        for light in self.lights:
            viewer.DelLight(self.light)

        self.lights = new_lights

    def set_draw_boundaries(self, enabled):
        self.prs3d_drawer.SetFaceBoundaryDraw(enabled)

    def set_hidden_line_removal(self, enabled):
        view = self.v3d_view
        view.SetComputedMode(enabled)
        self.redraw()

    def set_antialiasing(self, enabled):
        self._update_rendering_params()

    def set_shadows(self, enabled):
        self._update_rendering_params()

    def set_reflections(self, enabled):
        self._update_rendering_params()

    def set_raytracing(self, enabled):
        self._update_rendering_params()

    def set_raytracing_depth(self, depth):
        self._update_rendering_params()

    def _update_rendering_params(self, **params):
        """ Set the rendering parameters of the view

        Parameters
        ----------
        **params:
            See Graphic3d_RenderingParams members

        """
        d = self.declaration
        view = self.v3d_view
        rendering_params = view.ChangeRenderingParams()
        if d.raytracing:
            method = Graphic3d_RM_RAYTRACING
        else:
            method = Graphic3d_RM_RASTERIZATION

        defaults = dict(
            Method=method,
            RaytracingDepth=d.raytracing_depth,
            #IsGlobalIlluminationEnabled=d.raytracing,
            IsShadowEnabled=d.shadows,
            IsReflectionEnabled=d.reflections,
            IsAntialiasingEnabled=d.antialiasing,
            IsTransparentShadowEnabled=d.shadows,
            NbMsaaSamples=4,
            StereoMode=Graphic3d_StereoMode_QuadBuffer,
            AnaglyphFilter=Graphic3d_RenderingParams.Anaglyph_RedCyan_Optimized,
            ToReverseStereo=False
        )
        defaults.update(**params)
        for attr, v in defaults.items():
            setattr(rendering_params, attr, v)
        self.redraw()

    def set_background_gradient(self, gradient):
        """ Set the background gradient

        Parameters
        ----------
        gradient: Tuple
            Gradient parameters Color 1, Color 2, and optionally th fill method

        """
        c1, _ = color_to_quantity_color(gradient[0])
        c2, _ = color_to_quantity_color(gradient[1])
        fill_method = Aspect_GFM_VER
        if len(gradient) == 3:
            attr = 'Aspect_GFM_{}'.format(gradient[2].upper())
            fill_method = getattr(Aspect, attr, Aspect_GFM_VER)
        self.v3d_view.SetBgGradientColors(c1, c2, fill_method, True)

    def set_shape_color(self, color):
        self.shape_color = color_to_quantity_color(color)

    def set_trihedron_mode(self, mode):
        attr = 'Aspect_TOTP_{}'.format(mode.upper().replace("-", "_"))
        position = getattr(Aspect, attr)
        self.v3d_view.TriedronDisplay(position, BLACK, 0.1, V3d.V3d_ZBUFFER)
        self.redraw()

    def set_grid_mode(self, mode):
        if not mode:
            self.v3d_viewer.DeactivateGrid()
        else:
            a, b = mode.title().split("-")
            grid_type = getattr(Aspect_GridType, f'Aspect_GT_{a}')
            grid_mode = getattr(Aspect_GridDrawMode, f'Aspect_GDM_{b}')
            self.v3d_viewer.ActivateGrid(grid_type, grid_mode)

    def set_grid_colors(self, colors):
        c1, _ = color_to_quantity_color(colors[0])
        c2, _ = color_to_quantity_color(colors[1])
        grid = self.v3d_viewer.Grid()
        grid.SetColors(c1, c2)

    # -------------------------------------------------------------------------
    # Viewer interaction
    # -------------------------------------------------------------------------
    def set_selection_mode(self, mode):
        """ Set the selection mode.

        Parameters
        ----------
        mode: String
            The mode to use (Face, Edge, Vertex, Shell, or Solid)

        """
        ais_context = self.ais_context
        ais_context.Deactivate()
        if mode == 'any':
            for mode in (TopAbs.TopAbs_SHAPE, TopAbs.TopAbs_SHELL,
                         TopAbs.TopAbs_FACE, TopAbs.TopAbs_EDGE,
                         TopAbs.TopAbs_WIRE, TopAbs.TopAbs_VERTEX):
                ais_context.Activate(AIS_Shape.SelectionMode_(mode))
            return
        attr = 'TopAbs_%s' % mode.upper()
        mode = getattr(TopAbs, attr, TopAbs.TopAbs_SHAPE)
        ais_context.Activate(AIS_Shape.SelectionMode_(mode))

    def set_display_mode(self, mode):
        mode = V3D_DISPLAY_MODES.get(mode)
        if mode is None:
            return
        self.ais_context.SetDisplayMode(mode, True)
        self.redraw()

    def set_view_mode(self, mode):
        """ Set the view mode or (or direction)

        Parameters
        ----------
        mode: String
            The mode to or direction to view.

        """
        mode = V3D_VIEW_MODES.get(mode.lower())
        if mode is None:
            return
        self.v3d_view.SetProj(mode)

    def set_view_projection(self, mode):
        mode = getattr(Graphic3d_Camera, 'Projection_%s' % mode.title())
        self.camera.SetProjectionType(mode)
        self.redraw()

    def set_lock_rotation(self, locked):
        self.widget._lock_rotation = locked

    def set_lock_zoom(self, locked):
        self.widget._lock_zoom = locked

    def zoom_factor(self, factor):
        self.v3d_view.SetZoom(factor)

    def rotate_view(self, x=0, y=0, z=0):
        self.v3d_view.Rotate(x, y, z, True)

    def turn_view(self, x=0, y=0, z=0):
        self.v3d_view.Turn(x, y, z, True)

    def fit_all(self):
        view = self.v3d_view
        view.FitAll()
        view.ZFitAll()
        self.redraw()

    def fit_selection(self):
        if not self._selected_shapes:
            return

        # Compute bounding box of the selection
        view = self.v3d_view
        pad = 20
        bbox = self.get_bounding_box(self._selected_shapes)
        xmin, ymin = self.get_screen_coordinate(bbox[0:3])
        xmax, ymax = self.get_screen_coordinate(bbox[3:6])
        cx, cy = int(xmin+(xmax-xmin)/2), int(ymin+(ymax-ymin)/2)
        self.ais_context.MoveTo(cx, cy, view, True)
        view.WindowFit(xmin-pad, ymin-pad, xmax+pad, ymax+pad)

    def take_screenshot(self, filename):
        return self.v3d_view.Dump(filename)

    # -------------------------------------------------------------------------
    # Display Handling
    # -------------------------------------------------------------------------
    def display_ais(self, ais_shape, update=True):
        """ Display an AIS_Shape.

        Parameters
        ----------
        ais_shape: OCCT.AIS.AIS_Shape
            The AIS shape to display.
        update: Bool
            Option to update the viewer.
        """
        self.ais_context.Display(ais_shape, update)

    def display_shape(self, shape, color=None, transparency=None,
                      material=None, texture=None, update=True):
        """ Display a shape.

        Parameters
        ----------
        shape: OCCT.TopoDS.TopoDS_Shape
            The shape to display
        color: collections.Sequence(float) or OCCT.Quantity.Quantity_Color
            The enaml color
        transparency: float
            The transparency (0 to 1).
        material: String
            The material to render the shape.
        texture: declaracad.occ.shape.Texture
            The texture to apply to the shape.

        Returns
        -------
        ais_shape: OCCT.AIS.AIS_Shape
            The AIS_Shape created for the part.
        """
        if texture is not None:
            ais_shape = AIS_TexturedShape(shape)

            if os.path.exists(texture.path):

                ais_shape.SetTextureFileName(
                    TCollection_AsciiString(texture.path))

                params = texture.repeat
                ais_shape.SetTextureRepeat(params.enabled, params.u, params.v)

                params = texture.origin
                ais_shape.SetTextureOrigin(params.enabled, params.u, params.v)

                params = texture.scale
                ais_shape.SetTextureScale(params.enabled, params.u, params.v)

                ais_shape.SetTextureMapOn()
                ais_shape.SetDisplayMode(3)

        else:
            ais_shape = AIS_Shape(shape)

        if color:
            color, alpha = color_to_quantity_color(color)
            ais_shape.SetColor(color)
            if alpha is not None:
                ais_shape.SetTransparency(alpha)
        elif material is None and texture is None:
            color, alpha = self.shape_color
            ais_shape.SetColor(color)
            if alpha is not None:
                ais_shape.SetTransparency(alpha)

        if transparency is not None:
            ais_shape.SetTransparency(transparency)

        ma = material_to_material_aspect(material)
        ais_shape.SetMaterial(ma)

        try:
            self.ais_context.Display(ais_shape, update)
        except RuntimeError as e:
            log.exception(e)
            self.errors[shape] = e
        return ais_shape

    def display_geom(self, geom, color=None, transparency=None,
                     material=None, update=True):
        """ Display a geometric entity.

        Parameters
        ----------
        geom: OCCT.gp.gp_Pnt or OCCT.Geom.Geom_Curve or OCCT.Geom.Geom_Surface
            The shape to display
        color: enaml.color.Color
            An enaml color
        transparency: float
            The transparency (0 to 1).
        material: OCCT.Graphic3d.Graphic3d_NameOfMaterial
            The material.

        Returns
        -------
        result: AIS_Shape or None
            The AIS_Shape created for the geometry. Returns *None* if the
            entity cannot be converted to a shape.
        """
        if isinstance(geom, gp_Pnt):
            shape = BRepBuilderAPI_MakeVertex(geom).Vertex()
        elif isinstance(geom, Geom_Curve):
            shape = BRepBuilderAPI_MakeEdge(geom).Edge()
        elif isinstance(geom, Geom_Surface):
            shape = BRepBuilderAPI_MakeFace(geom, 1.0e-7).Face()
        else:
            return None

        return self.display_shape(shape, color, transparency, material, update)

    def display_mesh(self, mesh, mode=2):
        """ Display a mesh.

        Parameters
        ----------
        mesh: OCCT.SMESH_SMESH_Mesh or OCCT.SMESH_SMESH_subMesh
            The mesh.
        mode: int
            Display mode for mesh elements (1=wireframe, 2=solid).

        Returns
        -------
        result: OCCT.MeshVS.MeshVS_Mesh
            The mesh created.
        """
        vs_link = SMESH_MeshVSLink(mesh)
        mesh_vs = MeshVS_Mesh()
        mesh_vs.SetDataSource(vs_link)
        prs_builder = MeshVS_MeshPrsBuilder(mesh_vs)
        mesh_vs.AddBuilder(prs_builder)
        mesh_vs_drawer = mesh_vs.GetDrawer()
        mesh_vs_drawer.SetBoolean(MeshVS_DA_DisplayNodes, False)
        mesh_vs_drawer.SetColor(MeshVS_DA_EdgeColor, BLACK)
        mesh_vs.SetDisplayMode(mode)
        self.ais_context.Display(mesh_vs, True)
        return mesh_vs

    def update_selection(self, pos, area, shift):
        """ Update the selection state

        """
        d = self.declaration
        widget = self.widget
        view = self.v3d_view
        ais_context = self.ais_context

        if area:
            xmin, ymin, dx, dy = area
            ais_context.Select(xmin, ymin, xmin + dx, ymin + dy, view, True)
        elif shift:
            # multiple select if shift is pressed
            ais_context.ShiftSelect(True)
        else:
            ais_context.Select(True)
        ais_context.InitSelected()

        # Lookup the shape declrations based on the selection context
        selection = {}
        shapes = []
        displayed_shapes = self._displayed_shapes
        occ_shapes = self._displayed_shapes.values()
        while ais_context.MoreSelected():
            if ais_context.HasSelectedShape():
                i = None
                found = False
                topods_shape = ais_context.SelectedShape()
                shape_type = topods_shape.ShapeType()
                attr = str(shape_type).split("_")[-1].lower() + 's'

                # Try quick lookup
                occ_shape = displayed_shapes.get(topods_shape)
                if occ_shape:
                    shapes.append(topods_shape)
                    selection[occ_shape.declaration] = {
                        'shapes': {0: topods_shape}}
                    found = True
                else:
                    # Try long lookup based on topology
                    for occ_shape in occ_shapes:
                        shape_list = getattr(occ_shape.topology, attr, None)
                        if shape_list is None:
                            continue
                        if topods_shape in shape_list:
                            declaration = occ_shape.declaration
                            shapes.append(topods_shape)
                            i = shape_list.index(topods_shape)

                            # Insert what was selected into the options
                            if declaration not in selection:
                                selection[declaration] = {}
                            info = selection[declaration]
                            if attr not in info:
                                info[attr] = {}
                            info[attr][i] = topods_shape
                            found = True
                            break

                # Mark it as found we don't know what shape it's from
                if not found:
                    if None not in selection:
                        selection[None] = {}
                    if attr not in selection[None]:
                        selection[None][attr] = {}
                    info = selection[None][attr]
                    # Just keep incrementing the index
                    info[len(info)] = topods_shape

            ais_context.NextSelected()

        if shift:
            ais_context.UpdateSelected(True)
        # Set selection
        self._selected_shapes = shapes
        d.selection = ViewerSelection(
            selection=selection, position=pos, area=area)

    def update_display(self, change=None):
        """ Queue an update request """
        self._update_count += 1
        timed_call(1, self._do_update)

    def clear_display(self):
        """ Remove all shapes and dimensions drawn """
        # Erase all just hides them
        remove = self.ais_context.Remove
        for occ_shape in self._displayed_shapes.values():
            remove(occ_shape.ais_shape, False)
        for ais_dim in self._displayed_dimensions.keys():
            remove(ais_dim, False)
        self.gfx_structure.Clear()
        self.ais_context.UpdateCurrentViewer()

    def reset_view(self):
        """ Reset to default zoom and orientation """
        self.v3d_view.Reset()

    @contextmanager
    def redraw_blocked(self):
        """ Temporarily stop redraw during """
        self._redraw_blocked = True
        yield
        self._redraw_blocked = False

    def redraw(self):
        if not self._redraw_blocked:
            self.v3d_view.Redraw()

    def _expand_shapes(self, shapes, dimensions, graphics):
        expansion = []
        for s in shapes:
            if isinstance(s, OccPart):
                if s.declaration.display:
                    subshapes = self._expand_shapes(
                        s.children(), dimensions, graphics)
                    expansion.extend(subshapes)
            elif isinstance(s, OccShape):
                if s.declaration.display:
                    expansion.append(s)
                    for c in s.declaration.traverse():
                        if isinstance(c, Dimension):
                            dimensions.add(c.proxy)
                        elif isinstance(c, DisplayItem):
                            graphics.add(c.proxy)
            elif isinstance(s, OccDimension):
                dimensions.add(s)
            elif isinstance(s, OccDisplayItem):
                graphics.add(s)
        return expansion

    def _do_update(self):
        # Only update when all changes are done
        self._update_count -= 1
        if self._update_count != 0:
            return

        qtapp = Application.instance()._qapp
        start_time = datetime.now()

        declaration = self.declaration
        declaration.loading = True
        self.errors = {}
        try:
            view = self.v3d_view

            self.clear_display()
            log.debug("Rendering...")

            #: Expand all parts otherwise we lose the material information
            dimensions = self.dimensions = set()
            graphics = self.graphics = set()
            shapes = self._expand_shapes(self.children(), dimensions, graphics)

            if not shapes:
                log.debug("No shapes to display")
                return

            displayed_shapes = {}
            ais_shapes = []
            self.set_selection_mode(declaration.selection_mode)
            n = len(shapes)
            for i, occ_shape in enumerate(shapes):
                qtapp.processEvents()
                if self._update_count != 0:
                    log.debug("Aborted!")
                    return  # Another update coming abort

                d = occ_shape.declaration
                topods_shape = occ_shape.shape
                if not topods_shape or topods_shape.IsNull():
                    log.error("{} has no shape!".format(occ_shape))
                    continue

                # Translate part locations
                parent = occ_shape.parent()
                if parent and isinstance(parent, OccPart) \
                        and not topods_shape.Locked():

                    # Build transform for nested parts
                    l = topods_shape.Location()
                    while isinstance(parent, OccPart):
                        l = parent.location.Multiplied(l)
                        parent = parent.parent()

                    topods_shape.Location(l)

                    # HACK: Prevent doing this multiple times when the view is
                    # force updated and the same part is rendered
                    topods_shape.Locked(True)

                # Save the mapping of topods_shape to declaracad shape
                displayed_shapes[topods_shape] = occ_shape

                declaration.progress = min(100, max(0, i * 100 / n))
                ais_shape = self.display_shape(
                    topods_shape,
                    d.color,
                    d.transparency,
                    d.material if d.material.name else None,
                    d.texture,
                    update=False)

                occ_shape.ais_shape = ais_shape
                if ais_shape:
                    ais_shapes.append(ais_shape)

            # Display all dimensions
            displayed_dimensions = {}
            if dimensions:
                log.debug(f"Adding {len(dimensions)} dimensions...")
                for item in dimensions:
                    dim = item.dimension
                    if dim is not None and item.declaration.display:
                        displayed_dimensions[dim] = item
                        self.display_ais(dim, update=False)

            displayed_graphics = {}
            if graphics:
                log.debug(f"Adding {len(graphics)} graphics...")
                for item in graphics:
                    if not item.declaration.display:
                        continue
                    context = self.gfx_structure.NewGroup()
                    item.create_item(context)
                self.gfx_structure.Display()

            self.ais_context.UpdateCurrentViewer()

            self._displayed_shapes = displayed_shapes
            self._displayed_dimensions = displayed_dimensions
            self._displayed_graphics = displayed_graphics

            # Update bounding box
            bbox = self.get_bounding_box(displayed_shapes.keys())
            declaration.bbox = BBox(*bbox)
            declaration.progress = 100
            log.debug("Took: {}".format(datetime.now() - start_time))
        except Exception as e:
            log.error("Failed to display shapes: ")
            log.exception(e)
            self.errors[None] = e
        finally:
            declaration.loading = False
            declaration.errors = self.errors
