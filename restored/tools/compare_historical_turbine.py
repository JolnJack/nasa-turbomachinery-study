"""Compare isolated IBM/IBSYS diagnostic outputs to untouched printed references.

The E16.8 transport is rounded to the number of significant digits visibly
used in the report. This is numeric evidence, not historical G-format identity.
"""
from pathlib import Path
import argparse, hashlib, json, re, math

ROOT = Path(__file__).resolve().parents[2]
KIT = ROOT / "audit/2026-10-23/restoration/historical7094"


def numbers(line):
    line = re.sub(r"E ([0-9]{2})", r"E+\1", line)
    return [float(x) for x in re.findall(r"[-+]?(?:\d+\.\d*|\.\d+)(?:E[-+]\d+)?", line)]


def printed(value):
    return float(format(value, ".6g" if 1 <= abs(value) < 1e5 else ".5g"))


def word_rows(text, tag):
    rows = []
    for line in text.splitlines():
        if not line.startswith(tag + " "):
            continue
        row = []
        for token in line[6:].split():
            word = int(token, 8)
            sign = -1 if word & (1 << 35) else 1
            exponent = (word >> 27) & 255
            fraction = word & ((1 << 27) - 1)
            row.append(sign * math.ldexp(fraction, exponent - 128 - 27))
        assert len(row) == 5
        rows.append(row)
    return rows


def blocks(text):
    vel, perf = word_rows(text, "VELW"), word_rows(text, "PERFW")
    if vel or perf:
        assert len(vel) % 6 == len(perf) % 5 == 0
        assert len(vel) // 6 == len(perf) // 5
        return [vel[i * 6:i * 6 + 6] + perf[i * 5:i * 5 + 5] for i in range(len(vel) // 6)]
    lines = text.splitlines()
    out = []
    for i, line in enumerate(lines):
        if line.strip() == "VELOCITIES AND ANGLES":
            rows = [numbers(x) for x in lines[i + 1:i + 7]] + [numbers(x) for x in lines[i + 8:i + 13]]
            assert all(len(x) == 5 for x in rows)
            out.append(rows)
    return out


def compare(want, raw, design_coefficients=False):
    assert len(want) == len(raw), (len(want), len(raw))
    diffs, matches = [], 0
    for row, (a, b) in enumerate(zip(want, raw), 1):
        assert len(a) == len(b)
        for col, (expected, actual) in enumerate(zip(a, b), 1):
            rendered = float(format(actual, ".6g")) if design_coefficients else printed(actual)
            if rendered == expected:
                matches += 1
            else:
                diffs.append({"row": row, "column": col, "expected": expected, "raw_actual": actual, "printed_actual": rendered})
    return {"exact_cells": matches, "expected_cells": sum(map(len, want)), "differences": diffs}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("design", type=Path)
    p.add_argument("long", type=Path)
    p.add_argument("short", type=Path)
    p.add_argument("original", type=Path)
    p.add_argument("--carry", action="store_true", help="long/short jobs begin with the design case and retain its full internal coefficients")
    a = p.parse_args()
    refs = json.loads((ROOT / "restored/tests/reference_full.json").read_text())
    texts = {key: (getattr(a, key) / "listing.txt").read_text() for key in ["design", "long", "short", "original"]}
    coeff = []
    for line in texts["design"].splitlines():
        if re.match(r"^\s*(PD\s+[0-9.]|K\s+[0-9.]|DESIGN WT-FLOW|DESIGN ETA-T|DESIGN P0,/P5,)", line) and numbers(line):
            coeff.append(numbers(line)[-1])
    if word_rows(texts["design"], "COEFW"):
        coeff = word_rows(texts["design"], "COEFW")[0]
    short = []
    lines = texts["short"].splitlines()
    started = False
    pending = []
    for line in lines:
        if "K V1VC1" in line and not "FORMAT" in line:
            started = True
        if started and re.fullmatch(r"[ \-+0-9.E]+", line) and len(numbers(line)) == 5:
            pending += numbers(line)
            if len(pending) == 10:
                short.append(pending)
                pending = []
    words = word_rows(texts["short"], "WORDS")
    if words:
        assert len(words) % 2 == 0
        short = [words[i] + words[i + 1] for i in range(0, len(words), 2)]
    long = blocks(texts["long"])
    if a.carry:
        long = long[1:]
    original = blocks(texts["original"])
    result = {
        "provenance": {key: {"path": str(getattr(a, key)), "listing_sha256": hashlib.sha256(texts[key].encode()).hexdigest()} for key in texts},
        "comparisons": {
            "table-III": compare(refs["turbine_table_iii"], blocks(texts["design"])[0]),
            "design-coefficients": compare([refs["turbine_design_coefficients"]], [coeff], True),
            "table-IV-original-input": compare(sum(refs["turbine_table_iv"], []), sum(original[:3], [])),
            "table-IV-" + ("carried-coefficients" if a.carry else "rounded-coefficients"): compare(sum(refs["turbine_table_iv"], []), sum(long[:3], [])),
            "table-V-" + ("carried-coefficients" if a.carry else "rounded-coefficients"): compare(refs["turbine_table_v"], short),
        },
        "long_points": len(long), "short_points": len(short), "short_values_from_exact_octal_words": bool(words),
        "limits": "Archived IBM compiler/library version is not established as NASA's exact version. FORMAT and input transport were adapted, and arc-function names exported as aliases. Raw printed reference data is unchanged."
    }
    dest = KIT / ("comparison-carry.json" if a.carry else "comparison.json")
    dest.write_text(json.dumps(result, indent=2) + "\n")
    for label, r in result["comparisons"].items():
        print(label, r["exact_cells"], "/", r["expected_cells"])
        for d in r["differences"][:10]:
            print(" ", d)
    print("RESULTS", dest)


if __name__ == "__main__":
    main()
