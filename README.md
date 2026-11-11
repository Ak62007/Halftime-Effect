# The Halftime Effect

This project studies whether scheduled England football matches add useful information
to a half-hourly Great Britain electricity-demand forecast. It first develops an
event-blind day-ahead baseline, then evaluates whether a schedule-aware correction adds
value around England matches.

The schedule-aware extension of the third-generation baseline is on the
`match-aware-v3` branch. Start with the [match-aware v3 report](docs/match_aware_v3/README.md).
The [event-blind v3 report](docs/event_blind_v3/README.md) links the exogenous-data
audit, development experiments and untouched 2026 final test. The
[event-blind v2 report](docs/event_blind_v2/README.md) and earlier
[match-aware forecasting report](docs/match_aware/README.md) document the preceding
experiments.

The locked event-blind v3 model achieves 982 MW MAE on untouched January–March 2026,
39.0% better than the refit v2 specification and 60.1% better than weekly seasonal
naive. Its errors still show serial dependence and changing conditional variance, and
its locked intervals under-cover. The earlier tournament correction improved aggregate EURO 2024 MAE by
6.8%, but did not establish a robust halftime-aware forecast or a causal effect.

Using v3 as the tournament baseline lowers retrospective EURO 2024 event-window MAE to
761 MW before any schedule correction. The locked schedule-shape layer improves the
scheduled-play and halftime windows, but slightly worsens aggregate event-window MAE to
772 MW. A 19-match forward refit is therefore an unconfirmed deployment model, not a
validated performance claim.

Run the complete integrity suite with:

```bash
.venv/bin/python -m unittest discover -s tests -v
```

The v3 reports are indexed in [docs/event_blind_v3/README.md](docs/event_blind_v3/README.md);
the v2 reproduction order is documented in
[docs/event_blind_v2/README.md](docs/event_blind_v2/README.md#reproduction-order), and the
match-aware pipeline remains documented in
[docs/match_aware/README.md](docs/match_aware/README.md#reproduction-order).
