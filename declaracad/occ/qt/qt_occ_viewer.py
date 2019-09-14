"""
Copyright (c) 2015, Jairus Martin.
Distributed under the terms of the MIT License.
The full license is in the file COPYING.txt, distributed with this software.
Created on Sep 26, 2016

Based on https://github.com/tpaviot/pythonocc-core/
            blob/master/src/addons/Display/qtDisplay.py

"""
import sys
import logging
import traceback
from atom.api import List, Dict, Typed, Int, Value, Property, Bool

from enaml.qt import QtCore, QtGui
from enaml.qt.QtWidgets import QOpenGLWidget
from enaml.qt.QtCore import Qt, QRect
from enaml.qt.QtGui import QPainter
from enaml.qt.qt_control import QtControl
from enaml.qt.qt_toolkit_object import QtToolkitObject
from enaml.application import deferred_call, timed_call


from OCCT import Aspect, Graphic3d, TopAbs, V3d
from OCCT.AIS import (
    AIS_InteractiveContext, AIS_Shape, AIS_Shaded, AIS_WireFrame
)
from OCCT.Aspect import (
    Aspect_DisplayConnection, Aspect_TOTP_LEFT_LOWER, Aspect_GFM_VER
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
    Graphic3d_MaterialAspect, Graphic3d_RM_RASTERIZATION,
    Graphic3d_StereoMode_QuadBuffer, Graphic3d_RenderingParams
)

from OCCT.MeshVS import (
    MeshVS_DA_DisplayNodes, MeshVS_DA_EdgeColor, MeshVS_Mesh,
    MeshVS_MeshPrsBuilder
)
from OCCT.OpenGl import OpenGl_GraphicDriver
from OCCT.Quantity import Quantity_Color, Quantity_NOC_BLACK
from OCCT.TopoDS import TopoDS_Shape
from OCCT.V3d import V3d_Viewer, V3d_View, V3d_TypeOfOrientation

from .utils import color_to_quantity_color
from ..impl.occ_part import OccPart
from ..widgets.occ_viewer import ProxyOccViewer, ViewerSelectionEvent
from ..shape import BBox

from declaracad.core.utils import log

if sys.platform == 'win32':
    from OCCT.WNT import WNT_Window
    V3d_Window = WNT_Window
elif sys.platform == 'darwin':
    from OCCT.Cocoa import CocoaWindow
    V3d_Window = CocoaWindow
else:
    from OCCT.XwWindow import Xw_Window
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

