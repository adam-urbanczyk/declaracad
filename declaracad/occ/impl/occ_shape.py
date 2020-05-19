"""
Copyright (c) 2016-2018, Jairus Martin.

Distributed under the terms of the GPL v3 License.

The full license is in the file LICENSE, distributed with this software.

Created on Sep 30, 2016

@author: jrm
"""
import os
from math import pi
from atom.api import (
    Atom, Bool, Instance, List, Typed, Str, Property, observe, set_default
)

from OCCT import GeomAbs
from OCCT.AIS import AIS_Shape
from OCCT.Bnd import Bnd_Box
from OCCT.BRep import BRep_Builder, BRep_Tool
from OCCT.BRepAdaptor import (
    BRepAdaptor_Curve, BRepAdaptor_CompCurve, BRepAdaptor_Surface
)
from OCCT.BRepBndLib import BRepBndLib
from OCCT.BRepBuilderAPI import (
    BRepBuilderAPI_MakeShape, BRepBuilderAPI_MakeFace,
    BRepBuilderAPI_Transform, BRepBuilderAPI_MakeWire
)
from OCCT.BRepPrimAPI import (
    BRepPrimAPI_MakeBox, BRepPrimAPI_MakeCone,
    BRepPrimAPI_MakeCylinder, BRepPrimAPI_MakeHalfSpace, BRepPrimAPI_MakePrism,
    BRepPrimAPI_MakeSphere, BRepPrimAPI_MakeWedge, BRepPrimAPI_MakeTorus,
    BRepPrimAPI_MakeRevol,
)
from OCCT.BRepTools import BRepTools, BRepTools_WireExplorer
from OCCT.Geom import (
    Geom_Ellipse, Geom_Circle, Geom_Parabola, Geom_Hyperbola, Geom_Line
)
from OCCT.GeomAbs import (
    GeomAbs_Line, GeomAbs_Circle, GeomAbs_Ellipse, GeomAbs_Hyperbola,
    GeomAbs_Parabola, GeomAbs_BezierCurve, GeomAbs_BSplineCurve,
    GeomAbs_OffsetCurve, GeomAbs_OtherCurve,
)

from OCCT.gp import (
    gp, gp_Pnt, gp_Dir, gp_Vec, gp_Ax1, gp_Ax2, gp_Ax3, gp_Trsf, gp_Pln
)

from OCCT.TopAbs import (
    TopAbs_VERTEX, TopAbs_EDGE, TopAbs_FACE, TopAbs_WIRE,
    TopAbs_SHELL, TopAbs_SOLID, TopAbs_COMPOUND,
    TopAbs_COMPSOLID
)
from OCCT.TopExp import TopExp, TopExp_Explorer
from OCCT.TopoDS import (
    TopoDS, TopoDS_Wire, TopoDS_Vertex, TopoDS_Edge,
    TopoDS_Face, TopoDS_Shell, TopoDS_Solid,
    TopoDS_Compound, TopoDS_CompSolid, TopoDS_Shape
)
from OCCT.TopTools import (
    TopTools_ListOfShape,
    TopTools_ListIteratorOfListOfShape,
    TopTools_IndexedDataMapOfShapeListOfShape
)

from OCCT.IGESControl import IGESControl_Reader
from OCCT.IFSelect import IFSelect_RetDone, IFSelect_ItemsByEntity
from OCCT.STEPControl import STEPControl_Reader
from OCCT.RWStl import RWStl

from ..shape import (
    ProxyShape, ProxyFace, ProxyBox, ProxyCone, ProxyCylinder,
    ProxyHalfSpace, ProxyPrism, ProxySphere, ProxyWedge,
    ProxyTorus, ProxyRevol, ProxyRawShape, ProxyLoadShape, BBox, Shape,
    coerce_point, coerce_direction
)

from declaracad.core.utils import log


DX = gp_Dir(1, 0, 0)
DXN = gp_Dir(-1, 0, 0)
DY = gp_Dir(0, 1, 0)
DYN = gp_Dir(0, -1, 0)
DZ = gp_Dir(0, 0, 1)
DZN = gp_Dir(0, 0, -1)
AX = gp_Ax1()
AX.SetDirection(gp.DX_())
AY = gp_Ax1()
AY.SetDirection(gp.DY_())
AZ = gp_Ax1()
AZ.SetDirection(gp.DZ_())


def coerce_axis(value):
    pos, dir, rotation = value
    axis = gp_Ax2(pos.proxy, dir.proxy)
    axis.Rotate(axis.Axis(), rotation)
    return axis


def coerce_shape(shape):
    """ Coerce a declaration into a TopoDS_Shape

    """
    if isinstance(shape, Shape):
        return shape.proxy.shape
    return shape


class WireExplorer(Atom):
    """ Wire traversal ported from the pythonocc examples by @jf--

    """
    wire = Instance(TopoDS_Wire)
    wire_explorer = Typed(BRepTools_WireExplorer)

    def _loop_topo(self, edges=True):
        wexp = self.wire_explorer = BRepTools_WireExplorer(self.wire)

        items = set()  # list that stores hashes to avoid redundancy
        occ_seq = TopTools_ListOfShape()

        get_current = wexp.Current if edges else wexp.CurrentVertext

        while wexp.More():
            current_item = get_current()
            if current_item not in items:
                items.add(current_item)
                occ_seq.Append(current_item)
            wexp.Next()

        # Convert occ_seq to python list
        seq = []
        topology_type = TopoDS.Edge_ if edges else TopoDS.Vertex_
        occ_iterator = TopTools_ListIteratorOfListOfShape(occ_seq)
        while occ_iterator.More():
            topo_to_add = topology_type(occ_iterator.Value())
            seq.append(topo_to_add)
            occ_iterator.Next()
        return seq

    def ordered_edges(self):
        return self._loop_topo(edges=True)

    def ordered_vertices(self):
        return self._loop_topo(edges=False)


