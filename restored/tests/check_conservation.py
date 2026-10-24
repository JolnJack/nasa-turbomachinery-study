"""Independent rotor mass-continuity and Euler energy checks on diagnostic copies."""
from pathlib import Path
import importlib.util,subprocess,shutil,json,datetime,math
ROOT=Path(__file__).resolve().parents[2];SRC=ROOT/'restored'
run=ROOT/'audit/2026-10-23/restoration'/('conservation-'+datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ'));run.mkdir()
source=(SRC/'turbine_tn_d8063.f').read_text().replace('   43 PRS= 1./EQPRS', '''   43 WRITE(0,*) 'AUDIT',MODE,G,R,T0,U3,U4U3,VCR,VUVC3,VU4VC3,
     1 T5,DELH,A3,A5,BL4,COSB3,COSB4,W3WC3,W4WC4,PW4PW3,P4P4ID
      PRS= 1./EQPRS''')
assert source!=(SRC/'turbine_tn_d8063.f').read_text()
spec=importlib.util.spec_from_file_location('generate',SRC/'tools/generate_compat27.py');gen=importlib.util.module_from_spec(spec);spec.loader.exec_module(gen)
report={}
for model in ['native32','compat27']:
 text=source if model=='native32' else gen.generate(source,27,False)[0]
 path=run/('instrumented-'+model+('.f' if model=='native32' else '.f90'));path.write_text(text)
 flags=['-std=legacy','-fno-automatic','-fcheck=all','-ffpe-trap=invalid,zero,overflow']
 if model=='compat27':flags+=['-fdefault-real-16','-ffree-line-length-none']
 cmd=[shutil.which('gfortran'),*flags,str(path),str(SRC/'read_namelist_cards.f90'),'-o',str(run/model)]
 b=subprocess.run(cmd,capture_output=True);(run/(model+'.build.stderr')).write_bytes(b.stderr);assert b.returncode==0,b.stderr
 inp=(ROOT/'turbine_tn_d8063.inp').read_bytes();r=subprocess.run([str(run/model)],input=inp,capture_output=True,timeout=8)
 (run/(model+'.stdout')).write_bytes(r.stdout);(run/(model+'.stderr')).write_bytes(r.stderr)
 observations=[]
 for line in r.stderr.decode().splitlines():
  if not line.strip().startswith('AUDIT'):continue
  values=list(map(float,line.split()[1:]));mode,g,gas,t0,u3,ratio,vcr,vu3,vu4,t5,dh,a3,a5,bl4,cos3,cos4,w3,w4,pw4pw3,loss=values
  def flow(x):return x*(1-(g-1)/(g+1)*x*x)**(1/(g-1))
  upstream=a3*flow(w3)*cos3;downstream=a5*bl4*cos4*pw4pw3*flow(w4)*loss
  mass=abs(upstream-downstream)/max(abs(upstream),1e-30)
  euler=u3*vcr*(vu3-ratio*vu4)
  if mode>=3:euler/=32.1741*778.029
  energy=abs(euler-dh)/max(abs(dh),1e-30)
  cp=g/(g-1)*gas
  if mode>=3:cp/=778.029
  thermal=abs(cp*(t0-t5)-dh)/max(abs(dh),1e-30)
  observations.append({'mode':mode,'mass_relative_residual':mass,'euler_relative_residual':energy,'thermal_relative_residual':thermal})
 maxmass=max((x['mass_relative_residual'] for x in observations),default=math.inf);maxenergy=max((max(x['euler_relative_residual'],x['thermal_relative_residual']) for x in observations),default=math.inf)
 row={'exit':r.returncode,'points':len(observations),'max_mass_relative_residual':maxmass,'max_energy_relative_residual':maxenergy,'pass':r.returncode==0 and len(observations)>=61 and maxmass<3e-5 and maxenergy<5e-6,'rules':'Mass <=3e-5: source root tolerance 1e-5 plus single-real rounding. Energy <=5e-6: printed audit operands/single-real cancellation. These are conservation checks, not tolerances for NASA printed-table acceptance.','observations':observations,'command':cmd}
 report[model]=row;print(model,{k:v for k,v in row.items() if k not in ['observations','rules','command']})
(run/'results.json').write_text(json.dumps(report,indent=2)+'\n');print('RESULTS',run)
raise SystemExit(0 if all(x['pass'] for x in report.values()) else 1)
