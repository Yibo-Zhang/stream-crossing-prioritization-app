"""Input data validation utilities.

Location in repo: src/utils/validation.py

Null-coded categorical values
-----------------------------
The SADES assessment protocol records several categorical fields with explicit
"not scored" markers rather than leaving the cell blank. In the 5,592-record
extract in data/input/crossings.csv these are:

    GC_Score    N/A Score - Wetland (1,726), N/A Score - Surface (318),
                No Score - Not Surveyable (183), No Score - Private (115),
                N/A Score - Tidal (68), No Score - Other (1),
                N/A Score - Drainage (1)
    AOP_Score   No Score - Private (100), No Score - Not Surveyable (75),
                N/A Score - Drainage (1)
    UsUndermin, DsUndermin, OutScour, UsBankArmo, DsBankArmo   Unknown

These markers mean "this criterion could not be scored at this crossing", which
is the same information content as a blank cell. Before this revision they were
neither listed in the params.json enum nor recognized as null, so
validate_dataset reported them as invalid values and src/model.py exited. The
only way to run the model was --skip-validation, which disabled every other
check at the same time, including checks on fields that genuinely drive scores.

The approach implemented here is the explicit-list approach:

  1. A named list of null-coded values is declared in configs/params.json.
     Values on that list are converted to NaN by apply_null_codes and are not
     reported as validation errors.
  2. Any categorical value that is neither in the field's enum nor on the
     null-coded list is still an error and still halts the run. A new marker
     appearing in a future SADES export therefore has to be reviewed and added
     to the list deliberately, rather than being silently converted to null.

This keeps the guarantee that unreviewed values cannot enter the model, which a
blanket downgrade of errors to warnings would not provide.

Scoring relevance
-----------------
Every field carrying an enum rule in params.json feeds a criterion score, so
every enum rule defaults to severity "error". A rule may set
``"severity": "warning"`` to report without halting; this is intended for
descriptive fields added to the rule set that do not drive a score.

Comparison keys
---------------
Enum comparison is done on a canonical key, not on the raw string. A value that
parses as an integral number is compared as that integer, so the FUNCT_SYST
domain [0..7] declared in params.json matches the float 7.0 that pandas
produces when the column contains blanks. Before this revision every non-null
FUNCT_SYST value in the demo extract (5,247 of 5,592 records) was reported as
invalid for this reason alone.
"""
import math

import numpy as np
import pandas as pd

# Fallback list used when configs/params.json does not declare "null_values".
# Kept in sync with the markers observed in the SADES extract. "None" is
# deliberately absent: it is a valid, scored category in UsUndermin, DsUndermin,
# OutScour, UsBankEros and DsBankEros, where it means "no undermining, scour or
# erosion observed" and maps to a score of 0.
DEFAULT_NULL_VALUES = (
    "N/A Score - Wetland",
    "N/A Score - Surface",
    "N/A Score - Tidal",
    "N/A Score - Drainage",
    "No Score - Not Surveyable",
    "No Score - Private",
    "No Score - Other",
    "Unknown",
)

ERROR = "error"
WARNING = "warning"


# --------------------------------------------------------------------------- #
# Comparison keys
# --------------------------------------------------------------------------- #

def _is_missing(value):
    """True for None, NaN, NaT and pd.NA. Scalars only."""
    if value is None or value is pd.NA:
        return True
    if isinstance(value, float) and math.isnan(value):
        return True
    try:
        result = pd.isna(value)
    except (TypeError, ValueError):
        return False
    return bool(result) if np.isscalar(result) else False


def comparison_key(value, case_sensitive=False):
    """Return the canonical comparison key for one cell or one allowed value.

    A value that is numerically integral is keyed as its integer string, so
    that 7, 7.0, "7" and "7.0" all compare equal. This is what makes the
    integer FUNCT_SYST enum in params.json match the float column pandas
    produces when the source CSV has blank cells.

    Any other value is keyed as its stripped string form, lower-cased unless
    ``case_sensitive`` is set. Missing values return None and are never
    compared.
    """
    if _is_missing(value):
        return None

    if isinstance(value, bool):
        # Excluded from the numeric branch on purpose: bool is a subclass of
        # int in Python, and keying True as "1" would let a boolean column
        # match a numeric enum by accident.
        return str(value) if case_sensitive else str(value).lower()

    if isinstance(value, (int, float, np.integer, np.floating)):
        number = float(value)
        return str(int(number)) if number.is_integer() else repr(number)

    text = str(value).strip()
    if not text:
        return None

    try:
        number = float(text)
    except ValueError:
        pass
    else:
        return str(int(number)) if number.is_integer() else repr(number)

    return text if case_sensitive else text.lower()


