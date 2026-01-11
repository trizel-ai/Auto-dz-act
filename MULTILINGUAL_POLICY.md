# Multilingual Availability & Public Reference Requirement

---

## Status

This document establishes the **multilingual publication policy** and **reference coupling requirements** for AUTO DZ ACT documentation.

**Authority**: This GitHub repository (`trizel-ai/Auto-dz-act`) is the canonical source.

---

## Multilingual requirement

All authoritative definition files of AUTO DZ ACT **must be made available in all languages officially supported by the TRIZEL-AI platform**:

**Platform**: https://trizel-ai.com/

### Minimum language coverage

- Primary language of publication
- English
- Any additional languages exposed through the platform interface

---

## Reference coupling

### GitHub as canonical source

- **GitHub repository**: `trizel-ai/Auto-dz-act`
- **Role**: Authoritative, version-controlled reference source
- **Precedence**: GitHub takes precedence over all other publications

### Website publication requirements

The website https://trizel-ai.com/ must:

1. **Publish faithful representations** of GitHub documentation
2. **Maintain version alignment** with GitHub commits
3. **Never contradict** the GitHub definition
4. **Never extend** beyond what GitHub states
5. **Never reinterpret** the documented scope

### In case of discrepancy

**GitHub is authoritative.**

If any webpage contradicts GitHub documentation, the GitHub version is correct and the webpage is in error.

---

## Public accessibility mandate

### Access requirements

- **All definition pages** must be publicly accessible
- **No authentication** required to view documentation
- **No paywalls** or registration barriers
- **Direct linking** must be supported

### Version traceability

Published web pages must clearly display:
- The exact **GitHub commit hash** they mirror
- The **version number** (e.g., v1.0)
- The **last updated date**
- A **link back to the GitHub source**

### Example version reference

```
Source: github.com/trizel-ai/Auto-dz-act
Commit: [commit-hash]
Version: 1.0
Last updated: 2026-01-10
```

---

## Scope preservation in translation

### Non-negotiable constraints

Multilingual publication does NOT:
- Alter the scope of AUTO DZ ACT
- Introduce theory-specific context
- Grant interpretative authority to translations
- Create new definitions or explanations
- Add cultural or contextual interpretations

### Translation fidelity

Translations are **representational only** and must:

1. **Preserve strict neutrality** — no theory names in any language
2. **Maintain wording fidelity** — faithful to original meaning
3. **Use equivalent neutral terms** — no introduction of bias
4. **Keep symbolic notation unchanged** — (E, M, D), (DZ), etc.
5. **Preserve all disclaimers and warnings**

### Translation review

All translations must be:
- Reviewed for neutrality compliance
- Verified against the English/primary version
- Checked for unintentional theoretical bias
- Approved before publication

---

## Required documents for multilingual publication

The following documents must be available in all supported languages:

### Core documents (mandatory)
- **README.md**
- **DEFINITION.md**
- **SCOPE_AND_NONDISCLOSURE.md**
- **HISTORICAL_PROVENANCE.md**
- **PUBLICATIONS.md**

### Reference documents (mandatory)
- **reference/REFERENCE_REQUESTS.md**
- **reference/GLOSSARY.md**

### Extended documentation (recommended)
- **docs/MATHEMATICAL_LOGIC.md**
- **REPOSITORY_STRUCTURE.md**

---

## Platform responsibilities

The TRIZEL-AI platform (https://trizel-ai.com/) is responsible for:

1. **Hosting** multilingual versions of all mandatory documents
2. **Maintaining** version synchronization with GitHub
3. **Displaying** clear version/commit references
4. **Ensuring** public accessibility without barriers
5. **Preventing** contradictions or unauthorized extensions
6. **Updating** translations when GitHub source changes

---

## Enforcement

### Violation examples

The following constitute violations of this policy:

❌ Website adds theory names not in GitHub version  
❌ Website omits neutrality disclaimers  
❌ Translation introduces interpretative language  
❌ Website requires login to view definitions  
❌ Website fails to reference source commit  
❌ Website extends definitions beyond GitHub scope  

### Correction mechanism

When violations are detected:
1. GitHub version is cited as authoritative
2. Website must correct to match GitHub
3. Incorrect versions must be removed or marked as deprecated
4. Version history must document the correction

---

## Update synchronization

### When GitHub updates

1. Website translations must be updated within reasonable timeframe
2. Old versions must be clearly marked as superseded
3. Version numbers must increment consistently
4. Commit references must be updated

### Translation workflow

Recommended process:
1. GitHub repository updated (English/primary language)
2. Commit tagged with version number
3. Translations prepared for all supported languages
4. Translations reviewed for neutrality and fidelity
5. Website updated with new versions
6. Commit hash and version displayed on all pages

---

## Language-specific considerations

### Neutral terminology across languages

Care must be taken to ensure that:
- Technical terms remain consistent across languages
- No language introduces cultural bias
- Symbolic notation remains unchanged
- Citations and DOIs are identical in all languages

### Example: Avoiding theory-specific terms

If a language has common terms that imply specific theories:
- Use neutral descriptive phrases instead
- Add glossary entries to clarify neutral usage
- Never use theory-laden vocabulary

---

## GitHub repository language structure (optional)

If multilingual files are added to this GitHub repository, they should be organized as:

```
Auto-dz-act/
├── README.md (English)
├── README.fr.md (French)
├── README.ar.md (Arabic)
├── DEFINITION.md (English)
├── DEFINITION.fr.md (French)
├── DEFINITION.ar.md (Arabic)
...
```

However, **website hosting is the primary multilingual mechanism**.  
GitHub may remain English-only with translations hosted on https://trizel-ai.com/.

---

## Compliance verification

To verify compliance:

### Website checklist
- [ ] All mandatory documents published in all supported languages
- [ ] Public access without authentication
- [ ] Commit hash and version clearly displayed
- [ ] Direct link to GitHub source provided
- [ ] No theory names introduced
- [ ] No scope extensions beyond GitHub
- [ ] Translations faithful to original

### GitHub checklist
- [ ] All source documents theory-neutral
- [ ] Version tags used for releases
- [ ] Commit history clean and traceable
- [ ] No executable code present

---

## Authority and precedence

In all cases:

**GitHub repository `trizel-ai/Auto-dz-act` is the authoritative source.**

Website, translations, and all derivative publications are subordinate to the GitHub version.

---

**Version**: 1.0  
**Repository**: https://github.com/trizel-ai/Auto-dz-act  
**Platform**: https://trizel-ai.com/  
**Last Updated**: 2026-01-10

---

END OF MULTILINGUAL POLICY
