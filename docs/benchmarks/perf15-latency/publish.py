"""Preserve PERF-15 raw evidence and its pre-measurement protocol."""
import gzip
import hashlib
import json
from pathlib import Path
import shutil
import tarfile

ROOT = Path('build/perf15')
DEST = Path('docs/benchmarks/perf15-latency')


def compress(source, target):
    with source.open('rb') as stream, target.open('wb') as output:
        with gzip.GzipFile(filename='', fileobj=output, mode='wb', mtime=0) as archive:
            shutil.copyfileobj(stream, archive)


def group(name):
    original, target = ROOT/name, DEST/name
    assert json.loads((original/'verified.json').read_text())['hashes_unchanged']
    target.mkdir()
    for file in sorted(original.iterdir()):
        if file.suffix == '.csv':
            compress(file, target/(file.name+'.gz'))
        elif file.suffix == '.json':
            shutil.copy2(file, target/file.name)


def validation():
    target = DEST/'validation'
    target.mkdir()
    for name in ('red', 'build', 'build2', 'check', 'tsan', 'complexity', 'complexity-green', 'pixels', 'paced'):
        source = Path('/tmp/perf15-'+name+'.log')
        if source.exists():
            compress(source, target/(name+'.log.gz'))


def integrity():
    hashes = {str(file.relative_to(DEST)): hashlib.sha256(file.read_bytes()).hexdigest()
              for file in sorted(DEST.rglob('*')) if file.is_file() and file != DEST/'sha256.json'}
    (DEST/'sha256.json').write_text(json.dumps(hashes, indent=2)+'\n')


def measured_sources():
    manifest = json.loads((ROOT/'paced/manifest.json').read_text())
    with (DEST/'measured-sources.tar.gz').open('wb') as output:
        with gzip.GzipFile(filename='', fileobj=output, mode='wb', mtime=0) as zipped:
            with tarfile.open(fileobj=zipped, mode='w') as archive:
                for name, expected in manifest['hashes'].items():
                    source = Path(name)
                    if source.suffix == '.yuv':
                        continue
                    assert hashlib.sha256(source.read_bytes()).hexdigest() == expected
                    archive.add(source, arcname=name)


def main():
    DEST.mkdir(parents=True, exist_ok=False)
    for name in ('pixels', 'paced'):
        group(name)
    validation()
    measured_sources()
    shutil.copy2('docs/PERF15_LATENCY_TRIAL.md', DEST/'protocol.md')
    shutil.copy2(__file__, DEST/'publish.py')
    integrity()


if __name__ == '__main__':
    main()
