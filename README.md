# The Halftime Effect

This project studies half-hourly Great Britain electricity demand and asks whether
known England football schedules improve a day-ahead forecast.

## Presentation-ready model scope

The retained modelling progression is:

1. weekly seasonal naive;
2. calendar seasonal regression and a weekly-lag extension;
3. multi-lag Ridge regression;
4. recursive autoregressive residual forecasts;
5. direct residual ARX Ridge;
6. small ARMA residual models and a documented SARIMAX feasibility test;
7. plain Ridge with issued weather, embedded wind and embedded solar forecasts;
8. ARCH diagnostics and GARCH(1,1) conditional variance;
9. linear scheduled-window football corrections.

Temperature splines, histogram gradient boosting, boosting-based variance models and
linear-boosting blends are excluded from the presentation branch.

## Headline results

- Corrected seven-fold development MAE falls from 2,039 MW for weekly naive to
  825 MW for plain exogenous Ridge.
- Recursive AR residuals reach 777 MW, ARMA(1,1) reaches 802 MW and the selected direct
  residual ARX Ridge model reaches 750 MW.
- In the retrospective January to March 2026 evaluation, direct ARX records 931 MW MAE;
  NESO records 807 MW on the rows where its forecast is available.
- The EURO 2024 scheduled-window correction reduces aggregate MAE from 1,130 to
  1,052 MW, but halftime-proxy MAE worsens from 808 to 984 MW.
- The football analysis remains predictive and does not establish a causal effect.

## Presentation materials

- [Complete 17-slide plan](docs/presentation/00_complete_plan.md)
- [Verified results](docs/presentation/01_verified_model_results.md)
- [Slide-by-slide script](docs/presentation/02_slide_by_slide_script.md)
- [Four-member assignment](docs/presentation/03_team_assignment_and_learning.md)
- [Teacher question bank](docs/presentation/04_teacher_question_bank.md)
- [Model equations](docs/presentation/05_model_equations.md)

## Reproduction

```bash
.venv/bin/python src/build_event_blind_v2_data.py
.venv/bin/python src/evaluate_v2_regression_candidates.py
.venv/bin/python src/evaluate_v2_ar_error_candidates.py
.venv/bin/python src/evaluate_v2_direct_residual_candidates.py
.venv/bin/python src/diagnose_v2_garch.py
.venv/bin/python src/evaluate_event_blind_v2_final_test.py

.venv/bin/python src/evaluate_v3_ridge_ablation.py
.venv/bin/python src/evaluate_presentation_scope_dynamics.py
.venv/bin/python src/evaluate_presentation_scope_arma.py
.venv/bin/python src/evaluate_presentation_scope_final_test.py

.venv/bin/python src/fit_event_blind_models.py
.venv/bin/python src/select_match_correction.py
.venv/bin/python src/select_tournament_correction.py
.venv/bin/python src/evaluate_euro_2024_holdout.py

.venv/bin/python -m unittest discover -s tests -v
```
