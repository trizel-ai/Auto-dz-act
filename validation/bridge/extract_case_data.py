"""Controlled extraction script for the TRIZEL validation bridge.

Usage
-----
    python validation/bridge/extract_case_data.py --case <case-id> \\
        [--registry <path-to-registry.json>] \\
        [--repo-root <path-to-repo-root>] \\
        [--log-file <path-to-log-file>]

Rules
-----
All extraction is governed by bridge_rules.md and registry.json.

- Reads the bridge registry to find the allowed source paths for the case.
- Validates that every source path is accessible in the local repository tree.
- Copies approved source files into the case's raw/ directory.
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
_DEFAULT_REPO_ROOT = os.path.abspath(os.path.join(_BRIDGE_DIR, "..", ".."))

EXTRACTION_METHOD = "bridge_controlled_extraction"
REGISTRY_VERSION_KEY = "registry_version"


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
    return path.upper().startswith("PLACEHOLDER")


def validate_entry(
    entry: dict[str, Any], repo_root: str, logger: logging.Logger
) -> list[str]:
    """Validate the registry entry and return the list of resolvable source paths.

    Raises
    ------
    RuntimeError
        If the entry is not extractable (status check, placeholder paths, or
        missing source files).
    """
    case_id = entry.get("case_id", "<unknown>")

    # --- extraction status check --------------------------------------------
    status = entry.get("extraction_status", "")
    if status != "approved":
        raise RuntimeError(
            f"Case '{case_id}': extraction_status is '{status}', "
            "not 'approved'. Update the registry entry to 'approved' "
            "once source paths are confirmed."
        )

    # --- source paths check -------------------------------------------------
    allowed_paths = entry.get("allowed_source_paths", [])
    if not allowed_paths:
        raise RuntimeError(
            f"Case '{case_id}': no allowed_source_paths declared in registry."
        )

    resolvable: list[str] = []
    for raw_path in allowed_paths:
        if _is_placeholder(raw_path):
            raise RuntimeError(
                f"Case '{case_id}': source path is still a placeholder: "
                f"'{raw_path}'. Update the registry with a confirmed "
                "repository-visible path before running extraction."
            )
        full_path = os.path.join(repo_root, raw_path)
        if not os.path.exists(full_path):
            raise RuntimeError(
                f"Case '{case_id}': declared source path does not exist in "
                f"repository tree: '{raw_path}' (resolved to '{full_path}'). "
                "Extraction cannot proceed."
            )
        logger.info("Source path validated: %s", full_path)
        resolvable.append(raw_path)

    return resolvable


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


def extract_files(
    entry: dict[str, Any],
    source_paths: list[str],
    repo_root: str,
    logger: logging.Logger,
) -> list[dict[str, str]]:
    """Copy approved source files into the case raw/ directory.

    Returns a list of copy records: [{source_path, destination_path}, ...].

    Raises
    ------
    RuntimeError
        On any copy failure or filename collision within this run.
    """
    case_id = entry["case_id"]
    raw_dir = os.path.join(repo_root, entry["target_case_raw_dir"])

    os.makedirs(raw_dir, exist_ok=True)

    copy_records: list[dict[str, str]] = []
    seen_destinations: set[str] = set()

    for rel_path in source_paths:
        src = os.path.join(repo_root, rel_path)
        filename = _destination_filename(rel_path)
        dst = os.path.join(raw_dir, filename)

        if filename in seen_destinations:
            raise RuntimeError(
                f"Case '{case_id}': destination filename collision for "
                f"'{filename}' (from source path '{rel_path}'). "
                "Two source paths would produce the same destination filename."
            )
        seen_destinations.add(filename)

        logger.info("Copying '%s' → '%s'", src, dst)
        try:
            shutil.copy2(src, dst)
        except OSError as exc:
            raise RuntimeError(
                f"Case '{case_id}': failed to copy '{src}' to '{dst}': {exc}"
            ) from exc

        copy_records.append(
            {"source_path": rel_path, "destination_path": os.path.relpath(dst, repo_root)}
        )
        logger.info("Copied successfully: %s", filename)

    return copy_records


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

    If provenance.json already exists it is read and updated in-place.
    If it does not exist a new record is written.

    Raises
    ------
    RuntimeError
        If the provenance file cannot be written.
    """
    case_id = entry["case_id"]
    # Derive the case directory from target_case_raw_dir (one level up from raw/).
    raw_dir_rel = entry["target_case_raw_dir"]
    case_dir = os.path.dirname(os.path.join(repo_root, raw_dir_rel))
    provenance_path = os.path.join(case_dir, "provenance.json")

    # Load existing provenance if present.
    if os.path.isfile(provenance_path):
        with open(provenance_path, encoding="utf-8") as fh:
            provenance: dict[str, Any] = json.load(fh)
    else:
        provenance = {
            "repository": entry.get("source_organization", ""),
            "organization": entry.get("source_organization", ""),
            "epistemic_layer": "Layer-1",
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

    # Remove the pending note if it exists.
    provenance.pop("note", None)

    try:
        with open(provenance_path, "w", encoding="utf-8") as fh:
            json.dump(provenance, fh, indent=2)
            fh.write("\n")
    except OSError as exc:
        raise RuntimeError(
            f"Case '{case_id}': failed to write provenance to "
            f"'{provenance_path}': {exc}"
        ) from exc

    logger.info("Provenance updated: %s", provenance_path)


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def run_extraction(
    case_id: str,
    registry_path: str,
    repo_root: str,
    logger: logging.Logger,
) -> None:
    """Execute a governed extraction for *case_id*.

    This is the single entry point for all bridge extraction logic.  It
    follows bridge_rules.md exactly and fails safely at every step.
    """
    logger.info("=== TRIZEL Validation Bridge — extraction start ===")
    logger.info("Case ID      : %s", case_id)
    logger.info("Registry     : %s", registry_path)
    logger.info("Repository   : %s", repo_root)

    # 1. Load registry.
    registry = load_registry(registry_path)
    registry_version = registry.get(REGISTRY_VERSION_KEY, "unknown")
    logger.info("Registry version: %s", registry_version)

    # 2. Find entry for this case.
    entry = find_registry_entry(registry, case_id)
    logger.info(
        "Registry entry found for '%s' (source: %s)",
        case_id,
        entry.get("source_repository", "<unset>"),
    )

    # 3. Validate entry and resolve source paths.
    source_paths = validate_entry(entry, repo_root, logger)

    # 4. Extract (copy) files.
    copy_records = extract_files(entry, source_paths, repo_root, logger)

    # 5. Update provenance atomically.
    update_provenance(entry, copy_records, registry_version, repo_root, logger)

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
            repo_root=args.repo_root,
            logger=logger,
        )
        return 0
    except (FileNotFoundError, KeyError, ValueError, RuntimeError) as exc:
        logger.error("Extraction failed: %s", exc)
        return 1


if __name__ == "__main__":
    sys.exit(main())
