# Stream Crossing Prioritization Model v1.8

A modular Python tool for analyzing and prioritizing stream crossing replacements across multiple criteria, including flood vulnerability, environmental quality, structural risk, road criticality, wildlife connectivity, habitat quality, and environmental justice. The project ships in two forms: a command line model that reads and writes CSV files, and a Streamlit web application that exposes the same model through an interactive interface for stakeholders.

---

## Features

- Multi criteria analysis across 7 goals.
- Dynamic weighted scoring that adapts to missing data, plus a mean imputed variant for comparison.
- Confidence reporting per crossing (criteria present out of total).
- Jenks natural breaks classification of scores into qualitative classes.
- Configurable parameters through an external `params.json`.
- Input validation for enumerated fields and numeric ranges.
- CSV based workflow for interoperability and version control.
- Formatted, color coded Excel report for stakeholders.
- Interactive web application with weight and criterion controls, region selection, an interactive map, a ranked table, and one click export.

---

## Two ways to run

1. **Command line model** (`src/model.py`): batch scoring from an input CSV to a set of output CSVs, suitable for reproducible runs and scripting.
2. **Web application** (`app.py`): a Streamlit interface intended for sharing with reviewers who do not run Python. It calls the same `run_analysis` function used by the command line model, so results are identical for identical inputs and parameters.

---

## Installation

### 1. Create the project folder

```bash
mkdir stream-crossing-app
cd stream-crossing-app
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

## Project structure

```text
stream-crossing-app/
├── app.py                                  # Streamlit web interface (entry point)
├── requirements.txt
├── .streamlit/
│   └── config.toml                         # theme for the web app
├── src/
│   ├── __init__.py
│   ├── model.py                            # CLI entry point and run_analysis()
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
│       ├── validation.py
│       └── gis_utils.py                    # boundary/HUC12/point loading, spatial filter, photo lookup
├── scripts/
│   ├── generate_excel_report.py            # file based Excel report (CLI)
│   └── excel_report.py                     # in memory Excel report (used by the web app)
├── configs/
│   └── params.json
├── data/
│   ├── input/
│   │   └── crossings.csv                   # optional demo dataset
│   ├── output/
│   │   └── (results_*.csv, report.xlsx)
│   └── gis/
│       ├── New_Hampshire_Political_Boundaries.geojson   # field "name" (towns)
│       ├── RPC_s_Regional_Planning_Commissions.geojson  # field "NAME" (RPC/county)
│       ├── SADES_Stream_Crossings_2021.geojson          # field "SADES_ID" (points)
│       └── HUC12_NH_Clipped.geojson                     # field "HU_12_NAME" (watersheds)
└── README.md
```

Note on package imports: `src/__init__.py`, `src/goals/__init__.py`, and `src/utils/__init__.py` must all exist so that `app.py` and `model.py` can resolve `from utils import ...` and `from goals import ...`. The web app adds `src/` and `scripts/` to `sys.path` at startup.

---

## Preparing input data

1. Start from your source workbook, for example `Final_Stream_CrossingV5_4-23-2025.xlsx`.
2. In Excel, use **Save As, CSV (Comma delimited)**.
3. Place the CSV at `data/input/crossings.csv`.
4. Confirm that column names and values follow the model metadata, for example `HC_2yr`, `StructCond`, `GC_Score`, `AOP_Score`, and `SADES_ID`.

---

## Preparing GIS data

The web app reads four GeoJSON layers from `data/gis/`, all in EPSG:4326 (WGS84), each trimmed to a single identifier column plus geometry to stay within the 1 GB memory ceiling of the free Streamlit tier:

| Layer file | Identifier field | Purpose |
| --- | --- | --- |
| `New_Hampshire_Political_Boundaries.geojson` | `name` | town boundaries |
| `RPC_s_Regional_Planning_Commissions.geojson` | `NAME` | RPC/county boundaries |
| `SADES_Stream_Crossings_2021.geojson` | `SADES_ID` | crossing point locations |
| `HUC12_NH_Clipped.geojson` | `HU_12_NAME` | HUC12 watersheds |

These GeoJSON files are prepared offline from the original shapefiles (reproject to EPSG:4326, keep only the identifier column plus geometry) and then copied into `data/gis/`. The one time shapefile to GeoJSON conversion utility is maintained separately and is not part of this repository.

If the GeoJSON files are absent, the app still runs: region filtering and the map layer are simply disabled, and a notice is shown.

---

## Running the command line model

From the project root, with the virtual environment activated:

```bash
python src/model.py --input data/input/crossings.csv
```

This will:

- Load `configs/params.json`.
- Validate the dataset (unless skipped).
- Compute all goal scores, the dynamic weighted composite (`TotScr`, `TotRank`), and the mean imputed composite (`TotScrMS`, `TotMSRank`).
- Save multiple CSV outputs to `data/output/`.

### Command line options

```bash
python src/model.py --help
```

Key arguments:

- `--input` (required): path to the input CSV file.
- `--output-dir`: output directory (default `data/output`).
- `--params`: path to the parameter JSON (default `configs/params.json`).
- `--skip-validation`: skip input validation checks.
- `--version`: print the model version.

Example with custom parameters and output directory:

```bash
python src/model.py \
  --input data/input/crossings.csv \
  --output-dir data/output/run_2026 \
  --params configs/params_sensitivity.json
