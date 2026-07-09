
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

st.set_page_config(page_title="Stream Crossing Prioritization Model", layout="wide")

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

# Maps each goal to its criteria_weights sub-dictionary key in params.json,
# and to the Jenks-classified quality column produced by model.py for that goal.
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


@st.cache_data
def load_default_params():
    with open(DEFAULT_PARAMS_PATH) as f:
        return json.load(f)


@st.cache_data
def load_default_input():
    if DEFAULT_INPUT_PATH.exists():
        return pd.read_csv(DEFAULT_INPUT_PATH)
    return None


def build_weight_controls(base_params):
    """Weight/toggle sliders for goals and their nested criteria. Rendered at the
    top of the page per the requested layout, not in the sidebar."""
    params = copy.deepcopy(base_params)

    st.header("1. Weightings")
    st.caption(
        "Toggle a goal off to exclude it entirely from the composite score. "
        "Sliders reflect the survey-derived defaults from configs/params.json "
        "and can be adjusted from 0 to 1."
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
                weight = st.slider(
                    "Goal weight", 0.0, 1.0, float(default_w), 0.01,
                    key=f"goal_w_{goal_key}", disabled=not on,
                )
                params["goal_weights"][goal_key] = weight if on else 0.0

                crit_key = GOAL_TO_CRITERIA_KEY.get(goal_key)
                if crit_key and crit_key in base_params.get("criteria_weights", {}):
                    with st.expander(f"{label}: criteria weights", expanded=False):
                        for crit, crit_label in CRITERIA_LABELS[crit_key].items():
                            default_cw = base_params["criteria_weights"][crit_key][crit]
                            con = st.checkbox(
                                f"Include: {crit_label}", value=True,
                                key=f"crit_on_{crit_key}_{crit}",
                            )
                            cw = st.slider(
                                crit_label, 0.0, 1.0, float(default_cw), 0.01,
                                key=f"crit_w_{crit_key}_{crit}", disabled=not con,
                            )
                            params["criteria_weights"][crit_key][crit] = cw if con else 0.0

    return params


def build_region_selector():
    st.header("2. Select Region")
    st.caption(
        "Choose a town, county, and/or HUC12 watershed to filter crossings, or "
        "draw a custom polygon on the map below. Selections are combined as a "
        "union of matching SADES_IDs."
    )

    town_names = gis_utils.get_town_names()
    county_names = gis_utils.get_county_names()
    huc12_names = gis_utils.get_huc12_names()

    col1, col2, col3 = st.columns(3)
    with col1:
        town = st.selectbox(
            "Town (New_Hampshire_Political_Boundaries.geojson, field 'name')",
            ["-- All towns --"] + town_names,
        )
    with col2:
        county = st.selectbox(
            "County / RPC (RPC_s_Regional_Planning_Commissions.geojson, field 'NAME')",
            ["-- All counties --"] + county_names,
        )
    with col3:
        huc12 = st.selectbox(
            "HUC12 Watershed (HUC12_NH_Clipped.geojson, field 'HU_12_NAME')",
            ["-- All watersheds --"] + huc12_names,
        )

    if not town_names and not county_names and not huc12_names:
        st.warning(
            "Boundary GeoJSON files not found in data/gis/. Region filtering and "
            "the map layer will be unavailable until they are added."
        )

    return (
        None if town == "-- All towns --" else town,
        None if county == "-- All counties --" else county,
        None if huc12 == "-- All watersheds --" else huc12,
    )


def build_map_section(selected_ids):
    st.header("3. Interactive GIS Map")
    st.caption("Draw a polygon to select crossings by area of interest. Drawing a new shape replaces the previous selection.")

    try:
        from streamlit_folium import st_folium
    except ImportError:
        st.error("streamlit-folium is not installed. Add it to requirements.txt to enable the map.")
        return None

    points_gdf = gis_utils.load_sades_points()
    boundaries_gdf = gis_utils.load_town_boundaries()

    if points_gdf is None:
        st.info("SADES point GeoJSON not found in data/gis/. Map will not display crossing locations.")

    result_df = st.session_state.get("result_df")
    fmap = gis_utils.build_map(
        boundaries_gdf=boundaries_gdf,
        points_gdf=points_gdf,
        highlight_ids=selected_ids,
        results_df=result_df,
        score_col="TotQual",
    )

    map_output = st_folium(fmap, width=None, height=500, key="main_map")

    drawn_ids = None
    if map_output and map_output.get("last_active_drawing"):
        geometry = map_output["last_active_drawing"].get("geometry")
        if geometry:
            drawn_ids = gis_utils.get_ids_in_drawn_polygon(geometry)
            if drawn_ids is not None:
                st.success(f"Polygon selection: {len(drawn_ids)} crossings found.")

    return drawn_ids


def filter_by_region(df, town, county, huc12, drawn_ids):
    """Union of town, county, HUC12, and drawn-polygon selections. Returns df
    unchanged if no spatial filter is active."""
    id_sets = []

    if town:
        ids = gis_utils.get_ids_in_town(town)
        if ids is not None:
            id_sets.append(set(ids))
    if county:
        ids = gis_utils.get_ids_in_county(county)
        if ids is not None:
            id_sets.append(set(ids))
    if huc12:
        ids = gis_utils.get_ids_in_huc12(huc12)
        if ids is not None:
            id_sets.append(set(ids))
    if drawn_ids is not None:
        id_sets.append(set(drawn_ids))

    if not id_sets:
        return df

    combined_ids = set().union(*id_sets)
    if "SADES_ID" not in df.columns:
        return df
    return df[df["SADES_ID"].astype(str).isin(combined_ids)]


def rank_top_crossings(df, top_n=20):
    """Rank crossings for display per the requested interpretation logic:
    sort by Jenks class (TotQual, highest first), then by confidence
    (Tot_Present, most complete first), then by TotRank (lowest/best first)
    as the final tiebreaker. This deliberately favors interpretability
    (Jenks class + confidence) over raw TotRank, since TotRank alone can be
    misleading when very few criteria are present for a given crossing."""
    if df.empty:
        return df

    ranked = df.copy()

    if "TotQual" in ranked.columns:
        ranked["_qual_order"] = ranked["TotQual"].map(JENKS_ORDER).fillna(-1)
    else:
        ranked["_qual_order"] = -1

    if "Tot_Present" not in ranked.columns:
        ranked["_confidence_order"] = 0
    else:
        ranked["_confidence_order"] = ranked["Tot_Present"]

    sort_cols = ["_qual_order", "_confidence_order"]
    ascending = [False, False]

    if "TotRank" in ranked.columns:
        sort_cols.append("TotRank")
        ascending.append(True)

    ranked = ranked.sort_values(sort_cols, ascending=ascending)
    ranked = ranked.drop(columns=["_qual_order", "_confidence_order"])
    return ranked.head(top_n)


def build_top_crossings_table(display_df):
    st.header("4. Top Crossings")
    st.caption(
        "Sorted primarily by Jenks natural-breaks class (Very High to Very Low), "
        "then by confidence (criteria present out of total), then by total rank "
        "as a tiebreaker. A high rank based on only 2 of 18 criteria is far less "
        "reliable than one based on 16 of 18, so class + confidence is emphasized "
        "over raw rank alone."
    )

    top_n = st.slider("Number of top crossings to display", 5, 50, 20)
    top_df = rank_top_crossings(display_df, top_n=top_n)

    show_cols = ["SADES_ID", "TotRank", "TotQual", "ConfTot"]
    for goal_key, qual_col in GOAL_QUAL_COL.items():
        if qual_col and qual_col in top_df.columns:
            show_cols.append(qual_col)

    show_cols = [c for c in show_cols if c in top_df.columns]
    st.dataframe(top_df[show_cols], use_container_width=True)

    if "SADES_ID" in top_df.columns and not top_df.empty:
        selected_id = st.selectbox(
            "Select a SADES_ID to view crossing photo(s)",
            top_df["SADES_ID"].astype(str).tolist(),
        )
        if st.button("Load photo(s) for selected crossing"):
            with st.spinner("Querying SADES photo service..."):
                photo_urls = gis_utils.query_sades_photo_urls(selected_id)
            if photo_urls:
                for url in photo_urls:
                    st.image(url, caption=f"SADES_ID {selected_id}")
            else:
                st.info(
                    "No photos found, or the SADES photo service could not be "
                    "reached / the field mapping is unverified. See gis_utils.py "
                    "PHOTO_LAYER_ID_FIELD for details."
                )

    return top_df


def build_downloads_section(display_df):
    st.header("5. Downloads")

    csv_bytes = display_df.to_csv(index=False).encode("utf-8")
    col_a, col_b = st.columns(2)

    col_a.download_button(
        "Download full results as CSV",
        data=csv_bytes,
        file_name="results_all.csv",
        mime="text/csv",
    )

    try:
        excel_bytes = build_excel_report(display_df)
        col_b.download_button(
            "Download Excel report",
            data=excel_bytes,
            file_name="report.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    except Exception as e:
        st.warning(f"Excel report could not be generated: {e}")


def main():
    st.title("Stream Crossing Prioritization Model")
    st.caption(
        "Adjust weightings, select a region or draw an area of interest, then run "
        "the model to view and download prioritized results."
    )

    base_params = load_default_params()
    params = build_weight_controls(base_params)

    town, county, huc12 = build_region_selector()

    st.divider()
    uploaded = st.file_uploader(
        "Upload input CSV (optional; uses bundled demo data/input/crossings.csv if not provided)",
        type="csv",
    )
    skip_validation = st.checkbox(
        "Validate input data before running (unchecked = skip validation, default)",
        value=False,
    )

    with st.expander("View current parameter configuration (JSON)"):
        st.json(params)

    if uploaded is not None:
        df = pd.read_csv(uploaded)
    else:
        df = load_default_input()
        if df is None:
            st.info(
                "No input CSV uploaded and no bundled demo file found at "
                "data/input/crossings.csv. Upload a CSV to proceed."
            )
            return
        st.caption(f"Using bundled demo dataset: {len(df)} records.")

    if skip_validation:
        validation_rules = params.get("validation", {})
        errors = validate_dataset(df, validation_rules)
        if errors:
            st.error("Validation failed. Uncheck validation or fix the input data.")
            for e in errors:
                st.write(f"- {e}")
            st.stop()

    drawn_ids = build_map_section(st.session_state.get("region_ids"))

    filtered_df = filter_by_region(df, town, county, huc12, drawn_ids)
    region_ids = set(filtered_df["SADES_ID"].astype(str)) if "SADES_ID" in filtered_df.columns else None
    st.session_state["region_ids"] = region_ids

    if (town or county or huc12 or drawn_ids is not None) and "SADES_ID" in df.columns:
        st.caption(f"Region filter active: {len(filtered_df)} of {len(df)} crossings selected.")

    if st.button("Run Analysis", type="primary"):
        run_df = filtered_df if not filtered_df.empty else df
        with st.spinner("Running model..."):
            result_df = run_analysis(run_df.copy(), params)

        sort_col = "TotRank" if "TotRank" in result_df.columns else None
        display_df = result_df.sort_values(sort_col) if sort_col else result_df

        st.session_state["result_df"] = display_df
        st.success(f"Analysis complete: {len(display_df)} crossings scored.")

    if "result_df" in st.session_state:
        display_df = st.session_state["result_df"]
        build_top_crossings_table(display_df)
        st.divider()
        with st.expander("View full results table"):
            st.dataframe(display_df, use_container_width=True)
        build_downloads_section(display_df)


if __name__ == "__main__":
    main()
