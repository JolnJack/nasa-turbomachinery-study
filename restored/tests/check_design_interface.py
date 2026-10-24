"""End-to-end inverse solver checks: SI/US, static/total targets, clear failures."""
from pathlib import Path
import datetime, gzip, importlib.util, json

ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('solver',ROOT/'restored/tools/turbine_design_solver.py')
solver=importlib.util.module_from_spec(spec);spec.loader.exec_module(solver)
run=ROOT/'audit/2026-10-23/restoration'/('design-interface-'+datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ'));run.mkdir()
base=(ROOT/'restored/examples/turbine_original.inp').read_text().split('&END')[0]+'&END\n'
static=solver.override(solver.override(solver.override(base,'ITEST',1),'ETAD',.86975),'PDSGN',1.79477)
us=solver.override(base,'MODE',5)
conversion={'P0':172368.9/47.88025898033584,'T0':1144.44*1.8,'A0':.0120176/.09290304,'A1':.0038008/.09290304,'A3':.0039789/.09290304,'A5':.0044543/.09290304,'D3':12.6238/2.54,'D2':12.9997/2.54,'U3':237.9524/.3048,'R':99.1976/(32.1741*.3048**2*1.8),'WD':.33879/.45359237}
for k,v in conversion.items():us=solver.override(us,k,v)
checks=[]
for model in ['native32','compat27']:
    executable=solver.build(run/model,model)
    for name,text in [('SI-total',base),('SI-static',static),('US-total',us),('over-capacity',solver.override(base,'WD',1000))]:
        result=solver.solve(text,executable)
        (run/(model+'-'+name+'.json.gz')).write_bytes(gzip.compress(json.dumps(result).encode()))
        expected='stator-capacity-boundary-or-exceeded' if name=='over-capacity' else 'matched'
        check={'name':model+'-'+name,'pass':result['status']==expected,'status':result['status'],'errors':result.get('best',{}).get('errors')}
        checks.append(check);print(check,flush=True)
    for name,text in [('ambiguous-inheritance',base+base),('missing-design-flow',base.replace('WD=.33879',''))]:
        try:solver.solve(text,executable);ok=False
        except ValueError:ok=True
        checks.append({'name':model+'-'+name,'pass':ok})
(run/'results.json').write_text(json.dumps({'checks':checks},indent=2)+'\n');print('RESULTS',run)
raise SystemExit(0 if all(c['pass'] for c in checks) else 1)
