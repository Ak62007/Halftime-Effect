import json
import unittest
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
CONFIG = json.loads((ROOT / "configs/event_blind_v3_experiment.json").read_text())
DATA_DIR = ROOT / "data/processed/event_blind_v3"


class EventBlindV3DataTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = pd.read_csv(DATA_DIR / "demand_v3.csv")
        cls.audit = json.loads((DATA_DIR / "data_audit.json").read_text())

    def test_final_test_is_complete_and_marked_unopened(self):
        final = self.data.loc[self.data["is_final_test"]]
        self.assertEqual(final["settlement_date"].min(), "2026-01-01")
        self.assertEqual(final["settlement_date"].max(), "2026-03-31")
        self.assertEqual(len(final), 4318)
        self.assertTrue(final["experiment_split"].eq("final_test_unopened").all())
        self.assertFalse(self.audit["final_test_opened_for_model_selection"])

    def test_weather_is_complete_and_ex_ante(self):
        columns = [column for column in self.data if column.startswith("temperature_forecast_")]
        self.assertGreaterEqual(len(columns), 4)
        self.assertFalse(self.data[columns].isna().any().any())
        self.assertTrue(self.data["weather_ex_ante_eligible"].all())
        self.assertTrue(self.data["weather_forecast_lead_hours"].eq(48).all())

    def test_embedded_forecasts_are_complete_and_cutoff_safe(self):
        columns = [
            "embedded_wind_forecast_mw",
            "embedded_solar_forecast_mw",
            "embedded_wind_capacity_mw",
            "embedded_solar_capacity_mw",
        ]
        eligible = self.data["source_quality_eligible"]
        self.assertFalse(self.data.loc[eligible, columns].isna().any().any())
        issued = self.data.loc[
            eligible & self.data["embedded_forecast_available_at_cutoff"]
        ].copy()
        self.assertTrue(
            (
                pd.to_datetime(issued["embedded_forecast_issue_utc"], utc=True)
                <= pd.to_datetime(issued["forecast_cutoff_utc"], utc=True)
            ).all()
        )
        self.assertEqual(self.audit["embedded_after_cutoff_eligible"], 0)

    def test_previously_opened_period_is_not_a_validation_fold(self):
        prior_start, prior_end = CONFIG["previously_opened_period"]
        for fold in CONFIG["validation_folds"]:
            self.assertFalse(
                fold["validation_start"] <= prior_end
                and fold["validation_end_inclusive"] >= prior_start
            )
        self.assertFalse(self.audit["previously_opened_period_used_as_validation"])

    def test_dst_day_counts_remain_correct(self):
        self.assertEqual(
            self.audit["local_day_row_count_frequency"],
            {"46": 5, "48": 1816, "50": 5},
        )


if __name__ == "__main__":
    unittest.main()
