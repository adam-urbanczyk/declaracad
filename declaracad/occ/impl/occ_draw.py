"""
Copyright (c) 2016-2019, Jairus Martin.

Distributed under the terms of the GPL v3 License.

The full license is in the file LICENSE, distributed with this software.

Created on Sep 30, 2016

@author: jrm
"""
import os
from atom.api import Typed, Int, Tuple, List, set_default

from OCCT.BRep import BRep_Tool
from OCCT.BRepBuilderAPI import (
    BRepBuilderAPI_MakeEdge, BRepBuilderAPI_MakeFace,
    BRepBuilderAPI_MakePolygon, BRepBuilderAPI_Transform,
    BRepBuilderAPI_MakeVertex, BRepBuilderAPI_MakeWire
)
from OCCT.BRepLib import BRepLib
from OCCT.BRepOffsetAPI import BRepOffsetAPI_MakeOffset
from OCCT.Font import Font_BRepTextBuilder, Font_FontAspect, Font_FontMgr
from OCCT.GC import (
    GC_MakeSegment, GC_MakeArcOfCircle, GC_MakeArcOfEllipse, GC_MakeLine
)
from OCCT.gp import (
    gp_Dir, gp_Pnt, gp_Lin, gp_Pln, gp_Circ, gp_Elips, gp_Vec, gp_Trsf,
    gp_Ax3, gp_Ax2, gp
)
from OCCT.TopoDS import (
    TopoDS, TopoDS_Shape, TopoDS_Edge, TopoDS_Wire, TopoDS_Vertex
)
from OCCT.GeomAPI import GeomAPI_PointsToBSpline, GeomAPI
from OCCT.Geom import (
    Geom_BezierCurve, Geom_BSplineCurve, Geom_TrimmedCurve, Geom_Plane,
    Geom_Ellipse, Geom_Circle, Geom_Parabola, Geom_Hyperbola, Geom_Line
)
from OCCT.TColgp import TColgp_Array1OfPnt
from OCCT.TCollection import TCollection_HAsciiString
from OCCT.NCollection import NCollection_Utf16String
#from OCCT.NCollection import NCollection_UtfString

from ..shape import coerce_point, coerce_direction
from ..draw import (
    ProxyPlane, ProxyVertex, ProxyLine, ProxyCircle, ProxyEllipse,
    ProxyHyperbola, ProxyParabola, ProxyEdge, ProxyWire, ProxySegment, ProxyArc,
    ProxyPolyline, ProxyBSpline, ProxyBezier, ProxyTrimmedCurve, ProxyText,
    ProxyRectangle
)
from .occ_shape import OccShape, OccDependentShape, Topology, coerce_axis
from .occ_svg import make_ellipse



#: Track registered fonts
FONT_MANAGER = Font_FontMgr.GetInstance_()
FONT_REGISTRY = set()
FONT_ASPECTS = {
    'regular': Font_FontAspect.Font_FA_Regular,
    'bold': Font_FontAspect.Font_FA_Bold,
    'italic': Font_FontAspect.Font_FA_Italic,
    'bold-italic': Font_FontAspect.Font_FA_BoldItalic
}

ORIGIN = gp.Origin_()
DEFAULT_AXIS = gp_Ax3(gp.Origin_(), gp.DZ_())


class OccPlane(OccShape, ProxyPlane):
    #: Update the class reference
    reference = set_default('https://dev.opencascade.org/doc/refman/html/'
                            'classgp___pnt.html')

    curve = Typed(Geom_Plane)

    def create_shape(self):
        d = self.declaration
        pln = gp_Pln(d.position.proxy, d.direction.proxy)

        curve = self.curve = Geom_Plane(pln)
        if d.bounds:
            u, v = d.bounds
            face = BRepBuilderAPI_MakeFace(pln, u.x, v.x, u.y, v.y)
        else:
            face = BRepBuilderAPI_MakeFace(pln)

        self.shape = face.Face()

    def set_bounds(self, bounds):
        self.create_shape()


