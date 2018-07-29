"""
Copyright (c) 2017, Jairus Martin.

Distributed under the terms of the GPL v3 License.

The full license is in the file LICENSE, distributed with this software.

Created on Dec 6, 2015

@author: jrm
"""
from argparse import ArgumentParser


def main():
    parser = ArgumentParser()
    parser.add_argument("-v", "--view", help="View the given file")
    parser.add_argument("--frameless", action='store_true',
                        help="Frameless viewer")
    args = parser.parse_args()
    if args.view:
        from declaracad.apps import viewer
        viewer.main(**args.__dict__)
    else:
        from declaracad.apps import workbench
        workbench.main(**args.__dict__)
        
if __name__ == '__main__':
    main()
