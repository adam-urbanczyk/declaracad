"""
Copyright (c) 2018, Jairus Martin.

Distributed under the terms of the GPL v3 License.

The full license is in the file LICENSE, distributed with this software.

Created on Oct 10, 2018

@author: jrm
"""
import os
import enaml
from atom.api import Constant, Enum, Float, Unicode
from declaracad.occ.plugin import ModelExporter, load_model
        
        
VERTEX_MODES = {'one compound': 0, 'single vertex': 1}
PRECISION_MODES = {'least': -1, 'average': 0, 'greatest': 1, 'session': 2}
ASSEMBLY_MODES = {'off': 0, 'on': 1, 'auto': 2}
SURFACECURVE_MODES = {'off': 0, 'on': 1}
        
        
class StepExporter(ModelExporter):
    """
    References
    ----------
    https://dev.opencascade.org/doc/overview/html/
        occt_user_guides__step.html#occt_step_3
    """
    extension = 'step'
    schema = Enum('AP214 CD', 'AP214 DIS', 'AP203', 'AP214 IS', 'AP242 DIS')
    units = Enum('mm', 'in')
    precision_mode = Enum('average', 'least', 'greatest', 'session')
    precision_val = Float(0.0001).tag(
        help="This parameter gives the uncertainty for STEP entities "
             "constructed from OCCT shapes when the write.precision.mode "
             "parameter value is 'greatest'.")
    product_name = Unicode().tag(
        help="Defines the text string that will be used for field `name' of "
             "PRODUCT entities written to the STEP file.")
    assembly_mode = Enum('off', 'on', 'auto')
    surfacecurve_mode = Enum('on', 'off')
    vertex_mode = Enum('one compound', 'single vertex')

    @classmethod
    def get_options_view(cls):
        with enaml.imports():
            from .options import OptionsForm
            return OptionsForm
    
    def export(self):
        """ Export a DeclaraCAD model from an enaml file to an STL based on the
        given options.
        
        Parameters
        ----------
        options: declaracad.occ.plugin.ExportOptions
        
        """
        from OCC.STEPControl import STEPControl_Writer, STEPControl_AsIs
        from OCC.Interface import Interface_Static_SetCVal as SetCVal
        from OCC.Interface import Interface_Static_SetIVal as SetIVal
        from OCC.Interface import Interface_Static_SetRVal as SetRVal
        from OCC.IFSelect import IFSelect_RetDone
        
        # Set all params
        exporter = STEPControl_Writer()
        SetIVal("write.precision.mode", PRECISION_MODES[self.precision_mode])
        if self.precision_mode == 'greatest':
            SetRVal("write.precision.val", self.precision_val)
        SetIVal("write.step.assembly", ASSEMBLY_MODES[self.assembly_mode])
        SetCVal("write.step.schema", self.schema)
        if self.product_name:
            SetCVal("write.step.product.name", self.product_name)
        SetIVal("write.surfacecurve.mode", 
                SURFACECURVE_MODES[self.surfacecurve_mode])
        SetCVal("write.step.unit", self.units.upper())
        SetIVal("write.step.vertex.mode", VERTEX_MODES[self.vertex_mode])

        # Load the enaml model file
        parts = load_model(self.filename)
        
        for part in parts:
            # Render the part from the declaration
            shape = part.render()
            
            # Transfer all shapes
            if hasattr(shape, 'Shape'):
                exporter.Transfer(shape.Shape(), STEPControl_AsIs)
            else:
                exporter.Transfer(shape, STEPControl_AsIs)

        # Send it
        status = exporter.Write(self.path)
        if status != IFSelect_RetDone or not os.path.exists(self.path):
            raise RuntimeError("Failed to write shape")
        
    
