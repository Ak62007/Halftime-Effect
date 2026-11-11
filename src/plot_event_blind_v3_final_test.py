"""Plot the locked event-blind v3 January--March 2026 final test."""
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
result = json.loads((MODEL_DIR / "final_test_evaluation.json").read_text())
predictions = pd.read_csv(MODEL_DIR / "final_test_predictions.csv")
predictions["timestamp_utc"] = pd.to_datetime(predictions["timestamp_utc"], utc=True)
predictions["timestamp_london"] = predictions["timestamp_utc"].dt.tz_convert(
    "Europe/London"
)
plt.style.use("dark_background")
colors = {
    "Weekly naive": "#7f8c8d",
    "V2": "#3498db",
    "V3 base": "#1abc9c",
    "V3 locked": "#00e5ff",
    "NESO": "#ffb300",
    "Actual": "#f5f5f5",
}


fig, axes = plt.subplots(1, 2, figsize=(16, 7))
metric_keys = [
    ("Weekly naive", "weekly_seasonal_naive"),
    ("V2", "v2_locked_spec_refit"),
    ("V3 base", "v3_spline_base"),
    ("V3 locked", "v3_locked"),
    ("NESO*", "neso_day_ahead_available_rows"),
]
values = [result["point_metrics"][key]["mae_mw"] for _, key in metric_keys]
bar_colors = [
    colors["Weekly naive"],
    colors["V2"],
    colors["V3 base"],
    colors["V3 locked"],
    colors["NESO"],
]
bars = axes[0].bar([x[0] for x in metric_keys], values, color=bar_colors)
for bar, value in zip(bars, values):
    axes[0].text(bar.get_x() + bar.get_width() / 2, value + 45, f"{value:,.0f}", ha="center")
axes[0].set_ylim(0, max(values) * 1.16)
axes[0].set_ylabel("Final-test MAE (MW)")
axes[0].set_title("V3 materially improves the independent research forecast", fontweight="bold")
axes[0].text(
    0.99,
    0.98,
    "* NESO: 4,222 cutoff-available rows",
    transform=axes[0].transAxes,
    ha="right",
    va="top",
    fontsize=9,
    color="#bbbbbb",
)
axes[0].grid(axis="y", alpha=0.15)

months = ["January", "February", "March"]
x = np.arange(3)
width = 0.26
for offset, (label, key) in zip(
    [-width, 0, width], [("V2", "v2"), ("V3 locked", "v3"), ("NESO", "neso_available_rows")]
):
    month_values = [
        result["month_metrics"][str(month)][key]["mae_mw"] for month in [1, 2, 3]
    ]
    axes[1].bar(x + offset, month_values, width, label=label, color=colors[label])
axes[1].set_xticks(x, months)
axes[1].set_ylabel("Monthly MAE (MW)")
axes[1].set_title("V3 improves v2 in every final-test month", fontweight="bold")
axes[1].legend()
axes[1].grid(axis="y", alpha=0.15)
fig.suptitle("Event-blind v3: untouched January–March 2026 test", fontsize=18, fontweight="bold")
fig.tight_layout(rect=[0, 0, 1, 0.94])
fig.savefig(FIGURES / "04_final_test_performance.png", dpi=300, bbox_inches="tight")
plt.close(fig)


for name, forecast in [
    ("v2", "v2_forecast_mw"),
    ("v3", "v3_forecast_mw"),
    ("neso", "neso_day_ahead_forecast_mw"),
]:
    predictions[f"{name}_error"] = predictions["demand_mw"] - predictions[forecast]
    predictions[f"{name}_ae"] = predictions[f"{name}_error"].abs()
daily = predictions.groupby("settlement_date").agg(
    v2_mae=("v2_ae", "mean"),
    v3_mae=("v3_ae", "mean"),
    neso_mae=("neso_ae", "mean"),
    v3_bias=("v3_error", "mean"),
)
daily.index = pd.to_datetime(daily.index)
fig, axes = plt.subplots(2, 1, figsize=(16, 9), sharex=True)
axes[0].plot(daily.index, daily["v2_mae"], color=colors["V2"], label="V2")
axes[0].plot(daily.index, daily["v3_mae"], color=colors["V3 locked"], label="V3 locked", linewidth=2)
axes[0].plot(daily.index, daily["neso_mae"], color=colors["NESO"], label="NESO", alpha=0.9)
axes[0].set_ylabel("Daily MAE (MW)")
axes[0].set_title("Large regime-specific misses remain", fontweight="bold")
axes[0].legend()
axes[0].grid(alpha=0.15)
axes[1].bar(
    daily.index,
    daily["v3_bias"],
    color=np.where(daily["v3_bias"].ge(0), "#e74c3c", "#3498db"),
    width=0.8,
)
axes[1].axhline(0, color="white", linewidth=0.8)
axes[1].set_ylabel("V3 daily mean error\nactual − forecast (MW)")
axes[1].set_xlabel("London settlement date")
axes[1].set_title("The final-test deterioration is dominated by under-forecast days", fontweight="bold")
axes[1].grid(axis="y", alpha=0.15)
fig.tight_layout()
fig.savefig(FIGURES / "05_final_test_daily_errors.png", dpi=300, bbox_inches="tight")
plt.close(fig)


