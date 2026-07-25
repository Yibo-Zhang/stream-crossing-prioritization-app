# Stream Crossing Prioritization Model, UNH Beta Model v1.2

A modular Python tool for analyzing and prioritizing stream crossing replacements across seven goals: flood vulnerability, environmental quality, structural risk, road criticality, wildlife connectivity, habitat quality, and environmental justice. The project ships in two forms: a command line model that reads and writes CSV files, and a Streamlit web application that exposes the same model through an interactive interface for stakeholders.

UNH Beta Model v1.2 is the July 2025 update of UNH Beta Model v1.1 (finalized May 2025) per Consultant Team recommendations at the end of the ARPA phase. It changes what is reported rather than how criteria are scored, with one exception: the Habitat Quality criterion formerly named "habitat quality" is renamed **Habitat Condition Tier** (score column `HCTScr`). It also adds terrestrial wildlife connectivity (`WlCo`) and watershed water quality impairment (`WWQI`). See `docs/Guide-Metadata_-_v1.2.docx` for the full data dictionary and the Model Eval Memo for the scoring changes.

### Version history

- **UNH Beta Model v1.1** — the model finalized by UNH in May 2025.
- **UNH Beta Model v1.2** (this version) — the July 2025 update per Consultant Team recommendations at the end of the ARPA phase, adding terrestrial wildlife data and watershed water quality impairment data among other changes. All updates are summarized in the Model Eval Memo; future version updates through publication of the Prioritization Tool are appended to that memo.
- **Pilot Model v1.1** — not yet developed; the version to be published in the Prioritization Tool (anticipated January 2027).

---

## What changed in v1.2

- **Reporting is mean-substituted.** The Excel report and the web interface show the mean-substituted ranking family only: per goal `FVMSRank` / `FVQualMS` and similar, and for the total `TotScrMS` / `TotMSRank` / `TotQualMS`. The dynamic (non-substituted) `Rank` and `Qual` columns are still computed and are kept in `results_all.csv` and the workbook's `All Results` sheet.
- **Location and Landowner** labels are added after `SADES_ID` on every sheet, built from the input record.
- **CostEstimate** replaces the ARPA-phase `RoundCost` column. It is a planning-level replacement cost rounded to a whole reporting increment (default $10,000, rounded up) so figures read with trailing zeros, for example `150,000` or `1,270,000`. The base and direction are set in `configs/params.json` under `constants` (`cost_round_base`, `cost_round_mode`).
- **Header definitions on hover.** Every workbook header carries a cell comment taken from `configs/metadata.csv`.
- **New criteria surfaced.** Watershed water quality impairment (`WWQI`, shown as `WImpair`) and wildlife corridor (`WlCo`) now appear on the Environmental Quality and Wildlife Connectivity sheets.
- **Baseline comparison.** A fixed default baseline (default weightings, full extent) is built by `scripts/build_baseline.py` and stored at `data/baseline/baseline_all.csv.gz`. When a run departs from the default weightings or the full extent, each sheet gains `Base_` prefixed baseline columns (matched on `SADES_ID`) and a `Default Baseline (v1.2)` sheet holds the full baseline record for the crossings in that run.
- **Local review columns.** `LocalPriority` (enter `1`) and `LocalNotes` are appended to every sheet for local use; neither feeds back into the model.
- **Instructions sheet** carried over from the ARPA-phase workbook and updated for v1.2.

Reporting layout, colors, cost rounding, and the metadata loader now live in one place, `src/utils/report_spec.py`, instead of being duplicated across the model and the two report scripts.

---

## Project structure

