"""Behavioral regressions. Only NASA reference triples are treated as truth.
Synthetic probes check continuity, completion and interfaces, not experimental accuracy.
"""
import argparse, hashlib, json, os, re, shutil, subprocess, sys, datetime
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
BASE=ROOT/'audit/2026-10-22/baseline'
p=argparse.ArgumentParser();p.add_argument('--source',type=Path,default=ROOT/'restored');p.add_argument('--only',default='');p.add_argument('--tag',default='regression');p.add_argument('--compat27',action='store_true');p.add_argument('--quad',action='store_true');args=p.parse_args()
allowed={'compressor','ar','turbine','input','cards','features','domain','supersonic'}
if args.only and not set(args.only.split(','))<=allowed:p.error('Unknown test group')
RUN=ROOT/'audit/2026-10-23/restoration'/('run-'+args.tag+'-'+datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ'));RUN.mkdir(parents=True)
FC=os.environ.get('FC') or shutil.which('gfortran')
FLAGS=['-std=legacy','-fno-automatic','-fcheck=all','-ffpe-trap=invalid,zero,overflow','-fbacktrace','-g']
if args.compat27:FLAGS+=(['-fdefault-real-16'] if args.quad else ['-fdefault-real-8','-fdefault-double-8'])+['-ffree-line-length-none']
meta={'source':str(args.source.resolve()),'compiler':subprocess.check_output([FC,'--version'],text=True).splitlines()[0],'flags':FLAGS,'builds':{},'checks':[],'cases':{}}
for prog in ['compressor_tn_d7487','turbine_tn_d8063']:
 src=args.source/('compat27/'+prog+'.f90' if args.compat27 else prog+'.f'); cmd=[FC,*FLAGS,str(src),'-o',str(RUN/prog)]
 
 if (args.source/'read_namelist_cards.f90').exists():cmd.insert(-2,str(args.source/'read_namelist_cards.f90'))
 r=subprocess.run(cmd,capture_output=True);(RUN/(prog+'.build.stderr')).write_bytes(r.stderr)
 meta['builds'][prog]={'command':cmd,'exit':r.returncode,'sha256':hashlib.sha256(src.read_bytes()).hexdigest()}
 if r.returncode:raise RuntimeError(r.stderr.decode())
comp=[x.strip()+'&END\n' for x in (BASE/'compressor_tn_d7487.inp').read_text().split('&END') if x.strip()]
turb=[x.lstrip('\n')+'&END\n' for x in (BASE/'turbine_tn_d8063.inp').read_text().split('&END') if x.strip()]
def override(s,k,v):
 pat=r'(?i)(?<![A-Z0-9_])'+k+r'\s*=\s*[-+0-9.Ee]+'
 return re.sub(pat,k+'='+str(v),s) if re.search(pat,s) else s.replace('&END',k+'='+str(v)+' &END')
def run(label,prog,data):
 (RUN/(label+'.inp')).write_text(data)
 try:
  r=subprocess.run([str(RUN/prog)],input=data.encode(),capture_output=True,timeout=8)
  out=r.stdout.decode(errors='replace');err=r.stderr.decode(errors='replace');code=r.returncode
 except subprocess.TimeoutExpired as e:out=(e.stdout or b'').decode(errors='replace');err='TIMEOUT';code=None
 (RUN/(label+'.stdout')).write_text(out);(RUN/(label+'.stderr')).write_text(err)
 meta['cases'][label]={'exit':code,'stderr':err,'input_sha256':hashlib.sha256(data.encode()).hexdigest()}
 return code,out,err
def triples(s):return [list(map(float,m)) for m in re.findall(r'WEQ\s+PRESSURE RATIO\s+ETAT\n\s*([\d.]+)\s+([\d.]+)\s+([\d.]+)',s)]
def rows(s):
 a=[]
 for line in s.splitlines():
  try:v=list(map(float,line.split()))
  except ValueError:continue
  if len(v)==10:a.append(v)
 return a
def check(name,ok,detail=''):
 meta['checks'].append({'name':name,'pass':bool(ok),'detail':detail});print(('PASS ' if ok else 'FAIL ')+name+' '+str(detail),flush=True)
def selected(s):return not args.only or s in args.only.split(',')
ref=json.loads((ROOT/'audit/2026-10-22/functional/reference_core.json').read_text())
if selected('compressor'):
 for i,speed in enumerate(['100','90','80','60']):
  code,out,err=run('compressor-'+speed,'compressor_tn_d7487',comp[i])
  check('compressor '+speed+' safe completion',code==0 and not err,err[:180])
  actual=triples(out);wanted=ref['compressor'][speed]
  check('compressor '+speed+' reference triples',actual==wanted,{'expected':len(wanted),'actual':len(actual),'differences':[(i+1,a,b) for i,(a,b) in enumerate(zip(wanted,actual)) if a!=b]})
if selected('ar'):
 for center in [1.2,2.,3.,4.,5.]:
  values=[]
  for val in [max(1.2,center-.0001),center,min(5.,center+.0001)]:
   code,out,err=run('ar-'+str(val),'compressor_tn_d7487',override(comp[0],'AR',val));v=triples(out)
   values.append(v[0][1:] if v else None)
  ok=all(v is not None for v in values) and all(abs(a-b)<.01 for left,right in zip(values,values[1:]) for a,b in zip(left,right))
  check('AR node continuity '+str(center),ok,values)
if selected('turbine'):
 for mode in [0,1,2]:
  code,out,err=run('turbine-'+str(mode),'turbine_tn_d8063',override(turb[0 if mode==2 else 1],'MODE',mode))
  check('turbine '+str(mode)+' safe completion',code==0 and not err,err[:120])
  check('turbine '+str(mode)+' intact titles','12.62-CM DIA TURBINE' in out and '100 PERCENT SPEED' in out)
  if mode!=2:
   count=len(rows(out)) if mode==1 else out.count('OVERALL PERFORMANCE')
   check('turbine '+str(mode)+' complete choking scan',count==20 and 'LAST CASE IS APPROXIMATE LIMITING LOADING' in out,count)
if selected('input'):
 for prog in ['compressor_tn_d7487','turbine_tn_d8063']:
  code,out,err=run(prog+'-empty',prog,'');check(prog+' empty EOF',code==0 and not err,err[:100])
  code,out,err=run(prog+'-malformed',prog,' &INPUT GAM=bad &END\n' if prog.startswith('compressor') else 'title\ncase\n &IN G=bad &END\n');check(prog+' malformed input fails',code not in (None,0),err[:100])
if selected('cards'):
 for prog in ['compressor_tn_d7487','turbine_tn_d8063']:
  prefix='' if prog.startswith('compressor') else 'title\ncase\n'
  group='INPUT' if prog.startswith('compressor') else 'IN'
  for label,data in [('truncated',prefix+' &'+group+(' GAM=1.4\n' if prog.startswith('compressor') else ' G=1.4\n')),('garbage',prefix+'garbage\n'),('wrong-group',prefix+' &WRONG X=1 &END\n')]:
   code,out,err=run(prog+'-'+label,prog,data)
   check(prog+' rejects '+label,code not in (0,None),err[:100])
if selected('features'):
 for key,val in [('SPLT',0),('CURVH',.1),('AL1MF',10)]:
  code,out,err=run('feature-'+key,'compressor_tn_d7487',override(comp[0],key,val))
  check('compressor feature '+key,code==0 and not err and len(triples(out))>0,{'points':len(triples(out)),'exit':code})
  check('compressor readable '+key,not bool(re.search(r'\*{3,}',out)))
 full=comp[0]+override(comp[0],'NONDES',.9)
 partial=comp[0]+' &INPUT NONDES=.9 &END\n'
 c,fullout,e=run('two-full-inputs','compressor_tn_d7487',full)
 c,partout,e=run('partial-second-input','compressor_tn_d7487',partial)
 check('compressor partial namelist keeps geometry',c==0 and triples(fullout)==triples(partout),{'full':len(triples(fullout)),'partial':len(triples(partout))})
 for mode in [3,4,5]:
  data=override(turb[0 if mode==5 else 1],'MODE',mode)
  conv={'P0':172368.9/47.88025898033584,'T0':1144.44*1.8,'A0':.0120176/.09290304,'A1':.0038008/.09290304,'A3':.0039789/.09290304,'A5':.0044543/.09290304,'D3':12.6238/2.54,'D2':12.9997/2.54,'U3':237.9524/.3048,'R':99.1976/(32.1741*.3048**2*1.8)}
  if mode==5:conv['WD']=.33879/.45359237
  for key,v in conv.items():data=override(data,key,format(v,'.12g'))
  c,out,e=run('mode-'+str(mode),'turbine_tn_d8063',data)
  n=len(rows(out)) if mode==4 else out.count('OVERALL PERFORMANCE')
  check('turbine US mode '+str(mode),c==0 and not e and n==(1 if mode==5 else 20),{'points':n,'exit':c})
  if mode==4:
   c,si,e=run('units-si','turbine_tn_d8063',override(turb[1],'MODE',1))
   aa=rows(si);bb=rows(out);diff=max((abs(x[j]-y[j])/max(abs(x[j]),1e-12) for x,y in zip(aa,bb) for j in [0,2,3,4,5,8,9]),default=float('inf'))
   check('turbine SI US dimensionless agreement',len(aa)==len(bb)==20 and diff<1e-4,{'max_relative_difference':diff,'rule':'1e-4 reflects printed 5 significant digits and published unit constants, not NASA reference tolerance'})
 c,out,e=run('static-design','turbine_tn_d8063',override(override(override(turb[0],'ITEST',1),'ETAD',.86975),'PDSGN',1.79477))
 check('turbine static design',c==0 and not e and out.count('OVERALL PERFORMANCE')==1)
 for label,data in [('lowercase',comp[0].lower()),('slash',comp[0].replace('&END','/')),('dollar',comp[0].replace('&','$')),('comment','! leading comment\n'+comp[0])]:
  c,out,e=run('cards-'+label,'compressor_tn_d7487',data)
  check('namelist syntax '+label,c==0 and not e and triples(out)==ref['compressor']['100'])
if selected('domain'):
 for key,value in [('NVOVCR',16),('GAM',1),('VLDRR',1),('AR',5.1)]:
  c,out,e=run('invalid-'+key,'compressor_tn_d7487',override(comp[0],key,value))
  check('compressor rejects '+key,c==1 and 'INVALID COMPRESSOR INPUT DOMAIN' in e,{'exit':c,'stderr':e[:80]})
 for key,value in [('MODE',6),('DELV',-.05),('G',1),('A1',0)]:
  c,out,e=run('invalid-'+key,'turbine_tn_d8063',override(turb[1],key,value))
  check('turbine rejects '+key,c==1 and 'INVALID TURBINE INPUT DOMAIN' in e,{'exit':c,'stderr':e[:80]})
 c,out,e=run('infeasible-design','turbine_tn_d8063',override(turb[0],'WD',1000))
 check('turbine infeasible design reports failure',c==2 and 'DESIGN FLOW EXCEEDS STATOR CAPACITY' in e,{'exit':c,'stderr':e[:80]})
 failed=turb[0]
 for key,value in [('P0',200000),('T0',1000),('U3',225),('WD',.4),('ETAD',.90),('PDSGN',1.8)]:failed=override(failed,key,value)
 failed+='FAILED DESIGN MUST NOT FEED OFF-DESIGN\nNEW SYNTHETIC CASE\n &IN MODE=0 &END\n'
 c,out,e=run('failed-design-followed-by-offdesign','turbine_tn_d8063',failed)
 check('failed turbine design stops before inherited off-design',c==2 and 'DESIGN TARGETS NOT ACHIEVED' in e and 'OVERALL PERFORMANCE' not in out,{'exit':c,'performance_blocks':out.count('OVERALL PERFORMANCE'),'stderr':e[:160]})
 bad=comp[0]
 for key,value in [('NONDES',.4),('TOP',250),('POP',80000),('AR',1.2),('SPLT',0)]:bad=override(bad,key,value)
 bad=re.sub(r'\bVOVCR=.*?(?=NVOVCR=)','VOVCR='+','.join(format(.05+i*.05,'.3f') for i in range(15))+', ',bad,flags=re.S)
 c,out,e=run('nonphysical-compressor-diffuser','compressor_tn_d7487',bad)
 check('compressor rejects negative diffuser losses',c==2 and 'NONPHYSICAL COMPRESSOR PERFORMANCE' in e,{'exit':c,'stderr':e[:160]})
 bad=turb[1]
 for key,value in [('G',1.6667),('R',99.1976),('U3',350),('T0',600),('XK',0),('PD',.9),('V1',.2),('VMAX',1.2),('DELV',.1),('MODE',1)]:bad=override(bad,key,value)
 c,out,e=run('nonpositive-turbine-work','turbine_tn_d8063',bad)
 check('turbine rejects undefined positive-work parameters',c==2 and 'OUTSIDE POSITIVE-WORK DOMAIN' in e,{'exit':c,'stderr':e[:160]})
 c,out,e=run('bounded-legacy-design','turbine_tn_d8063',(ROOT/'restored/tests/fixtures/turbine_slow_design.inp').read_text())
 check('legacy turbine search has a finite iteration budget',c==2 and 'ITERATION BUDGET EXCEEDED' in e,{'exit':c,'stderr':e[:160]})
if selected('supersonic'):
 data=override(override(override(turb[1],'V1',1.05),'VMAX',1.10),'A5',.02)
 c,out,e=run('supersonic-stator-start','turbine_tn_d8063',data)
 inlet=[float(v) for v in re.findall(r' V/VCR\)0\s+([-+0-9.E]+)',out)]
 check('supersonic stator start has nonzero inlet flow',c==0 and not e and len(inlet)==2 and all(v>0 for v in inlet),{'exit':c,'V0VC0':inlet,'stderr':e[:120]})
(RUN/'results.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2)+'\n')
print('RESULTS',RUN)
sys.exit(0 if all(x['pass'] for x in meta['checks']) else 1)
