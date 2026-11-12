# The Halftime Effect complete project summary from Himanshu Kumar

## My overall view of the project

From my perspective, this project is mainly about designing a fair test of an interesting forecasting
question. We wanted to know whether the published timing of England football matches could improve
half-hourly forecasts of Great Britain electricity demand, with particular interest in halftime. We
quickly recognised that simply comparing demand before and during halftime would not be reliable. Demand
also changes with time of day, weekday, season, holidays, weather and embedded electricity generation.
Our solution was to build a normal-demand forecast first and test football information only after that
baseline had been established.

## Data and preparation

The target variable is NESO electricity demand outturn measured in MW for each half-hour. We combined it
with London calendar information, historical demand lags, archived weather forecasts, embedded wind and
solar forecasts, and verified England fixture schedules. UTC was used to keep the time series complete
and uniquely ordered, while London time was used for human calendar features. We checked missing values,
duplicates, units, daylight-saving transitions and source timing. Each day-ahead forecast follows a
10:00 London time cutoff on the previous day, which prevents realized target-day information from leaking
into the model.

## Analysis and modelling

The EDA showed strong annual, daily and weekly structure. Demand was generally higher in winter, working
days had stronger morning and evening peaks, and weekend profiles were different. Autocorrelation was
high at lag 1, lag 48 and lag 336, showing short-run, daily and weekly memory. ADF and Phillips-Perron
tests disagreed on the raw series, while both rejected a unit root after differencing. Spectral analysis
also confirmed weekly, daily and harmonic cycles.

We began forecasting with a weekly seasonal-naive benchmark. Calendar regression, multi-lag Ridge,
recursive residual AR and direct residual ARX progressively improved accuracy. Weather and embedded wind
and solar forecasts added substantial predictive information. Direct residual ARX achieved the best
development result at 750 MW mean MAE. On the locked 2025 test, the earlier V2 direct-ARX model achieved
1,622 MW MAE compared with 3,101 MW for weekly naive, although NESO remained more accurate.

## Final result and conclusion

The match-aware model added scheduled pregame, play, halftime-proxy and post-match windows. On EURO 2024,
aggregate event-window MAE improved from 1,130 to 1,052 MW, but only three of seven fixtures improved.
Halftime-proxy MAE worsened from 808 to 984 MW. I therefore see the project as a successful forecasting
study with an honest negative halftime finding. We developed a credible, leakage-safe baseline, but the
evidence did not verify a stable halftime-specific or causal football effect.
