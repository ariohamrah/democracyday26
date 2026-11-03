"""Independent roster and final candidate/party probability consistency checks."""
import copy
import json
import unittest
from collections import Counter, defaultdict

from forecast.fields import load_targets, party
from forecast.io import ROOT, read_csv
from forecast.roster import validate_roster


class RosterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.targets = load_targets()
        cls.by_id = {r['race_id']: r for r in cls.targets}
        cls.holdovers = read_csv(ROOT / 'data/roster/senate_holdovers.csv')

    def test_complete_current_roster_and_holdovers(self):
        validate_roster(self.targets, self.holdovers)
        self.assertEqual(Counter(r['chamber'] for r in self.targets), {'House': 435, 'Senate': 35})
        self.assertEqual(len(self.by_id), 470)
        self.assertEqual(Counter(r['party'] for r in self.holdovers), {'D': 32, 'R': 31, 'I': 2})
        self.assertEqual(Counter(r['caucus'] for r in self.holdovers), {'D': 34, 'R': 31})
        contested = {(r['state'], r['seat_class']) for r in self.targets if r['chamber'] == 'Senate'}
        held = {(r['state'], int(r['seat_class'])) for r in self.holdovers}
        self.assertFalse(contested & held)
        self.assertEqual(len(contested | held), 100)

    def test_roster_rejects_equal_size_wrong_seat_and_duplicate(self):
        broken = copy.deepcopy(self.targets)
        next(r for r in broken if r['race_id'] == 'CA-52')['district'] = 53
        with self.assertRaises(ValueError):
            validate_roster(broken, self.holdovers)
        broken = copy.deepcopy(self.targets)
        broken[-1] = copy.deepcopy(broken[0])
        with self.assertRaises(ValueError):
            validate_roster(broken, self.holdovers)

    def test_holdover_overlap_rejected(self):
        broken = copy.deepcopy(self.holdovers)
        broken[0]['state'], broken[0]['seat_class'] = 'AL', '2'
        with self.assertRaises(ValueError):
            validate_roster(self.targets, broken)

    def test_candidate_names_and_actual_party_identity(self):
        for row in self.targets:
            names = [c['name'] for c in row['candidates']]
            self.assertEqual(len(names), len(set(names)), row['race_id'])
            self.assertTrue(all(n.strip() for n in names), row['race_id'])
            self.assertTrue(all(c['party'] in ('D', 'R', 'I', 'O') for c in row['candidates']))
            for side in ('candidate_d', 'candidate_r'):
                if row[side]:
                    self.assertIn(row[side], names)
        self.assertEqual(party('Independent, Unenrolled'), 'I')
        self.assertEqual(party('Democratic-Farmer-Labor'), 'D')
        self.assertEqual(party('Republican, Conservative'), 'R')
        sd = self.by_id['SD-SEN']
        self.assertEqual({c['name'] for c in sd['candidates']}, {'Mike Rounds', 'Brian L. Bengs'})

    def test_independent_principal_pairs_do_not_change_parties(self):
        expected = {'AK-01': ('Bill Hill', 'Nicholas J. Begich III'),
                    'NE-SEN': ('Dan Osborn', 'Pete Ricketts'),
                    'ID-SEN': ('Todd Achilles', 'James E. Risch'),
                    'SD-SEN': ('Brian L. Bengs', 'Mike Rounds'),
                    'MT-SEN': ('Seth Bodnar', 'Kurt Alme')}
        for race, pair in expected.items():
            row = self.by_id[race]
            self.assertEqual((row['candidate_d'], row['candidate_r']), pair)
            parties = {c['name']: c['party'] for c in row['candidates']}
            self.assertEqual(parties[pair[0]], 'I')
            self.assertEqual(parties[pair[1]], 'R')
            self.assertIsNone(row['profile']['caucus_assumption'])
        mt = self.by_id['MT-SEN']
        self.assertIn('Alani Bankhead', {c['name'] for c in mt['candidates']})
        ak = self.by_id['AK-SEN']
        self.assertIn('Dan Sullivan', {c['name'] for c in ak['candidates']})
        self.assertIn('Daniel J. Sullivan, Jr.', {c['name'] for c in ak['candidates']})

    def test_same_party_fields(self):
        rows = {r['race_id']: r for r in self.targets if r['field_kind'] == 'same_party_top_two'}
        expected = {'CA-04', 'CA-07', 'CA-11', 'CA-12', 'CA-14', 'CA-29', 'CA-34', 'CA-37', 'CA-40'}
        self.assertEqual(set(rows), expected)
        for race, row in rows.items():
            self.assertEqual(len(row['candidates']), 2)
            self.assertEqual({c['party'] for c in row['candidates']}, {'R' if race == 'CA-40' else 'D'})
            self.assertEqual(row['electoral_system'], 'top_two_general')


class GeneratedOutputTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.forecasts = read_csv(ROOT / 'outputs/forecasts.csv')
        cls.candidates = read_csv(ROOT / 'outputs/candidate_forecasts.csv')
        cls.submission = read_csv(ROOT / 'outputs/submission.csv')

    def test_output_coverage_and_candidate_identity(self):
        roster = load_targets()
        expected = {r['race_id'] for r in roster}
        for rows in (self.forecasts, self.submission):
            self.assertEqual(len(rows), 470)
            self.assertEqual({r['race_id'] for r in rows}, expected)
        actual_candidates = {(r['race_id'], r['candidate']) for r in self.candidates}
        expected_candidates = {(r['race_id'], c['name']) for r in roster for c in r['candidates']}
        self.assertEqual(actual_candidates, expected_candidates)
        self.assertEqual(len(actual_candidates), len(self.candidates))

    def test_candidate_probabilities_reconcile_to_parties_and_winner(self):
        groups = defaultdict(list)
        for row in self.candidates:
            q = float(row['q'])
            self.assertTrue(0 <= q <= 1, row)
            groups[row['race_id']].append(row)
        for row in self.forecasts:
            candidates = groups[row['race_id']]
            self.assertAlmostEqual(sum(float(c['q']) for c in candidates), 1, places=9)
            for party_code, column in [('D', 'q_democratic'), ('R', 'q_republican'), ('I', 'q_independent'), ('O', 'q_other')]:
                self.assertAlmostEqual(sum(float(c['q']) for c in candidates if c['party'] == party_code), float(row[column]), places=9)
            winner = next(c for c in candidates if c['candidate'] == row['most_likely_winner'])
            self.assertEqual(winner['party'], row['most_likely_winner_party'])
            self.assertAlmostEqual(float(winner['q']), max(float(c['q']) for c in candidates), places=9)
            self.assertAlmostEqual(float(winner['q']), float(row['winner_probability']), places=9)


if __name__ == '__main__':
    unittest.main()
