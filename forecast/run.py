"""Run offline: python3 -m forecast.run [--odds organizer.csv]."""
import argparse
import json
from collections import Counter, defaultdict
import numpy as np
from .aura import score
from .data import load_history
from .features import build_features
from .field_priors import estimate_field_priors
from .fields import load_targets, distribution
from .io import ROOT,CUTOFF,write_csv,read_csv,manifest
from .model import BASE_FEATURES,FULL_FEATURES,backtest,metrics,train_predict
from .odds import load_odds,FIELDS
from .polling import attach_poll_features,load_poll_observations
from .roster import validate_roster
from .scoring import expected_points,market_benchmark
from .simulate import simulate


def summarize(predictions):
    result={}
    groups={'all':predictions,'competitive':[r for r in predictions if r['competitive']],
            'unpolled_or_archive_missing':[r for r in predictions if not r['poll_present']],
            'polled':[r for r in predictions if r['poll_present']]}
    groups.update({c:[r for r in predictions if r['chamber']==c] for c in ('House','Senate')})
    groups.update({str(y):[r for r in predictions if r['year']==y] for y in sorted({r['year'] for r in predictions})})
    for key,rows in groups.items():result[key]=metrics([r['outcome'] for r in rows],[r['q'] for r in rows])
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--odds',type=str,default=str(ROOT/'data/odds/organizer_odds.csv'))
    parser.add_argument('--draws',type=int,default=100000)
    args=parser.parse_args()
    out=ROOT/'outputs';out.mkdir(exist_ok=True)
    history,presidential,excluded=load_history()
    eligible=[r for r in history if int(r['year'])>=2006 and not r['excluded']]
    training=build_features(history,eligible,presidential)
    training,poll_history_metadata=attach_poll_features(training)
    raw_targets=load_targets()
    holdovers=read_csv(ROOT/'data/roster/senate_holdovers.csv')
    validate_roster(raw_targets,holdovers)
    targets=build_features(history,raw_targets,presidential)
    targets,poll_current_metadata=attach_poll_features(targets)
    priors=estimate_field_priors()
    variants={'full':FULL_FEATURES,'without_aura':[f for f in FULL_FEATURES if not f.startswith('aura_')],
              'without_local_polls':[f for f in FULL_FEATURES if f not in ('poll_residual','poll_present')],
              'without_generic_ballot':[f for f in FULL_FEATURES if not f.startswith('generic_')],
              'fundamentals_only':BASE_FEATURES}
    validation={};all_backtests=[]
    for name,features in variants.items():
        bt=backtest(training,features)
        validation[name]=summarize(bt)
        all_backtests.extend(dict(variant=name,**r) for r in bt)
        print(name,{k:v for k,v in validation[name]['all'].items() if k!='calibration'},flush=True)
    q,mu,sigma,info=train_predict(training,targets,FULL_FEATURES)
    distributions=[];notes=[]
    for row,p,center,sd in zip(targets,q,mu,sigma):
        row['sigma']=float(sd)
        d,n=distribution(row,float(p),float(center),float(sd),info,priors)
        distributions.append(d);notes.append(n)
    valid={r['race_id']:set(['D','R','I','O']+[c['name'] for c in d]) for r,d in zip(targets,distributions)}
    prices,price_meta=load_odds(args.odds,valid)
    detailed=[];candidate_rows=[];template=[]
    for row,dist,center,sd,p_pair,note in zip(targets,distributions,mu,sigma,q,notes):
        race=row['race_id'];party_probs={p:sum(c['q'] for c in dist if c['party']==p) for p in ('D','R','I','O')}
        winner=max(dist,key=lambda c:c['q'])
        imported=prices.get(race,{})
        kinds={price_meta[race,k]['contract_type'] for k in imported}
        if len(kinds)>1:raise ValueError(f'Mixed party and candidate contract types for {race}; use separate imports')
        contract_type=next(iter(kinds)) if kinds else ('candidate' if row['field_kind']=='same_party_top_two' else 'party')
        probs=party_probs if contract_type=='party' else {c['name']:c['q'] for c in dist}
        # Do not score a candidate contract using a party label, or vice versa.
        for outcome in imported:
            if outcome not in probs:raise ValueError(f'Contract definition mismatch: {race}/{outcome}')
        points={k:expected_points(probs[k],p) for k,p in imported.items() if p is not None}
        known={k:v for k,v in points.items() if v is not None}
        best=max(known,key=known.get) if known else ''
        missing=[k for k,v in probs.items() if v>0 and imported.get(k) is None]
        zero=any(p==0 for p in imported.values())
        complete=bool(best) and not missing and not zero
        provisional=any(m['status']=='provisional_reconstruction' for (r,k),m in price_meta.items() if r==race)
        status=('zero_price_requires_organizer_rule' if zero else 'missing_prices' if not best else
                'provisional_complete' if complete and provisional else 'complete' if complete else 'best_among_priced_outcomes_only')
        d=dict(race_id=race,chamber=row['chamber'],state=row['state'],district=row['district'],special=row['special'],
               most_likely_winner=winner['name'],most_likely_winner_party=winner['party'],winner_probability=winner['q'],
               q_democratic=party_probs['D'],q_republican=party_probs['R'],q_independent=party_probs['I'],q_other=party_probs['O'],
               modeled_candidate_a=row['candidate_d'],modeled_candidate_b=row['candidate_r'],q_candidate_a_conditional_pair=float(p_pair),
               modeled_pair_margin=float(center),margin_error_sd=float(sd),
               p_democratic=imported.get('D'),p_republican=imported.get('R'),
               scoring_contract_type=contract_type,score_maximizing_selection=best if complete else '',
               best_priced_selection=best,expected_points_best_priced=known.get(best),
               market_trusting_benchmark=market_benchmark({k:v for k,v in imported.items() if v is not None}) or '',
               scoring_status=status,prices_provisional=provisional,missing_price_outcomes=';'.join(missing),
               local_poll_count=row['poll_count'],generic_poll_count=row['generic_poll_count'],generic_margin=row['generic_margin'],
               poll_margin=row['poll_margin'] if row['poll_present'] else '',
               aura_candidate_a=score(row['candidate_d']),aura_candidate_b=score(row['candidate_r']),aura_difference=row['aura_difference'],
               open_seat=row['open_seat'],field_kind=row['field_kind'],electoral_system=row['electoral_system'],
               baseline_presidential_year=row['prior_pres_year'],presidential_margin=row['prior_pres_margin'],
               baseline_geography=row['pres_geography'],old_congressional_lag_suppressed=bool(row['lag_missing']),
               candidate_source=row['candidate_source'],poll_ids=row['poll_ids'],limitations=note,forecast_cutoff=CUTOFF)
        detailed.append(d)
        for c in dist:
            candidate_rows.append(dict(race_id=race,chamber=row['chamber'],candidate=c['name'],party=c['party'],ballot_party=c['party_label'],
                                       q=c['q'],name_aura=c['aura'],incumbent=c['incumbent'],
                                       candidate_contract_p=imported.get(c['name']) if contract_type=='candidate' else '',
                                       party_contract_p=imported.get(c['party']) if contract_type=='party' else '',
                                       note='Party price is not a candidate price; do not interchange.',forecast_cutoff=CUTOFF))
        for outcome,value in probs.items():
            if value<=0:continue
            blank=dict.fromkeys(FIELDS,'');blank.update(race_id=race,outcome=outcome,contract_type=contract_type,status='missing')
            template.append(blank)
    from .submission import format_submission, HEADERS
    write_csv(out/'submission.csv',format_submission(detailed),HEADERS)
    write_csv(out/'forecasts.csv',detailed)
    write_csv(out/'candidate_forecasts.csv',candidate_rows)
    write_csv(out/'organizer_odds_template.csv',template,FIELDS)
    write_csv(out/'historical_backtests.csv',all_backtests)
    feature_columns=['year','race_id','chamber','candidate_d','candidate_r','margin','prior_pres_year','pres_geography','lag_year']+FULL_FEATURES+['poll_count','generic_poll_count','poll_ids']
    write_csv(out/'historical_features.csv',[{k:r.get(k,'') for k in feature_columns} for r in training],feature_columns)
    write_csv(out/'historical_exclusions.csv',excluded,['year','race_id','reason'])
    chamber=simulate(targets,distributions,holdovers,info['uncertainty'],args.draws)
    coverage=dict(house_races=435,senate_races=35,senate_holdovers=len(holdovers),nominees=len(candidate_rows),
                  training_rows=len(training),training_cycles=sorted({r['year'] for r in training}),
                  current_locally_polled=sum(bool(r['poll_present']) for r in targets),
                  current_generic_poll_count=targets[0]['generic_poll_count'],
                  current_generic_margin=targets[0]['generic_margin'],
                  district_geographic_baselines=sum(r['pres_geography']=='district_on_target_map' for r in targets),
                  races_with_some_priced_outcomes=sum(bool(r['best_priced_selection']) for r in detailed),
                  races_with_complete_scoring_prices=sum(bool(r['score_maximizing_selection']) for r in detailed),
                  scoring_status_counts=dict(Counter(r['scoring_status'] for r in detailed)),
                  field_counts=dict(Counter(r['field_kind'] for r in targets)),
                  historical_exclusions=dict(Counter(r['excluded'] for r in history if r['excluded'])))
    report=dict(cutoff=CUTOFF,coverage=coverage,metrics=validation,
                aura_brier_delta_full_minus_without=validation['full']['all']['brier']-validation['without_aura']['all']['brier'],
                polling_history=poll_history_metadata,polling_current=poll_current_metadata,
                historical_contest_points=None,contest_points_reason='No genuine matching historical competition price snapshots recovered.',
                training_origin_caveat='Historical poll publication dates proxied by median field date plus three days. Historical nominee/geography snapshots reconstructed retrospectively.',
                calibrated_population='Regular, binary D/R races only; field adjustments are not part of the reported backtest.')
    for name,data in [('validation.json',report),('model.json',dict(cutoff=CUTOFF,features=FULL_FEATURES,fit=info,field_priors=priors)),('chamber_forecasts.json',chamber)]:
        (out/name).write_text(json.dumps(data,indent=2,allow_nan=False)+'\n')
    manifest()
    from .report import write_report
    write_report(report,info,chamber)
    print(json.dumps(coverage,indent=2))


if __name__=='__main__':main()
