"""Feasibility test of small cutoff-safe ARMA error models for v3."""
from __future__ import annotations

import json
import warnings

import numpy as np
import pandas as pd
from statsmodels.tsa.statespace.sarimax import SARIMAX

from evaluate_v3_dynamic_candidates import BASE_ALPHA, BASE_RECENT_DAYS
from evaluate_v3_nonlinear_candidates import fit_spline
from evaluate_v3_ridge_ablation import (
    CONFIG,
    OUT,
    load_development,
    metrics,
    required_available,
    summarize,
)


ORDERS = [(1, 0, 1), (2, 0, 1), (2, 0, 2)]


def longest_contiguous(frame: pd.DataFrame) -> pd.DataFrame:
    blocks = frame["timestamp_utc"].diff().ne(pd.Timedelta(minutes=30)).cumsum()
    return frame.loc[blocks.eq(blocks.value_counts().idxmax())].copy()


def innovations(
    residual: np.ndarray,
    timestamp_us: np.ndarray,
    intercept: float,
    ar: np.ndarray,
    ma: np.ndarray,
) -> np.ndarray:
    errors = np.zeros(len(residual), dtype=float)
    for index in range(len(residual)):
        prediction = intercept
        valid = True
        for lag, coefficient in enumerate(ar, 1):
            prior = index - lag
            if (
                prior < 0
                or timestamp_us[index] - timestamp_us[prior]
                != lag * 30 * 60 * 1_000_000
            ):
                valid = False
                break
            prediction += coefficient * residual[prior]
        if valid:
            for lag, coefficient in enumerate(ma, 1):
                prior = index - lag
                if prior < 0:
                    valid = False
                    break
                prediction += coefficient * errors[prior]
        errors[index] = residual[index] - prediction if valid else 0.0
    return errors


def day_ahead_forecast(
    frame: pd.DataFrame,
    validate: pd.Series,
    intercept: float,
    ar: np.ndarray,
    ma: np.ndarray,
) -> np.ndarray:
    residual = frame["base_residual_mw"].to_numpy(dtype=float) / 1_000
    timestamp_us = frame["timestamp_utc"].astype("int64").to_numpy()
    interval_end_us = frame["interval_end_utc"].astype("int64").to_numpy()
    actual_innovations = innovations(residual, timestamp_us, intercept, ar, ma)
    result = np.full(len(frame), np.nan)
    validate_values = validate.to_numpy(dtype=bool)
    dates = frame["settlement_date"].to_numpy()
    for settlement_date in frame.loc[validate, "settlement_date"].drop_duplicates():
        positions = np.flatnonzero(validate_values & (dates == settlement_date))
        cutoff = pd.Timestamp(frame.loc[positions[0], "forecast_cutoff_utc"])
        cutoff_us = int(cutoff.to_datetime64().astype("datetime64[us]").astype("int64"))
        known_end = int(np.searchsorted(interval_end_us, cutoff_us, side="right") - 1)
        work_y = residual[: int(positions.max()) + 1].copy()
        work_y[known_end + 1 :] = np.nan
        work_error = actual_innovations[: int(positions.max()) + 1].copy()
        work_error[known_end + 1 :] = 0.0
        for index in range(known_end + 1, int(positions.max()) + 1):
            prediction = intercept
            valid = True
            for lag, coefficient in enumerate(ar, 1):
                prior = index - lag
                if (
                    prior < 0
                    or timestamp_us[index] - timestamp_us[prior]
                    != lag * 30 * 60 * 1_000_000
                    or not np.isfinite(work_y[prior])
                ):
                    valid = False
                    break
                prediction += coefficient * work_y[prior]
            if valid:
                for lag, coefficient in enumerate(ma, 1):
                    prior = index - lag
                    if prior < 0:
                        valid = False
                        break
                    prediction += coefficient * work_error[prior]
            work_y[index] = prediction if valid else 0.0
            work_error[index] = 0.0
        result[positions] = work_y[positions] * 1_000
    if np.isnan(result[validate_values]).any():
        raise ValueError("Incomplete ARMA validation forecast")
    return result


def main() -> None:
    data = load_development()
    available = required_available(data)
    results = {
        "base_model": "spline_ridge_a1",
        "purpose": "small nonseasonal ARMA feasibility after explicit exogenous seasonality",
        "final_test_opened": False,
        "candidates": {},
    }
    for fold in CONFIG["validation_folds"]:
        fold_name = fold["name"]
        training_end = pd.Timestamp(fold["train_end_inclusive"])
        training_start = max(
            pd.Timestamp(CONFIG["source_start_date"]),
            training_end - pd.Timedelta(days=BASE_RECENT_DAYS - 1),
        )
        train = data["settlement_date"].between(
            training_start.strftime("%Y-%m-%d"), fold["train_end_inclusive"]
        ) & available
        modeled_mask = available & data["settlement_date"].between(
            training_start.strftime("%Y-%m-%d"), fold["validation_end_inclusive"]
        )
        training = data.loc[train].copy()
        modeled = data.loc[modeled_mask].copy().reset_index(drop=True)
        base_forecast, _ = fit_spline(training, modeled, BASE_ALPHA)
        modeled["base_forecast_mw"] = base_forecast
        modeled["base_residual_mw"] = modeled["demand_mw"] - base_forecast
        validate = modeled["settlement_date"].between(
            fold["validation_start"], fold["validation_end_inclusive"]
        )
        actual = modeled.loc[validate, "demand_mw"].to_numpy(dtype=float)
        training_residuals = longest_contiguous(
            modeled.loc[
                modeled["settlement_date"].le(fold["train_end_inclusive"]),
                ["timestamp_utc", "base_residual_mw"],
            ]
        )
        y = training_residuals["base_residual_mw"].to_numpy(dtype=float) / 1_000
        for order in ORDERS:
            name = f"arma_{order[0]}_{order[2]}"
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                fitted = SARIMAX(
                    y,
                    order=order,
                    trend="c",
                    enforce_stationarity=False,
                    enforce_invertibility=False,
                ).fit(disp=False, maxiter=75)
            parameters = dict(zip(fitted.param_names, fitted.params))
            intercept = float(parameters.get("intercept", 0.0))
            ar = np.array(
                [parameters[f"ar.L{lag}"] for lag in range(1, order[0] + 1)]
            )
            ma = np.array(
                [parameters[f"ma.L{lag}"] for lag in range(1, order[2] + 1)]
            )
            correction = day_ahead_forecast(modeled, validate, intercept, ar, ma)
            forecast = (
                modeled.loc[validate, "base_forecast_mw"].to_numpy()
                + correction[validate.to_numpy()]
            )
            results["candidates"].setdefault(
                name, {"order": order, "folds": {}}
            )["folds"][fold_name] = {
                "converged": bool(fitted.mle_retvals.get("converged", False)),
                "aic": float(fitted.aic),
                "intercept": intercept,
                "ar": ar.tolist(),
                "ma": ma.tolist(),
                **metrics(actual, forecast),
            }
    for item in results["candidates"].values():
        item["summary"] = summarize(item["folds"])
    results["best_arma_candidate"] = min(
        results["candidates"],
        key=lambda name: results["candidates"][name]["summary"]["mean_fold_mae_mw"],
    )
    (OUT / "arma_candidate_metrics.json").write_text(
        json.dumps(results, indent=2) + "\n"
    )
    print(
        json.dumps(
            {
                "candidates": {
                    name: item["summary"] for name, item in results["candidates"].items()
                },
                "best": results["best_arma_candidate"],
                "final_test_opened": False,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
