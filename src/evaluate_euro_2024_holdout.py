"""One-time evaluation of the locked tournament correction on EURO 2024."""
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
from select_tournament_correction import fit_raw_correction, tournament_rows


ROOT = Path(__file__).resolve().parents[1]
MODEL_DIR = ROOT / "data/processed/match_aware/modeling"


def metric_bundle(rows: pd.DataFrame) -> dict:
    actual = rows["demand_mw"].to_numpy(dtype=float)
    columns = {
        "weekly_seasonal_naive": "demand_lag_336",
        "neso_day_ahead": "neso_day_ahead_forecast_mw",
        "event_blind": "event_blind_forecast_mw",
        "match_aware": "match_aware_forecast_mw",
    }
    return {name: metric_values(actual, rows[column].to_numpy(dtype=float)) for name, column in columns.items()}


def main() -> None:
    # Reconstruct the already-locked final correction from all 12 historical
    # tournament fixtures. No 2024 row enters this fit.
    historical = tournament_rows()
    spec = next(spec for spec in CORRECTION_SPECS if spec.name == "four_window")
    beta = fit_raw_correction(historical, spec.features)

    data = load_data()
    event_blind, event_blind_name = selected_event_blind_predictions(data)
    data["event_blind_forecast_mw"] = event_blind
    data["tournament_correction_mw"] = correction_values(data, spec, beta)
    data["match_aware_forecast_mw"] = (
        data["event_blind_forecast_mw"] + data["tournament_correction_mw"]
    )

    period = data.loc[
        data["data_split"].eq("event_holdout") & data["source_quality_eligible"]
    ].copy()
    match_days = period.loc[period["event_role"].eq("event_holdout")].copy()
    event_window = match_days.loc[
        match_days[
            [
                "pregame_overlap_fraction",
                "scheduled_match_overlap_fraction",
                "postmatch_overlap_fraction",
            ]
        ].max(axis=1).gt(0)
    ].copy()
    scopes = {
        "full_holdout_period": period,
        "seven_match_days": match_days,
        "correction_event_window_primary": event_window,
        "pregame_window": match_days.loc[match_days["pregame_overlap_fraction"].gt(0)],
        "scheduled_match_window": match_days.loc[
            match_days["scheduled_match_overlap_fraction"].gt(0)
        ],
        "halftime_proxy_window": match_days.loc[
            match_days["halftime_proxy_overlap_fraction"].gt(0)
        ],
        "postmatch_window": match_days.loc[match_days["postmatch_overlap_fraction"].gt(0)],
    }

    scope_metrics = {name: metric_bundle(rows) for name, rows in scopes.items()}
    event_window["event_blind_absolute_error_mw"] = (
        event_window["demand_mw"] - event_window["event_blind_forecast_mw"]
    ).abs()
    event_window["match_aware_absolute_error_mw"] = (
        event_window["demand_mw"] - event_window["match_aware_forecast_mw"]
    ).abs()
    per_match = event_window.groupby(["match_id", "opponent"], as_index=False).agg(
        n=("demand_mw", "size"),
        event_blind_mae_mw=("event_blind_absolute_error_mw", "mean"),
        match_aware_mae_mw=("match_aware_absolute_error_mw", "mean"),
    )
    per_match["mae_change_mw"] = (
        per_match["match_aware_mae_mw"] - per_match["event_blind_mae_mw"]
    )

    rng = np.random.default_rng(20241113)
    changes = per_match["mae_change_mw"].to_numpy()
    bootstrap_mean_changes = np.mean(
        rng.choice(changes, size=(20_000, len(changes)), replace=True), axis=1
    )
    primary_blind = scope_metrics["correction_event_window_primary"]["event_blind"]
    primary_aware = scope_metrics["correction_event_window_primary"]["match_aware"]
    evaluation = {
        "evaluation_status": "EURO 2024 holdout opened after model lock",
        "locked_event_blind_model": event_blind_name,
        "locked_tournament_correction": spec.name,
        "historical_training_matches": 12,
        "holdout_matches": int(match_days["match_id"].nunique()),
        "coefficients_mw": {
            feature: float(beta[index]) for index, feature in enumerate(spec.features)
        },
        "scope_metrics": scope_metrics,
        "primary_result": {
            "event_blind_mae_mw": primary_blind["mae_mw"],
            "match_aware_mae_mw": primary_aware["mae_mw"],
            "mae_improvement_mw": primary_blind["mae_mw"] - primary_aware["mae_mw"],
            "mae_improvement_percent": 100
            * (primary_blind["mae_mw"] - primary_aware["mae_mw"])
            / primary_blind["mae_mw"],
            "matches_improved": int(per_match["mae_change_mw"].lt(0).sum()),
            "mean_match_mae_change_mw": float(changes.mean()),
            "fixture_bootstrap_95_low_change_mw": float(
                np.quantile(bootstrap_mean_changes, 0.025)
            ),
            "fixture_bootstrap_95_high_change_mw": float(
                np.quantile(bootstrap_mean_changes, 0.975)
            ),
        },
        "per_match": per_match.to_dict(orient="records"),
        "model_changed_after_holdout": False,
    }
    (MODEL_DIR / "euro_2024_holdout_evaluation.json").write_text(
        json.dumps(evaluation, indent=2) + "\n"
    )

    output_columns = [
        "match_id",
        "opponent",
        "competition",
        "timestamp_utc",
        "timestamp_london",
        "minutes_from_scheduled_kickoff",
        "demand_mw",
        "demand_lag_336",
        "neso_day_ahead_forecast_mw",
        "event_blind_forecast_mw",
        "tournament_correction_mw",
        "match_aware_forecast_mw",
        "pregame_overlap_fraction",
        "scheduled_match_overlap_fraction",
        "halftime_proxy_overlap_fraction",
        "postmatch_overlap_fraction",
    ]
    match_days[output_columns].to_csv(
        MODEL_DIR / "euro_2024_holdout_predictions.csv", index=False
    )
    print(json.dumps(evaluation, indent=2))


if __name__ == "__main__":
    main()
