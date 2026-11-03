"""Download public geography metadata for auditing; no election-result updates."""
import json
from pathlib import Path
import requests

root = Path(__file__).resolve().parents[1]
out = root / 'data/geography'
out.mkdir(exist_ok=True)
urls = {
    'dataset_index': 'https://www.electionwrld.com/api/v1/datasets',
    'district_example': 'https://www.electionwrld.com/api/v1/districts/CA-01',
}
for key, url in urls.items():
    response = requests.get(url, timeout=60)
    response.raise_for_status()
    data = response.json()
    (out / (key + '.json')).write_text(json.dumps(data, indent=2) + '\n')
    if key == 'district_example':
        print(json.dumps({k: v for k, v in data.items() if k != 'results'}, indent=2))
    else:
        print(json.dumps(data, indent=2)[:16000])