class OccVertex(OccShape, ProxyVertex):
    #: Update the class reference
    reference = set_default('https://dev.opencascade.org/doc/refman/html/'
                            'class_b_rep_builder_a_p_i___make_vertex.html')

    def set_x(self, x):
        self.create_shape()

    def set_y(self, y):
        self.create_shape()

    def set_z(self, z):
        self.create_shape()


class OccEdge(OccShape, ProxyEdge):
    #: Update the class reference
    reference = set_default('https://dev.opencascade.org/doc/refman/html/'
                            'class_b_rep_builder_a_p_i___make_edge.html')

    curve = Typed(Geom_TrimmedCurve)

    def get_transform(self):
        d = self.declaration
        t = gp_Trsf()
        axis = gp_Ax3()
        axis.SetDirection(d.direction.proxy)
        t.SetTransformation(axis)
        t.SetTranslationPart(gp_Vec(*d.position))
        return t

    def make_edge(self, *args):
        d = self.declaration
        if d.surface:
            # Convert the curve to 2d
            args = list(args)
            pln = gp_Pln(d.position.proxy, d.direction.proxy)
            args[0] = GeomAPI.To2d_(args[0], pln)
            args.insert(1,  BRep_Tool.Surface_(d.surface))
        return BRepBuilderAPI_MakeEdge(*args).Edge()

    def get_value_at(self, t, derivative=0):
        if self.curve is not None:
            return Topology.get_value_at(self.curve, t, derivative)
        raise NotImplementedError(
                "Cannot get value for %s" % self.declaration)

    def set_surface(self, surface):
        self.create_shape()


class OccLine(OccEdge, ProxyLine):
    #: Update the class reference
    reference = set_default('https://dev.opencascade.org/doc/refman/html/'
                            'classgp___lin.html')

    curve = Typed(Geom_Line)

    def get_transformed_points(self, points=None):
        d = self.declaration
        t = self.get_transform()
        return [p.proxy.Transformed(t) for p in points or d.points]

    def create_shape(self):
        d = self.declaration
        if len(d.points) == 2:
            curve = GC_MakeLine(*self.get_transformed_points()).Value()
        else:
            curve = GC_MakeLine(d.position.proxy, d.direction.proxy).Value()
        self.curve = curve
        self.shape = self.make_edge(curve)

    def set_points(self, points):
        self.create_shape()


class OccSegment(OccLine, ProxySegment):
    #: Update the class reference
    reference = set_default('https://dev.opencascade.org/doc/refman/html/'
                            'class_g_c___make_segment.html')

    def create_shape(self):
        d = self.declaration
        points = self.get_transformed_points()
        if len(points) < 2:
            raise ValueError("A segment requires at least two points")
        shape = BRepBuilderAPI_MakeWire()
        if d.surface:
            pln = gp_Pln(d.position.proxy, d.direction.proxy)
            surface = BRep_Tool.Surface_(d.surface)
        else:
            surface = None
        for i in range(1, len(points)):
            segment = GC_MakeSegment(points[i-1], points[i]).Value()
            if surface:
                segment = GeomAPI.To2d_(segment, pln)
                edge = BRepBuilderAPI_MakeEdge(segment, surface).Edge()
                BRepLib.BuildCurves3d_(edge)
            else:
                edge = BRepBuilderAPI_MakeEdge(segment).Edge()
            shape.Add(edge)
        self.shape = shape.Shape()


