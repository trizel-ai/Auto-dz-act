# TRIZEL Validation Bridge — Local Workspace

**Layer**: Layer-1 (Execution)
**Status**: Active
**Version**: 1.0
**Repository**: https://github.com/trizel-ai/Auto-dz-act

---

## Why Local Multi-Repository Visibility Is Required

The TRIZEL validation bridge is extraction-only: it copies repository-visible
source material from production repositories into validation case directories.
This design is correct.

However, the bridge can only operate automatically when all required source
repositories are **locally visible** at the time of execution.  Without local
visibility the bridge has no material to extract from, and validation remains
blocked or manual.

This workspace layer formalises that requirement.  It does not change any
epistemic rule; it activates the bridge operationally.

---

## Why Bridge Execution Cannot Rely on Network Fetching

Bridge rule 3 (bridge_rules.md) forbids all network requests.  The bridge
must never pull data from the internet, from an API, or from any resource
outside the local repository context.

This means source repositories must be present as local filesystem paths at
the time the bridge runs.  Fetching them on demand would violate the
extraction-only guarantee and would make provenance non-auditable.

---

## How Production Repositories Are Made Visible to the Bridge

Each required repository is declared in `repositories.json` with an
`expected_local_path` field.  Before extraction starts, the workspace
resolver (`resolve_workspace_paths.py`) checks that every required repository
is present at its declared local path.

The expected production repositories for this workspace are:

| Role | Repository |
|------|-----------|
| Validation repository | `trizel-ai/Auto-dz-act` |
| Raw immutable source | `abdelkader-omran/AUTO-DZ-ACT-3I-ATLAS-DAILY` |
| Normalised / epistemic source | `abdelkader-omran/AUTO-DZ-ACT-ANALYSIS-3I-ATLAS` |

Actual local paths must be declared in `repositories.json` once they are
confirmed.  No path is invented or assumed.

---

## This Is a Local Execution Model, Not a Synchronisation Model

Workspace resolution checks for the **presence** of repositories at declared
local paths.  It does not:

- clone or fetch any repository
- synchronise content between repositories
- modify any file in any repository
- perform any extraction

The bridge operates only on repository-visible local paths.  If a path cannot
be confirmed, extraction is blocked until the workspace is correctly set up.

---

## Components

| File | Role |
|------|------|
| `README.md` | This document |
| `WORKSPACE_RULES.md` | Strict rules governing local workspace usage |
| `repositories.json` | Declarative registry of required local repositories |
| `resolve_workspace_paths.py` | Workspace readiness checker (no extraction) |

---

END OF WORKSPACE README
