# TRIZEL Validation Bridge

**Layer**: Layer-1 (Execution)  
**Status**: Active  
**Version**: 1.0  
**Repository**: https://github.com/trizel-ai/Auto-dz-act

---

## Why the Bridge Exists

The TRIZEL validation framework enforces strict provenance rules: no artifact may
be populated with synthetic, placeholder, or externally-fabricated data.  This is
correct and intentional.

However, this invariant creates a structural gap: real data produced by TRIZEL
production/analysis repositories (e.g. `AUTO-DZ-ACT-ANALYSIS-3I-ATLAS`) is not
automatically visible inside the validation repository.  Without a governed
mechanism, the only option is manual copying — which is not auditable, not
scalable, and breaks reproducibility guarantees.

The bridge solves that problem by defining a **controlled, extraction-only path**
from production repositories to validation cases.

---

## What Problem the Bridge Solves

Validation cases enter a blocked state when real source data exists in a
production repository but cannot be accessed within the validation context.

The bridge enables:

    production repository
      → governed source registry
      → controlled extraction
      → validation case population (raw/)
      → provenance update

without introducing hidden logic, external fetches, or provenance loss.

---

## Extraction-Only

The bridge is **extraction-only**.

It does not:

- transform or aggregate data beyond what is declared in `bridge_rules.md`
- fetch data from the public internet
- synthesise or invent data
- bypass provenance requirements
- modify the epistemic rules of the TRIZEL framework

It copies already-existing, repository-visible source material into the
`raw/` directory of the designated validation case and records the exact
origin of every file it touches.

---

## Explicit Provenance

Every extraction performed by the bridge must produce an auditable provenance
record that maps:

    source_repository → source_file_path → target_case/raw/filename

No file may be placed in a case directory without this mapping being written to
the case's `provenance.json` (or a bridge-specific provenance supplement).

---

## Governance Constraints

The bridge operates exclusively for governed validation use within the
`trizel-ai/Auto-dz-act` repository.  It must not be repurposed as a general
repository synchronisation mechanism.

All allowed source repositories and source paths are declared in `registry.json`
before any extraction takes place.  Anything not declared in the registry is
rejected by the extraction script.

---

## Workspace Resolution Prerequisite

Before any extraction can proceed, the local multi-repository workspace must
be resolved.  This means all source repositories declared in
`workspace/repositories.json` must be locally visible at their declared paths.

Run the workspace readiness checker first:

    python validation/bridge/workspace/resolve_workspace_paths.py

Extraction is **blocked** if this check does not exit with status 0.  Source
repositories that are absent or declared only as placeholders prevent
extraction from starting.

See `workspace/README.md` and `workspace/WORKSPACE_RULES.md` for the full
specification of the workspace model.

---

## Components

| File | Role |
|------|------|
| `README.md` | This document |
| `bridge_rules.md` | Strict operational rules for all extractions |
| `registry.json` | Controlled source-to-case mapping |
| `extract_case_data.py` | Extraction script (reads registry, copies files, updates provenance) |
| `workspace/` | Local multi-repository workspace model (readiness checker, rules, registry) |

---

END OF BRIDGE README
