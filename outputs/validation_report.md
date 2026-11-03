# Validation report

Information cutoff: **2026-11-02T20:13:00-08:00**. Reproduction is offline from saved snapshots.

## Measured historical performance

Expanding, whole-cycle holdouts: 2016, 2018, 2020, 2022, 2024. Each fit and ridge penalty uses earlier cycles only; error calibration also uses nested earlier-cycle fits. Training starts in 2006. These measurements cover ordinary regular D/R contests, not every historical ballot configuration.

| Model | Races | Brier | Log loss (natural log) | Winner accuracy |
|---|---:|---:|---:|---:|
| full | 2100 | 0.04070 | 0.13359 | 94.48% |
| without_aura | 2100 | 0.04050 | 0.13303 | 94.48% |
| without_local_polls | 2100 | 0.04124 | 0.13741 | 94.38% |
| without_generic_ballot | 2100 | 0.03703 | 0.12513 | 94.76% |
| fundamentals_only | 2100 | 0.03661 | 0.12572 | 95.10% |

Lower Brier/log loss is better. Ablations independently refit/tune/recalibrate the model. No significance or causal claim is made from a small number of correlated election cycles.

Aura Brier difference (full minus no aura): **+0.000204**. The fitted aura coefficient is **+1.3384 margin points per one-unit score difference**. This is an exploratory name-form hypothesis, not evidence of a voter mechanism.

## Full-model slices

| Slice | Races | Brier | Log loss | Accuracy |
|---|---:|---:|---:|---:|
| competitive | 452 | 0.12575 | 0.38858 | 82.52% |
| unpolled_or_archive_missing | 1726 | 0.01931 | 0.07222 | 97.62% |
| polled | 374 | 0.13943 | 0.41686 | 79.95% |
| House | 1949 | 0.03938 | 0.12991 | 94.77% |
| Senate | 151 | 0.05773 | 0.18110 | 90.73% |
| 2016 | 399 | 0.03274 | 0.11248 | 95.74% |
| 2018 | 420 | 0.06860 | 0.20138 | 89.52% |
| 2020 | 435 | 0.04299 | 0.15094 | 95.63% |
| 2022 | 426 | 0.03747 | 0.12363 | 94.37% |
| 2024 | 420 | 0.02128 | 0.07801 | 97.14% |

Competitive means the prior presidential two-party margin was within 10 points. “Unpolled” includes missing polling archives; it is not proof no poll existed. No 2024 local or generic polls were recovered.

## Calibration

| Predicted bin | Count | Mean forecast | Observed D-win rate |
|---|---:|---:|---:|
| 0.0–0.1 | 876 | 0.015 | 0.005 |
| 0.1–0.2 | 84 | 0.149 | 0.214 |
| 0.2–0.3 | 62 | 0.248 | 0.306 |
| 0.3–0.4 | 44 | 0.342 | 0.364 |
| 0.4–0.5 | 32 | 0.451 | 0.406 |
| 0.5–0.6 | 34 | 0.560 | 0.618 |
| 0.6–0.7 | 33 | 0.643 | 0.727 |
| 0.7–0.8 | 41 | 0.744 | 0.756 |
| 0.8–0.9 | 83 | 0.851 | 0.940 |
| 0.9–1.0 | 811 | 0.989 | 0.989 |

## Coverage

- Forecast roster: 435 House, 35 Senate; 65 Senate holdovers; 1281 candidate records.
- Historical training: 4152 eligible races, 2006–2024; individual exclusions are saved.
- House geography: 435/435 district presidential baselines reaggregated on the 2026 maps by The Downballot. Same-number old congressional results are suppressed in redistricted states.
- Current local polling matched in 70/470 races. Current national generic feature: D+8.00, from 1 eligible survey(s) in the saved archive.
- Scoring prices: 0 races have a calculable best-priced outcome; only 0 have prices covering every modeled positive-probability outcome.
- Finance coverage and rejected matches are in `data/signals/fec_audit.json`; finance is audit-only.
- Historical competition points: unavailable; no benchmark price backtest is claimed.

## Material limitations and unresolved gaps

1. **Historical as-of reconstruction is incomplete.** Polls lack original publication timestamps; median field date plus three days is a safeguard, not proof of availability. Nominee lists and geographic presidential calculations are retrospective reconstructions. Simultaneous presidential results and post-2024 outcomes are excluded.
2. **The delivered candidate-field extensions are not fully backtested.** Same-party contests borrow a separately estimated incumbent prior. Independent challengers borrow partisan fundamentals but retain independent identities. Louisiana forecasts refer to the eventual winner and allocate party probability using incumbency or equal shares; advancement and runoff transfers are not fitted. Ranked-choice outcomes use an eventual-winner approximation. Montana uses complete three-way polling when available. These races deserve particular caution.
3. **Data gaps remain.** The current polling archive has only one generic survey in its final 30-day window, though other public aggregate snapshots are documented. Expert ratings were researched, but automated downloads returned 403 and historical dated ratings were not recovered. Approval and FEC finance are collected for audit, not fitted updates. Demographics are not admitted without comparable dated district data. No incremental-performance claim is made for excluded inputs.
4. **Public scoring prices are missing.** A provisional November 1 Kalshi reconstruction was technically recovered but excluded from publication because redistribution permission was not established under the source’s data terms. Import the organizer’s authorized snapshot. Current prices are never substituted. Missing/zero prices remain unresolved; best-priced choices are not labeled globally optimal when another modeled outcome has no price. Party-settlement contracts are not candidate contracts. See `docs/market_data_publication.md`.
5. **Chamber uncertainty is estimated from few cycles.** Shared national/regional errors are fitted from earlier holdout residuals; rare realignments and correlated candidate-field errors may be understated. Independent caucus choices are reported as bounds. Printed-ballot uncontested probabilities are conditional on ballot/qualification assumptions.
6. **Official competition acceptance is not verified.** CSVs are standard UTF-8 files for Drive/Sheets; the organizer’s official odds snapshot and scoring universe remain unresolved.

See `historical_backtests.csv` for every prediction, `historical_features.csv` for inspectable feature rows, `validation.json` for machine-readable metrics, and `model.json` for fitted coefficients and field-prior counts.