#class Display(OCCViewer.Viewer3d):

    #def DisplayShape(self, shapes, material=None, texture=None, color=None,
                     #transparency=None, update=False, fit=False):
        #if a gp_Pnt is passed, first convert to vertex
        #if issubclass(shapes.__class__, OCCViewer.gp_Pnt):
            #vertex = OCCViewer.BRepBuilderAPI_MakeVertex(shapes)
            #shapes = [vertex.Shape()]
            #SOLO = True
        #elif isinstance(shapes, OCCViewer.gp_Pnt2d):
            #vertex = OCCViewer.BRepBuilderAPI_MakeVertex(
                #OCCViewer.gp_Pnt(shapes.X(), shapes.Y(), 0))
            #shapes = [vertex.Shape()]
            #SOLO = True
        #if a Geom_Curve is passed
        #elif callable(getattr(shapes, "GetHandle", None)):
            #handle = shapes.GetHandle()
            #if issubclass(handle.__class__, OCCViewer.Handle_Geom_Curve):
                #edge = BRepBuilderAPI_MakeEdge(handle)
                #shapes = [edge.Shape()]
                #SOLO = True
            #elif issubclass(handle.__class__, OCCViewer.Handle_Geom2d_Curve):
                #edge2d = BRepBuilderAPI_MakeEdge2d(handle)
                #shapes = [edge2d.Shape()]
                #SOLO = True
            #elif issubclass(handle.__class__, OCCViewer.Handle_Geom_Surface):
                #bounds = True
                #toldegen = 1e-6
                #face = OCCViewer.BRepBuilderAPI_MakeFace()
                #face.Init(handle, bounds, toldegen)
                #face.Build()
                #shapes = [face.Shape()]
                #SOLO = True
        #elif isinstance(shapes, OCCViewer.Handle_Geom_Surface):
            #bounds = True
            #toldegen = 1e-6
            #face = OCCViewer.BRepBuilderAPI_MakeFace()
            #face.Init(shapes, bounds, toldegen)
            #face.Build()
            #shapes = [face.Shape()]
            #SOLO = True
        #elif isinstance(shapes, OCCViewer.Handle_Geom_Curve):
            #edge = OCCViewer.BRepBuilderAPI_MakeEdge(shapes)
            #shapes = [edge.Shape()]
            #SOLO = True
        #elif isinstance(shapes, OCCViewer.Handle_Geom2d_Curve):
            #edge2d = OCCViewer.BRepBuilderAPI_MakeEdge2d(shapes)
            #shapes = [edge2d.Shape()]
            #SOLO = True
        #elif issubclass(shapes.__class__, OCCViewer.TopoDS_Shape):
            #shapes = [shapes]
            #SOLO = True
        #else:
            #SOLO = False

        #ais_shapes = []

        #for shape in shapes:
            #if material or texture:
                #if texture:
                    #self.View.SetSurfaceDetail(OCCViewer.OCC.V3d.V3d_TEX_ALL)
                    #shape_to_display = OCCViewer.OCC.AIS.AIS_TexturedShape(
                        #shape)
                    #(filename, toScaleU, toScaleV, toRepeatU, toRepeatV,
                        #originU, originV) = texture.GetProperties()
                    #shape_to_display.SetTextureFileName(
                        #OCCViewer.TCollection_AsciiString(filename))
                    #shape_to_display.SetTextureMapOn()
                    #shape_to_display.SetTextureScale(True, toScaleU, toScaleV)
                    #shape_to_display.SetTextureRepeat(True, toRepeatU,
                                                      #toRepeatV)
                    #shape_to_display.SetTextureOrigin(True, originU, originV)
                    #shape_to_display.SetDisplayMode(3)
                #elif material:
                    #shape_to_display = OCCViewer.AIS_Shape(shape)
                    #shape_to_display.SetMaterial(material)
            #else:
                #TODO: can we use .Set to attach all TopoDS_Shapes
                #to this AIS_Shape instance?
                #shape_to_display = OCCViewer.AIS_Shape(shape)

            #ais_shapes.append(shape_to_display.GetHandle())

        #if not SOLO:
            #computing graphic properties is expensive
            #if an iterable is found, so cluster all TopoDS_Shape under
            #an AIS_MultipleConnectedInteractive
            #shape_to_display = OCCViewer.AIS_MultipleConnectedInteractive()
            #for i in ais_shapes:
                #shape_to_display.Connect(i)

        #set the graphic properties
        #if material is None:
            #The default material is too shiny to show the object
            #color well, so I set it to something less reflective
            #shape_to_display.SetMaterial(OCCViewer.Graphic3d_NOM_NEON_GNC)
        #if color:
            #color, transparency = color_to_quantity_color(color)
            #for shp in ais_shapes:
                #self.Context.SetColor(shp, color, False)
        #if transparency:
            #shape_to_display.SetTransparency(transparency)
        #if update:
            #only update when explicitely told to do so
            #self.Context.Display(shape_to_display.GetHandle(), False)
            #especially this call takes up a lot of time...
            #if fit:
                #self.FitAll()
            #self.Redraw()
        #else:
            #self.Context.Display(shape_to_display.GetHandle(), False)

        #if SOLO:
            #return ais_shapes[0]
        #else:
            #return shape_to_display


