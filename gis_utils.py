
"""GIS utilities: load boundary/HUC12/point GeoJSON layers, spatial filtering,
and SADES photo lookup.

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

GIS_DIR = Path(__file__).parent / "data" / "gis"

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


def build_map(boundaries_gdf=None, points_gdf=None, highlight_ids=None, results_df=None, score_col="TotQual"):
    import folium
    from folium.plugins import Draw

    if points_gdf is not None and not points_gdf.empty:
        bounds = points_gdf.total_bounds
        center = [(bounds[1] + bounds[3]) / 2, (bounds[0] + bounds[2]) / 2]
    else:
        center = [43.6, -71.5]  # roughly central New Hampshire

    m = folium.Map(location=center, zoom_start=9, tiles="CartoDB positron")

    if boundaries_gdf is not None and not boundaries_gdf.empty:
        folium.GeoJson(
            boundaries_gdf.to_json(),
            name="Boundaries",
            style_function=lambda x: {"color": "#555555", "weight": 1, "fillOpacity": 0.03},
        ).add_to(m)

    qual_colors = {
        "Very High": "#d73027",
        "High": "#fc8d59",
        "Moderate": "#fee08b",
        "Low": "#91cf60",
        "Very Low": "#1a9850",
    }

    if points_gdf is not None and not points_gdf.empty:
        score_lookup = {}
        if results_df is not None and score_col in results_df.columns and SADES_ID_FIELD in results_df.columns:
            score_lookup = dict(zip(results_df[SADES_ID_FIELD].astype(str), results_df[score_col]))

        for _, row in points_gdf.iterrows():
            sid = str(row.get(SADES_ID_FIELD, ""))
            geom = row.geometry
            if geom is None:
                continue
            qual = score_lookup.get(sid)
            color = qual_colors.get(qual, "#3186cc")
            in_selection = highlight_ids is None or sid in highlight_ids
            folium.CircleMarker(
                location=[geom.y, geom.x],
                radius=5 if in_selection else 3,
                color=color,
                fill=True,
                fill_color=color,
                fill_opacity=0.9 if in_selection else 0.25,
                opacity=0.9 if in_selection else 0.25,
                popup=folium.Popup(f"SADES_ID: {sid}", max_width=200),
            ).add_to(m)

    Draw(
        export=False,
        draw_options={"polyline": False, "circle": False, "marker": False, "circlemarker": False},
        edit_options={"edit": True},
    ).add_to(m)

    return m
