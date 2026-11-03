"""Candidate-level probabilities, with explicit nonstandard-field assumptions."""
import json
import math
from collections import defaultdict
import numpy as np
from scipy.special import ndtr, ndtri
from .aura import difference, score
from .features import name_key
from .io import ROOT, read_csv
from .polling import load_poll_observations, _date


def party(label):
    label=label.split(',')[0].strip()
    if label.startswith('Democrat'):return 'D'
    if label.startswith('Republican'):return 'R'
    if label in ('Independent','Nonpartisan','By Petition','No Party Affiliation','Unaffiliated','Unenrolled','No Political Party','No Party'):
        return 'I'
    return 'O'


def load_targets():
    groups=defaultdict(list)
    for r in read_csv(ROOT/'data/roster/nominees_audited.csv'):
        r['party']=party(r['party_label'])
        r['incumbent']=r['incumbent']=='true'
        groups[r['race_id']].append(r)
    profiles=json.loads((ROOT/'data/roster/race_profiles.json').read_text())
    targets=[]
    for race_id,candidates in sorted(groups.items()):
        row=candidates[0]
        profile=profiles.get(race_id,{})
        def representative(p):
            cs=[c for c in candidates if c['party']==p]
            if not cs:return ''
            return sorted(cs,key=lambda c:(not c['incumbent'],c['name']))[0]['name']
        a=profile.get('candidate_a') or representative('D')
        b=profile.get('candidate_b') or representative('R')
        lookup={c['name']:c for c in candidates}
        targets.append(dict(year=2026,race_id=race_id,chamber=row['chamber'],state=row['state'],district=row['district'],
                            seat_class=(3 if row['state'] in ('FL','OH') else 2) if row['chamber']=='Senate' else '',
                            special='SPECIAL' in race_id,candidate_d=a,candidate_r=b,
                            incumbent_difference=float(lookup.get(a,{}).get('incumbent',False))-float(lookup.get(b,{}).get('incumbent',False)),
                            open_seat=not any(c['incumbent'] for c in candidates),
                            candidates=candidates,profile=profile,poll_aliases=profile.get('poll_aliases',{}),
                            field_kind=profile.get('kind','standard'),
                            electoral_system=profile.get('electoral_system','majority_runoff' if row['state']=='GA' else 'plurality'),
                            candidate_source=row['source_url']))
    return targets


def three_way_poll_shares(row, names):
    """Only complete current multi-candidate poll questions; no fabricated shares."""
    polls,_=load_poll_observations()
    aliases=row.get('poll_aliases',{})
    keys={name:{name_key(name),*[name_key(x) for x in aliases.get(name,[])]} for name in names}
    selected={}
    for p in polls:
        geography=row['race_id'] if row['chamber']=='House' else row['state']
        if p['year']!=2026 or p['kind']!=row['chamber'] or p['geography']!=geography or 'results' not in p:continue
        age=(_date('2026-11-02')-_date(p['date'])).days
        if not 0<=age<=45 or p['available_date']>'2026-11-02':continue
        values={}
        for name in names:
            matches=[r['pct'] for r in p['results'] if name_key(r.get('candidate','')) in keys[name]]
            if len(matches)==1:values[name]=float(matches[0])
        if len(values)!=len(names):continue
        key=(p['pollster'],p['date'])
        selected[key]=(values,math.exp(-age/21)*math.sqrt(min(p['sample_size'] or 600,2000)/600))
    if not selected:return None,0
    denom=sum(w for v,w in selected.values())
    shares={n:sum(v[n]*w for v,w in selected.values())/denom for n in names}
    return shares,len(selected)


