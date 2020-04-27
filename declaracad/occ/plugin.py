# -*- coding: utf-8 -*-
"""
Copyright (c) 2017, Jairus Martin.

Distributed under the terms of the GPL v3 License.

The full license is in the file LICENSE, distributed with this software.

Created on Dec 13, 2017

@author: jrm
"""
import os
import sys
import json
import time
import enaml
import atexit
import jsonpickle
from types import ModuleType
from atom.api import (
    Atom, ContainerList, Str, Float, Dict, Bool, Int, Instance, Enum,
    ForwardInstance, Constant, observe, set_default
)
from declaracad.core.api import Plugin, Model, log
from declaracad.core.utils import ProcessLineReceiver, Deferred

from enaml.application import timed_call, deferred_call
from enaml.core.parser import parse
from enaml.core.import_hooks import EnamlCompiler
from enaml.colors import ColorMember

from .part import Part


def viewer_factory():
    with enaml.imports():
        from .view import ViewerDockItem
    return ViewerDockItem

def document_type():
    from declaracad.editor.plugin import Document
    return Document


class EmptyFileError(Exception):
    """ This is raised when no source code is given such as when a new file
    is created but unsaved.
    """


def load_model(filename, source=None):
    """ Load a DeclaraCAD model from an enaml file. Ideally this should be
    used in a separate process but it's not required.

    Parameters
    ----------
    filename: String
        Path to the enaml file to load
    source: String
        Source code to parse (optional)

    Returns
    -------
    result: List[occ.shape.Shape]
        A list of shapes that can be passed to the python-occ viewer.

    """

    # Parse the enaml file or load from source code
    if not source and os.path.exists(filename):
        with open(filename, 'r') as f:
            source = f.read()
    if not source:
        raise EmptyFileError(
            f"No source code given or '{filename}' does not exist")

    # Parse and compile the code
    ast = parse(source)
    code = EnamlCompiler.compile(ast, filename)
    module = ModuleType(filename.rsplit('.', 1)[0])
    module.__file__ = filename
    namespace = module.__dict__
    with enaml.imports():
        exec(code, namespace)
    Assembly = namespace['Assembly']
    return [Assembly()]


class ModelExporter(Atom):
    extension = ''
    path = Str()
    filename = Str()

    def _default_path(self):
        ext = self.extension.lower()
        filename = os.path.splitext(self.filename)[0]
        return "{}.{}".format(filename, ext)

    def export(self):
        """ Export a DeclaraCAD model from an enaml file to a 3D model format
        with the given options.

        """
        raise NotImplementedError

    @classmethod
    def get_options_view(cls):
        """ Return the options view used to define the paramters that can be
        used by this exporter.

        """
        raise NotImplementedError


class ScreenshotOptions(Atom):
    #: Path to save
    path = Str()

    #: Document file name
    filename = Str()

    #: Only screenshot this view
    target = Str()

    def _default_path(self):
        return "{}.png".format(os.path.splitext(self.filename)[0])

    def format(self):
        """ Return formatted option values for the exporter app to parse """
        return json.dumps(self.__getstate__())


