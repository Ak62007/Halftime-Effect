"""Retrospective EURO 2024 diagnostic for the locked match-aware-v3 policy."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from evaluate_v3_ridge_ablation import metrics


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data/processed/match_aware_v3"
LOCK = json.loads((ROOT / "configs/match_aware_v3_model_lock.json").read_text())
LOCK_COMMIT = "37471f6"


def metric_bundle(rows: pd.DataFrame) -> dict:
    actual = rows["demand_mw"].to_numpy(dtype=float)
    result = {
        "weekly_seasonal_naive": metrics(actual, rows["lag_336"].to_numpy(dtype=float)),
        "v3_event_blind": metrics(actual, rows["v3_forecast_mw"].to_numpy(dtype=float)),
        "v3_match_aware": metrics(
            actual, rows["match_aware_forecast_mw"].to_numpy(dtype=float)
        ),
    }
    available = rows["neso_available_at_cutoff"].astype(bool).to_numpy()
    result["neso_available_rows"] = metrics(
        actual[available],
        rows.loc[available, "neso_day_ahead_forecast_mw"].to_numpy(dtype=float),
    )
    return result


def main() -> None:
    data = pd.read_csv(OUT / "tournament_v3_baselines_with_euro_2024.csv")
    euro = data.loc[data["tournament_edition"].eq("UEFA EURO 2024")].copy()
    if euro["match_id"].nunique() != 7:
        raise ValueError("Expected seven EURO 2024 fixtures")

    coefficients = LOCK["schedule_correction"]["coefficients_mw"]
    euro["schedule_correction_mw"] = sum(
        euro[feature].to_numpy(dtype=float) * value
        for feature, value in coefficients.items()
    )
    euro["match_aware_forecast_mw"] = (
        euro["v3_forecast_mw"] + euro["schedule_correction_mw"]
    )
    euro["event_window_overlap_fraction"] = euro[
        [
            "pregame_overlap_fraction",
            "scheduled_match_overlap_fraction",
            "postmatch_overlap_fraction",
        ]
    ].sum(axis=1)
    scopes = {
        "seven_match_days": euro,
        "event_window_primary": euro.loc[euro["event_window_overlap_fraction"].gt(0)],
        "pregame_window": euro.loc[euro["pregame_overlap_fraction"].gt(0)],
        "scheduled_match_window": euro.loc[
            euro["scheduled_match_overlap_fraction"].gt(0)
        ],
        "halftime_proxy_window": euro.loc[
            euro["halftime_proxy_overlap_fraction"].gt(0)
        ],
        "postmatch_window": euro.loc[euro["postmatch_overlap_fraction"].gt(0)],
    }
    scope_metrics = {name: metric_bundle(rows) for name, rows in scopes.items()}

    primary = scopes["event_window_primary"].copy()
    primary["blind_ae"] = (
        primary["demand_mw"] - primary["v3_forecast_mw"]
    ).abs()
    primary["aware_ae"] = (
        primary["demand_mw"] - primary["match_aware_forecast_mw"]
    ).abs()
    per_match = primary.groupby(["match_id", "opponent"], as_index=False).agg(
        n=("demand_mw", "size"),
        event_blind_mae_mw=("blind_ae", "mean"),
        match_aware_mae_mw=("aware_ae", "mean"),
    )
    per_match["mae_change_mw"] = (
        per_match["match_aware_mae_mw"] - per_match["event_blind_mae_mw"]
    )
    changes = per_match["mae_change_mw"].to_numpy(dtype=float)
    rng = np.random.default_rng(20261112)
    bootstrap = np.mean(
        rng.choice(changes, size=(20_000, len(changes)), replace=True), axis=1
    )
    blind = scope_metrics["event_window_primary"]["v3_event_blind"]
    aware = scope_metrics["event_window_primary"]["v3_match_aware"]
    result = {
        "evaluation_status": (
            "EURO 2024 retrospective diagnostic; period was already opened before "
            f"match-aware-v3 lock commit {LOCK_COMMIT}"
        ),
        "new_holdout_claim": False,
        "model_changed_after_locked_rerun": False,
        "locked_correction": LOCK["schedule_correction"],
        "matches": int(euro["match_id"].nunique()),
        "scope_metrics": scope_metrics,
        "primary_result": {
            "event_blind_mae_mw": blind["mae_mw"],
            "match_aware_mae_mw": aware["mae_mw"],
            "mae_improvement_mw": blind["mae_mw"] - aware["mae_mw"],
            "mae_improvement_percent": 100
            * (blind["mae_mw"] - aware["mae_mw"])
            / blind["mae_mw"],
            "event_blind_rmse_mw": blind["rmse_mw"],
            "match_aware_rmse_mw": aware["rmse_mw"],
            "matches_improved": int((changes < 0).sum()),
            "fixture_mean_mae_change_mw": float(changes.mean()),
            "fixture_bootstrap_95_low_change_mw": float(np.quantile(bootstrap, 0.025)),
            "fixture_bootstrap_95_high_change_mw": float(np.quantile(bootstrap, 0.975)),
        },
        "per_match": per_match.to_dict(orient="records"),
        "future_untouched_tournament_required": True,
    }
    (OUT / "euro_2024_retrospective_evaluation.json").write_text(
        json.dumps(result, indent=2) + "\n"
    )
    output_columns = [
        "match_id",
        "opponent",
        "timestamp_utc",
        "minutes_from_scheduled_kickoff",
        "demand_mw",
        "lag_336",
        "neso_day_ahead_forecast_mw",
        "neso_available_at_cutoff",
        "v3_forecast_mw",
        "schedule_correction_mw",
        "match_aware_forecast_mw",
        "pregame_overlap_fraction",
        "scheduled_match_overlap_fraction",
        "halftime_proxy_overlap_fraction",
        "postmatch_overlap_fraction",
    ]
    euro[output_columns].to_csv(OUT / "euro_2024_retrospective_predictions.csv", index=False)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
