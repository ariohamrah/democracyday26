from .io import ROOT,CUTOFF


def write_report(report,info,chamber):
    c=report['coverage'];m=report['metrics']
    lines=['# Validation report','',f'Information cutoff: **{CUTOFF}**. Reproduction is offline from saved snapshots.','',
           '## Measured historical performance','',
           'Expanding, whole-cycle holdouts: 2016, 2018, 2020, 2022, 2024. Each fit and ridge penalty uses earlier cycles only; error calibration also uses nested earlier-cycle fits. Training starts in 2006. These measurements cover ordinary regular D/R contests, not every historical ballot configuration.','',
           '| Model | Races | Brier | Log loss (natural log) | Winner accuracy |',
           '|---|---:|---:|---:|---:|']
    for name,slices in m.items():
        v=slices['all'];lines.append(f"| {name} | {v['n']} | {v['brier']:.5f} | {v['log_loss']:.5f} | {v['accuracy']:.2%} |")
    lines+=['','Lower Brier/log loss is better. Ablations independently refit/tune/recalibrate the model. No significance or causal claim is made from a small number of correlated election cycles.','',
            f"Aura Brier difference (full minus no aura): **{report['aura_brier_delta_full_minus_without']:+.6f}**. The fitted aura coefficient is **{info['coefficients']['aura_difference']:+.4f} margin points per one-unit score difference**. This is an exploratory name-form hypothesis, not evidence of a voter mechanism.",'',
            '## Full-model slices','',
            '| Slice | Races | Brier | Log loss | Accuracy |','|---|---:|---:|---:|---:|']
    for key,v in m['full'].items():
        if key=='all':continue
        if v['n']:lines.append(f"| {key} | {v['n']} | {v['brier']:.5f} | {v['log_loss']:.5f} | {v['accuracy']:.2%} |")
    lines+=['','Competitive means the prior presidential two-party margin was within 10 points. “Unpolled” includes missing polling archives; it is not proof no poll existed. No 2024 local or generic polls were recovered.','',
            '## Calibration','', '| Predicted bin | Count | Mean forecast | Observed D-win rate |','|---|---:|---:|---:|']
    for b in m['full']['all']['calibration']:
        lines.append(f"| {b['lower']:.1f}–{b['lower']+.1:.1f} | {b['n']} | {b['predicted']:.3f} | {b['observed']:.3f} |")
    lines+=['','## Coverage','',f"- Forecast roster: {c['house_races']} House, {c['senate_races']} Senate; {c['senate_holdovers']} Senate holdovers; {c['nominees']} candidate records.",
            f"- Historical training: {c['training_rows']} eligible races, 2006–2024; individual exclusions are saved.",
            f"- House geography: {c['district_geographic_baselines']}/435 district presidential baselines reaggregated on the 2026 maps by The Downballot. Same-number old congressional results are suppressed in redistricted states.",
            f"- Current local polling matched in {c['current_locally_polled']}/470 races. Current national generic feature: D{c['current_generic_margin']:+.2f}, from {c['current_generic_poll_count']} eligible survey(s) in the saved archive.",
            f"- Scoring prices: {c['races_with_some_priced_outcomes']} races have a calculable best-priced outcome; only {c['races_with_complete_scoring_prices']} have prices covering every modeled positive-probability outcome.",
            '- Finance coverage and rejected matches are in `data/signals/fec_audit.json`; finance is audit-only.',
            '- Historical competition points: unavailable; no benchmark price backtest is claimed.','',
            '## Material limitations and unresolved gaps','',
            '1. **Historical as-of reconstruction is incomplete.** Polls lack original publication timestamps; median field date plus three days is a safeguard, not proof of availability. Nominee lists and geographic presidential calculations are retrospective reconstructions. Simultaneous presidential results and post-2024 outcomes are excluded.',
            '2. **The delivered candidate-field extensions are not fully backtested.** Same-party contests borrow a separately estimated incumbent prior. Independent challengers borrow partisan fundamentals but retain independent identities. Louisiana forecasts refer to the eventual winner and allocate party probability using incumbency or equal shares; advancement and runoff transfers are not fitted. Ranked-choice outcomes use an eventual-winner approximation. Montana uses complete three-way polling when available. These races deserve particular caution.',
            '3. **Data gaps remain.** The current polling archive has only one generic survey in its final 30-day window, though other public aggregate snapshots are documented. Expert ratings were researched, but automated downloads returned 403 and historical dated ratings were not recovered. Approval and FEC finance are collected for audit, not fitted updates. Demographics are not admitted without comparable dated district data. No incremental-performance claim is made for excluded inputs.',
            '4. **Public scoring prices are missing.** A provisional November 1 Kalshi reconstruction was technically recovered but excluded from publication because redistribution permission was not established under the source’s data terms. Import the organizer’s authorized snapshot. Current prices are never substituted. Missing/zero prices remain unresolved; best-priced choices are not labeled globally optimal when another modeled outcome has no price. Party-settlement contracts are not candidate contracts. See `docs/market_data_publication.md`.',
            '5. **Chamber uncertainty is estimated from few cycles.** Shared national/regional errors are fitted from earlier holdout residuals; rare realignments and correlated candidate-field errors may be understated. Independent caucus choices are reported as bounds. Printed-ballot uncontested probabilities are conditional on ballot/qualification assumptions.',
            '6. **Official competition acceptance is not verified.** CSVs are standard UTF-8 files for Drive/Sheets; the organizer’s official odds snapshot and scoring universe remain unresolved.','',
            'See `historical_backtests.csv` for every prediction, `historical_features.csv` for inspectable feature rows, `validation.json` for machine-readable metrics, and `model.json` for fitted coefficients and field-prior counts.']
    (ROOT/'outputs/validation_report.md').write_text('\n'.join(lines)+'\n')
