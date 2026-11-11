"""Leakage and model-lock checks for event-blind v2 development artifacts."""
import json
import unittest
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
MODEL_DIR = ROOT / "data/processed/event_blind_v2/modeling"


class EventBlindV2ModelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.regression = json.loads(
            (MODEL_DIR / "regression_candidate_metrics.json").read_text()
        )
        cls.direct = json.loads(
            (MODEL_DIR / "direct_residual_candidate_metrics.json").read_text()
        )
        cls.garch = json.loads((MODEL_DIR / "garch_diagnostics.json").read_text())
        cls.lock = json.loads(
            (ROOT / "configs/event_blind_v2_model_lock.json").read_text()
        )

    def test_final_test_remained_unopened_during_selection(self):
        self.assertFalse(self.regression["final_test_opened"])
        self.assertFalse(self.direct["final_test_opened"])
        self.assertFalse(self.garch["final_test_opened"])
        self.assertFalse(self.lock["final_test_opened"])
        predictions = pd.read_csv(MODEL_DIR / "direct_residual_validation_predictions.csv")
        self.assertLess(predictions["settlement_date"].max(), "2025-01-01")

    def test_locked_names_match_development_selection(self):
        self.assertEqual(
            self.regression["best_regression_candidate"],
            self.lock["point_forecast"]["base_model"],
        )
        self.assertEqual(
            self.direct["best_direct_residual_candidate"],
            self.lock["point_forecast"]["direct_residual_model"],
        )

    def test_selected_v2_improves_v1_and_weekly_naive(self):
        selected = self.direct["candidates"][
            self.direct["best_direct_residual_candidate"]
        ]["summary"]["mean_fold_mae_mw"]
        old = self.regression["candidates"]["calendar_weekly_v1"]["summary"][
            "mean_fold_mae_mw"
        ]
        weekly = self.regression["benchmarks"]["weekly_seasonal_naive"]["summary"][
            "mean_fold_mae_mw"
        ]
        self.assertLess(selected, old)
        self.assertLess(selected, weekly)

    def test_garch_converged_but_residual_claim_remains_cautious(self):
        self.assertTrue(self.garch["summary"]["all_folds_converged"])
        self.assertFalse(self.lock["residual_independence_achieved"])
        self.assertFalse(self.lock["constant_conditional_variance_achieved"])


if __name__ == "__main__":
    unittest.main()