window = predictions.loc[
    predictions["timestamp_london"].between(
        pd.Timestamp("2026-01-01", tz="Europe/London"),
        pd.Timestamp("2026-01-15", tz="Europe/London"),
        inclusive="left",
    )
].copy()
q95 = 2.8900806591156853
lower = window["v3_forecast_mw"] - q95 * window["structured_sigma_mw"]
upper = window["v3_forecast_mw"] + q95 * window["structured_sigma_mw"]
fig, axis = plt.subplots(figsize=(17, 7))
axis.fill_between(
    window["timestamp_london"], lower, upper, color=colors["V3 locked"], alpha=0.14, label="Locked nominal 95% interval"
)
axis.plot(window["timestamp_london"], window["demand_mw"], color=colors["Actual"], linewidth=2, label="Actual")
axis.plot(window["timestamp_london"], window["v2_forecast_mw"], color=colors["V2"], linewidth=1.0, label="V2")
axis.plot(window["timestamp_london"], window["v3_forecast_mw"], color=colors["V3 locked"], linewidth=1.6, label="V3 locked")
axis.plot(window["timestamp_london"], window["neso_day_ahead_forecast_mw"], color=colors["NESO"], linewidth=1.1, label="NESO")
axis.set_ylabel("Demand / forecast (MW)")
axis.set_xlabel("London time")
axis.set_title("First two final-test weeks: v3 captures shape but misses several daily levels", fontweight="bold")
axis.legend(ncol=5, fontsize=9)
axis.grid(alpha=0.14)
fig.tight_layout()
fig.savefig(FIGURES / "06_final_test_first_two_weeks.png", dpi=300, bbox_inches="tight")
plt.close(fig)


residual = predictions["v3_residual_mw"].to_numpy()
standardized = predictions["standardized_residual"].to_numpy()
raw_acf = acf(residual, nlags=336, fft=True)
standardized_acf = acf(standardized, nlags=336, fft=True)
raw_squared = acf((residual - residual.mean()) ** 2, nlags=336, fft=True)
standardized_squared = acf((standardized - standardized.mean()) ** 2, nlags=336, fft=True)
lags = np.arange(337)
fig, axes = plt.subplots(1, 3, figsize=(18, 6))
axes[0].plot(lags[1:], raw_acf[1:], color=colors["V3 locked"], label="Raw")
axes[0].plot(lags[1:], standardized_acf[1:], color="#2ecc71", label="Standardized")
axes[0].set_title("Residual dependence remains", fontweight="bold")
axes[0].set_ylabel("ACF")
axes[0].set_xlabel("Lag (half-hours)")
axes[0].legend()
axes[1].plot(lags[1:], raw_squared[1:], color="#e74c3c", label="Raw squared")
axes[1].plot(lags[1:], standardized_squared[1:], color="#2ecc71", label="Standardized squared")
axes[1].set_title("Variance standardization helps, but is incomplete", fontweight="bold")
axes[1].set_ylabel("Squared-residual ACF")
axes[1].set_xlabel("Lag (half-hours)")
axes[1].legend()
for axis in axes[:2]:
    for lag in [48, 96, 336]:
        axis.axvline(lag, color="#777777", linestyle="--", linewidth=0.8)
    axis.grid(alpha=0.14)
development = [0.8009312800470266, 0.9502973824413566]
final = [result["interval_metrics"]["coverage_80"], result["interval_metrics"]["coverage_95"]]
x = np.arange(2)
width = 0.34
axes[2].bar(x - width / 2, development, width, label="Development LOO", color="#9b59b6")
axes[2].bar(x + width / 2, final, width, label="Final test", color=colors["V3 locked"])
axes[2].axhline(0.8, color="#888888", linestyle="--", linewidth=0.8)
axes[2].axhline(0.95, color="#888888", linestyle="--", linewidth=0.8)
axes[2].set_xticks(x, ["80% interval", "95% interval"])
axes[2].set_ylim(0.6, 1.0)
axes[2].set_ylabel("Observed coverage")
axes[2].set_title("Locked intervals under-cover the new season", fontweight="bold")
axes[2].legend()
axes[2].grid(axis="y", alpha=0.14)
fig.suptitle("V3 final-test residual and interval diagnostics", fontsize=18, fontweight="bold")
fig.tight_layout(rect=[0, 0, 1, 0.94])
fig.savefig(FIGURES / "07_final_test_residual_intervals.png", dpi=300, bbox_inches="tight")
plt.close(fig)
