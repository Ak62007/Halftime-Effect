"""Select a small schedule-aware correction with leave-one-match-out validation.

This stage uses only the 23 primary historical fixtures from 2022--2023. The two
March 2024 validation matches and Euro 2024 holdout are deliberately not read.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from fit_event_blind_models import MODEL_SPECS, design_matrix, load_data


ROOT = Path(__file__).resolve().parents[1]
MODEL_DIR = ROOT / "data/processed/match_aware/modeling"
MODEL_DIR.mkdir(parents=True, exist_ok=True)


@dataclass(frozen=True)
class CorrectionSpec:
    name: str
    features: tuple[str, ...]


# Locked before historical match residuals are inspected.
CORRECTION_SPECS = [
    CorrectionSpec("scheduled_match_only", ("scheduled_match_overlap_fraction",)),
    CorrectionSpec(
        "match_plus_halftime",
        ("scheduled_match_overlap_fraction", "halftime_proxy_overlap_fraction"),
    ),
    CorrectionSpec(
        "four_window",
        (
            "pregame_overlap_fraction",
            "scheduled_match_overlap_fraction",
            "halftime_proxy_overlap_fraction",
            "postmatch_overlap_fraction",
        ),
    ),
]

CONTEXT_START_MINUTES = -240
CONTEXT_END_MINUTES = 285


def selected_event_blind_predictions(data: pd.DataFrame) -> tuple[np.ndarray, str]:
    event_blind_metrics = json.loads(
        (MODEL_DIR / "event_blind_metrics.json").read_text()
    )
    selected_name = event_blind_metrics["selected_model"]
    selected_spec = next(spec for spec in MODEL_SPECS if spec.name == selected_name)
    coefficients = np.load(MODEL_DIR / "coefficients" / f"{selected_name}.npy")
    return np.asarray(design_matrix(data, selected_spec) @ coefficients).ravel(), selected_name


def primary_match_context() -> tuple[pd.DataFrame, str]:
    data = load_data()
    forecasts, selected_name = selected_event_blind_predictions(data)
    data["event_blind_forecast_mw"] = forecasts
    data["event_blind_residual_mw"] = (
        data["demand_mw"] - data["event_blind_forecast_mw"]
    )
    context = data.loc[
        data["event_role"].eq("historical_primary_train")
        & data["source_quality_eligible"]
        & data["event_blind_residual_mw"].notna()
        & data["minutes_from_scheduled_kickoff"].ge(CONTEXT_START_MINUTES)
        & data["minutes_from_scheduled_kickoff"].lt(CONTEXT_END_MINUTES)
    ].copy()
    if context["match_id"].nunique() != 23:
        raise ValueError("Expected exactly 23 primary historical fixtures")
    return context, selected_name


def fit_correction(
    training: pd.DataFrame,
    spec: CorrectionSpec,
    event_column: str = "match_id",
) -> np.ndarray:
    """Fit global correction terms with event-specific intercept/slope nuisances."""
    x_global = training.loc[:, spec.features].to_numpy(dtype=float)
    events = pd.Categorical(training[event_column])
    event_codes = events.codes
    n_rows = len(training)
    n_events = len(events.categories)
    intercepts = np.zeros((n_rows, n_events), dtype=float)
    intercepts[np.arange(n_rows), event_codes] = 1.0
    hours = training["minutes_from_scheduled_kickoff"].to_numpy(dtype=float) / 60
    slopes = intercepts * hours[:, None]
    matrix = np.column_stack([x_global, intercepts, slopes])
    target = training["event_blind_residual_mw"].to_numpy(dtype=float)
    coefficients, *_ = np.linalg.lstsq(matrix, target, rcond=None)
    return coefficients[: len(spec.features)]


def correction_values(data: pd.DataFrame, spec: CorrectionSpec, beta: np.ndarray) -> np.ndarray:
    return data.loc[:, spec.features].to_numpy(dtype=float) @ beta


def metric_values(actual: np.ndarray, forecast: np.ndarray) -> dict:
    error = actual - forecast
    return {
        "n": int(len(error)),
        "mae_mw": float(np.mean(np.abs(error))),
        "rmse_mw": float(np.sqrt(np.mean(error**2))),
        "me_mw": float(np.mean(error)),
    }


def bootstrap_coefficients(
    context: pd.DataFrame,
    spec: CorrectionSpec,
    repetitions: int = 1_000,
    seed: int = 20241111,
) -> np.ndarray:
    """Fixture-cluster bootstrap; repeated fixtures receive unique nuisance effects."""
    rng = np.random.default_rng(seed)
    match_ids = context["match_id"].drop_duplicates().to_numpy()
    draws = np.empty((repetitions, len(spec.features)), dtype=float)
    grouped = {match_id: group for match_id, group in context.groupby("match_id")}
    for repetition in range(repetitions):
        sampled_ids = rng.choice(match_ids, size=len(match_ids), replace=True)
        pieces = []
        for sample_index, match_id in enumerate(sampled_ids):
            piece = grouped[match_id].copy()
            piece["bootstrap_event"] = f"sample_{sample_index}"
            pieces.append(piece)
        sample = pd.concat(pieces, ignore_index=True)
        draws[repetition] = fit_correction(sample, spec, "bootstrap_event")
    return draws


def main() -> None:
    context, event_blind_name = primary_match_context()
    match_ids = context["match_id"].drop_duplicates().tolist()
    score_mask = context[
        [
            "pregame_overlap_fraction",
            "scheduled_match_overlap_fraction",
            "postmatch_overlap_fraction",
        ]
    ].max(axis=1).gt(0)
    scored_context = context.loc[score_mask].copy()
    actual_all = scored_context["demand_mw"].to_numpy(dtype=float)
    blind_all = scored_context["event_blind_forecast_mw"].to_numpy(dtype=float)

    summary = {
        "selection_scope": "23 primary historical England fixtures in 2022-2023",
        "selection_method": "leave-one-match-out cross-validation",
        "primary_metric": "pooled MAE inside the pregame-through-postmatch correction window",
        "event_blind_model": event_blind_name,
        "context_minutes": [CONTEXT_START_MINUTES, CONTEXT_END_MINUTES],
        "n_matches": len(match_ids),
        "baseline": metric_values(actual_all, blind_all),
        "candidates": {},
        "march_2024_validation_opened": False,
        "euro_2024_holdout_opened": False,
    }
    prediction_rows: list[pd.DataFrame] = []

    for spec in CORRECTION_SPECS:
        fold_frames = []
        for held_out in match_ids:
            training = context.loc[context["match_id"].ne(held_out)]
            held = scored_context.loc[scored_context["match_id"].eq(held_out)].copy()
            beta = fit_correction(training, spec)
            held["correction_mw"] = correction_values(held, spec, beta)
            held["match_aware_forecast_mw"] = (
                held["event_blind_forecast_mw"] + held["correction_mw"]
            )
            held["candidate"] = spec.name
            fold_frames.append(held)
        predictions = pd.concat(fold_frames, ignore_index=True)
        actual = predictions["demand_mw"].to_numpy(dtype=float)
        aware = predictions["match_aware_forecast_mw"].to_numpy(dtype=float)
        final_beta = fit_correction(context, spec)
        bootstrap = bootstrap_coefficients(context, spec)
        coefficient_results = {}
        for index, feature in enumerate(spec.features):
            coefficient_results[feature] = {
                "estimate_mw": float(final_beta[index]),
                "cluster_bootstrap_95_low_mw": float(np.quantile(bootstrap[:, index], 0.025)),
                "cluster_bootstrap_95_high_mw": float(np.quantile(bootstrap[:, index], 0.975)),
            }
        per_match = predictions.assign(
            blind_absolute_error=lambda frame: (
                frame["demand_mw"] - frame["event_blind_forecast_mw"]
            ).abs(),
            aware_absolute_error=lambda frame: (
                frame["demand_mw"] - frame["match_aware_forecast_mw"]
            ).abs(),
        ).groupby("match_id").agg(
            blind_mae_mw=("blind_absolute_error", "mean"),
            aware_mae_mw=("aware_absolute_error", "mean"),
        )
        per_match["mae_change_mw"] = per_match["aware_mae_mw"] - per_match["blind_mae_mw"]
        candidate_metrics = metric_values(actual, aware)
        candidate_metrics.update(
            {
                "features": list(spec.features),
                "mae_improvement_vs_blind_mw": float(
                    summary["baseline"]["mae_mw"] - candidate_metrics["mae_mw"]
                ),
                "matches_improved": int(per_match["mae_change_mw"].lt(0).sum()),
                "median_match_mae_change_mw": float(per_match["mae_change_mw"].median()),
                "final_coefficients": coefficient_results,
            }
        )
        summary["candidates"][spec.name] = candidate_metrics
        prediction_rows.append(predictions)

    best_correction = min(
        CORRECTION_SPECS,
        key=lambda spec: summary["candidates"][spec.name]["mae_mw"],
    )
    summary["best_correction_candidate"] = best_correction.name
    correction_improves_mae = (
        summary["candidates"][best_correction.name]["mae_mw"]
        < summary["baseline"]["mae_mw"]
    )
    summary["correction_passes_deployment_gate"] = correction_improves_mae
    summary["selected_correction"] = (
        best_correction.name if correction_improves_mae else "no_correction"
    )
    summary["selection_locked_before_external_match_validation"] = True
    (MODEL_DIR / "match_correction_selection.json").write_text(
        json.dumps(summary, indent=2) + "\n"
    )
    all_predictions = pd.concat(prediction_rows, ignore_index=True)
    output_columns = [
        "candidate",
        "match_id",
        "opponent",
        "competition",
        "timestamp_utc",
        "timestamp_london",
        "minutes_from_scheduled_kickoff",
        "demand_mw",
        "event_blind_forecast_mw",
        "correction_mw",
        "match_aware_forecast_mw",
        "pregame_overlap_fraction",
        "scheduled_match_overlap_fraction",
        "halftime_proxy_overlap_fraction",
        "postmatch_overlap_fraction",
    ]
    all_predictions[output_columns].to_csv(
        MODEL_DIR / "match_correction_lomo_predictions.csv", index=False
    )
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
