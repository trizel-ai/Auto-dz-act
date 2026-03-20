# TRIZEL Validation Bridge — Operational Rules

**Layer**: Layer-1 (Execution)  
**Version**: 1.0  
**Repository**: https://github.com/trizel-ai/Auto-dz-act

---

## Rule 1 — Extraction Only

The bridge may only **copy** source material from a declared source repository
into the `raw/` directory of the designated validation case.

No data may be created, generated, synthesised, or derived within the bridge
itself.

---

## Rule 2 — No Synthesis

The bridge must never produce file contents that did not already exist in the
declared source repository.

Any transformation step (e.g. renaming, format change) must be:

- explicitly declared in the registry entry for that case
- recorded in the provenance update
- limited to what is strictly necessary for ingestion

---

## Rule 3 — No External Fetching

The bridge must not make any network request or access any resource outside the
local repository context.

All source material must be available as repository-visible files at the time of
extraction.

If a source path resolves to a URL, an API endpoint, or any non-local resource,
extraction must stop immediately.

---

## Rule 4 — No Undeclared Transformations

Every transformation applied to source material must be declared explicitly in
the registry entry for that case under the `"allowed_transformations"` key.

Transformations not listed are forbidden.

If no transformations are declared, the file is copied verbatim.

---

## Rule 5 — Mandatory Source Mapping

Every extraction must establish and record a complete mapping:

    source_repository → source_file_path → target_case/raw/filename

This mapping must be written to `provenance.json` (or a bridge provenance
supplement) before the extraction is considered complete.

No file may be placed in a case directory without this mapping existing in the
provenance record.

---

## Rule 6 — Provenance Must Be Updated Explicitly

After extraction the case provenance record must be updated to reflect:

- `source_repository`: name of the production repository
- `source_file`: exact file path within the source repository
- `extraction_method`: always `"bridge_controlled_extraction"`
- `extraction_timestamp`: ISO-8601 UTC timestamp of the extraction
- `bridge_registry_version`: version of the registry used

The provenance update must be atomic with the file copy.  A partial extraction
(files copied but provenance not updated) is treated as a failure.

---

## Rule 7 — Fail Safely on Unresolvable Sources

If any of the following conditions are detected, extraction must stop
immediately and exit with a non-zero status:

- The source repository path is not accessible in the local context
- The source file path declared in the registry does not exist
- The declared path is not repository-visible (e.g. outside working tree)
- Provenance would become ambiguous (e.g. conflicting records)

No partial state may be left in the case directory.  Any files already copied
in the current run must be rolled back or their provenance clearly marked
`extraction_incomplete`.

---

## Rule 8 — Registry Is Authoritative

The registry (`registry.json`) is the sole authoritative source of allowed
source repositories and source paths.

Auto-discovery of source files is forbidden.

If a file exists in the source repository but is not listed in the registry, it
must not be extracted.

---

## Rule 9 — No Case-Specific Rule Adaptation

These rules apply uniformly to all validation cases.

No case may request an exception to any rule above.

If a case cannot be populated under these rules, the case's `epistemic_state`
must remain `source_extraction_pending` until the registry is updated through
the normal governance process.

---

## Rule 10 — Audit Trail

Every invocation of `extract_case_data.py` must produce a human-readable log
entry (written to stdout or a log file declared at call-time) that records:

- case ID processed
- registry entries consulted
- files copied (source path → destination path)
- provenance fields written
- success or failure reason

---

END OF BRIDGE RULES