class Topology(Atom):
    """ Topology traversal ported from the pythonocc examples by @jf--

    Implements topology traversal from any TopoDS_Shape this class lets you
    find how various topological entities are connected from one to another
    find the faces connected to an edge, find the vertices this edge is
    made from, get all faces connected to a vertex, and find out how many
    topological elements are connected from a source


    Note
    ----
    when traversing TopoDS_Wire entities, its advised to use the
    specialized ``WireExplorer`` class, which will return the vertices /
    edges in the expected order

    """

    #: Maps topology types and functions that can create this topology
    topo_factory = {
        TopAbs_VERTEX: TopoDS.Vertex_,
        TopAbs_EDGE: TopoDS.Edge_,
        TopAbs_FACE: TopoDS.Face_,
        TopAbs_WIRE: TopoDS.Wire_,
        TopAbs_SHELL: TopoDS.Shell_,
        TopAbs_SOLID: TopoDS.Solid_,
        TopAbs_COMPOUND: TopoDS.Compound_,
        TopAbs_COMPSOLID: TopoDS.CompSolid_
    }

    topo_types = {
        TopAbs_VERTEX: TopoDS_Vertex,
        TopAbs_EDGE: TopoDS_Edge,
        TopAbs_FACE: TopoDS_Face,
        TopAbs_WIRE: TopoDS_Wire,
        TopAbs_SHELL: TopoDS_Shell,
        TopAbs_SOLID: TopoDS_Solid,
        TopAbs_COMPOUND: TopoDS_Compound,
        TopAbs_COMPSOLID: TopoDS_CompSolid
    }

    curve_factory = {
        GeomAbs_Line: lambda c: Geom_Line(c.Line()),
        GeomAbs_Circle: lambda c: Geom_Circle(c.Circle()),
        GeomAbs_Ellipse: lambda c: Geom_Ellipse(c.Ellipse()),
        GeomAbs_Hyperbola: lambda c: Geom_Hyperbola(c.Hyperbola()),
        GeomAbs_Parabola: lambda c: Geom_Parabola(c.Parabola()),
        GeomAbs_BezierCurve: BRepAdaptor_Curve.Bezier,
        GeomAbs_BSplineCurve: BRepAdaptor_Curve.BSpline,
        GeomAbs_OffsetCurve: BRepAdaptor_Curve.OffsetCurve,
        GeomAbs_OtherCurve: BRepAdaptor_CompCurve,
    }

    #: The shape which topology will be traversed
    shape = Instance(TopoDS_Shape)

    #: Filter out TopoDS_* entities of similar TShape but different orientation
    #: for instance, a cube has 24 edges, 4 edges for each of 6 faces
    #: that results in 48 vertices, while there are only 8 vertices that have
    #: a unique geometric coordinate
    #: in certain cases ( computing a graph from the topology ) its preferable
    #: to return topological entities that share similar geometry, though
    #: differ in orientation by setting the ``ignore_orientation`` variable
    #: to True, in case of a cube, just 12 edges and only 8 vertices will be
    #: returned
    #: for further reference see TopoDS_Shape IsEqual / IsSame methods
    ignore_orientation = Bool()

    def _loop_topo(self, topology_type, topological_entity=None,
                   topology_type_to_avoid=None):
        """ this could be a faces generator for a python TopoShape class
        that way you can just do:
        for face in srf.faces:
            processFace(face)
        """
        allowed_types = self.topo_types.keys()
        if topology_type not in allowed_types:
            raise TypeError('%s not one of %s' % (
                topology_type, allowed_types))

        shape = self.shape
        if shape is None:
            return []

        topo_exp = TopExp_Explorer()
        # use self.myShape if nothing is specified
        if topological_entity is None and topology_type_to_avoid is None:
            topo_exp.Init(shape, topology_type)
        elif topological_entity is None and topology_type_to_avoid is not None:
            topo_exp.Init(shape, topology_type, topology_type_to_avoid)
        elif topology_type_to_avoid is None:
            topo_exp.Init(topological_entity, topology_type)
        elif topology_type_to_avoid:
            topo_exp.Init(
                topological_entity, topology_type, topology_type_to_avoid)

        items = set()  # list that stores hashes to avoid redundancy
        occ_seq = TopTools_ListOfShape()
        while topo_exp.More():
            current_item = topo_exp.Current()
            if current_item not in items:
                items.add(current_item)
                occ_seq.Append(current_item)
            topo_exp.Next()

        # Convert occ_seq to python list
        seq = []
        factory = self.topo_factory[topology_type]
        occ_iterator = TopTools_ListIteratorOfListOfShape(occ_seq)
        while occ_iterator.More():
            topo_to_add = factory(occ_iterator.Value())
            seq.append(topo_to_add)
            occ_iterator.Next()

        if not self.ignore_orientation:
            return seq

        # else filter out those entities that share the same TShape
        # but do *not* share the same orientation
        filter_orientation_seq = []
        for i in seq:
            present = False
            for j in filter_orientation_seq:
                if i.IsSame(j):
                    present = True
                    break
            if present is False:
                filter_orientation_seq.append(i)
        return filter_orientation_seq


    # -------------------------------------------------------------------------
    # Shape Topology
    # -------------------------------------------------------------------------
    faces = Property(lambda self: self._loop_topo(TopAbs_FACE),
                     cached=True)

    def _number_of_topo(self, iterable):
        n = 0
        for i in iterable:
            n += 1
        return n

    def number_of_faces(self):
        return self._number_of_topo(self.faces)

    vertices = Property(lambda self: self._loop_topo(TopAbs_VERTEX),
                        cached=True)

    #: Get a list of points from verticies
    points = Property(lambda self: [coerce_point(v) for v in self.vertices],
                        cached=True)

    def number_of_vertices(self):
        return self._number_of_topo(self.vertices)

    edges = Property(lambda self: self._loop_topo(TopAbs_EDGE),
                     cached=True)

    def number_of_edges(self):
        return self._number_of_topo(self.edges)

    wires = Property(lambda self: self._loop_topo(TopAbs_WIRE),
                     cached=True)

    def number_of_wires(self):
        return self._number_of_topo(self.wires)

    shells = Property(lambda self: self._loop_topo(TopAbs_SHELL),
                     cached=True)

    def number_of_shells(self):
        return self._number_of_topo(self.shells)

    solids = Property(lambda self: self._loop_topo(TopAbs_SOLID),
                      cached=True)

    def number_of_solids(self):
        return self._number_of_topo(self.solids)

    def comp_solids(self):
        """ loops over all compound solids """
        return self._loop_topo(TopAbs_COMPSOLID)

    def number_of_comp_solids(self):
        return self._number_of_topo(self.comp_solids())

    compounds = Property(lambda self: self._loop_topo(TopAbs_COMPOUND),
                         cached=True)

    def number_of_compounds(self):
        return self._number_of_topo(self.compounds)

    def ordered_vertices_from_wire(self, wire):
        """ Get verticies from a wire.

        Parameters
        ----------
        wire: TopoDS_Wire
        """
        return WireExplorer(wire).ordered_vertices()

    def number_of_ordered_vertices_from_wire(self, wire):
        return self._number_of_topo(self.ordered_vertices_from_wire(wire))

    def ordered_edges_from_wire(self, wire):
        """ Get edges from a wire.

        Parameters
        ----------
        wire: TopoDS_Wire
        """
        return WireExplorer(wire).ordered_edges()

    def number_of_ordered_edges_from_wire(self, wire):
        return self._number_of_topo(self.ordered_edges_from_wire(wire))

    def _map_shapes_and_ancestors(self, topo_type_a, topo_type_b, topological_entity):
        '''
        using the same method
        @param topoTypeA:
        @param topoTypeB:
        @param topological_entity:
        '''
        topo_set = set()
        _map = TopTools_IndexedDataMapOfShapeListOfShape()
        TopExp.MapShapesAndAncestors_(
            self.shape, topo_type_a, topo_type_b, map)
        results = _map.FindFromKey(topological_entity)
        if results.IsEmpty():
            yield None

        topology_iterator = TopTools_ListIteratorOfListOfShape(results)
        factory = self.topo_factory[topo_type_b]
        while topology_iterator.More():

            topo_entity = factory(topology_iterator.Value())

            # return the entity if not in set
            # to assure we're not returning entities several times
            if not topo_entity in topo_set:
                if self.ignore_orientation:
                    unique = True
                    for i in topo_set:
                        if i.IsSame(topo_entity):
                            unique = False
                            break
                    if unique:
                        yield topo_entity
                else:
                    yield topo_entity

            topo_set.add(topo_entity)
            topology_iterator.Next()

    def _number_shapes_ancestors(self, topo_type_a, topo_type_b,
                                 topological_entity):
        """ Get the number of shape ancestors If you want to know how many
        edges a faces has:
        _number_shapes_ancestors(self, TopAbs_EDGE, TopAbs_FACE, edg)
        will return the number of edges a faces has
        @param topo_type_a:
        @param topo_type_b:
        @param topological_entity:
        """
        topo_set = set()
        _map = TopTools_IndexedDataMapOfShapeListOfShape()
        TopExp.MapShapesAndAncestors_(
            self.shape, topo_type_a, topo_type_b, _map)
        results = _map.FindFromKey(topological_entity)
        if results.IsEmpty():
            return None
        topology_iterator = TopTools_ListIteratorOfListOfShape(results)
        while topology_iterator.More():
            topo_set.add(topology_iterator.Value())
            topology_iterator.Next()
        return len(topo_set)

    # ======================================================================
    # EDGE <-> FACE
    # ======================================================================
    def faces_from_edge(self, edge):
        """

        :param edge:
        :return:
        """
        return self._map_shapes_and_ancestors(TopAbs_EDGE, TopAbs_FACE, edge)

    def number_of_faces_from_edge(self, edge):
        """

        :param edge:
        :return:
        """
        return self._number_shapes_ancestors(TopAbs_EDGE, TopAbs_FACE, edge)

    def edges_from_face(self, face):
        """

        :param face:
        :return:
        """
        return self._loop_topo(TopAbs_EDGE, face)

    def number_of_edges_from_face(self, face):
        return len(self._loop_topo(TopAbs_EDGE, face))

    # ======================================================================
    # VERTEX <-> EDGE
    # ======================================================================
    def vertices_from_edge(self, edg):
        return self._loop_topo(TopAbs_VERTEX, edg)

    def number_of_vertices_from_edge(self, edg):
        return len(self._loop_topo(TopAbs_VERTEX, edg))

    def edges_from_vertex(self, vertex):
        return self._map_shapes_and_ancestors(TopAbs_VERTEX, TopAbs_EDGE, vertex)

    def number_of_edges_from_vertex(self, vertex):
        return self._number_shapes_ancestors(TopAbs_VERTEX, TopAbs_EDGE, vertex)

    # ======================================================================
    # WIRE <-> EDGE
    # ======================================================================
    def edges_from_wire(self, wire):
        return self._loop_topo(TopAbs_EDGE, wire)

    def number_of_edges_from_wire(self, wire):
        return len(self._loop_topo(TopAbs_EDGE, wire))

    def wires_from_edge(self, edg):
        return self._map_shapes_and_ancestors(TopAbs_EDGE, TopAbs_WIRE, edg)

    def wires_from_vertex(self, edg):
        return self._map_shapes_and_ancestors(TopAbs_VERTEX, TopAbs_WIRE, edg)

    def number_of_wires_from_edge(self, edg):
        return self._number_shapes_ancestors(TopAbs_EDGE, TopAbs_WIRE, edg)

    # ======================================================================
    # WIRE <-> FACE
    # ======================================================================
    def wires_from_face(self, face):
        return self._loop_topo(TopAbs_WIRE, face)

    def number_of_wires_from_face(self, face):
        return len(self._loop_topo(TopAbs_WIRE, face))

    def faces_from_wire(self, wire):
        return self._map_shapes_and_ancestors(TopAbs_WIRE, TopAbs_FACE, wire)

    def number_of_faces_from_wires(self, wire):
        return self._number_shapes_ancestors(TopAbs_WIRE, TopAbs_FACE, wire)

    # ======================================================================
    # VERTEX <-> FACE
    # ======================================================================
    def faces_from_vertex(self, vertex):
        return self._map_shapes_and_ancestors(TopAbs_VERTEX, TopAbs_FACE, vertex)

    def number_of_faces_from_vertex(self, vertex):
        return self._number_shapes_ancestors(TopAbs_VERTEX, TopAbs_FACE, vertex)

    def vertices_from_face(self, face):
        return self._loop_topo(TopAbs_VERTEX, face)

    def number_of_vertices_from_face(self, face):
        return len(self._loop_topo(TopAbs_VERTEX, face))

    # ======================================================================
    # FACE <-> SOLID
    # ======================================================================
    def solids_from_face(self, face):
        return self._map_shapes_and_ancestors(TopAbs_FACE, TopAbs_SOLID, face)

    def number_of_solids_from_face(self, face):
        return self._number_shapes_ancestors(TopAbs_FACE, TopAbs_SOLID, face)

    def faces_from_solids(self, solid):
        return self._loop_topo(TopAbs_FACE, solid)

    def number_of_faces_from_solids(self, solid):
        return len(self._loop_topo(TopAbs_FACE, solid))


    # -------------------------------------------------------------------------
    # Surface Types
    # -------------------------------------------------------------------------
    def extract_surfaces(self, surface_type):
        """ Returns a list of dicts containing the face and surface

        """
        surfaces = []
        attr = str(surface_type).split("_")[-1]
        for f in self.faces:
            surface = self.cast_surface(f, surface_type)
            if surface is not None:
                surfaces.append({
                    'face': f, 'surface': getattr(surface, attr)()})
        return surfaces

    plane_surfaces = Property(
        lambda self: self.extract_surfaces(GeomAbs.GeomAbs_Plane), cached=True)

    cone_surfaces = Property(
        lambda self: self.extract_surfaces(GeomAbs.GeomAbs_Cone), cached=True)

    sphere_surfaces = Property(
        lambda self: self.extract_surfaces(GeomAbs.GeomAbs_Sphere), cached=True)

    torus_surfaces = Property(
        lambda self: self.extract_surfaces(GeomAbs.GeomAbs_Torus), cached=True)

    cone_surfaces = Property(
        lambda self: self.extract_surfaces(GeomAbs.GeomAbs_Cone), cached=True)

    cylinder_surfaces = Property(
        lambda self: self.extract_surfaces(GeomAbs.GeomAbs_Cylinder), cached=True)

    bezier_surfaces = Property(
        lambda self: self.extract_surfaces(GeomAbs.GeomAbs_BezierSurface), cached=True)

    bspline_surfaces = Property(
        lambda self: self.extract_surfaces(GeomAbs.GeomAbs_BplineSurface), cached=True)

    offset_surfaces = Property(
        lambda self: self.extract_surfaces(GeomAbs.GeomAbs_OffsetSurface), cached=True)

    # -------------------------------------------------------------------------
    # Curve Types
    # -------------------------------------------------------------------------
    def extract_curves(self, curve_type):
        """ Returns a list of tuples containing the edge and curve

        """
        curves = []
        for e in self.edges:
            curve = self.cast_curve(e, curve_type)
            if curve is not None:
                curves.append({'edge': e, 'curve': curve})
        return curves

    line_curves = List()

    def _default_line_curves(self):
        return self.extract_curves(GeomAbs_Line)

    circle_curves = List()

    def _default_circle_curves(self):
        return self.extract_curves(GeomAbs_Circle)

    ellipse_curves = List()

    def _default_ellipse_curves(self):
        return self.extract_curves(GeomAbs_Ellipse)

    hyperbola_curves = List()

    def _default_hyperbola_curves(self):
        return self.extract_curves(GeomAbs_Hyperbola)

    parabola_cuves = List()

    def _default_parabola_cuves(self):
        return self.extract_curves(GeomAbs_Parabola)

    bezier_curves = List()

    def _default_bezier_curves(self):
        return self.extract_curves(GeomAbs_BezierCurve)

    bspline_curves = List()

    def _default_bspline_curves(self):
        return self.extract_curves(GeomAbs_BSplineCurve)

    offset_curves = List()

    def _default_offset_curves(self):
        return self.extract_curves(GeomAbs_OffsetCurve)

    curves = List()

    def _default_curves(self):
        return self.extract_curves(None)


    # -------------------------------------------------------------------------
    # Utilities
    # -------------------------------------------------------------------------
    @classmethod
    def cast_shape(cls, topods_shape):
        """ Convert a TopoDS_Shape into it's actual type, ex an TopoDS_Edge

        Parameters
        -----------
        topods_shape: TopoDS_Shape
            The shape to cas

        Returns
        -------
        shape: TopoDS_Shape
            The actual shape.

        """
        return cls.topo_factory[topods_shape.ShapeType()](topods_shape)

    @classmethod
    def cast_curve(cls, shape, expected_type=None):
        """ Attempt to cast the shape (an edge or wire) to a curve

        Parameters
        ----------
        shape: TopoDS_Edge
            The shape to cast
        expected_type: GeomAbs_CurveType
            The type to restrict

        Returns
        -------
        curve: Curve or None
            The curve or None if it could not be created or if it was not
            of the expected type (if given).
        """
        edge = TopoDS.Edge_(shape)
        curve = BRepAdaptor_Curve(edge)
        return cls.curve_factory[curve.GetType()](curve)

    @classmethod
    def cast_surface(cls, shape, expected_type=None):
        """ Attempt to cast the shape (a face) to a surface

        Parameters
        ----------
        shape: TopoDS_Face
            The shape to cast
        expected_type: GeomAbs_SurfaceType
            The type to restrict

        Returns
        -------
        surface: BRepAdaptor_Surface or None
            The surface or None if it could not be created or did not
            match the expected type (if given).
        """
        if isinstance(shape, TopoDS_Face):
            face = shape
        else:
            face = TopoDS.Face_(shape)
        surface = BRepAdaptor_Surface(face, True)
        if expected_type is not None and surface.GetType() != expected_type:
            return None
        return surface

    @classmethod
    def is_circle(cls, shape):
        """ Check if an edge or wire is a part of a circle.
        This can be used to see if an edge can be used for radius dimensions.

        Returns
        -------
        bool: Bool
            Whether the shape is a part of circle
        """
        edge = TopoDS.Edge_(shape)
        curve = BRepAdaptor_Curve(edge)
        return curve.GetType() == GeomAbs.GeomAbs_Circle

    @classmethod
    def is_ellipse(cls, shape):
        """ Check if an edge or wire is a part of an ellipse.
        This can be used to see if an edge can be used for radius dimensions.

        Returns
        -------
        bool: Bool
            Whether the shape is a part of an ellipse
        """
        edge = TopoDS.Edge_(shape)
        curve = BRepAdaptor_Curve(edge)
        return curve.GetType() == GeomAbs.GeomAbs_Ellipse

    @classmethod
    def is_line(cls, shape):
        """ Check if an edge or wire is a line.
        This can be used to see if an edge can be used for length dimensions.

        Returns
        -------
        bool: Bool
            Whether the shape is a part of a line
        """
        edge = TopoDS.Edge_(shape)
        curve = BRepAdaptor_Curve(edge)
        return curve.GetType() == GeomAbs.GeomAbs_Line

    @classmethod
    def is_plane(cls, shape):
        """ Check if a surface is a plane.

        Returns
        -------
        bool: Bool
            Whether the shape is a part of a line
        """
        surface = cls.cast_surface(shape)
        if surface is None:
            return False
        return surface.GetType() == GeomAbs.GeomAbs_Plane

    @classmethod
    def is_cylinder(cls, shape):
        """ Check if a surface is a cylinder.

        Returns
        -------
        bool: Bool
            Whether the shape is a part of a line
        """
        surface = cls.cast_surface(shape)
        if surface is None:
            return False
        return surface.GetType() == GeomAbs.GeomAbs_Cylinder

    @classmethod
    def is_shape_in_list(cls, shape, shapes):
        """ Check if an shape is in a list of shapes using the IsSame method.

        Parameters
        ----------
        shape: TopoDS_Shape
            The shape to check
        shapes: Iterable[TopoDS_Shape]
            An interable of shapes to check against

        Returns
        -------
        bool: Bool
            Whether the shape is in the list
        """
        if not isinstance(shape, TopoDS_Shape):
            raise TypeError("Expected a TopoDS_Shape instance")
        return any(shape.IsSame(s) for s in shapes)

    @classmethod
    def get_value_at(cls, curve, t, derivative=0):
        """ Get the value of the curve at parameter t with it's derivatives.

        Parameters
        ----------
        curve: BRepAdaptor_Curve
            The curve to get the value from
        t: Float
            The parameter value from 0 to 1
        derivative: Int
            The derivative from 0 to 4

        Returns
        -------
        results: Point or Tuple
            If the derivative is 0 only the position at t is returned,
            otherwise a tuple of the position and all deriviatives.
        """
        p = gp_Pnt()
        if derivative == 0:
            curve.D0(t, p)
            return coerce_point(p)
        v1 = gp_Vec()
        if derivative == 1:
            curve.D1(t, p, v1)
            return (coerce_point(p), coerce_direction(v1))
        v2 = gp_Vec()
        if derivative == 2:
            curve.D1(t, p, v1, v2)
            return (coerce_point(p), coerce_direction(v1),
                    coerce_direction(v2))
        v3 = gp_Vec()
        if derivative == 3:
            curve.D3(t, p, v1, v2, v3)
            return (coerce_point(p), coerce_direction(v1),
                    coerce_direction(v2), coerce_direction(v3))
        raise ValueError("Invalid derivative")


