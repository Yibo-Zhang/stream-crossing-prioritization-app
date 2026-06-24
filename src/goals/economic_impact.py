"""Economic Impact calculations."""
import pandas as pd
import numpy as np

def calculate_cost(df, params):
    constants = params['constants']
    score_maps = params["score_maps"]
    cost_map = {int(k): v for k, v in score_maps["cost_multiplier"].items()}
    df["CstMult"] = df["TIER"].replace(cost_map)
    df['AvgBFW'] = df[['ChanBFW1', 'ChanBFW2', 'ChanBFW3']].mean(axis=1)
    df['ReqWidth'] = constants['bankfull_multiplier'] * df['AvgBFW'] + 2
    df['Cost'] = (constants['cpi'] * constants['base_cost_per_unit'] * 
                  df['StructLen'] * df['ReqWidth'] * df['CstMult'])
    df['Cost'] = df['Cost'].replace(0, np.nan)
    return df
