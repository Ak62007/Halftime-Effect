"""One-time evaluation of the locked event-blind v3 model on Jan--Mar 2026."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor

from diagnose_v2_garch import residual_diagnostics
from evaluate_v2_direct_residual_candidates import cutoff_features, direct_design, fit_ridge
from evaluate_v2_regression_candidates import (
    CANDIDATES as V2_CANDIDATES,
    fit_and_predict as fit_v2,
)
from evaluate_v3_dynamic_candidates import v3_direct_design
from evaluate_v3_nonlinear_candidates import fit_spline
from evaluate_v3_ridge_ablation import OUT, load_v3_data, metrics, required_available
from diagnose_v3_variance import variance_design


ROOT = Path(__file__).resolve().parents[1]
LOCK = json.loads((ROOT / "configs/event_blind_v3_model_lock.json").read_text())
LOCK_COMMIT = "adc6f74"
V2_BASE = next(
    candidate
    for candidate in V2_CANDIDATES
    if candidate.name == "ridge_multilag_level_recent730_a0.1"
)


def main() -> None:
    data = load_v3_data(include_final_test=True)
    final_mask = data["settlement_date"].between(
        LOCK["final_test_start"], LOCK["final_test_end_inclusive"]
    )
    if int(final_mask.sum()) != 4_318:
        raise ValueError("Unexpected v3 final-test row count")
    available = required_available(data)
    training_end = pd.Timestamp(LOCK["final_training_end_inclusive"])
    recent_days = LOCK["research_point_forecast"]["training_window_days"]
    training_start = training_end - pd.Timedelta(days=recent_days - 1)
    train = data["settlement_date"].between(
        training_start.strftime("%Y-%m-%d"), LOCK["final_training_end_inclusive"]
    ) & available
    modeled_mask = available & data["settlement_date"].between(
        training_start.strftime("%Y-%m-%d"), LOCK["final_test_end_inclusive"]
    )
    training = data.loc[train].copy()
    modeled = data.loc[modeled_mask].copy().reset_index(drop=True)

    base_forecast, base_metadata = fit_spline(
        training, modeled, LOCK["research_point_forecast"]["base_alpha"]
    )
    modeled["base_forecast_mw"] = base_forecast
    modeled["base_residual_mw"] = modeled["demand_mw"] - base_forecast
    modeled = cutoff_features(modeled)
    x_all = v3_direct_design(modeled)
    complete = np.isfinite(x_all).all(axis=1)
    train_dynamic = (
        modeled["settlement_date"].le(LOCK["final_training_end_inclusive"]).to_numpy()
        & complete
    )
    direct_target = modeled.loc[train_dynamic, "base_residual_mw"].to_numpy() / 1_000
    ridge_coefficients = fit_ridge(
        x_all[train_dynamic],
        direct_target,
        LOCK["research_point_forecast"]["direct_ridge_alpha"],
    )
    ridge_correction = np.full(len(modeled), np.nan)
    ridge_correction[complete] = (x_all[complete] @ ridge_coefficients) * 1_000
    hgb_parameters = LOCK["research_point_forecast"]["direct_hgb_parameters"].copy()
    hgb = HistGradientBoostingRegressor(**hgb_parameters)
    hgb.fit(x_all[train_dynamic], direct_target)
    hgb_correction = np.full(len(modeled), np.nan)
    hgb_correction[complete] = hgb.predict(x_all[complete]) * 1_000
    modeled["direct_ridge_forecast_mw"] = base_forecast + ridge_correction
    modeled["direct_hgb_forecast_mw"] = base_forecast + hgb_correction
    modeled["v3_forecast_mw"] = (
        LOCK["research_point_forecast"]["ridge_blend_weight"]
        * modeled["direct_ridge_forecast_mw"]
        + LOCK["research_point_forecast"]["hgb_blend_weight"]
        * modeled["direct_hgb_forecast_mw"]
    )
    modeled["v3_residual_mw"] = modeled["demand_mw"] - modeled["v3_forecast_mw"]
    modeled_final = modeled["settlement_date"].between(
        LOCK["final_test_start"], LOCK["final_test_end_inclusive"]
    )
    if not complete[modeled_final.to_numpy()].all():
        raise ValueError("Incomplete locked v3 features in final test")

    # Refit the locked v2 comparator over the same 730-day information window.
    v2_training = data.loc[train].copy()
    v2_base_forecast, _ = fit_v2(v2_training, modeled, V2_BASE)
    v2_modeled = modeled.copy()
    v2_modeled["base_forecast_mw"] = v2_base_forecast
    v2_modeled["base_residual_mw"] = v2_modeled["demand_mw"] - v2_base_forecast
    v2_modeled = cutoff_features(v2_modeled)
    v2_x = direct_design(v2_modeled)
    v2_complete = np.isfinite(v2_x).all(axis=1)
    v2_train = (
        v2_modeled["settlement_date"].le(LOCK["final_training_end_inclusive"]).to_numpy()
        & v2_complete
    )
    v2_coefficients = fit_ridge(
        v2_x[v2_train],
        v2_modeled.loc[v2_train, "base_residual_mw"].to_numpy() / 1_000,
        0.0,
    )
    v2_correction = np.full(len(v2_modeled), np.nan)
    v2_correction[v2_complete] = (v2_x[v2_complete] @ v2_coefficients) * 1_000
    modeled["v2_forecast_mw"] = v2_base_forecast + v2_correction

    # Locked structured variance scale and fixed development calibration constants.
    variance_x = variance_design(
        modeled,
        np.where(np.isfinite(modeled["v3_forecast_mw"]), modeled["v3_forecast_mw"], base_forecast),
    )
    variance_parameters = LOCK["interval_model"]["scale_model_parameters"].copy()
    variance_model = HistGradientBoostingRegressor(**variance_parameters)
    training_residual = modeled.loc[train_dynamic, "v3_residual_mw"].to_numpy()
    variance_model.fit(
        variance_x[train_dynamic], np.log(training_residual**2 + 100.0**2)
    )
    raw_train_variance = np.exp(variance_model.predict(variance_x[train_dynamic]))
    variance_scale = float(
        np.sqrt(np.mean(training_residual**2 / raw_train_variance))
    )
    sigma = (
        np.sqrt(np.exp(variance_model.predict(variance_x[modeled_final.to_numpy()])))
        * variance_scale
    )

    evaluation = modeled.loc[modeled_final].copy()
    evaluation["structured_sigma_mw"] = sigma
    evaluation["standardized_residual"] = evaluation["v3_residual_mw"] / sigma
    actual = evaluation["demand_mw"].to_numpy(dtype=float)
    neso_available = evaluation["neso_available_at_cutoff"].to_numpy(dtype=bool)
    point_metrics = {
        "weekly_seasonal_naive": metrics(actual, evaluation["lag_336"].to_numpy()),
        "v2_locked_spec_refit": metrics(actual, evaluation["v2_forecast_mw"].to_numpy()),
        "v3_spline_base": metrics(actual, evaluation["base_forecast_mw"].to_numpy()),
        "v3_direct_ridge": metrics(
            actual, evaluation["direct_ridge_forecast_mw"].to_numpy()
        ),
        "v3_direct_hgb": metrics(
            actual, evaluation["direct_hgb_forecast_mw"].to_numpy()
        ),
        "v3_locked": metrics(actual, evaluation["v3_forecast_mw"].to_numpy()),
        "neso_day_ahead_available_rows": metrics(
            actual[neso_available],
            evaluation.loc[neso_available, "neso_day_ahead_forecast_mw"].to_numpy(),
        ),
    }
    common_available_metrics = {
        "v2": metrics(
            actual[neso_available],
            evaluation.loc[neso_available, "v2_forecast_mw"].to_numpy(),
        ),
        "v3": metrics(
            actual[neso_available],
            evaluation.loc[neso_available, "v3_forecast_mw"].to_numpy(),
        ),
        "neso": metrics(
            actual[neso_available],
            evaluation.loc[neso_available, "neso_day_ahead_forecast_mw"].to_numpy(),
        ),
    }
    q80 = LOCK["interval_model"]["locked_central_80_critical_value"]
    q95 = LOCK["interval_model"]["locked_central_95_critical_value"]
    absolute_standardized = np.abs(evaluation["standardized_residual"].to_numpy())
    interval_metrics = {
        "coverage_80": float(np.mean(absolute_standardized <= q80)),
        "coverage_95": float(np.mean(absolute_standardized <= q95)),
        "mean_80_interval_width_mw": float(np.mean(2 * q80 * sigma)),
        "mean_95_interval_width_mw": float(np.mean(2 * q95 * sigma)),
        "mean_sigma_mw": float(np.mean(sigma)),
        "variance_training_scale": variance_scale,
    }
    month_metrics = {}
    for month, subset in evaluation.groupby(evaluation["timestamp_london"].dt.month):
        available_month = subset["neso_available_at_cutoff"].to_numpy(dtype=bool)
        month_metrics[str(month)] = {
            "v2": metrics(
                subset["demand_mw"].to_numpy(), subset["v2_forecast_mw"].to_numpy()
            ),
            "v3": metrics(
                subset["demand_mw"].to_numpy(), subset["v3_forecast_mw"].to_numpy()
            ),
            "neso_available_rows": metrics(
                subset.loc[available_month, "demand_mw"].to_numpy(),
                subset.loc[available_month, "neso_day_ahead_forecast_mw"].to_numpy(),
            ),
        }
    result = {
        "evaluation_status": f"Jan-Mar 2026 final test opened after lock commit {LOCK_COMMIT}",
        "lock_file": "configs/event_blind_v3_model_lock.json",
        "model_changed_after_opening": False,
        "n": int(len(evaluation)),
        "date_range": [evaluation["settlement_date"].min(), evaluation["settlement_date"].max()],
        "neso_available_rows": int(neso_available.sum()),
        "neso_unavailable_dates": sorted(
            evaluation.loc[~neso_available, "settlement_date"].unique().tolist()
        ),
        "training_rows": int(len(training)),
        "base_fit_metadata": base_metadata,
        "point_metrics": point_metrics,
        "common_neso_available_metrics": common_available_metrics,
        "month_metrics": month_metrics,
        "interval_metrics": interval_metrics,
        "residual_diagnostics": residual_diagnostics(
            evaluation["v3_residual_mw"].to_numpy()
        ),
        "standardized_residual_diagnostics": residual_diagnostics(
            evaluation["standardized_residual"].to_numpy()
        ),
    }
    (OUT / "final_test_evaluation.json").write_text(json.dumps(result, indent=2) + "\n")
    columns = [
        "timestamp_utc",
        "timestamp_london",
        "settlement_date",
        "demand_mw",
        "lag_336",
        "neso_day_ahead_forecast_mw",
        "neso_available_at_cutoff",
        "v2_forecast_mw",
        "base_forecast_mw",
        "direct_ridge_forecast_mw",
        "direct_hgb_forecast_mw",
        "v3_forecast_mw",
        "v3_residual_mw",
        "structured_sigma_mw",
        "standardized_residual",
    ]
    evaluation[columns].to_csv(OUT / "final_test_predictions.csv", index=False)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