```text
stream-crossing-app/
├── app.py                                  # Streamlit web interface (entry point)
├── requirements.txt
├── .streamlit/
│   └── config.toml
├── src/
│   ├── model.py                            # CLI entry point and run_analysis()
│   ├── goals/
│   │   ├── flood_vulnerability.py
│   │   ├── environmental_quality.py
│   │   ├── structural_risk.py
│   │   ├── road_criticality.py
│   │   ├── wildlife_connectivity.py
│   │   ├── habitat_quality.py              # Habitat Condition Tier (HCTScr)
│   │   ├── economic_impact.py              # CostEstimate
│   │   └── environmental_justice.py
│   └── utils/
│       ├── io_utils.py
│       ├── scoring_utils.py
│       ├── validation.py
│       ├── gis_utils.py
│       ├── labels.py                       # Location and Landowner labels  (NEW)
│       └── report_spec.py                  # sheet layout, colors, metadata, cost rounding  (NEW)
├── scripts/
│   ├── generate_excel_report.py            # file-based Excel report (wrapper)
│   ├── excel_report.py                     # in-memory Excel report (used by the app)
│   └── build_baseline.py                   # build the default baseline  (NEW)
├── configs/
│   ├── params.json
│   └── metadata.csv                        # workbook header definitions  (NEW)
├── data/
│   ├── input/crossings.csv                 # bundled demo dataset
│   ├── output/                             # results_*.csv, report.xlsx
│   ├── baseline/                           # baseline_all.csv.gz, baseline_manifest.json  (NEW)
│   └── gis/                                # four GeoJSON layers (see below)
├── docs/
│   └── Guide-Metadata_-_v1.2.docx          # data dictionary  (NEW)
└── README.md
```

---

## Running the command line model

```bash
python src/model.py --input data/input/crossings.csv
```

This loads `configs/params.json`, validates the dataset unless skipped, computes all goal scores, the dynamic composite (`TotScr`, `TotRank`) and the mean-substituted composite (`TotScrMS`, `TotMSRank`), and writes CSV outputs to `data/output/`.

### Building the baseline and the workbook

```bash
# Build the default baseline once (default weightings, full extent), then commit it.
python scripts/build_baseline.py

# Build report.xlsx from the latest results_all.csv.
python scripts/generate_excel_report.py

# Include the baseline comparison in the workbook:
python scripts/generate_excel_report.py --baseline auto
```

---

## Running the web application

```bash
streamlit run app.py
```

The interface presents, in order: weightings, region selection, the interactive map, the top crossings table, and the downloads. When you change any weighting or select a region, the downloadable workbook includes the `Base_` baseline comparison; a default run over the full extent omits it, since it would compare against itself.

---

## Preparing input data

1. Start from the source workbook and use **Save As, CSV (Comma delimited)**.
2. Place the CSV at `data/input/crossings.csv`.
3. Confirm that column names and values follow the model metadata, for example `HC_2yr`, `StructCond`, `GC_Score`, `AOP_Score`, `WWQI`, `WlCo`, and `SADES_ID`.

Note: the repository `.gitignore` ignores `*.csv` and `data/input/*`. The demo dataset is re-included by an explicit negation placed after those rules (`!data/input/crossings.csv`); `configs/metadata.csv` and the gzip-compressed baseline are likewise force-tracked.

---

## Preparing GIS data

The web app reads four GeoJSON layers from `data/gis/`, all in EPSG:4326, each trimmed to a single identifier column plus geometry:

| Layer file | Identifier field | Purpose |
| --- | --- | --- |
| `New_Hampshire_Political_Boundaries.geojson` | `name` | town boundaries |
| `RPC_s_Regional_Planning_Commissions.geojson` | `NAME` | RPC/county boundaries |
| `SADES_Stream_Crossings_2021.geojson` | `SADES_ID` | crossing point locations |
| `HUC12_NH_Clipped.geojson` | `HU_12_NAME` | HUC12 watersheds |

If the GeoJSON files are absent, the app still runs: region filtering and the map layer are disabled, and a notice is shown.

---

## Configuration (params.json)

- `goal_weights`: relative weight of each goal in the composite score.
- `criteria_weights`: weights for criteria inside each goal. The Habitat Quality goal (`hqg`) now uses the key `habitat_condition_tier` (the loader still accepts the legacy `habitat_quality` key).
- `score_maps`, `bins`: categorical mappings and binning for scoring.
- `constants`: `cpi`, `bankfull_multiplier`, `base_cost_per_unit`, and the v1.2 additions `cost_round_base` (default 10000) and `cost_round_mode` (`up` or `nearest`).
- `validation`: enumerated value and numeric range rules.

---

## Dependencies

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

`jenkspy>=0.3.0` is required: the classification code and the report builder call `jenks_breaks` with the `n_classes` keyword, which replaced `nb_class` at 0.3.0.

---

## Citation

> Asadifakhr, K., Crocker, P., Lucey, K., Bell, E., and Mo, W. (2026).
> Stream Crossing Prioritization Model (UNH Beta Model v1.2). University of New Hampshire.

## Contact

- **Name:** Koorosh (Kai) Asadifakhr
- **Email:** Koorosh.Asadifakhr@unh.edu
- **Institution:** University of New Hampshire
