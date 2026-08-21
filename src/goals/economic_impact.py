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

Bankfull width guard
--------------------
Required width is ReqWidth = bankfull_multiplier * AvgBFW + 2, so a crossing
with no bankfull width measurement (AvgBFW = 0) does not produce a zero cost.
It produces a cost computed against a 2 ft required width, which the existing
``Cost.replace(0, np.nan)`` guard cannot catch because the product is not zero.

In data/input/crossings.csv this affects a large share of the dataset:

    AvgBFW = 0                                   2,763 of 5,592 records (49.4%)
    of those, a cost was still reported          2,469 records
    dollars reported against a 2 ft width        about $219.8M
    share of the $2.16B statewide reported total about 10%

A crossing cannot be replaced with a 2 ft opening, so those figures were not
planning-level estimates of anything. Cost is now left missing whenever AvgBFW
is zero, negative or absent, on the same reasoning already applied to a zero
opening area in Structural Risk and to a zero computed cost here: a value that
is physically infeasible indicates absent input data, not a cheap project.

Recording the reason
--------------------
CostBasis states, per crossing, why a cost is or is not reported, so a blank
CostEstimate in the workbook is not read as a zero-cost project. The column is
descriptive and does not enter any score.

Known open item, not changed here
---------------------------------
41 records carry a mix of zero and positive readings across ChanBFW1, ChanBFW2
and ChanBFW3. A zero alongside positive readings is more likely an unrecorded
measurement than a real zero-width channel, and including it lowers AvgBFW and
therefore the estimate. AvgBFW remains the plain arithmetic mean of the three
readings, unchanged, pending a project decision. Those records are counted in
the cost_summary return so the size of the question stays visible.
"""
import numpy as np
import pandas as pd

from utils.report_spec import round_cost

DEFAULT_COST_ROUND_BASE = 10000
DEFAULT_COST_ROUND_MODE = "up"

BFW_FIELDS = ["ChanBFW1", "ChanBFW2", "ChanBFW3"]

# CostBasis values.
BASIS_ESTIMATED = "Estimated"
BASIS_NO_BFW = "Not estimated: no bankfull width"
BASIS_NO_INPUTS = "Not estimated: missing structure inputs"


def calculate_cost(df, params):
    """Add the replacement cost columns to ``df`` and return it.

    Columns added
    -------------
    CstMult       cost multiplier from the NHDOT road tier
    AvgBFW        mean of ChanBFW1, ChanBFW2, ChanBFW3
    ReqWidth      required replacement width, bankfull_multiplier * AvgBFW + 2
    Cost          unrounded cost in dollars, NaN where not estimable
    CostEstimate  Cost rounded to the reporting increment
    CostBasis     why a cost is or is not reported
    """
    constants = params['constants']
    score_maps = params["score_maps"]

    # TIER here is the NHDOT road tier from the road inventory join, not the
    # Wildlife Action Plan habitat tier. The cost_multiplier map is keyed 0-6,
    # which matches the road tier domain (WAP_TIER only takes 0-3).
    cost_map = {int(k): v for k, v in score_maps["cost_multiplier"].items()}
    df["CstMult"] = df["TIER"].replace(cost_map)

    bfw = df[BFW_FIELDS].apply(pd.to_numeric, errors="coerce")
    df['AvgBFW'] = bfw.mean(axis=1)

    # A bankfull width of zero, a negative width, or no reading at all leaves
    # the required replacement width undefined rather than equal to the 2 ft
    # constant term.
    has_bfw = df['AvgBFW'].notna() & (df['AvgBFW'] > 0)

    df['ReqWidth'] = constants['bankfull_multiplier'] * df['AvgBFW'] + 2
    df['ReqWidth'] = df['ReqWidth'].where(has_bfw)

    df['Cost'] = (constants['cpi'] * constants['base_cost_per_unit'] *
                  df['StructLen'] * df['ReqWidth'] * df['CstMult'])

    # Retained from the previous revision: a computed cost of zero comes from a
    # zero structure length or a zero multiplier and is equally implausible.
    df['Cost'] = df['Cost'].replace(0, np.nan)
    df['Cost'] = df['Cost'].where(has_bfw)

    df['CostEstimate'] = round_cost(
        df['Cost'],
        base=constants.get('cost_round_base', DEFAULT_COST_ROUND_BASE),
        mode=constants.get('cost_round_mode', DEFAULT_COST_ROUND_MODE),
    )

    df['CostBasis'] = np.where(
        df['Cost'].notna(), BASIS_ESTIMATED,
        np.where(has_bfw, BASIS_NO_INPUTS, BASIS_NO_BFW),
    )
    return df


def cost_summary(df):
    """Return counts describing cost coverage for the current run.

    Reported by the CLI and carried onto the Run Settings sheet so a reader can
    see how much of the extent the cost column actually covers.
    """
    if 'AvgBFW' not in df.columns:
        return {}

    bfw = df[BFW_FIELDS].apply(pd.to_numeric, errors="coerce") if all(
        f in df.columns for f in BFW_FIELDS) else None

    mixed = 0
    if bfw is not None:
        mixed = int(((bfw == 0).any(axis=1) & (bfw > 0).any(axis=1)).sum())

    no_bfw = int((df['AvgBFW'].isna() | (df['AvgBFW'] <= 0)).sum())
    estimated = int(df['Cost'].notna().sum()) if 'Cost' in df.columns else 0

    return {
        "crossings": int(len(df)),
        "cost_estimated": estimated,
        "no_bankfull_width": no_bfw,
        "missing_structure_inputs": int(len(df)) - estimated - no_bfw,
        "mixed_zero_and_positive_bfw_readings": mixed,
        "total_cost_estimated": float(df['Cost'].sum(skipna=True))
        if 'Cost' in df.columns else 0.0,
    }
