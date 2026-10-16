# Initial demand-data audit

Date: 16 October 2026  
Updated: 17 October 2026  
Status: Preliminary feasibility audit; dataset selection is not final.

## Purpose and scope

Assess whether Elexon's five-minute demand records could support a more detailed halftime analysis than the half-hourly core proposed in the project specification. This audit records data structure and documentation findings only. It contains no estimated football effects, forecast scores, or causal conclusions.

Evidence comes from the saved outputs in [the student's verification notebook](../notebooks/01_intial_data_verification.ipynb), [the retrieval function](../src/get_data_sample.py), and the official sources listed below. The notebook was inspected, not rerun, when this document was written.

## Retrieval specification

Provider: Elexon Insights; underlying rolling-demand information is attributed to NESO.

Endpoint: `https://data.elexon.co.uk/bmrs/api/v1/demand/outturn/summary`

| Parameter | Requested value |
|---|---|
| `from` | `2024-07-14T00:00:00Z` |
| `to` | `2024-07-15T00:00:00Z` |
| `format` | `json` |

The student's function uses `requests.get()` with query parameters and a 30-second timeout, calls `raise_for_status()`, and parses the response with `.json()`. The response is a list of dictionaries, converted into a pandas DataFrame.

This request covers a UTC day, not a midnight-to-midnight Europe/London day. Local-day boundaries and match times must be handled explicitly in subsequent work.

## Findings from the notebook

| Check | Saved evidence / finding | Scope or qualification |
|---|---|---|
| Shape | 289 rows, three columns | One requested date range only |
| Fields | `recordType`, `startTime`, `demand` | Returned schema for this sample |
| Missing values | `info()` reports 289 non-null entries in every column | No nulls in this sample; does not rule out undocumented sentinel values |
| Demand type | `int64` | Numeric representation confirmed; measurement meaning comes from documentation |
| Timestamp parsing | Converted from strings to `datetime64[us, UTC]` | UTC offsets are present in the returned timestamps |
| Sorting | Sorted DataFrame assigned back to `sample_data` | Sorting is retained |
| Earliest timestamp | `2024-07-14 00:00:00+00:00` | Matches requested lower boundary |
| Latest timestamp | `2024-07-15 00:00:00+00:00` | Matches requested upper boundary |
| Timestamp sequence | Loop compares each sorted row with an expected timestamp advanced by five minutes; no mismatches printed | Supports a complete, unique five-minute sequence across the observed range |
| Record types | `VD`: 289 records | No other record type observed in this sample |

There are 288 five-minute steps in 24 hours. Including both endpoint timestamps gives 289 records. Both boundaries were returned in this request; this is an observed API behaviour, not yet a verified general boundary contract. Selecting timestamps from July 14 00:00 UTC up to, but excluding, July 15 00:00 UTC would leave 288 records.

Row count alone does not prove completeness: missing and duplicate timestamps can offset each other. The notebook's sequence check provides the stronger evidence here. Its message about a possible duplicate is too narrow: a mismatch could also indicate a gap or ordering issue. The corresponding Markdown should describe a sequence check and should not claim that the count alone establishes completeness.

## Additional historical samples — 17 October 2026

The corrected notebook code and saved outputs were reviewed without rerunning the requests. Each sample uses midnight UTC on the requested date through midnight UTC the following day, with both endpoints returned.

| Requested date | Rows | First timestamp (UTC) | Last timestamp (UTC) | Null values | Duplicate timestamps | Five-minute sequence | Record type |
|---|---:|---|---|---|---|---|---|
| 10 July 2024 | 289 | 2024-07-10 00:00 | 2024-07-11 00:00 | None | None indicated by complete sequence | Complete | All `VD` |
| 1 July 2024 | 289 | 2024-07-01 00:00 | 2024-07-02 00:00 | None | None indicated by complete sequence | Complete | All `VD` |
| 1 July 2023 | 289 | 2023-07-01 00:00 | 2023-07-02 00:00 | None | None indicated by complete sequence | Complete | All `VD` |

All three samples have the same three-column schema, UTC-aware timestamps, and integer demand values. Non-null counts come from `info()`; timestamp uniqueness and spacing are supported by the expected-sequence loops rather than separate duplicate-count outputs. Returned boundaries match the requested boundaries.

An earlier notebook version accidentally substituted July 10's DataFrame into both July 1 checks. The variable references and final sequence loop were corrected, and the saved outputs now show the intended dates. The table above uses only the corrected results.

**Conclusion:** the three additional samples pass the initial structural checks, and historical records are retrievable for the tested day in 2023. This does not establish continuous coverage between these dates, availability for every required fixture, or the earliest available history. Dataset selection remains provisional.

## Timezone and daylight-saving exercise — 17 October 2026

The notebook converts the July sample to `Europe/London`, showing a +01:00 offset relative to UTC, and retains 289 rows. A conversion back to UTC and equality check has not yet been recorded.

The student also generated five-minute sequences between consecutive London calendar midnights, including the first midnight and excluding the next. These are synthetic expected timelines, not retrieved demand records.

| London calendar day | Elapsed hours between local midnights | London timestamp count | UTC timestamp count | London timestamps unique with timezone? | UTC timestamps unique? | UTC spacing verification saved |
|---|---:|---:|---:|---|---|---|
| 30 March 2024 — ordinary day | 24 | 288 | 288 | Yes | Yes | All 287 gaps are five minutes |
| 31 March 2024 — spring transition | 23 | 276 | 276 | Yes | Yes | All 275 gaps are five minutes |
| 27 October 2024 — autumn transition | 25 | 300 | 300 | Yes | Yes | All 299 gaps are five minutes |

Spring output skips local 01:00–01:55: 00:55+00:00 is followed by 02:00+01:00. Autumn output repeats the local 01:00–01:55 labels with different offsets: first +01:00, then +00:00. Those repeated clock labels represent different instants, so timezone-aware London timestamps remain unique as well as their UTC equivalents.

Timezone conversion preserves the instants and the number of observations. It does not turn a 23-hour or 25-hour London calendar day into a 24-hour UTC calendar day: the converted sequence still covers the original London day's boundaries. The updated saved outputs confirm five-minute spacing throughout all three UTC sequences using difference value counts. The July round-trip equality check has not been recorded; this is a minor remaining evidence item, not a failure of the conversion shown.

Session stopping point: the timezone learning exercise is complete. Next session, apply the expected timelines to actual API records on the spring and autumn transition dates, using London-midnight boundaries converted to UTC. Actual transition-day demand retrieval remains unverified, and the measurement-definition questions remain open.

Implication: expect 276, 288, or 300 five-minute observations for complete London calendar days under this boundary convention. A complete UTC calendar day has 288 such timestamps. Do not discard repeated autumn clock labels after removing timezone information, and do not confuse these synthetic checks with validation of actual API data on transition dates.

## Documentation findings

| Topic | Finding | Source / confidence |
|---|---|---|
| Demand definition | Rolling System Demand is an estimate of Transmission System Demand using operational meters, derived from the total of fuel-type generation categories. | Current Elexon rolling-demand page [S1] |
| Included components | Includes demand met from the transmission system, including power-station auxiliary demand, pumping demand, and interconnector exports. | [S1] |
| Aggregation caveat | The page states that negative fuel-type category values are capped at zero. | [S1]; relevant to interpreting the derived total |
| Units | MW for the five-minute series. | [S1]; legacy response definition also labels demand in MW [S3] |
| `VD` | Means **Demand Value**; it is not evidence that a row is marked “validated.” | Official interface record-type mapping [S2] |
| Measurement convention | Current rolling-demand page describes five-minute average MW values, while the older P220 specification describes five-minute-apart snapshots derived from instantaneous outturn. | Unresolved for the exact current endpoint; [S1] versus [S4] |
| Timestamp convention | Precise relationship between `startTime` and the measurement/averaging window has not been established. | Do not infer interval-start semantics solely from the field name |

The legacy API guide [S3] links rolling system demand to FUELINST and lists `VD` body records. It describes an older service, so its authentication, parameters, defaults, and response format must not be assumed to apply to the current Insights endpoint.

## Implications for the project

- Five-minute spacing and successful historical retrieval make this a promising candidate for investigating short halftime changes.
- Transmission System Demand is not identical to household consumption, National Demand (`ND`), or the forecast-performance table's `Demand Outturn`. These series must not be silently combined or assumed numerically identical.
- More frequent measurements can improve temporal detail but do not increase the number of independent match events. Learning a match-aware forecasting adjustment still requires verified earlier fixtures and suitable demand coverage.
- No decision to replace the half-hourly core has been made. The sample supports further feasibility checks, not a claim that the dataset is ready for event modelling.
- No formal event-effect analysis or tuning has been performed. The sample is from a planned event holdout date; further audit should focus on structure and availability rather than selecting models based on its demand pattern.

## Open checks before dataset selection

1. Resolve whether current endpoint values are snapshots or five-minute averages, and how timestamps relate to those measurements.
2. Verify retrieval and timestamp completeness for all seven Euro 2024 England matches, comparison periods, and candidate pre-tournament training dates.
3. Establish historical coverage, maximum request range, boundary behaviour, revisions, and any documented quality flags or sentinel values.
4. Check UTC-to-Europe/London conversion and daylight-saving transitions on appropriate dates; this summer sample does not test DST transitions.
5. Cross-check against a consistently defined half-hourly source and investigate differences without assuming target equivalence.
6. Verify official fixture metadata and earlier England match availability before deciding whether match-aware training is feasible.
7. Complete the notebook's written interpretation and, for clearer reporting, add explicit missing-value counts, duplicate counts, and consecutive-spacing counts.

## Source log

Official documentation consulted during the initial research on 16 October 2026:

- **S1 — Elexon, Rolling System Demand.** Current definition, included components, units, and stated averaging convention: https://bmrs.elexon.co.uk/rolling-system-demand
- **S2 — Elexon Digital BSC, NETA Interface Definition and Design Document Part 1.** Record-type mapping: search for “Demand Value” to locate `VD`: https://bscdocs.elexon.co.uk/bsc-module/interface-definition-documents/neta-interface-definition-and-design-document-part-1-interfaces-with-bsc-parties-and-their-agents/v-57-0/id-67b34bd747c7f13fbb2970f5
- **S3 — Elexon, BMRS API and Data Push User Guide, version 2.0 (2018), section 5.2.12, printed page 75.** Legacy rolling-demand service and response fields: https://assets.elexon.co.uk/wp-content/uploads/2018/09/28160411/BMRS-API-Data-Push-User-Guide.pdf
- **S4 — Elexon, P220 Requirements Specification, version 1.0 (2007), section 3.3.2, printed page 14.** Historical specification describing snapshot demand values: https://assets.elexon.co.uk/wp-content/uploads/sites/11/2012/02/28170955/p220as10.pdf
- **S5 — Elexon, current System Demand Summary endpoint documentation.** Exact endpoint reference; insufficient on its own to resolve all measurement definitions: https://bmrs.elexon.co.uk/api-documentation/endpoint/demand/outturn/summary
- **S6 — NESO, Historic Demand Data.** Candidate longer historical archive for coverage and cross-checking; not audited in the notebook: https://www.neso.energy/data-portal/historic-demand-data
- **S7 — Elexon, Insights Data Platform guidance.** Public historical API access and interface guidance: https://github.com/elexon-data/insights-docs/blob/main/docs/insights_data_platform.md

This audit remains preliminary and must be updated and frozen before formal event-effect modelling.
