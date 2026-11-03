import unittest
from forecast.optimize_submission import select, build


class OptimizeTests(unittest.TestCase):
    def setUp(self):
        self.candidates = [dict(candidate='Favorite', party='D', q=.7),
                           dict(candidate='Underdog', party='R', q=.3)]

    def test_expected_points_can_select_underdog(self):
        selected, status, points = select(self.candidates, {'D': .9, 'R': .1}, 'party')
        self.assertEqual(selected['candidate'], 'Underdog')
        self.assertEqual(selected['q'], .3)
        self.assertEqual(status, 'optimized')
        self.assertGreater(points, .9)

    def test_does_not_always_pick_underdog(self):
        selected, _, _ = select(self.candidates, {'D': .51, 'R': .49}, 'party')
        self.assertEqual(selected['candidate'], 'Favorite')

    def test_export_uses_selected_candidate_probability(self):
        candidates = [dict(c, race_id='AK-01') for c in self.candidates]
        metadata = {('AK-01', p):dict(contract_type='party', status='current_proxy') for p in ('D','R')}
        rows, audit = build(candidates, {'AK-01':{'D':.9,'R':.1}}, metadata,
                            [dict(race_id='AK-AL', chamber='House')])
        self.assertEqual(rows[0]['candidate_name'], 'Underdog')
        self.assertEqual(rows[0]['predicted_winner_party'], 'R')
        self.assertEqual(rows[0]['win_probability'], .3)
        self.assertTrue(audit[0]['provisional'])

    def test_missing_and_zero_are_not_silently_substituted(self):
        self.assertEqual(select(self.candidates, {}, 'party')[:2], (None, 'missing_prices'))
        self.assertEqual(select(self.candidates, {'D': .9}, 'party')[1], 'best_among_priced_only')
        self.assertEqual(select(self.candidates, {'D': 1, 'R': 0}, 'party')[1], 'zero_price_requires_rule')

    def test_party_contract_cannot_choose_same_party_candidate(self):
        candidates = [dict(candidate='A', party='D', q=.6), dict(candidate='B', party='D', q=.4)]
        self.assertEqual(select(candidates, {'D': .5}, 'party')[1], 'party_contract_cannot_select_candidate')
        self.assertEqual(select(candidates, {'A': .6, 'B': .4}, 'candidate')[0]['candidate'], 'B')
