# Teacher question bank

Answers should begin with the direct conclusion, then give one reason and one caveat.

## Research design and data

### 1. What exactly are you predicting?

Half-hourly Great Britain electricity-demand outturn in MW. The main operational task
is a day-ahead point forecast issued at 10:00 London time on the preceding day.

### 2. Why use MW rather than MWh?

The NESO target is demand power in MW for each settlement interval. MWh would represent
energy accumulated over the half-hour and would equal average MW multiplied by 0.5
hours.

### 3. Why use national demand rather than household consumption?

The available consistent high-frequency target is national network demand. It includes
more than households, so behavioural explanations about kettles or cooking remain
hypotheses rather than directly measured mechanisms.

### 4. What is embedded generation?

Generation connected within distribution networks, such as local solar and wind, can
reduce the demand observed by the transmission system. This makes issued embedded-
generation forecasts useful inputs for predicting transmission-visible demand.

### 5. Why use both UTC and London time?

UTC creates a unique regular chronological sequence. London time supplies relevant
clock, weekday and holiday labels. Autumn repeats a local hour and spring skips one,
so a local timestamp alone is not a unique elapsed-time index.

### 6. Why do clock-change days have 46 or 50 intervals?

In spring, London moves forward and skips one local hour, removing two half-hours. In
autumn, London repeats one hour, adding two. UTC remains continuous in both cases.

### 7. How did you prevent leakage?

Every input must have an issue timestamp no later than the previous-day 10:00 cutoff.
Lagged demand is also checked by elapsed timestamp rather than assumed from row position.
Chronological folds replace random splitting.

### 8. Why is realized weather not allowed?

Tomorrow’s realized weather is unknown when a day-ahead forecast is issued. We use
archived issued weather forecasts to reproduce information that was genuinely
available.

## EDA, stationarity and spectra

### 9. Why is the winter-to-summer fall not necessarily a trend?

It reverses as the next winter approaches. That pattern is compatible with annual
seasonality. A persistent trend concerns the underlying level across repeated cycles,
and the initial EDA contains limited annual history.

### 10. What does an autocorrelation of 0.989 at lag 1 mean?

Adjacent half-hours have a very strong linear relationship. It does not mean 98.9%
forecast accuracy, and lag 1 is unavailable for tomorrow’s later intervals at the
day-ahead issuance time.

### 11. Why not include every significant ACF lag?

Raw demand contains deterministic seasonality and the sample is large, so many small
correlations become statistically detectable. Adjacent lag tests are dependent.
Forecast order should combine theory, availability and validation rather than count
significant stems.

### 12. What is the difference between ACF and PACF?

ACF measures the total relationship between observations separated by a lag. PACF
measures the remaining linear relationship at that lag after controlling for shorter
lags.

### 13. What is a unit root?

A unit root is a form of non-stationarity where shocks have persistent effects and the
level can wander. Differencing can remove a conventional unit-root component, but it
does not automatically remove seasonality or changing variance.

### 14. Why do ADF and Phillips–Perron disagree for raw demand?

They share a unit-root null but handle serial correlation differently. Demand has
strong, complex seasonality and both tests require modelling choices. The disagreement
is reported as uncertainty rather than resolved by selecting the preferred p-value.

### 15. Does rejecting a unit root prove stationarity?

No. The test addresses one specific source of non-stationarity. Seasonal dependence,
changing variance and structural changes can remain.

### 16. What does the periodogram add beyond the ACF?

The ACF displays dependence by lag. The periodogram displays power by frequency. It
confirms weekly, daily and harmonic cycles and shows which frequencies different
seasonal differences suppress.

### 17. Why are there harmonics at two, three and four cycles per day?

The daily demand curve is not a perfect sine wave. Morning and evening changes create a
more complex shape that requires multiples of the daily fundamental frequency.

## Forecasting models

### 18. Why is weekly seasonal naive a meaningful benchmark?

It aligns the weekday and clock phase using genuinely available demand from one week
earlier. A learned model should improve on this strong, transparent rule before its
extra complexity is justified.

