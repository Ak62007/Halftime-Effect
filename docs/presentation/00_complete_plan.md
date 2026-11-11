# Halftime Effect presentation plan

## Purpose

Create a professional 17-slide presentation for the course instructor. The deck will
explain the complete research workflow without using internal branch names or software
version labels as the narrative. It will show how the question, data, diagnostics and
forecasting models developed, then end with the football-window result and its limits.

## Presentation artifact

- Editable Canva deck: https://www.canva.com/d/eOkW1f8IU7K2RP5
- View-only Canva deck: https://www.canva.com/d/onoKx6Ex99ayiHr
- Canva design ID: `DAHapb-ZY90`
- Format: 17 slides, with verified project figures and results.
- Supporting speaker script, team allocation, learning guide, model equations and
  teacher question bank are stored beside this plan in `docs/presentation/`.

## Corrected model scope

### Retain

- Weekly seasonal naive benchmark.
- Calendar seasonal regression and calendar regression with a weekly demand lag.
- Multi-lag Ridge regression.
- Recursive autoregressive residual corrections.
- Direct multi-horizon residual ARX Ridge regression.
- Small ARMA residual models and the recorded SARIMAX feasibility test.
- Archived weather, embedded wind and embedded solar inputs in a linear Ridge model.
- ARCH diagnostics and GARCH(1,1) forecast-variance analysis.
- Linear scheduled-window match corrections trained and validated by complete fixtures.

### Remove from the presentation model path

- Temperature-spline Ridge models.
- Histogram gradient boosting models.
- Linear and boosting forecast blends.
- Boosting-based variance models.
- Calibration layers that depend on the removed nonlinear models.

The corrected exogenous model will be rerun with a plain Ridge base. Recursive AR,
direct residual ARX Ridge and ARMA corrections will be recomputed from that base so no
reported result silently depends on a removed spline or boosting model.

## Slide plan

| Slide | Title | Main content | Primary visual |
|---:|---|---|---|
| 1 | The Halftime Effect | Research title, course context, four group members | Minimal title treatment with electricity and football theme |
| 2 | Research question and scope | Forecast normal GB demand, test scheduled match information, distinguish prediction from causality | Two-stage research flow |
| 3 | Data sources | NESO demand and forecast data, verified England fixtures, bank holidays, archived weather forecasts, embedded wind and solar forecasts | Source-to-dataset flow |
| 4 | What one row means | Half-hour interval, MW target, UTC timeline, London calendar fields, event-overlap variables | Annotated example record and timeline |
| 5 | Data preparation and safeguards | DST handling, complete UTC grid, quality exclusions, issue-time availability, protected evaluation periods | Data pipeline with validation gates |
| 6 | Demand across the year | Winter and summer level differences, recurring daily movement, limited evidence for a permanent trend | Full half-hourly training plot and daily mean plot |
| 7 | Daily and weekly demand patterns | Morning rise, evening peak, weekday and weekend differences, large between-day variation | Weekday profiles and winter-summer Monday comparison |
| 8 | Autocorrelation and the first benchmark | Lag 1, lag 48 and lag 336 dependence, leakage-safe reason for using lag 336 | Lag correlation or ACF plus weekly-naive forecast week |
| 9 | Stationarity evidence | Raw, first, daily and weekly differences; rolling mean and variance; ADF and PP findings | Transformation and rolling-diagnostic figure |
| 10 | Spectral evidence | Peaks near daily, weekly and harmonic frequencies; differencing as frequency-specific filtering | Periodogram comparison |
| 11 | Forecasting protocol | Previous-day 10:00 cutoff, rolling-origin validation, MAE/RMSE/bias, untouched tests, no future target lags | Chronological train-validation-test diagram |
| 12 | Seasonal and lag-based regression | Weekly naive, calendar seasonal, calendar plus weekly lag, multi-lag Ridge | Editable model-progression chart |
| 13 | Residual time-series models | Recursive AR, direct residual ARX Ridge, ARMA candidates, rejected SARIMAX feasibility fit | Model equations and development-performance chart |
| 14 | Exogenous forecast inputs | Incremental value of calendar, archived weather, embedded wind and solar in plain Ridge | Feature-ablation chart |
| 15 | Forecast accuracy and residual diagnostics | Corrected final test, NESO comparison, residual ACF, ARCH-LM and GARCH interval result | Final-test chart and small diagnostic callouts |
| 16 | Scheduled football information | Historical tournament training, four overlap windows, EURO 2024 event-window and halftime results | Event-window diagram and holdout comparison |
| 17 | Conclusions and limitations | Stronger normal-demand forecast, unstable match correction, no causal claim, data and future-evaluation limits | Four concise conclusions and next-study conditions |

## Evidence rules for the deck

- Use figures already exported from the notebooks whenever they communicate the result
  clearly.
- Recover the high-resolution forecasting figures from the pre-cleanup Git commit.
- Recompute only the model results affected by removing splines and boosting.
- Never compare metrics from different date ranges without labeling the evaluation
  period.
- Label EURO 2024 as an already opened retrospective result where applicable.
- Describe the halftime interval as a scheduled proxy, not an observed instantaneous
  pickup.
- State that match coefficients support prediction only and do not identify causality.

## Four-member speaking split

### Member 1: problem and data, slides 1–5

Explain the research question, target variable, data sources, timestamps, half-hour
resolution and data-quality safeguards. This member should understand MW versus MWh,
UTC versus London time, DST days and why forecast issue time matters.

### Member 2: exploratory analysis, slides 6–10

Explain long-run seasonality, intraday profiles, autocorrelation, stationarity tests and
the periodogram. This member should understand ACF versus PACF, unit-root test nulls,
differencing, frequency and period, and why a significant lag does not automatically
become a model term.

### Member 3: forecasting models, slides 11–15

Explain the chronological evaluation protocol and the progression from naive forecasts
to calendar regression, multi-lag Ridge, recursive AR, direct ARX, ARMA and exogenous
Ridge. This member should understand every model input, the day-ahead information
boundary, Ridge regularization, direct versus recursive forecasting and forecast-error
metrics.

### Member 4: football experiment and conclusion, slides 16–17

Explain scheduled overlap variables, fixture-level validation, EURO 2024 results,
halftime limitations and the distinction between predictive association and causality.
This member should understand why seven matches provide weak evidence and why a future
untouched tournament is necessary.

## Deliverables

1. Restored and filtered model code and reports on a presentation-preparation branch.
2. Recomputed syllabus-scope model tables and high-resolution figures.
3. A 17-slide Canva presentation with editable text and charts.
4. A slide-by-slide speaking script.
5. Four member-specific preparation guides.
6. A shared teacher-question bank with concise defensible answers.
7. A model-equation and metric appendix document for revision before presenting.

## Work sequence

1. Preserve the student's current notebook changes.
2. Recover relevant model files and figures from Git history.
3. Remove spline and boosting dependencies from the corrected modelling path.
4. Recompute the plain-Ridge, recursive AR, direct ARX and ARMA comparisons.
5. Verify all dates, metrics, model equations and caveats.
6. Prepare the final slide copy and upload selected project figures to Canva.
7. Build and visually inspect the 17-slide Canva deck.
8. Write presenter scripts, member guides and the question bank.
9. Deliver links and a short rehearsal order.
