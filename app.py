"""Streamlit interface for the Stream Crossing Prioritization Model (v1.8).

Performance model (Option B):
  - Weight controls live in a fragment: moving a slider reruns only that block,
    not the map or results.
  - The map is display only (no polygon draw), renders only after a run
    completes, shows only the crossings included in that run, and renders all
    such points as a single GeoJSON layer, which is far faster than one
    folium marker per crossing.
  - The Run Analysis button appears before the map in the page layout; the
    map section only calls st_folium once "result_df" exists in
    st.session_state.
  - The results block (table, photos, downloads) is a separate fragment, so the
    table-size slider and photo switcher do not rebuild the map.
Requires Streamlit 1.37 or newer for st.fragment.
"""

import sys
import json
import copy
from pathlib import Path

import streamlit as st
import pandas as pd
import numpy as np

sys.path.insert(0, str(Path(__file__).parent / "src"))
sys.path.insert(0, str(Path(__file__).parent / "scripts"))

from model import run_analysis  # noqa: E402
from utils.validation import validate_dataset  # noqa: E402
from utils import gis_utils  # noqa: E402  (src/utils/gis_utils.py)
from excel_report import build_excel_report  # noqa: E402  (scripts/excel_report.py)

st.set_page_config(
    page_title="Stream Crossing Prioritization Model",
    page_icon="\U0001F30A",
    layout="wide",
)

DEFAULT_PARAMS_PATH = Path(__file__).parent / "configs" / "params.json"
DEFAULT_INPUT_PATH = Path(__file__).parent / "data" / "input" / "crossings.csv"

GOAL_LABELS = {
    "flood_vulnerability": "Flood Vulnerability",
    "environmental_quality": "Environmental Quality",
    "structural_risk": "Structural Risk",
    "road_criticality": "Road Criticality",
    "wildlife_connectivity": "Wildlife Connectivity",
    "habitat_quality": "Habitat Quality",
    "environmental_justice": "Environmental Justice",
}

GOAL_TO_CRITERIA_KEY = {
    "flood_vulnerability": "fv",
    "environmental_quality": "eq",
    "structural_risk": "sr",
    "road_criticality": "rc",
    "wildlife_connectivity": "wl",
    "habitat_quality": "hqg",
}

GOAL_QUAL_COL = {
    "flood_vulnerability": "FVQual",
    "environmental_quality": "EQQual",
    "structural_risk": "SRQual",
    "road_criticality": "RCQual",
    "wildlife_connectivity": "WLQual",
    "habitat_quality": "HQGQual",
    "environmental_justice": None,  # EJ has no dedicated Qual column in model.py
}

CRITERIA_LABELS = {
    "fv": {"hydraulic_capacity": "Hydraulic Capacity", "flooding_history": "Flooding History"},
    "eq": {"erosion": "Erosion", "geomorphic_compatibility": "Geomorphic Compatibility", "water_quality": "Water Quality"},
    "sr": {"condition": "Condition", "size": "Size", "material": "Material"},
    "rc": {"aadt": "AADT", "distance_to_services": "Distance to Services", "functional_classification": "Functional Classification"},
    "wl": {"aop": "Aquatic Organism Passage", "special_species": "Special Species", "terrestrial_organism_passage": "Terrestrial Organism Passage"},
    "hqg": {"habitat_quality": "Habitat Quality", "wetland_proximity": "Wetland Proximity", "conservation_status": "Conservation Status"},
}

JENKS_ORDER = {"Very High": 4, "High": 3, "Moderate": 2, "Low": 1, "Very Low": 0}

QUAL_COLORS = {
    "Very High": ("#d73027", "#ffffff"),
    "High": ("#fc8d59", "#3a1705"),
    "Moderate": ("#fee08b", "#4a3b00"),
    "Low": ("#91cf60", "#123a08"),
    "Very Low": ("#1a9850", "#ffffff"),
}

# Region selection: label shown to the user -> internal method key.
REGION_METHODS = {
    "All crossings": "all",
    "Town": "town",
    "County / RPC": "county",
    "HUC12 Watershed": "huc12",
}


def fragment_decorator(func):
    """Apply st.fragment (or the older experimental alias) if available.
    Falls back to a no-op so the app still runs on older Streamlit."""
    frag = getattr(st, "fragment", None) or getattr(st, "experimental_fragment", None)
    return frag(func) if frag is not None else func


# --------------------------------------------------------------------------- #
# Presentation
# --------------------------------------------------------------------------- #

