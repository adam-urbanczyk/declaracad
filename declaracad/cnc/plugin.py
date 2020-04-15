# -*- coding: utf-8 -*-
"""
Copyright (c) 2017, Jairus Martin.

Distributed under the terms of the GPL v3 License.

The full license is in the file LICENSE, distributed with this software.

Created on Aug 8, 2018

@author: jrm
"""
import logging
from atom.api import (
    Atom, Instance, Subclass, Str, Int, Bool, ContainerList, Bytes, observe
)
from declaracad.core.api import Plugin, log
from enaml.application import deferred_call
from twisted.internet import reactor
from twisted.internet.defer import Deferred, DeferredList, inlineCallbacks
from twisted.internet.serialport import SerialPort
from twisted.protocols.basic import LineReceiver
from serial.tools.list_ports import comports


class ConnectionFactory(Atom):
    def refresh(self):
        """ Do a scan to see which connections are available.
        
        """
        raise NotImplementedError

    def connect(self, protocol):
        """ Create a new connection for the given protocol.
        Must return a deferred that resolves when connected .
        
        """
        raise NotImplementedError


class SerialConnectionFactory(ConnectionFactory):
    
    #: The port
    port = Instance(object)
    
    baudrate = Int(115200).tag(config=True)
    
    @classmethod
    def get_connections(cls):
        return [Connection(name=str(port),
                           factory=cls(port=port)) for port in comports()]

    def connect(self, protocol):
        from twisted.internet import reactor
        d = Deferred()
        def do_connect():
            try:
                conn = SerialPort(protocol, self.port.device, reactor, 
                                  baudrate=self.baudrate)
                d.callback(conn)
            except Exception as e:
                log.error(e)
                d.callback(e)
        deferred_call(do_connect)
        return d


class Connection(Atom, LineReceiver):
    #: Name
    name = Str()
    
    #: Connection state
    connected = Int()
    
    #: Log output
    output = ContainerList()
    
    #: Split on newlines
    delimiter = Bytes(b'\n')
    
    #: Connection errors
    errors = Str()
    
    #: The factory that created this connection
    factory = Instance(ConnectionFactory)
    
    def connect(self):
        return self.factory.connect(self)
    
    def connectionMade(self):
        self.connected = 1
        
    def connectionLost(self, reason):
        self.connected = 0
        self.errors = str(reason)
    
    def lineReceived(self, line):
        self.output.append(line)
        
    def write(self, message):
        if self.transport is None:
            return IOError("Not connected")
        if not isinstance(message, bytes):
            message = message.encode()
        return self.transport.write(message)

    def disconnect(self):
        """ """
        if self.transport:
            self.transport.loseConnection()


class CncPlugin(Plugin):
    
    #: Connection factories
    connection_factories = ContainerList(Subclass(ConnectionFactory), default=[
        SerialConnectionFactory
    ])
    
    #: Connections
    available_connections = ContainerList(Connection)
    
    #: Active connections
    connections = ContainerList(Connection)
    
    def start(self):
        self.refresh_connections()
        
    def refresh_connections(self):
        """ Update available connections """
        conns = []
        for ConnectionFactory in self.connection_factories:
            conns.extend(ConnectionFactory.get_connections())            
        self.available_connections = conns
