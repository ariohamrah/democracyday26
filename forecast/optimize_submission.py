"""Export expected-score picks; never substitute model q for missing scoring p."""
import argparse
from collections import defaultdict
from pathlib import Path

from .io import ROOT, read_csv, write_csv
from .odds import load_odds
from .scoring import expected_points
from .submission import HEADERS, internal_id


def select(candidates, prices, contract_type):
    groups = defaultdict(list)
    for c in candidates:
        groups[c['party'] if contract_type == 'party' else c['candidate']].append(c)
    scores = {}
    missing, zero = [], []
    for outcome, members in groups.items():
        q = sum(float(c['q']) for c in members)
        if q == 0:
            continue
        p = prices.get(outcome)
        if p is None:
            missing.append(outcome)
        elif p == 0:
            zero.append(outcome)
        else:
            scores[outcome] = expected_points(q, p)
    if not scores:
        return None, 'zero_price_requires_rule' if zero else 'missing_prices', None
    best = max(scores, key=scores.get)
    # A party contract cannot distinguish two candidates of the same party.
    if len(groups[best]) != 1:
        return None, 'party_contract_cannot_select_candidate', scores[best]
    status = ('zero_price_requires_rule' if zero else
              'best_among_priced_only' if missing else 'optimized')
    return groups[best][0], status, scores[best]


def build(candidates, prices, metadata, template):
    groups = defaultdict(list)
    for c in candidates:
        groups[c['race_id']].append(c)
    rows, audit = [], []
    for t in template:
        race = internal_id(t)
        if race not in groups:
            raise ValueError(f'Missing candidates: {race}')
        kinds = {m['contract_type'] for (r, _), m in metadata.items() if r == race}
        if len(kinds) > 1:
            raise ValueError(f'Mixed contract types: {race}')
        selected, status, points = select(groups[race], prices.get(race, {}), next(iter(kinds), 'candidate'))
        provisional = any(m['status'] != 'organizer_exact' for (r, _), m in metadata.items() if r == race)
        rows.append(dict(race_id=t['race_id'], chamber=t['chamber'],
                         predicted_winner_party=selected['party'] if selected else '',
                         candidate_name=selected['candidate'] if selected else '',
                         win_probability=selected['q'] if selected else ''))
        audit.append(dict(race_id=t['race_id'], status=status,
                          provisional=provisional, expected_points=points,
                          selected_candidate=selected['candidate'] if selected else ''))
    return rows, audit


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--odds', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--allow-current-proxy', action='store_true')
    parser.add_argument('--fallback-most-likely', action='store_true',
                        help='Fill unpriced/ambiguous draft rows with explicitly audited likely-winner fallbacks.')
    parser.add_argument('--allow-partial-draft', action='store_true',
                        help='Write a DRAFT with blank unpriced races and explicit audit flags.')
    args = parser.parse_args()
    candidates = read_csv(ROOT/'outputs/candidate_forecasts.csv')
    valid = defaultdict(set)
    for c in candidates:
        valid[c['race_id']].update((c['candidate'], 'D', 'R', 'I', 'O'))
    prices, metadata = load_odds(args.odds, valid, allow_current_proxy=args.allow_current_proxy)
    rows, audit = build(candidates, prices, metadata, read_csv(ROOT/'data/submission_template.csv'))
    unresolved = sum(r['status'] != 'optimized' or r['provisional'] for r in audit)
    if unresolved and not args.allow_partial_draft:
        parser.error(f'{unresolved} races have incomplete, ambiguous, zero, or provisional odds. No submission written.')
    if args.fallback_most_likely:
        if not args.allow_partial_draft:
            parser.error('Fallback requires --allow-partial-draft.')
        for row, detail, template in zip(rows, audit, read_csv(ROOT/'data/submission_template.csv')):
            if not row['candidate_name']:
                race = internal_id(template)
                winner = max((c for c in candidates if c['race_id'] == race), key=lambda c:float(c['q']))
                row.update(predicted_winner_party=winner['party'], candidate_name=winner['candidate'], win_probability=winner['q'])
                detail['status'] += ':most_likely_fallback'
                detail['selected_candidate'] = winner['candidate']
    output = Path(args.output)
    if args.allow_partial_draft and 'draft' not in output.stem.lower():
        parser.error('Partial output filename must contain draft.')
    write_csv(output, rows, HEADERS)
    write_csv(output.with_suffix('.audit.csv'), audit)
    counts = defaultdict(int)
    for r in audit:
        counts[r['status']] += 1
    print(dict(counts))
    print(f'{unresolved} races not certified against complete official odds.')


if __name__ == '__main__':
    main()
