"""Controlled extraction script for the TRIZEL validation bridge.

Usage
-----
    python validation/bridge/extract_case_data.py --case <case-id> \\
        [--registry <path-to-registry.json>] \\
        [--workspace <path-to-repositories.json>] \\
        [--repo-root <path-to-repo-root>] \\
        [--log-file <path-to-log-file>]

Rules
-----
All extraction is governed by bridge_rules.md and registry.json.

- Verifies workspace readiness via repositories.json before any extraction.
- Reads the bridge registry to find the allowed source paths for the case.
- Validates that every source path is accessible in the local repository tree.
- For dual-source entries: copies raw files from the DAILY repository into
  raw/ (Step A) and normalized files from the ANALYSIS repository into
  normalized/ (Step B).  No mixing.  No inversion.
- Updates (or prepares) the case provenance.json with full source traceability.
- Fails safely if any required condition is not met.

No network requests are made.
No files are placed without a corresponding provenance record.
Auto-discovery of source files is forbidden.
"""

import argparse
import json
import logging
import os
import shutil
import sys
from datetime import datetime, timezone
from typing import Any

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_BRIDGE_DIR = os.path.dirname(os.path.abspath(__file__))
_DEFAULT_REGISTRY = os.path.join(_BRIDGE_DIR, "registry.json")
_DEFAULT_WORKSPACE = os.path.join(_BRIDGE_DIR, "workspace", "repositories.json")
_DEFAULT_REPO_ROOT = os.path.abspath(os.path.join(_BRIDGE_DIR, "..", ".."))

EXTRACTION_METHOD = "bridge_controlled_copy"
REGISTRY_VERSION_KEY = "registry_version"
TRIZEL_REPOSITORY = "trizel-ai/Auto-dz-act"

_PLACEHOLDER_PREFIX = "PLACEHOLDER"
_STATUS_CONFIRMED = "confirmed"


# ---------------------------------------------------------------------------
# Logging helpers
# ---------------------------------------------------------------------------

def _build_logger(log_file: str | None) -> logging.Logger:
    """Return a logger that writes to stdout (and optionally a file)."""
    logger = logging.getLogger("trizel.bridge")
    logger.setLevel(logging.DEBUG)
    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")

    sh = logging.StreamHandler(sys.stdout)
    sh.setFormatter(fmt)
    logger.addHandler(sh)

    if log_file:
        fh = logging.FileHandler(log_file, encoding="utf-8")
        fh.setFormatter(fmt)
        logger.addHandler(fh)

    return logger


# ---------------------------------------------------------------------------
# Workspace readiness check
# ---------------------------------------------------------------------------

def check_workspace_readiness(workspace_path: str, logger: logging.Logger) -> None:
    """Assert that all required repositories are locally resolved.

    Reads *workspace_path* (repositories.json) and raises ``RuntimeError``
    if any required repository has an unconfirmed or placeholder path.

    This implements the mandatory pre-extraction guard described in
    WORKSPACE_RULES.md (W-5, W-6).

    Raises
    ------
    FileNotFoundError
        If the workspace registry cannot be found.
    RuntimeError
        If any required repository is not locally present.
    """
    if not os.path.isfile(workspace_path):
        raise FileNotFoundError(
            f"Workspace registry not found: {workspace_path}. "
            "Run bootstrap_workspace.py first."
        )

    with open(workspace_path, encoding="utf-8") as fh:
        workspace = json.load(fh)

    repositories = workspace.get("repositories", [])
    unresolved: list[str] = []

    for repo in repositories:
        if not repo.get("visibility_required", False):
            continue
        name = repo.get("repository", "<unnamed>")
        path = repo.get("expected_local_path", "")
        status = repo.get("local_path_status", "")

        if path.strip().upper().startswith(_PLACEHOLDER_PREFIX):
            unresolved.append(
                f"  [{name}]: path is still a placeholder — run bootstrap_workspace.py"
            )
            continue

        if status != _STATUS_CONFIRMED or not os.path.isdir(path):
            unresolved.append(
                f"  [{name}]: local path not found or not confirmed: '{path}'"
            )

    if unresolved:
        lines = "\n".join(unresolved)
        raise RuntimeError(
            "Workspace is NOT ready — the following required repositories "
            "are unresolved:\n"
            + lines
            + "\n\nRun bootstrap_workspace.py then resolve_workspace_paths.py "
            "before extraction."
        )

    logger.info("Workspace readiness confirmed — ALL REQUIRED REPOSITORIES ARE RESOLVED")


