"""Validate PERF-15 pair identity, raw captures and derived measurements."""
import csv
import json
import math
from pathlib import Path
import statistics

import bench_perf15 as bench


def child(directory, name):
    if not isinstance(name, str) or name in ('', '.', '..') or Path(name).name != name:
        raise ValueError('evidence paths must be local filenames')
    path = directory / name
    if path.is_symlink():
        raise ValueError('evidence paths must not be symlinks')
    return path


def close(actual, expected, tolerance=1e-12):
    if not math.isfinite(actual) or not math.isclose(actual, expected, rel_tol=1e-12, abs_tol=tolerance):
        raise ValueError('derived measurement differs from raw evidence')


def trace_values(rows, field):
    values = [float(row[field]) for row in rows]
    if any(not math.isfinite(value) or value < 0 for value in values):
        raise ValueError('trace times must be finite and nonnegative')
    return values


def trace_metrics(path):
    with path.open() as stream:
        rows = list(csv.DictReader(stream))
    if [int(row['frame']) for row in rows] != list(range(2700)):
        raise ValueError('missing, duplicate or unexpected frames')
    times = sorted(trace_values(rows, 'total'))
    return dict(frame_mean=statistics.fmean(times),
                frame_p95=times[(len(times)-1)*95//100],
                frame_p99=times[(len(times)-1)*99//100],
                processing_cpu_mean=statistics.fmean(trace_values(rows, 'processing_cpu')))


def verify_hashes(directory, row):
    required = {'results.json', row['baseline'], row['candidate']}
    if len(required) != 3 or not required.issubset(row['hashes']):
        raise ValueError('missing required evidence hashes')
    for name, expected in row['hashes'].items():
        if bench.digest(child(directory, name)) != expected:
            raise ValueError('raw capture hash differs')


def check_command(command):
    if not isinstance(command, list) or len(command) != 11:
        raise ValueError('capture command must contain the protocol arguments')
    if not all(isinstance(value, str) for value in command):
        raise ValueError('capture arguments must be strings')


def verify_invocation(directory, record):
    command, environment = record['command'], record['environment']
    check_command(command)
    if not isinstance(environment, dict):
        raise ValueError('capture environment must be an object')
    trace = Path(command[-1])
    if trace.name != record['trace'] or trace.parent.name != directory.name:
        raise ValueError('command trace differs from capture location')
    expected, controls = bench.capture_configuration(
        Path(command[0]).parent, Path(environment['UP_PROFILE_INPUT']).parent, record['job'], trace)
    actual = dict(environment)
    # Historical captures cleared inherited controls and omitted these zero defaults.
    for key in ('UP_PROFILE_EXECUTOR', 'UP_PROFILE_ACTIVE'):
        actual.setdefault(key, '0')
    if command != expected or actual != controls:
        raise ValueError('capture invocation differs from treatment or timing protocol')
    return controls


def verify_runtime(record, controls):
    result = record['result']
    if json.loads(record['stdout']) != result:
        raise ValueError('capture summary differs from process output')
    expected = {key: int(controls['UP_PROFILE_' + key.upper()])
                for key in ('executor', 'zerocopy', 'sharp_threshold', 'warmup')}
    expected['tuner_policy'] = 'latency-experiment' if record['job']['treatment'] == 'latency' else 'legacy'
    if any(type(result[key]) is not type(value) or result[key] != value for key, value in expected.items()):
        raise ValueError('runtime controls differ from captured invocation')


def verify_record(directory, record, clip, treatment, trace):
    if record['returncode'] != 0 or record.get('failure') or record['job'] != bench.settings(clip, treatment):
        raise ValueError('failed capture or mismatched capture identity')
    if record['trace'] != trace:
        raise ValueError('capture trace differs from pair')
    verify_runtime(record, verify_invocation(directory, record))
    computed = trace_metrics(child(directory, trace))
    for metric, expected in computed.items():
        actual = record['result'][metric]
        if actual <= 0:
            raise ValueError('capture summary must be positive')
        close(actual, expected, .001)
    return record['result']


def verify_measurements(directory, row):
    records = json.loads((directory / 'results.json').read_text())
    if len(records) != 2 or sorted(row['order']) != sorted(['baseline', row['treatment']]):
        raise ValueError('pair must contain exactly one reference and one candidate')
    traces = dict(baseline=row['baseline']) | {row['treatment']: row['candidate']}
    results = {name: verify_record(directory, record, row['clip'], name, traces[name])
               for name, record in zip(row['order'], records)}
    if set(row['ratios']) != set(bench.METRICS):
        raise ValueError('pair metrics differ from the protocol')
    for metric in bench.METRICS:
        close(row['ratios'][metric], results[row['treatment']][metric] / results['baseline'][metric])
    valid = all(result['adaptive_outcome'] in ('fixed', 'settled', 'searching')
                for result in results.values())
    if row['valid_outcomes'] is not valid:
        raise ValueError('pair outcome differs from capture outcomes')


def verify_identity(row, job, index):
    if job is not None and any(row[key] != value for key, value in job.items()):
        raise ValueError('pair identity differs from planned job')
    if index is not None and (row['index'] != index or row['directory'] != 'pair-%04d' % index):
        raise ValueError('pair index differs from plan')


def validate_pair(root, row, job=None, index=None):
    try:
        directory = child(root, row['directory'])
        verify_identity(row, job, index)
        verify_hashes(directory, row)
        saved = json.loads((directory / 'pair.json').read_text())
        if saved != {key: value for key, value in row.items() if key != 'source'}:
            raise ValueError('pair summary differs from saved pair')
        verify_measurements(directory, row)
    except (OSError, KeyError, TypeError, ValueError, OverflowError) as error:
        raise RuntimeError('completed pair evidence changed or invalid: ' + str(error)) from error
