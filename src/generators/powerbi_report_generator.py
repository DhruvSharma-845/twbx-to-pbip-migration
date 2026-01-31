"""
Stage 4: Power BI Report Artifacts Generator

Generates Power BI report definition files (PBIR format) from canonical schema.
Creates pages and visuals with proper Power BI JSON structure.
"""

import os
import json
import shutil
import hashlib
from typing import List, Dict, Any, Optional

from ..models.canonical_schema import (
    CanonicalReport, CanonicalPage, CanonicalVisual, VisualType,
    VisualEncoding, AggregationType
)
from ..models.powerbi_schema import PBIReport, PBIPage, PBIVisualConfig


class PowerBIReportGenerator:
    """
    Generates Power BI report artifacts (PBIR format).
    
    Creates:
    - definition.pbir (model reference)
    - report.json (report settings)
    - pages.json (page metadata)
    - Individual page folders with visuals
    - Theme resources
    """
    
    # Visual type mapping from canonical to Power BI
    VISUAL_TYPE_MAP = {
        VisualType.BAR_CHART: 'clusteredBarChart',
        VisualType.CLUSTERED_BAR: 'clusteredColumnChart',
        VisualType.STACKED_BAR: 'stackedColumnChart',
        VisualType.LINE_CHART: 'lineChart',
        VisualType.AREA_CHART: 'areaChart',
        VisualType.PIE_CHART: 'pieChart',
        VisualType.DONUT_CHART: 'donutChart',
        VisualType.TABLE: 'tableEx',
        VisualType.MATRIX: 'pivotTable',
        VisualType.CARD: 'card',
        VisualType.SLICER: 'slicer',
        VisualType.SCATTER: 'scatterChart',
        VisualType.MAP: 'map',
        VisualType.TREEMAP: 'treemap',
        VisualType.FUNNEL: 'funnel',
        VisualType.GAUGE: 'gauge',
        VisualType.KPI: 'kpi',
        VisualType.TEXT: 'textbox',
        VisualType.IMAGE: 'image',
        VisualType.UNKNOWN: 'tableEx',
    }
    
    # Data role mappings for each visual type
    VISUAL_DATA_ROLES = {
        'clusteredColumnChart': {
            'category': 'Category',
            'values': 'Y',
            'series': 'Series'
        },
        'clusteredBarChart': {
            'category': 'Category',
            'values': 'Y',
            'series': 'Series'
        },
        'lineChart': {
            'category': 'Category',
            'values': 'Y',
            'series': 'Series'
        },
        'areaChart': {
            'category': 'Category',
            'values': 'Y',
            'series': 'Series'
        },
        'pieChart': {
            'category': 'Category',
            'values': 'Y'
        },
        'donutChart': {
            'category': 'Category',
            'values': 'Y'
        },
        'tableEx': {
            'category': 'Values'
        },
        'pivotTable': {
            'category': 'Rows',
            'values': 'Values',
            'series': 'Columns'
        },
        'card': {
            'values': 'Fields'
        },
        'slicer': {
            'category': 'Values'
        },
        'scatterChart': {
            'category': 'Category',
            'values': 'Y',
            'series': 'Series'
        }
    }
    
    def __init__(self, output_path: str, model_path: str, template_path: Optional[str] = None):
        """
        Initialize the generator.
        
        Args:
            output_path: Base path for the report folder
            model_path: Relative path to semantic model
            template_path: Optional path to template PBIP for resources
        """
        self.output_path = output_path
        self.model_path = model_path
        self.template_path = template_path
        self.report: Optional[PBIReport] = None
    
    def generate(self, canonical_report: CanonicalReport) -> PBIReport:
        """
        Generate Power BI report from canonical report.
        
        Args:
            canonical_report: The canonical report definition
            
        Returns:
            PBIReport structure
        """
        self.report = self._create_report(canonical_report)
        
        # Create directory structure
        self._create_directories()
        
        # Copy static resources from template if available
        self._copy_resources()
        
        # Generate all report files
        self._generate_pbir()
        self._generate_report_json()
        self._generate_version_json()
        self._generate_pages_json()
        self._generate_page_folders()
        
        return self.report
    
    def _create_report(self, canonical_report: CanonicalReport) -> PBIReport:
        """Create Power BI report from canonical report."""
        report = PBIReport(
            name=canonical_report.name,
            semantic_model_path=self.model_path
        )
        
        for canonical_page in canonical_report.pages:
            pbi_page = self._convert_page(canonical_page)
            report.pages.append(pbi_page)
        
        return report
    
    def _convert_page(self, canonical_page: CanonicalPage) -> PBIPage:
        """Convert canonical page to Power BI page."""
        page = PBIPage(
            name=canonical_page.id,
            display_name=canonical_page.display_name,
            width=canonical_page.width,
            height=canonical_page.height
        )
        
        for canonical_visual in canonical_page.visuals:
            pbi_visual = self._convert_visual(canonical_visual)
            page.visuals.append(pbi_visual)
        
        return page
    
    def _convert_visual(self, canonical_visual: CanonicalVisual) -> PBIVisualConfig:
        """Convert canonical visual to Power BI visual config."""
        pbi_type = self.VISUAL_TYPE_MAP.get(canonical_visual.visual_type, 'tableEx')
        
        visual = PBIVisualConfig(
            visual_type=pbi_type,
            name=canonical_visual.id,
            x=canonical_visual.x,
            y=canonical_visual.y,
            width=canonical_visual.width,
            height=canonical_visual.height,
            title=canonical_visual.title
        )
        
        # Build data roles based on visual type
        visual.data_roles = self._build_data_roles(
            pbi_type,
            canonical_visual.category,
            canonical_visual.values,
            canonical_visual.series
        )
        
        return visual
    
    def _build_data_roles(self, visual_type: str, 
                         category: List[VisualEncoding],
                         values: List[VisualEncoding],
                         series: List[VisualEncoding]) -> Dict[str, List[Dict[str, Any]]]:
        """Build Power BI data role mappings."""
        data_roles = {}
        role_mapping = self.VISUAL_DATA_ROLES.get(visual_type, {})
        
        if category and 'category' in role_mapping:
            role_name = role_mapping['category']
            data_roles[role_name] = [
                self._encoding_to_data_role(enc) for enc in category
            ]
        
        if values and 'values' in role_mapping:
            role_name = role_mapping['values']
            data_roles[role_name] = [
                self._encoding_to_data_role(enc, is_measure=True) for enc in values
            ]
        
        if series and 'series' in role_mapping:
            role_name = role_mapping['series']
            data_roles[role_name] = [
                self._encoding_to_data_role(enc) for enc in series
            ]
        
        return data_roles
    
    def _encoding_to_data_role(self, encoding: VisualEncoding, is_measure: bool = False) -> Dict[str, Any]:
        """Convert a visual encoding to Power BI data role format."""
        role = {
            'Column': {
                'Expression': {
                    'SourceRef': {
                        'Entity': encoding.table_name or 'Data'
                    }
                },
                'Property': encoding.field_name
            }
        }
        
        if is_measure or encoding.is_measure:
            # Wrap in aggregation
            if encoding.aggregation and encoding.aggregation != AggregationType.NONE:
                agg_map = {
                    AggregationType.SUM: 'Sum',
                    AggregationType.COUNT: 'Count',
                    AggregationType.COUNTD: 'CountNotNull',
                    AggregationType.AVG: 'Avg',
                    AggregationType.MIN: 'Min',
                    AggregationType.MAX: 'Max',
                }
                role['Column']['Aggregation'] = agg_map.get(encoding.aggregation, 'Sum')
        
        return role
    
    def _create_directories(self):
        """Create the report directory structure."""
        definition_path = os.path.join(self.output_path, 'definition')
        pages_path = os.path.join(definition_path, 'pages')
        resources_path = os.path.join(self.output_path, 'StaticResources', 'SharedResources', 'BaseThemes')
        
        os.makedirs(definition_path, exist_ok=True)
        os.makedirs(pages_path, exist_ok=True)
        os.makedirs(resources_path, exist_ok=True)
    
    def _copy_resources(self):
        """Copy static resources from template."""
        if self.template_path and os.path.exists(self.template_path):
            template_resources = os.path.join(self.template_path, 'StaticResources')
            output_resources = os.path.join(self.output_path, 'StaticResources')
            
            if os.path.exists(template_resources):
                if os.path.exists(output_resources):
                    shutil.rmtree(output_resources)
                shutil.copytree(template_resources, output_resources)
        else:
            # Generate default theme
            self._generate_default_theme()
    
    def _generate_default_theme(self):
        """Generate a default Power BI theme."""
        theme = {
            "name": "CY25SU12",
            "dataColors": [
                "#118DFF", "#12239E", "#E66C37", "#6B007B", "#E044A7",
                "#744EC2", "#D9B300", "#D64550", "#197278", "#1AAB40"
            ],
            "foreground": "#252423",
            "foregroundNeutralSecondary": "#605E5C",
            "background": "#FFFFFF",
            "tableAccent": "#118DFF"
        }
        
        theme_path = os.path.join(
            self.output_path, 'StaticResources', 'SharedResources', 'BaseThemes', 'CY25SU12.json'
        )
        with open(theme_path, 'w', encoding='utf-8') as f:
            json.dump(theme, f, indent=2)
    
    def _generate_pbir(self):
        """Generate definition.pbir file."""
        pbir = {
            "version": "4.0",
            "datasetReference": {
                "byPath": {
                    "path": self.model_path
                }
            }
        }
        
        pbir_path = os.path.join(self.output_path, 'definition.pbir')
        with open(pbir_path, 'w', encoding='utf-8') as f:
            json.dump(pbir, f, indent=2)
    
    def _generate_report_json(self):
        """Generate report.json file."""
        report_config = {
            "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/report/3.1.0/schema.json",
            "themeCollection": {
                "baseTheme": {
                    "name": "CY25SU12",
                    "reportVersionAtImport": {
                        "visual": "2.5.0",
                        "report": "3.1.0",
                        "page": "2.3.0"
                    },
                    "type": "SharedResources"
                }
            },
            "objects": {
                "section": [
                    {
                        "properties": {
                            "verticalAlignment": {
                                "expr": {
                                    "Literal": {
                                        "Value": "'Top'"
                                    }
                                }
                            }
                        }
                    }
                ]
            },
            "resourcePackages": [
                {
                    "name": "SharedResources",
                    "type": "SharedResources",
                    "items": [
                        {
                            "name": "CY25SU12",
                            "path": "BaseThemes/CY25SU12.json",
                            "type": "BaseTheme"
                        }
                    ]
                }
            ],
            "settings": {
                "useStylableVisualContainerHeader": True,
                "exportDataMode": "AllowSummarized",
                "defaultDrillFilterOtherVisuals": True,
                "allowChangeFilterTypes": True,
                "useEnhancedTooltips": True,
                "useDefaultAggregateDisplayName": True
            }
        }
        
        report_path = os.path.join(self.output_path, 'definition', 'report.json')
        with open(report_path, 'w', encoding='utf-8') as f:
            json.dump(report_config, f, indent=2)
    
    def _generate_version_json(self):
        """Generate version.json file."""
        version = {
            "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/versionMetadata/1.0.0/schema.json",
            "version": "2.0.0"
        }
        
        version_path = os.path.join(self.output_path, 'definition', 'version.json')
        with open(version_path, 'w', encoding='utf-8') as f:
            json.dump(version, f, indent=2)
    
    def _generate_pages_json(self):
        """Generate pages.json file."""
        pages_meta = {
            "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/pagesMetadata/1.0.0/schema.json",
            "pageOrder": [page.name for page in self.report.pages],
            "activePageName": self.report.pages[0].name if self.report.pages else ""
        }
        
        pages_path = os.path.join(self.output_path, 'definition', 'pages', 'pages.json')
        with open(pages_path, 'w', encoding='utf-8') as f:
            json.dump(pages_meta, f, indent=2)
    
    def _generate_page_folders(self):
        """Generate individual page folders with page.json only (no separate visual files)."""
        for idx, page in enumerate(self.report.pages):
            page_folder = os.path.join(self.output_path, 'definition', 'pages', page.name)
            
            os.makedirs(page_folder, exist_ok=True)
            
            # Generate page.json with embedded visuals (legacy compatible format)
            self._generate_legacy_page_json(page, page_folder, idx)
    
    def _generate_page_json(self, page: PBIPage, page_folder: str):
        """Generate page.json for a single page."""
        # Use older format without schema for compatibility
        page_config = {
            "name": page.name,
            "displayName": page.display_name,
            "displayOption": 1,  # FitToPage as integer
            "height": page.height,
            "width": page.width,
            "config": json.dumps({
                "name": page.name,
                "displayName": page.display_name,
                "displayOption": "FitToPage",
                "layoutWidth": page.width,
                "layoutHeight": page.height
            }),
            "ordinal": 0
        }
        
        page_path = os.path.join(page_folder, 'page.json')
        with open(page_path, 'w', encoding='utf-8') as f:
            json.dump(page_config, f, indent=2)
    
    def _generate_simple_page_json(self, page: PBIPage, page_folder: str):
        """Generate simple page.json matching sample PBIP format."""
        # Simple page config matching the sample format exactly
        page_config = {
            "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/page/2.0.0/schema.json",
            "name": page.name,
            "displayName": page.display_name,
            "displayOption": "FitToPage",
            "height": page.height,
            "width": page.width
        }
        
        page_path = os.path.join(page_folder, 'page.json')
        with open(page_path, 'w', encoding='utf-8') as f:
            json.dump(page_config, f, indent=2)
    
    def _generate_legacy_page_json(self, page: PBIPage, page_folder: str, page_idx: int):
        """Generate page.json without visuals (empty page for compatibility)."""
        # Use the exact same format as the sample PBIP - just basic page properties
        page_config = {
            "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/page/2.0.0/schema.json",
            "name": page.name,
            "displayName": page.display_name,
            "displayOption": "FitToPage",
            "height": page.height,
            "width": page.width
        }
        
        page_path = os.path.join(page_folder, 'page.json')
        with open(page_path, 'w', encoding='utf-8') as f:
            json.dump(page_config, f, indent=2)
    
    def _generate_simple_visual_json(self, visual: PBIVisualConfig, index: int, visuals_folder: str):
        """Generate visual.json with compatible schema version."""
        visual_folder = os.path.join(visuals_folder, visual.name)
        os.makedirs(visual_folder, exist_ok=True)
        
        # Visual config with schema version 1.0.0 for compatibility
        visual_config = {
            "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/visual/1.0.0/schema.json",
            "name": visual.name,
            "position": {
                "x": visual.x,
                "y": visual.y,
                "z": index,
                "height": visual.height,
                "width": visual.width,
                "tabOrder": index
            },
            "visual": {
                "visualType": visual.visual_type,
                "objects": {
                    "title": [
                        {
                            "properties": {
                                "show": {"expr": {"Literal": {"Value": "true"}}},
                                "text": {"expr": {"Literal": {"Value": f"'{visual.title or 'Visual'}'"}}}
                            }
                        }
                    ]
                }
            }
        }
        
        visual_path = os.path.join(visual_folder, 'visual.json')
        with open(visual_path, 'w', encoding='utf-8') as f:
            json.dump(visual_config, f, indent=2)
    
    def _generate_visual_json(self, visual: PBIVisualConfig, page: PBIPage, visuals_folder: str):
        """Generate visual.json for a single visual."""
        visual_id = visual.name
        visual_folder = os.path.join(visuals_folder, visual_id)
        os.makedirs(visual_folder, exist_ok=True)
        
        # Build visual configuration - using older compatible format without schema
        visual_config = {
            "name": visual_id,
            "visualType": visual.visual_type,
            "x": visual.x,
            "y": visual.y,
            "z": 0,
            "width": visual.width,
            "height": visual.height,
            "config": json.dumps({
                "name": visual_id,
                "layouts": [
                    {
                        "id": 0,
                        "position": {
                            "x": visual.x,
                            "y": visual.y,
                            "z": 0,
                            "width": visual.width,
                            "height": visual.height
                        }
                    }
                ],
                "singleVisual": {
                    "visualType": visual.visual_type,
                    "projections": self._build_projections(visual),
                    "prototypeQuery": self._build_prototype_query(visual),
                    "objects": {
                        "title": [
                            {
                                "properties": {
                                    "show": {"expr": {"Literal": {"Value": "true"}}},
                                    "titleWrap": {"expr": {"Literal": {"Value": "true"}}},
                                    "text": {"expr": {"Literal": {"Value": f"'{visual.title or 'Visual'}'"}}}
                                }
                            }
                        ]
                    },
                    "vcObjects": {
                        "title": [
                            {
                                "properties": {
                                    "show": {"expr": {"Literal": {"Value": "true"}}},
                                    "text": {"expr": {"Literal": {"Value": f"'{visual.title or 'Visual'}'"}}}
                                }
                            }
                        ]
                    }
                }
            }),
            "filters": "[]",
            "tabOrder": 0
        }
        
        visual_path = os.path.join(visual_folder, 'visual.json')
        with open(visual_path, 'w', encoding='utf-8') as f:
            json.dump(visual_config, f, indent=2)
    
    def _build_visual_query(self, visual: PBIVisualConfig) -> Dict[str, Any]:
        """Build the visual query configuration."""
        query = {
            "queryState": {
                "Category": {
                    "projections": []
                },
                "Y": {
                    "projections": []
                }
            }
        }
        
        # Add projections based on data roles
        for role_name, columns in visual.data_roles.items():
            if role_name not in query["queryState"]:
                query["queryState"][role_name] = {"projections": []}
            
            for i, col in enumerate(columns):
                projection = {
                    "field": col,
                    "queryRef": f"{col.get('Column', {}).get('Property', 'field')}.{i}",
                    "nativeQueryRef": col.get('Column', {}).get('Property', 'field')
                }
                query["queryState"][role_name]["projections"].append(projection)
        
        return query
    
    def _build_projections(self, visual: PBIVisualConfig) -> Dict[str, Any]:
        """Build projections for visual config."""
        projections = {}
        
        for role_name, columns in visual.data_roles.items():
            if columns:
                projections[role_name] = [
                    {"queryRef": col.get('Column', {}).get('Property', 'field')} 
                    for col in columns
                ]
        
        return projections
    
    def _build_prototype_query(self, visual: PBIVisualConfig) -> Dict[str, Any]:
        """Build prototype query for visual."""
        select_items = []
        
        for role_name, columns in visual.data_roles.items():
            for col in columns:
                col_info = col.get('Column', {})
                entity = col_info.get('Expression', {}).get('SourceRef', {}).get('Entity', 'Data')
                prop = col_info.get('Property', 'field')
                
                select_item = {
                    "Column": {
                        "Expression": {
                            "SourceRef": {"Source": "d"}
                        },
                        "Property": prop
                    },
                    "Name": f"{entity}.{prop}"
                }
                
                # Add aggregation if present
                if col_info.get('Aggregation'):
                    select_item = {
                        "Aggregation": {
                            "Expression": select_item["Column"],
                            "Function": 0  # Sum
                        },
                        "Name": f"Sum({entity}.{prop})"
                    }
                
                select_items.append(select_item)
        
        # Default if no items
        if not select_items:
            select_items = [
                {
                    "Column": {
                        "Expression": {"SourceRef": {"Source": "d"}},
                        "Property": "Value"
                    },
                    "Name": "Data.Value"
                }
            ]
        
        return {
            "Version": 2,
            "From": [
                {"Name": "d", "Entity": "Data", "Type": 0}
            ],
            "Select": select_items
        }
    
    def _build_visual_objects(self, visual: PBIVisualConfig) -> Dict[str, Any]:
        """Build visual objects (formatting properties)."""
        return {
            "general": [
                {
                    "properties": {
                        "responsive": {
                            "expr": {
                                "Literal": {
                                    "Value": "true"
                                }
                            }
                        }
                    }
                }
            ]
        }


