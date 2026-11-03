"""Feature construction from historical race rows and known pre-election inputs."""
import re
import unicodedata
from .aura import difference
from .geography import baseline_for, changed_map, district_baselines, normalize_race
from .simulate import REGIONS


def name_key(name):
    name = unicodedata.normalize('NFKD', str(name)).encode('ascii','ignore').decode().lower()
    parts = re.findall('[a-z]+', name)
    parts = [p for p in parts if p not in ('jr','sr','iii','ii','iv')]
    return ' '.join([parts[0],parts[-1]]) if len(parts) > 1 else ' '.join(parts)


def incumbent_difference(race, previous):
    if 'incumbent_difference' in race and race['incumbent_difference'] is not None:
        return float(race['incumbent_difference'])
    if not previous:
        return 0.
    winner = previous.get('winner_name', '')
    if not winner:
        winner = previous['candidate_d'] if previous['dem_votes'] > previous['rep_votes'] else previous['candidate_r']
    key = name_key(winner)
    if not key:
        return 0.
    return float(name_key(race.get('candidate_d','')) == key) - float(name_key(race.get('candidate_r','')) == key)


def president_party(year):
    return -1 if year in (2006,2008,2018,2020,2026) else 1


def build_features(history, targets, presidential):
    """Inputs: one row per historical final contest, D/R vote totals; target rows.

    Congressional lag is only used if district lines can be compared. For Senate,
    a state's most recent earlier contest supplies shared partisan information;
    incumbency is matched to the same seat class separately.
    """
    baselines = district_baselines()
    output = []
    for race in targets:
        year, state, chamber = int(race['year']), race['state'], race['chamber']
        earlier = [r for r in history if int(r['year']) < year and r['state'] == state and r['chamber'] == chamber]
        if chamber == 'House':
            earlier = [r for r in earlier if r['race_id'] == race['race_id']]
        # Nonstandard fields (independent winners, same-party top-two, RCV
        # first rounds) cannot supply a comparable Democratic/Republican lag.
        # Keep them in the separate seat history for incumbent identification.
        # House lags must be adjacent cycles so skipped races cannot silently
        # reach across an intervening redistricting.
        lag_earlier = [r for r in earlier if not r.get('excluded')
                       and year - int(r['year']) <= (2 if chamber == 'House' else 6)]
        previous = max(lag_earlier, key=lambda r: int(r['year'])) if lag_earlier else None
        same_seat = [r for r in earlier if str(r.get('seat_class','')) == str(race.get('seat_class',''))]
        previous_seat = max(same_seat, key=lambda r: int(r['year'])) if same_seat else previous
        local_pres, pres_year = baseline_for(race['race_id'], year, baselines) if chamber == 'House' else (None, None)
        if local_pres is None:
            state_pres = [r for r in presidential if r['state'] == state and int(r['year']) < year]
            if not state_pres:
                raise ValueError(f'No prior presidential data for {state}/{year}')
            latest = max(state_pres, key=lambda r: int(r['year']))
            d, r = float(latest['dem_votes']), float(latest['rep_votes'])
            local_pres, pres_year = 100*(d-r)/(d+r), int(latest['year'])
            pres_level = 'state'
        else:
            pres_level = 'district_on_target_map'
        assert pres_year < year
        lag_ok = previous is not None and not (chamber == 'House' and changed_map(state, year))
        if lag_ok:
            d, r = previous['dem_votes'], previous['rep_votes']
            # An unopposed race does not provide a useful estimate of partisan lean.
            lag_ok = min(d,r) > 0 and (d+r) > 0
        lag = 100*(d-r)/(d+r) if lag_ok else local_pres
        aura, missing = difference(race.get('candidate_d',''), race.get('candidate_r',''))
        result = dict(race)
        result.update(lag_margin=lag, prior_pres_margin=local_pres,
                      incumbent_difference=incumbent_difference(race, previous_seat),
                      midterm_president=president_party(year) if year % 4 == 2 else 0,
                      senate=float(chamber == 'Senate'), lag_missing=float(not lag_ok),
                      aura_difference=aura, aura_missing=float(missing),
                      prior_pres_year=pres_year, pres_geography=pres_level,
                      region=REGIONS[state], lag_year=int(previous['year']) if lag_ok else '',
                      boundary_changed=chamber == 'House' and changed_map(state,year))
        if 'dem_votes' in race:
            d, r = race['dem_votes'], race['rep_votes']
            result['margin'] = 100*(d-r)/(d+r)
        output.append(result)
    return output
