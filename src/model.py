#!/usr/bin/env python
"""Stream Crossing Prioritization Model v1.7"""

import argparse
import timeit
import pandas as pd
import numpy as np
import sys
from pathlib import Path

from utils.io_utils import load_csv, save_csv, load_params
from utils.validation import validate_dataset
from utils.scoring_utils import normalize_minmax, calculate_confidence, apply_jenks_classification

from goals.flood_vulnerability import calculate_fv
from goals.environmental_quality import calculate_eq
from goals.structural_risk import calculate_sr
from goals.road_criticality import calculate_rc
from goals.wildlife_connectivity import calculate_wl
from goals.habitat_quality import calculate_hqg
from goals.economic_impact import calculate_cost
from goals.environmental_justice import calculate_ej


def parse_arguments():
    parser = argparse.ArgumentParser(description='Stream Crossing Prioritization Analysis')
    parser.add_argument('--input', required=True, help='Path to input CSV file')
    parser.add_argument('--output-dir', default='./data/output', help='Output directory')
    parser.add_argument('--params', default='configs/params.json', help='Parameters JSON file')
    parser.add_argument('--skip-validation', action='store_true', help='Skip validation')
    parser.add_argument('--version', action='version', version='v1.7')
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
    
    total_criterion_cols = ['HCScr', 'BlkFScr', 'ErosScr', 'GCScr', 'WQIScr', 'CondScr', 'SizeScr', 'MatScr',
                           'AADTScr', 'DstIMPScr', 'FncSysScr', 'AOPScr', 'SpSpScr', 'HQScr', 'WtlndScr', 'CnsvStScr', 'EJScr']
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

    df['TotScrMS']    = df.apply(calc_total_ms, axis=1)
    df['TotScrMS']    = df['TotScrMS'].round(8)
    df['TotMSRank']   = df['TotScrMS'].rank(method='dense', ascending=False)
    df['RoundScoreMS'] = df['TotScrMS'].round(2)
    df['TotQualMS']   = apply_jenks_classification(df['TotScrMS'])
    return df

def run_analysis(df, params):
    print("\nCalculating goal scores...")
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
    print("  - Total Score (Mean-Imputed)")       # NEW
    df = calculate_total_score_ms(df, params)     # NEW
    return df