### 19. What does Ridge regression do?

Ridge minimizes squared error plus an L2 penalty on coefficients. It stabilizes a large
set of correlated lag, calendar and seasonal features by shrinking coefficients rather
than selecting them individually.

### 20. Why use multiple safe lags?

Different prior days and weeks carry information about the current demand level and
recent changes. The lags begin far enough in the past to exist at the day-ahead cutoff.

### 21. Recursive AR versus direct ARX: what is the difference?

Recursive AR estimates a residual equation and repeatedly feeds its own forecasts into
later steps. Direct ARX predicts the target-horizon residual from cutoff-known residual
history, horizon, calendar and exogenous inputs. Direct ARX avoids long recursive error
propagation but estimates a richer relationship.

### 22. Why did ARMA improve less than direct ARX?

Moving-average innovations mainly influence early recursive steps, while delivery
begins many half-hours after the issue cutoff. Direct ARX explicitly represents horizon
and cutoff summaries, which are better aligned with the day-ahead task.

### 23. Why was SARIMAX rejected?

The tested `(2,0,1) x (1,0,1,48)` residual specification reached the iteration limit
without reliable convergence and produced unstable, partly cancelling coefficients. We
rejected that fit rather than presenting an unreliable likelihood result.

### 24. Why keep direct ARX when recursive AR scores lower in 2026?

Direct ARX won the seven-fold development comparison, 750 versus 777 MW. The 2026
period was already opened, so switching after seeing its 918 versus 931 MW result would
use the evaluation period for model selection.

### 25. What information generated the largest improvement?

Archived issued weather and embedded wind and solar forecasts. Calendar enrichment
alone produced a small gain, while combining all forecast-available inputs reduced
plain-Ridge development MAE to about 825 MW.

### 26. Why does NESO still perform better?

NESO has a richer operational forecasting process and likely more detailed system,
weather and demand information. Our goal is a reproducible academic model, not a claim
to replace the system operator’s production forecast.

### 27. Are the model residuals independent?

No. Short-lag residual autocorrelation remains strong. Adjacent half-hours share common
day-level weather and system shocks that cannot be updated after a fixed day-ahead
issuance time.

### 28. Did GARCH create constant variance?

No. It captured persistent changes in conditional scale, with alpha plus beta around
0.97 to 0.98, but ARCH-LM still rejected after standardization and final intervals
under-covered.

## Football experiment

### 29. What is the halftime proxy?

A predeclared scheduled interval from match minute 45 to 75. It allows for the nominal
halftime region within half-hourly data but does not use actual whistle and restart
times.

### 30. Why use fractional overlap features?

A 19:45 kickoff or a window boundary can fall inside a settlement interval. Fractional
overlap records whether 5, 15 or 30 minutes of that row belong to the scheduled window,
rather than assigning the whole half-hour incorrectly.

### 31. Did the model prove a halftime electricity effect?

No. EURO 2024 halftime-proxy MAE worsened from 808 to 984 MW after correction. More
fundamentally, the observational schedule design cannot isolate football from all
correlated factors.

### 32. How can the primary window improve while halftime worsens?

The primary score combines pregame, scheduled play and post-match rows. Pregame and
post-match errors improved enough to reduce the aggregate score, while scheduled-play
and halftime scores became worse.

### 33. Is seven matches enough?

It is enough for a transparent case study but not for a robust general effect. The
half-hours within one match are dependent, so the effective event sample is seven
clusters. Only three fixtures improved and the fixture-bootstrap interval crossed zero.

### 34. What would strengthen the evidence?

More tournament editions, verified actual halftime timestamps, audience or match-
importance inputs known in advance, richer forecast vintages and evaluation on a future
tournament kept untouched throughout model development.

### 35. What is the final conclusion in one sentence?

Forecast-available calendar, lag, weather and renewable information produces a much
stronger day-ahead demand model, but the available football schedule data does not
support a stable halftime-aware improvement or a causal claim.
