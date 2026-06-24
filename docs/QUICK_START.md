# Quick Start Guide

This guide shows how to go from a fresh clone/folder to running the model and getting results.

---

## 1. Setup (5–10 minutes)

From the project root (`stream-crossing-prioritization/`):

### 1.1 Create and activate a virtual environment

**Mac/Linux:**
```bash
python3 -m venv venv
source venv/bin/activate
```

**Windows (CMD/PowerShell):**
```cmd
python -m venv venv
venv\Scripts\activate
```

### 1.2 Install dependencies

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

---

## 2. Prepare Input Data (Excel → CSV)

1. Start from your Excel file  
   Example: `Final_Stream_CrossingV5_4-23-2025.xlsx`.

2. Open it in Excel.

3. Save as CSV:
   - File → Save As
   - Choose **CSV (Comma delimited)**.
   - Name it, for example: `crossings.csv`.

4. Move the CSV to:
   ```text
   data/input/crossings.csv
   ```

5. Ensure column names and values match the metadata (e.g., `HC_2yr`, `StructCond`, `GC_Score`, `AOP_Score`, etc.).

---

## 3. Run the Model

From the project root, with the virtual environment activated:

### 3.1 Basic run

```bash
python src/model.py --input data/input/crossings.csv
```

This will:

- Load `configs/params.json`.
- Validate the dataset (unless `--skip-validation` is used).
- Compute all goal scores and the total prioritization score.
- Write multiple CSV result files into `data/output/`.

### 3.2 Common options

```bash
python src/model.py --help
```

Key arguments:

- `--input` (required): Path to input CSV file.
- `--output-dir`: Output directory (default: `data/output`).
- `--params`: Path to parameter JSON (default: `configs/params.json`).
- `--skip-validation`: Skip input validation checks.
- `--version`: Print model version.

Example with custom params and output directory:

```bash
python src/model.py \
  --input data/input/crossings.csv \
  --output-dir data/output/run_2026 \
  --params configs/params_sensitivity.json
```

---

## 4. Inspect Outputs

After a successful run, check `data/output/` for:

- `results_all.csv` – complete dataset with all scores.
- `results_flood_vulnerability.csv`
- `results_environmental_quality.csv`
- `results_structural_risk.csv`
- `results_road_criticality.csv`
- `results_wildlife_connectivity.csv`
- `results_habitat_quality.csv`
- `results_environmental_justice.csv`
- `results_final_results.csv` – compact summary per crossing.

Characteristics:

- Sorted by `TotRank` when present.
- Numeric fields rounded to 2 decimal places.

Open these in Excel, LibreOffice, R, Python, or GIS software.

---

## 5. Generate Excel Report (Optional)

To create a multi-sheet, formatted Excel workbook:

```bash
python scripts/generate_excel_report.py
```

This will create:

```text
data/output/report.xlsx
```

Includes:

- One sheet per goal, plus “All Results”.
- Color-coded tabs.
- Highlighted rank/quality/confidence fields.
- Instructions sheet describing layout.

---

## 6. Modify Parameters (Sensitivity Analyses)

All configuration is in:

```text
configs/params.json
```

Key sections:

- `goal_weights`: Importance of each goal in total score.
- `criteria_weights`: Weights of criteria within each goal.
- `score_maps`: Scoring for categorical fields (e.g., condition, material, AOP).
- `bins`: Buckets for AADT, size, depth of cover.
- `constants`: CPI and cost-related constants.
- `validation`: Rules for allowed values and numeric ranges.

### Example: adjust goal weights

```json
"goal_weights": {
  "flood_vulnerability": 0.95,
  "environmental_quality": 0.75,
  "structural_risk": 0.75,
  "road_criticality": 0.70,
  "wildlife_connectivity": 0.75,
  "habitat_quality": 0.75,
  "environmental_justice": 0.50
}
```

Save as:

```text
configs/params_custom.json
```

Run:

```bash
python src/model.py \
  --input data/input/crossings.csv \
  --params configs/params_custom.json \
  --output-dir data/output/custom_run
```

---

## 7. Validation and Troubleshooting

### 7.1 Validation

The model checks:

- Enumerated fields (e.g., `StructCond` must be one of `Poor`, `Fair`, `Good`).
- Numeric ranges (e.g., `AADT` within configured limits).

If validation fails, you’ll see error messages and the script will stop.

To bypass validation (not recommended unless you understand the data):

```bash
python src/model.py --input data/input/crossings.csv --skip-validation
```

### 7.2 Common issues

- **Missing Python packages**  
  Ensure venv is activated and run:
  ```bash
  pip install -r requirements.txt
  ```

- **File not found**  
  Check that the input path is correct and relative to the project root:
  ```bash
  ls data/input/
  ```

- **Missing columns**  
  Make sure your CSV has the fields described in your metadata (`Guide-Metadata-1.7.docx`).

---

## 8. Testing (Optional)

Run unit tests:

```bash
pytest tests/ -v
```

Run a specific test file:

```bash
pytest tests/test_flood_vulnerability.py -v
```

---

## 9. Typical Workflow Summary

1. Activate virtual environment.
2. Convert Excel → CSV into `data/input/`.
3. Run:
   ```bash
   python src/model.py --input data/input/crossings.csv
   ```
4. (Optional) Generate Excel report:
   ```bash
   python scripts/generate_excel_report.py
   ```
5. Explore `data/output/` in your analysis tools.
6. Adjust `configs/params.json` for alternative scenarios and rerun.

---
