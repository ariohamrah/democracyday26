"""Fetch live party quotes as an explicitly authorized proxy, never historical odds."""
import csv
import json
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from scripts.collect_kalshi_history import BASE, ROOT, get, race_for
from forecast.io import write_csv
from forecast.odds import FIELDS


def fetch(job):
    ticker, race = job
    url = f'{BASE}/events?series_ticker={ticker}&with_nested_markets=true&limit=200'
    response = get(url)
    if response.status_code != 200:
        return []
    data = response.json()
    (ROOT/'private_outputs/current_raw'/f'{ticker}.json').write_text(json.dumps(data))
    result = []
    for event in data.get('events', []):
        if not re.search(r'-26(?:$|-)', event['event_ticker']):
            continue
        for m in event.get('markets', []):
            rule = m.get('rules_primary', '')
            if 'sworn in' not in rule:
                continue
            party = next((p for label, p in [('Democratic', 'D'), ('Republican', 'R')]
                          if f'representative of the {label} party' in rule or f'member of the {label} party' in rule), None)
            if party is None or m.get('status') not in ('active', 'open'):
                continue
            bid, ask = m.get('yes_bid_dollars'), m.get('yes_ask_dollars')
            if bid is None or ask is None:
                continue
            bid, ask = float(bid), float(ask)
            if not 0 <= bid <= ask <= 1 or (bid == 0 and ask == 1):
                continue
            result.append(dict(race_id=race, outcome=party, contract_type='party', probability=(bid+ask)/2,
                               snapshot_at=datetime.now(timezone.utc).isoformat(), snapshot_timezone='UTC',
                               price_definition='CURRENT_yes_bid_ask_midpoint_NOT_November_1', source_url=url,
                               status='current_proxy', market_ticker=m['ticker']))
    return result


def main():
    (ROOT/'private_outputs/current_raw').mkdir(parents=True, exist_ok=True)
    series = json.loads((ROOT/'data/signals/kalshi_series.json').read_text())['series']
    valid = {r['race_id'] for r in csv.DictReader((ROOT/'outputs/forecasts.csv').open())}
    jobs = [(s['ticker'], race_for(s['ticker'])) for s in series if race_for(s['ticker']) in valid]
    grouped = {}
    with ThreadPoolExecutor(max_workers=4) as pool:
        for rows in pool.map(fetch, jobs):
            for r in rows:
                grouped.setdefault((r['race_id'], r['outcome']), []).append(r)
    unique = [v[0] for v in grouped.values() if len(v) == 1]
    write_csv(ROOT/'private_outputs/current_odds.csv', sorted(unique, key=lambda r:(r['race_id'],r['outcome'])), FIELDS)
    print(f'{len(unique)} current quotes across {len(set(r["race_id"] for r in unique))} races', flush=True)


if __name__ == '__main__':
    main()
