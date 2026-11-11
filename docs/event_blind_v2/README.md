# Event-blind v2 forecasting experiment

This experiment improves the day-ahead electricity-demand baseline before any football
schedule correction is applied. Model development uses four rolling-origin validation
folds ending in December 2024. January–March 2025 is opened once, only after the model
specification was locked in commit `0c3d4b9`.

## Reports

1. [Experiment plan](00_experiment_plan.md) — forecasting question, syllabus concepts,
   leakage rules, validation design and candidate model families.
2. [Development and model selection](01_model_selection.md) — regression, dynamic-error,
   SARIMAX and GARCH experiments using development data only.
3. [Untouched final test](02_final_test.md) — final point accuracy, stability, interval
   coverage and residual diagnostics for January–March 2025.

## Headline result

The locked v2 forecast achieves **1,622 MW MAE** on the untouched final test. This is a
32.4% reduction from the v1 baseline (2,401 MW) and a 47.7% reduction from weekly
seasonal naive (3,101 MW). NESO's operational forecast remains substantially stronger
at 781 MW MAE.

The point forecast is therefore materially improved, but the residuals are neither
independent nor conditionally homoskedastic. GARCH captures part of the time-varying
scale, not the common within-day shocks. The evidence points toward missing ex-ante
inputs—especially archived weather forecasts—rather than a need for arbitrary extra AR
orders.

## Reproduction order

The scripts below assume the project virtual environment and finalized source data.

```bash
.venv/bin/python src/build_event_blind_v2_data.py
.venv/bin/python src/evaluate_v2_regression_candidates.py
.venv/bin/python src/evaluate_v2_ar_error_candidates.py
.venv/bin/python src/evaluate_v2_direct_residual_candidates.py
.venv/bin/python src/diagnose_v2_garch.py
.venv/bin/python src/plot_event_blind_v2_selection.py
.venv/bin/python src/evaluate_event_blind_v2_final_test.py
.venv/bin/python src/plot_event_blind_v2_final_test.py
.venv/bin/python -m unittest discover -s tests -v
```

January–March 2025 is no longer an untouched period and must not be reused to select a
new model. Any next-generation forecast needs a later holdout.