class OccArc(OccLine, ProxyArc):
    #: Update the class reference
    reference = set_default('https://dev.opencascade.org/doc/refman/html/'
                            'class_g_c___make_arc_of_circle.html')

    curve = Typed(Geom_TrimmedCurve)

    def create_shape(self):
        d = self.declaration
        n = len(d.points)
        if d.radius:
            sense = True
            points = [p.proxy for p in d.points] # Do not trasnform these
            #if d.radius2:
            #    g = gp_Elips(coerce_axis(d.axis), d.radius, d.radius2)
            #    factory = GC_MakeArcOfEllipse
            #else:
            g = gp_Circ(coerce_axis(d.axis), d.radius)
            factory = GC_MakeArcOfCircle

            if n == 2:
                arc = factory(g, points[0], points[1], sense).Value()
            elif n == 1:
                arc = factory(g, d.alpha1, points[0], sense).Value()
            else:
                arc = factory(g, d.alpha1, d.alpha2, sense).Value()
            self.curve = arc
            self.shape = self.make_edge(arc)
        elif n == 2:
            points = self.get_transformed_points()
            arc = GC_MakeArcOfEllipse(points[0], points[1]).Value()
            self.curve = arc
            self.shape = self.make_edge(arc)
        elif n == 3:
            points = self.get_transformed_points()
            arc = GC_MakeArcOfCircle(points[0], points[1], points[2]).Value()
            self.curve = arc
            self.shape = self.make_edge(arc)
        else:
            raise ValueError("Could not create an Arc with the given children "
                             "and parameters. Must be given one of:\n\t"
                             "- two or three points\n\t"
                             "- radius and 2 points\n\t"
                             "- radius, alpha1 and one point\n\t"
                             "- radius, alpha1 and alpha2")

    def set_radius(self, r):
        self.create_shape()

    def set_radius2(self, r):
        self.create_shape()

    def set_alpha1(self, a):
        self.create_shape()

    def set_alpha2(self, a):
        self.create_shape()


class OccCircle(OccEdge, ProxyCircle):
    #: Update the class reference
    reference = set_default('https://dev.opencascade.org/doc/refman/html/'
                            'classgp___circ.html')

    curve = Typed(Geom_Circle)

    def create_shape(self):
        d = self.declaration
        curve = self.curve = Geom_Circle(coerce_axis(d.axis), d.radius)
        self.shape = self.make_edge(curve)

    def set_radius(self, r):
        self.create_shape()


class OccEllipse(OccEdge, ProxyEllipse):
    #: Update the class reference
    reference = set_default('https://dev.opencascade.org/doc/refman/html/'
                            'classgp___elips.html')

    curve = Typed(Geom_Ellipse)

    def create_shape(self):
        d = self.declaration
        major = max(d.major_radius, d.minor_radius)
        minor = min(d.major_radius, d.minor_radius)
        curve = self.curve = Geom_Ellipse(coerce_axis(d.axis), major, minor)
        self.shape = self.make_edge(curve)

    def set_major_radius(self, r):
        self.create_shape()

    def set_minor_radius(self, r):
        self.create_shape()


class OccHyperbola(OccEdge, ProxyHyperbola):
    #: Update the class reference
    reference = set_default('https://dev.opencascade.org/doc/refman/html/'
                            'classgp___hypr.html')

    curve = Typed(Geom_Hyperbola)

    def create_shape(self):
        d = self.declaration
        major = max(d.major_radius, d.minor_radius)
        minor = min(d.major_radius, d.minor_radius)
        curve = self.curve = Geom_Hyperbola(coerce_axis(d.axis), major, minor)
        self.shape = self.make_edge(curve)

    def set_major_radius(self, r):
        self.create_shape()

    def set_minor_radius(self, r):
        self.create_shape()


class OccParabola(OccEdge, ProxyParabola):
    #: Update the class reference
    reference = set_default('https://dev.opencascade.org/doc/refman/html/'
                            'classgp___parab.html')

    curve = Typed(Geom_Parabola)

    def create_shape(self):
        d = self.declaration
        curve = self.curve = Geom_Parabola(coerce_axis(d.axis), d.focal_length)
        self.shape = self.make_edge(curve)

    def set_focal_length(self, l):
        self.create_shape()


class OccPolyline(OccLine, ProxyPolyline):
    #: Update the class reference
    reference = set_default('https://dev.opencascade.org/doc/refman/html/'
                            'class_b_rep_builder_a_p_i___make_polygon.html')

    def create_shape(self):
        d = self.declaration
        points = self.get_transformed_points()
        shape = BRepBuilderAPI_MakePolygon()
        for p in points:
            shape.Add(p)
        if d.closed:
            shape.Close()
        self.shape = shape.Wire()

    def set_closed(self, closed):
        self.create_shape()