def _key_series(series, case_sensitive=False):
    """Vectorized comparison_key over a Series, preserving the index."""
    return series.map(lambda v: comparison_key(v, case_sensitive))


# --------------------------------------------------------------------------- #
# Null-coded value resolution
# --------------------------------------------------------------------------- #

def resolve_null_values(rules, global_null_values=None):
    """Return the null-coded values that apply to one field.

    ``rules`` is that field's entry in params['validation']. The field-level
    "null_values" list, when present, is added to the global list rather than
    replacing it, so a field can accept an extra marker without restating the
    shared ones. A field may set ``"inherit_null_values": false`` to opt out of
    the global list entirely.
    """
    values = []
    if rules.get("inherit_null_values", True):
        source = DEFAULT_NULL_VALUES if global_null_values is None else global_null_values
        values.extend(source)
    values.extend(rules.get("null_values", []))
    return values


# --------------------------------------------------------------------------- #
# Field-level checks
# --------------------------------------------------------------------------- #

def validate_schema(df, required_fields):
    """Raise ValueError if any of ``required_fields`` is absent from ``df``.

    Parameters
    ----------
    df : pd.DataFrame
        Input dataframe to validate.
    required_fields : list of str
        Column names that must be present.

    Raises
    ------
    ValueError
        If any required field is missing.
    """
    missing = [f for f in required_fields if f not in df.columns]
    if missing:
        raise ValueError(f"Missing required fields: {missing}")


def validate_enum_field(df, field, valid_values, case_sensitive=False,
                        null_values=None):
    """Return the values of ``field`` that are neither valid nor null-coded.

    Parameters
    ----------
    df : pd.DataFrame
        Input dataframe.
    field : str
        Field name to validate. A field absent from ``df`` returns [].
    valid_values : list
        Allowed values for this field.
    case_sensitive : bool, default False
        Whether comparison is case-sensitive.
    null_values : list, optional
        Values treated as an explicit "not scored" marker. These are reported
        by find_null_coded_values and converted to NaN by apply_null_codes;
        they are never returned here.

    Returns
    -------
    list
        The distinct offending values in their original form, so the message
        shown to the user names each value exactly as it appears in the file.
    """
    if field not in df.columns:
        return []

    series = df[field].dropna()
    if series.empty:
        return []

    allowed = {comparison_key(v, case_sensitive) for v in valid_values}
    allowed |= {comparison_key(v, case_sensitive) for v in (null_values or [])}
    allowed.discard(None)

    keys = _key_series(series, case_sensitive)
    offending = series[~keys.isin(allowed) & keys.notna()]
    return list(dict.fromkeys(offending.tolist()))


def find_null_coded_values(df, field, null_values, case_sensitive=False):
    """Return {original value: row count} for the null-coded values present.

    Used to report what apply_null_codes converted, so a run states plainly how
    many records lost a criterion to a "not scored" marker rather than to a
    blank cell.
    """
    if field not in df.columns or not null_values:
        return {}

    series = df[field].dropna()
    if series.empty:
        return {}

    null_keys = {comparison_key(v, case_sensitive) for v in null_values}
    null_keys.discard(None)

    keys = _key_series(series, case_sensitive)
    hits = series[keys.isin(null_keys)]
    if hits.empty:
        return {}
    return {value: int(count) for value, count in hits.value_counts().items()}


