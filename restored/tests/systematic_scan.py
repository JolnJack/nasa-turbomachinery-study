"""Declared finite-grid scan. Preserve every classification, including failures."""
from pathlib import Path
import argparse, concurrent.futures, datetime, gzip, hashlib, importlib.util
import itertools, json, math, re, shutil, subprocess, time

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "restored"


def load_generator():
    spec = importlib.util.spec_from_file_location("scan_generator", SRC / "tools/generate_compat27.py")
    gen = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gen)
    return gen


def override(text, name, value):
    pattern = r"(?<![A-Z0-9_])" + name + r"\s*=\s*[-+0-9.Ee]+"
    replacement = name + "=" + str(value)
    if re.search(pattern, text):
        return re.sub(pattern, replacement, text)
    return text.replace("&END", replacement + " &END")


def flow(x, g):
    return x * (1 - (g - 1) / (g + 1) * x * x) ** (1 / (g - 1))


def relative(a, b):
    return abs(a - b) / max(abs(b), 1e-30)


def build(run, models=('native32','compat27')):
    comp = (SRC / "compressor_tn_d7487.f").read_text().replace("      WRITE(6,305) EWF,PR,ETAD", """      WRITE(0,*) 'COMP_AUDIT',SW,EWF,POP,TOP,U2,VU2,U1MF,
     1 VU1MF,DHAERO,DHACT,PR,ETAD,CP,T2P,RHO2,R2G,VM2,D2,B2,
     2 DEIGV,DEINC,DEBL,DESF,DEDF,DERC,DEVLD,DEVD
      WRITE(6,305) EWF,PR,ETAD""")
    turb = (SRC / "turbine_tn_d8063.f").read_text().replace("   43 PRS= 1./EQPRS", """   43 WRITE(0,*) 'TURB_AUDIT',MODE,G,R,T0,U3,U4U3,VCR,VUVC3,
     1 VU4VC3,T5,DELH,A3,A5,BL4,COSB3,COSB4,W3WC3,W4WC4,
     2 PW4PW3,P4P4ID,W1,ETAT,ETAS,Z,Z1,PD,XK,V1VC1
      PRS= 1./EQPRS""")
    gen = load_generator()
    paths = {}
    records = []
    for name, text in [("compressor", comp), ("turbine", turb)]:
        for model in models:
            folder = run / (name + "-" + model)
            folder.mkdir(exist_ok=True)
            code = gen.generate(text, 27, name == "compressor")[0] if model == "compat27" else text
            source = folder / ("scan.f90" if model == "compat27" else "scan.f")
            source.write_text(code)
            flags = ["-std=legacy", "-fno-automatic", "-fcheck=all", "-ffpe-trap=invalid,zero,overflow", "-fbacktrace"]
            if model == "compat27":
                flags += ["-fdefault-real-16", "-ffree-line-length-none"]
            if model == "modern64":
                flags += ["-fdefault-real-8", "-fdefault-double-8"]
            cmd = [shutil.which("gfortran"), *flags, str(source), str(SRC / "read_namelist_cards.f90"), "-o", str(folder / "program")]
            p = subprocess.run(cmd, capture_output=True)
            (folder / "build.stderr").write_bytes(p.stderr)
            p.check_returncode()
            paths[name, model] = folder / "program"
            records.append({"program":name,"model":model,"command":cmd,"sha256":hashlib.sha256(code.encode()).hexdigest()})
    (run / "builds.json").write_text(json.dumps(records, indent=2) + "\n")
    return paths


