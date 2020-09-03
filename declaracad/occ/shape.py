# -*- coding: utf-8 -*-
"""
Copyright (c) 2016-2018, Jairus Martin.

Distributed under the terms of the GPL v3 License.

The full license is in the file LICENSE, distributed with this software.

Created on Sep 30, 2016

@author: jrm
"""
import math
from math import pi
from atom.api import (
    Atom, Tuple, Instance, Bool, Str, Float, FloatRange, Property, Coerced,
    Typed, ForwardTyped, List, Enum, Event, observe
)

from contextlib import contextmanager
from enaml.core.declarative import d_
from enaml.colors import ColorMember
from enaml.widgets.control import ProxyControl
from enaml.widgets.toolkit_object import ToolkitObject


from declaracad.core.utils import log

#: TODO: This breaks the proxy pattern
from OCCT.gp import gp, gp_Pnt, gp_Dir, gp_Vec
from OCCT.BRep import BRep_Tool
from OCCT.TopoDS import TopoDS_Face, TopoDS_Shell, TopoDS_Shape


class BBox(Atom):
    xmin = Float()
    ymin = Float()
    zmin = Float()
    xmax = Float()
    ymax = Float()
    zmax = Float()

    def _get_dx(self):
        return self.xmax-self.xmin

    dx = Property(_get_dx, cached=True)

    def _get_dy(self):
        return self.ymax-self.ymin

    dy = Property(_get_dy, cached=True)

    def _get_dz(self):
        return self.zmax-self.zmin

    dz = Property(_get_dz, cached=True)

    def __init__(self, xmin=0, ymin=0, zmin=0, xmax=0, ymax=0, zmax=0):
        super(BBox, self).__init__(xmin=xmin, ymin=ymin, zmin=zmin,
                                   xmax=xmax, ymax=ymax, zmax=zmax)

    def __getitem__(self, key):
        return (self.xmin, self.ymin, self.zmin,
                self.xmax, self.ymax, self.zmax)[key]

    def _get_center(self):
        return Point((self.xmin + self.xmax)/2,
                     (self.ymin + self.ymax)/2,
                     (self.zmin + self.zmax)/2)
    center = Property(_get_center, cached=True)

    def _get_diagonal(self):
        return math.sqrt(self.dx**2+self.dy**2+self.dz**2)

    diagonal = Property(_get_diagonal, cached=True)

    def _get_min(self):
        return Point(self.xmin, self.ymin, self.zmin)

    def _get_max(self):
        return Point(self.xmax, self.xmax, self.xmax)

    min = Property(_get_min)
    max = Property(_get_max)

    def __repr__(self):
        return "<BBox: x=%s y=%s z=%s w=%s h=%s d=%s>" % (
            self.xmin, self.ymin, self.zmin, self.dx, self.dy, self.dz)


class ProxyShape(ProxyControl):
    #: A reference to the Shape declaration.
    declaration = ForwardTyped(lambda: Shape)

    def set_position(self, position):
        pass

    def set_direction(self, direction):
        pass

    def set_axis(self, axis):
        raise NotImplementedError

    def set_color(self, color):
        pass

    def set_transparency(self, alpha):
        pass

    def set_texture(self, texture):
        pass

    def get_bounding_box(self):
        raise NotImplementedError


class ProxyFace(ProxyShape):
    #: A reference to the Shape declaration.
    declaration = ForwardTyped(lambda: Face)

    def set_wire(self, wire):
        raise NotImplementedError


class ProxyBox(ProxyShape):
    #: A reference to the shape declaration.
    declaration = ForwardTyped(lambda: Box)

    def set_dx(self, dx):
        raise NotImplementedError

    def set_dy(self, dy):
        raise NotImplementedError

    def set_dz(self, dz):
        raise NotImplementedError


class ProxyCone(ProxyShape):
    #: A reference to the shape declaration.
    declaration = ForwardTyped(lambda: Cone)

    def set_radius(self, r):
        raise NotImplementedError

    def set_radius2(self, r):
        raise NotImplementedError

    def set_height(self, height):
        raise NotImplementedError

    def set_angle(self, angle):
        raise NotImplementedError


class ProxyCylinder(ProxyShape):
    #: A reference to the shape declaration.
    declaration = ForwardTyped(lambda: Cylinder)

    def set_radius(self, r):
        raise NotImplementedError

    def set_height(self, height):
        raise NotImplementedError

    def set_angle(self, angle):
        raise NotImplementedError


