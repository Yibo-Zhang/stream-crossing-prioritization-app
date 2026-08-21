"""In-memory Excel report builder for the Stream Crossing Prioritization Model.

Location in repo: scripts/excel_report.py

Returns the formatted, multi-sheet workbook as bytes so the Streamlit app can
serve it through st.download_button without touching the filesystem.
scripts/generate_excel_report.py is a thin command line wrapper around this same
function, so the two workbooks cannot drift apart.

UNH Beta Model v1.2 workbook structure
--------------------------------------
Instructions           carried over from the ARPA-phase workbook and updated
Flood Vulnerability    one sheet per goal, ordered by the Spring 2024 survey
Road Criticality
Structural Risk
Wildlife Connectivity
Habitat Quality
Environmental Quality
Environmental Justice
Final Results          every goal block plus cost and the total score
Default Baseline (v1.2)  default-weight, full-extent baseline, restricted to the
                       crossings in this run (only when a baseline is supplied)
All Results            complete field and score dump for this run

Every sheet reports the mean-substituted ranking family only. Every header cell
carries a hover note taken from configs/metadata.csv. Every sheet ends with the
blank LocalPriority and LocalNotes columns.
"""
import math
import sys
from io import BytesIO
from pathlib import Path

import numpy as np
import pandas as pd

# Allow "python scripts/excel_report.py" and plain imports from the app, which
# already places src/ and scripts/ on sys.path.
_SRC = Path(__file__).resolve().parents[1] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from utils import report_spec                      # noqa: E402
from utils import definitions                      # noqa: E402
from utils.io_utils import load_params             # noqa: E402
from model import build_sheet_frame                # noqa: E402

JOIN_KEY = report_spec.JOIN_KEY
BASELINE_PREFIX = report_spec.BASELINE_PREFIX
BASELINE_SHEET_NAME = "Default Baseline (v1.2)"
ALL_SHEET_NAME = "All Results"
INSTRUCTIONS_SHEET_NAME = "Instructions"
DEFINITIONS_SHEET_NAME = "Definitions"
RUN_SETTINGS_SHEET_NAME = "Run Settings"

# Instructions-sheet styling and the embedded readability screenshot.
INK = "#0E2233"
READABILITY_IMAGE_PATH = (
    Path(__file__).resolve().parents[1] / "docs" / "assets" / "fv_readability_example.png"
)

# Column-level number formats. Anything not listed falls back to two decimals
# for floats and to General for text.
RANK_COLUMNS = (
    "FVMSRank", "RCMSRank", "SRMSRank", "WLMSRank", "HQGMSRank", "EQMSRank",
    "TotMSRank", "FVRank", "RCRank", "SRRank", "WLRank", "HQGRank", "EQRank", "TotRank",
)
CURRENCY_COLUMNS = ("Cost", "CostEstimate")
SCORE_COLUMNS = ("TotScrMS", "TotScr")

MAX_COLUMN_WIDTH = 46
MIN_COLUMN_WIDTH = 9


def jenks_qual(series, labels=None, n_classes=5):
    """Fallback Jenks classification, used only if a Qual column is absent from
    an older results file. jenkspy renamed nb_class to n_classes at 0.3.0."""
    import jenkspy

    if labels is None:
        labels = ["Very Low", "Low", "Moderate", "High", "Very High"]

    values = series.dropna().values
    if len(values) == 0:
        return pd.Series(index=series.index, dtype="object")

    raw_breaks = jenkspy.jenks_breaks(values, n_classes=n_classes)
    breaks = np.unique(raw_breaks)
    use_labels = labels[: len(breaks) - 1]
    qual = pd.cut(series, bins=breaks, labels=use_labels, include_lowest=True,
                  duplicates="drop")
    return qual.astype("object")


FALLBACK_PAIRS = [
    ("FVScrMS", "FVQualMS"), ("WLScrMS", "WLQualMS"), ("HQGScrMS", "HQGQualMS"),
    ("EQScrMS", "EQQualMS"), ("RCScrMS", "RCQualMS"), ("SRScrMS", "SRQualMS"),
    ("TotScrMS", "TotQualMS"),
]


def _fill_missing_qual(df):
    """Add any Qual column that is absent but whose score column is present.

    Only reached when an older results file is passed to the report builder;
    a frame straight from model.run_analysis already carries every Qual column.
    """
    for score_col, qual_col in FALLBACK_PAIRS:
        if score_col in df.columns and qual_col not in df.columns:
            df[qual_col] = jenks_qual(df[score_col])
    return df


