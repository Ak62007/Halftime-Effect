"""Integrity checks for locked model-selection artifacts."""
import json
import unittest
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
MODEL_DIR = ROOT / "data/processed/match_aware/modeling"


class MatchAwareModelSelectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.general = json.loads(
            (MODEL_DIR / "match_correction_selection.json").read_text()
        )
        cls.tournament = json.loads(
            (MODEL_DIR / "tournament_correction_selection.json").read_text()
        )

    def test_general_policy_respects_no_improvement_gate(self):
        self.assertFalse(self.general["correction_passes_deployment_gate"])
        self.assertEqual(self.general["selected_correction"], "no_correction")

    def test_tournament_selection_is_locked_before_holdout(self):
        self.assertFalse(self.tournament["euro_2024_holdout_opened"])
        self.assertTrue(self.tournament["selection_locked_before_euro_2024"])
        self.assertEqual(self.tournament["selected_tournament_correction"], "four_window")

    def test_cross_edition_predictions_cover_twelve_fixtures(self):
        predictions = pd.read_csv(
            MODEL_DIR / "tournament_correction_cross_edition_predictions.csv"
        )
        four_window = predictions.loc[predictions["candidate"].eq("four_window")]
        self.assertEqual(four_window["match_id"].nunique(), 12)
        self.assertEqual(set(four_window["tournament_edition"]), {
            "UEFA EURO 2020",
            "FIFA World Cup 2022",
        })

    def test_no_euro_2024_rows_enter_selection_predictions(self):
        predictions = pd.read_csv(
            MODEL_DIR / "tournament_correction_cross_edition_predictions.csv"
        )
        self.assertFalse(predictions["match_id"].str.contains("2024").any())


if __name__ == "__main__":
    unittest.main()
