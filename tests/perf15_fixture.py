"""Small deterministic capture data for PERF-15 evidence regressions."""
import json

import bench_perf15 as bench


def invocation(job, trace):
    command = ['unused/' + job['binary'], '12', str(job['usm']),
               str(job['size']*16//9), str(job['size']), '2700', '1', '0', '0',
               '33333', str(trace)]
    environment = dict(UP_PROFILE_INPUT='unused/' + job['clip'] + '.yuv',
                       UP_PROFILE_WIDTH=str(job['width']), UP_PROFILE_HEIGHT=str(job['height']),
                       UP_PROFILE_ADAPTIVE=str(job['adaptive']), UP_PROFILE_WARMUP='0',
                       UP_PROFILE_SHARP_THRESHOLD='3500', UP_PROFILE_ZEROCOPY='1',
                       UP_PROFILE_USM_CPU_FIRST='0', UP_PROFILE_USM_CPU_COUNT=str(job['affinity']),
                       UP_PROFILE_VERIFY_PIXELS='0')
    return dict(command=command, environment=environment)


def write_capture(directory, clip, treatment, index, value, outcome):
    trace = directory / ('%d.csv' % index)
    trace.write_text('frame,total,processing_cpu\n' + ''.join(
        '%d,%.3f,%.3f\n' % (frame, value, value) for frame in range(2700)))
    job = bench.settings(clip, treatment)
    result = dict.fromkeys(bench.METRICS, value) | dict(
        adaptive_outcome=outcome, executor=0, zerocopy=1, sharp_threshold=3500, warmup=0,
        skip_usm=int(outcome == 'sharpness-bypass'),
        lap_mean=4000 if outcome == 'sharpness-bypass' else 1000,
        tuner_policy='latency-experiment' if treatment == 'latency' else 'legacy')
    return dict(job=job, trace=trace.name, returncode=0, **invocation(job, trace),
                result=result, stdout=json.dumps(result), stderr='')


def fake_pair(args, **job):
    job.pop('rows')
    records = [write_capture(args.output, job['clip'], name, index,
                             1.0 if name == 'baseline' else 1.2,
                             fixture_outcome(name))
               for index, name in enumerate(job['order'])]
    (args.output / 'results.json').write_text(json.dumps(records))
    by_name = {row['job']['treatment']: row for row in records}
    return dict(**job, valid_outcomes=False, ratios=dict.fromkeys(bench.METRICS, 1.2),
                baseline=by_name['baseline']['trace'], candidate=by_name[job['treatment']]['trace'])


def fixture_outcome(treatment):
    if treatment == 'baseline':
        return 'fixed'
    return 'fallback' if bench.settings('animation', treatment)['adaptive'] else 'sharpness-bypass'
