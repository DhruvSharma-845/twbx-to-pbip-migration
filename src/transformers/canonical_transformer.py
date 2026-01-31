"""
Stage 2: Canonical BI Schema Generator

Transforms Tableau extracted schema into platform-agnostic canonical schema.
"""

import uuid
import hashlib
from typing import List, Dict, Any, Optional

from ..models.tableau_schema import (
    TableauWorkbook, TableauDatasource, TableauWorksheet, TableauDashboard,
    TableauColumn, TableauVisualType, TableauDataType, TableauRole,
    CalculationType
)
from ..models.canonical_schema import (
    CanonicalReport, CanonicalDataset, CanonicalTable, CanonicalColumn,
    CanonicalMeasure, CanonicalRelationship, CanonicalPage, CanonicalVisual,
    CanonicalFilter, VisualEncoding, DataType, VisualType, ConfidenceLevel,
    AggregationType
)
from .calculation_translator import CalculationTranslator


class CanonicalTransformer:
    """
    Transforms Tableau workbook schema to canonical BI schema.
    
    This is Stage 2 of the migration pipeline, producing a 
    platform-agnostic intermediate representation.
    """
    
    # Visual type mapping
    VISUAL_TYPE_MAP = {
        TableauVisualType.BAR: VisualType.CLUSTERED_BAR,
        TableauVisualType.LINE: VisualType.LINE_CHART,
        TableauVisualType.AREA: VisualType.AREA_CHART,
        TableauVisualType.PIE: VisualType.PIE_CHART,
        TableauVisualType.SCATTER: VisualType.SCATTER,
        TableauVisualType.TEXT_TABLE: VisualType.TABLE,
        TableauVisualType.CROSSTAB: VisualType.MATRIX,
        TableauVisualType.MAP: VisualType.MAP,
        TableauVisualType.TREEMAP: VisualType.TREEMAP,
        TableauVisualType.HEATMAP: VisualType.MATRIX,
        TableauVisualType.HISTOGRAM: VisualType.CLUSTERED_BAR,
        TableauVisualType.GANTT: VisualType.BAR_CHART,
        TableauVisualType.BULLET: VisualType.CLUSTERED_BAR,
        TableauVisualType.PACKED_BUBBLE: VisualType.SCATTER,
        TableauVisualType.DUAL_AXIS: VisualType.LINE_CHART,  # Will be flagged
        TableauVisualType.COMBINED_AXIS: VisualType.LINE_CHART,
        TableauVisualType.UNKNOWN: VisualType.TABLE,
    }
    
    # Data type mapping
    DATA_TYPE_MAP = {
        TableauDataType.STRING: DataType.STRING,
        TableauDataType.INTEGER: DataType.INTEGER,
        TableauDataType.REAL: DataType.DOUBLE,
        TableauDataType.DATE: DataType.DATE,
        TableauDataType.DATETIME: DataType.DATETIME,
        TableauDataType.BOOLEAN: DataType.BOOLEAN,
        TableauDataType.UNKNOWN: DataType.STRING,
    }
    
    def __init__(self):
        self.warnings: List[str] = []
        self.unsupported_features: Dict[str, List[str]] = {
            'lod_expressions': [],
            'table_calculations': [],
            'dual_axis_charts': [],
            'other': []
        }
    
    def transform(self, workbook: TableauWorkbook) -> CanonicalReport:
        """
        Transform a Tableau workbook to canonical schema.
        
        Args:
            workbook: Parsed Tableau workbook
            
        Returns:
            CanonicalReport with platform-agnostic representation
        """
        # Create dataset from datasources
        dataset = self._create_dataset(workbook)
        
        # Create pages from dashboards (or worksheets if no dashboards)
        pages = self._create_pages(workbook, dataset)
        
        # Build the report
        report = CanonicalReport(
            name=workbook.name,
            dataset=dataset,
            pages=pages,
            source_file=workbook.name,
            migration_warnings=self.warnings,
            unsupported_features=self.unsupported_features
        )
        
        return report
    
    def _create_dataset(self, workbook: TableauWorkbook) -> CanonicalDataset:
        """Create canonical dataset from Tableau datasources."""
        dataset = CanonicalDataset(
            name=f"{workbook.name}_Model",
            description=f"Semantic model migrated from Tableau workbook: {workbook.name}"
        )
        
        # Process each datasource
        for ds in workbook.datasources:
            tables, measures = self._process_datasource(ds)
            dataset.tables.extend(tables)
        
        # If no tables, create a placeholder
        if not dataset.tables:
            dataset.tables.append(self._create_placeholder_table(workbook))
        
        return dataset
    
    def _process_datasource(self, datasource: TableauDatasource) -> tuple:
        """Process a single Tableau datasource into tables and measures."""
        tables = []
        all_measures = []
        
        for tableau_table in datasource.tables:
            canonical_table = self._convert_table(tableau_table, datasource)
            tables.append(canonical_table)
        
        # Process calculated fields into measures
        for calc_field in datasource.calculated_fields:
            measure = self._convert_calculated_field(calc_field, datasource)
            if measure:
                # Add measure to the first table or create a measures table
                if tables:
                    tables[0].measures.append(measure)
                all_measures.append(measure)
        
        return tables, all_measures
    
    def _convert_table(self, tableau_table: TableauColumn, datasource: TableauDatasource) -> CanonicalTable:
        """Convert a Tableau table to canonical table."""
        canonical_table = CanonicalTable(
            name=self._sanitize_name(tableau_table.name),
            display_name=tableau_table.display_name,
            source_table=tableau_table.name
        )
        
        for col in tableau_table.columns:
            canonical_col = CanonicalColumn(
                name=self._sanitize_name(col.name),
                display_name=col.display_name,
                data_type=self.DATA_TYPE_MAP.get(col.datatype, DataType.STRING),
                source_column=col.name
            )
            canonical_table.columns.append(canonical_col)
        
        # Ensure table has at least one column
        if not canonical_table.columns:
            canonical_table.columns.append(CanonicalColumn(
                name="Placeholder",
                display_name="Placeholder",
                data_type=DataType.STRING
            ))
        
        return canonical_table
    
    def _convert_calculated_field(self, calc_field: TableauColumn, datasource: TableauDatasource) -> Optional[CanonicalMeasure]:
        """Convert a Tableau calculated field to a canonical measure."""
        if not calc_field.calculation:
            return None
        
        # Get the table name for field qualification
        table_name = datasource.tables[0].name if datasource.tables else "Data"
        
        translator = CalculationTranslator(table_name=self._sanitize_name(table_name))
        dax_expr, confidence, unsupported_reason = translator.translate(calc_field.calculation)
        
        # Track unsupported features
        if calc_field.calculation_type == CalculationType.LOD:
            self.unsupported_features['lod_expressions'].append(calc_field.name)
        elif calc_field.calculation_type == CalculationType.TABLE_CALC:
            self.unsupported_features['table_calculations'].append(calc_field.name)
        
        measure = CanonicalMeasure(
            name=self._sanitize_name(calc_field.name),
            display_name=calc_field.display_name,
            expression=calc_field.calculation,
            dax_expression=dax_expr,
            confidence=confidence,
            aggregation=translator.get_aggregation_type(calc_field.calculation),
            unsupported_reason=unsupported_reason
        )
        
        return measure
    
    def _create_placeholder_table(self, workbook: TableauWorkbook) -> CanonicalTable:
        """Create a placeholder table when no datasources are found."""
        # Collect all field references from worksheets
        fields_seen = set()
        
        for ws in workbook.worksheets:
            fields_seen.update(ws.rows)
            fields_seen.update(ws.columns)
            for mark_fields in ws.marks.values():
                fields_seen.update(mark_fields)
        
        # Create columns from field references
        columns = []
        for field_name in fields_seen:
            columns.append(CanonicalColumn(
                name=self._sanitize_name(field_name),
                display_name=field_name,
                data_type=DataType.STRING
            ))
        
        # Ensure at least one column
        if not columns:
            columns.append(CanonicalColumn(
                name="Value",
                display_name="Value",
                data_type=DataType.STRING
            ))
        
        return CanonicalTable(
            name="Data",
            display_name="Data",
            columns=columns,
            description="Placeholder table - no datasource metadata available"
        )
    
    def _create_pages(self, workbook: TableauWorkbook, dataset: CanonicalDataset) -> List[CanonicalPage]:
        """Create canonical pages from Tableau dashboards or worksheets."""
        pages = []
        
        if workbook.dashboards:
            # Create a page for each dashboard
            for i, dashboard in enumerate(workbook.dashboards):
                page = self._convert_dashboard(dashboard, workbook, dataset, i)
                pages.append(page)
        else:
            # Create pages from worksheets directly
            for i, worksheet in enumerate(workbook.worksheets):
                page = self._create_page_from_worksheet(worksheet, dataset, i)
                pages.append(page)
        
        # Ensure at least one page
        if not pages:
            pages.append(CanonicalPage(
                id=self._generate_page_id("Page1"),
                name="Page1",
                display_name="Page 1",
                width=1280,
                height=720
            ))
        
        return pages
    
    def _convert_dashboard(self, dashboard: TableauDashboard, workbook: TableauWorkbook, 
                          dataset: CanonicalDataset, index: int) -> CanonicalPage:
        """Convert a Tableau dashboard to a canonical page."""
        page_id = self._generate_page_id(dashboard.name)
        
        page = CanonicalPage(
            id=page_id,
            name=self._sanitize_name(dashboard.name),
            display_name=dashboard.title or dashboard.name,
            width=min(dashboard.width, 1920),
            height=min(dashboard.height, 1080),
            source_dashboard=dashboard.name
        )
        
        # Convert zones to visuals
        for zone in dashboard.zones:
            if zone.zone_type == 'viz' and zone.worksheet_name:
                # Find the worksheet
                worksheet = workbook.get_worksheet_by_name(zone.worksheet_name)
                if worksheet:
                    visual = self._convert_worksheet_to_visual(
                        worksheet, zone, dataset
                    )
                    page.visuals.append(visual)
        
        # If no visuals from zones, create from all worksheets
        if not page.visuals:
            for i, ws in enumerate(workbook.worksheets):
                visual = self._create_visual_from_worksheet(ws, dataset, i)
                page.visuals.append(visual)
        
        return page
    
    def _create_page_from_worksheet(self, worksheet: TableauWorksheet, 
                                    dataset: CanonicalDataset, index: int) -> CanonicalPage:
        """Create a page from a single worksheet."""
        page_id = self._generate_page_id(worksheet.name)
        
        page = CanonicalPage(
            id=page_id,
            name=self._sanitize_name(worksheet.name),
            display_name=worksheet.title or worksheet.name,
            width=1280,
            height=720
        )
        
        visual = self._create_visual_from_worksheet(worksheet, dataset, 0)
        page.visuals.append(visual)
        
        return page
    
    def _convert_worksheet_to_visual(self, worksheet: TableauWorksheet, 
                                     zone: Any, dataset: CanonicalDataset) -> CanonicalVisual:
        """Convert a worksheet placed in a dashboard zone to a visual."""
        visual_id = self._generate_visual_id(worksheet.name)
        visual_type = self.VISUAL_TYPE_MAP.get(worksheet.visual_type, VisualType.TABLE)
        
        # Check for unsupported features
        unsupported = []
        confidence = ConfidenceLevel.HIGH
        
        if worksheet.is_dual_axis:
            unsupported.append("Dual-axis chart - converted to single axis")
            self.unsupported_features['dual_axis_charts'].append(worksheet.name)
            confidence = ConfidenceLevel.MEDIUM
        
        # Scale zone coordinates to fit Power BI canvas
        x, y, width, height = self._scale_zone_position(zone)
        
        visual = CanonicalVisual(
            id=visual_id,
            name=worksheet.name,
            visual_type=visual_type,
            x=x,
            y=y,
            width=width,
            height=height,
            title=worksheet.title or worksheet.name,
            source_worksheet=worksheet.name,
            confidence=confidence,
            unsupported_features=unsupported
        )
        
        # Set encodings from field references
        self._set_visual_encodings(visual, worksheet, dataset)
        
        return visual
    
    def _create_visual_from_worksheet(self, worksheet: TableauWorksheet, 
                                      dataset: CanonicalDataset, index: int) -> CanonicalVisual:
        """Create a visual from a worksheet without zone positioning."""
        visual_id = self._generate_visual_id(worksheet.name)
        visual_type = self.VISUAL_TYPE_MAP.get(worksheet.visual_type, VisualType.TABLE)
        
        # Calculate position based on index (grid layout)
        cols_per_row = 2
        col = index % cols_per_row
        row = index // cols_per_row
        
        x = 50 + col * 600
        y = 50 + row * 400
        width = 550
        height = 350
        
        unsupported = []
        confidence = ConfidenceLevel.HIGH
        
        if worksheet.is_dual_axis:
            unsupported.append("Dual-axis chart")
            confidence = ConfidenceLevel.MEDIUM
        
        visual = CanonicalVisual(
            id=visual_id,
            name=worksheet.name,
            visual_type=visual_type,
            x=x,
            y=y,
            width=width,
            height=height,
            title=worksheet.title or worksheet.name,
            source_worksheet=worksheet.name,
            confidence=confidence,
            unsupported_features=unsupported
        )
        
        self._set_visual_encodings(visual, worksheet, dataset)
        
        return visual
    
    def _set_visual_encodings(self, visual: CanonicalVisual, 
                              worksheet: TableauWorksheet, dataset: CanonicalDataset):
        """Set visual encodings from worksheet field references."""
        # Get the primary table name
        table_name = dataset.tables[0].name if dataset.tables else "Data"
        
        # Rows go to category axis for most chart types
        for field in worksheet.rows:
            encoding = VisualEncoding(
                field_name=self._sanitize_name(field),
                table_name=table_name,
                is_measure=False
            )
            visual.category.append(encoding)
        
        # Columns often contain measures
        for field in worksheet.columns:
            # Check if this is a measure
            is_measure = self._is_measure_field(field, worksheet, dataset)
            encoding = VisualEncoding(
                field_name=self._sanitize_name(field),
                table_name=table_name,
                is_measure=is_measure,
                aggregation=AggregationType.SUM if is_measure else AggregationType.NONE
            )
            if is_measure:
                visual.values.append(encoding)
            else:
                visual.series.append(encoding)
        
        # Process mark encodings
        for enc_type, fields in worksheet.marks.items():
            for field in fields:
                encoding = VisualEncoding(
                    field_name=self._sanitize_name(field),
                    table_name=table_name
                )
                if enc_type == 'tooltip':
                    visual.tooltip.append(encoding)
                elif enc_type == 'color':
                    visual.series.append(encoding)
    
    def _is_measure_field(self, field_name: str, worksheet: TableauWorksheet, 
                          dataset: CanonicalDataset) -> bool:
        """Determine if a field is a measure."""
        # Check if field has aggregation in shelves
        for shelf in worksheet.shelves:
            for f in shelf.fields:
                if f.get('name') == field_name and f.get('aggregation'):
                    return True
        
        # Check if it's in the dataset measures
        for table in dataset.tables:
            for measure in table.measures:
                if measure.name == self._sanitize_name(field_name):
                    return True
        
        # Default: assume numeric-looking fields are measures
        numeric_indicators = ['sum', 'avg', 'count', 'sales', 'profit', 'quantity', 
                             'revenue', 'amount', 'total', 'price']
        return any(ind in field_name.lower() for ind in numeric_indicators)
    
    def _scale_zone_position(self, zone) -> tuple:
        """Scale zone position to Power BI canvas coordinates."""
        # Power BI standard canvas is 1280x720
        # Scale proportionally
        pbi_width = 1280
        pbi_height = 720
        
        # Assume Tableau dashboard is around 1200x800 if not specified
        tb_width = 1200
        tb_height = 800
        
        scale_x = pbi_width / tb_width
        scale_y = pbi_height / tb_height
        
        x = int(zone.x * scale_x)
        y = int(zone.y * scale_y)
        width = int(zone.width * scale_x)
        height = int(zone.height * scale_y)
        
        # Ensure minimum sizes
        width = max(width, 100)
        height = max(height, 100)
        
        # Ensure within canvas bounds
        x = min(x, pbi_width - width)
        y = min(y, pbi_height - height)
        
        return x, y, width, height
    
    def _sanitize_name(self, name: str) -> str:
        """Sanitize a name for use in Power BI."""
        if not name:
            return "Unnamed"
        
        # Remove or replace invalid characters
        sanitized = name.replace(' ', '_')
        sanitized = ''.join(c for c in sanitized if c.isalnum() or c in '_-')
        
        # Ensure it doesn't start with a number
        if sanitized and sanitized[0].isdigit():
            sanitized = '_' + sanitized
        
        # Ensure not empty
        if not sanitized:
            sanitized = "Field"
        
        return sanitized
    
    def _generate_page_id(self, name: str) -> str:
        """Generate a deterministic page ID."""
        # Power BI uses 20-character hex IDs
        hash_bytes = hashlib.md5(name.encode()).hexdigest()
        return hash_bytes[:20]
    
    def _generate_visual_id(self, name: str) -> str:
        """Generate a deterministic visual ID."""
        return str(uuid.uuid5(uuid.NAMESPACE_DNS, name)).replace('-', '')[:32]
