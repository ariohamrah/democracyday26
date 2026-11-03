# 2026 congressional forecast

This repository builds actual candidate and party forecasts for all 435 voting House seats and 35 Senate contests, with 65 Senate holdovers in chamber simulations. The CSVs import directly into Google Drive/Sheets. It separates estimated election probabilities **q** from November 1 Kalshi scoring probabilities **p**.

The information cutoff is **November 2, 2026, 8:13 p.m. America/Los_Angeles** (`2026-11-02T20:13:00-08:00`). Date-only current sources have day-level provenance; exact intraday availability is not certified. The local source snapshots contain no 2026 general-election results used by the model.

## Reproduce

Python 3.9+:

```sh
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python -m forecast.run
```

All forecast commands are offline after dependency installation. The seed is 20261102 and chamber simulations use 100,000 draws. Source-refresh scripts are separate and should not be run to reproduce this frozen edition. Results can differ at the last floating-point digits across numerical-library/platform versions.

All 34 local tests passed. `docs/github-actions-workflow.example.yml` is an optional CI configuration; it is not installed as an active workflow because the available GitHub token lacks the workflow scope.

## Outputs

- `outputs/submission.csv`: 470 rows; most likely candidate, probability, fully score-maximizing selection where all needed prices exist, and best available priced selection with explicit status.
- `outputs/forecasts.csv`: race-level diagnostics, party probabilities, distinct market prices, modeled candidate pair, polling coverage, aura, geography, and limitations.
- `outputs/candidate_forecasts.csv`: every candidate with model probability and inspectable name score. A party price shown alongside a candidate is explicitly **not** that candidate's price.
- `outputs/chamber_forecasts.json`: shared-error simulations of the full chambers, including independent caucus bounds.
- `outputs/validation_report.md` / `validation.json`: measured out-of-time results, ablations, calibration, coverage and gaps.
- `outputs/historical_backtests.csv`, `historical_features.csv`, `historical_exclusions.csv`: audit trail.
- `outputs/writeup.txt`: approximately 100-word submission paragraph.

Upload CSVs to Drive, then choose **Open with Google Sheets**, or use Sheets **File → Import → Upload**. No spreadsheet-specific formulas or macros are required.

## Model

A standardized ridge regression predicts the Democratic-minus-Republican two-party margin from lagged congressional returns, **strictly prior** presidential returns, incumbency inferred from prior winners (official nominees for 2026), midterm presidential party, chamber, missingness, and name aura. Target-map presidential baselines replace noncomparable old district returns. Polling adds a national generic-ballot feature and a local margin residual, with presence indicators. Ridge penalties are selected using expanding whole-cycle validation; uncertainty is calibrated using nested earlier-cycle errors. Geographic and candidate matching rules are explicit in source.

The name score is the equal-weight mean of five fixed name-only heuristics: length near 12 letters, estimated syllable rhythm, first/last alliteration, absence of long consonant clusters, and distinct-letter fraction. It takes no party, fame, biography or outcome input. Its regression coefficient is learned, and an out-of-time no-aura ablation is reported. The English/ASCII-oriented pronunciation heuristic has obvious linguistic limitations; it is not a measure of candidate quality or a demonstrated causal effect.

Historical tests hold out complete cycles from 2016 through 2024. The fitted binary model's performance must not be read as validation of all candidate-field extensions. See the validation report for the separate assumptions covering same-party contests, independents, minor parties, ranked choice and runoffs. Uncontested seats are conditional on the printed ballot. Senate composition includes holdovers; new independent winners are not silently assigned to Democrats.

Polling aggregations deduplicate firm/field-date questions, favor likely-voter samples, cap sample-size influence, discount partisan polls, and decay older observations. Those aggregation settings are declared heuristics; the incremental regression weights are learned. Expert ratings, approval, finance and demographics are not assigned invented fitted weights when usable historical validation data are missing. Finance/public national snapshots are preserved for audit.

## Competition scoring and odds import

For each eligible outcome, expected reward is `q * -log2(p)`. The most likely winner and reward-maximizing choice can differ. With exactly complementary binary prices and `q=p`, the underdog is the expected-score-optimal choice (a tie at 0.5). This benchmark is tested and emitted where its assumptions hold.

