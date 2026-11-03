import csv
import hashlib
import json
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CUTOFF = '2026-11-02T20:13:00-08:00'


def read_csv(path):
    with Path(path).open(encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))


def write_csv(path, rows, fields=None):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fields or list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def timestamp(value):
    result = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if result.tzinfo is None:
        raise ValueError('A timestamp must include its timezone')
    return result


def assert_cutoff(value, cutoff=CUTOFF):
    if timestamp(value) > timestamp(cutoff):
        raise ValueError(f'Post-cutoff information: {value}')


def manifest():
    files = []
    for path in sorted((ROOT / 'data').rglob('*')):
        relative=path.relative_to(ROOT).as_posix()
        if relative.startswith('data/odds/raw/') or relative=='data/odds/provisional_nov1.csv' or (relative.startswith('data/signals/kalshi_') and relative.endswith('.json')):
            continue
        if path.is_file() and path.name != 'manifest.json':
            files.append(dict(path=str(path.relative_to(ROOT)), bytes=path.stat().st_size,
                              sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
    (ROOT / 'data/manifest.json').write_text(json.dumps(dict(cutoff=CUTOFF, files=files), indent=2) + '\n')