def _attach_beta_columns(sheet_df, baseline_df, sheet_name):
    """Left-join the default baseline results onto ``sheet_df`` on SADES_ID.

    The join is done on the string form of the key so that an integer key in one
    frame and a text key in the other still match. Crossings absent from the
    baseline are left blank rather than dropped.
    """
    if baseline_df is None or JOIN_KEY not in sheet_df.columns:
        return sheet_df

    cols = [c for c in report_spec.BASELINE_COMPARE_COLS.get(sheet_name, [])
            if c in baseline_df.columns]
    if not cols:
        return sheet_df

    right = baseline_df[[JOIN_KEY] + cols].copy()
    right["_join_key"] = right[JOIN_KEY].astype(str)
    right = right.drop_duplicates(subset="_join_key").set_index("_join_key")
    right = right.drop(columns=[JOIN_KEY]).add_prefix(BASELINE_PREFIX)

    out = sheet_df.copy()
    out["_join_key"] = out[JOIN_KEY].astype(str)
    out = out.join(right, on="_join_key").drop(columns=["_join_key"])
    return out


def _column_format(workbook, column, base):
    """Return a cell format for the data body of ``column``."""
    props = dict(base)
    name = column[len(BASELINE_PREFIX):] if column.startswith(BASELINE_PREFIX) else column
    if name in CURRENCY_COLUMNS:
        props["num_format"] = "$#,##0"
    elif name in RANK_COLUMNS:
        props["num_format"] = "0"
    elif name in SCORE_COLUMNS:
        props["num_format"] = "0.0000"
    return workbook.add_format(props) if props else None


def _write_sheet(writer, workbook, sheet_name, frame, tab_color, notes,
                 goal_header_cols=None, group_colors=None):
    """Write one formatted sheet: data, header fills, hover notes, widths,
    freeze panes and autofilter."""
    frame.to_excel(writer, index=False, sheet_name=sheet_name)
    ws = writer.sheets[sheet_name]
    ws.set_tab_color(tab_color)

    cols = list(frame.columns)
    n_rows = len(frame)

    plain_hdr = workbook.add_format(
        {"bold": True, "bg_color": "#FFFFFF", "border": 1, "align": "center",
         "valign": "vcenter", "text_wrap": True})
    goal_hdr = workbook.add_format(
        {"bold": True, "bg_color": tab_color, "border": 1, "align": "center",
         "valign": "vcenter", "text_wrap": True})
    total_hdr = workbook.add_format(
        {"bold": True, "italic": True, "bg_color": report_spec.SHEET_COLORS["Final Results"],
         "border": 1, "align": "center", "valign": "vcenter", "text_wrap": True})
    beta_hdr = workbook.add_format(
        {"bold": True, "bg_color": report_spec.BASELINE_SHEET_COLOR, "border": 1,
         "align": "center", "valign": "vcenter", "text_wrap": True})
    local_hdr = workbook.add_format(
        {"bold": True, "bg_color": "#F2F2F2", "border": 1, "align": "center",
         "valign": "vcenter", "text_wrap": True})

    goal_header_cols = set(goal_header_cols or [])
    group_colors = group_colors or {}

    for idx, col in enumerate(cols):
        # Column width from the widest of header and body, within bounds.
        body = frame[col].astype(str).replace({"nan": "", "<NA>": "", "None": ""})
        max_len = body.str.len().max() if n_rows else 0
        body_len = int(max_len) if pd.notna(max_len) else 0
        width = max(MIN_COLUMN_WIDTH, min(MAX_COLUMN_WIDTH, max(len(str(col)), body_len) + 2))
        ws.set_column(idx, idx, width, _column_format(workbook, col, {}))

        # Header fill.
        if col in report_spec.USER_COLUMNS:
            fmt = local_hdr
        elif col.startswith(BASELINE_PREFIX):
            fmt = beta_hdr
        elif col in group_colors:
            fmt = group_colors[col]
        elif col in report_spec.TOTAL_HEADER_COLS:
            fmt = total_hdr
        elif col in goal_header_cols:
            fmt = goal_hdr
        else:
            fmt = plain_hdr
        ws.write(0, idx, col, fmt)

        note = report_spec.note_for(col, notes)

        # Two columns carry a standing caveat that has to appear wherever the
        # column appears, so it is appended rather than left to metadata.csv.
        base_name = (col[len(BASELINE_PREFIX):]
                     if col.startswith(BASELINE_PREFIX) else col)
        if base_name == "CostEstimate":
            note = f"{note}\n\n{report_spec.COST_ESTIMATE_NOTE}" if note else (
                f"CostEstimate\n\n{report_spec.COST_ESTIMATE_NOTE}")
        elif base_name == "LocalPriority":
            note = f"LocalPriority\n\n{report_spec.LOCAL_PRIORITY_NOTE}"

        if note is None and col not in report_spec.USER_COLUMNS:
            # Raw SADES / road-inventory fields carried into the full dump are not
            # individually defined in metadata.csv. Give them a generic, accurate
            # note rather than inventing a specific meaning for each.
            note = (
                f"{col}\n\nRaw field carried through from the input dataset "
                "(SADES assessment or NHDOT road inventory) without modification. "
                "Not used directly in scoring."
            )
        if note:
            ws.write_comment(0, idx, note,
                             {"width": 320, "height": 190, "author": report_spec.MODEL_VERSION})

    ws.set_row(0, 32)
    ws.freeze_panes(1, min(report_spec.FREEZE_COLUMNS, len(cols)))
    if n_rows:
        ws.autofilter(0, 0, n_rows, len(cols) - 1)

    # LocalPriority accepts 1, 0, or a blank. 0 lets a community record a
    # deliberate decision to set a crossing aside, which a blank cannot express:
    # a blank is indistinguishable from a crossing nobody has looked at yet.
    if "LocalPriority" in cols and n_rows:
        idx = cols.index("LocalPriority")
        ws.data_validation(1, idx, n_rows, idx, {
            "validate": "list",
            "source": [1, 0],
            "ignore_blank": True,
            "input_title": "Local priority",
            "input_message": ("1 = local priority.\n"
                              "0 = deprioritised locally.\n"
                              "Blank = no local position recorded.\n"
                              "Does not change the model score or rank."),
        })
    return ws