class OccBSpline(OccLine, ProxyBSpline):
    #: Update the class reference
    reference = set_default('https://dev.opencascade.org/doc/refman/html/'
                            'class_geom___b_spline_curve.html')

    curve = Typed(Geom_BSplineCurve)

    def create_shape(self):
        d = self.declaration
        if not d.points:
            raise ValueError("Must have at least two points")
        # Poles and weights
        points = self.get_transformed_points()
        pts = TColgp_Array1OfPnt(1, len(points))
        set_value = pts.SetValue

        # TODO: Support weights
        for i, p in enumerate(points):
            set_value(i+1, p)
        curve = self.curve = GeomAPI_PointsToBSpline(pts).Curve()
        self.shape = self.make_edge(curve)


class OccBezier(OccLine, ProxyBezier):
    #: Update the class reference
    reference = set_default('https://dev.opencascade.org/doc/refman/html/'
                            'class_geom___bezier_curve.html')

    curve = Typed(Geom_BezierCurve)

    def create_shape(self):
        d = self.declaration
        n = len(d.points)
        if n < 2:
            raise ValueError("A bezier must have at least 2 points!")

        points = self.get_transformed_points()
        pts = TColgp_Array1OfPnt(1, n)
        set_value = pts.SetValue

        # TODO: Support weights
        for i, p in enumerate(points):
            set_value(i+1, p)

        curve = self.curve = Geom_BezierCurve(pts)
        self.shape = self.make_edge(curve)


class OccText(OccShape, ProxyText):
    #: Update the class reference
    reference = set_default('https://dev.opencascade.org/doc/refman/html/'
                            'class_topo_d_s___shape.html')

    builder = Typed(Font_BRepTextBuilder, ())

    # font = Typed(Font_SystemFont)

    def create_shape(self):
        """ Create the shape by loading it from the given path. """
        d = self.declaration
        font_family = d.font
        if font_family and os.path.exists(font_family) \
                and font_family not in FONT_REGISTRY:
            FONT_MANAGER.RegisterFont(font_family, True)
            FONT_REGISTRY.add(font_family)

        font_style = FONT_ASPECTS.get(d.style)
        font_name = TCollection_HAsciiString(font_family)
        font = FONT_MANAGER.FindFont(font_name, font_style, int(d.size))
        text = NCollection_Utf16String(d.text.encode('utf-16'))
        self.shape = self.builder.Perform(font, text)

    def set_text(self, text):
        self.create_shape()

    def set_font(self, font):
        self.create_shape()

    def set_size(self, size):
        self.create_shape()

    def set_style(self, style):
        self.create_shape()

    def set_composite(self, composite):
        self.create_shape()


class OccTrimmedCurve(OccEdge, ProxyTrimmedCurve):
    #: Update the class reference
    reference = set_default('https://dev.opencascade.org/doc/refman/html/'
                            'class_geom___trimmed_curve.html')

    curve = Typed(Geom_TrimmedCurve)

    def create_shape(self):
        pass

    def init_layout(self):
        self.update_shape()
        for child in self.children():
            child.observe('shape', self.update_shape)

    def update_shape(self, change=None):
        d = self.declaration
        child = self.get_first_child()
        if hasattr(child, 'curve'):
            curve = child.curve
        else:
            curve = BRep_Tool.Curve_(child.shape, 0, 1)[0]
        trimmed_curve = self.curve = Geom_TrimmedCurve(curve, d.u, d.v)
        self.shape = self.make_edge(trimmed_curve)

    def set_u(self, u):
        self.update_shape()

    def set_v(self, v):
        self.update_shape()


