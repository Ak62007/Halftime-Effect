# Pre-tournament England fixture inventory

Research date: 17 October 2026  
Scope: England men's senior internationals played from 1 January 2023 through 31 May 2024, inclusive.

19 October update: half-hour demand coverage is now verified for all 12 fixtures. The combined inventory also includes two June warm-ups and seven tournament fixtures, all covered. See [the final dataset handoff](finalized_dataset.md) and `data/processed/final_fixture_coverage.csv`; the original feasibility notes below are historical.

## Result

The [official England legacy register](https://www.englandfootball.com/england/mens-senior-team/Legacy) lists 12 matches in this period: ten in 2023 and two in 2024. The inventory contains eight EURO qualifiers and four friendlies, with seven home and five away fixtures.

Machine-readable file: [england_fixtures_pre_euro_2024.csv](../data/england_fixtures_pre_euro_2024.csv).

These are candidate historical events, not a decision to fit a match-aware model. No electricity demand was downloaded or analysed for these fixtures as part of this research.

## Verified scheduled kickoffs

All clock times below are British time, including away fixtures. They are scheduled kickoffs, not measurements of the actual first whistle.

| Date | Fixture | Competition | British kickoff | UTC kickoff |
|---|---|---|---|---|
| 2023-03-23 | Italy–England | EURO qualifier | 19:45 GMT | 19:45 |
| 2023-03-26 | England–Ukraine | EURO qualifier | 17:00 BST | 16:00 |
| 2023-06-16 | Malta–England | EURO qualifier | 19:45 BST | 18:45 |
| 2023-06-19 | England–North Macedonia | EURO qualifier | 19:45 BST | 18:45 |
| 2023-09-09 | Ukraine–England | EURO qualifier | 17:00 BST | 16:00 |
| 2023-09-12 | Scotland–England | Friendly / heritage match | 19:45 BST | 18:45 |
| 2023-10-13 | England–Australia | Friendly | 19:45 BST | 18:45 |
| 2023-10-17 | England–Italy | EURO qualifier | 19:45 BST | 18:45 |
| 2023-11-17 | England–Malta | EURO qualifier | 19:45 GMT | 19:45 |
| 2023-11-20 | North Macedonia–England | EURO qualifier | 19:45 GMT | 19:45 |
| 2024-03-23 | England–Brazil | Friendly | 19:00 GMT | 19:00 |
| 2024-03-26 | England–Belgium | Friendly | 19:45 GMT | 19:45 |

The date is unchanged by these British-to-UTC conversions. The CSV stores complete ISO timestamps with offsets, a stable match identifier, competition, home/away status, per-row source URLs, and uncertainty notes.

## Evidence and source choices

The legacy register establishes the completed fixture inventory. Official advance announcements explicitly establish the scheduled times and timezone:

| Fixtures covered | Official timing evidence |
|---|---|
| March 2023: Italy and Ukraine | [England squad announcement, 16 March 2023](https://www.englandfootball.com/articles/2023/Mar/16/england-mens-senior-squad-named-for-italy-and-ukraine-euro-qualifiers-20231603) |
| June 2023: Malta and North Macedonia | [Summer squad schedule, 5 May 2023](https://www.englandfootball.com/articles/2023/May/05/summer-england-squad-announcement-dates-confirmed-20230505) |
| September 2023: Ukraine and Scotland | [September squad schedule, 25 August 2023](https://www.englandfootball.com/articles/2023/Aug/25/england-mens-squad-announcement-september-international-window-20232508) |
| October 2023: Australia and Italy | [October squad schedule, 29 September 2023](https://www.englandfootball.com/articles/2023/Sep/29/england-mens-squad-announcement-october-international-window-20232809) |
| November 2023: Malta and North Macedonia | [November squad announcement, 9 November 2023](https://www.englandfootball.com/articles/2023/Nov/09/england-mens-senior-squad-named-for-malta-and-north-macedonia-games-20230911) |
| March 2024: Brazil and Belgium | [Fixture announcement, 6 November 2023](https://www.englandfootball.com/articles/2023/Nov/06/england-mens-team-to-play-brazil-and-belgium-at-wembley-20230611) |

Scheduled times from these advance publications are appropriate calendar metadata; they do not verify what a particular forecast system knew at a specific issue time. A later operational experiment must define its issue time and availability rules.

## Conflicting official labels

Two official match-centre previews have a timezone label inconsistent with explicit advance announcements:

- [England–Ukraine match centre, 26 March 2023](https://www.englandfootball.com/england/mens-senior-team/fixtures-results/2023-24/england-mens-ukraine-uefa-euro-qualifier-wembley-sunday-26-march-2023) prints 17:00 GMT. The March squad announcement explicitly prints 17:00 BST. The CSV uses the latter, yielding 16:00 UTC.
- [England–North Macedonia match centre, 19 June 2023](https://www.englandfootball.com/england/mens-senior-team/fixtures-results/2023-24/england-mens-north-macedonia-uefa-euro-qualifier-old-trafford-monday-19-june-2023) prints 19:45 GMT. The summer schedule and [ticket announcement](https://www.englandfootball.com/articles/2023/Feb/09/Ticket-sale-windows-confirmed-for-England-v-North-Macedonia) explicitly print 19:45 BST. The CSV uses BST, yielding 18:45 UTC.

These conflicts are preserved in the CSV notes rather than silently ignored. They do not establish actual whistle times.

## Interpretation and limitations

- Twelve events are more useful than having no earlier match examples, but still provide a small event sample. Do not treat five-minute rows as independent match replications.
- Eight qualifiers and four friendlies may attract different audiences from tournament knockout games. Generalisation to EURO 2024 must be evaluated, not assumed.
- Scotland–England may affect viewers across two GB nations; consider reporting sensitivity with and without this fixture.
- Historical demand availability has not been checked for each fixture. The next task is a structural coverage audit at these dates, without inspecting effects.
- Actual kickoff, halftime whistle, second-half start, and final whistle are not verified here. Any scheduled-kickoff-based halftime feature is a proxy; exact chronology belongs in separate retrospective fields.
- The 3 and 7 June 2024 warm-up friendlies fall outside the requested 31 May cutoff and are excluded. Including them would require an explicit revision to the development/validation design.
- If March–May 2024 is reserved for validation, only the ten 2023 events are initially available for training. The two March 2024 friendlies must not quietly enter training while also being used for validation.
- This inventory does not settle the demand snapshot-versus-average ambiguity or establish a causal interpretation.

## Next acceptance gate

Check demand coverage and quality for the inventory, then document the chronological train/validation design before looking at match-demand outcomes. Decide whether the number and comparability of usable earlier fixtures justify a simple match adjustment or only an exploratory scenario. Keep the seven EURO 2024 matches as the event holdout.
