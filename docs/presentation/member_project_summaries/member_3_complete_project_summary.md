# The Halftime Effect complete project summary from Gautam Chhabra

## My overall view of the project

From my perspective, the main story is the progression from a simple benchmark to a stronger day-ahead
forecasting system. The project asked whether England fixture timing adds useful information, but that
question could only be answered after building the best reasonable event-blind forecast from the data and
methods available to us.

## Forecasting setup

The target was NESO half-hourly demand outturn in MW. Forecasts were issued by 10:00 London time on the
previous day. Calendar variables, historical demand lags, archived weather forecasts and embedded wind
and solar forecasts were allowed only when available by that cutoff. Chronological rolling validation
replaced random splitting so that model selection recreated genuine forecasting conditions.

EDA and diagnostic analysis showed annual, daily and weekly seasonality. Strong ACF values at daily and
weekly lags justified seasonal features and a weekly-naive benchmark. Differencing and unit-root tests
showed that transformations improved stability without removing all dependence. Spectral analysis
confirmed the same daily and weekly cycles in the frequency domain.

## Model development and performance

Across four development folds, weekly naive recorded 2,154 MW mean MAE. Calendar plus weekly-lag
regression reduced this to 1,616 MW. Multi-lag Ridge reached 1,467 MW, recursive residual AR reached
1,381 MW, and direct residual ARX reached 1,348 MW. Ridge was suitable because the model contained many
correlated lag and seasonal predictors.

The next stage added richer exogenous information. The reproduced Ridge model scored 1,418 MW mean MAE.
Issued weather reduced this to 1,265 MW, embedded wind and solar to 1,062 MW, and all exogenous inputs
together to 825 MW. Using this stronger base, recursive AR achieved 777 MW, ARMA(1,1) achieved 802 MW,
and direct residual ARX achieved 750 MW. Direct ARX was selected because it directly predicted each
target horizon from cutoff-known residual history and exogenous inputs. Although recursive AR was 13 MW
better in the later 2026 retrospective period, we retained direct ARX because it had already won
development validation.

## Final football experiment

The match-aware model added scheduled pregame, play, halftime-proxy and post-match overlap features. Its
aggregate EURO 2024 event-window MAE was 1,052 MW compared with 1,130 MW for the event-blind forecast.
However, only three of seven fixtures improved, and halftime MAE worsened from 808 to 984 MW. I conclude
that the project made major progress in normal-demand forecasting, while football timing delivered only
limited and unstable predictive value. The evidence does not support a reliable halftime-specific model.
