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
from atom.api import List, Dict, Typed, Int, Property, Bool

from enaml.qt import QtCore, QtGui
from enaml.qt.QtWidgets import QOpenGLWidget

from enaml.qt.QtCore import Qt
from enaml.qt.qt_control import QtControl
from enaml.qt.qt_toolkit_object import QtToolkitObject
from enaml.application import timed_call

from OCC import Graphic3d, Aspect, V3d
from OCC.Bnd import Bnd_Box
from OCC.BRepBndLib import brepbndlib_Add
from OCC.BRepBuilderAPI import BRepBuilderAPI_MakeShape
from OCC.Display import OCCViewer
from OCC.gp import gp_Pnt, gp_Dir, gp_Ax3
from OCC.Quantity import Quantity_Color, Quantity_TOC_RGB, Quantity_NOC_BLACK

from ..impl.occ_part import OccPart
from ..widgets.occ_viewer import (
    ProxyOccViewer, ViewerSelectionEvent, ProxyOccViewerClippedPlane
)
from ..shape import BBox

log = logging.getLogger('declaracad')


class Display(OCCViewer.Viewer3d):

    def DisplayShape(self, shapes, material=None, texture=None, color=None,
                     transparency=None, update=False, fit=False):
        # if a gp_Pnt is passed, first convert to vertex
        if issubclass(shapes.__class__, OCCViewer.gp_Pnt):
            vertex = OCCViewer.BRepBuilderAPI_MakeVertex(shapes)
            shapes = [vertex.Shape()]
            SOLO = True
        elif isinstance(shapes, OCCViewer.gp_Pnt2d):
            vertex = OCCViewer.BRepBuilderAPI_MakeVertex(
                OCCViewer.gp_Pnt(shapes.X(), shapes.Y(), 0))
            shapes = [vertex.Shape()]
            SOLO = True
        # if a Geom_Curve is passed
        elif callable(getattr(shapes, "GetHandle", None)):
            handle = shapes.GetHandle()
            if issubclass(handle.__class__, OCCViewer.Handle_Geom_Curve):
                edge = OCCViewer.BRepBuilderAPI_MakeEdge(handle)
                shapes = [edge.Shape()]
                SOLO = True
            elif issubclass(handle.__class__, OCCViewer.Handle_Geom2d_Curve):
                edge2d = OCCViewer.BRepBuilderAPI_MakeEdge2d(handle)
                shapes = [edge2d.Shape()]
                SOLO = True
            elif issubclass(handle.__class__, OCCViewer.Handle_Geom_Surface):
                bounds = True
                toldegen = 1e-6
                face = OCCViewer.BRepBuilderAPI_MakeFace()
                face.Init(handle, bounds, toldegen)
                face.Build()
                shapes = [face.Shape()]
                SOLO = True
        elif isinstance(shapes, OCCViewer.Handle_Geom_Surface):
            bounds = True
            toldegen = 1e-6
            face = OCCViewer.BRepBuilderAPI_MakeFace()
            face.Init(shapes, bounds, toldegen)
            face.Build()
            shapes = [face.Shape()]
            SOLO = True
        elif isinstance(shapes, OCCViewer.Handle_Geom_Curve):
            edge = OCCViewer.BRepBuilderAPI_MakeEdge(shapes)
            shapes = [edge.Shape()]
            SOLO = True
        elif isinstance(shapes, OCCViewer.Handle_Geom2d_Curve):
            edge2d = OCCViewer.BRepBuilderAPI_MakeEdge2d(shapes)
            shapes = [edge2d.Shape()]
            SOLO = True
        elif issubclass(shapes.__class__, OCCViewer.TopoDS_Shape):
            shapes = [shapes]
            SOLO = True
        else:
            SOLO = False

        ais_shapes = []

        for shape in shapes:
            if material or texture:
                if texture:
                    self.View.SetSurfaceDetail(OCCViewer.OCC.V3d.V3d_TEX_ALL)
                    shape_to_display = OCCViewer.OCC.AIS.AIS_TexturedShape(
                        shape)
                    (filename, toScaleU, toScaleV, toRepeatU, toRepeatV,
                        originU, originV) = texture.GetProperties()
                    shape_to_display.SetTextureFileName(
                        OCCViewer.TCollection_AsciiString(filename))
                    shape_to_display.SetTextureMapOn()
                    shape_to_display.SetTextureScale(True, toScaleU, toScaleV)
                    shape_to_display.SetTextureRepeat(True, toRepeatU,
                                                      toRepeatV)
                    shape_to_display.SetTextureOrigin(True, originU, originV)
                    shape_to_display.SetDisplayMode(3)
                elif material:
                    shape_to_display = OCCViewer.AIS_Shape(shape)
                    shape_to_display.SetMaterial(material)
            else:
                # TODO: can we use .Set to attach all TopoDS_Shapes
                # to this AIS_Shape instance?
                shape_to_display = OCCViewer.AIS_Shape(shape)

            ais_shapes.append(shape_to_display.GetHandle())

        if not SOLO:
            # computing graphic properties is expensive
            # if an iterable is found, so cluster all TopoDS_Shape under
            # an AIS_MultipleConnectedInteractive
            shape_to_display = OCCViewer.AIS_MultipleConnectedInteractive()
            for i in ais_shapes:
                shape_to_display.Connect(i)

        #set the graphic properties
        if material is None:
            #The default material is too shiny to show the object
            #color well, so I set it to something less reflective
            shape_to_display.SetMaterial(OCCViewer.Graphic3d_NOM_NEON_GNC)
        if color:
            # Convert enaml color to OCC color
            if color.alpha != 255:
                transparency = 1-color.alpha/255.0
            color = Quantity_Color(color.red/255.,
                                   color.green/255.,
                                   color.blue/255., Quantity_TOC_RGB)
            for shp in ais_shapes:
                self.Context.SetColor(shp, color, False)
        if transparency:
            shape_to_display.SetTransparency(transparency)
        if update:
            # only update when explicitely told to do so
            self.Context.Display(shape_to_display.GetHandle(), False)
            # especially this call takes up a lot of time...
            if fit:
                self.FitAll()
            self.Repaint()
        else:
            self.Context.Display(shape_to_display.GetHandle(), False)

        if SOLO:
            return ais_shapes[0]
        else:
            return shape_to_display



