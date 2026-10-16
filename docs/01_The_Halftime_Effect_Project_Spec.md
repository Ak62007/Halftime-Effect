---
title: "THE HALFTIME EFFECT"
subtitle: "A guided time-series and causal-inference research project"
date: "Project specification | 14 October 2026"
---

# The Halftime Effect

**Can football matches measurably change Britain's electricity demand?**  
*A time-series, event-study, and forecasting investigation of synchronized human behavior*

**Status:** Approved project concept; not yet implemented  
**Track:** Data Science / Applied Econometrics  
**Duration:** 14 core working days + up to 4 optional polish days  
**Time budget:** Aim for 2–3 focused hours per working day; adjust only after data audit  
**Compute:** Ordinary laptop CPU; no GPU or cloud required  
**Audience:** Student, university time-series instructor, and a separate AI project mentor  
**Companion career experiment:** Neural Network Robustness under Distribution Shift

> **Elevator pitch.** During England's UEFA Euro 2024 semifinal and final, the British electricity-grid operator reported unusually large increases in demand at halftime. Can we detect related anomalies in publicly available *half-hourly* demand data, quantify them against credible counterfactuals, and determine whether scheduled-match information improves a statistical forecast?

## 1. Why this project exists

**Academic goal.** Apply advanced time-series ideas from five course modules to an unusual real-world stochastic process, with a defensible explanation for each method selected or rejected. The focus is analysis, not merely fitting a list of models.

**Career goal.** Experience the day-to-day work of a Data Scientist: acquiring imperfect data, formulating testable questions, reasoning about confounding and counterfactuals, building statistical models, checking assumptions, and communicating uncertainty.

**What makes this distinctive.** The signal of interest is not just electricity demand; it is the aggregate behavioral response of millions of viewers at synchronized moments of a football match. This makes the question compelling while still inviting serious statistical scrutiny.

**Verified motivating fact.** Britain's National Energy System Operator (NESO) reports a **1 GW** halftime demand pickup during the England–Netherlands Euro 2024 semifinal and a **1.3 GW** pickup during the England–Spain final. Those are operator-reported rapid pickups, **not numbers already recovered from the public half-hour dataset** (Source S1).

## 2. Exact research questions and hypotheses

### Primary question

**RQ1.** Do England's Euro 2024 matches coincide with electricity-demand deviations that are unusual after accounting for normal calendar, seasonal, and weather-driven patterns?

### Secondary questions

- **RQ2 — Event dynamics:** Do estimated anomalies differ around kickoff, approximate halftime, and full-time/post-match windows? Are patterns heterogeneous between group and knockout games?
- **RQ3 — Explanatory/counterfactual:** How large is the estimated *half-hourly* deviation from a no-match baseline, and how sensitive is it to baseline choice, weather adjustment, and placebo dates?
- **RQ4 — Forecasting:** Does adding *information available before the forecast is issued* about scheduled England matches reduce out-of-sample forecast error, especially within match windows?
- **RQ5 — Course methods:** What stationarity, seasonality, spectral, structural-stability, and conditional-variance behavior does the electricity-demand process show?

### Pre-registered hypotheses (not findings)

- **H1:** Absolute baseline-model forecast residuals are systematically larger during pre-specified match windows than during comparable non-match windows.
- **H2:** Halftime and post-match windows have different demand profiles from typical matched Sundays/evenings after adjustment, though the *sign* of any effect is left open.
- **H3:** Match-calendar features can improve forecast accuracy in some held-out match windows, but may offer negligible improvement over all half-hour observations.
- **H4:** The demand series contains strong daily/weekly periodicity; a seasonal baseline should be hard to beat.

**Non-goals:** Estimate national TV viewership from demand; infer individual kettle behavior; claim to reconstruct NESO's instantaneous 1.3 GW pickup; prove a causal treatment effect without defending identification assumptions.

## 3. Data sources and acquisition specification

