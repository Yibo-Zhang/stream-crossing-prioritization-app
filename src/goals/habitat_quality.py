"""Habitat Quality goal calculations.

Beta v2 change: the first criterion of this goal is renamed from "habitat
quality" to "Habitat Condition Tier", per Final_scoring_decisions.docx section 8
and Memo_Beta_to_Pilot_Changes.docx section 5.1. The rename removes the
collision between the criterion name and the goal name. The short code used
throughout the model is HCT:

    params key   habitat_quality      -> habitat_condition_tier
    score column HQScr                -> HCTScr
    weighted     SHQ                  -> SHCT

The source field HQ_WAP is unchanged: it is produced by the upstream GIS step
from the 2020 NH Wildlife Action Plan habitat condition tiers and is not renamed
here. The goal itself keeps the key habitat_quality in goal_weights.
"""
import pandas as pd
import numpy as np
from utils.scoring_utils import (
    calculate_weighted_average,
    normalize_minmax,
    calculate_confidence,
    apply_jenks_classification,
)

# Current key, plus the pre-Beta-v2 key so an older params.json still loads.
HCT_WEIGHT_KEYS = ("habitat_condition_tier", "habitat_quality")


def _hct_weight(weights):
    """Return the Habitat Condition Tier criterion weight.

    Accepts either the Beta v2 key or the legacy key so that a params file
    written for the Pilot model does not raise KeyError. Raises with an explicit
    message if neither is present.
    """
    for key in HCT_WEIGHT_KEYS:
        if key in weights:
            return weights[key]
    raise KeyError(
        "criteria_weights['hqg'] must define 'habitat_condition_tier' "
        f"(or the legacy key 'habitat_quality'); found {sorted(weights)}"
    )


def calculate_hqg(df, params):
    weights = params['criteria_weights']['hqg']
    w_hct = _hct_weight(weights)

    # Habitat Condition Tier (was: habitat quality)
    df['HCTScr'] = df['HQ_WAP']
    df['WAP_TIER'] = df['WAP_TIER'].replace(0, np.nan)

    df['WtlndScr'] = df['Wetlnd']
    df['Wetlnd'] = df['Wetlnd'].map({1: 'Wetland Nearby', 0: np.nan})

    df['CnsvStScr'] = df['ConsvStat']
    df['ConsvStat'] = df['ConsvStat'].map({1: 'Conserved Land', 0: np.nan})

    df['SHCT'] = df['HCTScr'] * w_hct
    df['SWtlnd'] = df['WtlndScr'] * weights['wetland_proximity']
    df['SCnsvSt'] = df['CnsvStScr'] * weights['conservation_status']

    def calc_hqg_score(row):
        num = den = 0.0
        if pd.notna(row['HCTScr']):
            num += row['SHCT']; den += w_hct
        if pd.notna(row['WtlndScr']):
            num += row['SWtlnd']; den += weights['wetland_proximity']
        if pd.notna(row['CnsvStScr']):
            num += row['SCnsvSt']; den += weights['conservation_status']
        return num / den if den > 0 else np.nan

    df['HQGScr'] = df.apply(calc_hqg_score, axis=1)
    df['HQGRank'] = df['HQGScr'].rank(method='dense', ascending=False)
    present, missing, conf_str = calculate_confidence(df, ['HCTScr', 'WtlndScr', 'CnsvStScr'])
    df['HQG_Present'], df['HQG_Missing'], df['ConfHQG'] = present, missing, conf_str
    df['HQGNrm'] = normalize_minmax(df['HQGScr'])
    df['HQGQual'] = apply_jenks_classification(df['HQGScr'])

    # Mean-imputed score: null HQGScr values filled with the mean of non-null HQGScr
    hq_mean = df['HQGScr'].mean()
    df['HQGScrMS'] = df['HQGScr'].fillna(hq_mean)

    # Rank, normalization, and Jenks classification based on HQGScrMS
    df['HQGMSRank'] = df['HQGScrMS'].rank(method='dense', ascending=False)
    df['HQGMSNrm'] = normalize_minmax(df['HQGScrMS'])
    df['HQGQualMS'] = apply_jenks_classification(df['HQGScrMS'])
    return df
