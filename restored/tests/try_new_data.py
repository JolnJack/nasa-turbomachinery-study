"""Run new synthetic inputs; report consistency without inventing NASA truth.

Inputs, diagnostic source copies, builds and failures get a fresh audit folder.
No production equations or original inputs are modified.
"""
from pathlib import Path
import datetime, hashlib, importlib.util, json, math, re, shutil, subprocess, sys

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "restored"
stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
RUN = ROOT / "audit/2026-10-23/restoration" / ("new-data-" + stamp)
RUN.mkdir()


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


gen = module("generator", SRC / "tools/generate_compat27.py")
hist = module("hist_compare", SRC / "tools/compare_historical_turbine.py")
result = {"kind": "synthetic new inputs, no independent experimental truth", "cases": {}, "checks": []}


def check(name, ok, detail=None):
    result["checks"].append({"name": name, "pass": bool(ok), "detail": detail})
    print(("PASS " if ok else "FAIL ") + name, flush=True)


def override(text, name, value):
    pattern = r"(?<![A-Z0-9_])" + name + r"\s*=\s*[-+0-9.E]+"
    assert re.search(pattern, text), name
    return re.sub(pattern, name + "=" + str(value), text)


comp = (SRC / "examples/compressor_original.inp").read_text().split("&END")[0] + "&END\n"
for k, v in {"POP":120000., "TOP":305., "N":68000., "MUO":1.872E-5, "AR":3.2}.items():
    comp = override(comp, k, v)
comp = re.sub(r"\bVOVCR=.*?(?=NVOVCR=)", "VOVCR=" + ",".join(format(.40+i*.02, ".2f") for i in range(15)) + ",\n ", comp, flags=re.S)
turb = """NEW SYNTHETIC TURBINE FORWARD CASE
225 M/S - SI UNITS - LONG OUTPUT
 &IN P0=200000.,T0=1000.,A0=.0120176,A1=.0038008,A3=.0039789,A5=.0044543,
 AL1=72.47,B4=-56.86,U3=225.,U4U3=.567765,R=99.1976,G=1.6667,
 BL1=.95168,BL4=.93718,ZZ=22.,V1=.30,DELV=.05,VMAX=.80,DELY=.05,YMAX=1.40,
 D3=12.6238,D2=12.9997,MODE=0,XK=.30,PD=.985 &END
NEW SYNTHETIC TURBINE FORWARD CASE
225 M/S - SI UNITS - SHORT OUTPUT
 &IN MODE=1 &END
"""
(RUN / "compressor.inp").write_text(comp)
(RUN / "turbine.inp").write_text(turb)
result["input_changes"] = {"compressor":{"POP_Pa":120000,"TOP_K":305,"N_rpm":68000,"MUO_Pa_s":1.872e-5,"AR":3.2,"VOVCR":[.40,.68]},"turbine":{"P0_Pa":200000,"T0_K":1000,"U3_m_s":225,"XK":.30,"PD":.985,"MODE":[0,1],"note":"Forward prediction with specified coefficients; not a successful inverse design or experiment."}}

comp_source = (SRC / "compressor_tn_d7487.f").read_text().replace("      WRITE(6,305) EWF,PR,ETAD", """      WRITE(0,*) 'COMP_AUDIT',SW,EWF,POP,TOP,U2,VU2,U1MF,
     1 VU1MF,DHAERO,DHACT,PR,ETAD,CP,T2P,RHO2,R2G,VM2,D2,B2,
     2 DEIGV,DEINC,DEBL,DESF,DEDF,DERC,DEVLD,DEVD
      WRITE(6,305) EWF,PR,ETAD""")
turb_source = (SRC / "turbine_tn_d8063.f").read_text().replace("   43 PRS= 1./EQPRS", """   43 WRITE(0,*) 'TURB_AUDIT',MODE,G,R,T0,U3,U4U3,VCR,VUVC3,
     1 VU4VC3,T5,DELH,A3,A5,BL4,COSB3,COSB4,W3WC3,W4WC4,
     2 PW4PW3,P4P4ID
      PRS= 1./EQPRS""")


