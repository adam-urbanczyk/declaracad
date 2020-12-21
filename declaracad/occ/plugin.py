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
import asyncio
import functools
import jsonpickle
from types import ModuleType
from atom.api import (
    Atom, ContainerList, Str, Float, Dict, Bool, Int, Instance, Enum,
    ForwardInstance, Constant, observe, set_default
)
from declaracad.core.api import Plugin, Model, log
from declaracad.core.utils import ProcessLineReceiver

from enaml.application import timed_call, deferred_call
from enaml.core.parser import parse
from enaml.core.import_hooks import EnamlCompiler
from enaml.colors import ColorMember

from .part import Part


@functools.lru_cache
def is_remote_attr(name):
    """ Check if the given attr name is valid on the remote viewer.

    """
    with enaml.imports():
        from .view import ViewerWindow, ModelViewer
    attrs = [name]
    if name.startswith('set_'):
        attrs.append(name[4:])
    for cls in (ViewerWindow, ModelViewer):
        for attr in attrs:
            if hasattr(cls, attr):
                return True
    return False


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
    """ Load a DeclaraCAD model from an enaml file, source, or a shape
    supported by the LoadShape node.

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
    if source or filename.endswith('.enaml'):
        # Parse and compile the code
        with open(filename, 'r') as f:
            source = f.read()
        ast = parse(source)
        code = EnamlCompiler.compile(ast, filename)
        module = ModuleType(filename.rsplit('.', 1)[0])
        module.__file__ = filename
        namespace = module.__dict__
        with enaml.imports():
            exec(code, namespace)
        Assembly = namespace['Assembly']
        return [Assembly()]
    elif os.path.exists(filename):
        # Try to load from filename
        with enaml.imports():
            from .loader import LoadedPart
        return [LoadedPart(filename=filename)]
    else:
        return []


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

    #: Default save directory
    default_dir = Str()

    #: Document file name
    filename = Str()

    #: Only screenshot this view
    target = Str()

    def _default_path(self):
        path, filename = os.path.split(self.filename)
        default_dir = self.default_dir or path
        filename, ext = os.path.splitext(filename)
        return os.path.join(default_dir, "{}.png".format(filename))

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
    max_retries = Int(10)

    #: ID count
    _id = Int()

    #: Holds responses temporarily
    _responses = Dict()

    #: Seconds to ping
    _ping_rate = Int(40)

    #: Capture stderr separately
    err_to_out = set_default(False)

    def redraw(self):
        if self.document:
            # Trigger a reload
            self.document.version += 1
        else:
            self.set_version(self._id)

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
        encoded_msg = jsonpickle.dumps(request).encode() + b'\r\n'
        deferred_call(self.transport.write, encoded_msg)

    async def start(self):
        atexit.register(self.terminate)
        cmd = [sys.executable]
        if not sys.executable.endswith('declaracad'):
            cmd.extend(['-m', 'declaracad'])
        cmd.extend(['view', '-', '-f'])
        loop = asyncio.get_event_loop()
        self.process = await loop.subprocess_exec(lambda: self, *cmd)
        return self.process

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

        log.debug(f"Attempting to restart viewer {self.process}")
        deferred_call(self.start)

    def connection_made(self, transport):
        super().connection_made(transport)
        self.schedule_ping()
        self.terminated = False

    def data_received(self, data):
        line = data.decode()
        try:
            response = jsonpickle.loads(line)
            # log.debug(f"viewer | resp | {response}")
        except Exception as e:
            log.debug(f"viewer | out | {line.rstrip()}")
            response = {}

        doc = self.document

        if not isinstance(response, dict):
            log.debug(f"viewer | out | {response.rstrip()}")
            return
        elif response:
            log.debug(f"viewer | out | {response}")

        #: Special case for startup
        response_id = response.get('id')
        if response_id == 'window_id':
            self.window_id = response['result']
            self.restarts = 0  # Clear the restart count
            return
        elif response_id == 'keep_alive':
            return
        elif response_id == 'invoke_command':
            command_id = response.get('command_id')
            parameters = response.get('parameters', {})
            log.debug(f"viewer | out | {command_id}({parameters})")
            self.plugin.workbench.invoke_command(command_id, parameters)
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
            f = self._responses.pop(response_id, None)
            if f is not None:
                try:
                    error = response.get('error')
                    if error is not None:
                        if doc:
                            msgs = error.get('message', '').split("\n")
                            doc.errors.extend(msgs)
                        f.set_error(RuntimeError(error))
                    else:
                        f.set_result(response.get('result'))
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

    def err_received(self, data):
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

    def process_exited(self, reason=None):
        log.warning(f"renderer | process ended: {reason}")
        if not self.terminated:
            # Clear the filename on crash so it works when reset
            self.restart()
        log.warning("renderer | stdout closed")

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
        """ Proxy all calls not defined here to the remote viewer.

        This makes doing `setattr(renderer, attr, value)` get passed to the
        remote viewer.

        """
        if not is_remote_attr(name):
            raise AttributeError(f"Remote viewer has no attribute '{name}'")

        def remote_viewer_call(*args, **kwargs):
            f = asyncio.Future()
            self._id += 1
            kwargs['_id'] = self._id
            self._responses[self._id] = f
            self.send_message(name, *args, **kwargs)
            return f
        return remote_viewer_call


class ViewerPlugin(Plugin):
    # -------------------------------------------------------------------------
    # Default viewer settings
    # -------------------------------------------------------------------------
    background_mode = Enum('gradient', 'solid').tag(config=True, viewer='background')
    background_top = ColorMember('lightgrey').tag(config=True, viewer='background')
    background_bottom = ColorMember('grey').tag(config=True, viewer='background')
    background_fill_method = Enum(
        'corner3', 'corner1', 'corner2', 'corner4',
        'ver', 'hor', 'diag1', 'diag2',
        ).tag(config=True, viewer='background')
    trihedron_mode = Str('right-lower').tag(config=True, viewer=True)

    #: Defaults
    shape_color = ColorMember('steelblue').tag(config=True, viewer=True)

    #: Grid options
    grid_mode = Str().tag(config=True, viewer=True)
    grid_major_color = ColorMember('#444').tag(config=True, viewer='grid_colors')
    grid_minor_color = ColorMember('#888').tag(config=True, viewer='grid_colors')

    #: Rendering options
    antialiasing = Bool(True).tag(config=True, viewer=True)
    raytracing = Bool(True).tag(config=True, viewer=True)
    draw_boundaries = Bool(True).tag(config=True, viewer=True)
    shadows = Bool(True).tag(config=True, viewer=True)
    reflections = Bool(True).tag(config=True, viewer=True)
    chordial_deviation = Float(0.001).tag(config=True, viewer=True)

    # -------------------------------------------------------------------------
    # Plugin members
    # -------------------------------------------------------------------------
    #: Default dir for screenshots
    screenshot_dir = Str().tag(config=True)

    #: Exporters
    exporters = ContainerList()

    def get_viewer_members(self):
        for m in self.members().values():
            meta = m.metadata
            if not meta:
                continue
            if meta.get('viewer'):
                yield m

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
        viewer.renderer.source = editor.get_text()
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

    # -------------------------------------------------------------------------
    # Plugin commands
    # -------------------------------------------------------------------------

    def export(self, event):
        """ Export the current model to stl """
        options = event.parameters.get('options')
        if not options:
            raise ValueError("An export `options` parameter is required")

        # Pickle the configured exporter and send it over
        cmd = [sys.executable]
        if not sys.executable.endswith('declaracad'):
            cmd.extend(['-m', 'declaracad'])

        data = jsonpickle.dumps(options)
        assert data != 'null', f"Exporter failed to serialize: {options}"
        cmd.extend(['export', data])
        log.debug(" ".join(cmd))
        protocol = ProcessLineReceiver()
        loop = asyncio.get_event_loop()
        deferred_call(loop.subprocess_exec, lambda: protocol, *cmd)
        return protocol

    def screenshot(self, event):
        """ Export the views as a screenshot """
        if 'options' not in event.parameters:
            editor = self.workbench.get_plugin('declaracad.editor')
            filename = editor.active_document.name
            options = ScreenshotOptions(
                filename=filename,
                default_dir=self.screenshot_dir)
        else:
            options = event.parameters.get('options')
            # Update the default screenshot dir
            self.screenshot_dir, _ = os.path.split(options.path)
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

