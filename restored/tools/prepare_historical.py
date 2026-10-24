"""Fetch hash-pinned public archives and build the isolated historical runtime."""
from pathlib import Path
import hashlib, json, subprocess, tarfile, urllib.request

ROOT = Path(__file__).resolve().parents[2]
DEST = ROOT / "audit/2026-10-23/restoration/historical7094"
ARCHIVES = {
    "s709-2.4.4.tar.gz": "86d3f896b4b5cfe5f78200a89717902dfb826131c2fbdb32bbb5bddd69526096",
    "ibsys.tar.gz": "7442d355e0077cee6f40dc2937d22bd400d65840de7ef33564d1e90dd163bfb0",
}
DEST.mkdir(parents=True, exist_ok=True)
for name, expected in ARCHIVES.items():
    archive = DEST / name
    if not archive.exists():
        urllib.request.urlretrieve("https://www.cozx.com/dpitts/tarballs/ibm709x/" + name, archive)
    actual = hashlib.sha256(archive.read_bytes()).hexdigest()
    if actual != expected:
        raise RuntimeError("Archive hash mismatch; retained for inspection: " + str(archive))
    marker = DEST / ("s709-2.4.4/Makefile" if name.startswith("s709") else "IBFTC/rtl/fasc.map")
    if not marker.exists():
        with tarfile.open(archive) as source:
            source.extractall(DEST, filter="data")
    with tarfile.open(archive) as source:
        for member in source.getmembers():
            if member.isfile():
                local = DEST / member.name
                expected_data = source.extractfile(member).read()
                if not local.is_file() or local.read_bytes() != expected_data:
                    raise RuntimeError("Archived runtime source/tape changed: " + str(local))
kit = DEST / "s709-2.4.4"
# No installation or global PATH changes. Build and tapes stay in the audit tree.
command = ["make", "s709", "txt2bcd", "bcd2cbn", "bcd2txt", "gendate", "CFLAGS=-O2 -DUSE64 -DUNIX -DDARWIN -DANSICRT -Iinclude"]
build = subprocess.run(command, cwd=kit, capture_output=True)
(DEST / "prepare-build.stdout").write_bytes(build.stdout)
(DEST / "prepare-build.stderr").write_bytes(build.stderr)
build.check_returncode()
identity = {name: hashlib.sha256((kit / name).read_bytes()).hexdigest() for name in ["s709", "txt2bcd", "bcd2cbn", "bcd2txt", "gendate", "ASYS1.BIN", "ASYS8.BIN"]}
(DEST / "runtime-identity.json").write_text(json.dumps({"archives": ARCHIVES, "build_command": command, "files": identity}, indent=2) + "\n")
print("Prepared isolated runtime:", kit)