def run_modern(program, model, source, data):
    folder = RUN / (program + "-" + model)
    folder.mkdir()
    code = source if model == "native32" else gen.generate(source, 27, program == "compressor")[0]
    path = folder / ("instrumented.f" if model == "native32" else "instrumented.f90")
    path.write_text(code)
    flags = ["-std=legacy", "-fno-automatic", "-fcheck=all", "-ffpe-trap=invalid,zero,overflow", "-fbacktrace"]
    if model != "native32":
        flags += ["-fdefault-real-16", "-ffree-line-length-none"]
    cmd = [shutil.which("gfortran"), *flags, str(path), str(SRC / "read_namelist_cards.f90"), "-o", str(folder / "program")]
    build = subprocess.run(cmd, capture_output=True)
    (folder / "build.stderr").write_bytes(build.stderr)
    build.check_returncode()
    try:
        p = subprocess.run([str(folder / "program")], input=data.encode(), capture_output=True, timeout=10)
        out, err, rc = p.stdout.decode(), p.stderr.decode(), p.returncode
    except subprocess.TimeoutExpired as e:
        out, err, rc = (e.stdout or b"").decode(), (e.stderr or b"").decode(), "timeout"
    (folder / "stdout").write_text(out)
    (folder / "stderr").write_text(err)
    prefix = "COMP_AUDIT" if program == "compressor" else "TURB_AUDIT"
    rows = [[float(v) for v in line.split()[1:]] for line in err.splitlines() if line.strip().startswith(prefix)]
    unexplained = [line for line in err.splitlines() if line.strip() and not line.strip().startswith(prefix)]
    key = program + "-" + model
    result["cases"][key] = {"command":cmd,"exit":rc,"points":len(rows),"unexpected_stderr":unexplained,"source_sha256":hashlib.sha256(code.encode()).hexdigest()}
    check(key + " completion and finite diagnostics", rc == 0 and bool(rows) and not unexplained and all(math.isfinite(v) for row in rows for v in row))
    return rows, out


def rel(a,b):
    return abs(a-b)/max(abs(b),1e-30)


def flow(x,g):
    return x*(1-(g-1)/(g+1)*x*x)**(1/(g-1))


for model in ["native32", "compat27"]:
    rows, output = run_modern("compressor", model, comp_source, comp)
    values=[]
    for row in rows:
        sw,ewf,p0,t0,u2,vu2,u1,vu1,haero,hact,pr,eta,cp,t2p,rho,rhog,vm2,d2,b2,*loss = row
        values.append({"flow_kg_s":sw,"corrected_flow_kg_s":ewf,"pressure_ratio":pr,"efficiency":eta,"mass_relative_residual":rel(3.14159*rhog*vm2*d2*b2,sw),"euler_relative_residual":rel(u2*vu2-u1*vu1,haero),"thermal_relative_residual":rel(cp*(t2p-t0),haero),"loss_closure_absolute_residual":abs(eta+sum(loss)-1)})
    result["cases"]["compressor-"+model]["observations"] = values
    check("compressor-"+model+" physical ranges", bool(values) and all(v["flow_kg_s"]>0 and v["pressure_ratio"]>1 and 0<v["efficiency"]<=1 for v in values))
    check("compressor-"+model+" mass/energy/loss consistency", bool(values) and all(v["mass_relative_residual"]<=.0011 and max(v["euler_relative_residual"],v["thermal_relative_residual"])<=5e-6 and v["loss_closure_absolute_residual"]<=2e-6 for v in values), "Mass bound follows original 0.001 density iteration tolerance; energy5e-6, loss2e-6. Not experimental accuracy limits.")
    rows, output = run_modern("turbine", model, turb_source, turb)
    values=[]
    for row in rows:
        mode,g,gas,t0,u3,ratio,vcr,vu3,vu4,t5,dh,a3,a5,bl4,cos3,cos4,w3,w4,pw4pw3,loss = row
        mass=rel(a3*flow(w3,g)*cos3,a5*bl4*cos4*pw4pw3*flow(w4,g)*loss)
        values.append({"mass_relative_residual":mass,"euler_relative_residual":rel(u3*vcr*(vu3-ratio*vu4),dh),"thermal_relative_residual":rel(g/(g-1)*gas*(t0-t5),dh)})
    result["cases"]["turbine-"+model]["conservation"] = values
    check("turbine-"+model+" conservation", bool(values) and all(v["mass_relative_residual"]<=3e-5 and max(v["euler_relative_residual"],v["thermal_relative_residual"])<=5e-6 for v in values))
    blocks = hist.blocks(output)
    short = [hist.numbers(line) for line in output.splitlines() if len(hist.numbers(line))==10]
    example=min(blocks,key=lambda b:abs(b[0][0]-.6)) if blocks else None
    result["cases"]["turbine-"+model].update({"long_points":len(blocks),"short_points":len(short),"representative":{"V1VC1":example[0][0],"mass_flow_kg_s":example[6][4],"total_efficiency":example[8][1],"total_pressure_ratio":example[9][2]} if example else None,"short_rows":short})
    check("turbine-"+model+" physical ranges and output counts", len(blocks)==len(short) and bool(short) and all(0<r[4]<=1 and 0<r[5]<=1 and r[8]>1 and r[9]>1 for r in short))

