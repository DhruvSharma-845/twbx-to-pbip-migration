"""
Superstore-specific PBIP generator with real data.
Creates a Power BI project with actual Superstore data embedded.
"""

import os
import json
import shutil
import uuid
import pandas as pd
from pathlib import Path
from typing import List, Dict, Any


class SuperstoreGenerator:
    """Generate Power BI PBIP for Superstore with real data."""
    
    def __init__(self, twbx_path: str, output_dir: str, template_dir: str = None):
        self.twbx_path = Path(twbx_path)
        self.output_dir = Path(output_dir)
        self.template_dir = Path(template_dir) if template_dir else None
        self.workbook_name = self.twbx_path.stem
        
    def generate(self) -> str:
        """Generate the full PBIP project."""
        # Extract TWBX
        extract_dir = self._extract_twbx()
        
        # Read data
        orders_df, people_df, returns_df = self._read_data(extract_dir)
        
        # Create PBIP structure
        pbip_dir = self.output_dir / self.workbook_name
        self._create_pbip_structure(pbip_dir)
        
        # Generate semantic model with real data
        self._generate_semantic_model(pbip_dir, orders_df, people_df, returns_df)
        
        # Generate report with visuals
        self._generate_report(pbip_dir)
        
        # Cleanup
        shutil.rmtree(extract_dir)
        
        return str(pbip_dir)
    
    def _extract_twbx(self) -> Path:
        """Extract TWBX file."""
        import zipfile
        extract_dir = self.output_dir / 'temp_extract'
        extract_dir.mkdir(parents=True, exist_ok=True)
        
        with zipfile.ZipFile(self.twbx_path, 'r') as z:
            z.extractall(extract_dir)
        
        return extract_dir
    
    def _read_data(self, extract_dir: Path):
        """Read data from extracted TWBX."""
        xls_path = extract_dir / 'Data' / 'Superstore' / 'Sample - Superstore.xls'
        
        orders_df = pd.read_excel(xls_path, sheet_name='Orders')
        people_df = pd.read_excel(xls_path, sheet_name='People')
        returns_df = pd.read_excel(xls_path, sheet_name='Returns')
        
        return orders_df, people_df, returns_df
    
    def _create_pbip_structure(self, pbip_dir: Path):
        """Create the PBIP folder structure."""
        # Create directories
        dirs = [
            pbip_dir,
            pbip_dir / f'{self.workbook_name}.SemanticModel',
            pbip_dir / f'{self.workbook_name}.SemanticModel' / 'definition',
            pbip_dir / f'{self.workbook_name}.SemanticModel' / 'definition' / 'tables',
            pbip_dir / f'{self.workbook_name}.SemanticModel' / '.pbi',
            pbip_dir / f'{self.workbook_name}.Report',
            pbip_dir / f'{self.workbook_name}.Report' / 'definition',
            pbip_dir / f'{self.workbook_name}.Report' / 'definition' / 'pages',
            pbip_dir / f'{self.workbook_name}.Report' / '.pbi',
        ]
        for d in dirs:
            d.mkdir(parents=True, exist_ok=True)
    
    def _generate_semantic_model(self, pbip_dir: Path, orders_df, people_df, returns_df):
        """Generate the semantic model with real data."""
        model_dir = pbip_dir / f'{self.workbook_name}.SemanticModel'
        definition_dir = model_dir / 'definition'
        tables_dir = definition_dir / 'tables'
        pbi_dir = model_dir / '.pbi'
        
        # Generate definition.pbism
        pbism = {
            "version": "1.0",
            "settings": {}
        }
        with open(model_dir / 'definition.pbism', 'w') as f:
            json.dump(pbism, f, indent=2)
        
        # Generate .pbi files
        with open(pbi_dir / 'localSettings.json', 'w') as f:
            json.dump({"version": "1.0"}, f, indent=2)
        
        with open(pbi_dir / 'editorSettings.json', 'w') as f:
            json.dump({
                "version": "1.0",
                "autodetectRelationships": True,
                "parallelQueryLoading": True,
                "typeDetectionEnabled": True
            }, f, indent=2)
        
        # Generate database.tmdl
        with open(definition_dir / 'database.tmdl', 'w') as f:
            f.write('database\n')
            f.write('\tcompatibilityLevel: 1600\n')
        
        # Generate model.tmdl
        model_content = '''model Model
\tculture: en-US
\tdefaultPowerBIDataSourceVersion: powerBI_V3
\tsourceQueryCulture: en-US
\tdataAccessOptions
\t\tlegacyRedirects
\t\treturnErrorValuesAsNull

annotation __PBI_TimeIntelligenceEnabled = 1

annotation PBI_ProTooling = ["DevMode"]

ref table 'Orders'

ref table 'People'

ref table 'Returns'
'''
        with open(definition_dir / 'model.tmdl', 'w') as f:
            f.write(model_content)
        
        # Generate tables with real data
        self._generate_orders_table(tables_dir, orders_df)
        self._generate_people_table(tables_dir, people_df)
        self._generate_returns_table(tables_dir, returns_df)
        
        # Generate diagramLayout.json
        with open(model_dir / 'diagramLayout.json', 'w') as f:
            json.dump({"version": "1.0", "diagrams": []}, f, indent=2)
    
    def _generate_orders_table(self, tables_dir: Path, df: pd.DataFrame):
        """Generate Orders table as a calculated table with DAX DATATABLE."""
        # Take first 30 rows for sample data (keep it manageable)
        sample_df = df.head(30)
        
        # Generate DAX DATATABLE expression
        dax_rows = self._generate_orders_dax_rows(sample_df)
        
        content = f'''table 'Orders' =
\t\tDATATABLE(
\t\t\t"Row ID", INTEGER,
\t\t\t"Order ID", STRING,
\t\t\t"Order Date", DATETIME,
\t\t\t"Ship Date", DATETIME,
\t\t\t"Ship Mode", STRING,
\t\t\t"Customer ID", STRING,
\t\t\t"Customer Name", STRING,
\t\t\t"Segment", STRING,
\t\t\t"Country", STRING,
\t\t\t"City", STRING,
\t\t\t"State", STRING,
\t\t\t"Postal Code", STRING,
\t\t\t"Region", STRING,
\t\t\t"Product ID", STRING,
\t\t\t"Category", STRING,
\t\t\t"Sub-Category", STRING,
\t\t\t"Product Name", STRING,
\t\t\t"Sales", DOUBLE,
\t\t\t"Quantity", INTEGER,
\t\t\t"Discount", DOUBLE,
\t\t\t"Profit", DOUBLE,
\t\t\t{{
{dax_rows}
\t\t\t}}
\t\t)
\tlineageTag: {str(uuid.uuid4())}

\tcolumn 'Row ID'
\t\tdataType: int64
\t\tlineageTag: {str(uuid.uuid4())}
\t\tsummarizeBy: none
\t\tsourceColumn: Row ID

\t\tannotation SummarizationSetBy = Automatic

\tcolumn 'Order ID'
\t\tdataType: string
\t\tlineageTag: {str(uuid.uuid4())}
\t\tsummarizeBy: none
\t\tsourceColumn: Order ID

\t\tannotation SummarizationSetBy = Automatic

\tcolumn 'Order Date'
\t\tdataType: dateTime
\t\tlineageTag: {str(uuid.uuid4())}
\t\tsummarizeBy: none
\t\tsourceColumn: Order Date

\t\tannotation SummarizationSetBy = Automatic

\tcolumn 'Ship Date'
\t\tdataType: dateTime
\t\tlineageTag: {str(uuid.uuid4())}
\t\tsummarizeBy: none
\t\tsourceColumn: Ship Date

\t\tannotation SummarizationSetBy = Automatic

\tcolumn 'Ship Mode'
\t\tdataType: string
\t\tlineageTag: {str(uuid.uuid4())}
\t\tsummarizeBy: none
\t\tsourceColumn: Ship Mode

\t\tannotation SummarizationSetBy = Automatic

\tcolumn 'Customer ID'
\t\tdataType: string
\t\tlineageTag: {str(uuid.uuid4())}
\t\tsummarizeBy: none
\t\tsourceColumn: Customer ID

\t\tannotation SummarizationSetBy = Automatic

\tcolumn 'Customer Name'
\t\tdataType: string
\t\tlineageTag: {str(uuid.uuid4())}
\t\tsummarizeBy: none
\t\tsourceColumn: Customer Name

\t\tannotation SummarizationSetBy = Automatic

\tcolumn 'Segment'
\t\tdataType: string
\t\tlineageTag: {str(uuid.uuid4())}
\t\tsummarizeBy: none
\t\tsourceColumn: Segment

\t\tannotation SummarizationSetBy = Automatic

\tcolumn 'Country'
\t\tdataType: string
\t\tlineageTag: {str(uuid.uuid4())}
\t\tsummarizeBy: none
\t\tsourceColumn: Country

\t\tannotation SummarizationSetBy = Automatic

\tcolumn 'City'
\t\tdataType: string
\t\tlineageTag: {str(uuid.uuid4())}
\t\tsummarizeBy: none
\t\tsourceColumn: City

\t\tannotation SummarizationSetBy = Automatic

\tcolumn 'State'
\t\tdataType: string
\t\tlineageTag: {str(uuid.uuid4())}
\t\tsummarizeBy: none
\t\tsourceColumn: State

\t\tannotation SummarizationSetBy = Automatic

\tcolumn 'Postal Code'
\t\tdataType: string
\t\tlineageTag: {str(uuid.uuid4())}
\t\tsummarizeBy: none
\t\tsourceColumn: Postal Code

\t\tannotation SummarizationSetBy = Automatic

\tcolumn 'Region'
\t\tdataType: string
\t\tlineageTag: {str(uuid.uuid4())}
\t\tsummarizeBy: none
\t\tsourceColumn: Region

\t\tannotation SummarizationSetBy = Automatic

\tcolumn 'Product ID'
\t\tdataType: string
\t\tlineageTag: {str(uuid.uuid4())}
\t\tsummarizeBy: none
\t\tsourceColumn: Product ID

\t\tannotation SummarizationSetBy = Automatic

\tcolumn 'Category'
\t\tdataType: string
\t\tlineageTag: {str(uuid.uuid4())}
\t\tsummarizeBy: none
\t\tsourceColumn: Category

\t\tannotation SummarizationSetBy = Automatic

\tcolumn 'Sub-Category'
\t\tdataType: string
\t\tlineageTag: {str(uuid.uuid4())}
\t\tsummarizeBy: none
\t\tsourceColumn: Sub-Category

\t\tannotation SummarizationSetBy = Automatic

\tcolumn 'Product Name'
\t\tdataType: string
\t\tlineageTag: {str(uuid.uuid4())}
\t\tsummarizeBy: none
\t\tsourceColumn: Product Name

\t\tannotation SummarizationSetBy = Automatic

\tcolumn 'Sales'
\t\tdataType: double
\t\tlineageTag: {str(uuid.uuid4())}
\t\tsummarizeBy: sum
\t\tsourceColumn: Sales

\t\tannotation SummarizationSetBy = Automatic

\tcolumn 'Quantity'
\t\tdataType: int64
\t\tlineageTag: {str(uuid.uuid4())}
\t\tsummarizeBy: sum
\t\tsourceColumn: Quantity

\t\tannotation SummarizationSetBy = Automatic

\tcolumn 'Discount'
\t\tdataType: double
\t\tlineageTag: {str(uuid.uuid4())}
\t\tsummarizeBy: none
\t\tsourceColumn: Discount

\t\tannotation SummarizationSetBy = Automatic

\tcolumn 'Profit'
\t\tdataType: double
\t\tlineageTag: {str(uuid.uuid4())}
\t\tsummarizeBy: sum
\t\tsourceColumn: Profit

\t\tannotation SummarizationSetBy = Automatic

\tmeasure 'Total Sales' = SUM('Orders'[Sales])
\t\tlineageTag: {str(uuid.uuid4())}
\t\tformatString: "$#,##0.00"

\tmeasure 'Total Profit' = SUM('Orders'[Profit])
\t\tlineageTag: {str(uuid.uuid4())}
\t\tformatString: "$#,##0.00"

\tmeasure 'Total Quantity' = SUM('Orders'[Quantity])
\t\tlineageTag: {str(uuid.uuid4())}
\t\tformatString: "#,##0"

\tmeasure 'Profit Ratio' = DIVIDE(SUM('Orders'[Profit]), SUM('Orders'[Sales]), 0)
\t\tlineageTag: {str(uuid.uuid4())}
\t\tformatString: "0.00%"

\tmeasure 'Avg Discount' = AVERAGE('Orders'[Discount])
\t\tlineageTag: {str(uuid.uuid4())}
\t\tformatString: "0.00%"

\tmeasure 'Order Count' = DISTINCTCOUNT('Orders'[Order ID])
\t\tlineageTag: {str(uuid.uuid4())}
\t\tformatString: "#,##0"

\tannotation PBI_NavigationStepName = Source
\tannotation PBI_ResultType = Table
'''
        
        with open(tables_dir / 'Orders.tmdl', 'w') as f:
            f.write(content)
    
    def _generate_orders_dax_rows(self, df: pd.DataFrame) -> str:
        """Generate DAX DATATABLE rows with real order data."""
        rows = []
        for _, row in df.iterrows():
            # Format dates for DAX DATE function
            order_date = f'DATE({row["Order Date"].year}, {row["Order Date"].month}, {row["Order Date"].day})'
            ship_date = f'DATE({row["Ship Date"].year}, {row["Ship Date"].month}, {row["Ship Date"].day})'
            
            # Escape quotes in strings (double quotes become double-double quotes in DAX)
            product_name = str(row['Product Name']).replace('"', '""')
            customer_name = str(row['Customer Name']).replace('"', '""')
            city = str(row['City']).replace('"', '""')
            
            postal_code = str(int(row['Postal Code'])) if pd.notna(row['Postal Code']) else ""
            
            row_data = (
                f'\t\t\t\t{{{int(row["Row ID"])}, '
                f'"{row["Order ID"]}", '
                f'{order_date}, '
                f'{ship_date}, '
                f'"{row["Ship Mode"]}", '
                f'"{row["Customer ID"]}", '
                f'"{customer_name}", '
                f'"{row["Segment"]}", '
                f'"{row["Country/Region"]}", '
                f'"{city}", '
                f'"{row["State/Province"]}", '
                f'"{postal_code}", '
                f'"{row["Region"]}", '
                f'"{row["Product ID"]}", '
                f'"{row["Category"]}", '
                f'"{row["Sub-Category"]}", '
                f'"{product_name}", '
                f'{row["Sales"]:.2f}, '
                f'{int(row["Quantity"])}, '
                f'{row["Discount"]:.2f}, '
                f'{row["Profit"]:.4f}}}'
            )
            rows.append(row_data)
        
        return ',\n'.join(rows)
    
    def _generate_people_table(self, tables_dir: Path, df: pd.DataFrame):
        """Generate People table using DAX DATATABLE."""
        # Generate DAX DATATABLE rows
        rows = []
        for _, row in df.iterrows():
            rows.append(f'\t\t\t\t{{"{row["Regional Manager"]}", "{row["Region"]}"}}')
        dax_rows = ',\n'.join(rows)
        
        content = f'''table 'People' =
\t\tDATATABLE(
\t\t\t"Regional Manager", STRING,
\t\t\t"Region", STRING,
\t\t\t{{
{dax_rows}
\t\t\t}}
\t\t)
\tlineageTag: {str(uuid.uuid4())}

\tcolumn 'Regional Manager'
\t\tdataType: string
\t\tlineageTag: {str(uuid.uuid4())}
\t\tsummarizeBy: none
\t\tsourceColumn: Regional Manager

\t\tannotation SummarizationSetBy = Automatic

\tcolumn 'Region'
\t\tdataType: string
\t\tlineageTag: {str(uuid.uuid4())}
\t\tsummarizeBy: none
\t\tsourceColumn: Region

\t\tannotation SummarizationSetBy = Automatic

\tannotation PBI_NavigationStepName = Source
\tannotation PBI_ResultType = Table
'''
        
        with open(tables_dir / 'People.tmdl', 'w') as f:
            f.write(content)
    
    def _generate_returns_table(self, tables_dir: Path, df: pd.DataFrame):
        """Generate Returns table using DAX DATATABLE."""
        sample_df = df.head(30)
        
        # Generate DAX DATATABLE rows
        rows = []
        for _, row in sample_df.iterrows():
            rows.append(f'\t\t\t\t{{"{row["Order ID"]}", "{row["Returned"]}"}}')
        dax_rows = ',\n'.join(rows)
        
        content = f'''table 'Returns' =
\t\tDATATABLE(
\t\t\t"Order ID", STRING,
\t\t\t"Returned", STRING,
\t\t\t{{
{dax_rows}
\t\t\t}}
\t\t)
\tlineageTag: {str(uuid.uuid4())}

\tcolumn 'Order ID'
\t\tdataType: string
\t\tlineageTag: {str(uuid.uuid4())}
\t\tsummarizeBy: none
\t\tsourceColumn: Order ID

\t\tannotation SummarizationSetBy = Automatic

\tcolumn 'Returned'
\t\tdataType: string
\t\tlineageTag: {str(uuid.uuid4())}
\t\tsummarizeBy: none
\t\tsourceColumn: Returned

\t\tannotation SummarizationSetBy = Automatic

\tannotation PBI_NavigationStepName = Source
\tannotation PBI_ResultType = Table
'''
        
        with open(tables_dir / 'Returns.tmdl', 'w') as f:
            f.write(content)
    
    def _generate_report(self, pbip_dir: Path):
        """Generate the report with pages and visuals."""
        report_dir = pbip_dir / f'{self.workbook_name}.Report'
        definition_dir = report_dir / 'definition'
        pages_dir = definition_dir / 'pages'
        pbi_dir = report_dir / '.pbi'
        
        # Generate definition.pbir
        pbir = {
            "version": "1.0",
            "datasetReference": {
                "byPath": {
                    "path": f"../{self.workbook_name}.SemanticModel"
                }
            }
        }
        with open(report_dir / 'definition.pbir', 'w') as f:
            json.dump(pbir, f, indent=2)
        
        # Generate .pbi files
        with open(pbi_dir / 'localSettings.json', 'w') as f:
            json.dump({"version": "1.0"}, f, indent=2)
        
        # Generate report.json
        report_json = {
            "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/report/1.0.0/schema.json",
            "themeCollection": {
                "baseTheme": {
                    "name": "CY24SU08",
                    "version": "5.0.0",
                    "type": "SharedResources"
                }
            },
            "layoutOptimization": "None"
        }
        with open(definition_dir / 'report.json', 'w') as f:
            json.dump(report_json, f, indent=2)
        
        # Generate version.json
        version_json = {
            "version": "1.0"
        }
        with open(definition_dir / 'version.json', 'w') as f:
            json.dump(version_json, f, indent=2)
        
        # Generate pages based on Tableau dashboards
        pages = [
            {'id': 'overview', 'name': 'Overview', 'displayName': 'Overview'},
            {'id': 'product', 'name': 'Product', 'displayName': 'Product'},
            {'id': 'customers', 'name': 'Customers', 'displayName': 'Customers'},
            {'id': 'performance', 'name': 'Performance', 'displayName': 'Performance'},
            {'id': 'forecast', 'name': 'Forecast', 'displayName': 'Forecast'},
            {'id': 'commission', 'name': 'Commission Model', 'displayName': 'Commission Model'},
        ]
        
        for page in pages:
            page_dir = pages_dir / page['id']
            page_dir.mkdir(parents=True, exist_ok=True)
            
            page_json = {
                "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/page/2.0.0/schema.json",
                "name": page['id'],
                "displayName": page['displayName'],
                "displayOption": "FitToPage",
                "height": 720,
                "width": 1280
            }
            with open(page_dir / 'page.json', 'w') as f:
                json.dump(page_json, f, indent=2)
        
        # Generate .pbip file
        pbip = {
            "version": "1.0",
            "artifacts": [
                {
                    "report": {
                        "path": f"{self.workbook_name}.Report"
                    }
                }
            ],
            "settings": {
                "enableAutoRecovery": True
            }
        }
        with open(pbip_dir / f'{self.workbook_name}.pbip', 'w') as f:
            json.dump(pbip, f, indent=2)


if __name__ == '__main__':
    import sys
    if len(sys.argv) < 3:
        print("Usage: python superstore_generator.py <twbx_path> <output_dir>")
        sys.exit(1)
    
    generator = SuperstoreGenerator(sys.argv[1], sys.argv[2])
    output = generator.generate()
    print(f"Generated PBIP at: {output}")
