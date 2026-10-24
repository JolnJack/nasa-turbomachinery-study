"""Report exact differences; discrepancies always make this command fail.
Same-five-significant-digit observations are classification only, never acceptance.
"""
from pathlib import Path
import argparse,json,subprocess,re,datetime,hashlib,shutil
ROOT=Path(__file__).resolve().parents[2];HERE=Path(__file__).resolve().parent
p=argparse.ArgumentParser();p.add_argument('--source',type=Path,default=ROOT/'restored');p.add_argument('--real64',action='store_true');p.add_argument('--compat27',action='store_true');p.add_argument('--quad',action='store_true');a=p.parse_args()
run=ROOT/'audit/2026-10-23/restoration'/('reference-'+datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ'));run.mkdir()
ref=json.loads((HERE/'reference_full.json').read_text());report={'source':str(a.source),'comparisons':{},'builds':{}}
for prog in ['compressor_tn_d7487','turbine_tn_d8063']:
 src=a.source/('compat27/'+prog+'.f90' if a.compat27 else prog+'.f');cmd=[shutil.which('gfortran'),'-std=legacy','-fno-automatic','-fcheck=all','-ffpe-trap=invalid,zero,overflow',*(['-fdefault-real-16'] if a.quad else (['-fdefault-real-8','-fdefault-double-8'] if (a.real64 or a.compat27) else [])),*(['-ffree-line-length-none'] if a.compat27 else []),str(src),'-o',str(run/prog)]
 
 if (a.source/'read_namelist_cards.f90').exists():cmd.insert(-2,str(a.source/'read_namelist_cards.f90'))
 b=subprocess.run(cmd,capture_output=True);(run/(prog+'.compile.stderr')).write_bytes(b.stderr);assert b.returncode==0
 report['builds'][prog]={'command':cmd,'sha256':hashlib.sha256(src.read_bytes()).hexdigest()}
def execute(label,prog,s):
 (run/(label+'.inp')).write_text(s);p=subprocess.run([str(run/prog)],input=s.encode(),capture_output=True,timeout=8)
 (run/(label+'.stdout')).write_bytes(p.stdout);(run/(label+'.stderr')).write_bytes(p.stderr)
 assert p.returncode==0,(label,p.returncode,p.stderr)
 return p.stdout.decode()
def numbers(s):return list(map(float,re.findall(r'(?<![A-Z0-9])[-+]?(?:\d+\.\d*|\.\d+)(?:E[-+]\d+)?',s)))
def compare(label,want,got,cols=None):
 diffs=[];match=0
 for i,(aa,bb) in enumerate(zip(want,got)):
  for j,(x,y) in enumerate(zip(aa,bb)):
   if x==y:match+=1
   else:diffs.append({'row':i+1,'field':cols[j] if cols else j+1,'expected':x,'actual':y,'delta':y-x,'same_5_significant_digits':format(x,'.5g')==format(y,'.5g')})
 report['comparisons'][label]={'expected_rows':len(want),'actual_rows':len(got),'exact_cells':match,'expected_cells':sum(map(len,want)),'differences':diffs}
 print(label,match,'/',sum(map(len,want)),'exact; rows',len(got),'/',len(want))
 for d in diffs[:3]:print(' ',d)
base=ROOT/'audit/2026-10-22/baseline'
comp=[s.strip()+'&END\n' for s in (base/'compressor_tn_d7487.inp').read_text().split('&END') if s.strip()]
for speed,s in zip(['100','90','80','60'],comp):
 out=execute('compressor-'+speed,'compressor_tn_d7487',s);lines=out.splitlines();vals=[];surge=[]
 for i,l in enumerate(lines):
  if 'WEQ' in l and 'PRESSURE RATIO' in l:vals.append(numbers(lines[i+1])+numbers(lines[i+3]))
  if 'SURGE FLOW RATE' in l:surge=numbers(lines[i+1])
 compare('compressor-'+speed,ref['compressor'][speed],vals,ref['compressor_columns']);compare('surge-choke-'+speed,[ref['surge_choke'][speed]],[surge])
turb=[s.lstrip('\n')+'&END\n' for s in (base/'turbine_tn_d8063.inp').read_text().split('&END') if s.strip()]
def longrows(out):
 lines=out.splitlines();blocks=[]
 for i,l in enumerate(lines):
  if 'VELOCITIES AND ANGLES' in l:blocks.append([numbers(x) for x in lines[i+1:i+7]]+[numbers(x) for x in lines[i+8:i+13]])
 return blocks
out=execute('turbine-design','turbine_tn_d8063',turb[0]);compare('turbine-table-iii',ref['turbine_table_iii'],longrows(out)[0])
coeff=[numbers(l)[-1] for l in out.splitlines() if re.match(r'^\s*(PD\s+[-+0-9.]|K\s+[-+0-9.]|DESIGN WT-FLOW|DESIGN ETA-T|DESIGN P0,/P5,)' ,l)]
compare('turbine-design-coefficients',[ref['turbine_design_coefficients']],[coeff])
for label,data in [('table-II-input',turb[1]),('table-III-coefficients',turb[1].replace('XK=.28699,PD=.98783','XK=.286840,PD=.987836'))]:
 out=execute('turbine-long-'+label,'turbine_tn_d8063',data);blocks=longrows(out)
 compare('turbine-table-iv-'+label,sum(ref['turbine_table_iv'],[]),sum(blocks[:3],[]))
 out=execute('turbine-short-'+label,'turbine_tn_d8063',data.replace('MODE=0','MODE=1'))
 short=[numbers(l) for l in out.splitlines() if len(numbers(l))==10]
 compare('turbine-table-v-'+label,ref['turbine_table_v'],short,ref['turbine_table_v_columns'])
(run/'comparison.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print('RESULTS',run)
raise SystemExit(0 if all(c['exact_cells']==c['expected_cells'] and c['actual_rows']==c['expected_rows'] for c in report['comparisons'].values()) else 1)
