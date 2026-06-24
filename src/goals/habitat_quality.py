"""Habitat Quality goal calculations."""
import pandas as pd
import numpy as np
from utils.scoring_utils import (
    calculate_weighted_average,
    normalize_minmax,
    calculate_confidence,
    apply_jenks_classification,
)


def calculate_hqg(df, params):
    weights = params['criteria_weights']['hqg']
    
    df['HQScr'] = df['HQ_WAP'].replace(0, np.nan)
    df['WAP_TIER'] = df['WAP_TIER'].replace(0, np.nan)
    
    df['WtlndScr'] = df['Wetlnd'].replace(0, np.nan)
    df['Wetlnd'] = df['Wetlnd'].map({1: 'Wetland Nearby', 0: np.nan})
    
    df['CnsvStScr'] = df['ConsvStat'].replace(0, np.nan)
    df['ConsvStat'] = df['ConsvStat'].map({1: 'Conserved Land', 0: np.nan})
    
    df['SHQ'] = df['HQScr'] * weights['habitat_quality']
    df['SWtlnd'] = df['WtlndScr'] * weights['wetland_proximity']
    df['SCnsvSt'] = df['CnsvStScr'] * weights['conservation_status']
    
    def calc_hqg_score(row):
        num = den = 0.0
        if pd.notna(row['HQScr']):
            num += row['SHQ']; den += weights['habitat_quality']
        if pd.notna(row['WtlndScr']):
            num += row['SWtlnd']; den += weights['wetland_proximity']
        if pd.notna(row['CnsvStScr']):
            num += row['SCnsvSt']; den += weights['conservation_status']
        return num / den if den > 0 else np.nan
    
    df['HQGScr'] = df.apply(calc_hqg_score, axis=1)
    df['HQGRank'] = df['HQGScr'].rank(method='dense', ascending=False)
    present, missing, conf_str = calculate_confidence(df, ['HQScr', 'WtlndScr', 'CnsvStScr'])
    df['HQG_Present'], df['HQG_Missing'], df['ConfHQG'] = present, missing, conf_str
    df['HQGNrm'] = normalize_minmax(df['HQGScr'])
    df['HQGQual'] = apply_jenks_classification(df['HQGScr'])

    # NEW: mean-imputed score — null HQGScr values filled with mean of non-null HQGScr values
    hq_mean = df['HQGScr'].mean()                                     # NEW
    df['HQGScrMS'] = df['HQGScr'].fillna(hq_mean)                      # NEW

    # NEW: rank, normalization, and Jenks classification based on HQGScrMS
    df['HQGMSRank'] = df['HQGScrMS'].rank(method='dense', ascending=False)  # NEW
    df['HQGMSNrm'] = normalize_minmax(df['HQGScrMS'])                        # NEW
    df['HQGQualMS'] = apply_jenks_classification(df['HQGScrMS'])             # NEW
    return df
