"""Plot the locked event-blind v2 January--March 2025 final test."""
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

result = json.loads((MODEL_DIR / "final_test_evaluation.json").read_text())
predictions = pd.read_csv(MODEL_DIR / "final_test_predictions.csv")
predictions["timestamp_utc"] = pd.to_datetime(predictions["timestamp_utc"], utc=True)
predictions["timestamp_london"] = predictions["timestamp_utc"].dt.tz_convert(
    "Europe/London"
)

colors = {
    "Weekly naive": "#9b59b6",
    "V1": "#3498db",
    "V2 locked": "#00e5ff",
    "NESO": "#ffb300",
    "Actual": "#f5f5f5",
}
plt.style.use("dark_background")

fig, axes = plt.subplots(1, 3, figsize=(18, 7))
metric_keys = [
    ("Weekly naive", "weekly_seasonal_naive"),
    ("V1", "v1_calendar_weekly_lag"),
    ("V2 locked", "v2_locked"),
    ("NESO", "neso_day_ahead"),
]
mae = [result["point_metrics"][key]["mae_mw"] for _, key in metric_keys]
bars = axes[0].bar(
    [label for label, _ in metric_keys],
    mae,
    color=[colors[label] for label, _ in metric_keys],
    edgecolor="white",
    linewidth=0.5,
)
for bar, value in zip(bars, mae):
    axes[0].text(bar.get_x() + bar.get_width() / 2, value + 60, f"{value:,.0f}", ha="center")
axes[0].set_ylim(0, max(mae) * 1.16)
axes[0].set_ylabel("Final-test MAE (MW)")
axes[0].set_title("V2 materially improves the research forecast", fontweight="bold")
axes[0].grid(axis="y", alpha=0.15)

months = ["January", "February", "March"]
x = np.arange(3)
width = 0.26
for offset, (label, key) in zip(
    [-width, 0, width], [("V1", "v1"), ("V2 locked", "v2"), ("NESO", "neso")]
):
    values = [result["month_metrics"][str(month)][key]["mae_mw"] for month in [1, 2, 3]]
    axes[1].bar(x + offset, values, width, label=label, color=colors[label])
axes[1].set_xticks(x, months)
axes[1].set_ylabel("Monthly MAE (MW)")
axes[1].set_title("V2 improvement persists in all three months", fontweight="bold")
axes[1].legend()
axes[1].grid(axis="y", alpha=0.15)

predictions["v1_ae"] = (predictions["demand_mw"] - predictions["v1_forecast_mw"]).abs()
predictions["v2_ae"] = (predictions["demand_mw"] - predictions["v2_forecast_mw"]).abs()
predictions["neso_ae"] = (
    predictions["demand_mw"] - predictions["neso_day_ahead_forecast_mw"]
).abs()
daily = predictions.groupby("settlement_date").agg(
    v1=("v1_ae", "mean"), v2=("v2_ae", "mean"), neso=("neso_ae", "mean")
)
daily.index = pd.to_datetime(daily.index)
axes[2].plot(daily.index, daily["v1"], color=colors["V1"], label="V1", alpha=0.85)
axes[2].plot(daily.index, daily["v2"], color=colors["V2 locked"], label="V2 locked", linewidth=1.8)
axes[2].plot(daily.index, daily["neso"], color=colors["NESO"], label="NESO", alpha=0.9)
axes[2].set_ylabel("Daily MAE (MW)")
axes[2].set_title("Large day-specific misses remain", fontweight="bold")
axes[2].legend()
axes[2].grid(alpha=0.15)

fig.suptitle("Event-blind v2: untouched January–March 2025 test", fontsize=18, fontweight="bold")
fig.tight_layout(rect=[0, 0, 1, 0.94])
fig.savefig(FIGURES / "04_final_test_performance.png", dpi=300, bbox_inches="tight")
plt.close(fig)


window = predictions.loc[
    predictions["timestamp_london"].between(
        pd.Timestamp("2025-01-01", tz="Europe/London"),
        pd.Timestamp("2025-01-15", tz="Europe/London"),
        inclusive="left",
    )
].copy()
lower = window["v2_forecast_mw"] - 1.96 * window["garch_sigma_mw"]
upper = window["v2_forecast_mw"] + 1.96 * window["garch_sigma_mw"]
fig, axis = plt.subplots(figsize=(17, 7))
axis.fill_between(
    window["timestamp_london"], lower, upper, color="#00e5ff", alpha=0.13, label="V2 nominal 95% interval"
)
axis.plot(window["timestamp_london"], window["demand_mw"], color=colors["Actual"], linewidth=2, label="Actual")
axis.plot(window["timestamp_london"], window["v1_forecast_mw"], color=colors["V1"], linewidth=1.1, label="V1")
axis.plot(window["timestamp_london"], window["v2_forecast_mw"], color=colors["V2 locked"], linewidth=1.5, label="V2 locked")
axis.plot(window["timestamp_london"], window["neso_day_ahead_forecast_mw"], color=colors["NESO"], linewidth=1.2, label="NESO")
axis.set_ylabel("Demand / forecast (MW)")
axis.set_xlabel("London time")
axis.set_title("First two final-test weeks: New Year level shift challenges every research model", fontweight="bold")
axis.legend(ncol=5, fontsize=9)
axis.grid(alpha=0.14)
fig.tight_layout()
fig.savefig(FIGURES / "05_final_test_first_two_weeks.png", dpi=300, bbox_inches="tight")
plt.close(fig)


residual = predictions["v2_residual_mw"].to_numpy()
standardized = predictions["standardized_residual"].to_numpy()
raw_acf = acf(residual, nlags=336, fft=True)
standardized_acf = acf(standardized, nlags=336, fft=True)
raw_squared = acf((residual - residual.mean()) ** 2, nlags=336, fft=True)
standardized_squared = acf((standardized - standardized.mean()) ** 2, nlags=336, fft=True)
lags = np.arange(337)
fig, axes = plt.subplots(2, 1, figsize=(16, 10), sharex=True)
axes[0].plot(lags[1:], raw_acf[1:], color="#00e5ff", label="V2 residual")
axes[0].plot(lags[1:], standardized_acf[1:], color="#2ecc71", label="GARCH-standardized")
axes[0].set_ylabel("Residual ACF")
axes[0].set_title("GARCH cannot remove mean dependence", fontweight="bold")
axes[0].legend()
axes[0].grid(alpha=0.14)
axes[1].plot(lags[1:], raw_squared[1:], color="#e74c3c", label="Squared residual")
axes[1].plot(lags[1:], standardized_squared[1:], color="#2ecc71", label="Standardized squared residual")
axes[1].set_ylabel("Squared-residual ACF")
axes[1].set_xlabel("Lag (half-hours)")
axes[1].set_title("Conditional variance remains incompletely specified", fontweight="bold")
axes[1].legend()
axes[1].grid(alpha=0.14)
for axis in axes:
    for lag in [48, 96, 336]:
        axis.axvline(lag, color="#777777", linestyle="--", linewidth=0.8)
fig.suptitle("Final-test residual diagnostics: the stronger model is still not white noise", fontsize=18, fontweight="bold")
fig.tight_layout(rect=[0, 0, 1, 0.95])
fig.savefig(FIGURES / "06_final_test_residual_diagnostics.png", dpi=300, bbox_inches="tight")
plt.close(fig)
