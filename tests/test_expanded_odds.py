import unittest
from scripts.collect_expanded_odds import event_race,parse_event
from forecast.optimize_submission import select_contracts


class ExpandedOddsTests(unittest.TestCase):
    def test_omnibus_and_at_large(self):
        self.assertEqual(event_race(dict(event_ticker='KXHOUSERACE-WYAL-26')), 'WY-01')
        self.assertEqual(event_race(dict(event_ticker='KXHOUSERACE-CA04-26')), 'CA-04')

    def test_legacy_kentucky_uses_rule_not_ticker(self):
        e=dict(event_ticker='SENATELA-26',series_ticker='SENATELA',title='Kentucky Senate winner?',markets=[dict(rules_primary='Senator of Kentucky')])
        self.assertEqual(event_race(e),'KY-SEN')
        e['markets'][0]['rules_primary']='Senator of Louisiana'
        with self.assertRaises(ValueError):event_race(e)

    def test_capitalized_party_is_admitted(self):
        e=dict(event_ticker='KXHOUSERACE-TX15-26',markets=[dict(ticker='TEST',status='active',
          rules_primary='If the House member sworn in for TX-15 is a member of the Democratic Party, then Yes.',
          yes_bid_dollars='.3',yes_ask_dollars='.4')])
        r=parse_event(e,{'TX-15':[dict(candidate='A',party='D')]},'2026-11-03T00:00:00+00:00')
        self.assertEqual(r[0]['outcome'],'D');self.assertAlmostEqual(r[0]['probability'],.35)

    def test_party_probability_is_sum_and_candidate_is_representative(self):
        cs=[dict(candidate='A',party='R',q=.4),dict(candidate='B',party='R',q=.3),dict(candidate='C',party='D',q=.3)]
        result=select_contracts(cs,{'R':.5,'D':.5},{p:dict(contract_type='party') for p in ['R','D']})
        self.assertEqual(result[0]['candidate'],'A');self.assertEqual(result[1],'optimized')
        self.assertAlmostEqual(result[2],.7);self.assertEqual(result[3:],('R','party'))

    def test_candidate_and_party_events_stay_distinct(self):
        cs=[dict(candidate='Independent',party='I',q=.4),dict(candidate='Republican',party='R',q=.6)]
        result=select_contracts(cs,{'Independent':.1,'R':.9},{'Independent':dict(contract_type='candidate'),'R':dict(contract_type='party')})
        self.assertEqual(result[0]['candidate'],'Independent');self.assertEqual(result[3: ],('Independent','candidate'))
