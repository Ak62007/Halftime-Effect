"""Evaluate syllabus-scope residual dynamics on the plain exogenous Ridge model.

This intentionally excludes temperature splines, boosting and forecast blends.
"""
from __future__ import annotations

import json

import numpy as np
import pandas as pd

from evaluate_v2_ar_error_candidates import (
    AR_LAG_SETS,
    fit_ar,
    rolling_day_ahead_ar_correction,
)
from evaluate_v2_direct_residual_candidates import cutoff_features, direct_design, fit_ridge
from evaluate_v3_ridge_ablation import (
    CONFIG,
    OUT,
    Candidate,
    fit_predict,
    load_development,
    metrics,
    required_available,
    summarize,
)


BASE = Candidate("v3_full_recent730_a1", "full", 1.0, 730)
DIRECT_ALPHAS = [0.0, 0.1, 1.0, 10.0]


def exogenous_direct_design(frame: pd.DataFrame) -> np.ndarray:
    """Direct ARX features known at the previous-day forecast cutoff."""
    base = direct_design(frame)
    extra = [
        frame["base_forecast_mw"].to_numpy(dtype=float) / 10_000,
        frame["temperature_forecast_gb_c"].to_numpy(dtype=float) / 20,
        frame["heating_degree_forecast"].to_numpy(dtype=float) / 20,
        frame["cooling_degree_forecast"].to_numpy(dtype=float) / 20,
        frame["forecast_temperature_change_from_prior_day_c"].to_numpy(dtype=float) / 20,
        frame["embedded_wind_forecast_mw"].to_numpy(dtype=float) / 10_000,
        frame["embedded_solar_forecast_mw"].to_numpy(dtype=float) / 10_000,
        frame["embedded_wind_change_week_mw"].to_numpy(dtype=float) / 10_000,
        frame["embedded_solar_change_week_mw"].to_numpy(dtype=float) / 10_000,
        frame["is_bank_holiday_any_gb"].astype(float).to_numpy(),
        frame["is_day_before_bank_holiday"].astype(float).to_numpy(),
        frame["is_day_after_bank_holiday"].astype(float).to_numpy(),
    ]
    return np.column_stack([base] + extra)


def main() -> None:
    data = load_development()
    available = required_available(data)
    results = {
        "base_model": BASE.name,
        "model_scope": "plain exogenous Ridge with recursive AR or direct residual ARX Ridge",
        "forecast_protocol": "all residual inputs known by previous-day 10:00 London cutoff",
        "base_folds": {},
        "recursive_ar_candidates": {},
        "direct_arx_candidates": {},
    }
    output_parts = []

    for fold in CONFIG["validation_folds"]:
        fold_name = fold["name"]
        training_end = pd.Timestamp(fold["train_end_inclusive"])
        training_start = max(
            pd.Timestamp(CONFIG["source_start_date"]),
            training_end - pd.Timedelta(days=BASE.recent_days - 1),
        )
        train_mask = data["settlement_date"].between(
            training_start.strftime("%Y-%m-%d"), fold["train_end_inclusive"]
        ) & available
        modeled_mask = data["settlement_date"].between(
            training_start.strftime("%Y-%m-%d"), fold["validation_end_inclusive"]
        ) & available
        training = data.loc[train_mask].copy()
        modeled = data.loc[modeled_mask].copy().reset_index(drop=True)
        base_forecast, metadata = fit_predict(training, modeled, BASE)
        modeled["base_forecast_mw"] = base_forecast
        modeled["base_residual_mw"] = modeled["demand_mw"] - base_forecast
        modeled["residual_mw"] = modeled["base_residual_mw"]
        modeled = cutoff_features(modeled)

        train_dynamic = modeled["settlement_date"].le(fold["train_end_inclusive"])
        validate = modeled["settlement_date"].between(
            fold["validation_start"], fold["validation_end_inclusive"]
        )
        actual = modeled.loc[validate, "demand_mw"].to_numpy(dtype=float)
        base_validation = modeled.loc[validate, "base_forecast_mw"].to_numpy(dtype=float)
        results["base_folds"][fold_name] = {**metadata, **metrics(actual, base_validation)}

        fold_output = modeled.loc[
            validate,
            ["timestamp_utc", "settlement_date", "demand_mw", "base_forecast_mw"],
        ].copy()
        fold_output["fold"] = fold_name

        x_all = exogenous_direct_design(modeled)
        complete = np.isfinite(x_all).all(axis=1)
        train_complete = train_dynamic.to_numpy() & complete
        if not complete[validate.to_numpy()].all():
            raise ValueError(f"Incomplete direct ARX features in {fold_name}")
        x_train = x_all[train_complete]
        x_validation = x_all[validate.to_numpy()]
        target = modeled.loc[train_complete, "base_residual_mw"].to_numpy() / 1_000
        for alpha in DIRECT_ALPHAS:
            name = f"direct_arx_ridge_a{alpha:g}"
            coefficients = fit_ridge(x_train, target, alpha)
            forecast = base_validation + (x_validation @ coefficients) * 1_000
            results["direct_arx_candidates"].setdefault(
                name, {"alpha": alpha, "folds": {}}
            )["folds"][fold_name] = {
                "training_rows": int(train_complete.sum()),
                "features": int(x_train.shape[1]),
                **metrics(actual, forecast),
            }
            fold_output[f"forecast_{name}_mw"] = forecast

        training_residuals = modeled.loc[
            train_dynamic, ["timestamp_utc", "residual_mw"]
        ]
        for name, lags in AR_LAG_SETS.items():
            intercept, coefficients, ar_rows = fit_ar(training_residuals, lags)
            correction = rolling_day_ahead_ar_correction(
                modeled, validate, intercept, coefficients, lags
            )
            forecast = base_validation + correction[validate.to_numpy()]
            results["recursive_ar_candidates"].setdefault(
                name, {"ar_lags": lags, "folds": {}}
            )["folds"][fold_name] = {
                "ar_training_rows": ar_rows,
                "ar_intercept_mw": intercept,
                "ar_coefficients": {
                    str(lag): float(value) for lag, value in zip(lags, coefficients)
                },
                **metrics(actual, forecast),
            }
            fold_output[f"forecast_{name}_mw"] = forecast
        output_parts.append(fold_output)

    results["base_summary"] = summarize(results["base_folds"])
    for family in ["recursive_ar_candidates", "direct_arx_candidates"]:
        for item in results[family].values():
            item["summary"] = summarize(item["folds"])
    candidates = {
        **{name: item["summary"] for name, item in results["recursive_ar_candidates"].items()},
        **{name: item["summary"] for name, item in results["direct_arx_candidates"].items()},
    }
    results["best_dynamic_candidate"] = min(
        candidates, key=lambda name: candidates[name]["mean_fold_mae_mw"]
    )
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "presentation_scope_dynamic_metrics.json").write_text(
        json.dumps(results, indent=2) + "\n"
    )
    pd.concat(output_parts, ignore_index=True).to_csv(
        OUT / "presentation_scope_dynamic_predictions.csv", index=False
    )
    print(
        json.dumps(
            {
                "base": results["base_summary"],
                "candidates": candidates,
                "best": results["best_dynamic_candidate"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
