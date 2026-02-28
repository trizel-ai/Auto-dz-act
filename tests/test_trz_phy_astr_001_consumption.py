"""Tests for canonical consumption of TRZ-PHY-ASTR-001.

The fixture at tests/fixtures/TRZ-PHY-ASTR-001.json is used as a stand-in for
the trizel-core catalog JSON; it is TEST FIXTURE ONLY and is not a vendored
canonical source.
"""

import os
import sys
import tempfile
import unittest
from decimal import Decimal

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from auto_dz_act.canonical.trz_phy_astr_001 import (
    RationalForm,
    TrzPhyAstr001,
    load_trz_phy_astr_001,
)

_FIXTURE = os.path.join(
    os.path.dirname(__file__), "fixtures", "TRZ-PHY-ASTR-001.json"
)


class TestLoadTrzPhyAstr001(unittest.TestCase):
    def setUp(self):
        self.c = load_trz_phy_astr_001(_FIXTURE)

    # --- return type ----------------------------------------------------------

    def test_returns_trz_phy_astr_001(self):
        self.assertIsInstance(self.c, TrzPhyAstr001)

    # --- Decimal fields -------------------------------------------------------

    def test_y_solar_tt_days_is_decimal(self):
        self.assertIsInstance(self.c.y_solar_tt_days, Decimal)

    def test_y_lunar_12_synodic_days_is_decimal(self):
        self.assertIsInstance(self.c.y_lunar_12_synodic_days, Decimal)

    def test_no_floats_in_decimal_fields(self):
        self.assertNotIsInstance(self.c.y_solar_tt_days, float)
        self.assertNotIsInstance(self.c.y_lunar_12_synodic_days, float)

    def test_decimal_values_match_fixture(self):
        self.assertEqual(self.c.y_solar_tt_days, Decimal("365.25"))
        self.assertEqual(self.c.y_lunar_12_synodic_days, Decimal("354.36708"))

    # --- rational forms -------------------------------------------------------

    def test_rational_fast_is_rational_form(self):
        self.assertIsInstance(self.c.rational_fast, RationalForm)

    def test_rational_stable_is_rational_form(self):
        self.assertIsInstance(self.c.rational_stable, RationalForm)

    def test_rational_p_q_are_integers(self):
        self.assertIsInstance(self.c.rational_fast.p, int)
        self.assertIsInstance(self.c.rational_fast.q, int)
        self.assertIsInstance(self.c.rational_stable.p, int)
        self.assertIsInstance(self.c.rational_stable.q, int)

    def test_rational_values_match_fixture(self):
        self.assertEqual(self.c.rational_fast, RationalForm(p=365, q=354))
        self.assertEqual(self.c.rational_stable, RationalForm(p=4383, q=4251))

    # --- immutability ---------------------------------------------------------

    def test_result_is_immutable(self):
        with self.assertRaises((AttributeError, TypeError)):
            self.c.y_solar_tt_days = Decimal("0")  # type: ignore[misc]

    # --- error handling -------------------------------------------------------

    def test_missing_file_raises_file_not_found(self):
        with self.assertRaises(FileNotFoundError):
            load_trz_phy_astr_001("/nonexistent/path/TRZ-PHY-ASTR-001.json")

    def test_missing_key_raises_key_error(self):
        import json

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as fh:
            json.dump({"inputs": {}, "approved_rational_forms": {}}, fh)
            bad_path = fh.name
        try:
            with self.assertRaises(KeyError):
                load_trz_phy_astr_001(bad_path)
        finally:
            os.unlink(bad_path)


if __name__ == "__main__":
    unittest.main()
