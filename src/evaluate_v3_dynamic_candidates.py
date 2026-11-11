"""Compare cutoff-safe direct and recursive residual dynamics for v3."""
from __future__ import annotations

import json

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor

from evaluate_v2_ar_error_candidates import (
    AR_LAG_SETS,
    fit_ar,
    rolling_day_ahead_ar_correction,
)
from evaluate_v2_direct_residual_candidates import cutoff_features, direct_design, fit_ridge
from evaluate_v3_nonlinear_candidates import fit_spline
from evaluate_v3_ridge_ablation import (
    CONFIG,
    OUT,
    load_development,
    metrics,
    required_available,
    summarize,
)


BASE_NAME = "spline_ridge_a1"
BASE_ALPHA = 1.0
BASE_RECENT_DAYS = 730
DIRECT_ALPHAS = [0.0, 0.1, 1.0, 10.0]
HGB_PARAMETERS = {
    "loss": "squared_error",
    "learning_rate": 0.05,
    "max_iter": 300,
    "max_leaf_nodes": 15,
    "min_samples_leaf": 100,
    "l2_regularization": 10.0,
}


def v3_direct_design(frame: pd.DataFrame) -> np.ndarray:
    base = direct_design(frame)
    extra_columns = [
        frame["base_forecast_mw"].to_numpy(dtype=float) / 10_000,
        frame["temperature_forecast_gb_c"].to_numpy(dtype=float) / 20,
        frame["heating_degree_forecast"].to_numpy(dtype=float) / 20,
        frame["cooling_degree_forecast"].to_numpy(dtype=float) / 20,
        frame["forecast_temperature_change_from_prior_day_c"].to_numpy(dtype=float)
        / 20,
        frame["embedded_wind_forecast_mw"].to_numpy(dtype=float) / 10_000,
        frame["embedded_solar_forecast_mw"].to_numpy(dtype=float) / 10_000,
        frame["embedded_wind_change_week_mw"].to_numpy(dtype=float) / 10_000,
        frame["embedded_solar_change_week_mw"].to_numpy(dtype=float) / 10_000,
        frame["is_bank_holiday_any_gb"].astype(float).to_numpy(),
        frame["is_day_before_bank_holiday"].astype(float).to_numpy(),
        frame["is_day_after_bank_holiday"].astype(float).to_numpy(),
        frame["embedded_forecast_imputed_from_week_lag"].astype(float).to_numpy(),
    ]
    return np.column_stack([base] + extra_columns)


def main() -> None:
    data = load_development()
    available = required_available(data)
    results = {
        "base_model": BASE_NAME,
        "forecast_protocol": "all residual inputs known by previous-day 10:00 cutoff",
        "final_test_opened": False,
        "base_folds": {},
        "direct_ridge_candidates": {},
        "direct_hgb_candidate": {"parameters": HGB_PARAMETERS, "folds": {}},
        "recursive_ar_candidates": {},
    }
    output_parts = []
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
        base_forecast, base_metadata = fit_spline(
            training, modeled, BASE_ALPHA
        )
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
        results["base_folds"][fold_name] = {
            **base_metadata,
            **metrics(actual, base_validation),
        }
        fold_output = modeled.loc[
            validate,
            ["timestamp_utc", "settlement_date", "demand_mw", "base_forecast_mw"],
        ].copy()
        fold_output["fold"] = fold_name

        x_all = v3_direct_design(modeled)
        complete = np.isfinite(x_all).all(axis=1)
        train_complete = train_dynamic.to_numpy() & complete
        if not complete[validate.to_numpy()].all():
            raise ValueError(f"Incomplete direct features: {fold_name}")
        x_train = x_all[train_complete]
        x_validation = x_all[validate.to_numpy()]
        target = modeled.loc[train_complete, "base_residual_mw"].to_numpy() / 1_000
        for alpha in DIRECT_ALPHAS:
            name = f"direct_v3_ridge_a{alpha:g}"
            coefficients = fit_ridge(x_train, target, alpha)
            forecast = base_validation + (x_validation @ coefficients) * 1_000
            results["direct_ridge_candidates"].setdefault(
                name, {"alpha": alpha, "folds": {}}
            )["folds"][fold_name] = {
                "training_rows": int(train_complete.sum()),
                "features": int(x_train.shape[1]),
                **metrics(actual, forecast),
            }
            fold_output[f"forecast_{name}_mw"] = forecast

        hgb = HistGradientBoostingRegressor(
            **HGB_PARAMETERS, early_stopping=False, random_state=7
        )
        hgb.fit(x_train, target)
        hgb_forecast = base_validation + hgb.predict(x_validation) * 1_000
        results["direct_hgb_candidate"]["folds"][fold_name] = {
            "training_rows": int(train_complete.sum()),
            "features": int(x_train.shape[1]),
            **metrics(actual, hgb_forecast),
        }
        fold_output["forecast_direct_v3_hgb_mw"] = hgb_forecast

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
    for item in results["direct_ridge_candidates"].values():
        item["summary"] = summarize(item["folds"])
    results["direct_hgb_candidate"]["summary"] = summarize(
        results["direct_hgb_candidate"]["folds"]
    )
    for item in results["recursive_ar_candidates"].values():
        item["summary"] = summarize(item["folds"])
    summaries = {
        **{
            name: item["summary"]
            for name, item in results["direct_ridge_candidates"].items()
        },
        "direct_v3_hgb": results["direct_hgb_candidate"]["summary"],
        **{
            name: item["summary"]
            for name, item in results["recursive_ar_candidates"].items()
        },
    }
    results["best_dynamic_candidate"] = min(
        summaries, key=lambda name: summaries[name]["mean_fold_mae_mw"]
    )
    (OUT / "dynamic_candidate_metrics.json").write_text(
        json.dumps(results, indent=2) + "\n"
    )
    pd.concat(output_parts, ignore_index=True).to_csv(
        OUT / "dynamic_validation_predictions.csv", index=False
    )
    print(
        json.dumps(
            {
                "base": results["base_summary"],
                "candidates": summaries,
                "best": results["best_dynamic_candidate"],
                "final_test_opened": False,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
