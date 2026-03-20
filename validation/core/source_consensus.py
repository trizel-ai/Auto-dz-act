"""Multi-source true-time consensus engine for the TRIZEL validation layer.

This module provides a reusable engine that collects valid source records from
multiple repositories or providers, normalises all timestamps to UTC, compares
temporal overlap and value agreement, and produces a structured consensus
record.

This is a comparison and validation layer only.
It does NOT impose a physical interpretation.
It does NOT privilege a theory.
It does NOT replace epistemic classification.

Public API
----------
normalize_source_time(record)
    Return the best available UTC-aware time for a source record.

collect_consensus_inputs(records)
    Validate input records and split them into valid and invalid groups,
    tracking all rejection reasons so nothing is silently discarded.

compute_time_span(valid_records)
    Compute the temporal spread across a collection of valid source records.

compare_numeric_field(valid_records, field_path)
    Compare a shared numeric field across all valid source records.

build_consensus_record(valid_records, invalid_records, compared_fields)
    Produce one structured consensus output record.

Design notes
------------
- All internal time comparison uses UTC-aware datetimes.
- Naive timestamps are rejected explicitly; never silently coerced.
- Invalid records are never silently discarded; all rejections are tracked.
- All classification thresholds are defined as named module-level constants.
- ISO-8601 timestamps with a trailing ``Z`` (UTC designator) are normalised
  to ``+00:00`` before parsing so that Python 3.10 and earlier versions that
  do not recognise ``Z`` in :meth:`datetime.fromisoformat` are supported.
"""

from datetime import datetime, timezone
from typing import Any, Sequence

__all__ = [
    "CONSENSUS_TIME_ALIGNED_MAX_SECONDS",
    "CONSENSUS_TIME_WEAK_MAX_SECONDS",
    "CONSENSUS_NUMERIC_ALIGNED_MAX_DELTA",
    "CONSENSUS_NUMERIC_WEAK_MAX_DELTA",
    "DEFAULT_COMPARED_FIELDS",
    "normalize_source_time",
    "collect_consensus_inputs",
    "compute_time_span",
    "compare_numeric_field",
    "build_consensus_record",
]

# ---------------------------------------------------------------------------
# Classification thresholds — never hide these in magic numbers
# ---------------------------------------------------------------------------

#: Maximum time spread (seconds) for a ``"aligned"`` time classification.
CONSENSUS_TIME_ALIGNED_MAX_SECONDS: int = 3_600        # 1 hour

#: Maximum time spread (seconds) for a ``"weakly_divergent"`` classification.
#: Spreads above this threshold are classified as ``"divergent"``.
CONSENSUS_TIME_WEAK_MAX_SECONDS: int = 86_400          # 24 hours

#: Maximum absolute ``max_delta`` for a ``"aligned"`` numeric field status.
CONSENSUS_NUMERIC_ALIGNED_MAX_DELTA: float = 0.01

#: Maximum absolute ``max_delta`` for a ``"weakly_divergent"`` numeric status.
#: Deltas above this threshold are classified as ``"divergent"``.
CONSENSUS_NUMERIC_WEAK_MAX_DELTA: float = 0.10

#: Default orbital fields compared when no explicit list is supplied.
DEFAULT_COMPARED_FIELDS: tuple[str, ...] = (
    "orbital.eccentricity",
    "orbital.semi_major_axis",
    "orbital.inclination",
    "orbital.perihelion_distance",
)

_UTC = timezone.utc


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _parse_utc(ts: str) -> datetime:
    """Parse an ISO-8601 timestamp string and return a UTC-aware datetime.

    Parameters
    ----------
    ts:
        ISO-8601 timestamp string, with or without a trailing ``Z``.

    Returns
    -------
    datetime
        An aware :class:`~datetime.datetime` normalised to UTC.

    Raises
    ------
    ValueError
        If *ts* cannot be parsed as a valid ISO-8601 string, or if the
        resulting datetime is timezone-naive.
    """
    normalised = ts
    if normalised.endswith("Z"):
        normalised = normalised[:-1] + "+00:00"

    dt = datetime.fromisoformat(normalised)

    if dt.tzinfo is None:
        raise ValueError(
            f"Timestamp must be timezone-aware: {ts!r}"
        )

    return dt.astimezone(_UTC)


