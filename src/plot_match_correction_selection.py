"""Plot general-fixture and tournament-specific correction selection results."""
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


def label_bars(axis, bars, decimals=0):
    for bar in bars:
        value = bar.get_height()
        axis.text(
            bar.get_x() + bar.get_width() / 2,
            value + axis.get_ylim()[1] * 0.015,
            f"{value:,.{decimals}f}",
            ha="center",
            fontsize=9,
        )


plt.style.use("dark_background")

# General England-fixture correction.
general = json.loads((MODEL_DIR / "match_correction_selection.json").read_text())
general_predictions = pd.read_csv(MODEL_DIR / "match_correction_lomo_predictions.csv")
selected_candidate = general["best_correction_candidate"]
selected_predictions = general_predictions.loc[
    general_predictions["candidate"].eq(selected_candidate)
].copy()
selected_predictions["blind_ae"] = (
    selected_predictions["demand_mw"]
    - selected_predictions["event_blind_forecast_mw"]
).abs()
selected_predictions["aware_ae"] = (
    selected_predictions["demand_mw"]
    - selected_predictions["match_aware_forecast_mw"]
).abs()
per_match = selected_predictions.groupby(["match_id", "opponent"], as_index=False).agg(
    blind_mae=("blind_ae", "mean"), aware_mae=("aware_ae", "mean")
)
per_match["mae_change"] = per_match["aware_mae"] - per_match["blind_mae"]
per_match = per_match.sort_values("mae_change")

fig, axes = plt.subplots(1, 2, figsize=(16, 7.5), gridspec_kw={"width_ratios": [1, 1.7]})
candidate_names = ["No correction", "Match only", "Match + halftime", "Four window"]
candidate_values = [
    general["baseline"]["mae_mw"],
    general["candidates"]["scheduled_match_only"]["mae_mw"],
    general["candidates"]["match_plus_halftime"]["mae_mw"],
    general["candidates"]["four_window"]["mae_mw"],
]
bars = axes[0].bar(
    candidate_names,
    candidate_values,
    color=["#f5f5f5", "#8e44ad", "#3498db", "#00bcd4"],
    edgecolor="white",
    linewidth=0.6,
)
axes[0].set_ylim(1050, 1175)
label_bars(axes[0], bars, decimals=1)
axes[0].tick_params(axis="x", rotation=18)
axes[0].set_ylabel("Leave-one-match-out MAE (MW)")
axes[0].set_title("No general correction passes the MAE gate", fontweight="bold")
axes[0].grid(axis="y", alpha=0.16)

bar_colors = np.where(per_match["mae_change"].lt(0), "#2ecc71", "#e74c3c")
axes[1].barh(
    np.arange(len(per_match)),
    per_match["mae_change"],
    color=bar_colors,
    alpha=0.85,
)
axes[1].axvline(0, color="white", linewidth=1)
axes[1].set_yticks(np.arange(len(per_match)), per_match["opponent"], fontsize=8)
axes[1].set_xlabel("Four-window MAE change (MW); negative is improvement")
axes[1].set_title("Effects vary substantially across the 23 fixtures", fontweight="bold")
axes[1].grid(axis="x", alpha=0.16)

fig.suptitle("General England-fixture correction: historical LOMO validation", fontsize=17, fontweight="bold")
fig.tight_layout(rect=[0, 0, 1, 0.94])
fig.savefig(FIGURES / "05_general_match_correction_selection.png", dpi=300, bbox_inches="tight")
plt.close(fig)


# Tournament-specific transfer experiment.
tournament = json.loads((MODEL_DIR / "tournament_correction_selection.json").read_text())
four = tournament["candidates"]["four_window"]
fig, axes = plt.subplots(1, 3, figsize=(18, 6.5), gridspec_kw={"width_ratios": [1.2, 1.2, 1.6]})

tournament_names = ["No correction", "Match only", "Match + halftime", "Four window"]
tournament_values = [
    tournament["baseline"]["mae_mw"],
    tournament["candidates"]["scheduled_match_only"]["mae_mw"],
    tournament["candidates"]["match_plus_halftime"]["mae_mw"],
    four["mae_mw"],
]
bars = axes[0].bar(
    tournament_names,
    tournament_values,
    color=["#f5f5f5", "#8e44ad", "#3498db", "#00bcd4"],
    edgecolor="white",
    linewidth=0.6,
)
axes[0].set_ylim(0, 2100)
label_bars(axes[0], bars)
axes[0].tick_params(axis="x", rotation=18)
axes[0].set_ylabel("Cross-edition MAE (MW)")
axes[0].set_title("Four windows transfer best", fontweight="bold")
axes[0].grid(axis="y", alpha=0.16)

editions = ["UEFA EURO 2020", "FIFA World Cup 2022"]
x = np.arange(len(editions))
width = 0.34
blind_values = [four["edition_transfer"][edition]["event_blind"]["mae_mw"] for edition in editions]
aware_values = [four["edition_transfer"][edition]["match_aware"]["mae_mw"] for edition in editions]
blind_bars = axes[1].bar(x - width / 2, blind_values, width, label="Event-blind", color="#f5f5f5")
aware_bars = axes[1].bar(x + width / 2, aware_values, width, label="Match-aware", color="#00bcd4")
axes[1].set_xticks(x, ["EURO 2020\ntrained on WC 2022", "World Cup 2022\ntrained on EURO 2020"])
axes[1].set_ylabel("MAE (MW)")
axes[1].set_ylim(0, 2300)
axes[1].set_title("Whole-edition transfer test", fontweight="bold")
axes[1].legend()
axes[1].grid(axis="y", alpha=0.16)
label_bars(axes[1], blind_bars)
label_bars(axes[1], aware_bars)

feature_labels = ["Pregame", "Scheduled match", "Halftime extra", "Post-match"]
feature_keys = [
    "pregame_overlap_fraction",
    "scheduled_match_overlap_fraction",
    "halftime_proxy_overlap_fraction",
    "postmatch_overlap_fraction",
]
estimates = np.array([four["final_coefficients"][key]["estimate_mw"] for key in feature_keys])
low = np.array([four["final_coefficients"][key]["cluster_bootstrap_95_low_mw"] for key in feature_keys])
high = np.array([four["final_coefficients"][key]["cluster_bootstrap_95_high_mw"] for key in feature_keys])
y = np.arange(len(feature_keys))
axes[2].errorbar(
    estimates,
    y,
    xerr=np.vstack([estimates - low, high - estimates]),
    fmt="o",
    color="#00bcd4",
    ecolor="#7fdbff",
    capsize=5,
    markersize=8,
)
axes[2].axvline(0, color="white", linestyle="--", linewidth=1)
axes[2].set_yticks(y, feature_labels)
axes[2].invert_yaxis()
axes[2].set_xlabel("Forecast increment (MW)")
axes[2].set_title("Final coefficients and fixture-bootstrap 95% intervals", fontweight="bold")
axes[2].grid(axis="x", alpha=0.16)

fig.suptitle("Tournament-specific correction selected before opening EURO 2024", fontsize=17, fontweight="bold")
fig.tight_layout(rect=[0, 0, 1, 0.93])
fig.savefig(FIGURES / "06_tournament_correction_selection.png", dpi=300, bbox_inches="tight")
plt.close(fig)
