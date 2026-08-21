"""Unit tests for validation utilities.

Location in repo: tests/test_validation.py

The tests added for the null-coded value work are grouped at the end. They cover
the three behaviours the change has to guarantee:

  1. A value on the reviewed null_values list does not fail validation and is
     converted to missing.
  2. A value that is on neither the enum nor the null list still fails, so an
     unreviewed marker cannot enter the model.
  3. A numeric enum matches the float column pandas produces from a CSV that has
     blank cells, which was the cause of every FUNCT_SYST value in the demo
     extract being reported invalid.
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from utils.validation import (  # noqa: E402
    DEFAULT_NULL_VALUES,
    apply_null_codes,
    comparison_key,
    find_null_coded_values,
    find_unscored_values,
    resolve_null_values,
    validate_dataset,
    validate_dataset_report,
    validate_enum_field,
    validate_numeric_range,
    validate_schema,
)


# --------------------------------------------------------------------------- #
# Schema
# --------------------------------------------------------------------------- #

def test_validate_schema_success():
    """Schema validation passes when all required fields are present."""
    df = pd.DataFrame({'field1': [1, 2], 'field2': ['a', 'b'], 'field3': [1.5, 2.5]})
    validate_schema(df, ['field1', 'field2', 'field3'])


def test_validate_schema_missing_fields():
    """Schema validation catches missing fields."""
    df = pd.DataFrame({'field1': [1, 2]})
    with pytest.raises(ValueError, match="Missing required fields"):
        validate_schema(df, ['field1', 'field2', 'field3'])


def test_validate_schema_extra_fields():
    """Schema validation allows extra fields."""
    df = pd.DataFrame({'field1': [1, 2], 'field2': ['a', 'b'], 'extra': [10, 20]})
    validate_schema(df, ['field1', 'field2'])


# --------------------------------------------------------------------------- #
# Enum
# --------------------------------------------------------------------------- #

def test_validate_enum_case_insensitive():
    """Enum validation is case-insensitive by default."""
    df = pd.DataFrame({'condition': ['Poor', 'FAIR', 'good', 'Fair']})
    assert validate_enum_field(df, 'condition', ['Poor', 'Fair', 'Good'],
                               case_sensitive=False) == []


def test_validate_enum_case_sensitive():
    """Enum validation can be case-sensitive."""
    df = pd.DataFrame({'condition': ['Poor', 'FAIR', 'good', 'Fair']})
    invalid = validate_enum_field(df, 'condition', ['Poor', 'Fair', 'Good'],
                                  case_sensitive=True)
    assert set(invalid) == {'FAIR', 'good'}


def test_validate_enum_invalid_values():
    """Enum validation catches invalid values."""
    df = pd.DataFrame({'condition': ['Poor', 'Fair', 'Excellent', 'Good']})
    assert validate_enum_field(df, 'condition', ['Poor', 'Fair', 'Good'],
                               case_sensitive=False) == ['Excellent']


def test_validate_enum_with_nan():
    """Enum validation ignores NaN values."""
    df = pd.DataFrame({'condition': ['Poor', np.nan, 'Fair', None]})
    assert validate_enum_field(df, 'condition', ['Poor', 'Fair', 'Good']) == []


def test_validate_enum_missing_field():
    """Enum validation handles a field that is absent from the frame."""
    df = pd.DataFrame({'other_field': [1, 2, 3]})
    assert validate_enum_field(df, 'condition', ['Poor', 'Fair', 'Good']) == []


def test_validate_enum_reports_each_value_once():
    """A repeated invalid value is reported once, in its original form."""
    df = pd.DataFrame({'condition': ['Excellent'] * 5 + ['Poor']})
    assert validate_enum_field(df, 'condition', ['Poor', 'Fair']) == ['Excellent']


# --------------------------------------------------------------------------- #
# Numeric range
# --------------------------------------------------------------------------- #

def test_validate_numeric_range():
    """Numeric range validation flags values on both sides of the range."""
    df = pd.DataFrame({'aadt': [500, 2000, 150000, -100]})
    assert len(validate_numeric_range(df, 'aadt', min_val=0, max_val=100000)) == 2


def test_validate_numeric_range_min_only():
    """Only a lower bound is enforced when max_val is omitted."""
    df = pd.DataFrame({'aadt': [500, 2000, -100]})
    out_of_range = validate_numeric_range(df, 'aadt', min_val=0)
    assert len(out_of_range) == 1
    assert out_of_range.iloc[0]['aadt'] == -100


def test_validate_numeric_range_max_only():
    """Only an upper bound is enforced when min_val is omitted."""
    df = pd.DataFrame({'aadt': [500, 2000, 150000]})
    out_of_range = validate_numeric_range(df, 'aadt', max_val=100000)
    assert len(out_of_range) == 1
    assert out_of_range.iloc[0]['aadt'] == 150000


def test_validate_numeric_range_with_nan():
    """A blank value is a data gap, not a range violation."""
    df = pd.DataFrame({'aadt': [500, np.nan, 150000]})
    assert len(validate_numeric_range(df, 'aadt', min_val=0, max_val=100000)) == 1


def test_validate_numeric_range_non_numeric():
    """Non-numeric values are coerced to NaN and ignored."""
    df = pd.DataFrame({'aadt': [500, 'invalid', 2000]})
    assert len(validate_numeric_range(df, 'aadt', min_val=0, max_val=100000)) == 0


def test_validate_numeric_range_non_default_index():
    """The mask is built on df.index, so a filtered frame is handled correctly.

    app.filter_by_region returns a boolean-masked slice that keeps the original
    index. A mask built on a fresh RangeIndex would misalign against it.
    """
    df = pd.DataFrame({'aadt': [500, 2000, 150000, -100]},
                      index=[10, 25, 43, 87])
    out_of_range = validate_numeric_range(df, 'aadt', min_val=0, max_val=100000)
    assert sorted(out_of_range.index) == [43, 87]


# --------------------------------------------------------------------------- #
# Dataset
# --------------------------------------------------------------------------- #

def test_validate_dataset():
    """Complete dataset validation reports both kinds of failure."""
    df = pd.DataFrame({'StructCond': ['Poor', 'Fair', 'Excellent'],
                       'AADT': [500, 2000, 150000]})
    rules = {'StructCond': {'enum': ['Poor', 'Fair', 'Good'], 'case_sensitive': False},
             'AADT': {'range': [0, 100000]}}

    errors = validate_dataset(df, rules)
    assert len(errors) == 2
    assert any('StructCond' in e and 'Excellent' in e for e in errors)
    assert any('AADT' in e and '1 values outside range' in e for e in errors)


def test_validate_dataset_no_errors():
    """Clean data produces no messages at all."""
    df = pd.DataFrame({'StructCond': ['Poor', 'Fair', 'Good'],
                       'AADT': [500, 2000, 50000]})
    rules = {'StructCond': {'enum': ['Poor', 'Fair', 'Good'], 'case_sensitive': False},
             'AADT': {'range': [0, 100000]}}
    assert validate_dataset(df, rules) == []


def test_validate_dataset_missing_field():
    """Rules for fields that are not in the frame are skipped."""
    df = pd.DataFrame({'StructCond': ['Poor', 'Fair', 'Good']})
    rules = {'StructCond': {'enum': ['Poor', 'Fair', 'Good'], 'case_sensitive': False},
             'AADT': {'range': [0, 100000]}}
    assert validate_dataset(df, rules) == []


# --------------------------------------------------------------------------- #
# Comparison keys
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("value", [7, 7.0, "7", "7.0", np.int64(7), np.float64(7.0)])
def test_comparison_key_integral_forms_agree(value):
    """Every integral form of 7 keys the same, whatever its type."""
    assert comparison_key(value) == "7"


def test_comparison_key_missing_forms():
    """Every missing-value form keys to None and is never compared."""
    for value in (None, np.nan, pd.NA, "", "   "):
        assert comparison_key(value) is None


def test_comparison_key_bool_is_not_numeric():
    """bool subclasses int; keying True as '1' would let it match a 0/1 enum."""
    assert comparison_key(True) != "1"


def test_numeric_enum_matches_float_column():
    """The FUNCT_SYST regression.

    params.json declares the domain as integers. pandas reads the column as
    float64 because the source CSV has blank cells, so every value arrives as
    7.0, 5.0 and so on. Before the canonical comparison key this reported all
    5,247 non-null records in the demo extract as invalid.
    """
    df = pd.DataFrame({'FUNCT_SYST': [7.0, 5.0, 0.0, np.nan, 3.0]})
    assert validate_enum_field(df, 'FUNCT_SYST', [0, 1, 2, 3, 4, 5, 6, 7]) == []


def test_numeric_enum_still_catches_out_of_domain():
    """Fixing the float comparison must not stop real violations being caught."""
    df = pd.DataFrame({'FUNCT_SYST': [7.0, 9.0]})
    assert validate_enum_field(df, 'FUNCT_SYST', [0, 1, 2, 3, 4, 5, 6, 7]) == [9.0]


# --------------------------------------------------------------------------- #
# Null-coded values
# --------------------------------------------------------------------------- #

SADES_NULL_CODES = ['N/A Score - Wetland', 'No Score - Private', 'Unknown']


def test_null_coded_values_do_not_fail_enum_validation():
    """The behaviour the change exists for."""
    df = pd.DataFrame({'GC_Score': ['Fully Compatible', 'N/A Score - Wetland',
                                    'No Score - Private']})
    assert validate_enum_field(df, 'GC_Score', ['Fully Compatible'],
                               null_values=SADES_NULL_CODES) == []


def test_unreviewed_value_still_fails_enum_validation():
    """A marker that is on neither list must still halt the run."""
    df = pd.DataFrame({'GC_Score': ['Fully Compatible', 'N/A Score - Estuary']})
    assert validate_enum_field(df, 'GC_Score', ['Fully Compatible'],
                               null_values=SADES_NULL_CODES) == \
        ['N/A Score - Estuary']


def test_none_is_not_treated_as_a_null_code():
    """'None' is a scored category meaning no undermining observed.

    It maps to 0 in five fields, so it must never be swept into the null list.
    """
    assert 'None' not in DEFAULT_NULL_VALUES
    df = pd.DataFrame({'UsUndermin': ['None', 'Footers', 'Unknown']})
    converted, report = apply_null_codes(
        df, {'UsUndermin': {'enum': ['None', 'Footers']}},
        null_values=DEFAULT_NULL_VALUES)
    assert converted.loc[0, 'UsUndermin'] == 'None'
    assert pd.isna(converted.loc[2, 'UsUndermin'])
    assert report['UsUndermin'] == {'Unknown': 1}


def test_apply_null_codes_converts_and_reports():
    """Conversion is limited to enum fields and leaves the caller's frame intact."""
    df = pd.DataFrame({
        'GC_Score': ['Fully Compatible', 'N/A Score - Wetland',
                     'N/A Score - Wetland', 'No Score - Private'],
        'AADT': [100, 200, 300, 400],
    })
    rules = {'GC_Score': {'enum': ['Fully Compatible']},
             'AADT': {'range': [0, 1000]}}

    converted, report = apply_null_codes(df, rules,
                                         null_values=SADES_NULL_CODES)

    assert converted['GC_Score'].isna().sum() == 3
    assert converted.loc[0, 'GC_Score'] == 'Fully Compatible'
    assert report['GC_Score'] == {'N/A Score - Wetland': 2,
                                  'No Score - Private': 1}
    # Numeric fields are untouched.
    assert converted['AADT'].tolist() == [100, 200, 300, 400]
    # The caller's frame is not modified.
    assert df['GC_Score'].isna().sum() == 0


