"""
Copyright (c) 2017, Jairus Martin.

Distributed under the terms of the GPL v3 License.

The full license is in the file COPYING.txt, distributed with this software.

Created on Dec 5, 2017

@author
"""
import os
import sys
import importlib
from glob import glob
from os.path import dirname, split
from cx_Freeze import setup, Executable


# Dependencies are automatically detected, but it might need
# fine tuning.
def patch():
    #: Patch zope to include an __init__.py file
    #: idk what person thought leaving it out was a good idea
    mod = importlib.import_module('zope')
    zope_dir = dirname(mod.__file__)
    __init__py = os.path.join(zope_dir, '__init__.py')
    if not os.path.exists(__init__py):
        with open(__init__py, 'w') as f:
            pass


def find_enaml_files(*modules):
    """ Find .enaml files to include in the zip """
    files = {}
    for name in modules:
        mod = importlib.import_module(name)
        mod_path = dirname(mod.__file__)
        pkg_root = dirname(mod_path)

        for file_type in ['enaml', 'png']:
            for f in glob('{}/**/*.{}'.format(mod_path, file_type),
                          recursive=True):
                pkg = f.replace(pkg_root+os.path.sep, '')
                files[f] = pkg

    return files.items()


def find_data_files(*modules):
    files = {}
    for name in modules:
        mod = importlib.import_module(name)
        mod_path = name#mod.__file__# if hasattr(mod, '__file__') else name
        pkg_root = name#dirname(mod_path)

        for f in glob('{}/**/*.png'.format(mod_path), recursive=True):
            pkg = f.replace(pkg_root+os.path.sep, '')
            files[f] = pkg
    return files.items()


patch()
setup(
  name='micropyde',
  author="CodeLV",
  author_email="frmdstryr@gmail.com",
  license='GPLv3',
  url='https://github.com/codelv/micropyde/',
  description="An IDE for micropython",
  long_description=open("README.md").read(),
  version='1.0',
  install_requires=[
      'PyQt5', 'enaml', 'enamlx', 'QScintilla', 'twisted', 'autobahn',
      'qt5reactor', 'qtconsole', 'jsonpickle', 'pozetron-cli', 'jedi',
      'pyserial',
  ],
  options=dict(
      build_exe=dict(
          packages=[
              'micropyde',
              'enaml',
              'enamlx',
              'qt5reactor',
              'pygments',
              'ipykernel',
              'zmq'
          ],
          zip_include_packages=[
              'atom',
              'asn1crypto', 'asyncio', 'attr', 'autobahn', 'automat',
              'collections', 'concurrent', 'constantly', 'ctypes', 'curses',
              'cffi', 'cryptography',
              'dateutil', 'dbm', 'distutils',
              'email', 'enaml', 'enamlx', 'encodings',
              'future',
              'html', 'http',
              'idna', 'importlib', 'incremental', 'ipykernel', 'IPython',
              'ipython_genutils',
              'jedi', 'json', 'jsonpickle', 'jupyter_client', 'jupyter_core',
              #'lib2to3',
              'logging', 'libfuturize',
              #'micropyde',
              'multiprocessing',
              'OpenSSL',
              'parso', 'past', 'pexpect', 'pkg_resources', 'ply',
              'prompt_toolkit', 'ptyprocess', 'pydoc_data', 'pyflakes',
              'pygments', 'pycparser',
              'qtconsole', 'qt5reactor', 'qtpy',
              'sqlite3', 'setuptools', 'serial',
              'traitlets', 'twisted', 'traitlets', 'txaio', 'tornado',
              'tkinter', 'test',
              'unittest', 'urllib',
              'wcwidth',
              'xml', 'xmlrpc',
              'zope',
              #'zmq',
          ],
          zip_includes=find_enaml_files(
              #'micropyde',
              'enaml',
          ),
          excludes=[
              'enaml.core.byteplay.byteplay2',
              'enamlx.qt.qt_occ_viewer',
              #'lib2to3',
          ],
      )
  ),
  executables=[
      Executable('main.py',
                 targetName='micropyde',
                 base='Win32GUI' if sys.platform == 'win32' else None)
  ]
)
