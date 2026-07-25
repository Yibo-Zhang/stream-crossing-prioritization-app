#!/usr/bin/env python
"""Stream Crossing Prioritization Model, UNH Beta Model v1.2.

UNH Beta Model v1.2 is the July 2025 update of UNH Beta Model v1.1 (finalized
May 2025) per Consultant Team recommendations at the end of the ARPA phase. The
scoring logic is the v1.1 logic documented in Final_scoring_decisions.docx and
the Model Eval Memo; v1.2 changes what is reported, not how criteria are scored,
with one exception: the Habitat Quality criterion formerly called "habitat
quality" is now "Habitat Condition Tier" (short code HCT, column HCTScr). v1.2
also adds terrestrial wildlife connectivity (WlCo) and watershed water quality
impairment (WWQI).

Reporting changes in v1.2:
  - Location and Landowner labels are added after SADES_ID.
  - Goal sheets and Final Results report the mean-substituted family only
    (FVMSRank / FVQualMS / TotScrMS / TotMSRank / TotQualMS). The dynamic Rank
    and Qual columns are still computed and are kept in results_all.csv.
  - CostEstimate replaces the ARPA-phase RoundCost column.
  - LocalPriority and LocalNotes are appended for local review.
  - The sheet and CSV column layout now lives in one place,
    src/utils/report_spec.py, instead of being duplicated here and in the two
    report scripts.
"""

import argparse
import timeit
import pandas as pd
import numpy as np
import sys
from pathlib import Path

from utils.io_utils import load_csv, save_csv, load_params
from utils.validation import validate_dataset
from utils.scoring_utils import normalize_minmax, calculate_confidence, apply_jenks_classification
from utils.labels import add_labels
from utils import report_spec

from goals.flood_vulnerability import calculate_fv
from goals.environmental_quality import calculate_eq
from goals.structural_risk import calculate_sr
from goals.road_criticality import calculate_rc
from goals.wildlife_connectivity import calculate_wl
from goals.habitat_quality import calculate_hqg
from goals.economic_impact import calculate_cost
from goals.environmental_justice import calculate_ej

MODEL_VERSION = report_spec.MODEL_VERSION
MODEL_TITLE = report_spec.MODEL_TITLE


def parse_arguments():
    parser = argparse.ArgumentParser(
        description=f'{MODEL_TITLE} ({MODEL_VERSION}) analysis')
    parser.add_argument('--input', required=True, help='Path to input CSV file')
    parser.add_argument('--output-dir', default='./data/output', help='Output directory')
    parser.add_argument('--params', default='configs/params.json', help='Parameters JSON file')
    parser.add_argument('--skip-validation', action='store_true', help='Skip validation')
    parser.add_argument('--version', action='version', version=MODEL_VERSION)
    return parser.parse_args()