def distribution(row, q, mu, sigma, info, priors):
    candidates=row['candidates']
    names=[c['name'] for c in candidates]
    a,b=row['candidate_d'],row['candidate_r']
    kind=row['field_kind']
    probs={name:0. for name in names}
    notes=[]
    aura_coefficient=info['coefficients'].get('aura_difference',0.)
    if len(candidates)==1:
        probs[names[0]]=1.
        notes.append('Conditional on certified printed ballot; write-in/qualification contingencies not modeled.')
    elif kind=='same_party_top_two':
        ia=next(c['incumbent'] for c in candidates if c['name']==a)
        ib=next(c['incumbent'] for c in candidates if c['name']==b)
        prior=priors['same_party_incumbent']['probability'] if ia and not ib else (1-priors['same_party_incumbent']['probability'] if ib and not ia else .5)
        center=ndtri(prior)*sigma+aura_coefficient*difference(a,b)[0]
        if row.get('poll_present'):
            weight=min(1.,max(0.,info['coefficients'].get('poll_residual',0.)))
            center=(1-weight)*center+weight*row['poll_margin']
        probs[a]=float(ndtr(center/sigma));probs[b]=1-probs[a]
        notes.append('Same-party incumbent prior fitted separately; aura/poll transfer from D-R model is an unvalidated extrapolation.')
    elif kind=='no_republican_nominee':
        hazard=priors['minor_with_one_major']['probability']
        probs[a]=1-hazard
        others=[n for n in names if n!=a]
        for n in others:probs[n]=hazard/len(others)
        notes.append('Single-major-party field uses empirical minor-candidate win prior.')
    elif kind=='three_way_competitive':
        major_names=[a,b]+[c['name'] for c in candidates if c['party']=='D' and c['name'] not in (a,b)]
        shares,n=three_way_poll_shares(row,major_names)
        if shares:
            vals=np.array([shares[n] for n in major_names]);vals=100*vals/vals.sum()
            rng=np.random.default_rng(20261102)
            simulations=vals+rng.normal(0,sigma/math.sqrt(2),size=(100000,len(vals)))
            wins=np.bincount(simulations.argmax(axis=1),minlength=len(vals))/len(simulations)
            rest=[n for n in names if n not in major_names]
            hazard=priors['minor_with_both_major']['probability'] if rest else 0.
            for name,p in zip(major_names,wins):probs[name]=float(p)*(1-hazard)
            for name in rest:probs[name]=hazard/len(rest)
            notes.append(f'Three-way vote-share simulation using {n} complete polls; transferred margin error, not separately validated.')
        else:
            # Unknown split is explicitly uncertain, not silently negligible.
            rest=[name for name in names if name not in major_names]
            hazard=priors['minor_with_both_major']['probability'] if rest else 0.
            probs[b]=(1-q)*(1-hazard)
            for name in major_names:
                if name!=b:probs[name]=q*(1-hazard)/(len(major_names)-1)
            for name in rest:probs[name]=hazard/len(rest)
            notes.append('No complete three-way poll: non-Republican probability split equally; substantial candidate-level uncertainty.')
    elif row['state']=='LA' and row['chamber']=='House':
        groups={p:[c for c in candidates if c['party']==p] for p in ('D','R','I','O')}
        minor=groups['I']+groups['O'];hazard=priors['minor_with_both_major']['probability'] if minor else 0.
        for p,mass in (('D',q*(1-hazard)),('R',(1-q)*(1-hazard))):
            group=groups[p]
            if not group:continue
            incumbents=[c for c in group if c['incumbent']]
            if len(group)>1 and len(incumbents)==1:
                win=priors['same_party_incumbent']['probability']
                for c in group:probs[c['name']]=mass*(win if c['incumbent'] else (1-win)/(len(group)-1))
            else:
                for c in group:probs[c['name']]=mass/len(group)
        for c in minor:probs[c['name']]=hazard/len(minor)
        notes.append('Eventual runoff winner: party probability split by empirical incumbent prior, otherwise equally; no ballot-transfer/advancement model.')
    else:
        q=float(np.clip(q,1e-8,1-1e-8))
        rest=[n for n in names if n not in (a,b)]
        hazard=priors['minor_with_both_major']['probability'] if rest else 0.
        if a not in probs or b not in probs:raise ValueError(f'Missing modeled nominees for {row["race_id"]}')
        probs[a]=q*(1-hazard);probs[b]=(1-q)*(1-hazard)
        for n in rest:probs[n]=hazard/len(rest)
        if kind in ('independent_principal_challenger','independent_incumbent'):
            notes.append('Independent principal side borrows D-R fundamentals; candidate identity and party probabilities remain separate; caucus unknown.')
        if row['electoral_system'] in ('ranked_choice','majority_runoff'):
            notes.append('Eventual winner approximation; no separately fitted transfer/turnout model for later rounds.')
    total=sum(probs.values())
    if abs(total-1)>1e-8:raise ValueError(f'Probabilities sum to {total}: {row["race_id"]}')
    return [dict(name=c['name'],party=c['party'],party_label=c['party_label'],q=probs[c['name']],
                 aura=score(c['name']),incumbent=c['incumbent']) for c in candidates],'; '.join(notes)