class QtBaseViewer(QOpenGLWidget):
    """The base Qt Widget for an OCC viewer
    """

    def __init__(self, parent=None):
        super(QtBaseViewer, self).__init__(parent)
        self._display = None
        self._inited = False

        # enable Mouse Tracking
        self.setMouseTracking(True)
        # Strong focus
        self.setFocusPolicy(Qt.WheelFocus)

        # required for overpainting the widget
        self.setAttribute(Qt.WA_PaintOnScreen)
        self.setAttribute(Qt.WA_NoSystemBackground)
        self.setAutoFillBackground(False)

    def GetHandle(self):
        """ returns an the identifier of the GUI widget.
        It must be an integer
        """
        win_id = self.winId()  # this returns either an int or voitptr

        if "%s" % type(win_id) == "<type 'PyCObject'>":  # PySide
            # with PySide, self.winId() does not return an integer
            if sys.platform == "win32":
                # Be careful, this hack is py27 specific
                # does not work with python31 or higher
                # since the PyCObject api was changed
                import ctypes
                ctypes.pythonapi.PyCObject_AsVoidPtr.restype = ctypes.c_void_p
                ctypes.pythonapi.PyCObject_AsVoidPtr.argtypes = [
                    ctypes.py_object]
                win_id = ctypes.pythonapi.PyCObject_AsVoidPtr(win_id)
        elif type(win_id) is not int:  # PyQt4 or 5
            # below integer cast may be required because self.winId() can
            # returns a sip.voitptr according to the PyQt version used
            # as well as the python version
            win_id = int(win_id)
        return win_id

    def resizeEvent(self, event):
        #super(QtBaseViewer, self).resizeEvent(event)
        if self._inited:
            self._display.OnResize()


