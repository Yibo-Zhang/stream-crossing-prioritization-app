"""Reporting specification shared by the CLI model and the Excel report builder.

Location in repo: src/utils/report_spec.py

Before Beta v2 the sheet layout was declared three times: in
``src/model.py:save_results``, in ``scripts/excel_report.py`` and again in
``scripts/generate_excel_report.py``. The three copies had already drifted
(``CoverDepth`` survived in one after the criterion was removed from the model,
``WlCo`` and ``WImpair`` were never added to the workbook at all). This module
holds the layout once so the CSV outputs, the file-based workbook and the
in-memory workbook served by the Streamlit app cannot disagree.

Contents:
  MODEL_VERSION       label printed by the CLI, the app header and the workbook
  SHEET_COLUMNS       column order per sheet, model outputs only
  BETA_COMPARE_COLS   columns duplicated with the Beta_ prefix for comparison
  USER_COLUMNS        blank columns reserved for local review
  SHEET_COLORS        tab and header fill per sheet
  load_field_metadata reads configs/metadata.csv for the header hover notes
  round_cost          reporting-level rounding of the replacement cost estimate
"""
from pathlib import Path

import numpy as np
import pandas as pd

MODEL_VERSION = "Beta v2"
MODEL_TITLE = "Stream Crossing Prioritization Model"

# repo root: utils/ -> src/ -> repo root
REPO_ROOT = Path(__file__).resolve().parents[2]
METADATA_PATH = REPO_ROOT / "configs" / "metadata.csv"
BASELINE_DIR = REPO_ROOT / "data" / "baseline"
BASELINE_PATH = BASELINE_DIR / "baseline_all.csv.gz"

JOIN_KEY = "SADES_ID"
LEAD_COLUMNS = ["SADES_ID", "Location", "Landowner"]
USER_COLUMNS = ["LocalPriority", "LocalNotes"]
BETA_PREFIX = "Beta_"

# Sort key for every sheet. Beta v2 reports the mean-substituted family only.
SORT_COLUMN = "TotMSRank"

# Total-score block repeated at the right-hand end of every goal sheet.
TOTAL_BLOCK = ["TotScrMS", "TotMSRank", "TotQualMS", "ConfTot"]

# Kept at four decimals in file output; everything else numeric is rounded to two.
HIGH_PRECISION_COLUMNS = {"TotScr", "TotScrMS"}

# --------------------------------------------------------------------------- #
# Sheet layout
#
# Rank and Qual columns computed on the dynamic (non-imputed) scores (FVRank,
# FVQual, TotRank, TotQual, ...) are still produced by the model and still
# written to results_all.csv and to the All Results sheet. They are excluded
# from the goal sheets and from Final Results so that a reviewer sees a single
# ranking family and cannot accidentally compare a mean-substituted rank against
# a dynamic one.
# --------------------------------------------------------------------------- #

SHEET_COLUMNS = {
    "Flood Vulnerability": LEAD_COLUMNS + [
        "HC_2yr", "HC_10yr", "HC_25yr", "HC_50yr", "HC_100yr", "BlckFlg",
        "FVMSRank", "FVQualMS", "ConfFV",
    ] + TOTAL_BLOCK,

    "Road Criticality": LEAD_COLUMNS + [
        "AADT", "MinDstImP", "FUNCT_SYST",
        "RCMSRank", "RCQualMS", "ConfRC",
    ] + TOTAL_BLOCK,

    "Structural Risk": LEAD_COLUMNS + [
        # CoverDepth is deliberately absent: the depth-of-cover criterion was
        # removed from Structural Risk in the Pilot model.
        "StructCond", "UsHwCon", "DsHwCon", "UsSize", "StructMat",
        "SRMSRank", "SRQualMS", "ConfSR",
    ] + TOTAL_BLOCK,

    "Wildlife Connectivity": LEAD_COLUMNS + [
        "AOP_Score", "Sp_Sp_FG", "WlCo",          # WlCo added in the Pilot model
        "WLMSRank", "WLQualMS", "ConfWL",
    ] + TOTAL_BLOCK,

    "Habitat Quality": LEAD_COLUMNS + [
        "WAP_TIER", "Wetlnd", "ConsvStat",
        "HQGMSRank", "HQGQualMS", "ConfHQG",
    ] + TOTAL_BLOCK,

    "Environmental Quality": LEAD_COLUMNS + [
        "Erosion", "GC_Score", "Impair", "WImpair",   # WImpair added in the Pilot model
        "EQMSRank", "EQQualMS", "ConfEQ",
    ] + TOTAL_BLOCK,

    "Environmental Justice": LEAD_COLUMNS + [
        "EJ", "ConfTot",
        "TotScrMS", "TotMSRank", "TotQualMS",
    ],

    "Final Results": LEAD_COLUMNS + [
        "HC_2yr", "HC_10yr", "HC_25yr", "HC_50yr", "HC_100yr", "BlckFlg",
        "FVMSRank", "FVQualMS",
        "AADT", "MinDstImP", "FUNCT_SYST",
        "RCMSRank", "RCQualMS",
        "StructCond", "UsHwCon", "DsHwCon", "UsSize", "StructMat",
        "SRMSRank", "SRQualMS",
        "AOP_Score", "Sp_Sp_FG", "WlCo",
        "WLMSRank", "WLQualMS",
        "WAP_TIER", "Wetlnd", "ConsvStat",
        "HQGMSRank", "HQGQualMS",
        "Erosion", "GC_Score", "Impair", "WImpair",
        "EQMSRank", "EQQualMS",
        "EJ", "CostEstimate", "ConfTot",
        "TotScrMS", "TotMSRank", "RoundScoreMS", "TotQualMS",
    ],
}

