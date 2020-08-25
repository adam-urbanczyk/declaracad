"""
Copyright (c) 2017, Jairus Martin.

Distributed under the terms of the GPL v3 License.

The full license is in the file LICENSE, distributed with this software.

Created on Aug 8, 2018

@author: jrm
"""
import serial
import asyncio
from atom.api import (
    Atom, Instance, Subclass, Str, Int, Bool, ContainerList, Bytes, Enum,
    List, Coerced, observe
)
from enaml.application import deferred_call
from serial.tools.list_ports import comports

from declaracad.core.api import Plugin, Model, log
from declaracad.core.serial import SerialTransport, create_serial_connection


class ConnectionFactory(Model):
    def refresh(self):
        """ Do a scan to see which connections are available.

        """
        raise NotImplementedError

    def connect(self, protocol):
        """ Create a new connection for the given protocol.
        Must return a deferred that resolves when connected .

        """
        raise NotImplementedError


class SerialConfig(Model):
    #: Available serial ports
    ports = List()

    PARITIES = {v: k for k, v in serial.PARITY_NAMES.items()}

    #: Serial port config
    port = Str().tag(config=True)
    baudrate = Int(115200).tag(config=True)
    bytesize = Enum(serial.EIGHTBITS, serial.SEVENBITS, serial.SIXBITS,
                    serial.FIVEBITS).tag(config=True)
    parity = Enum(*serial.PARITY_NAMES.values()).tag(config=True)
    stopbits = Enum(serial.STOPBITS_ONE, serial.STOPBITS_ONE_POINT_FIVE,
                    serial.STOPBITS_TWO).tag(config=True)
    xonxoff = Bool().tag(config=True)
    rtscts = Bool(True).tag(config=True)
    dsrdtr = Bool().tag(config=True)

    def _default_ports(self):
        return comports()

    def _default_parity(self):
        return 'None'

    def _default_port(self):
        if self.ports:
            return self.ports[0].device
        return ""

    def refresh(self):
        self.ports = self._default_ports()


class SerialConnectionFactory(ConnectionFactory):

    #: The port
    handle = Instance(object)
    config = Instance(SerialConfig, ())

    baudrate = Int(115200).tag(config=True)

    @classmethod
    def get_connections(cls):
        connections = []
        for port in comports():
            factory = cls(config=SerialConfig(port=port.device))
            connections.append(Connection(name=str(port), factory=factory))
        return connections

    async def connect(self, protocol):

        if self.handle is not None:
            transport, _ = self.handle
            transport.close()
        loop = asyncio.get_event_loop()

        config = self.config
        self.handle = await create_serial_connection(
            loop,
            lambda: protocol,
            config.port,
            baudrate=config.baudrate,
            bytesize=config.bytesize,
            parity=SerialConfig.PARITIES[config.parity],
            stopbits=config.stopbits,
            xonxoff=config.xonxoff,
            rtscts=config.rtscts)


class Connection(Model, asyncio.Protocol):
    #: Name
    name = Str()

    #: Connection state
    connected = Coerced(bool)

    transport = Instance(SerialTransport)

    #: Log output
    output = ContainerList()
    last_read = Bytes()
    last_write = Bytes()

    #: Split on newlines
    delimiter = Bytes(b'\n')

    #: Connection errors
    errors = Str()

    #: The factory that created this connection
    factory = Instance(ConnectionFactory)

    async def connect(self):
        return await self.factory.connect(self)

    def connection_made(self, transport):
        self.connected = True
        self.transport = transport

    def connection_lost(self, exc):
        self.connected = False
        self.errors = f'{exc}'

    def data_received(self, data):
        self.last_read = data
        self.output.append(data.decode())

    def pause_writing(self):
        print('pause writing')
        print(self.transport.get_write_buffer_size())


    def resume_writing(self):
        print(self.transport.get_write_buffer_size())
        print('resume writing')

    async def write(self, message):
        if self.transport is None:
            return IOError("Not connected")
        if not isinstance(message, bytes):
            message = message.encode()
        self.last_write = message

        # This just puts it into the write buffer
        self.transport.write(message)

    async def disconnect(self):
        """ """
        if self.transport:
            self.transport.close()


class CncPlugin(Plugin):

    #: Connection factories
    connection_factories = ContainerList(
        Subclass(ConnectionFactory), default=[SerialConnectionFactory])

    #: Connections
    available_connections = ContainerList(Connection)

    #: Active connection
    connection = Instance(Connection)

    #: Monitor fields
    add_newline = Bool(False).tag(config=True)
    strip_whitespace = Bool(False).tag(config=True)
    input_enabled = Bool(True).tag(config=True)
    output_enabled = Bool(True).tag(config=True)
    autoscroll = Bool(True).tag(config=True)

    #: Command history
    history = ContainerList().tag(config=True)

    #: Block writing
    locked = Bool()

    def start(self):
        self.refresh_connections()

    def refresh_connections(self):
        """ Update available connections """
        conns = []
        for ConnectionFactory in self.connection_factories:
            conns.extend(ConnectionFactory.get_connections())
        self.available_connections = conns

    def _default_connection(self):
        if self.available_connections:
            return self.available_connections[0]

    # -------------------------------------------------------------------------
    # Commands
    # -------------------------------------------------------------------------
    async def connect(self):
        if self.connection:
            await self.connection.connect()

    async def disconnect(self):
        if self.connection:
            await self.connection.disconnect()

    async def rapid_move_to(self, point):
        if self.locked:
            return
        connection = self.connection
        if connection:
            if not connection.connected:
                await connection.connect()
            x, y, z = point
            await connection.write(f'G0 X{x}, Y{y} Z{z}\n')

    async def send_file(self, filename):
        self.locked = True
        try:
            with open(filename, 'rb') as f:
                for line in f:
                    await self.connection.write(line)
        finally:
            self.locked = False
