"""Environmental Quality goal calculations."""
import pandas as pd
import numpy as np
from utils.scoring_utils import (
    calculate_weighted_average,
    normalize_minmax,
    calculate_confidence,
    apply_jenks_classification,
)



def calculate_erosion_score(df):
    """
    Calculate erosion score from 9 erosion-related components.
    Returns mean of all available components (dynamic).
    """
    def map_undermining_scour(value):
        """Map undermining inventory value to erosion score.
        'None' -> 0; any non-None undermining category -> 1; missing/blank -> NaN.
        """
        if pd.isna(value) or value == '':
            return np.nan
        if value == 'None':
            return 0
        return 1

    # Upstream Scour (Undermining Structure)
    df['UsScourScr'] = df['UsUndermin'].apply(map_undermining_scour)

    # Downstream Scour (Undermining Structure)
    df['DsScourScr'] = df['DsUndermin'].apply(map_undermining_scour)
    

    # Structure Opening Mostly Obstructed
    def map_obstruction(value):
        """Map obstruction value to erosion score.
        'None' -> 0; any other value -> 1; missing/blank -> NaN.
        """
        if pd.isna(value) or value == '':
            return np.nan
        if value == 'None':
            return 0
        return 1

    # Structure Opening Mostly Obstructed
    df['ObstrctScr'] = df['UsObstruct'].apply(map_obstruction)
    
    # Scour of the Streambed at the Outlet
    df['ScourScr'] = df['OutScour'].map({
        'None': 0,
        'Low': 0.33,
        'Medium': 0.66,
        'High': 1
    })
    
    # Structure Filled With Sediment
    df['SedFillScr'] = df['StructSed'].map({
        'Open': 0,
        '1/4 Full': 0,
        '1/2 Full': 0.33,
        '3/4 Full': 0.66,
        'High': 1
    })
    
    # Upstream Bank Erosion
    df['UsBnkErScr'] = df['UsBankEros'].map({
        'None': 0,
        'Low': 0.5,
        'High': 1
    })
    
    # Downstream Bank Erosion
    df['DsBnkErScr'] = df['DsBankEros'].map({
        'None': 0,
        'Low': 0.5,
        'High': 1
    })
    
    # Upstream Bank Armoring
    df['UsArmScr'] = df['UsBankArmo'].map({
        'Intact': 0,
        'Failing': 1
    })
    
    # Downstream Bank Armoring
    df['DsArmScr'] = df['DsBankArmo'].map({
        'Intact': 0,
        'Failing': 1
    })
    
    # Calculate erosion score as mean of all 9 components
    erosion_cols = ['UsScourScr', 'DsScourScr', 'ObstrctScr', 'ScourScr', 
                   'SedFillScr', 'UsBnkErScr', 'DsBnkErScr', 'UsArmScr', 'DsArmScr']
    df['ErosScr'] = df[erosion_cols].mean(axis=1)
    
    # Apply Jenks classification to erosion
    df['Erosion'] = apply_jenks_classification(df['ErosScr'])
    
    return df


def calculate_eq(df, params):
    """
    Calculate Environmental Quality (EQ) goal score.
    
    Parameters
    ----------
    df : pd.DataFrame
        Input dataframe with raw environmental quality data
    params : dict
        Parameters dictionary containing weights and score maps
        
    Returns
    -------
    pd.DataFrame
        Dataframe with EQ scores, ranks, and classifications added
    """
    weights = params['criteria_weights']['eq']
    score_maps = params['score_maps']
    
    # Calculate erosion score
    df = calculate_erosion_score(df)
    
    # Geomorphic Compatibility Score
    df['GCScr'] = df['GC_Score'].map(score_maps['geomorphic_compatibility'])
    
    # Water Quality Impairment
    df['WQIScr'] = df['Impair']
    df['Impair'] = df['Impair'].map({1: 'Impaired', 0: np.nan})

    # Watershed Water Quality Impairment
    df['WWQIScr'] = df['WWQI']
    df['WImpair'] = df['WWQI'].map({1: 'Impaired', 0: np.nan})

    # Calculate weighted criterion scores
    df['SEros'] = df['ErosScr'] * weights['erosion']
    df['SGC'] = df['GCScr'] * weights['geomorphic_compatibility']
    df['SWQI'] = df['WQIScr'] * weights['water_quality']
    df['SWWQI'] = df['WWQIScr'] * weights['water_quality']
    
    # Calculate EQ score dynamically
    # Special rule: WQI only included if there is erosion (SEros != 0)
    def calc_eq_score(row):
        num = 0.0
        den = 0.0
        
        if pd.notna(row['ErosScr']):
            num += row['SEros']
            den += weights['erosion']
        
        if pd.notna(row['GCScr']):
            num += row['SGC']
            den += weights['geomorphic_compatibility']
        
        # Only include WQI if erosion score exists and is non-zero
        if pd.notna(row['WQIScr']) and row['SEros'] != 0:
            num += row['SWQI']
            den += weights['water_quality']

        # Only include WWQI if erosion score exists and is non-zero
        if pd.notna(row['WWQIScr']) and row['SEros'] != 0:
            num += row['SWWQI']
            den += weights['water_quality']
        
        return num / den if den > 0 else np.nan
    
    df['EQScr'] = df.apply(calc_eq_score, axis=1)
    
    # Rank by EQ score
    df['EQRank'] = df['EQScr'].rank(method='dense', ascending=False)
    
    # Calculate confidence
    eq_cols = ['ErosScr', 'GCScr', 'WQIScr', 'WWQIScr']
    present, missing, conf_str = calculate_confidence(df, eq_cols)
    df['EQ_Present'] = present
    df['EQ_Missing'] = missing
    df['ConfEQ'] = conf_str
    
    # Normalize EQ score (0-1)
    df['EQNrm'] = normalize_minmax(df['EQScr'])
    
    # Apply Jenks classification
    df['EQQual'] = apply_jenks_classification(df['EQScr'])

    # NEW: mean-imputed score — null EQScr values filled with mean of non-null EQScr values
    eq_mean = df['EQScr'].mean()                                     # NEW
    df['EQScrMS'] = df['EQScr'].fillna(eq_mean)                      # NEW

    # NEW: rank, normalization, and Jenks classification based on EQScrMS
    df['EQMSRank'] = df['EQScrMS'].rank(method='dense', ascending=False)  # NEW
    df['EQMSNrm'] = normalize_minmax(df['EQScrMS'])                        # NEW
    df['EQQualMS'] = apply_jenks_classification(df['EQScrMS'])             # NEW
    
    return df