def _write_instructions(workbook, baseline_used):
    """Instructions sheet, reproducing the ARPA-phase workbook layout
    (Results-ARPA-1.7-5-30-25_PC.xlsx): a very wide column A holding the project
    description, the scroll-down prompt, the how-to bullets, the Flood
    Vulnerability readability example (text plus the embedded screenshot), and
    the NHSCI Data Viewer link. The Overarching Goal / Definition table that the
    ARPA layout placed to the right of the figure has moved to the Definitions
    sheet.
    """
    ws = workbook.add_worksheet(INSTRUCTIONS_SHEET_NAME)
    ws.set_tab_color("#0E2233")
    ws.hide_gridlines(2)
    # Print nicely: landscape, fit all columns onto one page width.
    ws.set_landscape()
    ws.fit_to_pages(1, 0)
    ws.set_margins(0.4, 0.4, 0.4, 0.4)

    title_fmt = workbook.add_format(
        {"bold": True, "font_size": 15, "font_color": INK, "text_wrap": True, "valign": "top"})
    body_fmt = workbook.add_format(
        {"text_wrap": True, "valign": "top", "font_size": 11})
    call_fmt = workbook.add_format(
        {"bold": True, "font_color": "#14606C", "font_size": 12})
    example_fmt = workbook.add_format(
        {"bold": True, "font_size": 12, "font_color": INK, "valign": "top"})
    link_fmt = workbook.add_format(
        {"font_color": "#1155CC", "underline": 1, "font_size": 11, "valign": "top"})
    thead_fmt = workbook.add_format(
        {"bold": True, "bg_color": "#D8E0E0", "border": 1, "align": "center",
         "valign": "vcenter", "text_wrap": True})
    tcell_key_fmt = workbook.add_format(
        {"bold": True, "text_wrap": True, "valign": "top", "border": 1})
    tcell_fmt = workbook.add_format(
        {"text_wrap": True, "valign": "top", "border": 1})

    # Column A deliberately very wide; the description and bullets live here.
    ws.set_column(0, 0, 150)
    ws.set_column(1, 1, 2)      # thin spacer
    ws.set_column(2, 2, 26)     # OVERARCHING GOAL
    ws.set_column(3, 3, 74)     # DEFINITION

    # Row 0 (A1): title line then the full project description, one cell.
    title_line = "ARPA-Phase Beta Crossing Prioritization Model Final Prioritized List"
    description = (
        "This workbook displays the results of the 2022-2025 New Hampshire Stream Crossing "
        "Replacement Prioritization Project. Funded through the American Rescue Plan Act (ARPA) "
        "as well as NH Sea Grant and in collaboration with New Hampshire Department of "
        "Environmental Services (NHDES), the New Hampshire Stream Crossing Initiative (NHSCI) "
        "and University of New Hampshire (UNH), this project developed a stakeholder-informed "
        "prioritization model for stream crossing replacements in the Merrimack and "
        "Piscataqua-Salmon Falls HUC 8 Watersheds utilizing data collected using the NHSCI "
        "Stream Crossing Protocol to identify multi-benefit crossing replacement projects that "
        "balance road safety, ecosystem restoration, flood vulnerability, wildlife passage, etc. "
        "These results will be refined from 2025-2027 with a grant provided to NHDES by the "
        "National Fish and Wildlife Foundation."
    )
    ws.write_rich_string(
        0, 0,
        title_fmt, title_line + "\n\n",
        body_fmt, description,
        title_fmt,  # cell format (wrap, top)
    )
    ws.set_row(0, 168)

    # Row 2 (A3): scroll-down prompt.
    ws.write(2, 0, "SCROLL DOWN FOR INSTRUCTIONS ON HOW TO UTILIZE THIS WORKBOOK", call_fmt)

    # Row 4 (A5): how-to bullets (tall). Verbatim wording from the ARPA workbook.
    bullets = (
        "- Each sheet represents an Overarching Goal, as defined on the Definitions sheet, and "
        "contains the data/model results for that corresponding goal as well as the overall, "
        "Total Crossing Scores that balance all Goals.\n"
        "- Sheets are arranged according to their importance according to the Spring 2024 UNH "
        "Crossing Survey results.\n"
        "- All results (including all Statewide Asset Database Exchange System (SADES) data and "
        "normalized model scores) are saved in the 'all_results' sheet.\n"
        "- Every column header carries a hover note; the Definitions sheet gives "
        "the fuller explanation, including what each attribute value means and "
        "the Goal and Criterion weights used.\n"
        "- The Run Settings sheet records the weights and the geographic extent "
        "this particular run used, so a result can always be traced to what it "
        "is a result of.\n"
        "- Each sheet opens with the same identification block: SADES_ID, "
        "Location, Town, Landowner and SurveyDate. Town is given as its own "
        "column so results can be sorted and filtered at a municipal, regional "
        "or watershed scale.\n"
        "- Cost Estimate is a planning-level figure only. It does not enter the "
        "priority score, and no cost is calculated for a crossing with no "
        "bankfull width measurement.\n"
        "- LocalPriority and LocalNotes are blank for local review: enter 1 to "
        "raise a crossing locally, 0 to set it aside, or leave it blank.\n"
        "- Each sheet is sorted by Total Crossing Score."
    )
    ws.write(4, 0, bullets, body_fmt)
    ws.set_row(4, 210)

    # Row 5 (A6): readability example heading.
    ws.write(5, 0, "Flood Vulnerability Sheet Readability Example:", example_fmt)

    # Row 6 (A7): readability example description.
    example_desc = (
        "As shown in the image below, each Goal sheet opens with the identification block and "
        "the raw data used to calculate that Goal (headers in white), followed by the model "
        "results for the Goal itself (headers in that Goal's own colour), then the Total "
        "Crossing results, which combine every available Goal score, in italics (headers in "
        "green). Where a run departs from the default weightings or covers less than the full "
        "project area, a further block compares it against the Total Project Area result "
        "(headers in grey, columns prefixed Base_). The key below lists every header colour."
    )
    ws.write(6, 0, example_desc, body_fmt)
    ws.set_row(6, 74)

    # The readability figure, embedded from docs/assets.
    #
    # Scaled to a target height rather than a fixed width. The v1.2 sheet has 24
    # columns against the 13 in the ARPA-phase screenshot, so scaling both to the
    # same width would render the v1.2 header text at about 35 per cent of native
    # against 60 per cent for the original, which is not legible once embedded.
    # Targeting the height the original occupied keeps the text the same size on
    # screen and lets the figure take the width it needs.
    #
    # Falls back silently if the asset is missing so the workbook still builds.
    image_bottom_row = 8
    if READABILITY_IMAGE_PATH.exists():
        from PIL import Image as _PILImage
        with _PILImage.open(READABILITY_IMAGE_PATH) as _im:
            img_w, img_h = _im.size
        # 226 px is the height the ARPA screenshot occupied at its 900 px width.
        target_h = 226.0
        scale = min(target_h / img_h, 1.0)
        ws.insert_image(
            8, 0, str(READABILITY_IMAGE_PATH),
            {"x_scale": scale, "y_scale": scale, "x_offset": 4, "y_offset": 6,
             "object_position": 1},
        )
        # Estimate how many default-height rows the scaled image spans so the
        # link below does not overlap it (about 20 px per row).
        rows_spanned = int((img_h * scale + 12) / 20) + 1
        image_bottom_row = 8 + rows_spanned
    else:
        ws.write(8, 0,
                 "[Flood Vulnerability readability example image not found: "
                 "docs/assets/fv_readability_example.png]", body_fmt)
        image_bottom_row = 10

    # Header colour key, below the image. Each row is filled in the colour it
    # names, so the key is read the same way the sheets are.
    key_row = image_bottom_row + 1
    ws.write(key_row, 0, "Header Colour Key:", example_fmt)
    ws.write(key_row, 2, "COLOUR", thead_fmt)
    ws.write(key_row, 3, "WHAT THE HEADER MARKS", thead_fmt)

    for offset, (label, color, meaning) in enumerate(
            report_spec.HEADER_COLOR_KEY, start=1):
        row = key_row + offset
        swatch_color = color or report_spec.SHEET_COLORS["Flood Vulnerability"]
        swatch = workbook.add_format(
            {"bold": True, "bg_color": swatch_color, "border": 1,
             "align": "center", "valign": "vcenter", "text_wrap": True,
             "italic": label == "Green"})
        shown = (label if color is not None
                 else f"{label} (example: Flood Vulnerability)")
        ws.write(row, 2, shown, swatch)
        ws.write(row, 3, meaning, tcell_fmt)
        ws.set_row(row, 58)

    # A goal keeps its own colour; list them so the first key row is concrete.
    goal_row = key_row + len(report_spec.HEADER_COLOR_KEY) + 1
    ws.write(goal_row, 2, "Goal colours", tcell_key_fmt)
    ws.write(goal_row, 3,
             "Flood Vulnerability, Road Criticality, Structural Risk, Wildlife "
             "Connectivity, Habitat Quality, Environmental Quality and "
             "Environmental Justice each use the colour of their own sheet tab.",
             tcell_fmt)
    ws.set_row(goal_row, 46)

    # NHSCI Data Viewer link, below the colour key.
    link_row = goal_row + 2
    ws.write_url(
        link_row, 0,
        "https://nhdes.maps.arcgis.com/apps/webappviewer/index.html?id=21173c9556be4c52bc20ea706e1c9f5a",
        link_fmt,
        string="All SADES data can be accessed and downloaded from the NHSCI Data Viewer",
    )

    # The Overarching Goal / Definition table that the ARPA layout carried on
    # this sheet now lives on the Definitions sheet, where a goal's definition
    # sits directly above the criteria that make it up.

    return ws




