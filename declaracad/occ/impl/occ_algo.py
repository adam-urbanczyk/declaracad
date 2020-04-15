"""
Copyright (c) 2016-2018, Jairus Martin.

Distributed under the terms of the GPL v3 License.

The full license is in the file LICENSE, distributed with this software.

Created on Sep 27, 2016

@author: jrm
"""
from atom.api import Int, Dict, Instance, set_default
from enaml.application import timed_call

from OCCT.BOPAlgo import BOPAlgo_Splitter, BOPAlgo_Section
from OCCT.BRepAlgoAPI import (
    BRepAlgoAPI_Fuse, BRepAlgoAPI_Common,
    BRepAlgoAPI_Cut
)
from OCCT.BRepBuilderAPI import (
    BRepBuilderAPI_Transform, BRepBuilderAPI_MakeWire
)
from OCCT.BRepFilletAPI import (
    BRepFilletAPI_MakeFillet, BRepFilletAPI_MakeChamfer
)
from OCCT.BRepOffsetAPI import (
    BRepOffsetAPI_MakeOffset, BRepOffsetAPI_MakeOffsetShape,
    BRepOffsetAPI_MakeThickSolid, BRepOffsetAPI_MakePipe,
    BRepOffsetAPI_ThruSections
)
from OCCT.BRepOffset import (
    BRepOffset_Skin, BRepOffset_Pipe,
    BRepOffset_RectoVerso
)
from OCCT.ChFi3d import (
    ChFi3d_Rational, ChFi3d_QuasiAngular, ChFi3d_Polynomial
)
from OCCT.GeomAbs import (
    GeomAbs_Arc, GeomAbs_Tangent, GeomAbs_Intersection
)
from OCCT.GeomFill import (
    GeomFill_IsCorrectedFrenet, GeomFill_IsFixed,
    GeomFill_IsFrenet, GeomFill_IsConstantNormal, GeomFill_IsDarboux,
    GeomFill_IsGuideAC, GeomFill_IsGuidePlan,
    GeomFill_IsGuideACWithContact,GeomFill_IsGuidePlanWithContact,
    GeomFill_IsDiscreteTrihedron
)
from OCCT.gp import (
    gp_Trsf, gp_Vec, gp_Pnt, gp_Ax1, gp_Ax3, gp_Dir, gp_Pnt2d
)
from OCCT.TColgp import TColgp_Array1OfPnt2d
from OCCT.TopTools import TopTools_ListOfShape
from OCCT.TopoDS import (
    TopoDS, TopoDS_Edge, TopoDS_Face, TopoDS_Wire, TopoDS_Shape
)


from declaracad.core.utils import log
from declaracad.occ.algo import (
    ProxyOperation, ProxyBooleanOperation, ProxyCommon, ProxyCut, ProxyFuse,
    ProxyFillet, ProxyChamfer, ProxyOffset, ProxyOffsetShape, ProxyThickSolid,
    ProxyPipe, ProxyThruSections, ProxySplit, ProxyIntersection,
    ProxyTransform, Translate, Rotate, Scale, Mirror, Shape
)

from .occ_shape import (
    OccShape, OccDependentShape, Topology, coerce_axis, coerce_shape
)


class OccOperation(OccDependentShape, ProxyOperation):
    """ Operation is a dependent shape that uses queuing to only
    perform the operation once all changes have settled because
    in general these operations are expensive.
    """
    def set_direction(self, direction):
        self.update_shape()

    def set_axis(self, axis):
        self.update_shape()


class OccBooleanOperation(OccOperation, ProxyBooleanOperation):
    """ Base class for a boolean shape operation.

    """

    def _do_operation(self, shape1, shape2):
        raise NotImplementedError()

    def update_shape(self, change=None):
        d = self.declaration
        if d.shape1 and d.shape2:
            shape = self._do_operation(
                coerce_shape(d.shape1), coerce_shape(d.shape2))
        else:
            shape = None

        for c in self.children():
            if shape:
                shape = self._do_operation(shape, c.shape)
            else:
                shape = c.shape
        self.shape = shape


class OccCommon(OccBooleanOperation, ProxyCommon):
    """ Common of all the child shapes together. """
    reference = set_default('https://dev.opencascade.org/doc/refman/html/'
                            'class_b_rep_algo_a_p_i___common.html')

    def _do_operation(self, shape1, shape2):
        return BRepAlgoAPI_Common(shape1, shape2).Shape()


class OccCut(OccBooleanOperation, ProxyCut):
    """ Cut all the child shapes from the first shape. """
    reference = set_default('https://dev.opencascade.org/doc/refman/html/'
                            'class_b_rep_algo_a_p_i___cut.html')

    def _do_operation(self, shape1, shape2):
        return BRepAlgoAPI_Cut(shape1, shape2).Shape()


