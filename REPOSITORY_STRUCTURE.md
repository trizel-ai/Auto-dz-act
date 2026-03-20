# Repository Structure

This repository is organized as a **definition-only** reference for AUTO DZ ACT.

---

## Root files

- **README.md** — Entry point and overview
- **LICENSE.md** — Creative Commons Attribution 4.0
- **DEFINITION.md** — Official algorithm definition
- **SCOPE_AND_NONDISCLOSURE.md** — Scope boundaries and neutrality mandate
- **HISTORICAL_PROVENANCE.md** — Provenance and historical record
- **PUBLICATIONS.md** — Citations and archival references
- **MULTILINGUAL_POLICY.md** — Multilingual availability and platform coupling requirements
- **GOVERNANCE.md** — Branch protection and governance requirements
- **REPOSITORY_STRUCTURE.md** — This file

---

## Directories

### reference/
Contains formal policies and reference materials:
- **README.md** — Directory purpose and scope
- **REFERENCE_REQUESTS.md** — Formal authorization and request intake policy
- **GLOSSARY.md** — Terminology and definitions
- **GITHUB_ZENODO_INTEGRATION_VERIFICATION.md** — GitHub-Zenodo integration verification and compliance documentation

### docs/
Contains extended documentation:
- **README.md** — Directory purpose and scope
- **MATHEMATICAL_LOGIC.md** — Mathematical and symbolic logic documentation

### assets/
Contains official visual assets:
- **README.md** — Assets usage guide
- **badges/** — SVG badges (full and compact versions)

### validation/
Contains the multi-phenomena validation framework and case scaffolding:
- **framework.md** — Framework definition: purpose, invariants, cross-case consistency, reproducibility rules
- **cases/** — One sub-directory per validated case:
  - **case-001-asteroid/** — Asteroid phenomenon case
  - **case-002-comet/** — Comet phenomenon case
  - **case-003-interstellar/** — Interstellar object phenomenon case
  - **case-004-neo/** — Near-Earth object (NEO) case
  - **case-005-extended/** — Extended / mixed phenomena case
  - Each case contains: `raw/`, `normalized/`, `manifest.json`, `provenance.json`, `artifact.json`, `epistemic_state.json`, `README.md`
- **summary/** — Validation summary outputs:
  - **validation-report.md** — Cross-case comparison, consistency checks, detected gaps, structural issues, recommendations

---

## Content policy

This repository contains **documentation only**.

No executable code, datasets, or automation may be added.

---

END OF STRUCTURE
