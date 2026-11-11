import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODEL_DIR = ROOT / "data/processed/event_blind_v3/modeling"
LOCK = json.loads((ROOT / "configs/event_blind_v3_model_lock.json").read_text())


class EventBlindV3ModelTests(unittest.TestCase):
    def test_every_selection_artifact_keeps_final_test_unopened(self):
        files = [
            "ridge_ablation_metrics.json",
            "nonlinear_candidate_metrics.json",
            "dynamic_candidate_metrics.json",
            "point_model_selection.json",
            "variance_model_diagnostics.json",
            "interval_calibration.json",
            "arma_candidate_metrics.json",
        ]
        for filename in files:
            artifact = json.loads((MODEL_DIR / filename).read_text())
            self.assertFalse(artifact["final_test_opened"], filename)

    def test_locked_point_model_matches_development_selection(self):
        selection = json.loads((MODEL_DIR / "point_model_selection.json").read_text())
        self.assertEqual(selection["selected_point_model"], "blend_ridge_0.5_hgb_0.5")
        self.assertAlmostEqual(
            selection["selected_summary"]["mean_fold_mae_mw"],
            LOCK["development_mean_fold_mae_mw"],
        )
        self.assertEqual(LOCK["research_point_forecast"]["ridge_blend_weight"], 0.5)
        self.assertEqual(LOCK["research_point_forecast"]["hgb_blend_weight"], 0.5)

    def test_v3_improves_v2_and_weekly_naive_in_development(self):
        ridge = json.loads((MODEL_DIR / "ridge_ablation_metrics.json").read_text())
        selected = LOCK["development_mean_fold_mae_mw"]
        self.assertLess(
            selected,
            ridge["candidates"]["v2_ridge_reproduced"]["summary"][
                "mean_fold_mae_mw"
            ],
        )
        self.assertLess(
            selected,
            ridge["benchmarks"]["weekly_seasonal_naive"]["summary"][
                "mean_fold_mae_mw"
            ],
        )

    def test_structured_intervals_meet_coverage_constraint_and_are_sharpest(self):
        calibration = json.loads((MODEL_DIR / "interval_calibration.json").read_text())
        self.assertEqual(calibration["selected_interval_scale_model"], "structured")
        structured = calibration["models"]["structured"]["summary"]
        self.assertLessEqual(abs(structured["mean_80_coverage"] - 0.8), 0.01)
        self.assertLessEqual(abs(structured["mean_95_coverage"] - 0.95), 0.01)
        eligible_widths = [
            item["summary"]["mean_95_interval_width_mw"]
            for item in calibration["models"].values()
        ]
        self.assertEqual(structured["mean_95_interval_width_mw"], min(eligible_widths))

    def test_lock_keeps_diagnostic_claims_cautious(self):
        self.assertTrue(LOCK["locked_before_final_test"])
        self.assertFalse(LOCK["final_test_opened"])
        self.assertFalse(LOCK["residual_independence_achieved"])
        self.assertFalse(LOCK["constant_conditional_variance_achieved"])
        self.assertFalse(
            LOCK["research_point_forecast"]["uses_neso_demand_forecast_as_input"]
        )

    def test_final_evaluation_uses_locked_period_without_retuning(self):
        evaluation = json.loads((MODEL_DIR / "final_test_evaluation.json").read_text())
        self.assertEqual(evaluation["date_range"], ["2026-01-01", "2026-03-31"])
        self.assertEqual(evaluation["n"], 4318)
        self.assertFalse(evaluation["model_changed_after_opening"])
        self.assertIn("adc6f74", evaluation["evaluation_status"])

    def test_final_v3_improves_v2_and_weekly_naive(self):
        evaluation = json.loads((MODEL_DIR / "final_test_evaluation.json").read_text())
        point = evaluation["point_metrics"]
        self.assertLess(
            point["v3_locked"]["mae_mw"], point["v2_locked_spec_refit"]["mae_mw"]
        )
        self.assertLess(
            point["v3_locked"]["mae_mw"], point["weekly_seasonal_naive"]["mae_mw"]
        )


if __name__ == "__main__":
    unittest.main()
