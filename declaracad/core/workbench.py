"""
Copyright (c) 2017, Jairus Martin.

Distributed under the terms of the GPL v3 License.

The full license is in the file LICENSE, distributed with this software.

Created on Jul 12, 2015

@author: jrm
"""
import enaml
from atom.api import Unicode
from enaml.qt.QtWidgets import QMessageBox
from enaml.workbench.ui.api import UIWorkbench


class DeclaracadWorkbench(UIWorkbench):
    #: Singleton instance
    _instance = None

    #: For error messages
    app_name = Unicode('DeclaraCAD')

    def __init__(self, *args, **kwargs):
        if DeclaracadWorkbench.instance() is not None:
            raise RuntimeError("Only one workbench may exist!")
        DeclaracadWorkbench._instance = self
        super(DeclaracadWorkbench, self).__init__(*args, **kwargs)

    @classmethod
    def instance(cls):
        return cls._instance

    @property
    def application(self):
        ui = self.get_plugin('enaml.workbench.ui')
        return ui._application

    @property
    def window(self):
        """ Return the main UI window or a dialog if it wasn't made yet
        (during loading)

        """
        ui = self.get_plugin('enaml.workbench.ui')
        return ui.window.proxy.widget

    # -------------------------------------------------------------------------
    # Message API
    # -------------------------------------------------------------------------
    def message_critical(self, title, message, *args, **kwargs):
        """ Shortcut to display a critical popup dialog.

        """
        return QMessageBox.critical(self.window, "{0} - {1}".format(
            self.app_name, title), message, *args, **kwargs)

    def message_warning(self, title, message, *args, **kwargs):
        """ Shortcut to display a warning popup dialog.

        """
        return QMessageBox.warning(self.window, "{0} - {1}".format(
            self.app_name, title), message, *args, **kwargs)

    def message_information(self, title, message, *args, **kwargs):
        """ Shortcut to display an info popup dialog.

        """
        return QMessageBox.information(self.window, "{0} - {1}".format(
            self.app_name, title), message, *args, **kwargs)

    def message_about(self, title, message, *args, **kwargs):
        """ Shortcut to display an about popup dialog.

        """
        return QMessageBox.about(self.window, "{0} - {1}".format(
            self.app_name, title), message, *args, **kwargs)

    def message_question(self, title, message, *args, **kwargs):
        """ Shortcut to display a question popup dialog.

        """
        return QMessageBox.question(self.window, "{0} - {1}".format(
            self.app_name, title), message, *args, **kwargs)
