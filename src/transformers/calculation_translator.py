"""
Tableau Calculation to DAX Translator

Translates Tableau calculated field expressions to DAX.
Includes confidence scoring and unsupported feature flagging.
"""

import re
from typing import Tuple, Optional, List
from ..models.canonical_schema import ConfidenceLevel, AggregationType


class CalculationTranslator:
    """
    Translates Tableau calculations to DAX expressions.
    
    Handles:
    - Basic aggregations (SUM, COUNT, AVG, MIN, MAX)
    - Simple arithmetic
    - Basic string functions
    
    Flags as unsupported:
    - LOD expressions (FIXED, INCLUDE, EXCLUDE)
    - Table calculations (LOOKUP, RUNNING_*, WINDOW_*, RANK)
    - Complex nested expressions
    """
    
    # Aggregation mappings
    AGGREGATION_MAP = {
        'SUM': ('SUM', AggregationType.SUM),
        'COUNT': ('COUNT', AggregationType.COUNT),
        'COUNTD': ('DISTINCTCOUNT', AggregationType.COUNTD),
        'AVG': ('AVERAGE', AggregationType.AVG),
        'AVERAGE': ('AVERAGE', AggregationType.AVG),
        'MIN': ('MIN', AggregationType.MIN),
        'MAX': ('MAX', AggregationType.MAX),
        'MEDIAN': ('MEDIAN', AggregationType.MEDIAN),
        'STDEV': ('STDEV.S', AggregationType.STDEV),
        'VAR': ('VAR.S', AggregationType.VAR),
        'ATTR': ('SELECTEDVALUE', AggregationType.NONE),
    }
    
    # Basic function mappings
    FUNCTION_MAP = {
        # String functions
        'LEN': 'LEN',
        'LEFT': 'LEFT',
        'RIGHT': 'RIGHT',
        'MID': 'MID',
        'UPPER': 'UPPER',
        'LOWER': 'LOWER',
        'TRIM': 'TRIM',
        'LTRIM': 'TRIM',  # DAX doesn't have LTRIM
        'RTRIM': 'TRIM',  # DAX doesn't have RTRIM
        'CONTAINS': 'CONTAINSSTRING',
        'REPLACE': 'SUBSTITUTE',
        'SPACE': 'REPT',  # REPT(" ", n)
        'SPLIT': None,  # No direct equivalent
        
        # Date functions
        'TODAY': 'TODAY',
        'NOW': 'NOW',
        'YEAR': 'YEAR',
        'MONTH': 'MONTH',
        'DAY': 'DAY',
        'DATEADD': 'DATEADD',
        'DATEDIFF': 'DATEDIFF',
        'DATEPART': None,  # Needs mapping to YEAR/MONTH/DAY
        'DATETRUNC': None,  # No direct equivalent
        'DATENAME': 'FORMAT',  # Needs transformation
        
        # Math functions
        'ABS': 'ABS',
        'ROUND': 'ROUND',
        'CEILING': 'CEILING',
        'FLOOR': 'FLOOR',
        'POWER': 'POWER',
        'SQRT': 'SQRT',
        'LOG': 'LOG',
        'LN': 'LN',
        'EXP': 'EXP',
        'SIGN': 'SIGN',
        'DIV': 'DIVIDE',
        'ZN': 'IF',  # ZN([x]) -> IF(ISBLANK([x]), 0, [x])
        
        # Logical functions
        'IF': 'IF',
        'IIF': 'IF',
        'CASE': 'SWITCH',
        'IFNULL': 'IF',  # IFNULL(x, y) -> IF(ISBLANK(x), y, x)
        'ISNULL': 'ISBLANK',
        'AND': 'AND',
        'OR': 'OR',
        'NOT': 'NOT',
        
        # Type conversion
        'INT': 'INT',
        'FLOAT': 'VALUE',
        'STR': 'FORMAT',
        'DATE': 'DATE',
        'DATETIME': 'DATETIME',
    }
    
    # Unsupported functions (table calcs, LOD)
    UNSUPPORTED_FUNCTIONS = {
        # LOD expressions
        'FIXED': 'LOD Expression - FIXED',
        'INCLUDE': 'LOD Expression - INCLUDE', 
        'EXCLUDE': 'LOD Expression - EXCLUDE',
        
        # Table calculations
        'LOOKUP': 'Table Calculation - LOOKUP',
        'PREVIOUS_VALUE': 'Table Calculation - PREVIOUS_VALUE',
        'FIRST': 'Table Calculation - FIRST',
        'LAST': 'Table Calculation - LAST',
        'INDEX': 'Table Calculation - INDEX',
        'SIZE': 'Table Calculation - SIZE',
        'RUNNING_SUM': 'Table Calculation - RUNNING_SUM',
        'RUNNING_AVG': 'Table Calculation - RUNNING_AVG',
        'RUNNING_COUNT': 'Table Calculation - RUNNING_COUNT',
        'RUNNING_MIN': 'Table Calculation - RUNNING_MIN',
        'RUNNING_MAX': 'Table Calculation - RUNNING_MAX',
        'WINDOW_SUM': 'Table Calculation - WINDOW_SUM',
        'WINDOW_AVG': 'Table Calculation - WINDOW_AVG',
        'WINDOW_MIN': 'Table Calculation - WINDOW_MIN',
        'WINDOW_MAX': 'Table Calculation - WINDOW_MAX',
        'WINDOW_COUNT': 'Table Calculation - WINDOW_COUNT',
        'WINDOW_MEDIAN': 'Table Calculation - WINDOW_MEDIAN',
        'WINDOW_STDEV': 'Table Calculation - WINDOW_STDEV',
        'WINDOW_VAR': 'Table Calculation - WINDOW_VAR',
        'RANK': 'Table Calculation - RANK',
        'RANK_DENSE': 'Table Calculation - RANK_DENSE',
        'RANK_MODIFIED': 'Table Calculation - RANK_MODIFIED',
        'RANK_PERCENTILE': 'Table Calculation - RANK_PERCENTILE',
        'RANK_UNIQUE': 'Table Calculation - RANK_UNIQUE',
        'TOTAL': 'Table Calculation - TOTAL',
        'SCRIPT_BOOL': 'R/Python Integration',
        'SCRIPT_INT': 'R/Python Integration',
        'SCRIPT_REAL': 'R/Python Integration',
        'SCRIPT_STR': 'R/Python Integration',
    }
    
    def __init__(self, table_name: str = "Data"):
        self.table_name = table_name
        self._warnings: List[str] = []
    
    def translate(self, tableau_formula: str) -> Tuple[Optional[str], ConfidenceLevel, Optional[str]]:
        """
        Translate a Tableau formula to DAX.
        
        Args:
            tableau_formula: The Tableau calculated field formula
            
        Returns:
            Tuple of (dax_expression, confidence, unsupported_reason)
        """
        self._warnings = []
        
        if not tableau_formula:
            return None, ConfidenceLevel.HIGH, None
        
        formula = tableau_formula.strip()
        
        # Check for unsupported constructs first
        unsupported_reason = self._check_unsupported(formula)
        if unsupported_reason:
            return None, ConfidenceLevel.UNSUPPORTED, unsupported_reason
        
        # Try to translate
        try:
            dax_expr, confidence = self._translate_expression(formula)
            return dax_expr, confidence, None
        except Exception as e:
            return None, ConfidenceLevel.LOW, f"Translation error: {str(e)}"
    
    def _check_unsupported(self, formula: str) -> Optional[str]:
        """Check for unsupported Tableau constructs."""
        formula_upper = formula.upper()
        
        # Check for LOD expressions (curly braces syntax)
        if '{' in formula and '}' in formula:
            lod_match = re.search(r'\{\s*(FIXED|INCLUDE|EXCLUDE)', formula, re.IGNORECASE)
            if lod_match:
                return f"LOD Expression ({lod_match.group(1).upper()}) - Not supported in DAX"
        
        # Check for unsupported functions
        for func, reason in self.UNSUPPORTED_FUNCTIONS.items():
            pattern = rf'\b{func}\s*\('
            if re.search(pattern, formula_upper):
                return reason
        
        return None
    
    def _translate_expression(self, formula: str) -> Tuple[str, ConfidenceLevel]:
        """Translate a Tableau expression to DAX."""
        result = formula
        confidence = ConfidenceLevel.HIGH
        
        # Replace field references [Field Name] with table qualified references
        result = self._qualify_field_references(result)
        
        # Translate aggregations
        result, agg_conf = self._translate_aggregations(result)
        if agg_conf.value < confidence.value:
            confidence = agg_conf
        
        # Translate functions
        result, func_conf = self._translate_functions(result)
        if func_conf.value < confidence.value:
            confidence = func_conf
        
        # Translate operators
        result = self._translate_operators(result)
        
        # Translate conditional expressions
        result, cond_conf = self._translate_conditionals(result)
        if cond_conf.value < confidence.value:
            confidence = cond_conf
        
        return result, confidence
    
    def _qualify_field_references(self, formula: str) -> str:
        """Add table qualification to field references."""
        # Pattern to match [FieldName] but not already qualified Table[Field]
        def replace_field(match):
            field_name = match.group(1)
            return f"'{self.table_name}'[{field_name}]"
        
        # Only replace if not already table-qualified
        result = re.sub(r'(?<!\w)\[([^\]]+)\]', replace_field, formula)
        return result
    
    def _translate_aggregations(self, formula: str) -> Tuple[str, ConfidenceLevel]:
        """Translate Tableau aggregations to DAX."""
        result = formula
        confidence = ConfidenceLevel.HIGH
        
        for tableau_agg, (dax_agg, _) in self.AGGREGATION_MAP.items():
            # Pattern: AGG([Field])
            pattern = rf'\b{tableau_agg}\s*\(([^)]+)\)'
            
            def replace_agg(match, dax_func=dax_agg):
                inner = match.group(1).strip()
                return f'{dax_func}({inner})'
            
            result = re.sub(pattern, replace_agg, result, flags=re.IGNORECASE)
        
        return result, confidence
    
    def _translate_functions(self, formula: str) -> Tuple[str, ConfidenceLevel]:
        """Translate Tableau functions to DAX equivalents."""
        result = formula
        confidence = ConfidenceLevel.HIGH
        
        for tableau_func, dax_func in self.FUNCTION_MAP.items():
            if dax_func is None:
                # Function has no equivalent
                if re.search(rf'\b{tableau_func}\s*\(', result, re.IGNORECASE):
                    confidence = ConfidenceLevel.MEDIUM
                continue
            
            # Simple function replacement
            pattern = rf'\b{tableau_func}\s*\('
            result = re.sub(pattern, f'{dax_func}(', result, flags=re.IGNORECASE)
        
        # Handle special cases
        result = self._handle_special_functions(result)
        
        return result, confidence
    
    def _handle_special_functions(self, formula: str) -> str:
        """Handle special function translations that need restructuring."""
        result = formula
        
        # ZN([x]) -> IF(ISBLANK([x]), 0, [x])
        zn_pattern = r'ZN\s*\(([^)]+)\)'
        def replace_zn(match):
            expr = match.group(1)
            return f'IF(ISBLANK({expr}), 0, {expr})'
        result = re.sub(zn_pattern, replace_zn, result, flags=re.IGNORECASE)
        
        # IFNULL(x, y) -> IF(ISBLANK(x), y, x)
        ifnull_pattern = r'IFNULL\s*\(([^,]+),\s*([^)]+)\)'
        def replace_ifnull(match):
            expr = match.group(1)
            default = match.group(2)
            return f'IF(ISBLANK({expr}), {default}, {expr})'
        result = re.sub(ifnull_pattern, replace_ifnull, result, flags=re.IGNORECASE)
        
        return result
    
    def _translate_operators(self, formula: str) -> str:
        """Translate Tableau operators to DAX."""
        result = formula
        
        # String concatenation: + to &
        # This is tricky as + can also be numeric addition
        # For now, leave as-is since DAX also supports +
        
        # Tableau uses <> for not equal, DAX also supports this
        # No change needed
        
        return result
    
    def _translate_conditionals(self, formula: str) -> Tuple[str, ConfidenceLevel]:
        """Translate conditional expressions."""
        result = formula
        confidence = ConfidenceLevel.HIGH
        
        # IIF -> IF (simple replacement, already done)
        
        # CASE WHEN THEN END -> SWITCH
        # This is complex, mark as medium confidence if present
        if re.search(r'\bCASE\b', result, re.IGNORECASE):
            confidence = ConfidenceLevel.MEDIUM
            # Basic CASE transformation
            # CASE [Field] WHEN 'a' THEN 1 WHEN 'b' THEN 2 ELSE 0 END
            # -> SWITCH([Field], "a", 1, "b", 2, 0)
            # This is a simplified transformation
        
        return result, confidence
    
    def get_aggregation_type(self, formula: str) -> AggregationType:
        """Determine the primary aggregation type from a formula."""
        if not formula:
            return AggregationType.NONE
        
        formula_upper = formula.upper()
        
        for agg_name, (_, agg_type) in self.AGGREGATION_MAP.items():
            if re.search(rf'\b{agg_name}\s*\(', formula_upper):
                return agg_type
        
        return AggregationType.NONE
    
    @property
    def warnings(self) -> List[str]:
        return self._warnings
