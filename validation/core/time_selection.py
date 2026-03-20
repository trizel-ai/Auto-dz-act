"""True-time-based source selection for the TRIZEL validation bridge.

This module provides a reusable engine for selecting the most recent candidate
file based on the intrinsic ``retrieved_utc`` timestamp embedded in each file,
rather than relying on storage conventions such as folder-date naming.

Public API
----------
extract_retrieved_utc(file_path)
    Read the ``retrieved_utc`` field from a JSON file and return it as an
    aware :class:`datetime.datetime` object in UTC.

select_latest_by_true_time(file_paths, logger=None)
    Given a collection of candidate file paths, return the path whose JSON
    content carries the latest ``retrieved_utc`` timestamp.

Design notes
------------
- Only local JSON files are read.  No network access is performed.
- Invalid or unreadable files are skipped with a warning; they never raise.
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


def extract_retrieved_utc(file_path: str) -> datetime | None:
    """Return the ``retrieved_utc`` timestamp from a JSON file.

    Parameters
    ----------
    file_path:
        Absolute or relative path to the JSON file to read.

    Returns
    -------
    datetime | None
        An aware :class:`~datetime.datetime` in UTC, or ``None`` if the file
        cannot be read, is not valid JSON, does not contain the
        ``retrieved_utc`` key, or contains a value that cannot be parsed as
        an ISO-8601 timestamp.
    """
    try:
        with open(file_path, encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, json.JSONDecodeError):
        return None

    if not isinstance(data, dict):
        return None

    raw_value = data.get("retrieved_utc")
    if not isinstance(raw_value, str) or not raw_value:
        return None

    # Normalise the trailing 'Z' UTC designator for compatibility with
    # Python versions that do not accept it in fromisoformat().
    normalised = raw_value
    if normalised.endswith("Z"):
        normalised = normalised[:-1] + "+00:00"

    try:
        dt = datetime.fromisoformat(normalised)
    except ValueError:
        return None

    # Ensure the result is always timezone-aware (UTC).
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=_UTC)
    else:
        dt = dt.astimezone(_UTC)

    return dt


def select_latest_by_true_time(
    file_paths: Sequence[str],
    logger: logging.Logger | None = None,
) -> str:
    """Return the path of the file with the latest ``retrieved_utc`` timestamp.

    Parameters
    ----------
    file_paths:
        An ordered collection of candidate file paths to evaluate.
    logger:
        Optional logger for diagnostic output.  When ``None``, a module-level
        silent logger is used so callers do not need to supply one.

    Returns
    -------
    str
        The element of *file_paths* whose JSON content contains the greatest
        ``retrieved_utc`` value.

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

    best_path: str | None = None
    best_dt: datetime | None = None

    for path in file_paths:
        dt = extract_retrieved_utc(path)
        if dt is None:
            _log.warning(
                "true-time selection: skipping '%s' — could not extract "
                "a valid retrieved_utc timestamp.",
                path,
            )
            continue

        _log.debug(
            "true-time selection: '%s' → retrieved_utc=%s", path, dt.isoformat()
        )

        if best_dt is None or dt > best_dt:
            best_dt = dt
            best_path = path

    if best_path is None:
        raise RuntimeError(
            "select_latest_by_true_time: no valid retrieved_utc timestamp "
            "found in any of the provided candidate files: "
            + ", ".join(repr(p) for p in file_paths)
        )

    _log.info(
        "true-time selection: selected '%s' (retrieved_utc=%s)",
        best_path,
        best_dt.isoformat() if best_dt else "?",
    )
    return best_path
