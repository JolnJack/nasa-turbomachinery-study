"""Check organized paths and immutable originals without running simulations."""
from pathlib import Path
from urllib.parse import unquote, urlsplit
import ast
import hashlib
import json
import re

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    errors = []
    baseline = json.loads((ROOT / 'audit/2026-10-22/baseline-manifest.json').read_text())
    locations = json.loads((ROOT / 'originals/manifest.json').read_text())['files']
    mapped = {row['original_name']: row for row in locations}
    if len(mapped) != 14 or set(mapped) != {row['file'] for row in baseline['files']}:
        errors.append('Original location map must cover exactly the 14 baseline files')
    for row in baseline['files']:
        name = row['file']
        entry = mapped.get(name)
        if entry is None:
            continue
        for path in [ROOT / entry['path'], ROOT / 'audit/2026-10-22/baseline' / name]:
            if not path.is_file() or sha(path) != row['sha256']:
                errors.append('Missing or changed original: ' + str(path.relative_to(ROOT)))
        if entry['sha256'] != row['sha256']:
            errors.append('Location-map hash differs from baseline: ' + name)

    docs = [ROOT / 'README.md', ROOT / 'audit/README.md', ROOT / 'originals/README.md',
            ROOT / 'reports/README.md', *sorted((ROOT / 'docs').glob('*.md')),
            *sorted((ROOT / 'restored').glob('*.md')),
            ROOT / 'audit/2026-10-23/restoration/ARCHIVED.md']
    links = 0
    for path in docs:
        if not path.is_file():
            errors.append('Missing navigation file: ' + str(path.relative_to(ROOT)))
            continue
        for raw in re.findall(r'\[[^\]]*\]\(([^)]+)\)', path.read_text()):
            target = urlsplit(raw.strip('<>'))
            if target.scheme or not target.path:
                continue
            links += 1
            resolved = (path.parent / unquote(target.path)).resolve()
            if not resolved.is_relative_to(ROOT) or not resolved.exists():
                errors.append('Broken local link in ' + str(path.relative_to(ROOT)) + ': ' + raw)

    scripts = [*sorted((ROOT / 'tools').glob('*.py')),
               *sorted((ROOT / 'restored/tests').glob('*.py')),
               *sorted((ROOT / 'restored/tools').glob('*.py'))]
    for path in scripts:
        try:
            ast.parse(path.read_text(), filename=str(path))
        except SyntaxError as exc:
            errors.append(str(exc))
    if errors:
        for error in errors:
            print('FAIL:', error)
        raise SystemExit(1)
    print(f'PASS: 14 original locations, 14 baseline copies, {links} local navigation links, '
          f'{len(scripts)} Python scripts')


if __name__ == '__main__':
    main()
