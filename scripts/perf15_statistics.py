"""Run-level paired estimates with circular block bootstrap sensitivity."""
import argparse
import json
import math
from pathlib import Path
import random
import statistics

from bench_perf15 import METRICS
from perf15_evidence import validate_pair


def percentile(ordered, probability):
    index = (len(ordered) - 1) * probability
    lower = int(index)
    upper = min(lower + 1, len(ordered) - 1)
    return ordered[lower] + (index - lower) * (ordered[upper] - ordered[lower])


def log_values(ratios):
    if not ratios or any(not math.isfinite(value) or value <= 0 for value in ratios):
        raise ValueError('ratios must be nonempty, finite and positive')
    return [math.log(value) for value in ratios]


def block_sums(values, length):
    count = len(values)
    return [math.fsum(values[(start + offset) % count] for offset in range(length))
            for start in range(count)]


def bootstrap_means(values, length, samples, seed):
    generator = random.Random(seed)
    count = len(values)
    whole, remainder = divmod(count, length)
    complete = block_sums(values, length)
    tail = block_sums(values, remainder)
    estimates = []
    for _ in range(samples):
        total = math.fsum(generator.choice(complete) for _ in range(whole))
        estimates.append((total + generator.choice(tail)) / count)
    return sorted(estimates)


def interval(values, length, samples, seed, alpha):
    estimates = bootstrap_means(values, length, samples, seed)
    return [math.exp(percentile(estimates, tail)) for tail in (alpha / 2, 1 - alpha / 2)]


def serial_correlation(values, lag):
    mean = statistics.fmean(values)
    centered = [value - mean for value in values]
    denominator = math.fsum(value * value for value in centered)
    if not denominator:
        return 0.0
    numerator = math.fsum(a * b for a, b in zip(centered, centered[lag:]))
    return numerator / denominator


def descriptive_summary(ratios, values):
    return dict(pairs=len(values), ratio=math.exp(statistics.fmean(values)),
                median=statistics.median(ratios), range=[min(ratios), max(ratios)],
                individual_guard_failures=sum(value > 1.05 for value in ratios))


def estimate(ratios, comparisons, samples=100000, seed=20260916):
    values = log_values(ratios)
    summary = descriptive_summary(ratios, values)
    if len(values) < 20:
        return dict(summary, interval=None, reason='fewer than 20 pairs; descriptive only')
    alpha = .05 / comparisons
    lengths = (1, 5, 10, 20)
    intervals = {str(length): interval(values, length, samples, seed + length, alpha)
                 for length in lengths if length < len(values)}
    return dict(summary,
                interval=[min(row[0] for row in intervals.values()),
                          max(row[1] for row in intervals.values())],
                block_intervals=intervals, per_interval_alpha=alpha,
                bootstrap_samples=samples,
                serial_correlation={str(lag): serial_correlation(values, lag)
                                    for lag in (1, 5, 10, 20) if lag < len(values)},
                chronological_quarter_ratios=[math.exp(statistics.fmean(values[start:start + 25]))
                                             for start in range(0, len(values), 25)])


def checked_pairs(directory):
    verified = json.loads((directory/'verified.json').read_text())
    if not verified['hashes_unchanged']:
        raise ValueError('unverified captures cannot support conclusions')
    rows = json.loads((directory/'pairs.json').read_text())
    plan = json.loads((directory/'plan.json').read_text())
    if len(rows) != len(plan):
        raise ValueError('incomplete confirmation matrix')
    for index, (row, job) in enumerate(zip(rows, plan)):
        validate_pair(directory, row, job, index)
    return rows


def group_estimates(rows, samples):
    keys = sorted({(row['clip'], row['treatment']) for row in rows})
    comparisons = len(keys)*len(METRICS)
    estimates = []
    for clip, treatment in keys:
        subset = [row for row in rows if (row['clip'], row['treatment']) == (clip, treatment)]
        metrics = {key: estimate([row['ratios'][key] for row in subset], comparisons, samples)
                   for key in METRICS}
        estimates.append(dict(clip=clip, treatment=treatment, pairs=len(subset), metrics=metrics,
                              valid_outcomes=all(row['valid_outcomes'] for row in subset)))
    return estimates


def control_consistent(row):
    return all(value['interval'] is not None and value['interval'][0] <= 1 <= value['interval'][1]
               for value in row['metrics'].values())


def gain_supported(value):
    return value['interval'] is not None and value['interval'][1] < .95


def stability_flags(value):
    quarters = value.get('chronological_quarter_ratios', [])
    correlations = value.get('serial_correlation', {})
    flags = []
    if quarters and min(quarters) < .95 and max(quarters) > 1:
        flags.append('chronological segments disagree on gain direction')
    if abs(correlations.get('20', 0)) > 2/math.sqrt(value['pairs']):
        flags.append('lag-20 dependence exceeds declared screening threshold')
    return flags


def guard_summary(rows, controls):
    return dict(complete=all(row['pairs'] >= 100 for row in rows),
                valid_outcomes_and_controls=all(row['valid_outcomes'] and controls.get(row['clip'], False)
                                               for row in rows),
                stability_checks_pass=all(not stability_flags(value)
                                          for row in rows for value in row['metrics'].values()),
                individual_guards_pass=all(value['individual_guard_failures'] == 0
                                          for row in rows for value in row['metrics'].values()))


def supported_gains(rows):
    return [dict(clip=row['clip'], metric=key) for row in rows
            for key, value in row['metrics'].items() if gain_supported(value)]


def candidate_review(rows, treatment, controls):
    subset = [row for row in rows if row['treatment'] == treatment]
    guards = guard_summary(subset, controls)
    gains = supported_gains(subset)
    latency_gain = any(row['metric'] == 'frame_p99' for row in gains)
    return dict(treatment=treatment, **guards, gains_over_5_percent=gains,
                qualifies=all(guards.values()) and latency_gain)


def analyze(directory, samples=100000):
    rows = group_estimates(checked_pairs(directory), samples)
    for row in rows:
        for value in row['metrics'].values():
            value['stability_flags'] = stability_flags(value)
    controls = {row['clip']: control_consistent(row) for row in rows if row['treatment'] == 'duplicate'}
    treatments = sorted({row['treatment'] for row in rows if row['treatment'] != 'duplicate'})
    return dict(method='paired log ratios; circular block percentile intervals; Bonferroni adjustment',
                estimates=rows, control_consistency=controls,
                reviews=[candidate_review(rows, treatment, controls) for treatment in treatments])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path)
    args = parser.parse_args()
    result = analyze(args.directory)
    (args.directory/'analysis.json').write_text(json.dumps(result, indent=2)+'\n')


if __name__ == '__main__':
    main()
