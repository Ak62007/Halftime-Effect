"""Build the isolated extended dataset used by the match-aware forecast.

This pipeline does not overwrite the finalized core artifacts in ``data/processed``.
It writes only to ``data/processed/match_aware``.

Run from any directory::

    .venv/bin/python src/build_match_aware_data.py --download
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
OUT = ROOT / "data/processed/match_aware"
CONFIG_PATH = ROOT / "configs/match_aware_data_contract.json"
CONFIG = json.loads(CONFIG_PATH.read_text())
TZ = CONFIG["timezone"]
DATASTORE_API = "https://api.neso.energy/api/3/action/datastore_search"


def require(condition, message):
    if not condition:
        raise ValueError(message)


def _download_file(url: str, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    response = requests.get(url, timeout=(15, 180))
    response.raise_for_status()
    temporary = destination.with_suffix(destination.suffix + ".part")
    temporary.write_bytes(response.content)
    temporary.replace(destination)


def _download_datastore(resource_id: str, destination: Path) -> None:
    """Download a complete CKAN datastore resource without using its redirect."""
    records: list[dict] = []
    offset = 0
    limit = 5_000
    while True:
        response = requests.get(
            DATASTORE_API,
            params={"resource_id": resource_id, "limit": limit, "offset": offset},
            timeout=(15, 180),
        )
        response.raise_for_status()
        payload = response.json()
        require(payload.get("success"), f"Datastore request failed for {resource_id}")
        result = payload["result"]
        page = result["records"]
        records.extend(page)
        offset += len(page)
        if not page or offset >= result["total"]:
            break
    require(records, f"Datastore resource {resource_id} returned no rows")
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + ".part")
    pd.DataFrame.from_records(records).drop(columns="_id", errors="ignore").to_csv(
        temporary, index=False
    )
    temporary.replace(destination)


def acquire(refresh: bool = False) -> None:
    for relative, url in CONFIG["sources"].items():
        destination = RAW / relative
        if destination.exists() and not refresh:
            continue
        _download_file(url, destination)
    for relative, resource_id in CONFIG["datastore_sources"].items():
        destination = RAW / relative
        if destination.exists() and not refresh:
            continue
        _download_datastore(resource_id, destination)


def settlement_timeline(start: str, end_exclusive: str) -> pd.DataFrame:
    """Build settlement periods from London midnights on an elapsed UTC grid."""
    records = []
    for day in pd.date_range(start, end_exclusive, inclusive="left", freq="D"):
        begin = day.tz_localize(TZ).tz_convert("UTC")
        end = (day + pd.Timedelta(days=1)).tz_localize(TZ).tz_convert("UTC")
        times = pd.date_range(begin, end, freq="30min", inclusive="left")
        records.extend(
            (day.strftime("%Y-%m-%d"), settlement_period, timestamp)
            for settlement_period, timestamp in enumerate(times, 1)
        )
    return pd.DataFrame(
        records,
        columns=["settlement_date", "settlement_period", "timestamp_utc"],
    )


def holiday_calendar() -> pd.DataFrame:
    raw = json.loads((RAW / "calendar/bank_holidays.json").read_text())
    records = [
        {"region": region, "date": event["date"], "title": event["title"]}
        for region in ["england-and-wales", "scotland"]
        for event in raw[region]["events"]
        if CONFIG["start_date"] <= event["date"] <= CONFIG["end_date_inclusive"]
    ]
    holidays = pd.DataFrame(records)
    require(not holidays.empty, "No bank holidays cover the extended period")
    return holidays


def fixture_inventory() -> pd.DataFrame:
    historical_2021_2022 = pd.read_csv(ROOT / "data/england_fixtures_2021_2022.csv")
    historical_2023_2024 = pd.read_csv(ROOT / "data/england_fixtures_pre_euro_2024.csv")
    historical = pd.concat(
        [historical_2021_2022, historical_2023_2024], ignore_index=True
    )
    dates = pd.to_datetime(historical["match_date_london"])
    historical["event_role"] = np.select(
        [
            dates.lt(CONFIG["primary_match_training_start"]),
            dates.le(CONFIG["train_end_inclusive"]),
        ],
        ["historical_sensitivity_event", "historical_primary_train"],
        default="validation_event",
    )
    historical["match_stage"] = historical["competition"]

    summer = pd.read_csv(ROOT / "data/england_fixtures_summer_2024.csv")
    summer["england_home_away"] = np.where(
        summer["opponent"].isin(["Bosnia and Herzegovina", "Iceland"]),
        "home",
        "neutral",
    )
    summer["competition"] = np.where(
        summer["event_role"].eq("event_holdout"),
        "UEFA EURO 2024",
        "International friendly",
    )

    columns = [
        "match_id",
        "match_date_london",
        "opponent",
        "england_home_away",
        "competition",
        "scheduled_kickoff_utc",
        "scheduled_kickoff_london",
        "match_stage",
        "event_role",
        "timing_source_url",
        "timing_status",
    ]
    fixtures = pd.concat([historical[columns], summer[columns]], ignore_index=True)
    require(not fixtures["match_id"].duplicated().any(), "Duplicate fixture identifiers")

    kickoff_utc = pd.to_datetime(fixtures["scheduled_kickoff_utc"], utc=True)
    kickoff_london = pd.to_datetime(fixtures["scheduled_kickoff_london"], utc=True)
    require(kickoff_london.eq(kickoff_utc).all(), "Fixture timezone conversions disagree")
    require(
        kickoff_utc.dt.tz_convert(TZ)
        .dt.strftime("%Y-%m-%d")
        .eq(fixtures["match_date_london"])
        .all(),
        "Fixture local dates do not match kickoffs",
    )

    competition = fixtures["competition"].str.lower()
    fixtures["is_tournament_match"] = (
        competition.str.contains("uefa euro|fifa world cup", regex=True)
        & ~competition.str.contains("qualif", regex=False)
    )
    fixtures["is_primary_match_training_candidate"] = fixtures["event_role"].eq(
        "historical_primary_train"
    )
    fixtures["is_sensitivity_match_training_candidate"] = fixtures[
        "event_role"
    ].isin(["historical_primary_train", "historical_sensitivity_event"])

    role_counts = fixtures["event_role"].value_counts().to_dict()
    require(role_counts.get("historical_sensitivity_event") == 16, "Expected 16 2021 events")
    require(role_counts.get("historical_primary_train") == 23, "Expected 23 primary training events")
    require(role_counts.get("validation_event") == 2, "Expected two validation events")
    require(role_counts.get("bridge_only") == 2, "Expected two bridge events")
    require(role_counts.get("event_holdout") == 7, "Expected seven Euro holdout events")
    return fixtures


def temperatures() -> pd.DataFrame:
    path = RAW / "weather/era5_temperature_20210331_2025.json"
    raw = json.loads(path.read_text())
    require(isinstance(raw, list) and len(raw) == 3, "Expected three weather locations")
    parts = []
    for name, item in zip(["london", "manchester", "birmingham"], raw):
        require(item["utc_offset_seconds"] == 0, "Weather offset must be UTC")
        require(item["hourly_units"]["temperature_2m"] == "°C", "Weather units changed")
        series = pd.Series(
            item["hourly"]["temperature_2m"],
            index=pd.to_datetime(item["hourly"]["time"], utc=True),
            name=f"temperature_{name}_c_retrospective",
        )
        require(series.index.is_unique and not series.isna().any(), "Invalid weather timeline")
        require(
            series.index.to_series()
            .diff()
            .dropna()
            .eq(pd.Timedelta(hours=1))
            .all(),
            "Weather hourly gaps",
        )
        parts.append(series)
    return pd.concat(parts, axis=1)


def _event_overlap_fraction(relative_start_minutes: pd.Series, start: int, end: int) -> pd.Series:
    relative_end_minutes = relative_start_minutes + 30
    overlap = np.minimum(relative_end_minutes, end) - np.maximum(relative_start_minutes, start)
    return pd.Series(np.clip(overlap, 0, 30) / 30, index=relative_start_minutes.index)


def build() -> dict:
    OUT.mkdir(parents=True, exist_ok=True)
    end_exclusive = (
        pd.Timestamp(CONFIG["end_date_inclusive"]) + pd.Timedelta(days=1)
    ).strftime("%Y-%m-%d")
    grid = settlement_timeline(CONFIG["start_date"], end_exclusive)
    keys = ["settlement_date", "settlement_period"]

    # The source mishandles the repeated local hour on these two autumn DST days:
    # 2021 contains conflicting duplicate forecasts and 2022 is two rows short.
    # Preserve the complete grid, but do not manufacture a primary target.
    excluded_source_dates = ["2021-10-31", "2022-10-30"]
    forecast = pd.read_csv(RAW / "neso/forecast_performance.csv")
    forecast = forecast.loc[
        forecast["Date"].between(CONFIG["start_date"], CONFIG["end_date_inclusive"])
    ].copy()
    forecast = forecast.rename(
        columns={
            "Date": "settlement_date",
            "Settlement_Period": "settlement_period",
            "Demand_Outturn": "demand_mw",
            "Demand_Forecast": "neso_day_ahead_forecast_mw",
        }
    )
    forecast = forecast.loc[~forecast["settlement_date"].isin(excluded_source_dates)].copy()
    require(not forecast.duplicated(keys).any(), "Duplicate forecast settlement keys outside excluded dates")
    expected_eligible_rows = int(
        (~grid["settlement_date"].isin(excluded_source_dates)).sum()
    )
    require(
        len(forecast) == expected_eligible_rows,
        "Primary source row count differs from the eligible complete grid",
    )
    data = grid.merge(
        forecast, on=keys, how="left", validate="one_to_one", indicator=True
    )
    data["source_quality_eligible"] = ~data["settlement_date"].isin(
        excluded_source_dates
    )
    require(
        data.loc[data["source_quality_eligible"], "_merge"].eq("both").all(),
        "Missing eligible primary settlement keys",
    )
    require(
        data.loc[~data["source_quality_eligible"], "_merge"].eq("left_only").all(),
        "Excluded source dates unexpectedly merged",
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
        "Source datetime/end-label mismatch",
    )

    issue_clock = pd.to_datetime(data["Publish_Datetime"].str.removesuffix("Z"))
    data["forecast_issue_utc"] = (
        issue_clock.dt.tz_localize(TZ, ambiguous="NaT", nonexistent="NaT").dt.tz_convert("UTC")
    )
    require(
        data.loc[data["source_quality_eligible"], "forecast_issue_utc"].notna().all(),
        "Invalid eligible forecast issue time",
    )
    require(
        data.loc[data["source_quality_eligible"], "forecast_issue_utc"]
        .lt(data.loc[data["source_quality_eligible"], "timestamp_utc"])
        .all(),
        "Forecast issued after target start",
    )
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
        data.loc[data["source_quality_eligible"], "neso_available_at_cutoff"].all(),
        "Some NESO forecasts miss the common 10:00 cutoff",
    )

    historical_parts = []
    for year in [2021, 2022, 2023, 2024]:
        historical = pd.read_csv(RAW / f"neso/historic_{year}.csv")
        historical["settlement_date"] = pd.to_datetime(
            historical["SETTLEMENT_DATE"], format="mixed", dayfirst=True
        ).dt.strftime("%Y-%m-%d")
        historical = historical.rename(
            columns={
                "SETTLEMENT_PERIOD": "settlement_period",
                "ND": "historic_nd_mw",
                "TSD": "historic_tsd_mw",
            }
        )
        historical_parts.append(
            historical[keys + ["historic_nd_mw", "historic_tsd_mw"]]
        )
    historical = pd.concat(historical_parts, ignore_index=True)
    require(not historical.duplicated(keys).any(), "Duplicate historic demand keys")
    data = data.merge(historical, on=keys, how="left", validate="one_to_one")

    numeric = ["demand_mw", "neso_day_ahead_forecast_mw", "historic_nd_mw", "historic_tsd_mw"]
    require(all(pd.api.types.is_numeric_dtype(data[column]) for column in numeric), "Non-numeric demand")
    require(
        data.loc[data["source_quality_eligible"], numeric].notna().all().all(),
        "Null eligible demand/forecast/cross-check values",
    )
    require(
        data[["historic_nd_mw", "historic_tsd_mw"]].notna().all().all(),
        "Historic cross-check contains nulls",
    )
    require(
        data.loc[data["source_quality_eligible"], numeric].gt(0).all().all(),
        "Nonpositive eligible demand/forecast",
    )
    require(data["timestamp_utc"].is_unique, "Duplicate UTC timestamps")
    require(
        data["timestamp_utc"]
        .diff()
        .dropna()
        .eq(pd.Timedelta(minutes=30))
        .all(),
        "UTC grid gaps",
    )

    holidays = holiday_calendar()
    for region, name in [
        ("england-and-wales", "is_bank_holiday_england_wales"),
        ("scotland", "is_bank_holiday_scotland"),
    ]:
        data[name] = data["settlement_date"].isin(
            holidays.loc[holidays["region"].eq(region), "date"]
        )
    data["is_bank_holiday_any_gb"] = (
        data["is_bank_holiday_england_wales"] | data["is_bank_holiday_scotland"]
    )
    data["hour_of_week"] = (
        data["timestamp_london"].dt.dayofweek * 24 + data["timestamp_london"].dt.hour
    )
    data["half_hour_of_week"] = (
        data["hour_of_week"] * 2 + data["timestamp_london"].dt.minute // 30
    )
    data["data_split"] = np.select(
        [
            data["settlement_date"].le(CONFIG["train_end_inclusive"]),
            data["settlement_date"].le(CONFIG["validation_end_inclusive"]),
            data["settlement_date"].lt(CONFIG["event_holdout_start"]),
            data["settlement_date"].le(CONFIG["event_holdout_end_inclusive"]),
        ],
        ["train", "validation", "bridge", "event_holdout"],
        default="post_event_context",
    )

    fixtures = fixture_inventory()
    fixture_columns = [
        "match_id",
        "match_date_london",
        "opponent",
        "england_home_away",
        "competition",
        "scheduled_kickoff_utc",
        "match_stage",
        "event_role",
        "is_tournament_match",
        "is_primary_match_training_candidate",
        "is_sensitivity_match_training_candidate",
    ]
    data = data.merge(
        fixtures[fixture_columns],
        left_on="settlement_date",
        right_on="match_date_london",
        how="left",
        validate="many_to_one",
    ).drop(columns="match_date_london")
    data["is_england_match_day"] = data["match_id"].notna()
    data["baseline_fit_eligible"] = (
        data["data_split"].eq("train")
        & data["source_quality_eligible"]
        & ~data["is_england_match_day"]
    )

    kickoff = pd.to_datetime(data["scheduled_kickoff_utc"], utc=True)
    data["minutes_from_scheduled_kickoff"] = (
        data["timestamp_utc"] - kickoff
    ).dt.total_seconds() / 60
    for window_name, (start, end) in CONFIG["event_windows_minutes"].items():
        fraction = _event_overlap_fraction(
            data["minutes_from_scheduled_kickoff"], start, end
        )
        data[f"{window_name}_overlap_fraction"] = fraction.fillna(0.0)
        require(
            data[f"{window_name}_overlap_fraction"].between(0, 1).all(),
            f"Invalid {window_name} overlap fractions",
        )

    weather = temperatures()
    union = weather.index.union(pd.DatetimeIndex(data["timestamp_utc"]))
    aligned = (
        weather.reindex(union)
        .sort_index()
        .interpolate(method="time", limit_area="inside")
        .reindex(data["timestamp_utc"])
    )
    require(aligned.notna().all().all(), "Uncovered weather timestamps")
    for column in aligned.columns:
        data[column] = aligned[column].to_numpy()
    data["temperature_proxy_c_retrospective"] = aligned.mean(axis=1).to_numpy()
    data["weather_ex_ante_eligible"] = False

    fixture_audit = (
        data.loc[data["is_england_match_day"]]
        .groupby(["match_id", "settlement_date", "event_role"], observed=True)
        .agg(
            rows=("timestamp_utc", "size"),
            demand_nulls=("demand_mw", lambda values: values.isna().sum()),
        )
        .reset_index()
    )
    require(len(fixture_audit) == 50, "Expected coverage for 50 fixture days")
    require(fixture_audit["demand_nulls"].eq(0).all(), "Fixture demand coverage contains nulls")

    data.to_csv(OUT / "demand_extended.csv", index=False)
    data.loc[data["data_split"].isin(["train", "validation"])].to_csv(
        OUT / "demand_modeling.csv", index=False
    )
    fixtures.to_csv(OUT / "fixtures_extended.csv", index=False)
    fixture_audit.to_csv(OUT / "fixture_coverage.csv", index=False)
    holidays.to_csv(OUT / "bank_holidays.csv", index=False)

    daily = data.groupby("settlement_date", observed=True).agg(
        rows=("timestamp_utc", "size"),
        demand_nulls=("demand_mw", lambda values: values.isna().sum()),
    )
    daily.to_csv(OUT / "daily_coverage.csv")
    demand_delta = data["demand_mw"] - data["historic_nd_mw"]
    audit = {
        "rows": int(len(data)),
        "local_dates": int(len(daily)),
        "date_range": [data["settlement_date"].min(), data["settlement_date"].max()],
        "missing_intervals": int((~data["source_quality_eligible"]).sum()),
        "duplicate_utc_timestamps": 0,
        "null_primary_demand": int(data["demand_mw"].isna().sum()),
        "source_quality_excluded_dates": excluded_source_dates,
        "local_daily_row_counts": {
            str(key): int(value)
            for key, value in daily["rows"].value_counts().sort_index().items()
        },
        "split_counts": {
            str(key): int(value) for key, value in data["data_split"].value_counts().items()
        },
        "fixture_role_counts": {
            str(key): int(value)
            for key, value in fixture_audit["event_role"].value_counts().items()
        },
        "baseline_fit_eligible_rows": int(data["baseline_fit_eligible"].sum()),
        "fixture_days": int(len(fixture_audit)),
        "historic_nd_comparison": {
            "identical_rows": int(demand_delta.eq(0).sum()),
            "mean_absolute_difference_mw": float(demand_delta.abs().mean()),
            "max_absolute_difference_mw": int(demand_delta.abs().max()),
        },
        "weather_missing_after_alignment": int(aligned.isna().sum().sum()),
        "euro_holdout_opened_for_model_selection": False,
    }
    (OUT / "data_checks.json").write_text(json.dumps(audit, indent=2) + "\n")

    manifest = {
        "built_at_utc": datetime.now(timezone.utc).isoformat(),
        "contract": CONFIG,
        "raw_files": [],
    }
    source_items = dict(CONFIG["sources"])
    source_items.update(
        {
            path: f"{DATASTORE_API}?resource_id={resource_id}"
            for path, resource_id in CONFIG["datastore_sources"].items()
        }
    )
    for relative, source_url in source_items.items():
        path = RAW / relative
        manifest["raw_files"].append(
            {
                "path": str(path.relative_to(ROOT)),
                "source_url": source_url,
                "bytes": path.stat().st_size,
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            }
        )
    output_names = [
        "demand_extended.csv",
        "demand_modeling.csv",
        "fixtures_extended.csv",
        "fixture_coverage.csv",
        "daily_coverage.csv",
        "data_checks.json",
    ]
    manifest["output_sha256"] = {
        str((OUT / name).relative_to(ROOT)): hashlib.sha256((OUT / name).read_bytes()).hexdigest()
        for name in output_names
    }
    (OUT / "data_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return audit


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--download", action="store_true")
    parser.add_argument("--refresh", action="store_true")
    arguments = parser.parse_args()
    if arguments.download or arguments.refresh:
        acquire(refresh=arguments.refresh)
    print(json.dumps(build(), indent=2))