def _definitions_formats(workbook):
    """Shared cell formats for the Definitions and Run Settings sheets."""
    return {
        "title": workbook.add_format(
            {"bold": True, "font_size": 15, "font_color": INK,
             "text_wrap": True, "valign": "top"}),
        "section": workbook.add_format(
            {"bold": True, "font_size": 12, "font_color": INK,
             "valign": "top", "bottom": 2, "bottom_color": INK}),
        "body": workbook.add_format(
            {"text_wrap": True, "valign": "top", "font_size": 11}),
        "thead": workbook.add_format(
            {"bold": True, "bg_color": "#D8E0E0", "border": 1,
             "align": "center", "valign": "vcenter", "text_wrap": True}),
        "key": workbook.add_format(
            {"bold": True, "text_wrap": True, "valign": "top", "border": 1}),
        "cell": workbook.add_format(
            {"text_wrap": True, "valign": "top", "border": 1}),
        "num": workbook.add_format(
            {"num_format": "0.000", "valign": "top", "border": 1,
             "align": "center"}),
        "int": workbook.add_format(
            {"num_format": "0", "valign": "top", "border": 1,
             "align": "center"}),
        "mono": workbook.add_format(
            {"font_name": "Consolas", "text_wrap": True, "valign": "top",
             "border": 1, "font_size": 10}),
    }


