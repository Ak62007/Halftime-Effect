# Stage 3 — Forward match-aware model

After completing the retrospective diagnostic, the already-selected four-window shape
form is refitted on all 19 England fixtures from EURO 2020, World Cup 2022 and EURO
2024. This uses the available evidence for future deployment; it is not an evaluation.

| Scheduled term | Forward increment | Fixture-bootstrap 95% interval |
|---|---:|---:|
| Pregame | +31 MW | −103 to +174 MW |
| Scheduled play | −530 MW | −842 to −210 MW |
| Halftime extra | +282 MW | +91 to +469 MW |
| Post-match | −366 MW | −568 to −168 MW |

At full halftime overlap, scheduled play and halftime are simultaneously active. The
net forward adjustment is therefore approximately **−248 MW**. The positive halftime
coefficient means partial recovery relative to the rest of scheduled play; it does not
mean demand is forecast 282 MW above the event-blind level.

For a future major England tournament fixture:

1. refit the locked v3 baseline using only information available before the edition;
2. construct fractional schedule overlaps from the known kickoff;
3. add the versioned coefficients in
   `configs/match_aware_v3_forward_model.json`;
4. freeze the complete pipeline before observing the new tournament outcomes;
5. score whole fixtures and report event-window, scheduled-play and halftime results.

The model has not yet passed an untouched tournament test. Its coefficients are
forecast adjustments conditional on v3, not estimates of the causal electricity effect
of football.
