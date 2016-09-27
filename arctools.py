# -*- coding: UTF-8 -*-
from __future__ import unicode_literals
'''
-------------------------------------------------------------------------------
Name:       arctools
Purpose:    Module with powerful tools built on top of standard arcpy
            functionality.

Author:     Tobias Litherland

Created:    17.12.2014
Copyright:  (c) Tobias Litherland 2014, 2015

-------------------------------------------------------------------------------

 Milestones:
    02.06.2015  TL  Added method create_filled_contours, which creates filled
                    contours for a specified set of contour levels.
    01.06.2015  TL  Added handling of grouped dictionaries in dictToTable.
    05.03.2015  TL  Canceled development of changeFieldOrder. The operation
                    is too complex and prone to errors, and the manual job
                    for a given table is not that hard. Maybe.
    05.03.2015  TL  Added property overwriteExistingOutput which controls
                    whether errors are raised if output allready exists.
    05.03.2015  TL  Added history. Current methods are:
                        dictToTable
                        tableToDict
                        renameFields (new)
                        changeFieldOrder (new)

-------------------------------------------------------------------------------

 Future improvements:
    - Rewrite functions to agree with PEP8.
    - Add "sortField" argument to tableToDict to allow sorted output based on a
        field.
    - Objectify module so it accepts a pre-loaded arcpy instance.

-------------------------------------------------------------------------------
'''
import os
import re
import datetime
import arcpy
import time
import random
import warnings
from collections import OrderedDict,Counter

# Properties
overwriteExistingOutput = False #True allows methods to overwrite existing output.

#Regex:
shapeIdentification = '(?i)^(shape)(@\w*)?$'
oidIdentification = '(?i)^objectid$'

class MethodException(Exception):
    def __init__(self, message):
        # Call the base class constructor with the parameters it needs
        super(MethodException, self).__init__(message)

class UnwritableFieldException(Exception):
    def __init__(self, message):
        # Call the base class constructor with the parameters it needs
        super(UnwritableFieldException, self).__init__(message)

class InputTypeException(Exception):
    def __init__(self, message):
        # Call the base class constructor with the parameters it needs
        super(InputStructureException, self).__init__(message)

class MissingFieldException(Exception):
    def __init__(self, message):
        # Call the base class constructor with the parameters it needs
        super(MissingFieldException, self).__init__(message)

class FieldException(Exception):
    def __init__(self, message):
        # Call the base class constructor with the parameters it needs
        super(FieldException, self).__init__(message)


def dictToTable(dictionary, table, method = 'insert', keyField = '', tableKey = '', fields = [],makeTable = True, featureClass = None, featureClassType = '', spatialReference = ''):
    '''
    Method for taking a dictionary and writing the values to a given table
    assuming that dictionary keys and table fields match. Can also perform
    update/insert/delete operations according to the values of method.

    All sub-dictionaries in dictionary must have fields in the same order.

    To be able to handle feature klasses, the dictionary must contain a "SHAPE"
    or "SHAPE@[argument]" field.

    Input
        dictionary      dict/list Dictionary of dictionaries or list of
                                dictionaries which is inserted into table.
                                Assumes that key names and value types match table schema.
        table           str     Path to output table.
        method          str     String defining operation performed on
                                table.
                                    insert = Append dictionary to table.
                                    update = Overwrite rows using dictionaryKey
                                             and tableKey to identify what rows
                                             to update.
                                    delete = Delete rows using dictionaryKey
                                             and tableKey to identify what rows
                                             to remove.
        keyField        str     Name of the field that contains unique id's
                                that are matched to the values of tableKey.
                                Data type of the field is arbitrary.
        tableKey        str     Name of the field that contains unique id's
                                that are matched to the values of
                                dictionaryKey. Data type of the field is
                                arbitrary. If left out it is assumed to be the
                                same as keyField.
        fields          list    List of fields from dictionary that should
                                be entered into table. If left empty method
                                will map all dictionary fields to table.
        makeTable       logic   True will recreate existing table according
                                to apparent data model of dictionary. False
                                will add to existing table, and fail if
                                table does not exist.
        featureClassType str    The type of feature class created. If empty,
                                queries the type property of the shape geometry.
        spatialReference bin    All valid identifiers of a spatial reference,
                                by name, ID or object.

    Output
        count           int     Report the numbers of rows written to the
                                table.
    '''

    arcpy.env.overwriteOutput = overwriteExistingOutput

    output_table = table
    dictionaryKey = keyField
    if not tableKey: #If fields are the same, you only need to specify one key field.
        tableKey = dictionaryKey

    assert isinstance(keyField, str)
    assert isinstance(tableKey, str)
    assert isinstance(dictionaryKey, str)
    assert not (method == 'update' and not (dictionaryKey and tableKey))
    assert not (method == 'delete' and not (dictionaryKey and tableKey))
    assert dictionary
    if fields:
        assert keyField in fields

    if not method in ['update','insert','delete']:
        raise MethodException('Operation %s not valid. Valid options are "insert","update" and "delete".',method)

    modifyTable = 'in_memory\\temporary_dataset'
    workspace = os.path.dirname(output_table)

    if arcpy.Exists(modifyTable):
        arcpy.Delete_management(modifyTable)

    if method == 'update' and makeTable == True:
