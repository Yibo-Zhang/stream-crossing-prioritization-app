#!/usr/bin/env python
"""Render the Flood Vulnerability readability example for the Instructions sheet.

Location in repo: scripts/build_readability_example.py

The image embedded on the Instructions sheet is a picture of what a goal sheet
looks like, so it has to match the goal sheet. The ARPA-phase screenshot it
replaces no longer did: it showed the dynamic ranking family (FVRank, FVQual,
TotRank, TotQual) that UNH Beta Model v1.2 removed from the goal sheets, it
predated the identification block, and it predated the grey Total Project Area
comparison columns entirely.

Rendering the figure from report_spec rather than screenshotting a workbook
means the columns, their order and their header colours are read from the same
declaration the workbook is built from, so the example cannot drift from the
sheet again. Re-run after changing SHEET_COLUMNS or SHEET_COLORS:

    python scripts/build_readability_example.py

Output: docs/assets/fv_readability_example.png
"""
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "src"))

from utils import report_spec  # noqa: E402

OUTPUT_PATH = REPO_ROOT / "docs" / "assets" / "fv_readability_example.png"

SHEET = "Flood Vulnerability"
INK = (14, 34, 51)
GRID = (150, 160, 168)
CALLOUT = (20, 96, 108)
BRACE = (216, 106, 42)
WHITE = (255, 255, 255)
BODY = (40, 52, 62)

SCALE = 2  # rendered at 2x, then downsampled, to keep the small type readable

# Two illustrative rows. Values are plausible SADES records rather than real
# ones: the figure demonstrates layout and colour, and quoting real crossings
# would date the image the first time the model is re-run.
ROWS = [
    {
        "SADES_ID": "4350", "Location": "Unnamed stream at Bay Rd, Durham",
        "Town": "Durham", "Landowner": "Town", "SurveyDate": "2023-06-14",
        "HC_2yr": "Overtop", "HC_10yr": "Overtop", "HC_25yr": "Overtop",
        "HC_50yr": "Vulnerable", "HC_100yr": "Vulnerable", "BlckFlg": "Flooded",
        "FVMSRank": "1", "FVQualMS": "Very High", "ConfFV": "2 of 2",
        "TotScrMS": "0.7412", "TotMSRank": "1", "TotQualMS": "Very High",
        "ConfTot": "17 of 19",
        "Base_FVMSRank": "3", "Base_FVQualMS": "Very High",
        "Base_TotMSRank": "6", "Base_TotQualMS": "Very High",
        "LocalPriority": "1", "LocalNotes": "On the 2026 paving list",
    },
    {
        "SADES_ID": "15856", "Location": "Berrys River at Mast Rd, Lee",
        "Town": "Lee", "Landowner": "NHDOT", "SurveyDate": "2022-08-02",
        "HC_2yr": "Pass", "HC_10yr": "Vulnerable", "HC_25yr": "Vulnerable",
        "HC_50yr": "Overtop", "HC_100yr": "Overtop", "BlckFlg": "",
        "FVMSRank": "14", "FVQualMS": "High", "ConfFV": "1 of 2",
        "TotScrMS": "0.6688", "TotMSRank": "2", "TotQualMS": "Very High",
        "ConfTot": "15 of 19",
        "Base_FVMSRank": "11", "Base_FVQualMS": "High",
        "Base_TotMSRank": "2", "Base_TotQualMS": "Very High",
        "LocalPriority": "0", "LocalNotes": "Replaced 2025, re-survey due",
    },
]

# Callout brackets over the header row: (first column, last column, label).
CALLOUTS = [
    ("SADES_ID", "SurveyDate", "Identification"),
    ("HC_2yr", "BlckFlg", "Raw Goal Data (white)"),
    ("FVMSRank", "ConfFV", "Flood Vulnerability\nGoal results\n(Goal colour)"),
    ("TotScrMS", "ConfTot", "Total Crossing Score\n(green, italic)"),
    ("Base_FVMSRank", "Base_TotQualMS",
     "Total Project Area\ncomparison (grey)"),
    ("LocalPriority", "LocalNotes", "Local review\n(blank)"),
]

# Minimum body width per column. The actual width is the larger of this and the
# rendered header text, so no header is ever clipped: a truncated header defeats
# the point of a figure whose subject is the headers.
COLUMN_WIDTH = {
    "Location": 210, "LocalNotes": 170,
}
DEFAULT_WIDTH = 62


def _font(size, bold=False, italic=False):
    """Return a TrueType face, falling back to the PIL default."""
    names = []
    if bold and italic:
        names = ["DejaVuSans-BoldOblique.ttf"]
    elif bold:
        names = ["DejaVuSans-Bold.ttf"]
    elif italic:
        names = ["DejaVuSans-Oblique.ttf"]
    else:
        names = ["DejaVuSans.ttf"]
    for name in names:
        for root in ("/usr/share/fonts/truetype/dejavu/",
                     "/usr/share/fonts/truetype/", ""):
            try:
                return ImageFont.truetype(root + name, size)
            except OSError:
                continue
    return ImageFont.load_default()


def _hex_to_rgb(value):
    """Convert a '#RRGGBB' string from report_spec into a PIL RGB tuple."""
    value = value.lstrip("#")
    return tuple(int(value[i:i + 2], 16) for i in (0, 2, 4))


