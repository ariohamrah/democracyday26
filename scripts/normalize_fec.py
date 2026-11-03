"""Normalize an existing official FEC zip; financing is audit-only, not fitted."""
import csv
import io
import json
import re
import sys
import zipfile
from datetime import datetime
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from forecast.features import name_key
from forecast.io import ROOT,CUTOFF,write_csv


def fec_name(value):
    parts=value.split(',')
    text=(parts[1]+' '+parts[0]) if len(parts)>1 else value
    return re.sub(r'\b(MR|MRS|MS|DR)\.?\b','',text,flags=re.I).strip()


def main():
    z=zipfile.ZipFile(ROOT/'data/signals/fec_weball26.zip')
    raw=csv.reader(io.StringIO(z.read('weball26.txt').decode('utf-8-sig')),delimiter='|')
    rows=[]
    for r in raw:
        if len(r)!=30:
            raise ValueError('Unexpected official FEC schema')
        coverage=datetime.strptime(r[27],'%m/%d/%Y').date().isoformat() if r[27] else ''
        eligible=bool(coverage and coverage<=CUTOFF[:10])
        rows.append(dict(fec_id=r[0],candidate_name=r[1],normalized_name=fec_name(r[1]),
            office={'H':'House','S':'Senate','P':'President'}.get(r[0][:1],''),state=r[18],district=r[19],
            party=r[4],incumbency_code=r[2],total_receipts=r[5],transfers_from_authorized=r[6],
            transfers_to_authorized=r[8],cash_on_hand=r[10],coverage_end=coverage,
            eligible_coverage_date=eligible,filing_received_at='',historical_availability_verified=False,
            source_url='https://www.fec.gov/files/bulk-downloads/2026/weball26.zip'))
    write_csv(ROOT/'data/signals/fec_candidates_2026.csv',rows)
    nominees=list(csv.DictReader(open(ROOT/'data/roster/nominees_audited.csv')))
    matches=[]
    for n in nominees:
        found=[r for r in rows if r['state']==n['state'] and r['office']==n['chamber']
               and name_key(r['normalized_name'])==name_key(n['name']) and r['eligible_coverage_date']]
        # District changes and alternative FEC candidate IDs are not silently resolved.
        status='unique_name_state_office_match' if len(found)==1 else ('ambiguous' if found else 'missing')
        match=found[0] if len(found)==1 else {}
        matches.append(dict(race_id=n['race_id'],candidate=n['name'],party=n['party_label'],match_status=status,
            fec_id=match.get('fec_id',''),total_receipts=match.get('total_receipts',''),cash_on_hand=match.get('cash_on_hand',''),
            coverage_end=match.get('coverage_end',''),filing_received_at='',used_in_model=False))
    write_csv(ROOT/'data/signals/fec_nominee_coverage.csv',matches)
    from collections import Counter
    audit=dict(records=len(rows),nominees=len(nominees),matches=dict(Counter(r['match_status'] for r in matches)),
               cutoff=CUTOFF,used_in_model=False,
               limitation='Coverage dates are known; receipt/amendment timestamps are not. Matching is name/state/office only, not verified committee lineage. Do not infer nominee status from FEC registration.')
    (ROOT/'data/signals/fec_audit.json').write_text(json.dumps(audit,indent=2)+'\n')
    print(json.dumps(audit))

if __name__=='__main__':main()
