import json
import unittest
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data/processed/match_aware_v3"
LOCK = json.loads((ROOT / "configs/match_aware_v3_model_lock.json").read_text())


class MatchAwareV3Tests(unittest.TestCase):
    def test_historical_baselines_cover_only_two_selection_editions(self):
        rows = pd.read_csv(OUT / "tournament_v3_baselines_historical_only.csv")
        self.assertEqual(rows["match_id"].nunique(), 12)
        self.assertEqual(
            set(rows["tournament_edition"].unique()),
            {"UEFA EURO 2020", "FIFA World Cup 2022"},
        )

    def test_selection_never_reads_euro_2024(self):
        result = json.loads((OUT / "correction_selection.json").read_text())
        self.assertFalse(result["euro_2024_read"])
        self.assertTrue(result["future_untouched_tournament_required"])

    def test_locked_shape_correction_improves_both_historical_editions(self):
        result = json.loads((OUT / "correction_selection.json").read_text())
        selected = result["selected_correction"]
        self.assertEqual(selected, "shape_four_window")
        item = result["candidates"][selected]
        self.assertTrue(item["improves_both_editions"])
        self.assertLess(item["mae_mw"], result["baseline"]["mae_mw"])

    def test_versioned_lock_matches_selection(self):
        result = json.loads((OUT / "correction_selection.json").read_text())
        selected = result["selected_correction"]
        self.assertEqual(LOCK["schedule_correction"]["name"], selected)
        for feature, value in LOCK["schedule_correction"]["coefficients_mw"].items():
            observed = result["candidates"][selected]["final_coefficients"][feature][
                "estimate_mw"
            ]
            self.assertAlmostEqual(value, observed)


if __name__ == "__main__":
    unittest.main()
