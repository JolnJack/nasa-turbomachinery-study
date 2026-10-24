"""Isolated turbine diagnostics; never change delivery sources or reference tables.

Trace checkpoints are observations of local arithmetic models, not recovered
historical intermediate values. NASA's printed report has no iteration trace.
"""
from pathlib import Path
import datetime, hashlib, importlib.util, json, re, shutil, subprocess

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
spec = importlib.util.spec_from_file_location("compat", HERE / "generate_compat27.py")
compat = importlib.util.module_from_spec(spec)
spec.loader.exec_module(compat)


def instrument(text):
    output = []
    stages = {
        "VCR=": ("critical", "VCR,PVCR"),
        "W1=": ("flow", "V1VC1,PD,W1"),
        "VRVC2=": ("stator", "X,X1,F,FP"),
        "VRVC3=": ("rotor-inlet", "X,X1,V3VC3,AL3"),
        "YGIV=": ("rotor-demand", "YGIV,W3WC4,FS,FC"),
        "YCAL=": ("rotor-iterate", "NCOUNT,XK,Y,YCAL,YGIV,IND"),
        "AL5=": ("exit-angle", "AL5,VUVC5,V5VC5,WXWC5,X,X1,T"),
    }
    for line in text.splitlines():
        bare = re.sub(r"^\d+\s+", "", line.strip())
        if bare.startswith("CALL GETK("):
            output.append("WRITE(0,*) 'TRACE getk-before',K,XK,ET,ETAD,PD")
        if bare.startswith("CALL SEEKPR("):
            output.append("WRITE(0,*) 'TRACE seekpr-before',L,PD,PR,PDSGN,XK")
        if bare.startswith("WRITE(6,509)"):
            output.append("WRITE(0,*) 'TRACE design-final',PD,XK,ETAT,ETAS,Z,Z1,AL5")
        output.append(line)
        for start, (name, values) in stages.items():
            if bare.startswith(start):
                output.append(f"WRITE(0,*) 'TRACE {name}',{values}")
        if bare.startswith("CALL GETK("):
            output.append("WRITE(0,*) 'TRACE getk-after',K,XK")
        if bare.startswith("CALL SEEKPR("):
            output.append("WRITE(0,*) 'TRACE seekpr-after',L,PD")
    return "\n".join(output) + "\n"


def main():
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    run = ROOT / "audit/2026-10-23/restoration" / ("turbine-trace-" + stamp)
    run.mkdir()
    source = (ROOT / "restored/turbine_tn_d8063.f").read_text()
    inp = (ROOT / "restored/examples/turbine_original.inp").read_text().split("&END")[0] + "&END\n"
    (run / "design.inp").write_text(inp)
    reader = ROOT / "restored/read_namelist_cards.f90"
    free = "\n".join((lab + " " if lab else "") + text for lab, text in compat.logical_lines(source))
    variants = {
        "native24": (free, []),
        "native53": (free, ["-fdefault-real-8", "-fdefault-double-8"]),
        "native113": (free, ["-fdefault-real-16"]),
        "truncate27": (compat.generate(source, 27, False)[0], ["-fdefault-real-16"]),
    }
    base27 = variants["truncate27"][0]
    # Hypothesis controls only. Do not select an arithmetic model by table fit.
    variants["nearest27"] = (base27.replace("SCALE(AINT(SCALE(FRACTION(VALUE),27))", "SCALE(ANINT(SCALE(FRACTION(VALUE),27))"), ["-fdefault-real-16"])
    variants["truncate27_backing53"] = (base27, ["-fdefault-real-8", "-fdefault-double-8"])
    report = {"source_sha256": hashlib.sha256(source.encode()).hexdigest(), "runs": {}}
    for name, (code, flags) in variants.items():
        folder = run / name
        folder.mkdir()
        src = folder / "trace.f90"
        src.write_text(instrument(code))
        cmd = [shutil.which("gfortran"), "-std=legacy", "-fno-automatic", "-ffree-line-length-none", "-fcheck=all", "-ffpe-trap=invalid,zero,overflow", *flags, str(src), str(reader), "-o", str(folder / "trace")]
        build = subprocess.run(cmd, capture_output=True)
        (folder / "build.stderr").write_bytes(build.stderr)
        assert build.returncode == 0, (name, build.stderr.decode())
        result = subprocess.run([str(folder / "trace")], input=inp.encode(), capture_output=True, timeout=15)
        (folder / "stdout").write_bytes(result.stdout)
        (folder / "trace.stderr").write_bytes(result.stderr)
        assert result.returncode == 0, (name, result.stderr.decode()[-2000:])
        rows = []
        for line in result.stderr.decode().splitlines():
            if line.strip().startswith("TRACE "):
                key, *values = line.strip()[6:].split()
                rows.append({"stage": key, "values": [float(v.replace("D", "E")) for v in values]})
        (folder / "trace.json").write_text(json.dumps(rows, indent=2) + "\n")
        final = [r for r in rows if r["stage"] == "design-final"][-1]
        report["runs"][name] = {"command": cmd, "checkpoints": len(rows), "final": final["values"], "getk_calls": sum(r["stage"] == "getk-before" for r in rows)}
    (run / "summary.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))
    print("RESULTS", run)


if __name__ == "__main__":
    main()
