"""Canonical consumption of TRZ-PHY-ASTR-001 from trizel-core catalog JSON.

Usage
-----
    from auto_dz_act.canonical.trz_phy_astr_001 import load_trz_phy_astr_001

    constants = load_trz_phy_astr_001("/path/to/TRZ-PHY-ASTR-001.json")

The caller must supply the path to the catalog JSON.  No default path is
provided: the execution environment is responsible for making the JSON
available (e.g. as an artifact) and passing its path at call-time.

No network calls are made.  All numeric values are held as ``decimal.Decimal``
instances initialised from the JSON string fields, so no floating-point
representation error is introduced.

Allowed consumption fields (see references/TRZ-PHY-ASTR-001.pointer.md):
- inputs.Y_SOLAR_TT_DAYS           — string decimal
- inputs.Y_LUNAR_12_SYNODIC_DAYS   — string decimal
- approved_rational_forms.fast     — (p, q) integers
- approved_rational_forms.stable   — (p, q) integers
"""

import json
from decimal import Decimal
from typing import NamedTuple


class RationalForm(NamedTuple):
    """An exact rational p/q with integer numerator and denominator."""

    p: int
    q: int


class TrzPhyAstr001(NamedTuple):
    """Immutable container for the four allowed TRZ-PHY-ASTR-001 fields."""

    y_solar_tt_days: Decimal
    y_lunar_12_synodic_days: Decimal
    rational_fast: RationalForm
    rational_stable: RationalForm


def load_trz_phy_astr_001(json_path: str) -> TrzPhyAstr001:
    """Load TRZ-PHY-ASTR-001 constants from a caller-supplied catalog JSON.

    Parameters
    ----------
    json_path:
        Absolute or relative path to TRZ-PHY-ASTR-001.json as provided by
        the execution environment.  The file must conform to the trizel-core
        catalog schema.

    Returns
    -------
    TrzPhyAstr001
        Immutable named-tuple.  Decimal fields are initialised from the JSON
        string values; no float conversion is performed at any stage.

    Raises
    ------
    FileNotFoundError
        If ``json_path`` does not exist.
    KeyError
        If required fields are absent from the JSON.
    """
    with open(json_path, encoding="utf-8") as fh:
        data = json.load(fh)

    inputs = data["inputs"]
    rational = data["approved_rational_forms"]

    return TrzPhyAstr001(
        y_solar_tt_days=Decimal(inputs["Y_SOLAR_TT_DAYS"]),
        y_lunar_12_synodic_days=Decimal(inputs["Y_LUNAR_12_SYNODIC_DAYS"]),
        rational_fast=RationalForm(
            p=int(rational["fast"]["p"]),
            q=int(rational["fast"]["q"]),
        ),
        rational_stable=RationalForm(
            p=int(rational["stable"]["p"]),
            q=int(rational["stable"]["q"]),
        ),
    )