##        warnings.warn('Updating table with makeTable == True:\nForcing makeTable == False.')
        makeTable = False

    if not makeTable:
        modifyTable = output_table

    # Get the field names from the first list in the
    islist = False
    isdict = False
    isgroupeddict = False

    # Straight list of dictionaries:
    if (isinstance(dictionary,list) or isinstance(dictionary,tuple)) and isinstance(dictionary[0],dict):
        islist = True
        dictionaryFrame = dictionary[0]

    # Dictionary of dictionaries:
    elif (isinstance(dictionary,dict) or isinstance(dictionary,OrderedDict)) and (isinstance(list(dictionary.values())[0],dict) or isinstance(list(dictionary.values())[0],OrderedDict)):
        isdict = True
        dictionaryFrame = list(dictionary.values())[0]

    # Dictionary of grouped dictionaries (dictionary of lists of dictionaries that have a common attribute):
    elif (isinstance(dictionary,dict) or isinstance(dictionary,OrderedDict)) and (isinstance(list(dictionary.values())[0],list) or isinstance(list(dictionary.values())[0],tuple)) and (isinstance(list(dictionary.values())[0][0],dict) or isinstance(list(dictionary.values())[0][0],OrderedDict)):
        isgroupeddict = True
        dictionaryFrame = list(dictionary.values())[0][0]
    else:
        raise InputTypeException('Unknown structure for input argument [dictionary].')

    # Unpack dictionaries and grouped dictionaries to lists for entry as table rows:
    if isdict:
        dictionary = [row for row in dictionary.values()]
    if isgroupeddict:
        dictionary = [item for sublist in dictionary.values() for item in sublist]

    # Check integrity of fields, and create new dictionary containing only the selected fields or all fields if none are selected.
    if fields:
        if isinstance(fields,str):
            fields = [fields]
        for field in fields:
            if not field in dictionaryFieldMappings:
                raise MissingFieldException('Field input %s is not present in dictionary.',field)

        dictionaryFieldMappings = {field:field for field in fields}
    else:
        # Create a mapping between the fields of the input dictionary and the actual field names of the output table.
        dictionaryFieldMappings = {field:field for field in list(dictionaryFrame.keys())}

    # Identify if feature class or not:
    orig_shape_name = ''
    orig_shape_field = ''
    orig_shape_suffix = ''
    if featureClass == None:
        featureClass = False
        for field in dictionaryFieldMappings:
            if re.findall(shapeIdentification,field):
                featureClass = True
                match = re.findall(shapeIdentification,field)[0]
                orig_shape_name = match[0]
                orig_shape_suffix = match[1]
                orig_shape_field = orig_shape_name + orig_shape_suffix
                break

    # Verify feature class:
    if featureClass:
        if makeTable and not featureClassType:
            if hasattr(dictionaryFrame[orig_shape_field],'type'):
                featureClassType = dictionaryFrame[orig_shape_field].type
            else:
                raise InputTypeException('featureClassType argument not passed, and input dictionary shape field %s does not have a type attribute' % field)

        if makeTable and not spatialReference:
            if hasattr(dictionaryFrame[orig_shape_field],'spatialReference'):
                spatialReference = dictionaryFrame[orig_shape_field].spatialReference
            else:
                raise InputTypeException('spatialReference argument not passed, and input dictionary shape field %s does not have a spatialReference attribute' % field)

    if makeTable:
        # Create modifiable table. (Do not write to actual output until end of method).
        if featureClass:
            result = arcpy.CreateFeatureclass_management(os.path.split(modifyTable)[0],os.path.split(modifyTable)[1],geometry_type = featureClassType, spatial_reference = spatialReference)
        else:
            result = arcpy.CreateTable_management(os.path.split(modifyTable)[0],os.path.split(modifyTable)[1])

        modifyTable = str(result) # Get the actual path to the output, as the in_memory output might change depending on environment.

    # Get describe object for output table.
    describe = arcpy.Describe(modifyTable)

    unwritable_fields = list_unwritable_fields(output_table, describe_object = describe)

    # Map fields to their output counterpart:
    new_shape_name = ''
    new_shape_field = ''
    if featureClass and hasattr(describe,'shapeFieldName'):
        new_shape_name = describe.shapeFieldName
        new_shape_field = new_shape_name + orig_shape_suffix

    for field in dictionaryFieldMappings:
        if re.findall(shapeIdentification,field):
            dictionaryFieldMappings[field] = new_shape_field

        elif re.findall('^' + orig_shape_name, field):
                new_field = re.sub('^' + orig_shape_name, new_shape_name, field)
                dictionaryFieldMappings[field] = new_field

        elif re.findall(oidIdentification,field):
            if hasattr(describe,'hasOID') and describe.hasOID:
                dictionaryFieldMappings[field] = describe.OIDFieldName

        # Add more mapping if applicable.

    # Rename fields in dictionary and dictionaryFrame to match output table convensions:
    dictionaryFrame = {dictionaryFieldMappings[k]:v for k,v in dictionaryFrame.items() if k in dictionaryFieldMappings}
    dictionaryFields = list(dictionaryFieldMappings.values())

    if method == 'update':
        for d in dictionaryFieldMappings.values():
            if d in unwritable_fields:
                raise UnwritableFieldException('Update method on field type %s is not allowed.' % d)

    if makeTable:
        # Add verified fields to newly created table.
        # Loop through key/value pairs and create fields according to the contents
        # of the first item in the dictionary. Default field type is text if
        # nothing else is found.
        for k,v in dictionaryFrame.items():
            fieldType = 'TEXT'
            length = max([50,len(str(v))])

            if re.findall(shapeIdentification,k):
                continue #Skip create field if shape.
            elif re.findall(oidIdentification,k):
                continue #Skip create field if objectid.
            elif k == 'GLOBALID':
                fieldType = 'GUID'
            elif isinstance(v,int):
                fieldType = 'LONG'
            elif isinstance(v,float):
                fieldType = 'DOUBLE'
            elif isinstance(v,datetime.datetime):
                fieldType = 'DATE'

            try:
                arcpy.AddField_management(modifyTable,k,fieldType,field_length = length)
            except arcpy.ExecuteError:
                raise FieldException('Failed to create field %s of type %s in table %s' % (k,fieldType,table))

    # Double check output fields with dictionary keys:
    tableFieldNames = [field.name for field in arcpy.ListFields(modifyTable)]

    for field in dictionaryFieldMappings.values():
        if not field in tableFieldNames:
            if not re.findall(shapeIdentification,field) or not re.findall(shapeIdentification,field)[0][0] in tableFieldNames:
                raise MissingFieldException('Dictionary field %s is not present in table %s.' % (field,output_table))

    # Remap fields in dictionary:
    dict2 = []
    for d in dictionary:
        dict2 += [{dictionaryFieldMappings[k]:v for k,v in d.items() if k in dictionaryFieldMappings}]
    dictionary = dict2

    if method in ['update', 'delete']:
        # Reset dictionaryKey as it may have recieved a new valuewhen dictionary keys were remapped to match output table.
        if dictionaryKey in dictionaryFieldMappings:
            dictionaryKey = dictionaryFieldMappings[dictionaryKey]
        if tableKey in dictionaryFieldMappings:
            tableKey = dictionaryFieldMappings[tableKey]

        if not tableKey in dictionaryFieldMappings.values():
            raise FieldException('tableKey is not part of table')

    ### Done handling fields ###

    ### Perform table operations ###
    operationCount = 0

    with arcpy.da.Editor(workspace) as edit:
        # Modify table:
        if method == 'insert':
            with arcpy.da.InsertCursor(modifyTable,dictionaryFields) as cursor:
                for d in dictionary:
                    values = [d[key] for key in cursor.fields]
                    operationCount += 1
                    cursor.insertRow(values)

        elif method == 'update':
            with arcpy.da.UpdateCursor(modifyTable,dictionaryFields) as cursor:
                for row in cursor:
                    t = dict(zip(dictionaryFields,row))
                    for d in dictionary:
                        if t[tableKey] == d[dictionaryKey]:
                            operationCount += 1
                            cursor.updateRow([d[key] for key in cursor.fields])

        elif method == 'delete':
            with arcpy.da.UpdateCursor(modifyTable,dictionaryFields) as cursor:
                for row in cursor:
                    t = dict(zip(dictionaryFields,row))
                    for d in dictionary:
                        if t[tableKey] == d[dictionaryKey]:
                            operationCount += 1
                            cursor.deleteRow()
    ### Done performing table operations ###

    # Check existence of output:
    if makeTable:
        if arcpy.Exists(output_table) and overwriteExistingOutput:
            arcpy.Delete_management(output_table)

        # Copy temp to final location:
        if featureClass:
            arcpy.CopyFeatures_management(modifyTable,output_table)
        else:
            arcpy.CopyRows_management(modifyTable,output_table)

        arcpy.Delete_management(modifyTable)

    return operationCount

