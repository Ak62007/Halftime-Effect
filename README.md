# The Halftime Effect

This project studies whether scheduled England football matches add useful information
to a half-hourly Great Britain electricity-demand forecast. It first develops an
event-blind day-ahead baseline, then evaluates whether a schedule-aware correction adds
value around England matches.

The second-generation event-blind experiment is on the `event-blind-v2` branch. Start
with the [event-blind v2 report](docs/event_blind_v2/README.md), which links the
pre-specified plan, development experiments and untouched final test. The earlier
[match-aware forecasting report](docs/match_aware/README.md) documents the EURO 2024
experiment.

The locked event-blind v2 model achieves 1,622 MW MAE on untouched January–March 2025:
32.4% better than v1 and 47.7% better than weekly seasonal naive. Its errors still show
serial dependence and changing conditional variance, and NESO remains much more accurate
at 781 MW MAE. The earlier tournament correction improved aggregate EURO 2024 MAE by
6.8%, but did not establish a robust halftime-aware forecast or a causal effect.

Run the complete integrity suite with:

```bash
.venv/bin/python -m unittest discover -s tests -v
```

The v2 reproduction order is documented in
[docs/event_blind_v2/README.md](docs/event_blind_v2/README.md#reproduction-order); the
match-aware pipeline remains documented in
[docs/match_aware/README.md](docs/match_aware/README.md#reproduction-order).