class OccFuse(OccBooleanOperation, ProxyFuse):
    """ Fuse all the child shapes together. """
    reference = set_default(
        'https://dev.opencascade.org/doc/overview/html/'
        'occt_user_guides__boolean_operations.html#occt_algorithms_7')
    def _do_operation(self, shape1, shape2):
        return BRepAlgoAPI_Fuse(shape1, shape2).Shape()


class OccIntersection(OccBooleanOperation, ProxyIntersection):
    reference = set_default(
        'https://dev.opencascade.org/doc/overview/html/'
        'occt_user_guides__boolean_operations.html#occt_algorithms_10a')

    def update_shape(self, change=None):
        section = BOPAlgo_Section()
        d = self.declaration
        if d.shape1:
            section.AddArgument(coerce_shape(d.shape1))
        if d.shape2:
            section.AddArgument(coerce_shape(d.shape2))
        for c in self.children():
            section.AddArgument(c.shape)
        section.Perform()
        if section.HasErrors():
            raise ValueError("Could not intersect shape %s" % d)
        self.shape = section.Shape()


class OccSplit(OccBooleanOperation, ProxySplit):
    """ Fuse all the child shapes together. """
    reference = set_default(
        'https://dev.opencascade.org/doc/overview/html/'
        'occt_user_guides__boolean_operations.html#occt_algorithms_8')

    def update_shape(self, change=None):
        splitter = BOPAlgo_Splitter()
        d = self.declaration
        tools = TopTools_ListOfShape()
        if d.shape1:
            shape = d.shape1
            splitter.AddArgument(shape)
        else:
            shape = None
        if d.shape2:
            tools.Append(d.shape2)
        for c in self.children():
            if shape:
                tools.Append(c.shape)
            else:
                shape = c.shape
                splitter.AddArgument(shape)
        splitter.SetTools(tools)
        splitter.Perform()
        if splitter.HasErrors():
            raise ValueError("Could not split shape %s" % d)
        self.shape = splitter.Shape()


class OccFillet(OccOperation, ProxyFillet):
    reference = set_default('https://dev.opencascade.org/doc/refman/html/'
                            'class_b_rep_fillet_a_p_i___make_fillet.html')

    shape_types = {
        'rational': ChFi3d_Rational,
        'angular': ChFi3d_QuasiAngular,
        'polynomial': ChFi3d_Polynomial
    }

    def update_shape(self, change=None):
        d = self.declaration
        # Get the shape to apply the fillet to
        child = self.get_first_child()
        fillet = BRepFilletAPI_MakeFillet(child.shape)

        # TODO: Set shape type

        operations = d.operations if d.operations else child.topology.edges
        for item in operations:
            if not isinstance(item, (list, tuple)):
                fillet.Add(d.radius, item)
                continue

            # If an array of points is create a changing radius fillet
            if len(item) == 2 and isinstance(item[0], (list, tuple)):
                pts, edge = item
                array = TColgp_Array1OfPnt2d(1, len(pts))
                for i, pt in enumerate(pts):
                    array.SetValue(i+1, gp_Pnt2d(*pt))
                fillet.Add(array, edge)
                continue

            # custom radius or r1 and r2 radius fillets
            fillet.Add(*item)
        self.shape = fillet.Shape()

    def set_shape_type(self, shape_type):
        self.update_shape()

    def set_radius(self, r):
        self.update_shape()

    def set_operations(self, operations):
        self.update_shape()


class OccChamfer(OccOperation, ProxyChamfer):
    reference = set_default('https://dev.opencascade.org/doc/refman/html/'
                            'class_b_rep_fillet_a_p_i___make_chamfer.html')

    def update_shape(self, change=None):
        d = self.declaration

        #: Get the shape to apply the fillet to
        child = self.get_first_child()
        chamfer = BRepFilletAPI_MakeChamfer(child.shape)

        operations = d.operations if d.operations else child.topology.faces

        for item in operations:
            edge = None
            d1, d2 = d.distance, d.distance2 or d.distance
            if isinstance(item, (tuple, list)):
                face = item[-1]
                n = len(item)
                if n > 1:
                    i = 0
                    if isinstance(item[-2], TopoDS_Edge):
                        edge = item[-2]
                        i += 1
                    if n == i + 2:
                        d1 = d2 = item[0]
                    elif n == i + 3:
                        d1, d2 = item[0:2]
            else:
                face = item

            if edge is None:
                for edge in child.topology.edges_from_face(face):
                    chamfer.Add(d1, d2, edge, face)
            else:
                chamfer.Add(d1, d2, edge, face)
        self.shape = chamfer.Shape()

    def set_distance(self, d):
        self.update_shape()

    def set_distance2(self, d):
        self.update_shape()

    def set_operations(self, operations):
        self.update_shape()


