import math
import tempfile
import unittest
from pathlib import Path
from forecast.aura import score, components, difference
from forecast.io import assert_cutoff, write_csv
from forecast.odds import load_odds, FIELDS
from forecast.scoring import choose, expected_points, market_benchmark
from forecast.geography import baseline_for, changed_map, district_baselines
from forecast.roster import APPORTIONMENT, CLASS_2


class ScoringTests(unittest.TestCase):
    def test_q_separate_from_p(self):
        likely, pick, points, status = choose({'A': .7, 'B': .3}, {'A': .9, 'B': .1})
        self.assertEqual(likely, 'A')
        self.assertEqual(pick, 'B')
        self.assertAlmostEqual(points['B'], .3 * math.log2(10))

    def test_market_underdog(self):
        for p in (.01, .1, .25, .49):
            self.assertEqual(market_benchmark({'A': p, 'B': 1-p}), 'A')

    def test_missing_and_endpoints(self):
        self.assertEqual(choose({'A': .5, 'B': .5}, {'A': .2})[3], 'missing_prices')
        self.assertIsNone(expected_points(.2, 0))
        self.assertEqual(expected_points(.2, 1), 0)
        self.assertEqual(choose({'A': .9, 'B': .1}, {'A': 1, 'B': 0})[3], 'zero_price_requires_organizer_rule')

    def test_bad_q(self):
        with self.assertRaises(ValueError):
            choose({'A': .8, 'B': .8}, {})


class FeatureTests(unittest.TestCase):
    def test_roster_constants(self):
        self.assertEqual(sum(APPORTIONMENT.values()), 435)
        self.assertEqual(len(CLASS_2), 33)

    def test_no_simultaneous_president_results(self):
        values = {(2024,2024,'CA-01'): 99., (2024,2020,'CA-01'): -20.}
        self.assertEqual(baseline_for('CA-01',2024,values), (-20.,2020))
        self.assertTrue(changed_map('TX',2026))
        self.assertFalse(changed_map('MO',2026))

    def test_current_geography_complete(self):
        b = district_baselines()
        self.assertEqual(sum(k[0] == 2026 and k[1] == 2024 for k in b), 435)
        # CA-01 changed from Republican to Democratic presidential territory.
        self.assertGreater(b[2026,2024,'CA-01'], 0)
        self.assertLess(b[2024,2024,'CA-01'], 0)

    def test_name_only(self):
        self.assertEqual(score('Ada Smith'), score('ADA SMITH'))
        self.assertEqual(components('Ada Adams')['alliteration'], 1)
        self.assertIsNone(score(''))
        self.assertEqual(difference('', 'Ada Smith'), (0., True))
        self.assertTrue(0 <= score('Alexandria Ocasio-Cortez') <= 1)

    def test_cutoff(self):
        assert_cutoff('2026-11-02T23:00:00-05:00')
        with self.assertRaises(ValueError):
            assert_cutoff('2026-11-03T12:00:00Z')
        with self.assertRaises(ValueError):
            assert_cutoff('2026-11-02')

    def test_odds_date_and_contract(self):
        row = dict.fromkeys(FIELDS, '')
        row.update(race_id='TX-SEN', outcome='D', contract_type='party', probability='.3',
                   snapshot_at='2026-11-01T12:00:00-05:00', snapshot_timezone='America/New_York',
                   price_definition='organizer_probability', source_url='https://example.org/odds', status='organizer_exact')
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'odds.csv'
            write_csv(path, [row])
            prices, _ = load_odds(path, {'TX-SEN': ['D','R']})
            self.assertEqual(prices['TX-SEN']['D'], .3)
            row['snapshot_at'] = '2026-11-02T12:00:00-05:00'
            write_csv(path, [row])
            with self.assertRaises(ValueError):
                load_odds(path, {'TX-SEN': ['D','R']})


if __name__ == '__main__':
    unittest.main()
