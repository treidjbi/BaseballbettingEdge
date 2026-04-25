import unittest
import os
import sys


sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "analytics", "diagnostics"))

from ump_diag_utils import unpack_fetch_umpires_result  # noqa: E402


class TestUmpDiagUtils(unittest.TestCase):
    def test_unpack_fetch_umpires_result_accepts_tuple_contract(self):
        result, diagnostics = unpack_fetch_umpires_result((
            {"Pitcher A": 0.25},
            {"hp_count_fetched": 1, "pitcher_nonzero_count": 1},
        ))

        self.assertEqual(result, {"Pitcher A": 0.25})
        self.assertEqual(
            diagnostics,
            {"hp_count_fetched": 1, "pitcher_nonzero_count": 1},
        )

    def test_unpack_fetch_umpires_result_preserves_legacy_dict_shape(self):
        result, diagnostics = unpack_fetch_umpires_result({"Pitcher A": 0.0})
        self.assertEqual(result, {"Pitcher A": 0.0})
        self.assertEqual(diagnostics, {})
