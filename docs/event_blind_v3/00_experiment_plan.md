# Event-blind v3 experiment plan

## Objective

Improve the event-blind day-ahead demand forecast using only information available by
10:00 London time on the preceding calendar day. Point accuracy is primary; residual
independence, variance stability and interval calibration are secondary diagnostics.

## Protected evaluation

- Source and development: 1 April 2021–31 December 2025.
- January–March 2025 was already opened by v2. It may enter later training windows but
  is never a v3 validation fold.
- Final test: 1 January–31 March 2026.
- The final test is removed immediately by every development loader.
- EURO 2024 is not used to select v3.

Seven rolling-origin folds cover autumn 2023, winter and spring 2024, late 2024, and
spring, summer and late 2025. Each training boundary stops before observations that
would be unavailable at the first validation-day cutoff.

## Candidate funnel

1. Ridge feature ablation: v2, calendar, weather, embedded generation and all inputs.
2. Fixed temperature splines and compact histogram-gradient-boosting corrections.
3. Direct multi-horizon residual Ridge/boosting and recursive AR errors.
4. Small nonseasonal ARMA errors as a syllabus-aligned feasibility check.
5. Fixed Ridge–boosting forecast blends with weights 0.25, 0.50 and 0.75.
6. Constant, GARCH and feature-conditioned variance scales.
7. Leave-one-fold-out interval calibration.

The primary selection criterion is mean fold MAE. Worst-fold MAE, bias and RMSE guard
against a small average gain produced by one unstable season. Interval scale models must
be within one percentage point of both nominal coverages after leave-one-fold-out
calibration; the narrowest eligible 95% interval wins.

## Forbidden information

- realized future weather;
- forecast vintages published after the 10:00 cutoff;
- actual residuals after the cutoff;
- January–March 2026 outcomes or metrics before the model lock;
- EURO 2024 outcomes for v3 selection.
