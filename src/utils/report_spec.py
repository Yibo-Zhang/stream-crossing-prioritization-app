"""Reporting specification shared by the CLI model and the Excel report builder.

Location in repo: src/utils/report_spec.py

Before UNH Beta Model v1.2 the sheet layout was declared three times: in
``src/model.py:save_results``, in ``scripts/excel_report.py`` and again in
``scripts/generate_excel_report.py``. The three copies had already drifted
(``CoverDepth`` survived in one after the criterion was removed from the model,
``WlCo`` and ``WImpair`` were never added to the workbook at all). This module
holds the layout once so the CSV outputs, the file-based workbook and the
in-memory workbook served by the Streamlit app cannot disagree.

Contents:
  MODEL_VERSION       label printed by the CLI, the app header and the workbook
  SHEET_COLUMNS       column order per sheet, model outputs only
  BASELINE_COMPARE_COLS  columns duplicated with the Base_ prefix for comparison
  USER_COLUMNS        blank columns reserved for local review
  SHEET_COLORS        tab and header fill per sheet
  load_field_metadata reads configs/metadata.csv for the header hover notes
  round_cost          reporting-level rounding of the replacement cost estimate
"""
from pathlib import Path

import numpy as np
import pandas as pd

MODEL_VERSION = "UNH Beta Model v1.2"
MODEL_VERSION_SHORT = "v1.2"
PRIOR_VERSION = "UNH Beta Model v1.1"
MODEL_TITLE = "Stream Crossing Prioritization Model"

# repo root: utils/ -> src/ -> repo root
REPO_ROOT = Path(__file__).resolve().parents[2]
METADATA_PATH = REPO_ROOT / "configs" / "metadata.csv"
BASELINE_DIR = REPO_ROOT / "data" / "baseline"
BASELINE_PATH = BASELINE_DIR / "baseline_all.csv.gz"

JOIN_KEY = "SADES_ID"

# Identification block repeated at the left of every sheet.
#   Town       emitted as its own column so a reviewer can sort, filter and
#              group at a municipal, regional or watershed scale. It is also
#              embedded in the Location label, which cannot be filtered on.
#   SurveyDate date of the SADES field assessment, placed after Landowner so
#              the currency of the underlying survey sits beside the rank.
LEAD_COLUMNS = ["SADES_ID", "Location", "Town", "Landowner", "SurveyDate"]
USER_COLUMNS = ["LocalPriority", "LocalNotes"]
BASELINE_PREFIX = "Base_"

# Frozen panes keep the identification block visible while scrolling right.
FREEZE_COLUMNS = len(LEAD_COLUMNS)

