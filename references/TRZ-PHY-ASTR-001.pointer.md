# Pointer: TRZ-PHY-ASTR-001

- **Pointer ID:** AUTO-DZ-ACT-REF-TRZ-PHY-ASTR-001
- **Consumer:** auto_dz_act
- **Canonical Source:** trizel-core
- **Canonical Const ID:** TRZ-PHY-ASTR-001
- **Canonical File Path:** trizel_core/physics/catalog/TRZ-PHY-ASTR-001.json
- **Status:** REFERENCE_ONLY (no computation here)

---

## Usage Rule

- auto_dz_act MUST NOT hardcode floats for this ratio.
- Any numeric use must be sourced from the canonical JSON in trizel-core (string decimals + rational pairs).

---

## Allowed Consumption Fields

- `inputs.Y_SOLAR_TT_DAYS` (string decimal)
- `inputs.Y_LUNAR_12_SYNODIC_DAYS` (string decimal)
- `approved_rational_forms.fast` (p,q)
- `approved_rational_forms.stable` (p,q)

---

## Non-Activation Clause

No analysis, no physics claims, no Gate transitions, no Gate-6 activation, no publication.

---

END OF POINTER