class ProxyHalfSpace(ProxyShape):
    #: A reference to the shape declaration.
    declaration = ForwardTyped(lambda: HalfSpace)

    def set_surface(self, surface):
        raise NotImplementedError

    def set_side(self, side):
        raise NotImplementedError


class ProxyPrism(ProxyShape):
    #: A reference to the shape declaration.
    declaration = ForwardTyped(lambda: Prism)

    def set_shape(self, surface):
        raise NotImplementedError

    def set_vector(self, vector):
        raise NotImplementedError

    def set_infinite(self, infinite):
        raise NotImplementedError

    def set_canonize(self, canonize):
        raise NotImplementedError


class ProxySphere(ProxyShape):
    #: A reference to the shape declaration.
    declaration = ForwardTyped(lambda: Sphere)

    def set_radius(self, r):
        raise NotImplementedError

    def set_angle(self, a):
        raise NotImplementedError

    def set_angle2(self, a):
        raise NotImplementedError

    def set_angle3(self, a):
        raise NotImplementedError


class ProxyTorus(ProxyShape):
    #: A reference to the shape declaration.
    declaration = ForwardTyped(lambda: Torus)

    def set_radius(self, r):
        raise NotImplementedError

    def set_radius2(self, r):
        raise NotImplementedError

    def set_angle(self, a):
        raise NotImplementedError

    def set_angle2(self, a):
        raise NotImplementedError

    def set_angle3(self, a):
        raise NotImplementedError


class ProxyWedge(ProxyShape):
    #: A reference to the shape declaration.
    declaration = ForwardTyped(lambda: Wedge)

    def set_dx(self, dx):
        raise NotImplementedError

    def set_dy(self, dy):
        raise NotImplementedError

    def set_dz(self, dz):
        raise NotImplementedError

    def set_itx(self, itx):
        raise NotImplementedError


class ProxyRevol(ProxyShape):
    #: A reference to the shape declaration.
    declaration = ForwardTyped(lambda: Revol)

    def set_shape(self, shape):
        raise NotImplementedError

    def set_angle(self, angle):
        raise NotImplementedError


class ProxyRawShape(ProxyShape):
    #: A reference to the shape declaration.
    declaration = ForwardTyped(lambda: RawShape)

    def get_shape(self):
        raise NotImplementedError


class ProxyLoadShape(ProxyShape):
    #: A reference to the shape declaration.
    declaration = ForwardTyped(lambda: LoadShape)

    def set_path(self, path):
        raise NotImplementedError

    def set_loader(self, loader):
        raise NotImplementedError


class Point(Atom):
    proxy = Typed(gp_Pnt)

    x = Float(0, strict=False)
    y = Float(0, strict=False)
    z = Float(0, strict=False)

    def __init__(self, x=0, y=0, z=0, **kwargs):
        if isinstance(x, TopoDS_Shape):
            pnt = BRep_Tool.Pnt_(x)
            x, y, z = pnt.X(), pnt.Y(), pnt.Z()
        elif isinstance(x, gp_Pnt):
            x, y, z = pnt.X(), pnt.Y(), pnt.Z()
        super().__init__(x=x, y=y, z=z, **kwargs)

    def _default_proxy(self):
        return gp_Pnt(self.x, self.y, self.z)

    # ========================================================================
    # Binds changes to the proxy
    # ========================================================================
    def _observe_x(self, change):
        if change['type'] == 'update':
            self.proxy.SetX(self.x)

    def _observe_y(self, change):
        if change['type'] == 'update':
            self.proxy.SetY(self.y)

    def _observe_z(self, change):
        if change['type'] == 'update':
            self.proxy.SetZ(self.z)

    # ========================================================================
    # Slice support
    # ========================================================================
    def __getitem__(self, key):
        return (self.x, self.y, self.z).__getitem__(key)

    def __setitem__(self, key, value):
        p = [self.x, self.y, self.z]
        p[key] = value
        self.x, self.y, self.z = p

    # ========================================================================
    # Operations support
    # ========================================================================
    def __add__(self, other):
        p = self.__coerce__(other)
        return self.__class__(self.x + p.x, self.y + p.y, self.z + p.z)

    def __sub__(self, other):
        p = self.__coerce__(other)
        return self.__class__(self.x - p.x, self.y - p.y, self.z - p.z)

    def __eq__(self, other):
        p = self.__coerce__(other)
        return self.proxy.IsEqual(p.proxy, 1e-6)

    def __mul__(self, other):
        return self.__class__(self.x * other, self.y * other, self.z * other)

    def __truediv__(self, other):
        return self.__class__(self.x / other, self.y / other, self.z / other)

    def cross(self, other):
        p = self.__coerce__(other)
        return self.__coerce__(self.proxy.Crossed(p.proxy))

    def dot(self, other):
        p = self.__coerce__(other)
        return self.proxy.Dot(p.proxy)

    def midpoint(self, other):
        p = self.__coerce__(other)
        return self.__class__(
            (self.x + p.x) / 2, (self.y + p.y) / 2, (self.z + p.z) / 2)

    def distance(self, other):
        p = self.__coerce__(other)
        return self.proxy.Distance(p.proxy)

    def distance2d(self, other):
        p = self.__coerce__(other)
        return math.sqrt((self.x-p.x)**2 + (self.y-p.y)**2)

    def replace(self, **kwargs):
        """ Create a copy with the value replaced with the given parameters.

        """
        p = Point(*self[:])
        for k, v in kwargs:
            setattr(k, v)
        return p

    def __hash__(self):
        return hash(self[:])

    @classmethod
    def __coerce__(self, other):
        return coerce_point(other)

    def __repr__(self):
        return "<Point: x=%s y=%s z=%s>" % self[:]