def tableToDict(table,sqlQuery = '', keyField = None, groupBy = None, fields = [],field_case = '', ordered = False):
    '''
    Method for creating a dictionary or a list from a table. Default to
    list(dict(),dict(),...). If keyField is passed, the method will return
    dict(dict(),dict(),...) with the values of keyField

    If table is a feature class and fields is empty, the SHAPE@ token is used
    to return the entire geometry.

    Input
          table           str     Path to the table that is converted to a
                                  python dictionary.
          sqlQuery        str     SQL query to perform a selection of the data
                                  within the table.
          keyField        str     Name of column containing non-empty, unique
                                  values identifying each row. Output is a
                                  dictionary with the contents of keyField as
                                  keys.
          groupBy         str     Name of column containing non-unique values.
                                  Output is a dictionary with the contents of
                                  groupBy as keys containing lists of
                                  dictionaries for each object matching the
                                  group.
          fields          list    List of field names that should be included
                                  in dictionary. Default gets all fields.
          field_case      str     Indicate if the dictionary field names
                                  should be forced "upper" or "lower" case.
          ordered         bool    Specifies if output is dict (False) or
                                  OrderedDict (True) with the same row order and
                                  field order as in the table.

    Output
          output          Default:          [{},{},...]
                          keyField:         {{},{},...}
                          groupBy:          {[{},{},...],[{},{},...],...}

    Feature:
        If field name "SHAPE" is specified, will append with @ to return entire shape.
        If field name "OBJECTID" is specified, will convert to the dataset-specific objectid field name.
    '''

    arcpy.env.overwriteOutput = overwriteExistingOutput

    output = list()

    if keyField and groupBy:
        Exception('Method takes either keyField or groupBy, not both.')

    if ordered:
        dict_func = OrderedDict
    else:
        dict_func = dict

    if keyField or groupBy:
        output = dict_func()

    if keyField:
        #Check if contents of field is unique:
        uniqueList = []
        with arcpy.da.SearchCursor(table,keyField,where_clause = sqlQuery) as cursor:
            for row in cursor:
                uniqueList += row
        if not len(set(uniqueList)) == len(uniqueList):
            Exception('When keyField is used as input, the column needs to have unique values. To group rows by the contents of a column, use groupBy.')

    if keyField and field_case:
        if field_case == 'upper':
            keyField = keyField.upper()
        elif field_case == 'lower':
            keyField = keyField.lower()

    if groupBy and field_case:
        if field_case == 'upper':
            groupBy = groupBy.upper()
        elif field_case == 'lower':
            groupBy = groupBy.lower()

    if fields:
        if isinstance(fields,str):
            fields = [fields]
    else:
        fields = [field.name for field in arcpy.ListFields(table)]
        for i in range(len(fields)):
            if re.findall(shapeIdentification, fields[i]):
                fields[i] = fields[i] + '@' #Add @ to extract entire shape, not just simplyfied.
                break


