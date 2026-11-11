"""Rolling-origin evaluation of event-blind v2 regression candidates.

The January--March 2025 final test is removed immediately after loading and is
never scored by this script.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import sparse
from scipy.sparse.linalg import lsqr


ROOT = Path(__file__).resolve().parents[1]
CONFIG = json.loads((ROOT / "configs/event_blind_v2_experiment.json").read_text())
DATA_DIR = ROOT / "data/processed/event_blind_v2"
OUT = DATA_DIR / "modeling"
OUT.mkdir(parents=True, exist_ok=True)


@dataclass(frozen=True)
class Candidate:
    name: str
    feature_family: str
    target_scale: str
    alpha: float
    recent_days: int | None


RIDGE_ALPHAS = [0.0, 0.01, 0.1, 1.0]
CANDIDATES = [
    Candidate("calendar_weekly_v1", "v1", "level", 0.0, 730),
] + [
    Candidate(
        f"ridge_multilag_{target}_{window}_a{alpha:g}",
        "multilag",
        target,
        alpha,
        None if window == "expanding" else 730,
    )
    for target in ["level", "log"]
    for window in ["expanding", "recent730"]
    for alpha in RIDGE_ALPHAS
]


def load_v2_data(include_final_test: bool = False) -> pd.DataFrame:
    data = pd.read_csv(DATA_DIR / "demand_v2.csv")
    if not include_final_test:
        # Enforce the unopened boundary before constructing outcomes or metrics.
        data = data.loc[~data["is_final_test"]].copy()
    data["timestamp_utc"] = pd.to_datetime(data["timestamp_utc"], utc=True)
    data["timestamp_london"] = data["timestamp_utc"].dt.tz_convert(
        CONFIG["timezone"]
    )
    data = data.sort_values("timestamp_utc").reset_index(drop=True)
    for lag in CONFIG["fixed_safe_lags_half_hours"]:
        shifted_time = data["timestamp_utc"].shift(lag)
        aligned = data["timestamp_utc"].sub(shifted_time).eq(
            pd.Timedelta(minutes=30 * lag)
        )
        data[f"lag_{lag}"] = data["demand_mw"].shift(lag).where(aligned)
    daily_lags = [96, 144, 192, 240, 288, 336]
    weekly_lags = [336, 672, 1008, 1344]
    data["safe_daily_mean"] = data[[f"lag_{lag}" for lag in daily_lags]].mean(
        axis=1, skipna=False
    )
    data["safe_daily_std"] = data[[f"lag_{lag}" for lag in daily_lags]].std(
        axis=1, skipna=False
    )
    data["weekly_mean_4"] = data[[f"lag_{lag}" for lag in weekly_lags]].mean(
        axis=1, skipna=False
    )
    data["weekly_std_4"] = data[[f"lag_{lag}" for lag in weekly_lags]].std(
        axis=1, skipna=False
    )
    data["daily_change_2_to_3"] = data["lag_96"] - data["lag_144"]
    data["weekly_change_1_to_2"] = data["lag_336"] - data["lag_672"]
    return data


def load_development() -> pd.DataFrame:
    return load_v2_data(include_final_test=False)


def annual_phase(data: pd.DataFrame) -> np.ndarray:
    local = data["timestamp_london"]
    fractional_day = local.dt.hour / 24 + local.dt.minute / (24 * 60)
    fractional_year_day = local.dt.dayofyear - 1 + fractional_day
    return 2 * np.pi * fractional_year_day.to_numpy() / 365.2425


def design_matrix(data: pd.DataFrame, family: str) -> sparse.csr_matrix:
    n = len(data)
    rows = np.arange(n)
    slots = data["half_hour_of_week"].astype(int).to_numpy()
    if not ((slots >= 0) & (slots < 336)).all():
        raise ValueError("Invalid half-hour-of-week value")
    slot = sparse.csr_matrix((np.ones(n), (rows, slots)), shape=(n, 336))
    phase = annual_phase(data)
    slot_sine = sparse.csr_matrix(
        (np.sin(phase), (rows, slots)), shape=(n, 336)
    )
    slot_cosine = sparse.csr_matrix(
        (np.cos(phase), (rows, slots)), shape=(n, 336)
    )
    origin = pd.Timestamp(CONFIG["source_start_date"], tz="UTC")
    trend_years = (
        data["timestamp_utc"].sub(origin).dt.total_seconds().to_numpy()
        / (365.2425 * 24 * 3600)
    )
    holiday = data["is_bank_holiday_any_gb"].astype(float).to_numpy()

    if family == "v1":
        dense_values = np.column_stack(
            [trend_years, holiday, data["lag_336"].to_numpy() / 10_000]
        )
        return sparse.hstack(
            [slot, slot_sine, slot_cosine, sparse.csr_matrix(dense_values)],
            format="csr",
        )
    if family != "multilag":
        raise ValueError(f"Unknown feature family: {family}")

    lag_columns = [f"lag_{lag}" for lag in CONFIG["fixed_safe_lags_half_hours"]]
    summary_columns = [
        "safe_daily_mean",
        "safe_daily_std",
        "weekly_mean_4",
        "weekly_std_4",
        "daily_change_2_to_3",
        "weekly_change_1_to_2",
    ]
    continuous = [trend_years, holiday]
    continuous.extend(data[column].to_numpy() / 10_000 for column in lag_columns)
    continuous.extend(data[column].to_numpy() / 10_000 for column in summary_columns)
    # Additional global annual harmonics capture seasonal shapes that are not well
    # approximated by one sinusoid while retaining the slot-specific fundamental.
    for harmonic in range(2, 7):
        continuous.extend(
            [np.sin(harmonic * phase), np.cos(harmonic * phase)]
        )
    dense_values = np.column_stack(continuous)
    return sparse.hstack(
        [slot, slot_sine, slot_cosine, sparse.csr_matrix(dense_values)],
        format="csr",
    )


def required_available(data: pd.DataFrame, candidate: Candidate) -> pd.Series:
    required = data["demand_mw"].notna() & data["source_quality_eligible"]
    lags = [336] if candidate.feature_family == "v1" else CONFIG[
        "fixed_safe_lags_half_hours"
    ]
    for lag in lags:
        required &= data[f"lag_{lag}"].notna()
    return required


def fit_and_predict(
    training: pd.DataFrame,
    validation: pd.DataFrame,
    candidate: Candidate,
) -> tuple[np.ndarray, dict]:
    x_train = design_matrix(training, candidate.feature_family)
    x_validation = design_matrix(validation, candidate.feature_family)
    if candidate.target_scale == "level":
        target = training["demand_mw"].to_numpy(dtype=float) / 10_000
    elif candidate.target_scale == "log":
        target = np.log(training["demand_mw"].to_numpy(dtype=float))
    else:
        raise ValueError(candidate.target_scale)
    solution = lsqr(
        x_train,
        target,
        damp=np.sqrt(candidate.alpha),
        atol=1e-8,
        btol=1e-8,
        iter_lim=5_000,
    )
    fitted_train = np.asarray(x_train @ solution[0]).ravel()
    prediction = np.asarray(x_validation @ solution[0]).ravel()
    smearing_factor = 1.0
    if candidate.target_scale == "level":
        prediction = prediction * 10_000
    else:
        # Duan's training-only smearing correction approximately removes the
        # downward bias created when log predictions are exponentiated.
        smearing_factor = float(np.mean(np.exp(target - fitted_train)))
        prediction = np.exp(prediction) * smearing_factor
    metadata = {
        "training_rows": int(len(training)),
        "features": int(x_train.shape[1]),
        "lsqr_stop_code": int(solution[1]),
        "lsqr_iterations": int(solution[2]),
        "smearing_factor": smearing_factor,
    }
    return prediction, metadata


def metrics(actual: np.ndarray, forecast: np.ndarray) -> dict:
    error = actual - forecast
    return {
        "n": int(len(error)),
        "me_mw": float(np.mean(error)),
        "mae_mw": float(np.mean(np.abs(error))),
        "rmse_mw": float(np.sqrt(np.mean(error**2))),
    }


def main() -> None:
    data = load_development()
    results = {
        "selection_scope": "four development-only rolling-origin folds",
        "selection_metric": CONFIG["selection_metric"],
        "final_test_opened": False,
        "euro_2024_used_for_selection": False,
        "candidates": {},
        "benchmarks": {},
    }
    prediction_parts = []

    for fold in CONFIG["validation_folds"]:
        fold_name = fold["name"]
        validation_mask = data["settlement_date"].between(
            fold["validation_start"], fold["validation_end_inclusive"]
        ) & data["source_quality_eligible"]
        validation = data.loc[validation_mask].copy()
        actual = validation["demand_mw"].to_numpy(dtype=float)
        results["benchmarks"].setdefault("weekly_seasonal_naive", {})[fold_name] = metrics(
            actual, validation["lag_336"].to_numpy(dtype=float)
        )
        results["benchmarks"].setdefault("neso_day_ahead", {})[fold_name] = metrics(
            actual, validation["neso_day_ahead_forecast_mw"].to_numpy(dtype=float)
        )

        fold_predictions = validation[
            ["timestamp_utc", "settlement_date", "demand_mw"]
        ].copy()
        fold_predictions["fold"] = fold_name
        fold_predictions["weekly_seasonal_naive_mw"] = validation["lag_336"].to_numpy()
        fold_predictions["neso_day_ahead_forecast_mw"] = validation[
            "neso_day_ahead_forecast_mw"
        ].to_numpy()

        for candidate in CANDIDATES:
            training_end = pd.Timestamp(fold["train_end_inclusive"])
            training_start = pd.Timestamp(CONFIG["source_start_date"])
            if candidate.recent_days is not None:
                training_start = max(
                    training_start,
                    training_end - pd.Timedelta(days=candidate.recent_days - 1),
                )
            availability = required_available(data, candidate)
            training_mask = (
                data["settlement_date"].between(
                    training_start.strftime("%Y-%m-%d"),
                    fold["train_end_inclusive"],
                )
                & availability
            )
            validation_available = required_available(validation, candidate)
            if not validation_available.all():
                raise ValueError(
                    f"Missing validation features: {candidate.name}, {fold_name}"
                )
            training = data.loc[training_mask].copy()
            forecast, metadata = fit_and_predict(training, validation, candidate)
            fold_metrics = metrics(actual, forecast)
            results["candidates"].setdefault(
                candidate.name,
                {
                    "feature_family": candidate.feature_family,
                    "target_scale": candidate.target_scale,
                    "alpha": candidate.alpha,
                    "recent_days": candidate.recent_days,
                    "folds": {},
                },
            )["folds"][fold_name] = {**metadata, **fold_metrics}
            fold_predictions[f"forecast_{candidate.name}_mw"] = forecast
        prediction_parts.append(fold_predictions)

    for group in [results["benchmarks"], results["candidates"]]:
        for name, item in group.items():
            folds = item.get("folds", item)
            fold_metrics = [value for value in folds.values() if isinstance(value, dict)]
            if not fold_metrics:
                continue
            item["summary"] = {
                "mean_fold_mae_mw": float(np.mean([x["mae_mw"] for x in fold_metrics])),
                "mean_fold_rmse_mw": float(np.mean([x["rmse_mw"] for x in fold_metrics])),
                "mean_fold_absolute_bias_mw": float(
                    np.mean([abs(x["me_mw"]) for x in fold_metrics])
                ),
                "worst_fold_mae_mw": float(max(x["mae_mw"] for x in fold_metrics)),
            }

    selected = min(
        results["candidates"],
        key=lambda name: results["candidates"][name]["summary"]["mean_fold_mae_mw"],
    )
    results["best_regression_candidate"] = selected
    results["regression_stage_locked_before_dynamic_models"] = True
    (OUT / "regression_candidate_metrics.json").write_text(
        json.dumps(results, indent=2) + "\n"
    )
    pd.concat(prediction_parts, ignore_index=True).to_csv(
        OUT / "regression_validation_predictions.csv", index=False
    )

    compact = {
        "benchmarks": {
            name: item["summary"] for name, item in results["benchmarks"].items()
        },
        "top_candidates": sorted(
            (
                (name, item["summary"])
                for name, item in results["candidates"].items()
            ),
            key=lambda pair: pair[1]["mean_fold_mae_mw"],
        )[:8],
        "best_regression_candidate": selected,
        "final_test_opened": False,
    }
    print(json.dumps(compact, indent=2))


if __name__ == "__main__":
    main()
