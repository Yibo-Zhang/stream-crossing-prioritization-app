"""Human-readable label construction for reporting.

Location in repo: src/utils/labels.py

The model keys everything on SADES_ID, which is unambiguous but not readable by
a reviewer looking at a spreadsheet. This module builds two plain-language
columns that are placed immediately after SADES_ID in every output sheet:

    Location    "<stream> at <road>, <town>"
    Landowner   road owner / maintaining authority (source field OWNERSHIP_)
    Town        municipality, as its own column
    SurveyDate  date of the SADES field assessment (source field AssessDate)

Town is also embedded in the Location label. It is emitted separately because a
label cannot be filtered or grouped: a reviewer working at a regional or
watershed scale needs to sort and filter by municipality, and a substring of
"Unnamed stream at Main St, Durham" does not support that. The column is built
with the same fallback chain used for the label, so the two always agree.

SurveyDate carries the assessment date through to the reporting sheets. A score
is only as current as the survey behind it, and the ARPA final report recommends
crossing reassessment every five years, so the reader needs the date next to the
rank rather than in the raw field dump.

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

# Ordered fallbacks for the survey date. AssessDate is the SADES assessment
# date and is populated for all 5,592 records in the demo extract; CreationDa is
# the feature creation date and is a weaker proxy, used only if AssessDate is
# absent from an input file.
SURVEY_DATE_FIELDS = ["AssessDate", "CreationDa"]

UNNAMED_STREAM_LABEL = "Unnamed stream"
UNNAMED_ROAD_LABEL = "Unnamed road"
INCLUDE_TOWN_IN_LOCATION = True

LOCATION_COLUMN = "Location"
LANDOWNER_COLUMN = "Landowner"
TOWN_COLUMN = "Town"
SURVEY_DATE_COLUMN = "SurveyDate"

# ISO 8601 (YYYY-MM-DD), the form AssessDate already uses in the demo extract.
# Kept explicit so a source file carrying a different order does not silently
# reorder day and month in the workbook.
SURVEY_DATE_FORMAT = "%Y-%m-%d"


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


def build_town(df):
    """Return the Town Series, using the same fallback chain as the label.

    SADES Town is populated for all 5,592 records in the demo extract and the
    NHDOT road-inventory TOWN_NAME for 5,247, so SADES is preferred and the road
    inventory is the fallback. The two disagree on capitalization
    ("East Kingston" against "EAST KINGSTON"); source capitalization is left as
    recorded, for the reason given above.
    """
    return _first_available(df, TOWN_NAME_FIELDS)


def build_survey_date(df):
    """Return the SurveyDate Series, parsed to a date.

    Values that do not parse are left missing rather than guessed at. The
    result is a date (not a timestamp), so the workbook shows 2023-06-14 rather
    than 2023-06-14 00:00:00.
    """
    raw = _first_available(df, SURVEY_DATE_FIELDS)
    parsed = pd.to_datetime(raw, format=SURVEY_DATE_FORMAT, errors="coerce")
    if parsed.notna().sum() == 0 and raw.notna().sum() > 0:
        # An input file using a different date order still yields a usable
        # column rather than an empty one.
        parsed = pd.to_datetime(raw, errors="coerce")
    return parsed.dt.date


def add_labels(df):
    """Add the reporting label columns to ``df`` in place and return it.

    Adds Location, Landowner, Town and SurveyDate. Town is overwritten with the
    resolved value rather than left as read, so that a record whose SADES Town
    is blank picks up the road-inventory TOWN_NAME instead of showing a gap.
    """
    df[LOCATION_COLUMN] = build_location(df)
    df[LANDOWNER_COLUMN] = build_landowner(df)
    df[TOWN_COLUMN] = build_town(df)
    df[SURVEY_DATE_COLUMN] = build_survey_date(df)
    return df
