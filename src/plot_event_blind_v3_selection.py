"""Create high-resolution event-blind v3 development figures."""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from statsmodels.tsa.stattools import acf


ROOT = Path(__file__).resolve().parents[1]
MODEL_DIR = ROOT / "data/processed/event_blind_v3/modeling"
FIGURES = ROOT / "docs/figures/event_blind_v3"
FIGURES.mkdir(parents=True, exist_ok=True)
ridge = json.loads((MODEL_DIR / "ridge_ablation_metrics.json").read_text())
nonlinear = json.loads((MODEL_DIR / "nonlinear_candidate_metrics.json").read_text())
dynamic = json.loads((MODEL_DIR / "dynamic_candidate_metrics.json").read_text())
point = json.loads((MODEL_DIR / "point_model_selection.json").read_text())
interval = json.loads((MODEL_DIR / "interval_calibration.json").read_text())
selected = pd.read_csv(MODEL_DIR / "selected_validation_predictions.csv")

plt.style.use("dark_background")
colors = {
    "V2": "#3498db",
    "Calendar": "#9b59b6",
    "Weather": "#2ecc71",
    "Embedded": "#ff9f43",
    "Full": "#00e5ff",
    "Selected": "#00e5ff",
    "NESO": "#ffb300",
}


feature_names = [
    ("V2", "v2_ridge_reproduced"),
    ("Calendar", "v3_calendar"),
    ("Weather", "v3_weather"),
    ("Embedded", "v3_embedded"),
    ("Full", "v3_full_recent730_a1"),
]
mean_mae = [ridge["candidates"][key]["summary"]["mean_fold_mae_mw"] for _, key in feature_names]
worst_mae = [ridge["candidates"][key]["summary"]["worst_fold_mae_mw"] for _, key in feature_names]
x = np.arange(len(feature_names))
fig, axis = plt.subplots(figsize=(12, 7))
width = 0.37
axis.bar(
    x - width / 2,
    mean_mae,
    width,
    label="Mean fold MAE",
    color=[colors[label] for label, _ in feature_names],
)
axis.bar(
    x + width / 2,
    worst_mae,
    width,
    label="Worst fold MAE",
    color=[colors[label] for label, _ in feature_names],
    alpha=0.48,
    hatch="//",
)
for position, value in zip(x - width / 2, mean_mae):
    axis.text(position, value + 25, f"{value:,.0f}", ha="center", fontsize=9)
axis.set_xticks(x, [label for label, _ in feature_names])
axis.set_ylabel("MAE (MW)")
axis.set_title(
    "V3 feature ablation: weather and embedded generation provide real forecast signal",
    fontweight="bold",
)
axis.legend()
axis.grid(axis="y", alpha=0.15)
fig.tight_layout()
fig.savefig(FIGURES / "01_feature_ablation.png", dpi=300, bbox_inches="tight")
plt.close(fig)


progression = [
    ("Weekly\nnaive", ridge["benchmarks"]["weekly_seasonal_naive"]["summary"]["mean_fold_mae_mw"], "#7f8c8d"),
    ("V2 Ridge", ridge["candidates"]["v2_ridge_reproduced"]["summary"]["mean_fold_mae_mw"], colors["V2"]),
    ("Full\nexogenous", ridge["candidates"]["v3_full_recent730_a1"]["summary"]["mean_fold_mae_mw"], colors["Full"]),
    ("Spline\nRidge", nonlinear["spline_candidates"]["spline_ridge_a1"]["summary"]["mean_fold_mae_mw"], "#1abc9c"),
    ("Direct\nRidge", dynamic["direct_ridge_candidates"]["direct_v3_ridge_a0"]["summary"]["mean_fold_mae_mw"], "#16a085"),
    ("Selected\nblend", point["selected_summary"]["mean_fold_mae_mw"], colors["Selected"]),
    ("NESO", ridge["benchmarks"]["neso_day_ahead"]["summary"]["mean_fold_mae_mw"], colors["NESO"]),
]
fig, axes = plt.subplots(1, 2, figsize=(17, 7))
bars = axes[0].bar(
    [x[0] for x in progression], [x[1] for x in progression], color=[x[2] for x in progression]
)
for bar, (_, value, _) in zip(bars, progression):
    axes[0].text(bar.get_x() + bar.get_width() / 2, value + 28, f"{value:,.0f}", ha="center")
axes[0].set_ylim(0, max(x[1] for x in progression) * 1.15)
axes[0].set_ylabel("Mean rolling-fold MAE (MW)")
axes[0].set_title("Each justified layer improves the research forecast", fontweight="bold")
axes[0].grid(axis="y", alpha=0.15)

