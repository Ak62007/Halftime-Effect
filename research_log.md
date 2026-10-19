# Research log

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
