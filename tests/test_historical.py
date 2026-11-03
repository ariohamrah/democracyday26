"""Historical data leakage and nonstandard-field regression checks."""
import unittest
from forecast.features import build_features
from forecast.data import load_history


class HistoricalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.history, cls.presidential, _ = load_history()

    def test_senate_independent_and_multicandidate_lags(self):
        targets = [dict(year=2026, state=s, chamber='Senate', race_id=s+'-SEN-2',
                        seat_class=2, candidate_d='Candidate Democrat', candidate_r='Candidate Republican')
                   for s in ['ME', 'AK']]
        rows = build_features(self.history, targets, self.presidential)
        for row in rows:
            self.assertEqual(row['lag_year'], 2020)
            self.assertLess(abs(row['lag_margin']), 20)

    def test_house_missing_adjacent_lag_does_not_cross_old_maps(self):
        history = [dict(year=2014, state='FL', chamber='House', race_id='FL-01',
                        seat_class='', candidate_d='Old Democrat', candidate_r='Old Republican',
                        dem_votes=80, rep_votes=20, winner_name='Old Democrat', excluded='')]
        target = dict(year=2020, state='FL', chamber='House', race_id='FL-01',
                      candidate_d='New Democrat', candidate_r='New Republican')
        row = build_features(history, [target], self.presidential)[0]
        self.assertTrue(row['lag_missing'])
        self.assertEqual(row['lag_margin'], row['prior_pres_margin'])

    def test_targets_never_use_same_cycle_results(self):
        targets = [r for r in self.history if r['year'] >= 2016 and not r['excluded']]
        rows = build_features(self.history, targets, self.presidential)
        for row in rows:
            self.assertLess(row['prior_pres_year'], row['year'])
            if row['lag_year'] != '':
                self.assertLess(row['lag_year'], row['year'])

    def test_fitted_targets_have_correct_binary_winners(self):
        for row in self.history:
            if not row['excluded']:
                self.assertEqual(row['winner_party'] == 'D', row['dem_votes'] > row['rep_votes'])


if __name__ == '__main__':
    unittest.main()


class FieldPriorTests(unittest.TestCase):
    def test_field_priors_reproducible_and_smoothed(self):
        from forecast.field_priors import estimate_field_priors
        priors = estimate_field_priors()
        for key in ('minor_with_both_major', 'minor_with_one_major', 'same_party_incumbent'):
            row = priors[key]
            self.assertGreater(row['trials'], 0)
            self.assertAlmostEqual(row['probability'], (row['successes']+.5)/(row['trials']+1))
            self.assertTrue(all(e['year'] <= 2024 for e in row['success_examples']))
        with self.assertRaises(ValueError):
            estimate_field_priors(2026)

    def test_nested_calibration_selects_alpha_using_earlier_years(self):
        from unittest.mock import patch
        import numpy as np
        from forecast.model import residuals_before
        years = np.repeat([2006,2008,2010,2012,2014], 4)
        x = np.arange(40, dtype=float).reshape(20,2)
        y = np.arange(20, dtype=float)
        seen = []
        def select(x, y, years):
            seen.append(int(years.max()))
            return 100.
        with patch('forecast.model.select_alpha', side_effect=select):
            residuals_before(x,y,years,1000.)
        self.assertEqual(seen, [2010,2012])
