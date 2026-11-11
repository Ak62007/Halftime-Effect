# Stage 0 — Protocol and leakage boundary

## Objective

Use the exact locked event-blind v3 architecture as the baseline for a forecast that
knows an England tournament fixture's date and scheduled kickoff. The schedule layer
may add corrections during pregame, scheduled play, the halftime proxy and post-match.

## Historical forecast construction

The old match-aware experiment used a much weaker calendar-plus-weekly-lag baseline.
Replacing its stored predictions with v3 predictions would be invalid if v3 were fitted
using demand observed after a historical match. Instead, v3 is refitted once per
tournament edition:

| Edition | Parameter-fitting endpoint | England fixtures | Status |
|---|---:|---:|---|
| UEFA EURO 2020 | 11 June 2021 | 7 | historical selection |
| FIFA World Cup 2022 | 19 November 2022 | 5 | historical selection |
| UEFA EURO 2024 | 14 June 2024 | 7 | previously opened diagnostic only |

The endpoint is two local dates before the first fixture. At each day-ahead cutoff,
recent residual summaries may use demand already observed by 10:00 on the preceding
day, exactly as in v3.

EURO 2020 has only 2,112 eligible pre-edition training intervals because the archived
v3 source starts in April 2021. The locked unpenalized direct Ridge design is
rank-deficient in this short history, so it is solved with minimum-norm least squares.
This changes numerical implementation, not the alpha-zero specification.

The known 30 October 2022 source defect also propagates into three- and four-week lag
features during the World Cup forecast history. Missing derived lags are replaced only
with the mean of other fixed, already-observed lags in the same row. Repaired rows help
maintain a continuous forecast/residual history but are excluded from parameter fitting.
No future demand is used.

## Validation unit

There are only two historical editions, so random half-hour or random-match splitting
would be misleading. Candidate schedule corrections are fitted on one complete edition
and evaluated on the other, then the direction is reversed. A correction must reduce
pooled MAE **and** improve each held-out edition separately.

The primary window is the union of:

- 120 minutes before scheduled kickoff;
- scheduled minutes 0–105;
- 60 minutes after the scheduled end.

The minute 45–75 halftime feature is an additional term inside scheduled play. It is a
schedule proxy, not an observed whistle-to-whistle interval.