cmd=[sys.executable,str(SRC/"tools/run_historical_turbine.py"),"--portable-formats","--library-source","--formatted-input","--dump-words","--input",str(RUN/"turbine.inp")]
p=subprocess.run(cmd,capture_output=True,text=True,timeout=55)
(RUN/"historical.log").write_text(p.stdout+p.stderr)
match=re.search(r"^RESULTS (.*)$",p.stdout,re.M)
check("turbine historical completion",p.returncode==0 and bool(match))
if match and p.returncode==0:
    folder=Path(match[1]);meta=json.loads((folder/"run.json").read_text());text=(folder/"listing.txt").read_text();blocks=hist.blocks(text);words=hist.word_rows(text,"WORDS");short=[words[i]+words[i+1] for i in range(0,len(words),2)]
    example=min(blocks,key=lambda b:abs(b[0][0]-.6))
    result["cases"]["turbine-historical"]={"command":cmd,"exit":p.returncode,"path":str(folder),"runtime":meta,"coefficients":{"PD":.985,"XK":.30},"long_points":len(blocks),"short_points":len(short),"representative":{"V1VC1":example[0][0],"mass_flow_kg_s":example[6][4],"total_efficiency":example[8][1],"total_pressure_ratio":example[9][2]},"short_rows":short}
    check("turbine historical physical ranges and output counts",len(blocks)==len(short) and bool(short) and all(math.isfinite(x) for row in short for x in row) and all(0<r[4]<=1 and 0<r[5]<=1 and r[8]>1 and r[9]>1 for r in short))
    values=[]
    g,gas,t0,p0,u3,ratio=1.6667,99.1976,1000.,200000.,225.,.567765
    g3=(g-1)/(g+1);g5=g/(g-1);pd=.985
    for b in blocks:
        vcr,vcr5=b[5][1],b[5][3];vu3,vu5=b[1][2],b[3][4]
        dh,t5,p5=b[7][4],b[10][3],b[10][4]
        t3=1-g3*(2*u3*vu3/vcr-(u3/vcr)**2)
        t4=1-g3*(u3/(vcr*math.sqrt(t3)))**2*(1-ratio**2)
        q=vcr5/(vcr*math.sqrt(t3*t4))
        loss=(p5/p0)/(pd*t3**g5*t4**g5*q**(2*g5))
        mass=rel(.0039789*flow(b[3][2],g)*math.cos(b[3][1]*.01745329),.0044543*.93718*math.cos(b[3][3]*.01745329)*t4**((g+1)/(2*(g-1)))*flow(b[0][3],g)*loss)
        values.append({"mass_relative_residual":mass,"euler_relative_residual":rel(u3*(vcr*vu3-ratio*vcr5*vu5),dh),"thermal_relative_residual":rel(g/(g-1)*gas*(t0-t5),dh)})
    result["cases"]["turbine-historical"]["conservation"] = values
    check("turbine historical independent conservation",all(v["mass_relative_residual"]<=3e-5 and max(v["euler_relative_residual"],v["thermal_relative_residual"])<=5e-6 for v in values))

result["production_identity"]={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [SRC/"compressor_tn_d7487.f",SRC/"turbine_tn_d8063.f",ROOT/"turbine_tn_d8063.f",SRC/"tools/generate_compat27.py"]}
result["pass"] = all(row["pass"] for row in result["checks"])
(RUN/"results.json").write_text(json.dumps(result,indent=2)+'\n')
print("RESULTS",RUN)
print("ALL CONSISTENCY CHECKS",result["pass"])
raise SystemExit(0 if result["pass"] else 1)
