import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data/processed/syllabus_aligned"


class SyllabusAlignedModelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.result = json.loads((OUT / "results.json").read_text())

    def test_only_approved_model_scope_is_declared(self):
        self.assertEqual(
            self.result["approved_model_scope"],
            [
                "weekly seasonal naive",
                "seasonal regression with Fourier terms and ARMA errors",
                "same seasonal model plus pre-scheduled match flags",
            ],
        )

    def test_fourier_regression_beats_weekly_naive(self):
        metrics = self.result["ordinary_validation"]["metrics"]
        self.assertLess(
            metrics["fourier_regression"]["mae_mw"],
            metrics["weekly_seasonal_naive"]["mae_mw"],
        )

    def test_arma_is_rejected_when_it_does_not_improve(self):
        validation = self.result["ordinary_validation"]
        metrics = validation["metrics"]
        self.assertGreater(
            metrics["fourier_regression_with_arma_errors"]["mae_mw"],
            metrics["fourier_regression"]["mae_mw"],
        )
        self.assertIn("ARMA(2,1) rejected", validation["selected_model"])

    def test_match_aware_extension_is_exploratory_and_worse(self):
        self.assertEqual(self.result["historical_match_flag_fit"]["historical_matches"], 5)
        scheduled = self.result["euro_2024"]["metrics"]["scheduled_match"]
        self.assertGreater(
            scheduled["exploratory_match_aware"]["mae_mw"],
            scheduled["event_blind_fourier_regression"]["mae_mw"],
        )

    def test_garch_is_not_forced_into_final_model(self):
        self.assertFalse(self.result["garch_fitted"])


if __name__ == "__main__":
    unittest.main()
