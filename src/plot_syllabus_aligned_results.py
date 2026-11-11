"""Create presentation figures for the syllabus-aligned models only."""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data/processed/syllabus_aligned"
FIGURES = ROOT / "docs/figures/syllabus_aligned"
FIGURES.mkdir(parents=True, exist_ok=True)
RESULT = json.loads((OUT / "results.json").read_text())

plt.style.use("dark_background")
COLORS = ["#7f8c8d", "#00e5ff", "#9b59b6", "#2ecc71"]


def main() -> None:
    metrics = RESULT["ordinary_validation"]["metrics"]
    keys = [
        ("Weekly naive", "weekly_seasonal_naive"),
        ("Fourier regression\n(selected)", "fourier_regression"),
        ("Fourier + ARMA\n(rejected)", "fourier_regression_with_arma_errors"),
        ("NESO", "neso_day_ahead"),
    ]
    values = [metrics[key]["mae_mw"] for _, key in keys]
    fig, axis = plt.subplots(figsize=(12, 7))
    bars = axis.bar([label for label, _ in keys], values, color=COLORS)
    for bar, value in zip(bars, values):
        axis.text(bar.get_x() + bar.get_width() / 2, value + 35, f"{value:,.0f}", ha="center")
    axis.set_ylim(0, max(values) * 1.18)
    axis.set_ylabel("March–May 2024 MAE (MW)")
    axis.set_title("Syllabus-aligned ordinary-day validation", fontweight="bold")
    axis.grid(axis="y", alpha=0.15)
    fig.tight_layout()
    fig.savefig(FIGURES / "01_model_validation.png", dpi=300, bbox_inches="tight")
    plt.close(fig)

    euro = RESULT["euro_2024"]["metrics"]
    scopes = [("Scheduled play", "scheduled_match"), ("Halftime proxy", "halftime_proxy")]
    models = [
        ("Weekly naive", "weekly_seasonal_naive", COLORS[0]),
        ("Fourier regression", "event_blind_fourier_regression", COLORS[1]),
        ("+ match flags", "exploratory_match_aware", "#ffb300"),
        ("NESO", "neso_day_ahead", COLORS[3]),
    ]
    x = np.arange(len(scopes))
    width = 0.19
    fig, axis = plt.subplots(figsize=(13, 7))
    for position, (label, key, color) in enumerate(models):
        values = [euro[scope_key][key]["mae_mw"] for _, scope_key in scopes]
        axis.bar(x + (position - 1.5) * width, values, width, label=label, color=color)
    axis.set_xticks(x, [label for label, _ in scopes])
    axis.set_ylabel("Retrospective EURO 2024 MAE (MW)")
    axis.set_title("Exploratory match flags do not improve the selected baseline", fontweight="bold")
    axis.legend()
    axis.grid(axis="y", alpha=0.15)
    fig.tight_layout()
    fig.savefig(FIGURES / "02_euro2024_results.png", dpi=300, bbox_inches="tight")
    plt.close(fig)

    predictions = pd.read_csv(OUT / "ordinary_validation_predictions.csv")
    predictions["timestamp_utc"] = pd.to_datetime(predictions["timestamp_utc"], utc=True)
    start = pd.Timestamp("2024-03-01", tz="UTC")
    sample = predictions.loc[
        predictions["timestamp_utc"].between(start, start + pd.Timedelta(days=14), inclusive="left")
    ]
    fig, axis = plt.subplots(figsize=(16, 7))
    axis.plot(sample["timestamp_utc"], sample["demand_mw"], color="white", linewidth=2, label="Actual")
    axis.plot(sample["timestamp_utc"], sample["weekly_naive_mw"], color=COLORS[0], linewidth=1, label="Weekly naive")
    axis.plot(sample["timestamp_utc"], sample["fourier_regression_forecast_mw"], color=COLORS[1], linewidth=1.6, label="Fourier regression")
    axis.set_ylabel("Demand / forecast (MW)")
    axis.set_xlabel("UTC time")
    axis.set_title("Selected model captures the recurring demand pattern", fontweight="bold")
    axis.legend()
    axis.grid(alpha=0.14)
    fig.tight_layout()
    fig.savefig(FIGURES / "03_validation_forecast_path.png", dpi=300, bbox_inches="tight")
    plt.close(fig)


if __name__ == "__main__":
    main()