def save_results(df, output_dir):
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"\nSaving results to {output_dir}...")

    goal_columns = {
        'flood_vulnerability': [
            'SADES_ID',
            'HC_2yr', 'HC_10yr', 'HC_25yr', 'HC_50yr', 'HC_100yr', 'BlckFlg',
            'FVRank', 'FVQual', 'FVMSRank', 'FVQualMS',
            'ConfFV',
            'TotRank', 'TotQual', 'TotMSRank', 'TotQualMS',
            'ConfTot',
        ],
        'road_criticality': [
            'SADES_ID',
            'AADT', 'MinDstImP', 'FUNCT_SYST',
            'RCRank', 'RCQual', 'RCMSRank', 'RCQualMS',
            'ConfRC',
            'TotRank', 'TotQual', 'TotMSRank', 'TotQualMS',
            'ConfTot',
        ],
        'structural_risk': [
            'SADES_ID',
            'StructCond', 'UsHwCon', 'DsHwCon', 'UsSize', 'CoverDepth', 'StructMat',
            'SRRank', 'SRQual', 'SRMSRank', 'SRQualMS',
            'ConfSR',
            'TotRank', 'TotQual', 'TotMSRank', 'TotQualMS',
            'ConfTot',
        ],
        'wildlife_connectivity': [
            'SADES_ID',
            'AOP_Score', 'Sp_Sp_FG',
            'WLRank', 'WLQual', 'WLMSRank', 'WLQualMS',
            'ConfWL',
            'TotRank', 'TotQual', 'TotMSRank', 'TotQualMS',
            'ConfTot',
        ],
        'habitat_quality': [
            'SADES_ID',
            'WAP_TIER', 'Wetlnd', 'ConsvStat',
            'HQGRank', 'HQGQual', 'HQGMSRank', 'HQGQualMS',
            'ConfHQG',
            'TotRank', 'TotQual', 'TotMSRank', 'TotQualMS',
            'ConfTot',
        ],
        'environmental_quality': [
            'SADES_ID',
            'Erosion', 'GC_Score', 'Impair',
            'EQRank', 'EQQual', 'EQMSRank', 'EQQualMS',
            'ConfEQ',
            'TotRank', 'TotQual', 'TotMSRank', 'TotQualMS',
            'ConfTot',
        ],
        'environmental_justice': [
            'SADES_ID',
            'EJ',
            'ConfTot',
            'TotRank', 'TotQual', 'TotMSRank', 'TotQualMS',
        ],
        'final_results': [
            'SADES_ID',
            'HC_2yr', 'HC_10yr', 'HC_25yr', 'HC_50yr', 'HC_100yr', 'BlckFlg',
            'FVRank', 'FVQual', 'FVMSRank', 'FVQualMS',
            'AADT', 'MinDstImP', 'FUNCT_SYST',
            'RCRank', 'RCQual', 'RCMSRank', 'RCQualMS',
            'StructCond', 'UsHwCon', 'DsHwCon', 'UsSize', 'CoverDepth', 'StructMat',
            'SRRank', 'SRQual', 'SRMSRank', 'SRQualMS',
            'AOP_Score', 'Sp_Sp_FG',
            'WLRank', 'WLQual', 'WLMSRank', 'WLQualMS',
            'WAP_TIER', 'Wetlnd', 'ConsvStat',
            'HQGRank', 'HQGQual', 'HQGMSRank', 'HQGQualMS',
            'Erosion', 'GC_Score', 'Impair',
            'EQRank', 'EQQual', 'EQMSRank', 'EQQualMS',
            'EJ', 'Cost',
            'ConfTot',
            'TotRank', 'TotQual', 'TotScrMS', 'TotMSRank', 'RoundScoreMS', 'TotQualMS',
        ],
    }

    for goal_name, cols in goal_columns.items():
        available_cols = [c for c in cols if c in df.columns]
        df_goal = df[available_cols].copy()
        if 'TotRank' in df_goal.columns:
            df_goal = df_goal.sort_values('TotRank', ascending=True)
        for col in df_goal.select_dtypes(include=[np.number]).columns:
            df_goal[col] = df_goal[col].round(2)
        filepath = output_dir / f'results_{goal_name}.csv'
        save_csv(df_goal, filepath)
        print(f"  ✓ {filepath.name}")

    df_all = df.copy()
    if 'TotRank' in df_all.columns:
        df_all = df_all.sort_values('TotRank', ascending=True)
    for col in df_all.select_dtypes(include=[np.number]).columns:
        df_all[col] = df_all[col].round(2)
    filepath = output_dir / 'results_all.csv'
    save_csv(df_all, filepath)
    print(f"  ✓ {filepath.name}")
    print("\n✓ All results saved successfully!")
    

def main():
    start_time = timeit.default_timer()
    args = parse_arguments()
    
    print("="*60)
    print("Stream Crossing Prioritization Model v1.7")
    print("="*60)
    
    print(f"\nLoading parameters from: {args.params}")
    try:
        params = load_params(args.params)
        print(f"  ✓ Parameters loaded (version {params.get('version', 'unknown')})")
    except Exception as e:
        print(f"  ✗ Error loading parameters: {e}")
        sys.exit(1)
    
    print(f"\nLoading input data from: {args.input}")
    try:
        df = load_csv(args.input)
        print(f"  ✓ Loaded {len(df)} records with {len(df.columns)} fields")
    except Exception as e:
        print(f"  ✗ Error loading input data: {e}")
        sys.exit(1)
    
    if not args.skip_validation and 'validation' in params:
        print("\nValidating input data...")
        errors = validate_dataset(df, params['validation'])
        if errors:
            print("  ✗ Validation errors found:")
            for error in errors:
                print(f"    - {error}")
            sys.exit(1)
        print("  ✓ Input data validated successfully")
    
    try:
        df_results = run_analysis(df, params)
    except Exception as e:
        print(f"\n✗ Error during analysis: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    
    try:
        save_results(df_results, args.output_dir)
    except Exception as e:
        print(f"\n✗ Error saving results: {e}")
        sys.exit(1)
    
    end_time = timeit.default_timer()
    runtime = end_time - start_time
    print(f"\n{'='*60}")
    print(f"Analysis completed in {runtime:.2f} seconds")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
