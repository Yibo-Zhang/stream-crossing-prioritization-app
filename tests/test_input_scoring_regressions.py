"""CSV-to-score regressions: use real classifier and current project params."""
import ast
import io
import json
import sys
import subprocess
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from model import run_analysis
from utils.io_utils import load_csv
from utils.validation import (apply_null_codes, canonicalize_enum_values,
                              validate_dataset_report)

BASE = {'SADES_ID':'synthetic','HC_2yr':'Pass','HC_10yr':'Pass','HC_25yr':'Pass','HC_50yr':'Pass','HC_100yr':'Pass','BlckFlg':0,
 'UsUndermin':'None','DsUndermin':'None','UsObstruct':'None','OutScour':'None','StructSed':'Open','UsBankEros':'None','DsBankEros':'None','UsBankArmo':'Intact','DsBankArmo':'Intact','GC_Score':'Fully Compatible','Impair':0,'WWQI':0,
 'StructCond':'Poor','UsHwCon':'Good','DsHwCon':'Good','StructMat':'Concrete','UsWidth':4,'UsOpenHght':4,'StructType':'Round Culvert',
 'AADT':1000,'FUNCT_SYST':4,'Dst_Hsptl':3,'Dst_EMS':4,'Dst_LawEn':5,'Dst_Fire':6,
 'AOP_Score':'Full Passage','Sp_Sp_FG':0,'WlCo':0,'HQ_WAP':0,'WAP_TIER':0,'Wetlnd':0,'ConsvStat':0,'EJScr':0,
 'TIER':1,'ChanBFW1':10,'ChanBFW2':10,'ChanBFW3':10,'StructLen':20}

@pytest.fixture
def params():
    return json.loads((ROOT / "configs/params.json").read_text())


def test_csv_preserves_none_and_real_missing_markers():
    df = load_csv(io.StringIO("kind,OutScour\nzero,None\nblank,\nnull,NULL\nnan,NaN\nunknown,Unknown\n"))
    assert df.loc[0, "OutScour"] == "None"
    assert df.loc[1:3, "OutScour"].isna().all()
    assert df.loc[4, "OutScour"] == "Unknown"


def test_numeric_and_other_none_values_keep_previous_missing_semantics():
    text = "AADT,UsWidth,StructCond,OutScour\nNone,None,None,None\n1000,4,Good,High\n"
    previous = pd.read_csv(io.StringIO(text))
    actual = load_csv(io.StringIO(text))
    pd.testing.assert_frame_equal(actual.drop(columns="OutScour"),
                                  previous.drop(columns="OutScour"))
    assert actual.loc[0, "OutScour"] == "None"


def test_csv_roundtrip_keeps_zero_erosion_components_and_scores(params):
    expected_input = pd.DataFrame([{**BASE, "OutScour": "High"},
                                   {**BASE, "SADES_ID": "B", "StructCond": "Fair"}])
    loaded = load_csv(io.StringIO(expected_input.to_csv(index=False)))
    expected = run_analysis(expected_input.copy(), params)
    actual = run_analysis(loaded, params)
    pd.testing.assert_frame_equal(actual, expected)
    assert actual.loc[0, "ErosScr"] == pytest.approx(1 / 9)


@pytest.mark.parametrize("variant", ["poor", "POOR", " Poor ", "  pOoR  "])
def test_accepted_condition_variants_keep_full_scores_and_ranks(params, variant):
    original = pd.DataFrame([{**BASE, "SADES_ID": "A"},
                             {**BASE, "SADES_ID": "B", "StructCond": "Fair"}])
    changed = original.copy()
    changed.loc[0, "StructCond"] = variant
    report = validate_dataset_report(changed, params["validation"],
                                     params["null_values"], params["score_maps"])
    assert report.ok and not report.warnings
    expected = run_analysis(original, params)
    actual = run_analysis(changed, params)
    pd.testing.assert_frame_equal(actual, expected)
    assert actual["TotMSRank"].tolist() == [1, 2]


@pytest.mark.parametrize("variant", ["none", "NONE", " None "])
def test_accepted_zero_risk_variants_are_not_positive_or_missing(params, variant):
    original = pd.DataFrame([BASE])
    changed = original.copy()
    for field in ["UsUndermin", "DsUndermin", "OutScour", "UsBankEros", "DsBankEros"]:
        changed[field] = variant
    pd.testing.assert_frame_equal(run_analysis(changed, params),
                                  run_analysis(original, params))


