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

class TestArctoolsModule(unittest.TestCase):

    def test_tableToDict_method(self):
        import arctools
        import arcpy

        for dataset in DATASETS:
            fullpath = os.path.join(TEST_GDB,dataset)

            data = arctools.tableToDict(fullpath)
            self.assertTrue(data)

    def test_dictToTable_method(self):
        import arctools
        import arcpy

        for dataset in DATASETS:
            fullpath = os.path.join(TEST_GDB,dataset)
            output = fullpath + '_output'

            data = arctools.tableToDict(fullpath)
            self.assertTrue(data)
            arctools.dictToTable(data,output)

            arcpy.Delete_management(output)

def run():
    suite = unittest.TestLoader().loadTestsFromTestCase(TestArctoolsModule)
    unittest.TextTestRunner(verbosity=2).run(suite)

if __name__ == '__main__':
    run()



