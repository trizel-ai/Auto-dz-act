"""Tests for validation.core.source_consensus.

Covers:
- normalize_source_time: observation_time_utc preference, retrieved_utc
  fallback, non-UTC offset normalisation, naive timestamp rejection,
  missing fields, invalid timestamp strings.
- collect_consensus_inputs: all-valid, mixed valid/invalid, non-dict records,
  invalid_count tracking, invalid_reasons tracking, no silent discard.
- compute_time_span: single record, multiple records, mixed offsets,
  empty input.
- compare_numeric_field: aligned / weakly_divergent / divergent / insufficient,
  missing payload, missing nested field, non-numeric values skipped, bool
  values rejected.
- build_consensus_record: output shape with all required keys, time alignment
  classification, field comparisons delegated correctly, invalid_sources
  propagated, empty valid set.
"""

import os
import sys
import unittest
from datetime import timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from validation.core.source_consensus import (
    CONSENSUS_NUMERIC_ALIGNED_MAX_DELTA,
    CONSENSUS_NUMERIC_WEAK_MAX_DELTA,
    CONSENSUS_TIME_ALIGNED_MAX_SECONDS,
    CONSENSUS_TIME_WEAK_MAX_SECONDS,
    DEFAULT_COMPARED_FIELDS,
    build_consensus_record,
    collect_consensus_inputs,
    compare_numeric_field,
    compute_time_span,
    normalize_source_time,
)

_UTC = timezone.utc


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

def _record(
    source_id: str = "src-001",
    retrieved_utc: str | None = "2026-03-20T12:00:00Z",
    observation_time_utc: str | None = None,
    payload: dict | None = None,
    repository: str = "test-repo",
) -> dict:
    """Build a minimal source record dict for use in tests."""
    rec: dict = {
        "source_id": source_id,
        "repository": repository,
    }
    if retrieved_utc is not None:
        rec["retrieved_utc"] = retrieved_utc
    if observation_time_utc is not None:
        rec["observation_time_utc"] = observation_time_utc
    if payload is not None:
        rec["payload"] = payload
    return rec


def _orbital_payload(
    eccentricity: float | None = 0.5,
    semi_major_axis: float | None = 1.5,
    inclination: float | None = 30.0,
    perihelion_distance: float | None = 0.75,
) -> dict:
    """Build a payload dict with orbital sub-fields."""
    orbital: dict = {}
    if eccentricity is not None:
        orbital["eccentricity"] = eccentricity
    if semi_major_axis is not None:
        orbital["semi_major_axis"] = semi_major_axis
    if inclination is not None:
        orbital["inclination"] = inclination
    if perihelion_distance is not None:
        orbital["perihelion_distance"] = perihelion_distance
    return {"orbital": orbital}


# ---------------------------------------------------------------------------
# normalize_source_time
# ---------------------------------------------------------------------------

