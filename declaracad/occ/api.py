"""
Copyright (c) 2017-2019, Jairus Martin.

Distributed under the terms of the GPL v3 License.

The full license is in the file LICENSE, distributed with this software.

Created on Dec 13, 2017

@author: jrm
"""
from .algo import (
    Cut, Common, Fuse, Split, Intersection,
    Fillet, Chamfer,
    Offset, OffsetShape,
    ThickSolid,
    Pipe,
    LinearForm, RevolutionForm,
    ThruSections,
    Transform, Translate, Rotate, Scale, Mirror
)

Loft = ThruSections
Sweep = Pipe

from .dimension import (
    AngleDimension, DiameterDimension, LengthDimension, RadiusDimension
)

from .draw import (
    Plane, Vertex, Edge, Line, Rectangle,
    Segment, Arc, Circle, Ellipse, Hyperbola,
    Parabola, Polyline, Polygon,
    BSpline, Bezier,
    Text, TrimmedCurve, Svg,
    Wire
)

from .part import Part, RawPart, LoadPart

from .shape import (
    Point, Direction, Shape, RawShape, LoadShape, Face, Texture, Material,
    Box, Cylinder, Sphere, Cone, Wedge, Torus,
    HalfSpace, Prism, Revol
)

Extrude = Prism


from enaml.core.api import Looper, Conditional, Include
