# Event-blind v3 forecasting experiment

V3 tests whether genuine ex-ante weather, embedded-generation and richer calendar
information can close the gap left by the v2 demand-lag model. All development choices
use rolling-origin folds ending in December 2025. January–March 2026 remains unopened
until the specification in `configs/event_blind_v3_model_lock.json` is committed.

## Reports

1. [Experiment plan](00_experiment_plan.md)
2. [Exogenous-data audit](01_data_audit.md)
3. [Development and model selection](02_model_selection.md)
4. [Untouched January–March 2026 final test](03_final_test.md)

The locked v3 model achieves 982 MW MAE on untouched January–March 2026, a 39.0%
reduction from the refit locked-v2 specification. NESO remains stronger at 807 MW on
the 4,222 rows where its forecast was available by the shared cutoff. Locked v3
intervals under-cover, so the success is a point-forecast result rather than a complete
probabilistic-forecast solution.
