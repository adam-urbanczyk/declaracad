"""
Copyright (c) 2018-2019, Jairus Martin.

Distributed under the terms of the GPL v3 License.

The full license is in the file LICENSE, distributed with this software.

Created on July 28, 2018

@author: jrm
"""
import os
import sys
import json
import enaml
import traceback
import faulthandler
faulthandler.enable()


from atom.api import Instance, Bool, Dict, Float
from enaml.application import timed_call, deferred_call

from declaracad import occ
occ.install()
from declaracad.core.app import Application
from declaracad.core.utils import JSONRRCProtocol
from declaracad.core.stdio import create_stdio_connection

with enaml.imports():
    from declaracad.occ.view import ViewerWindow


class ViewerProtocol(JSONRRCProtocol):
    """ Use stdio as a json-rpc interface to communicate with external
    processes.

    If --frameless is used, the interface must receive a ping at least every
    60 sec or it will assume it's owner has left and will exit.

    """
    view = Instance(ViewerWindow)
    watch = Bool()
    _watched_files = Dict()
    _exit_in_sec = Float(60, strict=False)

    def connection_made(self, transport):
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
        """ The JSONRRCProtocol tries to invoke 'handle_<attr>' on this class
        to handle JSON-RPC requests. This is invoked if such a method doesn't
        exist and attempts to redirect the getattr to the window or viewer.

        """
        if not name.startswith('handle_'):
            raise AttributeError(name)
        attr = name[7:]  # Strip handle_

        # Lookup matching methods on the window and viewer
        for target in (self.view, self.view.viewer):
            handler = getattr(target, attr, None)
            if handler is not None and callable(handler):
                return handler

        # Replace any set_<attr> with a setattr
        if attr.startswith('set_'):
            attr = attr[len('set_'):]
            for target in (self.view, self.view.viewer):
                handler = getattr(target, attr, None)
                if handler is not None and not callable(handler):
                    def handler(v, target=target, attr=attr):
                        setattr(target, attr, v)
                    return handler
        raise AttributeError(name)

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

    def check_for_changes(self):
        """ A simple poll loop to check if the file changed and if it has
        reload it by bumping the version.

        """
        if self.watch:
            timed_call(1000, self.check_for_changes)

        try:
            filename = self.view.filename
            if os.path.exists(filename):
                try:
                    mtime = os.stat(filename).st_mtime
                except:
                    return

                if filename not in self._watched_files:
                    self._watched_files[filename] = mtime
                elif self._watched_files[filename] != mtime:
                    self._watched_files[filename] = mtime
                    print("%s changed, reloading" % filename)
                    deferred_call(self.handle_version, self.view.version + 1)
        except Exception as e:
            print(traceback.format_exc())


def main(**kwargs):
    app = Application()

    filename = kwargs.get('file', '-')
    frameless = kwargs.get('frameless', False)
    watch = kwargs.get('watch', False)

    if not frameless and not os.path.exists(filename):
        raise ValueError("File %s does not exist!" % filename)

    view = ViewerWindow(filename='-', frameless=frameless)
    view.protocol = ViewerProtocol(view=view, watch=watch)
    if watch:
        timed_call(1000, view.protocol.check_for_changes)
    view.show()
    app.deferred_call(create_stdio_connection, app.loop, view.protocol)
    app.deferred_call(view.protocol.handle_filename, filename)
    app.start()


if __name__ == '__main__':
    main()
