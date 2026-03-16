# CONSUMPTION_RULE — TRZ-PHY-ASTR-001 (TRIZEL PHY_ASTR RATIO)

## 1. Canonical Source

- **Canonical repository:** `trizel-ai/trizel-core`
- **Canonical constant:** `TRZ-PHY-ASTR-001`
- **Canonical file:**
  `trizel_core/physics/catalog/TRZ-PHY-ASTR-001.json`

**Rule:**
Auto-dz-act is a CONSUMER only and must never become a truth-source.

---

## 2. Mandatory Input Rule

The loader must require a caller-supplied JSON path.

**Example signature:**

```
load_trz_phy_astr_001(json_path: str)
```

**Forbidden:**

- default paths
- embedded constants
- vendored copies of the JSON

---

## 3. Allowed JSON Fields

Only these fields may be consumed:

```
inputs.Y_SOLAR_TT_DAYS
inputs.Y_LUNAR_12_SYNODIC_DAYS
approved_rational_forms.fast
approved_rational_forms.stable
```

All decimal values must be read as **STRING** and converted to `Decimal`.

---

## 4. Prohibitions

- No hardcoded floats
- No duplication of canonical JSON
- No network retrieval
- No Gate transitions
- Gate-6 must remain **CLOSED**

---

## 5. Illustrative Pseudocode (non-executable)

```
function load_trz_phy_astr_001(json_path):
    data = read_json(json_path)

    solar = Decimal(data.inputs.Y_SOLAR_TT_DAYS)
    lunar = Decimal(data.inputs.Y_LUNAR_12_SYNODIC_DAYS)

    ratio = solar / lunar

    return ratio
```

---

END OF CONSUMPTION RULE