| Source | Required fields / use | Coverage and notes |
|---|---|---|
| NESO **Day Ahead Half Hourly Demand Forecast Performance** (S2) | `Date`, `Datetime`, `Settlement Period`, `Demand Forecast`, `Demand Outturn`, `Publish Datetime`; units MW | First-choice consistent half-hourly demand and operator-forecast comparison; history from April 2021; validate definitions and missing records before use. |
| NESO **Historic Demand Data 2023 and 2024** (S3) | `SETTLEMENT_DATE`, `SETTLEMENT_PERIOD`, `ND`; optional `TSD` | Independent cross-check and context. `ND` and `TSD` have different definitions: do **not** silently combine them. |
| UEFA Euro 2024 match records (S4) | Match date, opponents, announced kickoff, actual chronology, extra time/penalties, stage | Manually create a small, auditable match metadata file with a primary URL for each fixture. |
| Open-Meteo historical weather API (S5) | Historical hourly `temperature_2m`, optionally humidity/wind | Use a modest, clearly labeled regional proxy (e.g., London plus Manchester/Birmingham) for national weather; reanalysis observations are *not* pre-issue weather forecasts. |
| Optional early England fixtures | 2023 qualifiers / pre-Euro 2024 friendlies | Needed **only if** fitting an event-effect coefficient using events observed *before* Euro 2024. Verify times and avoid inventing records. |

### Fixed initial scope

- **Geography:** Great Britain electricity system, not the UK as a whole.
- **Baseline window:** 1 January 2023 – 31 May 2024 for model development, subject to coverage checks.
- **Validation:** Reserve a chronological portion of pre-tournament data, e.g., March–May 2024, before comparing on tournament events. The final split must be documented prior to inspecting Euro-event outcomes.
- **Primary event evaluation:** England's **seven** Euro 2024 matches: 16, 20, 25, 30 June; 6, 10, 14 July 2024 (UEFA source S4). Reserve tournament matches as the *event* holdout for the key claim.
- **Optional generic forecast check:** Later summer/autumn 2024 non-event dates for overall stability; these are separate from the event holdout.
- **Frequency:** Half-hourly (48 intervals on ordinary days, **46 or 50 during UK DST transitions**). Work in UTC internally, preserve local `Europe/London` interpretation for events, and explicitly verify whether settlement periods map to clock-time intervals correctly.
- **Target:** Select **one** consistently defined MW outturn series before analysis. Recommended primary: `Demand Outturn` from the forecast-performance file; test it against `ND` rather than assuming numerical identity.

### Data dictionary (minimum)

`timestamp_utc`, `timestamp_london`, `settlement_date`, `settlement_period`, `demand_mw`, `neso_day_ahead_forecast_mw`, `forecast_issue_utc`, `temperature_proxy_c`, `hour_of_week`, `is_uk_holiday`, `match_id`, `match_stage`, `scheduled_kickoff_utc`, `in_match_window`, `in_halftime_proxy_window`, `in_postmatch_window`.

Use separate columns for **pre-announced** information and **ex-post** information (e.g., actual extra time, goals, exact whistle times). Ex-post variables may enter retrospective explanation, **never** a day-ahead forecast unless known at issue time.

### Mandatory data-quality checks

1. Check duplicate/missing timestamps and settlement periods; document daylight-saving clock changes.
2. Confirm MW units and demand definitions; never equate instantaneous pickup with a 30-minute observation.
3. Check if `Publish Datetime` precedes its target interval for each operational forecast compared.
4. Verify match times with UEFA or official match reports. Settle whether each half-hour interval is labeled by its **start** or **end**.
5. Check weather timestamp alignment and missing values. Avoid using ex-post reanalysis in a claim of genuinely operational day-ahead forecasts; call weather-adjusted retrospective fits **explanatory baselines**, or use archived issued forecasts for true ex-ante testing.
6. Freeze a short `data_audit.md` before formal event-effect modeling.

**Day-2 feasibility gate:** If historic demand cannot be aligned reliably, simplify to a NESO-forecast-residual event study using the single forecast-performance table. If a high-frequency archive cannot be verified, **do not search indefinitely**; half-hourly analysis is the approved core.

## 4. Study design: three analysis layers

### Layer A — Understand ordinary electricity demand

Start by characterizing a non-event demand process. Use a fixed pre-tournament sample and create:

- Daily and weekly demand profiles, calendar heatmap, distribution and outliers.
- Seasonal decompositions; note **two seasonalities**: 48 half-hours/day and 336 half-hours/week.
- ACF/PACF and periodogram to identify dominant cycles.
- ADF and Phillips–Perron tests on appropriate series/transformations, with explicit deterministic terms and test caveats; tests are not a substitute for visualization.
- Seasonal naïve baseline, e.g., `demand[t-336]`, and at most **one or two** appropriately sized statistical models: seasonal regression with Fourier terms + ARMA errors, SARIMAX, or a similarly interpretable approach.

