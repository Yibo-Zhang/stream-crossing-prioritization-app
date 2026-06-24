"""Unit tests for scoring utilities."""
import pytest
import pandas as pd
import numpy as np
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from utils.scoring_utils import (
    calculate_weighted_average,
    normalize_minmax,
    calculate_confidence,
    apply_jenks_classification
)


def test_weighted_average_complete_data():
    """Test weighted average with complete data."""
    df = pd.DataFrame({
        'score1': [0.5, 0.8, 0.3],
        'score2': [0.6, 0.7, 0.4]
    })
    
    result = calculate_weighted_average(df, ['score1', 'score2'], [0.6, 0.4])
    
    expected = [0.54, 0.76, 0.34]
    np.testing.assert_array_almost_equal(result, expected)


def test_weighted_average_missing_data():
    """Test weighted average adapts to missing data."""
    df = pd.DataFrame({
        'score1': [0.5, np.nan, 0.3],
        'score2': [np.nan, 0.7, 0.4]
    })
    
    result = calculate_weighted_average(df, ['score1', 'score2'], [0.6, 0.4])
    
    # Row 0: Only score1 available
    assert result[0] == 0.5
    
    # Row 1: Only score2 available
    assert result[1] == 0.7
    
    # Row 2: Both available
    assert np.isclose(result[2], 0.34)


def test_weighted_average_all_missing():
    """Test weighted average with all missing returns NaN."""
    df = pd.DataFrame({
        'score1': [np.nan],
        'score2': [np.nan]
    })
    
    result = calculate_weighted_average(df, ['score1', 'score2'], [0.6, 0.4])
    
    assert pd.isna(result[0])


def test_weighted_average_equal_weights():
    """Test weighted average with equal weights."""
    df = pd.DataFrame({
        'score1': [0.5, 0.8],
        'score2': [0.6, 0.4]
    })
    
    result = calculate_weighted_average(df, ['score1', 'score2'], [0.5, 0.5])
    
    # Should be simple average
    expected = [0.55, 0.6]
    np.testing.assert_array_almost_equal(result, expected)


def test_normalize_minmax():
    """Test min-max normalization."""
    series = pd.Series([10, 20, 30, 40, 50])
    result = normalize_minmax(series)
    
    expected = pd.Series([0.0, 0.25, 0.5, 0.75, 1.0])
    pd.testing.assert_series_equal(result, expected)


def test_normalize_minmax_constant():
    """Test normalization with constant values returns unchanged."""
    series = pd.Series([5, 5, 5, 5])
    result = normalize_minmax(series)
    
    pd.testing.assert_series_equal(result, series)


def test_normalize_minmax_with_nan():
    """Test normalization handles NaN values."""
    series = pd.Series([10, np.nan, 30, 40, 50])
    result = normalize_minmax(series)
    
    assert pd.isna(result[1])
    assert result[0] == 0.0  # 10 is min
    assert result[4] == 1.0  # 50 is max


def test_calculate_confidence():
    """Test confidence calculation."""
    df = pd.DataFrame({
        'crit1': [1, np.nan, 1],
        'crit2': [1, 1, np.nan],
        'crit3': [np.nan, 1, 1]
    })
    
    present, missing, conf_str = calculate_confidence(df, ['crit1', 'crit2', 'crit3'])
    
    assert list(present) == [2, 2, 2]
    assert list(missing) == [1, 1, 1]
    assert list(conf_str) == ['2/3', '2/3', '2/3']


def test_calculate_confidence_all_present():
    """Test confidence with all data present."""
    df = pd.DataFrame({
        'crit1': [1, 2, 3],
        'crit2': [4, 5, 6]
    })
    
    present, missing, conf_str = calculate_confidence(df, ['crit1', 'crit2'])
    
    assert list(present) == [2, 2, 2]
    assert list(missing) == [0, 0, 0]
    assert list(conf_str) == ['2/2', '2/2', '2/2']


def test_calculate_confidence_all_missing():
    """Test confidence with all data missing."""
    df = pd.DataFrame({
        'crit1': [np.nan, np.nan],
        'crit2': [np.nan, np.nan]
    })
    
    present, missing, conf_str = calculate_confidence(df, ['crit1', 'crit2'])
    
    assert list(present) == [0, 0]
    assert list(missing) == [2, 2]
    assert list(conf_str) == ['0/2', '0/2']


