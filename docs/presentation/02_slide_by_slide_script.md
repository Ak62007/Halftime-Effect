# Slide-by-slide presentation script

The wording below is a speaking guide, not text to memorize. Each presenter should
understand the idea, then speak naturally. A 17-slide presentation should take roughly
16 to 20 minutes, excluding questions.

## Slide 1 — The Halftime Effect

**Purpose:** introduce the project in one sentence.

**Say:**

“Our project asks whether scheduled England football matches, especially halftime,
contain useful information for forecasting half-hourly Great Britain electricity
demand. We first model ordinary demand, because a visible spike is meaningful only
relative to what demand would normally have been.”

**Do not say:** that the project proves football causes a demand spike.

## Slide 2 — Research question and scope

**Purpose:** distinguish the two stages and prediction from causality.

**Say:**

“The first stage builds an event-blind day-ahead forecast using calendar, seasonal,
lagged-demand and forecast-available exogenous information. The second stage asks
whether known fixture timing improves that same forecast. The result is predictive. A
match coefficient can also absorb weather, tournament timing or other omitted factors,
so it is not automatically causal.”

## Slide 3 — Data sources

**Purpose:** establish where the evidence came from.

**Say:**

“NESO supplies demand outturn, its operational day-ahead forecast and embedded wind and
solar forecasts. We use the official UK bank-holiday calendar, archived issued weather
runs from Open-Meteo and a verified England fixture inventory. The important point is
that forecast models use information that could genuinely have been known before
delivery.”

**Know:** demand outturn is the target; the NESO demand forecast is an external
comparison, not an input to the research model.

## Slide 4 — What one observation represents

**Purpose:** define the unit of analysis and target.

**Say:**

“Each row represents one half-hour settlement interval. The target is national demand
outturn in megawatts. MW measures power, not half-hour energy in MWh. UTC gives every
interval a unique chronological identity. London time supplies human calendar labels
such as weekday and clock time.”

**Know:** a 19:45 kickoff overlaps two settlement intervals fractionally; event features
therefore use overlap fractions rather than crude whole-row labels.

## Slide 5 — Data preparation and safeguards

**Purpose:** show that time alignment is part of the methodology.

**Say:**

“We verified a complete 30-minute UTC grid, converted to London time for calendar
features, audited spring and autumn clock changes, and kept source-quality exclusions
explicit. Day-ahead inputs are joined by their issue time. We never randomly shuffle
the time series because that would allow later regimes to inform earlier forecasts.”

**Likely question:** why can a London day have 46 or 50 half-hours? See the question
bank’s DST answer.

## Slide 6 — Demand across the year

**Purpose:** explain long-run and high-frequency variation.

**Say:**

“The dense oscillation comes from the repeated daily cycle. The level is generally
higher in winter and lower in summer. We do not call the winter-to-summer fall a
permanent downward trend because demand rises again. The evidence is more consistent
with annual seasonality, although roughly one annual cycle is limited evidence of its
long-term stability.”

## Slide 7 — Daily shape by weekday and season

**Purpose:** show why one unconditional average is inadequate.

**Say:**

“Weekdays show a pronounced morning rise and later peak, while weekends have a weaker
morning pattern. All pooled weekday profiles peak around the early evening in this
sample. Winter Mondays stay above summer Mondays through the day and peak earlier. This
means the model needs both within-week and annual structure.”

**Useful numbers:** pooled Monday IQR is widest at 17:00, approximately 11,833 MW.
Winter and summer Monday medians at 17:00 are about 38,948 and 25,143 MW.

## Slide 8 — Autocorrelation and the weekly benchmark

**Purpose:** connect dependence to a feasible forecast.

**Say:**

“Demand is strongly related to recent values. Correlation is 0.989 at lag 1, 0.914 at
lag 48 and 0.893 at lag 336. Lag 1 is excellent for understanding persistence, but
tomorrow’s preceding half-hour does not exist when today’s day-ahead forecast is issued.
Lag 336 is already known and normally aligns the weekday, so it becomes the weekly
seasonal-naive benchmark.”

**Equation:** `forecast at t = observed demand at t minus 336 half-hours`.

**Result:** initial validation MAE is 1,946 MW.

## Slide 9 — Stationarity evidence

**Purpose:** combine visual and formal diagnostics.

**Say:**

“Raw demand does not have an obviously constant local mean or variance. First
differencing centres the series near zero most effectively, but its rolling variability
still changes. Daily and weekly differences remove different seasonal comparisons.
ADF fails to reject a unit root for raw demand with p 0.343, while Phillips–Perron
rejects. Both reject for every differenced series. The disagreement means we should not
claim that one test has conclusively classified raw demand.”

**Emphasize:** unit-root rejection does not prove white noise, constant variance or the
absence of seasonality.

## Slide 10 — Spectral evidence

**Purpose:** explain the same dependence in the frequency domain.

**Say:**

