"""As-of polling features; no election-result or retrospective-rating columns read.

Historical archive lacks publication dates: a three-day median-field-date lag is
an availability safeguard, not a claim of exact real-time reconstruction.
"""
import csv
import json
import math
from collections import Counter, defaultdict
from datetime import date, timedelta
from functools import lru_cache
from .features import name_key
from .geography import normalize_race
from .io import ROOT, CUTOFF


def election_day(year):
    first = date(year, 11, 1)
    return first + timedelta(days=(0-first.weekday()) % 7 + 1)


def _date(value):
    return date.fromisoformat(str(value)[:10])


def _number(value):
    try:
        n = float(value)
        return n if math.isfinite(n) else None
    except (TypeError, ValueError):
        return None


def _district(value):
    parts = str(value).upper().split('-')
    if len(parts) != 2:
        return str(value)
    try:
        return normalize_race(parts[0] + '-' + str(int(parts[1])).zfill(2))
    except ValueError:
        return normalize_race(str(value))


def _party(value):
    return {'DEM':'D','Democratic':'D','Democrat':'D','REP':'R','Republican':'R'}.get(value, value)


@lru_cache(maxsize=1)
def load_poll_observations():
    """Return normalized source observations with source metadata retained."""
    obs, rejected = [], Counter()
    path = ROOT / 'data/signals/historical_raw_polls.csv'
    if path.exists():
        with path.open(newline='', encoding='utf-8-sig') as f:
            for r in csv.DictReader(f):
                kind = r['type_simple']
                if kind not in ('House-G', 'Sen-G', 'House-G-US'):
                    continue
                year = int(r['cycle'])
                if year > 2024 or year < 2004:
                    continue
                parties = (_party(r['cand1_party']), _party(r['cand2_party']))
                if set(parties) != {'D','R'}:
                    rejected['historical_nonbinary_party'] += 1
                    continue
                try:
                    end, election = _date(r['polldate']), _date(r['electiondate'])
                except ValueError:
                    rejected['historical_invalid_date'] += 1
                    continue
                # Avoid primary, special and later runoff polls entering November forecast.
                if election != election_day(year):
                    rejected['historical_other_election_date'] += 1
                    continue
                a,b = _number(r['cand1_pct']),_number(r['cand2_pct'])
                if a is None or b is None or a+b <= 0:
                    continue
                d,rep = (a,b) if parties[0]=='D' else (b,a)
                dn,rn = (r['cand1_name'],r['cand2_name']) if parties[0]=='D' else (r['cand2_name'],r['cand1_name'])
                obs.append(dict(year=year,kind='generic' if kind=='House-G-US' else ('House' if kind=='House-G' else 'Senate'),
                    geography=_district(r['location']) if kind=='House-G' else r['location'],
                    date=end.isoformat(),available_date=(end+timedelta(days=3)).isoformat(),
                    availability='median_field_date_plus_3_days_proxy',poll_id=r['poll_id'],
                    pollster=r['pollster'],sample_size=_number(r['samplesize']),population='',
                    sponsor=r['partisan'],partisan=r['partisan'] not in ('','NA'),
                    candidate_d=dn,candidate_r=rn,dem_percent=d,rep_percent=rep,
                    source_url='https://github.com/fivethirtyeight/data/blob/master/pollster-ratings/raw_polls.csv'))
    path = ROOT / 'data/signals/polls_2026.json'
    if path.exists():
        for r in json.loads(path.read_text()):
            if r['office'] not in ('generic-ballot','house','senate'):
                continue
            try:
                end = _date(r['end'])
                available = max(end, _date(r['added']))
            except (ValueError, TypeError, KeyError):
                rejected['current_missing_availability_date'] += 1
                continue
            if r.get('dates_backwards') or _date(r['start']) > end:
                rejected['current_invalid_date'] += 1
                continue
            obs.append(dict(year=2026,kind={'generic-ballot':'generic','house':'House','senate':'Senate'}[r['office']],
                geography=_district(r.get('district')) if r['office']=='house' else (r.get('state') or 'US'),
                date=end.isoformat(),available_date=available.isoformat(),availability='aggregator_added_date',
                poll_id=r['id'],pollster=r['pollster'],sample_size=_number(r.get('n')),population=r.get('population') or '',
                sponsor='; '.join(r.get('sponsors') or []),partisan=bool(r.get('internal') or r.get('partisan')),
                results=r['results'],source_url=r.get('source_url') or ''))
    return obs, dict(rejected)