class ViewerProcess(ProcessLineReceiver):
    #: Window id obtained after starting the process
    window_id = Int()

    #: Process handle
    process = Instance(object)

    #: Reference to the plugin
    plugin = ForwardInstance(lambda: ViewerPlugin)

    #: Document
    document = ForwardInstance(document_type)

    #: Rendering error
    errors = Str()

    #: Process terminated intentionally
    terminated = Bool(False)

    #: Count restarts so we can detect issues with startup s
    restarts = Int()

    #: Max number it will attempt to restart
    max_retries = Int(20)

    #: ID count
    _id = Int()

    #: Holds responses temporarily
    _responses = Dict()

    #: Seconds to ping
    _ping_rate = Int(40)

    #: Capture stderr separately
    err_to_out = set_default(False)

    @observe('document', 'document.version')
    def _update_document(self, change):
        doc = self.document
        if doc is None:
            self.set_filename('-')
        else:
            self.set_filename(doc.name)
            self.set_version(doc.version)

    def send_message(self, method, *args, **kwargs):
        # Defer until it's ready
        if not self.transport or not self.window_id:
            #log.debug('renderer | message not ready deferring')
            timed_call(1000, self.send_message, method, *args, **kwargs)
            return
        _id = kwargs.pop('_id')
        _silent = kwargs.pop('_silent', False)

        request = {'jsonrpc': '2.0', 'method': method, 'params': args or kwargs}
        if _id is not None:
            request['id'] = _id
        if not _silent:
            log.debug(f'renderer | sent | {request}')
        self.transport.write(jsonpickle.dumps(request).encode()+b'\r\n')

    def _default_process(self):
        from twisted.internet import reactor
        exe = sys.executable
        atexit.register(self.terminate)
        return reactor.spawnProcess(self, exe,
                                    args=[exe, 'main.py', 'view', '-', '-f'],
                                    env=os.environ)

    def _default_window_id(self):
        # Spawn the process
        timed_call(0, lambda: self.process)
        return 0

    def restart(self):
        self.window_id = 0
        self.restarts += 1

        # TODO: 100 is probably excessive
        if self.restarts > self.max_retries:
            plugin = self.plugin
            plugin.workbench.message_critical(
                "Viewer failed to start",
                "Could not get the viewer to start after several attempts.")

            raise RuntimeError(
                "renderer | Failed to successfully start renderer aborting!")

        self.process = self._default_process()

    def connectionMade(self):
        super(ViewerProcess, self).connectionMade()
        self.schedule_ping()
        self.terminated = False

    def lineReceived(self, line):
        try:
            line = line.decode()
            response = jsonpickle.loads(line)
            #log.debug(f"viewer | resp | {response}")
        except Exception as e:
            log.debug(f"viewer | out | {line}")
            response = {}

        doc = self.document

        if not isinstance(response, dict):
            log.debug(f"viewer | out | {response}")
            return

        #: Special case for startup
        response_id = response.get('id')
        if response_id == 'window_id':
            self.window_id = response['result']
            self.restarts = 0  # Clear the restart count
            return
        elif response_id == 'keep_alive':
            return
        elif response_id == 'render_error':
            if doc:
                doc.errors.extend(response['error']['message'].split("\n"))
            return
        elif response_id == 'render_success':
            if doc:
                doc.errors = []
            return
        elif response_id == 'capture_output':
            # Script output capture it
            if doc:
                doc.output = response['result'].split("\n")
            return
        elif response_id == 'shape_selection':
            #: TODO: Do something with this?
            if doc:
                doc.output.append(str(response['result']))
            return
        elif response_id is not None:
            # Lookup the deferred object that should be stored for this id
            # when it is called and invoke the callback or errback based on the
            # result
            d = self._responses.get(response_id)
            if d is not None:
                del self._responses[response_id]
                try:
                    error = response.get('error')
                    if error is not None:
                        if doc:
                            doc.errors.extend(error.get('message', '').split("\n"))
                        d.errback(error)
                    else:
                        d.callback(response.get('result'))
                    return
                except Exception as e:
                    log.warning("RPC response not properly handled!")
                    log.exception(e)

            else:
                log.warning("Got unexpected reply")
            # else we got a response from something else, possibly an error?
        if 'error' in response and doc:
            doc.errors.extend(response['error'].get('message', '').split("\n"))
            doc.output.append(line)
        elif 'message' in response and doc:
            doc.output.extend(response['message'].split("\n"))
        elif doc:
            # Append to output
            doc.output.extend(line.split("\n"))

    def errReceived(self, data):
        """ Catch and log error output attempting to decode it

        """
        for line in data.split(b"\n"):
            if not line:
                continue
            if line.startswith(b"QWidget::") or line.startswith(b"QPainter::"):
                continue
            try:
                line = line.decode()
                log.debug(f"render | err | {line}")
                if self.document:
                    self.document.errors.append(line)
            except Exception as e:
                log.debug(f"render | err | {line}")

    def inConnectionLost(self):
        log.warning("renderer | stdio closed (we probably did it)")

    def outConnectionLost(self):
        if not self.terminated:
            # Clear the filename on crash so it works when reset
            #self.document = None
            self.restart()
        log.warning("renderer | stdout closed")

    def errConnectionLost(self):
        log.warning("renderer | stderr closed")

    def processEnded(self, reason):
        super(ViewerProcess, self).processEnded(reason)
        log.warning(f"renderer | process ended: {reason}")

    def terminate(self):
        super(ViewerProcess, self).terminate()
        self.terminated = True

    def schedule_ping(self):
        """ Ping perioidcally so the process stays awake """
        if self.terminated:
            return
        # Ping the viewer to tell it to keep alive
        self.send_message("ping", _id="keep_alive", _silent=True)
        timed_call(self._ping_rate*1000, self.schedule_ping)

    def __getattr__(self, name):
        """ Proxy all calls """
        def remote_viewer_call(*args, **kwargs):
            d = Deferred()
            self._id += 1
            kwargs['_id'] = self._id
            self._responses[self._id] = d
            self.send_message(name, *args, **kwargs)
            return d
        return remote_viewer_call