**Expected output:** a baseline that captures normal consumption without football labels.

### Layer B — Football event study and estimated anomalies

Define event windows **before comparing the outcomes**:

- **Pregame reference:** e.g., 60–120 minutes before the scheduled start.
- **During-match window:** scheduled kickoff through normal-time end (updated retrospectively for extra time in *descriptive* plots).
- **Approximate halftime window:** specify in relation to verified kickoff, with a sensitivity range because actual halftime timing varies and 30-minute data smear the pickup.
- **Post-match window:** approximately 0–60 minutes after final whistle for descriptive analysis.

First report **unadjusted** profiles; then report model-based anomalies:

$$a_t = y_t - \widehat{y}^{(0)}_t,$$

where $\widehat{y}^{(0)}_t$ is the *estimated demand had the match-related shock not occurred* under stated assumptions. The estimate is model-dependent, not an observed fact.

Use a pre-specified baseline fit without tournament match windows. Candidate explanatory model:

$$y_t=\alpha+f(\text{hour-of-week},\text{season})+g(\text{weather})+\beta_1 M_t+\beta_2 H_t+u_t,$$

where $M_t$ denotes match activity and $H_t$ a halftime proxy. Fit autocorrelation-aware errors or use inference robust to temporal dependence. A simpler no-match model plus a residual event study is an equally valid **core** analysis and may have more transparent interpretation.

**Comparisons:** matched same-weekday/same-time periods nearby in the calendar, plus placebo windows (same calendar/time on non-match days), alternative weather controls, and sensitivity to event-window definitions. Do not treat every half-hour as an independent experimental replicate: there are only seven core matches.

**Uncertainty:** report per-match effect intervals or placebo distributions if appropriate; be explicit that seven matches limit power and generalization. Daily/block-level resampling can be preferable to naïve independent-row bootstrapping.

**Causal claim discipline:** the intervention was not randomized. A credible design controls predictable cycles and weather, but viewers, concurrent TV, unusual events, and model misspecification remain threats. Describe the result as **estimated excess demand associated with match windows** unless identification assumptions are compellingly supported.

### Layer C — Forecast comparison

Evaluate a specific **day-ahead** forecasting scenario, with issue time and horizon fixed.

- **Baseline 0:** seasonal naïve weekly forecast.
- **Model 1:** event-blind calendar + seasonal statistical model.
- **Model 2 (conditional):** same model plus pre-scheduled match flags. Any match coefficient must be trained using **pre-tournament** historical matches (if verified and sufficient); otherwise position Model 2 as an *exploratory scenario* rather than a rigorously learned causal forecasting improvement.
- **External comparison:** NESO's published day-ahead forecast, matched to the same target interval and checked for publication time. Do not assume NESO is event-blind.

Metrics: overall and event-window **MAE**, **RMSE**, bias, and per-match error. Present confidence/sensitivity where justified. Compare identical evaluation timestamps and never tune on the seven tournament event outcomes before final reporting.

**Precedence if time is limited:** complete a credible event-blind forecast and analysis of NESO residuals **before** attempting match-aware training.

## 5. Relation to the professor's five modules

| Module | Required, conditional, or not forced? | Project implementation |
|---|---|---|
| M1: ARIMA, unit roots, SARIMA, DF/ADF/PP, seasonal unit roots | **Required:** stationarity, seasonal model, diagnostics. **Optional:** seasonal unit-root/HEGY if justified and supported in software | Examine raw and seasonally adjusted levels; explain deterministic seasonality versus unit root; fit limited seasonal benchmark. |
| M2: cointegration, ECM, VAR, Johansen, VECM, Granger | **Conditional extension** | Only if defensible comparable multivariate stochastic processes are available; do **not** assert cointegration between demand and arbitrary stationary weather features. A short VAR/Granger exercise can be included with caveats if justified. |
| M3: Quandt–Andrews, Bai–Perron, structural stability | **Required conceptual distinction; optional formal tests** | Differentiate a short-lived match intervention from a persistent parameter break; explore structural stability in a long baseline sample only if scope allows. |
| M4: ARCH/GARCH variants | **Diagnostics core, fitting conditional** | Check residual conditional heteroskedasticity; fit GARCH only if meaningful and avoid gratuitous EGARCH/GJR comparisons. |
| M5: spectral density, AR/MA/ARMA spectra, periodogram | **Required** | Periodogram plus interpretation of 1/day and 1/week peaks; connect to seasonal covariance structure. |

