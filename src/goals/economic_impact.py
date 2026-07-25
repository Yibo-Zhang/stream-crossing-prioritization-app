"""Economic Impact calculations.

Replacement cost is reported alongside the priority results as a planning
reference and does not enter the priority score.

v1.2 change: the reporting column formerly named RoundCost in the ARPA-phase
workbook (where it held cost in millions of dollars) is replaced by
CostEstimate, a dollar figure rounded to a whole reporting increment so the
last digits read as zeros, for example 150,000 or 1,270,000. The rounding base
and direction are configurable in configs/params.json under "constants":

    cost_round_base  dollars per increment, default 10000
    cost_round_mode  "up" (ceiling, conservative) or "nearest"

The unrounded Cost column is retained for traceability.
"""
import pandas as pd
import numpy as np

from utils.report_spec import round_cost

DEFAULT_COST_ROUND_BASE = 10000
DEFAULT_COST_ROUND_MODE = "up"


def calculate_cost(df, params):
    constants = params['constants']
    score_maps = params["score_maps"]

    # TIER here is the NHDOT road tier from the road inventory join, not the
    # Wildlife Action Plan habitat tier. The cost_multiplier map is keyed 0-6,
    # which matches the road tier domain (WAP_TIER only takes 0-3).
    cost_map = {int(k): v for k, v in score_maps["cost_multiplier"].items()}
    df["CstMult"] = df["TIER"].replace(cost_map)

    df['AvgBFW'] = df[['ChanBFW1', 'ChanBFW2', 'ChanBFW3']].mean(axis=1)
    df['ReqWidth'] = constants['bankfull_multiplier'] * df['AvgBFW'] + 2
    df['Cost'] = (constants['cpi'] * constants['base_cost_per_unit'] *
                  df['StructLen'] * df['ReqWidth'] * df['CstMult'])
    df['Cost'] = df['Cost'].replace(0, np.nan)

    df['CostEstimate'] = round_cost(
        df['Cost'],
        base=constants.get('cost_round_base', DEFAULT_COST_ROUND_BASE),
        mode=constants.get('cost_round_mode', DEFAULT_COST_ROUND_MODE),
    )
    return df
