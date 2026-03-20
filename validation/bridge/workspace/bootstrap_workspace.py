"""Workspace bootstrap script for the TRIZEL validation bridge.

Usage — explicit paths
----------------------
    python validation/bridge/workspace/bootstrap_workspace.py \\
        --auto-dz-act     /absolute/path/to/Auto-dz-act \\
        --atlas-daily     /absolute/path/to/AUTO-DZ-ACT-3I-ATLAS-DAILY \\
        --atlas-analysis  /absolute/path/to/AUTO-DZ-ACT-ANALYSIS-3I-ATLAS \\
        [--workspace      /path/to/repositories.json]

Usage — sibling-directory probe
--------------------------------
    python validation/bridge/workspace/bootstrap_workspace.py --probe \\
        [--workspace /path/to/repositories.json]

    In probe mode the script looks for the source repositories as siblings of
    the Auto-dz-act checkout (see PATH_RESOLUTION_CONVENTIONS.md, Rule PC-3).

What this script does
---------------------
1. Reads the current workspace registry (repositories.json).
2. Validates that every provided path exists as a local directory.
3. Writes confirmed absolute paths back into repositories.json, replacing any
   existing PLACEHOLDER values.
4. Prints a per-repository confirmation report.
5. Exits 0 if every required repository is confirmed, 1 otherwise.

What this script does NOT do
-----------------------------
- Make any network request
- Clone, fetch, or download any repository
- Copy, move, or modify any file outside repositories.json
- Invent or guess paths that were not provided or successfully probed

Rules enforced
--------------
See PATH_RESOLUTION_CONVENTIONS.md.  Key conventions applied here:

- PC-1 : absolute paths only — all written paths are normalised to absolute
- PC-2 : no invented paths — only paths that exist on the local filesystem
         are written; placeholder strings are never preserved as live paths
- PC-3 : sibling-directory probe convention for --probe mode
- PC-4 : this script is the only authorised mechanism for writing paths into
         repositories.json; manual edits are permitted but must follow PC-1
- PC-5 : bootstrap is idempotent; re-running with correct paths is safe
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

# The Auto-dz-act repo is three directories above this file:
#   bootstrap_workspace.py → workspace/ → bridge/ → validation/ → repo root
_AUTO_DZ_ACT_ROOT = os.path.abspath(
    os.path.join(_WORKSPACE_DIR, "..", "..", "..")
)

_PLACEHOLDER_PREFIX = "PLACEHOLDER"

# Canonical repository identifiers (as declared in repositories.json)
_REPO_AUTO_DZ_ACT = "trizel-ai/Auto-dz-act"
_REPO_ATLAS_DAILY = "abdelkader-omran/AUTO-DZ-ACT-3I-ATLAS-DAILY"
_REPO_ATLAS_ANALYSIS = "abdelkader-omran/AUTO-DZ-ACT-ANALYSIS-3I-ATLAS"

# Short directory names used by the sibling-directory probe (PC-3)
_SIBLING_NAME_AUTO_DZ_ACT = "Auto-dz-act"
_SIBLING_NAME_ATLAS_DAILY = "AUTO-DZ-ACT-3I-ATLAS-DAILY"
_SIBLING_NAME_ATLAS_ANALYSIS = "AUTO-DZ-ACT-ANALYSIS-3I-ATLAS"


# ---------------------------------------------------------------------------
# Registry I/O
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


def save_workspace_registry(data: dict[str, Any], workspace_path: str) -> None:
    """Write the registry back to *workspace_path* with standard formatting."""
    with open(workspace_path, mode="w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, ensure_ascii=False)
        fh.write("\n")


# ---------------------------------------------------------------------------
# Path validation
# ---------------------------------------------------------------------------

def _is_placeholder(path: str) -> bool:
    """Return True if *path* is an unresolved placeholder string."""
    return path.strip().upper().startswith(_PLACEHOLDER_PREFIX)


def validate_repo_path(path: str) -> tuple[bool, str]:
    """Validate that *path* is an existing local directory.

    Returns
    -------
    (True, normalised_absolute_path)   if the directory exists.
    (False, error_message)             otherwise.
    """
    abs_path = os.path.abspath(path)
    if os.path.isdir(abs_path):
        return True, abs_path
    return False, f"Path does not exist or is not a directory: '{abs_path}'"


# ---------------------------------------------------------------------------
# Sibling-directory probe (PC-3)
# ---------------------------------------------------------------------------

def probe_sibling_paths(auto_dz_act_root: str) -> dict[str, str | None]:
    """Probe for source repositories as siblings of the Auto-dz-act checkout.

    The sibling-directory convention (PC-3) expects all TRIZEL repositories to
    be checked out under the same parent directory.  For example:

        ~/workspace/trizel-ai/Auto-dz-act           ← this repository
        ~/workspace/abdelkader-omran/AUTO-DZ-ACT-3I-ATLAS-DAILY
        ~/workspace/abdelkader-omran/AUTO-DZ-ACT-ANALYSIS-3I-ATLAS

    Parameters
    ----------
    auto_dz_act_root:
        Absolute path to the Auto-dz-act checkout (parent of ``validation/``).

    Returns
    -------
    dict mapping repository identifier → absolute path (or None if not found).
    """
    parent = os.path.dirname(auto_dz_act_root)
    candidates = {
        _REPO_AUTO_DZ_ACT: auto_dz_act_root,
        _REPO_ATLAS_DAILY: os.path.join(parent, _SIBLING_NAME_ATLAS_DAILY),
        _REPO_ATLAS_ANALYSIS: os.path.join(
            parent, _SIBLING_NAME_ATLAS_ANALYSIS
        ),
    }
    return {
        repo: path if os.path.isdir(path) else None
        for repo, path in candidates.items()
    }


# ---------------------------------------------------------------------------
# Core bootstrap logic
# ---------------------------------------------------------------------------

def apply_paths(
    registry: dict[str, Any],
    path_map: dict[str, str],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Apply confirmed paths from *path_map* into the registry.

    Only entries whose ``repository`` key appears in *path_map* are modified.
    Entries not present in *path_map* are left unchanged.

    Parameters
    ----------
    registry:
        Full workspace registry dict (mutated in place and returned).
    path_map:
        Mapping of repository identifier → confirmed absolute local path.

    Returns
    -------
    (updated_registry, report)
        ``report`` is a list of per-repository result dicts with keys:
        ``repository``, ``status``, ``path``, ``message``.
    """
    report: list[dict[str, Any]] = []

    for repo in registry.get("repositories", []):
        name = repo.get("repository", "")
        if name not in path_map:
            report.append(
                {
                    "repository": name,
                    "status": "skipped",
                    "path": repo.get("expected_local_path", ""),
                    "message": "No path provided for this repository; left unchanged.",
                }
            )
            continue

        confirmed_path = path_map[name]
        repo["expected_local_path"] = confirmed_path
        repo["local_path_status"] = "confirmed"
        report.append(
            {
                "repository": name,
                "status": "confirmed",
                "path": confirmed_path,
                "message": f"Path confirmed and written: {confirmed_path}",
            }
        )

    return registry, report


