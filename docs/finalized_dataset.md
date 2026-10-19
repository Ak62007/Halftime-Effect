# Finalized analysis dataset — version 1

Decision frozen: 19 October 2026. Data acquisition and preprocessing are complete for the core project. No event-effect estimates, model fitting, forecast scores, or tournament plots were produced during finalization.

## Decision

Use **NESO Day Ahead Half Hourly Demand Forecast Performance, `Demand_Outturn`**, as the single primary target, named `demand_mw`. This follows the original specification's recommended source. Retain five-minute Elexon work as a feasibility exercise; it is not the core target. The uncertain summary transformation and timestamp interpretation do not need to delay the project further.

The [NESO source](https://www.neso.energy/data-portal/day-ahead-half-hourly-demand-forecast-performance/day_ahead_half_hourly_demand_forecast_performance) supplies outturn, operational forecasts, and forecast issue clocks. Its documented clock convention follows London time even where strings end in `Z`. We use settlement keys to construct a trustworthy UTC timeline. We use uncorrected outturn, not the TRIAD-corrected column.

## Files ready to use

| File under `data/processed/` | Purpose |
|---|---|
| `demand_development.csv` | Start here: 24,814 rows through 31 May 2024; contains train and validation only |
| `demand_halfhour.csv` | Complete primary table: 27,742 rows, 1 January 2023–31 July 2024, by London settlement date |
| `fixtures_all.csv` | 21 scheduled fixtures: 12 earlier fixtures, two June warm-ups, seven Euro holdouts, with primary source URLs |
| `final_fixture_coverage.csv` | Half-hour coverage for every fixture day |
| `daily_coverage.csv` | Counts and missing-demand check for every date |
| `weather_hourly_retrospective.csv` | Separate hourly temperature measurements |
| `bank_holidays.csv` | Official England/Wales and Scotland bank holiday dates and names |
| `final_data_checks.json` | Machine-readable validation results |
| `data_manifest.json` | Input URLs, snapshot hashes, sizes, build time, output hashes, and configuration |

Paths are relative to the repository root. Raw snapshots and processed outputs are ignored by Git under the existing repository rules; reproduce them with the script or retain a local backup. Do not refresh raw snapshots midway through analysis without explicitly creating a new data version.

## Evidence that the core is ready

| Check | Result |
|---|---|
| Calendar coverage | All 578 London dates present |
| UTC sequence | Complete, unique 30-minute grid; zero missing intervals |
| Primary demand | Numeric, positive, zero nulls |
| Forecast and historic cross-check fields | Numeric, positive, zero nulls |
| Daily counts | 575 ordinary days with 48 rows; two spring days with 46; one autumn day with 50 |
| Source timestamp alignment | Every source clock label equals its settlement-derived interval end |
| Operator issue timing | All forecasts precede their target interval start and are available by the fixed comparison cutoff |
| Fixture coverage | All 21 days complete, including all seven Euro matches |
| Temperature alignment | Zero missing values after documented interpolation |
| Required automated checks | Six tests pass: DST, UTC/end labels, forecast cutoff, split isolation, and target separation |

Counts are from the downloaded snapshots, not assumptions about provider-wide completeness. Full fixture day coverage is not a claim to have verified actual whistles.

## Time conventions and dictionary

| Field | Meaning and usage |
|---|---|
| `timestamp_utc` | **Start** of the half-hour observation interval; primary ordering/join key |
| `interval_end_utc` | End of that same half hour; do not mistake it for another observation |
| `timestamp_london` | Same start instant on London's clock, with seasonal offset |
| `settlement_date`, `settlement_period` | London operating date and ordinal half-hour period; SP1 is local 00:00–00:30 |
| `demand_mw` | Primary outturn target; half-hour demand level in MW, not MWh or an instantaneous pickup |
| `neso_day_ahead_forecast_mw` | Operator forecast paired with that source's outturn |
| `forecast_issue_utc` | Source issue clock interpreted in London time, then converted to UTC |
| `forecast_cutoff_utc` | Fixed experiment issue time: 10:00 London on the preceding calendar day |
| `neso_available_at_cutoff` | True for all rows; verifies operator benchmark availability |
| `Datetime`, `Publish_Datetime` | Original source strings kept for traceability; do not parse their `Z` as authoritative UTC |
| `historic_nd_mw`, `historic_tsd_mw` | Separate cross-check series; never splice into `demand_mw` |
| `TRIAD_Avoidance_Estimate` | Source retrospective adjustment; not an ex-ante predictor |
| `hour_of_week`, `half_hour_of_week` | London calendar positions, respectively 0–167 and 0–335; autumn may repeat positions |
| `is_bank_holiday_*` | Separate regional calendar indicators; `any_gb` is their union |
| `data_split` | Frozen chronological role below |
| `baseline_fit_eligible` | Train split excluding all earlier England fixture days, conservatively removing match influence from the initial event-blind baseline |
| `is_england_match_day`, `match_id`, `opponent` | Known inventory labels; match ID labels the whole day, not a halftime interval |
| `scheduled_kickoff_utc`, `match_stage`, `event_role` | Fixture metadata; no exact whistles, actual duration, or outcome variables included |
| `temperature_*_c_retrospective` | Three city-specific temperature controls |
| `temperature_proxy_c_retrospective` | Equal-weight mean of the three city controls; a regional proxy, not a population-weighted GB temperature |
| `weather_ex_ante_eligible` | Always false: do not use realized weather in operational forecast claims |

The [historic-demand documentation](https://www.neso.energy/data-portal/historic-demand-data/historic_demand_data_2024) defines National Demand separately from Transmission System Demand and identifies SP1 as 00:00–00:30. ND excludes station load, pumping and interconnector exports; embedded generation can suppress observed network demand. The target is not a direct total of household electricity consumption.

**A concrete example:** SP1 for 1 June 2024 covers London 00:00–00:30, corresponding to UTC 23:00–23:30 on 31 May. The source's end label reads `2024-06-01T00:30:00Z`, although it is a London clock label. The processed `timestamp_utc` correctly reads `2024-05-31 23:00:00+00:00`.

## Frozen chronological split

| Split | London dates | Rows | Role |
|---|---|---:|---|
| Train | 1 January 2023–29 February 2024 | 20,400 | Initial development; 19,922 rows eligible for the conservative no-match fit |
| Validation | 1 March–31 May 2024 | 4,414 | Compare/tune limited model choices chronologically |
| Bridge | 1–15 June 2024 | 720 | Not tuning data; includes two warm-ups, flagged for exclusion from no-match comparisons |
| Event holdout | 16 June–15 July 2024 | 1,440 | Tournament-era evaluation, including seven England matches and non-match intervals |
| Post-event context | 16–31 July 2024 | 768 | Optional descriptive context; not a second tuning set |

Tune on validation, then lock choices before opening tournament outcomes. A final refit on pre-June data may be planned after validation; keep the held-out evaluation unchanged and exclude historical fixture influence when fitting the no-match model. There are ten earlier training-event candidates and two validation friendlies, not 12 independent training events. Match-aware forecasting remains exploratory given the small and heterogeneous event sample. Do not use the two June warm-ups for tuning in version 1.

## Controls and limitations

Temperature comes from [Open-Meteo historical ERA5 reanalysis](https://open-meteo.com/en/docs/historical-weather-api), explicitly requested in UTC at London (51.5074, -0.1278), Manchester (53.4808, -2.2426), and Birmingham (52.4862, -1.8904). Hourly values are time-interpolated to interval starts; city columns are averaged equally. These are realized retrospective controls, not weather forecasts. Use them for explanatory counterfactuals only. Operational model comparisons should initially use calendar and past demand information, with lags restricted to what existed at the issue cutoff.

Regional bank holidays come from [GOV.UK](https://www.gov.uk/bank-holidays) and its [JSON feed](https://www.gov.uk/bank-holidays.json). School holidays, special TV programmes, and all other sporting events have not been exhaustively labelled. A non-England-match day is not automatically an uncontaminated control day.

The independent historic ND series differs from the selected target on most rows: mean absolute difference 58.97 MW, maximum 1,575 MW across this scope. The cause of all revisions/definition differences is not established. Treat ND as a separately labelled robustness target and score NESO against its paired primary outturn. Do not present the disagreement as a model error.

Half-hour observations cannot resolve a brief peak or reconstruct NESO's reported rapid pickup. Our question is now explicitly about **half-hourly deviations around approximate halftime and other match windows**. Decide event-window definitions and sensitivity ranges before viewing tournament demand. Exact halftime/full-time timing is unverified, so scheduled proxies must be labelled as proxies. Seven matches limit power and causal interpretation regardless of the number of rows.

## Rebuild and verify

Using existing raw snapshots:

```bash
.venv/bin/python src/finalize_data.py
.venv/bin/python -m unittest discover -s tests -v
```

For a fresh checkout, use `src/finalize_data.py --download` to download missing inputs. `--refresh` replaces inputs and deliberately creates a new snapshot. The script fails rather than silently filling missing demand or accepting broken timing, coverage, or forecast availability.

## Start the analysis

Create `notebooks/03_demand_eda.ipynb` and load only `demand_development.csv`. Parse `timestamp_utc` with `utc=True`, then derive London time with `tz_convert('Europe/London')`; CSV text can contain mixed offsets. Restrict the first EDA to `data_split == 'train'`, with `baseline_fit_eligible` for ordinary-demand profiles. Plot daily mean demand and average London half-hour profiles by weekday. Explain patterns before moving to tests or models.

Data verification is now closed for the core version. The student owns the statistical analysis and interpretation; further data work is needed only if a specific analytical failure warrants it.
