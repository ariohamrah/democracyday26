"""Geographically aligned past presidential returns, without same-cycle leakage."""
import csv
import re
from .io import ROOT


def normalize_race(value):
    value = value.strip().upper()
    if re.fullmatch(r'[A-Z]{2}-(AL|00|0)', value):
        return value[:2] + '-01'
    return value


def district_baselines():
    # map year: columns by presidential election year, D then R.
    column_map = {2010: {2008: (3,4), 2004: (5,6), 2000: (7,8)}, 2014: {2012: (3,4), 2008: (5,6)},
                  2016: {2016: (3,4), 2012: (5,6), 2008: (7,8)},
                  2018: {2016: (3,4), 2012: (5,6), 2008: (7,8)},
                  2020: {2020: (3,4), 2016: (5,6), 2012: (7,8), 2008: (9,10)},
                  2022: {2020: (3,4)}, 2024: {2024: (3,4), 2020: (6,7)},
                  2026: {2024: (3,4), 2020: (6,7)}}
    result = {}
    for map_year, columns in column_map.items():
        path = ROOT / f'data/geography/presidential_districts_map_{map_year}.csv'
        if not path.exists():
            continue
        with path.open(encoding='utf-8-sig', newline='') as f:
            for row in csv.reader(f):
                if not row or not re.fullmatch(r'[A-Z]{2}-(\d{2}|AL)', row[0]):
                    continue
                for election_year, (dcol,rcol) in columns.items():
                    try:
                        d, r = float(row[dcol].replace('%','')), float(row[rcol].replace('%',''))
                    except (ValueError, IndexError):
                        continue
                    if d + r > 0:
                        result[map_year, election_year, normalize_race(row[0])] = 100 * (d-r)/(d+r)
    exact = ROOT / 'data/geography/presidential_districts_map_2026_exact.csv'
    if exact.exists():
        with exact.open(encoding='utf-8-sig', newline='') as f:
            for row in csv.reader(f):
                if not row or not re.fullmatch(r'[A-Z]{2}-(\d{2}|AL)', row[0]):
                    continue
                d, r = float(row[4].replace(',', '')), float(row[5].replace(',', ''))
                result[2026, 2024, normalize_race(row[0])] = 100*(d-r)/(d+r)
    return result


def baseline_for(race_id, forecast_year, baselines):
    map_year = {2006: 2010, 2008: 2010, 2012: 2014}.get(forecast_year, forecast_year)
    eligible = [(election_year, margin) for (mp, election_year, race), margin in baselines.items()
                if mp == map_year and election_year < forecast_year and race == race_id]
    if not eligible:
        return None, None
    year, margin = max(eligible)
    assert year < forecast_year
    return margin, year


def changed_map(state, year):
    # Conservative state-level suppression of lag congressional returns.
    # Presidential returns are instead reaggregated on each target cycle's map.
    if year in (2012, 2022):
        return True
    changes = {2006: {'TX'}, 2016: {'FL','NC','VA'}, 2018: {'PA'},
               2020: {'NC'}, 2024: {'AL','GA','LA','NC','NY'},
               2026: {'AL','CA','FL','LA','NC','OH','TN','TX','UT'}}
    return state in changes.get(year, set())
