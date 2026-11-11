# Four-member presentation assignment

The split balances the amount of speaking and the conceptual difficulty. Replace
“Member 1” through “Member 4” with names after the group confirms availability.

## Member 1 — Research question, data and preparation

**Slides:** 1–5  
**Estimated time:** 4 minutes

### What this member presents

- The problem and the distinction between normal-demand forecasting and the football
  schedule experiment.
- All data sources and the role of each source.
- The half-hourly target and the meaning of MW.
- UTC ordering, London calendar features, DST and source-quality checks.
- The previous-day 10:00 information boundary.

### What this member must learn

1. **MW versus MWh:** MW is power. A half-hour interval at an average 30,000 MW would
   correspond to 15,000 MWh, but the dataset’s target is MW.
2. **Demand outturn:** the observed national demand measure used as the target.
3. **Embedded generation:** distribution-connected wind or solar can reduce demand
   visible to the transmission system even when final consumption is unchanged.
4. **UTC versus London time:** UTC uniquely orders intervals; London time describes
   human routines and holidays.
5. **DST:** spring has 46 London settlement periods and autumn has 50, while the UTC
   timeline remains regular.
6. **Forecast vintage:** the model may use a forecast issued before the cutoff, but not
   the weather or demand later realized on the target day.

### Questions this member should answer

- Why did you select this demand measure?
- Why is half-hourly data suitable but imperfect for halftime?
- Why did you not use random train/test splitting?
- How did you prevent future information leakage?
- Why do DST dates need special treatment?

### Handoff

“After establishing that every row is aligned and genuinely available, we first study
the ordinary patterns in demand. Member 2 will explain those diagnostics.”

## Member 2 — EDA, dependence, stationarity and spectra

**Slides:** 6–10  
**Estimated time:** 5 minutes

### What this member presents

- Long-run training series and daily aggregation.
- Weekday profiles and winter-summer variation.
- Lag correlations, ACF and the weekly seasonal-naive benchmark.
- Differencing, rolling mean and rolling standard deviation.
- ADF and Phillips–Perron evidence.
- Periodogram peaks and the effects of seasonal differencing.

### What this member must learn

1. **Trend versus seasonality:** a decline over part of a year is not proof of a
   permanent trend when it later reverses.
2. **Autocorrelation:** correlation between the series and its own lagged values.
3. **ACF versus PACF:** ACF includes direct and indirect lag relationships; PACF removes
   the linear effect of shorter lags.
4. **Stationarity:** constant unconditional mean and variance, with covariance depending
   on lag rather than calendar position.
5. **Unit root:** a source of persistent non-stationarity in which shocks do not decay
   conventionally.
6. **ADF and PP null:** both test a unit-root null, but handle serial correlation
   differently; disagreement requires caution.
7. **Frequency and period:** period equals one divided by frequency.
8. **Periodogram:** an estimate of how variance is distributed across frequencies; it
   identifies cycles but not their cause or timing within the cycle.

### Numbers to know

- Lag correlations: 0.989 at lag 1, 0.914 at lag 48, 0.893 at lag 336.
- Weekly-naive validation: MAE 1,946 MW, RMSE 2,541 MW.
- Raw ADF p-value: 0.3426; raw PP p-value is extremely small.
- The tests agree on rejecting a unit root for each differenced series.
- Main spectral frequencies: 1/7, 1, 2, 3 and 4 cycles per day.

### Questions this member should answer

- Why is lag 1 not a valid day-ahead predictor for tomorrow evening?
- Why do many ACF lags appear significant?
- Does rejecting a unit root prove stationarity?
- Why can ADF and PP disagree?
- Why does weekly differencing create a comb of spectral notches?

### Handoff

“These diagnostics establish strong daily and weekly structure, but forecasting quality
must be tested out of sample. Member 3 will explain the model progression.”

## Member 3 — Forecasting models and diagnostics

**Slides:** 11–15  
**Estimated time:** 6 minutes

### What this member presents

- Rolling-origin day-ahead evaluation.
- Weekly naive, calendar regression and multi-lag Ridge.
- Recursive AR, direct residual ARX and ARMA residual models.
- Exogenous Ridge ablation using weather, wind and solar forecasts.
- 2025 and 2026 out-of-sample results.
- Residual autocorrelation and GARCH limitations if asked.