# Sheet name -> results_<name>.csv written by the CLI model.
CSV_OUTPUT_NAMES = {
    "Flood Vulnerability": "flood_vulnerability",
    "Road Criticality": "road_criticality",
    "Structural Risk": "structural_risk",
    "Wildlife Connectivity": "wildlife_connectivity",
    "Habitat Quality": "habitat_quality",
    "Environmental Quality": "environmental_quality",
    "Environmental Justice": "environmental_justice",
    "Final Results": "final_results",
}

# Columns re-read from the Beta v2 default-weight, full-extent baseline and
# appended with the Beta_ prefix. Only model-derived results are duplicated.
# Raw field attributes (AADT, StructCond, ...) and the confidence strings are
# properties of the crossing record, not of the run, so they are identical in
# both runs and would only widen the sheet.
BETA_COMPARE_COLS = {
    "Flood Vulnerability": ["FVMSRank", "FVQualMS", "TotScrMS", "TotMSRank", "TotQualMS"],
    "Road Criticality": ["RCMSRank", "RCQualMS", "TotScrMS", "TotMSRank", "TotQualMS"],
    "Structural Risk": ["SRMSRank", "SRQualMS", "TotScrMS", "TotMSRank", "TotQualMS"],
    "Wildlife Connectivity": ["WLMSRank", "WLQualMS", "TotScrMS", "TotMSRank", "TotQualMS"],
    "Habitat Quality": ["HQGMSRank", "HQGQualMS", "TotScrMS", "TotMSRank", "TotQualMS"],
    "Environmental Quality": ["EQMSRank", "EQQualMS", "TotScrMS", "TotMSRank", "TotQualMS"],
    "Environmental Justice": ["TotScrMS", "TotMSRank", "TotQualMS"],
    "Final Results": [
        "FVMSRank", "FVQualMS", "RCMSRank", "RCQualMS", "SRMSRank", "SRQualMS",
        "WLMSRank", "WLQualMS", "HQGMSRank", "HQGQualMS", "EQMSRank", "EQQualMS",
        "TotScrMS", "TotMSRank", "RoundScoreMS", "TotQualMS",
    ],
}

SHEET_COLORS = {
    "Flood Vulnerability": "#8DD3C7",
    "Road Criticality": "#FFFFB3",
    "Structural Risk": "#FB8072",
    "Wildlife Connectivity": "#BEBADA",
    "Habitat Quality": "#80B1D3",
    "Environmental Quality": "#FDB462",
    "Environmental Justice": "#FCCDE5",
    "Final Results": "#B3DE69",
}

BETA_SHEET_COLOR = "#BFBFBF"
LOCAL_SHEET_COLOR = "#FFFFFF"

# Headers filled in the goal color on that goal's own sheet.
GOAL_HEADER_COLS = {
    "Flood Vulnerability": ["FVMSRank", "FVQualMS", "ConfFV"],
    "Road Criticality": ["RCMSRank", "RCQualMS", "ConfRC"],
    "Structural Risk": ["SRMSRank", "SRQualMS", "ConfSR"],
    "Wildlife Connectivity": ["WLMSRank", "WLQualMS", "ConfWL"],
    "Habitat Quality": ["HQGMSRank", "HQGQualMS", "ConfHQG"],
    "Environmental Quality": ["EQMSRank", "EQQualMS", "ConfEQ"],
    "Environmental Justice": ["EJ"],
}

# Headers filled in the Final Results color (italic) on every sheet.
TOTAL_HEADER_COLS = ["TotScrMS", "TotMSRank", "RoundScoreMS", "TotQualMS", "ConfTot"]