fold_order = [fold["name"] for fold in json.loads((ROOT / "configs/event_blind_v3_experiment.json").read_text())["validation_folds"]]
series = {
    "V2 Ridge": ridge["candidates"]["v2_ridge_reproduced"]["folds"],
    "Spline Ridge": nonlinear["spline_candidates"]["spline_ridge_a1"]["folds"],
    "Selected blend": point["candidates"][point["selected_point_model"]]["folds"],
    "NESO": ridge["benchmarks"]["neso_day_ahead"]["folds"],
}
for label, folds in series.items():
    axes[1].plot(
        np.arange(len(fold_order)),
        [folds[name]["mae_mw"] for name in fold_order],
        marker="o",
        linewidth=2,
        label=label,
    )
axes[1].set_xticks(np.arange(len(fold_order)), [name.replace("_", "\n") for name in fold_order], fontsize=8)
axes[1].set_ylabel("Fold MAE (MW)")
axes[1].set_title("The gain transfers across seasons", fontweight="bold")
axes[1].legend()
axes[1].grid(alpha=0.15)
fig.suptitle("Event-blind v3 development performance", fontsize=18, fontweight="bold")
fig.tight_layout(rect=[0, 0, 1, 0.95])
fig.savefig(FIGURES / "02_model_progression.png", dpi=300, bbox_inches="tight")
plt.close(fig)


def fold_mean_acf(values_column: str) -> np.ndarray:
    values = []
    for _, fold in selected.groupby("fold"):
        residual = fold[values_column].to_numpy(dtype=float)
        if values_column == "selected_residual_mw_squared":
            residual = (fold["selected_residual_mw"].to_numpy() - fold["selected_residual_mw"].mean()) ** 2
        values.append(acf(residual, nlags=336, fft=True))
    return np.mean(values, axis=0)


selected["selected_residual_mw_squared"] = selected["selected_residual_mw"] ** 2
raw_acf = fold_mean_acf("selected_residual_mw")
squared_acf = fold_mean_acf("selected_residual_mw_squared")
lags = np.arange(337)
fig, axes = plt.subplots(2, 2, figsize=(16, 10))
axes[0, 0].plot(lags[1:], raw_acf[1:], color="#00e5ff")
axes[0, 0].set_title("Mean residual ACF across folds", fontweight="bold")
axes[0, 0].set_ylabel("ACF")
axes[0, 1].plot(lags[1:], squared_acf[1:], color="#e74c3c")
axes[0, 1].set_title("Mean squared-residual ACF across folds", fontweight="bold")
for axis in axes[0]:
    for lag in [48, 96, 336]:
        axis.axvline(lag, color="#777777", linestyle="--", linewidth=0.8)
    axis.set_xlabel("Lag (half-hours)")
    axis.grid(alpha=0.15)

model_names = ["constant", "garch", "structured"]
labels = ["Constant", "GARCH", "Structured"]
coverage_80 = [interval["models"][name]["summary"]["mean_80_coverage"] for name in model_names]
coverage_95 = [interval["models"][name]["summary"]["mean_95_coverage"] for name in model_names]
x = np.arange(3)
width = 0.34
axes[1, 0].bar(x - width / 2, coverage_80, width, label="80% interval", color="#2ecc71")
axes[1, 0].bar(x + width / 2, coverage_95, width, label="95% interval", color="#9b59b6")
axes[1, 0].axhline(0.8, color="#2ecc71", linestyle="--", linewidth=0.8)
axes[1, 0].axhline(0.95, color="#9b59b6", linestyle="--", linewidth=0.8)
axes[1, 0].set_xticks(x, labels)
axes[1, 0].set_ylim(0.7, 1.0)
axes[1, 0].set_ylabel("Leave-one-fold-out coverage")
axes[1, 0].set_title("Conformal calibration reaches nominal coverage", fontweight="bold")
axes[1, 0].legend()
axes[1, 0].grid(axis="y", alpha=0.15)

widths = [interval["models"][name]["summary"]["mean_95_interval_width_mw"] for name in model_names]
bars = axes[1, 1].bar(labels, widths, color=["#7f8c8d", "#ff9f43", "#00e5ff"])
for bar, value in zip(bars, widths):
    axes[1, 1].text(bar.get_x() + bar.get_width() / 2, value + 45, f"{value:,.0f}", ha="center")
axes[1, 1].set_ylabel("Mean 95% interval width (MW)")
axes[1, 1].set_title("Structured scale is the sharpest calibrated model", fontweight="bold")
axes[1, 1].grid(axis="y", alpha=0.15)
fig.suptitle("V3 residual and uncertainty diagnostics", fontsize=18, fontweight="bold")
fig.tight_layout(rect=[0, 0, 1, 0.95])
fig.savefig(FIGURES / "03_residual_interval_diagnostics.png", dpi=300, bbox_inches="tight")
plt.close(fig)