class ViewerPlugin(Plugin):

    #: Background color
    background_mode = Enum('gradient', 'solid').tag(config=True)
    background_top = ColorMember('lightgrey').tag(config=True)
    background_bottom = ColorMember('grey').tag(config=True)
    trihedron_mode = Str('right-lower').tag(config=True)

    #: Defaults
    shape_color = ColorMember('steelblue').tag(config=True)

    #: Rendering options
    renderer_use_antialiasing = Bool(True).tag(config=True)
    renderer_use_raytracing = Bool(True).tag(config=True)
    renderer_draw_boundaries = Bool(True).tag(config=True)
    renderer_show_shadows = Bool(True).tag(config=True)


    #: Exporters
    exporters = ContainerList()

    def get_viewers(self):
        ViewerDockItem = viewer_factory()
        dock = self.workbench.get_plugin('declaracad.ui').get_dock_area()
        for item in dock.dock_items():
            if isinstance(item, ViewerDockItem):
                yield item

    def fit_all(self, event=None):
        return
        viewer = self.get_viewer()
        viewer.proxy.display.FitAll()

    def run(self, event=None):
        viewer = self.get_viewer()
        editor = self.workbench.get_plugin('declaracad.editor').get_editor()
        doc = editor.doc
        viewer.renderer.set_source(editor.get_text())
        doc.version += 1

    def get_viewer(self, name=None):
        for viewer in self.get_viewers():
            if name is None:
                return viewer
            elif viewer.name == name:
                return viewer

    def _default_exporters(self):
        """ TODO: push to an ExtensionPoint """
        from .exporters.stl.exporter import StlExporter
        from .exporters.step.exporter import StepExporter
        return [StlExporter, StepExporter]

    def export(self, event):
        """ Export the current model to stl """
        from twisted.internet import reactor
        options = event.parameters.get('options')
        if not options:
            raise ValueError("An export `options` parameter is required")

        # Pickle the configured exporter and send it over
        cmd = [sys.executable]
        if not sys.executable.endswith('declaracad'):
            cmd.append('main.py')

        data = jsonpickle.dumps(options)
        assert data != 'null', f"Exporter failed to serialize: {options}"
        cmd.extend(['export', data])

        log.debug(" ".join(cmd))
        protocol = ProcessLineReceiver()
        reactor.spawnProcess(
            protocol, sys.executable, args=cmd, env=os.environ)
        return protocol

    def screenshot(self, event):
        """ Export the views as a screenshot """
        if 'options' not in event.parameters:
            editor = self.workbench.get_plugin('declaracad.editor')
            options = ScreenshotOptions(filename=editor.active_document.name)
        else:
            options = event.parameters.get('options')
        results = []
        if options.target:
            viewer = self.get_viewer(options.target)
            if viewer:
                results.append(viewer.renderer.screenshot(options.path))
        else:
            for i, viewer in enumerate(self.get_viewers()):
                # Insert view number
                path, ext = os.path.splitext(options.path)
                filename = "{}-{}{}".format(path, i+1, ext)
                results.append(viewer.renderer.screenshot(filename))
        return results

