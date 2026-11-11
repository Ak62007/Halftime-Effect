"""Evaluate the presentation-facing syllabus-aligned forecasting models.

Models are intentionally limited to:
1. weekly seasonal naive;
2. Fourier seasonal regression with ARMA(2,1) errors;
3. the same forecast plus scheduled-match and halftime indicators.
"""
from __future__ import annotations

import json
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from statsmodels.stats.diagnostic import het_arch
from statsmodels.tsa.arima.model import ARIMA


ROOT = Path(__file__).resolve().parents[1]
CONFIG = json.loads((ROOT / "configs/syllabus_aligned_experiment.json").read_text())
DATA = ROOT / "data/processed/syllabus_aligned/demand_source.csv"
EVENTS = ROOT / "data/processed/match_aware/demand_extended.csv"
OUT = ROOT / "data/processed/syllabus_aligned"
OUT.mkdir(parents=True, exist_ok=True)


def load_data() -> pd.DataFrame:
    data = pd.read_csv(DATA)
    data["timestamp_utc"] = pd.to_datetime(data["timestamp_utc"], utc=True)
    data["timestamp_london"] = data["timestamp_utc"].dt.tz_convert(CONFIG["timezone"])
    data["interval_end_utc"] = pd.to_datetime(data["interval_end_utc"], utc=True)
    data["forecast_cutoff_utc"] = pd.to_datetime(data["forecast_cutoff_utc"], utc=True)
    event_columns = [
        "timestamp_utc",
        "match_id",
        "opponent",
        "competition",
        "event_role",
        "is_tournament_match",
        "minutes_from_scheduled_kickoff",
        "scheduled_match_overlap_fraction",
        "halftime_proxy_overlap_fraction",
    ]
    events = pd.read_csv(EVENTS, usecols=event_columns)
    events["timestamp_utc"] = pd.to_datetime(events["timestamp_utc"], utc=True)
    data = data.merge(events, on="timestamp_utc", how="left", validate="one_to_one")
    data["is_tournament_match"] = data["is_tournament_match"].fillna(False).astype(bool)
    data["is_england_match_day"] = data["match_id"].notna()
    data = data.sort_values("timestamp_utc").reset_index(drop=True)
    shifted = data["timestamp_utc"].shift(336)
    aligned = data["timestamp_utc"].sub(shifted).eq(pd.Timedelta(hours=168))
    data["weekly_naive_mw"] = data["demand_mw"].shift(336).where(aligned)
    return data


def regression_design(data: pd.DataFrame) -> tuple[np.ndarray, list[str]]:
    local = data["timestamp_london"]
    half_hours = (
        local.dt.dayofweek.to_numpy() * 48
        + local.dt.hour.to_numpy() * 2
        + local.dt.minute.to_numpy() / 30
    )
    weekly_phase = 2 * np.pi * half_hours / 336
    fractional_day = local.dt.hour / 24 + local.dt.minute / (24 * 60)
    annual_phase = 2 * np.pi * (
        local.dt.dayofyear.to_numpy() - 1 + fractional_day.to_numpy()
    ) / 365.2425
    origin = pd.Timestamp("2021-04-01", tz="UTC")
    trend = (
        data["timestamp_utc"].sub(origin).dt.total_seconds().to_numpy()
        / (365.2425 * 24 * 3600)
    )
    columns = [np.ones(len(data)), trend]
    names = ["intercept", "trend_years"]
    for harmonic in range(1, CONFIG["weekly_fourier_order"] + 1):
        columns.extend(
            [np.sin(harmonic * weekly_phase), np.cos(harmonic * weekly_phase)]
        )
        names.extend([f"weekly_sin_{harmonic}", f"weekly_cos_{harmonic}"])
    for harmonic in range(1, CONFIG["annual_fourier_order"] + 1):
        columns.extend(
            [np.sin(harmonic * annual_phase), np.cos(harmonic * annual_phase)]
        )
        names.extend([f"annual_sin_{harmonic}", f"annual_cos_{harmonic}"])
    exogenous = [
        ("is_bank_holiday_any_gb", 1.0),
        ("is_day_before_bank_holiday", 1.0),
        ("is_day_after_bank_holiday", 1.0),
        ("temperature_forecast_gb_c", 20.0),
        ("heating_degree_forecast", 20.0),
        ("cooling_degree_forecast", 20.0),
        ("embedded_wind_forecast_mw", 10_000.0),
        ("embedded_solar_forecast_mw", 10_000.0),
    ]
    for name, scale in exogenous:
        columns.append(data[name].astype(float).to_numpy() / scale)
        names.append(name)
    matrix = np.column_stack(columns)
    if not np.isfinite(matrix).all():
        raise ValueError("Fourier regression design contains missing values")
    return matrix, names


