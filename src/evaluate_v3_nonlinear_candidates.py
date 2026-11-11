"""Evaluate fixed-spline Ridge and nonlinear residual corrections for v3."""
from __future__ import annotations

import json

import numpy as np
import pandas as pd
from scipy import sparse
from scipy.sparse.linalg import lsqr
from sklearn.ensemble import HistGradientBoostingRegressor

from evaluate_v3_ridge_ablation import (
    CONFIG,
    OUT,
    Candidate,
    design_matrix,
    fit_predict,
    load_development,
    metrics,
    required_available,
    summarize,
)


BASE = Candidate("v3_full_recent730_a1", "full", 1.0, 730)
SPLINE_KNOTS_C = [-5.0, 0.0, 5.0, 10.0, 15.0, 20.0, 25.0]
SPLINE_ALPHAS = [0.1, 1.0, 10.0]
HGB_CANDIDATES = {
    "hgb_residual_l2_shallow": {
        "loss": "squared_error",
        "learning_rate": 0.05,
        "max_iter": 300,
        "max_leaf_nodes": 15,
        "min_samples_leaf": 100,
        "l2_regularization": 10.0,
    },
    "hgb_residual_l2_medium": {
        "loss": "squared_error",
        "learning_rate": 0.05,
        "max_iter": 300,
        "max_leaf_nodes": 31,
        "min_samples_leaf": 100,
        "l2_regularization": 10.0,
    },
    "hgb_residual_l1_medium": {
        "loss": "absolute_error",
        "learning_rate": 0.05,
        "max_iter": 300,
        "max_leaf_nodes": 31,
        "min_samples_leaf": 100,
        "l2_regularization": 10.0,
    },
}


def spline_design(data: pd.DataFrame) -> sparse.csr_matrix:
    base = design_matrix(data, "full")
    temperature = data["temperature_forecast_gb_c"].to_numpy(dtype=float)
    daily_mean = data["forecast_temperature_daily_mean_c"].to_numpy(dtype=float)
    hinges = []
    for values in [temperature, daily_mean]:
        hinges.extend(np.maximum(values - knot, 0) / 20 for knot in SPLINE_KNOTS_C)
    return sparse.hstack([base, sparse.csr_matrix(np.column_stack(hinges))], format="csr")


