"""Road Criticality goal calculations."""
import pandas as pd
import numpy as np
from utils.scoring_utils import (
    calculate_weighted_average,
    normalize_minmax,
    calculate_confidence,
    apply_jenks_classification,
)


def calculate_distance_score(distance):
    if distance <= 0.5:
        return 1
    elif 0.5 < distance <= 1:
        return 0.75
    elif 1 < distance <= 1.5:
        return 0.5
    elif 1.5 < distance <= 2:
        return 0.25
    else:
        return 0

def calculate_rc(df, params):
    weights = params['criteria_weights']['rc']
    score_maps = params['score_maps']
    bins = params['bins']

    # Convert keys to int so they match the dataframe integers
    func_map = {int(k): v for k, v in score_maps['functional_classification'].items()}
    df['FncSysScr'] = df['FUNCT_SYST'].map(func_map)
    
    df['AADTScr'] = df['AADT'].astype(float)
    df['AADTScr'] = pd.cut(df['AADTScr'], bins=bins['aadt'], labels=bins['aadt_scores'], right=False).astype(float)
    
    df['MinDstImP'] = df[['Dst_Hsptl', 'Dst_EMS', 'Dst_LawEn', 'Dst_Fire']].min(axis=1)
    df['DstIMPScr'] = df['MinDstImP'].apply(calculate_distance_score)

    df['SAADT'] = df['AADTScr'] * weights['aadt']
    df['SDstIMP'] = df['DstIMPScr'] * weights['distance_to_services']
    df['SFncSys'] = df['FncSysScr'] * weights['functional_classification']
    
    df['RCScr'] = calculate_weighted_average(df, ['AADTScr', 'DstIMPScr', 'FncSysScr'],
                                              [weights['aadt'], weights['distance_to_services'], weights['functional_classification']])
    
    df['RCRank'] = df['RCScr'].rank(method='dense', ascending=False)
    present, missing, conf_str = calculate_confidence(df, ['AADTScr', 'DstIMPScr', 'FncSysScr'])
    df['RC_Present'], df['RC_Missing'], df['ConfRC'] = present, missing, conf_str
    df['RCNrm'] = normalize_minmax(df['RCScr'])
    df['RCQual'] = apply_jenks_classification(df['RCScr'])

    # NEW: mean-imputed score — null RCScr values filled with mean of non-null RCScr values
    rc_mean = df['RCScr'].mean()                                     # NEW
    df['RCScrMS'] = df['RCScr'].fillna(rc_mean)                      # NEW

    # NEW: rank, normalization, and Jenks classification based on RCScrMS
    df['RCMSRank'] = df['RCScrMS'].rank(method='dense', ascending=False)  # NEW
    df['RCMSNrm'] = normalize_minmax(df['RCScrMS'])                        # NEW
    df['RCQualMS'] = apply_jenks_classification(df['RCScrMS'])             # NEW
    return df
