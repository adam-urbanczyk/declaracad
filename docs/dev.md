# Developing on Declaracad

DeclaraCAD is based heavily on enaml's [workbench](https://enaml.readthedocs.io/en/latest/dev_guides/workbenches.html) framework.



### Startup

The main entrypoint is in [`declaracad/__init__.py`](https://github.com/codelv/declaracad/blob/master/declaracad/__init__.py)
this simply parses command line arguments and then starts one of the apps from
the [`declaracad/apps/`](https://github.com/codelv/declaracad/blob/master/declaracad/apps/) package.
Each app can be run individually for testing purposes.


### Opencascade

DeclaraCAD uses enaml's proxy-toolkit abstraction layers to let OCCT be
used in a more abstract manner.

The enaml declarations are under [`declaracad/occ/]()
and the implemenations (which use OCCT) are under [`declaracad/occ/impl`]().


