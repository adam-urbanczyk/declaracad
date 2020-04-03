"""
Copyright (c) 2018, Jairus Martin.

Distributed under the terms of the GPL v3 License.

The full license is in the file LICENSE, distributed with this software.

Created on Aug 4, 2018

@author: jrm
"""
import sys
import time
import jsonpickle
import faulthandler
faulthandler.enable()

from declaracad import occ
occ.install()
import enaml
from enaml.qt.qt_application import QtApplication


def main(**kwargs):
    """ Runs ModelExporter.export() using the passed options.

    Parameters
    ----------
    options: Dict
        A jsonpickle dumped exporter

    """
    options = kwargs.pop('options')
    exporter = jsonpickle.loads(options)
    assert exporter, "Failed to load exporter from: {}".format(options)
    # An Application is required
    app = QtApplication()
    t0 = time.time()
    print("Exporting {e.filename} to {e.path}...".format(e=exporter))
    sys.stdout.flush()
    exporter.export()
    print("Success! Took {} seconds.".format(round(time.time()-t0, 2)))
