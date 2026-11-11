# The Halftime Effect

This repository studies whether scheduled England football matches improve forecasts
of half-hourly Great Britain electricity demand.

## Final presentation model

The final analysis is deliberately restricted to methods named in the supplied course
specification:

1. weekly seasonal naive;
2. seasonal regression with weekly and annual Fourier terms;
3. ARMA(2,1) errors as a tested but rejected extension;
4. scheduled-match and halftime flags as an unsuccessful exploratory extension;
5. ARCH diagnostics, without forcing GARCH into the final point forecast.

Start with the [syllabus-aligned final report](docs/syllabus_aligned/README.md). The
[alignment audit](docs/syllabus_alignment_audit.md) records which earlier experimental
methods were removed from the presentation-facing branch.

## Headline results

- Weekly seasonal naive ordinary-validation MAE: **1,933 MW**.
- Selected Fourier seasonal regression MAE: **1,483 MW**.
- Fourier regression with ARMA errors: **1,484 MW**, so it was rejected.
- During the seven EURO 2024 scheduled-match windows, Fourier regression MAE is
  **759 MW**; adding historical match flags worsens it to **948 MW**.
- During the halftime proxy, Fourier regression MAE is **812 MW**; match flags worsen
  it to **967 MW**.

The final conclusion is intentionally modest: Fourier seasonal regression improves the
weekly benchmark, while the available historical matches do not support a reliable
match-aware forecast. The work is predictive and does not establish a causal football
effect.

## Reproduction

```bash
.venv/bin/python src/build_forecast_dataset.py
.venv/bin/python src/evaluate_syllabus_aligned_models.py
.venv/bin/python src/plot_syllabus_aligned_results.py
.venv/bin/python -m unittest discover -s tests -v
```
