"""Input/output utilities for loading and saving data."""
import pandas as pd
import json


def load_csv(filepath):
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
    return pd.read_csv(filepath)


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