class OccRectangle(OccEdge, ProxyRectangle):
    def create_shape(self):
        d = self.declaration
        t = self.get_transform()
        w, h = d.width, d.height
        if d.rx or d.ry:
            rx, ry = d.rx, d.ry
            if not ry:
                ry = rx
            elif not rx:
                rx = ry

            # Clamp to the valid range
            rx = min(w/2, rx)
            ry = min(h/2, ry)

            # Bottom
            p1 = gp_Pnt(0+rx, 0, 0)
            p2 = gp_Pnt(0+w-rx, 0, 0)

            # Right
            p3 = gp_Pnt(w, ry, 0)
            p4 = gp_Pnt(w, h-ry, 0)

            # Top
            p5 = gp_Pnt(w-rx, h, 0)
            p6 = gp_Pnt(rx, h, 0)

            # Left
            p7 = gp_Pnt(0, h-ry, 0)
            p8 = gp_Pnt(0, ry, 0)
            shape = BRepBuilderAPI_MakeWire()

            e = d.tolerance

            # Bottom
            if not p1.IsEqual(p2, e):
                shape.Add(BRepBuilderAPI_MakeEdge(p1, p2).Edge())

            # Arc bottom right
            c = make_ellipse((w-rx, ry, 0), rx, ry)
            shape.Add(BRepBuilderAPI_MakeEdge(
                GC_MakeArcOfEllipse(c, p2, p3, False).Value()).Edge())

            # Right
            if not p3.IsEqual(p4, e):
                shape.Add(BRepBuilderAPI_MakeEdge(p3, p4).Edge())

            # Arc top right
            c.SetLocation(gp_Pnt(w-rx, h-ry, 0))
            shape.Add(BRepBuilderAPI_MakeEdge(
                GC_MakeArcOfEllipse(c, p4, p5, False).Value()).Edge())

            # Top
            if not p5.IsEqual(p6, e):
                shape.Add(BRepBuilderAPI_MakeEdge(p5, p6).Edge())

            # Arc top left
            c.SetLocation(gp_Pnt(rx, h-ry, 0))
            shape.Add(BRepBuilderAPI_MakeEdge(
                GC_MakeArcOfEllipse(c, p6, p7, False).Value()).Edge())

            # Left
            if not p7.IsEqual(p8, e):
                shape.Add(BRepBuilderAPI_MakeEdge(p7, p8).Edge())

            # Arc bottom left
            c.SetLocation(gp_Pnt(rx, ry, 0))
            shape.Add(BRepBuilderAPI_MakeEdge(
                GC_MakeArcOfEllipse(c, p8, p1, False).Value()).Edge())

            shape = shape.Wire()
            shape.Closed(True)
        else:
            shape = BRepBuilderAPI_MakePolygon(
                gp_Pnt(0, 0, 0), gp_Pnt(w, 0, 0),
                gp_Pnt(w, h, 0), gp_Pnt(0, h, 0), True).Wire()
        rect = BRepBuilderAPI_Transform(shape, t, False).Shape()
        self.shape = TopoDS.Wire_(rect)


class OccWire(OccDependentShape, ProxyWire):
    #: Update the class reference
    reference = set_default('https://dev.opencascade.org/doc/refman/html/'
                            'class_b_rep_builder_a_p_i___make_wire.html')

    def create_shape(self):
        pass

    def shape_to_wire(self, shape):
        if isinstance(shape, (TopoDS_Edge, TopoDS_Wire)):
            return shape
        return TopoDS.Wire_(shape)

    def update_shape(self, change=None):
        d = self.declaration
        shape = BRepBuilderAPI_MakeWire()
        convert = self.shape_to_wire
        for c in self.children():
            if c.shape is None:
                raise ValueError("Cannot build wire from empty shape: %s" % c)
            if isinstance(c.shape, (list, tuple)):
                #: Assume it's a list of drawn objects...
                for item in c.shape:
                    if item is not None:
                        shape.Add(convert(item))
            else:
                wire = convert(c.shape)
                if getattr(c.declaration, 'surface', None):
                    BRepLib.BuildCurves3d_(wire)
                shape.Add(wire)

        assert shape.IsDone(), 'Edges must be connected %s' % d
        self.shape = shape.Wire()

    def child_added(self, child):
        super(OccWire, self).child_added(child)
        child.observe('shape', self.update_shape)

    def child_removed(self, child):
        super(OccEdge, self).child_removed(child)
        child.unobserve('shape', self.update_shape)
