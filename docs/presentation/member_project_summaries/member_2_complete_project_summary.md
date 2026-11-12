# The Halftime Effect complete project summary from Tausheef

## My overall view of the project

I understand this project as an investigation of the patterns hidden inside electricity-demand data.
The football question was the motivation, but the first major challenge was understanding how demand
normally behaves. If ordinary seasonal and calendar patterns are not modelled correctly, a normal change
could easily be mistaken for a football-related effect.

## What the data showed

We used half-hourly Great Britain demand outturn from NESO as the target and placed every observation on
a continuous UTC timeline. London time supplied weekday, clock and holiday meaning. We also used demand
history, archived weather forecasts, embedded wind and solar forecasts, and published England fixture
information. All operational predictors had to be known by the previous-day forecast cutoff.

The exploratory plots showed that demand has several overlapping cycles. Winter levels were generally
higher than summer levels. Working days showed a strong morning rise and a later peak, while weekends
had weaker morning patterns. Winter Mondays stayed above summer Mondays and peaked earlier. This showed
that season affects both the level and shape of the daily demand curve.

The ACF gave numerical evidence of this memory. Correlation was 0.989 at lag 1, 0.914 at lag 48 and
0.893 at lag 336. Lag 336 represents one week and became the leakage-safe seasonal-naive benchmark.
Differencing made the series more stable around zero, although changing variance and seasonal dependence
remained. ADF failed to reject the raw-series unit-root null, while Phillips-Perron rejected it, so we
reported the disagreement instead of forcing a simple conclusion. The periodogram supported weekly,
daily and daily-harmonic frequencies.

## How this evidence shaped the models

The diagnosed patterns motivated calendar effects, annual seasonality and leakage-safe lags. Multi-lag
Ridge improved on weekly naive by handling many correlated predictors. Archived weather forecasts and
embedded wind and solar forecasts produced further gains. Residual structure was then modelled with
recursive AR, ARMA and direct residual ARX. Direct ARX achieved 750 MW mean MAE in development validation
and was selected before later evaluation periods were examined.

## My interpretation of the football result

The EURO 2024 match-aware forecast improved aggregate event-window MAE from 1,130 to 1,052 MW. However,
only three of seven fixtures improved, and halftime MAE became worse, rising from 808 to 984 MW. From my
perspective, the time-series analysis successfully explained much of ordinary demand, but it did not
reveal a stable repeating halftime pattern. The result is predictive rather than causal, and a stronger
claim would require more tournaments, verified whistle times and finer-frequency demand data.
