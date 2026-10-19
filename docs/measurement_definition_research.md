# Measurement-definition research

Date: 19 October 2026

Status update: the student subsequently authorized complete dataset finalization. The [finalized half-hourly core](finalized_dataset.md) supersedes the proposed additional FUELINST inspection below. Five-minute interpretation remains an optional extension; it no longer blocks the project.

## Findings

The [current official OpenAPI specification](https://data.elexon.co.uk/swagger/v1/swagger.json) establishes:

- `/demand/outturn/summary` is a downsampled visualisation endpoint; full access belongs under `/datasets`.
- `/datasets/FUELINST` describes average MW over five minutes despite its “instantaneous” title.
- Its response wraps records in `data`, with fuel type, generation, publication time, start time, and settlement fields.
- `startTime` has no explanatory description in either relevant response schema. The exact interval alignment remains unresolved.
- FUELINST supports settlement-date or publication-time filters; these cannot be combined. Do not reuse the summary endpoint's `from`/`to` parameters.

The [current rolling-demand page](https://bmrs.elexon.co.uk/rolling-system-demand) also describes five-minute average MW measurements. Together, current descriptions support averaging rather than treating an older snapshot specification as authoritative for today's feed. The timestamp convention and the summary's transformation still require clarification.

## Decision and next action

Keep the completed structural audits: they describe the summary records actually returned. They do not demonstrate raw-source completeness or averaging behaviour. Do not start a long baseline download through that endpoint yet.

Inspect one pre-tournament day from FUELINST, retaining all fuel types and publication metadata. Establish its structure and historical availability before constructing any aggregate demand target. Do not silently sum signed interconnector rows or assume equivalence to the summary or NESO National Demand.

If reconstruction and timing cannot be verified within a bounded check, use the specification's half-hourly core and keep five-minute results supplementary. Do not claim instantaneous pickup reconstruction or precise whistle-aligned effects without sufficient measurement evidence.

No additional demand sample was downloaded during this research; only the official API specification was downloaded and inspected. No provider contact was made.