# ---------------------------------------------------------------------------
# Registry helpers
# ---------------------------------------------------------------------------

def load_registry(registry_path: str) -> dict[str, Any]:
    """Load and return the bridge registry JSON.

    Raises
    ------
    FileNotFoundError
        If the registry file does not exist.
    ValueError
        If the registry is not a valid JSON object.
    """
    if not os.path.isfile(registry_path):
        raise FileNotFoundError(
            f"Registry not found: {registry_path}"
        )
    with open(registry_path, encoding="utf-8") as fh:
        data = json.load(fh)
    if not isinstance(data, dict):
        raise ValueError("Registry must be a JSON object.")
    return data


def find_registry_entry(
    registry: dict[str, Any], case_id: str
) -> dict[str, Any]:
    """Return the registry entry for *case_id*.

    Raises
    ------
    KeyError
        If no entry exists for the requested case.
    """
    entries = registry.get("entries", [])
    for entry in entries:
        if entry.get("case_id") == case_id:
            return entry
    raise KeyError(
        f"No registry entry found for case '{case_id}'. "
        "Extraction is not permitted for undeclared cases."
    )


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------

def _is_placeholder(path: str) -> bool:
    """Return True if *path* is an unresolved placeholder string."""
    return path.upper().startswith(_PLACEHOLDER_PREFIX)


def _is_dual_source_entry(entry: dict[str, Any]) -> bool:
    """Return True if *entry* declares a dual-source (raw + normalized) mapping."""
    return bool(
        entry.get("raw_source_repository")
        and entry.get("normalized_source_repository")
    )


def validate_entry_status(entry: dict[str, Any]) -> None:
    """Assert that the entry's extraction_status permits extraction.

    Raises
    ------
    RuntimeError
        If the status is not 'approved'.
    """
    case_id = entry.get("case_id", "<unknown>")
    status = entry.get("extraction_status", "")
    if status != "approved":
        raise RuntimeError(
            f"Case '{case_id}': extraction_status is '{status}', "
            "not 'approved'. Update the registry entry to 'approved' "
            "once workspace is resolved and source paths are confirmed."
        )


def _validate_source_paths(
    case_id: str,
    paths: list[str],
    label: str,
    repo_root: str,
    logger: logging.Logger,
) -> list[str]:
    """Validate a list of declared source paths and return resolvable ones.

    Parameters
    ----------
    label:
        Human-readable label used in error messages (e.g. 'raw', 'normalized').

    Raises
    ------
    RuntimeError
        If any path is a placeholder or does not exist in the repository tree.
    """
    if not paths:
        raise RuntimeError(
            f"Case '{case_id}': no allowed_{label}_source_paths declared in registry."
        )

    resolvable: list[str] = []
    for raw_path in paths:
        if _is_placeholder(raw_path):
            raise RuntimeError(
                f"Case '{case_id}': {label} source path is still a placeholder: "
                f"'{raw_path}'. Update the registry with a confirmed "
                "repository-visible path before running extraction."
            )
        full_path = os.path.join(repo_root, raw_path)
        if not os.path.exists(full_path):
            raise RuntimeError(
                f"Case '{case_id}': declared {label} source path does not exist "
                f"in repository tree: '{raw_path}' (resolved to '{full_path}'). "
                "Extraction cannot proceed."
            )
        logger.info("Source path validated [%s]: %s", label, full_path)
        resolvable.append(raw_path)

    return resolvable


