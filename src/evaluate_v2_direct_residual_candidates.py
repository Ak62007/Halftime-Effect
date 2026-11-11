"""Evaluate direct cutoff-safe multi-horizon residual corrections."""
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
REGRESSION_RESULTS = json.loads((OUT / "regression_candidate_metrics.json").read_text())
BASE_NAME = REGRESSION_RESULTS["best_regression_candidate"]
BASE_SPEC = next(candidate for candidate in CANDIDATES if candidate.name == BASE_NAME)
DIRECT_ALPHAS = [0.0, 0.1, 1.0, 10.0]
RESIDUAL_LAGS = [96, 144, 192, 240, 288, 336, 672]


def cutoff_features(frame: pd.DataFrame) -> pd.DataFrame:
    """Construct features using residuals whose intervals end by the issue cutoff."""
    frame = frame.sort_values("timestamp_utc").reset_index(drop=True).copy()
    timestamp_us = frame["timestamp_utc"].astype("int64").to_numpy()
    interval_end_us = frame["interval_end_utc"].astype("int64").to_numpy()
    residual = frame["base_residual_mw"].to_numpy(dtype=float)

    for lag in RESIDUAL_LAGS:
        values = pd.Series(residual).shift(lag)
        lag_time = pd.Series(timestamp_us).shift(lag)
        expected = int(pd.Timedelta(minutes=30 * lag).total_seconds() * 1_000_000)
        aligned = pd.Series(timestamp_us).sub(lag_time).eq(expected)
        frame[f"residual_lag_{lag}"] = values.where(aligned).to_numpy()

    summary_columns = [
        "cutoff_latest_residual",
        "cutoff_mean_6h",
        "cutoff_mean_12h",
        "cutoff_mean_24h",
        "cutoff_mean_48h",
        "cutoff_std_24h",
        "cutoff_std_48h",
    ]
    for column in summary_columns:
        frame[column] = np.nan
    frame["horizon_half_hours"] = np.nan

    for settlement_date, indices in frame.groupby("settlement_date").groups.items():
        positions = np.asarray(list(indices), dtype=int)
        cutoff = pd.Timestamp(frame.loc[positions[0], "forecast_cutoff_utc"])
        cutoff_us = int(
            cutoff.to_datetime64().astype("datetime64[us]").astype("int64")
        )
        known_end = int(np.searchsorted(interval_end_us, cutoff_us, side="right") - 1)
        if known_end < 95:
            continue
        history = residual[: known_end + 1]
        if not np.isfinite(history[known_end - 95 : known_end + 1]).all():
            continue
        values = {
            "cutoff_latest_residual": history[known_end],
            "cutoff_mean_6h": np.mean(history[known_end - 11 : known_end + 1]),
            "cutoff_mean_12h": np.mean(history[known_end - 23 : known_end + 1]),
            "cutoff_mean_24h": np.mean(history[known_end - 47 : known_end + 1]),
            "cutoff_mean_48h": np.mean(history[known_end - 95 : known_end + 1]),
            "cutoff_std_24h": np.std(history[known_end - 47 : known_end + 1]),
            "cutoff_std_48h": np.std(history[known_end - 95 : known_end + 1]),
        }
        for column, value in values.items():
            frame.loc[positions, column] = value
        target_start_us = timestamp_us[positions]
        frame.loc[positions, "horizon_half_hours"] = (
            target_start_us - cutoff_us
        ) / (30 * 60 * 1_000_000)
        if not (interval_end_us[positions] > cutoff_us).all():
            raise ValueError("A target was observed by its own issue cutoff")
    return frame


def direct_design(frame: pd.DataFrame) -> np.ndarray:
    columns = [f"residual_lag_{lag}" for lag in RESIDUAL_LAGS] + [
        "cutoff_latest_residual",
        "cutoff_mean_6h",
        "cutoff_mean_12h",
        "cutoff_mean_24h",
        "cutoff_mean_48h",
        "cutoff_std_24h",
        "cutoff_std_48h",
    ]
    scaled = [frame[column].to_numpy(dtype=float) / 1_000 for column in columns]
    horizon = frame["horizon_half_hours"].to_numpy(dtype=float) / 48
    scaled.append(horizon)
    # Allow the latest level correction to decay or strengthen with horizon.
    scaled.append((frame["cutoff_mean_24h"].to_numpy() / 1_000) * horizon)
    half_hour = frame["timestamp_london"].dt.hour.to_numpy() * 2 + (
        frame["timestamp_london"].dt.minute.to_numpy() // 30
    )
    daily_phase = 2 * np.pi * half_hour / 48
    for harmonic in range(1, 5):
        scaled.extend(
            [np.sin(harmonic * daily_phase), np.cos(harmonic * daily_phase)]
        )
    weekday = frame["timestamp_london"].dt.dayofweek.to_numpy()
    scaled.extend((weekday == day).astype(float) for day in range(1, 7))
    return np.column_stack([np.ones(len(frame))] + scaled)


