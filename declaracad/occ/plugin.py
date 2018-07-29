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
import atexit
import enaml
from atom.api import List, Unicode, Float, Bool, Int, Instance, observe
from declaracad.core.api import Plugin, Model, log
from enaml.application import timed_call
from .part import Part

from OCC.TopoDS import TopoDS_Compound
from OCC.BRep import BRep_Builder

from twisted.internet.protocol import ProcessProtocol
from twisted.protocols.basic import LineReceiver


def viewer_factory():
    with enaml.imports():
        from .view import ViewerDockItem
    return ViewerDockItem


class ExportError(Exception):
    """ Raised if export failed """


class ExportOptions(Model):
    path = Unicode()
    linear_deflection = Float(0.05, strict=False)
    angular_deflection = Float(0.5, strict=False)
    relative = Bool()
    binary = Bool(False)


class ViewerProcess(Model, ProcessProtocol, LineReceiver):
    #: Window id obtained after starting the process
    window_id = Int()
    
    #: Process handle
    process = Instance(object)
    
    #: Process stdio
    transport = Instance(object)
    
    #: Filename
    filename = Unicode()
    
    #: View version
    version = Int()
    
    #: Split on each line
    delimiter = b'\n'
    
    @observe('filename', 'version')
    def _update_viewer(self, change):
        self.send_message(change['name'], change['value'])
        
    def send_message(self, method, *args, **kwargs):
        # Defer until it's ready
        if not self.transport:
            log.debug('renderer | message not ready deferring')
            timed_call(0, self.send_message, method, *args, **kwargs)
            return
        request = {'jsonrpc': '2.0', 'method': method, 'params': args or kwargs}
        log.debug(f'renderer | sent | {request}')
        self.transport.write(json.dumps(request).encode()+b'\r\n')
    
    def _default_process(self):
        from twisted.internet import reactor
        exe = sys.executable
        atexit.register(self.terminate)
        return reactor.spawnProcess(self, exe, 
                                    args=[exe, 'main.py', '--view', '-',
                                          '--frameless'],
                                    env=os.environ)
    
    def _default_window_id(self):
        # Spawn the process 
        timed_call(0, lambda: self.process)
        return 0
    
    def connectionMade(self):
        self.transport.disconnecting = 0
    
    def outReceived(self, data):
        log.debug(f"render | out | {data}")
        self.dataReceived(data)
        
    def lineReceived(self, line):
        try:
            response = json.loads(line.decode())
            
        except Exception as e:
            log.error(f"render | resp | {e}")
            response = {}
        log.debug(f"render | resp | {response}")
        
        #: Special case for startup
        if response.get('id') == -0xbabe:
            self.window_id = response['result']
        
    def errReceived(self, data):
        log.debug(f"render | err | {data}")
    
    def inConnectionLost(self):
        log.warning("renderer | stdio closed (we probably did it)")
    
    def outConnectionLost(self):
        log.warning("renderer | stdout closed")
    
    def errConnectionLost(self):
        log.warning("renderer | stderr closed")
    
    def processExited(self, reason):
        log.warning(f"renderer | process exit status {reason.value.exitCode}")
    
    def processEnded(self, reason):
        log.warning(f"renderer | process ended status {reason.value.exitCode}")
        
    def terminate(self):
        try:
            self.transport.signalProcess('KILL')
        except:
            pass
    

class ViewerPlugin(Plugin):
    #: List of parts to display
    parts = List(Part)
    
    #: Viewer processes
    #viewers = List(ViewerProcess, default=[ViewerProcess()])
    
    def get_viewers(self):
        ViewerDockItem = viewer_factory()
        dock = self.workbench.get_plugin('declaracad.ui').get_dock_area()
        for item in dock.dock_items():
            if isinstance(item, ViewerDockItem):
                yield item

    def _observe_parts(self, change):
        """ When changed, do a fit all """
        if change['type'] == 'update':
            timed_call(500, self.fit_all)

    def fit_all(self, event=None):
        return
        viewer = self.get_viewer()
        viewer.proxy.display.FitAll()

    def get_viewer(self):
        return
        ui = self.workbench.get_plugin('enaml.workbench.ui')
        area = ui.workspace.content.find('dock_area')
        return area.find('viewer-item').viewer

    def export(self, event):
        """ Export the current model to stl """
        from OCC.StlAPI import StlAPI_Writer
        from OCC.BRepMesh import BRepMesh_IncrementalMesh
        #: TODO: All parts
        options = event.parameters.get('options')
        if not isinstance(options, ExportOptions):
            return False

        exporter = StlAPI_Writer()
        exporter.SetASCIIMode(not options.binary)

        #: Make a compound of compounds (if needed)
        compound = TopoDS_Compound()
        builder = BRep_Builder()
        builder.MakeCompound(compound)
        for part in self.parts:
            #: Must mesh the shape first
            if isinstance(part, Part):
                builder.Add(compound, part.proxy.shape)
            else:
                builder.Add(compound, part.proxy.shape.Shape())

        #: Build the mesh
        mesh = BRepMesh_IncrementalMesh(
            compound,
            options.linear_deflection,
            options.relative,
            options.angular_deflection
        )
        mesh.Perform()
        if not mesh.IsDone():
            raise ExportError("Failed to create the mesh")

        exporter.Write(compound, options.path)