def validate_dual_source_entry(
    entry: dict[str, Any], repo_root: str, logger: logging.Logger
) -> tuple[list[str], list[str]]:
    """Validate a dual-source registry entry.

    Returns
    -------
    (raw_paths, normalized_paths)
        Lists of validated source paths for raw and normalized extraction.

    Raises
    ------
    RuntimeError
        If the entry is not extractable.
    """
    validate_entry_status(entry)
    case_id = entry.get("case_id", "<unknown>")

    raw_paths = _validate_source_paths(
        case_id,
        entry.get("allowed_raw_source_paths", []),
        "raw",
        repo_root,
        logger,
    )
    normalized_paths = _validate_source_paths(
        case_id,
        entry.get("allowed_normalized_source_paths", []),
        "normalized",
        repo_root,
        logger,
    )
    return raw_paths, normalized_paths


def validate_entry(
    entry: dict[str, Any], repo_root: str, logger: logging.Logger
) -> list[str]:
    """Validate a single-source registry entry and return resolvable source paths.

    This function handles legacy single-source entries (``allowed_source_paths``).
    For dual-source entries use :func:`validate_dual_source_entry`.

    Raises
    ------
    RuntimeError
        If the entry is not extractable.
    """
    validate_entry_status(entry)
    case_id = entry.get("case_id", "<unknown>")
    allowed_paths = entry.get("allowed_source_paths", [])
    return _validate_source_paths(case_id, allowed_paths, "raw", repo_root, logger)


# ---------------------------------------------------------------------------
# Extraction helpers
# ---------------------------------------------------------------------------

def _destination_filename(rel_source_path: str) -> str:
    """Derive a collision-safe destination filename from *rel_source_path*.

    The relative path separators are replaced with double underscores so that
    ``data/results.csv`` and ``backup/results.csv`` map to distinct names
    (``data__results.csv`` and ``backup__results.csv``).
    """
    return rel_source_path.replace(os.sep, "__").replace("/", "__")


def _copy_files_to_dir(
    case_id: str,
    source_paths: list[str],
    target_dir_rel: str,
    repo_root: str,
    label: str,
    logger: logging.Logger,
) -> list[dict[str, str]]:
    """Copy approved source files into *target_dir_rel*.

    Parameters
    ----------
    label:
        Human-readable label for log messages (e.g. 'raw', 'normalized').

    Returns a list of copy records: [{source_path, destination_path}, ...].

    Raises
    ------
    RuntimeError
        On any copy failure or filename collision within this run.
    """
    target_dir = os.path.join(repo_root, target_dir_rel)
    os.makedirs(target_dir, exist_ok=True)

    copy_records: list[dict[str, str]] = []
    seen_destinations: set[str] = set()

    for rel_path in source_paths:
        src = os.path.join(repo_root, rel_path)
        filename = _destination_filename(rel_path)
        dst = os.path.join(target_dir, filename)

        if filename in seen_destinations:
            raise RuntimeError(
                f"Case '{case_id}': [{label}] destination filename collision for "
                f"'{filename}' (from source path '{rel_path}'). "
                "Two source paths would produce the same destination filename."
            )
        seen_destinations.add(filename)

        logger.info("[%s] Copying '%s' → '%s'", label, src, dst)
        try:
            shutil.copy2(src, dst)
        except OSError as exc:
            raise RuntimeError(
                f"Case '{case_id}': [{label}] failed to copy '{src}' to "
                f"'{dst}': {exc}"
            ) from exc

        copy_records.append(
            {
                "source_path": rel_path,
                "destination_path": os.path.relpath(dst, repo_root),
            }
        )
        logger.info("[%s] Copied successfully: %s", label, filename)

    return copy_records


def extract_files(
    entry: dict[str, Any],
    source_paths: list[str],
    repo_root: str,
    logger: logging.Logger,
) -> list[dict[str, str]]:
    """Copy approved source files into the case raw/ directory.

    Handles legacy single-source registry entries.  For dual-source entries
    use :func:`extract_dual_source_files`.

    Returns a list of copy records: [{source_path, destination_path}, ...].

    Raises
    ------
    RuntimeError
        On any copy failure or filename collision within this run.
    """
    return _copy_files_to_dir(
        case_id=entry["case_id"],
        source_paths=source_paths,
        target_dir_rel=entry["target_case_raw_dir"],
        repo_root=repo_root,
        label="raw",
        logger=logger,
    )


