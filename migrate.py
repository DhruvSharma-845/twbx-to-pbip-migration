#!/usr/bin/env python3
"""
Tableau TWBX to Power BI PBIP Migration Tool

A four-stage pipeline for converting Tableau workbooks to Power BI projects.

Usage:
    python migrate.py input.twbx output_folder/
    python migrate.py input_folder/ output_folder/
    python migrate.py input.twbx output_folder/ --template sample_pbip/
"""

import argparse
import sys
import os

# Add src to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.pipeline import migrate, PipelineConfig, MigrationPipeline


def main():
    parser = argparse.ArgumentParser(
        description='Migrate Tableau TWBX workbooks to Power BI PBIP projects',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s dashboard.twbx ./output/
  %(prog)s ./tableau_files/ ./powerbi_output/
  %(prog)s dashboard.twbx ./output/ --template ./samplepbipfolder/
  %(prog)s dashboard.twbx ./output/ --no-intermediate --quiet

The pipeline performs four stages:
  1. Extract Tableau semantic schema from TWBX/TWB files
  2. Generate platform-agnostic canonical BI schema (JSON)
  3. Generate Power BI semantic model (TMDL files)
  4. Generate Power BI report artifacts (PBIR files)

Output:
  - PBIP project folder that opens in Power BI Desktop
  - migration_report.json with migration details
  - intermediate/ folder with canonical JSON (optional)
        """
    )
    
    parser.add_argument(
        'input',
        help='Path to TWBX/TWB file or directory containing Tableau files'
    )
    
    parser.add_argument(
        'output',
        help='Output directory for generated PBIP projects'
    )
    
    parser.add_argument(
        '--template', '-t',
        help='Path to template PBIP folder for resources (optional)',
        default=None
    )
    
    parser.add_argument(
        '--no-intermediate',
        action='store_true',
        help='Do not save intermediate canonical JSON files'
    )
    
    parser.add_argument(
        '--quiet', '-q',
        action='store_true',
        help='Suppress progress messages'
    )
    
    args = parser.parse_args()
    
    # Validate input
    if not os.path.exists(args.input):
        print(f"Error: Input path does not exist: {args.input}")
        sys.exit(1)
    
    # Create output directory
    os.makedirs(args.output, exist_ok=True)
    
    # Run migration
    print(f"""
╔═══════════════════════════════════════════════════════════════╗
║     Tableau TWBX to Power BI PBIP Migration Pipeline          ║
╠═══════════════════════════════════════════════════════════════╣
║  Stage 1: Extract Tableau Semantic Schema                     ║
║  Stage 2: Generate Canonical BI Schema                        ║
║  Stage 3: Generate Power BI Semantic Model (TMDL)             ║
║  Stage 4: Generate Power BI Report Artifacts (PBIR)           ║
╚═══════════════════════════════════════════════════════════════╝
""")
    
    reports = migrate(
        input_path=args.input,
        output_path=args.output,
        template_path=args.template,
        save_intermediate=not args.no_intermediate,
        verbose=not args.quiet
    )
    
    # Summary
    successful = sum(1 for r in reports if r.success)
    failed = len(reports) - successful
    
    if failed > 0:
        print(f"\n⚠ {failed} migration(s) failed. Check migration_report.json for details.")
        sys.exit(1)
    else:
        print(f"\n✓ All {successful} migration(s) completed successfully!")
        print(f"\nOpen the .pbip file in Power BI Desktop to view the migrated report.")
        sys.exit(0)


if __name__ == '__main__':
    main()
