"""Fit and evaluate one GARCH(1,1) layer for the selected v2 mean model."""
from __future__ import annotations

import json
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from arch import arch_model
from statsmodels.stats.diagnostic import acorr_ljungbox, het_arch
from statsmodels.tsa.stattools import acf

from evaluate_v2_direct_residual_candidates import (
    BASE_NAME,
    BASE_SPEC,
    CONFIG,
    OUT,
    cutoff_features,
    direct_design,
    fit_ridge,
)
from evaluate_v2_regression_candidates import (
    fit_and_predict,
    load_development,
    required_available,
)


ROOT = Path(__file__).resolve().parents[1]
SELECTED_DIRECT_ALPHA = 0.0


def longest_contiguous(frame: pd.DataFrame) -> pd.DataFrame:
    blocks = frame["timestamp_utc"].diff().ne(pd.Timedelta(minutes=30)).cumsum()
    largest = blocks.value_counts().idxmax()
    return frame.loc[blocks.eq(largest)].copy()


def residual_diagnostics(residual: np.ndarray) -> dict:
    values = np.asarray(residual, dtype=float)
    correlation = acf(values, nlags=336, fft=True)
    squared = acf((values - values.mean()) ** 2, nlags=336, fft=True)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", FutureWarning)
        arch_lm, arch_p, _, _ = het_arch(values, nlags=48)
    ljung = acorr_ljungbox(values, lags=[48, 96, 336], return_df=True)
    return {
        "acf": {str(lag): float(correlation[lag]) for lag in [1, 2, 48, 96, 336]},
        "squared_acf": {str(lag): float(squared[lag]) for lag in [1, 2, 48, 96, 336]},
        "arch_lm_48": {"statistic": float(arch_lm), "p_value": float(arch_p)},
        "ljung_box": {
            str(lag): {
                "statistic": float(ljung.loc[lag, "lb_stat"]),
                "p_value": float(ljung.loc[lag, "lb_pvalue"]),
            }
            for lag in [48, 96, 336]
        },
    }


def garch_variance_forecasts(
    modeled: pd.DataFrame,
    validation_mask: pd.Series,
    training_end: str,
    omega: float,
    alpha: float,
    beta: float,
    last_training_variance: float,
) -> np.ndarray:
    """Forecast conditional variance from each cutoff without future residuals."""
    frame = modeled.reset_index(drop=True)
    validation_values = validation_mask.to_numpy(dtype=bool)
    residual = frame["selected_residual_mw"].to_numpy(dtype=float) / 1_000
    interval_end_us = frame["interval_end_utc"].astype("int64").to_numpy()
    dates = frame["settlement_date"].to_numpy()
    variance = np.full(len(frame), np.nan)

    training_positions = np.flatnonzero(
        frame["settlement_date"].le(training_end).to_numpy()
        & np.isfinite(residual)
    )
    last_training = int(training_positions.max())
    variance[last_training] = last_training_variance
    for index in range(last_training + 1, len(frame)):
        if not np.isfinite(residual[index - 1]) or not np.isfinite(variance[index - 1]):
            continue
        variance[index] = (
            omega + alpha * residual[index - 1] ** 2 + beta * variance[index - 1]
        )

    forecast_variance = np.full(len(frame), np.nan)
    for settlement_date in frame.loc[validation_values, "settlement_date"].drop_duplicates():
        positions = np.flatnonzero(validation_values & (dates == settlement_date))
        cutoff = pd.Timestamp(frame.loc[positions[0], "forecast_cutoff_utc"])
        cutoff_us = int(
            cutoff.to_datetime64().astype("datetime64[us]").astype("int64")
        )
        known_end = int(np.searchsorted(interval_end_us, cutoff_us, side="right") - 1)
        if not np.isfinite(variance[known_end]) or not np.isfinite(residual[known_end]):
            raise ValueError("GARCH state unavailable at forecast cutoff")
        current = omega + alpha * residual[known_end] ** 2 + beta * variance[known_end]
        for index in range(known_end + 1, int(positions.max()) + 1):
            if index > known_end + 1:
                current = omega + (alpha + beta) * current
            if index in positions:
                forecast_variance[index] = current
    if np.isnan(forecast_variance[validation_values]).any():
        raise ValueError("Incomplete GARCH variance forecasts")
    return forecast_variance


