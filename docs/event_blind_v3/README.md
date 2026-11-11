# Event-blind v3 forecasting experiment

V3 tests whether genuine ex-ante weather, embedded-generation and richer calendar
information can close the gap left by the v2 demand-lag model. All development choices
use rolling-origin folds ending in December 2025. January–March 2026 remains unopened
until the specification in `configs/event_blind_v3_model_lock.json` is committed.

## Reports

1. [Experiment plan](00_experiment_plan.md)
2. [Exogenous-data audit](01_data_audit.md)
3. [Development and model selection](02_model_selection.md)

The selected development forecast achieves 721 MW mean-fold MAE, compared with 1,418 MW
for the reproduced v2 Ridge base and 633 MW for NESO. This is a development result, not
the final v3 claim.
