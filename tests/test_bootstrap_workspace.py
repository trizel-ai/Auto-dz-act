"""Tests for workspace bootstrap and path resolution conventions.

Covers bootstrap_workspace.py behaviour:
- load_workspace_registry / save_workspace_registry round-trip
- _is_placeholder
- validate_repo_path
- probe_sibling_paths (filesystem-level)
- apply_paths
- run_bootstrap (integration: load → apply → save → report)
- CLI main() entry point
"""

import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from validation.bridge.workspace.bootstrap_workspace import (
    _is_placeholder,
    apply_paths,
    load_workspace_registry,
    probe_sibling_paths,
    run_bootstrap,
    save_workspace_registry,
    validate_repo_path,
    main,
    _REPO_AUTO_DZ_ACT,
    _REPO_ATLAS_DAILY,
    _REPO_ATLAS_ANALYSIS,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_registry(placeholder: bool = True) -> dict:
    """Return a minimal workspace registry suitable for testing."""
    path_value = (
        "PLACEHOLDER: test placeholder"
        if placeholder
        else "/confirmed/path"
    )
    return {
        "workspace_version": "1.0",
        "repositories": [
            {
                "repository": _REPO_AUTO_DZ_ACT,
                "role": "validation_repository",
                "expected_local_path": path_value,
                "local_path_status": "pending" if placeholder else "confirmed",
                "visibility_required": True,
            },
            {
                "repository": _REPO_ATLAS_DAILY,
                "role": "raw_source_repository",
                "expected_local_path": path_value,
                "local_path_status": "pending" if placeholder else "confirmed",
                "visibility_required": True,
            },
            {
                "repository": _REPO_ATLAS_ANALYSIS,
                "role": "normalized_source_repository",
                "expected_local_path": path_value,
                "local_path_status": "pending" if placeholder else "confirmed",
                "visibility_required": True,
            },
        ],
    }


def _write_registry(registry: dict) -> str:
    """Write *registry* to a temp file and return its path."""
    fh = tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", delete=False, encoding="utf-8"
    )
    json.dump(registry, fh, indent=2)
    fh.close()
    return fh.name


# ---------------------------------------------------------------------------
# load_workspace_registry
# ---------------------------------------------------------------------------

class TestLoadWorkspaceRegistry(unittest.TestCase):
    def test_loads_valid_registry(self):
        path = _write_registry(_make_registry())
        try:
            data = load_workspace_registry(path)
            self.assertIsInstance(data, dict)
            self.assertIn("repositories", data)
        finally:
            os.unlink(path)

    def test_missing_file_raises_file_not_found(self):
        with self.assertRaises(FileNotFoundError):
            load_workspace_registry("/nonexistent/path/repositories.json")

    def test_non_object_json_raises_value_error(self):
        fh = tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, encoding="utf-8"
        )
        json.dump([1, 2, 3], fh)
        fh.close()
        try:
            with self.assertRaises(ValueError):
                load_workspace_registry(fh.name)
        finally:
            os.unlink(fh.name)


# ---------------------------------------------------------------------------
# save_workspace_registry
# ---------------------------------------------------------------------------

class TestSaveWorkspaceRegistry(unittest.TestCase):
    def test_round_trips_registry(self):
        original = _make_registry()
        path = _write_registry(original)
        try:
            save_workspace_registry(original, path)
            reloaded = load_workspace_registry(path)
            self.assertEqual(reloaded["workspace_version"], "1.0")
            self.assertEqual(len(reloaded["repositories"]), 3)
        finally:
            os.unlink(path)


# ---------------------------------------------------------------------------
# _is_placeholder
# ---------------------------------------------------------------------------

class TestIsPlaceholder(unittest.TestCase):
    def test_placeholder_string_returns_true(self):
        self.assertTrue(_is_placeholder("PLACEHOLDER: some description"))

    def test_placeholder_case_insensitive(self):
        self.assertTrue(_is_placeholder("placeholder: lower case"))

    def test_real_path_returns_false(self):
        self.assertFalse(_is_placeholder("/home/user/repos/Auto-dz-act"))

    def test_leading_whitespace_handled(self):
        self.assertTrue(_is_placeholder("  PLACEHOLDER: with leading space"))


# ---------------------------------------------------------------------------
# validate_repo_path
# ---------------------------------------------------------------------------