def _match_values(poll, row, generic=False):
    if 'results' not in poll:
        if not generic and (name_key(poll['candidate_d']) != name_key(row.get('candidate_d','')) or
                            name_key(poll['candidate_r']) != name_key(row.get('candidate_r',''))):
            return None
        return poll['dem_percent'], poll['rep_percent']
    if generic:
        ds=[x for x in poll['results'] if _party(x.get('party'))=='D' or x.get('candidate') in ('Dem','Democrat','Democrats')]
        rs=[x for x in poll['results'] if _party(x.get('party'))=='R' or x.get('candidate') in ('Rep','Republican','Republicans')]
    else:
        dn,rn=row.get('candidate_d',''),row.get('candidate_r','')
        if not name_key(dn) or not name_key(rn):
            return None
        aliases=row.get('poll_aliases') or {}
        dk={name_key(n) for n in [dn]+aliases.get(dn,[])}
        rk={name_key(n) for n in [rn]+aliases.get(rn,[])}
        if dk & rk:
            return None  # ambiguous aliases must never merge distinct candidates
        ds=[x for x in poll['results'] if name_key(x.get('candidate','')) in dk]
        rs=[x for x in poll['results'] if name_key(x.get('candidate','')) in rk]
    if len(ds)!=1 or len(rs)!=1:
        return None
    d,r=_number(ds[0]['pct']),_number(rs[0]['pct'])
    if d is None or r is None or not (0<=d<=100 and 0<=r<=100) or d+r<=0:
        return None
    return d,r


def aggregate(polls, row, cutoff, generic=False):
    selected={}
    for p in polls:
        age=(cutoff-_date(p['date'])).days
        if not 0<=age<=(30 if generic else 45) or _date(p['available_date'])>cutoff:
            continue
        values=_match_values(p,row,generic)
        if values is None:
            continue
        # One question/population per firm and field date; prefer LV, then RV.
        key=(p['pollster'].lower().strip(),p['date'])
        priority=({'lv':3,'rv':2,'a':1}.get(p['population'].lower(),0),p['sample_size'] or 0,p['poll_id'])
        if key not in selected or priority>selected[key][0]:
            selected[key]=(priority,p,values,age)
    weighted=[]
    for _,p,(d,r),age in selected.values():
        n=p['sample_size'] or 600
        weight=math.sqrt(min(max(n,100),2000)/600)*math.exp(-age/21)
        if p['partisan']:
            weight*=0.5
        margin=d-r if generic else 100*(d-r)/(d+r)
        weighted.append((weight,margin))
    margin=sum(w*m for w,m in weighted)/sum(w for w,_ in weighted) if weighted else 0.
    return margin,len(weighted),[p['poll_id'] for _,p,_,_ in selected.values()]


def attach_poll_features(rows):
    """Return copied feature rows plus audit metadata; missing margins are zero.

    Adds generic_margin/generic_present, poll_margin/poll_present,
    poll_residual (local two-party margin minus prior presidential margin),
    poll_count and generic_poll_count. Always use presence flags with margins.
    """
    observations,rejected=load_poll_observations()
    index=defaultdict(list)
    for p in observations:
        index[(p['year'],p['kind'],p['geography'])].append(p)
    output=[]
    coverage=defaultdict(lambda:Counter())
    for row in rows:
        year=int(row['year'])
        cutoff=_date(CUTOFF) if year==2026 else election_day(year)-timedelta(days=1)
        g,gn,gids=aggregate(index[(year,'generic','US')],row,cutoff,True)
        geography=_district(row['race_id']) if row['chamber']=='House' else row['state']
        p,pn,pids=aggregate(index[(year,row['chamber'],geography)],row,cutoff)
        new=dict(row)
        new.update(generic_margin=g,generic_present=float(gn>0),poll_margin=p,poll_present=float(pn>0),
                   poll_residual=p-float(row['prior_pres_margin']) if pn else 0.,poll_count=pn,generic_poll_count=gn,
                   poll_ids=';'.join(pids),generic_poll_ids=';'.join(gids))
        output.append(new)
        coverage[str(year)]['races']+=1
        coverage[str(year)]['locally_polled']+=int(pn>0)
        coverage[str(year)]['generic_covered']+=int(gn>0)
    metadata=dict(source_observations=len(observations),rejected=rejected,
                  coverage={k:dict(v) for k,v in coverage.items()},
                  historical_availability='Median field date plus 3 days is a proxy, not exact publication reconstruction.',
                  current_availability='Aggregator added date and field-end date both must precede cutoff; date-level precision.',
                  aggregation='45-day local / 30-day generic; exponential age scale21days; sqrt sample size capped2000; partisan half-weight; dedup firm/fielddate preferringLV.',
                  unavailable_cycle='Historical poll archive ends2022; 2024 polling intentionally missing.')
    return output,metadata
