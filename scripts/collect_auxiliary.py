"""Public auxiliary evidence snapshots; not automatically admitted as model inputs."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import json
import requests

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'data/signals'
JOBS={
 'ratings_house.json':'https://insideelections.com/wp-content/themes/inside-elections/cache/ratings_latest_house_year=2026_district=all_clean.json?v=1793388069',
 'ratings_senate.json':'https://insideelections.com/wp-content/themes/inside-elections/cache/ratings_latest_senate_year=2026_district=all_clean.json?v=1793297246',
 'fec_weball26.zip':'https://www.fec.gov/files/bulk-downloads/2026/weball26.zip',
 'kalshi_texas_event.json':'https://api.elections.kalshi.com/trade-api/v2/events/SENATETX-26',
}

def fetch(job):
    name,url=job
    try:
        r=requests.get(url,timeout=60)
        saved = r.status_code==200
        if saved: (OUT/name).write_bytes(r.content)
        return dict(file=name,url=url,status=r.status_code,bytes=len(r.content),saved=saved,content_type=r.headers.get('Content-Type'))
    except requests.RequestException as e:
        return dict(file=name,url=url,saved=False,error=str(e))

if __name__=='__main__':
    with ThreadPoolExecutor(max_workers=4) as pool: results=list(pool.map(fetch,JOBS.items()))
    (OUT/'auxiliary_download_log.json').write_text(json.dumps(results,indent=2)+'\n')
    print(json.dumps(results,indent=2))
