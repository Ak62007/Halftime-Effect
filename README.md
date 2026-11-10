# The Halftime Effect

This project studies whether scheduled England football matches add useful information
to a half-hourly Great Britain electricity-demand forecast. The current implementation
builds an event-blind day-ahead baseline, learns a small schedule-aware tournament
correction, and evaluates it once on the seven England matches at EURO 2024.

The work is on the `match-aware-forecast` branch. Start with the
[match-aware forecasting report](docs/match_aware/README.md), which links every stage,
result table and high-resolution figure.

Headline result: the locked tournament correction improved aggregate pregame-to-post-
match MAE by 6.8% on EURO 2024, but improved only 3 of 7 fixtures and made the scheduled
match and halftime-proxy forecasts worse. The project therefore finds limited schedule
signal, not a robust halftime-aware forecast and not a causal effect.

Run the complete integrity suite with:

```bash
.venv/bin/python -m unittest discover -s tests -v
```

The expanded-data and model pipeline is documented with exact commands in
[docs/match_aware/README.md](docs/match_aware/README.md#reproduction-order).
