#!/usr/bin/env python
"""
Copyright (c) 2017, Jairus Martin.
Distributed under the terms of the GPL v3 License.
The full license is in the file COPYING.txt, distributed with this software.
Created on Dec 13, 2017
"""
from setuptools import setup, find_packages

setup(
    name='declaracad',
    version='0.3.0',
    description='Parametric 3D modeling with enaml and OpenCascade',
    long_description=open('README.md').read(),
    long_description_content_type='text/markdown',
    author='CodeLV',
    author_email='frmdstryr@gmail.com',
    license='GPL3',
    url='https://github.com/codelv/declaracad',
    entry_points={'console_scripts': [
        'declaracad = declaracad:main',
    ]},
    packages=find_packages(),
    install_requires=['enaml', 'jsonpickle', 'qtconsole',
                      'QScintilla', 'numpydoc', 'markdown', 'enamlx',
                      'qt5reactor', 'pyserial'],
)
