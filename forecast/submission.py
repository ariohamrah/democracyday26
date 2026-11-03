"""Export the user's exact five-column competition template."""
from .io import ROOT, read_csv, write_csv
from .roster import APPORTIONMENT

HEADERS = ['race_id', 'chamber', 'predicted_winner_party', 'candidate_name', 'win_probability']


def internal_id(template_row):
    race = template_row['race_id']
    if template_row['chamber'] == 'Senate' and race in ('FL-SEN', 'OH-SEN'):
        return race + '-SPECIAL'
    if template_row['chamber'] == 'House' and race.endswith('-AL'):
        if APPORTIONMENT.get(race[:2]) != 1:
            raise ValueError(f'Invalid at-large district: {race}')
        return race[:2] + '-01'
    return race


def format_submission(forecasts):
    template = read_csv(ROOT / 'data/submission_template.csv')
    if not template or list(template[0]) != HEADERS:
        raise ValueError('Submission template headers changed')
    index = {r['race_id']: r for r in forecasts}
    if len(index) != len(forecasts):
        raise ValueError('Duplicate forecast race')
    seen, rows = set(), []
    for source in template:
        key = internal_id(source)
        if key in seen or key not in index:
            raise ValueError(f'Duplicate or unmatched template race: {key}')
        seen.add(key)
        f = index[key]
        if f['chamber'] != source['chamber']:
            raise ValueError(f'Chamber mismatch: {key}')
        rows.append(dict(race_id=source['race_id'], chamber=source['chamber'],
                         predicted_winner_party=f['most_likely_winner_party'],
                         candidate_name=f['most_likely_winner'],
                         win_probability=f['winner_probability']))
    if seen != set(index):
        raise ValueError('Template does not cover all forecast races')
    return rows


if __name__ == '__main__':
    write_csv(ROOT / 'outputs/submission.csv', format_submission(read_csv(ROOT / 'outputs/forecasts.csv')), HEADERS)