class TestNormalizeSourceTime(unittest.TestCase):
    """Unit tests for normalize_source_time."""

    # --- observation_time_utc preference ---

    def test_prefers_observation_time_utc_over_retrieved_utc(self) -> None:
        rec = _record(
            retrieved_utc="2026-03-20T08:00:00Z",
            observation_time_utc="2026-03-20T06:00:00Z",
        )
        dt = normalize_source_time(rec)
        self.assertEqual(dt.hour, 6)

    def test_observation_time_utc_used_when_retrieved_absent(self) -> None:
        rec = _record(retrieved_utc=None, observation_time_utc="2026-03-20T09:00:00Z")
        dt = normalize_source_time(rec)
        self.assertEqual(dt.hour, 9)

    # --- retrieved_utc fallback ---

    def test_falls_back_to_retrieved_utc_when_observation_absent(self) -> None:
        rec = _record(retrieved_utc="2026-03-20T10:00:00Z")
        dt = normalize_source_time(rec)
        self.assertEqual(dt.hour, 10)

    # --- UTC normalisation ---

    def test_z_suffix_accepted(self) -> None:
        rec = _record(retrieved_utc="2026-03-20T12:00:00Z")
        dt = normalize_source_time(rec)
        self.assertEqual(dt.tzinfo, _UTC)
        self.assertEqual(dt.hour, 12)

    def test_plus_offset_normalised_to_utc(self) -> None:
        # +02:00 → UTC is 2 hours earlier
        rec = _record(retrieved_utc="2026-03-20T14:00:00+02:00")
        dt = normalize_source_time(rec)
        self.assertEqual(dt.tzinfo, _UTC)
        self.assertEqual(dt.hour, 12)

    def test_observation_time_with_offset_normalised(self) -> None:
        rec = _record(
            observation_time_utc="2026-03-20T16:00:00+04:00",
        )
        dt = normalize_source_time(rec)
        self.assertEqual(dt.tzinfo, _UTC)
        self.assertEqual(dt.hour, 12)

    # --- rejection cases ---

    def test_naive_retrieved_utc_raises_value_error(self) -> None:
        rec = _record(retrieved_utc="2026-03-20T12:00:00")  # no tz
        with self.assertRaises(ValueError):
            normalize_source_time(rec)

    def test_naive_observation_time_raises_value_error(self) -> None:
        rec = _record(observation_time_utc="2026-03-20T12:00:00")
        with self.assertRaises(ValueError):
            normalize_source_time(rec)

    def test_invalid_timestamp_string_raises_value_error(self) -> None:
        rec = _record(retrieved_utc="not-a-date")
        with self.assertRaises(ValueError):
            normalize_source_time(rec)

    def test_no_time_fields_raises_value_error(self) -> None:
        rec = {"source_id": "src-x", "repository": "r"}
        with self.assertRaises(ValueError):
            normalize_source_time(rec)

    def test_empty_retrieved_utc_raises_value_error(self) -> None:
        rec = _record(retrieved_utc="")
        with self.assertRaises(ValueError):
            normalize_source_time(rec)

    def test_non_string_retrieved_utc_raises_value_error(self) -> None:
        rec = {"source_id": "s", "retrieved_utc": 12345}
        with self.assertRaises(ValueError):
            normalize_source_time(rec)

    def test_invalid_observation_falls_through_to_retrieved_utc(self) -> None:
        """An invalid observation_time_utc should propagate its ValueError."""
        rec = _record(
            retrieved_utc="2026-03-20T12:00:00Z",
            observation_time_utc="bad-value",
        )
        with self.assertRaises(ValueError):
            normalize_source_time(rec)


# ---------------------------------------------------------------------------
# collect_consensus_inputs
# ---------------------------------------------------------------------------

class TestCollectConsensusInputs(unittest.TestCase):
    """Unit tests for collect_consensus_inputs."""

    def test_all_valid_returns_empty_invalid(self) -> None:
        records = [
            _record(source_id="a", retrieved_utc="2026-03-20T10:00:00Z"),
            _record(source_id="b", retrieved_utc="2026-03-20T11:00:00Z"),
        ]
        result = collect_consensus_inputs(records)
        self.assertEqual(result["invalid_count"], 0)
        self.assertEqual(len(result["invalid_records"]), 0)
        self.assertEqual(len(result["valid_records"]), 2)

    def test_no_time_fields_rejected(self) -> None:
        bad = {"source_id": "bad", "repository": "r"}
        result = collect_consensus_inputs([bad])
        self.assertEqual(result["invalid_count"], 1)
        self.assertEqual(len(result["valid_records"]), 0)

    def test_invalid_count_matches_invalid_records_length(self) -> None:
        bad1 = {"source_id": "b1", "repository": "r"}
        bad2 = {"source_id": "b2", "repository": "r"}
        good = _record(source_id="g", retrieved_utc="2026-03-20T10:00:00Z")
        result = collect_consensus_inputs([bad1, bad2, good])
        self.assertEqual(result["invalid_count"], 2)
        self.assertEqual(len(result["invalid_records"]), 2)
        self.assertEqual(len(result["valid_records"]), 1)

    def test_invalid_reasons_has_one_entry_per_rejection(self) -> None:
        bad = {"source_id": "b", "repository": "r"}
        result = collect_consensus_inputs([bad])
        self.assertEqual(len(result["invalid_reasons"]), 1)
        self.assertIsInstance(result["invalid_reasons"][0], str)

    def test_non_dict_record_rejected_with_reason(self) -> None:
        result = collect_consensus_inputs(["not-a-dict"])
        self.assertEqual(result["invalid_count"], 1)
        self.assertIn("source_id", result["invalid_records"][0])
        self.assertIn("reason", result["invalid_records"][0])

    def test_source_id_captured_in_invalid_records(self) -> None:
        bad = {"source_id": "known-bad", "repository": "r"}
        result = collect_consensus_inputs([bad])
        self.assertEqual(result["invalid_records"][0]["source_id"], "known-bad")

    def test_naive_timestamp_rejected_no_silent_discard(self) -> None:
        rec = _record(retrieved_utc="2026-03-20T12:00:00")  # naive
        result = collect_consensus_inputs([rec])
        self.assertEqual(result["invalid_count"], 1)
        self.assertEqual(len(result["valid_records"]), 0)

    def test_empty_input_returns_empty_results(self) -> None:
        result = collect_consensus_inputs([])
        self.assertEqual(result["invalid_count"], 0)
        self.assertEqual(result["valid_records"], [])
        self.assertEqual(result["invalid_records"], [])

    def test_result_has_all_required_keys(self) -> None:
        result = collect_consensus_inputs([])
        for key in ("valid_records", "invalid_records", "invalid_count",
                    "invalid_reasons"):
            self.assertIn(key, result, f"Key '{key}' missing from result")


