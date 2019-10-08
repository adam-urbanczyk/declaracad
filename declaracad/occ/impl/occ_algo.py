"""
Copyright (c) 2016-2018, Jairus Martin.

Distributed under the terms of the GPL v3 License.

The full license is in the file LICENSE, distributed with this software.

Created on Sep 27, 2016

@author: jrm
"""
from atom.api import Int, Dict, Instance, set_default
from enaml.application import timed_call
from ..algo import (
    ProxyOperation, ProxyBooleanOperation, ProxyCommon, ProxyCut, ProxyFuse,
    ProxyFillet, ProxyChamfer, ProxyOffset, ProxyThickSolid, ProxyPipe,
    ProxyThruSections, ProxyTransform, Translate, Rotate, Scale, Mirror
)
from .occ_shape import OccShape, OccDependentShape
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
    gp_Trsf, gp_Vec, gp_Pnt, gp_Ax1, gp_Dir, gp_Pnt2d
)
from OCCT.TopTools import TopTools_ListOfShape
from OCCT.TopAbs import TopAbs_WIRE
from OCCT.TopoDS import TopoDS_Edge, TopoDS_Face
from OCCT.TColgp import TColgp_Array1OfPnt2d

from declaracad.core.utils import log


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

    def update_shape(self, change=None):
        d = self.declaration
        if d.shape1 and d.shape2:
            shape = self._do_operation(d.shape1, d.shape2)
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
    reference = set_default('https://dev.opencascade.org/doc/refman/html/'
                            'class_b_rep_algo_a_p_i___fuse.html')
    def _do_operation(self, shape1, shape2):
        return BRepAlgoAPI_Fuse(shape1, shape2).Shape()


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
        shape = BRepFilletAPI_MakeFillet(child.shape)

        # TODO: Set shape type

        operations = d.operations if d.operations else child.topology.edges
        for item in operations:
            if not isinstance(item, (list, tuple)):
                shape.Add(d.radius, item)
                continue

            # If an array of points is create a changing radius fillet
            if len(item) == 2 and isinstance(item[0], (list, tuple)):
                pts, edge = item
                array = TColgp_Array1OfPnt2d(1, len(pts))
                for i, pt in enumerate(pts):
                    array.SetValue(i+1, gp_Pnt2d(*pt))
                shape.Add(array, edge)
                continue

            # custom radius or r1 and r2 radius fillets
            shape.Add(*item)

        self.shape = shape.Shape()

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

    offset_modes = Dict(default={
        'skin': BRepOffset_Skin,
        'pipe': BRepOffset_Pipe,
        'recto_verso': BRepOffset_RectoVerso
    })

    join_types = Dict(default={
        'arc': GeomAbs_Arc,
        'tangent': GeomAbs_Tangent,
        'intersection': GeomAbs_Intersection,
    })

    def update_shape(self, change=None):
        d = self.declaration

        #: Get the shape to apply the fillet to
        child = self.get_first_child()

        offset_shape = BRepOffsetAPI_MakeOffsetShape()

        if child.shape.ShapeType() == TopAbs_WIRE:
            offset_shape.PerformBySimple(
                TopoDS.Wire_(child.shape),
                d.offset
            )
        else:
            offset_shape.PerformByJoin(
                child.shape,
                d.offset,
                d.tolerance,
                self.offset_modes[d.offset_mode],
                d.intersection,
                False,
                self.join_types[d.join_type]
            )

        self.shape = offset_shape.Shape()

    def set_offset(self, offset):
        self.update_shape()

    def set_offset_mode(self, mode):
        self.update_shape()

    def set_join_type(self, mode):
        self.update_shape()

    def set_intersection(self, enabled):
        self.update_shape()


class OccThickSolid(OccOffset, ProxyThickSolid):
    reference = set_default('https://dev.opencascade.org/doc/refman/html/'
                            'class_b_rep_offset_a_p_i___make_thick_solid.html')

    def get_faces(self, child):
        d = self.declaration
        if d.faces:
            return d.faces
        for face in child.topology.faces:
            return [face]

    def update_shape(self, change=None):
        d = self.declaration

        #: Get the shape to apply the fillet to
        child = self.get_first_child()
        assert child.shape is not None, \
            "Cannot create thick solid from empty shape: %s" % child.declaration

        faces = TopTools_ListOfShape()
        for f in self.get_faces(child):
            faces.Append(f)
        assert not faces.IsEmpty()

        thick_solid = BRepOffsetAPI_MakeThickSolid()
        thick_solid.MakeThickSolidByJoin(
            child.shape,
            faces,
            d.offset,
            d.tolerance,
            self.offset_modes[d.offset_mode],
            d.intersection,
            False,
            self.join_types[d.join_type]
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
        shape = BRepOffsetAPI_ThruSections(d.solid, d.ruled, d.precision)

        #: TODO: Support Smoothing, Max degree, par type, etc...

        for child in self.children():
            if isinstance(child, OccVertex):
                shape.AddVertex(child.shape)
            elif isinstance(child, OccWire):
                shape.AddWire(child.shape)
            #: TODO: Handle transform???

        #: Set the shape
        self.shape = shape.Shape()

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

    def init_shape(self):
        d = self.declaration
        if d.shape:
            #: Make sure we bind the observer
            self.set_shape(d.shape)

    def get_shape(self):
        """ Return shape to apply the transform to. """
        for child in self.children():
            return child

    def get_transform(self):
        d = self.declaration
        result = gp_Trsf()
        #: TODO: Order matters... how to configure it???
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
        return result

    def update_shape(self, change=None):
        d = self.declaration

        #: Get the shape to apply the tranform to
        if d.shape:
            make_copy = True
            s = d.shape.proxy
        else:
            # Use the first child
            make_copy = False
            s = self.get_shape()
        t = self.get_transform()
        self.shape = BRepBuilderAPI_Transform(s.shape, t, make_copy).Shape()

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