def _get_nested_field(obj: Any, field_path: str) -> Any:
    """Safely retrieve a nested field using dot-separated path notation.

    Parameters
    ----------
    obj:
        The root mapping (expected to be a :class:`dict`).
    field_path:
        Dot-separated field path, e.g. ``"orbital.eccentricity"``.

    Returns
    -------
    Any
        The value at the requested path, or ``None`` if any intermediate
        key is absent or if any intermediate value is not a mapping.
    """
    current = obj
    for part in field_path.split("."):
        if not isinstance(current, dict):
            return None
        current = current.get(part)
        if current is None:
            return None
    return current


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def normalize_source_time(record: dict) -> datetime:
    """Return the best available UTC-aware time for a source record.

    Time selection preference:

    1. ``observation_time_utc`` — used when present and parseable.
    2. ``retrieved_utc`` — used as the fallback.

    Naive timestamps (no timezone information) are rejected so that all
    comparisons remain epistemically consistent.

    Parameters
    ----------
    record:
        A source record dict containing at least one of
        ``observation_time_utc`` or ``retrieved_utc``.

    Returns
    -------
    datetime
        An aware :class:`~datetime.datetime` normalised to UTC.

    Raises
    ------
    ValueError
        If neither field is present and valid, or if the timestamp string
        is unparseable or timezone-naive.
    """
    source_id = record.get("source_id", "(unknown)")

    obs = record.get("observation_time_utc")
    if isinstance(obs, str) and obs:
        try:
            return _parse_utc(obs)
        except ValueError as exc:
            raise ValueError(
                f"Invalid observation_time_utc in record {source_id!r}: {exc}"
            ) from exc

    ret = record.get("retrieved_utc")
    if isinstance(ret, str) and ret:
        try:
            return _parse_utc(ret)
        except ValueError as exc:
            raise ValueError(
                f"Invalid retrieved_utc in record {source_id!r}: {exc}"
            ) from exc

    raise ValueError(
        f"No valid time field (observation_time_utc or retrieved_utc) "
        f"found in record {source_id!r}."
    )


def collect_consensus_inputs(records: Sequence[Any]) -> dict:
    """Validate input records and split them into valid and invalid groups.

    Every rejection is tracked so that nothing is silently discarded.

    Parameters
    ----------
    records:
        An iterable of candidate source record dicts.

    Returns
    -------
    dict
        A result mapping with the following keys:

        * ``valid_records`` — list of records with a parseable UTC time.
        * ``invalid_records`` — list of ``{"source_id": ..., "reason": ...}``
          entries for every rejected record.
        * ``invalid_count`` — total number of rejected records.
        * ``invalid_reasons`` — list of human-readable rejection reason
          strings (one per rejected record, in order).
    """
    valid_records: list[dict] = []
    invalid_records: list[dict] = []
    invalid_reasons: list[str] = []

    for record in records:
        if not isinstance(record, dict):
            reason = (
                f"Record is not a dict (got {type(record).__name__!r})."
            )
            invalid_reasons.append(reason)
            invalid_records.append({"source_id": "(non-dict)", "reason": reason})
            continue

        source_id = record.get("source_id", "(unknown)")

        try:
            normalize_source_time(record)
        except Exception as exc:
            reason = str(exc)
            invalid_reasons.append(reason)
            invalid_records.append({"source_id": source_id, "reason": reason})
            continue

        valid_records.append(record)

    return {
        "valid_records": valid_records,
        "invalid_records": invalid_records,
        "invalid_count": len(invalid_records),
        "invalid_reasons": invalid_reasons,
    }


def compute_time_span(valid_records: Sequence[dict]) -> dict:
    """Compute the temporal spread across a collection of valid source records.

    Parameters
    ----------
    valid_records:
        Records that have already been validated by
        :func:`collect_consensus_inputs`.

    Returns
    -------
    dict
        A mapping with the following keys:

        * ``earliest_utc`` — the earliest UTC
          :class:`~datetime.datetime` found, or ``None`` when no times
          could be resolved.
        * ``latest_utc`` — the latest UTC
          :class:`~datetime.datetime` found, or ``None``.
        * ``time_span_seconds`` — float seconds between earliest and
          latest (``0.0`` when fewer than two valid times exist).
    """
    times: list[datetime] = []

    for record in valid_records:
        try:
            times.append(normalize_source_time(record))
        except Exception:
            continue

    if not times:
        return {
            "earliest_utc": None,
            "latest_utc": None,
            "time_span_seconds": 0.0,
        }

    earliest = min(times)
    latest = max(times)

    return {
        "earliest_utc": earliest,
        "latest_utc": latest,
        "time_span_seconds": (latest - earliest).total_seconds(),
    }


