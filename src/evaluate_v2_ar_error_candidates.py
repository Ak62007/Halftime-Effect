"""Add cutoff-aware autoregressive errors to the best v2 regression mean model."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from evaluate_v2_regression_candidates import (
    CANDIDATES,
    CONFIG,
    OUT,
    fit_and_predict,
    load_development,
    metrics,
    required_available,
)


ROOT = Path(__file__).resolve().parents[1]
REGRESSION_RESULTS_FILE = OUT / "regression_candidate_metrics.json"
if REGRESSION_RESULTS_FILE.exists():
    REGRESSION_RESULTS = json.loads(REGRESSION_RESULTS_FILE.read_text())
    BASE_NAME = REGRESSION_RESULTS["best_regression_candidate"]
    BASE_SPEC = next(candidate for candidate in CANDIDATES if candidate.name == BASE_NAME)
else:
    REGRESSION_RESULTS = None
    BASE_NAME = None
    BASE_SPEC = None

AR_LAG_SETS = {
    "ar_short_1_2": [1, 2],
    "ar_daily_1_2_48": [1, 2, 48],
    "ar_daily_1_2_48_96": [1, 2, 48, 96],
    "ar_multi_1_2_48_96_336": [1, 2, 48, 96, 336],
}


def fit_ar(residual_frame: pd.DataFrame, lags: list[int]) -> tuple[float, np.ndarray, int]:
    frame = residual_frame[["timestamp_utc", "residual_mw"]].copy()
    design = []
    valid = frame["residual_mw"].notna()
    for lag in lags:
        lag_residual = frame["residual_mw"].shift(lag)
        lag_time = frame["timestamp_utc"].shift(lag)
        aligned = frame["timestamp_utc"].sub(lag_time).eq(
            pd.Timedelta(minutes=30 * lag)
        )
        lag_residual = lag_residual.where(aligned)
        design.append(lag_residual.to_numpy())
        valid &= lag_residual.notna()
    matrix = np.column_stack([np.ones(valid.sum())] + [values[valid] for values in design])
    target = frame.loc[valid, "residual_mw"].to_numpy(dtype=float)
    coefficients, *_ = np.linalg.lstsq(matrix, target, rcond=None)
    return float(coefficients[0]), coefficients[1:], int(valid.sum())


def rolling_day_ahead_ar_correction(
    frame: pd.DataFrame,
    validation_mask: pd.Series,
    intercept: float,
    coefficients: np.ndarray,
    lags: list[int],
) -> np.ndarray:
    """Recursively forecast residuals after each previous-day 10:00 cutoff."""
    frame = frame.sort_values("timestamp_utc").reset_index(drop=True).copy()
    validation_values = validation_mask.to_numpy(dtype=bool)
    actual_residual = frame["residual_mw"].to_numpy(dtype=float)
    result = np.full(len(frame), np.nan)
    # CSV parsing preserves microsecond resolution. Keep every integer comparison in
    # that same unit; Timestamp.value is always nanoseconds and must not be mixed in.
    timestamp_us = frame["timestamp_utc"].astype("int64").to_numpy()
    interval_end_us = frame["interval_end_utc"].astype("int64").to_numpy()
    date_values = frame["settlement_date"].to_numpy()

    validation_dates = frame.loc[validation_values, "settlement_date"].drop_duplicates()
    for settlement_date in validation_dates:
        target_positions = np.flatnonzero(
            validation_values & (date_values == settlement_date)
        )
        if len(target_positions) == 0:
            continue
        cutoff = pd.Timestamp(frame.loc[target_positions[0], "forecast_cutoff_utc"])
        cutoff_us = int(
            cutoff.to_datetime64().astype("datetime64[us]").astype("int64")
        )
        if not (interval_end_us[target_positions] > cutoff_us).all():
            raise ValueError("Target outcome was already available at its forecast cutoff")
        known_end = int(
            np.searchsorted(interval_end_us, cutoff_us, side="right") - 1
        )
        last_target = int(target_positions.max())
        working = actual_residual[: last_target + 1].copy()
        working[known_end + 1 :] = np.nan
        for index in range(known_end + 1, last_target + 1):
            values = []
            missing = False
            for lag in lags:
                lag_index = index - lag
                aligned = (
                    lag_index >= 0
                    and timestamp_us[index] - timestamp_us[lag_index]
                    == int(pd.Timedelta(minutes=30 * lag).total_seconds() * 1_000_000)
                )
                value = working[lag_index] if aligned else np.nan
                if not np.isfinite(value):
                    missing = True
                    break
                values.append(value)
            prediction = 0.0 if missing else intercept + float(coefficients @ values)
            working[index] = prediction
        result[target_positions] = working[target_positions]
    if np.isnan(result[validation_values]).any():
        raise ValueError("Some validation residual forecasts were not generated")
    return result


def main() -> None:
    if BASE_SPEC is None:
        raise FileNotFoundError("Run evaluate_v2_regression_candidates.py first")
    data = load_development()
    # These columns are parsed here because the regression stage did not need them.
    data["interval_end_utc"] = pd.to_datetime(data["interval_end_utc"], utc=True)
    data["forecast_cutoff_utc"] = pd.to_datetime(data["forecast_cutoff_utc"], utc=True)
    results = {
        "base_regression": BASE_NAME,
        "forecast_protocol": "recursive AR errors after previous-day 10:00 London cutoff",
        "final_test_opened": False,
        "euro_2024_used_for_selection": False,
        "candidates": {},
    }
    prediction_parts = []

    for fold in CONFIG["validation_folds"]:
        fold_name = fold["name"]
        training_end = pd.Timestamp(fold["train_end_inclusive"])
        training_start = max(
            pd.Timestamp(CONFIG["source_start_date"]),
            training_end - pd.Timedelta(days=BASE_SPEC.recent_days - 1),
        )
        available = required_available(data, BASE_SPEC)
        training_mask = (
            data["settlement_date"].between(
                training_start.strftime("%Y-%m-%d"), fold["train_end_inclusive"]
            )
            & available
        )
        validation_mask = (
            data["settlement_date"].between(
                fold["validation_start"], fold["validation_end_inclusive"]
            )
            & available
        )
        training = data.loc[training_mask].copy()

        # Generate the same fixed-parameter mean prediction for every row required
        # by the residual process. No future target is used to estimate coefficients.
        modeled_mask = available & data["settlement_date"].between(
            training_start.strftime("%Y-%m-%d"), fold["validation_end_inclusive"]
        )
        modeled = data.loc[modeled_mask].copy().reset_index(drop=True)
        base_prediction, fit_metadata = fit_and_predict(training, modeled, BASE_SPEC)
        modeled["base_forecast_mw"] = base_prediction
        modeled["residual_mw"] = modeled["demand_mw"] - modeled["base_forecast_mw"]
        modeled_validation = modeled["settlement_date"].between(
            fold["validation_start"], fold["validation_end_inclusive"]
        )
        actual = modeled.loc[modeled_validation, "demand_mw"].to_numpy(dtype=float)

        fold_output = modeled.loc[
            modeled_validation,
            ["timestamp_utc", "settlement_date", "demand_mw", "base_forecast_mw"],
        ].copy()
        fold_output["fold"] = fold_name
        training_residuals = modeled.loc[
            modeled["settlement_date"].le(fold["train_end_inclusive"]),
            ["timestamp_utc", "residual_mw"],
        ]
        for name, lags in AR_LAG_SETS.items():
            intercept, coefficients, ar_training_rows = fit_ar(training_residuals, lags)
            correction = rolling_day_ahead_ar_correction(
                modeled, modeled_validation, intercept, coefficients, lags
            )
            correction_validation = correction[modeled_validation.to_numpy()]
            forecast = (
                modeled.loc[modeled_validation, "base_forecast_mw"].to_numpy()
                + correction_validation
            )
            result = metrics(actual, forecast)
            results["candidates"].setdefault(
                name,
                {
                    "ar_lags": lags,
                    "folds": {},
                },
            )["folds"][fold_name] = {
                **fit_metadata,
                "ar_training_rows": ar_training_rows,
                "ar_intercept_mw": intercept,
                "ar_coefficients": {
                    str(lag): float(value)
                    for lag, value in zip(lags, coefficients)
                },
                **result,
            }
            fold_output[f"forecast_{name}_mw"] = forecast
        prediction_parts.append(fold_output)

    for name, item in results["candidates"].items():
        folds = list(item["folds"].values())
        item["summary"] = {
            "mean_fold_mae_mw": float(np.mean([x["mae_mw"] for x in folds])),
            "mean_fold_rmse_mw": float(np.mean([x["rmse_mw"] for x in folds])),
            "mean_fold_absolute_bias_mw": float(
                np.mean([abs(x["me_mw"]) for x in folds])
            ),
            "worst_fold_mae_mw": float(max(x["mae_mw"] for x in folds)),
        }
    selected = min(
        results["candidates"],
        key=lambda name: results["candidates"][name]["summary"]["mean_fold_mae_mw"],
    )
    results["best_ar_error_candidate"] = selected
    results["ar_stage_locked_before_sarimax"] = True
    (OUT / "ar_error_candidate_metrics.json").write_text(
        json.dumps(results, indent=2) + "\n"
    )
    pd.concat(prediction_parts, ignore_index=True).to_csv(
        OUT / "ar_error_validation_predictions.csv", index=False
    )
    print(
        json.dumps(
            {
                "base_regression": BASE_NAME,
                "candidates": {
                    name: item["summary"] for name, item in results["candidates"].items()
                },
                "best_ar_error_candidate": selected,
                "final_test_opened": False,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