def cases():
    comp = (SRC / "examples/compressor_original.inp").read_text().split("&END")[0] + "&END\n"
    turb = (SRC / "examples/turbine_original.inp").read_text().split("&END")[1].lstrip("\n") + "&END\n"
    records = []
    def add(program, group, text, parameters):
        records.append({"id":f"{len(records):05d}","program":program,"group":group,"input":text,"parameters":parameters})
    def cdata(parameters, start):
        text = comp
        for key, value in parameters.items():
            text = override(text, key, value)
        array = ",".join(format(start + i * .05, ".4f") for i in range(15))
        return re.sub(r"\bVOVCR=.*?(?=NVOVCR=)", "VOVCR=" + array + ",\n ", text, flags=re.S)
    for speed, temp, pressure, ar, splt in itertools.product([.4,.6,.8,1.,1.1],[250.,288.15,350.],[80000.,101325.,200000.],[1.2,2.,2.7,3.,3.2,4.,5.],[0,1]):
        parameters = dict(NONDES=speed, TOP=temp, POP=pressure, AR=ar, SPLT=splt)
        for start in [.05,.50]:
            add("compressor", "primary-grid", cdata(parameters,start), dict(parameters, velocity_start=start, velocity_step=.05, velocity_count=15))
    supplements = {"B1MFB":[40.,50.,60.],"Z":[16.,48.],"AL1MF":[-10.,5.,10.,20.],"CURVH":[.05,.1],"CURVT":[.05,.1],"MUO":[1.2e-5,2.4e-5],"VLDRR":[1.05,1.3,1.6],"BLOCK":[.75,1.],"B2X":[0.,15.,40.]}
    for key, values in supplements.items():
        for value in values:
            for start in [.05,.5]:
                add("compressor", "one-axis-supplement", cdata({key:value},start), {key:value,"velocity_start":start})
    for g, gas in [(1.4,287.05),(1.6667,99.1976)]:
        for u3,temp,xk,pd in itertools.product([100.,180.,237.9524,350.],[600.,1000.,1400.],[0.,.03,.3,.7],[.9,.98,1.]):
            parameters=dict(G=g,R=gas,U3=u3,T0=temp,XK=xk,PD=pd,V1=.2,VMAX=1.2,DELV=.1,MODE=1)
            text=turb
            for k,v in parameters.items():text=override(text,k,v)
            add("turbine","primary-grid",text,parameters)
    supplements={"A0":[.008,.02],"A1":[.0028,.005],"A3":[.003,.005],"A5":[.003,.006],"AL1":[60.,80.],"B4":[-40.,-70.],"BL1":[.85,1.],"BL4":[.85,1.],"V1":[1.05,1.2]}
    for k, values in supplements.items():
        for value in values:
            text=override(override(turb,k,value),'MODE',1)
            if k=='V1':text=override(text,'VMAX',value+.1);text=override(text,'A5',.02)
            add("turbine","one-axis-supplement",text,{k:value})
    # Explicitly invalid inputs must be rejected, not treated as valid performance.
    for program, text, invalid in [
        ("compressor",comp,{"NVOVCR":[0,16],"GAM":[1],"POP":[0],"TOP":[0],"N":[0],"MUO":[0],"RGAS":[0],"DIT":[0],"B2":[0],"DRAT":[0],"LAMX":[0,1],"Z":[0],"AR":[1.1999,5.0001],"VLDRR":[1],"ADTH":[0],"CF":[-.1],"BLOCK":[0,1.01],"SPLT":[2],"NONDES":[0]}),
        ("turbine",turb,{"G":[1],"P0":[0],"T0":[0],"R":[0],"A0":[0],"A1":[0],"A3":[0],"A5":[0],"D2":[0],"D3":[0],"U3":[0],"U4U3":[0,1],"BL1":[0,1.01],"BL4":[0,1.01],"AL1":[90],"B4":[-90],"V1":[0],"DELV":[0,-.1],"DELY":[0],"YMAX":[0],"MODE":[-1,6],"PD":[0,1.01],"XK":[-.1]})]:
        for key,values in invalid.items():
            for value in values:add(program,"invalid-domain",override(text,key,value),{key:value})
    return records


def inspect(program, out, err, rc):
    prefix = "COMP_AUDIT" if program == "compressor" else "TURB_AUDIT"
    rows=[]
    for line in err.splitlines():
        if line.strip().startswith(prefix):
            rows.append([float(x) for x in line.split()[1:]])
    if rc == "timeout":return "timeout", rows, {}
    if isinstance(rc,int) and rc < 0:return "abnormal-exit", rows, {}
    if rc != 0:
        explicit=any(x in err for x in ["INVALID ","DESIGN FLOW EXCEEDS","DESIGN TARGETS NOT ACHIEVED","NONPHYSICAL COMPRESSOR PERFORMANCE","OUTSIDE POSITIVE-WORK DOMAIN","ITERATION BUDGET EXCEEDED"])
        return ("explicit-rejection" if explicit else "unexplained-exit"), rows, {}
    if not all(math.isfinite(x) for row in rows for x in row):return "nonfinite", rows, {}
    if not rows:return "no-performance-output", rows, {}
    residuals=[];physical=True
    for row in rows:
        if program == "compressor":
            sw,ewf,p0,t0,u2,vu2,u1,vu1,haero,hact,pr,eta,cp,t2p,rho,rhog,vm2,d2,b2,*loss=row
            residuals.append([relative(3.14159*rhog*vm2*d2*b2,sw),relative(u2*vu2-u1*vu1,haero),relative(cp*(t2p-t0),haero),abs(eta+sum(loss)-1)])
            physical &= sw>0 and pr>1 and 0<eta<=1
        else:
            mode,g,gas,t0,u3,ratio,vcr,vu3,vu4,t5,dh,a3,a5,bl4,cos3,cos4,w3,w4,pw4pw3,loss,*extra=row
            residuals.append([relative(a3*flow(w3,g)*cos3,a5*bl4*cos4*pw4pw3*flow(w4,g)*loss),relative(u3*vcr*(vu3-ratio*vu4),dh),relative(g/(g-1)*gas*(t0-t5),dh)])
            mass,etat,etas,z,z1,pd,xk,v1=extra
            physical &= mass>0 and dh>0 and 0<etat<=1 and 0<etas<=1 and z>1 and z1>1
    maxima=[max(x[i] for x in residuals) for i in range(len(residuals[0]))]
    bounds=[.0011,5e-6,5e-6,2e-6] if program=='compressor' else [3e-5,5e-6,5e-6]
    if not physical:return "outside-positive-work-range",rows,{"max_residuals":maxima}
    if any(a>b for a,b in zip(maxima,bounds)):return "conservation-failure",rows,{"max_residuals":maxima}
    if re.search(r"NO SOLUTION|NEGATIVE TEMPERATURE|RESTARTED",out):return "model-diagnostic",rows,{"max_residuals":maxima}
    return "consistent-performance",rows,{"max_residuals":maxima}


