"""
One-time conversion script: shapefiles -> lightweight GeoJSON.

Run this LOCALLY (not in the Streamlit app) wherever your original shapefiles
live. It reprojects each layer to EPSG:4326 (WGS84, required by folium/leaflet),
keeps ONLY the columns needed by the app plus geometry, and writes compact
GeoJSON files.

Usage:
    python convert_shapefiles_to_geojson.py

Edit SOURCE_DIR and OUTPUT_DIR below to match your local paths, then run.
After running, move (or point OUTPUT_DIR directly at) the four resulting
.geojson files into:

    stream-crossing-app/data/gis/

Required packages: geopandas, pyogrio (pip install geopandas pyogrio)
"""
from pathlib import Path
import geopandas as gpd

SOURCE_DIR = Path(r"C:\Users\ka1210\OneDrive - USNH\Desktop\Koorosh PhD research\NFWF\Code\Version 1.8\stream-crossing-prioritization-MeanSub\data\gis")   # <-- EDIT: folder containing your .shp files
OUTPUT_DIR = Path(r"C:\Users\ka1210\OneDrive - USNH\Desktop\Koorosh PhD research\NFWF\Code\Version 1.8\stream-crossing-prioritization-MeanSub\data\gis")      # <-- EDIT: where to write the .geojson files

LAYERS = [
    {
        "input": "New_Hampshire_Political_Boundaries.shp",
        "output": "New_Hampshire_Political_Boundaries.geojson",
        "keep_columns": ["name"],
    },
    {
        "input": "RPC_s_Regional_Planning_Commissions.shp",
        "output": "RPC_s_Regional_Planning_Commissions.geojson",
        "keep_columns": ["NAME"],
    },
    {
        "input": "SADES_Stream_Crossings_2021.shp",
        "output": "SADES_Stream_Crossings_2021.geojson",
        "keep_columns": ["SADES_ID"],
        "encoding": "cp1252",  # <-- Added fallback encoding for this specific layer
    },
    {
        "input": "HUC12_NH_Clipped.shp",
        "output": "HUC12_NH_Clipped.geojson",
        "keep_columns": ["HU_12_NAME"],
    },
]


def convert_layer(input_path, output_path, keep_columns, encoding=None):
    if not input_path.exists():
        print(f"  SKIPPED (not found): {input_path}")
        return

    # Pass the encoding parameter if it's specified in the dictionary
    try:
        gdf = gpd.read_file(input_path, encoding=encoding)
    except UnicodeDecodeError:
        # Secondary fallback if cp1252 still throws an error on a different layer
        print(f"  Encoding failed with standard setup. Trying alternative encoding 'latin1'...")
        gdf = gpd.read_file(input_path, encoding="latin1")

    if gdf.crs is None:
        print(f"  WARNING: {input_path.name} has no CRS defined; assuming EPSG:4326.")
        gdf = gdf.set_crs(epsg=4326)
    else:
        gdf = gdf.to_crs(epsg=4326)

    missing = [c for c in keep_columns if c not in gdf.columns]
    if missing:
        print(f"  WARNING: {input_path.name} is missing expected columns {missing}. "
              f"Available columns: {list(gdf.columns)}")

    available_keep = [c for c in keep_columns if c in gdf.columns]
    gdf = gdf[available_keep + ["geometry"]].copy()

    output_path.parent.mkdir(parents=True, exist_ok=True)
    gdf.to_file(output_path, driver="GeoJSON")

    size_kb = output_path.stat().st_size / 1024
    print(f"  OK: {output_path.name} written ({len(gdf)} features, {size_kb:.1f} KB)")


def main():
    print(f"Reading shapefiles from: {SOURCE_DIR.resolve()}")
    print(f"Writing GeoJSON to:      {OUTPUT_DIR.resolve()}\n")

    for layer in LAYERS:
        input_path = SOURCE_DIR / layer["input"]
        output_path = OUTPUT_DIR / layer["output"]
        encoding = layer.get("encoding", None) # Default to None (let geopandas auto-detect / use UTF-8)
        
        print(f"Converting {layer['input']} -> {layer['output']}")
        convert_layer(input_path, output_path, layer["keep_columns"], encoding=encoding)

    print("\nDone. Move the .geojson files above into data/gis/ in the app repo.")


if __name__ == "__main__":
    main()