def _write_table(ws, row, headers, rows, fmts, widths=None, key_first=True):
    """Write one bordered table and return the next free row."""
    for col, header in enumerate(headers):
        ws.write(row, col, header, fmts["thead"])
    row += 1
    for record in rows:
        for col, value in enumerate(record):
            if value is None:
                ws.write_blank(row, col, None, fmts["cell"])
            elif isinstance(value, float):
                ws.write_number(row, col, value, fmts["num"])
            elif isinstance(value, int) and not isinstance(value, bool):
                ws.write_number(row, col, value, fmts["int"])
            else:
                fmt = fmts["key"] if (key_first and col == 0) else fmts["cell"]
                ws.write(row, col, value, fmt)
        row += 1
    return row + 1


def _write_definitions(workbook):
    """Definitions sheet: what each Goal and Criterion measures.

    Two tables. The first is the Overarching Goal / Definition table, moved here
    from the Instructions sheet so that a goal's definition sits directly above
    the criteria that make it up rather than on another sheet. The second sets
    out, for every criterion, the score column it writes, the input fields it
    reads, how those inputs become a 0 to 1 score, and what leaves it missing.

    Weights are deliberately not repeated here. They are user-selectable, so a
    weight printed on a static reference sheet would describe a default rather
    than the run in hand. The Run Settings sheet carries the weights actually
    used, each beside its survey default.
    """
    ws = workbook.add_worksheet(DEFINITIONS_SHEET_NAME)
    ws.set_tab_color("#14606C")
    ws.hide_gridlines(2)
    ws.set_landscape()
    ws.fit_to_pages(1, 0)

    fmts = _definitions_formats(workbook)
    ws.set_column(0, 0, 26)     # Goal
    ws.set_column(1, 1, 32)     # Criterion
    ws.set_column(2, 2, 16)     # Score column
    ws.set_column(3, 3, 40)     # Source field(s)
    ws.set_column(4, 4, 72)     # How it is derived
    ws.set_column(5, 5, 56)     # When it is missing

    row = 0
    ws.write(row, 0, f"Definitions, {report_spec.MODEL_VERSION}", fmts["title"])
    row += 2

    ws.merge_range(
        row, 0, row, 5,
        "Each sheet in this workbook covers one Overarching Goal. A Goal is made "
        "up of Criteria, and each Criterion is scored 0 to 1, where 1 is the "
        "highest replacement priority. A Criterion with no data for a crossing "
        "drops out of that crossing's score rather than being scored zero, "
        "which is what the confidence columns count. The weights used to combine "
        "Criteria and Goals are recorded on the Run Settings sheet.",
        fmts["body"])
    ws.set_row(row, 62)
    row += 2

    # ---- Overarching Goals ------------------------------------------------ #
    ws.write(row, 0, "Overarching Goals", fmts["section"])
    row += 2

    ws.write(row, 0, "OVERARCHING GOAL", fmts["thead"])
    ws.merge_range(row, 1, row, 5, "DEFINITION", fmts["thead"])
    row += 1
    for goal, definition in report_spec.GOAL_DEFINITIONS:
        ws.write(row, 0, goal, fmts["key"])
        ws.merge_range(row, 1, row, 5, definition, fmts["cell"])
        ws.set_row(row, 46)
        row += 1
    row += 1

    # ---- Criteria --------------------------------------------------------- #
    ws.write(row, 0, "Criteria", fmts["section"])
    row += 2
    row = _write_table(
        ws, row,
        ["Goal", "Criterion", "Score column", "Source field(s)",
         "How it is derived", "When it is missing"],
        [(spec["goal"], spec["name"], spec["score_col"], spec["source"],
          spec["derivation"], spec["missing"])
         for spec in definitions.CRITERIA],
        fmts)

    return ws


