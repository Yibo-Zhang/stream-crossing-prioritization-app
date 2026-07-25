#!/usr/bin/env python
"""Command line wrapper that writes the Beta v2 Excel workbook to disk.

Location in repo: scripts/generate_excel_report.py

Reads data/output/results_all.csv (the full dump written by src/model.py) and
writes data/output/report.xlsx. The workbook itself is built by
scripts/excel_report.build_excel_report, which is the same function the
Streamlit app calls, so the file-based and in-memory workbooks are identical for
identical inputs.

Before Beta v2 this script held its own copy of the sheet layout and called
jenkspy.jenks_breaks with the nb_class keyword, which raises TypeError on
jenkspy 0.3.0 and later. Both problems are removed by delegating to
excel_report.

Usage
-----
    python scripts/generate_excel_report.py
    python scripts/generate_excel_report.py --input data/output/results_all.csv \
        --output data/output/report.xlsx --baseline data/baseline/baseline_all.csv.gz
"""
import argparse
import sys
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
for extra in (REPO_ROOT / "src", REPO_ROOT / "scripts"):
    if str(extra) not in sys.path:
        sys.path.insert(0, str(extra))

from excel_report import build_excel_report      # noqa: E402
from utils import report_spec                    # noqa: E402


def parse_arguments():
    parser = argparse.ArgumentParser(
        description=f"Build the {report_spec.MODEL_VERSION} Excel report")
    parser.add_argument("--input", default=str(REPO_ROOT / "data" / "output" / "results_all.csv"),
                        help="Full results CSV written by src/model.py")
    parser.add_argument("--output", default=str(REPO_ROOT / "data" / "output" / "report.xlsx"),
                        help="Destination workbook")
    parser.add_argument("--baseline", default=None,
                        help="Optional Beta v2 baseline file. Pass 'auto' to use "
                             "data/baseline/baseline_all.csv.gz if it exists.")
    return parser.parse_args()


def main():
    args = parse_arguments()

    input_csv = Path(args.input)
    if not input_csv.exists():
        raise FileNotFoundError(f"Expected results CSV at: {input_csv}")

    df = pd.read_csv(input_csv, low_memory=False)

    baseline_df = None
    if args.baseline:
        baseline_path = (report_spec.BASELINE_PATH if args.baseline == "auto"
                         else Path(args.baseline))
        if baseline_path.exists():
            baseline_df = pd.read_csv(baseline_path, low_memory=False)
            print(f"Baseline loaded: {baseline_path} ({len(baseline_df)} records)")
        elif args.baseline != "auto":
            raise FileNotFoundError(f"Baseline file not found: {baseline_path}")
        else:
            print("No baseline file found; the workbook will omit the Beta v2 comparison.")

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(build_excel_report(df, baseline_df=baseline_df))

    print(f"{report_spec.MODEL_VERSION} report written to: {output_path}")


if __name__ == "__main__":
    main()
