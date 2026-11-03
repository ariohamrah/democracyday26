"""Reconstruct a PROVISIONAL Nov 1 snapshot, never from current market prices.

Chosen time: 2026-11-01 23:00 America/New_York. Chosen definition: midpoint
of hourly closing yes bid/ask. Organizer time/definition are unknown.
Only explicit party-settlement contracts are admitted by this collector.
"""
import csv
import json
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
import requests
import threading
import time

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'data/odds'
RAW=OUT/'raw'
BASE='https://api.elections.kalshi.com/trade-api/v2'
SNAPSHOT='2026-11-01T23:00:00-05:00'
END=int(datetime.fromisoformat(SNAPSHOT).timestamp())
START=END-24*3600
LOCK=threading.Lock()
LAST=[0.]


def get(url):
    for attempt in range(4):
        with LOCK:
            delay=max(0.,.4-(time.monotonic()-LAST[0]))
            if delay:time.sleep(delay)
            LAST[0]=time.monotonic()
        response=requests.get(url,timeout=60)
        if response.status_code!=429:return response
        time.sleep(float(response.headers.get('Retry-After') or 2**(attempt+1)))
    return response


def race_for(ticker):
    house=re.fullmatch(r'(?:KX)?HOUSE([A-Z]{2})(\d{1,2})',ticker)
    if house:return f'{house[1]}-{int(house[2]):02}'
    senate=re.fullmatch(r'(?:KX)?SENATE(?:PARTY-?)?([A-Z]{2})(?:S)?',ticker)
    if senate:
        st=senate[1]
        return st+'-SEN'+('-SPECIAL' if st in ('FL','OH') else '')
    return None


def fetch_series(job):
    ticker,race=job
    url=f'{BASE}/events?series_ticker={ticker}&with_nested_markets=true&limit=200'
    cache=RAW/(ticker+'_events.json')
    if cache.exists():data=json.loads(cache.read_text())
    else:
        response=get(url)
        if response.status_code!=200:return [],dict(series=ticker,status=response.status_code)
        data=response.json()
        cache.write_text(json.dumps(data,indent=2)+'\n')
    rows=[]
    for event in data.get('events',[]):
        if not re.search(r'-26(?:$|-)',event['event_ticker']):continue
        for market in event.get('markets',[]):
            rule=market.get('rules_primary','')
            if ('representative of the Democratic party' in rule or 'member of the Democratic party' in rule) and 'sworn in' in rule:outcome='D'
            elif ('representative of the Republican party' in rule or 'member of the Republican party' in rule) and 'sworn in' in rule:outcome='R'
            else:continue
            mt=market['ticker']
            history_url=f'{BASE}/series/{ticker}/markets/{mt}/candlesticks?start_ts={START}&end_ts={END}&period_interval=60'
            candle_cache=RAW/(mt+'_candles.json')
            if candle_cache.exists():candles=json.loads(candle_cache.read_text())
            else:
                r=get(history_url)
                if r.status_code!=200:continue
                candles=r.json()
                candle_cache.write_text(json.dumps(candles,indent=2)+'\n')
            # Require the candle exactly at the chosen snapshot; no stale/current fill.
            matching=[c for c in candles.get('candlesticks',[]) if c['end_period_ts']==END]
            price=None
            if matching:
                c=matching[-1]
                bid=c.get('yes_bid',{}).get('close_dollars')
                ask=c.get('yes_ask',{}).get('close_dollars')
                if bid is not None and ask is not None:
                    bid,ask=float(bid),float(ask)
                    if 0<=bid<=ask<=1:price=(bid+ask)/2
            rows.append(dict(race_id=race,outcome=outcome,contract_type='party',probability=price if price is not None else '',
                             snapshot_at=SNAPSHOT,snapshot_timezone='America/New_York',
                             price_definition='hourly_closing_yes_bid_ask_midpoint',source_url=history_url,
                             status='provisional_reconstruction' if price is not None else 'missing',market_ticker=mt))
    return rows,dict(series=ticker,status=200,rows=len(rows))


def main():
    RAW.mkdir(parents=True,exist_ok=True)
    series=json.loads((ROOT/'data/signals/kalshi_series.json').read_text())['series']
    jobs=[(s['ticker'],race_for(s['ticker'])) for s in series if race_for(s['ticker'])]
    valid={r['race_id'] for r in csv.DictReader((ROOT/'data/roster/nominees_audited.csv').open())}
    jobs=[j for j in jobs if j[1] in valid]
    rows,logs=[],[]
    with ThreadPoolExecutor(max_workers=4) as pool:
        for result,log in pool.map(fetch_series,jobs):
            rows.extend(result);logs.append(log)
    # Reject ambiguity instead of arbitrarily choosing between series for same race.
    grouped={}
    for r in rows:grouped.setdefault((r['race_id'],r['outcome']),[]).append(r)
    unique=[v[0] for v in grouped.values() if len(v)==1]
    unique.sort(key=lambda r:(r['race_id'],r['outcome']))
    with (OUT/'provisional_nov1.csv').open('w',newline='',encoding='utf-8') as f:
        fields=['race_id','outcome','contract_type','probability','snapshot_at','snapshot_timezone','price_definition','source_url','status','market_ticker']
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(unique)
    (OUT/'reconstruction_log.json').write_text(json.dumps(dict(snapshot_at=SNAPSHOT,
        status='PROVISIONAL: organizer time and price definition unknown',series=logs,
        ambiguous_contracts=[list(k) for k,v in grouped.items() if len(v)>1],rows=len(unique)),indent=2)+'\n')
    print(len(jobs),'series queried;',len(unique),'unique party contracts;',sum(bool(r['probability']) for r in unique),'priced')


if __name__=='__main__':main()
