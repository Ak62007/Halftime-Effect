"""Plot development-only event-blind v2 model selection and diagnostics."""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from statsmodels.tsa.stattools import acf


ROOT = Path(__file__).resolve().parents[1]
MODEL_DIR = ROOT / "data/processed/event_blind_v2/modeling"
FIGURES = ROOT / "docs/figures/event_blind_v2"
FIGURES.mkdir(parents=True, exist_ok=True)

regression = json.loads((MODEL_DIR / "regression_candidate_metrics.json").read_text())
ar_results = json.loads((MODEL_DIR / "ar_error_candidate_metrics.json").read_text())
direct = json.loads((MODEL_DIR / "direct_residual_candidate_metrics.json").read_text())
garch = json.loads((MODEL_DIR / "garch_diagnostics.json").read_text())

models = {
    "Weekly naive": regression["benchmarks"]["weekly_seasonal_naive"],
    "v1 calendar + weekly lag": regression["candidates"]["calendar_weekly_v1"],
    "Multi-lag Ridge": regression["candidates"][regression["best_regression_candidate"]],
    "Ridge + recursive AR": ar_results["candidates"][ar_results["best_ar_error_candidate"]],
    "Ridge + direct ARX": direct["candidates"][direct["best_direct_residual_candidate"]],
    "NESO day-ahead": regression["benchmarks"]["neso_day_ahead"],
}
colors = {
    "Weekly naive": "#9b59b6",
    "v1 calendar + weekly lag": "#3498db",
    "Multi-lag Ridge": "#00bcd4",
    "Ridge + recursive AR": "#2ecc71",
    "Ridge + direct ARX": "#00e5ff",
    "NESO day-ahead": "#ffb300",
}

plt.style.use("dark_background")
fig, axes = plt.subplots(1, 2, figsize=(17, 7))
names = list(models)
mae = [models[name]["summary"]["mean_fold_mae_mw"] for name in names]
bars = axes[0].bar(names, mae, color=[colors[name] for name in names], edgecolor="white", linewidth=0.5)
for bar, value in zip(bars, mae):
    axes[0].text(bar.get_x() + bar.get_width() / 2, value + 35, f"{value:,.0f}", ha="center", fontsize=9)
axes[0].tick_params(axis="x", rotation=24)
axes[0].set_ylabel("Mean rolling-fold MAE (MW)")
axes[0].set_title("Each dynamic stage earns an out-of-sample improvement", fontweight="bold")
axes[0].grid(axis="y", alpha=0.15)
axes[0].set_ylim(0, max(mae) * 1.14)

fold_order = [fold["name"] for fold in json.loads((ROOT / "configs/event_blind_v2_experiment.json").read_text())["validation_folds"]]
for name in names:
    folds = models[name].get("folds", models[name])
    values = [folds[fold]["mae_mw"] for fold in fold_order]
    axes[1].plot(fold_order, values, marker="o", linewidth=1.8, label=name, color=colors[name])
axes[1].set_ylabel("Fold MAE (MW)")
axes[1].set_title("Improvement is present across seasons, but NESO remains far ahead", fontweight="bold")
axes[1].grid(alpha=0.15)
axes[1].legend(fontsize=8, ncol=2)
axes[1].tick_params(axis="x", rotation=18)
fig.suptitle("Event-blind v2 development-only model selection", fontsize=18, fontweight="bold")
fig.tight_layout(rect=[0, 0, 1, 0.94])
fig.savefig(FIGURES / "01_model_selection.png", dpi=300, bbox_inches="tight")
plt.close(fig)


reg_predictions = pd.read_csv(MODEL_DIR / "regression_validation_predictions.csv")
direct_predictions = pd.read_csv(MODEL_DIR / "direct_residual_validation_predictions.csv")
old_column = "forecast_calendar_weekly_v1_mw"
selected_column = "forecast_direct_residual_ridge_a0_mw"
acf_lags = np.arange(337)
old_fold_acf = []
selected_fold_acf = []
for fold in fold_order:
    old = reg_predictions.loc[reg_predictions["fold"].eq(fold)]
    selected = direct_predictions.loc[direct_predictions["fold"].eq(fold)]
    old_fold_acf.append(acf(old["demand_mw"] - old[old_column], nlags=336, fft=True))
    selected_fold_acf.append(
        acf(selected["demand_mw"] - selected[selected_column], nlags=336, fft=True)
    )
