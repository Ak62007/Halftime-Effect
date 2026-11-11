"""Leave-one-fold-out calibration of v3 forecast intervals."""
from __future__ import annotations

import json

import numpy as np
import pandas as pd

from evaluate_v3_ridge_ablation import OUT


SIGMA_COLUMNS = {
    "constant": "constant_sigma_mw",
    "garch": "garch_sigma_mw",
    "structured": "structured_sigma_mw",
}


def higher_quantile(values: np.ndarray, probability: float) -> float:
    return float(np.quantile(values, probability, method="higher"))


def main() -> None:
    predictions = pd.read_csv(OUT / "variance_validation_predictions.csv")
    results = {
        "method": "leave-one-fold-out absolute standardized-residual calibration",
        "point_forecast_changed": False,
        "final_test_opened": False,
        "models": {},
    }
    for model_name, sigma_column in SIGMA_COLUMNS.items():
        model_result = {"folds": {}}
        for fold_name in predictions["fold"].unique():
            calibration = predictions.loc[predictions["fold"].ne(fold_name)]
            evaluation = predictions.loc[predictions["fold"].eq(fold_name)]
            calibration_score = np.abs(
                calibration["selected_residual_mw"].to_numpy()
                / calibration[sigma_column].to_numpy()
            )
            evaluation_score = np.abs(
                evaluation["selected_residual_mw"].to_numpy()
                / evaluation[sigma_column].to_numpy()
            )
            q80 = higher_quantile(calibration_score, 0.8)
            q95 = higher_quantile(calibration_score, 0.95)
            sigma = evaluation[sigma_column].to_numpy()
            model_result["folds"][fold_name] = {
                "calibration_rows": int(len(calibration)),
                "evaluation_rows": int(len(evaluation)),
                "critical_80": q80,
                "critical_95": q95,
                "coverage_80": float(np.mean(evaluation_score <= q80)),
                "coverage_95": float(np.mean(evaluation_score <= q95)),
                "mean_80_interval_width_mw": float(np.mean(2 * q80 * sigma)),
                "mean_95_interval_width_mw": float(np.mean(2 * q95 * sigma)),
            }
        folds = list(model_result["folds"].values())
        model_result["summary"] = {
            "mean_80_coverage": float(np.mean([x["coverage_80"] for x in folds])),
            "mean_95_coverage": float(np.mean([x["coverage_95"] for x in folds])),
            "mean_80_interval_width_mw": float(
                np.mean([x["mean_80_interval_width_mw"] for x in folds])
            ),
            "mean_95_interval_width_mw": float(
                np.mean([x["mean_95_interval_width_mw"] for x in folds])
            ),
        }
        all_score = np.abs(
            predictions["selected_residual_mw"].to_numpy()
            / predictions[sigma_column].to_numpy()
        )
        model_result["locked_full_development_critical_values"] = {
            "central_80": higher_quantile(all_score, 0.8),
            "central_95": higher_quantile(all_score, 0.95),
        }
        results["models"][model_name] = model_result

    # Coverage is a constraint, not an objective to match to many decimals. Among
    # models within one percentage point of both nominal levels, prefer the sharper
    # (narrower) 95% interval.
    eligible = []
    for name in SIGMA_COLUMNS:
        summary = results["models"][name]["summary"]
        if (
            abs(summary["mean_80_coverage"] - 0.8) <= 0.01
            and abs(summary["mean_95_coverage"] - 0.95) <= 0.01
        ):
            eligible.append(name)
    if not eligible:
        raise ValueError("No interval model meets the development coverage tolerance")
    results["coverage_selection_tolerance"] = 0.01
    results["selected_interval_scale_model"] = min(
        eligible,
        key=lambda name: results["models"][name]["summary"][
            "mean_95_interval_width_mw"
        ],
    )
    (OUT / "interval_calibration.json").write_text(
        json.dumps(results, indent=2) + "\n"
    )
    print(
        json.dumps(
            {
                "models": {
                    name: {
                        **item["summary"],
                        "locked_critical_values": item[
                            "locked_full_development_critical_values"
                        ],
                    }
                    for name, item in results["models"].items()
                },
                "selected": results["selected_interval_scale_model"],
                "final_test_opened": False,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