# Removed following lines of code. Tool should not overwrite user input field names.
# This should be resolved outside of the tool in the users controll.
##        for index,field in enumerate(fields):
##            if field.lower() == 'shape':
##                fields[index] = field + '@'
##            if field.lower() == 'objectid':
##                desc = arcpy.Describe(table)
##                fields[index] = desc.OIDFieldName

    if keyField not in fields:
        Exception('keyField must be part of fields.')

    with arcpy.da.SearchCursor(table,fields,where_clause = sqlQuery) as cursor:
        for row in cursor:

            case_fields = fields

            if field_case == 'upper':
                case_fields = [f.upper() for f in fields]
            elif field_case == 'lower':
                case_fields = [f.lower() for f in fields]

            dictRow = dict_func(zip(case_fields,row))

            if keyField:
                output[dictRow[keyField]] = dictRow
            elif groupBy:
                if not dictRow[groupBy] in output:
                    output[dictRow[groupBy]] = []
                output[dictRow[groupBy]] += [dictRow]
            else:
                output += [dictRow]

    return output

def list_unwritable_fields(table, describe_object = None):
    '''
    Some operations write to fields, some fields are unwritable. This methods
    lists these fields for a given table or feature class.
    '''

    if not describe_object:
        desc = arcpy.Describe(table)
    else:
        desc = describe_object

    unwritable_fields = []
    if desc.hasOID:
        unwritable_fields += [desc.OIDFieldName]

    if desc.hasGlobalID:
        unwritable_fields += [desc.globalIDFieldName]

    return unwritable_fields