def _write_run_settings(workbook, run_context, params, baseline_used):
    """Run Settings sheet: the weights and extent this run actually used.

    Two runs of this model over the same crossings can produce different ranks,
    because the weights and the geographic extent are both user-selectable and
    both change the result. Jenks classes and min-max normalisation are computed
    across the crossings in the run, so restricting the extent changes the
    priority classes even when no weight is touched. Recording the settings
    beside the results is what makes a saved workbook interpretable later.
    """
    ws = workbook.add_worksheet(RUN_SETTINGS_SHEET_NAME)
    ws.set_tab_color("#5A6B75")
    ws.hide_gridlines(2)
    ws.set_landscape()
    ws.fit_to_pages(1, 0)

    fmts = _definitions_formats(workbook)
    ws.set_column(0, 0, 34)
    ws.set_column(1, 1, 34)
    ws.set_column(2, 2, 18)
    ws.set_column(3, 3, 18)
    ws.set_column(4, 4, 46)

    context = dict(run_context or {})

    row = 0
    ws.write(row, 0, f"Run Settings, {report_spec.MODEL_VERSION}", fmts["title"])
    row += 2
    ws.write(row, 0,
             "These are the settings this workbook was produced with. Both the "
             "weights and the extent change the result: priority classes and "
             "normalised scores are computed across the crossings included in "
             "the run, so the same crossing can fall in a different class "
             "statewide than it does within one town.",
             fmts["body"])
    ws.set_row(row, 44)
    row += 2

    # ---- Extent ----------------------------------------------------------- #
    ws.write(row, 0, "Geographic extent", fmts["section"])
    row += 2
    extent_rows = [
        ("Selection method", context.get("region_method_label", "All crossings")),
        ("Selected area", context.get("region_value") or "Full project area"),
        ("Crossings scored", context.get("crossings_scored")),
        ("Crossings in source file", context.get("crossings_available")),
        ("Input dataset", context.get("input_label", "not recorded")),
        ("Run date", context.get("run_timestamp", "not recorded")),
        ("Model version", report_spec.MODEL_VERSION),
        ("Weight scale used", context.get("weight_scale", "not recorded")),
        ("Total Project Area comparison",
         "Included: Base_ columns compare this run against the default "
         "weightings over the full project area"
         if baseline_used else
         "Not included: this run already uses the default weightings over the "
         "full project area, so the comparison would repeat the run"),
    ]
    row = _write_table(ws, row, ["Setting", "Value"], extent_rows, fmts)

    # ---- Weights ---------------------------------------------------------- #
    ws.write(row, 0, "Goal weights used in this run", fmts["section"])
    row += 2
    scale_max = context.get("weight_scale_max")
    defaults = context.get("default_goal_weights") or {}
    goal_rows = []
    for label, goal_key, _ in definitions.GOALS:
        used = params.get("goal_weights", {}).get(goal_key)
        default = defaults.get(goal_key)
        goal_rows.append((
            label,
            None if used is None else float(used),
            None if default is None else float(default),
            _weight_status(used, default, scale_max),
        ))
    row = _write_table(
        ws, row, ["Goal", "Weight used", "Survey default", "Status"],
        goal_rows, fmts)

    ws.write(row, 0, "Criterion weights used in this run", fmts["section"])
    row += 2
    default_criteria = context.get("default_criteria_weights") or {}
    criteria_key_for = {label: ck for label, _, ck in definitions.GOALS}
    crit_rows = []
    for spec in definitions.CRITERIA:
        ck = criteria_key_for.get(spec["goal"])
        if not ck or not spec["weight_key"]:
            continue
        used = params.get("criteria_weights", {}).get(ck, {}).get(spec["weight_key"])
        default = default_criteria.get(ck, {}).get(spec["weight_key"])
        crit_rows.append((
            spec["goal"], spec["name"],
            None if used is None else float(used),
            None if default is None else float(default),
            _weight_status(used, default, scale_max),
        ))
    row = _write_table(
        ws, row,
        ["Goal", "Criterion", "Weight used", "Survey default", "Status"],
        crit_rows, fmts)

    warnings = context.get("validation_warnings") or []
    if warnings:
        ws.write(row, 0, "Validation warnings", fmts["section"])
        row += 2
        row = _write_table(ws, row, ["Warning"],
                           [(message,) for message in warnings], fmts)

    return ws