class OccOffset(OccOperation, ProxyOffset):
    reference = set_default('https://dev.opencascade.org/doc/refman/html/'
                            'class_b_rep_offset_a_p_i___make_offset.html')

    offset_modes = {
        'skin': BRepOffset_Skin,
        'pipe': BRepOffset_Pipe,
        'recto_verso': BRepOffset_RectoVerso
    }

    join_types = {
        'arc': GeomAbs_Arc,
        'tangent': GeomAbs_Tangent,
        'intersection': GeomAbs_Intersection,
    }

    def get_shape_to_offset(self):
        d = self.declaration
        if d.shape:
            return coerce_shape(d.shape)
        else:
            #: Get the shape to apply the fillet to
            child = self.get_first_child()
            return child.shape

    def update_shape(self, change=None):
        d = self.declaration
        shape = self.get_shape_to_offset()
        if isinstance(shape, TopoDS_Edge):
            shape = BRepBuilderAPI_MakeWire(shape).Wire()
        elif not isinstance(shape, (TopoDS_Wire, TopoDS_Face)):
            t = type(shape)
            raise TypeError(
                "Unsupported child shape %s when using planar mode" % t)
        offset_shape = BRepOffsetAPI_MakeOffset(
            shape, self.join_types[d.join_type], not d.closed)
        offset_shape.Perform(d.offset)
        self.shape = offset_shape.Shape()

    def set_shape(self, shape):
        self.update_shape()

    def set_offset(self, offset):
        self.update_shape()

    def set_offset_mode(self, mode):
        self.update_shape()

    def set_join_type(self, mode):
        self.update_shape()

    def set_intersection(self, enabled):
        self.update_shape()


class OccOffsetShape(OccOffset, ProxyOffsetShape):
    reference = set_default('https://dev.opencascade.org/doc/refman/html/'
                            'class_b_rep_offset_a_p_i___make_offset_shape.html')

    def update_shape(self, change=None):
        d = self.declaration
        shape = self.get_shape_to_offset()
        offset_shape = BRepOffsetAPI_MakeOffsetShape()
        offset_shape.PerformByJoin(
            shape,
            d.offset,
            d.tolerance,
            self.offset_modes[d.offset_mode],
            d.intersection,
            False,
            self.join_types[d.join_type]
        )
        self.shape = offset_shape.Shape()


class OccThickSolid(OccOffset, ProxyThickSolid):
    reference = set_default('https://dev.opencascade.org/doc/refman/html/'
                            'class_b_rep_offset_a_p_i___make_thick_solid.html')

    def get_faces(self, occ_shape):
        d = self.declaration
        if d.faces:
            return d.faces

        if isinstance(occ_shape, TopoDS_Shape):
            topology = Topology(shape=occ_shape)
        else:
            topology = occ_shape.topology

        for face in topology.faces:
            return [face]

    def update_shape(self, change=None):
        d = self.declaration
        shape = self.get_shape_to_offset()
        faces = TopTools_ListOfShape()
        for f in self.get_faces(shape):
            faces.Append(f)
        assert not faces.IsEmpty()

        offset_mode = self.offset_modes[d.offset_mode]
        join_type = self.join_types[d.join_type]

        thick_solid = BRepOffsetAPI_MakeThickSolid()
        thick_solid.MakeThickSolidByJoin(
            shape,
            faces,
            d.offset,
            d.tolerance,
            offset_mode,
            d.intersection,
            False,
            join_type,
        )
        self.shape = thick_solid.Shape()

    def set_faces(self, faces):
        self.update_shape()