def create_filled_contours(raster,output_feature_class,explicit_contour_list,create_complete_polygons = False,raster_edge_crop_distance = 10):

    '''
    Method for creating filled contours for a specified list of contours.

    NB: Method will only work if the DEM is +1 contour higher in elevation than
    values in the explicit_contour_list.

    Input
          raster                raster  Raster dataset for which the values are
                                        calculated.
          output_feature_class  f.class The feature class to store the output
                                        polygons.
          explicit_contour_list list/float    A list containing the specific levels of
                                        every contour or a value for a single contour.

    '''

    if not isinstance(explicit_contour_list,list):
        explicit_contour_list = [explicit_contour_list]

    # We want an immutable list, so we convert to a tuple:
    explicit_contour_list = tuple(explicit_contour_list)

    # Add an additional explicit_contour to list. The additional contour helps
    # with creating the polygons. The additional contour is +1 of the regular
    # contour intervals over the topmost contour.
    regular_delta = Counter([j-i for i, j in zip(explicit_contour_list[:-1], explicit_contour_list[1:])]).most_common(1)[0][0]

    explicit_contour_list = explicit_contour_list + (explicit_contour_list[-1]+regular_delta,)

    contour_line = r'in_memory\arctools_contour_line'
    fishnet_line= r'in_memory\arctools_fishnet_line'
    polygons_raw = r'in_memory\polygons_raw'
    polygon_raster_mean = r'in_memory\polygon_raster_mean'
    polygons = r'in_memory\polygons'
    contour_merge_line = r'in_memory\arctools_contour_merge_line'
    contour_merge_line_buffer = r'in_memory\contour_merge_line_buffer'
    buffer_centroid = r'in_memory\buffer_centroid'
    level_join_polygons = r'in_memory\arctools_level_join_polygons'
    level_lyr = 'level_lyr'