class Direction(Point):
    proxy = Typed(gp_Dir)

    def _default_proxy(self):
        return gp_Dir(self.x, self.y, self.z)

    @classmethod
    def __coerce__(self, other):
        return coerce_direction(other)

    def __repr__(self):
        return "<Direction: x=%s y=%s z=%s>" % self[:]

    def reversed(self):
        """ Return a reversed copy """
        v = self.proxy.Reversed()
        return Direction(v.X(), v.Y(), v.Z())

    @classmethod
    def XY(cls, x, y):
        # Create a direction in the 2d XY plane with Z normal
        v = gp.DZ_().Rotated(gp.OZ_(), math.atan2(y, x))
        return Direction(v.X(), v.Y(), v.Z())

    @classmethod
    def XZ(cls, x, y):
        # Create a direction in the XY plane
        v = gp_Dir()
        v.Rotate(gp.OY_(), math.atan2(y, x))
        return Direction(v.X(), v.Y(), v.Z())

    @classmethod
    def YZ(cls, x, y):
        # Create a direction in the XY plane
        v = gp_Dir()
        v.Rotate(gp.OX_(), math.atan2(y, x))
        return Direction(v.X(), v.Y(), v.Z())

    def angle(self, other):
        p = self.__coerce__(other)
        return self.proxy.Angle(p.proxy)

    def is_parallel(self, other, tol=1e-6):
        p = self.__coerce__(other)
        return self.proxy.IsParallel(p.proxy, tol)

    def is_opposite(self, other, tol=1e-6):
        p = self.__coerce__(other)
        return self.proxy.IsOpposite(p.proxy, tol)

    def is_normal(self, other, tol=1e-6):
        """ Check if perpendicular """
        p = self.__coerce__(other)
        return self.proxy.IsNormal(p.proxy, tol)


def coerce_point(arg):
    if isinstance(arg, TopoDS_Shape):
        arg = BRep_Tool.Pnt_(arg)
    if hasattr(arg, 'XYZ'): # copy from gp_Pnt, gp_Vec, gp_Dir, etc..
        return Point(arg.X(), arg.Y(), arg.Z())
    if isinstance(arg, Point):
        return arg
    if isinstance(arg, dict):
        return Point(**arg)
    return Point(*arg)


def coerce_direction(arg):
    if isinstance(arg, TopoDS_Shape):
        arg = BRep_Tool.Pnt_(arg)
    if hasattr(arg, 'XYZ'): # copy from gp_Pnt2d, gp_Vec2d, gp_Dir2d, etc..
        return Direction(arg.X(), arg.Y(), arg.Z())
    if isinstance(arg, Direction):
        return arg
    if isinstance(arg, dict):
        return Direction(**arg)
    return Direction(*arg)


def coerce_rotation(arg):
    if isinstance(arg, (int, float)):
        return float(arg)
    return float(math.atan2(*arg))


class TextureParameters(Atom):
    """ Texture parametric parameter ranges
    """
    enabled = Bool(True)
    u = Float(0.0, strict=False)
    v = Float(0.0, strict=False)


