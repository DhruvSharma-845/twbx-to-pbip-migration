"""
Main Migration Pipeline

Orchestrates the four-stage Tableau TWBX to Power BI PBIP migration.

Stages:
1. Extract Tableau Semantic Schema
2. Generate Canonical BI Schema
3. Generate Power BI Semantic Model
4. Generate Power BI Report Artifacts
"""

import os
import json
import shutil
from datetime import datetime
from typing import Optional, List
from dataclasses import dataclass

from .extractors.tableau_extractor import TableauExtractor
from .transformers.canonical_transformer import CanonicalTransformer
from .generators.powerbi_report_generator import PBIPProjectGenerator
from .models.canonical_schema import (
    CanonicalReport, MigrationReport, ConfidenceLevel
)


@dataclass
class PipelineConfig:
    """Configuration for the migration pipeline."""
    input_path: str  # Path to TWBX file or directory
    output_path: str  # Output directory for PBIP projects
    template_path: Optional[str] = None  # Optional PBIP template
    save_intermediate: bool = True  # Save intermediate JSON files
    verbose: bool = True  # Enable verbose logging


class MigrationPipeline:
    """
    Orchestrates the Tableau to Power BI migration pipeline.
    
    This is the main entry point for the migration process.
    """
    
    def __init__(self, config: PipelineConfig):
        self.config = config
        self.migration_reports: List[MigrationReport] = []
    
    def run(self) -> List[MigrationReport]:
        """
        Run the complete migration pipeline.
        
        Returns:
            List of MigrationReport for each processed file
        """
        # Find all TWBX files
        twbx_files = self._find_twbx_files()
        
        if not twbx_files:
            print(f"No .twbx files found in {self.config.input_path}")
            return []
        
        print(f"Found {len(twbx_files)} Tableau workbook(s) to migrate")
        
        # Process each file
        for twbx_file in twbx_files:
            report = self._process_file(twbx_file)
            self.migration_reports.append(report)
        
        # Generate summary report
        self._generate_summary_report()
        
        return self.migration_reports
    
    def _find_twbx_files(self) -> List[str]:
        """Find all TWBX files in the input path."""
        if os.path.isfile(self.config.input_path):
            if self.config.input_path.endswith(('.twbx', '.twb')):
                return [self.config.input_path]
            return []
        
        twbx_files = []
        for root, dirs, files in os.walk(self.config.input_path):
            for file in files:
                if file.endswith(('.twbx', '.twb')):
                    twbx_files.append(os.path.join(root, file))
        
        return twbx_files
    
    def _process_file(self, twbx_file: str) -> MigrationReport:
        """Process a single Tableau workbook file."""
        file_name = os.path.splitext(os.path.basename(twbx_file))[0]
        project_name = self._sanitize_project_name(file_name)
        
        self._log(f"\n{'='*60}")
        self._log(f"Processing: {file_name}")
        self._log(f"{'='*60}")
        
        migration_report = MigrationReport(
            source_file=twbx_file,
            output_folder=os.path.join(self.config.output_path, project_name)
        )
        
        try:
            # Stage 1: Extract Tableau Schema
            self._log("\nStage 1: Extracting Tableau semantic schema...")
            extractor = TableauExtractor(twbx_file)
            tableau_workbook = extractor.extract()
            
            self._log(f"  - Extracted {len(tableau_workbook.datasources)} datasource(s)")
            self._log(f"  - Extracted {len(tableau_workbook.worksheets)} worksheet(s)")
            self._log(f"  - Extracted {len(tableau_workbook.dashboards)} dashboard(s)")
            
            # Stage 2: Generate Canonical Schema
            self._log("\nStage 2: Generating canonical BI schema...")
            transformer = CanonicalTransformer()
            canonical_report = transformer.transform(tableau_workbook)
            
            self._log(f"  - Created {len(canonical_report.dataset.tables)} table(s)")
            self._log(f"  - Created {len(canonical_report.pages)} page(s)")
            
            # Save intermediate if requested
            if self.config.save_intermediate:
                self._save_canonical_schema(canonical_report, project_name)
            
            # Track measures
            self._track_measures(canonical_report, migration_report)
            
            # Track unsupported features
            migration_report.unsupported_features = [
                {"type": k, "items": v} 
                for k, v in transformer.unsupported_features.items() if v
            ]
            
            # Stage 3 & 4: Generate Power BI Artifacts
            self._log("\nStage 3-4: Generating Power BI PBIP project...")
            generator = PBIPProjectGenerator(
                output_path=self.config.output_path,
                project_name=project_name,
                template_path=self.config.template_path
            )
            generator.generate(canonical_report)
            
            # Update migration report counts
            migration_report.dashboards_migrated = len(canonical_report.pages)
            migration_report.worksheets_migrated = len(tableau_workbook.worksheets)
            migration_report.visuals_migrated = sum(
                len(page.visuals) for page in canonical_report.pages
            )
            migration_report.tables_created = len(canonical_report.dataset.tables)
            migration_report.success = True
            
            self._log(f"\n✓ Migration completed successfully!")
            self._log(f"  Output: {migration_report.output_folder}")
            
            # Cleanup
            extractor.cleanup()
            
        except Exception as e:
            migration_report.success = False
            migration_report.error_message = str(e)
            self._log(f"\n✗ Migration failed: {e}")
            import traceback
            traceback.print_exc()
        
        return migration_report
    
    def _track_measures(self, report: CanonicalReport, migration_report: MigrationReport):
        """Track translated and flagged measures."""
        for table in report.dataset.tables:
            for measure in table.measures:
                measure_info = measure.to_dict()
                
                if measure.confidence in [ConfidenceLevel.HIGH, ConfidenceLevel.MEDIUM]:
                    migration_report.translated_measures.append(measure_info)
                    migration_report.measures_translated += 1
                else:
                    migration_report.flagged_measures.append(measure_info)
                    migration_report.measures_flagged += 1
    
    def _save_canonical_schema(self, report: CanonicalReport, project_name: str):
        """Save the canonical schema as intermediate JSON."""
        intermediate_path = os.path.join(
            self.config.output_path, 'intermediate', f'{project_name}_canonical.json'
        )
        os.makedirs(os.path.dirname(intermediate_path), exist_ok=True)
        
        # Convert to serializable format
        schema = self._serialize_canonical_report(report)
        
        with open(intermediate_path, 'w', encoding='utf-8') as f:
            json.dump(schema, f, indent=2)
        
        self._log(f"  - Saved canonical schema to: {intermediate_path}")
    
    def _serialize_canonical_report(self, report: CanonicalReport) -> dict:
        """Serialize canonical report to dictionary."""
        return {
            "name": report.name,
            "source_file": report.source_file,
            "dataset": {
                "name": report.dataset.name,
                "tables": [
                    {
                        "name": table.name,
                        "display_name": table.display_name,
                        "columns": [
                            {
                                "name": col.name,
                                "display_name": col.display_name,
                                "data_type": col.data_type.value
                            }
                            for col in table.columns
                        ],
                        "measures": [m.to_dict() for m in table.measures]
                    }
                    for table in report.dataset.tables
                ]
            },
            "pages": [
                {
                    "id": page.id,
                    "name": page.name,
                    "display_name": page.display_name,
                    "width": page.width,
                    "height": page.height,
                    "visuals": [
                        {
                            "id": visual.id,
                            "name": visual.name,
                            "type": visual.visual_type.value,
                            "x": visual.x,
                            "y": visual.y,
                            "width": visual.width,
                            "height": visual.height,
                            "confidence": visual.confidence.value,
                            "unsupported_features": visual.unsupported_features
                        }
                        for visual in page.visuals
                    ]
                }
                for page in report.pages
            ],
            "migration_warnings": report.migration_warnings,
            "unsupported_features": report.unsupported_features
        }
    
    def _generate_summary_report(self):
        """Generate a summary report of all migrations."""
        summary = {
            "generated_at": datetime.now().isoformat(),
            "total_files": len(self.migration_reports),
            "successful": sum(1 for r in self.migration_reports if r.success),
            "failed": sum(1 for r in self.migration_reports if not r.success),
            "migrations": [r.to_dict() for r in self.migration_reports]
        }
        
        summary_path = os.path.join(self.config.output_path, 'migration_report.json')
        with open(summary_path, 'w', encoding='utf-8') as f:
            json.dump(summary, f, indent=2)
        
        self._log(f"\n{'='*60}")
        self._log("MIGRATION SUMMARY")
        self._log(f"{'='*60}")
        self._log(f"Total files processed: {summary['total_files']}")
        self._log(f"Successful: {summary['successful']}")
        self._log(f"Failed: {summary['failed']}")
        self._log(f"\nReport saved to: {summary_path}")
    
    def _sanitize_project_name(self, name: str) -> str:
        """Sanitize the project name for use in folder/file names."""
        # Replace spaces and special characters
        sanitized = name.replace(' ', '_')
        sanitized = ''.join(c for c in sanitized if c.isalnum() or c in '_-')
        return sanitized or 'MigratedProject'
    
    def _log(self, message: str):
        """Log a message if verbose mode is enabled."""
        if self.config.verbose:
            print(message)


def migrate(
    input_path: str,
    output_path: str,
    template_path: Optional[str] = None,
    save_intermediate: bool = True,
    verbose: bool = True
) -> List[MigrationReport]:
    """
    Convenience function to run the migration pipeline.
    
    Args:
        input_path: Path to TWBX file or directory containing TWBX files
        output_path: Output directory for generated PBIP projects
        template_path: Optional path to a template PBIP folder for resources
        save_intermediate: Whether to save intermediate canonical JSON
        verbose: Whether to print progress messages
        
    Returns:
        List of MigrationReport objects
    """
    config = PipelineConfig(
        input_path=input_path,
        output_path=output_path,
        template_path=template_path,
        save_intermediate=save_intermediate,
        verbose=verbose
    )
    
    pipeline = MigrationPipeline(config)
    return pipeline.run()