class TestValidateRepoPath(unittest.TestCase):
    def test_existing_directory_returns_true(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            ok, result = validate_repo_path(tmpdir)
            self.assertTrue(ok)
            self.assertEqual(result, os.path.abspath(tmpdir))

    def test_nonexistent_path_returns_false(self):
        ok, result = validate_repo_path("/nonexistent/path/to/repo")
        self.assertFalse(ok)
        self.assertIn("does not exist", result)

    def test_result_is_absolute(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            # Use a relative path
            original_cwd = os.getcwd()
            os.chdir(os.path.dirname(tmpdir))
            try:
                relative = os.path.basename(tmpdir)
                ok, result = validate_repo_path(relative)
                self.assertTrue(ok)
                self.assertTrue(os.path.isabs(result))
            finally:
                os.chdir(original_cwd)


# ---------------------------------------------------------------------------
# probe_sibling_paths
# ---------------------------------------------------------------------------

class TestProbeSiblingPaths(unittest.TestCase):
    def test_probe_finds_existing_siblings(self):
        with tempfile.TemporaryDirectory() as parent:
            # Create sibling directories
            auto_dz = os.path.join(parent, "Auto-dz-act")
            daily = os.path.join(parent, "AUTO-DZ-ACT-3I-ATLAS-DAILY")
            analysis = os.path.join(parent, "AUTO-DZ-ACT-ANALYSIS-3I-ATLAS")
            for d in (auto_dz, daily, analysis):
                os.makedirs(d)

            result = probe_sibling_paths(auto_dz)

            self.assertEqual(result[_REPO_AUTO_DZ_ACT], auto_dz)
            self.assertEqual(result[_REPO_ATLAS_DAILY], daily)
            self.assertEqual(result[_REPO_ATLAS_ANALYSIS], analysis)

    def test_probe_returns_none_for_missing_siblings(self):
        with tempfile.TemporaryDirectory() as parent:
            auto_dz = os.path.join(parent, "Auto-dz-act")
            os.makedirs(auto_dz)
            # source repos NOT created

            result = probe_sibling_paths(auto_dz)

            self.assertEqual(result[_REPO_AUTO_DZ_ACT], auto_dz)
            self.assertIsNone(result[_REPO_ATLAS_DAILY])
            self.assertIsNone(result[_REPO_ATLAS_ANALYSIS])

    def test_probe_returns_dict_with_all_three_keys(self):
        with tempfile.TemporaryDirectory() as parent:
            auto_dz = os.path.join(parent, "Auto-dz-act")
            os.makedirs(auto_dz)

            result = probe_sibling_paths(auto_dz)

            self.assertIn(_REPO_AUTO_DZ_ACT, result)
            self.assertIn(_REPO_ATLAS_DAILY, result)
            self.assertIn(_REPO_ATLAS_ANALYSIS, result)


# ---------------------------------------------------------------------------
# apply_paths
# ---------------------------------------------------------------------------

class TestApplyPaths(unittest.TestCase):
    def test_confirmed_paths_are_written(self):
        registry = _make_registry(placeholder=True)
        path_map = {
            _REPO_AUTO_DZ_ACT: "/confirmed/auto-dz-act",
            _REPO_ATLAS_DAILY: "/confirmed/atlas-daily",
            _REPO_ATLAS_ANALYSIS: "/confirmed/atlas-analysis",
        }
        updated, report = apply_paths(registry, path_map)

        repos = {r["repository"]: r for r in updated["repositories"]}
        self.assertEqual(
            repos[_REPO_AUTO_DZ_ACT]["expected_local_path"],
            "/confirmed/auto-dz-act",
        )
        self.assertEqual(
            repos[_REPO_AUTO_DZ_ACT]["local_path_status"], "confirmed"
        )

    def test_unrecognised_repo_is_skipped(self):
        registry = _make_registry(placeholder=True)
        path_map = {"unknown/repo": "/some/path"}
        updated, report = apply_paths(registry, path_map)

        # Original placeholder should be unchanged
        repos = {r["repository"]: r for r in updated["repositories"]}
        self.assertIn(
            "PLACEHOLDER",
            repos[_REPO_AUTO_DZ_ACT]["expected_local_path"].upper(),
        )

    def test_report_contains_all_repositories(self):
        registry = _make_registry(placeholder=True)
        _, report = apply_paths(registry, {})
        reported_repos = {r["repository"] for r in report}
        self.assertIn(_REPO_AUTO_DZ_ACT, reported_repos)
        self.assertIn(_REPO_ATLAS_DAILY, reported_repos)
        self.assertIn(_REPO_ATLAS_ANALYSIS, reported_repos)

    def test_partial_path_map_leaves_others_unchanged(self):
        registry = _make_registry(placeholder=True)
        path_map = {_REPO_AUTO_DZ_ACT: "/confirmed/auto-dz-act"}
        updated, report = apply_paths(registry, path_map)

        repos = {r["repository"]: r for r in updated["repositories"]}
        # atlas-daily should still have placeholder
        self.assertIn(
            "PLACEHOLDER",
            repos[_REPO_ATLAS_DAILY]["expected_local_path"].upper(),
        )


# ---------------------------------------------------------------------------
# run_bootstrap (integration)
# ---------------------------------------------------------------------------

class TestRunBootstrap(unittest.TestCase):
    def test_bootstrap_writes_confirmed_paths(self):
        registry = _make_registry(placeholder=True)
        reg_path = _write_registry(registry)
        try:
            with tempfile.TemporaryDirectory() as d1, \
                    tempfile.TemporaryDirectory() as d2, \
                    tempfile.TemporaryDirectory() as d3:
                path_map = {
                    _REPO_AUTO_DZ_ACT: d1,
                    _REPO_ATLAS_DAILY: d2,
                    _REPO_ATLAS_ANALYSIS: d3,
                }
                result = run_bootstrap(reg_path, path_map)

            # Reload and verify
            saved = load_workspace_registry(reg_path)
            repos = {r["repository"]: r for r in saved["repositories"]}
            self.assertEqual(repos[_REPO_AUTO_DZ_ACT]["local_path_status"], "confirmed")
            self.assertTrue(result)
        finally:
            os.unlink(reg_path)

    def test_bootstrap_returns_false_when_required_repo_unconfirmed(self):
        registry = _make_registry(placeholder=True)
        reg_path = _write_registry(registry)
        try:
            with tempfile.TemporaryDirectory() as d1:
                # Only provide one of the three required repos
                path_map = {_REPO_AUTO_DZ_ACT: d1}
                result = run_bootstrap(reg_path, path_map)
            self.assertFalse(result)
        finally:
            os.unlink(reg_path)

    def test_missing_registry_raises_file_not_found(self):
        with self.assertRaises(FileNotFoundError):
            run_bootstrap("/nonexistent/repositories.json", {})


# ---------------------------------------------------------------------------
# main() CLI
# ---------------------------------------------------------------------------

class TestMain(unittest.TestCase):
    def test_no_args_returns_error_code(self):
        result = main([])
        self.assertEqual(result, 1)

    def test_explicit_paths_succeed_when_dirs_exist(self):
        registry = _make_registry(placeholder=True)
        reg_path = _write_registry(registry)
        try:
            with tempfile.TemporaryDirectory() as d1, \
                    tempfile.TemporaryDirectory() as d2, \
                    tempfile.TemporaryDirectory() as d3:
                result = main(
                    [
                        "--workspace", reg_path,
                        "--auto-dz-act", d1,
                        "--atlas-daily", d2,
                        "--atlas-analysis", d3,
                    ]
                )
            self.assertEqual(result, 0)
        finally:
            os.unlink(reg_path)

    def test_explicit_nonexistent_path_returns_error(self):
        registry = _make_registry(placeholder=True)
        reg_path = _write_registry(registry)
        try:
            result = main(
                [
                    "--workspace", reg_path,
                    "--auto-dz-act", "/nonexistent/path/Auto-dz-act",
                ]
            )
            self.assertEqual(result, 1)
        finally:
            os.unlink(reg_path)

    def test_probe_mode_with_existing_siblings(self):
        registry = _make_registry(placeholder=True)
        reg_path = _write_registry(registry)
        try:
            with tempfile.TemporaryDirectory() as parent:
                auto_dz = os.path.join(parent, "Auto-dz-act")
                daily = os.path.join(parent, "AUTO-DZ-ACT-3I-ATLAS-DAILY")
                analysis = os.path.join(
                    parent, "AUTO-DZ-ACT-ANALYSIS-3I-ATLAS"
                )
                for d in (auto_dz, daily, analysis):
                    os.makedirs(d)

                # Supply explicit auto-dz-act to anchor the probe parent
                result = main(
                    [
                        "--workspace", reg_path,
                        "--probe",
                        "--auto-dz-act", auto_dz,
                        "--atlas-daily", daily,
                        "--atlas-analysis", analysis,
                    ]
                )
            self.assertEqual(result, 0)
        finally:
            os.unlink(reg_path)

    def test_missing_workspace_file_returns_error(self):
        with tempfile.TemporaryDirectory() as d:
            result = main(
                [
                    "--workspace", "/nonexistent/repositories.json",
                    "--auto-dz-act", d,
                ]
            )
            self.assertEqual(result, 1)


if __name__ == "__main__":
    unittest.main()