def coerce_texture(arg):
    if isinstance(arg, dict):
        return TextureParameters(**arg)
    enabled = arg[2] if len(arg) > 2 else True
    return TextureParameters(u=arg[0], v=arg[1], enabled=enabled)


class Texture(Atom):

    #: Path to the texture file or image
    path = Str()

    #: If given, repeat in the u and v dimension
    repeat = Coerced(TextureParameters,
                     kwargs={'enabled': True, 'u': 1, 'v': 1},
                     coercer=coerce_texture)

    #: If given, adjust th eorigin to the u and v dimension
    origin = Coerced(TextureParameters,
                     kwargs={'enabled': True, 'u': 0, 'v': 0},
                     coercer=coerce_texture)

    #: If given, scale in the u and v dimension
    scale = Coerced(TextureParameters,
                    kwargs={'enabled': True, 'u': 1, 'v': 1},
                    coercer=coerce_texture)


class Material(Atom):
    #: Name
    name = Str()

    def __init__(self, name="", **kwargs):
        """ Constructor which accepts a material name

        """
        super().__init__(name=name, **kwargs)

    transparency = FloatRange(0.0, 1.0, 0.0)
    shininess = FloatRange(0.0, 1.0, 0.5)
    refraction_index = FloatRange(1.0, value=1.0)

    #: Color
    color = ColorMember()
    ambient_color = ColorMember()
    diffuse_color = ColorMember()
    specular_color = ColorMember()
    emissive_color = ColorMember()


class Shape(ToolkitObject):
    """ Abstract shape component that can be displayed on the screen
    and represented by the framework.

    Notes
    ------

    This shape's proxy holds an internal reference to the underlying shape
    which can be accessed using `self.proxy.shape` if needed. The topology
    of the shape can be accessed using the `self.proxy.topology` attribute.

    """
    #: Reference to the implementation control
    proxy = Typed(ProxyShape)

    #: Whether the shape should be displayed and exported when in a part
    #: If set to false this shape will be excluded from the rendered part
    display = d_(Bool(True))

    #: Description to display in the tooltip when clicked
    description = d_(Str())

    #: The tolerance to use for operations that may require it.
    tolerance = d_(Float(10**-6, strict=False))

    #: Material
    material = d_(Coerced(Material))

    #: A string representing the color of the shape.
    color = d_(ColorMember())

    #: The opacity of the shape used for display.
    transparency = d_(FloatRange(0.0, 1.0, 0.0))

    #: Texture to apply to the shape
    texture = d_(Instance(Texture))

    #: Position alias
    def _get_x(self):
        return self.position.x

    def _set_x(self, v):
        self.position.x = v

    x = d_(Property(_get_x, _set_x))

    def _get_y(self):
        return self.position.y

    def _set_y(self, v):
        self.position.y = v

    y = d_(Property(_get_y, _set_y))

    def _get_z(self):
        return self.position.z

    def _set_z(self, v):
        self.position.z = v

    z = d_(Property(_get_z, _set_z))

    #: A tuple or list of the (x, y, z) position of this shape. This is
    #: coerced into a Point.
    position = d_(Coerced(Point, coercer=coerce_point))

    def _default_position(self):
        return Point(0, 0, 0)

    #: A tuple or list of the (u, v, w) normal vector of this shape. This is
    #: coerced into a Vector setting the orentation of the shape.
    #: This is effectively the working plane.
    direction = d_(Coerced(Direction, coercer=coerce_direction))

    def _default_direction(self):
        return Direction(0, 0, 1)

    #: Rotation about the normal vector in radians
    rotation = d_(Coerced(float, coercer=coerce_rotation))

    def _get_axis(self):
        return (self.position, self.direction, self.rotation)

    def _set_axis(self, axis):
        self.position, self.direction, self.rotation = axis

    #: A tuple or list of the (u, v, w) axis of this shape. This is
    #: coerced into a Vector that defines the x, y, and z orientation of
    #: this shape.
    axis = d_(Property(_get_axis, _set_axis))

    def _get_topology(self):
        return self.proxy.topology

    #: A read only property that accesses the topology of the shape such
    #: as edges, faces, shells, solids, etc....
    topology = Property(_get_topology, cached=True)

    def _get_bounding_box(self):
        if self.proxy.shape:
            try:
                return self.proxy.get_bounding_box()
            except:
                pass

    #: Bounding box of this shape
    bbox = Property(_get_bounding_box, cached=True)

    @observe('color', 'transparency', 'display', 'texture')
    def _update_proxy(self, change):
        super(Shape, self)._update_proxy(change)

    @observe('proxy.shape')
    def _update_properties(self, change):
        """ Clear the cached references when the shape changes. """
        for k in ('bbox', 'topology'):
            self.get_member(k).reset(self)
        self.constructed()

    #: Triggered when the shape is constructed
    constructed = d_(Event(), writable=False)

    def activate_proxy(self):
        """ Activate the proxy object tree.

        This method should be called by a node to activate the proxy
        tree by making two initialization passes over the tree, from
        this node downward. This method is automatically at the proper
        times and should not normally need to be invoked by user code.

        """
        self.activate_top_down()
        for child in self.children:
            # Make sure each is initialized upon activation
            if not child.is_initialized:
                child.initialize()
            if isinstance(child, ToolkitObject):
                child.activate_proxy()
        self.activate_bottom_up()
        self.proxy_is_active = True
        self.activated()

    def render(self):
        """ Generates and returns the actual shape from the declaration.
        Enaml does this automatically when it's included in the viewer so this
        is only neede when working with shapes manually.

        Returns
        -------
        shape: TopoDS_Shape
            The shape generated by this declaration.

        """
        if not self.is_initialized:
            self.initialize()
        if not self.proxy_is_active:
            self.activate_proxy()
        return self.proxy.shape