def calculate_total_score(df, params):
    goal_weights = params['goal_weights']

    df['SFV'] = df['FVNrm'] * goal_weights['flood_vulnerability']
    df['SEQ'] = df['EQNrm'] * goal_weights['environmental_quality']
    df['SSR'] = df['SRNrm'] * goal_weights['structural_risk']
    df['SRC'] = df['RCNrm'] * goal_weights['road_criticality']
    df['SWL'] = df['WLNrm'] * goal_weights['wildlife_connectivity']
    df['SHQG'] = df['HQGNrm'] * goal_weights['habitat_quality']
    df['SEJ'] = df['EJScr'] * goal_weights['environmental_justice']

    def calc_total(row):
        num = sum([row['SFV'] if pd.notna(row['FVNrm']) else 0, row['SEQ'] if pd.notna(row['EQNrm']) else 0,
                  row['SSR'] if pd.notna(row['SRNrm']) else 0, row['SRC'] if pd.notna(row['RCNrm']) else 0,
                  row['SWL'] if pd.notna(row['WLNrm']) else 0, row['SHQG'] if pd.notna(row['HQGNrm']) else 0,
                  row['SEJ'] if pd.notna(row['EJScr']) else 0])
        den = sum([goal_weights['flood_vulnerability'] if pd.notna(row['FVNrm']) else 0,
                  goal_weights['environmental_quality'] if pd.notna(row['EQNrm']) else 0,
                  goal_weights['structural_risk'] if pd.notna(row['SRNrm']) else 0,
                  goal_weights['road_criticality'] if pd.notna(row['RCNrm']) else 0,
                  goal_weights['wildlife_connectivity'] if pd.notna(row['WLNrm']) else 0,
                  goal_weights['habitat_quality'] if pd.notna(row['HQGNrm']) else 0,
                  goal_weights['environmental_justice'] if pd.notna(row['EJScr']) else 0])
        return num / den if den > 0 else np.nan

    df['TotScr'] = df.apply(calc_total, axis=1)
    df['TotScr'] = df['TotScr'].round(8)
    df['TotRank'] = df['TotScr'].rank(method='dense', ascending=False)
    df['RoundScore'] = df['TotScr'].round(2)

    # HCTScr replaces HQScr here (Habitat Condition Tier rename).
    total_criterion_cols = ['HCScr', 'BlkFScr', 'ErosScr', 'GCScr', 'WQIScr', 'WWQIScr',
                            'CondScr', 'SizeScr', 'MatScr',
                            'AADTScr', 'DstIMPScr', 'FncSysScr',
                            'AOPScr', 'SpSpScr', 'WlCoScr',
                            'HCTScr', 'WtlndScr', 'CnsvStScr', 'EJScr']
    present, missing, conf_str = calculate_confidence(df, total_criterion_cols)
    df['Tot_Present'], df['Tot_Missing'], df['ConfTot'] = present, missing, conf_str
    df['TotQual'] = apply_jenks_classification(df['TotScr'])
    return df


def calculate_total_score_ms(df, params):
    goal_weights = params['goal_weights']

    df['SFVMS']  = df['FVMSNrm']  * goal_weights['flood_vulnerability']
    df['SEQMS']  = df['EQMSNrm']  * goal_weights['environmental_quality']
    df['SSRMS']  = df['SRMSNrm']  * goal_weights['structural_risk']
    df['SRCMS']  = df['RCMSNrm']  * goal_weights['road_criticality']
    df['SWLMS']  = df['WLMSNrm']  * goal_weights['wildlife_connectivity']
    df['SHQGMS'] = df['HQGMSNrm'] * goal_weights['habitat_quality']
    df['SEJMS']  = df['EJScr']    * goal_weights['environmental_justice']

    def calc_total_ms(row):
        num = sum([
            row['SFVMS']  if pd.notna(row['FVMSNrm'])  else 0,
            row['SEQMS']  if pd.notna(row['EQMSNrm'])  else 0,
            row['SSRMS']  if pd.notna(row['SRMSNrm'])  else 0,
            row['SRCMS']  if pd.notna(row['RCMSNrm'])  else 0,
            row['SWLMS']  if pd.notna(row['WLMSNrm'])  else 0,
            row['SHQGMS'] if pd.notna(row['HQGMSNrm']) else 0,
            row['SEJMS']  if pd.notna(row['EJScr'])     else 0,
        ])
        den = sum([
            goal_weights['flood_vulnerability']    if pd.notna(row['FVMSNrm'])  else 0,
            goal_weights['environmental_quality']  if pd.notna(row['EQMSNrm'])  else 0,
            goal_weights['structural_risk']        if pd.notna(row['SRMSNrm'])  else 0,
            goal_weights['road_criticality']       if pd.notna(row['RCMSNrm'])  else 0,
            goal_weights['wildlife_connectivity']  if pd.notna(row['WLMSNrm'])  else 0,
            goal_weights['habitat_quality']        if pd.notna(row['HQGMSNrm']) else 0,
            goal_weights['environmental_justice']  if pd.notna(row['EJScr'])     else 0,
        ])
        return num / den if den > 0 else np.nan

    df['TotScrMS']     = df.apply(calc_total_ms, axis=1)
    df['TotScrMS']     = df['TotScrMS'].round(8)
    df['TotMSRank']    = df['TotScrMS'].rank(method='dense', ascending=False)
    df['RoundScoreMS'] = df['TotScrMS'].round(2)
    df['TotQualMS']    = apply_jenks_classification(df['TotScrMS'])
    return df


