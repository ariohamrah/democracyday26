"""Run offline once more and verify exact deterministic numerical artifacts."""
import hashlib
from pathlib import Path
import subprocess
import sys

root=Path(__file__).resolve().parents[1]
paths=[root/'outputs'/name for name in ['submission.csv','forecasts.csv','candidate_forecasts.csv',
       'historical_backtests.csv','historical_features.csv','validation.json','model.json','chamber_forecasts.json']]
def hashes():return {str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
before=hashes()
subprocess.run([sys.executable,'-m','forecast.run'],cwd=root,check=True)
after=hashes()
if before!=after:raise SystemExit('Non-deterministic artifacts: '+str([k for k in before if before[k]!=after[k]]))
print('Deterministic reproduction verified for',len(paths),'numerical artifacts.')
