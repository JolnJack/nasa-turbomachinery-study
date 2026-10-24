"""Run the root turbine calculation in an isolated s709 / IBSYS experiment.

Requires the downloaded, locally built s709-2.4.4 under the audit directory.
Explicit options adapt job controls, numeric input transport, output formats,
and library symbol names. No NASA equations or physical constants are rewritten.
"""
from pathlib import Path
import argparse, datetime, hashlib, json, re, subprocess

ROOT = Path(__file__).resolve().parents[2]
KIT = ROOT / "audit/2026-10-23/restoration/historical7094/s709-2.4.4"


def fixed_statement(body, label=""):
    lines = []
    while len(body) > 64:
        end = body.rfind(",", 0, 64) + 1
        if not end:
            end = body.rfind("/", 0, 64) + 1
        if not end:
            end = 64
        lines.append(body[:end])
        body = body[end:]
    lines.append(body)
    return f"{label:>5} " + lines[0] + "\n" + "".join("     1" + x + "\n" for x in lines[1:])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--smoke", action="store_true")
    parser.add_argument("--input", type=Path)
    parser.add_argument("--portable-formats", action="store_true", help="replace unsupported G fields by E22.12 for diagnostic numeric output only")
    parser.add_argument("--library-source", action="store_true", help="assemble archived IBM NAMELIST and arc-function library routines")
    parser.add_argument("--formatted-input", action="store_true", help="transport identical decimal inputs via E24.0 records instead of unavailable NAMELIST runtime")
    parser.add_argument("--digits", type=int, default=8, choices=[7, 8, 9, 12])
    parser.add_argument("--dump-words", action="store_true", help="print exact 36-bit output words in octal, avoiding decimal-conversion uncertainty")
    a = parser.parse_args()
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    run = KIT.parent / ("smoke-" if a.smoke else "turbine-")
    run = run.with_name(run.name + stamp)
    run.mkdir()
    source = (ROOT / "turbine_tn_d8063.f").read_text()
    original_source_hash = hashlib.sha256(source.encode()).hexdigest()
    if a.portable_formats:
        formats = {
            "400": "FORMAT(6E22.12/6E22.12/6E22.12)",
            "500": "FORMAT(/50X,21HVELOCITIES AND ANGLES/" + "/".join(["5E22.12"] * 6) + ")",
            "501": "FORMAT(50X,19HOVERALL PERFORMANCE/" + "/".join(["5E22.12"] * 5) + ")",
            "505": "FORMAT(5E22.12/5E22.12)",
            "509": "FORMAT(/13X,2HPD,E22.12/14X,1HK,E22.12/1X,14HDESIGN WT-FLOW,E22.12)",
            "525": "FORMAT(3X,12HDESIGN ETA-S ,E22.12/2X,13HDESIGN P0,/P5,E22.12)",
            "526": "FORMAT(3X,12HDESIGN ETA-T ,E22.12/1X,14HDESIGN P0,/P5,,E22.12)",
        }
        for label, body in formats.items():
            body = body.replace("E22.12", "E16." + str(a.digits))
            pattern = rf"^ *{label} FORMAT[^\n]*(?:\n[^\n]{{5}}[^ 0\n][^\n]*)*"
            source, count = re.subn(pattern, fixed_statement(body, label).rstrip("\n"), source, flags=re.M)
            assert count == 1, label
    if a.smoke:
        source = "      WRITE(6,100)\n  100 FORMAT(22H HISTORICAL SMOKE PASS)\n      STOP\n      END\n"
    default_input = (ROOT / "restored/examples/turbine_original.inp").read_text().split("&END")[0] + "&END\n"
    inp = a.input.read_text() if a.input else default_input
    # IBSYS BCD has a dollar sign but no ampersand. The data values stay intact.
    inp = re.sub(r"&IN\b", "$IN", inp, flags=re.I)
    inp = re.sub(r"&END\b", "$END", inp, flags=re.I)
    if a.formatted_input and not a.smoke:
        names = "G P0 T0 A0 A1 A3 A5 D3 AL1 B4 BL1 BL4 PDSGN ITEST U3 U4U3 R V1 DELV VMAX XK WD ZZ MODE PD ETAD DELY YMAX D2".split()
        records, reads, formats = [], ["      NCAS=NCAS+1\n"], []
        for batch in inp.split("$END"):
            if not batch.strip():
                continue
            title, fields = batch.split("$IN", 1)
            fields = fields.upper()
            assignment = r"([A-Z][A-Z0-9]*)\s*=\s*([-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:E[-+]?\d+)?)"
            if re.sub(assignment, "", fields).strip(" ,\r\n\t"):
                raise ValueError("Unsupported or malformed numeric NAMELIST data: " + fields)
            values = dict(re.findall(assignment, fields))
            if not values or any(len(v) > 24 for v in values.values()):
                raise ValueError("Empty record or numeric field exceeds 24 columns")
            for name in ["MODE", "ITEST"]:
                if name in values and not re.fullmatch(r"[-+]?\d+", values[name]):
                    raise ValueError("Integer selector required: " + name)
            assert set(values) <= set(names)
            # First record initializes unused fields to zero; later records only
            # assign explicitly supplied fields, preserving computed coefficients.
            selected = names if not records else [n for n in names if n in values]
            case = len(records) + 1
            reads.append(fixed_statement(f"IF(NCAS.EQ.{case}) READ(5,{900+case}) " + ",".join(selected)))
            fmt = ["I24" if x in ["MODE", "ITEST"] else "E24.0" for x in selected]
            formats.append(fixed_statement("FORMAT(" + ",/".join(fmt) + ")", str(900 + case)))
            titles = title.lstrip("\n").splitlines()[:2]
            assert len(titles) == 2
            if any(x.strip() for x in title.lstrip("\n").splitlines()[2:]):
                raise ValueError("Exactly two title records must precede each group")
            records.append("\n".join(titles) + "\n" + "\n".join(f"{values.get(n,'0'):>24}" for n in selected) + "\n")
        source = source.replace("    1 READ(5,100)", "      NCAS=0\n    1 READ(5,100)")
        source = source.replace("      READ(5,IN)\n", "".join(reads))
        source = source.replace("C               FORMAT STATEMENTS", "".join(formats) + "C               FORMAT STATEMENTS")
        inp = "".join(records)
    if a.dump_words:
        source = source.replace("     1ETAS,DHTCR,WTHODE,EQPRS,EQPRT\n", "     1ETAS,DHTCR,WTHODE,EQPRS,EQPRT\n" + fixed_statement("IF(MODE.EQ.1.OR.MODE.EQ.4) WRITE(6,950) V1VC1,XNS,PRS,XNU,ETAT,ETAS,DHTCR,WTHODE,EQPRS,EQPRT"))
        lines = source.splitlines(keepends=True)
        for fmt, dump in [(500, 951), (501, 952), (509, 953)]:
            for idx, line in enumerate(lines):
                if line.startswith(f"      WRITE(6,{fmt})"):
                    end = idx + 1
                    statement = line[6:].strip()
                    while end < len(lines) and len(lines[end]) > 5 and lines[end][5] not in " 0":
                        statement += lines[end][6:].strip()
                        end += 1
                    args = statement.split(")", 1)[1]
                    if fmt == 509:
                        args += ",ETAD,PDSGN"
                    lines.insert(idx, fixed_statement(f"WRITE(6,{dump})" + args))
                    break
        source = "".join(lines)
        word_formats = fixed_statement("FORMAT(6HWORDS ,5O13/6HWORDS ,5O13)", "950")
        word_formats += fixed_statement("FORMAT(" + "/".join(["6HVELW  ,5O13"] * 6) + ")", "951")
        word_formats += fixed_statement("FORMAT(" + "/".join(["6HPERFW ,5O13"] * 5) + ")", "952")
        word_formats += fixed_statement("FORMAT(6HCOEFW ,5O13)", "953")
        source = source.replace("C               FORMAT STATEMENTS", word_formats + "C               FORMAT STATEMENTS")
    job = "$JOB           NASA TURBINE DIAGNOSTIC\n$EXECUTE       IBJOB\n$IBJOB         GO,LOGIC,MAP,FIOCS\n$IBFTC TURBIN  FULIST,REF,NODECK,M94\n"
    for line in source.splitlines():
        if line.startswith("      SUBROUTINE"):
            name = line.split()[1].split("(")[0]
            job += f"$IBFTC {name:<6}  FULIST,REF,NODECK,M94\n"
        job += line + "\n"
    if a.library_source:
        for name in (["fasc"] if a.formatted_input else ["frdu", "fiou", "fasc"]):
            lib = (KIT.parent / "IBFTC/rtl" / (name + ".map")).read_text()
            if name == "fasc":
                # Export modern function spellings at the original entry addresses.
                lib = lib.replace("       END", "       ENTRY   ASIN\n       ENTRY   ACOS\nASIN   SYN     ARSIN\nACOS   SYN     ARCOS\n       END")
            job += lib
            if not job.endswith("\n"):
                job += "\n"
    job += "$DATA\n" + ("" if a.smoke else inp)
    job += (KIT / "eof.dat").read_text() + (KIT / "ibsys.ctl").read_text()
    (run / "job.txt").write_text(job)
    date = subprocess.run([str(KIT / "gendate")], capture_output=True, check=True).stdout
    (run / "sysin.txt").write_bytes(date + job.encode())

    def command(args):
        result = subprocess.run([str(x) for x in args], cwd=run, capture_output=True, timeout=50)
        return result

    command([KIT / "txt2bcd", "sysin.txt", "sysin.bcd"]).check_returncode()
    command([KIT / "txt2bcd", KIT / "ibsys.ctl", "reader.bcd", "80", "80"]).check_returncode()
    command([KIT / "bcd2cbn", "reader"]).check_returncode()
    # The emulator has short legacy device-name buffers. Use local symlinks.
    for name in ["ASYS1.BIN", "ASYS8.BIN", "ibsys.cmd"]:
        (run / name).symlink_to(KIT / name)
    args = [str(KIT / "s709"), "-p", "-m7094", "-cibsys.cmd", "r=reader", "p=print", "u=punch", "a1r=ASYS1.BIN", "a2r=ASYS8.BIN", "a3=sysin.bcd", "a4=sysou1.bcd", "a5=sysut1.bin", "a6=sysut3.bin", "a7=sysut2.bin", "a8=syspp1.bin", "a9=sysut4.bin", "a10=sysck2.bin"]
    try:
        result = command(args)
        rc, out, err = result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired as error:
        rc, out, err = "timeout", error.stdout or b"", error.stderr or b""
    (run / "emulator.stdout").write_bytes(out)
    (run / "emulator.stderr").write_bytes(err)
    if (run / "sysou1.bcd").exists():
        conversion = command([KIT / "bcd2txt", "-p", "sysou1.bcd", "listing.txt"])
        (run / "conversion.stderr").write_bytes(conversion.stderr)
    listing = (run / "listing.txt").read_text() if (run / "listing.txt").exists() else ""
    start = re.search(r"^[ \t]*NASA RADIAL INFLOW TURBINE COMPUTER PROGRAM[ \t]*$", listing, re.M)
    if start:
        output = listing[start.start():]
        output = re.split(r"\n\f[ \t]*[0-9]+ LINES OUTPUT\.", output)[0]
        (run / "computed-output.txt").write_text(output + "\n")
    executed = ("HISTORICAL SMOKE PASS\n" in listing if a.smoke else bool(re.search(r"^ +VELOCITIES AND ANGLES$|^K V1VC1", listing, re.M)))
    diagnostic_failure = bool(re.search(r"^[ \t]*(?:ERROR TRACE\. CALLS IN REVERSE ORDER\.|EXECUTION TERMINATED\.|NO SOLUTION FOR THIS CASE|NO SOLUTION COULD BE FOUND|ITERATION PROCEDURE HAD TO BE RESTARTED)", listing, re.M))
    report = {"command": args, "emulator_status": rc, "program_executed": executed, "loading_suppressed": "LOADING HAS BEEN SUPPRESSED." in listing, "runtime_error": diagnostic_failure, "original_source_sha256": original_source_hash, "source_sha256": hashlib.sha256(source.encode()).hexdigest(), "format_change": "G formats to E16." + str(a.digits) if a.portable_formats else None, "library_source": a.library_source, "formatted_input": a.formatted_input, "dump_words": a.dump_words, "input_sha256": hashlib.sha256(inp.encode()).hexdigest(), "smoke": a.smoke}
    report["job_sha256"] = hashlib.sha256(job.encode()).hexdigest()
    report["runtime_sha256"] = {str(p.relative_to(KIT.parent)): hashlib.sha256(p.read_bytes()).hexdigest() for p in [KIT / "s709", KIT / "ASYS1.BIN", KIT / "ASYS8.BIN", KIT.parent / "IBFTC/rtl/fasc.map"]}
    (run / "run.json").write_text(json.dumps(report, indent=2) + "\n")
    print("RESULTS", run)
    print("EMULATOR", rc)
    if (run / "listing.txt").exists():
        text = (run / "listing.txt").read_text()
        print(text[-4500:])
    raise SystemExit(0 if rc == 0 and executed and not report["loading_suppressed"] and not report["runtime_error"] else 1)


if __name__ == "__main__":
    main()