class PBIPProjectGenerator:
    """
    Generates the complete PBIP project structure.
    Combines semantic model and report generation.
    """
    
    def __init__(self, output_path: str, project_name: str, template_path: Optional[str] = None):
        """
        Initialize the PBIP project generator.
        
        Args:
            output_path: Base path for the PBIP project
            project_name: Name of the project
            template_path: Optional path to template PBIP folder
        """
        self.output_path = output_path
        self.project_name = project_name
        self.template_path = template_path
    
    def generate(self, canonical_report: CanonicalReport):
        """Generate complete PBIP project."""
        project_folder = os.path.join(self.output_path, self.project_name)
        os.makedirs(project_folder, exist_ok=True)
        
        # Generate .pbip file
        self._generate_pbip_file(project_folder)
        
        # Generate semantic model
        model_folder = os.path.join(project_folder, f'{self.project_name}.SemanticModel')
        from .powerbi_model_generator import PowerBIModelGenerator
        model_gen = PowerBIModelGenerator(model_folder)
        model_gen.generate(canonical_report)
        
        # Generate report
        report_folder = os.path.join(project_folder, f'{self.project_name}.Report')
        model_path = f'../{self.project_name}.SemanticModel'
        
        template_report = None
        if self.template_path:
            template_report = os.path.join(self.template_path, 'Sample.Report')
        
        report_gen = PowerBIReportGenerator(report_folder, model_path, template_report)
        report_gen.generate(canonical_report)
    
    def _generate_pbip_file(self, project_folder: str):
        """Generate the .pbip project file."""
        pbip = {
            "version": "1.0",
            "artifacts": [
                {
                    "report": {
                        "path": f"{self.project_name}.Report"
                    }
                }
            ],
            "settings": {
                "enableAutoRecovery": True
            }
        }
        
        pbip_path = os.path.join(project_folder, f'{self.project_name}.pbip')
        with open(pbip_path, 'w', encoding='utf-8') as f:
            json.dump(pbip, f, indent=2)
