# Tableau TWBX to Power BI PBIP Migration Tool

A proof-of-concept system that converts Tableau TWBX dashboards into Power BI PBIP projects without requiring any live data sources.

## Overview

This tool implements a four-stage pipeline for migrating Tableau workbooks to Power BI:

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    MIGRATION PIPELINE ARCHITECTURE                       │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐    ┌────────┐ │
│  │   Stage 1    │    │   Stage 2    │    │   Stage 3    │    │Stage 4 │ │
│  │              │    │              │    │              │    │        │ │
│  │   Tableau    │───►│  Canonical   │───►│  Power BI    │───►│ Report │ │
│  │  Extraction  │    │    Schema    │    │    Model     │    │ Output │ │
│  │              │    │              │    │   (TMDL)     │    │ (PBIR) │ │
│  └──────────────┘    └──────────────┘    └──────────────┘    └────────┘ │
│        │                    │                   │                 │      │
│        ▼                    ▼                   ▼                 ▼      │
│   .twbx/.twb          JSON Schema         .tmdl files       .pbip folder │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

## Features

- **Automated semantic extraction** from Tableau workbooks
- **Schema-driven report generation** for Power BI
- **Visual and layout parity** with approximate mapping
- **Enterprise-ready architecture** with CI/CD-friendly output
- **Detailed migration reports** with confidence scoring

## Requirements

- Python 3.8+
- No external dependencies beyond standard library (lxml optional for enhanced parsing)

## Installation

```bash
# Clone the repository
cd twbx-to-pbip-migration

# Install dependencies (optional)
pip install -r requirements.txt
```

## Usage

### Command Line

```bash
# Migrate a single workbook
python migrate.py dashboard.twbx ./output/

# Migrate all workbooks in a directory
python migrate.py ./tableau_files/ ./powerbi_output/

# Use a template for theming
python migrate.py dashboard.twbx ./output/ --template ./samplepbipfolder/

# Quiet mode (no progress output)
python migrate.py dashboard.twbx ./output/ --quiet
```

### Python API

```python
from src.pipeline import migrate

# Simple migration
reports = migrate(
    input_path="dashboard.twbx",
    output_path="./output/",
    template_path="./samplepbipfolder/",
    save_intermediate=True,
    verbose=True
)

# Check results
for report in reports:
    if report.success:
        print(f"✓ Migrated {report.source_file}")
        print(f"  Visuals: {report.visuals_migrated}")
        print(f"  Measures: {report.measures_translated}")
    else:
        print(f"✗ Failed: {report.error_message}")
```

## Pipeline Stages

### Stage 1: Extract Tableau Semantic Schema

Parses `.twbx` (packaged) or `.twb` (XML) files to extract:

- **Datasources** (logical connections)
- **Tables and columns** (metadata only)
- **Calculated fields** (with formula classification)
- **Worksheets** (visual definitions)
- **Dashboard layouts** (zone positioning)
- **Filters and parameters**

### Stage 2: Generate Canonical BI Schema

Transforms Tableau metadata into a platform-agnostic JSON schema:

- **Dataset definition** (tables, columns, measures)
- **Visual encodings** (category, values, series)
- **Calculation translation** with confidence scoring
- **Unsupported feature flagging**

### Stage 3: Generate Power BI Semantic Model

Creates TMDL (Tabular Model Definition Language) files:

- `model.tmdl` - Model configuration
- `database.tmdl` - Compatibility settings
- `tables/*.tmdl` - Individual table definitions
- `cultures/en-US.tmdl` - Culture settings

**Note**: Models are placeholder/offline - no data connections.

### Stage 4: Generate Power BI Report Artifacts

Creates PBIR (Power BI Report) format files:

- `definition.pbir` - Model reference
- `report.json` - Report settings
- `pages/*.json` - Page definitions
- `visuals/*.json` - Visual configurations

## Visual Type Mapping

| Tableau | Power BI |
|---------|----------|
| Bar | clusteredColumnChart |
| Line | lineChart |
| Area | areaChart |
| Pie | pieChart |
| Text Table | tableEx |
| Crosstab | pivotTable (matrix) |
| Scatter | scatterChart |
| Map | map |
| Treemap | treemap |

## Calculation Translation

