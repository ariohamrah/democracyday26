"""Acquire public polling data; reproduction uses immutable saved snapshots."""
import json
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import requests

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'data/signals'
OUT.mkdir(exist_ok=True)
JOBS={
 'polls_2026.json':'https://www.electionwrld.com/api/v1/datasets/polls',
 'historical_raw_polls.csv':'https://raw.githubusercontent.com/fivethirtyeight/data/master/pollster-ratings/raw_polls.csv',
 'generic_ballot_polls.csv':'https://projects.fivethirtyeight.com/polls/data/generic_ballot_polls.csv',
 'house_polls.csv':'https://projects.fivethirtyeight.com/polls/data/house_polls.csv',
 'senate_polls.csv':'https://projects.fivethirtyeight.com/polls/data/senate_polls.csv',
}

def get(job):
    name,url=job
    r=requests.get(url,timeout=60)
    if r.status_code==200 and 'text/html' not in r.headers.get('Content-Type',''):
        (OUT/name).write_bytes(r.content)
    return dict(file=name,url=url,status=r.status_code,content_type=r.headers.get('Content-Type'),bytes=len(r.content),saved=(OUT/name).exists())

if __name__=='__main__':
    with ThreadPoolExecutor(max_workers=4) as pool:
        results=list(pool.map(get,JOBS.items()))
    (OUT/'poll_download_log.json').write_text(json.dumps(results,indent=2)+'\n')
    print(json.dumps(results,indent=2))