class QtViewer3d(QtBaseViewer):
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
        self._callbacks = {
            'key_pressed': [],
            'mouse_dragged': [],
            'mouse_scrolled': [],
            'mouse_moved': [],
            'mouse_pressed': [],
            'mouse_released': [],
        }
        #self.resize(960, 720)
        #self.setMinimumSize(960, 720)
#     def initDriver(self):
#         self._display = OCCViewer.Viewer3d(self.GetHandle())
#         self._display.Create()
#         # background gradient
#         self._display.set_bg_gradient_color(206, 215, 222, 128, 128, 128)
#         # background gradient
#         self._display.display_trihedron()
#         self._display.SetModeShaded()
#         self._display.EnableAntiAliasing()
#         self._inited = True
#         # dict mapping keys to functions
#         self._SetupKeyMap()
#         #
#         self._display.thisown = False

    def _SetupKeyMap(self):
        def set_shade_mode():
            self._display.DisableAntiAliasing()
            self._display.SetModeShaded()

        self._key_map = {ord('W'): self._display.SetModeWireFrame,
                         ord('S'): set_shade_mode,
                         ord('A'): self._display.EnableAntiAliasing,
                         ord('B'): self._display.DisableAntiAliasing,
                         ord('H'): self._display.SetModeHLR,
                         ord('F'): self._display.FitAll,
                         ord('G'): self._display.SetSelectionMode}

    def keyPressEvent(self, event):
        if self._fireEventCallback('key_pressed', event):
            return
        code = event.key()
        if code in self._key_map:
            self._key_map[code]()
        else:
            msg = "key: {0}\nnot mapped to any function".format(code)

            log.info(msg)

    def Test(self):
        if self._inited:
            self._display.Test()

    def focusInEvent(self, event):
        if self._inited:
            self._display.Repaint()

    def focusOutEvent(self, event):
        if self._inited:
            self._display.Repaint()

    def paintEvent(self, event):
        if self._inited:
            self._display.Context.UpdateCurrentViewer()
            # important to allow overpainting of the OCC OpenGL context in Qt
            self.swapBuffers()

        if self._drawbox:
            self.makeCurrent()
            painter = QtGui.QPainter(self)
            painter.setPen(QtGui.QPen(QtGui.QColor(0, 0, 0), 1))
            rect = QtCore.QRect(*self._drawbox)
            painter.drawRect(rect)
            painter.end()
            self.doneCurrent()

    def ZoomAll(self, evt):
        self._display.FitAll()

    def wheelEvent(self, event):
        if self._fireEventCallback('mouse_scrolled', event):
            return
        if self._lock_zoom:
            return
        try:  
            delta = event.angleDelta().y()  # PyQt5
        except:  
            delta = event.delta()  # PyQt4/PySide
        zoom_factor = 1.25 if delta > 0 else 1/1.25
        display = self._display
        display.Repaint()
        display.ZoomFactor(zoom_factor)

    def dragMoveEvent(self, event):
        if self._fireEventCallback('mouse_dragged', event):
            return
        pass
    
    def _fireEventCallback(self, name, event):
        handled = False
        for cb in self._callbacks.get(name, []):
            #: Raise StopIteration to ignore the default handlers
            try:
                cb((self._display, event))
            except StopIteration:
                handled = True
            except:
                traceback.print_exc()
                #log.error(traceback.format_exc())
        return handled

    def mousePressEvent(self, event):
        self.setFocus()
        self.dragStartPos = event.pos()
        if self._fireEventCallback('mouse_pressed', event):
            return
        self._display.StartRotation(self.dragStartPos.x(),
                                    self.dragStartPos.y())

    def mouseReleaseEvent(self, event):
        if self._fireEventCallback('mouse_released', event):
            return
        #pt = event.pos()
        modifiers = event.modifiers()

        if event.button() == Qt.LeftButton:
            pt = event.pos()
            if self._select_area and self._drawbox:
                [xmin, ymin, dx, dy] = self._drawbox
                self._display.SelectArea(xmin, ymin, xmin + dx, ymin + dy)
                self._select_area = False
            else:
                # multiple select if shift is pressed
                if modifiers == Qt.ShiftModifier:
                    self._display.ShiftSelect(pt.x(), pt.y())
                else:
                    # single select otherwise
                    self._display.Select(pt.x(), pt.y())
        elif event.button() == Qt.RightButton:
            if self._zoom_area:
                [xmin, ymin, dx, dy] = self._drawbox
                self._display.ZoomArea(xmin, ymin, xmin + dx, ymin + dy)
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
        if self._fireEventCallback('mouse_moved', event):
            return
        pt = event.pos()
        buttons = int(event.buttons())
        modifiers = event.modifiers()
        # ROTATE
        if (buttons == Qt.LeftButton and
                not modifiers == Qt.ShiftModifier):
            #dx = pt.x() - self.dragStartPos.x()
            #dy = pt.y() - self.dragStartPos.y()
            if not self._lock_rotation:
                self._display.Rotation(pt.x(), pt.y())
            self._drawbox = False
        # DYNAMIC ZOOM
        elif (buttons == Qt.RightButton and
              not modifiers == Qt.ShiftModifier):
            self._display.Repaint()
            self._display.DynamicZoom(abs(self.dragStartPos.x()),
                                      abs(self.dragStartPos.y()), abs(pt.x()),
                                      abs(pt.y()))
            self.dragStartPos = pt
            self._drawbox = False
        # PAN
        elif buttons == Qt.MidButton:
            dx = pt.x() - self.dragStartPos.x()
            dy = pt.y() - self.dragStartPos.y()
            self.dragStartPos = pt
            self._display.Pan(dx, -dy)
            self._drawbox = False
        # DRAW BOX
        # ZOOM WINDOW
        elif (buttons == Qt.RightButton and
              modifiers == Qt.ShiftModifier):
            self._zoom_area = True
            self.DrawBox(event)
        # SELECT AREA
        elif (buttons == Qt.LeftButton and
              modifiers == Qt.ShiftModifier):
            self._select_area = True
            self.DrawBox(event)
        else:
            self._drawbox = False
            self._display.MoveTo(pt.x(), pt.y())


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
    
    def _get_display(self):
        return self.widget._display
    
    #: Display
    display = Property(_get_display, cached=True)
    
    def get_shapes(self):
        return [c for c in self.children()
                if not isinstance(c, QtToolkitObject)]
    
    def create_widget(self):
        self.widget = QtViewer3d(parent=self.parent_widget())

    def init_widget(self):
        super(QtOccViewer, self).init_widget()
        d = self.declaration
        widget = self.widget

        #: Create viewer
        widget._display = Display(widget.GetHandle())
        display = widget._display
        display.Create()

        # background gradient
        self.set_background_gradient(d.background_gradient)
        self.set_trihedron_mode(d.trihedron_mode)
        self.set_display_mode(d.display_mode)
        self.set_selection_mode(d.selection_mode)
        self.set_view_mode(d.view_mode)
        self.set_antialiasing(d.antialiasing)
        self.set_lock_rotation(d.lock_rotation)
        self.set_lock_zoom(d.lock_zoom)
        self._update_raytracing_mode()

        #: Setup callbacks
        display.register_select_callback(self.on_selection)

        widget._inited = True  # dict mapping keys to functions
        widget._SetupKeyMap()  #
        display.thisown = False
        self.init_signals()
        
    def init_signals(self):
        d = self.declaration
        widget = self.widget
        for name in widget._callbacks.keys():
            if hasattr(d, name):
                cb = getattr(d, name)
                widget._callbacks[name].append(cb)
        
    def init_layout(self):
        super(QtOccViewer, self).init_layout()
        for child in self.children():
            self.child_added(child)
        display = self.display
        display.OnResize()

    def child_added(self, child):
        if not isinstance(child, QtToolkitObject):
            self.get_member('shapes').reset(self)
            child.observe('shape', self.update_display)
            self.update_display()
        else:
            super(QtOccViewer, self).child_added(child)

    def child_removed(self, child):
        if not isinstance(child, QtToolkitObject):
            self.get_member('shapes').reset(self)
            child.unobserve('shape', self.update_display)
        else:
            super(QtOccViewer, self).child_removed(child)
    
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
        for shape in shapes:
            brepbndlib_Add(shape, bbox)
        return bbox.Get()
    
    def get_screen_coordinate(self, point):
        """ Convert a 3d coordinate to a 2d screen coordinate
        
        Parameters
        ----------
        (x, y, z): Tuple
            A 3d coordinate
        """
        return self.display.View.Convert(*point)
    
    def set_antialiasing(self, enabled):
        if enabled:
            self.display.EnableAntiAliasing()
        else:
            self.display.DisableAntiAliasing()
            
    def set_shadows(self, enabled):
        self._update_raytracing_mode()
        
    def set_reflections(self, enabled):
        self._update_raytracing_mode()
        
    def _update_raytracing_mode(self):
        d = self.declaration    
        display = self.display
        if not hasattr(display.View, 'SetRaytracingMode'):
            return
        if d.shadows or d.reflections:
            display.View.SetRaytracingMode()
            if d.shadows:
                display.View.EnableRaytracedShadows()
            if d.reflections:
                display.View.EnableRaytracedReflections()
            if d.antialiasing:
                display.View.EnableRaytracedAntialiasing()
        else:
            display.View.DisableRaytracingMode()
            
    def set_background_gradient(self, gradient):
        self.display.set_bg_gradient_color(*gradient)
        
    def set_trihedron_mode(self, mode):
        attr = 'Aspect_TOTP_{}'.format(mode.upper().replace("-", "_"))
        position = getattr(Aspect, attr)
        self.display.View.TriedronDisplay(
            position, Quantity_NOC_BLACK, 0.1, V3d.V3d_ZBUFFER)
        if self.widget._inited:
            self.display.Context.UpdateCurrentViewer()
        
    def set_selection_mode(self, mode):
        """ Call SetSelectionMode<mode> on the display. """
        attr = 'SetSelectionMode{}'.format(mode.title())
        handler = getattr(self.display, attr, None)
        if handler is not None:
            handler()
        
    def set_display_mode(self, mode):
        if mode == 'shaded':
            self.display.SetModeShaded()
        elif mode == 'hlr':
            self.display.SetModeHLR()
        elif mode == 'wireframe':
            self.display.SetModeWireFrame()
    
    def set_view_mode(self, mode):
        """ Call View_<mode> on the display and refit as needed. """
        attr = 'View_{}'.format(mode.title())
        handler = getattr(self.display, attr, None)
        if handler is not None:
            handler()
        self.display.FitAll()
        
    def set_lock_rotation(self, locked):
        self.widget._lock_rotation = locked
        
    def set_lock_zoom(self, locked):
        self.widget._lock_zoom = locked
        
    def zoom_factor(self, factor):
        self.display.ZoomFactor(factor)
        
    def fit_all(self):
        self.display.FitAll()
        
    def fit_selection(self):
        if not self.display.selected_shapes:
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
        return self.display.View.Dump(filename)
    
    # -------------------------------------------------------------------------
    # Display Handling
    # -------------------------------------------------------------------------
    def on_selection(self, selection, *args, **kwargs):
        d = self.declaration
        selection = []
        for shape in self.display.selected_shapes:
            if shape in self._displayed_shapes:
                selection.append(self._displayed_shapes[shape].declaration)
            else:
                log.warn("shape {} not in {}".format(shape,
                                                     self._displayed_shapes))
        #d.selection = selection
        d.selection(ViewerSelectionEvent(selection=selection,
                                         parameters=args,
                                         options=kwargs))
        
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
        display = self.display
        # Erase all just hides them
        display.Context.PurgeDisplay()
        display.Context.RemoveAll()
    
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
            display = self.display

            self.clear_display()
            displayed_shapes = {}
            ais_shapes = []
            #log.debug("_do_update {}")

            #: Expand all parts otherwise we lose the material information
            shapes = self._expand_shapes(self.shapes[:])
            
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
                material = getattr(Graphic3d, 'Graphic3d_NOM_{}'.format(
                    d.material.upper()
                )) if d.material else None

                #: If last shape
                update = shape == shapes[-1]

                ais_shapes.append(display.DisplayShape(
                    s, color=d.color, material=material,
                    transparency=d.transparency,
                    update=update, fit=not self._displayed_shapes))
                
            self._ais_shapes = ais_shapes
            self._displayed_shapes = displayed_shapes
            
            # Update bounding box
            # TODO: Is there an API for this?
            bbox = self.get_bounding_box(displayed_shapes.keys())
            self.declaration.bbox = BBox(*bbox)
        except:
            log.error("Failed to display shapes: {}".format(
                traceback.format_exc()))


