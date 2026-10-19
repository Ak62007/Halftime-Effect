"""Checks for the time alignment and forecast boundaries that can invalidate results."""
import unittest
from pathlib import Path
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.finalize_data import settlement_timeline


class SettlementAlignmentTests(unittest.TestCase):
    def test_spring_day_has_46_intervals_and_no_utc_gap(self):
        d = settlement_timeline("2024-03-31", "2024-04-01")
        self.assertEqual(len(d), 46)
        self.assertEqual(str(d.timestamp_utc.iloc[-1]), "2024-03-31 22:30:00+00:00")
        self.assertTrue(d.timestamp_utc.diff().dropna().eq(pd.Timedelta(minutes=30)).all())

    def test_autumn_repeated_clock_labels_are_distinct_instants(self):
        d = settlement_timeline("2023-10-29", "2023-10-30")
        self.assertEqual(len(d), 50)
        local = d.timestamp_utc.dt.tz_convert("Europe/London")
        self.assertTrue(d.timestamp_utc.is_unique)
        self.assertEqual(local.dt.strftime("%H:%M").eq("01:00").sum(), 2)
        self.assertEqual(d.settlement_period.tolist(), list(range(1, 51)))


class FinalArtifactTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.d = pd.read_csv(ROOT / "data/processed/demand_halfhour.csv")

    def test_full_grid_and_local_dates(self):
        d = self.d
        utc = pd.to_datetime(d.timestamp_utc, utc=True)
        self.assertTrue(utc.is_unique)
        self.assertTrue(utc.diff().dropna().eq(pd.Timedelta(minutes=30)).all())
        self.assertTrue(utc.dt.tz_convert("Europe/London").dt.strftime("%Y-%m-%d").eq(d.settlement_date).all())
        end = utc + pd.Timedelta(minutes=30)
        source = pd.to_datetime(d.Datetime.str.removesuffix("Z"))
        self.assertTrue(end.dt.tz_convert("Europe/London").dt.tz_localize(None).eq(source).all())

    def test_operator_forecast_available_at_common_cutoff(self):
        d = self.d
        issued = pd.to_datetime(d.forecast_issue_utc, utc=True)
        cutoff = pd.to_datetime(d.forecast_cutoff_utc, utc=True)
        target = pd.to_datetime(d.timestamp_utc, utc=True)
        self.assertTrue(issued.le(cutoff).all())
        self.assertTrue(cutoff.lt(target).all())
        local_cutoff = cutoff.dt.tz_convert("Europe/London")
        self.assertTrue(local_cutoff.dt.hour.eq(10).all())
        self.assertTrue(local_cutoff.dt.tz_localize(None).dt.normalize().eq(
            pd.to_datetime(d.settlement_date) - pd.Timedelta(days=1)).all())

    def test_development_does_not_include_tournament(self):
        dev = pd.read_csv(ROOT / "data/processed/demand_development.csv")
        self.assertEqual(dev.settlement_date.max(), "2024-05-31")
        self.assertEqual(set(dev.data_split), {"train", "validation"})
        eligible = self.d.loc[self.d.baseline_fit_eligible]
        self.assertTrue(eligible.data_split.eq("train").all())
        self.assertFalse(eligible.is_england_match_day.any())

    def test_primary_target_is_not_silently_replaced_with_nd(self):
        self.assertFalse(self.d.demand_mw.eq(self.d.historic_nd_mw).all())
        self.assertFalse(self.d.weather_ex_ante_eligible.any())
        self.assertFalse(self.d.demand_mw.isna().any())


if __name__ == "__main__":
    unittest.main()
