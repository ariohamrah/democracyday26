"""Check delivered artifacts, including score calculations against source odds."""
import csv
import json
import math
import unittest
from collections import Counter, defaultdict
from forecast.io import ROOT
from forecast.roster import APPORTIONMENT


def rows(path):
    with (ROOT/path).open(newline='') as f:
        return list(csv.DictReader(f))


class OutputTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.forecasts = rows('outputs/forecasts.csv')
        cls.candidates = rows('outputs/candidate_forecasts.csv')
        cls.by_race = defaultdict(list)
        for row in cls.candidates:
            cls.by_race[row['race_id']].append(row)

    def test_complete_unique_roster(self):
        self.assertEqual(len(self.forecasts), 470)
        self.assertEqual(len({r['race_id'] for r in self.forecasts}), 470)
        self.assertEqual(Counter(r['chamber'] for r in self.forecasts), {'House':435,'Senate':35})
        self.assertEqual(Counter(r['state'] for r in self.forecasts if r['chamber']=='House'), APPORTIONMENT)
        self.assertEqual(set(self.by_race), {r['race_id'] for r in self.forecasts})
        self.assertEqual(len(rows('outputs/submission.csv')), 470)

    def test_probabilities_and_winners(self):
        for row in self.forecasts:
            candidates = self.by_race[row['race_id']]
            q = [float(c['q']) for c in candidates]
            self.assertTrue(all(math.isfinite(p) and 0 <= p <= 1 for p in q))
            self.assertAlmostEqual(sum(q), 1)
            self.assertAlmostEqual(max(q), float(row['winner_probability']))
            self.assertIn(row['most_likely_winner'], [c['candidate'] for c in candidates if float(c['q']) == max(q)])
            for party, field in [('D','q_democratic'),('R','q_republican'),('I','q_independent'),('O','q_other')]:
                self.assertAlmostEqual(sum(float(c['q']) for c in candidates if c['party']==party), float(row[field]))

    def test_exported_expected_points(self):
        # Candidate artifact carries the imported prices, so this also works
        # after rerunning with an organizer odds file instead of default odds.
        for row in self.forecasts:
            probs, prices = {}, {}
            for c in self.by_race[row['race_id']]:
                key = c['candidate'] if row['scoring_contract_type']=='candidate' else c['party']
                probs[key] = probs.get(key,0.) + float(c['q'])
                p = c['candidate_contract_p'] if row['scoring_contract_type']=='candidate' else c['party_contract_p']
                if p != '': prices[key] = float(p)
            points = {key: probs[key]*-math.log2(p) for key,p in prices.items() if p>0}
            best = row['best_priced_selection']
            if best:
                self.assertIn(best, points)
                self.assertAlmostEqual(float(row['expected_points_best_priced']), points[best])
                self.assertAlmostEqual(points[best], max(points.values()))
            if row['score_maximizing_selection']:
                self.assertEqual(row['score_maximizing_selection'], best)
                self.assertTrue(all(prices.get(k) is not None for k,q in probs.items() if q>0))
                self.assertFalse(any(p==0 for p in prices.values()))

    def test_historical_features_strictly_precede_cycle(self):
        for row in rows('outputs/historical_features.csv'):
            self.assertLess(int(row['prior_pres_year']), int(row['year']))
            if row['lag_year']:
                self.assertLess(int(row['lag_year']), int(row['year']))

    def test_chamber_expected_seat_totals(self):
        report = json.loads((ROOT/'outputs/chamber_forecasts.json').read_text())
        for chamber,total in [('House',435),('Senate',100)]:
            seats = report['chambers'][chamber]['seats']
            self.assertAlmostEqual(sum(r['mean'] for r in seats.values()), total)
        self.assertEqual(len(rows('data/roster/senate_holdovers.csv')), 65)


if __name__=='__main__':
    unittest.main()