class QtOccViewerClippedPlane(QtControl, ProxyOccViewerClippedPlane):

    #: Viewer widget
    graphic = Typed(Graphic3d.Graphic3d_ClipPlane)
    
    #: Updates blocked
    _updates_blocked = Bool(True)
    
    def _get_display(self):
        return self.parent().display
    
    #: Display
    display = Property(_get_display, cached=True)
    
    def create_widget(self):
        self.graphic = Graphic3d.Graphic3d_ClipPlane()
        
    def init_widget(self):
        #super(QtOccViewerClippedPlane, self).init_widget()
        d = self.declaration
        clip_plane = self.graphic
        self.set_enabled(d.enabled)
        self.set_capping(d.capping)
        self.set_capping_hatched(d.capping_hatched)
        self.set_position(d.position)
        if d.capping_color:
            self.set_capping_color(d.capping_color)
        
    def init_layout(self):
        self._updates_blocked = False
        viewer = self.parent()
        clip_plane = self.graphic.GetHandle()
        for ais_shp in viewer._ais_shapes:
            ais_shp.GetObject().AddClipPlane(clip_plane)
        self.update_viewer()
        
    def destroy(self):
        viewer = self.parent()
        self.graphic.SetOn(False)
        if viewer is not None:
            clip_plane = self.graphic.GetHandle()
            
            for ais_shp in viewer._ais_shapes:
                try:
                    ais_shp.GetObject().RemoveClipPlane(clip_plane)
                except:
                    pass
        del self.graphic
        super(QtOccViewerClippedPlane, self).destroy()
        
    # -------------------------------------------------------------------------
    # Helpers
    # -------------------------------------------------------------------------
    def update_viewer(self):
        if self._updates_blocked:
            return
        self.display.Context.UpdateCurrentViewer()
        
    # -------------------------------------------------------------------------
    # ProxyOccViewerCappedPlane API
    # -------------------------------------------------------------------------
    def set_enabled(self, enabled):
        self.graphic.SetOn(enabled)
        self.update_viewer()
        
    def set_capping(self, capping):
        self.graphic.SetCapping(capping)
        self.update_viewer()
    
    def set_capping_hatched(self, hatched):
        if hatched:
            self.graphic.SetCappingHatchOn()
        else:
            self.graphic.SetCappingHatchOff()
        self.update_viewer()
        
    def set_capping_color(self, color):
        display = self.display
        clip_plane = self.graphic
        if color:
            c = Quantity_Color(color.red/255.,
                               color.green/255.,
                               color.blue/255., Quantity_TOC_RGB)
            mat = clip_plane.CappingMaterial()
            mat.SetAmbientColor(c)
            mat.SetDiffuseColor(c)
            clip_plane.SetCappingMaterial(mat)
        
    def set_position(self, position):
        d = self.declaration
        pln = self.graphic.ToPlane()
        pln.SetPosition(gp_Ax3(gp_Pnt(*position), gp_Dir(*d.direction)))
        self.graphic.SetEquation(pln)
        self.update_viewer()
    
    def set_direction(self, direction):
        self.set_position(self.declaration.position)