def execute(run, paths, case, model, timeout=2.):
    start=time.monotonic();key=case['id']+'-'+model
    folder=run/'records';folder.mkdir(exist_ok=True)
    try:
        p=subprocess.run([str(paths[case['program'],model])],input=case['input'].encode(),capture_output=True,timeout=timeout)
        out,err,rc=p.stdout,p.stderr,p.returncode
    except subprocess.TimeoutExpired as e:
        out,err,rc=e.stdout or b'',e.stderr or b'','timeout'
    (folder/(key+'.stdout.gz')).write_bytes(gzip.compress(out))
    (folder/(key+'.stderr.gz')).write_bytes(gzip.compress(err))
    try:category,rows,metrics=inspect(case['program'],out.decode(errors='replace'),err.decode(errors='replace'),rc)
    except Exception as e:category,rows,metrics='inspection-error',[],{'error':repr(e)}
    return {'id':case['id'],'program':case['program'],'group':case['group'],'model':model,'exit':rc,'category':category,'points':len(rows),'elapsed_s':time.monotonic()-start,'metrics':metrics,'rows':rows,'input_sha256':hashlib.sha256(case['input'].encode()).hexdigest()}


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--resume',type=Path)
    parser.add_argument('--workers',type=int,default=4)
    parser.add_argument('--limit',type=int)
    parser.add_argument('--models',nargs='+',choices=['native32','compat27','modern64'],default=['native32','compat27'])
    a=parser.parse_args()
    run=a.resume or ROOT/'audit/2026-10-23/restoration'/('systematic-'+datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ'))
    run.mkdir(exist_ok=True)
    data=cases()
    if a.limit:data=data[:a.limit]
    path=run/'cases.json'
    if path.exists():assert json.loads(path.read_text())==data
    else:path.write_text(json.dumps(data,indent=2)+'\n')
    paths=build(run,a.models)
    previous=[]
    if (run/'results.jsonl').exists():previous=[json.loads(x) for x in (run/'results.jsonl').read_text().splitlines()]
    done={(x['id'],x['model']) for x in previous};results=list(previous)
    jobs=[(c,m) for c in data for m in a.models if (c['id'],m) not in done]
    print('RESULTS',run,flush=True);print('PLANNED',len(data)*len(a.models),'remaining',len(jobs),flush=True)
    with (run/'results.jsonl').open('a') as stream,concurrent.futures.ThreadPoolExecutor(max_workers=a.workers) as pool:
        futures=[pool.submit(execute,run,paths,c,m) for c,m in jobs]
        for f in concurrent.futures.as_completed(futures):
            row=f.result();results.append(row);stream.write(json.dumps(row)+'\n');stream.flush()
            if len(results)%100==0:print('COMPLETED',len(results),flush=True)
    categories={}
    for row in results:
        key=row['program']+'/'+row['model'];d=categories.setdefault(key,{});d[row['category']]=d.get(row['category'],0)+1
    summary={'planned_runs':len(data)*len(a.models),'completed_runs':len(results),'categories':categories,'timeout_s':2,'models':a.models,'notes':'Full declared finite grid, not proof of an infinite continuous domain. All classifications retained; non-performance/rejection is not performance success.'}
    (run/'summary.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary,indent=2),flush=True)


if __name__=='__main__':main()
