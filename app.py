"""Streamlit interface for the Stream Crossing Prioritization Model
(UNH Beta Model v1.2).

UNH Beta Model v1.2 is the July 2025 update of the model per Consultant Team
recommendations at the end of the ARPA phase, building on UNH Beta Model v1.1
(finalized May 2025). It adds terrestrial wildlife connectivity and watershed
water quality impairment, renames the Habitat Quality criterion to Habitat
Condition Tier, and reports the mean-substituted ranking family. The Excel
export adds a default-baseline comparison whenever the user departs from the
default weightings or the full statewide extent.

Weighting presentation scale:
  - Goal and criterion weights are presented on a coarse whole-number scale,
    either 0 to 4 or 0 to 10, chosen at the top of the Weightings section. The
    selected integer is divided by the scale maximum before the weights reach
    the model, so run_analysis still receives weights on 0 to 1.
  - Changing the scale returns every weight to its default on the new scale.

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
import datetime
from pathlib import Path

import streamlit as st
import pandas as pd
import numpy as np

sys.path.insert(0, str(Path(__file__).parent / "src"))
sys.path.insert(0, str(Path(__file__).parent / "scripts"))

from model import run_analysis  # noqa: E402
from utils import gis_utils  # noqa: E402  (src/utils/gis_utils.py)
from excel_report import build_excel_report  # noqa: E402  (scripts/excel_report.py)
from utils.validation import validate_dataset_report, apply_null_codes  # noqa: E402
from utils.io_utils import load_csv  # noqa: E402

st.set_page_config(
    page_title="Stream Crossing Prioritization Model (UNH Beta Model v1.2)",
    page_icon="\U0001F30A",
    layout="wide",
)

DEFAULT_PARAMS_PATH = Path(__file__).parent / "configs" / "params.json"
DEFAULT_INPUT_PATH = Path(__file__).parent / "data" / "input" / "crossings.csv"
DEFAULT_BASELINE_PATH = Path(__file__).parent / "data" / "baseline" / "baseline_all.csv.gz"

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
    "flood_vulnerability": "FVQualMS",
    "environmental_quality": "EQQualMS",
    "structural_risk": "SRQualMS",
    "road_criticality": "RCQualMS",
    "wildlife_connectivity": "WLQualMS",
    "habitat_quality": "HQGQualMS",
    "environmental_justice": None,  # EJ has no dedicated Qual column in model.py
}

CRITERIA_LABELS = {
    "fv": {"hydraulic_capacity": "Hydraulic Capacity", "flooding_history": "Flooding History"},
    "eq": {"erosion": "Erosion", "geomorphic_compatibility": "Geomorphic Compatibility", "water_quality": "Water Quality"},
    "sr": {"condition": "Condition", "size": "Size", "material": "Material"},
    "rc": {"aadt": "AADT", "distance_to_services": "Distance to Services", "functional_classification": "Functional Classification"},
    "wl": {"aop": "Aquatic Organism Passage", "special_species": "Special Species", "terrestrial_organism_passage": "Terrestrial Organism Passage"},
    "hqg": {"habitat_condition_tier": "Habitat Condition Tier", "wetland_proximity": "Wetland Proximity", "conservation_status": "Conservation Status"},
}

# Criterion keys renamed across model versions. The value is the display label to
# use whichever key a given params.json happens to carry. This lets the app read
# an older params.json (habitat_quality) or the v1.2 one (habitat_condition_tier)
# without a KeyError, and to fall back to a readable label for any unmapped key.
CRITERIA_KEY_ALIASES = {
    "habitat_quality": "Habitat Condition Tier",
}


def criterion_label(ck, key):
    """Return a display label for criterion ``key`` within group ``ck``.

    Resolution order: the label table for the group, then the cross-version
    alias table, then a title-cased fallback derived from the key itself. The
    fallback guarantees the UI never crashes on an unrecognized criterion key.
    """
    labels = CRITERIA_LABELS.get(ck, {})
    if key in labels:
        return labels[key]
    if key in CRITERIA_KEY_ALIASES:
        return CRITERIA_KEY_ALIASES[key]
    return key.replace("_", " ").title()


# --------------------------------------------------------------------------- #
# Weighting presentation scale
#
# NHDES review found that two-decimal weights imply more precision than the
# survey-derived Relative Importance Index supports in practice, and that
# reviewers could not act on the difference between, for example, 0.66 and
# 0.67. Weights are therefore set in whole numbers on a coarse scale and
# divided by the scale maximum before they reach the model, so that
# params["goal_weights"] and params["criteria_weights"] stay on 0 to 1 exactly
# as model.py expects.
#
# The division itself changes nothing. Both aggregation levels are normalized
# weighted averages: model.calculate_total_score and each goal module return
# num / den, where den is the sum of the weights of the terms that are not
# missing, so multiplying every weight in a group by a constant leaves the
# score, the rank, and the Jenks class unchanged. What does change the result
# is rounding the defaults onto whole steps, which is why
# render_scale_selector() reports the mapping in force.
# --------------------------------------------------------------------------- #

WEIGHT_SCALES = {"0 to 4": 4, "0 to 10": 10}
DEFAULT_SCALE_LABEL = "0 to 4"

# Widget key for the scale selector, and the bookkeeping key recording which
# scale the current weight values were built for.
SCALE_KEY = "weight_scale_label"
SCALE_APPLIED_KEY = "weight_scale_applied"


def current_scale_max():
    """Return the maximum of the selected presentation scale (4 or 10)."""
    label = st.session_state.get(SCALE_KEY, DEFAULT_SCALE_LABEL)
    return WEIGHT_SCALES.get(label, WEIGHT_SCALES[DEFAULT_SCALE_LABEL])


def to_display_units(weight, scale_max):
    """Convert a 0 to 1 model weight to a whole number on the display scale.

    Rounding is half away from zero rather than the half-to-even rule of the
    built-in round(), so a weight landing exactly on a half step (0.875 on the
    0 to 4 scale) always moves up instead of toward the nearest even integer.
    Values outside 0 to 1 are clipped, which matters only if a hand-edited
    params.json carries a weight outside that range.
    """
    scaled = float(weight) * scale_max
    return int(min(max(np.floor(scaled + 0.5), 0), scale_max))


def to_model_weight(display_value, scale_max):
    """Convert a whole number on the display scale back to a 0 to 1 weight."""
    return float(display_value) / float(scale_max)


def snap_weight(weight, scale_max):
    """Return the 0 to 1 weight actually used after display-scale rounding."""
    return to_model_weight(to_display_units(weight, scale_max), scale_max)


# Goal accent colors, matched to the workbook tab colors in
# src/utils/report_spec.py so the interface and the Excel report read as one
# product.
GOAL_COLORS = {
    "flood_vulnerability": "#3E9AA8",
    "environmental_quality": "#E08A3C",
    "structural_risk": "#D65F5F",
    "road_criticality": "#C9A227",
    "wildlife_connectivity": "#7C77B9",
    "habitat_quality": "#4F86C6",
    "environmental_justice": "#C86B98",
}


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
    """Apply st.fragment if available.
    Falls back to a no-op so the app still runs on Streamlit older than 1.37."""
    frag = getattr(st, "fragment", None)
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

/* Goal-colored header on each weighting card */
.sc-goalhead {
    display: flex; align-items: center; gap: 9px;
    font-family: 'Space Grotesk', sans-serif; font-weight: 600; font-size: 1.18rem;
    color: var(--ink); padding: 4px 0 8px 0; margin-top: 6px;
    border-bottom: 2px solid var(--goal);
}
.sc-goaldot { width: 12px; height: 12px; border-radius: 50%; background: var(--goal); flex: 0 0 auto; }
.sc-goalstate {
    margin-left: auto; font-family: 'IBM Plex Mono', monospace; font-weight: 500;
    font-size: 0.68rem; letter-spacing: 0.08em; text-transform: uppercase;
    color: #ffffff; background: var(--goal); border-radius: 999px; padding: 2px 9px;
}

/* Active-goal chip row */
.sc-chiprow { display: flex; flex-wrap: wrap; align-items: center; gap: 7px; margin: 2px 0 16px 0; }
.sc-chip-lead { font-size: 0.86rem; font-weight: 600; color: var(--ink); margin-right: 4px; }
.sc-chip {
    font-size: 0.74rem; font-weight: 600; color: #ffffff; background: var(--chip);
    border-radius: 999px; padding: 3px 11px; line-height: 1.4;
}
.sc-chip-muted { font-size: 0.74rem; color: var(--granite); font-style: italic; margin-left: 4px; }

/* Footer */
.sc-footer {
    margin-top: 34px; padding-top: 16px; border-top: 1px solid var(--line);
    color: var(--granite); font-size: 0.82rem; line-height: 1.5;
}
.sc-footer strong { color: var(--ink); }

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
          <div class="sc-hero-eyebrow">UNH Beta Model v1.2 &middot; updated July 2025</div>
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
        return int((df["TotQualMS"] == q).sum()) if "TotQualMS" in df.columns else 0

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


def _fmt_cost(v):
    """Currency format for the Cost Estimate column; blank for missing."""
    return "" if pd.isna(v) else f"${v:,.0f}"


def _build_table_column_labels():
    """Display headers for the Top Crossings table.

    The workbook carries hover definitions on its coded headers, but the app
    table has no such affordance, so the coded score columns are relabeled with
    plain names here. Goal columns are derived from GOAL_LABELS / GOAL_QUAL_COL
    so the two never drift apart.
    """
    labels = {
        "TotMSRank": "Rank",
        "TotQualMS": "Overall Priority",
        "ConfTot": "Confidence",
        "CostEstimate": "Cost Estimate",
    }
    for goal_key, qual_col in GOAL_QUAL_COL.items():
        if qual_col:
            labels[qual_col] = GOAL_LABELS[goal_key]
    return labels


TABLE_COLUMN_LABELS = _build_table_column_labels()


# --------------------------------------------------------------------------- #
# Data loading and caching
#
# The loaders below are cached on the file's modification time and size, not on
# nothing. A plain @st.cache_data with no arguments caches the first return
# value for the life of the process, so if params.json changes on disk (for
# example after a git push and a Streamlit Cloud hot reload that does not clear
# the data cache) the app keeps serving the old contents. Passing the file
# signature as an argument makes the cache key change when the file changes, so
# an edited params.json or dataset is picked up on the next rerun.
# --------------------------------------------------------------------------- #

def _file_signature(path):
    """Return a (path, mtime, size) tuple, or (path, 0, 0) if the file is
    absent, for use as a cache key."""
    try:
        stat = path.stat()
        return (str(path), stat.st_mtime, stat.st_size)
    except OSError:
        return (str(path), 0, 0)


@st.cache_data(show_spinner=False)
def _load_params_cached(signature):
    path = Path(signature[0])
    with open(path) as f:
        return json.load(f)


def load_default_params():
    return _load_params_cached(_file_signature(DEFAULT_PARAMS_PATH))


@st.cache_data(show_spinner=False)
def _load_input_cached(signature):
    path = Path(signature[0])
    if path.exists():
        return load_csv(path, low_memory=False)
    return None


def load_default_input():
    return _load_input_cached(_file_signature(DEFAULT_INPUT_PATH))


@st.cache_data(show_spinner=False)
def _load_baseline_cached(signature):
    """Load the committed default baseline (default weightings, full extent).

    Returns None if the baseline file is absent, in which case the Excel export
    simply omits the Base_ comparison columns and the Default Baseline sheet.
    """
    path = Path(signature[0])
    if path.exists():
        return pd.read_csv(path, low_memory=False)
    return None


def load_baseline():
    return _load_baseline_cached(_file_signature(DEFAULT_BASELINE_PATH))


def is_default_run(params, base_params, method, value):
    """True when this run uses the default weightings over the full extent.

    In that case the run and the baseline would be identical, so the Base_
    comparison is suppressed. Any weight change or region filter makes the run
    non-default, and the baseline comparison is attached to the workbook.
    """
    if method != "all" or value is not None:
        return False

    tol = 1e-9
    for goal, weight in base_params["goal_weights"].items():
        if abs(float(params["goal_weights"].get(goal, weight)) - float(weight)) > tol:
            return False
    for ck, crits in base_params.get("criteria_weights", {}).items():
        for crit, weight in crits.items():
            got = params["criteria_weights"].get(ck, {}).get(crit, weight)
            if abs(float(got) - float(weight)) > tol:
                return False
    return True


@st.cache_data(ttl=3600, show_spinner=False)
def cached_photo_urls(sades_id):
    """Cached SADES photo lookup so switching between top crossings is instant
    and the same crossing is not re-queried on every fragment rerun."""
    return gis_utils.query_sades_photo_urls(str(sades_id))


def assemble_params(base_params):
    """Build the params dict from the current weight-widget state in
    st.session_state, converting the display-scale integers back to the 0 to 1
    weights the model expects. Reading from session_state (rather than widget
    return values) lets the weight widgets live inside a fragment.

    The fallbacks cover the first script run, before the widgets exist. They
    use the rounded default rather than the raw params.json value so that a run
    always matches what the sliders show.
    """
    scale_max = current_scale_max()
    params = copy.deepcopy(base_params)
    for goal_key in GOAL_LABELS:
        on = st.session_state.get(f"goal_on_{goal_key}", True)
        display = st.session_state.get(f"goal_w_{goal_key}")
        w = (to_model_weight(display, scale_max) if display is not None
             else snap_weight(base_params["goal_weights"][goal_key], scale_max))
        params["goal_weights"][goal_key] = w if on else 0.0

        ck = GOAL_TO_CRITERIA_KEY.get(goal_key)
        if ck and ck in base_params.get("criteria_weights", {}):
            # Iterate the keys that actually exist in params, so a criterion
            # renamed between model versions cannot raise a KeyError here.
            for crit, default_cw in base_params["criteria_weights"][ck].items():
                con = st.session_state.get(f"crit_on_{ck}_{crit}", True)
                crit_display = st.session_state.get(f"crit_w_{ck}_{crit}")
                cw = (to_model_weight(crit_display, scale_max) if crit_display is not None
                      else snap_weight(default_cw, scale_max))
                params["criteria_weights"][ck][crit] = cw if con else 0.0
    return params


def _default_weight_state(base_params, scale_max):
    """Map every weight-widget key to its default value on the given scale.

    Single source of truth for the defaults: the same mapping initializes the
    widgets, resets them, and tests whether the user has moved anything.
    Criterion keys are read from params.json rather than from CRITERIA_LABELS,
    so a criterion renamed between model versions cannot raise a KeyError, and
    a goal with no criteria group (environmental_justice) is skipped by the
    GOAL_TO_CRITERIA_KEY.get() guard.

    Weight values are whole numbers on the display scale, matching the integer
    sliders; the toggle values are booleans.
    """
    state = {}
    for goal_key in GOAL_LABELS:
        state[f"goal_on_{goal_key}"] = True
        state[f"goal_w_{goal_key}"] = to_display_units(
            base_params["goal_weights"][goal_key], scale_max
        )

        ck = GOAL_TO_CRITERIA_KEY.get(goal_key)
        if ck and ck in base_params.get("criteria_weights", {}):
            for crit, default_cw in base_params["criteria_weights"][ck].items():
                state[f"crit_on_{ck}_{crit}"] = True
                state[f"crit_w_{ck}_{crit}"] = to_display_units(default_cw, scale_max)
    return state


def reset_weights_to_defaults(base_params, scale_max):
    """Restore every weight widget to its default on the given scale.

    Assignment is used rather than deletion of the session_state keys.
    Deleting a widget key clears the server-side value, but it leaves
    widget_value_changed False in Streamlit's widget registration, so the
    set_value flag is omitted from the widget proto and the browser keeps
    showing the value the user last set. Assigning the default marks the key
    as a new session state value, which raises that flag and forces the
    frontend to adopt the server value.

    Must be called before the weight widgets are instantiated in the current
    script run; SessionState.__setitem__ raises StreamlitAPIException for a
    key whose widget has already been created in the same run.
    """
    for key, value in _default_weight_state(base_params, scale_max).items():
        st.session_state[key] = value


def ensure_weight_state(base_params):
    """Initialize the weight widgets, and reset them when the scale changes.

    Returns the maximum of the scale now in force. On the first script run the
    bookkeeping key is absent, so every widget value is written at the default
    scale. When the user picks the other scale the stored maximum no longer
    matches and every weight returns to its default on the new scale, which is
    the agreed behavior: carrying an integer across scales would silently
    change its meaning, because 3 is a weight of 0.75 on the 0 to 4 scale and
    0.30 on the 0 to 10 scale.

    Because this rewrites the weight keys, it must run before any weight widget
    is created in the current script run.
    """
    scale_max = current_scale_max()
    if st.session_state.get(SCALE_APPLIED_KEY) != scale_max:
        reset_weights_to_defaults(base_params, scale_max)
        st.session_state[SCALE_APPLIED_KEY] = scale_max
    return scale_max


def weights_at_scale_defaults(base_params, scale_max):
    """True when no weight widget has been moved off its default."""
    return all(
        st.session_state.get(key) == value
        for key, value in _default_weight_state(base_params, scale_max).items()
    )


# --------------------------------------------------------------------------- #
# Weightings (fragment: slider moves rerun only this block)
# --------------------------------------------------------------------------- #

def render_scale_selector(base_params):
    """Render the weighting scale picker and return the scale maximum in force.

    The picker is created before ensure_weight_state() runs, so session_state
    already carries the new selection when the weight values are rebuilt for
    it. The selector holds its own value through the widget key rather than an
    index argument, which keeps Streamlit from receiving both a default and a
    session state entry for the same widget.
    """
    if SCALE_KEY not in st.session_state:
        st.session_state[SCALE_KEY] = DEFAULT_SCALE_LABEL

    pick_col, note_col = st.columns([1, 2])
    with pick_col:
        st.radio(
            "Weighting scale",
            list(WEIGHT_SCALES.keys()),
            key=SCALE_KEY,
            horizontal=True,
            help="Whole-number scale used by every goal and criterion slider. "
                 "Switching scales returns all weights to their defaults.",
        )

    scale_max = ensure_weight_state(base_params)

    with note_col:
        st.caption(
            f"Every slider moves in whole steps from 0 to {scale_max}. Each step is "
            f"divided by {scale_max} before the model runs, so a slider at {scale_max} "
            f"is a weight of 1.00 and a slider at 0 drops that goal or criterion "
            f"from the score."
        )

    with st.expander("How this scale maps to the model weights", expanded=False):
        st.markdown(
            "Goal and criterion scores are weighted averages, so only the ratios "
            "between weights affect the result: dividing every slider by the scale "
            "maximum changes no score, no rank, and no priority class. Rounding the "
            "survey values onto whole steps does change them. On the 0 to 4 scale "
            "several goals the survey placed apart share a step, and the coarser the "
            "scale, the more of that separation is lost. Runs at these defaults will "
            "therefore differ from the committed Default Baseline (v1.2), which uses "
            "the unrounded survey values, and the Excel export carries the baseline "
            "comparison columns so the difference stays visible."
        )
        rows = []
        for goal_key, goal_label in GOAL_LABELS.items():
            survey_w = float(base_params["goal_weights"][goal_key])
            steps = to_display_units(survey_w, scale_max)
            rows.append({
                "Goal": goal_label,
                "Weight": "Goal weight",
                "Survey value": round(survey_w, 2),
                "Default step": steps,
                "Model weight": round(to_model_weight(steps, scale_max), 2),
            })
            ck = GOAL_TO_CRITERIA_KEY.get(goal_key)
            if ck and ck in base_params.get("criteria_weights", {}):
                for crit, default_cw in base_params["criteria_weights"][ck].items():
                    crit_steps = to_display_units(default_cw, scale_max)
                    rows.append({
                        "Goal": goal_label,
                        "Weight": criterion_label(ck, crit),
                        "Survey value": round(float(default_cw), 2),
                        "Default step": crit_steps,
                        "Model weight": round(to_model_weight(crit_steps, scale_max), 2),
                    })
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    return scale_max


@fragment_decorator
def weight_controls_fragment(base_params):
    section_header(
        1, "Weightings",
        "Choose a weighting scale, then set each goal and criterion in whole numbers. "
        "Toggle a goal off to exclude it from the composite score. Sliders start at the "
        "survey-derived defaults, rounded to the nearest step on the chosen scale. "
        "Changes take effect on the next run.",
    )

    scale_max = render_scale_selector(base_params)

    # Reset control and a live summary of how many goals are active.
    top_l, top_r = st.columns([3, 1])
    with top_r:
        if st.button("Reset to defaults", use_container_width=True,
                     help="Restore every goal and criterion to its default weight and re-enable it."):
            # No explicit rerun: this button is rendered above the widget loop,
            # so the assigned defaults are picked up by the sliders and
            # checkboxes later in this same fragment pass, and by the chip
            # summary immediately below.
            reset_weights_to_defaults(base_params, scale_max)

    active_goals = [
        GOAL_LABELS[g] for g in GOAL_LABELS
        if st.session_state.get(f"goal_on_{g}", True)
    ]
    with top_l:
        chips = "".join(
            f'<span class="sc-chip" style="--chip:{GOAL_COLORS.get(g, "#5A6B75")}">'
            f'{GOAL_LABELS[g]}</span>'
            for g in GOAL_LABELS if st.session_state.get(f"goal_on_{g}", True)
        )
        excluded = [GOAL_LABELS[g] for g in GOAL_LABELS
                    if not st.session_state.get(f"goal_on_{g}", True)]
        note = f'<span class="sc-chip-muted">Excluded: {", ".join(excluded)}</span>' if excluded else ""
        st.markdown(
            f'<div class="sc-chiprow"><span class="sc-chip-lead">{len(active_goals)} of '
            f'{len(GOAL_LABELS)} goals active</span>{chips}{note}</div>',
            unsafe_allow_html=True,
        )

    cols_per_row = 2
    goal_keys = list(GOAL_LABELS.keys())
    for row_start in range(0, len(goal_keys), cols_per_row):
        row_keys = goal_keys[row_start: row_start + cols_per_row]
        row_cols = st.columns(cols_per_row, gap="medium")
        for col, goal_key in zip(row_cols, row_keys):
            label = GOAL_LABELS[goal_key]
            color = GOAL_COLORS.get(goal_key, "#5A6B75")
            on = st.session_state.get(f"goal_on_{goal_key}", True)
            with col:
                # Colored goal header tied to the workbook's goal color.
                st.markdown(
                    f'<div class="sc-goalhead" style="--goal:{color}">'
                    f'<span class="sc-goaldot"></span>{label}'
                    f'<span class="sc-goalstate">{"active" if on else "excluded"}</span></div>',
                    unsafe_allow_html=True,
                )
                # No value= argument on the weight widgets: ensure_weight_state()
                # has already put every key in session_state, and passing both a
                # default and a session state entry for one widget is what raises
                # Streamlit's duplicate-value warning.
                on = st.checkbox("Include this goal", key=f"goal_on_{goal_key}")
                st.slider(f"Goal weight (0 to {scale_max})", 0, scale_max, step=1,
                          key=f"goal_w_{goal_key}", disabled=not on)

                ck = GOAL_TO_CRITERIA_KEY.get(goal_key)
                if ck and ck in base_params.get("criteria_weights", {}):
                    crit_items = list(base_params["criteria_weights"][ck].items())
                    n_on = sum(
                        1 for crit, _ in crit_items
                        if st.session_state.get(f"crit_on_{ck}_{crit}", True)
                    )
                    with st.expander(f"Criteria weights  ({n_on}/{len(crit_items)} on)", expanded=False):
                        # Iterate the keys present in params, so a renamed
                        # criterion cannot raise a KeyError. Labels resolve
                        # through criterion_label(), which tolerates the
                        # habitat_quality -> Habitat Condition Tier rename.
                        for crit, _default_cw in crit_items:
                            crit_lab = criterion_label(ck, crit)
                            con = st.checkbox(
                                f"Include: {crit_lab}",
                                key=f"crit_on_{ck}_{crit}", disabled=not on)
                            st.slider(crit_lab, 0, scale_max, step=1,
                                      key=f"crit_w_{ck}_{crit}", disabled=not (on and con))


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
        score_col="TotQualMS",
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
    """Return the ``top_n`` crossings ordered by TotMSRank (1 = highest
    priority). Rows without a rank sort last."""
    if df.empty or "TotMSRank" not in df.columns:
        return df.head(top_n)
    ranked = df.sort_values("TotMSRank", ascending=True, na_position="last")
    return ranked.head(top_n)


def build_top_crossings_table(display_df):
    section_header(
        4, "Top Crossings",
        "Ranked by overall crossing score; Rank 1 is the highest priority.",
    )

    top_n = st.slider("Number of top crossings to display", 5, 50, 20)
    top_df = rank_top_crossings(display_df, top_n=top_n)

    # Identity, rank, cost, overall class and confidence, then the per-goal
    # classes. Cost sits before the color-coded class block so the qual columns
    # stay visually contiguous.
    goal_cols = [qc for qc in GOAL_QUAL_COL.values() if qc]
    ordered = ["SADES_ID", "Location", "TotMSRank", "CostEstimate",
               "TotQualMS", "ConfTot"] + goal_cols
    show_cols = [c for c in ordered if c in top_df.columns]

    table = top_df[show_cols].rename(columns=TABLE_COLUMN_LABELS)

    # Class columns to color-code, under their new display names.
    qual_source = ["TotQualMS"] + goal_cols
    qual_cols_present = [TABLE_COLUMN_LABELS.get(c, c) for c in qual_source if c in show_cols]

    styler = table.style
    if qual_cols_present:
        if hasattr(styler, "map"):          # Styler.applymap renamed to map in pandas 2.1
            styler = styler.map(_style_qual, subset=qual_cols_present)
        else:
            styler = styler.applymap(_style_qual, subset=qual_cols_present)

    number_formats = {}
    if "Rank" in table.columns:
        number_formats["Rank"] = _fmt_rank            # integer rank, no trailing .00
    if "Cost Estimate" in table.columns:
        number_formats["Cost Estimate"] = _fmt_cost   # e.g. $150,000
    if number_formats:
        styler = styler.format(number_formats)

    st.dataframe(styler, use_container_width=True, hide_index=True)

    st.download_button(
        "Download top crossings (CSV)",
        data=table.to_csv(index=False).encode("utf-8"),
        file_name="top_crossings.csv",
        mime="text/csv",
    )


def render_photo_browser(display_df):
    section_header(5, "Top Crossing Photos",
                   "Use the selector to view photos for any of the twenty highest-priority crossings.")

    top20 = rank_top_crossings(display_df, top_n=20)
    if top20.empty or "SADES_ID" not in top20.columns:
        st.caption("No crossings available for photos.")
        return

    ids = top20["SADES_ID"].astype(str).tolist()
    ranks = top20["TotMSRank"].tolist() if "TotMSRank" in top20.columns else [None] * len(ids)
    locs = top20["Location"].tolist() if "Location" in top20.columns else [""] * len(ids)

    labels = []
    for i, (sid, rnk, loc) in enumerate(zip(ids, ranks, locs)):
        rank_txt = f"Rank {int(rnk)}" if pd.notna(rnk) else f"Rank {i + 1}"
        loc_txt = f"{loc} " if isinstance(loc, str) and loc else ""
        labels.append(f"{rank_txt}: {loc_txt}(SADES_ID {sid})")

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
        if "TotMSRank" in display_df.columns and hasattr(st, "column_config"):
            cfg = {"TotMSRank": st.column_config.NumberColumn(format="%d")}
        st.dataframe(display_df, use_container_width=True, column_config=cfg)
    build_downloads_section(display_df)


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #

def validate_and_prepare(df, params):
    """Validate the input, convert reviewed null-coded markers, and report.

    The CLI has run validation since v1.1, but the app did not: an unreviewed
    categorical value reached the score maps, produced NaN, and lowered the
    confidence count with nothing said. The app now runs the same check the CLI
    runs, so the two cannot disagree about whether a file is usable.

    Returns (df, warnings), or (None, None) when the run must not proceed.
    There is deliberately no bypass control in the interface: an unrecognized
    value is a one-time configuration decision, not something to click past on
    every run.
    """
    rules = params.get("validation")
    if not rules:
        return df, []

    report = validate_dataset_report(
        df, rules,
        null_values=params.get("null_values"),
        score_maps=params.get("score_maps"))

    if not report.ok:
        st.error(
            "The input data contains categorical values the model has not been "
            "told how to handle, so it cannot be scored. Each value below needs "
            "to be reviewed once and added to configs/params.json: to that "
            "field's \"null_values\" list if it marks a crossing that could not "
            "be scored, or to its \"enum\" with a matching \"score_maps\" entry "
            "if it is a real category.")
        for message in report.errors:
            st.markdown(f"- {message}")
        return None, None

    for message in report.warnings:
        st.warning(message)

    # The conversion itself is not surfaced in the interface. The markers mean
    # the criterion could not be scored at that crossing, which is the same
    # information a blank cell carries, and every run of a real SADES extract
    # hits thousands of them. Reporting a routine, expected conversion on every
    # run trains the reader to dismiss the notice area, which is where genuine
    # warnings appear. The per-crossing effect is already visible where it
    # matters, in the confidence columns of the results.
    df, _ = apply_null_codes(df, rules, null_values=params.get("null_values"))

    return df, list(report.warnings)


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

    if uploaded is not None:
        df = load_csv(uploaded, low_memory=False)
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
        for k in ("result_df", "result_sig", "excel_bytes", "excel_error",
                  "run_context"):
            st.session_state.pop(k, None)

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

        # A whole-number scale puts zero one step away from the lowest non-zero
        # setting, so these two states are now easy to reach by accident. With
        # every goal at zero the composite denominator is zero for every
        # crossing and model.calculate_total_score returns NaN, which would
        # produce an empty ranking rather than an error, so the run is blocked.
        if sum(float(w) for w in params["goal_weights"].values()) <= 0:
            st.warning("Every goal weight is set to zero, so no crossing can be scored. "
                       "Raise at least one goal weight, then run again.")
            st.stop()

        # A goal whose criteria are all zero degrades rather than fails: its
        # score is NaN for every crossing, so the goal drops out of the
        # composite for every crossing. That is worth stating, not blocking.
        zeroed_goals = [
            GOAL_LABELS[goal_key]
            for goal_key, ck in GOAL_TO_CRITERIA_KEY.items()
            if float(params["goal_weights"].get(goal_key, 0.0)) > 0
            and sum(float(w) for w in params["criteria_weights"].get(ck, {}).values()) <= 0
        ]
        if zeroed_goals:
            st.warning("Every criterion is set to zero for " + ", ".join(zeroed_goals)
                       + ". These goals cannot be scored and will be left out of the "
                         "composite score for every crossing.")

        run_df, validation_warnings = validate_and_prepare(
            filtered_df.copy(), params)
        if run_df is None:
            st.stop()

        with st.spinner("Running model..."):
            try:
                result_df = run_analysis(run_df, params)
            except Exception as e:
                st.error(f"The model could not complete: {e}")
                st.stop()

        sort_col = "TotMSRank" if "TotMSRank" in result_df.columns else None
        display_df = result_df.sort_values(sort_col) if sort_col else result_df

        st.session_state["result_df"] = display_df
        st.session_state["result_sig"] = current_sig

        # Attach the default-baseline comparison only when the run departs from
        # the default weightings or the full extent; a default run would compare
        # against itself.
        default_run = is_default_run(params, base_params, method, value)
        baseline_df = None if default_run else load_baseline()
        if not default_run and baseline_df is None:
            st.info(
                "Baseline file data/baseline/baseline_all.csv.gz was not found, so "
                "the Excel export will omit the default-baseline comparison columns. Run "
                "scripts/build_baseline.py once and commit the result to enable it."
            )
        # Recorded on the Run Settings sheet so a saved workbook states what it
        # is a result of. Both inputs matter: Jenks classes and min-max
        # normalisation are computed across the crossings in the run, so the
        # extent changes the classes even when no weight is moved.
        run_context = {
            "region_method_label": next(
                (label for label, key in REGION_METHODS.items() if key == method),
                method),
            "region_value": value,
            "crossings_scored": len(display_df),
            "crossings_available": len(df),
            "input_label": (uploaded.name if uploaded is not None
                            else "Bundled demo dataset (data/input/crossings.csv)"),
            "run_timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
            "weight_scale": st.session_state.get(SCALE_KEY, DEFAULT_SCALE_LABEL),
            # The slider maximum, so the Run Settings sheet can tell a slider
            # left at its default position from one the user actually moved.
            # A survey default of 0.875 shows as a slider at 4 on the 0 to 4
            # scale and reaches the model as 1.00; without the scale that
            # untouched slider would be reported as changed.
            "weight_scale_max": current_scale_max(),
            "default_goal_weights": base_params.get("goal_weights", {}),
            "default_criteria_weights": base_params.get("criteria_weights", {}),
            "validation_warnings": validation_warnings,
        }
        st.session_state["run_context"] = run_context

        try:
            st.session_state["excel_bytes"] = build_excel_report(
                display_df, baseline_df=baseline_df, params=params,
                run_context=run_context)
            st.session_state.pop("excel_error", None)
        except Exception as e:
            st.session_state["excel_bytes"] = None
            st.session_state["excel_error"] = str(e)

        # is_default_run() compares against the unrounded params.json weights, so
        # a run left at the rounded defaults is correctly treated as a departure
        # from the committed baseline and keeps the Base_ comparison columns. The
        # message below separates that case from one where a slider was moved.
        scale_label = st.session_state.get(SCALE_KEY, DEFAULT_SCALE_LABEL)
        full_extent = method == "all" and value is None
        if default_run:
            scope = "default weightings, full extent"
        elif full_extent and weights_at_scale_defaults(base_params, current_scale_max()):
            scope = f"default weightings rounded to the {scale_label} scale, full extent"
        else:
            scope = "custom weightings or filtered extent"
        st.success(f"Analysis complete: {len(display_df)} crossings scored ({scope}).")

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

    render_footer()


def render_footer():
    st.markdown(
        """
        <div class="sc-footer">
          <strong>Stream Crossing Prioritization Model, UNH Beta Model v1.2</strong>,
          the July 2025 update of UNH Beta Model v1.1 (finalized May 2025).
          A collaboration of NHDES, the New Hampshire Stream Crossing Initiative, and the University of New Hampshire.
          Results are planning-level and are not a substitute for site-specific engineering assessment.<br>
          Column definitions are embedded as header comments in the Excel report and documented in the Guide and Metadata (v1.2).
        </div>
        """,
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()
