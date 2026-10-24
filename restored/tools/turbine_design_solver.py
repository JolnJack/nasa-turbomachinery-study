"""Bounded engineering inverse solver; the FORTRAN forward equations are the oracle.

This is a separate search algorithm, not a claim of historical source identity.
Accepts one complete SI or US namelist. Never uses supplied PD/K as root seeds.
"""
from pathlib import Path
import argparse, hashlib, importlib.util, json, math, re, shutil, subprocess

SRC = Path(__file__).resolve().parents[1]


def override(text, key, value):
    pattern = r"(?i)(?<![A-Z0-9_])" + key + r"\s*=\s*[-+0-9.DEde]+"
    replacement = key + '=' + format(value, '.17g')
    if re.search(pattern, text):
        return re.sub(pattern, replacement, text)
    return re.sub(r'(?i)&END', replacement + ' &END', text)


def fields(text):
    if len(re.findall(r'(?i)&IN\b', text)) != 1:
        raise ValueError('Supply exactly one complete &IN namelist; expand inherited inputs first.')
    return {k.upper():float(v.replace('D','E').replace('d','e')) for k,v in re.findall(r'(?i)\b([A-Z][A-Z0-9]*)\s*=\s*([-+0-9.DE]+)', text)}


def build(folder, model, algebraic=False, full=False):
    folder = Path(folder); folder.mkdir(parents=True, exist_ok=True)
    source = (SRC/'turbine_tn_d8063.f').read_text()
    if algebraic:
        # Eliminate the rotor velocity and K algebraically from Euler work
        # and the original continuity/loss equations. Only PD remains to solve.
        source=source.replace('      Y= .3', """      HDES=ETAD*(1.-PDSGN**(-G2/G))
      Y=((VUVC3-HDES*VCR/(2.*G3*U3))/U4U3
     1-U4U3*U3/VCR)/(SINB4*WCVC3*WC4WC3)
      IF(Y.LE.0..OR.G3*Y*Y.GE.1.) STOP 2
      PWY=SUBR(Y,G)
      PTEMP=YGIV/PWY
      IF(PTEMP.LE.0.) STOP 2
      HINC=W3WC4**2*FS**2
      IF(B3.GT.AB) HINC=W3WC4**2*FS**3
      XK=((1.-PTEMP**(1./G5))*(1.-G3*Y*Y)/G3-HINC)
     1/(Y*Y+W3WC4**2*FC**2)
      GO TO 82
      Y= .3""",1)
    if not full:
        source = source.replace('   40 CONTINUE', """   40 WRITE(6,*) 'DESIGN_EVAL',W1,ETAT,ETAS,Z,Z1,PD,XK,V1VC1
      STOP
      CONTINUE""", 1)
    else:
        source=source.replace('   43 PRS= 1./EQPRS', """   43 WRITE(0,*) 'DESIGN_STATE',MODE,G,R,T0,U3,U4U3,VCR,VUVC3,
     1 VU4VC3,T5,DELH,A3,A5,BL4,COSB3,COSB4,W3WC3,W4WC4,
     2 PW4PW3,P4P4ID,W1,ETAT,ETAS,Z,Z1,PD,XK,V1VC1,
     3 W3WC4,FS,FC,B3,AB
      PRS= 1./EQPRS""",1)
    flags = ['-std=legacy','-fno-automatic','-fcheck=all','-ffpe-trap=invalid,zero,overflow']
    if model == 'compat27':
        spec=importlib.util.spec_from_file_location('inverse_generator',SRC/'tools/generate_compat27.py')
        gen=importlib.util.module_from_spec(spec);spec.loader.exec_module(gen)
        source=gen.generate(source,27,False)[0]
        flags+=['-fdefault-real-16','-ffree-line-length-none']
    name=('algebraic-full' if algebraic else 'forward-full') if full else ('algebraic' if algebraic else 'evaluator')
    path=folder/(name+('.f90' if model=='compat27' else '.f'));path.write_text(source)
    command=[shutil.which('gfortran'),*flags,str(path),str(SRC/'read_namelist_cards.f90'),'-o',str(folder/name)]
    result=subprocess.run(command,capture_output=True)
    (folder/(name+'.build.stderr')).write_bytes(result.stderr)
    (folder/(name+'.build.json')).write_text(json.dumps({'command':command,'sha256':hashlib.sha256(source.encode()).hexdigest(),'exit':result.returncode},indent=2)+'\n')
    result.check_returncode()
    if not algebraic and not full:
        build(folder,model,True)
        build(folder,model,False,True)
    if algebraic and not full:build(folder,model,True,True)
    return folder/name


