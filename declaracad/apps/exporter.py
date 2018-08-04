"""
Copyright (c) 2018, Jairus Martin.

Distributed under the terms of the GPL v3 License.

The full license is in the file LICENSE, distributed with this software.

Created on Aug 4, 2018

@author: jrm
"""
import json
import faulthandler
faulthandler.enable()

from declaracad import occ
occ.install()
from declaracad.occ.plugin import export_model, ExportOptions
from enaml.qt.qt_application import QtApplication


def main(**kwargs):
    """ Runs export_model using the passed options.
    
    """
    options = kwargs.pop('options')
    
    try:
        options = json.loads(options)
    except:
        options = {'filename': options}
    
    options = ExportOptions(**options)
    
    # An Application is required
    app = QtApplication()
    export_model(options)
