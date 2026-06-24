"""Structural Risk goal calculations."""
import pandas as pd
import numpy as np
from utils.scoring_utils import (
    calculate_weighted_average,
    normalize_minmax,
    calculate_confidence,
    apply_jenks_classification,
)

def calculate_condition_score(row):
    struct, inlet, outlet = row['StrConScr'], row['InConScr'], row['OutConScr']
    valid_scores = [struct, inlet, outlet]
    num_valid = sum(pd.notna(valid_scores))
    if num_valid == 3:
        return 0.5 * struct + 0.3 * inlet + 0.2 * outlet
    elif num_valid == 2:
        if pd.notna(struct) and pd.notna(inlet):
            return (0.5 / 0.8) * struct + (0.3 / 0.8) * inlet
        elif pd.notna(struct) and pd.notna(outlet):
            return (0.5 / 0.7) * struct + (0.2 / 0.7) * outlet
        elif pd.notna(inlet) and pd.notna(outlet):
            return (0.3 / 0.5) * inlet + (0.2 / 0.5) * outlet
    elif num_valid == 1:
        if pd.notna(struct):
            return struct
        elif pd.notna(inlet):
            return inlet
        elif pd.notna(outlet):
            return outlet
    return np.nan

def calculate_sr(df, params):
    weights = params['criteria_weights']['sr']
    score_maps = params['score_maps']
    bins = params['bins']
    
    df['StrConScr'] = df['StructCond'].map(score_maps['condition'])
    df['InConScr'] = df['UsHwCon'].map(score_maps['condition'])
    df['OutConScr'] = df['DsHwCon'].map(score_maps['condition'])
    df['CondScr'] = df.apply(calculate_condition_score, axis=1)
    
    df['UsSize'] = df.apply(lambda row: (row['UsWidth'] ** 2 * 3.14 / 4) if row['StructType'] == 'Round Culvert' 
                            else row['UsWidth'] * row['UsOpenHght'], axis=1)
    df['UsSize'] = df['UsSize'].replace(0, np.nan)
    df['SizeScr'] = pd.cut(df['UsSize'], bins=bins['size'], labels=bins['size_scores'], right=True).astype(float)
    
    #removed depth of cover scoring according to the discussion on numerous bridges with 0 and large depth of cover not necessarily being a risk factor.

    df['MatScr'] = df['StructMat'].map(score_maps['material'])
    df['SCond'] = df['CondScr'] * weights['condition']
    df['SSize'] = df['SizeScr'] * weights['size']
    df['SMat'] = df['MatScr'] * weights['material']
    
    def calc_sr_score(row):
        cond = row['CondScr']
        if pd.notna(cond) and cond > 0:
            num = sum([row['SCond'] if pd.notna(cond) else 0, row['SSize'] if pd.notna(row['SizeScr']) else 0, row['SMat'] if pd.notna(row['MatScr']) else 0])
            den = sum([weights['condition'] if pd.notna(cond) else 0, weights['size'] if pd.notna(row['SizeScr']) else 0, weights['material'] if pd.notna(row['MatScr']) else 0])
        else:
            num = sum([row['SCond'] if pd.notna(cond) else 0, row['SMat'] if pd.notna(row['MatScr']) else 0])
            den = sum([weights['condition'] if pd.notna(cond) else 0, weights['material'] if pd.notna(row['MatScr']) else 0])
        return num / den if den > 0 else np.nan
    
    df['SRScr'] = df.apply(calc_sr_score, axis=1)
    df['SRRank'] = df['SRScr'].rank(method='dense', ascending=False)
    present, missing, conf_str = calculate_confidence(df, ['CondScr', 'SizeScr', 'MatScr'])
    df['SR_Present'], df['SR_Missing'], df['ConfSR'] = present, missing, conf_str
    df['SRNrm'] = normalize_minmax(df['SRScr'])
    df['SRQual'] = apply_jenks_classification(df['SRScr'])
    
    # NEW: mean-imputed score — null SRScr values filled with mean of non-null SRScr values
    sr_mean = df['SRScr'].mean()                                     # NEW
    df['SRScrMS'] = df['SRScr'].fillna(sr_mean)                      # NEW

    # NEW: rank, normalization, and Jenks classification based on SRScrMS
    df['SRMSRank'] = df['SRScrMS'].rank(method='dense', ascending=False)  # NEW
    df['SRMSNrm'] = normalize_minmax(df['SRScrMS'])                        # NEW
    df['SRQualMS'] = apply_jenks_classification(df['SRScrMS'])             # NEW

    return df
