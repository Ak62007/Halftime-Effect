# Event-blind v3 exogenous-data audit

## Archived weather forecasts

Open-Meteo's Previous Runs API supplies JMA forecasts for London, Manchester and
Birmingham. The acquisition contains 43,872 padded hourly timestamps per location from
31 March 2021 through 1 April 2026, with no missing day-1 or day-2 temperature values.

V3 initially uses `temperature_2m_previous_day2`, a forecast fixed 48 hours before each
valid time. It is not the freshest possible forecast, but every value necessarily
predates the 14–38-hour demand-forecast horizon. Hourly values are interpolated to the
half-hour grid; this interpolation combines two already-issued forecast values and does
not use realized weather.

## Embedded wind and solar forecasts

NESO's annual archives contain hourly vintages of half-hourly embedded wind and solar
forecasts. The 2021 archive alone has 5,465,982 rows. Acquisition therefore requests
only vintages produced from 05:00 through 10:59 UTC on the preceding date, then selects
the latest `Forecast_Datetime` no later than the row's London-time cutoff.

Across the complete experiment:

- no selected embedded forecast is published after cutoff;
- ten target dates have no eligible archived vintage, totalling 480 intervals;
- those rows use the same interval's forecast from exactly one week earlier;
- an explicit imputation indicator is retained;
- no future row is used as a fallback.

Missing-vintage dates are 2 and 16 December 2022; 25 July and 27 September 2024;
10–13 May and 21 November 2025; and 15 February 2026.

## Demand and calendar integrity

The final v3 table has 87,648 rows across 1,826 London dates. It preserves five 46-period
spring clock-change dates, 1,816 ordinary 48-period dates and five 50-period autumn
dates. The two previously audited defective source dates—31 October 2021 and 30 October
2022—remain explicit ineligible grid rows.

Official regional holiday names are retained. Derived features include holiday-adjacent
days, Christmas Eve, New Year's Eve, 2 January, working day and holiday-specific
intraday shapes.

NESO's demand benchmark is unavailable by 10:00 on 1 and 8 February 2026 because its
recorded publication time is 10:33. Those target rows remain valid for the research
model, while the NESO benchmark will be scored only where it was actually available.

## Audit result

- Weather missing values: 0.
- Remaining embedded-feature missing values: 0.
- Selected embedded vintages after cutoff: 0.
- Final-test rows: 4,318, still marked unopened.
- Previously opened January–March 2025 rows: 4,318, never used as a validation fold.
