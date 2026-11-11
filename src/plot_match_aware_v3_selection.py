"""Plot historical match-aware-v3 selection results at publication resolution."""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data/processed/match_aware_v3"
FIGURES = ROOT / "docs/figures/match_aware_v3"
FIGURES.mkdir(parents=True, exist_ok=True)
LOCK = json.loads((ROOT / "configs/match_aware_v3_model_lock.json").read_text())
RESULT = json.loads((OUT / "correction_selection.json").read_text())
PREDICTIONS = pd.read_csv(OUT / "correction_cross_edition_predictions.csv")

plt.style.use("dark_background")
COLORS = {"blind": "#00e5ff", "aware": "#ffb300", "gain": "#2ecc71", "loss": "#e74c3c"}


def main() -> None:
    selected = LOCK["schedule_correction"]["name"]
    selected_result = RESULT["candidates"][selected]
    editions = RESULT["historical_editions"]

    labels = ["Pooled", "EURO 2020", "World Cup 2022"]
    blind = [RESULT["baseline"]["mae_mw"]]
    aware = [selected_result["mae_mw"]]
    for edition in editions:
        item = selected_result["edition_transfer"][edition]
        blind.append(item["event_blind"]["mae_mw"])
        aware.append(item["match_aware"]["mae_mw"])

    fig, axes = plt.subplots(1, 2, figsize=(16, 7))
    x = np.arange(len(labels))
    width = 0.34
    bars_blind = axes[0].bar(x - width / 2, blind, width, color=COLORS["blind"], label="V3 event-blind")
    bars_aware = axes[0].bar(x + width / 2, aware, width, color=COLORS["aware"], label="V3 + schedule shape")
    for bars in [bars_blind, bars_aware]:
        for bar in bars:
            axes[0].text(
                bar.get_x() + bar.get_width() / 2,
                bar.get_height() + 35,
                f"{bar.get_height():,.0f}",
                ha="center",
                fontsize=10,
            )
    axes[0].set_xticks(x, labels)
    axes[0].set_ylabel("Cross-edition event-window MAE (MW)")
    axes[0].set_ylim(0, max(blind + aware) * 1.18)
    axes[0].set_title("The shape correction improves both historical editions", fontweight="bold")
    axes[0].legend()
    axes[0].grid(axis="y", alpha=0.15)

    minutes = np.arange(-180, 226)
    coefficients = LOCK["schedule_correction"]["coefficients_mw"]
    correction = np.zeros_like(minutes, dtype=float)
    correction += np.where((-120 <= minutes) & (minutes < 0), coefficients["pregame_overlap_fraction"], 0)
    correction += np.where((0 <= minutes) & (minutes < 105), coefficients["scheduled_match_overlap_fraction"], 0)
    correction += np.where((45 <= minutes) & (minutes < 75), coefficients["halftime_proxy_overlap_fraction"], 0)
    correction += np.where((105 <= minutes) & (minutes < 165), coefficients["postmatch_overlap_fraction"], 0)
    axes[1].plot(minutes, correction, color=COLORS["aware"], linewidth=3)
    axes[1].fill_between(minutes, 0, correction, color=COLORS["aware"], alpha=0.22)
    axes[1].axhline(0, color="white", linewidth=0.8)
    for minute, label in [(0, "Kickoff"), (45, "HT proxy"), (75, "Restart proxy"), (105, "Scheduled end")]:
        axes[1].axvline(minute, color="#777777", linestyle="--", linewidth=0.8)
        axes[1].text(minute + 3, 70, label, rotation=90, va="bottom", fontsize=9, color="#bbbbbb")
    axes[1].set_xlabel("Minutes from scheduled kickoff")
    axes[1].set_ylabel("Locked forecast correction (MW)")
    axes[1].set_title("Selected correction describes shape, not fixture level", fontweight="bold")
    axes[1].grid(axis="y", alpha=0.15)
    fig.suptitle("Match-aware v3 historical selection", fontsize=18, fontweight="bold")
    fig.tight_layout(rect=[0, 0, 1, 0.94])
    fig.savefig(FIGURES / "01_historical_selection.png", dpi=300, bbox_inches="tight")
    plt.close(fig)

    chosen = PREDICTIONS.loc[PREDICTIONS["candidate"].eq(selected)].copy()
    chosen["blind_ae"] = (chosen["demand_mw"] - chosen["v3_forecast_mw"]).abs()
    chosen["aware_ae"] = (chosen["demand_mw"] - chosen["match_aware_forecast_mw"]).abs()
    per_match = chosen.groupby(["tournament_edition", "match_id", "opponent"], as_index=False).agg(
        blind_mae=("blind_ae", "mean"), aware_mae=("aware_ae", "mean")
    )
    per_match["change"] = per_match["aware_mae"] - per_match["blind_mae"]
    per_match = per_match.sort_values(["tournament_edition", "match_id"])
    labels = per_match["opponent"].tolist()
    colors = np.where(per_match["change"].lt(0), COLORS["gain"], COLORS["loss"])
    fig, axis = plt.subplots(figsize=(15, 7))
    axis.bar(labels, per_match["change"], color=colors)
    axis.axhline(0, color="white", linewidth=0.9)
    axis.set_ylabel("Match-aware MAE − event-blind MAE (MW)")
    axis.set_xlabel("England opponent")
    axis.set_title("Average transfer improves, but individual fixtures remain heterogeneous", fontweight="bold")
    axis.tick_params(axis="x", rotation=45)
    axis.grid(axis="y", alpha=0.15)
    fig.tight_layout()
    fig.savefig(FIGURES / "02_historical_fixture_changes.png", dpi=300, bbox_inches="tight")
    plt.close(fig)


if __name__ == "__main__":
    main()