#### Debug storage:
##    contour_line = r'M:\GIS_Data\Hydrology\Projects\Reservoir_profile_builder\data.gdb\arctools_contour_line'
##    fishnet_line= r'M:\GIS_Data\Hydrology\Projects\Reservoir_profile_builder\data.gdb\arctools_fishnet_line'
##    polygons_raw = r'M:\GIS_Data\Hydrology\Projects\Reservoir_profile_builder\data.gdb\polygons_raw'
##    polygon_raster_mean = r'M:\GIS_Data\Hydrology\Projects\Reservoir_profile_builder\data.gdb\polygon_raster_mean'
##    polygons = r'M:\GIS_Data\Hydrology\Projects\Reservoir_profile_builder\data.gdb\polygons'
##    contour_merge_line = r'M:\GIS_Data\Hydrology\Projects\Reservoir_profile_builder\data.gdb\arctools_contour_merge_line'
##    contour_merge_line_buffer = r'M:\GIS_Data\Hydrology\Projects\Reservoir_profile_builder\data.gdb\contour_merge_line_buffer'
##    buffer_centroid = r'M:\GIS_Data\Hydrology\Projects\Reservoir_profile_builder\data.gdb\buffer_centroid'
##    level_join_polygons = r'M:\GIS_Data\Hydrology\Projects\Reservoir_profile_builder\data.gdb\arctools_level_join_polygons'
####


    print('Create contours')
    arcpy.CheckOutExtension('Spatial')
    arcpy.sa.ContourWithBarriers(raster,contour_line,explicit_only = True, in_explicit_contours = explicit_contour_list)
    arcpy.CheckInExtension('Spatial')


    print('Create fishnet')
    desc = arcpy.Describe(raster)
    XMin = desc.extent.XMin+desc.meanCellWidth
    XMax = desc.extent.XMax-desc.meanCellWidth
    YMin = desc.extent.YMin+desc.meanCellHeight
    YMax = desc.extent.YMax-desc.meanCellHeight
    arcpy.env.overwriteOutput = True
    arcpy.CreateFishnet_management(out_feature_class=fishnet_line, origin_coord='%0.4f %0.4f' % (XMin,YMin), y_axis_coord='%0.4f %0.4f' % (XMin,YMin+10), cell_width="0", cell_height="0", number_rows="1", number_columns="1", corner_coord='%0.4f %0.4f' % (XMax,YMax), labels="LABELS", template='%0.4f %0.4f %0.4f %0.4f' % (XMin,YMin,XMax,YMax), geometry_type="POLYLINE")
    arcpy.DefineProjection_management(fishnet_line,desc.spatialReference)

    print('Merge')
    arcpy.env.overwriteOutput = True
    arcpy.Merge_management(inputs=';'.join([contour_line,fishnet_line]), output=contour_merge_line, field_mappings="""Contour "Contour" true true false 8 Double 0 0 ,First,#,%(contour_line)s,Contour,-1,-1;Type "Type" true true false 4 Long 0 0 ,First,#,%(contour_line)s,Type,-1,-1;;Shape_Length "Shape_Length" false true true 8 Double 0 0 ,First,#,%(contour_line)s,Shape_Length,-1,-1,%(fishnet_line)s,Shape_Length,-1,-1""" % {'fishnet_line':fishnet_line,'contour_line':contour_line})

    print('Feature to polygon')
    arcpy.FeatureToPolygon_management(in_features=contour_merge_line, out_feature_class=polygons_raw, cluster_tolerance="", attributes="ATTRIBUTES", label_features="")

    arcpy.AddField_management(polygons_raw,'Contour','DOUBLE')

    poly_oid_name = arcpy.Describe(polygons_raw).OIDFieldName


    # Get the average elevation of each polygon, map these to their
    # corresponding contour elevation, and use the OBJECTID to map these back to
    # the polygon data. This process is 50x times faster than Spatial Join.
    print('Zonal statistics')
    start = time.clock()
    arcpy.CheckOutExtension('Spatial')
    arcpy.gp.ZonalStatisticsAsTable_sa(polygons_raw, poly_oid_name, raster, polygon_raster_mean, "DATA", "MEAN")
    arcpy.CheckInExtension('Spatial')
    stop = time.clock()

    table_oid_name = arcpy.Describe(polygon_raster_mean).OIDFieldName

    forreign_key = poly_oid_name + '_'
    table_dict = tableToDict(polygon_raster_mean,keyField = forreign_key) # Create ditionary from table, with keyField as the dictionary keys.

    bottom = explicit_contour_list[:-1]
    top = explicit_contour_list[1:]

    #Reclassify mean raster values to contour values:
    for k in table_dict:
        if table_dict[k]['MEAN'] > explicit_contour_list[-1]:
            table_dict[k]['MEAN'] = explicit_contour_list[-1]
        elif table_dict[k]['MEAN'] < explicit_contour_list[0]:
            table_dict[k]['MEAN'] = explicit_contour_list[0]
        else:
            for b,t in zip(bottom,top):
                if table_dict[k]['MEAN']>=b and table_dict[k]['MEAN']<t:
                    table_dict[k]['MEAN'] = t
                    break

    #Insert contour values to polygon data:
    found_warning = False
    with arcpy.da.UpdateCursor(polygons_raw,[poly_oid_name,'Contour'])as cursor:
        for row in cursor:
            if not row[0] in table_dict:
                row[1] = None #Polygons that where too small to get a raster value from Zonal Statistics. Handled later.
                found_warning = True
            else:
                row[1] = table_dict[row[0]]['MEAN']
            cursor.updateRow(row)

    if found_warning:
        print('WARNING: Some contours were too close together to be handled properly. Check Contour = None in resulting table.')

    print('Homebrew Spatial Join: %0.2f seconds' % (stop-start))
    print('Regular Spatial Join: %0.2f seconds' % 1947)
    print('Improvement: %0.0fx' % (19473/(stop-start)))

    if isinstance(output_feature_class,arcpy.Geometry):
        return arcpy.CopyFeatures_management(polygons_raw,arcpy.Geometry())
    elif isinstance(output_feature_class,list):
        return tableToDict(polygons_raw) # Will pass output as a list when no keyField is passed as an argument.
    else:
        arcpy.CopyFeatures_management(polygons_raw,output_feature_class)

