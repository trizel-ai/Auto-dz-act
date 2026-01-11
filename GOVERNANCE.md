# Governance & Branch Protection

---

## Purpose

This document specifies the governance and branch protection requirements for the AUTO DZ ACT repository to ensure the v1.0 definition remains locked and protected against accidental or hostile modification.

---

## Branch Protection Ruleset

**Repository administrators must configure the following branch protection ruleset:**

### Ruleset Configuration

- **Ruleset name**: `main-definition-protection`
- **Enforcement status**: Enabled
- **Target branches**: `main`

### Required Rules

The following rules must be enabled:

1. **Prevent force pushes**  
   - Ensures commit history cannot be rewritten

2. **Prevent branch deletion**  
   - Protects the main branch from accidental removal

3. **Require pull requests before merging**  
   - All changes must go through PR review process

4. **Require at least one review**  
   - Minimum one approval required (Copilot review allowed)

### Bypass List

The following entities may bypass branch protection rules for administrative purposes:

- **Repository admin**: `abdelkader-omran`
- **GitHub Copilot**: For review purposes only (not for force push)

---

## Rationale

These protections serve to:

- Lock the v1.0 definition as a stable reference
- Prevent unauthorized modifications
- Maintain scientific integrity
- Ensure all changes are reviewed
- Preserve commit history for traceability

---

## Implementation

**Note**: These settings require repository administrator access and must be configured through GitHub's web interface:

1. Navigate to: Repository Settings → Rules → Rulesets
2. Create new ruleset with name: `main-definition-protection`
3. Set target branches to: `main`
4. Enable all required rules listed above
5. Configure bypass permissions as specified
6. Activate the ruleset

---

## Compliance

Once implemented, this ruleset ensures that:

- ✓ The main branch cannot be force-pushed
- ✓ The main branch cannot be deleted
- ✓ All changes require pull request review
- ✓ At least one approval is required before merge
- ✓ Authorized admins can override when necessary

---

**Version**: 1.0  
**Repository**: https://github.com/trizel-ai/Auto-dz-act  
**Last Updated**: 2026-01-11

---

END OF GOVERNANCE
