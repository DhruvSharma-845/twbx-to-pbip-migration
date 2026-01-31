"""
Power BI Schema Models

Defines structures for generating Power BI PBIP artifacts.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any


@dataclass
class PBIColumn:
    """Power BI semantic model column."""
    name: str
    data_type: str  # String, Int64, Double, DateTime, Boolean, etc.
    source_column: Optional[str] = None
    format_string: Optional[str] = None
    is_hidden: bool = False
    summarize_by: str = "None"  # None, Sum, Count, Average, Min, Max
    description: Optional[str] = None
    
    def to_tmdl(self) -> str:
        """Generate TMDL representation."""
        lines = [f'\tcolumn {self.name}']
        lines.append(f'\t\tdataType: {self.data_type}')
        if self.source_column:
            lines.append(f'\t\tsourceColumn: {self.source_column}')
        if self.format_string:
            lines.append(f'\t\tformatString: {self.format_string}')
        if self.is_hidden:
            lines.append('\t\tisHidden')
        if self.summarize_by != "None":
            lines.append(f'\t\tsummarizeBy: {self.summarize_by}')
        lines.append('')
        return '\n'.join(lines)


@dataclass
class PBIMeasure:
    """Power BI semantic model measure."""
    name: str
    expression: str  # DAX expression
    format_string: Optional[str] = None
    is_hidden: bool = False
    display_folder: Optional[str] = None
    description: Optional[str] = None
    
    def to_tmdl(self) -> str:
        """Generate TMDL representation."""
        lines = [f'\tmeasure {self.name} = {self.expression}']
        if self.format_string:
            lines.append(f'\t\tformatString: {self.format_string}')
        if self.is_hidden:
            lines.append('\t\tisHidden')
        if self.display_folder:
            lines.append(f'\t\tdisplayFolder: {self.display_folder}')
        lines.append('')
        return '\n'.join(lines)


@dataclass
class PBITable:
    """Power BI semantic model table."""
    name: str
    columns: List[PBIColumn] = field(default_factory=list)
    measures: List[PBIMeasure] = field(default_factory=list)
    is_hidden: bool = False
    description: Optional[str] = None
    
    def to_tmdl(self) -> str:
        """Generate TMDL representation."""
        lines = [f'table {self.name}']
        lines.append('\tlineageTag: ' + self._generate_lineage_tag())
        lines.append('')
        
        # Add columns
        for col in self.columns:
            lines.append(col.to_tmdl())
        
        # Add measures
        for measure in self.measures:
            lines.append(measure.to_tmdl())
        
        return '\n'.join(lines)
    
    def _generate_lineage_tag(self) -> str:
        """Generate a deterministic lineage tag."""
        import hashlib
        return hashlib.md5(self.name.encode()).hexdigest()[:8] + '-' + \
               hashlib.md5(self.name.encode()).hexdigest()[8:12] + '-' + \
               hashlib.md5(self.name.encode()).hexdigest()[12:16] + '-' + \
               hashlib.md5(self.name.encode()).hexdigest()[16:20] + '-' + \
               hashlib.md5(self.name.encode()).hexdigest()[20:32]


@dataclass
class PBIRelationship:
    """Power BI semantic model relationship."""
    from_table: str
    from_column: str
    to_table: str
    to_column: str
    is_active: bool = True
    cross_filtering: str = "oneDirection"  # oneDirection, bothDirections
    
    def to_tmdl(self) -> str:
        """Generate TMDL representation."""
        lines = [f'relationship {self._generate_id()}']
        lines.append(f'\tfromColumn: {self.from_table}[{self.from_column}]')
        lines.append(f'\ttoColumn: {self.to_table}[{self.to_column}]')
        if not self.is_active:
            lines.append('\tisActive: false')
        if self.cross_filtering != "oneDirection":
            lines.append(f'\tcrossFilteringBehavior: {self.cross_filtering}')
        lines.append('')
        return '\n'.join(lines)
    
    def _generate_id(self) -> str:
        import hashlib
        key = f"{self.from_table}.{self.from_column}->{self.to_table}.{self.to_column}"
        return hashlib.md5(key.encode()).hexdigest()[:16]


@dataclass
class PBISemanticModel:
    """Power BI semantic model."""
    name: str
    tables: List[PBITable] = field(default_factory=list)
    relationships: List[PBIRelationship] = field(default_factory=list)
    culture: str = "en-US"
    compatibility_level: int = 1600
    
    def get_table_by_name(self, name: str) -> Optional[PBITable]:
        for table in self.tables:
            if table.name == name:
                return table
        return None


@dataclass
class PBIVisualConfig:
    """Configuration for a Power BI visual."""
    visual_type: str
    name: str
    x: int
    y: int
    width: int
    height: int
    title: Optional[str] = None
    data_roles: Dict[str, List[Dict[str, Any]]] = field(default_factory=dict)
    properties: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PBIPage:
    """Power BI report page."""
    name: str
    display_name: str
    width: int = 1280
    height: int = 720
    visuals: List[PBIVisualConfig] = field(default_factory=list)
    display_option: str = "FitToPage"


@dataclass
class PBIReport:
    """Power BI report definition."""
    name: str
    semantic_model_path: str
    pages: List[PBIPage] = field(default_factory=list)
    theme: str = "CY25SU12"
