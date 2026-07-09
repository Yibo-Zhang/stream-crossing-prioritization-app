
"""GIS utilities: load boundary/HUC12/point GeoJSON layers, spatial filtering,
and SADES photo lookup.

Location in repo: src/utils/gis_utils.py

Expected files in data/gis/ (produced by convert_shapefiles_to_geojson.py):

    data/gis/New_Hampshire_Political_Boundaries.geojson   (town boundaries; field "name")
    data/gis/RPC_s_Regional_Planning_Commissions.geojson  (county/RPC boundaries; field "NAME")
    data/gis/SADES_Stream_Crossings_2021.geojson          (SADES crossing points; field "SADES_ID")
    data/gis/HUC12_NH_Clipped.geojson                     (HUC12 watersheds; field "HU_12_NAME")

These are loaded with geopandas (still required for the spatial join / "within"
predicate), but reading pre-trimmed GeoJSON is much lighter on memory than
reading full shapefiles with all original attribute columns.
"""
from pathlib import Path

import geopandas as gpd
import pandas as pd
import requests
import streamlit as st
from shapely.geometry import shape

# This file now lives at src/utils/gis_utils.py, so the repo root is three
# levels up: utils/ -> src/ -> repo root.
GIS_DIR = Path(__file__).resolve().parents[2] / "data" / "gis"

TOWN_BOUNDARY_PATH = GIS_DIR / "New_Hampshire_Political_Boundaries.geojson"
COUNTY_BOUNDARY_PATH = GIS_DIR / "RPC_s_Regional_Planning_Commissions.geojson"
HUC12_BOUNDARY_PATH = GIS_DIR / "HUC12_NH_Clipped.geojson"
SADES_POINTS_PATH = GIS_DIR / "SADES_Stream_Crossings_2021.geojson"

TOWN_NAME_FIELD = "name"
COUNTY_NAME_FIELD = "NAME"
HUC12_NAME_FIELD = "HU_12_NAME"
SADES_ID_FIELD = "SADES_ID"

# ArcGIS REST endpoint for SADES stream crossing photos (public feature layer).
# Field name confirmed by user (2026-07-09) as "SADES_ID". This tool could not
# independently verify the live service schema (the metadata endpoint was
# unreachable from this environment), so this relies on that confirmation.
PHOTO_LAYER_URL = (
    "https://services3.arcgis.com/mB6GMjOL4lVKAyZO/ArcGIS/rest/services/"
    "SADES_Stream_Crossing_Photos_PUBLIC/FeatureServer/0"
)
PHOTO_LAYER_ID_FIELD = "SADES_ID"  # confirmed by user


def _load_geojson(path):
    if not path.exists():
        return None
    gdf = gpd.read_file(path)
    if gdf.crs is None:
        gdf = gdf.set_crs(epsg=4326)
    else:
        gdf = gdf.to_crs(epsg=4326)
    return gdf


@st.cache_resource
def load_town_boundaries():
    return _load_geojson(TOWN_BOUNDARY_PATH)


@st.cache_resource
def load_county_boundaries():
    return _load_geojson(COUNTY_BOUNDARY_PATH)


@st.cache_resource
def load_huc12_boundaries():
    return _load_geojson(HUC12_BOUNDARY_PATH)


@st.cache_resource
def load_sades_points():
    return _load_geojson(SADES_POINTS_PATH)


def get_town_names():
    gdf = load_town_boundaries()
    if gdf is None or TOWN_NAME_FIELD not in gdf.columns:
        return []
    return sorted(gdf[TOWN_NAME_FIELD].dropna().unique().tolist())


def get_county_names():
    gdf = load_county_boundaries()
    if gdf is None or COUNTY_NAME_FIELD not in gdf.columns:
        return []
    return sorted(gdf[COUNTY_NAME_FIELD].dropna().unique().tolist())


def get_huc12_names():
    gdf = load_huc12_boundaries()
    if gdf is None or HUC12_NAME_FIELD not in gdf.columns:
        return []
    return sorted(gdf[HUC12_NAME_FIELD].dropna().unique().tolist())


def _ids_within_polygon(points_gdf, polygon_gdf):
    if points_gdf is None or polygon_gdf is None or polygon_gdf.empty:
        return None
    joined = gpd.sjoin(points_gdf, polygon_gdf, how="inner", predicate="within")
    if SADES_ID_FIELD not in joined.columns:
        return None
    return joined[SADES_ID_FIELD].dropna().astype(str).unique().tolist()


