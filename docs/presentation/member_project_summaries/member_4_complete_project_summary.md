# The Halftime Effect complete project summary from Aditya Kumar

## My overall view of the project

I see this project as an exercise in critical evaluation. The original idea was attractive: simultaneous
viewer behaviour during England matches might create a recognisable electricity-demand pattern. Our task
was not to prove that idea at any cost. It was to test it using a realistic forecast, report uncertainty
and accept a negative result if the evidence did not support a halftime effect.

## How the project was built

We used NESO half-hourly Great Britain demand outturn in MW as the target. The dataset was aligned on a
complete UTC sequence, with London time used for calendar behaviour. We combined demand with calendar
variables, safe historical lags, archived weather forecasts, embedded wind and solar forecasts, and
verified fixture schedules. A fixed previous-day issue cutoff prevented future information leakage.

The initial analysis found strong winter-summer differences, weekday and weekend shapes, and repeated
daily and weekly dependence. ACF, differencing, ADF and Phillips-Perron tests, and the periodogram showed
that the series contained several kinds of temporal structure. These findings made it clear that an
unadjusted same-time comparison would not be a credible measure of a match effect.

The forecasting models improved in stages. Calendar and lag regression beat weekly naive. Multi-lag
Ridge handled the larger correlated feature set. Archived weather and embedded-generation forecasts
added important signal. Recursive AR, ARMA and direct residual ARX modelled remaining error dynamics.
Direct ARX was selected at 750 MW mean development MAE. On the locked 2025 test, the earlier V2
direct-ARX model achieved 1,622 MW MAE compared with 3,101 MW for weekly naive. NESO's operational
forecast remained stronger, which gave us a realistic external standard.

## What the final evidence means

For EURO 2024, the match-aware model improved aggregate event-window MAE from 1,130 to 1,052 MW. This
headline result was not enough on its own. Only three of seven fixtures improved. Pregame and post-match
windows became better, while scheduled play and halftime became worse. Halftime MAE increased from
808 to 984 MW.

My conclusion is that the project produced a useful normal-demand forecasting model but did not confirm
the effect suggested by its title. Seven fixtures are a small sample, scheduled halftime is only a proxy,
half-hour data cannot isolate a brief pickup, and observational data cannot prove causality. A future
study should use more tournaments, verified whistle times, uncertainty intervals, finer-resolution data
and a completely untouched event holdout.
