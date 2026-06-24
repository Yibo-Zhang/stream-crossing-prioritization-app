"""Unit tests for validation utilities."""
import pytest
import pandas as pd
import numpy as np
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from utils.validation import (
    validate_schema,
    validate_enum_field,
    validate_numeric_range,
    validate_dataset
)


def test_validate_schema_success():
    """Test schema validation with all required fields present."""
    df = pd.DataFrame({
        'field1': [1, 2],
        'field2': ['a', 'b'],
        'field3': [1.5, 2.5]
    })
    
    # Should not raise
    validate_schema(df, ['field1', 'field2', 'field3'])


def test_validate_schema_missing_fields():
    """Test schema validation catches missing fields."""
    df = pd.DataFrame({
        'field1': [1, 2]
    })
    
    with pytest.raises(ValueError, match="Missing required fields"):
        validate_schema(df, ['field1', 'field2', 'field3'])


def test_validate_schema_extra_fields():
    """Test schema validation allows extra fields."""
    df = pd.DataFrame({
        'field1': [1, 2],
        'field2': ['a', 'b'],
        'field3': [1.5, 2.5],
        'extra': [10, 20]
    })
    
    # Should not raise even with extra field
    validate_schema(df, ['field1', 'field2'])


def test_validate_enum_case_insensitive():
    """Test enum validation is case-insensitive by default."""
    df = pd.DataFrame({
        'condition': ['Poor', 'FAIR', 'good', 'Fair']
    })
    
    invalid = validate_enum_field(
        df, 'condition', ['Poor', 'Fair', 'Good'], case_sensitive=False
    )
    
    assert len(invalid) == 0


def test_validate_enum_case_sensitive():
    """Test enum validation can be case-sensitive."""
    df = pd.DataFrame({
        'condition': ['Poor', 'FAIR', 'good', 'Fair']
    })
    
    invalid = validate_enum_field(
        df, 'condition', ['Poor', 'Fair', 'Good'], case_sensitive=True
    )
    
    # FAIR and good are invalid (wrong case)
    assert len(invalid) == 2
    assert 'FAIR' in invalid
    assert 'good' in invalid


def test_validate_enum_invalid_values():
    """Test enum validation catches invalid values."""
    df = pd.DataFrame({
        'condition': ['Poor', 'Fair', 'Excellent', 'Good']
    })
    
    invalid = validate_enum_field(
        df, 'condition', ['Poor', 'Fair', 'Good'], case_sensitive=False
    )
    
    assert len(invalid) == 1
    assert 'Excellent' in invalid


def test_validate_enum_with_nan():
    """Test enum validation ignores NaN values."""
    df = pd.DataFrame({
        'condition': ['Poor', np.nan, 'Fair', None]
    })
    
    invalid = validate_enum_field(
        df, 'condition', ['Poor', 'Fair', 'Good'], case_sensitive=False
    )
    
    # NaN should be ignored, not flagged as invalid
    assert len(invalid) == 0


def test_validate_enum_missing_field():
    """Test enum validation handles missing field."""
    df = pd.DataFrame({
        'other_field': [1, 2, 3]
    })
    
    invalid = validate_enum_field(
        df, 'condition', ['Poor', 'Fair', 'Good'], case_sensitive=False
    )
    
    # Should return empty list, not error
    assert len(invalid) == 0


def test_validate_numeric_range():
    """Test numeric range validation."""
    df = pd.DataFrame({
        'aadt': [500, 2000, 150000, -100]
    })
    
    out_of_range = validate_numeric_range(df, 'aadt', min_val=0, max_val=100000)
    
    assert len(out_of_range) == 2  # 150000 and -100


def test_validate_numeric_range_min_only():
    """Test numeric range validation with only min."""
    df = pd.DataFrame({
        'aadt': [500, 2000, -100]
    })
    
    out_of_range = validate_numeric_range(df, 'aadt', min_val=0)
    
    assert len(out_of_range) == 1
    assert out_of_range.iloc[0]['aadt'] == -100


def test_validate_numeric_range_max_only():
    """Test numeric range validation with only max."""
    df = pd.DataFrame({
        'aadt': [500, 2000, 150000]
    })
    
    out_of_range = validate_numeric_range(df, 'aadt', max_val=100000)
    
    assert len(out_of_range) == 1
    assert out_of_range.iloc[0]['aadt'] == 150000


def test_validate_numeric_range_with_nan():
    """Test numeric range validation ignores NaN."""
    df = pd.DataFrame({
        'aadt': [500, np.nan, 150000]
    })
    
    out_of_range = validate_numeric_range(df, 'aadt', min_val=0, max_val=100000)
    
    # Only 150000 should be out of range, NaN ignored
    assert len(out_of_range) == 1


def test_validate_numeric_range_non_numeric():
    """Test numeric range validation handles non-numeric values."""
    df = pd.DataFrame({
        'aadt': [500, 'invalid', 2000]
    })
    
    out_of_range = validate_numeric_range(df, 'aadt', min_val=0, max_val=100000)
    
    # 'invalid' gets coerced to NaN and ignored
    assert len(out_of_range) == 0


def test_validate_dataset():
    """Test complete dataset validation."""
    df = pd.DataFrame({
        'StructCond': ['Poor', 'Fair', 'Excellent'],
        'AADT': [500, 2000, 150000]
    })
    
    rules = {
        'StructCond': {
            'enum': ['Poor', 'Fair', 'Good'],
            'case_sensitive': False
        },
        'AADT': {
            'range': [0, 100000]
        }
    }
    
    errors = validate_dataset(df, rules)
    
    # Should find 2 errors
    assert len(errors) == 2
    
    # Check error messages
    assert any('StructCond' in e and 'Excellent' in e for e in errors)
    assert any('AADT' in e and '1 values outside range' in e for e in errors)


def test_validate_dataset_no_errors():
    """Test dataset validation with no errors."""
    df = pd.DataFrame({
        'StructCond': ['Poor', 'Fair', 'Good'],
        'AADT': [500, 2000, 50000]
    })
    
    rules = {
        'StructCond': {
            'enum': ['Poor', 'Fair', 'Good'],
            'case_sensitive': False
        },
        'AADT': {
            'range': [0, 100000]
        }
    }
    
    errors = validate_dataset(df, rules)
    
    # Should be empty
    assert len(errors) == 0


def test_validate_dataset_missing_field():
    """Test dataset validation ignores rules for missing fields."""
    df = pd.DataFrame({
        'StructCond': ['Poor', 'Fair', 'Good']
    })
    
    rules = {
        'StructCond': {
            'enum': ['Poor', 'Fair', 'Good'],
            'case_sensitive': False
        },
        'AADT': {
            'range': [0, 100000]
        }
    }
    
    errors = validate_dataset(df, rules)
    
    # AADT rule should be skipped, no errors
    assert len(errors) == 0