# ---------------------------------------------------------------------------
# compute_time_span
# ---------------------------------------------------------------------------

class TestComputeTimeSpan(unittest.TestCase):
    """Unit tests for compute_time_span."""

    def test_single_record_span_is_zero(self) -> None:
        rec = _record(retrieved_utc="2026-03-20T12:00:00Z")
        result = compute_time_span([rec])
        self.assertEqual(result["time_span_seconds"], 0.0)

    def test_two_records_span_computed_correctly(self) -> None:
        r1 = _record(source_id="a", retrieved_utc="2026-03-20T10:00:00Z")
        r2 = _record(source_id="b", retrieved_utc="2026-03-20T11:00:00Z")
        result = compute_time_span([r1, r2])
        self.assertAlmostEqual(result["time_span_seconds"], 3600.0)

    def test_earliest_and_latest_utc_set(self) -> None:
        r1 = _record(source_id="a", retrieved_utc="2026-03-20T08:00:00Z")
        r2 = _record(source_id="b", retrieved_utc="2026-03-20T20:00:00Z")
        result = compute_time_span([r1, r2])
        self.assertIsNotNone(result["earliest_utc"])
        self.assertIsNotNone(result["latest_utc"])
        self.assertEqual(result["earliest_utc"].hour, 8)
        self.assertEqual(result["latest_utc"].hour, 20)

    def test_returned_datetimes_are_utc(self) -> None:
        r1 = _record(source_id="a", retrieved_utc="2026-03-20T10:00:00Z")
        r2 = _record(source_id="b", retrieved_utc="2026-03-20T11:00:00Z")
        result = compute_time_span([r1, r2])
        self.assertEqual(result["earliest_utc"].tzinfo, _UTC)
        self.assertEqual(result["latest_utc"].tzinfo, _UTC)

    def test_mixed_offsets_normalised_before_comparison(self) -> None:
        # +02:00 → 08:00 UTC; 08:30 UTC later
        r1 = _record(source_id="a", retrieved_utc="2026-03-20T10:00:00+02:00")
        r2 = _record(source_id="b", retrieved_utc="2026-03-20T08:30:00Z")
        result = compute_time_span([r1, r2])
        self.assertAlmostEqual(result["time_span_seconds"], 1800.0)

    def test_observation_time_preferred_over_retrieved(self) -> None:
        rec = _record(
            retrieved_utc="2026-03-20T10:00:00Z",
            observation_time_utc="2026-03-20T06:00:00Z",
        )
        result = compute_time_span([rec])
        self.assertEqual(result["earliest_utc"].hour, 6)

    def test_empty_input_returns_none_times(self) -> None:
        result = compute_time_span([])
        self.assertIsNone(result["earliest_utc"])
        self.assertIsNone(result["latest_utc"])
        self.assertEqual(result["time_span_seconds"], 0.0)

    def test_result_has_all_required_keys(self) -> None:
        result = compute_time_span([])
        for key in ("earliest_utc", "latest_utc", "time_span_seconds"):
            self.assertIn(key, result, f"Key '{key}' missing from result")


# ---------------------------------------------------------------------------
# compare_numeric_field
# ---------------------------------------------------------------------------

