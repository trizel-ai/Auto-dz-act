# Case 001 — Asteroid Validation Case

## Purpose

This case is the first operational validation of TRIZEL on a small-body asteroid observational dataset.

It is designed to validate:

- provenance completeness
- artifact structure
- repository-to-layer mapping
- epistemic consistency

## Source Repositories

| Role | Repository |
|------|------------|
| Raw data (Step A) | `abdelkader-omran/AUTO-DZ-ACT-3I-ATLAS-DAILY` |
| Normalized data (Step B) | `abdelkader-omran/AUTO-DZ-ACT-ANALYSIS-3I-ATLAS` |

## Extraction Path

```
AUTO-DZ-ACT-3I-ATLAS-DAILY     → raw/
AUTO-DZ-ACT-ANALYSIS-3I-ATLAS  → normalized/
```

No mixing. No inversion. No shared paths between raw and normalized extraction.

## Source Extraction Status

**PENDING WORKSPACE RESOLUTION — extraction blocked.**

The source repositories are declared in the bridge registry and workspace configuration.
Extraction cannot proceed until:

1. `validation/bridge/workspace/bootstrap_workspace.py` confirms all repository paths.
2. `validation/bridge/workspace/resolve_workspace_paths.py` reports:
   `ALL REQUIRED REPOSITORIES ARE RESOLVED`

Population of `raw/` and `normalized/` has not occurred.

No synthetic, placeholder, or externally-sourced data has been introduced.

## Files Added

None. `raw/` and `normalized/` remain unpopulated pending workspace resolution.

## Extraction Pipeline

```
bootstrap_workspace.py          ← resolve local paths for all required repos
  → resolve_workspace_paths.py  ← confirm all repos present (exit 0)
  → extract_case_data.py        ← Step A: DAILY → raw/
                                   Step B: ANALYSIS → normalized/
  → provenance.json             ← dual-source lineage recorded
  → manifest.json               ← real file inventory with sha256
  → artifact.json               ← status: extraction_complete
  → epistemic_state.json        ← state: extracted_raw_and_normalized
```

## Current Validation State

- Raw data: not present (pending workspace resolution)
- Normalized data: not present (pending workspace resolution)
- Manifest: configured, pending population
- Provenance: dual-source lineage declared, pending extraction
- Artifact: pending workspace resolution
- Epistemic state: `pending_workspace_resolution`

## Governance

Extraction governed by:

- `validation/bridge/bridge_rules.md`
- `validation/bridge/registry.json`
- `validation/bridge/workspace/WORKSPACE_RULES.md`

## Scope

This case does NOT introduce interpretation.

It strictly implements:

raw → normalized → manifest → provenance → artifact → epistemic_state

## Layer

Layer-1 (Execution)

## Repository

trizel-ai/Auto-dz-act

## Structure

```
case-001-asteroid/
├── raw/                  ← populated from AUTO-DZ-ACT-3I-ATLAS-DAILY (pending)
├── normalized/           ← populated from AUTO-DZ-ACT-ANALYSIS-3I-ATLAS (pending)
├── manifest.json         ← file registry (pending population)
├── provenance.json       ← dual-source lineage (declared, pending extraction)
├── artifact.json         ← structured output definition (pending extraction)
├── epistemic_state.json  ← classification of epistemic state
└── README.md             ← structural description (no interpretation)
```

---

END OF CASE README