def get_ids_in_town(town_name):
    boundaries = load_town_boundaries()
    points = load_sades_points()
    if boundaries is None or points is None:
        return None
    selected = boundaries[boundaries[TOWN_NAME_FIELD] == town_name]
    return _ids_within_polygon(points, selected)


def get_ids_in_county(county_name):
    boundaries = load_county_boundaries()
    points = load_sades_points()
    if boundaries is None or points is None:
        return None
    selected = boundaries[boundaries[COUNTY_NAME_FIELD] == county_name]
    return _ids_within_polygon(points, selected)


def get_ids_in_huc12(huc12_name):
    boundaries = load_huc12_boundaries()
    points = load_sades_points()
    if boundaries is None or points is None:
        return None
    selected = boundaries[boundaries[HUC12_NAME_FIELD] == huc12_name]
    return _ids_within_polygon(points, selected)


def get_ids_in_drawn_polygon(geojson_geometry):
    """geojson_geometry: a GeoJSON geometry dict, e.g. from streamlit-folium Draw output."""
    points = load_sades_points()
    if points is None or geojson_geometry is None:
        return None
    polygon = shape(geojson_geometry)
    polygon_gdf = gpd.GeoDataFrame({"geometry": [polygon]}, crs="EPSG:4326")
    return _ids_within_polygon(points, polygon_gdf)


def query_sades_photo_urls(sades_id, timeout=10):
    """Query the SADES photo FeatureServer for a given SADES_ID and return
    a list of direct attachment image URLs.

    Two-step ArcGIS REST workflow:
    1. /query to find the objectId(s) matching PHOTO_LAYER_ID_FIELD == sades_id
    2. /queryAttachments to get attachment metadata for those objectIds
    3. Build attachment URLs as {layer_url}/{objectId}/attachments/{attachmentId}
    """
    try:
        query_url = f"{PHOTO_LAYER_URL}/query"
        params = {
            "where": f"{PHOTO_LAYER_ID_FIELD}='{sades_id}'",
            "outFields": "OBJECTID",
            "returnGeometry": "false",
            "f": "json",
        }
        resp = requests.get(query_url, params=params, timeout=timeout)
        resp.raise_for_status()
        features = resp.json().get("features", [])
        object_ids = [f["attributes"]["OBJECTID"] for f in features if "attributes" in f]
        if not object_ids:
            return []

        attach_url = f"{PHOTO_LAYER_URL}/queryAttachments"
        attach_params = {
            "objectIds": ",".join(str(oid) for oid in object_ids),
            "f": "json",
        }
        attach_resp = requests.get(attach_url, params=attach_params, timeout=timeout)
        attach_resp.raise_for_status()
        attachment_groups = attach_resp.json().get("attachmentGroups", [])

        urls = []
        for group in attachment_groups:
            parent_oid = group.get("parentObjectId")
            for att in group.get("attachmentInfos", []):
                att_id = att.get("id")
                urls.append(f"{PHOTO_LAYER_URL}/{parent_oid}/attachments/{att_id}")
        return urls
    except Exception:
        return []



# --------------------------------------------------------------------------- #
# Selection helpers (single-method region filtering)
# --------------------------------------------------------------------------- #

def get_ids_for_selection(method, value):
    """SADES_IDs for a single chosen method ('town'|'county'|'huc12') and value.
    None for other methods, a missing value, or missing layers."""
    if not value:
        return None
    if method == "town":
        return get_ids_in_town(value)
    if method == "county":
        return get_ids_in_county(value)
    if method == "huc12":
        return get_ids_in_huc12(value)
    return None


def get_boundary_feature(method, value):
    """Single boundary feature (GeoDataFrame) for the chosen method/value,
    used to outline and zoom the map. None if unavailable."""
    if not value:
        return None
    if method == "town":
        gdf, field = load_town_boundaries(), TOWN_NAME_FIELD
    elif method == "county":
        gdf, field = load_county_boundaries(), COUNTY_NAME_FIELD
    elif method == "huc12":
        gdf, field = load_huc12_boundaries(), HUC12_NAME_FIELD
    else:
        return None
    if gdf is None or field not in gdf.columns:
        return None
    selected = gdf[gdf[field] == value]
    return selected if not selected.empty else None


# --------------------------------------------------------------------------- #
# Map (display only, single GeoJSON layer)
# --------------------------------------------------------------------------- #

# Shared diverging priority palette (matches the table styling in app.py).
QUAL_MAP_COLORS = {
    "Very High": "#d73027",
    "High": "#fc8d59",
    "Moderate": "#fee08b",
    "Low": "#91cf60",
    "Very Low": "#1a9850",
}
UNSCORED_COLOR = "#3186cc"


