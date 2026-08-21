"""Environmental Quality goal calculations."""
import pandas as pd
import numpy as np
from utils.scoring_utils import (
    calculate_weighted_average,
    normalize_minmax,
    calculate_confidence,
    apply_jenks_classification,
)



# Component maps, used only when configs/params.json does not carry them. The
# values match the maps that were hardcoded here before, so a params file
# written for an earlier version scores identically.
FALLBACK_EROSION_MAPS = {
    "outlet_scour": {"None": 0, "Low": 0.33, "Medium": 0.66, "High": 1},
    "sediment_fill": {"Open": 0, "1/4 Full": 0, "1/2 Full": 0.33,
                      "3/4 Full": 0.66, "High": 1},
    "bank_erosion": {"None": 0, "Low": 0.5, "High": 1},
    "bank_armoring": {"Intact": 0, "Failing": 1},
}

EROSION_COMPONENT_COLS = [
    'UsScourScr', 'DsScourScr', 'ObstrctScr', 'ScourScr',
    'SedFillScr', 'UsBnkErScr', 'DsBnkErScr', 'UsArmScr', 'DsArmScr',
]


def calculate_erosion_score(df, score_maps=None):
    """
    Calculate erosion score from 9 erosion-related components.
    Returns mean of all available components (dynamic).

    Parameters
    ----------
    df : pd.DataFrame
        Input dataframe.
    score_maps : dict, optional
        params['score_maps']. The four ordinal component maps (outlet_scour,
        sediment_fill, bank_erosion, bank_armoring) are read from here so the
        Definitions sheet and the validation coverage check describe the same
        mapping the model applies. FALLBACK_EROSION_MAPS is used for any map
        the params file does not define.

    Notes
    -----
    A value that is absent from its component map is scored NaN by Series.map
    and drops out of the component mean. utils.validation.find_unscored_values
    reports these at validation time so the gap is visible rather than silent.
    """
    score_maps = score_maps or {}

    def component_map(name):
        """Return one component map, preferring params over the fallback.

        An empty map in params is treated as absent rather than as an
        instruction to score nothing, so a truncated params file degrades to
        the documented default instead of silently voiding a component.
        """
        return score_maps.get(name) or FALLBACK_EROSION_MAPS[name]

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
    df['ScourScr'] = df['OutScour'].map(component_map('outlet_scour'))

    # Structure Filled With Sediment
    df['SedFillScr'] = df['StructSed'].map(component_map('sediment_fill'))

    # Upstream Bank Erosion
    df['UsBnkErScr'] = df['UsBankEros'].map(component_map('bank_erosion'))

    # Downstream Bank Erosion
    df['DsBnkErScr'] = df['DsBankEros'].map(component_map('bank_erosion'))

    # Upstream Bank Armoring
    df['UsArmScr'] = df['UsBankArmo'].map(component_map('bank_armoring'))

    # Downstream Bank Armoring
    df['DsArmScr'] = df['DsBankArmo'].map(component_map('bank_armoring'))

    # Calculate erosion score as mean of all 9 components
    df['ErosScr'] = df[EROSION_COMPONENT_COLS].mean(axis=1)
    
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
    
    # Calculate erosion score. score_maps is passed through so the four
    # ordinal component maps are read from configs/params.json, which is what
    # makes the Definitions sheet and the validation coverage check describe
    # the mapping the model actually applies rather than a second copy of it.
    df = calculate_erosion_score(df, score_maps)
    
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
    
    # Calculate EQ score dynamically.
    # Special rule (Final_scoring_decisions.docx section 4): the two water
    # quality criteria enter the Environmental Quality score only when the
    # erosion score is present and strictly positive. Testing ErosScr directly,
    # rather than the weighted SEros, avoids the NaN trap where a missing erosion
    # score gives SEros = NaN and NaN != 0 evaluates True, which previously
    # admitted water quality for crossings that have no erosion score at all.
    def calc_eq_score(row):
        num = 0.0
        den = 0.0

        eros_present_positive = pd.notna(row['ErosScr']) and row['ErosScr'] > 0

        if pd.notna(row['ErosScr']):
            num += row['SEros']
            den += weights['erosion']

        if pd.notna(row['GCScr']):
            num += row['SGC']
            den += weights['geomorphic_compatibility']

        # Only include WQI if the erosion score is present and positive.
        if pd.notna(row['WQIScr']) and eros_present_positive:
            num += row['SWQI']
            den += weights['water_quality']

        # Only include WWQI if the erosion score is present and positive.
        if pd.notna(row['WWQIScr']) and eros_present_positive:
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
