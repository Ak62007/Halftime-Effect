# Retained model equations and inputs

Notation:

- `y(t)` is half-hourly demand outturn in MW.
- `ŷ(t)` is the forecast.
- `e(t) = y(t) - ŷ(t)` is the signed residual.
- `h` is the day-ahead forecast horizon.
- `x(t)` contains calendar, seasonal, lag and issued exogenous inputs.

## 1. Weekly seasonal naive

```text
ŷ(t) = y(t - 336)
```

Input: demand exactly 336 half-hours earlier.  
Output: one half-hourly demand forecast in MW.

## 2. Calendar seasonal regression

```text
y(t) = calendar_slot(t)'β
     + annual_slot_terms(t)'γ
     + δ trend(t)
     + η holiday(t)
     + e(t)
```

The calendar-slot vector contains 336 half-hour-of-week indicators. Annual sine and
cosine terms can vary with the weekly slot. Coefficients are estimated by least squares.

## 3. Calendar regression with weekly lag

```text
y(t) = calendar_and_annual_terms(t)
     + ρ y(t - 336)
     + e(t)
```

The lag contributes the latest same-weekday level, while deterministic terms describe
the usual calendar shape.

## 4. Multi-lag Ridge regression

```text
ŷ(t) = x(t)'β̂

β̂ = argmin over β {
       Σ [y(t) - x(t)'β]² + λ Σ β(j)²
     }
```

The intercept is not penalized. Inputs include:

- 336 half-hour-of-week effects;
- annual seasonal sine and cosine terms;
- trend and bank-holiday indicators;
- safe daily lags 96, 144, 192, 240 and 288;
- weekly lags 336, 672, 1008 and 1344;
- recent lag means, standard deviations and changes.

## 5. Plain exogenous Ridge regression

```text
ŷ_base(t) = x_exogenous(t)'β̂_ridge
```

This extends the multi-lag Ridge inputs with:

- day-before and day-after bank-holiday flags;
- Christmas Eve, New Year's Eve and 2 January indicators;
- archived issued temperature forecasts for London, Manchester and Birmingham;
- GB temperature, heating-degree and cooling-degree forecasts;
- daily temperature summaries and change from the prior day;
- embedded wind and solar forecasts, capacities and capacity factors;
- week-over-week changes in embedded wind and solar forecasts.

The NESO demand forecast is not an input.

## 6. Recursive AR residual correction

First calculate base residuals:

```text
e(t) = y(t) - ŷ_base(t)
```

Then fit:

```text
e(t) = c + Σ φ(j) e(t - lag(j)) + u(t)
```

The main retained candidate uses lags 1, 2, 48 and 96. After the forecast cutoff,
unknown residuals are replaced recursively by earlier residual forecasts:

```text
ŷ_recursive(t) = ŷ_base(t) + ê_recursive(t)
```

## 7. Direct residual ARX Ridge

For target horizon `h`:

```text
e(d,h) = z(d,h)'γ + v(d,h)

ŷ_ARX(d,h) = ŷ_base(d,h) + ê(d,h)
```

`z(d,h)` contains only cutoff-known information:

- residual lags 96, 144, 192, 240, 288, 336 and 672;
- latest residual known at the cutoff;
- residual means over the previous 6, 12, 24 and 48 hours;
- residual standard deviations over 24 and 48 hours;
- forecast horizon and its interaction with recent residual level;
- clock Fourier terms and weekday indicators;
- base forecast, weather, holiday, embedded wind and embedded solar inputs.

The correction is direct because it maps cutoff-known information to each target
horizon rather than relying on tomorrow's earlier realized residuals.

## 8. ARMA residual model

For ARMA(p,q):

```text
e(t) = c
     + Σ from i=1 to p φ(i)e(t-i)
     + Σ from j=1 to q θ(j)u(t-j)
     + u(t)
```

Candidates: ARMA(1,1), ARMA(2,1) and ARMA(2,2). At issuance, known residuals and
innovations initialize the forecast; later residuals are generated recursively.

## 9. GARCH(1,1) conditional variance

GARCH does not change the point forecast. It models residual variance:

```text
e(t) = σ(t) z(t)

σ(t)² = ω + α e(t-1)² + β σ(t-1)²
```

`α + β` measures variance persistence. Values near one indicate slowly decaying
volatility regimes.

## 10. Scheduled-window match correction

```text
ŷ_match(t) = ŷ_event_blind(t)
           + γ1 PregameOverlap(t)
           + γ2 ScheduledPlayOverlap(t)
           + γ3 HalftimeProxyOverlap(t)
           + γ4 PostMatchOverlap(t)
```

Each overlap lies between zero and one. The model uses only scheduled fixture metadata
known before delivery. The coefficients estimate recurring forecast adjustments
associated with scheduled windows; they do not identify a causal football effect.

## Error metrics

```text
ME   = mean(y - ŷ)
MAE  = mean(|y - ŷ|)
RMSE = sqrt(mean((y - ŷ)²))
```

Positive ME means average underforecasting. RMSE exceeds MAE when larger misses receive
extra weight from squaring.
