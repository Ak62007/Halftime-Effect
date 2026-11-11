# Event-blind v2 — locked experiment plan

Status: candidate specifications fixed before fitting

Branch: `event-blind-v2`

Final test: 1 January–31 March 2025, unopened

## Objective

Build a stronger day-ahead event-blind electricity-demand forecast before revisiting
the match correction. The primary objective is lower out-of-sample error. A secondary
objective is to leave residuals with less autocorrelation and more stable conditional
variance.

Perfectly independent, homoskedastic residuals are not a guaranteed outcome. Diagnostics
will not be optimized at the expense of forecast accuracy, and a formal test can reject
small departures in a large sample even when they are operationally unimportant.

## Evidence from the completed analysis

The existing notebook and reports established:

- raw demand has changing level and spread;
- ADF and Phillips–Perron disagree about a raw-level unit root;
- first, daily and weekly differences reject a unit root, but none resembles white noise;
- daily differencing suppresses the daily spectral peak but leaves weekly dependence;
- weekly differencing suppresses weekly-aligned frequencies but leaves short-run and
  daily dependence;
- the periodogram contains strong weekly, daily, 12-hour, 8-hour and 6-hour structure;
- the v1 model residual ACF is 0.983 at 30 minutes, 0.464 at one day and 0.370 at two days;
- v1 residuals strongly reject both white noise and constant conditional variance.

This supports a model containing deterministic multiple seasonality plus dynamic error
structure. It does not justify choosing a differencing order from one unit-root test.

## Forecasting protocol

The forecast is issued at 10:00 London time on the day before delivery. Every forecast
must cover every settlement interval on the target local date. A feature is legal only
if its source observation is complete by the issue time.

Consequences:

- lag 48 is unavailable for much of the next delivery day and cannot be a universally
  observed input;
- fixed lags 96, 144, 192, 240, 288, 336, 672, 1008 and 1344 are safe for the complete
  delivery day;
- dynamic models may update their state only with observations ending by the cutoff;
- actual future residuals, actual future demand and retrospective weather are forbidden;
- NESO's published forecast remains an external comparator, not an event-blind input.

## Data separation

Model selection uses four rolling-origin folds:

| Fold | Training ends | Validation period | Main seasonal challenge |
|---|---|---|---|
| Autumn 2023 | 30 Aug 2023 | Sep–Oct 2023 | summer-to-winter transition |
| Winter 2023/24 | 30 Dec 2023 | Jan–Feb 2024 | high demand and holidays |
| Spring 2024 | 28 Feb 2024 | Mar–May 2024 | winter-to-summer transition |
| Late 2024 | 29 Sep 2024 | Oct–Dec 2024 | DST and winter rise |

Each training end is a complete local day before the first forecast's previous-day
10:00 cutoff. The unused interval between that training end and cutoff prevents the
fixed-parameter fold fit from reading observations unavailable to its first forecast.

The primary selection statistic is mean fold MAE. We will also report RMSE, bias,
worst-fold MAE and performance by clock time. The final test is January–March 2025 and
will be opened once after the mean model, transformations, hyperparameters and diagnostic
rules are locked.

EURO 2024 is already known from the earlier study. It is excluded from v2 model selection
and will not be presented as new evidence.

## Candidate mean models

### B0 — weekly seasonal naive

Reuse demand from the corresponding UTC half-hour 336 intervals earlier. This is the
minimum benchmark every learned model must beat.

### B1 — existing calendar plus weekly-lag regression

Reproduce the v1 model on every fold. This isolates improvement caused by the new model
rather than by different dates or scoring code.

### M1 — regularized multi-lag seasonal regression

Inputs:

- local half-hour-of-week;
- annual Fourier terms;
- linear trend and GB bank holiday;
- safe daily lags 96–288;
- weekly lags 336, 672, 1008 and 1344;
- recent-lag mean, spread and week-over-week changes.

Ridge regularization will stabilize the correlated lag coefficients. Both level-demand
and log-demand targets are candidates. Log demand is included because variability rises
with the demand level and may be more nearly constant on a relative scale.

### M2 — dynamic harmonic regression with ARMA errors

The conditional mean uses Fourier terms for daily, weekly and annual cycles plus calendar
effects. The residual follows a small ARMA process. The model is fitted in state-space
form and produces genuine multi-step forecasts from the previous-day cutoff; it may not
read realized residuals from the target day.

This directly connects the syllabus's Fourier/spectral and ARMA topics to the observed
multiple seasonalities.

### M3 — daily SARIMAX with weekly/annual Fourier terms

A compact daily seasonal ARIMA component uses period 48. Weekly period 336 and annual
seasonality are represented with Fourier regressors rather than an enormous seasonal
state. Level versus seasonal differencing will be compared only within the training
folds because the unit-root evidence is mixed.

This candidate is retained only if estimation is numerically stable and runtime is
reasonable.

## Conditional variance stage

ARCH/GARCH is not a replacement for the demand mean model. After the winning mean model
is locked:

1. test its rolling-origin residuals with squared-residual ACF and ARCH-LM;
2. if meaningful clustering remains, fit one GARCH(1,1) model to training residuals;
3. evaluate standardized residuals and interval coverage;
4. do not compare gratuitous EGARCH/GJR variants unless asymmetry is visibly and
   substantively justified.

GARCH may improve uncertainty forecasts even if point MAE does not change.

## Syllabus methods intentionally not forced

- VAR, VECM, Johansen cointegration and Granger causality are excluded because there is
  no defensible multivariate system of comparable ex-ante stochastic inputs.
- Retrospective ERA5 temperature is excluded from operational forecasts. It can be used
  later only as a labelled explanatory sensitivity or replaced by archived issued
  weather forecasts.
- Bai–Perron or related break analysis is conditional. First we will inspect rolling-fold
  bias and stability; formal break tests are useful only if persistent regimes remain.

## Decision rules

1. Select the mean-model family by mean rolling-origin MAE.
2. Use RMSE, bias and worst-fold MAE as stability checks; do not choose a model solely
   because one residual p-value is larger.
3. Reject any model with failed convergence, illegal feature availability or incomplete
   target-day coverage.
4. Lock the winning specification before opening January–March 2025.
5. Diagnose test residuals once; do not retune and reuse the same final test.
6. Only after v2 is frozen may the historical match correction be retrained on its
   residuals, followed by a newly designated event holdout.