def find_unscored_values(df, field, score_map, null_values=None,
                         case_sensitive=False):
    """Return {value: count} for values that are present but have no score.

    A field can pass the enum check and still contribute nothing, if the value
    is listed in the enum but absent from the score map that consumes it.
    Series.map returns NaN for an unmapped key, so the criterion silently
    becomes a data gap. This surfaced in the demo extract as StructSed:
    'Entirely Full' occurs 22 times and 'High', the only top-severity key in
    the sediment fill map, occurs zero times.

    Null-coded values are excluded, since those are meant to become NaN.
    """
    if field not in df.columns or not score_map:
        return {}

    series = df[field].dropna()
    if series.empty:
        return {}

    mapped = {comparison_key(k, case_sensitive) for k in score_map}
    mapped |= {comparison_key(v, case_sensitive) for v in (null_values or [])}
    mapped.discard(None)

    keys = _key_series(series, case_sensitive)
    unscored = series[~keys.isin(mapped) & keys.notna()]
    if unscored.empty:
        return {}
    return {value: int(count) for value, count in unscored.value_counts().items()}


def validate_numeric_range(df, field, min_val=None, max_val=None):
    """Return the subset of rows whose ``field`` value falls outside the range.

    Missing and non-numeric values are ignored: a blank AADT is a data gap for
    the confidence count to report, not a range violation.

    The mask is built on ``df.index`` rather than on a fresh RangeIndex. A
    frame filtered by town, county or HUC12 in app.py keeps the original index,
    and a mask on a default index would misalign against it.
    """
    if field not in df.columns:
        return pd.DataFrame()

    series = pd.to_numeric(df[field], errors="coerce")
    mask = pd.Series(True, index=df.index)

    if min_val is not None:
        mask &= (series >= min_val) | series.isna()
    if max_val is not None:
        mask &= (series <= max_val) | series.isna()

    return df[~mask]


# --------------------------------------------------------------------------- #
# Dataset-level entry points
# --------------------------------------------------------------------------- #

class ValidationReport:
    """Outcome of a validation pass.

    Attributes
    ----------
    errors : list of str
        Findings that halt the run. Non-empty means the input carries a
        categorical value that has never been reviewed, so the model cannot
        know whether to score it or to drop it.
    warnings : list of str
        Findings reported without halting, from rules marked
        ``"severity": "warning"``.
    null_coded : dict
        {field: {value: count}} for the null-coded markers found, so the size
        of the data gap introduced by conversion is visible.
    """

    def __init__(self, errors=None, warnings=None, null_coded=None):
        """Store the three result categories, copied so the caller cannot
        mutate the report after the fact."""
        self.errors = list(errors or [])
        self.warnings = list(warnings or [])
        self.null_coded = dict(null_coded or {})

    @property
    def ok(self):
        """True when the run may proceed, that is when there are no errors.

        Warnings and null-coded conversions do not affect this: both are
        reported outcomes, not reasons to stop.
        """
        return not self.errors

    @property
    def null_coded_total(self):
        """Total rows across every field that carried a null-coded marker.

        A single row can be counted more than once if two of its fields both
        carried a marker, which is the intended reading: the figure counts
        criterion-level data gaps, not crossings.
        """
        return sum(sum(counts.values()) for counts in self.null_coded.values())

    def format_lines(self):
        """Return the report as display lines, errors first."""
        lines = [f"[error] {message}" for message in self.errors]
        lines += [f"[warning] {message}" for message in self.warnings]
        for field, counts in sorted(self.null_coded.items()):
            detail = ", ".join(
                f"{value} ({count})"
                for value, count in sorted(counts.items(), key=lambda kv: -kv[1])
            )
            lines.append(f"[null-coded] {field}: {detail}")
        return lines

    def __bool__(self):
        """Allow ``if report:`` as shorthand for ``if report.ok:``."""
        return self.ok


