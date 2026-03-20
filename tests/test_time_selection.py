"""Tests for validation.core.time_selection.

Covers:
- extract_retrieved_utc: valid ISO-8601 (with Z, with offset, no tz),
  missing field, invalid value, unreadable file, non-JSON-object content.
- select_latest_by_true_time: correct selection by latest timestamp,
  skipping invalid timestamps, error on empty list, error when no valid
  candidates remain.
"""

import json
import logging
import os
import sys
import tempfile
import unittest

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

    def tearDown(self) -> None:
        # Clean up any temp files created during a test.
        pass  # individual tests use tempfile.NamedTemporaryFile; paths are stored

    # --- happy paths ---

    def test_parses_utc_z_suffix(self) -> None:
        path = _write_json({"retrieved_utc": "2026-03-20T12:00:00Z"})
        try:
            dt = extract_retrieved_utc(path)
            self.assertIsNotNone(dt)
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
            self.assertIsNotNone(dt)
            self.assertEqual(dt.hour, 12)
        finally:
            os.unlink(path)

    def test_parses_no_timezone_treats_as_utc(self) -> None:
        path = _write_json({"retrieved_utc": "2026-03-18T08:30:00"})
        try:
            dt = extract_retrieved_utc(path)
            self.assertIsNotNone(dt)
            self.assertEqual(dt.hour, 8)
        finally:
            os.unlink(path)

    def test_result_is_timezone_aware(self) -> None:
        from datetime import timezone
        path = _write_json({"retrieved_utc": "2026-03-20T00:00:00Z"})
        try:
            dt = extract_retrieved_utc(path)
            self.assertIsNotNone(dt)
            self.assertIsNotNone(dt.tzinfo)
            self.assertEqual(dt.tzinfo, timezone.utc)
        finally:
            os.unlink(path)

    def test_non_utc_offset_converted_to_utc(self) -> None:
        # +02:00 means the UTC equivalent is 2 hours earlier
        path = _write_json({"retrieved_utc": "2026-03-20T14:00:00+02:00"})
        try:
            dt = extract_retrieved_utc(path)
            self.assertIsNotNone(dt)
            from datetime import timezone
            self.assertEqual(dt.tzinfo, timezone.utc)
            self.assertEqual(dt.hour, 12)
        finally:
            os.unlink(path)

    # --- missing / invalid field ---

    def test_missing_retrieved_utc_returns_none(self) -> None:
        path = _write_json({"other_field": "value"})
        try:
            self.assertIsNone(extract_retrieved_utc(path))
        finally:
            os.unlink(path)

    def test_empty_string_returns_none(self) -> None:
        path = _write_json({"retrieved_utc": ""})
        try:
            self.assertIsNone(extract_retrieved_utc(path))
        finally:
            os.unlink(path)

    def test_non_string_value_returns_none(self) -> None:
        path = _write_json({"retrieved_utc": 12345})
        try:
            self.assertIsNone(extract_retrieved_utc(path))
        finally:
            os.unlink(path)

    def test_invalid_iso_format_returns_none(self) -> None:
        path = _write_json({"retrieved_utc": "not-a-date"})
        try:
            self.assertIsNone(extract_retrieved_utc(path))
        finally:
            os.unlink(path)

    # --- invalid file content ---

    def test_non_object_json_returns_none(self) -> None:
        path = _write_json(["a", "b"])
        try:
            self.assertIsNone(extract_retrieved_utc(path))
        finally:
            os.unlink(path)

    def test_invalid_json_returns_none(self) -> None:
        path = _write_text("NOT JSON {{{")
        try:
            self.assertIsNone(extract_retrieved_utc(path))
        finally:
            os.unlink(path)

    def test_nonexistent_file_returns_none(self) -> None:
        self.assertIsNone(extract_retrieved_utc("/tmp/this_file_does_not_exist_xyz.json"))


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

    # --- correct selection ---

    def test_selects_latest_among_two(self) -> None:
        older = self._make_file("2026-03-18T00:00:00Z")
        newer = self._make_file("2026-03-20T00:00:00Z")
        result = select_latest_by_true_time([older, newer], self.logger)
        self.assertEqual(result, newer)

    def test_selects_latest_among_three(self) -> None:
        a = self._make_file("2026-03-18T00:00:00Z")
        b = self._make_file("2026-03-20T00:00:00Z")
        c = self._make_file("2026-03-21T12:00:00Z")
        result = select_latest_by_true_time([a, b, c], self.logger)
        self.assertEqual(result, c)

    def test_order_of_paths_does_not_matter(self) -> None:
        older = self._make_file("2026-03-18T00:00:00Z")
        newer = self._make_file("2026-03-20T00:00:00Z")
        # Pass newer first to ensure it's not just returning the first element
        result = select_latest_by_true_time([newer, older], self.logger)
        self.assertEqual(result, newer)

    def test_single_valid_file_is_returned(self) -> None:
        only = self._make_file("2026-03-19T06:00:00Z")
        result = select_latest_by_true_time([only], self.logger)
        self.assertEqual(result, only)

    def test_skips_invalid_and_returns_valid(self) -> None:
        invalid = self._make_invalid_file()
        valid = self._make_file("2026-03-20T00:00:00Z")
        result = select_latest_by_true_time([invalid, valid], self.logger)
        self.assertEqual(result, valid)

    def test_folder_date_does_not_influence_selection(self) -> None:
        """File in 'newer' folder but older retrieved_utc should lose."""
        # Simulate: folder A is 2026-03-21, but data is from 2026-03-18
        # folder B is 2026-03-20, data is from 2026-03-20
        file_a = self._make_file("2026-03-18T00:00:00Z")
        file_b = self._make_file("2026-03-20T00:00:00Z")
        # Without true-time, file_a (newer folder) would be returned;
        # with true-time, file_b should win.
        result = select_latest_by_true_time([file_a, file_b], self.logger)
        self.assertEqual(result, file_b)

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
        result = select_latest_by_true_time([only])
        self.assertEqual(result, only)


if __name__ == "__main__":
    unittest.main()
