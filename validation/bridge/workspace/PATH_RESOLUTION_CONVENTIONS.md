# TRIZEL Validation Bridge — Path Resolution Conventions

**Layer**: Layer-1 (Execution)
**Version**: 1.0
**Repository**: https://github.com/trizel-ai/Auto-dz-act

---

## Purpose

This document defines the conventions for how local repository paths are
declared, resolved, and validated within the TRIZEL validation bridge workspace.

Path resolution is governed by the workspace rules in `WORKSPACE_RULES.md`.
This document specifies the *conventions* that support those rules: the expected
directory layouts, path formats, and tooling responsibilities.

---

## Rule PC-1 — Absolute Paths Only

All paths written into `repositories.json` under `expected_local_path` **must
be absolute**.

Relative paths are not permitted in `repositories.json`.  A relative path
cannot be resolved unambiguously across different invocation contexts (CI,
local machines, different working directories).

`bootstrap_workspace.py` normalises all supplied paths to absolute form using
`os.path.abspath` before writing them.  This normalisation is automatic and
non-optional.

---

## Rule PC-2 — No Invented Paths

A path is only written into `repositories.json` if:

1. it was explicitly supplied by the operator via a CLI flag, **or**
2. the sibling-directory probe (PC-3) confirmed it exists as a directory on
   the local filesystem.

Neither `bootstrap_workspace.py` nor any other script may construct, guess, or
hard-code a path and write it without local filesystem confirmation.

Placeholder strings (values beginning with `PLACEHOLDER`) are never treated as
live paths.  They remain in place until replaced by a confirmed path.

---

## Rule PC-3 — Sibling-Directory Probe Convention

When `bootstrap_workspace.py` is invoked with `--probe`, it applies the
following convention:

All TRIZEL repositories are expected to be checked out under the same parent
directory.  Given that the script locates itself at:

    <parent>/Auto-dz-act/validation/bridge/workspace/bootstrap_workspace.py

the probe constructs candidate paths for the source repositories as:

    <parent>/AUTO-DZ-ACT-3I-ATLAS-DAILY
    <parent>/AUTO-DZ-ACT-ANALYSIS-3I-ATLAS

Where `<parent>` is the parent directory of the `Auto-dz-act` checkout.

Example:

    ~/work/trizel/Auto-dz-act                        ← this repository
    ~/work/trizel/AUTO-DZ-ACT-3I-ATLAS-DAILY         ← probed automatically
    ~/work/trizel/AUTO-DZ-ACT-ANALYSIS-3I-ATLAS      ← probed automatically

A probed path is only used if `os.path.isdir` confirms it exists.  Non-existent
candidate paths are silently skipped; the repository remains unconfirmed.

Probe results can be overridden by explicit `--atlas-daily` or
`--atlas-analysis` flags.

---

## Rule PC-4 — Authorised Write Mechanism

`bootstrap_workspace.py` is the designated tool for writing confirmed paths
into `repositories.json`.

Manual edits to `repositories.json` are permitted but must comply with PC-1
(absolute paths) and PC-2 (only write paths that exist locally).

No other script may modify `expected_local_path` values in `repositories.json`.

---

## Rule PC-5 — Bootstrap Is Idempotent

Running `bootstrap_workspace.py` more than once with the same correct paths
produces the same result as running it once.

Re-running with corrected paths after a failed or partial bootstrap is always
safe.  Existing confirmed entries are overwritten with the new value; no state
accumulates between runs.

---

## Rule PC-6 — Bootstrap Does Not Perform Workspace Resolution

`bootstrap_workspace.py` writes paths and reports what was written.  It does
**not** perform the full workspace readiness check.

After bootstrap completes, run `resolve_workspace_paths.py` to verify that
all required repositories are reachable at their confirmed paths.  Only after
`resolve_workspace_paths.py` exits 0 may extraction proceed.

---

## Typical Workflow

```
# Step 1 — Bootstrap (probe mode: auto-detect siblings)
python validation/bridge/workspace/bootstrap_workspace.py --probe

# Step 1 — Bootstrap (explicit paths)
python validation/bridge/workspace/bootstrap_workspace.py \
    --auto-dz-act     /home/user/work/Auto-dz-act \
    --atlas-daily     /home/user/work/AUTO-DZ-ACT-3I-ATLAS-DAILY \
    --atlas-analysis  /home/user/work/AUTO-DZ-ACT-ANALYSIS-3I-ATLAS

# Step 2 — Verify workspace is ready
python validation/bridge/workspace/resolve_workspace_paths.py

# Step 3 — Run extraction (only if step 2 exits 0)
python validation/bridge/extract_case_data.py --case case-001-asteroid
```

---

## Relationship to Workspace Rules

| Path convention | Enforces workspace rule |
|-----------------|------------------------|
| PC-1 absolute paths | W-4 no hidden path assumptions |
| PC-2 no invented paths | W-4 no hidden path assumptions |
| PC-3 sibling probe | W-1 repositories must be present locally |
| PC-4 authorised write mechanism | W-2 explicitly declared repositories |
| PC-5 idempotent bootstrap | W-5 resolve before extraction starts |
| PC-6 bootstrap ≠ resolution | W-5 resolve before extraction starts |

---

END OF PATH RESOLUTION CONVENTIONS