class QtViewer3d(QOpenGLWidget):
    def __init__(self, *args, **kwargs):
        super(QtViewer3d, self).__init__(*args, **kwargs)
        self._lock_rotation = False
        self._lock_zoom = False
        self._drawbox = False
        self._zoom_area = False
        self._select_area = False
        self._inited = False
        self._leftisdown = False
        self._middleisdown = False
        self._rightisdown = False
        self._selection = None
        self._drawtext = True
        self._select_pen = QtGui.QPen(QtGui.QColor(0, 0, 0), 1)
        self._callbacks = {
            'key_pressed': [],
            'mouse_dragged': [],
            'mouse_scrolled': [],
            'mouse_moved': [],
            'mouse_pressed': [],
            'mouse_released': [],
        }
        self.proxy = None

        # enable Mouse Tracking
        self.setMouseTracking(True)
        # Strong focus
        self.setFocusPolicy(Qt.WheelFocus)

        # required for overpainting the widget
        self.setAttribute(Qt.WA_PaintOnScreen)
        self.setAttribute(Qt.WA_NoSystemBackground)
        self.setAutoFillBackground(False)

        #self.resize(960, 720)
        #self.setMinimumSize(960, 720)

    def get_window_id(self):
        """ returns an the identifier of the GUI widget.
        It must be an integer
        """
        win_id = self.winId()  # this returns either an int or voitptr
        if sys.platform == "win32" and 'PyCObject' in str(type(win_id)):
            import ctypes
            ctypes.pythonapi.PyCObject_AsVoidPtr.restype = ctypes.c_void_p
            ctypes.pythonapi.PyCObject_AsVoidPtr.argtypes = [ctypes.py_object]
            return ctypes.pythonapi.PyCObject_AsVoidPtr(win_id)
        return win_id

    def resizeEvent(self, e):
        if self._inited:
            self.proxy.v3d_view.MustBeResized()
        return super().resizeEvent(e)

    def keyPressEvent(self, event):
        if self._fire_event('key_pressed', event):
            return
        code = event.key()
        #if code in self._key_map:
        #    self._key_map[code]()
        #else:
        #    msg = "key: {0}\nnot mapped to any function".format(code)
        #    log.info(msg)

    def focusInEvent(self, event):
        if self._inited:
            self.proxy.v3d_view.Redraw()

    def focusOutEvent(self, event):
        if self._inited:
            self.proxy.v3d_view.Redraw()

    def paintEvent(self, event):
        if not self._inited:
            self.proxy.init_window()
            self._inited = True
            return

        self.proxy.ais_context.UpdateCurrentViewer()
        # important to allow overpainting of the OCC OpenGL context in Qt

        if self._drawbox:
            self.makeCurrent()
            painter = QPainter(self)
            painter.setPen(self._select_pen)
            painter.drawRect(QRect(*self._drawbox))
            painter.end()
            self.doneCurrent()

        #self.swapBuffers()

    def wheelEvent(self, event):
        if self._fire_event('mouse_scrolled', event):
            return
        if self._lock_zoom:
            return
        try:
            delta = event.angleDelta().y()  # PyQt5
        except:
            delta = event.delta()  # PyQt4/PySide
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
            #: Raise StopIteration to ignore the default handlers
            try:
                cb((view, event))
            except StopIteration:
                handled = True
            except:
                traceback.print_exc()
                #log.error(traceback.format_exc())
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
        #pt = event.pos()
        modifiers = event.modifiers()
        view = self.proxy.v3d_view

        if event.button() == Qt.LeftButton:
            pt = event.pos()

            area = self._select_area and self._drawbox
            self.proxy.update_selection(
                pos=(pt.x(), pt.y()),
                area=area,
                shift=modifiers == Qt.ShiftModifier)
            if area:
                self._select_area = False

        elif event.button() == Qt.RightButton:
            if self._zoom_area:
                [xmin, ymin, dx, dy] = self._drawbox
                view.WindowFit(xmin, ymin, xmin + dx, ymin + dy)
                self._zoom_area = False

    def DrawBox(self, event):
        tolerance = 2
        pt = event.pos()
        dx = pt.x() - self.dragStartPos.x()
        dy = pt.y() - self.dragStartPos.y()
        if abs(dx) <= tolerance and abs(dy) <= tolerance:
            return
        self._drawbox = [self.dragStartPos.x(), self.dragStartPos.y(), dx, dy]
        self.update()

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
            self._drawbox = False
        # DYNAMIC ZOOM
        elif (buttons == Qt.RightButton and not modifiers == Qt.ShiftModifier):
            view.Redraw()
            view.Zoom(abs(self.dragStartPos.x()), abs(self.dragStartPos.y()),
                      abs(pt.x()), abs(pt.y()))
            self.dragStartPos = pt
            self._drawbox = False
        # PAN
        elif buttons == Qt.MidButton:
            dx = pt.x() - self.dragStartPos.x()
            dy = pt.y() - self.dragStartPos.y()
            self.dragStartPos = pt
            view.Pan(dx, -dy)
            self._drawbox = False
        # DRAW BOX
        # ZOOM WINDOW
        elif (buttons == Qt.RightButton and modifiers == Qt.ShiftModifier):
            self._zoom_area = True
            self.DrawBox(event)
        # SELECT AREA
        elif (buttons == Qt.LeftButton and modifiers == Qt.ShiftModifier):
            self._select_area = True
            self.DrawBox(event)
        else:
            self._drawbox = False
            ais_context = self.proxy.ais_context
            ais_context.MoveTo(pt.x(), pt.y(), view, True)


