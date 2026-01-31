"""
Stage 3: Power BI Semantic Model Generator

Generates Power BI TMDL semantic model files from canonical schema.
Creates offline/disconnected models with placeholder tables (no data loading).
"""

import os
import json
import hashlib
from typing import List, Optional

from ..models.canonical_schema import (
    CanonicalReport, CanonicalDataset, CanonicalTable, CanonicalColumn,
    CanonicalMeasure, DataType, ConfidenceLevel
)
from ..models.powerbi_schema import (
    PBISemanticModel, PBITable, PBIColumn, PBIMeasure
)


class PowerBIModelGenerator:
    """
    Generates Power BI semantic model artifacts (.tmdl files).
    
    Creates offline/disconnected models that:
    - Contain table and column metadata only
    - Include translated DAX measures
    - Have no data connections or partitions
    - Are syntactically valid for Power BI Desktop
    """
    
    # Data type mapping from canonical to Power BI TMDL
    DATA_TYPE_MAP = {
        DataType.STRING: 'string',
        DataType.INTEGER: 'int64',
        DataType.DECIMAL: 'decimal',
        DataType.DOUBLE: 'double',
        DataType.DATE: 'dateTime',
        DataType.DATETIME: 'dateTime',
        DataType.BOOLEAN: 'boolean',
        DataType.BINARY: 'binary',
    }
    
    def __init__(self, output_path: str):
        """
        Initialize the generator.
        
        Args:
            output_path: Base path for the semantic model folder
        """
        self.output_path = output_path
        self.model: Optional[PBISemanticModel] = None
    
    def generate(self, report: CanonicalReport) -> PBISemanticModel:
        """
        Generate Power BI semantic model from canonical report.
        
        Args:
            report: The canonical report with dataset
            
        Returns:
            PBISemanticModel structure
        """
        self.model = self._create_model(report.dataset)
        
        # Create directory structure
        self._create_directories()
        
        # Generate all model files
        self._generate_pbism()
        self._generate_database_tmdl()
        self._generate_model_tmdl()
        self._generate_table_tmdl_files()
        self._generate_culture_tmdl()
        self._generate_diagram_layout()
        
        return self.model
    
    def _create_model(self, dataset: CanonicalDataset) -> PBISemanticModel:
        """Create Power BI semantic model from canonical dataset."""
        model = PBISemanticModel(
            name=dataset.name,
            culture='en-US',
            compatibility_level=1600
        )
        
        for canonical_table in dataset.tables:
            pbi_table = self._convert_table(canonical_table)
            model.tables.append(pbi_table)
        
        return model
    
    def _convert_table(self, canonical_table: CanonicalTable) -> PBITable:
        """Convert canonical table to Power BI table."""
        pbi_table = PBITable(
            name=canonical_table.name,
            description=canonical_table.description
        )
        
        # Convert columns
        for col in canonical_table.columns:
            pbi_col = self._convert_column(col)
            pbi_table.columns.append(pbi_col)
        
        # Convert measures
        for measure in canonical_table.measures:
            pbi_measure = self._convert_measure(measure, canonical_table.name)
            if pbi_measure:
                pbi_table.measures.append(pbi_measure)
        
        return pbi_table
    
    def _convert_column(self, col: CanonicalColumn) -> PBIColumn:
        """Convert canonical column to Power BI column."""
        data_type = self.DATA_TYPE_MAP.get(col.data_type, 'string')
        
        return PBIColumn(
            name=col.name,
            data_type=data_type,
            source_column=col.source_column or col.name,
            description=col.description
        )
    
    def _convert_measure(self, measure: CanonicalMeasure, table_name: str) -> Optional[PBIMeasure]:
        """Convert canonical measure to Power BI measure."""
        # Skip unsupported measures
        if measure.confidence == ConfidenceLevel.UNSUPPORTED:
            return None
        
        # Use translated DAX or create a placeholder
        if measure.dax_expression:
            expression = measure.dax_expression
        else:
            # Create a placeholder measure
            expression = f'0 /* Placeholder for: {measure.expression[:50] if measure.expression else "N/A"} */'
        
        return PBIMeasure(
            name=measure.name,
            expression=expression,
            format_string=measure.format_string,
            description=measure.description or f"Migrated from Tableau. Confidence: {measure.confidence.value}"
        )
    
    def _create_directories(self):
        """Create the semantic model directory structure."""
        definition_path = os.path.join(self.output_path, 'definition')
        cultures_path = os.path.join(definition_path, 'cultures')
        tables_path = os.path.join(definition_path, 'tables')
        pbi_path = os.path.join(self.output_path, '.pbi')
        
        os.makedirs(definition_path, exist_ok=True)
        os.makedirs(cultures_path, exist_ok=True)
        os.makedirs(tables_path, exist_ok=True)
        os.makedirs(pbi_path, exist_ok=True)
        
        # Create .pbi settings files
        self._generate_pbi_settings(pbi_path)
    
    def _generate_pbism(self):
        """Generate definition.pbism file."""
        pbism = {
            "version": "4.2",
            "settings": {}
        }
        
        pbism_path = os.path.join(self.output_path, 'definition.pbism')
        with open(pbism_path, 'w', encoding='utf-8') as f:
            json.dump(pbism, f, indent=2)
    
    def _generate_database_tmdl(self):
        """Generate database.tmdl file."""
        content = f"""database
\tcompatibilityLevel: {self.model.compatibility_level}

"""
        
        db_path = os.path.join(self.output_path, 'definition', 'database.tmdl')
        with open(db_path, 'w', encoding='utf-8') as f:
            f.write(content)
    
    def _generate_model_tmdl(self):
        """Generate model.tmdl file."""
        content = f"""model Model
\tculture: {self.model.culture}
\tdefaultPowerBIDataSourceVersion: powerBI_V3
\tsourceQueryCulture: en-US
\tdataAccessOptions
\t\tlegacyRedirects
\t\treturnErrorValuesAsNull

annotation __PBI_TimeIntelligenceEnabled = 1

annotation PBI_ProTooling = ["DevMode"]

ref cultureInfo {self.model.culture}

"""
        
        # Add unique table references (avoid duplicates)
        seen_tables = set()
        for table in self.model.tables:
            if table.name not in seen_tables:
                content += f"ref table '{table.name}'\n\n"
                seen_tables.add(table.name)
        
        model_path = os.path.join(self.output_path, 'definition', 'model.tmdl')
        with open(model_path, 'w', encoding='utf-8') as f:
            f.write(content)
    
    def _generate_table_tmdl_files(self):
        """Generate individual table .tmdl files."""
        tables_path = os.path.join(self.output_path, 'definition', 'tables')
        
        # Track which tables we've already written
        seen_tables = set()
        
        for table in self.model.tables:
            # Skip duplicate tables
            if table.name in seen_tables:
                continue
            seen_tables.add(table.name)
            
            content = self._generate_table_tmdl(table)
            # Sanitize filename
            safe_name = table.name.replace("'", "").replace('"', '').replace(' ', '_')
            table_file = os.path.join(tables_path, f'{safe_name}.tmdl')
            with open(table_file, 'w', encoding='utf-8') as f:
                f.write(content)
    
    def _generate_table_tmdl(self, table: PBITable) -> str:
        """Generate TMDL content for a single table using calculated table format."""
        lineage_tag = self._generate_lineage_tag(table.name)
        
        # Use calculated table format - this works without data source
        # Generate DAX to create an empty table with schema
        dax_columns = []
        for col in table.columns:
            dax_type = self._data_type_to_dax_type(col.data_type)
            dax_columns.append(f'"{col.name}", {dax_type}')
        
        if dax_columns:
            table_dax = 'DATATABLE(' + ', '.join(dax_columns) + ')'
        else:
            table_dax = 'DATATABLE("Value", STRING)'
        
        lines = [
            f'table \'{table.name}\'',
            f'\tlineageTag: {lineage_tag}',
            ''
        ]
        
        # Add columns - for calculated table, use isNameInferredFromValue
        for col in table.columns:
            col_lineage = self._generate_lineage_tag(f"{table.name}_{col.name}")
            lines.extend([
                f'\tcolumn \'{col.name}\'',
                f'\t\tdataType: {col.data_type}',
                f'\t\tlineageTag: {col_lineage}',
                f'\t\tsummarizeBy: none',
                f'\t\tisNameInferredFromValue',
                f'\t\tsourceColumn: [{col.source_column or col.name}]',
                '',
                f'\t\tannotation SummarizationSetBy = Automatic',
                ''
            ])
        
        # Add measures
        for measure in table.measures:
            measure_lineage = self._generate_lineage_tag(f"{table.name}_{measure.name}")
            # Clean expression for TMDL (handle multi-line)
            expr = measure.expression.replace('\n', ' ').replace('\t', ' ')
            lines.extend([
                f'\tmeasure \'{measure.name}\' = {expr}',
                f'\t\tlineageTag: {measure_lineage}',
                ''
            ])
        
        # Add partition with proper M query format for TMDL
        lines.append(f'\tpartition \'{table.name}\' = m')
        lines.append(f'\t\tmode: import')
        lines.append(f'\t\tsource')
        lines.append(f'\t\t\tlet')
        lines.append(f'\t\t\t\tSource = #table(')
        
        # Build column type table
        col_defs = []
        for col in table.columns:
            m_type = self._data_type_to_m_type(col.data_type)
            col_defs.append(f'\t\t\t\t\t{{"{col.name}", {m_type}}}')
        
        if col_defs:
            lines.append(f'\t\t\t\t\t{{')
            lines.append(',\n'.join(col_defs))
            lines.append(f'\t\t\t\t\t}},')
        else:
            lines.append(f'\t\t\t\t\t{{{{"Value", type text}}}},')
        
        lines.append(f'\t\t\t\t\t{{}}')
        lines.append(f'\t\t\t\t)')
        lines.append(f'\t\t\tin')
        lines.append(f'\t\t\t\tSource')
        lines.append('')
        
        # Add annotations
        lines.extend([
            f'\tannotation PBI_NavigationStepName = Source',
            f'\tannotation PBI_ResultType = Table',
            ''
        ])
        
        return '\n'.join(lines)
    
    def _data_type_to_m_type(self, data_type: str) -> str:
        """Convert Power BI data type to M type."""
        type_map = {
            'string': 'type text',
            'int64': 'Int64.Type',
            'double': 'type number',
            'decimal': 'type number',
            'dateTime': 'type datetime',
            'boolean': 'type logical',
            'binary': 'type binary'
        }
        return type_map.get(data_type, 'type text')
    
    def _data_type_to_dax_type(self, data_type: str) -> str:
        """Convert Power BI data type to DAX type for DATATABLE."""
        type_map = {
            'string': 'STRING',
            'int64': 'INTEGER',
            'double': 'DOUBLE',
            'decimal': 'CURRENCY',
            'dateTime': 'DATETIME',
            'boolean': 'BOOLEAN',
            'binary': 'BINARY'
        }
        return type_map.get(data_type, 'STRING')
    
    def _generate_culture_tmdl(self):
        """Generate culture .tmdl file."""
        content = f"""cultureInfo {self.model.culture}

\tlinguisticMetadata =
\t\t\t{{
\t\t\t  "Version": "1.0.0",
\t\t\t  "Language": "{self.model.culture}"
\t\t\t}}
\t\tcontentType: json

"""
        
        culture_path = os.path.join(self.output_path, 'definition', 'cultures', f'{self.model.culture}.tmdl')
        with open(culture_path, 'w', encoding='utf-8') as f:
            f.write(content)
    
    def _generate_diagram_layout(self):
        """Generate diagramLayout.json file."""
        # Create nodes for each table
        nodes = []
        for i, table in enumerate(self.model.tables):
            node = {
                "location": {
                    "x": 100 + (i % 3) * 300,
                    "y": 100 + (i // 3) * 200
                },
                "nodeIndex": i,
                "tableName": table.name,
                "isCollapsed": False
            }
            nodes.append(node)
        
        diagram = {
            "version": "1.1.0",
            "diagrams": [
                {
                    "ordinal": 0,
                    "scrollPosition": {
                        "x": 0,
                        "y": 0
                    },
                    "nodes": nodes,
                    "name": "All tables",
                    "zoomValue": 100,
                    "pinKeyFieldsToTop": False,
                    "showExtraHeaderInfo": False,
                    "hideKeyFieldsWhenCollapsed": False,
                    "tablesLocked": False
                }
            ],
            "selectedDiagram": "All tables",
            "defaultDiagram": "All tables"
        }
        
        diagram_path = os.path.join(self.output_path, 'diagramLayout.json')
        with open(diagram_path, 'w', encoding='utf-8') as f:
            json.dump(diagram, f, indent=2)
    
    def _generate_pbi_settings(self, pbi_path: str):
        """Generate .pbi folder settings files."""
        # localSettings.json
        local_settings = {
            "version": "1.0"
        }
        local_path = os.path.join(pbi_path, 'localSettings.json')
        with open(local_path, 'w', encoding='utf-8') as f:
            json.dump(local_settings, f, indent=2)
        
        # editorSettings.json - must match Power BI expected format
        editor_settings = {
            "version": "1.0",
            "autodetectRelationships": True,
            "parallelQueryLoading": True,
            "typeDetectionEnabled": True,
            "relationshipImportEnabled": True,
            "shouldNotifyUserOfNameConflictResolution": True
        }
        editor_path = os.path.join(pbi_path, 'editorSettings.json')
        with open(editor_path, 'w', encoding='utf-8') as f:
            json.dump(editor_settings, f, indent=2)
    
    def _generate_lineage_tag(self, name: str) -> str:
        """Generate a deterministic lineage tag UUID."""
        hash_bytes = hashlib.md5(name.encode()).hexdigest()
        return f'{hash_bytes[:8]}-{hash_bytes[8:12]}-{hash_bytes[12:16]}-{hash_bytes[16:20]}-{hash_bytes[20:32]}'
