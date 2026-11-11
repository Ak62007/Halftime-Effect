"""Diagnose ordinary-validation residual dependence without opening match outcomes."""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from statsmodels.stats.diagnostic import acorr_ljungbox, het_arch
from statsmodels.tsa.stattools import acf


ROOT = Path(__file__).resolve().parents[1]
MODEL_DIR = ROOT / "data/processed/match_aware/modeling"
FIGURES = ROOT / "docs/figures/match_aware"
FIGURES.mkdir(parents=True, exist_ok=True)


def longest_contiguous_block(data: pd.DataFrame) -> pd.DataFrame:
    """Avoid treating observations on opposite sides of an excluded day as adjacent."""
    new_block = data["timestamp_utc"].diff().ne(pd.Timedelta(minutes=30))
    block_id = new_block.cumsum()
    largest_id = block_id.value_counts().idxmax()
    return data.loc[block_id.eq(largest_id)].copy()


def main() -> None:
    predictions = pd.read_csv(MODEL_DIR / "ordinary_validation_predictions.csv")
    predictions["timestamp_utc"] = pd.to_datetime(predictions["timestamp_utc"], utc=True)
    predictions = predictions.sort_values("timestamp_utc").reset_index(drop=True)
    block = longest_contiguous_block(predictions)
    residual = block["selected_event_blind_error_mw"].to_numpy(dtype=float)

    max_lag = 336
    residual_acf = acf(residual, nlags=max_lag, fft=True)
    squared_acf = acf((residual - residual.mean()) ** 2, nlags=max_lag, fft=True)
    ljung_lags = [1, 2, 48, 96, 336]
    ljung_box = acorr_ljungbox(residual, lags=ljung_lags, return_df=True)
    arch_lm, arch_pvalue, arch_f, arch_f_pvalue = het_arch(residual, nlags=48)

    diagnostics = {
        "scope": "longest contiguous ordinary-validation block",
        "start_utc": block["timestamp_utc"].iloc[0].isoformat(),
        "end_utc": block["timestamp_utc"].iloc[-1].isoformat(),
        "n": int(len(block)),
        "reason_for_block": (
            "England match days remain excluded; using a contiguous block avoids "
            "creating false adjacency across those gaps."
        ),
        "acf": {
            str(lag): float(residual_acf[lag])
            for lag in [1, 2, 48, 96, 336]
        },
        "squared_residual_acf": {
            str(lag): float(squared_acf[lag])
            for lag in [1, 2, 48, 96, 336]
        },
        "ljung_box": {
            str(lag): {
                "statistic": float(ljung_box.loc[lag, "lb_stat"]),
                "p_value": float(ljung_box.loc[lag, "lb_pvalue"]),
            }
            for lag in ljung_lags
        },
        "arch_lm_48_lags": {
            "statistic": float(arch_lm),
            "p_value": float(arch_pvalue),
            "f_statistic": float(arch_f),
            "f_p_value": float(arch_f_pvalue),
        },
    }
    (MODEL_DIR / "event_blind_residual_diagnostics.json").write_text(
        json.dumps(diagnostics, indent=2) + "\n"
    )

    plt.style.use("dark_background")
    fig, axes = plt.subplots(2, 1, figsize=(16, 10), sharex=True)
    confidence = 1.96 / np.sqrt(len(block))
    lags = np.arange(max_lag + 1)
    panels = [
        (residual_acf, "Residual ACF", "Forecast errors remain predictable"),
        (
            squared_acf,
            "Squared-residual ACF",
            "Error magnitude also clusters over time",
        ),
    ]
    for axis, (values, ylabel, title) in zip(axes, panels):
        axis.plot(lags[1:], values[1:], color="#00bcd4", linewidth=1.1)
        axis.axhline(0, color="white", linewidth=0.8)
        axis.axhspan(-confidence, confidence, color="#ffb300", alpha=0.16)
        for lag in [48, 96, 336]:
            axis.axvline(lag, color="#888888", linestyle="--", linewidth=0.8)
            axis.text(lag, axis.get_ylim()[1] * 0.88, str(lag), color="#bbbbbb", ha="center")
        axis.set_ylabel(ylabel)
        axis.set_title(title, fontweight="bold")
        axis.grid(alpha=0.14)
    axes[1].set_xlabel("Lag (half-hours); 48 = one day, 336 = one week")
    fig.suptitle(
        "Event-blind residual dependence on the longest uninterrupted validation block",
        fontsize=17,
        fontweight="bold",
    )
    fig.text(
        0.5,
        0.015,
        "Shaded band is the approximate white-noise 95% reference ±1.96/√n; it is not a forecast interval.",
        ha="center",
        color="#bbbbbb",
    )
    fig.tight_layout(rect=[0, 0.035, 1, 0.95])
    fig.savefig(FIGURES / "04_event_blind_residual_dependence.png", dpi=300, bbox_inches="tight")
    plt.close(fig)
    print(json.dumps(diagnostics, indent=2))


if __name__ == "__main__":
    main()
