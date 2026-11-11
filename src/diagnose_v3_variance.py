"""Compare variance layers for the locked-development v3 point forecast."""
from __future__ import annotations

import json
import warnings

import numpy as np
import pandas as pd
from arch import arch_model
from sklearn.ensemble import HistGradientBoostingRegressor

from diagnose_v2_garch import (
    garch_variance_forecasts,
    longest_contiguous,
    residual_diagnostics,
)
from evaluate_v2_direct_residual_candidates import cutoff_features, fit_ridge
from evaluate_v3_dynamic_candidates import (
    BASE_ALPHA,
    BASE_RECENT_DAYS,
    HGB_PARAMETERS,
    v3_direct_design,
)
from evaluate_v3_nonlinear_candidates import fit_spline
from evaluate_v3_ridge_ablation import CONFIG, OUT, load_development, required_available


Z80 = 1.2815515655446004
Z95 = 1.959963984540054


def variance_design(frame: pd.DataFrame, selected_forecast: np.ndarray) -> np.ndarray:
    local = frame["timestamp_london"]
    local_slot = local.dt.hour.to_numpy() * 2 + local.dt.minute.to_numpy() / 30
    daily_phase = 2 * np.pi * local_slot / 48
    annual_phase = 2 * np.pi * (
        local.dt.dayofyear.to_numpy() - 1 + local_slot / 48
    ) / 365.2425
    columns = [np.asarray(selected_forecast) / 10_000]
    for harmonic in range(1, 4):
        columns.extend([np.sin(harmonic * daily_phase), np.cos(harmonic * daily_phase)])
    for harmonic in range(1, 3):
        columns.extend([np.sin(harmonic * annual_phase), np.cos(harmonic * annual_phase)])
    columns.extend(
        [
            frame["temperature_forecast_gb_c"].to_numpy(dtype=float) / 20,
            frame["heating_degree_forecast"].to_numpy(dtype=float) / 20,
            frame["cooling_degree_forecast"].to_numpy(dtype=float) / 20,
            frame["embedded_wind_forecast_mw"].to_numpy(dtype=float) / 10_000,
            frame["embedded_solar_forecast_mw"].to_numpy(dtype=float) / 10_000,
            frame["is_bank_holiday_any_gb"].astype(float).to_numpy(),
            frame["is_day_before_bank_holiday"].astype(float).to_numpy(),
            frame["is_day_after_bank_holiday"].astype(float).to_numpy(),
        ]
    )
    cutoff_us = frame["forecast_cutoff_utc"].astype("int64").to_numpy()
    target_us = frame["timestamp_utc"].astype("int64").to_numpy()
    columns.append((target_us - cutoff_us) / (48 * 30 * 60 * 1_000_000))
    matrix = np.column_stack(columns)
    if not np.isfinite(matrix).all():
        raise ValueError("Variance features contain non-finite values")
    return matrix


def interval_metrics(residual: np.ndarray, sigma: np.ndarray) -> dict:
    standardized = residual / sigma
    return {
        "coverage_80": float(np.mean(np.abs(standardized) <= Z80)),
        "coverage_95": float(np.mean(np.abs(standardized) <= Z95)),
        "mean_sigma_mw": float(np.mean(sigma)),
        "mean_95_interval_width_mw": float(np.mean(2 * Z95 * sigma)),
        "standardized_residual_diagnostics": residual_diagnostics(standardized),
    }


