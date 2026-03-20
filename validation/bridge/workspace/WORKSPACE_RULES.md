# TRIZEL Validation Bridge — Workspace Rules

**Layer**: Layer-1 (Execution)
**Version**: 1.0
**Repository**: https://github.com/trizel-ai/Auto-dz-act

---

## Rule W-1 — Source Repositories Must Be Present Locally

Every repository declared as required in `repositories.json` must exist as a
locally accessible directory at the time the bridge is invoked.

If any required repository is absent from the local filesystem, workspace
resolution fails and extraction is blocked.

---

## Rule W-2 — Repositories Must Be Explicitly Declared

Only repositories listed in `repositories.json` may be used as sources for
bridge extraction.

No repository may be discovered, inferred, or introduced at runtime.  If a
repository is needed but not yet declared, it must be added to
`repositories.json` through the normal governance process before extraction
can proceed.

---

## Rule W-3 — No Undeclared Repository May Be Used

Any attempt to reference a repository or local path that is not explicitly
declared in `repositories.json` must be rejected immediately.

The bridge inherits this constraint from bridge rule 8 (registry is
authoritative).  The workspace layer applies the same principle to repository-
level visibility.

---

## Rule W-4 — No Hidden Path Assumptions

No component of the bridge may assume the location of a source repository
without reading it from `repositories.json`.

Hard-coded paths, environment-variable-only paths, and implicit relative paths
are forbidden.  Every path must be traceable to a declared entry in the
workspace registry.

---

## Rule W-5 — Workspace Paths Must Resolve Before Extraction Starts

`resolve_workspace_paths.py` must complete successfully (exit 0) before any
extraction operation is initiated.

Extraction scripts must not be invoked if workspace resolution has not been
performed or has failed.

---

## Rule W-6 — Failure to Resolve Any Required Repository Blocks Extraction

If `resolve_workspace_paths.py` reports any required repository as missing or
unresolvable, the entire extraction pipeline is blocked.

Partial workspace availability does not allow partial extraction.  All
required repositories must be resolved before any extraction proceeds.

---

## Rule W-7 — Workspace Visibility Does Not Change Provenance Obligations

Confirming that a source repository is locally present does not alter any
provenance requirement defined in `bridge_rules.md`.

Every extracted file must still be mapped to its exact origin:

    source_repository → source_file_path → target_case/raw/filename

Workspace resolution is an execution prerequisite, not a relaxation of
governance.

---

## Rule W-8 — No Network Access During Workspace Resolution

`resolve_workspace_paths.py` must not make any network request.

Workspace resolution is a local filesystem check only.  If a repository is
not locally present, the resolver reports it as missing and exits non-zero.
It does not attempt to fetch, clone, or download anything.

---

## Rule W-9 — No Data Modification During Workspace Resolution

`resolve_workspace_paths.py` is a read-only readiness checker.

It must not copy, move, delete, or modify any file in any repository.  It
reports the state of the workspace and nothing else.

---

## Rule W-10 — Workspace Registry Version Must Be Recorded

Every workspace readiness report produced by `resolve_workspace_paths.py`
must include the `workspace_version` field from `repositories.json`.

This ensures that extraction runs can be traced to a specific version of the
workspace declaration.

---

END OF WORKSPACE RULES