def metrics(actual: np.ndarray, forecast: np.ndarray) -> dict:
    error = actual - forecast
    return {
        "n": int(len(error)),
        "mean_error_mw": float(np.mean(error)),
        "mae_mw": float(np.mean(np.abs(error))),
        "rmse_mw": float(np.sqrt(np.mean(error**2))),
    }


def fit_fourier_arma(
    data: pd.DataFrame, training_end: str
) -> tuple[np.ndarray, np.ndarray, np.ndarray, dict]:
    x, names = regression_design(data)
    eligible = (
        data["settlement_date"].le(training_end)
        & data["source_quality_eligible"]
        & data["demand_mw"].notna()
        & ~data["is_tournament_match"]
    ).to_numpy()
    y_scaled = data.loc[eligible, "demand_mw"].to_numpy(dtype=float) / 10_000
    beta, *_ = np.linalg.lstsq(x[eligible], y_scaled, rcond=None)
    regression_forecast = (x @ beta) * 10_000
    residual = data["demand_mw"].to_numpy(dtype=float) - regression_forecast
    arma_training = residual[
        data["settlement_date"].le(training_end).to_numpy()
        & data["source_quality_eligible"].to_numpy(dtype=bool)
        & np.isfinite(residual)
    ]
    order = tuple(CONFIG["arma_order"])
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        arma = ARIMA(arma_training, order=order, trend="n").fit(
            method_kwargs={"maxiter": 100}
        )
    metadata = {
        "training_end": training_end,
        "regression_training_rows": int(eligible.sum()),
        "regression_features": names,
        "arma_order": list(order),
        "arma_parameters": [float(value) for value in arma.params],
        "arma_converged": bool(arma.mle_retvals.get("converged", False)),
        "arma_aic": float(arma.aic),
    }
    return regression_forecast, residual, arma.params, metadata


def arma_day_ahead_correction(
    data: pd.DataFrame,
    residual: np.ndarray,
    arma_parameters: np.ndarray,
    target_mask: pd.Series,
) -> np.ndarray:
    correction = np.full(len(data), np.nan)
    order = tuple(CONFIG["arma_order"])
    target = data.loc[target_mask].copy()
    for _, rows in target.groupby("settlement_date"):
        positions = rows.index.to_numpy(dtype=int)
        cutoff = rows["forecast_cutoff_utc"].iloc[0]
        known = np.flatnonzero(
            (data["interval_end_utc"] <= cutoff).to_numpy()
            & np.isfinite(residual)
            & data["source_quality_eligible"].to_numpy(dtype=bool)
        )
        if len(known) < 336:
            raise ValueError("Insufficient residual history at forecast cutoff")
        known_end = known[-1]
        history = residual[known[-min(len(known), 1_344) : known_end + 1]]
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            filtered = ARIMA(history, order=order, trend="n").filter(arma_parameters)
        steps = int(positions.max() - known_end)
        forecast = np.asarray(filtered.forecast(steps=steps), dtype=float)
        correction[positions] = forecast[positions - known_end - 1]
    return correction


def forecast_period(
    data: pd.DataFrame, training_end: str, start: str, end: str
) -> tuple[pd.DataFrame, dict]:
    regression, residual, parameters, metadata = fit_fourier_arma(data, training_end)
    target = (
        data["settlement_date"].between(start, end)
        & data["source_quality_eligible"]
        & data["demand_mw"].notna()
    )
    correction = arma_day_ahead_correction(data, residual, parameters, target)
    output = data.loc[target].copy()
    output["fourier_regression_forecast_mw"] = regression[target.to_numpy()]
    output["arma_error_correction_mw"] = correction[target.to_numpy()]
    output["fourier_arma_forecast_mw"] = (
        output["fourier_regression_forecast_mw"]
        + output["arma_error_correction_mw"]
    )
    if output["fourier_arma_forecast_mw"].isna().any():
        raise ValueError("Missing syllabus-aligned forecasts")
    return output, metadata


def historical_tournament_forecasts(data: pd.DataFrame) -> pd.DataFrame:
    editions = {
        "FIFA World Cup 2022": ("2022-11-19", "2022-11-21", "2022-12-10"),
    }
    pieces = []
    for edition, (training_end, start, end) in editions.items():
        forecast, _ = forecast_period(data, training_end, start, end)
        rows = forecast.loc[
            forecast["is_tournament_match"]
            & forecast["competition"].fillna("").str.contains(
                "World Cup 2022", case=False, regex=False
            )
        ].copy()
        rows["tournament_edition"] = edition
        pieces.append(rows)
    result = pd.concat(pieces, ignore_index=True)
    if result["match_id"].nunique() != 5:
        raise ValueError("Expected five World Cup 2022 training matches")
    return result


