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
from enaml.application import timed_call
with enaml.imports():
    from declaracad.occ.view import ViewerWindow

from twisted.internet.stdio import StandardIO


class ViewerProtocol(JSONRRCProtocol):
    """ Use stdio as a json-rpc interface to communicate with external
    processes.
    
    """
    def __init__(self, view):
        self.view = view
        self._exit_in_sec = 60
        super(ViewerProtocol).__init__()
        
    def connectionMade(self):
        self.send_message({'result': self.handle_window_id(),
                           'id': 'window_id'})
        if self.view.frameless:
            self.schedule_close()
        
    def handle_window_id(self):
        return int(self.view.proxy.widget.winId())
        
    def handle_filename(self, filename):
        self.view.filename = filename
    
    def handle_version(self, version):
        self.view.version = version
        
    def handle_ping(self):
        self._exit_in_sec = 60
        return True
        
    def __getattr__(self, name):
        """ Attempt to call handlers on the viewer directly if they exist.
        
        It will attempt to lookup a function of the Window object, if that
        fails it will lookup the attr or function on the Viewer object. If
        the attr on the viewer is not callable a handler will be created to
        set the value.
        
        """
        if name.startswith("handle_"):
            attr = name.lstrip("handle_")
            handler = getattr(self.view, attr, None)
            if handler is not None:
                return handler
            handler = getattr(self.view.viewer, attr)
            if callable(handler):
                return handler
            return lambda v: setattr(self.view.viewer, attr, v)
            
        
    def schedule_close(self):
        """ A watchdog so if the parent is killed the viewer will automatically
        exit. Otherwise it will hang around forever.
        """
        if self._exit_in_sec <= 0:
            # Timeout
            print("WARNING: Ping timeout expired, closing")
            sys.exit(1)
        else:
            timed_call(self._exit_in_sec*1000, self.schedule_close)
            self._exit_in_sec = 0  # Clear timeout
    

def main(**kwargs):
    app = QtApplication()
    qt5reactor.install()
    view = ViewerWindow(filename=kwargs.get('file', '-'),
                        frameless=kwargs.get('frameless', False))
    view.protocol = ViewerProtocol(view)
    view.show()
    app.deferred_call(lambda: StandardIO(view.protocol))
    app.start()
    
    
if __name__ == '__main__':
    main()
