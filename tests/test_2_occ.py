import pytest
from textwrap import dedent

from OCCT.TopoDS import TopoDS_Shape

from declaracad.occ.plugin import load_model

TEMPLATE = """
import math
from declaracad.occ.api import *

enamldef Assembly(Part):
%s

"""

TESTS = {
'box1': """
     Box:
         position = (10, 2, 30)
     """,

'cone1': """
     Cone:
         radius = 1
         height = 5
     """,

'cylinder1': """
     Cylinder:
         radius = 2
     """,

'cylinder2': """
    Cylinder:
        angle = 30*math.pi
    """,

'sphere': """
    Sphere:
        radius = 2
    """,

'sphere-2': """
    Sphere:
        angle = math.pi/4
    """,
'sphere-3': """
    Sphere:
        angle = math.pi/4
        angle2 = math.pi/4
    """,
'sphere-4': """
    Sphere:
        angle = math.pi/4
        angle2 = math.pi/4
        angle3 = math.pi/4
    """,

'wedge': """
    Wedge:
        dy = 2
    """,

'torus': """
    Torus:
        radius = 2
        radius2 = 0.4
    """,
'torus-2': """
    Torus:
        radius = 5
        radius2 = 1
        angle = math.pi
    """,
'torus-3': """
    Torus:
        radius = 5
        radius2 = 1
        angle = math.pi
        angle2 = math.pi/4
    """,
'prism': """
    Prism:
        Wire:
            Polyline:
                points = [(0,5,0), (2,6,0),  (5,4,0), (0,5,0)]
    """,
'revol': """
    Revol:
        Wire:
            Polyline:
                points = [(0,0,0), (0,2,5),  (0,5,0), (0,0,0)]
    """,
'circle': """
    Wire:
        Circle:
            radius = 10
    """,
'ellipse': """
    Wire:
        Ellipse:
            major_radius = 3
            minor_radius = 2
    """,
'polygon': """
    Wire:
        Polyline:
            points = [(0,0,0), (0,2,5),  (0,5,0), (0,0,0)]
    """,
'bezier': """
    Wire:
        color = 'blue'
        Bezier: b1:
            points = [ (1,5,2),  (2,6,1),  (3,4,5)]
    """,
'bspline': """
    Wire:
        color = 'green'
        BSpline: bspline:
            attr r = 3
            points = [
                (r*math.sin(math.pi/2*i),r*math.cos(math.pi/2*i), i/4)
                for i in range(21)
            ]

    """,
'cut': """
    Cut:
        Box:
            pass
        Box:
            position = (0.5, 0.5, 0)
    """
}

@pytest.mark.parametrize('name', TESTS.keys())
def test_shapes_compile(qt_app, name):
    assembly = load_model("test", TEMPLATE % TESTS[name])
    assert assembly

@pytest.mark.parametrize('name', TESTS.keys())
def test_shapes_render(qt_app, name):
    assembly = load_model("test", TEMPLATE % TESTS[name])[0]
    assert isinstance(assembly.render(), TopoDS_Shape)







