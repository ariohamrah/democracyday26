"""Shared national/regional errors with exact model marginal probabilities."""
from collections import Counter
import numpy as np
from scipy.special import ndtr


REGIONS = {
    **dict.fromkeys('CT ME MA NH RI VT NJ NY PA'.split(), 'Northeast'),
    **dict.fromkeys('IL IN MI OH WI IA KS MN MO NE ND SD'.split(), 'Midwest'),
    **dict.fromkeys('DE FL GA MD NC SC VA DC WV AL KY MS TN AR LA OK TX'.split(), 'South'),
    **dict.fromkeys('AZ CO ID MT NV NM UT WY AK CA HI OR WA'.split(), 'West')}


def simulate(rows, distributions, holdovers, uncertainty, draws=100000, seed=20261102):
    rng = np.random.default_rng(seed)
    national = rng.normal(size=draws)
    regional = {r: rng.normal(size=draws) for r in sorted(set(REGIONS.values()))}
    counts = {c: {p: np.zeros(draws, dtype=int) for p in ('D','R','I','O')} for c in ('House','Senate')}
    for seat in holdovers:
        party = seat['party'] if seat['party'] in counts['Senate'] else 'O'
        counts['Senate'][party] += 1
    independent_dem_holdovers = sum(s['party'] == 'I' and s.get('caucus') == 'D' for s in holdovers)
    for row, distribution in zip(rows, distributions):
        sigma = max(3., float(row.get('sigma', 15)))
        a, b = uncertainty['national_sd']/sigma, uncertainty['regional_sd']/sigma
        if a*a+b*b > .8:
            scale = np.sqrt(.8/(a*a+b*b))
            a, b = a*scale, b*scale
        # Increasing normal variate means more Republican outcomes; D candidates first.
        z = a*national + b*regional[REGIONS[row['state']]] + np.sqrt(1-a*a-b*b)*rng.normal(size=draws)
        u = ndtr(z)
        ordered = sorted(distribution, key=lambda d: ({'D':0,'I':1,'O':2,'R':3}.get(d['party'],2), d['name']))
        cumulative = 0.
        for candidate in ordered:
            next_edge = cumulative + candidate['q']
            chosen = (u >= cumulative) & (u < next_edge + (1e-12 if next_edge > .999999 else 0))
            party = candidate['party'] if candidate['party'] in counts[row['chamber']] else 'O'
            counts[row['chamber']][party] += chosen.astype(int)
            cumulative = next_edge
        if abs(cumulative - 1) > 1e-8:
            raise ValueError('Candidate probabilities must sum to 1')
    result = dict(draws=draws, seed=seed, dependence='Gaussian copula; earlier-cycle fitted national/regional margin-error scales', chambers={})
    for chamber, chamber_counts in counts.items():
        total = 435 if chamber == 'House' else 100
        assert np.all(sum(chamber_counts.values()) == total)
        summary = {p: dict(mean=float(v.mean()), p10=int(np.quantile(v,.1)), p90=int(np.quantile(v,.9))) for p,v in chamber_counts.items()}
        if chamber == 'House':
            control = dict(democratic_majority=float(np.mean(chamber_counts['D'] >= 218)),
                           republican_majority=float(np.mean(chamber_counts['R'] >= 218)))
        else:
            d_known = chamber_counts['D'] + independent_dem_holdovers
            uncertain = chamber_counts['I'] + chamber_counts['O'] - independent_dem_holdovers
            control = dict(democratic_control_if_uncommitted_independents_do_not_join=float(np.mean(d_known >= 51)),
                           democratic_control_if_all_uncommitted_independents_join=float(np.mean(d_known+uncertain >= 51)),
                           republican_control_without_uncommitted_independents=float(np.mean(chamber_counts['R'] >= 50)),
                           note='Republican vice president breaks a 50–50 tie; no assumed caucus for new independent winners.')
        result['chambers'][chamber] = dict(seats=summary, control=control)
    return result
