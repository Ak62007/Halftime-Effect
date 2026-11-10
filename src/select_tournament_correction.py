"""Select a tournament-specific schedule correction without opening 2024 outcomes.

Candidate selection leaves out an entire historical tournament edition, which is
closer to the intended task of forecasting a new tournament than random row splits.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from fit_event_blind_models import load_data
from select_match_correction import (
    CORRECTION_SPECS,
    correction_values,
    metric_values,
    selected_event_blind_predictions,
)


ROOT = Path(__file__).resolve().parents[1]
MODEL_DIR = ROOT / "data/processed/match_aware/modeling"


def tournament_rows() -> pd.DataFrame:
    data = load_data()
    forecasts, _ = selected_event_blind_predictions(data)
    data["event_blind_forecast_mw"] = forecasts
    data["event_blind_residual_mw"] = data["demand_mw"] - forecasts
    score_window = data[
        [
            "pregame_overlap_fraction",
            "scheduled_match_overlap_fraction",
            "postmatch_overlap_fraction",
        ]
    ].max(axis=1).gt(0)
    rows = data.loc[
        data["event_role"].isin(
            ["historical_sensitivity_event", "historical_primary_train"]
        )
        & data["is_tournament_match"]
        & data["source_quality_eligible"]
        & data["event_blind_residual_mw"].notna()
        & score_window
    ].copy()
    rows["tournament_edition"] = np.select(
        [
            rows["competition"].str.contains("EURO", case=False, na=False),
            rows["competition"].str.contains("World Cup", case=False, na=False),
        ],
        ["UEFA EURO 2020", "FIFA World Cup 2022"],
        default="unknown",
    )
    if rows["match_id"].nunique() != 12 or rows["tournament_edition"].eq("unknown").any():
        raise ValueError("Expected 12 fixtures from two known tournament editions")
    return rows


def fit_raw_correction(training: pd.DataFrame, features: tuple[str, ...]) -> np.ndarray:
    """Estimate the average forecast increment that is knowable from the schedule."""
    matrix = training.loc[:, features].to_numpy(dtype=float)
    target = training["event_blind_residual_mw"].to_numpy(dtype=float)
    coefficients, *_ = np.linalg.lstsq(matrix, target, rcond=None)
    return coefficients


def raw_cluster_bootstrap(
    rows: pd.DataFrame,
    features: tuple[str, ...],
    repetitions: int = 2_000,
    seed: int = 20241112,
) -> np.ndarray:
    rng = np.random.default_rng(seed)
    match_ids = rows["match_id"].drop_duplicates().to_numpy()
    groups = {match_id: group for match_id, group in rows.groupby("match_id")}
    draws = np.empty((repetitions, len(features)))
    for repetition in range(repetitions):
        sampled = rng.choice(match_ids, size=len(match_ids), replace=True)
        sample = pd.concat([groups[match_id] for match_id in sampled], ignore_index=True)
        draws[repetition] = fit_raw_correction(sample, features)
    return draws


def main() -> None:
    rows = tournament_rows()
    actual = rows["demand_mw"].to_numpy(dtype=float)
    blind = rows["event_blind_forecast_mw"].to_numpy(dtype=float)
    baseline = metric_values(actual, blind)
    results = {
        "purpose": "forecast correction for a future tournament edition",
        "selection_method": "leave-one-tournament-edition-out cross-validation",
        "historical_editions": ["UEFA EURO 2020", "FIFA World Cup 2022"],
        "n_matches": int(rows["match_id"].nunique()),
        "n_half_hours": int(len(rows)),
        "baseline": baseline,
        "candidates": {},
        "march_2024_validation_opened": False,
        "euro_2024_holdout_opened": False,
    }
    prediction_frames = []

    for spec in CORRECTION_SPECS:
        fold_frames = []
        edition_metrics = {}
        for held_edition in rows["tournament_edition"].drop_duplicates():
            training = rows.loc[rows["tournament_edition"].ne(held_edition)]
            held = rows.loc[rows["tournament_edition"].eq(held_edition)].copy()
            beta = fit_raw_correction(training, spec.features)
            held["correction_mw"] = correction_values(held, spec, beta)
            held["match_aware_forecast_mw"] = (
                held["event_blind_forecast_mw"] + held["correction_mw"]
            )
            held["candidate"] = spec.name
            fold_frames.append(held)
            edition_metrics[held_edition] = {
                "n_matches": int(held["match_id"].nunique()),
                "event_blind": metric_values(
                    held["demand_mw"].to_numpy(),
                    held["event_blind_forecast_mw"].to_numpy(),
                ),
                "match_aware": metric_values(
                    held["demand_mw"].to_numpy(),
                    held["match_aware_forecast_mw"].to_numpy(),
                ),
            }
        predictions = pd.concat(fold_frames, ignore_index=True)
        aware_metrics = metric_values(
            predictions["demand_mw"].to_numpy(),
            predictions["match_aware_forecast_mw"].to_numpy(),
        )
        final_beta = fit_raw_correction(rows, spec.features)
        bootstrap = raw_cluster_bootstrap(rows, spec.features)
        coefficients = {
            feature: {
                "estimate_mw": float(final_beta[index]),
                "cluster_bootstrap_95_low_mw": float(
                    np.quantile(bootstrap[:, index], 0.025)
                ),
                "cluster_bootstrap_95_high_mw": float(
                    np.quantile(bootstrap[:, index], 0.975)
                ),
            }
            for index, feature in enumerate(spec.features)
        }

        # A deliberately harsher stability check within each edition.
        within_edition = {}
        for edition, edition_rows in rows.groupby("tournament_edition"):
            fold_parts = []
            for held_match in edition_rows["match_id"].drop_duplicates():
                training = edition_rows.loc[edition_rows["match_id"].ne(held_match)]
                held = edition_rows.loc[edition_rows["match_id"].eq(held_match)].copy()
                beta = fit_raw_correction(training, spec.features)
                held["forecast"] = held["event_blind_forecast_mw"] + correction_values(
                    held, spec, beta
                )
                fold_parts.append(held)
            edition_predictions = pd.concat(fold_parts, ignore_index=True)
            within_edition[edition] = {
                "event_blind_mae_mw": float(
                    np.mean(
                        np.abs(
                            edition_predictions["demand_mw"]
                            - edition_predictions["event_blind_forecast_mw"]
                        )
                    )
                ),
                "match_aware_mae_mw": float(
                    np.mean(
                        np.abs(
                            edition_predictions["demand_mw"]
                            - edition_predictions["forecast"]
                        )
                    )
                ),
            }

        results["candidates"][spec.name] = {
            "features": list(spec.features),
            **aware_metrics,
            "mae_improvement_vs_blind_mw": float(
                baseline["mae_mw"] - aware_metrics["mae_mw"]
            ),
            "edition_transfer": edition_metrics,
            "within_edition_lomo_sensitivity": within_edition,
            "final_coefficients": coefficients,
        }
        prediction_frames.append(predictions)

    best = min(
        CORRECTION_SPECS,
        key=lambda spec: results["candidates"][spec.name]["mae_mw"],
    )
    improves = results["candidates"][best.name]["mae_mw"] < baseline["mae_mw"]
    results["best_correction_candidate"] = best.name
    results["correction_passes_cross_edition_gate"] = improves
    results["selected_tournament_correction"] = best.name if improves else "no_correction"
    results["selection_locked_before_euro_2024"] = True
    (MODEL_DIR / "tournament_correction_selection.json").write_text(
        json.dumps(results, indent=2) + "\n"
    )

    predictions = pd.concat(prediction_frames, ignore_index=True)
    output_columns = [
        "candidate",
        "tournament_edition",
        "match_id",
        "opponent",
        "timestamp_utc",
        "minutes_from_scheduled_kickoff",
        "demand_mw",
        "event_blind_forecast_mw",
        "correction_mw",
        "match_aware_forecast_mw",
    ]
    predictions[output_columns].to_csv(
        MODEL_DIR / "tournament_correction_cross_edition_predictions.csv", index=False
    )
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