“The periodogram has power near the weekly frequency of one-seventh cycle per day, the
daily frequency of one cycle per day, and daily harmonics at two, three and four cycles
per day. First differencing suppresses low frequencies. Daily differencing creates
notches at daily harmonics, while weekly differencing suppresses frequencies aligned
with a seven-day cycle. No transformed spectrum is flat, so none is white noise before
modelling.”

**Likely question:** a period is the reciprocal of frequency. One cycle per day has a
one-day period; one-seventh cycle per day has a seven-day period.

## Slide 11 — Day-ahead forecasting protocol

**Purpose:** make evaluation credible.

**Say:**

“The forecast is issued at 10:00 London time on the previous day for every half-hour of
the target day. Seven rolling-origin folds select the corrected model. We report MAE,
RMSE and signed mean error. January to March 2026 was opened in earlier work, so the
corrected result is labelled retrospective rather than presented as a fresh untouched
test.”

**Know:** positive mean error means underforecasting because error equals actual minus
forecast.

## Slide 12 — Seasonal and lag-based regression

**Purpose:** explain the first modelling progression.

**Say:**

“The weekly naive method averages 2,154 MW MAE across four rolling folds. Calendar and
weekly-lag regression reaches 1,616 MW. Multi-lag Ridge reaches 1,467 MW. Recursive AR
residual correction reaches 1,381 MW, and direct residual ARX reaches 1,348 MW. Each
step is evaluated on the same folds. Ridge stabilizes many correlated calendar and lag
features by shrinking coefficients.”

**Avoid:** implying that the NESO comparison was trained by us. NESO is an external
operational forecast.

## Slide 13 — Residual time-series models

**Purpose:** explain recursive AR, direct ARX and ARMA clearly.

**Say:**

“A recursive AR model predicts the next residual from residual lags, then uses its own
prediction for later horizons. This is compact but errors can propagate. Direct ARX
predicts the residual for each target using only history known at the issue cutoff,
plus horizon, clock and exogenous terms. In the corrected seven-fold comparison,
recursive AR reaches 777 MW, ARMA(1,1) reaches 802 MW, and direct ARX reaches 750 MW.
We therefore select direct ARX.”

**PACF interpretation:** PACF measures the remaining relationship at a lag after
accounting for shorter lags. It guides candidate orders but does not select the final
model mechanically.

## Slide 14 — Value of exogenous forecasts

**Purpose:** explain where the largest accuracy improvement came from.

**Say:**

“We hold the plain Ridge method fixed and change the information supplied. The
reproduced lag model scores 1,418 MW. Richer calendar information changes this only to
1,400 MW. Archived weather forecasts reduce MAE to 1,265 MW. Embedded wind and solar
forecasts reduce it to 1,062 MW. Combining the inputs reaches 825 MW. These are issued
forecasts, not realized future weather or generation.”

**Interpretation:** embedded generation affects the demand visible to the transmission
system, so it is especially informative for net-demand forecasting.

## Slide 15 — Out-of-sample accuracy

**Purpose:** report generalization without hiding model-selection discipline.

**Say:**

“On the locked January to March 2025 test, the retained Ridge plus direct ARX model
reduces MAE from 3,101 MW for weekly naive to 1,622 MW. In the corrected 2026
retrospective evaluation, plain exogenous Ridge scores 1,005 MW, ARMA 970 MW, direct
ARX 931 MW and recursive AR 918 MW. Recursive AR happens to be lower on this opened
period, but we retain direct ARX because it won development validation. NESO remains
stronger at 807 MW on its available rows.”

**Important comparison caveat:** NESO has 4,222 available rows in 2026; the research
models have 4,318. Do not describe the 807 versus 931 comparison as perfectly identical
without this qualification.

## Slide 16 — Scheduled football information

**Purpose:** deliver the football result with the correct limitation.

**Say:**

“The model uses pregame, scheduled-play, halftime-proxy and post-match overlap
fractions. Historical validation holds out complete tournament editions. On EURO 2024,
the correction improves primary-window MAE from 1,130 to 1,052 MW, but only three of
seven fixtures improve. Halftime MAE worsens from 808 to 984 MW. The aggregate gain
comes from pregame and post-match intervals, so this is not a successful
halftime-specific forecast.”

**Causal wording:** say “associated forecast correction” or “scheduled-window anomaly,”
not “football caused X MW.”

## Slide 17 — Conclusions and limitations

**Purpose:** finish with what the evidence genuinely supports.

**Say:**

“First, calendar, lagged demand, archived weather and embedded-generation forecasts
materially improve normal-demand prediction. Second, direct residual ARX gives the
best development result among our retained models. Third, scheduled match information
does not deliver a stable halftime improvement. The study cannot identify a causal
football effect. A convincing confirmation needs more tournament editions, actual
halftime timestamps and a future tournament kept untouched from development.”

**Final sentence:**

“Our main result is therefore a stronger and defensible day-ahead demand model, together
with an honest negative result for robust halftime-aware forecasting.”