class OccShape(ProxyShape):
    #: A reference to the toolkit shape created by the proxy.
    shape = Typed(TopoDS_Shape)

    #: The shape that was shown on the screen
    ais_shape = Instance(AIS_Shape)

    #: Topology explorer of the shape
    topology = Typed(Topology)

    #: Class reference url
    reference = Str()

    # -------------------------------------------------------------------------
    # Initialization API
    # -------------------------------------------------------------------------
    def create_shape(self):
        """ Create the toolkit shape for the proxy object.

        This method is called during the top-down pass, just before the
        'init_shape()' method is called. This method should create the
        toolkit widget and assign it to the 'widget' attribute.

        """
        raise NotImplementedError

    def init_shape(self):
        """ Initialize the state of the toolkit widget.

        This method is called during the top-down pass, just after the
        'create_widget()' method is called. This method should init the
        state of the widget. The child widgets will not yet be created.

        """
        pass

    def init_layout(self):
        """ Initialize the layout of the toolkit shape.

        """
        pass

    def activate_top_down(self):
        """ Activate the proxy for the top-down pass.

        """
        #log.debug(f"{self}.create_shape()")
        self.create_shape()
        #log.debug(f"{self}.init_shape()")
        self.init_shape()

    def activate_bottom_up(self):
        """ Activate the proxy tree for the bottom-up pass.

        """
        #log.debug(f"{self}.init_layout()")
        self.init_layout()

    # -------------------------------------------------------------------------
    # Defaults and Observers
    # -------------------------------------------------------------------------
    def _default_topology(self):
        if self.shape is None:
            self.create_shape()
        return Topology(shape=self.shape)

    @observe('shape')
    def update_topology(self, change):
        if self.shape is not None:
            self.topology = self._default_topology()


    #@observe('shape')
    #def update_display(self, change):
    #    parent = self.parent()
    #    if parent:
    #        parent.update_display(change)

    def get_first_child(self):
        """ Return shape to apply the operation to. """
        for child in self.children():
            if isinstance(child, OccShape):
                return child

    def child_shapes(self):
        """ Iterator of all child shapes """
        for child in self.children():
            if isinstance(child, OccShape):
                if hasattr(child, 'shapes'):
                    for s in child.shapes:
                        yield s
                else:
                    yield child.shape

    # -------------------------------------------------------------------------
    # Proxy API
    # -------------------------------------------------------------------------
    def get_transform(self):
        """ Create a transform which rotates the default axis to align
        with the normal given by the position

        Returns
        -------
        transform: gp_Trsf

        """
        d = self.declaration

        # Move to position and align along direction axis
        t = gp_Trsf()
        if d.direction.is_parallel(DZ):
            t.SetRotation(AZ, d.direction.angle(DZ) + d.rotation)
        else:
            d1 = d.direction.cross(DZ)
            axis = gp_Ax1(gp_Pnt(0,0,0), d1.proxy)
            t.SetRotation(axis, d.direction.angle(DZ))

            # Apply the rotation an reverse any rotation added in
            sign = 1 if d1.y >= 0 else -1
            angle = d.rotation + sign * d1.angle(DX)

            if angle:
                rot = gp_Trsf()
                rot.SetRotation(AZ, angle)
                t.Multiply(rot)

        t.SetTranslationPart(gp_Vec(*d.position))
        return t

    def set_direction(self, direction):
        self.create_shape()

    def set_axis(self, axis):
        self.create_shape()

    def parent_shape(self):
        return self.parent().shape

    def get_bounding_box(self, shape=None):
        shape = shape or self.shape
        if not shape:
            return BBox()
        bbox = Bnd_Box()
        BRepBndLib.Add_(shape, bbox)
        pmin, pmax  = bbox.CornerMin(), bbox.CornerMax()
        return BBox(*(pmin.X(), pmin.Y(), pmin.Z(),
                      pmax.X(), pmax.Y(), pmax.Z()))