The assignment should be presented as a full time-series **workflow**, not as a promise to run every specialized test. If the instructor explicitly requires numerical output for every method, negotiate an appendix or revise scope knowingly.

## 6. Milestones: 14 core days + 4 optional days

| Day | Focus | Concrete exit artifact / acceptance gate |
|---|---|---|
| 1 | Understand NESO demand and TV pickup; write causal and forecasting questions | 1-page research protocol + source log |
| 2 | Download/merge datasets; verify units, local time and DST | `data_audit.md`, checked schema, fixture inventory; pass feasibility gate |
| 3 | EDA: seasonality, distributions, missingness | 4–6 labeled, source-backed figures |
| 4 | Stationarity and spectral analysis | ADF/PP interpretations, ACF/PACF, periodogram |
| 5 | Seasonal naïve forecast + holdout definition | Leakage-checked baseline metric table |
| 6 | Fit one seasonal statistical model | Model spec and residual diagnostics |
| 7 | Write a midpoint methodological note | Baseline results and model limitations documented |
| 8 | Build match/event windows; view descriptive curves | Event-aligned plots for seven games; no causal claims yet |
| 9 | Construct no-match counterfactual and residual anomalies | Per-match anomaly table in MW |
| 10 | Placebo tests and alternate matching/window specifications | Robustness/sensitivity table |
| 11 | Interpret causal assumptions, confounding, uncertainty | Short DAG + explicit identification paragraph |
| 12 | Compare time-respecting held-out forecasts / NESO errors | Whole-period and match-window forecast scores |
| 13 | Run justified volatility/structural-stability extension, or improve core diagnostics | One high-quality extension OR validated limitations |
| 14 | Consolidate evidence; draft report, figures, slides | Reproducible repository and 1st complete research presentation |
| 15–18 | **Optional:** another fixture period; deeper diagnostics; editing and rehearsal | Final presentation and polished write-up |

**Stop rule:** Protect the 14-day core. If implementation slips, drop advanced module extensions and extra matches first. Never drop timestamp validation, the counterfactual assumptions section, or held-out evaluation.

## 7. Minimum figures, tables, and final deliverables

**Required figures:** (1) historic half-hourly demand with annotated seasonality; (2) hour-of-week / daily profile; (3) ACF/PACF or seasonal decomposition; (4) spectral periodogram; (5) observed versus baseline demand on at least two Euro 2024 match days; (6) event-aligned anomalies with comparison/placebo; (7) forecast errors by event and non-event period.

**Required tables:** data audit, seven-match metadata, model diagnostics/assumptions, per-match anomaly MW estimates, placebo/sensitivity checks, out-of-sample forecast comparison.

**Final outputs:**

