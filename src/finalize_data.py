"""Acquire/rebuild the bounded NESO analysis dataset; no statistical modelling.

Run from any directory: .venv/bin/python src/finalize_data.py
Use --download to acquire missing raw inputs, or --refresh to replace snapshots.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data/raw"
OUT = ROOT / "data/processed"
CONFIG = json.loads((ROOT / "configs/data_contract.json").read_text())
TZ = CONFIG["timezone"]


def require(condition, message):
    if not condition:
        raise ValueError(message)


def acquire(refresh=False):
    for relative, url in CONFIG["sources"].items():
        dest = RAW / relative
        if dest.exists() and not refresh:
            continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        response = requests.get(url, timeout=(15, 120))
        response.raise_for_status()
        temporary = dest.with_suffix(dest.suffix + ".part")
        temporary.write_bytes(response.content)
        temporary.replace(dest)


def settlement_timeline(start, end_exclusive):
    """SP1 starts at London midnight; increment in elapsed UTC half-hours."""
    records = []
    for day in pd.date_range(start, end_exclusive, inclusive="left", freq="D"):
        begin = day.tz_localize(TZ).tz_convert("UTC")
        end = (day + pd.Timedelta(days=1)).tz_localize(TZ).tz_convert("UTC")
        times = pd.date_range(begin, end, freq="30min", inclusive="left")
        records.extend((day.strftime("%Y-%m-%d"), sp, t)
                       for sp, t in enumerate(times, 1))
    return pd.DataFrame(records, columns=["settlement_date", "settlement_period", "timestamp_utc"])


def holiday_calendar():
    raw = json.loads((RAW / "calendar/bank_holidays.json").read_text())
    records = [dict(region=region, date=e["date"], title=e["title"])
               for region in ["england-and-wales", "scotland"]
               for e in raw[region]["events"] if e["date"][:4] in ["2023", "2024"]]
    return pd.DataFrame(records)


def fixtures():
    earlier = pd.read_csv(ROOT / "data/england_fixtures_pre_euro_2024.csv")
    earlier["event_role"] = np.where(earlier.match_date_london <= CONFIG["train_end_inclusive"],
                                      "historical_train_candidate", "validation_event")
    earlier["match_stage"] = "pre_tournament"
    summer = pd.read_csv(ROOT / "data/england_fixtures_summer_2024.csv")
    cols = ["match_id", "match_date_london", "opponent", "scheduled_kickoff_utc",
            "scheduled_kickoff_london", "match_stage", "event_role", "timing_source_url"]
    result = pd.concat([earlier[cols], summer[cols]], ignore_index=True)
    require(not result.match_id.duplicated().any(), "Duplicate fixture identifiers")
    utc = pd.to_datetime(result.scheduled_kickoff_utc, utc=True)
    require(utc.dt.tz_convert(TZ).dt.strftime("%Y-%m-%d").eq(result.match_date_london).all(),
            "Fixture local dates do not match kickoffs")
    require(pd.to_datetime(result.scheduled_kickoff_london, utc=True).eq(utc).all(),
            "Fixture timezone conversions disagree")
    return result


def temperatures():
    raw = json.loads((RAW / "weather/era5_temperature.json").read_text())
    require(isinstance(raw, list) and len(raw) == 3, "Expected three weather locations")
    parts = []
    for name, item in zip(["london", "manchester", "birmingham"], raw):
        require(item["utc_offset_seconds"] == 0, "Weather offset must be UTC")
        require(item["hourly_units"]["temperature_2m"] == "°C", "Weather units changed")
        series = pd.Series(item["hourly"]["temperature_2m"],
                           index=pd.to_datetime(item["hourly"]["time"], utc=True),
                           name=f"temperature_{name}_c_retrospective")
        require(series.index.is_unique and not series.isna().any(), "Invalid weather timeline")
        require(series.index.to_series().diff().dropna().eq(pd.Timedelta(hours=1)).all(),
                "Weather hourly gaps")
        parts.append(series)
    return pd.concat(parts, axis=1)


def build():
    OUT.mkdir(parents=True, exist_ok=True)
    end_exclusive = (pd.Timestamp(CONFIG["end_date_inclusive"]) + pd.Timedelta(days=1)).strftime("%Y-%m-%d")
    grid = settlement_timeline(CONFIG["start_date"], end_exclusive)
    keys = ["settlement_date", "settlement_period"]
    f = pd.read_csv(RAW / "neso/forecast_performance.csv")
    f = f.loc[f.Date.between(CONFIG["start_date"], CONFIG["end_date_inclusive"])].copy()
    f = f.rename(columns={"Date": "settlement_date", "Settlement_Period": "settlement_period",
                          "Demand_Outturn": "demand_mw", "Demand_Forecast": "neso_day_ahead_forecast_mw"})
    require(not f.duplicated(keys).any(), "Duplicate forecast settlement keys")
    require(len(f) == len(grid), "Primary source row count differs from complete grid")
    d = grid.merge(f, on=keys, how="left", validate="one_to_one", indicator=True)
    require(d["_merge"].eq("both").all(), "Missing primary settlement keys")
    d = d.drop(columns="_merge")
    d["interval_end_utc"] = d.timestamp_utc + pd.Timedelta(minutes=30)
    d["timestamp_london"] = d.timestamp_utc.dt.tz_convert(TZ)
    # NESO documents London clock values despite literal Z suffixes.
    # Verify every supplied label against the SP-derived interval END clock.
    expected_end_clock = d.interval_end_utc.dt.tz_convert(TZ).dt.tz_localize(None)
    supplied_end_clock = pd.to_datetime(d.Datetime.str.removesuffix("Z"))
    require(supplied_end_clock.eq(expected_end_clock).all(), "Source datetime/end-label mismatch")
    issue_clock = pd.to_datetime(d.Publish_Datetime.str.removesuffix("Z"))
    d["forecast_issue_utc"] = issue_clock.dt.tz_localize(TZ, ambiguous="NaT", nonexistent="NaT").dt.tz_convert("UTC")
    require(d.forecast_issue_utc.notna().all(), "Ambiguous/nonexistent forecast issue time")
    require(d.forecast_issue_utc.lt(d.timestamp_utc).all(), "Forecast issued after target start")
    # Common experiment cutoff: 10:00 London on the preceding local day.
    cutoff_clock = pd.to_datetime(d.settlement_date) - pd.Timedelta(days=1) + pd.Timedelta(hours=CONFIG["forecast_issue_local_hour"])
    d["forecast_cutoff_utc"] = cutoff_clock.dt.tz_localize(TZ).dt.tz_convert("UTC")
    d["neso_available_at_cutoff"] = d.forecast_issue_utc.le(d.forecast_cutoff_utc)
    require(d.neso_available_at_cutoff.all(), "Some operator forecasts miss the chosen cutoff")

    hist = []
    for year, fmt in [(2023, "%d-%b-%y"), (2024, "%d-%b-%Y")]:
        h = pd.read_csv(RAW / f"neso/historic_{year}.csv")
        h["settlement_date"] = pd.to_datetime(h.SETTLEMENT_DATE, format=fmt).dt.strftime("%Y-%m-%d")
        h = h.rename(columns={"SETTLEMENT_PERIOD": "settlement_period", "ND": "historic_nd_mw", "TSD": "historic_tsd_mw"})
        hist.append(h[keys + ["historic_nd_mw", "historic_tsd_mw"]])
    hist = pd.concat(hist, ignore_index=True)
    d = d.merge(hist, on=keys, how="left", validate="one_to_one")
    numeric = ["demand_mw", "neso_day_ahead_forecast_mw", "historic_nd_mw", "historic_tsd_mw"]
    require(all(pd.api.types.is_numeric_dtype(d[c]) for c in numeric), "Non-numeric demand")
    require(d[numeric].notna().all().all(), "Null demand/forecast/cross-check values")
    require(d[numeric].gt(0).all().all(), "Nonpositive demand/forecast")
    require(d.timestamp_utc.is_unique, "Duplicate UTC timestamps")
    require(d.timestamp_utc.diff().dropna().eq(pd.Timedelta(minutes=30)).all(), "UTC grid gaps")

    holidays = holiday_calendar()
    for region, name in [("england-and-wales", "is_bank_holiday_england_wales"), ("scotland", "is_bank_holiday_scotland")]:
        d[name] = d.settlement_date.isin(holidays.loc[holidays.region.eq(region), "date"])
    d["is_bank_holiday_any_gb"] = d.is_bank_holiday_england_wales | d.is_bank_holiday_scotland
    d["hour_of_week"] = d.timestamp_london.dt.dayofweek * 24 + d.timestamp_london.dt.hour
    d["half_hour_of_week"] = d.hour_of_week * 2 + d.timestamp_london.dt.minute // 30
    d["data_split"] = np.select([
        d.settlement_date.le(CONFIG["train_end_inclusive"]),
        d.settlement_date.le(CONFIG["validation_end_inclusive"]),
        d.settlement_date.lt(CONFIG["event_holdout_start"]),
        d.settlement_date.le(CONFIG["event_holdout_end_inclusive"])],
        ["train", "validation", "bridge", "event_holdout"], default="post_event_context")
    fx = fixtures()
    d = d.merge(fx[["match_id", "match_date_london", "opponent", "scheduled_kickoff_utc", "match_stage", "event_role"]],
                left_on="settlement_date", right_on="match_date_london", how="left", validate="many_to_one").drop(columns="match_date_london")
    d["is_england_match_day"] = d.match_id.notna()
    # Conservative whole-day exclusion for the initial event-blind baseline.
    d["baseline_fit_eligible"] = d.data_split.eq("train") & ~d.is_england_match_day

    weather = temperatures()
    union = weather.index.union(pd.DatetimeIndex(d.timestamp_utc))
    aligned = weather.reindex(union).sort_index().interpolate(method="time", limit_area="inside").reindex(d.timestamp_utc)
    require(aligned.notna().all().all(), "Uncovered weather timestamps")
    for col in aligned.columns:
        d[col] = aligned[col].to_numpy()
    d["temperature_proxy_c_retrospective"] = aligned.mean(axis=1).to_numpy()
    d["weather_ex_ante_eligible"] = False

    # Keep only explicit, documented fields; retain raw source clocks for audit.
    keep = ["timestamp_utc", "interval_end_utc", "timestamp_london"] + keys + numeric + [
        "forecast_issue_utc", "forecast_cutoff_utc", "neso_available_at_cutoff",
        "Datetime", "Publish_Datetime", "TRIAD_Avoidance_Estimate",
        "hour_of_week", "half_hour_of_week", "is_bank_holiday_england_wales",
        "is_bank_holiday_scotland", "is_bank_holiday_any_gb", "data_split",
        "baseline_fit_eligible", "is_england_match_day", "match_id", "opponent",
        "scheduled_kickoff_utc", "match_stage", "event_role"] + aligned.columns.tolist() + [
        "temperature_proxy_c_retrospective", "weather_ex_ante_eligible"]
    d = d[keep]
    d.to_csv(OUT / "demand_halfhour.csv", index=False)
    d.loc[d.data_split.isin(["train", "validation"])].to_csv(OUT / "demand_development.csv", index=False)
    weather.to_csv(OUT / "weather_hourly_retrospective.csv", index_label="timestamp_utc")
    holidays.to_csv(OUT / "bank_holidays.csv", index=False)
    fx.to_csv(OUT / "fixtures_all.csv", index=False)
    daily = d.groupby("settlement_date").agg(rows=("timestamp_utc", "size"), demand_nulls=("demand_mw", lambda x: x.isna().sum()))
    daily.to_csv(OUT / "daily_coverage.csv")
    fixture_audit = d.loc[d.is_england_match_day].groupby(["match_id", "settlement_date", "event_role"]).agg(
        rows=("timestamp_utc", "size"), demand_nulls=("demand_mw", lambda x: x.isna().sum())).reset_index()
    require(len(fixture_audit) == 21, "Missing fixture-day demand coverage")
    require(fixture_audit.event_role.eq("event_holdout").sum() == 7, "Expected seven holdout matches")
    fixture_audit.to_csv(OUT / "final_fixture_coverage.csv", index=False)
    delta = d.demand_mw - d.historic_nd_mw
    audit = {
        "rows": len(d), "local_dates": len(daily), "missing_intervals": 0, "duplicate_utc_timestamps": 0,
        "null_primary_demand": int(d.demand_mw.isna().sum()), "source_end_labels_match_all_rows": True,
        "forecast_issues_before_interval_start": True, "all_operator_forecasts_available_at_10am_cutoff": True,
        "local_daily_row_counts": {str(k): int(v) for k, v in daily.rows.value_counts().sort_index().items()},
        "split_counts": {str(k): int(v) for k, v in d.data_split.value_counts().items()},
        "baseline_fit_eligible_rows": int(d.baseline_fit_eligible.sum()),
        "fixture_days": len(fixture_audit), "euro_holdout_matches": 7,
        "historic_nd_comparison": {"identical_rows": int(delta.eq(0).sum()), "mean_absolute_difference_mw": float(delta.abs().mean()), "max_absolute_difference_mw": int(delta.abs().max())},
        "weather_missing_after_alignment": int(d[aligned.columns].isna().sum().sum()),
        "forecast_target": "Demand_Outturn only; historic ND is a separate sensitivity target",
    }
    (OUT / "final_data_checks.json").write_text(json.dumps(audit, indent=2) + "\n")
    manifest = {"built_at_utc": datetime.now(timezone.utc).isoformat(), "contract": CONFIG, "raw_files": []}
    for relative, url in CONFIG["sources"].items():
        p = RAW / relative
        manifest["raw_files"].append({"path": str(p.relative_to(ROOT)), "source_url": url,
                                       "bytes": p.stat().st_size, "sha256": hashlib.sha256(p.read_bytes()).hexdigest()})
    manifest["output_sha256"] = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
                                  for p in sorted(OUT.glob("*.csv")) if p.name in ["demand_halfhour.csv", "demand_development.csv", "fixtures_all.csv", "bank_holidays.csv", "weather_hourly_retrospective.csv", "daily_coverage.csv", "final_fixture_coverage.csv"]}
    (OUT / "data_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps(audit, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--download", action="store_true")
    parser.add_argument("--refresh", action="store_true")
    args = parser.parse_args()
    if args.download or args.refresh:
        acquire(refresh=args.refresh)
    build()
