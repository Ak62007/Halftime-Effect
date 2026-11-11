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

    def test_euro_2024_is_retrospective_and_not_retuned(self):
        result = json.loads(
            (OUT / "euro_2024_retrospective_evaluation.json").read_text()
        )
        self.assertFalse(result["new_holdout_claim"])
        self.assertFalse(result["model_changed_after_locked_rerun"])
        self.assertEqual(result["matches"], 7)
        self.assertTrue(result["future_untouched_tournament_required"])

    def test_euro_2024_halftime_improves_but_primary_window_does_not(self):
        result = json.loads(
            (OUT / "euro_2024_retrospective_evaluation.json").read_text()
        )
        primary = result["scope_metrics"]["event_window_primary"]
        halftime = result["scope_metrics"]["halftime_proxy_window"]
        self.assertGreater(
            primary["v3_match_aware"]["mae_mw"],
            primary["v3_event_blind"]["mae_mw"],
        )
        self.assertLess(
            halftime["v3_match_aware"]["mae_mw"],
            halftime["v3_event_blind"]["mae_mw"],
        )

    def test_forward_refit_uses_all_nineteen_matches_without_claiming_evaluation(self):
        result = json.loads((OUT / "forward_model_refit.json").read_text())
        forward = json.loads(
            (ROOT / "configs/match_aware_v3_forward_model.json").read_text()
        )
        self.assertEqual(result["training_matches"], 19)
        self.assertTrue(result["future_untouched_tournament_required"])
        self.assertIn("not evaluated", forward["status"])
        for feature, value in forward["schedule_correction"][
            "coefficients_mw"
        ].items():
            self.assertAlmostEqual(value, result["coefficients"][feature]["estimate_mw"])


if __name__ == "__main__":
    unittest.main()
