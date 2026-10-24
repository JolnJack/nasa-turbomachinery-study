"""Reproducible historical-environment evidence, with explicit report erratum.

This does not waive the modern compat27 failures or claim full NASA-environment
identity. The raw comparison is retained alongside the formula-first decision.
"""
from pathlib import Path
import argparse, datetime, hashlib, importlib.util, json, re, subprocess, sys

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
p = argparse.ArgumentParser()
p.add_argument("--strict-raw", action="store_true", help="fail on the unchanged printed E1 value, even though formula-first acceptance passes")
args = p.parse_args()
spec = importlib.util.spec_from_file_location("historical_compare", HERE.parent / "tools/compare_historical_turbine.py")
cmp = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cmp)
stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
run = ROOT / "audit/2026-10-23/restoration" / ("historical-check-" + stamp)
run.mkdir()
ref = json.loads((HERE / "reference_full.json").read_text())
result = {"checks": [], "jobs": {}, "comparisons": {}, "scope": "Original turbine listing, archived IBM compiler/math library, adapted I/O; numerical reference reconstruction, not full-domain certification."}


def check(name, ok, detail=None):
    result["checks"].append({"name": name, "pass": bool(ok), "detail": detail})
    print(("PASS " if ok else "FAIL ") + name, flush=True)


def execute(label, data, expected_success=True):
    inp = run / (label + ".inp")
    inp.write_text(data)
    command = [sys.executable, str(HERE.parent / "tools/run_historical_turbine.py"), "--portable-formats", "--library-source", "--formatted-input", "--dump-words", "--input", str(inp)]
    p = subprocess.run(command, capture_output=True, text=True, timeout=55)
    (run / (label + ".log")).write_text(p.stdout + p.stderr)
    location = Path(re.search(r"^RESULTS (.*)$", p.stdout, re.M)[1])
    meta = json.loads((location / "run.json").read_text())
    result["jobs"][label] = {"path": str(location), "command": command, "exit": p.returncode, "run": meta}
    if expected_success:
        check(label + " executes without compile/runtime failure", p.returncode == 0 and meta["program_executed"] and not meta["runtime_error"])
    else:
        check(label + " returns a diagnostic failure", p.returncode == 1 and meta["runtime_error"])
    return (location / "listing.txt").read_text()


def shortrows(text):
    rows = cmp.word_rows(text, "WORDS")
    assert len(rows) % 2 == 0
    return [rows[i] + rows[i + 1] for i in range(0, len(rows), 2)]


def compare(label, want, actual, coefficients=False):
    comparison = cmp.compare(want, actual, coefficients)
    result["comparisons"][label] = comparison
    return comparison


def override(text, name, value):
    pattern = r"(?<![A-Z0-9_])" + name + r"\s*=\s*[-+0-9.E]+"
    if re.search(pattern, text):
        return re.sub(pattern, name + "=" + str(value), text)
    return text.replace("&END", name + "=" + str(value) + " &END")


original = (ROOT / "originals/turbine_tn_d8063.inp").read_text()
cases = [s.lstrip("\n") + "&END\n" for s in original.split("&END") if s.strip()]
longtext = execute("design-carry-long", cases[0] + "INHERIT FULL DESIGN COEFFICIENTS\n100 PERCENT SPEED\n &IN MODE=0 &END\n")
shorttext = execute("design-carry-short", cases[0] + "INHERIT FULL DESIGN COEFFICIENTS\n100 PERCENT SPEED\n &IN MODE=1 &END\n")
long = cmp.blocks(longtext)
short = shortrows(shorttext)
for label, want, actual, coefficients in [
    ("table-III", ref["turbine_table_iii"], long[0], False),
    ("design-coefficients", [ref["turbine_design_coefficients"]], cmp.word_rows(longtext, "COEFW"), True),
    ("table-IV", sum(ref["turbine_table_iv"], []), sum(long[1:4], []), False),
]:
    comparison = compare(label, want, actual, coefficients)
    check(label + " all printed values exact", not comparison["differences"], comparison)