def test_apply_null_codes_preserves_non_default_index():
    """A frame filtered by region keeps its index through the conversion."""
    df = pd.DataFrame({'GC_Score': ['Fully Compatible', 'Unknown']},
                      index=[41, 92])
    converted, _ = apply_null_codes(df, {'GC_Score': {'enum': ['Fully Compatible']}},
                                    null_values=SADES_NULL_CODES)
    assert list(converted.index) == [41, 92]
    assert pd.isna(converted.loc[92, 'GC_Score'])


def test_field_level_null_values_extend_the_global_list():
    """A field-level list adds to the global one rather than replacing it."""
    rules = {'null_values': ['Not Surveyed']}
    resolved = resolve_null_values(rules, ['Unknown'])
    assert set(resolved) == {'Unknown', 'Not Surveyed'}


def test_field_can_opt_out_of_the_global_list():
    """inherit_null_values: false gives a field full control of its own list."""
    rules = {'null_values': ['Not Surveyed'], 'inherit_null_values': False}
    assert resolve_null_values(rules, ['Unknown']) == ['Not Surveyed']


def test_find_null_coded_values_counts_rows():
    """The audit trail counts rows per marker, not distinct markers."""
    df = pd.DataFrame({'AOP_Score': ['No Passage', 'Unknown', 'Unknown']})
    assert find_null_coded_values(df, 'AOP_Score', ['Unknown']) == {'Unknown': 2}


