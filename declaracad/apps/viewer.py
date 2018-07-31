"""
Copyright (c) 2018, Jairus Martin.

Distributed under the terms of the GPL v3 License.

The full license is in the file LICENSE, distributed with this software.

Created on July 28, 2018

@author: jrm
"""
import sys
import json
import traceback
import qt5reactor

import faulthandler
faulthandler.enable()

from declaracad import occ
occ.install()
from declaracad.core.utils import JSONRRCProtocol

import enaml
from enaml.qt.qt_application import QtApplication 
with enaml.imports():
    from declaracad.occ.view import ViewerWindow

from twisted.internet.stdio import StandardIO
from twisted.protocols.basic import LineReceiver


class ViewerProtocol(JSONRRCProtocol):
    """ Use stdio as a json-rpc interface to communicate with external
    processes.
    
    """
    def __init__(self, view):
        self.view = view
        super(ViewerProtocol).__init__()
        
    def connectionMade(self):
        self.send_message({'result': self.handle_window_id(), 
                           'id': 'window_id'})
        
    def handle_window_id(self):
        return int(self.view.proxy.widget.winId())
        
    def handle_filename(self, filename):
        self.view.filename = filename
    
    def handle_version(self, version):
        self.view.version = version
    

def main(**kwargs):
    app = QtApplication()
    qt5reactor.install()
    view = ViewerWindow(filename=kwargs.get('view', '-'),
                        frameless=kwargs.get('frameless', False))
    view.protocol = ViewerProtocol(view)
    view.show()
    app.deferred_call(lambda: StandardIO(view.protocol))
    app.start()
    
    
if __name__ == '__main__':
    main()