class QtOccViewer(QtControl, ProxyOccViewer):

    #: Viewer widget
    widget = Typed(QtViewer3d)

    #: Update count
    _update_count = Int(0)

    #: Displayed Shapes
    _displayed_shapes = Dict()
    _ais_shapes = List()

    #: Shapes
    shapes = Property(lambda self: self.get_shapes(), cached=True)


    # -------------------------------------------------------------------------
    # OpenCascade specific members
    # -------------------------------------------------------------------------
    display_connection = Typed(Aspect_DisplayConnection, ())
    v3d_viewer = Typed(V3d_Viewer)
    v3d_view = Typed(V3d_View)

    ais_context = Typed(AIS_InteractiveContext)

    v3d_window = Typed(V3d_Window)

    #def _get_display(self):
        #return self.widget._display

    #: Display
    #display = Property(_get_display, cached=True)

    def get_shapes(self):
        return [c for c in self.children()
                if not isinstance(c, QtToolkitObject)]

    def create_widget(self):
        self.widget = QtViewer3d(parent=self.parent_widget())

    def init_widget(self):
        super().init_widget()
        d = self.declaration
        widget = self.widget
        widget.proxy = self

        # Create viewer
        graphics_driver = OpenGl_GraphicDriver(self.display_connection)
        viewer = self.v3d_viewer = V3d_Viewer(graphics_driver)
        view = self.v3d_view = viewer.CreateView()
        self.ais_context = AIS_InteractiveContext(viewer)

        viewer.SetDefaultLights()
        viewer.SetLightOn()

        # background gradient
        self.set_background_gradient(d.background_gradient)
        self.set_trihedron_mode(d.trihedron_mode)
        self.set_display_mode(d.display_mode)
        self.set_selection_mode(d.selection_mode)
        self.set_view_mode(d.view_mode)
        self.set_lock_rotation(d.lock_rotation)
        self.set_lock_zoom(d.lock_zoom)
        self._update_rendering_params()

        #: Setup callbacks
        #display.register_select_callback(self.on_selection)

        #widget.finalize_display()
        #self.init_window()

        self.init_signals()

    def init_signals(self):
        d = self.declaration
        widget = self.widget
        for name in widget._callbacks.keys():
            if hasattr(d, name):
                cb = getattr(d, name)
                widget._callbacks[name].append(cb)

    def init_layout(self):
        super().init_layout()
        for child in self.children():
            self.child_added(child)

    def init_window(self):
        """ Initialize the window when this widget is first painted
        otherwise the window handle will be invalid.

        """
        widget = self.widget
        win_id = widget.get_window_id()
        # Setup window
        if sys.platform == 'win32':
            window = WNT_Window(win_id)
        elif sys.platform == 'darwin':
            window = Cocoa_Window(win_id)
        else:
            window = Xw_Window(self.display_connection, win_id)
        if not window.IsMapped():
            window.Map()
        self.v3d_view.SetWindow(window)
        self.v3d_window = window

    def child_added(self, child):
        if not isinstance(child, QtToolkitObject):
            self.get_member('shapes').reset(self)
            child.observe('shape', self.update_display)
            self.update_display()
        else:
            super().child_added(child)

    def child_removed(self, child):
        if not isinstance(child, QtToolkitObject):
            self.get_member('shapes').reset(self)
            child.unobserve('shape', self.update_display)
        else:
            super().child_removed(child)

    # -------------------------------------------------------------------------
    # Viewer API
    # -------------------------------------------------------------------------
    def get_bounding_box(self, shapes):
        """ Compute the bounding box for the given list of shapes. Return values
        are in 3d coordinate space.

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
        add = BRepBndLib.Add_
        for shape in shapes:
            add(shape, bbox)
        pmin = bbox.CornerMin()
        pmax = bbox.CornerMax()
        return (pmin.X(), pmin.Y(), pmin.Z(), pmax.X(), pmax.Y(), pmax.Z())

    def get_screen_coordinate(self, point):
        """ Convert a 3d coordinate to a 2d screen coordinate

        Parameters
        ----------
        (x, y, z): Tuple
            A 3d coordinate
        """
        return self.display.View.Convert(*point)

    def set_antialiasing(self, enabled):
        self._update_rendering_params()

    def set_shadows(self, enabled):
        self._update_rendering_params()

    def set_reflections(self, enabled):
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
        defaults = dict(
            Method=Graphic3d_RM_RASTERIZATION,
            RaytracingDepth=3,
            IsShadowEnabled=d.shadows,
            IsReflectionEnabled=d.reflections,
            IsAntialiasingEnabled=d.antialiasing,
            IsTransparentShadowEnabled=d.shadows,
            StereoMode=Graphic3d_StereoMode_QuadBuffer,
            AnaglyphFilter=Graphic3d_RenderingParams.Anaglyph_RedCyan_Optimized,
            ToReverseStereo=False
        )
        defaults.update(**params)
        for attr, v in defaults.items():
            setattr(rendering_params, attr, v)
        view.Redraw()

    def set_background_gradient(self, gradient):
        c1, _ = color_to_quantity_color(gradient[0])
        c2, _ = color_to_quantity_color(gradient[1])
        self.v3d_view.SetBgGradientColors(c1, c2, Aspect_GFM_VER, True)

    def set_trihedron_mode(self, mode):
        attr = 'Aspect_TOTP_{}'.format(mode.upper().replace("-", "_"))
        position = getattr(Aspect, attr)
        color = Quantity_Color(Quantity_NOC_BLACK)
        self.v3d_view.TriedronDisplay(position, color, 0.1, V3d.V3d_ZBUFFER)
        self.ais_context.UpdateCurrentViewer()

    def set_selection_mode(self, mode):
        """ Set the selection mode.

        Parameters
        ----------
        mode: String
            The mode to use (Face, Edge, Vertex, Shell, or Solid)

        """
        ais_context = self.ais_context
        ais_context.CloseAllContexts(False)
        ais_context.OpenLocalContext()
        mode = getattr(TopAbs, 'TopAbs_%s' % mode.upper(), None)
        if mode is None:
            mode = TopAbs.TopAbs_SHAPE
        ais_context.ActivateStandardMode(mode)
        ais_context.UpdateSelected(True)

    def set_display_mode(self, mode):
        if mode == 'shaded':
            self.ais_context.SetDisplayMode(AIS_Shaded, True)
        #elif mode == 'hlr':
        #    self.v3d_view.SetComputedMode(True)
        elif mode == 'wireframe':
            self.ais_context.SetDisplayMode(AIS_WireFrame, True)

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
        self.fit_all()

    def set_lock_rotation(self, locked):
        self.widget._lock_rotation = locked

    def set_lock_zoom(self, locked):
        self.widget._lock_zoom = locked

    def zoom_factor(self, factor):
        self.v3d_view.SetZoom(factor)

    def fit_all(self):
        view = self.v3d_view
        view.FitAll()
        view.ZFitAll()
        view.Redraw()

    def fit_selection(self):
        if not self.selected_shapes:
            return

        # Compute bounding box of the selection
        bbox = self.get_bounding_box(self.display.selected_shapes)
        xmin, ymin = self.get_screen_coordinate(bbox[0:3])
        xmax, ymax = self.get_screen_coordinate(bbox[3:6])
        cx, cy = int(xmin+(xmax-xmin)/2), int(ymin+(ymax-ymin)/2)
        self.display.MoveTo(cx, cy)
        pad = 20
        self.display.ZoomArea(xmin-pad, ymin-pad, xmax+pad, ymax+pad)

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
                      material=None, update=True):
        """ Display a shape.

        Parameters
        ----------
        shape: OCCT.TopoDS.TopoDS_Shape
            The shape to display
        color: collections.Sequence(float) or OCCT.Quantity.Quantity_Color
            The enaml color
        transparency: float
            The transparency (0 to 1).

        material: OCCT.Graphic3d.Graphic3d_NameOfMaterial
            The material to render the shape.

        Returns
        -------
        ais_shape: OCCT.AIS.AIS_Shape
            The AIS_Shape created for the part.
        """
        ais_shape = AIS_Shape(shape)

        if color:
            color, transparency = color_to_quantity_color(color)
            ais_shape.SetColor(color)

        if transparency is not None:
            ais_shape.SetTransparency(transparency)

        if material is not None:
            ma = Graphic3d_MaterialAspect(material)
            ais_shape.SetMaterial(ma)

        self.ais_context.Display(ais_shape, update)
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
        mesh_vs_drawer.SetColor(MeshVS_DA_EdgeColor, self._black)
        mesh_vs.SetDisplayMode(mode)
        self.context.Display(mesh_vs, True)
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
        selection = []
        displayed_shapes = self._displayed_shapes
        while ais_context.MoreSelected():
            if ais_context.HasSelectedShape():
                ais_shape = ais_context.SelectedShape()
                shape = displayed_shapes.get(ais_shape)
                if shape:
                    selection.append(shape.declaration)
            ais_context.NextSelected()

        if shift:
            ais_context.UpdateSelected(True)

        # Set selection
        d.selection(ViewerSelectionEvent(selection=selection))

#     def _queue_update(self,change):
#         self._update_count +=1
#         timed_call(0,self._check_update,change)
#
#     def _dequeue_update(self,change):
#         # Only update when all changes are done
#         self._update_count -=1
#         if self._update_count !=0:
#             return
#         self.update_shape(change)


    def update_display(self, change=None):
        """ Queue an update request """
        self._update_count += 1
        timed_call(10, self._do_update)

    def clear_display(self):
        ais_context = self.ais_context
        # Erase all just hides them
        ais_context.PurgeDisplay()
        ais_context.RemoveAll(True)

    def _expand_shapes(self, shapes):
        expansion = []
        for s in shapes:
            for c in s.children():
                if isinstance(c, OccPart):
                    expansion.extend(self._expand_shapes(c.shapes))
            if hasattr(s, 'shapes'):
                expansion.extend(self._expand_shapes(s.shapes))
            else:
                expansion.append(s)
        return expansion

    def _do_update(self):
        # Only update when all changes are done
        self._update_count -= 1
        if self._update_count != 0:
            return
        #: TO
        try:
            view = self.v3d_view

            self.clear_display()
            displayed_shapes = {}
            ais_shapes = []
            #log.debug("_do_update {}")

            #: Expand all parts otherwise we lose the material information
            shapes = self._expand_shapes(self.shapes[:])
            last_shape = shapes[-1]
            for shape in shapes:
                d = shape.declaration
                if not shape.shape:
                    log.error("{} has no shape property!".format(shape))
                    continue

                try:
                    if isinstance(shape.shape, BRepBuilderAPI_MakeShape):
                        s = shape.shape.Shape()
                    else:
                        s = shape.shape
                except:
                    log.error("{} failed to create shape: {}".format(
                        shape, traceback.format_exc()))
                    continue

                displayed_shapes[s] = shape

                #: If a material is given
                if d.material:
                    material_type = 'Graphic3d_NOM_%s' % d.material.upper()
                    material = getattr(Graphic3d, material_type, None)
                else:
                    material = None

                ais_shape = self.display_shape(
                    s,
                    d.color,
                    d.transparency,
                    material,
                    shape is last_shape)
                if ais_shape:
                    ais_shapes.append(ais_shape)

            self._ais_shapes = ais_shapes
            self._displayed_shapes = displayed_shapes

            # Update bounding box
            # TODO: Is there an API for this?
            bbox = self.get_bounding_box(displayed_shapes.keys())
            self.declaration.bbox = BBox(*bbox)
        except:
            log.error("Failed to display shapes: {}".format(
                traceback.format_exc()))
