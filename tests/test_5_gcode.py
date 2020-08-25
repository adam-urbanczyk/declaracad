import os
import pytest
from declaracad.cnc import gcode


@pytest.mark.parametrize('name', os.listdir('examples/gcode'))
def test_gcode(name):
    path = 'examples/gcode/%s' % name
    data = gcode.parse(path)
    assert len(data.commands) > 0