1. `README.md`: question, sources, reproducibility, headline conclusions and caveats.
2. Clean data-acquisition/preprocessing scripts; no large downloaded raw files committed unnecessarily.
3. EDA/stationarity/spectral analysis; event study; forecasting experiment (notebook(s) or modular scripts).
4. `report.pdf` or `report.docx`, approximately **8–12 pages**, with methods, findings, uncertainties, references and limitations.
5. Instructor presentation, approximately **10–14 clear slides** (adjust to the professor's format).
6. `reflection.md`: which work was intellectually engaging, frustrating, and motivating for the career comparison.

**Suggested repository:**

```text
halftime-effect/
  README.md
  pyproject.toml
  data/README.md
  configs/project.yaml
  src/data_ingest.py
  src/data_validate.py
  src/features.py
  src/baselines.py
  src/event_study.py
  src/evaluate.py
  analyses/01_eda.ipynb
  analyses/02_time_series.ipynb
  analyses/03_events_and_forecasts.ipynb
  figures/
  reports/
  tests/test_time_alignment.py
  tests/test_forecast_cutoff.py
  research_log.md
```

## 8. Common failure modes and contingency rules

| Risk | Detection | Action |
|---|---|---|
| Half-hourly data hide a 5–10 minute pickup | Event effects differ greatly from NESO headline | Report **aggregated anomaly only**; don't claim instantaneous recreation. |
| DST or settlement-period misalignment | Duplicate/missing wall-clock times; fixture appears shifted | Standardize UTC and local timezone carefully; unit-test known 2024 times. |
| Too few match observations | Instability or wide intervals | Show seven separate event estimates; lean on matched-window placebo distribution and explicit uncertainty. |
| Ex-post information leaks into forecast | Weather data/event outcomes published after forecast issue | Split explanatory *retrospective* from truly ex-ante forecasting; use only issue-time-known covariates. |
| Event-aware model lacks historical matches | Coefficient fit mostly on holdout Euro 2024 | Drop confirmatory uplift claim; keep it an illustrative scenario. |
| Unjustified cointegration/GARCH | Diagnostic assumptions fail | Explain rejection; select a suitable method instead. |
| Scope expands to smart-grid engineering | More time spent on dashboards and APIs than statistical analysis | No web app or ML deployment in this assignment. |

## 9. Completion criteria: what counts as a good result?

The project is complete if all of the following are true:

- A second person can download and reconstruct the dataset from cited primary sources.
- Temporal conventions and demand definitions are explicit and checked.
- At least one statistical seasonal model is compared fairly to a meaningful baseline.
- A seven-match event analysis distinguishes description, association, and conditional counterfactual claims.
- Placebo and sensitivity checks probe the strongest conclusion.
- The results include at least one honest negative or uncertain finding if supported by data.
- The report states why unused syllabus techniques were inapplicable or lower-priority.
- No result is invented; NESO's reported 1.3 GW number is not misrepresented as our estimate.

**Career reflection prompts:** Do I enjoy reasoning about imperfect observational data? Did interpreting anomalies feel more rewarding than fitting the models? Did I enjoy making a defensible argument from uncertainty?

## 10. Handoff instructions for the next AI mentor

> You are the student's **guided Data Science mentor** for *The Halftime Effect*. This project specification is the source of truth. Treat every source, research question, time split, scope boundary, and anti-leakage rule here as deliberate. The student should perform the central thinking and coding. Work **one milestone at a time**; first teach the relevant theory simply, then ask the student to attempt a bounded task, review their actual output, and only then proceed. Do not produce an end-to-end implementation unless asked after the student has attempted it. Never invent data, model scores, NESO high-frequency observations, or causal conclusions. Maintain `research_log.md` with hypothesis, approach, evidence, problems and decisions. When a method's assumptions fail, explain why it should not be used. At the end of each milestone, provide a short acceptance checklist and the next task. Start with **Day 1: defining the unit of analysis, research questions, sources and falsifiable hypotheses.**

## 11. Verified starting references

- **S1 — NESO, Britain's Electricity Explained: 2024 Review.** Official report discussing 1 GW and 1.3 GW Euro 2024 TV pickups. https://www.neso.energy/news/britains-electricity-explained-2024-review
- **S2 — NESO, Day Ahead Half Hourly Demand Forecast Performance.** Half-hourly demand forecast, demand outturn, issue timestamps, units. https://www.neso.energy/data-portal/day-ahead-half-hourly-demand-forecast-performance/day_ahead_half_hourly_demand_forecast_performance
- **S3 — NESO, Historic Demand Data (2023; 2024).** `ND`/`TSD` definitions and half-hourly historic records. https://www.neso.energy/data-portal/historic-demand-data/historic_demand_data_2023 and https://www.neso.energy/data-portal/historic-demand-data/historic_demand_data_2024
- **S4 — UEFA, Euro 2024 fixtures and results.** Match dates, stage and competition chronology. https://www.uefa.com/uefaeuro/history/news/0275-151eb1c333ea-d30deec67b13-1000--uefa-euro-2024-results-when-and-where-were-the-matches/
- **S5 — Open-Meteo, Historical Weather API.** Hourly historical weather/reanalysis, variable definitions and API examples. https://open-meteo.com/en/docs/historical-weather-api

**Source status:** Pages above were checked in October 2026. Exact data downloads, timestamp conventions within the extracted file, event timing and availability of any high-frequency public archive **must still be verified during Day 2**; no analysis or project outcomes have been fabricated.
