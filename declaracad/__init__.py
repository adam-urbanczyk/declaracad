"""
Copyright (c) 2017, Jairus Martin.

Distributed under the terms of the GPL v3 License.

The full license is in the file LICENSE, distributed with this software.

Created on Dec 6, 2015

@author: jrm
"""
from argparse import ArgumentParser


def launch_exporter(args):
    from declaracad.apps import exporter
    exporter.main(**args.__dict__)


def launch_viewer(args):
    from declaracad.apps import viewer
    viewer.main(**args.__dict__)


def launch_workbench(args):
    from declaracad.apps import workbench
    workbench.main(**args.__dict__)


def main():
    parser = ArgumentParser()
    subparsers = parser.add_subparsers(help='DeclaraCAD subcommands')
    viewer = subparsers.add_parser("view", help="View the given file")
    viewer.set_defaults(func=launch_viewer)
    viewer.add_argument("file", help="File to view")
    viewer.add_argument("-f", "--frameless", action='store_true',
                        help="Frameless viewer")
    
    exporter = subparsers.add_parser("export", help="Export the given file")
    exporter.set_defaults(func=launch_exporter)
    exporter.add_argument("options", help="File to export or json string of "
                                          "ExportOption parameters")
    args = parser.parse_args()
    
    # Start the app
    launcher = getattr(args, 'func', launch_workbench)
    launcher(args)
    
        
if __name__ == '__main__':
    main()
