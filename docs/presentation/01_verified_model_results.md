# Verified model results for the presentation

This document is the numerical source of truth for the presentation. Results from
different evaluation periods must remain in separate tables.

## 1. Initial March to May 2024 validation

Ordinary days only, 4,318 half-hours.

| Forecast | MAE | RMSE | Mean error, actual minus forecast |
|---|---:|---:|---:|
| Weekly seasonal naive | 1,933 MW | 2,526 MW | -635 MW |
| Calendar seasonal regression | 1,536 MW | 1,933 MW | +490 MW |
| Calendar plus weekly lag, full history | 1,444 MW | 1,846 MW | +326 MW |
| Calendar plus weekly lag, recent history | **1,406 MW** | **1,812 MW** | -78 MW |
| NESO day-ahead | 681 MW | 914 MW | -58 MW |

## 2. Four-fold development comparison for the retained V2 models

| Forecast | Mean fold MAE | Mean fold RMSE | Worst fold MAE |
|---|---:|---:|---:|
| Weekly seasonal naive | 2,154 MW | 2,745 MW | 2,966 MW |
| Calendar plus weekly lag | 1,616 MW | 2,065 MW | 2,070 MW |
| Multi-lag Ridge | 1,467 MW | 1,894 MW | 1,664 MW |
| Ridge plus recursive AR(1,2,48,96) residuals | 1,381 MW | 1,787 MW | 1,529 MW |
| **Ridge plus direct residual ARX** | **1,348 MW** | **1,746 MW** | **1,518 MW** |
| NESO day-ahead | 623 MW | 822 MW | 690 MW |

The daily seasonal SARIMAX feasibility specification `(2,0,1) x (1,0,1,48)` reached
its iteration limit without convergence and was rejected.

## 3. January to March 2025 locked test

All project models use 4,318 half-hours.

| Forecast | MAE | RMSE | Mean error |
|---|---:|---:|---:|
| Weekly seasonal naive | 3,101 MW | 3,955 MW | -101 MW |
| Calendar plus weekly lag | 2,401 MW | 3,007 MW | +881 MW |
| **Multi-lag Ridge plus direct residual ARX** | **1,622 MW** | **2,141 MW** | +202 MW |
| NESO day-ahead | 781 MW | 1,051 MW | -114 MW |

The retained model improves MAE by 32.4% over the calendar model and 47.7% over weekly
naive.

## 4. Seven-fold exogenous Ridge ablation

These figures were recomputed after removing spline and boosting models.

| Plain Ridge feature set | Mean fold MAE | Worst fold MAE |
|---|---:|---:|
| Reproduced demand-lag Ridge | 1,418 MW | 1,664 MW |
| Rich calendar | 1,400 MW | 1,644 MW |
| Archived weather forecasts | 1,265 MW | 1,336 MW |
| Embedded wind and solar forecasts | 1,062 MW | 1,262 MW |
| **All exogenous inputs, recent 730 days** | **825 MW** | **925 MW** |
| All exogenous inputs, recent 1,095 days | 825 MW | 935 MW |
| NESO day-ahead | 633 MW | 690 MW |

The 1,095-day model is lower by only 0.2 MW in mean MAE. The 730-day model has lower
absolute bias and a better worst fold, so it remains the base for the corrected dynamic
comparison.

## 5. Corrected residual-dynamics comparison

All candidates use the same plain exogenous Ridge base. No spline or boosting model is
present.

| Forecast | Mean fold MAE | Mean fold RMSE | Worst fold MAE |
|---|---:|---:|---:|
| Plain exogenous Ridge | 825 MW | 1,103 MW | 925 MW |
| Recursive AR(1,2) | 813 MW | 1,089 MW | 905 MW |
| Recursive AR(1,2,48) | 777 MW | 1,052 MW | 850 MW |
| Recursive AR(1,2,48,96) | 777 MW | 1,051 MW | 849 MW |
| Recursive AR(1,2,48,96,336) | 781 MW | 1,054 MW | 852 MW |
| ARMA(1,1) | 802 MW | 1,078 MW | 886 MW |
| ARMA(2,1) | 818 MW | 1,095 MW | 913 MW |
| ARMA(2,2) | 818 MW | 1,095 MW | 913 MW |
| **Direct residual ARX Ridge** | **750 MW** | **1,021 MW** | **830 MW** |

Direct residual ARX Ridge is selected by development MAE.

## 6. January to March 2026 scope-corrected evaluation

This period was opened by earlier experiments. It is therefore a retrospective
scope-corrected evaluation, not a newly untouched test.

| Forecast | Rows | MAE | RMSE | Mean error |
|---|---:|---:|---:|---:|
| Weekly seasonal naive | 4,318 | 2,464 MW | 3,334 MW | -131 MW |
| Plain exogenous Ridge | 4,318 | 1,005 MW | 1,357 MW | +577 MW |
| Ridge plus ARMA(1,1) | 4,318 | 970 MW | 1,315 MW | +525 MW |
| Ridge plus direct residual ARX | 4,318 | **931 MW** | 1,263 MW | +383 MW |
| Ridge plus recursive AR(1,2,48,96) | 4,318 | 918 MW | **1,255 MW** | +371 MW |
| NESO day-ahead, available rows | 4,222 | **807 MW** | **1,103 MW** | +65 MW |

Recursive AR happens to score 13 MW lower than the development-selected direct ARX
model. We do not change the model after seeing this period. The presentation reports
both and retains direct ARX as the selected research specification.

## 7. GARCH uncertainty findings

GARCH changes forecast variance, not the point forecast.

| Result | Development | January to March 2025 test |
|---|---:|---:|
| Variance persistence, alpha plus beta | 0.980 average | 0.973 |
| Central 80% interval coverage | 80.5% | 75.7% |
| Central 95% interval coverage | 93.6% | 90.1% |

ARCH-LM still rejects after standardization. GARCH captures part of the changing scale,
but the test intervals under-cover and the model does not remove common within-day
forecast shocks.

## 8. EURO 2024 scheduled-window result

The primary window contains pregame, scheduled-play and post-match rows for seven
fixtures.

| Forecast | MAE | RMSE | Mean error |
|---|---:|---:|---:|
| Weekly seasonal naive | 1,143 MW | 1,583 MW | -470 MW |
| Event-blind calendar and weekly-lag forecast | 1,130 MW | 1,426 MW | +909 MW |
| Match-aware four-window forecast | **1,052 MW** | **1,254 MW** | -550 MW |
| NESO day-ahead | **614 MW** | **799 MW** | -349 MW |

Only three of seven fixtures improve. The fixture-bootstrap interval for the mean MAE
change crosses zero widely.

| Window | Event-blind MAE | Match-aware MAE | Result |
|---|---:|---:|---|
| Pregame | 1,424 MW | 1,265 MW | 158 MW better |
| Scheduled play | 799 MW | 976 MW | 177 MW worse |
| Halftime proxy | 808 MW | 984 MW | 176 MW worse |
| Post-match | 1,032 MW | 866 MW | 166 MW better |

The aggregate gain does not constitute a successful halftime-aware forecast.
