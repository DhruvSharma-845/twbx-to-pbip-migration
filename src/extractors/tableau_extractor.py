"""
Stage 1: Tableau TWBX Extractor

Extracts semantic schema from Tableau workbook files (.twbx and .twb).
"""

import os
import re
import zipfile
import tempfile
from typing import List, Dict, Any, Optional, Tuple
from xml.etree import ElementTree as ET

from ..models.tableau_schema import (
    TableauWorkbook, TableauDatasource, TableauTable, TableauColumn,
    TableauWorksheet, TableauDashboard, TableauDashboardZone,
    TableauFilter, TableauShelf, TableauVisualType, TableauDataType,
    TableauRole, CalculationType
)


class TableauExtractor:
    """
    Extracts semantic schema from Tableau workbook files.
    
    Handles both .twbx (packaged) and .twb (XML) files.
    """
    
    def __init__(self, file_path: str):
        self.file_path = file_path
        self.workbook: Optional[TableauWorkbook] = None
        self._temp_dir: Optional[str] = None
        
    def extract(self) -> TableauWorkbook:
        """
        Extract semantic schema from the Tableau file.
        
        Returns:
            TableauWorkbook containing all extracted metadata.
        """
        if self.file_path.endswith('.twbx'):
            return self._extract_from_twbx()
        elif self.file_path.endswith('.twb'):
            return self._extract_from_twb(self.file_path)
        else:
            raise ValueError(f"Unsupported file type: {self.file_path}")
    
    def _extract_from_twbx(self) -> TableauWorkbook:
        """Extract from packaged workbook (.twbx)."""
        with zipfile.ZipFile(self.file_path, 'r') as zf:
            # Find the .twb file inside the package
            twb_files = [f for f in zf.namelist() if f.endswith('.twb')]
            if not twb_files:
                raise ValueError("No .twb file found in .twbx package")
            
            # Extract to temp directory
            self._temp_dir = tempfile.mkdtemp()
            twb_path = zf.extract(twb_files[0], self._temp_dir)
            
            return self._extract_from_twb(twb_path)
    
    def _extract_from_twb(self, twb_path: str) -> TableauWorkbook:
        """Extract from XML workbook file (.twb)."""
        tree = ET.parse(twb_path)
        root = tree.getroot()
        
        workbook_name = os.path.splitext(os.path.basename(self.file_path))[0]
        workbook = TableauWorkbook(
            name=workbook_name,
            version=root.get('version')
        )
        
        # Extract datasources
        workbook.datasources = self._extract_datasources(root)
        
        # Extract worksheets
        workbook.worksheets = self._extract_worksheets(root)
        
        # Extract dashboards
        workbook.dashboards = self._extract_dashboards(root)
        
        # Extract global parameters
        workbook.parameters = self._extract_parameters(root)
        
        self.workbook = workbook
        return workbook
    
    def _extract_datasources(self, root: ET.Element) -> List[TableauDatasource]:
        """Extract datasource definitions."""
        datasources = []
        
        # Find all datasource elements
        for ds_elem in root.findall('.//datasource'):
            ds_name = ds_elem.get('name', 'Unknown')
            ds_caption = ds_elem.get('caption', ds_name)
            
            # Skip Parameters datasource (handled separately)
            if ds_name == 'Parameters':
                continue
            
            datasource = TableauDatasource(
                name=ds_name,
                caption=ds_caption
            )
            
            # Extract connection info
            connection = ds_elem.find('.//connection')
            if connection is not None:
                datasource.connection_info = {
                    'class': connection.get('class'),
                    'dbname': connection.get('dbname'),
                    'server': connection.get('server'),
                    'port': connection.get('port')
                }
            
            # Extract tables and columns
            datasource.tables = self._extract_tables(ds_elem)
            
            # Extract calculated fields
            datasource.calculated_fields = self._extract_calculated_fields(ds_elem)
            
            datasources.append(datasource)
        
        return datasources
    
    def _extract_tables(self, ds_elem: ET.Element) -> List[TableauTable]:
        """Extract logical tables from a datasource."""
        tables = []
        table_map: Dict[str, TableauTable] = {}
        
        # Look for columns which define the schema
        for col_elem in ds_elem.findall('.//column'):
            col_name = col_elem.get('name', '')
            if not col_name:
                continue
            
            # Clean column name (remove brackets)
            col_name = col_name.strip('[]')
            
            # Determine source table
            parent_name = col_elem.get('parent-name', '')
            if not parent_name:
                # Try to find from semantic-values or other attributes
                parent_name = 'Default'
            else:
                parent_name = parent_name.strip('[]')
            
            # Get or create table
            if parent_name not in table_map:
                table_map[parent_name] = TableauTable(
                    name=parent_name,
                    caption=parent_name
                )
            
            table = table_map[parent_name]
            
            # Create column
            column = self._create_column(col_elem, col_name)
            column.source_table = parent_name
            
            # Skip if it's a calculation (handled separately)
            if col_elem.find('calculation') is not None:
                continue
            
            table.columns.append(column)
        
        # Also look for metadata-records which contain column info
        for metadata in ds_elem.findall('.//metadata-record'):
            if metadata.get('class') == 'column':
                local_name_elem = metadata.find('local-name')
                remote_name_elem = metadata.find('remote-name')
                parent_name_elem = metadata.find('parent-name')
                
                if local_name_elem is not None:
                    col_name = local_name_elem.text or ''
                    col_name = col_name.strip('[]')
                    
                    parent_name = 'Default'
                    if parent_name_elem is not None and parent_name_elem.text:
                        parent_name = parent_name_elem.text.strip('[]')
                    
                    if parent_name not in table_map:
                        table_map[parent_name] = TableauTable(
                            name=parent_name,
                            caption=parent_name
                        )
                    
                    # Check if column already exists
                    existing_cols = [c.name for c in table_map[parent_name].columns]
                    if col_name not in existing_cols:
                        datatype = self._infer_datatype(metadata)
                        column = TableauColumn(
                            name=col_name,
                            caption=remote_name_elem.text if remote_name_elem is not None else col_name,
                            datatype=datatype,
                            source_table=parent_name
                        )
                        table_map[parent_name].columns.append(column)
        
        tables = list(table_map.values())
        
        # If no tables found, create a default placeholder
        if not tables:
            tables.append(TableauTable(
                name='Data',
                caption='Data',
                columns=[
                    TableauColumn(name='Value', caption='Value', datatype=TableauDataType.STRING)
                ]
            ))
        
        return tables
    
    def _create_column(self, col_elem: ET.Element, col_name: str) -> TableauColumn:
        """Create a TableauColumn from an XML element."""
        caption = col_elem.get('caption', col_name)
        
        # Determine data type
        datatype_str = col_elem.get('datatype', 'string')
        datatype = self._map_datatype(datatype_str)
        
        # Determine role
        role_str = col_elem.get('role', 'dimension')
        role = TableauRole.MEASURE if role_str == 'measure' else TableauRole.DIMENSION
        
        # Check for aggregation
        aggregation = col_elem.get('aggregation')
        
        return TableauColumn(
            name=col_name,
            caption=caption,
            datatype=datatype,
            role=role,
            aggregation=aggregation,
            is_hidden=col_elem.get('hidden') == 'true'
        )
    
    def _map_datatype(self, datatype_str: str) -> TableauDataType:
        """Map Tableau datatype string to enum."""
        mapping = {
            'string': TableauDataType.STRING,
            'integer': TableauDataType.INTEGER,
            'real': TableauDataType.REAL,
            'date': TableauDataType.DATE,
            'datetime': TableauDataType.DATETIME,
            'boolean': TableauDataType.BOOLEAN
        }
        return mapping.get(datatype_str.lower(), TableauDataType.STRING)
    
    def _infer_datatype(self, metadata: ET.Element) -> TableauDataType:
        """Infer data type from metadata record."""
        local_type = metadata.find('local-type')
        if local_type is not None and local_type.text:
            return self._map_datatype(local_type.text)
        return TableauDataType.STRING
    
    def _extract_calculated_fields(self, ds_elem: ET.Element) -> List[TableauColumn]:
        """Extract calculated fields from a datasource."""
        calc_fields = []
        
        for col_elem in ds_elem.findall('.//column'):
            calc_elem = col_elem.find('calculation')
            if calc_elem is None:
                continue
            
            col_name = col_elem.get('name', '').strip('[]')
            if not col_name:
                continue
            
            formula = calc_elem.get('formula', '')
            calc_type = self._classify_calculation(formula)
            
            calc_field = TableauColumn(
                name=col_name,
                caption=col_elem.get('caption', col_name),
                datatype=self._map_datatype(col_elem.get('datatype', 'string')),
                role=TableauRole.MEASURE if col_elem.get('role') == 'measure' else TableauRole.DIMENSION,
                calculation=formula,
                calculation_type=calc_type
            )
            
            calc_fields.append(calc_field)
        
        return calc_fields
    
    def _classify_calculation(self, formula: str) -> CalculationType:
        """Classify the type of Tableau calculation."""
        if not formula:
            return CalculationType.BASIC
        
        formula_upper = formula.upper()
        
        # Check for LOD expressions
        if any(lod in formula_upper for lod in ['FIXED', 'INCLUDE', 'EXCLUDE']):
            if '{' in formula and '}' in formula:
                return CalculationType.LOD
        
        # Check for table calculations
        table_calc_funcs = [
            'LOOKUP', 'PREVIOUS_VALUE', 'FIRST', 'LAST', 'INDEX',
            'RUNNING_SUM', 'RUNNING_AVG', 'RUNNING_COUNT', 'RUNNING_MIN', 'RUNNING_MAX',
            'WINDOW_SUM', 'WINDOW_AVG', 'WINDOW_MIN', 'WINDOW_MAX', 'WINDOW_COUNT',
            'RANK', 'RANK_DENSE', 'RANK_MODIFIED', 'RANK_PERCENTILE', 'RANK_UNIQUE',
            'SIZE', 'TOTAL'
        ]
        if any(func in formula_upper for func in table_calc_funcs):
            return CalculationType.TABLE_CALC
        
        return CalculationType.BASIC
    
    def _extract_worksheets(self, root: ET.Element) -> List[TableauWorksheet]:
        """Extract worksheet definitions."""
        worksheets = []
        
        for ws_elem in root.findall('.//worksheet'):
            ws_name = ws_elem.get('name', 'Untitled')
            
            worksheet = TableauWorksheet(name=ws_name)
            
            # Extract datasource reference
            datasources_elem = ws_elem.find('.//datasources')
            if datasources_elem is not None:
                ds_elem = datasources_elem.find('datasource')
                if ds_elem is not None:
                    worksheet.datasource_name = ds_elem.get('name') or ds_elem.get('caption')
            
            # Extract visual type from mark type
            worksheet.visual_type, worksheet.mark_type = self._infer_visual_type(ws_elem)
            
            # Check for dual axis
            worksheet.is_dual_axis = self._check_dual_axis(ws_elem)
            
            # Extract shelves (rows, columns, marks)
            worksheet.shelves = self._extract_shelves(ws_elem)
            
            # Extract field references
            worksheet.rows, worksheet.columns, worksheet.marks = self._extract_field_references(ws_elem)
            
            # Extract filters
            worksheet.filters = self._extract_worksheet_filters(ws_elem)
            
            worksheets.append(worksheet)
        
        return worksheets
    
    def _infer_visual_type(self, ws_elem: ET.Element) -> Tuple[TableauVisualType, Optional[str]]:
        """Infer the visual type from worksheet element."""
        # Look for pane element with mark type
        for pane in ws_elem.findall('.//pane'):
            for mark in pane.findall('mark'):
                mark_class = mark.get('class')
                if mark_class:
                    return self._map_mark_type(mark_class), mark_class
        
        # Try style element
        style = ws_elem.find('.//style-rule[@element="mark"]')
        if style is not None:
            mark_type = style.find('.//format[@attr="mark"]')
            if mark_type is not None:
                return self._map_mark_type(mark_type.get('value', '')), mark_type.get('value')
        
        return TableauVisualType.UNKNOWN, None
    
    def _map_mark_type(self, mark_type: str) -> TableauVisualType:
        """Map Tableau mark type to visual type."""
        if not mark_type:
            return TableauVisualType.UNKNOWN
        
        mark_type = mark_type.lower()
        mapping = {
            'bar': TableauVisualType.BAR,
            'line': TableauVisualType.LINE,
            'area': TableauVisualType.AREA,
            'pie': TableauVisualType.PIE,
            'circle': TableauVisualType.SCATTER,
            'shape': TableauVisualType.SCATTER,
            'text': TableauVisualType.TEXT_TABLE,
            'square': TableauVisualType.HEATMAP,
            'polygon': TableauVisualType.MAP,
            'gantt': TableauVisualType.GANTT,
            'ganttbar': TableauVisualType.GANTT
        }
        return mapping.get(mark_type, TableauVisualType.UNKNOWN)
    
    def _check_dual_axis(self, ws_elem: ET.Element) -> bool:
        """Check if worksheet uses dual axis."""
        # Count axes
        axes = ws_elem.findall('.//axis')
        row_axes = [a for a in axes if 'row' in str(a.get('type', '')).lower()]
        col_axes = [a for a in axes if 'col' in str(a.get('type', '')).lower()]
        
        return len(row_axes) > 1 or len(col_axes) > 1
    
    def _extract_shelves(self, ws_elem: ET.Element) -> List[TableauShelf]:
        """Extract shelf definitions (rows, columns, marks)."""
        shelves = []
        
        # Row shelf
        rows_elem = ws_elem.find('.//rows')
        if rows_elem is not None and rows_elem.text:
            shelves.append(TableauShelf(
                shelf_type='rows',
                fields=self._parse_shelf_fields(rows_elem.text)
            ))
        
        # Column shelf
        cols_elem = ws_elem.find('.//cols')
        if cols_elem is not None and cols_elem.text:
            shelves.append(TableauShelf(
                shelf_type='columns',
                fields=self._parse_shelf_fields(cols_elem.text)
            ))
        
        # Mark encodings (color, size, label, etc.)
        for encoding_elem in ws_elem.findall('.//encoding'):
            enc_type = encoding_elem.get('type', 'unknown')
            field_name = encoding_elem.get('column', '')
            if field_name:
                shelves.append(TableauShelf(
                    shelf_type=enc_type,
                    fields=[{'name': field_name.strip('[]')}]
                ))
        
        return shelves
    
    def _parse_shelf_fields(self, shelf_text: str) -> List[Dict[str, Any]]:
        """Parse field references from shelf text."""
        fields = []
        
        # Parse field references like [Field Name] or AGG([Field Name])
        pattern = r'\[([^\]]+)\]'
        matches = re.findall(pattern, shelf_text)
        
        for match in matches:
            field = {'name': match}
            
            # Check for aggregation
            agg_pattern = rf'(\w+)\(\[{re.escape(match)}\]\)'
            agg_match = re.search(agg_pattern, shelf_text)
            if agg_match:
                field['aggregation'] = agg_match.group(1)
            
            fields.append(field)
        
        return fields
    
    def _extract_field_references(self, ws_elem: ET.Element) -> Tuple[List[str], List[str], Dict[str, List[str]]]:
        """Extract simplified field references."""
        rows = []
        cols = []
        marks: Dict[str, List[str]] = {}
        
        # Rows
        rows_elem = ws_elem.find('.//rows')
        if rows_elem is not None and rows_elem.text:
            rows = re.findall(r'\[([^\]]+)\]', rows_elem.text)
        
        # Columns
        cols_elem = ws_elem.find('.//cols')
        if cols_elem is not None and cols_elem.text:
            cols = re.findall(r'\[([^\]]+)\]', cols_elem.text)
        
        # Mark encodings
        for encoding_elem in ws_elem.findall('.//encoding'):
            enc_type = encoding_elem.get('type', 'unknown')
            field_name = encoding_elem.get('column', '').strip('[]')
            if field_name:
                if enc_type not in marks:
                    marks[enc_type] = []
                marks[enc_type].append(field_name)
        
        return rows, cols, marks
    
    def _extract_worksheet_filters(self, ws_elem: ET.Element) -> List[TableauFilter]:
        """Extract filters from a worksheet."""
        filters = []
        
        for filter_elem in ws_elem.findall('.//filter'):
            field_name = filter_elem.get('column', '').strip('[]')
            filter_type = filter_elem.get('class', 'categorical')
            
            if not field_name:
                continue
            
            filter_obj = TableauFilter(
                field_name=field_name,
                filter_type=filter_type
            )
            
            # Extract filter values
            for member in filter_elem.findall('.//groupmember'):
                filter_obj.values.append(member.get('member'))
            
            filters.append(filter_obj)
        
        return filters
    
    def _extract_dashboards(self, root: ET.Element) -> List[TableauDashboard]:
        """Extract dashboard definitions."""
        dashboards = []
        
        for db_elem in root.findall('.//dashboard'):
            db_name = db_elem.get('name', 'Dashboard')
            
            dashboard = TableauDashboard(name=db_name)
            
            # Extract size
            size_elem = db_elem.find('size')
            if size_elem is not None:
                dashboard.width = int(size_elem.get('maxwidth', size_elem.get('width', '1280')))
                dashboard.height = int(size_elem.get('maxheight', size_elem.get('height', '800')))
            
            # Extract zones
            dashboard.zones = self._extract_zones(db_elem)
            
            dashboards.append(dashboard)
        
        return dashboards
    
    def _extract_zones(self, db_elem: ET.Element) -> List[TableauDashboardZone]:
        """Extract zones from a dashboard."""
        zones = []
        
        for zone_elem in db_elem.findall('.//zone'):
            zone_id = zone_elem.get('id', str(len(zones)))
            zone_type = zone_elem.get('type', 'blank')
            
            # Try to determine zone type from class or type-v2
            if zone_elem.get('type-v2') == 'viz':
                zone_type = 'viz'
            elif zone_elem.get('param'):
                zone_type = 'filter'
            
            zone = TableauDashboardZone(
                zone_id=zone_id,
                zone_type=zone_type
            )
            
            # Get worksheet reference
            zone.worksheet_name = zone_elem.get('name')
            
            # Get position
            try:
                zone.x = int(zone_elem.get('x', 0))
                zone.y = int(zone_elem.get('y', 0))
                zone.width = int(zone_elem.get('w', 100))
                zone.height = int(zone_elem.get('h', 100))
            except (ValueError, TypeError):
                pass
            
            zones.append(zone)
        
        return zones
    
    def _extract_parameters(self, root: ET.Element) -> List[Dict[str, Any]]:
        """Extract global parameters from the workbook."""
        parameters = []
        
        # Find Parameters datasource
        params_ds = root.find('.//datasource[@name="Parameters"]')
        if params_ds is None:
            return parameters
        
        for param_elem in params_ds.findall('.//column'):
            param_name = param_elem.get('name', '').strip('[]')
            if not param_name:
                continue
            
            param = {
                'name': param_name,
                'caption': param_elem.get('caption', param_name),
                'datatype': param_elem.get('datatype', 'string'),
                'role': param_elem.get('role', 'dimension')
            }
            
            # Get default value
            calc_elem = param_elem.find('calculation')
            if calc_elem is not None:
                param['default_value'] = calc_elem.get('formula', '')
            
            parameters.append(param)
        
        return parameters
    
    def cleanup(self):
        """Clean up temporary files."""
        if self._temp_dir and os.path.exists(self._temp_dir):
            import shutil
            shutil.rmtree(self._temp_dir)
