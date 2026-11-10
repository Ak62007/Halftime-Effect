"""Create versioned, outcome-blind figures for the extended data audit."""
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data/processed/match_aware"
FIGURES = ROOT / "docs/figures/match_aware"
FIGURES.mkdir(parents=True, exist_ok=True)

fixtures = pd.read_csv(DATA / "fixtures_extended.csv")
fixtures["match_date_london"] = pd.to_datetime(fixtures["match_date_london"])

role_order = [
    "historical_sensitivity_event",
    "historical_primary_train",
    "validation_event",
    "bridge_only",
    "event_holdout",
]
role_labels = {
    "historical_sensitivity_event": "2021 sensitivity",
    "historical_primary_train": "2022–23 primary training",
    "validation_event": "March 2024 validation",
    "bridge_only": "June warm-up bridge",
    "event_holdout": "Euro 2024 holdout",
}
colors = {
    "historical_sensitivity_event": "#9b59b6",
    "historical_primary_train": "#3498db",
    "validation_event": "#f1c40f",
    "bridge_only": "#95a5a6",
    "event_holdout": "#e74c3c",
}

plt.style.use("dark_background")
fig, (count_axis, timeline_axis) = plt.subplots(
    2,
    1,
    figsize=(15, 9),
    gridspec_kw={"height_ratios": [1, 2.1]},
)

year_role_counts = (
    fixtures.assign(year=fixtures["match_date_london"].dt.year)
    .groupby(["year", "event_role"], observed=True)
    .size()
    .unstack(fill_value=0)
)
bottom = pd.Series(0, index=year_role_counts.index, dtype=float)
for role in role_order:
    if role not in year_role_counts:
        continue
    values = year_role_counts[role]
    count_axis.bar(
        year_role_counts.index.astype(str),
        values,
        bottom=bottom,
        label=role_labels[role],
        color=colors[role],
        edgecolor="#111111",
        linewidth=0.5,
    )
    bottom = bottom + values

for position, total in enumerate(year_role_counts.sum(axis=1)):
    count_axis.text(position, total + 0.35, str(int(total)), ha="center", fontsize=10)
count_axis.set_ylabel("England fixtures")
count_axis.set_title("Expanded fixture inventory by calendar year", fontweight="bold")
count_axis.set_ylim(0, year_role_counts.sum(axis=1).max() + 3)
count_axis.grid(axis="y", alpha=0.18)
count_axis.legend(ncol=3, fontsize=9, loc="upper left")

role_positions = {role: index for index, role in enumerate(role_order)}
for role in role_order:
    subset = fixtures.loc[fixtures["event_role"].eq(role)]
    tournament = subset["is_tournament_match"].astype(bool)
    timeline_axis.scatter(
        subset.loc[~tournament, "match_date_london"],
        [role_positions[role]] * int((~tournament).sum()),
        marker="o",
        s=75,
        color=colors[role],
        edgecolor="white",
        linewidth=0.7,
        alpha=0.9,
    )
    timeline_axis.scatter(
        subset.loc[tournament, "match_date_london"],
        [role_positions[role]] * int(tournament.sum()),
        marker="*",
        s=150,
        color=colors[role],
        edgecolor="white",
        linewidth=0.7,
        alpha=0.95,
    )

timeline_axis.axvline(pd.Timestamp("2024-06-16"), color="#e74c3c", linestyle="--", alpha=0.7)
timeline_axis.text(
    pd.Timestamp("2024-06-16"),
    4.42,
    "Protected holdout opens",
    color="#ff8a80",
    ha="right",
    va="bottom",
    fontsize=9,
)
timeline_axis.set_yticks(
    list(role_positions.values()),
    [role_labels[role] for role in role_order],
)
timeline_axis.set_xlabel("London fixture date")
timeline_axis.set_title(
    "Outcome-blind fixture timeline (stars denote tournament matches)",
    fontweight="bold",
)
timeline_axis.grid(axis="x", alpha=0.18)
timeline_axis.set_ylim(-0.6, 4.65)

fig.suptitle(
    "Match-aware data expansion: 50 scheduled England fixtures",
    fontsize=18,
    fontweight="bold",
)
fig.tight_layout(rect=[0, 0, 1, 0.96])
fig.savefig(FIGURES / "01_extended_fixture_inventory.png", dpi=300, bbox_inches="tight")
plt.close(fig)

