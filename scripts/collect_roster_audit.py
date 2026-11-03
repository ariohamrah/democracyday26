"""Reproduce audited nominees and Senate holdovers from checked-in snapshots."""
import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def write_csv(path, rows):
    with path.open('w', newline='', encoding='utf-8') as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main():
    folder = ROOT / 'data/roster'
    with (folder / 'nominee_overrides.csv').open() as handle:
        overrides = {(r['race_id'], r['original_name']): r for r in csv.DictReader(handle)}
    with (ROOT / 'data/bootstrap/official_nominees.csv').open() as handle:
        raw = list(csv.DictReader(handle))
    rows = []
    matched = set()
    for row in raw:
        key = row['race_id'], row['name']
        if key in overrides:
            matched.add(key)
            change = overrides[key]
            if change['action'] == 'exclude':
                continue
            row['name'] = change['name']
            row['party_label'] = change['party_label']
        rows.append(row)
    assert matched == set(overrides), 'Overrides must match exactly one source candidate'
    assert len({r['race_id'] for r in rows if r['chamber'] == 'House'}) == 435
    assert len({r['race_id'] for r in rows if r['chamber'] == 'Senate'}) == 35
    assert len({(r['race_id'], r['name']) for r in rows}) == len(rows)
    write_csv(folder / 'nominees_audited.csv', rows)
    congress = json.loads((ROOT / 'data/bootstrap/congress.json').read_text())
    holdovers = []
    for state, senators in sorted(congress['senate'].items()):
        for senator in senators:
            if senator['class'] == 2 or (state in ('FL', 'OH') and senator['class'] == 3):
                continue
            holdovers.append(dict(state=state, seat_class=senator['class'], name=senator['name'],
                                  party=senator['party'], caucus='D' if senator['party'] == 'I' else senator['party'],
                                  bioguide=senator['bioguide'],
                                  source_url='https://www.electionwrld.com/api/v1/datasets/congress',
                                  source_date='2026-11-02'))
    assert len(holdovers) == 65
    write_csv(folder / 'senate_holdovers.csv', holdovers)
    print(f'{len(rows)} candidate lines; 435 House races; 35 Senate races; 65 holdovers')


if __name__ == '__main__':
    main()
