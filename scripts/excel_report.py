
"""In-memory Excel report builder, adapted from scripts/generate_excel_report.py."""
from io import BytesIO

import numpy as np
import pandas as pd


def jenks_qual(series, labels=None, n_classes=5):
    """Classify a numeric series into Jenks natural breaks with qualitative labels."""
    import jenkspy

    if labels is None:
        labels = ["Very Low", "Low", "Moderate", "High", "Very High"]

    values = series.dropna().values
    if len(values) == 0:
        return pd.Series(index=series.index, dtype="object")

    raw_breaks = jenkspy.jenks_breaks(values, nb_class=n_classes)
    breaks = np.unique(raw_breaks)
    n_intervals = len(breaks) - 1
    use_labels = labels[:n_intervals]

    qual = pd.cut(series, bins=breaks, labels=use_labels, include_lowest=True, duplicates="drop")
    return qual.astype("object")


GOAL_SHEETS = {
    "Flood Vulnerability": [
        "SADES_ID", "HC_2yr", "HC_10yr", "HC_25yr", "HC_50yr", "HC_100yr", "BlckFlg",
        "FVRank", "FVQual", "FVMSRank", "FVQualMS", "ConfFV",
        "TotRank", "TotQual", "TotMSRank", "TotQualMS", "ConfTot",
    ],
    "Road Criticality": [
        "SADES_ID", "AADT", "MinDstImP", "FUNCT_SYST",
        "RCRank", "RCQual", "RCMSRank", "RCQualMS", "ConfRC",
        "TotRank", "TotQual", "TotMSRank", "TotQualMS", "ConfTot",
    ],
    "Structural Risk": [
        "SADES_ID", "StructCond", "UsHwCon", "DsHwCon", "UsSize", "StructMat",
        "SRRank", "SRQual", "SRMSRank", "SRQualMS", "ConfSR",
        "TotRank", "TotQual", "TotMSRank", "TotQualMS", "ConfTot",
    ],
    "Wildlife Connectivity": [
        "SADES_ID", "AOP_Score", "Sp_Sp_FG",
        "WLRank", "WLQual", "WLMSRank", "WLQualMS", "ConfWL",
        "TotRank", "TotQual", "TotMSRank", "TotQualMS", "ConfTot",
    ],
    "Habitat Quality": [
        "SADES_ID", "WAP_TIER", "Wetlnd", "ConsvStat",
        "HQGRank", "HQGQual", "HQGMSRank", "HQGQualMS", "ConfHQG",
        "TotRank", "TotQual", "TotMSRank", "TotQualMS", "ConfTot",
    ],
    "Environmental Quality": [
        "SADES_ID", "Erosion", "GC_Score", "Impair",
        "EQRank", "EQQual", "EQMSRank", "EQQualMS", "ConfEQ",
        "TotRank", "TotQual", "TotMSRank", "TotQualMS", "ConfTot",
    ],
    "Environmental Justice": [
        "SADES_ID", "EJ", "ConfTot",
        "TotRank", "TotQual", "TotMSRank", "TotQualMS",
    ],
    "Final Results": [
        "SADES_ID",
        "HC_2yr", "HC_10yr", "HC_25yr", "HC_50yr", "HC_100yr", "BlckFlg",
        "FVRank", "FVQual", "FVMSRank", "FVQualMS",
        "AADT", "MinDstImP", "FUNCT_SYST",
        "RCRank", "RCQual", "RCMSRank", "RCQualMS",
        "StructCond", "UsHwCon", "DsHwCon", "UsSize", "StructMat",
        "SRRank", "SRQual", "SRMSRank", "SRQualMS",
        "AOP_Score", "Sp_Sp_FG",
        "WLRank", "WLQual", "WLMSRank", "WLQualMS",
        "WAP_TIER", "Wetlnd", "ConsvStat",
        "HQGRank", "HQGQual", "HQGMSRank", "HQGQualMS",
        "Erosion", "GC_Score", "Impair",
        "EQRank", "EQQual", "EQMSRank", "EQQualMS",
        "EJ", "Cost", "ConfTot",
        "TotRank", "TotQual",
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

GOAL_HEADERS = {
    "Flood Vulnerability": ["FVRank", "FVQual", "FVMSRank", "FVQualMS", "ConfFV"],
    "Road Criticality": ["RCRank", "RCQual", "RCMSRank", "RCQualMS", "ConfRC"],
    "Structural Risk": ["SRRank", "SRQual", "SRMSRank", "SRQualMS", "ConfSR"],
    "Wildlife Connectivity": ["WLRank", "WLQual", "WLMSRank", "WLQualMS", "ConfWL"],
    "Habitat Quality": ["HQGRank", "HQGQual", "HQGMSRank", "HQGQualMS", "ConfHQG"],
    "Environmental Quality": ["EQRank", "EQQual", "EQMSRank", "EQQualMS", "ConfEQ"],
    "Environmental Justice": ["EJ"],
}

FINAL_HEADERS = ["TotRank", "TotQual", "TotMSRank", "TotQualMS", "ConfTot"]

FINAL_GROUP_COLS = {
    "Flood Vulnerability": ["HC_2yr", "HC_10yr", "HC_25yr", "HC_50yr", "HC_100yr", "BlckFlg",
                             "FVRank", "FVQual", "FVMSRank", "FVQualMS"],
    "Road Criticality": ["AADT", "MinDstImP", "FUNCT_SYST", "RCRank", "RCQual", "RCMSRank", "RCQualMS"],
    "Structural Risk": ["StructCond", "UsHwCon", "DsHwCon", "UsSize", "StructMat",
                         "SRRank", "SRQual", "SRMSRank", "SRQualMS"],
    "Wildlife Connectivity": ["AOP_Score", "Sp_Sp_FG", "WLRank", "WLQual", "WLMSRank", "WLQualMS"],
    "Habitat Quality": ["WAP_TIER", "Wetlnd", "ConsvStat", "HQGRank", "HQGQual", "HQGMSRank", "HQGQualMS"],
    "Environmental Quality": ["Erosion", "GC_Score", "Impair", "EQRank", "EQQual", "EQMSRank", "EQQualMS"],
    "Environmental Justice": ["EJ"],
    "Final Results": ["ConfTot", "TotRank", "TotQual", "TotScrMS", "TotMSRank", "RoundScoreMS", "TotQualMS"],
}


def build_excel_report(df: pd.DataFrame) -> bytes:
    """Build the formatted, multi-sheet Excel report in memory and return it as bytes.

    Mirrors scripts/generate_excel_report.py but writes to a BytesIO buffer
    instead of a file on disk, so it can be served directly via
    st.download_button without touching the filesystem.
    """
    df_all = df.copy()

    if "TotRank" in df_all.columns:
        df_all = df_all.sort_values("TotRank", ascending=True)

    for col in df_all.select_dtypes(include=np.number).columns:
        df_all[col] = df_all[col].round(2)

    fallback_pairs = [
        ("FVScr", "FVQual"), ("WLScr", "WLQual"), ("HQGScr", "HQGQual"),
        ("EQScr", "EQQual"), ("RCScr", "RCQual"), ("SRScr", "SRQual"),
        ("TotScr", "TotQual"),
        ("FVScrMS", "FVQualMS"), ("WLScrMS", "WLQualMS"), ("HQGScrMS", "HQGQualMS"),
        ("EQScrMS", "EQQualMS"), ("RCScrMS", "RCQualMS"), ("SRScrMS", "SRQualMS"),
        ("TotScrMS", "TotQualMS"),
    ]
    for score_col, qual_col in fallback_pairs:
        if score_col in df_all.columns and qual_col not in df_all.columns:
            df_all[qual_col] = jenks_qual(df_all[score_col])

    buffer = BytesIO()

    with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
        workbook = writer.book

        instructions = pd.DataFrame(
            [
                "All results are saved in the 'All Results' sheet. "
                "Results are also categorized for each goal, and final scores are saved in 'Final Results'."
            ]
        )
        instructions.to_excel(writer, index=False, sheet_name="Instructions", header=False)

        sheet_to_cols = {}
        for sheet_name, cols in GOAL_SHEETS.items():
            available = [c for c in cols if c in df_all.columns]
            sheet_to_cols[sheet_name] = available
            if not available:
                continue

            df_sheet = df_all[available].copy()
            if "TotRank" in df_sheet.columns:
                df_sheet = df_sheet.sort_values("TotRank", ascending=True)
            for c in df_sheet.select_dtypes(include=np.number).columns:
                df_sheet[c] = df_sheet[c].round(2)

            df_sheet.to_excel(writer, index=False, sheet_name=sheet_name)

        df_all.to_excel(writer, index=False, sheet_name="All Results")

        final_color = SHEET_COLORS["Final Results"]
        fmt_final = workbook.add_format(
            {"italic": True, "bold": True, "bg_color": final_color, "border": 1, "align": "center"}
        )

        for sheet_name, color in SHEET_COLORS.items():
            if sheet_name not in writer.sheets:
                continue

            ws = writer.sheets[sheet_name]
            ws.set_tab_color(color)

            hdr_fmt = workbook.add_format(
                {"bold": True, "bg_color": color, "border": 1, "align": "center"}
            )

            cols = sheet_to_cols.get(sheet_name, [])
            if not cols:
                continue

            df_sheet = df_all[cols]

            for idx, col in enumerate(cols):
                max_len = df_sheet[col].astype(str).fillna("").map(len).max()
                header_len = len(col)
                width = max(header_len, max_len) + 1
                ws.set_column(idx, idx, width)

            for h in GOAL_HEADERS.get(sheet_name, []):
                if h in cols:
                    col_idx = cols.index(h)
                    ws.write(0, col_idx, h, hdr_fmt)

            for h in FINAL_HEADERS:
                if h in cols:
                    col_idx = cols.index(h)
                    ws.write(0, col_idx, h, fmt_final)

        if "Final Results" in writer.sheets:
            ws_final = writer.sheets["Final Results"]
            final_cols = sheet_to_cols.get("Final Results", [])

            for parent, cols in FINAL_GROUP_COLS.items():
                color = SHEET_COLORS[parent]
                fmt = workbook.add_format(
                    {"bold": True, "bg_color": color, "border": 1, "align": "center"}
                )
                for h in cols:
                    if h in final_cols:
                        col_idx = final_cols.index(h)
                        ws_final.write(0, col_idx, h, fmt)

        if "All Results" in writer.sheets:
            ws_all = writer.sheets["All Results"]
            for idx, col in enumerate(df_all.columns):
                max_len = df_all[col].astype(str).fillna("").map(len).max()
                header_len = len(col)
                width = max(header_len, max_len) + 1
                ws_all.set_column(idx, idx, width)

    buffer.seek(0)
    return buffer.getvalue()
