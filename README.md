# arctools
Wrapper for making my gis-day easier. Based on ESRI's arcpy module for ArcGIS Desktop.
<br/>
<br/>
Two primary functions:
<ul>
<li><b>tableToDict</b>: Take any database table and convert to a list of dictionaries (or a dictionary of dictionaries!). Supports grouping based on field attributes, and reading of only specific fields.</li>
<li><b>dictToTable</b>: Take any list of dictionaries (or dictionary of dictionaries!) and convert to a database table. Supports insert, update and delete (the two latter based on key fields and keys to match correct entries).</li>
</ul>