class Face(Shape):
    """ A Face turns it's first child Wire into a surface.

    Examples
    --------

    Add a Wire as a child
        Face:
            Wire:
                # etc..

    """

    #: Reference to the implementation control
    proxy = Typed(ProxyFace)

    #: List of wires to use
    wires = d_(List())


class Box(Shape):
    """ A primitive Box shape.

    Attributes
    ----------

    dx: Float
        Size or width of the box along the x-axis
    dy: Float
        Size or height of the box along the y-axis
    dz: Float
        Size or depth of the box along the z-axis

    Examples
    --------

    Box:
        dx = 3
        dy = 10
        # dx, dy, and dz are all 1 by default if omitted

    """
    #: Proxy shape
    proxy = Typed(ProxyBox)

    #: x size
    dx = d_(Float(1, strict=False)).tag(view=True)

    #: y size
    dy = d_(Float(1, strict=False)).tag(view=True)

    #: z size
    dz = d_(Float(1, strict=False)).tag(view=True)

    # TODO: Handle other constructors

    @observe('dx', 'dy', 'dz')
    def _update_proxy(self, change):
        super(Box, self)._update_proxy(change)


class Cone(Shape):
    """ A primitive Cone shape.

    Attributes
    ----------

    height: Float
        Height of the cone
    radius: Float
        Radius of the base of the cone
    radius2: Float
        Second radius of the base of the cone (to make it oval)
    angle:
        The angle to revolve (in radians) the base profile

    Examples
    --------

    Cone:
        height = 10
        radius = 5
        angle = math.pi/2

    """
    #: Proxy shape
    proxy = Typed(ProxyCone)

    #: Radius
    radius = d_(Float(1, strict=False)).tag(view=True)

    #: Radius 2 size
    radius2 = d_(Float(0, strict=False)).tag(view=True)

    #: Height
    height = d_(Float(1, strict=False)).tag(view=True)

    #: Angle
    angle = d_(Float(0, strict=False)).tag(view=True)

    @observe('radius', 'radius2', 'height', 'angle')
    def _update_proxy(self, change):
        super(Cone, self)._update_proxy(change)


class Cylinder(Shape):
    """ A primitive Cylinder shape.

    Attributes
    ----------

    height: Float
        Height of the cylinder
    radius: Float
        Radius of the base of the cylinder
    angle:
        The angle to revolve (in radians) the base profile.

    Examples
    --------

    Cone:
        height = 10
        radius = 5

    """
    #: Proxy shape
    proxy = Typed(ProxyCylinder)

    #: Radius
    radius = d_(Float(1, strict=False)).tag(view=True)

    #: Height
    height = d_(Float(1, strict=False)).tag(view=True)

    #: Angle
    angle = d_(Float(0, strict=False)).tag(view=True)

    @observe('radius', 'height', 'angle')
    def _update_proxy(self, change):
        super(Cylinder, self)._update_proxy(change)