class OccDependentShape(OccShape):
    """ Shape that is dependent on another shape """

    def create_shape(self):
        """ Create the toolkit shape for the proxy object.

        Operations depend on child or properties so they cannot be created
        in the top down pass but rather must be done in the init_layout method.

        """
        pass

    def init_layout(self):
        """ Initialize the layout of the toolkit shape.

        This method is called during the bottom-up pass. This method
        should initialize the layout of the widget. The child widgets
        will be fully initialized and layed out when this is called.

        """
        self.update_shape()
        # log.debug('init_layout %s shape %s' % (self, self.shape))
        assert self.shape is not None, "Shape was not created %s" % self

        # When they change re-compute
        for child in self.children():
           child.observe('shape', self.update_shape)

    def update_shape(self, change=None):
        """ Must be implmented in subclasses to create the shape
            when the dependent shapes change.
        """
        raise NotImplementedError

    def child_added(self, child):
        super(OccDependentShape, self).child_added(child)
        if isinstance(child, OccShape):
            child.observe('shape', self.update_shape)

    def child_removed(self, child):
        super(OccDependentShape, self).child_removed(child)
        if isinstance(child, OccShape):
            child.unobserve('shape', self.update_shape)

    def set_direction(self, direction):
        self.update_shape()

    def set_axis(self, axis):
        self.update_shape()


