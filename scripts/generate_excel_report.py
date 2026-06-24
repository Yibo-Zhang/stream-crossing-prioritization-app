#!/usr/bin/env python


import os
import pandas as pd
import numpy as np



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

    qual = pd.cut(series, bins=breaks, labels=use_labels, include_lowest=True, duplicates='drop')
    return qual.astype("object")



def main():
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    output_dir = os.path.join(project_root, "data", "output")
    input_csv = os.path.join(output_dir, "results_all.csv")
    excel_path = os.path.join(output_dir, "report.xlsx")

    if not os.path.exists(input_csv):
        raise FileNotFoundError(f"Expected results_all.csv at: {input_csv}")

    df = pd.read_csv(input_csv, low_memory=False)

    df_all = df.copy()

    if "TotRank" in df_all.columns:
        df_all = df_all.sort_values("TotRank", ascending=True)

    for col in df_all.select_dtypes(include=np.number).columns:
        df_all[col] = df_all[col].round(2)

    # Fallback Jenks for original Qual columns
    if "FVScr" in df_all.columns and "FVQual" not in df_all.columns:
        df_all["FVQual"] = jenks_qual(df_all["FVScr"])
    if "WLScr" in df_all.columns and "WLQual" not in df_all.columns:
        df_all["WLQual"] = jenks_qual(df_all["WLScr"])
    if "HQGScr" in df_all.columns and "HQGQual" not in df_all.columns:
        df_all["HQGQual"] = jenks_qual(df_all["HQGScr"])
    if "EQScr" in df_all.columns and "EQQual" not in df_all.columns:
        df_all["EQQual"] = jenks_qual(df_all["EQScr"])
    if "RCScr" in df_all.columns and "RCQual" not in df_all.columns:
        df_all["RCQual"] = jenks_qual(df_all["RCScr"])
    if "SRScr" in df_all.columns and "SRQual" not in df_all.columns:
        df_all["SRQual"] = jenks_qual(df_all["SRScr"])
    if "TotScr" in df_all.columns and "TotQual" not in df_all.columns:
        df_all["TotQual"] = jenks_qual(df_all["TotScr"])

    # NEW: Fallback Jenks for MS Qual columns (all goals except EJ)
    if "FVScrMS" in df_all.columns and "FVQualMS" not in df_all.columns:       # NEW
        df_all["FVQualMS"] = jenks_qual(df_all["FVScrMS"])                      # NEW
    if "WLScrMS" in df_all.columns and "WLQualMS" not in df_all.columns:       # NEW
        df_all["WLQualMS"] = jenks_qual(df_all["WLScrMS"])                      # NEW
    if "HQGScrMS" in df_all.columns and "HQGQualMS" not in df_all.columns:     # NEW
        df_all["HQGQualMS"] = jenks_qual(df_all["HQGScrMS"])                    # NEW
    if "EQScrMS" in df_all.columns and "EQQualMS" not in df_all.columns:       # NEW
        df_all["EQQualMS"] = jenks_qual(df_all["EQScrMS"])                      # NEW
    if "RCScrMS" in df_all.columns and "RCQualMS" not in df_all.columns:       # NEW
        df_all["RCQualMS"] = jenks_qual(df_all["RCScrMS"])                      # NEW
    if "SRScrMS" in df_all.columns and "SRQualMS" not in df_all.columns:       # NEW
        df_all["SRQualMS"] = jenks_qual(df_all["SRScrMS"])                      # NEW
    if "TotScrMS" in df_all.columns and "TotQualMS" not in df_all.columns:     # NEW
        df_all["TotQualMS"] = jenks_qual(df_all["TotScrMS"])                    # NEW

    goal_sheets = {
        "Flood Vulnerability": [
            "SADES_ID",
            "HC_2yr", "HC_10yr", "HC_25yr", "HC_50yr", "HC_100yr", "BlckFlg",
            "FVRank", "FVQual", "FVMSRank", "FVQualMS",         # NEW: FVMSRank, FVQualMS
            "ConfFV",
            "TotRank", "TotQual", "TotMSRank", "TotQualMS",     # NEW: TotMSRank, TotQualMS
            "ConfTot",
        ],
        "Road Criticality": [
            "SADES_ID",
            "AADT", "MinDstImP", "FUNCT_SYST",
            "RCRank", "RCQual", "RCMSRank", "RCQualMS",         # NEW: RCMSRank, RCQualMS
            "ConfRC",
            "TotRank", "TotQual", "TotMSRank", "TotQualMS",     # NEW: TotMSRank, TotQualMS
            "ConfTot",
        ],
        "Structural Risk": [
            "SADES_ID",
            "StructCond", "UsHwCon", "DsHwCon", "UsSize", "CoverDepth", "StructMat",
            "SRRank", "SRQual", "SRMSRank", "SRQualMS",         # NEW: SRMSRank, SRQualMS
            "ConfSR",
            "TotRank", "TotQual", "TotMSRank", "TotQualMS",     # NEW: TotMSRank, TotQualMS
            "ConfTot",
        ],
        "Wildlife Connectivity": [
            "SADES_ID",
            "AOP_Score", "Sp_Sp_FG",
            "WLRank", "WLQual", "WLMSRank", "WLQualMS",         # NEW: WLMSRank, WLQualMS
            "ConfWL",
            "TotRank", "TotQual", "TotMSRank", "TotQualMS",     # NEW: TotMSRank, TotQualMS
            "ConfTot",
        ],
        "Habitat Quality": [
            "SADES_ID",
            "WAP_TIER", "Wetlnd", "ConsvStat",
            "HQGRank", "HQGQual", "HQGMSRank", "HQGQualMS",     # NEW: HQGMSRank, HQGQualMS
            "ConfHQG",
            "TotRank", "TotQual", "TotMSRank", "TotQualMS",     # NEW: TotMSRank, TotQualMS
            "ConfTot",
        ],
        "Environmental Quality": [
            "SADES_ID",
            "Erosion", "GC_Score", "Impair",
            "EQRank", "EQQual", "EQMSRank", "EQQualMS",         # NEW: EQMSRank, EQQualMS
            "ConfEQ",
            "TotRank", "TotQual", "TotMSRank", "TotQualMS",     # NEW: TotMSRank, TotQualMS
            "ConfTot",
        ],
        "Environmental Justice": [
            "SADES_ID",
            "EJ",
            "ConfTot",
            "TotRank", "TotQual", "TotMSRank", "TotQualMS",     # NEW: TotMSRank, TotQualMS
        ],
        "Final Results": [
            "SADES_ID",
            "HC_2yr", "HC_10yr", "HC_25yr", "HC_50yr", "HC_100yr", "BlckFlg",
            "FVRank", "FVQual", "FVMSRank", "FVQualMS",         # NEW: FVMSRank, FVQualMS
            "AADT", "MinDstImP", "FUNCT_SYST",
            "RCRank", "RCQual", "RCMSRank", "RCQualMS",         # NEW: RCMSRank, RCQualMS
            "StructCond", "UsHwCon", "DsHwCon", "UsSize", "CoverDepth", "StructMat",
            "SRRank", "SRQual", "SRMSRank", "SRQualMS",         # NEW: SRMSRank, SRQualMS
            "AOP_Score", "Sp_Sp_FG",
            "WLRank", "WLQual", "WLMSRank", "WLQualMS",         # NEW: WLMSRank, WLQualMS
            "WAP_TIER", "Wetlnd", "ConsvStat",
            "HQGRank", "HQGQual", "HQGMSRank", "HQGQualMS",     # NEW: HQGMSRank, HQGQualMS
            "Erosion", "GC_Score", "Impair",
            "EQRank", "EQQual", "EQMSRank", "EQQualMS",         # NEW: EQMSRank, EQQualMS
            "EJ", "Cost",
            "ConfTot",
            "TotRank", "TotQual",
            "TotScrMS", "TotMSRank", "RoundScoreMS", "TotQualMS",  # NEW
        ],
    }

    sheet_colors = {
        "Flood Vulnerability": "#8DD3C7",
        "Road Criticality": "#FFFFB3",
        "Structural Risk": "#FB8072",
        "Wildlife Connectivity": "#BEBADA",
        "Habitat Quality": "#80B1D3",
        "Environmental Quality": "#FDB462",
        "Environmental Justice": "#FCCDE5",
        "Final Results": "#B3DE69",
    }

    # NEW: MS rank and MS qual added to goal-specific header coloring for each goal
    goal_headers = {
        "Flood Vulnerability": ["FVRank", "FVQual", "FVMSRank", "FVQualMS", "ConfFV"],     # NEW
        "Road Criticality": ["RCRank", "RCQual", "RCMSRank", "RCQualMS", "ConfRC"],         # NEW
        "Structural Risk": ["SRRank", "SRQual", "SRMSRank", "SRQualMS", "ConfSR"],          # NEW
        "Wildlife Connectivity": ["WLRank", "WLQual", "WLMSRank", "WLQualMS", "ConfWL"],    # NEW
        "Habitat Quality": ["HQGRank", "HQGQual", "HQGMSRank", "HQGQualMS", "ConfHQG"],    # NEW
        "Environmental Quality": ["EQRank", "EQQual", "EQMSRank", "EQQualMS", "ConfEQ"],   # NEW
        "Environmental Justice": ["EJ"],
    }

    # NEW: TotMSRank and TotQualMS added to final_headers for fmt_final styling in every sheet
    final_headers = ["TotRank", "TotQual", "TotMSRank", "TotQualMS", "ConfTot"]            # NEW

    final_color = sheet_colors["Final Results"]

    with pd.ExcelWriter(excel_path, engine="xlsxwriter") as writer:
        workbook = writer.book

        instructions = pd.DataFrame(
            [
                "All results are saved in the 'All Results' sheet. "
                "Results are also categorized for each goal, and final scores are saved in 'final_results'."
            ]
        )
        instructions.to_excel(writer, index=False, sheet_name="Instructions", header=False)

        sheet_to_cols = {}
        for sheet_name, cols in goal_sheets.items():
            available = [c for c in cols if c in df_all.columns]
            sheet_to_cols[sheet_name] = available

            if not available:
                print(f"Warning: No columns found for sheet '{sheet_name}'")
                continue

            df_sheet = df_all[available].copy()

            if "TotRank" in df_sheet.columns:
                df_sheet = df_sheet.sort_values("TotRank", ascending=True)
            for c in df_sheet.select_dtypes(include=np.number).columns:
                df_sheet[c] = df_sheet[c].round(2)

            df_sheet.to_excel(writer, index=False, sheet_name=sheet_name)

        df_all.to_excel(writer, index=False, sheet_name="All Results")

        fmt_final = workbook.add_format(
            {"italic": True, "bold": True, "bg_color": final_color, "border": 1, "align": "center"}
        )

        for sheet_name, color in sheet_colors.items():
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

            for h in goal_headers.get(sheet_name, []):
                if h in cols:
                    col_idx = cols.index(h)
                    ws.write(0, col_idx, h, hdr_fmt)

            for h in final_headers:
                if h in cols:
                    col_idx = cols.index(h)
                    ws.write(0, col_idx, h, fmt_final)

        if "Final Results" in writer.sheets:
            ws_final = writer.sheets["Final Results"]

            final_group_cols = {
                "Flood Vulnerability": [
                    "HC_2yr", "HC_10yr", "HC_25yr", "HC_50yr", "HC_100yr", "BlckFlg",
                    "FVRank", "FVQual", "FVMSRank", "FVQualMS",         # NEW
                ],
                "Road Criticality": [
                    "AADT", "MinDstImP", "FUNCT_SYST",
                    "RCRank", "RCQual", "RCMSRank", "RCQualMS",         # NEW
                ],
                "Structural Risk": [
                    "StructCond", "UsHwCon", "DsHwCon", "UsSize", "CoverDepth", "StructMat",
                    "SRRank", "SRQual", "SRMSRank", "SRQualMS",         # NEW
                ],
                "Wildlife Connectivity": [
                    "AOP_Score", "Sp_Sp_FG",
                    "WLRank", "WLQual", "WLMSRank", "WLQualMS",         # NEW
                ],
                "Habitat Quality": [
                    "WAP_TIER", "Wetlnd", "ConsvStat",
                    "HQGRank", "HQGQual", "HQGMSRank", "HQGQualMS",     # NEW
                ],
                "Environmental Quality": [
                    "Erosion", "GC_Score", "Impair",
                    "EQRank", "EQQual", "EQMSRank", "EQQualMS",         # NEW
                ],
                "Environmental Justice": ["EJ"],
                "Final Results": [
                    "ConfTot",
                    "TotRank", "TotQual",
                    "TotScrMS", "TotMSRank", "RoundScoreMS", "TotQualMS",  # NEW
                ],
            }

            final_cols = sheet_to_cols.get("Final Results", [])

            for parent, cols in final_group_cols.items():
                color = sheet_colors[parent]
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

    print(f"Results successfully saved in multiple sheets.")
    print(f"Excel report written to: {excel_path}")



if __name__ == "__main__":
    main()