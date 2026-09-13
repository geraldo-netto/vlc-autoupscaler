"""Analyze the final ten-pair scope; never launch more measurements."""
import argparse
from collections import Counter
import json
import math
from pathlib import Path
import statistics
import sys
from types import SimpleNamespace

sys.path.insert(0, str(Path.cwd()/'scripts'))
import bench_perf15 as bench
import bench_perf15_confirm as confirm
import perf15_statistics as stats


def verify_counts(rows):
    expected = {(clip, treatment): 10 for clip in bench.CLIPS for treatment in ('local', 'latency')}
    expected.update({(clip, 'duplicate'): 2 for clip in bench.CLIPS})
    if Counter((row['clip'], row['treatment']) for row in rows) != expected:
        raise ValueError('candidate/control counts differ from the final scope')


def verified_rows(original, extension):
    completed = json.loads((extension/'verified.json').read_text())
    if not completed['measurement_complete'] or not completed['hashes_unchanged']:
        raise ValueError('ten-pair measurement has not completed verification')
    rows = json.loads((extension/'combined-pairs.json').read_text())
    plan = confirm.plan(10, ['local', 'latency'], 20260916)
    if confirm.pending_jobs(plan, rows):
        raise ValueError('ten-pair matrix is incomplete')
    for label, directory in (('original', original), ('extension', extension)):
        subset = [row for row in rows if row['source'] == label]
        confirm.verify_evidence(SimpleNamespace(output=directory), subset)
    verify_counts(rows)
    return rows


def t_interval(values, alpha):
    from scipy.stats import t
    center = statistics.fmean(values)
    error = statistics.stdev(values)/math.sqrt(len(values))
    radius = float(t.ppf(1-alpha/2, len(values)-1))*error
    return [math.exp(center-radius), math.exp(center+radius)]


def metric_summary(rows, metric, samples):
    ratios = [row['ratios'][metric] for row in rows]
    values = stats.log_values(ratios)
    result = dict(pairs=len(rows), ratio=math.exp(statistics.fmean(values)),
                  median=statistics.median(ratios), range=[min(ratios), max(ratios)],
                  individual_ratios=ratios, guard_failures=sum(value > 1.05 for value in ratios),
                  gains_over_5=sum(value < .95 for value in ratios))
    if len(rows) == 2:
        result['uncertainty'] = 'two controls; descriptive variation only'
        return result
    result.update(conditional_t95=t_interval(values, .05),
                  conditional_family_t=t_interval(values, .05/24),
                  exploratory_blocks={str(length): stats.interval(values, length, samples,
                                                                  20260916+length, .05/24)
                                      for length in (2, 5)},
                  lag_correlations={str(lag): stats.serial_correlation(values, lag) for lag in (1, 2, 5)})
    return result


def records_for(row, original, extension):
    directory = original if row['source'] == 'original' else extension
    records = json.loads((directory/row['directory']/'results.json').read_text())
    return {record['job']['treatment']: record for record in records}


def absolute_summary(rows, original, extension):
    captures = [records_for(row, original, extension) for row in rows]
    treatment = rows[0]['treatment']
    return {metric: dict(reference_mean_us=statistics.fmean(pair['baseline']['result'][metric]
                                                           for pair in captures),
                         candidate_mean_us=statistics.fmean(pair[treatment]['result'][metric]
                                                           for pair in captures))
            for metric in bench.METRICS}


def phase_summary(rows, original, extension):
    captures = [records_for(row, original, extension)[row['treatment']] for row in rows]
    return dict(mean_settled_frames=statistics.fmean(row['summary']['settled_frames'] for row in captures),
                mean_exploration_frames=statistics.fmean(row['summary']['exploration_frames'] for row in captures),
                restarts=sum(row['summary']['restarts'] for row in captures),
                changed_frames=[row['summary']['changed_frames'] for row in captures])


def group_summary(rows, original, extension, samples):
    return dict(clip=rows[0]['clip'], treatment=rows[0]['treatment'], pairs=len(rows),
                valid_outcomes=all(row['valid_outcomes'] for row in rows),
                sources=[row['source'] for row in rows], repeats=[row['repeat'] for row in rows],
                started=[row['started'] for row in rows],
                metrics={key: metric_summary(rows, key, samples) for key in bench.METRICS},
                absolute=absolute_summary(rows, original, extension),
                phases=phase_summary(rows, original, extension))


def analyze(original, extension, samples=100000):
    import scipy
    rows = verified_rows(original, extension)
    keys = sorted({(row['clip'], row['treatment']) for row in rows})
    groups = [group_summary([row for row in rows if (row['clip'], row['treatment']) == key],
                            original, extension, samples) for key in keys]
    return dict(measurement_complete=True, paired_executions=2*len(rows),
                candidate_pairs=60, control_pairs=6, groups=groups,
                bootstrap_samples=samples, scipy_version=scipy.__version__,
                uncertainty='t intervals conditional on independent normal log differences; '
                            'small-block bootstrap sensitivities exploratory; controls descriptive')


def pct(value):
    return '%+.1f%%' % (100*(value-1))


def interval_text(values):
    return '['+', '.join(pct(value) for value in values)+']'


def markdown(result):
    lines = ['# PERF-15 ten-pair numerical results', '',
             'Measurement complete: 10 matched pairs per B/D option and clip.',
             '60 candidate pairs plus six retained control pairs; 132 paired executions.',
             'The unfinished pair is excluded and retained in the original archive.', '',
             'Changes use geometric means of paired ratios. Negative means less time or CPU.',
             'Intervals below are conditional family-adjusted paired-log t intervals.',
             'Block sensitivities, all ratios and chronological groups are in analysis.json.', '',
             '| Clip | Treatment | Mean | p95 | p99 | CPU |', '|---|---|---|---|---|---|']
    for row in result['groups']:
        values = [pct(row['metrics'][key]['ratio']) for key in bench.METRICS]
        lines.append('| %s | %s | %s |' % (row['clip'], row['treatment'], ' | '.join(values)))
    lines += ['', '| Clip | Treatment | Metric | Change | Conditional interval | Guard failures |',
              '|---|---|---|---|---|---|']
    for row in result['groups']:
        if row['treatment'] == 'duplicate':
            continue
        for key, value in row['metrics'].items():
            lines.append('| %s | %s | %s | %s | %s | %d/10 |' %
                         (row['clip'], row['treatment'], key, pct(value['ratio']),
                          interval_text(value['conditional_family_t']), value['guard_failures']))
    return '\n'.join(lines)+'\n'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('original', 'extension', 'output'):
        parser.add_argument(name, type=Path)
    args = parser.parse_args()
    result = analyze(args.original, args.extension)
    args.output.mkdir(parents=True, exist_ok=False)
    bench.save(args.output/'analysis.json', result)
    (args.output/'results.md').write_text(markdown(result))


if __name__ == '__main__':
    main()