def run_bootstrap(
    workspace_path: str,
    path_map: dict[str, str],
) -> bool:
    """Load the registry, apply *path_map*, save, and print a report.

    Returns True if every required repository has a confirmed path after the
    update, False otherwise.
    """
    registry = load_workspace_registry(workspace_path)
    registry, report = apply_paths(registry, path_map)

    # Determine overall success: all required repos must be confirmed
    all_confirmed = True
    for entry in registry.get("repositories", []):
        if entry.get("visibility_required", False):
            status = entry.get("local_path_status", "")
            if status != "confirmed":
                all_confirmed = False

    save_workspace_registry(registry, workspace_path)
    _print_bootstrap_report(report, all_confirmed)
    return all_confirmed


def _print_bootstrap_report(
    report: list[dict[str, Any]],
    all_confirmed: bool,
) -> None:
    """Print a human-readable bootstrap report to stdout."""
    width = 72
    print("=" * width)
    print("TRIZEL Validation Bridge — Workspace Bootstrap Report")
    print("=" * width)

    for r in report:
        status_label = r["status"].upper()
        print(f"\n  [{status_label}] {r['repository']}")
        print(f"  Path    : {r['path']}")
        print(f"  Message : {r['message']}")

    print("\n" + "-" * width)
    if all_confirmed:
        print(
            "BOOTSTRAP COMPLETE — all required repositories have confirmed paths."
        )
        print("Run resolve_workspace_paths.py to verify before extraction.")
    else:
        print(
            "BOOTSTRAP INCOMPLETE — one or more required repositories still"
        )
        print(
            "have unconfirmed paths.  Re-run with correct paths or update"
        )
        print("repositories.json manually before running extraction.")
    print("=" * width)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "TRIZEL validation bridge: workspace bootstrap.\n\n"
            "Writes confirmed local repository paths into repositories.json.\n"
            "Use --probe to attempt automatic sibling-directory detection,\n"
            "or supply explicit paths with the individual flags.\n\n"
            "Makes no network requests.  Only modifies repositories.json."
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
    parser.add_argument(
        "--probe",
        action="store_true",
        help=(
            "Probe for source repositories as siblings of the Auto-dz-act "
            "checkout (see PATH_RESOLUTION_CONVENTIONS.md, Rule PC-3).  "
            "Explicit path flags override probe results."
        ),
    )
    parser.add_argument(
        "--auto-dz-act",
        metavar="PATH",
        help=(
            "Absolute local path to the trizel-ai/Auto-dz-act checkout.  "
            "Defaults to the repository containing this script when --probe "
            "is used."
        ),
    )
    parser.add_argument(
        "--atlas-daily",
        metavar="PATH",
        help=(
            "Absolute local path to the "
            "abdelkader-omran/AUTO-DZ-ACT-3I-ATLAS-DAILY checkout."
        ),
    )
    parser.add_argument(
        "--atlas-analysis",
        metavar="PATH",
        help=(
            "Absolute local path to the "
            "abdelkader-omran/AUTO-DZ-ACT-ANALYSIS-3I-ATLAS checkout."
        ),
    )
    return parser.parse_args(argv)