def solve(text, executable, max_evaluations=240):
    f=fields(text)
    required=['MODE','ITEST','G','R','P0','T0','A1','AL1','WD','ETAD','PDSGN']
    if any(k not in f for k in required):
        raise ValueError('Missing explicit design fields: '+','.join(k for k in required if k not in f))
    if f['MODE'] not in (2,5) or f['ITEST'] not in (1,2):
        raise ValueError('Expected design MODE=2 or 5 and ITEST=1 or 2.')
    if not all(math.isfinite(x) for x in f.values()):raise ValueError('Nonfinite input')
    if min(f['WD'],f['P0'],f['T0'],f['R'],f['A1'])<=0 or f['G']<=1 or not 0<f['ETAD']<=1 or f['PDSGN']<=1:
        raise ValueError('Invalid design target or thermodynamic input')
    g=f['G']; q=(g-1)/(g+1); us=f['MODE']==5
    capacity=f['P0']*math.sqrt(2*g/(g+1)*(32.1741 if us else 1)/(f['R']*f['T0']))*f['A1']*math.cos(f['AL1']*.01745329)
    flow=lambda v:v*(1-q*v*v)**(1/(g-1))
    pdmin=f['WD']/(capacity*flow(1)) if capacity>0 else math.inf
    if pdmin>=1:
        return {'status':'stator-capacity-boundary-or-exceeded','evaluations':0,'PD_min':pdmin,'trace':[]}
    low=max(pdmin*(1+2e-6),1e-6)
    trace=[];cache={};best=None;budget=False
    def evaluate(pd,k):
        nonlocal best,budget
        pd=min(1.,max(low,pd));k=max(0.,k);key=(round(pd,13),round(k,13))
        if key in cache:return cache[key]
        if len(trace)>=max_evaluations:budget=True;return None
        target=f['WD']/(capacity*pd);a=0.;b=1.
        for _ in range(55):
            mid=(a+b)/2
            if flow(mid)<target:a=mid
            else:b=mid
        v1=(a+b)/2;data=text
        for name,value in [('MODE',3 if us else 0),('PD',pd),('XK',k),('V1',v1),('VMAX',v1)]:data=override(data,name,value)
        record={'PD':pd,'XK':k,'requested_V1':v1}
        try:
            run=subprocess.run([str(executable)],input=data.encode(),capture_output=True,timeout=.5)
            record.update(exit=run.returncode,stderr=run.stderr.decode(errors='replace')[:400])
            row=next(([float(x) for x in line.split()[1:]] for line in run.stdout.decode().splitlines() if line.strip().startswith('DESIGN_EVAL')),None)
            record['forward']=row
            if run.returncode==0 and row and len(row)==8 and all(math.isfinite(x) for x in row):
                mass,etat,etas,z,z1,actualpd,actualk,actualv=row
                eta=etat if f['ITEST']==2 else etas;pr=z if f['ITEST']==2 else z1
                if mass>0 and 0<etat<=1.00001 and 0<etas<=1.00001 and min(z,z1)>1 and abs(mass/f['WD']-1)<3e-5:
                    residual=[eta-f['ETAD'],math.log(pr/f['PDSGN'])]
                    record['residual']=residual
                    record['errors']=[abs(mass/f['WD']-1),abs(residual[0]),abs(pr/f['PDSGN']-1)]
                    record['objective']=sum(x*x for x in residual)
                    if best is None or record['objective']<best['objective']:best=record
        except subprocess.TimeoutExpired:record['exit']='timeout'
        trace.append(record)
        cache[key]=record if 'residual' in record else None
        return cache[key]
    # Deterministic generic seeds, independent of any supplied/known-root PD and K.
    seeds=[(.98,.1),(.94,.5),(1.,0.),(.90,.7),(.99,1.5),((1+low)/2,.03)]
    for seedpd,seedk in seeds:
        current=evaluate(seedpd,seedk)
        if current is None:continue
        for iteration in range(22):
            if max(current['errors'][1:])<=2e-5:break
            pd=current['PD'];k=current['XK'];res=current['residual']
            hp=5e-4;hk=5e-4*max(1,k)
            pp=evaluate(pd+hp if pd+hp<=1 else pd-hp,k)
            pk=evaluate(pd,k+hk)
            if pp is None:pp=evaluate(pd-hp,k)
            if pk is None and k>=hk:pk=evaluate(pd,k-hk)
            if pp is None or pk is None:break
            dp=pp['PD']-pd;dk=pk['XK']-k
            a=(pp['residual'][0]-res[0])/dp;b=(pk['residual'][0]-res[0])/dk
            c=(pp['residual'][1]-res[1])/dp;d=(pk['residual'][1]-res[1])/dk
            det=a*d-b*c
            if abs(det)<1e-12:break
            sp=(-d*res[0]+b*res[1])/det;sk=(c*res[0]-a*res[1])/det
            scale=max(1,abs(sp)/.12,abs(sk)/max(.5,k));sp/=scale;sk/=scale
            improved=None
            for alpha in [1.,.5,.25,.125,.0625,.03125,.015625,.0078125,.00390625,.001953125,.0009765625]:
                trial=evaluate(pd+alpha*sp,k+alpha*sk)
                if trial and trial['objective']<current['objective']:
                    improved=trial;break
            if improved is None:break
            current=improved
        if best and max(best['errors'][1:])<=2e-5:break
        if budget:break
    # Near rotor choking, a finite-difference Jacobian can become singular.
    # Use the algebraically reduced original equations, then require a fresh
    # execution of the ordinary FORTRAN forward solver to accept the root.
    if not best or not all(a<=b for a,b in zip(best['errors'],[3e-5,1e-4,1e-4])):
        algebra=Path(executable).with_name('algebraic');atrials=[]
        def reduced(pd):
            target=f['WD']/(capacity*pd);a=0.;b=1.
            for _ in range(55):
                mid=(a+b)/2
                if flow(mid)<target:a=mid
                else:b=mid
            data=text;v1=(a+b)/2
            for name,value in [('MODE',3 if us else 0),('PD',pd),('XK',0),('V1',v1),('VMAX',v1)]:data=override(data,name,value)
            record={'stage':'algebraic-reduction','PD':pd}
            try:
                r=subprocess.run([str(algebra)],input=data.encode(),capture_output=True,timeout=.5)
                row=next(([float(x) for x in line.split()[1:]] for line in r.stdout.decode().splitlines() if line.strip().startswith('DESIGN_EVAL')),None)
                record.update(exit=r.returncode,forward=row)
                if r.returncode==0 and row and all(math.isfinite(x) for x in row) and row[3]>0 and row[4]>0:
                    residual=(row[3] if f['ITEST']==2 else row[4])/f['PDSGN']-1
                    record['pressure_residual']=residual
            except subprocess.TimeoutExpired:record['exit']='timeout'
            trace.append(record);atrials.append(record)
            return record if 'pressure_residual' in record else None
        trials=[reduced(low+(1-low)*i/48) for i in range(49)]
        valid=[r for r in trials if r is not None]
        candidates=[r for r in valid if abs(r['pressure_residual'])<2e-6]
        for left,right in zip(valid,valid[1:]):
            if left['pressure_residual']*right['pressure_residual']>=0:continue
            for _ in range(32):
                mid=reduced((left['PD']+right['PD'])/2)
                if mid is None:break
                if abs(mid['pressure_residual'])<2e-6:
                    candidates.append(mid);break
                if left['pressure_residual']*mid['pressure_residual']<0:right=mid
                else:left=mid
        for candidate in sorted(candidates,key=lambda r:abs(r['pressure_residual'])):
            row=candidate['forward']
            if not 0<row[5]<=1.00001 or row[6]<0:continue
            # Ordinary solver must independently reproduce this candidate.
            budget=False;max_evaluations=max(max_evaluations,len(trace)+1)
            confirmed=evaluate(row[5],row[6])
            if confirmed and all(a<=b for a,b in zip(confirmed['errors'],[3e-5,1e-4,1e-4])):
                best=confirmed;break
            # The legacy CONTIN iteration itself can select an inaccurate
            # near-choke root. Validate the algebraic state against the loss,
            # mass and energy equations, preserving that legacy discrepancy.
            data=text
            for name,value in [('MODE',3 if us else 0),('PD',row[5]),('XK',row[6]),('V1',row[7]),('VMAX',row[7])]:data=override(data,name,value)
            try:
                rr=subprocess.run([str(Path(executable).with_name('algebraic-full'))],input=data.encode(),capture_output=True,timeout=.5)
                state=next(([float(x) for x in line.split()[1:]] for line in rr.stderr.decode().splitlines() if line.strip().startswith('DESIGN_STATE')),None)
            except subprocess.TimeoutExpired:continue
            if rr.returncode or state is None or not all(math.isfinite(x) for x in state):continue
            mode,gg,gas,t0,u3,ratio,vcr,vu3,vu4,t5,dh,a3,a5,bl4,cos3,cos4,w3,w4,pw4pw3,loss,mass,etat,etas,z,z1,pd,xk,v1,w3w4,fs,fc,b3,ab=state
            shape=lambda v:v*(1-(gg-1)/(gg+1)*v*v)**(1/(gg-1))
            relative=lambda a,b:abs(a-b)/max(abs(b),1e-30)
            upstream=a3*shape(w3)*cos3;downstream=a5*bl4*cos4*pw4pw3*shape(w4)*loss
            euler=u3*vcr*(vu3-ratio*vu4)/(32.1741*778.029 if us else 1)
            thermal=gg/(gg-1)*gas*(t0-t5)/(778.029 if us else 1)
            cx=w3w4*w3w4*(xk*fc*fc+fs**(3 if b3>ab else 2))
            predicted_loss=(1-(gg-1)/(gg+1)*(xk*w4*w4+cx)/(1-(gg-1)/(gg+1)*w4*w4))**(gg/(gg-1))
            conservation=[relative(upstream,downstream),relative(euler,dh),relative(thermal,dh),relative(loss,predicted_loss)]
            errors=[relative(mass,f['WD']),abs((etat if f['ITEST']==2 else etas)-f['ETAD']),relative(z if f['ITEST']==2 else z1,f['PDSGN'])]
            record={'stage':'algebraic-validated','PD':pd,'XK':xk,'forward':[mass,etat,etas,z,z1,pd,xk,v1],'errors':errors,'objective':sum(x*x for x in errors[1:]),'equation_residuals':conservation,'ordinary_forward_confirmation':confirmed,'full_stdout':rr.stdout.decode(),'full_stderr':rr.stderr.decode(),'validated_input':data}
            trace.append(record)
            if min(mass,dh,etat,etas)>0 and max(etat,etas)<=1 and min(z,z1)>1 and xk>=0 and 0<pd<=1 and all(a<=b for a,b in zip(errors,[3e-5,1e-4,1e-4])) and all(a<=b for a,b in zip(conservation,[3e-5,5e-6,5e-6,3e-5])):
                best=record;break
    status='matched' if best and all(a<=b for a,b in zip(best['errors'],[3e-5,1e-4,1e-4])) else 'unresolved-search'
    result={'status':status,'evaluations':len(trace),'PD_min':pdmin,'best':best,'trace':trace,'method':'bounded damped Newton; algebraic reduction near choking; ordinary forward solver comparison retained; alternate states require independent mass, Euler/thermal energy and empirical loss residual checks; no known-root coefficients used'}
    if status=='matched':
        data=text
        for name,value in [('MODE',3 if us else 0),('PD',best['PD']),('XK',best['XK']),('V1',best['forward'][-1]),('VMAX',best['forward'][-1])]:data=override(data,name,value)
        result['forward_input']=best.get('validated_input',data)
        result['replay_backend']='algebraic-full' if best.get('stage')=='algebraic-validated' else 'forward-full'
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--input',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--model',choices=['native32','compat27'],default='compat27');a=p.parse_args()
    a.output.mkdir(parents=True,exist_ok=False)
    executable=build(a.output,a.model)
    result=solve(a.input.read_text(),executable)
    (a.output/'result.json').write_text(json.dumps(result,indent=2)+'\n')
    if 'forward_input' in result:
        filename='equation-input.inp' if result['replay_backend']=='algebraic-full' else 'solved.inp'
        (a.output/filename).write_text(result['forward_input'])
    if (result.get('best') or {}).get('stage')=='algebraic-validated':
        (a.output/'computed-output.txt').write_text(result['best']['full_stdout'])
        (a.output/'equation-audit.txt').write_text(result['best']['full_stderr'])
    elif result['status']=='matched':
        replay=subprocess.run([str(executable.with_name('forward-full'))],input=result['forward_input'].encode(),capture_output=True,timeout=2)
        (a.output/'computed-output.txt').write_bytes(replay.stdout)
        (a.output/'equation-audit.txt').write_bytes(replay.stderr)
        state=next(([float(x) for x in line.split()[1:]] for line in replay.stderr.decode().splitlines() if line.strip().startswith('DESIGN_STATE')),None)
        target=fields(a.input.read_text())
        errors=[] if state is None else [abs(state[20]/target['WD']-1),abs(state[21 if target['ITEST']==2 else 22]-target['ETAD']),abs(state[23 if target['ITEST']==2 else 24]/target['PDSGN']-1)]
        result['full_output_replay']={'exit':replay.returncode,'errors':errors}
        if replay.returncode or len(errors)!=3 or not all(x<=b for x,b in zip(errors,[3e-5,1e-4,1e-4])):result['status']='full-output-replay-mismatch'
        (a.output/'result.json').write_text(json.dumps(result,indent=2)+'\n')
    print(result['status'],result['evaluations'],str(a.output))
    raise SystemExit(0 if result['status']=='matched' else 2)


if __name__=='__main__':main()