# Sort key for every sheet. v1.2 reports the mean-substituted family only.
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
        # removed from Structural Risk during scoring finalization (v1.1).
        "StructCond", "UsHwCon", "DsHwCon", "UsSize", "StructMat",
        "SRMSRank", "SRQualMS", "ConfSR",
    ] + TOTAL_BLOCK,

    "Wildlife Connectivity": LEAD_COLUMNS + [
        "AOP_Score", "Sp_Sp_FG", "WlCo",          # WlCo (terrestrial wildlife) added in v1.2
        "WLMSRank", "WLQualMS", "ConfWL",
    ] + TOTAL_BLOCK,

    "Habitat Quality": LEAD_COLUMNS + [
        "WAP_TIER", "Wetlnd", "ConsvStat",
        "HQGMSRank", "HQGQualMS", "ConfHQG",
    ] + TOTAL_BLOCK,

    "Environmental Quality": LEAD_COLUMNS + [
        "Erosion", "GC_Score", "Impair", "WImpair",   # WImpair (watershed WQ) added in v1.2
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
        "EJ", "CostEstimate", "CostBasis", "ConfTot",
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

# Columns re-read from the default-weight, full-extent baseline (the default
# UNH Beta Model v1.2 run) and appended with the Base_ prefix. Only
# model-derived results are duplicated.
# Raw field attributes (AADT, StructCond, ...) and the confidence strings are
# properties of the crossing record, not of the run, so they are identical in
# both runs and would only widen the sheet.
BASELINE_COMPARE_COLS = {
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

BASELINE_SHEET_COLOR = "#BFBFBF"
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
    "Final Results": ["CostEstimate", "CostBasis", "ConfTot", "TotScrMS",
                      "TotMSRank", "RoundScoreMS", "TotQualMS"],
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
    """Return the hover note for ``column``, resolving Base_ prefixed columns
    back to their base field."""
    if column in notes:
        return notes[column]
    if column.startswith(BASELINE_PREFIX):
        base = column[len(BASELINE_PREFIX):]
        if base in notes:
            return (
                f"{column}\n\nDefault-baseline value of {base}: the UNH Beta Model v1.2 "
                "result computed with the default survey-derived weightings over the full "
                f"statewide extent.\n\n{notes[base]}"
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


# --------------------------------------------------------------------------- #
# Instructions: header colour key
#
# Reproduced on the Instructions sheet so a reader can decode the header fills
# without opening the documentation. The three model-result fills are the ones
# a reader has to tell apart; the two input fills are included so the key
# accounts for every colour on a sheet.
# --------------------------------------------------------------------------- #

HEADER_COLOR_KEY = [
    ("Goal colour",
     None,  # resolved per sheet, this sheet's own tab colour
     "Model results for the goal this sheet covers, for example FVMSRank and "
     "FVQualMS on the Flood Vulnerability sheet. Each goal keeps the colour of "
     "its own tab."),
    ("Green",
     SHEET_COLORS["Final Results"],
     "Total Crossing Score results, shown in italics. These combine every "
     "available goal score for the crossing (TotScrMS, TotMSRank, TotQualMS, "
     "RoundScoreMS, ConfTot) and are repeated at the right-hand end of every "
     "sheet so a goal result can be read against the overall priority."),
    ("Grey",
     BASELINE_SHEET_COLOR,
     "Total Project Area score comparison. Columns prefixed Base_ hold the same "
     "result computed with the default survey-derived weightings over the full "
     "project area, so a filtered or re-weighted run can be compared against "
     "the project-wide default. Present only when the run departs from that "
     "default."),
    ("White",
     "#FFFFFF",
     "Raw input data carried from the SADES assessment or the NHDOT road "
     "inventory, unmodified, together with the identification columns."),
    ("Light grey",
     "#F2F2F2",
     "Blank columns left for local review: LocalPriority and LocalNotes."),
]

# Note attached to the CostEstimate header and repeated on the Instructions and
# Definitions sheets. Stated in one place so the three cannot drift.
COST_ESTIMATE_NOTE = (
    "Planning-level replacement cost estimate. It does not enter the priority "
    "score and does not affect any rank or priority class: it is reported "
    "beside the results as a budgeting reference only.\n\n"
    "No cost is calculated for a crossing with no bankfull width measurement "
    "(AvgBFW of zero or blank), because the required replacement width cannot "
    "be established from the survey. A blank CostEstimate therefore means "
    "\"not estimated\", never \"no cost\". The CostBasis column states the "
    "reason for each crossing.\n\n"
    "The estimate is a parametric figure from structure length, required width "
    "and a road-tier multiplier. It is not an engineer's estimate and carries "
    "none of the site-specific costs that dominate a real project, such as "
    "utility relocation, traffic management, right-of-way or permitting."
)

LOCAL_PRIORITY_NOTE = (
    "Optional local override, entered by the reviewing community, not by the "
    "model.\n\n"
    "    1  raise this crossing as a local priority\n"
    "    0  set this crossing aside, that is, deprioritise it locally\n"
    "  blank  no local position recorded\n\n"
    "The entry is recorded for local tracking and does not change TotScrMS or "
    "any rank in this workbook."
)