class OccFace(OccDependentShape, ProxyFace):

    def set_wires(self, wires):
        self.update_shape()

    def shape_to_face(self, shape):
        if isinstance(shape, OccShape):
            shape = shape.shape
        shape = Topology.cast_shape(shape)
        if isinstance(shape, (TopoDS_Face, TopoDS_Wire)):
            return shape
        if isinstance(shape, TopoDS_Edge):
            return BRepBuilderAPI_MakeWire(shape).Wire()
        return TopoDS.Wire_(shape)

    def update_shape(self, change=None):
        d = self.declaration
        if d.wires:
            shapes = d.wires
        else:
            shapes = [c for c in self.children() if isinstance(c, OccShape)]
        if not shapes:
            raise ValueError(
                "No wires or children available to create a face!")

        convert = self.shape_to_face
        for i, s in enumerate(shapes):
            if i == 0:
                shape = BRepBuilderAPI_MakeFace(convert(s))
            else:
                shape.Add(convert(s))
        self.shape = shape.Face()


class OccBox(OccShape, ProxyBox):
    reference = set_default('https://dev.opencascade.org/doc/refman/html/'
                            'class_b_rep_prim_a_p_i___make_box.html')

    def create_shape(self):
        d = self.declaration
        box = BRepPrimAPI_MakeBox(coerce_axis(d.axis), d.dx, d.dy, d.dz)
        self.shape = box.Shape()

    def set_dx(self, dx):
        self.create_shape()

    def set_dy(self, dy):
        self.create_shape()

    def set_dz(self, dz):
        self.create_shape()


