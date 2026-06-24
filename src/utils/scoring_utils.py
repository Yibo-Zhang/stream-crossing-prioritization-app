"""Generic scoring and calculation utilities."""
import pandas as pd
import numpy as np


def calculate_weighted_average(df, score_cols, weights):
    """
    Calculate dynamic weighted average that adapts to missing data.
    
    For each row, computes weighted average using only non-missing values.
    Weights are automatically adjusted to sum to 1 based on available data.
    
    Parameters
    ----------
    df : pd.DataFrame
        Input dataframe
    score_cols : list of str
        List of column names containing scores
    weights : list of float
        List of weights corresponding to score_cols
        
    Returns
    -------
    pd.Series
        Weighted average scores for each row
        
    Examples
    --------
    >>> df = pd.DataFrame({'s1': [0.5, np.nan, 0.3], 's2': [0.6, 0.7, np.nan]})
    >>> calculate_weighted_average(df, ['s1', 's2'], [0.6, 0.4])
    0    0.54    # (0.5*0.6 + 0.6*0.4) / (0.6+0.4) = 0.54
    1    0.70    # Only s2 available: 0.7*0.4 / 0.4 = 0.7
    2    0.30    # Only s1 available: 0.3*0.6 / 0.6 = 0.3
    """
    def weighted_avg(row):
        num = sum(row[col] * w for col, w in zip(score_cols, weights) 
                  if pd.notna(row[col]))
        den = sum(w for col, w in zip(score_cols, weights) 
                  if pd.notna(row[col]))
        return num / den if den > 0 else np.nan
    
    return df.apply(weighted_avg, axis=1)


def normalize_minmax(series):
    """
    Apply min-max normalization to scale values to 0-1 range.
    
    Formula: (x - min) / (max - min)
    
    Parameters
    ----------
    series : pd.Series
        Input series to normalize
        
    Returns
    -------
    pd.Series
        Normalized series where min=0 and max=1
        
    Notes
    -----
    If all values are identical (max == min), returns original series unchanged.
    
    Examples
    --------
    >>> s = pd.Series([10, 20, 30, 40, 50])
    >>> normalize_minmax(s)
    0    0.00
    1    0.25
    2    0.50
    3    0.75
    4    1.00
    """
    min_val = series.min()
    max_val = series.max()
    
    if max_val == min_val:
        return series
    
    return (series - min_val) / (max_val - min_val)


def calculate_confidence(df, criterion_cols):
    """
    Calculate confidence score showing data completeness.
    
    For each row, counts how many criteria have data vs. are missing.
    Returns counts and a formatted string (e.g., "16 of 18" means 16 of 18 present).
    
    Parameters
    ----------
    df : pd.DataFrame
        Input dataframe
    criterion_cols : list of str
        List of criterion column names to check
        
    Returns
    -------
    tuple of (pd.Series, pd.Series, pd.Series)
        - present_count: Number of non-missing criteria per row
        - missing_count: Number of missing criteria per row
        - confidence_string: Formatted string "present/total"
        
    Examples
    --------
    >>> df = pd.DataFrame({
    ...     'crit1': [1, np.nan, 1],
    ...     'crit2': [1, 1, np.nan],
    ...     'crit3': [np.nan, 1, 1]
    ... })
    >>> present, missing, conf_str = calculate_confidence(df, ['crit1', 'crit2', 'crit3'])
    >>> conf_str
    0    2 of 3
    1    2 of 3
    2    2 of 3
    """
    n_total = len(criterion_cols)
    present = df[criterion_cols].notna().sum(axis=1)
    missing = n_total - present
    conf_str = present.astype(str) + ' of ' + str(n_total)   # FIXED: was '/'    
    return present, missing, conf_str


