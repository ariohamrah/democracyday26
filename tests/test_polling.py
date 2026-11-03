import unittest
from datetime import date
from forecast.polling import aggregate, election_day, load_poll_observations


class PollingTests(unittest.TestCase):
    def observation(self, **changes):
        p=dict(pollster='Example',date='2026-10-30',available_date='2026-10-31',
               population='lv',sample_size=800,poll_id='1',partisan=False,
               candidate_d='Jane Doe',candidate_r='John Roe',dem_percent=52,rep_percent=48)
        p.update(changes)
        return p

    def test_publication_cutoff_and_candidate_matching(self):
        row=dict(candidate_d='Jane Doe',candidate_r='John Roe')
        p=self.observation(available_date='2026-11-03')
        self.assertEqual(aggregate([p],row,date(2026,11,2))[1],0)
        p=self.observation(candidate_d='Different Nominee')
        self.assertEqual(aggregate([p],row,date(2026,11,2))[1],0)

    def test_duplicate_populations_are_not_independent_polls(self):
        row=dict(candidate_d='Jane Doe',candidate_r='John Roe')
        lv=self.observation()
        rv=self.observation(population='rv',sample_size=1200,dem_percent=60,rep_percent=40,poll_id='2')
        mean,n,_=aggregate([lv,rv],row,date(2026,11,2))
        self.assertEqual(n,1)
        self.assertAlmostEqual(mean,4)

    def test_actuals_and_grades_cannot_enter_normalized_observations(self):
        observations,_=load_poll_observations()
        self.assertGreater(len(observations),1000)
        for p in observations:
            self.assertFalse(any('actual' in key or 'grade' in key or 'rating' in key for key in p))
            self.assertGreaterEqual(p['available_date'],p['date'])

    def test_explicit_alias_and_ambiguous_alias_rejection(self):
        row=dict(candidate_d='Bill Hill',candidate_r='Nicholas J. Begich III',
                 poll_aliases={'Nicholas J. Begich III':['Nick Begich']})
        poll=self.observation(results=[dict(candidate='Bill Hill',pct=48),dict(candidate='Nick Begich',pct=46)])
        self.assertEqual(aggregate([poll],row,date(2026,11,2))[1],1)
        row['poll_aliases']['Bill Hill']=['Nick Begich']
        self.assertEqual(aggregate([poll],row,date(2026,11,2))[1],0)

    def test_election_calendar(self):
        self.assertEqual(election_day(2022),date(2022,11,8))
        self.assertEqual(election_day(2024),date(2024,11,5))
        self.assertEqual(election_day(2026),date(2026,11,3))


if __name__=='__main__':
    unittest.main()
