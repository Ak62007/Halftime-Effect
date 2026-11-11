"""Build leakage-safe locked-v3 forecasts for historical tournament editions.

The v3 *architecture* is fixed by ``event_blind_v3_model_lock.json``.  Parameters
are refitted once before each tournament edition, using only demand outcomes that
would have been available before that edition's first England fixture.

EURO 2024 is excluded by default.  It is already an opened period and can only be
added later as a retrospective diagnostic with ``--include-euro-2024``.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor

from evaluate_event_blind_v3_final_test import LOCK
from evaluate_v2_direct_residual_candidates import cutoff_features
from evaluate_v3_dynamic_candidates import v3_direct_design
from evaluate_v3_nonlinear_candidates import fit_spline
from evaluate_v3_ridge_ablation import load_v3_data, metrics, required_available


ROOT = Path(__file__).resolve().parents[1]
CONFIG = json.loads((ROOT / "configs/match_aware_v3_experiment.json").read_text())
OUT = ROOT / "data/processed/match_aware_v3"
OUT.mkdir(parents=True, exist_ok=True)
MATCH_DATA = ROOT / "data/processed/match_aware/demand_extended.csv"

EDITION_LABELS = {
    "UEFA EURO 2020": "UEFA EURO 2020",
    "FIFA World Cup 2022": "FIFA World Cup 2022",
    "UEFA EURO 2024": "UEFA EURO 2024",
}


def fit_unpenalized_ridge_design(x: np.ndarray, y: np.ndarray) -> np.ndarray:
    """Minimum-norm OLS for the locked alpha=0 direct Ridge specification.

    The original normal-equation implementation is algebraically equivalent when
    the design is full rank, but is singular for the short pre-EURO-2020 history.
    ``lstsq`` preserves alpha=0 while handling redundant columns safely.
    """
    coefficients, *_ = np.linalg.lstsq(x, y, rcond=None)
    return coefficients


def repair_audited_lag_gaps(data: pd.DataFrame) -> pd.DataFrame:
    """Repair derived lag inputs disrupted by an earlier source-quality gap.

    Every substitute is the row-wise mean of other already-observed fixed lags.
    Repaired rows are retained for continuous forecasting and residual history but
    are explicitly excluded from parameter fitting.
    """
    data = data.copy()
    lag_columns = [
        f"lag_{lag}" for lag in [96, 144, 192, 240, 288, 336, 672, 1008, 1344]
    ]
    fallback = data[lag_columns].isna().any(axis=1) & data["demand_mw"].notna()
    row_fallback = data[lag_columns].mean(axis=1, skipna=True)
    for column in lag_columns:
        replace = fallback & data[column].isna()
        data.loc[replace, column] = row_fallback.loc[replace]

    daily = [f"lag_{lag}" for lag in [96, 144, 192, 240, 288, 336]]
    weekly = [f"lag_{lag}" for lag in [336, 672, 1008, 1344]]
    data["safe_daily_mean"] = data[daily].mean(axis=1, skipna=False)
    data["safe_daily_std"] = data[daily].std(axis=1, skipna=False)
    data["weekly_mean_4"] = data[weekly].mean(axis=1, skipna=False)
    data["weekly_std_4"] = data[weekly].std(axis=1, skipna=False)
    data["daily_change_2_to_3"] = data["lag_96"] - data["lag_144"]
    data["weekly_change_1_to_2"] = data["lag_336"] - data["lag_672"]
    data["v3_lag_fallback_used"] = fallback
    return data


def fixture_rows(include_euro_2024: bool) -> pd.DataFrame:
    columns = [
        "timestamp_utc",
        "match_id",
        "opponent",
        "competition",
        "event_role",
        "is_tournament_match",
        "scheduled_kickoff_utc",
        "minutes_from_scheduled_kickoff",
        "pregame_overlap_fraction",
        "scheduled_match_overlap_fraction",
        "halftime_proxy_overlap_fraction",
        "postmatch_overlap_fraction",
    ]
    rows = pd.read_csv(MATCH_DATA, usecols=columns)
    rows["timestamp_utc"] = pd.to_datetime(rows["timestamp_utc"], utc=True)
    rows = rows.loc[rows["match_id"].notna() & rows["is_tournament_match"]].copy()
    rows["tournament_edition"] = np.select(
        [
            rows["competition"].str.contains("EURO 2020", case=False, na=False),
            rows["competition"].str.contains("World Cup 2022", case=False, na=False),
            rows["competition"].str.contains("EURO 2024", case=False, na=False),
        ],
        ["UEFA EURO 2020", "FIFA World Cup 2022", "UEFA EURO 2024"],
        default="unknown",
    )
    allowed = set(CONFIG["historical_selection_editions"])
    if include_euro_2024:
        allowed.add(CONFIG["retrospective_diagnostic_edition"])
    rows = rows.loc[rows["tournament_edition"].isin(allowed)].copy()
    expected = 19 if include_euro_2024 else 12
    if rows["match_id"].nunique() != expected:
        raise ValueError(f"Expected {expected} tournament fixtures")
    return rows


def locked_v3_forecast(
    data: pd.DataFrame,
    training_end: pd.Timestamp,
    target_end: pd.Timestamp,
) -> tuple[pd.DataFrame, dict]:
    """Fit the locked v3 point model and forecast through ``target_end``."""
    available = required_available(data)
    recent_days = LOCK["research_point_forecast"]["training_window_days"]
    training_start = max(
        pd.Timestamp(data["settlement_date"].min()),
        training_end - pd.Timedelta(days=recent_days - 1),
    )
    train_mask = (
        data["settlement_date"].between(
            training_start.strftime("%Y-%m-%d"), training_end.strftime("%Y-%m-%d")
        )
        & available
        & ~data["v3_lag_fallback_used"]
    )
    modeled_mask = (
        data["settlement_date"].between(
            training_start.strftime("%Y-%m-%d"), target_end.strftime("%Y-%m-%d")
        )
        & available
    )
    training = data.loc[train_mask].copy()
    modeled = data.loc[modeled_mask].copy().reset_index(drop=True)
    if training.empty:
        raise ValueError("No eligible training rows")

    base_forecast, base_metadata = fit_spline(
        training, modeled, LOCK["research_point_forecast"]["base_alpha"]
    )
    modeled["base_forecast_mw"] = base_forecast
    modeled["base_residual_mw"] = modeled["demand_mw"] - base_forecast
    modeled = cutoff_features(modeled)
    x_all = v3_direct_design(modeled)
    complete = np.isfinite(x_all).all(axis=1)
    train_dynamic = (
        modeled["settlement_date"].le(training_end.strftime("%Y-%m-%d")).to_numpy()
        & complete
        & ~modeled["v3_lag_fallback_used"].to_numpy(dtype=bool)
    )
    target_complete = modeled["settlement_date"].between(
        (training_end + pd.Timedelta(days=1)).strftime("%Y-%m-%d"),
        target_end.strftime("%Y-%m-%d"),
    )
    if train_dynamic.sum() < 500:
        raise ValueError("Insufficient complete rows for the locked residual model")

    target = modeled.loc[train_dynamic, "base_residual_mw"].to_numpy() / 1_000
    if LOCK["research_point_forecast"]["direct_ridge_alpha"] != 0:
        raise ValueError("This reproducer expects the locked alpha=0 direct Ridge")
    ridge = fit_unpenalized_ridge_design(x_all[train_dynamic], target)
    ridge_correction = np.full(len(modeled), np.nan)
    ridge_correction[complete] = (x_all[complete] @ ridge) * 1_000

    hgb = HistGradientBoostingRegressor(
        **LOCK["research_point_forecast"]["direct_hgb_parameters"]
    )
    hgb.fit(x_all[train_dynamic], target)
    hgb_correction = np.full(len(modeled), np.nan)
    hgb_correction[complete] = hgb.predict(x_all[complete]) * 1_000

    modeled["direct_ridge_forecast_mw"] = base_forecast + ridge_correction
    modeled["direct_hgb_forecast_mw"] = base_forecast + hgb_correction
    modeled["v3_forecast_mw"] = (
        LOCK["research_point_forecast"]["ridge_blend_weight"]
        * modeled["direct_ridge_forecast_mw"]
        + LOCK["research_point_forecast"]["hgb_blend_weight"]
        * modeled["direct_hgb_forecast_mw"]
    )
    if not complete[target_complete.to_numpy()].all():
        missing_dates = sorted(
            modeled.loc[target_complete.to_numpy() & ~complete, "settlement_date"]
            .unique()
            .tolist()
        )
        diagnostic_columns = [
            column
            for column in modeled.columns
            if column.startswith("residual_lag_")
            or column.startswith("cutoff_")
            or column == "horizon_half_hours"
        ]
        missing_columns = {
            column: int(modeled.loc[target_complete, column].isna().sum())
            for column in diagnostic_columns
            if modeled.loc[target_complete, column].isna().any()
        }
        raise ValueError(
            "Incomplete locked-v3 features in the target period: "
            f"dates={missing_dates}, columns={missing_columns}"
        )
    metadata = {
        "training_start": training_start.strftime("%Y-%m-%d"),
        "training_end": training_end.strftime("%Y-%m-%d"),
        "training_rows": int(len(training)),
        "direct_training_rows": int(train_dynamic.sum()),
        "modeled_lag_fallback_rows": int(
            modeled["v3_lag_fallback_used"].sum()
        ),
        "base_fit": base_metadata,
    }
    return modeled, metadata


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--include-euro-2024", action="store_true")
    args = parser.parse_args()

    data = repair_audited_lag_gaps(load_v3_data(include_final_test=False))
    events = fixture_rows(args.include_euro_2024)
    editions = CONFIG["historical_selection_editions"].copy()
    if args.include_euro_2024:
        editions.append(CONFIG["retrospective_diagnostic_edition"])

    outputs: list[pd.DataFrame] = []
    audit = {
        "event_blind_architecture": "locked event-blind v3 point forecast",
        "lock_file": CONFIG["event_blind_lock"],
        "forecast_protocol": CONFIG["event_blind_refit_rule"],
        "euro_2024_included": args.include_euro_2024,
        "euro_2024_status": CONFIG["retrospective_diagnostic_status"],
        "editions": {},
    }
    for edition in editions:
        edition_events = events.loc[events["tournament_edition"].eq(edition)].copy()
        first_date = edition_events["timestamp_utc"].min().tz_convert(
            CONFIG["timezone"]
        ).normalize().tz_localize(None)
        last_date = edition_events["timestamp_utc"].max().tz_convert(
            CONFIG["timezone"]
        ).normalize().tz_localize(None)
        training_end = first_date - pd.Timedelta(days=2)
        modeled, metadata = locked_v3_forecast(data, training_end, last_date)
        forecast_columns = [
            "timestamp_utc",
            "settlement_date",
            "demand_mw",
            "lag_336",
            "neso_day_ahead_forecast_mw",
            "neso_available_at_cutoff",
            "base_forecast_mw",
            "direct_ridge_forecast_mw",
            "direct_hgb_forecast_mw",
            "v3_forecast_mw",
        ]
        joined = edition_events.merge(
            modeled[forecast_columns], on="timestamp_utc", how="left", validate="one_to_one"
        )
        if joined["v3_forecast_mw"].isna().any():
            raise ValueError(f"Missing v3 forecasts for {edition}")
        outputs.append(joined)
        actual = joined["demand_mw"].to_numpy(dtype=float)
        audit["editions"][edition] = {
            **metadata,
            "first_fixture_date": first_date.strftime("%Y-%m-%d"),
            "last_fixture_date": last_date.strftime("%Y-%m-%d"),
            "matches": int(joined["match_id"].nunique()),
            "match_day_rows": int(len(joined)),
            "v3_match_day_metrics": metrics(
                actual, joined["v3_forecast_mw"].to_numpy(dtype=float)
            ),
        }

    predictions = pd.concat(outputs, ignore_index=True)
    suffix = "with_euro_2024" if args.include_euro_2024 else "historical_only"
    predictions.to_csv(OUT / f"tournament_v3_baselines_{suffix}.csv", index=False)
    (OUT / f"baseline_audit_{suffix}.json").write_text(
        json.dumps(audit, indent=2) + "\n"
    )
    print(json.dumps(audit, indent=2))


if __name__ == "__main__":
    main()