def apply_jenks_classification(series, n_classes=5, labels=None):
    """
    Apply Jenks natural breaks with intelligent label selection.
    
    Selects labels based on WHERE values fall on 0-1 scale:
    - Wide spread (>60% of scale): Uses extreme labels
    - Clustered data: Uses labels matching the cluster position
    
    Examples:
    - [0.8, 1.0] → ['High', 'Very High']
    - [0.1, 0.2] → ['Very Low', 'Low']  
    - [0.1, 0.9] → ['Very Low', 'Very High'] (wide spread)
    - [0.05, 0.3, 0.5, 0.7, 0.95] → All 5 labels naturally
    
    Parameters:
    -----------
    series : pd.Series
        Normalized score series (0-1 range, where 1 = highest priority)
    n_classes : int, default=5
        Desired number of classes (adjusted if fewer unique values)
    labels : list of str, optional
        Class labels (default: ["Very Low", "Low", "Moderate", "High", "Very High"])
    
    Returns:
    --------
    pd.Series
        Categorical series with same index as input, NaN values preserved
    """
    import jenkspy
    import numpy as np
    import pandas as pd
    
    if labels is None:
        labels = ["Very Low", "Low", "Moderate", "High", "Very High"]
    
    # Initialize result with NaN
    result = pd.Series(np.nan, index=series.index, dtype="object")
    
    # Get non-NaN values
    values = series.dropna()
    if len(values) == 0:
        return result
    
    # Get unique values and sort
    unique_values = np.sort(values.unique())
    n_unique = len(unique_values)
    
    # Edge case: Single unique value
    if n_unique == 1:
        val = unique_values[0]
        if val <= 0.2:
            label = labels[0]
        elif val <= 0.4:
            label = labels[1]
        elif val <= 0.6:
            label = labels[2]
        elif val <= 0.8:
            label = labels[3]
        else:
            label = labels[4]
        result.loc[values.index] = label
        return result
    
    # Adjust n_classes to available unique values
    actual_classes = min(n_classes, n_unique)
    
    # Perform Jenks classification
    raw_breaks = jenkspy.jenks_breaks(values.values, n_classes=actual_classes)
    breaks = np.unique(raw_breaks)
    
    # CRITICAL FIX: Ensure enough breaks
    if len(breaks) < actual_classes + 1:
        if actual_classes == n_unique:
            # Create breaks using midpoints
            breaks = np.concatenate([
                [unique_values[0] - 1e-10],
                (unique_values[:-1] + unique_values[1:]) / 2,
                [unique_values[-1] + 1e-10]
            ])
        else:
            breaks = np.quantile(unique_values, np.linspace(0, 1, actual_classes + 1))
    
    n_intervals = len(breaks) - 1
    
    # SMART LABEL SELECTION
    data_range = unique_values.max() - unique_values.min()
    mean_value = np.mean(unique_values)
    
    # Strategy 1: Wide spread data (>60% of 0-1 scale)
    # Use labels spanning from min to max position
    if data_range > 0.6:
        # Map min and max values to label positions
        min_label_idx = int(unique_values.min() * len(labels))
        max_label_idx = int(unique_values.max() * len(labels))
        max_label_idx = min(max_label_idx, len(labels) - 1)
        
        # Distribute labels evenly between min and max
        if n_intervals == 2:
            # For 2 intervals, use the two extremes
            use_labels = [labels[min_label_idx], labels[max_label_idx]]
        else:
            # For more intervals, interpolate between min and max
            label_indices = np.linspace(min_label_idx, max_label_idx, n_intervals).astype(int)
            label_indices = np.clip(label_indices, 0, len(labels) - 1)
            # Remove duplicates while preserving order
            seen = set()
            unique_indices = []
            for idx in label_indices:
                if idx not in seen:
                    seen.add(idx)
                    unique_indices.append(idx)
            # If we lost some labels due to duplicates, fill from adjacent
            while len(unique_indices) < n_intervals and len(unique_indices) < len(labels):
                last_idx = unique_indices[-1]
                if last_idx < len(labels) - 1:
                    unique_indices.append(last_idx + 1)
                else:
                    unique_indices.insert(0, unique_indices[0] - 1)
            use_labels = [labels[i] for i in unique_indices[:n_intervals]]
    
    # Strategy 2: Clustered data
    # Use labels centered around the cluster position
    else:
        center_index = int(mean_value * len(labels))
        center_index = min(center_index, len(labels) - 1)
        
        half_width = n_intervals // 2
        start_index = center_index - half_width
        
        # Keep within bounds
        if start_index < 0:
            start_index = 0
        elif start_index + n_intervals > len(labels):
            start_index = len(labels) - n_intervals
        
        end_index = start_index + n_intervals
        use_labels = labels[start_index:end_index]
    
    # Classify
    classified = pd.cut(
        series,
        bins=breaks,
        labels=use_labels,
        include_lowest=True,
        duplicates='drop'
    )
    
    result.loc[classified.notna()] = classified.dropna()
    
    return result

