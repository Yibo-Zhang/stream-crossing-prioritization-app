"""Human-readable label construction for reporting.

Location in repo: src/utils/labels.py

The model keys everything on SADES_ID, which is unambiguous but not readable by
a reviewer looking at a spreadsheet. This module builds two plain-language
columns that are placed immediately after SADES_ID in every output sheet:

    Location   "<stream> at <road>, <town>"
    Landowner  road owner / maintaining authority (source field OWNERSHIP_)

Field completeness in the 5,592-record demo extract (data/input/crossings.csv):

    Town         5592 / 5592     (used as the town component)
    RoadNameF    5085 / 5592     (preferred road component)
    STREET       5247 / 5592     (road fallback, NHDOT road inventory join)
    RoadNameA     348 / 5592     (second road fallback, alternate name)
    StreamName   2121 / 5592     (stream component)
    OWNERSHIP_   5244 / 5592     (Landowner)

StreamName is populated for roughly 38 percent of records, so the stream
component falls back to UNNAMED_STREAM_LABEL rather than being left blank. The
town component is appended because Town is the only fully populated field of the
three and because road names such as "Main St" repeat across municipalities.
Set INCLUDE_TOWN_IN_LOCATION to False for a bare "stream at road" label.
"""
import re

import pandas as pd

# 313 of the 2,121 populated StreamName values in the demo extract begin with an
# NHDES assessment-unit identifier, for example
# "NHRIV600030606-04 BERRYS RIVER - UNNAMED BROOK". The identifier is stripped
# from the display label; it remains available in the AUIDs field.
AU_ID_PREFIX = re.compile(r"^NH[A-Z]{3}\d[\w.-]*\s+")

# Source capitalization is left as recorded. SADES and the NHDOT road inventory
# disagree on case ("EAST KINGSTON" against "East Kingston"), and rewriting the
# source text would make a label harder to trace back to the input record.

# Ordered fallbacks. The first field with a usable value wins.
STREAM_NAME_FIELDS = ["StreamName"]
ROAD_NAME_FIELDS = ["RoadNameF", "STREET", "RoadNameA"]
TOWN_NAME_FIELDS = ["Town", "TOWN_NAME"]

LANDOWNER_SOURCE_FIELD = "OWNERSHIP_"

UNNAMED_STREAM_LABEL = "Unnamed stream"
UNNAMED_ROAD_LABEL = "Unnamed road"
INCLUDE_TOWN_IN_LOCATION = True

LOCATION_COLUMN = "Location"
LANDOWNER_COLUMN = "Landowner"


def _first_available(df, fields, fallback=None):
    """Return a Series holding, per row, the first non-blank value across
    ``fields``. Values are stripped; empty strings count as missing."""
    result = pd.Series(pd.NA, index=df.index, dtype="object")
    for field in fields:
        if field not in df.columns:
            continue
        candidate = df[field].astype("object").where(df[field].notna())
        candidate = candidate.map(
            lambda v: v.strip() if isinstance(v, str) else v
        )
        candidate = candidate.where(candidate.astype(str).str.strip() != "")
        result = result.fillna(candidate)
    if fallback is not None:
        result = result.fillna(fallback)
    return result


def _strip_au_id(value):
    """Remove a leading NHDES assessment-unit identifier from a stream name."""
    if not isinstance(value, str):
        return value
    cleaned = AU_ID_PREFIX.sub("", value).strip()
    return cleaned or value


def build_location(df):
    """Return the Location label Series for ``df``."""
    stream = _first_available(df, STREAM_NAME_FIELDS)
    stream = stream.map(_strip_au_id).fillna(UNNAMED_STREAM_LABEL)
    road = _first_available(df, ROAD_NAME_FIELDS, fallback=UNNAMED_ROAD_LABEL)

    location = stream.astype(str) + " at " + road.astype(str)

    if INCLUDE_TOWN_IN_LOCATION:
        town = _first_available(df, TOWN_NAME_FIELDS)
        has_town = town.notna()
        location = location.where(~has_town, location + ", " + town.astype(str))

    return location


def build_landowner(df):
    """Return the Landowner Series, copied from OWNERSHIP_ where present."""
    if LANDOWNER_SOURCE_FIELD not in df.columns:
        return pd.Series(pd.NA, index=df.index, dtype="object")
    return df[LANDOWNER_SOURCE_FIELD]


def add_labels(df):
    """Add the Location and Landowner columns to ``df`` in place and return it."""
    df[LOCATION_COLUMN] = build_location(df)
    df[LANDOWNER_COLUMN] = build_landowner(df)
    return df
