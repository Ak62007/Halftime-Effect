"""Select a schedule correction on historical locked-v3 tournament residuals.

EURO 2024 is not read here.  Candidates transfer between complete tournament
editions: fit on EURO 2020 and score World Cup 2022, then reverse the roles.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from evaluate_v3_ridge_ablation import metrics


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data/processed/match_aware_v3"
CONFIG = json.loads((ROOT / "configs/match_aware_v3_experiment.json").read_text())


@dataclass(frozen=True)
class Candidate:
    name: str
    features: tuple[str, ...]
    shrinkage: float = 1.0
    estimation: str = "raw"


CANDIDATES = [
    Candidate("broad_event_window", ("event_window_overlap_fraction",)),
    Candidate("scheduled_match_only", ("scheduled_match_overlap_fraction",)),
    Candidate(
        "match_plus_halftime",
        ("scheduled_match_overlap_fraction", "halftime_proxy_overlap_fraction"),
    ),
    Candidate(
        "four_window_half_shrink",
        (
            "pregame_overlap_fraction",
            "scheduled_match_overlap_fraction",
            "halftime_proxy_overlap_fraction",
            "postmatch_overlap_fraction",
        ),
        0.5,
    ),
    Candidate(
        "four_window",
        (
            "pregame_overlap_fraction",
            "scheduled_match_overlap_fraction",
            "halftime_proxy_overlap_fraction",
            "postmatch_overlap_fraction",
        ),
    ),
    Candidate(
        "shape_match_plus_halftime",
        ("scheduled_match_overlap_fraction", "halftime_proxy_overlap_fraction"),
        estimation="fixture_level_and_drift_adjusted",
    ),
    Candidate(
        "shape_four_window",
        (
            "pregame_overlap_fraction",
            "scheduled_match_overlap_fraction",
            "halftime_proxy_overlap_fraction",
            "postmatch_overlap_fraction",
        ),
        estimation="fixture_level_and_drift_adjusted",
    ),
]


def load_historical() -> pd.DataFrame:
    path = OUT / "tournament_v3_baselines_historical_only.csv"
    data = pd.read_csv(path)
    expected = set(CONFIG["historical_selection_editions"])
    if set(data["tournament_edition"].unique()) != expected:
        raise ValueError("Historical prediction editions do not match the contract")
    if data["match_id"].nunique() != 12:
        raise ValueError("Expected 12 historical tournament fixtures")
    data["event_window_overlap_fraction"] = data[
        [
            "pregame_overlap_fraction",
            "scheduled_match_overlap_fraction",
            "postmatch_overlap_fraction",
        ]
    ].sum(axis=1)
    return data


def fit_coefficients(rows: pd.DataFrame, candidate: Candidate) -> np.ndarray:
    if candidate.estimation == "raw":
        fit_rows = rows.loc[rows["event_window_overlap_fraction"].gt(0)].copy()
        x = fit_rows.loc[:, candidate.features].to_numpy(dtype=float)
        y = (fit_rows["demand_mw"] - fit_rows["v3_forecast_mw"]).to_numpy(dtype=float)
        coefficients, *_ = np.linalg.lstsq(x, y, rcond=None)
        return coefficients * candidate.shrinkage
    if candidate.estimation != "fixture_level_and_drift_adjusted":
        raise ValueError(f"Unknown estimation mode: {candidate.estimation}")

    context = rows.loc[
        rows["minutes_from_scheduled_kickoff"].between(-240, 285, inclusive="left")
    ].copy()
    x_global = context.loc[:, candidate.features].to_numpy(dtype=float)
    events = pd.Categorical(context["match_id"])
    event_codes = events.codes
    intercepts = np.zeros((len(context), len(events.categories)))
    intercepts[np.arange(len(context)), event_codes] = 1.0
    hours = context["minutes_from_scheduled_kickoff"].to_numpy(dtype=float) / 60
    slopes = intercepts * hours[:, None]
    x = np.column_stack([x_global, intercepts, slopes])
    y = (context["demand_mw"] - context["v3_forecast_mw"]).to_numpy(dtype=float)
    coefficients, *_ = np.linalg.lstsq(x, y, rcond=None)
    return coefficients[: len(candidate.features)] * candidate.shrinkage


def correction(rows: pd.DataFrame, candidate: Candidate, beta: np.ndarray) -> np.ndarray:
    return rows.loc[:, candidate.features].to_numpy(dtype=float) @ beta


def bootstrap_coefficients(
    rows: pd.DataFrame,
    candidate: Candidate,
    repetitions: int = 5_000,
    seed: int = 20261111,
) -> np.ndarray:
    rng = np.random.default_rng(seed)
    match_ids = rows["match_id"].drop_duplicates().to_numpy()
    groups = {match_id: part for match_id, part in rows.groupby("match_id")}
    draws = np.empty((repetitions, len(candidate.features)))
    for index in range(repetitions):
        sampled = rng.choice(match_ids, size=len(match_ids), replace=True)
        pieces = []
        for sample_index, match_id in enumerate(sampled):
            piece = groups[match_id].copy()
            piece["match_id"] = f"bootstrap_{sample_index}"
            pieces.append(piece)
        sample = pd.concat(pieces, ignore_index=True)
        draws[index] = fit_coefficients(sample, candidate)
    return draws


def main() -> None:
    all_rows = load_historical()
    rows = all_rows.loc[all_rows["event_window_overlap_fraction"].gt(0)].copy()
    actual = rows["demand_mw"].to_numpy(dtype=float)
    blind = rows["v3_forecast_mw"].to_numpy(dtype=float)
    baseline = metrics(actual, blind)
    editions = rows["tournament_edition"].drop_duplicates().tolist()
    results = {
        "purpose": "schedule correction on the locked-v3 event-blind baseline",
        "selection_method": "leave one complete historical tournament edition out",
        "historical_editions": editions,
        "n_matches": int(rows["match_id"].nunique()),
        "n_scored_half_hours": int(len(rows)),
        "baseline": baseline,
        "candidates": {},
        "selection_gate": "pooled MAE must improve and MAE must improve in both held-out editions",
        "euro_2024_read": False,
        "future_untouched_tournament_required": True,
    }
    prediction_parts = []

    for candidate in CANDIDATES:
        folds = []
        edition_metrics = {}
        for held_edition in editions:
            training = all_rows.loc[
                all_rows["tournament_edition"].ne(held_edition)
            ]
            held = rows.loc[rows["tournament_edition"].eq(held_edition)].copy()
            beta = fit_coefficients(training, candidate)
            held["correction_mw"] = correction(held, candidate, beta)
            held["match_aware_forecast_mw"] = (
                held["v3_forecast_mw"] + held["correction_mw"]
            )
            held["candidate"] = candidate.name
            folds.append(held)
            held_actual = held["demand_mw"].to_numpy(dtype=float)
            edition_metrics[held_edition] = {
                "event_blind": metrics(
                    held_actual, held["v3_forecast_mw"].to_numpy(dtype=float)
                ),
                "match_aware": metrics(
                    held_actual,
                    held["match_aware_forecast_mw"].to_numpy(dtype=float),
                ),
            }

        predictions = pd.concat(folds, ignore_index=True)
        aware = metrics(
            predictions["demand_mw"].to_numpy(dtype=float),
            predictions["match_aware_forecast_mw"].to_numpy(dtype=float),
        )
        improves_each = all(
            item["match_aware"]["mae_mw"] < item["event_blind"]["mae_mw"]
            for item in edition_metrics.values()
        )
        final_beta = fit_coefficients(all_rows, candidate)
        bootstrap = bootstrap_coefficients(all_rows, candidate)
        coefficient_results = {
            feature: {
                "estimate_mw": float(final_beta[position]),
                "fixture_bootstrap_95_low_mw": float(
                    np.quantile(bootstrap[:, position], 0.025)
                ),
                "fixture_bootstrap_95_high_mw": float(
                    np.quantile(bootstrap[:, position], 0.975)
                ),
            }
            for position, feature in enumerate(candidate.features)
        }
        results["candidates"][candidate.name] = {
            "features": list(candidate.features),
            "shrinkage": candidate.shrinkage,
            "estimation": candidate.estimation,
            **aware,
            "mae_improvement_vs_blind_mw": float(baseline["mae_mw"] - aware["mae_mw"]),
            "improves_both_editions": improves_each,
            "edition_transfer": edition_metrics,
            "final_coefficients": coefficient_results,
        }
        prediction_parts.append(predictions)

    eligible = {
        name: item
        for name, item in results["candidates"].items()
        if item["mae_mw"] < baseline["mae_mw"] and item["improves_both_editions"]
    }
    if eligible:
        selected = min(eligible, key=lambda name: eligible[name]["mae_mw"])
        passes = True
    else:
        selected = "no_correction"
        passes = False
    results["selected_correction"] = selected
    results["correction_passes_gate"] = passes
    results["selection_locked_before_euro_2024_rerun"] = True

    (OUT / "correction_selection.json").write_text(json.dumps(results, indent=2) + "\n")
    pd.concat(prediction_parts, ignore_index=True).to_csv(
        OUT / "correction_cross_edition_predictions.csv", index=False
    )
    (OUT / "correction_lock.json").write_text(
        json.dumps(
            {
                "version": 1,
                "selected_correction": selected,
                "passes_gate": passes,
                "candidate": (
                    None
                    if selected == "no_correction"
                    else {
                        "features": results["candidates"][selected]["features"],
                        "shrinkage": results["candidates"][selected]["shrinkage"],
                        "estimation": results["candidates"][selected]["estimation"],
                        "coefficients_mw": {
                            feature: details["estimate_mw"]
                            for feature, details in results["candidates"][selected][
                                "final_coefficients"
                            ].items()
                        },
                    }
                ),
                "euro_2024_used_for_selection": False,
                "future_untouched_tournament_required": True,
            },
            indent=2,
        )
        + "\n"
    )
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
