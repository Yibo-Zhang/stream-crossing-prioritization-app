
# Stream Crossing Prioritization Model v1.8

A modular Python tool for analyzing and prioritizing stream crossing replacements based on multiple criteria including flood vulnerability, environmental quality, structural risk, road criticality, wildlife connectivity, habitat quality, and environmental justice.

---

## Features

- Multi-criteria analysis across 7 goals.
- Dynamic weighted scoring that adapts to missing data.
- Configurable parameters via external `params.json`.
- Input validation for enumerated fields and numeric ranges.
- CSV-based workflow for interoperability and version control.
- Optional formatted Excel report for stakeholders.
- Modular goal functions for sensitivity analysis.
- Unit tests for core utilities and goal logic.

---

## Installation

### 1. Clone / create the project

If you already created the folder manually, skip to step 2.

```bash
# Example
mkdir stream-crossing-prioritization
cd stream-crossing-prioritization
```

### 2. Create and activate a virtual environment

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

### 3. Install dependencies

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

---

## Project Structure

Your directory should look like this:

```text
stream-crossing-prioritization/
├── src/
│   ├── __init__.py
│   ├── model.py
│   ├── goals/
│   │   ├── __init__.py
│   │   ├── flood_vulnerability.py
│   │   ├── environmental_quality.py
│   │   ├── structural_risk.py
│   │   ├── road_criticality.py
│   │   ├── wildlife_connectivity.py
│   │   ├── habitat_quality.py
│   │   ├── economic_impact.py
│   │   └── environmental_justice.py
│   └── utils/
│       ├── __init__.py
│       ├── io_utils.py
│       ├── scoring_utils.py
│       └── validation.py
├── scripts/
│   └── generate_excel_report.py
├── tests/
│   ├── __init__.py
│   ├── conftest.py
│   ├── test_flood_vulnerability.py
│   ├── test_scoring_utils.py
│   └── test_validation.py
├── configs/
│   └── params.json
├── data/
│   ├── input/
│   │   └── (your_input_files.csv)
│   └── output/
│       └── (results_*.csv, report.xlsx)
├── docs/
│   └── QUICK_START.md
├── requirements.txt
├── .gitignore
├── setup.sh
├── setup.bat
└── README.md
```

---

## Preparing Input Data

1. Start from your Excel file  
   Example: `Final_Stream_CrossingV5_4-23-2025.xlsx`.

2. Open in Excel and **Save As → CSV (Comma delimited)**.

3. Move the CSV into:
   ```text
   data/input/crossings.csv
   ```

4. Ensure column names and values follow the metadata (e.g., `HC_2yr`, `StructCond`, `GC_Score`, `AOP_Score`, etc.).

---

## Running the Model

From the project root, with the virtual environment activated:

### Basic run

```bash
python src/model.py --input data/input/crossings.csv
```

This will:

- Load `configs/params.json`
- Validate the dataset (unless skipped)
- Compute all goal scores and the total prioritization score
- Save multiple CSV outputs to `data/output/`

### Command-line options

```bash
python src/model.py --help
```

Key arguments:

- `--input` (required): Path to input CSV file.
- `--output-dir`: Output directory (default: `data/output`).
- `--params`: Path to parameter JSON (default: `configs/params.json`).
- `--skip-validation`: Skip input validation checks.
- `--version`: Print model version.

Example with custom params and custom output directory:

```bash
python src/model.py \
  --input data/input/crossings.csv \
  --output-dir data/output/run_2026 \
  --params configs/params_sensitivity.json
```

---

## Outputs

After a successful run, you will find in `data/output/`:

- `results_all.csv` – all fields and scores.
- `results_flood_vulnerability.csv`
- `results_environmental_quality.csv`
- `results_structural_risk.csv`
- `results_road_criticality.csv`
- `results_wildlife_connectivity.csv`
- `results_habitat_quality.csv`
- `results_environmental_justice.csv`
- `results_final_results.csv` – compact summary per crossing.

Each file is:

- Sorted by `TotRank` (if present).
- Numeric fields rounded to 2 decimal places.

### Optional: Excel report

```bash
python scripts/generate_excel_report.py
```

Creates:

- `data/output/report.xlsx`

Content:

- One sheet per goal plus “All Results”.
- Color-coded tabs and formatted headers.
- Instructions sheet explaining layout.

---

## Configuration (params.json)

All key weights and mappings are in:

```text
configs/params.json
```

Main sections:

- `goal_weights`: Relative weight of each goal in total score.
- `criteria_weights`: Weights for criteria inside each goal.
- `score_maps`: Mappings for categorical fields (e.g., condition, material, AOP).
- `bins`: Binning definitions for AADT, size, depth of cover.
- `constants`: CPI, cost multipliers, etc.
- `validation`: Rules for enumerated values and numeric ranges.

### Example: changing goal weights

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

Save as `configs/params_custom.json` and run:

```bash
python src/model.py \
  --input data/input/crossings.csv \
  --params configs/params_custom.json \
  --output-dir data/output/custom_run
```

---

## Validation

The model can validate:

- Enumerated fields (e.g., `"Poor"`, `"Fair"`, `"Good"`).
- Numeric ranges (e.g., `AADT` must be between 0 and 100000).

If there are validation errors, the script will print them and exit. To bypass:

```bash
python src/model.py --input data/input/crossings.csv --skip-validation
```

Use this only if you know what you’re doing and have checked the data manually.

---

## Testing

Run tests from the project root:

```bash
pytest tests/ -v
```

You can also run a specific test file:

```bash
pytest tests/test_flood_vulnerability.py -v
```

---

## Code Formatting

The project is compatible with `black`:

```bash
black src/ tests/ scripts/
```

To check formatting without modifying:

```bash
black --check src/ tests/ scripts/
```

---

## Typical Workflow

1. Activate virtual environment.
2. Convert Excel to CSV in `data/input/`.
3. Run the model:
   ```bash
   python src/model.py --input data/input/crossings.csv
   ```
4. (Optional) Generate Excel report:
   ```bash
   python scripts/generate_excel_report.py
   ```
5. Open `data/output/` in Excel / QGIS / R / Python for further analysis.
6. Adjust `configs/params.json` for sensitivity runs as needed.

---

## Citation

If you use this model in publications or reports, you can cite it as:

> Asadifakhr, K., Crocker, P., Lucey, K., Bell, E., & Mo, W. (2025).  
> Stream Crossing Prioritization Model (Version 1.8). University of New Hampshire.

---

## Contact

For questions about the methodology or dataset:

- **Name:** Koorosh (Kai) Asadifakhr  
- **Email:** Koorosh.Asadifakhr@unh.edu  
- **Institution:** University of New Hampshire

