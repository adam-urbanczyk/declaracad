"""
Copyright (c) 2016-2018, Jairus Martin.

Distributed under the terms of the GPL v3 License.

The full license is in the file LICENSE, distributed with this software.

Created on Sep 30, 2016

@author: jrm
"""
from atom.api import Typed
from ..part import ProxyPart
from .occ_shape import OccDependentShape, OccShape

from OCCT.TopoDS import TopoDS_Compound
from OCCT.BRep import BRep_Builder


class OccPart(OccDependentShape, ProxyPart):
    #: A reference to the toolkit shape created by the proxy.
    builder = Typed(BRep_Builder)

    #: The compound shape
    shape = Typed(TopoDS_Compound)

    @property
    def shapes(self):
        return [child for child in self.children()
                if isinstance(child, OccShape)]

    def update_shape(self, change=None):
        """ Create the toolkit shape for the proxy object.

        """
        builder = self.builder = BRep_Builder()
        shape = TopoDS_Compound()
        builder.MakeCompound(shape)
        for child in self.shapes:
            if child.shape is None:
                continue
            # Not infinite planes cannot be added to a compound!
            builder.Add(shape, child.shape)
        self.shape = shape
