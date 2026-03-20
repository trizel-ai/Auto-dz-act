"""UTC-normalized true-time-based source selection for the TRIZEL validation bridge.

This module provides a reusable engine for selecting the most recent candidate
file based on the intrinsic ``retrieved_utc`` timestamp embedded in each file,
rather than relying on storage conventions such as folder-date naming.

All timestamps are normalised to UTC before comparison, ensuring that
time-zone-independent, epistemically consistent selection is performed.

Public API
----------
extract_retrieved_utc(file_path)
    Read the ``retrieved_utc`` field from a JSON file and return it as an
    aware :class:`datetime.datetime` object normalised to UTC.  Raises on
    any error so that callers can handle failure explicitly.

select_latest_by_true_time(file_paths, logger=None)
    Given a collection of candidate file paths, return ``(path, utc_datetime)``
    for the file whose ``retrieved_utc`` timestamp is the latest.  Invalid
    files are skipped with a warning.

Design notes
------------
- Only local JSON files are read.  No network access is performed.
- All timestamps must be timezone-aware; naive timestamps are rejected.
- Invalid or unreadable files are skipped inside
  :func:`select_latest_by_true_time`; they are never silently ignored by
  :func:`extract_retrieved_utc` itself.
- If *no* valid candidate is found after scanning all files, a
  :exc:`RuntimeError` is raised so the caller can handle the failure
  explicitly.
- ISO-8601 timestamps with a trailing ``Z`` (UTC designator) are normalised
  to ``+00:00`` before parsing so that Python 3.10 and earlier versions that
  do not recognise ``Z`` in :meth:`datetime.fromisoformat` are supported.
"""

import json
import logging
from datetime import datetime, timezone
from typing import Sequence

__all__ = [
    "extract_retrieved_utc",
    "select_latest_by_true_time",
]

_UTC = timezone.utc


def _normalize_to_utc(ts: str) -> datetime:
    """Convert an ISO-8601 timestamp string to a UTC-aware datetime.

    Parameters
    ----------
    ts:
        ISO-8601 timestamp string (with or without trailing ``Z``).

    Returns
    -------
    datetime
        An aware :class:`~datetime.datetime` normalised to UTC.

    Raises
    ------
    ValueError
        If *ts* cannot be parsed as a valid ISO-8601 string, or if the
        parsed datetime is timezone-naive (all timestamps must carry explicit
        timezone information).
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


def extract_retrieved_utc(file_path: str) -> datetime:
    """Return the ``retrieved_utc`` timestamp from a JSON file as UTC.

    Parameters
    ----------
    file_path:
        Absolute or relative path to the JSON file to read.

    Returns
    -------
    datetime
        An aware :class:`~datetime.datetime` normalised to UTC.

    Raises
    ------
    OSError
        If the file cannot be opened or read.
    json.JSONDecodeError
        If the file does not contain valid JSON.
    ValueError
        If the JSON content is not an object, the ``retrieved_utc`` key is
        missing or not a non-empty string, or the value cannot be parsed as
        a timezone-aware ISO-8601 timestamp.
    """
    with open(file_path, encoding="utf-8") as fh:
        data = json.load(fh)

    if not isinstance(data, dict):
        raise ValueError(
            f"Expected a JSON object in {file_path!r}, "
            f"got {type(data).__name__}."
        )

    raw_value = data.get("retrieved_utc")
    if not isinstance(raw_value, str) or not raw_value:
        raise ValueError(
            f"Missing or invalid retrieved_utc in {file_path!r}."
        )

    return _normalize_to_utc(raw_value)


def select_latest_by_true_time(
    file_paths: Sequence[str],
    logger: logging.Logger | None = None,
) -> tuple[str, datetime, int, int]:
    """Return the path, UTC timestamp, invalid count, and total count.

    Evaluates each candidate file for a valid ``retrieved_utc`` timestamp.
    All timestamps are normalised to UTC before comparison.  Files whose
    ``retrieved_utc`` field is missing, malformed, or timezone-naive are
    counted as invalid and skipped with a warning — they are never silently
    discarded without a trace.

    Parameters
    ----------
    file_paths:
        An ordered collection of candidate file paths to evaluate.
    logger:
        Optional logger for diagnostic output.  When ``None``, a module-level
        silent logger is used so callers do not need to supply one.

    Returns
    -------
    (path, utc_datetime, invalid_count, total_count)
        A four-element tuple:

        * ``path`` — absolute path of the selected (latest) file.
        * ``utc_datetime`` — UTC-normalised :class:`~datetime.datetime` of
          the selected file's ``retrieved_utc`` field.
        * ``invalid_count`` — number of candidate files that could not be
          evaluated (missing field, bad format, or timezone-naive timestamp).
        * ``total_count`` — total number of candidate files examined
          (``valid_count + invalid_count``).

    Raises
    ------
    RuntimeError
        If *file_paths* is empty, or if no file in *file_paths* yields a
        valid ``retrieved_utc`` timestamp.
    """
    _log = logger if logger is not None else logging.getLogger(__name__)

    if not file_paths:
        raise RuntimeError(
            "select_latest_by_true_time: no candidate files provided."
        )

    total_count = len(file_paths)
    invalid_count = 0
    candidates: list[tuple[datetime, str]] = []

    for path in file_paths:
        try:
            dt = extract_retrieved_utc(path)
            _log.debug(
                "true-time selection: '%s' → retrieved_utc=%s", path, dt.isoformat()
            )
            candidates.append((dt, path))
        except Exception as exc:
            invalid_count += 1
            _log.warning(
                "true-time selection: skipping '%s' — %s", path, exc
            )
            continue

    if not candidates:
        raise RuntimeError(
            "select_latest_by_true_time: no valid retrieved_utc timestamp "
            "found in any of the provided candidate files: "
            + ", ".join(repr(p) for p in file_paths)
        )

    candidates.sort(key=lambda x: x[0])
    best_dt, best_path = candidates[-1]

    _log.info(
        "true-time selection: selected '%s' (retrieved_utc=%s, "
        "invalid=%d total=%d)",
        best_path,
        best_dt.isoformat(),
        invalid_count,
        total_count,
    )
    return best_path, best_dt, invalid_count, total_count