class OccCone(OccShape, ProxyCone):
    reference = set_default('https://dev.opencascade.org/doc/refman/html/'
                            'class_b_rep_prim_a_p_i___make_cone.html')

    def create_shape(self):
        d = self.declaration
        args = [coerce_axis(d.axis), d.radius, d.radius2, d.height]
        if d.angle:
            args.append(d.angle)
        cone = BRepPrimAPI_MakeCone(*args)
        self.shape = cone.Shape()

    def set_radius(self, r):
        self.create_shape()

    def set_radius2(self, r):
        self.create_shape()

    def set_height(self, height):
        self.create_shape()

    def set_angle(self, a):
        self.create_shape()


class OccCylinder(OccShape, ProxyCylinder):
    reference = set_default('https://dev.opencascade.org/doc/refman/html/'
                            'class_b_rep_prim_a_p_i___make_cylinder.html')

    def create_shape(self):
        d = self.declaration
        args = [coerce_axis(d.axis), d.radius, d.height]
        if d.angle:
            args.append(d.angle)
        cylinder = BRepPrimAPI_MakeCylinder(*args)
        self.shape = cylinder.Shape()

    def set_radius(self, r):
        self.create_shape()

    def set_angle(self, angle):
        self.create_shape()

    def set_height(self, height):
        self.create_shape()


