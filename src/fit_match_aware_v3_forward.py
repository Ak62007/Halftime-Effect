"""Refit the selected schedule shape on all 19 tournaments for future use.

This is a deployment refit, not an evaluation.  EURO 2024 outcomes enter the fit, so
the resulting coefficients require a later untouched tournament for assessment.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from select_match_aware_v3_correction import (
    CANDIDATES,
    bootstrap_coefficients,
    fit_coefficients,
)


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data/processed/match_aware_v3"


def main() -> None:
    rows = pd.read_csv(OUT / "tournament_v3_baselines_with_euro_2024.csv")
    rows["event_window_overlap_fraction"] = rows[
        [
            "pregame_overlap_fraction",
            "scheduled_match_overlap_fraction",
            "postmatch_overlap_fraction",
        ]
    ].sum(axis=1)
    if rows["match_id"].nunique() != 19:
        raise ValueError("Expected all 19 tournament fixtures")
    candidate = next(item for item in CANDIDATES if item.name == "shape_four_window")
    beta = fit_coefficients(rows, candidate)
    bootstrap = bootstrap_coefficients(rows, candidate, repetitions=10_000, seed=20261113)
    result = {
        "status": "forward deployment refit; not evaluated on an untouched tournament",
        "selected_form": candidate.name,
        "estimation": candidate.estimation,
        "training_editions": [
            "UEFA EURO 2020",
            "FIFA World Cup 2022",
            "UEFA EURO 2024",
        ],
        "training_matches": int(rows["match_id"].nunique()),
        "coefficients": {
            feature: {
                "estimate_mw": float(beta[position]),
                "fixture_bootstrap_95_low_mw": float(
                    np.quantile(bootstrap[:, position], 0.025)
                ),
                "fixture_bootstrap_95_high_mw": float(
                    np.quantile(bootstrap[:, position], 0.975)
                ),
            }
            for position, feature in enumerate(candidate.features)
        },
        "future_untouched_tournament_required": True,
    }
    (OUT / "forward_model_refit.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