```

---

## Running the web application

### Local

From the project root:

```bash
streamlit run app.py
```

Streamlit prints a local URL (typically `http://localhost:8501`). The interface presents, in order: weightings, region selection, the interactive map, the top crossings table, and the downloads.

Validation is off by default in the app, which matches the intent of the command line `--skip-validation` flag. Check the validation box to run the enumerated field and numeric range checks before scoring.

### Deployment on Streamlit Community Cloud

1. Push the repository to a public GitHub repository.
2. Sign in at `https://share.streamlit.io` with GitHub.
3. Create a new app, select the repository and branch, and set the entry point to `app.py`.
4. After the build completes, share the resulting `*.streamlit.app` URL with reviewers.

The free tier provides 1 GB of memory per app. Reading the pre trimmed GeoJSON layers, rather than full shapefiles, keeps the app within that ceiling. Crossing photos are streamed directly from the SADES photo service to the browser through `st.image`, so they do not accumulate in the app's own memory; the practical limits there are the Esri side attachment size cap and network latency.

---

## Outputs

After a successful command line run, `data/output/` will contain:

- `results_all.csv`, all fields and scores.
- `results_flood_vulnerability.csv`
- `results_environmental_quality.csv`
- `results_structural_risk.csv`
- `results_road_criticality.csv`
- `results_wildlife_connectivity.csv`
- `results_habitat_quality.csv`
- `results_environmental_justice.csv`
- `results_final_results.csv`, a compact summary per crossing.

Each file is sorted by `TotRank` when present, with numeric fields rounded to two decimal places.

### Excel report

From the command line:

```bash
python scripts/generate_excel_report.py
```

This reads `data/output/results_all.csv` and writes `data/output/report.xlsx` with one sheet per goal plus an "All Results" sheet, color coded tabs, and formatted headers. The web app produces the same workbook in memory through `scripts/excel_report.py` and offers it directly as a download.

---

## Configuration (params.json)

All key weights and mappings are in `configs/params.json`. Main sections:

- `goal_weights`: relative weight of each goal in the composite score.
- `criteria_weights`: weights for criteria inside each goal.
- `score_maps`: mappings for categorical fields such as condition, material, and aquatic organism passage.
- `bins`: binning definitions for AADT and structure size.
- `constants`: cost per unit, CPI, and bankfull multiplier for the economic impact calculation.
- `validation`: enumerated value and numeric range rules.

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

Save the edited file, for example as `configs/params_custom.json`, and run:

```bash
python src/model.py \
  --input data/input/crossings.csv \
  --params configs/params_custom.json \
  --output-dir data/output/custom_run
```

In the web app, the same weights and per criterion toggles are adjustable through the controls in the Weightings section, without editing the JSON.

---

## Validation

The model can validate enumerated fields (for example `StructCond` in `Poor`, `Fair`, `Good`) and numeric ranges (for example `AADT`). If validation is enabled and errors are found, the command line model prints them and exits, and the web app lists them and stops before scoring. To bypass validation from the command line:

```bash
python src/model.py --input data/input/crossings.csv --skip-validation
```

Use this only after checking the data manually.

---

## Dependencies

The application and model depend on the following packages. A pinned lower bound is given for `jenkspy` because the classification code calls `jenks_breaks` with the `n_classes` keyword, which is the current parameter name (see the note below).

```text
streamlit
streamlit-folium
folium
geopandas
shapely
pyogrio
pandas
numpy
jenkspy>=0.3.0
xlsxwriter
requests
```

### Note on jenkspy

In `jenkspy`, the `jenks_breaks` keyword was renamed from `nb_class` to `n_classes` (documented in the project's release notes, https://github.com/mthh/jenkspy/releases). Current versions expose only `n_classes`; passing `nb_class` to version 0.3.0 or later raises a `TypeError`. The scoring utilities and the report builder both use `n_classes`, so `jenkspy>=0.3.0` is required.

---

## Testing

From the project root:

```bash
pytest tests/ -v
```

Run a single test file:

```bash
pytest tests/test_flood_vulnerability.py -v
```

---

## Code formatting

The project is compatible with `black`:

```bash
black src/ tests/ scripts/ app.py
```

Check formatting without modifying:

```bash
black --check src/ tests/ scripts/ app.py
```

---

## Typical workflow

1. Activate the virtual environment.
2. Convert the source workbook to CSV in `data/input/`.
3. For a scripted run, use `python src/model.py --input data/input/crossings.csv`.
4. For an interactive session, use `streamlit run app.py`.
5. Adjust weights in `configs/params.json` or through the web controls for sensitivity runs.
6. Open the outputs in Excel, QGIS, R, or Python for further analysis.

---

## Citation

If you use this model in publications or reports, cite it as:

> Asadifakhr, K., Crocker, P., Lucey, K., Bell, E., and Mo, W. (2025).
> Stream Crossing Prioritization Model (Version 1.8). University of New Hampshire.

---

## Contact

For questions about the methodology or dataset:

- **Name:** Koorosh (Kai) Asadifakhr
- **Email:** Koorosh.Asadifakhr@unh.edu
- **Institution:** University of New Hampshire
