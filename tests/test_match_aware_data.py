"""Integrity tests for the isolated extended match-aware artifacts."""
import unittest
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data/processed/match_aware"


class MatchAwareArtifactTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = pd.read_csv(OUT / "demand_extended.csv")
        cls.fixtures = pd.read_csv(OUT / "fixtures_extended.csv")

    def test_complete_utc_grid_and_explicit_source_exclusions(self):
        data = self.data
        timestamps = pd.to_datetime(data["timestamp_utc"], utc=True)
        self.assertTrue(timestamps.is_unique)
        self.assertTrue(
            timestamps.diff().dropna().eq(pd.Timedelta(minutes=30)).all()
        )
        excluded = data.loc[~data["source_quality_eligible"]]
        self.assertEqual(
            set(excluded["settlement_date"]), {"2021-10-31", "2022-10-30"}
        )
        self.assertEqual(len(excluded), 100)
        self.assertTrue(excluded["demand_mw"].isna().all())
        self.assertFalse(
            data.loc[data["source_quality_eligible"], "demand_mw"].isna().any()
        )
        self.assertFalse(data["historic_nd_mw"].isna().any())

    def test_fixture_roles_and_protected_holdout(self):
        counts = self.fixtures["event_role"].value_counts().to_dict()
        self.assertEqual(counts["historical_sensitivity_event"], 16)
        self.assertEqual(counts["historical_primary_train"], 23)
        self.assertEqual(counts["validation_event"], 2)
        self.assertEqual(counts["bridge_only"], 2)
        self.assertEqual(counts["event_holdout"], 7)
        development = pd.read_csv(OUT / "demand_modeling.csv")
        self.assertEqual(development["settlement_date"].max(), "2024-05-31")
        self.assertNotIn("event_holdout", set(development["data_split"]))

    def test_baseline_fit_rows_exclude_events_and_source_failures(self):
        eligible = self.data.loc[self.data["baseline_fit_eligible"]]
        self.assertTrue(eligible["data_split"].eq("train").all())
        self.assertTrue(eligible["source_quality_eligible"].all())
        self.assertFalse(eligible["is_england_match_day"].any())

    def test_scheduled_event_overlap_features_are_bounded_and_complete(self):
        fraction_columns = [
            "pregame_overlap_fraction",
            "scheduled_match_overlap_fraction",
            "halftime_proxy_overlap_fraction",
            "postmatch_overlap_fraction",
        ]
        for column in fraction_columns:
            self.assertTrue(self.data[column].between(0, 1).all())
            self.assertTrue(
                self.data.loc[~self.data["is_england_match_day"], column]
                .eq(0)
                .all()
            )

        event_rows = self.data.loc[self.data["is_england_match_day"]]
        totals = event_rows.groupby("match_id")[fraction_columns].sum()
        expected = {
            "pregame_overlap_fraction": 4.0,
            "scheduled_match_overlap_fraction": 3.5,
            "halftime_proxy_overlap_fraction": 1.0,
            "postmatch_overlap_fraction": 2.0,
        }
        for column, value in expected.items():
            self.assertTrue(np.allclose(totals[column], value))


if __name__ == "__main__":
    unittest.main()
