import unittest
from forecast.io import ROOT, read_csv
from forecast.submission import HEADERS, format_submission, internal_id


class SubmissionTests(unittest.TestCase):
    def test_exact_template_and_predictions(self):
        template = read_csv(ROOT/'data/submission_template.csv')
        output = read_csv(ROOT/'outputs/submission.csv')
        forecasts = read_csv(ROOT/'outputs/forecasts.csv')
        self.assertEqual(len(output), 470)
        self.assertEqual(list(output[0]), HEADERS)
        self.assertEqual([(r['race_id'],r['chamber']) for r in output],
                         [(r['race_id'],r['chamber']) for r in template])
        self.assertEqual(output, format_submission(forecasts))
        self.assertTrue(all(r['candidate_name'] and 0 <= float(r['win_probability']) <= 1 for r in output))

    def test_aliases_are_unambiguous(self):
        template = read_csv(ROOT/'data/submission_template.csv')
        keys = [internal_id(r) for r in template]
        self.assertEqual(len(set(keys)), 470)
        self.assertIn('FL-SEN-SPECIAL',keys)
        self.assertIn('OH-SEN-SPECIAL',keys)
        self.assertEqual(internal_id({'race_id':'AK-AL','chamber':'House'}),'AK-01')
        with self.assertRaises(ValueError):
            internal_id({'race_id':'CA-AL','chamber':'House'})