class HalfSpace(Shape):
    """ An infinite solid limited by a surface.

    Attributes
    ----------

    surface: Face or Shell
        Surface to divide
    side: Point
        A point on the side of the surface where the half space should be

    Notes
    -----

     A half-space is an infinite solid, limited by a surface. It is built from
     a face or a shell, which bounds it, and with a reference point, which
     specifies the side of the surface where the matter of the half-space is
     located. A half-space is a tool commonly used in topological operations
     to cut another shape

    Examples
    --------

    HalfSpace:
        # Plane at orgiin in z direction
        position = (0, 0, 0)
        direction = (0, 0, 1)
        side = (0, 0, -1) # Negative z side


    """
    #: Proxy shape
    proxy = Typed(ProxyHalfSpace)

    #: Surface that is either a face or a Shell
    surface = d_(Instance((TopoDS_Face, TopoDS_Shell)))

    #: Side of surface where the space is located
    side = d_(Coerced(Point, coercer=coerce_point))

    @observe('surface', 'side')
    def _update_proxy(self, change):
        super(HalfSpace, self)._update_proxy(change)


class Prism(Shape):
    """ A Prism extrudes a Face into a solid or a Wire into a surface along
    the given vector.

    Attributes
    ----------

    shape: Shape to extrude or None
        Reference to the shape to extrude.
    vector: Tuple of (x, y, z)
        The extrusion vector.
    infinite: Bool
        Whether to extrude an infinte distance along the given vector.
    canonize: Bool
        Attempt to canonize in simple shapes

    Notes
    -----

    The first child node will be used as the shape if none is given.


    Examples
    --------

    Prism:
        Wire:
            Polyline:
                points = [(0,5,0), (2,6,0),  (5,4,0), (0,5,0)]

    """

    #: Proxy shape
    proxy = Typed(ProxyPrism)

    #: Shape to build prism from
    shape = d_(Instance(Shape)).tag(view=True)

    #: Vector to build prism from, ignored if infinite is true
    vector = d_(Tuple((float, int), default=(0, 0, 1))).tag(view=True)

    #: Infinite
    infinite = d_(Bool(False)).tag(view=True)

    #: Attempt to canonize
    canonize = d_(Bool(True)).tag(view=True)

    @observe('shape', 'vector', 'infinite', 'canonize')
    def _update_proxy(self, change):
        super(Prism, self)._update_proxy(change)


class Sphere(Shape):
    """ A primitive Sphere shape.

    Attributes
    ----------

    radius: Float
        Radius of the sphere
    angle: Float
        The u-angle to revolve (in radians) along the base profile from 0 to 2pi.
    angle2: Float
        The v-min angle to start from (in radians) from -pi/2 to pi/2
    angle3: Float
        The v-max angle to start from (in radians) from -pi/2 to pi/2


    Notes
    --------

    Make a sphere of radius R. For all algorithms The resulting shape is
    composed of:

    - a lateral spherical face
    - Two planar faces parallel to the plane z = 0 if the sphere is truncated
      in the v parametric direction, or only one planar face if angle1 is
      equal to -p/2 or if angle2 is equal to p/2 (these faces are circles in
      case of a complete truncated sphere),
    - and in case of a portion of sphere, two planar faces to shut the shape.
      (in the planes u = 0 and u = angle).


    Examples
    --------

    Sphere:
        radius = 3

    Sphere:
        angle = math.pi/2

    """
    #: Proxy shape
    proxy = Typed(ProxySphere)

    #: Radius of sphere
    radius = d_(Float(1, strict=False)).tag(view=True)

    #: Angle of U (fraction of circle)
    angle = d_(FloatRange(low=0.0, high=2*pi, value=2*pi)).tag(view=True)

    #: Min Angle of V (fraction of circle in normal direction)
    angle2 = d_(FloatRange(low=-pi/2, high=pi/2, value=-pi/2)).tag(view=True)

    #: Max Angle of V (fraction of circle in normal direction)
    angle3 = d_(FloatRange(low=-pi/2, high=pi/2, value=pi/2)).tag(view=True)

    @observe('radius', 'angle', 'angle2', 'angle3')
    def _update_proxy(self, change):
        super(Sphere, self)._update_proxy(change)