CUSTOM_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@500;600;700&family=IBM+Plex+Sans:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500&display=swap');

:root {
    --ink: #0E2233; --current: #1F8A9B; --current-deep: #14606C;
    --granite: #5A6B75; --line: #D8E0E0; --sediment: #F4F6F5; --panel: #FFFFFF;
}

.stApp { background: var(--sediment); }
html, body, .stApp { font-family: 'IBM Plex Sans', system-ui, -apple-system, sans-serif; }
h1, h2, h3, h4 { font-family: 'Space Grotesk', sans-serif; color: var(--ink); }

/* Keep Streamlit's Material icon font intact (fixes expander arrows showing as
   the literal text 'keyboard_arrow_right'). */
[data-testid="stIconMaterial"], span[data-testid="stIconMaterial"],
.material-symbols-rounded, .material-symbols-outlined, i.material-icons {
    font-family: 'Material Symbols Rounded', 'Material Symbols Outlined', 'Material Icons' !important;
    font-feature-settings: 'liga' !important;
}

.block-container { max-width: 1180px; padding-top: 1.2rem; }

.sc-hero {
    position: relative;
    background: linear-gradient(160deg, #0E2233 0%, #123449 60%, #14606C 100%);
    border-radius: 14px; padding: 30px 34px 28px 34px; margin-bottom: 26px; overflow: hidden;
}
.sc-hero::before {
    content: ""; position: absolute; top: 0; left: 0; right: 0; height: 4px;
    background: linear-gradient(90deg, #1F8A9B 0%, #6FC3C9 45%, transparent 100%);
}
.sc-hero-eyebrow {
    font-family: 'IBM Plex Mono', monospace; font-size: 12px; letter-spacing: 0.14em;
    text-transform: uppercase; color: #8FD0D6; margin-bottom: 12px;
}
.sc-hero-title { color: #F4F6F5; font-size: 2.35rem; font-weight: 700; line-height: 1.05; margin: 0 0 10px 0; }
.sc-hero-sub { color: #C4D2D8; font-size: 1.02rem; max-width: 46em; margin: 0; }

.sc-section { display: flex; align-items: flex-start; gap: 16px; margin: 8px 0 6px 0; }
.sc-gauge {
    flex: 0 0 auto; font-family: 'IBM Plex Mono', monospace; font-weight: 500; font-size: 15px;
    color: var(--current-deep); background: #E6F1F2; border: 1px solid #BFDDE0;
    border-radius: 9px; padding: 6px 11px; line-height: 1; margin-top: 3px;
}
.sc-sec-title { font-size: 1.5rem; font-weight: 600; line-height: 1.15; }
.sc-sec-sub { color: var(--granite); font-size: 0.95rem; margin-top: 3px; max-width: 60em; }

.sc-kpis { display: flex; flex-wrap: wrap; gap: 14px; margin: 6px 0 18px 0; }
.sc-kpi {
    flex: 1 1 160px; background: var(--panel); border: 1px solid var(--line);
    border-left: 4px solid var(--current); border-radius: 11px; padding: 15px 17px;
}
.sc-kpi-val { font-family: 'Space Grotesk', sans-serif; font-size: 2rem; font-weight: 700; color: var(--ink); line-height: 1; }
.sc-kpi-label { color: var(--ink); font-weight: 600; font-size: 0.9rem; margin-top: 7px; }
.sc-kpi-note { color: var(--granite); font-size: 0.78rem; margin-top: 2px; }

.sc-legend { display: flex; flex-wrap: wrap; gap: 12px; align-items: center; margin: 4px 0 8px; }
.sc-legend-title { font-size: 0.82rem; font-weight: 600; color: var(--ink); }
.sc-legend-item { display: flex; align-items: center; gap: 6px; font-size: 0.8rem; color: var(--granite); }
.sc-legend-dot { width: 12px; height: 12px; border-radius: 50%; display: inline-block; border: 1px solid rgba(0,0,0,0.15); }

.stButton > button, .stDownloadButton > button {
    font-family: 'IBM Plex Sans', sans-serif; font-weight: 600; border-radius: 9px;
    border: 1px solid var(--current); background: var(--panel); color: var(--current-deep);
    transition: background 120ms ease, color 120ms ease;
}
.stButton > button:hover, .stDownloadButton > button:hover {
    background: #E6F1F2; color: var(--current-deep); border-color: var(--current-deep);
}
.stButton > button[kind="primary"] { background: var(--current); color: #ffffff; border-color: var(--current); }
.stButton > button[kind="primary"]:hover { background: var(--current-deep); border-color: var(--current-deep); }

[data-testid="stExpander"] { border: 1px solid var(--line); border-radius: 10px; }

@media (prefers-reduced-motion: reduce) {
    .stButton > button, .stDownloadButton > button { transition: none; }
}
</style>
"""


def inject_css():
    st.markdown(CUSTOM_CSS, unsafe_allow_html=True)


def render_hero():
    st.markdown(
        """
        <div class="sc-hero">
          <div class="sc-hero-eyebrow">Pilot Model</div>
          <div class="sc-hero-title">Stream Crossing Prioritization</div>
          <p class="sc-hero-sub">Adjust goal and criterion weightings, choose an area of interest,
          then run the model to rank crossings for replacement and export the results.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def section_header(number, title, subtitle=None):
    sub = f'<div class="sc-sec-sub">{subtitle}</div>' if subtitle else ""
    st.markdown(
        f"""
        <div class="sc-section">
          <div class="sc-gauge">{number:02d}</div>
          <div><div class="sc-sec-title">{title}</div>{sub}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_kpis(df):
    total = len(df)

    def count_q(q):
        return int((df["TotQual"] == q).sum()) if "TotQual" in df.columns else 0

    if "Tot_Present" in df.columns and "Tot_Missing" in df.columns:
        denom = (df["Tot_Present"] + df["Tot_Missing"]).replace(0, np.nan)
        mean_conf = (df["Tot_Present"] / denom).mean() * 100
        conf_str = f"{mean_conf:.0f}%" if pd.notna(mean_conf) else "n/a"
    else:
        conf_str = "n/a"

    cards = [
        ("Crossings scored", f"{total:,}", "in current view"),
        ("Very High priority", f"{count_q('Very High'):,}", "top Jenks class"),
        ("High priority", f"{count_q('High'):,}", "second Jenks class"),
        ("Mean data completeness", conf_str, "criteria present"),
    ]
    html = '<div class="sc-kpis">' + "".join(
        f'<div class="sc-kpi"><div class="sc-kpi-val">{value}</div>'
        f'<div class="sc-kpi-label">{label}</div>'
        f'<div class="sc-kpi-note">{note}</div></div>'
        for label, value, note in cards
    ) + "</div>"
    st.markdown(html, unsafe_allow_html=True)


def render_map_legend():
    items = "".join(
        f'<div class="sc-legend-item"><span class="sc-legend-dot" style="background:{bg}"></span>{name}</div>'
        for name, (bg, _fg) in QUAL_COLORS.items()
    )
    st.markdown(
        '<div class="sc-legend"><span class="sc-legend-title">Total priority (after run):</span>'
        + items
        + '<div class="sc-legend-item"><span class="sc-legend-dot" style="background:#3186cc"></span>Not yet scored</div></div>',
        unsafe_allow_html=True,
    )


def _style_qual(val):
    pair = QUAL_COLORS.get(val)
    if not pair:
        return ""
    bg, fg = pair
    return f"background-color: {bg}; color: {fg}; font-weight: 600;"


def _fmt_rank(v):
    return "" if pd.isna(v) else f"{v:.0f}"


# --------------------------------------------------------------------------- #
# Data loading and caching
# --------------------------------------------------------------------------- #

@st.cache_data
def load_default_params():
    with open(DEFAULT_PARAMS_PATH) as f:
        return json.load(f)


@st.cache_data
def load_default_input():
    if DEFAULT_INPUT_PATH.exists():
        return pd.read_csv(DEFAULT_INPUT_PATH)
    return None


@st.cache_data(ttl=3600, show_spinner=False)
def cached_photo_urls(sades_id):
    """Cached SADES photo lookup so switching between top crossings is instant
    and the same crossing is not re-queried on every fragment rerun."""
    return gis_utils.query_sades_photo_urls(str(sades_id))


def assemble_params(base_params):
    """Build the params dict from the current weight-widget state in
    st.session_state. Reading from session_state (rather than widget return
    values) lets the weight widgets live inside a fragment."""
    params = copy.deepcopy(base_params)
    for goal_key in GOAL_LABELS:
        on = st.session_state.get(f"goal_on_{goal_key}", True)
        w = st.session_state.get(f"goal_w_{goal_key}", base_params["goal_weights"][goal_key])
        params["goal_weights"][goal_key] = w if on else 0.0

        ck = GOAL_TO_CRITERIA_KEY.get(goal_key)
        if ck and ck in base_params.get("criteria_weights", {}):
            for crit in CRITERIA_LABELS[ck]:
                con = st.session_state.get(f"crit_on_{ck}_{crit}", True)
                cw = st.session_state.get(f"crit_w_{ck}_{crit}", base_params["criteria_weights"][ck][crit])
                params["criteria_weights"][ck][crit] = cw if con else 0.0
    return params


# --------------------------------------------------------------------------- #
# Weightings (fragment: slider moves rerun only this block)
# --------------------------------------------------------------------------- #

@fragment_decorator
def weight_controls_fragment(base_params):
    section_header(
        1, "Weightings",
        "Toggle a goal off to exclude it from the composite score. Sliders reflect "
        "the survey-derived defaults from configs/params.json and adjust from 0 to 1. "
        "Changes take effect on the next run.",
    )

    cols_per_row = 2
    goal_keys = list(GOAL_LABELS.keys())
    for row_start in range(0, len(goal_keys), cols_per_row):
        row_keys = goal_keys[row_start: row_start + cols_per_row]
        row_cols = st.columns(cols_per_row)
        for col, goal_key in zip(row_cols, row_keys):
            label = GOAL_LABELS[goal_key]
            default_w = base_params["goal_weights"][goal_key]
            with col:
                st.subheader(label)
                on = st.checkbox("Include this goal", value=True, key=f"goal_on_{goal_key}")
                st.slider("Goal weight", 0.0, 1.0, float(default_w), 0.01,
                          key=f"goal_w_{goal_key}", disabled=not on)

                ck = GOAL_TO_CRITERIA_KEY.get(goal_key)
                if ck and ck in base_params.get("criteria_weights", {}):
                    with st.expander(f"{label}: criteria weights", expanded=False):
                        for crit, crit_label in CRITERIA_LABELS[ck].items():
                            default_cw = base_params["criteria_weights"][ck][crit]
                            con = st.checkbox(f"Include: {crit_label}", value=True,
                                              key=f"crit_on_{ck}_{crit}")
                            st.slider(crit_label, 0.0, 1.0, float(default_cw), 0.01,
                                      key=f"crit_w_{ck}_{crit}", disabled=not con)


# --------------------------------------------------------------------------- #
# Region selection (two-step, single method, no draw)
# --------------------------------------------------------------------------- #

def _value_select(label, names, key):
    if not names:
        st.warning(f"No {label} boundaries found in data/gis/. Add the matching GeoJSON layer to enable this filter.")
        return None
    choice = st.selectbox(label, ["-- Select --"] + names, key=f"region_val_{key}")
    return None if choice == "-- Select --" else choice


def build_region_selector():
    section_header(
        2, "Select Region",
        "Choose one selection method, then its value. Only the chosen method is applied.",
    )
    method_label = st.selectbox("Selection method", list(REGION_METHODS.keys()), index=0)
    method = REGION_METHODS[method_label]

    value = None
    if method == "town":
        value = _value_select("Town", gis_utils.get_town_names(), "town")
    elif method == "county":
        value = _value_select("County / RPC", gis_utils.get_county_names(), "county")
    elif method == "huc12":
        value = _value_select("HUC12 Watershed", gis_utils.get_huc12_names(), "huc12")
    return method, value


def build_map_section(active_boundary_gdf, highlight_ids, result_df):
    """Display-only GIS map, rendered only after a run (result_df is not
    None), and restricted to only the crossings actually scored in
    result_df."""
    section_header(3, "Interactive GIS Map",
                   "Crossings are colored by total priority from the last run. Only crossings "
                   "included in that run are shown. Selecting a region zooms and highlights it.")

    try:
        from streamlit_folium import st_folium
    except ImportError:
        st.error("streamlit-folium is not installed. Add streamlit-folium to requirements.txt to enable the map.")
        return

    points_gdf = gis_utils.load_sades_points()
    if points_gdf is None:
        st.info("SADES point GeoJSON not found in data/gis/. The map cannot display crossing locations.")
        return

    fmap = gis_utils.build_map(
        points_gdf=points_gdf,
        active_boundary_gdf=active_boundary_gdf,
        highlight_ids=highlight_ids,
        results_df=result_df,
        score_col="TotQual",
    )

    render_map_legend()

    # returned_objects=[] makes the map display only: interactions do not send
    # data back and do not trigger reruns. Fall back on older st_folium.
    try:
        st_folium(fmap, use_container_width=True, height=520, key="main_map", returned_objects=[])
    except TypeError:
        try:
            st_folium(fmap, width=None, height=520, key="main_map", returned_objects=[])
        except TypeError:
            st_folium(fmap, width=None, height=520, key="main_map")


def filter_by_region(df, method, value):
    if method == "town":
        ids = gis_utils.get_ids_in_town(value) if value else None
    elif method == "county":
        ids = gis_utils.get_ids_in_county(value) if value else None
    elif method == "huc12":
        ids = gis_utils.get_ids_in_huc12(value) if value else None
    else:  # "all"
        return df

    if ids is None or "SADES_ID" not in df.columns:
        return df
    return df[df["SADES_ID"].astype(str).isin(set(ids))]


# --------------------------------------------------------------------------- #
# Results (fragment: table slider and photo switch rerun only this block)
# --------------------------------------------------------------------------- #

def rank_top_crossings(df, top_n=20):
    """Sort by Jenks class (TotQual, highest first), then by confidence
    (Tot_Present), then by TotRank as the final tiebreaker."""
    if df.empty:
        return df

    ranked = df.copy()
    ranked["_qual_order"] = ranked["TotQual"].map(JENKS_ORDER).fillna(-1) if "TotQual" in ranked.columns else -1
    ranked["_confidence_order"] = ranked["Tot_Present"] if "Tot_Present" in ranked.columns else 0

    sort_cols = ["_qual_order", "_confidence_order"]
    ascending = [False, False]
    if "TotRank" in ranked.columns:
        sort_cols.append("TotRank")
        ascending.append(True)

    ranked = ranked.sort_values(sort_cols, ascending=ascending)
    ranked = ranked.drop(columns=["_qual_order", "_confidence_order"])
    return ranked.head(top_n)


def build_top_crossings_table(display_df):
    section_header(
        4, "Top Crossings",
        "Sorted by Jenks class (Very High to Very Low), then by confidence (criteria "
        "present out of total), then by total rank as a tiebreaker. A rank based on "
        "2 of 18 criteria is far less reliable than one based on 16 of 18, so class "
        "and confidence are emphasized over raw rank.",
    )

    top_n = st.slider("Number of top crossings to display", 5, 50, 20)
    top_df = rank_top_crossings(display_df, top_n=top_n)

    show_cols = ["SADES_ID", "TotRank", "TotQual", "ConfTot"]
    for _goal_key, qual_col in GOAL_QUAL_COL.items():
        if qual_col and qual_col in top_df.columns:
            show_cols.append(qual_col)
    show_cols = [c for c in show_cols if c in top_df.columns]
    qual_cols_present = [c for c in show_cols if c.endswith("Qual")]

    styler = top_df[show_cols].style
    if qual_cols_present:
        if hasattr(styler, "map"):          # Styler.applymap renamed to map in pandas 2.1
            styler = styler.map(_style_qual, subset=qual_cols_present)
        else:
            styler = styler.applymap(_style_qual, subset=qual_cols_present)
    if "TotRank" in show_cols:
        styler = styler.format({"TotRank": _fmt_rank})   # integer rank, no trailing .00

    st.dataframe(styler, use_container_width=True, hide_index=True)

    st.download_button(
        "Download top crossings (CSV)",
        data=top_df[show_cols].to_csv(index=False).encode("utf-8"),
        file_name="top_crossings.csv",
        mime="text/csv",
    )


def render_photo_browser(display_df):
    section_header(5, "Top Crossing Photos",
                   "Photos load automatically for the ten highest-priority crossings. Use the selector to switch between them.")

    top10 = rank_top_crossings(display_df, top_n=10)
    if top10.empty or "SADES_ID" not in top10.columns:
        st.caption("No crossings available for photos.")
        return

    ids = top10["SADES_ID"].astype(str).tolist()
    labels = [f"Rank {i + 1}: SADES_ID {sid}" for i, sid in enumerate(ids)]
    choice = st.selectbox("View photos for", labels, index=0, key="photo_pick")
    sid = ids[labels.index(choice)]

    with st.spinner("Loading photos..."):
        urls = cached_photo_urls(sid)

    if not urls:
        st.info("No photos found for this crossing, or the SADES photo service could not be reached.")
        return

    cols = st.columns(2)
    for i, url in enumerate(urls):
        cols[i % 2].image(url, caption=f"SADES_ID {sid}")


def build_downloads_section(display_df):
    section_header(6, "Downloads", "Export the full scored dataset as CSV or the formatted Excel workbook.")

    col_a, col_b = st.columns(2)
    col_a.download_button(
        "Download full results as CSV",
        data=display_df.to_csv(index=False).encode("utf-8"),
        file_name="results_all.csv",
        mime="text/csv",
    )

    excel_bytes = st.session_state.get("excel_bytes")
    if excel_bytes:
        col_b.download_button(
            "Download Excel report",
            data=excel_bytes,
            file_name="report.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    else:
        err = st.session_state.get("excel_error")
        col_b.warning(f"Excel report unavailable: {err}" if err else "Excel report unavailable.")


@fragment_decorator
def results_fragment():
    display_df = st.session_state["result_df"]
    st.divider()
    render_kpis(display_df)
    build_top_crossings_table(display_df)
    st.divider()
    render_photo_browser(display_df)
    st.divider()
    with st.expander("View full results table"):
        cfg = {}
        if "TotRank" in display_df.columns and hasattr(st, "column_config"):
            cfg = {"TotRank": st.column_config.NumberColumn(format="%d")}
        st.dataframe(display_df, use_container_width=True, column_config=cfg)
    build_downloads_section(display_df)


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #

def main():
    inject_css()
    render_hero()

    base_params = load_default_params()
    weight_controls_fragment(base_params)
    params = assemble_params(base_params)

    method, value = build_region_selector()

    st.divider()
    uploaded = st.file_uploader(
        "Upload input CSV (optional; uses bundled demo data/input/crossings.csv if not provided)",
        type="csv",
    )
    run_validation = st.checkbox(
        "Validate input data before running (unchecked = skip validation, default)",
        value=False,
    )

    if uploaded is not None:
        df = pd.read_csv(uploaded)
        data_token = f"{uploaded.name}:{uploaded.size}"
    else:
        df = load_default_input()
        if df is None:
            st.info("No input CSV uploaded and no bundled demo file found at data/input/crossings.csv. Upload a CSV to proceed.")
            return
        data_token = "demo"
        st.caption(f"Using bundled demo dataset: {len(df)} records.")

    # Invalidate stale results when the data or region selection changes, so the
    # displayed results always match the selection they were run against.
    current_sig = f"{data_token}|{method}|{value}"
    if st.session_state.get("result_sig") not in (None, current_sig):
        for k in ("result_df", "result_sig", "excel_bytes", "excel_error"):
            st.session_state.pop(k, None)

    if run_validation:
        errors = validate_dataset(df, params.get("validation", {}))
        if errors:
            st.error("Validation failed. Uncheck validation or fix the input data.")
            for e in errors:
                st.write(f"- {e}")
            st.stop()

    filtered_df = filter_by_region(df, method, value)
    active_filter = method != "all" and value is not None
    if active_filter and "SADES_ID" in df.columns:
        st.caption(f"Region filter active: {len(filtered_df)} of {len(df)} crossings selected.")

    # Run button now appears before the map (map is rendered further down,
    # only once a result exists in session_state).
    st.divider()
    if st.button("Run Analysis", type="primary"):
        if active_filter and filtered_df.empty:
            st.warning("No crossings match the current selection. Choose a different area.")
            st.stop()

        run_df = filtered_df
        with st.spinner("Running model..."):
            try:
                result_df = run_analysis(run_df.copy(), params)
            except Exception as e:
                st.error(f"The model could not complete: {e}")
                st.stop()

        sort_col = "TotRank" if "TotRank" in result_df.columns else None
        display_df = result_df.sort_values(sort_col) if sort_col else result_df

        st.session_state["result_df"] = display_df
        st.session_state["result_sig"] = current_sig
        try:
            st.session_state["excel_bytes"] = build_excel_report(display_df)
            st.session_state.pop("excel_error", None)
        except Exception as e:
            st.session_state["excel_bytes"] = None
            st.session_state["excel_error"] = str(e)

        st.success(f"Analysis complete: {len(display_df)} crossings scored.")

    # Map (and results) are only rendered after a run has produced a
    # result_df, and the map only shows the crossings included in that run.
    if "result_df" in st.session_state:
        highlight = gis_utils.get_ids_for_selection(method, value)
        active_boundary = gis_utils.get_boundary_feature(method, value)
        build_map_section(active_boundary, highlight, st.session_state["result_df"])
        results_fragment()
    else:
        st.caption("Set your weightings and region, then click Run Analysis to score the crossings. "
                   "The map will appear here once a run has completed.")


if __name__ == "__main__":
    main()