def validate_dataset_report(df, validation_rules, null_values=None,
                            score_maps=None):
    """Validate ``df`` against ``validation_rules``; return a ValidationReport.

    Parameters
    ----------
    df : pd.DataFrame
        Input dataframe to validate.
    validation_rules : dict
        params['validation'].
    null_values : list, optional
        params['null_values']. DEFAULT_NULL_VALUES is used when omitted.
    score_maps : dict, optional
        params['score_maps']. When supplied, a rule that names its consuming
        map with ``"score_map": "<name>"`` also gets the coverage check from
        find_unscored_values, reported as a warning rather than an error: an
        unscored value degrades one criterion to missing, which the confidence
        count already reflects, so it does not justify halting a run.

    Notes
    -----
    An unrecognized categorical value produces an error naming both the value
    and the two ways to resolve it, because the resolution is a judgement the
    model cannot make: a new marker meaning "not scored" belongs on the
    null_values list, whereas a new real category belongs in the field's enum
    and needs a matching entry in the relevant score map.
    """
    errors, warnings, null_coded = [], [], {}

    for field, rules in validation_rules.items():
        if field not in df.columns:
            continue

        severity = rules.get("severity", ERROR)
        sink = errors if severity == ERROR else warnings

        if "enum" in rules:
            case_sensitive = rules.get("case_sensitive", False)
            field_nulls = resolve_null_values(rules, null_values)

            found = find_null_coded_values(df, field, field_nulls, case_sensitive)
            if found:
                null_coded[field] = found

            invalid = validate_enum_field(df, field, rules["enum"],
                                          case_sensitive, field_nulls)
            if invalid:
                sink.append(
                    f"{field} has unrecognized values: {invalid}. "
                    f"Add each value to params.json under validation.{field}."
                    "null_values if it marks a crossing that could not be "
                    f"scored, or to validation.{field}.enum with a matching "
                    "score_maps entry if it is a real category."
                )

            map_name = rules.get("score_map")
            if score_maps and map_name:
                unscored = find_unscored_values(
                    df, field, score_maps.get(map_name, {}), field_nulls,
                    case_sensitive)
                if unscored:
                    detail = ", ".join(f"{value} ({count} records)"
                                       for value, count in unscored.items())
                    warnings.append(
                        f"{field} has values with no entry in score_maps."
                        f"{map_name}: {detail}. These records score as missing "
                        "for this criterion. Add the value to the score map to "
                        "score it, or to null_values to record it as a "
                        "deliberate data gap."
                    )

        if "range" in rules:
            min_val, max_val = rules["range"]
            out_of_range = validate_numeric_range(df, field, min_val, max_val)
            if len(out_of_range) > 0:
                sink.append(
                    f"{field} has {len(out_of_range)} values outside range "
                    f"[{min_val}, {max_val}]"
                )

    return ValidationReport(errors, warnings, null_coded)


def validate_dataset(df, validation_rules, null_values=None):
    """Return the list of blocking validation messages for ``df``.

    Thin wrapper over validate_dataset_report for callers that only need the
    error list. An empty list means the run may proceed.
    """
    return validate_dataset_report(df, validation_rules, null_values).errors


def canonicalize_enum_values(df, validation_rules, copy=True):
    """Use the declared spelling/type for values accepted by enum validation.

    Scoring uses exact keys, whereas validation accepts case, whitespace and
    integral-number variants. Leave missing and unrecognized values unchanged;
    this is not a replacement for validation or null-code conversion.
    """
    out = df.copy() if copy else df
    for field, rules in validation_rules.items():
        if field not in out.columns or "enum" not in rules:
            continue
        case_sensitive = rules.get("case_sensitive", False)
        canonical = {
            comparison_key(value, case_sensitive): value for value in rules["enum"]
        }
        canonical.pop(None, None)
        out[field] = out[field].map(
            lambda value: canonical.get(comparison_key(value, case_sensitive), value)
        )
    return out


def apply_null_codes(df, validation_rules, null_values=None, copy=True):
    """Convert null-coded categorical markers to NaN.

    Returns
    -------
    (pd.DataFrame, dict)
        The converted frame, and {field: {value: count}} describing what was
        converted.

    Notes
    -----
    Run after validation passes, so a marker is only converted once it is known
    to be on the reviewed list. Conversion is to np.nan rather than pd.NA to
    match the missing-value sentinel the goal modules test with pd.notna and
    the sentinel Series.map produces for an unmapped key.

    Only fields carrying an enum rule are touched. Numeric and free-text fields
    are left exactly as read.
    """
    out = df.copy() if copy else df
    converted = {}

    for field, rules in validation_rules.items():
        if field not in out.columns or "enum" not in rules:
            continue

        case_sensitive = rules.get("case_sensitive", False)
        field_nulls = resolve_null_values(rules, null_values)
        if not field_nulls:
            continue

        found = find_null_coded_values(out, field, field_nulls, case_sensitive)
        if not found:
            continue

        null_keys = {comparison_key(v, case_sensitive) for v in field_nulls}
        null_keys.discard(None)

        keys = _key_series(out[field], case_sensitive)
        mask = keys.isin(null_keys)
        out.loc[mask, field] = np.nan
        converted[field] = found

    return out, converted
