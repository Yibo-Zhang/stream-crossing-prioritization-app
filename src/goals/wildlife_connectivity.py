"""Wildlife Connectivity goal calculations."""
import pandas as pd
import numpy as np
from utils.scoring_utils import (
    calculate_weighted_average,
    normalize_minmax,
    calculate_confidence,
    apply_jenks_classification,
)

def calculate_wl(df, params):
    weights = params['criteria_weights']['wl']
    score_maps = params['score_maps']
    
    df['AOPScr'] = df['AOP_Score'].map(score_maps['aop'])
    df['SpSpScr'] = df['Sp_Sp_FG'].replace(0, np.nan)
    df['Sp_Sp_FG'] = df['Sp_Sp_FG'].map({1: 'Present', 0: np.nan})
    df['WlCoScr'] = df['WlCo']
    df['WlCo'] = df['WlCo'].map({1: 'Wildlife Corridor', 0: np.nan})

    df['SAOP'] = df['AOPScr'] * weights['aop']
    df['SSpSp'] = df['SpSpScr'] * weights['special_species']
    df['SWlCo'] = df['WlCoScr'] * weights['terrestrial_organism_passage']
    
    def calc_wl_score(row):
        num = 0.0
        den = 0.0
        if pd.notna(row['AOPScr']):
            num += row['SAOP']
            den += weights['aop']
            if row['AOPScr'] > 0 and pd.notna(row['SpSpScr']):
                num += row['SSpSp']
                den += weights['special_species']

        if pd.notna(row['WlCoScr']):
            num += row['SWlCo']
            den += weights['terrestrial_organism_passage']

        return num / den if den > 0 else np.nan
    
    df['WLScr'] = df.apply(calc_wl_score, axis=1)
    df['WLRank'] = df['WLScr'].rank(method='dense', ascending=False)
    present, missing, conf_str = calculate_confidence(df, ['AOPScr', 'SpSpScr', 'WlCoScr'])
    df['WL_Present'], df['WL_Missing'], df['ConfWL'] = present, missing, conf_str
    df['WLNrm'] = normalize_minmax(df['WLScr'])
    df['WLQual'] = apply_jenks_classification(df['WLScr'])
    
    # NEW: mean-imputed score — null WLScr values filled with mean of non-null WLScr values
    wl_mean = df['WLScr'].mean()                                     # NEW
    df['WLScrMS'] = df['WLScr'].fillna(wl_mean)                      # NEW

    # NEW: rank, normalization, and Jenks classification based on WLScrMS
    df['WLMSRank'] = df['WLScrMS'].rank(method='dense', ascending=False)  # NEW
    df['WLMSNrm'] = normalize_minmax(df['WLScrMS'])                        # NEW
    df['WLQualMS'] = apply_jenks_classification(df['WLScrMS'])             # NEW
    
    return df
