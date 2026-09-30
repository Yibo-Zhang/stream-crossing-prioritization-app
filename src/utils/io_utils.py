"""Input/output utilities for loading and saving data."""
import pandas as pd
import json
import numpy as np

# Preserve pandas' usual blank/null spellings except literal "None": SADES
# uses that value for an observed absence of scour/erosion, scored as zero.
# Keep this explicit so all input entry points share the same CSV semantics.
CSV_NA_VALUES = [
    "", "#N/A", "#N/A N/A", "#NA", "-1.#IND", "-1.#QNAN", "-NaN", "-nan",
    "1.#IND", "1.#QNAN", "<NA>", "N/A", "NA", "NULL", "NaN", "n/a", "nan", "null",
]

ZERO_OBSERVATION_FIELDS = (
    "UsUndermin", "DsUndermin", "UsObstruct", "OutScour", "UsBankEros", "DsBankEros",
)


def _read_zero_observation(value):
    return np.nan if value in CSV_NA_VALUES else value

def load_csv(filepath, **kwargs):
    """
    Load CSV file into pandas DataFrame.
    
    Parameters
    ----------
    filepath : str
        Path to CSV file
        
    Returns
    -------
    pd.DataFrame
        Loaded dataframe
    """
    # Converters override NA parsing only for these categorical fields. Numeric
    # and other columns retain pandas' default missing-value/type inference.
    converters = {field: _read_zero_observation for field in ZERO_OBSERVATION_FIELDS}
    return pd.read_csv(filepath, converters=converters, **kwargs)


def save_csv(df, filepath):
    """
    Save pandas DataFrame to CSV file.
    
    Parameters
    ----------
    df : pd.DataFrame
        Dataframe to save
    filepath : str
        Path where CSV should be saved
    """
    df.to_csv(filepath, index=False)


def load_params(filepath):
    """
    Load parameters from JSON file.
    
    Parameters
    ----------
    filepath : str
        Path to JSON parameter file
        
    Returns
    -------
    dict
        Parameters dictionary
    """
    with open(filepath, 'r') as f:
        return json.load(f)


def save_params(params, filepath):
    """
    Save parameters dictionary to JSON file.
    
    Parameters
    ----------
    params : dict
        Parameters dictionary
    filepath : str
        Path where JSON should be saved
    """
    with open(filepath, 'w') as f:
        json.dump(params, f, indent=2)
