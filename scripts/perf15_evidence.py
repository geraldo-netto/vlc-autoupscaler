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


TRACE_FIELDS = ('frame,total,zimg,usm,zdispatch,zfirst,zlast,zmin,zmax,zmean,zhandoff,zcpu,'
                'udispatch,ufirst,ulast,umin,umax,umean,uhandoff,ucpu,processing_cpu,'
                'phase,workers,changed,skipped,selected_workers,pixel_hash').split(',')


def trace_rows(path):
    with path.open() as stream:
        reader = csv.DictReader(stream)
        if reader.fieldnames not in (TRACE_FIELDS, TRACE_FIELDS + ['adaptive_active']):
            raise ValueError('trace requires the complete profiler schema')
        rows = list(reader)
    if [int(row['frame']) for row in rows] != list(range(2700)):
        raise ValueError('missing, duplicate or unexpected frames')
    for field in TRACE_FIELDS[1:21]:
        trace_values(rows, field)
    for row in rows:
        verify_trace_row(row)
    return rows


def bounded_integer(value, low, high):
    if type(value) is not int or not low <= value <= high:
        raise ValueError('invalid bounded state or counter')
    return value


def verify_trace_row(row):
    for field, high in (('phase', 3), ('workers', 64), ('selected_workers', 64),
                        ('changed', 1), ('skipped', 1)):
        bounded_integer(int(row[field]), 0, high)
        if row[field] != str(int(row[field])):
            raise ValueError('trace state must use canonical integers')
    if row['pixel_hash'] != '0000000000000000':
        raise ValueError('timing protocol must disable pixel hashing')
    bypass = int(row['skipped']) == 1
    if bypass != (int(row['workers']) == 0) or bypass != (int(row['selected_workers']) == 0):
        raise ValueError('trace worker counts contradict bypass state')
    verify_activity_row(row)


def verify_activity_row(row):
    if 'adaptive_active' not in row:
        return
    if row['adaptive_active'] not in ('0', '1'):
        raise ValueError('trace activity must use canonical boolean integers')
    if row['adaptive_active'] == '1' and row['skipped'] == '1':
        raise ValueError('trace activity contradicts bypass state')
    if row['adaptive_active'] == '0' and row['changed'] == '1':
        raise ValueError('inactive tuner reports activity')


def verify_activity_transitions(rows):
    for previous, current in zip(rows, rows[1:]):
        if previous['adaptive_active'] == '0':
            if current['adaptive_active'] == '1' or current['phase'] != previous['phase']:
                raise ValueError('stopped tuner cannot restart activity or change phase')


def verify_trace_activity(rows, adaptive, outcome):
    if 'adaptive_active' not in rows[0]:
        return
    active = [row['adaptive_active'] == '1' for row in rows]
    if (not adaptive or outcome == 'disabled') and any(active):
        raise ValueError('trace activity contradicts disabled or fixed mode')
    if active[-1] != (outcome in ('searching', 'settled')):
        raise ValueError('terminal activity contradicts adaptive outcome')
    verify_activity_transitions(rows)


def trace_metrics(rows):
    times = sorted(trace_values(rows, 'total'))
    return dict(frame_mean=statistics.fmean(times),
                frame_p95=times[(len(times)-1)*95//100],
                frame_p99=times[(len(times)-1)*99//100],
                processing_cpu_mean=statistics.fmean(trace_values(rows, 'processing_cpu')))


def verify_trace_counters(result, rows):
    changes = bounded_integer(result['adaptive_changes'], 0, len(rows))
    settled = bounded_integer(result['first_settled_frame'], 0, len(rows))
    if changes != sum(int(row['changed']) for row in rows):
        raise ValueError('adaptive change counter differs from trace')
    first = next((i for i, row in enumerate(rows) if int(row['phase']) == 3), None)
    expected = {first} if first is not None else {0, len(rows)}
    if settled not in expected:
        raise ValueError('first settled frame differs from trace')
    if result['skip_usm'] != int(rows[-1]['skipped']):
        raise ValueError('final bypass differs from trace')
    if bounded_integer(result['usm_effective'], 0, 64) != int(rows[-1]['workers']):
        raise ValueError('final worker count differs from trace')


def verify_trace_transitions(rows, adaptive):
    allowed = {0: {0, 1, 3}, 1: {1, 2}, 2: {0, 2}, 3: {0, 3}}
    if int(rows[0]['phase']) != 0:
        raise ValueError('trace does not start in the initial phase')
    for previous, current in zip(rows, rows[1:]):
        if int(current['phase']) not in allowed[int(previous['phase'])]:
            raise ValueError('invalid adaptive phase transition')
        if int(current['skipped']) < int(previous['skipped']):
            raise ValueError('sharpness bypass cannot restart USM')
    if not adaptive and any(int(row['phase']) or int(row['changed']) for row in rows):
        raise ValueError('fixed mode contains adaptive activity')


def verify_terminal_state(result, rows):
    outcome, phase = result['adaptive_outcome'], int(rows[-1]['phase'])
    if outcome == 'settled' and (phase not in (0, 3) or not result['first_settled_frame']):
        raise ValueError('settled outcome contradicts trace phase')
    if outcome == 'disabled' and any(int(row['phase']) or int(row['changed']) for row in rows):
        raise ValueError('disabled tuner contains adaptive activity')
    if result['first_settled_frame'] == len(rows) and outcome != 'settled':
        raise ValueError('last-frame settlement contradicts outcome')


def verify_trace(record, path):
    rows = trace_rows(path)
    adaptive = bool(record['job']['adaptive'])
    verify_trace_activity(rows, adaptive, record['result']['adaptive_outcome'])
    verify_trace_counters(record['result'], rows)
    verify_trace_transitions(rows, adaptive)
    verify_terminal_state(record['result'], rows)
    expected = bench.trace_summary(path, adaptive)
    if json.dumps(record['summary'], sort_keys=True) != json.dumps(expected, sort_keys=True):
        raise ValueError('derived adaptive summary differs from trace')
    return trace_metrics(rows)


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
    verify_outcome(result, controls)


def verify_sharpness(result):
    skip, lap = result['skip_usm'], result['lap_mean']
    if type(skip) is not int or skip not in (0, 1) or type(lap) is not int or lap < 0:
        raise ValueError('invalid sharpness runtime evidence')
    if skip != int(0 < result['sharp_threshold'] < lap):
        raise ValueError('sharpness bypass contradicts runtime evidence')
    return bool(skip)


def verify_outcome(result, controls):
    if verify_sharpness(result):
        allowed = ('sharpness-bypass',)
    elif controls['UP_PROFILE_ADAPTIVE'] == '1':
        allowed = ('settled', 'searching', 'fallback', 'disabled')
    else:
        allowed = ('fixed',)
    if result['adaptive_outcome'] not in allowed:
        raise ValueError('adaptive outcome contradicts captured mode')


def verify_record(directory, record, clip, treatment, trace):
    if record['returncode'] != 0 or record.get('failure') or record['job'] != bench.settings(clip, treatment):
        raise ValueError('failed capture or mismatched capture identity')
    if record['trace'] != trace:
        raise ValueError('capture trace differs from pair')
    verify_runtime(record, verify_invocation(directory, record))
    computed = verify_trace(record, child(directory, trace))
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