# Which parent goal colors each header block on the Final Results sheet.
FINAL_GROUP_COLS = {
    "Flood Vulnerability": ["HC_2yr", "HC_10yr", "HC_25yr", "HC_50yr", "HC_100yr",
                            "BlckFlg", "FVMSRank", "FVQualMS"],
    "Road Criticality": ["AADT", "MinDstImP", "FUNCT_SYST", "RCMSRank", "RCQualMS"],
    "Structural Risk": ["StructCond", "UsHwCon", "DsHwCon", "UsSize", "StructMat",
                        "SRMSRank", "SRQualMS"],
    "Wildlife Connectivity": ["AOP_Score", "Sp_Sp_FG", "WlCo", "WLMSRank", "WLQualMS"],
    "Habitat Quality": ["WAP_TIER", "Wetlnd", "ConsvStat", "HQGMSRank", "HQGQualMS"],
    "Environmental Quality": ["Erosion", "GC_Score", "Impair", "WImpair",
                              "EQMSRank", "EQQualMS"],
    "Environmental Justice": ["EJ"],
    "Final Results": ["CostEstimate", "ConfTot", "TotScrMS", "TotMSRank",
                      "RoundScoreMS", "TotQualMS"],
}

# Goal definitions reproduced on the Instructions sheet, carried over from the
# ARPA-phase workbook (Results-ARPA-1.7-5-30-25_PC.xlsx, Instructions sheet).
GOAL_DEFINITIONS = [
    ("Flood Vulnerability",
     "The compatibility of the stream crossing structure to accommodate the natural "
     "shape of the river and transport flood flows, as well as other evidence of flood risk."),
    ("Road Criticality",
     "The community importance of the road segment and stream crossing structure to the "
     "functional operation of the transportation system."),
    ("Structural Risk",
     "The condition of the stream crossing structure and other structural integrity "
     "factors that affect stream crossing risk and magnitude of impact."),
    ("Wildlife Connectivity",
     "The compatibility of fish and wildlife to pass through a stream crossing structure, "
     "as well as presence of special species at that structure."),
    ("Habitat Quality",
     "Characterization of the landscape adjacent to the crossing structure for greatest "
     "opportunities to restore habitat connectivity and ecosystem services within a "
     "riverine system."),
    ("Environmental Quality",
     "The existing water quality of the stream segment and whether the stream crossing "
     "structure may negatively impact water quality."),
    ("Environmental Justice",
     "This goal promotes equitable distribution of resources and benefits among communities."),
]


# --------------------------------------------------------------------------- #
# Field metadata for the header hover notes
# --------------------------------------------------------------------------- #

def load_field_metadata(path=None):
    """Load configs/metadata.csv and return {field_name: description}.

    The CSV carries Field, Goal and Description columns. The goal is folded into
    the note text so a reviewer hovering over a header sees which goal the field
    belongs to. Returns an empty dict if the file is absent, so a missing
    metadata file degrades the workbook (no hover notes) rather than breaking it.
    """
    path = Path(path) if path is not None else METADATA_PATH
    if not path.exists():
        return {}

    meta = pd.read_csv(path, dtype=str).fillna("")
    if "Field" not in meta.columns or "Description" not in meta.columns:
        return {}

    notes = {}
    for _, row in meta.iterrows():
        field = str(row["Field"]).strip()
        if not field:
            continue
        goal = str(row.get("Goal", "")).strip()
        desc = str(row["Description"]).strip()
        notes[field] = f"{field}  ({goal})\n\n{desc}" if goal else f"{field}\n\n{desc}"
    return notes


def note_for(column, notes):
    """Return the hover note for ``column``, resolving Beta_ prefixed columns
    back to their base field."""
    if column in notes:
        return notes[column]
    if column.startswith(BETA_PREFIX):
        base = column[len(BETA_PREFIX):]
        if base in notes:
            return (
                f"{column}\n\nBeta v2 baseline value of {base}, computed with the default "
                f"survey-derived weightings over the full statewide extent.\n\n{notes[base]}"
            )
    return None


# --------------------------------------------------------------------------- #
# Cost reporting
# --------------------------------------------------------------------------- #

def round_cost(series, base=10000, mode="up"):
    """Round a replacement cost Series to a reporting-level figure.

    Parameters
    ----------
    series : pd.Series
        Unrounded cost in dollars.
    base : int
        Rounding base in dollars. 10000 gives figures such as 150,000 and
        1,270,000. 5000 additionally reproduces figures such as 65,000.
    mode : {"up", "nearest"}
        "up" takes the ceiling to the next multiple of ``base``, which keeps the
        reported figure conservative for planning. "nearest" rounds to the
        closest multiple.

    Notes
    -----
    Missing values are preserved. This is a presentation transform only; the
    unrounded Cost column is retained in results_all.csv and the All Results
    sheet.
    """
    values = pd.to_numeric(series, errors="coerce")
    if base is None or base <= 0:
        return values

    if mode == "nearest":
        scaled = np.round(values / base)
    else:
        scaled = np.ceil(values / base)

    return (scaled * base).where(values.notna())