def _weight_status(used, default, scale_max=None):
    """Describe how a weight used in the run compares with the survey default.

    The app sets weights with whole-number sliders, so a slider left where the
    interface put it does not carry the raw params.json weight: it carries that
    weight snapped to the nearest step. On the 0 to 4 scale, a survey default of
    0.875 shows as a slider at 4 and reaches the model as 1.00. Comparing the
    used weight against the raw default would report that untouched slider as
    "changed for this run", which is the opposite of what happened.

    The comparison is therefore made against the snapped default when the run
    came from the app and the scale is known, and against the raw default
    otherwise, which is right for a command line run that has no sliders.
    """
    if used is None or default is None:
        return "not recorded"
    used, default = float(used), float(default)

    if used == 0 and default != 0:
        return "turned off for this run"
    if abs(used - default) <= 1e-9:
        return "survey default"

    if scale_max:
        # Half away from zero, matching app.to_display_units.
        steps = math.floor(default * scale_max + 0.5)
        steps = min(max(steps, 0), scale_max)
        snapped = steps / float(scale_max)
        if abs(used - snapped) <= 1e-9:
            return "survey default, rounded to slider scale"

    return "changed for this run"


def build_excel_report(df: pd.DataFrame, baseline_df: pd.DataFrame = None,
                       metadata_path=None, params: dict = None,
                       run_context: dict = None) -> bytes:
    """Build the UNH Beta Model v1.2 workbook in memory and return it as bytes.

    Parameters
    ----------
    df : pd.DataFrame
        Scored results for this run, as returned by model.run_analysis.
    baseline_df : pd.DataFrame, optional
        Default baseline results (default weightings, full extent), as written by
        scripts/build_baseline.py. When supplied, Base_ comparison columns are
        appended to every sheet and a Default Baseline sheet is added holding the
        baseline record for the crossings present in ``df``. Pass None for a
        default run, where the comparison would be a copy of the run itself.
    metadata_path : str or Path, optional
        Override for configs/metadata.csv.
    params : dict, optional
        The parameter dict this run used. Supplies the weights printed on the
        Run Settings sheet, so that sheet describes the run rather than the
        committed defaults. Falls back to configs/params.json when omitted,
        which is correct for a default run.
    run_context : dict, optional
        Describes the run for the Run Settings sheet. Recognised keys:
        region_method_label, region_value, crossings_scored,
        crossings_available, input_label, run_timestamp, weight_scale,
        weight_scale_max, default_goal_weights, default_criteria_weights,
        validation_warnings. Any key omitted is reported as "not recorded"
        rather than guessed at.
    """
    df_all = _fill_missing_qual(df.copy())

    if report_spec.SORT_COLUMN in df_all.columns:
        df_all = df_all.sort_values(report_spec.SORT_COLUMN, ascending=True)

    notes = report_spec.load_field_metadata(metadata_path)
    baseline_used = baseline_df is not None and not baseline_df.empty

    if params is None:
        try:
            params = load_params(report_spec.REPO_ROOT / "configs" / "params.json")
        except Exception:
            # A missing or unreadable params file costs the workbook its
            # Definitions and Run Settings numbers, not the workbook itself.
            params = {}

    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
        workbook = writer.book
        _write_instructions(workbook, baseline_used)
        _write_definitions(workbook)
        _write_run_settings(workbook, run_context, params, baseline_used)

        final_group_formats = {}
        for parent, cols in report_spec.FINAL_GROUP_COLS.items():
            fmt = workbook.add_format({
                "bold": True, "bg_color": report_spec.SHEET_COLORS[parent],
                "border": 1, "align": "center", "valign": "vcenter", "text_wrap": True,
                "italic": parent == "Final Results",
            })
            for col in cols:
                final_group_formats[col] = fmt

        for sheet_name in report_spec.SHEET_COLUMNS:
            frame = build_sheet_frame(df_all, sheet_name, add_user_columns=False)
            if frame.empty and not len(frame.columns):
                continue
            if baseline_used:
                frame = _attach_beta_columns(frame, baseline_df, sheet_name)
            for col in report_spec.USER_COLUMNS:
                frame[col] = pd.NA

            _write_sheet(
                writer, workbook, sheet_name, frame,
                report_spec.SHEET_COLORS[sheet_name], notes,
                goal_header_cols=report_spec.GOAL_HEADER_COLS.get(sheet_name, []),
                group_colors=final_group_formats if sheet_name == "Final Results" else None,
            )

        if baseline_used and JOIN_KEY in df_all.columns:
            keys = set(df_all[JOIN_KEY].astype(str))
            beta_frame = baseline_df[baseline_df[JOIN_KEY].astype(str).isin(keys)].copy()
            if report_spec.SORT_COLUMN in beta_frame.columns:
                beta_frame = beta_frame.sort_values(report_spec.SORT_COLUMN, ascending=True)
            _write_sheet(writer, workbook, BASELINE_SHEET_NAME, beta_frame,
                         report_spec.BASELINE_SHEET_COLOR, notes)

        _write_sheet(writer, workbook, ALL_SHEET_NAME, df_all, "#5A6B75", notes)

    buffer.seek(0)
    return buffer.getvalue()
