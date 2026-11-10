"""Plot the locked ordinary-day validation results for the event-blind model."""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
MODEL_DIR = ROOT / "data/processed/match_aware/modeling"
FIGURES = ROOT / "docs/figures/match_aware"
FIGURES.mkdir(parents=True, exist_ok=True)

predictions = pd.read_csv(MODEL_DIR / "ordinary_validation_predictions.csv")
predictions["timestamp_utc"] = pd.to_datetime(predictions["timestamp_utc"], utc=True)
predictions["timestamp_london"] = predictions["timestamp_utc"].dt.tz_convert(
    "Europe/London"
)
metrics = json.loads((MODEL_DIR / "event_blind_metrics.json").read_text())

forecast_columns = {
    "Weekly seasonal naive": "weekly_naive_mw",
    "Selected event-blind": "selected_event_blind_forecast_mw",
    "NESO day-ahead": "neso_day_ahead_forecast_mw",
}
colors = {
    "Actual demand": "#f5f5f5",
    "Weekly seasonal naive": "#9b59b6",
    "Selected event-blind": "#00bcd4",
    "NESO day-ahead": "#ffb300",
}

for label, column in forecast_columns.items():
    predictions[f"absolute_error_{label}"] = (
        predictions["demand_mw"] - predictions[column]
    ).abs()

plt.style.use("dark_background")
fig, axes = plt.subplots(3, 1, figsize=(16, 13), gridspec_kw={"height_ratios": [1, 2, 1.25]})

labels = list(forecast_columns)
mae_values = [
    metrics["benchmarks"]["weekly_seasonal_naive"]["mae_mw"],
    metrics["candidates"][metrics["selected_model"]]["mae_mw"],
    metrics["benchmarks"]["neso_day_ahead"]["mae_mw"],
]
bars = axes[0].bar(
    labels,
    mae_values,
    color=[colors[label] for label in labels],
    edgecolor="white",
    linewidth=0.6,
)
for bar, value in zip(bars, mae_values):
    axes[0].text(
        bar.get_x() + bar.get_width() / 2,
        value + 45,
        f"{value:,.0f} MW",
        ha="center",
        fontsize=11,
    )
axes[0].set_ylabel("MAE (MW; lower is better)")
axes[0].set_ylim(0, max(mae_values) * 1.18)
axes[0].set_title("Ordinary-day validation accuracy", fontweight="bold")
axes[0].grid(axis="y", alpha=0.18)

# A fixed, non-cherry-picked two-week window from the middle of validation.
window = predictions.loc[
    predictions["timestamp_london"].between(
        pd.Timestamp("2024-04-15", tz="Europe/London"),
        pd.Timestamp("2024-04-29", tz="Europe/London"),
        inclusive="left",
    )
]
axes[1].plot(
    window["timestamp_london"],
    window["demand_mw"],
    label="Actual demand",
    color=colors["Actual demand"],
    linewidth=2.0,
    zorder=4,
)
for label, column in forecast_columns.items():
    axes[1].plot(
        window["timestamp_london"],
        window[column],
        label=label,
        color=colors[label],
        linewidth=1.25,
        alpha=0.9,
    )
axes[1].set_ylabel("Demand / forecast (MW)")
axes[1].set_title("Two fixed validation weeks: 15–28 April 2024", fontweight="bold")
axes[1].grid(alpha=0.16)
axes[1].legend(ncol=4, fontsize=9, loc="upper right")

predictions["local_date"] = predictions["timestamp_london"].dt.date
daily_mae = predictions.groupby("local_date")[
    [f"absolute_error_{label}" for label in labels]
].mean()
daily_mae.index = pd.to_datetime(daily_mae.index)
for label in labels:
    axes[2].plot(
        daily_mae.index,
        daily_mae[f"absolute_error_{label}"],
        label=label,
        color=colors[label],
        linewidth=1.25,
        alpha=0.9,
    )
axes[2].set_ylabel("Daily MAE (MW)")
axes[2].set_xlabel("London date")
axes[2].set_title("Error varies substantially from day to day", fontweight="bold")
axes[2].grid(alpha=0.16)
axes[2].legend(ncol=3, fontsize=9, loc="upper right")

fig.suptitle(
    "Event-blind day-ahead forecast: March–May 2024 validation",
    fontsize=18,
    fontweight="bold",
)
fig.text(
    0.5,
    0.012,
    "Validation excludes England match days; Euro 2024 outcomes were not opened.",
    ha="center",
    color="#bbbbbb",
    fontsize=10,
)
fig.tight_layout(rect=[0, 0.025, 1, 0.965])
fig.savefig(FIGURES / "02_event_blind_validation.png", dpi=300, bbox_inches="tight")
plt.close(fig)


fig, axes = plt.subplots(1, 2, figsize=(15, 6.5))
residual = predictions["selected_event_blind_error_mw"]
axes[0].hist(residual, bins=60, color="#00bcd4", alpha=0.8, edgecolor="#111111")
axes[0].axvline(0, color="white", linestyle="--", linewidth=1)
axes[0].axvline(residual.mean(), color="#ffb300", linewidth=1.5, label=f"Mean = {residual.mean():,.0f} MW")
axes[0].set_xlabel("Actual minus forecast (MW)")
axes[0].set_ylabel("Half-hour observations")
axes[0].set_title("Selected-model residual distribution", fontweight="bold")
axes[0].legend()
axes[0].grid(axis="y", alpha=0.15)

slot = predictions["timestamp_london"].dt.hour * 2 + predictions["timestamp_london"].dt.minute // 30
slot_summary = predictions.assign(local_slot=slot).groupby("local_slot")[
    "selected_event_blind_error_mw"
].agg(["mean", "std", "count"])
slot_summary["se95"] = 1.96 * slot_summary["std"] / np.sqrt(slot_summary["count"])
clock_labels = [f"{hour:02d}:00" for hour in range(0, 24, 3)]
clock_positions = list(range(0, 48, 6))
axes[1].plot(slot_summary.index, slot_summary["mean"], color="#00bcd4", linewidth=2)
axes[1].fill_between(
    slot_summary.index,
    slot_summary["mean"] - slot_summary["se95"],
    slot_summary["mean"] + slot_summary["se95"],
    color="#00bcd4",
    alpha=0.2,
    label="95% CI for mean error",
)
axes[1].axhline(0, color="white", linestyle="--", linewidth=1)
axes[1].set_xticks(clock_positions, clock_labels)
axes[1].set_xlabel("London clock time")
axes[1].set_ylabel("Mean actual minus forecast (MW)")
axes[1].set_title("Systematic error by time of day", fontweight="bold")
axes[1].legend()
axes[1].grid(alpha=0.15)

fig.suptitle("Where the event-blind baseline still misses", fontsize=17, fontweight="bold")
fig.tight_layout(rect=[0, 0, 1, 0.94])
fig.savefig(FIGURES / "03_event_blind_error_diagnostics.png", dpi=300, bbox_inches="tight")
plt.close(fig)
