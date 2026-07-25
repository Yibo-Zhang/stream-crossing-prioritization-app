#!/usr/bin/env python
"""Build and store the Beta v2 baseline run.

Location in repo: scripts/build_baseline.py

The baseline is the model run with the default survey-derived weightings in
configs/params.json over the full bundled extent, data/input/crossings.csv. It
is written once and committed, so that any later run with adjusted weightings or
a reduced geographic extent can be compared against a fixed reference.

Output
------
    data/baseline/baseline_all.csv.gz     full scored dump, gzip compressed
    data/baseline/baseline_manifest.json  provenance for the stored baseline

The .csv.gz extension is deliberate. The repository .gitignore excludes *.csv,
which would otherwise swallow this file; the compressed extension is not matched
by that rule and the file is roughly a fifth of the uncompressed size.

Usage
-----
    python scripts/build_baseline.py
    python scripts/build_baseline.py --input data/input/crossings.csv --force
"""
import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
for extra in (REPO_ROOT / "src", REPO_ROOT / "scripts"):
    if str(extra) not in sys.path:
        sys.path.insert(0, str(extra))

from model import run_analysis                  # noqa: E402
from utils.io_utils import load_csv, load_params  # noqa: E402
from utils import report_spec                    # noqa: E402


def _sha256(path, chunk=1 << 20):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(chunk), b""):
            digest.update(block)
    return digest.hexdigest()


def parse_arguments():
    parser = argparse.ArgumentParser(
        description=f"Build the {report_spec.MODEL_VERSION} default-weight baseline")
    parser.add_argument("--input", default=str(REPO_ROOT / "data" / "input" / "crossings.csv"))
    parser.add_argument("--params", default=str(REPO_ROOT / "configs" / "params.json"))
    parser.add_argument("--output", default=str(report_spec.BASELINE_PATH))
    parser.add_argument("--force", action="store_true",
                        help="Overwrite an existing baseline")
    return parser.parse_args()


def main():
    args = parse_arguments()
    output_path = Path(args.output)

    if output_path.exists() and not args.force:
        raise SystemExit(
            f"Baseline already exists at {output_path}. Re-run with --force to replace it. "
            "Replacing the baseline changes every Beta_ comparison column in the workbook."
        )

    input_path = Path(args.input)
    params = load_params(args.params)
    df = load_csv(input_path)
    print(f"Baseline input: {input_path} ({len(df)} records)")

    results = run_analysis(df, params)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    results.to_csv(output_path, index=False, compression="gzip")

    manifest = {
        "model_version": report_spec.MODEL_VERSION,
        "built_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "input_file": input_path.name,
        "input_sha256": _sha256(input_path),
        "input_records": int(len(df)),
        "params_file": Path(args.params).name,
        "params_version": params.get("version", "unknown"),
        "goal_weights": params["goal_weights"],
        "criteria_weights": params["criteria_weights"],
        "output_file": output_path.name,
        "output_records": int(len(results)),
        "output_columns": int(results.shape[1]),
    }
    manifest_path = output_path.parent / "baseline_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    size_mb = output_path.stat().st_size / (1024 * 1024)
    print(f"Baseline written to: {output_path} ({size_mb:.1f} MB)")
    print(f"Manifest written to: {manifest_path}")


if __name__ == "__main__":
    main()