def test_null_conversion_and_unknown_rejection_remain_distinct(params):
    rules = params["validation"]
    df = pd.DataFrame({"UsUndermin": ["None", " Unknown ", "unreviewed"],
                       "StructCond": ["Good", "No Score - Private", "unreviewed"]})
    assert not validate_dataset_report(df, rules, params["null_values"]).ok
    converted, _ = apply_null_codes(df, rules, params["null_values"])
    actual = canonicalize_enum_values(converted, rules)
    assert actual.loc[0, "UsUndermin"] == "None"
    assert actual.loc[1].isna().all()
    assert (actual.loc[2] == "unreviewed").all()
    assert df.loc[1, "UsUndermin"] == " Unknown "  # caller input not mutated


def test_canonicalization_respects_exact_rules_and_numeric_enums():
    rules = {"category": {"enum": ["Good"], "case_sensitive": True},
             "number": {"enum": [0, 7]}}
    df = pd.DataFrame({"category": ["good", " Good ", None],
                       "number": ["7.0", 0.0, np.nan]}, index=[3, 5, 8])
    result = canonicalize_enum_values(df, rules)
    assert result.loc[3, "category"] == "good"
    assert result.loc[5, "category"] == "Good"  # validation strips even in exact mode
    assert result.loc[3, "number"] == 7
    assert pd.isna(result.loc[8, "number"])
    pd.testing.assert_frame_equal(canonicalize_enum_values(result, rules), result)


def test_web_input_loaders_use_shared_csv_semantics():
    # Test the actual cached loader body without requiring a Streamlit server.
    module = ast.parse((ROOT / "app.py").read_text())
    loader = next(node for node in module.body
                  if isinstance(node, ast.FunctionDef) and node.name == "_load_input_cached")
    loader.decorator_list = []
    namespace = {"Path": Path, "load_csv": load_csv}
    exec(compile(ast.Module(body=[loader], type_ignores=[]), "app.py", "exec"), namespace)
    main = next(node for node in module.body
                if isinstance(node, ast.FunctionDef) and node.name == "main")
    assert any(isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
               and node.func.id == "load_csv" and node.args
               and isinstance(node.args[0], ast.Name) and node.args[0].id == "uploaded"
               for node in ast.walk(main))


def test_cached_web_loader_preserves_none(tmp_path):
    module = ast.parse((ROOT / "app.py").read_text())
    loader = next(node for node in module.body
                  if isinstance(node, ast.FunctionDef) and node.name == "_load_input_cached")
    loader.decorator_list = []
    namespace = {"Path": Path, "load_csv": load_csv}
    exec(compile(ast.Module(body=[loader], type_ignores=[]), "app.py", "exec"), namespace)
    path = tmp_path / "input.csv"
    path.write_text("OutScour\nNone\nHigh\n")
    assert namespace["_load_input_cached"]((str(path), 0, 0)).loc[0, "OutScour"] == "None"


@pytest.mark.parametrize("entrypoint", ["cli", "baseline"])
def test_real_file_entrypoints_preserve_csv_observations(tmp_path, entrypoint):
    source = tmp_path / "input.csv"
    pd.DataFrame([{**BASE, "OutScour": "High"}]).to_csv(source, index=False)
    common = ["--input", str(source), "--params", str(ROOT / "configs/params.json")]
    if entrypoint == "cli":
        output = tmp_path / "results"
        command = [sys.executable, str(ROOT / "src/model.py"), *common,
                   "--output-dir", str(output)]
        result_path = output / "results_all.csv"
    else:
        result_path = tmp_path / "baseline_all.csv.gz"
        command = [sys.executable, str(ROOT / "scripts/build_baseline.py"), *common,
                   "--output", str(result_path)]
    process = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, timeout=30)
    assert process.returncode == 0, process.stderr + process.stdout
    result = pd.read_csv(result_path)
    # CLI rounds ordinary numeric export columns to two decimals; baseline is raw.
    expected = 0.11 if entrypoint == "cli" else 1 / 9
    assert result.loc[0, "ErosScr"] == pytest.approx(expected)
