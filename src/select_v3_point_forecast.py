"""Select a fixed blend of the two strongest v3 dynamic forecasts."""
from __future__ import annotations

import json

import numpy as np
import pandas as pd

from diagnose_v2_garch import residual_diagnostics
from evaluate_v3_ridge_ablation import OUT, metrics, summarize


RIDGE_COLUMN = "forecast_direct_v3_ridge_a0_mw"
HGB_COLUMN = "forecast_direct_v3_hgb_mw"
BLEND_WEIGHTS_RIDGE = [0.25, 0.5, 0.75]


def main() -> None:
    predictions = pd.read_csv(OUT / "dynamic_validation_predictions.csv")
    results = {
        "selection_scope": "seven rolling-origin folds; final test unopened",
        "ridge_component": "direct_v3_ridge_a0",
        "hgb_component": "direct_v3_hgb",
        "candidate_ridge_weights": BLEND_WEIGHTS_RIDGE,
        "final_test_opened": False,
        "candidates": {},
    }
    actual = predictions["demand_mw"].to_numpy(dtype=float)
    ridge = predictions[RIDGE_COLUMN].to_numpy(dtype=float)
    hgb = predictions[HGB_COLUMN].to_numpy(dtype=float)
    for weight in BLEND_WEIGHTS_RIDGE:
        name = f"blend_ridge_{weight:g}_hgb_{1-weight:g}"
        forecast = weight * ridge + (1 - weight) * hgb
        predictions[f"forecast_{name}_mw"] = forecast
        folds = {}
        for fold_name, positions in predictions.groupby("fold").groups.items():
            index = np.asarray(list(positions), dtype=int)
            folds[fold_name] = metrics(actual[index], forecast[index])
        results["candidates"][name] = {
            "ridge_weight": weight,
            "hgb_weight": 1 - weight,
            "folds": folds,
            "summary": summarize(folds),
        }
    selected = min(
        results["candidates"],
        key=lambda name: results["candidates"][name]["summary"]["mean_fold_mae_mw"],
    )
    selected_column = f"forecast_{selected}_mw"
    predictions["selected_forecast_mw"] = predictions[selected_column]
    predictions["selected_residual_mw"] = (
        predictions["demand_mw"] - predictions["selected_forecast_mw"]
    )
    results["selected_point_model"] = selected
    results["selected_summary"] = results["candidates"][selected]["summary"]
    results["residual_diagnostics"] = residual_diagnostics(
        predictions["selected_residual_mw"].to_numpy(dtype=float)
    )
    results["residual_independence_achieved"] = False
    results["point_model_locked_before_variance_stage"] = True
    (OUT / "point_model_selection.json").write_text(
        json.dumps(results, indent=2) + "\n"
    )
    predictions.to_csv(OUT / "selected_validation_predictions.csv", index=False)
    print(
        json.dumps(
            {
                "candidates": {
                    name: item["summary"] for name, item in results["candidates"].items()
                },
                "selected": selected,
                "selected_summary": results["selected_summary"],
                "residual_diagnostics": results["residual_diagnostics"],
                "final_test_opened": False,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
