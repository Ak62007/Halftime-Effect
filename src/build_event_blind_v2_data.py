"""Build the isolated dataset for the event-blind v2 experiment.

The source file is the already-audited NESO Day Ahead Half Hourly Demand
Forecast Performance download. This builder does not overwrite the earlier core or
match-aware artifacts.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "configs/event_blind_v2_experiment.json"
CONFIG = json.loads(CONFIG_PATH.read_text())
RAW_FORECAST = ROOT / "data/raw/neso/forecast_performance.csv"
RAW_HOLIDAYS = ROOT / "data/raw/calendar/bank_holidays.json"
OUT = ROOT / "data/processed/event_blind_v2"
TZ = CONFIG["timezone"]


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def settlement_timeline(start: str, end_inclusive: str) -> pd.DataFrame:
    """Construct an elapsed UTC grid between London calendar midnights."""
    end_exclusive = pd.Timestamp(end_inclusive) + pd.Timedelta(days=1)
    records = []
    for day in pd.date_range(start, end_exclusive, inclusive="left", freq="D"):
        begin = day.tz_localize(TZ).tz_convert("UTC")
        end = (day + pd.Timedelta(days=1)).tz_localize(TZ).tz_convert("UTC")
        timestamps = pd.date_range(begin, end, freq="30min", inclusive="left")
        records.extend(
            (day.strftime("%Y-%m-%d"), period, timestamp)
            for period, timestamp in enumerate(timestamps, 1)
        )
    return pd.DataFrame(
        records,
        columns=["settlement_date", "settlement_period", "timestamp_utc"],
    )


def holiday_dates() -> dict[str, set[str]]:
    raw = json.loads(RAW_HOLIDAYS.read_text())
    return {
        region: {
            event["date"]
            for event in raw[region]["events"]
            if CONFIG["source_start_date"]
            <= event["date"]
            <= CONFIG["final_test_end_inclusive"]
        }
        for region in ["england-and-wales", "scotland"]
    }


def build() -> dict:
    OUT.mkdir(parents=True, exist_ok=True)
    grid = settlement_timeline(
        CONFIG["source_start_date"], CONFIG["final_test_end_inclusive"]
    )
    keys = ["settlement_date", "settlement_period"]

    # These two defects were established in the preceding data audit. They are
    # outside every v2 validation/test fold but remain explicit on the full grid.
    excluded_source_dates = ["2021-10-31", "2022-10-30"]
    source = pd.read_csv(RAW_FORECAST)
    source = source.loc[
        source["Date"].between(
            CONFIG["source_start_date"], CONFIG["final_test_end_inclusive"]
        )
    ].copy()
    source = source.rename(
        columns={
            "Date": "settlement_date",
            "Settlement_Period": "settlement_period",
            "Demand_Outturn": "demand_mw",
            "Demand_Forecast": "neso_day_ahead_forecast_mw",
        }
    )
    source = source.loc[~source["settlement_date"].isin(excluded_source_dates)]
    require(not source.duplicated(keys).any(), "Duplicate eligible source keys")

    data = grid.merge(source, on=keys, how="left", validate="one_to_one", indicator=True)
    data["source_quality_eligible"] = ~data["settlement_date"].isin(
        excluded_source_dates
    )
    require(
        data.loc[data["source_quality_eligible"], "_merge"].eq("both").all(),
        "Missing eligible settlement keys",
    )
    require(
        data.loc[~data["source_quality_eligible"], "_merge"].eq("left_only").all(),
        "Excluded dates unexpectedly merged",
    )
    data = data.drop(columns="_merge")

    data["interval_end_utc"] = data["timestamp_utc"] + pd.Timedelta(minutes=30)
    data["timestamp_london"] = data["timestamp_utc"].dt.tz_convert(TZ)
    expected_end_clock = data["interval_end_utc"].dt.tz_convert(TZ).dt.tz_localize(None)
    supplied_end_clock = pd.to_datetime(data["Datetime"].str.removesuffix("Z"))
    require(
        supplied_end_clock.loc[data["source_quality_eligible"]]
        .eq(expected_end_clock.loc[data["source_quality_eligible"]])
        .all(),
        "Source interval-end clock labels do not match the settlement grid",
    )

    issue_clock = pd.to_datetime(data["Publish_Datetime"].str.removesuffix("Z"))
    data["forecast_issue_utc"] = issue_clock.dt.tz_localize(
        TZ, ambiguous="NaT", nonexistent="NaT"
    ).dt.tz_convert("UTC")
    cutoff_clock = (
        pd.to_datetime(data["settlement_date"])
        - pd.Timedelta(days=1)
        + pd.Timedelta(hours=CONFIG["forecast_issue_local_hour"])
    )
    data["forecast_cutoff_utc"] = cutoff_clock.dt.tz_localize(TZ).dt.tz_convert("UTC")
    data["neso_available_at_cutoff"] = data["forecast_issue_utc"].le(
        data["forecast_cutoff_utc"]
    )
    require(
        data.loc[data["source_quality_eligible"], "forecast_issue_utc"].notna().all(),
        "Eligible source has an invalid issue timestamp",
    )
    require(
        data.loc[data["source_quality_eligible"], "neso_available_at_cutoff"].all(),
        "Some NESO forecasts were unavailable at the common cutoff",
    )

    numeric = ["demand_mw", "neso_day_ahead_forecast_mw"]
    require(
        data.loc[data["source_quality_eligible"], numeric].notna().all().all(),
        "Eligible demand or forecast values are missing",
    )
    require(
        data.loc[data["source_quality_eligible"], numeric].gt(0).all().all(),
        "Eligible demand or forecast values are nonpositive",
    )
    require(data["timestamp_utc"].is_unique, "UTC timestamps are not unique")
    require(
        data["timestamp_utc"]
        .diff()
        .dropna()
        .eq(pd.Timedelta(minutes=30))
        .all(),
        "UTC timeline contains a gap",
    )

    local = data["timestamp_london"]
    data["local_day_of_week"] = local.dt.dayofweek
    data["local_half_hour"] = local.dt.hour * 2 + local.dt.minute // 30
    data["half_hour_of_week"] = (
        data["local_day_of_week"] * 48 + data["local_half_hour"]
    )
    data["local_day_of_year"] = local.dt.dayofyear
    holidays = holiday_dates()
    data["is_bank_holiday_england_wales"] = data["settlement_date"].isin(
        holidays["england-and-wales"]
    )
    data["is_bank_holiday_scotland"] = data["settlement_date"].isin(
        holidays["scotland"]
    )
    data["is_bank_holiday_any_gb"] = (
        data["is_bank_holiday_england_wales"]
        | data["is_bank_holiday_scotland"]
    )
    data["is_final_test"] = data["settlement_date"].between(
        CONFIG["final_test_start"], CONFIG["final_test_end_inclusive"]
    )
    data["experiment_split"] = np.where(
        data["is_final_test"], "final_test_unopened", "development"
    )

    data.to_csv(OUT / "demand_v2.csv", index=False)
    daily_counts = data.groupby("settlement_date").size()
    audit = {
        "rows": int(len(data)),
        "local_dates": int(data["settlement_date"].nunique()),
        "date_range": [data["settlement_date"].min(), data["settlement_date"].max()],
        "development_rows": int(data["experiment_split"].eq("development").sum()),
        "final_test_rows_unopened": int(data["is_final_test"].sum()),
        "source_quality_excluded_dates": excluded_source_dates,
        "source_quality_excluded_rows": int((~data["source_quality_eligible"]).sum()),
        "duplicate_utc_timestamps": int(data["timestamp_utc"].duplicated().sum()),
        "eligible_null_targets": int(
            data.loc[data["source_quality_eligible"], "demand_mw"].isna().sum()
        ),
        "local_day_row_count_frequency": {
            str(key): int(value)
            for key, value in daily_counts.value_counts().sort_index().items()
        },
        "final_test_opened_for_model_selection": False,
        "euro_2024_used_for_v2_selection": False,
    }
    (OUT / "data_audit.json").write_text(json.dumps(audit, indent=2) + "\n")
    print(json.dumps(audit, indent=2))
    return audit


if __name__ == "__main__":
    build()