The published default `data/odds/organizer_odds.csv` has no price rows. Historical prices were technically recovered, but **quotes and price-derived selections are excluded from publication because redistribution permission was not established** under [Kalshi's Data Terms](https://kalshi-public-docs.s3.amazonaws.com/kalshi-data-terms-of-service.pdf). See `docs/market_data_publication.md`. A private reconstruction used **2026-11-01 23:00 America/New_York**, closing hourly yes-bid/yes-ask midpoints, and was labeled provisional. It is not the organizer's verified snapshot and is not required for public reproduction. Missing prices are blank; zero prices require an organizer rule because the logarithm is undefined. A price of one has zero reward. No epsilon substitute is used for scoring.

Fill `outputs/organizer_odds_template.csv` with the organizer's data and run:

```sh
python3 -m forecast.run --odds /absolute/path/organizer_odds.csv
```

Required fields: `race_id,outcome,contract_type,probability,snapshot_at,snapshot_timezone,price_definition,source_url,status,market_ticker`. Probability is 0–1, not cents. Use exact candidate names for `candidate` contracts or D/R/I/O for `party` contracts. A race import must use one contract type. Timestamps require offsets and must fall on November 1 in the declared IANA timezone. Status is `organizer_exact`, `provisional_reconstruction`, or `missing`. The importer rejects duplicates, unknown races/outcomes, wrong dates, invalid probabilities and mixed contract definitions. The organizer's official snapshot and scoring universe remain unknown.

`best_priced_selection` maximizes reward only over imported priced outcomes. `score_maximizing_selection` is blank if any positive-probability outcome lacks a price, or a zero-price rule is unresolved. Blank means unresolved, never zero. A complete winner-prediction CSV is provided even when a complete score-optimized entry cannot be certified.

## Sources and provenance

- [MIT Election Data and Science Lab](https://electionlab.mit.edu/data): historical congressional and presidential returns, retrieved through [Election Wrld's public API](https://www.electionwrld.com/developers), with source-specific official supplements. Underlying MIT data are CC0; Election Wrld compilation is CC BY 4.0. Detailed attribution is preserved in `data/bootstrap/sources.json`.
- [House Clerk official 2026 nominees](https://clerk.house.gov/member_info/electionInfo/2026/120-nominations.pdf): October 8 list, parsed with font-aware superscript handling; official-source corrections and targeted later checks in `data/roster/`. Original PDF is retained. Incumbency uses its markers, including candidates who moved districts.
- [The Downballot / Daily Kos Elections district presidential calculations](https://www.the-downballot.com/p/the-downballots-calculations-of-presidential): district baselines on historical and 2026 geography, including exact 2024 counts on 2026 lines. Public downloadable numerical tables retained with attribution. Current incumbent columns in historical sheets are never model inputs. Missouri is checked against its reverted map.
- [FiveThirtyEight raw polling archive](https://github.com/fivethirtyeight/data/tree/master/pollster-ratings): use poll observations only, never `actual` results or retrospective pollster-quality columns as features. CC BY 4.0; original publication timestamps are absent. VoteHub via Election Wrld supplies current polls and original survey links (CC BY 4.0).
- [FEC bulk data](https://www.fec.gov/data/browse-data/?tab=bulk-data): candidate receipts/cash on hand; audit-only because filing/amendment-time provenance was not recovered.
- [Kalshi API](https://docs.kalshi.com/api-reference/market/get-market-candlesticks): historical retrieval code and strict organizer-odds import; restricted market-data snapshots are not published and no trading is performed.
- Additional source checks, including FiftyPlusOne, expert ratings, approval and access limitations: `docs/signals.md`.

`data/manifest.json` records SHA-256 hashes of published data files. Original source terms remain applicable; no blanket license is asserted over third-party data. Snapshot refresh commands live in `scripts/` and require applicable source permissions. PDF parsing requires pdfplumber only for refresh, not offline forecast reproduction.

## Limits

Historical as-of publication reconstruction is imperfect; 2024 polling is unavailable; current national polling coverage in the downloadable archive is sparse. FEC and ratings are not fitted model updates. No demographic feature is included without comparable dated data. Field-specific candidate probabilities, especially Louisiana's within-party splits, are weaker than ordinary D/R probabilities. Shared-error covariance has few independent cycles to estimate it. Reported historical accuracy is not a claim of competition points, causal name effects, or superior future performance.