def main() -> None:
    data = load_development()
    available = required_available(data)
    results = {
        "point_model": "50/50 blend of direct_v3_ridge_a0 and direct_v3_hgb",
        "variance_models_change_point_forecast": False,
        "final_test_opened": False,
        "folds": {},
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
        base_forecast, _ = fit_spline(training, modeled, BASE_ALPHA)
        modeled["base_forecast_mw"] = base_forecast
        modeled["base_residual_mw"] = modeled["demand_mw"] - base_forecast
        modeled = cutoff_features(modeled)
        train_dynamic = modeled["settlement_date"].le(fold["train_end_inclusive"])
        validate = modeled["settlement_date"].between(
            fold["validation_start"], fold["validation_end_inclusive"]
        )
        x_all = v3_direct_design(modeled)
        complete = np.isfinite(x_all).all(axis=1)
        train_complete = train_dynamic.to_numpy() & complete
        ridge_coefficients = fit_ridge(
            x_all[train_complete],
            modeled.loc[train_complete, "base_residual_mw"].to_numpy() / 1_000,
            0.0,
        )
        ridge_correction = np.full(len(modeled), np.nan)
        ridge_correction[complete] = (x_all[complete] @ ridge_coefficients) * 1_000
        hgb = HistGradientBoostingRegressor(
            **HGB_PARAMETERS, early_stopping=False, random_state=7
        )
        hgb.fit(
            x_all[train_complete],
            modeled.loc[train_complete, "base_residual_mw"].to_numpy() / 1_000,
        )
        hgb_correction = np.full(len(modeled), np.nan)
        hgb_correction[complete] = hgb.predict(x_all[complete]) * 1_000
        selected_forecast = base_forecast + 0.5 * ridge_correction + 0.5 * hgb_correction
        modeled["selected_forecast_mw"] = selected_forecast
        modeled["selected_residual_mw"] = modeled["demand_mw"] - selected_forecast

        training_residual = modeled.loc[train_complete, "selected_residual_mw"].to_numpy()
        validation_residual = modeled.loc[validate, "selected_residual_mw"].to_numpy()
        constant_sigma = np.full(len(validation_residual), np.std(training_residual))

        garch_training = modeled.loc[
            train_complete, ["timestamp_utc", "selected_residual_mw"]
        ].dropna()
        garch_training = longest_contiguous(garch_training)
        scaled = garch_training["selected_residual_mw"].to_numpy() / 1_000
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            fitted_garch = arch_model(
                scaled,
                mean="Zero",
                vol="GARCH",
                p=1,
                q=1,
                dist="normal",
                rescale=False,
            ).fit(disp="off", show_warning=False)
        parameters = fitted_garch.params
        garch_input = modeled.rename(
            columns={"selected_residual_mw": "selected_residual_mw"}
        )
        garch_variance = garch_variance_forecasts(
            garch_input,
            validate,
            fold["train_end_inclusive"],
            float(parameters["omega"]),
            float(parameters["alpha[1]"]),
            float(parameters["beta[1]"]),
            float(fitted_garch.conditional_volatility[-1] ** 2),
        )
        garch_sigma = np.sqrt(garch_variance[validate.to_numpy()]) * 1_000

        # Early rows precede the residual model's complete lag history and are not
        # fitted or scored. Supply their finite base forecast only so construction of
        # the full feature matrix remains well defined.
        variance_forecast_input = np.where(
            np.isfinite(selected_forecast), selected_forecast, base_forecast
        )
        variance_x = variance_design(modeled, variance_forecast_input)
        variance_model = HistGradientBoostingRegressor(
            loss="squared_error",
            learning_rate=0.04,
            max_iter=250,
            max_leaf_nodes=15,
            min_samples_leaf=200,
            l2_regularization=20.0,
            early_stopping=False,
            random_state=7,
        )
        log_variance_target = np.log(training_residual**2 + 100.0**2)
        variance_model.fit(variance_x[train_complete], log_variance_target)
        raw_train_variance = np.exp(variance_model.predict(variance_x[train_complete]))
        scale = float(np.sqrt(np.mean(training_residual**2 / raw_train_variance)))
        structured_sigma = (
            np.sqrt(np.exp(variance_model.predict(variance_x[validate.to_numpy()])))
            * scale
        )

        fold_result = {
            "garch": {
                "converged": bool(fitted_garch.optimization_result.success),
                "alpha_plus_beta": float(
                    parameters["alpha[1]"] + parameters["beta[1]"]
                ),
                **interval_metrics(validation_residual, garch_sigma),
            },
            "constant": interval_metrics(validation_residual, constant_sigma),
            "structured": {
                "training_scale": scale,
                **interval_metrics(validation_residual, structured_sigma),
            },
            "original_residual_diagnostics": residual_diagnostics(validation_residual),
        }
        results["folds"][fold_name] = fold_result
        fold_output = modeled.loc[
            validate,
            [
                "timestamp_utc",
                "settlement_date",
                "demand_mw",
                "selected_forecast_mw",
                "selected_residual_mw",
            ],
        ].copy()
        fold_output["fold"] = fold_name
        fold_output["constant_sigma_mw"] = constant_sigma
        fold_output["garch_sigma_mw"] = garch_sigma
        fold_output["structured_sigma_mw"] = structured_sigma
        output_parts.append(fold_output)

    summary = {}
    for model_name in ["constant", "garch", "structured"]:
        fold_values = [fold[model_name] for fold in results["folds"].values()]
        summary[model_name] = {
            "mean_80_coverage": float(np.mean([x["coverage_80"] for x in fold_values])),
            "mean_95_coverage": float(np.mean([x["coverage_95"] for x in fold_values])),
            "mean_sigma_mw": float(np.mean([x["mean_sigma_mw"] for x in fold_values])),
            "mean_95_interval_width_mw": float(
                np.mean([x["mean_95_interval_width_mw"] for x in fold_values])
            ),
        }
    results["summary"] = summary
    results["selected_variance_model"] = min(
        summary,
        key=lambda name: abs(summary[name]["mean_80_coverage"] - 0.8)
        + abs(summary[name]["mean_95_coverage"] - 0.95),
    )
    (OUT / "variance_model_diagnostics.json").write_text(
        json.dumps(results, indent=2) + "\n"
    )
    pd.concat(output_parts, ignore_index=True).to_csv(
        OUT / "variance_validation_predictions.csv", index=False
    )
    print(
        json.dumps(
            {
                "summary": summary,
                "selected": results["selected_variance_model"],
                "final_test_opened": False,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