def compare_numeric_field(valid_records: Sequence[dict], field_path: str) -> dict:
    """Compare a shared numeric field across all valid source records.

    The field is accessed via :func:`_get_nested_field` on the
    ``"payload"`` sub-dict of each record, so a *field_path* of
    ``"orbital.eccentricity"`` resolves to
    ``record["payload"]["orbital"]["eccentricity"]``.

    Missing values are silently skipped; the whole consensus is never
    aborted because one field is absent in one source.  Non-numeric
    values are also skipped (they are not counted toward the result).

    Parameters
    ----------
    valid_records:
        Records that have already been validated by
        :func:`collect_consensus_inputs`.
    field_path:
        Dot-separated path to the numeric field inside each record's
        ``"payload"`` dict (e.g. ``"orbital.eccentricity"``).

    Returns
    -------
    dict
        When at least two numeric values are found:

        * ``count`` — number of records contributing a valid numeric value.
        * ``min`` — minimum value.
        * ``max`` — maximum value.
        * ``mean`` — arithmetic mean.
        * ``max_delta`` — ``max - min``.
        * ``status`` — ``"aligned"``, ``"weakly_divergent"``, or
          ``"divergent"`` based on *max_delta* thresholds.

        When fewer than two numeric values are found:

        * ``count`` — number of records that contributed a value (0 or 1).
        * ``status`` — ``"insufficient"``.
    """
    values: list[float] = []

    for record in valid_records:
        payload = record.get("payload")
        if not isinstance(payload, dict):
            continue
        raw = _get_nested_field(payload, field_path)
        if raw is None:
            continue
        if not isinstance(raw, (int, float)) or isinstance(raw, bool):
            continue
        values.append(float(raw))

    if len(values) < 2:
        return {
            "count": len(values),
            "status": "insufficient",
        }

    count = len(values)
    min_val = min(values)
    max_val = max(values)
    mean_val = sum(values) / count
    max_delta = max_val - min_val

    if max_delta <= CONSENSUS_NUMERIC_ALIGNED_MAX_DELTA:
        status = "aligned"
    elif max_delta <= CONSENSUS_NUMERIC_WEAK_MAX_DELTA:
        status = "weakly_divergent"
    else:
        status = "divergent"

    return {
        "count": count,
        "min": min_val,
        "max": max_val,
        "mean": mean_val,
        "max_delta": max_delta,
        "status": status,
    }


def build_consensus_record(
    valid_records: Sequence[dict],
    invalid_records: Sequence[dict],
    compared_fields: Sequence[str] | None = None,
) -> dict:
    """Produce one structured consensus output record.

    Parameters
    ----------
    valid_records:
        Records accepted by :func:`collect_consensus_inputs`.
    invalid_records:
        Rejection entries (``{"source_id": ..., "reason": ...}``) returned
        by :func:`collect_consensus_inputs`.
    compared_fields:
        Iterable of dot-separated field paths to compare across records.
        When ``None``, :data:`DEFAULT_COMPARED_FIELDS` is used.

    Returns
    -------
    dict
        A structured consensus result with the following keys:

        * ``consensus_method`` — always ``"multi_source_true_time"``.
        * ``sources_considered`` — total records evaluated.
        * ``sources_valid`` — records accepted as valid.
        * ``sources_invalid`` — records rejected as invalid.
        * ``selected_time_utc`` — ISO-8601 UTC string of the latest valid
          time found across all valid records, or ``None``.
        * ``time_span_seconds`` — float seconds between the earliest and
          latest valid source times.
        * ``time_alignment_status`` — ``"aligned"``, ``"weakly_divergent"``,
          or ``"divergent"`` based on :data:`CONSENSUS_TIME_ALIGNED_MAX_SECONDS`
          and :data:`CONSENSUS_TIME_WEAK_MAX_SECONDS`.
        * ``field_comparisons`` — mapping of field_path →
          :func:`compare_numeric_field` result for each compared field.
        * ``invalid_sources`` — copy of *invalid_records*.
    """
    if compared_fields is None:
        compared_fields = list(DEFAULT_COMPARED_FIELDS)

    sources_valid = len(valid_records)
    sources_invalid = len(invalid_records)
    sources_considered = sources_valid + sources_invalid

    time_meta = compute_time_span(valid_records)
    span_seconds = time_meta["time_span_seconds"]
    latest_utc = time_meta.get("latest_utc")

    selected_time_utc = (
        latest_utc.isoformat() if latest_utc is not None else None
    )

    if sources_valid == 0:
        time_alignment_status = "divergent"
    elif span_seconds <= CONSENSUS_TIME_ALIGNED_MAX_SECONDS:
        time_alignment_status = "aligned"
    elif span_seconds <= CONSENSUS_TIME_WEAK_MAX_SECONDS:
        time_alignment_status = "weakly_divergent"
    else:
        time_alignment_status = "divergent"

    field_comparisons: dict[str, dict] = {}
    for field_path in compared_fields:
        field_comparisons[field_path] = compare_numeric_field(
            valid_records, field_path
        )

    return {
        "consensus_method": "multi_source_true_time",
        "sources_considered": sources_considered,
        "sources_valid": sources_valid,
        "sources_invalid": sources_invalid,
        "selected_time_utc": selected_time_utc,
        "time_span_seconds": span_seconds,
        "time_alignment_status": time_alignment_status,
        "field_comparisons": field_comparisons,
        "invalid_sources": list(invalid_records),
    }
