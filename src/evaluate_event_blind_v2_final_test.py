"""One-time evaluation of the locked event-blind v2 model on Jan--Mar 2025."""
from __future__ import annotations

import json
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from arch import arch_model

from diagnose_v2_garch import (
    garch_variance_forecasts,
    longest_contiguous,
    residual_diagnostics,
)
from evaluate_v2_direct_residual_candidates import cutoff_features, direct_design, fit_ridge
from evaluate_v2_regression_candidates import (
    CANDIDATES,
    OUT,
    fit_and_predict,
    load_v2_data,
    metrics,
    required_available,
)


ROOT = Path(__file__).resolve().parents[1]
LOCK = json.loads((ROOT / "configs/event_blind_v2_model_lock.json").read_text())
BASE_SPEC = next(
    candidate
    for candidate in CANDIDATES
    if candidate.name == LOCK["point_forecast"]["base_model"]
)
V1_SPEC = next(candidate for candidate in CANDIDATES if candidate.name == "calendar_weekly_v1")


def main() -> None:
    data = load_v2_data(include_final_test=True)
    data["interval_end_utc"] = pd.to_datetime(data["interval_end_utc"], utc=True)
    data["forecast_cutoff_utc"] = pd.to_datetime(data["forecast_cutoff_utc"], utc=True)
    final_mask = data["settlement_date"].between(
        LOCK["final_test_start"], LOCK["final_test_end_inclusive"]
    )
    if int(final_mask.sum()) != 4_318:
        raise ValueError("Unexpected final-test row count")

    training_end = pd.Timestamp(LOCK["final_training_end_inclusive"])
    training_start = training_end - pd.Timedelta(
        days=LOCK["point_forecast"]["training_window_days"] - 1
    )
    available = required_available(data, BASE_SPEC)
    training_mask = data["settlement_date"].between(
        training_start.strftime("%Y-%m-%d"),
        LOCK["final_training_end_inclusive"],
    ) & available
    modeled_mask = available & data["settlement_date"].between(
        training_start.strftime("%Y-%m-%d"), LOCK["final_test_end_inclusive"]
    )
    training = data.loc[training_mask].copy()
    modeled = data.loc[modeled_mask].copy().reset_index(drop=True)

    base_prediction, base_metadata = fit_and_predict(training, modeled, BASE_SPEC)
    modeled["base_forecast_mw"] = base_prediction
    modeled["base_residual_mw"] = modeled["demand_mw"] - base_prediction
    modeled = cutoff_features(modeled)
    x_all = direct_design(modeled)
    complete = np.isfinite(x_all).all(axis=1)
    direct_training = (
        modeled["settlement_date"].le(LOCK["final_training_end_inclusive"]).to_numpy()
        & complete
    )
    direct_coefficients = fit_ridge(
        x_all[direct_training],
        modeled.loc[direct_training, "base_residual_mw"].to_numpy() / 1_000,
        LOCK["point_forecast"]["direct_residual_alpha"],
    )
    direct_correction = np.full(len(modeled), np.nan)
    direct_correction[complete] = (x_all[complete] @ direct_coefficients) * 1_000
    modeled["v2_forecast_mw"] = modeled["base_forecast_mw"] + direct_correction
    modeled["v2_residual_mw"] = modeled["demand_mw"] - modeled["v2_forecast_mw"]
    modeled_final = modeled["settlement_date"].between(
        LOCK["final_test_start"], LOCK["final_test_end_inclusive"]
    )
    if not complete[modeled_final.to_numpy()].all():
        raise ValueError("Incomplete locked-model features in final test")

    # Refit the frozen v1 comparator on the identical recent window.
    v1_available = required_available(data, V1_SPEC)
    v1_training = data.loc[
        data["settlement_date"].between(
            training_start.strftime("%Y-%m-%d"),
            LOCK["final_training_end_inclusive"],
        )
        & v1_available
    ].copy()
    final_data = data.loc[final_mask & v1_available].copy()
    v1_prediction, v1_metadata = fit_and_predict(v1_training, final_data, V1_SPEC)

    evaluation = modeled.loc[modeled_final].copy()
    evaluation = evaluation.merge(
        final_data[["timestamp_utc"]].assign(v1_forecast_mw=v1_prediction),
        on="timestamp_utc",
        how="left",
        validate="one_to_one",
    )
    actual = evaluation["demand_mw"].to_numpy(dtype=float)
    point_metrics = {
        "weekly_seasonal_naive": metrics(actual, evaluation["lag_336"].to_numpy()),
        "v1_calendar_weekly_lag": metrics(actual, evaluation["v1_forecast_mw"].to_numpy()),
        "v2_locked": metrics(actual, evaluation["v2_forecast_mw"].to_numpy()),
        "neso_day_ahead": metrics(
            actual, evaluation["neso_day_ahead_forecast_mw"].to_numpy()
        ),
    }

    # Frozen GARCH(1,1) variance layer.
    garch_training = modeled.loc[
        direct_training,
        ["timestamp_utc", "v2_residual_mw"],
    ].rename(columns={"v2_residual_mw": "selected_residual_mw"}).dropna()
    garch_training = longest_contiguous(garch_training)
    scaled_training = garch_training["selected_residual_mw"].to_numpy() / 1_000
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        fitted_garch = arch_model(
            scaled_training,
            mean="Zero",
            vol="GARCH",
            p=1,
            q=1,
            dist="normal",
            rescale=False,
        ).fit(disp="off", show_warning=False)
    params = fitted_garch.params
    modeled_for_variance = modeled.rename(
        columns={"v2_residual_mw": "selected_residual_mw"}
    )
    variance = garch_variance_forecasts(
        modeled_for_variance,
        modeled_final,
        LOCK["final_training_end_inclusive"],
        float(params["omega"]),
        float(params["alpha[1]"]),
        float(params["beta[1]"]),
        float(fitted_garch.conditional_volatility[-1] ** 2),
    )
    sigma = np.sqrt(variance[modeled_final.to_numpy()]) * 1_000
    evaluation["garch_sigma_mw"] = sigma
    evaluation["standardized_residual"] = evaluation["v2_residual_mw"] / sigma
    coverage_80 = float(np.mean(np.abs(evaluation["standardized_residual"]) <= 1.2815515655446004))
    coverage_95 = float(np.mean(np.abs(evaluation["standardized_residual"]) <= 1.959963984540054))

    month_metrics = {}
    for month, subset in evaluation.groupby(evaluation["timestamp_london"].dt.month):
        month_metrics[str(month)] = {
            "v1": metrics(
                subset["demand_mw"].to_numpy(), subset["v1_forecast_mw"].to_numpy()
            ),
            "v2": metrics(
                subset["demand_mw"].to_numpy(), subset["v2_forecast_mw"].to_numpy()
            ),
            "neso": metrics(
                subset["demand_mw"].to_numpy(),
                subset["neso_day_ahead_forecast_mw"].to_numpy(),
            ),
        }

    final_result = {
        "evaluation_status": "Jan-Mar 2025 final test opened after commit 0c3d4b9",
        "lock_file": "configs/event_blind_v2_model_lock.json",
        "model_changed_after_opening": False,
        "n": int(len(evaluation)),
        "date_range": [
            evaluation["settlement_date"].min(),
            evaluation["settlement_date"].max(),
        ],
        "training_rows": int(len(training)),
        "base_fit_metadata": base_metadata,
        "v1_fit_metadata": v1_metadata,
        "point_metrics": point_metrics,
        "month_metrics": month_metrics,
        "residual_diagnostics": residual_diagnostics(
            evaluation["v2_residual_mw"].to_numpy()
        ),
        "standardized_residual_diagnostics": residual_diagnostics(
            evaluation["standardized_residual"].to_numpy()
        ),
        "garch": {
            "converged": bool(fitted_garch.optimization_result.success),
            "omega": float(params["omega"]),
            "alpha": float(params["alpha[1]"]),
            "beta": float(params["beta[1]"]),
            "alpha_plus_beta": float(params["alpha[1]"] + params["beta[1]"]),
            "coverage_80": coverage_80,
            "coverage_95": coverage_95,
            "mean_sigma_mw": float(np.mean(sigma)),
        },
    }
    (OUT / "final_test_evaluation.json").write_text(
        json.dumps(final_result, indent=2) + "\n"
    )
    output_columns = [
        "timestamp_utc",
        "timestamp_london",
        "settlement_date",
        "demand_mw",
        "lag_336",
        "neso_day_ahead_forecast_mw",
        "v1_forecast_mw",
        "base_forecast_mw",
        "v2_forecast_mw",
        "v2_residual_mw",
        "garch_sigma_mw",
        "standardized_residual",
    ]
    evaluation[output_columns].to_csv(OUT / "final_test_predictions.csv", index=False)
    print(json.dumps(final_result, indent=2))


if __name__ == "__main__":
    main()