check("complete long and short choking scans", len(long) == 21 and len(short) == 20 and "LAST CASE IS APPROXIMATE LIMITING LOADING" in longtext and "LAST CASE IS APPROXIMATE LIMITING LOADING" in shorttext)
v = compare("table-V-raw", ref["turbine_table_v"], short)
check("raw table V has only the independently evidenced E1 discrepancy", len(v["differences"]) == 1 and v["differences"][0]["row"] == 9 and v["differences"][0]["column"] == 5 and v["differences"][0]["expected"] == .90378 and v["differences"][0]["printed_actual"] == .90078, v)
etas, ps, pt = .84947, 1.97464, 1.89244
formula = etas * (1 - ps ** (-1 / 3.5)) / (1 - pt ** (-1 / 3.5))
check("E1 candidate independently agrees with report identity", round(formula, 5) == .90078 and abs(formula - .90378) > .002, {"formula": formula, "printed": .90378, "candidate": .90078})

original_text = execute("original-table-II", cases[1])
original_cmp = compare("table-IV-original-table-II", sum(ref["turbine_table_iv"], []), sum(cmp.blocks(original_text)[:3], []))
check("original Table II remains a distinct nonmatching case", bool(original_cmp["differences"]), original_cmp)
rounded = execute("rounded-design-coefficients", cases[1].replace("XK=.28699,PD=.98783", "XK=.286840,PD=.987836"))
rounded_cmp = compare("table-IV-rounded-coefficients", sum(ref["turbine_table_iv"], []), sum(cmp.blocks(rounded)[:3], []))
check("rounded coefficients do not silently replace internal precision", bool(rounded_cmp["differences"]) and rounded_cmp["exact_cells"] > original_cmp["exact_cells"], rounded_cmp)

# Same documented six modes, using complete records at each unit-system change.
converted = {"P0":172368.9/47.88025898033584,"T0":1144.44*1.8,"A0":.0120176/.09290304,"A1":.0038008/.09290304,"A3":.0039789/.09290304,"A5":.0044543/.09290304,"D3":12.6238/2.54,"D2":12.9997/2.54,"U3":237.9524/.3048,"R":99.1976/(32.1741*.3048**2*1.8)}
for mode in range(6):
    data = override(cases[0 if mode in [2,5] else 1], "MODE", mode)
    if mode >= 3:
        for name, value in converted.items():
            data = override(data, name, format(value, ".12g"))
        if mode == 5:
            data = override(data, "WD", format(.33879/.45359237, ".12g"))
    text = execute("mode-" + str(mode), data)
    count = len(shortrows(text)) if mode in [1,4] else len(cmp.blocks(text))
    check("mode " + str(mode) + " expected output count", count == (1 if mode in [2,5] else 20), {"points": count})

# Validate the word decoder independently against literal IBM library constants.
check("octal decoder known 1 and 1/2", cmp.word_rows("WORDS  201400000000 200400000000 0 0 0", "WORDS")[0] == [1., .5, 0., 0., 0.])
failed = cases[0]
for name, value in {"P0":200000,"T0":1000,"U3":225,"WD":.4,"ETAD":.9,"PDSGN":1.8}.items():
    failed = override(failed, name, value)
failed += "FAILED DESIGN MUST BE REPORTED\nOFF-DESIGN DIAGNOSTIC\n &IN MODE=0 &END\n"
failed_output = execute("failed-design-diagnostic", failed, expected_success=False)
check("historical no-solution message is preserved", bool(re.search(r"^[ \t]*NO SOLUTION FOR THIS CASE", failed_output, re.M)))
result["raw_reference_exact"] = sum(x["exact_cells"] for key, x in result["comparisons"].items() if key in ["table-III", "design-coefficients", "table-IV", "table-V-raw"])
result["raw_reference_total"] = 425
result["formula_first_acceptance"] = all(x["pass"] for x in result["checks"])
result["raw_reference_acceptance"] = result["raw_reference_exact"] == 425
result["identity"] = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in [ROOT / "originals/turbine_tn_d8063.f", ROOT / "originals/turbine_tn_d8063.inp", HERE / "reference_full.json", HERE.parent / "tools/run_historical_turbine.py", HERE.parent / "tools/compare_historical_turbine.py", Path(__file__)]}
(run / "results.json").write_text(json.dumps(result, indent=2) + "\n")
print("RAW PRINTED REFERENCE", result["raw_reference_exact"], "/ 425; formula-first acceptance", result["formula_first_acceptance"])
print("RESULTS", run)
raise SystemExit(0 if result["formula_first_acceptance"] and (not args.strict_raw or result["raw_reference_acceptance"]) else 1)
