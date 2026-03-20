"""Workspace readiness checker for the TRIZEL validation bridge.

Usage
-----
    python validation/bridge/workspace/resolve_workspace_paths.py \\
        [--workspace <path-to-repositories.json>]

Purpose
-------
Reads the workspace registry (repositories.json) and validates that every
required repository is locally present at its declared path.

This script is a read-only readiness checker.  It does NOT:

- make any network request
- clone or fetch any repository
- copy, move, or modify any file
- perform any extraction

Extraction must not begin until this script exits with status 0.

Rules enforced
--------------
See WORKSPACE_RULES.md for the full rule set.  Key rules applied here:

- W-1  : required repositories must be locally present
- W-3  : undeclared repositories are not consulted
- W-4  : no hidden path assumptions (all paths read from repositories.json)
- W-5  : workspace must resolve before extraction starts
- W-6  : any missing required repository blocks extraction (exit non-zero)
- W-8  : no network access
- W-9  : no data modification
- W-10 : workspace registry version is recorded in every report
"""

import argparse
import json
import os
import sys
from typing import Any

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_WORKSPACE_DIR = os.path.dirname(os.path.abspath(__file__))
_DEFAULT_WORKSPACE_FILE = os.path.join(_WORKSPACE_DIR, "repositories.json")

_PLACEHOLDER_PREFIX = "PLACEHOLDER"
_STATUS_FOUND = "found"
_STATUS_MISSING = "missing"
_STATUS_PLACEHOLDER = "placeholder"


# ---------------------------------------------------------------------------
# Registry loading
# ---------------------------------------------------------------------------

def load_workspace_registry(workspace_path: str) -> dict[str, Any]:
    """Load and return the workspace registry JSON.

    Raises
    ------
    FileNotFoundError
        If the workspace file does not exist.
    ValueError
        If the workspace file is not a valid JSON object.
    """
    if not os.path.isfile(workspace_path):
        raise FileNotFoundError(
            f"Workspace registry not found: {workspace_path}"
        )
    with open(workspace_path, encoding="utf-8") as fh:
        data = json.load(fh)
    if not isinstance(data, dict):
        raise ValueError("Workspace registry must be a JSON object.")
    return data


# ---------------------------------------------------------------------------
# Path resolution
# ---------------------------------------------------------------------------

def _is_placeholder(path: str) -> bool:
    """Return True if *path* is an unresolved placeholder string."""
    return path.strip().upper().startswith(_PLACEHOLDER_PREFIX)


def resolve_repository(repo: dict[str, Any]) -> dict[str, Any]:
    """Resolve a single repository entry and return a status record.

    No network access is performed.  Only the local filesystem is consulted.

    Parameters
    ----------
    repo:
        A single repository object from the workspace registry.

    Returns
    -------
    dict with keys:
        repository, role, expected_local_path, visibility_required,
        local_path_confirmed, status, message
    """
    name = repo.get("repository", "<unnamed>")
    role = repo.get("role", "<unknown>")
    raw_path = repo.get("expected_local_path", "")
    required = bool(repo.get("visibility_required", False))

    if _is_placeholder(raw_path):
        return {
            "repository": name,
            "role": role,
            "expected_local_path": raw_path,
            "visibility_required": required,
            "local_path_confirmed": False,
            "status": _STATUS_PLACEHOLDER,
            "message": (
                f"Local path is still a placeholder. "
                f"Update repositories.json with the confirmed absolute path "
                f"for '{name}' before running extraction."
            ),
        }

    if os.path.isdir(raw_path):
        return {
            "repository": name,
            "role": role,
            "expected_local_path": raw_path,
            "visibility_required": required,
            "local_path_confirmed": True,
            "status": _STATUS_FOUND,
            "message": f"Local path confirmed: {raw_path}",
        }

    return {
        "repository": name,
        "role": role,
        "expected_local_path": raw_path,
        "visibility_required": required,
        "local_path_confirmed": False,
        "status": _STATUS_MISSING,
        "message": (
            f"Local path not found: '{raw_path}'. "
            f"Ensure '{name}' is checked out at this path before extraction."
        ),
    }


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------

def print_report(
    workspace_version: str,
    results: list[dict[str, Any]],
    all_resolved: bool,
) -> None:
    """Print a human-readable workspace readiness report to stdout."""
    width = 72
    print("=" * width)
    print("TRIZEL Validation Bridge — Workspace Readiness Report")
    print(f"Workspace registry version: {workspace_version}")
    print("=" * width)

    for r in results:
        status_label = r["status"].upper()
        required_label = "REQUIRED" if r["visibility_required"] else "optional"
        print(
            f"\n  [{status_label}] {r['repository']}"
            f"  ({required_label})"
        )
        print(f"  Role               : {r['role']}")
        print(f"  Expected path      : {r['expected_local_path']}")
        print(f"  Path confirmed     : {r['local_path_confirmed']}")
        print(f"  Message            : {r['message']}")

    print("\n" + "-" * width)
    if all_resolved:
        print("WORKSPACE READY — all required repositories are locally visible.")
        print("Extraction may proceed.")
    else:
        print("WORKSPACE NOT READY — one or more required repositories are")
        print("unresolved.  Extraction is BLOCKED until all required")
        print("repositories are locally visible.")
    print("=" * width)


# ---------------------------------------------------------------------------
# Main resolution logic
# ---------------------------------------------------------------------------

def check_workspace(workspace_path: str) -> bool:
    """Run the full workspace readiness check.

    Returns True if all required repositories are resolved, False otherwise.

    Raises
    ------
    FileNotFoundError, ValueError
        If the workspace registry cannot be loaded.
    """
    registry = load_workspace_registry(workspace_path)
    workspace_version = registry.get("workspace_version", "unknown")
    repositories = registry.get("repositories", [])

    results: list[dict[str, Any]] = []
    all_resolved = True

    for repo in repositories:
        record = resolve_repository(repo)
        results.append(record)
        if repo.get("visibility_required", False) and not record["local_path_confirmed"]:
            all_resolved = False

    print_report(workspace_version, results, all_resolved)
    return all_resolved


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "TRIZEL validation bridge: workspace readiness checker.\n\n"
            "Reads repositories.json and validates that all required source\n"
            "repositories are locally present.  Makes no network requests\n"
            "and modifies no data.  Exits 0 if workspace is ready, 1 otherwise."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--workspace",
        default=_DEFAULT_WORKSPACE_FILE,
        metavar="PATH",
        help=(
            "Path to repositories.json "
            "(default: validation/bridge/workspace/repositories.json)."
        ),
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point.  Returns 0 if workspace is ready, 1 otherwise."""
    args = _parse_args(argv)
    try:
        ready = check_workspace(args.workspace)
    except (FileNotFoundError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    return 0 if ready else 1


if __name__ == "__main__":
    sys.exit(main())