### What this member must learn

1. **Ridge regression:** least squares plus an L2 coefficient penalty; useful when many
   lag and seasonal features are correlated.
2. **Recursive forecasting:** fit a short-step residual equation and feed predictions
   back into later steps.
3. **Direct residual ARX:** directly predicts a residual at the required horizon using
   autoregressive history and exogenous variables known at the cutoff.
4. **ARMA:** autoregressive terms use past residuals; moving-average terms use past
   innovations.
5. **SARIMAX:** ARIMA with seasonal components and exogenous inputs. The tested seasonal
   specification did not converge reliably.
6. **MAE, RMSE and bias:** MAE describes typical magnitude; RMSE penalizes large misses;
   signed mean error describes average direction.
7. **ARCH/GARCH:** models changing conditional variance, not the mean point forecast.
8. **Model selection discipline:** select on rolling validation; report a test result
   without changing the model after seeing it.

### Numbers to know

- Four-fold development: naive 2,154; multi-lag Ridge 1,467; recursive AR 1,381;
  direct ARX 1,348 MW MAE.
- 2025 test: direct ARX model 1,622 versus naive 3,101 MW.
- Corrected seven-fold development: exogenous Ridge 825; recursive AR 777; ARMA(1,1)
  802; direct ARX 750 MW.
- Corrected 2026 retrospective: exogenous Ridge 1,005; ARMA 970; direct ARX 931;
  recursive AR 918; NESO 807 MW.

### Questions this member should answer

- Why use Ridge rather than ordinary least squares for the large base model?
- What is the difference between recursive AR and direct ARX?
- Why did ARMA help less than direct ARX?
- Why did you retain direct ARX when recursive AR was lower in the 2026 period?
- Why does NESO still perform better?
- Did GARCH make errors independent or variance constant?

### Handoff

“The selected model gives a stronger estimate of normal demand. Member 4 will explain
whether scheduled football information improves that counterfactual.”

## Member 4 — Football experiment, conclusion and limitations

**Slides:** 16–17  
**Estimated time:** 4 minutes plus conclusion

### What this member presents

- Fractional pregame, scheduled-play, halftime-proxy and post-match windows.
- Fixture-level and tournament-edition validation.
- EURO 2024 event-window, fixture and halftime results.
- Predictive versus causal interpretation.
- Limitations and future confirmation requirements.

### What this member must learn

1. **Event-blind forecast:** a forecast created without football labels.
2. **Scheduled overlap:** the fraction of a half-hour lying inside a predeclared event
   window.
3. **Halftime proxy:** scheduled minute 45 to 75, not verified whistle-to-whistle timing.
4. **Clustered evidence:** half-hours within one match share conditions; seven matches
   are seven clusters rather than approximately seventy independent experiments.
5. **Predictive association:** a schedule coefficient may improve forecasting without
   identifying football as the cause.
6. **Fixture heterogeneity:** a correction can help some opponents and harm others, so
   aggregate improvement can be unstable.

### Numbers to know

- EURO 2024 primary-window MAE: event-blind 1,130, match-aware 1,052, NESO 614 MW.
- Only three of seven fixtures improve.
- Halftime-proxy MAE worsens from 808 to 984 MW.
- Pregame improves by 158 MW and post-match improves by 166 MW.
- Scheduled-play MAE worsens by 177 MW.

### Questions this member should answer

- Did you prove that halftime causes a demand increase?
- Why is the halftime interval only a proxy?
- Is seven-match evidence enough?
- Why did aggregate event-window MAE improve while halftime worsened?
- What would make a future match-aware model credible?

### Closing line

“We achieved a materially stronger day-ahead model of ordinary demand, but scheduled
football information did not produce a stable halftime improvement. A future untouched
tournament is needed before making a robust match-aware forecasting claim.”

## Group rehearsal protocol

1. Each member first explains their slides without reading the script.
2. The next member asks two questions from the question bank.
3. The group checks that every metric includes its evaluation period.
4. Rehearse the three handoffs so the talk sounds continuous.
5. Target 16 to 20 minutes and reserve at least five minutes for questions.
6. One member controls the slides; speakers should not turn to read the screen.
