"""Collect public Election Wrld / MIT / official results snapshots."""
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import requests

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/'data/bootstrap'
OUT.mkdir(exist_ok=True)
STATES = 'AL AK AZ AR CA CO CT DE FL GA HI ID IL IN IA KS KY LA ME MD MA MI MN MS MO MT NE NV NH NJ NM NY NC ND OH OK OR PA RI SC SD TN TX UT VT VA WA WV WI WY'.split()
JOBS = [(f'house_{year}',f'house/{year}') for year in range(2004,2026,2)]
JOBS += [(f'senate_{st}',f'datasets/senate/{st.lower()}') for st in STATES]
JOBS += [('president_state','datasets/president-state'), ('sources','datasets/sources')]


def download(job):
    name, endpoint = job
    path = OUT/(name+'.json')
    url = 'https://www.electionwrld.com/api/v1/'+endpoint
    if path.exists():
        return name, 'cached'
    response = requests.get(url,timeout=60)
    response.raise_for_status()
    data = response.json()
    path.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
    return name,len(response.content)


if __name__ == '__main__':
    with ThreadPoolExecutor(max_workers=6) as pool:
        for result in pool.map(download,JOBS):
            print(*result,flush=True)
    (OUT/'provenance.json').write_text(json.dumps([dict(file=n+'.json',url='https://www.electionwrld.com/api/v1/'+u,
        attribution='Election Wrld compilation (CC BY 4.0); MIT Election Data and Science Lab and official returns (underlying terms in sources.json)',
        information_scope='Election results no later than 2024; newer results must be excluded') for n,u in JOBS],indent=2)+'\n')
