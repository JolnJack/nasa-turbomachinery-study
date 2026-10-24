from pathlib import Path
import json,hashlib
ROOT=Path(__file__).resolve().parents[2];SRC=ROOT/'restored'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
base=ROOT/'audit/2026-10-22/baseline'
m=json.loads((base.parent/'baseline-manifest.json').read_text())
locations=json.loads((ROOT/'originals/manifest.json').read_text())
locations={f['original_name']:f['path'] for f in locations['files']}
for f in m['files']:
 assert sha(ROOT/locations[f['file']])==f['sha256'], 'Original changed: '+f['file']
 assert sha(base/f['file'])==f['sha256'], 'Baseline changed: '+f['file']
g=json.loads((SRC/'compat27/generation.json').read_text())
for name,row in g['sources'].items():
 assert sha(SRC/(name+'.f'))==row['sha256'], 'Generated source stale: '+name
 assert sha(SRC/'compat27'/(name+'.f90'))==row['generated_sha256'], 'Generated source changed: '+name
for name,original in [('compressor_original.inp','compressor_tn_d7487.inp'),('turbine_original.inp','turbine_tn_d8063.inp')]:
 assert sha(SRC/'examples'/name)==sha(ROOT/'originals'/original)
print('PASS: 14 originals, 14 baseline copies, both generated programs and original example inputs')
