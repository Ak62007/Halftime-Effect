# Match-aware forecasting with the locked v3 baseline

Branch: `match-aware-v3`

This experiment asks whether a known England tournament schedule improves the locked
event-blind v3 day-ahead point forecast. It is predictive, not causal: a schedule
coefficient cannot establish that football caused the corresponding demand change.

The experiment has two deliberately separated stages:

1. [Protocol and baseline construction](00_protocol.md)
2. [Historical cross-edition selection](01_historical_selection.md)

EURO 2024 was already opened in the earlier project. Its new result will therefore be
reported only as a retrospective diagnostic, never as a fresh holdout. Confirmation
requires a future tournament whose outcomes have not been used during development.
