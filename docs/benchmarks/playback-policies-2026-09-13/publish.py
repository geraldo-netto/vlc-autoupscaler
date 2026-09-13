"""Archive raw policy evidence without rewriting measured results."""
import gzip
import hashlib
import json
from pathlib import Path
import shutil
import sys

sys.path.insert(0, str(Path.cwd() / 'scripts'))
from bench_playback_policies import summarize_trace

SOURCE = Path('build/decision-review/next')
DESTINATION = Path('docs/benchmarks/playback-policies-2026-09-13')


def compressed(source, destination):
    with source.open('rb') as original, destination.open('wb') as target:
        with gzip.GzipFile(filename='', mode='wb', fileobj=target, mtime=0) as archive:
            shutil.copyfileobj(original, archive)


def copy_group(group):
    source = SOURCE / group
    target = DESTINATION / group
    target.mkdir()
    for file in source.iterdir():
        if file.suffix in ('.csv', '.log'):
            compressed(file, target / (file.name + '.gz'))
    for name in ('manifest.json', 'verified.json'):
        shutil.copy2(source / name, target / name)
    if group == 'gpu':
        compressed(source / 'results.json', target / 'results.json.gz')
    else:
        shutil.copy2(source / 'results.json', target / 'results.json')


def corrected_classifications(name):
    source = SOURCE / name
    rows = json.loads((source / 'results.json').read_text())
    summaries = []
    for index, row in enumerate(rows):
        trace = source / Path(row['trace']).name
        summaries.append(dict(run=index, job=row['job'], repeat=row['repeat'],
                              summary=summarize_trace(trace, bool(row['job']['adaptive']))))
    (DESTINATION / name / 'corrected-classification.json').write_text(json.dumps(summaries, indent=2) + '\n')


def copy_runtime():
    source = SOURCE / 'native-runtime-final'
    target = DESTINATION / 'native-controls'
    target.mkdir()
    for name in ('result.json', 'subtitle.png', 'subtitle.srt'):
        shutil.copy2(source / name, target / name)
    compressed(source / 'vlc.log', target / 'vlc.log.gz')


def integrity():
    hashes = {}
    for file in sorted(DESTINATION.rglob('*')):
        if file.is_file() and file != DESTINATION / 'sha256.json':
            hashes[str(file.relative_to(DESTINATION))] = hashlib.sha256(file.read_bytes()).hexdigest()
    (DESTINATION / 'sha256.json').write_text(json.dumps(hashes, indent=2) + '\n')


def main():
    DESTINATION.mkdir(parents=True, exist_ok=False)
    for name in ('cpu', 'adaptive', 'adaptive-720', 'gpu', 'native-playback'):
        copy_group(name)
    for name in ('cpu', 'adaptive', 'adaptive-720'):
        corrected_classifications(name)
    copy_runtime()
    for name in ('bench_playback_policies-measured.py', 'bench_playback_policies-gpu-measured.py'):
        shutil.copy2(SOURCE / name, DESTINATION / name)
    shutil.copy2(Path(__file__), DESTINATION / 'publish.py')
    integrity()


if __name__ == '__main__':
    main()
