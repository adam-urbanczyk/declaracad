import pytest

def test_qt():
    from enaml.qt import QtCore, QtGui


def test_occt():
    import OCCT


def test_declaracad():
    import declaracad
    from declaracad.occ.qt import qt_occ_viewer
    from declaracad.occ.plugin import load_model
    from declaracad.occ import api

from declaracad.occ.impl.occ_factories import OCC_FACTORIES

@pytest.mark.parametrize('name', OCC_FACTORIES.keys())
def test_declaracad_factory(name):
    factory = OCC_FACTORIES[name]
    factory()

