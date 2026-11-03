"""Strict organizer-odds import. No live-price fallbacks."""
from datetime import datetime
from zoneinfo import ZoneInfo
from .io import read_csv, assert_cutoff, timestamp

FIELDS = ['race_id', 'outcome', 'contract_type', 'probability', 'snapshot_at',
          'snapshot_timezone', 'price_definition', 'source_url', 'status', 'market_ticker']


def load_odds(path, valid_outcomes, allow_current_proxy=False):
    prices, metadata = {}, {}
    for row in read_csv(path):
        missing = set(FIELDS) - set(row)
        if missing:
            raise ValueError(f'Missing odds columns: {sorted(missing)}')
        race, outcome = row['race_id'], row['outcome']
        if race not in valid_outcomes or outcome not in valid_outcomes[race]:
            raise ValueError(f'Unmatched contract: {race}/{outcome}')
        if row['contract_type'] not in ('candidate', 'party'):
            raise ValueError('contract_type must be candidate or party')
        current_proxy = row['status'] == 'current_proxy' and allow_current_proxy
        if row['status'] not in ('organizer_exact', 'provisional_reconstruction', 'missing') and not current_proxy:
            raise ValueError('Unknown snapshot status')
        if (race, outcome) in metadata:
            raise ValueError(f'Duplicate price: {race}/{outcome}')
        if row['probability']:
            if row['status'] == 'missing':
                raise ValueError('A missing price cannot contain a probability')
            if not all(row[k] for k in ('snapshot_at', 'snapshot_timezone', 'price_definition', 'source_url')):
                raise ValueError('Priced contracts need timestamp, timezone, price definition and source')
            if not current_proxy:
                assert_cutoff(row['snapshot_at'])
            snapshot = timestamp(row['snapshot_at']).astimezone(ZoneInfo(row['snapshot_timezone']))
            if snapshot.date().isoformat() != '2026-11-01' and not current_proxy:
                raise ValueError('Scoring price is not from November 1 in its declared timezone')
            p = float(row['probability'])
            if not 0 <= p <= 1:
                raise ValueError('Price must be a probability in [0,1], not cents')
        else:
            p = None
        prices.setdefault(race, {})[outcome] = p
        metadata[race, outcome] = row
    return prices, metadata
