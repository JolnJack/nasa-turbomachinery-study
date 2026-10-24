"""Build/run preserved sources without overwriting the user's original outputs.

This is a reproducibility diagnostic, not a certification of NASA source identity.
Every invocation creates a new run directory and records failures without masking them.
"""
from pathlib import Path
from hashlib import sha256
import datetime
import json
import subprocess

AUDIT = Path(__file__).resolve().parent
SOURCE = AUDIT / "baseline"
RUN = AUDIT / "runs" / datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
RUN.mkdir(parents=True)
FC = "/opt/homebrew/bin/gfortran"
report = {
    "compiler": subprocess.run([FC, "--version"], capture_output=True, text=True, check=True).stdout,
    "source_directory": str(SOURCE),
    "source_sha256": {p.name: sha256(p.read_bytes()).hexdigest() for p in SOURCE.glob("*.f")},
    "results": [],
}
profiles = {
    "existing_flags": ["-std=legacy", "-fno-automatic", "-w"],
    "diagnostic": ["-std=legacy", "-fno-automatic", "-Wall", "-Wextra", "-g", "-fcheck=all", "-fbacktrace", "-ffpe-trap=invalid,zero,overflow"],
}
for name in ("compressor_tn_d7487", "turbine_tn_d8063"):
    for profile, flags in profiles.items():
        target = RUN / (name + "-" + profile)
        command = [FC, *flags, str(SOURCE / (name + ".f")), "-o", str(target)]
        built = subprocess.run(command, capture_output=True, timeout=60)
        target.with_suffix(".compile.stdout").write_bytes(built.stdout)
        target.with_suffix(".compile.stderr").write_bytes(built.stderr)
        row = {"program": name, "profile": profile, "compile_command": command, "compile_exit": built.returncode}
        if built.returncode == 0:
            with (SOURCE / (name + ".inp")).open("rb") as inp, target.with_suffix(".stdout").open("wb") as stdout, target.with_suffix(".stderr").open("wb") as stderr:
                try:
                    proc = subprocess.run([str(target)], stdin=inp, stdout=stdout, stderr=stderr, cwd=RUN, timeout=20)
                    row["run_exit"] = proc.returncode
                    row["timed_out"] = False
                except subprocess.TimeoutExpired:
                    row["run_exit"] = None
                    row["timed_out"] = True
            output = target.with_suffix(".stdout").read_bytes()
            saved = (SOURCE / (name + ".out")).read_bytes()
            row["stdout_bytes"] = len(output)
            row["matches_existing_output_bytes"] = output == saved
            row["stderr_excerpt"] = target.with_suffix(".stderr").read_text(errors="replace")[:1600]
        report["results"].append(row)
        print(json.dumps(row, ensure_ascii=False), flush=True)
(RUN / "results.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
print("Evidence:", RUN)
