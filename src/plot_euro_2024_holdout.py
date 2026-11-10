"""Plot the one-time EURO 2024 holdout evaluation."""
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

evaluation = json.loads((MODEL_DIR / "euro_2024_holdout_evaluation.json").read_text())
predictions = pd.read_csv(MODEL_DIR / "euro_2024_holdout_predictions.csv")
predictions["timestamp_utc"] = pd.to_datetime(predictions["timestamp_utc"], utc=True)

colors = {
    "Weekly naive": "#9b59b6",
    "NESO day-ahead": "#ffb300",
    "Event-blind": "#f5f5f5",
    "Match-aware": "#00bcd4",
    "Actual": "#f5f5f5",
}
plt.style.use("dark_background")

fig, axes = plt.subplots(1, 3, figsize=(18, 7), gridspec_kw={"width_ratios": [1, 1.25, 1.25]})
primary = evaluation["scope_metrics"]["correction_event_window_primary"]
method_labels = ["Weekly naive", "NESO day-ahead", "Event-blind", "Match-aware"]
method_keys = ["weekly_seasonal_naive", "neso_day_ahead", "event_blind", "match_aware"]
values = [primary[key]["mae_mw"] for key in method_keys]
bars = axes[0].bar(
    method_labels,
    values,
    color=[colors[label] for label in method_labels],
    edgecolor="white",
    linewidth=0.6,
)
axes[0].set_ylim(0, 1350)
for bar, value in zip(bars, values):
    axes[0].text(bar.get_x() + bar.get_width() / 2, value + 25, f"{value:,.0f}", ha="center")
axes[0].tick_params(axis="x", rotation=20)
axes[0].set_ylabel("MAE (MW)")
axes[0].set_title("Locked primary event-window result", fontweight="bold")
axes[0].grid(axis="y", alpha=0.15)

per_match = pd.DataFrame(evaluation["per_match"]).sort_values("mae_change_mw")
bar_colors = np.where(per_match["mae_change_mw"].lt(0), "#2ecc71", "#e74c3c")
axes[1].barh(np.arange(len(per_match)), per_match["mae_change_mw"], color=bar_colors)
axes[1].axvline(0, color="white", linewidth=1)
axes[1].set_yticks(np.arange(len(per_match)), per_match["opponent"])
axes[1].set_xlabel("Match-aware minus event-blind MAE (MW)")
axes[1].set_title("Only 3 of 7 fixtures improve", fontweight="bold")
axes[1].grid(axis="x", alpha=0.15)

scope_labels = ["Pregame", "Scheduled match", "Halftime proxy", "Post-match"]
scope_keys = ["pregame_window", "scheduled_match_window", "halftime_proxy_window", "postmatch_window"]
blind = [evaluation["scope_metrics"][scope]["event_blind"]["mae_mw"] for scope in scope_keys]
aware = [evaluation["scope_metrics"][scope]["match_aware"]["mae_mw"] for scope in scope_keys]
x = np.arange(len(scope_labels))
width = 0.36
axes[2].bar(x - width / 2, blind, width, label="Event-blind", color=colors["Event-blind"])
axes[2].bar(x + width / 2, aware, width, label="Match-aware", color=colors["Match-aware"])
axes[2].set_xticks(x, scope_labels, rotation=16)
axes[2].set_ylabel("MAE (MW)")
axes[2].set_title("Correction helps outside the match, not halftime", fontweight="bold")
axes[2].legend()
axes[2].grid(axis="y", alpha=0.15)

fig.suptitle("EURO 2024: one-time evaluation of the locked tournament correction", fontsize=17, fontweight="bold")
fig.text(
    0.5,
    0.012,
    "Green means lower fixture MAE; the specification was not changed after these outcomes were opened.",
    ha="center",
    color="#bbbbbb",
)
fig.tight_layout(rect=[0, 0.035, 1, 0.94])
fig.savefig(FIGURES / "07_euro_2024_holdout_results.png", dpi=300, bbox_inches="tight")
plt.close(fig)


fig, axes = plt.subplots(4, 2, figsize=(17, 16), sharex=True)
axes = axes.ravel()
for axis, (match_id, match_rows) in zip(axes, predictions.groupby("match_id", sort=False)):
    view = match_rows.loc[
        match_rows["minutes_from_scheduled_kickoff"].between(-180, 240)
    ].sort_values("minutes_from_scheduled_kickoff")
    opponent = view["opponent"].iloc[0]
    axis.plot(
        view["minutes_from_scheduled_kickoff"],
        view["demand_mw"],
        color=colors["Actual"],
        linewidth=2.2,
        label="Actual",
        zorder=5,
    )
    axis.plot(
        view["minutes_from_scheduled_kickoff"],
        view["event_blind_forecast_mw"],
        color="#9b59b6",
        linewidth=1.4,
        label="Event-blind",
    )
    axis.plot(
        view["minutes_from_scheduled_kickoff"],
        view["match_aware_forecast_mw"],
        color=colors["Match-aware"],
        linewidth=1.6,
        label="Match-aware",
    )
    axis.plot(
        view["minutes_from_scheduled_kickoff"],
        view["neso_day_ahead_forecast_mw"],
        color=colors["NESO day-ahead"],
        linewidth=1.2,
        label="NESO day-ahead",
    )
    axis.axvspan(0, 105, color="#3498db", alpha=0.08)
    axis.axvspan(45, 75, color="#ffb300", alpha=0.12)
    axis.axvline(0, color="#aaaaaa", linestyle="--", linewidth=0.8)
    axis.set_title(f"England vs {opponent}", fontweight="bold")
    axis.set_ylabel("MW")
    axis.grid(alpha=0.13)

axes[-1].axis("off")
handles, labels = axes[0].get_legend_handles_labels()
fig.legend(handles, labels, loc="lower center", ncol=4, bbox_to_anchor=(0.5, 0.015))
for axis in axes[:-1]:
    axis.set_xlabel("Minutes from scheduled kickoff")
fig.suptitle(
    "EURO 2024 fixture paths (blue = scheduled match, gold = halftime proxy)",
    fontsize=17,
    fontweight="bold",
)
fig.tight_layout(rect=[0, 0.045, 1, 0.965])
fig.savefig(FIGURES / "08_euro_2024_fixture_forecasts.png", dpi=300, bbox_inches="tight")
plt.close(fig)
