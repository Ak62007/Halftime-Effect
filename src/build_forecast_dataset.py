"""Build the leakage-safe dataset for the syllabus-aligned forecast."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
CONFIG = json.loads((ROOT / "configs/forecast_data_contract.json").read_text())
RAW_DEMAND = ROOT / "data/raw/neso/forecast_performance.csv"
RAW_HOLIDAYS = ROOT / "data/raw/calendar/bank_holidays.json"
RAW_EXOGENOUS = ROOT / "data/raw/forecast_exogenous"
OUT = ROOT / "data/processed/syllabus_aligned"
TZ = CONFIG["timezone"]


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def settlement_timeline(start: str, end_inclusive: str) -> pd.DataFrame:
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
        records, columns=["settlement_date", "settlement_period", "timestamp_utc"]
    )


def holiday_table() -> pd.DataFrame:
    raw = json.loads(RAW_HOLIDAYS.read_text())
    records = []
    for region in ["england-and-wales", "scotland"]:
        for event in raw[region]["events"]:
            if CONFIG["source_start_date"] <= event["date"] <= CONFIG[
                "final_test_end_inclusive"
            ]:
                records.append(
                    {"region": region, "date": event["date"], "title": event["title"]}
                )
    holidays = pd.DataFrame(records)
    require(not holidays.empty, "No holidays found")
    return holidays


def weather_table() -> pd.DataFrame:
    payload = json.loads(
        (RAW_EXOGENOUS / "weather/jma_temperature_previous_runs.json").read_text()
    )
    selected = CONFIG["weather"]["selected_lead"]
    parts = []
    for response in payload:
        name = response["requested_location_name"]
        parts.append(
            pd.DataFrame(
                {
                    "timestamp_utc": pd.to_datetime(response["hourly"]["time"], utc=True),
                    f"temperature_forecast_{name}_c": response["hourly"][selected],
                }
            ).set_index("timestamp_utc")
        )
    weather = pd.concat(parts, axis=1).sort_index()
    require(weather.index.is_unique, "Duplicate weather timestamps")
    require(weather.notna().all().all(), "Missing archived weather forecast")
    return weather


def embedded_at_cutoff() -> pd.DataFrame:
    paths = sorted((RAW_EXOGENOUS / "neso_embedded").glob("embedded_cutoff_candidates_*.csv"))
    require(len(paths) == 6, "Expected six annual embedded forecast files")
    frame = pd.concat((pd.read_csv(path) for path in paths), ignore_index=True)
    frame["settlement_date"] = pd.to_datetime(frame["SETTLEMENT_DATE"]).dt.strftime(
        "%Y-%m-%d"
    )
    frame["settlement_period"] = pd.to_numeric(
        frame["SETTLEMENT_PERIOD"], errors="raise"
    ).astype(int)
    frame["embedded_forecast_issue_utc"] = pd.to_datetime(
        frame["Forecast_Datetime"], utc=True
    )
    cutoff_clock = (
        pd.to_datetime(frame["settlement_date"])
        - pd.Timedelta(days=1)
        + pd.Timedelta(hours=CONFIG["forecast_issue_local_hour"])
    )
    frame["forecast_cutoff_utc"] = cutoff_clock.dt.tz_localize(TZ).dt.tz_convert(
        "UTC"
    )
    eligible = frame["embedded_forecast_issue_utc"].le(frame["forecast_cutoff_utc"])
    frame = frame.loc[eligible].sort_values("embedded_forecast_issue_utc")
    keys = ["settlement_date", "settlement_period"]
    frame = frame.drop_duplicates(keys, keep="last")
    rename = {
        "EMBEDDED_WIND_FORECAST": "embedded_wind_forecast_mw",
        "EMBEDDED_WIND_CAPACITY": "embedded_wind_capacity_mw",
        "EMBEDDED_SOLAR_FORECAST": "embedded_solar_forecast_mw",
        "EMBEDDED_SOLAR_CAPACITY": "embedded_solar_capacity_mw",
    }
    frame = frame.rename(columns=rename)
    keep = keys + list(rename.values()) + ["embedded_forecast_issue_utc"]
    for column in rename.values():
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    require(frame[list(rename.values())].notna().all().all(), "Invalid embedded values")
    return frame[keep]


def build() -> dict:
    OUT.mkdir(parents=True, exist_ok=True)
    grid = settlement_timeline(
        CONFIG["source_start_date"], CONFIG["final_test_end_inclusive"]
    )
    keys = ["settlement_date", "settlement_period"]
    excluded_source_dates = ["2021-10-31", "2022-10-30"]
    source = pd.read_csv(RAW_DEMAND)
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
    require(not source.duplicated(keys).any(), "Duplicate demand source keys")
    data = grid.merge(source, on=keys, how="left", validate="one_to_one", indicator=True)
    data["source_quality_eligible"] = ~data["settlement_date"].isin(
        excluded_source_dates
    )
    require(
        data.loc[data["source_quality_eligible"], "_merge"].eq("both").all(),
        "Missing eligible demand keys",
    )
    data = data.drop(columns="_merge")

    data["interval_end_utc"] = data["timestamp_utc"] + pd.Timedelta(minutes=30)
    data["timestamp_london"] = data["timestamp_utc"].dt.tz_convert(TZ)
    cutoff_clock = (
        pd.to_datetime(data["settlement_date"])
        - pd.Timedelta(days=1)
        + pd.Timedelta(hours=CONFIG["forecast_issue_local_hour"])
    )
    data["forecast_cutoff_utc"] = cutoff_clock.dt.tz_localize(TZ).dt.tz_convert("UTC")
    issue_clock = pd.to_datetime(data["Publish_Datetime"].str.removesuffix("Z"))
    data["neso_forecast_issue_utc"] = issue_clock.dt.tz_localize(
        TZ, ambiguous="NaT", nonexistent="NaT"
    ).dt.tz_convert("UTC")
    data["neso_available_at_cutoff"] = data["neso_forecast_issue_utc"].le(
        data["forecast_cutoff_utc"]
    )
    development_cutoff = data["settlement_date"].le(
        CONFIG["development_end_inclusive"]
    )
    require(
        data.loc[
            data["source_quality_eligible"] & development_cutoff,
            "neso_available_at_cutoff",
        ].all(),
        "A development-period NESO demand forecast misses the common cutoff",
    )

    local = data["timestamp_london"]
    data["local_day_of_week"] = local.dt.dayofweek
    data["local_half_hour"] = local.dt.hour * 2 + local.dt.minute // 30
    data["half_hour_of_week"] = data["local_day_of_week"] * 48 + data["local_half_hour"]
    data["local_day_of_year"] = local.dt.dayofyear
    data["is_saturday"] = data["local_day_of_week"].eq(5)
    data["is_sunday"] = data["local_day_of_week"].eq(6)

    holidays = holiday_table()
    region_dates = {
        region: set(holidays.loc[holidays["region"].eq(region), "date"])
        for region in ["england-and-wales", "scotland"]
    }
    data["is_bank_holiday_england_wales"] = data["settlement_date"].isin(
        region_dates["england-and-wales"]
    )
    data["is_bank_holiday_scotland"] = data["settlement_date"].isin(
        region_dates["scotland"]
    )
    data["is_bank_holiday_any_gb"] = (
        data["is_bank_holiday_england_wales"] | data["is_bank_holiday_scotland"]
    )
    ew_titles = (
        holidays.loc[holidays["region"].eq("england-and-wales")]
        .set_index("date")["title"]
        .to_dict()
    )
    data["bank_holiday_title_england_wales"] = data["settlement_date"].map(
        ew_titles
    ).fillna("none")
    dates = pd.to_datetime(data["settlement_date"])
    holiday_any = set().union(*region_dates.values())
    data["is_day_before_bank_holiday"] = (
        dates.add(pd.Timedelta(days=1)).dt.strftime("%Y-%m-%d").isin(holiday_any)
    )
    data["is_day_after_bank_holiday"] = (
        dates.sub(pd.Timedelta(days=1)).dt.strftime("%Y-%m-%d").isin(holiday_any)
    )
    data["is_christmas_eve"] = dates.dt.strftime("%m-%d").eq("12-24")
    data["is_new_years_eve"] = dates.dt.strftime("%m-%d").eq("12-31")
    data["is_january_second"] = dates.dt.strftime("%m-%d").eq("01-02")
    data["is_working_day"] = (
        data["local_day_of_week"].lt(5) & ~data["is_bank_holiday_any_gb"]
    )

    weather = weather_table()
    union = weather.index.union(pd.DatetimeIndex(data["timestamp_utc"]))
    weather_halfhour = (
        weather.reindex(union)
        .sort_index()
        .interpolate(method="time", limit_area="inside")
        .reindex(data["timestamp_utc"])
    )
    require(weather_halfhour.notna().all().all(), "Weather does not cover demand grid")
    for column in weather_halfhour:
        data[column] = weather_halfhour[column].to_numpy()
    temperature_columns = list(weather_halfhour.columns)
    data["temperature_forecast_gb_c"] = data[temperature_columns].mean(axis=1)
    data["heating_degree_forecast"] = np.maximum(
        15.5 - data["temperature_forecast_gb_c"], 0
    )
    data["cooling_degree_forecast"] = np.maximum(
        data["temperature_forecast_gb_c"] - 18.0, 0
    )
    data["weather_forecast_lead_hours"] = CONFIG["weather"][
        "selected_lead_hours"
    ]
    data["weather_ex_ante_eligible"] = True

    embedded = embedded_at_cutoff()
    data = data.merge(embedded, on=keys, how="left", validate="one_to_one")
    embedded_columns = [
        "embedded_wind_forecast_mw",
        "embedded_wind_capacity_mw",
        "embedded_solar_forecast_mw",
        "embedded_solar_capacity_mw",
    ]
    data["embedded_forecast_available_at_cutoff"] = data[
        "embedded_wind_forecast_mw"
    ].notna()
    data["embedded_forecast_imputed_from_week_lag"] = ~data[
        "embedded_forecast_available_at_cutoff"
    ]
    timestamp_week_ago = data["timestamp_utc"].shift(336)
    aligned_week_lag = data["timestamp_utc"].sub(timestamp_week_ago).eq(
        pd.Timedelta(days=7)
    )
    for column in embedded_columns:
        safe_week_lag = data[column].shift(336).where(aligned_week_lag)
        data[column] = data[column].fillna(safe_week_lag)
    require(
        data.loc[data["source_quality_eligible"], embedded_columns]
        .notna()
        .all()
        .all(),
        "Embedded forecast does not cover every eligible demand row",
    )
    require(
        data.loc[
            data["source_quality_eligible"]
            & data["embedded_forecast_available_at_cutoff"],
            "embedded_forecast_issue_utc",
        ]
        .le(
            data.loc[
                data["source_quality_eligible"]
                & data["embedded_forecast_available_at_cutoff"],
                "forecast_cutoff_utc",
            ]
        )
        .all(),
        "An embedded forecast was published after the cutoff",
    )
    data["embedded_wind_capacity_factor_forecast"] = (
        data["embedded_wind_forecast_mw"] / data["embedded_wind_capacity_mw"]
    )
    data["embedded_solar_capacity_factor_forecast"] = (
        data["embedded_solar_forecast_mw"] / data["embedded_solar_capacity_mw"]
    )

    prior_start, prior_end = CONFIG["previously_opened_period"]
    data["is_previously_opened_period"] = data["settlement_date"].between(
        prior_start, prior_end
    )
    data["is_final_test"] = data["settlement_date"].between(
        CONFIG["final_test_start"], CONFIG["final_test_end_inclusive"]
    )
    data["experiment_split"] = np.select(
        [data["is_final_test"], data["is_previously_opened_period"]],
        ["final_test_unopened", "development_previously_opened"],
        default="development",
    )
    data.to_csv(OUT / "demand_source.csv", index=False)

    daily_counts = data.groupby("settlement_date").size()
    audit = {
        "rows": int(len(data)),
        "local_dates": int(data["settlement_date"].nunique()),
        "date_range": [data["settlement_date"].min(), data["settlement_date"].max()],
        "final_test_rows_unopened": int(data["is_final_test"].sum()),
        "previously_opened_rows": int(data["is_previously_opened_period"].sum()),
        "source_quality_excluded_dates": excluded_source_dates,
        "weather_missing": int(data[temperature_columns].isna().sum().sum()),
        "embedded_missing_eligible": int(
            data.loc[data["source_quality_eligible"], embedded_columns]
            .isna()
            .sum()
            .sum()
        ),
        "embedded_week_lag_imputed_rows": int(
            data.loc[
                data["source_quality_eligible"],
                "embedded_forecast_imputed_from_week_lag",
            ].sum()
        ),
        "embedded_week_lag_imputed_dates": sorted(
            data.loc[
                data["source_quality_eligible"]
                & data["embedded_forecast_imputed_from_week_lag"],
                "settlement_date",
            ].unique().tolist()
        ),
        "embedded_after_cutoff_eligible": int(
            data.loc[
                data["source_quality_eligible"]
                & data["embedded_forecast_available_at_cutoff"],
                "embedded_forecast_issue_utc",
            ]
            .gt(
                data.loc[
                    data["source_quality_eligible"]
                    & data["embedded_forecast_available_at_cutoff"],
                    "forecast_cutoff_utc",
                ]
            )
            .sum()
        ),
        "neso_unavailable_at_cutoff_rows": int(
            data.loc[data["source_quality_eligible"], "neso_available_at_cutoff"]
            .eq(False)
            .sum()
        ),
        "neso_unavailable_at_cutoff_dates": sorted(
            data.loc[
                data["source_quality_eligible"]
                & ~data["neso_available_at_cutoff"],
                "settlement_date",
            ].unique().tolist()
        ),
        "local_day_row_count_frequency": {
            str(key): int(value)
            for key, value in daily_counts.value_counts().sort_index().items()
        },
        "selection_fold_names": [fold["name"] for fold in CONFIG["validation_folds"]],
        "previously_opened_period_used_as_validation": False,
        "final_test_opened_for_model_selection": False,
    }
    (OUT / "data_audit.json").write_text(json.dumps(audit, indent=2) + "\n")
    print(json.dumps(audit, indent=2))
    return audit


if __name__ == "__main__":
    build()