class OccHalfSpace(OccDependentShape, ProxyHalfSpace):
    reference = set_default('https://dev.opencascade.org/doc/refman/html/'
                            'class_b_rep_prim_a_p_i___make_half_space.html')

    def update_shape(self, change=None):
        d = self.declaration
        if d.surface:
            surface = d.surface
        else:
            child = self.get_first_child()
            if child:
                surface = child.shape
            else:
                pln = gp_Pln(d.position.proxy, d.direction.proxy)
                surface = BRepBuilderAPI_MakeFace(pln).Face()
        half_space = BRepPrimAPI_MakeHalfSpace(surface, d.side.proxy)
        # Shape doesnt work see https://tracker.dev.opencascade.org/view.php?id=29969
        self.shape = half_space.Solid()

    def set_surface(self, surface):
        self.update_shape()

    def set_side(self, side):
        self.update_shape()


class OccPrism(OccDependentShape, ProxyPrism):
    reference = set_default('https://dev.opencascade.org/doc/refman/html/'
                            'class_b_rep_prim_a_p_i___make_prism.html')

    def update_shape(self, change=None):
        d = self.declaration

        if d.shape:
            shape = coerce_shape(d.shape)
            copy = True
        else:

            shape = self.get_shape().shape
            copy = False

        if d.infinite:
            args = (shape, d.direction.proxy, True, copy, d.canonize)
        else:
            args = (shape, gp_Vec(*d.vector), copy, d.canonize)
        prism = BRepPrimAPI_MakePrism(*args)
        self.shape = prism.Shape()

    def get_shape(self):
        for child in self.children():
            if isinstance(child, OccShape):
                return child

    def set_shape(self, shape):
        self.update_shape()

    def set_infinite(self, infinite):
        self.update_shape()

    def set_copy(self, copy):
        self.update_shape()

    def set_canonize(self, canonize):
        self.update_shape()

    def set_direction(self, direction):
        self.update_shape()

    def set_vector(self, vector):
        self.update_shape()


class OccRevol(OccDependentShape, ProxyRevol):

    #: Update the class reference
    reference = set_default('https://dev.opencascade.org/doc/refman/html/'
                            'class_b_rep_prim_a_p_i___make_wedge.html')

    def update_shape(self, change=None):
        d = self.declaration

        if d.shape:
            shape = coerce_shape(d.shape)
            copy = True
        else:
            shape = self.get_shape().shape
            copy = False

        #: Build arguments
        args = [shape, gp_Ax1(d.position.proxy, d.direction.proxy)]
        if d.angle:
            args.append(d.angle)
        args.append(copy)
        revol = BRepPrimAPI_MakeRevol(*args)
        self.shape = revol.Shape()

    def get_shape(self):
        """ Get the first child shape """
        for child in self.children():
            if isinstance(child, OccShape):
                return child

    def set_shape(self, shape):
        self.update_shape()

    def set_angle(self, angle):
        self.update_shape()

    def set_copy(self, copy):
        self.update_shape()

    def set_direction(self, direction):
        self.update_shape()


