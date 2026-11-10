"""Fit and validate event-blind day-ahead demand models.

Only ordinary March--May 2024 validation rows are scored. Historical validation
matches and the Euro holdout are deliberately excluded from selection.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import sparse
from scipy.sparse.linalg import lsqr


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data/processed/match_aware"
OUT = DATA_DIR / "modeling"
OUT.mkdir(parents=True, exist_ok=True)


@dataclass(frozen=True)
class ModelSpec:
    name: str
    fit_start: str
    weekly_lags: tuple[int, ...]


MODEL_SPECS = [
    ModelSpec("calendar_seasonal", "2021-04-01", ()),
    ModelSpec("calendar_plus_weekly_lag_full", "2021-04-01", (336,)),
    ModelSpec("calendar_plus_weekly_lag_recent", "2022-01-01", (336,)),
]


def load_data() -> pd.DataFrame:
    data = pd.read_csv(DATA_DIR / "demand_extended.csv")
    data["timestamp_utc"] = pd.to_datetime(data["timestamp_utc"], utc=True)
    data["timestamp_london"] = data["timestamp_utc"].dt.tz_convert("Europe/London")
    data = data.sort_values("timestamp_utc").reset_index(drop=True)
    for lag in [336, 672]:
        data[f"demand_lag_{lag}"] = data["demand_mw"].shift(lag)
        data[f"timestamp_lag_{lag}"] = data["timestamp_utc"].shift(lag)
        expected_delta = pd.Timedelta(minutes=30 * lag)
        aligned = data["timestamp_utc"].sub(data[f"timestamp_lag_{lag}"]).eq(expected_delta)
        data.loc[~aligned, f"demand_lag_{lag}"] = np.nan
    return data


def _annual_phase(data: pd.DataFrame) -> np.ndarray:
    local = data["timestamp_london"]
    fractional_day = local.dt.hour / 24 + local.dt.minute / (24 * 60)
    fractional_year_day = local.dt.dayofyear - 1 + fractional_day
    return 2 * np.pi * fractional_year_day.to_numpy() / 365.2425


def design_matrix(data: pd.DataFrame, spec: ModelSpec) -> sparse.csr_matrix:
    """Sparse seasonal regression design with local half-hour-of-week effects."""
    row_count = len(data)
    row_index = np.arange(row_count)
    slots = data["half_hour_of_week"].astype(int).to_numpy()
    require_slots = (slots >= 0) & (slots < 336)
    if not require_slots.all():
        raise ValueError("Invalid half-hour-of-week values")

    slot_matrix = sparse.csr_matrix(
        (np.ones(row_count), (row_index, slots)), shape=(row_count, 336)
    )
    phase = _annual_phase(data)
    seasonal_sine = sparse.csr_matrix(
        (np.sin(phase), (row_index, slots)), shape=(row_count, 336)
    )
    seasonal_cosine = sparse.csr_matrix(
        (np.cos(phase), (row_index, slots)), shape=(row_count, 336)
    )

    origin = pd.Timestamp("2021-04-01", tz="UTC")
    trend_years = (
        data["timestamp_utc"].sub(origin).dt.total_seconds().to_numpy()
        / (365.2425 * 24 * 3600)
    )
    holiday = data["is_bank_holiday_any_gb"].astype(float).to_numpy()
    dense_columns = [trend_years, holiday]
    for lag in spec.weekly_lags:
        dense_columns.append(data[f"demand_lag_{lag}"].to_numpy() / 10_000)
    dense_matrix = sparse.csr_matrix(np.column_stack(dense_columns))
    return sparse.hstack(
        [slot_matrix, seasonal_sine, seasonal_cosine, dense_matrix], format="csr"
    )


def required_columns_available(data: pd.DataFrame, spec: ModelSpec) -> pd.Series:
    available = data["demand_mw"].notna()
    for lag in spec.weekly_lags:
        available &= data[f"demand_lag_{lag}"].notna()
    return available


def fit_coefficients(data: pd.DataFrame, mask: pd.Series, spec: ModelSpec):
    training = data.loc[mask].copy()
    matrix = design_matrix(training, spec)
    target = training["demand_mw"].to_numpy(dtype=float)
    solution = lsqr(matrix, target, atol=1e-8, btol=1e-8, iter_lim=5_000)
    coefficients = solution[0]
    metadata = {
        "training_rows": int(len(training)),
        "features": int(matrix.shape[1]),
        "lsqr_stop_code": int(solution[1]),
        "lsqr_iterations": int(solution[2]),
        "training_residual_norm": float(solution[3]),
    }
    return coefficients, metadata


def predict(data: pd.DataFrame, coefficients: np.ndarray, spec: ModelSpec) -> np.ndarray:
    return np.asarray(design_matrix(data, spec) @ coefficients).ravel()


def metrics(actual: pd.Series, forecast: pd.Series) -> dict:
    error = actual.to_numpy(dtype=float) - forecast.to_numpy(dtype=float)
    return {
        "n": int(len(error)),
        "me_mw": float(error.mean()),
        "mae_mw": float(np.abs(error).mean()),
        "rmse_mw": float(np.sqrt(np.mean(error**2))),
    }


def main() -> None:
    data = load_data()
    ordinary_validation = (
        data["data_split"].eq("validation")
        & ~data["is_england_match_day"]
        & data["source_quality_eligible"]
    )
    scored = data.loc[ordinary_validation].copy()
    scored["weekly_naive_mw"] = scored["demand_lag_336"]

    results = {
        "selection_rule": "lowest MAE on ordinary March-May 2024 validation rows",
        "validation_matches_excluded": True,
        "euro_holdout_opened": False,
        "benchmarks": {
            "weekly_seasonal_naive": metrics(
                scored["demand_mw"], scored["weekly_naive_mw"]
            ),
            "neso_day_ahead": metrics(
                scored["demand_mw"], scored["neso_day_ahead_forecast_mw"]
            ),
        },
        "candidates": {},
    }

    coefficient_directory = OUT / "coefficients"
    coefficient_directory.mkdir(exist_ok=True)
    for spec in MODEL_SPECS:
        training_mask = (
            data["baseline_fit_eligible"]
            & data["settlement_date"].ge(spec.fit_start)
            & required_columns_available(data, spec)
        )
        validation_available = required_columns_available(scored, spec)
        if not validation_available.all():
            raise ValueError(f"Validation features missing for {spec.name}")
        coefficients, fit_metadata = fit_coefficients(data, training_mask, spec)
        scored[f"forecast_{spec.name}_mw"] = predict(scored, coefficients, spec)
        candidate_metrics = metrics(
            scored["demand_mw"], scored[f"forecast_{spec.name}_mw"]
        )
        results["candidates"][spec.name] = {
            "fit_start": spec.fit_start,
            "weekly_lags": list(spec.weekly_lags),
            **fit_metadata,
            **candidate_metrics,
        }
        np.save(coefficient_directory / f"{spec.name}.npy", coefficients)

    selected_name = min(
        results["candidates"],
        key=lambda name: results["candidates"][name]["mae_mw"],
    )
    results["selected_model"] = selected_name
    selected_column = f"forecast_{selected_name}_mw"
    scored["selected_event_blind_forecast_mw"] = scored[selected_column]
    scored["selected_event_blind_error_mw"] = (
        scored["demand_mw"] - scored["selected_event_blind_forecast_mw"]
    )

    output_columns = [
        "timestamp_utc",
        "timestamp_london",
        "settlement_date",
        "demand_mw",
        "weekly_naive_mw",
        "neso_day_ahead_forecast_mw",
    ] + [f"forecast_{spec.name}_mw" for spec in MODEL_SPECS] + [
        "selected_event_blind_forecast_mw",
        "selected_event_blind_error_mw",
    ]
    scored[output_columns].to_csv(OUT / "ordinary_validation_predictions.csv", index=False)
    (OUT / "event_blind_metrics.json").write_text(json.dumps(results, indent=2) + "\n")
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
