"""
Copyright (c) 2020, Jairus Martin.

Distributed under the terms of the GPL v3 License.

The full license is in the file LICENSE, distributed with this software.

Created on Dec 27, 2020

@author: jrm
"""
from declaracad.occ.api import Topology


def distance(points, start, end, scale=-1):
    """ Set the z-value of the points by interpolating the
    distance from start and end points. If the first two points are equal
    None is returned.

    Parameters
    ----------
    points: List[Point]
        List of 2d points interpolate
    start: Float
        The starting z-value
    end: Float
        The ending z-value
    scale: Float
        Scale to apply to interpolation

    Returns
    -------
    points: List[Point] or None
        The list of interpolated points on the curve

    """
    p0, p1 = points[0:2]
    if p0 == p1:
        None  # Line is vertical

    p0.z = start * scale
    p1.z = end * scale
    dz = (end - start) * scale

    if len(points) != 2:
        # Determine z value
        z = p0.z
        dt = 0  # Distance
        last = points[0]

        # Determine total distance
        for p in points[1:]:
            dt += last.distance2d(p)
            last = p

        # Determine distance at each point to calculate t
        d = 0
        last = points[0]
        for p in points[1:]:
            d += last.distance2d(p)
            t = d/dt
            assert 0 <= t <= 1
            p.z = (z + dz*t)
            last = p
    return points



def build_edge_graph(shapes):
    """ Build a graph of verticies and edges that connect them. This assumes
    that all edges are unique.

    Parameters
    ----------
    shapes: Iterable[TopoDS_Shape]
        Iterable of shapes to build an edge graph from

    Returns
    -------
    graph: Dict
        A mapping of points to set of connected edges

    """
    graph = {}
    for s in shapes:
        for e in Topology(shape=s).edges:
            for p in Topology(shape=e).points:
                r = graph.get(p)
                if r is None:
                    # Lookup using equals instead of hash
                    for node in graph:
                        if node == p:
                            r = graph[node]
                            break
                    if r is None:
                        r = graph[p] = []
                r.append(e)
    return graph

