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
import shutil
import arctools

PATH = os.path.dirname(__file__)

ORIG_GDB = os.path.join(PATH, r'bin\test.gdb')

TEST_GDB = os.path.join(PATH, r'bin\current_run_test.gdb')

DATASETS = ['feature_class', 'feature_class_overlapping', 'geodatabase_table']
FIELDS = [['id', 'weight', 'SHAPE@', 'name', 'SHAPE_Length', 'SHAPE_Area', 'time_and_date'],
          ['id', 'SHAPE@', 'SHAPE_Length', 'SHAPE_Area'],
          ['id', 'date', 'age', 'name']
          ]

METHODS = ['insert', 'update', 'delete']


class TestArctoolsModule(unittest.TestCase):

    def setUp(self):
        print('\nPerforming test setup.')
        if os.path.exists(TEST_GDB):
            shutil.rmtree(TEST_GDB)
        shutil.copytree(ORIG_GDB, TEST_GDB)
        print('Performing test setup. ...Done.')

    def tearDown(self):
        print('Performing test teardown.')
        shutil.rmtree(TEST_GDB)
        print('Performing test teardown. ...Done.')

    def test_zonal_statistics_as_dict(self):
        temp_raster = os.path.join('in_memory', 'temp_raster')
        if arctools.arcpy.Exists(temp_raster):
            arctools.arcpy.Delete(temp_raster)
        value_raster = arctools.arcpy.PolygonToRaster_conversion((os.path.join(TEST_GDB, DATASETS[1])), 'SHAPE_Length', out_rasterdataset=temp_raster, cellsize=1000)

        # Raster value, Polygon zonal:
        results = arctools.zonal_statistics_as_dict(value_data=value_raster,
                                                    zone_data=os.path.join(TEST_GDB, DATASETS[0]),
                                                    zone_key_field='id')

        self.assertTrue(results == {1: {'OBJECTID': 1, 'mean': 0.0010825648754691818}, 2: {'OBJECTID': 2, 'mean': 0.009181874117074926}, 3: {'OBJECTID': 3, 'mean': 0.004449951349145824}, 4: {'OBJECTID': 4, 'mean': 0.0020576288672450736}, 5: {'OBJECTID': 5, 'mean': 0.0037129196933174385}, 6: {'OBJECTID': 6, 'mean': 0.0033706004855966636}})

        # Raster value, Raster zonal:
        results = arctools.zonal_statistics_as_dict(value_data=value_raster,
                                                    zone_data=value_raster,
                                                    zone_key_field='id')

        self.assertTrue(results == {23632.885296373341: {'OBJECTID': 23632.885296373341, 'mean': 23632.885296373359}, 57518.941553407247: {'OBJECTID': 57518.941553407247, 'mean': 34102.250329783834}, 34102.250329783841: {'OBJECTID': 34102.250329783841, 'mean': 57518.941553407327}})

        # Polygon value, Raster zonal:
        results = arctools.zonal_statistics_as_dict(value_data=os.path.join(TEST_GDB, DATASETS[0]),
                                                    zone_data=value_raster,
                                                    method='sum',
                                                    value_key_field='id')

        self.assertTrue(results == {23632.885296373341: {'id': 23632.885296373341, 'sum': 28.0}, 57518.941553407247: {'id': 57518.941553407247, 'sum': 24.0}, 34102.250329783841: {'id': 34102.250329783841, 'sum': 103.0}})

        # Raster value, polygon zonal: Multiple methods:
        results = arctools.zonal_statistics_as_dict(value_data=value_raster,
                                                    zone_data=os.path.join(TEST_GDB, DATASETS[0]),
                                                    method=['mean', 'sum'],
                                                    zone_key_field='id')

        self.assertTrue(results == {1: {'sum': 23632.886, 'mean': 0.0010825648754691818, 'OBJECTID': 1}, 2: {'sum': 23632.886, 'mean': 0.009181874117074926, 'OBJECTID': 2}, 3: {'sum': 34102.252, 'mean': 0.004449951349145824, 'OBJECTID': 3}, 4: {'sum': 57518.94, 'mean': 0.0020576288672450736, 'OBJECTID': 4}, 5: {'sum': 57518.94, 'mean': 0.0037129196933174385, 'OBJECTID': 5}, 6: {'sum': 57518.94, 'mean': 0.0033706004855966636, 'OBJECTID': 6}})

    def test_tableToDict_method(self):
        return 0
        for dataset in DATASETS:
            fullpath = os.path.join(TEST_GDB, dataset)

            data = arctools.tableToDict(fullpath)
            self.assertTrue(data)

            # Test grouping.
            # TODO

    def test_dictToTable_method(self):
        return 0
        for dataset, fields in [(DATASETS[i], FIELDS[i]) for i in [0, 2]]:
            try:
                input = os.path.join(TEST_GDB, dataset)
                output = input + '_output'

                if arctools.arcpy.Exists(output):
                    arctools.arcpy.Delete_management(output)

                data = arctools.tableToDict(input, fields=fields)
                self.assertTrue(data)

                # INSERT METHOD:
                method = 'insert'
                arctools.dictToTable(data, output)  # default to method = 'insert'

                # Test fail when writing to existing table or feature class:
                try:
                    arctools.dictToTable(data, output, method='insert', makeTable=True)  # makeTable should be false when writing to an existing table. This should therefore fail.
                    self.fail('arctools.dictToTable overwrote output when is should have failed.')
                except:
                    self.assertTrue(True)  # Test is a success if the above line fails.

                # Assert feature type and spatial reference:
                in_desc = arctools.arcpy.Describe(input)
                out_desc = arctools.arcpy.Describe(output)

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

                # UPDATE METHOD:
                # All utems with ID=1 should have name = 'test_name'
                update_data = [{'id':1,'name':'test_name'}]
                arctools.dictToTable(update_data, output, method = 'update', dictionaryKey = 'id')

                response = arctools.tableToDict(output, groupBy = 'id')
                for id in response:
                    for item in response[id]:
                        if id == update_data[0]['id']:
                            self.assertTrue(item['name'] == update_data[0]['name'])
                        else:
                            self.assertFalse(item['name'] == update_data[0]['name'])

                # Test different kinds of input data structures.

            finally:
                if arctools.arcpy.Exists(output):
                    arctools.arcpy.Delete_management(output)

def run():
    suite = unittest.TestLoader().loadTestsFromTestCase(TestArctoolsModule)
    unittest.TextTestRunner(verbosity=2).run(suite)

if __name__ == '__main__':
    run()



