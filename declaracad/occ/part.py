"""
Copyright (c) 2016-2018, Jairus Martin.

Distributed under the terms of the GPL v3 License.

The full license is in the file LICENSE, distributed with this software.

Created on Sept 28, 2016

@author: jrm
"""
import enaml
from atom.api import Typed, ForwardTyped, Str, Enum, observe
from enaml.core.declarative import d_

from .shape import Shape, ProxyShape


class ProxyPart(ProxyShape):
    #: A reference to the Shape declaration.
    declaration = ForwardTyped(lambda: Part)


class ProxyRawPart(ProxyPart):
    #: A reference to the shape declaration.
    declaration = ForwardTyped(lambda: RawPart)

    def get_shapes(self):
        raise NotImplementedError


class ProxyLoadPart(ProxyPart):
    #: A reference to the shape declaration.
    declaration = ForwardTyped(lambda: LoadPart)

    def set_path(self, path):
        raise NotImplementedError

    def set_loader(self, loader):
        raise NotImplementedError


class Part(Shape):
    """ A Part is a compound shape. It may contain
    any number of nested parts and is typically subclassed.

    Attributes
    ----------

    name: String
        An optional name for the part
    description: String
        An optional description for the part

    Examples
    --------

    enamldef Case(Part):
        TopCover:
            # etc..
        BottomCover:
            # etc..

    """
    #: Reference to the implementation control
    proxy = Typed(ProxyPart)

    #: Optional name of the part
    name = d_(Str())

    #: Optional description of the part
    description = d_(Str())

    #: Static cache
    cache = {}

    @property
    def shapes(self):
        return [child for child in self.children if isinstance(child, Shape)]


class RawPart(Shape):
    """ A RawPart is a part that delegates creation to the declaration.
    This allows custom shapes to be added to the 3D model hierarchy. Users
    should subclass this and implement the `create_shapes` method.

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
    proxy = Typed(ProxyRawPart)

    def create_shapes(self, parent):
        """ Create the shape for the control.
        This method should create and initialize the shape.

        Parameters
        ----------
        parent : shape or None
            The parent shape for the control.

        Returns
        -------
        result : List[shape]
            The shapes for the control.


        """
        raise NotImplementedError

    def get_shapes(self):
        """ Retrieve the shapes for display.

        Returns
        -------
        shapes : List[shape] or None
            The toolkit shape that was previously created by the
            call to 'create_shapes' or None if the proxy is not
            active or the shape has been destroyed.
        """
        if self.proxy_is_active:
            return self.proxy.get_shapes()


with enaml.imports():
    from .loader import LoadedPart