def build_map(points_gdf=None, active_boundary_gdf=None, highlight_ids=None,
              results_df=None, score_col="TotQual"):
    """Display-only folium map.

    Only crossings present in ``results_df`` (i.e. the crossings the model
    actually scored on the last run) are drawn, instead of the full SADES
    inventory. Each point is colored by its Jenks priority class
    (QUAL_MAP_COLORS), giving an unambiguous color mapping for the crossings
    that were run. UNSCORED_COLOR is retained only as a defensive fallback
    in case a row in results_df is missing a score.

    All crossing points are added as ONE GeoJSON layer (with per-feature style
    baked into feature properties), rather than one folium object per point.
    This is the key performance change: folium builds each individual marker
    through server-side template compilation, which is slow for thousands of
    points, whereas a single GeoJSON layer is rendered client-side by Leaflet.
    prefer_canvas=True further speeds Leaflet drawing.
    """
    import folium

    highlight = set(highlight_ids) if highlight_ids is not None else None

    if active_boundary_gdf is not None and not active_boundary_gdf.empty:
        b = active_boundary_gdf.total_bounds
        center = [(b[1] + b[3]) / 2, (b[0] + b[2]) / 2]
    elif points_gdf is not None and not points_gdf.empty:
        b = points_gdf.total_bounds
        center = [(b[1] + b[3]) / 2, (b[0] + b[2]) / 2]
    else:
        center = [43.6, -71.5]  # roughly central New Hampshire

    m = folium.Map(location=center, zoom_start=9, tiles="CartoDB positron",
                   control_scale=True, prefer_canvas=True)

    if active_boundary_gdf is not None and not active_boundary_gdf.empty:
        folium.GeoJson(
            active_boundary_gdf.to_json(),
            name="Selected area",
            style_function=lambda x: {
                "color": "#14606C", "weight": 2,
                "fill": True, "fillColor": "#1F8A9B", "fillOpacity": 0.06,
            },
        ).add_to(m)

    # Only draw crossings the model actually ran on, i.e. rows present in
    # results_df. This satisfies "the map should only show crossings that
    # the model ran" instead of showing the full unfiltered SADES inventory.
    if (points_gdf is not None and not points_gdf.empty
            and SADES_ID_FIELD in points_gdf.columns
            and results_df is not None and SADES_ID_FIELD in results_df.columns):
        ran_ids = set(results_df[SADES_ID_FIELD].astype(str))
        gdf = points_gdf[[SADES_ID_FIELD, "geometry"]].copy()
        gdf = gdf[gdf.geometry.notna() & ~gdf.geometry.is_empty]
        gdf[SADES_ID_FIELD] = gdf[SADES_ID_FIELD].astype(str)
        gdf = gdf[gdf[SADES_ID_FIELD].isin(ran_ids)]

        if not gdf.empty:
            if score_col in results_df.columns:
                score_lookup = dict(zip(results_df[SADES_ID_FIELD].astype(str),
                                         results_df[score_col]))
                gdf["priority"] = gdf[SADES_ID_FIELD].map(score_lookup)
            else:
                gdf["priority"] = None

            gdf["color"] = gdf["priority"].map(QUAL_MAP_COLORS).fillna(UNSCORED_COLOR)
            if highlight is None:
                gdf["opacity"] = 0.9
            else:
                gdf["opacity"] = gdf[SADES_ID_FIELD].isin(highlight).map({True: 0.9, False: 0.18})
            gdf["label"] = gdf.apply(
                lambda r: f"SADES_ID {r[SADES_ID_FIELD]}"
                          + (f" ({r['priority']})" if pd.notna(r["priority"]) else ""),
                axis=1,
            )

            folium.GeoJson(
                gdf.to_json(),
                name="Crossings",
                marker=folium.CircleMarker(radius=6, weight=1, fill=True),
                style_function=lambda feat: {
                    "color": feat["properties"]["color"],
                    "fillColor": feat["properties"]["color"],
                    "fillOpacity": feat["properties"]["opacity"],
                    "opacity": feat["properties"]["opacity"],
                },
                tooltip=folium.GeoJsonTooltip(fields=["label"], labels=False),
            ).add_to(m)

    if active_boundary_gdf is not None and not active_boundary_gdf.empty:
        b = active_boundary_gdf.total_bounds
        m.fit_bounds([[b[1], b[0]], [b[3], b[2]]])

    return m
