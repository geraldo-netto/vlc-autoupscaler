"""Small deterministic capture data for PERF-15 evidence regressions."""
import json

import bench_perf15 as bench


def write_capture(directory, clip, treatment, index, value, outcome):
    trace = directory / ('%d.csv' % index)
    trace.write_text('frame,total,processing_cpu\n' + ''.join(
        '%d,%.3f,%.3f\n' % (frame, value, value) for frame in range(2700)))
    return dict(job=bench.settings(clip, treatment), trace=trace.name, returncode=0,
                result=dict.fromkeys(bench.METRICS, value) | {'adaptive_outcome': outcome})


def fake_pair(args, **job):
    job.pop('rows')
    records = [write_capture(args.output, job['clip'], name, index,
                             1.0 if name == 'baseline' else 1.2,
                             'fixed' if name == 'baseline' else 'fallback')
               for index, name in enumerate(job['order'])]
    (args.output / 'results.json').write_text(json.dumps(records))
    by_name = {row['job']['treatment']: row for row in records}
    return dict(**job, valid_outcomes=False, ratios=dict.fromkeys(bench.METRICS, 1.2),
                baseline=by_name['baseline']['trace'], candidate=by_name[job['treatment']]['trace'])