def changeFieldOrder(table,newTable,orderedFieldList):
    '''
    This method can reorder the fields in a table. All fields in
    orderedFieldList must exist in the table, and the method then changes the
    order of the table fields in accordance with the list.

    orderedFieldList does not have to contain all the fields in the table; the
    fields not specified will be moved to the head of the list.

    Input:
        table               str         path specifying the table or feature
                                        class.
        orderedFieldList    list(str)   names of existing fields in table.

    Output:
        newFieldList        list(str)   new complete list of field names in
                                        table.


    The way to handle this would be to make a new table with the correct fields,
    and copy all the data to the new table with a field mapping.
    '''

    shapeIdentification = '^shape(@\w*)?$'

    desc = arcpy.Describe(table)
    desc.hasM
    desc.hasZ
    desc.shapeType
    desc.featureType

    arcpy.env.overwriteOutput = overwriteExistingOutput

    fields = arcpy.ListFields(table)

    fieldCheck = False
    if isinstance(orderedFieldList[0],arcpy.Field):
        fieldCheck = True

    for of in orderedFieldList:
        if fieldCheck:
            name = of.name
        else:
            name = of
        if not name in [f.name for f in fields]:
            raise Exception('Field %s not found in table %s' % (of.name,table))

    newFields = []
    for of in orderedFieldList:
        if fieldCheck:
            name = of.name
        else:
            name = of
        for f in fields:
            if f.name == name:
                newFields += [f]

    if desc.datatype == u'FeatureClass':
        arcpy.CreateFeatureclass_management(os.path.realpath(newTable),os.path.basename(newTable),geometry_type=desc.shapeType,has_m=desc.hasM,has_z=desc.hasZ,spatial_reference=desc.spatialReference)
    else:
        arcpy.CreateTable_management(os.path.realpath(newTable),os.path.basename(newTable))


    for nf in newFields:
        if not nf.name.lower() == 'objectid':
            arcpy.AddField_management(newTable,nf.name,nf.type,)

    #CONTINUE HERE



def renameFields(table,newTable,fieldMappingDict):
    '''
    Method for batch-renaming fields in a table.

    For easy of coding, this method uses dictToTable and tableToDict in
    sequence, renaming the keys in the dictionary in between the operations.

    Input:
        table               str         path specifying the table or feature
                                        class to rename fields in.
        newTable            str         path specifying the resulting table or
                                        feature class. Can be the same as input
                                        table. In that case, input table is
                                        deleted before write operation.
        fieldMappingDict    dict(str)   dictionary with key/value pairs
                                        representing current/new field names.

    Output:
        newFieldList        list(str)   new complete list of field names in
                                        table.
    '''

    arcpy.env.overwriteOutput = overwriteExistingOutput

    old = tableToDict(table)

    new = []
    for row in old:
        new += [OrderedDict()]
        for k,v in row.items():
            if k in fieldMappingDict:
                k = fieldMappingDict[k]
            new[-1][k] = v

    if overwriteExistingOutput or table == newTable:
        try:
            arcpy.Delete_management(newTable)
        except:
            pass

    dictToTable(new, os.path.split(newTable)[0], os.path.split(newTable)[1], method = 'insert', makeTable = True)



if __name__ == '__main__':
    import sys
    import os
    sys.path = [os.path.dirname(__file__)] + sys.path

    from test import test_arctools
    test_arctools.run()
