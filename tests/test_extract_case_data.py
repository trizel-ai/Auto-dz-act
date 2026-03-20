"""Tests for the TRIZEL validation bridge extraction script.

Covers extract_case_data.py behaviour:
- _is_placeholder
- _is_dual_source_entry
- validate_entry_status
- _validate_source_paths
- validate_dual_source_entry
- validate_entry (legacy single-source)
- _copy_files_to_dir
- extract_files (legacy)
- extract_dual_source_files
- check_workspace_readiness
- update_provenance (legacy)
- update_dual_source_provenance
- run_extraction (integration, dual-source and legacy)
- main() CLI entry point
"""

import json
import logging
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from validation.bridge.extract_case_data import (
    EXTRACTION_METHOD,
    _is_placeholder,
    _is_dual_source_entry,
    validate_entry_status,
    _validate_source_paths,
    validate_dual_source_entry,
    validate_entry,
    _copy_files_to_dir,
    extract_files,
    extract_dual_source_files,
    check_workspace_readiness,
    update_provenance,
    update_dual_source_provenance,
    load_registry,
    find_registry_entry,
    run_extraction,
    main,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_logger() -> logging.Logger:
    """Return a silent logger for use in tests."""
    logger = logging.getLogger(f"test_extract_{id(object())}")
    logger.addHandler(logging.NullHandler())
    logger.propagate = False
    return logger


def _write_json(data: dict, suffix: str = ".json") -> str:
    """Write *data* to a temp file and return its path."""
    fh = tempfile.NamedTemporaryFile(
        mode="w", suffix=suffix, delete=False, encoding="utf-8"
    )
    json.dump(data, fh, indent=2)
    fh.close()
    return fh.name


def _make_registry(
    case_id: str = "case-test",
    status: str = "approved",
    dual_source: bool = True,
    raw_paths: list[str] | None = None,
    normalized_paths: list[str] | None = None,
    source_paths: list[str] | None = None,
    raw_dir: str = "raw",
    normalized_dir: str = "normalized",
) -> dict:
    """Build a minimal registry dict for testing."""
    if dual_source:
        entry = {
            "case_id": case_id,
            "raw_source_repository": "abdelkader-omran/AUTO-DZ-ACT-3I-ATLAS-DAILY",
            "normalized_source_repository": "abdelkader-omran/AUTO-DZ-ACT-ANALYSIS-3I-ATLAS",
            "allowed_raw_source_paths": raw_paths or [],
            "allowed_normalized_source_paths": normalized_paths or [],
            "target_case_raw_dir": raw_dir,
            "target_case_normalized_dir": normalized_dir,
            "extraction_status": status,
            "governance_reference": "validation/bridge/bridge_rules.md",
        }
    else:
        entry = {
            "case_id": case_id,
            "source_repository": "LEGACY-REPO",
            "source_organization": "trizel-ai",
            "allowed_source_paths": source_paths or [],
            "target_case_raw_dir": raw_dir,
            "extraction_status": status,
        }
    return {"registry_version": "1.1", "entries": [entry]}


def _make_workspace_registry(
    confirmed: bool = True,
    placeholder: bool = False,
) -> dict:
    """Build a minimal workspace registry dict for testing."""
    if placeholder:
        path_value = "PLACEHOLDER: not yet confirmed"
        status = "pending"
    elif confirmed:
        path_value = "/confirmed/path"
        status = "confirmed"
    else:
        path_value = "/missing/path"
        status = "confirmed"

    return {
        "workspace_version": "1.0",
        "repositories": [
            {
                "repository": "trizel-ai/Auto-dz-act",
                "expected_local_path": path_value,
                "local_path_status": status,
                "visibility_required": True,
            },
            {
                "repository": "abdelkader-omran/AUTO-DZ-ACT-3I-ATLAS-DAILY",
                "expected_local_path": path_value,
                "local_path_status": status,
                "visibility_required": True,
            },
            {
                "repository": "abdelkader-omran/AUTO-DZ-ACT-ANALYSIS-3I-ATLAS",
                "expected_local_path": path_value,
                "local_path_status": status,
                "visibility_required": True,
            },
        ],
    }


# ---------------------------------------------------------------------------
# _is_placeholder
# ---------------------------------------------------------------------------

class TestIsPlaceholder(unittest.TestCase):
    def test_placeholder_returns_true(self):
        self.assertTrue(_is_placeholder("PLACEHOLDER: something"))

    def test_placeholder_case_insensitive(self):
        self.assertTrue(_is_placeholder("placeholder: lower"))

    def test_real_path_returns_false(self):
        self.assertFalse(_is_placeholder("/some/real/path.csv"))

    def test_empty_string_returns_false(self):
        self.assertFalse(_is_placeholder(""))


# ---------------------------------------------------------------------------
# _is_dual_source_entry
# ---------------------------------------------------------------------------

class TestIsDualSourceEntry(unittest.TestCase):
    def test_dual_source_returns_true(self):
        entry = {
            "raw_source_repository": "org/DAILY",
            "normalized_source_repository": "org/ANALYSIS",
        }
        self.assertTrue(_is_dual_source_entry(entry))

    def test_missing_normalized_returns_false(self):
        entry = {"raw_source_repository": "org/DAILY"}
        self.assertFalse(_is_dual_source_entry(entry))

    def test_missing_raw_returns_false(self):
        entry = {"normalized_source_repository": "org/ANALYSIS"}
        self.assertFalse(_is_dual_source_entry(entry))

    def test_empty_entry_returns_false(self):
        self.assertFalse(_is_dual_source_entry({}))


# ---------------------------------------------------------------------------
# validate_entry_status
# ---------------------------------------------------------------------------

class TestValidateEntryStatus(unittest.TestCase):
    def test_approved_does_not_raise(self):
        entry = {"case_id": "test", "extraction_status": "approved"}
        validate_entry_status(entry)  # should not raise

    def test_non_approved_raises_runtime_error(self):
        entry = {"case_id": "test", "extraction_status": "pending_workspace_resolution"}
        with self.assertRaises(RuntimeError) as ctx:
            validate_entry_status(entry)
        self.assertIn("pending_workspace_resolution", str(ctx.exception))

    def test_missing_status_raises_runtime_error(self):
        with self.assertRaises(RuntimeError):
            validate_entry_status({"case_id": "test"})


# ---------------------------------------------------------------------------
# _validate_source_paths
# ---------------------------------------------------------------------------

class TestValidateSourcePaths(unittest.TestCase):
    def setUp(self):
        self.logger = _make_logger()

    def test_empty_paths_raises(self):
        with self.assertRaises(RuntimeError) as ctx:
            _validate_source_paths("c1", [], "raw", "/tmp", self.logger)
        self.assertIn("no allowed_raw_source_paths", str(ctx.exception))

    def test_placeholder_path_raises(self):
        with self.assertRaises(RuntimeError) as ctx:
            _validate_source_paths(
                "c1", ["PLACEHOLDER: not confirmed"], "raw", "/tmp", self.logger
            )
        self.assertIn("placeholder", str(ctx.exception).lower())

    def test_missing_file_raises(self):
        with self.assertRaises(RuntimeError) as ctx:
            _validate_source_paths(
                "c1", ["nonexistent/path.csv"], "raw", "/tmp", self.logger
            )
        self.assertIn("does not exist", str(ctx.exception))

    def test_existing_file_returns_path(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            src = os.path.join(tmpdir, "data.csv")
            with open(src, "w") as f:
                f.write("data")
            result = _validate_source_paths(
                "c1", ["data.csv"], "raw", tmpdir, self.logger
            )
        self.assertEqual(result, ["data.csv"])


# ---------------------------------------------------------------------------
# validate_dual_source_entry
# ---------------------------------------------------------------------------

class TestValidateDualSourceEntry(unittest.TestCase):
    def setUp(self):
        self.logger = _make_logger()

    def test_non_approved_status_raises(self):
        entry = {
            "case_id": "test",
            "raw_source_repository": "org/DAILY",
            "normalized_source_repository": "org/ANALYSIS",
            "allowed_raw_source_paths": [],
            "allowed_normalized_source_paths": [],
            "extraction_status": "pending",
        }
        with self.assertRaises(RuntimeError):
            validate_dual_source_entry(entry, "/tmp", self.logger)

    def test_approved_with_valid_paths_returns_both_lists(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            raw_file = os.path.join(tmpdir, "raw.csv")
            norm_file = os.path.join(tmpdir, "norm.csv")
            for f in (raw_file, norm_file):
                with open(f, "w") as fh:
                    fh.write("x")
            entry = {
                "case_id": "test",
                "raw_source_repository": "org/DAILY",
                "normalized_source_repository": "org/ANALYSIS",
                "allowed_raw_source_paths": ["raw.csv"],
                "allowed_normalized_source_paths": ["norm.csv"],
                "extraction_status": "approved",
            }
            raw_paths, norm_paths = validate_dual_source_entry(
                entry, tmpdir, self.logger
            )
        self.assertEqual(raw_paths, ["raw.csv"])
        self.assertEqual(norm_paths, ["norm.csv"])


# ---------------------------------------------------------------------------
# validate_entry (legacy single-source)
# ---------------------------------------------------------------------------

class TestValidateEntry(unittest.TestCase):
    def setUp(self):
        self.logger = _make_logger()

    def test_non_approved_raises(self):
        entry = {
            "case_id": "c1",
            "allowed_source_paths": [],
            "extraction_status": "pending",
        }
        with self.assertRaises(RuntimeError):
            validate_entry(entry, "/tmp", self.logger)

    def test_approved_with_existing_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            src = os.path.join(tmpdir, "file.csv")
            with open(src, "w") as f:
                f.write("x")
            entry = {
                "case_id": "c1",
                "allowed_source_paths": ["file.csv"],
                "extraction_status": "approved",
            }
            result = validate_entry(entry, tmpdir, self.logger)
        self.assertEqual(result, ["file.csv"])


# ---------------------------------------------------------------------------
# _copy_files_to_dir
# ---------------------------------------------------------------------------

class TestCopyFilesToDir(unittest.TestCase):
    def setUp(self):
        self.logger = _make_logger()

    def test_copies_file_to_target_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            src_dir = os.path.join(tmpdir, "src")
            dst_dir_rel = "dst"
            os.makedirs(src_dir)
            src_file = os.path.join(src_dir, "data.csv")
            with open(src_file, "w") as f:
                f.write("content")

            records = _copy_files_to_dir(
                case_id="test",
                source_paths=["src/data.csv"],
                target_dir_rel=dst_dir_rel,
                repo_root=tmpdir,
                label="raw",
                logger=self.logger,
            )

            dst = os.path.join(tmpdir, dst_dir_rel, "src__data.csv")
            self.assertTrue(os.path.isfile(dst))
            self.assertEqual(len(records), 1)
            self.assertEqual(records[0]["source_path"], "src/data.csv")

    def test_collision_raises_runtime_error(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create two source paths that map to the same destination name.
            # Since _destination_filename replaces / and os.sep with __, both
            # "a/b.csv" and "a__b.csv" map to "a__b.csv".  We can create that
            # scenario with explicit duplicate entries instead.
            src = os.path.join(tmpdir, "data.csv")
            with open(src, "w") as f:
                f.write("x")

            with self.assertRaises(RuntimeError) as ctx:
                _copy_files_to_dir(
                    case_id="test",
                    source_paths=["data.csv", "data.csv"],
                    target_dir_rel="dst",
                    repo_root=tmpdir,
                    label="raw",
                    logger=self.logger,
                )
            self.assertIn("collision", str(ctx.exception).lower())

    def test_missing_source_raises_runtime_error(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with self.assertRaises(RuntimeError):
                _copy_files_to_dir(
                    case_id="test",
                    source_paths=["nonexistent.csv"],
                    target_dir_rel="dst",
                    repo_root=tmpdir,
                    label="raw",
                    logger=self.logger,
                )


# ---------------------------------------------------------------------------
# extract_files (legacy)
# ---------------------------------------------------------------------------

class TestExtractFiles(unittest.TestCase):
    def setUp(self):
        self.logger = _make_logger()

    def test_copies_to_raw_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            src = os.path.join(tmpdir, "obs.csv")
            with open(src, "w") as f:
                f.write("data")
            entry = {
                "case_id": "test",
                "target_case_raw_dir": "raw",
            }
            records = extract_files(entry, ["obs.csv"], tmpdir, self.logger)
            self.assertTrue(
                os.path.isfile(os.path.join(tmpdir, "raw", "obs.csv"))
            )
            self.assertEqual(len(records), 1)


# ---------------------------------------------------------------------------
# extract_dual_source_files
# ---------------------------------------------------------------------------

class TestExtractDualSourceFiles(unittest.TestCase):
    def setUp(self):
        self.logger = _make_logger()

    def test_copies_raw_and_normalized_to_separate_dirs(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            raw_src = os.path.join(tmpdir, "raw_obs.csv")
            norm_src = os.path.join(tmpdir, "norm_obs.csv")
            with open(raw_src, "w") as f:
                f.write("raw")
            with open(norm_src, "w") as f:
                f.write("norm")

            entry = {
                "case_id": "test",
                "target_case_raw_dir": "raw",
                "target_case_normalized_dir": "normalized",
            }
            raw_records, norm_records = extract_dual_source_files(
                entry,
                raw_paths=["raw_obs.csv"],
                normalized_paths=["norm_obs.csv"],
                repo_root=tmpdir,
                logger=self.logger,
            )

            self.assertTrue(
                os.path.isfile(os.path.join(tmpdir, "raw", "raw_obs.csv"))
            )
            self.assertTrue(
                os.path.isfile(os.path.join(tmpdir, "normalized", "norm_obs.csv"))
            )
            self.assertEqual(len(raw_records), 1)
            self.assertEqual(len(norm_records), 1)

    def test_raw_and_normalized_dirs_are_separate(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            raw_src = os.path.join(tmpdir, "r.csv")
            norm_src = os.path.join(tmpdir, "n.csv")
            for f in (raw_src, norm_src):
                with open(f, "w") as fh:
                    fh.write("x")
            entry = {
                "case_id": "test",
                "target_case_raw_dir": "raw",
                "target_case_normalized_dir": "norm_dir",
            }
            extract_dual_source_files(
                entry,
                raw_paths=["r.csv"],
                normalized_paths=["n.csv"],
                repo_root=tmpdir,
                logger=self.logger,
            )
            # raw file must NOT appear in normalized dir and vice versa
            self.assertFalse(
                os.path.isfile(os.path.join(tmpdir, "norm_dir", "r.csv"))
            )
            self.assertFalse(
                os.path.isfile(os.path.join(tmpdir, "raw", "n.csv"))
            )


# ---------------------------------------------------------------------------
# check_workspace_readiness
# ---------------------------------------------------------------------------

class TestCheckWorkspaceReadiness(unittest.TestCase):
    def setUp(self):
        self.logger = _make_logger()

    def test_missing_workspace_file_raises_file_not_found(self):
        with self.assertRaises(FileNotFoundError):
            check_workspace_readiness("/nonexistent/repositories.json", self.logger)

    def test_placeholder_paths_raise_runtime_error(self):
        workspace = _make_workspace_registry(placeholder=True)
        path = _write_json(workspace)
        try:
            with self.assertRaises(RuntimeError) as ctx:
                check_workspace_readiness(path, self.logger)
            self.assertIn("placeholder", str(ctx.exception).lower())
        finally:
            os.unlink(path)

    def test_confirmed_but_missing_dir_raises_runtime_error(self):
        workspace = _make_workspace_registry(confirmed=False, placeholder=False)
        path = _write_json(workspace)
        try:
            with self.assertRaises(RuntimeError):
                check_workspace_readiness(path, self.logger)
        finally:
            os.unlink(path)

    def test_confirmed_existing_dirs_passes(self):
        with tempfile.TemporaryDirectory() as d1, \
                tempfile.TemporaryDirectory() as d2, \
                tempfile.TemporaryDirectory() as d3:
            workspace = {
                "workspace_version": "1.0",
                "repositories": [
                    {
                        "repository": "trizel-ai/Auto-dz-act",
                        "expected_local_path": d1,
                        "local_path_status": "confirmed",
                        "visibility_required": True,
                    },
                    {
                        "repository": "abdelkader-omran/AUTO-DZ-ACT-3I-ATLAS-DAILY",
                        "expected_local_path": d2,
                        "local_path_status": "confirmed",
                        "visibility_required": True,
                    },
                    {
                        "repository": "abdelkader-omran/AUTO-DZ-ACT-ANALYSIS-3I-ATLAS",
                        "expected_local_path": d3,
                        "local_path_status": "confirmed",
                        "visibility_required": True,
                    },
                ],
            }
            ws_path = _write_json(workspace)
            try:
                check_workspace_readiness(ws_path, self.logger)  # should not raise
            finally:
                os.unlink(ws_path)

    def test_optional_repos_not_required(self):
        with tempfile.TemporaryDirectory() as d1:
            workspace = {
                "workspace_version": "1.0",
                "repositories": [
                    {
                        "repository": "trizel-ai/Auto-dz-act",
                        "expected_local_path": d1,
                        "local_path_status": "confirmed",
                        "visibility_required": True,
                    },
                    {
                        "repository": "optional/repo",
                        "expected_local_path": "PLACEHOLDER: optional",
                        "local_path_status": "pending",
                        "visibility_required": False,
                    },
                ],
            }
            ws_path = _write_json(workspace)
            try:
                check_workspace_readiness(ws_path, self.logger)  # should not raise
            finally:
                os.unlink(ws_path)


# ---------------------------------------------------------------------------
# load_registry and find_registry_entry
# ---------------------------------------------------------------------------

class TestLoadRegistry(unittest.TestCase):
    def test_loads_valid_registry(self):
        path = _write_json({"registry_version": "1.1", "entries": []})
        try:
            data = load_registry(path)
            self.assertEqual(data["registry_version"], "1.1")
        finally:
            os.unlink(path)

    def test_missing_registry_raises_file_not_found(self):
        with self.assertRaises(FileNotFoundError):
            load_registry("/nonexistent/registry.json")

    def test_non_object_raises_value_error(self):
        fh = tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, encoding="utf-8"
        )
        json.dump([1, 2], fh)
        fh.close()
        try:
            with self.assertRaises(ValueError):
                load_registry(fh.name)
        finally:
            os.unlink(fh.name)


class TestFindRegistryEntry(unittest.TestCase):
    def test_finds_existing_entry(self):
        registry = _make_registry(case_id="case-001-asteroid")
        entry = find_registry_entry(registry, "case-001-asteroid")
        self.assertEqual(entry["case_id"], "case-001-asteroid")

    def test_missing_entry_raises_key_error(self):
        registry = _make_registry(case_id="case-001-asteroid")
        with self.assertRaises(KeyError):
            find_registry_entry(registry, "case-999-unknown")


# ---------------------------------------------------------------------------
# update_dual_source_provenance
# ---------------------------------------------------------------------------

class TestUpdateDualSourceProvenance(unittest.TestCase):
    def setUp(self):
        self.logger = _make_logger()

    def test_writes_provenance_with_dual_source_fields(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            raw_dir = os.path.join(tmpdir, "raw")
            entry = {
                "case_id": "test",
                "raw_source_repository": "org/DAILY",
                "normalized_source_repository": "org/ANALYSIS",
                "target_case_raw_dir": "raw",
                "governance_reference": "bridge_rules.md",
            }
            raw_records = [{"source_path": "r.csv", "destination_path": "raw/r.csv"}]
            norm_records = [{"source_path": "n.csv", "destination_path": "norm/n.csv"}]

            update_dual_source_provenance(
                entry, raw_records, norm_records, "1.1", tmpdir, self.logger
            )

            prov_path = os.path.join(tmpdir, "provenance.json")
            self.assertTrue(os.path.isfile(prov_path))
            with open(prov_path) as f:
                prov = json.load(f)

            self.assertEqual(prov["repository"], "trizel-ai/Auto-dz-act")
            self.assertEqual(prov["epistemic_layer"], "validation")
            self.assertEqual(prov["raw_source_repository"], "org/DAILY")
            self.assertEqual(
                prov["normalized_source_repository"], "org/ANALYSIS"
            )
            self.assertIn("raw", prov["source_files"])
            self.assertIn("normalized", prov["source_files"])
            self.assertEqual(prov["extraction_method"], EXTRACTION_METHOD)
            self.assertEqual(prov["workspace_resolution"], "confirmed")
            self.assertEqual(prov["governance_reference"], "bridge_rules.md")
            self.assertEqual(prov["processing_status"], "extraction_complete")

    def test_removes_legacy_fields(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            # Write a provenance with legacy fields first.
            prov_path = os.path.join(tmpdir, "provenance.json")
            with open(prov_path, "w") as f:
                json.dump({"note": "old note", "data_origin": "old"}, f)

            entry = {
                "case_id": "test",
                "raw_source_repository": "org/DAILY",
                "normalized_source_repository": "org/ANALYSIS",
                "target_case_raw_dir": "raw",
                "governance_reference": "bridge_rules.md",
            }
            update_dual_source_provenance(
                entry, [], [], "1.1", tmpdir, self.logger
            )

            with open(prov_path) as f:
                prov = json.load(f)
            self.assertNotIn("note", prov)
            self.assertNotIn("data_origin", prov)


# ---------------------------------------------------------------------------
# run_extraction — integration
# ---------------------------------------------------------------------------

class TestRunExtractionDualSource(unittest.TestCase):
    """Integration tests for run_extraction in dual-source mode."""

    def setUp(self):
        self.logger = _make_logger()

    def _setup_workspace(self, *repo_dirs) -> str:
        """Write a workspace registry with confirmed paths for all dirs."""
        repos = ["trizel-ai/Auto-dz-act",
                 "abdelkader-omran/AUTO-DZ-ACT-3I-ATLAS-DAILY",
                 "abdelkader-omran/AUTO-DZ-ACT-ANALYSIS-3I-ATLAS"]
        registry = {
            "workspace_version": "1.0",
            "repositories": [
                {
                    "repository": name,
                    "expected_local_path": path,
                    "local_path_status": "confirmed",
                    "visibility_required": True,
                }
                for name, path in zip(repos, repo_dirs)
            ],
        }
        return _write_json(registry)

    def test_dual_source_extraction_succeeds(self):
        with tempfile.TemporaryDirectory() as repo_root, \
                tempfile.TemporaryDirectory() as wd1, \
                tempfile.TemporaryDirectory() as wd2, \
                tempfile.TemporaryDirectory() as wd3:

            # Create source files.
            raw_src = os.path.join(repo_root, "raw_data.csv")
            norm_src = os.path.join(repo_root, "norm_data.csv")
            with open(raw_src, "w") as f:
                f.write("raw")
            with open(norm_src, "w") as f:
                f.write("norm")

            registry = {
                "registry_version": "1.1",
                "entries": [
                    {
                        "case_id": "case-test",
                        "raw_source_repository": "org/DAILY",
                        "normalized_source_repository": "org/ANALYSIS",
                        "allowed_raw_source_paths": ["raw_data.csv"],
                        "allowed_normalized_source_paths": ["norm_data.csv"],
                        "target_case_raw_dir": "cases/case-test/raw",
                        "target_case_normalized_dir": "cases/case-test/normalized",
                        "extraction_status": "approved",
                        "governance_reference": "bridge_rules.md",
                    }
                ],
            }
            reg_path = _write_json(registry)
            ws_path = self._setup_workspace(wd1, wd2, wd3)
            try:
                run_extraction(
                    case_id="case-test",
                    registry_path=reg_path,
                    workspace_path=ws_path,
                    repo_root=repo_root,
                    logger=self.logger,
                )
                self.assertTrue(
                    os.path.isfile(
                        os.path.join(repo_root, "cases/case-test/raw/raw_data.csv")
                    )
                )
                self.assertTrue(
                    os.path.isfile(
                        os.path.join(
                            repo_root, "cases/case-test/normalized/norm_data.csv"
                        )
                    )
                )
                # Provenance written.
                prov = os.path.join(repo_root, "cases/case-test/provenance.json")
                self.assertTrue(os.path.isfile(prov))
                with open(prov) as f:
                    data = json.load(f)
                self.assertEqual(data["processing_status"], "extraction_complete")
                self.assertEqual(data["workspace_resolution"], "confirmed")
            finally:
                os.unlink(reg_path)
                os.unlink(ws_path)

    def test_workspace_not_ready_blocks_extraction(self):
        with tempfile.TemporaryDirectory() as repo_root:
            workspace = _make_workspace_registry(placeholder=True)
            ws_path = _write_json(workspace)
            registry = _make_registry(
                case_id="case-test",
                status="approved",
                dual_source=True,
                raw_paths=["r.csv"],
                normalized_paths=["n.csv"],
                raw_dir="raw",
                normalized_dir="normalized",
            )
            reg_path = _write_json(registry)
            try:
                with self.assertRaises(RuntimeError):
                    run_extraction(
                        case_id="case-test",
                        registry_path=reg_path,
                        workspace_path=ws_path,
                        repo_root=repo_root,
                        logger=self.logger,
                    )
            finally:
                os.unlink(ws_path)
                os.unlink(reg_path)

    def test_non_approved_status_blocks_extraction(self):
        with tempfile.TemporaryDirectory() as repo_root, \
                tempfile.TemporaryDirectory() as wd1, \
                tempfile.TemporaryDirectory() as wd2, \
                tempfile.TemporaryDirectory() as wd3:
            registry = _make_registry(
                case_id="case-test",
                status="pending_workspace_resolution",
                dual_source=True,
                raw_paths=[],
                normalized_paths=[],
            )
            reg_path = _write_json(registry)
            ws_path = self._setup_workspace(wd1, wd2, wd3)
            try:
                with self.assertRaises(RuntimeError) as ctx:
                    run_extraction(
                        case_id="case-test",
                        registry_path=reg_path,
                        workspace_path=ws_path,
                        repo_root=repo_root,
                        logger=self.logger,
                    )
                self.assertIn("pending_workspace_resolution", str(ctx.exception))
            finally:
                os.unlink(reg_path)
                os.unlink(ws_path)

    def test_undeclared_case_raises_key_error(self):
        with tempfile.TemporaryDirectory() as repo_root, \
                tempfile.TemporaryDirectory() as wd1, \
                tempfile.TemporaryDirectory() as wd2, \
                tempfile.TemporaryDirectory() as wd3:
            registry = _make_registry(case_id="case-exists")
            reg_path = _write_json(registry)
            ws_path = self._setup_workspace(wd1, wd2, wd3)
            try:
                with self.assertRaises(KeyError):
                    run_extraction(
                        case_id="case-does-not-exist",
                        registry_path=reg_path,
                        workspace_path=ws_path,
                        repo_root=repo_root,
                        logger=self.logger,
                    )
            finally:
                os.unlink(reg_path)
                os.unlink(ws_path)


# ---------------------------------------------------------------------------
# main() CLI
# ---------------------------------------------------------------------------

class TestMain(unittest.TestCase):
    def test_missing_case_arg_returns_error(self):
        with self.assertRaises(SystemExit) as ctx:
            main(["--registry", "/tmp/r.json", "--workspace", "/tmp/w.json"])
        self.assertNotEqual(ctx.exception.code, 0)

    def test_missing_registry_returns_error(self):
        result = main(
            [
                "--case", "case-test",
                "--registry", "/nonexistent/registry.json",
                "--workspace", "/nonexistent/workspace.json",
            ]
        )
        self.assertEqual(result, 1)

    def test_successful_dual_source_extraction_returns_zero(self):
        with tempfile.TemporaryDirectory() as repo_root, \
                tempfile.TemporaryDirectory() as wd1, \
                tempfile.TemporaryDirectory() as wd2, \
                tempfile.TemporaryDirectory() as wd3:

            # Source files
            raw_src = os.path.join(repo_root, "raw_obs.csv")
            norm_src = os.path.join(repo_root, "norm_obs.csv")
            with open(raw_src, "w") as f:
                f.write("raw")
            with open(norm_src, "w") as f:
                f.write("norm")

            registry = {
                "registry_version": "1.1",
                "entries": [
                    {
                        "case_id": "case-cli-test",
                        "raw_source_repository": "org/DAILY",
                        "normalized_source_repository": "org/ANALYSIS",
                        "allowed_raw_source_paths": ["raw_obs.csv"],
                        "allowed_normalized_source_paths": ["norm_obs.csv"],
                        "target_case_raw_dir": "cases/case-cli-test/raw",
                        "target_case_normalized_dir": "cases/case-cli-test/normalized",
                        "extraction_status": "approved",
                        "governance_reference": "bridge_rules.md",
                    }
                ],
            }
            workspace = {
                "workspace_version": "1.0",
                "repositories": [
                    {
                        "repository": name,
                        "expected_local_path": path,
                        "local_path_status": "confirmed",
                        "visibility_required": True,
                    }
                    for name, path in [
                        ("trizel-ai/Auto-dz-act", wd1),
                        ("abdelkader-omran/AUTO-DZ-ACT-3I-ATLAS-DAILY", wd2),
                        ("abdelkader-omran/AUTO-DZ-ACT-ANALYSIS-3I-ATLAS", wd3),
                    ]
                ],
            }
            reg_path = _write_json(registry)
            ws_path = _write_json(workspace)
            try:
                result = main(
                    [
                        "--case", "case-cli-test",
                        "--registry", reg_path,
                        "--workspace", ws_path,
                        "--repo-root", repo_root,
                    ]
                )
                self.assertEqual(result, 0)
            finally:
                os.unlink(reg_path)
                os.unlink(ws_path)

    def test_failed_extraction_returns_one(self):
        with tempfile.TemporaryDirectory() as repo_root:
            workspace = _make_workspace_registry(placeholder=True)
            registry = _make_registry(
                case_id="case-test",
                status="approved",
                dual_source=True,
                raw_paths=[],
                normalized_paths=[],
            )
            reg_path = _write_json(registry)
            ws_path = _write_json(workspace)
            try:
                result = main(
                    [
                        "--case", "case-test",
                        "--registry", reg_path,
                        "--workspace", ws_path,
                        "--repo-root", repo_root,
                    ]
                )
                self.assertEqual(result, 1)
            finally:
                os.unlink(reg_path)
                os.unlink(ws_path)


if __name__ == "__main__":
    unittest.main()