class Torus(Shape):
    """ A primitive Torus shape (a ring like shape).

    Attributes
    ----------

    radius: Float
        Radius of the torus
    radius2: Float
        Radius of the torus profile
    angle:  Float
        The angle to revolve the torus (in radians) from 0 to 2 pi.
    angle2: Float
        The angle to revolve the torus profile (in radians) from -pi/2 to pi/2.

    Examples
    --------

    Torus:
        radius = 5

    """
    #: Proxy shape
    proxy = Typed(ProxyTorus)

    #: Radius of sphere
    radius = d_(Float(1, strict=False)).tag(view=True)

    #: Radius 2
    radius2 = d_(Float(0, strict=False)).tag(view=True)

    #: Angle of U (fraction of circle)
    angle = d_(FloatRange(low=0.0, high=2*pi, value=2*pi)).tag(view=True)

    #: Start Angle of V (fraction of circle in normal direction)
    angle2 = d_(Float(0, strict=False)).tag(view=True)

    #: Stop Angle of V (fraction of circle in normal direction)
    angle3 = d_(Float(0, strict=False)).tag(view=True)

    @observe('radius', 'radius2', 'angle', 'angle2', 'angle3')
    def _update_proxy(self, change):
        super(Torus, self)._update_proxy(change)


class Wedge(Shape):
    """ A primitive Wedge shape.

    Attributes
    ----------

    dx: Float
        Size of the wedge along the x-axis
    dy: Float
        Size of the wedge along the y-axis
    dz:  Float
        Size of the wedge along the z-axis
    ltx: Float
        Size of the base before the wedge starts. Must be >= 0.
        Defaults to 0.

    Examples
    --------

    Wedge:
        dy = 5

    """
    #: Proxy shape
    proxy = Typed(ProxyWedge)

    #: x size
    dx = d_(Float(1, strict=False)).tag(view=True)

    #: y size
    dy = d_(Float(1, strict=False)).tag(view=True)

    #: z size
    dz = d_(Float(1, strict=False)).tag(view=True)

    #: z size
    itx = d_(Float(0, strict=False)).tag(view=True)

    # TODO: Handle other constructors

    @observe('dx', 'dy', 'dz', 'itx')
    def _update_proxy(self, change):
        super(Wedge, self)._update_proxy(change)


class Revol(Shape):
    """ A Revol creates a shape by revolving a profile about an axis.

    Attributes
    ----------

    shape: Shape
        Shape to revolve. If not given, the first child will be used.
    angle: Float
        Angle to revolve (in radians) the base profile.

    Examples
    --------

    # This creates a cone of radius 4 and height 5.

    Revol:
        Wire:
            Polyline:
                points = [(0,0,0), (0,2,5),  (0,5,0), (0,0,0)]

    """
    #: Proxy shape
    proxy = Typed(ProxyRevol)

    #: Shape to build prism from
    shape = d_(Instance(Shape)).tag(view=True)

    #: Angle to revolve
    angle = d_(Float(0, strict=False)).tag(view=True)

    @observe('shape', 'angle')
    def _update_proxy(self, change):
        super(Revol, self)._update_proxy(change)


class RawShape(Shape):
    """ A RawShape is a shape that delegates shape creation to the declaration.
    This allows custom shapes to be added to the 3D model hierarchy. Users
    should subclass this and implement the `create_shape` method.

    Examples
    --------

    from OCC.TopoDS import TopoDS_Shape
    from OCC.StlAPI import StlAPI_Reader

    class StlShape(RawShape):
        #: Loads a shape from an stl file
        def create_shape(self, parent):
            stl_reader = StlAPI_Reader()
            shape = TopoDS_Shape()
            stl_reader.Read(shape, './models/fan.stl')
            return shape


    """
    #: Reference to the implementation control
    proxy = Typed(ProxyRawShape)

    def create_shape(self, parent):
        """ Create the shape for the control.
        This method should create and initialize the shape.

        Parameters
        ----------
        parent : shape or None
            The parent shape for the control.

        Returns
        -------
        result : shape
            The shape for the control.


        """
        raise NotImplementedError

    def get_shape(self):
        """ Retrieve the shape for display.

        Returns
        -------
        shape : shape or None
            The toolkit shape that was previously created by the
            call to 'create_shape' or None if the proxy is not
            active or the shape has been destroyed.
        """
        if self.proxy_is_active:
            return self.proxy.get_shape()


class TopoShape(RawShape):
    """ A declaration for inserting an existing TopoDS_Shape somewhere into a
    DeclaraCAD tree.

    """
    shape = d_(Instance(TopoDS_Shape))

    def create_shape(self, parent):
        return self.shape

    def get_shape(self):
        return self.shape