class OccSphere(OccShape, ProxySphere):
    reference = set_default('https://dev.opencascade.org/doc/refman/html/'
                            'class_b_rep_prim_a_p_i___make_sphere.html')

    def create_shape(self):
        d = self.declaration
        u = min(2*pi, max(0, d.angle))
        vmin = max(-pi/2, min(d.angle2, d.angle3))
        vmax = min(pi/2, max(d.angle2, d.angle3))
        sphere = BRepPrimAPI_MakeSphere(
            coerce_axis(d.axis), d.radius, vmin, vmax, u)
        self.shape = sphere.Shape()

    def set_radius(self, r):
        self.create_shape()

    def set_angle(self, a):
        self.create_shape()

    def set_angle2(self, a):
        self.create_shape()

    def set_angle3(self, a):
        self.create_shape()


class OccTorus(OccShape, ProxyTorus):

    reference = set_default('https://dev.opencascade.org/doc/refman/html/'
                            'class_b_rep_prim_a_p_i___make_torus.html')

    def create_shape(self):
        d = self.declaration
        args = [coerce_axis(d.axis), d.radius, d.radius2]
        if d.angle2 or d.angle3:
            amin = min(d.angle2, d.angle3)
            amax = max(d.angle2, d.angle3)
            args.append(amin)
            args.append(amax)
        if d.angle:
            args.append(d.angle)
        torus = BRepPrimAPI_MakeTorus(*args)
        self.shape = torus.Shape()

    def set_radius(self, r):
        self.create_shape()

    def set_radius2(self, r):
        self.create_shape()

    def set_angle(self, a):
        self.create_shape()

    def set_angle2(self, a):
        self.create_shape()

    def set_angle3(self, a):
        self.create_shape()


class OccWedge(OccShape, ProxyWedge):

    reference = set_default('https://dev.opencascade.org/doc/refman/html/'
                            'class_b_rep_prim_a_p_i___make_wedge.html')

    def create_shape(self):
        d = self.declaration
        wedge = BRepPrimAPI_MakeWedge(
            coerce_axis(d.axis), d.dx, d.dy, d.dz, d.itx)
        self.shape = wedge.Shape()

    def set_dx(self, dx):
        self.create_shape()

    def set_dy(self, dy):
        self.create_shape()

    def set_dz(self, dz):
        self.create_shape()

    def set_itx(self, itx):
        self.create_shape()


class OccRawShape(OccShape, ProxyRawShape):
    #: Update the class reference
    reference = set_default('https://dev.opencascade.org/doc/refman/html/'
                            'class_topo_d_s___shape.html')

    def create_shape(self):
        """ Delegate shape creation to the declaration implementation. """
        self.shape = self.declaration.create_shape(self.parent_shape())

    # -------------------------------------------------------------------------
    # ProxyRawShape API
    # -------------------------------------------------------------------------
    def get_shape(self):
        """ Retrieve the underlying toolkit shape.
        """
        return self.shape


class OccLoadShape(OccShape, ProxyLoadShape):
    #: Update the class reference
    reference = set_default('https://dev.opencascade.org/doc/refman/html/'
                            'class_topo_d_s___shape.html')

    def create_shape(self):
        """ Create the shape by loading it from the given path. """
        shape = self.load_shape()
        t = self.get_transform()
        loaded_shape = BRepBuilderAPI_Transform(shape, t, False)
        self.shape = loaded_shape.Shape()

    def get_transform(self):
        d = self.declaration
        t = gp_Trsf()
        t.SetTransformation(gp_Ax3(coerce_axis(d.axis)))
        return t

    def load_shape(self):
        d = self.declaration
        if not os.path.exists(d.path):
            raise ValueError("Can't load shape from `{}`, "
                             "the path does not exist".format(d.path))
        path, ext = os.path.splitext(d.path)
        name = ext[1:] if d.loader == 'auto' else d.loader
        loader = getattr(self, 'load_{}'.format(name.lower()))
        return loader(d.path)

    def load_brep(self, path):
        """ Load a brep model """
        shape = TopoDS_Shape()
        builder = BRep_Builder()
        BRepTools.Read_(shape, path, builder, None)
        return shape

    def load_iges(self, path):
        """ Load an iges model """
        reader = IGESControl_Reader()
        status = reader.ReadFile(path)
        if status != IFSelect_RetDone:
            raise ValueError("Failed to load: {}".format(path))
        reader.PrintCheckLoad(False, IFSelect_ItemsByEntity)
        reader.PrintCheckTransfer(False, IFSelect_ItemsByEntity)
        ok = reader.TransferRoots()
        return reader.Shape(1)

    def load_step(self, path):
        """ Alias for stp """
        return self.load_stp(path)

    def load_stp(self, path):
        """ Load a stp model """
        reader = STEPControl_Reader()
        status = reader.ReadFile(path)
        if status != IFSelect_RetDone:
            raise ValueError("Failed to load: {}".format(path))
        reader.PrintCheckLoad(False, IFSelect_ItemsByEntity)
        reader.PrintCheckTransfer(False, IFSelect_ItemsByEntity)
        ok = reader.TransferRoot()
        return reader.Shape(1)

    def load_stl(self, path):
        """ Load a stl model """
        builder = BRep_Builder()
        shape = TopoDS_Face()
        builder.MakeFace(shape)
        poly = RWStl.ReadFile_(path, None)
        builder.UpdateFace(shape, poly)
        return shape

    def load_dxf(self, path):
        """ Load a dxf model """
        from declaracad.occ.importers import dxf
        return dxf.load(path)

    # -------------------------------------------------------------------------
    # ProxyLoadShape API
    # -------------------------------------------------------------------------
    def set_path(self, path):
        self.create_shape()

    def set_loader(self, loader):
        self.create_shape()