def test_report_separates_errors_null_codes_and_warnings():
    """One field can produce a conversion and an error in the same pass."""
    df = pd.DataFrame({'GC_Score': ['Fully Compatible', 'N/A Score - Wetland',
                                    'N/A Score - Estuary']})
    rules = {'GC_Score': {'enum': ['Fully Compatible'],
                          'null_values': ['N/A Score - Wetland']}}

    report = validate_dataset_report(df, rules, null_values=[])

    assert not report.ok
    assert 'N/A Score - Estuary' in report.errors[0]
    assert report.null_coded == {'GC_Score': {'N/A Score - Wetland': 1}}
    assert report.null_coded_total == 1


def test_warning_severity_does_not_halt_the_run():
    """A rule marked severity: warning reports without blocking."""
    df = pd.DataFrame({'Descriptive': ['unexpected']})
    rules = {'Descriptive': {'enum': ['expected'], 'severity': 'warning'}}

    report = validate_dataset_report(df, rules)

    assert report.ok
    assert len(report.warnings) == 1


# --------------------------------------------------------------------------- #
# Score map coverage
# --------------------------------------------------------------------------- #

def test_find_unscored_values_catches_map_drift():
    """The StructSed regression.

    'Entirely Full' occurs 22 times in the demo extract while 'High', the only
    top-severity key in the sediment fill map, occurs zero times. The value
    passes the enum check and then scores as missing, so it has to be reported.
    """
    df = pd.DataFrame({'StructSed': ['Open', 'Entirely Full', 'Entirely Full']})
    score_map = {'Open': 0, '1/4 Full': 0, '1/2 Full': 0.33, '3/4 Full': 0.66,
                 'High': 1}
    assert find_unscored_values(df, 'StructSed', score_map) == {'Entirely Full': 2}


def test_find_unscored_values_ignores_null_codes():
    """A null-coded value is meant to become missing, so it is not reported."""
    df = pd.DataFrame({'GC_Score': ['Fully Compatible', 'Unknown']})
    assert find_unscored_values(df, 'GC_Score', {'Fully Compatible': 0},
                                null_values=['Unknown']) == {}


def test_score_map_coverage_reported_as_a_warning():
    """A scoring gap degrades one criterion, so it warns rather than halts."""
    df = pd.DataFrame({'StructSed': ['Open', 'Entirely Full']})
    rules = {'StructSed': {'enum': ['Open', 'Entirely Full'],
                           'score_map': 'sediment_fill'}}
    score_maps = {'sediment_fill': {'Open': 0, 'High': 1}}

    report = validate_dataset_report(df, rules, score_maps=score_maps)

    assert report.ok  # a scoring gap degrades one criterion, it does not halt
    assert len(report.warnings) == 1
    assert 'Entirely Full' in report.warnings[0]
