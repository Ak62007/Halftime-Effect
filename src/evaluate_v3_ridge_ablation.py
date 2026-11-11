"""Rolling-origin feature ablation for event-blind v3 Ridge candidates."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import sparse
from scipy.sparse.linalg import lsqr


ROOT = Path(__file__).resolve().parents[1]
CONFIG = json.loads((ROOT / "configs/event_blind_v3_experiment.json").read_text())
DATA_DIR = ROOT / "data/processed/event_blind_v3"
OUT = DATA_DIR / "modeling"
OUT.mkdir(parents=True, exist_ok=True)


@dataclass(frozen=True)
class Candidate:
    name: str
    feature_family: str
    alpha: float
    recent_days: int


CANDIDATES = [
    Candidate("v2_ridge_reproduced", "v2", 0.1, 730),
    Candidate("v3_calendar", "calendar", 0.1, 730),
    Candidate("v3_weather", "weather", 0.1, 730),
    Candidate("v3_embedded", "embedded", 0.1, 730),
] + [
    Candidate(f"v3_full_recent730_a{alpha:g}", "full", alpha, 730)
    for alpha in [0.01, 0.1, 1.0]
] + [
    Candidate(f"v3_full_recent1095_a{alpha:g}", "full", alpha, 1_095)
    for alpha in [0.1, 1.0]
]


def load_development() -> pd.DataFrame:
    data = pd.read_csv(DATA_DIR / "demand_v3.csv")
    # This is the hard unopened boundary. No final outcome or metric survives load.
    data = data.loc[~data["is_final_test"]].copy()
    data["timestamp_utc"] = pd.to_datetime(data["timestamp_utc"], utc=True)
    data["timestamp_london"] = data["timestamp_utc"].dt.tz_convert(CONFIG["timezone"])
    data["interval_end_utc"] = pd.to_datetime(data["interval_end_utc"], utc=True)
    data["forecast_cutoff_utc"] = pd.to_datetime(data["forecast_cutoff_utc"], utc=True)
    data = data.sort_values("timestamp_utc").reset_index(drop=True)
    for lag in CONFIG["fixed_safe_lags_half_hours"]:
        shifted_time = data["timestamp_utc"].shift(lag)
        aligned = data["timestamp_utc"].sub(shifted_time).eq(
            pd.Timedelta(minutes=30 * lag)
        )
        data[f"lag_{lag}"] = data["demand_mw"].shift(lag).where(aligned)
    daily_lags = [96, 144, 192, 240, 288, 336]
    weekly_lags = [336, 672, 1008, 1344]
    data["safe_daily_mean"] = data[[f"lag_{x}" for x in daily_lags]].mean(
        axis=1, skipna=False
    )
    data["safe_daily_std"] = data[[f"lag_{x}" for x in daily_lags]].std(
        axis=1, skipna=False
    )
    data["weekly_mean_4"] = data[[f"lag_{x}" for x in weekly_lags]].mean(
        axis=1, skipna=False
    )
    data["weekly_std_4"] = data[[f"lag_{x}" for x in weekly_lags]].std(
        axis=1, skipna=False
    )
    data["daily_change_2_to_3"] = data["lag_96"] - data["lag_144"]
    data["weekly_change_1_to_2"] = data["lag_336"] - data["lag_672"]
    temperatures = [
        "temperature_forecast_london_c",
        "temperature_forecast_manchester_c",
        "temperature_forecast_birmingham_c",
    ]
    grouped = data.groupby("settlement_date")["temperature_forecast_gb_c"]
    data["forecast_temperature_daily_mean_c"] = grouped.transform("mean")
    data["forecast_temperature_daily_min_c"] = grouped.transform("min")
    data["forecast_temperature_daily_max_c"] = grouped.transform("max")
    daily_mean = data.groupby("settlement_date")["temperature_forecast_gb_c"].mean()
    prior_day_mean = daily_mean.shift(1)
    data["forecast_temperature_change_from_prior_day_c"] = data[
        "settlement_date"
    ].map(daily_mean - prior_day_mean)
    data["embedded_wind_change_week_mw"] = data["embedded_wind_forecast_mw"] - data[
        "embedded_wind_forecast_mw"
    ].shift(336)
    data["embedded_solar_change_week_mw"] = data["embedded_solar_forecast_mw"] - data[
        "embedded_solar_forecast_mw"
    ].shift(336)
    if data[temperatures].isna().any().any():
        raise ValueError("Development weather features are incomplete")
    return data


def annual_phase(data: pd.DataFrame) -> np.ndarray:
    local = data["timestamp_london"]
    fractional_day = local.dt.hour / 24 + local.dt.minute / (24 * 60)
    return 2 * np.pi * (local.dt.dayofyear - 1 + fractional_day).to_numpy() / 365.2425


def slot_weighted(values: np.ndarray, slots: np.ndarray, width: int) -> sparse.csr_matrix:
    rows = np.arange(len(values))
    return sparse.csr_matrix((values, (rows, slots)), shape=(len(values), width))


def design_matrix(data: pd.DataFrame, family: str) -> sparse.csr_matrix:
    n = len(data)
    rows = np.arange(n)
    weekly_slot = data["half_hour_of_week"].astype(int).to_numpy()
    local_slot = data["local_half_hour"].astype(int).to_numpy()
    slot = sparse.csr_matrix((np.ones(n), (rows, weekly_slot)), shape=(n, 336))
    phase = annual_phase(data)
    blocks: list[sparse.spmatrix] = [
        slot,
        slot_weighted(np.sin(phase), weekly_slot, 336),
        slot_weighted(np.cos(phase), weekly_slot, 336),
    ]
    origin = pd.Timestamp(CONFIG["source_start_date"], tz="UTC")
    trend_years = (
        data["timestamp_utc"].sub(origin).dt.total_seconds().to_numpy()
        / (365.2425 * 24 * 3600)
    )
    dense = [trend_years, data["is_bank_holiday_any_gb"].astype(float).to_numpy()]
    lag_columns = [f"lag_{lag}" for lag in CONFIG["fixed_safe_lags_half_hours"]]
    summary_columns = [
        "safe_daily_mean",
        "safe_daily_std",
        "weekly_mean_4",
        "weekly_std_4",
        "daily_change_2_to_3",
        "weekly_change_1_to_2",
    ]
    dense.extend(data[column].to_numpy(dtype=float) / 10_000 for column in lag_columns)
    dense.extend(
        data[column].to_numpy(dtype=float) / 10_000 for column in summary_columns
    )
    for harmonic in range(2, 7):
        dense.extend([np.sin(harmonic * phase), np.cos(harmonic * phase)])

    include_calendar = family in {"calendar", "full"}
    include_weather = family in {"weather", "full"}
    include_embedded = family in {"embedded", "full"}
    if family not in {"v2", "calendar", "weather", "embedded", "full"}:
        raise ValueError(f"Unknown feature family: {family}")

    if include_calendar:
        calendar_flags = [
            "is_bank_holiday_any_gb",
            "is_day_before_bank_holiday",
            "is_day_after_bank_holiday",
            "is_christmas_eve",
            "is_new_years_eve",
            "is_january_second",
        ]
        blocks.extend(
            slot_weighted(data[column].astype(float).to_numpy(), local_slot, 48)
            for column in calendar_flags
        )
        dense.extend(data[column].astype(float).to_numpy() for column in calendar_flags[1:])

    if include_weather:
        weather_columns = [
            "temperature_forecast_london_c",
            "temperature_forecast_manchester_c",
            "temperature_forecast_birmingham_c",
            "temperature_forecast_gb_c",
            "heating_degree_forecast",
            "cooling_degree_forecast",
            "forecast_temperature_daily_mean_c",
            "forecast_temperature_daily_min_c",
            "forecast_temperature_daily_max_c",
            "forecast_temperature_change_from_prior_day_c",
        ]
        dense.extend(data[column].to_numpy(dtype=float) / 20 for column in weather_columns)
        blocks.extend(
            [
                slot_weighted(
                    data["heating_degree_forecast"].to_numpy(dtype=float) / 20,
                    local_slot,
                    48,
                ),
                slot_weighted(
                    data["cooling_degree_forecast"].to_numpy(dtype=float) / 20,
                    local_slot,
                    48,
                ),
            ]
        )

    if include_embedded:
        embedded_columns = [
            "embedded_wind_forecast_mw",
            "embedded_solar_forecast_mw",
            "embedded_wind_capacity_mw",
            "embedded_solar_capacity_mw",
            "embedded_wind_change_week_mw",
            "embedded_solar_change_week_mw",
        ]
        dense.extend(data[column].to_numpy(dtype=float) / 10_000 for column in embedded_columns)
        dense.extend(
            [
                data["embedded_wind_capacity_factor_forecast"].to_numpy(dtype=float),
                data["embedded_solar_capacity_factor_forecast"].to_numpy(dtype=float),
                data["embedded_forecast_imputed_from_week_lag"].astype(float).to_numpy(),
            ]
        )

    blocks.append(sparse.csr_matrix(np.column_stack(dense)))
    return sparse.hstack(blocks, format="csr")


def required_available(data: pd.DataFrame) -> pd.Series:
    required = data["demand_mw"].notna() & data["source_quality_eligible"]
    for lag in CONFIG["fixed_safe_lags_half_hours"]:
        required &= data[f"lag_{lag}"].notna()
    required &= data["forecast_temperature_change_from_prior_day_c"].notna()
    required &= data["embedded_wind_change_week_mw"].notna()
    required &= data["embedded_solar_change_week_mw"].notna()
    return required


def fit_predict(
    training: pd.DataFrame, validation: pd.DataFrame, candidate: Candidate
) -> tuple[np.ndarray, dict]:
    x_train = design_matrix(training, candidate.feature_family)
    x_validation = design_matrix(validation, candidate.feature_family)
    target = training["demand_mw"].to_numpy(dtype=float) / 10_000
    solution = lsqr(
        x_train,
        target,
        damp=np.sqrt(candidate.alpha),
        atol=1e-8,
        btol=1e-8,
        iter_lim=5_000,
    )
    forecast = np.asarray(x_validation @ solution[0]).ravel() * 10_000
    return forecast, {
        "training_rows": int(len(training)),
        "features": int(x_train.shape[1]),
        "lsqr_stop_code": int(solution[1]),
        "lsqr_iterations": int(solution[2]),
    }


def metrics(actual: np.ndarray, forecast: np.ndarray) -> dict:
    error = actual - forecast
    return {
        "n": int(len(error)),
        "me_mw": float(np.mean(error)),
        "mae_mw": float(np.mean(np.abs(error))),
        "rmse_mw": float(np.sqrt(np.mean(error**2))),
    }


def summarize(folds: dict) -> dict:
    values = list(folds.values())
    return {
        "mean_fold_mae_mw": float(np.mean([x["mae_mw"] for x in values])),
        "mean_fold_rmse_mw": float(np.mean([x["rmse_mw"] for x in values])),
        "mean_fold_absolute_bias_mw": float(np.mean([abs(x["me_mw"]) for x in values])),
        "worst_fold_mae_mw": float(max(x["mae_mw"] for x in values)),
    }


def main() -> None:
    data = load_development()
    available = required_available(data)
    results = {
        "selection_scope": "seven rolling-origin folds; Jan-Mar 2025 not scored",
        "selection_metric": CONFIG["selection_metric"],
        "final_test_opened": False,
        "previously_opened_period_used_as_validation": False,
        "candidates": {},
        "benchmarks": {},
    }
    output_parts = []
    for fold in CONFIG["validation_folds"]:
        fold_name = fold["name"]
        validate = data["settlement_date"].between(
            fold["validation_start"], fold["validation_end_inclusive"]
        ) & available
        validation = data.loc[validate].copy()
        if validation.empty:
            raise ValueError(f"Empty validation fold: {fold_name}")
        actual = validation["demand_mw"].to_numpy(dtype=float)
        results["benchmarks"].setdefault("weekly_seasonal_naive", {})[fold_name] = metrics(
            actual, validation["lag_336"].to_numpy(dtype=float)
        )
        neso = validation["neso_available_at_cutoff"].to_numpy(dtype=bool)
        results["benchmarks"].setdefault("neso_day_ahead", {})[fold_name] = metrics(
            actual[neso], validation.loc[neso, "neso_day_ahead_forecast_mw"].to_numpy()
        )
        fold_output = validation[
            ["timestamp_utc", "settlement_date", "demand_mw", "lag_336"]
        ].copy()
        fold_output["fold"] = fold_name
        for candidate in CANDIDATES:
            training_end = pd.Timestamp(fold["train_end_inclusive"])
            training_start = max(
                pd.Timestamp(CONFIG["source_start_date"]),
                training_end - pd.Timedelta(days=candidate.recent_days - 1),
            )
            train = data["settlement_date"].between(
                training_start.strftime("%Y-%m-%d"), fold["train_end_inclusive"]
            ) & available
            training = data.loc[train].copy()
            forecast, metadata = fit_predict(training, validation, candidate)
            result = metrics(actual, forecast)
            results["candidates"].setdefault(
                candidate.name,
                {
                    "feature_family": candidate.feature_family,
                    "alpha": candidate.alpha,
                    "recent_days": candidate.recent_days,
                    "folds": {},
                },
            )["folds"][fold_name] = {**metadata, **result}
            fold_output[f"forecast_{candidate.name}_mw"] = forecast
        output_parts.append(fold_output)

    for name, folds in results["benchmarks"].items():
        results["benchmarks"][name] = {"folds": folds, "summary": summarize(folds)}
    for item in results["candidates"].values():
        item["summary"] = summarize(item["folds"])
    selected = min(
        results["candidates"],
        key=lambda name: results["candidates"][name]["summary"]["mean_fold_mae_mw"],
    )
    results["best_ridge_candidate"] = selected
    (OUT / "ridge_ablation_metrics.json").write_text(json.dumps(results, indent=2) + "\n")
    pd.concat(output_parts, ignore_index=True).to_csv(
        OUT / "ridge_ablation_predictions.csv", index=False
    )
    print(
        json.dumps(
            {
                "benchmarks": {
                    name: item["summary"] for name, item in results["benchmarks"].items()
                },
                "candidates": {
                    name: item["summary"] for name, item in results["candidates"].items()
                },
                "best_ridge_candidate": selected,
                "final_test_opened": False,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