def run_analysis(df, params):
    print("\nCalculating goal scores...")
    print("  - Location and Landowner labels")
    df = add_labels(df)
    print("  - Flood Vulnerability")
    df = calculate_fv(df, params)
    print("  - Environmental Quality")
    df = calculate_eq(df, params)
    print("  - Structural Risk")
    df = calculate_sr(df, params)
    print("  - Road Criticality")
    df = calculate_rc(df, params)
    print("  - Wildlife Connectivity")
    df = calculate_wl(df, params)
    print("  - Habitat Quality")
    df = calculate_hqg(df, params)
    print("  - Economic Impact")
    df = calculate_cost(df, params)
    print("  - Environmental Justice")
    df = calculate_ej(df, params)
    print("  - Total Score")
    df = calculate_total_score(df, params)
    print("  - Total Score (Mean-Substituted)")
    df = calculate_total_score_ms(df, params)
    # Defragment after the many column insertions above.
    return df.copy()


def build_sheet_frame(df, sheet_name, add_user_columns=True):
    """Return the reporting frame for one sheet, sorted by TotMSRank.

    Used by both the CSV writer here and the Excel report builders, so a sheet
    and its matching CSV can never diverge.
    """
    cols = [c for c in report_spec.SHEET_COLUMNS[sheet_name] if c in df.columns]
    out = df[cols].copy()
    if report_spec.SORT_COLUMN in out.columns:
        out = out.sort_values(report_spec.SORT_COLUMN, ascending=True)
    if add_user_columns:
        for col in report_spec.USER_COLUMNS:
            out[col] = pd.NA
    return out


def round_for_output(frame):
    """Round numeric columns for file output.

    Two decimals as before, except the composite scores, which are kept at four
    so that TotScrMS still separates crossings that share a rounded score.
    """
    out = frame.copy()
    for col in out.select_dtypes(include=[np.number]).columns:
        out[col] = out[col].round(4 if col in report_spec.HIGH_PRECISION_COLUMNS else 2)
    return out


def save_results(df, output_dir):
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"\nSaving results to {output_dir}...")

    for sheet_name, file_stem in report_spec.CSV_OUTPUT_NAMES.items():
        df_goal = round_for_output(build_sheet_frame(df, sheet_name))
        filepath = output_dir / f'results_{file_stem}.csv'
        save_csv(df_goal, filepath)
        print(f"  [ok] {filepath.name}")

    df_all = df.copy()
    if report_spec.SORT_COLUMN in df_all.columns:
        df_all = df_all.sort_values(report_spec.SORT_COLUMN, ascending=True)
    df_all = round_for_output(df_all)
    filepath = output_dir / 'results_all.csv'
    save_csv(df_all, filepath)
    print(f"  [ok] {filepath.name}")
    print("\nAll results saved successfully.")


def main():
    start_time = timeit.default_timer()
    args = parse_arguments()

    banner = f"{MODEL_TITLE} {MODEL_VERSION}"
    print("=" * 60)
    print(banner)
    print("=" * 60)

    print(f"\nLoading parameters from: {args.params}")
    try:
        params = load_params(args.params)
        print(f"  [ok] Parameters loaded (version {params.get('version', 'unknown')})")
    except Exception as e:
        print(f"  [error] Error loading parameters: {e}")
        sys.exit(1)

    print(f"\nLoading input data from: {args.input}")
    try:
        df = load_csv(args.input)
        print(f"  [ok] Loaded {len(df)} records with {len(df.columns)} fields")
    except Exception as e:
        print(f"  [error] Error loading input data: {e}")
        sys.exit(1)

    if not args.skip_validation and 'validation' in params:
        print("\nValidating input data...")
        errors = validate_dataset(df, params['validation'])
        if errors:
            print("  [error] Validation errors found:")
            for error in errors:
                print(f"    - {error}")
            sys.exit(1)
        print("  [ok] Input data validated successfully")

    try:
        df_results = run_analysis(df, params)
    except Exception as e:
        print(f"\n[error] Error during analysis: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    try:
        save_results(df_results, args.output_dir)
    except Exception as e:
        print(f"\n[error] Error saving results: {e}")
        sys.exit(1)

    end_time = timeit.default_timer()
    runtime = end_time - start_time
    print(f"\n{'=' * 60}")
    print(f"Analysis completed in {runtime:.2f} seconds")
    print(f"{'=' * 60}\n")


if __name__ == "__main__":
    main()