def sheet_columns():
    """Columns of the Flood Vulnerability sheet, in workbook order.

    Base_ comparison columns and the local review columns are appended the way
    excel_report does, so the figure shows the sheet a filtered or re-weighted
    run produces, which is the case that needs the colour key.
    """
    cols = list(report_spec.SHEET_COLUMNS[SHEET])
    cols += [report_spec.BASELINE_PREFIX + c
             for c in report_spec.BASELINE_COMPARE_COLS[SHEET]
             if c in ("FVMSRank", "FVQualMS", "TotMSRank", "TotQualMS")]
    cols += list(report_spec.USER_COLUMNS)
    return cols


def header_fill(column):
    """Header fill colour for one column, matching excel_report._write_sheet."""
    if column in report_spec.USER_COLUMNS:
        return _hex_to_rgb("#F2F2F2")
    if column.startswith(report_spec.BASELINE_PREFIX):
        return _hex_to_rgb(report_spec.BASELINE_SHEET_COLOR)
    if column in report_spec.TOTAL_HEADER_COLS:
        return _hex_to_rgb(report_spec.SHEET_COLORS["Final Results"])
    if column in report_spec.GOAL_HEADER_COLS[SHEET]:
        return _hex_to_rgb(report_spec.SHEET_COLORS[SHEET])
    return WHITE


def render():
    """Draw the figure and write it to docs/assets/fv_readability_example.png.

    Layout, top to bottom: the callout brackets naming each block of columns,
    the header row filled in the same colours excel_report applies, two
    illustrative data rows, and a caption. Rendered at SCALE times the final
    size and downsampled, because small bold text drawn directly at final size
    is not legible once embedded in the workbook.
    """
    cols = sheet_columns()

    f_head_probe = _font(14 * SCALE, bold=True)
    f_head_probe_i = _font(14 * SCALE, bold=True, italic=True)
    widths = []
    for col in cols:
        probe = (f_head_probe_i if col in report_spec.TOTAL_HEADER_COLS
                 else f_head_probe)
        header_w = probe.getlength(col) + 14 * SCALE
        widths.append(int(max(COLUMN_WIDTH.get(col, DEFAULT_WIDTH) * SCALE,
                              header_w)))
    xs, x = [], 40 * SCALE
    for w in widths:
        xs.append(x)
        x += w
    table_right = x

    callout_h = 118 * SCALE
    header_h = 34 * SCALE
    row_h = 26 * SCALE
    top = callout_h + 14 * SCALE
    height = top + header_h + row_h * len(ROWS) + 26 * SCALE
    width = table_right + 40 * SCALE

    img = Image.new("RGB", (width, height), WHITE)
    draw = ImageDraw.Draw(img)

    f_call = _font(15 * SCALE, bold=True)
    f_head = _font(14 * SCALE, bold=True)
    f_head_i = _font(14 * SCALE, bold=True, italic=True)
    f_cell = _font(13 * SCALE)

    index = {c: i for i, c in enumerate(cols)}

    # Callout brackets above the header row.
    for first, last, label in CALLOUTS:
        if first not in index or last not in index:
            continue
        x0 = xs[index[first]] + 3 * SCALE
        x1 = xs[index[last]] + widths[index[last]] - 3 * SCALE
        y = callout_h
        draw.line([(x0, y), (x1, y)], fill=BRACE, width=2 * SCALE)
        draw.line([(x0, y), (x0, y - 9 * SCALE)], fill=BRACE, width=2 * SCALE)
        draw.line([(x1, y), (x1, y - 9 * SCALE)], fill=BRACE, width=2 * SCALE)
        mid = (x0 + x1) / 2
        draw.line([(mid, y), (mid, y + 10 * SCALE)], fill=BRACE, width=2 * SCALE)
        draw.multiline_text((mid, y - 14 * SCALE), label, font=f_call,
                            fill=CALLOUT, anchor="md", align="center",
                            spacing=4 * SCALE)

    # Header row.
    y0 = top
    for i, col in enumerate(cols):
        x0, w = xs[i], widths[i]
        draw.rectangle([x0, y0, x0 + w, y0 + header_h],
                       fill=header_fill(col), outline=GRID, width=1 * SCALE)
        italic = col in report_spec.TOTAL_HEADER_COLS
        f = f_head_i if italic else f_head
        draw.text((x0 + w / 2, y0 + header_h / 2), col, font=f, fill=INK,
                  anchor="mm")

    # Data rows.
    for r, record in enumerate(ROWS):
        y = y0 + header_h + r * row_h
        for i, col in enumerate(cols):
            x0, w = xs[i], widths[i]
            draw.rectangle([x0, y, x0 + w, y + row_h], fill=WHITE,
                           outline=GRID, width=1 * SCALE)
            text = record.get(col, "")
            if not text:
                continue
            f = f_cell
            while f.getlength(text) > w - 8 * SCALE and f.size > 8 * SCALE:
                f = _font(f.size - SCALE)
            draw.text((x0 + 4 * SCALE, y + row_h / 2), text, font=f, fill=BODY,
                      anchor="lm")

    caption = ("Flood Vulnerability sheet, "
               f"{report_spec.MODEL_VERSION}. The grey Total Project Area "
               "comparison columns appear only when a run uses custom "
               "weightings or covers less than the full project area.")
    draw.text((40 * SCALE, height - 16 * SCALE), caption,
              font=_font(12 * SCALE), fill=BODY, anchor="lm")

    img = img.resize((width // SCALE, height // SCALE), Image.LANCZOS)
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    img.save(OUTPUT_PATH)
    print(f"Wrote {OUTPUT_PATH} ({img.size[0]} x {img.size[1]} px, "
          f"{len(cols)} columns)")


if __name__ == "__main__":
    render()
