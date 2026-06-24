"""Input data validation utilities."""
import pandas as pd


def validate_schema(df, required_fields):
    """
    Validate that all required fields exist in dataframe.
    
    Parameters
    ----------
    df : pd.DataFrame
        Input dataframe to validate
    required_fields : list of str
        List of required column names
        
    Raises
    ------
    ValueError
        If any required fields are missing from dataframe
        
    Examples
    --------
    >>> df = pd.DataFrame({'col1': [1], 'col2': [2]})
    >>> validate_schema(df, ['col1', 'col2', 'col3'])
    ValueError: Missing required fields: ['col3']
    """
    missing = [f for f in required_fields if f not in df.columns]
    if missing:
        raise ValueError(f"Missing required fields: {missing}")


def validate_enum_field(df, field, valid_values, case_sensitive=False):
    """
    Validate that enumerated field contains only allowed values.
    
    Parameters
    ----------
    df : pd.DataFrame
        Input dataframe
    field : str
        Field name to validate
    valid_values : list
        List of valid values for this field
    case_sensitive : bool, default=False
        Whether comparison should be case-sensitive
        
    Returns
    -------
    list
        List of invalid values found (empty list if all valid)
        
    Examples
    --------
    >>> df = pd.DataFrame({'condition': ['Poor', 'FAIR', 'Excellent']})
    >>> validate_enum_field(df, 'condition', ['Poor', 'Fair', 'Good'], case_sensitive=False)
    ['Excellent']
    """
    if field not in df.columns:
        return []
    
    series = df[field].dropna()
    if len(series) == 0:
        return []
    
    if not case_sensitive:
        valid_lower = [str(v).lower() for v in valid_values]
        invalid = series[~series.astype(str).str.lower().isin(valid_lower)]
    else:
        invalid = series[~series.isin(valid_values)]
    
    return invalid.unique().tolist()


def validate_numeric_range(df, field, min_val=None, max_val=None):
    """
    Validate that numeric field values are within specified range.
    
    Parameters
    ----------
    df : pd.DataFrame
        Input dataframe
    field : str
        Field name to validate
    min_val : float, optional
        Minimum allowed value (inclusive)
    max_val : float, optional
        Maximum allowed value (inclusive)
        
    Returns
    -------
    pd.DataFrame
        Subset of rows with out-of-range values
        
    Examples
    --------
    >>> df = pd.DataFrame({'aadt': [500, 2000, 150000, -100]})
    >>> out_of_range = validate_numeric_range(df, 'aadt', min_val=0, max_val=100000)
    >>> len(out_of_range)
    2  # -100 and 150000 are out of range
    """
    if field not in df.columns:
        return pd.DataFrame()
    
    series = pd.to_numeric(df[field], errors='coerce')
    mask = pd.Series([True] * len(df))
    
    if min_val is not None:
        mask &= (series >= min_val) | series.isna()
    if max_val is not None:
        mask &= (series <= max_val) | series.isna()
    
    return df[~mask]


def validate_dataset(df, validation_rules):
    """
    Validate entire dataset against validation rules from params.json.
    
    Parameters
    ----------
    df : pd.DataFrame
        Input dataframe to validate
    validation_rules : dict
        Dictionary of validation rules from params['validation']
        
    Returns
    -------
    list of str
        List of validation error messages (empty if no errors)
        
    Examples
    --------
    >>> df = pd.DataFrame({
    ...     'StructCond': ['Poor', 'Fair', 'Excellent'],
    ...     'AADT': [500, 2000, 150000]
    ... })
    >>> rules = {
    ...     'StructCond': {'enum': ['Poor', 'Fair', 'Good'], 'case_sensitive': False},
    ...     'AADT': {'range': [0, 100000]}
    ... }
    >>> errors = validate_dataset(df, rules)
    >>> errors
    ['StructCond has invalid values: [Excellent]',
     'AADT has 1 values outside range [0, 100000]']
    """
    errors = []
    
    for field, rules in validation_rules.items():
        if field not in df.columns:
            continue
        
        # Validate enumerated fields
        if 'enum' in rules:
            case_sens = rules.get('case_sensitive', False)
            invalid = validate_enum_field(df, field, rules['enum'], case_sens)
            if invalid:
                errors.append(f"{field} has invalid values: {invalid}")
        
        # Validate numeric ranges
        if 'range' in rules:
            min_val, max_val = rules['range']
            out_of_range = validate_numeric_range(df, field, min_val, max_val)
            if len(out_of_range) > 0:
                errors.append(
                    f"{field} has {len(out_of_range)} values outside range "
                    f"[{min_val}, {max_val}]"
                )
    
    return errors
