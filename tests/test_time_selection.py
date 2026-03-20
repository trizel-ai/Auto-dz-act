"""Tests for validation.core.time_selection.

Covers:
- _normalize_to_utc: Z suffix, offset, naive timestamp rejection.
- extract_retrieved_utc: valid ISO-8601 (with Z, with non-UTC offset),
  missing field, invalid value, unreadable file, non-JSON-object content,
  timezone-naive value rejection.
- select_latest_by_true_time: correct selection by latest UTC timestamp,
  timezone normalization across mixed offsets, skipping invalid files,
  error on empty list, error when no valid candidates remain, tuple return.
"""

import json
import logging
import os
import sys
import tempfile
import unittest
from datetime import timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from validation.core.time_selection import (
    extract_retrieved_utc,
    select_latest_by_true_time,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_logger() -> logging.Logger:
    """Return a silent logger suitable for use in tests."""
    logger = logging.getLogger(f"test_time_selection_{id(object())}")
    logger.addHandler(logging.NullHandler())
    logger.propagate = False
    return logger


def _write_json(data: dict | list, suffix: str = ".json") -> str:
    """Write *data* to a temporary file and return its absolute path."""
    fh = tempfile.NamedTemporaryFile(
        mode="w", suffix=suffix, delete=False, encoding="utf-8"
    )
    json.dump(data, fh, indent=2)
    fh.close()
    return fh.name


def _write_text(text: str, suffix: str = ".json") -> str:
    """Write raw *text* to a temporary file and return its absolute path."""
    fh = tempfile.NamedTemporaryFile(
        mode="w", suffix=suffix, delete=False, encoding="utf-8"
    )
    fh.write(text)
    fh.close()
    return fh.name


# ---------------------------------------------------------------------------
# extract_retrieved_utc
# ---------------------------------------------------------------------------

class TestExtractRetrievedUtc(unittest.TestCase):
    """Unit tests for extract_retrieved_utc."""

    # --- happy paths ---

    def test_parses_utc_z_suffix(self) -> None:
        path = _write_json({"retrieved_utc": "2026-03-20T12:00:00Z"})
        try:
            dt = extract_retrieved_utc(path)
            self.assertEqual(dt.year, 2026)
            self.assertEqual(dt.month, 3)
            self.assertEqual(dt.day, 20)
            self.assertEqual(dt.hour, 12)
        finally:
            os.unlink(path)

    def test_parses_utc_plus_offset(self) -> None:
        path = _write_json({"retrieved_utc": "2026-03-20T12:00:00+00:00"})
        try:
            dt = extract_retrieved_utc(path)
            self.assertEqual(dt.hour, 12)
        finally:
            os.unlink(path)

    def test_result_is_timezone_aware(self) -> None:
        path = _write_json({"retrieved_utc": "2026-03-20T00:00:00Z"})
        try:
            dt = extract_retrieved_utc(path)
            self.assertIsNotNone(dt.tzinfo)
            self.assertEqual(dt.tzinfo, timezone.utc)
        finally:
            os.unlink(path)

    def test_non_utc_offset_converted_to_utc(self) -> None:
        # +02:00 means the UTC equivalent is 2 hours earlier
        path = _write_json({"retrieved_utc": "2026-03-20T14:00:00+02:00"})
        try:
            dt = extract_retrieved_utc(path)
            self.assertEqual(dt.tzinfo, timezone.utc)
            self.assertEqual(dt.hour, 12)
        finally:
            os.unlink(path)

    # --- timezone-naive timestamps are rejected ---

    def test_naive_timestamp_raises_value_error(self) -> None:
        path = _write_json({"retrieved_utc": "2026-03-18T08:30:00"})
        try:
            with self.assertRaises(ValueError):
                extract_retrieved_utc(path)
        finally:
            os.unlink(path)

    # --- missing / invalid field raises ---

    def test_missing_retrieved_utc_raises_value_error(self) -> None:
        path = _write_json({"other_field": "value"})
        try:
            with self.assertRaises(ValueError):
                extract_retrieved_utc(path)
        finally:
            os.unlink(path)

    def test_empty_string_raises_value_error(self) -> None:
        path = _write_json({"retrieved_utc": ""})
        try:
            with self.assertRaises(ValueError):
                extract_retrieved_utc(path)
        finally:
            os.unlink(path)

    def test_non_string_value_raises_value_error(self) -> None:
        path = _write_json({"retrieved_utc": 12345})
        try:
            with self.assertRaises(ValueError):
                extract_retrieved_utc(path)
        finally:
            os.unlink(path)

    def test_invalid_iso_format_raises_value_error(self) -> None:
        path = _write_json({"retrieved_utc": "not-a-date"})
        try:
            with self.assertRaises(ValueError):
                extract_retrieved_utc(path)
        finally:
            os.unlink(path)

    # --- invalid file content raises ---

    def test_non_object_json_raises_value_error(self) -> None:
        path = _write_json(["a", "b"])
        try:
            with self.assertRaises(ValueError):
                extract_retrieved_utc(path)
        finally:
            os.unlink(path)

    def test_invalid_json_raises_json_decode_error(self) -> None:
        path = _write_text("NOT JSON {{{")
        try:
            with self.assertRaises(json.JSONDecodeError):
                extract_retrieved_utc(path)
        finally:
            os.unlink(path)

    def test_nonexistent_file_raises_os_error(self) -> None:
        with self.assertRaises(OSError):
            extract_retrieved_utc("/tmp/this_file_does_not_exist_xyz.json")


# ---------------------------------------------------------------------------
# select_latest_by_true_time
# ---------------------------------------------------------------------------

class TestSelectLatestByTrueTime(unittest.TestCase):
    """Unit tests for select_latest_by_true_time."""

    def setUp(self) -> None:
        self.logger = _make_logger()
        self._temp_files: list[str] = []

    def tearDown(self) -> None:
        for path in self._temp_files:
            try:
                os.unlink(path)
            except OSError:
                pass

    def _make_file(self, retrieved_utc: str) -> str:
        path = _write_json({"retrieved_utc": retrieved_utc})
        self._temp_files.append(path)
        return path

    def _make_invalid_file(self) -> str:
        path = _write_json({"other": "data"})
        self._temp_files.append(path)
        return path

    # --- return type ---

    def test_returns_tuple_of_path_and_datetime(self) -> None:
        only = self._make_file("2026-03-19T06:00:00Z")
        result = select_latest_by_true_time([only], self.logger)
        self.assertIsInstance(result, tuple)
        self.assertEqual(len(result), 4)
        path, dt, invalid_count, total_count = result
        self.assertIsInstance(path, str)
        self.assertIsNotNone(dt.tzinfo)

    # --- correct selection ---

    def test_selects_latest_among_two(self) -> None:
        older = self._make_file("2026-03-18T00:00:00Z")
        newer = self._make_file("2026-03-20T00:00:00Z")
        path, _, _, _ = select_latest_by_true_time([older, newer], self.logger)
        self.assertEqual(path, newer)

    def test_selects_latest_among_three(self) -> None:
        a = self._make_file("2026-03-18T00:00:00Z")
        b = self._make_file("2026-03-20T00:00:00Z")
        c = self._make_file("2026-03-21T12:00:00Z")
        path, _, _, _ = select_latest_by_true_time([a, b, c], self.logger)
        self.assertEqual(path, c)

    def test_order_of_paths_does_not_matter(self) -> None:
        older = self._make_file("2026-03-18T00:00:00Z")
        newer = self._make_file("2026-03-20T00:00:00Z")
        # Pass newer first to ensure it's not just returning the first element
        path, _, _, _ = select_latest_by_true_time([newer, older], self.logger)
        self.assertEqual(path, newer)

    def test_single_valid_file_is_returned(self) -> None:
        only = self._make_file("2026-03-19T06:00:00Z")
        path, _, _, _ = select_latest_by_true_time([only], self.logger)
        self.assertEqual(path, only)

    def test_skips_invalid_and_returns_valid(self) -> None:
        invalid = self._make_invalid_file()
        valid = self._make_file("2026-03-20T00:00:00Z")
        path, _, _, _ = select_latest_by_true_time([invalid, valid], self.logger)
        self.assertEqual(path, valid)

    def test_folder_date_does_not_influence_selection(self) -> None:
        """File in 'newer' folder but older retrieved_utc should lose."""
        # Simulate: folder A is 2026-03-21, but data is from 2026-03-18
        # folder B is 2026-03-20, data is from 2026-03-20
        file_a = self._make_file("2026-03-18T00:00:00Z")
        file_b = self._make_file("2026-03-20T00:00:00Z")
        path, _, _, _ = select_latest_by_true_time([file_a, file_b], self.logger)
        self.assertEqual(path, file_b)

    def test_timezone_normalization(self) -> None:
        """UTC normalization must occur before comparison.

        f1: 2026-03-20T10:00:00+02:00  →  2026-03-20T08:00:00 UTC
        f2: 2026-03-20T08:30:00+00:00  →  2026-03-20T08:30:00 UTC
        f2 is later in UTC and should win.
        """
        f1 = self._make_file("2026-03-20T10:00:00+02:00")
        f2 = self._make_file("2026-03-20T08:30:00+00:00")
        selected, dt, _, _ = select_latest_by_true_time([f1, f2], self.logger)
        self.assertEqual(selected, f2)
        self.assertEqual(dt.hour, 8)
        self.assertEqual(dt.minute, 30)
        self.assertEqual(dt.tzinfo, timezone.utc)

    def test_returned_datetime_is_utc(self) -> None:
        only = self._make_file("2026-03-19T06:00:00+02:00")
        _, dt, _, _ = select_latest_by_true_time([only], self.logger)
        self.assertEqual(dt.tzinfo, timezone.utc)
        # +02:00 → 04:00 UTC
        self.assertEqual(dt.hour, 4)

    # --- invalid_count and total_count ---

    def test_invalid_count_is_zero_when_all_valid(self) -> None:
        a = self._make_file("2026-03-18T00:00:00Z")
        b = self._make_file("2026-03-20T00:00:00Z")
        _, _, invalid_count, total_count = select_latest_by_true_time(
            [a, b], self.logger
        )
        self.assertEqual(invalid_count, 0)
        self.assertEqual(total_count, 2)

    def test_invalid_count_tracks_missing_retrieved_utc(self) -> None:
        invalid = self._make_invalid_file()
        valid = self._make_file("2026-03-20T00:00:00Z")
        _, _, invalid_count, total_count = select_latest_by_true_time(
            [invalid, valid], self.logger
        )
        self.assertEqual(invalid_count, 1)
        self.assertEqual(total_count, 2)

    def test_total_count_equals_input_length(self) -> None:
        files = [self._make_file(f"2026-03-{d:02d}T00:00:00Z") for d in [15, 16, 17]]
        _, _, _, total_count = select_latest_by_true_time(files, self.logger)
        self.assertEqual(total_count, 3)

    # --- error cases ---

    def test_empty_list_raises_runtime_error(self) -> None:
        with self.assertRaises(RuntimeError):
            select_latest_by_true_time([], self.logger)

    def test_all_invalid_raises_runtime_error(self) -> None:
        inv1 = self._make_invalid_file()
        inv2 = self._make_invalid_file()
        with self.assertRaises(RuntimeError):
            select_latest_by_true_time([inv1, inv2], self.logger)

    def test_works_without_logger(self) -> None:
        """Passing logger=None should not raise."""
        only = self._make_file("2026-03-19T06:00:00Z")
        path, _, _, _ = select_latest_by_true_time([only])
        self.assertEqual(path, only)


if __name__ == "__main__":
    unittest.main()