class OccPipe(OccOperation, ProxyPipe):
    reference = set_default('https://dev.opencascade.org/doc/refman/html/'
                            'class_b_rep_offset_a_p_i___make_pipe.html')

    #: References to observed shapes
    _old_spline = Instance(OccShape)
    _old_profile = Instance(OccShape)

    fill_modes = Dict(default={
        'corrected_frenet': GeomFill_IsCorrectedFrenet,
        'fixed': GeomFill_IsFixed,
        'frenet': GeomFill_IsFrenet,
        'constant_normal': GeomFill_IsConstantNormal,
        'darboux': GeomFill_IsDarboux,
        'guide_ac': GeomFill_IsGuideAC,
        'guide_plan': GeomFill_IsGuidePlan,
        'guide_ac_contact': GeomFill_IsGuideACWithContact,
        'guide_plan_contact': GeomFill_IsGuidePlanWithContact,
        'discrete_trihedron': GeomFill_IsDiscreteTrihedron
    })

    def init_shape(self):
        super(OccPipe, self).init_shape()
        d = self.declaration
        if d.spline:
            self.set_spline(d.spline)
        if d.profile:
            self.set_profile(d.profile)

    def update_shape(self, change=None):
        d = self.declaration

        if d.spline and d.profile:
            spline, profile = d.spline.proxy, d.profile.proxy
        elif d.spline:
            spline = d.spline.proxy
            profile = self.get_first_child()
        elif d.profile:
            profile = d.spline.proxy
            spline = self.get_first_child()
        else:
            shapes = [c for c in self.children() if isinstance(c, OccShape)]
            spline, profile = shapes[0:2]

        args = [spline.shape, profile.shape]

        # Make sure spline is a wire
        if isinstance(args[0], TopoDS_Edge):
            args[0] = BRepBuilderAPI_MakeWire(args[0]).Wire()

        if d.fill_mode:
            args.append(self.fill_modes[d.fill_mode])
        pipe = BRepOffsetAPI_MakePipe(*args)
        self.shape = pipe.Shape()

    def set_spline(self, spline):
        # Unobserve the old spline and observe the new one
        if self._old_spline:
            self._old_spline.unobserve('shape', self.update_shape)
        child = spline.proxy
        child.observe('shape', self.update_shape)
        self._old_spline = child

        # Trigger an update if the shape was already built
        if self.shape:
            self.update_shape()

    def set_profile(self, profile):
        # Unobserve the old spline and observe the new one
        if self._old_profile:
            self._old_profile.unobserve('shape', self.update_shape)
        child = profile.proxy
        child.observe('shape', self.update_shape)
        self._old_profile = child

        # Trigger an update if the shape was already built
        if self.shape:
            self.update_shape()

    def set_fill_mode(self, mode):
        self.update_shape()


class OccThruSections(OccOperation, ProxyThruSections):
    reference = set_default('https://dev.opencascade.org/doc/refman/html/'
                            'class_b_rep_offset_a_p_i___thru_sections.html')

    def update_shape(self, change=None):
        from .occ_draw import OccVertex, OccWire

        d = self.declaration
        thru_sect = BRepOffsetAPI_ThruSections(d.solid, d.ruled, d.precision)

        #: TODO: Support Smoothing, Max degree, par type, etc...

        for child in self.children():
            if isinstance(child, OccVertex):
                thru_sect.AddVertex(child.shape)
            elif isinstance(child, OccWire):
                thru_sect.AddWire(child.shape)
            #: TODO: Handle transform???

        #: Set the shape
        self.shape = thru_sect.Shape()

    def set_solid(self, solid):
        self.update_shape()

    def set_ruled(self, ruled):
        self.update_shape()

    def set_precision(self, pres3d):
        self.update_shape()


class OccTransform(OccOperation, ProxyTransform):
    reference = set_default('https://dev.opencascade.org/doc/refman/html/'
                            'classgp___trsf.html')

    _old_shape = Instance(OccShape)

    def get_transform(self):
        d = self.declaration
        result = gp_Trsf()
        #: TODO: Order matters... how to configure it???
        if d.operations:
            for op in d.operations:
                t = gp_Trsf()
                if isinstance(op, Translate):
                    t.SetTranslation(gp_Vec(op.x, op.y, op.z))
                elif isinstance(op, Rotate):
                    t.SetRotation(gp_Ax1(gp_Pnt(*op.point),
                                        gp_Dir(*op.direction)), op.angle)
                elif isinstance(op, Mirror):
                    t.SetMirror(gp_Ax1(gp_Pnt(*op.point),
                                    gp_Dir(op.x, op.y, op.z)))
                elif isinstance(op, Scale):
                    t.SetScale(gp_Pnt(*op.point), op.s)
                result.Multiply(t)
        else:
            axis = gp_Ax3()
            axis.SetDirection(d.direction.proxy)
            result.SetTransformation(axis)
            result.SetTranslationPart(gp_Vec(*d.position))
        return result

    def update_shape(self, change=None):
        d = self.declaration

        #: Get the shape to apply the tranform to
        if d.shape:
            make_copy = True
            original = coerce_shape(d.shape)
        else:
            # Use the first child
            make_copy = False
            child = self.get_first_child()
            original = child.shape

        t = self.get_transform()
        transform = BRepBuilderAPI_Transform(original, t, make_copy)
        shape = transform.Shape()

        # Convert it back to the original type
        self.shape = Topology.cast_shape(shape)

    def set_shape(self, shape):
        if self._old_shape:
            self._old_shape.unobserve('shape', self.update_shape)
        self._old_shape = shape.proxy
        self._old_shape.observe('shape', self.update_shape)

    def set_translate(self, translation):
        self.update_shape()

    def set_rotate(self, rotation):
        self.update_shape()

    def set_scale(self, scale):
        self.update_shape()

    def set_mirror(self, axis):
        self.update_shape()
