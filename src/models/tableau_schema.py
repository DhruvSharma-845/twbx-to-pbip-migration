"""
Tableau Semantic Schema Models

Defines the data structures for extracted Tableau workbook metadata.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any
from enum import Enum


class TableauVisualType(Enum):
    """Tableau worksheet/visualization types."""
    BAR = "bar"
    LINE = "line"
    AREA = "area"
    PIE = "pie"
    SCATTER = "scatter"
    TEXT_TABLE = "text_table"
    CROSSTAB = "crosstab"
    MAP = "map"
    TREEMAP = "treemap"
    HEATMAP = "heatmap"
    HISTOGRAM = "histogram"
    GANTT = "gantt"
    BULLET = "bullet"
    PACKED_BUBBLE = "packed_bubble"
    DUAL_AXIS = "dual_axis"
    COMBINED_AXIS = "combined_axis"
    UNKNOWN = "unknown"


class TableauDataType(Enum):
    """Tableau field data types."""
    STRING = "string"
    INTEGER = "integer"
    REAL = "real"
    DATE = "date"
    DATETIME = "datetime"
    BOOLEAN = "boolean"
    UNKNOWN = "unknown"


class TableauRole(Enum):
    """Tableau field role (dimension vs measure)."""
    DIMENSION = "dimension"
    MEASURE = "measure"


class CalculationType(Enum):
    """Types of Tableau calculations."""
    BASIC = "basic"  # Simple aggregations
    TABLE_CALC = "table_calculation"  # Table calculations (unsupported)
    LOD = "lod"  # Level of Detail expressions (unsupported)
    PARAMETER = "parameter"


@dataclass
class TableauColumn:
    """Represents a column/field in Tableau."""
    name: str
    caption: Optional[str] = None
    datatype: TableauDataType = TableauDataType.STRING
    role: TableauRole = TableauRole.DIMENSION
    calculation: Optional[str] = None
    calculation_type: CalculationType = CalculationType.BASIC
    aggregation: Optional[str] = None
    is_hidden: bool = False
    source_table: Optional[str] = None
    
    @property
    def display_name(self) -> str:
        return self.caption or self.name


@dataclass
class TableauTable:
    """Represents a logical table in Tableau."""
    name: str
    caption: Optional[str] = None
    columns: List[TableauColumn] = field(default_factory=list)
    is_extract: bool = False
    connection_type: Optional[str] = None
    
    @property
    def display_name(self) -> str:
        return self.caption or self.name


@dataclass
class TableauDatasource:
    """Represents a Tableau datasource."""
    name: str
    caption: Optional[str] = None
    tables: List[TableauTable] = field(default_factory=list)
    calculated_fields: List[TableauColumn] = field(default_factory=list)
    parameters: List[Dict[str, Any]] = field(default_factory=list)
    connection_info: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def display_name(self) -> str:
        return self.caption or self.name


@dataclass
class TableauFilter:
    """Represents a filter in Tableau."""
    field_name: str
    filter_type: str  # categorical, range, relative_date, etc.
    values: List[Any] = field(default_factory=list)
    include_null: bool = False
    is_global: bool = False


@dataclass
class TableauShelf:
    """Represents a shelf (rows, columns, color, etc.) in a worksheet."""
    shelf_type: str  # rows, columns, pages, filters, color, size, label, detail, tooltip
    fields: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class TableauWorksheet:
    """Represents a Tableau worksheet."""
    name: str
    datasource_name: Optional[str] = None
    visual_type: TableauVisualType = TableauVisualType.UNKNOWN
    shelves: List[TableauShelf] = field(default_factory=list)
    filters: List[TableauFilter] = field(default_factory=list)
    title: Optional[str] = None
    is_dual_axis: bool = False
    mark_type: Optional[str] = None
    
    # Extracted field references for mapping
    rows: List[str] = field(default_factory=list)
    columns: List[str] = field(default_factory=list)
    marks: Dict[str, List[str]] = field(default_factory=dict)


@dataclass
class TableauDashboardZone:
    """Represents a zone (visual container) in a dashboard."""
    zone_id: str
    zone_type: str  # viz, blank, text, image, web, etc.
    worksheet_name: Optional[str] = None
    x: int = 0
    y: int = 0
    width: int = 100
    height: int = 100


@dataclass
class TableauDashboard:
    """Represents a Tableau dashboard."""
    name: str
    zones: List[TableauDashboardZone] = field(default_factory=list)
    width: int = 1280
    height: int = 800
    title: Optional[str] = None


@dataclass
class TableauWorkbook:
    """Represents a complete Tableau workbook."""
    name: str
    datasources: List[TableauDatasource] = field(default_factory=list)
    worksheets: List[TableauWorksheet] = field(default_factory=list)
    dashboards: List[TableauDashboard] = field(default_factory=list)
    parameters: List[Dict[str, Any]] = field(default_factory=list)
    version: Optional[str] = None
    
    def get_datasource_by_name(self, name: str) -> Optional[TableauDatasource]:
        for ds in self.datasources:
            if ds.name == name or ds.caption == name:
                return ds
        return None
    
    def get_worksheet_by_name(self, name: str) -> Optional[TableauWorksheet]:
        for ws in self.worksheets:
            if ws.name == name:
                return ws
        return None