class TestCompareNumericField(unittest.TestCase):
    """Unit tests for compare_numeric_field."""

    def _records_with_eccentricity(self, values: list) -> list[dict]:
        """Build records whose payload.orbital.eccentricity = each value."""
        records = []
        for i, val in enumerate(values):
            payload: dict = {}
            if val is not None:
                payload = {"orbital": {"eccentricity": val}}
            records.append(_record(source_id=f"s{i}", payload=payload))
        return records

    # --- insufficient cases ---

    def test_zero_values_returns_insufficient(self) -> None:
        records = [_record(source_id="s", payload={})]
        result = compare_numeric_field(records, "orbital.eccentricity")
        self.assertEqual(result["status"], "insufficient")
        self.assertEqual(result["count"], 0)

    def test_single_value_returns_insufficient(self) -> None:
        records = self._records_with_eccentricity([0.5])
        result = compare_numeric_field(records, "orbital.eccentricity")
        self.assertEqual(result["status"], "insufficient")
        self.assertEqual(result["count"], 1)

    def test_non_numeric_values_skipped(self) -> None:
        rec1 = _record(source_id="a", payload={"orbital": {"eccentricity": "bad"}})
        rec2 = _record(source_id="b", payload={"orbital": {"eccentricity": None}})
        result = compare_numeric_field([rec1, rec2], "orbital.eccentricity")
        self.assertEqual(result["status"], "insufficient")

    def test_bool_values_are_rejected(self) -> None:
        """Booleans are subclass of int in Python; they must be excluded."""
        rec1 = _record(source_id="a", payload={"orbital": {"eccentricity": True}})
        rec2 = _record(source_id="b", payload={"orbital": {"eccentricity": False}})
        result = compare_numeric_field([rec1, rec2], "orbital.eccentricity")
        self.assertEqual(result["status"], "insufficient")

    # --- aligned ---

    def test_identical_values_are_aligned(self) -> None:
        records = self._records_with_eccentricity([0.5, 0.5])
        result = compare_numeric_field(records, "orbital.eccentricity")
        self.assertEqual(result["status"], "aligned")
        self.assertEqual(result["max_delta"], 0.0)

    def test_delta_below_aligned_threshold_is_aligned(self) -> None:
        # Use a delta clearly below the threshold to avoid floating-point
        # boundary ambiguity (e.g. 0.51 - 0.5 ≈ 1.0e-17 above 0.01 in IEEE 754).
        delta = CONSENSUS_NUMERIC_ALIGNED_MAX_DELTA * 0.5
        records = self._records_with_eccentricity([0.5, 0.5 + delta])
        result = compare_numeric_field(records, "orbital.eccentricity")
        self.assertEqual(result["status"], "aligned")

    # --- weakly_divergent ---

    def test_delta_just_above_aligned_is_weakly_divergent(self) -> None:
        delta = CONSENSUS_NUMERIC_ALIGNED_MAX_DELTA + 0.001
        records = self._records_with_eccentricity([0.5, 0.5 + delta])
        result = compare_numeric_field(records, "orbital.eccentricity")
        self.assertEqual(result["status"], "weakly_divergent")

    def test_delta_at_weak_boundary_is_weakly_divergent(self) -> None:
        records = self._records_with_eccentricity(
            [0.5, 0.5 + CONSENSUS_NUMERIC_WEAK_MAX_DELTA]
        )
        result = compare_numeric_field(records, "orbital.eccentricity")
        self.assertEqual(result["status"], "weakly_divergent")

    # --- divergent ---

    def test_delta_above_weak_is_divergent(self) -> None:
        delta = CONSENSUS_NUMERIC_WEAK_MAX_DELTA + 0.001
        records = self._records_with_eccentricity([0.5, 0.5 + delta])
        result = compare_numeric_field(records, "orbital.eccentricity")
        self.assertEqual(result["status"], "divergent")

    # --- statistics ---

    def test_min_max_mean_max_delta_computed(self) -> None:
        records = self._records_with_eccentricity([0.4, 0.5, 0.6])
        result = compare_numeric_field(records, "orbital.eccentricity")
        self.assertAlmostEqual(result["min"], 0.4)
        self.assertAlmostEqual(result["max"], 0.6)
        self.assertAlmostEqual(result["mean"], 0.5)
        self.assertAlmostEqual(result["max_delta"], 0.2)
        self.assertEqual(result["count"], 3)

    def test_missing_field_in_one_source_does_not_fail(self) -> None:
        """Consensus must not abort when a field is absent in one record."""
        rec_with = _record(source_id="a", payload={"orbital": {"eccentricity": 0.5}})
        rec_without = _record(source_id="b", payload={})
        result = compare_numeric_field([rec_with, rec_without], "orbital.eccentricity")
        # Only 1 value → insufficient; critically, no exception raised
        self.assertEqual(result["status"], "insufficient")

    def test_missing_payload_key_does_not_fail(self) -> None:
        rec = _record(source_id="a")  # no payload key at all
        result = compare_numeric_field([rec], "orbital.eccentricity")
        self.assertEqual(result["status"], "insufficient")

    def test_integer_values_accepted(self) -> None:
        rec1 = _record(source_id="a", payload={"orbital": {"inclination": 30}})
        rec2 = _record(source_id="b", payload={"orbital": {"inclination": 31}})
        result = compare_numeric_field([rec1, rec2], "orbital.inclination")
        self.assertNotEqual(result["status"], "insufficient")

    def test_result_has_all_required_keys_when_sufficient(self) -> None:
        records = self._records_with_eccentricity([0.5, 0.6])
        result = compare_numeric_field(records, "orbital.eccentricity")
        for key in ("count", "min", "max", "mean", "max_delta", "status"):
            self.assertIn(key, result, f"Key '{key}' missing")

    def test_deeply_nested_field_resolved(self) -> None:
        rec1 = _record(source_id="a", payload={"orbital": {"perihelion_distance": 0.75}})
        rec2 = _record(source_id="b", payload={"orbital": {"perihelion_distance": 0.76}})
        result = compare_numeric_field([rec1, rec2], "orbital.perihelion_distance")
        self.assertIn("count", result)
        self.assertEqual(result["count"], 2)


