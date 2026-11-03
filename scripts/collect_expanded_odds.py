"""Paginated House markets, case-insensitive rules, and candidate contracts.

Run --cached to replay the private snapshots without changing their file times.
Raw quotes stay private. No model-derived or complementary prices are invented.
"""
import argparse
import json
import re
import unicodedata
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode
from scripts.collect_kalshi_history import ROOT, BASE, get, race_for
from forecast.io import read_csv, write_csv
from forecast.odds import FIELDS

EXTRA = {'KXALASKAHOUSE':'AK-01', 'KXCA11PERSON':'CA-11', 'KXCA17PERSON':'CA-17',
         'KXAKSENATE':'AK-SEN', 'KXMESENATEPERSON':'ME-SEN', 'KXMISENATE':'MI-SEN', 'KXIASENATE':'IA-SEN',
         'HOUSEAKAL':'AK-01'}
ALIASES = {'Nick Begich III':'Nicholas J. Begich III', 'Jim McDermott':'James C. “Jim” McDermott'}


def normalize(s):
    return re.sub('[^a-z0-9]', '', unicodedata.normalize('NFKD', s).encode('ascii','ignore').decode().lower())


def event_race(e):
    match = re.fullmatch(r'KXHOUSERACE-([A-Z]{2})(\d{2}|AL)-26', e['event_ticker'])
    if match:
        return match[1]+'-'+('01' if match[2]=='AL' else match[2])
    # This legacy series is mislabeled by ticker. Its title AND settlement rules name Kentucky.
    if e['series_ticker']=='SENATELA' and 'Kentucky' in e['title']:
        if all('Kentucky' in m.get('rules_primary','') for m in e.get('markets',[])):
            return 'KY-SEN'
        raise ValueError('Kentucky title/rules conflict')
    return EXTRA.get(e['series_ticker']) or race_for(e['series_ticker'])


def parse_event(e, candidates, snapshot):
    if not re.search(r'-26(?:$|-|NOV)', e['event_ticker']):
        return []
    race = event_race(e)
    if race not in candidates:
        return []
    result = []
    for m in e.get('markets', []):
        if m.get('status') not in ('active','open'):
            continue
        rule = m.get('rules_primary',''); lower = rule.lower()
        party = next((p for name,p in [('democratic','D'),('republican','R')]
                      if re.search(r'(?:member|representative) of the '+name+r' party', lower)), None)
        outcome, kind = None, None
        if party and 'sworn in' in lower:
            outcome, kind = party, 'party'
        else:
            name = ALIASES.get(m.get('yes_sub_title'), m.get('yes_sub_title',''))
            matches = [c for c in candidates[race] if normalize(c['candidate'])==normalize(name)]
            # Only named election-win/sworn-in contracts, not primary or margin markets.
            if len(matches)==1 and (' wins ' in lower or 'sworn in' in lower) and 'primary' not in lower:
                outcome,kind = matches[0]['candidate'],'candidate'
        if outcome is None:
            continue
        bid,ask = m.get('yes_bid_dollars'),m.get('yes_ask_dollars')
        if bid is None or ask is None:
            continue
        bid,ask = float(bid),float(ask)
        if not 0<=bid<=ask<=1 or (bid==0 and ask==1):
            continue
        result.append(dict(race_id=race,outcome=outcome,contract_type=kind,probability=(bid+ask)/2,
                           snapshot_at=snapshot,snapshot_timezone='UTC',
                           price_definition='CURRENT_yes_bid_ask_midpoint_NOT_November_1',
                           source_url=f'{BASE}/markets/{m["ticker"]}',status='current_proxy',market_ticker=m['ticker']))
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--cached',action='store_true');args=parser.parse_args()
    folder=ROOT/'private_outputs/current_raw';folder.mkdir(parents=True,exist_ok=True)
    if not args.cached:
        for series in ['KXHOUSERACE', *EXTRA]:
            events=[];cursor=''
            while True:
                response=get(BASE+'/events?'+urlencode(dict(series_ticker=series,with_nested_markets='true',limit=200,cursor=cursor)))
                response.raise_for_status();data=response.json();events.extend(data['events']);cursor=data.get('cursor')
                if not cursor:break
            (folder/(series+'.json')).write_text(json.dumps(dict(events=events)))
    candidates=defaultdict(list)
    for c in read_csv(ROOT/'outputs/candidate_forecasts.csv'):candidates[c['race_id']].append(c)
    grouped=defaultdict(dict)
    for path in sorted(folder.glob('*.json')):
        snapshot=datetime.fromtimestamp(path.stat().st_mtime,timezone.utc).isoformat()
        for e in json.loads(path.read_text()).get('events',[]):
            for row in parse_event(e,candidates,snapshot):
                grouped[row['race_id'],row['outcome']][row['market_ticker']]=row
    # Never discard a race merely because two legacy series overlap. Use the
    # most recently retrieved contract, tie-breaking by ticker deterministically.
    rows=[max(v.values(),key=lambda r:(r['snapshot_at'],r['market_ticker'])) for v in grouped.values()]
    write_csv(ROOT/'private_outputs/expanded_current_odds.csv',sorted(rows,key=lambda r:(r['race_id'],r['outcome'])),FIELDS)
    print(f'{len(rows)} quotes covering {len(set(r["race_id"] for r in rows))} races')


if __name__=='__main__':main()
