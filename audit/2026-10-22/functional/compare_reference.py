"""Compare printed numeric values without silently introducing tolerances.

Differences are observations, not automatic proof that the code is wrong.
The reference file documents contradictory calibration and formatting evidence.
"""
from pathlib import Path
import json
import re
import sys

HERE=Path(__file__).resolve().parent
RUN=Path(sys.argv[1]) if len(sys.argv)>1 else HERE/'run-20261023T044639690683Z'
ref=json.loads((HERE/'reference_core.json').read_text())
run=json.loads((RUN/'results.json').read_text())
cases={c['id']:c for c in run['cases']}

def compare(expected,actual,columns):
    mismatches=[]
    matched=0
    exact_rows=0
    for i,(want,got) in enumerate(zip(expected,actual)):
        if want==got:
            exact_rows+=1
        for name,a,b in zip(columns,want,got):
            if a==b:
                matched+=1
            else:
                mismatches.append({'row':i+1,'column':name,'reference':a,'actual':b,'difference':b-a})
    return {'expected_rows':len(expected),'actual_rows':len(actual),'exact_rows':exact_rows,'exact_numeric_cells':matched,
            'missing_rows':max(0,len(expected)-len(actual)),'mismatches':mismatches}

report={'scope':'Printed numeric values only, not bitwise arithmetic identity or full functional certification',
        'compressor_checked':{},'compressor_existing_output':{},'turbine_table_v':{},'reference_caveats':ref['turbine_table_v_caveats']}
baseline=(HERE.parent/'baseline'/'compressor_tn_d7487.out').read_text()
blocks=baseline.split('PERCENT NDES')[1:]
for speed,block in zip(('100','90','80','60'),blocks):
    actual=[list(map(float,m)) for m in re.findall(r'WEQ\s+PRESSURE RATIO\s+ETAT\n\s*([\d.]+)\s+([\d.]+)\s+([\d.]+)',block)]
    report['compressor_existing_output'][speed]=compare(ref['compressor'][speed],actual,ref['compressor_columns'])
    report['compressor_checked'][speed]=compare(ref['compressor'][speed],cases['compressor-speed-'+speed]['compressor_points'],ref['compressor_columns'])
for label in ('turbine-mode-1','turbine-short-extended-limit','turbine-short-tableIII-calibration'):
    report['turbine_table_v'][label]=compare(ref['turbine_table_v'],cases[label]['short_rows'],ref['turbine_table_v_columns'])
(RUN/'reference-comparison.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
for category in ('compressor_checked','compressor_existing_output','turbine_table_v'):
    for label,row in report[category].items():
        print(category,label,json.dumps({k:v for k,v in row.items() if k!='mismatches'}))
        if category=='compressor_existing_output' and row['mismatches']:
            print(row['mismatches'])