### Supported (High Confidence)

- Basic aggregations: `SUM`, `COUNT`, `AVG`, `MIN`, `MAX`
- String functions: `LEN`, `LEFT`, `RIGHT`, `UPPER`, `LOWER`
- Math functions: `ABS`, `ROUND`, `POWER`, `SQRT`
- Date functions: `TODAY`, `NOW`, `YEAR`, `MONTH`, `DAY`
- Logical functions: `IF`, `ISNULL`, `AND`, `OR`

### Flagged (Unsupported)

- **LOD Expressions**: `{FIXED ...}`, `{INCLUDE ...}`, `{EXCLUDE ...}`
- **Table Calculations**: `RUNNING_SUM`, `WINDOW_AVG`, `RANK`, `INDEX`
- **R/Python Scripts**: `SCRIPT_*` functions

## Output Structure

```
output/
├── ProjectName/
│   ├── ProjectName.pbip
│   ├── ProjectName.SemanticModel/
│   │   ├── definition.pbism
│   │   ├── diagramLayout.json
│   │   └── definition/
│   │       ├── model.tmdl
│   │       ├── database.tmdl
│   │       ├── cultures/
│   │       │   └── en-US.tmdl
│   │       └── tables/
│   │           └── Data.tmdl
│   └── ProjectName.Report/
│       ├── definition.pbir
│       ├── StaticResources/
│       └── definition/
│           ├── report.json
│           ├── version.json
│           └── pages/
│               ├── pages.json
│               └── {page_id}/
│                   ├── page.json
│                   └── visuals/
│                       └── {visual_id}/
│                           └── visual.json
├── intermediate/
│   └── ProjectName_canonical.json
└── migration_report.json
```

## Migration Report

The tool generates a machine-readable `migration_report.json`:

```json
{
  "generated_at": "2024-01-15T10:30:00",
  "total_files": 1,
  "successful": 1,
  "failed": 0,
  "migrations": [
    {
      "source_file": "dashboard.twbx",
      "output_folder": "./output/dashboard",
      "summary": {
        "dashboards_migrated": 2,
        "worksheets_migrated": 4,
        "visuals_migrated": 6,
        "tables_created": 1,
        "measures_translated": 5,
        "measures_flagged": 2
      },
      "translated_measures": [...],
      "flagged_measures": [...],
      "unsupported_features": [
        {"type": "lod_expressions", "items": ["Regional Sales Fixed"]},
        {"type": "table_calculations", "items": ["Running Total Sales"]}
      ],
      "success": true
    }
  ]
}
```

## Limitations

This is a proof-of-concept with known limitations:

### Explicit Non-Goals

- ❌ Does NOT connect to real data sources
- ❌ Does NOT publish to Power BI Service
- ❌ Does NOT create PBIX files
- ❌ Does NOT achieve pixel-perfect recreation

### Known Gaps

- Complex calculations may require manual review
- Custom visualizations are not supported
- Advanced formatting is simplified
- Parameter-driven dashboards need manual adjustment

## Design Principles

1. **Deterministic generation** over heuristics
2. **Schema validation** at each pipeline stage
3. **Enterprise-ready** output (CI/CD friendly)
4. **Clear separation** between semantics and deployment
5. **Transparent flagging** of unsupported features

## Testing

```bash
# Run the test suite
python -m tests.test_migration
```

## Architecture

```
src/
├── __init__.py
├── pipeline.py              # Main orchestrator
├── models/
│   ├── tableau_schema.py    # Tableau data models
│   ├── canonical_schema.py  # Intermediate schema
│   └── powerbi_schema.py    # Power BI data models
├── extractors/
│   └── tableau_extractor.py # Stage 1: TWBX parsing
├── transformers/
│   ├── canonical_transformer.py  # Stage 2: Schema transformation
│   └── calculation_translator.py # DAX translation
└── generators/
    ├── powerbi_model_generator.py   # Stage 3: TMDL generation
    └── powerbi_report_generator.py  # Stage 4: PBIR generation
```

## Contributing

This is a proof-of-concept. Contributions welcome for:

- Additional visual type mappings
- Enhanced calculation translation
- Parameter handling
- Custom theme support

## License

MIT License - See LICENSE file for details.