def _build_path_map(
    args: argparse.Namespace,
) -> tuple[dict[str, str], list[str]]:
    """Resolve CLI arguments into a validated path map.

    Returns
    -------
    (path_map, errors)
        ``path_map`` maps repository identifier → confirmed absolute path.
        ``errors`` is a list of human-readable error strings; empty on success.
    """
    path_map: dict[str, str] = {}
    errors: list[str] = []

    # Start with probe results if requested
    if args.probe:
        probed = probe_sibling_paths(_AUTO_DZ_ACT_ROOT)
        for repo, path in probed.items():
            if path is not None:
                path_map[repo] = path

    # Explicit flags override probe results
    explicit: dict[str, str | None] = {
        _REPO_AUTO_DZ_ACT: args.auto_dz_act,
        _REPO_ATLAS_DAILY: args.atlas_daily,
        _REPO_ATLAS_ANALYSIS: args.atlas_analysis,
    }
    for repo, raw_path in explicit.items():
        if raw_path is None:
            continue
        ok, result = validate_repo_path(raw_path)
        if ok:
            path_map[repo] = result
        else:
            errors.append(f"{repo}: {result}")

    return path_map, errors


def main(argv: list[str] | None = None) -> int:
    """CLI entry point.  Returns 0 if bootstrap succeeds, 1 otherwise."""
    args = _parse_args(argv)

    if not args.probe and not any(
        (args.auto_dz_act, args.atlas_daily, args.atlas_analysis)
    ):
        print(
            "ERROR: No paths provided.  Use --probe or supply explicit path "
            "flags.  Run with --help for usage.",
            file=sys.stderr,
        )
        return 1

    path_map, errors = _build_path_map(args)

    if errors:
        for err in errors:
            print(f"ERROR: {err}", file=sys.stderr)
        return 1

    if not path_map:
        print(
            "ERROR: No valid paths could be resolved (probe found nothing and "
            "no explicit paths were provided).",
            file=sys.stderr,
        )
        return 1

    try:
        ready = run_bootstrap(args.workspace, path_map)
    except (FileNotFoundError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    return 0 if ready else 1


if __name__ == "__main__":
    sys.exit(main())
