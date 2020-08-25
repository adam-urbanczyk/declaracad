"""
Copyright (c) 2020, Jairus Martin.

Distributed under the terms of the GPL v3 License.

The full license is in the file LICENSE, distributed with this software.

Created on Aug 24, 2020

@author: jrm
"""
import sys
import inspect
import asyncio
import logging
from functools import wraps, partial
from asyncqt import QEventLoop
from atom.api import Instance
from enaml.qt.qt_application import QtApplication
from declaracad.core.utils import log


class Application(QtApplication):
    """ Add asyncio support . Seems like a complete hack compared to twisted
    but whatever.

    """

    loop = Instance(QEventLoop)

    def __init__(self):
        super().__init__()

        #: Set event loop policy for windows
        if sys.platform == 'win32':
            asyncio.set_event_loop_policy(
                asyncio.WindowsSelectorEventLoopPolicy())

        self.loop = QEventLoop(self._qapp)
        asyncio.set_event_loop(self.loop)
        for name in ('asyncqt._unix._Selector',
                     'asyncqt._QEventLoop',
                     'asyncqt._SimpleTimer'):
            log = logging.getLogger(name)
            log.setLevel(logging.WARN)

    def start(self):
        """ Run using the event loop

        """
        log.info("Application starting")
        with self.loop:
            self.loop.run_forever()

    def deferred_call(self, callback, *args, **kwargs):
        """ Invoke a callable on the next cycle of the main event loop
        thread.

        Parameters
        ----------
        callback : callable
            The callable object to execute at some point in the future.

        args, kwargs
            Any additional positional and keyword arguments to pass to
            the callback.

        """
        if asyncio.iscoroutinefunction(callback):
            task = lambda: asyncio.ensure_future(callback(*args, **kwargs))
            return self.loop.call_soon(task)
        return super().deferred_call(callback, *args, **kwargs)

    def timed_call(self, ms, callback, *args, **kwargs):
        """ Invoke a callable on the main event loop thread at a
        specified time in the future.

        Parameters
        ----------
        ms : int
            The time to delay, in milliseconds, before executing the
            callable.

        callback : callable
            The callable object to execute at some point in the future.

        args, kwargs
            Any additional positional and keyword arguments to pass to
            the callback.

        """
        if asyncio.iscoroutinefunction(callback):
            task = lambda: asyncio.ensure_future(callback(*args, **kwargs))
            return self.loop.call_later(ms/1000, task)
        return super().timed_call(ms, callback, *args, **kwargs)
