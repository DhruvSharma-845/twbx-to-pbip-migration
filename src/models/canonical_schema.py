"""
Canonical BI Schema Models

Defines the intermediate representation used between Tableau extraction and Power BI generation.
This schema is platform-agnostic and can be validated at each stage.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any
from enum import Enum
import json


class ConfidenceLevel(Enum):
    """Confidence level for translations."""
    HIGH = "high"  # Direct 1:1 mapping
    MEDIUM = "medium"  # Translation with minor adjustments
    LOW = "low"  # Best-effort translation, may need review
    UNSUPPORTED = "unsupported"  # Cannot be translated


class DataType(Enum):
    """Platform-agnostic data types."""
    STRING = "string"
    INTEGER = "int64"
    DECIMAL = "decimal"
    DOUBLE = "double"
    DATE = "date"
    DATETIME = "datetime"
    BOOLEAN = "boolean"
    BINARY = "binary"


class AggregationType(Enum):
    """Aggregation types."""
    SUM = "sum"
    COUNT = "count"
    COUNTD = "countd"  # Count distinct
    AVG = "average"
    MIN = "min"
    MAX = "max"
    MEDIAN = "median"
    STDEV = "stdev"
    VAR = "variance"
    NONE = "none"


class VisualType(Enum):
    """Platform-agnostic visual types."""
    BAR_CHART = "bar_chart"
    CLUSTERED_BAR = "clustered_bar"
    STACKED_BAR = "stacked_bar"
    LINE_CHART = "line_chart"
    AREA_CHART = "area_chart"
    PIE_CHART = "pie_chart"
    DONUT_CHART = "donut_chart"
    TABLE = "table"
    MATRIX = "matrix"
    CARD = "card"
    SLICER = "slicer"
    SCATTER = "scatter"
    MAP = "map"
    TREEMAP = "treemap"
    FUNNEL = "funnel"
    GAUGE = "gauge"
    KPI = "kpi"
    TEXT = "text"
    IMAGE = "image"
    UNKNOWN = "unknown"


@dataclass
class CanonicalColumn:
    """A platform-agnostic column definition."""
    name: str
    display_name: str
    data_type: DataType
    is_nullable: bool = True
    is_key: bool = False
    source_column: Optional[str] = None
    description: Optional[str] = None


@dataclass
class CanonicalMeasure:
    """A platform-agnostic measure definition."""
    name: str
    display_name: str
    expression: str  # Original expression
    dax_expression: Optional[str] = None  # Translated DAX
    confidence: ConfidenceLevel = ConfidenceLevel.HIGH
    aggregation: AggregationType = AggregationType.SUM
    format_string: Optional[str] = None
    description: Optional[str] = None
    unsupported_reason: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "display_name": self.display_name,
            "expression": self.expression,
            "dax_expression": self.dax_expression,
            "confidence": self.confidence.value,
            "aggregation": self.aggregation.value,
            "format_string": self.format_string,
            "description": self.description,
            "unsupported_reason": self.unsupported_reason
        }


@dataclass
class CanonicalTable:
    """A platform-agnostic table definition."""
    name: str
    display_name: str
    columns: List[CanonicalColumn] = field(default_factory=list)
    measures: List[CanonicalMeasure] = field(default_factory=list)
    source_table: Optional[str] = None
    is_calculated: bool = False
    description: Optional[str] = None


@dataclass
class CanonicalRelationship:
    """A relationship between two tables."""
    from_table: str
    from_column: str
    to_table: str
    to_column: str
    is_active: bool = True
    cardinality: str = "many-to-one"  # many-to-one, one-to-many, one-to-one, many-to-many


@dataclass
class CanonicalDataset:
    """A platform-agnostic dataset/model definition."""
    name: str
    tables: List[CanonicalTable] = field(default_factory=list)
    relationships: List[CanonicalRelationship] = field(default_factory=list)
    description: Optional[str] = None
    
    def get_table_by_name(self, name: str) -> Optional[CanonicalTable]:
        for table in self.tables:
            if table.name == name:
                return table
        return None


@dataclass
class VisualEncoding:
    """Encoding for a visual channel."""
    field_name: str
    table_name: Optional[str] = None
    aggregation: AggregationType = AggregationType.NONE
    is_measure: bool = False
    format_string: Optional[str] = None


@dataclass
class CanonicalVisual:
    """A platform-agnostic visual definition."""
    id: str
    name: str
    visual_type: VisualType
    x: int = 0
    y: int = 0
    width: int = 400
    height: int = 300
    title: Optional[str] = None
    
    # Encoding channels
    category: List[VisualEncoding] = field(default_factory=list)
    values: List[VisualEncoding] = field(default_factory=list)
    series: List[VisualEncoding] = field(default_factory=list)
    tooltip: List[VisualEncoding] = field(default_factory=list)
    
    # Visual-specific properties
    properties: Dict[str, Any] = field(default_factory=dict)
    
    # Migration metadata
    source_worksheet: Optional[str] = None
    confidence: ConfidenceLevel = ConfidenceLevel.HIGH
    unsupported_features: List[str] = field(default_factory=list)


@dataclass
class CanonicalFilter:
    """A platform-agnostic filter definition."""
    field_name: str
    filter_type: str  # basic, relative_date, advanced
    table_name: Optional[str] = None
    values: List[Any] = field(default_factory=list)
    operator: Optional[str] = None  # equals, contains, greater_than, etc.
    is_slicer: bool = False


@dataclass 
class CanonicalPage:
    """A platform-agnostic page/dashboard definition."""
    id: str
    name: str
    display_name: str
    width: int = 1280
    height: int = 720
    visuals: List[CanonicalVisual] = field(default_factory=list)
    filters: List[CanonicalFilter] = field(default_factory=list)
    source_dashboard: Optional[str] = None


@dataclass
class CanonicalReport:
    """A complete platform-agnostic report definition."""
    name: str
    dataset: CanonicalDataset
    pages: List[CanonicalPage] = field(default_factory=list)
    theme: Optional[str] = None
    description: Optional[str] = None
    
    # Migration metadata
    source_file: Optional[str] = None
    migration_warnings: List[str] = field(default_factory=list)
    unsupported_features: Dict[str, List[str]] = field(default_factory=dict)


@dataclass
class MigrationReport:
    """Summary of the migration process."""
    source_file: str
    output_folder: str
    
    # Counts
    dashboards_migrated: int = 0
    worksheets_migrated: int = 0
    visuals_migrated: int = 0
    tables_created: int = 0
    measures_translated: int = 0
    measures_flagged: int = 0
    
    # Details
    translated_measures: List[Dict[str, Any]] = field(default_factory=list)
    flagged_measures: List[Dict[str, Any]] = field(default_factory=list)
    unsupported_features: List[Dict[str, str]] = field(default_factory=list)
    fidelity_gaps: List[Dict[str, str]] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    
    # Status
    success: bool = True
    error_message: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "source_file": self.source_file,
            "output_folder": self.output_folder,
            "summary": {
                "dashboards_migrated": self.dashboards_migrated,
                "worksheets_migrated": self.worksheets_migrated,
                "visuals_migrated": self.visuals_migrated,
                "tables_created": self.tables_created,
                "measures_translated": self.measures_translated,
                "measures_flagged": self.measures_flagged
            },
            "translated_measures": self.translated_measures,
            "flagged_measures": self.flagged_measures,
            "unsupported_features": self.unsupported_features,
            "fidelity_gaps": self.fidelity_gaps,
            "warnings": self.warnings,
            "success": self.success,
            "error_message": self.error_message
        }
    
    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)
