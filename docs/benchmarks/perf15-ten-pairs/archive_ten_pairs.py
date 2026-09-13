"""Preserve the bounded continuation before editing any measured source."""
import gzip
import hashlib
import json
from pathlib import Path
import shutil
import tarfile

ROOT = Path('build/perf15/ten-pairs')
DEST = Path('docs/benchmarks/perf15-ten-pairs')


def sources(manifest):
    files = dict(manifest['hashes'], **manifest['continuation'])
    with (DEST/'measured-sources.tar.gz').open('wb') as output:
        with gzip.GzipFile(filename='', fileobj=output, mode='wb', mtime=0) as zipped:
            with tarfile.open(fileobj=zipped, mode='w') as archive:
                for name, expected in files.items():
                    path = Path(name)
                    if path.suffix == '.yuv':
                        continue
                    if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
                        raise RuntimeError('source changed before archival: ' + name)
                    archive.add(path, arcname=name)


def captures():
    with (DEST/'captures.tar.gz').open('wb') as output:
        with gzip.GzipFile(filename='', fileobj=output, mode='wb', mtime=0) as zipped:
            with tarfile.open(fileobj=zipped, mode='w') as archive:
                for path in sorted(ROOT.rglob('*')):
                    if path.is_file():
                        archive.add(path, arcname=str(path.relative_to(ROOT)))


def main():
    verified = json.loads((ROOT/'verified.json').read_text())
    if not verified['measurement_complete'] or not verified['hashes_unchanged']:
        raise RuntimeError('bounded measurement has not completed verification')
    DEST.mkdir(parents=True, exist_ok=False)
    manifest = json.loads((ROOT/'manifest.json').read_text())
    sources(manifest)
    captures()
    for name in ('manifest', 'plan', 'complete-plan', 'pairs', 'combined-pairs', 'verified'):
        shutil.copy2(ROOT/(name+'.json'), DEST/(name+'.json'))
    shutil.copy2('docs/PERF15_TEN_PAIRS.md', DEST/'protocol.md')
    shutil.copy2(__file__, DEST/'archive_ten_pairs.py')
    print('Continuation sources and captures archived')


if __name__ == '__main__':
    main()
