import pytest
import faulthandler
faulthandler.enable()

from declaracad import occ
occ.install()

import enaml
from enaml.qt.qt_application import QtApplication

@pytest.yield_fixture(scope='session')
def qt_app():
    """Make sure a QtApplication is active.
    """
    app = QtApplication.instance()
    if app is None:
        app = QtApplication()
        yield app
        app.stop()
    else:
        yield app