old_fold_acf = np.asarray(old_fold_acf)
selected_fold_acf = np.asarray(selected_fold_acf)

fig, axes = plt.subplots(2, 1, figsize=(16, 10), sharex=True)
axes[0].plot(acf_lags[1:], old_fold_acf.mean(axis=0)[1:], color="#3498db", label="v1 mean across folds")
axes[0].plot(acf_lags[1:], selected_fold_acf.mean(axis=0)[1:], color="#00e5ff", label="v2 mean across folds")
axes[0].fill_between(
    acf_lags[1:],
    selected_fold_acf.min(axis=0)[1:],
    selected_fold_acf.max(axis=0)[1:],
    color="#00e5ff",
    alpha=0.12,
    label="v2 fold range",
)
for lag in [48, 96, 336]:
    axes[0].axvline(lag, color="#777777", linestyle="--", linewidth=0.8)
axes[0].set_ylabel("Residual ACF")
axes[0].set_title("V2 reduces daily dependence, but short-run errors remain highly persistent", fontweight="bold")
axes[0].legend()
axes[0].grid(alpha=0.14)

garch_predictions = pd.read_csv(MODEL_DIR / "selected_model_garch_validation.csv")
raw_squared = []
standardized_squared = []
for fold in fold_order:
    subset = garch_predictions.loc[garch_predictions["fold"].eq(fold)]
    raw = subset["selected_residual_mw"].to_numpy()
    standardized = subset["standardized_residual"].to_numpy()
    raw_squared.append(acf((raw - raw.mean()) ** 2, nlags=336, fft=True))
    standardized_squared.append(
        acf((standardized - standardized.mean()) ** 2, nlags=336, fft=True)
    )
raw_squared = np.asarray(raw_squared)
standardized_squared = np.asarray(standardized_squared)
axes[1].plot(acf_lags[1:], raw_squared.mean(axis=0)[1:], color="#e74c3c", label="Raw squared residual")
axes[1].plot(acf_lags[1:], standardized_squared.mean(axis=0)[1:], color="#2ecc71", label="GARCH-standardized squared residual")
for lag in [48, 96, 336]:
    axes[1].axvline(lag, color="#777777", linestyle="--", linewidth=0.8)
axes[1].set_xlabel("Lag (half-hours)")
axes[1].set_ylabel("Squared-residual ACF")
axes[1].set_title("GARCH reduces some daily variance structure, not short-run clustering", fontweight="bold")
axes[1].legend()
axes[1].grid(alpha=0.14)
fig.suptitle("Selected v2 residual and variance diagnostics", fontsize=18, fontweight="bold")
fig.tight_layout(rect=[0, 0, 1, 0.95])
fig.savefig(FIGURES / "02_residual_diagnostics.png", dpi=300, bbox_inches="tight")
plt.close(fig)


fig, axis = plt.subplots(figsize=(13, 6.5))
x = np.arange(len(fold_order))
width = 0.34
coverage_80 = [garch["folds"][fold]["coverage_80"] * 100 for fold in fold_order]
coverage_95 = [garch["folds"][fold]["coverage_95"] * 100 for fold in fold_order]
axis.bar(x - width / 2, coverage_80, width, color="#00bcd4", label="Nominal 80%")
axis.bar(x + width / 2, coverage_95, width, color="#2ecc71", label="Nominal 95%")
axis.axhline(80, color="#00bcd4", linestyle="--", linewidth=1)
axis.axhline(95, color="#2ecc71", linestyle="--", linewidth=1)
axis.set_xticks(x, fold_order)
axis.set_ylim(65, 100)
axis.set_ylabel("Observed interval coverage (%)")
axis.set_title("GARCH day-ahead interval coverage by rolling fold", fontweight="bold")
axis.legend()
axis.grid(axis="y", alpha=0.15)
fig.tight_layout()
fig.savefig(FIGURES / "03_garch_interval_coverage.png", dpi=300, bbox_inches="tight")
plt.close(fig)
