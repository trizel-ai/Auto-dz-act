"""Tests for auto_dz_act.constants — TRZ-PHY-ASTR-001 loader."""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from auto_dz_act.constants import (
    RationalForm,
    TrzPhyAstr001,
    load_trz_phy_astr_001,
)

_CATALOG_PATH = os.path.join(
    os.path.dirname(__file__), "..", "catalog", "TRZ-PHY-ASTR-001.json"
)


class TestTrzPhyAstr001Loader(unittest.TestCase):
    def setUp(self):
        self.constants = load_trz_phy_astr_001()

    def test_returns_named_tuple(self):
        self.assertIsInstance(self.constants, TrzPhyAstr001)

    def test_y_solar_tt_days_is_string(self):
        self.assertIsInstance(self.constants.y_solar_tt_days, str)

    def test_y_lunar_12_synodic_days_is_string(self):
        self.assertIsInstance(self.constants.y_lunar_12_synodic_days, str)

    def test_no_hardcoded_floats(self):
        self.assertNotIsInstance(self.constants.y_solar_tt_days, float)
        self.assertNotIsInstance(self.constants.y_lunar_12_synodic_days, float)

    def test_rational_fast_is_rational_form(self):
        self.assertIsInstance(self.constants.rational_fast, RationalForm)

    def test_rational_stable_is_rational_form(self):
        self.assertIsInstance(self.constants.rational_stable, RationalForm)

    def test_rational_p_q_are_integers(self):
        fast = self.constants.rational_fast
        stable = self.constants.rational_stable
        self.assertIsInstance(fast.p, int)
        self.assertIsInstance(fast.q, int)
        self.assertIsInstance(stable.p, int)
        self.assertIsInstance(stable.q, int)

    def test_custom_catalog_path(self):
        constants = load_trz_phy_astr_001(catalog_path=_CATALOG_PATH)
        self.assertEqual(constants, self.constants)

    def test_result_is_immutable(self):
        with self.assertRaises((AttributeError, TypeError)):
            self.constants.y_solar_tt_days = "0"  # type: ignore[misc]


if __name__ == "__main__":
    unittest.main()
