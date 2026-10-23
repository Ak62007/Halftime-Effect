# Research log

## 23 October 2026 — Consolidate descriptive EDA

- **Work:** the student plotted the continuous training series, local daily means, a February week, seven weekday mean profiles, Monday/Friday/Saturday quartile bands, and winter/summer Monday profiles.
- **Correction:** London time must be derived in the parent DataFrame before selecting baseline observations. Earlier UTC-based profile results were superseded; initial exploratory hypotheses remain preserved.
- **Evidence:** corrected Monday IQR is widest at 17:00 (11,833 MW) and narrowest at 23:00 (2,945 MW). At 17:00, summer Monday IQR is 1,747.25 MW and winter Monday IQR is 4,299.75 MW. Seasonal groups have 12 and 22 eligible Monday dates respectively.
- **Interpretation:** seasonal mixing contributes to pooled spread; observed calendar associations do not isolate causal mechanisms. IQR bands describe observations, not confidence or prediction intervals.
- **Artifact:** `analyses/01_demand_eda_analysis.md` documents each step and embeds eight figures exported from the saved notebook. Numerical findings were cross-checked against finalized development data.
- **Next:** guided autocorrelation analysis on the complete training timeline, then a seasonal naïve benchmark. No ACF, fitted model, or event-effect results have been generated yet.

## 19 October 2026 — Freeze the core dataset

- **Question:** can the project move beyond feasibility without relying on an unverified five-minute summary transformation?
- **Authorization:** the student requested that the mentor complete remaining data acquisition, verification, and selection so they can focus on analysis.
- **Decision:** use NESO forecast-performance `Demand_Outturn` as the half-hourly primary target. The high-frequency extension is dropped from the core, following the specification's stop rule.
- **Evidence:** 27,742 complete observations over 578 London dates; all 21 scheduled fixture days covered; no null target or duplicate UTC timestamps; six tests pass. Retrospective regional weather and official holidays are aligned.
- **Problems resolved:** source strings carry literal Z while representing London clocks; UTC reconstructed from settlement keys and every supplied interval-end label checked. Forecast publication clocks converted with the same documented convention and all precede the fixed previous-day 10:00 London cutoff.
- **Limitations retained:** historic ND differs from the primary outturn (mean absolute difference 58.97 MW); never splice them. Exact whistle times are unknown. No claim to recover instantaneous pickups. Temperature is reanalysis, so excluded from operational forecasting features.
- **Evaluation boundary:** train through February 2024; validation March–May; June bridge separated; tournament period is event holdout. Ten earlier fixtures are training candidates and two March friendlies remain validation events.
- **Artifacts:** `docs/finalized_dataset.md`, `configs/data_contract.json`, `src/finalize_data.py`, processed tables, audit JSON, hashes, and `tests/test_finalized_data.py`.
- **Next student milestone:** EDA of ordinary pre-tournament demand using the development file; first daily means and local weekday profiles, then explanations. No tournament-outcome inspection or modelling was performed in finalization.