def fit_spline(
    training: pd.DataFrame, validation: pd.DataFrame, alpha: float
) -> tuple[np.ndarray, dict]:
    x_train = spline_design(training)
    x_validation = spline_design(validation)
    target = training["demand_mw"].to_numpy(dtype=float) / 10_000
    solution = lsqr(
        x_train,
        target,
        damp=np.sqrt(alpha),
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


def compact_nonlinear_design(data: pd.DataFrame, base_forecast: np.ndarray) -> np.ndarray:
    local = data["timestamp_london"]
    local_slot = local.dt.hour.to_numpy() * 2 + local.dt.minute.to_numpy() / 30
    daily_phase = 2 * np.pi * local_slot / 48
    fractional_day = local.dt.hour / 24 + local.dt.minute / (24 * 60)
    annual_phase = 2 * np.pi * (
        local.dt.dayofyear - 1 + fractional_day
    ).to_numpy() / 365.2425
    columns: list[np.ndarray] = [np.asarray(base_forecast, dtype=float) / 10_000]
    for harmonic in range(1, 5):
        columns.extend([np.sin(harmonic * daily_phase), np.cos(harmonic * daily_phase)])
    for harmonic in range(1, 4):
        columns.extend([np.sin(harmonic * annual_phase), np.cos(harmonic * annual_phase)])
    weekday = local.dt.dayofweek.to_numpy()
    columns.extend((weekday == day).astype(float) for day in range(1, 7))

    lag_columns = [f"lag_{lag}" for lag in CONFIG["fixed_safe_lags_half_hours"]] + [
        "safe_daily_mean",
        "safe_daily_std",
        "weekly_mean_4",
        "weekly_std_4",
        "daily_change_2_to_3",
        "weekly_change_1_to_2",
    ]
    columns.extend(data[column].to_numpy(dtype=float) / 10_000 for column in lag_columns)
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
    columns.extend(data[column].to_numpy(dtype=float) / 20 for column in weather_columns)
    embedded_columns = [
        "embedded_wind_forecast_mw",
        "embedded_solar_forecast_mw",
        "embedded_wind_capacity_mw",
        "embedded_solar_capacity_mw",
        "embedded_wind_change_week_mw",
        "embedded_solar_change_week_mw",
    ]
    columns.extend(data[column].to_numpy(dtype=float) / 10_000 for column in embedded_columns)
    columns.extend(
        [
            data["embedded_wind_capacity_factor_forecast"].to_numpy(dtype=float),
            data["embedded_solar_capacity_factor_forecast"].to_numpy(dtype=float),
        ]
    )
    flag_columns = [
        "is_bank_holiday_any_gb",
        "is_day_before_bank_holiday",
        "is_day_after_bank_holiday",
        "is_christmas_eve",
        "is_new_years_eve",
        "is_january_second",
        "embedded_forecast_imputed_from_week_lag",
    ]
    columns.extend(data[column].astype(float).to_numpy() for column in flag_columns)
    cutoff_us = data["forecast_cutoff_utc"].astype("int64").to_numpy()
    target_us = data["timestamp_utc"].astype("int64").to_numpy()
    columns.append((target_us - cutoff_us) / (48 * 30 * 60 * 1_000_000))
    matrix = np.column_stack(columns)
    if not np.isfinite(matrix).all():
        raise ValueError("Nonlinear feature matrix contains non-finite values")
    return matrix


def main() -> None:
    data = load_development()
    available = required_available(data)
    results = {
        "base_model": BASE.name,
        "selection_scope": "seven rolling-origin folds; Jan-Mar 2025 not scored",
        "final_test_opened": False,
        "spline_candidates": {},
        "hgb_candidates": {},
        "base_folds": {},
    }
    output_parts = []
    for fold in CONFIG["validation_folds"]:
        fold_name = fold["name"]
        training_end = pd.Timestamp(fold["train_end_inclusive"])
        training_start = max(
            pd.Timestamp(CONFIG["source_start_date"]),
            training_end - pd.Timedelta(days=BASE.recent_days - 1),
        )
        train = data["settlement_date"].between(
            training_start.strftime("%Y-%m-%d"), fold["train_end_inclusive"]
        ) & available
        validate = data["settlement_date"].between(
            fold["validation_start"], fold["validation_end_inclusive"]
        ) & available
        training = data.loc[train].copy()
        validation = data.loc[validate].copy()
        actual = validation["demand_mw"].to_numpy(dtype=float)

        base_training, _ = fit_predict(training, training, BASE)
        base_validation, base_metadata = fit_predict(training, validation, BASE)
        results["base_folds"][fold_name] = {
            **base_metadata,
            **metrics(actual, base_validation),
        }
        fold_output = validation[
            ["timestamp_utc", "settlement_date", "demand_mw"]
        ].copy()
        fold_output["fold"] = fold_name
        fold_output["forecast_v3_full_ridge_mw"] = base_validation

        for alpha in SPLINE_ALPHAS:
            name = f"spline_ridge_a{alpha:g}"
            forecast, metadata = fit_spline(training, validation, alpha)
            results["spline_candidates"].setdefault(
                name, {"alpha": alpha, "knots_c": SPLINE_KNOTS_C, "folds": {}}
            )["folds"][fold_name] = {**metadata, **metrics(actual, forecast)}
            fold_output[f"forecast_{name}_mw"] = forecast

        x_train = compact_nonlinear_design(training, base_training)
        x_validation = compact_nonlinear_design(validation, base_validation)
        residual_target = (
            training["demand_mw"].to_numpy(dtype=float) - base_training
        ) / 1_000
        for name, parameters in HGB_CANDIDATES.items():
            model = HistGradientBoostingRegressor(
                **parameters, early_stopping=False, random_state=7
            )
            model.fit(x_train, residual_target)
            forecast = base_validation + model.predict(x_validation) * 1_000
            results["hgb_candidates"].setdefault(
                name, {"parameters": parameters, "folds": {}}
            )["folds"][fold_name] = {
                "training_rows": int(len(training)),
                "features": int(x_train.shape[1]),
                **metrics(actual, forecast),
            }
            fold_output[f"forecast_{name}_mw"] = forecast
        output_parts.append(fold_output)

    results["base_summary"] = summarize(results["base_folds"])
    for group_name in ["spline_candidates", "hgb_candidates"]:
        for item in results[group_name].values():
            item["summary"] = summarize(item["folds"])
    all_candidates = {
        **{
            name: item["summary"]
            for name, item in results["spline_candidates"].items()
        },
        **{
            name: item["summary"] for name, item in results["hgb_candidates"].items()
        },
    }
    results["best_nonlinear_stage_candidate"] = min(
        all_candidates, key=lambda name: all_candidates[name]["mean_fold_mae_mw"]
    )
    (OUT / "nonlinear_candidate_metrics.json").write_text(
        json.dumps(results, indent=2) + "\n"
    )
    pd.concat(output_parts, ignore_index=True).to_csv(
        OUT / "nonlinear_validation_predictions.csv", index=False
    )
    print(
        json.dumps(
            {
                "base": results["base_summary"],
                "candidates": all_candidates,
                "best": results["best_nonlinear_stage_candidate"],
                "final_test_opened": False,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