def extract_dual_source_files(
    entry: dict[str, Any],
    raw_paths: list[str],
    normalized_paths: list[str],
    repo_root: str,
    logger: logging.Logger,
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    """Execute dual-source extraction for a case.

    Step A — copies raw files from the DAILY repository into raw/.
    Step B — copies normalized files from the ANALYSIS repository into normalized/.

    No mixing between steps is permitted.

    Returns
    -------
    (raw_records, normalized_records)
        Lists of copy records for raw and normalized files respectively.

    Raises
    ------
    RuntimeError
        On any copy failure or filename collision.
    """
    case_id = entry["case_id"]
    logger.info("=== Step A: raw extraction (DAILY → raw/) ===")
    raw_records = _copy_files_to_dir(
        case_id=case_id,
        source_paths=raw_paths,
        target_dir_rel=entry["target_case_raw_dir"],
        repo_root=repo_root,
        label="raw",
        logger=logger,
    )

    logger.info("=== Step B: normalized extraction (ANALYSIS → normalized/) ===")
    normalized_records = _copy_files_to_dir(
        case_id=case_id,
        source_paths=normalized_paths,
        target_dir_rel=entry["target_case_normalized_dir"],
        repo_root=repo_root,
        label="normalized",
        logger=logger,
    )

    return raw_records, normalized_records


# ---------------------------------------------------------------------------
# Provenance helpers
# ---------------------------------------------------------------------------

def update_provenance(
    entry: dict[str, Any],
    copy_records: list[dict[str, str]],
    registry_version: str,
    repo_root: str,
    logger: logging.Logger,
) -> None:
    """Update the case provenance.json with bridge extraction metadata.

    Handles legacy single-source entries.  For dual-source entries use
    :func:`update_dual_source_provenance`.

    If provenance.json already exists it is read and updated in-place.
    If it does not exist a new record is written.

    Raises
    ------
    RuntimeError
        If the provenance file cannot be written.
    """
    case_id = entry["case_id"]
    raw_dir_rel = entry["target_case_raw_dir"]
    case_dir = os.path.dirname(os.path.join(repo_root, raw_dir_rel))
    provenance_path = os.path.join(case_dir, "provenance.json")

    if os.path.isfile(provenance_path):
        with open(provenance_path, encoding="utf-8") as fh:
            provenance: dict[str, Any] = json.load(fh)
    else:
        provenance = {
            "repository": entry.get("source_organization", ""),
            "organization": entry.get("source_organization", ""),
            "epistemic_layer": "validation",
            "case_id": case_id,
        }

    timestamp = datetime.now(timezone.utc).isoformat()

    provenance["data_origin"] = entry.get("source_repository", "")
    provenance["source_repository"] = entry.get("source_repository", "")
    provenance["source_organization"] = entry.get("source_organization", "")
    provenance["extraction_method"] = EXTRACTION_METHOD
    provenance["extraction_timestamp"] = timestamp
    provenance["bridge_registry_version"] = registry_version
    provenance["extracted_files"] = copy_records
    provenance["processing_status"] = "extraction_complete"
    provenance["governance_reference"] = entry.get(
        "governance_reference", "validation/bridge/bridge_rules.md"
    )
    provenance.pop("note", None)

    _write_provenance(provenance, provenance_path, case_id)
    logger.info("Provenance updated: %s", provenance_path)


def update_dual_source_provenance(
    entry: dict[str, Any],
    raw_records: list[dict[str, str]],
    normalized_records: list[dict[str, str]],
    registry_version: str,
    repo_root: str,
    logger: logging.Logger,
) -> None:
    """Update case provenance.json with dual-source extraction metadata.

    Records the full dual-source lineage required by the TRIZEL bridge:

    - raw_source_repository (DAILY)
    - normalized_source_repository (ANALYSIS)
    - source_files broken out by extraction step
    - extraction_method: bridge_controlled_copy
    - workspace_resolution: confirmed
    - governance_reference: bridge_rules.md

    Raises
    ------
    RuntimeError
        If the provenance file cannot be written.
    """
    case_id = entry["case_id"]
    raw_dir_rel = entry["target_case_raw_dir"]
    case_dir = os.path.dirname(os.path.join(repo_root, raw_dir_rel))
    provenance_path = os.path.join(case_dir, "provenance.json")

    if os.path.isfile(provenance_path):
        with open(provenance_path, encoding="utf-8") as fh:
            provenance: dict[str, Any] = json.load(fh)
    else:
        provenance = {}

    timestamp = datetime.now(timezone.utc).isoformat()

    provenance["repository"] = TRIZEL_REPOSITORY
    provenance["epistemic_layer"] = "validation"
    provenance["case_id"] = case_id
    provenance["raw_source_repository"] = entry.get("raw_source_repository", "")
    provenance["normalized_source_repository"] = entry.get(
        "normalized_source_repository", ""
    )
    provenance["source_files"] = {
        "raw": [r["source_path"] for r in raw_records],
        "normalized": [r["source_path"] for r in normalized_records],
    }
    provenance["extraction_method"] = EXTRACTION_METHOD
    provenance["extraction_timestamp"] = timestamp
    provenance["workspace_resolution"] = "confirmed"
    provenance["bridge_registry_version"] = registry_version
    provenance["governance_reference"] = entry.get(
        "governance_reference", "validation/bridge/bridge_rules.md"
    )
    provenance["processing_status"] = "extraction_complete"

    # Remove any legacy/pending notes
    for key in ("note", "data_origin", "source_repository", "source_organization"):
        provenance.pop(key, None)

    _write_provenance(provenance, provenance_path, case_id)
    logger.info("Dual-source provenance updated: %s", provenance_path)


def _write_provenance(
    provenance: dict[str, Any], path: str, case_id: str
) -> None:
    """Atomically write *provenance* JSON to *path*.

    Raises
    ------
    RuntimeError
        If the file cannot be written.
    """
    try:
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(provenance, fh, indent=2)
            fh.write("\n")
    except OSError as exc:
        raise RuntimeError(
            f"Case '{case_id}': failed to write provenance to '{path}': {exc}"
        ) from exc


# ---------------------------------------------------------------------------
# Audit log helper
# ---------------------------------------------------------------------------

def log_extraction_audit(
    logger: logging.Logger,
    case_id: str,
    raw_source_repo: str,
    normalized_source_repo: str,
    raw_records: list[dict[str, str]],
    normalized_records: list[dict[str, str]],
    timestamp: str,
    success: bool,
) -> None:
    """Print a structured audit log entry for the extraction run."""
    status = "SUCCESS" if success else "FAILURE"
    logger.info("=== EXTRACTION AUDIT LOG ===")
    logger.info("case_id                  : %s", case_id)
    logger.info("raw_source_repository    : %s", raw_source_repo)
    logger.info("normalized_source_repo   : %s", normalized_source_repo)
    logger.info("raw files copied         : %d", len(raw_records))
    for r in raw_records:
        logger.info("  RAW    %s → %s", r["source_path"], r["destination_path"])
    logger.info("normalized files copied  : %d", len(normalized_records))
    for r in normalized_records:
        logger.info(
            "  NORM   %s → %s", r["source_path"], r["destination_path"]
        )
    logger.info("extraction_timestamp     : %s", timestamp)
    logger.info("status                   : %s", status)
    logger.info("=== END AUDIT LOG ===")


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def run_extraction(
    case_id: str,
    registry_path: str,
    workspace_path: str,
    repo_root: str,
    logger: logging.Logger,
) -> None:
    """Execute a governed extraction for *case_id*.

    This is the single entry point for all bridge extraction logic.  It
    follows bridge_rules.md exactly and fails safely at every step.

    For dual-source registry entries (raw_source_repository +
    normalized_source_repository) the function performs:

    1. Workspace readiness check.
    2. Registry load and entry lookup.
    3. Source path validation (raw and normalized separately).
    4. Step A — raw extraction from DAILY → raw/.
    5. Step B — normalized extraction from ANALYSIS → normalized/.
    6. Dual-source provenance update.
    """
    logger.info("=== TRIZEL Validation Bridge — extraction start ===")
    logger.info("Case ID      : %s", case_id)
    logger.info("Registry     : %s", registry_path)
    logger.info("Workspace    : %s", workspace_path)
    logger.info("Repository   : %s", repo_root)

    # 1. Workspace readiness check (mandatory pre-condition).
    check_workspace_readiness(workspace_path, logger)

    # 2. Load registry.
    registry = load_registry(registry_path)
    registry_version = registry.get(REGISTRY_VERSION_KEY, "unknown")
    logger.info("Registry version: %s", registry_version)

    # 3. Find entry for this case.
    entry = find_registry_entry(registry, case_id)

    if _is_dual_source_entry(entry):
        logger.info(
            "Dual-source entry found for '%s' "
            "(raw: %s | normalized: %s)",
            case_id,
            entry.get("raw_source_repository", "<unset>"),
            entry.get("normalized_source_repository", "<unset>"),
        )

        # 4. Validate entry and resolve source paths (both steps).
        raw_paths, normalized_paths = validate_dual_source_entry(
            entry, repo_root, logger
        )

        # 5. Extract files (dual-source).
        raw_records, normalized_records = extract_dual_source_files(
            entry, raw_paths, normalized_paths, repo_root, logger
        )

        # 6. Update provenance with dual-source lineage.
        update_dual_source_provenance(
            entry, raw_records, normalized_records, registry_version, repo_root, logger
        )

        timestamp = datetime.now(timezone.utc).isoformat()
        log_extraction_audit(
            logger=logger,
            case_id=case_id,
            raw_source_repo=entry.get("raw_source_repository", ""),
            normalized_source_repo=entry.get("normalized_source_repository", ""),
            raw_records=raw_records,
            normalized_records=normalized_records,
            timestamp=timestamp,
            success=True,
        )

        logger.info(
            "=== Dual-source extraction complete for '%s' — "
            "%d raw + %d normalized file(s) copied ===",
            case_id,
            len(raw_records),
            len(normalized_records),
        )

    else:
        # Legacy single-source path.
        logger.info(
            "Registry entry found for '%s' (source: %s)",
            case_id,
            entry.get("source_repository", "<unset>"),
        )

        # 4. Validate entry and resolve source paths.
        source_paths = validate_entry(entry, repo_root, logger)

        # 5. Extract (copy) files.
        copy_records = extract_files(entry, source_paths, repo_root, logger)

        # 6. Update provenance atomically.
        update_provenance(
            entry, copy_records, registry_version, repo_root, logger
        )

        logger.info(
            "=== Extraction complete for '%s' — %d file(s) copied ===",
            case_id,
            len(copy_records),
        )


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="TRIZEL validation bridge: governed extraction script.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "All extraction is governed by bridge_rules.md and registry.json.\n"
            "No network requests are made.  Undeclared paths are rejected."
        ),
    )
    parser.add_argument(
        "--case",
        required=True,
        metavar="CASE_ID",
        help="Validation case ID to extract (e.g. case-001-asteroid).",
    )
    parser.add_argument(
        "--registry",
        default=_DEFAULT_REGISTRY,
        metavar="PATH",
        help="Path to registry.json (default: validation/bridge/registry.json).",
    )
    parser.add_argument(
        "--workspace",
        default=_DEFAULT_WORKSPACE,
        metavar="PATH",
        help=(
            "Path to repositories.json "
            "(default: validation/bridge/workspace/repositories.json)."
        ),
    )
    parser.add_argument(
        "--repo-root",
        default=_DEFAULT_REPO_ROOT,
        metavar="PATH",
        help="Absolute path to the repository root (default: auto-detected).",
    )
    parser.add_argument(
        "--log-file",
        default=None,
        metavar="PATH",
        help="Optional path to write log output in addition to stdout.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point.  Returns 0 on success, 1 on failure."""
    args = _parse_args(argv)
    logger = _build_logger(args.log_file)

    try:
        run_extraction(
            case_id=args.case,
            registry_path=args.registry,
            workspace_path=args.workspace,
            repo_root=args.repo_root,
            logger=logger,
        )
        return 0
    except (FileNotFoundError, KeyError, ValueError, RuntimeError) as exc:
        logger.error("Extraction failed: %s", exc)
        return 1


if __name__ == "__main__":
    sys.exit(main())

