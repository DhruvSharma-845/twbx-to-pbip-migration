#!/usr/bin/env python3
"""
Test script for the Tableau to Power BI migration pipeline.

This script tests the migration using the sample workbook.
"""

import os
import sys
import shutil
import tempfile

# Add parent to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.pipeline import migrate, PipelineConfig, MigrationPipeline
from src.extractors.tableau_extractor import TableauExtractor
from src.transformers.canonical_transformer import CanonicalTransformer


def test_tableau_extraction():
    """Test Stage 1: Tableau extraction."""
    print("\n" + "="*60)
    print("TEST: Stage 1 - Tableau Extraction")
    print("="*60)
    
    sample_twb = os.path.join(
        os.path.dirname(__file__), 
        'sample_data', 
        'sample_workbook.twb'
    )
    
    if not os.path.exists(sample_twb):
        print(f"✗ Sample TWB not found: {sample_twb}")
        return False
    
    try:
        extractor = TableauExtractor(sample_twb)
        workbook = extractor.extract()
        
        print(f"✓ Workbook name: {workbook.name}")
        print(f"✓ Datasources: {len(workbook.datasources)}")
        print(f"✓ Worksheets: {len(workbook.worksheets)}")
        print(f"✓ Dashboards: {len(workbook.dashboards)}")
        
        # Check datasource details
        for ds in workbook.datasources:
            print(f"  - Datasource: {ds.display_name}")
            print(f"    Tables: {len(ds.tables)}")
            print(f"    Calculated fields: {len(ds.calculated_fields)}")
            
            for calc in ds.calculated_fields:
                print(f"      [{calc.calculation_type.value}] {calc.display_name}: {calc.calculation[:50] if calc.calculation else 'N/A'}...")
        
        # Check worksheets
        for ws in workbook.worksheets:
            print(f"  - Worksheet: {ws.name} ({ws.visual_type.value})")
        
        # Check dashboards
        for db in workbook.dashboards:
            print(f"  - Dashboard: {db.name} ({db.width}x{db.height})")
            print(f"    Zones: {len(db.zones)}")
        
        extractor.cleanup()
        print("\n✓ Stage 1 PASSED")
        return True
        
    except Exception as e:
        print(f"✗ Stage 1 FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_canonical_transformation():
    """Test Stage 2: Canonical transformation."""
    print("\n" + "="*60)
    print("TEST: Stage 2 - Canonical Transformation")
    print("="*60)
    
    sample_twb = os.path.join(
        os.path.dirname(__file__), 
        'sample_data', 
        'sample_workbook.twb'
    )
    
    try:
        # Extract
        extractor = TableauExtractor(sample_twb)
        workbook = extractor.extract()
        
        # Transform
        transformer = CanonicalTransformer()
        report = transformer.transform(workbook)
        
        print(f"✓ Report name: {report.name}")
        print(f"✓ Dataset tables: {len(report.dataset.tables)}")
        print(f"✓ Pages: {len(report.pages)}")
        
        for table in report.dataset.tables:
            print(f"  - Table: {table.name}")
            print(f"    Columns: {len(table.columns)}")
            print(f"    Measures: {len(table.measures)}")
            
            for measure in table.measures:
                print(f"      [{measure.confidence.value}] {measure.display_name}")
                if measure.dax_expression:
                    print(f"        DAX: {measure.dax_expression[:60]}...")
                if measure.unsupported_reason:
                    print(f"        ⚠ Unsupported: {measure.unsupported_reason}")
        
        for page in report.pages:
            print(f"  - Page: {page.display_name}")
            print(f"    Visuals: {len(page.visuals)}")
            for visual in page.visuals:
                print(f"      - {visual.name} ({visual.visual_type.value})")
        
        # Report unsupported features
        if transformer.unsupported_features:
            print("\n  Unsupported features detected:")
            for feature_type, items in transformer.unsupported_features.items():
                if items:
                    print(f"    {feature_type}: {items}")
        
        extractor.cleanup()
        print("\n✓ Stage 2 PASSED")
        return True
        
    except Exception as e:
        print(f"✗ Stage 2 FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_full_migration():
    """Test complete migration pipeline."""
    print("\n" + "="*60)
    print("TEST: Full Migration Pipeline")
    print("="*60)
    
    sample_twb = os.path.join(
        os.path.dirname(__file__), 
        'sample_data', 
        'sample_workbook.twb'
    )
    
    # Create temp output directory
    output_dir = tempfile.mkdtemp(prefix='pbip_migration_test_')
    
    try:
        # Get template path
        template_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            'samplepbipfolder'
        )
        
        # Run migration
        reports = migrate(
            input_path=sample_twb,
            output_path=output_dir,
            template_path=template_path if os.path.exists(template_path) else None,
            save_intermediate=True,
            verbose=True
        )
        
        # Check results
        assert len(reports) == 1, "Expected 1 migration report"
        report = reports[0]
        
        assert report.success, f"Migration failed: {report.error_message}"
        
        print(f"\n✓ Migration successful!")
        print(f"  Dashboards migrated: {report.dashboards_migrated}")
        print(f"  Worksheets migrated: {report.worksheets_migrated}")
        print(f"  Visuals migrated: {report.visuals_migrated}")
        print(f"  Tables created: {report.tables_created}")
        print(f"  Measures translated: {report.measures_translated}")
        print(f"  Measures flagged: {report.measures_flagged}")
        
        # Check output structure
        project_folder = os.path.join(output_dir, 'sample_workbook')
        print(f"\n  Output folder: {project_folder}")
        
        # List generated files
        print("\n  Generated files:")
        for root, dirs, files in os.walk(project_folder):
            level = root.replace(project_folder, '').count(os.sep)
            indent = '  ' * (level + 2)
            print(f"{indent}{os.path.basename(root)}/")
            subindent = '  ' * (level + 3)
            for file in files:
                print(f"{subindent}{file}")
        
        # Verify key files exist
        pbip_file = os.path.join(project_folder, 'sample_workbook.pbip')
        model_folder = os.path.join(project_folder, 'sample_workbook.SemanticModel')
        report_folder = os.path.join(project_folder, 'sample_workbook.Report')
        
        assert os.path.exists(pbip_file), ".pbip file not found"
        assert os.path.exists(model_folder), "SemanticModel folder not found"
        assert os.path.exists(report_folder), "Report folder not found"
        
        # Verify TMDL files
        model_tmdl = os.path.join(model_folder, 'definition', 'model.tmdl')
        assert os.path.exists(model_tmdl), "model.tmdl not found"
        
        # Verify report files
        pbir_file = os.path.join(report_folder, 'definition.pbir')
        assert os.path.exists(pbir_file), "definition.pbir not found"
        
        print("\n✓ Full Migration PASSED")
        print(f"\n  Output preserved at: {output_dir}")
        
        return True
        
    except Exception as e:
        print(f"✗ Full Migration FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        # Don't clean up - keep output for inspection
        pass


def main():
    """Run all tests."""
    print("""
╔═══════════════════════════════════════════════════════════════╗
║       Tableau TWBX to Power BI PBIP Migration Tests           ║
╚═══════════════════════════════════════════════════════════════╝
""")
    
    results = []
    
    # Run tests
    results.append(("Stage 1: Tableau Extraction", test_tableau_extraction()))
    results.append(("Stage 2: Canonical Transformation", test_canonical_transformation()))
    results.append(("Full Migration Pipeline", test_full_migration()))
    
    # Summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    
    passed = sum(1 for _, r in results if r)
    failed = len(results) - passed
    
    for name, result in results:
        status = "✓ PASSED" if result else "✗ FAILED"
        print(f"  {status}: {name}")
    
    print(f"\nTotal: {passed} passed, {failed} failed")
    
    return failed == 0


if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)
