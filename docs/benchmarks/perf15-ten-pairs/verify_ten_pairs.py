"""Cross-check paired summaries against every completed raw frame trace."""
import csv
from collections import Counter
import json
import math
from pathlib import Path
import statistics
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from analyze_ten_pairs import verified_rows

ORIGINAL = Path('build/perf15/confirmation')
EXTENSION = Path('build/perf15/ten-pairs')


def close(actual, expected, label, tolerance=.001):
    if not math.isclose(actual, expected, rel_tol=1e-12, abs_tol=tolerance):
        raise ValueError('%s: %.9f != %.9f' % (label, actual, expected))


def tail_diagnostics(frames):
    tail = sorted(frames, key=lambda row: float(row['total']))[-27:]
    means = {key: statistics.fmean(float(row[key]) for row in tail)
             for key in ('total', 'zimg', 'usm', 'processing_cpu')}
    return dict(tail_frames=len(tail), tail_mean_us=means,
                cpu_below_wall=sum(float(row['processing_cpu']) < float(row['total']) for row in tail),
                phase_counts=dict(Counter(row['phase'] for row in tail)),
                includes_startup=any(row['frame'] == '0' for row in tail))


def trace_statistics(path):
    with path.open() as stream:
        frames = list(csv.DictReader(stream))
    if [int(row['frame']) for row in frames] != list(range(2700)):
        raise ValueError('missing or duplicate frame in ' + str(path))
    times = sorted(float(row['total']) for row in frames)
    metrics = dict(frame_mean=statistics.fmean(times),
                   frame_p95=times[(len(times)-1)*95//100],
                   frame_p99=times[(len(times)-1)*99//100],
                   processing_cpu_mean=statistics.fmean(float(row['processing_cpu']) for row in frames))
    return dict(metrics=metrics, diagnostics=tail_diagnostics(frames))


def verify_run(directory, record):
    if record['returncode'] != 0:
        raise ValueError('failed capture included in paired analysis')
    if record['environment']['UP_PROFILE_VERIFY_PIXELS'] != '0':
        raise ValueError('pixel hashing unexpectedly enabled during timing')
    computed = trace_statistics(directory/record['trace'])
    for metric, value in computed['metrics'].items():
        close(value, record['result'][metric], str(directory)+':'+metric)
    return dict(record['result'], diagnostics=computed['diagnostics'])


def verify_pair(pair):
    source = ORIGINAL if pair['source'] == 'original' else EXTENSION
    directory = source/pair['directory']
    records = json.loads((directory/'results.json').read_text())
    if len(records) != 2:
        raise ValueError('paired comparison must have exactly two completed captures')
    results = {row['job']['treatment']: verify_run(directory, row) for row in records}
    for metric, ratio in pair['ratios'].items():
        actual = results[pair['treatment']][metric]/results['baseline'][metric]
        close(actual, ratio, str(directory)+':ratio:'+metric, 1e-12)
    valid = all(row['adaptive_outcome'] in ('fixed','settled','searching') for row in results.values())
    if pair['valid_outcomes'] != valid:
        raise ValueError('adaptive outcome flag differs from captured outcomes')
    return dict(clip=pair['clip'], treatment=pair['treatment'], repeat=pair['repeat'], source=pair['source'],
                diagnostics={name: value['diagnostics'] for name, value in results.items()})


def main():
    rows = verified_rows(ORIGINAL, EXTENSION)
    diagnostics = [verify_pair(row) for row in rows]
    result = dict(pairs=len(rows), verified_executions=2*len(rows),
                  verified_frames=2*len(rows)*2700, raw_summaries_match=True,
                  timing_hashing_disabled=True, ratio_and_outcome_flags_match=True)
    (EXTENSION/'trace-verification.json').write_text(json.dumps(result, indent=2)+'\n')
    (EXTENSION/'trace-diagnostics.json').write_text(json.dumps(diagnostics, indent=2)+'\n')
    print(json.dumps(result))


if __name__ == '__main__':
    main()
