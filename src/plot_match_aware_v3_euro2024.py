"""Plot the locked match-aware-v3 EURO 2024 retrospective diagnostic."""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data/processed/match_aware_v3"
FIGURES = ROOT / "docs/figures/match_aware_v3"
RESULT = json.loads((OUT / "euro_2024_retrospective_evaluation.json").read_text())
OLD = json.loads(
    (ROOT / "data/processed/match_aware/modeling/euro_2024_holdout_evaluation.json").read_text()
)
PREDICTIONS = pd.read_csv(OUT / "euro_2024_retrospective_predictions.csv")
PREDICTIONS["timestamp_utc"] = pd.to_datetime(PREDICTIONS["timestamp_utc"], utc=True)
PREDICTIONS["timestamp_london"] = PREDICTIONS["timestamp_utc"].dt.tz_convert("Europe/London")

plt.style.use("dark_background")
COLORS = {
    "weekly": "#7f8c8d",
    "old": "#3498db",
    "blind": "#00e5ff",
    "aware": "#ffb300",
    "neso": "#2ecc71",
    "actual": "#f5f5f5",
}


def main() -> None:
    current = RESULT["scope_metrics"]["event_window_primary"]
    old = OLD["scope_metrics"]["correction_event_window_primary"]
    labels = ["Weekly\nnaive", "Old\nevent-blind", "Old\nmatch-aware", "V3\nevent-blind", "V3\nmatch-aware", "NESO"]
    values = [
        current["weekly_seasonal_naive"]["mae_mw"],
        old["event_blind"]["mae_mw"],
        old["match_aware"]["mae_mw"],
        current["v3_event_blind"]["mae_mw"],
        current["v3_match_aware"]["mae_mw"],
        current["neso_available_rows"]["mae_mw"],
    ]
    colors = [COLORS["weekly"], COLORS["old"], "#9b59b6", COLORS["blind"], COLORS["aware"], COLORS["neso"]]
    fig, axis = plt.subplots(figsize=(14, 7))
    bars = axis.bar(labels, values, color=colors)
    for bar, value in zip(bars, values):
        axis.text(bar.get_x() + bar.get_width() / 2, value + 25, f"{value:,.0f}", ha="center")
    axis.set_ylim(0, max(values) * 1.17)
    axis.set_ylabel("EURO 2024 event-window MAE (MW)")
    axis.set_title("V3 fixes most baseline error; its locked schedule layer adds no aggregate gain", fontweight="bold")
    axis.grid(axis="y", alpha=0.15)
    fig.tight_layout()
    fig.savefig(FIGURES / "03_euro2024_model_comparison.png", dpi=300, bbox_inches="tight")
    plt.close(fig)

    scopes = [
        ("Primary", "event_window_primary"),
        ("Pregame", "pregame_window"),
        ("Scheduled play", "scheduled_match_window"),
        ("Halftime proxy", "halftime_proxy_window"),
        ("Post-match", "postmatch_window"),
    ]
    blind = [RESULT["scope_metrics"][key]["v3_event_blind"]["mae_mw"] for _, key in scopes]
    aware = [RESULT["scope_metrics"][key]["v3_match_aware"]["mae_mw"] for _, key in scopes]
    x = np.arange(len(scopes))
    width = 0.35
    fig, axis = plt.subplots(figsize=(15, 7))
    axis.bar(x - width / 2, blind, width, color=COLORS["blind"], label="V3 event-blind")
    axis.bar(x + width / 2, aware, width, color=COLORS["aware"], label="V3 + locked schedule shape")
    for position, (before, after) in enumerate(zip(blind, aware)):
        change = after - before
        axis.text(position, max(before, after) + 22, f"{change:+.0f} MW", ha="center", color=COLORS["neso"] if change < 0 else "#e74c3c")
    axis.set_xticks(x, [label for label, _ in scopes])
    axis.set_ylabel("MAE (MW)")
    axis.set_title("Scheduled-play and halftime errors improve, but pre/post errors offset them", fontweight="bold")
    axis.legend()
    axis.grid(axis="y", alpha=0.15)
    fig.tight_layout()
    fig.savefig(FIGURES / "04_euro2024_window_results.png", dpi=300, bbox_inches="tight")
    plt.close(fig)

    event = PREDICTIONS.loc[
        PREDICTIONS[
            ["pregame_overlap_fraction", "scheduled_match_overlap_fraction", "postmatch_overlap_fraction"]
        ].sum(axis=1).gt(0)
    ].copy()
    fig, axes = plt.subplots(4, 2, figsize=(16, 16), sharey=True)
    axes = axes.ravel()
    for axis, (_, rows) in zip(axes, event.groupby("match_id", sort=True)):
        axis.plot(rows["minutes_from_scheduled_kickoff"], rows["demand_mw"], color=COLORS["actual"], linewidth=2.2, label="Actual")
        axis.plot(rows["minutes_from_scheduled_kickoff"], rows["v3_forecast_mw"], color=COLORS["blind"], linewidth=1.6, label="V3")
        axis.plot(rows["minutes_from_scheduled_kickoff"], rows["match_aware_forecast_mw"], color=COLORS["aware"], linewidth=1.6, label="V3 + schedule")
        axis.axvspan(45, 75, color=COLORS["aware"], alpha=0.12)
        axis.axvline(0, color="#777777", linestyle="--", linewidth=0.8)
        axis.set_title(f"England vs {rows['opponent'].iloc[0]}", fontweight="bold")
        axis.grid(alpha=0.12)
    axes[-1].axis("off")
    handles, legend_labels = axes[0].get_legend_handles_labels()
    axes[-1].legend(handles, legend_labels, loc="center", ncol=1, fontsize=12)
    fig.supxlabel("Minutes from scheduled kickoff", y=0.015)
    fig.supylabel("Demand / forecast (MW)")
    fig.suptitle("EURO 2024: the same correction helps some fixtures and harms others", fontsize=18, fontweight="bold")
    fig.tight_layout(rect=[0.03, 0.03, 1, 0.96])
    fig.savefig(FIGURES / "05_euro2024_fixture_paths.png", dpi=300, bbox_inches="tight")
    plt.close(fig)


if __name__ == "__main__":
    main()