def fit_match_flags(historical: pd.DataFrame) -> tuple[np.ndarray, dict]:
    score = historical[
        "scheduled_match_overlap_fraction"
    ].gt(0)
    rows = historical.loc[score].copy()
    x = rows[
        ["scheduled_match_overlap_fraction", "halftime_proxy_overlap_fraction"]
    ].to_numpy(dtype=float)
    residual = (
        rows["demand_mw"] - rows["fourier_regression_forecast_mw"]
    ).to_numpy(dtype=float)
    beta, *_ = np.linalg.lstsq(x, residual, rcond=None)
    return beta, {
        "historical_matches": int(rows["match_id"].nunique()),
        "scheduled_match_coefficient_mw": float(beta[0]),
        "halftime_additional_coefficient_mw": float(beta[1]),
        "status": "exploratory because only five usable historical tournament matches are available; EURO 2020 lacks enough pre-event history for annual Fourier estimation",
    }


def main() -> None:
    data = load_data()
    validation, validation_fit = forecast_period(
        data,
        CONFIG["development_training_end"],
        CONFIG["ordinary_validation_start"],
        CONFIG["ordinary_validation_end"],
    )
    ordinary = validation.loc[~validation["is_england_match_day"]].copy()
    validation_metrics = {
        "weekly_seasonal_naive": metrics(
            ordinary["demand_mw"].to_numpy(), ordinary["weekly_naive_mw"].to_numpy()
        ),
        "fourier_regression": metrics(
            ordinary["demand_mw"].to_numpy(),
            ordinary["fourier_regression_forecast_mw"].to_numpy(),
        ),
        "fourier_regression_with_arma_errors": metrics(
            ordinary["demand_mw"].to_numpy(),
            ordinary["fourier_arma_forecast_mw"].to_numpy(),
        ),
        "neso_day_ahead": metrics(
            ordinary["demand_mw"].to_numpy(),
            ordinary["neso_day_ahead_forecast_mw"].to_numpy(),
        ),
    }

    historical = historical_tournament_forecasts(data)
    match_beta, match_fit = fit_match_flags(historical)
    euro, euro_fit = forecast_period(
        data,
        CONFIG["euro_2024_training_end"],
        CONFIG["euro_2024_start"],
        CONFIG["euro_2024_end"],
    )
    euro = euro.loc[euro["event_role"].eq("event_holdout")].copy()
    euro["match_correction_mw"] = (
        euro["scheduled_match_overlap_fraction"].to_numpy(dtype=float) * match_beta[0]
        + euro["halftime_proxy_overlap_fraction"].to_numpy(dtype=float) * match_beta[1]
    )
    euro["match_aware_forecast_mw"] = (
        euro["fourier_regression_forecast_mw"] + euro["match_correction_mw"]
    )
    event_window = euro["scheduled_match_overlap_fraction"].gt(0)
    halftime = euro["halftime_proxy_overlap_fraction"].gt(0)
    euro_metrics = {}
    for name, mask in {"scheduled_match": event_window, "halftime_proxy": halftime}.items():
        rows = euro.loc[mask]
        actual = rows["demand_mw"].to_numpy(dtype=float)
        euro_metrics[name] = {
            "weekly_seasonal_naive": metrics(actual, rows["weekly_naive_mw"].to_numpy()),
            "event_blind_fourier_regression": metrics(
                actual, rows["fourier_regression_forecast_mw"].to_numpy()
            ),
            "exploratory_match_aware": metrics(
                actual, rows["match_aware_forecast_mw"].to_numpy()
            ),
            "neso_day_ahead": metrics(
                actual, rows["neso_day_ahead_forecast_mw"].to_numpy()
            ),
        }

    residual = (
        ordinary["demand_mw"] - ordinary["fourier_regression_forecast_mw"]
    ).to_numpy(dtype=float)
    arch_lm, arch_pvalue, _, _ = het_arch(residual, nlags=48)
    result = {
        "approved_model_scope": CONFIG["approved_models"],
        "ordinary_validation": {
            "dates": [CONFIG["ordinary_validation_start"], CONFIG["ordinary_validation_end"]],
            "fit": validation_fit,
            "metrics": validation_metrics,
            "selected_model": "Fourier seasonal regression; ARMA(2,1) rejected because validation MAE was slightly worse",
        },
        "historical_match_flag_fit": match_fit,
        "euro_2024": {
            "status": "previously opened; retrospective syllabus-aligned comparison",
            "fit": euro_fit,
            "matches": int(euro["match_id"].nunique()),
            "metrics": euro_metrics,
        },
        "arch_lm_48": {"statistic": float(arch_lm), "p_value": float(arch_pvalue)},
        "garch_fitted": False,
        "garch_decision": "ARCH is diagnosed, but GARCH is omitted from the presentation model because it does not change the point forecast and prior fits produced under-covered intervals.",
    }
    (OUT / "results.json").write_text(json.dumps(result, indent=2) + "\n")
    ordinary.to_csv(OUT / "ordinary_validation_predictions.csv", index=False)
    historical.to_csv(OUT / "historical_tournament_predictions.csv", index=False)
    euro.to_csv(OUT / "euro_2024_predictions.csv", index=False)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
