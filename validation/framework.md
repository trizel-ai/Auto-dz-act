# TRIZEL Multi-Phenomena Validation Framework

**Layer**: Layer-1 (Execution)  
**Status**: Active  
**Version**: 1.0  
**Repository**: https://github.com/trizel-ai/Auto-dz-act

---

## A. Purpose

This framework defines the **operational validation layer** for TRIZEL across multiple heterogeneous scientific phenomena.

It is NOT a new epistemic model.

Its purpose is to verify that TRIZEL:

- remains consistent across domains
- preserves provenance integrity
- enforces repository → layer → artifact traceability
- produces reproducible outputs

---

## B. Invariants

The following rules MUST NEVER be violated in any validated case:

1. No artifact without explicit provenance
2. No repository without defined epistemic role
3. No DOI/release without contextual interpretation
4. No artifact detached from its governance path
5. No case-specific rule adaptation

---

## C. Cross-Case Consistency

All validation cases MUST:

- follow identical directory structure
- use the same artifact schema
- use the same provenance format
- preserve naming consistency across all fields and files

Any deviation in structure is a framework violation, not a case exception.

---

## D. Case Structure

Each case MUST include the following files and directories:

```
case-XXX/
├── raw/                  ← unmodified source data
├── normalized/           ← processed standardized data
├── manifest.json         ← file index + hashes
├── provenance.json       ← full lineage (repo, layer, source)
├── artifact.json         ← structured output
├── epistemic_state.json  ← state classification
└── README.md             ← case description (no interpretation)
```

---

## E. Validation Criteria

Each case must pass all of the following checks before being considered validated:

- ✔ Full provenance chain present
- ✔ Repository attribution explicit
- ✔ Epistemic layer clearly defined
- ✔ DOI / release classification correct (if applicable)
- ✔ No missing metadata fields
- ✔ Reproducible outputs
- ✔ No ambiguity in artifact definition

---

## F. Reproducibility

Given identical inputs:

- outputs must be identical
- manifests must match
- hashes must match (if applicable)

Reproducibility is a structural requirement, not a best-effort goal.

---

## G. Critical Rule

TRIZEL rules MUST NOT be adapted per case.

If a case breaks the system:

→ the system must be corrected  
→ NOT the case

---

## H. Registered Cases

| Case ID | Phenomenon | Status |
|---------|-----------|--------|
| case-001 | Asteroid | Scaffolded |
| case-002 | Comet | Scaffolded |
| case-003 | Interstellar object | Scaffolded |
| case-004 | Near-Earth object (NEO) | Scaffolded |
| case-005 | Extended / mixed phenomena | Scaffolded |

---

## I. Scope Boundaries

This framework:

- operates at Layer-1 (execution)
- does NOT modify Layer-0 governance
- does NOT modify Layer-2 site
- does NOT interpret scientific results
- does NOT assert physical theories

---

END OF FRAMEWORK
