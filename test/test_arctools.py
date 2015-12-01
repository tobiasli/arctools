#-------------------------------------------------------------------------------
# Name:        arctools test suite
# Purpose:     Test the components of the arctools module.
#
# Author:      Tobias
#
# Created:     10.11.2015
# Copyright:   (c) Tobias 2015
# Licence:     <your licence>
#-------------------------------------------------------------------------------
import unittest
import os
PATH = os.path.dirname(__file__)
TEST_GDB = os.path.join(PATH,r'bin\test.gdb')

DATASETS = ['feature_class','geodatabase_table']
FIELDS = [  ['id', 'weight', 'SHAPE@', 'name', 'SHAPE_Length', 'SHAPE_Area', 'time_and_date'],
            ['index', 'date', 'age', 'content']
            ]

METHODS = ['insert','update','delete']

class TestArctoolsModule(unittest.TestCase):

    def test_tableToDict_method(self):
        import arctools
        import arcpy

        for dataset in DATASETS:
            fullpath = os.path.join(TEST_GDB,dataset)

            data = arctools.tableToDict(fullpath)
            self.assertTrue(data)

        # Test grouping.

    def test_dictToTable_method(self):
        import arctools
        import arcpy
        for dataset,fields in zip(DATASETS,FIELDS):
            try:
                input = os.path.join(TEST_GDB,dataset)
                output = input + '_output'

                if arcpy.Exists(output):
                    arcpy.Delete_management(output)

                data = arctools.tableToDict(input,fields = fields)
                self.assertTrue(data)
                arctools.dictToTable(data,output)

                # Test fail when writing to existing table or feature class:
                try:
                    arctools.dictToTable(data,output,method = 'insert', makeTable = True) # makeTable should be false when writing to an existing table. This should therefore fail.
                    self.fail('arctools.dictToTable overwrote output when is should have failed.')
                except:
                    self.assertTrue(True) # Test is a success if the above line fails.

                # Assert feature type and spatial reference:
                in_desc = arcpy.Describe(input)
                out_desc = arcpy.Describe(output)

                self.assertTrue(in_desc.dataType == out_desc.dataType)
                if hasattr(in_desc, 'shapeType') and hasattr(out_desc, 'shapeType'):
                    self.assertTrue(in_desc.shapeType == out_desc.shapeType)
                    self.assertTrue(in_desc.spatialReference.name == out_desc.spatialReference.name)
                else:
                    self.assertFalse(hasattr(in_desc, 'shapeType') and hasattr(out_desc, 'shapeType'))

                # Test insert when writing data to table a second time (append):
                arctools.dictToTable(data,output,method = 'insert', makeTable = False) #Duplicate contents of output table.
                test = arctools.tableToDict(output,fields = fields)
                self.assertTrue(test == data + data)

                # Test different kinds of input data structures.

            finally:
                if arcpy.Exists(output):
                    arcpy.Delete_management(output)

def run():
    suite = unittest.TestLoader().loadTestsFromTestCase(TestArctoolsModule)
    unittest.TextTestRunner(verbosity=2).run(suite)

if __name__ == '__main__':
    run()



