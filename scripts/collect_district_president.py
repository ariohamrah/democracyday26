"""Public export links published by The Downballot / Daily Kos Elections.

Only past presidential elections are used at each forecast origin; incumbent
columns and simultaneous presidential returns MUST NOT be used for backtests.
"""
import csv
import json
from pathlib import Path
import requests

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'data/geography'
SHEETS = {
    2026: ('1eZfaFI-c-PFOoKx1-zZA2MP0_dxRq_LVK0re3BOQqy0', '620838163'),
    2024: ('1ng1i_Dm_RMDnEvauH44pgE6JCUsapcuu8F2pCfeLWFo', '620838163'),
    2022: ('1CKngqOp8fzU22JOlypoxNsxL6KSAH920Whc-rd7ebuM', '1871835782'),
    2020: ('1XbUXnI9OyfAuhP5P3vWtMuGc5UJlrhXbzZo3AwMuHtk', '0'),
    2018: ('1zLNAuRqPauss00HDz4XbTH2HqsCzMe0pR8QmD1K8jk8', '0'),
    2016: ('1VfkHtzBTP5gf4jAu8tcVQgsBJ1IDvXEHjuMqYlOgYbA', '0'),
    2014: ('1xn6nCNM97oFDZ4M-HQgoUT3X4paOiSDsRMSuxbaOBdg', '0'),
    2010: ('1l7W130tPRF6dQ4JoqlQJSJexnEg4rZct-7kwDXqgoLE', '429358610'),
}


def main():
    provenance = []
    for year, (key, gid) in SHEETS.items():
        url = f'https://docs.google.com/spreadsheets/d/{key}/export?format=csv&gid={gid}'
        response = requests.get(url, timeout=60)
        response.raise_for_status()
        path = OUT / f'presidential_districts_map_{year}.csv'
        path.write_bytes(response.content)
        print(year, len(response.content), response.text[:300])
        provenance.append(dict(map_year=year, url=url,
                               attribution='The Downballot / Daily Kos Elections',
                               source_page='https://www.the-downballot.com/p/the-downballots-calculations-of-presidential',
                               caveat='Use only election-year columns strictly earlier than forecast year; ignore current incumbent columns.'))
    (OUT / 'president_provenance.json').write_text(json.dumps(provenance, indent=2)+'\n')
    exact_url='https://docs.google.com/spreadsheets/d/1eZfaFI-c-PFOoKx1-zZA2MP0_dxRq_LVK0re3BOQqy0/export?format=csv&gid=1491069057'
    response=requests.get(exact_url,timeout=60)
    response.raise_for_status()
    (OUT/'presidential_districts_map_2026_exact.csv').write_bytes(response.content)


if __name__ == '__main__':
    main()
