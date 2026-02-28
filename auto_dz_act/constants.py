"""Loader for TRZ-PHY-ASTR-001 canonical constants.

Reads from the vendored catalog JSON only. No network calls.
See: references/TRZ-PHY-ASTR-001.pointer.md
"""

import json
import os
from typing import NamedTuple

_CATALOG_PATH = os.path.join(
    os.path.dirname(__file__), "..", "catalog", "TRZ-PHY-ASTR-001.json"
)


class RationalForm(NamedTuple):
    p: int
    q: int


class TrzPhyAstr001(NamedTuple):
    y_solar_tt_days: str
    y_lunar_12_synodic_days: str
    rational_fast: RationalForm
    rational_stable: RationalForm


def load_trz_phy_astr_001(catalog_path: str = _CATALOG_PATH) -> TrzPhyAstr001:
    """Load TRZ-PHY-ASTR-001 constants from the vendored catalog JSON.

    Parameters
    ----------
    catalog_path:
        Path to TRZ-PHY-ASTR-001.json. Defaults to the vendored copy at
        catalog/TRZ-PHY-ASTR-001.json.

    Returns
    -------
    TrzPhyAstr001
        Immutable named-tuple with the four allowed consumption fields:
        y_solar_tt_days, y_lunar_12_synodic_days, rational_fast, rational_stable.
    """
    with open(catalog_path, encoding="utf-8") as fh:
        data = json.load(fh)

    inputs = data["inputs"]
    rational = data["approved_rational_forms"]

    return TrzPhyAstr001(
        y_solar_tt_days=inputs["Y_SOLAR_TT_DAYS"],
        y_lunar_12_synodic_days=inputs["Y_LUNAR_12_SYNODIC_DAYS"],
        rational_fast=RationalForm(
            p=int(rational["fast"]["p"]),
            q=int(rational["fast"]["q"]),
        ),
        rational_stable=RationalForm(
            p=int(rational["stable"]["p"]),
            q=int(rational["stable"]["q"]),
        ),
    )
