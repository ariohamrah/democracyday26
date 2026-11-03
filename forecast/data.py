"""Normalize saved result snapshots; keep exclusions inspectable."""
import json
from collections import Counter
from .io import ROOT
from .geography import normalize_race


def load_history():
    all_races, audit = [], []

    def add(race_id, chamber, state, district, seat_class, contest, series):
        year = int(contest['year'])
        if not 2004 <= year <= 2024 or year % 2 or contest.get('runoff'):
            return
        candidates = [c for c in contest['candidates'] if not c.get('writein')]
        ds = [c for c in candidates if c.get('party') == 'D']
        rs = [c for c in candidates if c.get('party') == 'R']
        reason = ''
        if contest.get('special'):
            reason = 'special_election_not_comparable_origin'
        elif len(ds) != 1 or len(rs) != 1:
            reason = 'unopposed_or_nonstandard_candidate_field'
        elif contest.get('round') == 'first-choice':
            reason = 'rcv_final_round_missing'
        final = contest
        if contest.get('decidedBy'):
            possible = [c for c in series if c.get('date') == contest['decidedBy']]
            if not possible:
                reason = 'runoff_result_missing'
            else:
                final = possible[0]
        final_ds = [c for c in final['candidates'] if c.get('party') == 'D' and not c.get('writein')]
        final_rs = [c for c in final['candidates'] if c.get('party') == 'R' and not c.get('writein')]
        if len(final_ds) != 1 or len(final_rs) != 1:
            reason = reason or 'nonbinary_final_round'
        if reason:
            audit.append(dict(year=year,race_id=race_id,reason=reason))
            # Retain a single strongest D/R candidate for lag and incumbent lookup,
            # but never fit on these excluded rows.
        ds = sorted(ds,key=lambda c:c.get('votes') or 0,reverse=True)
        rs = sorted(rs,key=lambda c:c.get('votes') or 0,reverse=True)
        d = (final_ds if not reason else ds)
        r = (final_rs if not reason else rs)
        winners = [c for c in final['candidates'] if c.get('winner')]
        row = dict(year=year, race_id=race_id,chamber=chamber,state=state,district=district,
                   seat_class=seat_class, candidate_d=ds[0]['name'] if ds else '',
                   candidate_r=rs[0]['name'] if rs else '',
                   dem_votes=float(d[0].get('votes') or 0) if d else 0.,rep_votes=float(r[0].get('votes') or 0) if r else 0.,
                   winner_name=winners[0]['name'] if len(winners)==1 else '',
                   winner_party=winners[0]['party'] if len(winners)==1 else '',
                   result_date=final['date'], stage=final.get('etype','general'),
                   excluded=reason, source='Election Wrld / MIT Election Data and Science Lab / official returns')
        if not reason and (row['dem_votes'] <= 0 or row['rep_votes'] <= 0):
            row['excluded'] = 'zero_votes'
        if not reason and row['winner_party'] not in ('D','R'):
            row['excluded'] = 'third_party_or_unknown_winner'
        all_races.append(row)

    for path in sorted((ROOT/'data/bootstrap').glob('house_*.json')):
        data = json.loads(path.read_text())
        for race_id, contests in data['races'].items():
            state = race_id[:2]
            if state in ('DC','AS','GU','MP','PR','VI'):
                continue
            race_id = normalize_race(race_id)
            for c in contests:
                add(race_id,'House',state,int(race_id[3:]),'',c,contests)
    for path in sorted((ROOT/'data/bootstrap').glob('senate_*.json')):
        state = path.stem.split('_')[1]
        data = json.loads(path.read_text())
        for key, contests in data.items():
            if not key.startswith('class'):
                continue
            for c in contests:
                add(state+'-SEN-'+key[-1],'Senate',state,'',int(key[-1]),c,contests)
    presidential = []
    source = json.loads((ROOT/'data/bootstrap/president_state.json').read_text())
    for year, states in source.items():
        if year.isdigit() and int(year) <= 2024:
            presidential.extend(dict(year=int(year),state=state,dem_votes=r['dem'],rep_votes=r['rep']) for state,r in states.items())
    return all_races, presidential, audit
