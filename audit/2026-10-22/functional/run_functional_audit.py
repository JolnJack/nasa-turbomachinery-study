"""Non-mutating functional probes of the preserved NASA reconstruction.

Generated inputs beyond the supplied cases are probes, not NASA reference data.
Program exit codes are preserved. EOF is recorded as an error, never passed off as 0.
"""
from pathlib import Path
import datetime
import hashlib
import json
import re
import subprocess

HERE = Path(__file__).resolve().parent
BASE = HERE.parent / 'baseline'
RUN = HERE / ('run-' + datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ'))
RUN.mkdir()
FC = '/opt/homebrew/bin/gfortran'
FLAGS = ['-std=legacy', '-fno-automatic', '-g', '-fcheck=all', '-fbacktrace', '-ffpe-trap=invalid,zero,overflow']
builds = {}
for program in ('compressor_tn_d7487', 'turbine_tn_d8063'):
    exe = RUN / program
    command = [FC, *FLAGS, str(BASE / (program + '.f')), '-o', str(exe)]
    proc = subprocess.run(command, capture_output=True, timeout=30)
    (RUN / (program + '.compile.stderr')).write_bytes(proc.stderr)
    builds[program] = {'command':command, 'exit':proc.returncode, 'sha256':hashlib.sha256((BASE / (program+'.f')).read_bytes()).hexdigest()}
    if proc.returncode:
        raise RuntimeError('Compilation failed: '+program)

def override(text, key, value):
    pattern = r'(?i)(?<![A-Z0-9_])' + key + r'\s*=\s*[-+0-9.Ee]+'
    if re.search(pattern,text):
        return re.sub(pattern,key+'='+str(value),text)
    return text.replace('&END', key+'='+str(value)+' &END')

def numeric_rows(text):
    rows=[]
    for line in text.splitlines():
        try:
            values=[float(s) for s in line.split()]
        except ValueError:
            continue
        if len(values)==10:
            rows.append(values)
    return rows

results=[]
def run_case(label, program, data, origin, timeout=4):
    path=RUN/label
    path.with_suffix('.inp').write_text(data)
    with path.with_suffix('.stdout').open('wb') as stdout, path.with_suffix('.stderr').open('wb') as stderr:
        try:
            proc=subprocess.run([str(RUN/program)],input=data.encode(),stdout=stdout,stderr=stderr,cwd=RUN,timeout=timeout)
            code=proc.returncode
            timed_out=False
        except subprocess.TimeoutExpired:
            code=None
            timed_out=True
    out=path.with_suffix('.stdout').read_text(errors='replace')
    err=path.with_suffix('.stderr').read_text(errors='replace')
    row={'id':label,'program':program,'input_origin':origin,'exit':code,'timed_out':timed_out,
         'runtime_error': next((s for s in err.splitlines() if 'Fortran runtime error' in s or 'Program received signal' in s),''),
         'long_output_points':out.count('OVERALL PERFORMANCE'), 'short_output_points':len(numeric_rows(out)),
         'limiting_loading': 'LAST CASE IS APPROXIMATE LIMITING LOADING' in out,
         'solver_failure_messages': [s.strip() for s in out.splitlines() if any(x in s for x in ('NO SOLUTION','PROCEDURE WAS ABORTED'))],
         'nonfinite_output':bool(re.search(r'(?i)(?<!\w)(nan|infinity)(?!\w)',out)),
         'overflow_fields':bool(re.search(r'\*{3,}',out)),
         'compressor_points':[list(map(float,m)) for m in re.findall(r'WEQ\s+PRESSURE RATIO\s+ETAT\n\s*([\d.]+)\s+([\d.]+)\s+([\d.]+)',out)],
         'short_rows':numeric_rows(out)}
    results.append(row)
    print(json.dumps({k:v for k,v in row.items() if k not in ('compressor_points','short_rows')},ensure_ascii=False),flush=True)
    return out

turbine=(BASE/'turbine_tn_d8063.inp').read_text()
chunks=turbine.split('&END')
design=chunks[0]+'&END\n'
offdesign=chunks[1].lstrip('\n')+'&END\n'
compressor=(BASE/'compressor_tn_d7487.inp').read_text()
compchunks=[s.strip()+'&END\n' for s in compressor.split('&END') if s.strip()]

for i,data in enumerate(compchunks):
    run_case('compressor-speed-'+['100','90','80','60'][i],'compressor_tn_d7487',data,'Existing input separated into standalone cases; corresponding printed sample output pp.13-16')
for key,value,label in [('SPLT',0,'no-splitters'),('AL1MF',10,'positive-swirl'),('CURVH',0.1,'curved-hub'),('AR',2.9999,'ar-below3'),('AR',3.0,'ar-exact3'),('AR',3.0001,'ar-above3')]:
    run_case('compressor-probe-'+label,'compressor_tn_d7487',override(compchunks[0],key,value),'Synthetic feature/boundary probe; no NASA expected output')

for mode in (0,1,2,3,4,5):
    data=override(design if mode in (2,5) else offdesign,'MODE',mode)
    if mode>=3:
        # Match the physical case using the gravitational conversion constant in this code.
        conversion={'P0':172368.9/47.88025898033584,'T0':1144.44*1.8,
                    'A0':.0120176/.09290304,'A1':.0038008/.09290304,
                    'A3':.0039789/.09290304,'A5':.0044543/.09290304,
                    'D3':12.6238/2.54,'D2':12.9997/2.54,'U3':237.9524/.3048,
                    'R':99.1976/(32.1741*.3048**2*1.8)}
        if mode==5:
            conversion['WD']=.33879/.45359237
        for key,val in conversion.items():
            data=override(data,key,format(val,'.12g'))
    run_case('turbine-mode-'+str(mode),'turbine_tn_d8063',data,'Table I/II input for SI; synthetically converted input for US modes')

static=override(override(design,'ITEST',1),'ETAD',.86975)
static=override(static,'PDSGN',1.79477)
run_case('turbine-static-design','turbine_tn_d8063',static,'Synthetic ITEST=1 round-trip based on rounded Table III static efficiency and pressure ratio')
run_case('turbine-six-speeds','turbine_tn_d8063','&END'.join(chunks[1:]).lstrip('\n'),'Existing six-speed off-design package / Table II')
run_case('turbine-short-extended-limit','turbine_tn_d8063',override(override(offdesign,'MODE',1),'VMAX',.8001),'Diagnostic input-only change to investigate floating-point endpoint; not original sample')
calibrated=override(override(override(offdesign,'MODE',1),'XK',.286840),'PD',.987836)
run_case('turbine-short-tableIII-calibration','turbine_tn_d8063',override(calibrated,'VMAX',.8001),'Diagnostic: Table III printed calibration + extended limit; not Table II input')

# Compile the exact existing FNTGRL routine into an independent mathematical check.
src=(BASE/'compressor_tn_d7487.f').read_text()
routine=src.split('      SUBROUTINE FNTGRL',1)[1].split('      FUNCTION ARSIN',1)[0]
driver='''      PROGRAM VERIFYF
      DIMENSION F(20),S(20)
      DO 20 K=0,2
      DO 10 I=1,11
      X=FLOAT(I-1)/4.
      F(I)=X**K
   10 CONTINUE
      CALL FNTGRL(11,.25,F,S)
      DO 15 I=1,11
      X=FLOAT(I-1)/4.
      EXACT=X**(K+1)/FLOAT(K+1)
      WRITE(*,*) K,I,S(I),EXACT,ABS(S(I)-EXACT)
   15 CONTINUE
   20 CONTINUE
      END
      SUBROUTINE FNTGRL'''+routine
(RUN/'fntgrl_formula_check.f').write_text(driver)
subprocess.run([FC,*FLAGS,str(RUN/'fntgrl_formula_check.f'),'-o',str(RUN/'fntgrl_formula_check')],check=True,capture_output=True,timeout=30)
fnt=subprocess.run([str(RUN/'fntgrl_formula_check')],capture_output=True,text=True,timeout=4)
(RUN/'fntgrl_formula_check.stdout').write_text(fnt.stdout)
(RUN/'fntgrl_formula_check.stderr').write_text(fnt.stderr)
errors=[float(l.split()[-1]) for l in fnt.stdout.splitlines() if len(l.split())==5]
fnt_result={'exit':fnt.returncode,'polynomial_cases':3,'checked_values':len(errors),'maximum_absolute_error':max(errors,default=None),'scope':'Constant, linear, quadratic functions; 11 nodes; step 0.25; not all possible arrays'}
report={'builds':builds,'cases':results,'fntgrl_formula_check':fnt_result}
(RUN/'results.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
print('RESULTS',RUN)
print('FNTGRL',json.dumps(fnt_result))
