"""Empirical, smoothed base rates for fields outside the binary margin model.

These are descriptive historical base rates, not validated candidate-specific
forecasts. Named independent candidates can be very unlike this pooled average.
"""
import json
from collections import Counter
from .io import ROOT
from .features import name_key
from .geography import normalize_race


def estimate_field_priors(cutoff_year=2024):
    """Use only regular general election contests in 2006..cutoff_year.

    Historical winners from 2004 onward identify incumbents. Runoff outcomes are
    followed when linked by decidedBy. First-choice RCV fields remain eligible
    only if an explicit final winner flag exists, because this estimates winner
    frequencies rather than vote margins. Excludes unresolved/unknown winners.
    """
    if cutoff_year > 2024:
        raise ValueError('Field priors must exclude post-2024 elections')
    series = {}
    for path in sorted((ROOT/'data/bootstrap').glob('house_*.json')):
        data = json.loads(path.read_text())
        for race_id, contests in data['races'].items():
            if race_id[:2] not in ('DC','AS','GU','MP','PR','VI'):
                series.setdefault(normalize_race(race_id), []).extend(contests)
    for path in sorted((ROOT/'data/bootstrap').glob('senate_*.json')):
        data = json.loads(path.read_text())
        for seat, contests in data.items():
            if seat.startswith('class'):
                series[path.stem.split('_')[1]+'-SEN-'+seat[-1]] = contests
    counts = {key: [0, 0] for key in ('minor_with_both_major', 'minor_with_one_major',
                                      'same_party_incumbent')}
    examples = {key: [] for key in counts}
    exclusions = Counter()
    aggregate_names = {'others', 'other', 'scattering', 'write-ins', 'writein',
                       'write in', 'write-ins (scattered)', 'none of these candidates'}
    for seat, contests in series.items():
        ordered = sorted((c for c in contests if 2004 <= int(c['year']) <= cutoff_year),
                         key=lambda c: c.get('date') or str(c['year'])+'-11-01')
        for contest in ordered:
            year = int(contest['year'])
            if year < 2006 or contest.get('special') or contest.get('runoff'):
                continue
            final = contest
            if contest.get('decidedBy'):
                matches = [c for c in ordered if c.get('date') == contest['decidedBy']]
                if not matches:
                    exclusions['missing_runoff_final'] += 1
                    continue
                final = matches[0]
            candidates = [c for c in contest['candidates'] if not c.get('writein')
                          and c['name'].strip().lower() not in aggregate_names]
            winners = [c for c in final['candidates'] if c.get('winner')]
            if len(winners) != 1:
                exclusions['no_unique_winner'] += 1
                continue
            winner = winners[0]
            parties = {c.get('party') for c in candidates}
            major_count = len(parties & {'D', 'R'})
            minor = [c for c in candidates if c.get('party') not in ('D', 'R')]
            key = None
            success = False
            if minor and major_count:
                key = 'minor_with_both_major' if major_count == 2 else 'minor_with_one_major'
                success = winner.get('party') not in ('D', 'R')
            elif len(candidates) == 2 and len(parties) == 1 and major_count == 1:
                earlier = [c for c in ordered if (c.get('date') or str(c['year'])+'-11-01') < (contest.get('date') or str(contest['year'])+'-11-01')]
                previous_winners = [w for c in earlier[-1:] for w in c['candidates'] if w.get('winner')]
                if len(previous_winners) != 1:
                    exclusions['same_party_no_prior_winner'] += 1
                    continue
                prior_key = name_key(previous_winners[0]['name'])
                incumbent = [c for c in candidates if name_key(c['name']) == prior_key]
                if len(incumbent) != 1:
                    exclusions['same_party_no_identified_incumbent'] += 1
                    continue
                key = 'same_party_incumbent'
                success = name_key(winner['name']) == prior_key
            if key:
                counts[key][0] += int(success)
                counts[key][1] += 1
                if success:
                    examples[key].append({'year': year, 'race_id': seat, 'winner': winner['name']})
    output = {}
    for key, (wins, total) in counts.items():
        output[key] = dict(probability=(wins+.5)/(total+1), successes=wins, trials=total,
                           smoothing='Jeffreys Beta(0.5,0.5)', success_examples=examples[key])
    output['metadata'] = dict(years=[2006,cutoff_year], source='Saved Election Wrld / MIT / official result snapshots',
                              excludes=dict(exclusions), limitations=[
                                  'Pooled historical frequencies are not individually validated candidate probabilities.',
                                  'Incumbency inferred from earlier winner misses appointments and district movers.',
                                  'Minor-candidate strength and endorsement differences are not modeled.',
                                  'Write-ins and aggregate Other rows excluded.'])
    return output
