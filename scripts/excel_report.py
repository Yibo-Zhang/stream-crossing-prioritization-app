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
from model import build_sheet_frame                # noqa: E402

JOIN_KEY = report_spec.JOIN_KEY
BASELINE_PREFIX = report_spec.BASELINE_PREFIX
BASELINE_SHEET_NAME = "Default Baseline (v1.2)"
ALL_SHEET_NAME = "All Results"
INSTRUCTIONS_SHEET_NAME = "Instructions"

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
    ws.freeze_panes(1, min(3, len(cols)))
    if n_rows:
        ws.autofilter(0, 0, n_rows, len(cols) - 1)

    # LocalPriority accepts 1 (or is left blank). ignore_blank keeps the column
    # usable as a free checklist without forcing an entry.
    if "LocalPriority" in cols and n_rows:
        idx = cols.index("LocalPriority")
        ws.data_validation(1, idx, n_rows, idx, {
            "validate": "list",
            "source": [1],
            "ignore_blank": True,
            "input_title": "Local priority",
            "input_message": "Enter 1 to flag this crossing as a local priority.",
        })
    return ws


def _write_instructions(workbook, baseline_used):
    """Instructions sheet, reproducing the ARPA-phase workbook layout
    (Results-ARPA-1.7-5-30-25_PC.xlsx): a very wide column A holding the project
    description, the scroll-down prompt, the how-to bullets, the Flood
    Vulnerability readability example (text plus the embedded screenshot), and
    the NHSCI Data Viewer link, with the Overarching Goal / Definition table to
    the right in columns D and E.
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
        "- Each sheet represents an Overarching Goal, as defined in the table to the right, and "
        "contains the data/model results for that corresponding goal as well as the overall, "
        "Total Crossing Scores that balance all Goals.\n"
        "- Sheets are arranged according to their importance according to the Spring 2024 UNH "
        "Crossing Survey results.\n"
        "- All results (including all Statewide Asset Database Exchange System (SADES) data and "
        "normalized model scores) are saved in the 'all_results' sheet.\n"
        "- All column headers are defined in the Data Dictionary Document.\n"
        "- Each sheet is sorted by Total Crossing Score."
    )
    ws.write(4, 0, bullets, body_fmt)
    ws.set_row(4, 120)

    # Row 5 (A6): readability example heading.
    ws.write(5, 0, "Flood Vulnerability Sheet Readability Example:", example_fmt)

    # Row 6 (A7): readability example description.
    example_desc = (
        "As detailed in the image below, each Goal sheet is comprised of the raw data (headers "
        "in white) used to calculate the Goal results, followed by the model Goal results "
        "(headers in their corresponding Goal color), and finally the Total Crossing results, "
        "which factor all available Goal scores per the model, in italics (headers in green)."
    )
    ws.write(6, 0, example_desc, body_fmt)
    ws.set_row(6, 60)

    # The readability screenshot, embedded from docs/assets. Scaled to about
    # 900 px wide so it sits within the wide column A. Falls back silently if the
    # asset is missing so the workbook still builds.
    image_bottom_row = 8
    if READABILITY_IMAGE_PATH.exists():
        from PIL import Image as _PILImage
        with _PILImage.open(READABILITY_IMAGE_PATH) as _im:
            img_w, img_h = _im.size
        target_w = 900.0
        scale = target_w / img_w
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

    # NHSCI Data Viewer link, below the image.
    link_row = image_bottom_row + 1
    ws.write_url(
        link_row, 0,
        "https://nhdes.maps.arcgis.com/apps/webappviewer/index.html?id=21173c9556be4c52bc20ea706e1c9f5a",
        link_fmt,
        string="All SADES data can be accessed and downloaded from the NHSCI Data Viewer",
    )

    # Overarching Goal / Definition table, to the right (columns D and E),
    # header on row 5 to align with the readability section, matching the ARPA
    # layout. Kept verbatim.
    ws.write(4, 2, "OVERARCHING GOAL", thead_fmt)
    ws.write(4, 3, "DEFINITION", thead_fmt)
    for i, (goal, definition) in enumerate(report_spec.GOAL_DEFINITIONS, start=5):
        ws.write(i, 2, goal, tcell_key_fmt)
        ws.write(i, 3, definition, tcell_fmt)
        ws.set_row(i, 46)

    return ws


def build_excel_report(df: pd.DataFrame, baseline_df: pd.DataFrame = None,
                       metadata_path=None) -> bytes:
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
    """
    df_all = _fill_missing_qual(df.copy())

    if report_spec.SORT_COLUMN in df_all.columns:
        df_all = df_all.sort_values(report_spec.SORT_COLUMN, ascending=True)

    notes = report_spec.load_field_metadata(metadata_path)
    baseline_used = baseline_df is not None and not baseline_df.empty

    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
        workbook = writer.book
        _write_instructions(workbook, baseline_used)

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