# ---------------------------------------------------------------------------
# build_consensus_record
# ---------------------------------------------------------------------------

class TestBuildConsensusRecord(unittest.TestCase):
    """Unit tests for build_consensus_record."""

    def _make_records(self, timestamps: list[str]) -> list[dict]:
        return [
            _record(source_id=f"s{i}", retrieved_utc=ts)
            for i, ts in enumerate(timestamps)
        ]

    # --- output shape ---

    def test_result_has_all_required_keys(self) -> None:
        records = self._make_records(["2026-03-20T10:00:00Z", "2026-03-20T11:00:00Z"])
        result = build_consensus_record(records, [], [])
        for key in (
            "consensus_method",
            "sources_considered",
            "sources_valid",
            "sources_invalid",
            "selected_time_utc",
            "time_span_seconds",
            "time_alignment_status",
            "field_comparisons",
            "invalid_sources",
        ):
            self.assertIn(key, result, f"Key '{key}' missing from result")

    def test_consensus_method_value(self) -> None:
        result = build_consensus_record([], [], [])
        self.assertEqual(result["consensus_method"], "multi_source_true_time")

    # --- source counts ---

    def test_sources_considered_is_sum_of_valid_and_invalid(self) -> None:
        valid = self._make_records(["2026-03-20T10:00:00Z", "2026-03-20T11:00:00Z"])
        invalid = [{"source_id": "bad", "reason": "missing time"}]
        result = build_consensus_record(valid, invalid, [])
        self.assertEqual(result["sources_considered"], 3)
        self.assertEqual(result["sources_valid"], 2)
        self.assertEqual(result["sources_invalid"], 1)

    def test_invalid_sources_propagated(self) -> None:
        invalid = [{"source_id": "bad", "reason": "missing time"}]
        result = build_consensus_record([], invalid, [])
        self.assertEqual(result["invalid_sources"], invalid)

    # --- time alignment ---

    def test_time_aligned_within_threshold(self) -> None:
        """Two records 30 minutes apart → aligned."""
        r1 = _record(source_id="a", retrieved_utc="2026-03-20T10:00:00Z")
        r2 = _record(source_id="b", retrieved_utc="2026-03-20T10:30:00Z")
        result = build_consensus_record([r1, r2], [], [])
        self.assertEqual(result["time_alignment_status"], "aligned")

    def test_time_weakly_divergent(self) -> None:
        """12 hour spread → weakly_divergent."""
        r1 = _record(source_id="a", retrieved_utc="2026-03-20T00:00:00Z")
        r2 = _record(source_id="b", retrieved_utc="2026-03-20T12:00:00Z")
        result = build_consensus_record([r1, r2], [], [])
        self.assertEqual(result["time_alignment_status"], "weakly_divergent")

    def test_time_divergent(self) -> None:
        """More than 24 hours apart → divergent."""
        r1 = _record(source_id="a", retrieved_utc="2026-03-18T00:00:00Z")
        r2 = _record(source_id="b", retrieved_utc="2026-03-20T00:00:00Z")
        result = build_consensus_record([r1, r2], [], [])
        self.assertEqual(result["time_alignment_status"], "divergent")

    def test_single_valid_record_is_aligned(self) -> None:
        """One valid record has zero spread → aligned."""
        r = _record(retrieved_utc="2026-03-20T10:00:00Z")
        result = build_consensus_record([r], [], [])
        self.assertEqual(result["time_alignment_status"], "aligned")

    def test_no_valid_records_is_divergent(self) -> None:
        result = build_consensus_record([], [], [])
        self.assertEqual(result["time_alignment_status"], "divergent")

    def test_selected_time_utc_is_latest_iso_string(self) -> None:
        r1 = _record(source_id="a", retrieved_utc="2026-03-20T10:00:00Z")
        r2 = _record(source_id="b", retrieved_utc="2026-03-20T11:00:00Z")
        result = build_consensus_record([r1, r2], [], [])
        # selected_time_utc must be an ISO-8601 string
        self.assertIsInstance(result["selected_time_utc"], str)
        self.assertIn("11:00", result["selected_time_utc"])

    def test_selected_time_utc_is_none_when_no_valid_records(self) -> None:
        result = build_consensus_record([], [], [])
        self.assertIsNone(result["selected_time_utc"])

    # --- field comparisons ---

    def test_field_comparisons_included_for_each_field(self) -> None:
        fields = ["orbital.eccentricity", "orbital.inclination"]
        r1 = _record(source_id="a", retrieved_utc="2026-03-20T10:00:00Z",
                     payload=_orbital_payload(eccentricity=0.5, inclination=30.0))
        r2 = _record(source_id="b", retrieved_utc="2026-03-20T11:00:00Z",
                     payload=_orbital_payload(eccentricity=0.5, inclination=30.0))
        result = build_consensus_record([r1, r2], [], compared_fields=fields)
        self.assertIn("orbital.eccentricity", result["field_comparisons"])
        self.assertIn("orbital.inclination", result["field_comparisons"])

    def test_default_fields_used_when_none_provided(self) -> None:
        result = build_consensus_record([], [], compared_fields=None)
        for field in DEFAULT_COMPARED_FIELDS:
            self.assertIn(field, result["field_comparisons"])

    def test_field_comparison_status_propagated(self) -> None:
        """Verify that numeric comparison results are correctly embedded."""
        r1 = _record(source_id="a", retrieved_utc="2026-03-20T10:00:00Z",
                     payload=_orbital_payload(eccentricity=0.5))
        r2 = _record(source_id="b", retrieved_utc="2026-03-20T11:00:00Z",
                     payload=_orbital_payload(eccentricity=0.5))
        result = build_consensus_record([r1, r2], [], ["orbital.eccentricity"])
        fc = result["field_comparisons"]["orbital.eccentricity"]
        self.assertEqual(fc["status"], "aligned")

    # --- integration with collect_consensus_inputs ---

    def test_integrate_with_collect_consensus_inputs(self) -> None:
        """build_consensus_record accepts output of collect_consensus_inputs."""
        records = [
            _record(source_id="good", retrieved_utc="2026-03-20T10:00:00Z"),
            {"source_id": "bad"},  # no time fields
        ]
        collected = collect_consensus_inputs(records)
        result = build_consensus_record(
            collected["valid_records"],
            collected["invalid_records"],
            compared_fields=[],
        )
        self.assertEqual(result["sources_valid"], 1)
        self.assertEqual(result["sources_invalid"], 1)
        self.assertEqual(result["sources_considered"], 2)
        self.assertEqual(result["invalid_sources"][0]["source_id"], "bad")

    # --- threshold constants sanity ---

    def test_time_aligned_threshold_below_weak_threshold(self) -> None:
        self.assertLess(
            CONSENSUS_TIME_ALIGNED_MAX_SECONDS,
            CONSENSUS_TIME_WEAK_MAX_SECONDS,
        )

    def test_numeric_aligned_threshold_below_weak_threshold(self) -> None:
        self.assertLess(
            CONSENSUS_NUMERIC_ALIGNED_MAX_DELTA,
            CONSENSUS_NUMERIC_WEAK_MAX_DELTA,
        )


if __name__ == "__main__":
    unittest.main()