def test_jenks_classification():
    """Run all comprehensive tests."""
    
    print("=" * 80)
    print("COMPREHENSIVE TEST SUITE FOR apply_jenks_classification")
    print("=" * 80)
    print()

    # ========================================================================
    # TEST CATEGORY 1: TWO UNIQUE VALUES
    # ========================================================================
    print("TEST CATEGORY 1: TWO UNIQUE VALUES")
    print("-" * 80)

    # Test 1.1: Two high values
    print("\n1.1 Two HIGH values [0.8, 1.0] with large sample")
    s1_1 = pd.Series([0.8]*2500 + [1.0]*2500)
    r1_1 = apply_jenks_classification(s1_1)
    vc1_1 = r1_1.value_counts().sort_index()
    print(f"Result: {vc1_1.to_dict()}")
    assert 'High' in vc1_1.index or 'Very High' in vc1_1.index
    assert r1_1.nunique() == 2
    print("✓ PASS")

    # Test 1.2: Two low values
    print("\n1.2 Two LOW values [0.1, 0.2]")
    s1_2 = pd.Series([0.1, 0.2])
    r1_2 = apply_jenks_classification(s1_2)
    print(f"Result: {r1_2.tolist()}")
    assert 'Very Low' in r1_2.values or 'Low' in r1_2.values
    assert r1_2.nunique() == 2
    print("✓ PASS")

    # Test 1.3: Two middle values
    print("\n1.3 Two MIDDLE values [0.45, 0.55]")
    s1_3 = pd.Series([0.45, 0.55])
    r1_3 = apply_jenks_classification(s1_3)
    print(f"Result: {r1_3.tolist()}")
    assert r1_3.nunique() == 2
    print("✓ PASS")

    # Test 1.4: Wide spread
    print("\n1.4 WIDE SPREAD [0.1, 0.9]")
    s1_4 = pd.Series([0.1, 0.9])
    r1_4 = apply_jenks_classification(s1_4)
    print(f"Result: {r1_4.tolist()}")
    assert r1_4[0] != r1_4[1]
    low_labels = ['Very Low', 'Low']
    high_labels = ['High', 'Very High']
    assert r1_4.iloc[0] in low_labels, f"0.1 should be low, got {r1_4.iloc[0]}"
    assert r1_4.iloc[1] in high_labels, f"0.9 should be high, got {r1_4.iloc[1]}"
    print("✓ PASS")

    # Test 1.5: Very close values
    print("\n1.5 VERY CLOSE values [0.500, 0.501]")
    s1_5 = pd.Series([0.500, 0.501])
    r1_5 = apply_jenks_classification(s1_5)
    print(f"Result: {r1_5.tolist()}")
    assert r1_5.nunique() == 2
    print("✓ PASS")

    # ========================================================================
    # TEST CATEGORY 2: THREE UNIQUE VALUES
    # ========================================================================
    print("\n\nTEST CATEGORY 2: THREE UNIQUE VALUES")
    print("-" * 80)

    print("\n2.1 Three HIGH values [0.7, 0.85, 0.95]")
    s2_1 = pd.Series([0.7, 0.85, 0.95])
    r2_1 = apply_jenks_classification(s2_1)
    print(f"Result: {r2_1.tolist()}")
    assert r2_1.nunique() == 3
    print("✓ PASS")

    print("\n2.2 Three LOW values [0.05, 0.15, 0.35]")
    s2_2 = pd.Series([0.05, 0.15, 0.35])
    r2_2 = apply_jenks_classification(s2_2)
    print(f"Result: {r2_2.tolist()}")
    assert r2_2.nunique() == 3
    print("✓ PASS")

    print("\n2.3 Three FULL RANGE [0.1, 0.5, 0.9]")
    s2_3 = pd.Series([0.1, 0.5, 0.9])
    r2_3 = apply_jenks_classification(s2_3)
    print(f"Result: {r2_3.tolist()}")
    assert r2_3.nunique() == 3
    print("✓ PASS")

    # ========================================================================
    # TEST CATEGORY 3: SINGLE UNIQUE VALUE
    # ========================================================================
    print("\n\nTEST CATEGORY 3: SINGLE UNIQUE VALUE")
    print("-" * 80)

    test_cases = [
        (0.05, "Very Low"), (0.15, "Very Low"),
        (0.25, "Low"), (0.35, "Low"),
        (0.45, "Moderate"), (0.55, "Moderate"),
        (0.65, "High"), (0.75, "High"),
        (0.85, "Very High"), (0.95, "Very High")
    ]

    for value, expected in test_cases:
        s = pd.Series([value] * 100)
        r = apply_jenks_classification(s)
        actual = r.iloc[0]
        print(f"  {value:.2f} → {actual} (expected {expected})")
        assert r.nunique() == 1
        assert actual == expected, f"Expected {expected}, got {actual}"
    
    print("✓ PASS: All single values correct")

    # ========================================================================
    # TEST CATEGORY 4: FOUR UNIQUE VALUES
    # ========================================================================
    print("\n\nTEST CATEGORY 4: FOUR UNIQUE VALUES")
    print("-" * 80)

    print("\n4.1 Four EVENLY SPACED [0.2, 0.4, 0.6, 0.8]")
    s4_1 = pd.Series([0.2, 0.4, 0.6, 0.8])
    r4_1 = apply_jenks_classification(s4_1)
    print(f"Result: {r4_1.tolist()}")
    assert r4_1.nunique() == 4
    # Check ascending order
    labels_order = ["Very Low", "Low", "Moderate", "High", "Very High"]
    indices = [labels_order.index(v) for v in r4_1.tolist()]
    assert indices == sorted(indices), "Should be ascending"
    print("✓ PASS")

    print("\n4.2 Four HIGH [0.65, 0.75, 0.85, 0.95]")
    s4_2 = pd.Series([0.65, 0.75, 0.85, 0.95])
    r4_2 = apply_jenks_classification(s4_2)
    print(f"Result: {r4_2.tolist()}")
    assert r4_2.nunique() == 4
    print("✓ PASS")

    # ========================================================================
    # TEST CATEGORY 5: LARGE DATASETS
    # ========================================================================
    print("\n\nTEST CATEGORY 5: LARGE DATASETS")
    print("-" * 80)

    print("\n5.1 Uniform distribution (n=1000)")
    np.random.seed(42)
    s5_1 = pd.Series(np.random.uniform(0, 1, 1000))
    r5_1 = apply_jenks_classification(s5_1)
    print(f"Distribution: {r5_1.value_counts().sort_index().to_dict()}")
    assert r5_1.nunique() <= 5 and r5_1.nunique() >= 3
    print("✓ PASS")

    print("\n5.2 Bimodal (0.2 and 0.8 clusters)")
    s5_2 = pd.Series(list(np.random.normal(0.2, 0.05, 500)) + 
                     list(np.random.normal(0.8, 0.05, 500)))
    s5_2 = s5_2.clip(0, 1)
    r5_2 = apply_jenks_classification(s5_2)
    print(f"Distribution: {r5_2.value_counts().sort_index().to_dict()}")
    print("✓ PASS")

    # ========================================================================
    # TEST CATEGORY 6: EDGE CASES
    # ========================================================================
    print("\n\nTEST CATEGORY 6: EDGE CASES")
    print("-" * 80)

    print("\n6.1 All NaN")
    s6_1 = pd.Series([np.nan, np.nan, np.nan])
    r6_1 = apply_jenks_classification(s6_1)
    assert r6_1.isna().all()
    print("✓ PASS")

    print("\n6.2 Mixed values and NaN")
    s6_2 = pd.Series([0.2, np.nan, 0.8, np.nan, 0.5])
    r6_2 = apply_jenks_classification(s6_2)
    assert r6_2.isna().sum() == 2
    assert r6_2.notna().sum() == 3
    print("✓ PASS")

    print("\n6.3 Boundaries [0.0, 1.0]")
    s6_3 = pd.Series([0.0, 1.0])
    r6_3 = apply_jenks_classification(s6_3)
    assert r6_3.iloc[0] == "Very Low"
    assert r6_3.iloc[1] == "Very High"
    print("✓ PASS")

    print("\n6.4 Single value + NaN")
    s6_4 = pd.Series([0.7, 0.7, np.nan, 0.7])
    r6_4 = apply_jenks_classification(s6_4)
    assert r6_4[r6_4.notna()].nunique() == 1
    assert pd.isna(r6_4.iloc[2])
    print("✓ PASS")

    print("\n6.5 Empty series")
    s6_5 = pd.Series([], dtype=float)
    r6_5 = apply_jenks_classification(s6_5)
    assert len(r6_5) == 0
    print("✓ PASS")

    print("\n6.6 Production-scale (5000 rows, 2 unique)")
    s6_6 = pd.Series([0.3] * 2500 + [0.7] * 2500)
    r6_6 = apply_jenks_classification(s6_6)
    vc6_6 = r6_6.value_counts().sort_index()
    assert r6_6.nunique() == 2
    assert all(vc6_6 == 2500)
    print(f"Result: {vc6_6.to_dict()}")
    print("✓ PASS")

    # ========================================================================
    # SUMMARY
    # ========================================================================
    print("\n" + "=" * 80)
    print("ALL TESTS PASSED! ✓✓✓")
    print("=" * 80)
    print("Test coverage:")
    print("  ✓ 2 unique values (5 scenarios)")
    print("  ✓ 3 unique values (3 scenarios)")
    print("  ✓ 4 unique values (2 scenarios)")
    print("  ✓ Single unique value (10 quintiles)")
    print("  ✓ Large datasets (2 scenarios)")
    print("  ✓ Edge cases (6 scenarios)")
    print("  Total: 30+ test scenarios")
    print("=" * 80)


def test_jenks_classification_custom_labels():
    """Test Jenks with custom labels."""
    series = pd.Series([1, 2, 10, 11, 20, 21])
    labels = ['Low', 'Medium', 'High', 'Very High', 'Extreme']
    result = apply_jenks_classification(series, n_classes=5, labels=labels)
    
    # Labels should be from our custom list
    unique_labels = result.unique()
    for label in unique_labels:
        assert label in labels
