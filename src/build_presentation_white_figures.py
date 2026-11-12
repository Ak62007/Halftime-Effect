"""Build white-background, presentation-sized versions of the core figures."""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from statsmodels.graphics.tsaplots import plot_acf


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs/presentation/assets/white_plots"
OUT.mkdir(parents=True, exist_ok=True)

NAVY = "#102744"
BLUE = "#2673E8"
TEAL = "#19B7C9"
GREEN = "#39A97B"
PURPLE = "#8E5BB7"
ORANGE = "#F4A62A"
RED = "#E35D52"
GRID = "#D9E0E7"


def presentation_style() -> None:
    plt.style.use("default")
    plt.rcParams.update(
        {
            "figure.facecolor": "white",
            "axes.facecolor": "white",
            "savefig.facecolor": "white",
            "text.color": NAVY,
            "axes.labelcolor": NAVY,
            "axes.edgecolor": "#8795A3",
            "xtick.color": NAVY,
            "ytick.color": NAVY,
            "font.size": 12,
            "axes.titlesize": 15,
            "axes.titleweight": "bold",
            "axes.labelsize": 12,
            "legend.fontsize": 10,
        }
    )


def save(fig: plt.Figure, name: str) -> None:
    fig.savefig(OUT / name, dpi=300, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def demand_figures() -> None:
    data = pd.read_csv(ROOT / "data/processed/demand_development.csv")
    data["timestamp_utc"] = pd.to_datetime(data["timestamp_utc"], utc=True)
    data = data.sort_values("timestamp_utc")
    demand = data.set_index("timestamp_utc")["demand_mw"].astype(float)

    fig, ax = plt.subplots(figsize=(14.5, 5.4))
    plot_acf(
        demand.dropna(),
        lags=336,
        alpha=0.05,
        fft=True,
        ax=ax,
        color=TEAL,
        vlines_kwargs={"color": "#A9B8C5", "linewidth": 0.65},
        marker="o",
        markersize=2.8,
    )
    ax.set_title("Demand autocorrelation through one week")
    ax.set_xlabel("Lag (half-hour periods)")
    ax.set_ylabel("Autocorrelation")
    ax.set_xlim(0, 336)
    ax.set_ylim(-0.18, 1.03)
    ax.set_xticks(np.arange(0, 337, 48))
    ax.grid(axis="y", color=GRID, linewidth=0.8, alpha=0.8)
    fig.tight_layout()
    save(fig, "08_acf_white.png")

    transformed = [
        ("Original electricity demand", demand, "Demand (MW)"),
        ("First difference", demand.diff(), "Change (MW)"),
        ("Daily seasonal difference (lag 48)", demand.diff(48), "Change (MW)"),
        ("Weekly seasonal difference (lag 336)", demand.diff(336), "Change (MW)"),
    ]
    fig, axes = plt.subplots(4, 1, figsize=(14.5, 8.2), sharex=True)
    for ax, (title, series, ylabel) in zip(axes, transformed):
        ax.plot(series.index, series.to_numpy(), color=TEAL, linewidth=0.48)
        ax.axhline(0, color="#8795A3", linewidth=0.7, linestyle="--")
        ax.set_title(title, fontsize=12, pad=5)
        ax.set_ylabel(ylabel, fontsize=10)
        ax.grid(color=GRID, linewidth=0.65, alpha=0.7)
    axes[-1].set_xlabel("Timestamp (UTC)")
    fig.suptitle("Electricity demand and differenced series", fontsize=17, fontweight="bold")
    fig.tight_layout(rect=[0, 0, 1, 0.96])
    save(fig, "09_transformations_white.png")


def v2_model_selection() -> None:
    model_dir = ROOT / "data/processed/event_blind_v2/modeling"
    regression = json.loads((model_dir / "regression_candidate_metrics.json").read_text())
    ar_results = json.loads((model_dir / "ar_error_candidate_metrics.json").read_text())
    direct = json.loads((model_dir / "direct_residual_candidate_metrics.json").read_text())
    models = {
        "Weekly naive": regression["benchmarks"]["weekly_seasonal_naive"],
        "Calendar + weekly lag": regression["candidates"]["calendar_weekly_v1"],
        "Multi-lag Ridge": regression["candidates"][regression["best_regression_candidate"]],
        "Recursive residual AR": ar_results["candidates"][ar_results["best_ar_error_candidate"]],
        "Direct residual ARX": direct["candidates"][direct["best_direct_residual_candidate"]],
        "NESO day-ahead": regression["benchmarks"]["neso_day_ahead"],
    }
    colors = [PURPLE, BLUE, TEAL, GREEN, "#18CFE3", ORANGE]
    names = list(models)
    values = [models[name]["summary"]["mean_fold_mae_mw"] for name in names]
    fig, ax = plt.subplots(figsize=(13.2, 6.3))
    bars = ax.bar(np.arange(len(names)), values, color=colors, width=0.72)
    for bar, value in zip(bars, values):
        ax.text(bar.get_x() + bar.get_width() / 2, value + 35, f"{value:,.0f}", ha="center", fontweight="bold")
    ax.set_xticks(np.arange(len(names)), names, rotation=15, ha="right")
    ax.set_ylabel("Mean rolling-fold MAE (MW)")
    ax.set_title("Chronological validation: each retained model layer reduces error")
    ax.set_ylim(0, max(values) * 1.17)
    ax.grid(axis="y", color=GRID, linewidth=0.8)
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    save(fig, "12_v2_selection_white.png")


def v3_ablation() -> None:
    metrics = json.loads(
        (ROOT / "data/processed/presentation_scope/modeling/ridge_ablation_metrics.json").read_text()
    )
    keys = [
        "v2_ridge_reproduced",
        "v3_calendar",
        "v3_weather",
        "v3_embedded",
        "v3_full_recent730_a1",
    ]
    labels = ["Reproduced Ridge", "Calendar", "Issued weather", "Embedded wind + solar", "All inputs"]
    summaries = [metrics["candidates"][key]["summary"] for key in keys]
    mean = [item["mean_fold_mae_mw"] for item in summaries]
    worst = [item["worst_fold_mae_mw"] for item in summaries]
    colors = [BLUE, PURPLE, GREEN, ORANGE, TEAL]
    x = np.arange(len(labels))
    width = 0.36
    fig, ax = plt.subplots(figsize=(13.2, 6.3))
    bars = ax.bar(x - width / 2, mean, width, color=colors, label="Mean fold MAE")
    ax.bar(x + width / 2, worst, width, color=colors, alpha=0.35, label="Worst fold MAE")
    for bar, value in zip(bars, mean):
        ax.text(bar.get_x() + bar.get_width() / 2, value + 22, f"{value:,.0f}", ha="center", fontweight="bold")
    ax.set_xticks(x, labels, rotation=12, ha="right")
    ax.set_ylabel("MAE (MW)")
    ax.set_title("Forecast weather and embedded generation add predictive signal")
    ax.grid(axis="y", color=GRID, linewidth=0.8)
    ax.spines[["top", "right"]].set_visible(False)
    ax.legend(frameon=False, ncol=2)
    fig.tight_layout()
    save(fig, "13_v3_ablation_white.png")


def euro_holdout() -> None:
    model_dir = ROOT / "data/processed/match_aware/modeling"
    evaluation = json.loads((model_dir / "euro_2024_holdout_evaluation.json").read_text())
    fig, axes = plt.subplots(1, 3, figsize=(16.5, 5.8), gridspec_kw={"width_ratios": [1, 1.15, 1.25]})
    primary = evaluation["scope_metrics"]["correction_event_window_primary"]
    labels = ["Weekly naive", "NESO", "Event-blind", "Match-aware"]
    keys = ["weekly_seasonal_naive", "neso_day_ahead", "event_blind", "match_aware"]
    values = [primary[key]["mae_mw"] for key in keys]
    bars = axes[0].bar(labels, values, color=[PURPLE, ORANGE, "#AEB9C3", TEAL])
    for bar, value in zip(bars, values):
        axes[0].text(bar.get_x() + bar.get_width() / 2, value + 22, f"{value:,.0f}", ha="center", fontweight="bold")
    axes[0].set_ylim(0, 1380)
    axes[0].set_ylabel("MAE (MW)")
    axes[0].set_title("Aggregate event window")
    axes[0].tick_params(axis="x", rotation=18)

    per_match = pd.DataFrame(evaluation["per_match"]).sort_values("mae_change_mw")
    bar_colors = np.where(per_match["mae_change_mw"].lt(0), GREEN, RED)
    axes[1].barh(np.arange(len(per_match)), per_match["mae_change_mw"], color=bar_colors)
    axes[1].axvline(0, color=NAVY, linewidth=1)
    axes[1].set_yticks(np.arange(len(per_match)), per_match["opponent"])
    axes[1].set_xlabel("Match-aware minus event-blind MAE (MW)")
    axes[1].set_title("Only 3 of 7 fixtures improve")

    scope_labels = ["Pregame", "Scheduled match", "Halftime proxy", "Post-match"]
    scope_keys = ["pregame_window", "scheduled_match_window", "halftime_proxy_window", "postmatch_window"]
    blind = [evaluation["scope_metrics"][scope]["event_blind"]["mae_mw"] for scope in scope_keys]
    aware = [evaluation["scope_metrics"][scope]["match_aware"]["mae_mw"] for scope in scope_keys]
    x = np.arange(len(scope_labels))
    width = 0.36
    axes[2].bar(x - width / 2, blind, width, label="Event-blind", color="#AEB9C3")
    axes[2].bar(x + width / 2, aware, width, label="Match-aware", color=TEAL)
    axes[2].set_xticks(x, scope_labels, rotation=15, ha="right")
    axes[2].set_ylabel("MAE (MW)")
    axes[2].set_title("Gains occur outside halftime")
    axes[2].legend(frameon=False)

    for ax in axes:
        ax.grid(axis="y", color=GRID, linewidth=0.75)
        ax.spines[["top", "right"]].set_visible(False)
    fig.suptitle("EURO 2024 match-aware forecast evaluation", fontsize=17, fontweight="bold")
    fig.tight_layout(rect=[0, 0, 1, 0.94])
    save(fig, "16_euro_holdout_white.png")


def main() -> None:
    presentation_style()
    demand_figures()
    v2_model_selection()
    v3_ablation()
    euro_holdout()


if __name__ == "__main__":
    main()