def main() -> None:
    data = load_development()
    data["interval_end_utc"] = pd.to_datetime(data["interval_end_utc"], utc=True)
    data["forecast_cutoff_utc"] = pd.to_datetime(data["forecast_cutoff_utc"], utc=True)
    results = {
        "selected_mean_model": "ridge multilag level + direct residual correction",
        "selected_base_regression": BASE_NAME,
        "garch_specification": "zero-mean Gaussian GARCH(1,1)",
        "final_test_opened": False,
        "folds": {},
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
        train_mask = data["settlement_date"].between(
            training_start.strftime("%Y-%m-%d"), fold["train_end_inclusive"]
        ) & available
        modeled_mask = available & data["settlement_date"].between(
            training_start.strftime("%Y-%m-%d"), fold["validation_end_inclusive"]
        )
        training = data.loc[train_mask].copy()
        modeled = data.loc[modeled_mask].copy().reset_index(drop=True)
        base_prediction, _ = fit_and_predict(training, modeled, BASE_SPEC)
        modeled["base_forecast_mw"] = base_prediction
        modeled["base_residual_mw"] = modeled["demand_mw"] - base_prediction
        modeled = cutoff_features(modeled)
        x_all = direct_design(modeled)
        complete = np.isfinite(x_all).all(axis=1)
        train_direct = (
            modeled["settlement_date"].le(fold["train_end_inclusive"]).to_numpy()
            & complete
        )
        validate = modeled["settlement_date"].between(
            fold["validation_start"], fold["validation_end_inclusive"]
        )
        coefficients = fit_ridge(
            x_all[train_direct],
            modeled.loc[train_direct, "base_residual_mw"].to_numpy() / 1_000,
            SELECTED_DIRECT_ALPHA,
        )
        correction = np.full(len(modeled), np.nan)
        correction[complete] = (x_all[complete] @ coefficients) * 1_000
        modeled["selected_forecast_mw"] = modeled["base_forecast_mw"] + correction
        modeled["selected_residual_mw"] = (
            modeled["demand_mw"] - modeled["selected_forecast_mw"]
        )

        garch_training = modeled.loc[
            train_direct,
            ["timestamp_utc", "selected_residual_mw"],
        ].dropna()
        garch_training = longest_contiguous(garch_training)
        scaled_training = garch_training["selected_residual_mw"].to_numpy() / 1_000
        model = arch_model(
            scaled_training,
            mean="Zero",
            vol="GARCH",
            p=1,
            q=1,
            dist="normal",
            rescale=False,
        )
        fitted = model.fit(disp="off", show_warning=False)
        params = fitted.params
        omega = float(params["omega"])
        alpha = float(params["alpha[1]"])
        beta = float(params["beta[1]"])
        variance_forecast = garch_variance_forecasts(
            modeled,
            validate,
            fold["train_end_inclusive"],
            omega,
            alpha,
            beta,
            float(fitted.conditional_volatility[-1] ** 2),
        )
        validation_residual = modeled.loc[validate, "selected_residual_mw"].to_numpy()
        validation_sigma_mw = np.sqrt(variance_forecast[validate.to_numpy()]) * 1_000
        standardized = validation_residual / validation_sigma_mw
        original_diagnostics = residual_diagnostics(validation_residual)
        standardized_diagnostics = residual_diagnostics(standardized)
        coverage_80 = float(np.mean(np.abs(standardized) <= 1.2815515655446004))
        coverage_95 = float(np.mean(np.abs(standardized) <= 1.959963984540054))
        results["folds"][fold_name] = {
            "garch_training_rows_contiguous": int(len(garch_training)),
            "omega": omega,
            "alpha": alpha,
            "beta": beta,
            "alpha_plus_beta": alpha + beta,
            "converged": bool(fitted.optimization_result.success),
            "coverage_80": coverage_80,
            "coverage_95": coverage_95,
            "mean_forecast_sigma_mw": float(np.mean(validation_sigma_mw)),
            "original_residual_diagnostics": original_diagnostics,
            "standardized_residual_diagnostics": standardized_diagnostics,
        }
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
        fold_output["garch_sigma_mw"] = validation_sigma_mw
        fold_output["standardized_residual"] = standardized
        output_parts.append(fold_output)

    results["summary"] = {
        "all_folds_converged": all(
            fold["converged"] for fold in results["folds"].values()
        ),
        "mean_80_coverage": float(
            np.mean([fold["coverage_80"] for fold in results["folds"].values()])
        ),
        "mean_95_coverage": float(
            np.mean([fold["coverage_95"] for fold in results["folds"].values()])
        ),
        "mean_alpha_plus_beta": float(
            np.mean([fold["alpha_plus_beta"] for fold in results["folds"].values()])
        ),
    }
    (OUT / "garch_diagnostics.json").write_text(json.dumps(results, indent=2) + "\n")
    pd.concat(output_parts, ignore_index=True).to_csv(
        OUT / "selected_model_garch_validation.csv", index=False
    )
    compact = {
        "summary": results["summary"],
        "folds": {
            name: {
                "alpha_plus_beta": fold["alpha_plus_beta"],
                "coverage_80": fold["coverage_80"],
                "coverage_95": fold["coverage_95"],
                "original_arch_p": fold["original_residual_diagnostics"]["arch_lm_48"]["p_value"],
                "standardized_arch_p": fold["standardized_residual_diagnostics"]["arch_lm_48"]["p_value"],
            }
            for name, fold in results["folds"].items()
        },
        "final_test_opened": False,
    }
    print(json.dumps(compact, indent=2))


if __name__ == "__main__":
    main()