def fit_ridge(x: np.ndarray, y: np.ndarray, alpha: float) -> np.ndarray:
    penalty = np.eye(x.shape[1]) * alpha
    penalty[0, 0] = 0.0
    return np.linalg.solve(x.T @ x + penalty, x.T @ y)


def main() -> None:
    data = load_development()
    data["interval_end_utc"] = pd.to_datetime(data["interval_end_utc"], utc=True)
    data["forecast_cutoff_utc"] = pd.to_datetime(data["forecast_cutoff_utc"], utc=True)
    results = {
        "base_regression": BASE_NAME,
        "target": "base-model residual in MW",
        "protocol": "direct multi-horizon features available at previous-day 10:00 cutoff",
        "final_test_opened": False,
        "euro_2024_used_for_selection": False,
        "candidates": {},
    }
    output_parts = []

    for fold in CONFIG["validation_folds"]:
        fold_name = fold["name"]
        training_end = pd.Timestamp(fold["train_end_inclusive"])
        training_start = max(
            pd.Timestamp(CONFIG["source_start_date"]),
            training_end - pd.Timedelta(days=BASE_SPEC.recent_days - 1),
        )
        available = required_available(data, BASE_SPEC)
        training_mask = data["settlement_date"].between(
            training_start.strftime("%Y-%m-%d"), fold["train_end_inclusive"]
        ) & available
        modeled_mask = available & data["settlement_date"].between(
            training_start.strftime("%Y-%m-%d"), fold["validation_end_inclusive"]
        )
        training = data.loc[training_mask].copy()
        modeled = data.loc[modeled_mask].copy().reset_index(drop=True)
        base_prediction, fit_metadata = fit_and_predict(training, modeled, BASE_SPEC)
        modeled["base_forecast_mw"] = base_prediction
        modeled["base_residual_mw"] = modeled["demand_mw"] - base_prediction
        modeled = cutoff_features(modeled)

        train_direct = modeled["settlement_date"].le(fold["train_end_inclusive"])
        validate = modeled["settlement_date"].between(
            fold["validation_start"], fold["validation_end_inclusive"]
        )
        x_all = direct_design(modeled)
        complete = np.isfinite(x_all).all(axis=1)
        train_direct &= complete
        if not complete[validate.to_numpy()].all():
            raise ValueError(f"Incomplete validation features for {fold_name}")
        x_train = x_all[train_direct.to_numpy()]
        y_train = modeled.loc[train_direct, "base_residual_mw"].to_numpy() / 1_000
        x_validation = x_all[validate.to_numpy()]
        actual = modeled.loc[validate, "demand_mw"].to_numpy()
        base_validation = modeled.loc[validate, "base_forecast_mw"].to_numpy()

        fold_output = modeled.loc[
            validate,
            ["timestamp_utc", "settlement_date", "demand_mw", "base_forecast_mw"],
        ].copy()
        fold_output["fold"] = fold_name
        for alpha in DIRECT_ALPHAS:
            name = f"direct_residual_ridge_a{alpha:g}"
            coefficients = fit_ridge(x_train, y_train, alpha)
            correction = (x_validation @ coefficients) * 1_000
            forecast = base_validation + correction
            result = metrics(actual, forecast)
            results["candidates"].setdefault(
                name, {"alpha": alpha, "folds": {}}
            )["folds"][fold_name] = {
                **fit_metadata,
                "residual_training_rows": int(train_direct.sum()),
                "residual_features": int(x_train.shape[1]),
                **result,
            }
            fold_output[f"forecast_{name}_mw"] = forecast
        output_parts.append(fold_output)

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
    results["best_direct_residual_candidate"] = selected
    results["direct_stage_locked_before_final_comparison"] = True
    (OUT / "direct_residual_candidate_metrics.json").write_text(
        json.dumps(results, indent=2) + "\n"
    )
    pd.concat(output_parts, ignore_index=True).to_csv(
        OUT / "direct_residual_validation_predictions.csv", index=False
    )
    print(
        json.dumps(
            {
                "base_regression": BASE_NAME,
                "candidates": {
                    name: item["summary"] for name, item in results["candidates"].items()
                },
                "best_direct_residual_candidate": selected,
                "final_test_opened": False,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
