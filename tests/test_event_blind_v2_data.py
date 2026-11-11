"""Acceptance checks for the isolated event-blind v2 modelling table."""
import json
import unittest
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data/processed/event_blind_v2"


class EventBlindV2DataTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = pd.read_csv(DATA_DIR / "demand_v2.csv")
        cls.data["timestamp_utc"] = pd.to_datetime(cls.data["timestamp_utc"], utc=True)
        cls.audit = json.loads((DATA_DIR / "data_audit.json").read_text())

    def test_utc_grid_is_unique_and_consecutive(self):
        self.assertFalse(self.data["timestamp_utc"].duplicated().any())
        differences = self.data["timestamp_utc"].diff().dropna()
        self.assertTrue(differences.eq(pd.Timedelta(minutes=30)).all())

    def test_only_audited_source_dates_are_ineligible(self):
        excluded = self.data.loc[
            ~self.data["source_quality_eligible"], "settlement_date"
        ]
        self.assertEqual(set(excluded), {"2021-10-31", "2022-10-30"})
        self.assertEqual(len(excluded), 100)

    def test_final_test_is_complete_and_still_marked_unopened(self):
        final = self.data.loc[self.data["is_final_test"]]
        self.assertEqual(final["settlement_date"].min(), "2025-01-01")
        self.assertEqual(final["settlement_date"].max(), "2025-03-31")
        self.assertEqual(final["settlement_date"].nunique(), 90)
        self.assertTrue(final["demand_mw"].notna().all())
        self.assertFalse(self.audit["final_test_opened_for_model_selection"])

    def test_all_eligible_neso_forecasts_meet_common_cutoff(self):
        eligible = self.data.loc[self.data["source_quality_eligible"]]
        self.assertTrue(eligible["neso_available_at_cutoff"].all())


if __name__ == "__main__":
    unittest.main()
