"""Evaluate the retained syllabus-scope models on January to March 2026.

The period was opened in earlier work, so this is a transparent retrospective
re-evaluation after removing spline and boosting models, not a new untouched test.
"""
from __future__ import annotations

import json
import warnings

import numpy as np
import pandas as pd
from statsmodels.tsa.statespace.sarimax import SARIMAX

from evaluate_presentation_scope_arma import day_ahead_forecast, longest_contiguous
from evaluate_presentation_scope_dynamics import BASE, exogenous_direct_design
from evaluate_v2_ar_error_candidates import fit_ar, rolling_day_ahead_ar_correction
from evaluate_v2_direct_residual_candidates import cutoff_features, fit_ridge
from evaluate_v3_ridge_ablation import (
    CONFIG,
    OUT,
    fit_predict,
    load_v3_data,
    metrics,
    required_available,
)


TRAINING_END = "2025-12-30"
FINAL_START = "2026-01-01"
FINAL_END = "2026-03-31"
RECURSIVE_LAGS = [1, 2, 48, 96]
ARMA_ORDER = (1, 0, 1)


def main() -> None:
    data = load_v3_data(include_final_test=True)
    available = required_available(data)
    training_end = pd.Timestamp(TRAINING_END)
    training_start = training_end - pd.Timedelta(days=BASE.recent_days - 1)
    train_mask = data["settlement_date"].between(
        training_start.strftime("%Y-%m-%d"), TRAINING_END
    ) & available
    modeled_mask = data["settlement_date"].between(
        training_start.strftime("%Y-%m-%d"), FINAL_END
    ) & available
    training = data.loc[train_mask].copy()
    modeled = data.loc[modeled_mask].copy().reset_index(drop=True)
    final = modeled["settlement_date"].between(FINAL_START, FINAL_END)
    if int(final.sum()) != 4_318:
        raise ValueError("Unexpected final-test row count")

    base_forecast, base_metadata = fit_predict(training, modeled, BASE)
    modeled["base_forecast_mw"] = base_forecast
    modeled["base_residual_mw"] = modeled["demand_mw"] - base_forecast
    modeled["residual_mw"] = modeled["base_residual_mw"]
    modeled = cutoff_features(modeled)

    train_dynamic = modeled["settlement_date"].le(TRAINING_END)
    x_all = exogenous_direct_design(modeled)
    complete = np.isfinite(x_all).all(axis=1)
    train_complete = train_dynamic.to_numpy() & complete
    if not complete[final.to_numpy()].all():
        raise ValueError("Incomplete direct ARX features in final period")
    direct_coefficients = fit_ridge(
        x_all[train_complete],
        modeled.loc[train_complete, "base_residual_mw"].to_numpy() / 1_000,
        0.0,
    )
    direct_correction = np.full(len(modeled), np.nan)
    direct_correction[complete] = (x_all[complete] @ direct_coefficients) * 1_000
    modeled["direct_arx_forecast_mw"] = base_forecast + direct_correction

    intercept, coefficients, ar_rows = fit_ar(
        modeled.loc[train_dynamic, ["timestamp_utc", "residual_mw"]], RECURSIVE_LAGS
    )
    recursive_correction = rolling_day_ahead_ar_correction(
        modeled, final, intercept, coefficients, RECURSIVE_LAGS
    )
    modeled["recursive_ar_forecast_mw"] = base_forecast + recursive_correction

    arma_training = longest_contiguous(
        modeled.loc[
            train_dynamic, ["timestamp_utc", "base_residual_mw"]
        ]
    )
    y = arma_training["base_residual_mw"].to_numpy(dtype=float) / 1_000
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        fitted = SARIMAX(
            y,
            order=ARMA_ORDER,
            trend="c",
            enforce_stationarity=False,
            enforce_invertibility=False,
        ).fit(disp=False, maxiter=75)
    parameters = dict(zip(fitted.param_names, fitted.params))
    arma_intercept = float(parameters.get("intercept", 0.0))
    arma_ar = np.array([parameters["ar.L1"]])
    arma_ma = np.array([parameters["ma.L1"]])
    arma_correction = day_ahead_forecast(
        modeled, final, arma_intercept, arma_ar, arma_ma
    )
    modeled["arma_1_1_forecast_mw"] = base_forecast + arma_correction

    evaluation = modeled.loc[final].copy()
    actual = evaluation["demand_mw"].to_numpy(dtype=float)
    neso_available = evaluation["neso_available_at_cutoff"].to_numpy(dtype=bool)
    results = {
        "status": "retrospective scope-corrected evaluation; period was opened previously",
        "dates": [FINAL_START, FINAL_END],
        "training_end": TRAINING_END,
        "training_rows": int(len(training)),
        "base_fit": base_metadata,
        "recursive_ar": {
            "lags": RECURSIVE_LAGS,
            "training_rows": ar_rows,
            "intercept_mw": intercept,
            "coefficients": {
                str(lag): float(value) for lag, value in zip(RECURSIVE_LAGS, coefficients)
            },
        },
        "arma_1_1": {
            "converged": bool(fitted.mle_retvals.get("converged", False)),
            "intercept": arma_intercept,
            "ar": arma_ar.tolist(),
            "ma": arma_ma.tolist(),
        },
        "metrics": {
            "weekly_seasonal_naive": metrics(actual, evaluation["lag_336"].to_numpy()),
            "plain_exogenous_ridge": metrics(actual, evaluation["base_forecast_mw"].to_numpy()),
            "ridge_plus_recursive_ar": metrics(
                actual, evaluation["recursive_ar_forecast_mw"].to_numpy()
            ),
            "ridge_plus_arma_1_1": metrics(
                actual, evaluation["arma_1_1_forecast_mw"].to_numpy()
            ),
            "ridge_plus_direct_arx": metrics(
                actual, evaluation["direct_arx_forecast_mw"].to_numpy()
            ),
            "neso_available_rows": metrics(
                actual[neso_available],
                evaluation.loc[neso_available, "neso_day_ahead_forecast_mw"].to_numpy(),
            ),
        },
        "neso_available_rows": int(neso_available.sum()),
        "selected_research_model": "plain exogenous Ridge plus direct residual ARX",
    }
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "presentation_scope_final_test.json").write_text(
        json.dumps(results, indent=2) + "\n"
    )
    evaluation[
        [
            "timestamp_utc",
            "timestamp_london",
            "settlement_date",
            "demand_mw",
            "lag_336",
            "base_forecast_mw",
            "recursive_ar_forecast_mw",
            "arma_1_1_forecast_mw",
            "direct_arx_forecast_mw",
            "neso_day_ahead_forecast_mw",
            "neso_available_at_cutoff",
        ]
    ].to_csv(OUT / "presentation_scope_final_predictions.csv", index=False)
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
